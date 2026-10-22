# 源码归属与独立观测模块

先读项目架构。下列是可适配的 Python 布局，文件名不是跨项目强制规定：

| 位置 | 归属 | 依赖方向 |
|---|---|---|
| app/ | 领域函数、事务、存储和业务效果 | 业务及独立状态模块 |
| bo_stategraph/ | 完整执行机制、声明、校验、统一实例和导出 | 中立领域/存储接口及项目选用的执行库 |
| app/ports.py | 应用定义的中立事件接口 | 不依赖图模型和 skill |
| integrations/bo_*.py | 项目维护的接线与适配 | 业务接口 + 观测实现 |
| observer_generated/runtime/ | skill 运行库副本 | 不导入业务实现 |
| observer_generated/runtime/bo_stategraph.py | 原路径兼容入口，不另存实现或实例 | 委托 bo_stategraph 包 |
| observer_generated/behavior.json | 静态结构与业务映射的生成输出 | 从生成器再生 |
| tooling/ | 业务映射源、生成器、检查入口 | 开发时可读各层 |

业务代码即使由 AI 编写，也由项目维护。实际业务执行器可以使用状态机，也可以用普通代码；独立状态网通过声明、适配器和真实证据与两者衔接。两种开发方式都必须维护模型、底层监控、源码同步、图和检查，不能因用户不用状态机指导开发而移除这些内容。具体见 [独立状态网](independent-python.md)。

发布时可按用户明确选择关闭采集或裁剪调试页面；默认保留状态结构与导出模块。旧示例的 `core` 导出专门演示完全剥离观测，不是日常开发或切换方式的默认产物。需要执行的业务状态机留在核心包。若希望连空接口调用都移除，需要构建转换及等效结果验证，不能仅凭目录隔离声称零开销；完全移除观测后也不能声称该包仍有运行监控。

观测专用方法与适配文件使用 `bo_`，自有适配类使用 `BO`；示例入口为 `trace.bo_record(...)`、`events.bo_emit(...)`。业务函数保留领域名称。生成目录放清晰归属说明，记录模板/工具来源；可编辑的界面和业务映射源放项目维护层。核心层通过可选回调依赖倒置；回调失败、关闭、丢事件不参与业务判定。关闭或排除采集范围时应跳过载荷求值。旧端口名只用于兼容；项目的 probe_callees 与白盒检查同步维护，避免改名后丢失验证。

## 配置和命令

参考 [ownership.example.json](../assets/ownership.example.json)。`scan` 显式列检查范围；`layers.paths` 用最长路径匹配归属，`allows` 限制本地静态导入，`external` 可限定核心层允许的外部模块。`reject_dynamic` 拒绝常见动态导入/exec。`managed_paths` 保存生成内容散列，清单本身不能包含在其中。

```text
python SKILL/scripts/architecture_guard.py inventory --root PROJECT
python SKILL/scripts/architecture_guard.py check --root PROJECT
python SKILL/scripts/architecture_guard.py seal --root PROJECT --reason "审阅后的重生成原因"
python SKILL/scripts/architecture_guard.py package --root PROJECT --out dist/core.zip
```

`seal` 是显式记录重生成，不能代替需求/运行验收。把 ownership.json、生成器、适配源、检查脚本和生成物纳入 change_sync watch_files；先记录变更，再重生成和 seal，最后 verify/accept。交付入口同时调用 change_sync check 与 architecture check。

`package` 只打包 `core_include` 明确列出的路径，不覆盖已有 ZIP；`core_layers` 与 `core_resources` 规定允许内容。打包前先运行项目同步门禁；解压到新目录运行核心入口和代表性场景，核对业务状态机/工作网保留、观测目录和导入均不存在。依赖库版本与许可证须保留。

## 范围

检查器只解析 `scan` 下 Python 静态导入，不执行被查代码。别名动态调用、插件注入、外部库内部依赖和未扫描目录仍需单独审阅；不是恶意代码沙盒。纯改名不能证明解耦。调用检查工具本身和清单变更都应受项目验收版本绑定。
