#!/usr/bin/env python3
"""
CDRA — генератор страниц наград из одного шаблона.

    python scripts/build_pages.py            # пересобрать index.html + 4 страницы наград в корне
    python scripts/build_pages.py --check    # ничего не писать; код 1, если файлы в корне отличаются от шаблона

Общая разметка:  src/page.html     (плейсхолдеры {{ИМЯ}} и блоки {{#ИМЯ}} на отдельной строке)
Данные наград:   src/pages.json    (потоки, даты, обложки, тексты)
Версия берётся из файла VERSION. Руками править сгенерированные HTML нельзя — правка пропадёт
при следующей сборке; меняй шаблон/данные и запускай этот скрипт (release.py делает это сам).
"""
import json, pathlib, sys, urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / 'src' / 'page.html'
DATA = ROOT / 'src' / 'pages.json'
SEAL = ROOT / 'src' / 'seal.svg'
HOME = ROOT / 'src' / 'home.html'   # body of the home page; its <head> comes from src/page.html


def esc(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def url_quote(path):
    return urllib.parse.quote(path, safe='/')


def hero_picture(h):
    return (f'<img src="{h["base"]}.{h["ext"]}" class="cover {h["cls"]}" alt="{esc(h["alt"])}" '
            f'width="{h["w"]}" height="{h["h"]}" fetchpriority="high" decoding="async">')


def facts_block(facts):
    out = []
    for dt, dd, light in facts:
        cls = ' class="is-light"' if light else ''
        out += ['            <div>', f'              <dt>{esc(dt)}</dt>',
                f'              <dd{cls}>{esc(dd)}</dd>', '            </div>']
    return out


def cards_block(items, d):
    """Home page cards: one link per award, with the tier named in text (not by colour alone)."""
    out = []
    for a, hero in items:
        out += [
            '            <li>',
            f'              <a class="award-card" data-tier="{a["tier"]}" href="{url_quote(a["file"])}">',
            f'                <img src="{hero["base"]}.{hero["ext"]}" class="card-cover" alt="" width="{min(hero["w"], hero["h"])}" height="{min(hero["w"], hero["h"])}" loading="lazy" decoding="async">',
            '                <span class="card-text">',
            f'                  <span class="card-num">{a["streams"]}<span class="medal" aria-hidden="true"></span></span>',
            f'                  <span class="card-sub">all-time streams · {a["tier"].capitalize()}</span>',
            f'                  <span class="card-date">{esc(a["date"])}</span>',
            '                </span>',
            '                <img src="images/link.svg" class="icon" alt="" width="38" height="38" loading="lazy" decoding="async">',
            f'                <span class="visually-hidden"> — open the award page for {a["streams"]} streams</span>',
            '              </a>',
            '            </li>']
    return out


def awards_block(awards, current):
    out = []
    for a in awards:
        cur = ' aria-current="page"' if a['file'] == current else ''
        out += [
            '              <li>',
            f'                <p class="award-date">{esc(a["date"])}</p>',
            f'                <a class="award-link" href="{a["file"]}"{cur}>',
            f'                  <span class="award-num">{a["streams"]}</span>',
            '                  <span class="award-unit">streams</span>',
            '                  <img src="images/link.svg" class="icon" alt="" width="38" height="38" loading="lazy" decoding="async">',
            f'                  <span class="visually-hidden"> — open award page for {a["streams"]} streams</span>',
            '                </a>',
            '              </li>']
    return out


def jsonld_graph(spec, d):
    """Structured data (JSON-LD) for one page. Every fact here must also be visible on the page."""
    base, tr, ar = d['base_url'], d['track'], d['artist']
    og = base + url_quote(spec['og'])
    artist = {'@type': ['Person', 'MusicGroup'], '@id': ar['id'], 'name': ar['name'], 'url': ar['url'],
              'jobTitle': ar['job'], 'genre': ar['genres'], 'sameAs': ar['same_as']}
    page = {'@type': 'WebPage', '@id': spec['URL'] + '#webpage', 'url': spec['URL'], 'name': spec['TITLE'],
            'description': spec['DESC'], 'inLanguage': 'en',
            'isPartOf': {'@type': 'WebSite', '@id': base + '#website', 'name': 'CDRA', 'url': base},
            'primaryImageOfPage': {'@type': 'ImageObject', 'url': og}}
    graph = []
    if spec.get('is_home'):
        graph.append({'@type': 'WebSite', '@id': base + '#website', 'name': 'CDRA',
                      'alternateName': d['home']['alt_names'], 'url': base, 'inLanguage': 'en',
                      'publisher': {'@id': ar['id']}})
    if spec.get('about_track'):
        rec_id = base + '#' + tr['id']
        page['about'] = {'@id': rec_id}
        graph += [page, {'@type': 'MusicRecording', '@id': rec_id, 'name': tr['name'],
                         'byArtist': {'@id': ar['id']},
                         'inAlbum': {'@type': 'MusicAlbum', 'name': tr['album'], 'byArtist': {'@id': ar['id']}},
                         'datePublished': tr['release_iso']}]
    else:
        page['about'] = {'@id': ar['id']}
        graph.append(page)
    graph.append(artist)
    return {'@context': 'https://schema.org', '@graph': graph}


def page_specs(d):
    """Описание каждой страницы: поля шаблона. Здесь и только здесь различаются страницы."""
    base, tr = d['base_url'], d['track']
    specs = {}
    track_facts = [('Award for', tr['artist'], False), ('Date', None, True),
                   ('Label', tr['label'], True), ('Release Date', tr['release'], True)]
    for a in d['awards']:
        h = d['heroes'][a['hero']]
        title = f"{tr['name']} by {tr['artist']}: {a['streams']} streams award | CDRA"
        specs[a['file']] = dict(
            TITLE=title,
            DESC=f"CDRA award: {tr['name']} by {tr['artist']} reached {a['streams']} all-time streams.",
            URL=base + url_quote(a['file']), NUM=a['streams'], DATE=a['date'], DED_TRACK=tr['name'], TIER=a['tier'], hero=h, current=a['file'],
            og=f"{d['og_dir']}/og-{a['file'][:-5]}.png",
            group1=[('p', 't-label', 'Award for the track'), ('h1', 't-display', tr['name']), ('p', 't-title', tr['artist'])],
            facts=[(dt, a['date'] if dd is None else dd, lt) for dt, dd, lt in track_facts],
            award_label=None, about_track=True, is_home=False)
    s = d['artist_page']
    specs[s['file']] = dict(
        TITLE=f"{tr['artist']}: {s['streams']} streams award | CDRA",
        DESC=f"CDRA award: {tr['artist']} reached {s['streams']} all-time streams.",
        URL=base + url_quote(s['file']), NUM=s['streams'], DATE=s['date'], DED_TRACK=None, TIER=s['tier'], hero=d['heroes'][s['hero']], current=None,
        og=f"{d['og_dir']}/og-{s['file'][:-5]}.png",
        group1=[('p', 't-label', 'Award for'), ('h1', 't-display', tr['artist'])],
        facts=[('Date', s['date'], True)], award_label='Awards for', about_track=False, is_home=False)
    home = d['home']
    src = dict(specs[next(a['file'] for a in d['awards'] if a['key'] == home['same_as'])])
    src.update(TITLE=home['title'], DESC=home['desc'], URL=base, is_home=True, about_track=False, TIER='gold')
    specs[home['file']] = src
    return specs


def render(template, spec, d, version):
    og = d['base_url'] + url_quote(spec['og'])
    blocks = {
        'JSONLD': ['  <script type="application/ld+json">' + json.dumps(jsonld_graph(spec, d), separators=(',', ':'), ensure_ascii=False) + '</script>'],
        'HERO_GROUP1': [f'            <{t} class="{c}">{esc(x)}</{t}>' for t, c, x in spec['group1']],
        'FACTS': facts_block(spec['facts']),
        'AWARD_LABEL': [f'                <p class="t-label">{spec["award_label"]}</p>'] if spec['award_label'] else [],
        'AWARDS': awards_block(d['awards'], spec['current']),
        'HOME_TRACK_CARDS': cards_block([(a, {**d['heroes']['low'], 'base': 'images/GET_IT,Vol.1/GET_IT,Vol.1_cover', 'w': 668, 'h': 668, 'ext': 'webp'}) for a in d['awards']], d),
        'HOME_ARTIST_CARD': cards_block([(d['artist_page'], {**d['heroes']['settwor']})], d),
        'SEAL': ['        ' + ln for ln in SEAL.read_text(encoding='utf-8').rstrip('\n').split('\n')],
    }
    ded = f"Presented to <strong>{esc(d['track']['artist'])}</strong> to commemorate {spec['NUM']} <span class=\"nb\">all-time</span> streams"
    ded += f" of “{esc(spec['DED_TRACK'])}”" if spec['DED_TRACK'] else ''
    inline = {'DEDICATION': ded, 'DATE': esc(spec['DATE']), 'VERSION': version, 'TITLE': esc(spec['TITLE']), 'DESC': esc(spec['DESC']), 'URL': spec['URL'],
              'OG_IMAGE': og, 'OG_ALT': esc(spec['DESC']), 'NUM': spec['NUM'], 'TIER': spec['TIER'], 'HERO_PICTURE': hero_picture(spec['hero'])}
    if spec.get('is_home'):
        template = template[:template.index('<body')] + HOME.read_text(encoding='utf-8')
    out = []
    for line in template.split('\n'):
        s = line.strip()
        if s.startswith('{{#') and s.endswith('}}'):
            out += blocks[s[3:-2]]
            continue
        for k, v in inline.items():
            line = line.replace('{{' + k + '}}', v)
        out.append(line)
    text = '\n'.join(out)
    assert '{{' not in text, 'unfilled placeholder'
    return text


def build(check=False):
    version = (ROOT / 'VERSION').read_text(encoding='utf-8').strip()
    d = json.loads(DATA.read_text(encoding='utf-8'))
    template = TEMPLATE.read_text(encoding='utf-8')
    bad = []
    for fname, spec in page_specs(d).items():
        text = render(template, spec, d, version)
        p = ROOT / fname
        cur = p.read_text(encoding='utf-8') if p.exists() else None
        if cur != text:
            bad.append(fname)
            if not check:
                p.write_text(text, encoding='utf-8', newline='\n')
    if not check:
        print(f'build_pages: {len(page_specs(d))} pages, {len(bad)} rewritten')
    return bad


if __name__ == '__main__':
    check_only = '--check' in sys.argv
    changed = build(check=check_only)
    if check_only:
        if changed:
            print('build_pages --check: out of sync with src/page.html + src/pages.json:', ', '.join(changed))
            print('  fix: python scripts/build_pages.py')
            sys.exit(1)
        print('build_pages --check: OK (all pages match the template)')
