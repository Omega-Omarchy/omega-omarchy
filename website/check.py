"""Check the exported site's links, preview media, metadata, and play payload."""
from __future__ import annotations
import argparse
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET
import zipfile


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.links = []
        self.canonical = None
        self.h1s = 0
        self.missing_alts = 0
        self.meta = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'meta':
            self.meta[attrs.get('property') or attrs.get('name')] = attrs.get('content')
        if 'id' in attrs:
            self.ids.append(attrs['id'])
        for key in ('src', 'href'):
            if key in attrs:
                self.links.append(attrs[key])
        if tag == 'link' and attrs.get('rel') == 'canonical':
            self.canonical = attrs.get('href')
        self.h1s += tag == 'h1'
        self.missing_alts += tag == 'img' and 'alt' not in attrs


def check(root: Path, *, require_game=True) -> dict:
    root = root.resolve()
    errors = []
    pages = {}
    for route in ('', 'news/'):
        path = root / route / 'index.html'
        page = Page()
        page.feed(path.read_text())
        pages[path] = page
        if len(set(page.ids)) != len(page.ids):
            errors.append(f'Duplicate element IDs: {route}')
        if page.canonical != f'https://omegaomarchy.org/{route}' or page.h1s != 1:
            errors.append(f'Incorrect page identity or main heading: {route}')
        if page.missing_alts:
            errors.append(f'Missing image alt text: {route}')
        if page.meta.get('twitter:card') != 'summary_large_image':
            errors.append(f'Missing large social card: {route}')
        for key, size in [('og:image', (1200, 630)), ('twitter:image', (1200, 600))]:
            url = urlsplit(page.meta.get(key) or '')
            image = root / url.path.lstrip('/')
            if url.scheme != 'https' or url.netloc != 'omegaomarchy.org' or not image.is_file():
                errors.append(f'Missing production social image: {route} {key}')
            else:
                header = image.read_bytes()[:24]
                if header[:8] != b'\x89PNG\r\n\x1a\n' or (int.from_bytes(header[16:20], 'big'), int.from_bytes(header[20:24], 'big')) != size:
                    errors.append(f'Incorrect social image dimensions: {key}')
    for current, page in pages.items():
        for link in page.links:
            url = urlsplit(link)
            if url.scheme or url.netloc:
                continue
            path = current if not url.path else ((root if url.path.startswith('/') else current.parent) / unquote(url.path).lstrip('/'))
            if url.path.endswith('/'):
                path = path / 'index.html'
            if not path.is_file() and not (url.path.lstrip('/').startswith('play/') and not require_game):
                errors.append(f'Missing linked file: {link}')
            if url.fragment and path in pages and url.fragment not in pages[path].ids:
                errors.append(f'Missing anchor: {link}')
    for name in re.findall(r'url\([\'"]?([^\)\'\"]+)', (root / 'style.css').read_text()):
        if not (root / name).is_file():
            errors.append(f'Missing stylesheet asset: {name}')
    previews = [root / f'assets/{scene}-{fid}.webp' for scene in ('gameplay', 'prologue', 'battle') for fid in ('sixteen-bit', 'high', 'ultra')]
    for preview in previews:
        if not preview.is_file() or preview.stat().st_size < 100:
            errors.append(f'Missing preview: {preview.name}')
    for detail in ('sixteen-bit', 'high', 'ultra'):
        for part in ('body', 'upper', 'fore', 'claw-open', 'claw-closed', 'joint'):
            asset = root / f'assets/robots/{detail}/custodian-{part}.png'
            if not asset.is_file() or asset.read_bytes()[:8] != b'\x89PNG\r\n\x1a\n':
                errors.append(f'Missing or invalid robot part: {detail}/{part}')
    for entrypoint in ('motion.js', 'news.js'):
        for module in re.findall(r"from ['\"]([^'\"]+)['\"]", (root / entrypoint).read_text()):
            if not (root / module).is_file():
                errors.append(f'Missing module: {module}')
    for font in ('geist-latin.woff2', 'jetbrains-mono-latin.woff2'):
        if (root / 'assets' / font).read_bytes()[:4] != b'wOF2':
            errors.append(f'Invalid font: {font}')
    for license in ('OMARCHY-FONT-LICENSE.txt', 'GEIST-LICENSE.txt', 'JETBRAINS-MONO-LICENSE.txt'):
        if not (root / 'assets' / license).is_file():
            errors.append(f'Missing font license: {license}')
    ET.parse(root / 'sitemap.xml')
    with zipfile.ZipFile(root / 'assets/character-agent-kit.zip') as kit:
        if kit.testzip():
            errors.append('Invalid character kit ZIP')
    if require_game:
        for name in ('index.html', 'omega-omarchy.apk', 'browserfs.min.js', 'character-agent-kit.zip'):
            if not (root / 'play' / name).is_file():
                errors.append(f'Missing game payload: {name}')
    text = '\n'.join((root / name).read_text() for name in ('index.html', 'style.css', 'site.js', 'theme.js', 'motion.js', 'motion-model.mjs', 'news.js', 'news-model.mjs'))
    if re.search(r'localhost|127\.0\.0\.1|file://', text):
        errors.append('Local-only reference in production page')
    if errors:
        raise ValueError('\n'.join(errors))
    return {'pages': len(pages), 'links': sum(len(p.links) for p in pages.values()), 'previewImages': len(previews), 'robotParts': 18, 'characterKit': 'valid', 'gameIncluded': require_game}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=Path(__file__).resolve().parents[1] / 'dist/website')
    parser.add_argument('--landing-only', action='store_true')
    args = parser.parse_args()
    print(json.dumps(check(args.directory, require_game=not args.landing_only), indent=2))
