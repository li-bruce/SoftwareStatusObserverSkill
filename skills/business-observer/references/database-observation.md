# Database observation

Use this reference when a project stores data. The graph keeps declared models,
database metadata, executed operations, and application transformations together.
Their evidence sources remain distinct.

## Establish the storage choice

Preserve an existing database and model layer. For a new project, ask one short
question about storage needs and offer a relevant default: SQLite with SQLAlchemy
for a small local Python application; PostgreSQL for a shared relational service;
MongoDB with an ODM for document storage; Neo4j when relationship traversal is
central; Redis for explicitly chosen key/value or cache operations. Explain the
choice in the user's language. Record the user's answer in the store `selection`.
Avoid adding databases or application features that the user has not requested.

The coding agent configures the model layer, native declaration export, database
collector, and operation probes. These are normal development tasks, rather than
extra modeling work for the user. Confirm the meaning of ambiguous business data
with the user; resolve driver and source bindings with the coding agent.

## Reused tools and current boundaries

| Storage | Collector | Evidence and limits |
| --- | --- | --- |
| SQLite, PostgreSQL, MySQL through SQLAlchemy | `Inspector` and optional native `MetaData` export | Tables, native field types, nullability, server defaults, primary/foreign keys, unique/check constraints and indexes in the configured schema. Dialect support varies. Views, triggers and stored routines remain outside this catalog. SQLite collection opens an existing file in read-only mode. |
| MongoDB through PyMongo | `listCollections` and `list_indexes` | Validator field paths, nested objects/arrays, validation settings and index metadata. Indexed paths without a validator have an unknown type. Existing documents are never sampled. The catalog is partial. |
| Redis through redis-py | Configured key patterns; optional `SCAN` plus `TYPE` | Sampling defaults to off. With opt-in, at most `sample_limit` type checks and `scan_limit` scans per pattern. No values or raw key identities are exported. Samples do not prove all key types. |
| Neo4j through its official driver | Labels, relationship types, `SHOW CONSTRAINTS`, `SHOW INDEXES` | Declared/indexed properties and native constraints. No unbounded property scan and no inferred label-to-label connections. The catalog is partial. |

