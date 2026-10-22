# 工作室 3D 打印任务工具

普通 Python + SQLite；两台本地模拟打印机。图展示实际函数、参数、审批判断、等待与恢复，以及占用和设备确认后的释放。需求方为主会话模拟，属于独立 AI Skill 对话验收，不是真人测试。

在本目录打开 PowerShell：

```powershell
$trialPython = '../SoftwareStatusObserverSkill/.venv/Scripts/python.exe'
& $trialPython -X utf8 -B server.py --demo --port 8897
```

打开 `http://127.0.0.1:8897`。若端口被占用，使用 `--port 0`，读取命令输出地址。新数据库会执行一段真实合成演练并保存记录；默认数据在 data/studio.sqlite。已有数据不会被 demo 覆盖。要重现新演练，传入另一个项目内 `--db data/new-demo.sqlite`。

选择“记录”中的演练记录，再选择“任务-B · v1”。沿时间轴可看到它等待机器、失去有效审批、被后续有资格任务越过、重新取得资格、占用机器、请求取消、等待停止确认、释放。任务-B · v2 是独立运行，参数与状态不会混用。点击节点查看实际输入输出；双击展开；“查看实际源码”读取对应构建的快照。拖动、名称、批注、筛选、核心标记保存在 bo_stategraph/config/views/local.json。

图不提供业务按钮。CLI 与 `/operator/command` 是独立的本地操作入口：

```powershell
& $trialPython -X utf8 -B main.py show
& $trialPython -X utf8 -B main.py command '{"command":"submit","submitter":"alice","printer_id":"P1","dimensions":[80,60,40],"material":"PLA","parameters":{"layer_mm":0.2}}'
```

提交命令返回 run_id。使用 approve（run_id、approver、expires Unix 秒）、cancel（run_id）、confirm（run_id、kind=complete/stop）、role（actor、printer_id、active）等命令。运行中的服务器会维护到期检查；单独 CLI 模式可调用 schedule 重新判断时间。角色与操作者是本地合成身份，没有实现登录认证或多租户服务。

首次提交/修改参数会真实执行两个检查线程；异常保存为 check_error，具体失败项与错误类型在图和 SQLite 中可查。每次参数变化生成新版本；未打印旧版本作废，已打印旧版本继续。没有模拟真实 STL/3MF 解析、打印驱动或物理效果。

开发与复现：

```powershell
& $trialPython -X utf8 -B tooling/build_model.py
& $trialPython -X utf8 -B observer_runtime/bo_sync.py scan --root (Get-Location).Path
& $trialPython -X utf8 -B tooling/gate.py check
& $trialPython -X utf8 -B tests/test_policy.py
& $trialPython -X utf8 -B tests/test_project.py
& ./tooling/browser_check.ps1
```

重新生成或修改源码会使旧验收失效，这是预期门禁行为。依据 AGENTS.md 继续已有 change 或开始新的 change，运行 inspect → review → verify → accept → check。不要反复重建基线。完整证据、失败修复、检查范围见 [review/README.md](review/README.md)。

观测只选择核心事件，内存上限 8,000；日志按 4 MiB 轮转，丢失显示 gap。保存的记录独立于 UI 缓存。SQLite 事务历史不是 UI 缓存，本地演练不自动清理。关闭采集后业务与状态网仍可运行；本项目没有声称零开销或任意进程崩溃后自动恢复所有检查。
