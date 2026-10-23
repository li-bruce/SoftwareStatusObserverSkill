"""Check a business-network draft and select unanswered questions.

This validates authored records and their links. It does not interpret natural
language, discover every ambiguity, or authenticate a claimed user quotation.
"""

from __future__ import annotations
import argparse
import json
from pathlib import Path

KINDS = {"action", "condition", "state", "effect", "resource", "event", "data"}
RELATIONS = {"flow", "guard", "data", "event", "resource", "join", "retry", "cancel"}
STATUSES = {"open", "resolved", "assumed", "deferred"}
CRITICAL = {
    "authority",
    "parameters",
    "completion",
    "concurrency",
    "resources",
    "cancellation",
    "retry",
    "consistency",
}
TOPICS = CRITICAL | {"scope", "other", "presentation"}
SOURCE_KINDS = {"user", "project_rule", "inference", "assistant"}


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _assess(doc, *, intent=None, model=None, acceptance=None, previous=None):
    """Check question, answer, decision, and graph references against the recorded conversation.

    Unanswered business ambiguities block confirmation. This validates the supplied
    record; it does not propose additional product requirements.
    """
    errors = []
    warnings = []

    def error(code, item):
        errors.append({"code": code, "item": str(item)})

    def text(value):
        return isinstance(value, str) and bool(value.strip())

    def records(values, label):
        if not isinstance(values, list):
            error("expected_list", label)
            return {}
        result = {}
        for value in values:
            if not isinstance(value, dict) or not text(value.get("id")):
                error("missing_id", label)
                continue
            if value["id"] in result:
                error("duplicate_id", value["id"])
            result[value["id"]] = value
        return result

    if not isinstance(doc, dict):
        return {
            "valid": False,
            "ready": False,
            "errors": [{"code": "expected_object", "item": "discovery"}],
            "warnings": [],
            "blocked": [],
            "questions": [],
            "awaiting_answers": [],
        }
    for name, artifact in [
        ("intent", intent),
        ("model", model),
        ("acceptance", acceptance),
        ("previous", previous),
    ]:
        if artifact is not None and not isinstance(artifact, dict):
            error("expected_object", name)
    if errors:
        return {
            "valid": False,
            "ready": False,
            "errors": errors,
            "warnings": [],
            "blocked": [],
            "questions": [],
            "awaiting_answers": [],
        }
    if doc.get("schema") != "business-discovery/v1":
        error("unknown_schema", "discovery")
    if not text(doc.get("goal")):
        error("missing_goal", "discovery")
    sources = records(doc.get("sources"), "sources")
    for sid, source in sources.items():
        if (
            source.get("kind") not in SOURCE_KINDS
            or not text(source.get("text"))
            or not text(source.get("locator"))
        ):
            error("invalid_source", sid)

    def refs(value, item, allowed=None):
        if (
            not isinstance(value, list)
            or not value
            or any(not isinstance(x, str) or x not in sources for x in value)
        ):
            error("missing_source", item)
            return False
        if allowed and any(sources[x].get("kind") not in allowed for x in value):
            error("not_a_decision_source", item)
            return False
        return True

    networks = records(doc.get("networks"), "networks")
    nodes = {}
    edges = {}
    if not networks:
        error("missing_business_network", "networks")
    for nid, net in networks.items():
        for field in ("title", "trigger", "outcome"):
            if not text(net.get(field)):
                error("missing_network_field", nid + "." + field)
        if (
            not isinstance(net.get("actors"), list)
            or not net["actors"]
            or not all(text(x) for x in net["actors"])
        ):
            error("missing_actors", nid)
        local = records(net.get("nodes"), nid + ".nodes")
        connections = records(net.get("edges"), nid + ".edges")
        if not local:
            error("empty_network", nid)
        for ident, item in local.items():
            if ident in nodes or ident in edges:
                error("duplicate_graph_id", ident)
            if not text(item.get("label")) or item.get("kind") not in KINDS:
                error("invalid_business_node", ident)
            refs(item.get("source_refs"), ident)
            nodes[ident] = item
        for ident, edge in connections.items():
            if ident in nodes or ident in edges:
                error("duplicate_graph_id", ident)
            if edge.get("relation") not in RELATIONS or not text(edge.get("label")):
                error("invalid_business_edge", ident)
            refs(edge.get("source_refs"), ident)
            edges[ident] = edge
    known = set(nodes) | set(edges)
    for ident, edge in edges.items():
        if edge.get("from") not in nodes or edge.get("to") not in nodes:
            error("unknown_edge_endpoint", ident)
    decisions = records(doc.get("decisions"), "decisions")
    for did, d in decisions.items():
        if d.get("topic") not in TOPICS or d.get("status") not in STATUSES:
            error("invalid_decision", did)
        if type(d.get("blocking")) is not bool:
            error("missing_blocking_flag", did)
        if d.get("topic") in CRITICAL and not d.get("blocking"):
            error("behavior_question_cannot_be_optional", did)
        for field in ("question", "why"):
            if not text(d.get(field)):
                error("missing_question_context", did + "." + field)
        refs(d.get("source_refs"), did)
        affects = d.get("affects")
        if (
            not isinstance(affects, list)
            or not affects
            or any(not isinstance(x, str) or x not in known for x in affects)
        ):
            error("unknown_affected_behavior", did)
        priority = d.get("priority", 2)
        if type(priority) is not int or priority not in (1, 2, 3):
            error("invalid_question_priority", did)
        options = d.get("options", [])
        if not isinstance(options, list) or (options and not 2 <= len(options) <= 3):
            error("invalid_options", did)
        elif options:
            items = records(options, did + ".options")
            for option in items.values():
                if not text(option.get("label")) or not text(option.get("effect")):
                    error("missing_option_effect", did)
        depends = d.get("depends_on", [])
        if not isinstance(depends, list) or any(
            not isinstance(x, str) or x not in decisions or x == did for x in depends
        ):
            error("invalid_question_dependency", did)
        asked = d.get("asked_in", [])
        if not isinstance(asked, list):
            error("invalid_question_history", did)
        elif asked:
            refs(asked, did + ".asked_in", {"assistant"})
        resolution = d.get("resolution")
        if d.get("status") == "resolved":
            if not isinstance(resolution, dict) or not text(resolution.get("text")):
                error("missing_resolution", did)
            else:
                method = resolution.get("kind")
                allowed = {
                    "user_answer": {"user"},
                    "existing_rule": {"project_rule"},
                    "delegated_choice": {"user"},
                }.get(method)
                if not allowed:
                    error("invalid_resolution_kind", did)
                else:
                    refs(resolution.get("source_refs"), did + ".resolution", allowed)
                if method == "delegated_choice" and not text(resolution.get("rationale")):
                    error("missing_delegated_rationale", did)
        elif resolution:
            error("unresolved_has_resolution", did)
        if d.get("status") in ("assumed", "deferred") and not text(d.get("note")):
            error("missing_assumption_or_deferral", did)
        if d.get("status") == "assumed":
            warnings.append({"code": "explicit_assumption", "item": did})
    if errors:
        return {
            "valid": False,
            "ready": False,
            "errors": errors,
            "warnings": warnings,
            "blocked": [],
            "questions": [],
            "awaiting_answers": [],
        }

    # Cycles in business behavior are valid; cycles between questions cannot be scheduled.
    def walk(did, stack, done):
        if did in stack:
            error("question_dependency_cycle", did)
            return
        if did in done:
            return
        stack.add(did)
        for other in (
            decisions[did].get("depends_on", [])
            if isinstance(decisions[did].get("depends_on", []), list)
            else []
        ):
            if isinstance(other, str) and other in decisions:
                walk(other, stack, done)
        stack.remove(did)
        done.add(did)

    done = set()
    for did in decisions:
        walk(did, set(), done)
    for eid, e in edges.items():
        refs_to_decisions = e.get("decision_refs", [])
        if not isinstance(refs_to_decisions, list) or any(
            not isinstance(x, str) or x not in decisions for x in refs_to_decisions
        ):
            error("unknown_edge_decision", eid)
    for did, d in decisions.items():
        if d.get("status") == "resolved" and any(
            decisions.get(x, {}).get("status") != "resolved"
            for x in d.get("depends_on", [])
            if isinstance(x, str)
        ):
            error("unresolved_upstream_decision", did)
    if previous:
        old = {
            d["id"]: d for d in previous.get("decisions", []) if isinstance(d, dict) and "id" in d
        }
        changes = records(doc.get("changes", []), "changes")
        for did, d in old.items():
            new = decisions.get(did)
            changed = (
                new is None
                or d.get("blocking")
                and not new.get("blocking")
                or d.get("status") == "resolved"
                and (
                    new.get("status") != "resolved"
                    or any(
                        new.get(k) != d.get(k)
                        for k in ("resolution", "affects", "topic", "blocking")
                    )
                )
            )
            if changed:
                matching = [
                    c
                    for c in changes.values()
                    if c.get("decision") == did and c.get("previous") == d
                ]
                if not matching:
                    error("decision_changed_without_history", did)
                else:
                    record = matching[-1]
                    refs(record.get("source_refs"), did + ".change", {"user", "project_rule"})
                    if not text(record.get("reason")):
                        error("missing_change_reason", did)
    if model is not None:
        model_ids = {n["id"] for n in model["nodes"]}
        for nid, n in nodes.items():
            links = n.get("model_nodes", [])
            if not isinstance(links, list) or any(
                not isinstance(x, str) or x not in model_ids for x in links
            ):
                error("unknown_model_node", nid)
            if not links and not text(n.get("outside_reason")):
                error("business_node_not_mapped", nid)
            if not links and n.get("outside_reason"):
                warnings.append({"code": "outside_implementation", "item": nid})
    if intent is not None or acceptance is not None or model is not None:
        rids = {r["id"] for r in (intent or {}).get("requirements", [])}
        checks = {
            c["id"]: c
            for c in [
                *(acceptance or {}).get("checks", []),
                *(acceptance or {}).get("model_checks", []),
            ]
        }
        mids = {n["id"] for n in (model or {}).get("nodes", [])}
        for did, d in decisions.items():
            if not d.get("blocking") or d.get("status") != "resolved":
                continue
            links = d.get("links", {})
            for name, artifact, ids in [
                ("requirements", intent, rids),
                ("model_nodes", model, mids),
                ("checks", acceptance, set(checks)),
            ]:
                if artifact is None:
                    continue
                values = links.get(name, []) if isinstance(links, dict) else []
                if (
                    not isinstance(values, list)
                    or not values
                    or any(not isinstance(x, str) or x not in ids for x in values)
                ):
                    error("missing_decision_link", did + "." + name)
            if intent is not None and acceptance is not None and isinstance(links, dict):
                for cid in links.get("checks", []):
                    if cid in checks and checks[cid].get("requirement") not in links.get(
                        "requirements", []
                    ):
                        error("test_for_different_requirement", did + "." + cid)
    blocked = [
        d["id"] for d in decisions.values() if d.get("blocking") and d.get("status") != "resolved"
    ]
    ready = [
        d
        for d in decisions.values()
        if d.get("status") == "open"
        and not d.get("asked_in")
        and all(
            decisions.get(x, {}).get("status") == "resolved"
            for x in d.get("depends_on", [])
            if isinstance(x, str)
        )
    ]
    # Return no usable plan for malformed records; never guess through a bad record.
    ready = (
        []
        if errors
        else sorted(ready, key=lambda d: (not d["blocking"], d.get("priority", 2), d["id"]))
    )
    return {
        "valid": not errors,
        "ready": not errors and not blocked,
        "errors": errors,
        "warnings": warnings,
        "blocked": blocked,
        "questions": ready[:3],
        "awaiting_answers": [
            d["id"] for d in decisions.values() if d.get("status") == "open" and d.get("asked_in")
        ],
    }


