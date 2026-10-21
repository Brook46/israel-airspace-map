"""Vector extraction from the domestic AIP charts (Hebrew PDF), georeferenced from each sheet's printed graticule.

* CVFR low-level route chart (B-03 appendix A): civil CVFR routes, military routes, approval-only legs, route altitudes.
* Sport-aviation low-altitude chart (B-08 appendix A): midweek / weekend / special routes, every-day and weekend
  bubbles, paraglider & hang-glider launch points.
Accuracy is limited by the chart (1:250,000) and the affine georeference: typically 100-400 m.
"""
import math, re
from .geometry import UNL

MID, END = [0, 1, 2, 3, 4], [5, 6]           # Sun..Thu, Fri..Sat  (JS getDay numbering: 0 = Sunday)
LABELS = {
    'cvfr_route': 'CVFR routes (civil)', 'cvfr_mil': 'Military low-level routes',
    'sport_route_mid': 'Sport routes · midweek', 'sport_route_end': 'Sport routes · weekend', 'sport_route_special': 'Sport routes · special',
    'aip_atz': 'Aerodrome traffic zones (ATZ)', 'sport_bubble_all': 'Sport bubbles · every day', 'sport_bubble_end': 'Sport bubbles · weekend', 'launch_site': 'Paraglider / hang-glider launch sites',
}
LAB = re.compile(r"(\d+)°\s*(\d+)'\s*([EN])")
HEB = re.compile(r'[֐-׿]')


def _near(c, t, tol=.03):
    return c is not None and all(abs(a - b) < tol for a, b in zip(c, t))


def _lsq(pts):
    """v = a + b*x + c*y  (normal equations, 3x3)."""
    S = lambda f: sum(f(p) for p in pts)
    A = [[len(pts), S(lambda p: p[0]), S(lambda p: p[1])], [S(lambda p: p[0]), S(lambda p: p[0] ** 2), S(lambda p: p[0] * p[1])],
         [S(lambda p: p[1]), S(lambda p: p[0] * p[1]), S(lambda p: p[1] ** 2)]]
    B = [S(lambda p: p[2]), S(lambda p: p[0] * p[2]), S(lambda p: p[1] * p[2])]
    for i in range(3):
        k = max(range(i, 3), key=lambda r: abs(A[r][i])); A[i], A[k] = A[k], A[i]; B[i], B[k] = B[k], B[i]
        for r in range(i + 1, 3):
            f = A[r][i] / A[i][i]; B[r] -= f * B[i]
            for c in range(i, 3): A[r][c] -= f * A[i][c]
    x = [0.0] * 3
    for i in (2, 1, 0): x[i] = (B[i] - sum(A[i][c] * x[c] for c in range(i + 1, 3))) / A[i][i]
    return x


def _spans(page):
    out = []
    for b in page.get_text('dict')['blocks']:
        for l in b.get('lines', []):
            for s in l['spans']:
                t = re.sub(r'[\x00-\x1f]', '', s['text']).strip()
                if t: x0, y0, x1, y1 = s['bbox']; out.append(((x0 + x1) / 2, (y0 + y1) / 2, t, s['bbox']))
    return out


def _lines(page):
    out = []
    for b in page.get_text('dict')['blocks']:
        for l in b.get('lines', []):
            t = re.sub(r'[\x00-\x1f]', '', ' '.join(s['text'] for s in l['spans'])).strip()
            if t: x0, y0, x1, y1 = l['bbox']; out.append(((x0 + x1) / 2, (y0 + y1) / 2, t, l['bbox']))
    return out


def _ctr_alt(txt):
    m = re.search(r'(GND|SFC|MSL|\d[\d ]*)\s*(?:/\s*MSL|/\s*GND)?\s*[-–]\s*(\d[\d ]*\d)', txt)
    if not m: return None, None
    lo = 0 if not re.match(r'\d', m.group(1)) else int(m.group(1).replace(' ', ''))
    return lo, int(m.group(2).replace(' ', ''))


