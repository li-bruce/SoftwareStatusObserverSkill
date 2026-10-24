/** Small, accessible controls shared by the graph toolbar and context menus. */
const shapes = {
  record: [["circle", { cx: 12, cy: 12, r: 6, fill: "currentColor", stroke: "none" }]],
  stop: [
    ["rect", { x: 6, y: 6, width: 12, height: 12, rx: 1, fill: "currentColor", stroke: "none" }],
  ],
  clear: [
    ["circle", { cx: 12, cy: 12, r: 8 }],
    ["path", { d: "M6.3 17.7 17.7 6.3" }],
  ],
  play: [["path", { d: "m8 5 11 7-11 7Z", fill: "currentColor", stroke: "none" }]],
  pause: [["path", { d: "M9 5v14M15 5v14", "stroke-width": 4 }]],
  previous: [["path", { d: "M6 5v14m12-14-9 7 9 7Z" }]],
  next: [["path", { d: "M18 5v14M6 5l9 7-9 7Z" }]],
  fit: [["path", { d: "M4 9V4h5m6 0h5v5m0 6v5h-5M9 20H4v-5" }]],
  locate: [
    ["circle", { cx: 12, cy: 12, r: 6 }],
    ["path", { d: "M12 2v4m0 12v4M2 12h4m12 0h4" }],
  ],
  download: [["path", { d: "M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5" }]],
  live: [["path", { d: "M4 12h13m-5-5 5 5-5 5M21 5v14" }]],
  plus: [["path", { d: "M5 12h14M12 5v14" }]],
  minus: [["path", { d: "M5 12h14" }]],
  expand: [
    ["path", { d: "M9 3H3v6m12-6h6v6M3 15v6h6m12-6v6h-6M8 8l-5-5m13 5 5-5M8 16l-5 5m13-5 5 5" }],
  ],
  collapse: [
    ["path", { d: "M3 3l6 6m0-6v6H3m18-6-6 6m0-6v6h6M3 21l6-6m0 6v-6H3m18 6-6-6m0 6v-6h6" }],
  ],
  layout: [
    ["rect", { x: 3, y: 4, width: 6, height: 6, rx: 1 }],
    ["rect", { x: 15, y: 14, width: 6, height: 6, rx: 1 }],
    ["path", { d: "M6 10v7h9M15 7h6m-3-3v6" }],
  ],
  undo: [["path", { d: "m8 4-5 5 5 5M3 9h10a7 7 0 0 1 0 14" }]],
  more: [6, 12, 18].map((cx) => [
    "circle",
    { cx, cy: 12, r: 1.5, fill: "currentColor", stroke: "none" },
  ]),
};

export function iconButton(button, name, label) {
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  for (const [key, value] of Object.entries({
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    "stroke-width": 1.7,
    "stroke-linecap": "round",
    "stroke-linejoin": "round",
    "aria-hidden": "true",
  }))
    svg.setAttribute(key, value);
  for (const [tag, attributes] of shapes[name] || shapes.more) {
    const element = document.createElementNS(ns, tag);
    for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, value);
    svg.append(element);
  }
  button.replaceChildren(svg);
  button.classList.add("icon-button");
  button.dataset.icon = name;
  if (label) {
    button.setAttribute("aria-label", label);
    button.title = label;
  }
}

export function installIcons(root) {
  for (const button of root.querySelectorAll("button[data-icon]"))
    iconButton(button, button.dataset.icon, button.getAttribute("aria-label"));
}

export function createContextMenu(menu) {
  let returnTarget = null;
  const items = () =>
    [...menu.querySelectorAll('[role="menuitem"]')].filter(
      (item) => !item.disabled && !item.closest("[hidden]"),
    );
  function close(restoreFocus = false) {
    if (menu.hidden) return;
    menu.hidden = true;
    if (restoreFocus && returnTarget?.isConnected) returnTarget.focus({ preventScroll: true });
  }
  function open(kind, title, x, y, target) {
    returnTarget = target || document.activeElement;
    menu.querySelector("[data-menu-title]").textContent = title;
    for (const group of menu.querySelectorAll("[data-menu-kind]"))
      group.hidden = group.dataset.menuKind !== kind;
    menu.hidden = false;
    menu.dataset.kind = kind;
    menu.style.left = Math.max(8, Math.min(x, innerWidth - menu.offsetWidth - 8)) + "px";
    menu.style.top = Math.max(8, Math.min(y, innerHeight - menu.offsetHeight - 8)) + "px";
    items()[0]?.focus({ preventScroll: true });
  }
  menu.addEventListener("click", (event) => {
    if (event.target.closest('[role="menuitem"]')) close(menu.contains(document.activeElement));
  });
  menu.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      close(true);
      return;
    }
    if (event.key === "Tab") {
      close();
      return;
    }
    const available = items(),
      index = available.indexOf(document.activeElement);
    const next =
      event.key === "ArrowDown"
        ? (index + 1) % available.length
        : event.key === "ArrowUp"
          ? (index + available.length - 1) % available.length
          : event.key === "Home"
            ? 0
            : event.key === "End"
              ? available.length - 1
              : -1;
    if (next >= 0) {
      event.preventDefault();
      event.stopPropagation();
      available[next]?.focus();
    }
  });
  document.addEventListener("pointerdown", (event) => {
    if (!menu.contains(event.target)) close();
  });
  window.addEventListener("resize", () => close());
  window.addEventListener("blur", () => close());
  return { open, close };
}
