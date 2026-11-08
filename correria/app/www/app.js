/* CorrerIA · a tela (JavaScript puro, sem build): o WhatsApp da Meta, o webhook, quem conversa, os apps que respondem
   e as últimas mensagens. Ações por data-a; tudo vem de /api/estado. */
(function () {
  'use strict';
  const VERSAO = '0.1.0';
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
  };
  const ic = (n, cls = 'ic') => `<svg class="${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${IC[n] || ''}</svg>`;

  const S = { e: null, teste: null, testando: false, salvando: false, form: {} };
  const api = {
    get: () => fetch('api/estado', { cache: 'no-store' }).then(ok),
    post: (rota, corpo) => fetch('api/' + rota, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(corpo || {}) }).then(ok),
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

  function cardApps(e) {
    const A = e.apps;
    const lista = A.length ? A.map(a => `<div class="app-l"><span class="rot-ic">${ic('layers')}</span><span class="app-t"><b class="wm">${esc(a.nome.slice(0, -2))}<span>${esc(a.nome.slice(-2))}</span></b><small>${esc(a.assunto)}</small></span></div>`).join('')
      : '<div class="status manual">Nenhum app respondendo. No GerencIA, ligue Mais › Configurações › Integrações › CorrerIA no WhatsApp.</div>';
    const t = S.teste;
    return `<section class="card" id="apps">${cab('layers', 'Apps que respondem')}
      ${lista}
      <div class="sep"></div>
      <div class="campo"><label for="f-teste">Testar uma pergunta</label>
        <textarea id="f-teste" class="inp" rows="2" placeholder="Ex.: Quanto gastei com mercado este mês?">${esc(S.form.teste || '')}</textarea>
        <div class="ajuda">Vai para o app como se viesse do WhatsApp, sem passar pela Meta.</div></div>
      <div class="btns"><button class="btn pri" data-a="testar"${S.testando || !A.length ? ' disabled' : ''}>${ic('send', 'ic-s')}${S.testando ? 'Perguntando…' : 'Perguntar'}</button></div>
      ${t ? `<div class="bolha">${esc(t.resposta)}${t.app ? `<small>${esc(t.app)}</small>` : ''}</div>` : ''}
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

  function render() {
    const e = S.e;
    if (!e) return;
    const ativo = document.activeElement && document.activeElement.id;
    const pronto = e.pronto && e.webhook.https && (e.webhook.verificado_em || e.webhook.ultimo) && e.apps.length && e.pessoas.some(p => p.numero);
    $('#app').innerHTML = `
      <header class="cab"><p class="eyebrow"><span class="brand">Correr<span>IA</span></span> · WhatsApp</p>
        <h1>Contato da CorrerIA Code</h1>
        <div class="sync${pronto ? '' : ' manual'}"><span class="dot"></span>${pronto ? (e.config.ligado ? 'Respondendo pelo WhatsApp' : 'Respostas pausadas') : 'Falta terminar a configuração'}</div></header>
      ${cardWhatsApp(e)}${cardWebhook(e)}${cardPessoas(e)}${cardApps(e)}${cardMensagens(e)}
      <footer class="marca"><span class="raio">${ic('zap')}</span><span class="wm">Correr<span>IA</span> Code</span><small>Desenvolvimento de softwares</small><small class="v">CorrerIA v${esc(e.versao || VERSAO)}</small></footer>`;
    if (ativo) { const el = document.getElementById(ativo); if (el && el.focus) el.focus(); }
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
    } else if (a === 'testar') {
      const texto = $('#f-teste').value.trim();
      if (!texto) { $('#f-teste').focus(); return; }
      const pessoa = (S.e.pessoas.find(p => p.numero) || S.e.pessoas[0] || {}).id || '';
      S.testando = true; S.teste = null; render();
      try {
        S.teste = await api.post('testar', { texto, pessoa });
      } catch (err) {
        toast(err.message);
      }
      S.testando = false; render();
    } else if (a === 'limpar') {
      await acao('registro/limpar', {}, 'Mensagens apagadas');
    }
  });
  document.addEventListener('input', ev => {
    const el = ev.target;
    if (el.dataset.f) S.form[el.dataset.f] = el.value;
    if (el.id === 'f-teste') S.form.teste = el.value;
  });
  document.addEventListener('change', async ev => {
    const el = ev.target;
    if (el.dataset.f === 'endereco') {
      const r = await acao('config', { endereco: el.value }, 'Endereço salvo');
      if (r) S.form.endereco = null;
      render();
    } else if (el.dataset.pessoa) {
      await acao('pessoa', { id: el.dataset.pessoa, numero: el.value }, el.value.trim() ? 'Número salvo' : 'Número tirado');
    }
  });

  carregar();
  // as mensagens novas aparecem sozinhas (sem atrapalhar quem está digitando)
  setInterval(() => {
    if (document.hidden) return;
    const a = document.activeElement;
    if (a && (a.tagName === 'INPUT' || a.tagName === 'TEXTAREA')) return;
    carregar();
  }, 10000);
  window.CORRERIA_TESTE = { S, render, carregar };
})();
