"""Observe database calls and selected transformations without owning business execution.

SQLAlchemy listeners observe statements sent to the driver. Other official clients
can use ``execute`` around their real calls; lazy results are returned untouched.
Application code decides when to consume results and when to commit transactions.
Only configured fields enter the existing BOProbe event stream.
"""

from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
import re
import time
import uuid

from ..adapters.python.bo_probe import _bo_internal as _transport_internal
from ..adapters.python.bo_probe import bo_selected
from ..observation.observation_scope import bo_internal, bo_is_internal


_bo_scope = ContextVar("bo_database_operation", default=None)
_bo_transaction = ContextVar("bo_database_transaction", default=None)
_bo_capturing = ContextVar("bo_database_capture", default=False)
_UNKNOWN_QUERY = "[query shape unavailable]"


def bo_query_shape(statement, language="sql", dialect=None):
    """Return a bounded, literal-free query and proven table references.

    Unsupported SQL is withheld, rather than falling back to raw SQL. Parser
    diagnostic context is disabled because errors can otherwise contain literals.
    Cypher uses Pygments only for redaction, not for semantic target inference.
    """
    if not isinstance(statement, str) or len(statement) > 32768:
        return _UNKNOWN_QUERY, [], ["query_not_parsed"]
    if language == "command":
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", statement):
            return statement, [], []
        return _UNKNOWN_QUERY, [], ["query_not_parsed"]
    try:
        if language == "cypher":
            from pygments.lexers import get_lexer_by_name
            from pygments.token import Comment, Error, Number, String

            tokens = list(get_lexer_by_name("cypher").get_tokens(statement))
            if any(kind in Error for kind, _ in tokens):
                return _UNKNOWN_QUERY, [], ["query_not_parsed"]
            clean = "".join(
                " " if kind in Comment else "?" if kind in String or kind in Number else text
                for kind, text in tokens
            )
            return " ".join(clean.split())[:256], [], ["cypher_targets_not_inferred"]
        if language != "sql":
            return _UNKNOWN_QUERY, [], ["query_not_parsed"]
        import sqlglot
        from sqlglot import exp

        # Native quoted/encoded values are separate SQLGlot expression classes,
        # not Literal subclasses. Redact the entire value before rendering it.
        literal_types = (
            exp.Literal,
            exp.RawString,
            exp.ByteString,
            exp.UnicodeString,
            exp.National,
            exp.HexString,
            exp.BitString,
            exp.Boolean,
            exp.Null,
        )
        dialect = {"postgresql": "postgres", "mssql": "tsql", "mariadb": "mysql"}.get(
            dialect, dialect
        )
        trees = sqlglot.parse(statement, read=dialect, error_message_context=0)
        if not trees or any(tree is None or tree.find(exp.Command) for tree in trees):
            return _UNKNOWN_QUERY, [], ["query_not_parsed"]
        targets = set()
        rendered = []
        for tree in trees:
            aliases = {cte.alias_or_name for cte in tree.find_all(exp.CTE)}
            for table in tree.find_all(exp.Table):
                if not isinstance(table.this, exp.Identifier):
                    continue
                if table.name in aliases and not table.db and not table.catalog:
                    continue
                targets.add(
                    "table:" + ".".join(p for p in (table.catalog, table.db, table.name) if p)
                )
            for item in tree.walk():
                item.comments = None
            tree = tree.transform(
                lambda item: exp.Placeholder() if isinstance(item, literal_types) else item
            )
            rendered.append(tree.sql(dialect=dialect, comments=False))
        return " ".join("; ".join(rendered).split())[:256], sorted(targets), []
    except Exception:
        return _UNKNOWN_QUERY, [], ["query_not_parsed"]


