"""Live NOTAMs from the Israel Airports Authority.

List: brin.iaa.gov.il/aeroinfo (all current NOTAMs, row ids).
Detail: brin.iaa.gov.il/MobileAeroinfo/maiDetails.aspx?rowID=... (full ICAO text with Q/B/C/D/E/F/G).
Details are cached per row id, so each NOTAM is downloaded once.
"""
import calendar, datetime as dt, html, json, os, re, time, urllib.request
from .geometry import NM, UNL, circle, find_coords, parse_alt, polygon, radius_m

LIST_URL = 'https://brin.iaa.gov.il/aeroinfo/AeroInfo.aspx?msgType=Notam'
DETAIL_URL = 'https://brin.iaa.gov.il/MobileAeroinfo/maiDetails.aspx?rowID={}&scrpos=0&mode=notam'
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36'

LABELS = {
    'notam_restr': 'Restricted / firing / exercises', 'notam_para': 'Parachuting', 'notam_uas': 'Drone (UAS) activity',
    'notam_obst': 'Obstacles, balloons & hazards', 'notam_sport': 'Sport aviation (bubbles, gliders, UL)',
    'notam_route': 'VFR & sport route changes', 'notam_airspace': 'Airspace changes (CTR / TMA / training)',
    'notam_ifr': 'Aerodrome & IFR info',
}


def _get(url, timeout=40):
    return urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': UA}), timeout=timeout).read().decode('utf-8', 'replace')


def _text(h):
    h = re.sub(r'<(script|style).*?</\1>', '', h, flags=re.S)
    t = html.unescape(re.sub(r'<[^>]+>', '\n', h)).replace('\xa0', ' ')
    return re.sub(r'\n\s*\n+', '\n', t)


def list_ids():
    page = _get(LIST_URL)
    ids = list(dict.fromkeys(re.findall(r'divMainInfo_(\d+)', page)))
    if not ids: raise RuntimeError('NOTAM list empty or page format changed')
    return ids


def fetch_details(ids, cache_dir, delay=0.35, log=print):
    os.makedirs(cache_dir, exist_ok=True)
    got = {}
    for i in ids:
        fp = os.path.join(cache_dir, f'{i}.txt')
        if os.path.exists(fp):
            got[i] = open(fp, encoding='utf-8').read(); continue
        try:
            t = _text(_get(DETAIL_URL.format(i)))
            k = t.find('NOTAM NO')
            if k < 0: raise RuntimeError('no NOTAM text')
            t = t[k:]
            open(fp, 'w', encoding='utf-8').write(t); got[i] = t
            time.sleep(delay)
        except Exception as e:
            log(f'  NOTAM {i}: {e}')
    for f in os.listdir(cache_dir):  # forget cancelled / expired ones
        if f.endswith('.txt') and f[:-4] not in ids: os.remove(os.path.join(cache_dir, f))
    return got


# ---------------------------------------------------------------- parsing
def _ts(s):
    """YYMMDDHHMM (UTC) -> epoch seconds."""
    return calendar.timegm(dt.datetime.strptime(s, '%y%m%d%H%M').timetuple())


