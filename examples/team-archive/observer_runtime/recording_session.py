"""Local observation intervals. Playback never calls application commands.

The provider returns a consistent, already instrumented graph view. Sampling
copies its event stream; it does not sample function execution or invent events.
"""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import threading
import time
import uuid
try:
    from .runtime_frames import merge_frames
except ImportError:
    from runtime_frames import merge_frames

SCHEMA = "stategraph-recording/v1"
def timestamp():
    return datetime.now(timezone.utc).isoformat()


def checkpoint(view, *, context=False):
    """Keep graph facts, not document bodies or arbitrary application state."""
    authority = view["authority"]
    model = view.get('model', {})
    fields = model.get('presentation', {}).get('recording', {}).get('parameters')
    if fields is None: fields = list(model.get('machine', {}).get('context', {}))

    value = {
        "authority": {
            "entity": authority.get("entity"),
            "state": authority.get("state"),
            "basis": deepcopy(authority.get("basis", {})),
            "parameters": {k: deepcopy(authority.get("parameters", {}).get(k))
                           for k in fields if k in authority.get("parameters", {})},
            "effects": [],  # Commit effects are read from selected probe fields.
        },
        "machine": deepcopy(view["machine"]),
        "health": deepcopy(view["health"]),
        "binding_status": deepcopy(view["binding_status"]),
        "historical": True, "busy": False,
    }
    if context:
        value.update(model=deepcopy(view["model"]), manifest=deepcopy(view["manifest"]),
                     events=deepcopy(view["events"][-2000:]))
    return value


