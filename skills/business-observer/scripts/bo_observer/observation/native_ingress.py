"""Merge native JSON events into an existing Pins stream without a second state store."""
from collections import OrderedDict
import json
from ..protocol import validate_event


class NativeIngress:
    def __init__(self, pins, project):
        self.pins, self.project = pins, project
        self.sequences, self.recent = {}, OrderedDict()

    def accept(self, value):
        p = self.pins
        event = validate_event(value, self.project, p.build_id)
        key = (event['run_id'], event['producer_id'])
        raw = json.dumps(event, sort_keys=True, ensure_ascii=False, allow_nan=False)
        if len(raw.encode()) > 24576:
            raise ValueError('native event too large')
        with p.lock:
            old = self.recent.get(event['id'])
            if old is not None:
                if old != raw: raise ValueError('conflicting duplicate event')
                return {'duplicate': True}
            previous = self.sequences.get(key, 0)
            if event['seq'] <= previous: raise ValueError('native event reordered')
            if key not in self.sequences and len(self.sequences) >= 256:
                raise ValueError('too many native producers for this recording session')
            if not p.enabled or p.closed:
                self._remember(value, key, raw)
                return {'recorded': False}
            if p.bo_scope is not None and event['node'] not in p.bo_scope:
                p.bo_filtered += 1
                self._remember(value, key, raw)
                return {'recorded': False}
            if p.queue.full():
                p.dropped += 1
                raise ValueError('observation queue is full')
            p.seq += 1
            p.dropped += max(0, value['seq']-previous-1)
            event.update(source_seq=event['seq'], seq=p.seq, stream_id=p.run_id)
            p.queue.put_nowait(json.dumps(event, ensure_ascii=False, allow_nan=False))
            self._remember(value, key, raw)
            return {'recorded': True, 'gap': max(0, value['seq']-previous-1)}

    def _remember(self, event, key, raw):
        self.sequences[key] = event['seq']
        self.recent[event['id']] = raw
        while len(self.recent) > 512: self.recent.popitem(last=False)
