"""Check exact event/frame identity and state transitions in a saved trial recording."""
import argparse
import json
from pathlib import Path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('recording',type=Path)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    data=json.loads(args.recording.read_text(encoding='utf8'))
    events=data['events'];raw=data.get('runtime_frames',{})
    frames={f['event_id']:f for f in raw.get('frames',[])}
    errors=[];states=set()
    if raw.get('schema')!='stategraph-runtime-frames/v1':errors.append('missing_or_wrong_frame_protocol')
    for event in events:
        frame=frames.get(event['id'])
        if frame is None:
            errors.append('missing_frame:'+event['id']);continue
        for key in ('run_id','build_id','revision'):
            if key not in event or frame.get(key)!=event[key]:errors.append('mismatched_'+key+':'+event['id'])
        configurations=frame.get('machine',{}).get('configurations',[])
        match=[c for c in configurations if c.get('attempt')==event['attempt']]
        if len(match)!=1:
            errors.append('wrong_instance:'+event['id']);continue
        state=match[0]['phase'];states.add(state)
        if event['node']=='operation_checking' and state!='checking':errors.append('future_state_used_for_enter:'+event['id'])
        if event['node']=='operation_result' and state!=event.get('outputs',{}).get('state'):errors.append('result_state_disagrees:'+event['id'])
        if frame['machine'].get('state_revision')!=frame.get('revision'):errors.append('frame_revision_disagrees:'+event['id'])
    if not {'checking','completed','rejected'}<=states:errors.append('missing_required_states:'+','.join(sorted({'checking','completed','rejected'}-states)))
    report={'recording':str(args.recording),'events':len(events),'frames':len(frames),'states':sorted(states),'errors':errors,'passed':not errors}
    if args.out.exists():raise FileExistsError(args.out)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'passed':report['passed'],'events':len(events),'frames':len(frames),'states':sorted(states),'error_count':len(errors)}))
    raise SystemExit(0 if report['passed'] else 1)


if __name__=='__main__':main()
