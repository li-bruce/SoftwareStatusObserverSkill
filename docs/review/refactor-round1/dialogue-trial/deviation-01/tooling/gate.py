"""Normal delivery entrypoint; propagate the frozen Skill's nonzero result."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "observer_runtime"

if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "check"
    if action == "check":
        status = subprocess.call([sys.executable, "-X", "utf8", "-B", str(SKILL / "architecture_guard.py"), "check", "--root", str(ROOT)])
        if status:
            raise SystemExit(status)
    raise SystemExit(subprocess.call([sys.executable, "-X", "utf8", "-B", str(SKILL / "change_sync.py"), action, "--root", str(ROOT), *sys.argv[2:]]))
