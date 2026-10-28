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
  4. нет видимых элементов за левым/правым краем экрана;
  5. СТРОГОЕ ПРАВИЛО 9 (v1.14.3): каждый экран (.screen) целиком помещается в один экран устройства
     (высота экрана страницы = высоте окна), а на экране «Questions and answers» это выполняется
     в КАЖДОМ состоянии: все вопросы закрыты и по очереди открыт каждый вопрос (ничего не вылезает,
     не обрезано внутри панели, не наезжает на стрелку). Старый «долг» (экраны, которые не влезали ДО
     правила 9) записан в scripts/fit_debt.json: новые нарушения роняют аудит, долг только уменьшается.

Нужен Playwright:  pip install playwright && playwright install chromium
(путь к своему Chromium можно задать переменной CDRA_CHROMIUM).
Сайт поднимается на временном локальном сервере, интернет не нужен.
Код выхода 1, если найдена хотя бы одна проблема.
"""
import argparse, functools, http.server, json, os, pathlib, socketserver, sys, threading

ROOT = pathlib.Path(__file__).resolve().parent.parent

# 24 размера: ширина×высота, от 320×568 до 2560×1440 (включая 844×390 и 768×1024)
SIZES = [
    (320, 568), (360, 640), (375, 667), (390, 844), (393, 852), (412, 915), (430, 932),
    (568, 320), (667, 375), (844, 390), (932, 430),
    (600, 960), (768, 1024), (820, 1180), (1024, 768), (1180, 820),
    (1280, 720), (1366, 768), (1536, 864), (1920, 1080), (2560, 1440),
    # v1.14.3: phones with the browser's own bars showing (the visible page is shorter than the screen)
    (375, 553), (390, 664), (360, 560),
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
    // v1.14.25 (owner): the award code on the plate is deliberately tiny and faint; the same code is full size in the facts row and the registry
    const own = [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim()) && !el.closest('.s1 .plaque > .award-code');
    if (own) {
      const fs = parseFloat(getComputedStyle(el).fontSize);
      if (fs < minText - tol) out.push(['text', `${label(el)}: ${fs.toFixed(2)} px`]);
    }
  }
  return out;
}
"""

# v1.14.3, правило 9: экран влезает в окно; экран с вопросами — в каждом состоянии
FIT_JS = """
() => [...document.querySelectorAll('.screen')].map(s => ({id: s.id, h: Math.round(s.getBoundingClientRect().height), vh: innerHeight}))
"""

FAQ_JS = """
(i) => {
  const s = document.querySelector('.faq-screen');
  const ds = [...s.querySelectorAll('.faq details')];
  ds.forEach((d, k) => { if (k === i) d.setAttribute('open', ''); else d.removeAttribute('open'); });
  const st = s.querySelector('.stack').getBoundingClientRect();
  const f = s.querySelector('.faq'); const fr = f.getBoundingClientRect();
  const out = []; const tol = 0.75;
  if (s.getBoundingClientRect().height > innerHeight + 1) out.push('screen taller than the window');
  if (fr.top < st.top - tol || fr.bottom > st.bottom + tol) out.push('the list leaves its box');
  const rs = [...f.querySelectorAll('summary')].map(e => e.getBoundingClientRect());
  rs.forEach((r, k) => {
    if (r.top < st.top - tol || r.bottom > st.bottom + tol) out.push('question ' + (k + 1) + ' outside its box');
    if (r.right > innerWidth + tol || r.left < -tol) out.push('question ' + (k + 1) + ' off the side');
  });
  const a = i >= 0 ? ds[i].querySelector('.faq-a') : null;
  if (a) {
    const ar = a.getBoundingClientRect();
    if (a.scrollHeight > a.clientHeight + 1) out.push('answer clipped inside its box (' + a.scrollHeight + ' > ' + a.clientHeight + ')');
    if (ar.top < st.top - tol || ar.bottom > st.bottom + tol) out.push('answer box outside the stack');
    if (getComputedStyle(a).position === 'absolute') {
      const first = Math.min(...rs.map(r => r.top));
      if (ar.bottom > first + tol) out.push('answer panel overlaps the number chips');
    }
    for (const el of a.querySelectorAll('p, a')) {
      const r = el.getBoundingClientRect();
      if (r.height > 0 && (r.bottom > ar.bottom + tol || r.top < ar.top - tol)) out.push('answer text outside its box');
    }
  }
  const nx = s.querySelector('.next');
  if (nx && fr.bottom > nx.getBoundingClientRect().top + tol) out.push('the list overlaps the arrow');
  return out;
}
"""

