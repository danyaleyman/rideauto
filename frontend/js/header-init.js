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

  var header = document.querySelector('.header');
  var burgerBtn = document.getElementById('headerBurgerBtn');
  var mobileMenu = document.getElementById('mobileHeaderMenu');
  if (header && burgerBtn && mobileMenu) {
    var desktopNav = header.querySelector('.nav-menu');
    if (desktopNav) {
      var links = desktopNav.querySelectorAll('a[href]');
      mobileMenu.innerHTML = '';
      links.forEach(function (a) {
        var href = (a.getAttribute('href') || '').trim();
        if (!href) return;
        var clone = document.createElement('a');
        clone.href = href;
        clone.textContent = (a.textContent || '').trim() || href;
        var t = (a.getAttribute('target') || '').trim();
        if (t) clone.target = t;
        var rel = (a.getAttribute('rel') || '').trim();
        if (rel) clone.rel = rel;
        if (a.classList.contains('active')) clone.classList.add('active');
        mobileMenu.appendChild(clone);
      });
    }
    var closeMobileMenu = function () {
      header.classList.remove('mobile-menu-open');
      burgerBtn.setAttribute('aria-expanded', 'false');
    };
    burgerBtn.addEventListener('click', function () {
      var willOpen = !header.classList.contains('mobile-menu-open');
      header.classList.toggle('mobile-menu-open', willOpen);
      burgerBtn.setAttribute('aria-expanded', willOpen ? 'true' : 'false');
    });
    mobileMenu.addEventListener('click', function (e) {
      if (e.target && e.target.tagName === 'A') closeMobileMenu();
    });
    window.addEventListener('resize', function () {
      if (window.innerWidth > 900) closeMobileMenu();
    });
  }
})();
