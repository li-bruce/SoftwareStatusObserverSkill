# 伴随修改与检查机制

本流程用于正在开发或持续修改的程序。业务抽象由需求约束，局部结构由静态证据生成，可执行状态机由真实程序声明导出，运行事实由实际探针/存储读取。每个小变更都维护这几部分，不在最终写完代码后才补图。

## 项目接入

沿用 `intent.json`、`behavior.json`、`manifest.json`，增加项目自己的 `sync.json` 和 `acceptance.json`。参考 [配置示例](../assets/sync.example.json) 和 [验收约束示例](../assets/acceptance.example.json)，按本项目的领域和路径修改，不继承示例审批规则作为通用要求。

`sync.json` 的关键字段：

- `code_files`：选入静态索引的 Python 文件，同时列入行为模型的 `source_files`。新入口/新文件必须判断是否加入，未扫描内容不在覆盖声明内。
- `watch_files`：模型生成器、业务验证脚本等额外输入。观测/测试命令中的项目 `.py` 脚本必须被跟踪；工具自身内容也参与版本绑定。
- `discovery`：需求澄清记录的项目相对路径，如 `discovery.json`。新接入项目添加此项；文件自动纳入版本绑定。关键问题未解决、答案来源不符、业务网未映射或决定缺少需求/验收项，会使 verify/check 失败。旧项目未配置时保持兼容，不声称已启用澄清检查。流程见 [需求提炼与反问](requirements-dialogue.md)。
- `required_probes`：必需的字面量探针点，包含 node、phase 和可选 `path::symbol`。`probe_callees` 指定真实调用形式，例如 `trace.record`。
- `required_runtime_probes`：指定用例开启采集时必须真正出现的事件。静态存在但执行不到的探针不会因此通过。
- `observations_command`：一个经过审阅的参数数组；运行项目自己的观测适配器，不能指向未经检查的任意命令。没有 shell 字符串拼接。
- `test_commands`：项目已有的相关测试命令数组；根据改动选必要回归，不能用图生成器的自检代替业务断言。

模型生成器在保留人工/AI 编写的业务分组之后调用：

```python
from vendor.code_structure import scan, enrich

index = scan(root, ["domain.py", "workflow.py", "store.py"])
model = enrich(authored_model, index, depth=1)
```

`authored_model` 来自业务需求与同源状态机声明。`enrich` 保留其业务 ID、分组和规则，从这些节点的源码锚点生成局部函数及静态调用边；函数参数、返回类型和调用实参均有源码依据。静态辅助节点默认没有运行事件，不会被标成“已执行”。不同业务调用上下文可以映射到同一函数。

独立 CLI 也支持 `code_structure.py scan` 和 `project`；后者要求业务映射输入与生成图输出为不同文件。未改文件复用之前的解析结果；提取器内容改变会使缓存失效。Python 动态分派、反射、回调和未解析对象保持 unresolved，不把普通 AST 当完整 CFG/数据流分析。

## 需求约束与真实观测

验收文件由已确认需求及明确标记的工程假设导出；在实现前记录正常和反例的可观察结果。它与业务实现、图生成器及运行取值脚本分开维护。

`checks` 每项包含 `id`、`requirement`、`case`、`path`、`equals`，约束实际返回值、权威状态、效果数量或关键值。当前工具使用精确 JSON 值比较，不支持任意表达式求值。为每个被检查用例运行 on/off/fault 模式；若另有模式，配置 `probe_modes`。

`model_checks` 约束上层关键声明及映射，例如审批聚合 ANY、关键 guard 表达式、业务父子关系或上下文类型。`path` 遍历 JSON；在节点数组上使用字符串时，按节点 `id` 选择。优先约束有业务意义的结构，不锁定所有措辞和布局。没有被这些约束覆盖的自然语言说明，仍需对照需求和源码审阅。

观测适配器**调用真实程序并读实际存储/结果**，不能读验收文件生成“正确答案”，也不能从图上反推程序状态。它的标准输出是一份 JSON：

```json
{
  "build_id": "本次实际源码和模型对应的构建标识",
  "machine": {"这里由实际加载的状态机 definition() 导出": true},
  "runs": [
    {
      "case": "no_approval",
      "mode": "on",
      "observations": {"state": "waiting_approval", "effects": 0},
      "events": [{"node": "authorize", "phase": "decision"}]
    }
  ]
}
```

