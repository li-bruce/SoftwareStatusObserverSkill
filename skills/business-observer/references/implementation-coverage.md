# Implementation coverage

The inventory asks whether implemented behavior is represented by graph/capture; it does not judge the user's business rules. Coding AI maintains it. Discovering an implemented feature requires truthful graph inclusion, not falsely treating it as a user-confirmed requirement.

The generator reads `implementation.json`, embeds `implementation` in the model, and tracks the file in source_files. Validate after `code_structure.enrich`. source_scope.roots includes `.`; tool exclusions are explicit, never a way to hide business entrypoints.

`change_sync inspect/verify` calls `implementation_coverage.py`. Missing legacy inventories fail until supplied and passed through existing gates, without baseline reset. Probes, white-box assertions, independent mappings, and state constraints remain protected.

```json
{"schema":"bo-implementation/v1","features":[{"id":"upload","label":"Submit file","business_node":"upload","nodes":["upload"],"sources":["app/service.py::upload"],"parameters":[{"source":"app/service.py::upload","name":"note","node":"upload","direction":"in","field":"note","policy":"value"}],"cases":[{"case":"upload_with_note","node":"upload","phase":"commit","values":[{"direction":"in","field":"note","path":["saved","note"]}]}]}],"support":{"app/storage.py::save":{"node":"upload","reason":"Persist the submission"}},"excluded":{}}
```

This example assumes one note parameter; account for every actual feature parameter. Begin from the independent source inventory, not the already-authored graph. Inspect HTTP routes, message reads, background jobs, authorization, and persistence. Unresolved dispatch remains an explicit gap.

- `features`: entrypoint source identity, visible business node, capture nodes, real cases. Display names may differ from code.
- `support`: assigns support symbols to a node, preserving searchable source nodes and resolvable calls. Unobserved helpers remain static, never marked executed.
- `excluded`: only identifiable observer code or constructors with reasons. Ordinary utility/business routes cannot escape coverage. Inspect observer HTTP routes using [exclusion rules](observer-exclusion.md); source remains versioned even when no business node/event is generated.
- `parameters`: every feature-entry argument. `value` captures directly. `derived` and `redacted` require reason and a real captured representation. `context` is limited to agreed technical context, never business inputs such as note. Signature/field changes invalidate old entries.
- `cases`: actual `case/node/phase`. Every declared capture field must occur with a valid type; absent events/fields or another build cannot pass. `values` compares events to independently obtained observations. Key inputs/decisions/effects need these comparisons or existing white-box/mapping assertions; both sides must not read the same probe.

Version binding and anti-weakening protect inventory/cases. Do not repair tests by deleting fields/scenarios. Feature deletion/rename/meaning changes require source migration and recorded requirement changes.

`Trace.record(..., scope="application")` covers login/configuration operations outside a task. `scope="entity"` spans attempts for one entity. Default attempt scope remains strict. Declare scope explicitly. Replay cannot inject later login/configuration events into earlier frames.

Static coverage establishes disposition for selected source symbols; scenarios establish values/results actually executed. Neither fully interprets dynamic calls nor proves every user intent or execution path. Preserve support-only, unresolved-call, and finite-scenario limitations in reports.
