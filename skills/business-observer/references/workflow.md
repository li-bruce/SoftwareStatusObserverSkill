# Development workflow

Start with [continuous development](continuous-development.md) and [multilanguage integration](multilanguage.md). Confirm current intent and drive/observe choice, maintain declarations, source bindings, and probes while coding, then run the complete gate. Users do not operate the intermediate artifacts.

Source inventory uses `code_structure.py` and `bo_sync.py` with actual language adapters, without executing scanned code. The obsolete `model_tool.py` was removed. Old snapshots cannot substitute for current-build verification.
