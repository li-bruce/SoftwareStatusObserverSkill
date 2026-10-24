/** A small illustrated tour of the viewer, independent of the runnable demo. */
import { t, onLanguageChange } from "./site-ui.mjs?rev=0.7.2";

const host = document.getElementById("viewer-tour");
const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)");
const steps = ["overview", "expand", "note", "record", "replay"];
let index = 0,
  timer = null,
  visible = false,
  playing = !reducedMotion.matches;

function render() {
  host.dataset.step = steps[index];
  host.querySelector("#tour-caption").textContent = t("tour.step." + steps[index]);
  host.querySelector("#tour-count").textContent = `${index + 1} / ${steps.length}`;
  const play = host.querySelector("#tour-play");
  play.textContent = playing ? "Ⅱ" : "▶";
  play.setAttribute("aria-label", t(playing ? "tour.pause" : "tour.play"));
  play.title = play.getAttribute("aria-label");
  play.setAttribute("aria-pressed", String(playing));
  host.querySelector("#tour-next").setAttribute("aria-label", t("tour.next"));
  host.querySelector("#tour-next").title = t("tour.next");
  host.querySelectorAll("[data-tour-copy]").forEach((element) => {
    element.textContent = t(element.dataset.tourCopy);
  });
}

function schedule() {
  clearTimeout(timer);
  if (playing && visible && !document.hidden)
    timer = setTimeout(() => {
      index = (index + 1) % steps.length;
      render();
      schedule();
    }, 2800);
}
host.querySelector("#tour-play").onclick = () => {
  playing = !playing;
  render();
  schedule();
};
host.querySelector("#tour-next").onclick = () => {
  playing = false;
  index = (index + 1) % steps.length;
  render();
  schedule();
};
new IntersectionObserver(
  ([entry]) => {
    visible = entry.isIntersecting;
    schedule();
  },
  { threshold: 0.2 },
).observe(host);
document.addEventListener("visibilitychange", schedule);
reducedMotion.addEventListener("change", () => {
  if (reducedMotion.matches) playing = false;
  render();
  schedule();
});
onLanguageChange(render);
render();
