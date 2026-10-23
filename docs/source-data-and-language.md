# Source depth, data relationships, and language policy

This note separates the current implementation from proposed extensions. The public introduction must use the same distinction.

The [development branch roadmap](development/dev-roadmap.md) tracks source neighborhoods, database schema, and API relationships with their current implementation boundaries and acceptance requirements.

## Can the lowest layer cover the whole codebase?

Yes, as an **indexed source view**. That does not mean every possible call can be resolved correctly or that every indexed call ran.

The current shared source inventory walks configured project-owned files independently of the existing business graph. Python AST and JS/TS/SFC adapters identify symbols, parameters, imports, calls, and entrypoints. The optional code layer now supports interactive local neighborhoods and a whole-index view, with bounded rendering and complete JSON export. Source enrichment also adds selected relationships to the authored graph's coverage obligations.

The implementation keeps these sources of evidence separate:

| Information | Source | Meaning |
|---|---|---|
| Files, definitions, references, signatures | Language parser or semantic index | The code exists at a bound revision. |
| Potential call/data-flow relationships | Static resolver | The implementation may use this path. |
| Actual calls, values, state changes | Explicit runtime capture | This instance used this path with these recorded values. |
| Business grouping | Confirmed dialogue plus source bindings | This implementation belongs to the discussed behavior. |

SCIP is a language-independent format for code-navigation indexing; it can supply definitions and references without making them execution evidence. CodeQL distinguishes syntax from data flow and explains why dynamic targets, library code, and aliasing complicate analysis. Neither source indexing nor a data-flow graph removes the need for runtime evidence. [SCIP specification](https://github.com/scip-code/scip), [CodeQL data-flow analysis](https://codeql.github.com/docs/writing-codeql-queries/about-data-flow-analysis/)

The recommended shape is one source index plus lazy projection: business node → selected implementation neighborhood → file/class/function detail → source. Shared functions remain one identity with multiple semantic memberships. Project libraries can be indexed separately; vendored code, dependencies, generated output, and the observer itself need explicit scope classifications.

### Cost

| Work | Likely cost and limit |
|---|---|
| Parse owned source and retain symbols | Offline CPU, memory, and index storage. It need not add application runtime overhead. |
| Resolve local/imported calls | More language-specific work, especially across modules and builds. |
| Resolve reflection, callbacks, dependency injection, dynamic imports | Substantially harder; retain unknown targets rather than fabricate completeness. |
| Show an entire graph at once | High visual and rendering cost; use neighborhood queries, limits, and progressive expansion. |
| Observe every function/value | Runtime and storage overhead; this is a different requirement and is not proposed by source indexing. |

No project-size benchmark was measured for this proposal. A file-completeness check can verify that all configured files were visited. It cannot prove a complete or exact dynamic call graph. Future acceptance should include new/deleted files, cross-module calls, unresolved targets, source moves, index-to-build identity, and bounded graph queries.

## Should data structures and database relationships be included?

Yes, where they explain business decisions and effects. Add them to the same typed graph, collapsed by default. Do not load every table or database row into the opening business view.

The data layer implements a versioned database catalog, SQLAlchemy metadata and native model exports, MongoDB/Redis/Neo4j collectors, and selected data-operation capture. It retains the existing typed fields, parameters, class/source relationships, and independently checked authoritative values. Automatic column lineage remains outside the implementation. See [the implemented scope](../skills/business-observer/references/database-observation.md).

The data layer distinguishes three kinds of evidence:

1. **Declared structure:** classes, DTOs, fields, types, tables, columns, primary/foreign keys, constraints.
2. **Implementation use:** functions that read/write/map these structures; queries and transformations supported by source or explicit bindings.
3. **Runtime instance:** selected row/entity IDs, revisions, actual reads/writes, and field changes associated with a run or transaction.

An ER relation says that a key references another table. It does not establish permission, ownership, business causality, or a runtime transfer. A DTO class is not a database table; a class is not an individual instance. These need separate relation types and stable identities.

SQLAlchemy reflection demonstrates a useful read-only schema source: table names, columns, keys, indexes, and constraints can be obtained through its Inspector. OpenLineage distinguishes dataset schema from column-level input/output lineage; this is a useful separation to borrow, without requiring this project to adopt its whole platform. [SQLAlchemy reflection](https://docs.sqlalchemy.org/en/20/core/reflection.html), [OpenLineage schema facet](https://openlineage.io/docs/spec/facets/dataset-facets/schema/), [OpenLineage column lineage](https://openlineage.io/docs/spec/facets/dataset-facets/column_lineage_facet/)

Implemented data roles are store, dataset, column, query, and transformation, carried by existing data/function nodes. Typed data relations express reads, writes, references, field mappings and transformations. DTO/entity-instance projection and automatic column lineage remain future work. Schema and viewer changes require explicit versioning and regression tests.

Start from migrations or an approved read-only catalog connection. Use schema/migration fingerprints to detect drift, independently verify selected effects against storage, and keep runtime capture allowlisted. Secrets, arbitrary records, and complete database contents are unnecessary for explaining a state change.

## English maintenance, user-language interaction

The Agent Skills specification defines the folder, metadata, and Markdown instruction format. It does not require an English instruction body or define an automatic locale protocol. English-first instructions and user-language interaction are a project policy, implemented through guidance and UI localization. [Agent Skills specification](https://agentskills.io/specification)

This repository uses:

- English maintained source, comments, Skill instructions, and default README.
- Conversation in the user's language. Original answers and evidence remain original.
- English UI fallback and an explicit Chinese choice. The project stores the viewer preference.
- Stable IDs, protocol keys, state values, source bindings, and assertions independent of display language.
- Separate Chinese display catalogs and a Chinese README. User notes, aliases, source snippets, and recorded values are not translated by a page-wide replacement.
- Historical trials, accepted user requirements, release evidence, and deliberately multilingual test data retained with an English index.

For the viewer, an explicit URL language overrides the stored project setting; otherwise the saved setting is used, followed by the browser preference and English fallback. The product introduction defaults to English and allows a saved explicit Chinese choice. Browser language alone is not a reliable substitute for user control. [W3C language preference guidance](https://www.w3.org/International/questions/qa-lang-priorities)

## How this affects the development workflow

The opening graph comes from the same discovery data as Web. The agent posts it directly in conversation with a verified Web address, requests confirmation or correction, and preserves unresolved items. Viewing the page is not confirmation.

Business ambiguity goes to the user. Parameter bindings, callback targets, capture locations, and source ownership are reconciled within coding and require current-source and test evidence. Each coding batch inventories source, updates mappings and capture, executes the independent scenarios, and reports mapping, state, business, and project results separately.

A successful demonstration proves the cases actually run. It does not prove complete static resolution, all possible schedules, production suitability, or human usability.

