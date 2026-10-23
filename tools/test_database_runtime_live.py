"""Exercise real local database servers using synthetic records and the shipped adapter.

Start examples/database-observer/compose.yaml (or provide BO_TEST_*_URL values). This test
does not use emulator clients or mock responses. It deletes only its own uniquely
named tables, collection, Redis key, and Neo4j nodes after recording observations.
"""

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/business-observer/scripts"))

from bo_observer.adapters.python.bo_probe import BOProbe
from bo_observer.data.runtime import BODataRuntime
from bo_observer.observation.observation_scope import bo_internal
from bo_observer.protocol import schema_check


def bo_runtime(store):
    """Build only the capture declarations needed for this independent native test."""
    inputs = {"operation": "string", "statement": "string", "parameters": {"limit": "number"}}
    outputs = {
        "status": "string",
        "duration_ms": "number",
        "rows": "number",
        "rows_known": "boolean",
        "target_source": "string",
        "result": {"count": "number"},
        "before": {"count": "number"},
        "error_type": "string",
        "transaction_id": "string",
        "targets": ["string"],
        "unknown_targets": ["string"],
        "target_access": [{"target": "string", "action": "string"}],
        "input_count": "number",
        "output_count": "number",
        "committed": "boolean",
    }
    operations = [
        {
            "id": name,
            "action": action,
            "parameters": {"limit": "number"},
            "before": {"count": "number"},
            "after": {"count": "number"},
        }
        for name, action in (
            ("read", "read"),
            ("write", "write"),
            ("transform", "transform"),
            ("transaction", "transaction"),
        )
    ]
    project = {
        "project_id": "db-runtime-" + store,
        "model": {
            "revision": "1",
            "nodes": [
                {"id": item["id"], "capture": {"in": inputs, "out": outputs}} for item in operations
            ],
        },
    }
    events = []
    probe = BOProbe(project, "live-database-1", sink=lambda body, kind: events.append(body))
    return BODataRuntime(probe, {"operations": operations}), probe, events


def bo_summary(runtime, probe, events, assertions, limitations=()):
    assert probe.flush(), "native event queue did not flush"
    assert probe.bo_errors == 0, "probe rejected an observation"
    for event in events:
        schema_check(event, "event")
    serialized = json.dumps(events)
    for forbidden in ("bo_test_local_only", "private_title_", "private_password_"):
        assert forbidden not in serialized, "unselected value entered event stream"
    assert any(event["phase"] == "error" for event in events), "driver failure was not observed"
    assert any(
        event["phase"] == "change" for event in events
    ), "data transformation was not observed"
    assert all(
        event["outputs"]["targets"] for event in events if event["node"] in {"read", "write"}
    ), "actual database target missing"
    return {
        "status": "passed",
        "assertions": assertions,
        "limitations": list(limitations),
        "probe_errors": probe.bo_errors,
        "runtime_errors": runtime.bo_errors,
        "suppressed": runtime.bo_suppressed,
        "events": events,
    }


