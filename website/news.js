import {mergeEntries, pinToTop, fetchRepository, repositoryUpdate} from './news-model.mjs';

const snapshot = JSON.parse(document.querySelector('#news-snapshot').textContent);
const feed = document.querySelector('#news-feed');
const status = document.querySelector('#news-status');
const controls = document.querySelector('#news-filters');
const empty = document.querySelector('#news-empty');
const formatDate = new Intl.DateTimeFormat('en-US', {month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC'});
let entries = mergeEntries(snapshot.editorial, snapshot.commits, snapshot.releases);
let filter = 'all';

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function render() {
  let visible = entries.filter(entry => filter === 'all' || entry.type === filter);
  if (filter === 'all') visible = pinToTop(visible);
  const fragment = document.createDocumentFragment();
  for (const entry of visible) {
    const article = element('article', 'news-entry');
    article.id = entry.id;
    article.dataset.kind = entry.type;
    const meta = element('div', 'news-meta');
    const date = element('time', '', formatDate.format(new Date(entry.date)));
    date.dateTime = entry.date;
    const kind = entry.prerelease ? 'Pre-release' : {news: 'News', release: 'Release', commit: 'Commit'}[entry.type];
    meta.append(date, element('span', 'news-kind', kind));
    if (entry.sha) meta.append(element('span', 'news-sha', entry.sha));
    const copy = element('div', 'news-copy');
    const heading = element('h2');
    const link = element('a', '', entry.title);
    link.href = entry.url;
    heading.append(link); copy.append(heading);
    for (const paragraph of entry.paragraphs) copy.append(element('p', '', paragraph));
    article.append(meta, copy); fragment.append(article);
  }
  feed.replaceChildren(fragment);
  empty.hidden = visible.length > 0;
  controls.querySelectorAll('button').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.newsFilter === filter)));
}

controls.hidden = false;
controls.addEventListener('click', event => {
  const button = event.target.closest('[data-news-filter]');
  if (!button) return;
  filter = button.dataset.newsFilter;
  render();
});
status.textContent = 'Checking the repository for newer entries…';

// Each endpoint can fail independently; a private repo, rate limit, or outage
// leaves the real build snapshot and authored announcements available.
const results = await Promise.allSettled([fetchRepository('commits'), fetchRepository('releases')]);
const update = repositoryUpdate(snapshot, results);
entries = update.entries;
render();
const loaded = update.liveCount;
status.textContent = loaded === 2 ? 'Release and commit entries are up to date with GitHub.'
  : loaded === 1 ? 'Some repository updates are unavailable. Showing the latest available entries.'
  : 'Live repository updates are unavailable. Showing history included with this site.';
