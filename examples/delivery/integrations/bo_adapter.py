"""business-observer integration. BO/bo_ names identify the optional adapter."""
import json
from collections import OrderedDict
from pathlib import Path
import threading
from observer_generated.runtime.bo_retention import EventHistory
from observer_generated.runtime.semantic_probe import Pins, Trace
from bo_stategraph import BOStateGraph


class BOAdapter:
    def __init__(self, model, build_id, *, enabled=True, fault=False):
        self.bo_graph = BOStateGraph(model, build_id=build_id, mode='drive')
        self.bo_events = EventHistory(project_root=Path(__file__).resolve().parents[1])
        self.bo_refs = OrderedDict()
        self.bo_reference_evictions = 0
        self.bo_lock = threading.Lock()
        def sink(line):
            if fault:
                raise OSError('injected observer sink failure')
            self.bo_events.append(json.loads(line))
        self.bo_pins = Pins(model, build_id, enabled=enabled, sink=sink)

    def bo_should_capture(self, node):
        if not self.bo_pins.enabled or self.bo_pins.closed:
            return False
        if self.bo_pins.bo_scope is not None and node not in self.bo_pins.bo_scope:
            self.bo_pins.bo_filtered += 1
            return False
        return True

    def __call__(self, node, phase, payload):
        attempt = payload['attempt']
        trace = Trace(self.bo_pins,'delivery:1',attempt)
        with self.bo_lock:
            depends = [(self.bo_refs[(attempt,n)],'recheck' if node=='recheck' else 'data')
                       for n in payload.get('uses',[]) if (attempt,n) in self.bo_refs]
            eid = trace.record(node,phase,payload['basis'],lambda:payload,depends=depends,
                               call_id=payload.get('call_id'), parent_call_id=payload.get('parent_call_id'))
            if eid:
                self.bo_refs[(attempt,node)] = eid
                self.bo_refs.move_to_end((attempt,node))
                while len(self.bo_refs) > self.bo_events.limits['memory_events']:
                    self.bo_refs.popitem(last=False)
                    self.bo_reference_evictions += 1

    def health(self):
        return {**self.bo_pins.health(), **self.bo_events.health(),
                'reference_evictions': self.bo_reference_evictions}

    def snapshot(self):
        self.bo_pins.flush(3)
        return self.bo_events.snapshot()

    def close(self):
        self.bo_pins.close()
