# Reviewed starting point

These files bind the published example to a reviewed candidate and its checks.
`tools/demo.py` restores them only for a fresh checkout, then checks the current
source. It does not generate approval for local edits. `tools/verify.py` first
requires that check, then reruns the tests using the same reviewed candidate.

The baseline records the reviewed Python AST compatibility update after the
initial public packaging work. Raw local test logs,
databases and conversation records are excluded. This is a consistency receipt,
not a signature or a complete proof of program correctness.