def bo_postgres():
    from sqlalchemy import Boolean, Integer, String, create_engine, inspect, select
    from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
    from sqlalchemy.exc import IntegrityError

    engine = create_engine(
        os.environ.get(
            "BO_TEST_POSTGRES_URL",
            "postgresql+pg8000://bo_test:bo_test_local_only@127.0.0.1:19432/bo_test",
        )
    )
    runtime, probe, events = bo_runtime("postgresql")
    runtime.attach_sqlalchemy(engine)
    name = "bo_runtime_" + uuid.uuid4().hex[:12]

    class BOBase(DeclarativeBase):
        pass

    class BOImage(BOBase):
        __tablename__ = name
        id: Mapped[int] = mapped_column(Integer, primary_key=True)
        title: Mapped[str] = mapped_column(String(100))
        visible: Mapped[bool] = mapped_column(Boolean)

    try:
        with bo_internal():
            BOBase.metadata.create_all(engine)
            with Session(engine) as session, session.begin():
                session.add_all(
                    [
                        BOImage(id=i, title=f"private_title_{i}", visible=i % 2 == 0)
                        for i in range(1, 5)
                    ]
                )
        with runtime.operation("read", {"limit": 4}), Session(engine) as session:
            records = session.scalars(select(BOImage).order_by(BOImage.id)).all()
        read_event = runtime.last_event_id
        approved = runtime.transform(
            "transform",
            lambda values: [value for value in values if value.visible],
            records,
            before=lambda values: {"count": len(values)},
            after=lambda values: {"count": len(values)},
            depends=[read_event],
        )
        assert len(approved) == 2
        transform_event = runtime.last_event_id
        with runtime.transaction("transaction", engine.begin()) as connection:
            with runtime.operation("write", depends=[transform_event]):
                connection.execute(
                    BOImage.__table__.update()
                    .where(BOImage.id.in_([item.id for item in approved]))
                    .values(title="private_title_updated")
                )
        try:
            with runtime.transaction("transaction", engine.begin()) as connection:
                with runtime.operation("write"):
                    connection.execute(
                        BOImage.__table__.insert().values(
                            id=9, title="private_title_rollback", visible=False
                        )
                    )
                raise ValueError("rollback synthetic operation")
        except ValueError:
            pass
        try:
            with runtime.operation("write"), engine.begin() as connection:
                connection.execute(
                    BOImage.__table__.insert().values(
                        id=1, title="private_title_duplicate", visible=False
                    )
                )
        except IntegrityError:
            pass
        else:
            raise AssertionError("duplicate key was accepted")
        with Session(engine) as session:
            rows = session.scalars(select(BOImage).order_by(BOImage.id)).all()
            assert len(rows) == 4 and sum(row.title == "private_title_updated" for row in rows) == 2
        probe.flush()
        size = len(events)
        with runtime.operation("read"), bo_internal():
            assert name in inspect(engine).get_table_names()
        probe.flush()
        assert len(events) == size, "observer reflection was captured"
        assert sum(event["phase"] == "commit" for event in events) == 1
        assert any(event["outputs"].get("status") == "rolled_back" for event in events)
        return bo_summary(
            runtime,
            probe,
            events,
            [
                "real ORM query",
                "4-to-2 transform",
                "committed update of two rows",
                "rollback leaves four rows",
                "duplicate-key failure",
                "observer reflection excluded",
                "selected values only",
                "explicit causal dependencies",
            ],
        )
    finally:
        with bo_internal():
            BOBase.metadata.drop_all(engine)
        runtime.close()
        probe.close()
        engine.dispose()


def bo_mongodb():
    from pymongo import MongoClient
    from pymongo.errors import DuplicateKeyError

    runtime, probe, events = bo_runtime("mongodb")
    listener = runtime.pymongo_listener()
    client = MongoClient(
        os.environ.get("BO_TEST_MONGODB_URL", "mongodb://127.0.0.1:19017/bo_test"),
        event_listeners=[listener],
        serverSelectionTimeoutMS=5000,
    )
    listener.bo_connection = client
    collection = client.get_default_database()["bo_runtime_" + uuid.uuid4().hex[:12]]
    try:
        with bo_internal():
            collection.insert_many(
                [
                    {"_id": i, "title": f"private_title_{i}", "visible": i % 2 == 0}
                    for i in range(1, 5)
                ]
            )
        with runtime.operation("read"):
            cursor = collection.find({}).batch_size(2)
            assert (
                runtime.last_event_id is None
            ), "creating a lazy cursor should not execute a command"
            records = list(cursor)
        read_event = runtime.last_event_id
        approved = runtime.transform(
            "transform",
            lambda values: [value for value in values if value["visible"]],
            records,
            before=lambda values: {"count": len(values)},
            after=lambda values: {"count": len(values)},
            depends=[read_event],
        )
        with runtime.operation("write", depends=[runtime.last_event_id]):
            result = collection.update_many(
                {"_id": {"$in": [value["_id"] for value in approved]}},
                {"$set": {"title": "private_title_updated"}},
            )
        assert result.modified_count == 2
        try:
            with runtime.operation("write"):
                collection.insert_one({"_id": 1, "title": "private_title_duplicate"})
        except DuplicateKeyError:
            pass
        else:
            raise AssertionError("duplicate key was accepted")
        assert collection.count_documents({"title": "private_title_updated"}) == 2
        probe.flush()
        size = len(events)
        with bo_internal(), runtime.operation("read"):
            list(collection.find({}))
        runtime.exclude_connection(client)
        with runtime.operation("read"):
            list(collection.find({}))
        probe.flush()
        assert len(events) == size, "observer collection query was captured"
        commands = {event["inputs"]["statement"] for event in events}
        assert {"find", "getMore", "update", "insert"} <= commands
        return bo_summary(
            runtime,
            probe,
            events,
            [
                "real PyMongo command monitoring",
                "lazy cursor starts only during consumption",
                "find/getMore calls",
                "4-to-2 transform",
                "two documents updated",
                "duplicate-key failure",
                "observer and exact-client exclusion",
            ],
            [
                "The local MongoDB service is standalone; multi-document transaction behavior is not tested."
            ],
        )
    finally:
        with bo_internal():
            collection.drop()
        client.close()
        runtime.close()
        probe.close()


