# Changelog

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
