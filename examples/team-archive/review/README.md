# 模拟用户演练：团队资料归档

本目录记录独立 Skill 使用演练，不代表真人可用性测试，也不代表生产需求确认。

- 日期：2026-10-20（Asia/Shanghai）。
- 允许的输入：本轮模拟用户需求、指定 business-observer Skill 副本、后续模拟用户答复。
- Skill：`../skill/business-observer/SKILL.md`（相对 project；只读）。
- 不读取 SoftwareStatusObserverSkill 源码、其他旧 demo 或测试答案；只允许调用指定的 Python 解释器。
- 所有新文件仅放在本 project；使用合成数据；外部发布不在本会话中执行。
- 当前阶段：第三轮需求澄清；D01–D05 已解决。本轮等待 D06–D08 的剩余边界，D09 容量变更时点尚未问。尚无应用、执行状态机、运行事实或通过的业务验收。

## 材料

- `round-01/dialogue.md`：模拟用户原始需求与本轮回复。
- `round-01/design.md`：来源区分、候选图与待绑定位置。
- `round-01/commands.md`：前期读取命令及结果摘要。
- `round-01/tool-results.json`：运行 Skill 工具的实际命令、退出码和输出，执行后生成。
- `round-01/focus.json` / `focus.md`：从同一候选图提取的当前局部图，执行后生成。
- `../discovery.json`：业务网、未决问题、实际提问来源。
- `../intent.json`：已知目标及边界。
- `../behavior.json`：尚待源码绑定的候选图；不可当作运行证明。

后续答复与变更按轮次追加，保留旧图、旧问题、失败和修复；不覆写已有轮次作为新证据。

第二轮记录见 `round-02/dialogue.md`、`design.md`、`focus.md` 和 `results.md`；本轮的 intent/discovery/behavior/acceptance 快照与工具原始输出也保存在 round-02。
