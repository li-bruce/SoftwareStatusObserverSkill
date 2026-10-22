# 第一轮重构后的本地复评

日期：2026-10-22。对象：本地提交 `f37b5c4c0132f33e148a2878ebc8f3ce835cd3e5`。沿用上一轮的功能、架构、协议、运行事实、Skill 流程、验证和交付维度，并对照其后形成的 M01–M15 验收要求。

本次只做评估、隔离复现和报告。没有修改产品源码、原有验收基线、已安装 Skill、用户布局或原服务的业务数据，也没有提交或发布新版本。

## 1. 总体判断

**这次重构有实质进展，原先“独立模块只是附加包装”的主要结构问题已得到处理；但“阶段结束即可确认状态网如实、完整映射实现”尚未形成可靠的验收闭环。**

完整执行器已迁入项目的 `bo_stategraph/`，旧执行入口改为委托，共同声明校验、真实实例投影、源码范围扫描、内部维护任务、项目内个人配置和事件保留都有实际实现。原先多个反例已修复。不能继续把当前版本描述成原来的两套独立状态实现。

本次又确认六项问题，其中前三项直接影响核心承诺：

| 编号 | 优先级 | 已确认的问题 | 影响 |
|---|---|---|---|
| R1 | P1 | 映射对照未绑定实际交付的运行投影，也未固定必需对照项 | 导出丢掉真实实例，完整收尾检查仍可通过 |
| R2 | P1 | 迁移匹配未完整遵循已接受的状态机语义 | 错误的迁移结果可能被判为 `observed` |
| R3 | P1 | 实例查询与页面快照的锁顺序相反 | 特定并发顺序下查询、记录及需要同一锁的业务操作可能停住 |
| R4 | P2 | 文件暂时被占用时，源码监视器直接退出 | 自动维护可能中断，关闭占用者后也不恢复 |
| R5 | P2 | 全图导出遗漏新的 `runtime_frames` | 普通 Python 接入的精确历史状态证据不能随该导出完整带走 |
| R6 | P2 | 探针文档中的默认接入绕过保留策略 | 按文档接入的新项目仍可能持续追加无上限日志 |

P1 表示扩大实际接入前应优先处理；P2 表示影响持续使用、复用或交付可靠性。这里不是安全漏洞评级，也没有发现需要认定为 P0 的已复现数据破坏。

建议继续小范围本地试用，但暂时不要把 `mapping: passed` 对外解释为“交付图的核心运行内容已完整核对”。它目前证明的是已提交的对照项通过，仍可能与真正交付的投影脱节。

## 2. 范围、方法和证据

从当前 Git 提交导出隔离副本，在 Windows / Python 3.13.13 / transitions 0.9.3 下运行。源码 ZIP SHA256 为 `2dfe47509e151698c74776c13f2547aa637307d445b620152438b44e4a15030d`。本地安装的 88 个 Skill 文件与仓库规范源逐个相同。

| 本次执行 | 结果 | 能支持的结论 |
|---|---|---|
| 完整入口 `tools/verify.py`，第一次 | 失败 | 实际遇到监视器替换文件时的 Windows 占用冲突 |
| 同一源码、同一入口重跑 | 通过 | 现有回归在第二次运行通过，不能抹去第一次故障 |
| 原评估反例重新运行 | 原缺目标、缺 guard、父子循环、父级迁移、空模式和枚举混同等得到修正 | 指定旧问题已处理；新增文件须用新增的总入口评估 |
| 交付示例 | 16 个场景 × 3 模式；201 项映射对照、96 项业务断言 | 指定场景的实际存储和观测值一致 |
| 归档示例 | 40 个场景 × 3 模式；480 项映射对照、189 项业务断言 | 同上；不是所有软件的完整性证明 |
| 旧新真实执行比较 | 30 个 SQLite/工作线程场景通过 | 保留场景中的状态、活动、资源、效果及观测一致 |
| 当前公共页面实际操作 | 14 项通过 | 拖动、下钻、保存、录制、回放、视图和窄屏操作可用 |
| 重启、换端口、新浏览器 | 5 项通过 | 项目配置和保存记录恢复；12 次展开/收起后 WebGL 仍可用 |
| 新的定向反例及正反对照 | 确认 R1–R6 | 具体触发条件和边界见下一节 |

完整回归还包括独立模块、两种 Python 执行方式、28 项重构检查、录制、安装、包完整性与剔除采集后的核心包实际启动。这些与上表有重叠，不相加为独立测试总数。

