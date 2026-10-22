'use strict';
/* Israel Airspace — client app. Data comes from data.json (built by update.py). */
const $ = (s, r = document) => r.querySelector(s), $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const FT = 3.28084, UNL = 99999, DAY = 86400000;
const store = {
  get(k, d) { try { const v = localStorage.getItem('as.' + k); return v == null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem('as.' + k, JSON.stringify(v)); } catch { } },
};
const toast = (msg, ms = 2600) => { const t = $('#toast'); t.textContent = msg; t.classList.add('on'); clearTimeout(toast.t); toast.t = setTimeout(() => t.classList.remove('on'), ms); };

/* ================================================================ layers */
const META = {
  // sport aviation
  sport_bubble_all: { g: 'Sport aviation', n: 'Bubbles · every day', t: 'Sport bubble · every day', c: '#30b94d', d: 'Airspace set aside for ultralights and powered paragliders, open every day.' },
  sport_bubble_end: { g: 'Sport aviation', n: 'Bubbles · weekend', t: 'Sport bubble · weekend', c: '#e0901a', d: 'Airspace set aside for ultralights and powered paragliders, open on weekends (Fri–Sat).' },
  sport_route_mid: { z: 9, g: 'Sport aviation', n: 'Routes · midweek (Sun–Thu)', t: 'Sport route · midweek', c: '#169c3c', d: 'Low-level sport-aviation route usable Sunday–Thursday.' },
  sport_route_end: { z: 9, g: 'Sport aviation', n: 'Routes · weekend (Fri–Sat)', t: 'Sport route · weekend', c: '#a0522d', d: 'Low-level sport-aviation route usable on weekends.' },
  sport_route_special: { z: 9, g: 'Sport aviation', n: 'Routes · special', t: 'Sport route · special', c: '#c2108a', d: 'Special sport-aviation route — see procedure B-08 for its conditions.' },
  launch_site: { g: 'Paragliding sites', n: 'Takeoffs (with wind directions)', t: 'Paragliding takeoff', c: '#0aa4e0', z: 7, d: 'Takeoff from OpenStreetMap. The coloured sectors show the wind directions the site works in. Check local club rules before flying.' },
  landing_site: { g: 'Paragliding sites', n: 'Landing fields', t: 'Landing field', c: '#30b94d', z: 11 },
  training_site: { g: 'Paragliding sites', n: 'Ground-handling spots', t: 'Ground-handling area', c: '#8e8e93', z: 11 },
  // airspace
  aip_ctr: { g: 'Airspace', n: 'Control zones (CTR)', t: 'Control Zone (CTR)', c: '#007aff', d: 'Controlled airspace around an airport or air-force base. Entry needs a clearance; paragliders may not fly inside IAF-base CTRs.' },
  aip_atz: { g: 'Airspace', n: 'Aerodrome zones (ATZ)', t: 'Aerodrome Traffic Zone (ATZ)', c: '#3d7bd9', d: 'Airspace around a smaller airfield. Contact the airfield / ATC before entering.' },
  aip_tma: { g: 'Airspace', n: 'Terminal areas (TMA)', t: 'Terminal Control Area', c: '#8e44d6', d: 'Controlled airspace above and around Ben-Gurion. Entry needs ATC clearance.' },
  aip_prohibited: { g: 'Airspace', n: 'Prohibited areas', t: 'Prohibited Area · no-fly', c: '#ff3b30', d: 'Flight is forbidden within the listed heights unless specifically authorised.' },
  aip_restricted: { g: 'Airspace', n: 'Restricted areas', t: 'Restricted Area', c: '#ff8a00', d: 'Entry is limited, usually military use at published times. Check before entering.' },
  aip_danger: { g: 'Airspace', n: 'Danger areas', t: 'Danger Area', c: '#e6b800', d: 'An area with a hazard to aircraft. Entry is allowed, but take care and coordinate where the AIP asks you to.' },
  aip_uas: { z: 9, g: 'Airspace', n: 'No-fly circles (LLU)', t: 'No-fly area (LLU)', c: '#ff2d55', d: 'Small no-fly circle around a sensitive site. Applies to drones, sport aviation and helicopters flying outside published routes.' },
  aip_obst: { z: 9, g: 'Airspace', n: 'Fixed obstacles & balloons', t: 'Fixed obstacle', c: '#8d6e4c', d: 'Permanent hazard such as a tethered balloon. Keep clear.' },
  aip_other: { g: 'Airspace', n: 'Other airspace', t: 'Airspace', c: '#8e8e93' },
  uas_area: { z: 8, g: 'Airspace', n: 'Drone operating areas (by NOTAM)', t: 'Drone (UAS) operating area', c: '#c2185b',
    d: 'Official drone operating area (domestic AIP B-09). It is closed to other traffic only when drone activity is coordinated or published by NOTAM — check the active NOTAMs for the chosen time.' },
  nature_reserve: { z: 9, g: 'Nature', n: 'Nature reserves, parks & nesting sites', t: 'Nature reserve / national park', c: '#2e8b57',
    d: 'Official list (domestic AIP, appendix E): no flight below the listed height above ground. Per the AIP these closures do not apply to non-powered paragliders and hang gliders. The outline comes from OpenStreetMap.' },
  // routes
  cvfr_route: { z: 9.5, g: 'Routes & points', n: 'CVFR routes', t: 'CVFR low-level route', c: '#1e9e55', d: 'Controlled-VFR transport route. Paragliders must stay 1 km to each side and 500 ft above/below.' },
  cvfr_mil: { z: 9.5, g: 'Routes & points', n: 'Military low-level routes', t: 'Military low-level route', c: '#1f6fd1', d: 'Military low-level route. Expect fast military traffic.' },
  vfr_points: { z: 11, g: 'Routes & points', n: 'VFR reporting points', t: 'VFR reporting point', c: '#2fa84f' },
  // NOTAMs
  notam_restr: { g: 'NOTAMs', n: 'Restrictions, firing, exercises', t: 'NOTAM · restriction', c: '#ff3b30' },
  notam_para: { g: 'NOTAMs', n: 'Parachuting', t: 'NOTAM · parachuting', c: '#5ac8fa' },
  notam_uas: { g: 'NOTAMs', n: 'Drone activity', t: 'NOTAM · drones', c: '#ff2d55' },
  notam_obst: { g: 'NOTAMs', n: 'Obstacles, balloons, hazards', t: 'NOTAM · obstacle / hazard', c: '#a2845e' },
  notam_sport: { g: 'NOTAMs', n: 'Sport aviation (bubbles, gliders)', t: 'NOTAM · sport aviation', c: '#e0901a' },
  notam_route: { z: 9, g: 'NOTAMs', n: 'Route changes', t: 'NOTAM · route', c: '#32ade6' },
  notam_airspace: { g: 'NOTAMs', n: 'Airspace changes (CTR, training)', t: 'NOTAM · airspace', c: '#8e44d6' },
  notam_ifr: { g: 'NOTAMs', n: 'Aerodrome & IFR info', t: 'NOTAM · aerodrome / IFR', c: '#8e8e93' },
  custom: { g: 'Your files', n: 'Imported airspace', t: 'Imported airspace', c: '#5e5ce6' },
};
const GROUPS = ['Paragliding sites', 'Sport aviation', 'Airspace', 'Nature', 'Routes & points', 'NOTAMs', 'Your files'];
const CORE = ['aip_ctr', 'aip_atz', 'aip_tma', 'uas_area', 'aip_prohibited', 'aip_restricted', 'aip_danger', 'aip_uas', 'aip_obst', 'custom'];
const SPORT = ['sport_bubble_all', 'sport_bubble_end', 'sport_route_mid', 'sport_route_end', 'sport_route_special'];
const N_SPORT = ['notam_restr', 'notam_para', 'notam_uas', 'notam_obst', 'notam_sport', 'notam_airspace'];
const SITES = ['launch_site', 'landing_site'];
const PROFILES = {
  para: {
    name: 'Paraglider', speed: 35, lo: 0, hi: 6000, when: 'now',
    layers: [...CORE, ...SITES, 'cvfr_route', ...N_SPORT],
    note: 'Free flight (no motor), 0–6,000 ft: takeoffs with their wind directions, landing fields, everything that can stop you at those heights (CTR/ATZ, prohibited, restricted, danger, no-fly circles), active NOTAMs, and the CVFR corridors you must keep 1 km from (zoom in to see them).',
    rules: ['Daylight and VMC only. Default flying days: weekends — from Friday 14:00 (and holiday eves) until dark on Saturday/holidays, unless a site procedure allows weekdays.',
      'Not inside IAF-base CTRs. Stay out of prohibited, restricted and danger areas within their published heights.',
      'Keep 1 km either side of CVFR routes (±500 ft of their altitude) and 5 NM from IFR (ATS) routes.',
      'No flying within 9 km (5 NM) of the borders unless a specific site procedure allows it.',
      'Do not take off when the wind exceeds 30 km/h. Check NOTAMs before every flight.'],
  },
  ppg: {
    name: 'PPG', speed: 45, lo: 0, hi: 4000, when: 'now',
    layers: [...CORE, ...SPORT, ...SITES, 'cvfr_route', 'nature_reserve', ...N_SPORT],
    note: 'Powered paraglider, 0–4,000 ft: the bubbles where you may fly for the chosen day, the sport routes between them, takeoffs and landings, plus everything that restricts you at those heights.',
    rules: ['Fly inside the sport-aviation bubbles; moving between bubbles that do not touch follows procedure B-10.',
      'Cross sport routes only to transit between areas, at about 200 ft AGL — do not fly along them.',
      'Keep 1 km either side of CVFR routes and 5 NM from IFR routes. No flight in IAF-base CTRs.',
      'No flying within 9 km of the borders unless a site procedure allows it. Daylight, VMC.'],
  },
  ul: {
    name: 'Ultralight', speed: 110, lo: 0, hi: 6000, when: 'now',
    layers: [...CORE, ...SPORT, 'cvfr_route', 'vfr_points', 'nature_reserve', ...N_SPORT, 'notam_route'],
    note: 'Ultralight / microlight, 0–6,000 ft: bubbles and sport routes for the chosen day, CVFR routes and reporting points (zoom in), and restrictions at those heights.',
    rules: ['Bubbles: VFR, no flight plan, but take-off approval from the relevant ATC unit. Routes outside bubbles need a flight plan and radio contact.',
      'Sport routes are flown at the published altitudes; dashed legs only with controller approval.'],
  },
  ga: {
    name: 'GA / VFR', speed: 180, lo: 0, hi: null, when: 'today',
    layers: [...CORE, 'aip_other', 'cvfr_route', 'cvfr_mil', 'vfr_points', 'sport_bubble_all', 'sport_bubble_end', 'nature_reserve', ...N_SPORT, 'notam_route', 'notam_ifr'],
    note: 'General aviation: all airspace at every height, CVFR and military routes, reporting points, sport bubbles (traffic) and all operational NOTAMs.',
    rules: ['CVFR routes: max 180 kt unless approved; transponder on (code 5100 unless told otherwise).'],
  },
  uas: { name: 'Drone', speed: 50, lo: 0, hi: 400, when: 'now', layers: ['aip_ctr', 'aip_prohibited', 'aip_restricted', 'aip_danger', 'aip_uas', 'aip_obst', 'nature_reserve', 'notam_uas', 'notam_restr', 'notam_obst', 'notam_airspace', 'custom'], note: 'Drones below 400 ft.', rules: [] },
  custom: { name: 'Custom', speed: 40, lo: 0, hi: null, layers: 'custom', note: 'Your own selection of layers and heights. Any change you make to layers or heights is saved here automatically and kept between visits.', rules: [] },
  all: { name: 'Everything', speed: 100, lo: 0, hi: null, when: 'any', layers: null, note: 'Every layer at every height.', rules: [] },
};

