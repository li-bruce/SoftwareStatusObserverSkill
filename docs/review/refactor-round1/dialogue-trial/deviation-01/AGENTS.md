# 本项目开发约定

仅在本目录开发。使用只读冻结 Skill：`../SoftwareStatusObserverSkill/.validation/refactor-trial/candidate-1/business-observer/SKILL.md`；不修改原 Skill、其他示例或已有服务。需求方为主会话模拟，不是真人测试。

读取 `discovery.json`、`intent.json` 和 `review/README.md`。默认用已确认状态网指导实现，维护独立 `bo_stategraph/`、源码映射、实际参数和运行证据。未决行为不能用实现框架授权代定。

实际解释器：`../SoftwareStatusObserverSkill/.venv/Scripts/python.exe`。以下命令在本项目目录执行；传给冻结脚本的 root 必须是本项目绝对路径。

```powershell
& ../SoftwareStatusObserverSkill/.venv/Scripts/python.exe -B tooling/gate.py begin --change .stategraph/implementation-01 --request '实现第三轮已确认的本地打印调度；D08、D09 依实际答复补全' --requirements R01 R02 R03 R04 R05 R06 R07 R08 R09 R10 R11
& ../SoftwareStatusObserverSkill/.venv/Scripts/python.exe -B ../SoftwareStatusObserverSkill/.validation/refactor-trial/candidate-1/business-observer/scripts/bo_sync.py scan --root 'C:/Users/Lvi_P/Documents/Work/CF/平台软著/stategraph-refactor-trial-20261022'
& ../SoftwareStatusObserverSkill/.venv/Scripts/python.exe -B tooling/gate.py inspect
& ../SoftwareStatusObserverSkill/.venv/Scripts/python.exe -B tooling/gate.py verify
& ../SoftwareStatusObserverSkill/.venv/Scripts/python.exe -B tooling/gate.py accept
& ../SoftwareStatusObserverSkill/.venv/Scripts/python.exe -B tooling/gate.py check
```

已有 active change 时继续它，不重建基线。每批编辑后读取 `.stategraph/maintenance.json`，处理图、探针、状态和源码差异；最终交付正常入口是 `tooling/gate.py check`。当前入口尚未接入 architecture_guard，完整交付前必须补齐，不能把当前开发阶段宣称验收通过。
