# End-of-iteration graph checks

Use the network to find which observations and neighboring behavior need testing.
Business expectations still come from confirmed requirements and independent
storage/function results. A graph cannot be its own business oracle.

## Select cases from the changed region

After `bo_sync scan` and `change_sync inspect`, inspect each changed feature's
source bindings, parameters, states, and incoming/outgoing relations. Include
shared helpers and other features using the same state or dataset. Reuse the
implementation inventory's `cases`, the mapping contract, and white-box checks;
add cases where a new behavior or captured field has no executed witness.

| Graph content affected | Required check and actual evidence |
| --- | --- |
| Feature, handler, function or parameter | Independently inventory source; resolve the binding; execute its registered case; compare captured fields with the actual input/result. New login or message handlers need their own feature mapping. |
| Decision, permission or state transition | Exercise the confirmed branches and a relevant rejection; compare the current actor, entity, version and resulting state. Run repeated or concurrent operations when that is part of the confirmed behavior. |
| Read, write, transformation or transaction | Refresh the catalog; check real targets and selected values. Require rows when known, errors on failure and commit/rollback outcomes for transactions. A capture allowlist is not a demand to invent every possible field. |
| Source structure, when enabled | Refresh with `bo_code.py scan`; verify with `bo_code.py check`. Reject stale, empty or damaged indexes. Open a local region and the code view; report unresolved targets and display limits. |
| Shared or cross-region relations | Check both ends and direction in the full model, collapsed view, a relevant type filter and local focus. Outside dependencies remain explicit boundaries. Static links alone never count as a runtime transfer. |
| Graph revision | Reload the actual viewer. Keep stable IDs, the selected perspective, positions, notes and filters. An already-seen discussion must not reset the view; a cleared focus stays cleared. Leave obsolete replay and remove old-version recordings from the current list. |
| Observation wiring | Compare real effects with observation on, off and failing. Opening code, querying metadata, recording controls and layout changes must add no business events. A slow source query must not serialize event reception. |
| Retention and recording | Cross the live-history time or count limit during a recording. Saved interval events must remain complete; normal history expiry is distinct from actual missing producer events. A deliberately skipped event must still be reported as a gap. |

Use a relevant isolated negative control: remove a required probe field, change a
captured value, omit a newly implemented feature, corrupt the source index or use
an old build identity. The existing gate must fail for that reason. Preserve the
failing result, restore the implementation and repeat the clean checks. Do not
replace protected baselines, weaken expected values or count a syntax error as
evidence of business-rule sensitivity.

## Run the connected project gate

```text
bo_sync.py scan --root PROJECT
change_sync.py inspect --root PROJECT
# Reconcile the candidate and review its source/graph changes.
change_sync.py verify --root PROJECT
change_sync.py accept --root PROJECT
change_sync.py check --root PROJECT
```

The agent invokes these installed scripts through the project's normal validation
command. `verify` already checks enabled source indexes, database projection,
required runtime feature cases, selected fields, state constraints and independent
business assertions. The four result categories remain mapping, state rules,
business and project checks. Missing services, parsers or evidence are failures or
unrun checks, never inferred passes.

The release suite exercises these shared mechanisms through `tests/test_code_graph.py`,
the database tests, source/feature coverage tests and viewer regressions. Each
application also supplies its domain-specific scenarios; running the Skill's own
unit tests does not validate that application.
