'use strict';

// Measure the real navigation, including enlarged text and responsive changes.
const header = document.querySelector('.site-header');
new ResizeObserver(() => {
  document.documentElement.style.setProperty('--site-header-height', `${header.getBoundingClientRect().height}px`);
}).observe(header);

const scenes = {
  gameplay: {caption: 'Chapter 1 · The Corrupted Install', alt: 'David stands on a metal platform beside an ascending-ring portal, with a ladder descending into the industrial level.'},
  prologue: {caption: 'Prologue · Transfer in progress', alt: 'The Omarch King lies on a table between two articulated robots as blue consciousness-transfer waves surround him.'},
  battle: {caption: 'RPG encounter · The Package Bureaucrat', alt: 'The Omarch King faces the Package Bureaucrat in a turn-based battle, with trust and dogma meters and tactical choices.'},
};
const fidelities = {'sixteen-bit': '16-bit', high: 'High', ultra: 'Ultra'};
let scene = 'gameplay';
let fidelity = 'ultra';
const preview = document.querySelector('#game-preview');
function updatePreview() {
  document.querySelectorAll('[data-scene]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.scene === scene)));
  document.querySelectorAll('[data-fidelity]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.fidelity === fidelity)));
  document.querySelector('.game-window').dataset.detail = fidelity;
  document.documentElement.dataset.previewDetail = fidelity;
  document.dispatchEvent(new CustomEvent('omega-preview-detail', {detail: fidelity}));
  preview.alt = scenes[scene].alt;
  preview.src = `assets/${scene}-${fidelity}.webp`;
  document.querySelector('#preview-caption').textContent = scenes[scene].caption;
  document.querySelector('#preview-detail').textContent = fidelities[fidelity];
  document.querySelector('#preview-status').textContent = '';
}
preview.addEventListener('error', () => {
  document.querySelector('#preview-status').textContent = 'That screenshot could not load. Try another scene or reload the page.';
});
document.querySelectorAll('[data-scene]').forEach(button => button.addEventListener('click', () => { scene = button.dataset.scene; updatePreview(); }));
document.querySelectorAll('[data-fidelity]').forEach(button => button.addEventListener('click', () => { fidelity = button.dataset.fidelity; updatePreview(); }));

const copyButton = document.querySelector('#copy-command');
copyButton.addEventListener('click', async () => {
  const code = document.querySelector('#install-command');
  const status = document.querySelector('#copy-status');
  try {
    await navigator.clipboard.writeText(code.textContent);
    copyButton.textContent = 'Copied';
    status.textContent = 'Commands copied. Paste them into your Linux terminal.';
  } catch {
    const selection = window.getSelection();
    const range = document.createRange();
    range.selectNodeContents(code);
    selection.removeAllRanges();
    selection.addRange(range);
    status.textContent = 'Commands selected. Copy them using your browser’s copy command.';
  }
});
