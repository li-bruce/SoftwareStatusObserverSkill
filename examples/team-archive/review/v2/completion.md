# 第二轮完成记录

本轮为 agent 根据模拟用户需求开展的独立开发和浏览器演练；所有资料、审批、账号均为合成数据。这里没有真人用户研究或全部并发调度证明。

动态归档大小上限已完成并验收。每项目共用配置，默认 8192 字节，只计算正文 UTF-8 字节数，等于上限允许；小数、零、负数拒绝，不取整。开始检查、手动继续和最终提交都读取当前项目上限。超限后已启动检查自然结束、未启动检查等待；调大仍需手动继续，同次同版本通过结果复用。上限变化不修改内容版本、不撤销审批，不修改已有归档快照。

最终通过的变更为 `.stategraph/change-004`：

- candidate：`bc2c0f65658e721d78f9404ed2cbf2d0aabf5f55686ec2c745df60965902a530`
- build：`e7e5f89d72093f5d99d37f9bb1f19a8b978a31e4cfecaced8a225b8409b3edc3`
- 模型：`1.1.0`；59 节点 / 124 边；原 55 节点 ID 全部保留。
- 使用的 Skill：只读 business-observer `0.4.0-candidate.8`。未修改其工具脚本。

`change-003` 先实现大小规则，build 为 `01113409f359d41272c4dbb42f670f75624e6d45b4399ebd9d1def7284007aac`。真实页面验证随后发现显示问题，另建 change-004 修复。首个 v2 候选的证据保存在 `initial-01113409/` 及原变更记录，未用新基线抹掉失败。

## 验证结果

| 验证 | 最终结果 |
|---|---|
| 真实业务场景 | 40 场景 × on/off/fault = 120 次执行，通过 |
| 独立业务预期 | 63 条；原有 41 条完整保留，新增 22 条 |
| 模型约束 | 9 条，通过 |
| 白盒 | 6 条规则、11 项实际事件检查，通过 |
| Python 针对性测试 | 13 项，通过，包括旧数据库迁移、配置持久化、UTF-8 边界、冻结源码读取 |
| 图断言 | 历史帧边界、同调用合并、旧配置参数过期、当前/历史上限区分，通过 |
| 新增定向改错 | 4/4 被检出；见下方 |
| 正常交付入口 | `validate.py` 返回 0 |
| 独立核心包 | `-I` 下实际执行通过，未加载 observer_runtime / integrations |
| 完整导出包 | 218 文件；新目录解压后 `validate.py` 返回 0 |
| 实际页面 | 运行中调小、自然结束、恢复后等待、手动继续、快照不变、当前/历史参数、首版源码及布局保留均核验 |

定向改错均在独立核心副本执行，未修改预期：

1. 等值不允许：`size_equal` 等待超时，活动未启动，检出。
2. 按字符数计算：实际 2731 与预期 8193 不符，并错误启动检查，检出。
3. 提交沿用旧资格：错误归档 1 条、仍使用 8192 而非当前 1，检出。
4. 条件恢复自动继续：`no_auto_resume` 不符，检出。

这 4 项在 change-003 核心实现上执行；change-004 只改图展示和相应图断言，核心文件未变。没有将源文件哈希失配当作业务反例被检出。

## 实际失败与修复

- SQLite 连接：旧表迁移测试清理文件时出现 WinError 32。连接上下文只管理事务，未保证及时关闭；初始化、种子、快照读取改为显式 `closing`，测试通过。
- 图的当前上限：初次 v2 完成运行后将上限调为 1，图顶部仍显示最后判断的 8192。提交和存储行为正确，显示来源错误。change-004 改为顶部显示当前项目上限，节点保留历史判断值并提示配置变化；更早历史帧不借用未来值。前后截图分别为 `before-fix-stale-limit-header.png`、`after-fix-current-vs-history.png`。
- 图测试夹具：新增行文本断言首次因夹具缺少描述字段产生 TypeError；补齐夹具描述，业务预期不变。
- 浏览器动态节点有一次点击目标失效；重新观察画布后用节点搜索定位成功，不计为业务规则失败。
- 页面重载曾使旧进程的已中断 HTTP 连接打印 WinError 10053；服务继续可用，最终监听与 HTTP 构建已重新核实。未将它写成归档失败。

