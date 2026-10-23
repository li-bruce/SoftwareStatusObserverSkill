/**
 * A small, deterministic application used only by the product walkthrough.
 * Events contain actual changes to this local sample, not recordings from a project.
 */
export class DemoSession {
  constructor() {
    this.reset();
  }

  /** Reset the sample and its recording; view controls are owned by the page. */
  reset() {
    this.current = { state: "empty", visible: false, notified: false };
    this.events = [];
    this.captured = [];
    this.recording = false;
    this.scope = "all";
    this.iterated = false;
    this.sequence = 0;
  }

  /** Freeze capture scope until stop; controls themselves produce no business events. */
  start(scope = "all") {
    if (this.recording) return false;
    if (!["all", "review"].includes(scope)) throw Error("Unknown capture scope");
    this.scope = scope;
    this.captured = [];
    this.recording = true;
    return true;
  }

  stop() {
    this.recording = false;
    return this.captured.map((event) => structuredClone(event));
  }

  /** Capture the sample's before/after values at an operation boundary. */
  emit(node, operation, values) {
    const before = structuredClone(this.current);
    this.current = { ...this.current, ...values };
    const event = {
      id: ++this.sequence,
      node,
      operation,
      before,
      after: structuredClone(this.current),
    };
    this.events.push(event);
    if (this.recording && (this.scope === "all" || node === "review")) {
      this.captured.push(structuredClone(event));
    }
    return event;
  }

  /** Execute only an operation allowed by the current sample state. */
  operate(operation) {
    if (operation === "upload") {
      if (this.current.state !== "empty" && !(this.iterated && this.current.state === "returned"))
        return false;
      this.emit("upload", "upload", { state: "uploaded", notified: false });
      this.emit("check", "validate", { state: "pending" });
      this.emit("notify", "notify", { notified: true });
      return true;
    }
    if (this.current.state !== "pending") return false;
    if (operation === "approve") {
      this.emit("review", "approve", { state: "displayed", visible: true });
      return true;
    }
    if (operation === "return" && this.iterated) {
      this.emit("review", "return", { state: "returned", visible: false });
      return true;
    }
    return false;
  }

  /** Add the user's illustrated iteration without silently resetting existing evidence. */
  addReturnPath() {
    this.iterated = true;
  }

  /** Start another sample operation while keeping the requested flow revision. */
  restartOperation() {
    const iterated = this.iterated;
    this.reset();
    this.iterated = iterated;
  }

  /** Read captured facts at a replay position; never mutate the sample application. */
  frame(index) {
    if (!Number.isInteger(index) || index < 0 || index >= this.captured.length) return null;
    return structuredClone(this.captured[index]);
  }
}
