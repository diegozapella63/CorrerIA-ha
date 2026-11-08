# Instruções para quem for mexer neste repositório (pessoas ou IAs)

CorrerIA é um app (add-on) do Home Assistant: o contato da CorrerIA Code no WhatsApp, pela API oficial da Meta (WhatsApp Business, Cloud API). As pessoas da casa perguntam pelo WhatsApp; o CorrerIA confere quem mandou, passa a pergunta para o app da família daquele assunto e devolve a resposta. Faz parte de uma família de apps do mesmo dono, que conversam entre si pelo Home Assistant:

| App | Repositório | O que é |
|---|---|---|
| CorrerIA | `diegozapella63/correria-ha` (este) | o contato no WhatsApp |
| GerencIA | `diegozapella63/gerencia-ha` | finanças; responde pelo CorrerIA (`/api/integracao/conversa`) |
| CronologIA | `diegozapella63/cronologia-ha` | calendário, rotinas, remédios, placar |
| ResolvIA | `diegozapella63/resolvia-ha` | listas de tarefas, pontos, repetição |
| InventarIA | `diegozapella63/inventario-ha` | inventário da casa |
| MemorIA | `diegozapella63/memoria-ha` | cadernos de anotação |

O Home Assistant instala direto do GitHub (`repository.yaml` + `correria/config.yaml`), a partir da branch `main`: o que está em `main` é o que os usuários recebem.

## Estrutura

```
correria/config.yaml        versão e opções do app (porta 8443 do webhook, /ssl e /share só para leitura)
correria/CHANGELOG.md       o que mudou em cada versão (o HA mostra ao atualizar)
correria/DOCS.md            manual do usuário (aba Documentação no HA): a Meta, o Duck DNS, o roteador
correria/app/server.py      os dois servidores (só biblioteca padrão): a tela (8099, pelo painel) e o webhook (8443, https)
correria/app/whatsapp.py    a Cloud API: assinatura do webhook, mensagens, mandar, lida/digitando, conferir; números do Brasil
correria/app/apps.py        os apps da família: acha share/*/correria.json, escolhe o app da pergunta (e do tipo do anexo) e pergunta
correria/app/fala.py        áudio do WhatsApp (OGG/Opus) para texto pela fala para texto do Home Assistant (POST /api/stt/<motor>)
correria/app/www/           a tela: index.html, app.js (JavaScript puro, sem build), styles.css, fontes, icon.svg
tests/                      testes (ver tests/README.md)
```

Os dados ficam em `/data/config.json` (ID do número, token, chave secreta, token de verificação, endereço, número de cada pessoa) e `/data/conversas.json` (a conversa de cada número, as mensagens já vistas e o registro da tela), os dois com permissão só do dono e no backup do Home Assistant.

## Rodar no computador

```
cd correria/app
CORRERIA_DEV=1 CORRERIA_DATA=/tmp/c/data CORRERIA_SHARE=/tmp/c/share CORRERIA_SSL=/tmp/c/ssl python3 server.py
```

Abra `http://localhost:8099` (Ana e Beto aparecem como pessoas de exemplo). O webhook fica na 8443, em http sem certificado em `CORRERIA_SSL`. `CORRERIA_GRAPH` troca o endereço da Graph API (os testes usam uma Meta de mentira). Para um app que responde, rode o GerencIA com `GERENCIA_SHARE=/tmp/c/share/gerencia` e ligue nele **Integrações › CorrerIA no WhatsApp**.

## Checklist de toda mudança

1. Implementar. Servidor: só biblioteca padrão do Python. Tela: `correria/app/www/app.js` (um IIFE; ações por `data-a`; tudo vem de `/api/estado`).
2. Testar: `python3 -m unittest discover -s tests -t .` (servidor e tela; a tela precisa do playwright, o https do openssl). Toda mudança ou bug corrigido vem com o teste dele.
3. Subir a versão nos três lugares (iguais): `correria/config.yaml` (`version:`), `correria/app/server.py` (`VERSAO`) e `correria/app/www/app.js` (`const VERSAO`). Correção = patch (0.1.0 → 0.1.1); novidade = minor (0.1.x → 0.2.0).
4. `correria/CHANGELOG.md`: nova seção no topo, em português, do ponto de vista de quem usa.
5. `correria/DOCS.md` quando muda o comportamento ou aparece algo novo.
6. Commit em `main` com mensagem em português ("CorrerIA 0.2.0: ..."), `git pull --rebase` e push. O GitHub roda todos os testes a cada push (aba Actions).

## Como os apps conversam

- **Os apps → CorrerIA** (o contrato, igual para todos os apps): cada app que responde pelo WhatsApp grava, com a opção ligada nele, `share/<app>/correria.json` (`app`, `nome`, `assunto`, `rota`, `url`, `ip_url`, `chave` e, se lê arquivos, `anexos`: os tipos que lê, como `["application/pdf", "image/jpeg", "image/png", "image/webp"]`) e responde em `POST <url><rota>` com `Authorization: Bearer <chave>` e `X-App: CorrerIA`: `{texto, historico: [{papel: eu|ia, texto}], pessoa: {id, nome}, anexo?: {tipo, nome, b64}}` → `{resposta}`. `texto` é a pergunta ou a legenda (pode vir vazio com anexo); `b64` é um data URL. O áudio chega como texto: o CorrerIA ouve antes (`fala.py`), então nenhum app precisa tratar áudio. Um anexo só vai para os apps que declaram aquele tipo. Desligado, o arquivo some e a chave deixa de valer. Hoje: o GerencIA (`/api/integracao/conversa`; fotos e PDF ficam para conferir no Início dele). Para pôr outro app: o arquivo, a rota e as palavras do assunto em `apps.PALAVRAS`.
- **Meta**: o webhook (`GET /webhook` confere o token de verificação e devolve o `hub.challenge`; `POST /webhook` só com `X-Hub-Signature-256` certo, responde 200 na hora e trata depois) e a Graph API (`/<id do número>/messages` para mandar, marcar como lida e mostrar digitando; `/<id>?fields=display_phone_number,verified_name` para conferir). A mesma mensagem (pelo `id`) é tratada uma vez só.
- **Home Assistant**: as pessoas (`person.*`) pela API (`/api/states`); a fala para texto (`stt.*`: `GET /api/stt/<motor>` diz se aceita OGG/Opus, `POST` com o cabeçalho `X-Speech-Content`, escrito assim por causa do proxy do Supervisor); o certificado do Duck DNS em `/ssl` (fullchain.pem e privkey.pem), relido quando muda.
- **Mídia do WhatsApp**: foto, documento e áudio chegam com um id; `GET /<id>` dá um endereço que vale 5 minutos e só abre com o token (`whatsapp.midia`, até 20 MB).
- **Regras da Meta**: desde janeiro de 2026 não pode assistente de IA para qualquer assunto no WhatsApp Business; a IA de cada app responde só sobre os apps (no GerencIA, `chat.instrucoes_whatsapp`). Fora de 24 horas da última mensagem da pessoa, só modelos aprovados (o CorrerIA ainda não manda nada por conta própria).

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
