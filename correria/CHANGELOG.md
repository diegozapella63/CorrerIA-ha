# Mudanças

## 0.4.0

- **Claude e Gemini**: um cartão novo conecta os apps da casa ao Claude e ao Gemini, como um conector. Eles leem e mudam os dados dos apps (lançar um gasto, marcar uma conta como paga, criar uma tarefa…). Cole o endereço do conector no Claude (Configurações › Conectores) ou no Gemini (Apps conectados); ao conectar, aparece um código, e você aprova o pedido aqui, no Home Assistant, sem senha nova. O pedido aparece no alto da tela e no sino do Home Assistant. Em **Conectados**, quem está ligado e quando usou, com **Desconectar**.
- **WhatsApp com todos os apps**: a IA do Home Assistant usa as ferramentas de todos os apps ligados, então qualquer app responde pelo WhatsApp e pela conversa da tela, e dá para mudar coisas também: o CorrerIA mostra o que vai fazer e só faz depois do seu **sim** (ou nada, com **não**).
- **Apps da casa** (antes Apps que respondem) mostra o que cada app faz pelo CorrerIA ("Lê e muda") e se a IA do Home Assistant está respondendo.
- O que o Claude e o Gemini mudam aparece em **Últimas mensagens**.

## 0.3.0

- **Conversar com a IA** pela tela do CorrerIA (o balão no alto): a mesma conversa do WhatsApp, sem passar por ele. Pergunte sobre os apps da casa ou mande uma foto ou um PDF; a pergunta vai para o app do assunto e a resposta mostra qual app respondeu. A conversa fica guardada para cada pessoa (as últimas 40 mensagens); a lixeira no alto apaga. Substitui o Testar uma pergunta.
- **Sobre**, o mesmo dos outros apps: CorrerIA Code, os apps da família e o GitHub.
- O Voltar do celular volta da conversa e do Sobre para a tela principal.

## 0.2.0

- **Fotos e PDFs**: mande a foto de uma nota, um print ou a fatura em PDF e o app do assunto lê com a IA. No GerencIA, o que ele achar fica para conferir nos Avisos do Início (nada é lançado sozinho), e a fatura com senha abre com as Senhas dos PDFs. Com uma pergunta junto ("quanto deu essa nota?"), a resposta vem com o que foi lido.
- **Áudio**: o CorrerIA ouve o áudio pela fala para texto do Home Assistant e manda o texto para o app, então todos os apps entendem áudio. Em **Apps que respondem** aparece se a fala para texto aceita o áudio do WhatsApp.
- Em **Apps que respondem**, o que cada app lê além de texto.

## 0.1.0

- Primeira versão: o contato da CorrerIA Code no WhatsApp, pela API oficial da Meta.
- As pessoas da casa perguntam pelo WhatsApp e o GerencIA responde sobre as finanças, com a IA e os seus dados.
- Só os números cadastrados em **Quem conversa** recebem resposta.
- Tela com o WhatsApp (confere com a Meta), o webhook (endereço, URL de retorno e token de verificação para colar na Meta, o certificado do Duck DNS), quem conversa, os apps que respondem com **Testar uma pergunta** e as últimas mensagens.
