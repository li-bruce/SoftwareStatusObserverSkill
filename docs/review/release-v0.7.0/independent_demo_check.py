"""Check confirmed publishing rules against real SQLite effects in an isolated database.

This release-trial oracle imports the independent project's business service.
It does not read the graph, copy its expectations, or alter the running demo.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    root = args.project.resolve()
    sources = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
               for p in sorted((root / "app").glob("*.py"))}
    sys.path.insert(0, str(root))
    from app.service import Service, DomainError

    checks = []

    def check(name, condition):
        if not condition:
            raise AssertionError(name)
        checks.append(name)

    def denied(name, callback, status):
        try:
            callback()
        except DomainError as error:
            check(name, error.status == status)
        else:
            raise AssertionError(name + ": action unexpectedly succeeded")

    # The temporary database belongs to this test, not the user's running app.
    scratch = (Path.cwd() / ".validation").resolve()
    scratch.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch) as temporary:
        assert Path(temporary).resolve().is_relative_to(scratch)
        database = Path(temporary) / "oracle.sqlite"
        service = Service(database)
        service.initialize()

        def rows(sql):
            with closing(sqlite3.connect(database)) as connection:
                return connection.execute(sql).fetchall()

        try:
            member, member_actor = service.login("member", "member-demo")
            reviewer, reviewer_actor = service.login("reviewer", "reviewer-demo")
            check("T02_roles", (member_actor["role"], reviewer_actor["role"]) == ("member", "reviewer"))
            denied("T02_wrong_password", lambda: service.login("member", "wrong"), 401)
            check("T01_empty_public_page", service.public() == [])
            item = service.submit(member, "Original title", "Original body")
            ident = item["id"]
            check("T03_pending_version", (item["state"], item["content_version"]) == ("pending", 1))
            check("T03_recipient", rows("SELECT recipient_id, content_version FROM messages") == [(2, 1)])
            notice = service.inbox(reviewer)[0]
            denied("T11_recipient_privacy", lambda: service.message(member, notice["id"]), 404)
            check("T11_member_inbox", service.inbox(member) == [])
            denied("T04_member_cannot_review", lambda: service.review(member, ident, "approve", 1, item["revision"]), 403)
            check("T04_no_publication", rows("SELECT COUNT(*) FROM publications") == [(0,)])
            item = service.review(reviewer, ident, "reject", 1, item["revision"])
            check("T05_rejected", item["state"] == "rejected")
            denied("T06_reviewer_cannot_edit", lambda: service.edit(reviewer, ident, "Bad", "Bad", 1, item["revision"]), 403)
            item = service.edit(member, ident, "Revised title", "Revised body", 1, item["revision"])
            check("T07_identity_and_version", (item["id"], item["content_version"]) == (ident, 2))
            item = service.resubmit(member, ident, 2, item["revision"])
            check("T07_pending_again", item["state"] == "pending")
            denied("T08_old_version", lambda: service.review(reviewer, ident, "approve", 1, item["revision"]), 409)
            check("T08_no_write", rows("SELECT COUNT(*) FROM publications") == [(0,)])
            # A logged-in actor's current database role must be read again.
            with closing(sqlite3.connect(database)) as connection:
                connection.execute("UPDATE accounts SET role='member' WHERE id=2")
                connection.commit()
            denied("T04_current_role", lambda: service.review(reviewer, ident, "approve", 2, item["revision"]), 403)
            with closing(sqlite3.connect(database)) as connection:
                connection.execute("UPDATE accounts SET role='reviewer' WHERE id=2")
                connection.commit()
            item = service.review(reviewer, ident, "approve", 2, item["revision"])
            check("T09_exact_snapshot", rows("SELECT content_version,title,body,author_id FROM publications") == [(2, "Revised title", "Revised body", 1)])
            denied("T10_duplicate_review", lambda: service.review(reviewer, ident, "approve", 2, item["revision"]), 409)
            denied("T10_published_readonly", lambda: service.edit(member, ident, "Changed", "Changed", 2, item["revision"]), 409)
            check("T09_public_content", service.public()[0]["body"] == "Revised body")
            check("T10_exactly_once", rows("SELECT COUNT(*) FROM publications") == [(1,)])

            concurrent = service.submit(member, "Concurrent title", "Concurrent body")

            def review_once(_):
                try:
                    service.review(reviewer, concurrent["id"], "approve", 1, concurrent["revision"])
                    return "committed"
                except DomainError as error:
                    return error.status

            with ThreadPoolExecutor(max_workers=2) as pool:
                outcomes = list(pool.map(review_once, range(2)))
            check("T10_concurrent_exactly_once", outcomes.count("committed") == 1 and outcomes.count(409) == 1)
            check("T10_concurrent_effect_count", rows("SELECT COUNT(*) FROM publications") == [(2,)])
        finally:
            service.close()

    check("source_unchanged_during_test", all(hashlib.sha256((root / name).read_bytes()).hexdigest() == digest for name, digest in sources.items()))
    result = {"passed": True, "checks": checks, "source_hashes": sources,
              "scope": "Independent business rules and SQLite effects with observation off. Runtime mapping and browser behavior require separate evidence."}
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": True, "checks": len(checks), "output": str(args.out)}))


if __name__ == "__main__":
    main()
