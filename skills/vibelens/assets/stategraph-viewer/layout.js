import { t as boTranslate } from "./i18n.js";
// Layout preferences are local view data. They never change model or runtime facts.
import { graphBounds, nodeType, nodeTypes, viewTypes, relationType } from "./graph-core.js";
import { dataRelations, migrateDataFilters } from "./data-layer.js";
import { codeRelations, migrateCodeFilters } from "./code-layer.js";
export const layoutKey = (model, projectId) =>
  "business-observer.layout.v2:" +
  (projectId ||
    model.project_id ||
    model.presentation?.layout_id ||
    model.presentation?.subject ||
    model.intent);
export function emptyFilters() {
  return {
    dataTypes: 1,
    codeTypes: 1,
    nodes: Object.keys(nodeTypes),
    edges: [
      "call",
      "flow",
      "transition",
      "guard",
      "data",
      "resource",
      "join",
      "shared",
      "other",
      ...dataRelations,
      ...codeRelations,
    ],
    regions: Object.keys(nodeTypes),
    depth: "all",
    hiddenNodes: [],
    hiddenEdges: [],
  };
}
export function cleanFilters(value) {
  value = migrateCodeFilters(migrateDataFilters(value));
  const clean = emptyFilters();
  for (const kind of ["nodes", "edges", "regions"])
    if (Array.isArray(value?.[kind]))
      clean[kind] = [...new Set(value[kind].filter((type) => clean[kind].includes(type)))];
  if (Number.isInteger(value?.depth) && value.depth >= 0 && value.depth < 100)
    clean.depth = value.depth;
  for (const field of ["hiddenNodes", "hiddenEdges"])
    if (Array.isArray(value?.[field]))
      clean[field] = [...new Set(value[field].filter((id) => typeof id === "string" && id.length))];
  return clean;
}
export function emptyLayout() {
  return {
    schema: 2,
    positions: Object.create(null),
    expanded: [],
    camera: null,
    algorithm: "cluster",
    annotations: Object.create(null),
    focus: null,
    filters: emptyFilters(),
  };
}
/** Carry saved positions and annotations across explicitly declared node ID changes. */
export function migrateNodeIds(state, aliases = {}, edgeAliases = {}) {
  // Explicit one-to-one renames only. Keep both records on a conflict.
  const targets = Object.values(aliases),
    migrated = Object.create(null);
  for (const [from, to] of Object.entries(aliases)) {
    if (
      typeof to !== "string" ||
      from === to ||
      targets.filter((x) => x === to).length !== 1 ||
      aliases[to]
    )
      continue;
    if (state.positions?.[to] || state.annotations?.[to]) continue;
    for (const field of ["positions", "annotations"])
      if (state[field]?.[from]) {
        state[field][to] = state[field][from];
        delete state[field][from];
      }
    state.expanded = (state.expanded || []).map((id) => (id === from ? to : id));
    if (state.filters?.hiddenNodes)
      state.filters.hiddenNodes = state.filters.hiddenNodes.map((id) => (id === from ? to : id));
    if (state.focus === from) state.focus = to;
    migrated[from] = to;
  }
  if (state.filters?.hiddenEdges)
    state.filters.hiddenEdges = state.filters.hiddenEdges.map((id) => {
      const target = edgeAliases[id];
      return typeof target === "string" &&
        target &&
        !edgeAliases[target] &&
        Object.values(edgeAliases).filter((value) => value === target).length === 1
        ? target
        : id;
    });
  return migrated;
}
const coordinate = (n) => typeof n === "number" && Number.isFinite(n) && Math.abs(n) < 1e7;
function cleanText(value, limit, multiline = false) {
  if (typeof value !== "string") return "";
  const cleaned = value
    .replace(
      multiline ? /[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/g : /[\u0000-\u001f\u007f]/g,
      " ",
    )
    .trim();
  return [...cleaned].slice(0, limit).join("");
}
export function annotationFor(state, id) {
  return state.annotations?.[id] || { label: "", note: "", core: false };
}
export function displayName(node, state) {
  return annotationFor(state, node.referenceOf || node.id).label || node.label;
}
// Search the complete model, including nodes hidden by a collapsed parent.
export function searchNodes(all, state, query, limit = 20) {
  const normalize = (value) =>
    String(value || "")
      .normalize("NFKC")
      .toLocaleLowerCase();
  const terms = normalize(query).trim().split(/\s+/).filter(Boolean);
  if (!terms.length) return [];
  return [...all.values()]
    .map((node) => {
      const annotation = annotationFor(state, node.id),
        name = displayName(node, state);
      const primary = normalize([name, node.label, node.id].join(" "));
      const haystack = normalize(
        [
          primary,
          annotation.note,
          node.kind,
          node.field,
          node.fieldType,
          node.data_role,
          node.data_store,
          node.data_key,
          node.data_metadata?.native_type,
          node.source?.path,
          node.source?.symbol,
        ].join(" "),
      );
      return {
        node,
        name,
        score: terms.every((term) => primary.includes(term)) ? 0 : 1,
        match: terms.every((term) => haystack.includes(term)),
      };
    })
    .filter((entry) => entry.match)
    .sort((a, b) => a.score - b.score || a.node.id.localeCompare(b.node.id))
    .slice(0, limit);
}
export function ancestorsToReveal(all, id) {
  const parents = [],
    seen = new Set([id]);
  let parent = all.get(id)?.parent;
  while (parent && all.has(parent) && !seen.has(parent)) {
    parents.push(parent);
    seen.add(parent);
    parent = all.get(parent)?.parent;
  }
  return parents;
}
export function setAnnotation(state, id, value) {
  if (typeof id !== "string" || !id) return;
  const annotation = {
    label: cleanText(value?.label, 80),
    note: cleanText(value?.note, 500, true),
    core: value?.core === true,
  };
  state.annotations ||= Object.create(null);
  if (annotation.label || annotation.note || annotation.core) state.annotations[id] = annotation;
  else delete state.annotations[id];
  return annotation;
}
export function readLayout(storage, key) {
  const clean = emptyLayout();
  try {
    const value = JSON.parse(storage.getItem(key));
    if (value?.schema !== 2) return { state: clean, available: true, restored: false };
    for (const [id, p] of Object.entries(value.positions || {}))
      if (coordinate(p?.x) && coordinate(p?.y))
        clean.positions[id] = { x: p.x, y: p.y, pinned: p.pinned === true };
    clean.expanded = Array.isArray(value.expanded)
      ? value.expanded.filter((x) => typeof x === "string")
      : [];
    if (
      value.annotations &&
      typeof value.annotations === "object" &&
      !Array.isArray(value.annotations)
    )
      for (const [id, annotation] of Object.entries(value.annotations))
        setAnnotation(clean, id, annotation);
    clean.focus = typeof value.focus === "string" ? value.focus : null;
    clean.filters = cleanFilters(value.filters);
    if (["cluster", "layered", "stress"].includes(value.algorithm))
      clean.algorithm = value.algorithm;
    if (
      coordinate(value.camera?.x) &&
      coordinate(value.camera?.y) &&
      value.camera.scale >= 0.12 &&
      value.camera.scale <= 3
    )
      clean.camera = value.camera;
    return { state: clean, available: true, restored: true };
  } catch {
    return { state: clean, available: false, restored: false };
  }
}
export function writeLayout(storage, key, state) {
  try {
    storage.setItem(key, JSON.stringify(state));
    return true;
  } catch {
    return false;
  }
}
// Containment is independent of calls, state transitions and runtime evidence.
export function hierarchyOf(graph) {
  const parents = new Map(),
    children = new Map(),
    depths = new Map();
  for (const b of graph.boxes) {
    const chain = ancestorsToReveal(graph.all, b.id);
    // Malformed parent cycles must not hang layout or invent a valid hierarchy.
    if (chain.some((id) => graph.all.get(id)?.parent === b.id)) continue;
    const parent = chain.find((id) => graph.byId.has(id));
    if (parent) {
      parents.set(b.id, parent);
      if (!children.has(parent)) children.set(parent, []);
      children.get(parent).push(b.id);
    }
  }
  const depth = (id) => {
    if (!depths.has(id)) depths.set(id, parents.has(id) ? depth(parents.get(id)) + 1 : 0);
    return depths.get(id);
  };
  for (const b of graph.boxes) depth(b.id);
  return {
    parents,
    children,
    depths,
    roots: graph.boxes.filter((b) => !parents.has(b.id)).map((b) => b.id),
  };
}
/** Find the selected region, its descendants, and its related nodes for highlighting. */
export function selectionContext(graph, id) {
  const nodes = new Set(),
    edges = new Set(),
    regions = new Set(),
    branch = new Set();
  if (!graph?.byId.has(id)) return { active: false, nodes, edges, regions, branch };
  const tree = hierarchyOf(graph);
  const descend = (key) => {
    branch.add(key);
    for (const child of tree.children.get(key) || []) descend(child);
  };
  descend(id);
  for (const key of branch) nodes.add(key);
  for (const edge of graph.edges)
    if (branch.has(edge.from) || branch.has(edge.to)) {
      edges.add(edge.id);
      nodes.add(edge.from);
      nodes.add(edge.to);
    }
  for (const key of [...nodes]) {
    if (tree.children.has(key)) regions.add(key);
    for (const parent of ancestorsToReveal(graph.all, key))
      if (graph.byId.has(parent)) {
        regions.add(parent);
        nodes.add(parent);
      }
  }
  return { active: true, nodes, edges, regions, branch };
}
export const nodeCenter = (b) => ({ x: b.x + b.w / 2, y: b.y + 31 });
const nodeRadius = (b) => Math.hypot(b.w / 2, Math.max(31, b.h - 31)) + 10;
export function hasSelfRelation(graph, id) {
  const edges = [
    ...(graph.rawEdges || []),
    ...(graph.edges?.flatMap((e) => e.members || [e]) || []),
  ];
  const inside = (key) => key === id || ancestorsToReveal(graph.all, key).includes(id);
  return edges.some(
    (e) =>
      e.type !== "contains" && ((e.from === id && inside(e.to)) || (e.to === id && inside(e.from))),
  );
}
function encloseCircles(circles) {
  const ordered = [...circles].sort((a, b) => b.radius - a.radius),
    seeds = [ordered[0]];
  for (const key of ["x", "y"])
    for (const sign of [-1, 1])
      seeds.push(
        ordered.reduce((a, b) => (sign * a[key] + a.radius > sign * b[key] + b.radius ? a : b)),
      );
  let best = null;
  for (const seed of seeds) {
    let { x, y, radius } = seed;
    for (const c of ordered) {
      const distance = Math.hypot(c.x - x, c.y - y);
      if (distance + c.radius <= radius) continue;
      if (distance + radius <= c.radius) {
        ({ x, y, radius } = c);
        continue;
      }
      const next = (radius + distance + c.radius) / 2,
        shift = (next - radius) / distance;
      x += (c.x - x) * shift;
      y += (c.y - y) * shift;
      radius = next;
    }
    if (!best || radius < best.radius) best = { x, y, radius };
  }
  return best;
}
export function hierarchyRegions(graph) {
  const tree = hierarchyOf(graph),
    regions = [];
  function visit(id) {
    const b = graph.byId.get(id),
      center = nodeCenter(b),
      ids = [id];
    const children = tree.children.get(id) || [],
      self = children.length > 0 && hasSelfRelation(graph, id);
    const circles = children.length && !self ? [] : [{ ...center, radius: nodeRadius(b) }];
    for (const child of children) {
      const sub = visit(child);
      ids.push(...sub.ids);
      circles.push({ x: sub.cx, y: sub.cy, radius: sub.radius });
    }
    const enclosure = self
      ? {
          ...center,
          radius: Math.max(
            ...circles.map((c) => Math.hypot(c.x - center.x, c.y - center.y) + c.radius),
          ),
        }
      : encloseCircles(circles);
    const radius = enclosure.radius + (ids.length > 1 ? 30 : 0);
    let root = id;
    while (tree.parents.has(root)) root = tree.parents.get(root);
    const region = {
      id,
      root,
      depth: tree.depths.get(id),
      ids,
      self,
      cx: enclosure.x,
      cy: enclosure.y,
      radius,
      x: enclosure.x - radius,
      y: enclosure.y - radius,
      w: radius * 2,
      h: radius * 2,
    };
    if (ids.length > 1) regions.push(region);
    return region;
  }
  for (const id of tree.roots) visit(id);
  return regions.sort((a, b) => a.depth - b.depth);
}
export function refreshHierarchy(graph) {
  graphBounds(graph);
  graph.regions = hierarchyRegions(graph);
  for (const r of graph.regions) {
    const right = Math.max(graph.minX + graph.width, r.x + r.w + 40),
      bottom = Math.max(graph.minY + graph.height, r.y + r.h + 40);
    graph.minX = Math.min(graph.minX, r.x - 40);
    graph.minY = Math.min(graph.minY, r.y - 40);
    graph.width = right - graph.minX;
    graph.height = bottom - graph.minY;
  }
  return graph;
}
export { relationType };
export const relationStyles = {
  "code-defines": { label: boTranslate("Defines"), color: 0x83929e, dash: [2, 5], arrow: "none" },
  "code-calls": { label: boTranslate("Static call"), color: 0x2476ad, dash: [6, 4], arrow: "open" },
  "code-imports": { label: boTranslate("Import"), color: 0x8172a3, dash: [3, 4], arrow: "open" },
  "code-inherits": { label: boTranslate("Inheritance"), color: 0x975b86, dash: [], arrow: "open" },
  "code-parameter": { label: boTranslate("Parameter"), color: 0x627f9c, dash: [], arrow: "open" },
  "code-maps": {
    label: boTranslate("Source binding"),
    color: 0x638b98,
    dash: [2, 4],
    arrow: "open",
  },
  call: { label: boTranslate("Call"), color: 0x2476ad, dash: [], arrow: "open" },
  flow: { label: boTranslate("Flow"), color: 0x4e647b, dash: [], arrow: "filled" },
  transition: {
    label: boTranslate("State transition"),
    color: 0x8c57ad,
    dash: [10, 4],
    arrow: "filled",
  },
  guard: {
    label: boTranslate("Decision dependency"),
    color: 0xaf731c,
    dash: [3, 5],
    arrow: "diamond",
  },
  data: { label: boTranslate("Value transfer"), color: 0x207e7d, dash: [7, 5], arrow: "open" },
  reads: { label: boTranslate("Read"), color: 0x316da4, dash: [], arrow: "open" },
  writes: { label: boTranslate("Write"), color: 0xb16b36, dash: [], arrow: "filled" },
  references: { label: boTranslate("Reference"), color: 0x716a9c, dash: [3, 4], arrow: "open" },
  maps: { label: boTranslate("Mapping"), color: 0x677a88, dash: [8, 3, 2, 3], arrow: "diamond" },
  transforms: { label: boTranslate("Transform"), color: 0x887130, dash: [7, 4], arrow: "filled" },
  resource: { label: boTranslate("Resource"), color: 0x7c7b2d, dash: [10, 3, 2, 3], arrow: "open" },
  join: { label: boTranslate("Join"), color: 0xa36045, dash: [], arrow: "bar" },
  shared: { label: boTranslate("Shared reference"), color: 0x68759e, dash: [2, 6], arrow: "none" },
  contains: { label: boTranslate("Contains"), color: 0x83929e, dash: [2, 5], arrow: "none" },
  other: { label: boTranslate("Relation"), color: 0x677a88, dash: [4, 4], arrow: "open" },
};
// Folding projects endpoints in graph-core. Keep already-visible inner endpoints:
// an expanded cross-circle call must not turn into a new parent-to-parent call.
/** Route relations through visible region boundaries while retaining their original endpoints. */
export function compoundEdges(graph) {
  const tree = hierarchyOf(graph),
    groups = new Set((graph.regions || []).map((r) => r.id)),
    result = new Map();
  const chain = (id) => {
    const out = [id];
    while (tree.parents.has(id)) {
      id = tree.parents.get(id);
      out.push(id);
    }
    return out;
  };
  for (const edge of graph.edges) {
    if (edge.type === "contains") continue; // The enclosure already shows containment.
    const a = chain(edge.from),
      b = chain(edge.to);
    const from = edge.from,
      to = edge.to,
      type = relationType(edge);
    const sourceRegion = groups.has(from) && !b.includes(from),
      targetRegion = groups.has(to) && !a.includes(to);
    const crossing =
      !a.includes(to) &&
      !b.includes(from) &&
      (sourceRegion || targetRegion || tree.parents.get(from) !== tree.parents.get(to));
    const key = [
      from,
      to,
      type,
      sourceRegion,
      targetRegion,
      ["python-ast", "source-ast"].includes(edge.origin) ? "static" : "model",
    ].join("|");
    const members = edge.members || [{ ...edge, from: edge.from, to: edge.to }];
    if (!result.has(key))
      result.set(key, {
        ...edge,
        id: "summary:" + key,
        from,
        to,
        type,
        sourceRegion,
        targetRegion,
        crossing,
        members: [],
        labels: new Set(),
        observed: false,
        current: false,
        edgeIds: new Set(),
      });
    const summary = result.get(key);
    summary.members.push(...members);
    summary.edgeIds.add(edge.id);
    for (const label of edge.labels || [edge.label]) if (label) summary.labels.add(label);
    summary.observed ||= members.some((member) => member.observed);
    summary.current ||= members.some((member) => member.observed && member.current);
  }
  return [...result.values()];
}
export function filterNode(node, all, filters, asRegion = false) {
  if (hiddenByNode(node.id, all, new Set(filters.hiddenNodes || []))) return false;
  if (node.filter_context && !asRegion) return true;
  return (
    ((node.filter_context && !asRegion) ||
      viewTypes(node).some((type) =>
        (asRegion ? filters.regions : filters.nodes).includes(type),
      )) &&
    (filters.depth === "all" ||
      (node.projection_depth ?? ancestorsToReveal(all, node.id).length) === filters.depth)
  );
}
/** An explicitly hidden group also hides its descendants and shared references. */
export function hiddenByNode(id, all, hidden) {
  const seen = new Set();
  while (id && !seen.has(id)) {
    if (hidden.has(id) || hidden.has(all.get(id)?.referenceOf)) return true;
    seen.add(id);
    id = all.get(id)?.parent;
  }
  return false;
}
/** Filter the rendered graph by node, edge, and region type; keep the source model intact. */
export function presentationGraph(graph, value) {
  const filters = cleanFilters(value),
    regions = new Set(),
    glyphs = new Set();
  for (const r of graph.regions || [])
    if (filterNode(graph.all.get(r.id), graph.all, filters, true)) regions.add(r.id);
  const grouped = new Map((graph.regions || []).map((r) => [r.id, r]));
  for (const b of graph.boxes) {
    const region = grouped.get(b.id);
    if (filterNode(b.node, graph.all, filters) && (!region || region.self || !regions.has(b.id)))
      glyphs.add(b.id);
  }
  const hidden = new Set(filters.hiddenNodes),
    hiddenEdges = new Set(filters.hiddenEdges);
  const edges = compoundEdges(graph)
    .map((edge) => ({
      ...edge,
      members: edge.members.filter(
        (member) =>
          !hiddenEdges.has(member.id) &&
          !hiddenByNode(member.from, graph.all, hidden) &&
          !hiddenByNode(member.to, graph.all, hidden),
      ),
    }))
    .filter((edge) => edge.members.length)
    .filter((e) => filters.edges.includes(relationStyles[e.type] ? e.type : "other"))
    .flatMap((e) => {
      const edge = {
        ...e,
        sourceRegion: e.sourceRegion && regions.has(e.from),
        targetRegion: e.targetRegion && regions.has(e.to),
      };
      // Filtering never invents a replacement endpoint or a new relationship.
      return (edge.sourceRegion || glyphs.has(e.from)) && (edge.targetRegion || glyphs.has(e.to))
        ? [edge]
        : [];
    });
  return { filters, regions, glyphs, edges };
}
/** Count folded elements separately from excluded ones, using original identities. */
export function elementCoverage(graph, presentation) {
  const visible = new Set([...presentation.glyphs, ...presentation.regions]);
  const owners = new Map(),
    hidden = new Set(presentation.filters.hiddenNodes);
  for (const [id, node] of graph.all) {
    if (hiddenByNode(id, graph.all, hidden) || !filterNode(node, graph.all, presentation.filters))
      continue;
    if (graph.eligibleIds && !graph.eligibleIds.has(id)) continue;
    const owner = [id, ...ancestorsToReveal(graph.all, id)].find((p) => visible.has(p));
    if (owner) owners.set(id, owner);
  }
  const drawn = new Set(presentation.edges.flatMap((edge) => edge.members.map((m) => m.id)));
  const foldedEdges = graph.rawEdges.filter(
    (e) =>
      !drawn.has(e.id) &&
      !presentation.filters.hiddenEdges.includes(e.id) &&
      owners.has(e.from) &&
      owners.has(e.to) &&
      (e.type === "contains" || (owners.get(e.from) === owners.get(e.to) && e.from !== e.to)) &&
      (e.type === "contains" || presentation.filters.edges.includes(relationType(e))),
  );
  return {
    nodes: graph.all.size,
    edges: graph.rawEdges.length,
    visibleNodes: visible.size,
    foldedNodes: [...owners].filter(([id, owner]) => id !== owner).length,
    excludedNodes: graph.all.size - owners.size,
    visibleEdges: drawn.size,
    foldedEdges: foldedEdges.length,
    excludedEdges: graph.rawEdges.length - drawn.size - foldedEdges.length,
  };
}
export function renderRevision(view, selection = []) {
  const { clock, ...basis } = view.authority.basis || {};
  // Time is not graph content. Keep the exact deadline crossing as a change,
  // so stopping clock-only redraws cannot make expired evidence look current.
  const deadlines = (view.machine.configurations || []).map((run) => [
    run.attempt,
    run.qualification?.valid_until != null && clock >= run.qualification.valid_until,
  ]);
  return JSON.stringify([
    selection,
    view.manifest.build_id,
    view.manifest.model_hash || view.model,
    view.binding_status,
    view.busy,
    view.events.length,
    view.events.at(-1)?.id,
    view.events.at(-1)?.seq,
    { ...view.authority, basis },
    view.machine,
    deadlines,
  ]);
}
export function edgePorts(graph, edge, nodePort = 32) {
  const regions = new Map((graph.regions || []).map((r) => [r.id, r]));
  const a = graph.byId.get(edge.from),
    b = graph.byId.get(edge.to),
    source = regions.get(edge.from),
    target = regions.get(edge.to);
  const p = edge.sourceRegion && source ? { x: source.cx, y: source.cy } : nodeCenter(a),
    q = edge.targetRegion && target ? { x: target.cx, y: target.cy } : nodeCenter(b);
  const dx = q.x - p.x,
    dy = q.y - p.y,
    length = Math.hypot(dx, dy) || 1;
  const ar = edge.sourceRegion ? regions.get(edge.from)?.radius || 28 : nodePort,
    br = edge.targetRegion ? regions.get(edge.to)?.radius || 28 : nodePort;
  return {
    start: { x: p.x + (dx / length) * ar, y: p.y + (dy / length) * ar },
    end: { x: q.x - (dx / length) * br, y: q.y - (dy / length) * br },
  };
}
function overlaps(a, b, gap = 22) {
  return (
    a.x < b.x + b.w + gap && a.x + a.w + gap > b.x && a.y < b.y + b.h + gap && a.y + a.h + gap > b.y
  );
}
function freePosition(node, x, y, placed) {
  if (!placed.some((p) => overlaps({ ...node, x, y }, p))) return { x, y };
  // Circle groups can be much larger than ordinary nodes. A fixed search radius
  // can fail silently; rectangle-edge candidates and a rightmost fallback cannot.
  const candidates = placed
    .flatMap((p) => [
      { x: p.x + p.w + 24, y },
      { x: p.x - node.w - 24, y },
      { x, y: p.y + p.h + 24 },
      { x, y: p.y - node.h - 24 },
    ])
    .sort((a, b) => Math.hypot(a.x - x, a.y - y) - Math.hypot(b.x - x, b.y - y));
  return (
    candidates.find((point) => !placed.some((p) => overlaps({ ...node, ...point }, p))) || {
      x: Math.max(...placed.map((p) => p.x + p.w)) + 24,
      y,
    }
  );
}
export function placeIncremental(graph, state) {
  const placed = [],
    tree = hierarchyOf(graph);
  const templates = graph.boxes.some((b) => !state.positions[b.id]) ? circleTemplates(graph) : null;
  for (const b of graph.boxes) {
    const p = state.positions[b.id];
    if (p) {
      b.x = p.x;
      b.y = p.y;
      b.pinned = p.pinned;
      placed.push(b);
    }
  }
  for (const b of graph.boxes) {
    if (state.positions[b.id]) continue;
    const parent = graph.byId.get(tree.parents.get(b.id)),
      near = parent && placed.includes(parent) ? parent : null;
    const local = near && templates.get(near.id).items.find((item) => item.id === b.id),
      anchor = near && nodeCenter(near);
    const point = local
      ? { x: anchor.x + local.x, y: anchor.y + local.y }
      : freePosition(b, b.x, b.y, placed);
    Object.assign(b, point, { pinned: false });
    state.positions[b.id] = { ...point, pinned: false };
    placed.push(b);
  }
  return refreshHierarchy(graph);
}
/** Move a node or expanded group while preserving its children's relative positions. */
export function setPosition(graph, state, id, x, y) {
  if (!coordinate(x) || !coordinate(y) || !graph.byId.has(id)) return false;
  const b = graph.byId.get(id),
    dx = x - b.x,
    dy = y - b.y;
  // A manual group move carries saved descendants too. Pins constrain automatic
  // layout; an explicit drag of their enclosing group preserves their offsets.
  const moves = Object.entries(state.positions).filter(
    ([key]) => key === id || ancestorsToReveal(graph.all, key).includes(id),
  );
  if (!moves.some(([key]) => key === id)) moves.push([id, { x: b.x, y: b.y, pinned: !!b.pinned }]);
  if (moves.some(([, p]) => !coordinate(p.x + dx) || !coordinate(p.y + dy))) return false;
  for (const [key, p] of moves) {
    const next = { ...p, x: p.x + dx, y: p.y + dy };
    state.positions[key] = next;
    if (graph.byId.has(key)) Object.assign(graph.byId.get(key), next);
  }
  refreshHierarchy(graph);
  return true;
}
export function togglePin(graph, state, id) {
  const b = graph.byId.get(id);
  if (!b) return;
  const next = !state.positions[id]?.pinned;
  state.positions[id] = { x: b.x, y: b.y, pinned: next };
  b.pinned = next;
  return next;
}
export function topologyKey(graph) {
  return JSON.stringify([
    graph.boxes.map((b) => [b.id, b.node.parent || null]).sort(),
    graph.edges.map((e) => [e.id, e.from, e.to, e.type]).sort(),
  ]);
}
// ELK performs the global layered/stress layout. A constrained merge preserves
// exact user pins and removes overlaps with those pins. It is not yFiles.
export async function calculateLayout(elk, graph, state, algorithm = "layered") {
  if (algorithm === "cluster") return clusteredLayout(elk, graph, state);
  if (!["layered", "stress"].includes(algorithm)) throw Error("Unknown layout algorithm");
  const input = {
    id: "root",
    layoutOptions: {
      "elk.algorithm": algorithm,
      "elk.direction": "RIGHT",
      "elk.randomSeed": "42",
      "elk.spacing.nodeNode": "65",
      "elk.spacing.componentComponent": "100",
      "elk.layered.spacing.nodeNodeBetweenLayers": "110",
      "elk.edgeRouting": "ORTHOGONAL",
      "elk.stress.desiredEdgeLength": "240",
      "elk.stress.iterationLimit": "250",
    },
    children: graph.boxes.map((b) => ({ id: b.id, width: b.w, height: b.h, x: b.x, y: b.y })),
    edges: graph.edges
      .filter((e) => graph.byId.has(e.from) && graph.byId.has(e.to))
      .map((e, i) => ({ id: "e" + i, sources: [e.from], targets: [e.to] })),
  };
  const output = await elk.layout(input),
    proposed = new Map(output.children.map((n) => [n.id, n]));
  const result = Object.create(null),
    placed = [],
    pins = graph.boxes.filter((b) => state.positions[b.id]?.pinned);
  let dx = 60,
    dy = 60;
  if (pins.length) {
    const p = proposed.get(pins[0].id);
    dx = pins[0].x - p.x;
    dy = pins[0].y - p.y;
  }
  for (const b of pins) {
    result[b.id] = { x: b.x, y: b.y, pinned: true };
    placed.push({ ...b });
  }
  for (const b of graph.boxes) {
    if (result[b.id]) continue;
    const p = proposed.get(b.id);
    if (!p || !coordinate(p.x) || !coordinate(p.y))
      throw Error("Layout returned invalid coordinates");
    const point = freePosition(b, p.x + dx, p.y + dy, placed);
    result[b.id] = { ...point, pinned: false };
    placed.push({ ...b, ...point });
  }
  return result;
}
export function applyLayout(graph, state, positions) {
  // Hidden descendants follow their nearest moved visible ancestor. Restoring
  // an undo snapshot can supply them explicitly and takes precedence.
  for (const [id, p] of Object.entries(state.positions)) {
    if (positions[id]) continue;
    const parent = ancestorsToReveal(graph.all, id).find(
      (key) => positions[key] && state.positions[key],
    );
    if (parent) {
      const old = state.positions[parent],
        next = positions[parent];
      state.positions[id] = { ...p, x: p.x + next.x - old.x, y: p.y + next.y - old.y };
    }
  }
  for (const [id, p] of Object.entries(positions)) state.positions[id] = { ...p };
  for (const b of graph.boxes) {
    const p = positions[b.id];
    if (p) {
      state.positions[b.id] = { ...p };
      Object.assign(b, p);
    }
  }
  return refreshHierarchy(graph);
}
// Place a circle around a fixed core, testing a bounded set of rays. Each ray
// skips collision intervals rather than running a continuous force simulation.
function placeCircle(radius, occupied, preferred = -Math.PI / 2) {
  let best = null;
  for (let i = 0; i < 72; i++) {
    const angle = preferred + (i * 2 * Math.PI) / 72,
      ux = Math.cos(angle),
      uy = Math.sin(angle);
    let distance = 0;
    for (let pass = 0; pass <= occupied.length; pass++) {
      let changed = false;
      for (const c of occupied) {
        const projection = c.x * ux + c.y * uy,
          perpendicular = c.x * c.x + c.y * c.y - projection * projection,
          sum = radius + c.radius + 28;
        if (perpendicular >= sum * sum) continue;
        const half = Math.sqrt(Math.max(0, sum * sum - perpendicular)),
          near = projection - half,
          far = projection + half;
        if (distance > near - 1e-6 && distance < far + 1e-6) {
          distance = far + 1;
          changed = true;
        }
      }
      if (!changed) break;
    }
    if (!best || distance < best.distance - 0.01)
      best = { x: ux * distance, y: uy * distance, radius, distance };
  }
  return best;
}
function circleTemplates(graph) {
  const tree = hierarchyOf(graph),
    templates = new Map();
  function pack(id) {
    const b = graph.byId.get(id),
      core = { x: 0, y: 0, radius: nodeRadius(b) };
    const children = (tree.children.get(id) || [])
      .map(pack)
      .sort((a, b) => b.radius - a.radius || a.id.localeCompare(b.id));
    const self = children.length > 0 && hasSelfRelation(graph, id);
    const items = [{ id, x: -b.w / 2, y: -31, w: b.w, h: b.h }],
      occupied = children.length && !self ? [] : [core];
    for (const [index, child] of children.entries()) {
      const position = placeCircle(
        child.radius,
        occupied,
        -Math.PI / 2 + (index * 2 * Math.PI) / Math.max(children.length, 1),
      );
      occupied.push(position);
      items.push(
        ...child.items.map((item) => ({
          ...item,
          x: item.x + position.x - child.cx,
          y: item.y + position.y - child.cy,
        })),
      );
    }
    const enclosure = self
      ? { x: 0, y: 0, radius: Math.max(...occupied.map((c) => Math.hypot(c.x, c.y) + c.radius)) }
      : encloseCircles(occupied);
    const result = {
      id,
      radius: enclosure.radius + (children.length ? 30 : 0),
      cx: enclosure.x,
      cy: enclosure.y,
      items,
    };
    templates.set(id, result);
    return result;
  }
  tree.roots.forEach(pack);
  return templates;
}
// Pack each visible subtree into a circle, with its own core as the origin.
// ELK places only the top-level circles, so it cannot flatten their contents.
async function clusteredLayout(elk, graph, state) {
  const tree = hierarchyOf(graph),
    templates = circleTemplates(graph),
    roots = tree.roots.map((id) => templates.get(id));
  if (!roots.length) return Object.create(null);
  const owner = (id) => {
      while (tree.parents.has(id)) id = tree.parents.get(id);
      return id;
    },
    links = new Map();
  for (const e of graph.edges) {
    const a = owner(e.from),
      b = owner(e.to);
    if (a !== b) links.set(a + ">" + b, { id: "group:" + a + ">" + b, sources: [a], targets: [b] });
  }
  const output = await elk.layout({
    id: "root",
    layoutOptions: {
      "elk.algorithm": "stress",
      "elk.randomSeed": "42",
      "elk.stress.iterationLimit": "250",
      "elk.stress.desiredEdgeLength": "480",
      "elk.spacing.nodeNode": "140",
      "elk.spacing.componentComponent": "140",
    },
    children: roots.map((c) => ({ id: c.id, width: 2 * c.radius, height: 2 * c.radius })),
    edges: [...links.values()],
  });
  const proposed = new Map(output.children.map((p) => [p.id, p])),
    result = Object.create(null),
    occupied = [];
  const hasPin = (c) => c.items.some((item) => state.positions[item.id]?.pinned);
  for (const c of [...roots].sort((a, b) => Number(hasPin(b)) - Number(hasPin(a)))) {
    const p = proposed.get(c.id);
    if (!coordinate(p?.x) || !coordinate(p?.y)) throw Error("Invalid group position");
    const anchor = c.items.find((item) => state.positions[item.id]?.pinned);
    const origin = anchor
      ? { x: state.positions[anchor.id].x - anchor.x, y: state.positions[anchor.id].y - anchor.y }
      : { x: p.x + c.radius - c.cx, y: p.y + c.radius - c.cy };
    const boxes = c.items.map((item) => ({
      ...graph.byId.get(item.id),
      x: origin.x + item.x,
      y: origin.y + item.y,
      ...(state.positions[item.id]?.pinned ? state.positions[item.id] : {}),
    }));
    const enclosure = hierarchyRegions({
      boxes,
      byId: new Map(boxes.map((b) => [b.id, b])),
      all: graph.all,
      edges: graph.edges,
      rawEdges: graph.rawEdges,
    }).find((r) => r.id === c.id);
    const bounds = enclosure || {
      x: origin.x + c.cx - c.radius,
      y: origin.y + c.cy - c.radius,
      w: 2 * c.radius,
      h: 2 * c.radius,
    };
    const next = anchor ? bounds : freePosition(bounds, bounds.x, bounds.y, occupied),
      dx = next.x - bounds.x,
      dy = next.y - bounds.y;
    occupied.push({ ...bounds, x: next.x, y: next.y });
    for (const b of boxes)
      result[b.id] = { x: b.x + dx, y: b.y + dy, pinned: !!state.positions[b.id]?.pinned };
  }
  return result;
}
/** Place newly revealed descendants around their current parent position. */
export function settleExpansion(graph, state, id) {
  const tree = hierarchyOf(graph);
  const footprint = (key) => {
    const group = graph.regions.find((r) => r.id === key),
      b = graph.byId.get(key),
      p = nodeCenter(b);
    return {
      id: key,
      x: group?.cx ?? p.x,
      y: group?.cy ?? p.y,
      radius: group?.radius || nodeRadius(b),
    };
  };
  let current = id;
  while (current) {
    const parent = tree.parents.get(current),
      siblings = parent ? tree.children.get(parent) : tree.roots;
    const center = parent
      ? nodeCenter(graph.byId.get(parent))
      : nodeCenter(graph.byId.get(current));
    const fixed = (key) =>
      state.positions[key]?.pinned ||
      [...graph.all.keys()].some(
        (k) => state.positions[k]?.pinned && ancestorsToReveal(graph.all, k).includes(key),
      );
    const reserved = siblings.filter((key) => key === current || fixed(key)).map(footprint);
    if (parent && hasSelfRelation(graph, parent))
      reserved.push({ ...center, radius: nodeRadius(graph.byId.get(parent)) });
    for (const sibling of siblings.filter((key) => key !== current && !fixed(key))) {
      const before = footprint(sibling);
      if (
        reserved.some(
          (c) => Math.hypot(before.x - c.x, before.y - c.y) < before.radius + c.radius + 28,
        )
      ) {
        const after = placeCircle(
          before.radius,
          reserved.map((c) => ({ ...c, x: c.x - center.x, y: c.y - center.y })),
          Math.atan2(before.y - center.y, before.x - center.x),
        );
        const b = graph.byId.get(sibling);
        setPosition(
          graph,
          state,
          sibling,
          b.x + center.x + after.x - before.x,
          b.y + center.y + after.y - before.y,
        );
      }
      reserved.push(footprint(sibling));
    }
    current = parent;
  }
  return refreshHierarchy(graph);
}
// A small shared gesture controller makes node drag distinct from canvas pan,
// including pointer cancellation, scale conversion and lost capture.
export function pickHit(hits, x, y) {
  const front = hits.slice().reverse(),
    distance = (h) => Math.hypot(x - h.cx, y - h.cy);
  // Label rectangles can overlap another node's glyph after manual positioning.
  // Pick the closest actual glyph first, then handles, labels and edge labels.
  const glyphs = front.filter((h) => h.id && Number.isFinite(h.r) && distance(h) <= h.r);
  if (glyphs.length) return glyphs.sort((a, b) => distance(a) - distance(b))[0];
  const under = front.filter((h) => x >= h.x && x <= h.x + h.w && y >= h.y && y <= h.y + h.h);
  return (
    under.find((h) => h.expand) ||
    under.filter((h) => h.id).sort((a, b) => distance(a) - distance(b))[0] ||
    under[0] ||
    front.find((h) => h.border && Math.abs(distance(h) - h.radius) < 12) ||
    front.filter((h) => h.border && distance(h) < h.radius).sort((a, b) => a.radius - b.radius)[0]
  );
}
export class GraphGesture {
  start(pointer, { node = null, pan, scale }) {
    this.active = {
      pointerId: pointer.pointerId,
      x: pointer.x,
      y: pointer.y,
      node: node ? { id: node.id, x: node.x, y: node.y } : null,
      pan: { ...pan },
      scale,
      moved: false,
    };
  }
  move(pointer) {
    const a = this.active;
    if (!a || a.pointerId !== pointer.pointerId) return null;
    const dx = pointer.x - a.x,
      dy = pointer.y - a.y;
    if (Math.hypot(dx, dy) > 4) a.moved = true;
    if (!a.moved) return null;
    return a.node
      ? { kind: "node", id: a.node.id, x: a.node.x + dx / a.scale, y: a.node.y + dy / a.scale }
      : { kind: "pan", x: a.pan.x + dx, y: a.pan.y + dy };
  }
  end(pointerId) {
    if (this.active?.pointerId !== pointerId) return null;
    const old = this.active;
    this.active = null;
    return old;
  }
}
