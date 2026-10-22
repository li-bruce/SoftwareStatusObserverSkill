import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tests.scenarios import run_all
from observer_runtime.behavior_model import capture

if __name__ == "__main__":
    model = json.loads((ROOT / "behavior.json").read_text())
    payload = run_all(model, capture(ROOT, model))
    print(json.dumps(payload, ensure_ascii=False, allow_nan=False))
