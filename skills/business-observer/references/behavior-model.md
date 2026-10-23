# v3 property graph and evidence contract

Use `schema_version:3`. `intent` references project requirements JSON. `source_files` explicitly includes business, adapter, probe, and UI files to bind. `nodes/edges/overview/scope` are required. [behavior.example.json](../assets/behavior.example.json) demonstrates structure, not mandatory domain/path choices. No graph database is required.

A node has stable `id`, `kind` (`action/function/decision/wait/effect/data/state`), `label`, `summary`, `source={path,symbol}`, and `capture={in:{field:type},out:{field:type}}`. Optional fields include parent, requirements, input/output meaning, predicate, and resume. Executable nodes need source. Capture types may be string/number/boolean/scalar, object field dictionaries, or single-item array schemas. Unlisted fields are dropped; excessive or incorrect values are rejected.

An edge has `id/from/to/type/label/evidence`. `flow` declares allowed progression, `data` value dependence, `guard` conditions, `contains` grouping. These are declarations, not execution evidence. Overview and parent control presentation; hidden nodes remain in the graph and grouping creates no facts.

An event includes `id/run_id/seq/build_id/model_revision/entity/attempt/node/phase/call_id/parent_call_id/basis/inputs/outputs/depends/observed_at`. Basis may include param_version/epoch/clock. Phases are enter/return/read/decision/wait/commit/change/error; dependency types are data/control/trigger/recheck. Data/control dependencies stay within an attempt; cross-attempt linkage requires explicit trigger, and renewed authorization uses recheck. Missing references or incompatible builds/versions must not be silently joined.

`call_id/parent_call_id` describe calls; `depends` describes value/control dependencies. Adjacent sequence numbers give display order only. Existing references do not prove correct semantics; review insertion points and actual values.

`/api/view` contains model, manifest, binding_status, events, health, and authority. Authority adapts actual entity/basis/state/parameters/approvals/relation/effects from business storage; the viewer is not business authority. Historical snapshots add `historical=true` and `case_label`. Current evidence requires matching build/entity/basis, including relationship/time changes. History retains original inputs/outputs.

The manifest stores file/model/intent hashes, bound function locations, source snapshots, calls, and guards. Source changes must show stale. Displayed source is the loaded snapshot; changed disk source is separate evidence. `unknowns` lists omissions and non-static uncertainty.

Domain presentation comes from the model: default_node; presentation.subject/states/command_panel_url (local path); overview and views.dependencies node/x/y coordinates. edge.short_label/overview_route are display-only. Nodes may expose predicate/resume/reason_labels/inspect_target. candidate_table configures child functions, identity, and Boolean condition columns; aggregate specifies repeated candidates' ID/result fields. Group by parent_call_id, retaining aggregate and individual results. Ordinary models need no candidate table. Optional `/api/view.available_cases` lists historical scenes; otherwise only current execution exists. The template does not hardcode domain IDs. Project implementation owns large-layout choices and authorization.

Minimal function node:

```json
{"id":"price","kind":"function","label":"Calculate price","summary":"Convert quantity into an amount","source":{"path":"domain.py","symbol":"calculate_price"},"capture":{"in":{"quantity":"number"},"out":{"amount":"number"}}}
```

Match schemas to source and actual fields before capturing; renaming a copied example is insufficient. Future command descriptions may contain command names, inputs, and guards. The current viewer cannot execute business commands; editable presentation is not executable business control.
