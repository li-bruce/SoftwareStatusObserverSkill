# 安装与使用

[English](usage.en.md) · [返回首页](../README.md)

## 在自己的项目中使用

按首页安装完整的 `business-observer` 目录，不要只复制 `SKILL.md`。安装后在项目的新对话中使用 `$business-observer`，并描述要实现或修改的功能。

例如：

```text
使用 $business-observer 为文件导出功能加入审批。
导出前需要权限检查和内容检查；请先按我的描述建图并确认理解一致，
再开发程序，并让我能从运行图看到判断条件、关键参数和对应函数。
```

Skill 先把你已描述的行为、对象和条件整理成图，用必要的澄清或反例核对理解，不主动深挖业务、补完流程或推荐规则。已有答案直接引用，具体歧义保持未决；用户或其他 Skill 提供后续补充时，再更新同一张图和对应检查。

明确后，按项目原有方式继续开发。AI 自行维护模型、状态机、源码映射、探针和检查材料；你不需要填写内部记录或手动同步。每轮结束打开更新图，查看变化、展开内部关系、检索关键参数和函数，再提出下一步修改。

## 看懂运行图

可采用任何方案设计、规定的开发流程或编码 Skill。business-observer 作为必需支线贯穿整个过程：开始实现前保存独立预期和关键参数要求；编码中绑定真实函数并接入探针；每个功能完成时执行检查。其他编码 Skill 可以负责实现，但需要遵守同一模型、参数和验证约定。

AI 会接入白盒检查，核对核心函数、参数类型、真实输入与结果及运行版本。中间记录保存在项目内，需要排查接入问题时可以查看[全过程开发说明](../skills/business-observer/references/continuous-development.md)。

对话中可让 AI：“从完整图提取我正在修改的部分，保留范围外的条件和源码关联，先展示给我确认。”工具输出 JSON 与 Markdown；显示在对话中的静态图不等于可交互页面。共享或换环境使用[局部图与导出命令](../skills/business-observer/references/focus-and-sharing.md)。

| 层次 | 要回答的问题 |
|---|---|
| 业务链路 | 这次操作经过哪些步骤，为什么停在这里？ |
| 内部状态与关键代码 | 哪项活动在执行，输入是什么，哪个条件还没满足？ |
| 局部程序结构与源码 | 哪个函数负责这一步，调用和实现在哪里？ |

主流程的“正在检查”是汇总。内部活动的等待、执行、完成等状态仍保存在每次运行中，可以展开和查询；折叠图不会删除状态。记录按运行身份、参数版本和构建版本对应，缺失数据不推测为成功。

业务、函数、状态、参数和资源都在同一张图中，以形状和颜色区分。双击节点或选中后点“展开”查看内部关系；选中后点“源码”，实现在节点旁打开。

拖动节点调整位置，圈内空白拖动整组，画布空白拖动视野。布局、展开和视野保存在项目内，刷新后恢复；切换运行只更新值。选中节点后点“固定节点”（快捷键 P），自动布局会保留该位置。可选圆形分组、层次或关系布局，点“自动布局”执行，也可撤销。布局数据不改变程序状态或业务授权。

选中节点，点“名称与备注”即可编辑名称、批注和核心标记，再提交保存。业务、函数、参数和状态节点都支持。“恢复原名”保留备注。原始名称和源码关联不会改变，AI 重新生成图也不会覆盖稳定 ID 下的标注。刷新会恢复关注节点和展开层次，折叠父节点再展开会恢复内部层次。

个人配置位于 `bo_stategraph/config/views/local.json`，换端口或重启服务后仍可恢复，清除浏览器缓存不会删除它。文件默认不提交 Git。保存冲突或写入失败会提示“未保存”；生成图和升级公共模块不会覆盖个人配置。多人实时协同不在当前范围。

首次只显示高层节点，展开后查看关键状态、函数和值。“分析细节”显示辅助代码、资源和汇合；隐藏只是减少显示内容。记录前选择全部核心事件或当前区域，点击“开始记录”，在程序中操作，再“结束记录”。回放按当前视图组织步骤，节点和底部显示值的前后变化；局部采集之外的行为不补造。