本轮页面启动于隔离副本的 8839 端口，重启到 8840，使用独立合成数据库；两轮构建身份相同：`04c30b54d4840253efab715c9dcd6679f050767d30ba89b5dc0f79ef9993038e`。录制包含 85 个事件和 3 个操作，回放检查在 83 个步骤看到变化行。检查未发现页面脚本错误或崩溃；这不等于长期稳定性或大图性能结论。

上一轮的独立打印项目对话、69 次场景、2,013 个事务快照和 29 项浏览器检查作为已有材料复核，**没有把它们计为本次重新执行**。当时的需求方是模拟角色，代码、数据库和浏览器操作是真实执行；不是独立真人易用性研究。

证据：[清单与源码散列](<C:/Users/Lvi_P/Documents/Work/CF/平台软著/SoftwareStatusObserverSkill/docs/assessment/2026-10-22/inventory.json>)、[命令及结果](<C:/Users/Lvi_P/Documents/Work/CF/平台软著/SoftwareStatusObserverSkill/docs/assessment/2026-10-22/checks.json>)、[示例摘要](<C:/Users/Lvi_P/Documents/Work/CF/平台软著/SoftwareStatusObserverSkill/docs/assessment/2026-10-22/baseline-summary.json>)、[首次完整日志](<C:/Users/Lvi_P/Documents/Work/CF/平台软著/SoftwareStatusObserverSkill/docs/assessment/2026-10-22/full-check.log>)、[原样重跑日志](<C:/Users/Lvi_P/Documents/Work/CF/平台软著/SoftwareStatusObserverSkill/docs/assessment/2026-10-22/full-check-repeat.log>)、[旧反例结果](<C:/Users/Lvi_P/Documents/Work/CF/平台软著/SoftwareStatusObserverSkill/docs/assessment/2026-10-22/previous-cases.json>)、[本轮反例](<C:/Users/Lvi_P/Documents/Work/CF/平台软著/SoftwareStatusObserverSkill/docs/assessment/2026-10-22/reproductions.json>)、[浏览器结果](<C:/Users/Lvi_P/Documents/Work/CF/平台软著/SoftwareStatusObserverSkill/docs/assessment/2026-10-22/ui-result.json>)、[重启结果](<C:/Users/Lvi_P/Documents/Work/CF/平台软著/SoftwareStatusObserverSkill/docs/assessment/2026-10-22/ui-resume-result.json>)。

旧反例脚本还读取了原 8824 服务。该段输出仅保留追溯，不能证明当前源码的运行效果；本报告关于新版本页面和实例的结论使用隔离服务及上述构建身份。

## 3. 与上一轮问题及本期要求的对应

| 原问题 | 本次结论 | 依据及剩余边界 |
|---|---|---|
| F1：声明与校验分散 | 主要结构已修复 | 公共校验复用，原非法声明得到一致拒绝；更深迁移语义见 R2 |
| F2：父状态迁移误报 | 原反例已修复，语义支持仍不完整 | 父级迁移与真实引擎一致；通配优先级和复合目标初始子状态仍漏检 |
| F3：空模式使检查空转 | 原问题已修复 | 非空模式、必需命令/探针和断言保护已进入总入口；R1 是不同的验收缺口 |
| F4：新文件未进入维护 | 主要流程已接通 | 独立源码枚举、符号分类、维护任务和收尾检查有效；watch 写失败见 R4 |
| F5：事件与日志无界 | 完整示例已处理，通用入口未统一 | `EventHistory` 有数量、时间和日志轮换；默认探针文档路径见 R6 |
| F6：公共模块耦合归档领域 | 明显改善 | 采集字段由项目配置，权限视图按角色标签；跨领域材料有实际代码证据 |
| F7：双实例来源、替换不完整 | 已完成主要替换 | 同一快照派生查询和导出，旧执行入口委托；新锁顺序及导出问题见 R3/R5 |
| F8：已确认模型仍写“待确认” | 已修复所列当前残留 | 原指出的当前模型、模型源和 discovery 表述不再存在；历史原话可保留 |
| F9：新能力未纳入总回归 | 明显改善 | 双方式、独立核心、迁移、保存、录制进入入口；本次反例说明仍有盲区 |
| F10：布尔与整数枚举混同 | 原问题已修复 | `True` 不再通过整数枚举 `[1]` |

原低层 `behavior_model.check()` 仍只核对已登记内容，这是其既有职责。新文件漏登记现在由外层源码清单和阶段检查负责，不能再只调用旧函数就判断 F4 未修复。

本期验收项逐项判断如下。“有证据”只指约定范围，不代替一般化证明。

