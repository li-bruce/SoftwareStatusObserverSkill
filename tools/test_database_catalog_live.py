"""Exercise collectors against the isolated db-vis Compose databases.

This is an opt-in integration test: it changes only named synthetic fixtures on
the documented loopback ports. Missing URLs fail unless --allow-missing is set.
"""

import argparse
import json
import os
from pathlib import Path
import sys
import unittest
from urllib.parse import unquote, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/business-observer/scripts"))

from bo_observer.data.catalog import collect, export_sqlalchemy_metadata
from bo_observer.data.contract import validate_catalog
from bo_observer.data.projection import structure_differences


ALLOW_MISSING = False


def database_url(case, variable, port):
    """Keep synthetic schema mutations confined to the local acceptance services."""
    url = os.environ.get(variable)
    if not url:
        if ALLOW_MISSING:
            case.skipTest(f"{variable} was not configured (--allow-missing).")
        case.fail(f"Set {variable} for the real database integration test.")
    parts = urlsplit(url)
    if parts.hostname not in {"localhost", "127.0.0.1", "::1"} or parts.port != port:
        case.fail(f"{variable} must address the isolated loopback service on port {port}.")
    return url


def resource(catalog, key):
    return next(item for item in catalog["resources"] if item["key"] == key)


def fields(value):
    return {item["name"]: item for item in value["fields"]}


