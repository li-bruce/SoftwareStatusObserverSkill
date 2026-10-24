/** Node database observations share BOProbe and never own database connection lifetimes. */
import { AsyncLocalStorage } from "node:async_hooks";
import { randomUUID } from "node:crypto";
import { bo_selected } from "./bo_runtime.mjs";

const bo_context = new AsyncLocalStorage();

/** Exclude observer metadata/transport work, including work resumed after await. */
export function bo_internal(callback) {
  return bo_context.run({ ...bo_context.getStore(), internal: true }, callback);
}

/** Return only a command name. Native SQL/Cypher text needs a reviewed parser adapter. */
export function bo_command_shape(statement) {
  return typeof statement === "string" && /^[A-Za-z][A-Za-z0-9_]{0,63}$/.test(statement)
    ? statement
    : "[query text omitted]";
}

export class BODataRuntime {
  constructor(probe, config) {
    this.bo_probe = probe;
    this.bo_operations = new Map((config.operations || config).map((item) => [item.id, item]));
    this.bo_excluded = new WeakSet();
    this.bo_errors = 0;
    this.bo_suppressed = 0;
    this.bo_events = new AsyncLocalStorage();
    // BOProbe's boolean protects synchronous builders. Keep its asynchronous sink
    // in the same observer scope too, so a later await cannot re-enter capture.
    if (probe.bo_sink) {
      const sink = probe.bo_sink;
      probe.bo_sink = (...args) => bo_internal(() => sink.apply(probe, args));
    }
  }

  /** Bind causal identifiers to a caller-controlled async request boundary. */
  operation(node, callback, context = {}) {
    if (!this.bo_operations.has(node)) throw Error("Unknown data operation");
    return this.bo_events.run({ last: null }, () =>
      bo_context.run({ ...bo_context.getStore(), node, ...context }, callback),
    );
  }

  get lastEventId() {
    return this.bo_events.getStore()?.last || null;
  }

  excludeConnection(connection) {
    this.bo_excluded.add(connection);
  }

  bo_allowed(connection) {
    if (
      bo_context.getStore()?.internal ||
      this.bo_probe.bo_internal ||
      (connection && this.bo_excluded.has(connection))
    ) {
      this.bo_suppressed++;
      return false;
    }
    return true;
  }

  bo_select(value, spec) {
    try {
      return bo_internal(() => bo_selected(value, spec));
    } catch {
      this.bo_errors++;
      return {};
    }
  }

  bo_begin(node, options) {
    try {
      const operation = this.bo_operations.get(node);
      const context = bo_context.getStore() || {};
      const targets = [...new Set(options.targets || [])]
        .filter((value) => typeof value === "string" && value.length <= 256)
        .slice(0, 64);
      const call = {
        node,
        callId: randomUUID(),
        started: performance.now(),
        inputs: {
          operation: operation.action,
          statement: bo_command_shape(options.statement || "command"),
          parameters: this.bo_select(options.parameters || {}, operation.parameters || {}),
        },
        targets,
        targetSource: targets.length
          ? "provided"
          : ["read", "write"].includes(operation.action)
            ? "unresolved"
            : "not_applicable",
        unknown:
          targets.length || !["read", "write"].includes(operation.action)
            ? []
            : ["target_not_observed"],
        transactionId: context.transactionId,
        context: {
          entity: options.entity ?? context.entity,
          attempt: options.attempt ?? context.attempt,
          scope: options.scope ?? context.scope,
          parentCallId: options.parentCallId ?? context.parentCallId,
          depends: (options.depends || []).map((value) =>
            typeof value === "string" ? { event: value, type: "data" } : value,
          ),
        },
      };
      this.bo_emit(call, "enter", { status: "started" });
      return call;
    } catch {
      this.bo_errors++;
      return null;
    }
  }

  bo_emit(call, phase, values) {
    if (!call) return;
    try {
      const outputs = {
        duration_ms: Math.round((performance.now() - call.started) * 1000) / 1000,
        targets: call.targets,
        unknown_targets: call.unknown,
        target_source: call.targetSource,
        ...values,
      };
      if (call.transactionId) outputs.transaction_id = call.transactionId;
      const id = this.bo_probe.record(call.node, phase, () => ({ inputs: call.inputs, outputs }), {
        ...call.context,
        callId: call.callId,
      });
      const state = this.bo_events.getStore();
      if (id && state) state.last = id;
    } catch {
      this.bo_errors++;
    }
  }

  bo_summary(callback, value) {
    try {
      return callback ? bo_internal(() => callback(value)) : {};
    } catch {
      this.bo_errors++;
      return {};
    }
  }

  bo_finish(call, result, options) {
    if (!call) return;
    try {
      const summary = this.bo_summary(options.summarize, result) || {};
      const outputs = { status: "returned", rows_known: false };
      if (Number.isSafeInteger(summary.rows) && summary.rows >= 0) {
        outputs.rows = summary.rows;
        outputs.rows_known = true;
      }
      if (summary.result !== undefined)
        outputs.result = this.bo_select(
          summary.result,
          this.bo_operations.get(call.node).after || {},
        );
      this.bo_emit(call, "return", outputs);
    } catch {
      this.bo_errors++;
    }
  }

  /** A synchronous result, iterator, or cursor is returned with its exact identity. */
  execute(node, callback, options = {}) {
    const call = this.bo_allowed(options.connection) ? this.bo_begin(node, options) : null;
    try {
      const result = callback();
      this.bo_finish(call, result, options);
      return result;
    } catch (error) {
      this.bo_emit(call, "error", {
        status: "failed",
        error_type: error?.constructor?.name || "Error",
      });
      throw error;
    }
  }

