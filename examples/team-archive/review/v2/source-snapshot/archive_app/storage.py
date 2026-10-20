"""SQLite authority: source entries, relationships, approvals, runs and archives."""
import json
from contextlib import closing
from pathlib import Path
import sqlite3


class ArchiveStore:
    def __init__(self, path: str):
        self.path = str(Path(path).absolute())
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as db:
            db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS meta(id INTEGER PRIMARY KEY CHECK(id=1),epoch INTEGER NOT NULL);
            INSERT OR IGNORE INTO meta VALUES(1,1);
            CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,name TEXT NOT NULL,role TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY,title TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS folders(id TEXT PRIMARY KEY,project_id TEXT NOT NULL,parent_id TEXT,title TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS assignments(project_id TEXT,folder_id TEXT,operator_id TEXT,PRIMARY KEY(project_id,folder_id,operator_id));
            CREATE TABLE IF NOT EXISTS documents(id TEXT PRIMARY KEY,project_id TEXT,folder_id TEXT,title TEXT,number TEXT,content TEXT,version INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS grants(id TEXT PRIMARY KEY,project_id TEXT,operator_id TEXT,document_id TEXT,content_version INTEGER,reviewer_id TEXT,deadline REAL,revoked INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS runs(sequence INTEGER PRIMARY KEY AUTOINCREMENT,id TEXT UNIQUE NOT NULL,payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS archives(id TEXT PRIMARY KEY,document_id TEXT NOT NULL,content_version INTEGER NOT NULL,content TEXT NOT NULL,title TEXT,project_id TEXT,number TEXT,run_id TEXT NOT NULL,created REAL NOT NULL,UNIQUE(document_id,content_version));
            """)
            # Additive migration keeps existing projects, approvals and snapshots.
            db.execute("BEGIN IMMEDIATE")
            columns = {r["name"] for r in db.execute("PRAGMA table_info(projects)")}
            if "archive_limit_bytes" not in columns:
                db.execute("ALTER TABLE projects ADD COLUMN archive_limit_bytes INTEGER NOT NULL DEFAULT 8192 CHECK(archive_limit_bytes>0)")
            if "limit_revision" not in columns:
                db.execute("ALTER TABLE projects ADD COLUMN limit_revision INTEGER NOT NULL DEFAULT 1")
            db.commit()

    def connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        return db

    @staticmethod
    def bump(db: sqlite3.Connection) -> int:
        db.execute("UPDATE meta SET epoch=epoch+1 WHERE id=1")
        return db.execute("SELECT epoch FROM meta WHERE id=1").fetchone()[0]

    def seed(self) -> None:
        with closing(self.connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            db.executemany("INSERT OR IGNORE INTO users VALUES(?,?,?)",[
                ("alice","林晓 · 文件夹负责人","manager"),("bob","周宁 · 审核员","reviewer"),
                ("carol","陈青 · 审核员","reviewer"),("dana","杜然 · 子目录负责人","manager")])
            db.executemany("INSERT OR IGNORE INTO projects(id,title) VALUES(?,?)",[("P1","研发资料"),("P2","共享资料")])
            db.executemany("INSERT OR IGNORE INTO folders VALUES(?,?,?,?)",[
                ("F1","P1",None,"项目资料"),("F2","P1","F1","设计记录"),
                ("F3","P1","F2","历史草稿"),("F4","P2",None,"其他项目")])
            db.executemany("INSERT OR IGNORE INTO assignments VALUES(?,?,?)",[
                ("P1","F1","alice"),("P1","F2","alice"),("P1","F3","dana"),("P2","F4","dana")])
            db.execute("INSERT OR IGNORE INTO documents VALUES(?,?,?,?,?,?,?)",
                       ("DOC-001","P1","F2","接口设计说明","RD-001","模拟资料：版本一的固定内容。",1))
            db.commit()

    @staticmethod
    def project_limit(db: sqlite3.Connection, project_id: str) -> dict:
        row = db.execute("SELECT archive_limit_bytes,limit_revision FROM projects WHERE id=?",
                         (project_id,)).fetchone()
        if row is None:
            raise ValueError("项目不存在")
        return {"project_id":project_id,"limit_bytes":row["archive_limit_bytes"],
                "limit_revision":row["limit_revision"]}

    @staticmethod
    def get_run(db: sqlite3.Connection, run_id: str) -> dict:
        row = db.execute("SELECT payload FROM runs WHERE id=?",(run_id,)).fetchone()
        if row is None:
            raise ValueError("找不到这次运行")
        return json.loads(row["payload"])

    @staticmethod
    def save_run(db: sqlite3.Connection, run: dict) -> None:
        db.execute("INSERT INTO runs(id,payload) VALUES(?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload",
                   (run["id"],json.dumps(run,ensure_ascii=False)))

    @staticmethod
    def find_archive(db: sqlite3.Connection, document_id: str, content_version: int) -> dict | None:
        row = db.execute("SELECT * FROM archives WHERE document_id=? AND content_version=?",
                         (document_id,content_version)).fetchone()
        return dict(row) if row else None

    def snapshot(self) -> dict:
        with closing(self.connect()) as db:
            db.execute("BEGIN")
            data = {table:[dict(r) for r in db.execute("SELECT * FROM "+table)]
                    for table in ("users","projects","folders","assignments","documents","grants","archives")}
            data["runs"] = [json.loads(r["payload"]) for r in db.execute("SELECT payload FROM runs ORDER BY sequence")]
            data["epoch"] = db.execute("SELECT epoch FROM meta WHERE id=1").fetchone()[0]
            return data
