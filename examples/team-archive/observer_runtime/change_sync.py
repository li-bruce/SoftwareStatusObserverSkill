"""Checked coding iterations: business intent + static slice + runtime witnesses.

Nonzero check blocks completion when integrated into the project's test/CI gate.
This is a consistency/regression mechanism, not a proof of arbitrary semantics.
Commands are explicit argv arrays from reviewed project configuration, never shell.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone
try:
    from .behavior_model import capture, check as binding_check, contained, digest, read, validate
    from .code_structure import scan, enrich, key
    from .statechart_contract import validate_chart
    from .worknet_contract import validate_net
    from .execution_contract import validate_execution_graph, validate_configuration
    from .requirements_dialogue import assess as assess_discovery
    from .whitebox_contract import static_errors as whitebox_static, assess as assess_whitebox, protected_items
except ImportError:
    from behavior_model import capture, check as binding_check, contained, digest, read, validate
    from code_structure import scan, enrich, key
    from statechart_contract import validate_chart
    from worknet_contract import validate_net
    from execution_contract import validate_execution_graph, validate_configuration
    from requirements_dialogue import assess as assess_discovery
    from whitebox_contract import static_errors as whitebox_static, assess as assess_whitebox, protected_items


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")


def config(root, name):
    result = read(contained(root, name))
    for field in ("model", "manifest", "code_files", "watch_files", "acceptance", "observations_command"):
        if not result.get(field): raise ValueError("missing sync config: " + field)
    for command in [result["observations_command"], *result.get("test_commands", [])]:
        if not isinstance(command, list) or not command or not all(isinstance(v, str) for v in command):
            raise ValueError("check commands must be nonempty argv arrays")
    result["config_path"] = name
    return result


def snapshot(root, cfg, previous=None):
    model = read(contained(root, cfg["model"]))
    intent = read(contained(root, model["intent"]))
    acceptance = read(contained(root, cfg["acceptance"]))
    paths = sorted(set([cfg["config_path"], cfg["model"], model["intent"], cfg["acceptance"],
                        *model["source_files"], *cfg["code_files"], *cfg["watch_files"],
                        *([cfg['discovery']] if cfg.get('discovery') else []),
                        *([cfg['whitebox']] if cfg.get('whitebox') else [])]) - {cfg["manifest"]})
    files = {}
    for name in paths:
        path = contained(root, name)
        files[name] = digest(path.read_bytes()) if path.is_file() else None
    index = scan(root, cfg["code_files"], (previous or {}).get("structure"))
    tools = {name: digest((Path(__file__).parent/name).read_bytes())
             for name in ("change_sync.py", "code_structure.py", "behavior_model.py", "statechart_contract.py", "worknet_contract.py", "execution_contract.py", "requirements_dialogue.py", "whitebox_contract.py")}
    return {"id": digest({"files": files, "tools": tools}), "files": files, "tools": tools, "model": model, "intent": intent,
            "acceptance": acceptance, "structure": index,
            "whitebox": read(contained(root,cfg["whitebox"])) if cfg.get("whitebox") else None,
            "discovery_path":cfg.get('discovery'),
            "discovery": read(contained(root,cfg['discovery'])) if cfg.get('discovery') else None}


def at_path(value, path):
    for field in path:
        if isinstance(value, list) and isinstance(field, str):
            selected = [v for v in value if isinstance(v, dict) and v.get("id") == field]
            if len(selected) != 1: raise ValueError("missing unique node ID: " + field)
            value = selected[0]
        else:
            value = value[field]
    return value


def structural_errors(root, cfg, snap):
    errors = list(snap["structure"]["errors"])
    errors.extend({"missing_file": p} for p, sha in snap["files"].items() if sha is None)
    if not set(cfg["code_files"]) <= set(snap["model"]["source_files"]):
        errors.append("selected code files must be included in the bound source_files")
    for p, u in snap["structure"]["units"].items():
        if u["file_hash"] != snap["files"].get(p): errors.append("file changed during scan: " + p)
    try:
        validate(root, snap["model"])
        capture(root, snap["model"])  # Resolve all declared source symbols; do not write a manifest.
        if snap["model"].get("machine"): validate_chart(snap["model"])
        if snap["model"].get("worknet"): validate_net(snap["model"]["worknet"])
        validate_execution_graph(snap['model'])
        projected = enrich(snap["model"], snap["structure"], cfg.get("slice_depth", 1))
        if digest(projected) != digest(snap["model"]):
            errors.append("static projection is stale: rebuild model with code_structure.enrich")
    except (OSError, ValueError, KeyError, SyntaxError) as exc:
        errors.append(str(exc))
    ids = {n["id"] for n in snap["model"]["nodes"]}
    sites = []
    for s in snap["structure"]["symbols"].values():
        for c in s["calls"]:
            if c["expression"] in cfg.get("probe_callees", ["trace.record"]) and c.get("literal_pair"):
                node, phase = c["literal_pair"]
                sites.append({"symbol": s["id"], "node": node, "phase": phase})
                if node not in ids: errors.append("probe references missing node: " + node)
    for required in cfg.get("required_probes", []):
        if not any(all(site.get(k) == v for k,v in required.items()) for site in sites):
            errors.append({"missing_required_probe": required})
    checks = snap["acceptance"].get("checks", [])
    known = {r["id"] for r in snap["intent"]["requirements"]}
    if snap.get("whitebox"):
        errors.extend(whitebox_static(snap["whitebox"], snap["model"], snap["structure"], known))
    if not checks or len({c["id"] for c in checks}) != len(checks):
        errors.append("acceptance needs uniquely identified checks")
    for c in checks:
        if c.get("requirement") not in known or not c.get("case") or not isinstance(c.get("path"), list) or "equals" not in c:
            errors.append({"invalid_acceptance_check": c.get("id")})
    model_checks = snap["acceptance"].get("model_checks", [])
    if len({c["id"] for c in [*checks, *model_checks]}) != len(checks)+len(model_checks):
        errors.append("acceptance and model check IDs must be unique")
    for c in model_checks:
        try:
            if c.get("requirement") not in known: raise ValueError("unknown requirement")
            actual = at_path(snap["model"], c["path"])
            if digest(actual) != digest(c["equals"]):
                errors.append({"model_claim_mismatch": c["id"], "requirement": c["requirement"],
                               "expected": c["equals"], "actual": actual})
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            errors.append({"invalid_model_check": c.get("id"), "error": str(exc)})
    watched = set(snap["files"])
    for command in [cfg["observations_command"], *cfg.get("test_commands", [])]:
        for arg in command[1:]:
            if arg.endswith(".py") and (Path(arg).is_absolute() or arg not in watched):
                errors.append("check script must be a watched project-relative file: " + arg)
    return errors


def impact(base, current):
    old, new = base["structure"]["symbols"], current["structure"]["symbols"]
    changed = sorted(k for k in set(old) | set(new) if old.get(k, {}).get("ast_hash") != new.get(k, {}).get("ast_hash"))
    affected = set(changed)
    # Reverse static callers are potentially affected, not proof of runtime reachability.
    edges = base["structure"]["edges"] + current["structure"]["edges"]
    while True:
        callers = {e["from"] for e in edges if e["to"] in affected}
        if callers <= affected: break
        affected |= callers
    nodes = {n["id"]: n for m in (base["model"], current["model"]) for n in m["nodes"]}
    mapped = {key(n["source"]["path"], n["source"]["symbol"]) for n in nodes.values() if n.get("source")}
    affected_nodes = {n["id"] for n in nodes.values() if n.get("source") and key(n["source"]["path"], n["source"]["symbol"]) in affected}
    while True:
        parents = {nodes[n]["parent"] for n in affected_nodes if nodes[n].get("parent") in nodes}
        if parents <= affected_nodes: break
        affected_nodes |= parents
    file_changes = sorted(p for p in set(base["files"]) | set(current["files"]) if base["files"].get(p) != current["files"].get(p))
    return {"candidate_id": current["id"], "changed_files": file_changes, "changed_symbols": changed,
            "affected_callers": sorted(affected-set(changed)), "affected_nodes": sorted(affected_nodes),
            "unmapped_changed_symbols": sorted(set(changed)-mapped),
            "changed_requirements": [r for r in current["intent"]["requirements"] if r not in base["intent"]["requirements"]],
            "unresolved_call_count": len(current["structure"]["unresolved"]),
            "meaning": "Potential impact plus authored abstraction mapping; semantic truth still needs contract and runtime checks."}


def review_errors(change, base, current, changes):
    errors = []
    path = change / "review.json"
    if not path.exists(): return ["missing review.json for this candidate"]
    review = read(path)
    if review.get("candidate_id") != current["id"]: errors.append("review belongs to an older candidate")
    for part in ("business", "state_machine", "abstraction", "probes"):
        item = review.get("decisions", {}).get(part, {})
        if item.get("action") not in {"updated", "unchanged", "not_applicable"} or not item.get("reason", "").strip():
            errors.append("review needs action and reason: " + part)
    for symbol in changes["unmapped_changed_symbols"]:
        if not review.get("excluded_symbols", {}).get(symbol, "").strip():
            errors.append("classify changed symbol outside selected graph: " + symbol)
    old = {c["id"]: c for c in [*base["acceptance"]["checks"], *base["acceptance"].get("model_checks", [])]}
    new = {c["id"]: c for c in [*current["acceptance"]["checks"], *current["acceptance"].get("model_checks", [])]}
    old.update({"whitebox:" + k: v for k, v in protected_items(base.get("whitebox")).items()})
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
                if rid not in allowed or not review.get("requirement_changes", {}).get(rid, "").strip():
                    errors.append("acceptance changed outside recorded request: " + rid + "/" + cid)
    return errors


def inspect(root, cfg, change):
    base = read(change / "baseline.json")
    current = snapshot(root, cfg, base)
    changes = impact(base, current)
    changes["errors"] = structural_errors(root, cfg, current)
    changes["review_errors"] = review_errors(change, base, current, changes)
    if base.get('discovery_path') and not cfg.get('discovery'):
        changes['errors'].append('configured discovery was removed; preserve its questions and decisions')
    if base.get("whitebox") and not current.get("whitebox"):
        changes["errors"].append("configured whitebox contract was removed")
    if cfg.get('discovery'):
        discovery=assess_discovery(current['discovery'],intent=current['intent'],model=current['model'],
                                  acceptance=current['acceptance'],previous=base.get('discovery'))
        changes['discovery']=discovery
        changes['errors'].extend({'discovery':e} for e in discovery['errors'])
        if discovery['blocked']:changes['errors'].append({'unanswered_business_questions':discovery['blocked']})
    write(change / "structure.json", current["structure"])
    write(change / "impact.json", changes)
    return base, current, changes


def run_command(root, command, dest, timeout):
    # Configuration must be reviewed as normal project test commands before use.
    # Keep sync.json portable while using the active virtual environment.
    argv = [sys.executable if value == "{python}" else value for value in command]
    try:
        result = subprocess.run(argv, cwd=root, capture_output=True, text=True, encoding="utf-8",
                                errors="replace", timeout=timeout, shell=False)
        out = {"argv": command, "exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
    except (OSError, subprocess.TimeoutExpired) as exc:
        out = {"argv": command, "exit_code": -1, "stdout": "", "stderr": str(exc)}
    write(dest, out)
    return out


def assess_observations(model, contract, payload, modes, required_probes=()):
    errors = []
    if model.get("machine"):
        try: validate_chart(model, payload.get("machine")) if payload.get("machine") else errors.append("runtime machine definition missing")
        except (ValueError, KeyError, TypeError) as exc: errors.append(str(exc))
    runs = payload.get("runs", [])
    identities = [(r.get("case"), r.get("mode")) for r in runs]
    if len(identities) != len(set(identities)): errors.append("duplicate runtime case/mode")
    for wanted in required_probes:
        matches = [r for r in runs if r.get("case") == wanted["case"] and r.get("mode") == "on"]
        if len(matches) != 1 or not any(all(e.get(k) == v for k,v in wanted.items() if k != "case") for e in matches[0].get("events", [])):
            errors.append({"missing_runtime_probe": wanted})
    for check in contract["checks"]:
        for mode in modes:
            matches = [r for r in runs if r.get("case") == check["case"] and r.get("mode") == mode]
            try:
                if len(matches) != 1: raise ValueError("missing unique case/mode")
                value = at_path(matches[0]["observations"], check["path"])
                if digest(value) != digest(check["equals"]):
                    errors.append({"requirement": check["requirement"], "check": check["id"], "mode": mode,
                                   "expected": check["equals"], "actual": value})
            except (KeyError, IndexError, TypeError, ValueError) as exc:
                errors.append({"check": check["id"], "mode": mode, "error": str(exc)})
    return errors


def verify(root, cfg, change):
    base, current, changes = inspect(root, cfg, change)
    errors = changes["errors"] + changes["review_errors"]
    if errors: return {"valid": False, "errors": errors, "candidate_id": current["id"]}
    results = []
    observation = run_command(root, cfg["observations_command"], change/"checks"/"observations.json", cfg.get("timeout_seconds", 120))
    if observation["exit_code"] != 0:
        errors.append("runtime observation command failed")
    else:
        try:
            payload = json.loads(observation["stdout"])
            if payload.get("build_id") != capture(root, current["model"])["build_id"]:
                errors.append("runtime observations belong to another build")
            if current['model'].get('worknet'):
                if not payload.get('worknet'):raise ValueError('runtime worknet definition is required')
                validate_net(current['model']['worknet'],payload['worknet'])
                for run in payload.get('runs',[]):
                    if run.get('case') in cfg.get('required_worknet_cases',[]) and not run.get('worknet'):
                        raise ValueError('missing actual worknet snapshot: '+run['case'])
                    validate_net(current['model']['worknet'],snapshot=run.get('worknet'))
            if current['model'].get('machine',{}).get('execution'):
                for run in payload.get('runs',[]):
                    configurations=run.get('configurations',[])
                    if run.get('case') in cfg.get('required_execution_cases',[]) and not configurations:
                        raise ValueError('missing actual internal states: '+run['case'])
                    identities=[(c.get('attempt'),c.get('param_version')) for c in configurations]
                    if len(identities)!=len(set(identities)):raise ValueError('duplicate execution instance')
                    for state in configurations:validate_configuration(current['model'],state)
            errors += assess_observations(current["model"], current["acceptance"], payload,
                cfg.get("probe_modes", ["on", "off", "fault"]), cfg.get("required_runtime_probes", []))
            if current.get("whitebox"):
                report = assess_whitebox(current["whitebox"], current["model"], payload,
                                        capture(root, current["model"])["build_id"])
                write(change/"checks"/"whitebox.json", report)
                errors.extend(report["errors"])
        except (ValueError, TypeError, KeyError) as exc:
            errors.append("invalid runtime observations: " + str(exc))
    for i, command in enumerate(cfg.get("test_commands", [])):
        result = run_command(root, command, change/"checks"/f"test-{i}.json", cfg.get("timeout_seconds", 120))
        results.append({"argv": command, "exit_code": result["exit_code"]})
        if result["exit_code"] != 0: errors.append("project test failed: " + str(command))
    after = snapshot(root, cfg, current)
    if after["id"] != current["id"]: errors.append("candidate changed while checks were running")
    receipt = {"valid": not errors, "errors": errors, "candidate_id": current["id"],
        "review_hash": digest(read(change/"review.json")), "observations_hash": digest(observation),
        "tests": results, "checked_at": datetime.now(timezone.utc).isoformat(),
        "meaning": "Selected structural consistency and explicit observed requirements; not arbitrary semantic equivalence."}
    write(change/"verification.json", receipt)
    return receipt


def verified_receipt(root, cfg, change):
    _, current, changes = inspect(root, cfg, change)
    errors = changes["errors"] + changes["review_errors"]
    path = change/"verification.json"
    if not path.exists(): return current, [*errors, "run verify for this candidate first"]
    receipt = read(path)
    if not receipt.get("valid") or receipt.get("candidate_id") != current["id"]:
        errors.append("verification is failed or stale")
    if (change/"review.json").exists() and receipt.get("review_hash") != digest(read(change/"review.json")):
        errors.append("review changed after verification")
    return current, errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["begin", "inspect", "verify", "accept", "check"])
    parser.add_argument("--root", required=True); parser.add_argument("--config", default="sync.json")
    parser.add_argument("--change"); parser.add_argument("--request"); parser.add_argument("--requirements", nargs="*", default=[])
    a = parser.parse_args(); root = Path(a.root).absolute().resolve(); cfg = config(root, a.config)
    active = contained(root, cfg.get("active_change", ".stategraph/active.json"))
    if a.command == "begin":
        if not a.change or not a.request: raise ValueError("begin requires --change and --request")
        change = contained(root, a.change)
        if change.exists(): raise ValueError("change already exists; continue it instead of replacing the baseline")
        if active.exists() and not (contained(root, read(active)["change"])/"accepted.json").exists():
            raise ValueError("finish the active change before beginning another")
        initial = snapshot(root, cfg)
        if active.exists():
            previous_change = contained(root, read(active)["change"])
            if read(previous_change/"accepted.json").get("candidate_id") != initial["id"]:
                raise ValueError("previous accepted inputs changed before begin; reconcile that change instead of hiding it in a fresh baseline")
        if any(not r.strip() or len(r)>64 for r in a.requirements):
            raise ValueError("invalid requested requirement ID")
        path = contained(root, cfg["manifest"])
        if path.exists() and binding_check(root, initial["model"], read(path))["status"] != "current":
            raise ValueError("old manifest is already stale; preserve and resolve that change before beginning")
        initial.update(request=a.request, requested_requirements=a.requirements,
                       previous_manifest=read(path) if path.exists() else None)
        write(change/"baseline.json", initial); write(active, {"change": a.change})
        result = {"valid": True, "status": "editing", "baseline_id": initial["id"], "change": a.change}
    else:
        change = contained(root, a.change or read(active)["change"])
        if a.command == "inspect":
            _, _, result = inspect(root, cfg, change)
            result["valid"] = not (result["errors"] or result["review_errors"])
        elif a.command == "verify": result = verify(root, cfg, change)
        else:
            current, errors = verified_receipt(root, cfg, change)
            if a.command == "accept" and not errors:
                manifest = capture(root, current["model"])
                if snapshot(root, cfg, current)["id"] != current["id"]:
                    raise ValueError("inputs changed while accepting; inspect and verify again")
                # Manifest writes follow verified consistency, not the other way around.
                write(contained(root, cfg["manifest"]), manifest)
                accepted = {"candidate_id": current["id"], "build_id": manifest["build_id"],
                            "verification_hash": digest(read(change/"verification.json"))}
                write(change/"accepted.json", accepted)
            elif a.command == "check":
                accepted = read(change/"accepted.json") if (change/"accepted.json").exists() else {}
                if accepted.get("candidate_id") != current["id"]: errors.append("change is not accepted for current inputs")
                if (change/"verification.json").exists() and accepted.get("verification_hash") != digest(read(change/"verification.json")):
                    errors.append("accepted verification differs")
                manifest_path = contained(root, cfg["manifest"])
                if not manifest_path.exists() or binding_check(root, current["model"], read(manifest_path))["status"] != "current":
                    errors.append("manifest does not match accepted inputs")
                elif accepted.get("build_id") != read(manifest_path).get("build_id"):
                    errors.append("manifest differs from accepted build")
            result = {"valid": not errors, "status": "current" if not errors else "needs_sync", "errors": errors,
                      "candidate_id": current["id"]}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("valid") else 1


if __name__ == "__main__":
    try: raise SystemExit(main())
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, ensure_ascii=False)); raise SystemExit(2)
