"""Local-only Google login server. Run: python 電影.py (see companion guide)."""
import json
import os
import secrets
import time
from pathlib import Path
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, unquote

BASE = Path(__file__).resolve().parent
PAGE = '영화_B_수정본2.html'
CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '142731366349-8j19n5cgjthpdklti7rtasb1brrc3eod.apps.googleusercontent.com').strip()
ORIGIN = 'http://localhost:8000'
SESSIONS = {}
NONCES = {}

class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Never log credentials or cookies.

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer-when-downgrade')
        self.send_header('Cross-Origin-Opener-Policy', 'same-origin-allow-popups')
        super().end_headers()

    def cookie(self, name):
        try:
            cookies = SimpleCookie(self.headers.get('Cookie', ''))
            return cookies[name].value if name in cookies else ''
        except Exception:
            return ''

    def reply(self, status, data, cookie=None):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        if cookie:
            self.send_header('Set-Cookie', cookie)
        self.end_headers()
        self.wfile.write(body)

    def valid_host(self):
        return self.headers.get('Host') == 'localhost:8000'

    def do_GET(self):
        if not self.valid_host():
            return self.reply(403, {'error': 'http://localhost:8000 주소로 접속해 주세요.'})
        now = time.time()
        for collection in (SESSIONS, NONCES):
            for key, value in list(collection.items()):
                if value['expires'] < now:
                    collection.pop(key, None)
        path = unquote(urlsplit(self.path).path)
        if path in ('/', '/' + PAGE, '/영화_B_수정본_2.html'):
            body = (BASE / PAGE).read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            return self.wfile.write(body)
        if path == '/auth/config':
            if not CLIENT_ID.endswith('.apps.googleusercontent.com'):
                return self.reply(503, {'error': '구글 클라이언트 ID를 먼저 설정해 주세요. 함께 제공된 로그인 안내를 확인하세요.'})
            nonce = secrets.token_urlsafe(32)
            key = secrets.token_urlsafe(32)
            NONCES[key] = {'nonce': nonce, 'expires': now + 1800}
            return self.reply(200, {'clientId': CLIENT_ID, 'nonce': nonce},
                'movie_nonce=' + key + '; HttpOnly; SameSite=Strict; Path=/auth; Max-Age=1800')
        if path == '/auth/session':
            session = SESSIONS.get(self.cookie('movie_session'))
            return self.reply(200, {'user': session['user'] if session else None})
        return self.reply(404, {'error': '페이지를 찾을 수 없습니다.'})

    def do_POST(self):
        if not self.valid_host() or self.headers.get('Origin') != ORIGIN:
            return self.reply(403, {'error': '허용되지 않은 요청입니다.'})
        if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
            return self.reply(415, {'error': 'JSON 요청이 필요합니다.'})
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if size < 1 or size > 20000:
                raise ValueError()
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, dict):
                raise ValueError()
        except (ValueError, TypeError):
            return self.reply(400, {'error': '요청 형식이 올바르지 않습니다.'})
        path = urlsplit(self.path).path
        if path == '/auth/logout':
            SESSIONS.pop(self.cookie('movie_session'), None)
            return self.reply(200, {'ok': True},
                'movie_session=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0')
        if path != '/auth/google':
            return self.reply(404, {'error': '요청 주소가 올바르지 않습니다.'})
        challenge = NONCES.pop(self.cookie('movie_nonce'), None)
        if not challenge or challenge['expires'] < time.time():
            return self.reply(401, {'error': '로그인 요청이 만료되었습니다.'})
        credential = data.get('credential')
        if not isinstance(credential, str) or not credential:
            return self.reply(400, {'error': '구글 로그인 정보가 없습니다.'})
        if not CLIENT_ID.endswith('.apps.googleusercontent.com'):
            return self.reply(503, {'error': '클라이언트 ID 설정이 필요합니다.'})
        try:
            from google.oauth2 import id_token
            from google.auth.transport.requests import Request
            import requests
            transport = requests.Session()
            try:
                class TimedRequest(Request):
                    def __call__(self, *args, **kwargs):
                        kwargs['timeout'] = 10
                        return super().__call__(*args, **kwargs)
                claims = id_token.verify_oauth2_token(credential, TimedRequest(session=transport), CLIENT_ID)
            finally:
                transport.close()
            if not secrets.compare_digest(str(claims.get('nonce', '')), challenge['nonce']):
                raise ValueError('nonce')
            if not claims.get('sub'):
                raise ValueError('subject')
        except ImportError:
            return self.reply(503, {'error': '서버에 google-auth와 requests 설치가 필요합니다.'})
        except ValueError:
            return self.reply(401, {'error': '구글 로그인 정보를 검증하지 못했습니다.'})
        except Exception:
            return self.reply(503, {'error': '구글 검증 서버에 연결하지 못했습니다. 잠시 후 다시 시도하세요.'})
        user = {'id': claims['sub'], 'name': claims.get('name') or '사용자'}
        old = self.cookie('movie_session')
        SESSIONS.pop(old, None)
        session_id = secrets.token_urlsafe(32)
        SESSIONS[session_id] = {'user': user, 'expires': time.time() + 3600}
        return self.reply(200, {'user': user},
            'movie_session=' + session_id + '; HttpOnly; SameSite=Lax; Path=/; Max-Age=3600')

if __name__ == '__main__':
    print('Open http://localhost:8000 (Ctrl+C to stop)')
    if not CLIENT_ID:
        print('GOOGLE_CLIENT_ID is not set. See the companion guide.')
    ThreadingHTTPServer(('127.0.0.1', 8000), Handler).serve_forever()
