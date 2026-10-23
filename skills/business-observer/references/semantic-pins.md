# Capture at semantic boundaries

Install shared runtime with `bo_upgrade.py` and record hashes, including `semantic_probe.py` and `bo_retention.py`. File integration uses `Pins(model, build_id, path=project_root / "data/events.jsonl", project_root=project_root, enabled=True)` and loads `bo_stategraph/config/retention.json`. Supplying only `path` still gives default bounds but never guesses the project root. Invalid configuration raises at construction. Runtime write failure goes to health without changing business results.

`pins.attempt(entity)` creates a Trace. `trace.record(node, phase, basis, builder, depends=..., call_id=..., parent_call_id=...)` executes a builder returning `{inputs,outputs}` in an isolation boundary. The returned event ID is only for observation linkage; business behavior must not depend on it. Custom sinks must use `EventHistory` or their own bounded implementation and verify retention/loss indicators. A bounded queue does not bound the output file.

```python
result = calculate_price(quantity)  # Existing business computation.
observed = trace.record("price", "return", basis,
    lambda: {"inputs": {"quantity": quantity}, "outputs": {"amount": result}},
    depends=[(input_event, "data")])
allowed = result <= current_limit  # Application still owns the decision.
trace.record("limit", "decision", basis,
    lambda: {"inputs": {"amount": result, "limit": current_limit},
             "outputs": {"allowed": allowed}}, depends=[(observed, "data")])
```

Capture actual values at their original read/evaluation point. Record received inputs and returned values; reuse the real guard result rather than recomputing it in the observer. Emit commit only after successful transaction completion and compare effect IDs with the database.

Select fields explicitly. Even a permitted string must not contain a token, full exception, or business body. No automatic locals/repr/SQL capture. Builder errors, schema rejection, overflow, and sink failures increment health and appear as gaps. Builders must be short field copies, never network reads or blocking work.

Compare state, returns, and effects in on/off/fault modes using real values and transaction IDs. Test builder failure, overflow, and sensitive samples. Disabled capture must not call the builder. The commit→enqueue→disk crash window remains; bounded queues do not prove zero overhead or resource-exhaustion immunity.

Possible OpenTelemetry mapping: attempt→trace, call→span, semantic point→event, explicit cross-attempt trigger→link. The reference implementation is local JSONL and does not claim OTel protocol support.