const PICON = {
  para: '<path d="M3 9c3-5 15-5 18 0"/><path d="M4 9l8 9.5L20 9M8.5 9.7 12 18.5l3.5-8.8"/><circle cx="12" cy="20" r="1.4" fill="currentColor"/>',
  ppg: '<path d="M4 6.5c2.8-4 13.2-4 16 0"/><path d="M5 6.5l7 7.5 7-7.5"/><circle cx="12" cy="17.5" r="3.8"/><path d="M12 13.7v7.6M8.2 17.5h7.6"/>',
  ul: '<path d="M2 9.5 12 5l10 4.5L12 11z"/><path d="M12 11v4.5M7.5 19h9M12 15.5 8 19M12 15.5l4 3.5"/><circle cx="7.5" cy="19.6" r="1.3"/><circle cx="16.5" cy="19.6" r="1.3"/>',
  ga: '<path d="M21 15.5v-2l-8-4.8V3.8a1.5 1.5 0 0 0-3 0v4.9l-8 4.8v2l8-2.4v4.8l-2.2 1.6v1.6l3.7-1 3.7 1v-1.6L13 17.9v-4.8z" fill="currentColor" stroke="none"/>',
  uas: '<circle cx="5.5" cy="5.5" r="2.6"/><circle cx="18.5" cy="5.5" r="2.6"/><circle cx="5.5" cy="18.5" r="2.6"/><circle cx="18.5" cy="18.5" r="2.6"/><rect x="9" y="9" width="6" height="6" rx="1.6"/><path d="M7.4 7.4 9 9M16.6 7.4 15 9M7.4 16.6 9 15M16.6 16.6 15 15"/>',
  custom: '<path d="M4 6h9M17 6h3M4 12h3M11 12h9M4 18h11M19 18h1"/><circle cx="15" cy="6" r="2"/><circle cx="9" cy="12" r="2"/><circle cx="17" cy="18" r="2"/>',
  all: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3.3 3 14.7 0 18M12 3c-3 3.3-3 14.7 0 18"/>',
};
const picon = k => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">${PICON[k] || PICON.all}</svg>`;
/* ================================================================ state */
let DATA = { zones: [] }, zones = [], loaded = false;
let prof = store.get('prof', 'para'), when = store.get('when', null), band = store.get('band', null);
let enabled = store.get('layers', null), hidden = new Set(store.get('hidden', []));
let showApprox = store.get('approx', false), theme = store.get('theme', 'auto');
let alt = store.get('alt', 0), altGps = false, pin = null, me = null, follow = false, selected = null;
const sec = { head: store.get('head', 0), cone: store.get('cone', 30), min: store.get('smin', 10), speed: store.get('speed', null), max: store.get('smax', 10000), cursor: null, ahead: [] };
const P = () => PROFILES[prof] || PROFILES.para;
const speedNow = () => sec.speed ?? P().speed;
const secLen = () => Math.min(150, Math.max(2, speedNow() * sec.min / 60));
if (when !== 'at') when = 'now';
if (!enabled) { enabled = {}; Object.keys(META).forEach(k => enabled[k] = Array.isArray(P().layers) ? P().layers.includes(k) : true); }

/* ================================================================ map */
const map = L.map('map', { zoomControl: false, zoomSnap: .5, preferCanvas: true, doubleClickZoom: false, renderer: L.canvas({ tolerance: 8 }) }).setView([31.75, 34.95], 8);
L.control.zoom({ position: 'topright' }).addTo(map);
const mq = matchMedia('(prefers-color-scheme: dark)');
const SAT = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', { maxZoom: 18, attribution: 'Esri, Maxar' });
const OSM = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, attribution: '© OpenStreetMap contributors' }).addTo(map);
function applyStyle(s) {
  theme = s || theme; store.set('theme', theme);
  const night = theme === 'night' || ((theme === 'auto' || theme === 'sat') && mq.matches);
  document.documentElement.dataset.theme = theme === 'day' ? 'day' : night ? 'night' : 'day';
  if (theme === 'auto') delete document.documentElement.dataset.theme;
  if (theme === 'sat') { if (map.hasLayer(OSM)) map.removeLayer(OSM); if (!map.hasLayer(SAT)) SAT.addTo(map); }
  else { if (map.hasLayer(SAT)) map.removeLayer(SAT); if (!map.hasLayer(OSM)) OSM.addTo(map); }
  const pane = OSM.getContainer(); if (pane) { pane.classList.toggle('tiles-dark', theme !== 'sat' && night); pane.classList.toggle('tiles-soft', theme !== 'sat' && !night); }
  $('#map').classList.toggle('sat', theme === 'sat');
  $$('.stylesel button, .stylesel-i').forEach(b => b.classList.toggle('on', b.dataset.s === theme));
  document.querySelector('meta[name=theme-color]')?.setAttribute('content', night ? '#1c1c1e' : '#f2f2f7');
}
OSM.on('load', () => applyStyle());
mq.addEventListener?.('change', () => applyStyle());
const svgR = L.svg({ padding: .3 });
const coneLayer = L.polygon([], { renderer: svgR, color: '#ff3b30', weight: 1.5, dashArray: '2 6', fillColor: '#ff3b30', fillOpacity: .06, interactive: false }).addTo(map);
const cursorMk = L.circleMarker([0, 0], { renderer: svgR, radius: 5, color: '#fff', weight: 2, fillColor: '#ff3b30', fillOpacity: 1, interactive: false });
let pinMk = null, meMk = null, accC = null, groups = {}, shapes = {}, labels = L.layerGroup().addTo(map);

/* ================================================================ geometry helpers */
function inRing(lat, lon, r) { let i = false; for (let k = 0; k < r.length - 1; k++) { const [y1, x1] = r[k], [y2, x2] = r[k + 1]; if ((x1 > lon) !== (x2 > lon) && lat < (y2 - y1) * (lon - x1) / (x2 - x1) + y1) i = !i; } return i; }
function bbox(z) { if (z._bb) return z._bb; let a = 90, b = -90, c = 180, d = -180; for (const [y, x] of z.geom.ring) { if (y < a) a = y; if (y > b) b = y; if (x < c) c = x; if (x > d) d = x; } return z._bb = [a, b, c, d]; }
function inZone(z, lat, lon) { const bb = bbox(z); return lat >= bb[0] && lat <= bb[1] && lon >= bb[2] && lon <= bb[3] && inRing(lat, lon, z.geom.ring); }
function dest(p, hdg, km) { const h = hdg * Math.PI / 180; return [p.lat + km * Math.cos(h) / 111.32, p.lng + km * Math.sin(h) / (111.32 * Math.cos(p.lat * Math.PI / 180))]; }
const isArea = z => z.geom && (z.geom.kind === 'polygon' || z.geom.kind === 'circle');
const fl = z => z.floor_ft ?? 0, ce = z => z.ceil_ft ?? UNL;
const area = z => { const b = bbox(z); return (b[1] - b[0]) * (b[3] - b[2]); };
const meta = z => META[z.layer] || META.aip_other;
const zkey = z => `${z.layer}|${z.id}|${(z.geom?.ring?.[0] || []).join(',')}`;
function fmtAlt(v, ref) {
  if (v == null) return '—'; if (v === 0) return 'GND'; if (v >= UNL) return 'Unlimited'; if (v < 0) return `${(-v).toLocaleString('en-US')} ft below sea level`;
  return v.toLocaleString('en-US') + ' ft' + (ref === 'AGL' ? ' AGL' : ref === 'FL' ? ` (FL${String(Math.round(v / 100)).padStart(3, '0')})` : '');
}
const altShort = (v, ref) => v == null ? '' : v === 0 ? 'GND' : v >= UNL ? 'UNL' : (ref === 'FL' ? 'FL' + Math.round(v / 100) : String(v)) + (ref === 'AGL' ? ' AGL' : '');
const fmtM = v => v == null || v >= UNL || !v ? '' : Math.round(v / FT).toLocaleString('en-US') + ' m';

