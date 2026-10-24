"""Independent Python state model, observed instances and lossless graph export.

Standard library only. No imports from the application, viewer or collector.
The model describes allowed behavior; only application evidence updates instances.
It never executes guards, effects or business commands on behalf of the application.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import threading

try:
    from .bo_contracts import (
        value_errors as bo_value_errors,
        validate_chart,
        state_tree,
        active_states,
        entered_states,
        transition_states,
    )
    from .execution_contract import validate_execution_graph, validate_configuration
except ImportError:
    from bo_contracts import (
        value_errors as bo_value_errors,
        validate_chart,
        state_tree,
        active_states,
        entered_states,
        transition_states,
    )
    from execution_contract import validate_execution_graph, validate_configuration


BO_SCHEMA = "bo-stategraph/v1"
BO_MODES = {"observe", "drive"}


def bo_digest(value):
    """Hash a JSON value deterministically; reject values that JSON cannot represent."""
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    ).hexdigest()


class BOStateGraph:
    """A state machine's structure and observation functions, independent of its driver.

    `drive` means application code consumes bo_definition() to build its executor.
    `observe` means application code implements the behavior itself. Neither mode
    bypasses authorization or makes graph edits execute application commands.
    """

    def __init__(self, model, *, build_id, mode="observe", instance_provider=None):
        """Validate and copy the declaration before accepting any runtime evidence.

        A provider owns live snapshots; otherwise this object stores submitted observations.
        """
        if mode not in BO_MODES:
            raise ValueError("mode must be observe or drive")
        if not isinstance(build_id, str) or not build_id:
            raise ValueError("build_id required")
        if instance_provider is not None and not callable(instance_provider):
            raise ValueError("instance provider must be callable")
        self._model = deepcopy(model)
        self._chart = self._model.get("machine", {})
        self._bo_validate()
        self.build_id, self.mode = build_id, mode
        self._instances = {}
        self._provider = instance_provider
        self._lock = threading.RLock()
        self.bo_rejected = 0

    def bo_bind_instances(self, provider):
        """Bind a consistent authoritative snapshot reader, not another state cache."""
        if not callable(provider):
            raise ValueError("instance provider must be callable")
        with self._lock:
            if self._instances:
                raise ValueError("cannot mix stored observations and a live state provider")
            self._provider = provider

    def _bo_validate(self):
        validate_chart(self._model)
        bo_digest(self._model)

    def bo_definition(self):
        """Return an independent copy for an engine adapter or external consumer."""
        return deepcopy(self._chart)

    def bo_structure(self):
        """Full graph, including collapsed/unselected nodes, types and source bindings."""
        return deepcopy(self._model)

    def bo_check_definition(self, loaded_definition):
        """Compare the loaded executor definition with the declared machine by digest."""
        return {
            "valid": bo_digest(loaded_definition) == bo_digest(self._chart),
            "expected": bo_digest(self._chart),
            "loaded": bo_digest(loaded_definition),
        }

    def bo_require_definition(self, loaded_definition):
        """Startup gate: invalid/drifted executor declarations raise before use."""
        validate_chart(self._model, loaded_definition)
        return self.bo_check_definition(loaded_definition)

    def bo_candidates(self, state, event, *, guards=None, payload=None):
        """Inspect declared transitions. Unknown guards remain unknown, not allowed.

        `matched` reports supplied Boolean facts only; it is not permission to act.
        This method does not query a database, call a guard or change any state.
        """
        active = active_states(self._chart, state)
        if event not in self._chart["events"]:
            raise ValueError("unknown event")
        guards, payload = guards or {}, payload or {}
        errors = []
        for key, spec in self._chart["events"][event].get("payload", {}).items():
            if key not in payload:
                errors.append("payload." + key + ": missing")
            else:
                errors += bo_value_errors(payload[key], spec, "payload." + key)
        candidates = []
        for transition in self._chart["transitions"]:
            sources = transition["source"]
            sources = sources if isinstance(sources, list) else [sources]
            if transition["trigger"] != event or not (
                active.intersection(sources) or "*" in sources
            ):
                continue
            missing, rejected = [], []
            for field, expected in (("conditions", True), ("unless", False)):
                names = transition.get(field, [])
                names = names if isinstance(names, list) else [names]
                for name in names:
                    if type(guards.get(name)) is not bool:
                        missing.append(name)
                    elif guards[name] != expected:
                        rejected.append(name)
            result = "rejected" if errors or rejected else "unknown" if missing else "matched"
            candidates.append(
                {
                    "transition": deepcopy(transition),
                    "result": result,
                    "missing_guards": missing,
                    "rejected_guards": rejected,
                }
            )
        # Child handlers take priority; a false guard allows fallback to the
        # ancestor, whereas missing guard evidence cannot prove that fallback.
        _, parents = state_tree(self._chart)

        def source_nodes(candidate):
            source = candidate["transition"]["source"]
            sources = set(source if isinstance(source, list) else [source])
            # transitions expands '*' to the states registered at this scope.
            # At the root this means top-level states, including HSM parents.
            if "*" in sources:
                sources = {s for s, parent in parents.items() if parent is None}
            return sources & active

        def ancestor(a, b):
            while b is not None:
                if b == a:
                    return True
                b = parents.get(b)
            return False

        for index, candidate in enumerate(candidates):
            blockers = [
                other
                for j, other in enumerate(candidates)
                if j != index
                and other["result"] in ("matched", "unknown")
                and any(
                    (a != b and ancestor(a, b)) or (a == b and j < index)
                    for a in source_nodes(candidate)
                    for b in source_nodes(other)
                )
            ]
            if blockers and candidate["result"] == "matched":
                candidate["result"] = (
                    "shadowed" if any(b["result"] == "matched" for b in blockers) else "unknown"
                )
        return {"candidates": candidates, "errors": errors, "authorizes_execution": False}

    def bo_observe(
        self,
        instance_id,
        *,
        state,
        context,
        revision,
        evidence_id,
        build_id,
        configuration=None,
        event=None,
        guards=None,
        payload=None,
    ):
        """Attach a complete actual snapshot after an application semantic boundary.

        Revisions are supplied by the application, per instance. They must cover
        all observed changes, not just a subset such as activity updates. Invalid
        states are retained as evidence with errors. Wrong builds and older or
        conflicting revisions cannot overwrite the current instance.
        """
        with self._lock:
            if self._provider is not None:
                raise ValueError("instances are owned by the bound state provider")
            if (
                not isinstance(instance_id, str)
                or not instance_id
                or not evidence_id
                or type(revision) is not int
                or revision < 0
                or not isinstance(context, dict)
            ):
                self.bo_rejected += 1
                return {"accepted": False, "errors": ["invalid instance/evidence/revision/context"]}
            if build_id != self.build_id:
                self.bo_rejected += 1
                return {"accepted": False, "errors": ["different loaded build"]}
            observed = {
                "instance_id": instance_id,
                "state": state,
                "context": deepcopy(context),
                "configuration": deepcopy(configuration),
                "revision": revision,
                "evidence_id": evidence_id,
                "build_id": build_id,
                "event": event,
                "guards": deepcopy(guards),
                "payload": deepcopy(payload),
            }
            previous = self._instances.get(instance_id)
            if previous and revision <= previous["observed"]["revision"]:
                same = observed == previous["observed"]
                if not same:
                    self.bo_rejected += 1
                return {
                    "accepted": same,
                    "duplicate": same,
                    "errors": [] if same else ["old or conflicting revision"],
                }
            errors, missing = [], []
            try:
                active = active_states(self._chart, state)
            except (ValueError, TypeError) as exc:
                active = set()
                errors.append(str(exc))
            for key, spec in self._chart["context"].items():
                if key not in context:
                    missing.append("context." + key)
                else:
                    errors += bo_value_errors(context[key], spec, "context." + key)
            if self._chart.get("execution") and configuration is None:
                missing.append("execution configuration")
            if self._chart.get("execution") and configuration is not None:
                try:
                    validate_configuration(self._model, configuration)
                except (ValueError, KeyError, TypeError) as exc:
                    errors.append("execution: " + str(exc))
            transition = None
            if previous:
                old = previous["observed"]
                if revision != old["revision"] + 1:
                    missing.append("intermediate revisions")
                if event:
                    try:
                        transition = self.bo_candidates(
                            old["state"], event, guards=guards, payload=payload
                        )
                        errors += transition["errors"]
                        viable = [
                            c
                            for c in transition["candidates"]
                            if c["result"] in ("matched", "unknown")
                        ]
                        known = [c["transition"] for c in viable if c["result"] == "matched"]
                        if any(c["result"] == "unknown" for c in viable):
                            missing.append("guard evidence")
                        elif (
                            not known
                            or transition_states(self._chart, old["state"], known) != active
                        ):
                            errors.append("actual transition differs from declaration")
                    except ValueError as exc:
                        errors.append(str(exc))
                elif old["state"] != state:
                    missing.append("transition event")
            elif event:
                missing.append("previous state")
            entry = {
                "observed": observed,
                "errors": errors,
                "missing": missing,
                "status": "mismatch" if errors else "partial" if missing else "observed",
                "transition_check": transition,
            }
            bo_digest(entry)
            self._instances[instance_id] = entry
            return {"accepted": True, **deepcopy(entry)}

    def bo_instances(self, machine=None):
        """Read all actual instances through the same projection used by the viewer.

        Existing data without a complete-state revision retains separate component
        revisions. A projection never invents transitions or a global sequence.
        """
        # Never invoke application code under our lock: providers can acquire a
        # service lock while a concurrent recording already owns that lock.
        if machine is None:
            with self._lock:
                provider = self._provider
            if provider is not None:
                machine = provider()
                with self._lock:
                    if provider is not self._provider:
                        raise ValueError("instance provider changed during snapshot read")
        with self._lock:
            if machine is not None:
                result = []
                identities = set()
                for configuration in machine.get("configurations", []):
                    cfg = deepcopy(configuration)
                    ident = cfg.get("attempt")
                    if not ident or ident in identities:
                        raise ValueError("missing or duplicate execution instance")
                    identities.add(ident)
                    errors, missing = [], []
                    state = cfg.get("phase")
                    try:
                        active = sorted(active_states(self._chart, state))
                    except (ValueError, TypeError) as exc:
                        active = []
                        errors.append(str(exc))
                    if self._chart.get("execution"):
                        try:
                            validate_configuration(self._model, cfg)
                        except (ValueError, TypeError, KeyError) as exc:
                            errors.append(str(exc))
                    revision = cfg.get("state_revision")
                    if revision is None:
                        missing.append("complete state revision unavailable in legacy record")
                    elif type(revision) is not int or revision < 0:
                        errors.append("invalid complete state revision")
                    context = cfg.get("context", {})
                    for key, spec in self._chart["context"].items():
                        if key not in context:
                            missing.append("context." + key)
                        else:
                            errors += bo_value_errors(context[key], spec, "context." + key)
                    if not cfg.get("run_build_id"):
                        missing.append("loaded build unavailable")
                    elif cfg["run_build_id"] != self.build_id:
                        missing.append("execution belongs to another build")
                    if cfg.get("source_status") not in (None, "current"):
                        missing.append("source status: " + str(cfg["source_status"]))
                    result.append(
                        {
                            "observed": {
                                "instance_id": ident,
                                "state": state,
                                "active_states": active,
                                "context": deepcopy(cfg.get("context", {})),
                                "configuration": cfg,
                                "revision": revision,
                                "component_revisions": {"activity": cfg.get("revision")},
                                "build_id": cfg.get("run_build_id"),
                                "evidence_id": "state:" + ident,
                                "snapshot_sha256": bo_digest(cfg),
                            },
                            "errors": errors,
                            "missing": missing,
                            "status": (
                                "mismatch" if errors else "partial" if missing else "observed"
                            ),
                            "transition_check": None,
                        }
                    )
                return result
            return deepcopy(list(self._instances.values()))

    def bo_export(self, *, runtime=None, binding=None):
        """Export full declared structure and supplied evidence, with no view filters.

        Runtime must already be allowlisted by the adapter. Raw application objects
        and arbitrary database contents must not be passed to this method.
        """
        instances = self.bo_instances(
            runtime.get("machine") if runtime is not None and "machine" in runtime else None
        )
        with self._lock:
            value = {
                "schema": BO_SCHEMA,
                "execution_mode": self.mode,
                "build_id": self.build_id,
                "definition_sha256": bo_digest(self._chart),
                "model": self.bo_structure(),
                "instances": instances,
                "binding": deepcopy(binding or {"status": "not_checked"}),
                "runtime": deepcopy(runtime) if runtime is not None else None,
                "coverage": {
                    "structure": "full_declared_graph",
                    "runtime": (
                        "adapter_supplied_evidence"
                        if runtime is not None or instances
                        else "not_observed"
                    ),
                    "unknowns": deepcopy(self._model.get("scope", {}).get("unknowns", [])),
                    "rejected_observations": self.bo_rejected,
                },
            }
            value["sha256"] = bo_digest(value)
            return value


def bo_export_view(view, *, mode="observe", graph=None):
    """Export the existing viewer protocol without making the view authoritative.

    Keeps all instance configurations, event identities/dependencies and source
    status exactly as supplied, including evidence from a different build. No
    inferred events or attempt IDs are added. The caller takes a consistent read.
    """
    if graph is None:
        graph = BOStateGraph(view["model"], build_id=view["manifest"]["build_id"], mode=mode)
    elif graph.build_id != view["manifest"]["build_id"] or graph.bo_structure() != view["model"]:
        raise ValueError("export view differs from loaded graph")
    keys = ("manifest", "authority", "machine", "events", "health", "historical", "runtime_frames")
    return graph.bo_export(
        runtime={k: view[k] for k in keys if k in view}, binding=view.get("binding_status")
    )


def bo_validate_export(value):
    """Validate the public protocol, including instances derived from one snapshot."""
    if value.get("schema") != BO_SCHEMA:
        raise ValueError("unknown export schema")
    unsigned = {k: v for k, v in value.items() if k != "sha256"}
    if value.get("sha256") != bo_digest(unsigned):
        raise ValueError("export digest mismatch")
    graph = BOStateGraph(value["model"], build_id=value["build_id"], mode=value["execution_mode"])
    if value["definition_sha256"] != bo_digest(graph.bo_definition()):
        raise ValueError("definition mismatch")
    if not isinstance(value.get("instances"), list):
        raise ValueError("export instances must be a list")
    runtime = value.get("runtime")
    if runtime is not None and "runtime_frames" in runtime:
        frames = runtime["runtime_frames"]
        if (
            not isinstance(frames, dict)
            or frames.get("schema") != "stategraph-runtime-frames/v1"
            or not isinstance(frames.get("frames"), list)
        ):
            raise ValueError("invalid exact runtime frame protocol")
        events = {e["id"]: e for e in runtime.get("events", [])}
        seen = set()
        for frame in frames["frames"]:
            if not isinstance(frame, dict) or any(
                not isinstance(frame.get(k), str) or not frame[k]
                for k in ("event_id", "run_id", "build_id")
            ):
                raise ValueError("runtime frame needs nonempty event/run/build identities")
            if not isinstance(frame.get("machine"), dict):
                raise ValueError("runtime frame needs a machine snapshot")
            event = events.get(frame.get("event_id"))
            if event is None or frame["event_id"] in seen:
                raise ValueError("runtime frame needs a unique exported event")
            seen.add(frame["event_id"])
            if (
                type(frame.get("revision")) is not int
                or type(event.get("revision")) is not int
                or frame["revision"] < 0
                or type(frame.get("machine", {}).get("state_revision")) is not int
                or any(frame.get(k) != event.get(k) for k in ("revision", "run_id", "build_id"))
                or frame.get("machine", {}).get("state_revision") != frame["revision"]
            ):
                raise ValueError("runtime frame differs from its event identity/revision")
            if not isinstance(frame.get("authority"), dict):
                raise ValueError("runtime frame needs selected authority")
    if runtime is not None and "machine" in runtime:
        if value["instances"] != graph.bo_instances(runtime["machine"]):
            raise ValueError("export instances differ from the supplied runtime snapshot")
    return value


def bo_read_export(path):
    return bo_validate_export(json.loads(Path(path).read_text(encoding="utf-8-sig")))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    export = sub.add_parser("export", help="Export model only, or a saved full /api/view response")
    source = export.add_mutually_exclusive_group(required=True)
    source.add_argument("--model")
    source.add_argument("--view")
    export.add_argument("--build-id")
    export.add_argument("--mode", choices=sorted(BO_MODES), default="observe")
    export.add_argument("--out", required=True)
    check = sub.add_parser("check")
    check.add_argument("path")
    args = parser.parse_args()
    if args.command == "check":
        value = bo_read_export(args.path)
        print(
            json.dumps(
                {
                    "valid": True,
                    "nodes": len(value["model"]["nodes"]),
                    "edges": len(value["model"]["edges"]),
                }
            )
        )
        return
    if args.view:
        value = bo_export_view(
            json.loads(Path(args.view).read_text(encoding="utf-8-sig")), mode=args.mode
        )
    else:
        if not args.build_id:
            parser.error("--model requires --build-id (use unbound if no build is loaded)")
        graph = BOStateGraph(
            json.loads(Path(args.model).read_text(encoding="utf-8-sig")),
            build_id=args.build_id,
            mode=args.mode,
        )
        value = graph.bo_export()
    with Path(args.out).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"path": args.out, "sha256": value["sha256"]}))


if __name__ == "__main__":
    main()
