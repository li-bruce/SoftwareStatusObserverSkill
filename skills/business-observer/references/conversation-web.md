# 从对话到运行的同一张图

用户在 Codex 等开发工具中讨论、确认和修改。Web 页面只提供图的查看、拖动、展开、筛选、批注和调试；没有答题、业务确认或修改业务规则的接口。

## 开始讨论

AI 根据对话建立 `discovery.json`，结构见 [需求提炼](requirements-dialogue.md)。尚不确定的规则保持 open，来源分别记为用户、推断或项目规则。先运行 `requirements_dialogue.py validate`；`check` 仍会拒绝未解决的关键问题。不要为了打开图把问题写成已解决。

每个设计节点使用稳定 `id`。若已有实现或提前预留实现标识，填写 `model_nodes`；第一项是设计投影使用的主标识，其余是讨论时关联定位的节点。设计节点可用 `parent` 指向同一份设计中的父节点；循环和缺失父节点报错。状态节点显示为状态类型，资源节点显示为资源类型。此阶段没有运行实例或实际值，不伪造执行记录，也不把草图作为合法可执行状态机加载。

设置 `project_id`、简短 `title` 和稳定的 `layout_id`，后续运行服务返回同一 `layout_id`。草图的主节点标识进入实现图；多个节点不能偷偷合并为同一主标识。真实的多归属用共享关系表示。布局和批注保存在项目自己的 `bo_stategraph/config/views/local.json`。

AI 执行（`<skill>` 指本 Skill 的实际目录）：

```bash
python <skill>/scripts/bo_web.py serve --root <project> --port 8830
python <skill>/scripts/bo_design.py focus --root <project> --decision D1 --label "核对下载是否需要等待预览"
```

将 `http://127.0.0.1:8830/graph` 打开在开发工具的内置浏览器。页面自动显示并高亮本轮相关节点、边和包围区域；用户可取消聚焦，继续查看完整图。说明限 120 字，不在页面重复整段对话。按节点定位可用 `--nodes node_a node_b`；清除讨论范围可用 `focus --nodes`。

收到对话答案后，由 AI 修改需求、决定、图和检查场景，然后重新设置聚焦。图会自动重新读取。需求已变而聚焦未更新时，页面提示“讨论范围待更新”，不会假装仍是当前讨论。`focus` 只写展示配置，不改决定或检查结果；既有需求历史检查和源码映射门禁继续生效。

## 进入开发和运行

项目服务复用相同 Web 资源，通过 `BOWeb(root, assets=项目图资源目录)` 接入两项行为：

- GET 前调用 `allowed(path)`，被关闭的图路由返回 404 和 `code: bo_web_disabled`；`get('/api/design')` 只读取对话聚焦配置。没有设计回答的 POST 接口。
- 业务页面的图入口标记 `data-bo-entry`，返回 HTML 前用 `entry_html` 处理。业务自己的状态与操作接口独立于图接口，关闭 Web 仍能正常工作。

此接入放在 `integrations/`，业务方法不导入 Web 模块。项目以原来的运行视图替代草图数据：同一节点关联源码、关键参数、状态和事件。运行中也可由 AI 更新当前讨论范围。AI 必须检查草图与实现的稳定标识、布局标识，以及未映射的节点；打开页面不算映射验收。

代码中的公共核心、执行器、声明和参数仍按原有严格校验执行。完整 gate 继续分别报告实现映射、状态约束和业务规则。

## 交付时控制 Web

```bash
python <skill>/scripts/bo_web.py mode hidden --root <project>
python <skill>/scripts/bo_web.py mode disabled --root <project>
python <skill>/scripts/bo_web.py mode visible --root <project>
python <skill>/scripts/bo_web.py status --root <project>
```

| 设置 | 行为 |
| --- | --- |
| visible | 显示入口，图与调试 API 可访问。 |
| hidden | 刷新业务页面后隐藏入口；已知图地址仍可访问。它不是访问控制。 |
| disabled | 关闭图页面、图资源、源码、记录、个人配置和图导出的 HTTP 接口；已打开图停止展示。恢复 visible 后可继续查看。 |

设置保存在 `bo_stategraph/config/web.json`，重启保留；不会改变执行器、采集模式、Python 查询、结构导出或个人布局。它关闭图功能，业务服务进程仍运行。非法配置报错，不默默启用。若需要停止记录或关闭采集，另按记录/探针机制处理，不把关闭页面当作采集关闭。

要交付不包含调试 Web 与采集实现的代码包，先通过项目 gate，再执行：

```bash
python <skill>/scripts/bo_web.py package --root <project> --out dist/core.zip
```

它复用 `architecture_guard.py package`：要求项目有有效的 `ownership.json`，新 ZIP 不能覆盖旧包；保留业务状态机和中立接口，按明确的核心文件清单排除页面、采集器、集成服务和个人配置。必须解压并运行业务测试，不能只检查 ZIP 文件名。原项目保留，便于继续开发和恢复调试；不要通过批量删目录或改业务函数“移除 debug”。
