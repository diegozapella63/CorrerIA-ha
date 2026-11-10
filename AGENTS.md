# Instruções para quem for mexer neste repositório (pessoas ou IAs)

CorrerIA é um app (add-on) do Home Assistant que junta os apps em três lugares: o **WhatsApp** (o contato da CorrerIA Code, pela API oficial da Meta: WhatsApp Business, Cloud API), o **Claude** e o **Gemini** (como servidor MCP, com login OAuth aprovado no painel) e a conversa da própria tela. Cada app publica as suas ferramentas (ler e mudar); no WhatsApp e na tela, a IA do Home Assistant usa essas ferramentas (as mudanças só depois do "sim" da pessoa); o Claude e o Gemini chamam as mesmas ferramentas pelo MCP. Faz parte de uma família de apps do mesmo dono, que conversam entre si pelo Home Assistant:

| App | Repositório | O que é |
|---|---|---|
| CorrerIA | `diegozapella63/correria-ha` (este) | os apps no WhatsApp, no Claude e no Gemini |
| GerencIA | `diegozapella63/gerencia-ha` | finanças; ferramentas e a conversa com anexos (`/api/integracao/conversa`) |
| CronologIA | `diegozapella63/cronologia-ha` | calendário, rotinas, remédios, placar |
| ResolvIA | `diegozapella63/resolvia-ha` | listas de tarefas, pontos, repetição |
| InventarIA | `diegozapella63/inventario-ha` | inventário da casa |
| MemorIA | `diegozapella63/memoria-ha` | cadernos de anotação |

O Home Assistant instala direto do GitHub (`repository.yaml` + `correria/config.yaml`), a partir da branch `main`: o que está em `main` é o que os usuários recebem.

No `config.yaml`, `url` aponta para o repositório e o `panel_admin` fica no padrão do Home Assistant (o painel só para administradores): aqui ficam o token da Meta, a chave secreta, os números das pessoas e a aprovação das IAs conectadas.

## Estrutura

```
correria/config.yaml        versão e opções do app (porta pública 8443, /ssl e /share só para leitura)
correria/CHANGELOG.md       o que mudou em cada versão (o HA mostra ao atualizar)
correria/DOCS.md            manual do usuário (aba Documentação no HA): a Meta, o Duck DNS, o roteador, o Claude e o Gemini
correria/app/server.py      os dois servidores (só biblioteca padrão): a tela (8099, pelo painel) e a porta pública (8443, https:
                            o webhook e, com o Claude e o Gemini ligados, o MCP e o login); o "sim" das mudanças
correria/app/ferramentas.py as ferramentas de todos os apps juntas (<app>_<nome>); app só com rota vira <app>_perguntar
correria/app/ia.py          a IA do WhatsApp e da tela: ai_task do Home Assistant com as ferramentas (lê, propõe as mudanças)
correria/app/mcp.py         o protocolo MCP (JSON-RPC 2.0 pelo POST /mcp, Streamable HTTP só com JSON, sem sessão)
correria/app/oauth.py       o login do Claude e do Gemini: OAuth 2.1 com PKCE, registro dinâmico, aprovação no painel
correria/app/whatsapp.py    a Cloud API: assinatura do webhook, mensagens, mandar, lida/digitando, conferir; números do Brasil
correria/app/apps.py        os apps da família: acha share/*/correria.json, escolhe o app da pergunta (e do tipo do anexo) e pergunta
correria/app/fala.py        áudio para texto pela fala para texto do Home Assistant (POST /api/stt/<motor>): o do WhatsApp (OGG/Opus)
                            e o do microfone da Conversa (PCM de 16 kHz, como o Assist; POST /api/fala da tela)
correria/app/www/           a tela: index.html, app.js (JavaScript puro, sem build; abre na conversa com a IA; os três pontos
                            levam ao Mais, um menu com Configurações e Sobre; Configurações em abas Apps, WhatsApp, MCP, Dados, Aparência e
                            Opções, guardada em localStorage; Mais, Configurações e Sobre ocupam uma entrada no histórico
                            cada, para o Voltar do celular), styles.css, fontes, icon.svg
correria/app/uso.py         Uso da IA: as chamadas da IA do WhatsApp e da tela, por dia e tipo, em /data/uso_ia.json
tests/                      testes (ver tests/README.md)
tools/prints_readme.py      refaz as capturas do README (docs/*.png) com uma casa inventada
tools/cobertura.py          a cobertura de linhas dos testes (tests/run.sh --cobertura), só biblioteca padrão
```

