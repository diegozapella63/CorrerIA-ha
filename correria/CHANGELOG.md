# Mudanças

## 1.13.1

- **Conversa**: o cabeçalho (CorrerIA › Conversa e os botões) fica sempre no alto, mesmo ao rolar as mensagens. Antes ele saía da tela junto com elas.

## 1.13.0

- **Conector MCP › Pelo túnel da Cloudflare**: para quando a operadora bloqueia a porta 443 (ou usa CGNAT). Ligado, o CorrerIA abre uma porta só na rede de casa para o app **Cloudflared** do Home Assistant e mostra, pronto para copiar, o que vai nele. As IAs chegam pela 443 da Cloudflare, sem abrir porta no roteador. O cartão diz quando chegou uma conexão pelo túnel.
- **Conector MCP**: avisa quando o endereço tem uma porta no fim, porque as IAs (como o Claude) só conectam na porta 443. O texto do cartão agora explica isso.

## 1.12.0

- **Editar perguntas**: toque numa pergunta para mudar o texto dela. Uma pergunta apagada até ficar vazia sai da lista.

## 1.11.0

- **Conector MCP**: a opção que o Claude recomenda no login (a identidade publicada da IA) passa a funcionar. O registro automático continua valendo.
- **Conector MCP e Webhook**: o cartão mostra de que endereço é o certificado e avisa quando é de outro. Avisa também quando falta a porta no fim do endereço e quando chegou (ou não) uma conexão de fora de casa, e se ela abriu. Assim fica claro se o que falta é o Duck DNS, o roteador ou o certificado.
- **Conector MCP**: o passo a passo ficou mais claro: copiar, adicionar o conector personalizado e aprovar o código.
- **Editar perguntas**: **Perguntas prontas** e **Mais perguntas** fecham num toque no título, com a seta no canto. O aparelho lembra.
- **Configurações › Opções › Conversas**: agora é **Guardar as conversas por** 7, 30 ou 90 dias, ou **Sempre**.

## 1.10.0

- **Sim e Não para tocar**: quando a IA vai mudar algo nos apps, a conversa mostra os botões **Sim** e **Não** embaixo da mensagem, e o WhatsApp também, com botões. Escrever sim continua valendo.
- **Perguntas prontas**: 6 à vista, uma de cada app ligado, e em **Editar perguntas** mais 20 modelos dos apps (um toque põe a pergunta na lista).

## 1.9.0

- **O fundo e os cartões seguem o tema do Home Assistant**, no claro e no escuro: o mesmo fundo do Home Assistant e dos outros apps da família (antes, cada app tinha o seu). Com um tema seu no Home Assistant, o app usa as cores dele; ao trocar o tema ou o modo no Home Assistant, o app muda junto.
- **Conversa e WhatsApp**: a IA responde com todos os acentos (algumas IAs escreviam "voce" e "Alimentacao").
- **Conversa e WhatsApp**: quando um app devolve mais do que cabe, a IA sabe que viu só uma parte e pede o resto, em vez de responder como se fosse tudo. E as leituras e mudanças além do limite de uma vez não somem mais caladas: as mudanças que ficaram de fora aparecem embaixo do **sim**.

## 1.8.0

- **No computador** (1000 px ou mais): a barra lateral dos outros apps, em todas as telas. No alto o CorrerIA, depois **Conversa** e **Mais**, as **Conversas** (a aberta marcada, o + para uma nova, a lixeira ao passar o mouse) e a versão embaixo. A Conversa fica com o resto da tela; Mais, Configurações e Sobre ficam no meio, como nos outros apps.

## 1.7.0

- **No computador** (1000 px ou mais): a Conversa ocupa a tela toda, e as conversas ficam numa lateral à esquerda, com a **Nova conversa** no alto e a aberta marcada, como nos chats de sempre. No celular, nada muda.
- **Configurações › Opções › Conversas**: as conversas paradas há mais de **7**, **30** ou **90 dias** saem sozinhas, ou **Nunca**. Começa em 30 dias. Vale para as conversas daqui e para as mensagens guardadas do WhatsApp.
- A aba **Opções** agora aparece sempre.

## 1.6.2

