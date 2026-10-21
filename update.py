#!/usr/bin/env python3
"""Collect Israeli airspace data into web/data.json.

  python3 update.py            # NOTAMs every run; eAIP when a new AIRAC is out; domestic AIP when a new amendment is out
  python3 update.py --force    # rebuild everything

Sources
  NOTAM     brin.iaa.gov.il  (list + per-NOTAM ICAO detail, cached)
  eAIP      e-aip.azurefd.net  (ENR 2.1 TMA, ENR 5.1 P/R/D, AD 2.17 CTR)
  Domestic  gov.il  "פמ"ת מלא" PDF  (P/R/D/LLU tables, VFR points, CVFR + sport-aviation charts)
  Custom    data/custom/*.txt|.air|.geojson|.json|.kml  (your own OpenAir / GeoJSON / KML)
Needs:  pip install pymupdf   (only for the domestic AIP PDF)
"""
import json, os, re, sys, time, traceback, urllib.parse, urllib.request
from sources import notam, eaip, domestic, charts, custom, osm_sites, purpose, reserves
from sources.geometry import UNL

ROOT = os.path.dirname(os.path.abspath(__file__))
D = lambda *p: os.path.join(ROOT, 'data', *p)
OUT = os.path.join(ROOT, 'web', 'data.json')
UA = notam.UA
PDF_BASE = 'https://www.gov.il/BlobFolder/guide/aip/he/'
PDF_NAME = 'פמת מלא {n}-{yy:02d}.pdf'


def log(*a): print(time.strftime('%H:%M:%S'), *a, flush=True)


def jload(p, d=None):
    try: return json.load(open(p, encoding='utf-8'))
    except Exception: return d


def jsave(p, v):
    tmp = p + '.tmp'; json.dump(v, open(tmp, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':')); os.replace(tmp, p)


def _head(url):
    try:
        r = urllib.request.urlopen(urllib.request.Request(url, method='HEAD', headers={'User-Agent': UA}), timeout=30)
        return r.status == 200, r.headers.get('Content-Length')
    except Exception:
        return False, None


def find_domestic_pdf(known):
    """Newest published amendment: try n-yy for this and last year (gov.il does not answer scripts on the index page)."""
    yy = time.gmtime().tm_year % 100
    for y in (yy, yy - 1):
        for n in (6, 5, 4, 3, 2, 1):
            name = PDF_NAME.format(n=n, yy=y)
            url = PDF_BASE + urllib.parse.quote(name)
            if known and known.get('name') == name: return name, url, known.get('size')
            ok, size = _head(url)
            if ok: return name, url, size
    return None, None, None


def step_eaip(state, force):
    cur = eaip.current_airac()
    old = jload(D('cache', 'eaip.json'))
    if old and old.get('airac') == cur and not force:
        return old, f'AIRAC {cur[:10]} (cached)'
    airac, zones = eaip.fetch_aip_zones(log=lambda *a: None)
    v = {'airac': airac, 'z': zones}; jsave(D('cache', 'eaip.json'), v)
    return v, f'AIRAC {airac[:10]}: {len(zones)} zones'


def step_domestic(force):
    meta = jload(D('cache', 'domestic_meta.json'), {}) or {}
    pdf = D('cache', 'domestic_aip.pdf')
    check_due = force or not os.path.exists(pdf) or time.time() - meta.get('checked', 0) > 24 * 3600
    if check_due:
        name, url, size = find_domestic_pdf(meta if os.path.exists(pdf) else None)
        if name and (name != meta.get('name') or not os.path.exists(pdf)):
            log('  downloading domestic AIP', name)
            with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': UA}), timeout=600) as r, open(pdf + '.tmp', 'wb') as f:
                while True:
                    b = r.read(1 << 20)
                    if not b: break
                    f.write(b)
            os.replace(pdf + '.tmp', pdf); meta.update(name=name, size=size, parsed=None)
        meta['checked'] = time.time(); jsave(D('cache', 'domestic_meta.json'), meta)
    derived = jload(D('cache', 'domestic_derived.json'))
    if derived and meta.get('parsed') == meta.get('name') and not force:
        return derived, meta.get('name'), 'cached'
    log('  parsing domestic AIP (tables, VFR points, charts)…')
    derived = {'vfr': eaip.parse_vfr_points(pdf), 'tables': domestic.parse_pdf(pdf), 'charts': charts.extract(pdf, log=log), 'desc': purpose.descriptions(pdf)}
    jsave(D('cache', 'domestic_derived.json'), derived); meta['parsed'] = meta.get('name'); jsave(D('cache', 'domestic_meta.json'), meta)
    return derived, meta.get('name'), 'parsed'


