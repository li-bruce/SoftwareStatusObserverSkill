# Actual implementation and delivered projection

AI maintains this contract. Configure `mapping_contract: "mapping.json"` and `require_mapping_witnesses: true` in sync.json. It defines the implementation evidence checked this stage; business expectations remain separate.

`mapping.json` uses `schema: bo-mapping/v1`:

| Field | Meaning |
|---|---|
| cases, modes | Explicit required scenarios and on/off/fault modes, never inferred from submitted results |
| source | Actual storage reader or function-result source |
| actual_collection | Array path to each run's actual instances, e.g. `["authority_snapshot","runs"]` |
| actual_id | Stable actual instance identity path, e.g. `["id"]` |
| fields | Unique id, real graph node, actual-value path, mapped path under observed projection |
| export | Required public-export case and mode |

Compare at least state, complete revision, build_id, and every declared context field per instance. With activities, compare the complete configuration. A wrapped configuration may specify reviewed keys; the actual configuration must contain exactly those keys, including updates for new fields. Compare actual/projected lists even with zero instances.

Example: `{"id":"slots","node":"available_slots","actual":["slots"],"mapped":["context","slots"]}`. Use a real project node. Actual values must be independently read, not copied from the projection.

Preserve every run's case, mode, events, business observations, and storage records; add:

```python
machine = bo_machine(actual_snapshot)
run["projection"] = {"build_id": build_id, "machine": machine,
                     "instances": graph.bo_instances(machine)}
```

Produce top-level stategraph_export with public `graph.bo_export(runtime={"machine": selected_run["projection"]["machine"]})`, selecting the contract's run. Use the same adapter as Web/Python queries; do not create an idealized test-only projection.

The checker reads mapped values from the delivered projection and compares required cases, instances, revisions, builds, fields, and public export. Existing mapping_checks and business assertions remain; reports separate witnesses from projection_checks.

The contract participates in candidate fingerprints and baselines. Add coverage freely; removing cases/fields or changing old bindings blocks delivery. Technical migrations preserve old bindings, add new ones, and verify migration rather than resetting begin. source_moves does not automatically rewrite this contract.

Required negative cases: missing exported instance/field, wrong object/return, stale revision, fewer cases, and a public export disconnected from a separately submitted equal-value comparison. Accurate projection of a business violation can pass mapping while state/business checks fail. Finite contracts do not prove arbitrary natural-language meaning; disclose unexecuted paths, dynamic code, and external-service scope.
