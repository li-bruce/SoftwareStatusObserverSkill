"""Exact, event-bound runtime projections for adapters without activity journals.

The project supplies selected state data from its authoritative transaction or
revision history. This module checks identity; it never reconstructs business
state from event order, the final snapshot, or wall-clock time.
"""

from copy import deepcopy
import json

SCHEMA = "stategraph-runtime-frames/v1"


def merge_frames(recording, view, checkpoint):
    incoming = view.get("runtime_frames")
    if incoming is None:
        return
    retained = recording.setdefault("runtime_frames", {"schema": SCHEMA, "frames": []})
    gaps = recording["gaps"]

    def gap(message):
        if message not in gaps:
            gaps.append(message)

    if (
        not isinstance(incoming, dict)
        or incoming.get("schema") != SCHEMA
        or not isinstance(incoming.get("frames"), list)
    ):
        gap("Invalid runtime snapshot protocol; final state was not used to fill historical steps.")
        return
    if incoming.get("partial") is True:
        retained["partial"] = True
    events = {e["id"]: e for e in recording["events"]}
    frames = {f["event_id"]: f for f in retained["frames"] if f["event_id"] in events}
    for frame in incoming["frames"]:
        if not isinstance(frame, dict):
            gap("Runtime snapshot is missing its event ID.")
            continue
        event = events.get(frame.get("event_id"))
        if event is None:
            continue  # Outside the selected recording boundary.
        revision = event.get("revision")
        if (
            type(revision) is not int
            or type(frame.get("revision")) is not int
            or frame.get("revision") != revision
            or frame.get("run_id") != event.get("run_id")
            or event.get("stream_id", event.get("run_id")) != recording["run_id"]
            or frame.get("build_id") != recording["build_id"]
        ):
            gap(
                "Runtime snapshot and event have different process, build, or revision identities; the step remains missing."
            )
            continue
        try:
            machine = frame["machine"]
            if (
                type(machine.get("state_revision")) is not int
                or machine.get("state_revision") != revision
            ):
                raise ValueError("snapshot revision differs")
            resources = machine.get("shared_resources", {})
            nodes = {node["id"] for node in view["model"]["nodes"]}
            if not isinstance(resources, dict) or any(
                node not in nodes or not isinstance(data, dict) for node, data in resources.items()
            ):
                raise ValueError("shared resources must map graph node IDs to selected values")
            # Reuse the normal selected-field policy; no arbitrary application
            # fields, effects or document bodies are added by this protocol.
            selected = checkpoint({**view, "authority": frame["authority"], "machine": machine})
            clean = {k: deepcopy(frame[k]) for k in ("event_id", "run_id", "build_id", "revision")}
            clean.update(machine=selected["machine"], authority=selected["authority"])
            json.dumps(clean, allow_nan=False)
        except (KeyError, TypeError, ValueError, AttributeError):
            gap("Invalid runtime snapshot content; the step remains missing.")
            continue
        if clean["event_id"] in frames and frames[clean["event_id"]] != clean:
            gap("Conflicting runtime snapshots for one event; the first record was retained.")
            continue
        frames[clean["event_id"]] = clean
    retained["frames"] = [frames[e["id"]] for e in recording["events"] if e["id"] in frames]
