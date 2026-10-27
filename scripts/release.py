#!/usr/bin/env python3
"""
CDRA release tool — the ONLY sanctioned way to version and package the site.

    python scripts/release.py check                         validate the project
    python scripts/release.py sync                          write VERSION into every page
    python scripts/release.py sitemap                       regenerate sitemap.xml + robots.txt (generated, don't edit by hand)
    python scripts/release.py bump patch|minor|major --note "what changed"
    python scripts/release.py zip                           check + build  dist/CDRA vX.X.X.zip
    python scripts/release.py release patch|minor|major --note "..."   bump + check + zip

HARD RULE: every archive is named exactly  "CDRA vX.X.X.zip"  (capital CDRA, one space,
lowercase v, three numbers). This script refuses to produce any other name.
"""
import argparse, datetime, fnmatch, json, pathlib, re, sys, urllib.parse, zipfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_pages  # страницы генерируются из src/page.html + src/pages.json

ROOT = pathlib.Path(__file__).resolve().parent.parent
VERSION_FILE = ROOT / 'VERSION'
CHANGELOG = ROOT / 'CHANGELOG.md'
SITEMAP = ROOT / 'sitemap.xml'
DIST = ROOT / 'dist'
SEMVER = re.compile(r'^(\d+)\.(\d+)\.(\d+)$')
ZIP_NAME = re.compile(r'^CDRA v\d+\.\d+\.\d+\.zip$')
REQUIRED_SKILLS = ['apple-design', 'apple-hig-review', 'claude-liquid-glass']
REQUIRED_FILES = ['VERSION', 'css/style.css', 'index.html', 'src/page.html', 'src/pages.json', 'scripts/build_pages.py']
# В .gitignore: в чистом клоне репозитория их может не быть — тогда только предупреждение
LOCAL_ONLY = ['AGENTS.md', 'CLAUDE.md', 'CHANGELOG.md']
BASE_URL = 'https://cdras.github.io/'
EXTRA_PAGES = ['404.html']   # несут версию, но не попадают в sitemap (noindex)
EXCLUDE = ['dist', '.git', '__pycache__', '*.pyc', '*.zip', '.DS_Store', 'Thumbs.db']


def read_version():
    v = VERSION_FILE.read_text(encoding='utf-8').strip()
    if not SEMVER.match(v):
        sys.exit(f'VERSION must look like 1.2.3, got {v!r}')
    return v


def archive_name(version):
    name = f'CDRA v{version}.zip'
    assert ZIP_NAME.match(name), name
    return name


def site_pages():
    """Root-level pages that carry the visible version (the ones with .screen sections)."""
    return [p for p in sorted(ROOT.glob('*.html')) if 'class="screen' in p.read_text(encoding='utf-8')]


def versioned_pages():
    return site_pages() + [ROOT / n for n in EXTRA_PAGES if (ROOT / n).exists()]


def sync(version):
    rebuilt = build_pages.build()   # index.html + 4 награды из шаблона, сразу с актуальной версией
    n = len(rebuilt)
    for p in versioned_pages():
        t = p.read_text(encoding='utf-8')
        o = t
        t = re.sub(r'(<html[^>]*\bdata-version=")[^"]*(")', rf'\g<1>{version}\2', t)
        t = re.sub(r'(<meta name="cdra-version" content=")[^"]*(")', rf'\g<1>{version}\2', t)
        t = re.sub(r'(<span data-cdra-version>)[^<]*(</span>)', rf'\g<1>v{version}\2', t)
        if t != o:
            p.write_text(t, encoding='utf-8', newline='\n'); n += 1
    print(f'sync: version {version} written to {len(versioned_pages())} pages ({n} changed)')


