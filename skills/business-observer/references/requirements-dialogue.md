# 从需求到业务网，再澄清状态规则

第一次接入或用户改变行为要求时使用。先读已有用户答案和项目规则；无需重新询问已经明确的选择。只改文案、布局或无行为变化的重构时，核对已有业务网即可，不重启需求访谈。

## 先给用户一个具体的理解

提炼目标、参与者、业务对象、开始事件、关键动作与成功效果。用短句或小图描述顶层链路。遇到并行、依赖、共享资源、循环或多个入口，表达成网或几条相关链，不强行串成单一流程。没有结束状态的事件服务、协作编辑器等，应说明持续维护的约束，不能编造一个完成审批流程。

每个顶层节点对应有业务意义的行为或条件，后续映射到真实状态、核心函数与参数。不要用页面菜单或目录树代替业务网，也不要先画全量调用图再猜上层含义。

明确区分：用户已说明的规则、现有项目规则、当前推断和待询问项。推断可以先画成候选，但不能冒充已确认的状态转换。用最少的文字先说明当前理解，再问具体分歧。

## 找会改变程序行为的模糊点

根据这次需求判断，不机械询问整张清单：

| 需求中的不确定处 | 要澄清的实际选择 |
|---|---|
| “处理完”“成功” | 哪个效果持久保存才算成功；是否要全部分支完成 |
| “可以同时做”“等待空闲” | 哪些活动可并行；容量在哪个范围共享；等待什么、由谁恢复 |
| “审批后执行”“权限有变化” | 角色、范围、有效期、参数版本；执行中失效与替代授权如何处理 |
| “改一下再跑” | 新旧参数和运行如何隔离；旧任务是否继续、结果能否提交 |
| “取消”“失败重试” | 取消请求与实际停止是否分开；已经发生的效果怎么办；重试是否重复提交 |
| “同步”“自动恢复” | 冲突时以谁为准；哪些条件满足后恢复；需用户操作还是自动触发 |

先问会决定顶层网形状、外部效果、权限或并发约束的分歧，再问依赖它的细节。一个问题说明场景与后果，例如“检查已通过、预览仍在生成时，能否先下载文件？这决定下载是否必须等待两个分支。”选项用具体行为，不用“强一致”“最终一致”等代号。合理时给 2–3 个互斥选项；不适合封闭选择时用一个短的开放问题。

每轮通常 1–3 问。仅向用户展示这一轮，内部可保留后续问题。答案已知、只需按现有规则推导、或普通可逆实现选择，不再询问。推荐选项需要依据；推荐、默认选中、沉默和等待时长都不是用户答案。

使用当前环境的异步提问工具时，将相关问题集中提交；继续整理结构和不依赖答案的工作。关键行为尚未确定时，相关实现和验收保持未定。没有工具则直接用简短文字提问。用户明确授权自行决定时，可以作出带理由的工程选择，来源记为 delegated_choice，不能写成用户逐项选择。

授权按用户给出的范围使用。“实现细节由你决定”允许选择实现已定规则的方法，不自动包含尚未确定的取消对象、权限范围、成功条件或对外效果。例如，同一任务的新旧运行并存，用户只说“取消时实际停止再归还资源”，仍未回答取消哪几次运行；不能因为单次取消较保守，就把它称为普通实现细节。若用户明确把这项业务选择也交给你，才记录 delegated_choice 及依据。能够从已确认规则直接推出的结果则无需再问。

## 回答后要改变模型

把答案写成可执行规则：触发事件、前置状态、条件、参数类型/范围、下一状态、效果以及等待/恢复条件。更新受影响的顶层节点/边，随后同步局部代码映射、状态机和反例。不要只保存一份问答记录，代码仍使用旧规则。

部分回答只解决对应的问题，其他问题继续等待；回答引入新的分支时，只补问新的关键分歧。用户明确改变先前规则时保留旧答案和变更依据，更新受影响的规则与测试；两句话是否互相替代不清楚时，问清这个冲突，不同时宣称两条都已确认。

停止提问的条件是：当前要实现的行为已有可执行解释，关键分歧已解决，剩余事项不影响该部分正确性。不要要求用户再批准一次完整需求文档才能开始已经授权的工作。

完成后重新对照用户原话核对每个 delegated_choice：授权是否包含这一选择，理由是否真正守住了用户已定的约束。发现自己扩大解释时，保留原记录、说明纠正原因，将尚未授权的业务选择恢复为未决；不要编造一条新的用户答复。记录校验不会代替这一步语义核对。

## 最小可检查记录

在项目内维护 `discovery.json`。脚本只检查记录及引用，业务提炼和发现遗漏由 agent 完成。结构见 [例子](../assets/discovery.example.json)。

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

`questions` 只从已写出的未决项中选择本轮问题；已问但未答的列为 awaiting_answers，不重复发送。它不会自动从自然语言发现所有模糊点。更新需求后还要重新做语义核对，不能把“脚本没列问题”当作需求已经完整。

新项目在 `sync.json` 加入 `"discovery": "discovery.json"`，纳入 `change_sync verify/check`。实现后可单独核对映射：

```text
python SKILL/scripts/requirements_dialogue.py check --file discovery.json --intent intent.json --model behavior.json --acceptance acceptance.json
```

未解决的关键问题、无答案来源、丢失原业务节点映射或决定没有对应需求/检查，都会使交付检查失败。文件内容与脚本也纳入候选版本，回答改变后旧验收失效。旧项目未配置 discovery 时保留兼容行为，应明确尚未接入这一检查，而不是声称已强制澄清。

自然语言来源是否真实、问题是否覆盖所有重要分歧、答案是否被正确解释，仍需要对照用户原话与独立试用；这些不是 JSON 校验能证明的。
