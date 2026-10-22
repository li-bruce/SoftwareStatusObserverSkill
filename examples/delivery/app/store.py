"""Application-owned local transaction and effects. One process, shared lock."""
import json
import sqlite3
import threading
from contextlib import contextmanager
from bo_stategraph.workflow import recover_records


class Store:
    def __init__(self, path: str = ':memory:'):
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS job(id INTEGER PRIMARY KEY, document TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS artifact(version INTEGER PRIMARY KEY, checksum TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS journal(seq INTEGER PRIMARY KEY, event TEXT, source TEXT, target TEXT);
        CREATE TABLE IF NOT EXISTS execution_run(attempt TEXT PRIMARY KEY, document TEXT NOT NULL);
        ''')
        columns={r['name'] for r in self.db.execute('PRAGMA table_info(journal)')}
        for name,kind in [('attempt','TEXT'),('param_version','INTEGER')]:
            if name not in columns:self.db.execute('ALTER TABLE journal ADD COLUMN '+name+' '+kind)
        if not self.db.execute('SELECT 1 FROM job').fetchone():
            with self.transaction():
                self.put({'project':'P1','actor':'alice','role':'engineer','content':'public sample',
                          'param_version':1,'clock':100,'epoch':1,'state':'draft','grants':[],
                          'checks':{},'prepared_version':None,'reason':'','attempt':'none','capacity':2,'execution':{}})
        else:
            # This application owns one Store per process. A new process has no old workers.
            with self.transaction():
                job=self.get()
                records=[json.loads(row['document']) for row in self.db.execute('SELECT document FROM execution_run')]
                for record in recover_records(job, records): self.put_execution(record)
                self.put(job)

    @contextmanager
    def transaction(self):
        with self.lock:
            self.db.execute('BEGIN IMMEDIATE')
            try:
                yield
                self.db.execute('COMMIT')
            except Exception:
                self.db.execute('ROLLBACK')
                raise

    def get(self) -> dict:
        return json.loads(self.db.execute('SELECT document FROM job WHERE id=1').fetchone()[0])

    def put(self, job: dict) -> None:
        self.db.execute('INSERT OR REPLACE INTO job VALUES (1, ?)', (json.dumps(job),))

    def execution(self, attempt: str) -> dict | None:
        row=self.db.execute('SELECT document FROM execution_run WHERE attempt=?',(attempt,)).fetchone()
        return json.loads(row['document']) if row else None

    def put_execution(self, value: dict) -> None:
        previous = self.execution(value['attempt'])
        value = {**value, 'state_revision': previous.get('state_revision', -1) + 1 if previous else 0}
        self.db.execute('INSERT INTO execution_run VALUES (?,?) ON CONFLICT(attempt) DO UPDATE SET document=excluded.document',
                        (value['attempt'],json.dumps(value)))

    def update_execution(self, attempt: str, **changes):
        value=self.execution(attempt)
        if value:self.put_execution({**value,**changes})

    def artifact(self, version: int, checksum: str) -> None:
        self.db.execute('INSERT INTO artifact VALUES (?, ?)', (version,checksum))

    def record_transition(self, event, source, target, attempt, param_version):
        self.db.execute('INSERT INTO journal(event,source,target,attempt,param_version) VALUES (?,?,?,?,?)',
                        (event,source,target,attempt,param_version))

    def snapshot(self) -> dict:
        with self.lock:
            return {**self.get(), 'effects':[dict(r) for r in self.db.execute('SELECT * FROM artifact ORDER BY version')],
                    'journal':[dict(r) for r in self.db.execute('SELECT * FROM journal ORDER BY seq')],
                    'executions':[json.loads(r['document']) for r in self.db.execute('SELECT document FROM execution_run ORDER BY rowid')]}

    def close(self):
        self.db.close()
