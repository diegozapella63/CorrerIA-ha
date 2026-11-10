# Testes do CorrerIA

```
tests/run.sh                  todos (o mesmo que python3 -m unittest discover -s tests -t .)
tests/e2e/run.sh              só a tela (tests/test_tela.py); tests/e2e/run.sh test_sobre ... só esses
tests/run.sh --cobertura      todos, com a cobertura de linhas do servidor (python3 tools/cobertura.py --linhas)
```

Só biblioteca padrão, mais o **playwright** com o Chromium para a tela (`pip install playwright && python -m playwright install chromium`) e o **openssl** para o teste do https. No GitHub, falha também se algum teste for pulado.

**Cobertura**: o `tools/cobertura.py` (só biblioteca padrão, a mesma ferramenta do EconomIA) roda todos os testes com um
rastreador ligado nos arquivos de `correria/app/*.py`, desde a importação, e mostra o % de cada um e as linhas que nenhum
teste percorre (`--minimo 95` falha abaixo de 95%). O servidor da tela do `test_tela.py` roda numa thread do próprio teste,
então entra na conta. Na 0.10.1, 99,6% das linhas (o GitHub exige 95%; só ficam de fora o `if __name__` e uns poucos ramos de defesa). A tela (`www/app.js`) não tem cobertura medida: o Playwright em
Python não dá a cobertura do JavaScript; ela é conferida pelo `test_tela.py`, tela a tela.

| Arquivo | O que testa |
|---|---|
| `test_whatsapp.py` | a assinatura do webhook, as mensagens e as falhas no que a Meta manda, o texto no jeito do WhatsApp (negrito, partes), os números do Brasil com e sem o 9 e o cliente da Graph API |
| `test_fala.py` | o áudio em texto: o do WhatsApp (o motor que aceita OGG/Opus) e o do microfone da Conversa (PCM de 16 kHz), o cabeçalho, o idioma, os erros |
| `test_apps.py` | achar os apps (`share/*/correria.json`), escolher o app da pergunta, perguntar (chave, IP de reserva, erros), listar e chamar as ferramentas de um app |
| `test_ferramentas.py` | as ferramentas de todos os apps juntas (`<app>_<nome>`), o `<app>_perguntar` de quem só tem rota, erros e app fora do ar |
| `test_ia.py` | a IA do WhatsApp e da tela com as ferramentas: ler e responder, propor mudanças, ferramenta errada, só texto, rodadas, a IA simulada |
| `test_mcp.py` | o protocolo MCP: initialize, tools/list (com as dicas de leitura e de apagar), tools/call, notificações, listas, erros |
| `test_oauth.py` | o login do Claude e do Gemini: registro, pedido com PKCE, aprovar e recusar, token, renovar (gira), desconectar, prazos, erros, limites |
| `test_servidor.py` | a configuração (o token nunca volta), quem conversa, responder (conversa, número sem cadastro, repetida, áudio, pausado, sem app, erros), com as ferramentas (ler, o sim, o não, o prazo, a IA do Home Assistant fora do ar), o webhook (token de verificação, assinatura, só /webhook, https com certificado e renovação), o Claude e o Gemini pela porta pública (do registro ao MCP, desligado, erros), a tela (rotas, só pelo painel) e os casos raros (respostas quebradas, o app que saiu antes do sim, o certificado estragado, o aviso no sino, o corpo que não chega inteiro, o `main()`) |
| `test_versao.py` | a versão num lugar só (o `config.yaml`; o servidor lê de lá, no contêiner e no computador; a tela não tem a versão escrita; a seção do CHANGELOG) |
| `test_uso.py` | Uso da IA: as chamadas por dia, tipo (WhatsApp, Conversa) e resultado (ok, sem cota, erro), os 120 dias e as 40 últimas, o arquivo estragado e a IA contando o canal |
| `test_tela.py` | a tela num Chromium a 390 px: abre na conversa, o Mais (Configurações e Sobre por último), Configurações em abas (guardadas, numa linha até 320 px), Dados (onde ficam, sem o token), Aparência (o tema no aparelho, a cor da casa, a Cor do dia), Uso da IA, configurar e conferir, pausar, webhook e copiar, quem conversa, os apps (o que cada um faz), o conector MCP (ligar, endereço, pedido no alto, aprovar e recusar, conectados, desconectar), Conversar com a IA (texto, sugestão, foto, Falar com um microfone de mentira, sem microfone ou sem fala para texto, conversa guardada, Voltar do celular), últimas mensagens, Sobre, tudo pronto, tema claro e escuro |

Ajuda em `base.py`: `importar_servidor()` (o `server.py` com pastas temporárias), `ServidorFalso` (um servidor HTTP que guarda os pedidos), `MetaFalsa` (a Graph API), `AppFalso` (um app da família com as ferramentas) e `certificado()` (um certificado próprio, como o do Duck DNS). Pessoas e números inventados (Ana, Beto).
