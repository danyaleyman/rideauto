(function () {
  if (!(window.WRAAuthFavorites && typeof window.WRAAuthFavorites.initHeader === 'function')) return;
  window.WRAAuthFavorites.initHeader({
    loginButtonSelector: '#headerLoginBtn',
    favoritesButtonSelector: '#headerFavoritesBtn',
    accountButtonSelector: '#headerAccountBtn'
  });
  var saveBtn = document.getElementById('saveSearchSubBtn');
  if (saveBtn) {
    saveBtn.addEventListener('click', function () {
      if (!window.WRAAuthFavorites || typeof window.WRAAuthFavorites.saveCurrentSearchSubscription !== 'function') return;
      var name = prompt('Название подписки:', 'Подписка на поиск') || 'Подписка на поиск';
      var filters = (window.location && window.location.search) ? Object.fromEntries(new URLSearchParams(window.location.search).entries()) : {};
      window.WRAAuthFavorites.saveCurrentSearchSubscription(name, filters);
    });
  }
})();
