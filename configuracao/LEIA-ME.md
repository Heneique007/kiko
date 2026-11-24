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
