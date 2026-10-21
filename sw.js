// Offline support: app shell cache-first, data network-first, map tiles cache-first (bounded).
const SHELL = 'shell-v1', DATA = 'data-v1', TILES = 'tiles-v1', MAX_TILES = 3000;
const ASSETS = ['./', './index.html', './app.js', './style.css', './manifest.webmanifest', './icon.svg',
  'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css', 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js'];
self.addEventListener('install', e => { e.waitUntil(caches.open(SHELL).then(c => c.addAll(ASSETS)).then(() => self.skipWaiting())); });
self.addEventListener('activate', e => { e.waitUntil(self.clients.claim()); });
async function trim(cache) { const keys = await cache.keys(); for (let i = 0; i < keys.length - MAX_TILES; i++) await cache.delete(keys[i]); }
self.addEventListener('fetch', e => {
  const u = new URL(e.request.url);
  if (e.request.method !== 'GET' || u.pathname.startsWith('/api/')) return;
  if (u.pathname.endsWith('/data.json')) {
    e.respondWith(fetch(e.request).then(r => { const c = r.clone(); caches.open(DATA).then(x => x.put(e.request, c)); return r; })
      .catch(() => caches.match(e.request)));
    return;
  }
  if (/tile\.openstreetmap\.org|arcgisonline\.com/.test(u.host)) {
    e.respondWith(caches.open(TILES).then(async c => { const hit = await c.match(e.request); if (hit) return hit;
      const r = await fetch(e.request); if (r.ok || r.type === 'opaque') { c.put(e.request, r.clone()); trim(c); } return r; }));
    return;
  }
  if (u.origin === location.origin) {   // own files: network first, so updates arrive; cache when offline
    e.respondWith(fetch(e.request).then(r => { if (r.ok) { const c = r.clone(); caches.open(SHELL).then(x => x.put(e.request, c)); } return r; })
      .catch(() => caches.match(e.request).then(h => h || caches.match('./index.html'))));
    return;
  }
  e.respondWith(caches.match(e.request).then(hit => hit || fetch(e.request)));
});
