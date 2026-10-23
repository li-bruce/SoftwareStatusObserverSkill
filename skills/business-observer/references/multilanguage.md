# Shared graph and language adapters

One graph has one logical source of truth. `bo_stategraph/project.json` uses `bo-project/v1` for project identity, the user's mode choice, and the current v3 graph. `model.machine` is the execution declaration. Business groups, static calls, data, and authorization relations remain in the same graph; ordinary edges are not executable transitions.

Existing Python projects may retain their v3 graph file and move execution declarations into `bo_stategraph/machine.json`, read by both generator and actual engine. Exported copies are generated artifacts, never independently maintained definitions.

| Component | Responsibility | Boundary |
|---|---|---|
| Shared Python service | Validation, source inventory, recording, queries, export, focused graphs, full viewer | Does not decide business outcomes |
| Native state module | Read declarations; execute transitions in drive mode or observe actual application state | Business execution does not require the observer service |
| Language adapter | Source facts, types, possible calls, explicit safe capture and JSON transport | Does not infer business meaning from function names |
| Coding process | Confirmed grouping, bindings, probes, independent expectations, validation | File synchronization does not prove correct mapping |

The shared implementation is in `scripts/bo_observer/`: `graph/`, `workflow/`, `observation/`, `web/`, `delivery/`, `adapters/`. Top-level `scripts/*.py` preserve installed command entrypoints without duplicating implementation. The three-file independent Python state core can still be packaged alone. Native JS executors and probes do not import Python.

## Current support

- Python AST locates functions, parameters, annotations, and calls. Existing complete examples retain transitions, concurrent activities, resources, waiting, joins, and recovery.
- JavaScript/TypeScript uses a pinned TypeScript compiler for functions, arrows, methods, imports, calls, and routes.
- React indexes JSX/TSX components and event handlers. Lifecycle, Hooks, and asynchronous callback behavior require runtime evidence.
- Vue uses compiler-sfc for SFC script, script setup, and template entry points, retaining original file locations.
- Unsupported languages, syntax errors, and missing parsers are explicit gaps. Static candidates are not observed calls.

Native `bo.fsm/1` supports flat states, events, synchronous Boolean guards, and ordered transition selection. It rejects unsupported hierarchy, activities, and callbacks at load time. Complex projects reuse a native engine through an explicit adapter. Do not advertise the complete Python examples' Petri/hierarchical features as implemented by the JS executor. Monitoring can preserve complete activity configurations; advanced analysis opens on demand.

## Common protocols

Schemas are in `scripts/bo_observer/schemas/`. Python checks JSON Schema 2020-12, followed by shared semantic checks for dangling relations, state projections, engines, and guards. Native adapters also validate supported local semantics.

| Protocol | Contents |
|---|---|
| `bo-project/v1` | User mode choice, business abstraction, source bindings, state/capture declarations |
| `bo-source/v1` | Common symbols, parameters, possible calls, unresolved items, errors |
| `bo-event/v1` | Project/build/model/run/producer/call identity, before/after values, explicit causal dependencies |
| `bo-snapshot/v1` | Actual complete instance state, parameters, activities, and resources tied to the same evidence |
| `bo-stategraph/v1` | Full structure and retained actual evidence, independent of UI filters |

The service validates model revision and build identity; native clients return them unchanged. Producer sequences increase within their own streams. Receipt order supports replay, not inferred cross-process causality. Each instance has one authoritative producer. Duplicate events must match exactly. Old sequences, conflicting identity, wrong builds, and invalid protocols fail. Invalid actual business states retain their original values and report `mismatch`. JSON cannot carry functions, cyclic objects, NaN, Infinity, or integers outside the JS safe range; use an explicitly typed string convention for large integers.

The shared service listens locally. Native probes use bounded asynchronous queues, explicit field selection, and capture diagnostics on failure. Frontends need explicit permitted local origins and a development token, never wildcard CORS. Do not commit tokens, runtime records, or personal layouts. Web visibility and capture are independent switches; neither removes declarations or the actual executor.

State-change events require the application's `revision`, immediately followed by the actual snapshot with that revision and `evidence_id`. Ordinary calls need not have state snapshots. Missing state frames remain unknown. Replay uses receipt sequence, not wall-clock ordering across processes. Frame count and byte limits apply; final state must not fill historical gaps.

## Development and confirmation

Ask once: **develop from the state declaration (`drive`), or retain application logic and observe (`observe`)?** Record the user's exact answer and location. Before an answer, continue only independent preparation. Preserve change provenance if the user later changes mode.

`bo_sync scan` separates `confirmations.user` from `confirmations.coding`. Business grouping, authorization, and state meaning go to the user. Callback targets, parameters, and capture locations are reconciled during coding. Configured `reconciliation` records bind dynamic-target answers to current source fingerprints, actual targets, and registered runtime scenarios. Stale answers or missing targets block acceptance. These records do not replace real white-box cases.

Use `begin → scan → inspect → verify → accept → check`. All languages retain implementation inventories, parameter coverage, actual events, independent effects, and protected mapping contracts. Code, declaration, or tool changes invalidate old results. The user answers necessary business questions and inspects the graph; AI maintains the intermediate artifacts.

## Installation

```bash
python -m pip install -r <skill>/requirements.txt
npm ci --prefix <skill>/scripts/bo_observer/adapters/javascript
python <skill>/scripts/bo.py validate --root <project>
python <skill>/scripts/bo.py serve --root <project> --port 8830 --origin http://127.0.0.1:5173
```

Node and parser dependencies are required only for JS/TS/SFC analysis; native probes themselves have no third-party dependencies. Use locked versions; changing a compiler invalidates old source fingerprints. Service `validate` checks declarations, source inventory, bindings, and static implementation coverage, not project tests. Full acceptance still uses the connected gate; a running server is not acceptance evidence.

Primary references: [TypeScript Compiler API](https://github.com/microsoft/TypeScript/wiki/Using-the-Compiler-API), [Vue SFC compiler](https://github.com/vuejs/core/tree/main/packages/compiler-sfc). They supply syntax facts, not business ownership or complete dynamic-call proof.
