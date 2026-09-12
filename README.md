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

### GitHub Pages

O workflow `.github/workflows/deploy-pages.yml` gera as páginas a partir da
planilha e publica os HTML, CSS, favicon e fotos a cada push na branch `main`.
Novos setores são incluídos automaticamente. Credenciais, backups, planilha e
código do editor não entram no pacote público do Pages.

### Editor local

Execute com Python 3.10 ou superior, sem instalar dependências:

```powershell
python -X utf8 editor.py
```

Mantenha o terminal aberto e acesse http://127.0.0.1:8002/editor, ou use
**Editar Página** no rodapé da página principal. O link abre o editor na
máquina de quem clica e só funciona quando esse servidor local está em execução.

As credenciais desta máquina estão em `.editor-secrets.json`, ignorado pelo
Git; a senha fica como hash PBKDF2, não como texto puro. Em outra máquina,
ou para trocar o acesso, execute `python configurar_editor.py`.

- Use as abas **Servidores**, **Unidades** e **Setores** para criar, editar e
  excluir registros. Em um servidor, selecione setor e unidade para transferi-lo.
- Renomear um setor ou mover/renomear uma unidade atualiza seus servidores.
  Para excluir uma unidade ou setor, transfira ou exclua primeiro seus registros.
- Escolha uma foto já disponível em `photos`. Para adicionar outra imagem,
  copie-a para essa pasta e recarregue o editor antes de iniciar alterações.
- **Aplicar alteração** mantém a edição pendente. **Salvar na planilha** grava
  o conjunto de alterações e regenera as páginas locais. Feche o Excel antes.
- O primeiro salvamento cria as abas `EditorSetores` e `EditorUnidades` e as
  colunas `Foto` e `ID` em `TAES`. As fotos passam a ser escolhidas na planilha;
  `photos.json` é usado somente para importar as associações antigas.
- Cada gravação cria uma cópia da planilha em `.editor-backups`. Para restaurar,
  encerre o editor, copie o backup desejado sobre `Corpo Administrativo.xlsx`
  e execute `python -X utf8 build.py`.
- Alterações externas na planilha impedem sobrescrever uma versão antiga:
  recarregue o editor antes de continuar. Aniversários são gravados como dia/mês.

Para publicar as alterações locais, revise `git status`, faça commit da planilha,
das páginas e de eventuais fotos novas, e envie para `main`. O editor não executa
commit ou push automaticamente.

1. Em **Settings → Pages → Build and deployment → Source**, selecione
   **GitHub Actions**.
2. Envie o workflow para a branch `main`.
3. Acompanhe **Actions → Publicar site no GitHub Pages**. Também é possível
   iniciar uma publicação manualmente pelo botão **Run workflow**.
4. Após o job `deploy` terminar, o endereço aparece no ambiente `github-pages`.

Endereço esperado: https://leandromarques-ufersa.github.io/corpo_administrativo/

Esta pasta não foi adicionada ao workflow dos docentes; a publicação atual
dos docentes continua usando apenas `dist`. Não há consulta ao SIGAA nem
agendamento neste projeto administrativo.
