"""Bounded observation history. Current business state is never deleted here."""

from collections import deque
from copy import deepcopy
import json
import os
from pathlib import Path
import threading
import time

DEFAULTS = {
    "memory_events": 10000,
    "memory_seconds": 1800,
    "log_bytes": 8 * 1024 * 1024,
    "log_backups": 2,
}


class EventHistory:
    def __init__(self, *, project_root=None, path=None, limits=None):
        settings = dict(DEFAULTS)
        if project_root:
            config = Path(project_root) / "bo_stategraph/config/retention.json"
            if config.exists():
                settings.update(json.loads(config.read_text(encoding="utf-8")))
        settings.update(limits or {})
        if set(settings) != set(DEFAULTS) or any(
            type(v) is not int or v <= 0 for v in settings.values()
        ):
            raise ValueError("retention limits must be positive integers with known names")
        self.limits, self.path = settings, Path(path) if path else None
        self.events, self.listeners = deque(), []
        self.lock = threading.RLock()
        self.evicted = self.log_errors = self.listener_errors = 0

    def _trim(self):
        cutoff = time.monotonic() - self.limits["memory_seconds"]
        while self.events and (
            len(self.events) > self.limits["memory_events"] or self.events[0][0] < cutoff
        ):
            self.events.popleft()
            self.evicted += 1

    def append(self, event):
        with self.lock:
            self.events.append((time.monotonic(), deepcopy(event)))
            self._trim()
            listeners = list(self.listeners)
        # Recording listeners copy bounded data in memory, before UI history expires.
        for listener in listeners:
            try:
                listener(event)
            except Exception:
                self.listener_errors += 1
        if self.path:
            try:
                self._log(event)
            except OSError:
                self.log_errors += 1

    def _log(self, event):
        raw = (json.dumps(event, ensure_ascii=False) + "\n").encode("utf-8")
        if len(raw) > self.limits["log_bytes"]:
            self.log_errors += 1
            return
        with self.lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if (
                self.path.exists()
                and self.path.stat().st_size + len(raw) > self.limits["log_bytes"]
            ):

                def rotated(i):
                    return self.path.with_name(self.path.name + "." + str(i))

                for i in range(self.limits["log_backups"], 1, -1):
                    if rotated(i - 1).exists():
                        os.replace(rotated(i - 1), rotated(i))
                os.replace(self.path, rotated(1))
            with self.path.open("ab") as stream:
                stream.write(raw)

    def snapshot(self):
        with self.lock:
            self._trim()
            return deepcopy([event for _, event in self.events])

    def subscribe(self, listener):
        with self.lock:
            self.listeners.append(listener)

        def unsubscribe():
            with self.lock:
                if listener in self.listeners:
                    self.listeners.remove(listener)

        return unsubscribe

    def health(self):
        with self.lock:
            self._trim()
            return {
                "retained_events": len(self.events),
                "evicted_events": self.evicted,
                "history_start_seq": self.events[0][1].get("seq") if self.events else None,
                "log_errors": self.log_errors,
                "listener_errors": self.listener_errors,
                "retention": dict(self.limits),
            }