DEBT_FILE = ROOT / 'scripts' / 'fit_debt.json'
NO_ANIM = '*, *::before, *::after, ::details-content { transition: none !important; animation: none !important; }'


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
    for extra in ('404.html', 'PRIVACY-POLICY.html'):
        if (ROOT / extra).exists(): names.append(extra)
    return names


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--page', action='append', help='только эта страница (можно несколько раз)')
    ap.add_argument('--size', action='append', help='только этот размер, например 844x390')
    ap.add_argument('--shots', help='папка для скриншотов первого экрана')
    ap.add_argument('--write-debt', action='store_true', help='записать текущие нарушения правила 9 (кроме экрана вопросов) в scripts/fit_debt.json')
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
    fit_found = set()          # «страница|экран|ШxВ» — экраны, которые не влезают (правило 9)
    debt = set(json.loads(DEBT_FILE.read_text(encoding='utf-8'))) if DEBT_FILE.exists() else set()
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

                # правило 9: каждый экран влезает в окно
                if name not in ('404.html', 'PRIVACY-POLICY.html'):
                    for r in page.evaluate(FIT_JS):
                        if r['h'] > r['vh'] + 1:
                            fit_found.add(f"{name}|{r['id']}|{w}x{h}")
                    # экран вопросов: все закрыты и каждый открыт по очереди (без анимации: меряем итог)
                    if page.query_selector('.faq-screen'):
                        page.add_style_tag(content=NO_ANIM)
                        n = page.evaluate("document.querySelectorAll('.faq-screen .faq details').length")
                        for i in range(-1, n):
                            for msg in page.evaluate(FAQ_JS, i):
                                problems.append((name, f'{w}×{h}', 'fit', f"questions, {'all closed' if i < 0 else 'question ' + str(i + 1) + ' open'}: {msg}"))
                if a.shots: page.screenshot(path=str(pathlib.Path(a.shots) / f'{pathlib.Path(name).stem}_{w}x{h}.png'))
            ctx.close()
        browser.close()
    httpd.shutdown()

    # правило 9: экран вопросов («s3» с .faq) не имеет права быть в долге; остальные — только старый долг
    new_fit = sorted(k for k in fit_found if k not in debt)
    for k in new_fit:
        page_, scr, size = k.split('|')
        problems.append((page_, size, 'fit', f'screen #{scr} does not fit one window (rule 9) and is not in scripts/fit_debt.json'))
    if a.write_debt:
        keep = sorted(k for k in fit_found if not (k.split('|')[0] in ('index.html', 'AWARD-STANDARDS.html') and k.split('|')[1] == 's3'))
        DEBT_FILE.write_text(json.dumps(keep, indent=0, ensure_ascii=False) + '\n', encoding='utf-8')
        print(f'fit_debt.json: {len(keep)} записей')
    paid = sorted(k for k in debt if k not in fit_found)

    seen = set(); uniq = []
    for p in problems:
        if p not in seen: seen.add(p); uniq.append(p)
    if uniq:
        print(f'AUDIT FAILED: {len(uniq)} проблем(ы) на {checked} проверках')
        for name, size, kind, msg in uniq: print(f'  - {name} @ {size} [{kind}] {msg}')
        sys.exit(1)
    print(f'audit_layout: OK — {len(names)} страниц × {len(sizes)} размеров = {checked} проверок, проблем нет')
    left = len(fit_found & debt)
    if left: print(f'  правило 9, старый долг: {left} экран(ов)×размер(ов) всё ещё не влезают (scripts/fit_debt.json, TODO.md задача 14); новых нарушений нет')
    if paid and not a.page and not a.size: print(f'  долг уменьшился: {len(paid)} запис(ей) в fit_debt.json уже влезают — удали их из файла (python scripts/audit_layout.py --write-debt)')


if __name__ == '__main__':
    main()
