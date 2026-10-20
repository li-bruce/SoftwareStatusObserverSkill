"""Run real scenarios in three observation modes, with version binding."""
import json
from pathlib import Path
import sys
ROOT=Path(__file__).absolute().parents[1]
sys.path.insert(0,str(ROOT))
from observer_runtime.behavior_model import capture


def main():
    model=json.loads((ROOT/"behavior.json").read_text(encoding="utf-8"))
    before=capture(ROOT,model)
    # Business modules load only after the candidate has been bound.
    from archive_app.workflow import definition
    from tooling.scenarios import CASES, execute
    from tooling.size_scenarios import CASES as SIZE_CASES, execute as execute_size
    if capture(ROOT,model)["build_id"]!=before["build_id"]:
        raise RuntimeError("source changed while loading")
    runs=[]
    for mode in ("on","off","fault"):
        for case in CASES:
            runs.append(execute(case,mode,model,before["build_id"]))
        for case in SIZE_CASES:
            runs.append(execute_size(case,mode,model,before["build_id"]))
    print(json.dumps({"build_id":before["build_id"],"machine":definition(),"runs":runs},ensure_ascii=False))


if __name__=="__main__":
    main()