def _bo_sql_access(statement, dialect=None):
    """Identify table reads and DML destinations, without claiming column lineage.

    Reads use explicit table references. INSERT/UPDATE/DELETE destinations are
    writes; implicit reads within an UPDATE are not separate data-flow claims.
    Unresolved aliases and other statement families remain unknown.
    """
    try:
        import sqlglot
        from sqlglot import exp

        dialect = {"postgresql": "postgres", "mssql": "tsql", "mariadb": "mysql"}.get(
            dialect, dialect
        )
        trees = sqlglot.parse(statement, read=dialect, error_message_context=0)
        access = set()
        for tree in trees:
            if not isinstance(tree, (exp.Query, exp.Insert, exp.Update, exp.Delete)):
                return [], ["target_access_not_inferred"]
            aliases = {cte.alias_or_name for cte in tree.find_all(exp.CTE)}
            tables = list(tree.find_all(exp.Table))
            destinations = set()
            for command in tree.find_all(exp.Insert, exp.Update, exp.Delete):
                destination = command.this
                if isinstance(destination, exp.Schema):
                    destination = destination.this
                if not isinstance(destination, exp.Table):
                    return [], ["target_access_not_inferred"]
                if any(
                    table is not destination
                    and table.alias == destination.name
                    and table.name != destination.name
                    for table in tables
                ):
                    return [], ["target_access_not_inferred"]
                destinations.add(id(destination))
            for table in tables:
                if not isinstance(table.this, exp.Identifier):
                    return [], ["target_access_not_inferred"]
                if table.name in aliases and not table.db and not table.catalog:
                    continue
                key = "table:" + ".".join(p for p in (table.catalog, table.db, table.name) if p)
                access.add((key, "write" if id(table) in destinations else "read"))
        return [{"target": key, "action": action} for key, action in sorted(access)], []
    except Exception:
        return [], ["target_access_not_inferred"]


@dataclass
class _Scope:
    runtime: object
    node: str
    parameters: dict = field(default_factory=dict)
    entity: str = "application"
    attempt: str = "application"
    scope: str = "application"
    parent_call_id: str | None = None
    depends: tuple = ()


@dataclass
class _Call:
    scope: _Scope
    call_id: str
    started: float
    inputs: dict
    targets: list
    unknown: list
    transaction_id: str | None
    target_source: str
    target_access: list


