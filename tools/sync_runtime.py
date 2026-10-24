"""Copy maintained Skill sources to shipped examples; never touch project config/data."""
from pathlib import Path
import shutil
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills/vibelens'
CORE = ('bo_contracts.py', 'execution_contract.py')


def sync():
    sys.path.insert(0, str(SKILL/'scripts'))
    from bo_upgrade import apply, bridge_source
    for project, runtime in [('delivery', 'observer_generated/runtime'), ('team-archive', 'observer_runtime')]:
        root = ROOT / 'examples' / project
        for source in (SKILL / 'scripts').glob('*.py'):
            if source.name in ('bo_stategraph.py', *CORE):
                (root/runtime/source.name).write_bytes(bridge_source(source.name))
            else:
                shutil.copyfile(source, root / runtime / source.name)
        targets = ['integrations/bo_view', 'observer_generated/static'] if project == 'delivery' else ['static/graph']
        for target in targets:
            for source in (SKILL / 'assets/stategraph-viewer').iterdir():
                if source.is_file(): shutil.copyfile(source, root / target / source.name)
        tests = root / ('tests' if project == 'delivery' else 'tooling')
        for name in ('test_recording.py', 'test_stategraph_module.py', 'test_recorded_views.mjs'):
            shutil.copyfile(ROOT / 'tools' / name, tests / name)
    for project in ('delivery', 'team-archive', 'python-modes'):
        target = ROOT / 'examples' / project / 'bo_stategraph'
        target.mkdir(exist_ok=True)
        shutil.copyfile(SKILL / 'scripts/bo_stategraph.py', target / '__init__.py')
        for name in CORE: shutil.copyfile(SKILL / 'scripts' / name, target / name)
    for project, runtime, viewers in [('delivery','observer_generated/runtime',['integrations/bo_view','observer_generated/static']),
                                     ('team-archive','observer_runtime',['static/graph'])]:
        root=ROOT/'examples'/project
        result=apply(root,runtime=runtime,viewers=viewers)
        origin={'source':'VibeLens/skills/vibelens',
                'release':result['release'],'protocols':result['protocols'],
                'manifest':('../../' if project=='delivery' else '../')+'bo_stategraph/runtime-version.json'}
        (root/runtime/'origin.json').write_text(json.dumps(origin,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    for source,target in [('bo_observer/adapters/javascript/bo_runtime.mjs','bo_runtime.mjs'),
        ('bo_observer/adapters/python/bo_probe.py','bo_probe.py'),('bo_observer/adapters/python/bo_executor.py','bo_executor.py'),
        ('bo_contracts.py','bo_contracts.py'),('execution_contract.py','execution_contract.py')]:
        shutil.copyfile(SKILL/'scripts'/source,ROOT/'examples/multilanguage/bo_stategraph'/target)
    print('Runtime and viewer sources copied; project definitions and personal files preserved.')


if __name__ == '__main__':
    sync()
