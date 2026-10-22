"""SQLite authority plus transaction-bound history for deterministic replay."""
from contextlib import closing
import json
import sqlite3
from pathlib import Path

TABLES = ("tasks", "runs", "activities", "printers", "roles", "approvals", "effects")

class Store:
    def __init__(self, path: str, printers: list):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as c:
            c.executescript('''
            CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY, submitter TEXT NOT NULL, version INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, task_id TEXT NOT NULL, version INTEGER NOT NULL,
              submitter TEXT NOT NULL, printer_id TEXT NOT NULL, dimensions TEXT NOT NULL, material TEXT NOT NULL,
              parameters TEXT NOT NULL, state TEXT NOT NULL, queue_seq INTEGER, reason TEXT NOT NULL,
              UNIQUE(task_id,version));
            CREATE TABLE IF NOT EXISTS activities(run_id TEXT, name TEXT, state TEXT NOT NULL, result TEXT,
              started REAL, ended REAL, PRIMARY KEY(run_id,name));
            CREATE TABLE IF NOT EXISTS printers(id TEXT PRIMARY KEY, limits TEXT NOT NULL, materials TEXT NOT NULL,
              occupant TEXT UNIQUE);
            CREATE TABLE IF NOT EXISTS roles(actor TEXT, printer_id TEXT, active INTEGER NOT NULL, PRIMARY KEY(actor,printer_id));
            CREATE TABLE IF NOT EXISTS approvals(id TEXT PRIMARY KEY, task_id TEXT NOT NULL, version INTEGER NOT NULL,
              printer_id TEXT NOT NULL, approver TEXT NOT NULL, expires REAL NOT NULL, revoked INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS effects(id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL,
              kind TEXT NOT NULL, printer_id TEXT NOT NULL, clock REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS history(revision INTEGER PRIMARY KEY AUTOINCREMENT, action TEXT NOT NULL, snapshot TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS counters(name TEXT PRIMARY KEY, value INTEGER NOT NULL);
            INSERT OR IGNORE INTO counters VALUES('queue',0);
            ''')
            for p in printers:
                c.execute("INSERT OR IGNORE INTO printers VALUES(?,?,?,NULL)", (p["id"], json.dumps(p["limits"]), json.dumps(p["materials"])))
            c.commit()

    def connect(self):
        c = sqlite3.connect(self.path, timeout=15)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys=ON")
        return c

    def snapshot(self, connection=None) -> dict:
        if connection is None:
            with closing(self.connect()) as c:
                c.execute("BEGIN")
                return self.snapshot(c)
        result = {table: [dict(row) for row in connection.execute("SELECT * FROM " + table + " ORDER BY rowid")] for table in TABLES}
        for row in result["runs"]:
            for field in ("dimensions", "parameters"):
                row[field] = json.loads(row[field])
        for row in result["printers"]:
            for field in ("limits", "materials"):
                row[field] = json.loads(row[field])
        for row in result["activities"]:
            row["result"] = json.loads(row["result"]) if row["result"] else None
        return result

    def change(self, action: str, operation) -> tuple:
        with closing(self.connect()) as c:
            try:
                c.execute("BEGIN IMMEDIATE")
                result = operation(c)
                snapshot = self.snapshot(c)
                revision = c.execute("INSERT INTO history(action,snapshot) VALUES(?,?)", (action, json.dumps(snapshot, ensure_ascii=False))).lastrowid
                c.commit()
                return result, revision, snapshot
            except BaseException:
                c.rollback()
                raise

    def history(self) -> list:
        with closing(self.connect()) as c:
            return [{"revision": r["revision"], "action": r["action"], "snapshot": json.loads(r["snapshot"])} for r in c.execute("SELECT * FROM history ORDER BY revision")]
