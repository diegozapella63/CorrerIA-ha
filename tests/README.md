# Testes do CorrerIA

```
python3 -m unittest discover -s tests -t .
```

Só biblioteca padrão, mais o **playwright** com o Chromium para a tela (`pip install playwright && python -m playwright install chromium`) e o **openssl** para o teste do https. No GitHub, falha também se algum teste for pulado.

| Arquivo | O que testa |
|---|---|
| `test_whatsapp.py` | a assinatura do webhook, as mensagens e as falhas no que a Meta manda, o texto no jeito do WhatsApp (negrito, partes), os números do Brasil com e sem o 9 e o cliente da Graph API |
| `test_fala.py` | o áudio do WhatsApp em texto: o motor que aceita OGG/Opus, o cabeçalho, o idioma, os erros |
| `test_apps.py` | achar os apps (`share/*/correria.json`), escolher o app da pergunta, perguntar (chave, IP de reserva, erros), listar e chamar as ferramentas de um app |
| `test_ferramentas.py` | as ferramentas de todos os apps juntas (`<app>_<nome>`), o `<app>_perguntar` de quem só tem rota, erros e app fora do ar |
| `test_ia.py` | a IA do WhatsApp e da tela com as ferramentas: ler e responder, propor mudanças, ferramenta errada, só texto, rodadas, a IA simulada |
| `test_mcp.py` | o protocolo MCP: initialize, tools/list (com as dicas de leitura e de apagar), tools/call, notificações, listas, erros |
| `test_oauth.py` | o login do Claude e do Gemini: registro, pedido com PKCE, aprovar e recusar, token, renovar (gira), desconectar, prazos, erros, limites |
| `test_servidor.py` | a configuração (o token nunca volta), quem conversa, responder (conversa, número sem cadastro, repetida, áudio, pausado, sem app, erros), com as ferramentas (ler, o sim, o não, o prazo, a IA do Home Assistant fora do ar), o webhook (token de verificação, assinatura, só /webhook, https com certificado e renovação), o Claude e o Gemini pela porta pública (do registro ao MCP, desligado, erros) e a tela (rotas, só pelo painel) |
| `test_tela.py` | a tela num Chromium a 390 px: abre na conversa, as Opções em abas (guardadas, numa linha até 320 px), configurar e conferir, pausar, webhook e copiar, quem conversa, os apps (o que cada um faz), o conector MCP (ligar, endereço, pedido no alto, aprovar e recusar, conectados, desconectar), Conversar com a IA (texto, sugestão, foto, conversa guardada, Voltar do celular), últimas mensagens, Sobre, tudo pronto, tema claro e escuro |

Ajuda em `base.py`: `importar_servidor()` (o `server.py` com pastas temporárias), `ServidorFalso` (um servidor HTTP que guarda os pedidos), `MetaFalsa` (a Graph API), `AppFalso` (um app da família com as ferramentas) e `certificado()` (um certificado próprio, como o do Duck DNS). Pessoas e números inventados (Ana, Beto).