def assess(doc, **kwargs):
    try:
        return _assess(doc, **kwargs)
    except (TypeError, KeyError, RecursionError) as exc:
        return {
            "valid": False,
            "ready": False,
            "errors": [{"code": "invalid_record_shape", "item": str(exc)}],
            "warnings": [],
            "blocked": [],
            "questions": [],
            "awaiting_answers": [],
        }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=["validate", "questions", "check"])
    p.add_argument("--file", required=True)
    for name in ("intent", "model", "acceptance", "previous"):
        p.add_argument("--" + name)
    args = p.parse_args()
    try:
        artifacts = {
            name: read(getattr(args, name))
            for name in ("intent", "model", "acceptance", "previous")
            if getattr(args, name)
        }
        if any(not isinstance(value, dict) for value in artifacts.values()):
            raise ValueError("linked records must be JSON objects")
        result = assess(read(args.file), **artifacts)
    except (OSError, ValueError) as exc:
        result = {
            "valid": False,
            "ready": False,
            "errors": [{"code": "unreadable_record", "item": str(exc)}],
            "blocked": [],
        }
    if args.action == "check":
        result["record_valid"] = result["valid"]
        result["valid"] = result["ready"]
        if result["blocked"]:
            result["errors"].append(
                {"code": "unanswered_business_questions", "item": ",".join(result["blocked"])}
            )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["valid"] and (args.action != "check" or result["ready"]) else 1)


if __name__ == "__main__":
    main()
