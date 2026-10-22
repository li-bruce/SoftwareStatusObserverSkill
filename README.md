# Software Status Observer Skill

[English](README.en.md) · [安装与使用](docs/usage.zh-CN.md) · [运行示例](examples/delivery/README.md) · [本轮重构与验收](docs/review/refactor-round1/README.md)

**在 Vibe Coding 中，帮助开发者看懂和调试 AI 生成的程序。**

`business-observer` 让 AI 在开发时同步维护业务逻辑、关键代码关系和真实状态机；程序运行后，用分层图展示核心函数、参数、判断条件和执行状态。

## 可以看到什么

- 从业务节点展开到内部活动、关键函数，再查看对应源码。
- 直接在节点和边上查看参数类型、实际值、执行结果及等待原因。
- 查看并行活动、可用名额和汇合条件，定位是哪一步阻止流程继续。
- 按运行和参数版本回看状态，区分当前事实、旧记录和缺失信息。
- 在同一张节点图中查看业务、函数和状态；拖动并固定节点，使用层次或关系布局。刷新后恢复手动布局。
- 开始/结束记录程序操作，回放核心事件并定位源码；按业务流、状态机、函数、资源等预设或自定义组合筛选。圈内空白可拖动整组，共享节点通过引用入口显示。见[操作与验证材料](docs/review/recorded-views/README.md)。
- 可记录全部核心事件或仅选中区域；回放按当前层级组织步骤，显示状态与数值的前后变化。支持节点批注与核心标记。见[本次操作说明与验证](docs/review/focused-replay/README.md)和[类型、规则、采集设计](skills/business-observer/references/types-rules-capture.md)。
- 修改节点的显示名称和备注，保留源码身份；刷新、折叠再展开后恢复个人标注与观察层次。
- 搜索函数、参数、名称或备注，直接定位到收起层级中的节点。

AI 默认在内部依据状态网引导开发，用户可以采用任何框架和编码流程。用户明确要求不用这种开发方法时，AI 跟随其实现适配状态网。两种方式都必须维护底层监控、随源码更新的图、参数映射和验证，用户不需要操作中间构建步骤。

Python 的状态网保存在独立模块中。业务既可使用状态机引擎，也可使用自己的函数逻辑；模型、监控和导出不会因此消失。见[两种实现的可运行示例](examples/python-modes/README.md)与[模块契约](skills/business-observer/references/independent-python.md)。完整示例通过 `/api/stategraph/export` 下载全部已建模节点、关系、状态声明和保留的运行证据，页面筛选不影响导出。

Skill 根据用户当前描述建图，通过必要的澄清或反例确认图是否符合原意；不主动深入推演、补完业务流程或推荐规则。用户或其他 Skill 补充规则后，再更新同一张图和对应检查。修改代码时，检查图、状态机、探针和测试是否同步。上层结构来自需求理解，局部程序关系来自 Python AST，运行状态来自实际执行。

## 安装 Skill

在支持 `$skill-installer` 的 Codex 对话中输入：

```text
使用 $skill-installer，从以下地址安装 business-observer：
https://github.com/li-bruce/SoftwareStatusObserverSkill/tree/main/skills/business-observer
```

`main` 提供最新提交；历史标签保留对应版本。已安装旧版时，请先保留自己的修改，再更新完整 Skill 目录。

也可以克隆仓库后安装到指定项目：

```bash
git clone https://github.com/li-bruce/SoftwareStatusObserverSkill.git
cd SoftwareStatusObserverSkill
python tools/install_skill.py --project /path/to/your-project
```

安装脚本将完整 Skill 复制到目标项目的 `.agents/skills/business-observer`，遇到已有目录会停止。打开该项目的新对话后使用：

```text
使用 $business-observer 开发这个功能：……
先用图帮我理清业务和状态；开发方案按本项目的要求执行。
开发中自行维护图和检查，完成后让我查看变化和运行结果。
```

日常只需描述需求、回答关键业务问题和查看图。AI 负责中间的源码映射、探针、同步与验证；无需逐步操作内部文件或命令。安装 Skill 本身不会在后台监听所有编辑器，AI 会在接入项目时配置相应检查入口。

## 运行示例

需要 Python 3.11–3.13、Node.js 20+ 和支持 WebGL 的现代浏览器。Node.js 仅用于图测试。

```bash
python -m venv .venv
```

