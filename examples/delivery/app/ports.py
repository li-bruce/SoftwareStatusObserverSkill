"""Application-owned optional diagnostics boundary; no generated graph types."""
from typing import Callable


class BOEvents:
    def __init__(self, callback: Callable | None = None):
        self.callback = callback
        self.errors = 0

    def bo_emit(self, node: str, phase: str, payload: Callable[[], dict]) -> None:
        if self.callback is None:
            return
        try:
            gate = getattr(self.callback, 'bo_should_capture', None)
            if gate is not None and not gate(node):
                return
            self.callback(node, phase, payload())
        except Exception:
            self.errors += 1

    emit = bo_emit  # Compatibility for earlier adapters.

Events = BOEvents