| 项目 | 判断 | 主要依据或缺口 |
|---|---|---|
| M01 完整迁移 | 有证据 | 旧新真实服务对照，执行机制进入独立目录，兼容入口委托 |
| M02 共同声明 | 基础通过，语义部分不足 | 公共规则已复用，R2 仍影响迁移结果解释 |
| M03 同一实例 | 普通路径通过，并发未闭合 | 实际页面/导出一致；R3 可造成查询停滞 |
| M04 新增实现查漏 | 约定源码范围内有证据 | 新文件、删除和符号分类进入收尾检查；不等于任意动态调用分析 |
| M05 核心值映射 | 未完整通过目标 | R1 的值对照与交付投影脱节，必需对照集合未固定 |
| M06 决策与实际路径 | 指定场景有证据 | 正反例、白盒和事件；未运行路径仍未知 |
| M07 层级及内部活动 | 部分通过 | 父级迁移、活动/资源和折叠保留；复合进入规则仍漏检 |
| M08 资源与运行身份 | 现有执行范围有证据 | 单名额等待、多名额重叠、归还、旧新尝试隔离 |
| M09 检查不能静默弱化 | 基础通过，仍有缺口 | 模式/探针/命令受保护；删除部分映射对照尚不触发覆盖退化 |
| M10 如实呈现 bug | 场景有证据，验收未完整闭合 | 分项报告方向正确；R1 仍可能让错误/遗漏投影通过 |
| M11 两种方式均维护 | 代码与已有对话有证据 | 普通 Python 跟随与状态机执行均有接入；宿主自动唤醒并非安装即具备 |
| M12 关闭观测不破坏业务 | 指定场景有证据 | 三模式及核心包实际运行；并发查询风险另见 R3 |
| M13 保留边界 | 部分通过 | 已有适配器受控，默认文档入口及完整历史导出仍有 R5/R6 |
| M14 个人配置 | 本次重点复验通过 | 文件保存、重载、重启、换端口；迁移、冲突和故障检查在总回归内 |
| M15 跨领域复用 | 有限范围有证据 | 字段/标签配置测试；打印项目为上一轮独立试用材料 |

## 4. 新确认的问题

### R1 · P1：映射对照未绑定交付投影，缺项也可能通过

`mapping_contract.assess()` 检查对照 ID 不重复、来源和投影名称非空，以及提交的 `actual` 与 `mapped` 是否相同。`projection` 是文字，不会被解析为当前导出中的某个实例、修订或字段；检查器也没有读取固定的必需对照清单。

本次分别验证了三个层次：

1. 两项对照中一项资源值错误，结果失败；只删掉错误项，仍保留一项正确对照，结果通过。必需模式、命令和探针的保护不等于必需字段覆盖保护。
2. 合法导出中的状态是 `c`，实际状态及另行提交的对照值都是 `a`；导出自洽检查和映射对照分别通过。摘要正确只能证明文件内部未变，不能证明它与另一个对照对应。
3. 在完整归档项目的隔离副本，先让观测命令导出实际有 1 个实例的 `archive_snapshot/on` 快照，正常 verify/accept/check 通过。随后仅将该公共导出改为空配置，保留所有业务场景、原预期、必需探针、480 项映射对照和 189 项业务断言，再次 verify/accept/check 仍全部通过。

这不是要求工具证明 AI 理解了所有自然语言。这里要核对的对象已经存在：实际运行、当前交付的图/实例、被要求的核心字段。当前缺少把三者逐项连接起来的机器约定。

**修复方向：** 在开始阶段建立可审查的映射检查清单，记录稳定节点 ID、源码事实位置、导出路径、场景/实例/修订/构建身份及类型。验证器从真正交付的投影取 `mapped`，不只相信适配器另交的一对数值。必需项删除、身份错绑、缺实例、少字段和旧修订都应失败或明确报告未覆盖。不同项目可有不同清单，不设全项目通用的固定断言数量。

代码：[对照器](<C:/Users/Lvi_P/Documents/Work/CF/平台软著/SoftwareStatusObserverSkill/skills/business-observer/scripts/mapping_contract.py:22>)、[导出及对照分别校验](<C:/Users/Lvi_P/Documents/Work/CF/平台软著/SoftwareStatusObserverSkill/skills/business-observer/scripts/sync_verify.py:106>)、[检查约定保护范围](<C:/Users/Lvi_P/Documents/Work/CF/平台软著/SoftwareStatusObserverSkill/skills/business-observer/scripts/sync_config.py:65>)。证据：[完整收尾检查正反对照](<C:/Users/Lvi_P/Documents/Work/CF/平台软著/SoftwareStatusObserverSkill/docs/assessment/2026-10-22/export-binding-result.json>)、[完整命令](<C:/Users/Lvi_P/Documents/Work/CF/平台软著/SoftwareStatusObserverSkill/docs/assessment/2026-10-22/export-binding-commands.json>)、[复现脚本](<C:/Users/Lvi_P/Documents/Work/CF/平台软著/SoftwareStatusObserverSkill/docs/assessment/2026-10-22/export_binding_gate.py>)、[组件级对照](<C:/Users/Lvi_P/Documents/Work/CF/平台软著/SoftwareStatusObserverSkill/docs/assessment/2026-10-22/reproductions.json>)。

