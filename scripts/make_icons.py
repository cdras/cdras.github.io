#!/usr/bin/env python3
"""CDRA — иконки сайта и ярлыка iPhone (images/icons/*, favicon.ico). Запуск: python scripts/make_icons.py
Фон #260041, белая надпись CDRA шрифтом Gloock, тонкая золотая рамка. Без прозрачности (iOS сам скругляет углы)."""
import pathlib, tempfile
from playwright.sync_api import sync_playwright
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / 'images' / 'icons'
FONTS = (ROOT / 'fonts' / 'fonts' / 'fonts-icons.css').as_uri()
HTML = """<!doctype html><meta charset="utf-8"><link rel="stylesheet" href="%s">
<style>html,body{margin:0;width:1024px;height:1024px;background:#260041;overflow:hidden}
.f{position:absolute;inset:96px;border:6px solid #e0b64a;border-radius:40px}
.f::after{content:"";position:absolute;inset:14px;border:2px solid rgba(224,182,74,.55);border-radius:28px}
.t{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;
 font:400 280px/1 'Gloock',Georgia,serif;letter-spacing:-.01em;color:#fff;padding-bottom:12px}</style>
<div class="f"></div><div class="t">CDRA</div>""" % FONTS

def main():
    with sync_playwright() as pw:
        b = pw.chromium.launch(); pg = b.new_page(viewport={'width': 1024, 'height': 1024})
        with tempfile.NamedTemporaryFile('w', suffix='.html', delete=False, encoding='utf-8', dir=ROOT) as f:
            f.write(HTML); tmp = pathlib.Path(f.name)
        try:
            pg.goto(tmp.as_uri()); pg.evaluate('document.fonts.ready'); pg.wait_for_timeout(300)
            pg.screenshot(path=str(OUT / '_master.png'))
        finally:
            tmp.unlink(missing_ok=True); b.close()
    m = Image.open(OUT / '_master.png').convert('RGB')
    for name, n in {'apple-touch-icon': 180, 'icon-512': 512, 'icon-256': 256, 'icon-192': 192, 'icon-96': 96, 'icon-48': 48, 'icon-32': 32, 'icon-16': 16}.items():
        m.resize((n, n), Image.LANCZOS).save(OUT / f'{name}.png', optimize=True)
    m.resize((256, 256), Image.LANCZOS).save(ROOT / 'favicon.ico', sizes=[(16, 16), (32, 32), (48, 48)])
    m.resize((180, 180), Image.LANCZOS).save(ROOT / 'apple-touch-icon.png', optimize=True)  # iOS also looks for it in the site root
    (OUT / '_master.png').unlink()
    print('icons written')

if __name__ == '__main__':
    main()
