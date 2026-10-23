"""Application-owned executable lifecycle and persistent parallel activities."""
from copy import deepcopy
import json
from pathlib import Path
from enum import StrEnum
import importlib.metadata
from transitions import Machine
from .bo_contracts import validate_runtime_definition

BO_DEFINITION=json.loads(Path(__file__).with_name('machine.json').read_text(encoding='utf-8'))
validate_runtime_definition(BO_DEFINITION)


class Phase(StrEnum):
    CREATED = "created"
    CHECKING = "checking"
    WAITING = "waiting"
    READY = "ready"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPING = "stopping"
    CANCELLED = "cancelled"
    SUPERSEDED = "superseded"
    INTERRUPTED = "interrupted"


ACTIVE = ["created", "checking", "waiting", "ready"]
TERMINAL = {"completed", "failed", "cancelled", "superseded", "interrupted"}
ACTIVITIES = ["content_check", "index_check"]
ACTIVITY_TERMINAL = {"succeeded", "rejected", "failed", "cancelled"}
TRANSITIONS = BO_DEFINITION['transitions']
LABELS = BO_DEFINITION['labels']


class Workflow:
    def __init__(self, phase: str, evaluation: dict):
        validate_runtime_definition(definition(), loaded_engine='transitions.Machine',
            loaded_version=importlib.metadata.version('transitions'),
            guard_names={name for name in dir(self) if callable(getattr(self,name))})
        Phase(phase)
        self.evaluation = evaluation
        self.machine = Machine(model=self, states=[p.value for p in Phase],
            transitions=TRANSITIONS, initial=phase, auto_transitions=False)

    def approved(self):
        return self.evaluation.get("allowed", False)

    def all_passed(self):
        return self.evaluation.get("all_passed", False)

    def effect_saved(self):
        return self.evaluation.get("effect_saved", False)

    def checks_failed(self):
        return self.evaluation.get("checks_failed", False)

    def settled(self):
        return self.evaluation.get("settled", False)


def definition() -> dict:
    return deepcopy(BO_DEFINITION)


def initial_configuration(attempt: str, version: int, capacity: int) -> dict:
    if type(capacity) is not int or capacity not in (1, 2):
        raise ValueError("Processing capacity must be 1 or 2")
    if type(version) is not int or version < 1:
        raise ValueError("Content version must be a positive integer")
    return {"attempt":attempt,"param_version":version,"revision":0,
            "activities":{a:"pending" for a in ACTIVITIES},
            "resources":{"processing_slots":{"capacity":capacity,"available":capacity,"holders":[]}},
            "join":{"state":"waiting","pending":list(ACTIVITIES)},"journal":[],
            "results":{},"discarded":[],"wait_reasons":{}}


def change_phase(run: dict, event: str, evaluation: dict, now: float) -> None:
    workflow = Workflow(run["phase"], evaluation)
    old = workflow.state
    if not workflow.trigger(event):
        raise ValueError("State machine rejected transition: " + event)
    run["phase"] = workflow.state
    run["phase_journal"].append({"event":event,"source":old,"target":workflow.state,
                                "attempt":run["id"],"clock":now,
                                "activity_revision":run["configuration"]["revision"]})


def activity_step(run: dict, event: str, activity: str, now: float,
                  outcome: str | None = None) -> None:
    cfg = run["configuration"]
    before = deepcopy({k:cfg[k] for k in ("activities","resources","join")})
    states, resource = cfg["activities"], cfg["resources"]["processing_slots"]
    if event == "wait":
        if states[activity] != "pending" or resource["available"] > 0:
            raise ValueError("Waiting-for-slot precondition is not satisfied")
        states[activity] = "waiting"
    elif event == "start":
        if states[activity] not in ("pending","waiting") or resource["available"] < 1 or activity in cfg["discarded"]:
            raise ValueError("Check cannot start")
        states[activity] = "running"
        resource["available"] -= 1
        resource["holders"].append(activity)
    elif event == "finish":
        if states[activity] != "running" or outcome not in ("succeeded","rejected","failed"):
            raise ValueError("Check has not started or its result is invalid")
        states[activity] = outcome
        resource["available"] += 1
        resource["holders"].remove(activity)
        if all(s in ACTIVITY_TERMINAL for s in states.values()):
            cfg["join"]["state"] = "enabled"
    elif event == "join":
        if cfg["join"]["state"] != "enabled":
            raise ValueError("Checks must finish before joining")
        cfg["join"]["state"] = "passed" if all(s=="succeeded" for s in states.values()) else "rejected"
    elif event == "abort":
        if "running" in states.values():
            raise ValueError("Running checks have not finished")
        cfg["activities"] = {a:s if s in ACTIVITY_TERMINAL else "cancelled" for a,s in states.items()}
        cfg["join"]["state"] = "rejected"
    else:
        raise ValueError("Unknown activity event")
    cfg["join"]["pending"] = [a for a in ACTIVITIES if cfg["activities"][a] not in ACTIVITY_TERMINAL]
    cfg["revision"] += 1
    cfg["journal"].append({"seq":cfg["revision"],"event":event,"activity":activity,
        "before":before,"after":deepcopy({k:cfg[k] for k in ("activities","resources","join")}),
        "clock":now,"phase":run["phase"],"discarded":list(cfg["discarded"]),
        "wait_reasons":dict(cfg["wait_reasons"])})


