"""Reproduce a scripted storage-selection dialogue using real CLI and SQLite calls.

The dialogue is synthetic. Commands, schema changes, native exports and the
recorded query are executed; this is not an independent human or LLM trial.
"""

import argparse
from contextlib import closing
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills/business-observer/scripts"
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(SCRIPTS))

import test_database_sync as database_fixture
from bo_observer.adapters.python.bo_probe import BOProbe
from bo_observer.data.runtime import BODataRuntime
from bo_observer.data.sync import runtime_errors
from bo_observer.graph.behavior_model import capture
from bo_observer.observation.observation_scope import bo_internal
from bo_observer.protocol import validate_event


def trial(output):
    output.mkdir(parents=True, exist_ok=True)
    commands, turns = [], []
    fixture = database_fixture.DatabaseSyncTests()
    fixture.setUp()
    root = fixture.root

    def say(role, content, evidence=None):
        turns.append({"role": role, "content": content, "evidence": evidence or []})

    def command(ident, action, expected=0):
        argv = [
            sys.executable,
            "-B",
            "-X",
            "utf8",
            str(SCRIPTS / "bo_db.py"),
            action,
            "--root",
            str(root),
        ]
        result = subprocess.run(argv, cwd=ROOT, capture_output=True, timeout=30)
        parsed = json.loads(result.stdout.decode("utf-8"))
        commands.append(
            {
                "id": ident,
                "command": [
                    "python",
                    "skills/business-observer/scripts/bo_db.py",
                    action,
                    "--root",
                    "$TRIAL",
                ],
                "exit_code": result.returncode,
                "result": parsed,
            }
        )
        if result.returncode != expected:
            raise AssertionError(
                f"{ident}: exit {result.returncode}, expected {expected}: {parsed}"
            )
        return parsed

    try:
        (root / "bo_stategraph/databases.json").unlink()
        say(
            "user",
            "这是一个已有的本地图片审核工程，业务流程保持现状。这次把数据库接入状态图，先只在我自己的电脑使用，数据库还没确定。",
        )
        initial = command("initial-guide", "guide")
        assert len(initial["user"]) == 1
        assert initial["coding"][0]["depends_on"] == [initial["user"][0]["id"]]
        say(
            "assistant",
            "按目前单机使用的范围，推荐 SQLite，Python 端使用 SQLAlchemy 管理数据模型。如果近期就要作为多人共用的服务部署，可以选 PostgreSQL。你这次希望先用哪一种？",
            ["initial-guide"],
        )
        say("user", "先用 SQLite 和 SQLAlchemy。沿用现在的业务逻辑，不增加其他流程。")
        fixture.config["stores"][0]["selection"] = {
            "source": "user",
            "answer": turns[-1]["content"],
            "locator": "scripted-dialogue:turn-3",
        }
        fixture.enable_exporter()
        (root / "image_store.py").write_text(
            "def list_images(connection):\n    return connection.exec_driver_sql('SELECT id, title FROM images ORDER BY id').fetchall()\n",
            encoding="utf-8",
        )
        fixture.config["operations"][0]["source"] = {
            "path": "image_store.py",
            "symbol": "list_images",
        }
        fixture.write_config()
        repeated = command("confirmed-guide", "guide")
        assert repeated["user"] == []
        assert repeated["coding"][0]["depends_on"] == []
        command("initial-sync", "sync")
        command("initial-check", "check")
        with closing(sqlite3.connect(fixture.database)) as connection, connection:
            connection.execute("INSERT INTO images VALUES (1, 'Synthetic image')")

        from sqlalchemy import create_engine

        project = json.loads((root / "bo_stategraph/project.json").read_text(encoding="utf-8"))
        manifest = capture(root, project["model"])
        events = []
        probe = BOProbe(
            project, manifest["build_id"], sink=lambda event, kind: events.append(event)
        )
        runtime = BODataRuntime(probe, fixture.config)
        engine = create_engine("sqlite:///" + str(fixture.database))
        runtime.attach_sqlalchemy(engine)
        spec = importlib.util.spec_from_file_location(
            "bo_dialogue_image_store", root / "image_store.py"
        )
        application = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(application)
        try:
            with runtime.operation("db.query"), engine.connect() as connection:
                rows = application.list_images(connection)
            assert len(rows) == 1
            assert probe.flush()
            count = len(events)
            with runtime.operation("db.query"), bo_internal(), engine.connect() as connection:
                connection.exec_driver_sql("SELECT COUNT(*) FROM images").scalar()
            assert probe.flush()
            assert len(events) == count == 2
            for event in events:
                validate_event(event, project, manifest["build_id"])
            assert (
                runtime_errors(
                    root,
                    {"runs": [{"case": "query-success", "mode": "on", "events": events}]},
                    project["model"],
                )
                == []
            )
        finally:
            runtime.close()
            probe.close()
            engine.dispose()
        say(
            "assistant",
            "已按你的选择接入。图中可以看到 images 表、字段以及 list_images 的读取关系；实际查询已采集，观察器自己的统计查询没有进入记录。业务流程保持原样。",
            ["confirmed-guide", "initial-sync", "initial-check", "runtime-query"],
        )
        say("user", "在图片数据中增加一个 reviewed 字段，先保留现有流程。")
        changed = fixture.model_source.replace(
            "nullable=False))", "nullable=False), Column('reviewed', Integer))"
        )
        (root / "models.py").write_text(changed, encoding="utf-8")
        pending = command("pending-migration-sync", "sync", expected=1)
        assert any(
            isinstance(error, dict)
            and error.get("schema_difference", {}).get("field") == "reviewed"
            for error in pending["errors"]
        )
        command("pending-migration-check", "check", expected=1)
        say(
            "assistant",
            "模型已增加 reviewed，图中已标明这个字段还没有出现在实际数据库中；本轮检查暂未通过。我会完成对应迁移后再核对。",
            ["pending-migration-sync", "pending-migration-check"],
        )
        with closing(sqlite3.connect(fixture.database)) as connection, connection:
            connection.execute("ALTER TABLE images ADD COLUMN reviewed INTEGER")
        command("migrated-sync", "sync")
        command("migrated-check", "check")
        say(
            "assistant",
            "迁移完成，实际数据库和模型中的 reviewed 已对应，重新检查通过。没有增加审核规则或新的业务步骤。",
            ["migrated-sync", "migrated-check"],
        )

        existing = deepcopy(fixture.config)
        existing["stores"][0].update(
            engine="mongodb",
            model_layer="Mongoose",
            url_env="BO_EXISTING_MONGODB_URL",
            selection={
                "source": "user",
                "answer": "已有 MongoDB 和 Mongoose，沿用即可。",
                "locator": "scripted-dialogue:existing-project",
            },
        )
        (root / "bo_stategraph/databases.json").write_text(json.dumps(existing), encoding="utf-8")
        reuse = command("existing-mongodb-guide", "guide")
        assert reuse["user"] == []
        assert reuse["coding"][0]["depends_on"] == []
        say("user", "另一个已有工程使用 MongoDB 和 Mongoose，继续沿用即可。")
        say(
            "assistant",
            "沿用 MongoDB 和 Mongoose，并接入相应的模型导出和查询采集。Mongoose 的应用校验与数据库中的验证规则会分别标明。",
            ["existing-mongodb-guide"],
        )
        record = {
            "kind": "scripted-simulated-dialogue",
            "date": "2026-10-24",
            "skill_sha256": hashlib.sha256(
                (ROOT / "skills/business-observer/SKILL.md").read_bytes()
            ).hexdigest(),
            "scope": "Storage selection, native model export, real SQLite schema update, runtime query and observer exclusion. Existing business graph uses the shared integration fixture.",
            "limitations": [
                "Scripted human and assistant turns, not an independent LLM or human usability test.",
                "The existing-MongoDB branch tests decision reuse only; live MongoDB collection is covered by the separate live suite.",
                "This is not a complete image-review product acceptance.",
            ],
            "turns": turns,
            "commands": commands,
            "runtime": {
                "events": events,
                "business_rows": len(rows),
                "observer_query_added_events": 0,
                "required_cases_valid": True,
            },
            "checks": {
                "one_initial_question": True,
                "confirmed_choice_not_reasked": True,
                "coding_wiring_requires_choice": True,
                "unapplied_migration_rejected": True,
                "migration_retest_passed": True,
                "existing_mongodb_reused": True,
                "unsolicited_business_features_added": [],
            },
        }
        (output / "dialogue.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        lines = [
            "# Scripted database-selection dialogue",
            "",
            "Date: 2026-10-24. This is a **scripted simulation**, with real CLI, native model export, SQLite migration, and runtime-query execution. It is not an independent LLM or human test. The existing graph is the shared integration fixture; this is a storage workflow test, not acceptance of a complete image-review product.",
            "",
            "The maintained Skill was read before the trial; its exact SHA-256 and complete command results are in [dialogue.json](dialogue.json). Reproduce with `python tools/test_database_dialogue.py --out docs/review/db-vis`. `$TRIAL` in the record denotes the temporary project directory.",
            "",
            "## Conversation",
            "",
        ]
        for index, turn in enumerate(turns, 1):
            lines.extend([f"**{index}. Simulated {turn['role']}**", "", turn["content"], ""])
            if turn["evidence"]:
                lines.extend(
                    [
                        "Executed evidence: "
                        + ", ".join(f"`{item}`" for item in turn["evidence"])
                        + ".",
                        "",
                    ]
                )
        lines.extend(
            [
                "## Executed command outcomes",
                "",
                "| Step | Command | Exit | Outcome |",
                "| --- | --- | ---: | --- |",
            ]
        )
        for item in commands:
            result = item["result"]
            outcome = (
                f"{len(result['user'])} user question(s)"
                if "user" in result
                else f"valid={str(result['valid']).lower()}"
            )
            lines.append(
                f"| {item['id']} | `bo_db.py {item['command'][2]}` | {item['exit_code']} | {outcome} |"
            )
        lines.extend(
            [
                "",
                "## Review",
                "",
                "The initial prompt rendered one relevant tradeoff question. An explicit choice removed the question and released the coding tasks. The model change was exported automatically; an unapplied database migration failed both synchronization and independent checking, then passed after the real ALTER TABLE. An actual query produced two probe events and the observer's own query produced none. The existing-MongoDB choice was reused without a new selection question. The authored conversation adds no new business flow; this last conclusion is a transcript review, not a proof of arbitrary future AI behavior.",
                "",
            ]
        )
        (output / "dialogue.md").write_text("\n".join(lines), encoding="utf-8")
        return record["checks"]
    finally:
        fixture.doCleanups()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "docs/review/db-vis")
    args = parser.parse_args()
    print(json.dumps(trial(args.out.resolve()), indent=2))


if __name__ == "__main__":
    main()