- **Conversa**: para o que não está nos apps e muda com o tempo (preços, lojas, níveis e benefícios de bancos, novidades, notícias), a IA agora pesquisa na internet antes de responder, em vez de responder de memória.

## 1.6.1

- **Configurações › Opções › Tela cheia**: o ícone do **Recolher a Conversa sozinha** fica na mesma linha do título, e os tempos ficam em duas linhas (1 e 3 minutos, 5 e 10 minutos), sem o "10 min" quebrar.

## 1.6.0

- **Pesquisar na internet**: na Conversa daqui, a IA pesquisa na internet o que os apps não têm, como preços, lojas e novidades ("quanto custa a geladeira tal?", "pesquise lojas de piso em Curitiba"). A resposta diz de onde veio. No WhatsApp não (lá a IA fica nos apps, pela regra da Meta); o Claude e o Gemini já pesquisam sozinhos.
- **Configurações › Apps › IA** (antes "IA do Home Assistant"): além da IA **Para conversar**, agora há a **Para pesquisar na internet**, que começa **Igual à de conversar**. Escolha nela uma IA do Home Assistant com a busca na web ligada (no Claude, a opção de pesquisa na web da integração).
- **Uso da IA**: as pesquisas aparecem como **Pesquisa na internet**.

## 1.5.0

- **Casa**: o Home Assistant entrou como mais um app. Na Conversa, no WhatsApp e no Claude dá para pedir "liga a luz da entrada", "fecha a cortina da sala" ou "põe o ar em 23 graus". O pedido vai para o Assist do Home Assistant, que só mexe no que está exposto a ele. Dá também para perguntar como está ("a luz da sala está ligada?", "qual a temperatura?"). Cada mudança espera o seu **sim**, como nos outros apps. Liga e desliga em **Configurações › Apps › Casa** (vem ligada).
- **Tela cheia**: a Conversa recolhe sozinha depois de **3 minutos** sem uso (antes, 5). O tempo muda em **Configurações › Opções › Tela cheia** (1, 3, 5 ou 10 minutos).

## 1.4.1

- **Conversa**: com um teclado (o computador, a TV), **Enter** envia e **Shift+Enter** quebra a linha, como no WhatsApp Web. Antes, numa tela de toque com teclado, o Enter só quebrava a linha. No celular, o Enter do teclado da tela continua quebrando a linha.
- O que você escreveu em mais de uma linha aparece assim no balão.

## 1.4.0

- **Tela cheia** (com a CronologIA 1.97.0 ou mais nova): sem a faixa do lado. Os botões da Conversa e do **Sair da tela cheia** ficam no alto do painel, ao lado do relógio, e o painel fica com a tela toda. Aberta, a Conversa toma o lugar da folha do MemorIA; o resto do painel fica onde estava. O ponto de resposta nova aparece no botão do alto.
- **Ctrl+Espaço** abre a Conversa e, aberta, recolhe (fora da tela cheia, leva o cursor para a caixa de escrever).

## 1.3.0

- **Tela cheia**: a Conversa começa **recolhida**, numa faixa fina à direita, e o painel da CronologIA fica com quase a tela toda. Um toque no botão da faixa abre a Conversa. Aberta, ela recolhe sozinha depois de **5 minutos sem uso**, ou quando você toca em **Recolher**. Se uma resposta chegar com ela recolhida, aparece um ponto no botão.
- **Fixar** (o alfinete, no alto da Conversa): a Conversa fica aberta e não recolhe mais, nem da próxima vez. Toque de novo para soltar.
- **Barras de rolagem** finas e arredondadas, sem as setinhas.

## 1.2.0

- **Tela cheia** (telas de 1100 px ou mais, para a TV ou o tablet na parede): o botão no alto da Conversa põe o painel da tela cheia da CronologIA à esquerda (o **A seguir**, o que vem **Depois**, as **Tarefas do dia**, o placar e a folha do MemorIA) e a **Conversa** à direita, sempre à mão para pedir qualquer coisa aos apps. O painel se atualiza sozinho com o que você pede na Conversa. Sai pelo mesmo botão, pelo **Esc** ou pelo **Voltar** do celular. Precisa da CronologIA 1.95.0 ou mais nova (abra a CronologIA uma vez depois de atualizar).