最早的 `empty-export-*` 探索碰巧选择了原本没有实例的首个场景，不能作为数据丢失证据；已明确标记其局限，结论采用后续有 1 个实例的正反对照。

### R2 · P1：状态迁移判断仍有假通过

原来的父状态迁移误报已经修复。本次使用实际安装的 transitions 0.9.3 作为独立对照，又发现两种被公共声明接受的情况：

| 声明 | 真实引擎结果 | 错误观测值 | 当前观察器 |
|---|---|---|---|
| 先声明 `a --go--> b`，后声明 `* --go--> c` | `b` | `c` | `observed`，没有错误 |
| `idle --go--> active`，其中 active 初始子状态为 a，另有 b | `active_a` | `active_b` | `observed`，没有错误 |

第一种情况中，`source_nodes()` 用活动状态与 source 求交，`*` 没有转换为实际源状态，优先级遮蔽未生效。第二种只要求目标父状态在结果的祖先集合中，没有核对进入父状态时应递归进入的初始子状态。

这里是**核对结果错误**，并非已经发现业务引擎执行错误。开发者可能看到“符合声明”的假象。

**修复方向：** 为支持的引擎定义明确的语义范围，用真实引擎的动作序列对照候选和最终活动状态集合。补通配顺序、复合进入、内部迁移与并行区域的组合检查；尚未实现的语义应拒绝接入或显示不支持，不能归入 `observed`。不必为此改用 XML。

