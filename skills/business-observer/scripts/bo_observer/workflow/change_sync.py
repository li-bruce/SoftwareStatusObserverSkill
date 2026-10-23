"""Checked coding iterations: business intent + static slice + runtime witnesses.

Nonzero check blocks completion when integrated into the project's test/CI gate.
This is a consistency/regression mechanism, not a proof of arbitrary semantics.
Commands are explicit argv arrays from reviewed project configuration, never shell.
"""

from __future__ import annotations
import argparse
import json
from pathlib import Path

try:
    from ...bo_sync import source_inventory, maintenance_task
    from ...behavior_model import capture, check as binding_check, contained, digest, read, validate
    from ...code_structure import scan, enrich, key
    from ...statechart_contract import validate_chart
    from ...worknet_contract import validate_net
    from ...execution_contract import validate_execution_graph, validate_configuration
    from ...requirements_dialogue import assess as assess_discovery
    from ...whitebox_contract import static_errors as whitebox_static, protected_items
    from ...source_migration import source_moves, rebind_probe, rebind_whitebox
except ImportError:
    from bo_sync import source_inventory, maintenance_task
    from behavior_model import capture, check as binding_check, contained, digest, read, validate
    from code_structure import scan, enrich, key
    from statechart_contract import validate_chart
    from worknet_contract import validate_net
    from execution_contract import validate_execution_graph, validate_configuration
    from requirements_dialogue import assess as assess_discovery
    from whitebox_contract import static_errors as whitebox_static, protected_items
    from source_migration import source_moves, rebind_probe, rebind_whitebox


try:
    from ...sync_config import config, snapshot
    from ...sync_io import write, at_path
    from ...sync_verify import run_command, assess_observations, verify as verify_candidate
except ImportError:
    from sync_config import config, snapshot
    from sync_io import write, at_path
    from sync_verify import run_command, assess_observations, verify as verify_candidate


def verify(root, cfg, change):
    """Run the common verification pipeline against the current candidate and frozen baseline."""
    return verify_candidate(root, cfg, change, inspect=inspect, snapshot=snapshot)


