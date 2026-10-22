# Python 独立状态网

状态网是项目的一部分，长期保留；采集器和调试页面可以单独启停或裁剪。

## 两个独立选择

| 配置 | 含义 |
|---|---|
| development_mode: guided | AI 内部依据已确认的状态网安排开发，用户可采用任何框架 |
| development_mode: observe | 用户明确拒绝上述引导，AI 跟随其实现维护状态网与监控 |
| execution_mode: drive | 项目执行器消费同一状态声明 |
| execution_mode: observe | 普通代码或已有执行器决定结果，适配器读取实际状态 |

未表态或使用普通函数不构成退出引导。两种开发方式都必须维护映射、探针、展示和收尾检查。用户不必选择这些配置。

## 源码组织

```text
app/                         领域行为和存储
app/ports.py                 中立、失败隔离的 bo_ 事件接口
bo_stategraph/
  __init__.py                公共 BOStateGraph 查询/导出
  bo_contracts.py             共同声明、类型及层级校验
  execution_contract.py     活动、资源、等待、汇合约束
  workflow.py               项目原有完整执行器及其声明
  query.py                  从实际存储读取全部实例的投影
  config/retention.json     观测缓存和日志保留限制
  config/views/local.json   个人布局、名称、批注、筛选
integrations/bo_*.py         可选采集和服务接线
observer_runtime/           可选开发检查、采集、记录工具
behavior.json               完整关系模型，与执行声明绑定
```

完整示例的原 workflow.py 仅保留兼容导入；业务代码直接引用独立模块。项目执行器可以依赖 transitions 等执行库，公共查询和校验代码仅依赖标准库。不能把完整执行器说成无第三方依赖。

新项目先用下文 `bo_upgrade.py apply` 安装公共核心和图组件，再增加 `workflow.py`、`query.py` 及项目约束。不要在 `__init__.py` 另写同名 BOStateGraph 或另定导出格式。跨实例共享机器等扩展放在独立项目校验器，实际快照、诊断与公共实例协议保持一致；不为套用单次运行资源池而伪造资源归属。

`BOStateGraph` 不调用业务 guards 或 effects。`bo_structure/bo_definition` 返回声明；`bo_candidates` 核对已提供的判断证据，不能授权执行。`bo_instances` 使用绑定的权威快照提供者；页面、查询、导出都读取同一套实际配置，没有第二个可写状态缓存。自定义项目也可用 `bo_observe` 接收带构建/完整修订号的真实快照；二者互斥。

`bo_observe` 保留实际错误状态并标记 mismatch，不能用声明修正事实。旧数据缺少完整修订号时标记 partial；活动修订号不能冒充整实例修订。类型、层级和实际声明共用 bo_contracts；层级支持 transitions 风格父子状态和并行区域，历史状态及未知分隔符明确拒绝，不声称完整 SCXML 解释器。状态资源约束由 execution_contract 检查。

## 项目接入

加载前调用 `validate_runtime_definition`，提供实际 loaded_engine、loaded_version 和 guard_names；模型绑定用 `bo_require_definition`，差异抛出 ValueError。`bo_check_definition` 只是诊断接口。支持平面迁移、子状态优先、通配顺序、复合初始状态和独立并行区域。历史状态、跨并行区域迁移、状态/迁移回调及未知引擎需要专门适配，当前加载时拒绝。普通 Python 使用 python.explicit；adapter-selected 仅用于显式选择执行方式的小示例，不代表任意引擎已验证。

提供者在图锁外取得一致快照，再派生实例与导出；不得在图锁内调用业务回调。必须实际测试并发查询、记录、导出和业务推进。

sync.json 的 stategraph.module 指向 `bo_stategraph/__init__.py`，同时配置开发/执行方式、决定来源和静态及运行必需探针。用户明确改为跟随时填写 decision_source: user，并记录原意。执行方式变化不得删除观测契约。

源范围在 source_scope 指定，默认扫描项目 Python 文件；排除项必须注明原因。`bo_sync scan/watch` 发出内部更新任务，AI 消费任务后继续 inspect/verify/accept/check。watch 不自带编辑器大模型唤醒能力；项目 AI 指令和验证入口必须接好。

## 查询和导出

完整示例提供 GET /api/stategraph 和 /api/stategraph/export。model 包含全部已建模关系，instances 与 runtime.machine 来自同次快照；runtime 只包括实际接入并保留的证据。没有运行时不能虚构初始实例。

收尾观测命令返回公共 `bo_export` 产生的 stategraph_export，与当前 model/build 一致。检查器验证协议与同源实例，再按 [映射清单](mapping-contract.md) 核对每个场景的实际字段与交付投影；保留原 mapping_checks。仅给合法空导出不能通过。有 runtime_frames 的完整视图必须带出运行帧及事件，导入核对身份和修订。

```text
python bo_stategraph/__init__.py export --model behavior.json --build-id unbound --out stategraph.json
python bo_stategraph/__init__.py check stategraph.json
```

离线结构导出标记 not_observed/not_checked。也可 export --view view.json 保存完整 /api/view 响应；摘要检查完整性，不是数字签名。

个人配置由 GET/POST /api/preferences 保存，修订号检查防止多窗口/进程覆盖，原子写入防止半份文件。首次可迁移当前项目的浏览器缓存。共享或业务核心包排除个人文件。稳定 ID 延续布局；明确改名可在 presentation.node_aliases 提供一对一迁移，冲突时保留原资料，不能猜测合并。

缓存按数量和时间保留，JSONL 按大小轮转；不删除业务存储和用户保存的记录。主动记录直接订阅采集事件，避免 UI 缓存过期导致区间遗漏；达到记录上限会停止并说明缺口。运行增量接口、性能基线另列 TODO。

## 升级与迁移

先保留 change_sync begin 基线，将原执行器及恢复/调度机制完整迁入 workflow.py，再改所有实际调用方。旧 workflow 和 runtime 导入路径只作兼容委托；不能保留两份实现。项目第一次迁移的本地文件由 baseline 散列识别；之后由 runtime-version.json 记录版本和文件散列。

```text
python SKILL/scripts/bo_upgrade.py plan --root PROJECT --runtime observer_runtime --viewer static/graph --baseline .stategraph/CHANGE/baseline.json
python SKILL/scripts/bo_upgrade.py apply --root PROJECT --runtime observer_runtime --viewer static/graph --baseline .stategraph/CHANGE/baseline.json
```

SKILL、PROJECT、CHANGE 换成真实路径；从项目副本运行时另传 `--source` 指向安装 Skill 的 scripts。工具不覆盖自行修改过的公共文件，先合并后再升级；复制失败回滚并保留备份。项目 workflow/query 和 config/views 不在复制清单。旧协议不同会拒绝自动复制，需要明确迁移模型。升级后重新生成、核对旧新行为、verify → accept → check，不能只复制后宣称迁移完成。仓库维护用 tools/sync_runtime.py 同步受控副本，tools/check_package.py 检查它们一致。

共享图通过节点 `basis_fields` 声明判断依赖的修订字段，通过 `semantic_roles` 声明权限等语义标签；不按函数名称猜测。`presentation.context_fields` 指定页内参数说明，`presentation.recording` 白名单决定记录字段。等待和中断实例保留全部已知事实，旧构建或未确定的工作线程状态标为 partial。

examples/python-modes 演示相同结构下两种执行方式；两个完整示例验证真实存储、资源调度、权限、记录和导出。通过这些检查仅证明已声明范围，不能推断任意动态调用都完整。
