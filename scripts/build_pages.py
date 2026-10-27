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
import datetime, json, pathlib, sys, urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / 'src' / 'page.html'
DATA = ROOT / 'src' / 'pages.json'
HOME = ROOT / 'src' / 'home.html'   # body of the home page; its <head> comes from src/page.html
LEGACY_ARTIST_URLS = ['SETTWOR-1m.html']   # v1.12.0: old public URLs of the artist award, kept as redirects
STANDARDS = ROOT / 'src' / 'standards.html'   # body of the award-standards page (v1.11.0)


def esc(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def url_quote(path):
    return urllib.parse.quote(path, safe='/')


def hero_src(h):
    return h.get('src') or (h.get('sleeve') and f'{h["sleeve"]}.{h["ext"]}') or f'{h["base"]}.{h["ext"]}'


def zoom_parts(h):
    """v1.11.9 (task 13.2): tap the cover to enlarge it. Pure CSS: a checkbox before <main>, the cover inside a <label>, a full-screen
    <label> as the way out. Returns (toggle, box) markup for the two placeholders; both are empty without a hero."""
    if not h:
        return '', ''
    toggle = '  <input type="checkbox" id="zoom" class="zoom-toggle" aria-label="Enlarge the cover">'
    box = ('  <label class="zoom-box" for="zoom">\n'
           f'    <img src="{hero_src(h)}" class="zoom-img" alt="{esc(h["alt"])}" width="{h["w"] if not h.get("sleeve") else 668}" height="{h["h"] if not h.get("sleeve") else 668}" decoding="async">\n'
           '    <span class="zoom-close">Close</span>\n'
           '  </label>')
    return toggle, box


def hero_picture(h):
    return '<label class="zoom-cover" for="zoom">' + _hero_picture(h) + '</label>'


def _hero_picture(h):
    if h.get('sleeve'):
        # v1.9.9 (task 12.4, part 1): plain cover + a disc drawn in CSS (metal from body[data-tier]).
        # The box keeps the old 900:668 proportions, so the screen heights do not change.
        return (f'<span class="cover {h["cls"]} has-disc"><span class="disc" aria-hidden="true"></span>'
                f'<img src="{h.get("src") or h["sleeve"] + "." + h["ext"]}" class="sleeve" alt="{esc(h["alt"])}" '
                f'width="668" height="668" fetchpriority="high" decoding="async"></span>')
    return (f'<img src="{h.get("src") or h["base"] + "." + h["ext"]}" class="cover {h["cls"]}" alt="{esc(h["alt"])}" '
            f'width="{h["w"]}" height="{h["h"]}" fetchpriority="high" decoding="async">')


def fact_link(label, url, aria=None):
    """One link of a fact row. v1.11.10: optional aria-label (it always contains the visible label); a mailto: link opens no new tab."""
    attrs = ' rel="noopener"' + ('' if url.startswith('mailto:') else ' target="_blank"')
    if aria:
        attrs += f' aria-label="{esc(aria)}"'
    return f'<a class="fact-link" href="{esc(url)}"{attrs}>{esc(label)}</a>'


def share_links(url, title, text):
    """v1.11.10 (task 13.3): plain share links built from the page URL: no scripts, no trackers, no extra parameters.
    Telegram and X open their own share pages in a new tab; e-mail opens the visitor's mail app."""
    q = lambda v: urllib.parse.quote(v, safe='')
    return [('Telegram', f'https://t.me/share/url?url={q(url)}&text={q(text)}', 'Share on Telegram'),
            ('X', f'https://twitter.com/intent/tweet?text={q(text)}&url={q(url)}', 'Share on X'),
            ('Email', f'mailto:?subject={q(title)}&body={q(text + chr(10) + url)}', 'Share by email')]


def facts_block(facts):
    out = []
    for dt, dd, light, *href in facts:
        cls = ' class="is-light is-links"' if (light and href) else (' class="is-light"' if light else '')
        if dt == 'Share':   # v1.11.10: no dot separators, the links sit in a wrapping row (see css «v1.11.10»)
            cls = ' class="is-light is-links is-share"'
        if not href:
            text = esc(dd)
        else:   # href[0] = list of (label, url): several links in one row (v1.10.5)
            text = ' <span aria-hidden="true">·</span> '.join(fact_link(*x) for x in href[0])
        out += ['            <div>', f'              <dt>{esc(dt)}</dt>',
                f'              <dd{cls}>{text}</dd>', '            </div>']
    return out


def card_art(hero):
    """Cover of a home card; for the track awards a small CSS disc peeks out from under it (v1.9.10, task 12.4 part 2)."""
    s = min(hero["w"], hero["h"])
    img = (f'<img src="{hero.get("src") or hero["base"] + "." + hero["ext"]}" class="card-cover" alt="" width="{s}" height="{s}" '
           f'loading="lazy" decoding="async">')
    if hero.get('disc'):
        return ['                <span class="card-art has-disc"><span class="disc" aria-hidden="true"></span>' + img + '</span>']
    return ['                ' + img]


def earned_awards(d):
    """v1.11.2 (owner): the track awards come from the standards table. A recorded milestone (src/pages.json › milestones:
    streams + date) becomes an award page only when its number equals the Single number of a level in `standards`; the level
    name and the metal come from that level. Change a number in `standards` and the page appears or disappears by itself."""
    out = []
    for m in d['milestones']:
        n = int(m['streams'].replace(',', ''))
        for lv in d['standards']['levels']:
            if lv['values'][0] == n:
                out.append({**m, 'tier': lv['tier'], 'level': lv['name'], 'n': n})
                break
    return sorted(out, key=lambda a: a['n'])


def earned_album(d):
    """v1.12.0: the album award follows the Album column of `standards` the same way the track awards follow the Single column.
    Returns None when the number is not a level of the Album column (no page then)."""
    a = d.get('album_award')
    if not a:
        return None
    n = int(a['streams'].replace(',', ''))
    for lv in d['standards']['levels']:
        if lv['values'][1] == n:
            return {**a, 'tier': lv['tier'], 'level': lv['name']}
    return None


def earned_artist(d):
    """v1.13.0 (owner: the artist award may show its level and a disc now): level and metal come from the Artist column of `standards`.
    No match = no level (the page still exists, as before)."""
    a = dict(d['artist_page'])
    n = int(a['streams'].replace(',', ''))
    a['tier'] = None
    for lv in d['standards']['levels']:
        if lv['values'][2] == n:
            a['tier'], a['level'] = lv['tier'], lv['name']
            break
    return a


def parse_date(s):
    """v1.12.0: award dates may be exact («May 1, 2025»), a month («October 2026») or a season («Winter 2026»), as the owner gives them."""
    s = s.strip()
    for f in ('%B %d, %Y', '%B %Y'):
        try:
            return datetime.datetime.strptime(s, f).date()
        except ValueError:
            pass
    season, year = s.split()
    return datetime.date(int(year), {'Winter': 1, 'Spring': 4, 'Summer': 7, 'Autumn': 10, 'Fall': 10}[season], 1)


def date_on(s):
    """'on May 1, 2025' for an exact date, 'in October 2026' for a month or a season."""
    return ('on ' if ',' in s else 'in ') + s


def load_data():
    d = json.loads(DATA.read_text(encoding='utf-8'))
    d['awards'] = earned_awards(d)
    d['album'] = earned_album(d)
    d['artist_page'] = earned_artist(d)
    return d


def join_and(items):
    return items[0] if len(items) == 1 else ', '.join(items[:-1]) + ' and ' + items[-1]


def home_texts(d):
    """Home texts that list the awards: generated, so they follow the standards table."""
    nums = [a['streams'] for a in d['awards']]; tr = d['track']; art = d['artist_page']; alb = d.get('album')
    words = {1: 'One', 2: 'Two', 3: 'Three', 4: 'Four', 5: 'Five', 6: 'Six', 7: 'Seven', 8: 'Eight'}
    total = len(nums) + (1 if alb else 0) + 1
    bits = ([f"{join_and(nums)} for the track"] if nums else []) + ([f"{alb['streams']} for the album"] if alb else []) + [f"{art['streams']} for the artist"]
    lead = f"{words.get(total, total)} {'awards' if total > 1 else 'award'} for all-time streams: " + join_and(bits) + "."
    which = (f"The {join_and(nums)} {'awards are' if len(nums) > 1 else 'award is'} for the track “{esc(tr['name'])}” from the album {esc(tr['album'])}, "
             f"released on {esc(tr['release'])}. " if nums else '') \
          + (f"The {alb['streams']} award is for the album {esc(tr['album'])}. " if alb else '') \
          + f"The {art['streams']} award is for {esc(tr['artist'])} as an artist."
    parts = [f"{a['streams']} for the track {date_on(a['date'])}" for a in d['awards']] \
          + ([f"{alb['streams']} for the album {date_on(alb['date'])}"] if alb else []) + [f"{art['streams']} for the artist {date_on(art['date'])}"]
    dates = '; '.join(parts) + '.'
    # v1.11.15: figures for the register strip on the first screen; all from pages.json, so they follow the awards list
    def short_n(n): return f'{n / 1_000_000:g}M' if n >= 1_000_000 else f'{n // 1000}K'
    allr = d['awards'] + ([alb] if alb else []) + [art]
    top = max(int(a['streams'].replace(',', '')) for a in allr)
    last = max(allr, key=lambda a: parse_date(a['date']))
    ld = parse_date(last['date'])
    return {'HOME_LEAD': lead, 'HOME_WHICH': which, 'HOME_DATES': dates,
            'HOME_COUNT': str(total), 'HOME_TOP': short_n(top), 'HOME_TOP_FULL': f'{top:,}',
            'HOME_LATEST': ld.strftime('%b %Y'), 'HOME_LATEST_FULL': last['date']}


def level_shown(a, d):
    """Level name of an earned award (set by earned_awards), '' for the artist award."""
    return a.get('level', '')
    n = int(a['streams'].replace(',', ''))
    for lv in d['standards']['levels']:
        if lv['tier'] == tier:
            return tier.capitalize() if n >= lv['values'][0] else ''
    return ''


def cards_block(items, d):
    """Home page cards: one link per award, with the tier named in text (not by colour alone)."""
    out = []
    for a, hero in items:
        out += [
            '            <li>',
            f'              <a class="award-card"{" data-tier=" + chr(34) + a["tier"] + chr(34) if a.get("tier") else ""} href="{url_quote(a["file"])}">',
            *card_art(hero),
            '                <span class="card-text">',
            f'                  <span class="card-kind">{esc(a.get("kind", "Single"))}</span>',
            f'                  <span class="card-num">{a["streams"]}</span>',
            f'                  <span class="card-sub">all-time streams{" · " + level_shown(a, d) if level_shown(a, d) else ""}</span>',
            f'                  <span class="card-date"><span>{esc(a["date"])}</span>{" <span class=" + chr(34) + "card-days" + chr(34) + ">· " + milestone_days(d["track"], a) + "</span>" if "n" in a else ""}</span>',
            '                </span>',
            '                <img src="images/link.svg" class="icon" alt="" width="38" height="38" loading="lazy" decoding="async">',
            f'                <span class="visually-hidden"> — open the award page for {a["streams"]} streams</span>',
            '              </a>',
            '            </li>']
    return out


def short_num(n):
    """250000 -> 250K, 2500000 -> 2.5M (the narrow-screen form of a table number; the full number stays for screen readers)."""
    if n >= 1_000_000:
        v = n / 1_000_000
        return (f'{v:g}') + 'M'
    return f'{n // 1000}K'


def std_rows(std):
    """Rows of the award-standards table. A value of None means «not set yet» (shown as a dash, read as «not set»)."""
    out = []
    for lv in std['levels']:
        out += [f'            <tr data-tier="{lv["tier"]}">',
                f'              <th scope="row"><span class="lvl"><span class="mini-disc" aria-hidden="true"></span><span>{esc(lv["name"])}</span></span></th>']
        for v in lv['values']:
            if v is None:
                out.append('              <td><span aria-hidden="true">—</span><span class="visually-hidden">not set</span></td>')
            else:
                plus = '+' if lv.get('plus') else ''
                out.append(f'              <td><span class="n-full">{v:,}{plus}</span><span class="n-short" aria-hidden="true">{short_num(v)}{plus}</span></td>')
        out.append('            </tr>')
    return out


def disc_row(std):
    """Decorative row of the five metals on the first screen of the standards page (one disc per distinct tier)."""
    seen = []
    for lv in std['levels']:
        if lv['tier'] not in seen: seen.append(lv['tier'])
    return [f'          <div class="disc-row" aria-hidden="true">'] + [f'            <span class="mini-disc" data-tier="{t}"></span>' for t in seen] + ['          </div>']


def awards_block(awards, current):
    out = []
    for a in awards:
        cur = ' aria-current="page"' if a['file'] == current else ''
        out += [
            f'              <li data-tier="{a["tier"]}">',
            f'                <p class="award-date">{esc(a["date"])}</p>',
            f'                <a class="award-link" href="{a["file"]}"{cur}>',
            '                  <span class="mini-disc" aria-hidden="true"></span>',
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
                         'datePublished': tr['release_iso'], 'genre': tr['genre'], 'sameAs': [tr['spotify'], tr['apple_music'], tr['youtube_music'], tr['youtube']]}]
    else:
        if not spec.get('no_about'):
            page['about'] = {'@id': ar['id']}
        graph.append(page)
    graph.append(artist)
    return {'@context': 'https://schema.org', '@graph': graph}


