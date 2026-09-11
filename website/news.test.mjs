import test from 'node:test';
import assert from 'node:assert/strict';
import {commitEntries, releaseEntries, mergeEntries, repositoryUpdate, fetchRepository, REPO_URL} from './news-model.mjs';

const sha = 'a'.repeat(40);
const rawCommit = {sha, html_url: 'javascript:bad()', commit: {message: '<script>example</script>\nBody stays in GitHub', committer: {date: '2026-09-04T05:54:38Z'}}};
const rawRelease = {id: 17, draft: false, tag_name: 'v0.1.0', name: 'Chapter 1', published_at: '2026-09-11T18:00:00Z', body: '## Changes\nA [new level](https://example.org).', prerelease: false};

test('Commits use exact repository IDs and titles without trusting supplied URLs', () => {
  const [commit] = commitEntries([rawCommit]);
  assert.equal(commit.sha, 'aaaaaaa');
  assert.equal(commit.title, '<script>example</script>');
  assert.equal(commit.url, `${REPO_URL}/commit/${sha}`);
  assert.deepEqual(commitEntries([null, {sha: 'oops'}, {...rawCommit, commit: {}}]), []);
  assert.throws(() => commitEntries({message: 'rate limited'}));
});

test('Releases omit drafts and preserve prerelease labels and safe tag links', () => {
  const entries = releaseEntries([rawRelease, {...rawRelease, draft: true}, {...rawRelease, published_at: null},
    {...rawRelease, id: 18, prerelease: true, tag_name: 'test/alpha'}]);
  assert.equal(entries.length, 2);
  assert.equal(entries[0].paragraphs[0], 'Changes A new level.');
  assert.equal(entries[1].prerelease, true);
  assert.equal(entries[1].url, `${REPO_URL}/releases/tag/test%2Falpha`);
});

test('Announcements and repository entries merge by timestamp without duplicates', () => {
  const editorial = [{id: 'hello', type: 'news', date: '2026-09-11T12:00:00-04:00'}];
  const commit = commitEntries([rawCommit]);
  const releases = releaseEntries([rawRelease]);
  assert.deepEqual(mergeEntries(editorial, [...commit, ...commit], releases).map(e => e.id), ['release-17', 'hello', `commit-${sha}`]);
});

test('Unavailable endpoints preserve their snapshot while successful endpoints update', () => {
  const snapshot = {editorial: [{id: 'hello', type: 'news', date: '2026-09-11T12:00:00Z'}], commits: commitEntries([rawCommit]), releases: []};
  const failure = {status: 'rejected', reason: new Error('Unavailable')};
  const releaseSuccess = {status: 'fulfilled', value: releaseEntries([rawRelease])};
  const partial = repositoryUpdate(snapshot, [failure, releaseSuccess]);
  assert.equal(partial.liveCount, 1);
  assert.equal(partial.entries.length, 3);
  assert.ok(partial.entries.some(e => e.id === `commit-${sha}`));
  assert.equal(repositoryUpdate(snapshot, [failure, failure]).entries.length, 2);
  assert.equal(repositoryUpdate(snapshot, [{status: 'fulfilled', value: []}, releaseSuccess]).entries.length, 2);
});

test('Public requests omit credentials, normalize results, and reject API failures', async () => {
  const entries = await fetchRepository('commits', async (url, options) => {
    assert.equal(url, 'https://api.github.com/repos/Omega-Omarchy/omega-omarchy/commits?per_page=20');
    assert.equal(options.credentials, 'omit');
    assert.ok(options.signal instanceof AbortSignal);
    assert.equal(options.headers.Authorization, undefined);
    return {ok: true, json: async () => [rawCommit]};
  });
  assert.equal(entries.length, 1);
  for (const status of [404, 403, 429, 500]) {
    await assert.rejects(fetchRepository('releases', async () => ({ok: false, status})), /Repository response/);
  }
  await assert.rejects(fetchRepository('secrets'), /Unsupported/);
});
