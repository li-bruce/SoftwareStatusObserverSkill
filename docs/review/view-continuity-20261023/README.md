# View continuity acceptance — 2026-10-23

Branch: `dev`. Scope: personal view continuity, current-version recording lists, complete folded graph presentation, and an inventory of deeper source/data/API support.

## What changed

Personal settings use the stable project identity. Type filters, individually hidden nodes and relations, expansion, positions, pins, camera, notes, and custom views survive graph updates. Explicit node/edge aliases carry settings through declared renames. Newly visible nodes receive positions while existing coordinates remain fixed.

The all-elements action clears exclusions without rearranging or opening groups. Cross-group static calls now remain visible on their containing regions. Counts distinguish visible, folded, and filtered elements. A source line shift no longer changes a static call ID.

Recordings are scoped to code and model identity. An updated graph clears the current list and exits obsolete replay; same-version restarts retain recordings. Original private JSON files remain on disk. Frozen review records are preserved.

## Failures, fixes, and retests

| Finding | Change | Evidence |
|---|---|---|
| Individual node/relation exclusions were absent; layout fallback could depend on a display title. | Add individual exclusions and stable project keys, with explicit legacy-key migration and conflict preservation. | [View regression](03-view-regression-retest.log), [browser data](11-browser-evidence.json). |
| Collapsing a group suppressed static calls; root hints could omit state/new-feature nodes. | Retain original cross-group relations and include all root identities. | [View regression](03-view-regression-retest.log), [folded screenshot](10-all-elements-folded.png). |
| Recordings from any build appeared together; replay could keep displaying an old graph. | Match build/model identity in list/get/capture and exit incompatible replay. | [16 recording checks](02-recording-regression.log), [browser checks](13-browser-check.json). |
| The new JSON persistence test compared object prototypes as well as serialized values. | Compare the actual serialized contract; retain all position, exclusion, and custom-view assertions. | [Initial test failure](01-view-regression.log) → [passing retest](03-view-regression-retest.log). |
| The Windows sandbox rejected the default temporary directory in the new source-ID test. | Use a project-owned temporary directory; keep the same identity and repeated-call assertions. | [6 source checks](04-source-identity.log). |

## Browser acceptance

The browser used [an isolated fixture](../../../tools/view_continuity_demo.py) with the unchanged production viewer, project preference service, and recorder. Its upgrade control changes synthetic graph/build data. It is a repeatable UI acceptance case, not a new full application trial.

1. Show all elements and expand groups. Hide State nodes and State transition edges.
2. Hide the Check permission node and one specific static call. Move a node and its containing group; pin the group. Save “My review.”
3. Start recording, perform an operation in the test application, stop, and enter replay.
4. Upgrade the graph while replay is open. The viewer returns to live mode and the old recording disappears. A new Save receipt function appears.
5. Compare existing coordinates, pin flags, and expansion before/after the update and after browser reload: all four existing visible nodes match exactly. Hidden content and the selected custom view remain.
6. Select All elements, then Collapse all: **8 nodes = 4 visible + 4 folded; 6 relations = 4 visible + 2 folded; 0 filtered nodes or relations.** Browser console errors/warnings: 0.

[Before update](08-before-update.png) · [After update](09-after-update.png) · [All elements folded](10-all-elements-folded.png) · [Chinese interface](15-all-elements-zh-CN.png) · [Recorded data](11-browser-evidence.json) · [Data assertions](13-browser-check.json)

Reproduce with `python tools/view_continuity_demo.py --port 0`. Open the printed URL; application controls are at `/control`. Use a fresh `--directory` for an independent run. Test data stays under `.validation` by default.

## Application and repository checks

Both shipped examples use the normal begin → scan/review → verify → accept → check workflow. Their original business requirements and test expectations are unchanged.

| Example | Mapping evidence | Business expectations | Result |
|---|---|---|---|
| Delivery | 201 value witnesses; 303 projection checks; 10 features | 96 / 96 executed | Mapping, state rules, business, project checks passed. |
| Team archive | 480 value witnesses; 1,113 projection checks; 22 features | 189 / 189 executed | Mapping, state rules, business, project checks passed. |

[Review generation](05-review-generation.log) · [Verification](06-example-verification.log) · [Acceptance](07-example-acceptance.log) · [Frozen acceptance summary](17-example-acceptance.json)

Full repository regression **passed** with exit code 0: [12-full-suite.log](12-full-suite.log). This includes strict declarations, dialogue gates, mapping, observer isolation, Python/Node/React/Vue adapters, HTTP integration, installation, both examples, and executable observer-free exports. [Formatting](14-format-check.log) and [documentation links](16-document-links.log) passed. The [staged byte check](18-staged-input-byte-check.json) matched all 405 accepted input and shipped adapter files.

## Boundaries

Full source neighborhoods, generic database schema, and typed API relationships are tracked in the [dev roadmap](../../development/dev-roadmap.md). Existing AST and route extraction are useful foundations but do not establish those complete layers. Dynamic call targets remain explicit unknowns. Identity conflicts are retained rather than guessed; repeated identical calls can still require explicit migration after insertion/reordering.
