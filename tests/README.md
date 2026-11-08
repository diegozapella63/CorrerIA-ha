# Testes do CorrerIA

```
python3 -m unittest discover -s tests -t .
```

Só biblioteca padrão, mais o **playwright** com o Chromium para a tela (`pip install playwright && python -m playwright install chromium`) e o **openssl** para o teste do https. No GitHub, falha também se algum teste for pulado.

| Arquivo | O que testa |
|---|---|
| `test_whatsapp.py` | a assinatura do webhook, as mensagens e as falhas no que a Meta manda, o texto no jeito do WhatsApp (negrito, partes), os números do Brasil com e sem o 9 e o cliente da Graph API |
| `test_fala.py` | o áudio do WhatsApp em texto: o motor que aceita OGG/Opus, o cabeçalho, o idioma, os erros |
| `test_apps.py` | achar os apps (`share/*/correria.json`), escolher o app da pergunta, perguntar (chave, IP de reserva, erros) |
| `test_servidor.py` | a configuração (o token nunca volta), quem conversa, responder (conversa, número sem cadastro, repetida, áudio, pausado, sem app, erros), o webhook (token de verificação, assinatura, só /webhook, https com certificado e renovação) e a tela (rotas, só pelo painel) |
| `test_tela.py` | a tela num Chromium a 390 px: configurar e conferir, pausar, webhook e copiar, quem conversa, testar uma pergunta, últimas mensagens, tudo pronto, tema claro e escuro |

Ajuda em `base.py`: `importar_servidor()` (o `server.py` com pastas temporárias), `ServidorFalso` (um servidor HTTP que guarda os pedidos), `MetaFalsa` (a Graph API) e `certificado()` (um certificado próprio, como o do Duck DNS). Pessoas e números inventados (Ana, Beto).
