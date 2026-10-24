# Do not observe the observer

Graph/runtime records explain the target application. Event delivery, graph refresh, source reading, export, layout saving, and record controls are not business steps. Their source remains versioned/classified and capture faults remain in health; do not produce business events for these operations.

## Source and graph

Register exact source identities in `implementation.excluded` with `category: observer` and a reason. HTTP observer handlers also provide sorted `routes` containing every actual decorator path, for example `["/api/view"]`. The checker compares source and permits only Skill graph routes and `/api/bo/` observer endpoints. Unknown/dynamic routes or functions also bound to business routes cannot be excluded this way. Never exclude an entire application entrypoint file.

Use bo_ methods, BO classes, and isolated observer files for helpers. Source scanning retains them for version/wiring checks; enrich does not expand registered observer implementation into business-call nodes. A real transition executor in `bo_stategraph/workflow.py` remains application logic and cannot be excluded merely by its directory.

## Runtime wiring

HTTP middleware calls `web.is_observer_request(request.url.path)` before capture. Skip observer pages/assets/APIs. Give business routes explicit ownership; do not label unknown requests as developer-graph business operations.

Wrap custom observation reads/reports in `observation_scope.bo_internal()`. Public Pins automatically uses this context for builders and sink writes; recording uses it when reading views, preventing recursive capture. Context is thread/async-task local and restores after exceptions. Never wrap actual business execution.

Do not filter by words such as notification or report: notifying a reviewer and submitting business reports remain business events. Invalid static exclusions fail acceptance. Suppressed internal capture has its own `health.suppressed_internal` count, not business-event loss.

## Correct an old misclassification

Preserve baseline/history and begin a change. Reclassify each mistaken observer route, remove its business node/capture wiring, and record `observer_reclassifications` in review.json by old feature ID with exact original source order and a reason.

This migration requires every source of the old feature to be a registered observer HTTP route, unchanged source AST against baseline, and removal of the feature/node from the business graph. Business sources, simultaneous handler edits, or a prose-only reason fail. All original expectations, mapping witnesses, required probes, and business-capture protections remain active; do not reset the baseline.

Run inspect → verify → accept → check. Verify polling/source/layout/record controls add no business events, actual business still generates events, and off/fault preserves outcomes. Old recordings keep their original model/facts rather than being rewritten as new-version results.
