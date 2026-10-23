"""Observer reads/reports must not become business steps or hide business work."""
import asyncio
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'skills/business-observer/scripts'))
from code_structure import scan, enrich
from implementation_coverage import static_errors, observer_reclassifications, protected_errors, protected_captures
from observation_scope import bo_internal, bo_is_internal, endpoint_paths, observer_exclusion, observer_route
from semantic_probe import Pins
from probe import Probe


SOURCE = '''
def upload(note):
    bo_report(note)
    return notify(note)

def notify(note):
    return note

def bo_report(value):
    return value

@app.get('/api/view')
def view():
    return {'events': []}

@app.post('/api/login')
def login(username):
    return username

@app.get('/api/view')
@app.post('/api/login')
def mixed():
    return None
'''


def node(ident, symbol):
    return {'id':ident,'label':ident,'kind':'action','layer':'business',
            'source':{'path':'app.py','symbol':symbol},'capture':{'in':{'note':'string'},'out':{}}}


class ObserverNoiseTests(unittest.TestCase):
    def setUp(self):
        (ROOT/'.validation').mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'.validation')
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        (self.root/'app.py').write_text(SOURCE,encoding='utf-8')
        self.index=scan(self.root,['app.py'])
        self.model={'revision':'test','nodes':[node('upload','upload'),node('notify','notify')],
                    'edges':[],'graph_roots':['upload','notify'],'implementation':{
                        'schema':'bo-implementation/v1','features':[],'support':{},'excluded':{
                            'app.py::bo_report':{'category':'observer','reason':"Send observation facts only"}}}}

    def pins(self, model=None, sink=None):
        events=[]
        pins=Pins(model or self.model,'build',sink=sink or (lambda text:events.append(json.loads(text))))
        self.addCleanup(pins.close)
        return pins,pins.attempt('entity'),events

    def test_excluded_report_is_not_reintroduced_by_static_calls(self):
        model=enrich(self.model,self.index,depth=3)
        symbols={n['source']['symbol'] for n in model['nodes'] if n.get('source')}
        self.assertNotIn('bo_report',symbols)
        self.assertIn('notify',symbols)
        self.assertIn('app.py::bo_report',self.index['symbols'])  # Still inspectable.
        self.assertTrue(any(e['type']=='flow' for e in model['edges']))

    def test_builder_cannot_recursively_report_itself(self):
        pins,trace,events=self.pins()
        def payload():
            trace.record('notify','return',{},lambda:{'inputs':{'note':'observer work'}})
            return {'inputs':{'note':'actual upload'}}
        trace.record('upload','commit',{},payload)
        self.assertTrue(pins.flush())
        self.assertEqual([e['node'] for e in events],['upload'])
        self.assertEqual(pins.health()['suppressed_internal'],1)

    def test_sink_reporting_cannot_feed_back_into_collector(self):
        events=[]
        def sink(text):
            events.append(json.loads(text))
            if len(events)==1:
                trace.record('notify','return',{},lambda:{'inputs':{'note':'sink report'}})
        pins,trace,_=self.pins(sink=sink)
        trace.record('upload','commit',{},lambda:{'inputs':{'note':'upload'}})
        self.assertTrue(pins.flush())
        self.assertEqual(len(events),1)

    def test_explicit_observer_node_skips_payload_and_sequence(self):
        model=copy.deepcopy(self.model)
        model['nodes'].append(node('report','bo_report'))
        pins,trace,events=self.pins(model)
        calls=[]
        trace.record('report','return',{},lambda:calls.append(True))
        self.assertEqual(calls,[])
        self.assertEqual(pins.seq,0)
        self.assertEqual(events,[])

    def test_business_notification_is_still_recorded(self):
        pins,trace,events=self.pins()
        trace.record('notify','commit',{},lambda:{'inputs':{'note':"Message for the reviewer"}})
        self.assertTrue(pins.flush())
        self.assertEqual(events[0]['inputs']['note'],"Message for the reviewer")

    def test_suppression_is_task_local_and_restored_on_error(self):
        async def run():
            entered=asyncio.Event()
            release=asyncio.Event()
            async def observation():
                with bo_internal():
                    entered.set()
                    await release.wait()
                    self.assertTrue(bo_is_internal())
            task=asyncio.create_task(observation())
            await entered.wait()
            self.assertFalse(bo_is_internal())
            release.set()
            await task
        asyncio.run(run())
        with self.assertRaises(RuntimeError):
            with bo_internal(): raise RuntimeError('observer failure')
        self.assertFalse(bo_is_internal())

    def test_legacy_probe_sink_is_also_suppressed(self):
        events=[]
        def emit():
            return probe.emit(kind='fact',node_id='business',entity_id='e',request_id='r',attempt_id='a',tx_id='t',payload={})
        def sink(text):
            events.append(text)
            if len(events)==1: emit()
        probe=Probe(build_id='b',model_revision='r',fields={'fact':[]},nodes=['business'],sink=sink)
        self.addCleanup(probe.close)
        emit()
        self.assertTrue(probe.flush())
        self.assertEqual(len(events),1)

    def test_observer_routes_need_exact_explicit_classification(self):
        symbol=self.index['symbols']['app.py::view']
        item={'category':'observer','reason':"Graph polling",'routes':['/api/view']}
        self.assertTrue(observer_exclusion(symbol,item))
        self.assertFalse(observer_exclusion(symbol,{'category':'observer','reason':"Graph polling"}))
        self.assertFalse(observer_exclusion(self.index['symbols']['app.py::login'],item))
        self.assertFalse(observer_exclusion(self.index['symbols']['app.py::mixed'],item))
        self.assertTrue(observer_route('/api/recordings/start?x=1'))
        self.assertFalse(observer_route('/api/view-orders'))
        self.assertFalse(observer_route('/api/messages'))

    def migration(self):
        before=copy.deepcopy(self.model)
        before['nodes']=[node('developer','view')]
        feature={'id':'developer','sources':['app.py::view'],'nodes':['developer'],
                 'parameters':[],'cases':[]}
        before['implementation']['features']=[feature]
        after=copy.deepcopy(before)
        after['nodes']=[]
        after['implementation']['features']=[]
        after['implementation']['excluded']['app.py::view']={
            'category':'observer','reason':"Return graph only",'routes':['/api/view']}
        review={'developer':{'sources':['app.py::view'],'reason':"Correct the observation endpoint's mistaken business mapping"}}
        return before,after,review

    def test_reclassification_needs_review_and_unchanged_source(self):
        before,after,review=self.migration()
        approved,errors=observer_reclassifications(before,after,self.index,review,before_index=self.index)
        self.assertEqual(errors,[])
        self.assertEqual(approved,{'developer'})
        self.assertEqual(protected_errors(before['implementation'],after['implementation'],observer_features=approved),[])
        self.assertEqual(protected_captures(before,after,observer_features=approved),[])
        self.assertTrue(protected_errors(before['implementation'],after['implementation']))
        changed=copy.deepcopy(self.index)
        changed['symbols']['app.py::view']['ast_hash']='modified'
        self.assertTrue(observer_reclassifications(before,after,changed,review,before_index=self.index)[1])

    def test_business_feature_cannot_use_observer_reclassification(self):
        before,after,review=self.migration()
        before['implementation']['features'][0]['sources'].append('app.py::login')
        review['developer']['sources'].append('app.py::login')
        after['implementation']['excluded']['app.py::login']={
            'category':'observer','reason':"This must not hide login",'routes':['/api/login']}
        self.assertTrue(observer_reclassifications(before,after,self.index,review,before_index=self.index)[1])

    def test_optional_migration_preserves_partial_review_checks(self):
        self.assertEqual(observer_reclassifications({}, {}, {}, None), (set(), []))
        for invalid in ([], 'waive', True):
            self.assertTrue(observer_reclassifications({}, {}, {}, invalid)[1])
        before,after,review=self.migration()
        self.assertTrue(observer_reclassifications(before,after,{},review)[1])

    def test_observer_feature_is_rejected_but_login_exclusion_is_not_allowed(self):
        before,after,_=self.migration()
        errors=static_errors(before['implementation'],before,self.index)
        self.assertTrue(any('observer_endpoint_is_not_business' in e for e in errors if isinstance(e,dict)))
        after['implementation']['excluded']['app.py::login']={
            'category':'observer','reason':"Not a valid observation route",'routes':['/api/login']}
        errors=static_errors(after['implementation'],after,self.index)
        self.assertTrue(any(e.get('entrypoint_cannot_be_excluded')=='app.py::login' for e in errors if isinstance(e,dict)))


if __name__=='__main__': unittest.main()
