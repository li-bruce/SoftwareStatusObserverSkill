# 实际实现与交付投影的对应

清单由开发 AI 维护，用户不需要填写。`sync.json` 必须配置 `mapping_contract: "mapping.json"` 和 `require_mapping_witnesses: true`。清单定义本阶段检查哪些实现，业务预期另行保存。

`mapping.json` 使用 `schema: bo-mapping/v1`：

| 字段 | 用途 |
|---|---|
| cases、modes | 明确场景和 on/off/fault 模式，不从提交的结果倒推应检查范围 |
| source | 实际存储读取器或函数结果的来源 |
| actual_collection | 从每项 run 取得实际实例列表的数组路径，如 `["authority_snapshot","runs"]` |
| actual_id | 实际记录的稳定实例身份路径，如 `["id"]` |
| fields | 每项有唯一 id、实际图 node、实际字段 actual 路径、observed 中的 mapped 路径 |
| export | 指定公开导出的 case、mode |

每个实例至少比较 state、完整 revision、build_id 和全部声明的 context 字段。有活动执行时还比较完整 configuration。包装不同时可为 configuration 指定 keys；实际配置必须恰好包含这些已审查键，新增字段也须维护清单。零实例也必须经过实际列表与投影列表的核对。

字段示意：`{"id":"slots","node":"available_slots","actual":["slots"],"mapped":["context","slots"]}`。node 必须替换为项目真实图节点。actual 必须独立读取，不能复制投影。

每项 runs 保留原 case、mode、events、业务 observations 和实际存储记录，并增加：

```python
machine = bo_machine(actual_snapshot)
run["projection"] = {
    "build_id": build_id,
    "machine": machine,
    "instances": graph.bo_instances(machine),
}
```

顶层 stategraph_export 通过公共 `graph.bo_export(runtime={"machine": selected_run["projection"]["machine"]})` 产生。selected_run 必须是清单指定的那次运行。它使用与页面、Python 查询相同的适配器，不能为检查另造理想投影。

检查器从实际交付投影读取 mapped，核对场景集合、实例、修订、构建、字段以及公开导出。原 mapping_checks 仍执行，不删除原对照或业务断言；报告分别给出 witnesses 与 projection_checks。

清单进入候选指纹和变更基线。新增覆盖可以加入；移除场景/字段或改变原绑定会阻止收尾。技术迁移须保存旧绑定、增加新绑定并验证迁移，不能重新 begin 隐藏退化。当前 source_moves 不自动改写此清单。

必测反例：缺公开实例、缺字段、错对象/返回值、旧修订、减少场景、公开导出与另交的相等对照脱节。真实业务违规且投影准确时，映射可通过，状态约束或业务规则仍失败。有限清单不证明任意自然语言含义；未执行路径、动态代码和外部服务仍须报告范围。
