# Database observation example

This branch connects database structure and actual operations to the existing
developer graph. The Python observer manages metadata and views; native Python
or Node.js code executes the application.

## Try the graph

From the repository root, with Python 3.11+:

```bash
python -m pip install -r skills/vibelens/requirements.txt -r skills/vibelens/requirements-database.txt
python tools/database_demo.py --port 8868
```

Open [the graph](http://127.0.0.1:8868/graph). The fixture uses a disposable SQLite
database. Select **Queries and data processing**, start recording, and execute the synthetic
application action in another terminal:

```bash
curl -X POST http://127.0.0.1:8868/demo/run -H "Content-Type: application/json" -d "{}"
```

On Windows PowerShell:

```powershell
Invoke-RestMethod http://127.0.0.1:8868/demo/run -Method Post -ContentType application/json -Body '{}'
```

Stop recording and replay the selected values: 12 candidates, 7 selected images,
and 7 committed rows. Submit `{"rollback":true}` to exercise a rolled-back write.
After both operations, the fixture runs the same data-mapping checks as a project
integration. Its response reports `mapping_status: passed`; before both cases
have executed, the status is `pending`.
`POST /demo/upgrade` applies the fixture's migration, updates its model source,
and reloads the graph. Personal settings remain; old-build recordings leave the list.
These three `/demo/` routes belong to the test application only. The shipped
observer service exposes no business execution route.

`--root .validation/my-database-demo` retains generated example files for inspection.
The fixture must receive a fresh directory. See its readable implementation in
[database_demo.py](../../tools/database_demo.py).

## Run the checks

The pinned native-client acceptance suite requires Node.js 20.19+.
Install the Python dependencies above before running these commands.

```bash
python tools/verify_databases.py
docker compose -f examples/database-observer/compose.yaml up -d --wait
npm ci --prefix tools/database-native
python tools/verify_databases.py --live --native
docker compose -f examples/database-observer/compose.yaml down
```

Live checks require PostgreSQL, MongoDB, Redis, and Neo4j. They fail when a server
is missing. The Compose file binds only local ports and uses synthetic test credentials.
Tests remove only their own named resources. SQLite checks need no Docker.
For alternative isolated test services, set `BO_TEST_POSTGRES_URL`,
`BO_TEST_MONGODB_URL`, `BO_TEST_REDIS_URL`, and `BO_TEST_NEO4J_URL`. Catalog,
Python runtime and Node runtime checks use the same four settings. PostgreSQL
accepts the SQLAlchemy `postgresql+pg8000://` URL; the Node runner translates
the scheme for its native driver.

The browser check uses Playwright and Chromium:

```bash
python tools/verify_databases.py --browser
```

Install Playwright in the Node environment used by the test. `NODE_PATH` can point
to an existing installation; `BO_BROWSER_EXECUTABLE` can select an installed Chrome.
`BO_BROWSER_EVIDENCE` chooses a new screenshot/report directory. The test launches
and stops its own disposable application.

For an application integration, follow [database observation](../../skills/vibelens/references/database-observation.md).
Recorded failures, fixes and screenshots are in [the review](../../docs/review/db-vis/README.md).
