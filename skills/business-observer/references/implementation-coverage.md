# 实现覆盖

这份清单回答“程序已经实现的内容，是否在图和采集中有对应”，不代替用户判断业务规则。由编码 AI 维护，用户不用填表。确认原意的对话边界不变；发现代码新增了功能时要如实纳入图，不能把它当作用户已确认的新需求。

## 接入

项目生成器读取 `implementation.json`，写入模型的 `implementation`，并将文件加入 `source_files`。调用 `code_structure.enrich` 后再验证。`source_scope.roots` 包含 `.`，工具代码可以明确排除，业务入口和实现文件不能靠排除理由绕开。

`change_sync inspect/verify` 自动调用 `implementation_coverage.py`。旧项目没有清单时会报错；补齐后通过原有检查再接受，不自动重置基线。既有探针、白盒断言、独立映射和状态约束均继续检查。

```json
{
  "schema": "bo-implementation/v1",
  "features": [{
    "id": "upload", "label": "提交文件", "business_node": "upload",
    "nodes": ["upload"], "sources": ["app/service.py::upload"],
    "parameters": [{
      "source": "app/service.py::upload", "name": "note",
      "node": "upload", "direction": "in", "field": "note", "policy": "value"
    }],
    "cases": [{
      "case": "upload_with_note", "node": "upload", "phase": "commit",
      "values": [{"direction": "in", "field": "note", "path": ["saved", "note"]}]
    }]
  }],
  "support": {
    "app/storage.py::save": {"node": "upload", "reason": "保存提交记录"}
  },
  "excluded": {}
}
```

示例只展示有一个 `note` 参数的函数；实际函数的每个参数均需处置。清单不能从已有图直接照抄：先读独立源码清单，再确定实现归属和功能入口。HTTP 路由、消息读取、后台任务、权限检查、持久化效果都按实际实现检查；未识别的动态分派须记录证据缺口，不能宣称全覆盖。

## 检查的内容

- `features` 列出功能入口的源码身份、业务可见节点、相关采集节点及真实运行场景。代码命名和图的展示名称可以不同。
- `support` 将辅助实现归入一个节点。生成器保留其源码节点和可解析调用；它仍可下钻、搜索，不是删除。辅助函数未被探针执行时只标为静态实现，不能显示为执行成功。
- `excluded` 仅允许可辨认的观测代码或构造方法，并注明原因。普通业务函数不能写成 `utility` 排除；应用路由不能归入排除或辅助实现。
- `parameters` 包含每个功能入口的参数。`value` 直接采集；`derived` 描述实际摘要；`redacted` 描述脱敏表示。后两项需要原因和真实采集字段。仅约定的技术上下文参数可以用 `context`；`note` 等业务参数不能这样跳过。源参数或字段改动后旧清单会失败。
- `cases` 指向实际运行结果的 `case/node/phase`。所有声明采集字段都要在这些场景中出现且符合类型；缺事件、缺字段或其他构建的记录都不能通过。`values` 比较事件与该场景 `observations` 中独立取得的实际值。关键输入、判断和效果应配置此比较或原有白盒/映射断言；不得让两边都读取同一条探针。

清单和运行场景受版本绑定及防弱化检查保护。测试不能通过删除原有字段或场景修好。功能删除、改名或语义变化应按源码迁移及已记录的需求变更处理，不能仅修改清单。

## 任务外的事件

`Trace.record(..., scope="application")` 记录登录、配置等应用级操作；`scope="entity"` 记录同一实体的跨任务操作，默认 `attempt` 仍严格按任务分隔。范围必须由项目明确指定。回放截断仍按实际记录时序，不能给历史帧补入后来的登录或配置事件。

## 验收边界

静态清单证明的是选定 Python 源码中的实现有去向；运行场景证明的是实际执行到的字段与结果。它不自动理解任意动态调用或所有用户意图。检查报告保留静态辅助实现、未解析调用和有限场景的边界；不能把有限测试包装成所有执行路径都已观测。
