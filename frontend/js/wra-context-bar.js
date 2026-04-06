/**
 * Недавно смотрели и список сравнения (localStorage) + закреплённая панель.
 */
(function () {
  var CMP_KEY = "wra_compare_ids_v1";
  var RCV_KEY = "wra_recent_ids_v1";
  var CMP_MAX = 4;
  var RCV_MAX = 12;

  function parseIds(raw) {
    if (!raw || typeof raw !== "string") return [];
    return raw
      .split(",")
      .map(function (s) {
        return String(s || "").trim();
      })
      .filter(Boolean);
  }

  function loadKey(key, maxN) {
    try {
      var arr = parseIds(localStorage.getItem(key));
      if (arr.length > maxN) arr = arr.slice(0, maxN);
      return arr;
    } catch (e) {
      return [];
    }
  }

  function saveKey(key, arr, maxN) {
    try {
      var a = (arr || []).slice(0, maxN);
      localStorage.setItem(key, a.join(","));
    } catch (e2) {}
  }

  function uniqPush(arr, id, maxN) {
    var v = String(id || "").trim();
    if (!v) return arr;
    var out = arr.filter(function (x) {
      return x !== v;
    });
    out.unshift(v);
    return out.slice(0, maxN);
  }

  function renderBar() {
    var bar = document.getElementById("wraContextBar");
    if (!bar) return;
    var rcv = loadKey(RCV_KEY, RCV_MAX);
    var cmp = loadKey(CMP_KEY, CMP_MAX);
    var rcEl = document.getElementById("wraContextRecent");
    var cmEl = document.getElementById("wraContextCompare");
    if (rcEl) {
      rcEl.innerHTML = "";
      rcEl.hidden = rcv.length === 0;
      rcv.slice(0, 6).forEach(function (id) {
        var a = document.createElement("a");
        a.href = typeof window.wraCarDetailUrl === "function" ? window.wraCarDetailUrl(id) : "/detail/" + encodeURIComponent(id);
        a.className = "wra-context-bar__link";
        a.textContent = id.length > 18 ? id.slice(0, 16) + "…" : id;
        a.title = id;
        rcEl.appendChild(a);
      });
    }
    if (cmEl) {
      cmEl.innerHTML = "";
      cmEl.hidden = cmp.length < 2;
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "btn btn-secondary wra-context-bar__compare-btn";
      btn.textContent = "Сравнить (" + cmp.length + ")";
      btn.addEventListener("click", function () {
        if (window.WRAAuthFavorites && typeof window.WRAAuthFavorites.compareCars === "function") {
          window.WRAAuthFavorites.compareCars(cmp.slice(0, CMP_MAX));
          if (window.WRAAnalytics && typeof window.WRAAnalytics.track === "function") {
            window.WRAAnalytics.track("wra_compare_open", { count: cmp.length });
          }
        } else {
          alert(
            "Чтобы сравнивать в личном кабинете, войдите через Telegram. Или откройте несколько объявлений в отдельных вкладках."
          );
        }
      });
      cmEl.appendChild(btn);
    }
    bar.hidden = rcv.length === 0 && cmp.length < 2;
  }

  window.WRAContextBar = {
    addRecent: function (id) {
      var arr = loadKey(RCV_KEY, RCV_MAX);
      saveKey(RCV_KEY, uniqPush(arr, id, RCV_MAX), RCV_MAX);
      renderBar();
    },
    isInCompare: function (id) {
      var v = String(id || "").trim();
      if (!v) return false;
      return loadKey(CMP_KEY, CMP_MAX).indexOf(v) >= 0;
    },
    /** Импорт из ссылки ?compare=id1,id2 (до CMP_MAX объявлений). */
    importCompareFromShare: function (csv) {
      var ids = parseIds(csv).slice(0, CMP_MAX);
      if (!ids.length) return 0;
      saveKey(CMP_KEY, ids, CMP_MAX);
      renderBar();
      if (window.WRAAnalytics && typeof window.WRAAnalytics.track === "function") {
        window.WRAAnalytics.track("wra_compare_import_url", { count: ids.length });
      }
      return ids.length;
    },
    toggleCompare: function (id) {
      var v = String(id || "").trim();
      if (!v) return;
      var arr = loadKey(CMP_KEY, CMP_MAX);
      var i = arr.indexOf(v);
      if (i >= 0) arr.splice(i, 1);
      else {
        if (arr.length >= CMP_MAX) arr.pop();
        arr.unshift(v);
      }
      saveKey(CMP_KEY, arr, CMP_MAX);
      renderBar();
      if (window.WRAAnalytics && typeof window.WRAAnalytics.track === "function") {
        window.WRAAnalytics.track("wra_compare_toggle", { id: v, count: arr.length });
      }
    },
    getCompare: function () {
      return loadKey(CMP_KEY, CMP_MAX);
    },
    render: renderBar,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", renderBar);
  } else {
    renderBar();
  }
})();
