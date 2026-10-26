#!/usr/bin/env python3
"""
CDRA layout audit — обязательный шаг перед выдачей архива (см. AGENTS.md, раздел 5).

    python scripts/audit_layout.py            # все страницы × 21 размер экрана
    python scripts/audit_layout.py --page index.html --size 844x390
    python scripts/audit_layout.py --shots dist/shots    # + скриншоты первого экрана

Проверяет на каждом размере и странице:
  1. нет горизонтальной прокрутки;
  2. кнопки и ссылки не меньше 44×44 px;
  3. текст не меньше 13 px;
  4. нет видимых элементов за левым/правым краем экрана.

Нужен Playwright:  pip install playwright && playwright install chromium
(путь к своему Chromium можно задать переменной CDRA_CHROMIUM).
Сайт поднимается на временном локальном сервере, интернет не нужен.
Код выхода 1, если найдена хотя бы одна проблема.
"""
import argparse, functools, http.server, os, pathlib, socketserver, sys, threading

ROOT = pathlib.Path(__file__).resolve().parent.parent

# 21 размер: ширина×высота, от 320×568 до 2560×1440 (включая 844×390 и 768×1024)
SIZES = [
    (320, 568), (360, 640), (375, 667), (390, 844), (393, 852), (412, 915), (430, 932),
    (568, 320), (667, 375), (844, 390), (932, 430),
    (600, 960), (768, 1024), (820, 1180), (1024, 768), (1180, 820),
    (1280, 720), (1366, 768), (1536, 864), (1920, 1080), (2560, 1440),
]
MIN_TAP = 44      # px
MIN_TEXT = 13     # px
TOL = 0.5         # допуск на округление

JS = """
({minTap, minText, tol}) => {
  const out = [];
  const vw = document.documentElement.clientWidth;
  const label = el => {
    const t = (el.getAttribute('aria-label') || el.textContent || el.alt || '').trim().replace(/\\s+/g, ' ').slice(0, 40);
    return el.tagName.toLowerCase() + (el.className && typeof el.className === 'string' ? '.' + el.className.trim().split(/\\s+/).join('.') : '') + (t ? ` “${t}”` : '');
  };
  const visible = el => {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || cs.display === 'contents') return false;
    const r = el.getBoundingClientRect();
    return r.width > 1 && r.height > 1;
  };
  const sr = el => !!el.closest('.visually-hidden');

  // 1. горизонтальная прокрутка
  const se = document.scrollingElement;
  if (se.scrollWidth > se.clientWidth + tol) out.push(['hscroll', `scrollWidth ${se.scrollWidth} > clientWidth ${se.clientWidth}`]);
  if (document.body.scrollWidth > vw + tol) out.push(['hscroll', `body.scrollWidth ${document.body.scrollWidth} > ${vw}`]);

  for (const el of document.querySelectorAll('body *')) {
    if (!visible(el) || sr(el)) continue;
    const r = el.getBoundingClientRect();

    // 4. за краем экрана (по горизонтали; вертикально страница листается)
    if (r.left < -tol || r.right > vw + tol) out.push(['offscreen', `${label(el)}: left ${r.left.toFixed(1)}, right ${r.right.toFixed(1)}, viewport ${vw}`]);

    // 2. цели нажатия
    if (el.matches('a[href], button, input, select, textarea, summary, [role=button]')) {
      if (r.width < minTap - tol || r.height < minTap - tol) out.push(['tap', `${label(el)}: ${r.width.toFixed(1)}×${r.height.toFixed(1)} px`]);
    }

    // 3. размер текста (только у элементов с собственным текстом)
    const own = [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim());
    if (own) {
      const fs = parseFloat(getComputedStyle(el).fontSize);
      if (fs < minText - tol) out.push(['text', `${label(el)}: ${fs.toFixed(2)} px`]);
    }
  }
  return out;
}
"""


def serve():
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a, **k): pass
    handler = functools.partial(Quiet, directory=str(ROOT))
    class QuietServer(socketserver.TCPServer):
        def handle_error(self, request, client_address): pass   # браузер сам обрывает загрузки при навигации
    httpd = QuietServer(('127.0.0.1', 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def pages():
    names = sorted(p.name for p in ROOT.glob('*.html') if 'class="screen' in p.read_text(encoding='utf-8'))
    for extra in ('404.html', 'fonts/compare.html'):
        if (ROOT / extra).exists(): names.append(extra)
    return names


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--page', action='append', help='только эта страница (можно несколько раз)')
    ap.add_argument('--size', action='append', help='только этот размер, например 844x390')
    ap.add_argument('--shots', help='папка для скриншотов первого экрана')
    a = ap.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit('Playwright не установлен: pip install playwright && playwright install chromium')

    sizes = [tuple(map(int, s.lower().split('x'))) for s in a.size] if a.size else SIZES
    names = a.page or pages()
    if a.shots: pathlib.Path(a.shots).mkdir(parents=True, exist_ok=True)

    httpd = serve(); base = f'http://127.0.0.1:{httpd.server_address[1]}/'
    problems = []; checked = 0
    with sync_playwright() as pw:
        kw = {'executable_path': os.environ['CDRA_CHROMIUM']} if os.environ.get('CDRA_CHROMIUM') else {}
        browser = pw.chromium.launch(**kw)
        for w, h in sizes:
            ctx = browser.new_context(viewport={'width': w, 'height': h}, device_scale_factor=1,
                                      has_touch=False)
            page = ctx.new_page()
            for name in names:
                page.goto(base + name, wait_until='load')
                page.evaluate('document.fonts.ready')
                found = page.evaluate(JS, {'minTap': MIN_TAP, 'minText': MIN_TEXT, 'tol': TOL})
                checked += 1
                for kind, msg in found: problems.append((name, f'{w}×{h}', kind, msg))
                if a.shots: page.screenshot(path=str(pathlib.Path(a.shots) / f'{pathlib.Path(name).stem}_{w}x{h}.png'))
            ctx.close()
        browser.close()
    httpd.shutdown()

    seen = set(); uniq = []
    for p in problems:
        if p not in seen: seen.add(p); uniq.append(p)
    if uniq:
        print(f'AUDIT FAILED: {len(uniq)} проблем(ы) на {checked} проверках')
        for name, size, kind, msg in uniq: print(f'  - {name} @ {size} [{kind}] {msg}')
        sys.exit(1)
    print(f'audit_layout: OK — {len(names)} страниц × {len(sizes)} размеров = {checked} проверок, проблем нет')


if __name__ == '__main__':
    main()
