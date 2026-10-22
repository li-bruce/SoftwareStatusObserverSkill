"""Run independent observations and report mapping, state and business results."""
import json
import subprocess
import sys
from datetime import datetime, timezone
try:
    from .sync_io import write, at_path
    from .behavior_model import capture, digest, read
    from .statechart_contract import validate_chart
    from .worknet_contract import validate_net
    from .execution_contract import validate_configuration
    from .whitebox_contract import assess as assess_whitebox
    from .mapping_contract import assess as assess_mapping
except ImportError:
    from sync_io import write, at_path
    from behavior_model import capture, digest, read
    from statechart_contract import validate_chart
    from worknet_contract import validate_net
    from execution_contract import validate_configuration
    from whitebox_contract import assess as assess_whitebox
    from mapping_contract import assess as assess_mapping


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


def assess_observations(model, contract, payload, modes, required_probes=(), counts=None):
    errors = []
    if counts is not None:
        counts.update(required=len(contract.get('checks', []))*len(modes), executed=0)
    if not modes or set(modes) - {"on", "off", "fault"}:
        return ["probe_modes must include actual observation checks"]
    if not contract.get("checks"):
        return ["no acceptance assertions were configured"]
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
                if counts is not None: counts['executed'] += 1
                if digest(value) != digest(check["equals"]):
                    errors.append({"requirement": check["requirement"], "check": check["id"], "mode": mode,
                                   "expected": check["equals"], "actual": value})
            except (KeyError, IndexError, TypeError, ValueError) as exc:
                errors.append({"check": check["id"], "mode": mode, "error": str(exc)})
    return errors


def verify(root, cfg, change, *, inspect, snapshot):
    base, current, changes = inspect(root, cfg, change)
    mapping_errors = changes["errors"] + changes["review_errors"]
    rule_errors, business_errors, project_errors = [], [], []
    reports = {
        'mapping': {'status': 'not_run', 'errors': mapping_errors,
                    'scope': 'Inventoried source, classified symbols, loaded declaration, required probes and actual value witnesses'},
        'state_rules': {'status': 'not_run', 'errors': rule_errors},
        'project_checks': {'status': 'not_run', 'errors': project_errors,
                           'scope': 'Configured project tests, architecture and viewer checks'},
        'business': {'status': 'not_run', 'errors': business_errors, 'assertions': {},
                     'scope': 'Authored business and whitebox expectations; this does not prove all user intent'}
    }
    if mapping_errors:
        reports['mapping']['status'] = 'failed'
        receipt = {'valid': False, 'errors': mapping_errors, 'reports': reports, 'candidate_id': current['id']}
        write(change/'verification.json', receipt)
        return receipt
    results = []
    validation_complete = False
    observation = run_command(root, cfg["observations_command"], change/"checks"/"observations.json", cfg.get("timeout_seconds", 120))
    if observation["exit_code"] != 0:
        mapping_errors.append("runtime observation command failed")
    else:
        try:
            payload = json.loads(observation["stdout"])
            if payload.get("build_id") != capture(root, current["model"])["build_id"]:
                mapping_errors.append("runtime observations belong to another build")
            # Runtime declarations and probe identity are mapping questions.
            # The expected business outcome is checked independently below.
            if current['model'].get('machine'):
                validate_chart(current['model'], payload.get('machine') or {})
            for wanted in cfg.get('required_runtime_probes', []):
                runs = [r for r in payload.get('runs', []) if r.get('case') == wanted['case'] and r.get('mode') == 'on']
                if len(runs) != 1 or not any(all(e.get(k) == v for k, v in wanted.items() if k != 'case') for e in runs[0].get('events', [])):
                    mapping_errors.append({'missing_runtime_probe': wanted})
            witnesses = assess_mapping(payload, required=cfg.get('require_mapping_witnesses', False))
            mapping_errors.extend(witnesses['errors'])
            reports['mapping']['witnesses'] = witnesses['checks']
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
                    for state in configurations:
                        try: validate_configuration(current['model'], state)
                        except (ValueError, KeyError, TypeError) as exc:
                            rule_errors.append({'case': run['case'], 'error': str(exc)})
            business_errors += assess_observations({}, current["acceptance"], payload,
                cfg.get("probe_modes", ["on", "off", "fault"]), counts=reports['business']['assertions'])
            if current.get("whitebox"):
                report = assess_whitebox(current["whitebox"], current["model"], payload,
                                        capture(root, current["model"])["build_id"])
                write(change/"checks"/"whitebox.json", report)
                business_errors.extend(report["errors"])
            validation_complete = True
        except (ValueError, TypeError, KeyError) as exc:
            mapping_errors.append("invalid runtime observations: " + str(exc))
    for i, command in enumerate(cfg.get("test_commands", [])):
        result = run_command(root, command, change/"checks"/f"test-{i}.json", cfg.get("timeout_seconds", 120))
        results.append({"argv": command, "exit_code": result["exit_code"]})
        if result["exit_code"] != 0: project_errors.append("project test failed: " + str(command))
    after = snapshot(root, cfg, current)
    if after["id"] != current["id"]: mapping_errors.append("candidate changed while checks were running")
    for report in reports.values():
        report['status'] = 'failed' if report['errors'] else 'passed' if validation_complete else 'not_run'
    reports['project_checks']['status'] = 'failed' if project_errors else 'passed' if results else 'not_run'
    errors = mapping_errors + rule_errors + business_errors + project_errors
    receipt = {"valid": not errors, "errors": errors, "candidate_id": current["id"],
        'reports': reports,
        "review_hash": digest(read(change/"review.json")), "observations_hash": digest(observation),
        "tests": results, "checked_at": datetime.now(timezone.utc).isoformat(),
        "meaning": "Selected structural consistency and explicit observed requirements; not arbitrary semantic equivalence."}
    write(change/"verification.json", receipt)
    return receipt


