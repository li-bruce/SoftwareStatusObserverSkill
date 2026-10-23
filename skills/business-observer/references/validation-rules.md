# Executable validation rules

Combine general checks, domain rules, and project scenarios. Select applicable dimensions; unrelated projects need not implement every category.

| Dimension | Define | Execution and evidence |
|---|---|---|
| Types and functions | Parameter type/range/unit/identity; input-to-return relations | Static signatures and white-box fields |
| Decisions | AND/OR/exclusion, propagation scope, unknowns, short circuiting | Allow/deny cases; independently varied conditions; actual evaluation events |
| Data relations | Direction, direct/transitive scope, read completeness, data version | Synthetic relationships, independent expectations, actual reads/storage |
| States and sequences | Legal transitions, waiting, recovery, cancel, retry, idempotency | Compare model and application; operation sequences and invariants |
| Concurrency/resources | Same-run join, capacity, acquire/release, run isolation | Real barriers/scheduling, complete configurations, authoritative effects |
| Commit | Validity of evidence, transaction protection, failure without effects | Controlled commit-window interleavings, conflicts, chosen atomicity mechanism |
| Observation | Off/fault preserve behavior; correct identities; no invented missing data | On/off/fault cases, missing-probe and incorrect-field injection |
| Graph and changes | Types/directions preserved, traceable boundaries, no stale evidence | Focus graph checks, change_sync, actual drilldown |
| Test sensitivity | Broken rules fail for the relevant business reason | Isolated mutations, unchanged expectations, expected-failure assertions |

Record each rule's source, applicability, input/operations, expected property, evidence location, checker, and version. Graph, tests, and implementation may share enums/IDs. Expectations must not call the decision under test to calculate the answer.

Before loading, validate definitions, types, supported transition semantics, and actual engine wiring. Invalid definitions raise errors. Invalid runtime facts retain actual values and fail state/business checks. Mapping reads delivered projections through the [protected contract](mapping-contract.md); retain original `mapping_checks`.

Report `mapping`, `state_rules`, `business`, `project_checks` separately. Compare independent storage values, function inputs/outputs, or recipient identities against unified instance queries and probes. Duplicating the same projection is not independent evidence. Business tests use predetermined expectations; project checks include architecture/UI. A correctly mapped program bug may pass mapping but fail rules. Showing an invalid program as normal must also fail mapping.

For complex conditions, borrow [MC/DC](https://swehb.nasa.gov/plugins/viewsource/viewpagesrc.action?pageId=180584662): where feasible, vary each condition independently to change the decision. State coupling and uncovered combinations; ordinary branch tests are not automatically MC/DC. Consider [NIST combinatorial testing](https://csrc.nist.gov/pubs/ir/7878/final) and [Hypothesis stateful testing](https://hypothesis.readthedocs.io/en/latest/stateful.html). These coverage methods do not choose business rules for the user.

Distinguish concurrency safety from progress under stated assumptions. Retain fairness, timeout, and external-service assumptions. Finite tests do not prove all schedules. Petri-style resource, wait, and join semantics belong in the application's existing state configuration, not a separate authoritative analysis layer.

Choose mutations relevant to the changed rules: wrong propagation scope; missing tenant/version; `<` changed to `<=`; AND changed to OR; removed exclusion; early join; leaked resource; missing probe; wrong input; mixed runs. See [authorization patterns](authorization-patterns.md). Test valid inheritance too; multi-hop is not inherently wrong. Syntax errors, hash changes, or startup failures do not establish semantic test sensitivity. Mutate isolated copies and preserve the final clean run.

`whitebox_contract.py` does not prove complete data flow or generate exhaustive MC/DC, combinations, or schedules. Implement real domain tests and disclose selected coverage and remaining gaps.