class LiveCatalogTests(unittest.TestCase):
    def snapshot(self, engine, variable, **options):
        store = {"id": "live-catalog", "engine": engine, "url_env": variable, **options}
        result = collect(store)
        validate_catalog(result, store)
        self.assertNotIn("private-live-row", json.dumps(result))
        return result

    def test_postgresql_real_constraints_defaults_and_migrations(self):
        from sqlalchemy import create_engine, text, MetaData, Table, Column, Integer

        variable = "BO_TEST_POSTGRES_URL"
        url = database_url(self, variable, 19432)
        engine = create_engine(url)

        def cleanup():
            with engine.begin() as connection:
                connection.execute(text("DROP TABLE IF EXISTS bo_test_catalog_generated"))
                connection.execute(text("DROP TABLE IF EXISTS bo_test_catalog_images"))
                connection.execute(text("DROP TABLE IF EXISTS bo_test_catalog_projects"))

        try:
            cleanup()
            metadata = MetaData()
            Table(
                "bo_test_catalog_generated",
                metadata,
                Column("id", Integer, primary_key=True),
                Column("score", Integer, server_default=text("0")),
            )
            metadata.create_all(engine)
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "CREATE TABLE bo_test_catalog_projects(id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE)"
                    )
                )
                connection.execute(
                    text(
                        "CREATE TABLE bo_test_catalog_images(id INTEGER PRIMARY KEY, project_id INTEGER REFERENCES bo_test_catalog_projects(id) ON DELETE CASCADE, title TEXT NOT NULL, score INTEGER NOT NULL DEFAULT 0 CHECK(score >= 0))"
                    )
                )
                connection.execute(
                    text("CREATE INDEX bo_test_catalog_title ON bo_test_catalog_images(title)")
                )
                connection.execute(
                    text(
                        "CREATE UNIQUE INDEX bo_test_catalog_title_lower ON bo_test_catalog_images(lower(title))"
                    )
                )
                connection.execute(
                    text("INSERT INTO bo_test_catalog_projects VALUES(1, 'private-live-row')")
                )
            first = self.snapshot("sqlalchemy", variable)
            declared = export_sqlalchemy_metadata(metadata, "live-catalog")
            self.assertEqual(structure_differences(first, declared), [])
            image = resource(first, "table:bo_test_catalog_images")
            expression_index = next(
                item
                for item in image["constraints"]
                if item["name"] == "bo_test_catalog_title_lower"
            )
            self.assertEqual(expression_index["fields"], [])
            self.assertTrue(json.loads(expression_index["description"])["unique"])
            self.assertIn("lower", expression_index["description"])
            self.assertEqual(first["coverage"], "partial")
            self.assertEqual(fields(image)["score"]["default"], "0")
            self.assertFalse(fields(image)["title"]["nullable"])
            foreign = next(item for item in image["constraints"] if item["kind"] == "foreign_key")
            self.assertEqual(foreign["target"], "table:bo_test_catalog_projects")
            self.assertEqual(json.loads(foreign["description"])["ondelete"], "CASCADE")
            self.assertTrue(
                {"primary_key", "foreign_key", "index", "check"}
                <= {item["kind"] for item in image["constraints"]}
            )
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "ALTER TABLE bo_test_catalog_images ADD COLUMN reviewed BOOLEAN DEFAULT false"
                    )
                )
                connection.execute(
                    text("ALTER TABLE bo_test_catalog_images RENAME COLUMN title TO caption")
                )
            second = self.snapshot("sqlalchemy", variable)
            changed = fields(resource(second, "table:bo_test_catalog_images"))
            self.assertIn("reviewed", changed)
            self.assertIn("caption", changed)
            self.assertNotIn("title", changed)
            self.assertEqual(
                resource(first, "table:bo_test_catalog_projects"),
                resource(second, "table:bo_test_catalog_projects"),
            )
            self.assertEqual(second, self.snapshot("sqlalchemy", variable))
        finally:
            try:
                cleanup()
            finally:
                engine.dispose()

    def test_mongodb_live_validator_changes_and_unvalidated_collection(self):
        from pymongo import MongoClient

        variable = "BO_TEST_MONGODB_URL"
        url = database_url(self, variable, 19017)
        with MongoClient(url, serverSelectionTimeoutMS=5000) as client:
            database = client["bo_test"]

            def cleanup():
                database.drop_collection("bo_test_catalog_images")
                database.drop_collection("bo_test_catalog_free")

            cleanup()
            try:
                schema = {
                    "bsonType": "object",
                    "required": ["title"],
                    "properties": {
                        "title": {"bsonType": "string"},
                        "score": {"bsonType": "int", "minimum": 0},
                    },
                }
                collection = database.create_collection(
                    "bo_test_catalog_images", validator={"$jsonSchema": schema}
                )
                database.create_collection("bo_test_catalog_free")
                collection.create_index("title", name="bo_test_catalog_title", unique=True)
                collection.insert_one({"title": "private-live-row", "score": 2})
                database["bo_test_catalog_free"].insert_one({"secret": "private-live-row"})
                first = self.snapshot("mongodb", variable, namespace="bo_test")
                image = resource(first, "collection:bo_test_catalog_images")
                self.assertTrue(fields(image)["title"]["required"])
                self.assertTrue(
                    any(
                        item["kind"] == "unique" and item["fields"] == ["title"]
                        for item in image["constraints"]
                    )
                )
                self.assertEqual(
                    set(fields(resource(first, "collection:bo_test_catalog_free"))), {"_id"}
                )
                self.assertEqual(first["coverage"], "partial")
                schema["properties"]["caption"] = schema["properties"].pop("title")
                schema["properties"]["reviewed"] = {"bsonType": "bool"}
                schema["required"] = ["caption"]
                database.command(
                    "collMod", "bo_test_catalog_images", validator={"$jsonSchema": schema}
                )
                collection.drop_index("bo_test_catalog_title")
                collection.update_many(
                    {}, {"$rename": {"title": "caption"}, "$set": {"reviewed": False}}
                )
                collection.create_index("caption", name="bo_test_catalog_caption", unique=True)
                second = self.snapshot("mongodb", variable, namespace="bo_test")
                updated = fields(resource(second, "collection:bo_test_catalog_images"))
                self.assertEqual(set(updated), {"_id", "caption", "reviewed", "score"})
                self.assertEqual(second, self.snapshot("mongodb", variable, namespace="bo_test"))
            finally:
                cleanup()

    def test_redis_live_bounded_type_sampling_never_collects_values(self):
        from redis import Redis

        variable = "BO_TEST_REDIS_URL"
        url = database_url(self, variable, 19379)
        client = Redis.from_url(url, socket_timeout=5)
        keys = ["bo_test:catalog:one", "bo_test:catalog:two", "bo_test:catalog:three"]
        try:
            client.delete(*keys)
            client.hset(keys[0], mapping={"title": "private-live-row"})
            client.set(keys[1], "private-live-row")
            first = self.snapshot("redis", variable, key_patterns=["bo_test:catalog:*"])
            self.assertEqual(fields(first["resources"][0])["value"]["native_type"], "unknown")
            second = self.snapshot(
                "redis",
                variable,
                key_patterns=["bo_test:catalog:*"],
                sample_limit=100,
                scan_limit=100,
            )
            self.assertEqual(fields(second["resources"][0])["value"]["native_type"], "hash|string")
            self.assertEqual(second["coverage"], "sampled")
            client.zadd(keys[2], {"private-live-row": 1})
            third = self.snapshot(
                "redis",
                variable,
                key_patterns=["bo_test:catalog:*"],
                sample_limit=100,
                scan_limit=100,
            )
            self.assertEqual(
                fields(third["resources"][0])["value"]["native_type"], "hash|string|zset"
            )
            self.assertNotIn(keys[0], json.dumps(third))
        finally:
            try:
                client.delete(*keys)
            finally:
                client.close()

    def test_neo4j_live_constraints_property_changes_and_real_label_tokens(self):
        from neo4j import GraphDatabase

        variable = "BO_TEST_NEO4J_URL"
        url = database_url(self, variable, 19687)
        parts = urlsplit(url)
        auth = (unquote(parts.username), unquote(parts.password or "")) if parts.username else None
        clean_url = urlunsplit(
            (parts.scheme, parts.netloc.rsplit("@", 1)[-1], parts.path, parts.query, parts.fragment)
        )
        with GraphDatabase.driver(clean_url, auth=auth, connection_timeout=5) as driver:
            with driver.session(database="neo4j") as session:

                def execute(query):
                    session.run(query).consume()

                def cleanup():
                    execute("DROP INDEX bo_test_catalog_title IF EXISTS")
                    execute("DROP INDEX bo_test_catalog_caption IF EXISTS")
                    execute("DROP CONSTRAINT bo_test_catalog_id IF EXISTS")
                    execute("MATCH (n:BOTestCatalogImage) DETACH DELETE n")
                    execute("MATCH (n:BOTestCatalogProject) DETACH DELETE n")

                cleanup()
                try:
                    execute(
                        "CREATE CONSTRAINT bo_test_catalog_id FOR (n:BOTestCatalogImage) REQUIRE n.id IS UNIQUE"
                    )
                    execute(
                        "CREATE INDEX bo_test_catalog_title FOR (n:BOTestCatalogImage) ON (n.title)"
                    )
                    execute(
                        "CREATE (i:BOTestCatalogImage {id: 'one', title: 'private-live-row'}), (p:BOTestCatalogProject {id: 'project'}), (i)-[:BOTestCatalogBelongsTo]->(p)"
                    )
                    first = self.snapshot("neo4j", variable, namespace="neo4j")
                    image = resource(first, "label:BOTestCatalogImage")
                    self.assertEqual(set(fields(image)), {"id", "title"})
                    self.assertTrue(any(item["kind"] == "unique" for item in image["constraints"]))
                    self.assertEqual(
                        resource(first, "relationship:BOTestCatalogBelongsTo")["kind"],
                        "relationship",
                    )
                    self.assertEqual(first["coverage"], "partial")
                    self.assertFalse(
                        any(
                            item["kind"] == "connects"
                            for value in first["resources"]
                            for item in value["constraints"]
                        )
                    )
                    execute("MATCH (n:BOTestCatalogImage) SET n.caption = n.title REMOVE n.title")
                    execute("DROP INDEX bo_test_catalog_title")
                    execute(
                        "CREATE INDEX bo_test_catalog_caption FOR (n:BOTestCatalogImage) ON (n.caption)"
                    )
                    second = self.snapshot("neo4j", variable, namespace="neo4j")
                    self.assertEqual(
                        set(fields(resource(second, "label:BOTestCatalogImage"))), {"id", "caption"}
                    )
                    self.assertEqual(second, self.snapshot("neo4j", variable, namespace="neo4j"))
                finally:
                    cleanup()


def main():
    global ALLOW_MISSING
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="Explicitly skip databases whose test URL is not configured.",
    )
    parser.add_argument("--report", type=Path, help="Write a credential-free JSON test summary.")
    arguments = parser.parse_args()
    ALLOW_MISSING = arguments.allow_missing
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(LiveCatalogTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if arguments.report:
        arguments.report.parent.mkdir(parents=True, exist_ok=True)
        arguments.report.write_text(
            json.dumps(
                {
                    "suite": "database-catalog-live",
                    "tests": result.testsRun,
                    "failures": len(result.failures),
                    "errors": len(result.errors),
                    "skipped": len(result.skipped),
                    "success": result.wasSuccessful(),
                    "engines": ["postgresql", "mongodb", "redis", "neo4j"],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