搜索名称、函数、参数或备注，可找到收起层级中的节点。结果会注明所属节点、输入／输出和类型；选中后展开相关层级并定位，其他展开区域和位置保留。参数节点的“源码”会打开采集该参数的函数。

布局与样式依赖均开源：PixiJS 为 MIT、ELK.js 为 EPL-2.0，自写 JS/CSS 为 MIT；没有引入 yFiles 代码，见 [第三方声明](../THIRD_PARTY_NOTICES.md)。规则权限的表达方案见 [ReBAC 图设计](../skills/business-observer/references/rebac-graph.md)，当前示例已有真实子条件采集；通用 ReBAC 引擎适配仍待接入。

## 接入维护者：内部同步命令

以下是 AI 自动执行或维护者排障时使用的步骤，不是日常用户的操作要求。新项目由 AI 在 `sync.json` 配置 `"whitebox": "whitebox.json"`，并将检查接入项目现有入口。安装 Skill 不会自动监听所有外部编辑；未经过检查的改动不能显示为已同步。

在示例目录 `examples/delivery` 中执行：

```bash
python observer_generated/runtime/change_sync.py begin --root . --change .stategraph/my-change --request "本轮改动"
# 修改业务代码、必要的探针、tooling/build_graph.py 和测试。
python tooling/dev.py graph --reason "说明图或状态定义为何更新"
python observer_generated/runtime/bo_sync.py scan --root .
python tooling/dev.py inspect
```

审阅 `.stategraph/my-change/impact.json`，填写同目录的 `review.json`：记录当前 `candidate_id`，说明业务、状态机、抽象和探针各自更新了什么，或为何无需改变。具体格式见 [伴随修改检查](../skills/business-observer/references/cochange.md)。需要改变已有业务规则时，`begin` 的 `--requirements` 应明确列出相应需求 ID。

```bash
python tooling/dev.py verify
python tooling/dev.py accept
python tooling/dev.py check
python tooling/dev.py archive --label my-change
```

`verify` 运行真实程序和反例；`accept` 只接受同一个已验证版本；`check` 在交付前核对当前内容。之后修改源码、图、规则、工具或测试，会让旧验收失效。不要通过改写预期结果来掩盖 bug。

从项目根目录独立盘点源码，用模型中的 `implementation` 对应功能、辅助实现、参数和实际场景。不能用一段排除理由代替功能映射；缺参数或事件会失败。旧项目更新 Skill 后需按[实现覆盖说明](../skills/business-observer/references/implementation-coverage.md)补齐清单，继续原有变更并验收。验证分别报告实现映射、状态约束、业务规则和项目检查，程序有 bug 而图如实显示时两者分别报告。

`sync.json` 中的命令使用参数数组，不执行 shell。`{python}` 表示运行检查脚本的当前 Python，避免写入机器专属路径。首次启动只恢复随版本发布的已审阅基线；修改后的内容不会自动获得通过。

## 隔离与运行模式

业务层通过自己定义的中立接口 `app/ports.py` 接入观测。完整状态执行、资源约束、统一查询位于独立的 `bo_stategraph/`，关闭观测时仍保留。`integrations/bo_*.py` 和运行工具负责可选采集与页面，不把第二套模拟状态插进业务函数。升级已有项目见[模块迁移步骤](../skills/business-observer/references/independent-python.md)。

```bash
python tooling/dev.py ownership
python tooling/dev.py core --out dist/delivery-core.zip
```

核心包包含业务源码、依赖清单和许可证，剔除观测实现与页面；安装依赖后用 `python main.py` 运行。中立接口仍保留空调用。普通运行、关闭观测和注入观测故障的结果由测试对照。

探针增加字段构造、队列和存储开销；状态记录与图刷新也有成本。`bo_stategraph/config/retention.json` 限制观测缓存和轮换日志；用户保存的记录与业务数据库不随缓存清理删除。运行增量接口和性能基线留待后续，400 ms 页面刷新和刻意延时不能用于推断正式系统性能。
