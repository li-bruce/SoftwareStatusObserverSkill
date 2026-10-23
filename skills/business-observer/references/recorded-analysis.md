# Recording, analysis views, and shared membership

These features help developers understand implementation. View controls never change business state; replay sends no business commands. See [types, rules, capture](types-rules-capture.md) for scope/step granularity. Main controls are view/search/recording, with canvas tools and a persistent legend on the sides. Version/test-case/historical-time controls are not primary selectors; records still retain exact source identity. Notes and core markers use stable IDs.

## Record actual operations

Follow the [DevTools recording pattern](https://developer.chrome.com/docs/devtools/performance/reference): start, operate the application, stop, locate events, inspect values, replay.

recording_session.py saves intervals, source, and gaps using the Python standard library. recording.js projects read-only event-boundary views. The service adapter supplies actual snapshots/loaded source and optional operation markers after real commands return. Business functions/authorization stay independent.

| API | Purpose |
|---|---|
| POST /api/recordings/start | Start interval; repeated start returns current recording |
| POST /api/recordings/stop | Capture final boundary and stop appending |
| GET /api/recordings | Status and saved list |
| GET /api/recordings/{id} | Events, initial/final state, model, source |
| GET /api/source?recording={id}&path={path} | Source bound to that recording |

Preserve producer/run/attempt/event/call/build identities. Pre-start context is separate from interval events. Several runs may appear in one operation recording, but values/evaluations remain assigned to their attempts.

The provider must read consistent state/events at the project's state boundary. Background persistence runs each second; stop resamples and writes. Normal stop saves the complete interval; abnormal exit may lose the last unsaved segment and marks interruption. Limits: 20,000 probe events, 2,000 operation markers, 32 MiB. Overflow, capture failure, and save failure expose gaps. Record only chosen fields, never arbitrary locals/bodies/credentials. Disabled capture cannot be presented as recording real events.

Saved records bind loaded model/source. Do not display new code as old implementation. Replay includes only prior events and exact journal revisions. Never copy final check/approval/commit outcomes into early frames. Missing boundaries are unknown; final snapshot is used only at the end. Header replay values require explicit presentation.replay_parameters node/direction/field bindings, e.g. limit_bytes from project_limit out.limit_bytes; matching field names alone are insufficient.

Edge animation requires real dependency references, same-call parent identity, captured input/return, or exact activity resource/join evidence. Static calls/shared references/temporal adjacency are not transfers. Use a separate animation layer, stop when done, and handle background tabs, reduced motion, and disposal.

## Exact frames and shared resources

Projects without machine.execution journals may supply runtime_frames with schema stategraph-runtime-frames/v1. Each frame contains event_id/run_id/build_id/integer revision and actual post-transaction machine/authority. Event revision and machine.state_revision must match. Validate identity and parameter allowlists; do not save out-of-scope frames or overwrite an old event with later values. Do not pass raw databases/arbitrary objects as projections.

Set `runtime_frames.partial: true` when snapshots accompany only state-change events rather than every ordinary function call. Every event carrying an integer state revision still requires its matching frame; partial mode does not excuse a missing state boundary. A function-call step without a frame has unknown state, not an invented copy of the last snapshot. Include the actual phase in each complete configuration and current-state summary at the same transaction boundary.

Project phase labels take precedence for business-phase changes. Activity enums use activity meanings. Raw captured strings remain raw; the value `pending` in a parameter must not automatically become the activity label "Not started". Missing optional display labels fall back to the original state ID.

Obtain frames from transactional snapshots/version history; periodic sampling cannot reconstruct intervening changes. Missing frames stay unknown; start/end snapshots prove only endpoints. Frame count/bytes share recording limits.

machine.configurations retains existing run structure. machine.shared_resources stores one global entry per actual resource-node ID with selected fields. presentation.runtime_owner identifies the abstract node showing flow changes. Viewer shows before/after flow/activity/resource values without fabricating per-run pools. Project scenarios still verify global mutual exclusion/capacity/fairness. Snapshot differences alone do not prove calls or causality.

## Analysis views

All views filter the same graph. Users need not manually expand every parent before finding states/functions.

| Preset | Purpose |
|---|---|
| Layered overview | Progressive detail with context |
| Business flow | Business operations and relations |
| State machine | Declared states and transitions |
| Functions and parameters | Functions, inputs, returns, static calls |
| Authorization | Explicitly mapped decisions/dependencies |
| Concurrency and resources | Activities, capacity, waiting, joins |
| Data dependencies | Values/functions/decisions and transfers |
| Observed execution | Nodes with selected-run evidence |
| Waiting and failures | Waiting/rejected/error nodes |
| Shared membership | Original nodes and other-group entries |

Authorization uses explicit semantic mapping, not name-based proof of coverage. A ! badge can mean wait/reject/error; inspect the reason. Static function edges still do not prove execution.

Combine node/edge/region types, depth, scope, and text; save up to 20 custom views. Each has separate coordinates/expansion/camera, with aliases/notes shared by canonical node ID. New presets do not overwrite old views. Persist in bo_stategraph/config/views/local.json, with browser cache only. Ports/restarts preserve the project file; concurrent-save conflicts prompt refresh rather than silent overwrite.

## Shared abstraction membership

parent is the primary layout/expansion/drag hierarchy. presentation.memberships contains explicit `{group,member,reason,evidence}` shared relations, not calls/causality/authorization. The reference also derives membership from machine.execution.within and declared activities/resources/joins.

Keep one canonical node. Other groups show a referenceOf entry marked ↗, sharing value/source/notes but with local coordinates and independent collapse. Shared edges have a distinct style and no execution animation. References do not recursively expand by default, preventing endless duplication/cycles. Cross-group navigation returns to the original.

This does not force shared meanings into exclusive groups or treat geometric overlap as membership. A matrix may help large-set intersections but does not replace the execution graph. Alternatives: [Bubble Sets](https://vialab.science.uoit.ca/wp-content/publication_media/pdf/col2009c.pdf) smooth envelopes, [LineSets](https://www.microsoft.com/en-us/research/publication/design-study-of-linesets-a-novel-set-visualization-technique/) curved membership paths, [KelpFusion](https://www.microsoft.com/en-us/research/wp-content/uploads/2016/12/kelpfusion_tvcg2013.pdf) mixed areas/links, [UpSet](https://upset.app/) set intersections. Primary hierarchy plus references is a design choice for circular expansion, independent collapse, and source navigation, not a claim of superiority or proven usability.

## Required verification

Test region/group dragging vs canvas pan and inner hit priority; shared glyph/fill/legend badges; start/stop/empty/repeated-start/cross-run/loss/save-failure/restart/limit behavior; no future values in replay; replay without business writes; original recorded source; view changes preserving raw event/cursor identity; custom layout restoration; hidden facts retained; independently collapsible shared groups with no duplicate execution counts; real browser locate/play/pause/animation. Finite small-graph automation is not universal performance or human-usability proof.
