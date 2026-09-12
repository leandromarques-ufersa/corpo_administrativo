"""Gera o site a partir da planilha local, sem dependências externas."""
import html
import json
import re
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote
import workbook_store

ROOT = Path(__file__).parent
NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
SECTORS = [
    ('biblioteca', 'Biblioteca', 'Biblioteca', '#1943c9', '#edf2ff'),
    ('coordenadoria-academica', 'Coordenadoria Acadêmica', 'Acadêmica', '#b84415', '#fff3ec'),
    ('assuntos-estudantis', 'Coordenadoria de Assuntos Estudantis', 'Assuntos Estudantis', '#067568', '#eaf8f3'),
    ('planejamento-administracao', 'Coordenadoria de Planejamento e Administração', 'Planejamento e Administração', '#733bb9', '#f4effc'),
    ('direcao', 'Direção', 'Direção', '#22677b', '#eaf5f8'),
]
DEFAULT_SECTORS = tuple(SECTORS)


def esc(value):
    return html.escape(str(value), quote=True)


def clean(value):
    value = ' '.join(str(value or '').split())
    return '' if value.casefold() in {'-', '—', 'n/a', 'indisponível'} else value


def read_people():
    with zipfile.ZipFile(ROOT / 'Corpo Administrativo.xlsx') as archive:
        strings = []
        if 'xl/sharedStrings.xml' in archive.namelist():
            strings = [''.join(n.itertext()) for n in ET.fromstring(archive.read('xl/sharedStrings.xml')).findall('s:si', NS)]
        book = ET.fromstring(archive.read('xl/workbook.xml'))
        sheet = next(s for s in book.find('s:sheets', NS) if s.get('name') == 'TAES')
        rid = sheet.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
        rels = ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'))
        target = next(r.get('Target') for r in rels if r.get('Id') == rid)
        path = target.lstrip('/') if target.startswith('/') else 'xl/' + target
        rows = []
        headers = {}
        for row in ET.fromstring(archive.read(path)).findall('.//s:sheetData/s:row', NS):
            values = {}
            for cell in row.findall('s:c', NS):
                col = re.sub(r'\d', '', cell.get('r'))
                value = cell.find('s:v', NS)
                inline = cell.find('s:is', NS)
                text = value.text if value is not None else ''.join(inline.itertext()) if inline is not None else ''
                if cell.get('t') == 's':
                    text = strings[int(text)]
                values[col] = clean(text)
            if not headers:
                headers = values
                if not {'Nome', 'Siape', 'Setor', 'Unidade', 'Cargo', 'Nascimento', 'Ramal', 'WhatsApp'} <= set(headers.values()):
                    raise ValueError('Cabeçalhos obrigatórios ausentes na aba TAES')
                continue
            person = {name: values.get(col, '') for col, name in headers.items()}
            if person.get('Nome'):
                if person['Setor'] not in {s[1] for s in SECTORS}:
                    raise ValueError('Setor desconhecido: ' + person['Setor'])
                rows.append(person)
        if not rows:
            raise ValueError('A planilha não contém servidores')
        ids = [p['Siape'] for p in rows if p['Siape']]
        if len(ids) != len(set(ids)):
            raise ValueError('Matrícula repetida na planilha')
        prop = book.find('s:workbookPr', NS)
        epoch = datetime(1904, 1, 1) if prop is not None and prop.get('date1904') in {'1', 'true'} else datetime(1899, 12, 30)
        for person in rows:
            birthday = person['Nascimento']
            if re.fullmatch(r'\d+(?:\.\d+)?', birthday):
                person['Nascimento'] = (epoch + timedelta(days=float(birthday))).strftime('%d-%m')
            elif birthday:
                parsed = None
                for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%d/%m', '%d-%m'):
                    try:
                        value = birthday + '/2000' if fmt in ('%d/%m', '%d-%m') else birthday
                        parse_fmt = fmt + '/%Y' if fmt in ('%d/%m', '%d-%m') else fmt
                        parsed = datetime.strptime(value, parse_fmt).strftime('%d-%m')
                        break
                    except ValueError:
                        pass
                if parsed is None:
                    raise ValueError('Data de nascimento inválida para ' + person['Nome'])
                person['Nascimento'] = parsed
        return rows


