"""Application state: lifecycle, concurrent activities and shared capacity.

The graph uses the same activity IDs, resource requirements and join as execution.
The observer does not decide when work starts or when the lifecycle may advance.
"""
from copy import deepcopy
from enum import StrEnum
import threading
from types import SimpleNamespace
from transitions import Machine


class Phase(StrEnum):
    DRAFT='draft'
    WAITING='waiting'
    CHECKING='checking'
    READY='ready'
    FAILED='failed'
    CANCELLED='cancelled'
    COMPLETED='completed'


class ActivityState(StrEnum):
    PENDING='pending'
    WAITING='waiting'
    RUNNING='running'
    SUCCEEDED='succeeded'
    REJECTED='rejected'
    FAILED='failed'
    CANCELLED='cancelled'


STATES=[p.value for p in Phase]
EXECUTION={
    'schema':'activity-graph/v1','within':'checking','parent':'flow.checks',
    'activity_state_type':'ActivityState','activity_states':[s.value for s in ActivityState],
    'activities':[
        {'id':'checksum','label':'计算内容摘要','source':{'path':'app/checks.py','symbol':'checksum'},'requires':{'workers':1}},
        {'id':'privacy','label':'检查敏感标记','source':{'path':'app/checks.py','symbol':'privacy_check'},'requires':{'workers':1}}],
    'resources':[{'id':'workers','label':'本次并发名额','scope':'run','capacity_field':'capacity','min':1,'max':2}],
    'join':{'id':'join','label':'确认检查结果','policy':'all','requires':['checksum','privacy'],
            'success_event':'checked','success_states':['ready','completed'],'guard':'execution_complete'},
    'source':{'path':'app/workflow.py','symbol':'ActivityExecution'},
}
TRANSITIONS=[
    {'trigger':'start','source':['draft','waiting','failed','ready'],'dest':'checking'},
    {'trigger':'block','source':['draft','waiting','failed','ready','checking'],'dest':'waiting'},
    {'trigger':'checked','source':'checking','dest':'ready','conditions':'execution_complete'},
    {'trigger':'fail','source':'checking','dest':'failed'},
    {'trigger':'publish','source':'ready','dest':'completed','conditions':'execution_complete'},
    {'trigger':'cancel','source':['draft','waiting','checking','ready','failed'],'dest':'cancelled'},
    {'trigger':'edit','source':['draft','waiting','checking','ready','failed','completed'],'dest':'draft'},
]
TERMINAL={'succeeded','rejected','failed','cancelled'}


def completed(execution: dict | None, attempt: str | None, param_version: int | None) -> bool:
    if not execution or execution.get('attempt')!=attempt or execution.get('param_version')!=param_version:
        return False
    return (execution.get('join',{}).get('state')=='passed'
            and all(execution.get('activities',{}).get(a)=='succeeded' for a in EXECUTION['join']['requires'])
            and set(execution.get('resources',{}))=={r['id'] for r in EXECUTION['resources']}
            and all(r.get('available')==r.get('capacity') and not r.get('holders') for r in execution['resources'].values()))


def advance(state: str,event: str,execution=None,*,attempt=None,param_version=None) -> str:
    holder=SimpleNamespace(execution_complete=lambda:completed(execution,attempt,param_version))
    Machine(holder,states=STATES,transitions=TRANSITIONS,initial=Phase(state).value,
            auto_transitions=False,model_attribute='phase')
    if not holder.trigger(event):raise ValueError('两项检查尚未在本次运行中通过，不能继续提交')
    return holder.phase


def definition() -> dict:
    return {'engine':'transitions.Machine','version':'0.9.3','initial':'draft',
            'state_type':'Phase','states':STATES,'values':STATES,'transitions':deepcopy(TRANSITIONS),
            'events':{t['trigger']:{'payload':{}} for t in TRANSITIONS},
            'event_labels':dict(zip(['start','block','checked','fail','publish','cancel','edit'],
                                   ['开始检查','等待有效授权','两项检查通过','检查失败','提交成功','取消','修改内容'])),
            'context':{'param_version':{'type':'integer','min':1},'clock':{'type':'integer','min':0},
                       'capacity':{'type':'integer','min':1,'max':2},'execution':{'type':'object','schema':'activity-graph/v1'}},
            'guards':{'execution_complete':{'description':'本次运行的两项检查均已通过，且占用的名额已经归还',
                                            'source':{'path':'app/workflow.py','symbol':'completed'}}},
            'labels':dict(zip(STATES,['待检查','等待执行授权','正在检查','可以提交','检查失败','已取消','已交付'])),
            'source':{'path':'app/workflow.py','symbol':'advance'},'execution':deepcopy(EXECUTION)}


