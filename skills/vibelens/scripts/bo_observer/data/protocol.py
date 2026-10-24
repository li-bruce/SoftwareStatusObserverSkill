"""Validate data graph extensions without loading a database driver or contacting a server.

Metadata may be partial or unverified. Its structure, provenance and references
must still be explicit, including when a producer omits the generated marker.
"""

from pathlib import PurePosixPath, PureWindowsPath
from urllib.parse import quote

MANAGED = "bo-database/v1"
ROLES = {"store", "dataset", "column", "query", "transform"}
ORIGINS = {"database", "declaration"}
COVERAGE = {"complete", "partial", "sampled"}
RESOURCE_KINDS = {"table", "collection", "key_pattern", "label", "relationship"}
STATUSES = {
    "matched",
    "database_only",
    "declared_only",
    "application_declared",
    "different",
    "unverified",
}
TARGET_SOURCES = {
    "parsed_sql",
    "driver",
    "provided",
    "parsed_and_provided",
    "unresolved",
    "not_applicable",
}


def _require(condition, message):
    if not condition:
        raise ValueError("invalid database projection: " + message)


def _text(value, label, *, empty=False):
    _require(isinstance(value, str) and (empty or bool(value.strip())), label + " needs a string")
    return value


def _enum(value, allowed, label):
    _require(isinstance(value, str) and value in allowed, label + " has an unsupported value")


def _object(value, required, optional, label):
    _require(isinstance(value, dict), label + " needs an object")
    _require(set(required) <= value.keys(), label + " is missing required fields")
    _require(value.keys() <= set(required) | set(optional), label + " has undeclared fields")


def _strings(value, label):
    _require(isinstance(value, list), label + " needs an array")
    for item in value:
        _text(item, label)
    _require(len(value) == len(set(value)), label + " has duplicate values")
    return value


def _path(value, label):
    _text(value, label)
    posix, windows = PurePosixPath(value), PureWindowsPath(value)
    _require(
        not posix.is_absolute()
        and not windows.drive
        and not windows.root
        and ".." not in posix.parts
        and ".." not in windows.parts
        and str(posix) != ".",
        label + " must stay inside the project",
    )


def _field(value):
    _object(
        value,
        {"name", "native_type", "nullable"},
        {"primary_key", "required", "generated", "default"},
        "field metadata",
    )
    for key in ("name", "native_type"):
        _text(value[key], "field " + key)
    _require(
        value["nullable"] is None or type(value["nullable"]) is bool,
        "nullable needs boolean or null",
    )
    for key in ("primary_key", "required", "generated"):
        if key in value:
            _require(type(value[key]) is bool, key + " needs boolean")
    if "default" in value:
        _require(
            value["default"] is None or isinstance(value["default"], str),
            "default needs string or null",
        )


def _constraint(value, *, provenance=False):
    required = {"kind", "name", "fields"} | ({"origin"} if provenance else set())
    _object(value, required, {"target", "target_fields", "description"}, "constraint")
    _enum(
        value["kind"],
        {
            "primary_key",
            "foreign_key",
            "unique",
            "index",
            "check",
            "validation",
            "property",
            "type",
            "ttl",
            "connects",
        },
        "constraint kind",
    )
    _text(value["name"], "constraint name", empty=True)
    _strings(value["fields"], "constraint fields")
    if provenance:
        _enum(value["origin"], ORIGINS, "constraint origin")
    if "target" in value:
        _text(value["target"], "constraint target")
    if "target_fields" in value:
        _strings(value["target_fields"], "constraint target fields")
    if "description" in value:
        _text(value["description"], "constraint description", empty=True)
    if value["kind"] in {"primary_key", "foreign_key", "unique"}:
        _require(bool(value["fields"]), "key constraint needs fields")
    if value["kind"] == "foreign_key":
        _require(bool(value.get("target")), "foreign key needs a target")
        _require(
            len(value["fields"]) == len(value.get("target_fields", [])),
            "foreign key field counts differ",
        )


