# Node.js gallery trial review

Application v1 and v2 both passed the four required categories using the frozen Skill candidate-3. Version v2 is an explicitly simulated **PNG-only** requirements iteration; the original separate-login and mutual-review answers remain authoritative. No GitHub publication occurred.

| Check | Application v1 | Application v2 |
|---|---|---|
| Implementation mapping | Passed: 11 features, 68 observed events, 12 witnesses, 51 projection checks | Passed: 11 features, 75 observed events, 15 witnesses, 63 projection checks |
| State constraints | Passed | Passed |
| Business rules | 48/48 assertions executed | 63/63 assertions executed |
| Project checks | Passed | Passed; final `npm test` passed |

The assertions run with observation on, off and failing. A separate queue-capacity-one execution retained the same business outcomes. These numbers are executed assertions and selected witnesses, not a percentage of all possible behavior.

## Current runnable result

- [Application](http://127.0.0.1:53700/)
- [Observer graph and replay](http://127.0.0.1:57136/graph)
- Build: `1311bfdbaf3c39dd1b3e61713ae0eedf2b9dd26ce1040fb7c858566fa441fdbc`
- Accepted candidate: `56cf88e8bc27370be0e8725beb975948ee1350e9ecb7b224a832935d2064cffd`
- Run from project root: `npm run dev`; stop this launch: Ctrl+C or `python tooling/dev.py --stop`. The next launch prints new actual ports.
- Synthetic local accounts: `alice` and `bob`, password `[REDACTED_CREDENTIAL]`; equal upload/review permissions, no self-review.

The final live build matches the accepted manifest and the graph binding is current. The existing three exhibited images include preserved prior test data. PNG-only policy governs new uploads; earlier accepted images are not retroactively reclassified.

## v1 evidence entry

Preserved full verification: `review/v1/c3-verification.json`; accepted receipt: `review/v1/c3-accepted.json`; original change: `review/changes/causal-capture-iteration/`. Business request/model snapshots are retained in `review/v1/`.

The real browser recording `135acb7323ec42c3b5cc0ec6f3278740` contains **36 events** and exact frames `received → pending_review → published`. Alice uploaded and Bob approved; independent storage agrees. Audit: `review/v1/browser-audit.json`; original recording: `review/v1/browser-recording.json`. Errors/dropped: 0/0. Viewer controls added zero events. A later isolated run of the **unchanged preserved v1 core** confirmed JPEG was accepted and notified Bob (`review/v1/jpeg-baseline.json`); its run date is later, its source is v1.

Screenshots: [v1 pending replay](v1-replay-pending.png), [v1 approved replay](v1-replay-published.png), [v1 exhibition](v1-gallery-candidate3.png), [English viewer](v1-replay-en.png). Switching language reloads the viewer to live mode; the English screenshot is a live viewer, not an English replay claim.

## v2 evidence entry

Full verification and acceptance: `review/changes/png-only-v2/verification.json` and `accepted.json`; final normal gate: `review/commands/100-v2-normal-gate.json` / `.log`. Machine-readable category results: [check-results.json](check-results.json).

The real browser recording `a05325bf62504bbb8fab37bb190385e2` contains **41 events** and exact frames `received → invalid_file → received → pending_review → published`. JPEG was readable but rejected, generated no message and saved no exhibition file. A separate PNG upload generated Bob's sole pending message and was approved. Audit: `review/v2/browser-audit.json`; full actual recording: `review/v2/browser-recording.json`; final live/zero-control-event check: `review/v2/final-live-check.json`. Errors/dropped: 0/0.

Screenshots: [JPEG rejected](v2-jpeg-rejected.png), [actual JPEG decision](v2-replay-jpeg-decision.png), [only PNG awaiting review](v2-png-review-message.png), [PNG pending replay](v2-replay-pending.png), [approval replay](v2-replay-published.png), [exhibition](v2-gallery.png).

Stable business/state IDs remain `upload`, `image_check`, `invalid_file`, `pending_review`, `upload_message`, `display_review`, `published`, and `not_displayed`; all account and other workflow IDs remain. `app/domain.mjs::decodeImage` now obtains actual original format, fully decodes, and returns separate `readable`, `original_format`, and `accepted`. The `image_check` node captures these fields. `upload` passes actual acceptance to the declaration's `validate.valid` payload and commits messages only for accepted PNG. The state enum/context shape is unchanged. `imageBytes` also rejects `invalid_file`, including readable-but-disallowed JPEG. Discovery D2 keeps its complete prior object under `changes[].previous` with the simulated request source. No earlier assertion or requirement outside R2 was removed.

## Skill provenance, dialogue and failures

Candidate-3 was independently copied from `SoftwareStatusObserverSkill/.validation/gallery-trials/candidate-3/business-observer`, 144 files. The adjacent upstream manifest SHA256 is `fd022e1377b17e2679a8e1e8e0b9cbba51d1bb41c2f4af017383cc7dab1ccb8c`. Installation manifests and original candidate-1/2 evidence remain in `review/`; original frozen copies were not patched. Public upgrade/reapply passed. The optional-label / business-phase / activity-phase / raw-value regression passed. This project's machine omits optional `labels` and remains operational; it does not itself contain a business state literally named `pending`.

Actual browser language switching passed. Layout SHA256 stayed exactly `540ed4f19f559d58d4832a351e15bc83db932cfa621aed9a5b2620bbfe3fd019` across idempotent public upgrade; the real saved login note survived reload: [note screenshot](candidate3-note-preserved.png). A local service subclass retains the original project layout identity; this adaptation is in `integrations/bo_service.py`.

- [Actual dialogue export](actual-dialogue-export.json): source-provided user/assistant messages and available clarification calls, extracted from the chat. Reasoning and tool outputs are excluded. This is a selective actual export, not a reconstructed transcript. Clarification reply payloads preserve their exact question and answer text. Initial delegated brief remains `review/original-brief.txt`.
- [Coordinator messages verbatim](coordinator-messages-verbatim.json): exact sent tool arguments with IDs, including clearly identified simulated confirmations/changes. These do not override original human account-permission answers. Initial `review/conversation.json` is an authored requirements record, not a verbatim chat export.
- [Later coordinator updates verbatim](coordinator-updates-verbatim.json): additional source messages, including the later handled-approval instruction.
- [Failure / correction / retest index](FAILURES-AND-RETESTS.md): links command IDs to original failures, environmental interruptions, corrections, negative tests and passing retests. Raw outputs are under `review/commands/`; none were replaced by a passing summary.

## Reproduce / inspect source

[Sanitized evidence archive](gallery-trial-evidence.zip), [archive digest and redaction index](evidence-package-manifest.json). The archive contains exact original command logs, v1/v2 recordings and independent audits, dialogue exports, review records and selected screenshots. Its internal `EVIDENCE-MANIFEST.json` is an explicit file whitelist with both original and distributed hashes. Credential-bearing embedded source snippets are redacted only in distribution copies; local original evidence remains intact. Runtime library trees, scenario working copies, databases, credentials and personal configurations are excluded. Raw command log bytes are unchanged. The existing source ZIP is unchanged.

[Full v2 source package](gallery-v2-source.zip), [exact source file list and hashes](source-files.json), [package SHA256](source-package-sha256.json). The package includes code, public runtime/viewer, frozen candidate-3, locks, synthetic fixtures, maintained contracts and accepted audit metadata. It excludes node_modules, runtime databases/store, sessions, collector token, personal views/config and historic test data. It does not include the local Python package target; install it with the supplied pinned requirements. See packaged `README.md` for setup, joint start, recording and checks.

The clean **core-only exports were executed**, including deliberate mutation detection: [v1 core](gallery-core-candidate-3.zip), [v2 core](gallery-core-v2.zip). In a core export run `npm ci` then `node app/server.mjs`; the full observer development command applies to the full source package. The full source ZIP is hash/inclusion checked; a separate fresh dependency installation from that ZIP has not been claimed.

Required scope is complete. This is local synthetic integration testing, with no human usability or production identity claim. Dynamic/external call reconciliation has explicit selected-case boundaries. Queue-limited test shutdown can emit socket-reset diagnostics; those are preserved in raw stderr, while healthy live recording reports zero collector errors and drops. The first implementation batch predating the first successful baseline remains an explicit historical process limitation.
