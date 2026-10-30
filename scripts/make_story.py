#!/usr/bin/env python3
"""
CDRA — story pictures 1080×1920 for the share window: images/story/<page>.png (v1.14.15).

    python scripts/make_story.py

Each picture is a real screenshot of the first screen of the built award page (light theme, a 405×720 phone at 8/3x = exactly 1080×1920), with the scroll hint and dots hidden,
so it always matches the site. Needs Playwright + Chromium (like make_og.py). Run it after build_pages.py whenever a number, date, cover or look changes;
release.py does not run it (the pictures are static files).
"""
import pathlib, sys
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / 'images' / 'story'
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_pages

# v1.14.17: the artist page shows the portrait from settwor.com.pl; offline (or on a slow network) it never loaded and the story picture had a broken image.
# The same file lives in images/, so any request for the remote portrait is answered from the local copy.
REMOTE = 'https://settwor.com.pl/images/main.jpg'
LOCAL = ROOT / 'images' / 'SETTWOR_main.jpg'

def local_portrait(route):
    route.fulfill(path=str(LOCAL), content_type='image/jpeg')

def pages():
    return sorted(p for p in ROOT.glob('*.html') if 'class="plaque"' in p.read_text(encoding='utf-8'))

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        ctx = b.new_context(viewport={'width': 405, 'height': 720}, device_scale_factor=8 / 3, color_scheme='light', reduced_motion='reduce')
        for p in pages():
            pg = ctx.new_page()
            pg.route(REMOTE, local_portrait)
            pg.goto(p.as_uri())
            pg.add_style_tag(content='.next,.dots,.share-dlg{display:none!important}html{scroll-snap-type:none!important}')
            pg.evaluate('document.fonts.ready')
            pg.wait_for_function('Array.from(document.images).filter(i => !i.closest(\'dialog\') && i.loading !== \'lazy\').every(i => i.complete && i.naturalWidth > 0)')
            pg.wait_for_timeout(900)
            dst = OUT / (p.stem + '.png')
            pg.screenshot(path=str(dst))
            print('story:', dst.relative_to(ROOT))
            pg.close()
        b.close()

if __name__ == '__main__':
    main()
