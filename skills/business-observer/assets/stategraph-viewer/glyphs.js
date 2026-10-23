import { t as boTranslate } from "./i18n.js";
// One geometry source for WebGL nodes and the SVG legend.
export const meanings = {
  "code-file": boTranslate("Indexed source file"),
  "code-class": boTranslate("Declared class and its methods"),
  "code-function": boTranslate("Function found in source"),
  "code-parameter": boTranslate("Declared parameter and type"),
  "code-unresolved": boTranslate("External or dynamically resolved reference"),
  business: boTranslate("Business operation"),
  function: boTranslate("Function or method"),
  state: boTranslate("State in the state machine"),
  decision: boTranslate("Condition or rule"),
  resource: boTranslate("Available and occupied capacity"),
  data: boTranslate("Input, return value, or data"),
  effect: boTranslate("Committed effect"),
  wait: boTranslate("Waiting for a condition"),
  store: boTranslate("Configured database or storage"),
  dataset: boTranslate("Table, collection, key pattern, or graph label"),
  column: boTranslate("Field type and constraints"),
  query: boTranslate("Recorded database command or query"),
  transform: boTranslate("Application processing of data"),
};
export function glyphShapes(type) {
  if (type === "code-file")
    return [{ kind: "polygon", points: [-24, -28, 10, -28, 25, -12, 25, 28, -24, 28] }];
  if (type === "code-class") return [{ kind: "rect", x: -27, y: -26, w: 54, h: 52, r: 5 }];
  if (type === "code-parameter") return glyphShapes("data");
  if (type === "code-unresolved") return glyphShapes("decision");
  if (type === "store")
    return [
      { kind: "rect", x: -28, y: -20, w: 56, h: 42, r: 8 },
      { kind: "ellipse", cx: 0, cy: -18, rx: 28, ry: 8 },
    ];
  if (type === "dataset") return [{ kind: "rect", x: -29, y: -21, w: 58, h: 42, r: 3 }];
  if (type === "column") return [{ kind: "rect", x: -25, y: -15, w: 50, h: 30, r: 15 }];
  if (type === "query")
    return [{ kind: "polygon", points: [-29, -21, 16, -21, 30, 0, 16, 21, -29, 21, -17, 0] }];
  if (type === "transform")
    return [
      {
        kind: "polygon",
        points: [-15, -25, 15, -25, 28, -12, 28, 12, 15, 25, -15, 25, -28, 12, -28, -12],
      },
    ];
  if (type === "business") return [{ kind: "circle", r: 29 }];
  if (type === "state")
    return [
      { kind: "circle", r: 24 },
      { kind: "circle", r: 19, outline: true },
    ];
  if (type === "decision") return [{ kind: "polygon", points: [0, -27, 29, 0, 0, 27, -29, 0] }];
  if (type === "data") return [{ kind: "rect", x: -31, y: -19, w: 62, h: 38, r: 18 }];
  if (type === "effect") return [{ kind: "rect", x: -23, y: -23, w: 46, h: 46, r: 7 }];
  if (type === "resource")
    return [2, 1, 0].map((k) => ({
      kind: "rect",
      x: -25,
      y: -18 + k * 5,
      w: 50,
      h: 24,
      r: 7,
      opaque: true,
    }));
  if (type === "wait")
    return [{ kind: "polygon", points: [-22, -24, 22, -24, 12, 0, 22, 24, -22, 24, -12, 0] }];
  return [{ kind: "polygon", points: [-30, 0, -17, -23, 17, -23, 30, 0, 17, 23, -17, 23] }];
}
function mix(a, b, amount) {
  return [16, 8, 0].reduce(
    (value, shift) =>
      value |
      (Math.round(((a >> shift) & 255) * (1 - amount) + ((b >> shift) & 255) * amount) << shift),
    0,
  );
}
export function glyphAppearance(color, { core = false, selected = false, related = false } = {}) {
  const strong = core || selected;
  return {
    fill: strong ? mix(color, 0x142a40, 0.24) : mix(0xffffff, color, related ? 0.3 : 0.18),
    ink: strong ? 0xffffff : mix(color, 0x142a40, 0.55),
    border: color,
    emphasis: selected ? "selected" : core ? "core" : related ? "related" : "normal",
  };
}
export function drawGlyph(g, type, x, y, color, appearance = glyphAppearance(color)) {
  for (const s of glyphShapes(type)) {
    if (s.kind === "circle") g.circle(x, y, s.r);
    if (s.kind === "ellipse") g.ellipse(x + s.cx, y + s.cy, s.rx, s.ry);
    if (s.kind === "rect") g.roundRect(x + s.x, y + s.y, s.w, s.h, s.r);
    if (s.kind === "polygon") g.poly(s.points.map((v, i) => v + (i % 2 ? y : x)));
    if (!s.outline) g.fill({ color: appearance.fill, alpha: 1 });
    g.stroke({ color: s.outline ? appearance.ink : color, width: 1.8 });
  }
}
export function legendGlyph(type, style, options = {}) {
  const ns = "http://www.w3.org/2000/svg",
    svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", "-36 -36 72 72");
  svg.setAttribute("aria-hidden", "true");
  svg.dataset.glyph = type;
  const appearance = glyphAppearance(style.color, options),
    hex = (value) => "#" + value.toString(16).padStart(6, "0");
  const color = hex(style.color),
    ink = hex(appearance.ink);
  for (const s of glyphShapes(type)) {
    const el = document.createElementNS(ns, s.kind === "polygon" ? "polygon" : s.kind);
    if (s.kind === "circle") el.setAttribute("r", s.r);
    if (s.kind === "ellipse") for (const k of ["cx", "cy", "rx", "ry"]) el.setAttribute(k, s[k]);
    if (s.kind === "rect")
      for (const [k, v] of Object.entries({ x: s.x, y: s.y, width: s.w, height: s.h, rx: s.r }))
        el.setAttribute(k, v);
    if (s.kind === "polygon") el.setAttribute("points", s.points.join(" "));
    el.setAttribute("stroke", s.outline ? ink : color);
    el.setAttribute("stroke-width", "2");
    el.setAttribute("fill", s.outline ? "none" : hex(appearance.fill));
    svg.append(el);
  }
  const text = document.createElementNS(ns, "text");
  text.setAttribute("text-anchor", "middle");
  text.setAttribute("y", "7");
  text.setAttribute("font-size", "22");
  text.setAttribute("fill", ink);
  text.textContent = style.glyph;
  svg.append(text);
  return svg;
}
export function legendRelation(style) {
  const ns = "http://www.w3.org/2000/svg",
    svg = document.createElementNS(ns, "svg"),
    color = "#" + style.color.toString(16).padStart(6, "0");
  svg.setAttribute("viewBox", "0 0 44 20");
  svg.setAttribute("aria-hidden", "true");
  const line = document.createElementNS(ns, "path");
  line.setAttribute("d", "M2 10 H34");
  line.setAttribute("stroke", color);
  line.setAttribute("stroke-width", "2");
  line.setAttribute("stroke-dasharray", style.dash.join(" "));
  svg.append(line);
  if (style.arrow !== "none") {
    const arrow = document.createElementNS(ns, "path");
    arrow.setAttribute(
      "d",
      style.arrow === "bar"
        ? "M36 4 V16"
        : style.arrow === "diamond"
          ? "M40 10 L34 5 L28 10 L34 15 Z"
          : "M31 5 L39 10 L31 15" + (style.arrow === "filled" ? " Z" : ""),
    );
    arrow.setAttribute("stroke", color);
    arrow.setAttribute("stroke-width", "1.8");
    arrow.setAttribute(
      "fill",
      style.arrow === "filled" ? color : style.arrow === "diamond" ? "white" : "none",
    );
    svg.append(arrow);
  }
  return svg;
}
