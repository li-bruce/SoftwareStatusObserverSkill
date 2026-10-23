# Code structure and release work table

Requested on 2026-10-24. Execute these stages in order. A completed stage records
its actual commit and evidence; a planned check is not a passed check.

| Stage | Work | Status | Exit evidence |
| --- | --- | --- | --- |
| 1 | Publish `db-vis` with changes and acceptance | In progress | Database review, remote branch SHA and CI result |
| 2 | Merge database work into `dev`; create `code-vis` | Pending | Branch ancestry and clean working tree |
| 3 | Research and implement optional code structure, focused retrieval, whole-code view and automatic updates | Pending | Design, regression failures/repairs, browser evidence and strict source checks |
| 4 | Complete acceptance and merge `code-vis` into `dev` | Pending | Full suite, installed-copy/Git-export checks and merge SHA |
| 5 | Build and iterate a demo in a new conversation using the Skill | Pending | Actual simulated dialogue, implementation, screenshots and acceptance |
| 6 | Assess architecture, functionality, coupling and readability; repair and retest | Pending | Findings tied to source, changes and repeated tests |
| 7 | Improve end-of-iteration graph checks and update the bilingual introduction | Pending | Executable checks, Skill guidance and actual site review |
| 8 | Merge to `main`, publish a version and verify distribution | Pending | Release, main SHA, CI, Pages and fresh-install evidence |

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