def field(label, value):
    return '<div><dt>' + label + '</dt><dd>' + (esc(value) if value else '<span class="unavailable">Indisponível</span>') + '</dd></div>'


def card(person, photos, prefix):
    name = person['Nome']
    words = name.split()
    initials = words[0][0] + (words[-1][0] if len(words) > 1 else '')
    photo = photos.get(person['Siape'])
    portrait = '<span aria-hidden="true">' + esc(initials) + '</span>'
    if photo:
        target = (ROOT / 'photos' / photo).resolve()
        if target.parent != (ROOT / 'photos').resolve() or not target.is_file():
            raise ValueError('Foto inválida: ' + photo)
        portrait += '<img src="' + prefix + 'photos/' + quote(photo) + '" alt="Foto de ' + esc(name) + '" width="88" height="104" loading="lazy" onerror="this.remove()">'
    else:
        portrait += '<span class="sr-only">Foto indisponível</span>'
    number = person['WhatsApp']
    digits = re.sub(r'\D', '', number)
    if len(digits) in {10, 11}:
        digits = '55' + digits
    whatsapp = '<span class="unavailable">Indisponível</span>'
    if number:
        whatsapp = '<a href="https://wa.me/' + digits + '" target="_blank" rel="noopener noreferrer">' + esc(number) + ' ↗</a>' if len(digits) in {12, 13} and digits.startswith('55') else esc(number)
    return f'''<article class="card" data-siape="{esc(person['Siape'])}">
      <div class="card-top"><div class="portrait">{portrait}</div><div><span class="degree">Servidor</span><h3>{esc(name)}</h3>
      <p class="status">Matrícula SIAPE: {esc(person['Siape'] or 'Indisponível')}</p></div></div>
      <div class="formation"><h4>Cargo</h4><p>{esc(person['Cargo'] or 'Indisponível')}</p></div>
      <div class="formation"><h4>Formação</h4><p>{esc(person.get('Formação') or 'Indisponível')}</p></div>
      <dl class="contact"><div class="contact-pair">{field('Aniversário', person['Nascimento'])}{field('Ramal', person['Ramal'])}</div>
      <div class="whatsapp"><dt>WhatsApp</dt><dd>{whatsapp}</dd></div></dl></article>'''


def shell(title, body, prefix='./', active=None, color='#1943c9', pale='#edf2ff'):
    editor_link = '<p><a href="http://127.0.0.1:8002/editor" target="_blank" rel="noopener noreferrer">Editar Página</a></p>' if active is None else ''
    nav = '<a href="' + prefix + 'index.html"' + (' aria-current="page"' if active is None else '') + '>Início</a>'
    for slug, name, short, _, _ in SECTORS:
        nav += '<a href="' + prefix + slug + '/index.html"' + (' aria-current="page"' if active == slug else '') + '>' + esc(short) + '</a>'
    return f'''<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="Conheça os servidores, setores e unidades do corpo administrativo da UFERSA, Campus Angicos.">
<title>{esc(title)} | Corpo Administrativo UFERSA Angicos</title><link rel="icon" href="{prefix}favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="{prefix}css/style.css"><link rel="stylesheet" href="{prefix}css/admin.css"></head>
<body style="--accent:{color};--pale:{pale}"><a class="skip" href="#conteudo">Pular para o conteúdo</a>
<header class="top"><a class="brand" href="{prefix}index.html"><span class="brandmark">U</span><span>UFERSA<span class="brand-sub">CAMPUS ANGICOS</span></span></a>
<span class="directory-label">Corpo administrativo</span><nav aria-label="Navegação principal">{nav}</nav></header>
<main id="conteudo">{body}</main><footer><div><strong>Corpo Administrativo · UFERSA Angicos</strong><p>Servidores e unidades do campus.</p></div>
<div class="footnote">Informações do cadastro administrativo local.<br>Campos sem informação aparecem como indisponíveis.{editor_link}</div></footer></body></html>'''