These APIs provide maintained metadata interfaces. A generic table
diagram tool cannot replace the storage-specific information they expose.
[SQLAlchemy reflection](https://docs.sqlalchemy.org/en/20/core/reflection.html),
[MongoDB collection metadata](https://www.mongodb.com/docs/manual/reference/command/listcollections/),
[Redis SCAN](https://redis.io/docs/latest/commands/scan/), and
[Neo4j procedures](https://neo4j.com/docs/operations-manual/current/procedures/built-in-procedures/)
document the relevant boundaries. Redis `COUNT` is a hint, not a strict bound on
the server response. Neo4j schema visualization statistics are not used to
invent actual connections.

The real-server collector acceptance covers PostgreSQL, MongoDB, Redis and Neo4j;
SQLite also has real-file regression tests. MySQL uses the SQLAlchemy dialect
interface but is not covered by that acceptance run. Cassandra, Elasticsearch,
DynamoDB and other database families still require dedicated adapters. A shared
JSON format does not imply that every database already has an implementation.

## Declarations and database enforcement

Catalogs use `bo-data-catalog/v1`, with `origin: declaration|database`, coverage,
and explicit limitations. Native declarations use stable resource keys, such as
`table:images`, `collection:images`, `key_pattern:session:*`, or `label:Image`.

`validation_scope` defaults to `database`. These declarations express expected
database fields and constraints and are checked against actual metadata.
`validation_scope: application` is reserved for declarations such as Mongoose
ODM validation and references. They describe application behavior; the graph
must not present them as MongoDB-enforced validators or foreign keys. Source
freshness, configured operation coverage and runtime checks still apply.

Declared database constraints are compared by their fields and rules, rather
than automatically generated names. Default and check expressions are compared
conservatively as native text. A mismatch may need a reviewed dialect-specific
mapping; arbitrary SQL-expression equivalence is not claimed. Unknown types or
uninspected properties remain explicitly unverified.

## Development and runtime

Store configuration belongs in `bo_stategraph/databases.json`. Connection URLs
come from named environment variables. Native exporters write catalog JSON to
stdout; the synchronizer validates it before publishing generated files.

Exporters execute project code. Keep their entrypoints offline and limited to
registered metadata: SQLAlchemy `MetaData` without `create_all`, Mongoose schemas
without database connection or initialization, and equivalent native model APIs.
The observer does not make an arbitrary exporter command read-only. Include
exporter modules in the store's `source_files` and review import-time effects.

After model/source changes, the synchronizer reruns configured exporters and
recollects database metadata. It updates only its managed graph nodes and edges.
Unchanged resource IDs and personal view files remain stable. A table or field
rename receives a new ID. A reviewed one-to-one `presentation.node_aliases` or
`edge_aliases` entry can preserve existing view settings; the collector does not
infer these aliases from similar names.
Name similarity alone is not evidence of identity.
Failed collection leaves the last good files in place and reports stale evidence.
An independent check recomputes facts without repairing them.

At runtime, use the existing `BOProbe` event protocol. SQLAlchemy execution hooks
and PyMongo command listeners feed configured operation scopes. Other native
operations use the explicit data-operation wrapper. Application transformation
helpers record selected before/after values, not a second execution of the
business function. Transaction completion remains separate from query return.
No collector drains a result cursor to obtain a display count.

Metadata queries run inside `bo_internal()`. Observer-owned connections can also
be registered for exclusion. These explicit markers suppress collection,
transport and graph maintenance operations without guessing from SQL text or
business names. Review required runtime cases, actual targets, failures,
transaction outcomes and selected data transformations at each coding checkpoint.

The Web data watcher refreshes valid schema/source changes, replaces the loaded
build, preserves personal preferences, and excludes older build events and
recordings from the current view. Failed refreshes keep the previous session
with a visible failure report. Application producers must use the new collector
build settings before sending further events.

## Commands and capture requirements

Install the optional `requirements-database.txt`, then use:

```text
bo_db.py guide --root PROJECT
bo_db.py sync --root PROJECT
bo_db.py check --root PROJECT
bo.py serve --root PROJECT --port 8830
```

The standalone `bo_db.py watch` is useful when another launcher hosts the graph.
`bo.py serve` already watches configured data projects. `bo_sync scan/watch` also
refreshes data mappings, while the normal `change_sync verify` gate independently
checks current metadata, selected values and required runtime cases. A metadata
refresh does not accept a coding batch.

Each configured operation supplies `source`, `store`, `action`, `targets`, selected
`parameters`, `before`, `after`, and `required_cases`. Those cases require successful
runtime evidence by default. List an expected failing case in `failure_cases` as
well as `required_cases`; a failure cannot stand in for successful capture. A
transaction case needs a real commit acknowledgement. Keep independent expected
values in the existing whitebox/mapping contracts.

For a query that reads one resource and writes another, declare each resource's
role in `target_actions`. Multi-target writes require this mapping; a
`read_write` target creates both directions in the graph. For example:

```json
{
  "action": "write",
  "targets": ["table:images", "table:archive"],
  "target_actions": {"table:images": "read", "table:archive": "write"}
}
```

This models `INSERT INTO archive SELECT ... FROM images` as a read from images
and a write to archive. Python SQL observations additionally report
`target_access` entries from explicit table references and INSERT/UPDATE/DELETE
destinations. Runtime checks reject reversed or undeclared roles. A table that
appears in both roles requires `read_write`; implicit reads inside UPDATE are
not a claim of column lineage. Unresolved destination aliases and unsupported
statement families remain unverified and fail the required mapping case.
Generic native wrappers retain their supplied target bindings and declared
roles; they do not claim to infer access roles from SQL or Cypher text.

Use `requirements` on each operation to link its obligations to confirmed
requirement IDs. Removing an operation, required case or captured field, or
changing an existing success case to failure requires the existing recorded
requirement-change review. Adding the data feature does not weaken older gates.

`target_source` distinguishes targets derived from parsed SQL, native driver
commands, and explicit application bindings. Generic Redis/Neo4j/Node wrappers
use the supplied binding; this is not proof that arbitrary query text was fully
analyzed. Python SQL uses SQLGlot for literal removal and table references;
Cypher uses Pygments for redaction only. Node SQL/Cypher text is withheld by default.
Selected summaries are collected after the application consumes the result.
Unknown row counts stay unknown. Database-internal query plans and automatic
column lineage are not captured by this version.

Python uses `BODataRuntime.attach_sqlalchemy(engine)` with an operation scope,
`pymongo_listener()` registered before client creation, or `execute`/`execute_async`
around a real native call. `transform` records selected before/after values from
the actual function invocation. A transaction wrapper must receive a manager
that commits on normal exit, such as `engine.begin()`; a raw Neo4j transaction
context only closes and is not interchangeable. Native Node examples use
`executeAsync`, `transform`, and explicit transaction begin/commit/rollback callbacks.
See the real [database example](../../../examples/database-observer/README.md).
