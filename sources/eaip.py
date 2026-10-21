"""Scrape Israel's eAIP (e-aip.azurefd.net) for P/R/D areas, TMAs and CTRs -> zone dicts.
Also reads VFR reporting points from the domestic Hebrew AIP PDF (needs optional `pymupdf`)."""
import html, math, os, re, urllib.request
from .geometry import circle_ring, parse_alt, NM

ROOT = 'https://e-aip.azurefd.net/'
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124 Safari/537.36'
PT = r'(\d{4,6}(?:\.\d+)?)\s*([NS])\s*(\d{5,7}(?:\.\d+)?)\s*([EW])'
PT2 = r"(\d+)\s*°\s*(\d+)\s*'\s*(?:(\d+(?:\.\d+)?)\s*\"?)?\s*([NS])\s*(\d+)\s*°\s*(\d+)\s*'\s*(?:(\d+(?:\.\d+)?)\s*\"?)?\s*([EW])"


def get(url, timeout=60):
    return urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': UA}), timeout=timeout).read()


def current_airac():
    """Newest AIRAC folder whose date is <= today (the page lists current + upcoming)."""
    import datetime
    page = get(ROOT).decode('utf-8', 'replace')
    ds = sorted(set(re.findall(r'(\d{4}-\d{2}-\d{2})-AIRAC', page)))
    today = datetime.date.today().isoformat()
    ok = [d for d in ds if d <= today]
    return (ok[-1] if ok else ds[0]) + '-AIRAC'


def lines_of(url):
    h = get(url).decode('utf-8', 'replace')
    h = re.sub(r'<(script|style).*?</\1>', '', h, flags=re.S)
    h = html.unescape(re.sub(r'<[^>]+>', '\n', h)).replace('\xa0', ' ')
    return [re.sub(r'\s+', ' ', l).strip() for l in h.split('\n') if l.strip()]


def _dec(v, deg):
    ip, _, fp = v.partition('.')
    d = int(ip[:deg]); rest = ip[deg:]
    m = int(rest[:2]) if len(rest) >= 2 else 0
    s = float(rest[2:] + ('.' + fp if fp else '')) if len(rest) > 2 else 0.0
    return d + m / 60 + s / 3600


def _pt(m):
    lat = _dec(m.group(1), 2) * (1 if m.group(2) == 'N' else -1)
    lon = _dec(m.group(3), 2 if len(m.group(3).split('.')[0]) == 6 else 3) * (1 if m.group(4) == 'E' else -1)
    return lat, lon


def _pt2(m):
    g = m.groups()
    lat = int(g[0]) + int(g[1]) / 60 + float(g[2] or 0) / 3600
    lon = int(g[4]) + int(g[5]) / 60 + float(g[6] or 0) / 3600
    return lat * (1 if g[3] == 'N' else -1), lon * (1 if g[7] == 'E' else -1)


def find_pts(s):
    out = [(m.start(), _pt(m)) for m in re.finditer(PT, s)]
    out += [(m.start(), _pt2(m)) for m in re.finditer(PT2, s)]
    return [p for _, p in sorted(out)]


def _bearing(c, p):
    return math.degrees(math.atan2((p[1] - c[1]) * math.cos(math.radians(c[0])), p[0] - c[0])) % 360


def _arc(c, r_m, p1, p2, cw):
    a1, a2 = _bearing(c, p1), _bearing(c, p2)
    if cw:
        if a2 <= a1: a2 += 360
    else:
        if a2 >= a1: a2 -= 360
    n = max(3, int(abs(a2 - a1) / 4))
    pts = []
    for i in range(1, n):
        b = math.radians(a1 + (a2 - a1) * i / n)
        pts.append((c[0] + r_m * math.cos(b) / 111320, c[1] + r_m * math.sin(b) / (111320 * math.cos(math.radians(c[0])))))
    return pts


