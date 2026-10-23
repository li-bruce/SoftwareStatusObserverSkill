---
name: business-observer
license: MIT
description: Maintain a business and state graph while developing or changing Python, Node.js, React, or Vue software. Link confirmed intent to source, selected parameters, and runtime evidence so developers can debug AI implementations and verify mapping separately from business correctness.
---

# Business Observer

Help developers understand what the AI actually implemented. Business behavior, states, important functions, parameters, and runtime evidence belong to one graph with progressive detail. The user may choose any application architecture, framework, or coding workflow.

Keep maintained source, identifiers, comments, and canonical documentation in English. Respond in the user's language; preserve their original answers as evidence. Localize display labels without changing IDs, protocol keys, state values, source bindings, or assertions. English is the UI fallback; allow an explicit language choice. Do not translate historical evidence in place. See [language policy](references/language-policy.md).

## 1. Confirm intent and development mode

Read the request, project conventions, and existing decisions. Use task, business, and state graphs to express the user's current intent. Clarifying questions and counterexamples resolve actual ambiguity; they do not recommend additional business rules. Do not repeat settled questions or treat silence as confirmation. Read [requirements dialogue](references/requirements-dialogue.md).

At first adoption, explain and ask: **Should the project run from the state declaration (drive), or keep its own logic and use the graph for observation (observe)? Both maintain the graph and monitoring.** Record the user's answer and conversation location. Until answered, continue only mode-independent preparation. Reuse an existing explicit choice; record the source of later changes.

Before behavior implementation, show a compact business-network diagram directly in the conversation, using the same `discovery.json` and stable IDs as Web. Run `bo_design.py preview --root PROJECT --url ACTUAL_GRAPH_URL --out review/design-preview.md`; present its Mermaid diagram in the user's language and a clickable, verified Web URL. State pending choices on the draft. Do not merely say a server started or expect users to find its address. Ask them to confirm the current understanding or correct it in conversation, update the same diagram, and continue once that scope is confirmed. Explicit earlier confirmation of the same graph scope may be reused; never infer confirmation from silence, page viewing, or notes. Highlight the discussion with `bo_design.py focus`. Web has no answer form. See [conversation and graph](references/conversation-web.md).

Route business ownership, permissions, and state meaning to the user. Reconcile parameter bindings, callback targets, types, and capture locations with the coding process. Implementation answers must reference current source and an actual verification case; prose is not runtime evidence. Keep unresolved dynamic targets unknown.

When the requested software stores data, reuse its database choice or run `bo_db.py guide --root PROJECT` to prepare a short selection question. Recommend a database that fits the stated workload, explain the tradeoff, and record the user's choice. Keep confirmed business scope unchanged. See [database observation](references/database-observation.md) for supported stores and model layers.

## 2. Establish declarations, adapters, and expectations

Read [multilanguage architecture and protocols](references/multilanguage.md). Python provides shared graph validation, source aggregation, recording, querying, export, and the complete viewer. The application keeps native execution and authoritative state; both sides exchange versioned JSON.

New projects store a `bo-project/v1` document in `bo_stategraph/project.json`, including the mode decision and complete model. `model.machine` is the state declaration; drive mode binds it to the selected executor. Bind functions through stable source references; do not embed executable function code in JSON. Existing Python projects may retain a v3 graph and a shared `bo_stategraph/machine.json` consumed by their real executor and graph generator. Never edit generated copies independently.

- **drive:** a project-local executor consumes the declaration. Reject unsupported semantics or connect a suitable native engine; never silently omit behavior.
- **observe:** the application's own logic runs. Read its actual state without simulating a second authoritative result.
- **Both:** inventory source independently, retain the state network, capture required parameters, update mappings during development, and verify actual implementation. Business execution must survive the Python observer being unavailable. Hiding the Web UI must not remove the declaration or executor.

Existing complete Python examples retain hierarchy validation, concurrent activities, waiting, resources, joins, and recovery. Native JS/Python `bo.fsm/1` executors support a strict flat subset. Complete instance queries must expose active activities and resources; advanced analysis can remain collapsed. See [independent module](references/independent-python.md), [model contract](references/behavior-model.md), and [integrated execution](references/integrated-execution.md).

Before implementation, define independent expectations for confirmed rules: success, rejection, boundaries, and applicable cancellation, recovery, or concurrency cases. Establish the [implementation inventory](references/implementation-coverage.md), [mapping contract](references/mapping-contract.md), and [whitebox expectations](references/validation-rules.md). Link each scenario to actual functions, parameters, reads, effects, and graph fields. Never copy graph values as independent expected results or weaken earlier checks to obtain a pass.

For data access, configure `bo_stategraph/databases.json`, a native ORM/ODM or explicit data model, its JSON exporter, and `BODataRuntime` wiring in an isolated `bo_` module. Map actual reads, writes, commits/rollbacks, and selected data transformations to source and required cases. Distinguish application model rules, database-enforced structure, and observed samples. The observer reads metadata; the application's migration workflow changes the database.

## 3. Maintain the graph during each coding batch

Connect these commands to the project's AI instructions and verification entrypoint. The AI runs them; the user does not maintain intermediate files:

```text
change_sync begin -> coding and local generation -> bo_sync scan -> change_sync inspect
-> resolve confirmations and implementation review -> change_sync verify -> accept -> check
```

Commands require the project `--root`; `begin` also needs `--change` and the actual request. Continue an active change instead of replacing its baseline to hide drift. See [continuous development](references/continuous-development.md).

`bo_sync scan/watch` discovers new, changed, and deleted files independently of nodes already in the graph. Python, JS/TS, React, and Vue adapters produce common source facts. Missing parsers, syntax errors, and unsupported languages are explicit gaps. Watch produces maintenance tasks; the host or active coding AI must consume them. It cannot wake arbitrary editors or agents by itself.

