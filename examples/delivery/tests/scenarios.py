"""Exercise real commands and SQLite effects. Does not load expected answers."""
from concurrent.futures import ThreadPoolExecutor
from app.service import Delivery
from app.store import Store
from app.ports import Events
from integrations.bo_adapter import BOAdapter
from app.checks import run_checks
import threading

CASES=['normal','no_grant','alternative','revoked','expired','bad_scope','bad_role',
       'edit_after_prepare','cancel','retry','duplicate','worker_failure','concurrent','privacy','resource_wait','parallel']

from integrations.bo_scenarios import SCENARIOS


def exercise(name, model, build_id, mode='on'):
    store=Store(); observer=BOAdapter(model,build_id,enabled=mode!='off',fault=mode=='fault')
    events=Events(observer if mode!='off' else None); app=Delivery(store,events,execution_version=build_id)
    try:
        if name!='no_grant':app.command('grant',id='G1',expires=200)
        if name=='alternative':
            app.command('grant',id='G2',expires=220);app.command('revoke',id='G1')
        if name=='bad_scope':app.command('grant',id='G1',project='WRONG',expires=200)
        if name=='bad_role':app.command('role',role='viewer')
        if name=='privacy':app.command('edit',content='SECRET: synthetic only');app.command('grant',id='G2',expires=220)
        if name=='worker_failure':
            def fail(_,**kwargs):raise RuntimeError('synthetic worker failure')
            app.checker=fail
        if name=='parallel':
            barrier=threading.Barrier(2)
            app.checker=lambda content,**kw:run_checks(content,task_hook=lambda _:barrier.wait(3),**kw)
        if name=='resource_wait':
            app.command('edit',content='resource sample',capacity=1);app.command('grant',id='G2',expires=220)
            gate=threading.Event();first=[True];lock=threading.Lock()
            def limited(content,**kw):
                original=kw.pop('progress')
                def progress(event,snapshot):
                    if event=='wait':gate.set()
                    original(event,snapshot)
                def hook(_):
                    with lock:initial=first[0];first[0]=False
                    if initial and not gate.wait(3):raise RuntimeError('resource wait did not occur')
                return run_checks(content,progress=progress,task_hook=hook,**kw)
            app.checker=limited
        if name in ('revoked','expired','edit_after_prepare','cancel'):
            app.prepare()
            if name=='revoked':app.command('revoke',id='G1')
            elif name=='expired':app.command('clock',clock=200)
            elif name=='edit_after_prepare':app.command('edit',content='new version')
            else:app.command('cancel')
            app.commit()
        elif name=='retry':
            app.command('revoke',id='G1');app.execute()
            app.command('grant',id='G2',expires=220);app.execute()
        elif name=='concurrent':
            app.prepare()
            with ThreadPoolExecutor(max_workers=4) as pool:
                list(pool.map(lambda _:app.commit(),range(4)))
        else:
            app.execute()
            if name=='duplicate':app.execute();app.commit()
        result=store.snapshot();actual=observer.snapshot();health=observer.bo_pins.health()
        return {'case':name,'mode':mode,'observations':{'state':result['state'],
                'effects':len(result['effects']),'versions':[a['version'] for a in result['effects']],
                'reason':result['reason'],'tasks':sorted(result['checks'].get('tasks',{})),
                'observer_errors':health['errors'],'port_errors':events.errors},
                'events':actual,'authority':result,'health':health,'configurations':result['executions']}
    finally:
        observer.close();store.close()
