/**
 * Яндекс.Метрика + Top.Mail.Ru + VK (ретаргетинг) — только после согласия cookie
 * (подключается из cookie-consent.js). dataLayer уже создаёт wra-analytics.js при том же согласии.
 *
 * VK: задайте window.WRA_VK_RTRG_ID в wra-site-config.js (код из кабинета VK Реклама).
 */
(function () {
  if (window.__wraMktPixelsInited) return;
  window.__wraMktPixelsInited = true;

  var YM_ID = 108438859;
  var MAILRU_ID = "3756335";

  // --- Яндекс.Метрика ---
  (function (m, e, t, r, i, k, a) {
    m[i] =
      m[i] ||
      function () {
        (m[i].a = m[i].a || []).push(arguments);
      };
    m[i].l = 1 * new Date();
    for (var j = 0; j < document.scripts.length; j++) {
      if (document.scripts[j].src === r) return;
    }
    k = e.createElement(t);
    a = e.getElementsByTagName(t)[0];
    k.async = 1;
    k.src = r;
    a.parentNode.insertBefore(k, a);
  })(window, document, "script", "https://mc.yandex.ru/metrika/tag.js", "ym");

  ym(YM_ID, "init", {
    ssr: true,
    webvisor: true,
    clickmap: true,
    ecommerce: "dataLayer",
    accurateTrackBounce: true,
    trackLinks: true,
  });

  var y = document.createElement("noscript");
  y.innerHTML =
    '<div><img src="https://mc.yandex.ru/watch/' +
    YM_ID +
    '" style="position:absolute;left:-9999px;" alt="" /></div>';
  document.body.appendChild(y);

  // --- Top.Mail.Ru ---
  var _tmr = window._tmr || (window._tmr = []);
  _tmr.push({ id: MAILRU_ID, type: "pageView", start: new Date().getTime() });
  (function (d, w, id) {
    if (d.getElementById(id)) return;
    var ts = d.createElement("script");
    ts.type = "text/javascript";
    ts.async = true;
    ts.id = id;
    ts.src = "https://top-fwz1.mail.ru/js/code.js";
    var f = function () {
      var s = d.getElementsByTagName("script")[0];
      s.parentNode.insertBefore(ts, s);
    };
    if (w.opera === "[object Opera]") {
      d.addEventListener("DOMContentLoaded", f, false);
    } else {
      f();
    }
  })(document, window, "tmr-code");

  var m = document.createElement("noscript");
  m.innerHTML =
    '<div><img src="https://top-fwz1.mail.ru/counter?id=' +
    MAILRU_ID +
    ';js=na" style="position:absolute;left:-9999px;" alt="Top.Mail.Ru" /></div>';
  document.body.appendChild(m);

  // --- VK Реклама (ретаргетинг) ---
  var vkId =
    typeof window.WRA_VK_RTRG_ID === "string" ? window.WRA_VK_RTRG_ID.trim() : "";
  if (vkId) {
    !(function () {
      var t = document.createElement("script");
      t.type = "text/javascript";
      t.async = true;
      t.src = "https://vk.com/js/api/openapi.js?169";
      t.onload = function () {
        try {
          if (!window.VK || !VK.Retargeting) return;
          VK.Retargeting.Init(vkId);
          VK.Retargeting.Hit();
        } catch (e) {}
      };
      var h = document.getElementsByTagName("head")[0];
      h.insertBefore(t, h.firstChild);
    })();
  }
})();
