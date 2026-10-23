# Concurrency inside the existing state machine and graph

Extend the application's actual execution mechanism. Petri-style ideas contribute capacity/tokens, enabling, atomic acquire/release, waiting, and joins. Developers need to see what runs, why it waits, and what enables progress through existing business/function nodes. A separate Petri projection is optional only when requested, never a mandatory extra authority or page.

## Complete state and visible summary

A high-level checking state summarizes digest/content activities. Retain complete per-run configuration: run ID, parameter version, activity-instance states, resource scope/capacity/holders, waiting targets, join condition, and completed work. Repeated concurrent calls require distinct identities, not a last-result slot keyed by function name.

Activities/resources belong in the original declaration read by executor and generator. Summary and drilldown use the same IDs. Instance queries are independent of collapse. After parameter changes, an old run's still-running activities remain queryable until they actually stop, even if commit is no longer permitted.

Completeness is bounded by declared business execution scope. Report ordinary unmonitored calls, external services, and dynamic activities. Undeclared work is unknown or a contract error, not hidden under a seemingly complete running label. Static calls do not reveal actual state.

## Execution constraints

- Acquire capacity and enter running atomically. Insufficient capacity enters waiting with the resource identified.
- Release actual holdings on completion/failure. Distinguish cancelling queued work, cooperative cancellation, and waiting for running work to finish; a cancellation request is not proof all work stopped.
- ALL joins require every prerequisite in the same run/version to finish successfully. Check internal configuration before ready/completed, not merely a passed=true return.
- Resource scope is explicit: run-local, process-shared, or external/global. Separate capacity-one pools do not enforce one global slot.
- Multiple activities may run simultaneously. A single high-level enum must not discard the parallel configuration.

Use a hierarchical/parallel engine or a high-level state plus typed activities as appropriate. Do not rewrite every application as a generic Petri engine.

## Python reference contract

machine.execution declares schema=activity-graph/v1, within, parent, activities/resources/join and corresponding guards. IDs reference original graph nodes with execution_role activity/resource/join. Resource edges carry positive integer units; join edges cover every prerequisite. Generate them from the machine declaration.

Configurations contain attempt/param_version/revision/activities/resources/join/journal. Journal entries contain seq/event/activity/before/after. Authoritative queries return all execution instances, not only the latest. Declared activities and static functions retain their own source attribution.

The checker supports one execution per declared activity per run, run-local integer resources, wait/start/finish/join/abort, and ALL joins. It does not support dynamic activity counts, repeated same-name instances, process-wide pools, or arbitrary loops. Extend identity/engine/checker before claiming those semantics.

change_sync verify compares loaded declarations, node/edge consistency, and journal replay. required_execution_cases require configurations. Even with capture off, read configurations from application storage. Legal JSON does not establish actual work completion; independently test function results/effects.

## Presentation

A business group can summarize “Digest running; content check waiting; available 0/1.” Expand original nodes for state, function, parameters, and source. Resource edges indicate acquired/exhausted/released capacity; join edges identify finished/pending prerequisites.

Use readable run/version labels. Every historical frame uses that frame's values/edges; final outcome is separate. Clear old content on version switches. Keep research terminology/test counts out of the operating canvas.

The shared viewer cannot understand arbitrary project configuration automatically. Adapt attempt selection, exact journal frames, and activity/resource/join node bindings and verify in a browser. Copying a template proves no complete visibility. Use real source/model types. Ordinary helper calls remain drilldown nodes, not fabricated resource dependencies.