def _capture(value, depth=0):
    _require(depth <= 6, "capture nesting exceeds six levels")
    if isinstance(value, dict):
        for key, spec in value.items():
            _text(key, "capture field")
            _capture(spec, depth + 1)
    elif isinstance(value, list):
        _require(len(value) == 1, "capture array needs one item declaration")
        _capture(value[0], depth + 1)
    else:
        _enum(value, {"string", "number", "boolean", "scalar"}, "capture type")


def operation_target_actions(operation):
    """Resolve declared access roles without treating every source as a write target."""
    action, targets = operation["action"], operation["targets"]
    specified = operation.get("target_actions")
    if action not in {"read", "write"}:
        _require(specified is None, "target actions apply only to read/write operations")
        return {}
    _require(
        action != "write" or len(targets) <= 1 or specified is not None,
        "multi-target writes require explicit target_actions",
    )
    if specified is None:
        return {target: action for target in targets}
    _require(
        isinstance(specified, dict) and set(specified) == set(targets),
        "target_actions must cover exactly the declared targets",
    )
    for value in specified.values():
        _enum(value, {"read", "write", "read_write"}, "target action")
    _require(
        action != "read" or all(value == "read" for value in specified.values()),
        "read operation cannot declare a write target",
    )
    _require(
        action != "write" or any(value in {"write", "read_write"} for value in specified.values()),
        "write operation needs a write target",
    )
    return specified


def validate_target_access(outputs):
    """Keep per-table runtime roles typed and bound to the event's observed targets."""
    if "target_access" not in outputs:
        return
    access = outputs["target_access"]
    _require(isinstance(access, list), "target_access needs an array")
    targets = _strings(outputs.get("targets", []), "observed targets")
    seen = set()
    for item in access:
        _object(item, {"target", "action"}, set(), "observed target access")
        _text(item["target"], "observed target")
        _enum(item["action"], {"read", "write"}, "observed target action")
        _require(item["target"] in targets, "observed access target is absent from targets")
        identity = (item["target"], item["action"])
        _require(identity not in seen, "duplicate observed target access")
        seen.add(identity)


def _operation(node, model):
    metadata = node["data_metadata"]
    _object(metadata, {"action", "targets"}, {"target_actions"}, "operation metadata")
    _enum(metadata["action"], {"read", "write", "transaction", "transform"}, "operation action")
    _require(
        (node["data_role"] == "transform") == (metadata["action"] == "transform"),
        "operation role and action differ",
    )
    _strings(metadata["targets"], "operation targets")
    operation_target_actions(metadata)
    source = node.get("source")
    _object(source, {"path", "symbol"}, set(), "operation source")
    _path(source["path"], "operation source path")
    _text(source["symbol"], "operation source symbol")
    _require(source["path"] in model["source_files"], "operation source is not in source_files")
    _text(node.get("parent"), "operation parent")
    capture = node.get("capture")
    _object(capture, {"in", "out"}, set(), "operation capture")
    _capture(capture["in"])
    _capture(capture["out"])
    _object(
        capture["in"], {"operation", "statement", "parameters"}, set(), "operation input capture"
    )
    expected_out = {
        "status": "string",
        "duration_ms": "number",
        "rows": "number",
        "rows_known": "boolean",
        "error_type": "string",
        "transaction_id": "string",
        "targets": ["string"],
        "unknown_targets": ["string"],
        "input_count": "number",
        "output_count": "number",
        "committed": "boolean",
        "target_source": "string",
        "target_access": [{"target": "string", "action": "string"}],
    }
    _object(
        capture["out"], set(expected_out) | {"result", "before"}, set(), "operation output capture"
    )
    _require(
        capture["in"]["operation"] == "string" and capture["in"]["statement"] == "string",
        "operation and statement capture must be strings",
    )
    _require(
        all(capture["out"][key] == spec for key, spec in expected_out.items()),
        "operation outcome capture differs from the common contract",
    )
    _require(
        all(
            isinstance(spec, dict)
            for spec in (
                capture["in"]["parameters"],
                capture["out"]["result"],
                capture["out"]["before"],
            )
        ),
        "selected values need field maps",
    )


