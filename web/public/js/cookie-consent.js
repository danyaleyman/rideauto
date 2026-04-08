(function () {
  var STORAGE_KEY = "wra_cookie_consent_v1";
  var CONSENT_ACCEPTED = "accepted";
  var CONSENT_REJECTED = "rejected";

  function getConsent() {
    try {
      return window.localStorage.getItem(STORAGE_KEY);
    } catch (e) {
      return null;
    }
  }

  function setConsent(value) {
    try {
      window.localStorage.setItem(STORAGE_KEY, value);
    } catch (e) {
      // no-op
    }
  }

  function loadDeferredAnalyticsScripts() {
    var selectors = [
      'script[type="text/plain"][data-cookie-category="analytics"]',
      'script[type="text/plain"][data-cookie-category="marketing"]'
    ];
    var deferred = document.querySelectorAll(selectors.join(","));
    deferred.forEach(function (node) {
      var script = document.createElement("script");
      if (node.src) script.src = node.src;
      if (node.textContent && node.textContent.trim()) script.text = node.textContent;
      script.async = true;
      document.head.appendChild(script);
      node.setAttribute("data-cookie-loaded", "1");
    });
    if (!window.__wraMktPixelsRequested) {
      window.__wraMktPixelsRequested = true;
      var mkt = document.createElement("script");
      mkt.src = "/js/wra-mkt-pixels.js?v=20260407";
      mkt.async = true;
      document.head.appendChild(mkt);
    }
    window.dispatchEvent(new CustomEvent("cookie-consent:accepted"));
  }

  function hideBanner() {
    var el = document.getElementById("cookie-consent-banner");
    if (el) el.remove();
  }

  function createBanner() {
    if (document.getElementById("cookie-consent-banner")) return;

    var el = document.createElement("div");
    el.id = "cookie-consent-banner";
    el.className = "cookie-consent";
    el.innerHTML =
      '<div class="cookie-consent__inner">' +
      '  <div class="cookie-consent__top">' +
      '    <img class="cookie-consent__icon" src="/image/Cookie.png" alt="" width="30" height="30" loading="lazy" decoding="async">' +
      '    <div class="cookie-consent__copy">' +
      '      <p class="cookie-consent__headline">Мы используем файлы cookie</p>' +
      '      <p class="cookie-consent__text">Мы используем файлы cookie, чтобы улучшить ваш опыт. Продолжая использовать наш сайт, вы соглашаетесь с нашей <a class="cookie-consent__link" href="/privacy">Политикой конфиденциальности</a>, <a class="cookie-consent__link" href="/cookies">Политикой cookie</a> и <a class="cookie-consent__link" href="/agreement">Пользовательским соглашением</a>.</p>' +
      "    </div>" +
      "  </div>" +
      '  <div class="cookie-consent__footer">' +
      '    <button type="button" class="cookie-consent__btn--accept" id="cookie-accept-all">Принять</button>' +
      '    <button type="button" class="cookie-consent__btn--reject" id="cookie-reject-all">Только необходимые</button>' +
      "  </div>" +
      "</div>";

    document.body.appendChild(el);

    var accept = document.getElementById("cookie-accept-all");
    var reject = document.getElementById("cookie-reject-all");
    if (accept) {
      accept.addEventListener("click", function () {
        setConsent(CONSENT_ACCEPTED);
        hideBanner();
        loadDeferredAnalyticsScripts();
      });
    }
    if (reject) {
      reject.addEventListener("click", function () {
        setConsent(CONSENT_REJECTED);
        hideBanner();
      });
    }
  }

  function initCookieConsent() {
    var consent = getConsent();
    if (consent === CONSENT_ACCEPTED) {
      loadDeferredAnalyticsScripts();
      return;
    }
    if (consent === CONSENT_REJECTED) {
      return;
    }
    createBanner();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initCookieConsent);
  } else {
    initCookieConsent();
  }
})();
