# KIKO

Aplicação privada de IA para até quatro contas. Frontend estático, mobile-first, em HTML/CSS/JavaScript; API Python/FastAPI; Firebase exclusivamente para autenticação; um único modelo Kaggle com os modos **Learn**, **Think** e **Quick**.

**Comece por [SETUP_PT.md](SETUP_PT.md).** O código não inclui credenciais nem prompts privados. O login e a IA precisam da configuração dos seus serviços; a distribuição mostra uma indicação explícita enquanto essa configuração está vazia.

## Organização

- `frontend/`: a única pasta publicada no GitHub Pages. Inclui PWA, identidade oficial, Markdown seguro, streaming e anexos.
- `backend/app/`: autenticação, prompts, transporte Kaggle, API, streaming e processamento de ficheiros separados.
- `backend/prompts/`: três exemplos genéricos. Os prompts de produção ficam exclusivamente em Secret Files.
- `backend/tests/`: testes automatizados de API, autorização, isolamento, streaming, cancelamento, configuração e documentos.
- `tests/`: testes JavaScript e verificação de interface com respostas externas controladas.
- `tools/check_kaggle.py`: consulta real dos modelos disponíveis, sem mostrar credenciais temporárias.
- `configuracao/`: modelos dos workflows e do `.gitignore`; siga [as instruções](configuracao/LEIA-ME.md) para os aplicar nos caminhos obrigatórios do GitHub.
- `render.yaml`: backend Docker, sem base de dados.

## Funcionamento

1. Firebase autentica por email/palavra-passe; o browser envia o ID token em cada pedido.
2. A API verifica assinatura, validade e revogação do token e o UID na lista autorizada.
3. O servidor seleciona o TXT do modo e valida `KIKO_MODEL` contra `LLMS_AVAILABLE` obtido pelo CLI Kaggle.
4. A resposta usa SSE nativo quando disponível. O fallback identifica-se como não nativo e entrega o texto completo numa única mensagem.
5. Mensagens existem apenas na memória JavaScript. Os anexos pertencem ao respetivo UID e têm armazenamento efémero e limitado.

Não existe registo público na interface, seleção de modelos pelo cliente, áudio, histórico persistente, Firestore ou Realtime Database. A autenticação Firebase usa persistência local e restaura a sessão mesmo depois de fechar a aplicação, com renovação dos tokens pelo SDK. A API valida a conta novamente antes de mostrar o chat; falhas temporárias são repetidas automaticamente, sem apagar a sessão. O service worker guarda exclusivamente recursos estáticos numa lista explícita.

## Executar localmente

Python 3.12 e Node.js 24.15 ou superior para os testes JavaScript. O frontend em produção não precisa de Node ou de compilação.

```sh
python -m venv .venv
# Ative o ambiente virtual; veja o guia para Windows.
pip install -r backend/requirements-test.txt
# Copie env.example para .env e configure os valores privados.
python -m uvicorn app.main:app --app-dir backend --env-file .env --port 8000 --workers 1 --no-access-log
```

Noutro terminal, na raiz do repositório:

```sh
python -m http.server 5500 --directory frontend
```

Abra `http://localhost:5500`. Configure `frontend/js/config.js` e `CORS_ORIGINS` antes de testar o login.

## Testes

```sh
python -m pytest backend/tests -q
npm ci
npm test
# Verificação adicional em browser real:
pip install -r tests/requirements-browser.txt
python -m playwright install chromium
python tests/browser_check.py
```

Os testes substituem Firebase/Kaggle por respostas controladas, sem introduzir um modo de demonstração na aplicação. Consulte [VALIDACAO_PT.md](VALIDACAO_PT.md) para os resultados efetivamente executados e as verificações externas pendentes.

## Limites e operação

Use **um único worker e uma única instância** do backend: anexos, quotas de pedidos e credenciais temporárias vivem em memória. Reiniciar, republicar ou suspender o serviço perde os anexos. Uma nova conversa tenta eliminá-los imediatamente; a expiração e a limpeza periódica cobrem falhas de rede e o fecho do separador.

