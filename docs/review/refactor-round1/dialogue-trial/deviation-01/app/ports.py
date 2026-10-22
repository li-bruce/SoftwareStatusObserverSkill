"""Optional, failure-isolated observation port owned by the application."""
class EventPort:
    def __init__(self, callback=None):
        self.callback = callback
        self.errors = 0

    def bo_emit(self, node, phase, context, builder):
        if self.callback is None:
            return
        try:
            self.callback(node, phase, context, builder())
        except Exception:
            self.errors += 1