## 1.1.0

- **Conversa › Clipe**: um botão só com **Tirar foto**, **Escolher fotos** (a galeria do celular) e **Escolher arquivo** (uma foto ou um PDF).
- **Conversa › Perguntas prontas**: as sugestões viram suas. **Editar perguntas** tira (✕) e acrescenta as que você quiser; **Padrão** volta às dos apps. Ficam guardadas no aparelho.
- **Conversa**: o botão ✨ ao lado da caixa abre as perguntas prontas a qualquer momento, não só na conversa vazia.

## 1.0.0

- **Primeira versão completa** do CorrerIA: os apps da casa (CronologIA, ResolvIA, GerencIA, InventarIA, MemorIA) num lugar só, para perguntar e pedir:
  - na **Conversa** do próprio app, com a IA do Home Assistant;
  - no **WhatsApp**, pelo contato da CorrerIA Code (a API oficial da Meta), com foto, PDF e áudio;
  - no **Claude**, no **Gemini** e em qualquer IA que aceite um conector personalizado, pelo **conector MCP**, com o login aprovado aqui.
- As mudanças só acontecem depois do **sim** da pessoa; as do conector ficam em **Últimas mudanças**.
- No padrão da família: ícones em tudo, seções que contraem, sub-opções num quadro, **Uso da IA**, **Sensores no Home Assistant**, **Aparência** (tema e cor) e **Sobre**.

## 0.17.1

- **Sensores no Home Assistant** como no ResolvIA: a chave **Criar sensores** e, num quadro embaixo dela, cada sensor numa linha com o que mostra.
- **Últimas chamadas** (Uso da IA) com quantas são.

## 0.17.0

- **WhatsApp liga e desliga**, como o conector MCP: **Usar o WhatsApp**, em Configurações › WhatsApp. Desligado, só aparece a chave e o CorrerIA não responde nem guarda as mensagens. Ligado, o resto (o estado, Responder pelo WhatsApp, os campos e o Conferir) fica num quadro embaixo da chave. Quem já tinha configurado continua ligado.
- **Sem o botão Salvar**: o ID do número, o token e a chave secreta se salvam ao sair do campo, como o endereço; com os três, o CorrerIA confere com a Meta sozinho.
- **Contrair e expandir**: um toque no cabeçalho de uma seção fecha ou abre (a seta no canto); o aparelho lembra as que ficaram fechadas.
- **Últimas mudanças** (no Conector MCP) ficam recolhidas, com a contagem.

## 0.16.3

- **Conector MCP**: o que depende do conector (os pedidos para conectar, o endereço público e o do conector, os conectados e as **Últimas mudanças**) fica num quadro embaixo de **Ligar o conector**, dentro do cartão dele. Com o conector desligado, nada disso aparece.

## 0.16.2

- **Configurações**: a seta que mostra que há mais abas agora aparece (na 0.16.1 ela ficava escondida atrás das abas), e acompanha a largura delas quando a fonte do app termina de carregar.

## 0.16.1

- **IA do Home Assistant** no padrão dos outros apps: o estado em verde quando está tudo certo ("Pronta para conversar · Usando…"), a **IA para conversar** numa caixa de seleção (a janela do app, como nos outros) e o **Verificar de novo**.
- **Configurações**: quando as abas não cabem, a ponta de onde há mais some aos poucos, com uma seta.
- **WhatsApp**: saiu a linha "Falta terminar a configuração do WhatsApp" do alto; o cartão do WhatsApp já diz o que falta.

## 0.16.0

- **IA para conversar** (em **Configurações › Apps › IA do Home Assistant**), como nos outros apps: escolha qual IA do Home Assistant responde no WhatsApp e na conversa. De início fica a padrão do Home Assistant.
- O nome da IA aparece no que deu certo ("Claude AI Task respondeu hoje às 14:32"), nos erros e nas **Últimas chamadas** do Uso da IA. Sem cota, o aviso fica em português: "… ficou sem cota (o limite de uso acabou)".
- **Ícones em tudo**, como nos outros apps: nas abas (no computador), no título das telas, nas linhas (Responder pelo WhatsApp, Ligar o conector, Criar os sensores, Cor do dia), nos campos (ID do número, Token, Endereço público…), nas Últimas chamadas e em todo botão com texto (Conferir, Salvar, Aprovar, Desconectar, Limpar, as sugestões da conversa). Os Sensores ganharam o seu ícone.
- A lista das conversas não tem mais a linha depois da última.

