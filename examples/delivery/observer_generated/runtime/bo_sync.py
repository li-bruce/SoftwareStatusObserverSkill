"""Discover project changes independently of the graph and emit an internal AI task.

Call `scan` after edits, or `watch` from a project-local editor integration.
This discovers work; it does not claim to invoke an arbitrary editor's AI.
"""
import argparse
import fnmatch
import hashlib
import json
from pathlib import Path
import time

IGNORED = {'.git', '.venv', 'node_modules', '__pycache__', '.stategraph',
           '.validation', '.planning', '.release', '.pytest_cache', 'dist'}


def source_inventory(root, cfg):
    root = Path(root).resolve()
    scope = cfg.get('source_scope', {})
    if not isinstance(scope, dict):
        raise ValueError('source scope must be an object')
    exclusions = scope.get('exclude', {})
    if not isinstance(exclusions, dict) or any(not isinstance(reason, str) or not reason.strip() for reason in exclusions.values()):
        raise ValueError('each source exclusion needs a reason')
    roots = scope.get('roots', ['.'])
    if not isinstance(roots, list) or not roots or any(not isinstance(p, str) or not p.strip() for p in roots):
        raise ValueError('source scope needs nonempty project-relative roots')
    files, excluded = {}, {}
    for prefix in roots:
        start = (root / prefix).resolve()
        if not start.is_relative_to(root): raise ValueError('source scope escapes project')
        if not start.exists(): raise ValueError('source scope is missing: ' + prefix)
        paths = [start] if start.is_file() else start.rglob('*.py')
        for path in paths:
            name = path.relative_to(root).as_posix()
            if any(part in IGNORED for part in Path(name).parts): continue
            if path.is_symlink() or not path.resolve().is_relative_to(root):
                raise ValueError('source symlink escapes declared project: ' + name)
            reason = next((v for pattern, v in exclusions.items() if fnmatch.fnmatchcase(name, pattern)), None)
            if reason:
                excluded[name] = reason
            else:
                files[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {'files': dict(sorted(files.items())), 'excluded': dict(sorted(excluded.items()))}


def maintenance_task(root, cfg, previous=None):
    current = source_inventory(root, cfg)
    old = (previous or {}).get('files', {})
    changed = sorted(p for p in set(old) | set(current['files']) if old.get(p) != current['files'].get(p))
    registered = set(cfg.get('code_files', []))
    if not cfg.get('source_scope') and not cfg.get('stategraph'):
        registered |= set(cfg.get('watch_files', []))
    unregistered = sorted(set(current['files']) - registered)
    digest = hashlib.sha256(json.dumps(current, sort_keys=True).encode()).hexdigest()
    return {'schema': 'bo-maintenance/v1', 'source_id': digest, 'inventory': current,
            'changed_files': changed, 'unregistered_files': unregistered,
            'status': 'needs_update' if changed or unregistered else 'current',
            'internal_prompt': '核查列出的实现变化；更新受影响业务抽象、状态、函数/参数映射和探针。'
                '新增入口不能因不在旧图中而忽略。完成局部投影及实际场景验证后运行项目收尾检查。'
                '不要要求用户填写观测文件；仅在新的业务歧义出现时提问。',
            'ai_invocation': 'host_or_coding_agent_required'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['scan', 'watch'])
    parser.add_argument('--root', default='.')
    parser.add_argument('--config', default='sync.json')
    parser.add_argument('--interval', type=float, default=1)
    args = parser.parse_args()
    root = Path(args.root).resolve()
    target = root / '.stategraph/maintenance.json'
    previous, last = None, None
    baseline = root / '.stategraph/source-baseline.json'
    while True:
        cfg_path = (root / args.config).resolve()
        if not cfg_path.is_relative_to(root): raise ValueError('config escapes project')
        try:
            cfg = json.loads(cfg_path.read_text(encoding='utf-8-sig'))
            # Reading a detected change never acknowledges it. Only accept updates
            # this baseline after the full verification gate succeeds.
            previous = json.loads(baseline.read_text(encoding='utf-8')) if baseline.exists() else None
            value = maintenance_task(root, cfg, previous)
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
            # Editors can briefly leave configuration incomplete. Keep watching,
            # report the missing evidence, and retry without replacing the baseline.
            value = {'schema': 'bo-maintenance/v1', 'status': 'needs_update',
                     'errors': [str(error)], 'inventory': None,
                     'internal_prompt': '修复源码扫描配置后重新扫描；当前不能判定映射完整。',
                     'ai_invocation': 'host_or_coding_agent_required'}
        # Registration and an accepted baseline can change without changing file
        # bytes. Publish those task transitions too, rather than leaving stale work.
        task_id = hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()
        if task_id != last:
            target.parent.mkdir(exist_ok=True)
            temporary = target.with_suffix('.tmp')
            temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
            temporary.replace(target)
            print(json.dumps(value, ensure_ascii=False), flush=True)
            last = task_id
        if args.command == 'scan': return 1 if value.get('errors') else 0
        time.sleep(max(.1, args.interval))


if __name__ == '__main__':
    raise SystemExit(main())
