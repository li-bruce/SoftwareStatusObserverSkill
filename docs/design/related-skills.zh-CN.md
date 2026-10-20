# 可借鉴的 Skill 与工具

本项目借鉴具体做法，保持独立安装。下面的工具不是使用本 Skill 的前置依赖，也不替代实际运行验证。

| 参考 | 借鉴的部分 | 本项目的使用边界 |
|---|---|---|
| [Understand Anything：understand](https://github.com/egonex-ai/understand-anything/blob/main/understand-anything-plugin/skills/understand/SKILL.md) | 以文件、函数和关系建立可浏览图，按改动更新 | 静态结构作为候选来源；关键节点仍需业务约定和实际执行证据 |
| [Understand Anything：understand-domain](https://github.com/egonex-ai/understand-anything/blob/main/understand-anything-plugin/skills/understand-domain/SKILL.md) | 从代码材料组织领域和业务步骤，复用已有图 | 本项目先在对话中明确行为，编码时持续绑定；不能把事后推断当成已确认需求 |
| [Spec Kit](https://github.com/github/spec-kit) | 规格、澄清、模板、交接、跨产物核对和可恢复步骤 | 可作为用户选择的开发主线。本 Skill 同步维护状态、探针、源码关联与验证，不要求替换主线 |
| 本地 `state-machine` Skill | 状态、事件、转换、条件和动作的建模顺序 | 该 Skill 面向 UI；这里只借鉴术语清单，应用内部并发、资源和事务仍由实际实现负责 |
| 本地 `skill-creator` Skill | 控制范围、按需提供参考、用真实独立任务检验 Skill 行为 | 独立试验只给需求与 Skill，不给既定答案；模拟用户结果不冒充真人试用 |

核对日期：2026-10-20。Understand Anything 的本地安装版本与网页版本在数据目录等细节上不同，本项目没有复制其执行脚本。Spec Kit 的具体源码取舍见[路线中的参考表](roadmap.zh-CN.md)。

权限表达另参考 [OpenFGA 建模指南](https://openfga.dev/docs/modeling/overview) 和 [SpiceDB](https://authzed.com/docs/spicedb/concepts/schema)。这些资料指导提问、节点类型、证据和测试选择；本版不声称已适配两种引擎。
