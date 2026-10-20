# 第一轮实际结果

本记录属于模拟用户演练。

| 操作 | 退出码 | 实际结果 |
|---|---:|---|
| requirements_dialogue validate，带 intent/model | 0 | valid=true，ready=false；无格式错误，8 个关键业务问题未决 |
| requirements_dialogue questions | 0 | awaiting_answers 为 D01、D02、D03；未返回新的问题 |
| requirements_dialogue check | 1 | record_valid=true；unanswered_business_questions 拒绝交付，符合当前未答状态 |
| focus_graph，`--root .` | 1 | 路径被解析为 project/project/behavior.json，文件不存在 |
| path_repro.py | 0 | `Path(".").resolve()` 复现重复 project；绝对路径与 `absolute().resolve()` 正常 |
| focus_graph，明确绝对 project 路径 | 0 | 提取成功；5/10 节点、8 条边界、无预算截断、complete=false、无运行事实 |

## 路径问题

原始错误完整保存在 `tool-results.json`；最小复现为 `path_repro.py`，实际输出保存在 `path-repro-result.json`。

解释器版本为 Python 3.13.13。当前环境中，工作目录是预期的 project，但 `Path(".").resolve()` 得到多一层 project 的路径。Skill 的 focus_graph CLI 在入口调用此表达式，继而找不到模型。

处理：按同一 CLI 的 `--root` 参数提供已核对的绝对项目路径。Skill 仍执行原有 `contained` 路径限制和原有提取逻辑，未修改 Skill、复制工具实现、跳过校验或弱化规则。成功命令与输出保存在 `focus-absolute-root-result.json`。

这只是可用的正确参数调用，未修复相对路径环境问题；后续命令继续使用绝对项目根，原失败保留。

解释器还输出 `Failed to find real location of C:\Users\Lvi_P\miniforge3\python.exe`。各命令仍执行并返回上述结果，告警保留；未读取或修改 Python 父项目。

## 当前交付边界

- 已生成候选图的局部视图 `focus.json` / `focus.md`。
- 图的稳定身份来自 behavior.json；5 个选中节点与 8 条范围外原边保留。
- 没有业务代码、实际状态机、真实参数/调用事件、同步验收或浏览器任务证据。
- 当前通过的是记录格式和静态局部图提取，不是业务正确性或真人易用性。
- 等待本轮 3 个问题的模拟用户答复。
