from pathlib import Path
import json
import re
import subprocess
import tempfile
import unittest

from news_build import build_news


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
