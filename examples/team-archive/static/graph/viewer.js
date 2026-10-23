import { t as boTranslate } from "./i18n.js";
import { locale, translateShell, restoreLocale, saveLocale, localeURL } from "./i18n.js";
import { createGraphRenderer, nodePoint, bezierAt } from "./renderer.js";
import { createConversationFocus, discussionContext } from "./conversation.js";
import { projectStorage } from "./preferences.js";
import { createPoller } from "./polling.js";
import { migrateNodeIds } from "./layout.js";
import {
  executionIds,
  layoutGraph,
  selectedConfiguration,
  configurations,
  stateLabels,
  phaseLabel,
  nodeTypes,
  sourceBinding,
  parameterSummary,
} from "./graph-core.js";
import {
  layoutKey,
  readLayout,
  writeLayout,
  placeIncremental,
  setPosition,
  togglePin,
  calculateLayout,
  applyLayout,
  topologyKey,
  GraphGesture,
  annotationFor,
  displayName,
  setAnnotation,
  pickHit,
  searchNodes,
  ancestorsToReveal,
  selectionContext,
  refreshHierarchy,
  compoundEdges,
  edgePorts,
  relationStyles,
  settleExpansion,
  presentationGraph,
  filterNode,
  cleanFilters,
  emptyFilters,
  renderRevision,
} from "./layout.js";
import { presets, profileFor, cleanProfile, matchingNodes, sharedMemberships } from "./analysis.js";
import { legendGlyph, legendRelation, meanings, glyphAppearance } from "./glyphs.js";
import { timeline, frame, eventLabel, transferEdges, recordingRequest } from "./recording.js";
import {
  boKinds,
  boValue,
  boDisplayValue,
  boStepPlan,
  boStepDetail,
  boTransferLabel,
} from "./replay-steps.js";
const $ = (id) => document.getElementById(id),
  app = new PIXI.Application(),
  scene = new PIXI.Container();
// The bundled ELK entry defaults to its Node fallback unless a factory is supplied.
const layoutWorker = new Worker(new URL("./elk-worker.min.js", import.meta.url));
const elk = new ELK({ workerFactory: () => layoutWorker }),
  gesture = new GraphGesture();
let version = "live",
  caseChoice = "live",
  choice = "latest",
  step = "latest",
  view = null,
  graph = null,
  selected = null;
let scale = 1,
  pan = { x: 0, y: 0 },
  expanded = new Set(),
  preferences = null,
  storageKey = null,
  first = true,
  lastKey = "",
  dirty = false;
let layoutEpoch = 0,
  layoutBusy = false,
  layoutError = null,
  undo = null,
  detailMode = null,
  saveTimer = null;
let focusContext = { active: false, nodes: new Set(), edges: new Set(), regions: new Set() },
  renderedEdges = [],
  presentation = null;
let analysisId = "overview",
  analysisSettings = null,
  analysisKey = null,
  analysisOverride = null;
let recording = null,
  replayItems = [],
  replayIndex = 0,
  playTimer = null,
  recordBusy = false,
  recordActive = false,
  lastRecordPoll = 0,
  latestLive = null;
let animationFrame = null,
  animationUntil = 0,
  animatedIds = [],
  animationEvent = null,
  lastLiveEvent = null;
let boPlan = [],
  boPlanKey = "",
  boDetail = null,
  boTransfers = new Map();
const edgePaths = new Map(),
  animationLayer = new PIXI.Container(),
  animationDot = new PIXI.Graphics();
let drawFrame = null,
  disposed = false,
  contextLost = false;
const hits = [],
  fullSources = new Map(),
  metrics = { nodes: 0, edges: 0, texts: 0 };
