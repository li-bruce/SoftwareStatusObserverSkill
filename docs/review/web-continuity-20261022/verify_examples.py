"""Revalidate the active repair stage; never replace its baseline or expectations."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent


def run(project, script, command, label):
    result = subprocess.run([sys.executable, '-B', '-X', 'utf8', str(script), command,
                             '--root', str(project)], cwd=ROOT, capture_output=True,
                            text=True, encoding='utf-8', timeout=360)
    (OUT / (label + '.json')).write_text(json.dumps({
        'command': [str(script.relative_to(ROOT)), command, '--root', str(project.relative_to(ROOT))],
        'exit_code': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr
    }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return result, json.loads(result.stdout)


def main():
    label = sys.argv[1]
    failed = False
    for name, runtime in [('delivery','observer_generated/runtime'), ('team-archive','observer_runtime')]:
        project = ROOT / 'examples' / name
        script = project / runtime / 'change_sync.py'
        change = project / '.stategraph/web-continuity'
        assert (change / 'baseline.json').exists()
        _, impact = run(project, script, 'inspect', label + '-' + name + '-inspect')
        previous = json.loads((project / '.stategraph/assessment-fixes/review.json').read_text(encoding='utf-8'))
        missing = set(impact.get('required_classification', [])) - set(previous['excluded_symbols'])
        if missing: raise ValueError('Classify newly introduced symbols before reviewing: ' + str(missing))
        review = {
            'candidate_id': impact['candidate_id'],
            'decisions': {
                'business': {'action':'unchanged','reason':'保留全部已确认需求、业务预期和白盒断言；对话确认仍在开发工具中进行，Web 只读展示。'},
                'state_machine': {'action':'unchanged','reason':'保留完整状态声明、执行引擎和严格校验；关闭 Web 不影响业务执行或 Python 查询。'},
                'abstraction': {'action':'updated','reason':'保留图节点和源码绑定；从同一需求记录投影设计图，当前对话聚焦只改变展示；类型填充和核心高亮。'},
                'probes': {'action':'unchanged','reason':'未修改探针和采集约定；Web 控制与采集独立，原 on/off/fault 和实际值投影检查全部保留。'}
            },
            'excluded_symbols': previous['excluded_symbols'], 'requirement_changes': {}
        }
        (change / 'review.json').write_text(json.dumps(review, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        result, receipt = run(project, script, 'verify', label + '-' + name + '-verify')
        print(json.dumps({'example':name,'exit_code':result.returncode,'valid':receipt['valid'],
                          'reports':receipt.get('reports'),'errors':receipt.get('errors')}, ensure_ascii=False), flush=True)
        if result.returncode:
            failed = True
            continue
        for command in ('accept', 'check'):
            result, response = run(project, script, command, label + '-' + name + '-' + command)
            print(json.dumps({'example':name,'command':command,**response}, ensure_ascii=False), flush=True)
            if result.returncode:
                failed = True
                break
    if failed: raise SystemExit(1)


if __name__ == '__main__': main()
