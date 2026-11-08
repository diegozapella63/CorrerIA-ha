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
correria/app/fala.py        áudio do WhatsApp (OGG/Opus) para texto pela fala para texto do Home Assistant (POST /api/stt/<motor>)
correria/app/www/           a tela: index.html, app.js (JavaScript puro, sem build; abre na conversa com a IA; a engrenagem leva às
                            Opções, em abas Apps, WhatsApp e Claude e Gemini, guardada em localStorage; Opções e Sobre ocupam uma
                            entrada no histórico cada, para o Voltar do celular), styles.css, fontes, icon.svg
tests/                      testes (ver tests/README.md)
tools/prints_readme.py      refaz as capturas do README (docs/*.png) com uma casa inventada
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
2. Testar: `python3 -m unittest discover -s tests -t .` (servidor e tela; a tela precisa do playwright, o https do openssl). Toda mudança ou bug corrigido vem com o teste dele.
3. Subir a versão nos três lugares (iguais): `correria/config.yaml` (`version:`), `correria/app/server.py` (`VERSAO`) e `correria/app/www/app.js` (`const VERSAO`). Correção = patch (0.1.0 → 0.1.1); novidade = minor (0.1.x → 0.2.0).
4. `correria/CHANGELOG.md`: nova seção no topo, em português, do ponto de vista de quem usa.
5. `correria/DOCS.md` quando muda o comportamento ou aparece algo novo.
6. Commit em `main` com mensagem em português ("CorrerIA 0.2.0: ..."), `git pull --rebase` e push. O GitHub roda todos os testes a cada push (aba Actions).

## Como os apps conversam

- **Os apps → CorrerIA** (o contrato, igual para todos os apps): cada app, com a opção **CorrerIA** ligada nele (Mais › Configurações › Integrações; desligada por padrão, sem depender da IA do app), grava `share/<app>/correria.json` (600, atômico) com `app` (o id, `[a-z0-9]`, prefixo das ferramentas), `nome`, `assunto`, `url`, `ip_url`, `chave` (própria, em `/data/correria.key` do app), `versao`, `ferramentas` (a rota, `/api/integracao/ferramentas`) e, só quem responde com a IA dele (hoje o GerencIA, para fotos e PDFs), `rota` e `anexos`. Tudo com `Authorization: Bearer <chave>` e `X-App: CorrerIA`; desligado, o arquivo some e as rotas respondem 401.
  - **Ferramentas**: `GET <url><ferramentas>` → `{instrucoes, ferramentas: [{nome ([a-z0-9_], até 40), titulo, descricao, entrada (JSON Schema, type object), grava, apaga}]}` (guardado por 60 s); `POST` `{nome, argumentos, pessoa: {id, nome}, cliente: Claude|Gemini|WhatsApp|CorrerIA}` → `{texto}`; 400 `{erro}` (argumento inválido: a IA lê e tenta de novo), 404 (ferramenta desconhecida). As gravações usam as regras da tela do app. Aqui o nome vira `<app>_<nome>` (`ferramentas.py`); um app só com `rota` vira `<app>_perguntar`.
  - **Conversa** (rota, só para fotos e PDFs e como reserva sem a IA do Home Assistant): `POST <url><rota>` `{texto, historico: [{papel: eu|ia, texto}], pessoa: {id, nome}, canal: whatsapp|correria, anexo?: {tipo, nome, b64}}` → `{resposta}`. Um anexo só vai para os apps que declaram aquele tipo em `anexos`. O áudio chega como texto: o CorrerIA ouve antes (`fala.py`).
  - Para pôr outro app: o arquivo, as rotas e uma sugestão em `SUGESTOES` (app.js).
- **WhatsApp e a conversa da tela** (`ia.py` e `responder_ia` no server.py): com algum app com ferramentas, a pergunta vai para a IA do Home Assistant (`POST /api/services/ai_task/generate_data?return_response`, sem `entity_id`: a entidade padrão) com o catálogo das ferramentas, a conversa e os resultados; ela devolve `{chamar: [{ferramenta, argumentos, resumo}], resposta}`. Leituras rodam na hora (até 4 rodadas); gravações viram um pendente em `conversas.json` e a resposta "Vou fazer isto: … Responda *sim*"; o próximo "sim" (`SIM_RE`) faz, o "não" (`NAO_RE`) desfaz e outra mensagem descarta. Sem a IA do Home Assistant e com um app com `rota`, vai pelo caminho antigo (`apps.escolher` + `perguntar`).
- **Claude e Gemini (MCP)**, só com `mcp` ligado na tela (desligado: 404 em tudo abaixo), na porta pública: `/.well-known/oauth-protected-resource[/mcp]` (RFC 9728) e `/.well-known/oauth-authorization-server` (e `openid-configuration`, RFC 8414), com o endereço tirado do `Host` do pedido; `POST /registrar` (RFC 7591; público ou com segredo); `GET /autorizar` (PKCE S256 obrigatório; a página mostra um código de 4 dígitos e consulta `/autorizar/estado` até alguém aprovar na tela, `POST /api/mcp/decidir`, com um aviso no sino do Home Assistant); `POST /token` (`authorization_code` e `refresh_token`, que gira; acesso de 1 hora, renovação de 90 dias); `POST /mcp` (Bearer; sem token, 401 com `WWW-Authenticate: Bearer resource_metadata=…`) com `initialize`, `ping`, `tools/list` e `tools/call` (`readOnlyHint`/`destructiveHint` de `grava`/`apaga`). A conexão fica com a pessoa que aprovou (vai como `pessoa` nas ferramentas); as gravações vão para o registro (tipo `mcp`). `POST /api/mcp/desconectar` tira uma conexão.
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
- Dados de exemplo e de testes sempre inventados (Ana, Beto, números fictícios): nunca nomes, números ou conversas reais do dono.

## Conversa com o dono

Respostas curtas, em português. Ao terminar uma mudança: o que mudou, a versão e se está publicado. Ele usa o app do Home Assistant no Android.
