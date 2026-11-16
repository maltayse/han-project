#!/usr/bin/env python3
"""Run: python3 observer.py --open. Stop: Ctrl-C."""
import argparse
import json
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from collector import Collector


def allowed(host, origin, port):
    expected = {f'127.0.0.1:{port}', f'localhost:{port}'}
    return host in expected and (not origin or origin in {f'http://{h}' for h in expected})


def handler_for(collector):
    lock = threading.Lock()
    cached = [0, None]

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            if not allowed(self.headers.get('Host'), self.headers.get('Origin'), self.server.server_port):
                self.send_error(403)
                return
            if self.path == '/api/snapshot':
                with lock:
                    if time.monotonic() - cached[0] > 1:
                        try:
                            cached[1] = collector.snapshot()
                            cached[0] = time.monotonic()
                        except Exception:
                            self.send_error(500, 'Collection failed; retry to retain the previous view')
                            return
                    body = json.dumps(cached[1], ensure_ascii=False).encode()
                mime = 'application/json; charset=utf-8'
            elif self.path in ('/', '/index.html', '/classic', '/office.js', '/office.css'):
                filename = {'/':'index.html', '/classic':'classic.html'}.get(self.path, self.path[1:])
                body = Path(__file__).with_name(filename).read_bytes()
                mime = ('text/javascript' if filename.endswith('.js') else 'text/css' if filename.endswith('.css') else 'text/html') + '; charset=utf-8'
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; img-src 'self' data:; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
            self.end_headers()
            self.wfile.write(body)
    return Handler


def main():
    p = argparse.ArgumentParser(description='Local read-only Claude Code agent dashboard')
    p.add_argument('--port', type=int, default=8765)
    p.add_argument('--claude-dir', type=Path, default=Path.home()/'.claude')
    p.add_argument('--open', action='store_true')
    p.add_argument('--demo', action='store_true', help='Show synthetic data without reading any Claude files')
    args = p.parse_args()
    if args.demo:
        from demo import DemoCollector
        collector = DemoCollector()
    else:
        collector = Collector(args.claude_dir)
    handler = handler_for(collector)
    try:
        server = ThreadingHTTPServer(('127.0.0.1', args.port), handler)
    except OSError:
        server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
    url = f'http://127.0.0.1:{server.server_port}'
    print(f'Claude Observer → {url}\nRead-only · local machine only · Ctrl-C to stop', flush=True)
    if args.demo:
        print('DEMO: synthetic sessions only. No Claude files or paid model calls.', flush=True)
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
