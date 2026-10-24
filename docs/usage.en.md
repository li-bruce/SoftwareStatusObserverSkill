# Installation and usage

[中文](usage.zh-CN.md) · [Home](../README.md)

## Use it in your project

Install the complete `vibelens` directory, not just `SKILL.md`. In a new conversation inside the target project, invoke `$vibelens` and describe the feature or change.

```text
Use $vibelens to add approval to file exports.
Exports require authorization and content checks. Build a graph from this
description and confirm that it reflects my intent before implementation.
Let me inspect decisions, key parameters and functions in the runtime graph.
```

The Skill first posts a concise business graph directly in the conversation and provides its verified live Web address. You confirm or correct it in the conversation before behavior implementation. It builds that focused graph from your description, then uses necessary clarifications or counterexamples to confirm its interpretation. It does not proactively expand the workflow or recommend business rules. Later additions from you or another Skill update the same graph and its checks. Once that is clear, continue with your project's development approach. The agent maintains state definitions, mappings, probes and checks internally. At the end of each iteration, open the updated graph, expand details, search for key parameters and functions, and request further changes. You do not need to fill in review files or run synchronization commands yourself.

At first use, explicitly choose **drive** or **observe**. Both maintain observation and mapping checks. Business ambiguities come to you; the coding agent resolves implementation bindings against source and tests. See the [Python/Node/React/Vue example](../examples/multilanguage/README.md) and [protocol reference](../skills/vibelens/references/multilanguage.md).

## Read the graph

| Level | Question |
|---|---|
| Business flow | What steps does this operation follow, and why did it stop? |
| Internal state and key code | Which activity is running, what inputs does it use, and what condition is missing? |
| Local code structure and source | Which function owns this step, and where is its implementation? |

The top-level “checking” state is a summary. Each run retains the waiting, running and completion state of every declared activity. Folding nodes only changes presentation. Run identity, parameter version and build version keep records distinct; missing observations are not inferred as success.

Business, function, state, parameter and resource nodes share one canvas, with different shapes and colors. Double-click a node, or select it and click “Expand”. Select “Source” to open code beside it.

Drag nodes to position them, empty group interiors to move the group, and the canvas background to pan. Positions, expansion and camera settings are saved in the project. Runtime updates only change displayed facts. Select “Pin” (shortcut P) to preserve a position during automatic layout. Choose circular grouping, layered or stress layout, click “Arrange”, and undo if needed. Layout preferences do not change application state or authorization.

Select any node and choose “Name and note”, edit its label, note or core marker, then save. Business, function, parameter and state nodes are supported. “Restore original name” restores the generated name while keeping the note. Source identities and runtime facts stay unchanged. Stable node IDs preserve personal labels across regeneration. Folding a parent retains its children's expansion choices.

Preferences live in `bo_stategraph/config/views/local.json`. They survive a server restart, port change or cleared browser cache. Git and core exports exclude this personal file. Conflicting or failed saves are reported; runtime upgrades do not overwrite it. Real-time collaborative editing is not provided.

The initial view shows high-level nodes. Expand for key functions, state and values; “Analysis details” reveals auxiliary code, resources and joins. To replay operations, select all instrumented events or a focused region, start recording, operate the application, then stop. Steps follow the current view and show before/after values. Uncaptured behavior remains unknown.

Search by name, function, parameter or note. Results identify the owning function and input/output type. Selecting a result reveals its parents and centers the node, preserving other expanded regions and positions. A captured parameter's source link opens its owning function.

All active layout and styling components are open source: PixiJS (MIT), ELK.js (EPL-2.0), and original JS/CSS (MIT). No yFiles code is included. See [third-party notices](../THIRD_PARTY_NOTICES.md) and the [ReBAC graph design](../skills/vibelens/references/rebac-graph.md) (the example captures real conditions; general engine integration remains pending).

## Integration maintainers: internal synchronization

These steps are performed by the agent, or used when troubleshooting the integration. They are not routine user tasks. Installing a Skill alone does not monitor every external editor; unchecked edits cannot be marked synchronized.

Version 0.4 adds a required companion track for the selected scope, while leaving the design method, architecture and coding workflow to the project. Modeling, source mapping, application state and runtime verification remain active throughout coding. Define independent expectations and key parameter contracts before implementation; bind real functions and probes while coding; verify each feature before accepting it. Other coding Skills can implement the feature while following these contracts.

Configure `"whitebox": "whitebox.json"` in `sync.json` for new projects. The checker verifies selected source signatures, observed field types/values, field relationships and build identity. See the [example contract](../examples/delivery/whitebox.json) and [workflow reference](../skills/vibelens/references/continuous-development.md).

Use [focus/export commands](../skills/vibelens/references/focus-and-sharing.md) to discuss a local part of the same graph, retain omitted conditions as explicit boundaries, or export a reproducible set of synthetic files. A static conversation diagram is not an interactive application view.

From `examples/delivery`:

```bash
python observer_generated/runtime/change_sync.py begin --root . --change .stategraph/my-change --request "Describe the change"
# Edit business code, relevant probes, tooling/build_graph.py and tests.
python tooling/dev.py graph --reason "Explain the graph or state-definition update"
python observer_generated/runtime/bo_sync.py scan --root .
python tooling/dev.py inspect
```

Review `.stategraph/my-change/impact.json` and create `review.json` beside it. Bind it to the current `candidate_id`; explain updates or retained behavior for business rules, state machine, abstractions and probes. The [change-check reference](../skills/vibelens/references/cochange.md) contains the schema. When changing existing requirements, pass their IDs to `begin --requirements`.

```bash
python tooling/dev.py verify
python tooling/dev.py accept
python tooling/dev.py check
python tooling/dev.py archive --label my-change
```

`verify` executes the program and counterexamples. `accept` accepts only that verified candidate. `check` compares the current inputs before delivery. Later edits to code, graph, rules, tools or tests invalidate the old acceptance. Do not rewrite expected outcomes to hide a bug.

Inventory project-owned source through the Python, JS/TS, React, and Vue adapters and maintain the model's `implementation` contract linking features, supporting functions, parameters and real scenarios. An exclusion sentence cannot replace a feature mapping; missing fields or events fail verification. Existing projects must add the [coverage inventory](../skills/vibelens/references/implementation-coverage.md) after upgrading and continue the existing change. Reports still separate mapping fidelity, state constraints, business expectations and project checks.

Commands in `sync.json` are argument arrays, never shell strings. `{python}` resolves to the current interpreter. First launch restores a fixed, reviewed release baseline; edited code is not automatically approved.

## Separation and runtime modes

Business code uses its neutral interface in `app/ports.py`. Complete state execution, resource constraints and unified queries live in `bo_stategraph/` and remain when observation is disabled. Optional capture and UI wiring use `integrations/bo_*.py` and runtime tools. Observation does not simulate a second business state. See the [module migration guide](../skills/vibelens/references/independent-python.md) for upgrades.

```bash
python tooling/dev.py ownership
python tooling/dev.py core --out dist/delivery-core.zip
```

The core ZIP contains business source, requirements and licenses without the observer implementation or pages. Install its requirements, then run `python main.py`. The neutral interface retains no-op calls. Tests compare results with probes enabled, disabled and failing.

Probes add payload, queue and storage costs; state recording and graph polling also have a cost. `bo_stategraph/config/retention.json` bounds the event cache and rotating logs. Saved recordings and business storage are not deleted with the cache. Incremental APIs and performance baselines remain future work. The 400 ms polling and deliberate delays are not performance measurements.
