"""Check selected source contracts against actual, version-bound probe events.

Expectations are project-owned inputs, never inferred from observed results.
This checks declared evidence and contracts, not arbitrary semantic equivalence.
"""

from __future__ import annotations
import argparse
import json
import math
from pathlib import Path

try:
    from ...behavior_model import read, contained, digest, capture
    from ...code_structure import scan, key
except ImportError:
    from behavior_model import read, contained, digest, capture
    from code_structure import scan, key

TYPES = {"integer", "number", "string", "boolean", "array", "object", "null"}
OPS = {"eq", "ne", "lt", "le", "gt", "ge", "in"}


def get(value, path):
    if not isinstance(path, list) or not path:
        raise ValueError("field path must be a nonempty list")
    for part in path:
        if isinstance(value, list) and type(part) is int:
            value = value[part]
        elif isinstance(value, dict) and isinstance(part, str):
            value = value[part]
        else:
            raise ValueError("field path does not match value")
    return value


def has_type(value, name):
    return {
        "integer": type(value) is int,
        "number": type(value) in (int, float) and math.isfinite(value),
        "string": isinstance(value, str),
        "boolean": type(value) is bool,
        "array": isinstance(value, list),
        "object": isinstance(value, dict),
        "null": value is None,
    }.get(name, False)


def assertion_errors(value, fields):
    errors = []
    for field in fields:
        try:
            actual = get(value, field["path"])
            if "type" in field and not has_type(actual, field["type"]):
                raise ValueError("type mismatch")
            if "equals" in field and digest(actual) != digest(field["equals"]):
                raise ValueError("value mismatch")
            if "min" in field and (not has_type(actual, "number") or actual < field["min"]):
                raise ValueError("below minimum")
            if "max" in field and (not has_type(actual, "number") or actual > field["max"]):
                raise ValueError("above maximum")
            if "compare" in field:
                comparison = field["compare"]
                other = get(value, comparison["path"])
                op = comparison["op"]
                if op in {"lt", "le", "gt", "ge"} and not (
                    has_type(actual, "number") and has_type(other, "number")
                ):
                    raise ValueError("ordered comparison needs finite numbers")
                passed = {
                    "eq": lambda: digest(actual) == digest(other),
                    "ne": lambda: digest(actual) != digest(other),
                    "lt": lambda: actual < other,
                    "le": lambda: actual <= other,
                    "gt": lambda: actual > other,
                    "ge": lambda: actual >= other,
                    "in": lambda: isinstance(other, list)
                    and any(digest(actual) == digest(v) for v in other),
                }[op]()
                if not passed:
                    raise ValueError("field relation mismatch")
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            errors.append({"path": field.get("path"), "error": str(exc)})
    return errors


def schema_errors(contract):
    errors = []
    if contract.get("schema_version") != 1:
        errors.append("expected whitebox schema_version 1")
    rules, checks = contract.get("rules", []), contract.get("checks", [])
    if not rules or len({r.get("id") for r in rules}) != len(rules):
        errors.append("rules need unique IDs")
    ids = {r.get("id") for r in rules}
    for rule in rules:
        for field in ("id", "requirement", "node", "claim", "basis", "category", "source"):
            if not rule.get(field):
                errors.append({"rule": rule.get("id"), "missing": field})
        if not isinstance(rule.get("parameters", {}), dict):
            errors.append("parameters must map names to optional annotations")
        if not all(rule.get("source", {}).get(k) for k in ("path", "symbol")):
            errors.append("rule needs source path and symbol")
    if not checks or len({c.get("id") for c in checks}) != len(checks):
        errors.append("checks need unique IDs")
    for check in checks:
        if check.get("rule") not in ids or not check.get("case") or not check.get("phase"):
            errors.append({"invalid_check": check.get("id")})
        count = check.get("count", {})
        minimum, maximum = count.get("min", 1), count.get("max")
        if (
            type(minimum) is not int
            or minimum < 1
            or (maximum is not None and (type(maximum) is not int or maximum < minimum))
        ):
            errors.append("event count must require at least one observation")
        if not check.get("fields"):
            errors.append("check needs observed field assertions")
        for field in [*check.get("fields", []), *check.get("select", [])]:
            if not isinstance(field.get("path"), list) or not field["path"]:
                errors.append("assertion needs nonempty field path")
            if not any(k in field for k in ("type", "equals", "min", "max", "compare")):
                errors.append("assertion has no condition")
            if "type" in field and field["type"] not in TYPES:
                errors.append("unsupported field type")
            if "compare" in field:
                compare = field["compare"]
                if (
                    compare.get("op") not in OPS
                    or not isinstance(compare.get("path"), list)
                    or not compare["path"]
                ):
                    errors.append("unsupported field comparison")
        if check.get("modes", ["on"]) != ["on"]:
            errors.append(
                "whitebox evidence checks run in on mode; use business checks for off/fault"
            )
    for rid in ids - {c.get("rule") for c in checks}:
        errors.append({"rule_without_case": rid})
    return errors


