# Corpo Administrativo — UFERSA Angicos

Site estático independente, com a identidade visual do diretório de docentes.
O cadastro é editado diretamente em `Corpo Administrativo.xlsx`, nas abas
`TAES`, `EditorSetores` e `EditorUnidades`. A aba `Como editar` contém o guia.

## Abrir e atualizar

Dentro desta pasta, execute com Python 3, sem instalar bibliotecas:

```powershell
python -X utf8 build.py
python -m http.server 8001
```

Abra http://localhost:8001. Também é possível abrir `index.html` diretamente:
os links incluem o nome dos arquivos e usam caminhos relativos.

1. Edite os servidores na aba `TAES`. Cada linha é um cartão: acrescente uma
   linha para criar, altere os campos para editar ou exclua a linha inteira.
2. Arraste as imagens para a pasta `photos` do projeto. Na coluna `Foto`,
   informe **somente o nome exato do arquivo**, por exemplo `maria-silva.jpg`.
   Não insira a imagem na célula, nem um caminho do Windows ou uma URL.
   Deixe a célula vazia para mostrar as iniciais, sem foto.
3. Cadastre setores e unidades nas abas correspondentes, conforme abaixo.
4. Salve a planilha. Para conferir localmente, execute `python -X utf8 build.py`
   e abra `index.html`. O editor local não precisa estar em execução.
5. Envie a planilha e as fotos novas para a branch `main`. O workflow gera
   as páginas automaticamente antes de publicar no GitHub Pages.

### Setores, unidades e fotos pela planilha

Em `EditorSetores`, cada linha representa um setor:

| Coluna | Preenchimento |
| --- | --- |
| Nome | Nome completo, obrigatório. |
| Endereço | Parte do link, como `biblioteca`. Use letras minúsculas, números e hífens. Se vazio, é gerado pelo nome. Mantenha estável ao renomear o setor para preservar seus links. |
| Nome no menu | Nome curto; se vazio, usa o nome completo. |
| Cor / Fundo | Cores como `#1943c9` e `#edf2ff`; opcionais. |

Em `EditorUnidades`, preencha `Setor` com o nome exato de um setor cadastrado
e `Unidade` com o nome da unidade. Para novos registros, deixe `ID` vazio;
o gerador cria o identificador em memória. Mantenha os IDs existentes e não
copie o ID de outra linha. A mesma regra vale para `ID` em `TAES`.

Para transferir um servidor, altere `Setor` e `Unidade` em `TAES`. Ao renomear
um setor ou unidade, atualize o nome também nas linhas correspondentes das
outras abas. Para excluir um setor/unidade, primeiro transfira ou exclua seus
registros dependentes. Setores e unidades sem servidores são permitidos.

Exemplo: `Foto = maria-silva.jpg` aponta para `photos/maria-silva.jpg`.
Nas páginas dos setores, o HTML usa `../photos/maria-silva.jpg`, funcionando
também no endereço do GitHub Pages. Maiúsculas, minúsculas e extensão precisam
coincidir exatamente. São aceitas imagens JPG, JPEG, PNG, WEBP e GIF.

Não é necessário editar `photos.json`: ele serve apenas para compatibilidade
com planilhas antigas sem a coluna `Foto`. A validação ocorre antes de gerar
páginas e impede publicar referências inválidas, SIAPEs/IDs duplicados,
aniversários inválidos ou fotos inexistentes. Corrija o erro informado e tente
novamente. A geração não grava alterações na planilha.

Altere o visual em `css/style.css` e a estrutura em `build.py`. Edições diretas
nos HTML serão substituídas pela próxima geração.

## Dados e organização

- Cada setor cadastrado tem uma página própria, com seções para suas unidades.
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
  `Adressa.jpg` para Andressa e `Maria.png` para Maria José; podem ser ajustadas na coluna `Foto` de `TAES`.

O protótipo anterior está preservado em `referencia/index-anterior.html` e
`referencia/style-anterior.css` apenas como referência.

## Hospedagem

O projeto funciona na raiz ou em uma subpasta de um site estático. Para publicar,
envie `index.html`, `favicon.svg`, `css`, `photos` e as pastas dos setores cadastrados.
A planilha e o gerador são usados apenas para produzir os HTML localmente.

### GitHub Pages

O workflow `.github/workflows/deploy-pages.yml` gera as páginas a partir da
planilha e publica os HTML, CSS, favicon e fotos a cada push na branch `main`.
Novos setores são incluídos automaticamente. Credenciais, backups, planilha e
código do editor não entram no pacote público do Pages.

### Editor local (opcional)

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
- A planilha já está preparada com `EditorSetores`, `EditorUnidades`, `Foto`
  e `ID`. O editor local continua compatível com essas mesmas abas e colunas.
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