A conversa da tela (`/api/conversa`) é de quem está no painel: o Home Assistant manda `X-Remote-User-Id` e o CorrerIA acha a pessoa pelo `user_id` dela; guardada em `conversas.json` (`tela`: de cada login, `{atual, lista: [{id, titulo, criada, atualizada, mensagens}]}`, as últimas 30 conversas com as últimas 40 mensagens cada; a lista de antes da 0.6.0, uma conversa só, vira a primeira). Rotas: `GET /api/conversa` (a aberta), `GET /api/conversas` (a lista), `POST /api/conversa/nova`, `/abrir` e `/apagar` (`{id}`); trocar de conversa descarta o pendente do "sim".

Os dados ficam em `/data/config.json` (ID do número, token, chave secreta, token de verificação, endereço, número de cada pessoa, `mcp`), `/data/conversas.json` (a conversa de cada número, as mensagens já vistas, o registro, a conversa da tela e os `pendentes`: as mudanças que esperam o "sim", por 30 minutos) e `/data/mcp.json` (os clientes registrados pelo Claude e pelo Gemini e as conexões, com os tokens só em hash SHA-256), todos com permissão só do dono e no backup do Home Assistant.

## Rodar no computador

```
cd correria/app
CORRERIA_DEV=1 CORRERIA_DATA=/tmp/c/data CORRERIA_SHARE=/tmp/c/share CORRERIA_SSL=/tmp/c/ssl python3 server.py
```

Abra `http://localhost:8099` (Ana e Beto aparecem como pessoas de exemplo). A porta pública fica na 8443, em http sem certificado em `CORRERIA_SSL` (`CORRERIA_PORTA` e `CORRERIA_PORTA_WEBHOOK` mudam as portas). `CORRERIA_GRAPH` troca o endereço da Graph API (os testes usam uma Meta de mentira). Fora do Home Assistant, a IA é simulada (`ia.simulado`: "lança 25 de padaria" propõe, uma pergunta lê o resumo). Para um app de verdade, rode o GerencIA com `GERENCIA_SHARE=/tmp/c/share/gerencia GERENCIA_PORTA=8191 GERENCIA_URL_INTERNA=http://127.0.0.1:8191` e ligue nele **Integrações › CorrerIA**.

## Checklist de toda mudança

1. Implementar. Servidor: só biblioteca padrão do Python. Tela: `correria/app/www/app.js` (um IIFE; ações por `data-a`; tudo vem de `/api/estado`).
2. Testar: `tests/run.sh` (o mesmo que `python3 -m unittest discover -s tests -t .`: servidor e tela; a tela precisa do playwright, o https do openssl); só a tela: `tests/e2e/run.sh` (ou `tests/e2e/run.sh test_sobre ...`); a cobertura de linhas do servidor: `tests/run.sh --cobertura` (fica acima de 95%; ver tests/README.md). Toda mudança ou bug corrigido vem com o teste dele.
3. Subir a versão num lugar só: `correria/config.yaml` (`version:`). O servidor lê de lá (`VERSAO`, pelo `ler_versao`; na imagem, o Dockerfile copia o config.yaml para /app) e a tela recebe pelo `/api/estado`; o `tests/test_versao.py` confere, e também a seção do CHANGELOG. Correção = patch (0.1.0 → 0.1.1); novidade = minor (0.1.x → 0.2.0).
4. `correria/CHANGELOG.md`: nova seção no topo, em português, do ponto de vista de quem usa.
5. `correria/DOCS.md` quando muda o comportamento ou aparece algo novo.
6. Commit em `main` com mensagem em português ("CorrerIA 0.2.0: ..."), `git pull --rebase` e push. O GitHub roda todos os testes a cada push (aba Actions).