def milestone_days(tr, a):
    """v1.10.3: days from the track release (src/pages.json track.release_iso) to the award date: computed, not typed."""
    import datetime
    d0 = datetime.date.fromisoformat(tr['release_iso'])
    d1 = datetime.datetime.strptime(a['date'], '%B %d, %Y').date()
    return f"{(d1 - d0).days} days after release"


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
            group1=[('p', 't-label', f"{a['level']} award for the track"), ('h1', 't-display', tr['name']), ('p', 't-title', tr['artist'])],
            facts=[(dt, a['date'] if dd is None else dd, lt) for dt, dd, lt in track_facts]
                  + [('Album', tr['album'], True), ('Genre', tr['genre'], True), ('Reached in', milestone_days(tr, a), True),
                     ('Listen', '', True, [('Spotify', tr['spotify']), ('Apple Music', tr['apple_music']), ('YouTube Music', tr['youtube_music']), ('YouTube', tr['youtube'])]),
                     ('Share', '', True, share_links(base + url_quote(a['file']), title, f"CDRA award: {tr['name']} by {tr['artist']} reached {a['streams']} all-time streams."))],
            award_label=None, about_track=True, is_home=False)
    alb = d.get('album')
    if alb:   # v1.12.0: album award page (Album column of the standards); only facts the owner gave: artist, date, label
        atitle = f"{tr['album']} by {tr['artist']}: {alb['streams']} streams award | CDRA"
        adesc = f"CDRA award: the album {tr['album']} by {tr['artist']} reached {alb['streams']} all-time streams."
        specs[alb['file']] = dict(
            TITLE=atitle, DESC=adesc, URL=base + url_quote(alb['file']), NUM=alb['streams'], DATE=alb['date'], DED_TRACK=tr['album'], TIER=alb['tier'],
            hero=d['heroes'][alb['hero']], current=None, og=f"{d['og_dir']}/og-{alb['file'][:-5]}.png",
            group1=[('p', 't-label', f"{alb['level']} award for the album"), ('h1', 't-display', tr['album']), ('p', 't-title', tr['artist'])],
            facts=[('Award for', tr['artist'], False), ('Date', alb['date'], True), ('Label', tr['label'], True),
                   ('Share', '', True, share_links(base + url_quote(alb['file']), atitle, adesc))],
            award_label='Awards for', about_track=False, is_home=False)
    s = d['artist_page']
    specs[s['file']] = dict(
        TITLE=f"{tr['artist']}: {s['streams']} streams award | CDRA",
        DESC=f"CDRA award: {tr['artist']} reached {s['streams']} all-time streams.",
        URL=base + url_quote(s['file']), NUM=s['streams'], DATE=s['date'], DED_TRACK=None, TIER=s.get('tier') or '', hero=d['heroes'][s['hero']], current=None,
        og=f"{d['og_dir']}/og-{s['file'][:-5]}.png",
        group1=[('p', 't-label', f"{s['level']} award for the artist" if s.get('level') else 'Award for'), ('h1', 't-display', tr['artist'])],
        facts=[('Date', s['date'], True), ('Share', '', True, share_links(base + url_quote(s['file']), f"{tr['artist']}: {s['streams']} streams award | CDRA", f"CDRA award: {tr['artist']} reached {s['streams']} all-time streams."))], award_label='Awards for', about_track=False, is_home=False)
    home = d['home']
    src = dict(specs[d['awards'][-1]['file'] if d['awards'] else d['artist_page']['file']])
    src.update(TITLE=home['title'], DESC=home['desc'].replace('{list}', join_and([a['streams'] for a in d['awards']] + ([alb['streams']] if alb else []) + [d['artist_page']['streams']])), URL=base, is_home=True, about_track=False, TIER='gold', body=HOME,
               og=f"{d['og_dir']}/og-{home['file'][:-5]}.png")   # v1.11.11: own preview card (was the last award's)
    specs[home['file']] = src
    # v1.11.0: the award-standards page: own body (src/standards.html), head from the shared template, no hero
    st = d['standards']
    specs[st['file']] = dict(
        TITLE=st['title'], DESC=st['desc'], URL=base + url_quote(st['file']), NUM='', DATE='', DED_TRACK=None, TIER='', hero=None, current=None,
        og=f"{d['og_dir']}/og-{st['file'][:-5]}.png", group1=[], facts=[], award_label=None,
        about_track=False, is_home=False, no_about=True, body=STANDARDS)
    return specs


