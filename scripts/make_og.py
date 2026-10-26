#!/usr/bin/env python3
"""
CDRA — карточки 1200×630 для превью ссылок (Telegram, соцсети): images/og/og-<страница>.png.

    python scripts/make_og.py

Берёт обложку, число потоков и тексты из src/pages.json, шрифт Outfit (весь текст, с v1.9.0) — из fonts/fonts/fonts-site.css, как на сайте.
Нужен Playwright + Chromium (как для audit_layout.py). Результат — обычные PNG, их коммитят вместе с сайтом.
Запускать при смене обложки, числа потоков или шрифтов; в release.py не входит (картинки статичны).
"""
import json, pathlib, tempfile
from playwright.sync_api import sync_playwright
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / 'images' / 'og'
INK = '#260041'
SEAL = (ROOT / 'src' / 'seal.svg').read_text(encoding='utf-8')
TIERS = {  # same values as body[data-tier] in css/style.css
    'bronze':   ('#f3d3b4', '#c98a52', '#8a5226', '#8a5226', '201,138,82'),
    'silver':   ('#f6f8fb', '#c3c9d2', '#7b8594', '#66707f', '195,201,210'),
    'gold':     ('#fbeeb0', '#e0b64a', '#a67a17', '#8a6410', '224,182,74'),
    'platinum': ('#ffffff', '#d9dfea', '#8592ab', '#566684', '190,200,220'),
}

HTML = """<!doctype html><meta charset="utf-8">
<link rel="stylesheet" href="{fonts}">
<style>
  html,body{{margin:0;width:1200px;height:630px;background:#fff;color:{ink};overflow:hidden}}
  .card{{position:relative;width:1200px;height:630px;display:flex;align-items:center;gap:48px;padding:36px 84px 0 84px;box-sizing:border-box}}
  .cover{{flex:0 0 auto;width:{cw}px;height:{ch}px;object-fit:cover;border-radius:6px}}
  .txt{{flex:1 1 auto;display:flex;flex-direction:column;gap:26px;min-width:0}}
  .g{{display:flex;flex-direction:column;gap:6px}}
  .lab{{font-family:'Outfit',system-ui,sans-serif;font-size:34px;line-height:1.15}}
  .big{{font-family:'Outfit',system-ui,sans-serif;font-size:{bigfs}px;line-height:1.05;letter-spacing:-.01em;white-space:nowrap}}
  .sub{{font-family:'Outfit',system-ui,sans-serif;font-size:40px;line-height:1.1}}
  .num{{font-weight:700;font-family:'Outfit',system-ui,sans-serif;font-size:92px;line-height:1;letter-spacing:-.01em;white-space:nowrap}}
  .logo{{position:absolute;left:84px;bottom:46px;height:28px;width:auto}}
  html{{--g-hi:{g_hi};--g-mid:{g_mid};--g-lo:{g_lo}}}
  .frame{{position:absolute;inset:54px 22px 22px;border:2px solid {line};border-radius:6px;box-shadow:inset 0 0 0 8px #fff,inset 0 0 0 10px rgba({rgb},.9)}}
  .glow{{position:absolute;inset:0;background:radial-gradient(ellipse 60% 70% at 38% 50%,rgba({rgb},.14),transparent 70%)}}
  .seal{{position:absolute;left:calc(50% - 52px);top:2px;width:104px;height:auto;filter:drop-shadow(0 6px 8px rgba(38,0,65,.28))}}
</style>
<div class="card">
  <div class="glow"></div><div class="frame"></div>{seal}
  <img class="cover" src="{cover}" alt="">
  <div class="txt">
    <div class="g">{group1}</div>
    <div class="g"><div class="lab">for reaching</div><div class="num">{num}</div><div class="sub">all-time streams</div></div>
  </div>
  <img class="logo" src="{logo}" alt="">
</div>"""


# уменьшает .big и .num, пока они не влезут в колонку (длинные названия и «1,000,000»)
FIT = """() => {
  const col = document.querySelector('.txt').clientWidth;
  for (const el of document.querySelectorAll('.big, .num')) {
    let fs = parseFloat(getComputedStyle(el).fontSize);
    while (el.scrollWidth > col && fs > 24) { fs -= 2; el.style.fontSize = fs + 'px'; }
  }
}"""


def main():
    d = json.loads((ROOT / 'src' / 'pages.json').read_text(encoding='utf-8'))
    tr = d['track']
    jobs = []
    for a in d['awards']:
        h = d['heroes'][a['hero']]
        jobs.append((f"og-{pathlib.Path(a['file']).stem}", h, a['streams'], a['tier'],
                     f'<div class="lab">Award for the track</div><div class="big">{tr["name"]}</div><div class="sub">{tr["artist"]}</div>'))
    s = d['artist_page']
    jobs.append((f"og-{pathlib.Path(s['file']).stem}", d['heroes'][s['hero']], s['streams'], s['tier'],
                 f'<div class="lab">Award for</div><div class="big">{tr["artist"]}</div>'))
    fonts = (ROOT / 'fonts' / 'fonts' / 'fonts-site.css').as_uri()
    logo = (ROOT / 'images' / 'CDRAlogo.svg').as_uri()
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={'width': 1200, 'height': 630}, device_scale_factor=1)
        for name, h, num, tier, group1 in jobs:
            g_hi, g_mid, g_lo, line, rgb = TIERS[tier]
            square = h['cls'] == 'cover--square'
            cw, ch = (366, 366) if square else (500, 371)
            cover = (ROOT / f"{h['base']}.{h['ext']}").as_uri()
            html = HTML.format(fonts=fonts, ink=INK, cw=cw, ch=ch, bigfs=64, cover=cover, group1=group1, num=num, logo=logo,
                              g_hi=g_hi, g_mid=g_mid, g_lo=g_lo, line=line, rgb=rgb, seal=SEAL)
            with tempfile.NamedTemporaryFile('w', suffix='.html', delete=False, encoding='utf-8', dir=ROOT) as f:
                f.write(html); tmp = pathlib.Path(f.name)
            try:
                pg.goto(tmp.as_uri()); pg.evaluate('document.fonts.ready'); pg.wait_for_timeout(200)
                pg.evaluate(FIT)
                out = OUT / f'{name}.png'
                pg.screenshot(path=str(out), clip={'x': 0, 'y': 0, 'width': 1200, 'height': 630})
            finally:
                tmp.unlink(missing_ok=True)
            im = Image.open(out).convert('RGB'); im.save(out, optimize=True)
            print(f'{out.relative_to(ROOT)}  {im.size}  {out.stat().st_size/1024:.0f} KB')
        b.close()


if __name__ == '__main__':
    main()
