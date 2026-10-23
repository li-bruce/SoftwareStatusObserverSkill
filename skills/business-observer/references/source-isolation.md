# Source ownership and observer isolation

Read the project's architecture first. This adaptable Python layout is not a mandatory naming scheme:

| Path | Ownership | Dependencies |
|---|---|---|
| app/ | Domain functions, transactions, storage, effects | Domain and independent state module |
| bo_stategraph/ | Complete execution, declaration, validation, instance query/export | Neutral domain/storage ports and chosen engine |
| app/ports.py | Application-owned neutral event interface | No graph-model or Skill dependency |
| integrations/bo_*.py | Project-owned wiring/adapters | Business ports and observer implementation |
| observer_generated/runtime/ | Copied Skill runtime | Does not import business implementation |
| observer_generated/runtime/bo_stategraph.py | Compatibility entry only | Delegates to bo_stategraph, no separate instances |
| observer_generated/behavior.json | Generated source structure/business mapping | Rebuilt by generator |
| tooling/ | Authored mappings, generators, gates | May read all layers during development |

AI-written business code is still project-owned. Actual execution may use a state engine or ordinary code; declarations/adapters/real evidence connect either to the independent graph. Both modes maintain model, monitoring, source synchronization, graph, and checks. See [independent module](independent-python.md).

Explicit delivery choices may disable capture or omit debug Web. Keep structure/export by default. Legacy `core` export demonstrates full observer removal, not a default development artifact; required business state machines remain. Removing even neutral-interface calls requires a build transform and equivalence tests. Directory isolation is not zero overhead, and an observer-free package cannot claim runtime monitoring.

Use `bo_` for observation methods/files and `BO` for adapter classes, e.g. trace.bo_record/events.bo_emit. Preserve domain names. Generated folders declare ownership/tool provenance; editable UI/mapping sources remain project-owned. Optional callbacks invert dependencies. Callback failure, disabled capture, or loss must not decide business outcomes. Skip payload evaluation when disabled/out of scope. Legacy port aliases are compatibility only; update probe_callees and white-box checks on rename.

## Configuration and commands

See [ownership.example.json](../assets/ownership.example.json). `scan` is explicit scope. `layers.paths` uses longest-prefix ownership; `allows` constrains local static imports; `external` may constrain core dependencies. `reject_dynamic` rejects common dynamic import/exec. managed_paths stores generated-file hashes and must not contain its own manifest.

```text
python SKILL/scripts/architecture_guard.py inventory --root PROJECT
python SKILL/scripts/architecture_guard.py check --root PROJECT
python SKILL/scripts/architecture_guard.py seal --root PROJECT --reason "Reviewed regeneration"
python SKILL/scripts/architecture_guard.py package --root PROJECT --out dist/core.zip
```

Seal records reviewed regeneration, never substitutes for requirement/runtime acceptance. Track ownership, generator, adapters, checks, and generated files in change_sync. Begin first, regenerate/seal, then verify/accept. Delivery calls both synchronization and architecture checks.

Package only explicit core_include paths; never overwrite a ZIP. core_layers/core_resources constrain contents. Pass synchronization first, extract into a fresh directory, and run representative core scenarios. Verify required state/worknet behavior remains and observer imports/files do not. Retain dependency versions/licenses.

This guard parses Python static imports in scan scope without executing code. Dynamic aliases, plugin injection, library internals, and unscanned directories require separate review. It is not a hostile-code sandbox. Renaming alone proves no decoupling. Version-bind the guard and ownership manifest too.
