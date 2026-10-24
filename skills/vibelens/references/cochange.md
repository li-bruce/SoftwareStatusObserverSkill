# Maintain and verify while changing code

Business abstractions follow requirements; local structure follows static evidence; declarations bind actual execution; runtime facts come from probes/storage. The initial user chooses drive/observe. Both require monitoring, source adaptation, graph, and checks during each coding step—not a graph added after implementation. See [independent module](independent-python.md).

## Integration

For moved/renamed bound functions record review.json source_moves:

```json
{"source_moves":[{"from":{"path":"old.py","symbol":"commit"},"to":{"path":"app/service.py","symbol":"commit"},"reason":"Move the implementation while retaining node, probe, and check identities"}]}
```

Old/new symbols must exist in baseline/current AST inventories with one-to-one mapping; authored node IDs must bind the new symbol. This permits required_probes.symbol and white-box source relocation only—not removing probes, changing node/phase, deleting parameter checks, or changing expectations. Existing source/probe/runtime checks still apply. Migration records do not prove equivalence. AI handles technical moves without new business approval. Keep stable test entrypoints; this table does not rewrite arbitrary commands/data.

Alongside intent/behavior/manifest, add project sync.json and acceptance.json using the [sync](../assets/sync.example.json) and [acceptance](../assets/acceptance.example.json) examples. Adapt domain/paths; do not inherit approval rules. Asset examples describe fields and are not a mutually runnable scaffold. Complete matched projects are examples/delivery and examples/team-archive.

Important sync.json fields:

- code_files: supported-language source indexed and included in model source_files. Assess every new file/entrypoint; unscanned content is not covered.
- source_scope: roots includes `.`, justified tool excludes, require_symbol_classification=true. Do not exclude business or put it only in watch_files. Add the [implementation inventory](implementation-coverage.md) linking features/source/capture/cases.
- require_mapping_witnesses=true: independent-state projects must compare actual values to projections; do not disable it.
- watch_files: generators/checks and extra inputs. Track project Python scripts in observation/test commands; tool contents also bind versions.
- discovery: project-relative confirmation record, version-bound automatically. Blocking questions, unsupported answers, missing graph/requirement/case links fail verify/check. Legacy omission is compatible but must be disclosed. See [dialogue](requirements-dialogue.md).
- required_probes: literal node/phase plus optional path::symbol. probe_callees names real interfaces such as trace.record.
- required_runtime_probes: events that must actually occur in enabled cases. Static presence alone cannot pass.
- observations_command: reviewed argv array for the real observation adapter, no shell concatenation or unchecked arbitrary command.
- test_commands: relevant existing project commands; graph-generator self-checks cannot replace business assertions.

After preserving authored grouping, a generator calls:

```python
from vendor.code_structure import scan, enrich
index = scan(root, ["domain.py", "bo_stategraph/workflow.py", "store.py"])
model = enrich(authored_model, index, depth=1)
```

The authored model comes from intent and shared execution declarations. enrich preserves business IDs/groups/rules and adds local source-backed functions, parameter/return types, actual argument expressions, and possible-call edges. Static helpers have no fabricated runtime events. Several business contexts may use one function.

The code_structure scan/project CLI is available; project requires distinct authored input/generated output paths. Unchanged units may reuse parsing; extractor changes invalidate cache. Dynamic dispatch/reflection/callbacks remain unresolved. Ordinary AST is not a complete CFG/dataflow analysis.

## Expectations and actual observation

Record normal/counterexample observable outcomes before implementation, derived from confirmed requirements and labeled engineering assumptions. Maintain them separately from implementation, graph generator, and observation readers.

Each acceptance checks entry has id/requirement/case/path/equals and compares exact JSON values from actual return/state/effect/key values, without arbitrary expression evaluation. Execute each referenced case in on/off/fault, or all configured probe_modes. model_checks constrains meaningful higher-level declarations/mappings such as ANY aggregation, guards, parentage, context type. Paths traverse JSON; a string selects nodes by ID in arrays. Avoid fixing every display label/layout. Unconstrained prose still needs source/intent review.

The observation adapter runs the application and reads real storage/results. It must not read acceptance values to manufacture answers or infer application state from the graph. Standard output is one JSON object with build_id, full actual loaded machine definition, and runs. Each run contains case/mode/observations/events. The machine must cover the real states/events/context/guards/transitions contract. Return every required case/mode. Probe build identity comes from the same loaded build; the reference uses read-only behavior_model.capture with load-time file checks.

## Each change

1. begin before editing preserves request/source/model/requirements/expectations. --requirements lists only authorized changed requirement IDs; pure refactors may list none. Investigate/preserve preexisting stale evidence rather than hiding it under a new baseline.
2. During small coding steps update real code/state/probes/mapping, regenerate structure/candidate, and inspect. impact.json lists changed functions, possible callers, business parents, unclassified symbols, and errors. structure.json retains deterministic source evidence. Review each candidate.
3. verify checks structure/bindings/declarations/probes, then actual observations/tests, comparing machine definition, independent expectations, runtime probes, and build identity. Input changes during verification invalidate results immediately.
4. accept only a passing current candidate; delivery check rechecks it. Later code/model/intent/config/check/tool changes invalidate the receipt.

```text
python SKILL_DIR/scripts/change_sync.py begin --root . --change .stategraph/change-001 --request "Confirmed change" --requirements R4
python build_model.py
python SKILL_DIR/scripts/change_sync.py inspect --root .
python SKILL_DIR/scripts/change_sync.py verify --root .
python SKILL_DIR/scripts/change_sync.py accept --root .
python SKILL_DIR/scripts/change_sync.py check --root .
```

begin stores the active pointer, so subsequent commands may omit --change. Nonzero inspect during work means not yet deliverable. Never derive business sequence/causality from static call ordering.

review.json shares the baseline/impact directory and includes current candidate_id; decisions.business/state_machine/abstraction/probes each have action updated/unchanged/not_applicable and concrete reason. requirement_changes ties altered expectations to authorized requirement changes. Implementation ownership is validated by the inventory; legacy excluded_symbols cannot bypass new gates. Review becomes stale when the candidate changes.

Review is semantic rationale, not a passing test. Writing updated everywhere cannot override inconsistent source/state/probes/results/effects. Deleting/changing protected expectations/declarations requires the begin-recorded requirement scope. Adding counterexamples is allowed; implementation changes alone do not justify rewriting requirements.

## Delivery gate and limits

Connect `python SKILL_DIR/scripts/change_sync.py check --root .` to normal tests/CI. Success is exit 0; stale/failed is nonzero. Initial adoption only establishes comparison from that time. Do not install global Git/editor hooks. Old processes retain old build identity; only verified, loaded new programs bind new graphs to new facts.

Connected, executed checks reject missing bindings, stale projections, constrained rule drift, differing runtime declarations, missing/unexecuted probes, failed business counterexamples, unauthorized expectation weakening, and old evidence presented as current. They do not prove uncovered paths, arbitrary prose, dynamic calls, external semantics, or tamper-proof audit. Maintain independent meaningful expectations/readers; an always-success test is not acceptance. Without a connected gate, claim workflow adoption only, not enforced interception.
