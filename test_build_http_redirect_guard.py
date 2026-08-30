from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
import urllib.request

from build_http_redirect_guard import NO_REDIRECT_OPENER, RedirectDenied

hits = {'source': 0, 'target': 0}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/source':
            hits['source'] += 1
            self.send_response(302)
            self.send_header('Location', '/target')
            self.end_headers()
            return
        if self.path == '/target':
            hits['target'] += 1
            body = b'should-never-be-fetched'
            self.send_response(200)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, format, *args):
        return


server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
thread = Thread(target=server.serve_forever, daemon=True)
thread.start()
try:
    url = f'http://127.0.0.1:{server.server_port}/source'
    request = urllib.request.Request(url)
    try:
        NO_REDIRECT_OPENER.open(request, timeout=2)
    except RedirectDenied as exc:
        if exc.code != 302:
            raise SystemExit(f'BUILD_HTTP_REDIRECT_GUARD_FAILED wrong status: {exc.code}')
    else:
        raise SystemExit('BUILD_HTTP_REDIRECT_GUARD_FAILED redirect was not rejected')
finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)

if hits != {'source': 1, 'target': 0}:
    raise SystemExit(f'BUILD_HTTP_REDIRECT_GUARD_FAILED unexpected network hits: {hits}')

print('BUILD_HTTP_REDIRECT_GUARD_OK: source-hit=1; redirect-target-hit=0; denial=pre-follow')
