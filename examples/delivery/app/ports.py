"""Application-owned optional diagnostics boundary; no generated graph types."""
from typing import Callable


class Events:
    def __init__(self, callback: Callable | None = None):
        self.callback = callback
        self.errors = 0

    def emit(self, node: str, phase: str, payload: Callable[[], dict]) -> None:
        if self.callback is None:
            return
        try:
            self.callback(node, phase, payload())
        except Exception:
            self.errors += 1
