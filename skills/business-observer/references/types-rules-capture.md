# Types, rules, and runtime recording

Distinguish current implementation from integration conventions. This developer tool does not force one programming framework or rule engine.

## Classes, objects, calls

Keep distinct identities, following [UML class/instance concepts](https://www.omg.org/spec/UML/2.5.1/):

| Item | Meaning | Representation |
|---|---|---|
| Class/type | Field/method definition | Type in its business region, expanding key members |
| Instance | Concrete object of a type | Selected object ID/fields bound as runtime facts |
| Call | One method execution | Call ID, receiver ID, inputs/return/start/end; node count is not call count |
| Business entity | Stable domain object | May correspond to a database row or several code objects |

Business-to-class mapping is many-to-many. Type/instance, definition/member, receiver/call, inheritance, composition, reference, and invocation remain distinct relations. Inheritance is not a runtime call. Shared objects keep one identity and shared entries, not copied state.

Do not expand the whole heap by default. Select an entity to inspect relevant fields/calls. Separate entity/attempt/call and never carry old values between objects/runs. State the mapping among database, process-object, and business IDs; process addresses are not durable business identity.

Current boundary: Python indexes classes/methods/resolvable calls; generated views emphasize key functions/parameters and events have entity/attempt/call identity. Generic heap collection and automatic complete class-instance visualization are not implemented. These conventions are not promises that every schema/adapter already supports them. Extensions require coordinated validation, capture identity, UI, and cross-instance tests.

## Rules and evaluation

Stable rule graphs need typed semantics. [DMN](https://www.omg.org/dmn/) separates inputs, decisions, knowledge; expressions/tables still define execution. [OpenFGA](https://openfga.dev/docs/concepts) and [SpiceDB](https://authzed.com/docs/spicedb/concepts/schema) distinguish object types, relations, permission expressions, and facts; preserve union/intersection/exclusion/recursion/conditions rather than making every relation transitive. [SHACL](https://www.w3.org/TR/shacl/) separates constraints and data for validation, not authorization. [Semantic DMN](https://arxiv.org/abs/1807.11615) is conceptual guidance, not runtime evidence.

One evaluation combines request actor/action/object, versioned facts, context/time, actually visited rules, result, and effects. A scenario is more than a dataset: actions, time, versions, and commit boundaries matter.

Default to instance bindings on the same rule graph: actual object/field/condition results beside nodes and actual relations/transfers on edges. Do not copy the full permission graph for every request. For recursion/inheritance/groups/exclusion/revocation, expand a minimal evidence subgraph and disclose omitted context. Relation data being graph-shaped does not require displaying every database instance.

Allow needs support; denial may mean missing relation, explicit exclusion, condition failure, or an incomplete query. Do not render all as one red path or equate timeout with denial. [SpiceDB tracing](https://authzed.com/docs/spicedb/modeling/validation-testing-debugging) may expose actual traversal at additional cost. Boolean-only engines show missing explanation, never AI-invented paths. Generic DMN/OpenFGA/SpiceDB adapters are not implemented here.

## Separate collection from display

| Capture mode | Fixed at start | Adjustable during replay |
|---|---|---|
| All core events | All connected, allowlisted probe fields | Business/state/function view, expansion, filters |
| Selected region | Selected roots/descendants/ancestors and necessary complete-version boundaries | Further filtering/drilldown within captured evidence; no retrospective outside capture |

All means connected probes, not every variable/line/call. Save the selected boundary in capture. Concurrency/shared-resource state may be needed to explain waiting without collecting every outside payload. Show focused-recording status.

POST /api/recordings/start accepts `{"scope":{"mode":"focused","roots":["content_check"]}}`; absent scope or all records core events. Stop, limits, or save failure restores default capture. Read-only views/replay send no commands.

Zoom never deletes raw events. Display steps follow visible abstraction/types, not pixel size: business views aggregate internal values; function views show captured calls/parameters; raw-event mode exposes each event. Expansion rebuilds steps while retaining raw cursor identity. Static calls cannot fill missing observations.

Each displayed step keeps its event interval and all intermediate before→after changes. Unknown previous value is not zero/empty. Separate values by producer/entity/attempt/node/call/direction/field. Business views show major decisions/activity/resources, not misleading cross-object parameter differences. Legacy records without call identity support only their existing identity scope. Final snapshot appears only at the end.

Transfers distinguish calls, input/return, decisions, transitions, resource acquisition, joins, and actual values/actions. Static structure, shared references, and temporal adjacency do not animate as real transfers.

## Capture location and overhead

Legacy reference wiring: bo_record/bo_emit → selected fields/identity → bounded queue → same-process background writer → event file. Recording also uses a background thread. This is not a separate collector or zero overhead. Check capture scope before lazy payload construction; disabled/failing observation cannot alter outcomes. Field computation, serialization, queues, and scheduling still cost resources. Measure real production load.

Native multilanguage adapters can send the same explicit evidence to the independent Python service through JSON; business code still creates accurate facts and retains transport costs.

| Mechanism | Good at | Does not automatically provide |
|---|---|---|
| Explicit probes/neutral ports | Decisions, selected values, authority reads, committed effects | Unconnected variables/external state |
| [sys.monitoring / PEP 669](https://peps.python.org/pep-0669/) | Selected Python 3.12+ call/return/exception events | Business meaning/arbitrary reliable snapshots; callbacks remain in-process |
| [OpenTelemetry collector](https://opentelemetry.io/docs/collector/deploy/agent/) | Independent processing/export of SDK/instrumented telemetry | Unexposed conditions; application instrumentation still costs |
| [py-spy](https://github.com/benfred/py-spy) | External sampled stacks/hotspots | Every call/state/permission basis without gaps |

Moving delivery into a collector does not remove the application's responsibility for facts. Sampling cannot replace deterministic state records merely to claim noninvasiveness. No generic OTel collector adapter is included.

## Source and acceptance

Business uses its own neutral ports. Observation methods use bo_, classes BO, wiring integrations/bo_*, runtime observer_runtime or observer_generated/runtime. Domain functions, real execution state, and variables keep domain names outside removable observation folders. Legacy aliases are compatibility only.

Developers may change business freely; AI maintains stable IDs, source bindings, types, probes, white-box expectations, and existing gates per iteration. Report broken mappings on rename/refactor/removal; graph cache must not hide stale bindings. Ordinary manual edits are not automatically consumed by a Skill.

Test skipped out-of-region payload construction, complete boundaries, stop/failure restoration, equivalent off/filtered/fault outcomes, different abstraction steps over unchanged raw events, intermediate changes and identity isolation, evidence-only animation, and stable personal notes/core markers that do not alter source or permissions.
