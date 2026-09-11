'use strict';

const themes = [
  {id: 'tokyo-night', name: 'Tokyo Night', color: '#1a1b26'},
  {id: 'everforest', name: 'Everforest', color: '#272e33'},
  {id: 'gruvbox', name: 'Gruvbox', color: '#282828'},
];
const themeButton = document.querySelector('#theme-toggle');
function setTheme(id) {
  const theme = themes.find(theme => theme.id === id) || themes[0];
  document.documentElement.dataset.theme = theme.id;
  themeButton.setAttribute('aria-label', `Change color theme. Current theme: ${theme.name}`);
  themeButton.title = `${theme.name} · Change theme (T)`;
  document.querySelector('meta[name="theme-color"]').content = theme.color;
  try { localStorage.setItem('omega-site-theme', theme.id); } catch { /* Preferences are optional. */ }
}
function cycleTheme() {
  const index = themes.findIndex(theme => theme.id === document.documentElement.dataset.theme);
  setTheme(themes[(index + 1) % themes.length].id);
}
setTheme(document.documentElement.dataset.theme);
themeButton.addEventListener('click', cycleTheme);
document.addEventListener('keydown', event => {
  if (event.key.toLowerCase() !== 't' || event.altKey || event.ctrlKey || event.metaKey || event.repeat) return;
  if (event.target.closest('input, textarea, select, button, a, summary, [contenteditable="true"]')) return;
  event.preventDefault();
  cycleTheme();
});
