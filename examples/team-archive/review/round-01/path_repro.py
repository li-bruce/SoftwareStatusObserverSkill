"""Read-only minimal reproduction of the observed path resolution failure."""
import json
import os
from pathlib import Path
import sys

project = Path(__file__).parent.parent.parent
skill = project.parent / "skill" / "business-observer"
sys.path.insert(0, str(skill / "scripts"))
from behavior_model import contained

result = {
    "cwd": os.getcwd(),
    "file": __file__,
    "version": sys.version,
    "dot_absolute": str(Path(".").absolute()),
    "dot_resolve": str(Path(".").resolve()),
    "dot_absolute_resolve": str(Path(".").absolute().resolve()),
    "model_exists_without_resolve": Path("behavior.json").exists(),
    "checks": [],
}
for root in [Path("."), Path(".").resolve(), Path(os.getcwd()), project]:
    item = {"root_argument": str(root)}
    try:
        path = contained(root, "behavior.json")
        item.update(result=str(path), exists=path.exists())
    except Exception as error:
        item.update(error_type=type(error).__name__, error=str(error))
    result["checks"].append(item)
print(json.dumps(result, ensure_ascii=True, indent=2))
