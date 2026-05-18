# Gerador de Link de Pagamento Cielo — Grupo LLE (Streamlit)

Aplicação Streamlit para gerar links de pagamento Cielo, com histórico no Google Sheets e autenticação por senha. Pronta pra subir no Streamlit Community Cloud (gratuito).

## Recursos

- 🔐 Login por senha compartilhada
- 💳 Geração de links de pagamento Cielo via API
- 📊 Histórico persistente em uma planilha do Google Sheets
- ✅ Acompanhamento de pagamentos (Pagos / Não pagos)
- 🎨 Identidade visual do Grupo LLE

---

## Passo 1: Configurar Google Cloud + Sheets

Esse passo é o mais demorado, mas só precisa fazer uma vez. Leva uns 8 minutos.

### 1.1 Criar projeto e habilitar APIs

1. Acesse [console.cloud.google.com](https://console.cloud.google.com) e faça login
2. Crie um projeto novo (ex: `link-cielo-grupolle`)
3. No menu lateral, vá em **APIs & Services → Library**
4. Procure e clique em **Enable** para cada uma destas:
   - **Google Sheets API**
   - **Google Drive API**

### 1.2 Criar a Service Account

1. **APIs & Services → Credentials → Create Credentials → Service Account**
2. Preencha:
   - **Service account name:** `link-cielo-bot` (qualquer nome)
   - **Service account ID:** preenche automaticamente
3. Clique em **Create and Continue**
4. Em "Grant access" pode pular (Continue)
5. Em "Grant users access" pode pular (Done)

### 1.3 Gerar a chave JSON da Service Account

1. Na lista de Service Accounts, clique no que você acabou de criar
2. Aba **Keys → Add Key → Create new key**
3. Tipo: **JSON** → **Create**
4. Vai baixar um arquivo `.json` — guarde com segurança, é a credencial de acesso
5. Anote o **email da service account** (algo como `link-cielo-bot@seu-projeto.iam.gserviceaccount.com`)

### 1.4 Criar a planilha e compartilhar com a Service Account

1. Acesse [sheets.google.com](https://sheets.google.com) e crie uma planilha nova
2. Dê um nome (ex: `Link Cielo — Histórico Grupo LLE`)
3. Clique em **Compartilhar** (botão azul no canto superior direito)
4. Cole o email da service account (do passo 1.3)
5. Permissão: **Editor**
6. **Desmarque** "Notificar pessoas" e clique em **Compartilhar**
7. Copie o **ID da planilha** da URL — está entre `/d/` e `/edit`:
   ```
   https://docs.google.com/spreadsheets/d/[ID-AQUI]/edit
   ```

> ✅ A planilha começa vazia. Na primeira vez que o app rodar, ele cria automaticamente o cabeçalho na linha 1. Você não precisa preparar nada na planilha — só compartilhar com a service account.

---

## Passo 2: Configurar o repositório no GitHub

1. Crie um novo repositório no GitHub (recomendado **privado**)
2. Faça upload de todos os arquivos deste projeto **EXCETO** `.streamlit/secrets.toml`
   - O `.gitignore` já protege esse arquivo automaticamente

---

## Passo 3: Subir no Streamlit Community Cloud

1. Acesse [share.streamlit.io](https://share.streamlit.io) e faça login com GitHub
2. Clique em **New app**
3. Preencha:
   - **Repository:** seu repositório
   - **Branch:** `main`
   - **Main file path:** `app.py`
4. Antes de clicar em "Deploy", abra **Advanced settings**
5. Em **Secrets**, cole o conteúdo (formato TOML):

```toml
APP_PASSWORD = "uma-senha-forte-aqui"

CIELO_CLIENT_ID = "seu_client_id_da_cielo"
CIELO_CLIENT_SECRET = "seu_client_secret_da_cielo"

GOOGLE_SHEET_ID = "id_da_sua_planilha"

[gcp_service_account]
type = "service_account"
project_id = "seu-projeto"
private_key_id = "abc123..."
private_key = """-----BEGIN PRIVATE KEY-----
... (conteúdo da private_key do JSON, MANTENHA as quebras de linha) ...
-----END PRIVATE KEY-----
"""
client_email = "link-cielo-bot@seu-projeto.iam.gserviceaccount.com"
client_id = "123456789"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "https://www.googleapis.com/robot/v1/metadata/x509/link-cielo-bot%40seu-projeto.iam.gserviceaccount.com"
universe_domain = "googleapis.com"
```

> 💡 **Dica importante** sobre a `private_key`: ela vem como uma string única no JSON com `\n` (barra-N) entre as linhas. No TOML use **aspas triplas (`"""`)** e cole exatamente como está, ou substitua os `\n` por quebras de linha reais. O Streamlit aceita ambos.

6. Clique em **Deploy**
7. Aguarde 2-3 minutos enquanto o app é construído
8. URL final: `https://link-cielo-grupolle.streamlit.app` (ou similar)

---

## Passo 4: Compartilhar com a equipe

Envie a URL final e a `APP_PASSWORD` pros colegas.

> ⚠️ **Cuidado:** qualquer pessoa com a URL e a senha consegue gerar links de pagamento reais. Compartilhe com responsabilidade.

---

## Como rodar localmente (para desenvolvimento)

```bash
# 1. Ambiente virtual
python -m venv .venv
.venv\Scripts\activate           # Windows
source .venv/bin/activate         # macOS/Linux

# 2. Instalar dependências
pip install -r requirements.txt

# 3. Criar secrets.toml local
copy .streamlit\secrets.toml.example .streamlit\secrets.toml    # Windows
cp .streamlit/secrets.toml.example .streamlit/secrets.toml       # macOS/Linux

# 4. Editar o .streamlit/secrets.toml com os valores reais

# 5. Rodar
streamlit run app.py
```

App abre em `http://localhost:8501`.

---

## Estrutura do projeto

```
cielo-link-streamlit/
├── app.py                          # Aplicação principal Streamlit
├── components/
│   └── ui.py                       # Tema e componentes visuais
├── utils/
│   ├── auth.py                     # Autenticação por senha
│   ├── cielo_client.py             # Cliente da API Cielo
│   └── database.py                 # Persistência no Google Sheets
├── assets/
│   └── logo.png                    # Logo Grupo LLE
├── .streamlit/
│   ├── config.toml                 # Tema Streamlit
│   └── secrets.toml.example        # Template de secrets
├── requirements.txt
├── .gitignore
└── README.md
```

---

## Como atualizar o app depois

1. Edite os arquivos localmente
2. Commit e push no GitHub
3. O Streamlit Cloud **atualiza sozinho** em 1-2 minutos

---

## Troubleshooting

### "APIError: [403] The caller does not have permission"
A planilha não foi compartilhada com a service account. Volta no passo 1.4 e adicione o email da service account como Editor.

### "SpreadsheetNotFound"
O `GOOGLE_SHEET_ID` está errado nos secrets. Pega na URL da planilha, entre `/d/` e `/edit`.

### "google.auth.exceptions.MalformedError: No key could be detected"
A `private_key` foi colada de forma incorreta. Use aspas triplas `"""..."""` no TOML e mantenha o `-----BEGIN PRIVATE KEY-----` / `-----END PRIVATE KEY-----`.

### "Erro na Cielo: Falha ao gerar token (HTTP 401)"
Credenciais Cielo incorretas. Verifique no painel da Cielo se foram geradas pelo caminho **E-commerce → Link de Pagamento → Configurações → Dados Cadastrais → Gerar Credenciais de Acesso às APIs**.

### Atualizações no GitHub não refletem no app
Vai no painel do Streamlit Cloud e clique em **Reboot app**.

---

## Detalhes técnicos

### Sobre a planilha Google
- Acesso é controlado por uma **Service Account** (conta de serviço), não pelo seu login pessoal
- A planilha permanece sob seu controle — você pode abrir, editar e excluir manualmente quando quiser
- A primeira aba é usada como banco; **não mexa no cabeçalho** (linha 1)
- Você pode adicionar mais abas pra outras coisas, o programa não interfere

### Cache da conexão
A conexão com o Google Sheets é cacheada via `@st.cache_resource` — não autentica a cada interação, melhorando performance.

### Rate limit do Google Sheets
A API gratuita permite **60 reads + 60 writes por minuto** por usuário. Pra uso interno de pequena/média equipe é mais que suficiente. Se precisar escalar muito, considere mover pra Supabase ou outro DB.

### Limitações do Streamlit Cloud (plano gratuito)
- App "dorme" após inatividade prolongada — primeiro acesso depois disso demora ~30s pra acordar
- 1GB de RAM por app, suficiente pra essa aplicação
- Permite só repositórios públicos no plano gratuito — se quiser privado, é Pro
