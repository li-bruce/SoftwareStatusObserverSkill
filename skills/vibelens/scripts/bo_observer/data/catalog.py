"""Read database structure without collecting records or running migrations.

Collectors return the same catalog shape but keep the coverage limits of each
storage model. Optional drivers are imported only when their collector is used.
"""

import importlib
import json
import os
import warnings
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, unquote

from bo_observer.observation.observation_scope import bo_internal


class CatalogError(RuntimeError):
    """A metadata failure safe to show without connection details or row data."""


def _dependency(name):
    try:
        return importlib.import_module(name)
    except ImportError:
        raise CatalogError(f"Install the optional '{name}' package for this collector.") from None


def _catalog(store, *, origin="database", coverage="complete"):
    return {
        "protocol": "bo-data-catalog/v1",
        "store_id": store["id"],
        "engine": store["engine"],
        "origin": origin,
        "coverage": coverage,
        "limitations": [],
        "resources": [],
    }


def _resource(kind, name, *, key=None):
    return {
        "key": key or f"{kind}:{name}",
        "kind": kind,
        "name": name,
        "fields": [],
        "constraints": [],
    }


def _constraint(kind, name, fields, **extra):
    return {"kind": kind, "name": name or "", "fields": list(fields), **extra}


def _finish(catalog):
    """Make snapshots deterministic so a metadata poll does not move the graph."""
    catalog["limitations"] = sorted(set(catalog["limitations"]))
    catalog["resources"].sort(key=lambda item: item["key"])
    for resource in catalog["resources"]:
        resource["fields"].sort(key=lambda item: item["name"])
        resource["constraints"].sort(key=lambda item: json.dumps(item, sort_keys=True))
    return catalog


def collect(store, *, root=None):
    """Collect configured metadata; failures never expose the connection URL.

    ``root`` resolves relative SQLite database paths. Credentials stay in the
    environment, and all collector queries are marked as observer operations.
    """
    collectors = {
        "sqlalchemy": _sqlalchemy,
        "mongodb": _mongodb,
        "redis": _redis,
        "neo4j": _neo4j,
    }
    engine = store.get("engine")
    if engine not in collectors:
        raise CatalogError("Unsupported database collector.")
    url = os.environ.get(store.get("url_env", ""))
    if not url:
        raise CatalogError("The configured database URL environment variable is missing.")
    try:
        with bo_internal():
            return _finish(collectors[engine](store, url, root))
    except CatalogError:
        raise
    except Exception as error:
        # Driver errors can include credentials, full queries, or rejected values.
        raise CatalogError(
            f"{engine} metadata collection failed ({type(error).__name__})."
        ) from None


def _table_key(name, schema=None):
    return "table:" + (f"{schema}." if schema else "") + name


def _inspect(inspector, method, catalog, *args, **kwargs):
    """Keep dialect reflection warnings as coverage gaps instead of silent omissions."""
    with warnings.catch_warnings(record=True) as noticed:
        warnings.simplefilter("always")
        result = getattr(inspector, method)(*args, **kwargs)
    if noticed:
        catalog["coverage"] = "partial"
        catalog["limitations"].append(
            "The dialect reported incomplete metadata reflection; some native objects or types may not be represented."
        )
    return result


def _sqlalchemy(store, url, root):
    sa = _dependency("sqlalchemy")
    connection_url = sa.engine.make_url(url)
    if connection_url.get_backend_name() == "sqlite":
        database = connection_url.database
        if not database or database == ":memory:" or database.startswith("file:"):
            raise CatalogError(
                "SQLite collection requires an existing file; export in-memory declarations instead."
            )
        path = Path(database)
        if not path.is_absolute():
            path = Path(root or Path.cwd()) / path
        path = path.resolve()
        if not path.is_file():
            raise CatalogError("The configured SQLite database file does not exist.")
        # SQLite's read-only URI prevents accidental creation of a new database.
        connection_url = connection_url.set(
            database="file:" + path.as_posix(),
            query={**connection_url.query, "mode": "ro", "uri": "true"},
        )
    catalog = _catalog(store)
    schema = store.get("namespace") or None
    engine = sa.create_engine(connection_url)
    try:
        with engine.connect() as connection:
            inspector = sa.inspect(connection)
            for name in _inspect(inspector, "get_table_names", catalog, schema=schema):
                resource = _resource("table", name, key=_table_key(name, schema))
                primary = _inspect(inspector, "get_pk_constraint", catalog, name, schema=schema)
                primary_fields = primary.get("constrained_columns") or []
                for column in _inspect(inspector, "get_columns", catalog, name, schema=schema):
                    resource["fields"].append(
                        {
                            "name": column["name"],
                            "native_type": str(column["type"]),
                            "nullable": column.get("nullable"),
                            "primary_key": column["name"] in primary_fields,
                            "default": (
                                str(column["default"])
                                if column.get("default") is not None
                                else None
                            ),
                            "generated": bool(column.get("computed") or column.get("identity")),
                        }
                    )
                if primary_fields:
                    resource["constraints"].append(
                        _constraint("primary_key", primary.get("name"), primary_fields)
                    )
                _reflect_constraints(inspector, name, schema, resource, catalog)
                catalog["resources"].append(resource)
            views = _inspect(inspector, "get_view_names", catalog, schema=schema)
            if views:
                catalog["coverage"] = "partial"
                catalog["limitations"].append(
                    "Views are outside this table catalog; their definitions were not collected."
                )
    finally:
        engine.dispose()
    catalog["limitations"].append(
        "Coverage is limited to tables in the configured/default schema and dialect-supported constraints; triggers and stored routines are not inspected."
    )
    return catalog


