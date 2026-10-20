# 局部图与共享

## 从同一张图抽取

`focus_graph.py` 是不依赖浏览器、数据库或编码 Skill 的纯提取器。输入使用行为图的稳定节点/边 ID；支持锚点、深度、节点/边预算和关系类型过滤。默认先展开条件、数据、资源与汇合关系。

```text
python <skill>/scripts/focus_graph.py --root . --model observer_generated/behavior.json --nodes authorize --depth 1 --max-nodes 12 --out review/permission.json --markdown review/permission.md
```

输出保留模型版本和内容哈希、原节点/边、源码映射、跨边界关系和缺口。范围外关系保留原端点、方向与类型，不把多跳路径改成直接关系。预算不足明确列出数量和截断；源图没有的依赖无法恢复。Markdown 内的 Mermaid 供对话确认，JSON 供页面或其他工具渲染。

需要运行事实时，用 `--events` 传入实际事件 JSON 数组，并指定 `--run-id` 和 `--build-id`。不同运行或旧版本事件不混入当前视图；不选运行时只展示定义。事件不足只报告缺口，不重新求值授权。

对话展示聚焦的局部图、具体例子和真正未决的问题。用户更改显示名称或布局，保存在个人视图中；改变规则含义则回到需求记录并更新案例。提取器不修改模型、不控制程序。当前参考页面保留持久布局与标注；自动语义补丁、多用户协作和图直接控制仍需另行实现。

## 导出与复现

`project_bundle.py` 使用明确的文件白名单；不递归打包整个工作目录。支持 `project`（代码与复现材料）和 `review`（选定视图与证据）。数据库和密钥文件不进入共享包，使用合成 fixture。

项目中建立 `bundle.json`：

```json
{
  "schema_version": 1,
  "kind": "project",
  "project_id": "my-project",
  "data_policy": "synthetic-only",
  "versions": {"model": "r1", "skill": "0.4.0"},
  "files": ["README.md", "app.py", "requirements.json", "tests.py"],
  "commands": ["python tests.py"]
}
```

```text
python <skill>/scripts/project_bundle.py export --root . --config bundle.json --out dist/project-r1.zip
python <skill>/scripts/project_bundle.py inspect --root . --archive dist/project-r1.zip
```

`inspect` 检查文件范围、长度、哈希与路径，不执行包内命令。synthetic-only 是导出者的声明，工具不能自动识别文本中的所有敏感信息；导出前审阅文件清单和内容。

源码、规则、独立预期和工具版本进入 Git；生成图由声明重建，运行结果绑定构建和数据版本；个人布局与别名独立存储。共享变更时同时提交必要的模型、映射和测试。冲突先解决需求及源码，再生成图；不合并来自不同构建的“通过”记录。旧版本记录保留供回看。
