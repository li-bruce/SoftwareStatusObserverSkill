# 源码导览

[English](source-guide.en.md) · [使用说明](usage.zh-CN.md) · [架构说明](refactor-multilanguage.md)

这份导览按实际执行路径介绍源码。维护中的实现位于 [skills/business-observer](../skills/business-observer/)，示例项目中的同名模块是安装副本，用于验证接入真实项目后的行为。

## 先找到对应目录

| 位置 | 负责什么 |
|---|---|
| [SKILL.md](../skills/business-observer/SKILL.md) | 开发对话、业务图确认、迭代检查的操作流程。 |
| [scripts/bo.py](../skills/business-observer/scripts/bo.py) | 原生项目的启动、校验、源码检索与导出入口。 |
| [scripts/bo_stategraph.py](../skills/business-observer/scripts/bo_stategraph.py) | 独立状态声明、观测到的实例与完整关系结构导出。 |
| [scripts/bo_contracts.py](../skills/business-observer/scripts/bo_contracts.py) | 参数类型、状态层次、活动状态计算和声明的严格校验。 |
| [scripts/execution_contract.py](../skills/business-observer/scripts/execution_contract.py) | 并发活动、汇合、资源与运行配置的约束。 |
| [scripts/bo_observer](../skills/business-observer/scripts/bo_observer/) | 共用服务、语言适配、开发检查及 Web 支持。 |
| [assets/stategraph-viewer](../skills/business-observer/assets/stategraph-viewer/) | 项目实际使用的图页面、布局、记录和回放。 |
| [schemas](../skills/business-observer/scripts/bo_observer/schemas/) | 各语言与服务之间使用的 JSON 协议。 |
| [examples](../examples/) | 可运行项目、业务逻辑和验收场景。 |
| [tools](../tools/) 与 [tests](../tests/) | 安装、同步安装副本、仓库验收。 |
| [docs/site](site/) | 产品介绍页和独立的浏览器示例演示。 |
| [docs/review](review/) | 历次验收材料。历史记录保留原文。 |

scripts 根目录下多数小文件负责转发导入或命令调用。需要修改实现时，沿着导入进入 bo_observer。独立状态模块及两个约束文件可以脱离观测服务导入。

## 按三条路径阅读

### 一次代码修改怎样更新到图中

1. [workflow/bo_sync.py](../skills/business-observer/scripts/bo_observer/workflow/bo_sync.py) 的 source_inventory 从项目范围枚举源码，maintenance_task 与上次验收基线比较。因此新增文件也在检查范围内。
2. [sources.py](../skills/business-observer/scripts/bo_observer/sources.py) 的 scan 分派 Python、JavaScript 等语言解析；只有文件和解析器版本都匹配时才复用缓存。无法确定的调用会保留。
3. [graph/code_structure.py](../skills/business-observer/scripts/bo_observer/graph/code_structure.py) 提取 Python 声明，并通过 enrich 把局部源码结构关联到上层节点。
4. [development.py](../skills/business-observer/scripts/bo_observer/development.py) 将业务含义问题交给用户确认，将未明确的实现关系交给编码阶段处理。
5. [workflow/change_sync.py](../skills/business-observer/scripts/bo_observer/workflow/change_sync.py) 检查当前候选、影响范围和评审记录。
6. [workflow/sync_verify.py](../skills/business-observer/scripts/bo_observer/workflow/sync_verify.py) 运行约定的观测与测试，分别报告映射、状态规则、业务断言和项目检查。

扫描与检查只更新诊断信息。只有当前候选通过完整验证后，accept 才推进验收基线。

### 一次业务操作怎样进入运行图

