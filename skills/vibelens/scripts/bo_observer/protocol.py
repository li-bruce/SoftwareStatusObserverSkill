"""The common JSON boundary. Structural validation and semantic checks are distinct."""

from __future__ import annotations
from copy import deepcopy
import json
from pathlib import Path

SCHEMAS = Path(__file__).parent / "schemas"


def _shared():
    try:
        from ..bo_contracts import validate_chart
        from ..behavior_model import validate_events
        from ..observation_scope import observer_nodes
    except ImportError:
        from bo_contracts import validate_chart
        from behavior_model import validate_events
        from observation_scope import observer_nodes
    return validate_chart, validate_events, observer_nodes


def schema_check(value, name):
    """Validate a protocol envelope and its JSON number range before processing it."""
    try:
        from jsonschema import Draft202012Validator
    except ImportError as exc:
        raise ValueError(
            "Install the Skill requirements.txt before using the JSON service"
        ) from exc
    path = SCHEMAS / (name + ".schema.json")
    if not path.is_file():
        # Copied project runtime carries the protocol beside its Python package.
        path = Path(__file__).parent / "schemas" / (name + ".schema.json")
    schema = json.loads(path.read_text(encoding="utf-8"))
    errors = sorted(
        Draft202012Validator(schema).iter_errors(value), key=lambda e: str(list(e.path))
    )
    if errors:
        raise ValueError("; ".join(f"{list(e.path)}: {e.message}" for e in errors[:12]))

    # Python accepts non-finite JSON numbers and integers wider than JS can retain.
    def portable(v):
        if type(v) is int and abs(v) > 9007199254740991:
            raise ValueError("integer exceeds JSON safe range; encode as a typed string")
        if isinstance(v, dict):
            for x in v.values():
                portable(x)
        elif isinstance(v, list):
            for x in v:
                portable(x)

    portable(value)
    json.dumps(value, allow_nan=False)


def validate_project(project):
    """Check project identity, mode choice, and machine declaration; return a detached copy."""
    schema_check(project, "project")
    validate_chart, _, _ = _shared()
    validate_chart(project["model"])
    from .data.protocol import validate_data_projection

    validate_data_projection(project["model"])
    if project["model"].get("project_id", project["project_id"]) != project["project_id"]:
        raise ValueError("project identity differs from graph")
    if (
        project["selection"]["mode"] == "drive"
        and project["model"]["machine"]["engine"] == "python.explicit"
    ):
        raise ValueError(
            "drive mode requires an executable adapter, not an observation-only declaration"
        )
    return deepcopy(project)


def validate_event(event, project, build_id):
    """Check build identity and allowlisted capture fields; return the validated event copy."""
    schema_check(event, "event")
    if (event["project_id"], event["model_revision"], event["build_id"]) != (
        project["project_id"],
        project["model"]["revision"],
        build_id,
    ):
        raise ValueError("event belongs to a different project, model revision or build")
    _, _, internal_nodes = _shared()
    if event["node"] in internal_nodes(project["model"]):
        raise ValueError("observer infrastructure is not a business event")
    node = next((n for n in project["model"]["nodes"] if n["id"] == event["node"]), None)
    if node is None:
        raise ValueError("unknown event node")
    if node.get("data_role") in {"query", "transform"} and "target_source" in event["outputs"]:
        from .data.protocol import TARGET_SOURCES

        provenance = event["outputs"]["target_source"]
        if not isinstance(provenance, str) or provenance not in TARGET_SOURCES:
            raise ValueError("invalid database target_source provenance")
    if node.get("data_role") in {"query", "transform"}:
        from .data.protocol import validate_target_access

        validate_target_access(event["outputs"])
    try:
        from ..semantic_probe import selected
    except ImportError:
        from semantic_probe import selected
    for key, direction in [("inputs", "in"), ("outputs", "out")]:
        fields = node.get("capture", {}).get(direction, {})
        if set(event[key]) - set(fields):
            raise ValueError("undeclared capture fields")
        if selected(event[key], fields) != event[key]:
            raise ValueError("capture does not match declaration")
    return deepcopy(event)


def validate_snapshot(value, project, build_id):
    """Validate snapshot identity and declared context fields.

    State mismatches remain runtime evidence for BOStateGraph to report.
    """
    schema_check(value, "snapshot")
    if (value["project_id"], value["model_revision"], value["build_id"]) != (
        project["project_id"],
        project["model"]["revision"],
        build_id,
    ):
        raise ValueError("snapshot belongs to a different project, revision or build")
    if set(value["context"]) - set(project["model"]["machine"]["context"]):
        raise ValueError("snapshot has undeclared context fields")
    # Actual invalid states remain facts. BOStateGraph diagnoses, never corrects them.
    return deepcopy(value)
