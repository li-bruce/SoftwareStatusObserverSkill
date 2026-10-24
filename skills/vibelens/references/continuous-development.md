# From requirements to actual execution

This Skill is a required companion to development. The user initially chooses `drive` (execute from a state declaration) or `observe` (follow existing logic). The main workflow may use any user-selected architecture, framework, or coding Skill. Both modes always require monitoring, source-driven state-network updates, function/parameter mappings, the graph, and validation. Internal maintenance is not a user-operated workflow. See [independent state module](independent-python.md).

The files and commands below are for AI and integration maintainers. Users discuss graph meaning, request ordinary development changes, and inspect the updated graph and results. AI maintains artifacts and runs checks. Do not repeatedly request graph confirmation when business meaning is unchanged.

| Main workflow | Companion work | Evidence |
|---|---|---|
| Requirements and design | Express supplied business chains; clarify meaning with focused graphs; define states, parameters, interfaces, independent expectations | Sources, questions, model, cases |
| Coding and refactoring | Follow recorded drive/observe choice; maintain isolated state module, source bindings, core capture, graph, checks | Change scope, locations, types, probes, model revision |
| Debugging and delivery | Compare actual execution, internal values, authoritative effects, observer isolation | Results and focus graph for the same build |

Hand off requirements, model, bindings, probe contract, independent expectations, and check entrypoints—not just a requirements summary. Existing projects map their own names and test commands through configuration. Reuse real lifecycle declarations from mature engines, handlers, or domain objects. Do not create a second controlling state machine or require the example's framework.

Cover all implemented features. Missing state, source mapping, capture, or verification prevents completion claims. Collapse and focus do not shrink the source inventory. Report unsupported languages and dynamic mechanisms as gaps. Ordinary implementation choices need no Skill approval; choices changing confirmed behavior return to the relevant question. Small changes update only affected artifacts.

## Persist the development contract

At first integration, merge a short contract into the project's existing instruction file, preserving other rules. Replace every placeholder with real relative paths and runnable commands:

```text
This project uses VibeLens for its developer runtime graph.
Ask for drive or observe at first setup, record the answer and source; reuse an existing choice.
Both modes require monitoring, source-driven state updates, parameter/function mappings, graph, and checks.
Read the project rules, current graph, and Skill; preserve the existing design/coding workflow.
Before related behavior changes, preserve a change baseline. Update state, bindings, probes, and independent expectations while coding.
Run the project validation entrypoint, including change_sync check, before delivery. Fix failures; never reset the baseline to hide them.
AI performs this maintenance. Ask the user only about unclear business meaning and present the updated graph and relevant results.
```

The normal validation command must call synchronization checks and propagate failure exits. Rehearse a source-only change that omits graph/probe maintenance: the normal gate must reject it, then pass only after the missing updates and revalidation. This persists instructions across conversations and catches omissions at the gate; it cannot intercept every external edit that bypasses that gate.

## Before implementation

1. Derive the business chain from supplied requirements into `intent.json`, `discovery.json`, and a candidate graph. Follow [dialogue rules](requirements-dialogue.md). Keep user-owned ambiguity pending; proceed with ordinary technical choices.
2. Define types, states, events, relation rules, and success effects. Reuse actual declarations in existing projects. In new projects agree a minimal execution interface and scenarios; the entire model need not be finished before coding starts.
3. Save independent expectations in `acceptance.json`. Define `whitebox.json`: each key rule's node, function, parameters, and required runtime values/relations.
4. Run `whitebox_contract.py plan`. Its result is `planned`, not a passed application test.
5. Export focused JSON/Markdown with `focus_graph.py`, explaining shown nodes and outside conditions. Design graphs may use stable IDs and pending bindings; acceptance requires every declared key function to resolve.

## During each behavior change

