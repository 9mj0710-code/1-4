"""Local HTTP checks. Google verification is mocked; this does not test real Google login."""
import importlib.util, threading, urllib.request, urllib.error, http.cookiejar, json, types, sys
from unittest.mock import patch
spec = importlib.util.spec_from_file_location('movie', __file__.replace('로그인_검증.py', '로그인서버.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
server = m.ThreadingHTTPServer(('127.0.0.1', 0), m.Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
base = 'http://127.0.0.1:' + str(server.server_port)
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
def call(path, data=None, origin='http://localhost:8000'):
    headers = {'Host': 'localhost:8000'}
    if data is not None:
        headers.update({'Content-Type': 'application/json', 'Origin': origin})
    request = urllib.request.Request(base + path, headers=headers, data=None if data is None else json.dumps(data).encode())
    try:
        with opener.open(request, timeout=5) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()
try:
    assert call('/')[0] == 200
    assert json.loads(call('/auth/session')[1])['user'] is None
    m.CLIENT_ID = ''
    assert call('/auth/config')[0] == 503
    assert call('/auth/google', {}, 'https://other.example')[0] == 403
    assert call('/auth/google', {'credential': 'bad'})[0] == 401
    assert call('/not-allowed')[0] == 404
    m.CLIENT_ID = 'test.apps.googleusercontent.com'
    assert call('/auth/config')[0] == 200
    nonce = next(iter(m.NONCES.values()))['nonce']
    names = ['google', 'google.oauth2', 'google.oauth2.id_token', 'google.auth', 'google.auth.transport', 'google.auth.transport.requests', 'requests']
    modules = {name: types.ModuleType(name) for name in names}
    modules['google.oauth2.id_token'].verify_oauth2_token = lambda *args: {'sub': 'test-user', 'name': 'Test', 'nonce': nonce}
    modules['google.auth.transport.requests'].Request = type('Request', (), {'__init__': lambda self, **kwargs: None})
    modules['requests'].Session = lambda: types.SimpleNamespace(close=lambda: None)
    with patch.dict(sys.modules, modules):
        assert call('/auth/google', {'credential': 'mock-only'})[0] == 200
    assert json.loads(call('/auth/session')[1])['user']['id'] == 'test-user'
    assert call('/auth/google', {'credential': 'replay'})[0] == 401
    assert call('/auth/logout', {})[0] == 200
    assert json.loads(call('/auth/session')[1])['user'] is None
    print('PASS: routes, config, origin, nonce, mocked login, session, logout, replay rejection.')
    print('Real Google account login requires your client ID and browser testing.')
finally:
    server.shutdown()
    server.server_close()
