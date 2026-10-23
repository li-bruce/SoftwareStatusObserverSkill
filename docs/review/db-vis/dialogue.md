# Scripted database-selection dialogue

Date: 2026-10-24. This is a **scripted simulation**, with real CLI, native model export, SQLite migration, and runtime-query execution. It is not an independent LLM or human test. The existing graph is the shared integration fixture; this is a storage workflow test, not acceptance of a complete image-review product.

The maintained Skill was read before the trial; its exact SHA-256 and complete command results are in [dialogue.json](dialogue.json). Reproduce with `python tools/test_database_dialogue.py --out docs/review/db-vis`. `$TRIAL` in the record denotes the temporary project directory.

## Conversation

**1. Simulated user**

这是一个已有的本地图片审核工程，业务流程保持现状。这次把数据库接入状态图，先只在我自己的电脑使用，数据库还没确定。

**2. Simulated assistant**

按目前单机使用的范围，推荐 SQLite，Python 端使用 SQLAlchemy 管理数据模型。如果近期就要作为多人共用的服务部署，可以选 PostgreSQL。你这次希望先用哪一种？

Executed evidence: `initial-guide`.

**3. Simulated user**

先用 SQLite 和 SQLAlchemy。沿用现在的业务逻辑，不增加其他流程。

**4. Simulated assistant**

已按你的选择接入。图中可以看到 images 表、字段以及 list_images 的读取关系；实际查询已采集，观察器自己的统计查询没有进入记录。业务流程保持原样。

Executed evidence: `confirmed-guide`, `initial-sync`, `initial-check`, `runtime-query`.

**5. Simulated user**

在图片数据中增加一个 reviewed 字段，先保留现有流程。

**6. Simulated assistant**

模型已增加 reviewed，图中已标明这个字段还没有出现在实际数据库中；本轮检查暂未通过。我会完成对应迁移后再核对。

Executed evidence: `pending-migration-sync`, `pending-migration-check`.

**7. Simulated assistant**

迁移完成，实际数据库和模型中的 reviewed 已对应，重新检查通过。没有增加审核规则或新的业务步骤。

Executed evidence: `migrated-sync`, `migrated-check`.

**8. Simulated user**

另一个已有工程使用 MongoDB 和 Mongoose，继续沿用即可。

**9. Simulated assistant**

沿用 MongoDB 和 Mongoose，并接入相应的模型导出和查询采集。Mongoose 的应用校验与数据库中的验证规则会分别标明。

Executed evidence: `existing-mongodb-guide`.

## Executed command outcomes

| Step | Command | Exit | Outcome |
| --- | --- | ---: | --- |
| initial-guide | `bo_db.py guide` | 0 | 1 user question(s) |
| confirmed-guide | `bo_db.py guide` | 0 | 0 user question(s) |
| initial-sync | `bo_db.py sync` | 0 | valid=true |
| initial-check | `bo_db.py check` | 0 | valid=true |
| pending-migration-sync | `bo_db.py sync` | 1 | valid=false |
| pending-migration-check | `bo_db.py check` | 1 | valid=false |
| migrated-sync | `bo_db.py sync` | 0 | valid=true |
| migrated-check | `bo_db.py check` | 0 | valid=true |
| existing-mongodb-guide | `bo_db.py guide` | 0 | 0 user question(s) |

## Review

The initial prompt rendered one relevant tradeoff question. An explicit choice removed the question and released the coding tasks. The model change was exported automatically; an unapplied database migration failed both synchronization and independent checking, then passed after the real ALTER TABLE. An actual query produced two probe events and the observer's own query produced none. The existing-MongoDB choice was reused without a new selection question. The authored conversation adds no new business flow; this last conclusion is a transcript review, not a proof of arbitrary future AI behavior.
