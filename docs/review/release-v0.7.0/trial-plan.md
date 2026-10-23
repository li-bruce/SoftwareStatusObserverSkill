# Independent conversation trial plan

Prepared before the new conversation begins. This is a simulated user trial,
not evidence from a human usability study. The initial request and subsequent
answers will be sent through a real, separate Codex conversation using the
merged `dev` Skill. Actual messages, failures, repairs and screenshots will be
retained with the final implementation.

## User intent reserved for clarification

Build a small team document publishing application. A member signs in and
submits a titled text document. A reviewer receives an in-application message,
approves or rejects the document, and approved documents appear on a public
page. The initial request intentionally leaves “reviewer” and rejection handling
ambiguous so the Skill must confirm their meaning.

The simulated user's settled answers are:

- Use observation mode: application logic owns execution. Use Python, a simple
  JavaScript frontend and a local database; accept SQLite with SQLAlchemy when
  asked. No external mail service or mobile application is requested.
- Two seeded local test accounts have fixed member/reviewer roles. A member
  cannot review. The reviewer reviews any submitted document and may not edit
  its content. Each request checks the current actor and document state.
- A rejected document can be edited and resubmitted by its author. Published
  documents are read-only in this version. Messages are visible only to their
  recipient. An approval publishes the reviewed version exactly once.
- Preserve the confirmed scope. A question may distinguish these interpretations;
  recommending subscriptions, teams, comments or other business features is
  outside the requested application.

After the first accepted implementation, the simulated user will request one
explicit iteration: mark a message as read and show the recipient's unread
count. Repeated marking is idempotent; another user's message stays unchanged.
The new field, functions and user action must enter the same graph and checks.

## Evidence required

| Area | Evidence to retain |
| --- | --- |
| Conversation | Mode and database choices; necessary clarification/counterexample; conversation diagram and working graph URL; explicit graph confirmation before behavior implementation |
| Application | Real sign-in, submission, recipient message, denial, rejection/resubmission, approval and public content; independent database reads |
| Graph and source | Login and messaging included; function/parameter bindings; optional local and whole-code view; new/deleted source refresh and explicit unresolved targets |
| Data | SQLAlchemy model export, actual SQLite catalog, read/write targets, selected values, transformation, commit and rollback/error where applicable |
| Observation | Actual event recording and replay; observer actions create no business events; observation off/failure preserves effects |
| Iteration | Begin from accepted baseline; add the requested feature; preserve personal view state; clear old-build recording list; four separate verification reports |
| Negative checks | Intentionally missing mapping/required field and stale source/index must fail; retain the failure, restore the real implementation, and rerun without relaxing assertions |
| Delivery | Reproducible commands, screenshots, source package and actual test results; distinguish trial coverage from existing repository coverage |

Advanced hierarchy, resource/concurrency semantics, additional language adapters
and other database engines retain their independent repository tests. This
single demo does not claim to exercise every possible application architecture.
