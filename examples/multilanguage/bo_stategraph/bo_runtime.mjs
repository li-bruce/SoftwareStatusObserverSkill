// Native application adapter. No Python imports or observer-dependent decisions.
// Only the declared flat bo.fsm/1 subset executes here; other engines need adapters.
/** Reject unsupported machine semantics and missing guards before an executor is created. */
export function bo_validateMachine(machine, guards = {}) {
  if (machine.engine !== "bo.fsm" || machine.version !== "1")
    throw Error("Unsupported native machine engine/version");
  if (machine.execution || machine.states.some((s) => typeof s !== "string"))
    throw Error("bo.fsm/1 is flat; hierarchy/activity needs an explicit engine adapter");
  const allowed = new Set([
    "engine",
    "version",
    "states",
    "values",
    "initial",
    "state_type",
    "transitions",
    "events",
    "context",
    "guards",
    "labels",
  ]);
  if (Object.keys(machine).some((k) => !allowed.has(k)))
    throw Error("Unsupported machine semantics");
  if (
    !machine.states.length ||
    machine.states.some((s) => !s.trim()) ||
    new Set(machine.states).size !== machine.states.length ||
    !machine.states.includes(machine.initial)
  )
    throw Error("Invalid initial/states");
  if (
    machine.state_type !== "enum" ||
    machine.values?.length !== machine.states.length ||
    new Set(machine.values).size !== machine.values.length ||
    machine.values.some((s) => !machine.states.includes(s))
  )
    throw Error("Invalid state values");
  if (
    ["context", "events", "guards"].some(
      (k) => machine[k] === null || typeof machine[k] !== "object" || Array.isArray(machine[k]),
    )
  )
    throw Error("Expected context, events and guards objects");
  const names = Object.keys(machine.guards || {});
  if (names.some((n) => !Object.hasOwn(guards, n) || typeof guards[n] !== "function"))
    throw Error("Missing guard implementation");
  for (const t of machine.transitions) {
    if (
      Object.keys(t).some((k) => !["source", "dest", "trigger", "conditions", "unless"].includes(k))
    )
      throw Error("Unsupported transition semantics");
    const sources = Array.isArray(t.source) ? t.source : [t.source];
    if (
      !sources.length ||
      sources.some((s) => s !== "*" && !machine.states.includes(s)) ||
      (t.dest !== null && !machine.states.includes(t.dest)) ||
      !Object.hasOwn(machine.events, t.trigger)
    )
      throw Error("Dangling transition");
    for (const key of ["conditions", "unless"])
      for (const guard of bo_list(t[key]))
        if (!names.includes(guard)) throw Error("Undeclared guard");
  }
  for (const spec of Object.values(machine.context || {})) bo_spec(spec);
  for (const event of Object.values(machine.events || {})) {
    if (!event?.payload || typeof event.payload !== "object") throw Error("Event payload required");
    for (const spec of Object.values(event.payload)) bo_spec(spec);
  }
}
const bo_list = (v) => (v === undefined ? [] : Array.isArray(v) ? v : [v]);
function bo_spec(spec) {
  if (!["integer", "number", "boolean", "string", "enum", "object", "array"].includes(spec?.type))
    throw Error("Unknown value type");
  if (spec.type === "enum" && (!Array.isArray(spec.values) || !spec.values.length))
    throw Error("Enum requires values");
  if (
    (spec.min !== undefined && !Number.isFinite(spec.min)) ||
    (spec.max !== undefined && !Number.isFinite(spec.max)) ||
    spec.min > spec.max
  )
    throw Error("Invalid value bounds");
  if (spec.items) bo_spec(spec.items);
  for (const child of Object.values(spec.properties || {})) bo_spec(child);
}
/** Validate a context or payload value recursively against the declared JSON type. */
export function bo_value(value, spec) {
  bo_spec(spec);
  const type = spec.type;
  const valid = {
    integer: Number.isSafeInteger(value),
    number: typeof value === "number" && Number.isFinite(value),
    boolean: typeof value === "boolean",
    string: typeof value === "string",
    enum: spec.values?.some(
      (v) => typeof v === typeof value && JSON.stringify(v) === JSON.stringify(value),
    ),
    object: value !== null && typeof value === "object" && !Array.isArray(value),
    array: Array.isArray(value),
  }[type];
  if (!valid) throw Error(`Expected ${type}`);
  if (
    ["integer", "number"].includes(type) &&
    ((spec.min !== undefined && value < spec.min) || (spec.max !== undefined && value > spec.max))
  )
    throw Error("Value outside bounds");
  if (type === "array" && spec.items) for (const v of value) bo_value(v, spec.items);
  if (type === "object") {
    for (const k of spec.required || [])
      if (!Object.hasOwn(value, k)) throw Error("Missing property");
    for (const [k, s] of Object.entries(spec.properties || {}))
      if (Object.hasOwn(value, k)) bo_value(value[k], s);
  }
}
export class BOExecutor {
  constructor(machine, guards = {}) {
    bo_validateMachine(machine, guards);
    this.bo_definition = structuredClone(machine);
    this.bo_guards = guards;
  }
  /** Return one destination and its guard results; the application commits the effects. */
  step(state, event, context, payload = {}) {
    const m = this.bo_definition;
    if (!m.states.includes(state) || !Object.hasOwn(m.events, event))
      throw Error("Unknown state/event");
    if (Object.keys(context).some((k) => !Object.hasOwn(m.context, k)))
      throw Error("Unknown context field");
    for (const [k, s] of Object.entries(m.context)) {
      if (!Object.hasOwn(context, k)) throw Error("Missing context");
      bo_value(context[k], s);
    }
    const fields = m.events[event].payload;
    if (Object.keys(payload).some((k) => !Object.hasOwn(fields, k)))
      throw Error("Unknown payload field");
    for (const [k, s] of Object.entries(fields)) {
      if (!Object.hasOwn(payload, k)) throw Error("Missing payload");
      bo_value(payload[k], s);
    }
    const evaluated = {};
    const guard = (name) => {
      if (!Object.hasOwn(evaluated, name)) {
        const v = this.bo_guards[name](structuredClone(context), structuredClone(payload));
        if (typeof v !== "boolean") throw Error("Guard must return boolean synchronously");
        evaluated[name] = v;
      }
      return evaluated[name];
    };
    for (const t of m.transitions)
      if (
        t.trigger === event &&
        (bo_list(t.source).includes(state) || bo_list(t.source).includes("*"))
      ) {
        if (bo_list(t.conditions).every(guard) && bo_list(t.unless).every((n) => !guard(n)))
          return {
            state: t.dest ?? state,
            guards: evaluated,
            event,
            payload: structuredClone(payload),
          };
      }
    throw Error("No enabled transition");
  }
}

