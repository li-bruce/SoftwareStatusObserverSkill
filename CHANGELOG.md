# Changelog

## 0.7.1 — 2026-10-24

- Rename the product and repository to **VibeLens**; use `$vibelens` and `skills/vibelens`.
- Update the English/Chinese introduction, installation commands, CI paths and source guides.
- Add explicit legacy installation migration with a complete backup, failure rollback and existing-file protection.
- Preserve runtime modules, JSON protocol identifiers, layout keys and recorded evidence. Historical source links point to their fixed `v0.7.0` paths.
- [Migration instructions](docs/rename-vibelens.md) and [rename acceptance](docs/review/vibelens-rename/README.md).

## 0.7.0 — 2026-10-24

### Optional code structure

- Add an optional source structure layer to the existing graph: files, classes, functions, parameters, imports, inheritance and individual call occurrences. Reuse the Python, TypeScript/React and Vue parsers.
- Add **Local code** for a selected region and **Code structure** for the indexed source scope. Preserve node identities, layouts, filters and annotations. Show unresolved targets and explicit retrieval boundaries.
- Refresh enabled indexes after source edits, including added/deleted files and syntax failures. Independently verify saved graph contents during iteration acceptance; reject stale or altered exports.
- Keep the current source-only preset out of recorded frames; restore the code perspective when returning to live observation.
- Preserve the selected perspective and cleared discussion focus on reload, including preferences saved before this update. Add this regression to the full check command.
- Keep source browsing and indexing outside business capture. Distinguish static source evidence from runtime observations and their build identities.
- Retain failed attempts and repairs in [code structure acceptance](docs/review/code-vis/README.md), including actual browser recording/replay, source edits, installed examples and cross-language cases.

### Database observation