def _node(node, model, stores):
    role = node.get("data_role")
    _enum(role, ROLES, "node data_role")
    _require(
        node.get("kind") == ("function" if role in {"query", "transform"} else "data"),
        "node kind does not match data_role",
    )
    for key in ("id", "label", "summary", "data_store"):
        _text(node.get(key), key)
    _require(node["data_store"] in stores, "node refers to an unregistered store")
    _enum(node.get("data_origin"), ORIGINS, "node origin")
    _enum(node.get("data_coverage"), COVERAGE, "node coverage")
    metadata = node.get("data_metadata")
    _require(isinstance(metadata, dict), "data_metadata needs an object")
    if role in {"query", "transform"}:
        _operation(node, model)
        return
    _text(node.get("data_key"), "resource key")
    if role == "store":
        _require(node["data_key"] == "store", "store key must be store")
        _object(metadata, {"engine", "limitations", "model_layer"}, set(), "store metadata")
        _enum(metadata["engine"], {"sqlalchemy", "mongodb", "redis", "neo4j"}, "store engine")
        _strings(metadata["limitations"], "store limitations")
        _text(metadata["model_layer"], "store model_layer")
    elif role == "dataset":
        _enum(metadata.get("status"), STATUSES | {"outside_scope"}, "dataset status")
        if metadata["status"] == "outside_scope":
            _object(metadata, {"status"}, set(), "outside-scope resource")
            _require(node["data_coverage"] == "partial", "outside-scope resource must be partial")
        else:
            _object(
                metadata,
                {"kind", "status", "constraints", "declared_constraints"},
                set(),
                "dataset metadata",
            )
            _enum(metadata["kind"], RESOURCE_KINDS, "dataset kind")
            _require(
                node["data_key"].startswith(metadata["kind"] + ":")
                and len(node["data_key"]) > len(metadata["kind"]) + 1,
                "dataset key does not match its kind",
            )
            for key in ("constraints", "declared_constraints"):
                _require(isinstance(metadata[key], list), "constraints need an array")
                for constraint in metadata[key]:
                    _constraint(constraint)
    else:
        _require(
            "status" in metadata and "declared" in metadata,
            "column metadata needs status and declaration",
        )
        _enum(metadata["status"], STATUSES, "column status")
        _field({key: value for key, value in metadata.items() if key not in {"status", "declared"}})
        if metadata["declared"] is not None:
            _field(metadata["declared"])
            _require(
                metadata["declared"]["name"] == metadata["name"],
                "column declaration identity differs",
            )


