# Gallery trial review: business v1, business v2, Skill candidate 3

The PNG-only iteration and bounded session-isolation repair are complete within
the declared trial scope. Original Chinese dialogue, failures and screenshots
are retained. Simulated test-role clarification is not human usability evidence.

| Result | Business v1 | Final business v2 |
| --- | --- | --- |
| Accepted formats | Actual PNG / JPEG | Actual PNG only; JPEG and other non-PNG rejected without notification |
| Implementation mapping | Passed; 38 witnesses, 126 projections, 18 features | Passed; 44 witnesses, 132 projections, 18 features |
| State constraints | Passed | Passed |
| Business rules | 135/135 on/off/fault assertions | 162/162 on/off/fault assertions |
| Project checks | 11 tests and architecture passed | 13 tests and architecture passed |
| Browser | Actual operation, 37 events, 2 frames, no gaps; locale and note/layout checks | JPEG rejection + empty reviewer inbox + PNG review/publication; 58 events, 2 frames, no gaps; actual replay reaches 4/4 |

All 45 original assertions, 60 node IDs, state IDs and capture schemas are retained.
Nine assertions are added for the explicitly confirmed PNG-only change. The legacy
reviewer-rejection case ID is documented; its v2 upload fixture is PNG. Skill
candidate 3 is the observer distribution used for both business versions, not a
business version. Its 144 frozen files remain unchanged.

## Review entrypoints

- [V1 accepted review](V1-REVIEW.md)
- [V2 final review and cookie-isolation evidence](V2-REVIEW.md)
- [V2 pre-cookie passing checkpoint](V2-BEFORE-COOKIE-REVIEW.md)
- [Actual dialogue and provenance](ACTUAL-DIALOGUE-INDEX.md)
- [Failure / repair / retest index](FAILURE-RETEST-INDEX.md)
- [Source reproduction results and instructions](SOURCE-REPRODUCTION.md)

## Download and inspect

- [V1 reproducible source](gallery-v1-source.zip) and [exact file manifest](gallery-v1-source.zip.manifest.json)
- [V2 reproducible source](gallery-v2-source.zip) and [exact file manifest](gallery-v2-source.zip.manifest.json)
- [Redacted review evidence ZIP](gallery-review-evidence.zip) and [evidence manifest](review-evidence.manifest.json)
- [V1 four reports](evidence/v1-four-reports.json), [V2 final four reports](evidence/v2-final-four-reports.json)
- [Actual final recording](evidence/v2-final-browser-recording.json), [independent final SQL](evidence/v2-final-independent-sql.json)
- [Stable IDs / parameters / source analysis](evidence/stable-id-and-source-analysis.json)
- [Complete v1 graph export](gallery-stategraph-v1.json), [complete final v2 graph export](gallery-stategraph-v2-final.json)

Both source archives were actually extracted and executed, with application and
observer available, correct format-specific effects and normal gate exit 0.
They exclude runtime databases, token state, personal configuration and node_modules;
they retain synthetic images and dependency locks. Raw preference configurations
remain local; bounded layout/note results and screenshots remain reviewable.

## Live final build

[Application](http://127.0.0.1:8842/) · [Developer graph](http://127.0.0.1:8842/graph)

Build: `389a6fb6b293dc32cfdde1f39bf71e478f4ec9af9f88b839ac539fe2cfc9db83`.
Candidate: `7d7e36bedaa3212ae9f10558420b76f1a2d813a62f0bf5b031cdbd15a3d8c9a0`.
Project: `C:/Users/Lvi_P/Documents/Codex/2026-10-23/business-observer-gallery-python`.
The launcher is `python -B run.py --port 8842 --database work/gallery-v2-final-candidate3.sqlite`.
It prints both URLs and owns only its own server/observer threads.

## Key visual evidence

- [Initial design pending clarification](screenshots/phase-01-design.png)
- [V1 business label versus raw parameter](screenshots/candidate3-pending-en.png)
- [V1 retained Chinese note](screenshots/candidate3-retained-note-zh.png)
- [Optional-label fallback, explicitly derived display fixture](screenshots/candidate3-optional-labels-fixture.png)
- [Final JPEG rejection](screenshots/v2-final-JPEG-rejected.png)
- [Final no-JPEG-message inbox](screenshots/v2-final-no-JPEG-message.png)
- [Final PNG awaiting review](screenshots/v2-final-PNG-review.png)
- [Final public PNG](screenshots/v2-final-public.png)
- [Final actual replay completed](screenshots/v2-final-replay-completed.png)

## Skill origin and limits

Frozen source is the supplied SoftwareStatusObserverSkill/.validation/gallery-trials/
candidate-3/business-observer; project copy .agents/skills/business-observer-candidate-3.
Sibling manifest SHA256:
`fd022e1377b17e2679a8e1e8e0b9cbba51d1bb41c2f4af017383cc7dab1ccb8c`.
All 144 file hashes match. Candidate 3 fixes contextual business/activity/raw
labels, optional-label fallback, and partial-frame documentation; it was not
patched during this business iteration. Earlier candidate 1/2 failures remain
historical evidence, not rewritten passes.

The same-host cookie-collision mechanism is reproduced before repair and passes
after the project-specific session namespace. Historical F06's particular cause
cannot be traced from its retained data. No known blocker remains within this
finite gallery trial. The full Skill repository suite and human usability study
were not run. No approval is pending. Nothing is published to GitHub.
