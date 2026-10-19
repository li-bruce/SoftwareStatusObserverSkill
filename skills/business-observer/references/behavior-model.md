# v3 属性图与证据契约

`schema_version:3`；`intent` 是项目内需求 JSON；`source_files` 明确包含业务、适配、探针、页面等要绑定的文件；`nodes`、`edges`、`overview`、`scope` 是必需项。可改写示例在 `assets/behavior.example.json`，它说明结构，不强制其仿真业务或路径；不依赖图数据库。

node：稳定 id，kind(action/function/decision/wait/effect/data/state)，label，summary，source={path,symbol}，capture={in:{字段:类型},out:{字段:类型}}；可选 parent、requirements、inputs/outputs（数据含义）、predicate、resume。可执行节点必须有 source。capture 类型可为 string/number/boolean/scalar、对象字段字典或单项数组 schema，未列字段丢弃，超长/错误类型拒绝。

edge：id/from/to/type/label/evidence。type=flow（允许流程）、data（参数/值依赖）、guard（条件限制）、contains（分组）。这些都是模型声明，不是已执行事实。overview 指定节点布局；隐藏节点仍在同一图内，parent 不新增事实。

event：id、run_id、seq、build_id、model_revision、entity、attempt、node、phase、call_id、parent_call_id、basis={param_version,epoch,clock}、inputs、outputs、depends=[{event,type}]、observed_at。phase=enter/return/read/decision/wait/commit/change/error；type=data/control/trigger/recheck。数据和控制引用须属于同一 attempt；跨 attempt 只允许显式 trigger，跨期重新授权标 recheck。缺引用、不同 build 或版本差异不能悄悄拼接。

调用归属用 call_id/parent_call_id；输入输出依赖用 depends。相邻 seq 只给显示顺序，不产生依赖。引用存在性不能证明引用语义正确；需要审阅插入点并检查实际字段。

`/api/view`：model、manifest、binding_status、events、health、authority。authority 包含 entity、basis、state、parameters、approvals、relation、effects，均由真实业务存储适配；viewer 不成为业务真相。若历史 snapshot 则另带 historical=true、case_label。当前有效事件要求 build、entity 和 basis 对应，时钟/关系变化也失效；历史事件仍可查看当时输入输出。

manifest 保存文件 hash、model/intent hash、绑定函数行号与快照片段、calls/guards。新源码变化必须显示 stale；页面源码为加载时快照，磁盘新版另做变更证据。unknowns 明确扫描遗漏和非静态可判事项。

viewer 的领域配置来自模型：default_node；presentation.subject/states/command_panel_url（本地路径）；overview 和 views.dependencies 的 node/x/y 布局；edge.short_label/overview_route 只改变呈现。节点可提供 predicate/resume/reason_labels/inspect_target；candidate_table 配置子函数、身份字段和布尔条件列；aggregate 配置重复候选调用的 id/result 字段。同一 parent_call_id 分组，整体结果与逐条结果都保留。普通模型无需候选表。`/api/view.available_cases` 为可选历史现场列表，未接入时只有当前。模板不硬编码领域节点 ID；大型布局与业务权限仍由项目实现负责。

最小 function 节点例：`{"id":"price","kind":"function","label":"计算费用","summary":"将数量变换为费用","source":{"path":"domain.py","symbol":"calculate_price"},"capture":{"in":{"quantity":"number"},"out":{"amount":"number"}}}`。把 schema 与源码/实际字段对应好，再 capture；不能复制示例后只改名称。

未来 commands 只存命令名、输入契约和 guards；当前 viewer 没有执行接口。不要把图的可编辑性当业务可执行性。