def static_errors(contract, model, structure, requirements):
    errors = schema_errors(contract)
    nodes = {n["id"]: n for n in model["nodes"]}
    for rule in contract.get("rules", []):
        node = nodes.get(rule.get("node"), {})
        source = rule.get("source", {})
        if rule.get("requirement") not in requirements:
            errors.append({"rule": rule.get("id"), "error": "unknown requirement"})
        if node.get("source") != source:
            errors.append({"rule": rule.get("id"), "error": "node/source binding differs"})
        symbol = structure["symbols"].get(key(source.get("path"), source.get("symbol")))
        if not symbol:
            errors.append(
                {"rule": rule.get("id"), "error": "source symbol missing from selected code"}
            )
            continue
        params = {p["name"]: p["annotation"] for p in symbol["parameters"]}
        for name, annotation in rule.get("parameters", {}).items():
            if name not in params or (annotation is not None and params[name] != annotation):
                errors.append({"rule": rule["id"], "parameter": name, "error": "signature differs"})
        if "returns" in rule and symbol["returns"] != rule["returns"]:
            errors.append({"rule": rule["id"], "error": "return annotation differs"})
    return errors


def assess(contract, model, payload, expected_build):
    errors = schema_errors(contract)
    results = []
    if payload.get("build_id") != expected_build:
        errors.append("runtime payload belongs to another build")
    rules = {r["id"]: r for r in contract.get("rules", [])}
    for check in contract.get("checks", []):
        failures = []
        rule = rules.get(check.get("rule"), {})
        runs = [
            r
            for r in payload.get("runs", [])
            if r.get("case") == check.get("case") and r.get("mode") == "on"
        ]
        matches = []
        if len(runs) != 1:
            failures.append("missing unique case/on run")
        else:
            events = runs[0].get("events", [])
            ids = [e.get("id") for e in events]
            if len(ids) != len(set(ids)):
                failures.append("duplicate event identity")
            matches = [
                e
                for e in events
                if e.get("node") == rule.get("node")
                and e.get("phase") == check.get("phase")
                and not assertion_errors(e, check.get("select", []))
            ]
            count = check.get("count", {})
            if len(matches) < count.get("min", 1) or len(matches) > count.get("max", math.inf):
                failures.append("observed event count differs")
            for event in matches:
                for name in ("id", "run_id", "attempt", "call_id", "entity"):
                    if not isinstance(event.get(name), str) or not event[name]:
                        failures.append("missing event identity: " + name)
                if (
                    event.get("build_id") != expected_build
                    or event.get("model_revision") != model["revision"]
                ):
                    failures.append("stale event build/model")
                identity = tuple(event.get(k) for k in ("run_id", "attempt", "entity"))
                peers = [e for e in events if e.get("call_id") == event.get("call_id")]
                if any(
                    tuple(e.get(k) for k in ("run_id", "attempt", "entity")) != identity
                    for e in peers
                ):
                    failures.append("call identity crosses run/attempt/entity")
                parent_id = event.get("parent_call_id")
                if parent_id:
                    parents = [e for e in events if e.get("call_id") == parent_id]
                    if (
                        parent_id == event.get("call_id")
                        or not parents
                        or any(
                            tuple(e.get(k) for k in ("run_id", "attempt", "entity")) != identity
                            or e.get("build_id") != expected_build
                            or e.get("model_revision") != model["revision"]
                            for e in parents
                        )
                    ):
                        failures.append("parent call is missing or belongs to another execution")
                failures.extend(assertion_errors(event, check.get("fields", [])))
        results.append(
            {
                "check": check.get("id"),
                "rule": check.get("rule"),
                "requirement": rule.get("requirement"),
                "case": check.get("case"),
                "node": rule.get("node"),
                "source": rule.get("source"),
                "events": [e.get("id") for e in matches],
                "status": "failed" if failures else "passed",
                "errors": failures,
            }
        )
    errors.extend({"check": r["check"], "errors": r["errors"]} for r in results if r["errors"])
    return {
        "valid": not errors,
        "errors": errors,
        "checks": results,
        "coverage": {
            "rules": len(rules),
            "checks": len(results),
            "passed": sum(r["status"] == "passed" for r in results),
        },
        "scope": "Declared source bindings and observed values; missing evidence never passes.",
    }


def protected_items(contract):
    """Normalize rules and expectations for the existing requirement-change gate."""
    rules = {r["id"]: r for r in (contract or {}).get("rules", [])}
    items = {"rule:" + k: v for k, v in rules.items()}
    for c in (contract or {}).get("checks", []):
        items["check:" + c["id"]] = {
            **c,
            "requirement": rules.get(c.get("rule"), {}).get("requirement"),
        }
    return items


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=["plan", "check"])
    p.add_argument("--root", required=True)
    p.add_argument("--contract", default="whitebox.json")
    p.add_argument("--model")
    p.add_argument("--observations")
    p.add_argument("--out")
    a = p.parse_args()
    root = Path(a.root).absolute().resolve()
    contract = read(contained(root, a.contract))
    errors = schema_errors(contract)
    result = {
        "valid": not errors,
        "errors": errors,
        "status": "planned",
        "rules": [r.get("id") for r in contract.get("rules", [])],
        "meaning": "Plan shape only; implementation and runtime are not verified.",
    }
    if a.command == "check":
        if not a.model or not a.observations:
            p.error("check requires --model and --observations")
        model = read(contained(root, a.model))
        intent = read(contained(root, model["intent"]))
        structure = scan(root, [s for s in model["source_files"] if s.endswith(".py")])
        errors += static_errors(
            contract, model, structure, {r["id"] for r in intent["requirements"]}
        )
        result = assess(
            contract, model, read(contained(root, a.observations)), capture(root, model)["build_id"]
        )
        result["errors"] = errors + result["errors"]
        result["valid"] = not result["errors"]
    if a.out:
        out = contained(root, a.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, ensure_ascii=False))
        raise SystemExit(2)