def build_sitemap(date=None):
    """sitemap.xml is GENERATED: root + every award page + their images. Never edit by hand."""
    date = date or datetime.date.today().isoformat()
    if SITEMAP.exists() and not date:
        pass
    old = {}
    if SITEMAP.exists():
        for loc, lm in re.findall(r'<loc>([^<]+)</loc>\s*<lastmod>([^<]+)</lastmod>', SITEMAP.read_text(encoding='utf-8')):
            old[loc] = lm
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">']
    pages = [('index.html', BASE_URL)] + [(p.name, BASE_URL + urllib.parse.quote(p.name)) for p in site_pages() if p.name != 'index.html']
    for fname, loc in pages:
        t = (ROOT / fname).read_text(encoding='utf-8')
        imgs = []
        for src in re.findall(r'<img[^>]*\bsrc="(images/[^"]+\.(?:png|jpe?g|webp))"', t):
            u = BASE_URL + urllib.parse.quote(src)
            if u not in imgs: imgs.append(u)
        out.append('  <url>')
        out.append(f'    <loc>{loc}</loc>')
        out.append(f'    <lastmod>{old.get(loc, date) if date == "keep" else date}</lastmod>')
        for u in imgs: out.append(f'    <image:image><image:loc>{u}</image:loc></image:image>')
        out.append('  </url>')
    out.append('</urlset>')
    SITEMAP.write_text('\n'.join(out) + '\n', encoding='utf-8', newline='\n')
    (ROOT / 'robots.txt').write_text(f'User-agent: *\nAllow: /\n\nSitemap: {BASE_URL}sitemap.xml\n', encoding='utf-8', newline='\n')
    print(f'sitemap: {len(pages)} URLs + robots.txt')


def check(version):
    errs = []
    for f in REQUIRED_FILES:
        if not (ROOT / f).exists(): errs.append(f'missing file: {f}')
    for f in LOCAL_ONLY:
        if not (ROOT / f).exists(): print(f'warning: {f} not found (git-ignored, local only)')
    for s in REQUIRED_SKILLS:
        sk = ROOT / 'skills' / s / 'SKILL.md'
        if not sk.exists(): print(f'warning: skills/{s}/SKILL.md not found (git-ignored, local only)')
    names = []
    for sk in sorted((ROOT / 'skills').glob('*/SKILL.md')):
        m = re.search(r'^name:\s*(\S+)', sk.read_text(encoding='utf-8'), re.M)
        names.append(m.group(1) if m else None)
        if m and m.group(1) != sk.parent.name:
            errs.append(f'skill name {m.group(1)!r} != folder {sk.parent.name!r}')
    if len(names) != len(set(names)): errs.append('duplicate skill names')

    if CHANGELOG.exists():
        m = re.search(r'^## \[(\d+\.\d+\.\d+)\]', CHANGELOG.read_text(encoding='utf-8'), re.M)
        if not m or m.group(1) != version:
            errs.append(f'CHANGELOG.md top entry is {m.group(1) if m else None}, VERSION is {version}')

    pages = site_pages()
    if not pages: errs.append('no site pages found')
    stale = build_pages.build(check=True)
    if stale: errs.append('pages differ from src/page.html + src/pages.json: ' + ', '.join(stale) + ' (run: python scripts/build_pages.py)')
    for p in versioned_pages():
        t = p.read_text(encoding='utf-8'); n = p.name
        for label, pat in [('html data-version', r'<html[^>]*\bdata-version="([^"]*)"'),
                           ('meta cdra-version', r'<meta name="cdra-version" content="([^"]*)"'),
                           ('visible version', r'<span data-cdra-version>v([^<]*)</span>')]:
            m = re.search(pat, t)
            if not m: errs.append(f'{n}: {label} missing')
            elif m.group(1) != version: errs.append(f'{n}: {label} is {m.group(1)}, VERSION is {version}')
        vp = re.findall(r'<meta[^>]*name="viewport"[^>]*>', t)
        if len(vp) != 1: errs.append(f'{n}: need exactly one viewport meta, found {len(vp)}')
        elif re.search(r'user-scalable\s*=\s*(no|0)|maximum-scale', vp[0]): errs.append(f'{n}: viewport must not block zoom')
        for img in re.findall(r'<img\b[^>]*>', t):
            if not re.search(r'\balt=', img): errs.append(f'{n}: <img> without alt: {img[:60]}')
        for key in (('og:image', 'twitter:image') if p in pages else ()):
            m = re.search(r'<meta (?:property|name)="%s" content="([^"]+)"' % key, t)
            if not m: errs.append(f'{n}: {key} missing')
            elif m.group(1).startswith(BASE_URL):
                f = ROOT / urllib.parse.unquote(m.group(1)[len(BASE_URL):])
                if not f.exists(): errs.append(f'{n}: {key} file not found: {f.relative_to(ROOT)}')
        for rel in re.findall(r'<source[^>]*\bsrcset="([^"]+)"', t):
            if not (ROOT / urllib.parse.unquote(rel.lstrip('/'))).exists(): errs.append(f'{n}: <source srcset> file not found: {rel}')
        if p in pages:   # trust signals: valid JSON-LD that points to the official site, plus a visible link to it
            lds = re.findall(r'<script type="application/ld\+json">(.*?)</script>', t, re.S)
            if len(lds) != 1: errs.append(f'{n}: need exactly one JSON-LD block, found {len(lds)}')
            else:
                try:
                    g = json.loads(lds[0]).get('@graph', [])
                    if not any('https://settwor.github.io/' in (x.get('sameAs') or []) for x in g): errs.append(f'{n}: JSON-LD artist has no sameAs link to https://settwor.github.io/')
                except ValueError as e: errs.append(f'{n}: JSON-LD is not valid JSON ({e})')
            if 'href="https://settwor.github.io/"' not in t: errs.append(f'{n}: no visible link to https://settwor.github.io/')
        if re.search(r'<script\b(?![^>]*application/ld\+json)', t): errs.append(f'{n}: executable <script> found — site is static HTML/CSS (only JSON-LD allowed, see AGENTS.md)')

    sm = SITEMAP.read_text(encoding='utf-8') if SITEMAP.exists() else ''
    for p in pages:
        loc = BASE_URL if p.name == 'index.html' else BASE_URL + urllib.parse.quote(p.name)
        if f'<loc>{loc}</loc>' not in sm: errs.append(f'sitemap.xml: missing {loc} (run: python scripts/release.py sitemap)')
    if not (ROOT / 'robots.txt').exists(): errs.append('robots.txt missing')

    css = (ROOT / 'css' / 'style.css').read_text(encoding='utf-8')
    if re.search(r'(min|max)-device-(width|height)', css): errs.append('css/style.css: device-width/height media queries are forbidden')
    if re.search(r'@media[^{]*prefers-reduced-motion', css) is None: errs.append('css/style.css: prefers-reduced-motion block missing')

    if errs:
        print('CHECK FAILED:'); [print('  -', e) for e in errs]; sys.exit(1)
    print(f'check: OK (version {version}, {len(pages)} pages, {len(names)} skills)')