Configured data projects also refresh their native model exports and database metadata during `bo_sync scan/watch`. `bo.py serve` watches configured data and reloads validated graph builds automatically. The native development launcher must reload its producer with the new build identity; old-build events remain rejected. `bo_db.py check` and `change_sync verify` independently recompute data mappings and require executed cases. A failed collector leaves the previous graph marked stale; never accept it as current.

Read `confirmations.user` and `confirmations.coding`. Ask users only about unresolved business meaning; reconcile unresolved calls and implementation changes within coding. Configure `reconciliation` records when dynamic bindings need protection. Stale source answers, absent targets, and missing verification cases must fail; records do not replace actual value and call checks.

Map all implemented features, including later login, messages, queries, configuration, and frontend actions. Give entrypoints, parameters, helpers, and runtime cases a traceable place in the graph. Collapsing a feature is not excluding it. Static edges are candidates; capture actual calls, decisions, state changes, and effects at their execution boundaries. Do not invent results for conditions skipped by short-circuit evaluation. See [source isolation](references/source-isolation.md) and [semantic probes](references/semantic-pins.md).

Use `bo_` for observation wiring and `BO` for adapter classes; keep domain names for business methods. Select fields explicitly. Never collect credentials, tokens, or arbitrary bodies. Isolate builder, transport, and storage failures; bound queues. Events identify project, model, build, run, producer, entity, call, and parameter version. Arrival order across processes is not causality. Use application/entity scope for features such as login outside a selected task.

Collection, reporting, polling, source viewing, layout, and recording controls must not produce business events. Exclusions need exact source and identity. Split mixed business/observer handlers rather than exempting them wholesale. Preserve real login, message, and state-change capture. See [observer exclusions](references/observer-exclusion.md).

Track source moves explicitly, preserving node identities, parameters, and assertions. Generate from canonical sources and check installed copies. Do not reset capture baselines, fabricate events, or relax expectations to remove failures. Keep personal layouts in `bo_stategraph/config/views/local.json`; upgrades must preserve them. See [source migration](references/cochange.md).

Keep project, node, and relation IDs stable across iterations. Use explicit `presentation.node_aliases` / `edge_aliases` for one-to-one renames; retain dormant personal settings and migration conflicts. Do not derive identity from labels, source line numbers, or build versions. A changed title is not a new project.

## 4. Present and inspect

Reuse the complete `assets/stategraph-viewer/` interaction. After each batch, provide the updated graph and a brief explanation of changes. Start at high-level nodes, then expand important functions, states, and values; reveal advanced details on demand. Any expanded node uses a region with its type's color. Preserve group dragging, saved layouts, typed edges, notes, core markers, search, source navigation, and replay.

Provide one project development command that launches the application and its observer service together and prints both actual URLs. Keep application execution independent if observation is unavailable. The launcher must track and clean up only processes it started. Connect recording/replay to real runtime events; a design-only server has no business recording and must be labeled accordingly. Verify both URLs, build identity, recording start/stop, and replay against a real user operation before delivery.

Every view must preserve meaningful relations. If the other endpoint is hidden, expose an explicit boundary; never invent a direct call or permission. Capture scope and replay granularity are separate. Show actual state/value changes at each step. Distinguish declarations, static derivation, and observed facts; missing or stale evidence is not current truth. See [hierarchical interaction](references/hierarchical-graph.md), [recording](references/recorded-analysis.md), and [local graphs and sharing](references/focus-and-sharing.md).

Respect explicit individual exclusions, including hidden groups and their descendants. “All elements” clears every exclusion while retaining layout and expansion. Folded elements remain represented by their group and counts; cross-group static relations retain their original endpoints. After a code/graph update, show only current-version recordings and leave an obsolete replay. A same-version process restart may retain recordings. Verify this across an actual reload; never reset personal views to make a new graph fit.

Separate a rule definition, relation data, and one evaluation. Do not generalize one example into all ReBAC. Read [authorization patterns](references/authorization-patterns.md), [rule graphs](references/rebac-graph.md), or [types and instances](references/types-rules-capture.md) when relevant.

When requested, hide the debug Web UI with `bo_web.py mode` or use the verified core export. Preserve declarations, native execution, and unified queries. Run the exported core; filenames alone do not prove removal. Personal layouts, credentials, and runtime records are private by default. Upgrades may remove unchanged superseded managed files; report conflicts for user-modified files.

## 5. Verify and deliver

Report **implementation mapping**, **state constraints**, **business rules**, and **project checks** separately. A graph may accurately expose a business bug: mapping can pass while business checks fail. Missing evidence and unrun tests are not passes. Reject invalid declarations, types, projections, engines, or guard wiring before loading. Preserve actual invalid runtime values with diagnostics; never correct observations to fit the model.

Verify that unsynchronized source changes fail; every feature and required field has actual evidence; key values match independent reads; business effects agree with observation on, off, failing, and queue-limited; viewer/recording controls create no business events; filtered views retain relations; export and Web removal preserve business execution. Run architecture checks, existing gates, and new language cases without weakening prior checks.

For configured databases, check a real schema change, actual query targets and selected values, a transformation, commit and applicable rollback/error cases, and observer-query exclusion. Verify source links, data relations, replay, saved layout, and obsolete-recording removal after a build change. Missing drivers or services are unrun checks. Keep mapping results separate from business outcomes and unverified schema details.

Keep failures, fixes, retests, and limitations. Deliver an accessible graph, reproducible commands, and usage guidance. Distinguish scripted dialogue, independent AI trials, and human testing. Open or message another conversation only with user authorization.
