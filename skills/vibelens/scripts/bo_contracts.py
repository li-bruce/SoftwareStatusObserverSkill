"""Shared, application-independent model and value contracts.

The project checker, standalone module and exports use these same rules.
Runtime violations are diagnostics; callers must preserve the actual facts.
"""

import math
import json


def value_errors(value, spec, name):
    kind = spec.get("type")
    matches = {
        "integer": type(value) is int,
        "number": type(value) in (int, float) and math.isfinite(value),
        "boolean": type(value) is bool,
        "string": isinstance(value, str),
        "array": isinstance(value, list),
        "object": isinstance(value, dict),
        "enum": any(type(value) is type(item) and value == item for item in spec.get("values", [])),
    }
    if not matches.get(kind, False):
        return [f"{name}: expected {kind}"]
    errors = []
    if kind in ("integer", "number"):
        if "min" in spec and value < spec["min"]:
            errors.append(f"{name}: below min")
        if "max" in spec and value > spec["max"]:
            errors.append(f"{name}: above max")
    if kind == "array" and spec.get("items"):
        for i, item in enumerate(value):
            errors.extend(value_errors(item, spec["items"], f"{name}[{i}]"))
    if kind == "object":
        for key in spec.get("required", []):
            if key not in value:
                errors.append(f"{name}.{key}: missing")
        for key, item in spec.get("properties", {}).items():
            if key in value:
                errors.extend(value_errors(value[key], item, f"{name}.{key}"))
    return errors


def state_tree(chart):
    """Return actual engine names and ancestry; underscores are not split heuristically."""
    states, parents = {}, {}
    separator = chart.get("separator", "_")
    if separator != "_":
        raise ValueError("unsupported state separator: " + str(separator))

    def descend(items, parent=None):
        if not isinstance(items, list) or not items:
            raise ValueError("states must be a nonempty list")
        for item in items:
            data = {"name": item} if isinstance(item, str) else item
            if (
                not isinstance(data, dict)
                or not isinstance(data.get("name"), str)
                or not data["name"]
            ):
                raise ValueError("state needs a nonempty name")
            unsupported = set(data) - {"name", "initial", "children", "parallel"}
            if unsupported:
                raise ValueError("unsupported state semantics: " + ", ".join(sorted(unsupported)))
            if "parallel" in data and ("children" in data or "initial" in data):
                raise ValueError("parallel state cannot also declare children or initial")
            name = (parent + separator if parent else "") + data["name"]
            if name in states:
                raise ValueError("duplicate state name")
            if data.get("history"):
                raise ValueError("history states require a supported engine adapter")
            states[name], parents[name] = data, parent
            nested = data.get("parallel", data.get("children"))
            if nested is not None:
                descend(nested, name)

    descend(chart["states"])
    for name, data in states.items():
        if "initial" in data:
            initial = data["initial"]
            if not isinstance(initial, str) or name + separator + initial not in states:
                raise ValueError("unknown compound initial state: " + name)
    return states, parents


def entered_states(chart, target):
    """Resolve compound initial descendants and every parallel region."""
    states, parents = state_tree(chart)
    if target not in states:
        raise ValueError("unknown transition target")

    def enter(name):
        data = states[name]
        if data.get("parallel"):
            return [
                leaf for child, parent in parents.items() if parent == name for leaf in enter(child)
            ]
        if data.get("initial"):
            return enter(name + "_" + data["initial"])
        return [name]

    return enter(target)


