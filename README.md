# Corpo Administrativo — UFERSA Angicos

Site estático independente, com a identidade visual do diretório de docentes.
Os dados vêm exclusivamente da aba `TAES` de `Corpo Administrativo.xlsx`.

## Abrir e atualizar

Dentro desta pasta, execute com Python 3, sem instalar bibliotecas:

```powershell
python -X utf8 build.py
python -m http.server 8001
```

Abra http://localhost:8001. Também é possível abrir `index.html` diretamente:
os links incluem o nome dos arquivos e usam caminhos relativos.

1. Edite a planilha mantendo os cabeçalhos e os cinco nomes de setores.
2. Salve as fotos em `photos`, o nome da pasta já existente no projeto.
3. Associe cada matrícula SIAPE ao arquivo em `photos.json`. Use `null` quando
   não houver foto identificada. A correspondência é explícita, sem reconhecimento facial.
4. Execute novamente `python -X utf8 build.py` para atualizar as seis páginas.

Altere o visual em `css/style.css` e a estrutura em `build.py`. Edições diretas
nos HTML serão substituídas pela próxima geração.

## Dados e organização

- Os cinco setores têm páginas próprias, com seções para cada valor de `Unidade`.
- Os 42 registros da planilha foram preservados. Pessoas presentes apenas no
  protótipo antigo não foram incluídas.
- Os cartões exibem nome, matrícula SIAPE, cargo, aniversário (dia/mês), ramal e
  WhatsApp. Campos vazios ou `-` aparecem como `Indisponível`.
- Datas numéricas do Excel são convertidas em dia/mês, sem exibir ano de nascimento.
- Cargos, nomes e unidades seguem a planilha, inclusive a grafia `Seguraça do Trabalho`.
- Os números completos de WhatsApp geram links quando tiverem DDD. Números
  incompletos são apresentados como texto, sem inventar um DDD.
- Christy Ally De Oliveira Lopes e Rodrigo Lacerda De Melo estão sem foto
  identificada e aparecem com iniciais. Arquivos de nomes genéricos não foram atribuídos.
- As associações de fotos foram feitas pelos nomes disponíveis, incluindo
  `Adressa.jpg` para Andressa e `Maria.png` para Maria José; podem ser ajustadas em `photos.json`.

O protótipo anterior está preservado em `referencia/index-anterior.html` e
`referencia/style-anterior.css` apenas como referência.

## Hospedagem

O projeto funciona na raiz ou em uma subpasta de um site estático. Para publicar,
envie `index.html`, `favicon.svg`, `css`, `photos` e as cinco pastas de setores.
A planilha e o gerador são usados apenas para produzir os HTML localmente.

Esta pasta não foi adicionada ao workflow dos docentes; a publicação atual
dos docentes continua usando apenas `dist`. Não há consulta ao SIGAA nem
agendamento neste projeto administrativo.
