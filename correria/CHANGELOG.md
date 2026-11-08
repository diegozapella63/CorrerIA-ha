# Mudanças

## 0.2.0

- **Fotos e PDFs**: mande a foto de uma nota, um print ou a fatura em PDF e o app do assunto lê com a IA. No GerencIA, o que ele achar fica para conferir nos Avisos do Início (nada é lançado sozinho), e a fatura com senha abre com as Senhas dos PDFs. Com uma pergunta junto ("quanto deu essa nota?"), a resposta vem com o que foi lido.
- **Áudio**: o CorrerIA ouve o áudio pela fala para texto do Home Assistant e manda o texto para o app, então todos os apps entendem áudio. Em **Apps que respondem** aparece se a fala para texto aceita o áudio do WhatsApp.
- Em **Apps que respondem**, o que cada app lê além de texto.

## 0.1.0

- Primeira versão: o contato da CorrerIA Code no WhatsApp, pela API oficial da Meta.
- As pessoas da casa perguntam pelo WhatsApp e o GerencIA responde sobre as finanças, com a IA e os seus dados.
- Só os números cadastrados em **Quem conversa** recebem resposta.
- Tela com o WhatsApp (confere com a Meta), o webhook (endereço, URL de retorno e token de verificação para colar na Meta, o certificado do Duck DNS), quem conversa, os apps que respondem com **Testar uma pergunta** e as últimas mensagens.
