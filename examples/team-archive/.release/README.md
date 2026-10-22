# 发布时已审阅的记录

`tools/archive_demo.py` 在全新目录恢复这里的状态记录和 manifest，然后先执行 `change_sync check`。它不会为修改后的代码生成新验收。

独立试验最后通过的是 `change-004`，其完整记录保存在 `review/changes/change-004`。发布副本另建 `release-v04`，只调整 AGENTS.md 中的 Skill 路径和开发说明，之后重新运行 120 次场景、参数检查及测试。业务代码、模型、探针和构建保持不变。

首次 Git 导出发现嵌套换行规则改变了包初始化文件；`release-bytes-v04` 在示例自身规则中保留原字节，再次完整验证，应用构建仍相同。这些记录保留为版本来源。

当前活动记录为 `recorded-views`，包含交互分组、类型图例、操作记录与回放、分析视图和共享节点。每次修改都重新执行正常验收；记录和截图见 [本次审查材料](../../../docs/review/recorded-views/README.md)。修改项目时继续正常变更流程，不要覆盖已发布记录。
