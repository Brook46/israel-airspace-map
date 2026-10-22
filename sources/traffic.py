"""Live traffic over Israel.

* ADS-B (airliners, GA, helicopters, some ultralights / gliders): opendata.adsb.fi, fallback api.adsb.lol
  (community-fed, free; rate limited, so results are cached for a few seconds).
* FLARM / OGN / FANET trackers (gliders, paragliders, hang gliders, tow planes, some drones):
  Open Glider Network APRS stream (aprs.glidernet.org:14580), kept open in a background thread.
Drones with Remote ID broadcast only over local radio; there is no public network feed for them.
"""
import json, math, re, socket, threading, time, urllib.request

UA = 'IsraelAirspaceMap/1.0 (personal pilot tool)'
CENTER, RADIUS_NM = (31.6, 35.0), 250
ADSB = ['https://opendata.adsb.fi/api/v2/lat/{lat}/lon/{lon}/dist/{nm}', 'https://api.adsb.lol/v2/lat/{lat}/lon/{lon}/dist/{nm}']
CAT = {'A1': 'light', 'A2': 'plane', 'A3': 'plane', 'A4': 'plane', 'A5': 'plane', 'A6': 'jet', 'A7': 'helicopter',
       'B1': 'glider', 'B2': 'balloon', 'B3': 'skydiver', 'B4': 'ultralight', 'B6': 'drone'}
OGN_TYPE = {1: 'glider', 2: 'tow plane', 3: 'helicopter', 4: 'skydiver', 5: 'drop plane', 6: 'hang glider', 7: 'paraglider',
            8: 'plane', 9: 'jet', 11: 'balloon', 12: 'airship', 13: 'drone'}

_lock = threading.Lock()
_adsb = {'t': 0, 'items': [], 'src': None, 'err': None}
_ogn = {}            # id -> item
_ogn_state = {'connected': False, 'err': None, 'since': None}


def _adsb_fetch():
    last = None
    for url in ADSB:
        try:
            req = urllib.request.Request(url.format(lat=CENTER[0], lon=CENTER[1], nm=RADIUS_NM), headers={'User-Agent': UA})
            d = json.loads(urllib.request.urlopen(req, timeout=12).read())
            out = []
            for a in d.get('aircraft') or d.get('ac') or []:
                if a.get('lat') is None: continue
                alt = a.get('alt_baro'); ground = alt == 'ground'
                out.append({'id': 'icao-' + a.get('hex', ''), 'cs': (a.get('flight') or '').strip() or a.get('r') or a.get('hex'),
                            'reg': a.get('r'), 'model': a.get('desc') or a.get('t'), 'kind': CAT.get(a.get('category'), 'plane'),
                            'lat': a['lat'], 'lon': a['lon'], 'alt_ft': 0 if ground else alt, 'gnd': ground,
                            'alt_geo_ft': a.get('alt_geom'), 'gs_kt': a.get('gs'), 'trk': a.get('track'), 'vs_fpm': a.get('baro_rate') or a.get('geom_rate'),
                            'squawk': a.get('squawk'), 'age': a.get('seen_pos', 0), 'src': 'ADS-B'})
            return out, url.split('/')[2]
        except Exception as e:
            last = e
    raise RuntimeError(f'ADS-B unavailable: {last}')


def adsb(max_age=8):
    with _lock:
        if time.time() - _adsb['t'] < max_age: return _adsb
    try:
        items, src = _adsb_fetch()
        with _lock: _adsb.update(t=time.time(), items=items, src=src, err=None)
    except Exception as e:
        with _lock: _adsb.update(t=time.time(), err=str(e))
    return _adsb


# ---------------------------------------------------------------- OGN APRS
_POS = re.compile(r"[/@](?:\d{6}h)?(\d{2})(\d{2}\.\d{2})([NS]).(\d{3})(\d{2}\.\d{2})([EW])(.)(\d{3})/(\d{3})/A=(-?\d{6})(.*)")


def _parse(line):
    if line.startswith('#') or '>' not in line: return None
    src, rest = line.split('>', 1)
    body = rest.split(':', 1)[1] if ':' in rest else ''
    m = _POS.search(body)
    if not m: return None
    la = int(m.group(1)) + float(m.group(2)) / 60; lo = int(m.group(4)) + float(m.group(5)) / 60
    tail = m.group(11)
    pe = re.search(r'!W(\d)(\d)!', tail)
    if pe: la += int(pe.group(1)) / 60000; lo += int(pe.group(2)) / 60000
    if m.group(3) == 'S': la = -la
    if m.group(6) == 'W': lo = -lo
    idm = re.search(r'\bid([0-9A-F]{2})([0-9A-F]{6})', tail)
    kind = 'unknown'; stealth = False
    if idm:
        b = int(idm.group(1), 16); kind = OGN_TYPE.get((b >> 2) & 0x0F, 'unknown'); stealth = bool(b & 0x80)
        if b & 0x40: return None                       # no-tracking flag set by the pilot: respect it
    climb = re.search(r'([+-]\d+)fpm', tail)
    return {'id': 'ogn-' + src, 'cs': src, 'kind': kind, 'lat': round(la, 5), 'lon': round(lo, 5), 'alt_ft': int(m.group(10)),
            'trk': int(m.group(8)), 'gs_kt': int(m.group(9)), 'vs_fpm': int(climb.group(1)) if climb else None, 't': time.time(), 'src': 'OGN/FLARM'}


def _ogn_loop():
    while True:
        try:
            s = socket.create_connection(('aprs.glidernet.org', 14580), timeout=30)
            s.sendall(f'user N0CALL pass -1 vers israel-airspace 1.0 filter r/{CENTER[0]}/{CENTER[1]}/450\n'.encode())
            _ogn_state.update(connected=True, err=None, since=time.time())
            s.settimeout(90); buf = b''; last_ka = time.time()
            while True:
                if time.time() - last_ka > 240: s.sendall(b'# keepalive\n'); last_ka = time.time()
                d = s.recv(8192)
                if not d: raise ConnectionError('closed')
                buf += d
                *lines, buf = buf.split(b'\n')
                for ln in lines:
                    it = _parse(ln.decode('utf-8', 'replace').strip())
                    if it:
                        with _lock: _ogn[it['id']] = it
        except Exception as e:
            _ogn_state.update(connected=False, err=str(e))
            time.sleep(30)


def start_ogn():
    threading.Thread(target=_ogn_loop, daemon=True).start()


def snapshot():
    a = adsb()
    now = time.time()
    with _lock:
        for k in [k for k, v in _ogn.items() if now - v['t'] > 600]: del _ogn[k]
        og = [dict(v, age=round(now - v['t'])) for v in _ogn.values()]
        items = [i for i in list(a['items']) + og if 29.3 <= i['lat'] <= 33.6 and 33.9 <= i['lon'] <= 36.3]   # Israel + surrounding approach
    return {'t': int(now), 'items': items,
            'sources': {'adsb': {'ok': a['err'] is None, 'from': a['src'], 'msg': a['err'] or f"{len(a['items'])} aircraft"},
                        'ogn': {'ok': _ogn_state['connected'], 'msg': (f'{len(og)} trackers' if _ogn_state['connected'] else (_ogn_state['err'] or 'connecting'))}}}
