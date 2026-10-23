# Source guide

[中文](source-guide.zh-CN.md) · [Usage](usage.en.md) · [Architecture](refactor-multilanguage.md)

Read this guide when you want to change the Skill, inspect a recorded value, or find the code behind a graph interaction. The maintained implementation lives in [skills/business-observer](../skills/business-observer/). Example projects contain installed copies to test real project integration.

## Repository map

| Location | What to read or change here |
|---|---|
| [SKILL.md](../skills/business-observer/SKILL.md) | The conversation and iteration workflow followed by the coding agent. |
| [scripts/bo.py](../skills/business-observer/scripts/bo.py) | Entry point for serving, validating, inspecting, and exporting a native project. |
| [scripts/bo_stategraph.py](../skills/business-observer/scripts/bo_stategraph.py) | Independent state declaration, observed instances, and complete graph export. |
| [scripts/bo_contracts.py](../skills/business-observer/scripts/bo_contracts.py) | Value types, state hierarchy, active-state calculation, and strict declaration checks. |
| [scripts/execution_contract.py](../skills/business-observer/scripts/execution_contract.py) | Activity, join, resource, and runtime-configuration constraints. |
| [scripts/bo_observer](../skills/business-observer/scripts/bo_observer/) | Shared services, language adapters, development checks, and Web support. |
| [assets/stategraph-viewer](../skills/business-observer/assets/stategraph-viewer/) | The real project's interactive graph, layout, recording, and replay UI. |
| [schemas](../skills/business-observer/scripts/bo_observer/schemas/) | Versioned JSON contracts used at language and service boundaries. |
| [examples](../examples/) | Executable applications with their own business rules and acceptance contracts. |
| [tools](../tools/) and [tests](../tests/) | Installation, managed-copy synchronization, and repository acceptance checks. |
| [docs/site](site/) | The bilingual product page and its separate browser-only sample walkthrough. |
| [docs/review](review/) | Recorded acceptance evidence. Prior records remain unchanged. |

Most Python files directly under scripts are small import/CLI entry points retained for installed projects. Follow their imports into bo_observer to edit the implementation. The independent state module and its two contract files are deliberately kept importable without the observer service.

## Three paths through the implementation

### 1. A coding iteration changes the graph

1. [workflow/bo_sync.py](../skills/business-observer/scripts/bo_observer/workflow/bo_sync.py): source_inventory enumerates the declared project scope independently of existing graph nodes. maintenance_task compares that inventory with the last accepted baseline.
2. [sources.py](../skills/business-observer/scripts/bo_observer/sources.py): scan dispatches Python and JavaScript-family analysis. It caches only matching source/parser versions and retains unresolved calls.
3. [graph/code_structure.py](../skills/business-observer/scripts/bo_observer/graph/code_structure.py): parse_unit extracts Python declarations; enrich combines the authored abstraction with local source nodes.
4. [development.py](../skills/business-observer/scripts/bo_observer/development.py): questions separates business questions for the user from unresolved implementation questions for the coding agent.
5. [workflow/change_sync.py](../skills/business-observer/scripts/bo_observer/workflow/change_sync.py): inspect compares the candidate with its baseline and checks the review. Acceptance requires the exact candidate's successful verification receipt.
6. [workflow/sync_verify.py](../skills/business-observer/scripts/bo_observer/workflow/sync_verify.py): verify runs the configured observations and tests, then reports mapping, state constraints, business assertions, and project checks separately.

An inspection does not advance the accepted baseline. Acceptance is the explicit boundary after all configured checks succeed.

### 2. A program operation appears in the graph

