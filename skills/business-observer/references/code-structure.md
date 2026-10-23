# Optional code structure

Use the existing source adapters and viewer. Keep business labels and runtime
state in the authored model; source-derived declarations are a separate projection
within the same graph. The feature is available in both drive and observe modes.

The default overview stays compact. Tell the developer they can select a region
and enable **Local code**, or choose **Code structure** for the full indexed scope.
Both use the same dragging, expansion, notes, source navigation and filters.
Static nodes are not recorded business operations.

```bash
python SKILL/scripts/bo_code.py scan --root PROJECT --out .stategraph/code-export.json
python SKILL/scripts/bo_code.py query --root PROJECT --focus NODE_ID --depth 1 --out review/code-focus.json
python SKILL/scripts/bo_code.py check --root PROJECT
```

Use the project's reviewed `sync.json` source scope. Missing parsers, unsupported
languages, syntax failures and excluded implementation must remain visible gaps.
Do not restrict the index to nodes that already exist in the business graph.
Do not identify functions by line numbers or infer ambiguous targets by labels.

Once enabled, `.stategraph/code-graph.json` is refreshed by viewer requests and
`bo_sync scan/watch`. Run maintenance after coding and before verification. The
verification command independently checks the current source against this export;
it must fail if declarations, relations or file coverage have drifted. Preserve
the failed check before refreshing and retesting. Source code edits do not imply
that a native application has reloaded; keep its build status distinct.

During each relevant batch, verify the changed feature from its business node
through its source binding and actual runtime evidence. For source changes, cover
new/deleted declarations, call direction, parameter changes and unresolved targets.
Exercise focused and complete views, boundary relations, saved layout/notes and
source revision checks. Verify opening/refreshing/filtering the code view produces
no business events. Keep runtime and business checks independent of static edges.

The supported relationship index covers files, classes, functions, declared
parameters, imports, inheritance and syntactic call occurrences in Python,
JS/TS/React/Vue. It does not prove dynamic dispatch or arbitrary variable flow.
Bounded queries report omitted content; use JSON export for the full indexed
scope. Never describe a bounded canvas as every possible execution path.
