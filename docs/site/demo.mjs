import { DemoSession } from "./demo-model.mjs?rev=0.7.0";
import { messages } from "./demo-messages.mjs?rev=0.7.0";
import { initialize, t, locale, onLanguageChange } from "./site-ui.mjs?rev=0.7.0";

const session = new DemoSession();
const stages = ["conversation", "inspect", "record", "iterate"];
const element = (id) => document.getElementById(id);
const escapeText = (value) =>
  String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
let stage = "conversation";
let conversationStep = 0;
let expanded = false;
let sourceOpen = false;
let replayIndex = null;
let playTimer = null;

/** Replay reads a captured snapshot; live mode reads the current sample state. */
function displayed() {
  const event = replayIndex === null ? session.events.at(-1) : session.frame(replayIndex);
  return {
    event,
    values: replayIndex === null ? session.current : (event?.after ?? session.current),
  };
}

function text(x, y, value, css = "") {
  return `<text x="${x}" y="${y}" text-anchor="middle" class="${css}">${escapeText(value)}</text>`;
}

function circleNode(id, x, y, label, active, type = "business") {
  const color = { business: "#2457db", state: "#8056a8", function: "#087f80" }[type];
  return `<g class="${active ? "active-node" : ""}" data-node="${id}" transform="translate(${x} ${y})">
    <circle r="25" fill="${color}18" stroke="${color}" stroke-width="2"/>
    ${text(0, 49, label)}
  </g>`;
}

function arrow(fromX, toX, active) {
  return `<path class="${active ? "active-edge" : ""}" d="M${fromX} 170H${toX}"
    stroke="#9aadc2" fill="none" stroke-width="1.5" marker-end="url(#demo-arrow)"/>`;
}

/** Expanded regions own their outer flow connections and expose the internal detail. */
function renderGraph() {
  const { event, values } = displayed();
  const active = event?.node;
  const radius = expanded ? 108 : 27;
  const confirmed = stage !== "conversation" || conversationStep >= 2;
  let content =
    '<defs><marker id="demo-arrow" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto"><path d="M0 0L7 3.5L0 7" fill="#8095ac"/></marker></defs>';
  if (confirmed) {
    content += arrow(90, 180, active === "check") + arrow(230, 320, active === "notify");
    content += arrow(370, 490 - radius, active === "review");
    content += circleNode("check", 205, 170, t("graph.check"), active === "check");
    content += circleNode("notify", 345, 170, t("graph.notify"), active === "notify");
  } else {
    // Only the activities in the first request appear before the user's answer.
    content += arrow(90, 490 - radius, false);
  }
  content += arrow(490 + radius, 645, values.visible);
  content += circleNode("upload", 65, 170, t("graph.upload"), active === "upload");
  content += circleNode("exhibition", 670, 170, t("graph.exhibition"), values.visible);
  content +=
    '<g class="demo-parent ' +
    (active === "review" ? "active-node" : "") +
    '" id="review-node" role="button" tabindex="0" aria-expanded="' +
    expanded +
    '" aria-label="' +
    escapeText(t(expanded ? "graph.collapse" : "graph.expand")) +
    '"><circle cx="490" cy="170" r="' +
    radius +
    '" fill="#edf2fe" stroke="#2457db" stroke-width="1.7"/>' +
    text(490, expanded ? 90 : 219, t("graph.review")) +
    text(490, expanded ? 112 : 175, expanded ? "−" : "+") +
    "</g>";
  if (expanded) {
    content +=
      '<path d="M448 149L535 188M535 188L455 220" stroke="#7da3b4" fill="none" stroke-dasharray="4 3"/>';
    content += circleNode("review-state", 448, 149, t("state." + values.state), false, "state");
    content +=
      '<g id="function-node" class="demo-parent" role="button" tabindex="0" aria-label="' +
      escapeText(t("graph.source")) +
      '"><path d="M535 164L556 176V200L535 212L514 200V176Z" stroke="#087f80" fill="#d8f0ed" stroke-width="2"/>' +
      text(535, 235, "approve()") +
      "</g>";
    content +=
      '<rect x="404" y="232" width="91" height="27" rx="5" fill="white" stroke="#8aaca8"/>' +
      text(449, 250, "visible: " + values.visible, "mono");
  }
  if (confirmed)
    content +=
      '<path d="M205 197V293" stroke="#a76b13" fill="none" stroke-dasharray="4 4"/>' +
      text(205, 315, t("graph.blocked"), "svg-small");
  if (session.iterated) {
    content +=
      '<path d="M490 ' +
      (170 + radius) +
      'V310H366" stroke="#8056a8" fill="none" marker-end="url(#demo-arrow)"/>';
    content += circleNode(
      "returned",
      340,
      310,
      t("graph.returned"),
      values.state === "returned",
      "state",
    );
    content +=
      '<path d="M315 310C80 380 65 300 65 198" stroke="#8056a8" fill="none" stroke-dasharray="4 4" marker-end="url(#demo-arrow)"/>' +
      text(130, 354, t("graph.resubmit"), "svg-small");
  }
  element("demo-graph").innerHTML = content;
  bindActivation("review-node", () => {
    expanded = !expanded;
    if (!expanded) sourceOpen = false;
    render();
    element("review-node").focus();
  });
  if (expanded)
    bindActivation("function-node", () => {
      sourceOpen = !sourceOpen;
      render();
      element("function-node").focus();
    });
}

