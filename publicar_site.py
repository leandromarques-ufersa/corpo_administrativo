"""Prepara apenas os arquivos públicos, incluindo setores criados pelo editor."""
import shutil
from pathlib import Path
import build

output = Path('_site')
build.build(output=output)
(output/'css').mkdir(exist_ok=True)
for source in Path('css').glob('*.css'):
    shutil.copy2(source, output/'css'/source.name)
shutil.copy2('favicon.svg', output/'favicon.svg')
shutil.copytree('photos', output/'photos', dirs_exist_ok=True)