原始过程在 `review/round-05/development-notes.md`、`review/round-05/*verify*`、`.stategraph/change-003` 和 `.stategraph/change-004`。模拟需求与问答保留在 `review/round-05/dialogue.md`。

## 图和当前运行

新增 `project_limit`、`set_size_limit`、`size_guard`，并产生一个 `check_size` 静态局部函数节点；`commit_guard` 增加大小资格和关键参数。详见 `node-changes.md` 与 `node-changes.json`。

首版的“本次双检查”、固定标记和备注仍在；同一视野的 `layout-v1-same-view.png` 与 `layout-v2-same-view.png` 展示共享节点位置保留。图上的版本菜单读取冻结 v1 的模型、源码与运行记录，旧源码仍绑定 `6eb25ba0…`。当前运行事实和保存场景绑定最终构建 `e7e5f89d…`。

实际最后一次页面运行 `148fe9a5ee92` 已完成；内容、索引各启动一次，等待恢复后复用内容结果，最终复用同版本已有快照 `e6f02fb1c0d8`。当前共 2 次运行、1 条归档，内容仍为版本 1，项目上限恢复为 8192。前次构建的运行保留为未绑定当前源码的历史记录。权威核对在 `final-audit.json`、`authoritative-final.json`。

当前服务保持运行：

- 操作台：`http://127.0.0.1:8824/`
- 图：`http://127.0.0.1:8824/graph`
- 回环监听 PID 50756，父进程 PID 8792；入口是本 project/run.py，数据库 data/v2.sqlite3，隐藏启动。
- 最终 HTTP `binding=current`，与上方构建相同。完整进程/入口/HTTP 对照在 `runtime-proof.json`。PID 是本次交付时证据，后续可能变化。

截图 `graph-final.png` 展示保存的“检查通过后调小上限 · 提交重新判断”：两项检查通过，最终上限 1 字节，大小判定 false、未归档、仍等待。`application-final.png` 展示实际操作台完成状态。

## 复现命令与导出

从项目或完整导出目录执行，安装 requirements.txt 中依赖并确保 Node 在 PATH：

```powershell
python -X utf8 -B validate.py
python -X utf8 -B run.py --port 8824 --db data/v2.sqlite3 --delay 4
```

8824 已被交付服务占用；核对现有页面无需再启动。需要独立实例时选择其他空闲回环端口和独立数据库。验证命令不会 capture/accept 新基线。

本机没有默认解释器时，已有指定解释器可替代 `python`：

```powershell
$archivePython = 'C:\Users\Lvi_P\Documents\Work\CF\平台软著\SoftwareStatusObserverSkill\.venv\Scripts\python.exe'
& $archivePython -X utf8 -B validate.py
```

本机解释器只用于运行，没有读取其所属项目源码。`sync.json` 使用 `{python}` 和 PATH 上的 node，未写死本机验证命令。

- 完整包：`project-v2.zip`，SHA-256 `9ef626506984baa7567f915f38198ae46ef38ab30621e070ae2088d82bf45d6b`。
- 完整包清单/完整性：`bundle-config.json`、`bundle-integrity.json`。
- 新目录复验：`project-export-validation.json` / `.txt`，目录 `review/v2/project-export`，包含冻结 v1 的必需文件。
- 核心包：`archive-core-v2.zip`；清单/哈希在 `core-package.json`，实际隔离执行在 `core-smoke.json`。
- 首版压缩包保持原 SHA-256：`a9b9b706e1c26b517d67f90780165c5c5c0af62c8493b37dd49e9101a1c4d869`。

完整包不携带实时 SQLite 数据库；实际页面结果通过合成权威快照、运行日志和截图保存。`AGENTS.md` 仍使用本次演练的相邻 Skill 路径，外部仓库便携发布的路径调整及复验由主会话另行记录。本轮没有外部发布。

## 证据范围

图可证明所保存模型、源码绑定及所采集运行事实的对应关系；有限场景不能证明任意动态路径、全部线程交错或生产配置权限。布局保留通过当前浏览器的实际切换和截图核对，没有进行真人可用性研究。原图展开较多节点时仍可能存在文字/边重叠，可折叠或局部搜索查看；没有把这项已知界面限制宣称为消除。
