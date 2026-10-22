"""Focused approval contract retained from the initial change baseline."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.policy import grant_matches

run = {"task_id": "task", "printer_id": "P1", "version": 2, "submitter": "submitter"}
grant = {"task_id": "task", "printer_id": "P1", "version": 2, "approver": "reviewer", "expires": 20, "revoked": 0}
assert grant_matches(grant, run, True, 19)["eligible"]
for field, value in {"task_id": "different", "printer_id": "P2", "version": 1, "approver": "submitter", "revoked": 1}.items():
    assert not grant_matches({**grant, field: value}, run, True, 19)["eligible"], field
assert not grant_matches(grant, run, False, 19)["eligible"]
assert not grant_matches(grant, run, True, 20)["eligible"]
assert not grant_matches(grant, run, True, 21)["eligible"]
assert grant_matches({**grant, "irrelevant_note": "ignored"}, run, True, 19)["eligible"]
print('{"valid":true,"assertions":10,"scope":"task/printer/version/self/role/revocation/expiry"}')
