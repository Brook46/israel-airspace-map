"""Paragliding / hang-gliding sites from OpenStreetMap (© OpenStreetMap contributors, ODbL) via the Overpass API.
Takeoffs carry their usable wind directions (tag `direction`, e.g. 'WSW-NW', or `free_flying:site_orientation`)."""
import json, os, shutil, subprocess, time, urllib.parse, urllib.request

ENDPOINTS = ['https://overpass-api.de/api/interpreter', 'https://overpass.kumi.systems/api/interpreter']
QUERY = '[out:json][timeout:60];(nwr["free_flying:site"](29.4,34.2,33.4,35.95);nwr["sport"="free_flying"](29.4,34.2,33.4,35.95););out center tags;'
UA = 'IsraelAirspaceMap/1.0 (personal pilot tool)'
COMPASS = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW']


def _deg(tok):
    tok = tok.strip().upper()
    if tok in COMPASS: return COMPASS.index(tok) * 22.5
    try: return float(tok) % 360
    except ValueError: return None


def wind_sectors(tags):
    """-> list of [from_deg, to_deg] clockwise ranges of suitable wind directions."""
    out = []
    d = tags.get('direction') or ''
    for part in d.replace(',', ';').split(';'):
        part = part.strip()
        if not part: continue
        if '-' in part:
            a, b = part.split('-', 1); a, b = _deg(a), _deg(b)
            if a is not None and b is not None: out.append([a, b])
        else:
            a = _deg(part)
            if a is not None: out.append([(a - 22.5) % 360, (a + 22.5) % 360])
    if not out:
        dirs = [_deg(t) for t in (tags.get('free_flying:site_orientation') or '').replace(',', ';').split(';') if t.strip()]
        out = [[(a - 22.5) % 360, (a + 22.5) % 360] for a in dirs if a is not None]
    return out


def fetch(cache_path, max_age_days=7, log=print):
    cache = None
    try: cache = json.load(open(cache_path))
    except Exception: pass
    if cache and time.time() - cache.get('t', 0) < max_age_days * 86400: return cache['els'], 'cached'
    for ep in ENDPOINTS:
        try:
            req = urllib.request.Request(ep, data=urllib.parse.urlencode({'data': QUERY}).encode(), headers={'User-Agent': UA})
            els = json.loads(urllib.request.urlopen(req, timeout=90).read())['elements']
            json.dump({'t': time.time(), 'els': els}, open(cache_path, 'w')); return els, 'fresh'
        except Exception as e:
            log(f'  overpass {ep}: {e}')
            if shutil.which('curl'):   # old Python TLS stacks fail on some servers; curl usually works
                try:
                    out = subprocess.run(['curl', '-s', '-m', '90', '-A', UA, '--data-urlencode', 'data=' + QUERY, ep], capture_output=True, timeout=120).stdout
                    els = json.loads(out)['elements']
                    json.dump({'t': time.time(), 'els': els}, open(cache_path, 'w')); return els, 'fresh'
                except Exception as e2:
                    log(f'  overpass via curl {ep}: {e2}')
    if cache: return cache['els'], 'stale cache'
    raise RuntimeError('Overpass unavailable')


def to_zones(els):
    zs = []
    for e in els:
        t = e.get('tags', {})
        kind = t.get('free_flying:site') or ('takeoff' if t.get('free_flying:takeoff') == 'yes' else None)
        layer = {'takeoff': 'launch_site', 'landing': 'landing_site', 'training': 'training_site'}.get(kind)
        if not layer: continue
        lat = e.get('lat') or e.get('center', {}).get('lat'); lon = e.get('lon') or e.get('center', {}).get('lon')
        if lat is None: continue
        name = t.get('name:en') or t.get('name') or {'launch_site': 'Takeoff', 'landing_site': 'Landing', 'training_site': 'Ground handling'}[layer]
        he = t.get('name:he') or t.get('alt_name') or ''
        notes = []
        if t.get('direction'): notes.append(f"Wind {t['direction']}")
        if t.get('free_flying:ridge') == 'yes': notes.append('ridge soaring')
        if t.get('free_flying:hanggliding') == 'yes': notes.append('hang gliders too')
        if t.get('surface'): notes.append(f"surface: {t['surface']}")
        if t.get('free_flying:official') == 'yes': notes.append('official site')
        if t.get('description'): notes.append(t['description'])
        z = {'id': f"osm{e['type'][0]}{e['id']}", 'name': name + (f' · {he}' if he and he not in name else ''), 'layer': layer,
             'floor_ft': None, 'ceil_ft': None, 'text': '; '.join(notes), 'source': 'OpenStreetMap',
             'geom': {'kind': 'point', 'ring': [[round(lat, 6), round(lon, 6)]]}}
        if layer == 'launch_site':
            z['wind'] = wind_sectors(t); z['wind_text'] = t.get('direction') or t.get('free_flying:site_orientation') or ''
            if t.get('ele'): z['elev_m'] = t['ele']
        zs.append(z)
    return zs
