"""Parse text tables from the Hebrew domestic AIP PDF: appendices B (P/R/D), C (LLU no-fly circles), D (obstacles)."""
import math, re
from .geometry import circle_ring, NM
from .eaip import _arc, _zone

CO = re.compile(r"(\d+)\s*°\s*(\d+)\s*'\s*(\d+(?:\.\d+)?)\s*(?:\"|''|’’)?\s*([EN])")
UNLR = re.compile(r'\bUNL\b')


def _pairs(text):
    """Ordered [(lat, lon)] from 'E then N' (either order) coordinate tokens."""
    vals = [(m.start(), m.group(4), int(m.group(1)) + int(m.group(2)) / 60 + float(m.group(3)) / 3600) for m in CO.finditer(text)]
    out, i = [], 0
    while i + 1 < len(vals):
        a, b = vals[i], vals[i + 1]
        if {a[1], b[1]} == {'E', 'N'}:
            lon = a[2] if a[1] == 'E' else b[2]; lat = a[2] if a[1] == 'N' else b[2]
            out.append((a[0], (lat, lon))); i += 2
        else:
            i += 1
    return out


def _radius_m(txt):
    m2 = re.search(r'רדיוסו\s*[:|\s]*(ק"מ|מייל)\s*(אחד|חצי)', txt)
    if m2: return {'אחד': 1.0, 'חצי': 0.5}[m2.group(2)] * (1000 if m2.group(1) == 'ק"מ' else NM)
    m = re.search(r'רדיוסו\s*(חצי|אחד|[\d.]+)\s*[:|\s]*(ק"מ|קמ|מייל|מטר|מ\')?', txt)
    if not m: return None
    n = {'חצי': 0.5, 'אחד': 1.0}.get(m.group(1)) or float(m.group(1))
    u = m.group(2)
    if not u:
        u = re.search(r'ק"מ|מייל|מטר|מ\'', txt[m.end():m.end() + 25]); u = u.group(0) if u else None
    if u is None: u = 'מטר' if n >= 100 else 'ק"מ'
    r = n * {'ק"מ': 1000, 'קמ': 1000, 'מייל': NM, 'מטר': 1, "מ'": 1}[u]
    return r if r <= 60000 else None


def _alts(head):
    """-> (floor_ft, ceil_ft) from header text of a P/R/D record."""
    h = re.sub(r'\(\s*-\s*\)\s*(\d)', r'-\1', head.replace(',', ''))
    nums = [int(x.replace(' ', '')) for x in re.findall(r'-?(?<![\d.])\d{1,2}(?: \d{3})(?![\d.])|-?(?<![\d.])\d{3,5}(?![\d.])', h)]
    gnd = 'GND' in h
    ceil = 99999 if UNLR.search(h) else (nums[0] if nums else None)
    floor = 0 if gnd else (nums[1] if len(nums) > 1 else 0)
    return floor, ceil


def parse_prd(text, src):
    zones = []
    for rec in re.split(r'\n(?=LL[PRD]\d+)', text):
        m = re.match(r'(LL([PRD])\d+\w*)', rec)
        if not m: continue
        code, kind = m.group(1), m.group(2)
        flat = re.sub(r'\s*\n\s*', ' | ', rec)
        flat = re.sub(r'(\d)\s*\|\s*\.\s*\|\s*(\d)', r'\1.\2', flat)
        first = CO.search(flat); circ = 'מעגל' in flat
        head = flat[:first.start()] if first else flat
        if circ: head = flat[:flat.find('מעגל')] if flat.find('מעגל') > 0 else head
        heb = ' '.join(re.findall(r'[֐-׿"\'-]*[֐-׿][֐-׿"\'-]*', head)).replace('נ"צ', '').strip()
        floor, ceil = _alts(head)
        ps = _pairs(flat)
        layer = {'P': 'aip_prohibited', 'R': 'aip_restricted', 'D': 'aip_danger'}[kind]
        name = f'{code} {heb}'.strip()
        geom = None
        if circ and ps:
            r = _radius_m(flat)
            if r: geom = {'kind': 'circle', 'center': ps[0][1], 'radius_m': r, 'ring': circle_ring(ps[0][1][0], ps[0][1][1], r)}
        elif len(ps) >= 3:
            pts = [p for _, p in ps]; ring = []
            arcs = [(a.start(), re.search(r'([\d.]+)\s*[|\s]*:?\s*(ק"מ|מייל)', flat[a.start():a.start() + 80])) for a in re.finditer('קשת ברדיוס', flat)]
            i = 0; used = set()
            posn = [pos for pos, _ in ps]
            for ai, (apos, rm) in enumerate(arcs):
                idx = next((k for k, pos in enumerate(posn) if pos > apos), None)
                if idx is None or idx + 1 >= len(pts) or not rm: continue
                used.add(idx - 1)
            for k, p in enumerate(pts):
                ring.append(p)
            # rebuild with arcs: point before arc -> arc around center to end point
            ring = []; k = 0
            arc_after = {}
            for apos, rm in arcs:
                idx = next((j for j, pos in enumerate(posn) if pos > apos), None)
                if idx is not None and idx + 1 < len(pts) and rm:
                    r = float(rm.group(1)) * (NM if rm.group(2) == 'מייל' else 1000)
                    arc_after[idx - 1] = (pts[idx], pts[idx + 1], r)
            skip = set()
            for k, p in enumerate(pts):
                if k in skip: continue
                ring.append(p)
                if k in arc_after:
                    c, q, r = arc_after[k]
                    a1 = math.degrees(math.atan2((p[1] - c[1]) * math.cos(math.radians(c[0])), p[0] - c[0])) % 360
                    a2 = math.degrees(math.atan2((q[1] - c[1]) * math.cos(math.radians(c[0])), q[0] - c[0])) % 360
                    cw = ((a2 - a1) % 360) <= 180
                    ring += _arc(c, r, p, q, cw); ring.append(q); skip.update({k + 1, k + 2})
            if ring[0] != ring[-1]: ring.append(ring[0])
            geom = {'kind': 'polygon', 'ring': ring}
        if geom:
            z = _zone(name, geom, floor, ceil, layer, 'Domestic AIP appendix B', src); z['raw'] = re.sub(r'\s*\|\s*', '\n', flat).strip(); zones.append(z)
    return zones


