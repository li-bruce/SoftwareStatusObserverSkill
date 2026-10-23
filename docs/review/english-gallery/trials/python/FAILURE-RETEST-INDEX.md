# Failure, repair, and retest index

Historical evidence is retained verbatim. This index reports current scope without
rewriting the earlier reports. Raw command records include argv, cwd, exit code,
stdout, and stderr under commands/. Screenshots and AX snapshots are separate.

| ID | Failure | Repair / current status | Evidence and retest |
| --- | --- | --- | --- |
| D01 | Candidate-1 Windows metadata path keys | Public candidate 2 fixed | skill-defects.md; 62-65; 102/107 C3 independent hashes |
| D02 | Candidate-1 chained-call question ID collisions | Public candidate 2 fixed; old answers rejected | 66; original/regenerated reconciliation; 103/105 current 81 answers |
| D03 | Optional machine.labels causes viewer failure | Public candidate 3 fallback verified | candidate3-optional-labels-fixture.json and browser TXT/PNG; explicit derived display fixture |
| D04 | Public focus fails on project envelope | Public candidate 2 fixed; compatibility helper archived | 71/77; 112 current public focus |
| G01 | Initial conversation lacked inline diagram | Same stable network added, no fabricated confirmation | confirmed-network.mmd; phase reports and public preview 77 |
| D05 | pending business state displayed as generic activity Not started | Public candidate 3 context-aware display verified | candidate2-pending-label-defect TXT/PNG; candidate3-pending-en/zh and review-en TXT/PNG |
| F01 | Interpreter/ensurepip Temp failures | Workspace TMP/TEMP and venv | failures.md; commands 01/01b/01c; subsequent gates |
| F02 | Early server lifecycle/reachability failures | Hosted foreground server verified; exact early cause unresolved | failures.md original startup evidence; 111 actual startup plus both HTTP200 |
| F03 | Adapter omitted journal | Empty journal plus actual revisions returned | original failure screenshot/log; 106 tests; current browser |
| F04 | Ownership managed hashes absent | Independently verified explicit seal; check retained | 35/36; 101/102/107; 106 architecture |
| F05 | Ordinary calls diagnosed as missing frames | partial=true; missing actual state frame still rejected | original 41-event record; negative checker fixture; 106 test; final 37-event record has no gaps |
| F06 | One initial reviewer login token rejection | Retry succeeded; cause unresolved, no claimed fix | original screenshot/AX/record; clean final C2 and C3 browser flows |
| F07 | Frame current summary null | Same transactional row supplies phase and current | original record; 106 exact-frame tests; final 2 frames and independent SQL |
| F08 | Hosted PowerShell redirection files empty | Python tee retains actual main-server output | original empty logs and failed assertion retained; 88/111 tee logs |
| U01 | First candidate-2 frozen-copy sandbox denial | Authorized escalation installed new independent copy | commands 61-64; no security settings changed |
| C301 | Strict whole preferences object comparison failed | Revision 30 to 31; all entries exactly equal | before-upgrade vs candidate3-preferences-before-browser; current upgrade report |
| C302 | Initial textual diff included false newline differences | Compare decoded original bytes on both sides | helper patch; 102 vs 107; final diff contains only four files |
| S01 | Exploratory PowerShell rg wildcard path/missing receipt filenames | Use directory glob or actual inventory | Tool transcript; no project/business gate affected |
| S02 | CIM process inspection denied by environment | No retry or permission weakening required | Tool transcript; known owned server sessions used |

Candidate-3 commands 95-116 retain passing precheck, change workflow, independent
hash checks, full verify, accept/check, core export/challenges, and actual collection.
Candidate-2 upgrade record's earlier pending paragraph is historical; its final
status was partial on D05. Candidate-3 final scope supersedes it as described in
candidate-3-upgrade.md, while candidate-1/2 checkpoints remain immutable evidence.


# v2 failures, repairs, and retests

## V201: Deliberate pre-implementation requirement counterexample

Command 122 executed the v2 JPEG expectation against the still-v1 implementation.
It failed with exit 1: expected images 0, actual 1. This demonstrates the requested
behavior change; it is not a defect in v1's confirmed PNG/JPEG contract. Command
123 passed after the actual decoder policy and drive guard changed. After the
coverage repair, command 138 verifies the independently named JPEG-only scenario
with zero images/messages and status 415.

## V202: Protected reviewer fixture coverage

Inspect command 127 returned exit 1 with review_errors.weakened_feature_coverage
for review/cases/reject_jpeg/commit. Existing v1 feature records lack explicit
feature-level requirements, so the recorded requirement-change allowance does
not waive this immutable coverage obligation. No frozen checker was changed.

