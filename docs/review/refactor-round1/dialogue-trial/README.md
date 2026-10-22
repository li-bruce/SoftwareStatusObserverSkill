# 3D 打印工具：独立 Skill 接入验收

维护功能及普通 Python 执行方式已验收。打开运行图：[本地查看器](http://127.0.0.1:50393)。服务核实时间、构建及事件数量见 [live-service.json](round-04/live-service.json)。

需求方由主会话模拟。本对话独立接入冻结 Skill；本地设备与身份均为合成数据。以下是独立 AI 和脚本运行证据，不是真人可用性或物理打印验证。

## 当前交付：维护与 observe 模式

维护期间仍可提交、检查、审批和排队，只阻止新的打印开始。已在打印的任务继续；管理员手动退出维护后，按原入队顺序及当前有效审批调度。维护状态持久化，无自动到期。工作室管理员资格独立于提交者和打印机审批角色，演示管理员为 `admin`，配置见 `config/studio.json`。

业务执行器为 `app/workflow.py` 中的普通 Python 函数、条件和 SQL，不消费状态机声明。`development_mode` 与 `execution_mode` 均为 `observe`；公共状态图、运行监控、完整 Pixi/ELK 查看器继续工作。

- 公共代码来自冻结 candidate-7，通过 `bo_upgrade` 安装。公共文件散列核对通过，[再次升级计划](round-04/public-upgrade-plan.json) 无变化、无冲突；已删除项目 CSS 注入。
- [stage.json](round-04/stage.json) 绑定 accepted 候选、构建、证据文件散列与源码归档。最终构建为 `fcd4b92e126df7a537f52ed51e41fede833f369a350377d5b5d2e218eaf43148`。
- [verify-final.json](round-04/verify-final.json)：437 项映射见证、333/333 项独立业务断言、公共导出与状态规则全部通过。
- 23 场景 × 采集开启/关闭/故障 = 69 次运行；全部 2,013 个事务快照检查共享资源和前置条件，新增维护检查区分“已开始继续”与“维护时新开始”。见 [test-project.json](round-04/test-project.json)。
- [browser-report.json](round-04/browser-report.json)：完整查看器 29 项 Chrome 交互检查，包括真实维护/拒绝事件的精确回放、管理命令录制、源码与实际参数、区域拖动、批注、只读检查、保存冲突，以及 1440/390/320px 宽度。
- 当前演示 195 个事件对应 195 个原始 revision 精确帧，没有用最终状态填充中间帧。全局打印机资源与管理事件身份独立保留。
- [mutations.json](round-04/mutations.json)：审批到期边界、尺寸上限和忽略维护三个隔离错误副本，未同步时正常门禁均拒绝；如实重新映射后映射仍通过，原业务预期分别检出 15、3、32 个失败。原实现与预期没有被这些实验修改。
- 通过 22 条显式 `source_moves` 将执行器迁至 `app/workflow.py`。原 76 条业务预期、6 条白盒规则和检查均保留；仅按已审阅迁移重绑源码位置，探针节点、阶段和参数不变。
- [accept.json](round-04/accept.json)、[check-console.jsonl](round-04/check-console.jsonl) 为正常入口最终通过记录，含 architecture_guard；[accepted-source.zip](round-04/accepted-source.zip) 保存源码、配置、基线和验收记录。

## 前一阶段与纠偏记录

[candidate-4/stage.json](candidate-4/stage.json) 和 [candidate-4/accepted-source.zip](candidate-4/accepted-source.zip) 固定保留维护功能之前的已验收阶段：256 项映射、228 项业务断言、48 次场景运行、1,398 个事务快照及 24 项浏览器检查。本轮 maintenance-02 从该候选建立；其 87 个基线文件散列以及 model、intent、acceptance、whitebox 均与前阶段归档一致。最初 implementation-01 基线也未改写。

[deviation-01/evidence.json](deviation-01/evidence.json) 保留被独立复核否定的简化 BOStateGraph/SVG 实现和旧通过报告，不计入当前集成结果。前轮协议与回放修复见 [candidate-4/findings.md](candidate-4/findings.md)。

[round-04/dialogue.md](round-04/dialogue.md) 保存 U05/U06 澄清；[round-04/failures.md](round-04/failures.md) 记录源码迁移门禁误判、管理事件投影错误和公共 candidate-7 修复后的最终结果。保留失败记录，没有重建基线或修改预期来获得通过。

## 复现

在项目目录执行：

```powershell
$trialPython = '../SoftwareStatusObserverSkill/.venv/Scripts/python.exe'
& $trialPython -X utf8 -B server.py --demo --port 0 --db data/reproduce.sqlite
& $trialPython -X utf8 -B tooling/gate.py check
& ./tooling/browser_check.ps1
& $trialPython -X utf8 -B tooling/mutation_check.py
```

服务命令持续运行，其他检查在另一终端执行。浏览器脚本会启动独立服务和数据库；故障实验只写隔离副本。未来迭代先保留本轮 accepted 结果，再正常 begin 新 change；不能把旧 receipt 当新代码通过。公共代码通过 `bo_upgrade` 更新。

## 验证边界

关闭观察接口不改变这些场景的业务结果，未声称零开销。静态调用关系不证明运行调用；事件顺序不证明因果。SQLite 互斥与两个线程竞争测试只覆盖本实现和明确场景，不能推广到分布式设备。检查线程中断后不会自动恢复；设备占用、等待、维护和停止确认状态保存在数据库。没有实施真实认证、STL/3MF 解析或物理打印。