def structural_errors(root, cfg, snap):
    """Check source scope, model bindings, probes, declarations, and test contracts together."""
    errors = list(snap["structure"]["errors"])
    if cfg.get("reconciliation"):
        from ..development import reconciliation_errors

        errors.extend(
            reconciliation_errors(snap.get("reconciliation"), snap["structure"], snap["model"])
        )
    document = read(contained(root, cfg["model"]))
    if document.get("protocol") == "bo-project/v1":
        selection = document["selection"]
        stategraph = cfg.get("stategraph", {})
        if selection["mode"] != stategraph.get("development_mode") or selection[
            "answer"
        ] != stategraph.get("decision"):
            errors.append("project JSON and sync mode choice differ")
    registered = (
        set(cfg["code_files"])
        if cfg.get("source_scope") or cfg.get("stategraph")
        else set(cfg["code_files"]) | set(cfg["watch_files"])
    )
    if not cfg.get("stategraph"):
        for path in set(snap.get("source_inventory", {}).get("files", {})) - registered:
            errors.append(
                {
                    "unregistered_source": path,
                    "action": "map implementation or record an explicit scope exclusion",
                }
            )
    if cfg.get("stategraph"):
        try:
            from ...implementation_coverage import (
                static_errors as implementation_errors,
                inventory_errors,
            )
        except ImportError:
            from implementation_coverage import (
                static_errors as implementation_errors,
                inventory_errors,
            )
        errors.extend(inventory_errors(cfg, snap.get("source_inventory", {})))
        errors.extend(
            implementation_errors(
                snap["model"].get("implementation"), snap["model"], snap["structure"]
            )
        )
        module = cfg["stategraph"]["module"]
        if module not in snap["files"] or not snap["files"].get(module):
            errors.append("independent stategraph module is missing or not watched")
        if not snap["model"].get("machine"):
            errors.append("stategraph declaration is required in both development modes")
    errors.extend({"missing_file": p} for p, sha in snap["files"].items() if sha is None)
    if not set(cfg["code_files"]) <= set(snap["model"]["source_files"]):
        errors.append("selected code files must be included in the bound source_files")
    for p, u in snap["structure"]["units"].items():
        if u["file_hash"] != snap["files"].get(p):
            errors.append("file changed during scan: " + p)
    try:
        validate(root, snap["model"])
        capture(
            root, snap["model"]
        )  # Resolve all declared source symbols; do not write a manifest.
        if snap["model"].get("machine"):
            validate_chart(snap["model"])
        if snap["model"].get("worknet"):
            validate_net(snap["model"]["worknet"])
        validate_execution_graph(snap["model"])
        projected = enrich(snap["model"], snap["structure"], cfg.get("slice_depth", 1))
        if digest(projected) != digest(snap["model"]):
            errors.append("static projection is stale: rebuild model with code_structure.enrich")
    except (OSError, ValueError, KeyError, SyntaxError) as exc:
        errors.append(str(exc))
    ids = {n["id"] for n in snap["model"]["nodes"]}
    sites = []
    for s in snap["structure"]["symbols"].values():
        for c in s["calls"]:
            if c["expression"] in cfg.get("probe_callees", ["trace.record"]) and c.get(
                "literal_pair"
            ):
                node, phase = c["literal_pair"]
                sites.append({"symbol": s["id"], "node": node, "phase": phase})
                if node not in ids:
                    errors.append("probe references missing node: " + node)
    for required in cfg.get("required_probes", []):
        if not any(all(site.get(k) == v for k, v in required.items()) for site in sites):
            errors.append({"missing_required_probe": required})
    checks = snap["acceptance"].get("checks", [])
    known = {r["id"] for r in snap["intent"]["requirements"]}
    if snap.get("whitebox"):
        errors.extend(whitebox_static(snap["whitebox"], snap["model"], snap["structure"], known))
    if not checks or len({c["id"] for c in checks}) != len(checks):
        errors.append("acceptance needs uniquely identified checks")
    for c in checks:
        if (
            c.get("requirement") not in known
            or not c.get("case")
            or not isinstance(c.get("path"), list)
            or "equals" not in c
        ):
            errors.append({"invalid_acceptance_check": c.get("id")})
    model_checks = snap["acceptance"].get("model_checks", [])
    if len({c["id"] for c in [*checks, *model_checks]}) != len(checks) + len(model_checks):
        errors.append("acceptance and model check IDs must be unique")
    for c in model_checks:
        try:
            if c.get("requirement") not in known:
                raise ValueError("unknown requirement")
            actual = at_path(snap["model"], c["path"])
            if digest(actual) != digest(c["equals"]):
                errors.append(
                    {
                        "model_claim_mismatch": c["id"],
                        "requirement": c["requirement"],
                        "expected": c["equals"],
                        "actual": actual,
                    }
                )
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            errors.append({"invalid_model_check": c.get("id"), "error": str(exc)})
    watched = set(snap["files"])
    for command in [cfg["observations_command"], *cfg.get("test_commands", [])]:
        for arg in command[1:]:
            if arg.endswith(".py") and (Path(arg).is_absolute() or arg not in watched):
                errors.append("check script must be a watched project-relative file: " + arg)
    return errors


