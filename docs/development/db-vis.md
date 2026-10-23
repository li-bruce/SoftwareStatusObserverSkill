# Database observation

Branch: `db-vis`, based on `dev` (`ab14ff7`). Implemented and locally verified on 2026-10-24.

## Delivery plan

- [x] Versioned database configuration and catalog contracts, stable identities, provenance, and explicit coverage limits.
- [x] SQLAlchemy relational metadata, MongoDB document metadata, Redis key patterns, and Neo4j property-graph metadata. Reuse maintained open-source libraries.
- [x] Native data-operation capture linked to existing events: actual queries, result summaries, selected parameters, transformations, commits, rollbacks, and failures. Exclude observer collection and reporting at entry.
- [x] Automatic catalog refresh and source fingerprints during development; stale export and mapping checks must fail.
- [x] Existing Web graph: data views, typed nodes/relations, inline structure and runtime details, recording/replay, preserved layouts.
- [x] Skill dialogue: reuse existing choices; offer storage recommendations when a choice is needed, record the user's selection, configure the appropriate model layer and capture automatically.
- [x] Real database and browser acceptance, failures/repairs/retests, and unchanged existing checks.

The structure declaration, actual catalog, and observed operations retain separate provenance in one graph. Observed samples are not complete schema constraints. A successful statement is not a committed transaction. Result capture must not consume a cursor ahead of the application. Unsupported metadata is reported, never silently discarded.

See [the review and final evidence](../review/db-vis/README.md) and
[the runnable example](../../examples/database-observer/README.md).
Local acceptance covers real SQLite, PostgreSQL, MongoDB, Redis and Neo4j,
Python and Node clients, the bilingual viewer, and both existing examples.
GitHub Actions is configured but has not run for this local branch.

Further adapters, MySQL live acceptance, database-internal execution plans and
automatic column lineage remain separate work. The native application launcher
must reload producer settings when the observer publishes a new build identity.
