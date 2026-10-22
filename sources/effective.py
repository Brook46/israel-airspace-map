"""'When is it in force?' — one readable line per item, from what the official source says (never guessed)."""
import re

DAYS = {'SUN': 'Sun', 'MON': 'Mon', 'TUE': 'Tue', 'WED': 'Wed', 'THU': 'Thu', 'FRI': 'Fri', 'SAT': 'Sat'}
DOW = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
MONTHS_HE = {'ינואר': 'January', 'פברואר': 'February', 'מרץ': 'March', 'מרס': 'March', 'אפריל': 'April', 'מאי': 'May', 'יוני': 'June',
             'יולי': 'July', 'אוגוסט': 'August', 'ספטמבר': 'September', 'אוקטובר': 'October', 'נובמבר': 'November', 'דצמבר': 'December'}


def _cap(s): return s[:1].upper() + s[1:] if s else s


def _days(days):
    if not days or len(days) == 7: return 'every day'
    if days == [0, 1, 2, 3, 4]: return 'Sun–Thu (weekdays)'
    if days == [5, 6]: return 'Fri–Sat (weekend)'
    return ', '.join(DOW[d] for d in days)


def _eaip(text):
    t = (text or '').upper()
    parts = []
    if 'H24' in t: parts.append('24 hours (H24)')
    for m in re.finditer(r'\b(SUN|MON|TUE|WED|THU|FRI|SAT)\s+(\d{2}:\d{2}|SR)\s*(?:\(UTCW\))?\s*-\s*(SUN|MON|TUE|WED|THU|FRI|SAT)\s+(\d{2}:\d{2}|SS)\s*(?:\(UTCW\))?', t):
        a, ta, b, tb = m.groups()
        ta = 'sunrise' if ta == 'SR' else ta; tb = 'sunset' if tb == 'SS' else tb
        parts.append(f'{DAYS[a]} {ta} – {tb}' if a == b else f'{DAYS[a]} {ta} → {DAYS[b]} {tb}')
    same = {}
    for p in list(parts):
        m = re.fullmatch(r'(\w{3}) (sunrise|\d{2}:\d{2}) – (sunset|\d{2}:\d{2})', p)
        if m: same.setdefault(f'{m.group(2)} – {m.group(3)}', []).append(m.group(1)); parts.remove(p)
    order = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
    for span, ds in same.items(): parts.append(f"{', '.join(sorted(ds, key=order.index))}: {span}")
    if 'UTCW' in t: parts.append('times as published, marked UTCW')
    if re.search(r'HOLIDAY', t): parts.append('not on holidays (see AIP remark)')
    if re.search(r'\bNOTAM\b', t): parts.append('when activated by NOTAM')
    return '; '.join(dict.fromkeys(parts))


def _hebrew(desc):
    d = desc or ''; parts = []
    if re.search(r'נוטאם|NOTAM', d): parts.append('Only when activated by NOTAM')
    m = re.search(r'בין השעות\s*(\d{1,2}:?\d{2})\s*[-–]\s*(\d{1,2}:?\d{2})', d)
    if m: parts.append(f'between {m.group(1)} and {m.group(2)}')
    for he, en in MONTHS_HE.items():
        pass
    m = re.search(r'(' + '|'.join(MONTHS_HE) + r')\s*(?:עד|-|–)\s*(' + '|'.join(MONTHS_HE) + r')', d)
    if m: parts.append(f'season: {MONTHS_HE[m.group(1)]} to {MONTHS_HE[m.group(2)]}')
    if re.search(r'בכל גובה', d): parts.append('at all heights')
    return '; '.join(parts)


def effective(z):
    L, src = z.get('layer', ''), z.get('source', '')
    if src == 'NOTAM': return None                      # NOTAM cards show validity, schedule and next active times
    if L == 'uas_area': return 'Not permanent — only when drone activity is coordinated / published by NOTAM. Check active NOTAMs.'
    if L in ('sport_bubble_all', 'sport_bubble_end', 'sport_route_mid', 'sport_route_end', 'sport_route_special'):
        return _cap(f"{_days(z.get('days'))} (sport-aviation chart)")
    if L in ('aip_ctr', 'aip_atz') and z.get('from_chart'):
        return _cap(f"{_days(z.get('days'))} (CVFR chart" + (', a smaller CTR applies on weekends)' if z.get('days') == [0, 1, 2, 3, 4] else ')'))
    if L == 'nature_reserve':
        m = re.search(r'\(([^)]*עד[^)]*)\)', z.get('text', ''))
        s = _hebrew(z.get('text', '') + ' ' + z.get('raw', ''))
        return _cap(s) if s else 'All year (AIP appendix E)'
    if L in ('aip_uas', 'aip_obst'): return 'Permanent (domestic AIP)'
    if L in ('launch_site', 'landing_site', 'training_site', 'vfr_points', 'cvfr_route', 'cvfr_mil'): return None
    parts = []
    if src.startswith('eAIP'): parts.append(_eaip(z.get('text', '')))
    parts.append(_hebrew(z.get('desc_he', '')))
    s = '; '.join(p for p in parts if p)
    s = re.sub(r'(when activated by NOTAM); Only when activated by NOTAM', r'\1', s, flags=re.I)
    s = re.sub(r'^Only when activated by NOTAM; (.*)when activated by NOTAM', r'\1when activated by NOTAM', s)
    if s: return _cap(s)
    if L in ('aip_prohibited',): return 'Permanent unless the AIP says otherwise'
    if L in ('aip_tma', 'aip_ctr'): return 'As published in the AIP (normally 24 hours)'
    return 'Not stated in the AIP — check NOTAMs'
