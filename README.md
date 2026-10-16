# Enciclopédia das Ervas Sagradas

Aplicação Flask com catálogo cultural e espiritual, filtros, comparação de ervas e painel administrativo protegido. O SQLite da pasta atual contém 142 registros após a migração suplementar; a aplicação cria e migra o banco automaticamente ao iniciar.

## Executar localmente

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:SECRET_KEY = py -c "import secrets; print(secrets.token_hex(32))"
$env:ADMIN_USERNAME = "admin"
$env:ADMIN_PASSWORD_HASH = py -c "from werkzeug.security import generate_password_hash; print(generate_password_hash(input('Nova senha: ')))"
py app.py
```

Abra `http://127.0.0.1:5000`; o cat?logo ? p?blico e n?o exige conta. O painel administrativo fica em `/admin`. Em desenvolvimento, as credenciais podem ser configuradas por vari?veis de ambiente ou pelo arquivo local ignorado `instance/admin_credentials.json`. O painel nunca fica aberto sem autentica??o.

## Acesso ao cat?logo

O cat?logo e a API s?o p?blicos. Somente o painel administrativo exige usu?rio e senha; n?o h? contas de leitores.

## Publicação

O `Procfile` inicia Gunicorn com debug desativado. Configure estas variáveis no serviço de hospedagem:

- `APP_ENV=production`
- `SECRET_KEY`: valor aleatório longo e persistente entre reinicializações.
- `ADMIN_USERNAME` e `ADMIN_PASSWORD_HASH`: usuário e hash da senha, nunca a senha em texto puro.
- `DATABASE_PATH`: caminho para arquivo SQLite em volume persistente gravável, por exemplo `/data/ervas.db`.
- `PORT`: fornecida pela plataforma.

Gere uma chave com `python -c "import secrets; print(secrets.token_hex(32))"`. Gere o hash com `python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash(input('Senha: ')))"` e salve os valores no gerenciador de segredos da hospedagem.

SQLite requer armazenamento persistente e é adequado para uma única instância da aplicação. Não compartilhe um arquivo SQLite entre várias instâncias/hosts. Para escalar horizontalmente, migre o backend de dados para um banco gerenciado, como PostgreSQL, com adaptador e migrações apropriados.

## Conteúdo e segurança de saúde

O catálogo reúne associações culturais e espirituais. Os usos tradicionais aqui descritos não comprovam eficácia nem segurança clínica. As 142 fichas ainda não passaram por revisão clínica individual; contraindicações e fontes por espécie são marcadas como não avaliadas até que alguém as revise. Não use as descrições como receita ou orientação para ingestão, aplicação tópica ou inalação.

Referências gerais consultadas:

- [Anvisa — Formulário de Fitoterápicos](https://www.gov.br/anvisa/pt-br/assuntos/farmacopeia/formulario-fitoterapico)
- [Ministério da Saúde — Plantas medicinais e fitoterapia](https://www.gov.br/saude/pt-br/composicao/saps/pics/as-praticas/plantas-medicinais-2013-fitoterapia)

Esses materiais são referências de segurança e regulação; não validam automaticamente as afirmações de cada ficha. Ao revisar uma espécie, registre a fonte correspondente ao nome científico e as contraindicações conhecidas no painel administrativo.

## Estrutura

```text
app.py                 Flask, autenticação, validação e acesso SQLite
ervas.db               banco local (ignorado pelo Git)
templates/             páginas Jinja, incluindo login e administração
static/css/             estilos
static/js/              filtros, modal, comparação e tema
requirements.txt        dependências
Procfile                inicialização de produção com Gunicorn
```

