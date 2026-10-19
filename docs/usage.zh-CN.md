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

Skill 应先整理谁触发什么操作、涉及哪些对象、成功或等待的条件，再询问会改变执行结果的缺失规则。已经回答的内容直接引用；尚未回答的问题保留为未决，不把 AI 的建议当成用户决定。示例记录在 `assets/discovery.example.json`，检查命令为：

```text
python <skill>/scripts/requirements_dialogue.py check --file discovery.json
```

涉及权限、提交、等待或恢复的关键问题未解决时，已接入的变更检查会拒绝验收。独立脚本只能校验记录和关联，问题是否完整、回答是否理解正确仍需审阅。

## 看懂运行图

| 层次 | 要回答的问题 |
|---|---|
| 业务链路 | 这次操作经过哪些步骤，为什么停在这里？ |
| 内部状态与关键代码 | 哪项活动在执行，输入是什么，哪个条件还没满足？ |
| 局部程序结构与源码 | 哪个函数负责这一步，调用和实现在哪里？ |

主流程的“正在检查”是汇总。内部活动的等待、执行、完成等状态仍保存在每次运行中，可以展开和查询；折叠图不会删除状态。记录按运行身份、参数版本和构建版本对应，缺失数据不推测为成功。

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
