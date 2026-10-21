"""Shared geometry + altitude helpers."""
import math, re

NM = 1852.0
UNL = 99999

# 323145N0351642E | 323732.9N0352302.1E | 3231N03518E | N323122E0345511 | 32 31 45N 035 16 42E
_C1 = re.compile(r'(?<![\d.])(\d{4}(?:\d{2})?(?:\.\d+)?)\s*([NS])\s*[,/ ]?\s*(\d{5}(?:\d{2})?(?:\.\d+)?)\s*([EW])')
_C2 = re.compile(r'(?<![A-Z\d])([NS])\s*(\d{4}(?:\d{2})?(?:\.\d+)?)\s*([EW])\s*(\d{5}(?:\d{2})?(?:\.\d+)?)')


def _dms(v, deg):
    ip, _, fp = v.partition('.')
    d = int(ip[:deg]); rest = ip[deg:]
    if len(rest) == 2:
        return d + float(rest + ('.' + fp if fp else '')) / 60
    m = int(rest[:2]) if len(rest) >= 2 else 0
    s = float(rest[2:] + ('.' + fp if fp else '')) if len(rest) > 2 else 0.0
    return d + m / 60 + s / 3600


def in_region(lat, lon):
    return 28.5 <= lat <= 34.5 and 32.5 <= lon <= 37.5


def find_coords(text):
    """Ordered list of (lat, lon) found in free text (ICAO NOTAM / AIP styles)."""
    hits = []
    for m in _C1.finditer(text):
        lat = _dms(m.group(1), 2) * (1 if m.group(2) == 'N' else -1)
        lon = _dms(m.group(3), 3) * (1 if m.group(4) == 'E' else -1)
        hits.append((m.start(), lat, lon))
    for m in _C2.finditer(text):
        lat = _dms(m.group(2), 2) * (1 if m.group(1) == 'N' else -1)
        lon = _dms(m.group(4), 3) * (1 if m.group(3) == 'E' else -1)
        hits.append((m.start(), lat, lon))
    for m in re.finditer(r'(?<![\d.])(\d{6})E\s*(\d{7})E', text):  # common typo: lat written with E
        hits.append((m.start(), _dms(m.group(1), 2), _dms(m.group(2), 3)))
    hits.sort()
    return [(la, lo) for _, la, lo in hits if in_region(la, lo)]


def circle_ring(lat, lon, r_m, n=48):
    ring = []
    for i in range(n):
        b = 2 * math.pi * i / n
        ring.append((lat + r_m * math.cos(b) / 111320.0, lon + r_m * math.sin(b) / (111320.0 * math.cos(math.radians(lat)))))
    ring.append(ring[0])
    return ring


def circle(lat, lon, r_m, approx=False):
    g = {'kind': 'circle', 'center': (lat, lon), 'radius_m': round(r_m), 'ring': circle_ring(lat, lon, r_m)}
    if approx: g['approx'] = True
    return g


def polygon(pts):
    ring = list(pts)
    if ring[0] != ring[-1]: ring.append(ring[0])
    return {'kind': 'polygon', 'ring': ring}


RADIUS = re.compile(r'(?:(\d+(?:\.\d+)?)\s*(NM|KM|M)\s*(?:RADIUS|RAD)\b|(?:RADIUS|RAD)\s*(?:OF\s*)?(\d+(?:\.\d+)?)\s*(NM|KM|M)\b)')


def radius_m(text):
    m = RADIUS.search(text)
    if not m: return None
    v = float(m.group(1) or m.group(3)); u = m.group(2) or m.group(4)
    return v * {'NM': NM, 'KM': 1000.0, 'M': 1.0}[u]


def parse_alt(s):
    """'GND' | '1,500FT AMSL' | '400M AGL' | 'FL095' | 'UNL' -> (feet, ref) ; ref in GND/AMSL/AGL/FL/UNL or None."""
    if not s: return None, None
    s = s.upper().replace(',', '').strip()
    if re.match(r'(GND|SFC)\b', s): return 0, 'GND'
    if s.startswith('UNL'): return UNL, 'UNL'
    m = re.match(r'FL\s*(\d+)', s)
    if m: return int(m.group(1)) * 100, 'FL'
    m = re.search(r'(\d+(?:\.\d+)?)\s*(FT|M)\b\s*(AMSL|MSL|AGL|SFC|ALT)?', s)
    if m:
        v = float(m.group(1)) * (3.28084 if m.group(2) == 'M' else 1)
        ref = {'AGL': 'AGL', 'SFC': 'AGL'}.get(m.group(3) or '', 'AMSL')
        return int(round(v)), ref
    return None, None


def point_in_ring(lat, lon, ring):
    inside = False
    for i in range(len(ring) - 1):
        y1, x1 = ring[i]; y2, x2 = ring[i + 1]
        if (x1 > lon) != (x2 > lon) and lat < (y2 - y1) * (lon - x1) / (x2 - x1) + y1:
            inside = not inside
    return inside
