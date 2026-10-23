"""Application logic: native execution or the application's own implementation."""
def advance(state: str, event: str, slots: int, executor=None):
    if executor is not None:
        return executor.step(state,event,{'slots':slots})
    if event=='start' and state=='pending':
        return {'state':'running' if slots>0 else 'waiting','guards':{'available':slots>0},'event':event,'payload':{}}
    if event=='resume' and state=='waiting' and slots>0:
        return {'state':'running','guards':{'available':True},'event':event,'payload':{}}
    if event=='finish' and state=='running':
        return {'state':'done','guards':{},'event':event,'payload':{}}
    raise ValueError('no enabled transition')
