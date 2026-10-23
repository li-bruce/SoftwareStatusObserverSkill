# Python, Node.js, React, and Vue share one graph

This synthetic task starts when a slot is available, waits when it is not, and can finish after recovery. Python maintains the graph and recording; native code executes the task. React and Vue provide independent operation interfaces.

From the repository root:

```bash
python -m pip install -r skills/business-observer/requirements.txt
python tools/setup_adapters.py
npm ci --prefix examples/multilanguage
python tools/multilanguage_demo.py --mode drive
# Or: python tools/multilanguage_demo.py --mode observe
```

Open the printed [application](http://127.0.0.1:8850/) and [graph](http://127.0.0.1:8855/graph) URLs. Start recording, start and finish each frontend task, stop, then replay actual state/value changes. Expand functions and parameters to their source. Ctrl+C stops processes owned by the launcher.

- drive: the native executor reads transitions from bo_stategraph/project.json.
- observe: src/job.mjs keeps its own logic; graph and capture still work.
- src/ contains business code; integrations/bo_* contains capture and composition; bo_stategraph/ contains declarations and native adapters.
- Tests also execute src/job.py using the same declaration.
- .stategraph/collector.json is local connection configuration with a temporary development token. Do not commit or share it.
- Layouts and language preferences live in bo_stategraph/config/views/local.json.

```bash
python tools/verify_multilanguage.py
python tools/test_multilanguage.py
```

Cases cover both modes, capture enabled/disabled/failing, actual Python/JS functions, compiled React/Vue handlers, independent source inventory, and typed parameters/events. Additional regressions cover transport, conflicts, stale bindings, and observer-noise exclusion. The repository-wide gate remains `python tools/verify.py`.

Native bo.fsm/1 supports flat states/events and synchronous Boolean guards only. Unsupported semantics fail. For full concurrent activities, waiting, resources, and joins, see the [Python archive example](../team-archive/README.md). Do not present this native subset as a general workflow engine.
