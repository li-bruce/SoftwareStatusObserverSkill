/** Native callback/capture contracts. Real server acceptance lives in the live database suite. */
import assert from "node:assert/strict";
import { BOProbe } from "../skills/vibelens/scripts/bo_observer/adapters/javascript/bo_runtime.mjs";
import {
  BODataRuntime,
  bo_internal,
  bo_command_shape,
} from "../skills/vibelens/scripts/bo_observer/adapters/javascript/bo_data.mjs";

const input = { operation: "string", statement: "string", parameters: { limit: "number" } };
const output = {
  status: "string",
  duration_ms: "number",
  rows: "number",
  rows_known: "boolean",
  target_source: "string",
  result: { count: "number" },
  before: { count: "number" },
  error_type: "string",
  transaction_id: "string",
  targets: ["string"],
  unknown_targets: ["string"],
  input_count: "number",
  output_count: "number",
  committed: "boolean",
};
const project = {
  project_id: "native-data-test",
  model: {
    revision: "1",
    nodes: ["query", "transform", "transaction"].map((id) => ({
      id,
      capture: { in: input, out: output },
    })),
  },
};
const config = {
  operations: [
    { id: "query", action: "read", parameters: { limit: "number" }, after: { count: "number" } },
    {
      id: "transform",
      action: "transform",
      before: { count: "number" },
      after: { count: "number" },
    },
    { id: "transaction", action: "transaction" },
  ],
};
let events = [],
  bo;
const probe = new BOProbe({
  project,
  buildId: "build-1",
  sink: async (body) => {
    events.push(body);
    await Promise.resolve();
    // After-await transport activity must remain excluded, without an event loop.
    await bo.executeAsync("query", async () => 1, { statement: "internal" });
  },
});
bo = new BODataRuntime(probe, config);

let consumed = false;
function* rows() {
  consumed = true;
  yield "private value";
}
const cursor = rows();
assert.equal(
  bo.execute("query", () => cursor, { statement: "find", targets: ["collection:image"] }),
  cursor,
);
assert.equal(consumed, false);
assert.equal(cursor.next().value, "private value");

const result = { count: 2, password: "private password" };
assert.equal(
  await bo.executeAsync("query", async () => result, {
    statement: "SELECT * FROM image WHERE title = 'private title'",
    parameters: { limit: 2, password: "secret" },
    targets: ["table:image"],
    summarize: (value) => ({ rows: value.count, result: value }),
  }),
  result,
);
assert.equal(bo_command_shape("SELECT 'secret'"), "[query text omitted]");

await Promise.all(
  ["a", "b"].map((entity) =>
    bo.operation(
      "query",
      async () => {
        await bo.executeAsync(
          "query",
          async () => {
            await Promise.resolve();
            return entity;
          },
          { statement: "get" },
        );
        const dependency = bo.lastEventId;
        assert.ok(dependency);
        const values = [1, 2, 3];
        assert.equal(
          bo.transform(
            "transform",
            (items) => {
              items.pop();
              return items;
            },
            values,
            {
              before: (items) => ({ count: items.length }),
              after: (items) => ({ count: items.length }),
              depends: [dependency],
            },
          ),
          values,
        );
      },
      { entity },
    ),
  ),
);

const connection = {};
bo.excludeConnection(connection);
bo.execute("query", () => 7, { connection });
await bo_internal(async () => {
  await Promise.resolve();
  bo.execute("query", () => 9);
});

const fault = new Error("private application failure");
assert.throws(
  () =>
    bo.execute("query", () => {
      throw fault;
    }),
  (error) => error === fault,
);
const beforeErrors = bo.bo_errors;
assert.equal(
  bo.execute("query", () => 42, {
    summarize: () => {
      throw Error("collector");
    },
  }),
  42,
);
assert.equal(bo.bo_errors, beforeErrors + 1);

const order = [];
const transaction = {
  begin: async () => {
    order.push("begin");
    return connection;
  },
  commit: async () => {
    order.push("commit");
  },
  rollback: async () => {
    order.push("rollback");
  },
};
assert.equal(
  await bo.transaction("transaction", transaction, async (received) => {
    assert.equal(received, connection);
    order.push("body");
    return result;
  }),
  result,
);
assert.deepEqual(order, ["begin", "body", "commit"]);
await assert.rejects(
  bo.transaction("transaction", transaction, async () => {
    throw fault;
  }),
  (error) => error === fault,
);
assert.equal(order.at(-1), "rollback");
await assert.rejects(
  bo.transaction(
    "transaction",
    {
      ...transaction,
      commit: async () => {
        throw fault;
      },
    },
    async () => result,
  ),
  (error) => error === fault,
);
await assert.rejects(
  bo.transaction(
    "transaction",
    {
      ...transaction,
      rollback: async () => {
        throw Error("rollback");
      },
    },
    async () => {
      throw fault;
    },
  ),
  (error) => error === fault,
);

assert.equal(await probe.flush(), true);
assert.equal(probe.bo_errors, 0);
assert.ok(bo.bo_suppressed > 0);
const serialized = JSON.stringify(events);
for (const secret of [
  "private value",
  "private title",
  "private password",
  "secret",
  "private application failure",
])
  assert.ok(!serialized.includes(secret));
assert.equal(events[1].outputs.rows_known, false);
assert.equal(events[3].outputs.rows, 2);
assert.deepEqual(events[3].outputs.result, { count: 2 });
for (const entity of ["a", "b"]) {
  const changes = events.filter((event) => event.entity === entity && event.phase === "change");
  assert.equal(changes.length, 1);
  assert.equal(changes[0].outputs.before.count, 3);
  assert.equal(changes[0].outputs.input_count, 3);
  assert.equal(changes[0].outputs.output_count, 2);
  assert.ok(
    events.some(
      (event) =>
        event.entity === entity &&
        changes[0].depends.some(
          (dependency) => dependency.event === event.id && dependency.type === "data",
        ),
    ),
  );
}
assert.equal(events.filter((event) => event.phase === "commit").length, 1);
assert.equal(events.at(-1).outputs.status, "rollback_failed");
const commitFailure = events.find((event) => event.outputs.status === "commit_failed");
assert.ok(commitFailure);
assert.equal(Object.hasOwn(commitFailure.outputs, "committed"), false);
console.log(
  JSON.stringify({
    status: "passed",
    checks: 33,
    events: events.length,
    suppressed: bo.bo_suppressed,
  }),
);