def _reflect_constraints(inspector, name, schema, resource, catalog):
    for method, kind in (
        ("get_foreign_keys", "foreign_key"),
        ("get_unique_constraints", "unique"),
        ("get_indexes", "index"),
        ("get_check_constraints", "check"),
    ):
        try:
            items = _inspect(inspector, method, catalog, name, schema=schema)
        except NotImplementedError:
            catalog["coverage"] = "partial"
            catalog["limitations"].append(
                f"The active dialect does not reflect {kind} constraints."
            )
            continue
        for item in items:
            fields = item.get("constrained_columns", item.get("column_names", [])) or []
            if any(field is None for field in fields):
                catalog["coverage"] = "partial"
                catalog["limitations"].append("An expression index has no complete column mapping.")
            value = _constraint(kind, item.get("name"), [field for field in fields if field])
            if kind == "foreign_key":
                target_schema = item.get("referred_schema") or schema
                if schema is None and target_schema == inspector.default_schema_name:
                    target_schema = None
                value.update(
                    target=_table_key(item["referred_table"], target_schema),
                    target_fields=item.get("referred_columns") or [],
                    description=json.dumps(item.get("options") or {}, sort_keys=True, default=str),
                )
            elif kind == "check":
                value["description"] = item.get("sqltext", "")
            elif kind == "index":
                value["description"] = json.dumps(
                    {
                        key: item[key]
                        for key in ("unique", "expressions", "column_sorting", "dialect_options")
                        if key in item
                    },
                    sort_keys=True,
                    default=str,
                )
            resource["constraints"].append(value)


def export_sqlalchemy_metadata(metadata, store_id, *, dialect=None):
    """Export an application's SQLAlchemy MetaData without opening a database."""
    sa = _dependency("sqlalchemy")
    catalog = _catalog({"id": store_id, "engine": "sqlalchemy"}, origin="declaration")
    with bo_internal():
        for table in metadata.tables.values():
            resource = _resource("table", table.name, key=_table_key(table.name, table.schema))
            for column in table.columns:
                value = {
                    "name": column.name,
                    "native_type": str(column.type),
                    "nullable": column.nullable,
                    "primary_key": column.primary_key,
                    "generated": bool(column.computed is not None or column.identity is not None),
                }
                if column.server_default is not None:
                    if hasattr(column.server_default, "arg"):
                        default = column.server_default.arg
                        # A Python string is a SQL literal, while text()/SQL
                        # expressions are rendered as expressions by SQLAlchemy.
                        if isinstance(default, str):
                            default = sa.literal(default)
                        value["default"] = str(
                            default.compile(dialect=dialect, compile_kwargs={"literal_binds": True})
                        )
                elif not (
                    column.primary_key
                    and column.autoincrement in (True, "auto")
                    and isinstance(column.type, sa.Integer)
                ):
                    value["default"] = None
                resource["fields"].append(value)
            for constraint in table.constraints:
                fields = [column.name for column in constraint.columns]
                if isinstance(constraint, sa.ForeignKeyConstraint):
                    elements = list(constraint.elements)
                    # Metadata may contain a reference whose target table is not loaded.
                    targets = [element.target_fullname.rsplit(".", 1) for element in elements]
                    resource["constraints"].append(
                        _constraint(
                            "foreign_key",
                            constraint.name,
                            fields,
                            target="table:" + targets[0][0],
                            target_fields=[target[1] for target in targets],
                            description=json.dumps(
                                {
                                    key: getattr(constraint, key)
                                    for key in (
                                        "ondelete",
                                        "onupdate",
                                        "deferrable",
                                        "initially",
                                        "match",
                                    )
                                    if getattr(constraint, key) is not None
                                },
                                sort_keys=True,
                            ),
                        )
                    )
                elif isinstance(constraint, sa.PrimaryKeyConstraint) and fields:
                    resource["constraints"].append(
                        _constraint("primary_key", constraint.name, fields)
                    )
                elif isinstance(constraint, sa.UniqueConstraint):
                    resource["constraints"].append(_constraint("unique", constraint.name, fields))
                elif isinstance(constraint, sa.CheckConstraint):
                    resource["constraints"].append(
                        _constraint(
                            "check", constraint.name, fields, description=str(constraint.sqltext)
                        )
                    )
            for index in table.indexes:
                fields = [column.name for column in index.columns]
                resource["constraints"].append(
                    _constraint(
                        "index",
                        index.name,
                        fields,
                        description="Unique index." if index.unique else "Index.",
                    )
                )
            catalog["resources"].append(resource)
    catalog["limitations"].append(
        "Declared SQLAlchemy metadata; this does not prove that migrations were applied."
    )
    catalog["limitations"].append(
        "Unspecified autoincrement and server-fetched defaults depend on the dialect and are not asserted as absent defaults."
    )
    return _finish(catalog)