def impact(base, current):
    """Find changed symbols and their potential callers, then trace them to graph parents."""
    old, new = base["structure"]["symbols"], current["structure"]["symbols"]
    changed = sorted(
        k
        for k in set(old) | set(new)
        if old.get(k, {}).get("ast_hash") != new.get(k, {}).get("ast_hash")
    )
    affected = set(changed)
    # Reverse static callers are potentially affected, not proof of runtime reachability.
    edges = base["structure"]["edges"] + current["structure"]["edges"]
    while True:
        callers = {e["from"] for e in edges if e["to"] in affected}
        if callers <= affected:
            break
        affected |= callers
    nodes = {n["id"]: n for m in (base["model"], current["model"]) for n in m["nodes"]}
    mapped = {
        key(n["source"]["path"], n["source"]["symbol"]) for n in nodes.values() if n.get("source")
    }
    affected_nodes = {
        n["id"]
        for n in nodes.values()
        if n.get("source") and key(n["source"]["path"], n["source"]["symbol"]) in affected
    }
    while True:
        parents = {nodes[n]["parent"] for n in affected_nodes if nodes[n].get("parent") in nodes}
        if parents <= affected_nodes:
            break
        affected_nodes |= parents
    file_changes = sorted(
        p
        for p in set(base["files"]) | set(current["files"])
        if base["files"].get(p) != current["files"].get(p)
    )
    return {
        "candidate_id": current["id"],
        "changed_files": file_changes,
        "changed_symbols": changed,
        "affected_callers": sorted(affected - set(changed)),
        "affected_nodes": sorted(affected_nodes),
        "unmapped_changed_symbols": sorted(set(changed) - mapped),
        "unmapped_implementation_symbols": sorted(set(new) - mapped),
        "changed_requirements": [
            r for r in current["intent"]["requirements"] if r not in base["intent"]["requirements"]
        ],
        "unresolved_call_count": len(current["structure"]["unresolved"]),
        "meaning": "Potential impact plus authored abstraction mapping; semantic truth still needs contract and runtime checks.",
    }


def review_errors(change, base, current, changes):
    """Reject stale reviews and unapproved weakening of requirements, probes, or assertions."""
    errors = []
    try:
        from ...mapping_contract import protected_plan_errors, validate_plan
    except ImportError:
        from mapping_contract import protected_plan_errors, validate_plan
    errors.extend(
        protected_plan_errors(base.get("mapping_contract"), current.get("mapping_contract"))
    )
    try:
        from ...implementation_coverage import (
            protected_errors,
            protected_captures,
            observer_reclassifications,
        )
    except ImportError:
        from implementation_coverage import (
            protected_errors,
            protected_captures,
            observer_reclassifications,
        )
    if current.get("stategraph_contract"):
        try:
            validate_plan(current.get("mapping_contract"), current["model"])
        except (ValueError, TypeError, KeyError) as exc:
            errors.append(str(exc))
    path = change / "review.json"
    if not path.exists():
        return ["missing review.json for this candidate"]
    review = read(path)
    if review.get("candidate_id") != current["id"]:
        errors.append("review belongs to an older candidate")
    moves, move_errors = source_moves(review, base, current)
    errors.extend(move_errors)
    observer_features, observer_errors = observer_reclassifications(
        base.get("model", {}),
        current.get("model", {}),
        current.get("structure", {}),
        review.get("observer_reclassifications"),
        before_index=base.get("structure"),
    )
    errors.extend(observer_errors)
    errors.extend(
        protected_errors(
            base.get("model", {}).get("implementation"),
            current.get("model", {}).get("implementation"),
            moves,
            base.get("requested_requirements", []),
            review.get("requirement_changes"),
            observer_features=observer_features,
        )
    )
    errors.extend(
        protected_captures(
            base.get("model", {}),
            current.get("model", {}),
            base.get("requested_requirements", []),
            review.get("requirement_changes"),
            observer_features=observer_features,
        )
    )
    previous_checks = base.get("verification_contract") or {}
    new_checks = current.get("verification_contract") or {}
    for name, values in previous_checks.items():
        if isinstance(values, list):
            expected = (
                [rebind_probe(v, moves) for v in values] if name == "required_probes" else values
            )
            removed = [v for v in expected if v not in (new_checks.get(name) or [])]
            if removed:
                errors.append({"weakened_verification": name, "removed": removed})
        elif values is True and new_checks.get(name) is not True:
            errors.append({"weakened_verification": name})
    for part in ("business", "state_machine", "abstraction", "probes"):
        item = review.get("decisions", {}).get(part, {})
        if (
            item.get("action") not in {"updated", "unchanged", "not_applicable"}
            or not item.get("reason", "").strip()
        ):
            errors.append("review needs action and reason: " + part)
    for symbol in changes.get("required_classification", changes["unmapped_changed_symbols"]):
        plan = current["model"].get("implementation") or {}
        if (
            symbol in plan.get("excluded", {})
            or current["structure"]["symbols"].get(symbol, {}).get("kind") == "class"
        ):
            continue
        if not review.get("excluded_symbols", {}).get(symbol, "").strip():
            errors.append("classify changed symbol outside selected graph: " + symbol)
    old = {
        c["id"]: c
        for c in [*base["acceptance"]["checks"], *base["acceptance"].get("model_checks", [])]
    }
    new = {
        c["id"]: c
        for c in [*current["acceptance"]["checks"], *current["acceptance"].get("model_checks", [])]
    }
    old.update(
        {
            "whitebox:" + k: rebind_whitebox(v, moves)
            for k, v in protected_items(base.get("whitebox")).items()
        }
    )
    new.update({"whitebox:" + k: v for k, v in protected_items(current.get("whitebox")).items()})
    allowed = set(base.get("requested_requirements", []))
    old_intent = {r["id"]: r for r in base["intent"]["requirements"]}
    new_intent = {r["id"]: r for r in current["intent"]["requirements"]}
    for rid in set(old_intent) | set(new_intent):
        if old_intent.get(rid) != new_intent.get(rid) and rid not in allowed:
            errors.append("intent changed outside recorded request: " + rid)
    # Adding counterexamples is allowed; changing/removing existing expectations
    # needs the recorded requirement change, not an explanation invented at the end.
    for cid in old:
        if old.get(cid) != new.get(cid):
            requirements = {d["requirement"] for d in (old.get(cid), new.get(cid)) if d}
            for rid in requirements:
                if (
                    rid not in allowed
                    or not review.get("requirement_changes", {}).get(rid, "").strip()
                ):
                    errors.append("acceptance changed outside recorded request: " + rid + "/" + cid)
    return errors


