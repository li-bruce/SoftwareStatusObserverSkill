"""Public collector adapter, with bounded event history and removable collection."""
import json
from pathlib import Path
import time
import uuid
from app.ports import TracePort
from bo_stategraph import BOStateGraph
from observer_runtime.semantic_probe import Pins, Trace
from observer_runtime.bo_retention import EventHistory


class BOObserver:
    def __init__(self, root: Path, model: dict, build_id: str, mode: str='on', event_dir=None):
        self.mode=mode
        self.graph=BOStateGraph(model,build_id=build_id,mode='drive')
        self.events=EventHistory(project_root=root,path=Path(event_dir or root/'data')/'events.jsonl' if mode=='on' else None)
        self.pins=Pins(model,build_id,enabled=mode=='on',sink=self.write)

    def write(self, text: str):
        self.events.append(json.loads(text))

    def trace(self, entity: str, attempt: str) -> TracePort:
        if self.mode=='fault':
            def broken(*args,**kwargs):
                raise RuntimeError('injected collector failure')
            return TracePort(broken)
        return TracePort(Trace(self.pins,entity,attempt).record) if self.mode=='on' else TracePort()

    def snapshot(self):
        self.pins.flush()
        return self.events.snapshot()

    def bo_http(self, endpoint, method, path, arguments, status):
        """Observe the real response; never record cookies or raw request bodies."""
        groups={
            'session':'sessions','login':'sessions','logout':'sessions',
            'files':'file_access','upload':'file_access','download':'file_access','review':'file_access',
            'messages':'messages','read_message':'messages',
            'index':'interface','favicon':'interface','health':'interface','asset':'interface',
        }
        node=groups.get(endpoint)
        if node is None:
            return  # Observer endpoints never become business events.
        self.trace('application',uuid.uuid4().hex).bo_record(
            node,endpoint,{'param_version':1,'epoch':1,'clock':time.time()},
            lambda:{'inputs':{'request':method+' '+path,'arguments':json.dumps(arguments,ensure_ascii=False,sort_keys=True)},
                    'outputs':{'status':status}},scope='application')

    def health(self):
        return {**self.pins.health(),**self.events.health(),'mode':self.mode}

    def close(self):
        self.pins.close()