def bo_redis():
    import redis

    runtime, probe, events = bo_runtime("redis")
    client = redis.Redis.from_url(
        os.environ.get("BO_TEST_REDIS_URL", "redis://127.0.0.1:19379/15"),
        decode_responses=True,
        socket_timeout=5,
    )
    key = "bo:runtime:" + uuid.uuid4().hex
    targets = ["key_pattern:bo:runtime:*"]
    try:
        with bo_internal():
            client.hset(
                key, mapping={"1": "approved", "2": "pending", "3": "approved", "4": "pending"}
            )
        records = runtime.execute(
            "read",
            lambda: client.hgetall(key),
            connection=client,
            statement="HGETALL",
            targets=targets,
            summarize=lambda value: {"result": {"count": len(value)}},
        )
        approved = runtime.transform(
            "transform",
            lambda values: {key: value for key, value in values.items() if value == "approved"},
            records,
            before=lambda values: {"count": len(values)},
            after=lambda values: {"count": len(values)},
            depends=[runtime.last_event_id],
        )
        assert len(approved) == 2
        runtime.execute(
            "write",
            lambda: client.hset(key, mapping={item: "displayed" for item in approved}),
            connection=client,
            statement="HSET",
            targets=targets,
            depends=[runtime.last_event_id],
        )
        assert sum(value == "displayed" for value in client.hgetall(key).values()) == 2
        try:
            runtime.execute(
                "read", lambda: client.get(key), connection=client, statement="GET", targets=targets
            )
        except redis.ResponseError:
            pass
        else:
            raise AssertionError("wrong Redis value type was accepted")
        probe.flush()
        size = len(events)
        with bo_internal():
            runtime.execute(
                "read", lambda: client.hgetall(key), connection=client, statement="HGETALL"
            )
        runtime.exclude_connection(client)
        runtime.execute("read", lambda: client.hgetall(key), connection=client, statement="HGETALL")
        probe.flush()
        assert len(events) == size
        return bo_summary(
            runtime,
            probe,
            events,
            [
                "real Redis commands",
                "hash read",
                "4-to-2 transform",
                "two fields updated",
                "wrong-type failure",
                "observer and exact-client exclusion",
            ],
            [
                "Redis pipelines and partial EXEC failures require a driver-specific transaction adapter; this suite does not claim rollback semantics."
            ],
        )
    finally:
        with bo_internal():
            client.delete(key)
        client.close()
        runtime.close()
        probe.close()