function bindActivation(id, handler) {
  element(id).addEventListener("click", handler);
  element(id).addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      handler();
    }
  });
}

function message(role, key) {
  return `<div class="message ${role === "user" ? "user" : ""}">
    <small>${escapeText(t("chat." + role))}</small>${escapeText(t(key))}
  </div>`;
}

function renderConversation() {
  element("demo-heading").textContent = t("heading." + stage);
  element("demo-instruction").textContent = t("instruction." + stage);
  const conversation = element("conversation"),
    advance = element("advance");
  advance.hidden = stage === "record";
  advance.disabled = false;
  if (stage === "conversation") {
    const first = Math.max(0, conversationStep - 1);
    conversation.innerHTML = Array.from({ length: conversationStep - first + 1 }, (_, index) => {
      const step = first + index;
      return message(step % 2 ? "skill" : "user", "chat." + step);
    }).join("");
    advance.textContent = t(conversationStep < 4 ? "advance.conversation" : "advance.inspect");
  } else if (stage === "iterate") {
    conversation.innerHTML = message("user", "chat.change");
    advance.textContent = t(session.iterated ? "advance.applied" : "advance.iterate");
    advance.disabled = session.iterated;
  } else {
    conversation.replaceChildren();
    advance.textContent = t("advance.record");
  }
}

/** Display actual before/after values from the selected sample event. */
function renderDetails() {
  const { event, values } = displayed();
  const label =
    stage === "conversation"
      ? t(conversationStep === 4 ? "status.confirmed" : "status.draft")
      : stage === "inspect"
        ? t("status.inspect")
        : session.recording
          ? t("status.recording") + " · " + session.captured.length
          : replayIndex !== null
            ? t("status.replay") + " " + (replayIndex + 1)
            : session.iterated
              ? t("status.iterated")
              : session.captured.length
                ? t("status.saved") + " · " + session.captured.length
                : session.events.length
                  ? t("status.live")
                  : t("status.ready");
  element("demo-status").textContent = label;
  const rows = ["state", "visible", "notified"].map((key) => {
    const value = (input) => (key === "state" ? t("state." + input) : String(input));
    const changed = event && event.before[key] !== event.after[key];
    const display = changed
      ? value(event.before[key]) + " → " + value(event.after[key])
      : value(values[key]);
    return (
      "<div><dt>" +
      escapeText(t("field." + key)) +
      "</dt><dd>" +
      escapeText(display) +
      "</dd></div>"
    );
  });
  if (event)
    rows.push(
      "<div><dt>" +
        escapeText(t("field.operation")) +
        "</dt><dd>" +
        escapeText(t("operation." + event.operation)) +
        "</dd></div>",
    );
  element("change-detail").innerHTML = rows.join("");
  element("change-detail").hidden = stage === "conversation";
  element("source-snippet").hidden = !sourceOpen;
  element("source-snippet").textContent =
    'function approve(image) {\n  if (image.state !== "pending") return false;\n  image.state = "displayed";\n  image.visible = true;\n  return true;\n}';
}

