import chinese from "./messages.zh-CN.js";

export const supportedLocales = ["en", "zh-CN"];
export function normalizeLocale(value) {
  if (typeof value !== "string") return null;
  const tag = value.toLowerCase();
  return tag === "zh" || tag.startsWith("zh-")
    ? "zh-CN"
    : tag === "en" || tag.startsWith("en-")
      ? "en"
      : null;
}
export function chooseLocale({ explicit, saved, conversation } = {}) {
  return (
    normalizeLocale(explicit) || normalizeLocale(saved) || normalizeLocale(conversation) || "en"
  );
}
const browser = typeof window !== "undefined";
const explicit = browser ? new URL(window.location.href).searchParams.get("lang") : null;
// Read the agent-recorded language before modules create their translated labels.
// A browser locale alone does not change an English-first project.
let conversationLocale = null;
if (browser) {
  try {
    const response = await fetch("/api/design", { cache: "no-store" });
    if (response.ok) conversationLocale = (await response.json()).locale;
  } catch {}
}
let current = chooseLocale({ explicit, conversation: conversationLocale });
export function locale() {
  return current;
}
export function setLocale(value) {
  current = normalizeLocale(value) || "en";
  return current;
}
export function t(message, ...values) {
  const template = current === "zh-CN" ? (chinese[message] ?? message) : message;
  return template.replace(/\{(\d+)\}/g, (match, index) =>
    index < values.length ? String(values[index]) : match,
  );
}

// Translate only the original HTML shell, before any user/model content is inserted.
// Notes, node labels, values, source code, and protocol fields never pass through this walk.
export function translateShell(document) {
  document.documentElement.lang = current;
  const walker = document.createTreeWalker(document.body, 4);
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    if (["SCRIPT", "STYLE"].includes(node.parentElement?.tagName)) continue;
    const text = node.textContent,
      trimmed = text.trim();
    if (trimmed) node.textContent = text.replace(trimmed, t(trimmed));
  }
  for (const element of document.querySelectorAll("[aria-label], [title], [placeholder]"))
    for (const name of ["aria-label", "title", "placeholder"])
      if (element.hasAttribute(name)) element.setAttribute(name, t(element.getAttribute(name)));
  document.title = t(document.title);
}

const preferenceKey = "business-observer.layout.v2:locale";
export function storedLocale(storage) {
  try {
    return normalizeLocale(JSON.parse(storage.getItem(preferenceKey))?.locale);
  } catch {
    return null;
  }
}
export async function saveLocale(storage, value) {
  const normalized = normalizeLocale(value);
  if (!normalized) throw Error("Unsupported interface language");
  storage.setItem(preferenceKey, JSON.stringify({ locale: normalized }));
  const saved = await storage.flush();
  if (saved === false) throw Error("Language preference was not saved");
  return normalized;
}
export function localeURL(href, value) {
  const url = new URL(href);
  url.searchParams.set("lang", normalizeLocale(value) || "en");
  return url.href;
}
export function restoreLocale(storage, href, conversation = conversationLocale) {
  const url = new URL(href);
  const desired = chooseLocale({
    explicit: url.searchParams.get("lang"),
    saved: storedLocale(storage),
    conversation,
  });
  return desired === current ? null : localeURL(href, desired);
}
