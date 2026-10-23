# Development branch: graph continuity and deeper source views

Status: `dev` foundations, with database work implemented on its `db-vis` branch. Deeper source and API work remain planned. See [database delivery](db-vis.md) for the new scope and evidence.

## Implemented in this iteration

- Project-owned view settings survive source/model updates: type filters, individual exclusions, expanded groups, positions, camera, custom views, names, and notes.
- Explicit one-to-one node/edge aliases migrate personal settings. A conflict preserves both records. Deleted IDs remain dormant so restoring a feature can recover its settings. Similar names do not imply identity.
- Static call IDs use caller, target, call content, and repeated-call occurrence. Line numbers remain source evidence. Moving a call by adding comments no longer changes its ID. Inserting an identical repeated call can still make occurrence identity ambiguous.
- All elements clears type, individual, scope, text, depth, and advanced-detail exclusions. It preserves expansion and positions. Cross-group relations connect enclosing regions; internal relations and contained nodes are counted as folded.
- The recording list and replay endpoint accept only the current code/graph version. Changing the graph exits an old replay and interrupts active capture. Restarting the same version preserves recordings. Private original JSON files remain on disk; frozen review evidence is unchanged.

## Capability inventory

| Layer | Present | Remaining work |
|---|---|---|
| Source / AST | Independent source inventory; definitions, classes, parameters, imports, call sites, unresolved targets; selected implementation nodes and resolved static calls in the graph. Python and JS/TS/React/Vue adapters. | A complete browsable source index with file/class/function neighborhoods, bounded queries, and lazy expansion. The current canvas is a projection of mapped implementations, not every AST syntax node. |
| Data / database | On `db-vis`: strict catalogs, SQLAlchemy/Mongoose exports, SQLAlchemy/PyMongo/Redis/Neo4j metadata, native Python/Node query and transformation capture, data views and automatic refresh. Real SQLite and four-server tests. | Additional database adapters, arbitrary DTO/entity mapping, automatic column lineage, and database-internal execution plans. |
| API | Python route decorators, JS route registrations, DOM/JSX/Vue handlers appear in source inventory and mapping checks. | Typed endpoint nodes, method/path identity, request/response contracts, client-to-endpoint and endpoint-to-handler relations. No general OpenAPI import or verified cross-service request matching exists yet. |

Source pointers: [Python extraction and graph projection](../../skills/business-observer/scripts/bo_observer/graph/code_structure.py), [JS/TS/SFC extraction](../../skills/business-observer/scripts/bo_observer/adapters/javascript/scan.mjs), [current capability boundary](../source-data-and-language.md).

## Planned work and acceptance

- [ ] **Source neighborhoods.** Query file → class/function → references/calls against a build-bound index. Keep unresolved targets explicit, exclude observer/vendor code by declared scope, and preserve original source locations. Test newly added/deleted files, imported calls, callbacks, source moves, large neighborhoods, and stale builds. Static candidates remain distinct from executed calls.
- [x] **Database schema on `db-vis`.** Read metadata and export native declarations; preserve types, nullability, keys, constraints and evidence boundaries. Map actual data access and transformations. Test schema drift, failures, unknown targets, observer exclusion and view continuity. Further adapters remain separate work.
- [ ] **API relationships.** Normalize supported route definitions and OpenAPI declarations into endpoint identities. Attach handler, parameter/schema, and explicitly resolved client relations. Test path parameters, routers/prefixes, method differences, dynamic URLs, contract drift, and frontend/backend build mismatch. Unresolved requests remain unlinked candidates.
- [ ] **Shared protocol additions.** Define typed nodes/edges, source provenance, confidence/unknown fields, migration rules, and export fixtures before exposing new layers. Extend strict validation and language adapters together.

These additions are optional lower-level views. The opening graph continues to show confirmed business structure. They do not replace source mapping checks or runtime evidence.