def parse_boundary(s):
    """Boundary text with optional arcs/circles -> geom dict or None."""
    s = s.replace('–', '-')
    m = re.search(r'circle radius\s*([\d.]+)\s*(NM|KM)\s*cent\w*\s*on\s*(.*)', s, re.I)
    if m:
        c = find_pts(m.group(3))
        if c:
            r = float(m.group(1)) * (NM if m.group(2).upper() == 'NM' else 1000)
            return {'kind': 'circle', 'center': c[0], 'radius_m': r, 'ring': circle_ring(c[0][0], c[0][1], r)}
    ring, toks = [], re.split(r'\s+-\s+(?=\d)', s)
    arcs = []  # (index of start point in ring, center, r_m, cw)
    for t in toks:
        pts = find_pts(t)
        if not pts: continue
        ring.append(pts[0])
        am = re.search(r'(counter-?clockwise|clockwise)\s*arc\s*radius\s*([\d.]+)\s*(NM|KM)\s*cent\w*\s*on', t, re.I)
        if am and len(pts) >= 2:
            arcs.append((len(ring) - 1, pts[1], float(am.group(2)) * (NM if am.group(3).upper() == 'NM' else 1000), 'counter' not in am.group(1).lower()))
    if len(ring) < 3: return None
    closed = ring + [ring[0]]
    out, ai = [], {a[0]: a for a in arcs}
    for i, p in enumerate(ring):
        out.append(p)
        if i in ai:
            _, c, r, cw = ai[i]
            out += _arc(c, r, p, closed[i + 1], cw)
    if out[0] != out[-1]: out.append(out[0])
    return {'kind': 'polygon', 'ring': out}


def _alt(s):
    s = s.upper()
    m = re.search(r'FL\s*\d+|\d[\d ]*\s*FT|GND|SFC|UNL', s)
    if m: s = m.group(0)
    s = s.replace('ALT', '').replace('MSL', '').strip()
    s = s.replace(' ', '') if re.match(r'\d', s) else s
    s = re.sub(r'(\d)FT', r'\1 FT', s)
    return parse_alt(s)[0]


def _zone(name, geom, floor, ceil, layer, text, src):
    return {'id': name, 'name': name, 'location': '', 'text': text, 'layer': layer, 'floor_ft': floor, 'ceil_ft': ceil,
            'days': None, 'geom': geom, 'source': src}


def parse_enr51(L, src):
    zones, i = [], 0
    while i < len(L):
        m = re.match(r'^(LL([PRD])\d+\w*)$', L[i])
        if m and i + 4 < len(L):
            name, kind = m.group(1), m.group(2)
            j = i + 1; geo = []
            while j < len(L) and not re.search(r'\bFT\b|^FL\s*\d', L[j]) and not re.match(r'^LL[PRD]\d', L[j]):
                geo.append(L[j]); j += 1
            if j < len(L) and not re.match(r'^LL[PRD]\d', L[j]):
                up = L[j]; lo = ''; k = j + 1
                mm = re.match(r'^(.*?)\s*/\s*(.+)$', up)
                if mm and mm.group(2).strip():
                    up, lo = mm.group(1), mm.group(2)
                elif mm:
                    up = mm.group(1)
                if not lo and k < len(L) and L[k] == '/':
                    lo = L[k + 1] if k + 1 < len(L) else ''; k += 2
                elif not lo and k < len(L) and L[k].startswith('/') and len(L[k]) > 1:
                    lo = L[k][1:]; k += 1
                rem = []
                while k < len(L) and not re.match(r'^LL[PRD]\d', L[k]) and not re.match(r'^\d+\.$', L[k]) and len(rem) < 6:
                    rem.append(L[k]); k += 1
                g = parse_boundary(' '.join(geo))
                if g:
                    layer = {'P': 'aip_prohibited', 'R': 'aip_restricted', 'D': 'aip_danger'}[kind]
                    zones.append(_zone(name, g, _alt(lo) if lo else 0, _alt(up), layer, ' | '.join(rem), src))
                    zones[-1]['raw'] = '\n'.join([name, ' '.join(geo), f'Upper: {up}', f'Lower: {lo}'] + rem)
                i = k; continue
        i += 1
    return zones


