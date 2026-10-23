"""Check an inline activity configuration against its state graph and actual journal.

This protocol supports one invocation per declared activity in each run, integer
capacity, atomic allocation, completion and ALL join. It does not infer hidden calls.
"""

from copy import deepcopy

TERMINAL = {"succeeded", "rejected", "failed", "cancelled"}


def validate_execution_graph(model):
    """Validate activity, join, and resource declarations within the same state graph."""
    spec = model.get("machine", {}).get("execution")
    if not spec:
        return {"valid": True, "applicable": False}
    if spec.get("schema") != "activity-graph/v1":
        raise ValueError("unsupported activity configuration schema")
    chart = model["machine"]
    nodes = {n["id"]: n for n in model["nodes"]}
    if spec["within"] not in chart["values"] or spec["parent"] not in nodes:
        raise ValueError("execution scope missing")
    activities = {a["id"]: a for a in spec["activities"]}
    resources = {r["id"]: r for r in spec["resources"]}
    join = spec["join"]
    if (
        not activities
        or len(activities) != len(spec["activities"])
        or len(resources) != len(spec["resources"])
    ):
        raise ValueError("duplicate or missing activity/resource IDs")
    if set(activities) & set(resources) or join["id"] in {*activities, *resources}:
        raise ValueError("execution identities overlap")
    if (
        join["policy"] != "all"
        or len(set(join["requires"])) != len(join["requires"])
        or set(join["requires"]) != set(activities)
    ):
        raise ValueError("ALL join must include every declared activity")
    if set(spec["activity_states"]) != {"pending", "waiting", "running", *TERMINAL}:
        raise ValueError("incomplete activity states")
    for r in resources.values():
        if (
            r.get("scope") != "run"
            or type(r["min"]) is not int
            or type(r["max"]) is not int
            or not 0 < r["min"] <= r["max"]
        ):
            raise ValueError("unsupported resource scope or capacity bounds")
    expected = set()
    for aid, a in activities.items():
        if not a["requires"] or set(a["requires"]) - set(resources):
            raise ValueError("undefined resource dependency")
        for rid, units in a["requires"].items():
            if type(units) is not int or units <= 0 or units > resources[rid]["min"]:
                raise ValueError("activity cannot start at minimum capacity")
            expected.add((rid, aid, "resource", units))
        expected.add((aid, join["id"], "join", None))
        if nodes.get(aid, {}).get("source") != a["source"]:
            raise ValueError("activity source and graph source differ: " + aid)
    for key, role in (
        [(a, "activity") for a in activities]
        + [(r, "resource") for r in resources]
        + [(join["id"], "join")]
    ):
        n = nodes.get(key, {})
        if n.get("parent") != spec["parent"] or n.get("execution_role") != role:
            raise ValueError(
                "activity configuration must be represented by the original inline node: " + key
            )
    actual = {
        (e["from"], e["to"], e["type"], e.get("units"))
        for e in model["edges"]
        if e["type"] in ("resource", "join")
    }
    if actual != expected:
        raise ValueError("inline resource/join edges differ from executable declaration")
    if model.get("worknet"):
        raise ValueError("integrated activity model must not add a separate worknet projection")
    guarded = [t for t in chart["transitions"] if t["dest"] in join["success_states"]]
    if not guarded:
        raise ValueError("missing lifecycle completion transition")
    for t in guarded:
        conditions = t.get("conditions", [])
        conditions = [conditions] if isinstance(conditions, str) else conditions
        if join["guard"] not in conditions:
            raise ValueError("lifecycle can bypass activity completion")
    return {"valid": True, "activities": len(activities), "resources": len(resources)}


def validate_configuration(model, snapshot):
    """Check a runtime activity/resource configuration against its declared capacities and states."""
    spec = model["machine"]["execution"]
    activities = {a["id"]: a for a in spec["activities"]}
    resources = {r["id"]: r for r in spec["resources"]}
    join = spec["join"]
    if (
        not isinstance(snapshot.get("attempt"), str)
        or not snapshot["attempt"]
        or type(snapshot.get("param_version")) is not int
        or snapshot["param_version"] < 1
    ):
        raise ValueError("missing execution instance identity")
    if set(snapshot.get("activities", {})) != set(activities) or set(
        snapshot.get("resources", {})
    ) != set(resources):
        raise ValueError("execution instance omits declared internal states")
    initial_resources = {}
    for rid, r in resources.items():
        capacity = snapshot["resources"][rid]["capacity"]
        if type(capacity) is not int or not r["min"] <= capacity <= r["max"]:
            raise ValueError("invalid capacity")
        initial_resources[rid] = {"capacity": capacity, "available": capacity, "holders": []}
    current = {
        "activities": {a: "pending" for a in activities},
        "resources": initial_resources,
        "join": {"state": "waiting", "pending": list(join["requires"])},
    }
    journal = snapshot.get("journal", [])
    if type(snapshot.get("revision")) is not int or snapshot["revision"] != len(journal):
        raise ValueError("missing execution updates")
    for seq, entry in enumerate(journal, 1):
        if entry["seq"] != seq or entry["before"] != current:
            raise ValueError("execution history is discontinuous")
        expected = deepcopy(current)
        event = entry["event"]
        aid = entry["activity"]
        states = expected["activities"]
        if event in ("wait", "start", "finish"):
            if aid not in activities:
                raise ValueError("unknown running activity")
            need = activities[aid]["requires"]
            can_start = all(expected["resources"][r]["available"] >= n for r, n in need.items())
            if event == "wait":
                if states[aid] != "pending" or can_start:
                    raise ValueError("resource wait has no missing resource")
                states[aid] = "waiting"
            elif event == "start":
                if states[aid] not in ("pending", "waiting") or not can_start:
                    raise ValueError("activity started without resource")
                for rid, n in need.items():
                    expected["resources"][rid]["available"] -= n
                    expected["resources"][rid]["holders"].append(aid)
                states[aid] = "running"
            else:
                outcome = entry["after"]["activities"].get(aid)
                if states[aid] != "running" or outcome not in {"succeeded", "rejected", "failed"}:
                    raise ValueError("completion without running activity")
                for rid, n in need.items():
                    expected["resources"][rid]["available"] += n
                    expected["resources"][rid]["holders"].remove(aid)
                states[aid] = outcome
                if all(states[a] in TERMINAL for a in join["requires"]):
                    expected["join"]["state"] = "enabled"
        elif event == "join":
            if aid != join["id"] or expected["join"]["state"] != "enabled":
                raise ValueError("join before all activities completed")
            expected["join"]["state"] = (
                "passed" if all(states[a] == "succeeded" for a in join["requires"]) else "rejected"
            )
        elif event == "abort":
            if aid != join["id"] or "running" in states.values():
                raise ValueError("abort leaves running activity/resource")
            expected["activities"] = {
                a: s if s in TERMINAL else "cancelled" for a, s in states.items()
            }
            expected["join"]["state"] = "rejected"
        else:
            raise ValueError("unknown internal state event")
        expected["join"]["pending"] = [
            a for a in join["requires"] if expected["activities"][a] not in TERMINAL
        ]
        if expected != entry["after"]:
            raise ValueError("internal state update violates declared resource or join rules")
        current = expected
    if current != {k: snapshot[k] for k in ("activities", "resources", "join")}:
        raise ValueError("current state differs from actual execution history")
    if snapshot.get("phase") in join["success_states"] and (
        current["join"]["state"] != "passed"
        or any(s != "succeeded" for s in current["activities"].values())
    ):
        raise ValueError("lifecycle advanced before this execution completed")
    return {"valid": True, "updates": len(journal)}
