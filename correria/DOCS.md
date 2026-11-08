# CorrerIA

Os apps da casa (da CorrerIA Code) em três lugares:

- no **WhatsApp**, num contato da CorrerIA Code: as pessoas da casa perguntam ("quanto gastei com mercado este mês?", "o que tem na agenda amanhã?") e pedem ("lança 45 de mercado", "marca a tarefa do lixo como feita");
- no **Claude** e no **Gemini**, como um conector;
- na conversa da própria tela do CorrerIA.

Cada app, com a opção **CorrerIA** ligada nele (Mais › Configurações › Integrações), publica as suas ferramentas: o que dá para ler e mudar nele. O CorrerIA junta as ferramentas de todos e a IA usa as que precisa.

Usa a **API oficial do WhatsApp Business** (da Meta): sem risco de o número ser bloqueado, como acontece com os jeitos não oficiais.

## Do que precisa

- Uma conta na Meta para desenvolvedores, com um app do tipo **Empresa** e o produto **WhatsApp**. Para começar, a Meta dá um **número de teste**, que conversa com até 5 números cadastrados. Para todo mundo conversar, depois, um número só do CorrerIA (um chip que não esteja no WhatsApp comum).
- O Home Assistant acessível pela internet com **https**, só na porta do CorrerIA: o app **Duck DNS** (com o Let's Encrypt) e a porta **8443** encaminhada no roteador. O Nabu Casa não serve, porque ele não chega nos apps.
- Nos apps, a opção **CorrerIA** ligada (GerencIA 1.39.0, CronologIA 1.60.0, ResolvIA 2.49.0, InventarIA 1.37.0 e MemorIA 1.8.0 ou mais novos).
- Para o WhatsApp e a conversa da tela, uma IA no Home Assistant (Configurações › Sistema › IA: a entidade padrão das tarefas de IA).

## Passo a passo

### 1. Na Meta (developers.facebook.com)

1. **Meus apps › Criar app**, tipo **Empresa**, e adicione o produto **WhatsApp**.
2. Em **WhatsApp › Configuração da API**, anote o **ID do número de telefone** e cadastre o seu celular como destinatário do número de teste (chega um código pelo WhatsApp).
3. Token que não vence: em **business.facebook.com › Configurações › Usuários do sistema**, adicione um usuário **Administrador**, dê a ele o app e o WhatsApp como ativos e toque em **Gerar token**, com as permissões `whatsapp_business_messaging` e `whatsapp_business_management` e validade **Nunca**. (O token da tela de Configuração da API vence em 24 horas.)
4. Em **Configurações do app › Básico**, copie a **Chave secreta do aplicativo**. Ela confere que cada mensagem veio mesmo da Meta.

### 2. No Home Assistant e no roteador

1. Instale o app **Duck DNS** (loja oficial). Crie um nome em duckdns.org (ex.: `casa-exemplo.duckdns.org`), cole o token do Duck DNS e ligue o **Let's Encrypt** (aceitar os termos). Ele gera o certificado em `/ssl` e renova sozinho; o CorrerIA usa o novo sem reiniciar.
2. No roteador, encaminhe a porta **8443** (TCP) para o IP do Home Assistant, porta 8443. Para usar outra porta de fora, mude a porta do CorrerIA em **Configurações › Aplicativos › CorrerIA › Rede**.
3. Só o endereço do webhook fica aberto na internet: a tela do CorrerIA continua só pelo painel do Home Assistant, e qualquer mensagem sem a assinatura da Meta é recusada.

### 3. No CorrerIA

O CorrerIA abre na **Conversa**. A engrenagem no alto abre as **Opções**, em três abas: **Apps** (os apps ligados, a IA, o áudio e as últimas mensagens), **WhatsApp** (a conta, o webhook e quem conversa) e **Claude e Gemini**. A aba escolhida fica guardada.

1. **WhatsApp** (aba WhatsApp): cole o ID do número, o token e a chave secreta e toque em **Salvar**. O app confere com a Meta e mostra o número e o nome. O token e a chave não aparecem mais (só o fim, como ••••1234); para trocar, cole outro.
2. **Webhook na Meta**: escreva o **Endereço público** (ex.: `https://casa-exemplo.duckdns.org:8443`). Na Meta, em **WhatsApp › Configuração › Webhook**, toque em Editar, cole a **URL de retorno** e o **Token de verificação** que o CorrerIA mostra e toque em **Verificar e salvar**. Depois, em Campos do webhook, assine **messages**. O cartão mostra quando a Meta confirmou o endereço e a última mensagem que chegou.
3. **Quem conversa**: escreva o WhatsApp de cada pessoa da casa (as pessoas do Home Assistant). Só esses números recebem resposta; os outros aparecem em Últimas mensagens como "sem cadastro", sem resposta.
4. Em cada app, ligue **Mais › Configurações › Integrações › CorrerIA**. Eles aparecem na aba **Apps**, com o que fazem ("Lê e muda").
5. A **Conversa** (onde o CorrerIA abre) fala com os apps pela tela, sem passar pela Meta: bom para conferir antes de terminar a parte da Meta.

Pronto: mande "oi" do seu WhatsApp para o número do CorrerIA.

## Como responde

- Recebeu, o CorrerIA marca como lida, mostra "digitando…" e passa a pergunta para a IA do Home Assistant, com as ferramentas dos apps: ela lê o que precisa nos apps e responde. A resposta volta no jeito do WhatsApp (negrito com *asterisco*), em partes se for longa.
- **Para mudar algo** ("lança 32,50 de feira", "paguei a internet"), o CorrerIA responde o que vai fazer ("Vou fazer isto: Lançar R$ 32,50 de Feira hoje. Responda *sim* para confirmar") e só faz depois do **sim** (também vale "pode", "ok", "confirmo"). **Não** cancela; outra pergunta também. O pedido espera até 30 minutos.
- A conversa de cada pessoa vai junto com a pergunta (as últimas mensagens de até 12 horas atrás), para a IA lembrar do que se falou. Depois disso, recomeça.
- **Fotos e PDFs**: mande a foto de uma nota, um print ou a fatura em PDF (com ou sem uma pergunta na legenda). O CorrerIA passa para o app do assunto que lê aquele tipo (na aba **Apps** aparece o que cada um lê). No GerencIA, a IA lê como no Ler com IA: o que ela achar fica para conferir nos **Avisos do Início** ("Enviado por Ana · Pelo WhatsApp · 4 lançamentos") e a resposta lista o que foi lido; nada é lançado sozinho. A fatura em PDF com senha abre com as **Senhas dos PDFs** do GerencIA; se nenhuma abrir, a resposta pede para cadastrar e mandar de novo. Com uma pergunta junto ("quanto deu essa nota?"), a resposta vem com o que foi lido. Até 20 MB.
- **Áudio**: o CorrerIA ouve pela fala para texto do Home Assistant (Configurações › Assistentes de voz; a do Home Assistant Cloud primeiro) e manda o texto para o app, como se a pessoa tivesse escrito. O WhatsApp grava em OGG: na aba **Apps**, a linha **Áudio** diz se a fala para texto aceita esse formato. Se não aceitar, a resposta pede para escrever.
- Vídeo, figurinha e localização recebem "Por enquanto eu entendo texto, áudio, foto e PDF".
- Pelo WhatsApp, a IA fala só dos apps da casa: é a regra do WhatsApp para contatos de empresas (assistente para qualquer assunto não é permitido).
- Sem nenhuma IA no Home Assistant, as perguntas vão para o GerencIA, que responde com a IA dele (só responde).
- **Responder pelo WhatsApp**, no cartão WhatsApp, pausa as respostas sem desligar nada.
- Fotos e PDFs vão para o app que lê aquele tipo (hoje, o GerencIA); áudio vira texto antes.
- **Últimas mensagens** (aba Apps) mostra o que chegou, o que foi respondido, os números sem cadastro e os erros (como "Passaram mais de 24 horas": o WhatsApp só deixa responder até 24 horas depois da última mensagem da pessoa).

## Claude e Gemini

A aba **Claude e Gemini** (nas Opções) liga os apps da casa no Claude e no Gemini, como um conector (o padrão MCP). Eles veem as ferramentas de todos os apps ligados e leem e mudam os dados: "quanto gastei com mercado em outubro?", "lança 45,90 de mercado no cartão", "o que tem na agenda amanhã?". Antes de mudar algo, eles mostram o que vão fazer.

1. Ligue **Conectar o Claude e o Gemini** e confira o **Endereço público** (na aba WhatsApp, cartão Webhook). Ele usa a mesma porta (8443) e o mesmo certificado do WhatsApp; só o endereço do conector e o login ficam abertos, e só com essa opção ligada.
2. Copie o **Endereço do conector** (ex.: `https://casa-exemplo.duckdns.org:8443/mcp`).
3. **No Claude** (planos Pro, Max, Team ou Enterprise): **Configurações › Conectores › Adicionar conector personalizado**, dê um nome (CorrerIA), cole o endereço e toque em **Conectar**. Feito uma vez no site, vale também no app do celular.
   **No Gemini** (no site gemini.google.com; hoje só no plano Google AI Ultra): **Configurações › Apps conectados › Adicionar app personalizado**, cole o endereço e toque em **Próximo**.
4. Abre uma página do CorrerIA com um **código**. Abra o CorrerIA no Home Assistant: o pedido aparece no alto da Conversa (e no sino do Home Assistant), com o mesmo código: toque nele e em **Aprovar**. A página volta sozinha para o Claude ou o Gemini.

A conexão fica com a pessoa que aprovou (as mudanças são registradas no nome dela). Em **Conectados** aparecem os conectados e quando usaram; **Desconectar** tira na hora. O que eles mudam aparece em **Últimas mensagens**. Desligado, o endereço do conector some da internet (as conexões voltam a valer quando ligar de novo).

O que eles leem vai para a Anthropic (Claude) ou para o Google (Gemini), como qualquer conversa com eles.

## Conversar com a IA

O CorrerIA abre na **Conversa** com os apps da casa, do mesmo jeito que pelo WhatsApp, mas sem passar por ele (e sem a regra de só falar dos apps). Pergunte ("quanto gastei este mês?"), peça uma mudança (com o **sim**, como no WhatsApp), **tire uma foto** pela câmera (a câmera abre aqui dentro; em http, sem https, dá para tirar ou escolher a foto pelo celular) ou mande uma **foto** ou um **PDF** pelo clipe; embaixo de cada resposta aparece qual app foi usado. Com a conversa vazia, aparecem sugestões: é só tocar.

As conversas são de quem está usando a tela (o login do Home Assistant, ligado à pessoa) e ficam guardadas: fechou, abre de onde parou. No alto, **Nova conversa** começa outra (a de antes fica guardada) e **Conversas** abre a lista, como nos chats de sempre: a mais recente primeiro, com o nome tirado da primeira pergunta; toque para abrir ou na lixeira para apagar. Na conversa, arrastar o dedo para o lado passa para as outras: para a esquerda, a anterior (mais antiga); para a direita, a mais nova. Ficam as últimas 30 conversas, cada uma com as últimas 40 mensagens. Nas Opções e no Sobre, o Voltar do celular volta um passo.

## Sobre

No fim das Opções, **Sobre**: a CorrerIA Code, os apps da família (com o link de cada um no GitHub) e o meu GitHub. É o mesmo Sobre dos outros apps.

## Custo e privacidade

- A Meta não cobra as mensagens que as pessoas mandam. As respostas do CorrerIA são grátis até 1.000 por mês por número (regra da Meta desde outubro de 2026); depois disso, alguns centavos cada.
- As perguntas e as respostas do WhatsApp passam pelos servidores da Meta. A IA é a do Home Assistant.
- O login do Claude e do Gemini fica em `/data/mcp.json` (os tokens só como hash), também no backup.
- A configuração e as conversas ficam em `/data` (config.json e conversas.json, só para o app) e entram no backup do Home Assistant.
