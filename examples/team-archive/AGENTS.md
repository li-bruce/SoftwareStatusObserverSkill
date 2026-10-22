# 资料归档示例的开发约定

这是开发者调试示例，使用合成数据。主线设计、框架和编码方法不限。

每轮相关开发先读取 `../../skills/business-observer/SKILL.md`、`intent.json`、`discovery.json`、`behavior.json` 和当前验证结果。单独复制本示例时，先安装相同版本的 business-observer，并将这里的 Skill 路径改为实际安装位置。保留已确认规则和稳定节点 ID；观测与验证是开发时必须同步维护的部分。

首次运行由仓库根目录的 `python tools/archive_demo.py --prepare-only` 恢复已发布的验收记录，不自动接受修改后的内容。已有未完成变更继续原记录，不能新建基线遮掩遗漏。

行为修改前，在本目录记录本轮请求和确实允许修改的需求，例如：

```bash
python observer_runtime/change_sync.py begin --root . --change .stategraph/my-change --request "本次实际需求" --requirements R14
```

变更目录和需求 ID 按真实范围选择。开发时一起维护业务源码、实际状态机、`tooling/behavior_source.json`、`tooling/build_model.py`、探针与独立预期。生成后执行 `inspect → verify → accept → check`；审阅记录由 AI 填写，不能改写预期迎合实现，也不能只重新采集指纹消除错误。具体命令用工具的 `--help` 与 Skill 说明核对。

日常交付的正常验证入口：

```bash
python -X utf8 -B validate.py
```

它检查已验收的源码与图、层间依赖、规则测试和历史图事实；失败返回非零。它不会自行生成或接受新基线。Node 从 PATH 查找，也可通过 `ARCHIVE_NODE` 指定。

用户只讨论业务含义和查看每轮更新图。AI 自行维护中间材料，只在新的业务歧义或冲突时提问。保留拖动布局、名称、备注、历史版本和已有证据；新的迭代另存记录。业务核心不得导入观测实现，图上的名称与位置不得改变业务授权。

这些约定和检查入口不在后台监控所有编辑器。绕过入口的修改不能声称已同步；启动和图页面必须区分加载版本与磁盘版本。

默认由 AI 内部依据状态网引导开发，不额外暴露维护流程。用户明确不用该方法时，仅切换设计依据；两种方式都必须维护底层监控、按源码调整状态网、函数/参数映射、图和检查。未表态或改用普通代码不算退出。接入选择保存在 sync.json 的 stategraph；完整执行与查询位于 bo_stategraph/，observer_runtime 中的旧入口仅兼容委托。

每批相关修改后运行 `python observer_runtime/bo_sync.py scan --root .` 并处理 `.stategraph/maintenance.json`；独立源码扫描包括未跟踪的新文件。只有 verify → accept 才消除待办。个人视图位于 bo_stategraph/config/views/local.json，不随生成覆盖。阶段结果分别报告实现映射、状态约束和业务规则。
