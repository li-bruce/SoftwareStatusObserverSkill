"""Domain operations. Files are immutable; authority lives only in SQLite."""
import hashlib
from pathlib import Path
import time
import uuid
from .ports import TracePort
from bo_stategraph.workflow import next_state


class DomainError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


class ReviewService:
    def __init__(self, store, build_id: str, trace_factory=None, max_bytes: int=20*1024*1024):
        self.store,self.build_id,self.trace_factory,self.max_bytes=store,build_id,trace_factory,max_bytes

    def bo_trace(self, entity: str) -> TracePort:
        try:
            return self.trace_factory(entity,uuid.uuid4().hex) if self.trace_factory else TracePort()
        except Exception:
            return TracePort()

    def upload(self, actor: dict, filename: str, content: bytes, note: str='') -> dict:
        if actor['role'] != 'uploader':
            raise DomainError(403,'只有上传者可以提交文件')
        if not filename or len(filename)>200 or Path(filename).name!=filename or any(c in filename for c in '/\\\r\n\x00'):
            raise DomainError(400,'文件名无效，请使用不含路径的文件名')
        if not content:
            raise DomainError(400,'文件为空，请选择有内容的文件')
        if len(content)>self.max_bytes:
            raise DomainError(413,'文件超过当前上传大小上限')
        if len(note)>1000:
            raise DomainError(400,'提交说明最多1000字')
        ident=uuid.uuid4().hex
        trace=self.bo_trace(ident)
        basis={'param_version':1,'epoch':1,'clock':time.time()}
        call_id=uuid.uuid4().hex
        inputs={'size':len(content),'actor':actor['id'],'filename':filename,'note':note}
        entered=trace.bo_record('upload','enter',basis,lambda:{'inputs':inputs},call_id=call_id)
        target=self.store.files / ident
        staging=self.store.files / (ident+'.part')
        now=time.time()
        try:
            with staging.open('xb') as output:
                output.write(content)
                output.flush()
                import os
                os.fsync(output.fileno())
            staging.replace(target)
            with self.store.connection(write=True) as db:
                db.execute('INSERT INTO submissions(id,filename,size,sha256,uploader_id,reviewer_id,status,note,created_at,revision,build_id) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                    (ident,filename,len(content),hashlib.sha256(content).hexdigest(),actor['id'],'reviewer','pending',note,now,1,self.build_id))
                db.execute('INSERT INTO notifications(user_id,submission_id,text,created_at) VALUES(?,?,?,?)',
                    ('reviewer',ident,'有新文件待审核：'+filename,now))
        except BaseException:
            staging.unlink(missing_ok=True)
            target.unlink(missing_ok=True)
            raise
        committed=trace.bo_record('upload','commit',basis,lambda:{'inputs':inputs,'outputs':{'state':'pending','revision':1}},depends=[(entered,'control')],call_id=call_id)
        trace.bo_record('notify','commit',basis,lambda:{'outputs':{'recipient':'reviewer','count':1}},depends=[(committed,'data')],call_id=call_id)
        trace.bo_record('pending','wait',basis,lambda:{'outputs':{'state':'pending','reason':'等待审核者通过或驳回'}},depends=[(committed,'control')],call_id=call_id)
        return self.detail(actor,ident)

    def detail(self, actor: dict, ident: str) -> dict:
        with self.store.connection() as db:
            row=db.execute('SELECT * FROM submissions WHERE id=?',(ident,)).fetchone()
        if row is None:
            raise DomainError(404,'文件记录不存在')
        if actor['id'] not in (row['uploader_id'],row['reviewer_id']):
            raise DomainError(403,'你没有访问这份文件的权限')
        return dict(row)

    def list_files(self, actor: dict) -> list[dict]:
        field='reviewer_id' if actor['role']=='reviewer' else 'uploader_id'
        with self.store.connection() as db:
            return [dict(r) for r in db.execute('SELECT * FROM submissions WHERE '+field+'=? ORDER BY created_at DESC,id',(actor['id'],))]

    def review(self, actor: dict, ident: str, decision: str, note: str='') -> dict:
        if decision not in ('approve','reject'):
            raise DomainError(400,'请选择通过或驳回')
        if len(note)>1000:
            raise DomainError(400,'审核意见最多1000字')
        trace=self.bo_trace(ident)
        basis={'param_version':1,'epoch':1,'clock':time.time()}
        call_id=uuid.uuid4().hex
        inputs={'actor':actor['id'],'entity':ident,'decision':decision,'note':note}
        entered=trace.bo_record('review','enter',basis,lambda:{'inputs':inputs},call_id=call_id)
        with self.store.connection(write=True) as db:
            row=db.execute('SELECT * FROM submissions WHERE id=?',(ident,)).fetchone()
            if row is None:
                raise DomainError(404,'文件记录不存在')
            basis['epoch']=row['revision']
            allowed=actor['role']=='reviewer' and actor['id']==row['reviewer_id'] and actor['id']!=row['uploader_id']
            checked=trace.bo_record('review_guard','decision',basis,lambda:{'inputs':{'actor':actor['id'],'role':actor['role'],'before':row['status']},'outputs':{'allowed':allowed,'pending':row['status']=='pending'}},depends=[(entered,'control')],call_id=call_id)
            if not allowed:
                raise DomainError(403,'只有该文件的另一位审核者可以审核')
            try:
                state=next_state(row['status'],decision)
            except ValueError as exc:
                raise DomainError(409,str(exc)) from exc
            now=time.time()
            changed=db.execute('UPDATE submissions SET status=?,review_note=?,reviewed_at=?,revision=revision+1,build_id=? WHERE id=? AND status=? AND revision=?',
                (state,note,now,self.build_id,ident,'pending',row['revision'])).rowcount
            if changed!=1:
                raise DomainError(409,'审核状态已变化，请刷新后重试')
            label='通过' if state=='approved' else '驳回'
            db.execute('INSERT INTO notifications(user_id,submission_id,text,created_at) VALUES(?,?,?,?)',
                (row['uploader_id'],ident,'文件审核已'+label+'：'+row['filename'],now))
        basis['epoch']=row['revision']+1
        trace.bo_record('review','commit',basis,lambda:{'inputs':inputs,'outputs':{'before':row['status'],'state':state,'revision':row['revision']+1}},depends=[(checked,'control')],call_id=call_id)
        return self.detail(actor,ident)

    def messages(self, actor: dict) -> list[dict]:
        with self.store.connection() as db:
            return [dict(r) for r in db.execute('SELECT * FROM notifications WHERE user_id=? ORDER BY id DESC',(actor['id'],))]

    def read_message(self, actor: dict, ident: int) -> None:
        with self.store.connection(write=True) as db:
            changed=db.execute('UPDATE notifications SET read_at=COALESCE(read_at,?) WHERE id=? AND user_id=?',(time.time(),ident,actor['id'])).rowcount
        if not changed:
            raise DomainError(404,'消息不存在')
