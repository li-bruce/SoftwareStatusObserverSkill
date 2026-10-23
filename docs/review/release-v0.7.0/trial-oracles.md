# Independent trial expectations

These expectations follow the predefined simulated user intent and actual scope
confirmation. They are written before examining implementation results. The
trial's graph and runtime output are observations, not the expected answers.

| ID | Operation or counterexample | Expected business result | Required graph evidence |
| --- | --- | --- | --- |
| T01 | Open the public page without signing in | Only approved publication snapshots are visible | Public query and selected returned identifiers |
| T02 | Sign in as the seeded member/reviewer | Correct actor role; invalid credentials do not authenticate | Login decision and result; no password, token or session secret in capture |
| T03 | Member submits title and text, version 1 | One pending document and a message for the reviewer | Submission, actual parameters, state change and committed message |
| T04 | Member attempts review | Rejected; document and publication storage unchanged | Actual denial, current actor/state and no write effect |
| T05 | Reviewer rejects the pending version | Rejected state, no public snapshot | Review decision and state transition |
| T06 | Reviewer tries to edit the author's rejected content | Rejected; content unchanged | Ownership decision linked to the real method |
| T07 | Author revises the rejected document and resubmits | Same document identity, newer content version, pending again | Revision/resubmission path and actual version values |
| T08 | Reviewer approves an old version after revision | Rejected; no publication | Expected/current versions and failed check |
| T09 | Reviewer approves the current pending version | Exactly one snapshot of that version's title and text | Read, selected transformation, commit, approved state and public effect |
| T10 | Repeat review or attempt to edit the published document | Rejected; no duplicate publication or content change | Actual rejection and unchanged effect count |
| T11 | Open another recipient's message | Rejected or absent from the actor's own list | Recipient check and actual query result |
| T12 | Compare observation on, off and failing | Same authoritative business effects | Missing observations labeled as missing; no fabricated success |
| T13 | Browse graph/source, move nodes, start/stop recording | Business rows unchanged; controls add no business events | Exact excluded observer operations and recorded real application action |
| T14 | Requested iteration: recipient marks a message as read | Own unread count decreases once; repeated marking is idempotent | New feature, field, function, parameters, database write and state/value changes |
| T15 | Another actor marks that message | Rejected; read value and recipient count unchanged | Denial and independent database comparison |
| T16 | Add implementation but omit its mapping or required capture field | Iteration acceptance fails | Independent source inventory and required-field diagnostic |
| T17 | Change source or alter a saved code graph without maintenance | Mapping/code check fails | Stale or changed content identified, without repair inside verification |
| T18 | Complete an accepted code/model update | Current graph and events use the new identity; old recordings leave the current list | Saved layout/notes/filter continuity and fresh recording |

Some scenarios may be covered by one combined real operation. The final report
must point to executed evidence for each applicable row and explicitly identify
any row left unrun. An HTTP success alone does not establish the expected data
or observation result.
