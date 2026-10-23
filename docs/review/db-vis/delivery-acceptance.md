# Delivery example acceptance

The final candidate `501a6ec654a0b8476b70200fee75e9ffcd87d1a1a58237d0971693e93146f748` is accepted and current. The
original pre-change baseline remains
`d6139df376899cc9bfea08e6dba1c18c5ae55a61fbb3582c45dc53844a0cf7f8`.

## Result

- Implementation mapping: passed; 201 actual-value witnesses, 303 projection checks and 10 inventoried features.
- State rules: passed, including the existing concurrent checks, waiting, resource slots and joins.
- Business expectations: 96 required assertions executed, all passed.
- Project checks: all nine configured commands passed, including architecture, layout, recording and independent state-module tests.
- Acceptance and current-source check: passed.
- Fresh-copy restoration from `.release`: passed with no private working state or runtime manifest copied from the active project.

The application code, intent, machine declaration, mapping contract, whitebox
contract and business acceptance definitions retain their baseline bytes. See
[the comparison](delivery-preserved-contracts.json).

## Failure, repair and retest

1. [Initial inspection](delivery-01-initial-inspection.json) rejected the new candidate because it had no review. The original baseline was continued, and observer infrastructure was reviewed explicitly.
2. [Provisional verification](delivery-05-interrupted.md) was interrupted before completion while the shared runtime received an independently identified SQL redaction repair. No acceptance was written.
3. [The completed first verification](delivery-11-final-verification.json) passed mapping, state and business checks but failed the all-types layout fixture. The fixture treated new presentation roles such as `store` as protocol kinds.
4. [The failure detail](delivery-layout-first-failure.json) is preserved. The fixture now supplies the existing `data` or `function` kind plus `data_role`. Every original enclosure, expansion, self-relation and position assertion remains. Additional assertions check that a role name alone does not imply a data role. [The direct retest](delivery-layout-retest.log) passed.
5. Shared runtime changes invalidated earlier candidate reviews as expected. [The rejection](delivery-15-pre-review.json), [final review](delivery-final-review.json) and [reviewed inspection](delivery-16-reviewed-inspection.json) are retained.
6. [Final verification](delivery-17-verification.json), [acceptance](delivery-18-acceptance.json), [current-source check](delivery-19-current-check.json), and [fresh-copy check](delivery-20-clean-copy-check.json) all passed.

## Scope

This existing delivery application installs the shared database runtime and data
views but has no configured database catalog. Its regression confirms that the
new observer does not break the previous application or weaken its checks.
Separate database fixtures cover static catalogs, real queries, transformations,
transaction outcomes and the database viewer. The evidence above does not claim
that this legacy application itself was migrated to the new data adapter.

The published `.release` snapshot contains the accepted review, baseline,
verification, executed observations and test results for this candidate. Previous
release stages remain unchanged.
