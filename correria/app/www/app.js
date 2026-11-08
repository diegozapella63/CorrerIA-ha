/* CorrerIA · a tela (JavaScript puro, sem build): o WhatsApp da Meta, o webhook, quem conversa, os apps que respondem
   e as últimas mensagens. Ações por data-a; tudo vem de /api/estado. */
(function () {
  'use strict';
  const VERSAO = '0.3.0';
  const $ = s => document.querySelector(s);
  const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
  const IC = {
    zap: '<path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z"/>',
    chat: '<path d="M21 12a8 8 0 0 1-11.7 7.1L4 20.5l1.4-4.9A8 8 0 1 1 21 12Z"/>',
    link: '<path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.7 1.7"/><path d="M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7"/>',
    users: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8"/>',
    layers: '<path d="m12 2 10 5-10 5L2 7l10-5Z"/><path d="m2 17 10 5 10-5M2 12l10 5 10-5"/>',
    inbox: '<path d="M22 12h-6l-2 3h-4l-2-3H2"/><path d="M5.5 5.1 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.5-6.9A2 2 0 0 0 16.8 4H7.2a2 2 0 0 0-1.7 1.1Z"/>',
    entra: '<path d="M17 7 7 17M17 17H7V7"/>',
    sai: '<path d="M7 17 17 7M7 7h10v10"/>',
    ban: '<circle cx="12" cy="12" r="9"/><path d="m5.6 5.6 12.8 12.8"/>',
    alert: '<path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/><path d="M12 9v4M12 17h.01"/>',
    copy: '<rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>',
    send: '<path d="m22 2-7 20-4-9-9-4 20-7Z"/><path d="M22 2 11 13"/>',
    clip: '<path d="m21.4 11.1-9.2 9.2a6 6 0 0 1-8.5-8.5l8.6-8.6a4 4 0 1 1 5.7 5.7l-8.6 8.6a2 2 0 0 1-2.8-2.8l8-8"/>',
    x: '<path d="M18 6 6 18M6 6l12 12"/>',
    trash: '<path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6"/>',
    info: '<circle cx="12" cy="12" r="9"/><path d="M12 16v-4M12 8h.01"/>',
    chev: '<path d="m9 18 6-6-6-6"/>',
    back: '<path d="m15 18-6-6 6-6"/>',
    hourglass: '<path d="M5 22h14M5 2h14"/><path d="M17 22v-4.2a2 2 0 0 0-.6-1.4L12 12l-4.4 4.4a2 2 0 0 0-.6 1.4V22"/><path d="M7 2v4.2a2 2 0 0 0 .6 1.4L12 12l4.4-4.4a2 2 0 0 0 .6-1.4V2"/>',
    'external-link': '<path d="M15 3h6v6"/><path d="M10 14 21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>',
    'calendar-days': '<rect x="3" y="4" width="18" height="17" rx="2"/><path d="M8 2v4M16 2v4M3 10h18M8 14h.01M12 14h.01M16 14h.01M8 18h.01M12 18h.01"/>',
    'list-checks': '<path d="M13 5h8M13 12h8M13 19h8"/><path d="m3 17 2 2 4-4M3 7l2 2 4-4"/>',
    wallet: '<path d="M4 7h14a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a1 1 0 0 1-1-1V7Z"/><path d="M4 7V6a2 2 0 0 1 2-2h10"/><circle cx="16" cy="13.5" r="1.3"/>',
    package: '<path d="M11 21.7a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16V8a2 2 0 0 0-1-1.7l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.7z"/><path d="M12 22V12M3.3 7 12 12l8.7-5"/>',
    receipt: '<path d="M4 2v20l2-1 2 1 2-1 2 1 2-1 2 1 2-1 2 1V2l-2 1-2-1-2 1-2-1-2 1-2-1-2 1Z"/><path d="M8 8h8M8 12h8M8 16h5"/>',
    'book-open': '<path d="M12 7v14"/><path d="M3 18a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h5a4 4 0 0 1 4 4 4 4 0 0 1 4-4h5a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1h-6a3 3 0 0 0-3 3 3 3 0 0 0-3-3z"/>',
  };
  const ic = (n, cls = 'ic') => `<svg class="${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${IC[n] || ''}</svg>`;

  const S = { e: null, salvando: false, form: {}, tela: '', ch: { msgs: null, texto: '', anexo: null, enviando: false, pessoa: '' } };
  const api = {
    get: () => fetch('api/estado', { cache: 'no-store' }).then(ok),
    post: (rota, corpo) => fetch('api/' + rota, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(corpo || {}) }).then(ok),
    conversa: () => fetch('api/conversa', { cache: 'no-store' }).then(ok),
  };
  async function ok(r) {
    let j = null;
    try { j = await r.json(); } catch (e) { /* sem corpo */ }
    if (!r.ok) throw new Error((j && j.erro) || `Erro ${r.status}`);
    return j;
  }
  function toast(t) {
    const el = $('#toast');
    el.textContent = t;
    el.classList.add('on');
    clearTimeout(toast.t);
    toast.t = setTimeout(() => el.classList.remove('on'), 2600);
  }

  /* ---------- tema: o claro/escuro do Home Assistant (como os outros apps), senão o do sistema */
  function temaHA() {
    try {
      if (window.parent && window.parent !== window) {
        const ha = window.parent.document.querySelector('home-assistant');
        const dm = ha && ha.hass && ha.hass.themes && ha.hass.themes.darkMode;
        if (typeof dm === 'boolean') return dm ? 'dark' : 'light';
      }
    } catch (e) { /* fora do Home Assistant */ }
    return window.matchMedia && matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
  }
  function aplicarTema() {
    const t = temaHA();
    if (document.documentElement.dataset.theme !== t) document.documentElement.dataset.theme = t;
  }
  aplicarTema();
  setInterval(aplicarTema, 2000);
  try { matchMedia('(prefers-color-scheme: light)').addEventListener('change', aplicarTema); } catch (e) { /* antigo */ }

  /* ---------- datas */
  function quando(isoTxt) {
    if (!isoTxt) return '';
    const d = new Date(isoTxt), h = new Date();
    const hora = d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
    if (d.toDateString() === h.toDateString()) return 'hoje às ' + hora;
    const ontem = new Date(h); ontem.setDate(h.getDate() - 1);
    if (d.toDateString() === ontem.toDateString()) return 'ontem às ' + hora;
    return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' }) + ' às ' + hora;
  }
  const horaCurta = isoTxt => {
    const d = new Date(isoTxt), h = new Date();
    return d.toDateString() === h.toDateString() ? d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }) : d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' });
  };
  const fone = n => {
    const d = String(n || '').replace(/\D/g, '');
    const m = d.match(/^55(\d{2})(\d{4,5})(\d{4})$/);
    return m ? `+55 ${m[1]} ${m[2]}-${m[3]}` : (d ? '+' + d : '');
  };

  /* ---------- a tela */
  const cab = (icone, titulo, extra = '') => `<div class="rot"><span class="rot-ic">${ic(icone)}</span><h2>${titulo}</h2>${extra}</div>`;

  function cardWhatsApp(e) {
    const c = e.config;
    let st;
    if (!e.pronto) st = '<div class="status manual">Falta configurar: o ID do número, o token e a chave secreta.</div>';
    else if (e.conta) st = `<div class="status">${esc(e.conta.numero)}${e.conta.nome ? ' · ' + esc(e.conta.nome) : ''}</div>`;
    else st = '<div class="status manual">Configurado. Toque em Conferir para testar com a Meta.</div>';
    return `<section class="card" id="whatsapp">${cab('chat', 'WhatsApp')}
      <p class="lead">A conta do WhatsApp Business, criada no painel da Meta (developers.facebook.com).</p>
      ${e.pronto ? `<div class="linha-sw"><div><b>Responder pelo WhatsApp</b><span>${c.ligado ? 'Ligado.' : 'Pausado: as mensagens chegam, mas ninguém responde.'}</span></div>
        <button class="sw${c.ligado ? ' on' : ''}" data-a="ligado" role="switch" aria-checked="${c.ligado}" aria-label="Responder pelo WhatsApp"></button></div>` : ''}
      ${st}
      <div class="campo"><label for="f-numero">ID do número de telefone</label>
        <input id="f-numero" class="inp" inputmode="numeric" autocomplete="off" data-f="numero_id" value="${esc(S.form.numero_id != null ? S.form.numero_id : c.numero_id)}" placeholder="Ex.: 109876543210"></div>
      <div class="campo"><label for="f-token">Token de acesso</label>
        <input id="f-token" class="inp" type="password" autocomplete="off" data-f="token" value="${esc(S.form.token || '')}" placeholder="${c.token ? esc(c.token) + ' · cole outro para trocar' : 'Do Usuário do sistema, que não vence'}"></div>
      <div class="campo"><label for="f-segredo">Chave secreta do aplicativo</label>
        <input id="f-segredo" class="inp" type="password" autocomplete="off" data-f="segredo" value="${esc(S.form.segredo || '')}" placeholder="${c.segredo ? esc(c.segredo) + ' · cole outra para trocar' : 'Configurações do app › Básico'}"></div>
      <div class="btns"><button class="btn out" data-a="conferir"${e.pronto ? '' : ' disabled'}>Conferir</button><button class="btn pri" data-a="salvar"${S.salvando ? ' disabled' : ''}>Salvar</button></div>
    </section>`;
  }

  function cardWebhook(e) {
    const c = e.config, w = e.webhook;
    const cert = w.https ? `<div class="status">Certificado ${esc(w.certificado)} · porta ${w.porta}</div>`
      : `<div class="status manual">Sem certificado: instale o app Duck DNS com o Let's Encrypt (a Meta só aceita https).</div>`;
    const meta = w.ultimo ? `<div class="status">Última mensagem da Meta ${quando(w.ultimo)}.</div>`
      : w.verificado_em ? `<div class="status">A Meta confirmou o endereço ${quando(w.verificado_em)}.</div>`
        : '<div class="status manual">A Meta ainda não chamou.</div>';
    return `<section class="card" id="webhook">${cab('link', 'Webhook na Meta')}
      <p class="lead">O endereço pelo qual a Meta entrega as mensagens. No roteador, a porta ${w.porta} vai para o Home Assistant.</p>
      <div class="campo"><label for="f-endereco">Endereço público</label>
        <input id="f-endereco" class="inp" inputmode="url" autocomplete="off" autocapitalize="off" spellcheck="false" data-f="endereco" value="${esc(S.form.endereco != null ? S.form.endereco : c.endereco)}" placeholder="https://casa-exemplo.duckdns.org:${w.porta}"></div>
      ${c.webhook ? `<ol class="passos"><li>Na Meta, em WhatsApp › Configuração › <b>Webhook</b>, toque em Editar.</li><li>Cole a <b>URL de retorno</b> e o <b>Token de verificação</b> abaixo e toque em Verificar e salvar.</li><li>Em Campos do webhook, assine <b>messages</b>.</li></ol>
      <div class="campo"><label for="f-url">URL de retorno</label><div class="copiar"><input id="f-url" class="inp" readonly value="${esc(c.webhook)}"><button class="btn peq out" data-a="copiar" data-v="f-url" aria-label="Copiar a URL de retorno">${ic('copy', 'ic-s')}Copiar</button></div></div>` : ''}
      <div class="campo"><label for="f-verif">Token de verificação</label><div class="copiar"><input id="f-verif" class="inp" readonly value="${esc(c.verificacao)}"><button class="btn peq out" data-a="copiar" data-v="f-verif" aria-label="Copiar o token de verificação">${ic('copy', 'ic-s')}Copiar</button></div></div>
      ${cert}${meta}
    </section>`;
  }

  function cardPessoas(e) {
    const P = e.pessoas;
    const linhas = P.map(p => `<div class="pessoa${p.numero ? ' com' : ''}"><span class="av">${esc((p.nome || '?').slice(0, 1).toUpperCase())}</span>
      <b>${esc(p.nome)}${p.fora ? '<small>Não está mais no Home Assistant</small>' : ''}</b>
      <input class="inp" type="tel" inputmode="tel" autocomplete="off" data-pessoa="${esc(p.id)}" value="${esc(fone(p.numero))}" placeholder="55 11 99999-0000" aria-label="WhatsApp de ${esc(p.nome)}"></div>`).join('');
    return `<section class="card" id="pessoas">${cab('users', 'Quem conversa')}
      <p class="lead">Só esses números recebem resposta. Os outros ficam em Últimas mensagens, sem resposta.</p>
      ${linhas || '<p class="vazio">Nenhuma pessoa no Home Assistant.</p>'}
    </section>`;
  }

  // o que cada app lê além de texto (fotos e PDF, pelo correria.json dele)
  function leAnexos(a) {
    const t = a.anexos || [], foto = t.some(x => x.startsWith('image/')), pdf = t.includes('application/pdf');
    return foto && pdf ? 'Também lê fotos e PDF.' : foto ? 'Também lê fotos.' : pdf ? 'Também lê PDF.' : '';
  }
  function cardApps(e) {
    const A = e.apps, f = e.fala || {};
    const lista = A.length ? A.map(a => `<div class="app-l"><span class="rot-ic">${ic('layers')}</span><span class="app-t"><b class="wm">${esc(a.nome.slice(0, -2))}<span>${esc(a.nome.slice(-2))}</span></b><small>${esc(a.assunto)}</small>${leAnexos(a) ? `<small class="le">${leAnexos(a)}</small>` : ''}</span></div>`).join('')
      : '<div class="status manual">Nenhum app respondendo. No GerencIA, ligue Mais › Configurações › Integrações › CorrerIA no WhatsApp.</div>';
    const audio = f.pronta ? `<div class="status">Áudio: ouve pela fala para texto ${esc(f.nome)}.</div>` : `<div class="status manual">Áudio: ${esc(f.motivo || 'sem fala para texto.')}</div>`;
    return `<section class="card" id="apps">${cab('layers', 'Apps que respondem')}
      ${lista}${A.length ? audio : ''}
      ${A.length ? `<button class="btn out larga" data-a="conversa">${ic('chat', 'ic-s')}Conversar com a IA</button>` : ''}
    </section>`;
  }

  const TIPO = { recebida: ['entra', 'Recebida'], enviada: ['sai', 'Enviada'], bloqueada: ['ban', 'Número sem cadastro'], erro: ['alert', 'Erro'] };
  function cardMensagens(e) {
    const R = e.registro;
    return `<section class="card" id="mensagens">${cab('inbox', 'Últimas mensagens', R.length ? '<button class="btn peq" data-a="limpar">Limpar</button>' : '')}
      ${R.length ? `<div class="msgs">${R.map(r => {
        const [icone, rot] = TIPO[r.tipo] || ['chat', r.tipo];
        return `<div class="msg ${esc(r.tipo)}"><span class="msg-ic" title="${rot}">${ic(icone, 'ic-s')}</span><div>
          <div class="msg-t"><b>${esc(r.quem)}${r.tipo === 'bloqueada' ? ' · sem cadastro' : ''}</b><time datetime="${esc(r.em)}">${horaCurta(r.em)}</time></div>
          <p>${esc(r.texto)}</p></div></div>`;
      }).join('')}</div>` : '<p class="vazio">Nenhuma mensagem ainda.</p>'}
    </section>`;
  }

  function casa(e) {
    const pronto = e.pronto && e.webhook.https && (e.webhook.verificado_em || e.webhook.ultimo) && e.apps.length && e.pessoas.some(p => p.numero);
    return `
      <header class="cab"><div class="cab-l"><p class="eyebrow"><span class="brand">Correr<span>IA</span></span> · WhatsApp</p>
        <h1>Contato da CorrerIA Code</h1></div>
        ${e.apps.length ? `<button class="bt-topo" data-a="conversa" aria-label="Conversar com a IA" title="Conversar com a IA">${ic('chat')}</button>` : ''}</header>
      <div class="sync${pronto ? '' : ' manual'}"><span class="dot"></span>${pronto ? (e.config.ligado ? 'Respondendo pelo WhatsApp' : 'Respostas pausadas') : 'Falta terminar a configuração'}</div>
      ${cardWhatsApp(e)}${cardWebhook(e)}${cardPessoas(e)}${cardApps(e)}${cardMensagens(e)}
      <section class="card linha-card"><button class="linha" data-a="sobre"><span class="rot-ic">${ic('info')}</span><span class="linha-t"><b>Sobre</b><small>CorrerIA Code, os apps e o GitHub.</small></span>${ic('chev', 'ic-s chev')}</button></section>`;
  }

  /* ---------- Sobre: quem faz os apps (CorrerIA Code), os apps da família e o GitHub (a mesma página dos outros apps) */
  const GITHUB = 'https://github.com/diegozapella63';
  const PRODUTOS = [
    ['CronologIA', 'cronologia-ha', 'calendar-days', 'Agenda da família, remédios, rotinas e placar.'],
    ['ResolvIA', 'resolvia-ha', 'list-checks', 'Listas de tarefas com prazos, pontos e repetição.'],
    ['GerencIA', 'gerencia-ha', 'wallet', 'Finanças da casa: caixa, cartões e investimentos.'],
    ['InventarIA', 'inventario-ha', 'package', 'Inventário da casa: cômodos, itens e valores.'],
    ['EconomIA', 'economia-ha', 'receipt', 'Lista de compras com o melhor preço perto de casa.'],
    ['MemorIA', 'memoria-ha', 'book-open', 'Cadernos de anotação que abrem na hora certa.'],
    ['CorrerIA', 'CorrerIA-ha', 'chat', 'O contato no WhatsApp: os apps respondem por lá.'],
  ];
  const marcaNome = n => `<span class="sb-wm">${n.slice(0, -2)}<span>${n.slice(-2)}</span></span>`;
  const linkFora = (href, corpo, cls) => `<a class="${cls}" href="${href}" target="_blank" rel="noopener">${corpo}</a>`;
  const topoTela = titulo => `<header class="cab-tela"><button class="voltar" data-a="voltar">${ic('back', 'ic-s')}CorrerIA</button><h1>${titulo}</h1></header>`;
  function sobre(e) {
    const aqui = r => r === 'CorrerIA-ha';
    return `${topoTela('Sobre')}
      <div class="sobre-topo"><span class="sb-raio" aria-hidden="true">${ic('zap')}</span>
        <h2 class="sb-nome">Correr<span>IA</span> Code</h2><p class="sb-oque">desenvolvimento de softwares</p><p class="sb-lema">Feito na correria, rodado pela IA.</p></div>
      <section class="card">${cab('hourglass', 'Por que CorrerIA?')}
        <p class="sb-txt">Porque eu sou um programador sem tempo: vivo na correria. Então eu uso a IA para rodar tudo isso aqui. Ela escreve, testa e publica; eu dou as ideias e reclamo dos botões tortos.</p></section>
      <section class="card">${cab('layers', 'Os apps')}
        <ul class="sb-apps" aria-label="Os apps">${PRODUTOS.map(([n, repo, i, linha]) => `<li>${linkFora(`${GITHUB}/${repo}`,
          `<span class="rot-ic" aria-hidden="true">${ic(i)}</span><span class="mb"><b>${marcaNome(n)}${aqui(repo) ? `<em class="sb-aqui">Este app · v${esc(e.versao || VERSAO)}</em>` : ''}</b><span>${linha}</span></span>${ic('external-link', 'sb-ext')}`,
          `sb-app${aqui(repo) ? ' aqui' : ''}`)}</li>`).join('')}</ul></section>
      ${linkFora(GITHUB, `${ic('external-link', 'ic-s')}Meu GitHub`, 'btn pri larga sb-github')}`;
  }

  /* ---------- Conversar com a IA: a mesma ponte do WhatsApp, pela tela (texto, foto ou PDF; vai para o app do assunto) */
  function formatar(t) {  // o jeito do WhatsApp (*negrito*, _itálico_, listas com "- ") em HTML
    const linha = l => esc(l).replace(/\*([^*\n]+)\*/g, '<b>$1</b>').replace(/(^|\s)_([^_\n]+)_(?=\s|$|[.,!?])/g, '$1<i>$2</i>');
    return String(t || '').split(/\n{2,}/).map(par => {
      const ls = par.split('\n');
      if (ls.every(l => /^\s*[-•]\s+/.test(l))) return `<ul>${ls.map(l => `<li>${linha(l.replace(/^\s*[-•]\s+/, ''))}</li>`).join('')}</ul>`;
      return `<p>${ls.map(linha).join('<br>')}</p>`;
    }).join('');
  }
  const SUGESTOES = { gerencia: ['Quanto gastei este mês?', 'O que vence esta semana?'] };
  function conversa(e) {
    const c = S.ch, M = c.msgs;
    let corpo;
    if (M === null) corpo = '<p class="vazio">Abrindo…</p>';
    else if (!M.length && !c.enviando) {
      const sug = e.apps.flatMap(a => SUGESTOES[a.app] || []).slice(0, 4);
      corpo = `<div class="ch-vazio"><p>Pergunte sobre os apps da casa${e.apps.some(a => (a.anexos || []).length) ? ' ou mande uma foto ou um PDF' : ''}.</p>
        ${sug.length ? `<div class="ch-sug">${sug.map(t => `<button class="chip" data-a="ch-sug" data-v="${esc(t)}">${esc(t)}</button>`).join('')}</div>` : ''}</div>`;
    } else {
      corpo = M.map(m => `<div class="ch-msg ${m.papel === 'ia' ? 'ia' : 'eu'}"><div class="ch-bolha">${m.anexo ? `<span class="ch-anexo">${ic('clip', 'ic-s')}${esc(m.anexo)}</span>` : ''}${m.texto ? (m.papel === 'ia' ? formatar(m.texto) : `<p>${esc(m.texto)}</p>`) : ''}</div>${m.app ? `<small class="ch-app">${esc(m.app)}</small>` : ''}</div>`).join('')
        + (c.enviando ? '<div class="ch-msg ia"><div class="ch-bolha ch-pensando" aria-label="Pensando"><span></span><span></span><span></span></div></div>' : '');
    }
    const le = e.apps.some(a => (a.anexos || []).length);
    return `${topoTela('Conversa')}
      ${M && M.length ? '<button class="bt-limpar" data-a="ch-limpar" aria-label="Apagar a conversa" title="Apagar a conversa">' + ic('trash', 'ic-s') + '</button>' : ''}
      <div class="ch-lista" id="ch-lista">${corpo}</div>
      <div class="ch-pe">
        ${c.anexo ? `<div class="ch-prev">${ic('clip', 'ic-s')}<span>${esc(c.anexo.nome)}</span><button data-a="ch-anexo-rm" aria-label="Tirar o arquivo">${ic('x', 'ic-s')}</button></div>` : ''}
        <div class="ch-barra">${le ? `<button class="ch-bt" data-a="ch-anexar" aria-label="Mandar uma foto ou um PDF" title="Mandar uma foto ou um PDF">${ic('clip')}</button>` : ''}
          <textarea id="ch-txt" class="inp" rows="1" placeholder="Escreva a sua pergunta" enterkeyhint="send">${esc(c.texto)}</textarea>
          <button class="ch-bt pri" data-a="ch-enviar" aria-label="Enviar"${c.enviando ? ' disabled' : ''}>${ic('send')}</button></div>
      </div>`;
  }

  function render() {
    const e = S.e;
    if (!e) return;
    const ativo = document.activeElement && document.activeElement.id;
    document.body.dataset.tela = S.tela || 'casa';
    $('#app').innerHTML = S.tela === 'conversa' ? conversa(e) : S.tela === 'sobre' ? sobre(e) : casa(e);
    if (ativo) { const el = document.getElementById(ativo); if (el && el.focus) el.focus(); }
    if (S.tela === 'conversa') { const l = $('#ch-lista'); if (l) window.scrollTo(0, document.body.scrollHeight); }
  }

  /* ---------- telas: a conversa e o Sobre ocupam uma entrada no histórico (o Voltar do celular volta para a casa) */
  function abrirTela(t) {
    if (S.tela === t) return;
    if (!S.tela) history.pushState({ tela: t }, '');
    else history.replaceState({ tela: t }, '');
    S.tela = t;
    if (t === 'conversa' && S.ch.msgs === null) api.conversa().then(r => { S.ch.msgs = r.mensagens || []; S.ch.pessoa = r.pessoa || ''; render(); }).catch(err => { S.ch.msgs = []; toast(err.message); render(); });
    window.scrollTo(0, 0);
    render();
    if (t === 'conversa') setTimeout(() => { const i = $('#ch-txt'); if (i && matchMedia('(hover: hover)').matches) i.focus(); }, 60);
  }
  function voltar() {
    if (S.tela && history.state && history.state.tela) history.back();
    else { S.tela = ''; render(); }
  }
  window.addEventListener('popstate', () => {
    S.tela = (history.state && history.state.tela) || '';
    render();
  });
  async function enviarConversa(texto) {
    const c = S.ch;
    texto = String(texto == null ? c.texto : texto).trim();
    if ((!texto && !c.anexo) || c.enviando) return;
    const anexo = c.anexo;
    c.msgs = (c.msgs || []).concat([{ papel: 'eu', texto, anexo: anexo ? anexo.nome : '' }]);
    c.texto = ''; c.anexo = null; c.enviando = true;
    render();
    try {
      const r = await api.post('conversa', { texto, ...(anexo ? { anexo } : {}) });
      c.msgs = r.mensagens || [];
    } catch (err) {
      c.msgs = c.msgs.slice(0, -1);
      c.texto = texto; c.anexo = anexo;
      toast(err.message);
    }
    c.enviando = false;
    render();
  }

  async function carregar() {
    try {
      S.e = await api.get();
      render();
    } catch (err) {
      if (!S.e) $('#app').innerHTML = `<p class="boot">Não consegui abrir o CorrerIA. ${esc(err.message)}</p>`;
    }
  }
  async function acao(rota, corpo, msg) {
    try {
      const r = await api.post(rota, corpo);
      if (r && r.versao) S.e = r;
      if (msg) toast(msg);
      render();
      return r;
    } catch (err) {
      toast(err.message);
      return null;
    }
  }

  /* ---------- toques */
  document.addEventListener('click', async ev => {
    const el = ev.target.closest('[data-a]');
    if (!el || el.disabled) return;
    const a = el.dataset.a;
    if (a === 'salvar') {
      const corpo = { numero_id: $('#f-numero').value, token: $('#f-token').value, segredo: $('#f-segredo').value };
      S.salvando = true; render();
      const r = await acao('config', corpo, 'Salvo');
      S.salvando = false;
      if (r) { S.form.numero_id = null; S.form.token = ''; S.form.segredo = ''; if (r.pronto) await acao('conferir', {}, null).then(x => x && x.conta && toast('Conferido com a Meta')); }
      render();
    } else if (a === 'conferir') {
      const r = await acao('conferir', {}, null);
      if (r && r.conta) toast('Conferido com a Meta');
    } else if (a === 'ligado') {
      await acao('config', { ligado: !S.e.config.ligado }, S.e.config.ligado ? 'Respostas pausadas' : 'Respondendo');
    } else if (a === 'copiar') {
      const inp = document.getElementById(el.dataset.v);
      inp.select();
      try {
        if (!navigator.clipboard) throw new Error('sem área de transferência');
        await navigator.clipboard.writeText(inp.value);
        toast('Copiado');
      } catch (e) {
        toast('Toque e segure no texto para copiar');  // em http, o navegador não deixa copiar sozinho
      }
    } else if (a === 'conversa' || a === 'sobre') {
      abrirTela(a);
    } else if (a === 'voltar') {
      voltar();
    } else if (a === 'ch-enviar') {
      enviarConversa();
    } else if (a === 'ch-sug') {
      enviarConversa(el.dataset.v);
    } else if (a === 'ch-anexar') {
      $('#ch-arquivo').click();
    } else if (a === 'ch-anexo-rm') {
      S.ch.anexo = null; render();
    } else if (a === 'ch-limpar') {
      try { S.ch.msgs = (await api.post('conversa/limpar', {})).mensagens; render(); toast('Conversa apagada'); } catch (err) { toast(err.message); }
    } else if (a === 'limpar') {
      await acao('registro/limpar', {}, 'Mensagens apagadas');
    }
  });
  document.addEventListener('input', ev => {
    const el = ev.target;
    if (el.dataset.f) S.form[el.dataset.f] = el.value;
    if (el.id === 'ch-txt') { S.ch.texto = el.value; el.style.height = 'auto'; el.style.height = Math.min(el.scrollHeight, 140) + 'px'; }
  });
  document.addEventListener('keydown', ev => {
    // no computador, Enter envia (Shift+Enter quebra a linha); no celular, o botão Enviar
    if (ev.key === 'Enter' && !ev.shiftKey && !ev.isComposing && ev.target.id === 'ch-txt' && matchMedia('(hover: hover)').matches) { ev.preventDefault(); enviarConversa(); }
  });
  document.addEventListener('change', async ev => {
    const el = ev.target;
    if (el.id === 'ch-arquivo') {  // a foto ou o PDF da conversa
      const f = el.files && el.files[0];
      el.value = '';
      if (!f) return;
      if (f.size > 15 * 1024 * 1024) return toast('O arquivo é grande demais (até 15 MB).');
      const b64 = await new Promise((ok2, erro) => { const r = new FileReader(); r.onload = () => ok2(r.result); r.onerror = erro; r.readAsDataURL(f); });
      S.ch.anexo = { nome: f.name || 'Foto', b64 };
      render();
      return;
    }
    if (el.dataset.f === 'endereco') {
      const r = await acao('config', { endereco: el.value }, 'Endereço salvo');
      if (r) S.form.endereco = null;
      render();
    } else if (el.dataset.pessoa) {
      await acao('pessoa', { id: el.dataset.pessoa, numero: el.value }, el.value.trim() ? 'Número salvo' : 'Número tirado');
    }
  });

  if (history.state && history.state.tela) history.replaceState(null, '');  // recarregou: começa na casa
  carregar();
  // as mensagens novas aparecem sozinhas (sem atrapalhar quem está digitando)
  setInterval(() => {
    if (document.hidden || S.tela) return;
    const a = document.activeElement;
    if (a && (a.tagName === 'INPUT' || a.tagName === 'TEXTAREA')) return;
    carregar();
  }, 10000);
  window.CORRERIA_TESTE = { S, render, carregar };
})();