def bump(level, note):
    a, b, c = map(int, read_version().split('.'))
    a, b, c = {'major': (a + 1, 0, 0), 'minor': (a, b + 1, 0), 'patch': (a, b, c + 1)}[level]
    new = f'{a}.{b}.{c}'
    VERSION_FILE.write_text(new + '\n', encoding='utf-8', newline='\n')
    today = datetime.date.today().isoformat()
    entry = f'## [{new}] - {today}\n\n- {note or "TODO: describe the change"}\n\n'
    t = CHANGELOG.read_text(encoding='utf-8') if CHANGELOG.exists() else '# Changelog\n'
    i = t.find('\n## [')
    t = (t[:i + 1] + entry + t[i + 1:]) if i != -1 else t.rstrip() + '\n\n' + entry
    CHANGELOG.write_text(t, encoding='utf-8', newline='\n')
    build_sitemap(today)
    print(f'bump: {level} -> {new}')
    sync(new)
    return new


def excluded(rel):
    parts = rel.parts
    return any(fnmatch.fnmatch(x, pat) for x in parts for pat in EXCLUDE)


def build_zip(version):
    DIST.mkdir(exist_ok=True)
    out = DIST / archive_name(version)
    if out.exists(): out.unlink()
    files = [p for p in sorted(ROOT.rglob('*')) if p.is_file() and not excluded(p.relative_to(ROOT))]
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in files:
            z.write(p, p.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(out) as z:
        assert z.read('VERSION').decode().strip() == version, 'VERSION inside archive does not match'
        assert z.testzip() is None
    print(f'zip: {out.relative_to(ROOT)}  ({len(files)} files, {out.stat().st_size/1024/1024:.1f} MB)')
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=['check', 'sync', 'sitemap', 'bump', 'zip', 'release'])
    ap.add_argument('level', nargs='?', choices=['patch', 'minor', 'major'])
    ap.add_argument('--note', default='')
    a = ap.parse_args()
    if a.cmd in ('bump', 'release') and not a.level: ap.error(f'{a.cmd} needs patch|minor|major')
    if a.cmd == 'check': check(read_version())
    elif a.cmd == 'sync': sync(read_version())
    elif a.cmd == 'sitemap': build_sitemap()
    elif a.cmd == 'bump': bump(a.level, a.note)
    elif a.cmd == 'zip': v = read_version(); sync(v); build_sitemap('keep'); check(v); build_zip(v)
    elif a.cmd == 'release': v = bump(a.level, a.note); check(v); build_zip(v)


if __name__ == '__main__':
    main()
