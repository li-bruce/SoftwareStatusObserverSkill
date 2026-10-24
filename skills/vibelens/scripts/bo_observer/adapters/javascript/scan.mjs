// Parse source only: no import, evaluation, build or execution of application code.
import { createHash } from "node:crypto";
import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";
import path from "node:path";
const bo_require = createRequire(
  process.env.BO_ADAPTER_HOME
    ? pathToFileURL(path.join(process.env.BO_ADAPTER_HOME, "package.json"))
    : import.meta.url,
);
const ts = bo_require("typescript"),
  { parse: parseVue } = bo_require("@vue/compiler-sfc");
if (ts.version !== "5.9.3" || bo_require("@vue/compiler-sfc/package.json").version !== "3.5.22")
  throw Error("Adapter dependency versions differ from package-lock.json");

const hash = (text) => createHash("sha256").update(text).digest("hex");
const printer = ts.createPrinter({ removeComments: true, newLine: ts.NewLineKind.LineFeed });
const functionLike = (n) =>
  ts.isFunctionDeclaration(n) ||
  ts.isFunctionExpression(n) ||
  ts.isArrowFunction(n) ||
  ts.isMethodDeclaration(n) ||
  ts.isGetAccessorDeclaration(n) ||
  ts.isSetAccessorDeclaration(n) ||
  ts.isConstructorDeclaration(n);
const routeNames = new Set(["get", "post", "put", "patch", "delete", "route", "websocket"]);

