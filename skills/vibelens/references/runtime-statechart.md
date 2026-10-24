# Integrate state execution into the application

For new/refactored lifecycles, ask the user for drive or observe. Drive uses a suitable native engine consuming the declaration; observe adapts actual application state. Both maintain graph/monitoring. Record choice/provenance as described in [independent state network](independent-python.md). Prefer adapting an existing engine's definition/context/snapshot over creating another authoritative state machine.

## Engine fit

- [transitions.HierarchicalMachine](https://github.com/pytransitions/transitions): nested states, explicit events, guards, callbacks. Examples pin 0.9.3. Disable auto_transitions so generated to_* methods cannot bypass conditions. Add dataclass/Enum and executable boundary checks for context/event types.
- [python-statemachine](https://python-statemachine.readthedocs.io/en/latest/): declarative states/events and validation; verify hierarchy, async, and recovery against the project's locked version.
- [XState](https://stately.ai/docs/typescript): typed context/events, guards, actors, inspection for native TypeScript execution. Do not reimplement Python business logic in a browser just to visualize it.

Choose for language, sync/async behavior, hierarchy/concurrency, persistence, recovery, and dependency cost. The example engine is not mandatory.

## Minimum contract

Declare persisted enums/hierarchy, initial/final states, events/payloads, context types/ranges/enums/units/mutability, guards/actions, errors/cancellation/retry. Keep function input/output types. Execute validation; Python annotations alone do not validate inputs.

With an engine, create executor and graph from the same declaration. With ordinary code, load the declaration in the independent module and verify actual source/state changes against it. Business grouping, functions, reads/writes, and decision dependencies are additional typed relations, not all transitions. `scripts/statechart_contract.py <behavior.json>` checks the Python reference format. State whether definitions come from actual engine or observer declaration. The former needs loaded-engine comparison; the latter needs independent state/condition/value/effect tests. A module agreeing with itself proves no execution equivalence.

Business commands validate inputs, read authority, and execute guards. Keep protected effects/final state transactional where possible; external systems need project-specific idempotency/recovery. Observation records semantic points but does not decide eligibility. Separate sync transitions from async work: do not hold locks through long work, and recheck mutable parameters/authorization before commit.

A transactional transition log is business persistence and rolls back with state/effects. Best-effort probes have different loss/fault windows. Entering a state machine does not replace authentication.

Test invalid states/events/types/ranges, rejected guards, rollback, repeated commit, parameter changes, authorization replacement, error/retry, and restart recovery. Off/fault probes must preserve execution. Prove displayed states come from actual execution and match source version, declarations, and persistence.