激活虚拟环境：Windows PowerShell 使用 `.venv\Scripts\Activate.ps1`；macOS/Linux 使用 `source .venv/bin/activate`。

```bash
python -m pip install -r examples/delivery/requirements.txt
python tools/demo.py
```

打开 [运行图](http://127.0.0.1:8797/) 和 [操作页](http://127.0.0.1:8797/control)。批准当前版本，点击“检查并提交”，在图中展开“检查内容”。将并发名额改为 1，可看到一项执行、另一项等待。两项检查通过后，程序重新检查授权和版本，再保存交付物。

示例使用合成文本和本地 SQLite。图约每 400 ms 更新；检查刻意放慢以方便观察。完整操作见[示例说明](examples/delivery/README.md)。

另一个[资料归档示例](examples/team-archive/README.md)是在新会话中从需求开始开发的，保留了提问、实现、发现问题、修复和增加大小上限的全过程：

```bash
python tools/archive_demo.py --port 8824
```

打开[操作台](http://127.0.0.1:8824/)与[开发者图](http://127.0.0.1:8824/graph)。审查材料包含首版与修改后的图、真实参数、截图和复现命令；其中需求方由 AI 模拟，明确区别于真人使用测试。

## 项目内容

2026-10-22 更新明确了“确认用户意图”的引导范围，保留消除歧义所需的追问和反例。新增[项目流转系统独立试用记录](docs/review/intent-confirmation-20261022/README.md)，包含实际模拟对话、跨类型派生迭代、失败与修复、截图及可运行源码包。

v0.5.0 完成独立状态网替换、共同校验和统一实例，新增源码范围扫描与收尾映射检查、项目内个人配置、事件保留和版本化升级。映射正确与业务正确分别报告。代码变化及试用证据见[本轮审查材料](docs/review/refactor-round1/README.md)。

v0.4.0 增加贯穿开发过程的白盒约定、实际参数与判断检查、带边界的局部图提取，以及显式文件清单导出。设计依据见[路线与关系设计](docs/design/roadmap.zh-CN.md)，可运行命令见[全过程开发](skills/business-observer/references/continuous-development.md)和[局部图与共享](skills/business-observer/references/focus-and-sharing.md)。

| 目录 | 内容 |
|---|---|
| `skills/business-observer/` | Skill 提示、检查脚本、探针和图模板 |
| `examples/delivery/app/` | 领域函数、业务存储和事务 |
| `examples/*/bo_stategraph/` | 完整状态执行、活动/资源机制、共同协议和统一查询；个人配置在 config/views |
| `examples/delivery/integrations/` | 可选观测接入和页面源文件 |
| `examples/delivery/observer_generated/` | 生成的图、页面和运行库副本 |
| `examples/team-archive/` | 独立会话开发的资料归档程序及两轮验证记录 |
| `tests/`、`tools/` | 安装、发布检查和回归测试 |

## 验证与边界

当前版本包含受保护的[映射清单](skills/business-observer/references/mapping-contract.md)：从实际存储取值，逐项核对每个约定场景的实例和公共导出，删除场景或必需字段会使验收失败。既有项目接入本版时需要补齐 `sync.json` 的 `mapping_contract` 和对应观察输出，不能用重新建立基线跳过检查。非法状态定义、未支持的引擎语义和错误 guard 接线在加载前报错；实际运行违规保留原值并报告约束失败。

```bash
python tools/verify.py
```

检查包括需求澄清、权限和版本反例、并发与资源等待、旧新运行隔离、图回看、观测开启/关闭/故障时的结果一致性，以及剔除观测层后的核心包运行。修改记录与验收流程见[使用说明](docs/usage.zh-CN.md)。

当前提供 Python 参考实现，Skill 和示例界面以中文为主。其他语言需要对应的静态分析和运行适配。图覆盖明确选取的业务路径与内部活动；不会采集全部函数局部变量。检查通过不等于证明整个软件或权限系统正确。

当前图支持查看和下钻；执行仍通过示例操作页。图上修改节点并控制程序尚未实现。示例用于本地开发，不提供生产部署、用户认证或崩溃后工作线程恢复。

## 许可证

[MIT](LICENSE)。依赖与来源见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

对话初期可直接打开内置设计图，用户仍在 Codex 中确认和修改；图沿用到运行调试。支持隐藏入口、关闭 Web 和导出无页面核心包，节点按类型填充并突出核心标记。参见[对话与 Web 图](skills/business-observer/references/conversation-web.md)。
