# 根据用户意图构建并确认业务网

第一次接入或用户改变行为要求时使用。目标是把用户当前的认知和描述准确表达为任务网、业务网和状态网，通过对话确认理解一致。本 Skill 不主动深度推演业务、不补完整个流程，也不推荐业务规则或方案。

## 先表达当前理解

读取用户描述、已有答案和项目规则，提炼其中的目标、参与者、业务对象、开始事件、关键动作及效果。用短句和局部图呈现；已描述的并行、依赖、共享资源、循环和多个入口应保持原结构。不要根据典型业务模板补入未提及的审批、补偿或恢复机制。

每个顶层节点对应已给定的行为或条件，后续映射到真实状态、核心函数和参数。用户已说明的规则、项目规则、当前推断和待确认项分别标明来源。缺少信息时保留未说明或待确认，不替用户猜出确定规则，也不宣称业务已完整。

## 只为确认原意提问

保留必要的澄清和反例追问。反例只检验当前理解是否符合原意，不用于发掘更多业务需求。提问应能指出所依据的原话或图中关系，以及答案会如何改变当前图。仅有理论上可能发生的情形，不足以发起追问。

| 已有上下文 | 可以确认的内容 |
|---|---|
| 用户已描述内容检查和预览，但“检查通过即可下载”指向不明 | 这里的“检查”指哪一项，当前图的下载条件是否表达准确 |
| 用户已描述多个运行并存，又说“取消这次任务” | “这次”指当前一次运行还是这个任务的所有运行 |
| 新补充说明与已确认的图直接冲突 | 补充是否替代旧规则，受影响的节点或关系如何更新 |

答案已明确、能从已有规则直接推出、或属于普通可逆实现选择时不再询问。有歧义时用自然语言呈现不同理解及其影响，不推荐其中一种业务选择。每轮只呈现必要的问题，通常不超过 1–3 个；不按权限、并发、取消等主题逐项盘问。

用户继续在开发工具中对话，Web 只展示当前讨论范围。只改文案、布局或无行为变化的重构时核对现有图即可。当前描述在图中已有一致表达时结束确认，不要求用户额外审批整份需求文档。

推荐、默认选中、沉默和等待时长都不是用户答案。用户明确授权 AI 决定的选择可记录为 delegated_choice，并保留授权范围和理由；“实现细节由你决定”不自动授权改变业务含义。本 Skill 不主动索取这种授权以绕过确认。

## 对话或外部规则补充后更新同一张图

按已确认内容更新触发事件、前置状态、条件、参数、后继状态、效果及已说明的等待/恢复行为，保留稳定节点身份。同步局部源码映射、状态机和针对这些规则的验证场景。确认反例服务于理解；验证反例服务于检查已定规则，两者都不自动增加业务要求。

部分答复只解决对应项。用户改变先前规则时保留旧决定和变更来源；直接冲突未解决前，不同时声称两种含义都已确认。用户认可图的某个范围，不意味着认可图外假设或所有实现结果。

用户或其他 Skill 可以继续完善业务，再将补充内容交回本 Skill。标明文档或对话定位、提出者和确认状态；已采纳的项目规则可引用为 project_rule，未确认的外部建议保留为候选，不能伪造 user_answer。然后更新受影响的图、实现绑定与检查，保留原有源码、运行和业务验证门禁。

## 最小可检查记录

在项目内维护 `discovery.json`。记录已给定的业务以及必要的理解确认；没有未决问题时，decisions 可以为空。脚本只检查记录及引用，不负责发现业务规则缺口。结构见 [例子](../assets/discovery.example.json)。

- sources：id、kind（user/project_rule/inference/assistant）、原话 text 和定位 locator。测试回复明确写测试来源，不伪装成人类反馈。
- networks：id、title、actors、trigger、outcome、nodes、edges。节点有 id/label/kind/source_refs；边有 id/from/to/relation/label/source_refs，可引用 decision_refs。支持循环；跨网共享含义可复用来源，各节点身份仍唯一。
- decisions：id、topic、question、why、affects、blocking、status、source_refs。可加 priority（1 优先）、depends_on、2–3 个 options（id/label/effect）、asked_in（实际已问出的 assistant 来源）。
- status 为 open/resolved/assumed/deferred。只有 resolved 表示关键分歧解决。resolution 包含 kind（user_answer/existing_rule/delegated_choice）、text、source_refs；delegated_choice 另有 rationale。assumed/deferred 用 note 写明假设或未做范围，不能把关键问题隐藏成不阻塞。
- 实现后：节点的 model_nodes 指向原图 ID；外部未实现节点写 outside_reason。关键决定的 links.requirements/model_nodes/checks 指向需求、原图和真实验收项。
- 已确认规则改变时，在 changes 保存 id、decision、previous（原决定完整对象）、source_refs、reason。使用 --previous 或变更检查比对，不能静默抹去旧答案。

```text
python SKILL/scripts/requirements_dialogue.py validate --file discovery.json
python SKILL/scripts/requirements_dialogue.py questions --file discovery.json
python SKILL/scripts/requirements_dialogue.py check --file discovery.json
```

`questions` 只从已写出的未决项中选择本轮问题；已问但未答的列为 awaiting_answers，不重复发送。它不会自动从自然语言发现所有模糊点。更新需求后还要核对图是否如实表达已有描述，不能把“脚本没列问题”当作业务规则已经完整。

新项目在 `sync.json` 加入 `"discovery": "discovery.json"`，纳入 `change_sync verify/check`。实现后可单独核对映射：

```text
python SKILL/scripts/requirements_dialogue.py check --file discovery.json --intent intent.json --model behavior.json --acceptance acceptance.json
```

未解决的关键问题、无答案来源、丢失原业务节点映射或决定没有对应需求/检查，都会使交付检查失败。文件内容与脚本也纳入候选版本，回答改变后旧验收失效。旧项目未配置 discovery 时保留兼容行为，应明确尚未接入这一检查，而不是声称已强制澄清。

确认是否符合用户原意，需要对照原话和用户对图的反馈；JSON 校验不证明这一点，也不证明业务规则穷尽。检查已有决定、严格定义、源码映射和实际运行的要求保持不变。