def transition_states(chart, previous, transitions):
    """Expected configuration for the supported declarative subset, never facts.

    This checks only supplied guard results. It does not call business callbacks.
    Independent parallel region transitions compose; cross-region transitions
    are rejected when the declaration is loaded.
    """
    states, parents = state_tree(chart)
    before = active_states(chart, previous)
    leaves = {
        s for s in before if not any(p == s and child in before for child, p in parents.items())
    }

    def chain(name):
        result = []
        while name is not None:
            result.append(name)
            name = parents[name]
        return result

    removed, added = set(), set()
    for transition in transitions:
        target = transition["dest"]
        if target is None:
            continue
        sources = transition["source"]
        sources = sources if isinstance(sources, list) else [sources]
        if "*" in sources:
            sources = [s for s, p in parents.items() if p is None]
        for source in set(sources) & before:
            ancestors = chain(source)
            common = next((p for p in ancestors if p in chain(target)), None)
            exit_root = source
            while parents[exit_root] is not None and parents[exit_root] != common:
                exit_root = parents[exit_root]
            if common == source:
                exit_root = source
            removed.update(s for s in leaves if exit_root in chain(s))
            added.update(entered_states(chart, target))
    return active_states(chart, sorted((leaves - removed) | added))


def validate_value_spec(spec, name):
    if not isinstance(spec, dict) or spec.get("type") not in {
        "integer",
        "number",
        "boolean",
        "string",
        "enum",
        "array",
        "object",
    }:
        raise ValueError("unknown value type: " + name)
    if spec["type"] == "enum" and (not isinstance(spec.get("values"), list) or not spec["values"]):
        raise ValueError("enum needs values: " + name)
    for bound in ("min", "max"):
        if bound in spec and (
            type(spec[bound]) not in (int, float) or not math.isfinite(spec[bound])
        ):
            raise ValueError("invalid bound: " + name)
    if "min" in spec and "max" in spec and spec["min"] > spec["max"]:
        raise ValueError("invalid bounds")
    if spec.get("items") is not None:
        validate_value_spec(spec["items"], name + "[]")
    for key, child in spec.get("properties", {}).items():
        validate_value_spec(child, name + "." + key)


def validate_runtime_definition(
    chart, *, loaded_engine=None, loaded_version=None, guard_names=None
):
    """Fail before creating an executor when its declared semantics are unsupported."""
    if not isinstance(chart, dict):
        raise ValueError("statechart must be an object")
    unsupported = set(chart) & {
        "queued",
        "auto_transitions",
        "ignore_invalid_triggers",
        "send_event",
        "ordered_transitions",
        "model_override",
        "before_state_change",
        "after_state_change",
        "prepare_event",
        "finalize_event",
        "on_exception",
    }
    if unsupported:
        raise ValueError("unsupported engine options: " + ", ".join(sorted(unsupported)))
    engine = chart.get("engine")
    if engine not in (
        None,
        "transitions.Machine",
        "transitions.HierarchicalMachine",
        "transitions.extensions.HierarchicalMachine",
        "adapter-selected",
        "python.explicit",
        "bo.fsm",
    ):
        raise ValueError("unsupported execution engine: " + str(engine))
    if loaded_engine is not None and engine not in (None, "adapter-selected", loaded_engine):
        raise ValueError("loaded engine differs from declaration")
    if (
        loaded_version is not None
        and engine != "adapter-selected"
        and chart.get("version") != loaded_version
    ):
        raise ValueError("loaded engine version differs from declaration")
    if guard_names is not None and set(chart.get("guards", {})) - set(guard_names):
        raise ValueError("declared guard is missing from loaded executor")
    states, parents = state_tree(chart)
    if engine == "bo.fsm":
        if (
            chart.get("version") != "1"
            or any(p is not None for p in parents.values())
            or chart.get("execution")
        ):
            raise ValueError(
                "bo.fsm/1 supports flat states; hierarchy and activities need an explicit engine adapter"
            )
        if set(chart) - {
            "engine",
            "version",
            "states",
            "values",
            "initial",
            "state_type",
            "transitions",
            "events",
            "context",
            "guards",
            "labels",
        }:
            raise ValueError("unsupported bo.fsm semantics")
        if (
            chart.get("state_type") != "enum"
            or not isinstance(chart.get("values"), list)
            or len(chart["values"]) != len(states)
            or set(chart["values"]) != set(states)
        ):
            raise ValueError("bo.fsm values must exactly cover its states")
        if not all(isinstance(chart.get(k), dict) for k in ("context", "events", "guards")):
            raise ValueError("bo.fsm requires context, events and guards objects")
    if chart.get("initial") not in states:
        raise ValueError("unknown initial state")
    active_states(chart, entered_states(chart, chart["initial"]))
    if engine == "transitions.Machine" and any(p is not None for p in parents.values()):
        raise ValueError("flat engine cannot load hierarchical states")
    for name, spec in chart.get("context", {}).items():
        validate_value_spec(spec, name)
    for event, data in chart.get("events", {}).items():
        if not isinstance(data, dict) or not isinstance(data.get("payload"), dict):
            raise ValueError("event needs payload declaration: " + event)
        for name, spec in data["payload"].items():
            validate_value_spec(spec, event + "." + name)
    for transition in chart["transitions"]:
        if set(transition) - {"source", "dest", "trigger", "conditions", "unless"}:
            raise ValueError("unsupported transition callback or semantics")
        sources = transition["source"]
        sources = sources if isinstance(sources, list) else [sources]
        if not sources:
            raise ValueError("transition needs a source")
        if any(s != "*" and s not in states for s in sources) or transition["dest"] not in {
            None,
            *states,
        }:
            raise ValueError("dangling transition")
        if transition["trigger"] not in chart.get("events", {}):
            raise ValueError("unknown transition event")
        for field in ("conditions", "unless"):
            refs = transition.get(field, [])
            refs = refs if isinstance(refs, list) else [refs]
            if set(refs) - set(chart.get("guards", {})):
                raise ValueError("undefined guard")
        # Explicitly bound the supported HSM subset instead of silently applying
        # sequential rules to cross-region transitions.
        for source in sources:
            if source == "*" or transition["dest"] is None:
                continue
            branch = source
            while parents[branch] is not None:
                parent = parents[branch]
                if states[parent].get("parallel") and not (
                    transition["dest"] == branch or transition["dest"].startswith(branch + "_")
                ):
                    raise ValueError("cross-region transition requires a supported engine adapter")
                branch = parent


