# 安装与使用

[English](usage.en.md) · [返回首页](../README.md)

## 在自己的项目中使用

按首页安装完整的 `business-observer` 目录，不要只复制 `SKILL.md`。安装后在项目的新对话中使用 `$business-observer`，并描述要实现或修改的功能。

例如：

```text
使用 $business-observer 为文件导出功能加入审批。
导出前需要权限检查和内容检查；请先确认并发、失败和重试的规则，
再开发程序，并让我能从运行图看到判断条件、关键参数和对应函数。
```

Skill 应先整理谁触发什么操作、涉及哪些对象、成功或等待的条件，再询问会改变执行结果的缺失规则。已经回答的内容直接引用；尚未回答的问题保留为未决，不把 AI 的建议当成用户决定。完整记录见 [discovery.example.json](../skills/business-observer/assets/discovery.example.json)。`<skill>` 表示安装后的 `business-observer` 目录：

```text
python <skill>/scripts/requirements_dialogue.py check --file discovery.json
```

将示例复制为 `discovery.json` 时，D1 故意保留为未决问题；此时检查返回非零属于预期，需要取得回答并更新记录。

涉及权限、提交、等待或恢复的关键问题未解决时，已接入的变更检查会拒绝验收。独立脚本只能校验记录和关联，问题是否完整、回答是否理解正确仍需审阅。

## 看懂运行图

| 层次 | 要回答的问题 |
|---|---|
| 业务链路 | 这次操作经过哪些步骤，为什么停在这里？ |
| 内部状态与关键代码 | 哪项活动在执行，输入是什么，哪个条件还没满足？ |
| 局部程序结构与源码 | 哪个函数负责这一步，调用和实现在哪里？ |

主流程的“正在检查”是汇总。内部活动的等待、执行、完成等状态仍保存在每次运行中，可以展开和查询；折叠图不会删除状态。记录按运行身份、参数版本和构建版本对应，缺失数据不推测为成功。

业务、函数、状态、参数和资源都在同一张图中，以形状和颜色区分。双击节点或选中后点“展开”查看内部关系；选中后点“源码”，实现在节点旁打开。

拖动节点调整位置，拖动空白平移。布局、展开状态和视野保存在当前浏览器，刷新后恢复；切换运行只更新值。选中节点后点“固定节点”（快捷键 P），自动布局会保留该位置。可选“层次布局”或“关系布局”，点“自动布局”执行，也可撤销。展开后按需点“显示完整图”并放大。布局数据不改变程序状态或业务授权。

选中节点，点“名称与备注”即可编辑。业务、函数、参数和状态节点都支持。输入时自动保存；“恢复原名”保留备注。原始名称和源码关联不会改变，AI 重新生成图也不会覆盖这些标注。刷新会恢复关注节点和展开层次，折叠父节点再展开会恢复内部层次。

这些偏好保存在当前浏览器、同一网站地址下；清除网站数据会删除它们，不会自动同步到其他设备。保存失败时页面明确提示。

布局与样式依赖均开源：PixiJS 为 MIT、ELK.js 为 EPL-2.0，自写 JS/CSS 为 MIT；没有引入 yFiles 代码，见 [第三方声明](../THIRD_PARTY_NOTICES.md)。规则权限的表达方案见 [ReBAC 图设计](../skills/business-observer/references/rebac-graph.md)，该部分当前是设计分析。

## 修改代码时

在示例目录 `examples/delivery` 中执行：

```bash
python observer_generated/runtime/change_sync.py begin --root . --change .stategraph/my-change --request "本轮改动"
# 修改业务代码、必要的探针、tooling/build_graph.py 和测试。
python tooling/dev.py graph --reason "说明图或状态定义为何更新"
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

`sync.json` 中的命令使用参数数组，不执行 shell。`{python}` 表示运行检查脚本的当前 Python，避免写入机器专属路径。首次启动只恢复随版本发布的已审阅基线；修改后的内容不会自动获得通过。

## 隔离与运行模式

业务层只调用自己定义的可选观测接口 `app/ports.py`。`bo_` 适配文件和 `observer_generated/` 属于观测部分。应用实际使用的状态机和资源约束属于业务核心，关闭观测时仍保留。

```bash
python tooling/dev.py ownership
python tooling/dev.py core --out dist/delivery-core.zip
```

核心包包含业务源码、依赖清单和许可证，剔除观测实现与页面；安装依赖后用 `python main.py` 运行。中立接口仍保留空调用。普通运行、关闭观测和注入观测故障的结果由测试对照。

探针增加字段构造、队列和存储开销；状态记录与图刷新也有成本。示例会保留运行记录，尚无长期服务的保留策略或生产性能指标。400 ms 的页面刷新和刻意延时不能用于推断正式系统性能。