1. 应用完成业务判断，通过 [Python BOProbe](../skills/business-observer/scripts/bo_observer/adapters/python/bo_probe.py) 或 [JavaScript BOProbe](../skills/business-observer/scripts/bo_observer/adapters/javascript/bo_runtime.mjs) 提交指定参数。
2. 适配器筛选采集字段、抑制观测自身的事件，并排队发送。传输失败单独计数。
3. [protocol.py](../skills/business-observer/scripts/bo_observer/protocol.py) 校验项目、构建版本、类型及消息大小。
4. [service.py](../skills/business-observer/scripts/bo_observer/service.py) 的 GraphSession.event 保存事件标识、来源顺序和依赖；snapshot 将真实状态关联到对应事件。
5. [bo_stategraph.py](../skills/business-observer/scripts/bo_stategraph.py) 的 bo_observe 对照声明检查实际状态及版本。实际状态与声明冲突时保留原始事实并报告差异。
6. [observation/recording_session.py](../skills/business-observer/scripts/bo_observer/observation/recording_session.py) 保存指定时间段及缺失信息。view/export 返回结构和保留的运行事实。

驱动模式还会在应用自身调用 BOExecutor.step，依据声明求取下一状态；观察模式由应用自己的逻辑决定。两种模式遵守相同的观测协议。

### 一次点击怎样改变图的显示

| 文件 | 阅读重点 |
|---|---|
| [viewer.js](../skills/business-observer/assets/stategraph-viewer/viewer.js) | 页面按钮、数据刷新和记录选择的连接入口。 |
| [graph-core.js](../skills/business-observer/assets/stategraph-viewer/graph-core.js) | 节点值、源码关联、事件筛选与图内容。 |
| [layout.js](../skills/business-observer/assets/stategraph-viewer/layout.js) | 展开收起、分组位置、筛选和批注。 |
| [renderer.js](../skills/business-observer/assets/stategraph-viewer/renderer.js) | Pixi 绘制和鼠标可命中的区域。 |
| [recording.js](../skills/business-observer/assets/stategraph-viewer/recording.js) | 回放步骤及运行证据支持的连线传递。 |
| [runtime-frames.js](../skills/business-observer/assets/stategraph-viewer/runtime-frames.js) | 查找事件对应的精确快照，比较状态和资源。 |
| [replay-steps.js](../skills/business-observer/assets/stategraph-viewer/replay-steps.js) | 按当前观察层级展示相关变化。 |
| [preferences.js](../skills/business-observer/assets/stategraph-viewer/preferences.js) | 通过项目接口保存个人显示配置。 |
| [polling.js](../skills/business-observer/assets/stategraph-viewer/polling.js) | 串行刷新及暂停、销毁控制。 |

完整模型、当前视图、运行证据各自保存。筛选视图保留完整模型，移动节点或回放记录仅改变显示。

## 修改和排版约定

主要函数用英文说明用途，在容易误读的位置解释顺序、所有权和失败处理。校验、状态修改等操作分行展开。源码可读性调整保持公开名称、协议字段、图 ID 及受保护的验收要求。

先修改主 Skill 的源码，再用 tools/sync_runtime.py 更新示例中的安装副本；项目自身的定义、数据和个人配置保留。第三方资源与历史验收材料保持原样。

[tools/formatting](../tools/formatting/) 固定开发用排版工具版本，与运行依赖分开：

    python -m pip install -r tools/formatting/requirements.txt
    npm ci --prefix tools/formatting
    python tools/format_source.py
    python tools/format_source.py --check

排版范围是维护中的 Python 模块、图页面 JavaScript、原生 JavaScript 适配器和产品页面。第三方 Pixi/ELK、示例安装副本、测试和历史材料不在排版范围。

纯可读性修改可以与指定提交比较可执行语法树：

    python tools/check_readability_equivalence.py --base <commit>
    node tools/check_js_readability_equivalence.mjs --base <commit>

JavaScript 比较使用原生适配器开发依赖中的 TypeScript。比较排除注释、文档字符串和行号，还需要运行实际行为验收：

    python tools/check_package.py
    python tools/verify.py

安装模块更新后，示例项目需要重新生成源码关联、检查候选、执行 verify，再 accept/check，并生成一份新的验收记录。
