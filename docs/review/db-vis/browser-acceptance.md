# Database viewer acceptance

The final post-recovery run is in [final/database-browser-results.json](final/database-browser-results.json),
with its six screenshots in the same directory. It also checks the fixture's
strict capture obligations after both commit and rollback, and per-target
read/write animation is covered by `tools/test_database_view.mjs`.

The browser test runs a disposable Python application with SQLAlchemy and a real SQLite database. It serves the canonical observer viewer and records real queries, application processing, writes, commit, and rollback. The test does not inject fabricated graph events.

## Reproduce

Run from the repository root after installing the normal Python requirements and `skills/business-observer/requirements-database.txt`. The test uses `.venv` by default. Set `BO_PYTHON` to use another interpreter.

Exact PowerShell environment used for the retained screenshots:

```powershell
$env:NODE_PATH='C:/Users/Lvi_P/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules'
$env:BO_BROWSER_EXECUTABLE='C:/Program Files/Google/Chrome/Application/chrome.exe'
node tools/test_database_browser.mjs
```

Versions: Node.js 20.19.6, Python 3.13.13, SQLAlchemy 2.0.55, sqlglot 28.10.1, Playwright 1.62.1, Chrome 155.0.8059.85. The viewport is 1550 × 1040. On another machine, install Playwright and its Chromium browser or set `BO_BROWSER_EXECUTABLE` to an available Chromium executable. `NODE_PATH` above is specific to this machine.

The runner starts its own local server on port 8869 and closes it afterward. `BO_BROWSER_PORT` and `BO_BROWSER_EVIDENCE` override the port and evidence directory. `tools/database_demo.py --port 8868` starts the same disposable fixture for manual inspection. The fixture's `/demo/*` endpoints belong only to this test application.

## Retained evidence

The final result is in [database-browser-results.json](database-browser-results.json); process output is in [database-browser-server.log](database-browser-server.log). The final run passed with no browser console errors or uncaught page errors.

| Evidence | What was checked |
| --- | --- |
| [Structure](database-01-structure-en.png) | Database, table, and field types share the existing graph; native foreign keys produce table references and field mappings; expanded groups preserve their type colors. |
| [Queries and processing](database-02-processing-en.png) | A real SELECT supplies 12 candidates; application processing selects 7; a real INSERT writes the selection. Inline values and the details panel show recorded statement, target source, duration, and counts. |
| [Replay](database-03-replay-en.png) | A captured processing step shows the before/result values and input/output counts. Commit and rollback remain separate transaction outcomes. |
| [Updated graph](database-04-updated-layout-en.png) | An explicit application migration adds `caption`; the fixture updates the SQLAlchemy model, synchronizes, and reloads the observer. The graph build changes, dragged and pinned positions survive, hidden edges/nodes remain hidden, and old recordings are cleared. |
| [Chinese structure view](database-05-structure-zh.png) | Viewer controls, node and relationship types, field metadata labels, and legend use Chinese; source identifiers remain unchanged. |
| [Unavailable metadata](database-06-unavailable-zh.png) | Removing the connection configuration makes a real collection attempt fail. The previous valid graph remains visible with a concise warning. Restoring the connection and collecting again clears the warning. |

The application tests both commit and rollback against the stored rows. An observer-owned query inside an otherwise instrumented scope produces no event. The browser checks recording, replay, view boundaries, schema/source refresh, saved layout, filters, and language switching.

The fixture performs its own migration and session replacement. These browser checks do not establish that every database dialect, arbitrary ORM, or production hot reload works. Native database and watcher acceptance are recorded separately. This viewer uses the metadata and runtime evidence supplied by those adapters.

## Failures and corrections

The earlier failed runs are retained rather than replaced by the passing report:

| Attempt | Failure | Correction |
| --- | --- | --- |
| [1](database-attempt1-expansion-failure.json) | The test assumed repeated “Expand one level” would recursively expand every dataset. | The runner explicitly expands the datasets it inspects. The fixture also returns an empty favicon response to avoid an unrelated console error. |
| [2](database-attempt2-ingestion-failure.json) | The fixture detected rejected events but did not expose the rejection detail. | The fixture now reports the probe and ingestion failures. |
| [3](database-attempt3-dependency-failure.json) | Dependency IDs supplied as strings did not satisfy the event protocol. | The fixture uses typed dependency references; the runtime also normalizes its documented string shorthand. Runtime tests validate emitted event envelopes. |
| [4](database-attempt4-replay-start-failure.json) | The test inspected live values after stopping a recording had opened replay at its initial frame. | The runner explicitly returns to live observation before checking the final runtime values. |

The final review also corrected display semantics: an ended transaction with an unverified outcome stays neutral; partial write and rollback failures are distinct; database metadata and application declarations retain their provenance on relationship captions. Unknown row counts remain unknown. SQL-derived targets, driver-reported targets, and explicit application bindings have different labels.

## Viewer regressions

```powershell
node tools/test_database_view.mjs
node tools/test_recorded_views.mjs
node tools/test_web_colors.mjs
node tools/test_view_continuity.mjs
node tools/test_view_coverage.mjs
node tools/test_refactor_view.mjs
node tools/test_i18n.mjs
```

All passed. These cover exact target evidence, folded graph completeness, filtered boundary edges, role and edge filters, saved preferences, shared legend/renderer glyphs, provenance, outcome labels, recorded changes, and language handling.
