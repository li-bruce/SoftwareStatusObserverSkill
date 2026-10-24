# Explicit probe integration

Copy `scripts/probe.py` into the project or import it from a fixed path; no pip package is required. The application owns business behavior and transactions. Probes accept only explicitly selected safe fields.

```python
from probe import Probe
probe = Probe(path="events.jsonl", build_id=build_id, model_revision="1",
              fields={"fact": {"value", "source", "version", "quality"}},
              nodes={"stock"})
# After successful business commit. Payload construction is isolated too.
probe.capture(lambda: [{"kind": "fact", "node_id": "stock", "entity_id": "item-1",
    "request_id": "request-1", "attempt_id": "attempt-1", "tx_id": "tx-1",
    "payload": {"value": 3, "source": "sqlite:items.stock", "version": 4,
                "quality": "committed"}}])
# Flush during orderly shutdown or testing, not on the hot business path.
probe.flush(timeout=2)
probe.close()
```

Set `enabled=False` to disable. Inject faults with a throwing sink; test overflow with a small `queue_size` and controlled blocked sink. Read `probe.health()`. A flush timeout means capture is incomplete; queued events are not written events.

An allowlist cannot prevent intentionally placing secrets into an allowed value. Review field meaning and injected samples. Never capture arbitrary repr, complete exceptions, or SQL parameters. Strings/lists have limits, nested dictionaries are rejected, and oversized events are dropped and counted.

Delivery follows commit, so a crash between commit and enqueue can lose events. This is observation, not an audit outbox: no exactly-once, cross-process ordering, or crash-recovery guarantee. Compare effects against authoritative business storage. A queue avoids sink I/O blocking, but CPU/memory exhaustion, a misplaced probe, or blocking payload construction can still interfere; do not claim zero impact.
