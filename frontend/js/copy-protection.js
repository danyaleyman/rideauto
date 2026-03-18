/**
 * Защита от копирования контента сайта
 */
(function() {
  'use strict';

  function preventCopy(e) {
    e.preventDefault();
    return false;
  }

  function preventContextMenu(e) {
    e.preventDefault();
    return false;
  }

  function preventKeyCopy(e) {
    var c = e.ctrlKey || e.metaKey;
    var key = (e.key || '').toLowerCase();
    if (c && (key === 'c' || key === 'x' || key === 'a' || key === 'u')) {
      e.preventDefault();
      return false;
    }
  }

  document.addEventListener('contextmenu', preventContextMenu);
  document.addEventListener('copy', preventCopy);
  document.addEventListener('cut', preventCopy);
  document.addEventListener('keydown', preventKeyCopy);
  document.addEventListener('selectstart', preventCopy);
  document.addEventListener('dragstart', preventCopy);
})();
