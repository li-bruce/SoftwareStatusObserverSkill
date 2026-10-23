"""Application state: lifecycle, concurrent activities and shared capacity.

The graph uses the same activity IDs, resource requirements and join as execution.
The observer does not decide when work starts or when the lifecycle may advance.
"""
from copy import deepcopy
import json
from pathlib import Path
from enum import StrEnum
import importlib.metadata
import threading
from types import SimpleNamespace
from transitions import Machine
from .bo_contracts import validate_runtime_definition

BO_DEFINITION=json.loads(Path(__file__).with_name('machine.json').read_text(encoding='utf-8'))
validate_runtime_definition(BO_DEFINITION)


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


STATES = BO_DEFINITION['states']
EXECUTION = BO_DEFINITION['execution']
TRANSITIONS = BO_DEFINITION['transitions']
TERMINAL={'succeeded','rejected','failed','cancelled'}


def completed(execution: dict | None, attempt: str | None, param_version: int | None) -> bool:
    if not execution or execution.get('attempt')!=attempt or execution.get('param_version')!=param_version:
        return False
    return (execution.get('join',{}).get('state')=='passed'
            and all(execution.get('activities',{}).get(a)=='succeeded' for a in EXECUTION['join']['requires'])
            and set(execution.get('resources',{}))=={r['id'] for r in EXECUTION['resources']}
            and all(r.get('available')==r.get('capacity') and not r.get('holders') for r in execution['resources'].values()))


def advance(state: str,event: str,execution=None,*,attempt=None,param_version=None) -> str:
    validate_runtime_definition(definition(), loaded_engine='transitions.Machine',
        loaded_version=importlib.metadata.version('transitions'), guard_names={'execution_complete'})
    holder=SimpleNamespace(execution_complete=lambda:completed(execution,attempt,param_version))
    Machine(holder,states=STATES,transitions=TRANSITIONS,initial=Phase(state).value,
            auto_transitions=False,model_attribute='phase')
    if not holder.trigger(event):raise ValueError("Both checks must pass in this run before committing")
    return holder.phase


def definition() -> dict:
    return deepcopy(BO_DEFINITION)


def execution_record(state, *, phase, clock, build_id=None, disposition='current'):
    """Persist the whole actual run, including a run waiting before any worker starts."""
    context = {'param_version': state['param_version'], 'clock': clock,
               'capacity': state['resources']['workers']['capacity'], 'execution': deepcopy(state)}
    return {**deepcopy(state), 'phase': phase, 'disposition': disposition,
            'run_build_id': build_id, 'context': context}


def advance_record(job, event, store):
    """Advance within the caller's transaction; storage owns the SQL operation."""
    previous = job['state']
    job['state'] = advance(previous, event, job.get('execution'),
                           attempt=job['attempt'], param_version=job['param_version'])
    store.record_transition(event, previous, job['state'], job['attempt'], job['param_version'])
    if event != 'edit':
        stored = store.execution(job['attempt'])
        if stored:
            context = {**stored.get('context', {}), 'clock': job['clock']}
            store.update_execution(job['attempt'], phase=job['state'], context=context)


def recover_records(job, records):
    """Preserve the last worker facts, but mark them unavailable after process loss."""
    interrupted = []
    for run in records:
        unfinished = any(s in ('running','waiting') for s in run['activities'].values()) or (
            run['phase']=='checking' and any(s=='pending' for s in run['activities'].values()))
        if unfinished:
            interrupted.append({**run, 'phase':'failed', 'disposition':'interrupted',
                                'source_status':'interrupted_workers'})
    if job['state']=='checking': job.update(state='failed',reason='process_restarted')
    return interrupted


class ActivityExecution:
    """Internal state of one run. Activity IDs are scoped by attempt and version."""
    def __init__(self,capacity: int=2,*,attempt='direct',param_version=1,progress=None):
        resource=EXECUTION['resources'][0]
        if type(capacity) is not int or not resource['min']<=capacity<=resource['max']:
            raise ValueError("Capacity must be 1 or 2")
        if not isinstance(attempt,str) or not attempt or type(param_version) is not int or param_version<1:
            raise ValueError("Invalid run ID or parameter version")
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
                raise RuntimeError("Occupied slots do not match running checks")
            if type(r['available']) is not int or r['available']<0 or r['available']+sum(held.values())!=r['capacity']:
                raise RuntimeError("Free and occupied slots do not add up to capacity")

    def start(self,activity):
        spec=next((a for a in self.spec['activities'] if a['id']==activity),None)
        if spec is None:raise ValueError("Unknown check")
        with self.changed:
            if self.activities[activity]!='pending':raise ValueError("This check has already started")
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
            if self.activities.get(activity)!='running':raise ValueError("Cannot finish a check that has not started")
            if type(passed) is not bool or type(error) is not bool:raise ValueError("Check result must be Boolean")
            before=self.body();spec=next(a for a in self.spec['activities'] if a['id']==activity)
            for rid,n in spec['requires'].items():
                self.resources[rid]['available']+=n;self.resources[rid]['holders'].remove(activity)
            self.activities[activity]=ActivityState.FAILED if error else ActivityState.SUCCEEDED if passed else ActivityState.REJECTED
            if all(self.activities[a] in TERMINAL for a in self.spec['join']['requires']):self.join_state='enabled'
            self.record('finish',activity,before)

    def join(self) -> bool:
        with self.changed:
            if self.join_state!='enabled':raise ValueError("Cannot join before all checks complete")
            before=self.body()
            passed=all(self.activities[a]=='succeeded' for a in self.spec['join']['requires'])
            self.join_state='passed' if passed else 'rejected';self.record('join',self.spec['join']['id'],before)
            return passed

    def abort(self):
        with self.changed:
            if any(s=='running' for s in self.activities.values()):raise ValueError("Running checks must finish and release their slots first")
            before=self.body()
            for a,s in self.activities.items():
                if s not in TERMINAL:self.activities[a]=ActivityState.CANCELLED
            self.join_state='rejected';self.record('abort',self.spec['join']['id'],before)
