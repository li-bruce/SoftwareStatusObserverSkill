# Software Status Observer Skill

[中文](README.md) · [Installation and usage](docs/usage.en.md) · [Runnable example](examples/delivery/README.en.md) · [Refactor review](docs/review/refactor-round1/README.md)

**Understand and debug the programs you build with AI.**

`business-observer` guides a coding agent to maintain business logic, selected code relationships and the application's real state machine together. A layered runtime graph shows core functions, parameters, decisions and execution state.

## What it shows

- Expand a business action into internal activities and key functions, then inspect its source.
- Keep business, function and state nodes in one graph. Drag and pin nodes, apply layered or stress layouts, and restore positions after reload.
- Start and stop a recording of program operations, replay instrumented events, and locate their source. Use preset or custom analysis views, drag groups from their empty interior, and inspect shared nodes through references. See the [walkthrough and checks (Chinese)](docs/review/recorded-views/README.md).
- Capture all instrumented core events or a selected region. Replay steps follow the visible abstraction level and show before/after values. Add node notes and core markers. See the [focused replay review](docs/review/focused-replay/README.md) and [type, rule and capture design](skills/business-observer/references/types-rules-capture.md) (Chinese).
- Add display names and notes without changing source identities; preserve personal labels and nested expansion across reloads.
- Search names, functions, parameters and notes, including nodes inside collapsed regions.
- Read parameter types, actual values, outcomes and waiting conditions directly on nodes and edges.
- Follow concurrent activities, available capacity and join conditions to find what blocks progress.
- Inspect each run and parameter version without confusing current facts, history and missing observations.

By default, the coding agent uses the state network to guide implementation internally. Users may choose any framework or coding workflow. If a user explicitly declines this development approach, the agent adapts the network to their implementation. Both modes require instrumentation, source-driven model updates, graph display and verification, without exposing intermediate maintenance steps as a user workflow.

The Python state network lives in an independent module. Business code may use a state-machine engine or ordinary functions; structure, observation and export remain available in either case. See the [runnable two-mode example](examples/python-modes/README.md) and [module contract](skills/business-observer/references/independent-python.md) (Chinese). Full demos expose `/api/stategraph/export` for the complete declared graph and retained runtime evidence, independently of viewport filters.

The Skill builds the graph from the user's current description and uses necessary clarifications or counterexamples to confirm that it reflects their intent. It does not proactively develop missing business workflows or recommend business rules. When the user or another Skill supplies further rules, it updates the same graph and its checks. During edits it checks whether the graph, state machine, probes and tests remain consistent. Business abstractions come from requirements; local code relationships come from Python AST analysis; runtime facts come from execution.

## Install the Skill

In Codex with `$skill-installer`, enter:

```text
Use $skill-installer to install business-observer from:
https://github.com/li-bruce/SoftwareStatusObserverSkill/tree/main/skills/business-observer
```

`main` contains the latest commits; historical tags retain their original versions. If upgrading an existing installation, preserve your edits before updating the complete Skill directory.

Or clone this repository and install into a project:

```bash
git clone https://github.com/li-bruce/SoftwareStatusObserverSkill.git
cd SoftwareStatusObserverSkill
python tools/install_skill.py --project /path/to/your-project
```

The script copies the full Skill to `.agents/skills/business-observer` in that project. It refuses to overwrite an existing installation. Open a new conversation in the target project and ask:

```text
Use $business-observer to implement this feature: …
Help me clarify the behavior and states using a graph.
Follow this project's development approach, maintain the graph and checks
as you code, then show me the changes and runtime results.
```

Describe the feature, answer business questions and inspect the graph. The agent maintains source mappings, probes and checks without asking you to manage intermediate files. Installing a Skill alone does not watch every editor; the agent connects checks to the project's workflow.

## Run the example

Use Python 3.11–3.13, Node.js 20+ and a modern WebGL browser. Node.js is needed only for graph tests.

```bash
python -m venv .venv
```

Activate with `.venv\Scripts\Activate.ps1` in Windows PowerShell or `source .venv/bin/activate` on macOS/Linux.

```bash
python -m pip install -r examples/delivery/requirements.txt
python tools/demo.py
```

