 (function () {
  var USER_KEY = "wra_tg_user_v1";
  var TOKEN_KEY = "wra_auth_token_v1";
  var FAVORITES_KEY_PREFIX = "wra_favorites_";
  var BOT_USERNAME = window.WRA_TELEGRAM_LOGIN_BOT || "";
  var API_BASE = (window.WRA_API_BASE || "").replace(/\/+$/, "");
  var state = {
    user: null,
    token: "",
    favorites: [],
    favoriteNotes: {},
    carsCache: null,
    onFavoritesChanged: []
  };

  function readJson(key, fallback) {
    try {
      var raw = window.localStorage.getItem(key);
      return raw ? JSON.parse(raw) : fallback;
    } catch (e) {
      return fallback;
    }
  }

  function writeJson(key, value) {
    try {
      window.localStorage.setItem(key, JSON.stringify(value));
    } catch (e) {
      // no-op
    }
  }

  function getCurrentUser() {
    return readJson(USER_KEY, null);
  }

  function getToken() {
    try { return window.localStorage.getItem(TOKEN_KEY) || ""; } catch (e) { return ""; }
  }

  function setToken(token) {
    state.token = token || "";
    try {
      if (state.token) window.localStorage.setItem(TOKEN_KEY, state.token);
      else window.localStorage.removeItem(TOKEN_KEY);
    } catch (e) {}
  }

  function setCurrentUser(user) {
    state.user = user;
    writeJson(USER_KEY, user);
  }

  function logoutUser() {
    if (state.token) {
      api("/api/logout", { method: "POST", auth: true }).catch(function () {});
    }
    try { window.localStorage.removeItem(USER_KEY); } catch (e) {}
    try { window.localStorage.removeItem(TOKEN_KEY); } catch (e) {}
    state.user = null;
    state.token = "";
    state.favorites = [];
    state.favoriteNotes = {};
    emitFavoritesChanged();
  }

  function favoritesStorageKey() {
    if (!state.user || !state.user.id) return null;
    return FAVORITES_KEY_PREFIX + String(state.user.id);
  }

  function loadFavorites() {
    var key = favoritesStorageKey();
    if (!key) return [];
    var list = readJson(key, []);
    return Array.isArray(list) ? list : [];
  }

  function saveFavorites() {
    var key = favoritesStorageKey();
    if (!key) return;
    writeJson(key, state.favorites);
  }

  function isFavorite(id) {
    return state.favorites.indexOf(String(id)) >= 0;
  }

  function toggleFavoriteLocal(id) {
    var sid = String(id);
    var idx = state.favorites.indexOf(sid);
    if (idx >= 0) state.favorites.splice(idx, 1);
    else state.favorites.push(sid);
    saveFavorites();
    emitFavoritesChanged();
    return idx < 0;
  }

  function ensureAuth() {
    if (state.user && state.user.id) return true;
    openLoginModal();
    return false;
  }

  function emitFavoritesChanged() {
    state.onFavoritesChanged.forEach(function (fn) {
      try { fn(state.favorites.slice()); } catch (e) {}
    });
  }

  function onFavoritesChanged(fn) {
    state.onFavoritesChanged.push(fn);
  }

  function api(path, options) {
    options = options || {};
    var method = options.method || "GET";
    var headers = { "Content-Type": "application/json" };
    if (options.auth && state.token) headers.Authorization = "Bearer " + state.token;
    return fetch(API_BASE + path, {
      method: method,
      headers: headers,
      body: options.body ? JSON.stringify(options.body) : undefined
    }).then(function (r) {
      if (!r.ok) {
        return r.json().catch(function () { return {}; }).then(function (err) {
          var msg = (err && err.error) ? err.error : ("HTTP " + r.status);
          throw new Error(msg);
        });
      }
      return r.json().catch(function () { return {}; });
    });
  }

  function loadFavoritesFromServer() {
    if (!state.token) {
      state.favorites = loadFavorites();
      emitFavoritesChanged();
      return Promise.resolve(state.favorites);
    }
    return api("/api/favorites", { auth: true }).then(function (res) {
      var rows = (res && res.result) || [];
      state.favorites = rows.map(function (r) { return String(r.car_id); });
      state.favoriteNotes = {};
      rows.forEach(function (r) {
        if (r && r.car_id != null && r.note) state.favoriteNotes[String(r.car_id)] = String(r.note);
      });
      saveFavorites(); // backup cache
      emitFavoritesChanged();
      return state.favorites;
    }).catch(function () {
      state.favorites = loadFavorites();
      state.favoriteNotes = {};
      emitFavoritesChanged();
      return state.favorites;
    });
  }

  function loadCarsJson() {
    if (state.carsCache) return Promise.resolve(state.carsCache);
    var candidates = ["cars.json", "../cars.json"];
    var chain = Promise.reject();
    candidates.forEach(function (url) {
      chain = chain.catch(function () {
        return fetch(url).then(function (r) {
          if (!r.ok) throw new Error("bad response");
          return r.json();
        });
      });
    });
    return chain.then(function (data) {
      state.carsCache = (data && data.result) || [];
      return state.carsCache;
    }).catch(function () {
      state.carsCache = [];
      return [];
    });
  }

  function carIdOf(car) {
    if (!car) return null;
    return car.id != null ? car.id : (car.inner_id != null ? car.inner_id : ((car.data && car.data.inner_id != null) ? car.data.inner_id : null));
  }

  function carDataOf(car) {
    return (car && car.data) ? car.data : (car || {});
  }

  function titleOfCar(car) {
    var d = carDataOf(car);
    var parts = [d.mark, d.model, d.generation || d.configuration].filter(Boolean);
    var t = parts.join(" ").trim();
    return t || "Автомобиль";
  }

  function createModal(id, title) {
    var exists = document.getElementById(id);
    if (exists) return exists;
    var overlay = document.createElement("div");
    overlay.className = "auth-modal-overlay";
    overlay.id = id;
    overlay.innerHTML =
      '<div class="auth-modal" role="dialog" aria-modal="true">' +
      '<h3>' + title + "</h3>" +
      '<div class="auth-modal-body"></div>' +
      '<div class="auth-modal-actions"><button type="button" class="auth-fav-btn auth-close-btn">Закрыть</button></div>' +
      "</div>";
    document.body.appendChild(overlay);
    overlay.addEventListener("click", function (e) {
      if (e.target === overlay || e.target.classList.contains("auth-close-btn")) {
        overlay.classList.remove("is-open");
      }
    });
    return overlay;
  }

  function openLoginModal() {
    var modal = createModal("wra-auth-modal", "Вход через Telegram");
    var body = modal.querySelector(".auth-modal-body");
    body.innerHTML =
      '<p>Войдите через Telegram, чтобы сохранять избранные авто и быстро возвращаться к ним с любого устройства.</p>' +
      '<div id="wra-telegram-widget-slot"></div>' +
      '<p style="margin-top:10px;">Нет аккаунта? <a class="auth-link-btn" href="https://telegram.org/" target="_blank" rel="noopener">Зарегистрироваться в Telegram</a></p>';
    modal.classList.add("is-open");

    var slot = document.getElementById("wra-telegram-widget-slot");
    if (!BOT_USERNAME) {
      slot.innerHTML = '<p>Не указан Telegram-бот для авторизации. Укажите <code>window.WRA_TELEGRAM_LOGIN_BOT</code> на странице.</p>';
      return;
    }

    window.wraTelegramAuth = function (user) {
      if (!user || !user.id) return;
      api("/api/auth/telegram", { method: "POST", body: user }).then(function (res) {
        if (!res || !res.token || !res.user) throw new Error("bad auth response");
        setToken(res.token);
        setCurrentUser(res.user);
        return loadFavoritesFromServer();
      }).catch(function () {
        // fallback mode if backend auth is unavailable
        setCurrentUser({
          id: user.id,
          first_name: user.first_name || "",
          last_name: user.last_name || "",
          username: user.username || "",
          photo_url: user.photo_url || "",
          auth_date: user.auth_date || 0
        });
        setToken("");
        state.favorites = loadFavorites();
        emitFavoritesChanged();
      }).finally(function () {
        modal.classList.remove("is-open");
      });
    };

    var script = document.createElement("script");
    script.async = true;
    script.src = "https://telegram.org/js/telegram-widget.js?22";
    script.setAttribute("data-telegram-login", BOT_USERNAME);
    script.setAttribute("data-size", "large");
    script.setAttribute("data-userpic", "false");
    script.setAttribute("data-radius", "8");
    script.setAttribute("data-onauth", "wraTelegramAuth(user)");
    script.setAttribute("data-request-access", "write");
    slot.innerHTML = "";
    slot.appendChild(script);
  }

  function openFavoritesModal() {
    if (!ensureAuth()) return;
    var modal = createModal("wra-favorites-modal", "Избранные автомобили");
    var body = modal.querySelector(".auth-modal-body");
    body.innerHTML = "<p>Загрузка списка...</p>";
    modal.classList.add("is-open");

    loadCarsJson().then(function (cars) {
      var ids = state.favorites.slice();
      if (!ids.length) {
        body.innerHTML = "<p>В избранном пока пусто.</p>";
        return;
      }
      var byId = new Map();
      cars.forEach(function (c) { byId.set(String(carIdOf(c)), c); });
      var html = ids.map(function (id) {
        var car = byId.get(String(id));
        if (!car) return "";
        var d = carDataOf(car);
        var linkId = carIdOf(car);
        var note = state.favoriteNotes[String(id)] || "";
        var price = d.my_price ? (Math.round(Number(d.my_price)).toLocaleString("ru-RU") + " ₽") : "Цена по запросу";
        return '<div style="padding:8px 0;border-bottom:1px solid #e5e7eb;">' +
          '<a class="auth-link-btn" href="car.html?id=' + encodeURIComponent(linkId) + '">' + titleOfCar(car) + "</a>" +
          '<div style="font-size:13px;color:#6b7280;margin-top:4px;">' + price + "</div>" +
          '<div style="font-size:12px;color:#4b5563;margin-top:4px;">' + (note ? ("Заметка: " + note) : "Без заметки") + '</div>' +
          '<button type="button" class="auth-fav-btn js-note-btn" data-car-id="' + String(id).replace(/"/g, "&quot;") + '" style="margin-top:6px;padding:6px 10px;font-size:12px;">Заметка</button>' +
          "</div>";
      }).filter(Boolean).join("");
      body.innerHTML = html || "<p>Не удалось найти автомобили из избранного в текущем каталоге.</p>";
      body.querySelectorAll(".js-note-btn").forEach(function (btn) {
        btn.addEventListener("click", function () {
          var cid = btn.getAttribute("data-car-id");
          if (!cid) return;
          var prev = state.favoriteNotes[cid] || "";
          var note = prompt("Заметка к авто:", prev);
          if (note == null) return;
          api("/api/favorites", { method: "POST", auth: true, body: { car_id: cid, note: note } }).then(function () {
            state.favoriteNotes[cid] = note;
            openFavoritesModal();
          }).catch(function () {
            alert("Не удалось сохранить заметку.");
          });
        });
      });
      if (ids.length) {
        body.innerHTML += '<div style="margin-top:12px;display:flex;gap:8px;flex-wrap:wrap;">' +
          '<button type="button" class="auth-fav-btn" id="favCompareBtn">Сравнить избранные</button>' +
          '<button type="button" class="auth-fav-btn" id="favHistoryBtn">Недавно просмотренные</button>' +
          '<button type="button" class="auth-fav-btn" id="favCheckoutBtn">Запросить расчёт/договор</button>' +
          "</div>";
        var compareBtn = document.getElementById("favCompareBtn");
        var historyBtn = document.getElementById("favHistoryBtn");
        var checkoutBtn = document.getElementById("favCheckoutBtn");
        if (compareBtn) compareBtn.addEventListener("click", function () {
          compareCars(ids.slice(0, 4));
        });
        if (historyBtn) historyBtn.addEventListener("click", function () {
          showHistoryModal();
        });
        if (checkoutBtn) checkoutBtn.addEventListener("click", function () {
          quickCheckout(ids);
        });
      }
    });
  }

  function openAccountModal() {
    if (!ensureAuth()) return;
    var modal = createModal("wra-account-modal", "Личный кабинет");
    var body = modal.querySelector(".auth-modal-body");
    body.innerHTML =
      '<div class="account-tabs">' +
      '  <button type="button" class="account-tab-btn is-active" data-tab="favorites">Избранное</button>' +
      '  <button type="button" class="account-tab-btn" data-tab="history">История</button>' +
      '  <button type="button" class="account-tab-btn" data-tab="subscriptions">Подписки</button>' +
      '  <button type="button" class="account-tab-btn" data-tab="checkout">Заявки</button>' +
      '</div>' +
      '<div id="wra-account-content">Загрузка...</div>';
    modal.classList.add("is-open");

    function setActiveTab(name) {
      body.querySelectorAll(".account-tab-btn").forEach(function (b) {
        b.classList.toggle("is-active", b.getAttribute("data-tab") === name);
      });
    }

    function renderFavoritesTab() {
      var ids = state.favorites.slice();
      if (!ids.length) return Promise.resolve('<p>Избранное пусто.</p>');
      return loadCarsJson().then(function (cars) {
        var byId = new Map();
        cars.forEach(function (c) { byId.set(String(carIdOf(c)), c); });
        var html = ids.map(function (id) {
          var car = byId.get(String(id));
          if (!car) return "";
          var d = carDataOf(car);
          var price = d.my_price ? (Math.round(Number(d.my_price)).toLocaleString("ru-RU") + " ₽") : "Цена по запросу";
          return '<div style="padding:8px 0;border-bottom:1px solid #e5e7eb;">' +
            '<a class="auth-link-btn" href="car.html?id=' + encodeURIComponent(carIdOf(car)) + '">' + titleOfCar(car) + '</a>' +
            '<div style="font-size:12px;color:#6b7280;margin-top:4px;">' + price + '</div>' +
            "</div>";
        }).filter(Boolean).join("");
        return html || "<p>Не удалось загрузить карточки избранного.</p>";
      });
    }

    function renderHistoryTab() {
      return api("/api/history?limit=30", { auth: true }).then(function (res) {
        var rows = (res && res.result) || [];
        if (!rows.length) return "<p>История пуста.</p>";
        return rows.map(function (r) {
          return '<div style="padding:8px 0;border-bottom:1px solid #e5e7eb;">' +
            '<a class="auth-link-btn" href="car.html?id=' + encodeURIComponent(r.car_id) + '">Авто #' + r.car_id + '</a>' +
            '<div style="font-size:12px;color:#6b7280;margin-top:4px;">' + (r.viewed_at || "") + '</div>' +
            "</div>";
        }).join("");
      }).catch(function () { return "<p>История недоступна.</p>"; });
    }

    function renderSubscriptionsTab() {
      return api("/api/subscriptions", { auth: true }).then(function (res) {
        var rows = (res && res.result) || [];
        var html = '<div style="margin-bottom:10px;"><button type="button" class="auth-fav-btn" id="subCreateBtn">Новая подписка</button></div>';
        if (!rows.length) {
          html += "<p>Подписок пока нет.</p>";
          return html;
        }
        html += rows.map(function (s) {
          return '<div style="padding:8px 0;border-bottom:1px solid #e5e7eb;">' +
            '<strong>' + (s.name || "Подписка") + '</strong>' +
            '<div style="font-size:12px;color:#6b7280;margin-top:4px;">' + JSON.stringify(s.filters || {}) + '</div>' +
            '<button type="button" class="auth-fav-btn js-sub-del" data-sid="' + s.id + '" style="margin-top:6px;padding:6px 10px;font-size:12px;">Удалить</button>' +
            "</div>";
        }).join("");
        return html;
      }).catch(function () { return "<p>Подписки недоступны.</p>"; });
    }

    function renderCheckoutTab() {
      return api("/api/checkout", { auth: true }).then(function (res) {
        var rows = (res && res.result) || [];
        if (!rows.length) return "<p>Заявок пока нет.</p>";
        return rows.map(function (r) {
          return '<div style="padding:8px 0;border-bottom:1px solid #e5e7eb;">' +
            '<strong>Заявка #' + r.id + '</strong>' +
            '<div style="font-size:12px;color:#6b7280;margin-top:4px;">Статус: ' + (r.status || "new") + "</div>" +
            '<div style="font-size:12px;color:#6b7280;">Авто: ' + ((r.car_ids || []).join(", ") || "—") + "</div>" +
            '<div style="font-size:12px;color:#6b7280;">Дата: ' + (r.created_at || "") + "</div>" +
            "</div>";
        }).join("");
      }).catch(function () { return "<p>Заявки недоступны.</p>"; });
    }

    function mountTab(name) {
      setActiveTab(name);
      var target = document.getElementById("wra-account-content");
      if (!target) return;
      target.innerHTML = "Загрузка...";
      var loader = name === "favorites" ? renderFavoritesTab :
        name === "history" ? renderHistoryTab :
        name === "subscriptions" ? renderSubscriptionsTab : renderCheckoutTab;
      loader().then(function (html) {
        target.innerHTML = html;
        var createBtn = document.getElementById("subCreateBtn");
        if (createBtn) {
          createBtn.addEventListener("click", function () {
            var nameSub = prompt("Название подписки:", "Подписка");
            if (nameSub == null) return;
            var raw = prompt("Фильтры в JSON (например {\"marks\":\"BMW\",\"price_to\":\"3500\"}):", "{}");
            if (raw == null) return;
            var filters = {};
            try { filters = JSON.parse(raw || "{}"); } catch (e) { alert("Невалидный JSON"); return; }
            api("/api/subscriptions", { method: "POST", auth: true, body: { name: nameSub, filters: filters } }).then(function () {
              mountTab("subscriptions");
            }).catch(function () { alert("Не удалось создать подписку."); });
          });
        }
        target.querySelectorAll(".js-sub-del").forEach(function (btn) {
          btn.addEventListener("click", function () {
            var sid = btn.getAttribute("data-sid");
            if (!sid) return;
            api("/api/subscriptions/" + encodeURIComponent(sid), { method: "DELETE", auth: true }).then(function () {
              mountTab("subscriptions");
            }).catch(function () { alert("Не удалось удалить подписку."); });
          });
        });
      });
    }

    body.querySelectorAll(".account-tab-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var tab = btn.getAttribute("data-tab") || "favorites";
        mountTab(tab);
      });
    });
    mountTab("favorites");
  }

  function showHistoryModal() {
    if (!ensureAuth()) return;
    var modal = createModal("wra-history-modal", "Недавно просмотренные");
    var body = modal.querySelector(".auth-modal-body");
    body.innerHTML = "<p>Загрузка...</p>";
    modal.classList.add("is-open");
    api("/api/history?limit=30", { auth: true }).then(function (res) {
      var rows = (res && res.result) || [];
      if (!rows.length) {
        body.innerHTML = "<p>История пока пуста.</p>";
        return;
      }
      body.innerHTML = rows.map(function (r) {
        var when = r.viewed_at || "";
        return '<div style="padding:8px 0;border-bottom:1px solid #e5e7eb;">' +
          '<a class="auth-link-btn" href="car.html?id=' + encodeURIComponent(r.car_id) + '">Авто #' + r.car_id + '</a>' +
          '<div style="font-size:12px;color:#6b7280;margin-top:4px;">' + when + '</div>' +
          "</div>";
      }).join("");
    }).catch(function () {
      body.innerHTML = "<p>Не удалось загрузить историю.</p>";
    });
  }

  function compareCars(ids) {
    ids = (ids || []).map(String).slice(0, 4);
    if (!ids.length) return;
    api("/api/compare?ids=" + encodeURIComponent(ids.join(","))).then(function (res) {
      var list = (res && res.result) || [];
      if (!list.length) {
        alert("Не удалось собрать данные для сравнения.");
        return;
      }
      var lines = list.map(function (c) {
        return [
          c.title || ("ID " + c.id),
          "Цена: " + (c.price_rub ? Math.round(Number(c.price_rub)).toLocaleString("ru-RU") + " ₽" : "—"),
          "Пробег: " + (c.km_age || "—"),
          "Мощность: " + (c.power || "—"),
          "Таможня: " + (c.customs_total_rub ? Math.round(Number(c.customs_total_rub)).toLocaleString("ru-RU") + " ₽" : "—")
        ].join("\n");
      });
      alert("Сравнение:\n\n" + lines.join("\n\n----------------\n\n"));
    }).catch(function () {
      alert("Сравнение временно недоступно.");
    });
  }

  function quickCheckout(ids) {
    if (!ensureAuth()) return;
    var contact = prompt("Укажите контакт для связи (телефон/Telegram):", "");
    if (contact == null) return;
    var comment = prompt("Комментарий к запросу (необязательно):", "") || "";
    api("/api/checkout", {
      method: "POST",
      auth: true,
      body: { car_ids: (ids || []).map(String), contact: contact, comment: comment }
    }).then(function () {
      alert("Запрос отправлен. Менеджер свяжется с вами.");
    }).catch(function () {
      alert("Не удалось отправить запрос. Попробуйте позже.");
    });
  }

  function saveCurrentSearchSubscription(name, filters) {
    if (!ensureAuth()) return Promise.resolve(false);
    return api("/api/subscriptions", {
      method: "POST",
      auth: true,
      body: { name: name || "Подписка на поиск", filters: filters || {} }
    }).then(function () {
      alert("Подписка сохранена.");
      return true;
    }).catch(function () {
      alert("Не удалось сохранить подписку.");
      return false;
    });
  }

  function addHistory(carId) {
    if (!state.token || !carId) return;
    api("/api/history", { method: "POST", auth: true, body: { car_id: String(carId) } }).catch(function () {});
  }

  function updateHeaderUi(opts) {
    var loginBtn = document.querySelector(opts.loginButtonSelector);
    var favBtn = document.querySelector(opts.favoritesButtonSelector);
    var accountBtn = opts.accountButtonSelector ? document.querySelector(opts.accountButtonSelector) : null;
    var favCount = favBtn ? favBtn.querySelector(".auth-fav-count") : null;
    if (!loginBtn || !favBtn) return;

    if (state.user && state.user.id) {
      var name = state.user.first_name || state.user.username || "Профиль";
      loginBtn.textContent = "Выйти (" + name + ")";
      loginBtn.onclick = function () {
        if (confirm("Выйти из аккаунта Telegram?")) logoutUser();
      };
      favBtn.classList.remove("auth-fav-hidden");
      if (accountBtn) accountBtn.classList.remove("auth-fav-hidden");
      if (favCount) favCount.textContent = String(state.favorites.length);
    } else {
      loginBtn.textContent = "Войти";
      loginBtn.onclick = openLoginModal;
      favBtn.classList.add("auth-fav-hidden");
      if (accountBtn) accountBtn.classList.add("auth-fav-hidden");
    }
  }

  function initHeader(opts) {
    state.user = getCurrentUser();
    state.token = getToken();
    state.favorites = loadFavorites();
    var favBtn = document.querySelector(opts.favoritesButtonSelector);
    if (favBtn) favBtn.addEventListener("click", openFavoritesModal);
    var accountBtn = opts.accountButtonSelector ? document.querySelector(opts.accountButtonSelector) : null;
    if (accountBtn) accountBtn.addEventListener("click", openAccountModal);
    updateHeaderUi(opts);
    onFavoritesChanged(function () { updateHeaderUi(opts); });
    if (state.token) {
      api("/api/me", { auth: true }).then(function (res) {
        if (res && res.user) setCurrentUser(res.user);
      }).catch(function () {
        setToken("");
      }).finally(function () {
        loadFavoritesFromServer();
      });
    }
  }

  function bindFavoriteButton(button, carId) {
    if (!button || carId == null) return;
    var sid = String(carId);
    button.classList.toggle("fav-active", isFavorite(sid));
    button.addEventListener("click", function (e) {
      e.preventDefault();
      e.stopPropagation();
      if (!ensureAuth()) return;
      var currentlyFav = isFavorite(sid);
      var action = currentlyFav ? api("/api/favorites/" + encodeURIComponent(sid), { method: "DELETE", auth: true }) : api("/api/favorites", { method: "POST", auth: true, body: { car_id: sid } });
      action.then(function () {
        if (currentlyFav) {
          state.favorites = state.favorites.filter(function (x) { return x !== sid; });
        } else {
          if (!isFavorite(sid)) state.favorites.push(sid);
        }
        saveFavorites();
        emitFavoritesChanged();
        button.classList.toggle("fav-active", !currentlyFav);
      }).catch(function () {
        // fallback to local if API failed
        var active = toggleFavoriteLocal(sid);
        button.classList.toggle("fav-active", active);
      });
    });
  }

  window.WRAAuthFavorites = {
    initHeader: initHeader,
    bindFavoriteButton: bindFavoriteButton,
    ensureAuth: ensureAuth,
    addHistory: addHistory,
    saveCurrentSearchSubscription: saveCurrentSearchSubscription,
    compareCars: compareCars,
    quickCheckout: quickCheckout
  };
})();
