# CorrerIA

O contato da CorrerIA Code no WhatsApp. As pessoas da casa mandam uma pergunta pelo WhatsApp ("quanto gastei com mercado este mês?", "o que vence esta semana?") e o app da família que cuida daquele assunto responde com a IA, com os seus dados. Hoje responde o **GerencIA** (finanças); os outros apps entram aos poucos.

Usa a **API oficial do WhatsApp Business** (da Meta): sem risco de o número ser bloqueado, como acontece com os jeitos não oficiais.

## Do que precisa

- Uma conta na Meta para desenvolvedores, com um app do tipo **Empresa** e o produto **WhatsApp**. Para começar, a Meta dá um **número de teste**, que conversa com até 5 números cadastrados. Para todo mundo conversar, depois, um número só do CorrerIA (um chip que não esteja no WhatsApp comum).
- O Home Assistant acessível pela internet com **https**, só na porta do CorrerIA: o app **Duck DNS** (com o Let's Encrypt) e a porta **8443** encaminhada no roteador. O Nabu Casa não serve, porque ele não chega nos apps.
- O **GerencIA** 1.37.0 ou mais novo, com a IA ligada.

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

1. **WhatsApp**: cole o ID do número, o token e a chave secreta e toque em **Salvar**. O app confere com a Meta e mostra o número e o nome. O token e a chave não aparecem mais (só o fim, como ••••1234); para trocar, cole outro.
2. **Webhook na Meta**: escreva o **Endereço público** (ex.: `https://casa-exemplo.duckdns.org:8443`). Na Meta, em **WhatsApp › Configuração › Webhook**, toque em Editar, cole a **URL de retorno** e o **Token de verificação** que o CorrerIA mostra e toque em **Verificar e salvar**. Depois, em Campos do webhook, assine **messages**. O cartão mostra quando a Meta confirmou o endereço e a última mensagem que chegou.
3. **Quem conversa**: escreva o WhatsApp de cada pessoa da casa (as pessoas do Home Assistant). Só esses números recebem resposta; os outros aparecem em Últimas mensagens como "sem cadastro", sem resposta.
4. No **GerencIA**, ligue **Mais › Configurações › Integrações › CorrerIA no WhatsApp**. Ele aparece em **Apps que respondem**.
5. **Testar uma pergunta** manda uma pergunta para o app como se viesse do WhatsApp, sem passar pela Meta: bom para conferir antes de terminar a parte da Meta.

Pronto: mande "oi" do seu WhatsApp para o número do CorrerIA.

## Como responde

- Recebeu, o CorrerIA marca como lida, mostra "digitando…" e pergunta ao app do assunto. A resposta volta no jeito do WhatsApp (negrito com *asterisco*), em partes se for longa.
- A conversa de cada pessoa vai junto com a pergunta (as últimas mensagens de até 12 horas atrás), para a IA lembrar do que se falou. Depois disso, recomeça.
- Por enquanto lê só texto: áudio, foto e figurinha recebem "Por enquanto eu só leio mensagens de texto".
- Pelo WhatsApp a IA só responde: lançar, pagar ou mudar um saldo continua no app. E fala só dos apps da casa: é a regra do WhatsApp para contatos de empresas (assistente para qualquer assunto não é permitido).
- **Responder pelo WhatsApp**, no cartão WhatsApp, pausa as respostas sem desligar nada.
- **Últimas mensagens** mostra o que chegou, o que foi respondido, os números sem cadastro e os erros (como "Passaram mais de 24 horas": o WhatsApp só deixa responder até 24 horas depois da última mensagem da pessoa).

## Custo e privacidade

- A Meta não cobra as mensagens que as pessoas mandam. As respostas do CorrerIA são grátis até 1.000 por mês por número (regra da Meta desde outubro de 2026); depois disso, alguns centavos cada.
- As perguntas e as respostas passam pelos servidores da Meta. A IA é a mesma dos apps (a do Home Assistant).
- A configuração e as conversas ficam em `/data` (config.json e conversas.json, só para o app) e entram no backup do Home Assistant.
