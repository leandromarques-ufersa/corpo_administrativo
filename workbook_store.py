"""Persistência OOXML do editor, usando apenas a biblioteca padrão do Python."""
import hashlib
import io
import json
import re
import uuid
import unicodedata
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit
from xml.etree import ElementTree as ET

S = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
P = 'http://schemas.openxmlformats.org/package/2006/relationships'
C = 'http://schemas.openxmlformats.org/package/2006/content-types'
FIELDS = ['Nome', 'Siape', 'Setor', 'Unidade', 'Cargo', 'Nascimento', 'Ramal', 'WhatsApp', 'Foto', 'ID', 'Formação', 'Email']
SECTOR_HEADERS = {'Endereço': 'slug', 'Nome': 'name', 'Nome no menu': 'short', 'Cor': 'color', 'Fundo': 'pale', 'Página': 'page'}
UNIT_HEADERS = {'ID': 'id', 'Setor': 'sector', 'Unidade': 'name'}


def slugify(name):
    ascii_name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '-', ascii_name).strip('-')


def serialize(tree, original=None):
    """Mantém prefixos usados por mc:Ignorable e mc:Choice Requires do Excel."""
    namespaces = {}
    if original:
        for _, (prefix, uri) in ET.iterparse(io.BytesIO(original), events=['start-ns']):
            namespaces[prefix] = uri
            if not re.fullmatch(r'ns\d+', prefix):
                ET.register_namespace(prefix, uri)
    else:
        ET.register_namespace('', S)
    preview = ET.tostring(tree, encoding='unicode')
    declared = set(re.findall(r'xmlns(?::([\w]+))?=', preview))
    for prefix, uri in namespaces.items():
        if prefix and prefix not in declared:
            tree.set('xmlns:'+prefix, uri)
    return ET.tostring(tree, encoding='utf-8', xml_declaration=True)


def column_name(number):
    result = ''
    while number:
        number, remainder = divmod(number-1, 26)
        result = chr(65+remainder)+result
    return result


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
    return [{name: row.get(col, '') for col, name in result[0].items() if name} for row in result[1:] if any(row.values())]