## Arquivos iguais em todos os apps

A lista dos arquivos que são iguais nos apps da família fica em `tools/iguais.py` (ele também é igual em todos):
`python3 tools/iguais.py` confere os daqui com os dos apps ao lado (`../resolvia-ha`, ...), e o GitHub confere a cada
push (job **Arquivos iguais aos dos outros apps**, que baixa os outros apps). Mudou um arquivo da lista? Copie para os
outros apps do grupo e publique todos. Um arquivo que passa a ser igual entra em `GRUPOS`, aqui e nas cópias.

`share/<app>/integracao.json` começa igual em todos os apps: `app` (o id, como no `correria.json`), `nome`, `versao` e
`gravado_em` (ISO 8601 com o fuso), depois os campos de cada app. O ResolvIA e o CronologIA ainda gravam o nome em
`app` (as versões de antes conferem por ele) e quem lê aceita os dois; o id entra numa próxima versão.

## Como os apps conversam

- **Os apps → CorrerIA** (o contrato, igual para todos os apps): cada app, com a opção **CorrerIA** ligada nele (Mais › Configurações › Integrações; desligada por padrão, sem depender da IA do app), grava `share/<app>/correria.json` (600, atômico) com `app` (o id, `[a-z0-9]`, prefixo das ferramentas), `nome`, `assunto`, `url`, `ip_url`, `chave` (própria, em `/data/correria.key` do app), `versao`, `ferramentas` (a rota, `/api/integracao/ferramentas`) e, só quem responde com a IA dele (hoje o GerencIA, para fotos e PDFs), `rota` e `anexos`. Tudo com `Authorization: Bearer <chave>` e `X-App: CorrerIA`; desligado, o arquivo some e as rotas respondem 401.
  - **Ferramentas**: `GET <url><ferramentas>` → `{instrucoes, ferramentas: [{nome ([a-z0-9_], até 40), titulo, descricao, entrada (JSON Schema, type object), grava, apaga}]}` (guardado por 60 s); `POST` `{nome, argumentos, pessoa: {id, nome}, cliente: Claude|Gemini|WhatsApp|CorrerIA}` → `{texto}`; 400 `{erro}` (argumento inválido: a IA lê e tenta de novo), 404 (ferramenta desconhecida). As gravações usam as regras da tela do app. Aqui o nome vira `<app>_<nome>` (`ferramentas.py`); um app só com `rota` vira `<app>_perguntar`.
  - **Conversa** (rota, só para fotos e PDFs e como reserva sem a IA do Home Assistant): `POST <url><rota>` `{texto, historico: [{papel: eu|ia, texto}], pessoa: {id, nome}, canal: whatsapp|correria, anexo?: {tipo, nome, b64}}` → `{resposta}`. Um anexo só vai para os apps que declaram aquele tipo em `anexos`. O áudio chega como texto: o CorrerIA ouve antes (`fala.py`).
  - Para pôr outro app: o arquivo, as rotas e uma sugestão em `SUGESTOES` (app.js).
