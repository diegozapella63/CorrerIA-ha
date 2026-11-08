# Mudanças

## 0.8.0

- A aba **Claude e Gemini** passa a se chamar **MCP**, com textos que valem para qualquer IA que aceite um conector personalizado (como o ChatGPT), e não só o Claude e o Gemini. O passo a passo ficou: na IA, adicione um **conector personalizado** com o endereço e aprove aqui o pedido com o código.

## 0.7.2

- Sem o "da casa" nos textos: **Apps** (nas Opções), "Os apps dentro do Claude e do Gemini", "Pergunte ou peça algo aos apps" e a descrição na loja de aplicativos.
- **Sobre**: a linha da CorrerIA agora diz o que ela é: "Pergunte e peça a qualquer app, no chat ou no WhatsApp."

## 0.7.1

- No alto da **Conversa**, **Olá** e o nome de quem está usando, como nos outros apps (CorrerIA · Olá, Ana), no lugar de "os apps da casa".

## 0.7.0

- Na **Conversa**, arrastar o dedo para o lado passa pelas conversas já guardadas, como nos outros apps: para a esquerda, a anterior (mais antiga); para a direita, a mais nova. Da conversa nova, ainda vazia, para a esquerda abre a mais recente. No fim da lista, a tela só balança de leve.

## 0.6.0

- **Nova conversa**, no alto da Conversa: começa outra do zero, e a de antes fica guardada.
- **Conversas**, também no alto: a lista das conversas com a IA, como nos chats de sempre. A mais recente fica primeiro, com o nome tirado da primeira pergunta, quando foi e quantas mensagens tem. Toque para abrir ou na lixeira para apagar. Ficam as últimas 30 conversas de cada login.
- **Tirar foto**, ao lado do clipe: a câmera abre aqui dentro, em tela cheia, como nos outros apps. A foto vai junto da próxima mensagem, com a miniatura antes de enviar. Em http (sem https) ou sem permissão, o app explica e oferece tirar ou escolher a foto pelo celular. O Voltar do celular fecha a câmera.

## 0.5.0

- O CorrerIA abre direto na **Conversa** com a IA: é só escrever (ou mandar uma foto ou um PDF). A lixeira e a engrenagem ficam no alto.
- A engrenagem abre as **Opções**, em abas: **Apps** (os apps ligados, a IA, o áudio e as últimas mensagens), **WhatsApp** (a conta, o webhook e quem conversa) e **Claude e Gemini**. A aba escolhida fica guardada; o **Sobre** fica no fim.
- Um pedido do Claude ou do Gemini para conectar aparece no alto da Conversa: um toque leva direto para aprovar.
- O Voltar do celular volta um passo: do Sobre para as Opções e das Opções para a Conversa.

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