- Add database structure, native queries, selected data transformations and transaction outcomes to the existing graph. Keep declaration, actual catalog and runtime evidence distinguishable.
- Support SQLAlchemy metadata, MongoDB/Mongoose documents, Redis key patterns and Neo4j relationships, using optional pinned open-source adapters. Refresh catalogs and graph identities when application models change.
- Capture Python and Node operations with explicit data targets and field selection. Exclude observer queries and reporting. Redact unselected SQL literals and distinguish statement success from transaction commit.
- Add bilingual data views, relationship details, selected-value replay and schema-change continuity to the Web viewer. Preserve personal layouts and filters.
- Guide storage selection in the Skill and require model export, capture, source mapping and actual database cases during each relevant development iteration.
- [Acceptance](docs/review/db-vis/README.md): full repository regression, 77 data cases, actual PostgreSQL/MongoDB/Redis/Neo4j collectors and Python/Node clients, real SQLite browser recording/replay, both example upgrades and Git-export installation passed locally. Failed attempts and repairs are retained. The [database branch CI](https://github.com/li-bruce/VibeLens/actions/runs/40013071589) also passed.
- MySQL live verification, database-internal execution plans and automatic column lineage remain outside this delivery.

### Acceptance and architecture repairs

- Repair SQLAlchemy default comparison, outcome-specific data evidence, and source/data enrichment ownership, without relaxing ordinary capture requirements.
- Reject corrupt saved source indexes, include authored state-module files in fallback scans, and bind Python functions declared inside control-flow blocks. Keep ambiguous definitions explicit.
- Isolate HTTP request session lifetimes so slow source work cannot block independent event ingestion or prematurely close an in-use old build.
- Separate live-history expiration from actual capture gaps. Recordings retain streamed interval events after live history expires; the viewer labels expiration separately in both languages, while real skipped producer events still fail completeness checks.
- Add graph-oriented iteration case selection, a component source guide, and a whole-project assessment. Preserve independent mapping, state, business and project reports.
- Exercise a separate application conversation through graph confirmation, implementation, a requested message-read migration, browser recording and public runtime upgrades. Retain original failures, source archives, screenshots and independent SQL-based checks in the [release evidence](docs/review/release-v0.7.0/README.md).

### View continuity

- Preserve project-owned layouts, type and individual filters, expansion, pins, annotations and custom views across graph updates. Support explicit project/node/edge identity migration; retain conflicts and dormant settings.
- Give static calls identities independent of line numbers. Keep repeated calls distinct and preserve their source locations as evidence.
- Add All elements and visible/folded/filtered counts. Keep cross-group static calls when collapsed and include roots omitted by an outdated hint list.
- Restrict the current recording list and replay to the current build/model; leave old replay on update. Same-version restarts retain recordings; private originals remain on disk.
- Synchronize Skill guidance and shipped examples. [Acceptance](docs/review/view-continuity-20261023/README.md) includes browser update/reload evidence, complete regression and staged-byte verification. The [development roadmap](docs/development/dev-roadmap.md) records completed source/data extensions and remaining API work.

## 0.6.0 — 2026-10-23

[Release notes](docs/releases/v0.6.0.md) · [Live introduction](https://li-bruce.github.io/VibeLens/)

### English presentation and independent gallery trials

- Publish the bilingual introduction through GitHub Pages. Preserve exact runtime-copy bytes across clean checkouts; validate historical references by transcript hash and archived members instead of local absolute paths. Add six portability regression cases.
- Refresh the multilingual example's Vue/Vite lockfile and rerun its 18 native cases; npm reports no known advisories for the updated example at publication.
- Fix nonblocking JavaScript parser input, a clean-clone regression fixture, and archive source byte consistency. Preserve failure/repair/retest records in the [publication review](docs/review/github-publication-v0.6.0/README.md).
- Add an illustrated bilingual product introduction with interactive graph layers, mixed views, drive/observe diagrams, iteration checks, and an explicitly illustrative replay.
- Require a conversation diagram and verified Web graph address before implementing confirmed scope. Generate both from the same discovery model; keep confirmation in conversation.
- Maintain English source, instructions, and default documentation; preserve original historical evidence and user labels. Persist the viewer's English/Chinese preference in project configuration.
- Fix portable upgrade metadata, chained-call source IDs, native project design views, optional state labels, and business-state versus activity-state replay wording.
- Retain strict mapping, business, state, and project checks. Record independent Python and Node gallery failures, repairs, and retests in the review materials.

### Multilanguage architecture

- Separate shared graph, workflow, observation, web, delivery and language adapters under `bo_observer`. Keep thin compatibility entrypoints; retire obsolete viewers and v1 schemas with safe managed-file migration.
- Add versioned project/source/event/snapshot JSON protocols, strict engine and value checks, bounded native transport, one authoritative producer per observed instance, and isolated Python collection.
- Inventory Python, JS/TS, React and Vue independently of existing graph nodes. Check native imports and DOM handlers; retain explicitly hashed historical sources and third-party bundles as evidence/dependencies.
- Ask the user to choose drive or observe at initial discovery. Route business confirmation to the user and implementation questions to coding-side evidence.
- Migrate the existing Python examples to JSON execution definitions and add actual frontend coverage. Add a native Python/Node and real React/Vue component example, keeping all existing gates.

## 2026-10-23 (main)

- Exclude graph polling, source/preferences/recording controls and observer reporting from business nodes and events. Retain their source inventory, validate exact observer-route exclusions, and suppress recursive collection in payload builders, sinks and recording snapshots.
- Add a reviewed migration for unchanged observer routes previously classified as business features, preserving business capture and assertion protections. Verify the independent upload-review application with repeated observer requests and real login/upload/review/message actions in on/off/fault modes.
- Require a source-first implementation inventory linking features, functions, parameters, graph nodes and actual observation cases. Reject omitted routes, business-source exclusions, missing fields and weakened coverage obligations.
- Preserve business actions in function views, business parameters on expansion, authored state identities and real relation endpoints at filter boundaries. Apply the same relation classification in selection and rendering.
- Support explicitly scoped application/entity events so login and configuration activity remains visible alongside a selected task.
- Migrate both runnable examples, adding previously absent command observations while retaining existing business, state, mapping and observer-removal checks.

## 2026-10-22 (main)

- Limit discovery to confirming the user's current intent. Retain clarifications and counterexamples that resolve actual ambiguity, without recommending additional business rules or workflows.
- Align the Skill, agent prompt, permission guidance and bilingual usage instructions with this boundary. Source mapping, runtime observation and acceptance checks remain required.
- Preserve an independent project-flow trial with actual simulated dialogue, failed checks, fixes, screenshots and runnable source packages. Its cross-type derivation iteration keeps prior node identities and assertions; the final 33 scenarios run in three observation modes.
- Point installation instructions to `main` so new installations include the latest changes rather than the older `v0.5.0` tag.

## 0.5.0

- Move complete example lifecycle, activity, resource, scheduling, cancellation and recovery coordination into `bo_stategraph`; retain old paths as delegates and compare old/new actual behavior.
- Share graph, type, hierarchy and activity validation. Use one authoritative instance query for Python, the viewer, recording and export. Preserve actual invalid facts with diagnostics.
- Discover source changes independently of existing graph nodes, maintain internal tasks and reject missing classifications, probes, assertions and implementation witnesses. Verify the public runtime export protocol.
- Support explicitly reviewed one-to-one function moves while preserving authored graph IDs, required probes and whitebox assertions; relocating source is not a business-rule change.
- Separate mapping fidelity, state/resource constraints, authored business expectations and project test reports.
- Persist personal layouts, labels, notes and view filters in the project with atomic writes and revision conflicts. Bound event caches and rotating logs; record directly from event intake.
- Add versioned runtime upgrades, conflict refusal and rollback. Separate drawing/object lifetime, preferences and polling from page coordination; show direct nodes first with advanced details on demand.
- Support exact event-bound transaction snapshots for ordinary Python state and shared-resource replay. Missing snapshots remain unknown; history is never filled from the final state.
- Normalize live release sources before fingerprinting and preserve frozen evidence bytes across Git checkouts.
- Shorten the Skill, align its integration instructions with code, and require reuse of the public query/export and full graph components. Review materials retain independent simulated dialogue, defects and subsequent fixes.
- Incremental event APIs, production performance baselines, general Petri analysis, universal ReBAC engines and graph-driven business commands remain out of scope.

## 0.4.0

- Add an independent team-archive project built through actual simulated clarification rounds, implementation, debugging and a dynamic size-limit iteration. Preserve preimplementation expectations, both graph versions, failures, final screenshots and reproducible review records.
- Verify its final 40 scenarios in three observation modes, 11 whitebox assertions, 13 Python tests, graph history and persistence, targeted mutations, and extracted core execution. Clarify that this is an agent simulation using synthetic data.

- Make observation a required companion track to any chosen development workflow: discuss the graph first, maintain it within the agent's work, then show changes and runtime results without requiring users to manage intermediate files.
- Search collapsed functions, parameters, custom names and notes; reveal the selected node without resetting saved positions or other expanded regions.
- Keep later reevaluations and final run fields out of historical frames. Link parameter nodes to their captured function's source.
- Combine split input/return values only when explicit call, execution, object and build identities match; preserve unknown values when identity is insufficient.
- Add source-bound whitebox plans and runtime assertions for types, values, field relationships, actual decisions and evidence identity; integrate them with change_sync and protect prior expectations.
- Capture individual grant conditions once, retain short-circuit behavior and correlate grant/authorization calls.
- Extract deterministic local graph views with original IDs, typed boundaries, source mappings, budgets and version-filtered runtime evidence; export JSON and Mermaid Markdown.
- Export explicit synthetic project/review files with portable manifests and integrity checks; never execute imported commands.
- Add isolated semantic mutations, missing/stale evidence, graph-boundary and bundle-tampering tests. Formal whole-program verification and automatic semantic graph editing remain outside this release.
- Add a source-backed ReBAC pattern guide covering direct access, groups, roles, inheritance, set operations, tenant scope, context, revocation and consistency, without prescribing one example's permission rules.

## 0.3.0

- Persistent display names and notes for every node type, with original names and source identities retained.
- Restore selected nodes and nested expansion; preserve older saved layouts and personal labels across regeneration.
- Open-source viewer dependency audit, retained licenses and checks for reviewed bundles.
- ReBAC graph design covering rule expressions, relation evidence, evaluation states, freshness and alternative authorization. This is design guidance, not a new authorization engine.

## 0.2.0

- One typed node-link graph for business steps, functions, parameters, resources and lifecycle states.
- Node dragging, exact pins, saved positions/expansion/camera, incremental expansion and layout undo.
- Local ELK.js 0.12.0 layered and stress layouts in a Web Worker.
- Activity-only history frames no longer borrow the run's final lifecycle state.
- Tests run both real layout algorithms and check persistence, pins, gestures and history boundaries.

## 0.1.0

First public release / 首次公开发布。

- Developer-facing business, internal-state and code graph with inline details.
- Requirement clarification with recorded answers and unresolved-question checks.
- Python AST slices, source bindings, runtime probes and code/graph change checks.
- Concurrent activities, capacity waits and all-join rules in the application's state machine.
- Synthetic delivery example, live PixiJS graph, scenario replay and core-only packaging.
- Bilingual installation and usage guides, pinned Python dependencies and MIT license.
- Portable Python command resolution and deterministic generated-file line endings.
- Stable source fingerprints across Python 3.11–3.13 AST schemas.
- Fix for a stale HTTP state snapshot paired with a completed operation flag.

Reproduce validation with `python tools/verify.py`: 5 AST compatibility tests, 22 clarification tests,
13 clarification workflow steps, 30 business/activity tests, 16 scenarios in
3 observation modes, 14 graph assertions, installation/HTTP checks and execution
of the observer-free core package. These are automated checks, not human usability
evidence or a proof of all application behavior.