def active_states(chart, value):
    states, parents = state_tree(chart)
    leaves = []

    def collect(item):
        if isinstance(item, list):
            for child in item:
                collect(child)
        else:
            leaves.append(item)

    collect(value)
    if not leaves or len(set(leaves)) != len(leaves) or any(s not in states for s in leaves):
        raise ValueError("unknown or duplicate active state")
    result = set(leaves)
    for leaf in leaves:
        parent = parents[leaf]
        while parent:
            result.add(parent)
            parent = parents[parent]
    # Concurrent leaves are legal only in distinct regions of a parallel state.
    # A parent plus its active child is not a second active leaf.
    for parent in [None, *states]:
        children = [s for s, p in parents.items() if p == parent and s in result]
        parallel = parent is not None and bool(states[parent].get("parallel"))
        if parent in leaves and states[parent].get("initial") and not children:
            raise ValueError("compound configuration is missing its active descendant")
        if len(children) > 1 and not parallel:
            raise ValueError("exclusive states cannot be active together")
        if parent in result and parallel:
            declared = [s for s, p in parents.items() if p == parent]
            if set(children) != set(declared):
                raise ValueError("parallel configuration is missing an active region")
        if parent in leaves and children:
            raise ValueError("active configuration repeats an ancestor")
    return result


