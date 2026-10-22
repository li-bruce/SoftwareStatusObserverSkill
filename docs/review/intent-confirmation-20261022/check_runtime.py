"""Read the real public export and saved recordings from the running trial."""
import argparse
import json
from pathlib import Path
import sys
import urllib.request


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--project',type=Path,default=Path(__file__).resolve().parents[4]/'project-flow-trial-20261022')
    parser.add_argument('--url',default='http://127.0.0.1:8870')
    parser.add_argument('--label',required=True)
    args=parser.parse_args()
    sys.path.insert(0,str(args.project))
    from bo_stategraph import bo_validate_export
    out=Path(__file__).parent/'browser'/args.label;out.mkdir(parents=True,exist_ok=False)
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    def get(path):
        with opener.open(args.url+path,timeout=10) as response:return json.load(response)
    def save(name,value):(out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8')
    export=get('/api/stategraph/export');save('export.json',export)
    bo_validate_export(export)
    listing=get('/api/recordings');save('recordings-list.json',listing)
    report={'export_valid':True,'nodes':len(export['model']['nodes']),'instances':len(export.get('instances',[])),'recordings':[]}
    for item in listing['recordings']:
        record=get('/api/recordings/'+item['id']);save('recording-'+item['id']+'.json',record)
        ids={c['attempt'] for c in record.get('final',{}).get('machine',{}).get('configurations',[])}
        unbound=[e['id'] for e in record['events'] if e.get('attempt') not in ids or e.get('entity')!=e.get('attempt')]
        report['recordings'].append({'id':item['id'],'events':len(record['events']),'keys':list(record),'event_keys':list(record['events'][0]) if record['events'] else [],'gaps':record.get('gaps',[]),'unbound_events':unbound,'value_changes':sum('before' in e.get('outputs',{}) and 'after' in e.get('outputs',{}) for e in record['events'])})
        assert not unbound,unbound
    save('report.json',report)
    print(json.dumps(report,ensure_ascii=True))


if __name__=='__main__':main()
