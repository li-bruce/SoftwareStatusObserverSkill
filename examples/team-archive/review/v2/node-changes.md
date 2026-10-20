# 第二轮节点与关键参数

本文件对应模拟开发演练，不是真人用户研究。

| 节点 | 本轮变化 | 关键参数 |
|---|---|---|
| `project_limit` · 项目归档大小上限 | 新增。每项目持久化默认 8192 字节，配置独立于内容版本 | `project_id`、`limit_bytes`、`limit_revision` |
| `set_size_limit` · 调整项目大小上限 | 新增。只接受正整数，调整后重查未结束运行 | `project_id: str`、`limit_bytes: int` |
| `size_guard` · 正文是否在当前上限内 | 新增。UTF-8 正文字节数 ≤ 当前上限，在开始、继续和提交时调用 | `content_bytes`、`limit_bytes`、`limit_revision`、`allowed`、`excess_bytes` |
| `commit_guard` · 当前是否仍有资格 | 更新。将实时大小判断加入资格合取条件 | 新增 `size_allowed` 和当前字节数、上限、修订号 |
| `flow.policy`、`flow.archive` | 更新说明，纳入当前大小资格与提交复核 | 保持原 ID |
| `flow.checks` | 继续使用原等待/恢复与检查复用，显示明确的等待原因 | 已通过结果、`resume_required`、`wait_reasons` |

AST 自动增加 `code.f3f4c403913bddaf`，对应 `archive_app/policy.py::check_size` 的局部函数结构。共新增 4 个模型节点（3 个业务映射、1 个静态代码节点），55 个原有节点 ID 全部保留，模型从 55 节点/114 边变为 59 节点/124 边。参数字段继续按捕获声明在同一图内生成。

项目 ID 和布局 ID 均保持 `team-archive-trial-01`。首版的“本次双检查”、固定标记和备注已在第二版浏览器中核验；同一视野的 `layout-v1-same-view.png` 与 `layout-v2-same-view.png` 保留共享节点位置对照。

顶部显示当前项目上限；节点详细值保留实际历史判断。完成后调低上限，不伪造该运行的新判断，旧值会标为历史。回看更早活动帧时不借用最终上限。版本菜单可以读取首版冻结源码和保存场景。
