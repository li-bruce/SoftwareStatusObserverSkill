# Independent Python state network

The state network remains part of the project. Capture and debug Web can be switched or packaged separately.

| Setting | Meaning |
|---|---|
| development_mode: drive | User chose declaration-guided development; any framework is still allowed |
| development_mode: observe | User chose their own logic; AI maintains the graph from implementation |
| execution_mode: drive | The real executor consumes the same state declaration |
| execution_mode: observe | Application code/engine owns outcomes; adapters read actual state |

Ask naturally at setup, record the answer/source, and keep both mode settings consistent. Do not choose without an answer. Both require mapping, probes, presentation, and delivery gates; users do not edit configuration themselves.

```text
app/                         Domain behavior and storage
app/ports.py                 Neutral, failure-isolated bo_ interface
bo_stategraph/
  __init__.py                Public BOStateGraph query/export
  bo_contracts.py            Shared declaration/type/hierarchy validation
  execution_contract.py     Activity/resource/wait/join constraints
  workflow.py               Complete project executor and declaration
  query.py                  Actual-storage projection of all instances
  config/retention.json     Capture cache/log limits
  config/views/local.json   Personal layout/names/notes/filters/language
integrations/bo_*.py         Optional capture/service wiring
observer_runtime/           Optional development, capture, recording tools
behavior.json               Full relation model tied to execution declaration
```

Old workflow.py paths in complete examples are compatibility imports; business callers use the independent module. The executor may depend on transitions or another chosen engine. Public query/validation core is standard-library-only; do not extend that claim to the full executor.

Install public core/viewer with bo_upgrade before adding project workflow/query/constraints. Do not redefine BOStateGraph or its export format in __init__.py. Cross-instance resources and other extensions use independent project validators while preserving actual snapshots/diagnostics/public instance protocol. Do not misrepresent a shared pool as a per-run pool.

BOStateGraph never invokes business guards/effects. bo_structure/bo_definition return declarations; bo_candidates evaluates supplied evidence only and cannot authorize execution. bo_instances uses the authoritative snapshot provider. Page, query, and export share actual configuration, with no second writable state cache. Alternatively bo_observe accepts real complete-version/build snapshots; it is mutually exclusive with a provider.

bo_observe retains invalid actual states with mismatch diagnostics, never repairs facts to match the model. Incomplete revisions mark partial; an activity revision is not a complete instance revision. Shared bo_contracts checks types/hierarchy/loaded definitions, including transitions-style nested states and parallel regions. History states and unknown separators fail; this is not a full SCXML interpreter. execution_contract checks activity/resource rules.

## Integration

Before load, call validate_runtime_definition with actual loaded_engine, loaded_version, and guard_names. Bind using bo_require_definition; mismatches raise ValueError. bo_check_definition is diagnostic only. Supported reference semantics include flat transitions, child precedence, ordered wildcards, compound initial states, and independent parallel regions. History, cross-region transitions, callbacks, and unknown engines require an adapter and are rejected. python.explicit describes ordinary Python; adapter-selected is only for the explicit-mode example, not arbitrary engine verification.

Acquire a consistent provider snapshot outside the graph lock, then derive instances/export. Never call business callbacks under the graph lock. Test concurrent querying, recording, export, and business progress.

Set sync.json stategraph.module to bo_stategraph/__init__.py, plus modes, decision provenance, and static/runtime required probes. A user change to observe records decision_source: user and the original meaning. Mode changes never remove observation contracts.

source_scope inventories supported project languages: Python AST, JS/TS/SFC adapters, justified excludes. bo_sync scan/watch emits internal maintenance work; coding AI consumes it before inspect/verify/accept/check. Watch does not wake arbitrary editor LLMs. Connect project AI instructions and the normal gate.

## Query and export

Complete examples expose GET /api/stategraph and /api/stategraph/export. model contains all modeled relations. instances/runtime.machine come from the same snapshot; runtime contains only connected, retained evidence. Never invent initial instances without execution.

Delivery observations return public bo_export output as stategraph_export for the current model/build. The checker validates protocol, shared instances, and [mapping contract](mapping-contract.md) fields for every case, retaining original mapping_checks. A legal empty export is insufficient. Views with runtime_frames export frames/events, checking identity/revision on import.

```text
python bo_stategraph/__init__.py export --model behavior.json --build-id unbound --out stategraph.json
python bo_stategraph/__init__.py check stategraph.json
```

Offline structure export is not_observed/not_checked. export --view view.json captures a complete /api/view response. Digests detect integrity changes; they are not signatures.

GET/POST /api/preferences uses revision conflicts and atomic writes across windows/processes. Initial migration may read this project's old browser cache. Exclude personal files from sharing/core packages. Stable IDs retain layout; explicit one-to-one presentation.node_aliases migrates IDs. Preserve conflicting material; never guess identity from similar names.

The project identity returned by `/api/preferences` owns every view key, independently of the graph title and build. `presentation.layout_aliases` lists explicit former layout names when migration is needed. `presentation.edge_aliases` migrates individual relation exclusions. Filters include `hiddenNodes` and `hiddenEdges`; hidden groups hide their descendants. Removed IDs remain dormant. A new ID receives an initial position without rearranging existing IDs.

“All elements” resets scope, query, depth, type, individual, and advanced-detail filters. Expansion and coordinates remain personal choices. The coverage readout distinguishes visible, folded, and filtered nodes/relations. A relation within a folded group is counted there; cross-group calls are projected onto regions with the actual endpoints retained in relation details.

Recordings belong to a build and model hash (or a model-content digest for providers without one). The current list and retrieval endpoint exclude older versions; a viewer leaves replay when this identity changes. Original private recording files and exported review evidence are preserved. Restarting the same code/graph does not clear the list.

Count/time retention bounds caches; size rotation bounds JSONL without deleting business storage or saved recordings. Recording subscribes directly to capture events to avoid UI-cache gaps, stops at limits, and reports loss. Runtime incremental APIs and performance baselines remain TODO.

## Upgrade

Preserve change_sync begin before moving the complete executor/recovery/scheduler into workflow.py and updating actual callers. Old imports delegate; never retain two implementations. Initial baseline hashes identify managed local files; subsequent runtime-version.json tracks release/hashes.

```text
python SKILL/scripts/bo_upgrade.py plan --root PROJECT --runtime observer_runtime --viewer static/graph --baseline .stategraph/CHANGE/baseline.json
python SKILL/scripts/bo_upgrade.py apply --root PROJECT --runtime observer_runtime --viewer static/graph --baseline .stategraph/CHANGE/baseline.json
```

Use real paths; copied upgrade tools also need --source pointing to canonical Skill scripts. Modified shared files require reconciliation; copy failure rolls back with backups. Project workflow/query and config/views are not copied. Protocol differences require explicit artifact migration. Regenerate, compare old/new behavior, then verify/accept/check. Copying alone is not migration acceptance. Repository maintenance uses tools/sync_runtime.py and tools/check_package.py.

basis_fields explicitly identifies revision dependencies; semantic_roles labels authorization/etc without name guessing. presentation.context_fields controls explanatory parameters; presentation.recording allowlists recorded fields. Waiting/interrupted instances retain all known facts. Old builds and unknown worker states remain partial.

examples/python-modes demonstrates both modes. Complete examples test storage, scheduling, permissions, recording, and export within their declared scope, not all dynamic calls.
