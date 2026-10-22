# 第四轮失败与修复记录

1. Windows 受限解释器中 Path('.').resolve() 错误重复末级目录，文件移动失败且没有改写源文件；改用经过工作目录核对的 absolute()，迁移路径仍严格在本试验目录内。
2. 新需求网络第一次缺少节点 source_refs，且把条件节点写成 decision（网络协议应为 condition），D15 又引用了只存在于详细图的生命周期节点。格式验证拒绝。补齐真实 U05/U06 来源，引用现有业务节点，未更改用户答案；再次 validate 为 ready。
3. 普通函数实现最初移动到 app/workflow.py。门禁 verify-01 拒绝：基线必需探针旧路径被移除，四条白盒规则的 source 路径变化被识别为未授权预期变更。未放松检查、修改公共 gate 或重建维护基线。保留原 workflow.py 路径及函数身份，在其中使用普通 Python 分支/SQL；删去执行所依赖的 transition() 和 declaration 导入。测试显式检查业务文件没有状态图依赖，公共导出为 observe。
4. candidate-6 经 bo_upgrade 安装，公共修复包括 LF 规范及窄屏工具栏换行。删除项目重复 CSS 和服务注入；浏览器将直接检查公共样式。

本轮新增预期在维护逻辑实现前写入 acceptance.json，原有 76 条预期和旧白盒实际值检查保持。新一轮基线 maintenance-02 的 baseline_id 等于 candidate-4 已验收 candidate_id；前轮完整归档保留。
5. 完整浏览器揭示全局管理事件的投影归属错误：bo_authority 对 administration 找不到业务运行时错误回退到最后一个打印任务。事件本身和管理员拒绝正确，但查看器按任务过滤后显示没有调用。修复为保留管理事件的原始 attempt，流程状态为空；全局打印机快照仍完整。没有补造业务运行或改动公共查看器。
6. 主会话确认路径迁移误判是公共同步协议缺陷，将提供 candidate-7 的显式 source_moves。当前暂留原路径不作为最终规避；等待公共支持后迁入 app/workflow.py。仍继续 maintenance-02 原基线，保留 verify-01 拒绝证据。

7. candidate-7 已通过 bo_upgrade 安装；22 条 source_moves 将旧类、方法和嵌套函数逐一映射到 app/workflow.py，原文件已移除。只重绑探针 symbol 和白盒 source；旧节点、阶段、参数、预期保留。verify-final、accept、check 均通过。maintenance-02 的 87 个基线文件散列以及 model、intent、acceptance、whitebox 与 candidate-4 归档一致；没有重建基线。最终浏览器 29 项通过，三个隔离错误副本仍被未改写业务预期拒绝。
