# Python、Node、React、Vue 共用一张图

这个合成示例演示：任务在有名额时开始，没有名额时等待，恢复后可以完成。Python 服务维护图和记录；原生代码执行任务，React 和 Vue 提供操作界面。

在仓库根目录安装依赖：

```bash
python -m pip install -r skills/vibelens/requirements.txt
python tools/setup_adapters.py
npm ci --prefix examples/multilanguage
```

明确选择一种方式运行：

```bash
python tools/multilanguage_demo.py --mode drive
# 或：python tools/multilanguage_demo.py --mode observe
```

打开 [操作界面](http://127.0.0.1:8850/) 和 [运行图](http://127.0.0.1:8855/graph)。在图中开始记录，再分别开始、完成 React 和 Vue 任务，结束记录后逐步回放。展开节点查看实际参数、函数和源码。Ctrl+C 关闭两个演示进程。

- `drive`：本地执行器读取 `bo_stategraph/project.json` 中的迁移声明。
- `observe`：`src/job.mjs` 使用自己的逻辑；采集与图继续工作。
- `src/` 是业务代码；`integrations/bo_*` 是观测及组装；`bo_stategraph/` 保存声明和原生适配器。
- Python 业务实现 `src/job.py` 由验收脚本真实执行，与 JS 使用相同声明。
- `.stategraph/collector.json` 是本机连接配置，含临时令牌；不提交、不分享。布局保存在 `bo_stategraph/config/views/local.json`。

执行完整跨语言示例验收：

```bash
python tools/verify_multilanguage.py
python tools/test_multilanguage.py
```

覆盖两种开发模式、采集开启/关闭/故障、实际 Python/JS 函数及编译后的 React/Vue 点击处理、源码盘点、参数和事件校验。HTTP 运输、冲突、陈旧绑定和观察自身不产生日志有独立回归。整个仓库仍用 `python tools/verify.py` 执行原有及新增检查。

原生 `bo.fsm/1` 执行器只支持平面状态、事件与同步布尔 guard。复杂状态机需要匹配的原生引擎适配器，不能把本示例当成通用工作流引擎。完整并发、等待、资源及汇合示例见 [team-archive](../team-archive/README.md)。
