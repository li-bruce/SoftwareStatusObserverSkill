# Software Status Observer Skill

[English](README.en.md) · [安装与使用](docs/usage.zh-CN.md) · [运行示例](examples/delivery/README.md)

**在 Vibe Coding 中，帮助开发者看懂和调试 AI 生成的程序。**

`business-observer` 让 AI 在开发时同步维护业务逻辑、关键代码关系和真实状态机；程序运行后，用分层图展示核心函数、参数、判断条件和执行状态。

## 可以看到什么

- 从业务节点展开到内部活动、关键函数，再查看对应源码。
- 直接在节点和边上查看参数类型、实际值、执行结果及等待原因。
- 查看并行活动、可用名额和汇合条件，定位是哪一步阻止流程继续。
- 按运行和参数版本回看状态，区分当前事实、旧记录和缺失信息。

Skill 会主动询问影响权限、状态和执行结果的模糊需求。修改代码时，检查图、状态机、探针和测试是否同步。上层结构来自需求理解，局部程序关系来自 Python AST，运行状态来自实际执行。

## 安装 Skill

在支持 `$skill-installer` 的 Codex 对话中输入：

```text
使用 $skill-installer，从以下地址安装 business-observer：
https://github.com/li-bruce/SoftwareStatusObserverSkill/tree/v0.1.0/skills/business-observer
```

也可以克隆仓库后安装到指定项目：

```bash
git clone https://github.com/li-bruce/SoftwareStatusObserverSkill.git
cd SoftwareStatusObserverSkill
python tools/install_skill.py --project /path/to/your-project
```

安装脚本将完整 Skill 复制到目标项目的 `.agents/skills/business-observer`，遇到已有目录会停止。打开该项目的新对话后使用：

```text
使用 $business-observer 开发这个功能：……
先梳理业务链和状态，询问会影响执行结果的未明确规则。
编码时同步维护分层图、关键函数和参数、真实状态机及探针。
交付前检查同步情况，并用实际运行解释成功、等待和失败路径。
```

## 运行示例

需要 Python 3.11–3.13、Node.js 20+ 和支持 WebGL 的现代浏览器。Node.js 仅用于图测试。

```bash
python -m venv .venv
```

激活虚拟环境：Windows PowerShell 使用 `.venv\Scripts\Activate.ps1`；macOS/Linux 使用 `source .venv/bin/activate`。

```bash
python -m pip install -r examples/delivery/requirements.txt
python tools/demo.py
```

打开 [运行图](http://127.0.0.1:8797/) 和 [操作页](http://127.0.0.1:8797/control)。批准当前版本，点击“检查并提交”，在图中展开“检查内容”。将并发名额改为 1，可看到一项执行、另一项等待。两项检查通过后，程序重新检查授权和版本，再保存交付物。

示例使用合成文本和本地 SQLite。图约每 400 ms 更新；检查刻意放慢以方便观察。完整操作见[示例说明](examples/delivery/README.md)。

## 项目内容

| 目录 | 内容 |
|---|---|
| `skills/business-observer/` | Skill 提示、检查脚本、探针和图模板 |
| `examples/delivery/app/` | 示例自己的状态机、并发活动和业务代码 |
| `examples/delivery/integrations/` | 可选观测接入和页面源文件 |
| `examples/delivery/observer_generated/` | 生成的图、页面和运行库副本 |
| `tests/`、`tools/` | 安装、发布检查和回归测试 |

## 验证与边界

```bash
python tools/verify.py
```

检查包括需求澄清、权限和版本反例、并发与资源等待、旧新运行隔离、图回看、观测开启/关闭/故障时的结果一致性，以及剔除观测层后的核心包运行。修改记录与验收流程见[使用说明](docs/usage.zh-CN.md)。

首版提供 Python 参考实现，Skill 和示例界面以中文为主。其他语言需要对应的静态分析和运行适配。图覆盖明确选取的业务路径与内部活动；不会采集全部函数局部变量。检查通过不等于证明整个软件或权限系统正确。

当前图支持查看和下钻；执行仍通过示例操作页。图上修改节点并控制程序尚未实现。示例用于本地开发，不提供生产部署、用户认证或崩溃后工作线程恢复。

## 许可证

[MIT](LICENSE)。依赖与来源见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