def parse_ctr(L, icao, src):
    zones = []
    for i, l in enumerate(L):
        if l == 'Designation and lateral limits' and i + 1 < len(L) and 'AD 2.17' in ' '.join(L[max(0, i - 4):i]):
            j = i + 1; geo = []
            while j < len(L) and not L[j].startswith('Vertical limits'):
                geo.append(L[j]); j += 1
            name = geo[0] if geo and geo[0].endswith('CTR') else f'{icao} CTR'
            vl = L[j + 1] if j + 1 < len(L) else ''
            nums = re.findall(r'(FL\s*\d+|\d[\d ]*\s*FT)', vl)
            ceil = _alt(nums[0]) if nums else None
            g = parse_boundary(' - '.join(re.sub(r'(\d{6}[NS])\s+(\d{6,7}[EW])', r'\1 \2', x) for x in geo))
            if g:
                zones.append(_zone(name, g, 0, ceil, 'aip_ctr', f'{icao} CTR: {vl}', src))
    return zones


def parse_tma(L, src):
    zones, name = [], None
    i = 0
    while i < len(L):
        l = L[i]
        if re.search(r'\b(TMA|CTA)\b', l) and 'FIR' not in l and not re.search(r'TMA/APP|control|ENR|TMA\s*\d', l, re.I) and len(l) < 45 and not find_pts(l):
            name = l
        if find_pts(l) and name:
            label = ''
            if i > 0 and re.search(r'Sector|Area|:$', L[i - 1]): label = L[i - 1].rstrip(':')
            geo = []; j = i
            while j < len(L) and (find_pts(L[j]) or L[j] in ('-', '.')) and len(geo) < 40:
                geo.append(L[j]); j += 1
            vl = ''
            for k in range(j, min(j + 3, len(L))):
                if re.search(r'\bFT\b|FL\s*\d|SFC|GND', L[k], re.I): vl = L[k]; break
            pts = find_pts(' - '.join(geo))
            lo, _, up = re.sub(r'\s+(?=\d{3}\b)', '', vl).partition(' to ')
            if lo and not re.search(r'[A-Za-z]', lo) and 'FT' in up: lo += ' FT'
            if len(pts) >= 3:
                ring = pts + ([pts[0]] if pts[0] != pts[-1] else [])
                zones.append(_zone((name + (' – ' + label if label else '')).strip(), {'kind': 'polygon', 'ring': ring},
                                   _alt(lo) if lo else None, _alt(up) if up else None, 'aip_tma', vl, src))
            i = j; continue
        i += 1
    return zones


def fetch_aip_zones(log=print):
    airac = current_airac(); base = f'{ROOT}{airac}/html/eAIP/'; src = f'eAIP {airac[:10]}'
    zones = []
    for name, fn in [('ENR-5.1', lambda L: parse_enr51(L, src)), ('ENR-2.1', lambda L: parse_tma(L, src))]:
        try:
            zones += fn(lines_of(f'{base}LL-{name}-en-GB.html')); log(f'{name}: {len(zones)} total')
        except Exception as e: log(f'{name} failed: {e}')
    for icao in ('LLBG', 'LLER', 'LLHA', 'LLOV', 'LLET', 'LLBS', 'LLIB', 'LLHZ'):
        try:
            zones += parse_ctr(lines_of(f'{base}LL-AD-2.{icao}-en-GB.html'), icao, src)
        except Exception:
            pass
    return airac, zones


# ---------- VFR reporting points from the domestic (Hebrew) AIP PDF ----------
PDF_URL = 'https://www.gov.il/BlobFolder/guide/aip/he/%D7%A4%D7%9E%D7%AA%20%D7%9E%D7%9C%D7%90%201-26.pdf'


def parse_vfr_points(pdf_path):
    import fitz
    pts = {}
    pat = re.compile(r'(\d+)°\s*(\d+)\'\s*(\d+)"\s*E\s*(\d+)°\s*(\d+)\'\s*(\d+)"\s*N\s*([A-Z]{5}|LL[A-Z]{2})\b')
    d = fitz.open(pdf_path)
    for page in d:
        t = page.get_text()
        if 'Letter' not in t or 'East' not in t: continue
        for m in pat.finditer(t.replace('\n', ' ')):
            g = [int(x) for x in m.groups()[:6]]
            pts[m.group(7)] = (g[3] + g[4] / 60 + g[5] / 3600, g[0] + g[1] / 60 + g[2] / 3600)
    return pts
