#!/usr/bin/env python3
"""
CDRA — measures the height of every embed widget page (v1.15.0) and writes src/embed-sizes.json.

    pip install playwright && playwright install chromium
    python scripts/measure_embed.py          # then: python scripts/build_pages.py

The widget is 504 px wide at its natural size (31.5rem at 16px); its height depends on the texts (e.g. the artist award has one row less).
build_pages.py puts the measured height into the aspect-ratio of the ready-made <iframe> code (EMBED.html), so the host page reserves
exactly the right space and the widget scales proportionally. Run this again after any change to the plaque texts, sizes or
css/embed.css. It only reads the generated embed/*.html files (light theme); it writes nothing else.
"""
import json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
import build_pages  # noqa: E402


def main():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit('Playwright is not installed: pip install playwright && playwright install chromium')
    d = build_pages.load_data()
    sizes = {}
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_context(reduced_motion='reduce').new_page()
        pg.set_viewport_size({'width': build_pages.EMBED_W, 'height': 700})
        for fname, _ in build_pages.embed_specs(d):
            pg.goto((ROOT / build_pages.EMBED_DIR / build_pages.embed_name(fname, 'light')).as_uri())
            pg.wait_for_timeout(800)
            h = pg.evaluate("document.querySelector('.embed .s1').getBoundingClientRect().height")
            sizes[fname] = round(h)
            print(f'{fname}: {h:.1f} -> {sizes[fname]}')
        b.close()
    build_pages.EMBED_SIZES.write_text(json.dumps(sizes, indent=2, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')
    print('wrote', build_pages.EMBED_SIZES.relative_to(ROOT))


if __name__ == '__main__':
    main()
