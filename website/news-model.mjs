export const REPOSITORY = 'Omega-Omarchy/omega-omarchy';
export const REPO_URL = `https://github.com/${REPOSITORY}`;
const validDate = value => typeof value === 'string' && Number.isFinite(Date.parse(value));
const text = (value, max = 400) => typeof value === 'string' ? value.trim().slice(0, max) : '';

export function commitEntries(payload) {
  if (!Array.isArray(payload)) throw new Error('Invalid commit response');
  return payload.slice(0, 20).flatMap(item => {
    if (!item || !/^[a-f0-9]{40,64}$/.test(item.sha) || !validDate(item.commit?.committer?.date)) return [];
    const title = text(text(item.commit.message, 8000).split('\n')[0]);
    if (!title) return [];
    return [{id: `commit-${item.sha}`, type: 'commit', date: item.commit.committer.date,
      title, paragraphs: [], sha: item.sha.slice(0, 7), url: `${REPO_URL}/commit/${item.sha}`}];
  });
}

export function releaseEntries(payload) {
  if (!Array.isArray(payload)) throw new Error('Invalid release response');
  return payload.slice(0, 20).flatMap(item => {
    if (!item || item.draft || !Number.isSafeInteger(item.id) || !validDate(item.published_at) || !text(item.tag_name)) return [];
    const excerpt = text(item.body, 8000)
      .replace(/!\[[^\]]*\]\([^)]*\)/g, '')
      .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')
      .replace(/^\s*#{1,6}\s+/gm, '').replace(/[`*_]/g, '').replace(/\s+/g, ' ').trim();
    const summary = excerpt.length > 320 ? `${excerpt.slice(0, 317).trimEnd()}…` : excerpt;
    return [{id: `release-${item.id}`, type: 'release', date: item.published_at,
      title: text(item.name) || text(item.tag_name), paragraphs: summary ? [summary] : [],
      prerelease: Boolean(item.prerelease), url: `${REPO_URL}/releases/tag/${encodeURIComponent(item.tag_name)}`}];
  });
}

export function mergeEntries(editorial, commits, releases) {
  const unique = new Map();
  for (const entry of [...editorial, ...releases, ...commits]) {
    if (entry && validDate(entry.date) && !unique.has(entry.id)) unique.set(entry.id, entry);
  }
  return [...unique.values()].sort((a, b) => Date.parse(b.date) - Date.parse(a.date) || a.id.localeCompare(b.id));
}

export function repositoryUpdate(snapshot, results) {
  const [commits, releases] = results.map((result, index) => result.status === 'fulfilled'
    ? result.value : snapshot[index === 0 ? 'commits' : 'releases']);
  return {entries: mergeEntries(snapshot.editorial, commits, releases),
    liveCount: results.filter(result => result.status === 'fulfilled').length};
}

export async function fetchRepository(kind, fetcher = fetch) {
  if (!['commits', 'releases'].includes(kind)) throw new Error('Unsupported repository feed');
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 6000);
  try {
    const response = await fetcher(`https://api.github.com/repos/${REPOSITORY}/${kind}?per_page=20`, {
      headers: {Accept: 'application/vnd.github+json'}, credentials: 'omit', signal: controller.signal,
    });
    if (!response.ok) throw new Error(`Repository response ${response.status}`);
    return (kind === 'commits' ? commitEntries : releaseEntries)(await response.json());
  } finally { clearTimeout(timer); }
}