def inspect(root, cfg, change):
    """Build the current candidate, assess its review, and write a maintenance task.

    Inspection updates diagnostics only; acceptance advances the source baseline.
    """
    base = read(change / "baseline.json")
    current = snapshot(root, cfg, base)
    changes = impact(base, current)
    changes["errors"] = structural_errors(root, cfg, current)
    if cfg.get("source_scope", {}).get("require_symbol_classification"):
        changes["required_classification"] = changes["unmapped_implementation_symbols"]
    changes["review_errors"] = review_errors(change, base, current, changes)
    task = maintenance_task(root, cfg, base.get("source_inventory"))
    task.update(
        affected_nodes=changes["affected_nodes"],
        unmapped_symbols=changes["unmapped_implementation_symbols"],
        candidate_id=current["id"],
    )
    write(contained(root, ".stategraph/maintenance.json"), task)
    if base.get("stategraph_contract") and not current.get("stategraph_contract"):
        changes["errors"].append(
            "independent stategraph contract was removed; changing development mode does not disable observation"
        )
    if current.get("stategraph_contract"):
        changes["stategraph"] = current["stategraph_contract"]
    if base.get("discovery_path") and not cfg.get("discovery"):
        changes["errors"].append(
            "configured discovery was removed; preserve its questions and decisions"
        )
    if base.get("whitebox") and not current.get("whitebox"):
        changes["errors"].append("configured whitebox contract was removed")
    if cfg.get("discovery"):
        discovery = assess_discovery(
            current["discovery"],
            intent=current["intent"],
            model=current["model"],
            acceptance=current["acceptance"],
            previous=base.get("discovery"),
        )
        changes["discovery"] = discovery
        changes["errors"].extend({"discovery": e} for e in discovery["errors"])
        if discovery["blocked"]:
            changes["errors"].append({"unanswered_business_questions": discovery["blocked"]})
    write(change / "structure.json", current["structure"])
    write(change / "impact.json", changes)
    return base, current, changes


