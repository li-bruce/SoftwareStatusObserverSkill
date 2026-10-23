"""Optional observations. The application never depends on their success."""
from collections.abc import Callable


class BOTracePort:
    def __init__(self, receiver: Callable | None = None):
        self.receiver = receiver
        self.errors = 0

    def bo_record(self, node, phase, basis, builder, **kwargs):
        if self.receiver is None:
            return None
        try:
            return self.receiver(node, phase, basis, builder, **kwargs)
        except Exception:
            self.errors += 1
            return None

    record = bo_record  # Compatibility for earlier adapters.


TracePort = BOTracePort

def no_trace(entity: str, attempt: str) -> TracePort:
    return TracePort()


def bo_record_change(factory, store, clock, node, builder):
    """Optional observation after a committed command; payload work is isolated."""
    try:
        snapshot = store.snapshot()
        trace = factory('application', 'commands')
        trace.bo_record(node, 'change', {'param_version':0, 'epoch':snapshot['epoch'], 'clock':float(clock())},
                        builder, scope='application')
    except Exception:
        pass  # Collection must not turn a successful business commit into failure.