1. The application makes its business decision and calls its native adapter's BOProbe.record with selected values: [Python](../skills/business-observer/scripts/bo_observer/adapters/python/bo_probe.py) or [JavaScript](../skills/business-observer/scripts/bo_observer/adapters/javascript/bo_runtime.mjs).
2. The adapter filters fields, suppresses observation of its own work, and queues delivery. Transport failures are counted separately from the business result.
3. [protocol.py](../skills/business-observer/scripts/bo_observer/protocol.py) checks project/build identity, field types, and envelope limits.
4. [service.py](../skills/business-observer/scripts/bo_observer/service.py): GraphSession.event retains producer identity, ordering, and dependencies. snapshot attaches the application's state to the corresponding event.
5. [bo_stategraph.py](../skills/business-observer/scripts/bo_stategraph.py): bo_observe checks the actual state/revision against the declaration. It records a mismatch as evidence instead of replacing the reported state with an expected state.
6. [observation/recording_session.py](../skills/business-observer/scripts/bo_observer/observation/recording_session.py) saves bounded recording intervals and explicit gaps. view/export serve the declared graph and retained evidence.

In drive mode, the application's native BOExecutor.step also reads the agreed definition. In observe mode, the application implements the decisions itself. Both paths use the same observation contract.

### 3. A click changes the view

| Viewer module | Responsibility |
|---|---|
| [viewer.js](../skills/business-observer/assets/stategraph-viewer/viewer.js) | Connect controls, graph data, live updates, and recording selection. Start here for UI wiring. |
| [graph-core.js](../skills/business-observer/assets/stategraph-viewer/graph-core.js) | Resolve node values, source bindings, event selection, and visible graph content. |
| [layout.js](../skills/business-observer/assets/stategraph-viewer/layout.js) | Expand/collapse regions, position groups, apply filters, and retain annotations. |
| [view-lifecycle.js](../skills/business-observer/assets/stategraph-viewer/view-lifecycle.js) | Keep project view identity stable across builds; compare recording and live graph versions. |
| [renderer.js](../skills/business-observer/assets/stategraph-viewer/renderer.js) | Draw nodes, regions, and edges in Pixi; maintain hit regions for interaction. |
| [recording.js](../skills/business-observer/assets/stategraph-viewer/recording.js) | Construct replay frames and evidence-supported transfers. |
| [runtime-frames.js](../skills/business-observer/assets/stategraph-viewer/runtime-frames.js) | Locate exact snapshots and compare state/resource changes. |
| [replay-steps.js](../skills/business-observer/assets/stategraph-viewer/replay-steps.js) | Choose which recorded changes are meaningful at the current view level. |
| [preferences.js](../skills/business-observer/assets/stategraph-viewer/preferences.js) | Save personal view state through the project preference API. |
| [polling.js](../skills/business-observer/assets/stategraph-viewer/polling.js) | Serialize refresh tasks and control their lifecycle. |

The complete model, the selected view, and the captured evidence are separate values. Filtering a view must preserve the complete model. Moving a node or replaying a step must not execute a business command.

## Comment and formatting conventions

- Describe purpose at public function boundaries; explain ordering, ownership, and failure handling where they are less obvious.
- Use explicit blocks for validation and state changes. Keep each operation readable on its own line.
- Keep public identifiers, protocol fields, graph IDs, and protected expectations stable during readability work.
- Maintain English source comments. Conversation and page copy may follow the user's selected language.
- Edit the canonical runtime first. Use tools/sync_runtime.py to update installed examples; preserve their definitions and personal configuration.
- Leave third-party bundles and frozen acceptance records unchanged.

Pinned development tools are listed in [tools/formatting](../tools/formatting/). They are separate from runtime dependencies:

    python -m pip install -r tools/formatting/requirements.txt
    npm ci --prefix tools/formatting
    python tools/format_source.py
    python tools/format_source.py --check

The formatter selects owned Python modules, viewer JavaScript, native JavaScript adapters, and the product site. It excludes vendored Pixi/ELK bundles, installed example copies, tests, and frozen records.

For a source-readability-only change, compare executable Python syntax with an explicit baseline:

    python tools/check_readability_equivalence.py --base <commit>
    node tools/check_js_readability_equivalence.mjs --base <commit>

The JavaScript comparison uses TypeScript from the native adapter's development dependencies. These comparisons ignore documentation and source positions. They supplement the actual behavior checks:

    python tools/check_package.py
    python tools/verify.py

When a managed runtime changes, rebuild each example's source bindings, inspect its new candidate, run verify, then accept/check before freezing a new record. Earlier accepted records remain available for review.
