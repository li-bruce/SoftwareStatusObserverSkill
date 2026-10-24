# One graph from conversation to execution

Users discuss, confirm, and revise in Codex or another development tool. Web provides graph viewing, dragging, expansion, filtering, notes, and debugging. It has no answer form, business-confirmation endpoint, or rule-editing API.

## Start the discussion

Create `discovery.json` using [intent confirmation](requirements-dialogue.md). Uncertain rules stay open with user/inference/project-rule sources. Run `requirements_dialogue.py validate`; `check` still rejects unresolved blocking questions. Opening a graph is not a reason to mark a question resolved.

Design nodes use stable IDs. `model_nodes` may reference existing or reserved implementation IDs: the first is the primary design projection ID; others support discussion focus. `parent` references the same design; missing parents/cycles fail. State/resource nodes retain their types. This stage has no runtime instances or actual values: do not fabricate events or load a sketch as a valid executable machine.

Set project_id, a short title, and stable layout_id; the runtime service must reuse layout_id. Carry primary IDs into the implementation graph. Do not silently merge multiple nodes under one ID; use shared relations for multiple membership. Layout and notes live in `bo_stategraph/config/views/local.json`.

```bash
python <skill>/scripts/bo_web.py serve --root <project> --port 8830
python <skill>/scripts/bo_design.py focus --root <project> --decision D1 --label "Confirm whether download waits for preview"
```

Open `http://127.0.0.1:8830/graph` in the development tool's browser. The page highlights current nodes/edges/regions directly, with no discussion bar. Users can click empty canvas or press Escape to dismiss focus and inspect the full graph. Dismissal survives reloads. Keep the metadata label within 120 characters. Use `--nodes node_a node_b` for node focus or `focus --nodes` to clear it.

Always present the first graph in the conversation as well. After checking the actual Web URL, run `bo_design.py preview --root <project> --url http://127.0.0.1:8830/graph --out review/design-preview.md`. This extracts Mermaid and matching JSON from the same design projection, preserving IDs, relations, scope, and unanswered questions. Embed the diagram in the reply, include the clickable URL, and ask whether the current understanding is right. Use the user's language without changing graph identities. If corrected, update discovery and regenerate both views. Proceed with behavior implementation after confirmation of that scope; an existing explicit confirmation may be reused. Do not turn page opening, silence, or a saved screenshot into approval. A failed Web launch must be disclosed; the inline draft remains useful but is not evidence that Web works.

After an answer, AI updates requirements, decisions, graph, scenarios, and focus. Web reloads the projection. The API marks stale focus; the viewer clears its highlights silently. Focus changes presentation only, never answers or check outcomes. Existing history/mapping gates remain active.

## Continue into implementation

Reuse assets through `BOWeb(root, assets=project_graph_assets)`:

- Check `allowed(path)` before GET; disabled routes return 404 with `code: bo_web_disabled`. `get('/api/design')` reads focus configuration only. No design-answer POST exists.
- Mark graph links in application HTML with `data-bo-entry`; process with `entry_html`. Business state/operation endpoints remain independent and work with Web disabled.
- Before generic HTTP capture, call `is_observer_request(path)` and skip graph pages/assets/APIs. Do not map unknown requests to a fake developer-graph business event. See [observer exclusion](observer-exclusion.md).

Keep integration in `integrations/`, not imported by business methods. Replace sketch data with the actual runtime view, retaining IDs and adding source/parameter/state/event bindings. AI may keep updating discussion focus during execution. Verify stable IDs, layout identity, and unmapped nodes; opening a page does not prove mapping. Core/engine/declaration/parameter validation stays strict and the full gate reports mapping, state rules, business, and project checks.

## Control Web at delivery

```bash
python <skill>/scripts/bo_web.py mode hidden --root <project>
python <skill>/scripts/bo_web.py mode disabled --root <project>
python <skill>/scripts/bo_web.py mode visible --root <project>
python <skill>/scripts/bo_web.py status --root <project>
```

| Mode | Behavior |
|---|---|
| visible | Application link and graph/debug APIs available |
| hidden | Link disappears after application refresh; known graph URL still works. Not access control. |
| disabled | Graph/assets/source/recording/preferences/export HTTP routes close; open viewers stop displaying. Restore visible to resume. |

Persisted `bo_stategraph/config/web.json` does not change executor, capture mode, Python queries, structural export, or personal layout. The business service remains running. Invalid configuration errors instead of enabling Web. Stop recording/capture separately; closing Web is not disabling capture.

For a package without debug Web or capture implementation, first pass the project gate:

```bash
python <skill>/scripts/bo_web.py package --root <project> --out dist/core.zip
```

This delegates to `architecture_guard.py package`, requiring valid ownership.json and a new ZIP path. Preserve the business state machine/neutral interface; an explicit core allowlist excludes viewer, capture, integration service, and personal settings. Extract and run business tests; a ZIP filename proves nothing. Keep the original development project. Do not remove debug by bulk directory deletion or editing business functions.
