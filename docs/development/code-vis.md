# Optional code structure

The authored business/state graph remains the semantic model. The optional code
index supplies deterministic source relationships in the same viewer. It is a
derived view, not an additional business engine.

## Prior art and implementation choice

- [CodeGraph](https://github.com/lzehrung/codegraph) exposes files, symbols,
  references and dependencies as a queryable source graph. Its separation of
  indexing from retrieval informed the local index and neighborhood API.
- [code-graph-analysis](https://github.com/eracle/code-graph-analysis) provides
  callers/callees and bounded impact queries. We adopt explicit traversal depth,
  retaining the original endpoints at a neighborhood boundary.
- [SCIP](https://github.com/scip-code/scip) distinguishes symbol identities,
  source occurrences and relationships. This release keeps identities separate
  from source lines and preserves individual call occurrences.
- [Tree-sitter-graph](https://github.com/tree-sitter/tree-sitter-graph) separates
  syntax extraction from graph construction. The existing Python AST and
  TypeScript/Vue parsers already cover this repository's supported languages;
  this release reuses them instead of adding a second parser stack.

These are design references. Their code, servers and storage engines are not
bundled. The implementation remains MIT and uses existing pinned dependencies.

## Components

| Component | Responsibility |
| --- | --- |
| `sources.py`, Python/TypeScript/Vue adapters | Source facts, file hashes, incremental parsing and unresolved targets |
| `code_graph/index.py` | Stable files, classes, functions, parameters, imports, inheritance and call occurrences |
| `code_graph/query.py` | Authored-to-source bindings, scoped retrieval and explicit boundaries/budgets |
| `code_graph/service.py` | Lazy source refresh, exact-revision source access, independent checks and JSON export |
| `code-layer.js` | Cancel obsolete requests and merge a display projection without changing the runtime build |
| Existing Web/view modules | Typed glyphs, edges, filtering, expansion, notes, dragging and personal layouts |

`/api/code/graph` is local, read-only and follows the same Web visibility policy
as the runtime graph. `focus=NODE_ID` selects an authored region or code node;
`depth=0..3` controls call/type neighbors. Responses default to 400 declarations,
with at most 80 named boundary nodes and 10,000 relations. The response reports
omitted nodes/relations. The viewer can load more, up to 5,000 declarations;
the CLI exports the entire indexed scope as JSON.

Opening the code view creates `.stategraph/code-graph.json`. Subsequent view
requests and `bo_sync scan/watch` refresh it from independent source inventory,
including new files. Unchanged files reuse parser facts within a running service.
`bo_code.py check` and iteration verification recompute the source graph and
reject stale or modified exports without repairing them. Viewing source requires
the exact code revision; a stale runtime build remains separately marked stale.

## Presentation and limits

The default overview does not request a code index. Select a business/function
node and choose **Local code**, or choose **Code structure** for the full indexed
scope. The optional layer uses the existing filter, expansion, layout and note
controls. Closing it restores the authored view. Static relations never receive
runtime values or animation without a corresponding observation.

Python, JS/TS, JSX/TSX and Vue declarations are supported. CommonJS static imports
and ES imports can resolve local declarations. External packages, dynamic
dispatch, callback parameters, aliases and framework behavior may remain
unresolved. This is a source relationship index, not every AST syntax node, a
whole-program type checker, or a proof that a call executed. Interface/type-only
references, arbitrary variable data flow and every language-specific re-export
pattern require additional adapters. Parse errors and excluded implementation
are explicit incomplete coverage, never a successful empty graph.
