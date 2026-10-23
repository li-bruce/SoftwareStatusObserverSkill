# Independent Python state graph

The same task uses either normal Python branches or a transitions engine reading the shared declaration. Both retain state structure, actual state queries, source bindings, and complete JSON export.

| File | Purpose |
|---|---|
| app.py | Business logic, without importing observation implementations |
| bo_stategraph/ | Independent state module, model, and source bindings |
| run.py | Composition and example entrypoint |
| build_model.py | Declaration maintenance and local AST parameter extraction |
| test_modes.py | Both modes and observer-isolation checks |

From the repository root:

```bash
python -m pip install -r examples/python-modes/requirements.txt
python examples/python-modes/build_model.py
python examples/python-modes/test_modes.py
python examples/python-modes/run.py --mode observe --out observed-graph.json
python examples/python-modes/run.py --mode drive --out driven-graph.json
```

Output files must not already exist. Both runs follow ready → waiting for capacity → running → completed, with one actual commit. They export the same state declaration and relationships with actual instance evidence; execution mode differs.

The user explicitly chooses drive or observe at adoption. Both maintain the graph, source synchronization, capture, and verification. The AI handles intermediate files.

The independent module and its validators use the standard library; drive mode additionally uses transitions. Optional bo_notify accepts only allowlisted snapshots, and observation failure must not change business outcomes. Missing evidence is not fabricated.

Changing source makes old bindings stale. Update declarations, source links, and independent tests before rebuilding. This small example's hash check is not complete semantic acceptance; integrated projects also use change_sync and whitebox scenarios. Full concurrency, permission, and database cases belong to the other examples.