代码：[优先级处理](<C:/Users/Lvi_P/Documents/Work/CF/平台软著/SoftwareStatusObserverSkill/skills/business-observer/scripts/bo_stategraph.py:108>)、[目标结果匹配](<C:/Users/Lvi_P/Documents/Work/CF/平台软著/SoftwareStatusObserverSkill/skills/business-observer/scripts/bo_stategraph.py:178>)。证据：[wildcard_priority 与 compound_initial](<C:/Users/Lvi_P/Documents/Work/CF/平台软著/SoftwareStatusObserverSkill/docs/assessment/2026-10-22/reproductions.json>)。语义对照：[transitions 官方文档](https://github.com/pytransitions/transitions#hierarchical-state-machine-hsm)、[SCXML 合法状态配置](https://www.w3.org/TR/scxml/#LegalStateConfigurations)。

### R3 · P1：实例查询与页面快照形成相反锁顺序

归档示例给公共实例查询绑定了 `recording_view()["machine"]`。于是存在两个正常调用方向：

```text
Python 查询 bo_instances()
  持有 graph._lock → 调用快照提供者 → 等待 service.lock

记录/导出 recording_view()
  持有 service.lock → graph_view() → 等待 graph._lock
```

本次调用真实 `LocalApplication`、SQLite 与 `BOStateGraph`，只用同步屏障控制线程在合法位置切换，不替换产品方法。两个线程均停在等待，对应锁均已由另一线程取得，没有异常退出。临时进程退出后释放全部测试资源。

这不是普通 UI 操作必然崩溃的证据；触发条件是公共 Python 查询与另一条记录/快照路径并发。但它正处于用户要求公开的查询接口上，并可能持有业务服务锁，影响后续需要该锁的操作。

**修复方向：** 不在图内部锁中调用外部提供者。先取得不可变、带身份和修订的快照，再在需要时短时锁住内部状态；记录、查询和导出遵循同一锁顺序。增加双向并发回归，验证查询完成及业务线程继续推进，不只是单线程值相等。

代码：[持锁调用提供者](<C:/Users/Lvi_P/Documents/Work/CF/平台软著/SoftwareStatusObserverSkill/skills/business-observer/scripts/bo_stategraph.py:201>)、[绑定路径](<C:/Users/Lvi_P/Documents/Work/CF/平台软著/SoftwareStatusObserverSkill/examples/team-archive/integrations/bo_server.py:50>)、[服务锁](<C:/Users/Lvi_P/Documents/Work/CF/平台软著/SoftwareStatusObserverSkill/examples/team-archive/integrations/bo_server.py:65>)、[嵌套实例查询](<C:/Users/Lvi_P/Documents/Work/CF/平台软著/SoftwareStatusObserverSkill/examples/team-archive/integrations/bo_server.py:133>)。证据：[线程复现](<C:/Users/Lvi_P/Documents/Work/CF/平台软著/SoftwareStatusObserverSkill/docs/assessment/2026-10-22/query-lock-order.log>)、[复现代码](<C:/Users/Lvi_P/Documents/Work/CF/平台软著/SoftwareStatusObserverSkill/docs/assessment/2026-10-22/reproduce.py>)。

### R4 · P2：watch 发布维护任务失败后不恢复

`bo_sync.py` 会捕获读取配置和源码时的暂时错误，但创建临时文件、写入和替换 `maintenance.json` 不在恢复分支内。

第一次完整回归实际触发 `PermissionError [WinError 5]`，监视进程退出，等待新任务的测试失败。随后原样重跑通过。独立复现用普通 Windows 文件句柄暂时打开维护文件且不共享删除权限，再修改源码；watch 退出码为 1，关闭句柄后也不会恢复。没有伪造文件系统异常。

**修复方向：** 写入采用独立临时文件，对暂时共享冲突有限重试，保留可见的失败状态并继续监视；只有发布成功才推进已发布标识。收尾扫描可继续作为兜底，但不能把它等同于监视器仍在运行。

代码：[输出写入](<C:/Users/Lvi_P/Documents/Work/CF/平台软著/SoftwareStatusObserverSkill/skills/business-observer/scripts/bo_sync.py:94>)。证据：[首次完整检查](<C:/Users/Lvi_P/Documents/Work/CF/平台软著/SoftwareStatusObserverSkill/docs/assessment/2026-10-22/full-check.log>)、[确定性冲突复现](<C:/Users/Lvi_P/Documents/Work/CF/平台软著/SoftwareStatusObserverSkill/docs/assessment/2026-10-22/watch-write-conflict.log>)。

### R5 · P2：全图导出遗漏精确运行帧

新接入的普通 Python 程序可以通过 `runtime_frames` 提交与事件精确绑定的事务投影；回放器据此显示过去的实际状态。但 `bo_export_view()` 仍只复制 manifest、authority、machine、events、health 和 historical，遗漏该字段。

本次先用实际录制器接收 1 个运行帧，确认无身份或内容缺口；同一视图经全图导出后不再有运行帧，公共导出校验仍通过。当前状态和原事件仍在；独立录制下载也有自己的保存路径。问题限于“从完整视图导出整个关系及运行证据”这条通路，不是所有录制都丢失。

**修复方向：** 为已声明的运行证据定义统一导出白名单及版本，将运行帧身份、事件关联和缺失范围纳入导出/导入往返验证。继续只导出已选择的字段，不扩大为抓取原始对象或数据库。

代码：[导出字段清单](<C:/Users/Lvi_P/Documents/Work/CF/平台软著/SoftwareStatusObserverSkill/skills/business-observer/scripts/bo_stategraph.py:277>)。证据：[录制器正向校验与导出对照](<C:/Users/Lvi_P/Documents/Work/CF/平台软著/SoftwareStatusObserverSkill/docs/assessment/2026-10-22/frame-export-result.json>)、[export_drops_runtime_frames](<C:/Users/Lvi_P/Documents/Work/CF/平台软著/SoftwareStatusObserverSkill/docs/assessment/2026-10-22/reproductions.json>)。

### R6 · P2：文档默认探针路径未使用保留策略

完整示例已正确用 `EventHistory` 包装探针输出；然而 `references/semantic-pins.md` 仍指导直接构造 `Pins(..., path=...)`。该默认 sink 只用追加模式写文件，不读取项目的 retention 配置。

在同一临时项目设置 1,024 字节日志上限并写入 25 个事件：文档默认路径得到单个 9,597 字节文件；接入 `EventHistory` 后，当前文件 384 字节、存在 1 个备份，内存只保留配置的 2 个事件，23 个淘汰有记录。

这是公开接入路径与功能承诺不一致；并不推翻两个完整示例中的轮换实现。

**修复方向：** 提供统一的项目探针工厂或明确要求使用有界 sink，更新 Skill 与示例片段；如果保留低层无限追加接口，应明确其职责并禁止把它当作已启用项目保留策略的默认接入。增加“直接按文档复制”的最小接入回归。

代码：[默认写入](<C:/Users/Lvi_P/Documents/Work/CF/平台软著/SoftwareStatusObserverSkill/skills/business-observer/scripts/semantic_probe.py:64>)、[公开指导](<C:/Users/Lvi_P/Documents/Work/CF/平台软著/SoftwareStatusObserverSkill/skills/business-observer/references/semantic-pins.md:3>)、[完整示例的正确接入](<C:/Users/Lvi_P/Documents/Work/CF/平台软著/SoftwareStatusObserverSkill/examples/team-archive/integrations/bo_observer.py:18>)。证据：[保留对照](<C:/Users/Lvi_P/Documents/Work/CF/平台软著/SoftwareStatusObserverSkill/docs/assessment/2026-10-22/retention-entry-result.json>)、[脚本](<C:/Users/Lvi_P/Documents/Work/CF/平台软著/SoftwareStatusObserverSkill/docs/assessment/2026-10-22/retention_entry.py>)。

## 5. 架构、协议、旧代码与维护成本

### 已经合理的部分

| 部分 | 当前职责 | 判断 |
|---|---|---|
| 项目 `bo_stategraph/` | 执行声明、推进规则、活动资源、查询和配置 | 已成为独立模块，保留项目领域差异是合理的 |
| `bo_contracts` / `execution_contract` | 图、类型、层级以及活动配置约束 | 公共含义集中，减少入口不一致 |
| 业务存储、领域函数和中立端口 | 真正业务数据、效果和外部依赖 | 没有为了观测而把这些全部搬进通用核心 |
| `sync_config` / `bo_sync` / `change_sync` / `sync_verify` | 源码范围、变化任务、阶段管理及分项验收 | 比原来集中在一个脚本更清晰 |
| `source_migration` | 显式源码移动和原身份保持 | 保留原断言及探针，优于仅重新生成后接受 |
| `preferences` / `polling` / `renderer` | 个人配置、刷新和 Pixi 对象管理 | 实际拆分，重启保存与反复操作有证据 |
| `bo_upgrade` 与包检查 | 公共文件清单、散列、冲突拒绝和回滚 | 复制式交付已有管理机制，不是任意覆盖 |

两个完整示例的旧 `workflow.py` 是委托入口；运行库中的旧公共模块入口也转到独立包，回归还检查对象身份。保留这种兼容层不等于保留第二套执行机制。用于旧版本复现的历史快照和 v1 工具应继续与当前入口隔离，也不应为了目录看起来干净而删除审查证据。

模型、事件、完整实例、活动日志、运行帧、录制和个人配置本来就是不同类型的数据，不能要求它们使用同一种 JSON。当前问题是跨协议的连接检查仍不充分：R1 是对照和公共导出之间断开，R5 是视图和导出之间断开，R3 是共享查询跨锁边界的问题。

### 仍需整理的部分

`viewer.js` 从原评估记录的 814 行减至 645 行，仍包含很多协调分支，其中 57 行超过 160 字符。当前 `change_sync.py` 为 298 行，`sync_verify.verify()` 仍集中处理多个检查阶段。行数只是定位线索，不是质量评分；真正值得拆的是独立的协议检查、外部 I/O 和状态更新。

下一步应优先建立带类型/明确字段的“阶段结果”和“运行投影检查”接口，再整理长函数。单纯把长函数搬到新文件，不会解决 R1–R5。第三方压缩后的 Pixi/ELK 文件不计作自有代码密集问题。[本次代码规模](<C:/Users/Lvi_P/Documents/Work/CF/平台软著/SoftwareStatusObserverSkill/docs/assessment/2026-10-22/code-metrics.json>)

复制公共核心、运行库和页面模板的交付方式适合自包含 Python 项目，但会产生升级成本。现有同步、散列和冲突检查值得保留；后续改动必须覆盖规范源、复制清单和实际包运行，不能只改某个例子中的副本。此次安装副本一致、总回归包检查通过，没有发现需要回退整个迁移的证据。

## 6. Skill 文本与引导流程

入口从原评估的 118 行、8,715 字符降为 60 行、3,485 字符，压缩约 60%。参考文档仍为 21 篇、约 57,292 字符，按需读取机制因此很重要；并非所有项目每轮都应加载全文。

当前五阶段组织是合理的：明确行为 → 建立模块与检查 → 编码期间维护 → 呈现图 → 分项验证。它已落实用户要求的关键区别：默认在 AI 内部依据状态网组织开发，用户拒绝后跟随其代码实现；两种方式都保留监控、映射和检查，普通用户不需要填中间文件。

本次认可以下改变：

- 提问仅针对改变权限、状态、并发、取消、恢复或效果的歧义，不把沉默视为同意。
- 不要求另一种编码 Skill 放弃自己的技术方案；状态网维护成为贯穿开发的必要支线。
- “必须维护”已有源码扫描、任务文件及阶段收尾检查，不再只有提示词义务。
- 明确 watch 是否唤醒 AI 依赖宿主接线；安装 Skill 本身不会自动控制任何编辑器。
- 实现映射、状态约束、业务规则和项目检查分别报告，方向符合用户最新目标。
- 使用公共核心和查看器，防止新项目另写同名简化类和只有截图的展示页。

仍需跟随代码修正三处：映射完整性说明应落到 R1 的可执行清单；引擎支持范围应与 R2 的真实能力一致；默认探针片段应接入 R6 的保留策略。不能只增加更多“必须”补丁。

上一轮对话试用曾出现同名简化核心和独立 SVG 页面，后续被检查否定并修正。这说明交付门禁有价值，也说明文字约束不能保证每轮 AI 都遵守。合理目标是在阶段结束发现偏离，展示未覆盖项，而不是证明 AI 从未误解需求。

这与规范驱动开发先形成约定、再实现和核对的思路相容。可以借鉴阶段产物、可执行约定和明确接收流程，但不能用“遵循流程”替代真实投影核对。[Spec Kit 官方流程](https://github.com/github/spec-kit#spec-driven-development)

## 7. 状态机、Petri、权限和类/实例的边界

### 层级：上层概述与底层实际状态同时存在

“检查中”可以作为折叠标题；真实配置仍须保存“内容检查完成、索引运行中、名额占用 1”。当前示例的独立配置和查询已保留这些内容。业务分组圈只是展示结构，不能凭圈的包含关系推断执行继承或并发。

真正的复合状态还规定如何进入内部初始状态，父状态迁移怎样应用于子状态；并行区域需要同时保存多个活动状态。因此 R2 不是增加标签就能修复，必须比较真实执行规则。[SCXML 配置规则](https://www.w3.org/TR/scxml/#LegalStateConfigurations)

### Petri 特性：什么时候能开始、为什么等待、什么时候汇合

当前执行器中，活动先取得名额，完成后归还；名额不足就等待；所有必需检查满足要求后才允许后续提交。这些已有代码、状态和日志，应继续用同一张图展示，不另建独立的 Petri 权威层。

Petri 网以条件/资源上的标记以及消耗、产生标记的动作解释这些行为。比如只有一个名额时两项检查不能同时占用；“都结束”也不等于“都成功”。这些概念可以指导资源不变量和序列测试。[Petri 网基础材料](https://www.site.uottawa.ca/~bochmann/ELG7187C/CourseNotes/BehaviorModeling/Petri-nets/index.html)

当前通用执行合约主要覆盖单次运行的固定活动、整数资源和 ALL 汇合。独立打印试用中的跨任务共享资源由其项目代码和真实运行帧映射，不能据此宣称公共库已经支持一般 Petri 网、任意重复活动、所有共享资源调度或自动死锁分析。R3 是 Python 锁顺序的工程死锁，与是否画出 Petri 图无关。

### 权限与类/实例

ReBAC 部分保留“规则定义、关系数据、一次请求的实际求值”三层是正确的。规则图可以稳定复用，请求只绑定当前主体、资源、关系版本和实际用到的证据；无需预先画出全库所有派生权限。现有情况清单已超出最初的一跳父子例子，但还没有通用 OpenFGA/SpiceDB 解释器适配，不应列为已经实现。[OpenFGA 模型与关系概念](https://openfga.dev/docs/concepts)

类、方法、对象、调用实例和业务运行实例仍是不同身份。当前 AST 与事件提供部分类/方法及调用关系，不是完整对象堆浏览器；通用接收者身份、对象生命周期和多对象错绑检查仍需专门接入。这不妨碍现有业务实例查询，但不能用 `attempt` 替代所有对象实例。

当前验证是结构检查、真实运行对照和有限场景测试的组合。最有价值的补充是动作序列、资源不变量、故意删改映射项和真正引擎对照；不需要为提升数字写重复实现的测试。Hypothesis 的状态测试可用于生成动作序列并缩小反例，是否采用取决于具体需要。[Hypothesis 状态测试](https://hypothesis.readthedocs.io/en/latest/stateful.html)

## 8. 页面、运行与共享

本次初始图只显示三个高层节点；展开、整组拖动、节点别名/批注/核心标记、源码定位和十种视图预设均可操作。布局和个人解释写入项目文件，换端口与新浏览器恢复成功。界面比早期平铺全部节点更适合从业务逐层看实现。

![本次隔离服务初始图](<C:/Users/Lvi_P/Documents/Work/CF/平台软著/SoftwareStatusObserverSkill/docs/assessment/2026-10-22/ui/01-initial.png>)

回放显示实际值的前后变化，未记录的过去值保留“未记录”，没有把最终值倒填到过去。图例常显，节点类型和连线类型可直接查看。

![重启后读取记录与变化](<C:/Users/Lvi_P/Documents/Work/CF/平台软著/SoftwareStatusObserverSkill/docs/assessment/2026-10-22/ui/07-restart-and-replay.png>)

视图压缩后细标签仍较小；预设切换“可操作”不等于每个复杂业务都易于理解。本次没有独立真人任务测量。320/390/900 像素下没有整页横向溢出，也不代表所有小屏文字密度都理想。

| 能力 | 本次判断 |
|---|---|
| 实时同步 | 真实请求、等待、恢复、内部活动和完成可见；限已接入事实 |
| 记录与回放 | 开始/结束、全部/局部采集和逐步变化通过；完整导出另有 R5 |
| 保留与保存 | 两示例缓存/日志受控，保存记录可恢复；通用默认接入另有 R6 |
| 观测隔离 | 三模式及核心包运行通过；不能据此声称零开销或任意并发都不影响业务 |
| 共享与迁移 | 清单包、散列、升级与身份迁移有实现；不是多人协同合并或自动脱敏 |
| 图操作软件 | 尚未实现，当前图编辑改变展示，不授予权限或发业务命令 |
| 大图与生产部署 | 本次未测，不给节点规模、CPU/延迟或生产可靠性承诺 |

## 9. 建议的下一步顺序

| 顺序 | 工作 | 验收条件 |
|---|---|---|
| 1 | 修正 R3 的锁边界 | 并发查询、记录、导出和业务推进均可结束；无相反锁顺序 |
| 2 | 完成 R1 的映射约定 | 缺实例、删对照项、绑错字段/修订、导出与对照脱节均被检出 |
| 3 | 补 R2 的引擎语义范围 | 两个新反例失败；支持范围与真实引擎动作序列一致，不支持的明确标记 |
| 4 | 修复 R4 的监视器恢复 | 文件短暂占用后继续发布最新任务，不能误清基线 |
| 5 | 统一 R5/R6 的证据及保留入口 | 精确帧往返不丢，按文档最小接入也有容量边界 |
| 6 | 更新 Skill 并回归 | 文本只描述已接通的接口；所有新反例进入正常检查，保留原业务断言 |

完成后重跑原有总入口，再做一次有限的跨领域编码迭代：新增函数、移动已绑定源码、故意漏掉一个参数或导出实例，确认阶段门禁能准确指出遗漏。只有修正代码且反例进入日常回归，才能把对应项从“部分”改为“通过”。

运行事件增量 API、分页/推送、刷新与哈希缓存、性能基线、大图压测、多人合并、通用权限引擎和一般 Petri 分析继续列 TODO，不用这些延期目标否定本轮已经完成的结构工作。

## 10. 复现和结论边界

本目录保存源码清单、两次总回归、原反例、新反例、完整收尾检查正反对照、保留对照及当前截图。退出码 0 可能只表示复现脚本成功运行；应读取其产品结果，不能把它当作功能通过。

隔离源码来自 `git archive f37b5c4`。先在该副本运行 `python tools/verify.py` 生成并核对示例产物，再从本仓库执行本目录的复现脚本。`reproduce.py` 使用 `.validation/assessment-20261022/source` 中已核对的模型；`export_binding_gate.py` 保留既有基线并在全新隔离项目中执行正反对照，若目录已存在会停止以避免覆盖本次证据。再次执行时应使用新的审查工作目录，不删除原证据。

浏览器脚本由上一轮脚本复制，本次仅调整输出位置和测试端口；通过 webapp-testing 的 `with_server.py` 在同一次调用中启动隔离服务并执行，结束时停止该测试服务。报告没有据旧 8824 服务推断新版本状态。

本次未做跨平台重新执行、长时间压力测试、分布式部署验证或新一轮真人使用研究。已有对话材料能证明那次模拟交互和实际实施过程，不能证明所有模型都会照做。

最终评价是：**架构方向正确，主要迁移已有运行证据；完整映射验收、迁移语义、并发查询和少数跨模块接线仍未闭合。** 下一轮应围绕这几处可复现问题修正，不需要重新发明一套图或再扩大 Skill 的口头要求。