class ActivityExecution:
    """Internal state of one run. Activity IDs are scoped by attempt and version."""
    def __init__(self,capacity: int=2,*,attempt='direct',param_version=1,progress=None):
        resource=EXECUTION['resources'][0]
        if type(capacity) is not int or not resource['min']<=capacity<=resource['max']:
            raise ValueError('并发名额必须是 1 或 2')
        if not isinstance(attempt,str) or not attempt or type(param_version) is not int or param_version<1:
            raise ValueError('运行编号和参数版本无效')
        self.spec=deepcopy(EXECUTION)
        self.attempt,self.param_version,self.progress=attempt,param_version,progress
        self.activities: dict[str,ActivityState]={a['id']:ActivityState.PENDING for a in self.spec['activities']}
        self.resources={resource['id']:{'capacity':capacity,'available':capacity,'holders':[]}}
        self.join_state='waiting';self.revision=0;self.journal=[];self.changed=threading.Condition()

    def body(self):
        return {'activities':dict(self.activities),'resources':deepcopy(self.resources),
                'join':{'state':self.join_state,'pending':[a for a in self.spec['join']['requires'] if self.activities[a] not in TERMINAL]}}

    def snapshot(self):
        with self.changed:
            return {'attempt':self.attempt,'param_version':self.param_version,'revision':self.revision,
                    **self.body(),'journal':deepcopy(self.journal)}

    def record(self,event,activity,before):
        self.invariant();self.revision+=1
        self.journal.append({'seq':self.revision,'event':event,'activity':activity,'before':before,'after':self.body()})
        # Delivery never acquires this lock while holding a store transaction.
        if self.progress:self.progress(event,self.snapshot())
        self.changed.notify_all()

    def invariant(self):
        for resource in self.spec['resources']:
            rid=resource['id'];r=self.resources[rid]
            held={a['id']:a['requires'].get(rid,0) for a in self.spec['activities'] if self.activities[a['id']]=='running'}
            if set(r['holders'])!={a for a,n in held.items() if n} or len(set(r['holders']))!=len(r['holders']):
                raise RuntimeError('占用名额与运行中的检查不一致')
            if type(r['available']) is not int or r['available']<0 or r['available']+sum(held.values())!=r['capacity']:
                raise RuntimeError('可用名额与占用名额之和不等于总数')

    def start(self,activity):
        spec=next((a for a in self.spec['activities'] if a['id']==activity),None)
        if spec is None:raise ValueError('未知检查项目')
        with self.changed:
            if self.activities[activity]!='pending':raise ValueError('这项检查已开始，不能重复启动')
            while any(self.resources[r]['available']<n for r,n in spec['requires'].items()):
                if self.activities[activity]!='waiting':
                    before=self.body();self.activities[activity]=ActivityState.WAITING;self.record('wait',activity,before)
                self.changed.wait()
            before=self.body()
            for rid,n in spec['requires'].items():
                self.resources[rid]['available']-=n;self.resources[rid]['holders'].append(activity)
            self.activities[activity]=ActivityState.RUNNING;self.record('start',activity,before)

    def finish(self,activity,passed: bool,*,error=False):
        with self.changed:
            if self.activities.get(activity)!='running':raise ValueError('检查尚未开始，不能报告完成')
            if type(passed) is not bool or type(error) is not bool:raise ValueError('检查结果必须是布尔值')
            before=self.body();spec=next(a for a in self.spec['activities'] if a['id']==activity)
            for rid,n in spec['requires'].items():
                self.resources[rid]['available']+=n;self.resources[rid]['holders'].remove(activity)
            self.activities[activity]=ActivityState.FAILED if error else ActivityState.SUCCEEDED if passed else ActivityState.REJECTED
            if all(self.activities[a] in TERMINAL for a in self.spec['join']['requires']):self.join_state='enabled'
            self.record('finish',activity,before)

    def join(self) -> bool:
        with self.changed:
            if self.join_state!='enabled':raise ValueError('还有检查未完成，不能汇总结果')
            before=self.body()
            passed=all(self.activities[a]=='succeeded' for a in self.spec['join']['requires'])
            self.join_state='passed' if passed else 'rejected';self.record('join',self.spec['join']['id'],before)
            return passed

    def abort(self):
        with self.changed:
            if any(s=='running' for s in self.activities.values()):raise ValueError('正在执行的检查需要先结束并归还名额')
            before=self.body()
            for a,s in self.activities.items():
                if s not in TERMINAL:self.activities[a]=ActivityState.CANCELLED
            self.join_state='rejected';self.record('abort',self.spec['join']['id'],before)
