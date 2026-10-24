import { initialize, t, locale, onLanguageChange } from "./site-ui.mjs?rev=0.7.1";

const views = ["business", "state", "decision", "function", "data", "source", "mixed"];
let view = "business";
const colors = {
  business: "#2457db",
  state: "#8056a8",
  decision: "#a76b13",
  function: "#087f80",
  source: "#556774",
  data: "#9b4a82",
};
const escapeText = (value) =>
  String(value).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");

/** Draw concept nodes only; project-specific interactions live on demo.html. */
function node(id, label, x, y, type = "business") {
  const color = colors[type];
  const shapes = {
    business: '<circle r="27"/>',
    state: '<circle r="27"/>',
    decision: '<path d="M0 -28L28 0L0 28L-28 0Z"/>',
    function: '<path d="M0 -28L25 -14V14L0 28L-25 14V-14Z"/>',
    source: '<rect x="-32" y="-25" width="64" height="50" rx="6"/>',
    data: '<path d="M-28 -18C-28 -31 28 -31 28 -18V18C28 31 -28 31 -28 18ZM-28 -18C-28 -5 28 -5 28 -18"/>',
  };
  return `<g data-node="${id}" transform="translate(${x} ${y})">
    <g fill="${color}18" stroke="${color}" stroke-width="2">${shapes[type]}</g>
    <text y="55" text-anchor="middle">${escapeText(label)}</text>
  </g>`;
}

function edge(x1, y1, x2, y2, label, type = "business") {
  return `<g>
    <path d="M${x1} ${y1}L${x2} ${y2}" fill="none" stroke="${colors[type]}"
      stroke-width="1.5" marker-end="url(#arrow)" ${type === "source" ? 'stroke-dasharray="5 4"' : ""}/>
    <text x="${(x1 + x2) / 2}" y="${(y1 + y2) / 2 - 12}" class="svg-small" text-anchor="middle">
      ${escapeText(label)}
    </text>
  </g>`;
}

function diagram() {
  let content;
  const rows = {
    business: ["node.request", "node.process", "node.result", "edge.flow"],
    state: ["node.ready", "node.active", "node.complete", "edge.event"],
    decision: ["node.input", "node.check", "node.allowed", "edge.depends"],
    function: ["node.value", "node.function", "node.output", "edge.data"],
    source: ["entry()", "service()", "store()", "edge.call"],
    data: ["node.query", "node.store", "node.transform", "edge.read"],
  };
  if (view === "mixed") {
    const selected = [...document.querySelectorAll("#mix-filters input:checked")].map(
      (input) => input.value,
    );
    content =
      '<circle cx="300" cy="160" r="137" class="business-region"/>' +
      node("flow", t("diagram.flow"), 300, 85);
    selected.forEach((type, index) => {
      const x = 300 + (index - (selected.length - 1) / 2) * 100;
      content +=
        edge(300, 113, x, 213, "", type) +
        node(type, t("diagram." + (type === "decision" ? "rule" : type)), x, 240, type);
    });
  } else {
    const row = rows[view];
    content = edge(127, 150, 273, 150, t(row[3]), view) + edge(327, 150, 473, 150, t(row[3]), view);
    for (let index = 0; index < 3; index++) {
      content += node(
        "node-" + index,
        view === "source" ? row[index] : t(row[index]),
        100 + index * 200,
        150,
        view === "data" && index !== 1 ? "function" : view,
      );
    }
  }
  return (
    '<svg viewBox="0 0 600 330" role="img" aria-label="' +
    escapeText(t("level." + view + ".title")) +
    '"><defs><marker id="arrow" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto"><path d="M0 0L7 3.5L0 7" fill="#8095ac"/></marker></defs>' +
    content +
    "</svg>"
  );
}

/** View selection changes presentation only, leaving the concept relationships intact. */
function render() {
  document.title =
    locale() === "en"
      ? "VibeLens — Understand what you build"
      : "VibeLens · 看懂你正在开发的程序";
  document.querySelectorAll("[data-view]").forEach((button) => {
    const selected = button.dataset.view === view;
    button.setAttribute("aria-selected", String(selected));
    button.tabIndex = selected ? 0 : -1;
  });
  document.getElementById("view-panel").setAttribute("aria-labelledby", "tab-" + view);
  document.getElementById("mix-filters").hidden = view !== "mixed";
  document.getElementById("level-title").textContent = t("level." + view + ".title");
  document.getElementById("level-body").textContent = t("level." + view + ".body");
  document.getElementById("level-number").textContent =
    String(views.indexOf(view) + 1).padStart(2, "0") +
    " / " +
    String(views.length).padStart(2, "0");
  document.getElementById("concept-graph").innerHTML = diagram();
  document.getElementById("install-prompt").textContent = t("install.prompt");
}
document.querySelectorAll("[data-view]").forEach((button) => {
  button.addEventListener("click", () => {
    view = button.dataset.view;
    render();
  });
  button.addEventListener("keydown", (event) => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    let index = views.indexOf(view);
    index =
      event.key === "Home"
        ? 0
        : event.key === "End"
          ? views.length - 1
          : (index + (event.key === "ArrowRight" ? 1 : -1) + views.length) % views.length;
    view = views[index];
    render();
    document.getElementById("tab-" + view).focus();
  });
});
document
  .querySelectorAll("#mix-filters input")
  .forEach((input) => input.addEventListener("change", render));
document.getElementById("copy-prompt").addEventListener("click", async () => {
  const status = document.getElementById("copy-status");
  try {
    await navigator.clipboard.writeText(t("install.prompt"));
    status.textContent = t("copy.done");
  } catch {
    status.textContent = t("copy.failed");
  }
});
onLanguageChange(render);
initialize();
