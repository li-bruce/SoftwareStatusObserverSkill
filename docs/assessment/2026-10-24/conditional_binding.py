"""Reproduce source-inventory/source-binding agreement using real parsers."""
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "skills/business-observer/scripts"))
from bo_observer.graph.behavior_model import symbols
from bo_observer.graph.code_structure import parse_unit

source = """if True:
    def conditional(value):
        return value
def outer():
    if True:
        def nested(value):
            return value
    return nested(1)
"""
with tempfile.TemporaryDirectory(dir=ROOT / ".validation") as folder:
    path = Path(folder) / "conditional.py"
    path.write_text(source, encoding="utf-8")
    inventory = parse_unit("conditional.py", source)["symbols"]
    bindings = symbols(path)
    missing = sorted(set(inventory) - set(bindings))
    print(json.dumps({"indexed": sorted(inventory), "bindable": sorted(bindings), "missing": missing}))
    assert not missing, "Indexed declarations must be available to source binding"
