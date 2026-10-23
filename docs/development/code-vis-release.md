# Code structure and release work table

Requested on 2026-10-24. Execute these stages in order. A completed stage records
its actual commit and evidence; a planned check is not a passed check.

| Stage | Work | Status | Exit evidence |
| --- | --- | --- | --- |
| 1 | Publish `db-vis` with changes and acceptance | Done; remote CI passed | `af5ae5a`, [database evidence](../review/db-vis/README.md), [five CI jobs](https://github.com/li-bruce/SoftwareStatusObserverSkill/actions/runs/40013071589) |
| 2 | Merge database work into `dev`; create `code-vis` | Done | `dev` fast-forwarded and pushed to `af5ae5a`; `code-vis` starts from that commit |
| 3 | Research and implement optional code structure, focused retrieval, whole-code view and automatic updates | Done | [Design and prior art](code-vis.md), 11 source/query/HTTP cases, [actual browser evidence](../review/code-vis/README.md) |
| 4 | Complete acceptance and merge `code-vis` into `dev` | Done; pushed; CI passed | `code-vis` at `7e80f2c`; merged into `dev` at `96f28f7`; [full regression](../review/code-vis/full-repository.log), [Git-export result](../review/code-vis/git-export-result.json), [five CI jobs](https://github.com/li-bruce/SoftwareStatusObserverSkill/actions/runs/40016953997) |
| 5 | Build and iterate a demo in a new conversation using the Skill | Done; v1, v2 and final runtime accepted | Thread `01a16a61-af8a-7881-82f5-c46f78fe533d`, "Stategraph v0.7 · 独立资料发布试用"; [visible dialogue](../review/release-v0.7.0/dialogue.md), [v1](../review/release-v0.7.0/v1-summary.md), [v2](../review/release-v0.7.0/v2-summary.md), [final upgrade](../review/release-v0.7.0/runtime-summary.md), [44 independent checks on the extracted final archive](../review/release-v0.7.0/extracted-acceptance.json) |
| 6 | Assess architecture, functionality, coupling and readability; repair and retest | Done; full regression and final five-job CI passed | `9134c61`, `e8e922e`, `1bfeb39`, `fa37289`; [assessment](../assessment/2026-10-24/README.md), [full local regression](../assessment/2026-10-24/full-retention-result.json), [latest CI](../assessment/2026-10-24/ci-final-core.json), 18 source regressions, real HTTP reload/ingestion, four database servers and browser replay/reload checks |
| 7 | Improve end-of-iteration graph checks and update the bilingual introduction | Done; browser tested | [Iteration checks](../../skills/business-observer/references/iteration-graph-checks.md), [bilingual site/browser evidence](../assessment/2026-10-24/site-final/result.json), seven perspectives, 390-pixel layout and a separate interactive walkthrough |
| 8 | Merge to `main`, publish a version and verify distribution | Candidate accepted; publication in progress | This work table on `main` receives the actual release, main SHA, CI, Pages and fixed-tag install receipts after publication. The frozen release source is already verified at `fa37289`. |

## Acceptance commitments

- Keep business confirmation in the conversation. Preserve the user's selected
  drive/observe mode and avoid adding business requirements during testing.
- Preserve the existing mapping, state, business and project gates. Source
  structure is a derived, optional view with explicit unresolved relationships.
- Keep observers out of business capture. Keep existing node identities,
  annotations, filters and positions when their meaning is unchanged.
- Record failures before repairs. Test actual runtime and browser behavior;
  distinguish a simulated user conversation from human usability evidence.
- Keep maintained code and documentation in English; retain bilingual UI and
  product copy and original historical evidence.

## Starting point

- Local database implementation: `3e18653` on `db-vis`.
- Database base: `dev` at `ab14ff7`.
- Published main before this sequence: `3e6ec3a`.
- [Database acceptance](../review/db-vis/README.md).
