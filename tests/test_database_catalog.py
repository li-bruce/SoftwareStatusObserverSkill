"""Real SQLite reflection and bounded driver-contract tests for data catalogs."""

import json
from contextlib import closing
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/vibelens/scripts"))

from bo_observer.data import catalog
from bo_observer.data.contract import validate_catalog
from bo_observer.observation.observation_scope import bo_is_internal


class CatalogTests(unittest.TestCase):
    def setUp(self):
        scratch = Path(__file__).resolve().parents[1] / ".validation"
        scratch.mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=scratch)
        self.root = Path(self.temporary.name)
        self.addCleanup(self.temporary.cleanup)
        self.db = self.root / "application.db"
        self.store = {"id": "app", "engine": "sqlalchemy", "url_env": "BO_TEST_DATABASE_URL"}
        self.env = patch.dict(os.environ, {"BO_TEST_DATABASE_URL": "sqlite:///application.db"})
        self.env.start()
        self.addCleanup(self.env.stop)

    def create_database(self):
        with closing(sqlite3.connect(self.db)) as connection, connection:
            connection.executescript(
                """
                CREATE TABLE projects(id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE);
                CREATE TABLE images(id INTEGER PRIMARY KEY, project_id INTEGER,
                    title TEXT NOT NULL, rating INTEGER DEFAULT 0 CHECK(rating >= 0),
                    FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE);
                CREATE INDEX images_title ON images(title);
                INSERT INTO projects VALUES(1, 'private-record-do-not-export');
            """
            )

    def test_real_sqlite_catalog_keeps_constraints_without_rows(self):
        self.create_database()
        result = catalog.collect(self.store, root=self.root)
        validate_catalog(result, self.store)
        self.assertEqual(result["protocol"], "bo-data-catalog/v1")
        self.assertEqual(result["coverage"], "complete")
        resources = {item["key"]: item for item in result["resources"]}
        self.assertEqual(set(resources), {"table:projects", "table:images"})
        image = resources["table:images"]
        fields = {item["name"]: item for item in image["fields"]}
        self.assertEqual(fields["project_id"]["native_type"], "INTEGER")
        self.assertFalse(fields["title"]["nullable"])
        self.assertTrue(fields["id"]["primary_key"])
        self.assertEqual(fields["rating"]["default"], "0")
        foreign = next(item for item in image["constraints"] if item["kind"] == "foreign_key")
        self.assertEqual(json.loads(foreign["description"])["ondelete"], "CASCADE")
        self.assertEqual(
            (foreign["fields"], foreign["target"], foreign["target_fields"]),
            (["project_id"], "table:projects", ["id"]),
        )
        self.assertEqual(
            {item["kind"] for item in image["constraints"]},
            {"primary_key", "foreign_key", "index", "check"},
        )
        serialized = json.dumps(result)
        self.assertNotIn("private-record-do-not-export", serialized)
        self.assertNotIn(str(self.db), serialized)
        self.assertFalse(bo_is_internal())

    def test_repeated_collection_is_stable_and_schema_change_is_detected(self):
        self.create_database()
        before = catalog.collect(self.store, root=self.root)
        self.assertEqual(before, catalog.collect(self.store, root=self.root))
        with closing(sqlite3.connect(self.db)) as connection, connection:
            connection.execute("ALTER TABLE images ADD COLUMN reviewed BOOLEAN")
        after = catalog.collect(self.store, root=self.root)
        self.assertNotEqual(before, after)
        self.assertEqual(
            {item["key"] for item in before["resources"]},
            {item["key"] for item in after["resources"]},
        )
        fields = next(item for item in after["resources"] if item["name"] == "images")["fields"]
        self.assertIn("reviewed", [item["name"] for item in fields])

    def test_collection_does_not_create_missing_sqlite_database(self):
        with self.assertRaisesRegex(catalog.CatalogError, "does not exist"):
            catalog.collect(self.store, root=self.root)
        self.assertFalse(self.db.exists())

    def test_sqlite_connections_are_read_only_and_observer_marked(self):
        self.create_database()
        import sqlalchemy

        original = sqlalchemy.create_engine
        observed = []

        def connect(url, **options):
            self.assertTrue(bo_is_internal())
            self.assertEqual(url.query["mode"], "ro")
            engine = original(url, **options)

            def before_execute(*args):
                observed.append(bo_is_internal())

            sqlalchemy.event.listen(engine, "before_cursor_execute", before_execute)
            return engine

        with patch.object(sqlalchemy, "create_engine", connect):
            catalog.collect(self.store, root=self.root)
        self.assertTrue(observed)
        self.assertTrue(all(observed))

    def test_in_memory_url_is_not_misrepresented_as_real_application_database(self):
        with patch.dict(os.environ, {"BO_TEST_DATABASE_URL": "sqlite:///:memory:"}):
            with self.assertRaisesRegex(catalog.CatalogError, "existing file"):
                catalog.collect(self.store, root=self.root)

    def test_views_are_explicitly_outside_table_coverage(self):
        self.create_database()
        with closing(sqlite3.connect(self.db)) as connection, connection:
            connection.execute("CREATE VIEW project_names AS SELECT name FROM projects")
        result = catalog.collect(self.store, root=self.root)
        self.assertEqual(result["coverage"], "partial")
        self.assertTrue(any("Views" in reason for reason in result["limitations"]))

    def test_unreflectable_expression_index_is_an_explicit_coverage_gap(self):
        self.create_database()
        with closing(sqlite3.connect(self.db)) as connection, connection:
            connection.execute("CREATE INDEX images_title_lower ON images(lower(title))")
        result = catalog.collect(self.store, root=self.root)
        validate_catalog(result)
        self.assertEqual(result["coverage"], "partial")
        self.assertTrue(
            any("incomplete metadata reflection" in message for message in result["limitations"])
        )

    def test_sqlalchemy_declaration_export_has_no_database_access(self):
        import sqlalchemy as sa

        metadata = sa.MetaData()
        sa.Table("projects", metadata, sa.Column("id", sa.Integer, primary_key=True))
        sa.Table(
            "images",
            metadata,
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("project_id", sa.ForeignKey("projects.id")),
            sa.Column("title", sa.String(40), nullable=False, unique=True),
            sa.CheckConstraint("length(title)>0", name="title_required"),
        )
        with patch.object(sa, "create_engine", side_effect=AssertionError("must not connect")):
            result = catalog.export_sqlalchemy_metadata(metadata, "app")
        self.assertEqual(result["origin"], "declaration")
        validate_catalog(result)
        image = next(item for item in result["resources"] if item["name"] == "images")
        self.assertNotIn("default", next(item for item in image["fields"] if item["name"] == "id"))
        self.assertEqual(
            next(item for item in image["fields"] if item["name"] == "title")["native_type"],
            "VARCHAR(40)",
        )
        self.assertEqual(
            next(item for item in image["constraints"] if item["kind"] == "foreign_key")["target"],
            "table:projects",
        )

    def test_orm_unresolved_foreign_table_can_still_be_exported(self):
        import sqlalchemy as sa

        metadata = sa.MetaData()
        sa.Table("images", metadata, sa.Column("owner", sa.ForeignKey("accounts.users.id")))
        result = catalog.export_sqlalchemy_metadata(metadata, "app")
        foreign = next(
            item for item in result["resources"][0]["constraints"] if item["kind"] == "foreign_key"
        )
        self.assertEqual(foreign["target"], "table:accounts.users")

    def test_string_server_defaults_match_real_sqlite_ddl(self):
        import sqlalchemy as sa
        from bo_observer.data.projection import structure_differences

        metadata = sa.MetaData()
        sa.Table(
            "defaults", metadata,
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("active", sa.Integer, server_default="1"),
            sa.Column("author", sa.String, server_default="O'Reilly"),
            sa.Column("score", sa.Integer, server_default=sa.text("42")),
        )
        engine = sa.create_engine("sqlite:///" + str(self.db))
        try:
            metadata.create_all(engine)
        finally:
            engine.dispose()
        declared = catalog.export_sqlalchemy_metadata(metadata, "app")
        actual = catalog.collect(self.store, root=self.root)
        self.assertEqual(structure_differences(actual, declared), [])
        fields = {field["name"]: field for field in declared["resources"][0]["fields"]}
        self.assertEqual(fields["active"]["default"], "'1'")
        self.assertEqual(fields["author"]["default"], "'O''Reilly'")
        fields["active"]["default"] = "'2'"
        self.assertTrue(structure_differences(actual, declared))

    def test_missing_driver_is_actionable_and_error_does_not_leak_url(self):
        with patch.object(
            catalog.importlib, "import_module", side_effect=ImportError("private-secret")
        ):
            with self.assertRaisesRegex(catalog.CatalogError, "optional 'sqlalchemy'") as caught:
                catalog.collect(self.store, root=self.root)
        self.assertNotIn("private-secret", str(caught.exception))
        with patch.object(
            catalog,
            "_sqlalchemy",
            side_effect=ValueError("postgresql://user:private-secret@host/db SELECT sensitive"),
        ):
            with self.assertRaises(catalog.CatalogError) as caught:
                catalog.collect(self.store, root=self.root)
        self.assertEqual(
            str(caught.exception), "sqlalchemy metadata collection failed (ValueError)."
        )
        self.assertFalse(bo_is_internal())

    def test_missing_environment_and_unknown_engine_fail_explicitly(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(catalog.CatalogError, "environment"):
                catalog.collect(self.store)
        with self.assertRaisesRegex(catalog.CatalogError, "Unsupported"):
            catalog.collect({**self.store, "engine": "invented"})

    def test_mongo_validator_fields_and_index_rules_without_document_reads(self):
        operations = []
        validator = {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["title"],
                "properties": {
                    "title": {"bsonType": "string"},
                    "address": {
                        "bsonType": "object",
                        "required": ["city"],
                        "properties": {"city": {"bsonType": ["string", "null"]}},
                    },
                    "tags": {
                        "bsonType": "array",
                        "items": {"properties": {"name": {"bsonType": "string"}}},
                    },
                },
            }
        }

        class Collection:
            def list_indexes(inner):
                operations.append(("indexes", bo_is_internal()))
                return [
                    {"name": "_id_", "key": {"_id": 1}},
                    {
                        "name": "title",
                        "key": {"title": 1},
                        "unique": True,
                        "partialFilterExpression": {"active": True},
                    },
                    {"name": "all_fields", "key": {"$**": 1}},
                    {
                        "name": "text_fields",
                        "key": {"_fts": "text", "_ftsx": 1},
                        "weights": {"title": 1, "caption": 1},
                    },
                ]

        class Database:
            def list_collections(inner):
                operations.append(("collections", bo_is_internal()))
                return [
                    {
                        "name": "images",
                        "type": "collection",
                        "options": {"validator": validator, "validationAction": "warn"},
                    }
                ]

            def __getitem__(inner, name):
                return Collection()

        class Client:
            def __init__(inner, *args, **kwargs):
                pass

            def __enter__(inner):
                return inner

            def __exit__(inner, *args):
                operations.append(("close", bo_is_internal()))

            def get_default_database(inner):
                return Database()

        with patch.object(catalog, "_dependency", return_value=SimpleNamespace(MongoClient=Client)):
            result = catalog.collect({**self.store, "engine": "mongodb"})
        self.assertEqual(result["coverage"], "partial")
        resource = result["resources"][0]
        validate_catalog(result)
        fields = {item["name"]: item for item in resource["fields"]}
        self.assertTrue(fields["title"]["required"])
        self.assertFalse(fields["address.city"]["required"])
        self.assertTrue(fields["address.city"]["nullable"])
        self.assertIn("tags[].name", fields)
        validation = next(item for item in resource["constraints"] if item["kind"] == "validation")
        self.assertEqual(json.loads(validation["description"])["validationAction"], "warn")
        index = next(item for item in resource["constraints"] if item["name"] == "title")
        self.assertIn("partialFilterExpression", index["description"])
        wildcard = next(item for item in resource["constraints"] if item["name"] == "all_fields")
        self.assertEqual(wildcard["fields"], [])
        self.assertIn("$**", wildcard["description"])
        self.assertNotIn("$**", fields)
        self.assertNotIn("_fts", fields)
        text_index = next(item for item in resource["constraints"] if item["name"] == "text_fields")
        self.assertEqual(text_index["fields"], ["title", "caption"])
        self.assertTrue(all(marked for _, marked in operations))

    def redis_driver(self, calls):
        class Client:
            def ping(inner):
                calls.append(("ping", bo_is_internal()))

            def scan(inner, **options):
                calls.append(("scan", options))
                return 2, [
                    b"session:private-key-1",
                    b"session:private-key-2",
                    b"session:private-key-3",
                ]

            def type(inner, key):
                calls.append(("type", bo_is_internal()))
                return b"hash"

            def close(inner):
                calls.append(("close", bo_is_internal()))

        return SimpleNamespace(Redis=SimpleNamespace(from_url=lambda *args, **kwargs: Client()))

    def test_redis_sampling_is_opt_in_and_no_keys_or_values_are_exported(self):
        calls = []
        store = {**self.store, "engine": "redis", "key_patterns": ["session:*"]}
        with patch.object(catalog, "_dependency", return_value=self.redis_driver(calls)):
            result = catalog.collect(store)
        self.assertEqual([item[0] for item in calls], ["ping", "close"])
        self.assertEqual(result["coverage"], "partial")
        self.assertEqual(result["resources"][0]["fields"][0]["native_type"], "unknown")
        calls.clear()
        with patch.object(catalog, "_dependency", return_value=self.redis_driver(calls)):
            result = catalog.collect({**store, "sample_limit": 2, "scan_limit": 1})
        self.assertEqual(result["coverage"], "sampled")
        validate_catalog(result)
        self.assertEqual(len([item for item in calls if item[0] == "type"]), 2)
        self.assertEqual(len([item for item in calls if item[0] == "scan"]), 1)
        self.assertNotIn("private-key", json.dumps(result))
        self.assertEqual(result["resources"][0]["fields"][0]["native_type"], "hash")

    def test_redis_rejects_unbounded_sampling(self):
        with patch.object(catalog, "_dependency", return_value=self.redis_driver([])):
            for limit in (-1, 101, True, "10"):
                with self.subTest(limit=limit), self.assertRaises(catalog.CatalogError):
                    catalog.collect({**self.store, "engine": "redis", "sample_limit": limit})

    def test_neo4j_uses_metadata_only_and_does_not_invent_connections(self):
        queries = []
        connections = []

        class Session:
            def __enter__(inner):
                return inner

            def __exit__(inner, *args):
                pass

            def run(inner, query):
                queries.append(query)
                self.assertTrue(bo_is_internal())
                if query.startswith("CALL db.labels"):
                    return [{"label": "Image"}, {"label": "Project"}]
                if query.startswith("CALL db.relationshipTypes"):
                    return [{"relationshipType": "BELONGS_TO"}]
                if query == "SHOW CONSTRAINTS":
                    return [
                        {
                            "name": "image_id",
                            "type": "UNIQUENESS",
                            "entityType": "NODE",
                            "labelsOrTypes": ["Image"],
                            "properties": ["id"],
                        },
                        {
                            "name": "weight_type",
                            "type": "RELATIONSHIP_PROPERTY_TYPE",
                            "entityType": "RELATIONSHIP",
                            "labelsOrTypes": ["BELONGS_TO"],
                            "properties": ["weight"],
                            "propertyType": "FLOAT",
                        },
                    ]
                return [
                    {
                        "name": "image_title",
                        "type": "RANGE",
                        "entityType": "NODE",
                        "labelsOrTypes": ["Image"],
                        "properties": ["title"],
                    }
                ]

        class Driver:
            def __enter__(inner):
                return inner

            def __exit__(inner, *args):
                pass

            def session(inner, **options):
                self.assertEqual(options["default_access_mode"], "READ")
                return Session()

        def driver(url, **options):
            connections.append((url, options))
            return Driver()

        dependency = SimpleNamespace(
            GraphDatabase=SimpleNamespace(driver=driver),
            READ_ACCESS="READ",
            Query=lambda query, timeout: query,
        )
        with (
            patch.dict(
                os.environ, {"BO_TEST_DATABASE_URL": "bolt://user:private-secret@localhost:7687"}
            ),
            patch.object(catalog, "_dependency", return_value=dependency),
        ):
            result = catalog.collect({**self.store, "engine": "neo4j"})
        self.assertEqual(result["coverage"], "partial")
        self.assertEqual(connections[0][0], "bolt://localhost:7687")
        validate_catalog(result)
        self.assertEqual(connections[0][1]["auth"], ("user", "private-secret"))
        self.assertNotIn("private-secret", json.dumps(result))
        self.assertEqual(len(queries), 4)
        self.assertFalse(any("MATCH" in query or "visualization" in query for query in queries))
        resources = {item["key"]: item for item in result["resources"]}
        self.assertEqual(
            set(resources), {"label:Image", "label:Project", "relationship:BELONGS_TO"}
        )
        self.assertEqual(resources["relationship:BELONGS_TO"]["fields"][0]["native_type"], "FLOAT")
        self.assertFalse(
            any(
                item["kind"] == "connects"
                for resource in result["resources"]
                for item in resource["constraints"]
            )
        )


if __name__ == "__main__":
    unittest.main()
