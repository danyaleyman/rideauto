"use client";

import { useEffect } from "react";

export function AboutEffects() {
  useEffect(() => {
    function initReveal() {
      const nodes = Array.prototype.slice.call(
        document.querySelectorAll(".scroll-reveal"),
      ) as HTMLElement[];
      if (!nodes.length) return;
      if (!("IntersectionObserver" in window)) {
        nodes.forEach((el) => el.classList.add("revealed"));
        return;
      }
      const observer = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (!entry.isIntersecting) return;
            entry.target.classList.add("revealed");
            observer.unobserve(entry.target);
          });
        },
        { threshold: 0.16, rootMargin: "0px 0px -8% 0px" },
      );
      nodes.forEach((el) => observer.observe(el));
    }

    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", initReveal);
    } else {
      initReveal();
    }

    function fmtTime(zone: string) {
      return new Intl.DateTimeFormat("ru-RU", {
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
        timeZone: zone,
      }).format(new Date());
    }
    function tick() {
      const m = document.getElementById("wraMskClock");
      const k = document.getElementById("wraKrClock");
      if (m) m.textContent = fmtTime("Europe/Moscow");
      if (k) k.textContent = fmtTime("Asia/Seoul");
    }
    tick();
    const id = window.setInterval(tick, 30_000);

    return () => {
      document.removeEventListener("DOMContentLoaded", initReveal);
      window.clearInterval(id);
    };
  }, []);
  return null;
}
