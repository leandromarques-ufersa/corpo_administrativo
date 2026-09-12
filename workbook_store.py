"""Persistência OOXML do editor, usando apenas a biblioteca padrão do Python."""
import hashlib
import json
import re
import uuid
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from xml.etree import ElementTree as ET

S = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
P = 'http://schemas.openxmlformats.org/package/2006/relationships'
C = 'http://schemas.openxmlformats.org/package/2006/content-types'
FIELDS = ['Nome', 'Siape', 'Setor', 'Unidade', 'Cargo', 'Nascimento', 'Ramal', 'WhatsApp', 'Foto', 'ID']


def revision(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sheet_paths(files):
    rels = ET.fromstring(files['xl/_rels/workbook.xml.rels'])
    targets = {r.get('Id'): r.get('Target') for r in rels}
    book = ET.fromstring(files['xl/workbook.xml'])
    return {s.get('name'): (targets[s.get('{'+R+'}id')].lstrip('/') if targets[s.get('{'+R+'}id')].startswith('/') else 'xl/'+targets[s.get('{'+R+'}id')]) for s in book.find('{'+S+'}sheets')}


def read_rows(files, path):
    strings = []
    if 'xl/sharedStrings.xml' in files:
        strings = [''.join(n.itertext()) for n in ET.fromstring(files['xl/sharedStrings.xml'])]
    result = []
    for row in ET.fromstring(files[path]).findall('.//{'+S+'}sheetData/{'+S+'}row'):
        values = {}
        for cell in row:
            value = cell.find('{'+S+'}v')
            inline = cell.find('{'+S+'}is')
            value = value.text or '' if value is not None else ''.join(inline.itertext()) if inline is not None else ''
            if cell.get('t') == 's':
                value = strings[int(value)]
            values[re.sub(r'\d', '', cell.get('r'))] = value
        result.append(values)
    if not result:
        return []
    return [{name: row.get(col, '') for col, name in result[0].items()} for row in result[1:] if any(row.values())]


def load(path, defaults, photo_path):
    with zipfile.ZipFile(path) as archive:
        files = {n: archive.read(n) for n in archive.namelist()}
    paths = sheet_paths(files)
    people = read_rows(files, paths['TAES'])
    has_photo = bool(people and 'Foto' in people[0])
    photos = json.loads(Path(photo_path).read_text(encoding='utf-8'))
    prop = ET.fromstring(files['xl/workbook.xml']).find('{'+S+'}workbookPr')
    epoch = datetime(1904, 1, 1) if prop is not None and prop.get('date1904') in {'1', 'true'} else datetime(1899, 12, 30)
    for i, person in enumerate(people):
        for field in FIELDS:
            person.setdefault(field, '')
            person[field] = ' '.join(person[field].split())
            if person[field].casefold() in {'-', '—', 'n/a', 'indisponível'}:
                person[field] = ''
        person['ID'] = person['ID'] or str(uuid.uuid5(uuid.NAMESPACE_URL, str(i)+person['Nome']+person['Siape']))
        if not has_photo:
            person['Foto'] = photos.get(person['Siape']) or ''
        birthday = person['Nascimento']
        if re.fullmatch(r'\d+(?:\.\d+)?', birthday):
            person['Nascimento'] = (epoch + timedelta(days=float(birthday))).strftime('%d/%m')
        elif birthday:
            for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d/%m'):
                try:
                    person['Nascimento'] = datetime.strptime(birthday, fmt).strftime('%d/%m')
                    break
                except ValueError:
                    continue
    sectors = read_rows(files, paths['EditorSetores']) if 'EditorSetores' in paths else [dict(zip(['slug', 'name', 'short', 'color', 'pale'], s)) for s in defaults]
    units = read_rows(files, paths['EditorUnidades']) if 'EditorUnidades' in paths else [{'id': str(uuid.uuid5(uuid.NAMESPACE_URL, p['Setor']+'|'+p['Unidade'])), 'sector': p['Setor'], 'name': p['Unidade']} for i, p in enumerate(people) if (p['Setor'], p['Unidade']) not in {(x['Setor'], x['Unidade']) for x in people[:i]}]
    return {'sectors': sectors, 'units': units, 'people': people, 'revision': revision(path)}


def validate(data, root):
    if not isinstance(data, dict) or any(not isinstance(data.get(k), list) for k in ('sectors', 'units', 'people')):
        raise ValueError('Cadastro inválido.')
    if sum(len(data[k]) for k in ('sectors', 'units', 'people')) > 10000:
        raise ValueError('Limite de registros excedido.')
    schemas = {'sectors': ['slug', 'name', 'short', 'color', 'pale'], 'units': ['id', 'sector', 'name'], 'people': FIELDS}
    for kind, fields in schemas.items():
        for item in data[kind]:
            if not isinstance(item, dict):
                raise ValueError('Registro inválido.')
            for key in fields:
                if not isinstance(item.get(key), str) or len(item[key]) > 500:
                    raise ValueError('Campo inválido: '+key)
                item[key] = item[key].strip()
                if any(ord(c) < 32 for c in item[key]):
                    raise ValueError('Caracteres inválidos em '+key)
    def unique(values, label):
        if len(values) != len(set(values)):
            raise ValueError(label+' repetido.')
    sectors = data['sectors']
    unique([s['name'].casefold() for s in sectors], 'Nome do setor')
    unique([s['slug'] for s in sectors], 'Endereço do setor')
    reserved = {'css', 'photos', 'referencia', 'admin', 'editor', '_site', 'api'}
    for s in sectors:
        if not s['name'] or not s['short'] or not re.fullmatch(r'[a-z][a-z0-9-]{0,79}', s['slug']) or s['slug'] in reserved:
            raise ValueError('Nome ou endereço de setor inválido.')
        if any(not re.fullmatch(r'#[0-9a-fA-F]{6}', s[k]) for k in ('color', 'pale')):
            raise ValueError('Cor inválida.')
    names = {s['name'] for s in sectors}
    unique([u['id'] for u in data['units']], 'Identificador de unidade')
    unique([(u['sector'], u['name'].casefold()) for u in data['units']], 'Unidade')
    for u in data['units']:
        if not u['id'] or not u['name'] or u['sector'] not in names:
            raise ValueError('Unidade sem nome ou setor válido.')
    units = {(u['sector'], u['name']) for u in data['units']}
    unique([p['ID'] for p in data['people']], 'Identificador do servidor')
    unique([p['Siape'] for p in data['people'] if p['Siape']], 'SIAPE')
    for p in data['people']:
        if not p['ID'] or not p['Nome'] or (p['Setor'], p['Unidade']) not in units:
            raise ValueError('Servidor sem nome ou unidade válida.')
        if p['Nascimento']:
            try:
                datetime.strptime(p['Nascimento']+'/2000', '%d/%m/%Y')
            except ValueError:
                raise ValueError('Aniversário deve ser dia/mês (ex.: 29/02).')
        if p['Foto']:
            target = (root/'photos'/p['Foto']).resolve()
            if target.parent != (root/'photos').resolve() or not target.is_file() or target.suffix.lower() not in {'.jpg', '.jpeg', '.png', '.webp', '.gif'}:
                raise ValueError('Foto inválida.')


def write(source, target, data):
    """Preserva as outras abas e componentes do arquivo original."""
    with zipfile.ZipFile(source) as archive:
        files = {n: archive.read(n) for n in archive.namelist()}
    paths = sheet_paths(files)
    book = ET.fromstring(files['xl/workbook.xml'])
    rels = ET.fromstring(files['xl/_rels/workbook.xml.rels'])
    types = ET.fromstring(files['[Content_Types].xml'])
    sheets = book.find('{'+S+'}sheets')
    tables = [('TAES', FIELDS, data['people']), ('EditorSetores', ['slug', 'name', 'short', 'color', 'pale'], data['sectors']), ('EditorUnidades', ['id', 'sector', 'name'], data['units'])]
    for name, headers, rows in tables:
        if name not in paths:
            number = max(int(s.get('sheetId')) for s in sheets)+1
            rid = 'rEditor'+uuid.uuid4().hex
            path = 'xl/worksheets/editor'+uuid.uuid4().hex+'.xml'
            ET.SubElement(sheets, '{'+S+'}sheet', {'name': name, 'sheetId': str(number), '{'+R+'}id': rid})
            ET.SubElement(rels, '{'+P+'}Relationship', {'Id': rid, 'Type': R+'/worksheet', 'Target': path[3:]})
            ET.SubElement(types, '{'+C+'}Override', {'PartName': '/'+path, 'ContentType': 'application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml'})
            paths[name] = path
        path = paths[name]
        if name == 'TAES':
            original = read_rows(files, path)
            extras = [key for key in (original[0] if original else {}) if key not in headers]
            headers = headers + extras
            original_by_id = {p.get('ID') or str(uuid.uuid5(uuid.NAMESPACE_URL, str(i)+' '.join(p['Nome'].split())+' '.join(p['Siape'].split()))): p for i, p in enumerate(original)}
            rows = [{**{k: original_by_id.get(p['ID'], {}).get(k, '') for k in extras}, **p} for p in rows]
        sheet = ET.fromstring(files[path]) if path in files else ET.Element('{'+S+'}worksheet')
        content = sheet.find('{'+S+'}sheetData')
        if content is None:
            content = ET.SubElement(sheet, '{'+S+'}sheetData')
        # Retain column widths, sheet settings and styles; replace the editable table.
        old_styles = {re.sub(r'\d', '', c.get('r')): c.get('s') for r in list(content)[:1] for c in r if c.get('s')}
        content.clear()
        for rownum, values in enumerate([dict(zip(headers, headers))]+rows, 1):
            row = ET.SubElement(content, '{'+S+'}row', {'r': str(rownum)})
            for colnum, key in enumerate(headers):
                col = chr(65+colnum)
                attrs = {'r': col+str(rownum), 't': 'inlineStr'}
                if rownum == 1 and col in old_styles:
                    attrs['s'] = old_styles[col]
                cell = ET.SubElement(row, '{'+S+'}c', attrs)
                ET.SubElement(ET.SubElement(cell, '{'+S+'}is'), '{'+S+'}t').text = values.get(key, '')
        dimension = sheet.find('{'+S+'}dimension')
        if dimension is not None:
            dimension.set('ref', 'A1:'+chr(64+len(headers))+str(len(rows)+1))
        autofilter = sheet.find('{'+S+'}autoFilter')
        if autofilter is not None:
            autofilter.set('ref', 'A1:'+chr(64+len(headers))+str(len(rows)+1))
        files[path] = ET.tostring(sheet, encoding='utf-8', xml_declaration=True)
    files['xl/workbook.xml'] = ET.tostring(book, encoding='utf-8', xml_declaration=True)
    files['xl/_rels/workbook.xml.rels'] = ET.tostring(rels, encoding='utf-8', xml_declaration=True)
    files['[Content_Types].xml'] = ET.tostring(types, encoding='utf-8', xml_declaration=True)
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