def validate_graph(model):
    if model.get("schema_version") == 3:
        for key in ("revision", "intent", "source_files", "nodes", "edges", "overview", "scope"):
            if not model.get(key):
                raise ValueError("missing " + key)
    elif model.get("schema_version") not in (None, "bo-model/v1"):
        raise ValueError("unsupported model schema")
    nodes = {n["id"]: n for n in model.get("nodes", [])}
    if not nodes or len(nodes) != len(model["nodes"]):
        raise ValueError("invalid node identities")
    for node in nodes.values():
        seen = {node["id"]}
        parent = node.get("parent")
        while parent:
            if parent not in nodes or parent in seen:
                raise ValueError("missing parent or hierarchy cycle")
            seen.add(parent)
            parent = nodes[parent].get("parent")
        if model.get("schema_version") == 3:
            if node.get("kind") not in {
                "action",
                "function",
                "decision",
                "wait",
                "effect",
                "data",
                "state",
            }:
                raise ValueError("invalid node kind")
            if not node.get("label") or not node.get("summary"):
                raise ValueError("node lacks developer explanation")
            if node["kind"] not in {"data", "state"} and not node.get("source"):
                raise ValueError("executable node lacks source: " + node["id"])
    edges = set()
    for edge in model.get("edges", []):
        if edge["id"] in edges or edge["from"] not in nodes or edge["to"] not in nodes:
            raise ValueError("duplicate/dangling edge")
        edges.add(edge["id"])
        if model.get("schema_version") == 3 and (
            edge.get("type") not in {"flow", "data", "guard", "contains", "resource", "join"}
            or not edge.get("evidence")
        ):
            raise ValueError("edge needs type and provenance")
        if edge.get("type") in ("resource", "join") and not model.get("machine", {}).get(
            "execution"
        ):
            raise ValueError("resource and join edges need an executable activity declaration")
    for item in model.get("overview", []):
        if item["node"] not in nodes:
            raise ValueError("unknown overview node")
    return nodes


def validate_chart(model, runtime_definition=None):
    validate_graph(model)
    chart = model["machine"]
    # Compact models are explicit bo-model/v1 or legacy unversioned declarations.
    fields = ("states", "values", "transitions", "events", "initial", "context")
    if model.get("schema_version") == 3:
        fields += ("engine", "version", "state_type")
    for key in fields:
        if key not in chart or chart[key] is None:
            raise ValueError("missing statechart field: " + key)
    validate_runtime_definition(chart)
    states, _ = state_tree(chart)
    values = set(chart["values"])
    if not values or len(values) != len(chart["values"]):
        raise ValueError("duplicate or missing state values")
    if not values <= states.keys():
        raise ValueError("unknown persisted state value")
    if chart["initial"] not in states:
        raise ValueError("unknown initial state")
    for name, spec in chart["context"].items():
        if spec.get("type") not in {
            "integer",
            "number",
            "boolean",
            "string",
            "enum",
            "array",
            "object",
        }:
            raise ValueError("unknown context type: " + name)
        if spec["type"] == "enum" and not spec.get("values"):
            raise ValueError("enum needs values")
        if "min" in spec and "max" in spec and spec["min"] > spec["max"]:
            raise ValueError("invalid bounds")
    for transition in chart["transitions"]:
        event = transition.get("trigger")
        if event not in chart["events"] or not isinstance(
            chart["events"][event].get("payload"), dict
        ):
            raise ValueError("transition event needs payload declaration")
        sources = transition["source"]
        sources = sources if isinstance(sources, list) else [sources]
        if any(s != "*" and s not in states for s in sources) or (
            transition["dest"] is not None and transition["dest"] not in states
        ):
            raise ValueError("dangling transition")
        for field in ("conditions", "unless"):
            refs = transition.get(field, [])
            refs = refs if isinstance(refs, list) else [refs]
            if set(refs) - set(chart.get("guards", {})):
                raise ValueError("undefined guard")
    represented = {n["value"] for n in model["nodes"] if n.get("layer") == "state"}
    if values != represented:
        raise ValueError("persisted states and graph projection differ")
    if runtime_definition is not None:
        validate_runtime_definition(runtime_definition)
        if json.dumps(chart, sort_keys=True, allow_nan=False) != json.dumps(
            runtime_definition, sort_keys=True, allow_nan=False
        ):
            raise ValueError("graph and runtime statechart declarations differ")
    try:
        from .execution_contract import validate_execution_graph
    except ImportError:
        from execution_contract import validate_execution_graph
    validate_execution_graph(model)
    return {
        "valid": True,
        "states": len(values),
        "events": len(chart["events"]),
        "runtime_definition_compared": runtime_definition is not None,
    }
