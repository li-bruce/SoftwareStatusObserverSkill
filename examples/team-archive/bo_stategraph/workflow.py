"""Application-owned executable lifecycle and persistent parallel activities."""
from copy import deepcopy
from enum import StrEnum
import importlib.metadata
from transitions import Machine


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
TRANSITIONS = [
    {"trigger":"begin","source":["created","waiting"],"dest":"checking","conditions":"approved"},
    {"trigger":"pause","source":ACTIVE,"dest":"waiting"},
    {"trigger":"checked","source":["checking","waiting"],"dest":"ready","conditions":["all_passed","approved"]},
    {"trigger":"publish","source":"ready","dest":"completed","conditions":["all_passed","approved","effect_saved"]},
    {"trigger":"reject","source":ACTIVE,"dest":"failed","conditions":"checks_failed"},
    {"trigger":"stop","source":ACTIVE,"dest":"stopping"},
    {"trigger":"cancel_done","source":"stopping","dest":"cancelled","conditions":"settled"},
    {"trigger":"stale_done","source":"stopping","dest":"superseded","conditions":"settled"},
    {"trigger":"interrupt","source":[*ACTIVE,"stopping"],"dest":"interrupted","conditions":"settled"},
]
LABELS = {"created":"准备归档","checking":"检查中","waiting":"等待资格 · 点击继续",
          "ready":"检查通过，复核提交","completed":"已归档","failed":"检查未通过",
          "stopping":"等待已启动检查结束","cancelled":"本次运行已取消",
          "superseded":"内容已改版，本次不可提交","interrupted":"进程中断，需新建运行"}


class Workflow:
    def __init__(self, phase: str, evaluation: dict):
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
    return {
        "engine":"transitions.Machine","version":importlib.metadata.version("transitions"),
        "states":[p.value for p in Phase],"values":[p.value for p in Phase],
        "initial":"created","state_type":"Phase (str enum)","transitions":deepcopy(TRANSITIONS),
        "events":{t["trigger"]:{"payload":{}} for t in TRANSITIONS},
        "labels":LABELS,"event_labels":{"begin":"开始检查","pause":"等待","checked":"两项通过",
        "publish":"提交归档","stop":"停止新检查","cancel_done":"取消完成","stale_done":"旧版本收尾",
        "reject":"检查失败","interrupt":"记录中断"},
        "context":{"param_version":{"type":"integer","min":1,"readonly":True},
                   "capacity":{"type":"integer","min":1,"max":2,"readonly":True},
                   "operator_id":{"type":"string","readonly":True},
                   "document_id":{"type":"string","readonly":True}},
        "guards":{k:"Authoritative evaluation."+k for k in
                  ("approved","all_passed","effect_saved","checks_failed","settled")},
        "source":{"path":"bo_stategraph/workflow.py","symbol":"Workflow"},
        "persistence":"SQLite runs.payload: phase, phase_journal and activity configuration in one transaction",
        "execution":{"schema":"activity-graph/v1","within":"checking","parent":"flow.checks",
            "activity_state_type":"ActivityState (str)",
            "activity_states":["pending","waiting","running","succeeded","rejected","failed","cancelled"],
            "activities":[{"id":a,"source":{"path":"archive_app/policy.py",
                "symbol":"check_content" if a=="content_check" else "check_index"},
                "requires":{"processing_slots":1}} for a in ACTIVITIES],
            "resources":[{"id":"processing_slots","scope":"run","min":1,"max":2}],
            "join":{"id":"checks_join","policy":"all","requires":ACTIVITIES,
                    "success_states":["ready","completed"],"guard":"all_passed"}},
    }


def initial_configuration(attempt: str, version: int, capacity: int) -> dict:
    if type(capacity) is not int or capacity not in (1, 2):
        raise ValueError("处理名额只能选择 1 或 2")
    if type(version) is not int or version < 1:
        raise ValueError("内容版本必须是正整数")
    return {"attempt":attempt,"param_version":version,"revision":0,
            "activities":{a:"pending" for a in ACTIVITIES},
            "resources":{"processing_slots":{"capacity":capacity,"available":capacity,"holders":[]}},
            "join":{"state":"waiting","pending":list(ACTIVITIES)},"journal":[],
            "results":{},"discarded":[],"wait_reasons":{}}


def change_phase(run: dict, event: str, evaluation: dict, now: float) -> None:
    workflow = Workflow(run["phase"], evaluation)
    old = workflow.state
    if not workflow.trigger(event):
        raise ValueError("状态机拒绝迁移：" + event)
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
            raise ValueError("等待名额的前提不成立")
        states[activity] = "waiting"
    elif event == "start":
        if states[activity] not in ("pending","waiting") or resource["available"] < 1 or activity in cfg["discarded"]:
            raise ValueError("检查不能启动")
        states[activity] = "running"
        resource["available"] -= 1
        resource["holders"].append(activity)
    elif event == "finish":
        if states[activity] != "running" or outcome not in ("succeeded","rejected","failed"):
            raise ValueError("检查尚未运行或结果无效")
        states[activity] = outcome
        resource["available"] += 1
        resource["holders"].remove(activity)
        if all(s in ACTIVITY_TERMINAL for s in states.values()):
            cfg["join"]["state"] = "enabled"
    elif event == "join":
        if cfg["join"]["state"] != "enabled":
            raise ValueError("检查未结束不能汇合")
        cfg["join"]["state"] = "passed" if all(s=="succeeded" for s in states.values()) else "rejected"
    elif event == "abort":
        if "running" in states.values():
            raise ValueError("运行中的检查尚未结束")
        cfg["activities"] = {a:s if s in ACTIVITY_TERMINAL else "cancelled" for a,s in states.items()}
        cfg["join"]["state"] = "rejected"
    else:
        raise ValueError("未知活动事件")
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
        cfg["wait_reasons"][a] = "已作废，不再启动；等待本次其他检查收尾"


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
                    cfg["wait_reasons"][a] = "；".join(evaluation["reasons"])+"；条件恢复后点击继续"
        elif run["resume_required"]:
            if run["phase"]!="waiting":
                change_phase(run,"pause",{},now)
            for a,s in cfg["activities"].items():
                if s in ("pending","waiting"):
                    cfg["wait_reasons"][a] = "当前条件已恢复，等待点击继续"
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
                        cfg["wait_reasons"][activity] = "等待本次运行的可用名额"
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
            cfg["results"][a]={"passed":False,"error":"进程中断"}
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
        raise ValueError("这次运行已结束或正在停止，请新建运行")
    run["resume_required"] = not evaluation["allowed"]
