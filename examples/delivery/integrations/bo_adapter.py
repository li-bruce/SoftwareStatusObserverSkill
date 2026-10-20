"""business-observer integration. BO/bo_ names identify the optional adapter."""
import json
from observer_generated.runtime.semantic_probe import Pins, Trace


class BOAdapter:
    def __init__(self, model, build_id, *, enabled=True, fault=False):
        self.bo_events = []
        self.bo_traces = {}
        self.bo_refs = {}
        def sink(line):
            if fault:
                raise OSError('injected observer sink failure')
            self.bo_events.append(json.loads(line))
        self.bo_pins = Pins(model, build_id, enabled=enabled, sink=sink)

    def __call__(self, node, phase, payload):
        attempt = payload['attempt']
        trace = self.bo_traces.setdefault(attempt, Trace(self.bo_pins,'delivery:1',attempt))
        refs = self.bo_refs.setdefault(attempt,{})
        depends = [(refs[n],'recheck' if node=='recheck' else 'data')
                   for n in payload.get('uses',[]) if n in refs]
        eid = trace.record(node,phase,payload['basis'],lambda:payload,depends=depends,
                           call_id=payload.get('call_id'), parent_call_id=payload.get('parent_call_id'))
        if eid:
            refs[node]=eid

    def snapshot(self):
        self.bo_pins.flush(3)
        return list(self.bo_events)

    def close(self):
        self.bo_pins.close()
