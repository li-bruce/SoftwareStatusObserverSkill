# 插入语义探针

通过 `bo_upgrade.py` 安装公共运行库并记录散列，包含 `semantic_probe.py` 和 `bo_retention.py`。文件接入使用 `Pins(model, build_id, path=project_root / "data/events.jsonl", project_root=project_root, enabled=True)`，自动加载 `bo_stategraph/config/retention.json`。仅提供 path 时也有默认容量边界，但不会猜测项目根目录。配置错误在构造时抛出；运行中写入失败记录到 health，不改变业务结果。

每次业务尝试由 `pins.attempt(entity)` 创建 Trace；`trace.record(node, phase, basis, builder, depends=..., call_id=..., parent_call_id=...)` 的 builder 返回 `{inputs,outputs}`，并在隔离块内运行。record 返回的 event_id 只供后续观测关联，业务不得依赖它是否存在。自定义 sink 必须连接 `EventHistory` 或项目自己的有界实现，并验证容量与丢失提示；队列有界不等于输出文件有界。

```python
result = calculate_price(quantity)  # 原有业务计算
observed = trace.record("price", "return", basis,
    lambda: {"inputs": {"quantity": quantity}, "outputs": {"amount": result}},
    depends=[(input_event, "data")])
allowed = result <= current_limit  # 原有判定仍由程序执行
trace.record("limit", "decision", basis,
    lambda: {"inputs": {"amount": result, "limit": current_limit},
             "outputs": {"allowed": allowed}}, depends=[(observed, "data")])
```

先取得业务值，再在原位置记录实际读取/判断。参数传播记录函数接收值与返回值；业务 guard 使用同一计算结果，不让观测端二次求值替代原判断。只有事务成功后记录 commit，并用效果 ID 与真实数据库核对。

显式选择字段；即使 schema 允许 string，也不要把令牌/异常全文/业务正文塞进它。禁止自动 locals、repr 和 SQL 参数抓取。构造异常、字段拒绝、队列满、sink 故障均计入 health；页面显示缺口。同步 builder 必须是短小的字段复制，不能做网络查询或阻塞操作。

测试 on/off/fault 对比业务状态、返回结果和效果；以真实数值和事务 ID 核对。还要检查 builder 失败、队列满和敏感样本。关闭时不调用 builder。异步输出有 commit→入队→落盘崩溃窗口，不是审计 outbox；有界队列不能证明绝对零开销或对资源耗尽免疫。

可向 OpenTelemetry 适配 attempt→trace、call→span、semantic point→event、explicit cross-attempt trigger→link。当前参考实现为本地 JSONL，不宣称实现 OTel 协议。
