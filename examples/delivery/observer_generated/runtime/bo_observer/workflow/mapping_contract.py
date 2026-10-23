"""Compare mapped observations with independently read implementation facts.

No desired business outcome belongs here. A faithfully displayed defect can pass
this check while the separately authored business contract fails.
"""

import json

try:
    from ...bo_stategraph import BOStateGraph, bo_validate_export
except ImportError:
    from bo_stategraph import BOStateGraph, bo_validate_export


def at(value, path):
    for key in path:
        value = value[key]
    return value


def equal(a, b):
    return json.dumps(a, sort_keys=True, allow_nan=False) == json.dumps(
        b, sort_keys=True, allow_nan=False
    )


def validate_plan(plan, model):
    """The project owns a protected list, not a list inferred from submitted checks."""
    if not isinstance(plan, dict) or plan.get("schema") != "bo-mapping/v1":
        raise ValueError("implementation mapping plan bo-mapping/v1 is required")
    for name in ("cases", "modes", "fields"):
        if not isinstance(plan.get(name), list) or not plan[name]:
            raise ValueError("mapping plan needs " + name)
    if len(set(plan["cases"])) != len(plan["cases"]) or len(set(plan["modes"])) != len(
        plan["modes"]
    ):
        raise ValueError("duplicate mapping case or mode")
    if set(plan["modes"]) - {"on", "off", "fault"}:
        raise ValueError("unknown mapping mode")
    if not plan.get("source"):
        raise ValueError("mapping source is required")
    for name in ("actual_collection", "actual_id"):
        if not isinstance(plan.get(name), list) or not plan[name]:
            raise ValueError("mapping plan needs " + name)
    nodes = {n["id"] for n in model["nodes"]}
    ids, mapped = set(), set()
    for field in plan["fields"]:
        if not field.get("id") or field["id"] in ids or field.get("node") not in nodes:
            raise ValueError("mapping field needs a unique identity and graph node")
        ids.add(field["id"])
        for name in ("actual", "mapped"):
            if not isinstance(field.get(name), list) or (name == "mapped" and not field[name]):
                raise ValueError("mapping field needs actual and mapped paths")
        if "keys" in field and (not field["keys"] or len(set(field["keys"])) != len(field["keys"])):
            raise ValueError("mapping selected keys must be nonempty and unique")
        mapped.add(tuple(field["mapped"]))
    if not {("state",), ("revision",), ("build_id",)} <= mapped:
        raise ValueError("mapping plan must cover state, complete revision and build identity")
    for name in model["machine"]["context"]:
        if ("context",) not in mapped and ("context", name) not in mapped:
            raise ValueError("mapping plan omits context field: " + name)
    if model["machine"].get("execution") and ("configuration",) not in mapped:
        raise ValueError("mapping plan must cover the complete activity configuration")
    selected = plan.get("export", {})
    if selected.get("case") not in plan["cases"] or selected.get("mode") not in plan["modes"]:
        raise ValueError("mapping plan must select the actual public export case and mode")
    return plan


def protected_plan_errors(before, after):
    if not before:
        return []
    if not after:
        return ["mapping plan was removed"]
    errors = []
    for name in ("cases", "modes", "fields"):
        if any(v not in after.get(name, []) for v in before[name]):
            errors.append("mapping coverage was removed or changed: " + name)
    for name in ("source", "actual_collection", "actual_id", "export"):
        if before.get(name) != after.get(name):
            errors.append("mapping binding changed: " + name)
    return errors


