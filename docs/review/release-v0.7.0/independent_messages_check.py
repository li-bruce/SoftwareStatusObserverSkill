"""Check the confirmed v2 message rules with independent SQLite reads.

The previous application creates a real v1 database in a child process. The new
application migrates and operates it. Neither expected values nor business truth
are read from the graph, probe payloads or the developer's acceptance fixtures.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--previous", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    project, previous = args.project.resolve(), args.previous.resolve()
    source_hashes = {p.relative_to(project).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                     for p in sorted((project / "app").glob("*.py"))}
    sys.path.insert(0, str(project))
    from app.service import Service, DomainError
    checks = []

    def check(label, condition):
        if not condition:
            raise AssertionError(label)
        checks.append(label)

    scratch = (Path.cwd() / ".validation").resolve()
    scratch.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch) as folder:
        database = Path(folder) / "messages.sqlite"
        seed = (
            "from pathlib import Path; from app.service import Service; import sys; "
            "s=Service(Path(sys.argv[1])); s.initialize(); "
            "token,_=s.login('member','member-demo'); "
            "s.submit(token,'Old title','Old body'); s.close()"
        )
        subprocess.run([sys.executable, "-B", "-X", "utf8", "-c", seed, str(database)],
                       cwd=previous, check=True, capture_output=True, text=True)

        def rows(sql):
            with closing(sqlite3.connect(database)) as connection:
                return connection.execute(sql).fetchall()

        check("M01_real_old_schema", "is_read" not in [r[1] for r in rows("PRAGMA table_info(messages)")])
        old_messages = rows("SELECT id,recipient_id,material_id,content_version FROM messages")
        service = Service(database)
        try:
            service.initialize()
            check("M02_old_message_identity", rows("SELECT id,recipient_id,material_id,content_version FROM messages") == old_messages)
            check("M03_existing_messages_unread", rows("SELECT is_read FROM messages") == [(0,)])
            member, _ = service.login("member", "member-demo")
            reviewer, _ = service.login("reviewer", "reviewer-demo")
            check("M04_recipient_count", service.unread_count(reviewer) == {"unread_count": 1})
            check("M05_other_recipient_count", service.unread_count(member) == {"unread_count": 0})
            ident = service.inbox(reviewer)[0]["id"]
            service.message(reviewer, ident)
            check("M06_open_does_not_mark", rows("SELECT is_read FROM messages") == [(0,)])
            for actor, target, expected in [(member, ident, 404), (reviewer, 999999, 404), ("invalid-session", ident, 401)]:
                before = rows("SELECT id,is_read FROM messages")
                try:
                    service.mark_message_read(actor, target)
                except DomainError as error:
                    check("M07_denied_" + str(expected) + "_" + str(target) + "_" + str(len(checks)), error.status == expected)
                else:
                    raise AssertionError("Marking a message unexpectedly succeeded")
                check("M08_denial_has_no_write_" + str(len(checks)), rows("SELECT id,is_read FROM messages") == before)
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda _: service.mark_message_read(reviewer, ident), range(2)))
            check("M09_concurrent_single_change", sorted(r["changed"] for r in results) == [False, True])
            check("M10_authoritative_read_value", rows("SELECT is_read FROM messages") == [(1,)])
            check("M11_count_never_negative", all(r["unread_count"] == 0 for r in results))
            again = service.mark_message_read(reviewer, ident)
            check("M12_repeat_is_idempotent", not again["changed"] and again["unread_count"] == 0)
            service.initialize()
            check("M13_restart_preserves_read", rows("SELECT is_read FROM messages") == [(1,)])
            service.submit(member, "New title", "New body")
            check("M14_new_message_unread", rows("SELECT is_read FROM messages ORDER BY id") == [(1,), (0,)])
            check("M15_count_includes_only_unread", service.unread_count(reviewer) == {"unread_count": 1})
            check("M16_publication_unchanged", rows("SELECT COUNT(*) FROM publications") == [(0,)])
        finally:
            service.close()
    result = {"passed": True, "scope": "Confirmed v2 message behavior and real v1 migration only; no graph-based oracle", "checks": checks, "source_sha256": source_hashes}
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": True, "checks": len(checks)}))


if __name__ == "__main__":
    main()
