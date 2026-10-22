# Reviewed starting point

These files bind the published example to a reviewed candidate and its checks.
`tools/demo.py` restores them only for a fresh checkout, then checks the current
source. It does not generate approval for local edits. `tools/verify.py` first
requires that check, then reruns the tests using the same reviewed candidate.

The current local receipt is `assessment-fixes`, covering the six 2026-10-22
assessment findings and strict loading/mapping checks. Previous stages are kept.
See [repair evidence](../../../docs/review/assessment-fixes-20261022/README.md).

The baseline records the reviewed v0.4 source-bound condition probes and verification tools. Raw local test logs,
databases and conversation records are excluded. This is a consistency receipt,
not a signature or a complete proof of program correctness.

当前本地活动记录更新为 `web-continuity`：同一图贯穿对话设计和运行，Web 保持只读；提供入口隐藏、Web 关闭、核心包导出及类型填充。旧检查和业务预期保留；证据见 [本轮材料](../../../docs/review/web-continuity-20261022/README.md)。
