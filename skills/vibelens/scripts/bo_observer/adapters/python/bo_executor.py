"""Native flat-state executor; the observer process is never required."""

from copy import deepcopy

try:
    from .bo_contracts import validate_runtime_definition, value_errors
except ImportError:
    try:
        from ....bo_contracts import validate_runtime_definition, value_errors
    except ImportError:
        from bo_contracts import validate_runtime_definition, value_errors


def bo_list(value):
    return value if isinstance(value, list) else [] if value is None else [value]


class BOExecutor:
    def __init__(self, machine, guards=None):
        """Validate the supported flat-state definition and every supplied guard before use."""
        self.bo_guards = guards or {}
        if machine.get("engine") != "bo.fsm" or machine.get("version") != "1":
            raise ValueError("unsupported native engine/version")
        validate_runtime_definition(
            machine, loaded_engine="bo.fsm", loaded_version="1", guard_names=self.bo_guards
        )
        if any(not callable(f) for f in self.bo_guards.values()):
            raise ValueError("guard implementation must be callable")
        self.bo_definition = deepcopy(machine)

    def step(self, state, event, context, payload=None):
        """Evaluate one declared transition using typed context, payload, and synchronous guards.

        Return the destination and guard evidence. The application remains responsible
        for committing its state and effects.
        """
        m = self.bo_definition
        payload = {} if payload is None else payload
        if state not in m["states"] or event not in m["events"]:
            raise ValueError("unknown state/event")
        if set(context) - set(m["context"]):
            raise ValueError("unknown context field")
        for key, spec in m["context"].items():
            if key not in context:
                raise ValueError("missing context")
            errors = value_errors(context[key], spec, key)
            if errors:
                raise ValueError("; ".join(errors))
        fields = m["events"][event]["payload"]
        if set(payload) != set(fields):
            raise ValueError("event payload fields differ from declaration")
        for key, spec in fields.items():
            errors = value_errors(payload[key], spec, key)
            if errors:
                raise ValueError("; ".join(errors))
        evaluated = {}

        def guard(name):
            if name not in evaluated:
                value = self.bo_guards[name](deepcopy(context), deepcopy(payload))
                if type(value) is not bool:
                    raise ValueError("guard must return boolean synchronously")
                evaluated[name] = value
            return evaluated[name]

        for t in m["transitions"]:
            if t["trigger"] == event and (
                state in bo_list(t["source"]) or "*" in bo_list(t["source"])
            ):
                if all(guard(n) for n in bo_list(t.get("conditions"))) and all(
                    not guard(n) for n in bo_list(t.get("unless"))
                ):
                    return {
                        "state": state if t["dest"] is None else t["dest"],
                        "guards": evaluated,
                        "event": event,
                        "payload": deepcopy(payload),
                    }
        raise ValueError("no enabled transition")
