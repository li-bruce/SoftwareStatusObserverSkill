# Python 独立状态网示例

同一任务用两种方式实现：普通 Python 分支，或读取同一声明配置 `transitions` 引擎。两者都保留状态结构、实际状态查询、源码绑定和完整 JSON 导出。

```text
app.py                  业务逻辑；不导入观测模块
bo_stategraph/          独立模块、完整模型和源码绑定
run.py                  接线和演示入口
build_model.py          维护声明，用 AST 提取局部函数参数
test_modes.py           两种实现的行为与隔离检查
```

在仓库根目录执行（Python 3.11+）：

```bash
python -m pip install -r examples/python-modes/requirements.txt
python examples/python-modes/build_model.py
python examples/python-modes/test_modes.py
python examples/python-modes/run.py --mode observe --out observed-graph.json
python examples/python-modes/run.py --mode drive --out driven-graph.json
```

输出文件不得已存在。两个运行都经过“准备 → 等待名额 → 执行 → 完成”，实际提交次数为 1。输出包含相同状态声明、关系结构和实际实例，只有执行方式不同。可以单独复制本目录运行，无需网页和仓库其他代码。

`drive/observe` 选择的是业务执行方式。Skill 默认仍在 AI 内部依据状态网指导开发；用户明确拒绝该方法时，改为适配用户实现。两种开发方式都必须维护监控、源码同步、状态网和检查，不要求用户操作中间步骤。

`bo_stategraph/__init__.py` 是 Skill 的 `bo_stategraph.py` 原样副本，只有标准库依赖。应用只通过可选 `bo_notify` 提交白名单快照；观测故障不改变业务结果。图的结构始终存在，未采集的状态不会补造。

源码修改后，旧绑定会显示过期。先维护声明、源码映射和独立测试，再生成并验证。此小例的散列检查只防止误用旧绑定，不是完整语义验收；正式项目使用 Skill 的 `change_sync` 与白盒场景。并发、权限和数据库隔离由仓库中的完整示例验证，本例不覆盖。
