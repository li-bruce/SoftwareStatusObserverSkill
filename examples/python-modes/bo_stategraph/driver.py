"""State-machine executor kept outside the application business code."""
from copy import deepcopy

class MachineLogic:
    """Use the declared graph to configure the existing transitions engine."""
    def __init__(self, definition: dict):
        from transitions import Machine
        self.slots = 0
        self.state = definition["initial"]
        self.machine = Machine(self, states=definition["states"], initial=self.state,
            transitions=deepcopy(definition["transitions"]), auto_transitions=False)

    def available(self):
        return self.slots > 0

    def apply(self, event: str, slots: int) -> str:
        self.slots = slots
        if not self.trigger(event):
            raise ValueError("当前状态不能执行这个操作")
        return self.state


