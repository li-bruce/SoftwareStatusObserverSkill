# 模型、证据与观测契约 v1

`assets/model.schema.json` 和 `event.schema.json` 为结构契约。model_tool 的轻量校验器仅支持这些 schema 用到的 JSON Schema 关键字，未知关键字直接报错，不冒充通用 JSON Schema 引擎。

节点 kind：object、action、condition、fact、effect、wait、state。层 level 为 0（业务）/1（条件）/2（事实）；源码在侧栏，通过 bindings 下钻。parent 仅分组。条件 operator 为 predicate/all/any；all/any 的 dependencies 指向事实或条件，与 supports 边一致。

边 type：acts_on（动作→对象）、supports（事实/条件→条件）、requires（条件→动作）、produces（动作→效果）、transitions_to（动作/状态/等待→后继）、describes（事实→对象）。方向体现关系语义，不都表示执行顺序。

bindings 的 node/path/symbol/role 是开发者声明。独立 AST capture 检查 path/symbol 是否存在并产生 line/end_line/file_sha256/ast_sha256/calls/guards；source_roots 为明确扫描范围。manifest 的 build_id 绑定意图、模型和全部扫描源码；必须在加载业务模块前捕获/核对，运行期间修改源码要提示已过期并重启。散列不是远程证明，解释器、动态 monkey patch、未列文件和依赖仍在边界外。

运行事件分 fact、decision、transition、effect；每条含 event_id、run_id、seq、build_id、model_revision、request_id、attempt_id、tx_id、entity_id、node_id、observed_at、kind、payload。payload 是允许列表中的扁平标量或标量列表，不容许任意嵌套正文。

各类 payload 必填字段如下；字段仍须同时列入 Probe 的允许列表。应用负责提供正确语义，探针不自行推断“已提交”。

| kind | 必填字段 | 说明 |
| --- | --- | --- |
| fact | value、source、version、quality | quality 为 committed/cache/intermediate/inferred/unknown；valid_until 可选或 null |
| decision | status、reason、evidence、basis_version | status 为 true/false/unknown/stale；evidence 是声明依赖的节点 ID，包含子条件；同次判定须同版本 |
| transition | from_state、to_state、outcome、basis_version | 等待也要提供状态；拒绝可保持状态不变 |
| effect | effect_id、outcome、basis_version | 仅成功提交后记录，须与权威效果 ID/事务核对 |

transition/effect 可显式提供 status 表达业务结果。viewer 对 waiting/denied/rejected/failed/blocked/cancelled 显示未满足，对 committed/delivered/completed/already_done/changed/observed 显示已观察；其他 outcome 默认为未知，不能仅因收到事件就标绿。自定义业务结果应提供明确 status 或适配 viewer，并实测拒绝与成功两种颜色。

只读 viewer 读取 `/api/view`：`model`、`manifest`、`events`、`health`、`binding_status`、可选 `authority`。manifest.bindings 提供位置和 snippet；health 至少含 enabled/dropped/errors/queued，binding_status 是 current/stale/unknown。authority 是独立业务读取的已脱敏视图；通用概览通过 `authority.summary={state,version,clock,effect_count}` 接入，各字段可省略。version 必须对应当前所选对象；多对象需要按筛选传递或适配，不能拿全局/别的对象版本冒充。clock 与 valid_until 使用同一业务时间单位。缺少 summary 的领域特有结构不会崩溃，未接入字段显示未知而不是零。旧协作示例的 facts/deliveries 结构保留兼容。可选 authority.receipts 提供 attempt_id/command/outcome 供历史标题使用。网络失败显示断连；数据/渲染错误另行说明。

页面事件过滤按 run/entity/attempt，历史与当前快照分开。旧 decision 的 basis_version 不等于当前状态版本时标过期；事件属于不同 build 时不叠加成当前执行证据。事实 valid_until 超过当前业务时间时同样过期。无事件的节点显示未观测，不把静态图当运行路线。

业务视图选择一个动作展示一跳关联，避免将多个业务动作堆成重叠全图。条件视图从选中条件展开支持与下游。历史时钟节点默认为 f_clock；自定义时钟节点可在 `/api/view` 顶层提供 clock_node。大规模图、跨对象版本与更复杂布局仍需按项目扩展。

`/api/view` 可提供 presentation：title、purpose、states（状态值到业务名称）、commands（命令到业务名称）、outcomes（回执到业务名称）、values（原始值到人可读文字）和 nodes。nodes 以 node ID 为键，每项可含 label、description、failure（不满足时的业务原因）、fields（数组事实对应的字段名）、values（该事实的值翻译）。这些字段只用于文字；节点颜色和有效性仍来自真实事件及版本。value 映射对有多个不同字段的数组需谨慎，不能把参数版本 1 误译为“启用”；复杂数组应提供单独的业务事实节点或专门格式化函数。

默认页面仅显示业务结果、流程和直接条件。源码/版本/ID/JSON 在默认收起的技术区；操作历史默认收起，选历史后应明确提示并可返回当前。领域页若需要更多步骤或事实，应按阅读目标加入，不把完整采集字段一次摊给用户。泛化能力、覆盖声明、测试计数放开发文档。

可选 presentation.edge_labels 将模型边文字映射为更易懂的业务用语；nodes 中 field_values 是按数组索引排列的值映射，优先于整项 values。这样批准状态 1 可显示“已批准”，参数版本 1 仍保持数字。

`model_tool.py events --root ... --model ... --events ...` 核对事件结构、类型、依赖 ID、版本和同次尝试 AND/OR 值的一致性；缺依赖列 unknown。它不证明叶子条件或基础事实为真，仍须读取权威结果/源码核对。旧版本事件应在对应旧源码/模型上验证，不能用新 build 冒充原证据。
