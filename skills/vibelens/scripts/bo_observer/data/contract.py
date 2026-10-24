"""Strict, portable database declarations and catalog validation.

Application choices live in databases.json. Catalogs describe metadata, never rows.
Both native adapters and the Python synchronizer use this boundary.
"""

from copy import deepcopy
from pathlib import Path
import json
import os
import tempfile
from urllib.parse import urlsplit, parse_qsl

from ..protocol import schema_check
from ..graph.behavior_model import contained, digest, read

CONFIG_PATH = "bo_stategraph/databases.json"
CATALOG_PATH = "bo_stategraph/database-catalog.json"
MANAGED = "bo-database/v1"


def validate_catalog(value, store=None):
    """Reject duplicate identities and broken declared references before projection."""
    schema_check(value, "database-catalog")
    if store and (value["store_id"], value["engine"]) != (store["id"], store["engine"]):
        raise ValueError("database catalog identity differs from its configured store")
    if value.get("validation_scope") == "application" and value["origin"] != "declaration":
        raise ValueError("application validation scope requires declaration provenance")
    resources = {r["key"]: r for r in value["resources"]}
    if len(resources) != len(value["resources"]):
        raise ValueError("duplicate database resource key")
    for resource in resources.values():
        fields = [f["name"] for f in resource["fields"]]
        if len(fields) != len(set(fields)):
            raise ValueError("duplicate database field name")
        for constraint in resource["constraints"]:
            local_fields = constraint["fields"]
            if not set(local_fields) <= set(fields):
                raise ValueError("database constraint refers to an absent local field")
            if constraint["kind"] in {"primary_key", "unique", "foreign_key"} and not local_fields:
                raise ValueError("database key constraint needs at least one field")
            if constraint["kind"] == "foreign_key":
                if not constraint.get("target"):
                    raise ValueError("foreign key needs an explicit target")
                target_fields = constraint.get("target_fields", [])
                if len(local_fields) != len(target_fields):
                    raise ValueError("foreign key field counts differ")
                target = resources.get(constraint["target"])
                if target and not set(target_fields) <= {
                    field["name"] for field in target["fields"]
                }:
                    raise ValueError("foreign key refers to an absent target field")
    return deepcopy(value)


def load_config(root, path=CONFIG_PATH):
    """Read local choices, model sources, and the operations that need runtime evidence."""
    config = read(contained(root, path))
    schema_check(config, "database-config")
    stores = {s["id"]: s for s in config["stores"]}
    operations = {o["id"]: o for o in config["operations"]}
    if len(stores) != len(config["stores"]) or len(operations) != len(config["operations"]):
        raise ValueError("duplicate database store or operation identity")
    for store in stores.values():
        for name in store["source_files"]:
            if not contained(root, name).is_file():
                raise ValueError("missing database model source: " + name)
        if store.get("declaration"):
            contained(root, store["declaration"])
    for operation in operations.values():
        from .protocol import operation_target_actions

        operation_target_actions(operation)
        if operation["store"] not in stores:
            raise ValueError("database operation refers to an unknown store")
        if not contained(root, operation["source"]["path"]).is_file():
            raise ValueError("missing database operation source")
        if not set(operation.get("failure_cases", [])) <= set(operation["required_cases"]):
            raise ValueError("failure cases must also be required runtime cases")
    exported = set()
    destinations = set()
    protected = {path, CATALOG_PATH, "bo_stategraph/project.json", "sync.json", "source-scope.json"}
    protected.update(p for s in stores.values() for p in s["source_files"])
    protected.update(o["source"]["path"] for o in operations.values())
    protected_paths = {contained(root, name).resolve() for name in protected}
    for exporter in config.get("exporters", []):
        if exporter["store"] not in stores or exporter["store"] in exported:
            raise ValueError("unknown or duplicate database exporter")
        if stores[exporter["store"]].get("declaration") != exporter["output"]:
            raise ValueError("export output must equal the store declaration path")
        contained(root, exporter["output"])
        destination = contained(root, exporter["output"]).resolve()
        if destination in protected_paths:
            raise ValueError("database exporter cannot overwrite configuration or source")
        if destination in destinations:
            raise ValueError("database exporters cannot share an output file")
        destinations.add(destination)
        exported.add(exporter["store"])
    return config


def source_identity(root, config):
    """Bind model exports to all configured source bytes and exporter settings."""
    names = {p for s in config["stores"] for p in s["source_files"]}
    names.update(o["source"]["path"] for o in config["operations"])
    for exporter in config.get("exporters", []):
        for argument in exporter["command"]:
            candidate = Path(root) / argument
            if candidate.is_file() and candidate.resolve().is_relative_to(Path(root).resolve()):
                names.add(candidate.resolve().relative_to(Path(root).resolve()).as_posix())
    files = {p: digest(contained(root, p).read_bytes()) for p in sorted(names)}
    connections = {}
    for store in config["stores"]:
        address = urlsplit(os.environ.get(store["url_env"], ""))
        # Keep connection credentials and options out of persisted identity input.
        # An environment switch still invalidates recordings even for equal schemas.
        routing = {
            key.lower(): value
            for key, value in parse_qsl(address.query)
            if key.lower()
            in {
                "host",
                "port",
                "db",
                "dbname",
                "database",
                "schema",
                "currentschema",
                "search_path",
                "options",
                "replicaset",
                "service",
            }
        }
        connections[store["id"]] = digest(
            {
                "scheme": address.scheme,
                "host": address.netloc.rsplit("@", 1)[-1].lower(),
                "database": address.path,
                "namespace": store.get("namespace"),
                "routing": routing,
            }
        )
    return digest({"config": config, "files": files, "connections": connections})


def capture_spec(operation):
    """Use the existing selected-value capture contract for data-operation events."""
    return {
        "in": {"operation": "string", "statement": "string", "parameters": operation["parameters"]},
        "out": {
            "status": "string",
            "duration_ms": "number",
            "rows": "number",
            "rows_known": "boolean",
            "result": operation["after"],
            "before": operation["before"],
            "error_type": "string",
            "transaction_id": "string",
            "targets": ["string"],
            "unknown_targets": ["string"],
            "input_count": "number",
            "output_count": "number",
            "committed": "boolean",
            "target_source": "string",
            "target_access": [{"target": "string", "action": "string"}],
        },
    }


def write_if_changed(path, value):
    """Publish complete JSON atomically and avoid touching unchanged generated files."""
    raw = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    path = Path(path)
    if path.exists() and path.read_text(encoding="utf-8") == raw:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="\n",
        dir=path.parent,
        prefix=path.name + ".",
        suffix=".tmp",
        delete=False,
    ) as stream:
        stream.write(raw)
        staging = Path(stream.name)
    try:
        staging.replace(path)
    finally:
        staging.unlink(missing_ok=True)
    return True
