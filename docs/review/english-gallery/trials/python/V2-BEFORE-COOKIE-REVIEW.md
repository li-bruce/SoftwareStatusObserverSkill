# Business v2: PNG-only iteration with unchanged Skill candidate 3

This is an explicitly simulated follow-up requirement, not a newly discovered
human product requirement or a human usability study. The actual delegated
messages and the actual conversation graph are retained separately from this
retrospective review. No feature other than accepted upload format was added.

## Version boundaries

| Item | Meaning | Build |
| --- | --- | --- |
| Business v1 | PNG and JPEG, pre-existing roles/review/messages/exhibition | a18c1bb36e98d314486e072c0ae90cd147780e4e279fdb3f61af714e8301e057 |
| Business v2 | Actual PNG only; JPEG and all non-PNG rejected without effects | 29f4a5735a3b9a73c094925c0fe02bbb265dbe118c8c444fa693c488c3084d2f |
| Skill candidate 3 | Frozen observer distribution used for both accepted versions | 144 files, unchanged during iteration |

V1's complete accepted receipt, source/evidence snapshot, report, expectations,
recording, screenshots, and original failures are preserved in the local checkpoint
and versioned exports. The new change uses the accepted v1 baseline
db5cf7a42b91c65c78c4f85ffbbcd509243b2853852e60afa2c094f63f799315;
it was never reset to conceal changes. V2 accepted candidate ID is
c8bb9170ac369192d35290ce0b4e46ff8c2444a0b9c58946ce9db0892aa567c0.

The initial request and independent PNG-only expectations were recorded before
changing domain behavior. discovery.changes.C_png_only_v2.previous contains the
complete old D_image decision, including its previous links. Only R_content's
business text changes. R_review is named in the change review solely to explain
the valid upload fixture migration; its requirement text and behavior are unchanged.

## Source and graph change

| Stable node | Actual implementation | v1 to v2 change |
| --- | --- | --- |
| image_check | app/service.py, Gallery.inspect_image, line 63 | Actual Pillow format PNG/JPEG acceptance becomes PNG only; JPEG still decodes and is captured as format JPEG, valid false |
| invalid_file / upload | app/service.py, Gallery.upload, line 83 | 415 error wording becomes PNG-only; rejection remains before any image/message/journal write |
| image_check / content guard | bo_stategraph/workflow.py, GalleryMachine.valid_content, line 21 | The bound drive guard permits PNG only and rejects direct JPEG submit attempts |
| upload | app/templates/upload.html | Localized hint and input accept become PNG-only; server enforcement uses actual content |

All 60 node IDs, 18 feature IDs, four persisted/initial state IDs, transition
topology, and capture schemas remain stable. Login, uploader/reviewer authority,
review decisions, messages, and exhibition queries retain their meanings.
Source inventory remains 9 files / 68 symbols. Model revision changes from
gallery-2 (business v1's historical revision name) to gallery-v2-png-only.
The Skill version is independent of that business model revision.

The parameters byte_count, valid, format, width, height, created, status and the
commit fields keep their identifiers and types. Their actual captured values
demonstrate the policy change. No new authoritative state or duplicate state
machine is introduced. The guard function binding is real and independently
tested, while the human-facing rule labels and decision history state PNG-only.

## Four separate results

| Category | Accepted v1 | Accepted v2 |
| --- | --- | --- |
| Implementation mapping | Passed; 38 witnesses / 126 projections / 18 features | Passed; 44 witnesses / 132 projections / 18 features |
| State constraints | Passed | Passed, including JPEG submit denied by actual drive guard |
| Business rules | 135/135 on/off/fault assertions | 162/162 on/off/fault assertions |
| Project checks | 11 tests + architecture | 12 tests + architecture |

All 45 original business assertions are preserved exactly. Nine independent
content assertions are added. Legacy case reject_jpeg retains its immutable
review-coverage ID and four original expectations but uses a valid PNG fixture
in v2. Actual JPEG rejection is separately named jpeg_upload_denied. This avoids
falsely representing an accepted JPEG review in v2. The original case plan, first
protected-coverage failure, repair, and retests are retained.

## Actual browser and independent evidence

The browser uploads test-reject.jpg and sees Only actual PNG images are accepted.
An independent SQLite read before any PNG upload finds zero images, messages,
and journal rows. The real reviewer UI shows no upload messages. The actual
recorded decoder output is format JPEG, valid false, width 800, height 600;
the reject event records created false and status 415.

Then test-exhibition.png is uploaded, remains publicly hidden while pending,
creates exactly one reviewer message, and becomes publicly visible after review.
Independent final SQL has one PNG, published, revision 2; one reviewer message;
and pending/published journal boundaries. Input-image SHA256 matches the stored
image digest. The real recording is 4fa667385710475d9510543ea39a6186:
58 contiguous events, two actual state frames, zero gaps. Its only HTTP rejection
is the intentional JPEG 415. No JPEG commit or notification event is invented.

Playback actually reaches step 4/4 in the state view. The ordinary-call frame
scope stays partial; missing state boundaries are still checked by the preserved
negative checker test. Observer controls add no business events. The public
complete export includes and validates both actual frames. The compact HTTP
export is not claimed to include them.

The exported v2 core is independently executed without observer modules. It
rejects JPEG with zero image/message effects, accepts PNG, hides pending images,
and publishes after approval. Deliberately unsynchronized source is rejected;
exact restoration passes. A separate SQL mutation fails for the business reason
that pending images leak publicly. No check or frozen implementation is weakened.

## Skill source and scope

Frozen source:
C:/Users/Lvi_P/Documents/Work/CF/平台软著/SoftwareStatusObserverSkill/.validation/gallery-trials/candidate-3/business-observer.
Project copy: .agents/skills/business-observer-candidate-3.
Supplied sibling-manifest SHA256:
fd022e1377b17e2679a8e1e8e0b9cbba51d1bb41c2f4af017383cc7dab1ccb8c.
Inventory SHA256:
bddfe1c7e4b25406a43b9442855004c19fdf362f5991057151c156d25e9d4eec.
All 144 files match. The candidate-3 delta from candidate 2 changes four viewer
files, one example, and recorded-analysis documentation. It fixes optional label
fallback and context-aware business/activity/raw-value display. V1's real locale,
note/layout, source, recording/replay, and explicitly derived optional-label
fixture evidence remains preserved. V2 does not patch or replace this Skill.

## Reproduction and remaining items

Use the supplied source archives/file manifests and locked dependencies. The
source packages exclude real runtime databases, personal configuration, actual
session/collector tokens, node_modules, .venv and Git metadata; they retain
synthetic PNG/JPEG fixtures and package/requirements lock files. Historical raw
personal-preference payloads remain local and are excluded from the review export;
the requested note/layout evidence is retained as screenshots and bounded results.

Run from the extracted v2 source with Python 3.12:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe -B run.py --port 8842 --database work/gallery-v2.sqlite
```

The delivered server is already running on http://127.0.0.1:8842/ and /graph;
do not start a second server on the same port. It prints both actual URLs and
closes only its own server/observer threads on Ctrl+C. No pending approval or
GitHub publication exists. These are finite project checks, not the full Skill
repository regression suite, arbitrary-path proof, or human usability evidence.
The historical isolated v1 form-token rejection cause remains unresolved and did
not recur in the final v2 flow. See the explicit failure/repair/retest index.
