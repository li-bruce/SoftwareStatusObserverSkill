import { t as boTranslate } from "./i18n.js";
import {
  dataRoles,
  dataRelations,
  dataLines,
  observedDataTransfer,
  dataStatusClass,
} from "./data-layer.js";
// Business groups, internal activity states and local source share one graph.
export const colors = {
  ink: 0x30454d,
  muted: 0x7d8e96,
  line: 0xb6c7cc,
  green: 0x208b73,
  orange: 0xbc8739,
  blue: 0x477b9c,
  white: 0xffffff,
};
export const stateLabels = {
  pending: boTranslate("Not started"),
  waiting: boTranslate("Waiting for capacity"),
  running: boTranslate("Running"),
  succeeded: boTranslate("Passed"),
  rejected: boTranslate("Rejected"),
  failed: boTranslate("Failed"),
  cancelled: boTranslate("Cancelled"),
};
export function phaseLabel(model, value) {
  const labels = model?.machine?.labels;
  return labels && Object.hasOwn(labels, value) ? labels[value] : String(value);
}
export function compact(v) {
  if (v === undefined) return "—";
  if (typeof v === "string") return v;
  return JSON.stringify(v);
}
export function typeName(t) {
  if (Array.isArray(t)) return `list[${typeName(t[0])}]`;
  if (typeof t === "object") return "record";
  return { number: "number", string: "str", boolean: "bool" }[t] || t;
}
export function configurations(view) {
  return view.machine.configurations || view.authority.parameters.executions || [];
}
export function executionIds(view) {
  const runs = configurations(view);
  return runs.length
    ? runs.map((x) => x.attempt)
    : [...new Set(view.events.filter((e) => e.node === "read").map((e) => e.attempt))];
}
export function currentAttempt(view, choice) {
  return choice === "latest"
    ? view.authority.parameters.attempt || executionIds(view).at(-1)
    : choice;
}
export function selectedConfiguration(view, choice = "latest", step = "latest") {
  const run = configurations(view).find((r) => r.attempt === currentAttempt(view, choice));
  if (!run) return null;
  if (step === "latest") return run;
  const entry = run.journal.find((e) => String(e.seq) === String(step));
  // Historical frames contain recorded state only, never the run's later
  // results, disposition or current qualification.
  return entry
    ? {
        attempt: run.attempt,
        param_version: run.param_version,
        ...entry.after,
        phase: entry.after.phase ?? entry.phase ?? null,
        revision: entry.seq,
        selectedFrame: entry,
      }
    : null;
}
export function selectedEvents(view, choice, step = "latest") {
  const id = currentAttempt(view, choice);
  let events = view.events.filter(
    (e) =>
      e.attempt === id ||
      e.scope === "application" ||
      (e.scope === "entity" && e.entity === view.authority.entity),
  );
  if (step !== "latest") {
    // A later reevaluation may reuse an activity revision. Only its first exact
    // recorded boundary belongs to this frame; absent boundaries stay unknown.
    const parent = view.model.machine.execution?.parent;
    const frame = events.find((e) => e.node === parent && e.outputs?.revision === Number(step));
    events = frame ? events.filter((e) => e.seq <= frame.seq) : [];
  }
  return events;
}
export function sourceBinding(view, all, id) {
  if (view?.stage === "design") return undefined;
  const direct = view?.manifest.bindings[id];
  if (direct) return direct;
  const node = all?.get(id);
  if (node?.referenceOf)
    return view?.manifest.bindings[node.referenceOf] || view?.manifest.bindings[node.event_node];
  return node?.field ? view?.manifest.bindings[node.event_node || node.parent] : undefined;
}
export function nodeEvents(node, events) {
  return events.filter((e) => e.node === (node.event_node || node.id));
}
export function callValues(node, events) {
  const calls = nodeEvents(node, events),
    last = calls.at(-1);
  if (!last) return { inputs: {}, outputs: {} };
  const keys = ["call_id", "run_id", "attempt", "entity", "build_id", "model_revision"];
  // Old probes used attempt:node for every call. That is not enough identity
  // to merge values; keep the last event until the caller supplies a call ID.
  const identified =
    keys.every((k) => typeof last[k] === "string" && last[k]) &&
    last.call_id !== `${last.attempt}:${last.node}`;
  const same = identified
    ? calls.filter(
        (e) =>
          keys.every((k) => e[k] === last[k]) &&
          e.basis?.param_version === last.basis?.param_version,
      )
    : [last];
  return same.reduce(
    (values, e) => ({
      inputs: { ...values.inputs, ...e.inputs },
      outputs: { ...values.outputs, ...e.outputs },
    }),
    { inputs: {}, outputs: {} },
  );
}
function activityName(view, id) {
  return view.model.nodes.find((n) => n.id === id)?.label || id;
}
function activityColor(state) {
  return (
    {
      running: "active",
      waiting: "blocked",
      rejected: "blocked",
      failed: "blocked",
      succeeded: "ok",
      cancelled: "historical",
    }[state] || "declared"
  );
}
function resourceOf(node, view, configuration) {
  return view.machine.shared_resources?.[node.id] || configuration?.resources?.[node.id];
}
function phaseValue(view, configuration, choice) {
  return configuration?.selectedFrame
    ? configuration.phase
    : choice === "latest"
      ? view.machine.current
      : configuration?.phase;
}
export function parameterSummary(view, _configuration = null, step = "latest") {
  if (step !== "latest") return "";
  const parameters = view.authority?.parameters || {},
    fields = view.model.presentation?.context_fields || [];
  return fields
    .filter((f) => parameters[f.key] !== undefined)
    .map(
      (f) =>
        (view.historical ? f.saved_label || f.label : f.label) +
        " " +
        compact(parameters[f.key]) +
        (f.unit ? " " + f.unit : ""),
    )
    .join(" · ");
}
function staleBasis(node, view, last) {
  const owner = view.model.nodes.find((n) => n.id === (node.event_node || node.id)) || node;
  const fields = owner.basis_fields || ["param_version"];
  return fields.some((key) => last.basis?.[key] !== view.authority.basis?.[key]);
}
export function status(node, view, events, choice, configuration = null) {
  if (view.stage === "design") return "declared";
  if (node.referenceOf) node = { ...node, id: node.referenceOf };
  if (["query", "transform"].includes(node.data_role)) {
    const last = nodeEvents(node, events).at(-1);
    const state = dataStatusClass(last?.outputs?.status);
    if (state) return state;
  }
  if (
    configuration?.disposition === "interrupted" &&
    (node.execution_role || node.id === view.model.machine.execution?.parent)
  )
    return "historical";
  if (node.execution_role === "activity")
    return activityColor(configuration?.activities?.[node.id]);
  if (node.execution_role === "resource") {
    const r = resourceOf(node, view, configuration);
    return typeof r?.available === "number" ? (r.available === 0 ? "blocked" : "ok") : "declared";
  }
  if (node.execution_role === "join")
    return (
      { waiting: "blocked", enabled: "active", passed: "ok", rejected: "blocked" }[
        configuration?.join?.state
      ] || "declared"
    );
  if (node.id === view.model.machine.execution?.parent && configuration)
    return Object.values(configuration.activities || {}).includes("running")
      ? "active"
      : configuration.join?.state === "passed"
        ? "ok"
        : "blocked";
  if (node.layer === "state")
    return node.value === phaseValue(view, configuration, choice) ? "active" : "declared";
  if (node.field) {
    const values = callValues(node, events)[node.direction === "in" ? "inputs" : "outputs"];
    if (!(node.field in values)) return "declared";
  }
  if (node.layer === "business") {
    const states = view.model.nodes
      .filter((n) => n.parent === node.id && n.layer !== "state")
      .map((n) => status(n, view, events, choice, configuration));
    if (!nodeEvents(node, events).length)
      return (
        ["active", "blocked", "ok", "historical"].find((s) => states.includes(s)) || "declared"
      );
  }
  const last = nodeEvents(node, events).at(-1);
  if (!last) return "declared";
  if (
    view.binding_status.status !== "current" ||
    choice !== "latest" ||
    staleBasis(node, view, last)
  )
    return "historical";
  if (
    last.phase === "wait" ||
    last.phase === "error" ||
    last.outputs.allowed === false ||
    last.outputs.safe === false
  )
    return "blocked";
  return last.phase === "enter" ? "active" : "ok";
}
export function lines(node, view, events, choice, configuration = null) {
  if (node.filter_context)
    return [
      {
        text: boTranslate("Filter boundary \u00B7 ") + nodeTypes[nodeType(node)].label,
        role: "muted",
      },
      { text: node.source?.symbol || node.summary, role: "symbol" },
    ];
  if (node.referenceOf) node = { ...node, id: node.referenceOf };
  if (dataRoles.includes(node.data_role)) {
    const values = callValues(node, events);
    return dataLines(node, values.inputs, values.outputs, nodeEvents(node, events).length > 0);
  }
  if (view.stage === "design") return node.summary ? [{ text: node.summary, role: "muted" }] : [];
  if (node.field) {
    const values = callValues(node, events)[node.direction === "in" ? "inputs" : "outputs"];
    return [
      { text: node.field + ": " + typeName(node.fieldType), role: "symbol" },
      {
        text:
          node.field in values
            ? compact(values[node.field])
            : boTranslate("Not captured in this run"),
        role: node.field in values ? "value" : "muted",
      },
    ];
  }
  const last = nodeEvents(node, events).at(-1),
    result = [{ text: node.signature || node.source?.symbol || node.summary, role: "symbol" }];
  if (node.execution_role === "resource") {
    const r = resourceOf(node, view, configuration);
    if (!r) {
      result.push({
        text: boTranslate("No resource state recorded at this boundary"),
        role: "muted",
      });
      return result;
    }
    for (const [field, value] of Object.entries(r))
      result.push({
        text: `${node.field_labels?.[field] || field}：${compact(value)}`,
        role: field === "available" && value === 0 ? "bad" : "value",
      });
    return result;
  }
  if (node.execution_role) {
    if (!configuration) {
      result.push({ text: boTranslate("No internal state recorded for this run"), role: "muted" });
      return result;
    }
    if (node.execution_role === "activity") {
      const state = configuration.activities?.[node.id];
      result.push({
        text: stateLabels[state] || state || boTranslate("Not recorded"),
        role: state === "waiting" || state === "failed" || state === "rejected" ? "bad" : "good",
      });
      if (configuration.disposition === "interrupted")
        result[result.length - 1] = {
          text:
            boTranslate("Execution interrupted; last recorded state: \u201C") +
            stateLabels[state] +
            "」",
          role: "muted",
        };
      result.push({
        text: `state: ${view.model.machine.execution?.activity_state_type || "str"} = ${state ?? boTranslate("Not recorded")}`,
        role: "value",
      });
      if (node.summary) result.push({ text: node.summary, role: "muted" });
    } else {
      const j = configuration.join;
      if (!j) {
        result.push({
          text: boTranslate("No join state recorded at this boundary"),
          role: "muted",
        });
        return result;
      }
      result.push({
        text:
          {
            waiting: boTranslate("Some activities are unfinished"),
            enabled: boTranslate("Activities finished; checking results"),
            passed: boTranslate("All activities passed"),
            rejected: boTranslate("Some activities did not pass"),
          }[j.state] || j.state,
        role: j.state === "passed" ? "good" : "bad",
      });
      if (j.pending?.length)
        result.push({
          text:
            boTranslate("Still waiting for: ") +
            j.pending.map((x) => activityName(view, x)).join("、"),
          role: "muted",
        });
      if (node.summary) result.push({ text: node.summary, role: "muted" });
      return result;
    }
  } else if (node.layer === "state") {
    result.push({ text: `phase: Phase = ${node.value}`, role: "value" });
    result.push({
      text:
        node.value === phaseValue(view, configuration, choice)
          ? boTranslate("Flow state for this run")
          : boTranslate("Reachable flow state"),
      role: "muted",
    });
    if (node.value === view.model.machine.execution?.within && configuration) {
      for (const [id, state] of Object.entries(configuration.activities || {}))
        result.push({
          text: activityName(view, id) + "：" + stateLabels[state],
          role: state === "waiting" ? "bad" : "value",
        });
    }
    return result;
  } else if (node.layer === "business") {
    result.push({ text: node.summary, role: "muted" });
    if (node.id === view.model.machine.execution?.parent) {
      if (configuration) {
        if (configuration.disposition === "interrupted")
          result.push({
            text: boTranslate("This run was interrupted; showing its last recorded state"),
            role: "bad",
          });
        for (const [id, state] of Object.entries(configuration.activities || {}))
          result.push({
            text: activityName(view, id) + "：" + stateLabels[state],
            role: state === "waiting" || state === "failed" ? "bad" : "value",
          });
        for (const r of Object.values(configuration.resources || {}))
          result.push({
            text: boTranslate("Available capacity: {0} / {1}", r.available, r.capacity),
            role: "value",
          });
      } else result.push({ text: boTranslate("Checks have not started"), role: "muted" });
    } else {
      const names = {
        "allowed": boTranslate("Allowed"),
        "version_ok": boTranslate("Parameter version remains valid"),
        "param_version": boTranslate("Parameter version"),
        "length": boTranslate("Text length"),
        "version": boTranslate("Committed version"),
        "reason": boTranslate("Reason execution cannot continue"),
      };
      const reasons = {
        no_current_authorization: boTranslate("No valid authorization"),
        check_rejected: boTranslate("Some checks did not pass"),
        authorization_or_version_changed: boTranslate("Authorization or parameter version changed"),
        worker_error: boTranslate("A check function failed"),
        process_restarted: boTranslate("Process restarted; previous checks were interrupted"),
      };
      const ids = view.model.nodes
        .filter((n) => n.parent === node.id && n.layer !== "state")
        .map((n) => n.id);
      for (const id of ids) {
        const e = events.filter((e) => e.node === id).at(-1),
          child = view.model.nodes.find((n) => n.id === id);
        if (e)
          for (const [k, v] of Object.entries(e.outputs).slice(0, 2))
            result.push({
              text: `${child?.field_labels?.[k] || names[k] || k}：${v === true ? boTranslate("Yes") : v === false ? boTranslate("No") : k === "reason" ? reasons[v] || v : compact(v)}`,
              role: v === false ? "bad" : "value",
            });
      }
    }
    if (!Object.keys(node.capture || {}).length) return result;
  }
  if (last && staleBasis(node, view, last))
    result.push({
      text: boTranslate("Historical decision/read: evidence changed; awaiting reevaluation"),
      role: "muted",
    });
  for (const [direction, spec] of Object.entries(node.capture || {})) {
    const vals = callValues(node, events)[direction === "in" ? "inputs" : "outputs"];
    for (const [key, t] of Object.entries(spec)) {
      if (!(key in vals) || key === "state") continue;
      result.push({
        text: `${direction === "in" ? boTranslate("Parameter") : boTranslate("Return")} ${key}: ${typeName(t)} = ${compact(vals[key])}`,
        role: vals[key] === false ? "bad" : "value",
      });
    }
  }
  if (!last && !node.execution_role)
    result.push({ text: boTranslate("No call recorded; expand to inspect source"), role: "muted" });
  return result;
}
export function wrapText(text, width = 47) {
  const out = [];
  let row = "",
    units = 0;
  for (const c of text) {
    const size = c.charCodeAt(0) > 255 ? 1.8 : 1;
    if (c === "\n" || units + size > width) {
      out.push(row);
      row = "";
      units = 0;
      if (c === "\n") continue;
    }
    row += c;
    units += size;
  }
  if (row || !out.length) out.push(row);
  return out;
}
export const nodeTypes = {
  business: { label: boTranslate("Business"), glyph: "B", color: 0x5075b5 },
  function: { label: boTranslate("Function"), glyph: "ƒ", color: 0x387c88 },
  state: { label: boTranslate("State"), glyph: "S", color: 0x9869a0 },
  decision: { label: boTranslate("Decision"), glyph: "?", color: 0xaf8029 },
  resource: { label: boTranslate("Resource"), glyph: "R", color: 0x7b8845 },
  data: { label: boTranslate("Parameter"), glyph: "x", color: 0x627f9c },
  effect: { label: boTranslate("Effect"), glyph: "✓", color: 0x2d8a70 },
  wait: { label: boTranslate("Wait"), glyph: "…", color: 0xb38442 },
  store: { label: boTranslate("Database"), glyph: "DB", color: 0x426b9a },
  dataset: { label: boTranslate("Table or collection"), glyph: "T", color: 0x3d7e97 },
  column: { label: boTranslate("Data field"), glyph: ":", color: 0x638b98 },
  query: { label: boTranslate("Database operation"), glyph: "Q", color: 0x316da4 },
  transform: { label: boTranslate("Data processing"), glyph: "Δ", color: 0x997345 },
};
export function nodeType(n) {
  if (dataRoles.includes(n.data_role)) return n.data_role;
  return n.layer === "business"
    ? "business"
    : n.kind === "state"
      ? "state"
      : n.kind === "resource" || n.execution_role === "resource"
        ? "resource"
        : n.kind === "decision" || n.execution_role === "join"
          ? "decision"
          : n.kind === "data"
            ? "data"
            : n.kind === "effect"
              ? "effect"
              : n.kind === "wait"
                ? "wait"
                : "function";
}
// A business action can also implement a function. View membership is not its
// visual type; selecting a view must not erase that function's values or calls.
export function viewTypes(n) {
  if (dataRoles.includes(n.data_role)) return [n.data_role];
  return [
    ...new Set([
      nodeType(n),
      ...(n.semantic_roles?.includes("business") ? ["business"] : []),
      ...(n.source && n.kind !== "state" && !n.field ? ["function"] : []),
    ]),
  ];
}
export function stateNodeId(model, value) {
  return model.nodes.find((n) => n.kind === "state" && n.value === value)?.id || "state." + value;
}
export function relationType(e) {
  if (e.type === "data" && dataRelations.includes(e.data_relation)) return e.data_relation;
  if (dataRelations.includes(e.type)) return e.type;
  return ["python-ast", "source-ast"].includes(e.origin) && e.type === "flow"
    ? "call"
    : [
          "call",
          "flow",
          "transition",
          "guard",
          "data",
          "resource",
          "join",
          "shared",
          "contains",
        ].includes(e.type)
      ? e.type
      : "other";
}
// One typed graph. Folding changes visible nodes, never their identities or facts.
// The old layoutGraph name remains for integrations; coordinates are assigned by layout.js.
export function layoutGraph(
  view,
  expanded = new Set(),
  _sourceOpen = new Set(),
  _fullSources = new Map(),
  choice = "latest",
  step = "latest",
  options = {},
) {
  const configuration = selectedConfiguration(view, choice, step),
    events = selectedEvents(view, choice, step);
  const all = new Map(view.model.nodes.map((n) => [n.id, n])),
    children = new Map(),
    rawEdges = [...view.model.edges];
  for (const n of view.model.nodes) {
    if (n.kind === "state") continue;
    for (const [direction, fields] of Object.entries(n.capture || {}))
      for (const [field, fieldType] of Object.entries(fields)) {
        const id = `field:${n.id}:${direction}:${field}`;
        all.set(id, {
          id,
          label: field,
          summary:
            direction === "in" ? boTranslate("Input parameter") : boTranslate("Return value"),
          kind: "data",
          layer: "parameter",
          parent: n.id,
          field,
          fieldType,
          direction,
          event_node: n.event_node || n.id,
          origin: "capture-field",
        });
        rawEdges.push({
          id: `capture:${id}`,
          from: direction === "in" ? id : n.id,
          to: direction === "in" ? n.id : id,
          type: "data",
          label: direction === "in" ? boTranslate("Input") : boTranslate("Return"),
          origin: "capture-field",
        });
      }
  }
  const stateIds = new Map();
  for (const value of view.model.machine.values) {
    const authored = [...all.values()].find((n) => n.kind === "state" && n.value === value);
    const id = stateNodeId(view.model, value);
    stateIds.set(value, id);
    if (!authored)
      all.set(id, {
        id,
        label: view.model.machine.labels?.[value] || value,
        kind: "state",
        layer: "state",
        value,
        source: view.model.machine.source,
      });
  }
  const attempt = currentAttempt(view, choice);
  for (const t of view.model.machine.transitions) {
    const sources = Array.isArray(t.source) ? t.source : [t.source];
    for (const source of view.model.machine.values.filter((v) =>
      sources.some((s) => s === "*" || s === v || v.startsWith(s + "_")),
    )) {
      const target = t.dest || source,
        from = stateIds.get(source),
        to = stateIds.get(target);
      const observed =
        step === "latest" &&
        (view.machine.journal || []).some(
          (j) =>
            j.event === t.trigger &&
            j.source === source &&
            j.target === target &&
            j.attempt === attempt,
        );
      rawEdges.push({
        id: "transition:" + t.trigger + ":" + source,
        from,
        to,
        type: "transition",
        event: t.trigger,
        label: view.model.machine.event_labels?.[t.trigger] || t.trigger,
        observed,
        current: choice === "latest",
      });
    }
  }
  // Membership is a view reference to one canonical identity, not another call.
  for (const m of options.memberships || []) {
    const member = all.get(m.member),
      group = all.get(m.group);
    if (!member || !group || member.parent === group.id || member.id === group.id) continue;
    const id = "ref:" + encodeURIComponent(group.id) + ":" + encodeURIComponent(member.id);
    all.set(id, {
      ...member,
      id,
      parent: group.id,
      referenceOf: member.id,
      event_node: member.event_node || member.id,
      summary: boTranslate("Shared entry: ") + m.reason,
      origin: "membership-reference",
      membership: m,
    });
    rawEdges.push({
      id: "shared:" + id,
      from: id,
      to: member.id,
      type: "shared",
      label: boTranslate("Same node"),
      evidence: m.evidence,
    });
  }
  const explicitlyHidden = new Set(options.hiddenNodes || []);
  const excludedIds = new Set();
  for (const [id, node] of all) {
    let current = node;
    const seen = new Set();
    while (current && !seen.has(current.id)) {
      seen.add(current.id);
      if (explicitlyHidden.has(current.id) || explicitlyHidden.has(current.referenceOf)) {
        excludedIds.add(id);
        break;
      }
      current = all.get(current.parent);
    }
  }
  let matched = null;
  if (options.match) {
    for (const [id, n] of all) {
      let depth = 0,
        p = n.parent;
      const seen = new Set([id]);
      while (p && !seen.has(p)) {
        seen.add(p);
        depth++;
        p = all.get(p)?.parent;
      }
      all.set(id, { ...n, projection_depth: depth });
    }
    matched = options.match(
      all,
      events,
      (n) => status(n, view, events, choice, configuration),
      rawEdges,
    );
    for (const id of excludedIds) matched.delete(id);
    for (const id of matched.contextIds || [])
      all.set(id, { ...all.get(id), filter_context: true, parent: undefined });
    for (const id of matched) {
      const node = all.get(id),
        seen = new Set([id]);
      let parent = node.parent;
      while (
        parent &&
        (!matched.has(parent) || matched.contextIds?.has(parent)) &&
        !seen.has(parent)
      ) {
        seen.add(parent);
        parent = all.get(parent)?.parent;
      }
      all.set(id, { ...node, parent: parent && matched.has(parent) ? parent : undefined });
    }
  }
  for (const n of all.values())
    if (n.parent) {
      if (!children.has(n.parent)) children.set(n.parent, []);
      children.get(n.parent).push(n.id);
    }
  const visibleIds = matched
    ? new Set([...matched].filter((id) => !all.get(id).parent))
    : new Set([
        ...(view.model.graph_roots || view.model.overview?.map((x) => x.node) || []),
        ...[...all.values()].filter((n) => !n.parent).map((n) => n.id),
      ]);
  // State nodes follow the same containment and expansion rules as functions.
  // Folding affects visibility only; all states and facts remain in `all`.
  function reveal(id, seen = new Set()) {
    if (seen.has(id)) return;
    seen.add(id);
    if (expanded.has(id) && !all.get(id)?.filter_context)
      for (const child of children.get(id) || [])
        if (!matched || matched.has(child)) {
          visibleIds.add(child);
          reveal(child, seen);
        }
  }
  for (const id of [...visibleIds]) reveal(id);
  const eligibleIds = new Set(
    [...all.keys()].filter(
      (id) =>
        !excludedIds.has(id) &&
        (!matched || matched.has(id)) &&
        (!options.include || options.include(all.get(id))),
    ),
  );
  const boxes = [...visibleIds]
    .filter((id) => eligibleIds.has(id))
    .map((id, i) => {
      const node = all.get(id),
        type = nodeType(node),
        rows = lines(node, view, events, choice, configuration);
      return {
        id,
        node,
        type,
        rows,
        open: expanded.has(id) && !node.filter_context,
        kids: node.filter_context
          ? []
          : (children.get(id) || []).filter((id) => eligibleIds.has(id)),
        state: status(node, view, events, choice, configuration),
        x: 80 + (i % 5) * 230,
        y: 70 + Math.floor(i / 5) * 180,
        w: 190,
        h: type === "state" ? 105 : ["query", "transform"].includes(type) ? 172 : 135,
      };
    });
  const byId = new Map(boxes.map((b) => [b.id, b]));
  function visible(id) {
    const seen = new Set();
    let n = all.get(id);
    while (n && !byId.has(n.id)) {
      if (seen.has(n.id)) return null;
      seen.add(n.id);
      n = all.get(n.parent);
    }
    return n?.id;
  }
  const edgeMap = new Map();
  for (const e of rawEdges) {
    if (!eligibleIds.has(e.from) || !eligibleIds.has(e.to) || options.hiddenEdges?.includes(e.id))
      continue;
    const from = visible(e.from),
      to = visible(e.to);
    if (!from || !to || (from === to && e.from !== e.to)) continue;
    // Project every cross-group relation onto its enclosing groups. Original
    // endpoints remain in members; folding must not erase static call edges.
    const source = all.get(e.from),
      target = all.get(e.to);
    if (!source || !target) continue;
    const sourceEvents = nodeEvents(source, events),
      targetEvents = nodeEvents(target, events),
      ids = new Set(sourceEvents.map((x) => x.id));
    let observed =
      e.type === "transition"
        ? e.observed
        : !["python-ast", "source-ast", "capture-field"].includes(e.origin) &&
          !["contains", "shared"].includes(e.type) &&
          targetEvents.some((x) =>
            (x.depends || []).some((d) => ids.has(d.event) && d.type === e.type),
          );
    if (["reads", "writes"].includes(e.data_relation))
      observed = events.some((event) => observedDataTransfer(e, event, all));
    let label =
      e.type === "contains"
        ? target.kind === "state"
          ? boTranslate("State membership")
          : boTranslate("Contains")
        : e.label;
    if (configuration && e.type === "resource") {
      const state = configuration.activities?.[e.to];
      observed = !!state && state !== "pending";
      label =
        state === "running"
          ? boTranslate("Occupies {0} slots", e.units)
          : state === "waiting"
            ? boTranslate("Capacity exhausted; waiting")
            : ["succeeded", "failed", "rejected"].includes(state)
              ? boTranslate("Capacity released")
              : e.label;
    }
    if (configuration && e.type === "join") {
      const state = configuration.activities?.[e.from];
      observed = ["succeeded", "failed", "rejected"].includes(state);
      label =
        state === "succeeded"
          ? boTranslate("This check passed")
          : state === "failed"
            ? boTranslate("Check failed")
            : state === "rejected"
              ? boTranslate("Check rejected")
              : boTranslate("Waiting for this check");
    }
    const current =
      choice === "latest" &&
      view.binding_status.status === "current" &&
      (!sourceEvents.length ||
        sourceEvents.at(-1)?.basis.param_version === view.authority.basis.param_version);
    // Different relation types sharing endpoints remain separate edges.
    const key = from + ">" + to + ":" + relationType(e) + ":" + (e.origin || "model");
    const member = { ...e, label, observed, current };
    if (edgeMap.has(key)) {
      const found = edgeMap.get(key);
      found.labels.add(label);
      found.observed ||= observed;
      found.members.push(member);
    } else
      edgeMap.set(key, {
        ...e,
        from,
        to,
        labels: new Set([label]),
        members: [member],
        observed,
        current,
      });
  }
  const graph = {
    boxes,
    byId,
    edges: [...edgeMap.values()],
    rawEdges,
    events,
    configuration,
    children,
    all,
    eligibleIds,
  };
  return graphBounds(graph);
}
export function graphBounds(graph) {
  const boxes = graph.boxes;
  graph.minX = boxes.length ? Math.min(...boxes.map((b) => b.x)) - 55 : 0;
  graph.minY = boxes.length ? Math.min(...boxes.map((b) => b.y)) - 55 : 0;
  graph.width = (boxes.length ? Math.max(...boxes.map((b) => b.x + b.w)) : 100) - graph.minX + 55;
  graph.height = (boxes.length ? Math.max(...boxes.map((b) => b.y + b.h)) : 100) - graph.minY + 55;
  return graph;
}
