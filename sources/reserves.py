"""Nature reserves, national parks and nesting sites with a flight restriction.

The list and the height limit are official (domestic AIP chapter A-17, appendix E: code, name, type, height AGL).
The AIP has no boundaries, so outlines come from OpenStreetMap (© OpenStreetMap contributors, ODbL) and only areas
whose name matches an entry in the AIP list are kept."""
import json, re, time
from .osm_sites import overpass

QUERY = ('[out:json][timeout:150];(way["leisure"="nature_reserve"](29.4,34.2,33.4,35.95);relation["leisure"="nature_reserve"](29.4,34.2,33.4,35.95);'
         'way["boundary"="national_park"](29.4,34.2,33.4,35.95);relation["boundary"="national_park"](29.4,34.2,33.4,35.95);'
         'way["boundary"="protected_area"](29.4,34.2,33.4,35.95);relation["boundary"="protected_area"](29.4,34.2,33.4,35.95););out geom qt;')
PREFIX = re.compile(r'^(שמורת טבע|שמורת|גן לאומי|גן|אתר לאומי|אתר|פארק|יער)\s+')
FINAL = str.maketrans('םןץףך', 'מנצפכ')
TYPES = ['אתרי קינון של מינים בסכנת הכחדה ושמורה', 'אתרי קינון של מינים בסכנת הכחדה', 'שמורת טבע', 'גן לאומי', 'אזור קינון']
TYPE_EN = {'שמורת טבע': 'Nature reserve', 'גן לאומי': 'National park', 'אתרי קינון': 'Nesting site of endangered species', 'אזור קינון': 'Nesting area'}


def norm(name):
    n = PREFIX.sub('', (name or '').strip())
    return re.sub(r'[^א-ת]', '', n.translate(FINAL))


def appendix_e(pdf_path):
    import fitz
    d = fitz.open(pdf_path)
    pages = [i for i, p in enumerate(d) if i < 140 and 'רשימת גנים לאומיים' in p.get_text() and re.search(r'LLP\d{4}', p.get_text())]
    if not pages: return []
    t = ''
    for i in range(pages[0], min(pages[0] + 25, len(d))):
        pt = d[i].get_text()
        if i > pages[0] and 'LLP' not in pt: break
        t += ' ' + pt
    t = re.sub(r'\s+', ' ', t)
    t = re.sub(r'פמ"ת פנים ארצי|רשות התעופה האזרחית|א-\s*\d+\s*-\s*\d+|עדכון\s*\d+/\d+|קוד שם אזור סוג אזור גובה מירבי מעפ"ש', ' ', t)
    t = re.sub(r"\b\d{1,2}\s*'?\s*(?:ינו|פבר|מרץ|אפר|מאי|יוני|יולי|אוג|ספט|אוק|נוב|דצמ)\S*\s*\d{4}|\b\d{1,2}\s+'?(?:ינו|פבר|מרץ|אפר|מאי|יוני|יולי|אוג|ספט|אוק|נוב|דצמ)\S*", ' ', t)
    out = []
    for m in re.finditer(r'(LLP\d{4})\s+(.*?)\s+(\d{3,4})(?=\s+LLP\d{4}|\s*$)', t):
        code, body, h = m.group(1), m.group(2).strip(), int(m.group(3))
        typ = next((x for x in TYPES if x in body), '')
        name = body.split(typ)[0].strip(' -–') if typ else body
        season = re.search(r'([א-ת]+\s+עד\s+[א-ת]+)', body)
        out.append({'code': code, 'name': name, 'type': typ or body, 'height_agl': h, 'season': season.group(1) if season else ''})
    return out


def _rings(el):
    if el['type'] == 'way':
        g = [(p['lat'], p['lon']) for p in el.get('geometry', [])]
        return [g] if len(g) >= 4 else []
    segs = [[(p['lat'], p['lon']) for p in m.get('geometry', [])] for m in el.get('members', []) if m.get('role') in ('outer', '') and m.get('geometry')]
    rings = []
    while segs:
        ring = segs.pop(0)
        changed = True
        while changed and ring[0] != ring[-1]:
            changed = False
            for i, s in enumerate(segs):
                if s[0] == ring[-1]: ring += s[1:]
                elif s[-1] == ring[-1]: ring += s[::-1][1:]
                elif s[-1] == ring[0]: ring = s + ring[1:]
                elif s[0] == ring[0]: ring = s[::-1] + ring[1:]
                else: continue
                segs.pop(i); changed = True; break
        if len(ring) >= 4 and ring[0] == ring[-1]: rings.append(ring)
    return rings


def _simplify(r, max_pts=70):
    step = max(1, len(r) // max_pts)
    s = r[::step]
    if s[-1] != r[-1]: s.append(r[-1])
    return [[round(a, 5), round(b, 5)] for a, b in s]


def build(pdf_path, cache_path, log=print, max_age_days=30):
    listing = appendix_e(pdf_path)
    try: cache = json.load(open(cache_path))
    except Exception: cache = None
    if not cache or time.time() - cache.get('t', 0) > max_age_days * 86400:
        try:
            els = overpass(QUERY, log=log); cache = {'t': time.time(), 'els': els}; json.dump(cache, open(cache_path, 'w'))
        except Exception as e:
            if not cache: raise
            log(f'  reserves: using cached outlines ({e})')
    by = {}
    for e in cache['els']:
        t = e.get('tags', {})
        for nm in {t.get('name:he'), t.get('name'), t.get('official_name:he'), t.get('alt_name:he')}:
            if nm and re.search(r'[א-ת]', nm): by.setdefault(norm(nm), []).append(e)
    zones, matched = [], 0
    for it in listing:
        els = by.get(norm(it['name']))
        if not els: continue
        matched += 1
        typ_en = next((v for k, v in TYPE_EN.items() if k in it['type']), 'Protected area')
        for e in els:
            for ring in _rings(e):
                zones.append({'id': it['code'], 'name': f"{it['code']} {it['name']}", 'layer': 'nature_reserve', 'floor_ft': 0, 'floor_ref': 'GND',
                              'ceil_ft': it['height_agl'], 'ceil_ref': 'AGL', 'days': None,
                              'text': f"{typ_en}. No flight below {it['height_agl']} ft above ground" + (f" ({it['season']})" if it['season'] else '') + '.',
                              'source': 'Domestic AIP appendix E + OpenStreetMap outline', 'osm_id': f"{e['type']}/{e['id']}",
                              'raw': f"{it['code']}  {it['name']}  |  {it['type']}  |  {it['height_agl']} ft AGL", 'geom': {'kind': 'polygon', 'ring': _simplify(ring)}})
    log(f'  nature reserves: {len(listing)} in the AIP list, {matched} matched to an outline')
    return zones
