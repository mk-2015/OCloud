(function () {
  var KEY = 'theme';
  var root = document.documentElement;
  var ICONS = { dark: '\uD83C\uDF19', light: '\u2600\uFE0F' };
  var SELECTOR = '#themeToggle,[data-theme-toggle]';

  function current() {
    return root.getAttribute('data-theme') === 'light' ? 'light' : 'dark';
  }

  function applyIcons() {
    var icon = ICONS[current()];
    var buttons = document.querySelectorAll(SELECTOR);
    for (var i = 0; i < buttons.length; i++) {
      buttons[i].textContent = icon;
      buttons[i].title = 'Toggle theme';
    }
  }

  function toggleTheme() {
    var next = current() === 'dark' ? 'light' : 'dark';
    root.setAttribute('data-theme', next);
    try { localStorage.setItem(KEY, next); } catch (e) {}
    applyIcons();
    try {
      window.dispatchEvent(new CustomEvent('themechange', { detail: { theme: next } }));
    } catch (e) {}
  }

  window.toggleTheme = toggleTheme;
  window.syncThemeButtons = applyIcons;

  function wire() {
    var buttons = document.querySelectorAll(SELECTOR);
    for (var i = 0; i < buttons.length; i++) {
      var b = buttons[i];
      if (!b.getAttribute('data-theme-bound')) {
        b.setAttribute('data-theme-bound', '1');
        b.addEventListener('click', toggleTheme);
      }
    }
    applyIcons();
  }

  try {
    root.setAttribute('data-theme', (localStorage.getItem(KEY) || 'dark') === 'light' ? 'light' : 'dark');
  } catch (e) {}

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', wire);
  } else {
    wire();
  }
})();
