"""Database runtime obligations shared by feature coverage and synchronization.

Capture schemas whitelist values. Presence depends on the actual operation and
outcome; a successful read has no error and a transaction has no row count.
"""

from .contract import capture_spec, MANAGED
from ..observation.semantic_probe import selected


def projected_operations(config, model):
    """Only exact configured projections may use database presence rules."""
    nodes = {node["id"]: node for node in model["nodes"]}
    matched, errors = {}, []
    for operation in config["operations"]:
        node = nodes.get(operation["id"], {})
        if (
            node.get("managed_by") != MANAGED
            or node.get("capture") != capture_spec(operation)
            or node.get("source") != operation["source"]
            or node.get("data_metadata", {}).get("action") != operation["action"]
        ):
            errors.append({"database_capture_contract_mismatch": operation["id"]})
        else:
            matched[operation["id"]] = operation
    return matched, errors


def event_errors(operation, event):
    """Validate all selected values and the fields required by this exact outcome."""
    spec = capture_spec(operation)
    inputs, outputs = event.get("inputs", {}), event.get("outputs", {})
    errors = []
    for direction, value in [("in", inputs), ("out", outputs)]:
        try:
            if not isinstance(value, dict) or selected(value, spec[direction]) != value:
                raise ValueError("undeclared fields")
        except (ValueError, TypeError) as exc:
            errors.append(
                {
                    "invalid_database_values": direction,
                    "operation": operation["id"],
                    "error": str(exc),
                }
            )
    if not isinstance(inputs, dict) or not isinstance(outputs, dict):
        return errors
    required = {
        "status",
        "duration_ms",
        "targets",
        "unknown_targets",
        "target_source",
        "target_access",
    }
    phase = event.get("phase")
    if phase == "error":
        required.add("error_type")
    if operation["action"] in {"read", "write"} and phase in {"return", "error"}:
        required.add("rows_known")
    if outputs.get("rows_known") is True:
        required.add("rows")
    if phase == "commit" or outputs.get("status") == "rolled_back":
        required.add("committed")
    for direction, value, fields in [
        ("in", inputs, {"operation", "statement", "parameters"}),
        ("out", outputs, required),
    ]:
        for field in sorted(fields):
            if field not in value or value[field] is None:
                errors.append(
                    {
                        "missing_database_event_field": field,
                        "direction": direction,
                        "operation": operation["id"],
                        "phase": phase,
                    }
                )
    if inputs.get("operation") != operation["action"]:
        errors.append({"database_operation_mismatch": operation["id"]})
    if outputs.get("status") == "rolled_back" and outputs.get("committed") is not False:
        errors.append({"unconfirmed_database_rollback": operation["id"]})
    return errors


