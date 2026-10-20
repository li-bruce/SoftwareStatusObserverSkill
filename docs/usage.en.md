# Installation and usage

[中文](usage.zh-CN.md) · [Home](../README.en.md)

## Use it in your project

Install the complete `business-observer` directory, not just `SKILL.md`. In a new conversation inside the target project, invoke `$business-observer` and describe the feature or change.

```text
Use $business-observer to add approval to file exports.
Exports require authorization and content checks. Clarify concurrency,
failure and retry rules before implementation. Let me inspect decision
conditions, key parameters and responsible functions in the runtime graph.
```

The Skill should first identify actors, triggers, objects, outcomes and waiting conditions. It asks about missing rules that change execution, reuses existing answers, and keeps unanswered questions open. An AI recommendation is not a user decision. See [discovery.example.json](../skills/business-observer/assets/discovery.example.json). Here `<skill>` is the installed `business-observer` directory:

```text
python <skill>/scripts/requirements_dialogue.py check --file discovery.json
```

If you copy the example to `discovery.json`, D1 is deliberately unresolved. A nonzero exit is expected until an answer is obtained and the record updated.

When integrated into change checks, unresolved blocking questions prevent acceptance. The script validates records and links; reviewers still need to assess whether questions are complete and answers were understood correctly.

## Read the graph

| Level | Question |
|---|---|
| Business flow | What steps does this operation follow, and why did it stop? |
| Internal state and key code | Which activity is running, what inputs does it use, and what condition is missing? |
| Local code structure and source | Which function owns this step, and where is its implementation? |

The top-level “checking” state is a summary. Each run retains the waiting, running and completion state of every declared activity. Folding nodes only changes presentation. Run identity, parameter version and build version keep records distinct; missing observations are not inferred as success.

Business, function, state, parameter and resource nodes share one canvas, with different shapes and colors. Double-click a node, or select it and click “展开” (expand). Select “源码” (source) to open code beside it.

Drag nodes to position them; drag the background to pan. Positions, expansion and camera settings are saved in this browser and restored after reload. Runtime updates only change displayed facts. Select “固定节点” (pin, shortcut P) to preserve an exact position during automatic layout. Choose layered or stress layout, click “自动布局”, and undo if needed. Use “显示完整图” to fit the graph and zoom for details. Layout preferences do not change application state or authorization.

Select any node and choose “名称与备注” (name and note). Edits save as you type. Business, function, parameter and state nodes are supported. “恢复原名” restores the generated name while keeping the note. Source identities and runtime facts stay unchanged. Regeneration preserves personal labels; reload restores focus and nested expansion. Folding a parent retains its children's expansion choices.

Preferences are local to this browser and website address. Clearing site data removes them; they do not sync across devices. Storage failures are shown explicitly.

All active layout and styling components are open source: PixiJS (MIT), ELK.js (EPL-2.0), and original JS/CSS (MIT). No yFiles code is included. See [third-party notices](../THIRD_PARTY_NOTICES.md) and the [ReBAC graph design](../skills/business-observer/references/rebac-graph.md) (Chinese, design only; no engine integration yet).

## Edit code and keep the graph synchronized

From `examples/delivery`:

```bash
python observer_generated/runtime/change_sync.py begin --root . --change .stategraph/my-change --request "Describe the change"
# Edit business code, relevant probes, tooling/build_graph.py and tests.
python tooling/dev.py graph --reason "Explain the graph or state-definition update"
python tooling/dev.py inspect
```

Review `.stategraph/my-change/impact.json` and create `review.json` beside it. Bind it to the current `candidate_id`; explain updates or retained behavior for business rules, state machine, abstractions and probes. The [change-check reference](../skills/business-observer/references/cochange.md) contains the schema. When changing existing requirements, pass their IDs to `begin --requirements`.

```bash
python tooling/dev.py verify
python tooling/dev.py accept
python tooling/dev.py check
python tooling/dev.py archive --label my-change
```

`verify` executes the program and counterexamples. `accept` accepts only that verified candidate. `check` compares the current inputs before delivery. Later edits to code, graph, rules, tools or tests invalidate the old acceptance. Do not rewrite expected outcomes to hide a bug.

Commands in `sync.json` are argument arrays, never shell strings. `{python}` resolves to the current interpreter. First launch restores a fixed, reviewed release baseline; edited code is not automatically approved.

## Separation and runtime modes

Business code depends on its own optional interface in `app/ports.py`. Files prefixed `bo_` and `observer_generated/` implement observation. The real state machine and resource constraints belong to the application and remain active when observation is disabled.

```bash
python tooling/dev.py ownership
python tooling/dev.py core --out dist/delivery-core.zip
```

The core ZIP contains business source, requirements and licenses without the observer implementation or pages. Install its requirements, then run `python main.py`. The neutral interface retains no-op calls. Tests compare results with probes enabled, disabled and failing.

Probes add payload, queue and storage costs; state recording and graph polling also have a cost. The example retains run history and has no long-running retention policy or production performance claim. Its 400 ms polling and deliberate delays are not performance measurements.