def validate_data_projection(model):
    """Reject malformed data extensions while leaving ordinary project graphs unchanged."""
    nodes = {node["id"]: node for node in model.get("nodes", [])}
    edges = model.get("edges", [])
    data_nodes = [n for n in nodes.values() if "data_role" in n or n.get("managed_by") == MANAGED]
    data_edges = [e for e in edges if "data_relation" in e or e.get("managed_by") == MANAGED]
    if not data_nodes and not data_edges and "database" not in model:
        return
    registry = model.get("database")
    _object(
        registry,
        {"protocol", "source_id", "catalog_id", "stores", "managed_source_files"},
        set(),
        "database registry",
    )
    _require(registry["protocol"] == MANAGED, "unsupported database registry protocol")
    for key in ("source_id", "catalog_id"):
        _text(registry[key], key)
    stores = _strings(registry["stores"], "registered stores")
    for path in _strings(registry["managed_source_files"], "managed source files"):
        _path(path, "managed source file")
        _require(
            path in model.get("source_files", []), "managed source file is absent from source_files"
        )
    for node in data_nodes:
        _node(node, model, stores)
    store_nodes = [n for n in data_nodes if n["data_role"] == "store"]
    _require(
        len(store_nodes) == len(stores) and {n["data_store"] for n in store_nodes} == set(stores),
        "each registered store needs exactly one store node",
    )
    datasets = {
        (n["data_store"], n["data_key"]): n for n in data_nodes if n["data_role"] == "dataset"
    }
    _require(
        len(datasets) == sum(n["data_role"] == "dataset" for n in data_nodes),
        "duplicate dataset identity",
    )
    for node in data_nodes:
        role, store = node["data_role"], node["data_store"]
        parent = nodes.get(node.get("parent"))
        if "parent" in node:
            _require(parent is not None, "missing data parent")
        if role in {"dataset", "column"}:
            _require(
                parent is not None
                and parent.get("data_role") == ("store" if role == "dataset" else "dataset")
                and parent.get("data_store") == store,
                "resource hierarchy or store differs",
            )
        if role == "column":
            _require(
                node["data_key"] == parent["data_key"] + "." + node["data_metadata"]["name"],
                "column key differs from its parent",
            )
        if node.get("managed_by") == MANAGED and role not in {"query", "transform"}:
            key = parent["data_key"] if role == "column" else node["data_key"]
            expected = "db:" + quote(store, safe="") + ":" + quote(key, safe="")
            if role == "column":
                expected += ":field:" + quote(node["data_metadata"]["name"], safe="")
            _require(
                node["id"] == expected, "managed resource identity differs from its native key"
            )
        if role in {"query", "transform"}:
            for target in node["data_metadata"]["targets"]:
                _require((store, target) in datasets, "operation target is absent from its store")
    for edge in data_edges:
        start, end = nodes.get(edge.get("from")), nodes.get(edge.get("to"))
        _require(start is not None and end is not None, "data edge has an absent endpoint")
        if "data_relation" not in edge:
            _require(
                edge.get("type") == "contains"
                and end.get("data_role") in ROLES
                and end.get("parent") == start["id"],
                "managed edge needs a relation or matching containment",
            )
            continue
        relation = edge["data_relation"]
        _enum(relation, {"reads", "writes", "references", "maps", "transforms"}, "data_relation")
        _require(edge.get("type") == "data", "data_relation needs a data edge")
        source_role, target_role = start.get("data_role"), end.get("data_role")
        if relation == "transforms":
            _require(target_role in {"query", "transform"}, "transforms must end at an operation")
        elif relation in {"reads", "writes"}:
            dataset, operation = (start, end) if relation == "reads" else (end, start)
            _require(
                dataset.get("data_role") == "dataset"
                and operation.get("data_role") == "query"
                and operation_target_actions(operation["data_metadata"]).get(dataset["data_key"])
                in ({"read", "read_write"} if relation == "reads" else {"write", "read_write"}),
                "read/write edge endpoints disagree with the action",
            )
            _require(
                dataset["data_store"] == operation["data_store"]
                and dataset["data_key"] in operation["data_metadata"]["targets"],
                "read/write edge differs from declared targets",
            )
        else:
            expected = "dataset" if relation == "references" else "column"
            _require(
                source_role == target_role == expected and start["data_store"] == end["data_store"],
                "reference endpoints have incompatible roles or stores",
            )
            _enum(edge.get("data_origin"), ORIGINS, "edge origin")
            constraints = edge.get("data_constraints")
            _require(
                isinstance(constraints, list) and bool(constraints),
                "reference edge needs its constraints",
            )
            for constraint in constraints:
                _constraint(constraint, provenance=True)
                destination = end if relation == "references" else nodes[end["parent"]]
                _require(
                    constraint.get("target") == destination["data_key"],
                    "reference constraint target differs from endpoint",
                )
                if relation == "maps":
                    pairs = zip(constraint["fields"], constraint.get("target_fields", []))
                    _require(
                        (start["data_metadata"]["name"], end["data_metadata"]["name"]) in pairs,
                        "field map differs from its constraint",
                    )
