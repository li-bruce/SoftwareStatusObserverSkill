# Catalog and synchronization acceptance

Date: 2026-10-24 (Asia/Shanghai).

The collector integration suite uses isolated loopback PostgreSQL, MongoDB,
Redis and Neo4j services. It creates and removes only its `bo_test_catalog_*`,
`bo_test:catalog:*`, and `BOTestCatalog*` synthetic fixtures. SQLAlchemy SQLite
tests use temporary real database files. No production database was used.

## Failures found and changes verified

- The first live run passed MongoDB, Redis and Neo4j, but PostgreSQL could not
  import Psycopg's binary driver: Windows application control blocked its DLL,
  and a separate libpq installation was unavailable. The acceptance environment
  switched to the pure-Python pg8000 driver. The same PostgreSQL schema,
  migration and constraint assertions then passed. See the
  [initial summary](catalog-live-before-driver-fix.json),
  [retest summary](catalog-live-after-driver-fix.json), and
  [retest log](catalog-live-after-driver-fix.log).
- Initial SQLite unit fixtures left native connections open after transaction
  contexts, causing Windows file cleanup failures. Fixtures now explicitly close
  them. Collector engines already dispose their connections.
- Synchronization initially allowed a metadata collection exception to escape,
  omitted default/constraint comparisons, and accepted an operation reporting
  an unconfigured target. Regression cases exposed these gaps; the updated
  boundary returns a failure without replacing prior good files, checks declared
  constraints, and checks required runtime targets.
- Exporter stderr used the local Windows encoding; decoding it as UTF-8 raised a
  reader-thread error. Export handling now keeps stderr out of the public report
  and decodes the JSON stdout separately.
- Application ODM validation is now distinguished from database-enforced
  validation. This avoids treating a normal Mongoose model as a MongoDB validator
  or foreign-key constraint. The explicit application provenance does not disable
  source freshness or operation runtime checks.
- SQLAlchemy can create an implicit PostgreSQL sequence for an integer primary
  key without an explicit model default. The declaration exporter now leaves
  that unspecified default open while still comparing explicit defaults. The
  [final live run](catalog-live-final.json) verifies this against PostgreSQL.
- A SQLite expression index cannot be fully reflected by SQLAlchemy. Reflection
  warnings now produce explicit partial coverage, rather than silently reporting
  a complete catalog. Native expressions remain subject to conservative matching.
- Connection identity originally omitted query-string database selectors. A
  Redis `?db=1` to `?db=2` regression exposed the gap. Routing selectors now
  participate in identity; password rotation alone does not change it. This also
  verifies that two SQLite files with identical schemas need separate evidence.

## Covered behavior

The real-server cases verify schema add/rename updates, SQL primary/foreign keys,
check constraints, server defaults and indexes; MongoDB validators, unique
indexes and unvalidated collections; bounded Redis type sampling; Neo4j labels,
relationship types and unique/index property changes. Catalogs contain metadata,
not the inserted synthetic record contents.

Synchronization tests verify stale check failures, native exporter reruns after
source changes, unapplied migrations, source and graph consistency, exact
preservation of personal view bytes, strict catalog/config validation, and failure
recovery. Watcher tests use a real local HTTP server to verify build replacement,
preserved preferences, old recording/event exclusion, rejected stale producer
events, unchanged-tick stability and recovery from an unavailable database.

MySQL uses SQLAlchemy reflection but was not live-tested in this suite.
Cassandra, Elasticsearch and DynamoDB do not have collectors in this version.
Neo4j property-value scans, full database execution plans and row-level lineage
are outside this implementation. These boundaries are retained in the catalogs
and the Skill reference.
