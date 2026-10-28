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

def pages():
    return sorted(p for p in ROOT.glob('*.html') if 'class="plaque"' in p.read_text(encoding='utf-8'))

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        ctx = b.new_context(viewport={'width': 405, 'height': 720}, device_scale_factor=8 / 3, color_scheme='light', reduced_motion='reduce')
        for p in pages():
            pg = ctx.new_page()
            pg.goto(p.as_uri())
            pg.add_style_tag(content='.next,.dots,.share-dlg{display:none!important}html{scroll-snap-type:none!important}')
            pg.evaluate('document.fonts.ready')
            pg.wait_for_timeout(900)
            dst = OUT / (p.stem + '.png')
            pg.screenshot(path=str(dst))
            print('story:', dst.relative_to(ROOT))
            pg.close()
        b.close()

if __name__ == '__main__':
    main()
