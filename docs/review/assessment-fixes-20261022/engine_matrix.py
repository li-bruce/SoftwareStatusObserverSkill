"""Compare accepted declarations with the real engine, including competing handlers."""
from copy import deepcopy
import itertools
import json
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools'))
from test_assessment_fixes import EngineTests
from bo_stategraph import BOStateGraph
from transitions import MachineError
from transitions.extensions import HierarchicalMachine


def main():
    cases, unsupported, skipped, failures=0,0,0,[]
    states=['idle',{'name':'work','initial':'a','children':['a','b']},'done']
    values=['idle','work_a','work_b','done']
    sources=['*','idle','work','work_a','work_b','done']
    targets=['idle','work','work_a','work_b','done',None]
    declarations=[[{'source':s,'dest':t,'trigger':'go'}] for s,t in itertools.product(sources,targets)]
    declarations += [[{'source':a,'dest':'work_a','trigger':'go'},
                       {'source':b,'dest':'done','trigger':'go'}] for a,b in itertools.product(sources,sources)]
    for initial,transitions in itertools.product(values,declarations):
        m=EngineTests().fixture(states,initial,transitions,values)
        try:graph=BOStateGraph(m,build_id='b')
        except ValueError: unsupported+=1;continue
        holder=SimpleNamespace()
        HierarchicalMachine(holder,states=states,initial=initial,transitions=transitions,auto_transitions=False)
        graph.bo_observe('a',state=deepcopy(holder.state),context={},revision=0,evidence_id='e0',build_id='b')
        try: executed=holder.go()
        except MachineError:skipped+=1;continue
        if not executed:skipped+=1;continue
        cases+=1
        outcome=graph.bo_observe('a',state=holder.state,context={},revision=1,evidence_id='e1',build_id='b',event='go')
        if outcome['status']!='observed':failures.append({'initial':initial,'transitions':transitions,'actual':holder.state,'outcome':outcome})
    result={'executed':cases,'unsupported':unsupported,'unhandled':skipped,'failures':failures}
    (Path(__file__).parent/'engine-matrix-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))
    assert not failures


if __name__=='__main__':main()
