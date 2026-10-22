"""Project configuration and independently inventoried candidate snapshots."""
from pathlib import Path
try:
    from .behavior_model import read, contained, digest
    from .code_structure import scan
    from .bo_sync import source_inventory
except ImportError:
    from behavior_model import read, contained, digest
    from code_structure import scan
    from bo_sync import source_inventory


def config(root, name):
    result = read(contained(root, name))
    for field in ("model", "manifest", "code_files", "watch_files", "acceptance", "observations_command"):
        if not result.get(field): raise ValueError("missing sync config: " + field)
    for command in [result["observations_command"], *result.get("test_commands", [])]:
        if not isinstance(command, list) or not command or not all(isinstance(v, str) for v in command):
            raise ValueError("check commands must be nonempty argv arrays")
    modes = result.get("probe_modes", ["on", "off", "fault"])
    if not isinstance(modes, list) or not modes or len(set(modes)) != len(modes) or set(modes) - {"on", "off", "fault"}:
        raise ValueError("probe_modes must be a nonempty unique list of on/off/fault")
    stategraph = result.get("stategraph")
    if stategraph is not None:
        if not isinstance(stategraph, dict) or not stategraph.get("module"):
            raise ValueError("stategraph requires an independent module")
        if stategraph.get("execution_mode") not in {"drive", "observe"}:
            raise ValueError("stategraph execution_mode must be drive or observe")
        if stategraph.get("development_mode") not in {"guided", "observe"}:
            raise ValueError("stategraph development_mode must be guided or observe")
        if stategraph.get("development_mode") == "observe" and (
                stategraph.get("decision_source") != "user" or not stategraph.get("decision", "").strip()):
            raise ValueError("observation-led development needs the user's explicit choice; silence is not opt-out")
        if not result.get("required_probes") or not result.get("required_runtime_probes"):
            raise ValueError("both development modes require static and runtime probe checks")
        if not result.get('test_commands'):
            raise ValueError('stategraph projects require at least one independent test command')
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
    inventory = source_inventory(root, cfg) if cfg.get('source_scope') or cfg.get('stategraph') else {'files': {}, 'excluded': {}}
    paths = sorted(set(paths) | set(inventory['files']))
    files = {}
    for name in paths:
        path = contained(root, name)
        files[name] = digest(path.read_bytes()) if path.is_file() else None
    index = scan(root, cfg["code_files"], (previous or {}).get("structure"))
    tools = {path.name: digest(path.read_bytes()) for path in sorted(Path(__file__).parent.glob('*.py'))}
    return {"id": digest({"files": files, "tools": tools}), "files": files, "tools": tools, "model": model, "intent": intent,
            "acceptance": acceptance, "structure": index, "source_inventory": inventory,
            'verification_contract': {name: cfg.get(name, ['on','off','fault'] if name == 'probe_modes' else None) for name in
                ('probe_modes','test_commands','required_runtime_probes','required_probes','required_execution_cases','require_mapping_witnesses')},
            "whitebox": read(contained(root,cfg["whitebox"])) if cfg.get("whitebox") else None,
            "stategraph_contract":cfg.get('stategraph'),
            "discovery_path":cfg.get('discovery'),
            "discovery": read(contained(root,cfg['discovery'])) if cfg.get('discovery') else None}


