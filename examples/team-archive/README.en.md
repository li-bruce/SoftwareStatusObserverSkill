# Team archive: independent development trial

[中文](README.md) · [Review record](../../docs/review/v0.4.0/README.md)

Built in a new conversation using business-observer, from requirement clarification through implementation, fixes and a dynamic size-limit iteration. The requester was simulated by AI; all data is synthetic.

## Run

From the repository root:

```bash
python -m pip install -r examples/delivery/requirements.txt
python tools/archive_demo.py --port 8824
```

Open the [application](http://127.0.0.1:8824/) and [developer graph](http://127.0.0.1:8824/graph). Python 3.11–3.13 is required; validation also needs Node.js 20+.

Choose an operator and have another reviewer approve the current document version. Start a run with one or two checking slots. Both checks must pass before an immutable SQLite snapshot is saved. Checks deliberately take four seconds for observation.

While a check is running, lower the project limit to one byte. Started work finishes; pending work waits. Raise the limit to 8192 and explicitly continue the run. The graph shows the size, limit, waiting reason, parameters and source.

Expand and search nodes, inspect source, drag or pin positions, and edit display names and notes. Preferences persist in the same browser. Compare the frozen first version with the current version. Current project settings and historical decision values are labeled separately.

## Rules and verification

This example requires the current folder's direct manager. Approvals bind project, operator, document and content version; any currently valid approval suffices. Self-approval is rejected, and the expiry instant is excluded.

Each run owns its two checks and capacity. `SECRET:` in the body, or missing title, project or document number, rejects archiving. Submission rechecks eligibility in the same SQLite transaction. Snapshots are immutable and unique per document version.

The project limit defaults to 8192 UTF-8 body bytes, includes equality and accepts only positive integers. Changing it does not change the content version or invalidate approvals. Continue and commit read the current limit.

```bash
python tools/archive_demo.py --verify
python tools/verify.py
```

The agent follows [AGENTS.md](AGENTS.md) when changing the project; users need not manage intermediate synchronization files. `archive_app/` owns business execution, `integrations/` adapts observation, and `observer_runtime/` holds pinned Skill tools. `review/` retains actual dialogues, preimplementation expectations, failures, repairs, results and screenshots.

The public copy omits databases, scratch runs, duplicate extracts and whole-project ZIPs. Source snapshots, review records and core ZIPs remain; see the [copy manifest](review/publication-copy.json). Original candidate paths in historical records describe the trial environment.

This is a local development example without production authentication or crash recovery for workers. Finite scenarios and agent-operated browser checks do not prove every possible interleaving or human usability.
