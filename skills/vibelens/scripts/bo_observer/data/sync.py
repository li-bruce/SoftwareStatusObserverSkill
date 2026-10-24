"""Refresh data metadata during coding and verify the generated projection independently."""

from copy import deepcopy
from pathlib import Path
import subprocess
import sys

from .contract import (
    CONFIG_PATH,
    CATALOG_PATH,
    load_config,
    validate_catalog,
    source_identity,
    write_if_changed,
)
from .projection import project_model, structure_differences
from ..graph.behavior_model import contained, digest, read
from ..observation.observation_scope import bo_internal
from .catalog import CatalogError


def _declarations(root, config, *, export):
    """Run a configured native model exporter as an argv command, returning JSON on stdout."""
    exported = {}
    stores = {s["id"]: s for s in config["stores"]}
    if export:
        for item in config.get("exporters", []):
            command = [sys.executable if arg == "{python}" else arg for arg in item["command"]]
            completed = subprocess.run(
                command, cwd=root, capture_output=True, timeout=60, shell=False
            )
            if completed.returncode:
                raise ValueError(
                    "model exporter failed for "
                    + item["store"]
                    + " (exit "
                    + str(completed.returncode)
                    + ")"
                )
            import json

            try:
                value = json.loads(completed.stdout.decode("utf-8-sig"))
                exported[item["store"]] = validate_catalog(value, stores[item["store"]])
            except (ValueError, TypeError, KeyError) as exc:
                raise ValueError(
                    "model exporter returned an invalid catalog for " + item["store"]
                ) from exc
    declarations = []
    for store in config["stores"]:
        if store.get("declaration"):
            value = exported.get(store["id"])
            if value is None:
                value = validate_catalog(read(contained(root, store["declaration"])), store)
            if value["origin"] != "declaration":
                raise ValueError("model exporter must identify declaration provenance")
            declarations.append(value)
    return declarations


def synchronize(root, *, model_path="bo_stategraph/project.json", update=True, force=False):
    """Serialize independent watch/scan/check processes over the project catalog bundle."""
    from ..web.view_preferences import file_lock

    root = Path(root).absolute().resolve()
    try:
        with file_lock(root / ".stategraph/database.lock"):
            return _synchronize(root, model_path=model_path, update=update, force=force)
    except (OSError, ValueError) as exc:
        return {"configured": True, "valid": False, "changed": False, "errors": [str(exc)]}


def _synchronize(root, *, model_path, update, force):
    """Refresh generated facts without accepting a coding batch or changing any business data.

    A failed read leaves the last good files intact. Check mode recomputes current
    catalogs and projection but never repairs them, so stale data cannot pass.
    """
    root = Path(root).absolute().resolve()
    if not contained(root, CONFIG_PATH).exists():
        project_path = contained(root, model_path)
        document = read(project_path) if project_path.exists() else {}
        model = document.get("model", document)
        if (
            "database" in model
            or any(
                "data_role" in node or node.get("managed_by") == "bo-database/v1"
                for node in model.get("nodes", [])
            )
            or any(
                "data_relation" in edge or edge.get("managed_by") == "bo-database/v1"
                for edge in model.get("edges", [])
            )
        ):
            return {
                "configured": False,
                "valid": False,
                "changed": False,
                "errors": [
                    "database configuration removed; remove configuration through a reviewed update"
                ],
            }
        return {"configured": False, "valid": True, "errors": [], "changed": False}
    try:
        from .catalog import collect

        config = load_config(root)
        if any(s.get("declaration") == model_path for s in config["stores"]):
            raise ValueError("database declaration cannot overwrite the project model")
        source_id = source_identity(root, config)
        previous_path = contained(root, CATALOG_PATH)
        previous = read(previous_path) if previous_path.exists() else {}
        # Export after source/config changes, or explicitly on a full independent check.
        with bo_internal():
            declarations = _declarations(
                root, config, export=force or not update or previous.get("source_id") != source_id
            )
            catalogs = [
                validate_catalog(collect(store, root=root), store) for store in config["stores"]
            ]
        if source_identity(root, load_config(root)) != source_id:
            raise ValueError("database model sources changed during collection; retry")
        payload = {"catalogs": catalogs, "declarations": declarations}
        bundle = {
            "protocol": "bo-database-bundle/v1",
            "source_id": source_id,
            "catalog_id": digest(payload),
            **payload,
        }
        document = read(contained(root, model_path))
        base = document["model"] if document.get("protocol") == "bo-project/v1" else document
        model = project_model(base, config, bundle)
        candidate = (
            {**document, "model": model}
            if "model" in document and document.get("protocol") == "bo-project/v1"
            else model
        )
        from ..protocol import validate_project
        from ..graph.behavior_model import validate_graph
        from .protocol import validate_data_projection

        validate_data_projection(model)
        validate_graph(model)
        if candidate.get("protocol") == "bo-project/v1":
            validate_project(candidate)
        declared = {d["store_id"]: d for d in declarations}
        differences = [
            {"store": c["store_id"], **d}
            for c in catalogs
            for d in structure_differences(c, declared.get(c["store_id"]))
        ]
        errors = [{"schema_difference": item} for item in differences]
        changed = document != candidate or previous != bundle
        if not update and changed:
            errors.append("database catalog or graph projection is stale; run bo_db sync")
        if update:
            for store in config["stores"]:
                if store["id"] in declared:
                    write_if_changed(contained(root, store["declaration"]), declared[store["id"]])
            write_if_changed(previous_path, bundle)
            write_if_changed(contained(root, model_path), candidate)
        return {
            "configured": True,
            "valid": not errors,
            "errors": errors,
            "changed": changed,
            "source_id": source_id,
            "catalog_id": bundle["catalog_id"],
            "stores": [
                {"id": c["store_id"], "coverage": c["coverage"], "limitations": c["limitations"]}
                for c in catalogs
            ],
        }
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        ImportError,
        CatalogError,
        subprocess.SubprocessError,
    ) as exc:
        # Driver exceptions contain server addresses and may contain credentials;
        # catalog adapters sanitize those before this boundary.
        return {"configured": True, "valid": False, "changed": False, "errors": [str(exc)]}


def runtime_errors(root, payload, model):
    """Validate configured runtime obligations using the shared data evidence contract."""
    from .evidence import validate_runtime

    if not contained(root, CONFIG_PATH).exists():
        return []
    return validate_runtime(load_config(root), payload, model)
