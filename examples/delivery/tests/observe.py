"""Emit observations by executing the real program, not by consulting acceptance.json."""
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from observer_generated.runtime.behavior_model import capture

model=json.loads((ROOT/'observer_generated/behavior.json').read_text(encoding='utf-8'))
loaded=capture(ROOT,model)  # Bind before importing the business modules.
from app.workflow import definition
from tests.scenarios import CASES,exercise


def observe():
    runs=[exercise(case,model,loaded['build_id'],mode) for case in CASES for mode in ('on','off','fault')]
    if capture(ROOT,model)['build_id']!=loaded['build_id']:
        raise RuntimeError('source changed during execution')
    return {'build_id':loaded['build_id'],'machine':definition(),'runs':runs}


if __name__=='__main__':
    print(json.dumps(observe(),ensure_ascii=False))
