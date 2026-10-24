import { t } from "./i18n.js";

// Database facts share the graph and event stream. These helpers only present
// supplied evidence; they never run a query or infer a missing relationship.
export const dataRoles = ["store", "dataset", "column", "query", "transform"];
export const dataRelations = ["reads", "writes", "references", "maps", "transforms"];
/** Upgrade old broad filters once; subsequent role exclusions remain explicit. */
export function migrateDataFilters(value) {
  if (!value || value.dataTypes === 1) return value;
  const next = { ...value, dataTypes: 1 };
  for (const key of ["nodes", "regions"])
    if (Array.isArray(value[key]))
      next[key] = [
        ...new Set([
          ...value[key],
          ...(value[key].includes("data") ? ["store", "dataset", "column"] : []),
          ...(value[key].includes("function") ? ["query", "transform"] : []),
        ]),
      ];
  if (Array.isArray(value.edges) && value.edges.includes("data"))
    next.edges = [...new Set([...value.edges, ...dataRelations])];
  return next;
}
const value = (item) => (typeof item === "string" ? item : JSON.stringify(item));
const present = (item) => item !== undefined && item !== null;

function statusLabel(status) {
  return (
    {
      entered: t("Started"),
      started: t("Started"),
      transformed: t("Processed"),
      returned: t("Returned result"),
      succeeded: t("Executed"),
      success: t("Executed"),
      executed: t("Executed"),
      committed: t("Committed"),
      rolled_back: t("Rolled back"),
      rollback: t("Rolled back"),
      failed: t("Failed"),
      error: t("Failed"),
      ended_before_exit: t("Transaction ended; outcome unverified"),
      partial_failure: t("Some writes failed"),
      acknowledgement_failed: t("Write acknowledgement failed"),
      rollback_failed: t("Rollback failed; outcome unverified"),
    }[status] || status
  );
}

export function dataStatusClass(status) {
  if (status === "ended_before_exit") return "historical";
  return [
    "failed",
    "error",
    "rolled_back",
    "rollback",
    "partial_failure",
    "acknowledgement_failed",
    "rollback_failed",
  ].includes(status)
    ? "blocked"
    : null;
}

/** Keep provenance, execution outcome, and committed effect visibly separate. */
export function dataLines(node, inputs = {}, outputs = {}, recorded = false) {
  const meta = node.data_metadata || {},
    rows = [];
  if (["query", "transform"].includes(node.data_role)) {
    if (recorded) {
      const outcome = [statusLabel(outputs.status) || t("Started")];
      if (present(outputs.duration_ms)) outcome.push(`${outputs.duration_ms} ms`);
      if (outputs.rows_known === true && present(outputs.rows))
        outcome.push(t("{0} rows", outputs.rows));
      if (outputs.rows_known === false) outcome.push(t("Row count unknown"));
      if (outputs.committed === true && !["committed"].includes(outputs.status))
        outcome.push(t("Committed"));
      if (outputs.committed === false && !["rolled_back", "rollback"].includes(outputs.status))
        outcome.push(t("Not committed"));
      rows.push({
        text: outcome.join(" · "),
        role:
          dataStatusClass(outputs.status) === "blocked"
            ? "bad"
            : dataStatusClass(outputs.status) === "historical"
              ? "muted"
              : "value",
      });
      if (inputs.statement) rows.push({ text: inputs.statement, role: "symbol" });
      const targetSource = {
        parsed_sql: t("Targets from SQL"),
        driver: t("Targets reported by driver"),
        provided: t("Targets supplied by application"),
        parsed_and_provided: t("Targets from SQL and application"),
        unresolved: t("Targets unresolved"),
      }[outputs.target_source];
      if (targetSource) rows.push({ text: targetSource, role: "muted" });
      if (present(outputs.input_count) || present(outputs.output_count))
        rows.push({
          text: t("Items: {0} → {1}", outputs.input_count ?? "?", outputs.output_count ?? "?"),
          role: "value",
        });
      if (present(outputs.before) || present(outputs.result))
        rows.push({
          text: t(
            "Values: {0} → {1}",
            present(outputs.before) ? value(outputs.before) : "?",
            present(outputs.result) ? value(outputs.result) : "?",
          ),
          role: "value",
        });
      if (present(inputs.parameters))
        rows.push({ text: t("Parameters: {0}", value(inputs.parameters)), role: "value" });
      if (outputs.error_type) rows.push({ text: outputs.error_type, role: "bad" });
      if (outputs.unknown_targets?.length)
        rows.push({
          text: t("Unresolved targets: {0}", outputs.unknown_targets.join(", ")),
          role: "muted",
        });
    } else rows.push({ text: node.summary || t("No query recorded"), role: "muted" });
    if (node.source?.symbol) rows.push({ text: node.source.symbol, role: "symbol" });
    return rows;
  }
  const origin = { database: t("Actual structure"), declaration: t("Declared structure") }[
    node.data_origin
  ];
  const coverage = {
    complete: t("Complete scope"),
    partial: t("Partial scope"),
    sampled: t("Sampled structure"),
  }[node.data_coverage];
  const identity = [meta.engine || meta.kind, meta.native_type].filter(Boolean);
  if (meta.primary_key) identity.push(t("Primary key"));
  if (meta.nullable === false || meta.required === true) identity.push(t("Required"));
  if (meta.nullable === true) identity.push(t("Nullable"));
  if (identity.length) rows.push({ text: identity.join(" · "), role: "value" });
  const comparison = {
    declared_only: t("Awaiting database structure"),
    database_only: t("Database structure only"),
    matched: t("Declaration matches database"),
    different: t("Declaration differs from database"),
    stale: t("Structure needs checking"),
    application_declared: t("Application model declaration"),
    unverified: t("Database structure unverified"),
    outside_scope: t("Reference outside inspected scope"),
  }[meta.status];
  if (comparison)
    rows.push({
      text: comparison,
      role: ["different", "stale"].includes(meta.status)
        ? "bad"
        : ["application_declared", "unverified", "outside_scope"].includes(meta.status)
          ? "muted"
          : "value",
    });
  if (origin || coverage)
    rows.push({ text: [origin, coverage].filter(Boolean).join(" · "), role: "muted" });
  for (const constraint of meta.constraints || [])
    rows.push({
      text: [
        constraint.kind,
        constraint.fields?.join(", "),
        constraint.target ? `→ ${constraint.target}` : constraint.description,
      ]
        .filter(Boolean)
        .join(" · "),
      role: "symbol",
    });
  for (const limitation of meta.limitations || []) rows.push({ text: limitation, role: "muted" });
  if (!rows.length && node.summary) rows.push({ text: node.summary, role: "muted" });
  return rows;
}