## 0.15.0

- **Últimas mensagens** foi para o fim da aba **WhatsApp**. O que as IAs conectadas mudaram fica na aba **MCP**, em **Últimas mudanças**, cada um com o seu **Limpar**.
- **MCP**: o **Endereço público** e o certificado aparecem na própria aba (antes, ela mandava escrever o endereço na aba WhatsApp). O estado do WhatsApp ("Falta terminar a configuração do WhatsApp") só aparece na aba dele.
- **Uso da IA** no padrão dos outros apps: toque numa barra para ver o dia, os tipos em etiquetas e as **Últimas chamadas** recolhidas, com o motivo quando deu errado.
- O áudio ficou mais claro: "Áudios do WhatsApp viram texto pelo Home Assistant Cloud.", na aba **WhatsApp**.

## 0.14.0

- **Sensores no Home Assistant** (em **Configurações › Apps**, depois do Uso da IA; vem desligado): `sensor.correria_certificado`, com os dias até o certificado vencer, e `binary_sensor.correria_whatsapp`, ligado com o WhatsApp conectado (e o erro da Meta quando cai, como um token vencido). A aba **Documentação** traz um exemplo de automação.

## 0.13.1

- **Configurações**: no celular estreito, a aba escolhida (como **Opções**, a última) fica à vista; antes, as abas voltavam para o começo.

## 0.13.0

- **Atalho no celular** saiu de Aparência e foi para uma aba nova, **Opções** (Mais › Configurações › Opções), como nos outros apps.

## 0.12.1

- **Atalho no celular**: o caminho fica na largura toda, inteiro também nos celulares estreitos, com o **Copiar** embaixo.

## 0.12.0

- **Atalho no celular**, em **Mais › Configurações › Aparência**: o caminho do CorrerIA no Home Assistant, com **Copiar**, e como criar um ícone na tela inicial do celular que abre a Conversa direto (no app do Home Assistant: Configurações › Aplicativo complementar › Gerenciar atalhos). O mesmo vale em todos os apps da família.

## 0.11.1

- **Tema**: **Automático** agora se chama **Sistema** (segue o claro ou escuro do Home Assistant, como antes). O nome cabe ao lado do ícone e é o mesmo em todos os apps da família.

## 0.11.0

- **Uma altura só**: botões, campos e botões de escolha (as abas de Configurações, o Tema) têm a mesma altura, a mesma de todos os apps da família. O Tema ficou com o ícone ao lado do nome.

## 0.10.1

- Nada muda na tela. A versão do app agora é escrita num lugar só, e os testes passam a cobrir quase todo o servidor (mais de 95%).

## 0.10.0

O CorrerIA fica igual aos outros apps da família:

- **Mais**: os três pontos no alto da Conversa abrem um menu, como nos outros apps: **Configurações** (antes Opções) e, por último, **Sobre**, que sai de dentro de Configurações.
- **Configurações** ganha as abas **Dados** (onde ficam os dados, sem mostrar token nem chave) e **Aparência**: o **tema** (Automático, Claro ou Escuro, só neste aparelho, começando em Automático) e a **cor do app** para a casa toda, com as 12 cores da família e a **Cor do dia**, a mesma dos outros apps. Antes, a cor era sempre âmbar.
- **Uso da IA**, na aba Apps: quantas vezes o CorrerIA chamou a IA hoje, em 7 dias e no mês, por dia, do WhatsApp e da Conversa, com as últimas chamadas e os tokens estimados.

## 0.9.0

- **Falar na Conversa**: com a caixa vazia, o botão redondo vira o microfone. Toque, fale e toque no ✓: o que você disse vai como a pergunta. O **X** cancela. Escrevendo, o botão volta a ser o Enviar. Usa a fala para texto do Home Assistant, a mesma dos áudios do WhatsApp.

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