/** Copy declared capture fields only, with bounded values and JSON-safe numbers. */
function bo_selected(value, spec, depth = 0) {
  if (depth > 6) throw Error("Capture depth exceeded");
  if (Array.isArray(spec)) {
    if (!Array.isArray(value) || spec.length !== 1 || value.length > 64)
      throw Error("Bounded array required");
    return value.map((v) => bo_selected(v, spec[0], depth + 1));
  }
  if (spec && typeof spec === "object") {
    if (value === null || typeof value !== "object" || Array.isArray(value))
      throw Error("Expected selected object");
    return Object.fromEntries(
      Object.entries(spec)
        .filter(([k]) => Object.hasOwn(value, k))
        .map(([k, s]) => [k, bo_selected(value[k], s, depth + 1)]),
    );
  }
  if (value === null) return null;
  if (
    ["number", "scalar"].includes(spec) &&
    typeof value === "number" &&
    Number.isFinite(value) &&
    (!Number.isInteger(value) || Number.isSafeInteger(value))
  )
    return value;
  if (["boolean", "scalar"].includes(spec) && typeof value === "boolean") return value;
  if (["string", "scalar"].includes(spec) && typeof value === "string" && value.length <= 256)
    return value;
  throw Error("Unapproved capture type");
}

/** Queue observations separately from business decisions; delivery failures stay local. */
export class BOProbe {
  constructor({
    project,
    buildId,
    endpoint,
    token,
    runId = globalThis.crypto.randomUUID(),
    producerId = globalThis.crypto.randomUUID(),
    enabled = true,
    capacity = 256,
    timeout = 1000,
    sink = null,
  }) {
    this.bo_project = project;
    this.bo_build = buildId;
    this.bo_endpoint = endpoint;
    this.bo_token = token;
    this.bo_run = runId;
    this.bo_producer = producerId;
    this.bo_enabled = enabled;
    this.bo_capacity = capacity;
    this.bo_timeout = timeout;
    this.bo_sink = sink;
    this.bo_queue = [];
    this.bo_seq = 0;
    this.bo_busy = false;
    this.bo_internal = false;
    this.bo_errors = 0;
    this.bo_dropped = 0;
    this.bo_suppressed = 0;
    this.bo_nodes = new Map(project.model.nodes.map((n) => [n.id, n]));
    const excluded = project.model.implementation?.excluded || {};
    this.bo_excluded = new Set(
      project.model.nodes
        .filter(
          (n) =>
            n.source && excluded[`${n.source.path}::${n.source.symbol}`]?.category === "observer",
        )
        .map((n) => n.id),
    );
  }
  record(
    node,
    phase,
    builder,
    {
      entity = "application",
      attempt = "application",
      scope = "application",
      basis = {},
      callId = null,
      parentCallId = null,
      depends = [],
      revision = null,
    } = {},
  ) {
    if (!this.bo_enabled) return null;
    if (this.bo_internal || this.bo_excluded.has(node)) {
      this.bo_suppressed++;
      return null;
    }
    try {
      this.bo_internal = true;
      const spec = this.bo_nodes.get(node)?.capture;
      if (!spec) throw Error("Unknown capture node");
      if (
        !["enter", "return", "read", "decision", "wait", "commit", "change", "error"].includes(
          phase,
        )
      )
        throw Error("Unknown phase");
      const values = builder();
      const seq = ++this.bo_seq,
        id = `${this.bo_run}:${this.bo_producer}:${seq}`;
      const event = {
        protocol: "bo-event/v1",
        schema_version: 3,
        project_id: this.bo_project.project_id,
        model_revision: this.bo_project.model.revision,
        build_id: this.bo_build,
        run_id: this.bo_run,
        producer_id: this.bo_producer,
        seq,
        id,
        node,
        phase,
        entity,
        attempt,
        scope,
        call_id: callId || id,
        parent_call_id: parentCallId,
        basis: bo_selected(basis, { param_version: "number", epoch: "number", clock: "number" }),
        inputs: bo_selected(values.inputs || {}, spec.in || {}),
        outputs: bo_selected(values.outputs || {}, spec.out || {}),
        depends,
        observed_at: new Date().toISOString(),
      };
      if (revision !== null) {
        if (!Number.isSafeInteger(revision) || revision < 0) throw Error("Invalid state revision");
        event.revision = revision;
      }
      if (new TextEncoder().encode(JSON.stringify(event)).length > 24576)
        throw Error("Event too large");
      if (this.bo_queue.length >= this.bo_capacity) {
        this.bo_dropped++;
        return null;
      }
      this.bo_queue.push({ kind: "events", body: event });
      queueMicrotask(() => this.bo_drain());
      return id;
    } catch {
      this.bo_errors++;
      return null;
    } finally {
      this.bo_internal = false;
    }
  }
  snapshot(
    instanceId,
    state,
    context,
    revision,
    evidenceId,
    { event = null, guards = null, payload = null, configuration = null } = {},
  ) {
    if (!this.bo_enabled) return false;
    if (this.bo_internal) {
      this.bo_suppressed++;
      return false;
    }
    try {
      if (this.bo_queue.length >= this.bo_capacity) {
        this.bo_dropped++;
        return false;
      }
      const body = {
        protocol: "bo-snapshot/v1",
        project_id: this.bo_project.project_id,
        model_revision: this.bo_project.model.revision,
        build_id: this.bo_build,
        run_id: this.bo_run,
        producer_id: this.bo_producer,
        instance_id: instanceId,
        state,
        context,
        revision,
        evidence_id: evidenceId,
        event,
        guards,
        payload,
        configuration,
      };
      const raw = JSON.stringify(body);
      if (new TextEncoder().encode(raw).length > 24576) throw Error("Snapshot too large");
      this.bo_queue.push({ kind: "snapshots", body: JSON.parse(raw) });
      queueMicrotask(() => this.bo_drain());
      return true;
    } catch {
      this.bo_errors++;
      return false;
    }
  }
  async bo_drain() {
    if (this.bo_busy) return;
    this.bo_busy = true;
    try {
      while (this.bo_queue.length) {
        const item = this.bo_queue.shift();
        try {
          if (this.bo_sink) {
            let pending;
            this.bo_internal = true;
            try {
              pending = this.bo_sink(item.body, item.kind);
            } finally {
              this.bo_internal = false;
            }
            await pending;
          } else {
            for (let attempt = 0; attempt < 2; attempt++) {
              try {
                const response = await fetch(`${this.bo_endpoint}/api/bo/${item.kind}`, {
                  method: "POST",
                  headers: { "Content-Type": "application/json", "X-BO-Token": this.bo_token },
                  body: JSON.stringify(item.body),
                  signal: AbortSignal.timeout(this.bo_timeout),
                });
                if (!response.ok) throw Error("Collector rejected observation");
                break;
              } catch (error) {
                if (attempt === 1) throw error;
              }
            }
          }
        } catch {
          this.bo_errors++;
        }
      }
    } finally {
      this.bo_busy = false;
    }
  }
  async flush(timeout = 2000) {
    const deadline = Date.now() + timeout;
    while ((this.bo_busy || this.bo_queue.length) && Date.now() < deadline)
      await new Promise((r) => setTimeout(r, 5));
    return !this.bo_busy && !this.bo_queue.length;
  }
}
