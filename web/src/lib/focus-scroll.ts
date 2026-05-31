/** Подскролл поля при фокусе (клавиатура на iOS/Android в sheet и dropdown). */
export function scrollFocusedFieldIntoView(el: HTMLElement | null) {
  if (!el) return;
  const run = () => {
    try {
      el.scrollIntoView({ block: "center", inline: "nearest", behavior: "smooth" });
    } catch {
      el.scrollIntoView(true);
    }
  };
  requestAnimationFrame(() => {
    run();
    window.setTimeout(run, 300);
  });
}
