# Team archive development rules

This is a developer-debugging example with synthetic data. The application architecture, framework, and coding method remain open.

Before each relevant iteration, read the repository Skill at `../../skills/business-observer/SKILL.md`, intent.json, discovery.json, behavior.json, and the current validation result. When copying this example separately, install the same Skill revision and update that path. Preserve confirmed rules and stable node IDs. Observation and verification must be maintained during development.

First launch uses `python tools/archive_demo.py --prepare-only` from the repository root to restore the published acceptance record. It does not accept edited content. Continue an unfinished change; never replace its baseline to hide omissions.

Before changing behavior, record the actual request and requirement IDs explicitly allowed to change:

```bash
python observer_runtime/change_sync.py begin --root . --change .stategraph/my-change --request "Actual request" --requirements R14
```

Choose the change directory and IDs from the real scope. Maintain business source, the actual state machine, tooling/behavior_source.json, tooling/build_model.py, probes, and independent expectations together. Generate, then inspect → verify → accept → check. The AI writes the review. Never change expectations to match a faulty implementation or merely recapture fingerprints to remove failures. Consult command --help and the Skill for exact arguments.

The normal delivery verification entrypoint is:

```bash
python -X utf8 -B validate.py
```

It checks accepted source/graph identity, architectural dependencies, business tests, and historical facts. Failure returns nonzero. It neither generates nor accepts a new baseline. Node comes from PATH or ARCHIVE_NODE.

Users discuss business meaning and inspect the updated graph. The AI maintains intermediate artifacts and asks only about new business ambiguities or conflicts. Preserve layouts, names, notes, historical versions, and existing evidence; save each new iteration separately. Business core must not import observation implementations. Graph names and coordinates must not change authorization.

These rules and entrypoints do not monitor every editor in the background. Edits bypassing them cannot be claimed synchronized. Startup and Web must distinguish the loaded build from disk source.

At first adoption, ask the user to choose drive (state-driven development) or observe (follow existing logic), and record their answer and source. Never choose silently. Both require monitoring, source-based graph adaptation, function/parameter mappings, and verification. This synthetic example explicitly uses drive. sync.json records stategraph selection; complete execution and queries live in bo_stategraph/. Old observer_runtime entrypoints delegate for compatibility only.

After each relevant coding batch, run `python observer_runtime/bo_sync.py scan --root .` and reconcile .stategraph/maintenance.json. Independent inventory includes untracked new files. Only verify → accept clears maintenance tasks. Private views live in bo_stategraph/config/views/local.json and are not overwritten by generation. Report mapping, state constraints, business rules, and project checks separately.
