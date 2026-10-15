/* theme.js — persiste e aplica o tema claro/escuro */
(function () {
  const btn = document.getElementById('theme-toggle');
  if (!btn) return;

  function getTheme() {
    return localStorage.getItem('herbAppTheme') || 'light';
  }

  function applyTheme(theme) {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem('herbAppTheme', theme);
    btn.textContent = theme === 'dark' ? '🌗' : '☀️';
  }

  applyTheme(getTheme());

  btn.addEventListener('click', function () {
    const current = document.documentElement.dataset.theme || 'dark';
    applyTheme(current === 'dark' ? 'light' : 'dark');
  });
})();
