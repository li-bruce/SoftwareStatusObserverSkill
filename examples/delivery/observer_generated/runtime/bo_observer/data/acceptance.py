"""Keep data-capture obligations protected across a reviewed coding change."""


def protected_errors(previous, current, requested=(), reasons=None):
    """A removed case/value or changed outcome needs its recorded requirement change."""
    if not previous:
        return []
    active = {item["id"]: item for item in (current or {}).get("operations", [])}
    errors = []
    reasons = reasons or {}

    def retained(old, new):
        if isinstance(old, dict):
            return isinstance(new, dict) and all(
                key in new and retained(value, new[key]) for key, value in old.items()
            )
        if isinstance(old, list):
            return (
                isinstance(new, list)
                and len(old) == len(new)
                and all(retained(a, b) for a, b in zip(old, new))
            )
        return old == new

    for old in previous["operations"]:
        new = active.get(old["id"])
        changed = new is None or any(
            not retained(old.get(key, {}), new.get(key, {}))
            for key in ("parameters", "before", "after")
        )
        if new is not None:
            changed |= not set(old["required_cases"]) <= set(new["required_cases"])
            changed |= bool(
                (set(new.get("failure_cases", [])) - set(old.get("failure_cases", [])))
                & set(old["required_cases"])
            )
        requirements = old.get("requirements", [])
        approved = bool(requirements) and all(
            r in requested and isinstance(reasons.get(r), str) and reasons[r].strip()
            for r in requirements
        )
        if changed and not approved:
            errors.append(
                {
                    "weakened_database_capture": old["id"],
                    "required_action": "Preserve required cases and selected values, or record the linked requirement change.",
                }
            )
    return errors