Open the [runtime graph](http://127.0.0.1:8797/) and [control page](http://127.0.0.1:8797/control). Approve the current version, run **检查并提交** (check and submit), then expand **检查内容** (check content) in the graph. Set capacity to 1 to see one activity running while another waits. After both checks pass, the application rechecks authorization and version before committing an artifact.

The example uses synthetic text and local SQLite. The graph polls about every 400 ms; checks are deliberately slowed for observation. See the [walkthrough](examples/delivery/README.en.md).

## Repository layout

The 2026-10-22 update focuses clarification on confirming the user's intent, retaining questions and counterexamples needed to resolve ambiguity. The [independent project-flow trial](docs/review/intent-confirmation-20261022/README.md) (Chinese) includes actual simulated dialogue, a cross-type derivation iteration, failures and fixes, screenshots, and runnable source packages.

Version 0.5.0 moves complete lifecycle coordination into the independent state module, unifies validation and instance queries, and adds independent source inventory, stage completion checks, project-local preferences, bounded event retention and versioned upgrades. Mapping fidelity and business correctness have separate reports. See the [code and trial review](docs/review/refactor-round1/README.md) (Chinese).

The [team archive example](examples/team-archive/README.en.md) was built in a separate conversation from an initial request, followed by clarification, implementation, fixes and a size-limit iteration:

```bash
python tools/archive_demo.py --port 8824
```

Open the [application](http://127.0.0.1:8824/) and [developer graph](http://127.0.0.1:8824/graph). The review includes both iterations, actual runtime evidence and screenshots. The requester was simulated by AI; this is not a human usability study.

Version 0.4.0 adds source-bound whitebox contracts throughout development, observed parameter and decision checks, focused graph extraction with explicit boundaries, and allowlisted project exports. See the [design (Chinese)](docs/design/roadmap.zh-CN.md), [development workflow](skills/business-observer/references/continuous-development.md), and [focus/export commands](skills/business-observer/references/focus-and-sharing.md).

| Directory | Purpose |
|---|---|
| `skills/business-observer/` | Skill instructions, checks, probes and graph templates |
| `examples/delivery/app/` | Domain functions, storage and transactions |
| `examples/*/bo_stategraph/` | Complete lifecycle and activity execution, shared contracts and queries; preferences under config/views |
| `examples/delivery/integrations/` | Optional observer adapter and viewer sources |
| `examples/delivery/observer_generated/` | Generated graph, viewer and copied runtime helpers |
| `tests/`, `tools/` | Installation, release checks and regression tests |

## Checks and scope

The current version includes a protected [mapping plan](skills/business-observer/references/mapping-contract.md) (Chinese). It compares actual store values with each required scenario's instances and the public export. Removing required scenarios or fields fails acceptance. Existing projects must add `mapping_contract` to `sync.json` and provide the corresponding observations; recreating a baseline is not a migration. Invalid definitions, unsupported engine semantics and missing guard bindings fail before loading. Runtime violations remain visible as actual facts and fail constraint checks.

```bash
python tools/verify.py
```

Checks cover requirement clarification, authorization and version counterexamples, concurrency and resource waits, overlapping runs, historical graph rendering, equal business outcomes with probes on/off/faulty, and running the core package without the observer. The [usage guide](docs/usage.en.md) explains the edit-and-review workflow.

This first release provides a Python reference implementation. Skill instructions and the demo UI are primarily Chinese; these guides are bilingual. Other languages need their own static analysis and runtime adapters. Coverage is limited to selected paths and declared activities, not every function local. Passing checks is not a proof of complete program or authorization correctness.

The graph supports inspection and drill-down. Commands run through the control page; editing graph nodes to control the application is not implemented. This is a local development example without production authentication or restoration of crashed worker threads.

## License

[MIT](LICENSE). See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for dependencies and attribution.

The built-in graph can show the initial design and follow the coding conversation into runtime debugging. Answers stay in the coding assistant; the Web is read-only. Hide its entry, disable Web routes, or export the verified core without the viewer. Typed fills emphasize core nodes. See the [conversation and Web guide](skills/business-observer/references/conversation-web.md) (Chinese).
