# Software behavior models and Petri worknets

Workflows describe progression; statecharts describe objects responding to events. Software may also use dataflow, event protocols, data relationships/constraints, computation dependencies, or hybrid continuous/discrete models. Link several representations to functions and facts in one typed graph; their edges are not interchangeable executable transitions.

[SCXML](https://www.w3.org/TR/scxml/) covers nested/parallel states; parallel state does not imply real threads. See [Petri/process discovery](https://www.processmining.org/process-discovery.html). Choose observable properties before enumerating states to avoid state-space explosion.

## Integrate concurrency semantics

Default to [existing machine/activity graph](integrated-execution.md). The semantics below do not require a separate analysis layer, authority, or Petri page. The worknet contract also supports adapters for existing Petri engines and legacy projects.

Where relevant, define place/token types, initial marking/capacity (resource tokens differ from data/permission evidence); consumed/produced tokens, arc weights, guards, external completion (reads do not consume); enabling/atomic firing/wait/resume; failure/cancel release; ALL/ANY joins and error completion; invariants/final states. Tokens cannot replace authorization rechecks at commit. Parallel arrows alone do not implement concurrency.

Prefer the existing scheduler/worknet engine. A small integer P/T kernel is not a general colored/timed Petri engine. Time windows, priorities, read/inhibitor arcs require matching semantics/checkers. Current worknet_contract checks integer consume/produce arcs and explicit Boolean guards only.

## Shared definitions and runtime checks

[worknet.example.json](../assets/worknet.example.json) illustrates declarations. Model worknet comes from the actual executor's definition. Observations return that actual top-level worknet; each case returns capacity/marking/guards/enabled/journal, with transition/before/after/guards per journal entry.

```text
python SKILL/scripts/worknet_contract.py --model behavior.json --observations observations.json
```

change_sync compares model/loaded definitions, replays arcs, checks resource conservation and current enabling. required_worknet_cases requires markings; unstarted cases may have empty marking. Test blocking at capacity one, actual overlap at capacity two, failure release, no premature join, and cancel/retry interleavings. Finite exploration states its bounds/marking counts; it does not prove arbitrary networks.

Default views show actual execution/resource/wait/join information inside original groups/functions. A requested Petri projection may show places/transitions/weights. Distinguish current state, history, and final scenario outcome; early replay must not highlight future transitions. Missing events remain gaps, not inferred tokens. Failure branches may collapse but remain discoverable. Historical graph/source/parameters stay tied to the original build.