def validate_runtime(config, payload, model):
    """Require executed cases for every configured operation, independent of old graph nodes."""
    known = {n["id"]: n for n in model["nodes"]}
    _, errors = projected_operations(config, model)
    runs = payload.get("runs", [])

    def complete(value, spec):
        """Required selected fields must have been observed, including nested fields."""
        if isinstance(spec, dict):
            return isinstance(value, dict) and all(
                k in value and complete(value[k], child) for k, child in spec.items()
            )
        if isinstance(spec, list):
            return isinstance(value, list) and all(complete(item, spec[0]) for item in value)
        return (
            value is None
            or (spec in {"number", "scalar"} and type(value) in {int, float})
            or (spec in {"boolean", "scalar"} and type(value) is bool)
            or (spec in {"string", "scalar"} and isinstance(value, str))
        )

    def resolve_target(key, store):
        candidates = {
            n["data_key"]
            for n in known.values()
            if n.get("data_store") == store and n.get("data_role") == "dataset"
        }
        if key in candidates:
            return key
        if key.startswith("table:") and "." not in key[6:]:
            matches = [
                c for c in candidates if c.startswith("table:") and c.rsplit(".", 1)[-1] == key[6:]
            ]
            if len(matches) == 1:
                return matches[0]
        return key

    for operation in config["operations"]:
        from .protocol import operation_target_actions, validate_target_access

        target_actions = operation_target_actions(operation)
        if operation["id"] not in known:
            errors.append({"missing_database_node": operation["id"]})
        for case in operation["required_cases"]:
            selected = [r for r in runs if r.get("case") == case and r.get("mode") == "on"]
            events = [
                e for r in selected for e in r.get("events", []) if e.get("node") == operation["id"]
            ]
            failure_expected = case in operation.get("failure_cases", [])
            phases = (
                {"error"}
                if failure_expected
                else {"commit"} if operation["action"] == "transaction" else {"return", "change"}
            )
            terminal = [e for e in events if e.get("phase") in phases]
            if len(selected) != 1 or not terminal:
                errors.append({"missing_database_runtime_case": case, "operation": operation["id"]})
            if terminal and not any(
                isinstance(e.get("outputs", {}).get("status"), str) and e["outputs"]["status"]
                for e in terminal
            ):
                errors.append({"missing_database_outcome": operation["id"], "case": case})
            if (
                failure_expected
                and terminal
                and not any(e.get("outputs", {}).get("error_type") for e in terminal)
            ):
                errors.append({"missing_database_error": operation["id"], "case": case})
            if (
                not failure_expected
                and terminal
                and not any(
                    e.get("outputs", {}).get("status")
                    in {
                        "returned",
                        "succeeded",
                        "success",
                        "executed",
                        "transformed",
                        "changed",
                        "committed",
                    }
                    for e in terminal
                )
            ):
                errors.append({"unsuccessful_database_case": operation["id"], "case": case})
            if (
                operation["action"] == "transaction"
                and not failure_expected
                and terminal
                and not any(e.get("outputs", {}).get("committed") is True for e in terminal)
            ):
                errors.append({"unconfirmed_database_commit": operation["id"], "case": case})
            selections = [("inputs", "parameters", operation["parameters"])]
            if not failure_expected:
                selections += [
                    ("outputs", "before", operation["before"]),
                    ("outputs", "result", operation["after"]),
                ]
            for side, key, spec in selections:
                if spec and not any(complete(e.get(side, {}).get(key), spec) for e in events):
                    errors.append(
                        {"missing_database_values": key, "operation": operation["id"], "case": case}
                    )
            for event in events:
                errors.extend(event_errors(operation, event))
                output = event.get("outputs", {})
                try:
                    validate_target_access(output)
                except ValueError as exc:
                    errors.append(
                        {"invalid_database_target_access": operation["id"], "error": str(exc)}
                    )
                    continue
                access = output.get("target_access", [])
                if (
                    output.get("target_source") in {"parsed_sql", "parsed_and_provided"}
                    and operation["action"] in {"read", "write"}
                    and not access
                ):
                    errors.append({"missing_database_target_access": operation["id"], "case": case})
                for observed in access:
                    key = resolve_target(observed["target"], operation["store"])
                    wanted = target_actions.get(key)
                    if wanted != "read_write" and observed["action"] != wanted:
                        errors.append(
                            {
                                "unexpected_database_target_access": observed,
                                "expected": wanted,
                                "operation": operation["id"],
                                "case": case,
                            }
                        )
                if output.get("unknown_targets"):
                    errors.append(
                        {
                            "unresolved_database_targets": output["unknown_targets"],
                            "operation": operation["id"],
                        }
                    )
                if event.get("phase") in {"return", "commit", "change"}:
                    targets = output.get("targets", [])
                    declared = set(operation["targets"])
                    if not isinstance(targets, list) or not all(
                        isinstance(t, str) for t in targets
                    ):
                        errors.append({"invalid_database_targets": operation["id"]})
                    elif (
                        operation["action"] in {"read", "write"}
                        and declared
                        and (
                            not targets
                            or not {resolve_target(t, operation["store"]) for t in targets}
                            <= declared
                        )
                    ):
                        errors.append(
                            {
                                "unexpected_database_targets": targets,
                                "expected": sorted(declared),
                                "operation": operation["id"],
                            }
                        )
    return errors
