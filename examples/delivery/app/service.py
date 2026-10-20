"""Application-owned commands. Core never imports graph/skill implementation."""
from app.checks import run_checks
from app.ports import Events
from app.store import Store
from app.workflow import advance, ActivityExecution, completed
import uuid


def eligible_grant(grant: dict, job: dict, events=None, parent_call_id=None) -> bool:
    conditions = {}
    def remember(name, value):
        conditions[name] = value
        return value
    allowed = (remember('project', grant['project'] == job['project'])
               and remember('actor', grant['actor'] == job['actor'])
               and remember('version', grant['version'] == job['param_version'])
               and remember('not_revoked', not grant['revoked'])
               and remember('not_expired', job['clock'] < grant['expires']))
    if events is not None:
        events.emit('grant', 'decision', lambda: {
            **observation(job, inputs={'grant_id': grant['id'], 'grant_version': grant['version'],
                          'param_version': job['param_version'], 'clock': job['clock'],
                          'expires': grant['expires']},
                          outputs={'allowed': allowed, 'conditions': dict(conditions),
                                   'evaluated': list(conditions)}),
            'call_id': uuid.uuid4().hex, 'parent_call_id': parent_call_id})
    return allowed


def authorized(job: dict, events=None) -> bool:
    call_id = uuid.uuid4().hex if events is not None else None
    evaluated = []
    allowed = False
    if job['role'] == 'engineer':
        for grant in job['grants']:
            evaluated.append(grant['id'])
            if eligible_grant(grant, job, events, call_id):
                allowed = True
                break
    if events is not None:
        events.emit('authorize', 'decision', lambda: {
            **observation(job, inputs={'role': job['role'], 'grants': len(job['grants'])},
                          outputs={'allowed': allowed, 'evaluated_grants': evaluated}),
            'call_id': call_id})
    return allowed


def observation(job: dict, inputs=None, outputs=None, uses=()) -> dict:
    return {'attempt': job['attempt'], 'basis': {k:job[k] for k in ('param_version','epoch','clock')},
            'inputs': inputs or {}, 'outputs': outputs or {}, 'uses': list(uses)}