let legacyStorage;
try {
  legacyStorage = window.localStorage;
} catch {}
const storage = await projectStorage(legacyStorage, (message) => {
  if ($("layout-status")) $("layout-status").textContent = message;
});
const restoredLocaleURL = restoreLocale(storage, window.location.href, navigator.languages);
if (restoredLocaleURL) window.location.replace(restoredLocaleURL);
translateShell(document);
$("language").value = locale();
$("language").addEventListener("change", async (event) => {
  event.target.disabled = true;
  try {
    save();
    await saveLocale(storage, event.target.value);
    window.location.assign(localeURL(window.location.href, event.target.value));
  } catch (error) {
    $("layout-status").textContent = String(error.message);
    event.target.value = locale();
    event.target.disabled = false;
  }
});
await app.init({
  resizeTo: $("viewport"),
  preference: "webgl",
  antialias: true,
  background: 0xf6f8fa,
  resolution: Math.min(devicePixelRatio, 1.5),
  autoDensity: true,
  autoStart: false,
});
$("canvas-host").appendChild(app.canvas);
app.stage.addChild(scene, animationLayer);
animationLayer.addChild(animationDot);
app.canvas.setAttribute("aria-hidden", "true");
$("renderer").textContent = "PixiJS / WebGL · ELK";
const renderer = createGraphRenderer({
  PIXI,
  app,
  scene,
  metrics,
  hits,
  edgePaths,
  onMetrics: (data) => Object.assign($("renderer").dataset, data),
});
function point(box) {
  return nodePoint(graph, presentation, box);
}
function updatePresentation() {
  presentation = presentationGraph(graph, preferences.filters);
  renderedEdges = presentation.edges;
  $("empty").hidden = !!(presentation.glyphs.size + presentation.regions.size);
  if (!$("empty").hidden)
    $("empty").textContent = boTranslate("No matching nodes. Change the view or filters.");
}
function draw() {
  dirty = false;
  drawFrame = null;
  if (!graph || disposed || contextLost || document.hidden) return;
  focusContext = selected
    ? selectionContext(graph, selected)
    : discussionContext(graph, conversation.ids);
  updatePresentation();
  renderer.draw({
    graph,
    presentation,
    focusContext,
    preferences,
    selected,
    scale,
    pan,
    boDetail,
    boTransfers,
    formatChange: boChangeText,
    formatValue: boText,
    contextLost,
  });
  app.renderer.render(app.stage);
  $("zoom").value = Math.round(scale * 100) + "%";
  updateSemanticGeometry();
  positionDetail();
}
function schedule() {
  if (!dirty && !disposed && !contextLost && !document.hidden) {
    dirty = true;
    drawFrame = requestAnimationFrame(draw);
  }
}
function save() {
  if (!preferences) return;
  saveAnalysis();
  preferences.expanded = [...expanded];
  preferences.camera = { x: pan.x, y: pan.y, scale };
  preferences.focus = selected;
  const saved = writeLayout(storage, storageKey, preferences);
  if (!layoutBusy)
    $("layout-status").textContent =
      layoutError || (saved ? storage.status() : boTranslate("This view could not be saved"));
}
function saveSoon() {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(save, 180);
}
window.addEventListener("pagehide", (event) => {
  save();
  storage.flush();
  clearTimeout(saveTimer);
  poller.pause();
  cancelAnimationFrame(drawFrame);
  dirty = false;
  if (!event.persisted) {
    disposed = true;
    poller.close();
    stopPlayback();
    stopAnimation();
    layoutWorker.terminate();
    resizeObserver.disconnect();
    renderer.clear();
    app.destroy(true, { children: true });
  }
});
document.addEventListener("visibilitychange", () => {
  if (document.hidden) {
    stopPlayback();
    stopAnimation();
    poller.pause();
    cancelAnimationFrame(drawFrame);
    dirty = false;
  } else {
    schedule();
    poller.run();
  }
});
window.addEventListener("pageshow", (event) => {
  if (event.persisted) {
    schedule();
    poller.run();
  }
});
app.canvas.addEventListener("webglcontextlost", (event) => {
  event.preventDefault();
  contextLost = true;
  cancelAnimationFrame(drawFrame);
  dirty = false;
  $("connection").textContent = boTranslate("Graphics connection lost; recovering");
});
app.canvas.addEventListener("webglcontextrestored", () => {
  contextLost = false;
  schedule();
});
function cancelLayout() {
  layoutEpoch++;
  layoutBusy = false;
  layoutError = null;
  $("arrange").disabled = false;
}
function project() {
  if (!view) return;
  const renamed = migrateNodeIds(preferences, view.model.presentation?.node_aliases);
  expanded = new Set([...expanded].map((id) => renamed[id] || id));
  selected = renamed[selected] || selected;
  const profile = currentProfile();
  graph = layoutGraph(view, expanded, new Set(), new Map(), choice, step, {
    include: (n) =>
      n.filter_context ||
      analysisSettings?.advanced ||
      (!["python-ast", "source-ast"].includes(n.origin) && n.analysis_level !== "advanced") ||
      annotationFor(preferences, n.id).core,
    memberships: sharedMemberships(view.model),
    ...(!profile.hierarchical ||
    profile.scope !== "all" ||
    profile.query ||
    profile.nodes.length < 8 ||
    profile.depth !== "all"
      ? {
          match: (all, events, status, relations) =>
            matchingNodes(all, view, events, profile, status, relations),
        }
      : {}),
  });
  for (const b of graph.boxes) {
    b.baseHeight = b.h;
    b.h += annotationFor(preferences, b.node.referenceOf || b.id).note ? 22 : 0;
  }
  placeIncremental(graph, preferences);
  updatePresentation();
  if (selected && !graph.byId.has(selected))
    selected = ancestorsToReveal(graph.all, selected).find((id) => graph.byId.has(id)) || null;
  updateFilters();
  updateSemantic();
  updateActions();
  updateDetail();
  updateEdgeDetail();
  if (recording) boUpdateReplay();
  schedule();
}
async function arrange(initial = false) {
  if (!graph) return;
  const epoch = ++layoutEpoch,
    key = topologyKey(graph),
    scope = storageKey,
    algorithm = $("layout").value;
  const previous = JSON.stringify(preferences.positions),
    camera = { scale, pan: { ...pan } };
  layoutBusy = true;
  layoutError = null;
  $("arrange").disabled = true;
  $("layout-status").textContent = boTranslate("Arranging\u2026");
  try {
    const positions = await calculateLayout(elk, graph, preferences, algorithm);
    if (epoch !== layoutEpoch || scope !== storageKey || !graph || key !== topologyKey(graph))
      return;
    undo = { positions: previous, camera };
    $("undo-layout").disabled = false;
    applyLayout(graph, preferences, positions);
    preferences.algorithm = algorithm;
    fit();
    if (conversation.ids.length) frameDiscussion();
  } catch (error) {
    if (epoch === layoutEpoch) {
      console.error(error);
      layoutError = boTranslate("Layout failed; keeping previous positions");
    }
  } finally {
    if (epoch === layoutEpoch) {
      layoutBusy = false;
      $("arrange").disabled = false;
      save();
      updateActions();
      schedule();
    }
  }
}
function plotArea() {
  const top = 42,
    bottom = $("step-changes").hidden ? 24 : Math.min(160, $("step-changes").offsetHeight + 25);
  return {
    top,
    height: Math.max(60, app.screen.height - top - bottom),
    width: Math.max(60, app.screen.width - 45),
  };
}
function fit() {
  if (!graph) return;
  refreshHierarchy(graph);
  const area = plotArea();
  scale = Math.max(0.12, Math.min(1.05, area.width / graph.width, area.height / graph.height));
  pan = {
    x: (app.screen.width - graph.width * scale) / 2 - graph.minX * scale,
    y: area.top + (area.height - graph.height * scale) / 2 - graph.minY * scale,
  };
  schedule();
  saveSoon();
}
function zoom(factor, point = { x: app.screen.width / 2, y: app.screen.height / 2 }) {
  const next = Math.max(0.12, Math.min(3, scale * factor));
  pan.x = point.x - ((point.x - pan.x) * next) / scale;
  pan.y = point.y - ((point.y - pan.y) * next) / scale;
  scale = next;
  schedule();
  saveSoon();
}
function select(id) {
  selected = id;
  selectedEdge = null;
  detailMode = null;
  $("node-details").hidden = true;
  $("edge-details").hidden = true;
  updateActions();
  schedule();
  saveSoon();
}
function frameDiscussion() {
  const boxes = [...discussionContext(graph, conversation.ids).nodes]
    .map((id) => graph?.byId.get(id))
    .filter(Boolean);
  if (!boxes.length) return;
  const bounds = boxes.map((b) => graph.regions.find((r) => r.id === b.id) || b);
  const left = Math.min(...bounds.map((b) => b.x)) - 55,
    top = Math.min(...bounds.map((b) => b.y)) - 55;
  const width = Math.max(...bounds.map((b) => b.x + b.w)) - left + 55,
    height = Math.max(...bounds.map((b) => b.y + b.h)) - top + 55;
  const area = plotArea();
  scale = Math.max(0.12, Math.min(1.1, area.width / width, area.height / height));
  pan = {
    x: (app.screen.width - width * scale) / 2 - left * scale,
    y: area.top + (area.height - height * scale) / 2 - top * scale,
  };
  schedule();
}
function showDiscussion(ids) {
  if (!graph) return;
  if (analysisId !== "overview") changeAnalysis("overview");
  for (const id of ids) for (const parent of ancestorsToReveal(graph.all, id)) expanded.add(parent);
  if (
    ids.some(
      (id) =>
        graph.all.get(id)?.analysis_level === "advanced" ||
        ["python-ast", "source-ast"].includes(graph.all.get(id)?.origin),
    )
  )
    analysisSettings.advanced = true;
  selected = null;
  project();
  frameDiscussion();
}
function toggle(id) {
  if (!graph?.children.has(id)) return;
  cancelLayout();
  selected = id;
  const opening = !expanded.has(id);
  if (opening) expanded.add(id);
  else expanded.delete(id);
  project();
  if (opening) {
    settleExpansion(graph, preferences, id);
    updatePresentation();
    focusSelection();
  }
  save();
  schedule();
}
function pin() {
  if (!selected) return;
  cancelLayout();
  togglePin(graph, preferences, selected);
  updateActions();
  save();
  schedule();
}
function updateHierarchyPath() {
  const host = $("hierarchy-path");
  host.replaceChildren();
  const home = document.createElement("button");
  home.textContent = boTranslate("Overview");
  home.onclick = () => $("collapse").click();
  host.append(home);
  if (!graph?.byId.has(selected)) return;
  const path = [...ancestorsToReveal(graph.all, selected).reverse(), selected];
  for (const id of path) {
    const node = graph.all.get(id);
    if (!node) continue;
    const separator = document.createElement("span");
    separator.textContent = "›";
    const button = document.createElement("button");
    button.textContent = displayName(node, preferences);
    if (id === selected) button.setAttribute("aria-current", "location");
    button.onclick = () => {
      select(id);
      focusSelection();
    };
    host.append(separator, button);
  }
}
function focusSelection() {
  if (!graph?.byId.has(selected)) return;
  const context = selectionContext(graph, selected),
    boxes = [
      ...graph.boxes.filter((b) => context.branch.has(b.id)),
      ...graph.regions.filter((r) => context.branch.has(r.id)),
    ];
  const minX = Math.min(...boxes.map((b) => b.x)) - 55,
    minY = Math.min(...boxes.map((b) => b.y)) - 55;
  const width = Math.max(...boxes.map((b) => b.x + b.w)) - minX + 55,
    height = Math.max(...boxes.map((b) => b.y + b.h)) - minY + 55;
  const area = plotArea();
  scale = Math.max(0.12, Math.min(1.15, area.width / width, area.height / height));
  pan = {
    x: (app.screen.width - width * scale) / 2 - minX * scale,
    y: area.top + (area.height - height * scale) / 2 - minY * scale,
  };
  schedule();
  saveSoon();
}
function updateActions() {
  const b = graph?.byId.get(selected),
    binding = sourceBinding(view, graph?.all, selected);
  $("reference-origin").hidden = !b?.node.referenceOf;
  $("core-toggle").disabled = !b;
  const core = b && annotationFor(preferences, b.node.referenceOf || b.id).core;
  $("core-toggle").textContent = core ? boTranslate("\u2605 Core") : boTranslate("\u2606 Core");
  $("core-toggle").setAttribute("aria-pressed", String(!!core));
  updateHierarchyPath();
  $("focus-selection").disabled = !b;
  $("node-expand").disabled = !b?.kids.length;
  $("node-expand").textContent = b?.open ? boTranslate("Collapse") : boTranslate("Expand");
  $("pin").disabled = !b;
  $("pin").textContent = b?.pinned ? boTranslate("Unpin") : boTranslate("Pin node");
  $("annotate").disabled = !b;
  $("details").disabled = !b;
  $("source").disabled = !binding;
  $("selection").textContent = b
    ? `${nodeTypes[b.type].label} · ${displayName(b.node, preferences)}` +
      (b.open ? boTranslate(" \u00B7 Drag empty space inside a region to move its group") : "") +
      (binding ? ` · ${binding.path}:${binding.line}` : "")
    : boTranslate("Double-click to expand; drag a node or empty region space to move its group.");
}
function updateSemantic() {
  const host = $("semantic"),
    focused = document.activeElement?.dataset.nodeId;
  host.replaceChildren();
  for (const b of graph.boxes) {
    if (!presentation.glyphs.has(b.id) && !presentation.regions.has(b.id)) continue;
    const button = document.createElement("button"),
      name = displayName(b.node, preferences);
    button.dataset.representation = presentation.regions.has(b.id)
      ? presentation.glyphs.has(b.id)
        ? "self"
        : "circle"
      : "node";
    button.dataset.color = "#" + nodeTypes[b.type].color.toString(16).padStart(6, "0");
    button.dataset.core = String(!!annotationFor(preferences, b.node.referenceOf || b.id).core);
    button.dataset.referenceOf = b.node.referenceOf || "";
    button.dataset.runState = b.state;
    button.dataset.depth = ancestorsToReveal(graph.all, b.id).length;
    button.textContent = name;
    button.dataset.nodeId = b.id;
    button.dataset.nodeType = b.type;
    button.setAttribute("aria-label", name);
    button.setAttribute("aria-expanded", String(!!b.open));
    button.onclick = () => select(b.id);
    button.onfocus = () => {
      if (selected !== b.id) select(b.id);
    };
    host.appendChild(button);
  }
  if (focused) {
    const el = [...host.children].find((e) => e.dataset.nodeId === focused);
    el?.focus({ preventScroll: true });
  }
  const relationships = $("semantic-edges"),
    focusedEdge = document.activeElement?.dataset.edgeId;
  relationships.replaceChildren();
  for (const edge of renderedEdges) {
    const button = document.createElement("button"),
      style = relationStyles[edge.type] || relationStyles.other;
    button.textContent = boTranslate(
      "{0}: {1} \u2192 {2}, {3} relations",
      style.label,
      displayName(graph.byId.get(edge.from).node, preferences),
      displayName(graph.byId.get(edge.to).node, preferences),
      edge.members.length,
    );
    button.dataset.edgeId = edge.id;
    button.dataset.from = edge.from;
    button.dataset.to = edge.to;
    button.dataset.relationType = edge.type;
    button.dataset.layer = edge.crossing ? "foreground" : "internal";
    button.dataset.sourceRegion = String(edge.sourceRegion);
    button.dataset.targetRegion = String(edge.targetRegion);
    button.dataset.count = edge.members.length;
    button.onclick = () => showEdge(edge);
    relationships.appendChild(button);
  }
  if (focusedEdge)
    [...relationships.children]
      .find((e) => e.dataset.edgeId === focusedEdge)
      ?.focus({ preventScroll: true });
}
function updateSemanticGeometry() {
  const r = app.canvas.getBoundingClientRect();
  for (const el of $("semantic").children) {
    const b = graph.byId.get(el.dataset.nodeId);
    if (!b) continue;
    const appearance = glyphAppearance(nodeTypes[b.type].color, {
      core: annotationFor(preferences, b.node.referenceOf || b.id).core,
      selected: selected === b.id,
      related: focusContext.nodes.has(b.id),
    });
    el.dataset.fill = "#" + appearance.fill.toString(16).padStart(6, "0");
    el.dataset.fillEmphasis = appearance.emphasis;
    el.dataset.discussion = String(conversation.ids.includes(b.id));
  }
  for (const el of $("semantic").children) {
    const b = graph.byId.get(el.dataset.nodeId);
    if (b) {
      const p = point(b);
      el.dataset.x = b.x;
      el.dataset.y = b.y;
      el.dataset.pinned = String(!!b.pinned);
      el.dataset.emphasis = focusContext.active
        ? selected === b.id
          ? "selected"
          : focusContext.nodes.has(b.id)
            ? "related"
            : "dimmed"
        : "normal";
      el.setAttribute("aria-pressed", String(selected === b.id));
      el.dataset.parent = b.node.parent || "";
      el.dataset.screenX = r.left + p.x * scale + pan.x;
      el.dataset.screenY = r.top + p.y * scale + pan.y;
    }
  }
  for (const el of $("semantic").children) {
    const region = presentation.regions.has(el.dataset.nodeId)
      ? graph.regions.find((region) => region.id === el.dataset.nodeId)
      : null;
    el.dataset.groupRadius = region?.radius || "";
    el.dataset.groupCenterX = region?.cx ?? "";
    el.dataset.groupCenterY = region?.cy ?? "";
  }
  for (const el of $("semantic-edges").children) {
    const edge = renderedEdges.find((e) => e.id === el.dataset.edgeId);
    if (!edge) continue;
    const ports = edgePorts(graph, edge, Math.max(32, 15 / scale));
    el.dataset.startX = ports.start.x;
    el.dataset.startY = ports.start.y;
    el.dataset.endX = ports.end.x;
    el.dataset.endY = ports.end.y;
  }
}
let selectedEdge = null;
function showEdge(edge) {
  select(null);
  selectedEdge = edge.id;
  updateEdgeDetail();
}
function updateEdgeDetail() {
  const panel = $("edge-details"),
    edge = renderedEdges.find((e) => e.id === selectedEdge);
  if (!edge) {
    selectedEdge = null;
    panel.hidden = true;
    return;
  }
  const style = relationStyles[edge.type] || relationStyles.other;
  $("edge-title").textContent = boTranslate(
    "{0} \u00B7 {1} relations",
    style.label,
    edge.members.length,
  );
  $("edge-members").replaceChildren(
    ...edge.members.map((member) => {
      const item = document.createElement("li"),
        a = graph.all.get(member.from),
        b = graph.all.get(member.to);
      item.textContent = `${a ? displayName(a, preferences) : member.from} → ${b ? displayName(b, preferences) : member.to}：${member.label || style.label}（${["python-ast", "source-ast"].includes(member.origin) ? boTranslate("Static call") : member.observed ? (member.current ? boTranslate("Observed in this run") : boTranslate("Observed in a previous run")) : boTranslate("Declared relation")}）`;
      return item;
    }),
  );
  const ports = edgePorts(graph, edge);
  panel.hidden = false;
  panel.style.left =
    Math.max(
      12,
      Math.min(
        app.screen.width - panel.offsetWidth - 12,
        ((ports.start.x + ports.end.x) / 2) * scale + pan.x,
      ),
    ) + "px";
  panel.style.top =
    Math.max(
      45,
      Math.min(
        app.screen.height - panel.offsetHeight - 12,
        ((ports.start.y + ports.end.y) / 2) * scale + pan.y,
      ),
    ) + "px";
}
$("close-edge").onclick = () => {
  selectedEdge = null;
  $("edge-details").hidden = true;
  $("viewport").focus({ preventScroll: true });
};
function updateDetail() {
  const b = graph?.byId.get(selected);
  if (!b || !detailMode) {
    $("node-details").hidden = true;
    return;
  }
  const annotation = annotationFor(preferences, b.node.referenceOf || b.id),
    editing = detailMode === "annotation";
  $("node-details").hidden = false;
  $("detail-title").textContent = displayName(b.node, preferences);
  $("annotation-form").hidden = !editing;
  const rows = [
    ...(annotation.label || editing
      ? [{ text: boTranslate("Original name: ") + b.node.label }]
      : []),
    ...(editing ? [{ text: boTranslate("Node: ") + b.id }] : b.rows),
    ...(!editing && annotation.note ? [{ text: boTranslate("Note: ") + annotation.note }] : []),
  ];
  $("detail-rows").replaceChildren(
    ...rows.map((r) => {
      const p = document.createElement("p");
      p.textContent = r.text;
      return p;
    }),
  );
  const binding = sourceBinding(view, graph.all, selected),
    source = detailMode === "source" && binding;
  $("source-code").hidden = !source;
  $("full-source").hidden = !source;
  if (source) {
    const key = view.manifest.build_id + ":" + binding.path,
      full = fullSources.get(key);
    $("detail-title").textContent =
      `${binding.path}:${binding.line} · ${view.manifest.build_id.slice(0, 8)}`;
    $("source-code").textContent = full ?? binding.snippet;
    $("full-source").hidden = !!full;
  }
  positionDetail();
}
function positionDetail() {
  if ($("node-details").hidden || !graph?.byId.has(selected)) return;
  const b = graph.byId.get(selected),
    p = point(b),
    panel = $("node-details"),
    w = panel.offsetWidth,
    h = panel.offsetHeight;
  panel.style.left =
    Math.max(10, Math.min(app.screen.width - w - 10, p.x * scale + pan.x + 45)) + "px";
  panel.style.top =
    Math.max(10, Math.min(app.screen.height - h - 12, p.y * scale + pan.y - 30)) + "px";
}
function showDetail(mode) {
  detailMode = mode;
  updateDetail();
}
function editAnnotation() {
  if (!graph?.byId.has(selected)) return;
  const b = graph.byId.get(selected),
    annotation = annotationFor(preferences, b.node.referenceOf || selected);
  $("node-name").value = annotation.label;
  $("node-name").placeholder = b.node.label;
  $("node-note").value = annotation.note;
  $("node-core").checked = !!annotation.core;
  showDetail("annotation");
  $("node-name").focus({ preventScroll: true });
}
function saveAnnotation() {
  const b = graph?.byId.get(selected);
  if (!b || detailMode !== "annotation") return;
  cancelLayout();
  const annotation = setAnnotation(preferences, b.node.referenceOf || selected, {
    label: $("node-name").value,
    note: $("node-note").value,
    core: $("node-core").checked,
  });
  b.h = b.baseHeight + (annotation.note ? 22 : 0);
  placeIncremental(graph, preferences);
  for (const el of $("semantic").children) {
    const node = graph.byId.get(el.dataset.nodeId)?.node;
    if (node) {
      const name = displayName(node, preferences);
      el.textContent = name;
      el.setAttribute("aria-label", name);
    }
  }
  updateActions();
  updateDetail();
  save();
  schedule();
}
$("core-toggle").onclick = () => {
  const b = graph?.byId.get(selected);
  if (!b) return;
  const id = b.node.referenceOf || b.id,
    previous = annotationFor(preferences, id);
  setAnnotation(preferences, id, { ...previous, core: !previous.core });
  updateActions();
  updateSemantic();
  save();
  schedule();
};
$("node-core").onchange = saveAnnotation;
$("node-name").oninput = saveAnnotation;
$("node-note").oninput = saveAnnotation;
$("restore-name").onclick = () => {
  $("node-name").value = "";
  saveAnnotation();
};
$("annotation-form").onsubmit = (e) => {
  e.preventDefault();
  saveAnnotation();
  detailMode = null;
  updateDetail();
  $("viewport").focus({ preventScroll: true });
};
$("full-source").onclick = async () => {
  const id = selected,
    build = view.manifest.build_id,
    binding = sourceBinding(view, graph.all, id),
    requestedVersion = version;
  const response = await fetch(
    "/api/source?path=" +
      encodeURIComponent(binding.path) +
      (recording
        ? "&recording=" + recording.id
        : "&version=" + encodeURIComponent(requestedVersion)),
  );
  if (!response.ok) return;
  const data = await response.json();
  if (view?.manifest.build_id !== build || data.build_id !== build || version !== requestedVersion)
    return;
  fullSources.set(build + ":" + binding.path, data.source);
  if (fullSources.size > 16) fullSources.delete(fullSources.keys().next().value);
  if (selected === id) updateDetail();
};
function hitAt(e) {
  const r = app.canvas.getBoundingClientRect();
  return pickHit(hits, (e.clientX - r.left - pan.x) / scale, (e.clientY - r.top - pan.y) / scale);
}
app.canvas.addEventListener("pointerdown", (e) => {
  if (e.button !== 0 || gesture.active) return;
  const hit = hitAt(e);
  cancelLayout();
  app.canvas.setPointerCapture(e.pointerId);
  if (hit?.id) select(hit.id);
  else if (hit?.region) select(hit.region);
  const owner = hit?.id || hit?.region;
  gesture.start(
    { pointerId: e.pointerId, x: e.clientX, y: e.clientY },
    { node: owner ? graph.byId.get(owner) : null, pan, scale },
  );
  gesture.active.hit = hit;
  app.canvas.style.cursor = owner ? "grabbing" : "move";
});
app.canvas.addEventListener("pointermove", (e) => {
  const move = gesture.move({ pointerId: e.pointerId, x: e.clientX, y: e.clientY });
  if (!move) return;
  if (move.kind === "node") setPosition(graph, preferences, move.id, move.x, move.y);
  else pan = { x: move.x, y: move.y };
  schedule();
});
function endDrag(e, cancelled = false) {
  const gestureEnd = gesture.end(e.pointerId);
  if (!gestureEnd) return;
  app.canvas.style.cursor = "default";
  if (!gestureEnd.moved && !cancelled) {
    const h = gestureEnd.hit;
    if (h?.expand) toggle(h.expand);
    else if (h?.region) select(h.region);
    else if (h?.edge) showEdge(h.edge);
    else if (!h) select(null);
  }
  save();
  schedule();
}
app.canvas.addEventListener("pointerup", (e) => endDrag(e));
app.canvas.addEventListener("pointercancel", (e) => endDrag(e, true));
app.canvas.addEventListener("lostpointercapture", (e) => endDrag(e, true));
app.canvas.addEventListener("dblclick", (e) => {
  const h = hitAt(e);
  if (h?.id) toggle(h.id);
  else if (h?.region) toggle(h.region);
});
app.canvas.addEventListener(
  "wheel",
  (e) => {
    e.preventDefault();
    const r = app.canvas.getBoundingClientRect();
    zoom(Math.exp(-e.deltaY * 0.0015), { x: e.clientX - r.left, y: e.clientY - r.top });
  },
  { passive: false },
);
$("viewport").addEventListener("keydown", (e) => {
  if (
    e.target.closest(
      "input,textarea,select,#node-details,#edge-details,#semantic-edges,#filter-panel,#legend-panel",
    )
  )
    return;
  if (e.key.toLowerCase() === "f") focusSelection();
  if (e.key === "0") fit();
  if (e.key === "+" || e.key === "=") zoom(1.15);
  if (e.key === "-") zoom(1 / 1.15);
  if (e.key.toLowerCase() === "p") pin();
  if (e.key === "Enter" && selected) {
    e.preventDefault();
    toggle(selected);
  }
  if (e.key === "Escape") {
    detailMode = null;
    select(null);
  }
  const delta = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] }[
    e.key
  ];
  if (delta) {
    e.preventDefault();
    const b = graph?.byId.get(selected),
      distance = e.shiftKey ? 80 : 20;
    cancelLayout();
    if (b)
      setPosition(graph, preferences, b.id, b.x + delta[0] * distance, b.y + delta[1] * distance);
    else {
      pan.x -= delta[0] * 50;
      pan.y -= delta[1] * 50;
    }
    save();
    schedule();
  }
});
$("fit").onclick = fit;
$("zoom-in").onclick = () => zoom(1.2);
$("zoom-out").onclick = () => zoom(1 / 1.2);
$("arrange").onclick = () => arrange();
$("undo-layout").onclick = () => {
  if (!undo) return;
  cancelLayout();
  preferences.positions = Object.assign(Object.create(null), JSON.parse(undo.positions));
  scale = undo.camera.scale;
  pan = undo.camera.pan;
  undo = null;
  $("undo-layout").disabled = true;
  project();
  save();
};
$("collapse").onclick = () => {
  cancelLayout();
  expanded.clear();
  selected = null;
  detailMode = null;
  project();
  fit();
  save();
};
$("focus-selection").onclick = focusSelection;
$("expand").onclick = () => {
  cancelLayout();
  const roots = graph.boxes.filter((b) => !b.node.parent).map((b) => b.id);
  for (const id of roots) expanded.add(id);
  project();
  for (const id of roots) settleExpansion(graph, preferences, id);
  fit();
  save();
};
$("node-expand").onclick = () => toggle(selected);
$("pin").onclick = pin;
$("details").onclick = () => showDetail("values");
$("source").onclick = () => showDetail("source");
$("close-detail").onclick = () => {
  detailMode = null;
  updateDetail();
  $("viewport").focus({ preventScroll: true });
};
$("annotate").onclick = editAnnotation;
function filteredSearch(query) {
  return searchNodes(graph.all, preferences, query, 1000)
    .filter(
      (result) =>
        filterNode(result.node, graph.all, preferences.filters) ||
        (graph.children.has(result.node.id) &&
          filterNode(result.node, graph.all, preferences.filters, true)),
    )
    .slice(0, 30);
}
function updateFilters() {
  $("filter-toggle").disabled = false;
  const filters = (preferences.filters = cleanFilters(preferences.filters));
  for (const input of $("filter-panel").querySelectorAll("input[data-filter]"))
    input.checked = filters[input.dataset.filter].includes(input.value);
  const depth = $("filter-depth"),
    max = Math.max(
      0,
      ...[...graph.all.keys()].map((id) => ancestorsToReveal(graph.all, id).length),
    );
  if (depth.dataset.max !== String(max)) {
    depth.replaceChildren(
      new Option(boTranslate("All levels"), "all"),
      ...Array.from(
        { length: max + 1 },
        (_, i) =>
          new Option(
            i ? boTranslate("Level ") + i + boTranslate(" ") : boTranslate("Top level"),
            String(i),
          ),
      ),
    );
    depth.dataset.max = String(max);
  }
  depth.value = String(filters.depth);
  const profile = currentProfile();
  $("filter-scope").value = profile.scope;
  $("filter-query").value = profile.query;
  const active = JSON.stringify(filters) !== JSON.stringify(emptyFilters());
  $("filter-toggle").textContent = active
    ? boTranslate("Filters \u00B7 active")
    : boTranslate("Filters");
  $("filter-count").textContent = boTranslate(
    "Showing {0} nodes and {1} relations",
    new Set([...presentation.glyphs, ...presentation.regions]).size,
    renderedEdges.length,
  );
}
function applyFilters() {
  cancelLayout();
  preferences.filters = cleanFilters(preferences.filters);
  project();
  showSearch();
  save();
  schedule();
}
for (const kind of ["nodes", "edges", "regions"]) {
  const values =
    kind === "edges"
      ? Object.fromEntries(Object.entries(relationStyles).filter(([key]) => key !== "contains"))
      : nodeTypes;
  const host = $("filter-" + kind);
  for (const [value, style] of Object.entries(values)) {
    const label = document.createElement("label"),
      input = document.createElement("input"),
      name = document.createElement("span");
    input.type = "checkbox";
    input.dataset.filter = kind;
    input.value = value;
    input.checked = true;
    name.textContent = style.label;
    name.style.color = "#" + style.color.toString(16).padStart(6, "0");
    label.append(input, name);
    host.append(label);
    input.onchange = () => {
      preferences.filters[kind] = [...host.querySelectorAll("input:checked")].map((el) => el.value);
      applyFilters();
    };
  }
}
for (const button of $("filter-panel").querySelectorAll("button[data-filter-group]")) {
  button.onclick = () => {
    const key = button.dataset.filterGroup;
    preferences.filters[key] = button.dataset.all === "true" ? emptyFilters()[key] : [];
    applyFilters();
  };
}
$("filter-depth").onchange = (event) => {
  preferences.filters.depth = event.target.value === "all" ? "all" : Number(event.target.value);
  applyFilters();
};
$("filter-reset").onclick = () => {
  analysisOverride = null;
  const profile = profileFor(analysisId, analysisSettings.custom);
  preferences.filters = cleanFilters(profile);
  applyFilters();
};
$("filter-toggle").onclick = () => {
  const panel = $("filter-panel");
  panel.hidden = !panel.hidden;
  $("filter-toggle").setAttribute("aria-expanded", String(!panel.hidden));
};
$("close-filters").onclick = () => {
  $("filter-panel").hidden = true;
  $("filter-toggle").setAttribute("aria-expanded", "false");
  $("filter-toggle").focus();
};
$("filter-panel").onkeydown = (event) => {
  if (event.key === "Escape") $("close-filters").click();
};
function showSearch() {
  const list = $("search-results");
  list.replaceChildren();
  if (!graph || !$("node-search").value.trim()) {
    list.hidden = true;
    return;
  }
  const results = filteredSearch($("node-search").value);
  for (const result of results) {
    const button = document.createElement("button");
    button.type = "button";
    const title = document.createElement("strong"),
      description = document.createElement("span");
    const parent = graph.all.get(result.node.parent),
      context = parent ? displayName(parent, preferences) : "";
    title.textContent = result.name;
    description.textContent = result.node.field
      ? [
          context,
          result.node.direction === "in" ? boTranslate("Input") : boTranslate("Output"),
          result.node.fieldType,
        ]
          .filter(Boolean)
          .join(" · ")
      : [context, result.node.source?.symbol || result.node.id].filter(Boolean).join(" · ");
    button.append(title, description);
    button.onclick = () => revealResult(result.node.id);
    list.append(button);
  }
  if (!results.length) {
    const empty = document.createElement("p");
    empty.textContent = boTranslate("No nodes found");
    list.append(empty);
  }
  list.hidden = false;
}
function revealResult(id) {
  if (!graph?.all.has(id)) return;
  if (
    ["python-ast", "source-ast"].includes(graph.all.get(id).origin) ||
    graph.all.get(id).analysis_level === "advanced"
  ) {
    analysisSettings.advanced = true;
    updateAnalysisOptions();
  }
  cancelLayout();
  for (const parent of ancestorsToReveal(graph.all, id)) expanded.add(parent);
  project();
  select(id);
  const box = graph.byId.get(id);
  if (box?.open && box.kids.length) focusSelection();
  else if (box) {
    scale = Math.max(0.8, scale);
    const p = point(box);
    pan = { x: app.screen.width / 2 - p.x * scale, y: app.screen.height / 2 - p.y * scale };
  }
  $("search-results").hidden = true;
  save();
  schedule();
  $("viewport").focus({ preventScroll: true });
}
$("node-search").oninput = showSearch;
$("node-search").onfocus = showSearch;
$("node-search").onkeydown = (e) => {
  if (e.key === "Escape") $("search-results").hidden = true;
  if (e.key === "Enter") {
    e.preventDefault();
    const first = graph && filteredSearch(e.target.value)[0];
    if (first) revealResult(first.node.id);
  }
};
document.addEventListener("pointerdown", (e) => {
  if (!e.target.closest(".graph-search")) $("search-results").hidden = true;
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && !e.target.closest("#viewport,.graph-search,input,textarea,select")) {
    select(null);
    $("viewport").focus({ preventScroll: true });
  }
});
$("attempt").onchange = (e) => {
  choice = e.target.value;
  step = "latest";
  lastKey = "";
  project();
};
$("step").onchange = (e) => {
  step = e.target.value;
  project();
  updateFacts();
};
const resizeObserver = new ResizeObserver(() => {
  if (!disposed) {
    app.renderer.resize($("viewport").clientWidth, $("viewport").clientHeight);
    schedule();
  }
});
resizeObserver.observe($("viewport"));
function updateFacts() {
  if (!view) return;
  const state = selectedConfiguration(view, choice, step),
    p = view.authority.parameters;
  const phase =
    step !== "latest" ? state?.phase : choice === "latest" ? view.machine.current : state?.phase;
  $("phase").textContent = phase
    ? boTranslate("Flow state: ") + phaseLabel(view.model, phase)
    : step !== "latest"
      ? boTranslate("Inspecting internal activity; no flow state recorded at this step")
      : boTranslate("No runtime records");
  $("context").textContent =
    parameterSummary(view, state, step) ||
    boTranslate("Parameter version {0}", state?.param_version ?? p.param_version ?? "—") +
      (step !== "latest" ? boTranslate(" \u00B7 step {0}", step) : "");
}
function frameLabel(entry) {
  const name = view.model.nodes.find((n) => n.id === entry.activity)?.label || entry.activity;
  return `${entry.seq} · ${entry.event === "join" ? (entry.after.join.state === "passed" ? boTranslate("All checks passed") : boTranslate("Some checks did not pass")) : entry.event === "abort" ? boTranslate("Checks stopped") : name + "：" + (stateLabels[entry.after.activities[entry.activity]] || entry.event)}`;
}
async function poll() {
  const requestedVersion = version,
    requestedCase = caseChoice;
  try {
    const r = await fetch(
      "/api/view?version=" +
        encodeURIComponent(version) +
        "&case=" +
        encodeURIComponent(caseChoice),
      { cache: "no-store" },
    );
    if (r.status === 404) {
      const error = await r.json();
      if (error.code === "bo_web_disabled") {
        stopPlayback();
        stopAnimation();
        changeView();
        $("connection").textContent = boTranslate("Debug Web is disabled");
        $("empty").hidden = false;
        $("empty").textContent = boTranslate("Re-enable Web in the development tool to continue.");
        return;
      }
    }
    if (!r.ok) throw Error("HTTP " + r.status);
    const next = await r.json();
    if (disposed || version !== requestedVersion || caseChoice !== requestedCase) return;
    const key = renderRevision(next, [version, caseChoice, choice, step]);
    const previousLive = latestLive;
    latestLive = next;
    document.querySelector(".record-bar").hidden = next.stage === "design";
    $("program-link").hidden = next.stage === "design";
    if (Object.hasOwn(next, "program_url")) {
      const url = next.program_url ? new URL(next.program_url, location.href) : null;
      const safe =
        url &&
        ["http:", "https:"].includes(url.protocol) &&
        ["localhost", "127.0.0.1"].includes(url.hostname);
      $("program-link").hidden = next.stage === "design" || !safe;
      if (safe) $("program-link").href = url.href;
    }
    if (next.stage !== "design") await refreshRecordings(next);
    if (recording) {
      $("connection").textContent = boTranslate("Connected \u00B7 recorded replay");
      return;
    }
    view = next;
    $("title").textContent =
      (view.model.presentation.subject || boTranslate("Application")) +
      (next.stage === "design"
        ? boTranslate(" \u00B7 design graph")
        : boTranslate(" \u00B7 runtime graph"));
    const baseKey = layoutKey(
      next.layout_id
        ? { ...view.model, presentation: { ...view.model.presentation, layout_id: next.layout_id } }
        : view.model,
    );
    loadAnalysis(baseKey);
    const nextStorageKey = baseKey + (analysisId === "overview" ? "" : ":view:" + analysisId);
    if (nextStorageKey !== storageKey) {
      cancelLayout();
      const restored = readLayout(storage, nextStorageKey);
      preferences = restored.state;
      storageKey = nextStorageKey;
      if (!restored.restored)
        preferences.filters = cleanFilters(profileFor(analysisId, analysisSettings.custom));
      if (analysisSettings.annotations) preferences.annotations = analysisSettings.annotations;
      selected = preferences.focus;
      expanded = new Set(restored.restored ? preferences.expanded : []);
      if (preferences.camera) {
        scale = preferences.camera.scale;
        pan = { x: preferences.camera.x, y: preferences.camera.y };
      }
      first = true;
      $("layout").value = preferences.algorithm;
    }
    const cases = next.available_cases || [];
    if (JSON.stringify([cases, version]) !== $("case").dataset.options) {
      $("case").replaceChildren(
        ...cases.map(
          (v) =>
            new Option(
              v === "live" ? boTranslate("Current operation") : next.case_names?.[v] || v,
              v,
            ),
        ),
      );
      $("case").dataset.options = JSON.stringify([cases, version]);
      if (cases.includes(caseChoice)) $("case").value = caseChoice;
    }
    const gaps =
      next.health.errors +
      next.health.dropped +
      (next.health.parse_errors || 0) +
      (next.health.truncated || 0);
    $("connection").textContent = contextLost
      ? boTranslate("Graphics connection lost; recovering")
      : gaps
        ? boTranslate("Missing ") + gaps + boTranslate(" records")
        : next.historical
          ? boTranslate("Saved run")
          : boTranslate("Connected");
    const stale = next.binding_status.status !== "current";
    $("binding").textContent = stale
      ? boTranslate("Application has not loaded the new code")
      : boTranslate("Build ") + next.manifest.build_id.slice(0, 8);
    $("binding").classList.toggle("stale", stale);
    if (stale && !contextLost)
      $("connection").textContent =
        next.stage === "design"
          ? boTranslate("Design declaration \u00B7 not implemented")
          : boTranslate("Application has not loaded the new code");
    if (key !== lastKey) {
      lastKey = key;
      const run = selectedConfiguration(view, choice);
      $("step").replaceChildren(
        new Option(boTranslate("Latest state"), "latest"),
        ...(run?.journal || []).map((e) => new Option(frameLabel(e), String(e.seq))),
      );
      if (run?.journal.some((e) => String(e.seq) === step)) $("step").value = step;
      else step = "latest";
      const select = $("attempt");
      select.replaceChildren(new Option(boTranslate("Current run"), "latest"));
      const runs = configurations(view);
      if (runs.length)
        runs.forEach((run, i) =>
          select.add(
            new Option(
              boTranslate("Run {0} \u00B7 version {1}", i + 1, run.param_version) +
                (run.disposition === "superseded"
                  ? boTranslate(" (older version)")
                  : run.disposition === "interrupted"
                    ? boTranslate(" (interrupted)")
                    : ""),
              run.attempt,
            ),
          ),
        );
      else
        for (const id of executionIds(view)) select.add(new Option(boTranslate("Run ") + id, id));
      select.value = choice;
      const hasPositions = Object.keys(preferences.positions).length > 0;
      project();
      if (first) {
        first = false;
        if (!hasPositions) arrange(true);
        else if (!preferences.camera) fit();
      }
      saveSoon();
    }
    await conversation.refresh();
    updateFacts();
    const newest = next.events.at(-1);
    if (newest && newest.id !== lastLiveEvent) {
      if (previousLive && lastLiveEvent) boUpdateLive(previousLive, next);
      lastLiveEvent = newest.id;
    }
  } catch (error) {
    if (disposed) return;
    console.error(error);
    $("connection").textContent = boTranslate("Cannot connect to the application");
    if (!view) {
      $("empty").hidden = false;
      $("empty").textContent = boTranslate("Waiting for the application to connect.");
    }
  }
}
function changeView() {
  cancelLayout();
  choice = "latest";
  step = "latest";
  lastKey = "";
  detailMode = null;
  selectedEdge = null;
  view = null;
  graph = null;
  renderer.clear();
  presentation = null;
  app.renderer.render(app.stage);
  $("node-details").hidden = true;
  $("edge-details").hidden = true;
}
$("version").onchange = (e) => {
  version = e.target.value;
  caseChoice = "live";
  changeView();
};
$("case").onchange = (e) => {
  caseChoice = e.target.value;
  changeView();
};
function loadAnalysis(baseKey) {
  const key = baseKey + ":analysis";
  if (analysisKey === key) return;
  analysisKey = key;
  let saved;
  try {
    saved = JSON.parse(storage.getItem(key));
  } catch {}
  analysisSettings = {
    advanced: false,
    custom: [],
    overrides: Object.create(null),
    selected: "overview",
    annotations: null,
  };
  if (saved) {
    analysisSettings.advanced = saved.advanced === true;
    analysisSettings.custom = (Array.isArray(saved.custom) ? saved.custom : [])
      .slice(0, 20)
      .filter(
        (p) =>
          typeof p.id === "string" &&
          /^custom-[a-z0-9-]+$/.test(p.id) &&
          typeof p.label === "string",
      )
      .map((p) => ({ ...cleanProfile(p), id: p.id, label: p.label.slice(0, 40) }));
    for (const [id, p] of Object.entries(saved.overrides || {}))
      if (presets.some((x) => x.id === id) || analysisSettings.custom.some((x) => x.id === id))
        analysisSettings.overrides[id] = cleanProfile(p);
    if (saved.annotations && typeof saved.annotations === "object")
      analysisSettings.annotations = saved.annotations;
    if ([...presets, ...analysisSettings.custom].some((p) => p.id === saved.selected))
      analysisSettings.selected = saved.selected;
  }
  analysisId = analysisSettings.selected;
  analysisOverride = analysisSettings.overrides[analysisId] || null;
  updateAnalysisOptions();
}
function currentProfile() {
  const p = analysisOverride || profileFor(analysisId, analysisSettings?.custom);
  return cleanProfile({ ...p, ...preferences?.filters });
}
function saveAnalysis() {
  if (!analysisKey || !analysisSettings) return;
  analysisSettings.selected = analysisId;
  analysisSettings.annotations = preferences?.annotations || analysisSettings.annotations;
  if (analysisOverride) analysisSettings.overrides[analysisId] = analysisOverride;
  else delete analysisSettings.overrides[analysisId];
  try {
    storage.setItem(analysisKey, JSON.stringify(analysisSettings));
  } catch {}
}
function updateAnalysisOptions() {
  $("analysis-view").replaceChildren(
    ...[...presets, ...analysisSettings.custom].map((p) => new Option(p.label, p.id)),
  );
  $("analysis-details").setAttribute("aria-pressed", String(analysisSettings.advanced));
  $("analysis-view").value = analysisId;
  $("delete-view").hidden = !analysisId.startsWith("custom-");
}
function changeAnalysis(id) {
  if (!analysisSettings || id === analysisId) return;
  stopPlayback();
  cancelLayout();
  save();
  clearTimeout(saveTimer);
  analysisId = id;
  if (!["overview", "business"].includes(id)) analysisSettings.advanced = true;
  analysisOverride = analysisSettings.overrides[id] || null;
  saveAnalysis();
  updateAnalysisOptions();
  const base = analysisKey.slice(0, -":analysis".length),
    key = base + (id === "overview" ? "" : ":view:" + id),
    restored = readLayout(storage, key);
  preferences = restored.state;
  storageKey = key;
  if (!restored.restored)
    preferences.filters = cleanFilters(profileFor(id, analysisSettings.custom));
  if (analysisSettings.annotations) preferences.annotations = analysisSettings.annotations;
  expanded = new Set(restored.state.expanded);
  if (!restored.restored && id === "shared")
    expanded = new Set(sharedMemberships(view.model).map((m) => m.group));
  selected = preferences.focus;
  detailMode = null;
  undo = null;
  $("undo-layout").disabled = true;
  $("layout").value = preferences.algorithm;
  project();
  if (preferences.camera) {
    scale = preferences.camera.scale;
    pan = { x: preferences.camera.x, y: preferences.camera.y };
    schedule();
  } else arrange();
  saveSoon();
}
$("analysis-details").onclick = () => {
  if (!analysisSettings) return;
  analysisSettings.advanced = !analysisSettings.advanced;
  updateAnalysisOptions();
  project();
  saveSoon();
};
$("analysis-view").onchange = (e) => changeAnalysis(e.target.value);
$("filter-scope").onchange = (e) => {
  analysisOverride = { ...currentProfile(), scope: e.target.value, hierarchical: false };
  applyFilters();
  arrange();
};
$("filter-query").onchange = (e) => {
  analysisOverride = { ...currentProfile(), query: e.target.value, hierarchical: false };
  applyFilters();
  arrange();
};
$("save-view").onsubmit = (e) => {
  e.preventDefault();
  if (!analysisSettings) return;
  const label = $("custom-view-name").value.trim();
  if (!label) return;
  const existing = analysisSettings.custom.find((p) => p.label === label);
  if (!existing && analysisSettings.custom.length >= 20) {
    $("filter-count").textContent = boTranslate(
      "Up to 20 custom views can be saved. Delete one first.",
    );
    return;
  }
  const id = existing?.id || "custom-" + Date.now().toString(36),
    profile = { ...currentProfile(), hierarchical: false, id, label };
  analysisSettings.custom = analysisSettings.custom.filter((p) => p.id !== id).concat(profile);
  // A saved view starts from the arrangement the developer is looking at.
  save();
  writeLayout(storage, analysisKey.slice(0, -":analysis".length) + ":view:" + id, preferences);
  saveAnalysis();
  updateAnalysisOptions();
  changeAnalysis(id);
  $("filter-count").textContent = boTranslate("Saved \u201C") + label + "」";
};
$("delete-view").onclick = () => {
  const old = analysisId;
  changeAnalysis("overview");
  analysisSettings.custom = analysisSettings.custom.filter((p) => p.id !== old);
  delete analysisSettings.overrides[old];
  saveAnalysis();
  updateAnalysisOptions();
};
$("reference-origin").onclick = () => {
  const id = graph?.byId.get(selected)?.node.referenceOf;
  if (!id) return;
  if (analysisId !== "overview") changeAnalysis("overview");
  revealResult(id);
  focusSelection();
};
const legendHost = $("node-legend");
legendHost.replaceChildren();
for (const [type, style] of Object.entries(nodeTypes)) {
  const compact = document.createElement("span");
  compact.append(legendGlyph(type, style), document.createTextNode(style.label));
  legendHost.append(compact);
  const row = document.createElement("div"),
    label = document.createElement("div"),
    description = document.createElement("span");
  label.textContent = style.label;
  description.textContent = meanings[type];
  label.append(description);
  row.append(legendGlyph(type, style), label);
  $("legend-types").append(row);
}
const edgeLegend = document.querySelector(".relation-legend");
edgeLegend.replaceChildren();
for (const [type, style] of Object.entries(relationStyles))
  if (!["contains", "other"].includes(type)) {
    const label = document.createElement("span");
    label.append(legendRelation(style), document.createTextNode(style.label));
    edgeLegend.append(label);
  }
