# Configurar e publicar a KIKO

Este guia parte de um projeto novo. No final terá **um repositório GitHub**, a interface no **GitHub Pages**, a API no **Render** e quatro contas no **Firebase Authentication**. Não precisa de criar qualquer base de dados.

Os exemplos `UTILIZADOR`, `SEU-PROJETO` e `https://kiko-api.onrender.com` são marcadores: substitua-os pelos valores que os seus serviços mostrarem. Não são serviços já criados.

## 1. Preparar os ficheiros e o GitHub

1. Extraia `KIKO_projeto_completo.zip` no computador. Dentro encontrará a pasta `kiko`.
2. Entre em [GitHub](https://github.com/) e escolha **New repository**. Nome: `kiko`. Pode usar um repositório público, porque os segredos serão configurados fora dele.
3. Se utilizar um plano que permita Pages em repositórios privados, pode optar por privado. Confirme as condições do seu plano.
4. Para carregar sem terminal: no repositório, escolha **Add file → Upload files** e arraste o **conteúdo** da pasta `kiko`. A raiz do repositório deve mostrar `frontend`, `backend`, `.github`, `render.yaml` e os guias. Não crie uma segunda pasta `kiko` dentro do repositório.
5. Certifique-se de que `.github/workflows/pages.yml` e `.github/workflows/test.yml` foram incluídos. Alguns gestores de ficheiros podem ocultar nomes começados por ponto. Uma alternativa mais simples para atualizações frequentes é o [GitHub Desktop](https://desktop.github.com/): clone o repositório, copie o conteúdo para a pasta clonada e faça **Commit → Push**.
6. Use o ramo principal `main`. Se preferir outro nome, ajuste `branches: [main]` em `pages.yml`.

Não carregue `.env`, credenciais JSON, tokens Kaggle ou os três prompts privados. O `.gitignore` ajuda no Git, mas **não impede** carregar ficheiros manualmente pelo site. Revise o que está a publicar.

## 2. Criar o Firebase e as quatro contas

### 2.1 Projeto e aplicação Web

1. Abra a [consola Firebase](https://console.firebase.google.com/).
2. Escolha **Adicionar projeto**, dê-lhe um nome e conclua a criação. Google Analytics não é necessário.
3. Nas definições do projeto, adicione uma **aplicação Web**, identificada pelo símbolo `</>`.
4. Dê-lhe o nome `KIKO`. Não precisa de Firebase Hosting.
5. Guarde os valores de configuração pública: `apiKey`, `authDomain`, `projectId` e `appId`.

### 2.2 Ativar email e palavra-passe

1. Entre em **Build → Authentication → Get started**.
2. Em **Sign-in method**, ative **Email/Password**.
3. Ative apenas a opção de email/palavra-passe; ligação por email sem palavra-passe não é necessária.
4. Não é necessário ativar Google, Apple ou outros fornecedores.
5. Em **Users**, escolha **Add user** e crie manualmente cada uma das quatro contas.
6. Guarde o **UID** de cada conta. UID é o identificador da conta, não o email.
7. Prepare uma lista sem espaços, no formato `UID1,UID2,UID3,UID4`. Esta lista será usada apenas no backend.

A ausência de formulário de registo na KIKO não substitui a autorização do servidor. Mesmo que exista outra conta Firebase, só os quatro UIDs permitidos podem chamar a API.

### 2.3 Domínios autorizados e recuperação

1. Em **Authentication → Settings → Authorized domains**, acrescente `UTILIZADOR.github.io`.
2. Acrescente o seu domínio próprio se o utilizar.
3. Para desenvolvimento, confirme também `localhost` e `127.0.0.1` se necessários; não assuma que foram adicionados automaticamente.
4. Os domínios autorizados não incluem `https://`, portas ou `/kiko/`.
5. Em **Templates**, pode personalizar o email de recuperação de palavra-passe. O botão da KIKO usa o mecanismo oficial Firebase e exige primeiro um email válido.

### 2.4 Credenciais privadas do backend

1. Nas definições do projeto, abra **Service accounts → Firebase Admin SDK**.
2. Gere uma chave privada da conta de serviço e descarregue o JSON.
3. Guarde-a num local seguro. **Não a carregue no GitHub nem no frontend.**
4. No Render, será guardada como Secret File com o nome `firebase-admin.json`.
5. Guarde também o **Project ID**, que terá de corresponder ao projeto do frontend e à conta de serviço.

Alternativa: definir o JSON completo em `FIREBASE_SERVICE_ACCOUNT_JSON`, como segredo do Render. Escolha uma das alternativas. Se ambas estiverem definidas, o JSON da variável tem prioridade. O modo recomendado neste guia usa o ficheiro e `GOOGLE_APPLICATION_CREDENTIALS=/etc/secrets/firebase-admin.json`.

## 3. Preparar o Kaggle e escolher o modelo

1. Utilize uma conta Kaggle com acesso ao serviço de Model Proxy/Benchmarks.
2. Nas definições da conta Kaggle, obtenha o token adequado ao CLI e à variável `KAGGLE_API_TOKEN`. Não confunda este token com as credenciais **temporárias** do Model Proxy, que o servidor obtém automaticamente.
3. O backend executa `kaggle benchmarks init -y --env-file ... --example-file ...` numa pasta temporária e lê `MODEL_PROXY_URL`, `MODEL_PROXY_API_KEY`, `MODEL_PROXY_EXPIRY_TIME` e `LLMS_AVAILABLE`.
4. Escolha **um modelo realmente devolvido por essa lista**. Não copie um nome comercial só porque aparece num exemplo.
5. Defina esse ID em `KIKO_MODEL`. Pode usar um alias existente ou `MODEL_ALIASES_JSON`, mas a resolução só é aceite se o ID final existir nas credenciais atuais.
6. Para fotografias, escolha um modelo com capacidade visual. Um modelo só de texto pode recusar imagens.

### Consultar a lista real sem divulgar credenciais

Se já tiver Python 3.12 no computador, abra um terminal na pasta `kiko`, crie/ative o ambiente virtual conforme a secção 8 e instale as dependências. Defina `KAGGLE_API_TOKEN` em `.env` e execute:

```sh
python tools/check_kaggle.py
```

O programa carrega `.env` e apresenta apenas os IDs disponíveis. Não mostra a URL privada nem a chave temporária. Precisa de acesso real ao Kaggle; não é um catálogo simulado.

Pode também executar `kaggle benchmarks init --help` para verificar a versão e as opções do CLI. A disponibilidade do Model Proxy e as quotas dependem da conta Kaggle.

## 4. Publicar o backend no Render

### 4.1 Criar o serviço a partir do mesmo repositório

1. Entre no [Render](https://dashboard.render.com/).
2. Escolha **New → Blueprint** e ligue o repositório `kiko`.
3. O Render encontra `render.yaml` na raiz e propõe o serviço `kiko-api`.
4. O Dockerfile é `./backend/Dockerfile`; o contexto de construção é a **raiz do repositório** (`.`). Não altere o contexto para `backend`, porque os caminhos `COPY` partem da raiz.
5. O Blueprint usa o plano `free` para facilitar o primeiro teste. Reveja a disponibilidade e condições mostradas no painel. Pode escolher um plano adequado a utilização regular.
6. Preencha as variáveis pedidas. Um primeiro deploy pode ficar sem a configuração completa; o health check continuará a funcionar, mas o chat devolverá erro de configuração até os segredos estarem disponíveis.
7. Não crie uma base de dados nem um disco persistente.
8. Mantenha **uma única instância** e **um único worker**. O Dockerfile já usa `--workers 1`.

Também pode criar um **Web Service → Docker** manualmente, com os mesmos caminhos e variáveis. A porta é lida de `$PORT`; não fixe a porta externa no Render. O arranque é o `CMD` do Dockerfile.

### 4.2 Variáveis de ambiente

| Variável | Valor/objetivo |
|---|---|
| `KIKO_ENV` | `production` no Render; `development` apenas no computador de desenvolvimento. |
| `KAGGLE_API_TOKEN` | Token privado da sua conta Kaggle. |
| `KIKO_MODEL` | ID real ou alias que resolve para um ID da lista `LLMS_AVAILABLE` atual. |
| `KIKO_ALLOWED_UIDS` | Os quatro UIDs Firebase separados por vírgulas. Aceita entre um e quatro durante a configuração. |
| `FIREBASE_PROJECT_ID` | Project ID do mesmo projeto usado no frontend. |
| `GOOGLE_APPLICATION_CREDENTIALS` | `/etc/secrets/firebase-admin.json` quando usa o Secret File recomendado. |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | Alternativa: JSON privado completo numa variável; deixe ausente se usar o ficheiro. |
| `KIKO_PROMPTS_DIR` | `/etc/secrets` no Render. |
| `CORS_ORIGINS` | Origem completa do Pages, por exemplo `https://UTILIZADOR.github.io`. **Sem `/kiko/` e sem `*`.** |
| `STREAM_MODE` | `auto` recomendado. `native` exige tentativa de SSE; aceita uma resposta JSON completa se o serviço ignorar o pedido. `emulate` pede uma resposta completa e envia-a num único evento, sem animação artificial. |
| `MAX_FILE_MB` | `10` por omissão; inteiro de 1 a 30. |
| `MAX_TOTAL_MB` | `50` por omissão; máximo 300. Limite partilhado por todas as contas. |
| `MAX_FILES` | `20` por omissão; máximo 200, partilhado. |
| `FILE_TTL_HOURS` | `6` por omissão; máximo 72. |
| `MAX_DOC_CHARS` | `35000` por omissão; máximo 100000 por documento. |
| `MAX_CONTEXT_CHARS` | `120000` por omissão; máximo 300000 para texto e documentos de todo o pedido. |
| `MAX_ATTACHMENTS` | `4` por mensagem; máximo 8. Existe ainda limite de 12 referências a anexos em todo o contexto. |
| `RATE_LIMIT_PER_MINUTE` | `20` por omissão; máximo 120 por UID, separadamente para chat e uploads. Uma geração simultânea por UID; até quatro no serviço. |
| `KAGGLE_CHAT_PATH` | Opcional, `/openapi/v1/chat/completions` por omissão, preservado do servidor original. Altere apenas se a integração da sua conta o exigir. |
| `MODEL_ALIASES_JSON` | Opcional, objeto JSON de aliases privados, por exemplo `{"meu-alias":"ID_REAL_DISPONIVEL"}`. Não acrescenta modelos à sua conta. |
| `KIKO_ALLOW_EXAMPLE_PROMPTS` | Apenas para desenvolvimento, `true` permite exemplos. Em produção são sempre recusados como fallback. |

Para várias origens CORS, separe por vírgulas:

```text
https://UTILIZADOR.github.io,https://kiko.seudominio.pt
```

Durante desenvolvimento:

```text
http://localhost:5500,http://127.0.0.1:5500
```

A aplicação rejeita valores numéricos fora dos intervalos, em vez de aceitar uploads sem limite. Não reduza os limites abaixo das necessidades do seu uso sem considerar os anexos já presentes.

### 4.3 Secret Files

No painel do serviço Render, entre em **Environment → Secret Files** e adicione:

| Nome | Conteúdo |
|---|---|
| `firebase-admin.json` | O JSON da conta de serviço Firebase. |
| `learn.txt` | O prompt privado para Learn. |
| `think.txt` | O prompt privado para Think. |
| `quick.txt` | O prompt privado para Quick. |

Os três prompts devem ser TXT UTF-8, não vazios, com até 30000 caracteres. Para começar, pode copiar os textos genéricos dos ficheiros `.example.txt` e depois personalizá-los. Guarde-os nos Secret Files com os nomes **sem `.example`**.

Prioridade dos prompts:

1. Um diretório explicitamente definido por `KIKO_PROMPTS_DIR` é a localização autoritativa para os três ficheiros.
2. Sem diretório definido, procura `/etc/secrets`.
3. Apenas em desenvolvimento, procura depois `backend/prompts-private/`.
4. Apenas em desenvolvimento e com `KIKO_ALLOW_EXAMPLE_PROMPTS=true`, usa os exemplos genéricos.

Em produção, a falta de um prompt resulta em **503 com mensagem de configuração**. Não é substituído silenciosamente pelo exemplo. O servidor lê o TXT em cada pedido, sem cache dos prompts; após alterar Secret Files, aplique as alterações/redeploy no Render para que o ficheiro montado seja atualizado.

### 4.4 Confirmar que a API arrancou

1. Guarde as variáveis e Secret Files e execute **Deploy latest commit** ou a opção equivalente.
2. Aguarde o estado **Live**.
3. Copie a URL real do serviço, por exemplo `https://kiko-api-xxxx.onrender.com`.
4. Abra `https://URL-REAL/api/health`. Deve ver `{"status":"ok"}`.
5. Abrir `/api/me` diretamente, sem token, deve devolver **401**. Isso é esperado.
6. O health check confirma que o processo está ativo; não valida sozinho Firebase, prompts ou Kaggle. Esses pontos são testados com login e mensagem real.

O serviço pode suspender-se por inatividade conforme o plano escolhido. O primeiro pedido poderá demorar mais e os anexos anteriores podem ter desaparecido. A KIKO informa falhas; não apresenta IA offline.

## 5. Configurar e publicar o frontend

### 5.1 Preencher a configuração pública

Edite `frontend/js/config.js` no GitHub ou no computador:

```js
export const config = Object.freeze({
  apiBaseUrl: 'https://URL-REAL-DO-SEU-SERVICO.onrender.com',
  firebase: {
    apiKey: 'CHAVE_PUBLICA_DA_APP_WEB',
    authDomain: 'SEU-PROJETO.firebaseapp.com',
    projectId: 'SEU-PROJETO',
    appId: 'ID_DA_APP_WEB',
  },
});
```

Não acrescente `/api` ao endereço do servidor. A API deve ser HTTPS em produção. A chave `apiKey` da aplicação Web Firebase é configuração pública; **não é** a chave privada da conta de serviço. Não acrescente `KAGGLE_API_TOKEN`, UIDs ou prompts a este ficheiro.

### 5.2 Ativar Pages

1. Abra **Settings → Pages** do repositório.
2. Em **Build and deployment → Source**, escolha **GitHub Actions**.
3. Vá a **Actions → Publicar frontend KIKO → Run workflow**, se o carregamento anterior ainda não o executou.
4. Aguarde o resultado verde. O workflow publica **exclusivamente `frontend/`**.
5. A URL aparece no job de deployment e em Settings → Pages. Normalmente é `https://UTILIZADOR.github.io/kiko/`.
6. Confirme que CSS, logótipo e ícones carregam. Os caminhos são relativos e suportam `/kiko/`.
7. Confirme que `CORS_ORIGINS` no Render tem a origem `https://UTILIZADOR.github.io`, e que o domínio está autorizado no Firebase.

As mudanças em `frontend/` no ramo `main` voltam a publicar a interface automaticamente. Mudanças no backend seguem o mecanismo de deploy do Render. Testes estão num workflow separado; confirme também o resultado desse workflow antes de disponibilizar uma atualização às quatro pessoas.

## 6. Primeira utilização e teste real

1. Abra a URL Pages, online, e inicie sessão com uma das quatro contas.
2. Confirme que o email aparece no menu da conta.
3. Escolha **Think**, envie uma pergunta curta e confirme uma resposta real do Kaggle.
4. Escolha **Learn** e envie uma segunda mensagem relacionada. O contexto anterior deve permanecer.
5. Escolha **Quick** e confirme o novo estilo de resposta.
6. Durante uma resposta longa, toque em **Parar**. O texto já recebido deve permanecer, e o botão de enviar deve voltar a estar disponível.
7. Experimente **Copiar** e **Regenerar**. A regeneração da última resposta usa o modo atualmente selecionado.
8. Anexe uma imagem e um TXT ou PDF com texto. Leia os limites no botão **Limites dos anexos**.
9. Um modelo sem capacidades visuais pode recusar a imagem; altere o único modelo do servidor para um modelo visual disponível se precisar desta função.
10. Toque em **Nova conversa**. As mensagens e anexos da composição devem desaparecer, mantendo o login.
11. Termine sessão. O estado temporário deve ser limpo.
12. Atualize a página: o Firebase pode manter o login, mas a conversa não deve regressar.

### Verificar uma quinta conta

Crie temporariamente uma quinta conta no Firebase, **sem** acrescentar o UID a `KIKO_ALLOWED_UIDS`. Tente entrar na KIKO: o Firebase pode autenticar, mas a API deve devolver **403** e a interface deve informar que a conta não está autorizada. A aplicação termina essa sessão. Confirme este resultado antes de entregar o acesso às quatro pessoas.

### Formatos e limitações reais

- JPG/JPEG, PNG, WebP e GIF: descodificados e convertidos para JPEG. Apenas a primeira imagem de GIF animado.
- HEIC/HEIF: conversão com `pillow-heif`; algumas variantes/codificações podem não ser descodificáveis e são recusadas.
- PDF: texto das primeiras 40 páginas; ficheiros protegidos ou só com digitalizações são recusados quando não há texto. Não existe OCR.
- DOCX: texto de parágrafos e tabelas.
- TXT, Markdown, CSV, JSON: texto UTF-8; JSON tem de ser válido.
- XLSX: nomes de folhas e células, usando valores calculados já guardados; não executa fórmulas ou macros.
- PPTX: texto e tabelas; não interpreta imagens ou o aspeto gráfico dos diapositivos.
- ZIP e formatos executáveis: recusados. Os contentores OOXML são inspecionados com limites de expansão e de estrutura antes de serem lidos.

A aplicação envia o contexto completo disponível e não faz remoção silenciosa de mensagens antigas para caber no modelo. Se os limites da KIKO ou do modelo forem excedidos, inicie uma nova conversa. Um anexo que expirou ou se perdeu num reinício precisa de ser anexado novamente numa nova conversa.

## 7. Instalar no iPhone e Android

### iPhone

1. Abra a URL HTTPS da KIKO no Safari.
2. Toque em **Partilhar → Adicionar ao ecrã principal** e confirme o nome KIKO.
3. Abra pelo ícone criado e inicie sessão.
4. Confirme a escrita com o teclado aberto, incluindo no fim de uma conversa longa. Em telemóvel, Enter cria uma nova linha; envie pelo botão de seta.

### Android

1. Abra a URL HTTPS no Chrome.
2. No menu do Chrome, escolha **Instalar aplicação** ou **Adicionar ao ecrã principal**, conforme a opção apresentada.
3. Abra pelo ícone e inicie sessão.

A PWA pode abrir a estrutura da interface sem rede depois de a ter carregado, mas precisa de internet para autenticação, anexos e IA. O service worker não guarda chamadas privadas. Não existe botão fictício de instalação: a instalação usa as opções reais do navegador.

O layout usa `100dvh`, `visualViewport` e safe areas; os testes DOM não substituem a validação do teclado num iPhone/Android físico. Faça esta verificação nas versões dos dispositivos que vão ser usados.

## 8. Desenvolvimento e testes no computador

### Windows, PowerShell

Instale Python 3.12 e, para os testes JavaScript, Node.js 24.15 ou superior. Na pasta do projeto:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements-test.txt
Copy-Item .env.example .env
```

Se a ativação de scripts não for permitida no computador, use diretamente `.\.venv\Scripts\python.exe` em vez de alterar políticas de segurança. Edite `.env`, coloque a conta de serviço fora do repositório e defina o seu caminho em `GOOGLE_APPLICATION_CREDENTIALS`. Em Windows, pode usar `/` nos caminhos, por exemplo `C:/Segredos/firebase-admin.json`.

### macOS/Linux

```sh
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -r backend/requirements-test.txt
cp .env.example .env
```

Para prompts privados locais, crie `backend/prompts-private` e os três TXT. A pasta é ignorada pelo Git. Para testar os exemplos, use `KIKO_ENV=development`, `KIKO_ALLOW_EXAMPLE_PROMPTS=true` e deixe `KIKO_PROMPTS_DIR` vazio. Estes valores não devem substituir a configuração de produção.

### Arranque local

Na raiz:

```sh
python -m uvicorn app.main:app --app-dir backend --env-file .env --port 8000 --workers 1 --no-access-log
```

Noutro terminal, na raiz:

```sh
python -m http.server 5500 --directory frontend
```

Defina `apiBaseUrl: 'http://localhost:8000'` no frontend e abra `http://localhost:5500`. Não abra `index.html` por `file://`, porque os módulos, autenticação e PWA precisam de HTTP/HTTPS. Reponha a URL HTTPS Render antes de publicar.

### Testes

```sh
python -m pytest backend/tests -q
npm ci
npm test
```

Verificação adicional em Chromium real, num ambiente que permita arrancar o navegador:

```sh
pip install -r tests/requirements-browser.txt
python -m playwright install chromium
python tests/browser_check.py
```

O teste de browser usa exclusivamente respostas Firebase/Kaggle controladas. Não cria utilizadores reais nem consome quotas reais de IA. O workflow GitHub inclui esta verificação; se falhar, consulte o erro antes de disponibilizar o projeto. Consulte `VALIDACAO_PT.md` para saber o que foi efetivamente executado na entrega.

### Testar Docker localmente

Se tiver Docker instalado:

```sh
docker build -f backend/Dockerfile -t kiko-api .
docker run --rm -p 8000:8000 --env-file .env kiko-api
```

Se usa credenciais por ficheiro, monte o diretório dos segredos no contentor e ajuste os caminhos para `/etc/secrets`; um caminho Windows do host não existe dentro do Docker. Por exemplo, em Linux/macOS:

```sh
docker run --rm -p 8000:8000 --env-file .env -e GOOGLE_APPLICATION_CREDENTIALS=/etc/secrets/firebase-admin.json -e KIKO_PROMPTS_DIR=/etc/secrets -v /caminho/privado/segredos:/etc/secrets:ro kiko-api
```

## 9. Personalizar e manter

- **Cores, espaços e tipografia:** `frontend/css/variables.css`.
- **Textos e estrutura da interface:** `frontend/index.html`; mensagens de funcionamento nos módulos `frontend/js/`.
- **Logótipo:** o original está em `frontend/assets/KIKO.png`; cabeçalho, login e ícones estão nessa pasta e em `assets/icons`. Substitua as variantes mantendo as proporções e dimensões do manifesto. Não altere só o original esperando que as outras imagens mudem automaticamente.
- **Prompts:** altere os três Secret Files no Render. Não precisa de alterar Python.
- **Modelo:** altere `KIKO_MODEL` no Render; os três modos continuam a usar o mesmo.
- **Atualizações PWA:** os ficheiros estáticos usam rede com fallback de cache. Ao alterar a lista de recursos ou fazer uma atualização estrutural, incremente o nome `kiko-static-v1` em `frontend/sw.js`. Depois publique e reabra a aplicação online.
- **Sessão versus conversa:** apenas a autenticação pode persistir. Não existe recuperação de conversas após atualizar/fechar. Copie uma resposta antes de sair se precisar de a conservar.
- **Operação:** mantenha o backend numa única instância; não aumente workers para escalar sem mudar a arquitetura de anexos. A versão entregue foi desenhada para quatro pessoas.

## 10. Diagnóstico

| Sintoma | Verificação/ação |
|---|---|
| «Configuração inicial» no login | Preencha os quatro campos Firebase e a URL da API em `config.js`; publique novamente. |
| Email ou palavra-passe incorretos | Confirme a conta criada manualmente e use recuperação de palavra-passe se necessário. |
| Conta autenticada mas recusada | Confirme o UID em `KIKO_ALLOWED_UIDS`, não apenas o email. Máximo de quatro UIDs. |
| 401 | Sessão inválida/expirada, conta desativada ou token revogado. Termine sessão e volte a entrar; confirme o mesmo projeto Firebase no servidor e frontend. |
| 403 | UID fora da lista ou fornecedor de autenticação diferente de email/palavra-passe. |
| 400/422 | Pedido inválido, contexto demasiado longo, anexo inválido/sem texto ou formato de documento não processável. Leia a mensagem da interface. |
| 404 ao usar anexo | Expirou, foi eliminado, pertence a outra conta ou perdeu-se num reinício. Inicie uma nova conversa e volte a anexar. |
| 413 | Limite por ficheiro, tamanho do pedido ou armazenamento temporário excedido. Remova anexos ou aguarde a expiração. |
| 415 | Formato não suportado, incluindo ZIP. |
| 429 | Limite por minuto, geração já em curso ou quota Kaggle. Pare a geração anterior/aguarde e confirme a quota da conta. |
| 502 | Falha de comunicação, recusa de credenciais temporárias ou resposta inválida do Kaggle. Verifique conta, acesso e `KAGGLE_CHAT_PATH`. |
| 503 | Firebase/Kaggle/modelo/prompt/limite mal configurado ou fornecedor indisponível. Confirme os valores e Secret Files. |
| Erro de CORS/servidor inacessível | URL Render correta em `config.js`; origem Pages sem `/kiko/` em `CORS_ORIGINS`; serviço Live; HTTPS em produção. |
| Login funciona mas a IA falha | Health e login não testam Kaggle. Confirme token, lista real de modelos e os três prompts privados. |
| Resposta aparece de uma vez | O modelo não forneceu SSE nativo ou `STREAM_MODE=emulate`. O fallback entrega texto completo e não simula tokens. |
| «Ligação interrompida» | O fluxo terminou sem confirmação final, houve falha de rede ou foi excedido o tempo limite. Texto parcial é preservado; tente novamente. |
| PDF recusado | Pode estar protegido ou ser uma digitalização sem texto. Converta com OCR fora da KIKO antes de anexar. |
| XLSX tem células vazias | Pode não ter resultados calculados guardados. Abra e guarde no Excel/LibreOffice; o servidor não calcula fórmulas. |
| Imagem recusada pelo modelo | Confirme que `KIKO_MODEL` tem capacidades visuais e está disponível nesta conta. |
| Interface antiga | Abra online, feche/reabra a PWA e confirme o deploy Pages. Se necessário, limpe dados do site, sabendo que isso termina a sessão. |
| Primeiro pedido lento | O plano Render pode ter suspendido o serviço; aguarde o arranque. Se isso prejudicar o uso, escolha um plano adequado no painel. |

Não copie tokens, ficheiros privados ou conteúdo de conversas para tickets públicos. Os erros da API são resumidos e não incluem as respostas brutas do Kaggle.

## Referências oficiais

- [Firebase: autenticação por email e palavra-passe](https://firebase.google.com/docs/auth/web/password-auth)
- [Firebase: verificar ID tokens no servidor](https://firebase.google.com/docs/auth/admin/verify-id-tokens)
- [Firebase: manter e revogar sessões](https://firebase.google.com/docs/auth/admin/manage-sessions)
- [Kaggle CLI: Benchmarks](https://github.com/Kaggle/kaggle-cli/blob/main/docs/benchmarks.md)
- [Render: Blueprint YAML](https://render.com/docs/blueprint-spec)
- [Render: variáveis e Secret Files](https://render.com/docs/configure-environment-variables)
- [GitHub Pages: workflows personalizados](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)
