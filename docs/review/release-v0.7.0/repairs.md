# Defects found by the independent conversation

The trial runs a separate application built from the installed Skill. These are
public-tool defects, distinct from mistakes in that application's integration.
The trial is a simulated conversation, not a human usability study.

| Finding | Original failure | Repair | Verification |
| --- | --- | --- | --- |
| String SQLAlchemy defaults were exported without SQL literal quoting | `server_default="1"` differed from the real SQLite default `'1'` | Compile literal strings through SQLAlchemy; preserve SQL expressions and support an explicit dialect | [Red test](data-default-red.log), [retest](data-default-green.log); real SQLite, escaped apostrophe, expression and genuine default drift |
| Data whitelists were treated as universally required feature fields | Successful reads required `error_type`; transactions required `rows` | Shared `data/evidence.py` validates configured operations and outcome-dependent presence. Feature coverage uses it only for an exact configured projection with a project root | [Actual trial failure](trial-runtime-coverage-initial.json), [regression](data-coverage-green.log), [ordinary feature checks](ordinary-coverage-green.log) |
| Database projection deleted source enrichment and reordered generated content | `bo_db sync` and source enrichment could each invalidate the other's output | Preserve the source-owned `code_evidence` for an unchanged binding and existing element order; regenerate all database-owned fields | [Actual reproduction](trial-projection-failure.json), [red test](data-source-composition-red.log), [retest](data-source-composition-green.log) |

No business expectations were removed. The data tests explicitly reject missing
selected results, transformation inputs, known row counts, error details and
commit/rollback information. Wrong value types, altered capture contracts and
missing ordinary feature fields still fail. A `managed_by` marker without the
project's database configuration grants no exception.

The stricter data event validator required three old synthetic test fixtures to
include the real event envelope. Their expected successes and counterexamples
remain intact. [The first complete run](data-suite-retest.log) preserves those
fixture failures; [the retest](data-suite-green.log) passed the full database
suite. The initial default regression also passed its comparison arguments in
reverse order; the corrected test compares observed metadata with declarations.

The source and database generators own different fields in the same graph.
Keeping source evidence during a metadata refresh does not validate its hash:
the independent source/mapping gate still recomputes that evidence. Database
checks continue to recompute the catalog and generated database fields.

An example verification also rejected a candidate modified during the checks.
[The failed receipt](team-archive-candidate-change-failure.log) is retained.
Subsequent acceptance must use a frozen candidate, with public-module edits and
installed-copy updates completed before verification starts.

SQLAlchemy's distinction between literal strings and SQL expressions is described
in its [Column documentation](https://docs.sqlalchemy.org/en/20/core/metadata.html#sqlalchemy.schema.Column.params.server_default).

After all three repairs, [the full repository regression](data-fix-full-repository.log)
passed, including both accepted examples, source/graph checks, multilingual
adapters, installation, HTTP operation and executed core exports. Real
[PostgreSQL/MongoDB/Redis/Neo4j metadata](data-fix-live-catalog.json),
[Python operations](data-fix-live-runtime.json), and
[Node.js operations and protocol validation](data-fix-native-protocol.log) also
passed. These are the pre-assessment results for this repair checkpoint; later
changes need their own final acceptance.