const runtimeLegend = document.createElement("span");
runtimeLegend.className = "runtime-key";
runtimeLegend.textContent = boTranslate("\u25CF Runtime evidence");
edgeLegend.append(runtimeLegend);
function boVisible() {
  return graph.boxes.filter((b) => presentation.glyphs.has(b.id) || presentation.regions.has(b.id));
}
function boText(value, row) {
  return boDisplayValue(value, view.model, row);
}
function boChangeText(row) {
  return `${row.field}: ${boText(row.before, row)} → ${boText(row.after, row)}`;
}
function boShowChanges() {
  const panel = $("step-changes");
  panel.hidden = !boDetail;
  if (!boDetail) return;
  $("change-title").textContent =
    boDetail.event.kind === "start"
      ? boTranslate("Recording started")
      : boDetail.event.kind === "end"
        ? boTranslate("Recording stopped")
        : eventLabel(boDetail.event, view.model);
  $("change-count").textContent = boDetail.rows.length
    ? boTranslate("{0} changes", boDetail.rows.length)
    : boTranslate("No visible value changes");
  $("change-rows").replaceChildren(
    ...boDetail.rows.map((row) => {
      const line = document.createElement("div");
      line.className = "change-row";
      line.dataset.eventId = row.event;
      line.dataset.owner = row.owner;
      line.dataset.kind = row.kind;
      const kind = document.createElement("span");
      kind.className = "change-kind";
      kind.textContent = boKinds[row.kind].label;
      kind.style.color = "#" + boKinds[row.kind].color.toString(16).padStart(6, "0");
      const node = document.createElement("button");
      node.textContent = row.sourceLabel;
      node.onclick = () => {
        select(row.owner);
        focusSelection();
      };
      const value = document.createElement("span");
      value.className = "change-value";
      value.append(document.createTextNode(row.field + ": "));
      const before = document.createElement("del"),
        after = document.createElement("ins");
      before.textContent = boText(row.before, row);
      after.textContent = boText(row.after, row);
      value.append(before, document.createTextNode(" → "), after);
      line.append(kind, node, value);
      return line;
    }),
  );
  for (const button of $("semantic").children) {
    const rows = boDetail.rows.filter((r) => r.owner === button.dataset.nodeId);
    button.dataset.changes = JSON.stringify(
      rows.map((r) => ({ field: r.field, before: r.before, after: r.after, kind: r.kind })),
    );
  }
}
function boSetTransfers(events) {
  boTransfers.clear();
  for (const event of events) {
    const configuration = (
      recording?.final.machine.configurations ||
      view.machine.configurations ||
      []
    ).find((c) => c.attempt === event.attempt);
    for (const id of transferEdges(event, view.events, renderedEdges, graph.all, configuration)) {
      const edge = renderedEdges.find((e) => e.id === id),
        entry = configuration?.journal?.find((j) => j.seq === event.outputs?.revision);
      const reverse =
        edge.type === "resource"
          ? entry?.event !== "start"
          : edge.type === "call" && ["return", "decision", "error"].includes(event.phase);
      boTransfers.set(id, {
        event,
        label: boTransferLabel(edge, event, configuration),
        type: edge.type,
        reverse,
      });
    }
  }
  for (const el of $("semantic-edges").children)
    el.dataset.payload = boTransfers.get(el.dataset.edgeId)?.label || "";
}
function boUpdateReplay() {
  if (!recording || !graph) return;
  const visible = boVisible(),
    key = JSON.stringify([
      recording.id,
      $("replay-grain").value,
      visible.map((b) => [b.id, b.type]),
    ]);
  if (key !== boPlanKey) {
    boPlanKey = key;
    boPlan = boStepPlan(recording, replayItems, graph.all, visible, {
      mode: $("replay-grain").value,
    });
    $("replay-range").max = boPlan.length - 1;
    $("replay-events").replaceChildren(
      ...boPlan.map(
        (raw, i) =>
          new Option(
            `${i + 1} · ${eventLabel(replayItems[raw], recording.context.model)}`,
            String(raw),
          ),
      ),
    );
  }
  const previous = boPlan.filter((i) => i < replayIndex).at(-1) ?? -1,
    position = Math.max(0, boPlan.filter((i) => i <= replayIndex).length - 1),
    item = replayItems[replayIndex];
  boDetail = boStepDetail(recording, replayItems, replayIndex, previous, graph.all, visible, {
    mode: $("replay-grain").value,
  });
  boShowChanges();
  boSetTransfers(replayItems.slice(Math.max(1, previous + 1), replayIndex + 1));
  $("replay-range").value = position;
  $("replay-events").value = String(boPlan[position]);
  $("replay-position").value = `${position + 1} / ${boPlan.length}`;
  Object.assign($("replay-position").dataset, {
    eventId: item.id,
    rawIndex: String(replayIndex),
    rawCount: String(replayItems.length),
    stepCount: String(boPlan.length),
  });
  $("replay-note").textContent = recording.gaps.length
    ? boTranslate("Recording gap: ") + recording.gaps.join("；")
    : recording.capture?.mode === "focused"
      ? boTranslate("Focused recording \u00B7 outside scope not captured")
      : boTranslate("{0} raw events", recording.events.length);
  $("replay-prev").disabled = replayIndex === 0;
  $("replay-next").disabled = replayIndex === replayItems.length - 1;
  $("replay-locate").disabled = !item.node;
}
function boUpdateLive(before, after) {
  const known = new Set(before.events.map((e) => e.id)),
    events = after.events.filter((e) => !known.has(e.id));
  if (!events.length) return;
  const sample = { context: before, final: after, events, commands: [], status: "recording" },
    items = timeline(sample);
  boDetail = boStepDetail(sample, items, items.length - 1, 0, graph.all, boVisible());
  boShowChanges();
  boSetTransfers(events);
  animateEvent(events.at(-1));
  schedule();
}
function boCaptureScope() {
  if ($("capture-mode").value === "all") return { mode: "all" };
  const box = graph?.byId.get(selected);
  if (!box) throw Error(boTranslate("Select a node or region to record"));
  const id = box.node.referenceOf || box.node.event_node || box.id,
    known = new Set(view.model.nodes.map((n) => n.id));
  const root = known.has(id)
    ? id
    : box.type === "state"
      ? view.model.machine.execution?.parent
      : null;
  if (!root) throw Error(boTranslate("This node has no capture binding"));
  return { mode: "focused", roots: [root] };
}
function stopAnimation() {
  cancelAnimationFrame(animationFrame);
  animationFrame = null;
  animationDot.clear();
  animationUntil = 0;
  $("renderer").dataset.animationActive = "false";
  if (!disposed && !contextLost) app.renderer.render(app.stage);
}
function animateEvent(event) {
  if (!graph || disposed || document.hidden || contextLost) return;
  stopAnimation();
  animationEvent = event;
  animatedIds = [...boTransfers.keys()];
  if (!animatedIds.length)
    animatedIds = transferEdges(event, view.events, renderedEdges, graph.all, graph.configuration);
  $("renderer").dataset.animatedEdges = JSON.stringify(animatedIds);
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const started = performance.now();
  animationUntil = started + 650;
  const tick = (now) => {
    if (now >= animationUntil || disposed || document.hidden || contextLost) {
      stopAnimation();
      return;
    }
    animationLayer.position.set(pan.x, pan.y);
    animationLayer.scale.set(scale);
    animationDot.clear();
    const t = (now - started) / 650;
    for (const id of animatedIds) {
      const path = edgePaths.get(id);
      if (path) {
        const p = bezierAt(path, boTransfers.get(id)?.reverse ? 1 - t : t);
        const edge = renderedEdges.find((e) => e.id === id),
          style = relationStyles[edge?.type] || relationStyles.other,
          r = 5 / scale;
        if (["guard", "transition"].includes(edge?.type))
          animationDot
            .poly([p.x, p.y - r, p.x + r, p.y, p.x, p.y + r, p.x - r, p.y])
            .fill(style.color);
        else if (["data", "resource"].includes(edge?.type))
          animationDot.rect(p.x - r, p.y - r, 2 * r, 2 * r).fill(style.color);
        else animationDot.circle(p.x, p.y, r).fill(style.color);
      }
    }
    const node = graph.boxes.find(
      (b) =>
        (boDetail?.rows.some((r) => r.owner === b.id) ||
          (b.node.referenceOf || b.node.event_node || b.id) === event.node) &&
        (presentation.glyphs.has(b.id) || presentation.regions.has(b.id)),
    );
    if (node) {
      const p = point(node),
        region = presentation.regions.has(node.id) && graph.regions.find((r) => r.id === node.id);
      animationDot
        .circle(p.x, p.y, (region?.radius || 32) + 10 * t)
        .stroke({ color: 0x238065, width: 2 / scale, alpha: 1 - t });
    }
    $("renderer").dataset.animationActive = "true";
    app.renderer.render(app.stage);
    animationFrame = requestAnimationFrame(tick);
  };
  animationFrame = requestAnimationFrame(tick);
}
async function refreshRecordings(next, force = false) {
  $("record-start").disabled =
    recordBusy ||
    recordActive ||
    !!recording ||
    next.historical ||
    next.binding_status.status !== "current";
  if (!force && Date.now() - lastRecordPoll < 2000) return;
  lastRecordPoll = Date.now();
  try {
    const listing = await recordingRequest("");
    recordActive = !!listing.active;
    $("capture-mode").disabled = recordActive || !!recording;
    $("record-start").disabled ||= !!listing.active;
    $("record-stop").disabled = recordBusy || !listing.active;
    const selected = recording?.id || "",
      options = listing.recordings.filter((r) => r.status !== "recording");
    const optionKey = JSON.stringify(options.map((r) => [r.id, r.events, r.status, r.gaps]));
    if ($("record-list").dataset.options !== optionKey) {
      $("record-list").replaceChildren(
        new Option(boTranslate("Live observation"), ""),
        ...options.map(
          (r) =>
            new Option(
              boTranslate(
                "{0} \u00B7 {1} events{2}{3}",
                new Date(r.started_at).toLocaleTimeString(),
                r.events,
                r.capture?.mode === "focused" ? boTranslate(" \u00B7 focused") : "",
                r.gaps.length ? boTranslate(" \u00B7 gaps") : "",
              ),
              r.id,
            ),
        ),
      );
      $("record-list").dataset.options = optionKey;
    }
    $("record-list").value = selected;
    const scopeName =
      listing.active?.capture?.mode === "focused"
        ? listing.active.capture.roots
            .map((id) => next.model.nodes.find((n) => n.id === id)?.label || id)
            .join("、")
        : "";
    $("record-status").textContent = listing.active
      ? boTranslate(
          "{0} \u00B7 {1} events",
          scopeName ? boTranslate("Only ") + scopeName : boTranslate("Recording"),
          listing.active.events,
        )
      : listing.error
        ? listing.error
        : recording
          ? ""
          : boTranslate("Only connected core events are captured");
  } catch (error) {
    $("record-status").textContent = error.message;
    $("record-start").disabled = true;
  }
}
$("record-start").onclick = async () => {
  recordBusy = true;
  try {
    const scope = boCaptureScope();
    await recordingRequest("/start", { scope });
    await refreshRecordings(latestLive, true);
  } catch (error) {
    $("record-status").textContent = error.message;
  } finally {
    recordBusy = false;
    lastRecordPoll = 0;
  }
};
$("record-stop").onclick = async () => {
  recordBusy = true;
  $("record-stop").disabled = true;
  try {
    const saved = await recordingRequest("/stop", {});
    await openRecording(saved.id);
    await refreshRecordings(latestLive, true);
  } catch (error) {
    $("record-status").textContent = error.message;
  } finally {
    recordBusy = false;
    lastRecordPoll = 0;
  }
};
function stopPlayback() {
  clearTimeout(playTimer);
  playTimer = null;
  $("replay-play").textContent = boTranslate("Play");
}
function seek(index, locate = false) {
  if (!recording) return;
  replayIndex = Math.max(0, Math.min(replayItems.length - 1, Number(index) || 0));
  choice = "latest";
  step = "latest";
  view = frame(recording, replayIndex, replayItems);
  project();
  updateFacts();
  const item = replayItems[replayIndex];
  if (locate && item.node) {
    if (!graph.byId.has(item.node) && analysisId !== "overview") changeAnalysis("overview");
    revealResult(item.node);
  }
  animateEvent(item);
}
async function openRecording(id) {
  stopPlayback();
  stopAnimation();
  const saved = await recordingRequest("/" + encodeURIComponent(id));
  if (saved.schema !== "stategraph-recording/v1")
    throw Error(boTranslate("Unsupported recording format"));
  recording = saved;
  replayItems = timeline(saved);
  boPlanKey = "";
  $("replay").hidden = false;
  document.body.classList.add("is-replay");
  for (const id of ["version", "case", "attempt", "step"]) $(id).disabled = true;
  seek(0);
}
function leaveRecording() {
  stopPlayback();
  stopAnimation();
  recording = null;
  boDetail = null;
  boTransfers.clear();
  $("step-changes").hidden = true;
  $("replay").hidden = true;
  document.body.classList.remove("is-replay");
  $("record-list").value = "";
  for (const id of ["version", "case", "attempt", "step"]) $(id).disabled = false;
  lastKey = "";
  lastRecordPoll = 0;
  poller.run();
}
$("record-list").onchange = async (e) => {
  if (!e.target.value) return leaveRecording();
  try {
    await openRecording(e.target.value);
  } catch (error) {
    $("record-status").textContent = error.message;
  }
};
$("replay-live").onclick = leaveRecording;
$("replay-range").oninput = (e) => {
  stopPlayback();
  seek(boPlan[Number(e.target.value)]);
};
$("replay-events").onchange = (e) => {
  stopPlayback();
  seek(Number(e.target.value));
};
$("replay-prev").onclick = () => {
  stopPlayback();
  seek(boPlan.filter((i) => i < replayIndex).at(-1) ?? 0);
};
$("replay-next").onclick = () => {
  stopPlayback();
  seek(boPlan.find((i) => i > replayIndex) ?? replayIndex);
};
$("replay-locate").onclick = () => seek(replayIndex, true);
$("replay-grain").onchange = () => {
  stopPlayback();
  boPlanKey = "";
  boUpdateReplay();
  schedule();
};
$("replay-play").onclick = () => {
  if (playTimer) return stopPlayback();
  if (replayIndex >= replayItems.length - 1) seek(0);
  const advance = () => {
    const next = boPlan.find((i) => i > replayIndex);
    if (next === undefined) return stopPlayback();
    seek(next);
    playTimer = setTimeout(advance, Number($("replay-speed").value));
  };
  $("replay-play").textContent = boTranslate("Pause");
  playTimer = setTimeout(advance, Number($("replay-speed").value));
};
$("replay-export").onclick = () => {
  if (!recording) return;
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(recording, null, 2)], { type: "application/json" }),
  );
  const link = document.createElement("a");
  link.href = url;
  link.download = "stategraph-" + recording.id + ".json";
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
};
// Read-only debugging data; UI actions use the same pointer/keyboard handlers as users.
window.graphDebug = {
  get graph() {
    return graph;
  },
  get view() {
    return view;
  },
  get camera() {
    return { scale, pan: { ...pan } };
  },
  get metrics() {
    return { ...metrics, drawCount: renderer.frames, webgl: !!app.renderer.gl };
  },
  get layoutBusy() {
    return layoutBusy;
  },
};
const conversation = createConversationFocus({
  onFocus: showDiscussion,
  onClear: () => schedule(),
});
const poller = createPoller(poll, { enabled: () => !disposed && !document.hidden });
poller.run();
