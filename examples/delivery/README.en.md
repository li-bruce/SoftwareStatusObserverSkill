# Reviewed delivery example

[中文](README.md) · [Project home](../../README.en.md)

This program turns synthetic text into a delivery artifact. Its graph lets developers inspect authorization, checks, concurrent waits and committed effects.

Install `examples/delivery/requirements.txt`, then run from the repository root:

```bash
python tools/demo.py
```

Open the [graph](http://127.0.0.1:8797/) and [control page](http://127.0.0.1:8797/control). Use `--port 8801` if needed; stop with Ctrl+C. Local data is stored at `scratch/live.sqlite` inside this example.

## Follow a real run

1. Enter public sample text, set capacity to 1, then click **保存内容和名额** (save content and capacity).
2. Click **批准当前版本** (approve current version), then **检查并提交** (check and submit).
3. Expand **检查内容** (check content) in the graph. One activity occupies the slot while the other waits; both must pass before submission.
4. Use **时刻** (moment) to revisit the wait. Double-click a function to expand parameters and calls; select a node and click **源码** (source) to inspect implementation.

Business, function and state nodes share one graph. Drag nodes to move them; positions are saved in this browser. Pin selected nodes to preserve their position during automatic layout. Choose layered or stress layout, then click **自动布局**. Double-click to expand, drag the background to pan, and use the wheel to zoom.

Capacity 2 allows both activities to run simultaneously. Each activity state belongs to a specific run; **运行** (run) preserves records from older parameter versions.

## Try these cases

| Action | Expected behavior |
|---|---|
| Save new text and execute without new approval | The old approval cannot authorize this version; execution waits |
| Approve G1 and G2, then revoke G1 | A valid G2 still permits execution |
| Check only, revoke the sole approval, then submit | Commit rechecks authorization and waits |
| Add approval and execute again | Recheck and commit using current authorization |
| Include `SECRET:` in the text | The synthetic content check rejects delivery |
| Submit the same version repeatedly | SQLite contains only one artifact for that version |

`SECRET:` is a test rule, not a real data-security scanner. Tests advance an explicit integer clock; this is not a production expiry-time implementation.

## Replay reproducible scenarios

From this example directory:

```bash
python tooling/dev.py archive --label sample
```

Refresh the graph, choose `sample` under **版本** (version), then select a scenario. The archive executes the real program and retains source, events and internal states. It stays separate from the live session.

## Source map

- `app/workflow.py`: state types, concurrent activities, capacity and join conditions.
- `app/service.py`: inputs, authorization, checks and commit.
- `app/store.py`: run records and committed SQLite effects.
- `tooling/build_graph.py`: business grouping plus static local code relationships.
- `integrations/bo_view/`: editable graph UI sources.
- `observer_generated/`: generated output; edit sources and regenerate.

See the [usage guide](../../docs/usage.en.md) for the change workflow. The graph is read-only; the control page invokes real business commands. Capacity is per run. Restarting preserves the last state and marks unfinished runs as interrupted; it does not restore worker threads.
