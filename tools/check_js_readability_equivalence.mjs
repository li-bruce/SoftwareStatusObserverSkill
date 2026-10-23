/** Compare maintained JavaScript syntax with a Git revision before readability edits. */
import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";

const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const { values } = parseArgs({
  options: { base: { type: "string" }, out: { type: "string" } },
});
if (!values.base) throw Error("Pass --base <commit> to select the comparison revision.");
const adapter = "skills/business-observer/scripts/bo_observer/adapters/javascript/";
const viewer = "skills/business-observer/assets/stategraph-viewer/";
const require = createRequire(path.join(root, adapter, "package.json"));
const ts = require("typescript");
const vendor = new Set(["pixi.min.js", "elk.bundled.js", "elk-worker.min.js"]);
const files = [
  ...fs
    .readdirSync(path.join(root, viewer))
    .filter((name) => name.endsWith(".js") && !vendor.has(name))
    .map((name) => viewer + name),
  ...fs
    .readdirSync(path.join(root, adapter))
    .filter((name) => name.endsWith(".mjs"))
    .map((name) => adapter + name),
];

/** Retain token values and child order; discard comments, positions, and grouping. */
function syntax(source, name) {
  const tree = ts.createSourceFile(name, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.JS);
  if (tree.parseDiagnostics.length) throw Error("Invalid source: " + name);
  function normalize(node) {
    if (ts.isParenthesizedExpression(node)) return normalize(node.expression);
    const children = [];
    ts.forEachChild(node, (child) => {
      children.push(normalize(child));
    });
    // SourceFile.text contains comments and whitespace; literal text carries semantics.
    const text = ts.isSourceFile(node)
      ? undefined
      : ts.isNumericLiteral(node)
        ? Number(node.text)
        : (node.text ?? node.escapedText);
    return { kind: ts.SyntaxKind[node.kind], ...(text === undefined ? {} : { text }), children };
  }
  return JSON.stringify(normalize(tree));
}

const changes = files.filter((name) => {
  const before = execFileSync("git", ["show", values.base + ":" + name], {
    cwd: root,
    encoding: "utf8",
    maxBuffer: 10 * 1024 * 1024,
  });
  return syntax(before, name) !== syntax(fs.readFileSync(path.join(root, name), "utf8"), name);
});
const result = {
  base: values.base,
  javascript_modules: files.length,
  executable_ast_changes: changes,
  valid: changes.length === 0,
  scope: "TypeScript syntax trees; comments, source locations and redundant parentheses excluded",
};
const output = JSON.stringify(result, null, 2) + "\n";
if (values.out) fs.writeFileSync(values.out, output);
process.stdout.write(output);
process.exitCode = result.valid ? 0 : 1;