- **WhatsApp e a conversa da tela** (`ia.py` e `responder_ia` no server.py): com algum app com ferramentas, a pergunta vai para a IA do Home Assistant (`POST /api/services/ai_task/generate_data?return_response`, sem `entity_id`: a entidade padrão) com o catálogo das ferramentas, a conversa e os resultados; ela devolve `{chamar: [{ferramenta, argumentos, resumo}], resposta}`. Leituras rodam na hora (até 4 rodadas); gravações viram um pendente em `conversas.json` e a resposta "Vou fazer isto: … Responda *sim*"; o próximo "sim" (`SIM_RE`) faz, o "não" (`NAO_RE`) desfaz e outra mensagem descarta. Sem a IA do Home Assistant e com um app com `rota`, vai pelo caminho antigo (`apps.escolher` + `perguntar`).
- **Conector MCP** (qualquer IA que aceite um conector personalizado remoto: Claude, ChatGPT, Gemini…; na tela, só termos genéricos, sem marcas), só com `mcp` ligado na tela (desligado: 404 em tudo abaixo), na porta pública: `/.well-known/oauth-protected-resource[/mcp]` (RFC 9728) e `/.well-known/oauth-authorization-server` (e `openid-configuration`, RFC 8414), com o endereço tirado do `Host` do pedido; `POST /registrar` (RFC 7591; público ou com segredo); `GET /autorizar` (PKCE S256 obrigatório; a página mostra um código de 4 dígitos e consulta `/autorizar/estado` até alguém aprovar na tela, `POST /api/mcp/decidir`, com um aviso no sino do Home Assistant); `POST /token` (`authorization_code` e `refresh_token`, que gira; acesso de 1 hora, renovação de 90 dias); `POST /mcp` (Bearer; sem token, 401 com `WWW-Authenticate: Bearer resource_metadata=…`) com `initialize`, `ping`, `tools/list` e `tools/call` (`readOnlyHint`/`destructiveHint` de `grava`/`apaga`). A conexão fica com a pessoa que aprovou (vai como `pessoa` nas ferramentas); as gravações vão para o registro (tipo `mcp`). `POST /api/mcp/desconectar` tira uma conexão.
- **Meta**: o webhook (`GET /webhook` confere o token de verificação e devolve o `hub.challenge`; `POST /webhook` só com `X-Hub-Signature-256` certo, responde 200 na hora e trata depois) e a Graph API (`/<id do número>/messages` para mandar, marcar como lida e mostrar digitando; `/<id>?fields=display_phone_number,verified_name` para conferir). A mesma mensagem (pelo `id`) é tratada uma vez só.
- **Home Assistant**: as pessoas (`person.*`) pela API (`/api/states`); a fala para texto (`stt.*`: `GET /api/stt/<motor>` diz se aceita OGG/Opus, `POST` com o cabeçalho `X-Speech-Content`, escrito assim por causa do proxy do Supervisor); o certificado do Duck DNS em `/ssl` (fullchain.pem e privkey.pem), relido quando muda.
- **Mídia do WhatsApp**: foto, documento e áudio chegam com um id; `GET /<id>` dá um endereço que vale 5 minutos e só abre com o token (`whatsapp.midia`, até 20 MB).
- **Regras da Meta**: desde janeiro de 2026 não pode assistente de IA para qualquer assunto no WhatsApp Business; no WhatsApp a IA responde só sobre os apps (`ia.ASSUNTO_WHATSAPP`; no GerencIA, `chat.instrucoes_whatsapp`). Fora de 24 horas da última mensagem da pessoa, só modelos aprovados (o CorrerIA ainda não manda nada por conta própria).

## Como o dono gosta (interface)

