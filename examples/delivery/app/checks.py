"""Run the activities declared inside the application's checking state."""
import hashlib
from concurrent.futures import ThreadPoolExecutor
from bo_stategraph.workflow import ActivityExecution


def checksum(content: str) -> str:
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


def privacy_check(content: str) -> bool:
    return 'SECRET:' not in content


def run_checks(content: str,*,capacity: int=2,execution=None,progress=None,task_hook=None) -> dict:
    execution=execution or ActivityExecution(capacity)
    execution.progress=progress
    handlers={'checksum':checksum,'privacy':privacy_check}
    if set(handlers)!={a['id'] for a in execution.spec['activities']}:
        raise ValueError('声明的检查项目与实际函数不一致')
    def work(activity):
        execution.start(activity)
        try:
            if task_hook:task_hook(activity)
            value=handlers[activity](content)
        except Exception as exc:
            execution.finish(activity,False,error=True)
            return {'ok':False,'error':type(exc).__name__,'value':None}
        execution.finish(activity,value is not False)
        return {'ok':value is not False,'value':value}
    with ThreadPoolExecutor(max_workers=len(handlers)) as pool:
        jobs={a['id']:pool.submit(work,a['id']) for a in execution.spec['activities']}
        results={name:future.result() for name,future in jobs.items()}
    passed=execution.join()
    return {'passed':passed,'checksum':results['checksum']['value'] or '',
            'safe':results['privacy']['ok'],'tasks':{n:v['ok'] for n,v in results.items()},
            'execution':execution.snapshot()}
