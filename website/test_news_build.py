from pathlib import Path
import json
import re
import shutil
import subprocess
import tempfile
import unittest

from news_build import build_news, latest_announcement, pin_to_top


class NewsBuildTests(unittest.TestCase):
    def test_real_commit_snapshot_and_markup_escaping(self):
        source = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            subprocess.run(['git', 'init', '-q', str(root)], check=True)
            subprocess.run(['git', '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                            'commit', '--allow-empty', '-qm', 'Fix <script>alert(1)</script> rendering'], cwd=root, check=True)
            out = root / 'site'
            out.mkdir()
            snapshot = build_news(source, out, root)
            self.assertEqual(len(snapshot['commits']), 1)
            self.assertEqual(snapshot['releases'], [])
            page = (out / 'news/index.html').read_text()
            self.assertIn('Fix &lt;script&gt;alert(1)&lt;/script&gt; rendering', page)
            self.assertNotIn('<script>alert(1)</script>', page)
            data = re.search(r'<script id="news-snapshot" type="application/json">(.*?)</script>', page, re.S).group(1)
            self.assertEqual(json.loads(data), snapshot)
            self.assertNotIn('test@example.invalid', page)
            self.assertIn('href="/news/" aria-current="page"', page)
            self.assertIn('href="/#game">Game</a>', page)

    def test_pin_to_top_defaults_to_freshest_news_and_a_newer_one_supplants_it(self):
        older = {"id": "older", "type": "news", "date": "2026-09-01T00:00:00Z"}
        commit = {"id": "commit-a", "type": "commit", "date": "2026-09-04T00:00:00Z"}
        newer = {"id": "newer", "type": "news", "date": "2026-09-10T00:00:00Z"}
        self.assertEqual([e["id"] for e in pin_to_top([commit, older])], ["older", "commit-a"])
        self.assertEqual([e["id"] for e in pin_to_top([newer, commit, older])], ["newer", "commit-a", "older"])
        self.assertEqual([e["id"] for e in pin_to_top([commit])], ["commit-a"])

    def test_pin_to_top_prefers_an_explicit_pin_over_the_freshest_news_entry(self):
        pinned_older = {"id": "older", "type": "news", "date": "2026-09-01T00:00:00Z", "pinned": True}
        newer = {"id": "newer", "type": "news", "date": "2026-09-10T00:00:00Z"}
        self.assertEqual([e["id"] for e in pin_to_top([newer, pinned_older])], ["older", "newer"])

    def test_build_rejects_more_than_one_pinned_announcement(self):
        source = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as temp:
            fake_source = Path(temp) / "source"
            shutil.copytree(source, fake_source)
            editorial = json.loads((fake_source / "news/editorial.json").read_text())
            editorial.append({**editorial[0], "id": "second-pinned-entry", "pinned": True})
            editorial[0]["pinned"] = True
            (fake_source / "news/editorial.json").write_text(json.dumps(editorial))
            root = Path(temp) / "root"
            root.mkdir()
            with self.assertRaises(ValueError):
                build_news(fake_source, root, root)

    def test_build_rejects_a_non_true_pinned_value(self):
        source = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as temp:
            fake_source = Path(temp) / "source"
            shutil.copytree(source, fake_source)
            editorial = json.loads((fake_source / "news/editorial.json").read_text())
            editorial[0]["pinned"] = "yes"
            (fake_source / "news/editorial.json").write_text(json.dumps(editorial))
            root = Path(temp) / "root"
            root.mkdir()
            with self.assertRaises(ValueError):
                build_news(fake_source, root, root)

    def test_latest_announcement_matches_pin_to_top_and_follows_a_newer_entry(self):
        source = Path(__file__).resolve().parent
        self.assertEqual(latest_announcement(source)["id"], "introducing-omega-omarchy")
        with tempfile.TemporaryDirectory() as temp:
            fake_source = Path(temp) / "source"
            shutil.copytree(source, fake_source)
            editorial = json.loads((fake_source / "news/editorial.json").read_text())
            editorial.append({**editorial[0], "id": "a-newer-announcement", "date": "2099-01-01T00:00:00Z"})
            (fake_source / "news/editorial.json").write_text(json.dumps(editorial))
            self.assertEqual(latest_announcement(fake_source)["id"], "a-newer-announcement")

    def test_source_archive_still_has_editorial_news(self):
        source = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            snapshot = build_news(source, root, root)
            self.assertEqual(snapshot['commits'], [])
            self.assertGreater(len(snapshot['editorial']), 0)
            self.assertTrue((root / 'news/index.html').is_file())


if __name__ == '__main__':
    unittest.main()