- Run `change_sync begin` before editing, preserving old requirements and expectations and declaring allowed requirement changes. Continue an existing change record; do not reset its baseline.
- Configure `source_scope` in `sync.json`: roots, justified excludes, and `require_symbol_classification`. After editing, run `python observer_runtime/bo_sync.py scan --root .`, read `maintenance.json`, and reconcile nodes, declarations, bindings, probes. `watch` produces the same work request; a host or coding AI must consume it. It cannot wake every editor by itself.
- Source inventory includes untracked files. Business code belongs in `code_files`, not merely `watch_files`. Maintain the [implementation inventory](implementation-coverage.md) linking features, support symbols, parameters, and actual events. Free-text `excluded_symbols` cannot bypass a feature. Repeated scans retain pending work; only accepted current candidates advance the source baseline.
- In drive mode implement rules/states/effects from the declaration; in observe mode adapt actual application behavior. Both modes use static analysis for function/parameter/call candidates, bind actual states and key decisions to business nodes, and maintain probes and checks.
- Capture at actual reads, condition evaluation, function results, state transitions, and after successful commits. Capture inputs and decisions from the same call. Do not query or recompute to fabricate an explanation.
- Select necessary fields only. Do not fabricate short-circuited condition results. Repeated calls need distinct `call_id`; preserve run, object, and parameter-version identity.
- Add `"whitebox": "whitebox.json"` to `sync.json`. Execute real scenarios and provide real events. `inspect` checks symbols/signatures, `verify` checks values, `accept` records that version.
- Refresh the focused graph and explain visible changes. Refactors may retain business IDs while updating source mappings. Change expectations only for confirmed requirement changes.

Complete integration also requires `require_mapping_witnesses: true` and a `mapping_contract` file. Define protected scenarios/fields first. Observation commands provide each run's actual `projection`; the checker reads it and binds it to the public export. See [mapping contract](mapping-contract.md). Retain existing `mapping_checks` containing `id/source/projection/actual/mapped`. Read `actual` independently from storage or function output, never from graph expectations. Run every agreed `probe_mode`, at least one real business assertion, and the project test command. Removing an existing mode, probe, or check must not silently pass.

Observation output must contain a real run's `stategraph_export` from public `BOStateGraph.bo_export`. Check its model, build, and instance projection. A same-named custom class, alternative JSON, or merely present module file does not establish integration. Reuse shared viewer assets; supply application data through the same-origin service. Project extensions must not replace the public protocol.

Keep four result categories: `mapping`, `state_rules`, `business`, `project_checks`. Business rules come from independent expectations. Architecture/UI checks are not automatically business failures. Missing evidence and unexecuted checks stay failed or `not_run`. A faithfully displayed bug can pass mapping and fail business rules. Connect `check` to project tests or CI; prompts alone cannot enforce edits, and an unconnected gate must be disclosed.

## White-box contract

Adapt the [minimal contract](../assets/whitebox.example.json); do not inherit its domain rules. Each `rules` entry has `id/requirement/claim/basis/category/node/source`, with optional parameter names/types and return constraints. `basis` references a confirmed requirement or explicitly marked assumption. `checks` reference rules and cases, specify `phase`, optional `select`, event `count`, and `fields`.

Field assertions use array paths such as `["inputs","param_version"]`. Supported checks include `type`, `equals`, numeric `min/max`, and `compare: {"path":[...],"op":"eq"}`. Operators: `eq/ne/lt/le/gt/ge/in`; no eval or executable expressions. Selectors narrow scope but must not hide required failure events. Cover each required branch.

Checked events require `id/run_id/attempt/call_id/entity/build_id/model_revision`. White-box checks run with observation enabled; off/fault modes still verify business rules and authoritative effects.

```text
python <skill>/scripts/whitebox_contract.py plan --root . --contract whitebox.json
python <skill>/scripts/whitebox_contract.py check --root . --model behavior.json --observations observations.json
python <skill>/scripts/focus_graph.py --root . --model behavior.json --nodes permission --depth 1 --out review/focus.json --markdown review/focus.md
```

Runtime evidence uses change_sync's `build_id` and `runs`, each with `case/mode/events/observations`. Handwritten expected events are suitable only for checker unit tests, never application acceptance.

## After implementation

Use the [iteration graph checks](iteration-graph-checks.md) to select affected and neighboring cases and verify actual view boundaries. The enabled source index and configured data graph are checked by the existing `change_sync verify` gate; neither can replace independent runtime witnesses or the project tests.

Check static bindings, independent business scenarios, white-box facts, applicable concurrency/wait/resource behavior, observer isolation, graph explanation, and export reproduction. Locate failures by requirement, node, function, and actual value; list missing evidence separately. Select applicable [validation rules](validation-rules.md), retaining unknowns and scope.

Independent trials use a new directory and conversation, initially receiving only the Skill and actual request. Mark simulated answers clearly; never present them as confirmed production requirements. Let the developer ask first, then answer from the trial persona. Preserve questions, failures, fixes, and the final passing sequence.
