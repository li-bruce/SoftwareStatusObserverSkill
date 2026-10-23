import { extra, chinese } from "./messages.mjs?rev=0.7.0";

const defaults = new Map(
  [...document.querySelectorAll("[data-i18n]")].map((element) => [
    element.dataset.i18n,
    [...element.childNodes]
      .map((node) => (node.nodeName === "BR" ? String.fromCharCode(10) : node.textContent))
      .join(""),
  ]),
);
document.querySelectorAll("[data-i18n-aria]").forEach((element) => {
  defaults.set(element.dataset.i18nAria, element.getAttribute("aria-label"));
});
const listeners = new Set();
const requested = new URLSearchParams(location.search).get("lang");
let saved;
try {
  saved = localStorage.getItem("bo.product.language");
} catch {
  /* Preference storage is optional. */
}
let language = ["en", "zh-CN"].includes(requested) ? requested : saved === "zh-CN" ? saved : "en";
let demoMessages = {};

/** Resolve product or demo copy without changing the state of either interaction. */
export function t(key) {
  const pair = demoMessages[key] || extra[key];
  const value = pair
    ? pair[language === "en" ? 0 : 1]
    : ((language === "zh-CN" ? chinese[key] : undefined) ?? defaults.get(key) ?? key);
  return value.split(String.fromCharCode(92, 110)).join(String.fromCharCode(10));
}

export function locale() {
  return language;
}

export function onLanguageChange(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** Use text nodes and line breaks so translated copy cannot inject page markup. */
export function setCopy(element, value) {
  element.replaceChildren();
  value.split(String.fromCharCode(10)).forEach((line, index) => {
    if (index) element.append(document.createElement("br"));
    element.append(document.createTextNode(line));
  });
}

export function localize() {
  document.documentElement.lang = language;
  document
    .querySelectorAll("[data-i18n]")
    .forEach((element) => setCopy(element, t(element.dataset.i18n)));
  document
    .querySelectorAll("[data-i18n-aria]")
    .forEach((element) => element.setAttribute("aria-label", t(element.dataset.i18nAria)));
  document.querySelectorAll("[data-local-link]").forEach((element) => {
    const url = new URL(element.getAttribute("href"), location.href);
    url.searchParams.set("lang", language);
    element.href = url.href;
  });
  const toggle = document.getElementById("language");
  toggle.textContent = language === "en" ? "中文" : "English";
  toggle.setAttribute("aria-label", language === "en" ? "Switch to Chinese" : "Switch to English");
  const prefix = "https://github.com/li-bruce/SoftwareStatusObserverSkill/blob/main/docs/";
  for (const [id, path] of [
    ["usage-link", "usage"],
    ["source-link", "source-guide"],
  ]) {
    const link = document.getElementById(id);
    if (link) link.href = prefix + path + (language === "en" ? ".en.md" : ".zh-CN.md");
  }
  listeners.forEach((listener) => listener());
}

/** Register the independent walkthrough's vocabulary only when that page loads. */
export function initialize(messages = {}) {
  demoMessages = messages;
  document.getElementById("language").addEventListener("click", () => {
    language = language === "en" ? "zh-CN" : "en";
    try {
      localStorage.setItem("bo.product.language", language);
    } catch {
      /* Keep the session usable. */
    }
    const url = new URL(location.href);
    url.searchParams.set("lang", language);
    history.replaceState(null, "", url);
    localize();
  });
  localize();
}
