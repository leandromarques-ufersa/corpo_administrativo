"""Editor local: python editor.py; somente http://127.0.0.1:8002."""
import hashlib
import hmac
import json
import mimetypes
import os
import secrets
import shutil
import tempfile
import time
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

import build
import workbook_store as store

ROOT = Path(__file__).resolve().parent
BOOK = ROOT / 'Corpo Administrativo.xlsx'
ORIGIN = 'http://127.0.0.1:8002'
SESSIONS = {}
FAILURES = []


def load():
    return store.load(BOOK, build.SECTORS, ROOT/'photos.json')


def save(data):
    if data.get('revision') != store.revision(BOOK):
        raise ValueError('A planilha mudou desde que você abriu o editor. Recarregue antes de editar novamente.')
    store.validate(data, ROOT)
    previous = load()
    backup_dir = ROOT/'.editor-backups'
    backup_dir.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.editor-tmp', dir=ROOT) as temp:
        temp = Path(temp)
        candidate = temp/'cadastro.xlsx'
        store.write(BOOK, candidate, data)
        store.load(candidate, build.SECTORS, ROOT/'photos.json')
        build.build(data=data, output=temp/'site')
        backup = backup_dir/(time.strftime('%Y%m%d-%H%M%S')+'-'+secrets.token_hex(4)+'.xlsx')
        shutil.copy2(BOOK, backup)
        try:
            os.replace(candidate, BOOK)
        except PermissionError:
            raise ValueError('Feche a planilha no Excel e tente salvar novamente.')
        try:
            for page in (temp/'site').rglob('*.html'):
                target = ROOT/page.relative_to(temp/'site')
                target.parent.mkdir(exist_ok=True)
                shutil.copy2(page, target)
            new_slugs = {s['slug'] for s in data['sectors']}
            for sector in previous['sectors']:
                slug = sector['slug']
                if slug not in new_slugs:
                    page = (ROOT/slug/'index.html').resolve()
                    if page.parent.parent == ROOT and page.is_file():
                        page.unlink()
        except OSError:
            shutil.copy2(backup, BOOK)
            build.build(data=previous)
            raise ValueError('Não foi possível atualizar as páginas. A planilha anterior foi restaurada.')
    return load()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def reply(self, status, body, content_type='application/json; charset=utf-8', cookie=None):
        payload = json.dumps(body, ensure_ascii=False).encode() if not isinstance(body, bytes) else body
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self'; frame-ancestors 'none'; form-action 'self'")
        if cookie:
            self.send_header('Set-Cookie', cookie)
        self.end_headers()
        self.wfile.write(payload)

    def session(self):
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get('Cookie', ''))
        except Exception:
            return None
        token = cookie['editor'].value if 'editor' in cookie else ''
        entry = SESSIONS.get(token)
        return entry if entry and entry['expires'] > time.time() else None

    def host_ok(self):
        return self.headers.get('Host') == '127.0.0.1:8002'

    def do_GET(self):
        if not self.host_ok():
            return self.reply(403, {'error': 'Endereço não autorizado.'})
        path = unquote(urlsplit(self.path).path)
        if path == '/api/state':
            session = self.session()
            if not session:
                return self.reply(401, {'error': 'Entre para editar.'})
            try:
                data = load()
                data['csrf'] = session['csrf']
                data['photos'] = sorted(p.name for p in (ROOT/'photos').iterdir() if p.suffix.lower() in {'.jpg', '.jpeg', '.png', '.webp', '.gif'})
                return self.reply(200, data)
            except Exception:
                return self.reply(500, {'error': 'Não foi possível ler a planilha. Verifique o arquivo local.'})
        assets = {'/editor': ROOT/'editor_ui/index.html', '/editor.js': ROOT/'editor_ui/editor.js', '/editor.css': ROOT/'editor_ui/editor.css'}
        target = assets.get(path)
        if target is None:
            target = (ROOT/(path.lstrip('/') or 'index.html')).resolve()
            allowed = target == ROOT/'index.html' or target == ROOT/'favicon.svg' or (target.parent == ROOT/'css' and target.suffix == '.css') or (target.parent == ROOT/'photos' and target.suffix.lower() in {'.jpg', '.jpeg', '.png', '.webp', '.gif'})
            if not allowed:
                try:
                    allowed = any(target == ROOT/s['slug']/'index.html' for s in load()['sectors'])
                except Exception:
                    allowed = False
            if not allowed:
                return self.reply(404, {'error': 'Não encontrado.'})
        if not target.is_file():
            return self.reply(404, {'error': 'Não encontrado.'})
        self.reply(200, target.read_bytes(), mimetypes.guess_type(target)[0] or 'application/octet-stream')

    def do_POST(self):
        if not self.host_ok() or self.headers.get('Origin') != ORIGIN:
            return self.reply(403, {'error': 'Origem não autorizada.'})
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 5_000_000 or self.headers.get('Content-Type') != 'application/json':
                return self.reply(400, {'error': 'Requisição inválida.'})
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError('Requisição inválida.')
            if self.path == '/api/login':
                FAILURES[:] = [t for t in FAILURES if t > time.time()-60]
                if len(FAILURES) >= 5:
                    return self.reply(429, {'error': 'Aguarde um minuto antes de tentar novamente.'})
                config = json.loads((ROOT/'.editor-secrets.json').read_text())
                username, password = data.get('username', ''), data.get('password', '')
                if not isinstance(username, str) or not isinstance(password, str) or len(password) > 1000:
                    raise ValueError('Credenciais inválidas.')
                actual = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(config['salt']), 600000).hex()
                if not (hmac.compare_digest(username.encode(), config['username'].encode()) and hmac.compare_digest(actual, config['password_hash'])):
                    FAILURES.append(time.time())
                    return self.reply(401, {'error': 'Usuário ou senha incorretos.'})
                token = secrets.token_urlsafe(32)
                SESSIONS[token] = {'csrf': secrets.token_urlsafe(32), 'expires': time.time()+8*3600}
                return self.reply(200, {'ok': True}, cookie='editor='+token+'; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800')
            session = self.session()
            if not session:
                return self.reply(401, {'error': 'Sessão encerrada. Entre novamente.'})
            if not hmac.compare_digest(self.headers.get('X-CSRF-Token', ''), session['csrf']):
                return self.reply(403, {'error': 'Atualize o editor e tente novamente.'})
            if self.path == '/api/logout':
                for token, entry in list(SESSIONS.items()):
                    if entry is session:
                        del SESSIONS[token]
                return self.reply(200, {'ok': True}, cookie='editor=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0')
            if self.path == '/api/save':
                saved = save(data)
                return self.reply(200, {'revision': saved['revision']})
            self.reply(404, {'error': 'Não encontrado.'})
        except (ValueError, KeyError, TypeError) as error:
            self.reply(400, {'error': str(error)})
        except Exception:
            self.reply(500, {'error': 'Não foi possível salvar. Verifique se a planilha está fechada e a pasta permite gravação.'})


if __name__ == '__main__':
    if not (ROOT/'.editor-secrets.json').is_file():
        raise SystemExit('Configure o login primeiro: python configurar_editor.py')
    print('Editor local: '+ORIGIN+'/editor\nMantenha este terminal aberto. Ctrl+C para encerrar.', flush=True)
    HTTPServer(('127.0.0.1', 8002), Handler).serve_forever()