def parse(text):
    n = {'raw': text.strip()}
    m = re.search(r'NOTAM NO:\s*(\S+)', text); n['id'] = m.group(1) if m else '?'
    m = re.search(r'Location Indicator:\s*(\S+)', text); n['loc'] = m.group(1) if m else ''
    m = re.search(r'Location Description:\s*([^\n]+)', text); n['loc_name'] = m.group(1).strip() if m else ''
    body = text[text.find('('):] if '(' in text else text
    m = re.search(r'Q\)\s*([^\n]+)', body)
    if m:
        q = [p.strip() for p in m.group(1).split('/')]
        n['q'] = q[1] if len(q) > 1 else ''
        try:
            n['q_lo'], n['q_hi'] = int(q[5]) * 100, int(q[6]) * 100
            qm = re.match(r'(\d{4})([NS])(\d{5})([EW])(\d{3})', q[7])
            if qm:
                lat = int(qm.group(1)[:2]) + int(qm.group(1)[2:]) / 60
                lon = int(qm.group(3)[:3]) + int(qm.group(3)[3:]) / 60
                n['q_center'], n['q_radius_nm'] = (lat, lon), int(qm.group(5))
        except (IndexError, ValueError):
            pass
    m = re.search(r'B\)\s*(\d{10})', body); n['from'] = _ts(m.group(1)) if m else None
    m = re.search(r'C\)\s*(\d{10}|PERM)\s*(EST)?', body)
    n['to'] = None if not m or m.group(1) == 'PERM' else _ts(m.group(1)); n['est'] = bool(m and m.group(2))
    m = re.search(r'\bD\)\s*(.*?)\s*(?=\bE\))', body, re.S); n['sched'] = re.sub(r'\s+', ' ', m.group(1)).strip() if m else ''
    m = re.search(r'\bE\)\s*(.*?)(?=\n\s*[FG]\)|\)\s*$|\Z)', body, re.S)
    n['e'] = re.sub(r'\s+', ' ', m.group(1)).strip().rstrip(')').strip() if m else ''
    m = re.search(r'\bF\)\s*([^\n]*?)\s*(?=G\)|\n|$)', body); n['f'] = m.group(1).strip() if m else ''
    m = re.search(r'\bG\)\s*([^\n)]*)', body); n['g'] = m.group(1).strip() if m else ''
    return n


# ---------------------------------------------------------------- classification
def classify(n):
    q, e = n.get('q', ''), n.get('e', '').upper()
    s2 = q[1:3] if len(q) >= 3 else ''
    if s2 in ('WU', 'WZ'): return 'notam_uas'
    if s2 == 'WP': return 'notam_para'
    if s2 in ('WC', 'OB', 'OL', 'WS', 'WL'): return 'notam_obst'
    if s2 in ('WG',) or re.search(r'ULTRALIGHT|BUBBLE|PPG|PARAMOTOR|PARAGLID|HANG GLID|GLD ACT|GLIDER', e):
        return 'notam_route' if s2 in ('AR',) else 'notam_sport'
    if s2 in ('AR',) or re.search(r'\bCVFR\b|\bHEL RTE\b', e): return 'notam_route'
    if s2[:1] == 'R' or s2 in ('WM', 'WE', 'WD', 'WH', 'WB', 'WA', 'WT', 'WV', 'WF', 'WJ', 'WR'): return 'notam_restr'
    if s2 in ('AE', 'AC', 'AT', 'AA', 'AO', 'AF', 'AH', 'AL', 'AZ'): return 'notam_airspace'
    if re.search(r'PJE|PARACHUT', e): return 'notam_para'
    if re.search(r'\bUAS\b|\bUAV\b|DRONE', e): return 'notam_uas'
    if re.search(r'FIRING|EXER|MISSILE|ROCKET|RESTRICTED|PROHIBITED', e): return 'notam_restr'
    return 'notam_ifr'


# ---------------------------------------------------------------- schedule
DOW = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN']


def _dow_set(tok):
    m = re.fullmatch(r'(MON|TUE|WED|THU|FRI|SAT|SUN)(?:-(MON|TUE|WED|THU|FRI|SAT|SUN))?', tok)
    if not m: return None
    a = DOW.index(m.group(1)); b = DOW.index(m.group(2)) if m.group(2) else a
    out, i = set(), a
    while True:
        out.add(i)
        if i == b: break
        i = (i + 1) % 7
    return out