def request_stop(run: dict, reason: str, now: float) -> None:
    if run["phase"] in TERMINAL:
        return
    if run["phase"] != "stopping":
        change_phase(run,"stop",{},now)
    run["stop_reason"] = reason
    cfg = run["configuration"]
    cfg["discarded"] = [a for a in ACTIVITIES if cfg["activities"][a] in ("pending","waiting")]
    for a in cfg["discarded"]:
        cfg["wait_reasons"][a] = "Discarded; do not start; wait for this run's active checks to finish"


def settle(run: dict, now: float) -> None:
    cfg = run["configuration"]
    if run["phase"]=="stopping" and "running" not in cfg["activities"].values():
        activity_step(run,"abort","checks_join",now)
        change_phase(run,"stale_done" if run["stop_reason"]=="version_changed" else "cancel_done",
                     {"settled":True},now)


def schedule(run: dict, evaluation: dict, now: float) -> list:
    """Select actual activities under the caller transaction; never execute domain work."""
    launches = []
    cfg = run["configuration"]
    if not evaluation["version_current"]:
        request_stop(run,"version_changed",now)
    if run["phase"]=="stopping":
        settle(run,now)
    else:
        if cfg["join"]["state"]=="enabled":
            activity_step(run,"join","checks_join",now)
        if cfg["join"]["state"]=="rejected":
            change_phase(run,"reject",{"checks_failed":True},now)
        elif not evaluation["allowed"]:
            run["resume_required"] = True
            if run["phase"]!="waiting":
                change_phase(run,"pause",{},now)
            for a,s in cfg["activities"].items():
                if s in ("pending","waiting"):
                    cfg["wait_reasons"][a] = "; ".join(evaluation["reasons"])+"; continue manually after conditions recover"
        elif run["resume_required"]:
            if run["phase"]!="waiting":
                change_phase(run,"pause",{},now)
            for a,s in cfg["activities"].items():
                if s in ("pending","waiting"):
                    cfg["wait_reasons"][a] = "Conditions restored; waiting for manual continuation"
        else:
            if run["phase"] in ("created","waiting"):
                change_phase(run,"begin",evaluation,now)
            if cfg["join"]["state"]=="passed" and run["phase"]!="ready":
                change_phase(run,"checked",{**evaluation,"all_passed":True},now)
            elif cfg["join"]["state"]!="passed":
                for activity in ACTIVITIES:
                    if cfg["activities"][activity] not in ("pending","waiting"):
                        continue
                    if cfg["resources"]["processing_slots"]["available"]:
                        cfg["wait_reasons"].pop(activity,None)
                        activity_step(run,"start",activity,now)
                        launches.append((deepcopy(run),activity,dict(evaluation["basis"])))
                    elif cfg["activities"][activity]=="pending":
                        cfg["wait_reasons"][activity] = "Wait for an available slot in this run"
                        activity_step(run,"wait",activity,now)
    return launches


def checks_passed(run: dict) -> bool:
    cfg, request = run["configuration"], run["input"]
    same_run = cfg["attempt"]==run["id"] and cfg["param_version"]==request["content_version"]
    return (same_run and cfg["join"]["state"]=="passed"
                  and all(cfg["activities"][a]=="succeeded" and cfg["results"].get(a,{}).get("passed") is True
                          for a in ACTIVITIES))


def interrupt(run: dict, now: float) -> None:
    """Mark vanished workers and release their resources; do not restart them."""
    cfg = run["configuration"]
    for a,s in list(cfg["activities"].items()):
        if s=="running":
            cfg["results"][a]={"passed":False,"error":"Process interrupted"}
            activity_step(run,"finish",a,now,"failed")
    activity_step(run,"abort","checks_join",now)
    change_phase(run,"interrupt",{"settled":True},now)
    run["stop_reason"]="process_interrupted"


def finish_activity(run, activity, result, outcome, now):
    run["configuration"]["results"][activity] = result
    activity_step(run, "finish", activity, now, outcome)
    settle(run, now)


def resume(run, evaluation):
    if run["phase"] in TERMINAL or run["stop_reason"]:
        raise ValueError("This run is finished or stopping; start a new run")
    run["resume_required"] = not evaluation["allowed"]
