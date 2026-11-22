# CorrerIA

Os apps da CorrerIA Code em três lugares:

- no **WhatsApp**, num contato da CorrerIA Code: as pessoas da casa perguntam ("quanto gastei com mercado este mês?", "o que tem na agenda amanhã?") e pedem ("lança 45 de mercado", "marca a tarefa do lixo como feita");
- em outras IAs, como um **conector MCP**;
- na conversa da própria tela do CorrerIA.

Cada app, com a opção **CorrerIA** ligada nele (Mais › Configurações › Integrações), publica as suas ferramentas: o que dá para ler e mudar nele. O CorrerIA junta as ferramentas de todos e a IA usa as que precisa.

Usa a **API oficial do WhatsApp Business** (da Meta): sem risco de o número ser bloqueado, como acontece com os jeitos não oficiais.

## Do que precisa

- Uma conta na Meta para desenvolvedores, com um app do tipo **Empresa** e o produto **WhatsApp**. Para começar, a Meta dá um **número de teste**, que conversa com até 5 números cadastrados. Para todo mundo conversar, depois, um número só do CorrerIA (um chip que não esteja no WhatsApp comum).
- O CorrerIA acessível pela internet com **https**: o app **Duck DNS** (com o Let's Encrypt) e, no roteador, a porta de fora **443** encaminhada para a **8443** do Home Assistant (o Claude só conecta na 443); ou o **túnel da Cloudflare**, sem abrir porta (veja Conector MCP). O Home Assistant Cloud não serve, porque ele não chega nos apps.
- Nos apps, a opção **CorrerIA** ligada (GerencIA 1.39.0, CronologIA 1.60.0, ResolvIA 2.49.0, InventarIA 1.37.0 e MemorIA 1.8.0 ou mais novos).
- Para o WhatsApp e a conversa da tela, uma IA no Home Assistant (uma integração com tarefas de IA, como Anthropic, Google Gemini, OpenAI ou Ollama). Em **Configurações › Integrações › IA › Para conversar** você escolhe qual; de início fica a padrão do Home Assistant (Configurações › Sistema › IA). Em **Para pesquisar na internet** fica a IA que pesquisa na web na Conversa daqui (começa **Igual à de conversar**): escolha uma com a busca na web ligada no Home Assistant (no Claude, a pesquisa na web da integração; no Gemini, a pesquisa do Google). Ela só pesquisa na Conversa da tela: no WhatsApp a IA fica nos apps, pela regra da Meta, e o Claude e o Gemini pelo conector já pesquisam sozinhos. Sem a busca ligada, a IA avisa que não consegue pesquisar, em vez de responder de memória. O estado fica verde quando está tudo certo; **Verificar de novo** busca de novo a lista das IAs e esquece o erro da última chamada.

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

O CorrerIA abre na **Conversa**. Numa tela grande (1100 px ou mais), com a CronologIA 1.95.0 ou mais nova, o botão **Tela cheia** no alto da Conversa põe o painel da CronologIA à esquerda (o **A seguir**, o que vem **Depois**, as **Tarefas do dia**, o placar e a folha do MemorIA) e a Conversa à direita, para a TV ou o tablet na parede: dá para pedir qualquer coisa aos apps a qualquer momento, e o painel mostra a mudança na hora. Quando o navegador deixa, ocupa o monitor todo. A Conversa começa recolhida, numa faixa fina à direita: um toque no botão abre. Com a CronologIA 1.97.0 ou mais nova não há faixa: os botões da Conversa e do **Sair da tela cheia** ficam no alto do painel, ao lado do relógio, e a Conversa aberta toma o lugar da folha do MemorIA. **Ctrl+Espaço** abre e recolhe a Conversa (fora da tela cheia, leva o cursor para a caixa de escrever). Com um teclado, **Enter** envia e **Shift+Enter** quebra a linha. Aberta, ela recolhe sozinha depois de 3 minutos sem uso (o tempo muda em **Configurações › Opções › Tela cheia**: 1, 3, 5 ou 10 minutos) ou no **Recolher**; com o **Fixar** (o alfinete), fica sempre aberta, também nas próximas vezes, até você soltar. Sai pelo mesmo botão (**Sair da tela cheia**), pelo **Esc** ou pelo **Voltar** do celular. Se o botão não aparecer, abra a CronologIA uma vez (é assim que o CorrerIA fica sabendo o endereço dela). Os três pontos no alto abrem o **Mais**, um menu como nos outros apps: **Configurações** e, por último, **Sobre**. **Configurações** tem as abas **Apps** (os apps ligados, a IA, o **Uso da IA** e os **Sensores no Home Assistant**), **WhatsApp** (a conta, o áudio, o webhook, quem conversa e as **Últimas mensagens**), **MCP** (o conector, o endereço público e as **Últimas mudanças**), **Dados** (onde ficam os dados), **Aparência** (o tema e a cor do app) e **Opções** (o **Atalho no celular**; só dentro do Home Assistant). A aba escolhida fica guardada. Um toque no cabeçalho de uma seção fecha ou abre (o aparelho lembra). O Voltar do celular volta um passo de cada vez.

**Uso da IA** (na aba Integrações), como nos outros apps: quantas vezes o CorrerIA chamou a IA do Home Assistant hoje, em 7 dias e no mês, uma barra por dia (toque numa barra para ver aquele dia), os tipos (WhatsApp, Conversa e Pesquisa na internet) e, recolhidas, as **Últimas chamadas**, com o tempo, os tokens estimados e, quando deu errado, o motivo. O Home Assistant não informa o consumo exato: ele fica no painel do provedor da IA, e o fim do cartão traz, para cada IA em uso (a de conversar e a de pesquisar), o site onde ver o consumo e o saldo (o Google AI Studio, o Claude Console ou o da OpenAI).

**Aparência**: o **tema** (Sistema, Claro ou Escuro) vale só para o aparelho e começa em **Sistema**, que segue o do Home Assistant; o fundo e os cartões são os do tema do Home Assistant, os mesmos dos outros apps. A **cor do app** vale para a casa toda: são as 12 cores da família, com os mesmos nomes dos outros apps. Com a **Cor do dia** ligada (vem assim), a cor muda todo dia, a mesma em todos os apps; escolher uma cor desliga.

**Dados**: tudo fica na pasta `/data` do app, que entra no backup do Home Assistant: `config.json` (o WhatsApp, o endereço e o número de cada pessoa), `conversas.json`, `mcp.json` (as IAs conectadas, com os tokens só em código) e `uso_ia.json`. O token e a chave secreta nunca voltam para a tela.

1. **WhatsApp** (aba WhatsApp): ligue **Usar o WhatsApp** e cole o ID do número, o token e a chave secreta (cada um se salva ao sair do campo). Com os três, o app confere com a Meta e mostra o número e o nome; **Conferir com a Meta** confere de novo. Desligado, o CorrerIA não responde nem guarda as mensagens do WhatsApp. O token e a chave não aparecem mais (só o fim, como ••••1234); para trocar, cole outro.
2. **Webhook na Meta**: escreva o **Endereço público** (ex.: `https://casa-exemplo.duckdns.org:8443`). Na Meta, em **WhatsApp › Configuração › Webhook**, toque em Editar, cole a **URL de retorno** e o **Token de verificação** que o CorrerIA mostra e toque em **Verificar e salvar**. Depois, em Campos do webhook, assine **messages**. O cartão mostra quando a Meta confirmou o endereço e a última mensagem que chegou.
3. **Quem conversa**: escreva o WhatsApp de cada pessoa da casa (as pessoas do Home Assistant). Só esses números recebem resposta; os outros aparecem em Últimas mensagens como "sem cadastro", sem resposta.
4. Em cada app, ligue **Mais › Configurações › Integrações › CorrerIA**. A aba **Integrações** mostra todos os apps da família: os ligados primeiro, com o que fazem ("Lê e muda"), e os outros com **Integração desligada**.
5. A **Conversa** (onde o CorrerIA abre) fala com os apps pela tela, sem passar pela Meta: bom para conferir antes de terminar a parte da Meta.

Pronto: mande "oi" do seu WhatsApp para o número do CorrerIA.

## Sensores no Home Assistant

Com **Criar sensores** ligado (em **Configurações › Integrações › Sensores no Home Assistant**; vem desligado, e desligar tira os sensores), o CorrerIA cria:

- `sensor.correria_certificado`: quantos dias faltam para o certificado de `/ssl` vencer (o do Duck DNS, que renova sozinho), com `vence`, `dominio` e `arquivo`; sem certificado, fica desconhecido. Um certificado vencido derruba o WhatsApp e o conector.
- `binary_sensor.correria_whatsapp`: ligado com a conta do WhatsApp conferida na Meta (a cada 30 minutos), com `nome`, `respondendo` (o **Responder pelo WhatsApp** ligado), `erro` (o que a Meta disse, como um token vencido), `conferido_em` e `ultima_mensagem`.

Exemplo de automação:

```yaml
triggers:
  - trigger: numeric_state
    entity_id: sensor.correria_certificado
    below: 15
  - trigger: state
    entity_id: binary_sensor.correria_whatsapp
    to: "off"
    for: "01:00:00"
actions:
  - action: notify.mobile_app_celular_da_ana
    data:
      title: CorrerIA
      message: >-
        {% if is_state('binary_sensor.correria_whatsapp', 'off') %}O WhatsApp desconectou: {{ state_attr('binary_sensor.correria_whatsapp', 'erro') }}
        {% else %}O certificado vence em {{ states('sensor.correria_certificado') }} dias.{% endif %}
```

## Como responde

- Recebeu, o CorrerIA marca como lida, mostra "digitando…" e passa a pergunta para a IA do Home Assistant, com as ferramentas dos apps: ela lê o que precisa nos apps e responde. A resposta volta no jeito do WhatsApp (negrito com *asterisco*), em partes se for longa.
- **Para mudar algo** ("lança 32,50 de feira", "paguei a internet"), o CorrerIA responde o que vai fazer ("Vou fazer isto: Lançar R$ 32,50 de Feira hoje"), com os botões **Sim** e **Não** embaixo (na conversa e no WhatsApp), e só faz depois do **Sim** (escrever "sim", "pode", "ok" ou "confirmo" também vale). **Não** cancela; outra pergunta também. O pedido espera até 30 minutos.
- **A casa** (1.5.0): "liga a luz da entrada", "fecha a cortina da sala", "põe o ar em 23 graus" vão para o Assist do Home Assistant, que só mexe no que está exposto a ele (no Home Assistant, **Configurações › Assistentes de voz › Expor**). Também dá para perguntar como algo está ("a luz da sala está ligada?", "qual a temperatura da sala?"). As mudanças esperam o **sim**, como as dos apps. Funciona também no Claude e nas outras IAs pelo conector MCP. Liga e desliga em **Configurações › Integrações › Casa** (vem ligada).
- A conversa de cada pessoa vai junto com a pergunta (as últimas mensagens de até 12 horas atrás), para a IA lembrar do que se falou. Depois disso, recomeça.
- **Fotos e PDFs**: mande a foto de uma nota, um print ou a fatura em PDF (com ou sem uma pergunta na legenda). O CorrerIA passa para o app do assunto que lê aquele tipo (na aba **Integrações** aparece o que cada um lê). No GerencIA, a IA lê como no Ler com IA: o que ela achar fica para conferir nos **Avisos do Início** ("Enviado por Ana · Pelo WhatsApp · 4 lançamentos") e a resposta lista o que foi lido; nada é lançado sozinho. A fatura em PDF com senha abre com as **Senhas dos PDFs** do GerencIA; se nenhuma abrir, a resposta pede para cadastrar e mandar de novo. Com uma pergunta junto ("quanto deu essa nota?"), a resposta vem com o que foi lido. Até 20 MB.
- **Áudio**: o CorrerIA ouve pela fala para texto do Home Assistant (Configurações › Assistentes de voz; a do Home Assistant Cloud primeiro) e manda o texto para o app, como se a pessoa tivesse escrito. O WhatsApp grava em OGG: na aba **WhatsApp**, a linha "Áudios do WhatsApp viram texto pelo …" mostra qual fala para texto é usada (ou por que os áudios não viram texto). Se não aceitar, a resposta pede para escrever.
- **Foto para uma tarefa**: mande a foto com um pedido na legenda ("põe na tarefa do piso") e a IA guarda a foto na tarefa do ResolvIA, depois do seu sim. Também dá para mandar a foto e pedir logo em seguida (em até 30 minutos). Vale no WhatsApp e no clipe da Conversa. A IA não vê a foto, só a guarda onde você disser.
- Vídeo, figurinha e localização recebem "Por enquanto eu entendo texto, áudio, foto e PDF".
- Pelo WhatsApp, a IA fala só dos apps: é a regra do WhatsApp para contatos de empresas (assistente para qualquer assunto não é permitido).
- Sem nenhuma IA no Home Assistant, as perguntas vão para o GerencIA, que responde com a IA dele (só responde).
- **Responder pelo WhatsApp**, no cartão WhatsApp, pausa as respostas sem desligar nada.
- Fotos e PDFs vão para o app que lê aquele tipo (hoje, o GerencIA); áudio vira texto antes.
- **Últimas mensagens** (aba WhatsApp, no fim) mostra o que chegou, o que foi respondido, os números sem cadastro e os erros (como "Passaram mais de 24 horas": o WhatsApp só deixa responder até 24 horas depois da última mensagem da pessoa).

## Conector MCP

A aba **MCP** (em Configurações) liga os apps em outras IAs, como um conector: o padrão MCP, com login. Serve para qualquer IA que aceite um conector personalizado remoto (como Claude, ChatGPT e Gemini). A IA vê as ferramentas de todos os apps ligados e lê e muda os dados: "quanto gastei com mercado em outubro?", "lança 45,90 de mercado no cartão", "o que tem na agenda amanhã?". Antes de mudar algo, ela mostra o que vai fazer.

**A porta 443.** O Claude (e outras IAs) só conectam num endereço na porta 443, a do https, sem porta no fim (`https://casa-exemplo.duckdns.org/mcp`, nunca `…:8443/mcp`). Há dois jeitos:

- **Pelo roteador**: encaminhe a porta de fora **443** para o IP do Home Assistant, porta **8443**, e escreva o endereço público sem a porta. Algumas operadoras bloqueiam a 443 de entrada em casa; aí use o túnel.
- **Pelo túnel da Cloudflare**: sem abrir porta no roteador (veja abaixo).

1. Ligue **Ligar o conector** e escreva o **Endereço público do conector** (ex.: `https://casa-exemplo.duckdns.org`), ali mesmo na aba MCP. É separado do endereço do webhook do WhatsApp (mudar um não muda o outro): pode ser o mesmo, com o mesmo certificado, que o cartão também mostra, ou outro, como um domínio pelo túnel da Cloudflare enquanto a Meta continua chegando pelo Duck DNS na porta 8443; só o endereço do conector e o login ficam abertos, e só com essa opção ligada.
2. Copie o **Endereço do conector** (ex.: `https://casa-exemplo.duckdns.org/mcp`).
3. Na IA, nas configurações de conectores (ou apps conectados), adicione um **conector personalizado**: dê um nome (CorrerIA), cole o endereço e conecte. Em geral isso é feito no site da IA e passa a valer também no app do celular; algumas pedem um plano pago ou um modo de desenvolvedor ligado. Se ela perguntar como entrar, escolha entrar agora (OAuth); para o cliente, vale tanto a identidade publicada da IA (o endereço do documento dela, CIMD) quanto o registro automático.
4. Abre uma página do CorrerIA com um **código**. Abra o CorrerIA no Home Assistant: o pedido aparece no alto da Conversa (e no sino do Home Assistant), com o mesmo código: toque nele e em **Aprovar**. A página volta sozinha para a IA.

**Se a IA não consegue chegar** ("não consegui conferir o servidor"), o cartão ajuda a achar o que falta:

- **O certificado é de outro endereço**: no app Duck DNS, o domínio não é o do endereço público do conector. Confira e reinicie o CorrerIA.
- **As IAs só conectam na porta 443**: o endereço tem outra porta no fim. Tire a porta do endereço e, no roteador, mande a 443 para a 8443 (ou use o túnel).
- **Sem :8443 no fim do endereço**: só chega se o roteador mandar a porta 443 para a 8443.
- **Nenhuma conexão de fora desde que o app abriu**: pelo celular, com o Wi-Fi desligado, abra `https://seu-endereço/.well-known/oauth-authorization-server` (aparece um texto com "issuer" quando chega). Se continuar assim, nada de fora está chegando: confira o IP do domínio no Duck DNS (o app Duck DNS do Home Assistant atualiza sozinho), o encaminhamento no roteador e a porta em **Configurações › Aplicativos › CorrerIA › Rede**. Se o IP do roteador for diferente do IP que os sites mostram, a operadora usa CGNAT, e é preciso pedir a ela um IP público (ou usar o túnel). Se a 8443 abre de fora e a 443 não, a operadora bloqueia a 443: use o túnel.
- **Chegou de fora, mas não abriu**: chegou, mas o https não fechou (por exemplo, o aparelho recusou o certificado).

### Túnel da Cloudflare (sem abrir porta)

Para quando a operadora bloqueia a porta 443 (ou usa CGNAT): o Home Assistant sai para a internet pelo túnel e a Cloudflare recebe as IAs na 443 dela, com o certificado dela. Nenhuma porta fica aberta no roteador, e o Duck DNS deixa de ser necessário para o conector.

Precisa de um **domínio seu** com o DNS na Cloudflare (o do Duck DNS não serve) e de uma conta na Cloudflare.

1. **Na Cloudflare**: crie a conta, ponha o seu domínio (ex.: `casa-exemplo.com.br`) e, no lugar onde comprou o domínio, troque os servidores DNS pelos dois que a Cloudflare indicar. Ligue os **WebSockets** do domínio (Rede).
2. **No CorrerIA › MCP**: escreva o **Endereço público do conector** com um nome no seu domínio, sem porta (ex.: `https://correria.casa-exemplo.com.br`), e ligue **Pelo túnel da Cloudflare**. Aparece, pronto para copiar, o que vai no app Cloudflared: o seu endereço e o serviço `http://IP-do-Home-Assistant:8444` (a porta do túnel, só na rede de casa: não encaminhe essa porta no roteador).
3. **No Home Assistant**: em **Configurações › Aplicativos › Loja de aplicativos › ⋮ › Repositórios**, adicione `https://github.com/homeassistant-apps/app-cloudflared` e instale o **Cloudflared** (não inicie ainda). Na aba **Configuração**, deixe **External Home Assistant Hostname** vazio (ou ponha um nome para o próprio Home Assistant) e, em **Additional Hosts**, cole o que o CorrerIA mostrou (no modo YAML do app, fica embaixo de `additional_hosts:`). Salve e inicie. No **Registro** do Cloudflared aparece um endereço de autorização: abra num navegador e autorize o seu domínio. O app cria o túnel e o nome no DNS sozinho.
4. **Confira**: pelo celular, abra `https://correria.casa-exemplo.com.br/.well-known/oauth-authorization-server` (aparece um texto com "issuer"). No CorrerIA › MCP, o cartão mostra **Chegou uma conexão pelo túnel**.
5. **Na IA**: o conector é o **Endereço do conector** (ex.: `https://correria.casa-exemplo.com.br/mcp`), como no passo a passo acima.

O webhook do WhatsApp pode usar o mesmo endereço (a URL de retorno muda junto). Com o túnel funcionando, o encaminhamento da 8443 no roteador pode sair.

A conexão fica com a pessoa que aprovou (as mudanças são registradas no nome dela). Em **Conectados** aparecem as IAs conectadas e quando usaram; **Desconectar** tira na hora. O que elas mudam aparece em **Últimas mudanças** (recolhidas), embaixo do conector. Desligado, o endereço do conector some da internet (as conexões voltam a valer quando ligar de novo).

O que a IA lê vai para a empresa dela, como qualquer conversa com ela.

## Conversar com a IA

O CorrerIA abre na **Conversa** com os apps, do mesmo jeito que pelo WhatsApp, mas sem passar por ele (e sem a regra de só falar dos apps). Pergunte ("quanto gastei este mês?"), peça uma mudança (com o **sim**, como no WhatsApp), ou mande uma foto ou um PDF pelo clipe: **Tirar foto** (a câmera abre aqui dentro; em http, sem https, dá para tirar ou escolher a foto pelo celular), **Escolher fotos** (a galeria) ou **Escolher arquivo** (uma foto ou um PDF); embaixo de cada resposta aparece qual app foi usado. Para **falar**, toque no microfone (o botão redondo, com a caixa vazia), fale e toque no ✓: o que você disse vai como a pergunta; o **X** cancela. Até 2 minutos de cada vez. Usa a fala para texto do Home Assistant (Configurações › Assistentes de voz); sem ela, o microfone não aparece e **Opções › Apps** diz por quê. O microfone só funciona com o Home Assistant aberto por https (como o Home Assistant Cloud ou o seu endereço externo). Com a conversa vazia, aparecem 6 **perguntas prontas**, uma de cada app ligado: é só tocar. Depois, o botão ✨ ao lado da caixa abre as mesmas a qualquer momento. Em **Editar perguntas**, toque numa pergunta para mudar o texto, o ✕ tira uma pergunta e **Adicionar** põe outra; embaixo, **Mais perguntas** traz até 20 modelos dos apps ligados (um toque põe na lista); **Padrão** volta às dos apps ligados. **Perguntas prontas** e **Mais perguntas** fecham e abrem num toque no título, e o aparelho lembra. Ficam guardadas no aparelho. Quando a IA vai mudar algo, os botões **Sim** e **Não** aparecem embaixo da mensagem.

As conversas são de quem está usando a tela (o login do Home Assistant, ligado à pessoa) e ficam guardadas: fechou, abre de onde parou. No alto, **Nova conversa** começa outra (a de antes fica guardada) e **Conversas** abre a lista, como nos chats de sempre: a mais recente primeiro, com o nome tirado da primeira pergunta; toque para abrir ou na lixeira para apagar. Na conversa, arrastar o dedo para o lado passa para as outras: para a esquerda, a anterior (mais antiga); para a direita, a mais nova. Ficam as últimas 30 conversas, cada uma com as últimas 40 mensagens. Nas Opções e no Sobre, o Voltar do celular volta um passo.

No computador (a partir de 1000 px de largura), fica a barra lateral dos outros apps: **Conversa**, **Mais** e as **Conversas** (a aberta marcada, o + para uma nova). A Conversa ocupa o resto da tela. No celular, o botão **Conversas** no alto abre a lista.

Para não guardar conversas para sempre, em **Configurações › Opções › Conversas**, em **Guardar as conversas por**, escolha por quanto tempo sem uso uma conversa fica: **7**, **30** (o de início) ou **90 dias**, ou **Sempre**. Vale para as conversas daqui e para as mensagens do WhatsApp guardadas no CorrerIA (as do celular de cada pessoa continuam no WhatsApp dela).

## Rondas

Uma ronda é um roteiro pronto que passa pelos apps, **uma pergunta de cada vez**, dentro da Conversa (só na tela do CorrerIA; não no WhatsApp). Comece pelo botão das Rondas no alto da Conversa ou em **Mais › Rondas**, onde ficam todas as rondas, o aviso e as últimas rondas.

Na primeira pergunta de cada assunto, o CorrerIA mostra antes o que já há no app. Uma pergunta que só vale quando há alguma coisa (mudar ou tirar uma rotina, descartar um item) não aparece se o app não tem nada ali. Responda escrevendo ou falando; cada mudança espera o seu **Sim**. **Próxima** segue, **Voltar** repete a pergunta anterior e o **X** sai.

**Ronda da casa** (escolha o cômodo):

1. **Tarefas** (ResolvIA): *Tem algo para arrumar?* · *Alguma outra tarefa?*
2. **Rotinas** (CronologIA): *Falta alguma rotina?* · *Alguma rotina precisa mudar?* · *Alguma rotina pode sair?*
3. **Itens** (InventarIA): *Chegou algum item novo?* · *Algum item foi descartado?* · *Algum item foi transferido de cômodo?*
4. **Consumíveis** (InventarIA): *Algum está acabando?* · *Algum consumível novo?* Com **Consumíveis por cômodo** ligado no InventarIA, aparecem os usados naquele cômodo; sem isso, todos.
5. **Compras** (EconomIA): *Precisa de algo do mercado?* · *Da farmácia?* · *Do pet shop?*

Depois da última pergunta, escolha o próximo cômodo: o feito hoje fica verde e cada um mostra há quantos dias foi a última ronda.

**Ronda de compras** (antes de sair): a lista, o que está na hora de repor, os consumíveis acabando, as ofertas e em qual loja a lista sai mais em conta.

**Ronda da chegada das compras**: o que da lista foi comprado (e por quanto tempo vai durar, para a reposição e para o InventarIA), o que veio fora da lista, os consumíveis e os itens novos para cadastrar e o gasto para lançar no GerencIA.

**Ronda do mês**: os gastos e as contas a pagar (GerencIA), os compromissos e as rotinas (CronologIA), as tarefas atrasadas (ResolvIA), os itens que saíram (InventarIA) e a reposição (EconomIA).

Cada ronda só mostra as etapas que dá para fazer: o app precisa estar com a opção **CorrerIA** ligada (Mais › Configurações › Integrações, em cada app), e a etapa dos consumíveis pede **Usar consumíveis** ligado no InventarIA. Os cômodos vêm do InventarIA; sem ele, você escreve o nome do cômodo. Sem **Usar cômodos** no ResolvIA, a etapa das tarefas procura o cômodo no nome das tarefas.

**Aviso de cômodo sem ronda** (Mais › Rondas › Aviso): uma chave, com o prazo embaixo: 15, 30 (de início) ou 45 dias, ou **Outro** (de 1 a 365). Um cômodo atrasado ganha um ponto no botão das Rondas, vem marcado na escolha e aparece no sino do Home Assistant (conferido de hora em hora). No celular: escolha o **Horário** e **Quem recebe**; cada pessoa escolhida recebe um aviso por dia, nesse horário, nos celulares ligados a ela no Home Assistant (Configurações › Pessoas), só quando há cômodo atrasado. **Testar no meu celular** manda um aviso de exemplo para você. Um cômodo que nunca teve ronda só conta depois da primeira ronda da casa.

## Atalho no celular

Para abrir o CorrerIA direto da tela inicial do celular (Android), sem passar pelo menu do Home Assistant: em **Mais › Configurações › Opções › Atalho no celular**, toque em **Copiar** embaixo do **Caminho** (algo como `/app/a1b2c3d4_correria`). No app do Home Assistant, abra **Configurações › Aplicativo complementar › Gerenciar atalhos** e, em **Atalho fixado**, escolha o tipo **Painel**, cole o caminho, dê o nome e adicione à tela inicial. O ícone abre o CorrerIA na Conversa. O mesmo cartão existe em todos os apps da família.

## Sobre

Em **Mais**, por último, **Sobre**: a CorrerIA Code, os apps da família (com o link de cada um no GitHub) e o meu GitHub. É o mesmo Sobre dos outros apps.

## Custo e privacidade

- A Meta não cobra as mensagens que as pessoas mandam. As respostas do CorrerIA são grátis até 1.000 por mês por número (regra da Meta desde outubro de 2026); depois disso, alguns centavos cada.
- As perguntas e as respostas do WhatsApp passam pelos servidores da Meta. A IA é a do Home Assistant.
- O login das IAs conectadas fica em `/data/mcp.json` (os tokens só como hash), também no backup.
- A configuração e as conversas ficam em `/data` (config.json e conversas.json, só para o app) e entram no backup do Home Assistant.