def build(data=None, output=None):
    global SECTORS
    data = data or workbook_store.load(ROOT / 'Corpo Administrativo.xlsx', DEFAULT_SECTORS, ROOT / 'photos.json')
    workbook_store.validate(data, ROOT)
    people = data['people']
    SECTORS = [tuple(s[k] for k in ('slug', 'name', 'short', 'color', 'pale')) for s in data['sectors']]
    output = Path(output) if output else ROOT
    output.mkdir(parents=True, exist_ok=True)
    photos = {p['Siape']: p['Foto'] for p in people}
    tiles = []
    counts = Counter(p['Setor'] for p in people)
    for index, (slug, name, short, color, pale) in enumerate(SECTORS, 1):
        members = [p for p in people if p['Setor'] == name]
        units = [u['name'] for u in data['units'] if u['sector'] == name]
        units.sort(key=lambda u: (0 if u in {'Diretoria', 'Coordenadoria'} else 1, u.casefold()))
        tiles.append(f'''<a class="dept-tile" style="--accent:{color};--pale:{pale}" href="./{slug}/index.html">
        <div class="tile-top"><span>SETOR {index:02}</span><span class="tile-arrow" aria-hidden="true">↗</span></div>
        <h2>{esc(name)}</h2><p>{len(units)} {'unidade' if len(units) == 1 else 'unidades'}</p>
        <div class="tile-bottom"><span>{len(members)} servidores</span><strong>Conhecer equipe →</strong></div></a>''')
        jumps = ''.join(f'<a href="#unidade-{i}">{esc(unit)}</a>' for i, unit in enumerate(units, 1))
        sections = []
        for i, unit in enumerate(units, 1):
            group = sorted([p for p in members if (p['Unidade'] or 'Unidade indisponível') == unit], key=lambda p: p['Nome'].casefold())
            sections.append(f'<section class="unit-section" aria-labelledby="unidade-{i}"><div class="section-heading"><h2 id="unidade-{i}">{esc(unit)}</h2><span>{len(group)} {"servidor" if len(group) == 1 else "servidores"}</span></div><div class="faculty-grid">' + ''.join(card(p, {p['Siape']: p['Foto']}, '../') for p in group) + '</div></section>')
        body = f'''<div class="department-heading"><a class="back" href="../index.html">← Todos os setores</a>
        <div class="dept-title"><div><p class="eyebrow">CORPO ADMINISTRATIVO / CAMPUS ANGICOS</p><h1>{esc(name)}</h1>
        <p class="department-name">Conheça a equipe e suas unidades.</p></div><div class="dept-count"><strong>{len(members)}</strong><span>servidores</span></div></div></div>
        <nav class="unit-nav" aria-label="Unidades deste setor">{jumps}</nav>''' + ''.join(sections)
        folder = output / slug
        folder.mkdir(exist_ok=True)
        (folder / 'index.html').write_text(shell(name, body, '../', slug, color, pale), encoding='utf-8')
    home = f'''<section class="intro"><div><p class="eyebrow">UNIVERSIDADE FEDERAL RURAL DO SEMI-ÁRIDO</p><h1>Conheça o<br><em>corpo administrativo.</em></h1>
    <p class="intro-copy">As pessoas que fazem parte do Campus Angicos.<br>Encontre equipes, unidades e contatos.</p></div>
    <div class="intro-numbers"><div><strong>{len(people)}</strong><span>servidores</span></div><div><strong>{len(SECTORS):02}</strong><span>setores</span></div></div></section>
    <section aria-labelledby="setores"><div class="section-heading"><h2 id="setores">Explore por setor</h2><span>Equipes · Unidades · Contatos</span></div>
    <div class="department-grid">{''.join(tiles)}</div></section>
    <aside class="information"><span class="info-icon" aria-hidden="true">i</span><p>Selecione um setor para consultar seus servidores, organizados por unidade. Cada cartão reúne cargo, matrícula, aniversário e contatos disponíveis.</p></aside>'''
    (output / 'index.html').write_text(shell('Conheça nosso corpo administrativo', home), encoding='utf-8')
    missing = [p['Nome'] for p in people if not photos.get(p['Siape'])]
    print(json.dumps({'servidores': len(people), 'setores': counts, 'sem_foto_associada': missing}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    build()
