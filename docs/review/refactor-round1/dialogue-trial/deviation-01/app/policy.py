"""Pure approval predicate; caller supplies facts from its current transaction."""

def grant_matches(grant: dict, run: dict, has_role: bool, now: float) -> dict:
    conditions = {
        "task_ok": grant["task_id"] == run["task_id"],
        "printer_ok": grant["printer_id"] == run["printer_id"],
        "version_ok": grant["version"] == run["version"],
        "other_actor": grant["approver"] != run["submitter"],
        "role_ok": bool(has_role),
        "active_ok": not bool(grant["revoked"]),
        "time_ok": now < grant["expires"],
    }
    return {**conditions, "eligible": all(conditions.values())}