def clean_launch(zs):
    out = []
    for z in zs:
        if z['layer'] != 'launch_site': out.append(z); continue
        if 'נקודות' in z['name']: continue
        p = z['geom']['ring'][0]
        if any(o['layer'] == 'launch_site' and abs(o['geom']['ring'][0][0] - p[0]) < .006 and abs(o['geom']['ring'][0][1] - p[1]) < .006 for o in out): continue
        nm = z['name'] if len(z['name']) > 2 else ''
        z['name'] = f'Launch site · near {nm}' if nm else 'Launch site'
        out.append(z)
    return out


def match_bubble_closures(nz, dz):
    """'ULTRALIGHT BUBBLE … CLSD' NOTAMs only carry a rough Q-line circle. Re-draw them on the actual bubble
    polygons (from the sport chart) whose centre lies inside that circle."""
    from sources.geometry import point_in_ring
    bubbles = [z for z in dz if z['layer'].startswith('sport_bubble')]
    out = []
    for z in nz:
        g = z.get('geom') or {}
        if g.get('approx') and g.get('kind') == 'circle' and 'BUBBLE' in z.get('text', '').upper():
            hits = []
            for b in bubbles:
                r = b['geom']['ring']; c = (sum(p[0] for p in r) / len(r), sum(p[1] for p in r) / len(r))
                if point_in_ring(c[0], c[1], g['ring']): hits.append(b)
            n = len(re.findall(r'\(B[A-Z]{4}\)', z.get('text', '')))
            if n and len(hits) > n:
                cx, cy = g['center']
                hits.sort(key=lambda b: (sum(p[0] for p in b['geom']['ring']) / len(b['geom']['ring']) - cx) ** 2 + (sum(p[1] for p in b['geom']['ring']) / len(b['geom']['ring']) - cy) ** 2)
                hits = hits[:n]
            if 1 <= len(hits) <= 6:
                for i, b in enumerate(hits):
                    q = dict(z); q['geom'] = {'kind': 'polygon', 'ring': [list(p) for p in b['geom']['ring']]}
                    q['floor_ft'], q['floor_ref'] = 0, 'GND'
                    q['name'] = f"{z['id']} · {b['name']}"; q['matched'] = True
                    out.append(q)
                continue
        out.append(z)
    return out


UNSUPPORTED = ('קטום', 'חצי מעגל', 'לאורך הגבול', 'לאורך כביש', 'לאורך קו', 'לאורך תוואי', 'לאורך מסילת')


def reliable(z):
    """Only official, exactly-defined shapes go on the map."""
    g = z.get('geom')
    if not g: return True
    if g.get('approx'):                                   # NOTAM without a published shape (Q-line reference circle)
        z['geom'] = None; z['area_note'] = 'No exact area published in the NOTAM'; return True
    if z.get('source') == 'Domestic AIP' and z['layer'] in ('aip_prohibited', 'aip_restricted', 'aip_danger'):
        raw = z.get('raw', '') + ' ' + z.get('desc_he', '')
        if any(w in raw for w in UNSUPPORTED): return False   # boundary follows a road/border/half-circle we cannot reproduce exactly
        lo, hi = z.get('floor_ft'), z.get('ceil_ft')
        if lo is not None and hi is not None and hi < UNL and hi <= lo and not (hi < 0): return False
    return True


def rnd(z):
    g = z.get('geom')
    if g:
        g['ring'] = [[round(a, 5), round(b, 5)] for a, b in g['ring']]
        if g.get('center'): g['center'] = [round(g['center'][0], 5), round(g['center'][1], 5)]
    return z