class Recordings:
    def __init__(self, directory, provider, sources, *, action_nodes=None,
                 interval=1.0, max_events=20000, max_bytes=32 * 1024 * 1024, scope_setter=None, event_source=None, command_fields=()):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.provider, self.sources = provider, sources
        self.action_nodes = action_nodes or {}
        self.bo_scope_setter = scope_setter
        self.interval, self.max_events, self.max_bytes = interval, max_events, max_bytes
        self.lock, self.operations = threading.RLock(), threading.Lock()
        self.active, self.cached, self.last_error = None, {}, ""
        self.catalog = {}
        self.command_fields = tuple(command_fields)
        self._stream_events = {}
        self._starting = self._stream_limited = False
        self._unsubscribe = event_source.subscribe(self.bo_event) if event_source else None
        self.closed = threading.Event()
        # An interrupted process never continues the old interval under a new ID.
        for path in self.directory.glob("*.json"):
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
                if value.get("schema") == SCHEMA:
                    self.catalog[path.stem] = self.summary(value)
                if value.get("schema") == SCHEMA and value.get("status") == "recording":
                    value.update(status="interrupted", ended_at=timestamp())
                    value["gaps"].append("程序结束前未点击结束；仅保留最后一次已保存记录。")
                    self._write(value)
            except (OSError, ValueError, KeyError):
                self.last_error = "有一份记录无法读取；原文件保留。"
        self.worker = threading.Thread(target=self._worker, daemon=True, name="stategraph-recordings")
        self.worker.start()

    def bo_event(self, event):
        with self.lock:
            if not self.active and not self._starting: return
            if len(self._stream_events) > self.max_events:
                self._stream_limited = True
                return
            self._stream_events[event['id']] = deepcopy(event)

    def _path(self, ident):
        if not isinstance(ident, str) or not re.fullmatch(r"[a-f0-9]{32}", ident):
            raise ValueError("记录编号无效")
        return self.directory / (ident + ".json")

    def _write(self, value):
        path = self._path(value["id"])
        data = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        if len(data.encode("utf-8")) > self.max_bytes:
            raise ValueError("记录达到大小上限")
        temporary = path.with_suffix(".tmp")
        temporary.write_text(data, encoding="utf-8", newline="\n")
        temporary.replace(path)
        self.cached[value["id"]] = value
        self.catalog[value["id"]] = self.summary(value)
        while len(self.cached) > 8:
            oldest = next(iter(self.cached))
            if self.active and oldest == self.active["id"]:
                self.cached[oldest] = self.cached.pop(oldest)
                continue
            del self.cached[oldest]

    def _save(self, value):
        if value['status'] != 'recording' and 'runtime_frames' in value:
            captured = {f['event_id'] for f in value['runtime_frames']['frames']}
            missing = sum(e['id'] not in captured for e in value['events'])
            if missing:
                message = f'{missing} 个步骤没有对应的运行快照；状态未作推断。'
                if message not in value['gaps']: value['gaps'].append(message)
        try:
            self._write(value)
            self.last_error = ""
        except (OSError, ValueError) as error:
            # Recording failure cannot change a business operation's result.
            self.last_error = str(error)[:160]
            value["status"] = "interrupted"
            value["ended_at"] = timestamp()
            value["gaps"].append("记录保存失败：" + self.last_error)
            self.cached[value["id"]] = value
            self.catalog[value["id"]] = self.summary(value)
            if self.active is value:
                self.active = None
        finally:
            if value["status"] != "recording":
                self.bo_restore_capture()

    def bo_capture_plan(self, model, requested=None):
        requested = requested or {"mode": "all"}
        if not isinstance(requested, dict) or requested.get("mode") not in ("all", "focused"):
            raise ValueError("采集范围无效")
        if requested["mode"] == "all":
            return {"mode": "all", "nodes": None, "roots": [], "boundary_nodes": []}
        if self.bo_scope_setter is None:
            raise ValueError("此程序尚未接入区域采集")
        nodes = {n["id"]: n for n in model["nodes"]}
        roots = requested.get("roots", requested.get("nodes", []))
        if not isinstance(roots, list) or not roots or len(roots) > 2000 or any(not isinstance(n, str) or n not in nodes for n in roots):
            raise ValueError("请选择有效的节点或区域")
        selected = set(roots)
        while True:
            children = {n["id"] for n in nodes.values() if n.get("parent") in selected}
            if children <= selected:
                break
            selected.update(children)
        boundary = set()
        for ident in list(selected):
            parent, seen = nodes[ident].get("parent"), set()
            while parent in nodes and parent not in seen:
                seen.add(parent)
                boundary.add(parent)
                parent = nodes[parent].get("parent")
        parent = model.get("machine", {}).get("execution", {}).get("parent")
        if parent in nodes:
            boundary.add(parent)  # Exact state revisions remain interpretable.
        allowed = selected | boundary
        return {"mode": "focused", "nodes": sorted(allowed), "roots": sorted(set(roots)),
                "boundary_nodes": sorted(boundary-selected)}

    def bo_restore_capture(self):
        if self.bo_scope_setter:
            self.bo_scope_setter(None)

    def start(self, label="", scope=None):
        with self.operations:
            try:
                return self._start(label, scope)
            finally:
                with self.lock:
                    self._starting = False
                    if not self.active: self._stream_events = {}

    def _start(self, label, scope):
        with self.lock:
            if self.active:
                return self.summary(self.active)
        with self.lock:
            self._stream_events = {}
            self._starting = True
            self._stream_limited = False
        view = self.provider()
        if view.get("historical") or view["binding_status"]["status"] != "current":
            raise ValueError("请先加载已验收的当前程序")
        health = view["health"]
        if not health.get("enabled", True):
            raise ValueError("当前程序未开启事件采集")
        plan = self.bo_capture_plan(view["model"], scope)
        if self.bo_scope_setter:
            self.bo_scope_setter(plan["nodes"])
            try:
                view = self.provider()
            except Exception:
                self.bo_restore_capture()
                raise
            health = view["health"]
        value = {
            "schema": SCHEMA, "id": uuid.uuid4().hex, "label": str(label).strip()[:80] or "操作记录",
            "status": "recording", "started_at": timestamp(), "ended_at": None,
            "build_id": view["manifest"]["build_id"], "run_id": health["run_id"],
            "start_seq": health["attempted"], "end_seq": health["attempted"],
            "context": checkpoint(view, context=True), "final": checkpoint(view),
            "sources": deepcopy(self.sources), "events": [], "commands": [], "gaps": [],
            "capture": plan,
            "command_fields": list(self.command_fields) or view.get("model",{}).get("presentation",{}).get("recording",{}).get("command_fields",[]),
        }
        if plan["nodes"] is not None:
            value["context"]["events"] = [e for e in value["context"]["events"] if e["node"] in plan["nodes"]]
        if len(view["events"]) > 2000:
            value["gaps"].append("开始前的上下文只保留最近 2000 条事件。")
        merge_frames(value, view, checkpoint)
        with self.lock:
            try:
                self._stream_events = {k:e for k,e in self._stream_events.items()
                    if e.get('run_id') == value['run_id'] and e['seq'] > value['start_seq']}
                self._stream_limited = False
                self._write(value)
            except Exception:
                self.bo_restore_capture()
                raise
            self.active = value
            self._starting = False
            return self.summary(value)


    def _capture(self, ident, view):
        with self.lock:
            value = self.active
            if not value or value["id"] != ident:
                return
            health = view["health"]
            if health.get("run_id") != value["run_id"] or view["manifest"]["build_id"] != value["build_id"]:
                value.update(status="interrupted", ended_at=timestamp())
                value["gaps"].append("采集进程或代码版本改变，已停止拼接。")
                self.active = None
                self._save(value)
                return
            end = health["attempted"]
            if end < value["end_seq"]:
                return  # A slower concurrent sampler cannot replace a newer boundary.
            merged = {e['id']:e for e in value['events']}
            merged.update(self._stream_events)
            merged.update({e['id']:e for e in view['events']})
            events = [e for e in merged.values() if e.get("run_id") == value["run_id"]
                      and value["start_seq"] < e["seq"] <= end]
            events.sort(key=lambda e: e["seq"])
            allowed = value.get("capture", {}).get("nodes")
            excluded = 0
            if allowed is not None:
                excluded = sum(e["node"] not in allowed for e in events)
                events = [e for e in events if e["node"] in allowed]
            value["scope_excluded"] = excluded
            value["capture_filtered"] = max(0, health.get("filtered", 0)-value["context"]["health"].get("filtered", 0))
            value.update(events=deepcopy(events[:self.max_events]), end_seq=end,
                         final=checkpoint(view))
            merge_frames(value, view, checkpoint)
            if len(events) > self.max_events or self._stream_limited:
                value.update(status="limited", ended_at=timestamp())
                value["gaps"].append("事件达到上限，已自动停止；超出部分未保存。")
                self.active = None
            initial = value["context"]["health"]
            if any(health.get(k, 0) > initial.get(k, 0) for k in ("errors", "dropped")):
                message = "区间内存在采集失败或丢事件，路线可能不完整。"
                if message not in value["gaps"]:
                    value["gaps"].append(message)
            if health.get('reference_evictions', 0) > initial.get('reference_evictions', 0):
                message = "因果引用缓存达到上限；未保留的依赖不作推断。"
                if message not in value['gaps']: value['gaps'].append(message)
            self._save(value)

    def sample(self):
        with self.lock:
            ident = self.active["id"] if self.active else None
        if ident:
            self._capture(ident, self.provider())

    def stop(self):
        with self.operations:
            with self.lock:
                ident = self.active["id"] if self.active else None
            if not ident:
                raise ValueError("当前没有正在记录的区间")
            self._capture(ident, self.provider())
            with self.lock:
                value = self.cached[ident]
                if value["status"] == "recording":
                    value.update(status="stopped", ended_at=timestamp())
                    if len(value["events"])+value.get("scope_excluded", 0) != value["end_seq"] - value["start_seq"]:
                        value["gaps"].append("事件序号存在缺口，未补造缺失步骤。")
                    self.active = None
                    self._save(value)
                return self.summary(value)

    def command(self, action, values, result=None, error=None):
        """Called by the optional HTTP adapter after a command returns."""
        try:
            with self.lock:
                if not self.active:
                    return
                allowed = self.active.get("capture", {}).get("nodes")
                if allowed is not None and self.action_nodes.get(action) not in allowed:
                    return
                if len(self.active["commands"]) >= 2000:
                    message = "操作标记达到 2000 条上限，后续标记未保存；探针事件继续采集。"
                    if message not in self.active["gaps"]:
                        self.active["gaps"].append(message)
                    return
                self.active["commands"].append({
                    "id": "command:" + self.active["id"] + ":" + str(len(self.active["commands"]) + 1),
                    "observed_at": timestamp(), "action": action, "node": self.action_nodes.get(action),
                    "values": {k: values[k] for k in self.active.get("command_fields", [])
                               if k in values and isinstance(values[k], (str, int, float, bool, type(None)))},
                    "result": {k: v for k, v in (result or {}).items() if k in self.active.get("command_fields", []) or k == "ok"},
                    "status": "error" if error else "ok", "error": str(error)[:160] if error else None,
                })
        except Exception:
            self.last_error = "操作标记未能保存"

    @staticmethod
    def summary(value):
        return {k: value[k] for k in ("id", "label", "status", "started_at", "ended_at", "build_id")} | {
            "events": len(value["events"]), "commands": len(value["commands"]), "gaps": value["gaps"],
            "capture": value.get("capture", {"mode": "all"}), "capture_filtered": value.get("capture_filtered", 0)}

    def get(self, ident):
        with self.lock:
            path = self._path(ident)
            value = self.cached.get(ident)
            if value is None:
                if not path.exists():
                    raise ValueError("记录不存在")
                value = json.loads(path.read_text(encoding="utf-8"))
            return deepcopy(value)

    def list(self):
        with self.lock:
            entries = {}
            for path in sorted(self.directory.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:50]:
                try:
                    if path.stem not in self.catalog:
                        value = json.loads(path.read_text(encoding="utf-8"))
                        if value.get("schema") == SCHEMA:
                            self.catalog[path.stem] = self.summary(value)
                    if path.stem in self.catalog:
                        entries[path.stem] = self.catalog[path.stem]
                except (OSError, ValueError, KeyError):
                    continue
            for ident, value in self.cached.items():
                entries[ident] = self.summary(value)
            return {"active": self.summary(self.active) if self.active else None,
                    "recordings": sorted(entries.values(), key=lambda v: v["started_at"], reverse=True)[:50],
                    "error": self.last_error}

    def _worker(self):
        while not self.closed.wait(self.interval):
            try:
                self.sample()
            except Exception as error:
                with self.lock:
                    self.last_error = "本次采样失败：" + str(error)[:120]
                    if self.active and self.last_error not in self.active["gaps"]:
                        self.active["gaps"].append(self.last_error)

    def close(self):
        self.closed.set()
        self.worker.join(2)
        try:
            self.sample()
        except Exception as error:
            self.last_error = "关闭前采样失败：" + str(error)[:120]
        if self._unsubscribe: self._unsubscribe()
        with self.lock:
            if self.active:
                value = self.active
                value.update(status="interrupted", ended_at=timestamp())
                value["gaps"].append("程序关闭，记录未完整结束。")
                self.active = None
                self._save(value)