/** Extract declarations, parameters, call sites, and frontend handlers from one source file. */
function parseUnit(path, original) {
  let source = original,
    template;
  if (path.endsWith(".vue")) {
    const parsed = parseVue(original, { filename: path });
    if (parsed.errors.length) throw Error(parsed.errors.map(String).join("; "));
    const blocks = [parsed.descriptor.script, parsed.descriptor.scriptSetup].filter(Boolean);
    if (blocks.some((b) => b.src))
      throw Error("External Vue script requires an explicit source binding");
    if (blocks.some((b) => b.lang && !["js", "ts", "jsx", "tsx"].includes(b.lang)))
      throw Error("Unsupported Vue script language");
    // Use UTF-16 offsets, the same units used by the compiler and SFC parser.
    source = original.replace(/[^\r\n]/g, " ");
    for (const b of blocks)
      source = source.slice(0, b.loc.start.offset) + b.content + source.slice(b.loc.end.offset);
    template = parsed.descriptor.template;
  }
  const kind = /\.(tsx|jsx)$/.test(path)
    ? ts.ScriptKind.TSX
    : /\.(ts|mts|cts|vue)$/.test(path)
      ? ts.ScriptKind.TS
      : ts.ScriptKind.JS;
  const sf = ts.createSourceFile(path, source, ts.ScriptTarget.Latest, true, kind);
  if (sf.parseDiagnostics.length)
    throw Error(
      sf.parseDiagnostics
        .map((d) => ts.flattenDiagnosticMessageText(d.messageText, " "))
        .join("; "),
    );
  const text = (n) => (n ? n.getText(sf) : "");
  const line = (n) => sf.getLineAndCharacterOfPosition(n.getStart(sf)).line + 1;
  const imports = {},
    symbols = {},
    entries = new Map(),
    names = new Map();
  const counts = new Map();
  function bindingNames(name) {
    if (ts.isIdentifier(name)) return [name.text];
    if (ts.isObjectBindingPattern(name) || ts.isArrayBindingPattern(name))
      return name.elements.flatMap((entry) =>
        ts.isBindingElement(entry) ? bindingNames(entry.name) : [],
      );
    return [];
  }
  function nameOf(n, owner) {
    if (ts.isConstructorDeclaration(n)) return "constructor";
    if (n.name) return text(n.name).replace(/^['"]|['"]$/g, "");
    if (ts.isVariableDeclaration(n.parent) || ts.isPropertyAssignment(n.parent))
      return text(n.parent.name);
    if (ts.isExportAssignment(n.parent)) return "default";
    const call = n.parent;
    const slot = ts.isCallExpression(call)
      ? `${text(call.expression)}:${call.arguments.indexOf(n)}`
      : "anonymous";
    const base = `${owner}.<callback:${slot}>`,
      count = (counts.get(base) || 0) + 1;
    counts.set(base, count);
    return `<callback:${slot}:${count}>`;
  }
  function register(n, owner = "", className = null) {
    // CommonJS declarations share import facts with ES modules. Dynamic require
    // expressions remain unresolved rather than executing a module to discover it.
    if (
      !owner &&
      ts.isVariableDeclaration(n) &&
      n.initializer &&
      ts.isCallExpression(n.initializer) &&
      text(n.initializer.expression) === "require" &&
      n.initializer.arguments.length === 1 &&
      ts.isStringLiteral(n.initializer.arguments[0])
    ) {
      const module = n.initializer.arguments[0].text;
      if (ts.isIdentifier(n.name)) imports[n.name.text] = { module, name: "*" };
      if (ts.isObjectBindingPattern(n.name))
        for (const entry of n.name.elements)
          if (ts.isIdentifier(entry.name))
            imports[entry.name.text] = { module, name: text(entry.propertyName || entry.name) };
    }
    if (ts.isImportDeclaration(n) && ts.isStringLiteral(n.moduleSpecifier)) {
      const from = n.moduleSpecifier.text,
        clause = n.importClause;
      if (!clause) imports[`<side-effect:${n.pos}>`] = { module: from, name: "*" };
      if (clause?.name) imports[clause.name.text] = { module: from, name: "default" };
      const b = clause?.namedBindings;
      if (b && ts.isNamespaceImport(b)) imports[b.name.text] = { module: from, name: "*" };
      if (b && ts.isNamedImports(b))
        for (const e of b.elements)
          imports[e.name.text] = { module: from, name: (e.propertyName || e.name).text };
    }
    if (ts.isObjectLiteralExpression(n)) {
      let part;
      if (ts.isVariableDeclaration(n.parent) || ts.isPropertyAssignment(n.parent))
        part = text(n.parent.name);
      else {
        const key = owner + ".<object>",
          count = (counts.get(key) || 0) + 1;
        counts.set(key, count);
        part = `<object:${count}>`;
      }
      const nested = owner ? `${owner}.${part}` : part;
      names.set(n, nested);
      ts.forEachChild(n, (child) => register(child, nested, className));
      return;
    }
    if (functionLike(n) && !n.body) return; // overload/ambient signature, not executable source
    if (functionLike(n) || ts.isClassDeclaration(n) || ts.isClassExpression(n)) {
      const own = nameOf(n, owner),
        name = owner ? `${owner}.${own}` : own;
      if (symbols[name]) throw Error(`Ambiguous source identity: ${name}`);
      const isClass = ts.isClassDeclaration(n) || ts.isClassExpression(n);
      const printed = printer.printNode(ts.EmitHint.Unspecified, n, sf);
      const item = {
        id: `${path}::${name}`,
        path,
        symbol: name,
        kind: isClass ? "class" : "function",
        class: className,
        language: path.endsWith(".vue")
          ? "vue"
          : kind === ts.ScriptKind.TSX
            ? "tsx"
            : kind === ts.ScriptKind.TS
              ? "typescript"
              : "javascript",
        line: line(n),
        end_line: sf.getLineAndCharacterOfPosition(n.end).line + 1,
        ast_hash: hash(printed),
        signature: isClass ? name : (n.parameters || []).map(text).join(", "),
        parameters: (n.parameters || []).map((p) => ({
          name: text(p.name),
          annotation: p.type ? text(p.type) : null,
        })),
        returns: n.type ? text(n.type) : null,
        calls: [],
        predicates: [],
        fields: [],
        bases: isClass
          ? (n.heritageClauses || []).flatMap((c) => c.types.map((v) => text(v.expression)))
          : [],
        entrypoints: [],
        local_names: (n.parameters || []).flatMap((p) => bindingNames(p.name)),
        role:
          !isClass && /^[A-Z]/.test(own) && kind === ts.ScriptKind.TSX ? "component" : undefined,
      };
      symbols[name] = item;
      names.set(n, name);
      if (isClass)
        for (const member of n.members)
          if (ts.isPropertyDeclaration(member))
            item.fields.push({
              name: text(member.name),
              type: member.type ? text(member.type) : null,
              value: member.initializer ? text(member.initializer) : null,
            });
      function body(part) {
        if (
          part !== n &&
          (functionLike(part) || ts.isClassDeclaration(part) || ts.isClassExpression(part))
        )
          return;
        if (ts.isCallExpression(part) || ts.isNewExpression(part)) {
          const args = [...(part.arguments || [])],
            loc = sf.getLineAndCharacterOfPosition(part.getStart(sf));
          const c = {
            expression: text(part.expression),
            line: loc.line + 1,
            column: loc.character,
            args: args.map(text),
            keywords: {},
          };
          if (args.length >= 2 && args.slice(0, 2).every(ts.isStringLiteral))
            c.literal_pair = args.slice(0, 2).map((a) => a.text);
          item.calls.push(c);
        }
        if (ts.isIfStatement(part) || ts.isConditionalExpression(part))
          item.predicates.push({
            line: line(part),
            expression: text(part.expression || part.condition),
          });
        if (ts.isVariableDeclaration(part)) item.local_names.push(...bindingNames(part.name));
        ts.forEachChild(part, body);
      }
      if (!isClass) body(n);
      ts.forEachChild(n, (child) => register(child, name, isClass ? name : className));
      return;
    }
    ts.forEachChild(n, (child) => register(child, owner, className));
  }
  register(sf);
  function addEntry(node, label) {
    let parent = node.parent,
      owner;
    while (parent && !owner) {
      owner = names.get(parent);
      parent = parent.parent;
    }
    const local = ts.isIdentifier(node) ? node.text : null;
    const name =
      names.get(node) || (owner && symbols[`${owner}.${local}`] ? `${owner}.${local}` : local);
    if (name && symbols[name]) symbols[name].entrypoints.push(label);
    if (label.startsWith("jsx:") && owner && symbols[owner] && name && symbols[name])
      symbols[owner].calls.push({
        expression: local || name,
        line: line(node),
        column: sf.getLineAndCharacterOfPosition(node.getStart(sf)).character,
        args: [],
        keywords: {},
      });
  }
  function routes(n) {
    if (
      ts.isCallExpression(n) &&
      ts.isPropertyAccessExpression(n.expression) &&
      n.expression.name.text === "addEventListener"
    ) {
      if (n.arguments[1]) addEntry(n.arguments[1], `dom:${text(n.arguments[0])}`);
    }
    if (
      ts.isBinaryExpression(n) &&
      n.operatorToken.kind === ts.SyntaxKind.EqualsToken &&
      ts.isPropertyAccessExpression(n.left) &&
      /^on[a-z]+$/.test(n.left.name.text)
    )
      addEntry(n.right, `dom:${n.left.name.text}`);
    if (
      ts.isCallExpression(n) &&
      ts.isPropertyAccessExpression(n.expression) &&
      routeNames.has(n.expression.name.text)
    ) {
      const [pathNode, ...handlers] = n.arguments;
      if (pathNode)
        for (const h of handlers) addEntry(h, `${text(n.expression)}(${text(pathNode)})`);
    }
    if (
      ts.isJsxAttribute(n) &&
      /^on[A-Z]/.test(text(n.name)) &&
      n.initializer &&
      ts.isJsxExpression(n.initializer) &&
      n.initializer.expression
    )
      addEntry(n.initializer.expression, `jsx:${text(n.name)}`);
    ts.forEachChild(n, routes);
  }
  routes(sf);
  if (template) {
    // The template is a real source symbol, so inline UI logic cannot disappear
    // from coverage. SFC supplies its actual source range; no inferred runtime.
    const tname = "<template>",
      base = template.loc.start.line;
    const item = {
      id: `${path}::${tname}`,
      path,
      symbol: tname,
      kind: "function",
      class: null,
      language: "vue",
      role: "template",
      line: base,
      end_line: template.loc.end.line,
      ast_hash: hash(template.content),
      signature: "template",
      parameters: [],
      returns: null,
      calls: [],
      predicates: [],
      fields: [],
      entrypoints: ["vue:template"],
      local_names: [],
    };
    const ast = template.ast;
    function templateWalk(n) {
      for (const p of n.props || [])
        if (p.type === 7 && p.exp?.content) {
          const expr = p.exp.content;
          if (p.name === "on") {
            const expression = /^[\w$.]+$/.test(expr.trim()) ? expr.trim() : null;
            if (expression)
              item.calls.push({
                expression,
                line: p.loc.start.line,
                column: p.loc.start.column - 1,
                args: [],
                keywords: {},
              });
            else item.predicates.push({ line: p.loc.start.line, expression: expr });
          }
        }
      for (const child of n.children || []) templateWalk(child);
    }
    if (ast) templateWalk(ast);
    symbols[tname] = item;
  }
  // Top-level side effects are not all function declarations. Keep their source
  // identity so registration/initialization code is explicitly classified too.
  const effects = sf.statements.filter(
    (n) =>
      !ts.isImportDeclaration(n) &&
      !ts.isInterfaceDeclaration(n) &&
      !ts.isTypeAliasDeclaration(n) &&
      !ts.isFunctionDeclaration(n) &&
      !ts.isClassDeclaration(n),
  );
  if (effects.length) {
    const calls = [];
    function top(n) {
      if (functionLike(n) || ts.isClassExpression(n)) return;
      if (ts.isCallExpression(n))
        calls.push({
          expression: text(n.expression),
          line: line(n),
          column: sf.getLineAndCharacterOfPosition(n.getStart(sf)).character,
          args: n.arguments.map(text),
          keywords: {},
        });
      ts.forEachChild(n, top);
    }
    effects.forEach(top);
    if (calls.length)
      symbols["<module>"] = {
        id: `${path}::<module>`,
        path,
        symbol: "<module>",
        kind: "function",
        class: null,
        language: "javascript",
        role: "initialization",
        line: 1,
        end_line: original.split("\n").length,
        ast_hash: hash(
          effects.map((n) => printer.printNode(ts.EmitHint.Unspecified, n, sf)).join("\n"),
        ),
        signature: "module",
        parameters: [],
        returns: null,
        calls,
        predicates: [],
        fields: [],
        entrypoints: [],
        local_names: [],
      };
  }
  return {
    imports,
    symbols,
    declarations: [],
    shadowed_globals: [],
    language: "javascript",
    adapter: `typescript@${ts.version};vue@3.5.22`,
  };
}

// Pipes can be nonblocking and arrive in several writes. Decode only after EOF
// so a split UTF-8 character and a temporary lack of data are both handled.
const input = [];
for await (const chunk of process.stdin) input.push(chunk);
const request = JSON.parse(Buffer.concat(input).toString("utf8"));
const units = {},
  errors = [];
for (const file of request.files) {
  try {
    units[file.path] = parseUnit(file.path, file.source);
  } catch (error) {
    errors.push({ path: file.path, error: String(error.message || error) });
  }
}
process.stdout.write(JSON.stringify({ units, errors }));
