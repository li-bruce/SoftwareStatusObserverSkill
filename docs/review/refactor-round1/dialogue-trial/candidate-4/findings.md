# 本轮发现、修复和证据边界

- 独立复核否定了原项目自写的同名 BOStateGraph 和 SVG 页面。原文件、当时的通过报告和活动变更基线全部保存在 `../deviation-01/`；这些报告不计作公共 Skill 集成验收。
- candidate-3 使用 `bo_upgrade.py` 安装公共核心、桥接运行库及完整 Pixi/ELK 查看器。项目特有共享资源约束迁到 `bo_stategraph/project_constraints.py`，查询适配单独放在 `bo_stategraph/query.py`，没有给每个运行复制两台打印机。
- 发现公共旧回放只支持运行内资源日志，无法重建本项目共享资源的中间快照。按主会话要求等待公共修复，没有替换 recording.js 或填入最终状态。candidate-4 增加精确事件快照协议后，再通过 bo_upgrade 更新。升级输出见 upgrade-apply.json。
- 新增运行创建构建编号的事务内持久化。旧数据缺少编号时保留 unknown/partial，不把现在的构建归给历史运行。
- 首轮完整源码定位失败，原因是服务适配器返回 text，公共协议实际字段是 source。修复适配器，公共 viewer 未改。
- 第一次回放详情检查选择了业务概述层。下钻到实际 Workflow.schedule 节点后，no_valid_approval、queue_seq 和打印参数可查；测试使用真实键盘焦点和按钮操作。
- 390/320px 公共样式的工具栏不换行，搜索框右边界固定为 398px。原始失败证据见 before-upgrade-browser.json。修复放在独立 static/project.css，服务适配器添加样式链接；所有安装的公共文件仍与 candidate-4 哈希一致。复测三个宽度 scrollWidth 等于视口宽度。
- runtime_frames 仅由捕获事件的 revision 对应的原始 SQLite history 快照构造。缺修订不使用最近/最终快照；同一事件的进程、构建、完整状态修订由公共记录器再次校验。
- 完整查看器录制保存了 151 个真实合成事件和 151 个精确帧。浏览器检验了实际等待/恢复、取消持有资源、停止确认释放，以及 available/holder 的 before/after；回放及所有图交互均不增加业务状态修订。

以上属于独立 AI 接入及脚本浏览器验收。需求方为主会话模拟，不是真人可用性研究；设备为 SQLite 本地模拟，不证明物理打印成功、真实登录权限或任意并发系统正确。