def render(template, spec, d, version):
    og = d['base_url'] + url_quote(spec['og'])
    blocks = {
        'JSONLD': ['  <script type="application/ld+json">' + json.dumps(jsonld_graph(spec, d), separators=(',', ':'), ensure_ascii=False) + '</script>'],
        # v1.11.16 (owner exception to rule 8): the one local tilt script, only on pages with an award block (award pages, home)
        'TILT_JS': ['  <script src="js/tilt.js" defer></script>'] if (spec.get('hero') or spec.get('is_home')) else [],
        'HERO_GROUP1': [f'            <{t} class="{c}">{esc(x)}</{t}>' for t, c, x in spec['group1']],
        'FACTS': facts_block(spec['facts']),
        'AWARD_LABEL': [f'                <p class="t-label">{spec["award_label"]}</p>'] if spec['award_label'] else [],
        'AWARDS': awards_block(d['awards'], spec['current']),
        'HOME_TRACK_CARDS': cards_block([(a, {**d['heroes']['low'], 'base': 'images/GET_IT,Vol.1/GET_IT,Vol.1_cover', 'w': 668, 'h': 668, 'ext': 'webp', 'disc': True}) for a in d['awards']], d),
        'HOME_ALBUM_CARD': cards_block([(d['album'], {**d['heroes']['low'], 'base': 'images/GET_IT,Vol.1/GET_IT,Vol.1_cover', 'w': 668, 'h': 668, 'ext': 'webp', 'disc': True})], d) if d.get('album') else [],
        'HOME_ARTIST_CARD': cards_block([(d['artist_page'], {**d['heroes']['settwor'], 'disc': True})], d),
        'STD_ROWS': std_rows(d['standards']),
        'STD_DISCS': disc_row(d['standards']),
    }
    S = lambda t: f'<span>{t}</span>'   # v1.13.1: every phrase is its own hop target
    ded = ' '.join([S('Presented to'), f"<strong>{esc(d['track']['artist'])}</strong>", S('to commemorate'), S(spec['NUM']), '<span class="nb">all-time</span>', S('streams')]
                   + ([S(f"of “{esc(spec['DED_TRACK'])}”")] if spec['DED_TRACK'] else []))
    inline = {**home_texts(d), 'DEDICATION': ded, 'DATE': esc(spec['DATE']), 'VERSION': version, 'TITLE': esc(spec['TITLE']), 'DESC': esc(spec['DESC']), 'URL': spec['URL'],
              'OG_IMAGE': og, 'OG_ALT': esc(spec['DESC']), 'NUM': spec['NUM'], 'TIER': spec['TIER'], 'HERO_PICTURE': hero_picture(spec['hero']) if spec['hero'] else '',
              'ZOOM_TOGGLE': zoom_parts(spec['hero'])[0], 'ZOOM_BOX': zoom_parts(spec['hero'])[1]}
    if spec.get('body'):   # home and standards pages: <head> from the shared template, body from their own file
        template = template[:template.index('<body')] + spec['body'].read_text(encoding='utf-8')
    out = []
    for line in template.split('\n'):
        s = line.strip()
        if s.startswith('{{#') and s.endswith('}}'):
            out += blocks[s[3:-2]]
            continue
        for k, v in inline.items():
            line = line.replace('{{' + k + '}}', v)
        out.append(line)
    text = '\n'.join(out).replace('<body data-tier="">', '<body>')   # an award without a level name (the artist award) has no metal
    assert '{{' not in text, 'unfilled placeholder'
    return text