def load(path, defaults, photo_path):
    with zipfile.ZipFile(path) as archive:
        files = {n: archive.read(n) for n in archive.namelist()}
    paths = sheet_paths(files)
    if 'TAES' not in paths:
        raise ValueError('A planilha precisa da aba TAES.')
    people = read_rows(files, paths['TAES'])
    for index, person in enumerate(people, 2):
        missing = set(FIELDS[:8]) - person.keys()
        if missing:
            raise ValueError('Cabeçalhos obrigatórios ausentes em TAES: '+', '.join(sorted(missing)))
        if not person.get('Nome', '').strip():
            raise ValueError(f'TAES: registro {index} sem Nome. Preencha o nome ou exclua a linha inteira.')
    has_photo = bool(people and 'Foto' in people[0])
    photos = json.loads(Path(photo_path).read_text(encoding='utf-8')) if not has_photo and Path(photo_path).is_file() else {}
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
            person['Nascimento'] = (epoch + timedelta(days=float(birthday))).strftime('%d-%m')
        elif birthday:
            for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%d/%m', '%d-%m'):
                try:
                    value = birthday + '/2000' if fmt in ('%d/%m', '%d-%m') else birthday
                    parse_fmt = fmt + '/%Y' if fmt in ('%d/%m', '%d-%m') else fmt
                    person['Nascimento'] = datetime.strptime(value, parse_fmt).strftime('%d-%m')
                    break
                except ValueError:
                    continue
    sectors = read_rows(files, paths['EditorSetores']) if 'EditorSetores' in paths else [dict(zip(['slug', 'name', 'short', 'color', 'pale'], s)) for s in defaults]
    units = read_rows(files, paths['EditorUnidades']) if 'EditorUnidades' in paths else [{'id': str(uuid.uuid5(uuid.NAMESPACE_URL, p['Setor']+'|'+p['Unidade'])), 'sector': p['Setor'], 'name': p['Unidade']} for i, p in enumerate(people) if (p['Setor'], p['Unidade']) not in {(x['Setor'], x['Unidade']) for x in people[:i]}]
    sectors = [{SECTOR_HEADERS.get(k, k): v.strip() for k, v in s.items()} for s in sectors]
    units = [{UNIT_HEADERS.get(k, k): v.strip() for k, v in u.items()} for u in units]
    for sector in sectors:
        sector.setdefault('name', '')
        sector.setdefault('page', '')
        sector['slug'] = sector.get('slug') or slugify(sector['name'])
        sector['short'] = sector.get('short') or sector['name']
        sector['color'] = sector.get('color') or '#1943c9'
        sector['pale'] = sector.get('pale') or '#edf2ff'
    for unit in units:
        unit.setdefault('sector', '')
        unit.setdefault('name', '')
        unit['id'] = unit.get('id') or str(uuid.uuid5(uuid.NAMESPACE_URL, unit['sector']+'|'+unit['name']))
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
            if kind == 'sectors':
                page = item.setdefault('page', '')
                if not isinstance(page, str) or len(page) > 2000 or any(c.isspace() for c in page):
                    raise ValueError('Página oficial inválida.')
                if page and (urlsplit(page).scheme not in {'http', 'https'} or not urlsplit(page).hostname):
                    raise ValueError('Página oficial deve ser um link http:// ou https://.')
    def unique(values, label):
        if len(values) != len(set(values)):
            raise ValueError(label+' repetido.')
    sectors = data['sectors']
    unique([s['name'].casefold() for s in sectors], 'Nome do setor')
    unique([s['slug'] for s in sectors], 'Endereço do setor')
    reserved = {'css', 'photos', 'referencia', 'admin', 'editor', '_site', 'api'}
    for s in sectors:
        if not s['name'] or not s['short'] or not re.fullmatch(r'[a-z][a-z0-9-]{0,79}', s['slug']) or s['slug'] in reserved:
            raise ValueError('EditorSetores: nome ou endereço inválido para '+s['name']+'. Use letras minúsculas, números e hífens no endereço.')
        if any(not re.fullmatch(r'#[0-9a-fA-F]{6}', s[k]) for k in ('color', 'pale')):
            raise ValueError('Cor inválida.')
    names = {s['name'] for s in sectors}
    unique([u['id'] for u in data['units']], 'Identificador de unidade')
    unique([(u['sector'], u['name'].casefold()) for u in data['units']], 'Unidade')
    for u in data['units']:
        if not u['id'] or not u['name'] or u['sector'] not in names:
            raise ValueError('EditorUnidades: unidade "'+u['name']+'" sem nome ou com setor inexistente: '+u['sector'])
    units = {(u['sector'], u['name']) for u in data['units']}
    unique([p['ID'] for p in data['people']], 'Identificador do servidor')
    unique([p['Siape'] for p in data['people'] if p['Siape']], 'SIAPE')
    for p in data['people']:
        if not p['ID'] or not p['Nome'] or (p['Setor'], p['Unidade']) not in units:
            raise ValueError('TAES: servidor "'+p['Nome']+'" sem nome ou com setor/unidade não cadastrado: '+p['Setor']+' / '+p['Unidade'])
        if p['Nascimento']:
            try:
                datetime.strptime(p['Nascimento'].replace('-', '/')+'/2000', '%d/%m/%Y')
            except ValueError:
                raise ValueError('TAES: aniversário de '+p['Nome']+' deve ser dia-mês (ex.: 29-02).')
        if p['Foto']:
            target = (root/'photos'/p['Foto']).resolve()
            exact_names = {f.name for f in (root/'photos').iterdir() if f.is_file()}
            if target.parent != (root/'photos').resolve() or not target.is_file() or p['Foto'] not in exact_names or target.suffix.lower() not in {'.jpg', '.jpeg', '.png', '.webp', '.gif'}:
                raise ValueError('TAES: foto de '+p['Nome']+' não encontrada ou inválida: '+p['Foto']+'. Use o nome exato do arquivo em photos, incluindo maiúsculas e extensão.')


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
        mapping = SECTOR_HEADERS if name == 'EditorSetores' else UNIT_HEADERS if name == 'EditorUnidades' else None
        if mapping:
            headers = list(mapping)
            rows = [{label: row.get(key, '') for label, key in mapping.items()} for row in rows]
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
            headers = list(original[0]) + [key for key in headers if key not in original[0]] if original else headers
            original_by_id = {p.get('ID') or str(uuid.uuid5(uuid.NAMESPACE_URL, str(i)+' '.join(p['Nome'].split())+' '.join(p['Siape'].split()))): p for i, p in enumerate(original)}
            rows = [{**{k: original_by_id.get(p['ID'], {}).get(k, '') for k in extras}, **p} for p in rows]
        sheet = ET.fromstring(files[path]) if path in files else ET.Element('{'+S+'}worksheet')
        content = sheet.find('{'+S+'}sheetData')
        if content is None:
            content = ET.SubElement(sheet, '{'+S+'}sheetData')
        # Retain column widths, sheet settings and styles; replace the editable table.
        old_styles = {re.sub(r'\d', '', c.get('r')): c.get('s') for r in list(content)[:1] for c in r if c.get('s')}
        body_styles = {re.sub(r'\d', '', c.get('r')): c.get('s') for r in list(content)[1:2] for c in r if c.get('s')}
        content.clear()
        for rownum, values in enumerate([dict(zip(headers, headers))]+rows, 1):
            row = ET.SubElement(content, '{'+S+'}row', {'r': str(rownum)})
            for colnum, key in enumerate(headers):
                col = column_name(colnum+1)
                attrs = {'r': col+str(rownum), 't': 'inlineStr'}
                if rownum == 1 and col in old_styles:
                    attrs['s'] = old_styles[col]
                elif rownum > 1 and col in body_styles:
                    attrs['s'] = body_styles[col]
                cell = ET.SubElement(row, '{'+S+'}c', attrs)
                value = values.get(key, '')
                if name == 'TAES' and key == 'Nascimento' and rownum > 1:
                    value = value.replace('/', '-')
                ET.SubElement(ET.SubElement(cell, '{'+S+'}is'), '{'+S+'}t').text = value
        dimension = sheet.find('{'+S+'}dimension')
        if dimension is not None:
            dimension.set('ref', 'A1:'+column_name(len(headers))+str(len(rows)+1))
        autofilter = sheet.find('{'+S+'}autoFilter')
        if autofilter is not None:
            autofilter.set('ref', 'A1:'+column_name(len(headers))+str(len(rows)+1))
        files[path] = serialize(sheet, files.get(path))
    files['xl/workbook.xml'] = serialize(book, files['xl/workbook.xml'])
    files['xl/_rels/workbook.xml.rels'] = serialize(rels, files['xl/_rels/workbook.xml.rels'])
    files['[Content_Types].xml'] = serialize(types, files['[Content_Types].xml'])
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
