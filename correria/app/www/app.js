/* CorrerIA · a tela (JavaScript puro, sem build). Abre na conversa com a IA (os apps); a engrenagem leva às
   Opções, em abas: Integrações (1.14.0; antes, Apps: os apps, a IA e as últimas mensagens), WhatsApp (a Meta, o webhook, quem conversa) e MCP (o
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
    plus: '<path d="M12 5v14M5 12h14"/>',
    sparkles: '<path d="M9.9 15.5a2 2 0 0 0-1.4-1.4L2.4 12.5a.5.5 0 0 1 0-1l6.1-1.6a2 2 0 0 0 1.4-1.4l1.6-6.1a.5.5 0 0 1 1 0l1.6 6.1a2 2 0 0 0 1.4 1.4l6.1 1.6a.5.5 0 0 1 0 1l-6.1 1.6a2 2 0 0 0-1.4 1.4l-1.6 6.1a.5.5 0 0 1-1 0z"/><path d="M20 3v4M22 5h-4"/>',
    arquivo: '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/>',
    spark: '<path d="M9.9 15.5a2 2 0 0 0-1.4-1.4L2.4 12.5a.5.5 0 0 1 0-1l6.1-1.6a2 2 0 0 0 1.4-1.4l1.6-6.1a.5.5 0 0 1 1 0l1.6 6.1a2 2 0 0 0 1.4 1.4l6.1 1.6a.5.5 0 0 1 0 1l-6.1 1.6a2 2 0 0 0-1.4 1.4l-1.6 6.1a.5.5 0 0 1-1 0z"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    key: '<circle cx="7.5" cy="15.5" r="4.5"/><path d="m10.7 12.3 9.8-9.8M17 6l3 3M14.5 8.5l2 2"/>',
    lock: '<rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
    hash: '<path d="M4 9h16M4 15h16M10 3 8 21M16 3l-2 18"/>',
    cloud: '<path d="M17.5 19H9a7 7 0 1 1 6.71-9h1.79a4.5 4.5 0 1 1 0 9Z"/>',
    code: '<path d="m16 18 6-6-6-6"/><path d="m8 6-6 6 6 6"/>',
    globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/>',
    shield: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z"/><path d="m9 12 2 2 4-4"/>',
    gauge: '<path d="m12 14 4-4"/><path d="M3.3 19a10 10 0 1 1 17.4 0"/>',
    calendar: '<rect x="3" y="4" width="18" height="17" rx="2"/><path d="M8 2v4M16 2v4M3 10h18"/>',
    refresh: '<path d="M21 12a9 9 0 0 1-15.5 6.2L3 16M3 12A9 9 0 0 1 18.5 5.8L21 8"/><path d="M21 3v5h-5M3 21v-5h5"/>',
    toggle: '<rect x="2" y="6" width="20" height="12" rx="6"/><circle cx="16" cy="12" r="3"/>',
    unlink: '<path d="m18.8 13.4 1.8-1.8a5 5 0 0 0-7.1-7.1l-1.8 1.8M5.2 10.6l-1.8 1.8a5 5 0 0 0 7.1 7.1l1.8-1.8M8 2v3M2 8h3M16 22v-3M22 16h-3"/>',
    pin: '<path d="M12 17v5"/><path d="M9 10.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24V16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V7a1 1 0 0 1 1-1 2 2 0 0 0 0-4H8a2 2 0 0 0 0 4 1 1 0 0 1 1 1z"/>',
    recolher: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M15 3v18"/><path d="m8 9 3 3-3 3"/>',
    maximize: '<path d="M8 3H5a2 2 0 0 0-2 2v3M21 8V5a2 2 0 0 0-2-2h-3M3 16v3a2 2 0 0 0 2 2h3M16 21h3a2 2 0 0 0 2-2v-3"/>',
    minimize: '<path d="M8 3v3a2 2 0 0 1-2 2H3M21 8h-3a2 2 0 0 1-2-2V3M3 16h3a2 2 0 0 1 2 2v3M16 21v-3a2 2 0 0 1 2-2h3"/>',
    casa: '<path d="M15 21v-8a1 1 0 0 0-1-1h-4a1 1 0 0 0-1 1v8"/><path d="M3 10a2 2 0 0 1 .709-1.528l7-6a2 2 0 0 1 2.582 0l7 6A2 2 0 0 1 21 10v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    luz: '<path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5"/><path d="M9 18h6"/><path d="M10 22h4"/>',
    'book-open': '<path d="M12 7v14"/><path d="M3 18a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h5a4 4 0 0 1 4 4 4 4 0 0 1 4-4h5a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1h-6a3 3 0 0 0-3 3 3 3 0 0 0-3-3z"/>',
  };
  const ic = (n, cls = 'ic') => `<svg class="${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${IC[n] || ''}</svg>`;

  // tela: '' (a conversa, onde o app abre), 'mais' (o menu, como nos outros apps), 'opcoes' (Configurações) ou 'sobre';
  // aba: a de Configurações (fica guardada neste aparelho)
  // Opções (0.13.0): o Atalho no celular, como nos outros apps; só dentro do Home Assistant (fora dele, a aba some)
  const ABAS = [['apps', 'Integrações', 'layers'], ['whatsapp', 'WhatsApp', 'chat'], ['mcp', 'MCP', 'plug'], ['dados', 'Dados', 'database'], ['aparencia', 'Aparência', 'palette'], ['opcoes', 'Opções', 'toggle']];
  // 1.7.0: Opções sempre (as conversas velhas valem em qualquer lugar)
  const abasDe = () => ABAS;
  const guardada = k => { try { return localStorage.getItem(k); } catch (e) { return null; } };
  const guardar = (k, v) => { try { localStorage.setItem(k, v); } catch (e) { /* sem armazenamento: só nesta vez */ } };
  const S = { e: null, salvando: false, form: {}, tela: '', aba: guardada('correria-aba') || 'apps', tema: guardada('correria-tema') || 'auto',
    ch: { msgs: null, texto: '', anexo: null, enviando: false, pessoa: '', ola: '', conversa: null, lista: undefined, fala: '' } };
  /* 1.8.0: no computador (1000 px ou mais, fora da Tela cheia), a barra lateral da família (como no GerencIA, no
     CronologIA e no ResolvIA), em todas as telas: o app, Conversa e Mais, as conversas e a versão (pintarLado) */
  const DESK = window.matchMedia ? matchMedia('(min-width: 1000px)') : null;
  const lateral = () => !!(DESK && DESK.matches && !S.cheia);
  let carregandoLista = false;
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
  // 0.16.0 (padrão da família): toda linha com título tem um ícone pequeno antes dele; todo campo também
  const tituloLinha = (icone, titulo) => `<b>${ic(icone, 'ic-s')}${titulo}</b>`;
  // 1.14.0: onde a tela fala de um site (o painel da Meta, o da Cloudflare, o do provedor da IA), o nome abre o site
  const site = (href, texto) => `<a href="${href}" target="_blank" rel="noopener noreferrer">${texto}</a>`;
  const META = 'https://developers.facebook.com/apps/';
  // 1.14.2: o Duck DNS (onde se cria o endereço da casa) e a Cloudflare, em todo lugar onde a tela fala deles
  const DUCK = () => site('https://www.duckdns.org/', 'Duck DNS'), NUVEM = () => site('https://dash.cloudflare.com/', 'Cloudflare');
  const rotulo = (para, icone, titulo) => `<label for="${para}">${ic(icone, 'ic-s')}${titulo}</label>`;
  const cab = (icone, titulo, extra = '') => `<div class="rot" role="button" tabindex="0" data-dobra="${esc(titulo)}" aria-expanded="${!fechadas().has(titulo)}"><span class="rot-ic">${ic(icone)}</span><h2>${titulo}</h2>${extra}<span class="dobra-ic" aria-hidden="true">${ic('chev', 'ic-s')}</span></div>`;
  // 0.17.0 (padrão da família): toda seção (cartão) contrai e expande num toque no cabeçalho; o aparelho lembra as fechadas
  const fechadas = () => { try { return new Set(JSON.parse(guardada('correria-fechadas') || '[]')); } catch (e) { return new Set(); } };
  function dobrar(rot) {
    const t = rot.dataset.dobra, F = fechadas(), fechar = !F.has(t);
    if (fechar) F.add(t); else F.delete(t);
    guardar('correria-fechadas', JSON.stringify([...F]));
    render();
  }

  function cardWhatsApp(e) {
    const c = e.config;
    let st;
    if (!e.pronto) st = '<div class="status manual">Falta configurar: o ID do número, o token e a chave secreta.</div>';
    else if (e.conta) st = `<div class="status">${esc(e.conta.numero)}${e.conta.nome ? ' · ' + esc(e.conta.nome) : ''}</div>`;
    else st = '<div class="status manual">Configurado. Toque em Conferir para testar com a Meta.</div>';
    const f = e.fala || {};  // 0.15.0: o áudio é do WhatsApp (antes, em Apps, "ouve pela fala para texto")
    const audio = !e.pronto ? '' : f.pronta ? `<div class="status">Áudios do WhatsApp viram texto pelo ${esc(f.nome)}.</div>`
      : `<div class="status manual">Áudios do WhatsApp não viram texto. ${esc(f.motivo || 'Falta a fala para texto no Home Assistant.')}</div>`;
    // 0.17.0: liga e desliga como o conector MCP; ligado, o resto fica no quadro embaixo da chave
    const usar = `<div class="linha-sw"><div>${tituloLinha('chat', 'Usar o WhatsApp')}<span>${c.whatsapp ? 'Ligado: as pessoas da casa conversam com os apps pelo WhatsApp.' : 'Desligado.'}</span></div>
        <button class="sw${c.whatsapp ? ' on' : ''}" data-a="whatsapp" role="switch" aria-checked="${!!c.whatsapp}" aria-label="Usar o WhatsApp"></button></div>`;
    if (!c.whatsapp) return `<section class="card" id="whatsapp">${cab('chat', 'WhatsApp')}
      <p class="lead">A conta do WhatsApp Business, criada no ${site(META, 'painel da Meta')}.</p>${usar}</section>`;
    return `<section class="card" id="whatsapp">${cab('chat', 'WhatsApp')}
      <p class="lead">A conta do WhatsApp Business, criada no ${site(META, 'painel da Meta')}.</p>${usar}
      <div class="sub-op"><div class="sub-box">
      ${e.pronto ? `<div class="linha-sw"><div>${tituloLinha('send', 'Responder pelo WhatsApp')}<span>${c.ligado ? 'Ligado.' : 'Pausado: as mensagens chegam, mas ninguém responde.'}</span></div>
        <button class="sw${c.ligado ? ' on' : ''}" data-a="ligado" role="switch" aria-checked="${c.ligado}" aria-label="Responder pelo WhatsApp"></button></div>` : ''}
      ${st}${audio}
      <div class="campo">${rotulo('f-numero', 'hash', 'ID do número de telefone')}
        <input id="f-numero" class="inp" inputmode="numeric" autocomplete="off" data-f="numero_id" value="${esc(S.form.numero_id != null ? S.form.numero_id : c.numero_id)}" placeholder="Ex.: 109876543210"></div>
      <div class="campo">${rotulo('f-token', 'key', 'Token de acesso')}
        <input id="f-token" class="inp" type="password" autocomplete="off" data-f="token" value="${esc(S.form.token || '')}" placeholder="${c.token ? esc(c.token) + ' · cole outro para trocar' : 'Do Usuário do sistema, que não vence'}"></div>
      <div class="campo">${rotulo('f-segredo', 'lock', 'Chave secreta do aplicativo')}
        <input id="f-segredo" class="inp" type="password" autocomplete="off" data-f="segredo" value="${esc(S.form.segredo || '')}" placeholder="${c.segredo ? esc(c.segredo) + ' · cole outra para trocar' : 'Configurações do app › Básico'}"></div>
      <button class="btn out larga" data-a="conferir"${e.pronto ? '' : ' disabled'}>${ic('refresh', 'ic-s')}Conferir com a Meta</button>
      </div></div>
    </section>`;
  }

  // 1.11.0: o caminho de fora até aqui: de que endereço é o certificado, a porta no endereço e a última conexão de fora
  // (assim dá para saber se o que falta é o Duck DNS, o roteador ou o certificado)
  function caminhoDeFora(e, semCert, { mcp = false } = {}) {
    // 1.14.0: o conector MCP tem o endereço público dele (e.mcp.endereco); o webhook, o seu
    const w = e.webhook || {}, M = e.mcp || {}, end = (mcp ? M.endereco : (e.config || {}).endereco) || '', f = w.fora || {}, out = [], t = w.tunel || {};
    const confere = mcp ? M.cert_confere : w.cert_confere;
    const nomeDe = x => { try { return x ? new URL(x).hostname : ''; } catch (_) { return ''; } };
    // 1.13.0: pelo túnel da Cloudflare, o https e a porta 443 são os dela: só a última conexão que chegou por ele
    // (o túnel é do conector; o webhook só passa por ele quando o endereço é o mesmo)
    if (t.ligado && (mcp || (end && nomeDe(end) === nomeDe(M.endereco)))) {
      if (!t.aberto) out.push(`<div class="status erro" data-fora><span><b>A porta ${t.porta} não abriu</b> · Reinicie o CorrerIA.</span></div>`);
      else if (end) out.push(t.em ? `<div class="status" data-fora>Chegou uma conexão pelo túnel ${quando(t.em)}.</div>`
        : `<div class="status manual" data-fora><span><b>Nada chegou pelo túnel desde que o app abriu</b> · Confira o app Cloudflared e abra o endereço do conector.</span></div>`);
      return out.join('');
    }
    if (!w.https) out.push(`<div class="status manual"><span>${semCert}</span></div>`);  // num span: a linha é flex, e os links partiriam o texto
    else if (confere === false) out.push(`<div class="status erro"><span><b>O certificado é de ${esc(w.cert_nome)}</b> · No app ${DUCK()}, confira o domínio; depois reinicie o CorrerIA.</span></div>`);
    else out.push(`<div class="status">Certificado ${w.cert_nome ? 'de ' + esc(w.cert_nome) : esc(w.certificado)} · porta ${w.porta}</div>`);
    let u = null;
    try { u = end ? new URL(end) : null; } catch (_) { u = null; }
    if (u && !u.port && Number(w.porta) !== 443) out.push(`<div class="status manual" data-porta><span>Sem <b>:${w.porta}</b> no fim do endereço, só chega aqui se o roteador mandar a porta 443 para a ${w.porta}.</span></div>`);
    // 1.13.0: o Claude (e outras IAs) só conectam na porta 443: com outra porta no endereço, o conector não abre
    if (mcp && u && u.port && u.port !== '443') out.push(`<div class="status erro" data-porta><span><b>As IAs só conectam na porta 443</b> · Tire o :${esc(u.port)} do endereço e, no roteador, mande a 443 para a ${w.porta} (ou use o túnel da ${NUVEM()}).</span></div>`);
    if (end && w.https) out.push(!f.em ? `<div class="status manual" data-fora><span><b>Nenhuma conexão de fora desde que o app abriu</b> · Pelo 5G, abra o endereço do conector.</span></div>`
      : f.ok ? `<div class="status" data-fora>Chegou uma conexão de fora ${quando(f.em)}.</div>`
        : `<div class="status erro" data-fora><span><b>Chegou de fora ${quando(f.em)}, mas não abriu</b> · ${esc(f.erro)}.</span></div>`);
    return out.join('');
  }

  function cardWebhook(e) {
    const c = e.config, w = e.webhook;
    const cert = caminhoDeFora(e, `Sem certificado: instale o app ${DUCK()} com o Let's Encrypt (a ${site(META, 'Meta')} só aceita https).`);
    const meta = w.ultimo ? `<div class="status">Última mensagem da Meta ${quando(w.ultimo)}.</div>`
      : w.verificado_em ? `<div class="status">A Meta confirmou o endereço ${quando(w.verificado_em)}.</div>`
        : '<div class="status manual">A Meta ainda não chamou.</div>';
    return `<section class="card" id="webhook">${cab('link', 'Webhook na Meta')}
      <p class="lead">O endereço pelo qual a ${site(META, 'Meta')} entrega as mensagens, como o do ${DUCK()}. No roteador, a porta ${w.porta} vai para o Home Assistant.</p>
      <div class="campo">${rotulo('f-endereco', 'globe', 'Endereço público')}
        <input id="f-endereco" class="inp" inputmode="url" autocomplete="off" autocapitalize="off" spellcheck="false" data-f="endereco" value="${esc(S.form.endereco != null ? S.form.endereco : c.endereco)}" placeholder="https://casa-exemplo.duckdns.org:${w.porta}"></div>
      ${c.webhook ? `<ol class="passos"><li>Na ${site(META, 'Meta')}, em WhatsApp › Configuração › <b>Webhook</b>, toque em Editar.</li><li>Cole a <b>URL de retorno</b> e o <b>Token de verificação</b> abaixo e toque em Verificar e salvar.</li><li>Em Campos do webhook, assine <b>messages</b>.</li></ol>
      <div class="campo">${rotulo('f-url', 'link', 'URL de retorno')}<div class="copiar"><input id="f-url" class="inp" readonly value="${esc(c.webhook)}"><button class="btn peq out" data-a="copiar" data-v="f-url" aria-label="Copiar a URL de retorno">${ic('copy', 'ic-s')}Copiar</button></div></div>` : ''}
      <div class="campo">${rotulo('f-verif', 'shield', 'Token de verificação')}<div class="copiar"><input id="f-verif" class="inp" readonly value="${esc(c.verificacao)}"><button class="btn peq out" data-a="copiar" data-v="f-verif" aria-label="Copiar o token de verificação">${ic('copy', 'ic-s')}Copiar</button></div></div>
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
    const g = (a.guarda || []).some(x => x.startsWith('image/')) ? ' Guarda fotos.' : '';  // 1.17.0: a foto para uma tarefa
    return (f && le ? `${f}; também lê ${le}.` : f ? f + '.' : le ? `Lê ${le}.` : '') + g;
  }
  function cardApps(e) {
    const A = e.apps, i = e.ia || {}, ft = e.fala_tela || {};
    const lista = A.length ? A.map(a => `<div class="app-l"><span class="rot-ic">${ic('layers')}</span><span class="app-t"><b class="wm">${esc(a.nome.slice(0, -2))}<span>${esc(a.nome.slice(-2))}</span></b><small>${esc(a.assunto)}</small>${a.erro ? `<small class="le erro">${esc(a.erro)}</small>` : oQueFaz(a) ? `<small class="le">${oQueFaz(a)}</small>` : ''}</span></div>`).join('')
      : '<div class="status manual">Nenhum app ligado. Em cada app, ligue Mais › Configurações › Integrações › CorrerIA.</div>';
    // 1.15.0: todos os apps da família aparecem; os que estão com a integração desligada, depois dos ligados, dizendo isso
    const fora = (e.apps_desligados || []).map(a => `<div class="app-l off"><span class="rot-ic">${ic('layers')}</span><span class="app-t"><b class="wm">${esc(a.nome.slice(0, -2))}<span>${esc(a.nome.slice(-2))}</span></b><small>${esc(a.assunto)}</small><small class="le off">Integração desligada.${A.length ? ' No app: Mais › Configurações › Integrações › CorrerIA.' : ''}</small></span></div>`).join('');
    const mic = ft.pronta === false ? `<div class="status manual">Falar na conversa: ${esc(ft.motivo || 'sem fala para texto.')}</div>` : '';
    return `<section class="card" id="apps">${cab('layers', 'Apps')}
      ${lista}${fora}${A.length ? mic : ''}
    </section>`;
  }

  /* ---------- Configurações › Integrações › IA (0.16.0): qual IA conversa (no WhatsApp e aqui), como nos outros apps; o nome dela
     no que deu certo ou errado (sem cota, por exemplo) e no Uso da IA. 1.6.0: e a que pesquisa na internet (a conversa da
     tela), vazia igual à de conversar */
  function cardIA(e) {
    const i = e.ia || {}, L = (e.ias || {}).lista || [], sel = (e.ias || {}).escolhida || '', pesq = (e.ias || {}).pesquisa || '';
    if (!e.apps.some(a => a.ferramentas) && !L.length) return '';
    // como nos outros apps: o estado (verde quando está tudo certo), a caixa de seleção da IA e o Verificar de novo
    const saiu = sel && !L.some(x => x.id === sel), nome = i.nome || (L.find(x => x.id === sel) || {}).nome || (!sel && L.length === 1 ? L[0].nome : '');
    const st = i.ok === false ? `<div class="status erro"><span><b>Não respondeu</b> · ${esc(i.erro)}</span></div>`
        : !L.length ? '<div class="status manual"><span><b>Nenhuma IA</b> · Adicione no Home Assistant uma integração com tarefas de IA (Anthropic, Google Gemini, OpenAI ou Ollama).</span></div>'
          : saiu ? '<div class="status manual"><span><b>A IA escolhida saiu do Home Assistant</b> · Usando a padrão.</span></div>'
            : `<div class="status"><span><b>Pronta para conversar</b> · ${nome ? `Usando ${esc(nome)}` : 'Usando a IA padrão do Home Assistant'}${i.simulada ? ' (simulada, fora do Home Assistant)' : i.ok ? `, que respondeu ${quando(i.em)}` : ''}.</span></div>`;
    const opts = (v) => L.map(x => `<option value="${esc(x.id)}"${x.id === v ? ' selected' : ''}>${esc(x.nome)}</option>`).join('');
    return `<section class="card" id="ia">${cab('spark', 'IA')}${st}
      ${L.length ? `<div class="campo">${rotulo('f-ia', 'chat', 'Para conversar')}<select id="f-ia" class="inp" data-ia-ent aria-label="IA para conversar">
        <option value=""${sel ? '' : ' selected'}>Padrão do Home Assistant</option>${opts(sel)}</select></div>
      <div class="campo">${rotulo('f-ia-pesquisa', 'globe', 'Para pesquisar na internet')}<select id="f-ia-pesquisa" class="inp" data-ia-pesq aria-label="IA para pesquisar na internet">
        <option value=""${pesq ? '' : ' selected'}>Igual à de conversar</option>${opts(pesq)}</select></div>` : ''}
      <button class="btn out larga" data-a="ia-verificar">${ic('refresh', 'ic-s')}Verificar de novo</button></section>`;
  }

  // o conector MCP (para qualquer IA que aceite um, sem nome de marca na tela): o endereço, os pedidos esperando aprovação e quem está conectado
  function cardMcp(e) {
    const m = e.mcp || {};
    const sw = `<div class="linha-sw"><div>${tituloLinha('plug', 'Ligar o conector')}<span>${m.ligado ? 'Ligado: as IAs conectadas leem e mudam os apps, com a sua aprovação.' : 'Desligado.'}</span></div>
        <button class="sw${m.ligado ? ' on' : ''}" data-a="mcp" role="switch" aria-checked="${!!m.ligado}" aria-label="Ligar o conector"></button></div>`;
    if (!m.ligado) return `<section class="card" id="mcp">${cab('plug', 'Conector MCP')}
      <p class="lead">Os apps dentro de outras IAs, como um conector.</p>${sw}</section>`;
    const pedidos = (m.pedidos || []).map(p => `<div class="pedido"><div class="pedido-t"><b>${esc(p.nome)} quer se conectar</b><span>Código <b class="cod">${esc(p.codigo)}</b> · ${esc(p.host)}</span></div>
        <div class="btns"><button class="btn out" data-a="mcp-recusar" data-v="${esc(p.id)}">${ic('x', 'ic-s')}Recusar</button><button class="btn pri" data-a="mcp-aprovar" data-v="${esc(p.id)}">${ic('check', 'ic-s')}Aprovar</button></div></div>`).join('');
    const conexoes = (m.conexoes || []).map(c => `<div class="conexao"><span class="av">${esc((c.nome || '?').slice(0, 1).toUpperCase())}</span>
        <div class="conexao-t"><b>${esc(c.nome)}</b><span>${[c.pessoa, c.usado ? 'usou ' + quando(c.usado) : ''].filter(Boolean).map(esc).join(' · ')}</span></div>
        <button class="btn peq out" data-a="mcp-desconectar" data-v="${esc(c.id)}">${ic('unlink', 'ic-s')}Desconectar</button></div>`).join('');
    const w = e.webhook || {};  // 0.15.0: o endereço público e o certificado aqui também (antes: "Escreva o endereço público na aba WhatsApp")
    // 1.14.0: o endereço público do conector é dele (antes era o mesmo campo do webhook, nas duas abas)
    const publico = `<div class="campo">${rotulo('f-endereco-mcp', 'globe', 'Endereço público do conector')}
        <input id="f-endereco-mcp" class="inp" inputmode="url" autocomplete="off" autocapitalize="off" spellcheck="false" data-f="endereco_mcp" value="${esc(S.form.endereco_mcp != null ? S.form.endereco_mcp : (m.endereco || ''))}" placeholder="https://correria.casa-exemplo.com.br"></div>
      ${caminhoDeFora(e, `Sem certificado: instale o app ${DUCK()} com o Let's Encrypt (as IAs só conectam por https), ou use o túnel da ${NUVEM()}.`, { mcp: true })}`;
    const endereco = m.url ? `<div class="campo">${rotulo('f-mcp', 'plug', 'Endereço do conector')}<div class="copiar"><input id="f-mcp" class="inp" readonly value="${esc(m.url)}"><button class="btn peq out" data-a="copiar" data-v="f-mcp" aria-label="Copiar o endereço do conector">${ic('copy', 'ic-s')}Copiar</button></div></div>
      ${conexoes ? '' : `<ol class="passos"><li>Toque em <b>Copiar</b>.</li><li>Na IA, em Conectores, adicione um <b>conector personalizado</b> e cole o endereço.</li><li>Ao entrar, abre uma página com um <b>código</b>: aprove aqui o pedido com o mesmo código.</li></ol>`}`
      : '';
    // 0.16.3: tudo o que depende do conector (os pedidos, os endereços, os conectados e as Últimas mudanças) fica num
    // quadro recuado logo abaixo de Ligar o conector, dentro do cartão dele
    // 1.13.0: o túnel da Cloudflare (o app Cloudflared): sem abrir porta no roteador, na 443 dela (a operadora pode
    // bloquear a 443 de casa); o que vai no additional_hosts do app, pronto para copiar
    const t = w.tunel || {};
    const ipHa = /^\d{1,3}(\.\d{1,3}){3}$/.test(location.hostname) ? location.hostname : 'IP-do-Home-Assistant';
    let hostPub = '';
    try { hostPub = m.endereco ? new URL(m.endereco).hostname : ''; } catch (_) { hostPub = ''; }
    const yaml = `- hostname: ${hostPub || 'correria.seu-dominio.com.br'}\n  service: http://${ipHa}:${t.porta || 8444}`;
    const tunel = `<div class="linha-sw"><div>${tituloLinha('cloud', 'Pelo túnel da Cloudflare')}<span>${t.ligado ? 'Sem abrir porta no roteador.' : 'Para quando a operadora bloqueia a porta 443.'}</span></div>
        <button class="sw${t.ligado ? ' on' : ''}" data-a="tunel" role="switch" aria-checked="${!!t.ligado}" aria-label="Pelo túnel da Cloudflare"></button></div>
      ${t.ligado ? `<div class="sub-op"><div class="sub-box"><div class="campo">${rotulo('f-tunel', 'code', 'No app Cloudflared, em Additional Hosts')}
        <textarea id="f-tunel" class="inp mono" rows="2" readonly data-size="off">${esc(yaml)}</textarea>
        <button class="btn peq out" data-a="copiar" data-v="f-tunel" aria-label="Copiar a configuração do túnel">${ic('copy', 'ic-s')}Copiar</button></div></div></div>` : ''}`;
    const R = e.registro_mcp || [];
    const mudancas = `<details class="uso-ult mudancas" id="mudancas"${S.mudAberto ? ' open' : ''}><summary>${ic('chev', 'ic-s')}${ic('clock', 'ic-s')}Últimas mudanças (${R.length})</summary>
      ${listaMsgs(R, 'Nenhuma mudança ainda.')}${R.length ? `<button class="btn peq out" data-a="limpar" data-v="mcp">${ic('trash', 'ic-s')}Limpar</button>` : ''}</details>`;
    return `<section class="card" id="mcp">${cab('plug', 'Conector MCP')}
      <p class="lead">Os apps dentro de outras IAs, como um conector. O endereço, como o do ${DUCK()}, tem que abrir de fora na porta 443: no roteador, a 443 vai para a ${w.porta}, ou pelo túnel da ${NUVEM()}.</p>${sw}
      <div class="sub-op"><div class="sub-box">${pedidos}${publico}${tunel}${endereco}
        ${conexoes ? `<div class="lbl">${ic('users', 'ic-s')}Conectados</div>${conexoes}` : ''}
        ${mudancas}</div></div>
    </section>`;
  }

  const TIPO = { recebida: ['entra', 'Recebida'], enviada: ['sai', 'Enviada'], bloqueada: ['ban', 'Número sem cadastro'], erro: ['alert', 'Erro'], mcp: ['plug', 'Conector MCP'] };
  function listaMsgs(R, vazio) {
    return R.length ? `<div class="msgs">${R.map(r => {
      const [icone, rot] = TIPO[r.tipo] || ['chat', r.tipo];
      return `<div class="msg ${esc(r.tipo)}"><span class="msg-ic" title="${rot}">${ic(icone, 'ic-s')}</span><div>
        <div class="msg-t"><b>${esc(r.quem)}${r.tipo === 'bloqueada' ? ' · sem cadastro' : ''}</b><time datetime="${esc(r.em)}">${horaCurta(r.em)}</time></div>
        <p>${esc(r.texto)}${r.app && r.tipo === 'mcp' ? ` <small>· ${esc(r.app)}</small>` : ''}</p></div></div>`;
    }).join('')}</div>` : `<p class="vazio">${vazio}</p>`;
  }
  // as últimas mensagens do WhatsApp (as do conector ficam no cartão dele, 0.16.3)
  function cardMensagens(e) {
    const R = e.registro || [];
    return `<section class="card" id="mensagens">${cab('inbox', 'Últimas mensagens', R.length ? `<button class="btn peq" data-a="limpar" data-v="whatsapp">${ic('trash', 'ic-s')}Limpar</button>` : '')}
      ${listaMsgs(R, 'Nenhuma mensagem ainda.')}
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
    const corpo = aba === 'whatsapp' ? cardWhatsApp(e) + (e.config.whatsapp ? cardWebhook(e) + cardPessoas(e) + cardMensagens(e) : '') : aba === 'mcp' ? cardMcp(e)
      : aba === 'dados' ? cardDados() : aba === 'aparencia' ? cardTema() + cardCor(e) : aba === 'opcoes' ? cardConversas(e) + cardTelaCheia(e) + cardAtalho(e) : cardApps(e) + cardIA(e) + cardCasa(e) + cardUso(e) + cardSensores(e);
    // 0.15.0: o estado do WhatsApp só na aba dele (o MCP funciona sem o WhatsApp)
    return `${topoTela('Configurações', 'Mais')}
      ${pendentes(e)}
      <div class="abas-wrap"><nav class="abas" role="tablist" aria-label="Configurações">${abasDe(e).map(([k, n, i]) => `<button role="tab" aria-selected="${k === aba}" class="${k === aba ? 'on' : ''}" data-a="aba" data-v="${k}">${ic(i, 'ic-s')}<span>${n}</span></button>`).join('')}</nav>
        <span class="abas-fim esq" aria-hidden="true">${ic('back', 'ic-s')}</span><span class="abas-fim dir" aria-hidden="true">${ic('chev', 'ic-s')}</span></div>
      ${corpo}`;
  }
  // Mais, um menu como nos outros apps: Configurações e, por último, Sobre (cada um na sua tela)
  function telaMais() {
    const linha = (a, icone, titulo, txt) => `<button class="linha" data-a="${a}"><span class="rot-ic">${ic(icone)}</span><span class="linha-t"><b>${titulo}</b><small>${txt}</small></span>${ic('chev', 'ic-s chev')}</button>`;
    return `${topoTela('Mais', 'Conversa')}
      <section class="card linha-card mais-menu">${linha('opcoes', 'gear', 'Configurações', 'Integrações, WhatsApp, MCP, dados e aparência.')}
        ${linha('sobre', 'info', 'Sobre', 'CorrerIA Code, os apps e o GitHub.')}</section>`;
  }

  /* ---------- Configurações › Dados e Aparência (como nos outros apps) */
  function cardDados() {
    return `<section class="card" id="onde">${cab('database', 'Onde ficam os dados')}
      <p class="lead">Na pasta <code>/data</code> do app, que entra no backup do Home Assistant: <code>config.json</code> (o WhatsApp, o endereço e o número de cada pessoa), <code>conversas.json</code> (as conversas e as últimas mensagens), <code>mcp.json</code> (as IAs conectadas, com os tokens só em código) e <code>uso_ia.json</code> (o Uso da IA). O token e a chave secreta nunca voltam para a tela.</p></section>`;
  }
  const TEMAS = [['auto', 'Sistema', 'phone'], ['claro', 'Claro', 'sun'], ['escuro', 'Escuro', 'moon']];
  function cardTema() {
    return `<section class="card" id="tema">${cab('contrast', 'Tema')}<p class="lead">Cada aparelho guarda a sua escolha. Sistema segue o do Home Assistant.</p>
      <div class="temas" role="radiogroup" aria-label="Tema">${TEMAS.map(([k, n, i]) => `<button role="radio" aria-checked="${S.tema === k}" class="${S.tema === k ? 'on' : ''}" data-a="tema" data-v="${k}">${ic(i)}<span>${n}</span></button>`).join('')}</div></section>`;
  }
  const TAG = 'M8 0h20a2 2 0 0 1 2 2v16a2 2 0 0 1-2 2H8L0 13V7z', FURO = 'M9.7 10a2.7 2.7 0 1 0-5.4 0a2.7 2.7 0 1 0 5.4 0z';
  function cardCor(e) {
    const ap = e.aparencia || {}, dia = ap.cor_dia !== false, atual = corAtual(e);
    return `<section class="card" id="cor">${cab('palette', 'Cor do app')}<p class="lead">Vale para todos os aparelhos.</p>
      <div class="linha-sw"><div>${tituloLinha('calendar', 'Cor do dia')}<span>Muda a cor do app todo dia, a mesma em todos os apps.</span></div>
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
      <div class="campo">${rotulo('f-atalho', 'phone', 'Caminho')}<div class="copiar pilha"><input id="f-atalho" class="inp" readonly value="${esc(e.atalho)}"><button class="btn peq out" data-a="copiar" data-v="f-atalho" aria-label="Copiar o caminho">${ic('copy', 'ic-s')}Copiar</button></div></div></section>`;
  }

  /* ---------- Configurações › Integrações › Uso da IA: as chamadas da IA do WhatsApp e da conversa da tela (tokens estimados), no
     padrão dos outros apps (0.15.0): Hoje, 7 dias e Este mês; uma barra por dia (tocar mostra o dia); os tipos; Últimas chamadas recolhidas */
  const TIPO_USO = { whatsapp: 'WhatsApp', conversa: 'Conversa', pesquisa: 'Pesquisa na internet' };
  const RES_USO = { cota: 'sem cota', formato: 'resposta fora do formato', erro: 'erro' };
  const SEM = ['dom', 'seg', 'ter', 'qua', 'qui', 'sex', 'sáb'];
  const chamadas = n => `${n} ${n === 1 ? 'chamada' : 'chamadas'}`;
  // 1.14.0: onde ver o consumo e o saldo de cada IA em uso (a de conversar e a de pesquisar), como nos outros apps
  const PROVEDORES = [
    [/google|gemini/, () => `Gemini: consumo e cota no ${site('https://aistudio.google.com/', 'Google AI Studio')}, em Dashboard › Usage; o saldo dos créditos, em Billing.`],
    [/openai|chatgpt|gpt/, () => `OpenAI: consumo e custo em ${site('https://platform.openai.com/usage', 'platform.openai.com/usage')}.`],
    [/anthropic|claude/, () => `Claude: consumo e custo no ${site('https://platform.claude.com/usage', 'Claude Console')}; o saldo dos créditos, em ${site('https://platform.claude.com/settings/billing', 'Billing')}.`],
  ];
  function provedoresIA(e) {
    const I = e.ias || {}, L = I.lista || [], de = id => { const x = L.find(y => y.id === id); return x ? `${x.id} ${x.nome}` : (id || ''); };
    const acha = t => PROVEDORES.filter(([re]) => re.test(String(t).toLowerCase()));
    let achados = acha([de(I.escolhida), de(I.pesquisa), (e.ia || {}).nome || '', ...((e.uso_ia || {}).ultimas || []).map(c => c.ia || '')].join(' '));
    if (!achados.length) {  // na padrão do Home Assistant: o provedor das IAs de lá, se for um só
      const todos = new Set(L.flatMap(x => acha(`${x.id} ${x.nome}`)));
      if (todos.size === 1) achados = [...todos];
    }
    return achados.length ? achados.map(([, nota]) => `<p class="uso-nota">${nota()}</p>`).join('') : '<p class="uso-nota">O consumo exato fica no painel do provedor da IA.</p>';
  }

  function cardUso(e) {
    const u = e.uso_ia;
    if (!u || !u.hoje || !(u.dias || []).length) return '';
    const mil = n => n >= 1000 ? `${String(Math.round(n / 100) / 10).replace('.', ',')} mil` : String(Math.round(n || 0));
    const sub = t => t.cota ? `<span class="s alerta">${t.cota} ${t.cota > 1 ? 'vezes' : 'vez'} sem cota</span>` : t.erros ? `<span class="s alerta">${t.erros} com erro</span>` : `<span class="s">≈ ${mil(t.tokens)} tokens</span>`;
    const tile = (k, t) => `<div class="uso-t"><span class="k">${k}</span><b>${t.chamadas || 0}</b>${sub(t)}</div>`;
    const max = Math.max(1, ...u.dias.map(d => d.chamadas || 0));
    const hoje = u.dias[u.dias.length - 1].dia;
    if (!S.usoDia || !u.dias.some(d => d.dia === S.usoDia)) S.usoDia = hoje;
    const nomeDia = d => d === hoje ? 'hoje' : SEM[new Date(d + 'T12:00:00').getDay()];
    const diaLongo = d => d === hoje ? 'Hoje' : `${nomeDia(d)[0].toUpperCase() + nomeDia(d).slice(1)}, ${d.slice(8, 10)}/${d.slice(5, 7)}`;
    const resto = d => `${d.erros ? `, ${d.erros} com erro` : ''}${d.cota ? `, ${d.cota} sem cota` : ''}`;
    const barras = u.dias.map(d => {
      const lab = `${diaLongo(d.dia)}: ${chamadas(d.chamadas || 0)}${resto(d)}`;
      return `<button class="uso-bar" data-a="uso-dia" data-v="${esc(d.dia)}" aria-pressed="${d.dia === S.usoDia}" aria-label="${esc(lab)}" title="${esc(lab)}"><i style="height:${d.chamadas ? Math.max(4, Math.round(d.chamadas / max * 100)) : 0}%"></i></button>`;
    }).join('');
    const sel = u.dias.find(d => d.dia === S.usoDia);
    const tipos = Object.entries(u.semana.tipos || {}).sort((a, b) => b[1] - a[1]);
    const ult = (u.ultimas || []).map(c => `<li><b>${esc(TIPO_USO[c.tipo] || c.tipo)}</b>${RES_USO[c.resultado] ? `<span class="r-erro">${RES_USO[c.resultado]}</span>` : ''}
        <span class="t">${c.ia ? `${esc(c.ia)} · ` : ''}${String(c.segundos).replace('.', ',')} s · ≈ ${mil(c.tokens)} tokens · ${esc(quandoCurto(c.quando))}</span>${c.erro ? `<span class="uso-motivo">${esc(c.erro)}</span>` : ''}</li>`).join('');
    return `<section class="card" id="uso">${cab('chart', 'Uso da IA')}<p class="lead">As chamadas do app para a IA. Os tokens são estimados.</p>
      <div class="uso-ts">${tile('Hoje', u.hoje)}${tile('7 dias', u.semana)}${tile('Este mês', u.mes)}</div>
      <div class="uso-chart" role="group" aria-label="Chamadas de IA nos últimos 7 dias">${barras}</div>
      <div class="uso-dias" aria-hidden="true">${u.dias.map(d => `<span>${nomeDia(d.dia)}</span>`).join('')}</div>
      <p class="uso-cap" aria-live="polite">${diaLongo(sel.dia)}: <b>${chamadas(sel.chamadas || 0)}</b>${resto(sel)}.</p>
      ${tipos.length ? `<ul class="uso-tipos" aria-label="Nos últimos 7 dias">${tipos.map(([k, n]) => `<li>${esc(TIPO_USO[k] || k)} <b>${n}</b></li>`).join('')}</ul>` : ''}
      <details class="uso-ult"${S.usoAberto ? ' open' : ''}><summary>${ic('chev', 'ic-s')}${ic('clock', 'ic-s')}Últimas chamadas${(u.ultimas || []).length ? ` (${u.ultimas.length})` : ''}</summary><ul>${ult || '<li>Nenhuma chamada ainda.</li>'}</ul></details>
      ${provedoresIA(e)}
    </section>`;
  }
  // 14:32 hoje; 11/11 14:32 nos outros dias (como nos outros apps)
  function quandoCurto(iso) {
    const d = new Date(iso);
    if (isNaN(d)) return '';
    const hm = d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
    return d.toDateString() === new Date().toDateString() ? 'hoje ' + hm : `${d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' })} ${hm}`;
  }

  /* ---------- 1.5.0: Configurações › Integrações › Casa: o Home Assistant como mais um app (o Assist liga e desliga o que está
     exposto a ele; ver como está, sem mexer), ligada de início; as mudanças, como as dos apps, depois do sim */
  function cardCasa(e) {
    const c = e.casa || {}, on = !!c.ligado;
    return `<section class="card" id="casa">${cab('casa', 'Casa')}<p class="lead">Luzes, tomadas, cortinas, ar e cenas, pelo Assist do Home Assistant.</p>
      <div class="linha-sw"><div>${tituloLinha('luz', 'Mexer na casa')}<span>${!c.disponivel ? 'Só dentro do Home Assistant.' : on ? 'Ligado: "liga a luz da entrada".' : 'Desligado.'}</span></div>
        <button class="sw${on ? ' on' : ''}" data-a="casa" role="switch" aria-checked="${on}" aria-label="Mexer na casa"></button></div>
      ${on ? `<div class="sub-op"><div class="sub-box"><p class="lead">Só o que está exposto ao Assist (no Home Assistant, <b>Configurações › Assistentes de voz › Expor</b>). Cada mudança espera o seu <b>sim</b>.</p></div></div>` : ''}</section>`;
  }

  /* ---------- 1.5.0: Configurações › Opções › Tela cheia: em quanto tempo sem uso a Conversa recolhe sozinha */
  /* ---------- Configurações › Opções › Conversas (1.7.0): as conversas paradas há mais de tantos dias saem sozinhas (as da
     tela e as mensagens do WhatsApp), para não ficarem guardadas para sempre */
  const APAGAR_DIAS = [7, 30, 90, 0];
  function cardConversas(e) {
    const d = APAGAR_DIAS.includes(e.apagar_dias) ? e.apagar_dias : 30;
    return `<section class="card" id="conversas-velhas">${cab('conversas', 'Conversas')}
      <div class="campo">${tituloLinha('clock', 'Guardar as conversas por')}
        <div class="chips-tempo" role="radiogroup" aria-label="Guardar as conversas por">${APAGAR_DIAS.map(n => `<button role="radio" aria-checked="${d === n}" class="chip${d === n ? ' on' : ''}" data-a="apagar-dias" data-v="${n}">${ic(n ? 'calendar' : 'check', 'ic-s')}${n ? n + ' dias' : 'Sempre'}</button>`).join('')}</div>
        <span class="dica">Sem uso por esse tempo, saem sozinhas: as da tela e as mensagens do WhatsApp.</span></div></section>`;
  }
  function cardTelaCheia(e) {
    if (!e.painel) return '';
    const m = RECOLHER.includes(e.recolher) ? e.recolher : 3;
    return `<section class="card" id="tela-cheia">${cab('maximize', 'Tela cheia')}
      <div class="campo">${tituloLinha('hourglass', 'Recolher a Conversa sozinha')}
        <div class="chips-tempo" role="radiogroup" aria-label="Recolher a Conversa sozinha">${RECOLHER.map(n => `<button role="radio" aria-checked="${m === n}" class="chip${m === n ? ' on' : ''}" data-a="recolher" data-v="${n}">${ic('hourglass', 'ic-s')}${n} min</button>`).join('')}</div>
        <span class="dica">Depois desse tempo sem uso. Fixada (o alfinete), nunca.</span></div></section>`;
  }

  /* ---------- Configurações › Integrações › Sensores no Home Assistant (depois do Uso da IA, como nos outros apps) */
  function cardSensores(e) {
    const on = !!(e.sensores && e.sensores.ligado);
    const lista = [
      ['sensor.correria_certificado', 'os dias até o certificado vencer'],
      ['binary_sensor.correria_whatsapp', 'ligado com o WhatsApp conectado, com o nome e o erro'],
    ];
    return `<section class="card" id="sensores">${cab('gauge', 'Sensores no Home Assistant')}<p class="lead">Para usar em painéis e automações do Home Assistant.</p>
      <div class="linha-sw"><div>${tituloLinha('gauge', 'Criar sensores')}<span>${on ? 'Ligado.' : 'Desligado: nenhum sensor no Home Assistant.'}</span></div>
        <button class="sw${on ? ' on' : ''}" data-a="sensores" role="switch" aria-checked="${on}" aria-label="Criar sensores"></button></div>
      ${on ? `<div class="sub-op"><div class="sub-box sensor-list">${lista.map(([id, o]) => `<div class="sensor-row"><code>${id}</code><span>${o}</span></div>`).join('')}</div></div>` : ''}</section>`;
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
  const ICONE_TELA = { 'Configurações': 'gear', Mais: 'mais', Sobre: 'info', Conversas: 'conversas', Conversa: 'chat' };
  const tituloTela = titulo => `${ICONE_TELA[titulo] ? `<span class="rot-ic tela-ic" aria-hidden="true">${ic(ICONE_TELA[titulo])}</span>` : ''}${titulo}`;
  const topoTela = (titulo, volta) => `<header class="cab-tela"><button class="voltar" data-a="voltar">${ic('back', 'ic-s')}${volta}</button><h1>${tituloTela(titulo)}</h1></header>`;
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
  // 1.10.0: as perguntas de cada app; à vista ficam 6, uma de cada app por vez, e em Editar perguntas mais 20 modelos
  const SUGESTOES = {
    gerencia: ['Quanto gastei este mês?', 'O que vence esta semana?', 'Qual é o meu patrimônio hoje?', 'Lança 45 de mercado', 'Quanto sobrou este mês?', 'Quanto rende a carteira por mês?'],
    cronologia: ['O que tem na agenda amanhã?', 'Quais remédios faltam hoje?', 'Quem está ganhando o placar?', 'Marca dentista sexta às 15h', 'Quais rotinas estão atrasadas?'],
    resolvia: ['Quais tarefas vencem hoje?', 'Por onde eu começo hoje?', 'Adiciona leite na lista de compras', 'O que está atrasado?', 'Quantas tarefas eu tenho?'],
    inventario: ['Quanto valem os itens da sala?', 'Quantos eletrônicos eu tenho?', 'Quais cômodos valem mais?', 'Onde está o liquidificador?', 'Quanto vale a casa toda?'],
    memoria: ['O que eu anotei esta semana?', 'O que abre agora?', 'Onde anotei o telefone do encanador?', 'Quais blocos são meus?'],
    economia: ['Onde a compra fica mais barata?', 'Tem cupom bom agora?', 'O que está acabando?', 'Quanto vai dar a compra da lista?'],
    casa: ['Quais luzes estão acesas?', 'Apaga a luz da sala', 'A porta da frente está trancada?', 'Qual é a temperatura da casa?'],
  };
  const GERAIS = ['Resume o meu dia', 'O que eu tenho para fazer hoje?', 'O que vence nos próximos dias, em todos os apps?'];
  function perguntasDosApps(e) {
    const ids = e.apps.map(a => a.app).concat(e.casa && e.casa.ligado && e.casa.disponivel ? ['casa'] : []);
    const filas = ids.map(id => (SUGESTOES[id] || []).slice()).filter(f => f.length), out = [];
    while (filas.some(f => f.length)) for (const f of filas) if (f.length) out.push(f.shift());  // uma de cada app por vez
    return ids.length ? [...new Set(out.concat(GERAIS))] : [];
  }
  /* 1.1.0: Perguntas prontas: as dos apps ligados até a pessoa editar (Editar perguntas, guardadas no aparelho em
     correria-perguntas); na conversa vazia ficam à vista, e o ✨ ao lado da caixa abre as mesmas a qualquer momento */
  const PERG = 'correria-perguntas';
  function perguntas(e) {
    const todas = perguntasDosApps(e), pad = todas.slice(0, 6), modelos = todas.slice(6, 26);
    try {
      const v = JSON.parse(localStorage.getItem(PERG) || 'null');
      if (Array.isArray(v)) return { lista: v.filter(x => typeof x === 'string' && x.trim()), pad, modelos };
    } catch (x) { /* sem o armazenamento do aparelho: as dos apps */ }
    return { lista: pad, pad, modelos };
  }
  function guardarPerguntas(lista) {
    try { if (lista == null) localStorage.removeItem(PERG); else localStorage.setItem(PERG, JSON.stringify(lista)); } catch (x) { /* modo privado */ }
  }
  function perguntaNova() {
    const ed = S.ch.editando, t = ed && (ed.rascunho || '').trim();
    if (!t) return;
    ed.lista.push(t); ed.rascunho = ''; render();
    const inp = $('#ch-ed-txt'); if (inp) inp.focus();
  }
  // 1.11.0: em Editar perguntas, Perguntas prontas e Mais perguntas fecham num toque no título, com a seta no canto (o
  // aparelho lembra, em correria-perguntas); de início, as duas abertas
  function edFechadas() {
    try { const o = JSON.parse(guardada('correria-perguntas') || '{}'); return o && typeof o === 'object' ? o : {}; } catch (_) { return {}; }
  }
  function edDobrar(k) {
    const o = edFechadas();
    o[k] = !o[k];
    guardar('correria-perguntas', JSON.stringify(o));
  }
  const edCab = (k, icone, titulo, fechada) => `<button type="button" class="ch-ed-h ch-ed-dobra${k === 'mais' ? ' ch-ed-mais' : ''}" data-a="ch-ed-dobra" data-v="${k}" aria-expanded="${!fechada}">${ic(icone, 'ic-s')}<span>${titulo}</span><span class="dobra-ic" aria-hidden="true">${ic('chev', 'ic-s')}</span></button>`;
  function blocoPerguntas(e) {
    const ed = S.ch.editando;
    const F = edFechadas();
    if (ed) return `<div class="ch-ed">${edCab('prontas', 'nova', `Perguntas prontas (${ed.lista.length})`, F.prontas)}
        ${F.prontas ? '' : `${ed.lista.map((q, i) => `<div class="ch-ed-lin"><textarea id="ch-ed-q-${i}" class="ch-ed-txt" data-ed-i="${i}" rows="${Math.min(4, Math.max(1, Math.ceil(q.length / 32)))}" maxlength="120" enterkeyhint="done" data-size="off" aria-label="Mudar “${esc(q)}”">${esc(q)}</textarea><button class="ch-ed-x" data-a="ch-ed-tirar" data-v="${i}" aria-label="Tirar “${esc(q)}”" title="Tirar">${ic('x', 'ic-s')}</button></div>`).join('')}
        <div class="ch-ed-nova"><input id="ch-ed-txt" class="inp" maxlength="120" placeholder="Nova pergunta" aria-label="Nova pergunta" enterkeyhint="done" value="${esc(ed.rascunho || '')}">
          <button class="btn out" data-a="ch-ed-add">${ic('plus', 'ic-s')}Adicionar</button></div>`}
        ${((mais) => mais.length ? `${edCab('mais', 'sparkles', `Mais perguntas (${mais.length})`, F.mais)}
          ${F.mais ? '' : mais.map(q => `<button class="ch-ed-lin ch-ed-modelo" data-a="ch-ed-por" data-v="${esc(q)}" aria-label="Pôr “${esc(q)}”"><span>${esc(q)}</span><span class="ch-ed-mais-ic">${ic('plus', 'ic-s')}</span></button>`).join('')}` : '')(
          perguntas(e).modelos.filter(q => !ed.lista.includes(q)))}
        <div class="ch-ed-bts"><button class="btn out" data-a="ch-ed-padrao">${ic('refresh', 'ic-s')}Padrão</button><button class="btn pri" data-a="ch-ed-pronto">${ic('check', 'ic-s')}Pronto</button></div></div>`;
    const { lista } = perguntas(e);
    return `${lista.length ? `<div class="ch-sug">${lista.map(t => `<button class="chip" data-a="ch-sug" data-v="${esc(t)}">${ic('sparkles', 'ic-s')}${esc(t)}</button>`).join('')}</div>` : ''}
      <button class="ch-ed-abrir" data-a="ch-ed-abrir">${ic('nova', 'ic-s')}Editar perguntas</button>`;
  }
  function conversa(e) {
    const c = S.ch, M = c.msgs;
    let corpo;
    if (M === null) corpo = '<p class="vazio">Abrindo…</p>';
    else if (!M.length && !c.enviando) {
      if (!e.apps.length) corpo = `<div class="ch-vazio"><p>Nenhum app ligado. Em cada app, ligue Mais › Configurações › Integrações › CorrerIA.</p><button class="btn out" data-a="opcoes">${ic('gear', 'ic-s')}Configurações</button></div>`;
      else {
        corpo = `<div class="ch-vazio"><p>Pergunte ou peça algo aos apps${e.apps.some(a => (a.anexos || []).length) ? ', ou mande uma foto ou um PDF' : e.apps.some(a => (a.guarda || []).length) ? ', ou mande uma foto' : ''}.</p>
          ${blocoPerguntas(e)}</div>`;
      }
    } else {
      // 1.10.0: a mudança que espera o sim (a última mensagem): o Sim e o Não para tocar, embaixo
      const sim = k => k === M.length - 1 && M[k].confirmar && !c.enviando
        ? `<div class="ch-sim"><button class="btn out" data-a="ch-resp" data-v="Não">${ic('x', 'ic-s')}Não</button><button class="btn pri" data-a="ch-resp" data-v="Sim">${ic('check', 'ic-s')}Sim</button></div>` : '';
      corpo = M.map((m, k) => `<div class="ch-msg ${m.papel === 'ia' ? 'ia' : 'eu'}"><div class="ch-bolha">${m.anexo ? `<span class="ch-anexo">${ic('clip', 'ic-s')}${esc(m.anexo)}</span>` : ''}${m.texto ? (m.papel === 'ia' ? formatar(m.texto) : `<p>${esc(m.texto)}</p>`) : ''}</div>${sim(k)}${m.app ? `<small class="ch-app">${esc(m.app)}</small>` : ''}</div>`).join('')
        + (c.enviando ? '<div class="ch-msg ia"><div class="ch-bolha ch-pensando" aria-label="Pensando"><span></span><span></span><span></span></div></div>' : '');
    }
    const le = e.apps.some(a => (a.anexos || []).length || (a.guarda || []).length), f = c.fala, ouvindo = f === 'ouvindo' || f === 'abrindo';
    const lugar = f === 'ouvindo' ? 'Ouvindo…' : f === 'abrindo' ? 'Abrindo o microfone…' : f === 'entendendo' ? 'Entendendo…' : 'Sua pergunta';
    // 1.1.0: um botão só para o anexo (Tirar foto, Escolher fotos, Escolher arquivo), e o ✨ das perguntas prontas
    const esquerda = ouvindo ? `<button class="ch-bt" data-a="ch-falar-x" aria-label="Cancelar" title="Cancelar">${ic('x')}</button>`
      : le ? `<button class="ch-bt${c.menu ? ' on' : ''}" data-a="ch-menu" aria-label="Anexar" title="Anexar" aria-expanded="${c.menu ? 'true' : 'false'}"${f ? ' disabled' : ''}>${ic('clip')}</button>` : '';
    const rap = !ouvindo && M && M.length && e.apps.length;
    const aberto = rap && (c.rapidas || c.editando);
    const menu = le && c.menu && !ouvindo ? `<div class="ch-menu" role="menu">
        <button class="ch-op" role="menuitem" data-a="ch-camera">${ic('camera', 'ic-s')}Tirar foto</button>
        <button class="ch-op" role="menuitem" data-a="ch-galeria">${ic('image', 'ic-s')}Escolher fotos</button>
        <button class="ch-op" role="menuitem" data-a="ch-anexar">${ic('arquivo', 'ic-s')}Escolher arquivo</button></div>` : '';
    return `<header class="cab"><div class="cab-l"><p class="eyebrow"><span class="brand">Correr<span>IA</span></span>${c.ola ? `<span class="ola-sep"> · </span>Olá, ${esc(c.ola)}` : ''}</p><h1>${tituloTela('Conversa')}</h1></div>
        <div class="cab-bts">${lateral() ? '' : `<button class="bt-icone" data-a="conversas" aria-label="Conversas" title="Conversas">${ic('conversas')}</button>
          ${M && M.length ? `<button class="bt-icone" data-a="ch-nova" aria-label="Nova conversa" title="Nova conversa">${ic('nova')}</button>` : ''}`}
          ${botaoCheia(e)}${lateral() ? '' : `<button class="bt-icone" data-a="mais" aria-label="Mais" title="Mais">${ic('mais')}</button>`}</div></header>
      ${pendentes(e)}
      <div class="ch-lista" id="ch-lista">${corpo}</div>
      <div class="ch-pe">
        ${aberto ? `<div class="ch-rapidas">${blocoPerguntas(e)}</div>` : ''}${menu}
        ${c.anexo ? `<div class="ch-prev">${/^data:image\//.test(c.anexo.b64 || '') ? `<img src="${c.anexo.b64}" alt="">` : ic('clip', 'ic-s')}<span>${esc(c.anexo.nome)}</span><button data-a="ch-anexo-rm" aria-label="Tirar o arquivo">${ic('x', 'ic-s')}</button></div>` : ''}
        <div class="ch-barra${ouvindo ? ' ouvindo' : ''}">${esquerda}
          <textarea id="ch-txt" class="inp" rows="1" data-size="off" placeholder="${lugar}" enterkeyhint="send"${f ? ' disabled' : ''}>${esc(c.texto)}</textarea>
          ${rap ? `<button class="ch-bt ch-qbt${aberto ? ' on' : ''}" data-a="ch-rapidas" aria-label="Perguntas prontas" title="Perguntas prontas" aria-expanded="${aberto ? 'true' : 'false'}">${ic('sparkles')}</button>` : ''}
          ${botaoPri(e)}</div>
      </div>`;
  }
  /* ---------- Tela cheia (1.2.0): numa tela grande (1100 px ou mais, como nos outros apps), o painel da CronologIA (o A
     seguir, as Tarefas do dia, o placar, a folha do MemorIA) toma a tela e a Conversa fica à direita, sempre à mão, para
     pedir qualquer coisa aos apps. O painel é a própria CronologIA (?painel=1), num quadro que não é redesenhado com a
     conversa. Sai pelo mesmo botão, pelo Esc, pelo Voltar do celular ou quando a tela fica estreita. */
  const LARGA = window.matchMedia ? matchMedia('(min-width: 1100px)') : null;
  const podeCheia = e => !!(e && e.painel && LARGA && LARGA.matches);
  function botaoCheia(e) {
    if (!podeCheia(e)) return '';
    if (!S.cheia) return `<button class="bt-icone" data-a="cheia" aria-label="Tela cheia" title="Tela cheia">${ic('maximize')}</button>`;
    // 1.3.0: Fixar (a Conversa não recolhe mais) e Recolher (só solta)
    const f = fixa(), tf = f ? 'Soltar a Conversa' : 'Fixar a Conversa aberta';
    return `<button class="bt-icone${f ? ' on' : ''}" data-a="conversa-fixar" aria-pressed="${f}" aria-label="${tf}" title="${tf}">${ic('pin')}</button>`
      + (f ? '' : `<button class="bt-icone" data-a="conversa-recolher" aria-label="Recolher a Conversa" title="Recolher a Conversa">${ic('recolher')}</button>`)
      + (cabPainel() ? '' : `<button class="bt-icone on" data-a="cheia" aria-label="Sair da tela cheia" title="Sair da tela cheia">${ic('minimize')}</button>`);
  }
  /* 1.4.0: com a CronologIA 1.97.0 ou mais nova (painel_cabecalho), os botões da Conversa e do Sair ficam no alto do
     painel, sem a faixa daqui: o painel fica com a tela toda e a Conversa aberta toma o lugar da folha (o painel diz onde,
     {painel: 'lugar', x, y, w, h}); ele avisa o toque nos botões ({painel: 'conversa' | 'sair'}) e aqui se conta se a
     Conversa está aberta ou tem resposta nova ({conversa: {aberta, novidade}}). Só as mensagens do quadro, da mesma origem. */
  const cabPainel = () => !!(S.cheia && S.e && S.e.painel_cabecalho);
  let esperaLugar = null;
  function contarAoPainel() {
    const q = $('#painel');
    if (!cabPainel() || !q || !q.contentWindow) return;
    try { q.contentWindow.postMessage({ conversa: { aberta: !!S.aberta, novidade: !!S.ch.novidade } }, location.origin); } catch (err) { /* fechou */ }
  }
  function aplicarLugar(l) {
    const st = document.body.style, q = $('#painel'), r = q ? q.getBoundingClientRect() : { left: 0, top: 0 };
    if (l && l.w > 0 && l.h > 0) {
      st.setProperty('--lx', Math.round(r.left + l.x) + 'px'); st.setProperty('--ly', Math.round(r.top + l.y) + 'px');
      st.setProperty('--lw', Math.round(l.w) + 'px'); st.setProperty('--lh', Math.round(l.h) + 'px');
    } else ['--lx', '--ly', '--lw', '--lh'].forEach(k => st.removeProperty(k));
    if (l && l.w > 0) { clearTimeout(esperaLugar); document.body.classList.remove('espera-lugar'); }
  }
  function esperarLugar() {  // abrindo: a Conversa aparece já no lugar da folha (ou, sem resposta, à direita)
    if (!cabPainel()) return;
    document.body.classList.add('espera-lugar');
    clearTimeout(esperaLugar);
    esperaLugar = setTimeout(() => document.body.classList.remove('espera-lugar'), 700);
  }
  function alternarConversa() {
    if (!S.cheia) return;
    if (S.aberta) recolher(); else abrirConversa();
  }
  window.addEventListener('message', ev => {
    const q = $('#painel'), d = ev.data;
    if (!S.cheia || !q || ev.source !== q.contentWindow || ev.origin !== location.origin || !d || typeof d !== 'object') return;
    if (d.painel === 'conversa') alternarConversa();
    else if (d.painel === 'sair') cheia(false);
    else if (d.painel === 'pronto') contarAoPainel();
    else if (d.painel === 'lugar') aplicarLugar(d);
  });
  /* 1.3.0: na Tela cheia, a Conversa começa recolhida (uma faixa fina à direita, com o botão de abrir) e o painel fica com
     quase a tela toda; aberta, recolhe sozinha depois de 5 minutos sem uso, ou no Recolher. Fixada (o alfinete, guardado
     no aparelho), fica aberta e nunca recolhe. */
  // 1.5.0: 3 minutos de início; Configurações › Opções › Tela cheia muda (1, 3, 5 ou 10)
  const RECOLHER = [1, 3, 5, 10];
  const recolheMs = () => (S.e && RECOLHER.includes(S.e.recolher) ? S.e.recolher : 3) * 60 * 1000;
  const fixa = () => guardada('correria-conversa-fixa') === '1';
  let timerRecolhe = null;
  function armarRecolher() {
    clearTimeout(timerRecolhe);
    if (!S.cheia || !S.aberta || fixa()) return;
    timerRecolhe = setTimeout(() => {
      if (!S.cheia || !S.aberta || fixa()) return;
      if (S.ch.enviando || S.ch.fala || CAM) return armarRecolher();  // no meio de algo: espera mais
      recolher();
    }, recolheMs());
  }
  function abrirConversa() {
    S.aberta = true;
    S.ch.novidade = false;
    esperarLugar();
    document.body.classList.remove('recolhida');
    render();
    armarRecolher();
    setTimeout(() => { const t = $('#ch-txt'); if (t) t.focus(); }, 60);
  }
  function recolher() {
    clearTimeout(timerRecolhe);
    pararFala();
    S.aberta = false;
    S.ch.menu = false;
    document.body.classList.add('recolhida');
    render();
  }
  function trilho() {
    return `<div class="trilho">
      <button class="tr-bt pri${S.ch.novidade ? ' novo' : ''}" data-a="conversa-abrir" aria-label="Abrir a Conversa" title="Abrir a Conversa">${ic('chat')}</button>
      <span class="tr-nome" aria-hidden="true">Conversa</span><span class="tr-esp"></span>
      <button class="tr-bt" data-a="cheia" aria-label="Sair da tela cheia" title="Sair da tela cheia">${ic('minimize')}</button></div>`;
  }
  // usar a Conversa (tocar, escrever, rolar) conta o tempo de novo
  ['pointerdown', 'keydown', 'input', 'wheel', 'touchstart'].forEach(t => document.addEventListener(t, ev => { if (S.cheia && S.aberta && ev.target && ev.target.closest && ev.target.closest('#app')) armarRecolher(); }, { passive: true }));
  window.addEventListener('scroll', () => { if (S.cheia && S.aberta) armarRecolher(); }, { passive: true });
  let fsDoc = null, fsLigada = false;
  function aoTelaCheiaDoNavegador() {  // saiu da tela cheia do navegador (o Esc dele): sai daqui também
    if (fsDoc && fsDoc.fullscreenElement) fsLigada = true;
    else if (fsLigada) { fsLigada = false; if (S.cheia) cheia(false); }
  }
  function cheia(on, voltou) {
    if (!!S.cheia === on || (on && !podeCheia(S.e))) return;
    S.cheia = on;
    S.aberta = on && fixa();
    clearTimeout(timerRecolhe);
    document.body.classList.toggle('cheia', on);
    document.body.classList.toggle('recolhida', on && !S.aberta);
    document.body.classList.toggle('cab-painel', cabPainel());
    if (on && S.aberta) esperarLugar();
    if (!on) { aplicarLugar(null); document.body.classList.remove('espera-lugar'); }
    let quadro = $('#painel');
    if (on && !quadro) {
      quadro = document.createElement('iframe');
      quadro.id = 'painel';
      quadro.title = 'Painel da CronologIA';
      quadro.src = S.e.painel;
      quadro.addEventListener('load', contarAoPainel);
      document.body.insertBefore(quadro, $('#app'));
    } else if (!on && quadro) quadro.remove();
    if (on) history.pushState({ ...(history.state || {}), cheia: 1 }, '');
    else if (!voltou && history.state && history.state.cheia) history.back();
    // o quadro do Home Assistant (a mesma origem) ocupa o monitor todo, quando o navegador deixa
    let el = document.documentElement;
    try { if (window.frameElement) el = window.frameElement; } catch (err) { /* outra origem: só esta página */ }
    const doc = el.ownerDocument;
    if (fsDoc !== doc) {
      if (fsDoc) fsDoc.removeEventListener('fullscreenchange', aoTelaCheiaDoNavegador);
      fsDoc = doc;
      doc.addEventListener('fullscreenchange', aoTelaCheiaDoNavegador);
    }
    try {
      if (on && !doc.fullscreenElement && el.requestFullscreen) el.requestFullscreen().catch(() => {});
      if (!on && doc.fullscreenElement && doc.exitFullscreen) doc.exitFullscreen().catch(() => {});
    } catch (err) { /* o navegador não deixa: o painel e a conversa, sem o monitor todo */ }
    render();
  }
  if (LARGA) {
    try { LARGA.addEventListener('change', () => { if (!LARGA.matches && S.cheia) cheia(false); else render(); }); } catch (err) { /* antigo */ }
  }
  if (DESK) {
    try { DESK.addEventListener('change', () => render()); } catch (err) { /* antigo */ }
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
  function listaConversas() {
    const L = S.ch.lista;
    return L === undefined ? '<p class="vazio">Carregando…</p>' : !L.length ? '<p class="vazio">Nenhuma conversa ainda.</p>'
      : `<ul class="conv-lista">${L.map(x => `<li class="conv${x.aberta ? ' aberta' : ''}"><button class="conv-abrir" data-a="conv-abrir" data-v="${esc(x.id)}"${x.aberta ? ' aria-current="true"' : ''}>
          <b>${esc(x.titulo)}</b><span>${esc(quando(x.atualizada))} · ${x.mensagens} ${x.mensagens === 1 ? 'mensagem' : 'mensagens'}${x.aberta ? ' · aberta' : ''}</span></button>
          <button class="bt-icone peq" data-a="conv-apagar" data-v="${esc(x.id)}" aria-label="Apagar ${esc(x.titulo)}" title="Apagar">${ic('trash', 'ic-s')}</button></li>`).join('')}</ul>`;
  }
  function telaConversas() {
    return `${topoTela('Conversas', 'Conversa')}<div class="conv-pag">
      <button class="btn pri larga" data-a="ch-nova">${ic('nova', 'ic-s')}Nova conversa</button>${listaConversas()}</div>`;
  }
  function pintarLado() {
    let el = document.getElementById('lado');
    if (!lateral()) { if (el) el.remove(); return; }
    if (!el) { el = document.createElement('aside'); el.id = 'lado'; el.setAttribute('aria-label', 'Menu'); document.body.prepend(el); }
    if (S.ch.lista === undefined && !carregandoLista) carregarLista();
    const t = S.tela, naConversa = !t || t === 'conversas', L = S.ch.lista || [];
    const link = (k, n, i, on) => `<button class="side-link" data-a="lado-ir" data-v="${k}"${on ? ' aria-current="page"' : ''}>${ic(i)}<span>${n}</span></button>`;
    el.innerHTML = `<div class="side-brand"><span class="side-raio" aria-hidden="true">${ic('zap')}</span><span>Correr<b>IA</b></span></div>
      <nav class="side-nav" aria-label="Seções">${link('', 'Conversa', 'chat', naConversa)}${link('mais', 'Mais', 'mais', !naConversa)}</nav>
      <div class="side-h"><span>Conversas</span><button class="side-nova" data-a="ch-nova" aria-label="Nova conversa" title="Nova conversa">${ic('nova', 'ic-s')}</button></div>
      <div class="side-lista">${S.ch.lista === undefined ? '<p class="side-vazio">Carregando…</p>' : !L.length ? '<p class="side-vazio">Nenhuma conversa ainda.</p>'
        : L.map(x => { const on = x.aberta && naConversa; return `<div class="side-conv${on ? ' on' : ''}"><button class="side-item" data-a="conv-abrir" data-v="${esc(x.id)}"${on ? ' aria-current="page"' : ''}>
          <span class="sl-nome">${esc(x.titulo)}</span><small>${esc(quando(x.atualizada))}</small></button>
          <button class="side-x" data-a="conv-apagar" data-v="${esc(x.id)}" aria-label="Apagar ${esc(x.titulo)}" title="Apagar">${ic('trash', 'ic-s')}</button></div>`; }).join('')}</div>
      <p class="side-foot">CorrerIA ${esc((S.e && S.e.versao) || '')}</p>`;
  }
  function carregarLista() {
    carregandoLista = true;
    const pinta = () => { carregandoLista = false; if (S.tela === 'conversas' || lateral()) render(); };
    return api.conversas().then(r => { S.ch.lista = r.conversas || []; pinta(); })
      .catch(err => { S.ch.lista = S.ch.lista || []; toast(err.message); pinta(); });
  }

  /* ---------- Tirar foto: a câmera aqui dentro, como nos outros apps (em http não abre: dá para escolher a foto) */
  let CAM = null;
  const camOk = () => !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
  async function abrirCamera() {
    fecharCamera(true);
    CAM = { status: 'abrindo' };
    history.pushState({ tela: S.tela || '', cam: true, ...(S.cheia ? { cheia: 1 } : {}) }, '');
    pintarCamera();
    if (!camOk()) {
      CAM.status = 'erro';
      CAM.erro = window.isSecureContext === false
        ? 'A câmera só abre aqui com o Home Assistant num endereço seguro (https), como o do Home Assistant Cloud. Dá para tirar a foto pelo celular e escolher.'
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
    const sel = ativo && 'selectionStart' in document.activeElement ? [document.activeElement.selectionStart, document.activeElement.selectionEnd] : null;
    document.body.dataset.tela = S.tela || 'conversa';
    document.body.classList.toggle('lado', lateral());
    pintarLado();
    aplicarCor();
    $('#app').innerHTML = S.cheia && !S.aberta ? (cabPainel() ? '' : trilho()) : S.tela === 'opcoes' ? opcoes(e) : S.tela === 'sobre' ? sobre(e) : S.tela === 'mais' ? telaMais() : S.tela === 'conversas' ? telaConversas() : conversa(e);
    if (ativo) {
      const el = document.getElementById(ativo);
      if (el && el.focus) el.focus();
      try { if (el && sel && sel[0] != null) el.setSelectionRange(sel[0], sel[1]); } catch (_) { /* um campo sem cursor */ }
    }
    if (!S.tela) {
      window.scrollTo(0, document.body.scrollHeight);
      const l = cabPainel() && $('#ch-lista');  // 1.4.0: no lugar da folha, a lista rola dentro do quadro
      if (l) l.scrollTop = l.scrollHeight;
    }
    contarAoPainel();
    // as abas não cabem num celular estreito e rolam para o lado: a escolhida fica à vista (a tela é redesenhada)
    const aba = document.querySelector('.abas .on');
    if (aba && aba.parentElement) {
      const nav = aba.parentElement, x = aba.offsetLeft - nav.offsetLeft;
      if (x < nav.scrollLeft || x + aba.offsetWidth > nav.scrollLeft + nav.clientWidth) nav.scrollLeft = Math.max(0, x - (nav.clientWidth - aba.offsetWidth) / 2);
    }
    marcarAbas();
    const F = fechadas();
    document.querySelectorAll('#app section.card > .rot[data-dobra]').forEach(r => r.parentElement.classList.toggle('fechada', F.has(r.dataset.dobra)));
  }
  // 0.16.1 (padrão da família): quando as abas não cabem, a ponta de onde há mais some aos poucos, com uma seta
  // (0.16.2) as abas mudam de largura quando a fonte do app termina de carregar: o tamanho de cada uma é acompanhado
  let olhoAbas = null;
  function marcarAbas() {
    const nav = document.querySelector('.abas-wrap > .abas');
    if (!nav) return;
    const w = nav.parentElement;
    w.classList.toggle('tem-esq', nav.scrollLeft > 2);
    w.classList.toggle('tem-dir', nav.scrollLeft + nav.clientWidth < nav.scrollWidth - 2);
    if (window.ResizeObserver && (!olhoAbas || olhoAbas.nav !== nav)) {
      if (olhoAbas) olhoAbas.ro.disconnect();
      const ro = new ResizeObserver(() => marcarAbas());
      ro.observe(nav);
      nav.querySelectorAll('button').forEach(b => ro.observe(b));
      olhoAbas = { nav, ro };
    }
  }
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => marcarAbas());
  document.addEventListener('scroll', ev => { if (ev.target.classList && ev.target.classList.contains('abas')) marcarAbas(); }, true);
  window.addEventListener('resize', marcarAbas);

  /* ---------- telas: as Opções e o Sobre ocupam uma entrada no histórico cada (o Voltar do celular volta um passo) */
  function abrirTela(t) {
    if (S.tela === t) return;
    pararFala();
    history.pushState({ tela: t, ...(S.cheia ? { cheia: 1 } : {}) }, '');
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
    if (S.cheia && !(history.state && history.state.cheia)) { cheia(false, true); return; }  // e sai da Tela cheia
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
    if (S.cheia && !S.aberta) c.novidade = true;  // chegou com a Conversa recolhida: o ponto no botão de abrir
    render();
    armarRecolher();
  }

  // na conversa, só redesenha quando muda o que ela mostra (um pedido para conectar, os apps): assim a lista não pula
  const assinatura = e => (S.tela ? JSON.stringify(e) : JSON.stringify([(e.mcp || {}).pedidos, e.apps.map(a => [a.app, a.anexos, a.guarda]), e.painel]));
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
    const rot = ev.target.closest('.rot[data-dobra]');
    if (rot && !ev.target.closest('button, a, input')) return dobrar(rot);
    const el = ev.target.closest('[data-a]');
    if (!el || el.disabled) return;
    const a = el.dataset.a;
    if (a === 'conferir') {
      const r = await acao('conferir', {}, null);
      if (r && r.conta) toast('Conferido com a Meta');
    } else if (a === 'ligado') {
      await acao('config', { ligado: !S.e.config.ligado }, S.e.config.ligado ? 'Respostas pausadas' : 'Respondendo');
    } else if (a === 'whatsapp') {  // 0.17.0: liga e desliga o WhatsApp, como o conector MCP
      await acao('config', { whatsapp: !S.e.config.whatsapp }, S.e.config.whatsapp ? 'WhatsApp desligado' : 'WhatsApp ligado');
    } else if (a === 'tunel') {  // 1.13.0: o túnel da Cloudflare
      const on = !!(S.e.webhook && S.e.webhook.tunel && S.e.webhook.tunel.ligado);
      await acao('config', { tunel: !on }, on ? 'Túnel desligado' : 'Túnel ligado');
    } else if (a === 'mcp') {
      await acao('config', { mcp: !S.e.mcp.ligado }, S.e.mcp.ligado ? 'Conector desligado' : 'Conector ligado');
    } else if (a === 'ia-verificar') {  // a lista das IAs de novo e esquece o erro da última chamada
      await acao('ia/verificar', {}, 'Verificado');
    } else if (a === 'casa') {
      const on = !!(S.e.casa && S.e.casa.ligado);
      await acao('config', { casa: !on }, on ? 'Casa desligada' : 'Casa ligada');
    } else if (a === 'recolher') {
      await acao('config', { recolher: Number(el.dataset.v) }, 'Salvo');
    } else if (a === 'apagar-dias') {  // 1.7.0
      const n = Number(el.dataset.v);
      await acao('config', { apagar_dias: n }, n ? `As conversas sem uso por ${n} dias saem sozinhas` : 'As conversas ficam guardadas');
      S.ch.lista = undefined;
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
    } else if (a === 'cheia') {
      cheia(!S.cheia);
    } else if (a === 'conversa-abrir') {
      abrirConversa();
    } else if (a === 'conversa-recolher') {
      recolher();
    } else if (a === 'conversa-fixar') {
      guardar('correria-conversa-fixa', fixa() ? '' : '1');
      armarRecolher();
      render();
    } else if (a === 'opcoes' || a === 'sobre' || a === 'mais') {
      abrirTela(a);
    } else if (a === 'lado-ir') {  // 1.8.0: Conversa e Mais, na barra lateral
      abrirTela(el.dataset.v);
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
      Object.assign(S.ch, { rapidas: false, editando: null });
      enviarConversa(el.dataset.v);
    } else if (a === 'ch-resp') {  // 1.10.0: o Sim ou o Não de uma mudança, num toque
      enviarConversa(el.dataset.v);
    } else if (a === 'ch-rapidas') {
      Object.assign(S.ch, { rapidas: !(S.ch.rapidas || S.ch.editando), editando: null, menu: false }); render();
    } else if (a === 'ch-ed-abrir') {
      Object.assign(S.ch, { editando: { lista: perguntas(S.e).lista.slice(), rascunho: '' }, menu: false }); render();
    } else if (a === 'ch-ed-dobra') {
      edDobrar(el.dataset.v); render();
    } else if (a === 'ch-ed-por') {
      if (!S.ch.editando.lista.includes(el.dataset.v)) S.ch.editando.lista.push(el.dataset.v);
      render();
    } else if (a === 'ch-ed-tirar') {
      S.ch.editando.lista.splice(Number(el.dataset.v), 1); render();
    } else if (a === 'ch-ed-add') {
      perguntaNova();
    } else if (a === 'ch-ed-padrao') {
      guardarPerguntas(null);
      S.ch.editando = { lista: perguntas(S.e).pad.slice(), rascunho: '' }; render();
    } else if (a === 'ch-ed-pronto') {
      // uma pergunta mudada vale como ficou; uma apagada até ficar vazia sai
      const ed = S.ch.editando, t = (ed.rascunho || '').trim(), lista = ed.lista.map(q => String(q || '').trim()).filter(Boolean).concat(t ? [t] : []);
      guardarPerguntas(lista.join('\n') === perguntas(S.e).pad.join('\n') ? null : lista);  // as dos apps: seguem os apps
      S.ch.editando = null; render();
    } else if (a === 'ch-menu') {
      S.ch.menu = !S.ch.menu; if (S.ch.menu) S.ch.rapidas = false; render();
    } else if (a === 'ch-galeria') {
      S.ch.menu = false; render();
      $('#ch-galeria').click();
    } else if (a === 'ch-anexar') {
      S.ch.menu = false; render();
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
        Object.assign(S.ch, { msgs: r.mensagens || [], conversa: r.conversa || null, lista: r.conversas, texto: a === 'ch-nova' ? '' : S.ch.texto, anexo: null, rapidas: false, menu: false });
        // 1.8.0: pela barra lateral, de outra tela, abre a Conversa
        if (S.tela === 'conversas') voltar(); else if (S.tela && lateral()) abrirTela(''); else render();
        if (a === 'ch-nova') setTimeout(() => { const t = $('#ch-txt'); if (t) t.focus(); }, 60);
      } catch (err) { toast(err.message); if (a === 'conv-abrir') carregarLista(); }
    } else if (a === 'conv-apagar') {
      try {
        const r = await api.post('conversa/apagar', { id: el.dataset.v });
        Object.assign(S.ch, { msgs: r.mensagens || [], conversa: r.conversa || null, lista: r.conversas || [] });
        render(); toast('Conversa apagada');
      } catch (err) { toast(err.message); }
    } else if (a === 'ch-camera') {
      S.ch.menu = false; render();
      abrirCamera();
    } else if (a === 'cam-fechar') {
      fecharCamera();
    } else if (a === 'cam-foto') {
      camFoto();
    } else if (a === 'cam-galeria') {
      fecharCamera();
      const inp = $('#ch-foto'); if (inp) inp.click();
    } else if (a === 'uso-dia') {  // Uso da IA: o dia da barra tocada
      S.usoDia = el.dataset.v; render();
    } else if (a === 'limpar') {
      await acao('registro/limpar', { canal: el.dataset.v }, el.dataset.v === 'mcp' ? 'Mudanças apagadas' : 'Mensagens apagadas');
    }
  });
  // Últimas chamadas aberta continua aberta quando a tela se redesenha (a cada poucos segundos)
  document.addEventListener('toggle', ev => {
    if (!ev.target.classList) return;
    if (ev.target.classList.contains('mudancas')) S.mudAberto = ev.target.open;
    else if (ev.target.classList.contains('uso-ult')) S.usoAberto = ev.target.open;
  }, true);
  document.addEventListener('input', ev => {
    const el = ev.target;
    if (el.dataset.f) S.form[el.dataset.f] = el.value;
    if (el.id === 'ch-ed-txt' && S.ch.editando) S.ch.editando.rascunho = el.value;
    if (el.dataset.edI != null && S.ch.editando) S.ch.editando.lista[Number(el.dataset.edI)] = el.value;  // 1.12.0: mudar uma pergunta
    if (el.id === 'ch-txt') {
      S.ch.texto = el.value; el.style.height = 'auto'; el.style.height = Math.min(el.scrollHeight, 140) + 'px';
      const b = $('#ch-pri'), novo = botaoPri(S.e);  // o microfone vira Enviar ao escrever (e volta com a caixa vazia)
      if (b && !novo.includes(`data-a="${b.dataset.a}"`)) b.outerHTML = novo;
    }
  });
  /* 1.4.1: o Enter envia (o Shift+Enter quebra a linha, como no WhatsApp Web, no Telegram e no Slack) quando há um
     teclado de verdade: um computador (um mouse ou um touchpad), ou uma tecla de letra que não veio do teclado da tela
     (o do Android manda 229). No celular, o Enter do teclado da tela quebra a linha. */
  let teclaDeVerdade = false;
  document.addEventListener('keydown', ev => { if (ev.key && ev.key.length === 1 && ev.keyCode !== 229 && !ev.isComposing) teclaDeVerdade = true; }, true);
  const comTeclado = () => teclaDeVerdade || matchMedia('(any-hover: hover), (any-pointer: fine)').matches;
  document.addEventListener('keydown', ev => {
    // 1.4.0: Ctrl+Espaço abre a Conversa e, aberta, recolhe (na Tela cheia; fora dela, o cursor vai para a caixa)
    if (ev.ctrlKey && !ev.altKey && !ev.metaKey && (ev.code === 'Space' || ev.key === ' ')) {
      ev.preventDefault();
      if (S.cheia) return alternarConversa();
      const t = $('#ch-txt'); if (t) t.focus();
      return;
    }
    // Tela cheia: o Esc sai (a câmera e o menu do anexo fecham antes, pelo Esc deles)
    if (ev.key === 'Escape' && S.cheia && !CAM && !S.ch.menu) { cheia(false); return; }
    if ((ev.key === 'Enter' || ev.key === ' ') && ev.target.matches && ev.target.matches('.rot[data-dobra]')) { ev.preventDefault(); return dobrar(ev.target); }
    // com teclado, Enter envia (Shift+Enter quebra a linha); no celular, o botão Enviar
    if (ev.key === 'Enter' && !ev.shiftKey && !ev.isComposing && ev.target.id === 'ch-txt' && comTeclado()) { ev.preventDefault(); enviarConversa(); }
    if (ev.key === 'Enter' && !ev.isComposing && ev.target.id === 'ch-ed-txt') { ev.preventDefault(); perguntaNova(); }
    if (ev.key === 'Enter' && !ev.isComposing && ev.target.dataset && ev.target.dataset.edI != null) { ev.preventDefault(); ev.target.blur(); }
  });
  document.addEventListener('change', async ev => {
    const el = ev.target;
    if (el.id === 'ch-arquivo' || el.id === 'ch-foto' || el.id === 'ch-galeria') {  // a foto ou o PDF da conversa
      const f = el.files && el.files[0];
      el.value = '';
      if (!f) return;
      if (f.size > 15 * 1024 * 1024) return toast('O arquivo é grande demais (até 15 MB).');
      const b64 = await new Promise((ok2, erro) => { const r = new FileReader(); r.onload = () => ok2(r.result); r.onerror = erro; r.readAsDataURL(f); });
      S.ch.anexo = { nome: f.name || 'Foto', b64 };
      render();
      return;
    }
    if (el.matches('[data-ia-ent]')) {  // 0.16.0: a IA para conversar
      const x = ((S.e.ias || {}).lista || []).find(o => o.id === el.value);
      await acao('config', { ia_entidade: el.value }, 'IA para conversar: ' + (x ? x.nome : 'a padrão do Home Assistant'));
      return;
    }
    if (el.matches('[data-ia-pesq]')) {  // 1.6.0: a IA para pesquisar na internet
      const x = ((S.e.ias || {}).lista || []).find(o => o.id === el.value);
      await acao('config', { ia_pesquisa: el.value }, 'IA para pesquisar na internet: ' + (x ? x.nome : 'igual à de conversar'));
      return;
    }
    if (['numero_id', 'token', 'segredo'].includes(el.dataset.f)) {  // 0.17.0: salva ao sair do campo (sem o botão Salvar)
      if (el.dataset.f !== 'numero_id' && !el.value.trim()) return;  // o token e a chave vazios: fica o que estava
      const r = await acao('config', { [el.dataset.f]: el.value }, 'Salvo');
      if (r) { S.form[el.dataset.f] = el.dataset.f === 'numero_id' ? null : ''; render(); if (r.pronto) await acao('conferir', {}, null).then(x => x && x.conta && toast('Conferido com a Meta')); }
      return;
    }
    if (el.dataset.f === 'endereco' || el.dataset.f === 'endereco_mcp') {  // 1.14.0: o do webhook e o do conector, cada um o seu
      const r = await acao('config', { [el.dataset.f]: el.value }, 'Endereço salvo');
      if (r) S.form[el.dataset.f] = null;
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