def intervals(n, now=None, horizon_days=31):
    """Active periods (UTC epoch pairs) within [now-1d, now+horizon] from B/C/D. None if unparseable (use B-C)."""
    b, c, sched = n.get('from'), n.get('to'), (n.get('sched') or '').upper()
    now = now or time.time()
    lo, hi = max(b or now, now - 86400), min(c or now + horizon_days * 86400, now + horizon_days * 86400)
    if hi <= lo: return []
    if not sched or re.search(r'\bH24\b', sched) and len(sched) < 6:
        return [(int(lo), int(hi))]
    out = []
    try:
        for seg in [s.strip() for s in sched.split(',') if s.strip()]:
            times = re.findall(r'(\d{4})-(\d{4})', seg)
            if not times:
                if 'SR-SS' in seg or 'SR - SS' in seg: times = [('0400', '1600')]  # rough Israel daylight in UTC
                else: return None
            head = re.sub(r'(\d{4})-(\d{4})', ' ', seg).replace('DAILY', ' ').replace('EXC', ' EXC ').split()
            dates, dows, excl = None, None, set()
            k = 0
            while k < len(head):
                t = head[k]
                if t == 'EXC':
                    ds = _dow_set(head[k + 1]) if k + 1 < len(head) else None
                    if ds: excl |= ds
                    k += 2; continue
                m = re.fullmatch(r'(\d{1,2})-(\d{1,2})', t)
                if m: dates = (dates or set()) | set(range(int(m.group(1)), int(m.group(2)) + 1))
                elif re.fullmatch(r'\d{1,2}', t): dates = (dates or set()) | {int(t)}
                elif _dow_set(t) is not None: dows = (dows or set()) | _dow_set(t)
                elif t in ('JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC', 'AND', '&'): pass
                else: return None
                k += 1
            day = dt.datetime.utcfromtimestamp(lo).replace(hour=0, minute=0, second=0)
            while day.timestamp() < hi:
                ok = (dates is None or day.day in dates) and (dows is None or day.weekday() in dows) and day.weekday() not in excl
                if ok:
                    base = calendar.timegm(day.timetuple())
                    for a, z in times:
                        s = base + int(a[:2]) * 3600 + int(a[2:]) * 60
                        e = base + int(z[:2]) * 3600 + int(z[2:]) * 60
                        if e <= s: e += 86400
                        s, e = max(s, b or s), min(e, c or e)
                        if e > s and e > lo and s < hi: out.append((int(s), int(e)))
                day += dt.timedelta(days=1)
    except Exception:
        return None
    return sorted(set(out))


# ---------------------------------------------------------------- geometry
def geometry(n, waypoints):
    e = n.get('e', '')
    pts = find_coords(e)
    r = radius_m(e)
    if pts and r:
        return circle(pts[0][0], pts[0][1], r)
    if len(pts) >= 3:
        return polygon(pts)
    for m in re.finditer(r'\b([A-Z]{5}(?:\s*-\s*[A-Z]{5})+)\b', e):
        chain = [waypoints[c] for c in re.findall(r'[A-Z]{5}', m.group(1)) if c in waypoints]
        if len(chain) >= 2:
            return {'kind': 'line', 'ring': chain}
    if pts and len(pts) == 1:
        return circle(pts[0][0], pts[0][1], 0.3 * NM, approx=True)
    qc, qr = n.get('q_center'), n.get('q_radius_nm')
    if qc and qr and qr < 60:
        return circle(qc[0], qc[1], max(qr, 0.5) * NM, approx=True)
    return None


def to_zone(n, waypoints, now=None):
    layer = classify(n)
    lo, lo_ref = parse_alt(n.get('f'))
    hi, hi_ref = parse_alt(n.get('g'))
    if lo is None and 'q_lo' in n: lo, lo_ref = n['q_lo'], ('GND' if n['q_lo'] == 0 else 'FL')
    if hi is None and 'q_hi' in n: hi, hi_ref = (UNL, 'UNL') if n['q_hi'] >= 99900 else (n['q_hi'], 'FL')
    iv = intervals(n, now)
    z = {'id': n['id'], 'name': n['id'], 'layer': layer, 'floor_ft': lo, 'ceil_ft': hi, 'floor_ref': lo_ref, 'ceil_ref': hi_ref,
         'geom': geometry(n, waypoints), 'text': n.get('e', ''), 'source': 'NOTAM', 'location': n.get('loc', ''),
         'valid_from': n.get('from'), 'valid_to': n.get('to'), 'est': n.get('est'), 'schedule': n.get('sched', ''),
         'times': iv if iv is not None else ([[n['from'], n['to'] or n['from'] + 14 * 86400]] if n.get('from') else None),
         'q': n.get('q', ''), 'raw': n['raw']}
    return z


def fetch(cache_dir, waypoints, log=print):
    ids = list_ids()
    det = fetch_details(ids, cache_dir, log=log)
    return [to_zone(parse(det[i]), waypoints) for i in ids if i in det]
