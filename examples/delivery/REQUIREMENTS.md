# Example requirements / 示例需求

This is a synthetic local development specification, not a production workflow.
本例使用合成文本、单进程线程和 SQLite。

| ID | Rule |
|---|---|
| R1 | Content and capacity edits increment the parameter version. Approvals bind to that version. / 修改文本和名额产生新参数版本，授权绑定版本。 |
| R2 | An engineer needs at least one unrevoked, unexpired grant matching project, team and version. Reevaluate alternatives after revocation; otherwise wait. / 执行者需要匹配范围及版本的有效授权；撤销后重新判断替代授权。 |
| R3 | Draft, checking, ready, completed, waiting, failed and cancelled are explicit states. Retry requires an explicit command; cancelled work cannot commit. / 状态明确，恢复需重新执行；取消后不能提交。 |
| R4 | Calculate SHA-256, then recheck version, role and authorization in the commit transaction. / 计算摘要，提交事务内再次检查版本、角色和授权。 |
| R5 | At most one artifact is committed per parameter version, including concurrent or repeated commits. / 同版本并发或重复提交只有一份交付物。 |
| R6 | Disabled or failing observation must not change the business result. The core has no dependency on observer code. / 观测关闭或故障不改变业务结果，核心不依赖观测实现。 |
| R7 | Checksum and synthetic `SECRET:` checks share 1–2 per-run slots, wait for capacity, return slots, and both must pass. These constraints are part of the running state machine. / 两项检查共享本次名额，等待、归还、全部通过均由原状态机执行。 |
| R8 | Query every declared activity instance by run and version. An old run cannot overwrite or commit a newer run. Preserve interrupted states and render historical moments without future results. / 所有声明的活动实例可查；旧运行不覆盖新版，回看不借用未来结果。 |

Not covered: distributed transactions, global worker pools, production identity,
arbitrary local variables, durable worker recovery or graph-driven commands.