function renderControls() {
  element("record-controls").hidden = !["record", "iterate"].includes(stage);
  element("start").disabled = session.recording;
  element("new-operation").disabled = session.recording;
  element("stop").disabled = !session.recording;
  element("capture-scope").disabled = session.recording;
  element("upload").disabled =
    session.current.state !== "empty" &&
    !(session.iterated && session.current.state === "returned");
  element("approve").disabled = session.current.state !== "pending";
  element("return").hidden = !session.iterated;
  element("return").disabled = session.current.state !== "pending";
  element("replay").max = Math.max(0, session.captured.length - 1);
  element("replay").value = replayIndex ?? Math.max(0, session.captured.length - 1);
  element("replay").disabled = session.recording || !session.captured.length;
  element("step-number").textContent =
    (session.captured.length ? (replayIndex ?? session.captured.length - 1) + 1 : 0) +
    " / " +
    session.captured.length;
  element("play").disabled = session.recording || !session.captured.length;
  element("play").textContent = t(playTimer ? "demo.pause" : "demo.play");
}

function render() {
  document.title =
    locale() === "en"
      ? "Business Observer — Interactive walkthrough"
      : "Business Observer · 交互演示";
  document.querySelectorAll("[data-stage]").forEach((button) => {
    const selected = button.dataset.stage === stage;
    button.setAttribute("aria-selected", String(selected));
    button.tabIndex = selected ? 0 : -1;
  });
  element("demo-panel").setAttribute("aria-labelledby", "stage-" + stage);
  renderConversation();
  renderGraph();
  renderDetails();
  renderControls();
}

function stopPlayback() {
  if (playTimer) clearInterval(playTimer);
  playTimer = null;
}
function selectStage(next) {
  stopPlayback();
  stage = next;
  render();
}

document.querySelectorAll("[data-stage]").forEach((button) => {
  button.addEventListener("click", () => selectStage(button.dataset.stage));
  button.addEventListener("keydown", (event) => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const index =
      event.key === "Home"
        ? 0
        : event.key === "End"
          ? stages.length - 1
          : (stages.indexOf(stage) + (event.key === "ArrowRight" ? 1 : -1) + stages.length) %
            stages.length;
    selectStage(stages[index]);
    element("stage-" + stage).focus();
  });
});
element("advance").addEventListener("click", () => {
  if (stage === "conversation" && conversationStep < 4) conversationStep++;
  else if (stage === "conversation") stage = "inspect";
  else if (stage === "inspect") stage = "record";
  else if (stage === "iterate") {
    session.addReturnPath();
    session.restartOperation();
    replayIndex = null;
  }
  render();
});
element("reset").addEventListener("click", () => {
  stopPlayback();
  session.reset();
  stage = "conversation";
  conversationStep = 0;
  expanded = false;
  sourceOpen = false;
  replayIndex = null;
  element("capture-scope").value = "all";
  render();
});
element("start").addEventListener("click", () => {
  stopPlayback();
  replayIndex = null;
  session.start(element("capture-scope").value);
  render();
});
element("new-operation").addEventListener("click", () => {
  stopPlayback();
  session.restartOperation();
  replayIndex = null;
  render();
});
element("stop").addEventListener("click", () => {
  session.stop();
  render();
});
for (const operation of ["upload", "approve", "return"]) {
  element(operation).addEventListener("click", () => {
    stopPlayback();
    replayIndex = null;
    session.operate(operation);
    render();
  });
}
element("replay").addEventListener("input", (event) => {
  stopPlayback();
  replayIndex = Number(event.target.value);
  render();
});
element("live").addEventListener("click", () => {
  stopPlayback();
  replayIndex = null;
  render();
});
element("play").addEventListener("click", () => {
  if (playTimer) {
    stopPlayback();
    render();
    return;
  }
  replayIndex = 0;
  playTimer = setInterval(() => {
    if (replayIndex + 1 >= session.captured.length) {
      stopPlayback();
      render();
      return;
    }
    replayIndex++;
    render();
  }, 1000);
  render();
});
window.addEventListener("pagehide", stopPlayback);
onLanguageChange(render);
initialize(messages);
