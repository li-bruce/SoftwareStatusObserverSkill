/** Live native drivers, synthetic data, and actual commit/rollback effects. */
import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname } from "node:path";
import { parseArgs } from "node:util";
import { randomUUID } from "node:crypto";
import pg from "pg";
import mongoose from "mongoose";
import { createClient } from "redis";
import neo4j from "neo4j-driver";
import { BOProbe } from "../../skills/vibelens/scripts/bo_observer/adapters/javascript/bo_runtime.mjs";
import {
  BODataRuntime,
  bo_internal,
  bo_mongoose_catalog,
} from "../../skills/vibelens/scripts/bo_observer/adapters/javascript/bo_data.mjs";

function fixture(store) {
  const inputs = { operation: "string", statement: "string", parameters: { limit: "number" } };
  const outputs = {
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
  const operations = ["read", "write", "transform", "transaction"].map((id) => ({
    id,
    action: id,
    parameters: { limit: "number" },
    before: { count: "number" },
    after: { count: "number" },
  }));
  const project = {
    project_id: "native-live-" + store,
    model: {
      revision: "1",
      nodes: operations.map(({ id }) => ({ id, capture: { in: inputs, out: outputs } })),
    },
  };
  const events = [];
  const probe = new BOProbe({
    project,
    buildId: "native-live-1",
    sink: (body) => events.push(body),
  });
  return { events, probe, runtime: new BODataRuntime(probe, { operations }) };
}

async function finish(fixture, assertions, extra = {}) {
  const { probe, events } = fixture;
  assert.equal(await probe.flush(), true);
  assert.equal(probe.bo_errors, 0);
  assert.ok(events.some((event) => event.phase === "change"));
  assert.ok(events.some((event) => event.phase === "error"));
  for (const value of ["private_title_", "bo_test_local_only"])
    assert.equal(JSON.stringify(events).includes(value), false);
  for (const event of events.filter((event) => ["read", "write"].includes(event.node))) {
    assert.ok(event.outputs.targets.length);
    assert.equal(event.outputs.target_source, "provided");
  }
  return { status: "passed", assertions, ...extra, events };
}

async function postgres() {
  const client = new pg.Client({
    connectionString: (
      process.env.BO_TEST_POSTGRES_URL ||
      "postgresql://bo_test:bo_test_local_only@127.0.0.1:19432/bo_test"
    ).replace(/^postgresql\+[^:]+:/, "postgresql:"),
  });
  const test = fixture("postgresql"),
    bo = test.runtime;
  const table = "bo_native_" + randomUUID().replaceAll("-", "");
  await client.connect();
  const options = { connection: client, targets: ["table:public." + table] };
  try {
    await client.query(
      `CREATE TABLE ${table} (id integer PRIMARY KEY, title text, visible boolean)`,
    );
    await client.query(
      `INSERT INTO ${table} SELECT i, 'private_title_' || i, i % 2 = 0 FROM generate_series(1,4) AS i`,
    );
    await bo.operation("read", async () => {
      const result = await bo.executeAsync(
        "read",
        () => client.query(`SELECT * FROM ${table} ORDER BY id`),
        {
          ...options,
          statement: "SELECT",
          summarize: (result) => ({ rows: result.rowCount, result: { count: result.rows.length } }),
        },
      );
      const selected = bo.transform(
        "transform",
        (rows) => rows.filter((row) => row.visible),
        result.rows,
        {
          before: (rows) => ({ count: rows.length }),
          after: (rows) => ({ count: rows.length }),
          depends: [bo.lastEventId],
        },
      );
      assert.equal(selected.length, 2);
      const transaction = {
        begin: async () => {
          await client.query("BEGIN");
          return client;
        },
        commit: (connection) => connection.query("COMMIT"),
        rollback: (connection) => connection.query("ROLLBACK"),
      };
      await bo.transaction("transaction", transaction, async (connection) =>
        bo.executeAsync(
          "write",
          () =>
            connection.query(`UPDATE ${table} SET title=$1 WHERE id = ANY($2::integer[])`, [
              "private_title_updated",
              selected.map((row) => row.id),
            ]),
          { ...options, statement: "UPDATE", summarize: (result) => ({ rows: result.rowCount }) },
        ),
      );
      await assert.rejects(
        bo.transaction("transaction", transaction, async (connection) => {
          await bo.executeAsync(
            "write",
            () =>
              connection.query(`INSERT INTO ${table} VALUES (9,$1,false)`, [
                "private_title_rollback",
              ]),
            { ...options, statement: "INSERT" },
          );
          throw Error("synthetic rollback");
        }),
      );
      await assert.rejects(
        bo.executeAsync(
          "write",
          () => client.query(`INSERT INTO ${table} VALUES (1,'private_title_duplicate',false)`),
          { ...options, statement: "INSERT" },
        ),
      );
    });
    const result = await client.query(
      `SELECT COUNT(*)::integer AS total, COUNT(*) FILTER (WHERE title = 'private_title_updated')::integer AS changed FROM ${table}`,
    );
    assert.deepEqual(result.rows[0], { total: 4, changed: 2 });
    await test.probe.flush();
    const size = test.events.length;
    await bo_internal(() => bo.executeAsync("read", () => client.query("SELECT 1"), options));
    bo.excludeConnection(client);
    await bo.executeAsync("read", () => client.query("SELECT 1"), options);
    await test.probe.flush();
    assert.equal(test.events.length, size);
    assert.equal(test.events.filter((event) => event.phase === "commit").length, 1);
    return await finish(test, [
      "actual pg driver",
      "4-to-2 transformation",
      "two committed updates",
      "rollback leaves four rows",
      "duplicate-key failure",
      "observer exclusion",
    ]);
  } finally {
    await client.query(`DROP TABLE IF EXISTS ${table}`);
    await client.end();
  }
}

async function mongodb() {
  const connection = await mongoose
    .createConnection(process.env.BO_TEST_MONGODB_URL || "mongodb://127.0.0.1:19017/bo_test")
    .asPromise();
  const test = fixture("mongodb"),
    bo = test.runtime;
  const suffix = randomUUID().replaceAll("-", "");
  const Owner = connection.model(
    "Owner",
    new mongoose.Schema({ name: { type: String, required: true } }),
    "bo_owner_" + suffix,
  );
  const Image = connection.model(
    "Image",
    new mongoose.Schema({
      title: String,
      visible: Boolean,
      owner: { type: mongoose.Schema.Types.ObjectId, ref: "Owner", required: true },
    }),
    "bo_image_" + suffix,
  );
  const options = { connection, targets: ["collection:" + Image.collection.collectionName] };
  try {
    await Promise.all([Owner.init(), Image.init()]);
    const owner = await Owner.create({ name: "synthetic owner" });
    const originals = await Image.create(
      [1, 2, 3, 4].map((id) => ({
        title: "private_title_" + id,
        visible: id % 2 === 0,
        owner: owner._id,
      })),
    );
    const catalog = bo_mongoose_catalog({ Image, Owner }, "mongo");
    assert.equal(catalog.origin, "declaration");
    assert.equal(catalog.validation_scope, "application");
    const resource = catalog.resources.find(
      (item) => item.name === Image.collection.collectionName,
    );
    assert.ok(
      resource.constraints.some(
        (item) =>
          item.kind === "foreign_key" &&
          item.target === "collection:" + Owner.collection.collectionName,
      ),
    );
    await bo.operation("read", async () => {
      const rows = await bo.executeAsync("read", () => Image.find({}).lean().exec(), {
        ...options,
        statement: "find",
        summarize: (rows) => ({ rows: rows.length, result: { count: rows.length } }),
      });
      const selected = bo.transform(
        "transform",
        (rows) => rows.filter((row) => row.visible),
        rows,
        {
          before: (rows) => ({ count: rows.length }),
          after: (rows) => ({ count: rows.length }),
          depends: [bo.lastEventId],
        },
      );
      assert.equal(selected.length, 2);
      const updated = await bo.executeAsync(
        "write",
        () =>
          Image.updateMany(
            { _id: { $in: selected.map((row) => row._id) } },
            { $set: { title: "private_title_updated" } },
          ).exec(),
        {
          ...options,
          statement: "update",
          depends: [bo.lastEventId],
          summarize: (result) => ({ rows: result.modifiedCount }),
        },
      );
      assert.equal(updated.modifiedCount, 2);
      await assert.rejects(
        bo.executeAsync(
          "write",
          () =>
            Image.create({
              _id: originals[0]._id,
              title: "private_title_duplicate",
              owner: owner._id,
            }),
          { ...options, statement: "insert" },
        ),
      );
    });
    assert.equal(await Image.countDocuments({ title: "private_title_updated" }), 2);
    await test.probe.flush();
    const size = test.events.length;
    bo.excludeConnection(connection);
    await bo.executeAsync("read", () => Image.find({}).lean().exec(), options);
    await test.probe.flush();
    assert.equal(test.events.length, size);
    return await finish(
      test,
      [
        "actual Mongoose ODM",
        "public schema metadata export",
        "declared reference provenance",
        "4-to-2 transformation",
        "two documents updated",
        "duplicate-key failure",
        "exact connection exclusion",
      ],
      { catalog, limitations: ["Standalone MongoDB; multi-document transactions are not tested."] },
    );
  } finally {
    await Image.collection.drop();
    await Owner.collection.drop();
    await connection.close();
  }
}

async function redis() {
  const client = createClient({
    url: process.env.BO_TEST_REDIS_URL || "redis://127.0.0.1:19379/15",
  });
  client.on("error", () => {});
  await client.connect();
  const test = fixture("redis"),
    bo = test.runtime;
  const key = "bo:native:" + randomUUID();
  const options = { connection: client, targets: ["key_pattern:bo:native:*"] };
  try {
    await client.hSet(key, { 1: "approved", 2: "pending", 3: "approved", 4: "pending" });
    await bo.operation("read", async () => {
      const values = await bo.executeAsync("read", () => client.hGetAll(key), {
        ...options,
        statement: "HGETALL",
        summarize: (value) => ({ result: { count: Object.keys(value).length } }),
      });
      const selected = bo.transform(
        "transform",
        (rows) => rows.filter(([, value]) => value === "approved"),
        Object.entries(values),
        {
          before: (rows) => ({ count: rows.length }),
          after: (rows) => ({ count: rows.length }),
          depends: [bo.lastEventId],
        },
      );
      assert.equal(selected.length, 2);
      await bo.executeAsync(
        "write",
        () => client.hSet(key, Object.fromEntries(selected.map(([id]) => [id, "displayed"]))),
        { ...options, statement: "HSET", depends: [bo.lastEventId] },
      );
      await assert.rejects(
        bo.executeAsync("read", () => client.get(key), { ...options, statement: "GET" }),
      );
    });
    assert.equal(
      Object.values(await client.hGetAll(key)).filter((value) => value === "displayed").length,
      2,
    );
    await test.probe.flush();
    const size = test.events.length;
    await bo_internal(() => bo.executeAsync("read", () => client.hGetAll(key), options));
    await test.probe.flush();
    assert.equal(test.events.length, size);
    return await finish(
      test,
      [
        "actual redis driver",
        "4-to-2 transformation",
        "two hash fields updated",
        "wrong-type failure",
        "observer exclusion",
      ],
      {
        limitations: [
          "Redis EXEC and partial transaction errors are not claimed as rollback-capable.",
        ],
      },
    );
  } finally {
    await client.del(key);
    await client.quit();
  }
}

async function graph() {
  const endpoint = new URL(
    process.env.BO_TEST_NEO4J_URL || "bolt://neo4j:bo_test_local_only@127.0.0.1:19687",
  );
  const auth = neo4j.auth.basic(
    decodeURIComponent(endpoint.username),
    decodeURIComponent(endpoint.password),
  );
  endpoint.username = "";
  endpoint.password = "";
  const driver = neo4j.driver(endpoint.toString(), auth);
  const session = driver.session();
  const test = fixture("neo4j"),
    bo = test.runtime;
  const run = randomUUID(),
    options = { connection: session, targets: ["label:BONativeDataTest"] };
  try {
    await session.run(
      "UNWIND range(1,4) AS id CREATE (:BONativeDataTest {run:$run,id:id,title:'private_title_new',visible:id % 2 = 0})",
      { run },
    );
    await bo.operation("read", async () => {
      const query = await bo.executeAsync(
        "read",
        () =>
          session.run(
            "MATCH (n:BONativeDataTest {run:$run}) RETURN n.id AS id,n.visible AS visible",
            { run },
          ),
        {
          ...options,
          statement: "MATCH",
          summarize: (result) => ({ rows: result.records.length }),
        },
      );
      const selected = bo.transform(
        "transform",
        (records) => records.filter((row) => row.get("visible")),
        query.records,
        {
          before: (records) => ({ count: records.length }),
          after: (records) => ({ count: records.length }),
          depends: [bo.lastEventId],
        },
      );
      assert.equal(selected.length, 2);
      const transaction = {
        begin: () => session.beginTransaction(),
        commit: (tx) => tx.commit(),
        rollback: (tx) => tx.rollback(),
      };
      await bo.transaction("transaction", transaction, (tx) =>
        bo.executeAsync(
          "write",
          () =>
            tx.run(
              "MATCH (n:BONativeDataTest {run:$run}) WHERE n.id IN $ids SET n.title='private_title_updated' RETURN n.id",
              { run, ids: selected.map((row) => row.get("id")) },
            ),
          {
            ...options,
            statement: "MATCH",
            summarize: (result) => ({ rows: result.records.length }),
          },
        ),
      );
      await assert.rejects(
        bo.transaction("transaction", transaction, async (tx) => {
          await bo.executeAsync(
            "write",
            () => tx.run("CREATE (:BONativeDataTest {run:$run,id:9})", { run }),
            { ...options, statement: "CREATE" },
          );
          throw Error("synthetic rollback");
        }),
      );
      await assert.rejects(
        bo.executeAsync("read", () => session.run("MATCH ??? invalid"), {
          ...options,
          statement: "MATCH",
        }),
      );
    });
    assert.equal(
      (
        await session.run("MATCH (n:BONativeDataTest {run:$run}) RETURN count(n) AS count", { run })
      ).records[0]
        .get("count")
        .toNumber(),
      4,
    );
    assert.equal(
      (
        await session.run(
          "MATCH (n:BONativeDataTest {run:$run}) WHERE n.title='private_title_updated' RETURN count(n) AS count",
          { run },
        )
      ).records[0]
        .get("count")
        .toNumber(),
      2,
    );
    return await finish(test, [
      "actual neo4j driver",
      "4-to-2 transformation",
      "two graph nodes updated",
      "commit acknowledgement",
      "rollback leaves four nodes",
      "Cypher syntax failure",
    ]);
  } finally {
    await session.run("MATCH (n:BONativeDataTest {run:$run}) DETACH DELETE n", { run });
    await session.close();
    await driver.close();
  }
}

const databases = {};
for (const [name, run] of [
  ["postgresql", postgres],
  ["mongodb", mongodb],
  ["redis", redis],
  ["neo4j", graph],
]) {
  try {
    databases[name] = await run();
  } catch (error) {
    databases[name] = {
      status: "failed",
      error_type: error.constructor.name,
      code: error.code || null,
    };
  }
  console.log(
    JSON.stringify({
      database: name,
      status: databases[name].status,
      events: databases[name].events?.length,
      error_type: databases[name].error_type,
    }),
  );
}
const status = Object.values(databases).every((item) => item.status === "passed")
  ? "passed"
  : "failed";
const { values } = parseArgs({
  options: {
    out: {
      type: "string",
      default: fileURLToPath(
        new URL("../../.validation/database-native-live.json", import.meta.url),
      ),
    },
  },
});
await mkdir(dirname(values.out), { recursive: true });
await writeFile(values.out, JSON.stringify({ status, databases }, null, 2) + "\n");
process.exitCode = status === "passed" ? 0 : 1;
