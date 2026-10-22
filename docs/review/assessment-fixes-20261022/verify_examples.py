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
        change = project / '.stategraph/assessment-fixes'
        assert (change / 'baseline.json').exists()
        _, impact = run(project, script, 'inspect', label + '-' + name + '-inspect')
        previous = json.loads((project / '.stategraph/refactor-round1/review.json').read_text(encoding='utf-8'))
        missing = set(impact.get('required_classification', [])) - set(previous['excluded_symbols'])
        if missing: raise ValueError('Classify newly introduced symbols before reviewing: ' + str(missing))
        review = {
            'candidate_id': impact['candidate_id'],
            'decisions': {
                'business': {'action':'unchanged','reason':'保留已确认需求、业务预期和白盒断言；本轮只修复评估中的 R1–R6。'},
                'state_machine': {'action':'updated','reason':'执行器在加载前核对定义、引擎版本及 guard；统一查询修复锁顺序，运行错误保留事实并报告。'},
                'abstraction': {'action':'updated','reason':'保留图节点和绑定；重新生成实际源码投影，新增受保护的场景及核心字段映射清单。'},
                'probes': {'action':'updated','reason':'保留原事件与对照，绑定每个实际场景投影及公共导出；补齐运行帧、有界默认文件输出和监视器写冲突恢复。'}
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