def _schema_fields(schema, prefix="", parent_required=True):
    """Flatten validator field paths without sampling any MongoDB documents."""
    fields = []
    required = schema.get("required", [])
    for name, definition in schema.get("properties", {}).items():
        if not isinstance(definition, dict):
            continue
        native = definition.get("bsonType", definition.get("type"))
        types = native if isinstance(native, list) else [native] if native else []
        field_name = prefix + name
        fields.append(
            {
                "name": field_name,
                "native_type": "|".join(types) if types else "unknown",
                "nullable": "null" in types if types else None,
                "required": parent_required and name in required,
            }
        )
        fields.extend(
            _schema_fields(definition, field_name + ".", parent_required and name in required)
        )
        items = definition.get("items")
        if isinstance(items, dict):
            fields.extend(_schema_fields(items, field_name + "[].", False))
    return fields


def _mongodb(store, url, root):
    pymongo = _dependency("pymongo")
    catalog = _catalog(store, coverage="partial")
    with pymongo.MongoClient(
        url, serverSelectionTimeoutMS=5000, connectTimeoutMS=5000, socketTimeoutMS=5000
    ) as client:
        database = (
            client[store["namespace"]] if store.get("namespace") else client.get_default_database()
        )
        for item in database.list_collections():
            if item.get("type") != "collection":
                catalog["limitations"].append(
                    "MongoDB views are not collection schemas and are omitted."
                )
                continue
            name = item["name"]
            resource = _resource("collection", name)
            options = item.get("options", {})
            validator = options.get("validator", {})
            schema = validator.get("$jsonSchema", {})
            resource["fields"] = _schema_fields(schema)
            if validator:
                resource["constraints"].append(
                    _constraint(
                        "validation",
                        "validator",
                        [field["name"] for field in resource["fields"]],
                        description=json.dumps(
                            {
                                "validator": validator,
                                "validationLevel": options.get("validationLevel", "strict"),
                                "validationAction": options.get("validationAction", "error"),
                            },
                            sort_keys=True,
                            default=str,
                        ),
                    )
                )
            for index in database[name].list_indexes():
                indexed_paths = list(index.get("weights") or index["key"])
                fields = [path for path in indexed_paths if "$**" not in path]
                if fields != indexed_paths:
                    catalog["limitations"].append(
                        "Wildcard indexes describe open field paths; their exact key specifications are retained in index metadata."
                    )
                known = {field["name"] for field in resource["fields"]}
                for field_name in fields:
                    if field_name not in known:
                        resource["fields"].append(
                            {
                                "name": field_name,
                                "native_type": "unknown",
                                "nullable": None,
                                "required": field_name == "_id",
                            }
                        )
                details = {
                    key: index[key]
                    for key in (
                        "key",
                        "weights",
                        "wildcardProjection",
                        "sparse",
                        "partialFilterExpression",
                        "collation",
                    )
                    if key in index
                }
                resource["constraints"].append(
                    _constraint(
                        "unique" if index.get("unique") or index["name"] == "_id_" else "index",
                        index["name"],
                        fields,
                        description=json.dumps(details, sort_keys=True, default=str),
                    )
                )
                if "expireAfterSeconds" in index:
                    resource["constraints"].append(
                        _constraint(
                            "ttl",
                            index["name"],
                            fields,
                            description=f"expireAfterSeconds={index['expireAfterSeconds']}",
                        )
                    )
            catalog["resources"].append(resource)
    catalog["limitations"].append(
        "Fields come from collection validators and index declarations, not document samples. Unvalidated fields, existing documents and validation bypasses are not inspected; index properties need not be required fields."
    )
    return catalog