以上只展示协议形状。`machine` 必须是完整运行声明，覆盖 states/events/context/guards/transitions 等现有 statechart 契约；不能照抄此示意对象。所有被验收约束引用的用例和配置模式都须实际返回。运行探针支持 build_id 时，从同一加载构建取得；参考程序用 `behavior_model.capture` 只读计算当前构建标识，并在加载前后核对文件。

## 每次变更

1. **修改前 begin**：保存用户请求、旧源码结构、业务图、需求及验收预期。仅把本次确实允许改变的需求 ID 列入 `--requirements`；纯重构可以不列，新需求可先分配新 ID。旧 manifest 或上一已验收输入已经失配时，先查明并保留差异，不用新基线隐藏它。
2. **编码时同步并 inspect**：按小步骤修改真实代码/状态机、探针及抽象映射，重新生成局部结构和候选图。`impact.json` 列变化函数、可能受影响的调用者、业务父节点、未映射符号及错误；`structure.json` 保存确定性证据。更新 review，继续下一个编码小步。
3. **verify**：先检查结构、源绑定、上层声明和必需探针，再运行真实观测及项目测试；比较实际机器定义、业务预期、运行探针及构建标识。运行中又改了输入，结果立即作废。
4. **accept / check**：只有同一候选的检查通过后才能 accept 更新 manifest。交付入口再次 check。之后改源码、图、需求、配置、检查脚本或工具版本，旧验证不再适用。

命令例，工作目录为项目根；将 `SKILL_DIR` 换成实际安装目录：

```text
python SKILL_DIR/scripts/change_sync.py begin --root . --change .stategraph/change-001 --request "本次明确的业务改动" --requirements R4
python build_model.py
python SKILL_DIR/scripts/change_sync.py inspect --root .
python SKILL_DIR/scripts/change_sync.py verify --root .
python SKILL_DIR/scripts/change_sync.py accept --root .
python SKILL_DIR/scripts/change_sync.py check --root .
```

`begin` 保存活动变更指针，后续命令可省略 `--change`。`inspect` 在编辑中返回非零很正常，表示尚未可交付。生成器必须保留业务语义来源，不从静态调用顺序自动发明业务流程或因果关系。

`review.json` 与 baseline/impact 放在同一变更目录。必需结构：当前 `candidate_id`；`decisions.business/state_machine/abstraction/probes` 各有 `action`（updated/unchanged/not_applicable）和具体 `reason`；`excluded_symbols` 为每个未映射变化符号说明为何属于折叠范围及影响；修改已有预期时，以 `requirement_changes` 说明对应的本次需求依据。候选改变后 review 必须重新核对。

review 是语义审阅记录，**不是自动通过证据**。即使全部写 updated，结构、运行状态机、探针、实际返回及效果不一致仍失败。已有预期/关键模型声明的删除或改写必须属于 begin 时记录的需求范围；增加反例可以直接进行。不要把“实现变了”当作改写需求的理由。

## 接入验收入口

把以下命令加入项目已有验证脚本或 CI：

```text
python SKILL_DIR/scripts/change_sync.py check --root .
```

成功返回 0；未同步或检查失败返回非零。首次接入没有历史基线时，明确只能从接入时刻起建立对照，不能宣称此前所有变更已验证。不要安装全局 Git/editor hooks。运行中的旧进程继续绑定旧构建，候选图标明待验证；通过检查并加载新程序后，才把新图与新运行事实关联。

## 能确保什么

已接入并实际执行的检查可以拒绝：缺失源码绑定、陈旧局部投影、上层已约束规则偏离、图与实际状态机声明不同、必需探针缺失/不执行、业务反例结果不符、未经本次需求允许改写旧预期、旧构建或旧检查冒充当前结果。

它不证明所有未覆盖路径、自由文本解释、动态调用或外部系统语义正确，也不是防恶意篡改的签名审计系统。AI/人工仍须维护有代表性的需求约束及独立观测适配器；仅写出一个永远返回成功的测试不能成为可信验收。没有接入检查命令时，只能声称采用了 Skill 的开发流程，不能声称工具已强制拦截。