def parse_llu(text, src):
    zones = []
    for rec in re.split(r'\n(?=LLU\d+)', text):
        m = re.match(r'(LLU\d+)', rec)
        if not m: continue
        flat = re.sub(r'\s*\n\s*', ' | ', rec)
        ps = [p for _, p in _pairs(flat)]
        first = CO.search(flat)
        head = flat[:first.start()] if first else flat
        heb = ' '.join(re.findall(r'[֐-׿"\'-]*[֐-׿][֐-׿"\'-]*', head.replace('מטר', ''))).strip()
        nm = re.findall(r'(?<![\d.])(\d{2,4})(?![\d.])', head.replace(m.group(1), ''))
        name = f'{m.group(1)} {heb}'.strip()
        if 'מטר' in head and ps and nm:
            r = float(nm[-1]) if len(nm) == 1 else float(nm[0])
            zones.append(_zone(name, {'kind': 'circle', 'center': ps[0], 'radius_m': r, 'ring': circle_ring(ps[0][0], ps[0][1], r)}, 0, None, 'aip_uas',
                               f'No-fly for drones, sport aviation and helicopters outside published routes (radius {int(r)} m)', src))
            zones[-1]['raw'] = re.sub(r'\s*\|\s*', '\n', flat).strip()
        elif len(ps) >= 3:
            zones.append(_zone(name, {'kind': 'polygon', 'ring': ps + [ps[0]]}, 0, None, 'aip_uas', 'No-fly area (LLU)', src))
    return zones


def parse_obstacles(text, src):
    zones = []
    flat = re.sub(r'\s+', ' ', text)
    for m in re.finditer(r'(LL[A-Z]\d{4})\s+(.*?)\s*([\d,]+)\s+(\d+\.\d+)\s+(\d{6})E\s+(\d{6})N', flat):
        code, label, alt, rad, lo, la = m.groups()
        def dms(v, d): return int(v[:d]) + int(v[d:d + 2]) / 60 + int(v[d + 2:d + 4]) / 3600
        lat, lon = dms(la, 2), dms(lo, 2)
        if not (28 < lat < 34 and 33 < lon < 37): continue
        r = float(rad) * NM; ceil = int(alt.replace(',', ''))
        heb = ' '.join(re.findall(r'[֐-׿"\'-]*[֐-׿][֐-׿"\'-]*', label))
        zones.append(_zone(f'{code} {heb}'.strip(), {'kind': 'circle', 'center': (lat, lon), 'radius_m': r, 'ring': circle_ring(lat, lon, r)}, 0, ceil, 'aip_obst',
                           'Fixed obstacle / tethered balloon', src))
    return zones


def parse_pdf(path):
    import fitz
    d = fitz.open(path); pages = [re.sub(r'\n+', '\n', p.get_text()) for p in d]
    def section(start_kw, end_kw, limit=40):
        s = next((i for i, t in enumerate(pages) if start_kw in t and 'LL' in t and i < 200 and ('קוד' in t or 'קוד זיהוי' in t)), None)
        return s
    # locate appendices by their headings
    pb = [i for i, t in enumerate(pages[:200]) if i > 55 and 'נספח ב' in t and 'אזורים אסורים, מוגבלים ומסוכנים' in t]
    pc = [i for i, t in enumerate(pages[:200]) if i > 70 and 'נספח ג' in t and 'LLU' in t]
    pd = [i for i, t in enumerate(pages[:200]) if i > 70 and 'נספח ד' in t and 'מכשולים קבועים' in t]
    if not pb: return []
    b0, c0 = pb[0], (pc[0] if pc else None); d0 = pd[0] if pd else None
    b_end = (c0 if c0 else b0 + 14); c_end = (d0 if d0 else (c0 + 4 if c0 else 0)); d_end = (d0 + 1) if d0 else 0
    src = 'Domestic AIP'
    z = parse_prd('\n'.join(pages[b0:b_end]), src)
    if c0 is not None: z += parse_llu('\n'.join(pages[c0:c_end]), src)
    if d0 is not None: z += parse_obstacles('\n'.join(pages[d0:d_end]), src)
    return z