def verified_receipt(root, cfg, change):
    """Require a successful verification receipt for the exact candidate being accepted."""
    _, current, changes = inspect(root, cfg, change)
    errors = changes["errors"] + changes["review_errors"]
    path = change / "verification.json"
    if not path.exists():
        return current, [*errors, "run verify for this candidate first"]
    receipt = read(path)
    if not receipt.get("valid") or receipt.get("candidate_id") != current["id"]:
        errors.append("verification is failed or stale")
    if (change / "review.json").exists() and receipt.get("review_hash") != digest(
        read(change / "review.json")
    ):
        errors.append("review changed after verification")
    return current, errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["begin", "inspect", "verify", "accept", "check"])
    parser.add_argument("--root", required=True)
    parser.add_argument("--config", default="sync.json")
    parser.add_argument("--change")
    parser.add_argument("--request")
    parser.add_argument("--requirements", nargs="*", default=[])
    a = parser.parse_args()
    root = Path(a.root).absolute().resolve()
    cfg = config(root, a.config)
    active = contained(root, cfg.get("active_change", ".stategraph/active.json"))
    if a.command == "begin":
        if not a.change or not a.request:
            raise ValueError("begin requires --change and --request")
        change = contained(root, a.change)
        if change.exists():
            raise ValueError("change already exists; continue it instead of replacing the baseline")
        if (
            active.exists()
            and not (contained(root, read(active)["change"]) / "accepted.json").exists()
        ):
            raise ValueError("finish the active change before beginning another")
        initial = snapshot(root, cfg)
        if active.exists():
            previous_change = contained(root, read(active)["change"])
            if read(previous_change / "accepted.json").get("candidate_id") != initial["id"]:
                raise ValueError(
                    "previous accepted inputs changed before begin; reconcile that change instead of hiding it in a fresh baseline"
                )
        if any(not r.strip() or len(r) > 64 for r in a.requirements):
            raise ValueError("invalid requested requirement ID")
        path = contained(root, cfg["manifest"])
        if (
            path.exists()
            and binding_check(root, initial["model"], read(path))["status"] != "current"
        ):
            raise ValueError(
                "old manifest is already stale; preserve and resolve that change before beginning"
            )
        initial.update(
            request=a.request,
            requested_requirements=a.requirements,
            previous_manifest=read(path) if path.exists() else None,
        )
        write(change / "baseline.json", initial)
        write(active, {"change": a.change})
        result = {
            "valid": True,
            "status": "editing",
            "baseline_id": initial["id"],
            "change": a.change,
        }
    else:
        change = contained(root, a.change or read(active)["change"])
        if a.command == "inspect":
            _, _, result = inspect(root, cfg, change)
            result["valid"] = not (result["errors"] or result["review_errors"])
        elif a.command == "verify":
            result = verify(root, cfg, change)
        else:
            current, errors = verified_receipt(root, cfg, change)
            if a.command == "accept" and not errors:
                manifest = capture(root, current["model"])
                if snapshot(root, cfg, current)["id"] != current["id"]:
                    raise ValueError("inputs changed while accepting; inspect and verify again")
                # Manifest writes follow verified consistency, not the other way around.
                write(contained(root, cfg["manifest"]), manifest)
                accepted = {
                    "candidate_id": current["id"],
                    "build_id": manifest["build_id"],
                    "verification_hash": digest(read(change / "verification.json")),
                }
                write(change / "accepted.json", accepted)
                write(
                    contained(root, ".stategraph/source-baseline.json"), current["source_inventory"]
                )
                task = maintenance_task(root, cfg, current["source_inventory"])
                task.update(candidate_id=current["id"], status="current")
                write(contained(root, ".stategraph/maintenance.json"), task)
            elif a.command == "check":
                accepted = (
                    read(change / "accepted.json") if (change / "accepted.json").exists() else {}
                )
                if accepted.get("candidate_id") != current["id"]:
                    errors.append("change is not accepted for current inputs")
                if (change / "verification.json").exists() and accepted.get(
                    "verification_hash"
                ) != digest(read(change / "verification.json")):
                    errors.append("accepted verification differs")
                manifest_path = contained(root, cfg["manifest"])
                if (
                    not manifest_path.exists()
                    or binding_check(root, current["model"], read(manifest_path))["status"]
                    != "current"
                ):
                    errors.append("manifest does not match accepted inputs")
                elif accepted.get("build_id") != read(manifest_path).get("build_id"):
                    errors.append("manifest differs from accepted build")
            result = {
                "valid": not errors,
                "status": "current" if not errors else "needs_sync",
                "errors": errors,
                "candidate_id": current["id"],
            }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("valid") else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, ensure_ascii=False))
        raise SystemExit(2)
