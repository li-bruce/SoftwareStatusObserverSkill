"""Real SQLite execution plus fault, privacy, cursor, and transaction regressions."""

import asyncio
from contextlib import asynccontextmanager, contextmanager
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/vibelens/scripts"))

from bo_observer.adapters.python.bo_probe import BOProbe
from bo_observer.data.runtime import BODataRuntime, bo_query_shape, _bo_sql_access
from bo_observer.observation.observation_scope import bo_internal
from bo_observer.protocol import schema_check


def bo_fixture():
    """Capture policy intentionally allows a few values, never arbitrary row objects."""
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
    nodes = [
        {"id": name, "capture": {"in": inputs, "out": outputs}}
        for name in ("query", "transform", "transaction")
    ]
    config = {
        "operations": [
            {
                "id": "query",
                "action": "read",
                "parameters": {"limit": "number"},
                "after": {"count": "number"},
            },
            {
                "id": "transform",
                "action": "transform",
                "before": {"count": "number"},
                "after": {"count": "number"},
            },
            {"id": "transaction", "action": "transaction"},
        ]
    }
    return {"project_id": "database-test", "model": {"revision": "1", "nodes": nodes}}, config


class DatabaseRuntimeTests(unittest.TestCase):
    def setUp(self):
        from sqlalchemy import create_engine

        (ROOT / ".validation").mkdir(exist_ok=True)
        self.bo_folder = tempfile.TemporaryDirectory(dir=ROOT / ".validation")
        self.bo_engine = create_engine(
            "sqlite:///" + str(Path(self.bo_folder.name) / "store.sqlite")
        )
        with self.bo_engine.begin() as connection:
            connection.exec_driver_sql("CREATE TABLE image (id INTEGER PRIMARY KEY, title TEXT)")
            connection.exec_driver_sql("INSERT INTO image VALUES (1, 'private title')")
        self.bo_events = []
        project, config = bo_fixture()
        self.bo_probe = BOProbe(
            project, "build-1", sink=lambda body, kind: self.bo_events.append(body)
        )
        self.bo_runtime = BODataRuntime(self.bo_probe, config)
        self.bo_runtime.attach_sqlalchemy(self.bo_engine)

    def tearDown(self):
        self.bo_runtime.close()
        self.bo_probe.close()
        self.bo_engine.dispose()
        self.bo_folder.cleanup()

    def bo_results(self):
        self.assertTrue(self.bo_probe.flush())
        self.assertEqual(self.bo_probe.bo_errors, 0)
        for event in self.bo_events:
            schema_check(event, "event")
        return self.bo_events

    def test_real_driver_query_redacts_literals_and_keeps_cursor_unconsumed(self):
        with self.bo_runtime.operation("query", {"limit": 2, "password": "sensitive"}):
            with self.bo_engine.connect() as connection:
                result = connection.exec_driver_sql(
                    "SELECT * FROM image WHERE title = 'private title' /* secret comment */"
                )
                self.assertEqual(result.fetchone().title, "private title")
                self.assertIsNone(result.fetchone())
        events = self.bo_results()
        self.assertEqual([event["phase"] for event in events], ["enter", "return"])
        self.assertEqual(events[0]["call_id"], events[1]["call_id"])
        self.assertEqual(events[1]["outputs"]["targets"], ["table:image"])
        self.assertEqual(events[1]["outputs"]["target_source"], "parsed_sql")
        self.assertFalse(events[1]["outputs"]["rows_known"])
        self.assertNotIn("committed", events[1]["outputs"])
        self.assertEqual(events[0]["inputs"]["parameters"], {"limit": 2})
        text = json.dumps(events)
        for forbidden in ("private title", "secret comment", "password", "sensitive"):
            self.assertNotIn(forbidden, text)

    def test_real_write_commit_and_rollback_match_database_rows(self):
        with self.bo_runtime.transaction("transaction", self.bo_engine.begin()) as connection:
            with self.bo_runtime.operation("query"):
                connection.exec_driver_sql("INSERT INTO image VALUES (2, 'new')")
        failure = ValueError("business refusal with private value")
        with self.assertRaises(ValueError) as raised:
            with self.bo_runtime.transaction("transaction", self.bo_engine.begin()) as connection:
                with self.bo_runtime.operation("query"):
                    connection.exec_driver_sql("INSERT INTO image VALUES (3, 'rolled back')")
                raise failure
        self.assertIs(raised.exception, failure)
        with self.bo_engine.connect() as connection:
            self.assertEqual(
                connection.exec_driver_sql("SELECT id FROM image ORDER BY id").scalars().all(),
                [1, 2],
            )
        events = self.bo_results()
        commits = [event for event in events if event["phase"] == "commit"]
        self.assertEqual(len(commits), 1)
        self.assertEqual(events[-1]["outputs"]["status"], "rolled_back")
        query_events = [event for event in events if event["node"] == "query"]
        self.assertTrue(all(event["outputs"].get("transaction_id") for event in query_events))
        self.assertEqual(query_events[1]["outputs"]["rows"], 1)
        self.assertNotIn("business refusal", json.dumps(events))

    def test_driver_error_keeps_actual_exception_and_does_not_leak_parameters(self):
        from sqlalchemy.exc import IntegrityError

        with self.assertRaises(IntegrityError):
            with self.bo_runtime.operation("query"):
                with self.bo_engine.begin() as connection:
                    connection.exec_driver_sql(
                        "INSERT INTO image VALUES (?, ?)", (1, "private second title")
                    )
        events = self.bo_results()
        self.assertEqual([event["phase"] for event in events], ["enter", "error"])
        self.assertEqual(events[-1]["outputs"]["error_type"], "IntegrityError")
        self.assertNotIn("private second title", json.dumps(events))

    def test_observer_metadata_and_exact_connection_exclusion(self):
        with self.bo_runtime.operation("query"):
            with bo_internal(), self.bo_engine.connect() as connection:
                self.assertEqual(
                    connection.exec_driver_sql("SELECT COUNT(*) FROM image").scalar(), 1
                )
            with self.bo_engine.connect() as connection:
                self.bo_runtime.exclude_connection(connection)
                self.assertEqual(
                    connection.exec_driver_sql("SELECT COUNT(*) FROM image").scalar(), 1
                )
            with self.bo_engine.connect() as connection:
                connection.exec_driver_sql("SELECT COUNT(*) FROM image").scalar()
        self.assertEqual(len(self.bo_results()), 2)
        self.bo_runtime.exclude_connection(self.bo_engine)
        with self.bo_runtime.operation("query"), self.bo_engine.connect() as connection:
            connection.exec_driver_sql("SELECT COUNT(*) FROM image").scalar()
        self.assertEqual(len(self.bo_results()), 2)

    def test_probe_sink_queries_do_not_recursively_capture(self):
        sinks = []

        def sink(body, kind):
            sinks.append(body)
            self.bo_runtime.execute("query", lambda: None, statement="internal")

        self.bo_probe.bo_sink = sink
        self.bo_runtime.execute("query", lambda: 42, statement="get")
        self.assertTrue(self.bo_probe.flush())
        self.assertEqual(len(sinks), 2)
        self.assertGreaterEqual(self.bo_runtime.bo_suppressed, 2)

    def test_generic_wrapper_preserves_lazy_identity_and_summarizer_failure(self):
        consumed = []

        def values():
            consumed.append(True)
            yield "private value"

        iterator = values()
        result = self.bo_runtime.execute(
            "query", lambda: iterator, statement="find", targets=["collection:image"]
        )
        self.assertIs(result, iterator)
        self.assertEqual(consumed, [])
        self.assertEqual(next(iterator), "private value")

        def broken_summary(value):
            raise RuntimeError("secret")

        marker = object()
        self.assertIs(
            self.bo_runtime.execute(
                "query", lambda: marker, statement="get", summarize=broken_summary
            ),
            marker,
        )
        events = self.bo_results()
        self.assertEqual(events[1]["outputs"]["status"], "returned")
        self.assertFalse(events[1]["outputs"]["rows_known"])
        self.assertEqual(self.bo_runtime.bo_errors, 1)
        self.assertNotIn("private value", json.dumps(events))

    def test_transform_selected_before_after_and_identity(self):
        original = [1, 2, 3]
        final = [2, 3]
        result = self.bo_runtime.transform(
            "transform",
            lambda values: final,
            original,
            before=lambda values: {"count": len(values), "private": "hidden"},
            after=lambda values: {"count": len(values), "rows": values},
        )
        self.assertIs(result, final)
        outputs = self.bo_results()[-1]["outputs"]
        self.assertEqual(outputs["before"], {"count": 3})
        self.assertEqual(outputs["result"], {"count": 2})
        self.assertEqual((outputs["input_count"], outputs["output_count"]), (3, 2))

    def test_in_place_transform_preserves_initial_count_and_values(self):
        values = [1, 2, 3]

        def shrink(items):
            items.pop()
            return items

        self.assertIs(
            self.bo_runtime.transform(
                "transform",
                shrink,
                values,
                before=lambda items: {"count": len(items)},
                after=lambda items: {"count": len(items)},
            ),
            values,
        )
        outputs = self.bo_results()[-1]["outputs"]
        self.assertEqual(outputs["before"], {"count": 3})
        self.assertEqual((outputs["input_count"], outputs["output_count"]), (3, 2))

    def test_explicit_rollback_inside_manager_never_claims_commit(self):
        with self.bo_runtime.transaction("transaction", self.bo_engine.begin()) as connection:
            connection.exec_driver_sql("INSERT INTO image VALUES (2, 'discard')")
            connection.rollback()
        with self.bo_engine.connect() as connection:
            self.assertEqual(connection.exec_driver_sql("SELECT COUNT(*) FROM image").scalar(), 1)
        events = self.bo_results()
        self.assertEqual(events[-1]["outputs"]["status"], "ended_before_exit")
        self.assertNotIn("committed", events[-1]["outputs"])
        self.assertFalse(any(event["phase"] == "commit" for event in events))

    def test_transform_failure_and_capture_fault_do_not_replace_application_error(self):
        failure = RuntimeError("private business failure")

        def transform(values):
            raise failure

        with self.assertRaises(RuntimeError) as raised:
            self.bo_runtime.transform(
                "transform", transform, [], before=lambda values: {"count": 0}
            )
        self.assertIs(raised.exception, failure)
        self.assertEqual(self.bo_results()[-1]["phase"], "error")
        self.bo_probe.record = lambda *args, **kwargs: (_ for _ in ()).throw(
            ValueError("collector fault")
        )
        self.assertEqual(self.bo_runtime.execute("query", lambda: 42, statement="get"), 42)

    def test_commit_failure_is_not_reported_as_committed(self):
        @contextmanager
        def failing_commit():
            yield
            raise OSError("commit failed")

        with self.assertRaises(OSError):
            with self.bo_runtime.transaction("transaction", failing_commit()):
                pass
        events = self.bo_results()
        self.assertEqual(events[-1]["outputs"]["status"], "failed")
        self.assertNotIn("committed", events[-1]["outputs"])
        self.assertFalse(any(event["phase"] == "commit" for event in events))

    def test_error_after_manual_commit_does_not_claim_rollback(self):
        with self.assertRaises(ValueError):
            with self.bo_runtime.transaction("transaction", self.bo_engine.begin()) as connection:
                connection.exec_driver_sql("INSERT INTO image VALUES (2, 'committed early')")
                connection.commit()
                raise ValueError("later application failure")
        with self.bo_engine.connect() as connection:
            self.assertEqual(connection.exec_driver_sql("SELECT COUNT(*) FROM image").scalar(), 2)
        outputs = self.bo_results()[-1]["outputs"]
        self.assertEqual(outputs["status"], "ended_before_exit")
        self.assertNotIn("committed", outputs)

    def test_async_concurrent_contexts_and_cancellation(self):
        async def run():
            async def work(value):
                await asyncio.sleep(0)
                return value

            result = await asyncio.gather(
                *[
                    self.bo_runtime.execute_async(
                        "query", lambda value=value: work(value), statement="get", entity=str(value)
                    )
                    for value in range(3)
                ]
            )
            self.assertEqual(result, [0, 1, 2])

            async def cancelled():
                raise asyncio.CancelledError()

            with self.assertRaises(asyncio.CancelledError):
                await self.bo_runtime.execute_async(
                    "query", cancelled, statement="get", entity="cancelled"
                )

            @asynccontextmanager
            async def manager():
                yield object()

            async with self.bo_runtime.transaction_async("transaction", manager()):
                await self.bo_runtime.execute_async("query", lambda: work(7), statement="get")

        asyncio.run(run())
        events = self.bo_results()
        for value in range(3):
            selected = [event for event in events if event["entity"] == str(value)]
            self.assertEqual(len(selected), 2)
            self.assertEqual(selected[0]["call_id"], selected[1]["call_id"])
        cancelled = [event for event in events if event["entity"] == "cancelled"]
        self.assertEqual(cancelled[-1]["outputs"]["error_type"], "CancelledError")
        self.assertEqual(events[-1]["phase"], "commit")

    def test_listener_detach_restores_unobserved_execution(self):
        self.bo_runtime.close()
        with self.bo_runtime.operation("query"), self.bo_engine.connect() as connection:
            connection.exec_driver_sql("SELECT * FROM image").all()
        self.assertEqual(self.bo_results(), [])


