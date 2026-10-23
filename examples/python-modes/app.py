"""Application logic. This file has no dependency on the observation module."""


class OwnLogic:
    """An ordinary implementation, with no state-machine library."""
    def __init__(self):
        self.state = "pending"

    def apply(self, event: str, slots: int) -> str:
        if event == "start" and self.state == "pending":
            self.state = "running" if slots > 0 else "waiting"
        elif event == "resume" and self.state == "waiting" and slots > 0:
            self.state = "running"
        elif event == "finish" and self.state == "running":
            self.state = "done"
        else:
            raise ValueError("The current state does not allow this operation")
        return self.state


class Job:
    def __init__(self, logic, bo_notify=None):
        self.logic, self.bo_notify = logic, bo_notify
        self.revision = self.effects = self.slots = 0
        self.bo_errors = 0

    def snapshot(self):
        return {"state": self.logic.state, "revision": self.revision,
                "context": {"slots": self.slots, "effects": self.effects}}

    def run(self, event: str, slots: int = 0):
        if type(slots) is not int or slots < 0:
            raise ValueError("Available slots must be a nonnegative integer")
        self.logic.apply(event, slots)
        self.slots = slots
        if event == "finish": self.effects += 1
        self.revision += 1
        # BO marks observation-only code. A broken observer cannot undo this result.
        if self.bo_notify:
            try: self.bo_notify(self.snapshot(), event, {"available": slots > 0})
            except Exception: self.bo_errors += 1
        return self.snapshot()