def _redis(store, url, root):
    redis = _dependency("redis")
    limit = store.get("sample_limit", 0)
    scan_limit = store.get("scan_limit", 10)
    if (
        type(limit) is not int
        or not 0 <= limit <= 100
        or type(scan_limit) is not int
        or not 1 <= scan_limit <= 100
    ):
        raise CatalogError(
            "Redis sampling limits must be integers: sample_limit 0..100, scan_limit 1..100."
        )
    catalog = _catalog(store, coverage="sampled" if limit else "partial")
    client = redis.Redis.from_url(url, socket_timeout=5, socket_connect_timeout=5)
    try:
        client.ping()
        for pattern in store.get("key_patterns", []):
            resource = _resource("key_pattern", pattern)
            observed = set()
            consumed = 0
            cursor = 0
            if limit:
                for _ in range(scan_limit):
                    cursor, keys = client.scan(cursor=cursor, match=pattern, count=min(limit, 100))
                    for key in keys[: limit - consumed]:
                        native = client.type(key)
                        if isinstance(native, bytes):
                            native = native.decode("ascii", errors="replace")
                        if native != "none":
                            observed.add(native)
                        consumed += 1
                    if not cursor or consumed >= limit:
                        break
            resource["fields"] = [
                {
                    "name": "value",
                    "native_type": "|".join(sorted(observed)) or "unknown",
                    "nullable": None,
                }
            ]
            catalog["resources"].append(resource)
    finally:
        client.close()
    catalog["limitations"].append(
        "Only explicitly configured key patterns are represented. Values, raw keys, TTL values and record contents are not collected."
    )
    catalog["limitations"].append(
        f"Type sampling is {'enabled' if limit else 'disabled'}; at most {limit} TYPE calls and {scan_limit if limit else 0} SCAN calls per pattern. SCAN COUNT is a hint, not a server-side bound; samples cannot prove all key types."
    )
    return catalog


def _neo4j(store, url, root):
    neo4j = _dependency("neo4j")
    parts = urlsplit(url)
    auth = None
    if parts.username is not None:
        auth = (unquote(parts.username), unquote(parts.password or ""))
        # The driver accepts credentials separately, never in the connection URI.
        url = urlunsplit(
            (parts.scheme, parts.netloc.rsplit("@", 1)[1], parts.path, parts.query, parts.fragment)
        )
    catalog = _catalog(store, coverage="partial")
    resources = {}

    def resource(kind, name):
        key = f"{kind}:{name}"
        return resources.setdefault(key, _resource(kind, name))

    with neo4j.GraphDatabase.driver(url, auth=auth, connection_timeout=5) as driver:
        with driver.session(
            database=store.get("namespace") or None, default_access_mode=neo4j.READ_ACCESS
        ) as session:
            for kind, query, name_key in (
                ("label", "CALL db.labels() YIELD label RETURN label", "label"),
                (
                    "relationship",
                    "CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType",
                    "relationshipType",
                ),
            ):
                for record in session.run(neo4j.Query(query, timeout=5)):
                    resource(kind, record[name_key])
            for query, is_index in (("SHOW CONSTRAINTS", False), ("SHOW INDEXES", True)):
                for record in session.run(neo4j.Query(query, timeout=5)):
                    item = dict(record)
                    kind = "relationship" if item.get("entityType") == "RELATIONSHIP" else "label"
                    names = item.get("labelsOrTypes") or []
                    fields = item.get("properties") or []
                    constraint_type = item.get("type", "")
                    constraint_kind = (
                        "index"
                        if is_index
                        else (
                            "unique"
                            if "UNIQUE" in constraint_type or constraint_type.endswith("KEY")
                            else "type" if "TYPE" in constraint_type else "property"
                        )
                    )
                    for name in names:
                        target = resource(kind, name)
                        target["constraints"].append(
                            _constraint(
                                constraint_kind,
                                item.get("name"),
                                fields,
                                description=constraint_type,
                            )
                        )
                        for field in fields:
                            value = next(
                                (value for value in target["fields"] if value["name"] == field),
                                None,
                            )
                            if value is None:
                                value = {"name": field, "native_type": "unknown", "nullable": None}
                                target["fields"].append(value)
                            if not is_index and (
                                "EXISTENCE" in constraint_type or constraint_type.endswith("KEY")
                            ):
                                value["nullable"] = False
                                value["required"] = True
                            if item.get("propertyType"):
                                value["native_type"] = str(item["propertyType"])
    catalog["resources"] = list(resources.values())
    catalog["limitations"].append(
        "Labels, relationship types, indexes and constraints are metadata. Undeclared properties and actual start/end label combinations are not scanned; no connections are inferred from schema visualization statistics."
    )
    return catalog