class QueryShapeTests(unittest.TestCase):
    def test_explicit_sql_table_roles_and_unresolved_alias(self):
        self.assertEqual(
            _bo_sql_access("INSERT INTO image SELECT * FROM image"),
            (
                [
                    {"target": "table:image", "action": "read"},
                    {"target": "table:image", "action": "write"},
                ],
                [],
            ),
        )
        self.assertEqual(
            _bo_sql_access(
                "UPDATE image SET title = source.title FROM source WHERE image.id = source.id"
            )[0],
            [
                {"target": "table:image", "action": "write"},
                {"target": "table:source", "action": "read"},
            ],
        )
        self.assertEqual(
            _bo_sql_access("UPDATE i SET title = 'x' FROM image AS i", "tsql")[1],
            ["target_access_not_inferred"],
        )

    def test_native_sql_literal_forms_are_redacted(self):
        cases = [
            ("postgres", "SELECT $$private_dollar$$ FROM image", "private_dollar"),
            ("postgres", "SELECT $tag$private_tagged$tag$ FROM image", "private_tagged"),
            ("postgres", "SELECT E'private_escape\\n' FROM image", "private_escape"),
            ("postgres", "SELECT U&'private_unicode' FROM image", "private_unicode"),
            ("postgres", "SELECT X'736563726574' FROM image", "736563726574"),
            ("postgres", "SELECT B'01110011' FROM image", "01110011"),
            ("mysql", "SELECT 0x736563726574 FROM image", "736563726574"),
            ("mysql", "SELECT _utf8'private_charset' FROM image", "private_charset"),
            ("tsql", "SELECT N'private_national' FROM image", "private_national"),
        ]
        for dialect, statement, forbidden in cases:
            with self.subTest(dialect=dialect, statement=statement):
                shape, targets, unknown = bo_query_shape(statement, dialect=dialect)
                self.assertNotIn(forbidden, shape)
                self.assertEqual(targets, ["table:image"])
                self.assertEqual(unknown, [])

    def test_sql_cte_and_literal_redaction(self):
        shape, targets, unknown = bo_query_shape(
            "WITH filtered AS (SELECT * FROM image WHERE title='private') SELECT * FROM filtered WHERE id>123"
        )
        self.assertEqual(targets, ["table:image"])
        self.assertEqual(unknown, [])
        self.assertNotIn("private", shape)
        self.assertNotIn("123", shape)

    def test_cypher_and_invalid_queries_never_fall_back_to_raw_text(self):
        shape, targets, unknown = bo_query_shape(
            'MATCH (n:Image) WHERE n.title="private" RETURN n LIMIT 42 // secret', "cypher"
        )
        self.assertNotIn("private", shape)
        self.assertNotIn("secret", shape)
        self.assertNotIn("42", shape)
        self.assertEqual(targets, [])
        self.assertIn("cypher_targets_not_inferred", unknown)
        for query, language in (
            ("SELECT 'private", "sql"),
            ("AUTH private", "command"),
            ("private" * 10000, "sql"),
        ):
            self.assertEqual(bo_query_shape(query, language)[0], "[query shape unavailable]")


if __name__ == "__main__":
    unittest.main()
