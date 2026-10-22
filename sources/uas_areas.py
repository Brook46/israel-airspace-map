"""Drone (UAS) operating areas from the domestic AIP, chapter B-09, appendices B-1 / B-2 / B-3 (official tables).
These areas are not permanently active: activity is coordinated / published by NOTAM. Shapes are taken exactly from
the tables (polygons and circles); entries described with arcs or other constructions are left out."""
import math, re
from .geometry import circle_ring

CO = re.compile(r"(\d+)\s*°\s*(\d+)\s*['’]\s*(\d+(?:\.\d+)?)\s*(?:\"|''|’’|”)?\s*([NE])")


def _logical(s):
    """PDF tables come out in visual (reversed) order for Hebrew: reverse, then restore digit runs."""
    out = []
    for line in (s or '').split('\n'):                    # each visual line separately, keep line order
        line = re.sub(r'\s+', ' ', line).strip()
        if re.search(r'[א-ת]', line):
            line = re.sub(r'\d[\d .,:/\-]*\d', lambda m: m.group(0)[::-1], line[::-1])
        if line: out.append(line)
    return ' '.join(out)


def _ft(s):
    s = (s or '').replace(',', '')
    if re.search(r'GND|פני הקרקע|ק"ק', s): return 0
    m = re.search(r'(\d[\d ]{0,6}\d|\d)', s)
    return int(m.group(1).replace(' ', '')) if m else None


def _pt(e, n):
    a, b = CO.search(e or ''), CO.search(n or '')
    if not (a and b): return None
    f = lambda m: int(m.group(1)) + int(m.group(2)) / 60 + float(m.group(3)) / 3600
    lon, lat = (f(a), f(b)) if a.group(4) == 'E' else (f(b), f(a))
    return (lat, lon) if 29 < lat < 34 and 34 < lon < 36.5 else None


def parse(pdf_path):
    import fitz
    d = fitz.open(pdf_path)
    title = [i for i, p in enumerate(d) if 150 < i < 200 and 'נתונים גיאוגרפיים' in (_logical(p.get_text()) + p.get_text())]
    if not title: return []
    pages = []
    for i in range(min(title), min(title) + 12):          # title pages and their continuation pages
        if CO.search(d[i].get_text()) and d[i].find_tables().tables: pages.append(i)
        elif i > max(title): break
    zones = []
    for pi in pages:
        p = d[pi]; txt = p.get_text()
        lt = _logical(txt) + txt
        appx = 'B-3' if 'בראשית' in lt else 'B-2' if re.search(r'מזערי|ירעזמ', lt) else 'B-1'
        try: tabs = p.find_tables().tables
        except Exception: continue
        for tb in tabs:
            rows = [[_logical(c or '') for c in r] for r in tb.extract()]
            if not rows: continue
            ncol = len(rows[0])
            recs, cur = [], None
            for r in rows:
                name, east, north = r[-1], r[-2] if ncol > 1 else '', r[-3] if ncol > 2 else ''
                rest = [c for c in r[:-3] if c]
                if name and not re.search(r'^(שם|ם)$', name) and (name not in ('', 'שם')):
                    if name.strip() in ('מזרח', 'צפון', 'גובה', 'הערות', 'תיאום', 'שם', 'גובה מרבי', 'גובה מזערי'): continue
                    cur = {'name': name, 'pts': [], 'cells': [], 'appx': appx}; recs.append(cur)
                if cur is None: continue
                pt = _pt(east, north)
                if pt: cur['pts'].append(pt)
                else:
                    for c in (east, north):
                        if c and not CO.search(c): cur['cells'].append(c)
                cur['cells'] += rest
            for rc in recs:
                if not rc['pts']: continue
                info = ' '.join(dict.fromkeys(rc['cells']))
                heights = [_ft(c) for c in rc['cells'] if re.search(r'\d{3}|GND', c) and not re.search(r'\d{2}-\d{7}|טלפון|\d{3}-\d{3}', c)]
                heights = [h for h in heights if h is not None and h <= 20000]
                lo, hi = (min(heights), max(heights)) if len(heights) >= 2 else (0, heights[0] if heights else None)
                if appx == 'B-1': lo = 0
                if re.search(r'קשת|בין הנ"צים|גליל בעל', info): continue    # arcs / cylinders between points: not reproduced exactly
                m = re.search(r'רדיוס\s*של\s*([\d.]+)\s*(קילומטר|ק"מ|מייל|מטר)', info)
                if m:
                    r_m = float(m.group(1)) * {'קילומטר': 1000, 'ק"מ': 1000, 'מייל': 1852, 'מטר': 1}[m.group(2)]
                    c = rc['pts'][0]; geom = {'kind': 'circle', 'center': list(c), 'radius_m': round(r_m), 'ring': circle_ring(c[0], c[1], r_m)}
                elif len(rc['pts']) >= 3:
                    ring = rc['pts'] + ([rc['pts'][0]] if rc['pts'][0] != rc['pts'][-1] else []); geom = {'kind': 'polygon', 'ring': ring}
                else: continue
                nm = re.sub(r'\s+', ' ', rc['name']).strip()
                remark = re.sub(r'\s+', ' ', re.sub(r'\d[\d ]{2,6}\s*(רגל|ft)?\s*(מעפ"י|AMSL)?', '', info)).strip()
                zones.append({'id': f'UAS {nm}', 'name': f'Drone area {nm}', 'layer': 'uas_area', 'floor_ft': lo, 'floor_ref': 'GND' if not lo else 'AMSL',
                              'ceil_ft': hi, 'ceil_ref': 'AMSL', 'days': None, 'by_notam': True,
                              'text': 'Drone (UAS) operating area. Active only when coordinated / published by NOTAM — check active NOTAMs.',
                              'remark_he': remark[:400], 'source': f'Domestic AIP B-09 appendix {appx}',
                              'raw': f"{nm} | {' | '.join(rc['cells'])} | " + ' '.join(f'{a:.5f},{b:.5f}' for a, b in rc['pts']), 'geom': geom})
    return zones
