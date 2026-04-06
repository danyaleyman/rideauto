/**
 * Аналитика и лёгкий RUM (без сторонних ID — шлём в dataLayer для GTM/Я.Метрика при подключении).
 * Web Vitals — только после согласия cookie (событие cookie-consent:accepted) или если уже accepted.
 */
(function () {
  window.dataLayer = window.dataLayer || [];

  function track(eventName, payload) {
    try {
      var row = { event: eventName, event_time: Date.now() };
      if (payload && typeof payload === "object") {
        for (var k in payload) {
          if (Object.prototype.hasOwnProperty.call(payload, k)) row[k] = payload[k];
        }
      }
      window.dataLayer.push(row);
    } catch (e) {}
  }

  function pageView() {
    track("wra_page_view", {
      path: typeof location !== "undefined" ? location.pathname : "",
      search: typeof location !== "undefined" ? (location.search || "").slice(0, 200) : "",
    });
  }

  /** Минимальный RUM без внешних библиотек (CLS / LCP / INP-подобное). */
  function initWebVitalsLite() {
    if (!window.PerformanceObserver) return;
    try {
      var lcp = 0;
      var poL = new PerformanceObserver(function (list) {
        var e = list.getEntries();
        for (var i = 0; i < e.length; i++) {
          var x = e[i];
          var v = x.renderTime || x.loadTime || x.startTime || 0;
          if (v > lcp) lcp = v;
        }
      });
      poL.observe({ type: "largest-contentful-paint", buffered: true });
      window.addEventListener(
        "pageshow",
        function () {
          setTimeout(function () {
            if (lcp > 0) track("wra_web_vital", { name: "LCP", value_ms: Math.round(lcp) });
            try {
              poL.disconnect();
            } catch (e2) {}
          }, 0);
        },
        { once: true }
      );
    } catch (e0) {}

    try {
      var cls = 0;
      var poC = new PerformanceObserver(function (list) {
        var e = list.getEntries();
        for (var i = 0; i < e.length; i++) {
          if (!e[i].hadRecentInput) cls += e[i].value || 0;
        }
      });
      poC.observe({ type: "layout-shift", buffered: true });
      window.addEventListener(
        "visibilitychange",
        function () {
          if (document.visibilityState === "hidden") {
            track("wra_web_vital", { name: "CLS", value: Math.round(cls * 1000) / 1000 });
            try {
              poC.disconnect();
            } catch (e3) {}
          }
        },
        { once: true }
      );
    } catch (e1) {}

    try {
      if (PerformanceObserver.supportedEntryTypes && PerformanceObserver.supportedEntryTypes.indexOf("event") >= 0) {
        var inp = 0;
        var poI = new PerformanceObserver(function (list) {
          var e = list.getEntries();
          for (var i = 0; i < e.length; i++) {
            var x = e[i];
            if (x.interactionId) {
              var d = x.duration || x.processingEnd - x.processingStart || 0;
              if (d > inp) inp = d;
            }
          }
        });
        poI.observe({ type: "event", buffered: true, durationThreshold: 16 });
        window.addEventListener(
          "visibilitychange",
          function () {
            if (document.visibilityState === "hidden" && inp > 0) {
              track("wra_web_vital", { name: "INP_max", value_ms: Math.round(inp) });
              try {
                poI.disconnect();
              } catch (e4) {}
            }
          },
          { once: true }
        );
      }
    } catch (e5) {}
  }

  var __wraRumInited = false;
  function initAfterConsent() {
    if (__wraRumInited) return;
    __wraRumInited = true;
    initWebVitalsLite();
    pageView();
  }

  window.WRAAnalytics = {
    track: track,
    pageView: pageView,
    initAfterConsent: initAfterConsent,
  };

  window.addEventListener("cookie-consent:accepted", initAfterConsent);
  try {
    var v = localStorage.getItem("wra_cookie_consent_v1");
    if (v === "accepted") initAfterConsent();
  } catch (e6) {}
})();