def bo_neo4j():
    from neo4j import GraphDatabase
    from neo4j.exceptions import CypherSyntaxError

    url = urlsplit(
        os.environ.get("BO_TEST_NEO4J_URL", "bolt://neo4j:bo_test_local_only@127.0.0.1:19687")
    )
    driver = GraphDatabase.driver(
        f"{url.scheme}://{url.hostname}:{url.port}",
        auth=(url.username, url.password),
        connection_timeout=5,
    )
    runtime, probe, events = bo_runtime("neo4j")
    run = uuid.uuid4().hex
    targets = ["label:BODataRuntimeTest"]
    try:
        with driver.session() as session:
            with bo_internal():
                session.run(
                    "UNWIND range(1,4) AS id CREATE (:BODataRuntimeTest {run:$run,id:id,title:'private_title_new',visible:id % 2 = 0})",
                    run=run,
                ).consume()
            records = runtime.execute(
                "read",
                lambda: list(
                    session.run(
                        "MATCH (n:BODataRuntimeTest {run:$run}) RETURN n.id AS id,n.visible AS visible ORDER BY id",
                        run=run,
                    )
                ),
                connection=session,
                statement="MATCH (n:BODataRuntimeTest {run:$run}) RETURN n.id,n.visible",
                language="cypher",
                targets=targets,
                summarize=lambda value: {"rows": len(value), "result": {"count": len(value)}},
            )
            approved = runtime.transform(
                "transform",
                lambda values: [value for value in values if value["visible"]],
                records,
                before=lambda values: {"count": len(values)},
                after=lambda values: {"count": len(values)},
                depends=[runtime.last_event_id],
            )
            assert len(approved) == 2

            @contextmanager
            def transaction():
                # Neo4j's raw transaction context does not commit on normal exit.
                # This explicit adapter supplies that documented transaction contract.
                tx = session.begin_transaction()
                try:
                    yield tx
                except BaseException:
                    tx.rollback()
                    raise
                else:
                    tx.commit()
                finally:
                    tx.close()

            with runtime.transaction("transaction", transaction()) as tx:
                runtime.execute(
                    "write",
                    lambda: tx.run(
                        "MATCH (n:BODataRuntimeTest {run:$run}) WHERE n.id IN $ids SET n.title='private_title_updated' RETURN count(n) AS count",
                        run=run,
                        ids=[item["id"] for item in approved],
                    ).single(),
                    connection=tx,
                    statement="MATCH (n:BODataRuntimeTest {run:$run}) WHERE n.id IN $ids SET n.title='private_title_updated' RETURN count(n)",
                    language="cypher",
                    targets=targets,
                    summarize=lambda value: {"rows": value["count"]},
                )
            try:
                with runtime.transaction("transaction", transaction()) as tx:
                    runtime.execute(
                        "write",
                        lambda: tx.run(
                            "CREATE (:BODataRuntimeTest {run:$run,id:9})", run=run
                        ).consume(),
                        connection=tx,
                        statement="CREATE (:BODataRuntimeTest {run:$run,id:9})",
                        language="cypher",
                        targets=targets,
                    )
                    raise ValueError("rollback synthetic operation")
            except ValueError:
                pass
            assert (
                session.run(
                    "MATCH (n:BODataRuntimeTest {run:$run}) RETURN count(n) AS count", run=run
                ).single()["count"]
                == 4
            )
            assert (
                session.run(
                    "MATCH (n:BODataRuntimeTest {run:$run}) WHERE n.title='private_title_updated' RETURN count(n) AS count",
                    run=run,
                ).single()["count"]
                == 2
            )
            try:
                runtime.execute(
                    "read",
                    lambda: list(session.run("MATCH ??? invalid")),
                    connection=session,
                    statement="MATCH ??? invalid",
                    language="cypher",
                    targets=targets,
                )
            except CypherSyntaxError:
                pass
            else:
                raise AssertionError("invalid Cypher was accepted")
            probe.flush()
            size = len(events)
            with bo_internal():
                runtime.execute(
                    "read", lambda: session.run("RETURN 1").consume(), connection=session
                )
            runtime.exclude_connection(session)
            runtime.execute("read", lambda: session.run("RETURN 1").consume(), connection=session)
            probe.flush()
            assert len(events) == size
        assert sum(event["phase"] == "commit" for event in events) == 1
        return bo_summary(
            runtime,
            probe,
            events,
            [
                "real Bolt query and materialization",
                "4-to-2 transform",
                "two nodes updated",
                "explicit commit acknowledgement",
                "rollback leaves four nodes",
                "Cypher syntax failure",
                "observer and exact-session exclusion",
            ],
        )
    finally:
        with bo_internal(), driver.session() as session:
            session.run("MATCH (n:BODataRuntimeTest {run:$run}) DETACH DELETE n", run=run).consume()
        driver.close()
        runtime.close()
        probe.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / ".validation/database-runtime-live.json")
    args = parser.parse_args()
    results = {}
    for name, callback in (
        ("postgresql", bo_postgres),
        ("mongodb", bo_mongodb),
        ("redis", bo_redis),
        ("neo4j", bo_neo4j),
    ):
        try:
            results[name] = callback()
            print(
                json.dumps(
                    {"database": name, "status": "passed", "events": len(results[name]["events"])}
                )
            )
        except Exception as error:
            # Error text can contain connection strings or user values; keep only type.
            results[name] = {"status": "failed", "error_type": type(error).__name__}
            print(json.dumps({"database": name, **results[name]}))
    report = {
        "status": (
            "passed" if all(item["status"] == "passed" for item in results.values()) else "failed"
        ),
        "databases": results,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
