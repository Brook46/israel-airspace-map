"""Import static airspace (CTR/TMA/R/D/P...) from OpenAir, GeoJSON or KML files in data/aip/."""
import json, math, os, re, glob
import xml.etree.ElementTree as ET
from .geometry import circle_ring, NM

AIP_LABELS = {'aip_ctr': 'AIP – CTR', 'aip_tma': 'AIP – TMA / CTA', 'aip_prohibited': 'AIP – Prohibited',
              'aip_restricted': 'AIP – Restricted', 'aip_danger': 'AIP – Danger', 'aip_other': 'AIP – Other', 'aip_uas': 'AIP – No-fly (LLU, drones/sport)', 'aip_obst': 'AIP – Fixed obstacles / balloons'}


def layer_for(name, cls=''):
    n = (name or '').upper(); c = (cls or '').upper()
    if re.search(r'\bCTR\b|\bATZ\b', n) or c == 'CTR': return 'aip_ctr'
    if re.search(r'\bTMA\b|\bCTA\b|\bTCA\b', n) or c in ('TMA', 'CTA'): return 'aip_tma'
    if re.search(r'\bLLP\d*|PROHIB', n) or c == 'P': return 'aip_prohibited'
    if re.search(r'\bLLR\d*|RESTRICT', n) or c in ('R', 'Q'): return 'aip_restricted'
    if re.search(r'\bLLD\d*|DANGER', n) or c == 'D': return 'aip_danger'
    return 'aip_other'


def _alt(s):
    from .geometry import parse_alt
    s = (s or '').strip().replace('AGL', ' AGL').replace('AMSL', ' AMSL').replace('MSL', ' MSL')
    return parse_alt(s.replace('ft', 'FT'))[0]


def _ll(tok):
    m = re.match(r'(\d+):(\d+)(?::(\d+(?:\.\d+)?))?\s*([NSEW])', tok.strip())
    v = int(m.group(1)) + int(m.group(2)) / 60 + (float(m.group(3)) / 3600 if m.group(3) else 0)
    return v * (-1 if m.group(4) in 'SW' else 1)


def _pt(s):
    a, b = re.split(r'\s+(?=\d+:\d+(?::[\d.]+)?\s*[EW])', s.strip(), maxsplit=1)
    return _ll(a), _ll(b)


def parse_openair(text, src):
    zones, cur, center = [], None, None

    def flush():
        nonlocal cur
        if cur and cur.get('pts'):
            ring = cur['pts']
            if ring[0] != ring[-1]: ring = ring + [ring[0]]
            zones.append(dict(id=cur['name'], name=cur['name'], location='', text=cur.get('txt', ''), layer=layer_for(cur['name'], cur.get('cls')),
                              floor_ft=cur.get('lo'), ceil_ft=cur.get('hi'), geom=cur['geom'] if 'geom' in cur else {'kind': 'polygon', 'ring': ring}, source=src))
        cur = None
    for raw in text.splitlines():
        ln = raw.split('*')[0].strip()
        if not ln: continue
        k, _, v = ln.partition(' '); k = k.upper(); v = v.strip()
        try:
            if k == 'AC': flush(); cur = {'cls': v, 'pts': []}
            elif cur is None: continue
            elif k == 'AN': cur['name'] = v
            elif k == 'AL': cur['lo'] = _alt(v)
            elif k == 'AH': cur['hi'] = _alt(v)
            elif k == 'V' and v.upper().startswith('X='): center = _pt(v[2:])
            elif k == 'DP': cur['pts'].append(_pt(v))
            elif k == 'DC':
                r = float(v) * NM; la, lo = center
                ring = circle_ring(la, lo, r); cur['pts'] = ring
                cur['geom'] = {'kind': 'circle', 'center': (la, lo), 'radius_m': r, 'ring': ring}
            elif k in ('DA', 'DB') and center:
                la, lo = center
                if k == 'DA':
                    r, a1, a2 = [float(x) for x in v.split(',')]; p1 = p2 = None
                else:
                    p1s, p2s = v.split(','); p1, p2 = _pt(p1s), _pt(p2s)
                    def brg(p): return math.degrees(math.atan2((p[1]-lo)*math.cos(math.radians(la)), p[0]-la)) % 360
                    a1, a2 = brg(p1), brg(p2)
                    r = math.hypot((p1[0]-la)*111320, (p1[1]-lo)*111320*math.cos(math.radians(la))) / NM
                if a2 < a1: a2 += 360
                n = max(2, int((a2 - a1) / 6))
                for i in range(n + 1):
                    b = math.radians(a1 + (a2 - a1) * i / n)
                    cur['pts'].append((la + r*NM*math.cos(b)/111320, lo + r*NM*math.sin(b)/(111320*math.cos(math.radians(la)))))
        except Exception:
            continue
    flush()
    return zones


def parse_geojson(text, src):
    zs = []
    for f in json.loads(text).get('features', []):
        g, p = f.get('geometry') or {}, f.get('properties') or {}
        polys = g['coordinates'] if g.get('type') == 'MultiPolygon' else [g['coordinates']] if g.get('type') == 'Polygon' else []
        name = p.get('name') or p.get('NAME') or p.get('Name') or 'zone'
        for poly in polys:
            ring = [(c[1], c[0]) for c in poly[0]]
            zs.append(dict(id=name, name=name, location='', text=str(p.get('description', '')), layer=layer_for(name, str(p.get('class', p.get('type', '')))),
                           floor_ft=p.get('floor_ft'), ceil_ft=p.get('ceiling_ft'), geom={'kind': 'polygon', 'ring': ring}, source=src))
    return zs


def parse_kml(text, src):
    text = re.sub(r'\sxmlns="[^"]+"', '', text, count=1)
    zs = []
    for pm in ET.fromstring(text).iter('Placemark'):
        name = (pm.findtext('name') or 'zone').strip()
        for c in pm.iter('coordinates'):
            ring = []
            for t in c.text.split():
                p = t.split(',')
                ring.append((float(p[1]), float(p[0])))
            if len(ring) >= 3:
                zs.append(dict(id=name, name=name, location='', text=(pm.findtext('description') or ''), layer=layer_for(name),
                               floor_ft=None, ceil_ft=None, geom={'kind': 'polygon', 'ring': ring}, source=src))
    return zs


def load_dir(d):
    zones = []
    for fp in sorted(glob.glob(os.path.join(d, '*'))):
        ext = os.path.splitext(fp)[1].lower(); src = 'AIP: ' + os.path.basename(fp)
        try:
            t = open(fp, encoding='utf-8', errors='replace').read()
            if ext in ('.txt', '.air', '.openair'): zones += parse_openair(t, src)
            elif ext in ('.geojson', '.json'): zones += parse_geojson(t, src)
            elif ext == '.kml': zones += parse_kml(t, src)
        except Exception as e:
            print('AIP import failed', fp, e)
    return zones
