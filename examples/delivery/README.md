# Reviewed delivery example

[中文](README.zh-CN.md) · [Project home](../../README.md)

Turn synthetic text into a delivery artifact while inspecting authorization, checks, concurrent waiting, and committed effects.

From the repository root, install the [dependencies](../../README.md#run-locally), then run:

```bash
python tools/demo.py
```

Open the [graph](http://127.0.0.1:8797/) and [control page](http://127.0.0.1:8797/control). Use --port to select another port. Ctrl+C stops the server.

## Follow an operation

1. Save public sample text with capacity 1.
2. Approve the current version, then choose **Check and commit**.
3. Expand **Check content**. One check occupies the slot while the other waits.
4. In the graph, start recording before operating the application, then stop and replay. Inspect the actual state/value changes and corresponding source.

With capacity 2, both checks may overlap. Each run retains its own activity and resource state. Drag regions, pin nodes, use automatic layout, and add display names or notes. Preferences persist in the project at bo_stategraph/config/views/local.json, independently of the browser port.

| Action | Expected behavior |
|---|---|
| Edit text and execute without new approval | Old approval cannot authorize the new version. |
| Approve G1 and G2, then revoke G1 | Reevaluation may use valid G2. |
| Check only, revoke the sole approval, then commit | Commit rechecks authorization and waits. |
| Restore approval and execute again | Recheck using current authorization. |
| Include SECRET: in the text | The synthetic marker check rejects delivery. |
| Submit the same version repeatedly or concurrently | SQLite retains one artifact for that version. |

SECRET: is a synthetic test rule, not a data-security scanner. The explicit integer clock is for deterministic expiry tests.

## Source and verification

- app/: business functions, authoritative storage, and neutral observation ports.
- bo_stategraph/: executable machine declaration, activities/resources, and unified queries.
- tooling/build_graph.py: confirmed business grouping and source-based enrichment.
- integrations/: optional capture and control/view wiring.
- observer_generated/: generated graph, viewer, and managed runtime copies.

```bash
python tools/verify.py
```

The graph is read-only. Use the control page for actual business commands. Restart marks unfinished persisted runs as interrupted; it does not revive lost worker threads. Historical acceptance snapshots remain original evidence.

See [usage](../../docs/usage.en.md) for the required change/verification workflow.