- Tudo em português do Brasil, sem palavras em inglês na tela.
- **Menos é mais**: textos curtos, sem explicar o óbvio, sem avisos repetidos.
- Botões lado a lado com o mesmo tamanho e alinhados; nada cortado nem saindo da tela.
- O token e a chave secreta nunca voltam para a tela (só o fim, ••••1234).
- Em http (sem https) não há área de transferência: o Copiar seleciona o texto e explica.
- Celular primeiro (390 px); tema claro e escuro, seguindo o do Home Assistant na hora.
- **Inativos no fim, recolhidos**: o que está inativo, cancelado, encerrado, arquivado ou ignorado de propósito (por uma opção, como Nunca considerar) fica numa seção no fim da lista, recolhida por padrão, com o nome e a contagem (ex.: **Arquivados (3)**); abre num toque. Vale para todos os apps da família. Aqui ainda não há lista assim: um app com a opção CorrerIA desligada nem aparece, e uma conexão desconectada sai da lista.
- **Caixas de seleção no visual do app**: nenhuma janela nativa do celular. Toda caixa de seleção abre pelo selectsheet.js; sugestões de texto (no lugar do `<datalist>`) e horários (sem AM/PM) também no visual do app; a caixa fechada igual aos outros campos (altura, cantos, seta), no claro e no escuro. Aqui ainda não há caixa de seleção nem `<datalist>`: a primeira que entrar traz o `selectsheet.js` (o arquivo igual dos outros apps, sem mudar nada), carregado antes do `app.js`.
- Dados de exemplo e de testes sempre inventados (Ana, Beto, números fictícios): nunca nomes, números ou conversas reais do dono.

**Padrão da família (igual em todos os apps)**
- Barra de baixo: o botão do meio é **Adicionar** (no EconomIA, a ação principal dele); **Buscar**, quando houver, é a 2ª aba; **Mais** é a última, com o ícone de três pontos.
- **Mais** é um menu: as funções do app, depois **Configurações** e por último **Sobre**. Os relatórios se chamam **Relatório de/do …**.
- **Configurações** em 4 abas, nesta ordem: **Integrações › Dados › Aparência › Opções**; abre em Integrações. Nenhuma função do app vira aba.
- **Integrações**, nesta ordem: os outros apps da família › CorrerIA › **IA do Home Assistant** (o Usar IA) › Falar › Uso da IA › Sensores.
- IA: as entradas se chamam **Colar mensagem**, **Escolher fotos** (ou **Escolher fotos ou PDF**, onde PDF vale) e **Digitalizar com IA**; a conversa recomeça em **Nova conversa**; o Voltar do celular fecha a Conversa.
- Palavras: **Apagar** (nunca Excluir); **Testar no meu celular**; **Home Assistant Cloud** (não Nabu Casa); recolhidos como **Nome (n)**; o CHANGELOG começa com "# Mudanças".
- Avisos no celular (todos chegam como Home Assistant): o título começa pelo nome do app, uma vez só ("ResolvIA · 📅 Vence hoje"), e o ícone pequeno é o do app (`notification_icon`); o canal e o grupo de cada aviso ficam como estão (o canal guarda o som e a importância que a pessoa escolheu no Android).
- **Dados**: Exportar › Backup na pasta share › Importar › Versões anteriores › Onde ficam os dados › Começar do zero.
- **Aparência**: o tema vale no aparelho (começa em Sistema); a cor do app vale para a casa toda; uma paleta só, de 12 cores (Vermelho, Coral, Laranja, Ouro, Verde, Menta, Turquesa, Azul, Índigo, Lilás, Rosa, Grafite); a Cor do dia é a mesma em todos os apps (as 11 sem o Grafite, pelo número do dia).

Aqui (o CorrerIA não tem barra de baixo nem Integrações: ele é a integração dos outros): os três pontos no alto da Conversa abrem o **Mais** (Configurações e, por último, Sobre); Configurações fica com as abas que fazem sentido aqui (**Apps**, **WhatsApp**, **MCP**, **Dados**, **Aparência** e **Opções**, esta só com o Atalho no celular e só dentro do Home Assistant); o **Uso da IA** fica na aba Apps (`uso.py`); Dados só tem **Onde ficam os dados** (nada de exportar: o token, a chave secreta e as conversas não saem daqui); a cor da casa em `config.json` (`cor`, `cor_dia`), o tema no aparelho (`correria-tema`). O endereço do repositório é `CorrerIA-ha` (o remote de verdade): não mude.

## Conversa com o dono

Respostas curtas, em português. Ao terminar uma mudança: o que mudou, a versão e se está publicado. Ele usa o app do Home Assistant no Android.
