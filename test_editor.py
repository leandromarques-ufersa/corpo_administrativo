import copy
import http.client
import json
import io
import re
import shutil
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import build
import configurar_editor
import editor
import workbook_store as store


class EditorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='.editor-tmp', dir=editor.ROOT)
        self.root = Path(self.temp.name)
        self.book = self.root/editor.BOOK.name
        shutil.copy2(editor.BOOK, self.book)
        shutil.copy2(editor.ROOT/'photos.json', self.root/'photos.json')
        shutil.copytree(editor.ROOT/'photos', self.root/'photos')
        self.defaults = copy.deepcopy(build.SECTORS)
        self.data = store.load(self.book, self.defaults, self.root/'photos.json')

    def tearDown(self):
        build.SECTORS = self.defaults
        self.temp.cleanup()

    def test_roundtrip_preserves_records_and_other_components(self):
        candidate = self.root/'roundtrip.xlsx'
        store.write(self.book, candidate, self.data)
        actual = store.load(candidate, self.defaults, self.root/'photos.json')
        for key in ('people', 'units', 'sectors'):
            self.assertEqual(self.data[key], actual[key])
        with zipfile.ZipFile(self.book) as original, zipfile.ZipFile(candidate) as saved:
            paths = store.sheet_paths({n: original.read(n) for n in original.namelist()})
            changed = {'xl/workbook.xml', 'xl/_rels/workbook.xml.rels', '[Content_Types].xml'}
            changed.update(paths[name] for name in ('TAES', 'EditorSetores', 'EditorUnidades') if name in paths)
            for name in original.namelist():
                if name not in changed:
                    self.assertEqual(original.read(name), saved.read(name), name)
            for name in ('xl/workbook.xml', 'xl/worksheets/sheet1.xml'):
                xml = saved.read(name)
                namespaces = {prefix for _, (prefix, uri) in store.ET.iterparse(io.BytesIO(xml), events=['start-ns'])}
                for element in store.ET.fromstring(xml).iter():
                    for key, value in element.attrib.items():
                        if key.endswith('}Ignorable') or key == 'Requires':
                            self.assertTrue(set(value.split()) <= namespaces, (name, value, namespaces))

    def test_create_move_edit_delete_and_empty_sector(self):
        self.data['sectors'].append(dict(slug='novo-setor', name='Novo setor', short='Novo', color='#123456', pale='#eefaff'))
        self.data['units'].append(dict(id='nova', sector='Novo setor', name='Nova unidade'))
        person = dict.fromkeys(store.FIELDS, '')
        person.update(ID='novo', Nome='Pessoa teste', Setor='Novo setor', Unidade='Nova unidade', Nascimento='29/02')
        self.data['people'].append(person)
        self.data['people'][0].update(Setor='Novo setor', Unidade='Nova unidade', Nome='Nome alterado')
        store.validate(self.data, self.root)
        with patch.object(editor, 'ROOT', self.root), patch.object(editor, 'BOOK', self.book), patch.object(build, 'ROOT', self.root):
            saved = editor.save(self.data)
            self.assertTrue((self.root/'novo-setor/index.html').is_file())
            self.assertIn('Nome alterado', (self.root/'novo-setor/index.html').read_text(encoding='utf-8'))
            self.assertEqual(len(saved['people']), 43)
            self.assertEqual(len(list((self.root/'.editor-backups').glob('*.xlsx'))), 1)
            saved['people'] = []
            saved['units'] = []
            result = editor.save(saved)
            self.assertEqual(result['people'], [])
            self.assertIn('Novo setor', (self.root/'index.html').read_text(encoding='utf-8'))
            result['sectors'] = []
            editor.save(result)
            self.assertFalse((self.root/'novo-setor/index.html').exists())

    def test_invalid_relations_duplicates_dates_and_paths(self):
        cases = [lambda d: d['units'].clear(), lambda d: d['people'].append(copy.deepcopy(d['people'][0])), lambda d: d['sectors'][0].update(slug='../escape'), lambda d: d['people'][0].update(Foto='../README.md'), lambda d: d['people'][0].update(Nascimento='31/02'), lambda d: d['sectors'].clear()]
        for modify in cases:
            data = copy.deepcopy(self.data)
            modify(data)
            with self.assertRaises(ValueError):
                store.validate(data, self.root)

    def test_stale_save_and_locked_workbook(self):
        original = self.book.read_bytes()
        with patch.object(editor, 'ROOT', self.root), patch.object(editor, 'BOOK', self.book), patch.object(build, 'ROOT', self.root):
            data = copy.deepcopy(self.data)
            data['revision'] = 'stale'
            with self.assertRaises(ValueError):
                editor.save(data)
            with patch.object(editor.os, 'replace', side_effect=PermissionError):
                with self.assertRaisesRegex(ValueError, 'Excel'):
                    editor.save(self.data)
        self.assertEqual(original, self.book.read_bytes())

    def test_birthday_privacy_and_formation(self):
        person = self.data['people'][0]
        person['Nascimento'] = '29-02'
        person['Formação'] = 'Mestrado em Educação'
        person['Email'] = 'servidor@ufersa.edu.br'
        store.validate(self.data, self.root)
        candidate = self.root/'birthday.xlsx'
        store.write(self.book, candidate, self.data)
        actual = store.load(candidate, self.defaults, self.root/'photos.json')
        self.assertEqual(actual['people'][0]['Nascimento'], '29-02')
        page = build.card(actual['people'][0], {}, '../')
        self.assertIn('<span class="degree">Mestrado em educação</span>', page)
        self.assertNotIn('<h4>Formação</h4>', page)
        self.assertIn('29/02', page)
        self.assertIn('<dt>Telefone</dt>', page)
        self.assertEqual(actual['people'][0]['Email'], person['Email'])
        self.assertIn('<dt>E-mail</dt><dd><a href="mailto:servidor@ufersa.edu.br">', page)
        self.assertNotIn('https://wa.me/', page)
        with zipfile.ZipFile(candidate) as archive:
            files = {n: archive.read(n) for n in archive.namelist()}
        rows = store.read_rows(files, store.sheet_paths(files)['TAES'])
        for row in rows:
            if row['Nascimento']:
                self.assertRegex(row['Nascimento'], r'^\d{2}-\d{2}$')

    def test_spreadsheet_new_records_without_technical_fields(self):
        data = copy.deepcopy(self.data)
        data['sectors'].append(dict(slug='', name='Apoio à Pesquisa', short='', color='', pale=''))
        data['units'].append(dict(id='', sector='Apoio à Pesquisa', name='Nova equipe'))
        person = dict.fromkeys(store.FIELDS, '')
        person.update(Nome='Nova pessoa', Setor='Apoio à Pesquisa', Unidade='Nova equipe', Foto='Alan.png')
        data['people'].append(person)
        candidate = self.root/'manual.xlsx'
        store.write(self.book, candidate, data)
        actual = store.load(candidate, self.defaults, self.root/'arquivo-inexistente.json')
        store.validate(actual, self.root)
        self.assertEqual(actual['sectors'][-1]['slug'], 'apoio-a-pesquisa')
        self.assertTrue(actual['units'][-1]['id'])
        self.assertTrue(actual['people'][-1]['ID'])
        with patch.object(build, 'ROOT', self.root):
            build.build(data=actual, output=self.root/'publico')
        page = (self.root/'publico/apoio-a-pesquisa/index.html').read_text(encoding='utf-8')
        self.assertIn('../photos/Alan.png', page)
        self.assertIn('Nova pessoa', page)

    def test_photo_case_and_invalid_relations_block_generation(self):
        data = copy.deepcopy(self.data)
        data['people'][0]['Foto'] = 'alan.PNG'
        with self.assertRaisesRegex(ValueError, 'foto de'):
            store.validate(data, self.root)
        data = copy.deepcopy(self.data)
        data['people'][0]['Unidade'] = 'Unidade inexistente'
        with patch.object(build, 'ROOT', self.root):
            with self.assertRaisesRegex(ValueError, 'não cadastrado'):
                build.build(data=data, output=self.root/'invalido')
        self.assertFalse((self.root/'invalido/index.html').exists())

    def test_http_auth_csrf_and_private_files(self):
        salt = bytes.fromhex('01'*32)
        config = {'username': 'test@example.test', 'salt': salt.hex(), 'password_hash': editor.hashlib.pbkdf2_hmac('sha256', b'test-password', salt, 600000).hex()}
        (self.root/'.editor-secrets.json').write_text(json.dumps(config))
        server = editor.HTTPServer(('127.0.0.1', 0), editor.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        def request(path, data=None, cookie='', csrf='', origin=editor.ORIGIN, host='127.0.0.1:8002'):
            conn = http.client.HTTPConnection('127.0.0.1', server.server_port)
            headers = {'Host': host, 'Origin': origin, 'Content-Type': 'application/json', 'Cookie': cookie, 'X-CSRF-Token': csrf}
            conn.request('GET' if data is None else 'POST', path, body=None if data is None else json.dumps(data), headers=headers)
            response = conn.getresponse()
            status, value, set_cookie = response.status, json.loads(response.read()), response.getheader('Set-Cookie')
            conn.close()
            return status, value, set_cookie
        try:
            with patch.object(editor, 'ROOT', self.root), patch.object(editor, 'BOOK', self.book):
                self.assertEqual(request('/api/state')[0], 401)
                for path in ('/.editor-secrets.json', '/Corpo%20Administrativo.xlsx', '/build.py', '/.git/config', '/photos/../.editor-secrets.json'):
                    self.assertEqual(request(path)[0], 404)
                credentials = {'username': config['username'], 'password': 'test-password'}
                self.assertEqual(request('/api/login', credentials, origin='https://evil.test')[0], 403)
                self.assertEqual(request('/api/login', credentials, host='evil.test')[0], 403)
                self.assertEqual(request('/api/login', {**credentials, 'password': 'wrong'})[0], 401)
                status, _, cookie = request('/api/login', credentials)
                self.assertEqual(status, 200)
                self.assertIn('HttpOnly', cookie)
                status, state, _ = request('/api/state', cookie=cookie)
                self.assertEqual(status, 200)
                self.assertEqual(request('/api/save', state, cookie=cookie)[0], 403)
                self.assertEqual(request('/api/logout', {}, cookie=cookie, csrf=state['csrf'])[0], 200)
                self.assertEqual(request('/api/state', cookie=cookie)[0], 401)
        finally:
            server.shutdown()
            server.server_close()


if __name__ == '__main__':
    unittest.main()