def match_ctrs(cands, lines, f, src):
    """cands: [(pts, dashed)] closed outlines in page coords; lines: text lines. -> CTR/ATZ zones."""
    labels = [(x, y, t, bb) for x, y, t, bb in lines if re.match(r'(CTR|ATZ)\b', t)]
    pairs = []
    for li, (x, y, t, bb) in enumerate(labels):
        for k, (pts, dashed) in enumerate(cands):
            xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
            if not (min(xs) - 60 <= x <= max(xs) + 60 and min(ys) - 60 <= y <= max(ys) + 60): continue
            d = 0 if _inside(x, y, pts) else min(math.hypot(px - x, py - y) for px, py in pts[:: max(1, len(pts) // 80)])
            if d < 90:
                area = (max(xs) - min(xs)) * (max(ys) - min(ys))
                pairs.append((d, area, li, k))
    pairs.sort()   # closest first; for labels inside several outlines prefer the smallest
    taken_l, taken_k, zones = set(), set(), []
    for d, area, li, k in pairs:
        if li in taken_l or k in taken_k: continue
        taken_l.add(li); taken_k.add(k)
        x, y, t, bb = labels[li]
        mm = re.match(r"((?:CTR|ATZ)(?:\s+(?!GND|SFC|MSL)[A-Z][A-Z’' ]*?)?)(?=\s+GND|\s+SFC|\s+MSL|\s+\d|\s+WEEKEND|\s*$)", t)
        name = re.sub(r'\s+', ' ', mm.group(1) if mm else t.split()[0]).strip()
        nearby = [(abs(y2 - y) + abs(x2 - x) / 3, t2) for x2, y2, t2, _ in lines if abs(x2 - x) < 70 and 0 < abs(y2 - y) < 26]
        if len(name) <= 4:
            cand = [t2 for _, t2 in sorted(nearby) if re.fullmatch(r"[A-Z][A-Z’' ]{2,}", t2) and t2 not in ('WEEKEND', 'QNH', 'GND', 'AGL')]
            if cand: name = f'{name} {cand[0]}'
        nxt = ' '.join(t2 for _, t2 in sorted(nearby)[:2])
        weekend = 'WEEKEND' in t.upper() or any(t2.strip().upper() == 'WEEKEND' and 0 < y2 - y < 16 and abs(x2 - x) < 40 for x2, y2, t2, _ in lines)
        lo, hi = _ctr_alt(t)
        if hi is None: lo, hi = _ctr_alt(nxt)
        if len(name) <= 4: continue          # unnamed outline label
        pts = cands[k][0]
        title = ' '.join(w if w in ('CTR', 'ATZ') else w.capitalize() for w in name.split())
        zones.append(_zone(title + (' (weekend)' if weekend else ''), 'aip_ctr' if name.startswith('CTR') else 'aip_atz',
                           [f(px, py) for px, py in pts], 'polygon', lo if lo is not None else 0, hi, END if weekend else None,
                           ('Active on weekends (Fri-Sat). ' if weekend else '') + 'From the CVFR chart: ' + t, src, from_chart=True,
                           ceil_ref='AMSL' if hi else None))
    # a CTR that has a separate (smaller) weekend version is the weekday CTR
    wk = {z['name'].replace(' (weekend)', '') for z in zones if z.get('days') == END}
    for z in zones:
        if not z.get('days') and z['name'] in wk:
            twin = next(o for o in zones if o['name'] == z['name'] + ' (weekend)')
            if z.get('ceil_ft') is None: z['ceil_ft'], z['ceil_ref'] = twin.get('ceil_ft'), twin.get('ceil_ref')
            z['days'] = MID; z['text'] = 'Weekdays (Sun-Thu); on weekends the smaller weekend CTR applies. ' + z['text']
    return zones


def georef(spans):
    lon, lat = [], []
    for cx, cy, t, bb in spans:
        m = LAB.fullmatch(t)
        if not m: continue
        v = int(m.group(1)) + int(m.group(2)) / 60
        if m.group(3) == 'E' and (cy < 130 or cy > 2690) and (bb[2] - bb[0]) < 32: lon.append((cx, cy, v))
        if m.group(3) == 'N' and (cx < 90 or cx > 1900): lat.append((cx, cy, v))
    if len(lon) < 6 or len(lat) < 6: raise ValueError('graticule not found')

    def robust(pts):
        pts = list(pts)
        while True:
            c = _lsq(pts); e = [abs(c[0] + c[1] * x + c[2] * y - v) for x, y, v in pts]
            if max(e) < 0.004 or len(pts) <= 6: return c, max(e)
            pts.pop(e.index(max(e)))
    (fl, el), (fa, ea) = robust(lon), robust(lat)
    return (lambda x, y: (round(fa[0] + fa[1] * x + fa[2] * y, 5), round(fl[0] + fl[1] * x + fl[2] * y, 5))), max(el, ea)


def _pts(g):
    out = []
    for it in g['items']:
        k = it[0]
        if k == 'l': out += ([(it[1].x, it[1].y)] if not out else []) + [(it[2].x, it[2].y)]
        elif k == 'c':
            p0, c1, c2, p3 = it[1:5]
            seg = [(p0.x * (1 - t) ** 3 + 3 * c1.x * t * (1 - t) ** 2 + 3 * c2.x * t ** 2 * (1 - t) + p3.x * t ** 3,
                    p0.y * (1 - t) ** 3 + 3 * c1.y * t * (1 - t) ** 2 + 3 * c2.y * t ** 2 * (1 - t) + p3.y * t ** 3) for t in (0, .25, .5, .75, 1)]
            out += seg if not out else seg[1:]
        elif k == 're':
            r = it[1]; out += [(r.x0, r.y0), (r.x1, r.y0), (r.x1, r.y1), (r.x0, r.y1), (r.x0, r.y0)]
        elif k == 'qu':
            q = it[1]; out += [(q.ul.x, q.ul.y), (q.ur.x, q.ur.y), (q.lr.x, q.lr.y), (q.ll.x, q.ll.y), (q.ul.x, q.ul.y)]
    return out


def _insets(dr):
    out = []
    for i, g in enumerate(dr):
        r = g['rect']
        if g['type'] == 'f' and g.get('fill') == (1.0, 1.0, 1.0) and 150000 < r.width * r.height < 1500000 and r.x1 < 1400 and i > 20000 and 400 < r.y0 < 1900:
            if not any(abs(r.x0 - o[1].x0) < 30 and abs(r.y0 - o[1].y0) < 30 for o in out): out.append((i, r))
    return out


def _inside(x, y, ring):
    ins = False
    for i in range(len(ring) - 1):
        (x1, y1), (x2, y2) = ring[i], ring[i + 1]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1: ins = not ins
    return ins


def _dashed(g):
    return bool(g.get('dashes') and re.search(r'[1-9]', g['dashes'].split(']')[0]))


def _alt_tags(dr, spans):
    """Yellow altitude boxes ('route altitude' in feet) -> [(x, y, feet)]."""
    tags = []
    for g in dr:
        r, f = g['rect'], g.get('fill')
        if f and _near(f, (1.0, 0.83, 0.0), .05) and 12 < r.width < 45 and 5 < r.height < 16:
            txt = ''.join(t for x, y, t, _ in spans if r.x0 - 1 <= x <= r.x1 + 1 and r.y0 - 1 <= y <= r.y1 + 1)
            m = re.search(r'(\d{3,5})', txt.replace(' ', ''))
            if m and 100 <= int(m.group(1)) <= 15000: tags.append(((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2, int(m.group(1))))
    return tags


def _route_alt(pts, tags):
    best, bd = None, 30.0
    for x, y, v in tags:
        for px, py in pts[:: max(1, len(pts) // 12)] + [pts[-1]]:
            d = math.hypot(px - x, py - y)
            if d < bd: best, bd = v, d
    return best


def _zone(name, layer, ring, kind, floor, ceil, days, text, src, **extra):
    z = {'id': name, 'name': name, 'layer': layer, 'floor_ft': floor, 'ceil_ft': ceil, 'days': days, 'text': text, 'source': src,
         'geom': {'kind': kind, 'ring': ring}}
    z.update(extra)
    return z


def chart_kind(dr):
    brown = sum(1 for g in dr if g['type'] == 's' and _near(g.get('color'), (0.5, 0.29, 0.17)) and 2 <= (g.get('width') or 0) <= 3)
    blue = sum(1 for g in dr if g['type'] == 's' and _near(g.get('color'), (0.0, 0.52, 0.81)) and 2.3 <= (g.get('width') or 0) <= 3.2)
    if brown > 20: return 'sport'
    if blue > 20: return 'cvfr'
    return None


def extract_page(page, kind, sheet):
    spans = _spans(page); f, res = georef(spans)
    dr = page.get_drawings(); ins = _insets(dr); tags = _alt_tags(dr, spans)
    src = 'Domestic AIP ' + ('B-08 sport chart' if kind == 'sport' else 'B-03 CVFR chart') + f' ({sheet})'
    zones, ctr_c = [], []
    for i, g in enumerate(dr):
        r = g['rect']; cx, cy = (r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2
        if r.x0 > 1600 and r.y0 > 1650: continue                     # legend
        if any(i > k and q.x0 <= cx <= q.x1 and q.y0 <= cy <= q.y1 for k, q in ins): continue   # enlarged insets
        col, fil, w = g.get('color'), g.get('fill'), g.get('width') or 0
        if kind == 'cvfr' and g['type'] == 's' and _near(col, (0.34, 0.32, 0.31), .04) and 0.8 <= w <= 1.8 and r.width * r.height > 600:
            pts = _pts(g)
            if len(pts) >= 4 and math.hypot(pts[0][0] - pts[-1][0], pts[0][1] - pts[-1][1]) < 3:
                ctr_c.append((pts, _dashed(g)))
            continue
        if kind == 'sport' and fil and _near(fil, (0.28, 0.76, 0.92), .06) and 15 < r.width < 30 and r.height < 18:
            near = sorted(((math.hypot(x - cx, y - cy), t) for x, y, t, _ in spans if HEB.search(t) and math.hypot(x - cx, y - cy) < 70), key=lambda a: a[0])
            nm = near[0][1] if near else 'Launch site'
            zones.append(_zone(nm, 'launch_site', [f(cx, cy)], 'point', None, None, None,
                               'Estimated paraglider / hang-glider launch point (sport chart symbol).', src))
            continue
        if g['type'] == 's' and 2.0 <= w <= 3.2:
            layer = None
            if kind == 'sport':
                if _near(col, (0.0, 0.59, 0.25)): layer, days, nm = 'sport_route_mid', MID, 'Midweek sport route'
                elif _near(col, (0.5, 0.29, 0.17)): layer, days, nm = 'sport_route_end', END, 'Weekend sport route'
                elif _near(col, (0.72, 0.05, 0.5), .05) or _near(col, (0.75, 0.03, 0.5), .05): layer, days, nm = 'sport_route_special', None, 'Special sport route'
            else:
                if _near(col, (0.0, 0.59, 0.25)): layer, days, nm = 'cvfr_route', None, 'CVFR route'
                elif _near(col, (0.0, 0.52, 0.81)): layer, days, nm = 'cvfr_mil', None, 'Military low-level route'
            if not layer: continue
            pts = _pts(g)
            if len(pts) < 2: continue
            appr = _dashed(g)
            alt = _route_alt(pts, tags)
            title = nm + (' · controller approval only' if appr else '')
            zones.append(_zone(title, layer, [f(x, y) for x, y in pts], 'line', None, alt, days,
                               (f'Published route altitude {alt:,} ft. ' if alt else '') + ('This leg may only be flown with controller approval.' if appr else ''),
                               src, approval=appr, route_alt=alt))
        elif kind == 'sport' and g['type'] == 'fs' and fil and col and w < 1.5:
            if _near(col, (0.5, 0.29, 0.17)) and _near(fil, (0.67, 0.44, 0.1), .05): layer, days, nm = 'sport_bubble_end', END, 'Weekend bubble'
            elif _near(col, (0.0, 0.59, 0.25), .05) and _near(fil, (0.23, 0.67, 0.21), .05): layer, days, nm = 'sport_bubble_all', None, 'Every-day bubble'
            else: continue
            pts = _pts(g)
            if len(pts) < 4 or r.width < 8: continue
            inn = [(x, y, t) for x, y, t, _ in spans if r.x0 <= x <= r.x1 and r.y0 <= y <= r.y1 and _inside(x, y, pts)]
            nums = [int(t.replace(' ', '')) for _, _, t in inn if re.fullmatch(r'\d{1,2}\s?\d{3}', t)]
            ceil = max(nums) if nums else None
            label = next((t for _, _, t in inn if t.startswith('בועת') and len(t) > 5), '')
            places = sorted({t for _, _, t in inn if HEB.search(t) and len(t) > 2 and not t.startswith('בועת')})[:12]
            title = label or (nm + (f' · up to {ceil:,} ft' if ceil else ''))
            zones.append(_zone(title, layer, [f(x, y) for x, y in pts], 'polygon', 0, ceil, days,
                               ('Places inside: ' + ', '.join(places)) if places else '', src))
    if ctr_c: zones += match_ctrs(ctr_c, _lines(page), f, src)
    return zones, res


def extract(pdf_path, log=print):
    import fitz
    d = fitz.open(pdf_path); out = []
    for i, p in enumerate(d):
        if i < 100 or 'ELEV ALT IN FEET' not in p.get_text(): continue
        dr = p.get_drawings()
        if len(dr) < 20000: continue
        kind = chart_kind(dr)
        if not kind: continue
        sheet = 'north' if sum(1 for o in out if o[0] == kind) == 0 else 'south'
        z, res = extract_page(p, kind, sheet)
        log(f'  chart p{i + 1}: {kind}/{sheet} {len(z)} features, georef residual {res * 111:.2f} km')
        out.append((kind, z))
    seen, uniq, ctrs = set(), [], []
    for _, zs in out:
        for z in zs:
            r = z['geom']['ring']; c = (sum(p[0] for p in r) / len(r), sum(p[1] for p in r) / len(r))
            if z['layer'] in ('aip_ctr', 'aip_atz'):   # the same CTR appears on both sheets
                if any(o[0] == z['layer'] and abs(o[1] - c[0]) < .03 and abs(o[2] - c[1]) < .03 and o[3] == tuple(z.get('days') or ()) for o in ctrs): continue
                ctrs.append((z['layer'], c[0], c[1], tuple(z.get('days') or ())))
            k = (z['layer'], round(c[0], 3), round(c[1], 3))
            if k in seen: continue
            seen.add(k); uniq.append(z)
    return uniq
