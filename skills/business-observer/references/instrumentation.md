# 显式探针接入

先把 `scripts/probe.py` 复制到项目或用固定路径导入（无需 pip 包）。应用仍拥有业务与事务。探针只接收约定的安全字段。

```python
from probe import Probe
probe = Probe(path="events.jsonl", build_id=build_id, model_revision="1",
              fields={"fact": {"value", "source", "version", "quality"}},
              nodes={"stock"})
# 在业务事务成功 commit 之后；capture 内构造载荷，构造失败也不影响业务
probe.capture(lambda: [{"kind": "fact", "node_id": "stock", "entity_id": "item-1",
    "request_id": "request-1", "attempt_id": "attempt-1", "tx_id": "tx-1",
    "payload": {"value": 3, "source": "sqlite:items.stock", "version": 4,
                "quality": "committed"}}])
# 正常退出/测试时 flush；不要在热业务路径等待磁盘。
probe.flush(timeout=2)
probe.close()
```

关闭：构造时 enabled=False。故障注入：提供会抛异常的 sink；队列满测试使用小 queue_size 与受控阻塞 sink。采集健康状态读取 `probe.health()`；flush 超时表示采集未完成，不能把待投递计为已写事件。

允许列表针对业务采集点，不能防止开发者故意把秘密放进允许的 value 字段；需人审字段语义和注入样本。不要把任意对象 repr、异常详情或 SQL 参数直接采集。默认字符串/列表有长度上限，嵌套字典被拒绝，事件超限丢弃并计数。

投递在提交之后，因此进程在 commit 与 enqueue 之间崩溃可丢事件。本实现是观测，不是审计 outbox；对 exactly-once、跨进程排序和崩溃恢复不作保证。真实效果核对必须读业务权威状态。队列避免 sink I/O 阻塞业务，但 CPU/内存耗尽、错误插入位置、卡死的载荷构造仍有影响，不能宣称绝对无干扰。
