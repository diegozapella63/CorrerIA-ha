/* CorrerIA · a tela (JavaScript puro, sem build). Abre na conversa com a IA (os apps); a engrenagem leva às
   Opções, em abas: Apps (os apps, a IA e as últimas mensagens), WhatsApp (a Meta, o webhook, quem conversa) e MCP (o
   conector para outras IAs). Ações por data-a; tudo vem de /api/estado. */
(function () {
  'use strict';
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
    nova: '<path d="M12 20h9"/><path d="M16.4 3.6a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/>',
    conversas: '<path d="M14 9a2 2 0 0 1-2 2H6l-4 4V4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2Z"/><path d="M18 9h2a2 2 0 0 1 2 2v11l-4-4h-6a2 2 0 0 1-2-2v-1"/>',
    camera: '<path d="M4 8h3l2-3h6l2 3h3v11H4z"/><circle cx="12" cy="13" r="3.5"/>',
    mic: '<rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 10a7 7 0 0 0 14 0M12 17v5"/>',
    check: '<path d="M20 6 9 17l-5-5"/>',
    image: '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.1-3.1a2 2 0 0 0-2.8 0L6 21"/>',
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
    gear: '<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/>',
    plug: '<path d="M12 22v-5M9 8V2M15 8V2M18 8v5a6 6 0 0 1-12 0V8Z"/>',
    mais: '<circle cx="12" cy="12" r="1.6" fill="currentColor"/><circle cx="19" cy="12" r="1.6" fill="currentColor"/><circle cx="5" cy="12" r="1.6" fill="currentColor"/>',
    database: '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5V19A9 3 0 0 0 21 19V5"/><path d="M3 12A9 3 0 0 0 21 12"/>',
    palette: '<circle cx="13.5" cy="6.5" r=".5" fill="currentColor"/><circle cx="17.5" cy="10.5" r=".5" fill="currentColor"/><circle cx="8.5" cy="7.5" r=".5" fill="currentColor"/><circle cx="6.5" cy="12.5" r=".5" fill="currentColor"/><path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.926 0 1.648-.746 1.648-1.688 0-.437-.18-.835-.437-1.125-.29-.289-.438-.652-.438-1.125a1.64 1.64 0 0 1 1.668-1.668h1.996c3.051 0 5.555-2.503 5.555-5.554C21.965 6.012 17.461 2 12 2z"/>',
    contrast: '<circle cx="12" cy="12" r="10"/><path d="M12 18a6 6 0 0 0 0-12v12z"/>',
    sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/>',
    moon: '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>',
    phone: '<rect width="14" height="20" x="5" y="2" rx="2"/><path d="M12 18h.01"/>',
    chart: '<path d="M3 3v16a2 2 0 0 0 2 2h16"/><path d="M18 17V9"/><path d="M13 17V5"/><path d="M8 17v-3"/>',
    'book-open': '<path d="M12 7v14"/><path d="M3 18a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h5a4 4 0 0 1 4 4 4 4 0 0 1 4-4h5a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1h-6a3 3 0 0 0-3 3 3 3 0 0 0-3-3z"/>',
  };
  const ic = (n, cls = 'ic') => `<svg class="${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${IC[n] || ''}</svg>`;

  // tela: '' (a conversa, onde o app abre), 'mais' (o menu, como nos outros apps), 'opcoes' (Configurações) ou 'sobre';
  // aba: a de Configurações (fica guardada neste aparelho)
  // Opções (0.13.0): o Atalho no celular, como nos outros apps; só dentro do Home Assistant (fora dele, a aba some)
  const ABAS = [['apps', 'Apps'], ['whatsapp', 'WhatsApp'], ['mcp', 'MCP'], ['dados', 'Dados'], ['aparencia', 'Aparência'], ['opcoes', 'Opções']];
  const abasDe = (e) => ABAS.filter(([k]) => k !== 'opcoes' || (e && e.atalho));
  const guardada = k => { try { return localStorage.getItem(k); } catch (e) { return null; } };
  const guardar = (k, v) => { try { localStorage.setItem(k, v); } catch (e) { /* sem armazenamento: só nesta vez */ } };
  const S = { e: null, salvando: false, form: {}, tela: '', aba: guardada('correria-aba') || 'apps', tema: guardada('correria-tema') || 'auto',
    ch: { msgs: null, texto: '', anexo: null, enviando: false, pessoa: '', ola: '', conversa: null, lista: undefined, fala: '' } };
  const api = {
    get: () => fetch('api/estado', { cache: 'no-store' }).then(ok),
    post: (rota, corpo) => fetch('api/' + rota, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(corpo || {}) }).then(ok),
    conversa: () => fetch('api/conversa', { cache: 'no-store' }).then(ok),
    conversas: () => fetch('api/conversas', { cache: 'no-store' }).then(ok),
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
    toast.t = setTimeout(() => el.classList.remove('on'), Math.min(9000, Math.max(2600, String(t).length * 55)));  // o texto longo fica mais tempo
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
    const t = S.tema === 'claro' ? 'light' : S.tema === 'escuro' ? 'dark' : temaHA();
    if (document.documentElement.dataset.theme !== t) document.documentElement.dataset.theme = t;
  }
  // a paleta da família: as 12 cores, nesta ordem e com estes nomes, em todos os apps (a do CronologIA)
  const PALETA = [['vermelho', 'Vermelho', '#FF5A4F', '#C42A1F'], ['coral', 'Coral', '#FF8A65', '#C2410C'], ['laranja', 'Laranja', '#FFA23E', '#B45309'],
    ['ouro', 'Ouro', '#F2C14E', '#8A6100'], ['verde', 'Verde', '#8BD45F', '#3F7A17'], ['menta', 'Menta', '#4ED3A6', '#0E7A57'],
    ['turquesa', 'Turquesa', '#3CCBDA', '#0B7285'], ['azul', 'Azul', '#62B5FF', '#0B67A8'], ['indigo', 'Índigo', '#8F9BFF', '#3D4BC2'],
    ['lilas', 'Lilás', '#B99BFF', '#6D3FD6'], ['rosa', 'Rosa', '#FF77A9', '#BE185D'], ['grafite', 'Grafite', '#B5B9C2', '#4E5560']]
    .map(([id, nome, fill, ink]) => ({ id, nome, fill, ink }));
  // a Cor do dia: as 11 sem o Grafite, pelo número do dia na data local (a mesma em todos os apps no mesmo dia)
  function corDoDia(d = new Date()) {
    const L = PALETA.filter(c => c.id !== 'grafite'), n = Math.floor(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()) / 864e5);
    return L[((n % L.length) + L.length) % L.length].id;
  }
  // a cor do app é da casa toda (no config.json); o aparelho guarda uma cópia só para abrir já com ela
  function corAtual(e) {
    let ap = (e || S.e || {}).aparencia;
    if (!ap) { try { ap = JSON.parse(guardada('correria-cor') || '{}'); } catch (x) { ap = {}; } }
    return ap.cor_dia !== false ? corDoDia() : (PALETA.some(c => c.id === ap.cor) ? ap.cor : 'ouro');
  }
  function aplicarCor() {
    const c = PALETA.find(x => x.id === corAtual()), r = document.documentElement.style;
    r.setProperty('--accent', c.fill);
    r.setProperty('--accent-ink', c.ink);
    if (S.e && S.e.aparencia) guardar('correria-cor', JSON.stringify(S.e.aparencia));
  }
  aplicarTema();
  aplicarCor();
  setInterval(aplicarTema, 2000);
  setInterval(aplicarCor, 60000);  // passou da meia-noite com o app aberto: a cor do dia novo
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

  // o que cada app faz pelo CorrerIA: ler e mudar (as ferramentas) e, além de texto, fotos e PDF (pelo correria.json dele)
  function oQueFaz(a) {
    const t = a.anexos || [], foto = t.some(x => x.startsWith('image/')), pdf = t.includes('application/pdf');
    const le = foto && pdf ? 'fotos e PDF' : foto ? 'fotos' : pdf ? 'PDF' : '';
    if (a.erro) return '';
    const f = a.ferramentas ? (a.gravam ? 'Lê e muda' : 'Lê') : a.conversa ? 'Responde' : '';
    return f && le ? `${f}; também lê ${le}.` : f ? f + '.' : le ? `Lê ${le}.` : '';
  }
  function cardApps(e) {
    const A = e.apps, f = e.fala || {}, i = e.ia || {}, ft = e.fala_tela || {};
    const lista = A.length ? A.map(a => `<div class="app-l"><span class="rot-ic">${ic('layers')}</span><span class="app-t"><b class="wm">${esc(a.nome.slice(0, -2))}<span>${esc(a.nome.slice(-2))}</span></b><small>${esc(a.assunto)}</small>${a.erro ? `<small class="le erro">${esc(a.erro)}</small>` : oQueFaz(a) ? `<small class="le">${oQueFaz(a)}</small>` : ''}</span></div>`).join('')
      : '<div class="status manual">Nenhum app ligado. Em cada app, ligue Mais › Configurações › Integrações › CorrerIA.</div>';
    const audio = f.pronta ? `<div class="status">Áudio: ouve pela fala para texto ${esc(f.nome)}.</div>` : `<div class="status manual">Áudio: ${esc(f.motivo || 'sem fala para texto.')}</div>`;
    const comFerr = A.some(a => a.ferramentas);
    const ia = !comFerr ? '' : i.simulada ? '<div class="status">IA simulada (fora do Home Assistant).</div>'
      : i.ok === false ? `<div class="status erro">IA: ${esc(i.erro)}</div>` : '<div class="status">IA: a do Home Assistant (Configurações › Sistema › IA).</div>';
    const mic = ft.pronta === false ? `<div class="status manual">Falar na conversa: ${esc(ft.motivo || 'sem fala para texto.')}</div>` : '';
    return `<section class="card" id="apps">${cab('layers', 'Apps')}
      ${lista}${ia}${A.length ? audio + mic : ''}
    </section>`;
  }

  // o conector MCP (para qualquer IA que aceite um, sem nome de marca na tela): o endereço, os pedidos esperando aprovação e quem está conectado
  function cardMcp(e) {
    const m = e.mcp || {};
    const sw = `<div class="linha-sw"><div><b>Ligar o conector</b><span>${m.ligado ? 'Ligado: as IAs conectadas leem e mudam os apps, com a sua aprovação.' : 'Desligado.'}</span></div>
        <button class="sw${m.ligado ? ' on' : ''}" data-a="mcp" role="switch" aria-checked="${!!m.ligado}" aria-label="Ligar o conector"></button></div>`;
    if (!m.ligado) return `<section class="card" id="mcp">${cab('plug', 'Conector MCP')}
      <p class="lead">Os apps dentro de outras IAs, como um conector.</p>${sw}</section>`;
    const pedidos = (m.pedidos || []).map(p => `<div class="pedido"><div class="pedido-t"><b>${esc(p.nome)} quer se conectar</b><span>Código <b class="cod">${esc(p.codigo)}</b> · ${esc(p.host)}</span></div>
        <div class="btns"><button class="btn out" data-a="mcp-recusar" data-v="${esc(p.id)}">Recusar</button><button class="btn pri" data-a="mcp-aprovar" data-v="${esc(p.id)}">Aprovar</button></div></div>`).join('');
    const conexoes = (m.conexoes || []).map(c => `<div class="conexao"><span class="av">${esc((c.nome || '?').slice(0, 1).toUpperCase())}</span>
        <div class="conexao-t"><b>${esc(c.nome)}</b><span>${[c.pessoa, c.usado ? 'usou ' + quando(c.usado) : ''].filter(Boolean).map(esc).join(' · ')}</span></div>
        <button class="btn peq out" data-a="mcp-desconectar" data-v="${esc(c.id)}">Desconectar</button></div>`).join('');
    const endereco = m.url ? `<div class="campo"><label for="f-mcp">Endereço do conector</label><div class="copiar"><input id="f-mcp" class="inp" readonly value="${esc(m.url)}"><button class="btn peq out" data-a="copiar" data-v="f-mcp" aria-label="Copiar o endereço do conector">${ic('copy', 'ic-s')}Copiar</button></div></div>
      ${conexoes ? '' : `<ol class="passos"><li>Na IA, adicione um <b>conector personalizado</b> com este endereço.</li><li>Aprove aqui o pedido com o código que aparece lá.</li></ol>`}`
      : '<div class="status manual">Escreva o endereço público na aba WhatsApp.</div>';
    return `<section class="card" id="mcp">${cab('plug', 'Conector MCP')}
      <p class="lead">Os apps dentro de outras IAs, como um conector.</p>${sw}
      ${pedidos}${endereco}
      ${conexoes ? `<div class="lbl">Conectados</div>${conexoes}` : ''}
    </section>`;
  }

  const TIPO = { recebida: ['entra', 'Recebida'], enviada: ['sai', 'Enviada'], bloqueada: ['ban', 'Número sem cadastro'], erro: ['alert', 'Erro'], mcp: ['plug', 'Conector MCP'] };
  function cardMensagens(e) {
    const R = e.registro;
    return `<section class="card" id="mensagens">${cab('inbox', 'Últimas mensagens', R.length ? '<button class="btn peq" data-a="limpar">Limpar</button>' : '')}
      ${R.length ? `<div class="msgs">${R.map(r => {
        const [icone, rot] = TIPO[r.tipo] || ['chat', r.tipo];
        return `<div class="msg ${esc(r.tipo)}"><span class="msg-ic" title="${rot}">${ic(icone, 'ic-s')}</span><div>
          <div class="msg-t"><b>${esc(r.quem)}${r.tipo === 'bloqueada' ? ' · sem cadastro' : ''}</b><time datetime="${esc(r.em)}">${horaCurta(r.em)}</time></div>
          <p>${esc(r.texto)}${r.app && r.tipo === 'mcp' ? ` <small>· ${esc(r.app)}</small>` : ''}</p></div></div>`;
      }).join('')}</div>` : '<p class="vazio">Nenhuma mensagem ainda.</p>'}
    </section>`;
  }

  // um pedido de uma IA para conectar esperando: aparece no alto da conversa e das Opções (quem abriu o app só para aprovar)
  function pendentes(e) {
    const n = ((e.mcp || {}).pedidos || []).length;
    if (!n || (S.tela === 'opcoes' && S.aba === 'mcp')) return '';
    return `<button class="aviso-topo" data-a="ir-mcp">${ic('plug', 'ic-s')}<span>${n === 1 ? esc(e.mcp.pedidos[0].nome) + ' quer se conectar' : n + ' pedidos para conectar'}</span>${ic('chev', 'ic-s')}</button>`;
  }
  function opcoes(e) {
    const aba = abasDe(e).some(([k]) => k === S.aba) ? S.aba : 'apps';
    const pronto = e.pronto && e.webhook.https && (e.webhook.verificado_em || e.webhook.ultimo) && e.apps.length && e.pessoas.some(p => p.numero);
    const corpo = aba === 'whatsapp' ? cardWhatsApp(e) + cardWebhook(e) + cardPessoas(e) : aba === 'mcp' ? cardMcp(e)
      : aba === 'dados' ? cardDados() : aba === 'aparencia' ? cardTema() + cardCor(e) : aba === 'opcoes' ? cardAtalho(e) : cardApps(e) + cardUso(e) + cardSensores(e) + cardMensagens(e);
    return `${topoTela('Configurações', 'Mais')}
      <div class="sync${pronto ? '' : ' manual'}"><span class="dot"></span>${pronto ? (e.config.ligado ? 'Respondendo pelo WhatsApp' : 'Respostas pausadas') : 'Falta terminar a configuração do WhatsApp'}</div>
      ${pendentes(e)}
      <nav class="abas" role="tablist" aria-label="Configurações">${abasDe(e).map(([k, n]) => `<button role="tab" aria-selected="${k === aba}" class="${k === aba ? 'on' : ''}" data-a="aba" data-v="${k}">${n}</button>`).join('')}</nav>
      ${corpo}`;
  }
  // Mais, um menu como nos outros apps: Configurações e, por último, Sobre (cada um na sua tela)
  function telaMais() {
    const linha = (a, icone, titulo, txt) => `<button class="linha" data-a="${a}"><span class="rot-ic">${ic(icone)}</span><span class="linha-t"><b>${titulo}</b><small>${txt}</small></span>${ic('chev', 'ic-s chev')}</button>`;
    return `${topoTela('Mais', 'Conversa')}
      <section class="card linha-card mais-menu">${linha('opcoes', 'gear', 'Configurações', 'Apps, WhatsApp, MCP, dados e aparência.')}
        ${linha('sobre', 'info', 'Sobre', 'CorrerIA Code, os apps e o GitHub.')}</section>`;
  }

  /* ---------- Configurações › Dados e Aparência (como nos outros apps) */
  function cardDados() {
    return `<section class="card" id="onde">${cab('database', 'Onde ficam os dados')}
      <p class="lead">Na pasta <code>/data</code> do app, que entra no backup do Home Assistant: <code>config.json</code> (o WhatsApp, o endereço e o número de cada pessoa), <code>conversas.json</code> (as conversas e as últimas mensagens), <code>mcp.json</code> (as IAs conectadas, com os tokens só em código) e <code>uso_ia.json</code> (o Uso da IA). O token e a chave secreta nunca voltam para a tela.</p></section>`;
  }
  const TEMAS = [['auto', 'Sistema', 'phone'], ['claro', 'Claro', 'sun'], ['escuro', 'Escuro', 'moon']];
  function cardTema() {
    return `<section class="card" id="tema">${cab('contrast', 'Tema')}<p class="lead">Vale só para este aparelho. Sistema segue o do Home Assistant.</p>
      <div class="temas" role="radiogroup" aria-label="Tema">${TEMAS.map(([k, n, i]) => `<button role="radio" aria-checked="${S.tema === k}" class="${S.tema === k ? 'on' : ''}" data-a="tema" data-v="${k}">${ic(i)}<span>${n}</span></button>`).join('')}</div></section>`;
  }
  const TAG = 'M8 0h20a2 2 0 0 1 2 2v16a2 2 0 0 1-2 2H8L0 13V7z', FURO = 'M9.7 10a2.7 2.7 0 1 0-5.4 0a2.7 2.7 0 1 0 5.4 0z';
  function cardCor(e) {
    const ap = e.aparencia || {}, dia = ap.cor_dia !== false, atual = corAtual(e);
    return `<section class="card" id="cor">${cab('palette', 'Cor do app')}<p class="lead">Em todos os aparelhos da casa.</p>
      <div class="linha-sw"><div><b>Cor do dia</b><span>Muda a cor do app todo dia, a mesma em todos os apps.</span></div>
        <button class="sw${dia ? ' on' : ''}" data-a="cor-dia" role="switch" aria-checked="${dia}" aria-label="Cor do dia"></button></div>
      <div class="cores" role="radiogroup" aria-label="Cor do app">${PALETA.map(c => `<button class="tsw${c.id === atual ? ' on' : ''}" role="radio" aria-checked="${c.id === atual}" style="--a:${c.fill}" data-a="cor" data-v="${c.id}">
        <svg viewBox="-5 -5 40 30" aria-hidden="true"><path class="sw-ring" d="${TAG}"/><path class="sw-gap" d="${TAG}"/><path class="sw-fill" d="${TAG + FURO}"/><path class="sw-check" d="m14.6 10.3 3.2 3.2 6.5-6.9"/></svg><span>${c.nome}</span></button>`).join('')}</div></section>`;
  }

  // Atalho no celular (igual em todos os apps da família): o caminho do app no Home Assistant, para um ícone na tela inicial
  // que abre o app direto (Atalho fixado do app do Home Assistant no Android). Fora do Home Assistant, não aparece.
  function cardAtalho(e) {
    if (!e.atalho) return '';
    return `<section class="card" id="atalho">${cab('phone', 'Atalho no celular')}<p class="lead">Um ícone na tela inicial do celular que abre o CorrerIA direto.</p>
      <ol class="passos"><li>No app do Home Assistant: <b>Configurações › Aplicativo complementar › Gerenciar atalhos</b>.</li><li>Em <b>Atalho fixado</b>, escolha o tipo <b>Painel</b> e cole o <b>Caminho</b> abaixo.</li></ol>
      <div class="campo"><label for="f-atalho">Caminho</label><div class="copiar pilha"><input id="f-atalho" class="inp" readonly value="${esc(e.atalho)}"><button class="btn peq out" data-a="copiar" data-v="f-atalho" aria-label="Copiar o caminho">${ic('copy', 'ic-s')}Copiar</button></div></div></section>`;
  }

  /* ---------- Configurações › Apps › Uso da IA: as chamadas da IA do WhatsApp e da conversa da tela (tokens estimados) */
  const TIPO_USO = { whatsapp: 'WhatsApp', conversa: 'Conversa' };
  const SEM = ['dom', 'seg', 'ter', 'qua', 'qui', 'sex', 'sáb'];
  function cardUso(e) {
    const u = e.uso_ia;
    if (!u || !u.hoje) return '';
    const mil = n => n >= 1000 ? `${String(Math.round(n / 100) / 10).replace('.', ',')} mil` : String(Math.round(n || 0));
    const tile = (k, t) => `<div class="uso-t"><span class="k">${k}</span><b>${t.chamadas || 0}</b><span class="s${t.erros || t.cota ? ' alerta' : ''}">${t.cota ? `${t.cota} sem cota` : t.erros ? `${t.erros} com erro` : `≈ ${mil(t.tokens)} tokens`}</span></div>`;
    const max = Math.max(1, ...u.dias.map(d => d.chamadas || 0));
    const hoje = u.dias.length ? u.dias[u.dias.length - 1].dia : '';
    const nomeDia = d => d === hoje ? 'hoje' : SEM[new Date(d + 'T12:00:00').getDay()];
    const tipos = u.semana.tipos || {};
    const ult = (u.ultimas || []).slice(0, 6);
    return `<section class="card" id="uso">${cab('chart', 'Uso da IA')}<p class="lead">As chamadas do CorrerIA para a IA do Home Assistant. Os tokens são estimados.</p>
      <div class="uso-ts">${tile('Hoje', u.hoje)}${tile('7 dias', u.semana)}${tile('Este mês', u.mes)}</div>
      <div class="uso-barras" aria-label="Chamadas nos últimos 7 dias">${u.dias.map(d => `<div class="uso-b${d.dia === hoje ? ' hoje' : ''}" title="${nomeDia(d.dia)}: ${d.chamadas}"><i style="height:${d.chamadas ? Math.max(4, Math.round(d.chamadas / max * 100)) : 0}%"></i><span>${nomeDia(d.dia)}</span></div>`).join('')}</div>
      ${Object.keys(tipos).length ? `<p class="uso-tipos">${Object.keys(tipos).map(k => `${TIPO_USO[k] || esc(k)} <b>${tipos[k]}</b>`).join(' · ')}</p>` : ''}
      ${ult.length ? `<div class="lbl">Últimas chamadas</div><ul class="uso-ult">${ult.map(c => `<li><b>${TIPO_USO[c.tipo] || esc(c.tipo)}</b>${c.resultado !== 'ok' ? `<span class="erro">${c.resultado === 'cota' ? 'sem cota' : c.resultado === 'formato' ? 'fora do formato' : 'erro'}</span>` : ''}<span>${String(c.segundos).replace('.', ',')} s · ≈ ${mil(c.tokens)} tokens · ${esc(horaCurta(c.quando))}</span></li>`).join('')}</ul>` : '<p class="vazio">Nenhuma chamada ainda.</p>'}
    </section>`;
  }

  /* ---------- Configurações › Apps › Sensores no Home Assistant (depois do Uso da IA, como nos outros apps) */
  function cardSensores(e) {
    const on = !!(e.sensores && e.sensores.ligado);
    return `<section class="card" id="sensores">${cab('chart', 'Sensores no Home Assistant')}<p class="lead">Para painéis e automações.</p>
      <div class="linha-sw"><div><b>Criar os sensores</b><span>${on ? 'Ligado: <code>sensor.correria_certificado</code> (os dias até o certificado vencer) e <code>binary_sensor.correria_whatsapp</code> (o WhatsApp conectado).' : 'Desligado: nenhum sensor no Home Assistant.'}</span></div>
        <button class="sw${on ? ' on' : ''}" data-a="sensores" role="switch" aria-checked="${on}" aria-label="Criar os sensores"></button></div></section>`;
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
    ['CorrerIA', 'CorrerIA-ha', 'chat', 'Pergunte e peça a qualquer app, no chat ou no WhatsApp.'],
  ];
  const marcaNome = n => `<span class="sb-wm">${n.slice(0, -2)}<span>${n.slice(-2)}</span></span>`;
  const linkFora = (href, corpo, cls) => `<a class="${cls}" href="${href}" target="_blank" rel="noopener">${corpo}</a>`;
  const topoTela = (titulo, volta) => `<header class="cab-tela"><button class="voltar" data-a="voltar">${ic('back', 'ic-s')}${volta}</button><h1>${titulo}</h1></header>`;
  function sobre(e) {
    const aqui = r => r === 'CorrerIA-ha';
    return `${topoTela('Sobre', 'Mais')}
      <div class="sobre-topo"><span class="sb-raio" aria-hidden="true">${ic('zap')}</span>
        <h2 class="sb-nome">Correr<span>IA</span> Code</h2><p class="sb-oque">desenvolvimento de softwares</p><p class="sb-lema">Feito na correria, rodado pela IA.</p></div>
      <section class="card">${cab('hourglass', 'Por que CorrerIA?')}
        <p class="sb-txt">Porque eu sou um programador sem tempo: vivo na correria. Então eu uso a IA para rodar tudo isso aqui. Ela escreve, testa e publica; eu dou as ideias e reclamo dos botões tortos.</p></section>
      <section class="card">${cab('layers', 'Os apps')}
        <ul class="sb-apps" aria-label="Os apps">${PRODUTOS.map(([n, repo, i, linha]) => `<li>${linkFora(`${GITHUB}/${repo}`,
          `<span class="rot-ic" aria-hidden="true">${ic(i)}</span><span class="mb"><b>${marcaNome(n)}${aqui(repo) ? `<em class="sb-aqui">Este app · v${esc(e.versao || '')}</em>` : ''}</b><span>${linha}</span></span>${ic('external-link', 'sb-ext')}`,
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
  const SUGESTOES = { gerencia: ['Quanto gastei este mês?', 'O que vence esta semana?'], cronologia: ['O que tem na agenda amanhã?'],
    resolvia: ['Quais tarefas vencem hoje?'], inventario: ['Quanto valem os itens da sala?'], memoria: ['O que eu anotei esta semana?'] };
  function conversa(e) {
    const c = S.ch, M = c.msgs;
    let corpo;
    if (M === null) corpo = '<p class="vazio">Abrindo…</p>';
    else if (!M.length && !c.enviando) {
      if (!e.apps.length) corpo = `<div class="ch-vazio"><p>Nenhum app ligado. Em cada app, ligue Mais › Configurações › Integrações › CorrerIA.</p><button class="btn out" data-a="opcoes">${ic('gear', 'ic-s')}Configurações</button></div>`;
      else {
        const sug = e.apps.flatMap(a => SUGESTOES[a.app] || []).slice(0, 4);
        corpo = `<div class="ch-vazio"><p>Pergunte ou peça algo aos apps${e.apps.some(a => (a.anexos || []).length) ? ', ou mande uma foto ou um PDF' : ''}.</p>
          ${sug.length ? `<div class="ch-sug">${sug.map(t => `<button class="chip" data-a="ch-sug" data-v="${esc(t)}">${esc(t)}</button>`).join('')}</div>` : ''}</div>`;
      }
    } else {
      corpo = M.map(m => `<div class="ch-msg ${m.papel === 'ia' ? 'ia' : 'eu'}"><div class="ch-bolha">${m.anexo ? `<span class="ch-anexo">${ic('clip', 'ic-s')}${esc(m.anexo)}</span>` : ''}${m.texto ? (m.papel === 'ia' ? formatar(m.texto) : `<p>${esc(m.texto)}</p>`) : ''}</div>${m.app ? `<small class="ch-app">${esc(m.app)}</small>` : ''}</div>`).join('')
        + (c.enviando ? '<div class="ch-msg ia"><div class="ch-bolha ch-pensando" aria-label="Pensando"><span></span><span></span><span></span></div></div>' : '');
    }
    const le = e.apps.some(a => (a.anexos || []).length), f = c.fala, ouvindo = f === 'ouvindo' || f === 'abrindo';
    const lugar = f === 'ouvindo' ? 'Ouvindo…' : f === 'abrindo' ? 'Abrindo o microfone…' : f === 'entendendo' ? 'Entendendo…' : 'Escreva a sua pergunta';
    const esquerda = ouvindo ? `<button class="ch-bt" data-a="ch-falar-x" aria-label="Cancelar" title="Cancelar">${ic('x')}</button>`
      : le ? `<button class="ch-bt" data-a="ch-camera" aria-label="Tirar foto" title="Tirar foto"${f ? ' disabled' : ''}>${ic('camera')}</button><button class="ch-bt" data-a="ch-anexar" aria-label="Mandar uma foto ou um PDF" title="Mandar uma foto ou um PDF"${f ? ' disabled' : ''}>${ic('clip')}</button>` : '';
    return `<header class="cab"><div class="cab-l"><p class="eyebrow"><span class="brand">Correr<span>IA</span></span>${c.ola ? ` · Olá, ${esc(c.ola)}` : ''}</p><h1>Conversa</h1></div>
        <div class="cab-bts"><button class="bt-icone" data-a="conversas" aria-label="Conversas" title="Conversas">${ic('conversas')}</button>
          ${M && M.length ? `<button class="bt-icone" data-a="ch-nova" aria-label="Nova conversa" title="Nova conversa">${ic('nova')}</button>` : ''}
          <button class="bt-icone" data-a="mais" aria-label="Mais" title="Mais">${ic('mais')}</button></div></header>
      ${pendentes(e)}
      <div class="ch-lista" id="ch-lista">${corpo}</div>
      <div class="ch-pe">
        ${c.anexo ? `<div class="ch-prev">${/^data:image\//.test(c.anexo.b64 || '') ? `<img src="${c.anexo.b64}" alt="">` : ic('clip', 'ic-s')}<span>${esc(c.anexo.nome)}</span><button data-a="ch-anexo-rm" aria-label="Tirar o arquivo">${ic('x', 'ic-s')}</button></div>` : ''}
        <div class="ch-barra${ouvindo ? ' ouvindo' : ''}">${esquerda}
          <textarea id="ch-txt" class="inp" rows="1" data-size="off" placeholder="${lugar}" enterkeyhint="send"${f ? ' disabled' : ''}>${esc(c.texto)}</textarea>
          ${botaoPri(e)}</div>
      </div>`;
  }
  // o botão redondo da conversa: com a caixa vazia, o microfone (Falar); ouvindo, o Pronto; com texto ou arquivo, o Enviar
  function botaoPri(e) {
    const c = S.ch, f = c.fala;
    if (f === 'ouvindo' || f === 'abrindo')
      return `<button id="ch-pri" class="ch-bt pri gravando" data-a="ch-falar" aria-label="Pronto: enviar o que falei" title="Pronto: enviar o que falei"${f === 'abrindo' ? ' disabled' : ''}>${ic('check')}</button>`;
    if (!f && (e.fala_tela || {}).pronta && !c.texto.trim() && !c.anexo)
      return `<button id="ch-pri" class="ch-bt pri" data-a="ch-falar" aria-label="Falar" title="Falar"${c.enviando ? ' disabled' : ''}>${ic('mic')}</button>`;
    return `<button id="ch-pri" class="ch-bt pri" data-a="ch-enviar" aria-label="Enviar"${c.enviando || f ? ' disabled' : ''}>${ic('send')}</button>`;
  }

  /* ---------- Falar na conversa: o microfone em PCM de 16 kHz, 16 bits, mono (o que a fala para texto do Home Assistant
     recebe, como o Assist; o mesmo do Falar dos outros apps), com o nível para o botão. Pronto: vira texto no servidor
     (/api/fala) e vai como a pergunta. Até 2 minutos; sair da conversa ou do app cancela. */
  const TAXA = 16000, MAX_FALA = 120;
  function Gravador(nivel) {
    let pedacos = [], total = 0, taxa = TAXA, fluxo = null, ctx = null, fonte = null, no = null;
    const fechar = () => {
      try { if (no) no.onaudioprocess = null; if (fonte) fonte.disconnect(); if (no) no.disconnect(); } catch (e) { /* já fechado */ }
      if (fluxo) fluxo.getTracks().forEach(t => t.stop());
      if (ctx && ctx.state !== 'closed') ctx.close().catch(() => {});
      fluxo = ctx = fonte = no = null;
    };
    this.iniciar = async () => {
      const md = navigator.mediaDevices;
      if (!md || !md.getUserMedia) throw Object.assign(new Error('sem_api'), { name: 'NoApi' });
      fluxo = await md.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
      const AC = window.AudioContext || window.webkitAudioContext;
      try { ctx = new AC({ sampleRate: TAXA }); } catch (e) { ctx = new AC(); }  // alguns só gravam na taxa deles: convertida no fim
      if (ctx.state === 'suspended') await ctx.resume().catch(() => {});
      taxa = ctx.sampleRate;
      fonte = ctx.createMediaStreamSource(fluxo);
      no = ctx.createScriptProcessor(4096, 1, 1);
      no.onaudioprocess = ev => {
        const d = ev.inputBuffer.getChannelData(0);
        pedacos.push(new Float32Array(d)); total += d.length;
        let soma = 0;
        for (let i = 0; i < d.length; i += 4) soma += d[i] * d[i];
        if (nivel) nivel(Math.min(1, Math.sqrt(soma / (d.length / 4)) * 5));
      };
      fonte.connect(no); no.connect(ctx.destination);  // a saída fica muda; só mantém o nó andando
    };
    this.parar = () => {  // o áudio em Int16 a 16 kHz
      fechar();
      const tudo = new Float32Array(total);
      let o = 0;
      for (const p of pedacos) { tudo.set(p, o); o += p.length; }
      pedacos = [];
      const r = taxa / TAXA, n = Math.floor(tudo.length / r), out = new Int16Array(n);
      for (let i = 0; i < n; i++) {  // a média de cada janela: um filtro simples quando gravou a 44,1/48 kHz
        const a = Math.floor(i * r), b = Math.max(a + 1, Math.min(tudo.length, Math.floor((i + 1) * r)));
        let s2 = 0;
        for (let j = a; j < b; j++) s2 += tudo[j];
        const v = Math.max(-1, Math.min(1, s2 / (b - a)));
        out[i] = v < 0 ? v * 0x8000 : v * 0x7fff;
      }
      return out;
    };
    this.cancelar = () => { fechar(); pedacos = []; total = 0; };
  }
  function erroMicrofone(err) {
    const n = (err && err.name) || '';
    if (n === 'NotAllowedError' || n === 'SecurityError') return 'O microfone está bloqueado. Permita o microfone para o Home Assistant (no navegador, no cadeado ao lado do endereço; no app do celular, nas permissões do app Home Assistant) e tente de novo.';
    if (n === 'NotFoundError' || n === 'OverconstrainedError') return 'Não achei um microfone neste aparelho.';
    if (n === 'NotReadableError') return 'O microfone está sendo usado por outro app. Feche o outro e tente de novo.';
    if (n === 'NoApi') return window.isSecureContext === false
      ? 'O microfone só funciona com o Home Assistant aberto por um endereço seguro (https). Neste endereço (http), o celular e o navegador não deixam usar o microfone.'
      : 'Este navegador não deixa usar o microfone aqui.';
    return `Não consegui abrir o microfone (${(err && err.message) || n || 'erro'}).`;
  }
  let GRAV = null;
  async function falar() {
    const c = S.ch;
    if (c.fala === 'ouvindo') {  // Pronto: o que falou vira texto e vai
      const g = GRAV;
      GRAV = null; clearTimeout(falar.t);
      if (!g) { c.fala = ''; return render(); }
      const pcm = g.parar();
      if (pcm.length < TAXA * 0.4) { c.fala = ''; render(); return toast('Não ouvi nada. Toque no microfone e fale.'); }
      c.fala = 'entendendo'; render();
      try {
        const r = await fetch('api/fala', { method: 'POST', headers: { 'Content-Type': 'application/octet-stream' }, body: pcm.buffer }).then(ok);
        if (c.fala !== 'entendendo') return;  // saiu da conversa enquanto entendia
        c.fala = '';
        if (r && r.texto) return enviarConversa(r.texto);
        render();
      } catch (err) {
        if (c.fala === 'entendendo') { c.fala = ''; render(); }
        toast(err.message);
      }
      return;
    }
    if (c.fala || c.enviando) return;
    const g = new Gravador(nv => { const b = $('#ch-pri'); if (b) b.style.setProperty('--nivel', nv.toFixed(2)); });
    GRAV = g; c.fala = 'abrindo'; render();
    try {
      await g.iniciar();
    } catch (err) {
      g.cancelar();
      if (GRAV === g) { GRAV = null; c.fala = ''; render(); toast(erroMicrofone(err)); }
      return;
    }
    if (GRAV !== g) return g.cancelar();
    c.fala = 'ouvindo'; render();
    falar.t = setTimeout(() => S.ch.fala === 'ouvindo' && falar(), MAX_FALA * 1000);
  }
  function pararFala() {  // Cancelar, sair da conversa ou do app: o que estava ouvindo some
    clearTimeout(falar.t);
    if (GRAV) GRAV.cancelar();
    GRAV = null;
    if (S.ch.fala) S.ch.fala = '';
  }
  document.addEventListener('visibilitychange', () => { if (document.hidden && S.ch.fala) { pararFala(); render(); } });

  /* ---------- Conversas: a lista das conversas com a IA, como nos chats de sempre (a mais recente primeiro) */
  function quando(iso) {
    const d = new Date(iso);
    if (isNaN(d)) return '';
    const hoje = new Date(), ontem = new Date(Date.now() - 864e5), hm = d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
    const dia = x => x.toDateString();
    return dia(d) === dia(hoje) ? `hoje às ${hm}` : dia(d) === dia(ontem) ? `ontem às ${hm}` : d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' }) + ` às ${hm}`;
  }
  function telaConversas() {
    const L = S.ch.lista;
    const lista = L === undefined ? '<p class="vazio">Carregando…</p>' : !L.length ? '<p class="vazio">Nenhuma conversa ainda.</p>'
      : `<ul class="conv-lista">${L.map(x => `<li class="conv${x.aberta ? ' aberta' : ''}"><button class="conv-abrir" data-a="conv-abrir" data-v="${esc(x.id)}">
          <b>${esc(x.titulo)}</b><span>${esc(quando(x.atualizada))} · ${x.mensagens} ${x.mensagens === 1 ? 'mensagem' : 'mensagens'}${x.aberta ? ' · aberta' : ''}</span></button>
          <button class="bt-icone peq" data-a="conv-apagar" data-v="${esc(x.id)}" aria-label="Apagar ${esc(x.titulo)}" title="Apagar">${ic('trash', 'ic-s')}</button></li>`).join('')}</ul>`;
    return `${topoTela('Conversas', 'Conversa')}<div class="conv-pag">
      <button class="btn pri larga" data-a="ch-nova">${ic('nova', 'ic-s')}Nova conversa</button>${lista}</div>`;
  }
  function carregarLista() {
    return api.conversas().then(r => { S.ch.lista = r.conversas || []; if (S.tela === 'conversas') render(); })
      .catch(err => { S.ch.lista = S.ch.lista || []; toast(err.message); if (S.tela === 'conversas') render(); });
  }

  /* ---------- Tirar foto: a câmera aqui dentro, como nos outros apps (em http não abre: dá para escolher a foto) */
  let CAM = null;
  const camOk = () => !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
  async function abrirCamera() {
    fecharCamera(true);
    CAM = { status: 'abrindo' };
    history.pushState({ tela: S.tela || '', cam: true }, '');
    pintarCamera();
    if (!camOk()) {
      CAM.status = 'erro';
      CAM.erro = window.isSecureContext === false
        ? 'A câmera só abre aqui com o Home Assistant num endereço seguro (https), como o do Nabu Casa. Dá para tirar a foto pelo celular e escolher.'
        : 'Este navegador não deixa usar a câmera aqui. Dá para tirar a foto pelo celular e escolher.';
      return pintarCamera();
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: false, video: { facingMode: { ideal: 'environment' }, width: { ideal: 1920 }, height: { ideal: 1440 } } });
      if (!CAM) { stream.getTracks().forEach(t => t.stop()); return; }
      Object.assign(CAM, { stream, status: 'ao-vivo' });
      pintarCamera();
      const v = $('#camera video');
      if (v) { v.srcObject = stream; v.play().catch(() => {}); }
    } catch (err) {
      if (!CAM) return;
      const negado = err && (err.name === 'NotAllowedError' || err.name === 'SecurityError');
      CAM.status = 'erro';
      CAM.erro = negado ? 'Sem permissão para usar a câmera. Libere a câmera para o app do Home Assistant nas configurações do celular, ou escolha uma foto.'
        : 'Não deu para abrir a câmera. Dá para escolher uma foto.';
      pintarCamera();
    }
  }
  function pintarCamera() {
    let el = $('#camera');
    if (!CAM) { if (el) el.remove(); return; }
    if (!el) {
      el = document.createElement('div');
      el.id = 'camera'; el.className = 'cam'; el.setAttribute('role', 'dialog'); el.setAttribute('aria-label', 'Tirar foto');
      el.innerHTML = '<video playsinline muted autoplay></video><div class="cam-ui"></div>';
      document.body.appendChild(el);
    }
    $('.cam-ui', el).innerHTML = `<div class="cam-top"><button class="cam-btn" data-a="cam-fechar" aria-label="Fechar">${ic('x')}</button><span class="cam-titulo">Tirar foto</span><span class="cam-btn vazio"></span></div>
      ${CAM.status === 'erro' ? `<div class="cam-msg">${ic('camera')}<p>${esc(CAM.erro)}</p><button class="btn pri" data-a="cam-galeria">${ic('image', 'ic-s')}Tirar ou escolher foto</button></div>`
        : `<div class="cam-meio"></div><p class="cam-dica">${CAM.status === 'abrindo' ? 'Abrindo a câmera…' : 'Enquadre e toque no botão'}</p>
      <div class="cam-baixo"><button class="cam-disparo" data-a="cam-foto" aria-label="Fotografar"${CAM.status !== 'ao-vivo' ? ' disabled' : ''}><span></span></button></div>`}`;
  }
  function fecharCamera(semHistorico) {
    if (!CAM) return;
    if (CAM.stream) CAM.stream.getTracks().forEach(t => t.stop());
    CAM = null;
    pintarCamera();
    if (!semHistorico && history.state && history.state.cam) history.back();
  }
  function camFoto() {
    const v = $('#camera video');
    if (!CAM || !v || !v.videoWidth) return;
    const k = Math.min(1, 1600 / Math.max(v.videoWidth, v.videoHeight));
    const cv = document.createElement('canvas');
    cv.width = Math.round(v.videoWidth * k); cv.height = Math.round(v.videoHeight * k);
    cv.getContext('2d').drawImage(v, 0, 0, cv.width, cv.height);
    try { if (navigator.vibrate) navigator.vibrate(15); } catch (e) { /* ok */ }
    const agora = new Date();
    S.ch.anexo = { nome: `Foto ${agora.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}`, b64: cv.toDataURL('image/jpeg', 0.86) };
    fecharCamera();
    render();
    setTimeout(() => { const t = $('#ch-txt'); if (t) t.focus(); }, 60);
  }

  function render() {
    const e = S.e;
    if (!e) return;
    const ativo = document.activeElement && document.activeElement.id;
    document.body.dataset.tela = S.tela || 'conversa';
    aplicarCor();
    $('#app').innerHTML = S.tela === 'opcoes' ? opcoes(e) : S.tela === 'sobre' ? sobre(e) : S.tela === 'mais' ? telaMais() : S.tela === 'conversas' ? telaConversas() : conversa(e);
    if (ativo) { const el = document.getElementById(ativo); if (el && el.focus) el.focus(); }
    if (!S.tela) window.scrollTo(0, document.body.scrollHeight);
    // as abas não cabem num celular estreito e rolam para o lado: a escolhida fica à vista (a tela é redesenhada)
    const aba = document.querySelector('.abas .on');
    if (aba && aba.parentElement) {
      const nav = aba.parentElement, x = aba.offsetLeft - nav.offsetLeft;
      if (x < nav.scrollLeft || x + aba.offsetWidth > nav.scrollLeft + nav.clientWidth) nav.scrollLeft = Math.max(0, x - (nav.clientWidth - aba.offsetWidth) / 2);
    }
  }

  /* ---------- telas: as Opções e o Sobre ocupam uma entrada no histórico cada (o Voltar do celular volta um passo) */
  function abrirTela(t) {
    if (S.tela === t) return;
    pararFala();
    history.pushState({ tela: t }, '');
    S.tela = t;
    window.scrollTo(0, 0);
    render();
  }
  function voltar() {
    if (S.tela && history.state && history.state.tela) history.back();
    else { S.tela = ''; render(); }
  }
  window.addEventListener('popstate', () => {
    if (CAM && !(history.state && history.state.cam)) { fecharCamera(true); return; }  // o Voltar do celular fecha a câmera
    S.tela = (history.state && history.state.tela) || '';
    window.scrollTo(0, 0);
    render();
  });
  function carregarConversa() {
    return api.conversa().then(r => { S.ch.msgs = r.mensagens || []; S.ch.pessoa = r.pessoa || ''; S.ch.ola = r.ola || ''; S.ch.conversa = r.conversa || null; render(); })
      .catch(err => { S.ch.msgs = []; toast(err.message); render(); });
  }
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
      c.conversa = r.conversa || null;
      c.lista = undefined;  // a lista muda (a conversa nova entra, a de agora sobe)
    } catch (err) {
      c.msgs = c.msgs.slice(0, -1);
      c.texto = texto; c.anexo = anexo;
      toast(err.message);
    }
    c.enviando = false;
    render();
  }

  // na conversa, só redesenha quando muda o que ela mostra (um pedido para conectar, os apps): assim a lista não pula
  const assinatura = e => (S.tela ? JSON.stringify(e) : JSON.stringify([(e.mcp || {}).pedidos, e.apps.map(a => [a.app, a.anexos])]));
  async function carregar() {
    try {
      const e = await api.get();
      const mudou = !S.e || assinatura(e) !== assinatura(S.e);
      S.e = e;
      if (mudou) render();
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
    } else if (a === 'mcp') {
      await acao('config', { mcp: !S.e.mcp.ligado }, S.e.mcp.ligado ? 'Conector desligado' : 'Conector ligado');
    } else if (a === 'sensores') {
      const on = !!(S.e.sensores && S.e.sensores.ligado);
      await acao('config', { sensores: !on }, on ? 'Sensores desligados' : 'Sensores ligados');
    } else if (a === 'mcp-aprovar' || a === 'mcp-recusar') {
      await acao('mcp/decidir', { id: el.dataset.v, aprovar: a === 'mcp-aprovar' }, a === 'mcp-aprovar' ? 'Aprovado: volte para a IA' : 'Recusado');
    } else if (a === 'mcp-desconectar') {
      await acao('mcp/desconectar', { id: el.dataset.v }, 'Desconectado');
    } else if (a === 'ir-mcp') {
      S.aba = 'mcp'; guardar('correria-aba', 'mcp');
      if (S.tela !== 'opcoes') abrirTela('opcoes'); else render();
      const c = $('#mcp'); if (c) c.scrollIntoView({ block: 'start' });
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
    } else if (a === 'opcoes' || a === 'sobre' || a === 'mais') {
      abrirTela(a);
    } else if (a === 'tema') {
      S.tema = el.dataset.v; guardar('correria-tema', S.tema); aplicarTema(); render();
    } else if (a === 'cor') {  // escolher uma cor desliga a Cor do dia; vale para a casa toda
      const c = PALETA.find(x => x.id === el.dataset.v);
      S.e.aparencia = { cor: c.id, cor_dia: false }; render();
      await acao('config', { cor: c.id, cor_dia: false }, 'Cor do app: ' + c.nome);
    } else if (a === 'cor-dia') {
      const on = !((S.e.aparencia || {}).cor_dia !== false);
      S.e.aparencia = Object.assign({}, S.e.aparencia, { cor_dia: on }); render();
      await acao('config', { cor_dia: on }, on ? 'Cor do dia ligada' : 'Cor do dia desligada');
    } else if (a === 'aba') {
      S.aba = el.dataset.v; guardar('correria-aba', S.aba); render();
    } else if (a === 'voltar') {
      voltar();
    } else if (a === 'ch-enviar') {
      enviarConversa();
    } else if (a === 'ch-falar') {
      falar();
    } else if (a === 'ch-falar-x') {
      pararFala(); render();
    } else if (a === 'ch-sug') {
      enviarConversa(el.dataset.v);
    } else if (a === 'ch-anexar') {
      $('#ch-arquivo').click();
    } else if (a === 'ch-anexo-rm') {
      S.ch.anexo = null; render();
    } else if (a === 'ch-limpar') {
      try { S.ch.msgs = (await api.post('conversa/limpar', {})).mensagens; render(); toast('Conversa apagada'); } catch (err) { toast(err.message); }
    } else if (a === 'conversas') {
      S.ch.lista = undefined; abrirTela('conversas'); carregarLista();
    } else if (a === 'ch-nova' || a === 'conv-abrir') {
      pararFala();
      try {
        const r = a === 'ch-nova' ? await api.post('conversa/nova', {}) : await api.post('conversa/abrir', { id: el.dataset.v });
        Object.assign(S.ch, { msgs: r.mensagens || [], conversa: r.conversa || null, lista: r.conversas, texto: a === 'ch-nova' ? '' : S.ch.texto, anexo: null });
        if (S.tela === 'conversas') voltar(); else render();
        if (a === 'ch-nova') setTimeout(() => { const t = $('#ch-txt'); if (t) t.focus(); }, 60);
      } catch (err) { toast(err.message); if (a === 'conv-abrir') carregarLista(); }
    } else if (a === 'conv-apagar') {
      try {
        const r = await api.post('conversa/apagar', { id: el.dataset.v });
        Object.assign(S.ch, { msgs: r.mensagens || [], conversa: r.conversa || null, lista: r.conversas || [] });
        render(); toast('Conversa apagada');
      } catch (err) { toast(err.message); }
    } else if (a === 'ch-camera') {
      abrirCamera();
    } else if (a === 'cam-fechar') {
      fecharCamera();
    } else if (a === 'cam-foto') {
      camFoto();
    } else if (a === 'cam-galeria') {
      fecharCamera();
      const inp = $('#ch-foto'); if (inp) inp.click();
    } else if (a === 'limpar') {
      await acao('registro/limpar', {}, 'Mensagens apagadas');
    }
  });
  document.addEventListener('input', ev => {
    const el = ev.target;
    if (el.dataset.f) S.form[el.dataset.f] = el.value;
    if (el.id === 'ch-txt') {
      S.ch.texto = el.value; el.style.height = 'auto'; el.style.height = Math.min(el.scrollHeight, 140) + 'px';
      const b = $('#ch-pri'), novo = botaoPri(S.e);  // o microfone vira Enviar ao escrever (e volta com a caixa vazia)
      if (b && !novo.includes(`data-a="${b.dataset.a}"`)) b.outerHTML = novo;
    }
  });
  document.addEventListener('keydown', ev => {
    // no computador, Enter envia (Shift+Enter quebra a linha); no celular, o botão Enviar
    if (ev.key === 'Enter' && !ev.shiftKey && !ev.isComposing && ev.target.id === 'ch-txt' && matchMedia('(hover: hover)').matches) { ev.preventDefault(); enviarConversa(); }
  });
  document.addEventListener('change', async ev => {
    const el = ev.target;
    if (el.id === 'ch-arquivo' || el.id === 'ch-foto') {  // a foto ou o PDF da conversa
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

  /* ---------- Arrastar para o lado na conversa: as outras conversas da lista, como os outros apps trocam de aba (dedo para a
     esquerda: a seguinte da lista, mais antiga; para a direita: a anterior, mais nova; a conversa nova, ainda vazia, vem antes
     de todas). Não vale começando na borda da tela (é o Voltar do celular), num campo, numa fileira que rola para o lado, com
     a câmera aberta, fora da conversa ou enquanto a IA responde. */
  let arraste = null;
  document.addEventListener('touchstart', ev => {
    arraste = null;
    if (S.tela || CAM || S.ch.fala || !ev.touches || ev.touches.length !== 1) return;
    const t = ev.touches[0];
    if (t.clientX < 24 || t.clientX > window.innerWidth - 24) return;
    for (let el = ev.target instanceof Element ? ev.target : ev.target.parentElement; el && el !== document.body; el = el.parentElement) {
      if (el.matches('input, textarea, select, [contenteditable], [data-noswipe]')) return;
      const st = getComputedStyle(el);
      if ((st.overflowX === 'auto' || st.overflowX === 'scroll') && el.scrollWidth > el.clientWidth + 2) return;
    }
    arraste = { x: t.clientX, y: t.clientY, at: Date.now() };
  }, { passive: true });
  document.addEventListener('touchend', ev => {
    const s = arraste;
    arraste = null;
    if (!s || S.tela || CAM || !ev.changedTouches || !ev.changedTouches.length) return;
    const t = ev.changedTouches[0], dx = t.clientX - s.x, dy = t.clientY - s.y;
    if (Math.abs(dx) < 70 || Math.abs(dx) < Math.abs(dy) * 2 || Date.now() - s.at > 800) return;
    trocarConversa(dx < 0 ? 1 : -1);
  }, { passive: true });
  document.addEventListener('touchcancel', () => { arraste = null; }, { passive: true });
  function deslizar(d, fim) {  // a conversa entra do lado para onde o dedo foi; no fim da lista, só um toque de leve
    const el = $('#ch-lista');
    if (!el || !el.animate || matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    el.animate(fim ? [{ transform: 'none' }, { transform: `translateX(${d > 0 ? -14 : 14}px)` }, { transform: 'none' }]
      : [{ opacity: 0, transform: `translateX(${d > 0 ? 40 : -40}px)` }, { opacity: 1, transform: 'none' }],
    { duration: fim ? 220 : 280, easing: 'cubic-bezier(0.2, 0.8, 0.2, 1)' });
  }
  async function trocarConversa(d) {
    const c = S.ch;
    if (c.enviando || c.trocando || !c.msgs) return;
    c.trocando = true;
    try {
      if (c.lista === undefined) c.lista = (await api.conversas()).conversas || [];
      const L = c.lista, i = L.findIndex(x => x.id === c.conversa), j = i + d;  // i = -1: a conversa nova, antes de todas
      if (j < 0 || j >= L.length) { deslizar(d, true); return; }
      const r = await api.post('conversa/abrir', { id: L[j].id });
      if (S.tela) return;
      Object.assign(c, { msgs: r.mensagens || [], conversa: r.conversa || null, lista: r.conversas || L });
      render();
      deslizar(d);
    } catch (err) {
      c.lista = undefined;
      toast(err.message);
    } finally {
      c.trocando = false;
    }
  }

  if (history.state && history.state.tela) history.replaceState(null, '');  // recarregou: começa na conversa
  carregar().then(carregarConversa);
  // as mensagens novas aparecem sozinhas (sem atrapalhar quem está digitando); com o conector ligado, a cada
  // 4 segundos, para o pedido de conexão aparecer logo
  let ultimaCarga = Date.now();
  setInterval(() => {
    if (document.hidden || S.tela === 'sobre') return;
    const a = document.activeElement;
    if (a && (a.tagName === 'INPUT' || a.tagName === 'TEXTAREA') && !a.readOnly) return;
    if (!(S.e && S.e.mcp && S.e.mcp.ligado) && Date.now() - ultimaCarga < 9500) return;
    ultimaCarga = Date.now();
    carregar();
  }, 4000);
  window.CORRERIA_TESTE = { S, render, carregar, get CAM() { return CAM; } };
})();
