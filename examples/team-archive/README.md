# Team archive: independent development trial

[中文](README.zh-CN.md) · [Original review record](../../docs/review/v0.4.0/README.md)

An earlier independent conversation used the Skill from clarification through implementation, failure repair, and a size-limit iteration. The requester was simulated by AI and all data is synthetic. Original dialogues and evidence remain unchanged.

## Run

From the repository root:

```bash
python tools/archive_demo.py --port 8824
```

Install [repository dependencies](../../README.md#run-locally) first. Open the [application](http://127.0.0.1:8824/) and [graph](http://127.0.0.1:8824/graph).

Choose an operator and have another reviewer approve the current document version. Start a run with one or two slots. Both checks must pass before an immutable SQLite snapshot is saved. Deliberate delays make concurrency, waiting, and cancellation observable.

While checks run, lower the project's limit to one byte. Started work finishes; pending work waits. Restore 8192 and manually continue. Inspect body size, current limit, waiting reason, functions, and actual values. Recording begins and ends in the graph; application controls perform the operation.

## Rules

The actor must directly manage the current folder. Approvals bind project, actor, document, and content version. Any currently valid approval suffices; self-approval and the expiry instant are rejected.

Each run owns its checks and capacity. A SECRET: marker or missing title/project/document number rejects archiving. Commit rechecks eligibility in the same transaction. Snapshots are immutable and unique per version.

The project limit defaults to 8192 UTF-8 body bytes, includes equality, and accepts only positive integers. Updating the limit does not change content version or approvals. Resume and commit read the current limit.

## Development and verification

```bash
python tools/archive_demo.py --verify
python tools/verify.py
```

Follow [AGENTS.md](AGENTS.md). The AI maintains intermediate synchronization artifacts. archive_app/ owns business logic; bo_stategraph/ owns the actual state module; integrations/ connects optional observation; observer_runtime/ contains managed Skill copies. Personal layouts and notes persist in bo_stategraph/config/views/local.json.

Original accepted intent, discovery answers, and historical recordings retain their original language. Current common viewer controls support English and Chinese.

This is a local development example without production authentication or worker crash recovery. Finite scenarios do not prove every interleaving or human usability.
