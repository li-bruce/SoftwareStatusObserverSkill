# 失败、修复与复测

1. 解释器路径警告：受限执行时出现 `Failed to find real location of C:\Users\Lvi_P\miniforge3\python.exe`。解释器实际执行与退出码分别保存，未改动仓库解释器。
2. 非有限尺寸的采集缺口：首次 48 场景业务断言无误，但 size_boundaries 的 on 模式有 2 次端口错误；数值白名单拒绝 NaN/Infinity。修复为对提交尺寸使用明确 JSON 文本字段，业务检查仍拒绝非法值；project-test-02.json 首次复测通过。后来扩展到实际参数、活动、资源与效果的独立 SQLite 对照。
3. 注入检查器的来源：内部审阅发现测试覆盖函数被替换时仍绑定默认 check_material 会误报实际实现。修复为自定义回调记到真实 `_check` 调用边界，明确 module/qualname；默认函数仍单独绑定。白盒异常规则同步指向工作器，不修改异常业务预期。
4. 首次 inspect 拒绝缺失 review.json；未 accept 或重建基线。建立逐项分类与内部 review，只有 7 个类容器不作为独立动作，所有函数/方法已绑定。
5. 验证命令退化：verify-01.json 拒绝移除初始 tests/test_policy.py。恢复原测试命令及独立 10 条审批断言，并保留综合测试；verify-02.json 通过。没有修改冻结检查器或基线。
6. 后台可达性：受限 Start-Process / exec 会话报告地址但跨调用 HTTP 超时；记录失败，不当作服务验收。隐藏宿主进程取得 HTTP 200。后续使用用户提供的 with_server.py 在同一次 exec 运行服务器和 Node Playwright，成功启动、交互并关闭。
7. SVG 点击：真实浏览器发现 pointer capture 将点击移到 SVG，节点选择没有发生。修复 pointerup 的选择/双击展开逻辑。之后点击、源码、展开、拖拽通过。
8. 浏览器脚本失败一：对 SVG g 调用 innerText 不适用（browser-report-01.json），改用 textContent；没有更改应用业务行为。
9. 浏览器脚本失败二：记录停止后立即断言，异步保存尚未完成（browser-report-02.json）。修复为等待实际“已保存”状态；browser-report.json 的 20 项通过。
10. 开发工具编辑错误：一次 PowerShell 引号替换未能解析；一次 contracts.py 字典拼接缺括号。均在运行前被语法检查发现并修复，未改变业务数据。最终检查包含编译所有项目 Python 源码。

后续隔离故意错误记录见 mutations.json；它们不是生产修复，也不修改本项目干净源码。保留原验收预期，不用重新 capture 来宣称业务反例通过。
