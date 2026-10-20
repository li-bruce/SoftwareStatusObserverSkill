# 第二轮设计与独立预期

状态：需求澄清；只有本轮确认的规则形成约束，没有业务实现。

## 图的变化

- `scope_check` 改为“是否直接负责所在文件夹”，保留原稳定 ID。
- 增加 `folder_assignments`，把直接负责关系作为范围判断的明确输入；祖先目录不提供继承权限。
- `approval_check` 明确目标为项目、操作人、资料、内容版本四元组；增加 `approval_target` 参数节点。
- `archive_commit` 改为“保存资料版本快照”。
- 增加 `archive_unique` 判断，要求相同资料/版本不得重复创建归档记录。
- `edit_approval` 明确“新版本不能沿用旧版本审批”；旧运行的处理仍待 D06。

所有新增节点仍在同一张候选图中，源码绑定待实现。图修订为 discovery-r02，第一轮快照保持不动。

## 参数和函数约定候选

| 业务节点 | 候选源码位置 | 关键参数及类型 | 结果与来源 |
|---|---|---|---|
| scope_check | archive_app/policy.py::is_direct_manager | project_id:str、operator_id:str、folder_id:str、assignments:list[dict] | bool；只比较直接归属和负责关系。U02 |
| approval_check | archive_app/policy.py::evaluate_approvals | project_id:str、operator_id:str、document_id:str、content_version:int、approvals:list[dict] | 逐条目标匹配及整体结果；整体组合/审批者规则待 D05，不预写 any/all |
| archive_unique | archive_app/store.py::find_archive | document_id:str、content_version:int | 该资料/版本的现有记录身份或缺失；读取实际 SQLite |
| archive_commit | archive_app/store.py::save_archive_snapshot | 资料身份、内容版本、固定内容快照及实际事务 | 保存效果/已有记录；重复请求的界面响应待实现选择，不能新增第二条记录 |

这是待绑定约定，不是已存在函数。稳定业务规则优先，最终函数签名在编码前 whitebox 中确定。状态机和活动/资源声明待 D04、D06、D08 得到可执行解释后建立。

## 独立验收预期

新增 acceptance.json，仅依据 U02 的已确认规则：

- 直接负责人匹配；只管理上级文件夹者不因祖先关系获权；子目录按自己的直接关系判断。
- 审批目标四个字段逐项不匹配时，该审批目标不匹配；不把此结论扩大成整体审批拒绝。
- 成功归档保存准确内容与版本；相同资料/版本重复归档后仍只有一条记录。
- 后续修改原资料不改变已经保存的快照；归档动作不移动或删除原资料。

这些是尚未执行的精确观察预期。实现的观察适配器必须实际运行程序并读取 SQLite，不得读取 acceptance 生成结果。完整归档场景还需满足后续确认的审批和检查前提，届时补充 fixture，而不改写这些已经确认的结果。

## 工程选择范围

本地 SQLite 应用实现可以自行设计；business-observer 作为同步维护业务约定、状态/活动、源码映射、参数、探针和真实验证材料的支线接入。未选择全局框架、全局 hook 或生产依赖。

## 当前未知

审批者和候选组合、共享名额和并发、运行中的撤销/改版、具体检查内容/失败、启动与自动恢复。本轮没有从“实现方案由你选择”推导这些业务答案。