/* ================================================================ time windows */
const DOW = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
function startOfDay(t) { const d = new Date(t); d.setHours(0, 0, 0, 0); return d.getTime(); }
let atTime = store.get('atTime', null);
function windowNow() {
  if (when === 'at' && atTime) return { a: atTime, b: atTime + 60000, label: fmtT(atTime) };
  const now = Date.now(); return { a: now, b: now + 60000, label: 'now' };
}
function windowDays(w) { if (!w) return null; const s = new Set(); for (let t = startOfDay(w.a); t < w.b; t += DAY) s.add(new Date(t + 3600000).getDay()); return s; }
let WIN = null, WDAYS = null;
function activeIn(z, a, b) {
  if (z.times && z.times.length) return z.times.some(([s, e]) => s * 1000 < b && e * 1000 > a);
  if (z.valid_from) return z.valid_from * 1000 < b && (!z.valid_to || z.valid_to * 1000 > a);
  return true;
}
function nextActive(z) {
  const now = Date.now();
  if (!z.times || !z.times.length) return null;
  const cur = z.times.find(([s, e]) => s * 1000 <= now && e * 1000 > now);
  if (cur) return { now: true, s: cur[0] * 1000, e: cur[1] * 1000 };
  const nx = z.times.find(([s]) => s * 1000 > now);
  return nx ? { now: false, s: nx[0] * 1000, e: nx[1] * 1000 } : null;
}
const fmtT = t => new Date(t).toLocaleString('en-GB', { weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
const fmtH = t => new Date(t).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
function relTime(t) { const m = Math.round((t - Date.now()) / 60000); if (Math.abs(m) < 60) return `${m} min`; const h = Math.round(m / 60); if (Math.abs(h) < 36) return `${h} h`; return `${Math.round(h / 24)} days`; }

/* ================================================================ filtering */
function bandNow() { if (prof === 'custom') return store.get('customBand', null) || band || { lo: 0, hi: null }; return band || { lo: P().lo ?? 0, hi: P().hi ?? null }; }
const fmtBand = b => `${b.lo.toLocaleString('en-US')} – ${b.hi == null ? 'Unlimited' : b.hi.toLocaleString('en-US') + ' ft'}`;
function visible(z, ignoreHidden) {
  if (enabled[z.layer] === false || (!ignoreHidden && hidden.has(zkey(z)))) return false;
  const b = bandNow();
  if (z.layer !== 'launch_site' && z.layer !== 'vfr_points') {
    if (b.hi != null && fl(z) >= b.hi) return false;
    if (b.lo > 0 && ce(z) <= b.lo) return false;
  }
  if (WIN) {
    if (!activeIn(z, WIN.a, WIN.b)) return false;   // NOTAMs: only those active at the chosen moment
    if (z.days && !z.days.some(d => WDAYS.has(d))) return false;
  }
  return true;
}
const drawnArea = z => isArea(z) && (showApprox || !z.geom.approx);
function zonesAtLL(ll) { return zones.filter(z => drawnArea(z) && visible(z) && inZone(z, ll.lat, ll.lng)).sort((a, b) => area(a) - area(b)); }
function relation(z, a) {
  if (a < fl(z)) return { k: 'dn', t: `Starts ${(fl(z) - a).toLocaleString('en-US')} ft above you`, tag: 'Below zone' };
  if (a > ce(z)) return { k: 'up', t: `Ends ${(a - ce(z)).toLocaleString('en-US')} ft below you`, tag: 'Above zone' };
  return { k: 'in', t: `${fmtAlt(fl(z), z.floor_ref)} – ${z.ceil_ft == null && z.layer.startsWith('sport_') ? 'ceiling not printed' : fmtAlt(ce(z), z.ceil_ref)}`, tag: 'Inside' };
}

/* ================================================================ rendering */
const LABELED = new Set(['aip_ctr', 'aip_atz', 'aip_tma', 'aip_prohibited', 'aip_restricted', 'aip_danger', 'sport_bubble_all', 'sport_bubble_end',
  'notam_restr', 'notam_para', 'notam_uas', 'notam_obst', 'notam_sport', 'notam_airspace', 'custom']);
function windRose(z) {
  const R = 13, c = 15, arcs = (z.wind || []).map(([f, t]) => {
    let span = ((t - f) + 360) % 360; if (span === 0) span = 360;
    const p = d => [c + R * Math.sin(d * Math.PI / 180), c - R * Math.cos(d * Math.PI / 180)];
    if (span >= 359) return `<circle cx="${c}" cy="${c}" r="${R}" class="wr"/>`;
    const [x1, y1] = p(f), [x2, y2] = p(f + span);
    return `<path class="wr" d="M${c} ${c}L${x1.toFixed(1)} ${y1.toFixed(1)}A${R} ${R} 0 ${span > 180 ? 1 : 0} 1 ${x2.toFixed(1)} ${y2.toFixed(1)}Z"/>`;
  }).join('');
  return L.divIcon({ className: '', iconSize: [30, 30], iconAnchor: [15, 15], html: `<div class="lsite"><svg viewBox="0 0 30 30"><circle cx="15" cy="15" r="13.5" class="wb"/>${arcs}<circle cx="15" cy="15" r="4.2" class="wc"/></svg></div>` });
}
const landIcon = L.divIcon({ className: '', iconSize: [16, 16], iconAnchor: [8, 8], html: '<div class="lland">L</div>' });
const notamIcon = c => L.divIcon({ className: '', iconSize: [20, 20], iconAnchor: [10, 10], html: `<div class="npin" style="--c:${c}">N</div>` });
let clickZone = null;
function render() {
  WIN = windowNow(); WDAYS = windowDays(WIN);
  Object.values(groups).forEach(g => map.removeLayer(g)); groups = {}; shapes = {}; labels.clearLayers();
  const vis = zones.filter(z => z.geom && visible(z)).sort((a, b) => (isArea(b) ? area(b) : 0) - (isArea(a) ? area(a) : 0));
  for (const z of vis) {
    const m = meta(z), key = z.geom.approx && !showApprox ? 'notam_pins' : z.layer, g = groups[key] || (groups[key] = L.layerGroup());
    let sh;
    if (z.geom.approx && !showApprox && isArea(z)) {
      sh = L.marker(z.geom.center || polyLabelPoint(z), { icon: notamIcon(m.c), keyboard: false, zIndexOffset: 300 });
      sh.on('click', () => { clickZone = z; });
    } else if (z.geom.kind === 'point') {
      sh = z.layer === 'launch_site' ? L.marker(z.geom.ring[0], { icon: windRose(z), keyboard: false, zIndexOffset: 500 })
        : z.layer === 'landing_site' ? L.marker(z.geom.ring[0], { icon: landIcon, keyboard: false })
        : L.circleMarker(z.geom.ring[0], { radius: 3, color: '#fff', weight: 1, fillColor: m.c, fillOpacity: 1 });
      sh.on('click', () => { clickZone = z; });
    } else if (z.geom.kind === 'line') {
      sh = L.polyline(z.geom.ring, { color: m.c, weight: z.layer.startsWith('notam') ? 4 : 2.5, opacity: .85, dashArray: z.approval || z.layer.startsWith('notam') ? '8 6' : null });
      sh.on('click', () => { clickZone = z; });
    } else {
      const bub = z.layer.startsWith('sport_bubble') || z.layer === 'nature_reserve', appr = z.geom.approx || z.layer === 'uas_area', wk = z.layer === 'aip_ctr' && z.days;
      sh = L.polygon(z.geom.ring, { color: m.c, weight: bub ? 1.2 : appr ? 1.2 : 2, dashArray: appr || wk ? '5 5' : z.matched ? '6 3' : null, fillColor: m.c, fillOpacity: bub ? .16 : appr ? .035 : z.matched ? .3 : .12 });
      if (LABELED.has(z.layer) && !appr) {
        const c = z.geom.center || polyLabelPoint(z);
        labels.addLayer(L.marker(c, { interactive: false, keyboard: false, icon: L.divIcon({ className: 'zl', iconSize: null,
          html: `<b>${altShort(ce(z), z.ceil_ref)}</b><span>${altShort(fl(z), z.floor_ref)}</span>`, iconAnchor: [0, 0] }) }));
      }
    }
    sh.addTo(g); shapes[z._k] = sh;
  }
  tiers();
  if (selected != null && shapes[selected]?.setStyle) shapes[selected].setStyle({ weight: 5, fillOpacity: .32 });
  lbl(); buildLayerList(); buildHidden(); syncBand(); update();
}
function tiers() {   // de-clutter: small things appear only when zoomed in
  const zm = map.getZoom();
  for (const [k, g] of Object.entries(groups)) {
    const minz = k === 'notam_pins' ? 8 : (META[k]?.z || 0);
    if (zm >= minz) { if (!map.hasLayer(g)) g.addTo(map); } else if (map.hasLayer(g)) map.removeLayer(g);
  }
}
map.on('zoomend', tiers);
function polyLabelPoint(z) { const b = bbox(z); const c = [(b[0] + b[1]) / 2, (b[2] + b[3]) / 2]; if (inRing(c[0], c[1], z.geom.ring)) return c; const r = z.geom.ring; let la = 0, lo = 0; r.forEach(p => { la += p[0]; lo += p[1]; }); return [la / r.length, lo / r.length]; }
function lbl() { const m = $('#map'), zm = map.getZoom(); m.classList.toggle('nolbl', zm < 10); m.classList.toggle('smallicons', zm < 9.5); }
map.on('zoomend', lbl);
function zoomTo(z) {
  const b = z.geom.kind === 'point' ? [z.geom.ring[0][0] - .02, z.geom.ring[0][0] + .02, z.geom.ring[0][1] - .02, z.geom.ring[0][1] + .02] : bbox(z);
  map.fitBounds([[b[0], b[2]], [b[1], b[3]]], { padding: [70, 70], maxZoom: 14 });
  if (mobile()) setSheet('s0');
}

/* ================================================================ Here tab */
const ICON = {
  warn: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4M12 17h.01"/></svg>',
  ok: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="m8 12.5 2.8 2.8L16 9.5"/></svg>',
  pin: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s7-6.3 7-12a7 7 0 0 0-14 0c0 5.7 7 12 7 12z"/><circle cx="12" cy="10" r="2.5"/></svg>',
};
const point = () => pin || me;
const EYE = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/></svg>', EYEOFF = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3l18 18M10.6 5.1A10 10 0 0 1 12 5c6.4 0 10 7 10 7a17 17 0 0 1-3 3.8M6.4 6.4C3.8 8.1 2 12 2 12s3.6 7 10 7a9.6 9.6 0 0 0 4.4-1"/><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2"/></svg>';
const zrow = (z, sub, tag, cls) => { const off = hidden.has(zkey(z)); return `<div class="zrow${off ? ' off' : ''}" role="button" tabindex="0" data-k="${z._k}"><span class="zbar" style="background:${meta(z).c}"></span><span class="grow"><div class="zname" dir="auto">${esc(z.name)}</div><div class="sub">${off ? 'Hidden · ' : ''}${sub}</div></span>${tag && !off ? `<span class="rel ${cls}">${tag}</span>` : ''}<button class="eye" data-eye="${z._k}" title="${off ? 'Show on map' : 'Hide from map'}" aria-label="${off ? 'Show' : 'Hide'}">${off ? EYEOFF : EYE}</button></div>`; };
function updateHere() {
  const p = point(), b = $('#banner');
  updateNotices();
  if (!p) { b.innerHTML = `<div class="banner gray">${ICON.pin}<div><b>No position yet</b><span>Allow location access, or tap the map to drop a pin.</span></div></div>`; $('#zlist').innerHTML = ''; return; }
  const here = zonesAtLL(p).map(z => ({ z, r: relation(z, alt) })).sort((a, b) => ({ in: 0, up: 1, dn: 2 }[a.r.k] - { in: 0, up: 1, dn: 2 }[b.r.k]) || fl(a.z) - fl(b.z));
  const blocking = here.filter(h => h.r.k === 'in' && !h.z.layer.startsWith('sport_bubble'));
  const inBubble = here.filter(h => h.r.k === 'in' && h.z.layer.startsWith('sport_bubble'));
  const nofly = blocking.filter(h => /aip_prohibited|aip_uas/.test(h.z.layer));
  const where = `${pin ? 'Pin' : 'You'} · ${Math.round(alt).toLocaleString('en-US')} ft${WIN ? ' · ' + WIN.label : ''}`;
  let html;
  if (nofly.length) html = `<div class="banner red">${ICON.warn}<div><b>No-fly zone</b><span>${esc(nofly[0].z.name)} · ${where}</span></div></div>`;
  else if (blocking.length) html = `<div class="banner red">${ICON.warn}<div><b>Inside ${blocking.length} zone${blocking.length > 1 ? 's' : ''}</b><span>${esc(blocking.slice(0, 2).map(h => h.z.name).join(', '))}${blocking.length > 2 ? ` +${blocking.length - 2}` : ''} · ${where}</span></div></div>`;
  else if (sec.ahead.length) { const a0 = sec.ahead[0]; html = `<div class="banner amber">${ICON.warn}<div><b>${esc(a0.z.name)} ahead</b><span>${a0.d1.toFixed(1)} km · about ${Math.max(1, Math.round(a0.d1 / speedNow() * 60))} min at your height · ${where}</span></div></div>`; }
  else if (inBubble.length) html = `<div class="banner green">${ICON.ok}<div><b>Inside ${esc(inBubble[0].z.name)}</b><span>Sport bubble, up to ${fmtAlt(ce(inBubble[0].z))} · ${where}</span></div></div>`;
  else html = `<div class="banner green">${ICON.ok}<div><b>${here.length ? 'Clear at this altitude' : 'No airspace here'}</b><span>${here.length ? `${here.length} zone${here.length > 1 ? 's' : ''} above or below · ` : ''}${where}</span></div></div>`;
  b.innerHTML = html;
  $('#zlist').innerHTML = here.length ? here.map(({ z, r }) => zrow(z, `${esc(meta(z).t)} · ${esc(r.t)}`, r.tag, r.k)).join('') : '<div class="row"><span class="sub">Nothing shown covers this point.</span></div>';
}
function updateNotices() {
  const ns = zones.filter(z => !z.geom && z.source === 'NOTAM' && z.layer !== 'notam_ifr' && enabled[z.layer] !== false && (!WIN || activeIn(z, WIN.a, WIN.b)));
  $('#notices').innerHTML = ns.length ? `<h2>Active NOTAMs without a mapped area</h2><div class="card">${ns.map(z => zrow(z, esc(z.text.slice(0, 90)) + (z.text.length > 90 ? '…' : ''), '', '')).join('')}</div>` : '';
}

/* ================================================================ side view (cone) */
const SV = { w: 340, h: 238, l: 38, r: 8, t: 10, b: 32 };
const DIRS = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];
function rays() {
  if (sec.cone >= 360) return Array.from({ length: 36 }, (_, i) => i * 10);
  const n = Math.max(3, Math.round(sec.cone / 5)); return Array.from({ length: n + 1 }, (_, i) => sec.head - sec.cone / 2 + sec.cone * i / n);
}
function sectionIntervals(p) {
  const L = secLen(), S = 120, R = rays(), out = [];
  const dl = L / 111.32, dn = L / (111.32 * Math.cos(p.lat * Math.PI / 180));
  const cand = zones.filter(z => { if (!drawnArea(z) || !visible(z) || z.layer.startsWith('sport_bubble')) return false; const bb = bbox(z); return !(bb[1] < p.lat - dl || bb[0] > p.lat + dl || bb[3] < p.lng - dn || bb[2] > p.lng + dn); });
  const pts = R.map(h => { const a = []; for (let i = 0; i <= S; i++) a.push(dest(p, h, L * i / S)); return a; });
  for (const z of cand) {
    const bb = bbox(z); let dmin = Infinity, dmax = -1, entry = 0;
    const inb = q => q[0] >= bb[0] && q[0] <= bb[1] && q[1] >= bb[2] && q[1] <= bb[3] && inRing(q[0], q[1], z.geom.ring);
    pts.forEach((ray, ri) => {
      let first = -1, last = -1;
      for (let i = 0; i <= S; i++) if (inb(ray[i])) { if (first < 0) first = i; last = i; }
      if (first >= 0) { const d = L * first / S; if (d < dmin) { dmin = d; entry = R[ri]; } dmax = Math.max(dmax, L * last / S); }
    });
    if (dmax >= 0) out.push({ z, d1: dmin, d2: dmax, hdg: ((entry % 360) + 360) % 360 });
  }
  return out;
}
function wedge(p, L) {
  const n = sec.cone >= 360 ? 72 : Math.max(8, Math.round(sec.cone / 3));
  const R = sec.cone >= 360 ? Array.from({ length: n }, (_, i) => i * 5) : Array.from({ length: n + 1 }, (_, i) => sec.head - sec.cone / 2 + sec.cone * i / n);
  const arc = R.map(h => dest(p, h, L)); return sec.cone >= 360 ? arc : [[p.lat, p.lng], ...arc];
}
function drawSection() {
  const p = point(), svg = $('#sv'); sec.ahead = [];
  const L = secLen(), sp = speedNow();
  $('#sumline').textContent = `${L < 10 ? L.toFixed(1) : Math.round(L)} km · ${sec.min} min ahead at ${sp} km/h`;
  const hh = Math.round(sec.head); $('#hdg').textContent = sec.cone >= 360 ? 'All around' : `${String(hh).padStart(3, '0')}° ${DIRS[Math.round(hh / 45) % 8]}`;
  $('#head').disabled = sec.cone >= 360;
  if (!p) { svg.innerHTML = '<text x="170" y="115" text-anchor="middle" fill="var(--label3)" font-size="13">Waiting for a position…</text>'; coneLayer.setLatLngs([]); updateAhead(); return; }
  coneLayer.setLatLngs(pin ? [] : wedge(p, L));
  const W = SV.w - SV.l - SV.r, H = SV.h - SV.t - SV.b, M = sec.max;
  const xs = d => SV.l + W * d / L, ys = a => SV.t + H * (1 - Math.min(Math.max(a, 0), M) / M);
  const iv = sectionIntervals(p).sort((a, b) => (ce(b.z) - fl(b.z)) - (ce(a.z) - fl(a.z)));
  let s = '';
  const step = M <= 3000 ? 500 : M <= 10000 ? 2000 : 10000;
  for (let a = 0; a <= M; a += step) s += `<line x1="${SV.l}" x2="${SV.w - SV.r}" y1="${ys(a)}" y2="${ys(a)}" stroke="var(--sep)"/><text x="${SV.l - 5}" y="${ys(a) + 3.5}" text-anchor="end" font-size="9.5" fill="var(--label3)">${a >= 1000 ? a / 1000 + 'k' : a}</text>`;
  const kmStep = [1, 2, 5, 10, 20, 25, 50].find(n => L / n <= 6) || 50;
  for (let d = 0; d <= L + .01; d += kmStep) { const an = d === 0 ? 'start' : d + kmStep > L + .01 ? 'end' : 'middle', mi = d / sp * 60;
    s += `<text x="${xs(d)}" y="${SV.h - 18}" text-anchor="${an}" font-size="9.5" fill="var(--label3)">${d} km</text><text x="${xs(d)}" y="${SV.h - 6}" text-anchor="${an}" font-size="8.5" fill="var(--label3)">${d === 0 ? 'now' : (mi < 10 ? mi.toFixed(1) : Math.round(mi)) + ' min'}</text>`; }
  s += `<rect x="${SV.l}" y="${ys(0)}" width="${W}" height="6" fill="var(--label3)" opacity=".35" rx="2"/>`;
  const placed = [];
  iv.forEach(({ z, d1, d2 }) => {
    if (fl(z) >= M) return;
    const x1 = xs(d1), x2 = Math.max(xs(d2), x1 + 2), top = ys(Math.min(ce(z), M)), bot = ys(fl(z)), c = meta(z).c;
    s += `<rect x="${x1}" y="${top}" width="${x2 - x1}" height="${Math.max(bot - top, 1.5)}" fill="${c}" fill-opacity=".28" stroke="${c}" stroke-width="1.5" rx="3"${z.geom.approx ? ' stroke-dasharray="4 3"' : ''}/>`;
    if (ce(z) > M) s += `<path d="M${x1} ${top + 7}l${(x2 - x1) / 2} -7 ${(x2 - x1) / 2} 7" fill="none" stroke="${c}" stroke-width="1.5" opacity=".8"/>`;
    if (x2 - x1 > 46 && bot - top > 13) { const cx = (x1 + x2) / 2, ly = Math.max(top + 11, SV.t + 10), w = Math.min(z.name.length, 22) * 5.2;
      if (!placed.some(q => Math.abs(q.y - ly) < 11 && Math.abs(q.x - cx) < (q.w + w) / 2 + 4)) { placed.push({ x: cx, y: ly, w });
        s += `<text x="${cx}" y="${ly}" text-anchor="middle" font-size="9.5" font-weight="600" fill="var(--label)" stroke="var(--glass-solid)" stroke-width="2.5" paint-order="stroke">${esc(z.name.length > 22 ? z.name.slice(0, 21) + '…' : z.name)}</text>`; } }
  });
  const ay = ys(alt);
  s += `<line x1="${SV.l}" x2="${SV.w - SV.r}" y1="${ay}" y2="${ay}" stroke="var(--blue)" stroke-width="1.4" stroke-dasharray="4 4"/><circle cx="${SV.l}" cy="${ay}" r="6.5" fill="var(--blue)" stroke="#fff" stroke-width="2.5"/>`;
  if (sec.cursor) { const cx = xs(sec.cursor.d), cy = ys(sec.cursor.a); s += `<line x1="${cx}" x2="${cx}" y1="${SV.t}" y2="${ys(0)}" stroke="var(--red)"/><circle cx="${cx}" cy="${cy}" r="4.5" fill="var(--red)" stroke="#fff" stroke-width="1.5"/>`; }
  svg.innerHTML = s; svg._iv = iv; svg._m = { W, H, L };
  sec.ahead = iv.filter(i => i.d1 > .05 && alt >= fl(i.z) && alt <= ce(i.z)).sort((a, b) => a.d1 - b.d1);
  updateAhead();
}
function svInspect(ev) {
  const svg = $('#sv'), m = svg._m, p = point(); if (!m || !p) return;
  const r = svg.getBoundingClientRect(), x = (ev.clientX - r.left) / r.width * SV.w, y = (ev.clientY - r.top) / r.height * SV.h;
  const d = Math.min(Math.max((x - SV.l) / m.W * m.L, 0), m.L), a = Math.min(Math.max((1 - (y - SV.t) / m.H) * sec.max, 0), sec.max);
  sec.cursor = { d, a };
  const hits = svg._iv.filter(i => d >= i.d1 && d <= i.d2 && a >= fl(i.z) && a <= ce(i.z)), near = svg._iv.some(i => d >= i.d1 && d <= i.d2);
  $('#svnote').innerHTML = `<b>${d.toFixed(1)} km · ${(d / speedNow() * 60).toFixed(1)} min · ${Math.round(a / 10) * 10} ft</b> — ` + (hits.length ? 'inside ' + hits.map(h => esc(h.z.name)).join(', ') : near ? 'clear of zones at this height' : 'no zones at this distance');
  if (sec.cone < 360) cursorMk.setLatLng(dest(p, sec.head, d)).addTo(map);
  drawSection();
}
function updateAhead() {
  const el = $('#ahead');
  if (!point() || !sec.ahead.length) { el.innerHTML = '<div class="row"><span class="sub">Nothing ahead at this height.</span></div>'; return; }
  el.innerHTML = sec.ahead.slice(0, 8).map(({ z, d1, hdg }) => zrow(z, `${esc(meta(z).t)} · ${d1.toFixed(1)} km ${DIRS[Math.round(hdg / 45) % 8]} · ${Math.max(1, Math.round(d1 / speedNow() * 60))} min`, 'Ahead', 'up')).join('');
}

/* ================================================================ detail card */
let detailFromSpot = false;
function openDetail(k, at, fromSpot) {
  detailFromSpot = !!fromSpot;
  const z = zones.find(x => x._k == k); if (!z) return;
  if (selected != null && selected !== z._k && shapes[selected]?.setStyle) shapes[selected].setStyle({ weight: 2, fillOpacity: .15 });
  selected = z._k; if (shapes[k]?.setStyle) shapes[k].setStyle({ weight: 5, fillOpacity: .32 });
  const m = meta(z), p = point(), r = p && isArea(z) && inZone(z, p.lat, p.lng) ? relation(z, alt) : null;
  const rows = [];
  if (isArea(z) || z.ceil_ft != null) {
    if (isArea(z)) rows.push(['Floor', `${fmtAlt(fl(z), z.floor_ref)}${fl(z) && fl(z) < UNL ? ' · ' + fmtM(fl(z)) : ''}`]);
    rows.push([z.geom?.kind === 'line' ? 'Route altitude' : 'Ceiling', z.ceil_ft == null && z.layer.startsWith('sport_') ? 'Not printed on the chart' : `${fmtAlt(z.ceil_ft ?? (isArea(z) ? UNL : null), z.ceil_ref)}${z.ceil_ft && z.ceil_ft < UNL ? ' · ' + fmtM(z.ceil_ft) : ''}`]);
  }
  const g = z.geom;
  if (g?.kind === 'circle') rows.push(['Shape', `Circle, radius ${g.radius_m >= 1000 ? (g.radius_m / 1000).toFixed(1) + ' km' : g.radius_m + ' m'}${g.approx ? ' (approximate)' : ''}`]);
  else if (g?.kind === 'polygon') rows.push(['Shape', z.matched ? 'Sport bubble named in this NOTAM (matched by location — check the text)' : `Area${g.approx ? ' (approximate)' : ''}`]);
  else if (g?.kind === 'line') rows.push(['Shape', z.approval ? 'Route · controller approval only' : 'Route']);
  else if (g?.kind === 'point') { rows.push(['Position', `${g.ring[0][0].toFixed(5)}, ${g.ring[0][1].toFixed(5)}`]); if (z.wind_text) rows.push(['Wind', esc(z.wind_text)]); if (z.elev_m) rows.push(['Elevation', `${z.elev_m} m`]); }
  else rows.push(['Shape', z.area_note || 'Whole country / no map shape']);
  if (z.days) rows.push(['Days', z.days.length === 7 ? 'Every day' : z.days.map(d => DOW[d]).join(' · ')]);
  let timeHtml = '';
  if (z.source === 'NOTAM') {
    const na = nextActive(z);
    rows.unshift(['In force', z.times?.length ? z.times.filter(([s, e]) => e * 1000 > Date.now()).slice(0, 4).map(([s, e]) => `${fmtT(s * 1000)}–${fmtH(e * 1000)}`).join(' · ') + (z.times.length > 4 ? ' …' : '') : 'See validity below']);
    rows.push(['Valid', `${z.valid_from ? fmtT(z.valid_from * 1000) : '—'} → ${z.valid_to ? fmtT(z.valid_to * 1000) + (z.est ? ' (est.)' : '') : 'permanent'}`]);
    if (z.schedule) rows.push(['Schedule (UTC)', esc(z.schedule)]);
    timeHtml = na ? (na.now ? `<div class="chipline on">● Active now — until ${fmtH(na.e)}</div>` : `<div class="chipline">Next active ${fmtT(na.s)} – ${fmtH(na.e)} (in ${relTime(na.s)})</div>`) : '<div class="chipline">No active period in the next 2 weeks</div>';
    const up = (z.times || []).filter(([s, e]) => e * 1000 > Date.now()).slice(0, 6);
    if (up.length > 1) timeHtml += `<div class="sub" style="margin:4px 2px 10px">Upcoming: ${up.map(([s, e]) => `${fmtT(s * 1000)}–${fmtH(e * 1000)}`).join(' · ')}</div>`;
  }
  if (z.effective) rows.unshift(['In force', esc(z.effective)]);
  if (z.purpose?.length) rows.unshift(['Purpose', esc(z.purpose.join(' · '))]);
  if (z.contact) rows.push(['Coordinate with', esc(z.contact)]);
  if (z.source?.startsWith('eAIP') && z.text) rows.push(['Activity (AIP)', esc(z.text)]);
  rows.push(['Source', esc(z.source)]);
  rows.push(['Accuracy', z.source === 'OpenStreetMap' ? 'Community data (OpenStreetMap) — check with the local club'
    : /chart/.test(z.source) ? 'Traced from the official AIP chart (about ±0.4 km)'
    : z.layer === 'nature_reserve' ? 'Height limit official (AIP appendix E); outline from OpenStreetMap'
    : z.area_note ? z.area_note : 'Official published coordinates']);
  const others = (at ? zonesAtLL(at) : []).filter(o => o._k !== z._k).slice(0, 8);
  const M = Math.max(ce(z) >= UNL ? 20000 : ce(z), 2000) * 1.1, pct = a => 100 - Math.min(a, M) / M * 100;
  const tower = isArea(z) ? `<div class="tower"><i style="top:${pct(Math.min(ce(z), M))}%;bottom:${100 - pct(fl(z))}%;background:${m.c}"></i>${p ? `<i style="top:${pct(alt)}%;height:3px;background:var(--blue)"></i>` : ''}</div>` : '';
  const text = z.source?.startsWith('eAIP') || /appendix B/.test(z.text || '') ? '' : z.text;
  $('#dbody').innerHTML = `<div class="dtype" style="color:${m.c}">${esc(m.t)}</div><div class="dname" dir="auto">${esc(z.name)}</div>
    ${m.d ? `<div class="sub" style="margin:-6px 0 12px;font-size:14px">${esc(m.d)}</div>` : ''}${timeHtml}
    ${r ? `<div class="banner ${r.k === 'in' ? 'red' : r.k === 'up' ? 'amber' : 'green'}" style="margin-bottom:14px"><div><b>${r.tag}</b><span>At ${Math.round(alt).toLocaleString('en-US')} ft · ${esc(r.t)}</span></div></div>` : ''}
    <div class="vr">${tower}<dl class="kv">${rows.map(([a, b]) => `<dt>${a}</dt><dd>${b}</dd>`).join('')}</dl></div>
    ${text ? `<h2>Details</h2><div class="card"><div class="txt" dir="auto">${esc(text)}</div></div>` : ''}
    ${z.desc_he ? `<h2>AIP description</h2><div class="card"><div class="txt" dir="rtl" lang="he">${esc(z.desc_he)}</div></div><div class="sub" style="margin:4px 4px 0">From the domestic AIP, chapter A-17 (Hebrew).</div>` : ''}
    ${z.raw ? `<details class="raw"${z.source === 'NOTAM' ? '' : ''}><summary>${z.source === 'NOTAM' ? 'Original NOTAM' : 'Original AIP data (raw)'}</summary><pre dir="auto">${esc(z.raw)}</pre></details>` : ''}
    ${others.length ? `<h2>Also at this spot</h2><div class="card">${others.map(o => zrow(o, `${esc(meta(o).t)} · ${fmtAlt(fl(o), o.floor_ref)} – ${fmtAlt(ce(o), o.ceil_ref)}`, '', '')).join('')}</div>` : ''}
    <div class="btnrow">${z.geom ? '<button class="btn" id="dzoom">Zoom to it</button>' : ''}<button class="btn sec" id="dhide">Hide it</button></div>
    <div class="note">Double-click or long-press a zone on the map to zoom to it. Hidden items can be restored under Layers.</div>`;
  $('#dzoom') && ($('#dzoom').onclick = () => zoomTo(z));
  $('#dhide').onclick = () => { hidden.add(zkey(z)); store.set('hidden', [...hidden]); closeOverlay('#detail'); toast('Hidden. Restore it under Layers.'); render(); };
  openOverlay('#detail'); $('#dbody').scrollTop = 0;
}
const sheetEl = $('#sheet'); sheetEl.addEventListener('scroll', () => { if (sheetEl.scrollTop) sheetEl.scrollTop = 0; });   // the panel itself must never scroll
function openOverlay(id) { sheetEl.scrollTop = 0; if ($('#sheet').classList.contains('collapsed')) setCollapsed(false); $(id).classList.add('on'); if (mobile() && ['s0', 's1'].includes(curState())) setSheet('s2'); }
function closeOverlay(id) {
  $(id).classList.remove('on');
  if (id === '#detail') { const s = selected; selected = null; if (s != null && shapes[s]?.setStyle) shapes[s].setStyle({ weight: 2, fillOpacity: .15 }); }
}

/* ================================================================ spot summary (tap on the map) */
const GROUPS_AT = [
  ['No-fly & restricted', ['aip_prohibited', 'aip_uas', 'aip_restricted', 'aip_danger', 'aip_obst']],
  ['Controlled airspace', ['aip_ctr', 'aip_atz', 'aip_tma', 'aip_other']],
  ['Drone operating areas', ['uas_area']],
  ['Active NOTAMs', ['notam_restr', 'notam_para', 'notam_uas', 'notam_obst', 'notam_sport', 'notam_airspace', 'notam_route', 'notam_ifr']],
  ['Nature reserves', ['nature_reserve']],
  ['Sport aviation', ['sport_bubble_all', 'sport_bubble_end']],
  ['Your files', ['custom']]];
function distM(a, b) { const dx = (a[1] - b[1]) * 111320 * Math.cos(a[0] * Math.PI / 180), dy = (a[0] - b[0]) * 111320; return Math.hypot(dx, dy); }
function distToLine(p, ring) { let best = Infinity; for (let i = 0; i < ring.length - 1; i++) { const a = ring[i], b = ring[i + 1];
  const kx = 111320 * Math.cos(p[0] * Math.PI / 180), ky = 111320, ax = (a[1] - p[1]) * kx, ay = (a[0] - p[0]) * ky, bx = (b[1] - p[1]) * kx, by = (b[0] - p[0]) * ky;
  const dx = bx - ax, dy = by - ay, t = Math.max(0, Math.min(1, -(ax * dx + ay * dy) / ((dx * dx + dy * dy) || 1))); best = Math.min(best, Math.hypot(ax + t * dx, ay + t * dy)); } return best; }
let lastSpot = null;
function openSpot(ll, tapped) {
  lastSpot = { ll, tapped };
  const p = [ll.lat, ll.lng], inside = zones.filter(z => isArea(z) && visible(z, true) && inZone(z, ll.lat, ll.lng)).sort((a, b) => fl(a) - fl(b));
  const near = zones.filter(z => visible(z, true) && z.geom && (z.geom.kind === 'point' || z.geom.kind === 'line'))
    .map(z => ({ z, d: z.geom.kind === 'point' ? distM(p, z.geom.ring[0]) : distToLine(p, z.geom.ring) }))
    .filter(o => o.d < (o.z.geom.kind === 'point' ? 2500 : 1500)).sort((a, b) => a.d - b.d).slice(0, 8);
  const b = bandNow(), blocking = inside.filter(z => !hidden.has(zkey(z)) && !z.layer.startsWith('sport_bubble') && !z.geom.approx);
  const nofly = blocking.filter(z => /aip_prohibited|aip_uas/.test(z.layer));
  const row = (z, sub) => zrow(z, sub, '', '');
  const hdr = tapped && tapped.geom.kind === 'point' ? `<div class="dtype" style="color:${meta(tapped).c}">${esc(meta(tapped).t)}</div><div class="spothead" dir="auto">${esc(tapped.name)}</div>${tapped.wind_text ? `<div class="sub">Works in wind ${esc(tapped.wind_text)}</div>` : ''}`
    : `<div class="dtype" style="color:var(--blue)">This spot</div><div class="spothead">${ll.lat.toFixed(4)}, ${ll.lng.toFixed(4)}</div>`;
  let html = hdr + `<div class="sub" style="margin:4px 0 12px">${WIN.label === 'now' ? 'Right now' : 'At ' + WIN.label} · heights ${fmtBand(b)} · ${esc(P().name)} profile</div>`;
  html += nofly.length ? `<div class="banner red">${ICON.warn}<div><b>No-fly zone</b><span>${esc(nofly.map(z => z.name).join(', '))}</span></div></div>`
    : blocking.length ? `<div class="banner amber">${ICON.warn}<div><b>${blocking.length} restriction${blocking.length > 1 ? 's' : ''} here</b><span>Check the heights below</span></div></div>`
    : `<div class="banner green">${ICON.ok}<div><b>No restrictions here</b><span>Nothing in your layers covers this spot at ${fmtBand(b)}</span></div></div>`;
  for (const [title, layers] of GROUPS_AT) {
    const zs = inside.filter(z => layers.includes(z.layer)); if (!zs.length) continue;
    html += `<div class="grp">${title}</div><div class="card">${zs.map(z => row(z, `${esc(meta(z).t)} · ${fmtAlt(fl(z), z.floor_ref)} – ${z.ceil_ft == null && z.layer.startsWith('sport_') ? 'ceiling not printed' : fmtAlt(ce(z), z.ceil_ref)}${z.geom.approx ? ' · approximate area' : ''}`)).join('')}</div>`;
  }
  if (near.length) html += `<div class="grp">Nearby</div><div class="card">${near.map(({ z, d }) => row(z, `${esc(meta(z).t)} · ${d < 1000 ? Math.round(d / 10) * 10 + ' m' : (d / 1000).toFixed(1) + ' km'} away${z.layer === 'cvfr_route' && d < 1000 ? ' · paragliders keep 1 km clear' : ''}${z.wind_text ? ' · wind ' + esc(z.wind_text) : ''}`)).join('')}</div>`;
  html += '<div class="note">Tap any line for full details. Only layers you have switched on, and NOTAMs active at the chosen time, are listed.</div>';
  $('#spotbody').innerHTML = html;
  closeOverlay('#detail'); openOverlay('#spot');
}

/* ================================================================ search */
let placeTimer = null, placeHits = [], placeQ = '';
function doSearch(q, keepPlaces) {
  const raw = q.trim(), ql = raw.toLowerCase(), el = $('#results');
  if (ql.length < 2) { el.innerHTML = '<div class="note">Search a zone code (LLP27, LLR24), a NOTAM number (C2221), a takeoff (Tavor, Gilboa), an airfield, or any place name in Hebrew or English (מצדה, Zikhron Yaakov).</div>'; return; }
  const hits = zones.filter(z => (z.name + ' ' + z.id + ' ' + (z.text || '') + ' ' + (z.location || '') + ' ' + (z.desc_he || '')).toLowerCase().includes(ql)).slice(0, 60);
  const places = placeQ === raw ? placeHits : [];
  hits.sort((a, b) => (b.name.toLowerCase().startsWith(ql) - a.name.toLowerCase().startsWith(ql)) || (/site/.test(b.layer) - /site/.test(a.layer)));
  el.innerHTML = (hits.length ? `<div class="grp">Airspace & sites</div><div class="card">${hits.map(z => zrow(z, `${esc(meta(z).t)}${!hidden.has(zkey(z)) && !visible(z) ? ' · not in current layers / time' : ''}`, '', '')).join('')}</div>` : '')
    + (places.length ? `<div class="grp">Places</div><div class="card">${places.map((p, i) => `<div class="zrow" role="button" tabindex="0" data-place="${i}"><span class="zbar" style="background:var(--blue)"></span><span class="grow"><div class="zname" dir="auto">${esc(p.name)}</div><div class="sub" dir="auto">${esc(p.sub)}</div></span><span class="chev">›</span></div>`).join('')}</div>` : '')
    + (!hits.length && !places.length ? `<div class="note">${placeQ === raw ? 'No matches.' : 'Searching places…'}</div>` : '')
    + (places.length ? '<div class="note">Place search © OpenStreetMap contributors (Nominatim).</div>' : '');
  $$('#results [data-place]').forEach(r => r.onclick = () => { const p = places[+r.dataset.place]; closeOverlay('#search'); const ll = L.latLng(p.lat, p.lon); map.setView(ll, 13); setPin(ll); openSpot(ll); });
  if (!keepPlaces && raw.length >= 3 && placeQ !== raw) {
    clearTimeout(placeTimer);
    placeTimer = setTimeout(async () => {
      try {
        const r = await fetch(`https://nominatim.openstreetmap.org/search?format=jsonv2&limit=6&countrycodes=il,ps&accept-language=en,he&q=${encodeURIComponent(raw)}`);
        const js = await r.json();
        placeHits = js.map(p => ({ name: p.name || p.display_name.split(',')[0], sub: p.display_name.split(',').slice(1, 3).join(',').trim() || p.type, lat: +p.lat, lon: +p.lon }));
      } catch { placeHits = []; }
      placeQ = raw; if ($('#q2').value.trim() === raw) doSearch(raw, true);
    }, 650);
  }
}

/* ================================================================ layers / profiles / sources */
function buildLayerList() {
  const cnt = {}; zones.forEach(z => { cnt[z.layer] = (cnt[z.layer] || 0) + 1; });
  const vcnt = {}; zones.forEach(z => { if (z.geom && visible(z)) vcnt[z.layer] = (vcnt[z.layer] || 0) + 1; });
  $('#layerlist').innerHTML = GROUPS.map(g => {
    const rows = Object.entries(META).filter(([k, m]) => m.g === g && cnt[k]); if (!rows.length) return '';
    return `<h2>${g}</h2><div class="card">${rows.map(([k, m]) => `<label class="row"><span class="dot" style="background:${m.c}"></span><span class="grow"><div>${m.n}</div><div class="sub">${enabled[k] !== false ? `${vcnt[k] || 0} of ${cnt[k]} shown` : `${cnt[k]} available`}</div></span><input class="sw" type="checkbox" data-k="${k}" ${enabled[k] !== false ? 'checked' : ''}></label>`).join('')}</div>`;
  }).join('');
  $$('#layerlist input').forEach(i => i.onchange = () => { toCustom(); enabled[i.dataset.k] = i.checked; saveCustom(); render(); });
}
function buildHidden() {
  const hz = zones.filter(z => hidden.has(zkey(z)));
  $('#hiddenlist').innerHTML = hz.length ? `<h2>Hidden (${hz.length})</h2><div class="card">${hz.map(z => `<div class="row"><span class="dot" style="background:${meta(z).c}"></span><span class="grow"><div dir="auto">${esc(z.name)}</div><div class="sub">${esc(meta(z).t)}</div></span><button class="pill" data-u="${z._k}">Restore</button></div>`).join('')}</div>` : '';
  $$('#hiddenlist [data-u]').forEach(b => b.onclick = () => { const z = zones.find(x => x._k == b.dataset.u); hidden.delete(zkey(z)); store.set('hidden', [...hidden]); render(); });
}
function buildProfiles() {
  $('#tbProfileName').textContent = P().name; $('#profname').textContent = P().name;
  $('#tbProfile svg').outerHTML = picon(prof);
  $('#profnote').textContent = P().note;
  $('#rules').innerHTML = P().rules.map(r => `<li>${esc(r)}</li>`).join('') + (P().rules.length ? '<li class="src">Summary of the domestic AIP (procedures B-08 / B-10). The AIP text governs.</li>' : '');
}
function applyProfile(p) {
  prof = p; store.set('prof', p);
  if (p === 'custom') { enabled = { ...(store.get('customLayers', null) || enabled) }; band = store.get('customBand', null); }
  else { enabled = {}; Object.keys(META).forEach(k => enabled[k] = Array.isArray(P().layers) ? P().layers.includes(k) : true); band = null; }
  store.set('layers', enabled); store.set('band', band); sec.speed = null; store.set('speed', null); syncSpeed();
  buildProfiles(); render();
}
function setWhen(w, quiet) {
  when = w; store.set('when', w);
  if (w === 'at' && (!atTime || atTime < Date.now() - 3600000)) setAt(Date.now() + 3 * 3600000, true);
  timeLabel();
  if (!quiet && loaded) render();
}
const toLocalInput = t => { const d = new Date(t - new Date(t).getTimezoneOffset() * 60000); return d.toISOString().slice(0, 16); };
function setAt(t, quiet) { atTime = Math.round(t / 60000) * 60000; store.set('atTime', atTime); when = 'at'; store.set('when', 'at'); timeLabel(); if (!quiet) render(); }
function timeLabel() { const l = $('#tbTimeLabel'); l.textContent = when === 'at' && atTime ? new Date(atTime).toLocaleString('en-GB', { weekday: 'short', hour: '2-digit', minute: '2-digit' }) : 'Now'; $('#tbTime').classList.toggle('plan', when === 'at'); }
function nextDow(dow, hour) { const d = new Date(); d.setHours(hour, 0, 0, 0); let add = (dow - d.getDay() + 7) % 7; if (add === 0 && d.getTime() < Date.now()) add = 7; return d.getTime() + add * DAY; }
function syncBand() { const b = bandNow(); $('#blo').value = b.lo; $('#bhi').value = b.hi == null ? 20500 : b.hi; $('#bandv').textContent = fmtBand(b); }
function setBand(lo, hi) { if (hi != null && hi <= lo) hi = Math.min(lo + 500, 20000); toCustom(); band = { lo, hi }; saveCustom(); render(); }
function toCustom() { if (prof === 'custom') return; band = bandNow(); prof = 'custom'; store.set('prof', prof); buildProfiles(); toast('Switched to Custom — your changes are remembered'); }
function saveCustom() { store.set('layers', enabled); store.set('band', band); store.set('customLayers', enabled); store.set('customBand', band); }
function buildSources() {
  const s = DATA.sources || {}, names = { notam: 'NOTAMs (IAA)', eaip: 'eAIP (CTR, TMA, P/R/D)', domestic: 'Domestic AIP (tables & charts)', custom: 'Your server files' };
  const age = DATA.generated ? Date.now() / 1000 - DATA.generated : null;
  $('#sources').innerHTML = `<div class="row"><span class="grow"><div>Built</div><div class="sub">${DATA.generated ? fmtT(DATA.generated * 1000) + ` (${relTime(DATA.generated * 1000).replace('-', '')} ago)` : '—'}</div></span></div>` +
    Object.entries(s).map(([k, v]) => `<div class="row"><span class="dot" style="background:${v.ok ? 'var(--green)' : 'var(--red)'}"></span><span class="grow"><div>${names[k] || k}</div><div class="sub" dir="auto">${esc(v.msg)}</div></span></div>`).join('') +
    `<div class="row"><span class="grow sub">AIRAC ${esc(DATA.airac || '—')} · domestic AIP ${esc(DATA.domestic_aip || '—')}</span></div>`;
  const stale = age != null && age > 6 * 3600, bad = Object.values(s).some(v => !v.ok);
  const t = DATA.generated ? new Date(DATA.generated * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '—';
  $('#stat').textContent = (bad ? '⚠︎ ' : '') + (stale ? 'Data ' + relTime(DATA.generated * 1000).replace('-', '') + ' old' : 'Updated ' + t);
  $('#stat').classList.toggle('warn', bad || stale);
}

/* ================================================================ position */
function setPin(ll) {
  pin = { lat: ll.lat, lng: ll.lng };
  if (!pinMk) pinMk = L.marker(ll, { icon: L.divIcon({ className: '', html: '<div class="pin"></div>', iconSize: [22, 22], iconAnchor: [11, 11] }), interactive: false, zIndexOffset: 800 }).addTo(map); else pinMk.setLatLng(ll);
  sec.cursor = null; cursorMk.remove(); update();
}
function clearPin() { pin = null; if (pinMk) { pinMk.remove(); pinMk = null; } sec.cursor = null; cursorMk.remove(); update(); }
function update() { drawSection(); updateHere(); }
function startGeo() {
  if (!navigator.geolocation) return;
  navigator.geolocation.watchPosition(p => {
    const first = !me; me = { lat: p.coords.latitude, lng: p.coords.longitude, alt: p.coords.altitude, hdg: p.coords.heading, spd: p.coords.speed };
    const ll = [me.lat, me.lng];
    if (!meMk) { meMk = L.marker(ll, { icon: L.divIcon({ className: '', html: '<div class="me"></div>', iconSize: [18, 18], iconAnchor: [9, 9] }), interactive: false, zIndexOffset: 900 }).addTo(map);
      accC = L.circle(ll, { renderer: svgR, radius: p.coords.accuracy, color: '#007aff', weight: 1, fillOpacity: .08, interactive: false }).addTo(map); }
    else { meMk.setLatLng(ll); accC.setLatLng(ll).setRadius(p.coords.accuracy); }
    if (first && !pin) map.setView(ll, 11);
    if (follow) map.panTo(ll, { animate: true });
    if (altGps && me.alt != null) setAlt(me.alt * FT, true);
    if (me.hdg != null && !isNaN(me.hdg) && (me.spd || 0) > 2 && sec.cone < 360) { sec.head = Math.round(me.hdg); $('#head').value = sec.head; }
    if (!pin) update();
  }, () => { if (!me) toast('Location is off — tap the map to drop a pin.'); }, { enableHighAccuracy: true, maximumAge: 5000 });
}
function setAlt(v, fromGps) { alt = Math.max(0, Math.round(v)); store.set('alt', alt); $('#alt').value = Math.min(alt, 12000); $('#altv').textContent = alt.toLocaleString('en-US'); $('#altm').textContent = Math.round(alt / FT).toLocaleString('en-US') + ' m'; if (!fromGps) altGps = false; update(); }
function syncSpeed() { $('#spd').value = speedNow(); $('#spdv').textContent = speedNow(); }

/* ================================================================ data */
function customZones() { return (store.get('custom', []) || []).map(z => ({ ...z, layer: 'custom', source: z.source || 'Your file' })); }
async function load(refresh) {
  try {
    const r = await fetch('data.json', { cache: 'no-cache' }); DATA = await r.json();
  } catch (e) { toast('Could not load data — showing what is cached.'); }
  zones = (DATA.zones || []).concat(customZones()); zones.forEach((z, i) => z._k = i);
  buildSources();
  if (!loaded) { loaded = true; buildProfiles(); }
  render();
  if (refresh) toast(`Updated · ${zones.length} items`);
}

/* ================================================================ exports */
const CLS = { aip_ctr: 'CTR', aip_tma: 'C', aip_prohibited: 'P', aip_restricted: 'R', aip_danger: 'Q', aip_uas: 'P', sport_bubble_all: 'W', sport_bubble_end: 'W', notam_restr: 'R', notam_para: 'Q', notam_uas: 'R', notam_obst: 'Q', notam_sport: 'W', notam_airspace: 'R' };
const kmlColor = hex => { const h = hex.replace('#', ''); return h.slice(4, 6) + h.slice(2, 4) + h.slice(0, 2); };
function exportZones() { return zones.filter(z => z.geom && visible(z)); }
function toKML(zs) {
  const used = [...new Set(zs.map(z => z.layer))];
  let k = '<?xml version="1.0" encoding="UTF-8"?>\n<kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>Israel airspace</name>';
  used.forEach(l => { const c = kmlColor((META[l] || META.aip_other).c); k += `<Style id="${l}"><LineStyle><color>ff${c}</color><width>2</width></LineStyle><PolyStyle><color>40${c}</color></PolyStyle><IconStyle><color>ff${c}</color></IconStyle></Style>`; });
  used.forEach(l => {
    k += `<Folder><name>${esc((META[l] || META.aip_other).n)}</name>`;
    zs.filter(z => z.layer === l).forEach(z => {
      const co = z.geom.ring.map(([a, b]) => `${b},${a},0`).join(' ');
      const shape = z.geom.kind === 'point' ? `<Point><coordinates>${co}</coordinates></Point>` : z.geom.kind === 'line' ? `<LineString><tessellate>1</tessellate><coordinates>${co}</coordinates></LineString>`
        : `<Polygon><outerBoundaryIs><LinearRing><coordinates>${co}</coordinates></LinearRing></outerBoundaryIs></Polygon>`;
      const desc = `${meta(z).t}\n${fmtAlt(fl(z), z.floor_ref)} – ${fmtAlt(ce(z), z.ceil_ref)}\n${z.text || ''}`;
      k += `<Placemark><name>${esc(z.name)}</name><styleUrl>#${l}</styleUrl><description>${esc(desc)}</description>${shape}</Placemark>`;
    });
    k += '</Folder>';
  });
  return k + '</Document></kml>';
}
function oaDMS(v, lat) { const a = Math.abs(v); let d = Math.floor(a), m = Math.floor((a - d) * 60), s = Math.round(((a - d) * 60 - m) * 60); if (s === 60) { s = 0; m++; } if (m === 60) { m = 0; d++; }
  return `${String(d).padStart(lat ? 2 : 3, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')} ${lat ? (v >= 0 ? 'N' : 'S') : (v >= 0 ? 'E' : 'W')}`; }
const oaAlt = (v, ref) => v == null ? null : v === 0 ? 'GND' : v >= UNL ? 'UNL' : ref === 'FL' ? `FL${Math.round(v / 100)}` : `${v}ft ${ref === 'AGL' ? 'AGL' : 'AMSL'}`;
const ascii = s => String(s).normalize('NFKD').replace(/[^\x20-\x7e]/g, '').replace(/\s+/g, ' ').trim();
function toOpenAir(zs) {
  let o = `* Israel airspace — exported ${new Date().toISOString()}\n* Informational only. Verify against the official AIP and NOTAMs.\n`;
  zs.filter(isArea).forEach(z => {
    const nm = ascii(z.name) || `${meta(z).t} ${z.id}`.trim();
    o += `\nAC ${CLS[z.layer] || 'R'}\nAN ${ascii(nm) || 'Zone'}${z.source === 'NOTAM' ? '' : ''}\nAL ${oaAlt(fl(z), z.floor_ref) || 'GND'}\nAH ${oaAlt(ce(z), z.ceil_ref) || 'UNL'}\n`;
    if (z.geom.kind === 'circle' && z.geom.center) o += `V X=${oaDMS(z.geom.center[0], true)} ${oaDMS(z.geom.center[1], false)}\nDC ${(z.geom.radius_m / 1852).toFixed(2)}\n`;
    else z.geom.ring.slice(0, -1).forEach(([a, b]) => { o += `DP ${oaDMS(a, true)} ${oaDMS(b, false)}\n`; });
  });
  return o;
}
function toGeoJSON(zs) {
  return JSON.stringify({ type: 'FeatureCollection', features: zs.map(z => ({ type: 'Feature',
    properties: { name: z.name, id: z.id, type: meta(z).t, layer: z.layer, floor_ft: z.floor_ft, ceil_ft: z.ceil_ft, floor_ref: z.floor_ref, ceil_ref: z.ceil_ref, text: z.text, source: z.source, days: z.days, valid_from: z.valid_from, valid_to: z.valid_to },
    geometry: z.geom.kind === 'point' ? { type: 'Point', coordinates: [z.geom.ring[0][1], z.geom.ring[0][0]] } : z.geom.kind === 'line' ? { type: 'LineString', coordinates: z.geom.ring.map(([a, b]) => [b, a]) } : { type: 'Polygon', coordinates: [z.geom.ring.map(([a, b]) => [b, a])] } })) });
}
const CRC = (() => { const t = new Uint32Array(256); for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; } return b => { let c = 0xffffffff; for (const x of b) c = t[(c ^ x) & 255] ^ (c >>> 8); return (c ^ 0xffffffff) >>> 0; }; })();
function zip1(name, text) {  // single-file ZIP, stored (no compression)
  const enc = new TextEncoder(), data = enc.encode(text), fn = enc.encode(name), crc = CRC(data), n = data.length;
  const lh = new DataView(new ArrayBuffer(30)); lh.setUint32(0, 0x04034b50, true); lh.setUint16(4, 20, true); lh.setUint32(14, crc, true); lh.setUint32(18, n, true); lh.setUint32(22, n, true); lh.setUint16(26, fn.length, true);
  const ch = new DataView(new ArrayBuffer(46)); ch.setUint32(0, 0x02014b50, true); ch.setUint16(4, 20, true); ch.setUint16(6, 20, true); ch.setUint32(16, crc, true); ch.setUint32(20, n, true); ch.setUint32(24, n, true); ch.setUint16(28, fn.length, true);
  const off = 30 + fn.length + n, cdl = 46 + fn.length;
  const end = new DataView(new ArrayBuffer(22)); end.setUint32(0, 0x06054b50, true); end.setUint16(8, 1, true); end.setUint16(10, 1, true); end.setUint32(12, cdl, true); end.setUint32(16, off, true);
  return new Blob([lh, fn, data, ch, fn, end], { type: 'application/vnd.google-earth.kmz' });
}
function download(name, blob) { const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name; document.body.appendChild(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1500); }
function doExport(fmt) {
  const zs = exportZones(), stamp = new Date().toISOString().slice(0, 10), base = `israel-airspace-${P().name.toLowerCase().replace(/\W+/g, '-')}-${stamp}`;
  if (!zs.length) return toast('Nothing to export with the current filters.');
  if (fmt === 'kml') download(base + '.kml', new Blob([toKML(zs)], { type: 'application/vnd.google-earth.kml+xml' }));
  if (fmt === 'kmz') download(base + '.kmz', zip1('doc.kml', toKML(zs)));
  if (fmt === 'txt') download(base + '-openair.txt', new Blob([toOpenAir(zs)], { type: 'text/plain' }));
  if (fmt === 'geojson') download(base + '.geojson', new Blob([toGeoJSON(zs)], { type: 'application/geo+json' }));
}
function exportNote() { const zs = exportZones(), a = zs.filter(isArea).length; $('#exportnote').textContent = `${zs.length} items match your profile, heights and day filter (${a} areas). OpenAir carries areas only; KML / GeoJSON also carry routes and points.`; }

/* ================================================================ custom import (client-side) */
function parseOpenAir(text, src) {
  const out = []; let cur = null, ctr = null;
  const dms = s => { const m = s.trim().match(/(\d+):(\d+)(?::(\d+(?:\.\d+)?))?\s*([NSEW])/); if (!m) return null; const v = +m[1] + m[2] / 60 + (m[3] ? m[3] / 3600 : 0); return /[SW]/.test(m[4]) ? -v : v; };
  const pt = s => { const m = s.match(/(\d+:\d+(?::[\d.]+)?\s*[NS])\s*,?\s*(\d+:\d+(?::[\d.]+)?\s*[EW])/); return m ? [dms(m[1]), dms(m[2])] : null; };
  const alt = s => { s = (s || '').toUpperCase(); if (/GND|SFC/.test(s)) return [0, 'GND']; if (/UNL/.test(s)) return [UNL, 'UNL']; let m = s.match(/FL\s*(\d+)/); if (m) return [+m[1] * 100, 'FL']; m = s.match(/(\d+)\s*(F|FT|M)?/); return m ? [Math.round(+m[1] * (m[2] === 'M' ? FT : 1)), /AGL|SFC/.test(s) ? 'AGL' : 'AMSL'] : [null, null]; };
  const flush = () => { if (cur && cur.ring.length > 2) { if (cur.ring[0] + '' !== cur.ring[cur.ring.length - 1] + '') cur.ring.push(cur.ring[0]); out.push({ id: cur.name, name: cur.name, floor_ft: cur.lo[0], floor_ref: cur.lo[1], ceil_ft: cur.hi[0], ceil_ref: cur.hi[1], text: `Class ${cur.cls}`, source: src, geom: cur.circle || { kind: 'polygon', ring: cur.ring } }); } cur = null; };
  for (const raw of text.split(/\r?\n/)) {
    const ln = raw.replace(/\*.*/, '').trim(); if (!ln) continue; const k = ln.slice(0, 2).toUpperCase(), v = ln.slice(2).trim();
    if (k === 'AC') { flush(); cur = { cls: v, name: 'Zone', lo: [0, 'GND'], hi: [UNL, 'UNL'], ring: [] }; continue; }
    if (!cur) continue;
    if (k === 'AN') cur.name = v; else if (k === 'AL') cur.lo = alt(v); else if (k === 'AH') cur.hi = alt(v);
    else if (k === 'V ' || ln.startsWith('V')) { const m = ln.match(/X\s*=\s*(.*)/); if (m) ctr = pt(m[1]); }
    else if (k === 'DP') { const p = pt(v); if (p) cur.ring.push(p); }
    else if (k === 'DC' && ctr) { const r = +v * 1852; const ring = []; for (let i = 0; i <= 48; i++) { const b = i / 48 * 2 * Math.PI; ring.push([ctr[0] + r * Math.cos(b) / 111320, ctr[1] + r * Math.sin(b) / (111320 * Math.cos(ctr[0] * Math.PI / 180))]); } cur.ring = ring; cur.circle = { kind: 'circle', center: ctr, radius_m: Math.round(r), ring }; }
  }
  flush(); return out;
}
function parseGeoJSON(text, src) {
  const out = [], j = JSON.parse(text);
  (j.features || []).forEach(f => { const g = f.geometry || {}, p = f.properties || {}; const nm = p.name || p.NAME || 'Zone';
    const polys = g.type === 'Polygon' ? [g.coordinates] : g.type === 'MultiPolygon' ? g.coordinates : [];
    polys.forEach(c => out.push({ id: nm, name: nm, floor_ft: p.floor_ft ?? 0, ceil_ft: p.ceil_ft ?? null, text: p.description || '', source: src, geom: { kind: 'polygon', ring: c[0].map(([x, y]) => [y, x]) } }));
    if (g.type === 'LineString') out.push({ id: nm, name: nm, source: src, text: '', geom: { kind: 'line', ring: g.coordinates.map(([x, y]) => [y, x]) } });
    if (g.type === 'Point') out.push({ id: nm, name: nm, source: src, text: '', geom: { kind: 'point', ring: [[g.coordinates[1], g.coordinates[0]]] } }); });
  return out;
}
function parseKML(text, src) {
  const out = [], doc = new DOMParser().parseFromString(text, 'application/xml');
  doc.querySelectorAll('Placemark').forEach(pm => { const nm = pm.querySelector('name')?.textContent?.trim() || 'Zone';
    pm.querySelectorAll('coordinates').forEach(c => { const ring = c.textContent.trim().split(/\s+/).map(t => t.split(',').map(Number)).filter(a => a.length >= 2).map(([x, y]) => [y, x]);
      if (ring.length >= 3) out.push({ id: nm, name: nm, floor_ft: 0, ceil_ft: null, text: pm.querySelector('description')?.textContent || '', source: src, geom: { kind: 'polygon', ring } }); }); });
  return out;
}

/* ================================================================ wiring */
function setSheet(s) { const sh = $('#sheet'); sh.classList.remove('s0', 's1', 's2', 's3'); sh.classList.add(s); store.set('sheet', s); setTimeout(() => map.invalidateSize(), 320); }
const mobile = () => innerWidth <= 760;
const STATES = ['s0', 's2', 's3'];
const curState = () => STATES.find(s => $('#sheet').classList.contains(s)) || 's2';
$('#grab').onclick = () => {   // tap the tab: collapse fully / open again
  if (!mobile()) return setCollapsed(true);
  setSheet(curState() === 's0' ? 's2' : 's0');
};
(() => {   // swipe the handle: down = show more map, up = show more panel
  let y0 = null; const g = $('#grab');
  g.addEventListener('touchstart', e => { y0 = e.touches[0].clientY; }, { passive: true });
  g.addEventListener('touchend', e => { if (y0 == null) return; const dy = e.changedTouches[0].clientY - y0; y0 = null; const sh = $('#sheet');
    const i = STATES.indexOf(curState()); if (dy > 30) setSheet(STATES[Math.max(0, i - 1)]); else if (dy < -30) setSheet(STATES[Math.min(3, i + 1)]); });
})();
$$('.overlay .bar').forEach(b => { const m = document.createElement('button'); m.className = 'back mapbtn'; m.innerHTML = 'Map <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"/></svg>';
  m.onclick = () => { if (mobile()) setSheet('s0'); else setCollapsed(true); }; b.appendChild(m); });
$$('#tabs button').forEach(b => b.onclick = () => { $$('#tabs button').forEach(x => x.classList.toggle('on', x === b)); $$('.pane').forEach(p => p.classList.toggle('on', p.id === 'p-' + b.dataset.t)); closeOverlay('#detail'); if (b.dataset.t === 'export') exportNote(); });
$$('[data-close]').forEach(b => b.onclick = () => { const id = b.closest('.overlay').id; closeOverlay('#' + id); if (id === 'detail' && detailFromSpot && lastSpot) openOverlay('#spot'); else if (id === 'spot') clearPinIfNoGps(); if (id === 'search') { $('#q2').value = ''; $('#q2').blur(); } });
function clearPinIfNoGps() { /* keep the pin so the Here tab still works */ }
function toggleHidden(k) {
  const z = zones.find(x => x._k == k); if (!z) return; const key = zkey(z);
  if (hidden.has(key)) { hidden.delete(key); toast('Shown on the map'); } else { hidden.add(key); toast('Hidden — tap the eye again to show it'); }
  store.set('hidden', [...hidden]); render(); refreshLists();
}
function refreshLists() {
  if ($('#spot').classList.contains('on') && lastSpot) { const st = $('#spotbody').scrollTop; openSpot(lastSpot.ll, lastSpot.tapped); $('#spotbody').scrollTop = st; }
  if ($('#search').classList.contains('on')) doSearch($('#q2').value, true);
}
document.addEventListener('click', e => {
  const eye = e.target.closest('[data-eye]'); if (eye) { e.stopPropagation(); e.preventDefault(); toggleHidden(eye.dataset.eye); return; }
  const row = e.target.closest('.zrow'); if (!row || !row.dataset.k) return;
  if (row.closest('#spotbody')) return openDetail(row.dataset.k, lastSpot?.ll, true);
  if (row.closest('#results')) { const z = zones.find(x => x._k == row.dataset.k); openDetail(row.dataset.k); if (z?.geom) zoomTo(z); return; }
  if (row.closest('#dbody')) return openDetail(row.dataset.k, null, detailFromSpot);
  openDetail(row.dataset.k, pin ? L.latLng(pin) : me ? L.latLng(me.lat, me.lng) : null);
});
document.addEventListener('keydown', e => { if (e.key === 'Enter' && e.target.classList?.contains('zrow')) e.target.click(); });
function openSearch() {   // the search field lives in the search card's own bar, so nothing can overlap it
  openPanel(); openOverlay('#search'); const q = $('#q2'); doSearch(q.value);
  q.focus(); setTimeout(() => q.focus(), 80);
}
$('#q').addEventListener('click', openSearch);
$('#q').addEventListener('focus', e => { e.target.blur(); openSearch(); });
$('#q2').oninput = e => doSearch(e.target.value);
$('#q2').addEventListener('keydown', e => { if (e.key === 'Escape') closeOverlay('#search'); });
$('#stat').onclick = () => { $$('#tabs button')[1].click(); setTimeout(() => $('#sources').scrollIntoView({ block: 'center' }), 50); };
$('#upd').onclick = async () => {
  const b = $('#upd'); b.classList.add('spin');
  try { const r = await fetch('api/refresh', { method: 'POST' }); if (!r.ok) throw 0; } catch { /* static hosting: just reload data.json */ }
  await load(true); b.classList.remove('spin');
};
$('#loc').onclick = () => {
  if (!me) return toast('Waiting for GPS…');
  if (pin) clearPin();
  follow = !follow; $('#loc').classList.toggle('on', follow);
  map.setView([me.lat, me.lng], Math.max(map.getZoom(), 12)); toast(follow ? 'Following your position' : 'Stopped following');
};
$('#clearPin').onclick = () => { clearPin(); if (me) map.setView([me.lat, me.lng], Math.max(map.getZoom(), 11)); };
map.on('dragstart', () => { if (follow) { follow = false; $('#loc').classList.remove('on'); } });

// tap = details, double-click / long-press = zoom to zone, tap on empty map = pin
const lp = { t: null, pos: null, fired: false };
function topZoneAt(ll) { const c = clickZone; clickZone = null; return c || zonesAtLL(ll)[0] || null; }
map.on('click', e => {
  if (lp.fired) { lp.fired = false; clickZone = null; return; }
  const tapped = clickZone; clickZone = null;
  if (!tapped || tapped.geom?.kind !== 'point') setPin(e.latlng);
  openSpot(tapped && tapped.geom?.kind === 'point' ? L.latLng(tapped.geom.ring[0][0], tapped.geom.ring[0][1]) : e.latlng, tapped);
});
map.on('dblclick', e => { const z = topZoneAt(e.latlng); if (z) zoomTo(z); else map.setZoomAround(e.latlng, map.getZoom() + 1); });
const mc = map.getContainer();
mc.addEventListener('pointerdown', e => { if (e.target.closest('.leaflet-control')) return; lp.pos = { x: e.clientX, y: e.clientY }; lp.fired = false; clearTimeout(lp.t);
  lp.t = setTimeout(() => { const z = zonesAtLL(map.mouseEventToLatLng(e))[0]; if (z) { lp.fired = true; zoomTo(z); if (navigator.vibrate) navigator.vibrate(15); } }, 600); });
mc.addEventListener('pointermove', e => { if (lp.t && lp.pos && Math.hypot(e.clientX - lp.pos.x, e.clientY - lp.pos.y) > 8) { clearTimeout(lp.t); lp.t = null; } });
['pointerup', 'pointercancel'].forEach(t => mc.addEventListener(t, () => { clearTimeout(lp.t); lp.t = null; }));
mc.addEventListener('contextmenu', e => e.preventDefault());

$('#alt').oninput = e => setAlt(+e.target.value);
$('#altGnd').onclick = () => setAlt(0);
$('#altGps').onclick = () => { if (me?.alt != null) { altGps = true; setAlt(me.alt * FT, true); toast('Following GPS altitude'); } else toast('GPS altitude not available on this device — use the slider.'); };
$('#head').oninput = e => { sec.head = +e.target.value; store.set('head', sec.head); sec.cursor = null; cursorMk.remove(); update(); };
$('#hdgGps').onclick = () => { if (me?.hdg != null && !isNaN(me.hdg)) { sec.head = Math.round(me.hdg); $('#head').value = sec.head; update(); } else toast('Heading is available once you are moving.'); };
const segBind = (sel, get, set) => { const upd = () => $$(sel + ' button').forEach(b => b.classList.toggle('on', +b.dataset.v === get())); $$(sel + ' button').forEach(b => b.onclick = () => { set(+b.dataset.v); upd(); sec.cursor = null; cursorMk.remove(); update(); }); upd(); };
segBind('#scone', () => sec.cone, v => { sec.cone = v; store.set('cone', v); });
segBind('#smin', () => sec.min, v => { sec.min = v; store.set('smin', v); });
segBind('#smax', () => sec.max, v => { sec.max = v; store.set('smax', v); });
$('#spd').oninput = e => { sec.speed = +e.target.value; store.set('speed', sec.speed); $('#spdv').textContent = sec.speed; update(); };
$('#spdAuto').onclick = () => { sec.speed = null; store.set('speed', null); syncSpeed(); update(); };
$('#sv').addEventListener('pointerdown', e => { svInspect(e); $('#sv').setPointerCapture(e.pointerId); $('#sv').onpointermove = svInspect; });
$('#sv').addEventListener('pointerup', () => { $('#sv').onpointermove = null; });
$('#blo').oninput = e => { const hi = +$('#bhi').value; setBand(+e.target.value, hi >= 20500 ? null : hi); };
$('#bhi').oninput = e => setBand(+$('#blo').value, +e.target.value >= 20500 ? null : +e.target.value);
$('#bandReset').onclick = () => { band = null; store.set('band', null); if (prof === 'custom') store.set('customBand', null); render(); };
$$('.stylesel button').forEach(b => b.onclick = () => applyStyle(b.dataset.s));
function setCollapsed(c) { $('#sheet').classList.toggle('collapsed', c); document.body.classList.toggle('panel-hidden', c); store.set('collapsed', c); setTimeout(() => map.invalidateSize(), 320); }

/* ---------------- toolbar + menus */
function openPanel(tab) {
  if (mobile()) { if (curState() === 's0') setSheet('s2'); } else setCollapsed(false);
  if (tab) { ['#search', '#spot', '#detail'].forEach(id => $(id).classList.contains('on') && closeOverlay(id)); const b = $(`#tabs [data-t=${tab}]`); if (b) b.click(); }
}
const menu = $('#menu');
function showMenu(anchor, title, items) {   // items: [{label, sub, on, icon, act}] or {html}
  menu.innerHTML = `<div class="mtitle">${title}</div>` + items.map((it, i) => it.html ? it.html : `<button class="mi${it.on ? ' on' : ''}" data-i="${i}" role="menuitemradio">${it.icon || ''}<span>${esc(it.label)}${it.sub ? `<small>${esc(it.sub)}</small>` : ''}</span><i>✓</i></button>`).join('');
  $$('#menu [data-i]').forEach(b => b.onclick = e => { e.stopPropagation(); closeMenu(); items[+b.dataset.i].act(); });
  const r = anchor.getBoundingClientRect(), w = Math.min(260, innerWidth - 16);
  menu.style.width = w + 'px'; menu.style.left = Math.max(8, Math.min(innerWidth - w - 8, r.left + r.width / 2 - w / 2)) + 'px';
  menu.style.bottom = (innerHeight - r.top + 10) + 'px'; menu.classList.add('on');
}
function closeMenu() { menu.classList.remove('on'); }
document.addEventListener('click', e => { if (!e.target.closest('#menu,#toolbar')) closeMenu(); });
$('#tbProfile').onclick = e => { e.stopPropagation(); if (menu.classList.contains('on') && menu.dataset.k === 'p') return closeMenu(); menu.dataset.k = 'p';
  showMenu($('#tbProfile'), 'Profile', Object.entries(PROFILES).map(([k, v]) => ({ icon: picon(k), label: v.name, sub: v.lo != null && v.hi != null ? `${v.lo.toLocaleString('en-US')}–${v.hi.toLocaleString('en-US')} ft` : k === 'custom' ? 'your own layers & heights' : 'all heights', on: k === prof, act: () => applyProfile(k) })));
};
$('#tbTime').onclick = e => { e.stopPropagation(); if (menu.classList.contains('on') && menu.dataset.k === 't') return closeMenu(); menu.dataset.k = 't';
  const d = new Date(), tom = (d.setHours(9, 0, 0, 0), d.getTime() + DAY);
  showMenu($('#tbTime'), 'Show airspace for', [
    { label: 'Now', sub: 'live, updates every minute', on: when === 'now', act: () => setWhen('now') },
    { label: 'In 3 hours', on: false, act: () => setAt(Date.now() + 3 * 3600000) },
    { label: 'Tomorrow 09:00', on: false, act: () => setAt(tom) },
    { label: 'Friday 10:00', on: false, act: () => setAt(nextDow(5, 10)) },
    { label: 'Saturday 10:00', on: false, act: () => setAt(nextDow(6, 10)) },
    { html: `<label class="mi pick"><span>Pick date &amp; time<small>${when === 'at' && atTime ? 'now set to ' + esc(fmtT(atTime)) : 'plan up to a month ahead'}</small></span></label><div class="pickwrap"><input type="datetime-local" id="planAt" value="${toLocalInput(atTime || Date.now() + 3 * 3600000)}"></div>` }]);
  $('#planAt').onchange = ev => { const t = new Date(ev.target.value).getTime(); if (!isNaN(t)) { setAt(t); closeMenu(); } };
};
$('#tbSearch').onclick = () => { closeMenu(); if (panelOpen() && $('#search').classList.contains('on')) { closeOverlay('#search'); return closePanel(); } openSearch(); };
const panelOpen = () => mobile() ? curState() !== 's0' : !$('#sheet').classList.contains('collapsed');
function closePanel() { if (mobile()) setSheet('s0'); else setCollapsed(true); }
$('#tbLayers').onclick = () => { closeMenu(); if (panelOpen() && $('#tabs .on')?.dataset.t === 'layers' && !$('.overlay.on')) return closePanel(); openPanel('layers'); };

$$('[data-x]').forEach(b => b.onclick = () => doExport(b.dataset.x));
$('#cust').onchange = async e => {
  const f = e.target.files[0]; if (!f) return; const t = await f.text(), ext = f.name.split('.').pop().toLowerCase();
  try {
    const zs = ext === 'kml' ? parseKML(t, f.name) : (ext === 'geojson' || ext === 'json') ? parseGeoJSON(t, f.name) : parseOpenAir(t, f.name);
    const all = (store.get('custom', []) || []).filter(z => z.source !== f.name).concat(zs); store.set('custom', all);
    $('#custst').textContent = `Imported ${zs.length} items from ${f.name}.`; enabled.custom = true; load();
  } catch (err) { $('#custst').textContent = 'Could not read that file: ' + err.message; }
};
setInterval(() => { if (document.visibilityState === 'visible') load(); }, 5 * 60000);
setInterval(() => { if (loaded && when === 'now') render(); }, 60000);   // NOTAM windows roll over
if ('serviceWorker' in navigator && (location.protocol === 'https:' || location.hostname === 'localhost' || location.hostname === '127.0.0.1')) navigator.serviceWorker.register('sw.js').catch(() => { });

applyStyle(theme); setCollapsed(!mobile() && store.get('collapsed', false)); if (mobile()) setSheet(store.get('sheet', 's0') === 's3' ? 's2' : (store.get('sheet', 's0') === 's1' ? 's0' : store.get('sheet', 's0')));
timeLabel();
$('#head').value = sec.head; syncSpeed(); setAlt(alt, true); setWhen(when, true); buildProfiles(); drawSection(); startGeo(); load();