def build(check=False):
    version = (ROOT / 'VERSION').read_text(encoding='utf-8').strip()
    d = load_data()
    template = TEMPLATE.read_text(encoding='utf-8')
    bad = []
    keep = {a['file'] for a in d['awards']}
    for m in d['milestones']:   # recorded but not earned under the current standards: no page, no preview card
        if m['file'] in keep: continue
        for q in (ROOT / m['file'], ROOT / d['og_dir'] / f"og-{m['file'][:-5]}.png"):
            if q.exists():
                bad.append(f'{q.name} (not earned under the standards: remove)')
                if not check: q.unlink()
    # v1.12.0: the artist award moved from SETTWOR-1m.html to its new file; the old public URL stays as a tiny static redirect (rule 6a)
    new_artist = d['artist_page']['file']
    for old in LEGACY_ARTIST_URLS:
        if old == new_artist: continue
        stub = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<title>Moved | CDRA</title>\n<meta name="robots" content="noindex">\n'
                f'<meta http-equiv="refresh" content="0; url={url_quote(new_artist)}">\n<link rel="canonical" href="{d["base_url"] + url_quote(new_artist)}">\n</head>\n'
                f'<body>\n<p>This page moved to <a href="{url_quote(new_artist)}">{esc(d["track"]["artist"])}, {d["artist_page"]["streams"]} streams award</a>.</p>\n</body>\n</html>\n')
        q = ROOT / old
        if not q.exists() or q.read_text(encoding='utf-8') != stub:
            bad.append(old)
            if not check: q.write_text(stub, encoding='utf-8', newline='\n')
        oq = ROOT / d['og_dir'] / f"og-{old[:-5]}.png"
        if oq.exists():
            bad.append(f'{oq.name} (old artist card: remove)')
            if not check: oq.unlink()
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
