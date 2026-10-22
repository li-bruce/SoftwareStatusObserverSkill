"""Authoritative lifecycle declaration consumed by the project executor."""
LABELS = {"checking": "检查中", "check_failed": "检查失败", "check_error": "检查异常", "awaiting_approval": "等待审批", "queued": "等待机器", "blocked": "等待有效审批", "printing": "打印中", "stopping": "等待停止确认", "completed": "已完成", "cancelled": "已取消", "superseded": "旧版本作废"}
TRANSITIONS = [
    {"trigger": "checks_passed", "source": "checking", "dest": "awaiting_approval"},
    {"trigger": "checks_failed", "source": "checking", "dest": "check_failed"},
    {"trigger": "checks_error", "source": "checking", "dest": "check_error"},
    {"trigger": "admit", "source": "awaiting_approval", "dest": "queued"},
    {"trigger": "lose_approval", "source": "queued", "dest": "blocked"},
    {"trigger": "restore_approval", "source": "blocked", "dest": "queued"},
    {"trigger": "start", "source": "queued", "dest": "printing"},
    {"trigger": "cancel_print", "source": "printing", "dest": "stopping"},
    {"trigger": "stop_confirmed", "source": "stopping", "dest": "cancelled"},
    {"trigger": "complete_confirmed", "source": ["printing", "stopping"], "dest": "completed"},
    {"trigger": "cancel_pending", "source": ["checking", "awaiting_approval", "queued", "blocked", "check_failed", "check_error"], "dest": "cancelled"},
    {"trigger": "invalidate", "source": ["checking", "awaiting_approval", "queued", "blocked", "check_failed", "check_error"], "dest": "superseded"},
]

def definition() -> dict:
    return {"engine": "project-python-sqlite", "version": "1", "state_type": "str", "states": list(LABELS), "values": list(LABELS), "initial": "checking", "context": {"version": {"type": "integer", "min": 1}}, "events": {t["trigger"]: {"payload": {}} for t in TRANSITIONS}, "transitions": TRANSITIONS, "labels": LABELS, "guards": {}, "source": {"path": "bo_stategraph/declaration.py", "symbol": "definition"}}

def transition(connection, run_id: str, trigger: str) -> str:
    current = connection.execute("SELECT state FROM runs WHERE id=?", (run_id,)).fetchone()[0]
    for t in TRANSITIONS:
        sources = t["source"] if isinstance(t["source"], list) else [t["source"]]
        if t["trigger"] == trigger and current in sources:
            connection.execute("UPDATE runs SET state=? WHERE id=?", (t["dest"], run_id))
            return t["dest"]
    raise ValueError(f"Invalid transition: {current} / {trigger}")