/** Invalid refreshes keep the last good graph, with an explicit current warning. */
export function databaseWarning(status) {
  if (!status || status.valid !== false) return null;
  return {
    label: t("Database structure needs checking"),
    details: (status.errors || [])
      .map((item) => (typeof item === "string" ? item : JSON.stringify(item)))
      .join("; ")
      .slice(0, 1200),
  };
}

/** A native constraint is metadata evidence, not an executed query or an inferred rule. */
export function dataRelationEvidence(edge) {
  if (!["references", "maps"].includes(edge.data_relation || edge.type)) return null;
  const origins = new Set(
    (edge.members || [edge]).flatMap((member) => [
      member.data_origin,
      ...(member.data_constraints || []).map((constraint) => constraint.origin),
    ]),
  );
  return origins.has("database") && origins.has("declaration")
    ? t("Database metadata and model")
    : origins.has("database")
      ? t("Database metadata")
      : origins.has("declaration")
        ? t("Model declaration")
        : null;
}

/** Static read/write declarations become observed only with a resolved target. */
export function observedDataTransfer(edge, event, all) {
  const relation = edge.data_relation || edge.type;
  if (!["reads", "writes"].includes(relation)) return false;
  const query = all.get(relation === "reads" ? edge.to : edge.from);
  const dataset = all.get(relation === "reads" ? edge.from : edge.to);
  const matchesTarget = (target) => {
    if (target === dataset?.data_key) return true;
    if (typeof target !== "string" || !target.startsWith("table:") || target.slice(6).includes("."))
      return false;
    const candidates = [...all.values()].filter(
      (node) =>
        node.data_role === "dataset" &&
        node.data_store === dataset?.data_store &&
        node.data_key?.startsWith("table:") &&
        node.data_key.slice(6).split(".").at(-1) === target.slice(6),
    );
    return candidates.length === 1 && candidates[0].id === dataset?.id;
  };
  const access = event.outputs?.target_access;
  // Parsed access identifies direction per table in a mixed read/write query.
  // Older or generic adapters still expose explicitly declared target bindings.
  if (
    Array.isArray(access) &&
    access.length &&
    !access.some(
      (item) =>
        matchesTarget(item.target) && item.action === (relation === "reads" ? "read" : "write"),
    )
  )
    return false;
  return (
    query?.id === event.node &&
    dataset?.data_role === "dataset" &&
    query.data_store === dataset.data_store &&
    event.outputs?.targets?.some(matchesTarget) === true &&
    ["return", "error", "commit", "change"].includes(event.phase)
  );
}

export function dataTransferLabel(type, event) {
  const names = {
    reads: t("Read"),
    writes: t("Write"),
    transforms: t("Transform"),
    references: t("Reference"),
    maps: t("Mapping"),
  };
  if (!names[type]) return null;
  const out = event.outputs || {},
    parts = [names[type]];
  if (out.status) parts.push(statusLabel(out.status));
  if (out.rows_known === true && present(out.rows)) parts.push(t("{0} rows", out.rows));
  if (type === "transforms" && (present(out.input_count) || present(out.output_count)))
    parts.push(t("Items: {0} → {1}", out.input_count ?? "?", out.output_count ?? "?"));
  return parts.join(" · ");
}