class Delivery:
    def __init__(self, store: Store, events: Events | None = None, checker=run_checks):
        self.store, self.events, self.checker = store, events or Events(), checker

    def transition(self, job: dict, event: str):
        old=job['state']
        job['state']=advance(old,event,job.get('execution'),attempt=job['attempt'],param_version=job['param_version'])
        self.store.db.execute('INSERT INTO journal(event,source,target,attempt,param_version) VALUES (?,?,?,?,?)',
                              (event,old,job['state'],job['attempt'],job['param_version']))
        if event!='edit':self.store.update_execution(job['attempt'],phase=job['state'])

    def command(self, action: str, **values) -> dict:
        with self.store.transaction():
            job = self.store.get()
            if action == 'edit':
                content = values['content']
                if not isinstance(content,str) or not 1 <= len(content) <= 4096:
                    raise ValueError('内容必须是 1 到 4096 个字符的文本')
                capacity=values.get('capacity',job['capacity'])
                if type(capacity) is not int or capacity not in (1,2):raise ValueError('并发名额必须是 1 或 2')
                self.transition(job,'edit')
                self.store.update_execution(job['attempt'],phase='cancelled',disposition='superseded')
                job.update(content=content,capacity=capacity,param_version=job['param_version']+1,
                           checks={},execution={},prepared_version=None,reason='',attempt='none')
            elif action == 'grant':
                expires = values['expires']; version = values.get('version',job['param_version'])
                if type(expires) is not int or expires < 0 or type(version) is not int or version < 1:
                    raise ValueError('授权版本和有效期必须是合法整数')
                g = {'id':str(values['id']),'project':values.get('project',job['project']),
                     'actor':values.get('actor',job['actor']),'version':version,'expires':expires,'revoked':False}
                if not g['id'] or not isinstance(g['project'],str) or not g['project']:
                    raise ValueError('授权编号和项目名称不能为空')
                job['grants'] = [x for x in job['grants'] if x['id'] != g['id']]+[g]
            elif action == 'revoke':
                if not any(g['id']==values['id'] for g in job['grants']):raise ValueError('找不到这份授权')
                for g in job['grants']:
                    if g['id']==values['id']:g['revoked']=True
            elif action == 'role':
                if values['role'] not in ('engineer','viewer'):raise ValueError('操作者角色无效')
                job['role']=values['role']
            elif action == 'clock':
                clock=values['clock']
                if type(clock) is not int or clock < job['clock']:raise ValueError('时钟必须是整数，且只能向前推进')
                job['clock']=clock
            elif action == 'cancel':
                self.transition(job,'cancel')
                self.store.update_execution(job['attempt'],disposition='cancelled')
            else:raise ValueError('不支持这项操作')
            job['epoch']+=1; self.store.put(job)
        self.events.emit('change','change',lambda:observation(job,outputs={'action':action,'state':job['state']}))
        return self.store.snapshot()

    def prepare(self, expected_version: int | None = None) -> dict:
        with self.store.transaction():
            job=self.store.get()
            if expected_version is not None and job['param_version']!=expected_version:return self.store.snapshot()
            if job['state'] in ('checking','completed','cancelled'):return self.store.snapshot()
            job['attempt']=uuid.uuid4().hex[:10]
            job.update(checks={},execution={},prepared_version=None)
            self.events.emit('read','read',lambda:observation(job,outputs={'param_version':job['param_version'],'length':len(job['content'])}))
            allowed=authorized(job, self.events)
            if not allowed:
                self.transition(job,'block');job['reason']='no_current_authorization';self.store.put(job)
                self.events.emit('wait','wait',lambda:observation(job,outputs={'reason':job['reason']},uses=['authorize']))
                return self.store.snapshot()
            self.transition(job,'start')
            execution=ActivityExecution(job['capacity'],attempt=job['attempt'],param_version=job['param_version'])
            job.update(reason='',execution=execution.snapshot())
            self.store.put_execution({**job['execution'],'phase':'checking','disposition':'current'})
            self.store.put(job)
        # Work runs outside the transaction; edit/revoke/cancel can happen meanwhile.
        try:
            result=self.checker(job['content'],capacity=job['capacity'],execution=execution,
                                progress=lambda event,state:self.execution_progress(job,event,state))
            if not completed(execution.snapshot(),job['attempt'],job['param_version']) and result['passed']:
                raise ValueError('检查函数报告通过，但本次运行的活动尚未完成')
        except Exception as exc:
            execution.progress=lambda event,state:self.execution_progress(job,event,state)
            execution.abort()
            with self.store.transaction():
                current=self.store.get()
                if current['state']=='checking' and current['attempt']==job['attempt'] and current['param_version']==job['param_version']:
                    self.transition(current,'fail');current['reason']='worker_error:'+type(exc).__name__;self.store.put(current)
            self.events.emit('wait','error',lambda:observation(job,outputs={'reason':'worker_error'},uses=['authorize']))
            return self.store.snapshot()
        self.events.emit('checksum','return',lambda:observation(job,inputs={'length':len(job['content'])},
            outputs={'checksum':result['checksum']},uses=['authorize','read']))
        self.events.emit('privacy','return',lambda:observation(job,inputs={'length':len(job['content'])},
            outputs={'safe':result['safe']},uses=['authorize','read']))
        self.events.emit('join','decision',lambda:observation(job,
            outputs={'passed':result['passed'],'tasks':list(result['tasks'])},uses=['checksum','privacy']))
        with self.store.transaction():
            current=self.store.get()
            if current['attempt']!=job['attempt'] or current['param_version']!=job['param_version']:
                return self.store.snapshot()
            if current['state']=='cancelled':return self.store.snapshot()
            checks={k:v for k,v in result.items() if k!='execution'}
            if not result['passed']:
                self.transition(current,'fail');current['reason']='check_rejected';current['checks']=checks
            else:
                self.transition(current,'checked')
                current.update(checks=checks,prepared_version=job['param_version'],reason='')
            self.store.put(current)
        if current['state'] in ('waiting','failed'):
            self.events.emit('wait','wait',lambda:observation(current,outputs={'reason':current['reason']},uses=['join']))
        return self.store.snapshot()

    def execution_progress(self, job: dict, event: str, state: dict) -> None:
        with self.store.transaction():
            current=self.store.get()
            previous=self.store.execution(job['attempt']) or {'phase':'checking','disposition':'current'}
            self.store.put_execution({**previous,**state})
            if current['attempt']==job['attempt'] and current['param_version']==job['param_version']:
                current['execution']=state;self.store.put(current)
        last=state['journal'][-1];activity=last['activity']
        phase='wait' if event=='wait' else 'enter' if event=='start' else 'return'
        self.events.emit('flow.checks',phase,lambda:observation(job,
            outputs={'revision':state['revision'],'activity':activity,'event':event},uses=['authorize']))
        if activity in state['activities']:
            self.events.emit(activity,phase,lambda:observation(job,
                outputs={'state':state['activities'][activity]},uses=['authorize']))

    def commit(self, expected_version: int | None = None) -> dict:
        with self.store.transaction():
            job=self.store.get()
            if expected_version is not None and job['param_version']!=expected_version:return self.store.snapshot()
            if job['state']!='ready':return self.store.snapshot()
            allowed=authorized(job, self.events);version_ok=job['prepared_version']==job['param_version']
            self.events.emit('recheck','decision',lambda:observation(job,
                outputs={'allowed':allowed,'version_ok':version_ok},uses=['authorize','join']))
            if not allowed or not version_ok or not job['checks']['passed']:
                self.transition(job,'block');job['reason']='authorization_or_version_changed';self.store.put(job)
                self.events.emit('wait','wait',lambda:observation(job,outputs={'reason':job['reason']},uses=['recheck']))
                return self.store.snapshot()
            self.store.artifact(job['param_version'],job['checks']['checksum'])
            self.transition(job,'publish');self.store.put(job)
        # Commit event is emitted only after the SQLite transaction succeeded.
        self.events.emit('commit','commit',lambda:observation(job,
            outputs={'version':job['param_version'],'checksum':job['checks']['checksum']},uses=['recheck','checksum']))
        return self.store.snapshot()

    def execute(self, expected_version: int | None = None) -> dict:
        version=self.store.snapshot()['param_version'] if expected_version is None else expected_version
        self.prepare(expected_version=version)
        return self.commit(expected_version=version)