def main(force=False):
    t0 = time.time(); src = {}; zones = []
    prev = jload(OUT, {}) or {}
    prev_by = {}
    for z in prev.get('zones', []): prev_by.setdefault(z.get('_src'), []).append(z)

    def keep(name, msg):  # on failure keep last good data of that source
        src[name] = {'ok': False, 'msg': msg, 'updated': (prev.get('sources', {}).get(name) or {}).get('updated')}
        return prev_by.get(name, [])

    # ---- domestic AIP (needed first: waypoints for NOTAM routes)
    waypoints, dom_name, derived = {}, None, None
    try:
        derived, dom_name, how = step_domestic(force)
        waypoints = {k: tuple(v) for k, v in derived['vfr'].items()}
        chart = [z for z in derived['charts'] if z['layer'] != 'launch_site']          # launch sites come from OpenStreetMap
        chart = [z for z in chart if not (z['layer'] == 'aip_ctr' and re.search(r'Ben Gurion|Haifa|Ller', z['name'], re.I) and not z.get('days'))]  # exact eAIP versions exist
        dz = derived['tables'] + chart
        dz += [{'id': k, 'name': k, 'layer': 'vfr_points', 'floor_ft': None, 'ceil_ft': None, 'text': 'VFR reporting point',
                'source': 'Domestic AIP', 'geom': {'kind': 'point', 'ring': [list(v)]}} for k, v in waypoints.items()]
        for z in dz: z['_src'] = 'domestic'
        src['domestic'] = {'ok': True, 'msg': f'{dom_name} ({how}): {len(dz)} items', 'updated': time.time()}
    except ImportError:
        dz = keep('domestic', 'pymupdf not installed:  pip install pymupdf')
    except Exception as e:
        traceback.print_exc(); dz = keep('domestic', f'failed: {e}')

    # ---- eAIP
    try:
        ev, msg = step_eaip(None, force)
        ez = ev['z']; airac = ev['airac']
        for z in ez: z['_src'] = 'eaip'
        src['eaip'] = {'ok': True, 'msg': msg, 'updated': time.time()}
    except Exception as e:
        traceback.print_exc(); ez = keep('eaip', f'failed: {e}'); airac = prev.get('airac')

    desc = (derived or {}).get('desc') or {}
    for z in ez + dz:
        if z['layer'] in purpose.TYPE_DEFAULT or z['layer'] in ('aip_ctr', 'aip_atz', 'aip_tma'):
            purpose.annotate(z, desc.get(z['name'].split()[0]))
    have = {z['name'].split()[0] for z in ez}
    dz = [z for z in dz if not (z['layer'] in ('aip_prohibited', 'aip_restricted', 'aip_danger') and z['name'].split()[0] in have)]

    # ---- NOTAMs
    try:
        nz = notam.fetch(D('cache', 'notam'), waypoints, log=log)
        for z in nz: z['_src'] = 'notam'
        src['notam'] = {'ok': True, 'msg': f'{len(nz)} NOTAMs', 'updated': time.time()}
    except Exception as e:
        traceback.print_exc(); nz = keep('notam', f'failed: {e}')


    # ---- paragliding sites (OpenStreetMap)
    try:
        els, how = osm_sites.fetch(D('cache', 'osm_sites.json'), log=log)
        oz = osm_sites.to_zones(els)
        for z in oz: z['_src'] = 'osm'
        src['osm'] = {'ok': True, 'msg': f'{sum(1 for z in oz if z["layer"] == "launch_site")} takeoffs, {sum(1 for z in oz if z["layer"] == "landing_site")} landings ({how})', 'updated': time.time()}
    except Exception as e:
        traceback.print_exc(); oz = keep('osm', f'failed: {e}')
    dz = dz + oz

    # ---- nature reserves (official AIP list + OSM outlines)
    try:
        rz = reserves.build(D('cache', 'domestic_aip.pdf'), D('cache', 'osm_reserves.json'), log=log)
        for z in rz: z['_src'] = 'reserves'
        src['reserves'] = {'ok': True, 'msg': f'{len({z["id"] for z in rz})} reserves / parks / nesting sites with an outline', 'updated': time.time()}
    except Exception as e:
        traceback.print_exc(); rz = keep('reserves', f'failed: {e}')
    dz = dz + rz

    # ---- custom files
    cz = custom.load_dir(D('custom'))
    for z in cz: z['_src'] = 'custom'
    if cz: src['custom'] = {'ok': True, 'msg': f'{len(cz)} zones from data/custom', 'updated': time.time()}

    allz = ez + dz + nz + cz
    zones = [rnd(z) for z in allz if reliable(z)]
    dropped = len(allz) - len(zones)
    if dropped: log(f'  left out {dropped} shapes that could not be reproduced exactly')
    out = {'generated': int(time.time()), 'airac': airac, 'domestic_aip': dom_name, 'sources': src, 'zones': zones}
    os.makedirs(os.path.dirname(OUT), exist_ok=True); jsave(OUT, out)
    log(f'wrote {OUT}: {len(zones)} zones in {time.time() - t0:.1f}s', {k: v["msg"] for k, v in src.items()})
    return out


if __name__ == '__main__':
    main(force='--force' in sys.argv)