Os limites iniciais são 50 MB por documento/folha de cálculo, 20 MB por imagem, 200 MB e 80 ficheiros temporários partilhados, 10 anexos por mensagem e 25 no contexto, com 6 horas de validade. Há uma quota de 80 tentativas de upload por UID a cada 3 horas e uma proteção de 20 pedidos/minuto por tipo. O limite de mensagem é 160 000 caracteres, de extração por documento 200 000 caracteres e de contexto 300 000 caracteres (máximo configurável 480 000). São limites locais, não garantias de tokens do modelo Kaggle. O ChatGPT Plus serve de referência, mas documentos de 512 MB e armazenamento em GB exigiriam outra infraestrutura; o Render Free usa armazenamento temporário em memória. As imagens são normalizadas para JPEG até 2048 × 2048; GIF usa a primeira imagem; HEIC/HEIF é convertido. Documentos usam extração de texto, sem OCR, interpretação de gráficos ou execução de macros/fórmulas. XLSX usa valores calculados guardados no ficheiro. PDFs limitam-se às primeiras 100 páginas; a extração de texto também tem limite configurável. Textos demasiado longos são sinalizados como limitados.

O modelo escolhido precisa de aceitar imagens para as analisar: a conversão não acrescenta capacidades visuais a um modelo de texto. Os formatos da interface são os realmente processados pelo backend; ZIP é recusado. A disponibilidade de cada modelo vem das credenciais atuais, não de uma lista inventada.

## Privacidade e dependências

A KIKO não escreve conversas numa base de dados nem nos logs da aplicação. O conteúdo enviado é transmitido ao Kaggle/modelo para gerar respostas; o Firebase trata a autenticação. As políticas desses fornecedores continuam a aplicar-se. O frontend público contém apenas a configuração pública Firebase e a URL da API.

Markdown: `marked` 17.0.1 e DOMPurify 3.3.1, incluídos localmente com licenças em `frontend/js/vendor/`. SDK Firebase Web 13.4.0 carregado do CDN oficial apenas após configuração. Dependências Python e de teste estão fixadas nos respetivos ficheiros; dependências JavaScript de desenvolvimento estão no `package-lock.json`.

A lógica Kaggle foi adaptada do ZIP fornecido: `kaggle benchmarks init`, credenciais efémeras, renovação com margem, fallback para credenciais ainda válidas, resolução de aliases validada contra a lista disponível e deteção de suporte de streaming. Foram removidas as páginas e a API legadas do Pal Chat. A validação de imagens foi reforçada para descodificação efetiva, e os anexos passaram a ter autorização por UID.

## Versão da Web App (Render + GitHub Pages)

Defina `APP_VERSION=1.1.0` em Render → kiko-api → Environment e aplique com deploy. O endpoint público `/api/version` devolve só a versão e a identificação do frontend desse deploy, sem cache. O workflow Pages atualizado gera `dist/` com recursos em `releases/<hash>/` e `version.json`, cujo hash é calculado também no Docker. A KIKO mostra a versão no canto inferior direito do chat, verifica ao abrir/voltar à aplicação e a cada 60 segundos enquanto visível. Ao detetar uma alteração, elimina apenas as caches estáticas KIKO e recarrega uma vez; mantém o Firebase, evita perder rascunhos e conversas (atualiza após iniciar uma conversa nova ou reabrir a app). Uma falha de rede não termina sessão nem reverte a versão verificada.

Para publicar mudanças de design, é obrigatório publicar o frontend no Pages; alterar `APP_VERSION` ou reiniciar o Render não publica HTML/CSS/JS. Consulte `configuracao/LEIA-ME.md` para instalar os workflows. O ZIP não tem ficheiros ocultos na raiz. Execute `python tests/build_check.py` para validar o artefacto efetivamente publicado.