  /** Use around the actual awaited driver call, not around a lazy query builder. */
  async executeAsync(node, callback, options = {}) {
    const call = this.bo_allowed(options.connection) ? this.bo_begin(node, options) : null;
    try {
      const result = await callback();
      this.bo_finish(call, result, options);
      return result;
    } catch (error) {
      this.bo_emit(call, "error", {
        status: "failed",
        error_type: error?.constructor?.name || "Error",
      });
      throw error;
    }
  }

  /** Snapshot selected values before an in-place or returning transformation. */
  transform(node, callback, value, options = {}) {
    const call = this.bo_allowed()
      ? this.bo_begin(node, { ...options, statement: "transform" })
      : null;
    const operation = this.bo_operations.get(node) || {};
    const before = call
      ? this.bo_select(this.bo_summary(options.before, value), operation.before || {})
      : {};
    const count = Array.isArray(value) ? value.length : null;
    try {
      const result = callback(value);
      if (call) {
        const outputs = {
          status: "transformed",
          before,
          result: this.bo_select(this.bo_summary(options.after, result), operation.after || {}),
        };
        if (count !== null) outputs.input_count = count;
        if (Array.isArray(result)) outputs.output_count = result.length;
        this.bo_emit(call, "change", outputs);
      }
      return result;
    } catch (error) {
      this.bo_emit(call, "error", {
        status: "failed",
        before,
        error_type: error?.constructor?.name || "Error",
      });
      throw error;
    }
  }

  /** Execute explicit native transaction functions; commit is observed after acknowledgement.
   * begin returns the driver's transaction/client. commit and rollback accept it.
   * callback must leave commit/rollback to this wrapper. The original application
   * error is preserved if rollback also fails; the event reports rollback_failed.
   */
  async transaction(node, { begin, commit, rollback }, callback, options = {}) {
    const call = this.bo_allowed(options.connection)
      ? this.bo_begin(node, { ...options, statement: "transaction" })
      : null;
    let resource,
      began = false,
      committing = false;
    try {
      resource = await begin();
      began = true;
      const result = await bo_context.run(
        { ...bo_context.getStore(), transactionId: call?.callId },
        () => callback(resource),
      );
      committing = true;
      await commit(resource);
      this.bo_emit(call, "commit", { status: "committed", committed: true });
      return result;
    } catch (error) {
      let rolledBack = false;
      if (began) {
        try {
          await rollback(resource);
          rolledBack = true;
        } catch {
          // The application error remains authoritative; rollback outcome is evidence.
        }
      }
      this.bo_emit(call, "error", {
        status: committing
          ? "commit_failed"
          : rolledBack
            ? "rolled_back"
            : began
              ? "rollback_failed"
              : "failed",
        ...(committing ? {} : { committed: false }),
        error_type: error?.constructor?.name || "Error",
      });
      throw error;
    }
  }
}

/** Export registered Mongoose model declarations without reading any stored document.
 * Only public Schema paths/indexes and collection names are read. Function-valued
 * validators and dynamic references are reported as unrepresented declarations.
 */
export function bo_mongoose_catalog(models, storeId) {
  const values = Array.isArray(models) ? models : Object.values(models);
  const collections = new Map(
    values.map((model) => [model.modelName, model.collection.collectionName]),
  );
  const limitations = new Set([
    "Custom validators and middleware are not represented by this catalog.",
  ]);
  const resources = values.map((model) => {
    const fields = [],
      constraints = [];
    const visit = (schema, prefix = "", depth = 0) => {
      if (depth > 6) {
        limitations.add("Nested schema depth exceeds six levels.");
        return;
      }
      schema.eachPath((path, type) => {
        const name = prefix + path;
        const declaredRequired = type.options?.required;
        const required = Array.isArray(declaredRequired) ? declaredRequired[0] : declaredRequired;
        const conditional = typeof required === "function";
        if (conditional) limitations.add("Conditional field requirements are not evaluated.");
        fields.push({
          name,
          native_type: String(type.instance || "unknown"),
          nullable: null,
          ...(conditional ? {} : { required: !!required }),
          ...(name === "_id" ? { primary_key: true } : {}),
        });
        const ref = type.options?.ref;
        if (typeof ref === "string" && collections.has(ref))
          constraints.push({
            kind: "foreign_key",
            name: `${name}_ref`,
            fields: [name],
            target: "collection:" + collections.get(ref),
            target_fields: ["_id"],
            description:
              "Declared Mongoose reference; not enforced by a MongoDB foreign-key constraint.",
          });
        else if (ref || type.options?.refPath)
          limitations.add("Dynamic or unregistered Mongoose references are not resolved.");
        if (type.schema) visit(type.schema, name + ".", depth + 1);
      });
    };
    visit(model.schema);
    for (const [keys, options] of model.schema.indexes())
      constraints.push({
        kind: options.unique ? "unique" : "index",
        name: options.name || Object.keys(keys).join("_"),
        fields: Object.keys(keys),
      });
    return {
      key: "collection:" + model.collection.collectionName,
      kind: "collection",
      name: model.collection.collectionName,
      fields,
      constraints,
    };
  });
  return {
    protocol: "bo-data-catalog/v1",
    store_id: storeId,
    engine: "mongodb",
    origin: "declaration",
    validation_scope: "application",
    coverage: "partial",
    limitations: [...limitations],
    resources,
  };
}
