// Live-traffic relay for the hosted (GitHub Pages) app — Cloudflare Workers, free tier.
// Deploy: dash.cloudflare.com → Workers & Pages → Create → "Hello World" worker → paste this file → Deploy.
// Then paste the worker URL (https://<name>.<you>.workers.dev) into the app: More → Live traffic → Traffic relay URL.
// Relays ADS-B only (adsb.fi, fallback adsb.lol). FLARM/OGN gliders & paragliders need serve.py (long-lived APRS stream).
const SOURCES = ['https://opendata.adsb.fi/api/v2/lat/31.6/lon/35.0/dist/250', 'https://api.adsb.lol/v2/lat/31.6/lon/35.0/dist/250'];
const CAT = { A1: 'light', A2: 'plane', A3: 'plane', A4: 'plane', A5: 'plane', A6: 'jet', A7: 'helicopter', B1: 'glider', B2: 'balloon', B3: 'skydiver', B4: 'ultralight', B6: 'drone' };
const ALLOW = '*';   // or 'https://brook46.github.io' to restrict

export default {
  async fetch(request, env, ctx) {
    if (request.method === 'OPTIONS') return new Response(null, { headers: { 'Access-Control-Allow-Origin': ALLOW, 'Access-Control-Allow-Methods': 'GET' } });
    const cache = caches.default, key = new Request('https://cache.local/traffic');
    let hit = await cache.match(key);
    if (!hit) {
      let out = null, from = null, err = null;
      for (const u of SOURCES) {
        try {
          const r = await fetch(u, { headers: { 'User-Agent': 'IsraelAirspaceMap/1.0 relay' } });
          if (!r.ok) throw new Error('HTTP ' + r.status);
          const d = await r.json();
          out = (d.aircraft || d.ac || []).filter(a => a.lat != null && a.lat >= 29.3 && a.lat <= 33.6 && a.lon >= 33.9 && a.lon <= 36.3).map(a => ({
            id: 'icao-' + a.hex, cs: (a.flight || '').trim() || a.r || a.hex, reg: a.r, model: a.desc || a.t, kind: CAT[a.category] || 'plane',
            lat: a.lat, lon: a.lon, alt_ft: a.alt_baro === 'ground' ? 0 : a.alt_baro, gnd: a.alt_baro === 'ground', alt_geo_ft: a.alt_geom,
            gs_kt: a.gs, trk: a.track, vs_fpm: a.baro_rate ?? a.geom_rate, squawk: a.squawk, age: a.seen_pos || 0, src: 'ADS-B' }));
          from = new URL(u).host; break;
        } catch (e) { err = String(e); }
      }
      const body = JSON.stringify({ t: Math.floor(Date.now() / 1000), items: out || [],
        sources: { adsb: { ok: !!out, from, msg: out ? `${out.length} aircraft` : err }, ogn: { ok: false, msg: 'not available through the relay' } } });
      hit = new Response(body, { headers: { 'Content-Type': 'application/json', 'Cache-Control': 'max-age=8' } });
      ctx.waitUntil(cache.put(key, hit.clone()));
    }
    const res = new Response(hit.body, hit);
    res.headers.set('Access-Control-Allow-Origin', ALLOW);
    return res;
  },
};
