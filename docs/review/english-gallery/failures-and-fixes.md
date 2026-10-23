# Failures and fixes

This record retains observed failures. A repair is only accepted after its corresponding check passes; the final index links the final gate results.

| Finding | Correction | Evidence |
|---|---|---|
| English UI changed a test's expected label. | Update the exact display expectation; retain the same behavioral assertion. | 01-view-regression.log, 06-view-regression-retest.log |
| An installed projection was stale after a template change. | Regenerate managed copies from the canonical source. | 07-refactor-retest.log, 11-core-refactor.log |
| Windows upgrade metadata used mixed path separators. | Normalize portable relative keys, reject conflicting digests and unsafe paths. | Protocol/source regression and independent Python trial defect D01 |
| Chained Python calls shared a source location and collided. | Distinguish expression content and occurrence in reconciliation IDs. | Protocol/source regression and independent Python trial defect D02 |
| The opening dialogue did not include its business graph. | Add `bo_design preview`, sharing discovery IDs/revision with Web, and require the inline diagram plus a verified URL. | 13-design-preview.log and trial dialogue records |
| Native project envelopes failed in design focus. | Read them through the shared model loader. | 12-source-protocol.log and independent Python trial defect D04 |
| A valid model omitted optional state labels and the viewer crashed. | Fall back to the raw phase identifier. | 17-replay.log and candidate-3 browser trial |
| Business `pending` was displayed as the generic activity label “Not started.” | Use project labels for business phases, activity labels only for activities, and preserve raw parameter values. | 17-replay.log and candidate-3 browser trial |
| Old/new service comparisons did not translate composed wait reasons. | Normalize only fully recognized, reviewed reason compositions; all fields, states, values, resources and effects remain compared. | 15-service-parity.log, 22-service-parity-retest.log |
| A graph test loaded only one module after localization introduced imports. | Resolve its local module dependencies in the test loader. | 19-archive-view.log, 23-archive-view-retest.log |
| A one-off translation script accidentally converted the `__proto__` test string to an object. | Require own dictionary keys in the translator and restore the exact original special-ID assertion. | 20-layout.log, 24-layout-retest.log |
| Translating a seeded document changed accepted business data. | Restore the original bytes in a separate seed-data JSON resource; retain the original acceptance assertions. | 26-team-archive-full-gate.log and subsequent full-gate retest |
| The small Python modes example retained old source fingerprints after translation. | Regenerate its declaration/source manifest, then run all six independent mode and drift checks. No freshness check is disabled. | 32-full-suite.log, 35-python-modes-regenerate.log, 36-python-modes-retest.log |
| The native demo launcher stopped business startup if the observer failed. | Start the application with capture disabled, clear stale transport settings, and keep it alive if observation later stops. | tools/test_demo_launcher.py and final full suite |

The seeded-data failure is a concrete separation of results: mapping, state constraints, and project checks passed while business checks failed. No acceptance expectation was changed to accommodate that failure.

## Language migration boundary

Maintained instructions, source comments, diagnostics, demo presentation and default documentation use English. Chinese locale catalogs, UTF-8 byte-length cases, deliberately non-English graph-label tests, original user-authored labels, accepted requirements, sample document data, and historical evidence retain their original text. See 29-language-audit.json.

Candidate-3 is frozen and was used independently in both new chats. The final canonical SKILL.md additionally removes one trailing blank line; executable Skill code and viewer assets are unchanged from that frozen candidate unless explicitly noted in the final manifest comparison. Example fixes and product documentation are outside the frozen Skill package.