Repair: preserve legacy case ID reject_jpeg and all 45 original assertions
exactly; its valid upload fixture is PNG in v2. Add jpeg_upload_denied for actual
JPEG rejection and jpeg_spoof_png for JPEG bytes with a PNG filename. Nine
independent assertions are added. This is explicitly documented fixture migration,
not evidence of a JPEG image being reviewed in v2. Initial planned expectations
and acceptance are retained as initial-*-before-coverage-repair.json. The original
v1 expectations remain unchanged. Inspect 131 and final inspect 135 pass;
full verify 136, accept 139, and ordinary gate 140 pass.

## V203: UI automation selector mismatch and intermediate snapshots

The browser wait for exact DOM text valid: timed out with no matches even though
the accessibility tree subsequently showed valid: false and actual JPEG content.
The field is split among presentation elements. Fresh AX inspection resolved
the test locator issue; no application or Skill repair was made. Confirmed
evidence is replay-JPEG-decision-confirmed.txt and the matching confirmed PNG.
The earlier replay-JPEG-decision snapshot/screenshot represents an intermediate
initial frame and is retained, not used as proof of the JPEG decision. The first
JPEG upload AX snapshot similarly preceded navigation; browser-jpeg-rejected-final
and the actual rejection screenshot are the settled evidence.

## V204: Read-thread argument limits

The first read_thread request used turnLimit 20 and maxOutputCharsPerItem 24000;
the tool rejected those arguments (limits 10 and 20000). A corrected read succeeded.
Only actual user-facing messages and exact targeted delegation prompts are
exported. Private reasoning and unrelated conversations are excluded. The tool
does not provide user messages inside child turn.items; this limitation is stated
instead of reconstructing absent dialogue. The original instruction/answer files
and parent delegation tool export supply those primary records separately.

## Final retests

Four reports pass: mapping 44 witnesses / 132 projection checks / 18 features;
state constraints; business 162/162 assertions; project 12 tests plus architecture.
The actual browser record has 58 contiguous events, two matching state frames,
and no gaps. The only HTTP error is the requested JPEG upload rejection (415).
Independent SQL before PNG: images/messages/journal all zero. After PNG approval:
one PNG published at revision 2, one reviewer message, two journal boundaries.
Browser playback actually reached the last of four state-view steps.

Core export and source-drift/mutation challenges pass in command 146. Original
v1 failures and their unresolved diagnoses remain in the prior failure index;
none is silently reclassified as a new fix. In particular the old isolated form
token rejection cause remains unknown and did not recur in this final v2 flow.


# Session namespace mechanism: reproduced, repaired, and bounded

The parent explicitly requested a bounded same-host/different-port interference
probe. This does not add a product feature. It is separate from diagnosing the
historical F06 reviewer-login rejection.

Before repair, real HTTP requests against two independent Flask applications on
random loopback ports produce: gallery control login successful; other application
sets its own default session; gallery's old form returns 400. Command 149 and
v2/cookie-mechanism-before.json retain that actual result without cookie or token
values. The gallery's CSRF check remains active.

The production change is one configuration field in app/web.py:create_app:
a project-specific SESSION_COOKIE_NAME. HTTP-only and SameSite settings remain.
The same real requests now succeed (command 150). Source inspection 154 and
verification 155 then correctly reject an excluded application entrypoint in the
test peer; state, business and project checks in 155 are not_run, not passed.

The regression peer was made an explicit independent WSGI test fixture that
serves a genuinely signed session from a separate Flask application. It defines
no gallery route or business feature. Its source is explicitly watched. It still
writes the foreign cookie over real HTTP and uses CookieJar's ordinary host/port
handling. Command 156 succeeds with the repaired application. Command 162 executes
the same current peer against SHA-verified pre-repair core code and reproduces
400, supporting that the fixture refactor did not remove the interference.

No cookie/header/token values are emitted or saved. Probe records contain only
paths, methods, status, final path, namespace equality, and independent row counts.
All test servers are owned by the probe and shut down with joined threads.

Rebound source, scan and inspect (157-160), full verify (161), accept (163), and
ordinary gates (164/169) pass. All original business assertions and tests remain;
the new actual-HTTP regression brings project tests from 12 to 13. Mapping is
44 witnesses / 132 projections / 18 features; business is 162/162; state and
architecture checks pass. Stable business IDs and capture schemas do not change.

The final browser repeated JPEG rejection, independent zero-row/no-message checks,
the reviewer empty inbox, PNG pending plus one message, reviewer login/approval,
and public display. Its current record has 58 contiguous events, two real state
frames and no gaps; the only HTTP error is the intentional JPEG 415. Actual replay
reaches 4/4. Final build:
389a6fb6b293dc32cfdde1f39bf71e478f4ec9af9f88b839ac539fe2cfc9db83.

Conclusion: this cookie-collision mechanism is reproduced and repaired in the
bounded test. F06's historical root cause cannot be traced from the retained
evidence because its contemporaneous cookie state was not collected. No claim
is made that this proves F06 was caused by the same mechanism. Pre-repair passing
v2 receipts, raw recordings and screenshots are preserved unchanged.
