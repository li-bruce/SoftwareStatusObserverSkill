# Software Status Observer Skill

[中文](README.md) · [Installation and usage](docs/usage.en.md) · [Runnable example](examples/delivery/README.en.md)

**Understand and debug the programs you build with AI.**

`business-observer` guides a coding agent to maintain business logic, selected code relationships and the application's real state machine together. A layered runtime graph shows core functions, parameters, decisions and execution state.

## What it shows

- Expand a business action into internal activities and key functions, then inspect its source.
- Keep business, function and state nodes in one graph. Drag and pin nodes, apply layered or stress layouts, and restore positions after reload.
- Read parameter types, actual values, outcomes and waiting conditions directly on nodes and edges.
- Follow concurrent activities, available capacity and join conditions to find what blocks progress.
- Inspect each run and parameter version without confusing current facts, history and missing observations.

The Skill asks about unclear requirements that affect permissions, state or outcomes. During edits it checks whether the graph, state machine, probes and tests remain consistent. Business abstractions come from requirements; local code relationships come from Python AST analysis; runtime facts come from execution.

## Install the Skill

In Codex with `$skill-installer`, enter:

```text
Use $skill-installer to install business-observer from:
https://github.com/li-bruce/SoftwareStatusObserverSkill/tree/v0.2.0/skills/business-observer
```

Or clone this repository and install into a project:

```bash
git clone https://github.com/li-bruce/SoftwareStatusObserverSkill.git
cd SoftwareStatusObserverSkill
python tools/install_skill.py --project /path/to/your-project
```

The script copies the full Skill to `.agents/skills/business-observer` in that project. It refuses to overwrite an existing installation. Open a new conversation in the target project and ask:

```text
Use $business-observer to implement this feature: …
First identify the business flows and states, and ask about unclear rules
that affect outcomes. Keep the layered graph, key functions and parameters,
real state machine and probes in sync while coding. Before delivery, run
the checks and explain successful, waiting and failed executions.
```

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

| Directory | Purpose |
|---|---|
| `skills/business-observer/` | Skill instructions, checks, probes and graph templates |
| `examples/delivery/app/` | Application-owned state machine, concurrent activities and business code |
| `examples/delivery/integrations/` | Optional observer adapter and viewer sources |
| `examples/delivery/observer_generated/` | Generated graph, viewer and copied runtime helpers |
| `tests/`, `tools/` | Installation, release checks and regression tests |

## Checks and scope

```bash
python tools/verify.py
```

Checks cover requirement clarification, authorization and version counterexamples, concurrency and resource waits, overlapping runs, historical graph rendering, equal business outcomes with probes on/off/faulty, and running the core package without the observer. The [usage guide](docs/usage.en.md) explains the edit-and-review workflow.

This first release provides a Python reference implementation. Skill instructions and the demo UI are primarily Chinese; these guides are bilingual. Other languages need their own static analysis and runtime adapters. Coverage is limited to selected paths and declared activities, not every function local. Passing checks is not a proof of complete program or authorization correctness.

The graph supports inspection and drill-down. Commands run through the control page; editing graph nodes to control the application is not implemented. This is a local development example without production authentication or restoration of crashed worker threads.

## License

[MIT](LICENSE). See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for dependencies and attribution.