def assess_projections(payload, plan, model, build_id):
    validate_plan(plan, model)
    errors, checks = [], 0
    public = bo_validate_export(payload["stategraph_export"])
    if (
        public["model"] != model
        or public["build_id"] != build_id
        or payload.get("build_id") != build_id
    ):
        raise ValueError("mapping projection belongs to another model or build")
    graph = BOStateGraph(model, build_id=build_id)
    runs = {}
    for run in payload.get("runs", []):
        key = (run["case"], run["mode"])
        if key in runs:
            raise ValueError("duplicate actual scenario: " + str(key))
        runs[key] = run
    required = {(case, mode) for case in plan["cases"] for mode in plan["modes"]}
    if required != set(runs):
        raise ValueError("mapping scenario coverage differs from protected plan")
    for key in sorted(required):
        run = runs[key]
        sample = run["projection"]
        if sample["build_id"] != build_id:
            raise ValueError("scenario projection has wrong build")
        instances = sample["instances"]
        if not equal(instances, graph.bo_instances(sample["machine"])):
            raise ValueError("scenario instances differ from its runtime machine")
        for item in instances:
            if item.get("missing"):
                errors.append(
                    {
                        "case": key,
                        "instance": item["observed"]["instance_id"],
                        "error": "required runtime evidence is incomplete",
                        "missing": item["missing"],
                    }
                )
        mapped = {item["observed"]["instance_id"]: item["observed"] for item in instances}
        records = at(run, plan["actual_collection"])
        actual = {at(item, plan["actual_id"]): item for item in records}
        if len(actual) != len(records) or len(mapped) != len(instances):
            raise ValueError("duplicate actual or mapped instance")
        checks += 1
        if sorted(actual) != sorted(mapped):
            errors.append({"case": key, "error": "actual and exported instance identities differ"})
        for ident, raw in actual.items():
            if ident not in mapped:
                continue
            for field in plan["fields"]:
                checks += 1
                a, b = at(raw, field["actual"]), at(mapped[ident], field["mapped"])
                if "keys" in field:
                    if set(a) != set(field["keys"]):
                        raise ValueError("actual configuration fields differ from mapping plan")
                    a, b = ({k: value[k] for k in field["keys"]} for value in (a, b))
                if not equal(a, b):
                    errors.append(
                        {
                            "case": key,
                            "instance": ident,
                            "field": field["id"],
                            "node": field["node"],
                            "source": plan["source"],
                            "error": "actual value differs from exported projection",
                        }
                    )
    selected = runs[(plan["export"]["case"], plan["export"]["mode"])]["projection"]
    if not equal(public["instances"], selected["instances"]) or not equal(
        public["runtime"]["machine"], selected["machine"]
    ):
        errors.append("public export differs from its protected scenario projection")
    return errors, checks


def instance_witnesses(instances, actual, *, case, source):
    """actual is read from the application's store by the scenario runner."""
    mapped = {i["observed"]["instance_id"]: i["observed"] for i in instances}
    result = [
        {
            "id": case + ":instances",
            "source": source,
            "projection": "bo_instances.instance_id",
            "actual": sorted(actual),
            "mapped": sorted(mapped),
        }
    ]
    for ident, fields in actual.items():
        for name, value in fields.items():
            result.append(
                {
                    "id": f"{case}:{ident}:{name}",
                    "source": source,
                    "projection": "bo_instances." + name,
                    "actual": value,
                    "mapped": mapped.get(ident, {}).get(name),
                }
            )
    return result


def assess(payload, *, required=False, plan=None, model=None, build_id=None):
    checks = payload.get("mapping_checks", [])
    errors = []
    if required and not checks:
        errors.append("no implementation mapping witnesses")
    projected = 0
    if plan is not None or required:
        try:
            projection_errors, projected = assess_projections(payload, plan, model, build_id)
            errors.extend(projection_errors)
        except (ValueError, TypeError, KeyError, IndexError, AttributeError) as exc:
            errors.append("invalid or incomplete implementation mapping: " + str(exc))
    seen = set()
    for check in checks:
        ident = check.get("id")
        if not ident or ident in seen:
            errors.append("missing or duplicate mapping check identity")
        seen.add(ident)
        if not check.get("source") or not check.get("projection"):
            errors.append({"check": ident, "error": "source and projection provenance required"})
        if "actual" not in check or "mapped" not in check:
            errors.append({"check": ident, "error": "missing actual or mapped value"})
            continue
        encode = lambda value: json.dumps(
            value, sort_keys=True, allow_nan=False, ensure_ascii=False
        )
        if encode(check["actual"]) != encode(check["mapped"]):
            errors.append(
                {
                    "check": ident,
                    "error": "mapped value differs from implementation",
                    "actual": check["actual"],
                    "mapped": check["mapped"],
                }
            )
    return {
        "valid": not errors,
        "errors": errors,
        "checks": len(checks),
        "projection_checks": projected,
        "scope": "Protected scenario/field plan against actual source facts and public projections; unexercised behavior remains unknown.",
    }