class BODataRuntime:
    """Bridge native database operations to an existing BOProbe.

    ``config`` is a bo-databases/v1 document or its operations list. Configuration
    validation belongs to the shared graph loader; runtime observation failures
    are counted in ``bo_errors`` and never replace application results/errors.
    """

    def __init__(self, probe, config):
        self.bo_probe = probe
        operations = config.get("operations", []) if isinstance(config, dict) else config
        self.bo_operations = {operation["id"]: operation for operation in operations}
        self.bo_errors = 0
        self.bo_suppressed = 0
        self.bo_excluded_connections = []
        self.bo_listeners = []
        self.bo_last_event = ContextVar("bo_database_last_event", default=None)

    @property
    def last_event_id(self):
        """The last successfully queued event in this task, for explicit causal links."""
        return self.bo_last_event.get()

    def exclude_connection(self, connection):
        """Register an exact observer-only client, connection, or SQLAlchemy engine."""
        if not any(item is connection for item in self.bo_excluded_connections):
            self.bo_excluded_connections.append(connection)

    def _allowed(self, connection=None):
        internal = bo_is_internal() or _transport_internal.get() or _bo_capturing.get()
        engine = getattr(connection, "engine", None) if connection is not None else None
        excluded = any(
            item is connection or (engine is not None and item is engine)
            for item in self.bo_excluded_connections
        )
        if internal or excluded:
            self.bo_suppressed += 1
            return False
        return True

    def _selected(self, value, spec):
        """Copy allowed values now, so later mutation cannot rewrite an earlier step."""
        try:
            with bo_internal():
                return bo_selected(value, spec)
        except Exception:
            self.bo_errors += 1
            return {}

    def _scope(self, node, parameters=None, **context):
        operation = self.bo_operations[node]
        selected = self._selected(parameters or {}, operation.get("parameters", {}))
        context["depends"] = tuple(
            {"event": value, "type": "data"} if isinstance(value, str) else value
            for value in context.get("depends", ())
        )
        parent = _bo_scope.get()
        if "parent_call_id" not in context and parent is not None:
            context["parent_call_id"] = parent.parent_call_id
        return _Scope(self, node, selected, **context)

    @contextmanager
    def operation(self, node, parameters=None, **context):
        """Associate actual driver calls with a declared graph node in this task/thread."""
        scope = self._scope(node, parameters, **context)
        token = _bo_scope.set(scope)
        try:
            yield
        finally:
            _bo_scope.reset(token)

    def _emit(self, call, phase, outputs):
        token = _bo_capturing.set(True)
        try:
            payload = {
                "duration_ms": round((time.perf_counter() - call.started) * 1000, 3),
                "targets": call.targets,
                "unknown_targets": call.unknown,
                "target_source": call.target_source,
                "target_access": call.target_access,
                **outputs,
            }
            if call.transaction_id is not None:
                payload["transaction_id"] = call.transaction_id
            event_id = self.bo_probe.record(
                call.scope.node,
                phase,
                lambda: {"inputs": call.inputs, "outputs": payload},
                entity=call.scope.entity,
                attempt=call.scope.attempt,
                scope=call.scope.scope,
                call_id=call.call_id,
                parent_call_id=call.scope.parent_call_id,
                depends=call.scope.depends,
            )
            if event_id is not None:
                self.bo_last_event.set(event_id)
            return event_id
        except Exception:
            self.bo_errors += 1
            return None
        finally:
            _bo_capturing.reset(token)

    def _begin(
        self, scope, statement="", language="command", targets=(), dialect=None, target_source=None
    ):
        try:
            with bo_internal():
                shape, inferred, unknown = bo_query_shape(statement, language, dialect)
                access, access_unknown = (
                    _bo_sql_access(statement, dialect)
                    if language == "sql" and inferred
                    else ([], [])
                )
                unknown = list(dict.fromkeys(unknown + access_unknown))
            operation = self.bo_operations[scope.node]
            explicit = [value for value in targets if isinstance(value, str) and len(value) <= 256]
            actual = sorted(set(inferred + explicit))[:64]
            if explicit:
                unknown = [value for value in unknown if value != "cypher_targets_not_inferred"]
            if not actual and not unknown and operation["action"] in {"read", "write"}:
                unknown = ["target_not_observed"]
            transaction = _bo_transaction.get()
            call = _Call(
                scope,
                uuid.uuid4().hex,
                time.perf_counter(),
                {
                    "operation": operation["action"],
                    "statement": shape,
                    "parameters": scope.parameters,
                },
                actual,
                unknown,
                transaction[1] if transaction and transaction[0] is self else None,
                target_source
                or (
                    "parsed_and_provided"
                    if inferred and explicit
                    else (
                        "parsed_sql"
                        if inferred
                        else (
                            "provided"
                            if explicit
                            else (
                                "not_applicable"
                                if operation["action"] not in {"read", "write"}
                                else "unresolved"
                            )
                        )
                    )
                ),
                access,
            )
            self._emit(call, "enter", {"status": "started"})
            return call
        except Exception:
            self.bo_errors += 1
            return None

    def _finish(self, call, status="returned", summary=None, error=None):
        if call is None:
            return
        try:
            outputs = {"status": status, "rows_known": False}
            if error is not None:
                outputs["error_type"] = type(error).__name__
            if isinstance(summary, dict):
                rows = summary.get("rows")
                if type(rows) is int and 0 <= rows <= 9007199254740991:
                    outputs.update(rows=rows, rows_known=True)
                if "result" in summary:
                    spec = self.bo_operations[call.scope.node].get("after", {})
                    outputs["result"] = self._selected(summary["result"], spec)
            self._emit(call, "error" if error is not None else "return", outputs)
        except Exception:
            self.bo_errors += 1

    def _summary(self, summarize, result):
        if summarize is None:
            return None
        try:
            with bo_internal():
                return summarize(result)
        except Exception:
            self.bo_errors += 1
            return None

    def execute(
        self,
        node,
        callback,
        *,
        connection=None,
        statement="command",
        language="command",
        targets=(),
        parameters=None,
        summarize=None,
        **context,
    ):
        """Call an official client unchanged and observe selected returned information.

        ``returned`` does not claim a lazy cursor has been consumed or a write has
        committed. Wrap the application's existing materialization if row counts
        are needed; this helper never calls list(), next(), fetch*, or consume().
        """
        call = None
        if self._allowed(connection):
            call = self._begin(
                self._scope(node, parameters, **context), statement, language, targets
            )
        try:
            result = callback()
        except BaseException as error:
            self._finish(call, "failed", error=error)
            raise
        self._finish(call, summary=self._summary(summarize, result) if call else None)
        return result

    async def execute_async(
        self,
        node,
        callback,
        *,
        connection=None,
        statement="command",
        language="command",
        targets=(),
        parameters=None,
        summarize=None,
        **context,
    ):
        """Await one native async operation while preserving cancellation and results."""
        call = None
        if self._allowed(connection):
            call = self._begin(
                self._scope(node, parameters, **context), statement, language, targets
            )
        try:
            result = await callback()
        except BaseException as error:
            self._finish(call, "failed", error=error)
            raise
        self._finish(call, summary=self._summary(summarize, result) if call else None)
        return result

    def transform(
        self, node, function, value, *, before=None, after=None, parameters=None, **context
    ):
        """Record selected values around a real transformation and return its original result."""
        call = (
            self._begin(self._scope(node, parameters, **context), "transform")
            if self._allowed()
            else None
        )
        initial = self._summary(before, value) if call and before else {}
        if call:
            initial = self._selected(initial, self.bo_operations[node].get("before", {}))
        input_count = len(value) if type(value) in (list, tuple, dict) else None
        try:
            result = function(value)
        except BaseException as error:
            if call:
                self._emit(
                    call,
                    "error",
                    {"status": "failed", "before": initial, "error_type": type(error).__name__},
                )
            raise
        if call:
            final = self._summary(after, result) if after else {}
            outputs = {
                "status": "transformed",
                "before": initial,
                "result": self._selected(final, self.bo_operations[node].get("after", {})),
            }
            if input_count is not None:
                outputs["input_count"] = input_count
            if type(result) in (list, tuple, dict):
                outputs["output_count"] = len(result)
            self._emit(call, "change", outputs)
        return result

    def _transaction_object(self, resource):
        """Inspect SQLAlchemy's transaction identity without executing any SQL."""
        try:
            with bo_internal():
                if callable(getattr(resource, "get_transaction", None)):
                    return resource.get_transaction()
                if type(getattr(resource, "is_active", None)) is bool:
                    return resource
        except Exception:
            self.bo_errors += 1
        return None

    def _transaction_active(self, transaction):
        try:
            return transaction is None or transaction.is_active
        except Exception:
            self.bo_errors += 1
            return False

    @contextmanager
    def transaction(self, node, manager, *, parameters=None, connection=None, **context):
        """Observe a transaction manager; emit commit only after its successful exit.

        Pass a real transaction manager such as ``engine.begin()`` or
        ``session.begin()`` which commits on a normal exit. A Neo4j transaction
        or MongoDB session alone does not have that contract: wrap the driver's
        explicit commit/rollback in a project-owned transaction manager first.
        An error during rollback/commit is marked failed;
        successful rollback of a body error is marked rolled_back.
        """
        call = (
            self._begin(self._scope(node, parameters, **context), "transaction")
            if self._allowed(connection)
            else None
        )
        token = _bo_transaction.set((self, call.call_id)) if call else None
        body_error = None
        active_before_exit = True
        try:
            with manager as resource:
                transaction = self._transaction_object(resource)
                try:
                    yield resource
                    active_before_exit = self._transaction_active(transaction)
                except BaseException as error:
                    body_error = error
                    active_before_exit = self._transaction_active(transaction)
                    raise
        except BaseException as error:
            if call:
                rolled_back = error is body_error and active_before_exit
                status = (
                    "rolled_back"
                    if rolled_back
                    else "ended_before_exit" if error is body_error else "failed"
                )
                self._emit(
                    call,
                    "error",
                    {
                        "status": status,
                        **({"committed": False} if rolled_back else {}),
                        "error_type": type(error).__name__,
                    },
                )
            raise
        else:
            if call:
                if not active_before_exit:
                    self._emit(call, "return", {"status": "ended_before_exit"})
                else:
                    self._emit(
                        call,
                        "return" if body_error else "commit",
                        {
                            "status": "rolled_back" if body_error else "committed",
                            "committed": body_error is None,
                        },
                    )
        finally:
            if token is not None:
                _bo_transaction.reset(token)

    @asynccontextmanager
    async def transaction_async(
        self, node, manager, *, parameters=None, connection=None, **context
    ):
        """Async counterpart of transaction(), with identical commit/error semantics."""
        call = (
            self._begin(self._scope(node, parameters, **context), "transaction")
            if self._allowed(connection)
            else None
        )
        token = _bo_transaction.set((self, call.call_id)) if call else None
        body_error = None
        active_before_exit = True
        try:
            async with manager as resource:
                transaction = self._transaction_object(resource)
                try:
                    yield resource
                    active_before_exit = self._transaction_active(transaction)
                except BaseException as error:
                    body_error = error
                    active_before_exit = self._transaction_active(transaction)
                    raise
        except BaseException as error:
            if call:
                rolled_back = error is body_error and active_before_exit
                status = (
                    "rolled_back"
                    if rolled_back
                    else "ended_before_exit" if error is body_error else "failed"
                )
                self._emit(
                    call,
                    "error",
                    {
                        "status": status,
                        **({"committed": False} if rolled_back else {}),
                        "error_type": type(error).__name__,
                    },
                )
            raise
        else:
            if call:
                if not active_before_exit:
                    self._emit(call, "return", {"status": "ended_before_exit"})
                else:
                    self._emit(
                        call,
                        "return" if body_error else "commit",
                        {
                            "status": "rolled_back" if body_error else "committed",
                            "committed": body_error is None,
                        },
                    )
        finally:
            if token is not None:
                _bo_transaction.reset(token)

    def attach_sqlalchemy(self, engine):
        """Install official SQLAlchemy driver events; return a listener removal function.

        Both Engine and AsyncEngine are supported. Only calls inside operation()
        are attributed. Observer connections and metadata/transport scopes are
        excluded. Cursor result streams are never read by these listeners.
        """
        from sqlalchemy import event

        engine = getattr(engine, "sync_engine", engine)
        pending = {}

        def before(connection, cursor, statement, parameters, execution_context, many):
            try:
                scope = _bo_scope.get()
                if scope is None or scope.runtime is not self or not self._allowed(connection):
                    return
                pending[id(execution_context)] = self._begin(
                    scope, statement, "sql", dialect=connection.dialect.name
                )
            except Exception:
                self.bo_errors += 1

        def after(connection, cursor, statement, parameters, execution_context, many):
            try:
                call = pending.pop(id(execution_context), None)
                self._finish(call, "executed", {"rows": cursor.rowcount})
            except Exception:
                self.bo_errors += 1

        def failed(exception_context):
            try:
                call = pending.pop(id(exception_context.execution_context), None)
                self._finish(call, "failed", error=exception_context.original_exception)
            except Exception:
                self.bo_errors += 1

        listeners = [
            ("before_cursor_execute", before),
            ("after_cursor_execute", after),
            ("handle_error", failed),
        ]
        for name, callback in listeners:
            event.listen(engine, name, callback)

        def detach():
            for name, callback in listeners:
                if event.contains(engine, name, callback):
                    event.remove(engine, name, callback)
            pending.clear()

        self.bo_listeners.append(detach)
        return detach

    def pymongo_listener(self, connection=None):
        """Create an official CommandListener for actual MongoDB network commands.

        Pass it to MongoClient(event_listeners=[listener]). Assign
        ``listener.bo_connection = client`` afterwards for exact exclusion. Lazy
        cursors only produce events when the application sends find/getMore.
        """
        from pymongo.monitoring import CommandListener

        runtime = self

        class BOCommands(CommandListener):
            def __init__(self):
                self.bo_connection = connection
                self.bo_pending = {}

            def started(self, event):
                try:
                    scope = _bo_scope.get()
                    if (
                        scope is None
                        or scope.runtime is not runtime
                        or not runtime._allowed(self.bo_connection)
                    ):
                        return
                    collection = event.command.get(event.command_name)
                    if event.command_name == "getMore":
                        collection = event.command.get("collection")
                    targets = ["collection:" + collection] if isinstance(collection, str) else []
                    self.bo_pending[(event.connection_id, event.request_id)] = runtime._begin(
                        scope,
                        event.command_name,
                        "command",
                        targets,
                        target_source="driver" if targets else "unresolved",
                    )
                except Exception:
                    runtime.bo_errors += 1

            def succeeded(self, event):
                try:
                    call = self.bo_pending.pop((event.connection_id, event.request_id), None)
                    # MongoDB may acknowledge a command with ok=1 but include
                    # writeErrors. The driver raises those after commandSucceeded.
                    write_errors = event.reply.get("writeErrors")
                    concern_error = event.reply.get("writeConcernError")
                    if call and (write_errors or concern_error):
                        rows = event.reply.get("n")
                        known = type(rows) is int and rows >= 0
                        runtime._emit(
                            call,
                            "error",
                            {
                                "status": (
                                    "acknowledgement_failed"
                                    if concern_error
                                    else "partial_failure" if known and rows > 0 else "failed"
                                ),
                                "error_type": (
                                    "DatabaseWriteConcernError"
                                    if concern_error
                                    else "DatabaseWriteError"
                                ),
                                "rows_known": known,
                                **({"rows": rows} if known else {}),
                            },
                        )
                    else:
                        runtime._finish(call, "executed", {"rows": event.reply.get("n")})
                except Exception:
                    runtime.bo_errors += 1

            def failed(self, event):
                try:
                    call = self.bo_pending.pop((event.connection_id, event.request_id), None)
                    if call:
                        runtime._emit(
                            call,
                            "error",
                            {"status": "failed", "error_type": "DatabaseCommandError"},
                        )
                except Exception:
                    runtime.bo_errors += 1

        return BOCommands()

    def close(self):
        """Detach listeners owned by this observer without closing application clients."""
        for detach in self.bo_listeners:
            detach()
        self.bo_listeners.clear()
