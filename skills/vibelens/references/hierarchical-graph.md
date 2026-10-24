# One typed graph with progressive layout

Business steps, functions, states, values, decisions, resources, and effects share one graph. Contains/call/input/return/decision/resource/join/transition relations stay distinct even with the same endpoints. Evidence types differ without splitting code and state into mutually exclusive graphs.

Use shape, color, and short labels. Show important function/type/value/result/wait information directly. Expand long values/source beside selection rather than filling every node with prose. Missing capture stays missing; a node executing does not prove every static call occurred.

New views start at graph_roots. Existing preferences restore expansion. Collapsed states remain in the full graph/search. Expanding any node replaces it with a region of its type color; show a center self-node only when actual internal relations connect to it. Contains alone does not require a center. Capture fields may project typed input/return nodes identified by function/direction/field, displaying only actual corresponding event values.

## Hierarchy, connections, selection

Parent defines spatial hierarchy. Each expanded node is a circular compound with packed child groups; ELK stress arranges top-level groups. Regions contain full labels/children and fit contents. Area means required layout space, not importance/count/business size. This borrows [circle packing](https://d3js.org/d3-hierarchy/pack) without a D3 dependency and [ELK inclusion trees](https://eclipse.dev/elk/documentation/tooldevelopers/graphdatastructure.html).

Spatial grouping does not turn calls/data/permission dependencies into containment or runtime evidence. Manual positions/pins take priority. Overlapping manually moved regions do not establish membership.

Parent-level edges terminate on region boundaries. Cross-region edges with visible internal endpoints connect those actual endpoints and draw above region fills/nodes. Only collapsed endpoints project to visible ancestors. Do not invent a parent-to-parent call from visible child calls. Regions express containment without duplicate interior contains lines. Never merge relation types or static calls with business flow. Aggregate edges show type/count and reveal original endpoints/evidence. One observed member does not imply the whole aggregate executed.

Stable glyphs: business circle, function hexagon, state double circle, decision diamond, parameter capsule, resource stack. Edges use distinct type colors/dashes/arrows for calls/flow/transitions/decisions/values/resources/joins. Keep a concise visible legend. Runtime badges/values are additional evidence, not replacement type colors.

Dragging a node, region edge/title, or empty region space moves all descendants, including saved hidden ones. Pins constrain automatic layout; explicit group drag moves pinned children with the group while retaining pins. Automatic movement of collapsed groups translates saved internal coordinates. Expansion uses current parent location, restores relative positions and nested expansion, and places new nodes locally. Make room by moving conflicting unpinned neighbors only, never during polling. Fit the expanded region; breadcrumbs return to ancestors.

Select a leaf to emphasize it, adjacent nodes/edges, and ancestor regions; select an expanded parent to emphasize its visible interior and external relations. Fade unrelated content. Selection styling is not execution evidence. Blank click/Esc clears. Region titles select; double-click progressively expands/collapses. Parent collapse retains internal expansion. Show breadcrumbs/counts, F to locate, P to pin, overview to collapse without deleting saved state. Search includes collapsed nodes while respecting filters.

State/function identities stay original. Transitions derive from actual declarations, and only matching-run evidence highlights them. Missing historical high-level state remains unknown rather than borrowing final state.

## Persistence and layout

- Node drag updates coordinates; blank region drag moves the group; outside drag pans. Inner regions/nodes/edge labels take hit priority.
- Save position/pins/expansion/camera in bo_stategraph/config/views/local.json by stable project/node ID, never attempt/port/build hash.
- Polling changes values only. Re-expansion restores positions; new nodes use nearby free space.
- Explicit Arrange triggers layout; a new view may arrange once. Pins stay exact; provide undo.
- Report failed persistence honestly. Drag, version change, or expansion invalidates outstanding async layout results.

Names/notes are personal presentation, shared by canonical ID and displayed beside nodes. Restore name removes only the alias, retaining notes. Original name/source identity remains available. AI regeneration cannot override personal aliases. Preserve hidden/historical IDs; actual ID migration is explicit, never guessed from names. Restore focus/expansion/camera on refresh and save final view on exit.

The project file is persistent authority; localStorage is cache. Initial empty-project migration may import only that project's old cache; existing files cannot be overwritten by cache. Revision comparison and atomic replacement protect multiwindow writes. Failed saves stay unsaved. Clearing browser storage does not delete project preferences. No real-time collaboration is claimed. Older layouts remain readable.

ELK.js 0.12.0 runs locally in a Worker. Default deterministic circular packing plus group stress, with layered/stress alternatives, produces fixed positions—not continuous force simulation. Polling cannot drift nodes. Pins outrank compactness. Arrange may reorganize old expanded layouts with undo. These choices borrow [yWorks incremental-layout principles](https://docs.yworks.com/yfiles-html/dguide/layout-incremental_layout/), not proprietary yFiles code. [Hierarchical layout](https://docs.yworks.com/yfiles-html/api/HierarchicalLayout/), [ELK.js](https://github.com/kieler/elkjs), [ELK stress](https://eclipse.dev/elk/reference/algorithms/org-eclipse-elk-stress.html).

## Rendering and integration

Assets include PixiJS 8.22.0, ELK, and licenses. graph-core projects nodes/facts; layout handles geometry/gestures; renderer owns drawing/hits/disposal; viewer coordinates UI; preferences/polling handle persistence/refresh. Serve all resources including the Worker from the same origin. Runtime data never goes to CDN/layout services.

Preserve model/manifest/events/authority/machine APIs. Stable layout_id shares layout across runs/history. graph_roots/parent define hierarchy; personal preferences restore scope. New views do not adopt obsolete default_expanded. States need explicit parentage, not renderer guesses. Do not recreate a separate machine_layout canvas. /api/source returns bound source/build only.

Test real drag/pan/refresh/pins, all algorithms, incremental expansion, undo, source links, hidden-descendant translation, circle containment/neighbor avoidance, boundary endpoints, aggregate types/endpoints/partial evidence, high-level initial view, highlights/breadcrumbs/history. Test notes across types, collapse/expand, regenerated names, restored original name retaining notes, failed saves, and old layouts. Automated small graphs prove neither human usability nor large-graph performance.

## Filtering and continuous operation

Independently filter node/edge/region types and depth. Hidden regions may expose enabled ordinary nodes; region-only views retain actual region relations. Hidden edges do not silently reconnect to unrelated endpoints. Explicit context boundaries preserve selected relations where supported. Filtering does not mutate graph/positions/expansion. Old layouts default to all types.

Reuse Pixi objects by stable identity, retaining at most 128 unused objects per frame; dispose excess without destroying potentially shared textures. Timestamp-only refreshes do not rebuild graphs, but crossing authorization expiry does. Background tabs pause polls/draw; foreground rereads. Closing releases worker/canvas. Source cache retains at most 16 files.

See [PixiJS performance Skill](https://github.com/pixijs/pixijs/blob/dev/skills/pixijs-performance/SKILL.md). Verify idle draw stability, bounded objects during repeated operations, expiry/live updates, errors/recovery. Object counts are not GPU measurements and finite small-graph tests do not establish crash immunity. [Recording/shared membership](recorded-analysis.md) uses the same glyph geometry for canvas/SVG legend, region type fills, and independent runtime badges.
