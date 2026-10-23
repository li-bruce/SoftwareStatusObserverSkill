"""Exercise real HTTP graph controls without generating business events."""
import json
from pathlib import Path
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from fastapi.testclient import TestClient
from integrations.server import create_app


def check(mode):
    model=json.loads((ROOT/'behavior.json').read_text(encoding='utf-8'))
    observers={sid for sid,item in model['implementation']['excluded'].items() if item['category']=='observer'}
    mapped={n['source']['path']+'::'+n['source']['symbol'] for n in model['nodes'] if n.get('source')}
    assert not mapped & observers,mapped & observers
    assert {'app/service.py::ReviewService.bo_trace','integrations/server.py::create_app.bo_view'} <= observers
    with tempfile.TemporaryDirectory(dir=ROOT/'scratch') as directory:
        app=create_app(directory,probe_mode=mode)
        with TestClient(app) as client:
            before=len(app.state.observer.snapshot())
            for _ in range(5):
                for path in ('/api/view','/api/design','/api/stategraph','/api/stategraph/export',
                             '/api/source?node=upload','/api/preferences','/api/recordings','/graph','/viewer.js'):
                    response=client.get(path)
                    assert response.status_code==200,(path,response.status_code)
            if mode=='on':
                assert client.post('/api/recordings/start',json={'label':'只操作观测界面'}).status_code==200
                for _ in range(5): assert client.get('/api/view').status_code==200
                empty_record=client.post('/api/recordings/stop').json()
                records=app.state.recordings.list()['recordings']
                empty=app.state.recordings.get(records[0]['id'])
                assert empty['events']==[],empty['events']
                assert client.post('/api/recordings/start',json={'label':'实际业务'}).status_code==200
            after=len(app.state.observer.snapshot())
            assert after==before,(mode,before,after)
            assert client.post('/api/login',json={'username':'uploader','password':'upload-demo'}).status_code==200
            submitted=client.post('/api/files',params={'filename':'观测排除回归.txt','note':'给审核者的消息必须保留'},content=b'noise regression')
            assert submitted.status_code==200,submitted.text
            ident=submitted.json()['id']
            assert client.post('/api/login',json={'username':'reviewer','password':'review-demo'}).status_code==200
            messages=client.get('/api/messages').json()['messages']
            assert len(messages)==1,messages
            assert client.post(f'/api/files/{ident}/review',json={'decision':'approve','note':'业务通过'}).status_code==200
            events=app.state.observer.snapshot()
            if mode=='on':
                assert {'sessions','upload','notify','review','messages'} <= {e['node'] for e in events}
                assert not any(e['node']=='developer' for e in events)
                assert any(e.get('inputs',{}).get('note')=='给审核者的消息必须保留' for e in events)
                response=client.post('/api/recordings/stop')
                assert response.status_code==200,response.text
                records=app.state.recordings.list()['recordings']
                recorded=[app.state.recordings.get(r['id']) for r in records if r['label']=='实际业务'][0]
                assert {e['id'] for e in recorded['events']}=={e['id'] for e in events}
            else:
                assert events==[],events
            with app.state.store.connection() as db:
                row=dict(db.execute('SELECT status,note FROM submissions WHERE id=?',(ident,)).fetchone())
            assert row=={'status':'approved','note':'给审核者的消息必须保留'},row
            return {'mode':mode,'observer_reads':50 if mode=='on' else 45,'observer_events':after-before,
                    'business_events':len(events),'state':row['status'],'passed':True}


if __name__=='__main__':
    result={'passed':True,'cases':[check(mode) for mode in ('on','off','fault')]}
    path=ROOT/'review/observer-noise-results.json'
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))
