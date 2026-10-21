#!/usr/bin/env python3
"""Run the map locally with automatic data refresh.

  python3 serve.py                 # http://localhost:8765  (this computer)
  python3 serve.py --lan           # also reachable from your phone on the same Wi-Fi (no GPS: browsers need HTTPS)
  python3 serve.py --cert c.pem --key k.pem --lan   # HTTPS, e.g. certificates made with `mkcert` -> GPS works on the phone
Options: --port N, --every MINUTES (default 10)
"""
import argparse, json, os, socket, ssl, threading, time, traceback
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import update

ROOT = os.path.dirname(os.path.abspath(__file__)); WEB = os.path.join(ROOT, 'web')
lock = threading.Lock(); status = {'running': False, 'last': None, 'error': None}


def run_update(force=False):
    if not lock.acquire(blocking=False): return False
    try:
        status.update(running=True); update.main(force=force); status.update(last=time.time(), error=None); return True
    except Exception as e:
        traceback.print_exc(); status.update(error=str(e)); return False
    finally:
        status.update(running=False); lock.release()


class H(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k): super().__init__(*a, directory=WEB, **k)

    def end_headers(self):
        if self.path.split('?')[0].endswith(('.json', '.js', '.html', '/', '.css', '.webmanifest')): self.send_header('Cache-Control', 'no-cache')
        super().end_headers()

    def _json(self, code, obj):
        b = json.dumps(obj).encode(); self.send_response(code); self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(b))); self.end_headers(); self.wfile.write(b)

    def do_GET(self):
        if self.path.startswith('/api/status'): return self._json(200, status)
        return super().do_GET()

    def do_POST(self):
        if self.path.startswith('/api/refresh'):
            ok = run_update() if not status['running'] else (lock.acquire() and (lock.release() or True))
            return self._json(200 if ok else 500, status)
        self._json(404, {})

    def log_message(self, *a): pass


def loop(every):
    while True:
        time.sleep(every * 60); run_update()


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--port', type=int, default=8765); ap.add_argument('--lan', action='store_true')
    ap.add_argument('--every', type=float, default=10); ap.add_argument('--cert'); ap.add_argument('--key'); a = ap.parse_args()
    if not os.path.exists(os.path.join(WEB, 'data.json')): print('First run: collecting data (the domestic AIP PDF is ~95 MB)…'); run_update()
    else: threading.Thread(target=run_update, daemon=True).start()
    threading.Thread(target=loop, args=(a.every,), daemon=True).start()
    srv = ThreadingHTTPServer(('0.0.0.0' if a.lan else '127.0.0.1', a.port), H)
    scheme = 'http'
    if a.cert:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); ctx.load_cert_chain(a.cert, a.key); srv.socket = ctx.wrap_socket(srv.socket, server_side=True); scheme = 'https'
    print(f'Open {scheme}://localhost:{a.port}')
    if a.lan:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(('8.8.8.8', 80)); print(f'On your phone (same Wi-Fi): {scheme}://{s.getsockname()[0]}:{a.port}')
        except OSError: pass
    srv.serve_forever()
