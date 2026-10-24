# Focused graphs and sharing

## Extract from the same graph

`focus_graph.py` is a pure extractor independent of browser, database, or coding Skill. Input uses stable graph node/edge IDs. It supports anchors, depth, node/edge budgets, and relation filtering, prioritizing condition/data/resource/join dependencies.

```text
python <skill>/scripts/focus_graph.py --root . --model observer_generated/behavior.json --nodes authorize --depth 1 --max-nodes 12 --out review/permission.json --markdown review/permission.md
```

Retain model revision/content hash, original IDs, source mappings, boundary relations, and gaps. Outside relations preserve endpoints/direction/type; never turn a multi-hop path into a direct relation. Report counts/truncation when budgets are exhausted. Missing source-graph dependencies cannot be recovered. Markdown Mermaid supports conversation; JSON supports other renderers.

For runtime evidence pass an actual JSON event array with `--events`, `--run-id`, and `--build-id`. Do not mix runs or builds. Without a run selection show definitions only. Missing evidence produces gaps, not reevaluated permissions.

Present the relevant graph, concrete examples, and real unresolved questions. Names/layout are personal preferences; changed rule meaning requires requirement/scenario updates. Extraction neither mutates the model nor controls the program. Persistent layout/notes exist; automatic semantic patches, real-time collaboration, and graph-driven business commands are separate future work.

## Export and reproduce

`project_bundle.py` uses explicit file allowlists, not recursive workspace capture. `project` bundles code/reproduction materials; `review` bundles selected views/evidence. Exclude databases/secrets and use synthetic fixtures.

```json
{"schema_version":1,"kind":"project","project_id":"my-project","data_policy":"synthetic-only","versions":{"model":"r1","skill":"0.4.0"},"files":["README.md","app.py","requirements.json","tests.py"],"commands":["python tests.py"]}
```

```text
python <skill>/scripts/project_bundle.py export --root . --config bundle.json --out dist/project-r1.zip
python <skill>/scripts/project_bundle.py inspect --root . --archive dist/project-r1.zip
```

Inspect validates scope, lengths, hashes, and paths without executing commands. `synthetic-only` is the exporter's declaration, not automatic secret detection. Review files/content before export.

Commit source, rules, independent expectations, and tool versions. Rebuild generated graphs from declarations; bind runs to build/data versions. Store personal layout/aliases separately. Share required model, mapping, and test updates together. Resolve requirement/source conflicts before regenerating graphs. Never merge passing receipts from different builds; retain old evidence for historical inspection.
