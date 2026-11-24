# Ficheiros de configuração do repositório

O ZIP não tem nomes começados por ponto na raiz, para facilitar o upload pelo site do GitHub.

O GitHub Actions só reconhece workflows em `.github/workflows/`, e o Git usa `.gitignore` no local original. A pasta `configuracao/` contém as cópias prontas a usar. **Carregar apenas estas cópias não altera os workflows ativos.**

## Atualizar diretamente pelo site do GitHub (sem terminal)

1. Carregue o conteúdo da pasta `kiko-main` do ZIP na raiz do repositório, como habitualmente. Não carregue ficheiros privados nem ambientes virtuais.
2. Abra `.github/workflows/test.yml` no repositório, clique no lápis (Edit), substitua todo o conteúdo pelo de `configuracao/github/workflows/test.yml` e faça Commit changes no ramo main.
3. Faça o mesmo em `.github/workflows/pages.yml`, usando `configuracao/github/workflows/pages.yml`.
4. Se o repositório já tiver `.gitignore`, mantenha-o; a cópia `configuracao/gitignore.txt` é fornecida para recuperação. Num repositório novo, crie o ficheiro `.gitignore` pelo botão Add file → Create new file e cole o conteúdo da cópia. Se os workflows não existirem, crie-os do mesmo modo introduzindo os caminhos completos indicados acima.
5. Em Actions, execute o workflow Testar KIKO e verifique os jobs backend e frontend. Execute Publicar frontend KIKO se for necessário.

O ficheiro `env.example` substitui `.env.example` como modelo de configuração local. Não é necessário publicá-lo com valores privados. O Docker usa `backend/Dockerfile.dockerignore`, que tem prioridade sobre o antigo `.dockerignore` da raiz. Num repositório existente, pode manter os antigos `.env.example` e `.dockerignore` se o upload não os eliminar.

## Alternativa para GitHub Desktop ou terminal

Copie o conteúdo do ZIP para a pasta clonada e execute `python tools/preparar_repositorio.py` a partir da raiz. O script recria/atualiza os três ficheiros de GitHub/Git nos caminhos obrigatórios (substitui versões existentes). Reveja as alterações, faça commit e push. Não introduz credenciais nem altera a configuração do Firebase.

## Versões e correção da publicação do layout

1. Substitua **também** `.github/workflows/pages.yml` pela cópia desta pasta. O novo workflow publica `dist/`, não o `frontend/` cru; a pasta `dist` é gerada automaticamente no GitHub. Atualize igualmente `test.yml`.
2. No GitHub, em Settings → Pages → Build and deployment → Source, selecione **GitHub Actions**. Em Actions → Publicar frontend KIKO → Run workflow → main, confirme o deploy. Abra a URL indicada pelo job `deployment`, não a visualização de ficheiros do repositório nem uma URL antiga.
3. No Render, em Environment do serviço `kiko-api`, adicione `APP_VERSION` com valor `1.1.0`. Guarde e faça deploy do commit atualizado (não apenas Restart). Para mudanças de versão posteriores, altere o valor manualmente e aplique com deploy. A variável está marcada `sync: false` no Blueprint para não repor automaticamente o valor.
4. Compare `https://kiko-api.onrender.com/api/version` com `version.json` na URL Pages (normalmente `https://heneique007.github.io/kiko/version.json`). O campo `build` deve coincidir. O campo `version` do Pages é apenas a versão inicial de recurso; o valor exibido é o `APP_VERSION` do Render quando os builds coincidem. Um build diferente indica que uma das publicações está atrasada.
5. A primeira atualização para esta release requer publicar e abrir o frontend novo pelo endereço correto; uma versão antiga que ainda não contém o código de atualização não pode executar esta lógica. A partir daí, a app verifica versões automaticamente. Não apague dados do site; a sessão Firebase permanece.
