import copy
import re
import zipfile
from pathlib import Path
import workbook_store as w

book = Path('Corpo Administrativo.xlsx')
with zipfile.ZipFile(book) as z:
    files = {n: z.read(n) for n in z.namelist()}
with zipfile.ZipFile('.privacy-tmp/converted.xlsx') as z:
    converted = {n: z.read(n) for n in z.namelist()}
path = w.sheet_paths(files)['TAES']
before = w.read_rows(files, path)
after = w.read_rows(converted, w.sheet_paths(converted)['TAES'])
assert len(before) == len(after) == 42
for a, b in zip(before, after):
    assert all(a[k] == b[k] for k in a if k != 'Nascimento')
    assert re.fullmatch(r'\d{2}-\d{2}', b['Nascimento'])
# Transfer only the authored birthday values, retaining all unrelated OOXML.
sheet = w.ET.fromstring(files[path])
styles = w.ET.fromstring(files['xl/styles.xml'])
xfs = styles.find('{'+w.S+'}cellXfs')
style_map = {}
for row in sheet.findall('.//{'+w.S+'}sheetData/{'+w.S+'}row')[1:]:
    if int(row.get('r')) > len(after)+1:
        continue
    cell = next(c for c in row if c.get('r') == 'H'+row.get('r'))
    old_style = int(cell.get('s', '0'))
    if old_style not in style_map:
        xf = copy.deepcopy(xfs[old_style])
        xf.set('numFmtId', '49')
        xf.set('applyNumberFormat', '1')
        style_map[old_style] = str(len(xfs))
        xfs.append(xf)
    for child in list(cell):
        cell.remove(child)
    cell.set('s', style_map[old_style])
    cell.set('t', 'inlineStr')
    w.ET.SubElement(w.ET.SubElement(cell, '{'+w.S+'}is'), '{'+w.S+'}t').text = after[int(row.get('r'))-2]['Nascimento']
xfs.set('count', str(len(xfs)))
files[path] = w.serialize(sheet, files[path])
files['xl/styles.xml'] = w.serialize(styles, files['xl/styles.xml'])
candidate = Path('.privacy-tmp/final.xlsx')
with zipfile.ZipFile(candidate, 'w', zipfile.ZIP_DEFLATED) as z:
    for name, content in files.items():
        z.writestr(name, content)
with zipfile.ZipFile(book) as original, zipfile.ZipFile(candidate) as saved:
    for name in original.namelist():
        if name not in {path, 'xl/styles.xml'}:
            assert original.read(name) == saved.read(name), name
candidate.replace(book)
print('42 aniversários convertidos; demais células e componentes preservados.')
