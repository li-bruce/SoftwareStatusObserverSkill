"""The application's executable statechart, typed context and transaction journal.

This module is business code. It has no dependency on the observer or its events.
The graph exports this declaration rather than inventing a second state machine.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass, field, fields
from enum import StrEnum
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).absolute().parent / ".deps"))
from transitions.extensions import HierarchicalMachine


class Priority(StrEnum):
    NORMAL = "normal"
    HIGH = "high"


class Phase(StrEnum):
    DRAFT = "draft"
    AUTHORIZING = "running_authorizing"
    SOLVING = "running_solving"
    RECHECKING = "running_rechecking"
    COMMITTING = "running_committing"
    WAIT_APPROVAL = "waiting_approval"
    WAIT_PARAMETERS = "waiting_parameters"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class Parameters:
    cells: int = field(metadata={"type":"integer", "min":1, "max":100000, "unit":"cells"})
    steps: int = field(metadata={"type":"integer", "min":1, "max":500, "unit":"iterations"})
    priority: Priority = field(metadata={"type":"enum", "values":["normal","high"]})
    param_version: int = field(metadata={"type":"integer", "min":1, "readonly":True})

    def __post_init__(self):
        for item in fields(self):
            value, meta = getattr(self, item.name), item.metadata
            if meta["type"] == "integer" and (type(value) is not int or value < meta["min"] or value > meta.get("max", 2**63-1)):
                raise ValueError(f"invalid {item.name}: {value!r}")
        object.__setattr__(self, "priority", Priority(self.priority))

    @classmethod
    def from_job(cls, job):
        return cls(**{f.name:job[f.name] for f in fields(cls)})


@dataclass(frozen=True)
class Evaluation:
    allowed: bool = False
    version_ok: bool = True
    effect_exists: bool = False
    reasons: tuple[str, ...] = ()
    support_ids: tuple[str, ...] = ()

    def __post_init__(self):
        if any(type(getattr(self,k)) is not bool for k in ("allowed","version_ok","effect_exists")):
            raise ValueError("guard values must be boolean")
        if type(self.reasons) is not tuple or type(self.support_ids) is not tuple:
            raise ValueError("guard collections must be immutable tuples")
        if any(not isinstance(v,str) for v in (*self.reasons,*self.support_ids)):
            raise ValueError("guard reasons and support ids must be strings")


STATES = ["draft", {"name":"running", "children":["authorizing","solving","rechecking","committing"], "initial":"authorizing"},
          {"name":"waiting", "children":["approval","parameters"], "initial":"approval"}, "completed", "failed"]
TRANSITIONS = [
    {"trigger":"begin", "source":["draft","waiting","failed"], "dest":"running_authorizing"},
    {"trigger":"gate", "source":"running_authorizing", "dest":"running_solving", "conditions":"approved"},
    {"trigger":"gate", "source":"running_authorizing", "dest":"waiting_approval", "unless":"approved"},
    {"trigger":"computed", "source":"running_solving", "dest":"running_rechecking"},
    {"trigger":"recheck", "source":"running_rechecking", "dest":"waiting_parameters", "unless":"version_current"},
    {"trigger":"recheck", "source":"running_rechecking", "dest":"waiting_approval", "conditions":"version_current", "unless":"approved"},
    {"trigger":"recheck", "source":"running_rechecking", "dest":"running_committing", "conditions":["version_current","approved"]},
    {"trigger":"publish", "source":"running_committing", "dest":"completed", "conditions":"effect_persisted"},
    {"trigger":"edit", "source":["draft","waiting","completed","failed"], "dest":"draft"},
    # A running computation retains its phase. Its immutable version is checked before publish.
    {"trigger":"edit", "source":"running", "dest":None},
    {"trigger":"fail", "source":"running", "dest":"failed"},
]
LABELS = {"draft":"Ready", "running":"Running", "running_authorizing":"Check authorization", "running_solving":"Compute",
    "running_rechecking":"Recheck", "running_committing":"Persist result", "waiting":"Waiting", "waiting_approval":"Wait for valid authorization",
    "waiting_parameters":"Wait for recomputation with new parameters", "completed":"Committed", "failed":"Failed"}


class Workflow:
    """One machine per authoritative transaction; no stale in-memory authority."""
    def __init__(self, phase: str, evaluation: Evaluation = Evaluation()):
        Phase(phase)
        self.evaluation = evaluation
        self.machine = HierarchicalMachine(model=self, states=STATES, transitions=TRANSITIONS,
            initial=phase, auto_transitions=False, send_event=True, queued=False)

    def approved(self, _):
        return self.evaluation.allowed

    def version_current(self, _):
        return self.evaluation.version_ok

    def effect_persisted(self, _):
        return self.evaluation.effect_exists

    @staticmethod
    def advance(db, event: str, evaluation: Evaluation = Evaluation(), *, attempt="command"):
        row = dict(db.execute("SELECT * FROM jobs WHERE id='SIM-001'").fetchone())
        params = Parameters.from_job(row)
        engine = Workflow(row["machine_state"], evaluation)
        if not engine.trigger(event):
            raise ValueError(f"guard rejected {event} from {engine.state}")
        phase = Phase(engine.state)
        state = phase.value.split("_")[0]
        reasons = list(evaluation.reasons) if state in {"waiting","failed"} else []
        db.execute("UPDATE jobs SET state=?,machine_state=?,reasons=? WHERE id='SIM-001'",
            (state,phase.value,json.dumps(reasons)))
        meta = dict(db.execute("SELECT epoch,clock FROM meta WHERE id=1").fetchone())
        # This journal commits or rolls back with the authoritative state/effect.
        db.execute("INSERT INTO machine_journal(event,source,target,attempt,context,recorded_at) VALUES(?,?,?,?,?,?)",
            (event,row["machine_state"],phase.value,attempt,json.dumps({**asdict(params),**asdict(evaluation),**meta}),time.time()))
        return phase


def definition():
    return {"engine":"transitions", "version":"0.9.3", "state_type":"Phase (str enum)",
        "initial":"draft", "completed_scope":"terminal for a parameter version; edit creates a new version",
        "events":{name:{"payload":({"allowed":"boolean","version_ok":"boolean","effect_exists":"boolean",
            "reasons":"tuple[string]","support_ids":"tuple[string]"} if name in {"gate","recheck","publish","fail"} else {})}
            for name in {t["trigger"] for t in TRANSITIONS}},
        "states":STATES, "values":[v.value for v in Phase], "labels":LABELS, "transitions":TRANSITIONS,
        "context":{f.name:dict(f.metadata) for f in fields(Parameters)},
        "guards":{"approved":"Evaluation.allowed: bool", "version_current":"Evaluation.version_ok: bool",
                  "effect_persisted":"Evaluation.effect_exists: bool"},
        "persistence":"jobs.machine_state + machine_journal; same SQLite transaction as the result",
        "source":{"path":"workflow.py","symbol":"Workflow"}}
