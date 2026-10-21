"""What an area is for: Hebrew AIP descriptions (domestic AIP chapter A-17) + eAIP ENR 5.1 remarks -> plain English."""
import re

# (pattern, English purpose) — first matches win but all matches are reported
RULES = [
    (r'הטסת רחפנים|רחפנ|כטב"ם|כטב״ם|כטבמ|\bUAS\b|\bUAV\b|DRONE', 'Drone (UAS) flying'),
    (r'טיסנ|MODEL', 'Model-aircraft flying'),
    (r'צנח|PJE|PARACHUT', 'Parachuting / skydiving'),
    (r'ש\s?טח(?:י)?\s?אש|מטווח|ירי|FIRING|RANGE|GUNNERY', 'Live firing / weapons range'),
    (r'\bTRG\b|אימון|TRAINING', 'Military flight training'),
    (r'MILOPS|\bMIL\b|צה"ל|צבא|בסיס|IDF', 'Military activity'),
    (r'טורבינ|TURBINE', 'Wind turbines'),
    (r'מחצב|פיצוצ|QUARRY|BLAST', 'Quarry blasting'),
    (r'אסד', 'Offshore gas platform'),
    (r'תחנת כוח|תחנת אשדוד|תחנת חדרה|מתקן|בתי הזיקוק|זיקוק|כור|מכון|דימונה|POWER', 'Sensitive / security site'),
    (r'בלון', 'Tethered balloon'),
    (r'כדור(?:ים)? פורח', 'Hot-air balloons'),
    (r'אירובט|AEROBATIC', 'Aerobatics'),
    (r'שמורת טבע|קינון|ציפור|BIRD', 'Nature reserve / bird protection'),
    (r'גבול|BORDER', 'Border area'),
    (r'הר הבית|ירושלים|כנסת|משכן', 'Sensitive site (Jerusalem)'),
]
RMK = {'TRG': 'training', 'MIL': 'military', 'MILOPS': 'military operations', 'CIVIL': 'civil', 'H24': 'active 24 hours'}


def purposes(*texts):
    t = ' '.join(x for x in texts if x)
    out = []
    for rx, en in RULES:
        if re.search(rx, t, re.I) and en not in out: out.append(en)
    return out


PAGE_HDR = re.compile(r'פמ"ת פנים ארצי|רשות התעופה האזרחית|א-\s*\d+\s*-\s*\d+|עדכון\s*\d+/\d+|\b\d{1,2}\s*[\'׳]?\s*(?:ינו|פבר|מרץ|אפר|מאי|יוני|יולי|אוג|ספט|אוק|נוב|דצמ)\S*\s*\d{4}|\d{4}\s*[\'׳]?(?:ינו|פבר|מרץ|אפר|מאי|יוני|יולי|אוג|ספט|אוק|נוב|דצמ)\S*')


def descriptions(pdf_path):
    """{'LLD41': 'LLD41, האזור המסוכן "דליה": …'} from the domestic AIP chapter A-17 paragraphs."""
    import fitz
    d = fitz.open(pdf_path)
    pages = [i for i, p in enumerate(d) if i < 120 and re.search(r'האזור (?:האסור|המסוכן|המוגבל|אסור)', p.get_text())]
    if not pages: return {}
    t = re.sub(r'\s+', ' ', ' '.join(d[i].get_text() for i in range(min(pages), max(pages) + 1)))
    t = PAGE_HDR.sub(' ', t)
    marks = []
    for m in re.finditer(r'\b(LL[PRDU])\s?(\d{1,4})\b|\b(\d{1,4})\s?(LL[PRDU])\b', t):
        code = (m.group(1) + m.group(2)) if m.group(1) else (m.group(4) + m.group(3))
        marks.append((m.start(), m.end(), code))
    out = {}
    for i, (s, e, code) in enumerate(marks):
        nxt = marks[i + 1][0] if i + 1 < len(marks) else len(t)
        seg = t[e:min(nxt, e + 700)]
        if 'האזור' not in seg[:80]: continue                       # list / table mentions, not the paragraph
        seg = re.sub(r'\s+[א-ת]{1,2}\.\s*$', '', seg.strip())        # trailing enumerator of the next item
        seg = seg.strip(' ,.:')
        if code not in out or len(seg) > len(out[code]): out[code] = f'{code}, {seg}'
    return out


def contacts(text):
    phones = re.findall(r'0\d{1,2}-?\d{7}|05\d-?\d{7}|0\d-\d{7}', text or '')
    tower = re.search(r'מגדל\s+([א-ת"\' ]{2,20}?)(?=\s+בטלפון|\s*[,.:]|\s*$)', text or '')
    return phones, (tower.group(1).strip() if tower else None)


def remark_en(rem):
    toks = [RMK.get(w, None) for w in re.findall(r'[A-Z0-9]+', rem or '')]
    return ', '.join(dict.fromkeys(t for t in toks if t))


TYPE_DEFAULT = {'aip_prohibited': 'Prohibited area — the AIP does not publish the reason (usually a security or sensitive site)',
                'aip_restricted': 'Restricted area — reason not stated in the AIP',
                'aip_danger': 'Danger area — the AIP does not state the activity',
                'aip_uas': 'No-fly circle for drones and sport aviation around a sensitive site',
                'aip_obst': 'Fixed obstacle (tethered balloon)'}


TOWERS = {'רמת דוד': 'Ramat David', 'חיפה': 'Haifa', 'הרצליה': 'Herzliya', 'תל נוף': 'Tel Nof', 'חצרים': 'Hatzerim', 'נבטים': 'Nevatim',
          'פלמחים': 'Palmachim', 'חצור': 'Hatzor', 'נתב"ג': 'Ben Gurion', 'מגידו': 'Megiddo', 'ראש פינה': 'Rosh Pina', 'עין שמר': 'Ein Shemer',
          'רמון': 'Ramon', 'עובדה': 'Ovda', 'קדם': 'Kedem', 'מצדה': 'Masada'}


def annotate(z, desc):
    """Attach Hebrew description, English purpose and coordination contacts to an AIP zone."""
    if desc: z['desc_he'] = desc
    p = purposes(desc, z.get('name'), z.get('text') if str(z.get('source', '')).startswith('eAIP') else '')
    z['purpose'] = p or ([TYPE_DEFAULT[z['layer']]] if z['layer'] in TYPE_DEFAULT else [])
    phones, tower = contacts(desc)
    if phones or tower: z['contact'] = ', '.join(([f'{TOWERS.get(tower, tower)} tower'] if tower else []) + phones)
    if 'NOTAM' in (desc or '') or 'נוטאם' in (desc or ''): z['purpose'].append('Activated by NOTAM only')
    return z
