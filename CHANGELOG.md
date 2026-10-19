# Changelog

## 0.1.0

First public release / 首次公开发布。

- Developer-facing business, internal-state and code graph with inline details.
- Requirement clarification with recorded answers and unresolved-question checks.
- Python AST slices, source bindings, runtime probes and code/graph change checks.
- Concurrent activities, capacity waits and all-join rules in the application's state machine.
- Synthetic delivery example, live PixiJS graph, scenario replay and core-only packaging.
- Bilingual installation and usage guides, pinned Python dependencies and MIT license.
- Portable Python command resolution and deterministic generated-file line endings.
- Fix for a stale HTTP state snapshot paired with a completed operation flag.

Reproduce validation with `python tools/verify.py`: 22 clarification tests,
13 clarification workflow steps, 30 business/activity tests, 16 scenarios in
3 observation modes, 14 graph assertions, installation/HTTP checks and execution
of the observer-free core package. These are automated checks, not human usability
evidence or a proof of all application behavior.
