"""CorrerIA: junta os apps da CorrerIA Code no WhatsApp (a API oficial da Meta), no Claude e no Gemini (MCP).
Cada app publica as suas ferramentas (share/<app>/correria.json); no WhatsApp e na conversa da tela, a IA do Home
Assistant usa essas ferramentas (ia.py) e as mudanças só acontecem depois do "sim" da pessoa; o Claude e o Gemini
chamam as mesmas ferramentas pelo MCP (mcp.py), com o login aprovado no painel (oauth.py).

Dois servidores (só biblioteca padrão do Python):
- a tela, pelo painel do Home Assistant (ingress, porta 8099): configuração, quem conversa, os apps, o Claude e o Gemini
  e as últimas mensagens;
- a porta pública (8443, https com o certificado do Duck DNS em /ssl): o webhook da Meta (/webhook, com a assinatura
  conferida) e, com o Claude e o Gemini ligados, o MCP (/mcp) e o login (/.well-known/*, /registrar, /autorizar,
  /token); o resto responde 404.
"""
import base64
import json
import mimetypes
import os
import re
import secrets
import socket
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import apps
import fala
import ferramentas
import ia
import mcp
import oauth
import uso
import whatsapp

def ler_versao():
    """A versão fica num lugar só, o config.yaml do app: no contêiner, ao lado do server.py (o Dockerfile copia); no
    computador, na pasta de cima."""
    aqui = os.path.dirname(os.path.abspath(__file__))
    for arq in (os.path.join(aqui, "config.yaml"), os.path.join(aqui, "..", "config.yaml")):
        try:
            with open(arq, encoding="utf-8") as f:
                m = re.search(r'^version:\s*"?([\d.]+)', f.read(), re.M)
            if m:
                return m.group(1)
        except OSError:
            pass
    return "0"


VERSAO = ler_versao()
DATA_DIR = os.environ.get("CORRERIA_DATA", "/data")
SHARE_DIR = os.environ.get("CORRERIA_SHARE", "/share")
SSL_DIR = os.environ.get("CORRERIA_SSL", "/ssl")
PORTA = int(os.environ.get("CORRERIA_PORTA", "8099"))
PORTA_WEBHOOK = int(os.environ.get("CORRERIA_PORTA_WEBHOOK", "8443"))
WWW = os.path.join(os.path.dirname(os.path.abspath(__file__)), "www")
DEV = os.environ.get("CORRERIA_DEV") == "1"            # no computador: a tela sem o painel e Ana e Beto de exemplo
LOG_HTTP = os.environ.get("CORRERIA_LOG_HTTP") != "0"   # no computador, cada pedido no registro (os testes desligam)
TOKEN = os.environ.get("SUPERVISOR_TOKEN")
HA_API = os.environ.get("CORRERIA_HA_API", "http://supervisor/core/api")
GRAPH = os.environ.get("CORRERIA_GRAPH", whatsapp.GRAPH)
PERMITIDOS = {"172.30.32.2", "127.0.0.1", "::1"}  # o painel do Home Assistant (ingress)
CONFIG_ARQ = os.path.join(DATA_DIR, "config.json")
USO = uso.Uso(os.path.join(DATA_DIR, "uso_ia.json"))  # Uso da IA: as chamadas da IA do WhatsApp e da tela
CANAL = threading.local()  # o canal da pergunta que está na IA agora (whatsapp ou conversa), para o Uso da IA
CONVERSAS_ARQ = os.path.join(DATA_DIR, "conversas.json")
MCP_ARQ = os.path.join(DATA_DIR, "mcp.json")
PENDENTE_VALE = 30 * 60       # uma mudança proposta espera o "sim" por até 30 minutos
MAX_MCP = 1024 * 1024
MAX_CORPO = 3 * 1024 * 1024   # a Meta manda até 3 MB
MAX_HISTORICO = 16            # as últimas mensagens de cada pessoa que vão junto com a pergunta
HORAS_CONVERSA = 12           # depois disso, a conversa recomeça
MAX_REGISTRO = 60             # as últimas mensagens que a tela mostra
PESSOA_RE = re.compile(r"^person\.[a-z0-9_]+$")

TRAVA = threading.Lock()
_travas_numero = defaultdict(threading.Lock)  # uma pergunta de cada vez por pessoa (a conversa fica na ordem)
ESTADO = {"ultimo_webhook": None, "verificado_em": None, "conta": None, "conta_em": None, "ia": None}


def log(*a):
    print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), *a, flush=True)


def agora_iso():
    return datetime.now().isoformat(timespec="seconds")


def gravar_arquivo(caminho, conteudo):
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    tmp = caminho + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(conteudo)
        f.flush()
        os.fsync(f.fileno())
    os.chmod(tmp, 0o600)
    os.replace(tmp, caminho)


def ler_json(caminho):
    try:
        with open(caminho, encoding="utf-8") as f:
            v = json.load(f)
        return v if isinstance(v, dict) else {}
    except (OSError, ValueError):
        return {}


# ---------------------------------------------------------------- configuração

def ler_config():
    c = ler_json(CONFIG_ARQ)
    out = {"numero_id": str(c.get("numero_id") or ""), "token": str(c.get("token") or ""), "segredo": str(c.get("segredo") or ""),
           "verificacao": str(c.get("verificacao") or ""), "endereco": str(c.get("endereco") or ""), "ligado": c.get("ligado") is not False,
           "mcp": c.get("mcp") is True,
           # a cor do app, da casa toda (como nos outros apps): uma das 12 da família; a Cor do dia, ligada até desligar
           "cor": c.get("cor") if c.get("cor") in CORES else "", "cor_dia": c.get("cor_dia") is not False,
           "pessoas": {k: whatsapp.so_digitos(v) for k, v in (c.get("pessoas") or {}).items() if PESSOA_RE.match(str(k)) and whatsapp.so_digitos(v)}}
    if len(out["verificacao"]) < 16:  # o token de verificação que a Meta manda de volta ao cadastrar o webhook
        out["verificacao"] = secrets.token_urlsafe(18)
        gravar_config(out)
    return out


CORES = ("vermelho", "coral", "laranja", "ouro", "verde", "menta", "turquesa", "azul", "indigo", "lilas", "rosa", "grafite")


def gravar_config(c):
    gravar_arquivo(CONFIG_ARQ, json.dumps(c, ensure_ascii=False, indent=1))


def _fim(segredo):
    return ("••••" + segredo[-4:]) if len(segredo) >= 8 else ("••••" if segredo else "")


def limpar_endereco(e):
    """O endereço público (https://casa-exemplo.duckdns.org:8443), sem /webhook nem barra no fim."""
    e = str(e or "").strip()
    if not e:
        return ""
    if not re.match(r"^https?://", e):
        e = "https://" + e
    u = urllib.parse.urlparse(e)
    if not u.hostname or " " in e:
        raise ValueError("Endereço inválido. Ex.: https://casa-exemplo.duckdns.org:8443")
    caminho = re.sub(r"/webhook/?$", "", u.path.rstrip("/"))
    return f"{u.scheme}://{u.netloc}{caminho}"


def salvar_config(corpo):
    with TRAVA:
        c = ler_config()
        if "numero_id" in corpo:
            n = whatsapp.so_digitos(corpo.get("numero_id"))
            if corpo.get("numero_id") and not n:
                raise ValueError("O ID do número de telefone tem só números.")
            c["numero_id"] = n
        for k in ("token", "segredo"):
            v = str(corpo.get(k) or "").strip()
            if v:  # vazio: fica o que estava (a tela nunca recebe o valor de volta)
                if len(v) < 8 or " " in v:
                    raise ValueError("Esse token parece incompleto." if k == "token" else "Essa chave secreta parece incompleta.")
                c[k] = v
        if "endereco" in corpo:
            c["endereco"] = limpar_endereco(corpo.get("endereco"))
        if "ligado" in corpo:
            c["ligado"] = corpo.get("ligado") is not False
        if "mcp" in corpo:
            c["mcp"] = corpo.get("mcp") is True
        if "cor" in corpo:  # escolher uma cor desliga a Cor do dia (a tela manda os dois)
            if corpo.get("cor") not in CORES:
                raise ValueError("Cor desconhecida.")
            c["cor"] = corpo.get("cor")
        if "cor_dia" in corpo:
            c["cor_dia"] = corpo.get("cor_dia") is not False
        gravar_config(c)
    if any(k in corpo for k in ("numero_id", "token")):
        ESTADO.update(conta=None, conta_em=None)
    return c


def salvar_pessoa(pid, numero):
    pid = str(pid or "")
    if not PESSOA_RE.match(pid):
        raise ValueError("Pessoa inválida.")
    n = whatsapp.so_digitos(numero)
    if n and not 10 <= len(n) <= 15:
        raise ValueError("Número inválido. Use o código do país e o DDD: 55 11 99999-0000.")
    if n and len(n) in (10, 11):
        n = "55" + n  # sem o código do país: Brasil
    with TRAVA:
        c = ler_config()
        outro = next((k for k, v in c["pessoas"].items() if k != pid and whatsapp.mesmo_numero(v, n)), None)
        if n and outro:
            raise ValueError("Esse número já é de outra pessoa.")
        if n:
            c["pessoas"][pid] = n
        else:
            c["pessoas"].pop(pid, None)
        gravar_config(c)


def conta(c=None):
    c = c or ler_config()
    return whatsapp.WhatsApp(c["numero_id"], c["token"], GRAPH)


def conferir_conta():
    """Confere o ID e o token na Meta: o número e o nome que aparecem no WhatsApp."""
    r = conta().conferir()
    ESTADO.update(conta=r, conta_em=agora_iso())
    return r


# ---------------------------------------------------------------- pessoas da casa (Home Assistant)

_pessoas_cache = {"t": 0.0, "v": None}


def ha_get(caminho, timeout=10):
    req = urllib.request.Request(HA_API + caminho, headers={"Authorization": f"Bearer {TOKEN}"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def pessoas_ha():
    """As pessoas do Home Assistant: [{id, nome, usuario}] (usuario: o login dela no Home Assistant, para a conversa da
    tela). Fora dele (no computador), Ana e Beto de exemplo."""
    if not TOKEN:
        return [{"id": "person.ana", "nome": "Ana", "usuario": "u-ana"}, {"id": "person.beto", "nome": "Beto", "usuario": "u-beto"}] if DEV else []
    if _pessoas_cache["v"] is not None and time.time() - _pessoas_cache["t"] < 60:
        return _pessoas_cache["v"]
    try:
        estados = ha_get("/states")
        v = sorted(({"id": s["entity_id"], "nome": (s.get("attributes") or {}).get("friendly_name") or s["entity_id"][7:],
                     "usuario": str((s.get("attributes") or {}).get("user_id") or "")}
                    for s in estados if isinstance(s, dict) and str(s.get("entity_id", "")).startswith("person.")), key=lambda p: p["nome"].lower())
    except (urllib.error.URLError, OSError, ValueError) as e:
        log("Não consegui ver as pessoas do Home Assistant:", e)
        return _pessoas_cache["v"] or []
    _pessoas_cache.update(t=time.time(), v=v)
    return v


def pessoa_do_numero(numero, c=None):
    """Quem é esse número (só as pessoas com número cadastrado conversam): {id, nome} ou None."""
    c = c or ler_config()
    pid = next((k for k, v in c["pessoas"].items() if whatsapp.mesmo_numero(v, numero)), None)
    if not pid:
        return None
    nome = next((p["nome"] for p in pessoas_ha() if p["id"] == pid), None) or pid[7:].replace("_", " ").title()
    return {"id": pid, "nome": nome}


# ---------------------------------------------------------------- conversas e registro

def ler_conversas():
    c = ler_json(CONVERSAS_ARQ)
    return {"conversas": c.get("conversas") if isinstance(c.get("conversas"), dict) else {},
            "ultimo_app": c.get("ultimo_app") if isinstance(c.get("ultimo_app"), dict) else {},
            "vistos": [x for x in c.get("vistos") or [] if isinstance(x, str)][-500:],
            "registro": [x for x in c.get("registro") or [] if isinstance(x, dict)][:MAX_REGISTRO],
            "tela": c.get("tela") if isinstance(c.get("tela"), dict) else {},  # a conversa da tela, de cada login
            "pendentes": c.get("pendentes") if isinstance(c.get("pendentes"), dict) else {}}  # mudanças esperando o "sim"


def _gravar_conversas(c):
    gravar_arquivo(CONVERSAS_ARQ, json.dumps(c, ensure_ascii=False))


def ja_vista(msg_id):
    """A Meta pode mandar a mesma mensagem de novo: cada uma é respondida uma vez só."""
    with TRAVA:
        c = ler_conversas()
        if msg_id in c["vistos"]:
            return True
        c["vistos"] = (c["vistos"] + [msg_id])[-500:]
        _gravar_conversas(c)
        return False


def registrar(tipo, quem, texto, app=""):
    """O que a tela mostra em Últimas mensagens: recebida, enviada, bloqueada (número sem cadastro), erro."""
    with TRAVA:
        c = ler_conversas()
        c["registro"].insert(0, {"em": agora_iso(), "tipo": tipo, "quem": str(quem or "")[:60], "texto": str(texto or "")[:300], "app": app})
        c["registro"] = c["registro"][:MAX_REGISTRO]
        _gravar_conversas(c)


def historico(numero):
    """As últimas mensagens dessa pessoa (de até 12 horas atrás), para a IA lembrar da conversa."""
    limite = (datetime.now() - timedelta(hours=HORAS_CONVERSA)).isoformat(timespec="seconds")
    lista = ler_conversas()["conversas"].get(whatsapp.canonico(numero)) or []
    return [{"papel": m.get("papel"), "texto": m.get("texto")} for m in lista if str(m.get("em") or "") >= limite][-MAX_HISTORICO:]


def guardar_conversa(numero, pergunta, resposta, app=None):
    k = whatsapp.canonico(numero)
    with TRAVA:
        c = ler_conversas()
        lista = c["conversas"].get(k) or []
        lista += [{"papel": "eu", "texto": pergunta[:2000], "em": agora_iso()}, {"papel": "ia", "texto": resposta[:4000], "em": agora_iso()}]
        c["conversas"][k] = lista[-MAX_HISTORICO * 2:]
        if app:
            c["ultimo_app"][k] = app["app"]
        _gravar_conversas(c)


def ultimo_app(numero):
    return ler_conversas()["ultimo_app"].get(whatsapp.canonico(numero))


def mascarar(numero):
    d = whatsapp.so_digitos(numero)
    return ("+" + d[:4] + "•••" + d[-4:]) if len(d) > 8 else d


# ---------------------------------------------------------------- mensagens

APPS = apps.Apps(SHARE_DIR, log)
FALA = fala.Fala(HA_API, TOKEN, log, simulada=DEV and not TOKEN)
SO_TEXTO = "Por enquanto eu entendo texto, áudio, foto e PDF."
NAO_LE = "Esse tipo de arquivo eu ainda não leio. Mande uma foto ou um PDF."
ROTULO = {"image": "foto", "document": "arquivo", "audio": "áudio"}
SEM_APP = "Ainda não há app ligado por aqui. Em cada app, ligue Mais › Configurações › Integrações › CorrerIA."
FERR = ferramentas.Ferramentas(lambda: APPS, log)  # o APPS de agora (os testes trocam)
SIM_RE = re.compile(r"^\s*(sim|s|ss|pode|pode sim|pode fazer|ok|okay|confirmo|confirma|confirmado|isso|isso mesmo|manda|faz|faça|beleza|blz|certo|claro|bora|fechado)\s*[.!]*\s*$", re.I)
NAO_RE = re.compile(r"^\s*(n|nao|não|cancela|cancelar|deixa|deixa pra l[aá]|esquece|nada)\b", re.I)


# ---------------------------------------------------------------- a IA do Home Assistant com as ferramentas dos apps

def ha_post(caminho, corpo, timeout=20):
    req = urllib.request.Request(HA_API + caminho, data=json.dumps(corpo).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read() or b"{}")


def chamar_ia(instrucoes):
    """A IA do Home Assistant (ai_task.generate_data, a entidade padrão de Configurações › Sistema › IA)."""
    if not TOKEN:
        raise ia.ErroIA("Sem o Home Assistant.")
    comeco, tipo = time.time(), getattr(CANAL, "tipo", "conversa")
    try:
        dados = _chamar_ia(instrucoes)
    except ia.ErroIA as e:
        USO.registrar(tipo, len(instrucoes), 0, time.time() - comeco, str(e))
        raise
    USO.registrar(tipo, len(instrucoes), len(json.dumps(dados, ensure_ascii=False)), time.time() - comeco)
    return dados


def _chamar_ia(instrucoes):
    try:
        r = ha_post("/services/ai_task/generate_data?return_response", {"task_name": "CorrerIA", "instructions": instrucoes}, timeout=150)
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read() or b"{}").get("message")
        except (ValueError, AttributeError):
            msg = None
        ESTADO["ia"] = {"ok": False, "erro": msg or f"O Home Assistant respondeu {e.code}.", "em": agora_iso()}
        raise ia.ErroIA(ESTADO["ia"]["erro"]) from None
    except (urllib.error.URLError, OSError, ValueError) as e:
        ESTADO["ia"] = {"ok": False, "erro": f"Não consegui falar com o Home Assistant ({getattr(e, 'reason', e)}).", "em": agora_iso()}
        raise ia.ErroIA(ESTADO["ia"]["erro"]) from None
    dados = ((r or {}).get("service_response") or {}).get("data")
    if dados is None:
        ESTADO["ia"] = {"ok": False, "erro": "A IA não devolveu resposta.", "em": agora_iso()}
        raise ia.ErroIA(ESTADO["ia"]["erro"])
    ESTADO["ia"] = {"ok": True, "erro": "", "em": agora_iso()}
    return dados


AGENTE = ia.Agente(FERR, chamar_ia, log, simulada=DEV and not TOKEN)


def pegar_pendente(chave):
    """A mudança que espera o "sim" dessa conversa (sai da lista: vale uma resposta só)."""
    with TRAVA:
        c = ler_conversas()
        p = c["pendentes"].pop(chave, None)
        if p is not None:
            _gravar_conversas(c)
    if not p or not isinstance(p.get("acoes"), list) or str(p.get("em") or "") < (datetime.now() - timedelta(seconds=PENDENTE_VALE)).isoformat(timespec="seconds"):
        return None
    return p["acoes"]


def guardar_pendente(chave, acoes):
    with TRAVA:
        c = ler_conversas()
        if acoes:
            c["pendentes"][chave] = {"em": agora_iso(), "acoes": acoes}
        else:
            c["pendentes"].pop(chave, None)
        _gravar_conversas(c)


def executar(acoes, pessoa, cliente):
    """O "sim": faz cada mudança proposta, pelas ferramentas dos apps. Devolve (texto, nomes dos apps)."""
    lista, linhas, nomes = FERR.todas(), [], []
    for a in acoes:
        f = FERR.achar(str(a.get("ferramenta") or ""), lista)
        if not f:
            linhas.append(f"- Não deu: {a.get('resumo') or a.get('ferramenta')} (o app não está mais ligado).")
            continue
        texto, erro = FERR.usar(f, a.get("argumentos") or {}, pessoa, cliente)
        linhas.append(f"- {'Não deu: ' if erro else ''}{texto.splitlines()[0] if texto else 'feito.'}")
        if f["app"]["nome"] not in nomes:
            nomes.append(f["app"]["nome"])
        if erro:
            registrar("erro", f["app"]["nome"], texto)
    ok = all(not x.startswith("- Não deu") for x in linhas)
    return ("Feito!\n" if ok else "") + "\n".join(linhas), nomes


def responder_ia(chave, texto, hist, pessoa, canal, cliente):
    """A pergunta pela IA do Home Assistant com as ferramentas dos apps: (resposta, nomes dos apps) ou None (nenhum app
    com ferramentas, ou a IA fora do ar com um app que responde sozinho: vai pelo caminho antigo)."""
    pend = pegar_pendente(chave)
    if pend:
        if SIM_RE.match(texto):
            return executar(pend, pessoa, cliente)
        if NAO_RE.match(texto):
            return "Tudo bem, não mudei nada.", []
    if not any(a["ferramentas"] for a in APPS.lista()):
        return None
    CANAL.tipo = "whatsapp" if canal == "whatsapp" else "conversa"
    try:
        r = AGENTE.responder(hist + [{"papel": "eu", "texto": texto}], pessoa, canal, cliente)
    except ia.ErroIA as e:
        log("IA:", e)
        if any(a["rota"] for a in APPS.lista()):
            return None
        return f"A IA do Home Assistant não respondeu agora ({str(e).rstrip('.')}). Tente de novo daqui a pouco.", []
    if r["pendente"]:
        guardar_pendente(chave, r["pendente"])
    return r["resposta"], r["apps"]


def responder_pergunta(texto, pessoa, numero=None):
    """A pergunta vai para a IA com as ferramentas dos apps (ou, sem nenhum app com ferramentas, para o app do assunto
    que responde com a IA dele); devolve (resposta, app). Serve para o WhatsApp."""
    hist = historico(numero) if numero else []
    r = responder_ia("wa:" + whatsapp.canonico(numero) if numero else "wa:", texto, hist, pessoa, "whatsapp", "WhatsApp")
    if r is not None:
        return r[0], {"app": "_ia", "nome": ", ".join(r[1]) or "CorrerIA"}
    app = APPS.escolher(texto, ultimo_app(numero) if numero else None)
    if not app:
        return SEM_APP, None
    try:
        return APPS.perguntar(app, texto, hist, pessoa), app
    except apps.ErroApp as e:
        registrar("erro", app["nome"], str(e))
        log("CorrerIA:", e)
        return f"Não consegui falar com o {app['nome']} agora. Tente de novo daqui a pouco.", app


def enviar(wa, para, pessoa, texto, app=None):
    try:
        wa.texto(para, texto)
        registrar("enviada", pessoa["nome"], whatsapp.para_whatsapp(texto), app["nome"] if app else "")
    except whatsapp.ErroWhatsApp as e:
        registrar("erro", "WhatsApp", str(e))
        log("WhatsApp:", e)


def tratar(m, nome_perfil, c):
    """Uma mensagem recebida: confere quem mandou, marca como lida, pergunta ao app e responde."""
    if ja_vista(m["id"]):
        return
    de = str(m["from"])
    texto = whatsapp.texto_da_mensagem(m)
    pessoa = pessoa_do_numero(de, c)
    if not pessoa:
        registrar("bloqueada", nome_perfil or mascarar(de), texto if texto is not None else f"[{m.get('type')}]")
        log("WhatsApp: mensagem de um número sem cadastro (", mascarar(de), ")")
        return
    if not c["ligado"]:
        registrar("recebida", pessoa["nome"], (texto or f"[{m.get('type')}]") + " (respostas pausadas)")
        return
    wa = conta(c)
    with _travas_numero[whatsapp.canonico(de)]:
        try:
            wa.lida(m["id"])
        except whatsapp.ErroWhatsApp:
            pass  # sem os tracinhos azuis: a resposta vai do mesmo jeito
        tipo = m.get("type")
        if tipo in ("image", "document"):
            return tratar_anexo(wa, m, de, pessoa)
        if tipo == "audio":
            try:
                bruto, _ = wa.midia((m.get("audio") or {}).get("id"))
                texto = FALA.texto(bruto)
            except (whatsapp.ErroWhatsApp, fala.ErroFala) as e:
                registrar("recebida", pessoa["nome"], "[áudio]")
                return enviar(wa, de, pessoa, f"Não consegui ouvir o áudio: {str(e).rstrip('.')}. Escreva a pergunta, por favor.")
            registrar("recebida", pessoa["nome"], f"[áudio] {texto}")
            return responder_texto(wa, de, pessoa, texto, ja_registrada=True)
        if texto is None:
            registrar("recebida", pessoa["nome"], f"[{tipo}]")
            return enviar(wa, de, pessoa, SO_TEXTO)
        return responder_texto(wa, de, pessoa, texto)


def responder_texto(wa, de, pessoa, texto, ja_registrada=False):
    """Uma pergunta em texto (ou o que a pessoa disse no áudio): vai para o app do assunto e a resposta volta."""
    texto = texto.strip()[:2000]
    if not texto:
        return
    if not ja_registrada:
        registrar("recebida", pessoa["nome"], texto)
    resposta, app = responder_pergunta(texto, pessoa, de)
    if app:
        guardar_conversa(de, texto, resposta, app)
    enviar(wa, de, pessoa, resposta, app)


def tratar_anexo(wa, m, de, pessoa):
    """Uma foto ou um documento (PDF): vai para o app do assunto que lê esse tipo (pela legenda, pela última conversa
    ou o primeiro), junto com a legenda; o app lê com a IA e responde."""
    tipo = m.get("type")
    info = m.get(tipo) or {}
    legenda = str(info.get("caption") or "").strip()[:2000]
    mime = str(info.get("mime_type") or "").split(";")[0].strip().lower()
    nome = str(info.get("filename") or "")[:120]
    rot = ROTULO.get(tipo, tipo)
    registrar("recebida", pessoa["nome"], f"[{rot}] {legenda}".strip())
    app = APPS.escolher(legenda, ultimo_app(de), tipo=mime)
    if not app:
        return enviar(wa, de, pessoa, NAO_LE if APPS.lista() else SEM_APP)
    guardar_pendente("wa:" + whatsapp.canonico(de), None)  # uma foto no meio desfaz a mudança que esperava o sim
    try:
        bruto, tipo_meta = wa.midia(info.get("id"))
    except whatsapp.ErroWhatsApp as e:
        registrar("erro", "WhatsApp", str(e))
        return enviar(wa, de, pessoa, f"Não consegui pegar o arquivo: {str(e).rstrip('.')}. Mande de novo, por favor.")
    anexo = {"tipo": tipo_meta or mime, "nome": nome, "b64": f"data:{tipo_meta or mime};base64," + base64.b64encode(bruto).decode()}
    try:
        resposta = APPS.perguntar(app, legenda, historico(de), pessoa, timeout=300, anexo=anexo)
    except apps.ErroApp as e:
        registrar("erro", app["nome"], str(e))
        resposta = f"Não consegui falar com o {app['nome']} agora. Tente de novo daqui a pouco."
    guardar_conversa(de, f"[{rot}] {legenda}".strip(), resposta, app)
    enviar(wa, de, pessoa, resposta, app)


def receber(corpo):
    """O que a Meta mandou no webhook (já com a assinatura conferida)."""
    c = ler_config()
    for numero_id, m, nome in whatsapp.mensagens(corpo):
        if c["numero_id"] and numero_id and numero_id != c["numero_id"]:
            continue  # de outro número da mesma conta da Meta
        try:
            tratar(m, nome, c)
        except Exception as e:  # noqa: BLE001  (uma mensagem com problema não derruba as outras)
            log("WhatsApp: erro ao tratar a mensagem:", e)
            registrar("erro", "CorrerIA", str(e))
    for para, erro in whatsapp.falhas(corpo):
        registrar("erro", "WhatsApp", f"Não chegou para {(pessoa_do_numero(para, c) or {}).get('nome') or mascarar(para)}: {erro}")


# ---------------------------------------------------------------- o webhook da Meta (porta 8443)

def certificado():
    """Os arquivos do certificado (do Duck DNS ou do Let's Encrypt), se existirem."""
    for cert, chave in (("fullchain.pem", "privkey.pem"), ("cert.pem", "key.pem")):
        a, b = os.path.join(SSL_DIR, cert), os.path.join(SSL_DIR, chave)
        if os.path.isfile(a) and os.path.isfile(b):
            return a, b
    return None


class ServidorWebhook(ThreadingHTTPServer):
    """https com o certificado de /ssl (relido quando o Duck DNS renova); sem certificado, http."""
    daemon_threads = True
    _ctx, _mtime = None, None

    def contexto(self):
        cc = certificado()
        if not cc:
            return None
        mt = (os.path.getmtime(cc[0]), os.path.getmtime(cc[1]))
        if self._ctx is None or mt != self._mtime:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.minimum_version = ssl.TLSVersion.TLSv1_2
            ctx.load_cert_chain(*cc)
            self._ctx, self._mtime = ctx, mt
            log("Webhook: certificado", os.path.basename(cc[0]), "carregado")
        return self._ctx

    def get_request(self):
        conn, addr = self.socket.accept()
        try:
            ctx = self.contexto()
        except (OSError, ssl.SSLError) as e:
            log("Webhook: certificado inválido:", e)
            ctx = None
        if ctx:
            conn = ctx.wrap_socket(conn, server_side=True, do_handshake_on_connect=False)
        return conn, addr

    def handle_error(self, request, client_address):
        pass  # robôs da internet batendo na porta: sem barulho no registro


# ---------------------------------------------------------------- o conector MCP para outras IAs (na porta pública)

INSTRUCOES_MCP = ("CorrerIA: os apps da CorrerIA Code num lugar só. Cada ferramenta tem o app na frente do nome "
                  "(gerencia_..., cronologia_...). Leia antes de gravar: os ids vêm das ferramentas de leitura. Antes de uma "
                  "ferramenta que grava ou apaga, diga à pessoa o que vai ser feito. Datas no formato AAAA-MM-DD; valores em reais.")


def registrar_mcp(quem, f, args, texto, erro):
    """Uma mudança feita por uma IA conectada (MCP) vai para Últimas mensagens."""
    nome = (quem.get("pessoa") or {}).get("nome")
    registrar("erro" if erro else "mcp", quem.get("cliente") + (f" · {nome}" if nome else ""),
              (texto.splitlines()[0] if texto else f["titulo"]), f["app"]["nome"])


def avisar_pedido(p):
    """Um aviso no Home Assistant (o sino), para quem está no celular saber onde aprovar."""
    if not TOKEN:
        return
    corpo = {"notification_id": "correria_conectar", "title": "CorrerIA",
             "message": f"{p['nome']} quer se conectar aos apps. Código {p['codigo']}. Abra o CorrerIA para aprovar ou recusar."}
    threading.Thread(target=lambda: _tentar(ha_post, "/services/persistent_notification/create", corpo), daemon=True).start()


def _tentar(fn, *args):
    try:
        fn(*args)
    except (urllib.error.URLError, OSError, ValueError) as e:
        log("Home Assistant:", e)


MCP = mcp.Servidor(FERR, VERSAO, INSTRUCOES_MCP, ao_gravar=registrar_mcp)
AUT = oauth.Autorizacao(MCP_ARQ, gravar_arquivo, log, ao_pedir=avisar_pedido)


def pagina_pedido(p):
    codigo, pid = p["codigo"], json.dumps(p["id"])
    corpo = f"""<h1>Conectar o {html_esc(p['nome'])}</h1>
<p>Abra o <b>CorrerIA</b> no Home Assistant e aprove o pedido com este código:</p>
<p class="codigo" id="codigo">{codigo}</p>
<p id="msg"><span class="espera" aria-label="Esperando"><i></i><i></i><i></i></span></p>"""
    script = f"""<script>(function(){{var id={pid};function ver(){{fetch('/autorizar/estado?p='+encodeURIComponent(id),{{cache:'no-store'}})
.then(function(r){{return r.json()}}).then(function(j){{if(j.ir){{document.getElementById('msg').textContent=j.estado==='aprovado'?'Aprovado. Voltando…':'Recusado.';
location.replace(j.ir);return}}if(j.estado==='vencido'){{document.getElementById('msg').textContent='O pedido venceu. Conecte de novo.';return}}
setTimeout(ver,2000)}}).catch(function(){{setTimeout(ver,4000)}})}}setTimeout(ver,1500)}})();</script>"""
    return oauth.pagina("Conectar", corpo, script)


def html_esc(t):
    return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


class Webhook(BaseHTTPRequestHandler):
    server_version = "CorrerIA"
    sys_version = ""

    def setup(self):
        self.request.settimeout(15)
        if isinstance(self.request, ssl.SSLSocket):
            self.request.do_handshake()
        super().setup()

    def log_message(self, fmt, *args):
        if DEV and LOG_HTTP:
            log("Webhook:", self.address_string(), fmt % args)

    def caminho(self):
        return urllib.parse.urlparse(self.path).path.rstrip("/") or "/"

    def base(self):
        """O endereço como quem chamou escreveu (o Claude confere que o recurso é igual ao que a pessoa colou)."""
        host = re.sub(r"[^A-Za-z0-9.\-:\[\]]", "", self.headers.get("Host") or "") or f"localhost:{PORTA_WEBHOOK}"
        proto = "https" if isinstance(self.request, ssl.SSLSocket) else ("https" if self.headers.get("X-Forwarded-Proto") == "https" else "http")
        return f"{proto}://{host}"

    def responder(self, status, texto="", tipo="text/plain; charset=utf-8", extra=None):
        corpo = texto.encode() if isinstance(texto, str) else texto
        self.send_response(status)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(corpo)

    def json(self, status, obj, extra=None):
        self.responder(status, json.dumps(obj, ensure_ascii=False), "application/json; charset=utf-8",
                       {"Cache-Control": "no-store", **(extra or {})})

    def html(self, status, texto):
        self.responder(status, texto, "text/html; charset=utf-8", {
            "Cache-Control": "no-store", "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer",
            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'"})

    def ler_corpo(self, maximo):
        n = int(self.headers.get("Content-Length") or 0)
        if n < 0 or n > maximo:
            raise ValueError("grande demais")
        return self.rfile.read(n) if n else b""

    def mcp_ligado(self):
        return ler_config()["mcp"]

    # ---- GET
    def do_GET(self):
        p = self.caminho()
        if p == "/webhook":
            return self.get_webhook()
        if not self.mcp_ligado():
            return self.responder(404)
        if p in ("/.well-known/oauth-protected-resource", "/.well-known/oauth-protected-resource/mcp"):
            return self.json(200, oauth.Autorizacao.recurso(self.base()))
        if p in ("/.well-known/oauth-authorization-server", "/.well-known/openid-configuration",
                 "/.well-known/oauth-authorization-server/mcp", "/.well-known/openid-configuration/mcp"):
            return self.json(200, oauth.Autorizacao.servidor(self.base()))
        if p == "/autorizar":
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            try:
                return self.html(200, pagina_pedido(AUT.pedir(q, self.base())))
            except oauth.ErroOAuth as e:
                if e.ir:
                    return self.responder(302, "", extra={"Location": e.ir, "Cache-Control": "no-store"})
                return self.html(400, oauth.pagina("Não deu", f"<h1>Não deu para conectar</h1><p>{html_esc(e.descricao)}</p>"))
        if p == "/autorizar/estado":
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            return self.json(200, AUT.situacao((q.get("p") or [""])[0]))
        if p == "/mcp":
            return self.responder(405, "", extra={"Allow": "POST"})
        return self.responder(404)

    def get_webhook(self):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        modo, tok, desafio = (q.get(k, [""])[0] for k in ("hub.mode", "hub.verify_token", "hub.challenge"))
        c = ler_config()
        if modo == "subscribe" and tok and secrets.compare_digest(tok, c["verificacao"]):
            ESTADO["verificado_em"] = agora_iso()
            log("Webhook: a Meta confirmou o endereço")
            return self.responder(200, desafio)
        return self.responder(403)

    # ---- POST
    def do_POST(self):
        p = self.caminho()
        if p == "/webhook":
            return self.post_webhook()
        if not self.mcp_ligado() or p not in ("/registrar", "/token", "/mcp"):
            return self.responder(404)
        try:
            corpo = self.ler_corpo(MAX_MCP)
        except ValueError:
            return self.responder(413)
        if p == "/mcp":
            return self.post_mcp(corpo)
        try:
            if p == "/registrar":
                try:
                    dados = json.loads(corpo or b"{}")
                except ValueError:
                    raise oauth.ErroOAuth("invalid_client_metadata", "JSON inválido.") from None
                return self.json(201, AUT.registrar(dados))
            tipo = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            if tipo == "application/json":
                try:
                    form = json.loads(corpo or b"{}")
                except ValueError:
                    form = {}
                form = form if isinstance(form, dict) else {}
            else:
                form = {k: v[0] for k, v in urllib.parse.parse_qs(corpo.decode("utf-8", "replace")).items()}
            return self.json(200, AUT.trocar(form, self.headers.get("Authorization") or ""), {"Pragma": "no-cache"})
        except oauth.ErroOAuth as e:
            extra = {"WWW-Authenticate": 'Basic realm="CorrerIA"'} if e.status == 401 else {}
            return self.json(e.status, e.json(), extra)

    def post_mcp(self, corpo):
        h = self.headers.get("Authorization") or ""
        token = h[7:].strip() if h.startswith("Bearer ") else ""
        con = AUT.conexao(token)
        if not con:
            meta = f'{self.base()}/.well-known/oauth-protected-resource/mcp'
            aviso = f'Bearer resource_metadata="{meta}"' + (', error="invalid_token"' if token else "")
            return self.json(401, {"erro": "Conecte pelo CorrerIA (aprovado no Home Assistant)."}, {"WWW-Authenticate": aviso})
        status, resp = MCP.http(corpo, {"pessoa": con.get("pessoa") or {}, "cliente": con.get("nome") or "MCP"})
        if resp is None:
            return self.responder(status)
        return self.json(status, resp)

    def post_webhook(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0 or n > MAX_CORPO:
            return self.responder(413 if n > MAX_CORPO else 400)
        corpo = self.rfile.read(n)
        c = ler_config()
        if not whatsapp.assinatura_ok(c["segredo"], corpo, self.headers.get("X-Hub-Signature-256")):
            log("Webhook: assinatura inválida" + ("" if c["segredo"] else " (falta a chave secreta do aplicativo)"))
            return self.responder(401)
        try:
            dados = json.loads(corpo)
        except ValueError:
            return self.responder(400)
        ESTADO["ultimo_webhook"] = agora_iso()
        self.responder(200, "ok")  # a Meta quer o 200 logo; a resposta vai depois, pela API
        threading.Thread(target=receber, args=(dados,), daemon=True).start()

    def do_DELETE(self):
        if self.caminho() == "/mcp" and self.mcp_ligado():
            return self.responder(405, "", extra={"Allow": "POST"})
        self.responder(404)

    def do_HEAD(self):
        self.responder(404)

    do_PUT = do_PATCH = do_OPTIONS = do_HEAD


# ---------------------------------------------------------------- a tela (porta 8099, pelo painel)

def atalho(host=None):
    """O caminho deste app no Home Assistant (/app/<slug>), para o Atalho no celular (Configurações › Aparência): pelo nome
    do contêiner (a1b2c3d4-correria → /app/a1b2c3d4_correria). CORRERIA_HOST troca o nome (testes); fora do Home
    Assistant, None (o cartão não aparece)."""
    host = host if host is not None else (os.environ.get("CORRERIA_HOST") or socket.gethostname())
    return "/app/" + host.replace("-", "_") if re.fullmatch(r"[a-z0-9]+-correria", host or "") else None


def estado():
    c = ler_config()
    nums = c["pessoas"]
    pessoas = [{"id": p["id"], "nome": p["nome"], "numero": nums.get(p["id"], "")} for p in pessoas_ha()]
    pessoas += [{"id": k, "nome": k[7:].replace("_", " ").title(), "numero": v, "fora": True} for k, v in nums.items() if k not in {p["id"] for p in pessoas}]
    cc = certificado()
    lista = APPS.publicos()
    todas = FERR.todas()
    for a in lista:  # o que cada app faz pelo CorrerIA: quantas ferramentas (e quantas gravam)
        fs = [f for f in todas if f["app"]["app"] == a["app"] and f["nome"] != ferramentas.PERGUNTAR]
        a.update(ferramentas=len(fs), gravam=sum(1 for f in fs if f["grava"]), erro=FERR.erros.get(a["app"], ""))
    return {
        "versao": VERSAO,
        "config": {"numero_id": c["numero_id"], "token": _fim(c["token"]), "segredo": _fim(c["segredo"]), "verificacao": c["verificacao"],
                   "endereco": c["endereco"], "webhook": (c["endereco"] + "/webhook") if c["endereco"] else "", "ligado": c["ligado"]},
        "mcp": {"ligado": c["mcp"], "url": (c["endereco"] + "/mcp") if c["endereco"] else "", "pedidos": AUT.abertos() if c["mcp"] else [],
                "conexoes": AUT.conexoes()},
        "ia": ESTADO["ia"] or {"ok": None, "erro": "", "em": None, "simulada": AGENTE.simulada},
        "pronto": bool(c["numero_id"] and c["token"] and c["segredo"]),
        "conta": ESTADO["conta"],
        "webhook": {"https": bool(cc), "certificado": os.path.basename(cc[0]) if cc else "", "porta": PORTA_WEBHOOK,
                    "verificado_em": ESTADO["verificado_em"], "ultimo": ESTADO["ultimo_webhook"]},
        "pessoas": pessoas,
        "apps": lista,
        "fala": FALA.status(),
        "fala_tela": FALA.status("wav"),
        "registro": ler_conversas()["registro"][:30],
        "aparencia": {"cor": c["cor"], "cor_dia": c["cor_dia"]},
        "atalho": atalho(),
        "uso_ia": USO.resumo(),
    }


# ---------------------------------------------------------------- a conversa na tela (Conversar com a IA)
# A mesma ponte do WhatsApp, pela tela do CorrerIA: a pergunta (ou a foto, o PDF) vai para o app do assunto, com a
# conversa de quem está usando a tela (o login do Home Assistant). Fica guardada (as últimas 40 mensagens).
MAX_TELA = 40
MAX_ANEXO = 15 * 1024 * 1024


def pessoa_da_tela(cab):
    """Quem está na tela, pelo login do Home Assistant (o painel manda X-Remote-User-*): a pessoa ligada a ele."""
    uid = str(cab.get("X-Remote-User-Id") or "")
    nome = str(cab.get("X-Remote-User-Display-Name") or cab.get("X-Remote-User-Name") or "")
    p = next((x for x in pessoas_ha() if uid and x.get("usuario") == uid), None)
    return ({"id": p["id"], "nome": p["nome"]} if p else {"id": "", "nome": nome or "Você"}), uid or "_"


def ola_da_tela(cab):
    """O primeiro nome de quem está na tela, para o "Olá" do alto, como nos outros apps; "" sem o login (fica só o CorrerIA)."""
    p = pessoa_da_tela(cab)[0]
    nome = p["nome"] if p["id"] else str(cab.get("X-Remote-User-Display-Name") or cab.get("X-Remote-User-Name") or "")
    return (nome.split() or [""])[0]


MAX_CONVERSAS = 30  # as conversas guardadas de cada login (as mais velhas saem)


def _titulo(msgs):
    """O nome da conversa: a primeira pergunta (a primeira linha, até 60 letras), ou o arquivo mandado."""
    m = next((x for x in msgs if x.get("papel") == "eu"), None) or {}
    t = re.sub(r"\s+", " ", str(m.get("texto") or "").split("\n")[0]).strip()
    t = t or str(m.get("anexo") or "").strip() or "Conversa"
    return t if len(t) <= 60 else t[:59].rstrip() + "…"


def _tela_de(c, chave):
    """As conversas da tela de um login: {"atual": id ou None, "lista": [{id, titulo, criada, atualizada, mensagens}]}.
    Até a 0.5.0 era uma conversa só (uma lista de mensagens): vira a primeira da lista."""
    v = (c.get("tela") or {}).get(chave)
    if isinstance(v, list):
        msgs = [m for m in v if isinstance(m, dict)]
        if not msgs:
            return {"atual": None, "lista": []}
        cid = "c0"  # fixo: a migração dá o mesmo id a cada leitura, até gravar
        em = str(msgs[-1].get("em") or agora_iso())
        return {"atual": cid, "lista": [{"id": cid, "titulo": _titulo(msgs), "criada": str(msgs[0].get("em") or em), "atualizada": em, "mensagens": msgs}]}
    if not isinstance(v, dict):
        return {"atual": None, "lista": []}
    lista = [x for x in v.get("lista") or [] if isinstance(x, dict) and x.get("id") and isinstance(x.get("mensagens"), list)]
    atual = v.get("atual") if any(x["id"] == v.get("atual") for x in lista) else None
    return {"atual": atual, "lista": lista}


def _mudar_tela(chave, mudar):
    """Lê as conversas do login, muda (mudar(t) recebe {"atual", "lista"}) e grava; devolve o que mudar devolveu."""
    with TRAVA:
        c = ler_json(CONVERSAS_ARQ)
        tela = c.get("tela") if isinstance(c.get("tela"), dict) else {}
        t = _tela_de(c, chave)
        r = mudar(t)
        t["lista"] = sorted(t["lista"], key=lambda x: str(x.get("atualizada") or ""), reverse=True)[:MAX_CONVERSAS]
        if t["atual"] and not any(x["id"] == t["atual"] for x in t["lista"]):
            t["atual"] = None
        if t["lista"]:
            tela[chave] = t
        else:
            tela.pop(chave, None)
        c["tela"] = tela
        _gravar_conversas(c)
        return r


def conversa_tela(chave):
    """A conversa aberta agora (as mensagens); nova, vazia."""
    t = _tela_de(ler_json(CONVERSAS_ARQ), chave)
    return next((x["mensagens"] for x in t["lista"] if x["id"] == t["atual"]), [])


def conversa_aberta(chave):
    t = _tela_de(ler_json(CONVERSAS_ARQ), chave)
    return t["atual"]


def conversas_tela(chave):
    """A lista para a tela: [{id, titulo, atualizada, mensagens: quantas, aberta}], a mais recente primeiro."""
    t = _tela_de(ler_json(CONVERSAS_ARQ), chave)
    lista = sorted(t["lista"], key=lambda x: str(x.get("atualizada") or ""), reverse=True)
    return [{"id": x["id"], "titulo": x.get("titulo") or "Conversa", "atualizada": x.get("atualizada"), "mensagens": len(x["mensagens"]),
             "aberta": x["id"] == t["atual"]} for x in lista]


def _gravar_tela(chave, lista):
    """Grava as mensagens da conversa aberta (a primeira mensagem de uma conversa nova cria a conversa na lista)."""
    def mudar(t):
        conv = next((x for x in t["lista"] if x["id"] == t["atual"]), None)
        if not lista:
            if conv:
                t["lista"].remove(conv)
            t["atual"] = None
            return
        if not conv:
            conv = {"id": secrets.token_hex(4), "criada": agora_iso()}
            t["lista"].append(conv)
            t["atual"] = conv["id"]
        # atualizada com os microssegundos: duas conversas no mesmo segundo ficam na ordem certa
        conv.update(mensagens=lista[-MAX_TELA:], titulo=conv.get("titulo") or _titulo(lista), atualizada=datetime.now().isoformat(timespec="microseconds"))
    _mudar_tela(chave, mudar)


def nova_conversa(chave):
    """Nova conversa: a aberta fica na lista; a próxima mensagem começa outra. A mudança esperando o "sim" sai."""
    _mudar_tela(chave, lambda t: t.update(atual=None))
    guardar_pendente("tela:" + chave, None)
    return {"mensagens": [], "conversa": None, "conversas": conversas_tela(chave)}


def abrir_conversa(chave, cid):
    def mudar(t):
        if not any(x["id"] == cid for x in t["lista"]):
            raise ValueError("Essa conversa não existe mais.")
        t["atual"] = cid
    _mudar_tela(chave, mudar)
    guardar_pendente("tela:" + chave, None)
    return {"mensagens": conversa_tela(chave), "conversa": cid, "conversas": conversas_tela(chave)}


def apagar_conversa(chave, cid):
    def mudar(t):
        aberta = t["atual"] == cid
        t["lista"] = [x for x in t["lista"] if x["id"] != cid]
        if aberta:
            t["atual"] = None
        return aberta
    if _mudar_tela(chave, mudar):
        guardar_pendente("tela:" + chave, None)
    return {"mensagens": conversa_tela(chave), "conversa": conversa_aberta(chave), "conversas": conversas_tela(chave)}


def conversar(corpo, pessoa, chave):
    """Uma mensagem da conversa da tela: texto e/ou um anexo ({nome, b64} em data URL). Devolve a conversa toda."""
    texto = str(corpo.get("texto") or "").strip()[:2000]
    anexo = corpo.get("anexo") if isinstance(corpo.get("anexo"), dict) and corpo["anexo"].get("b64") else None
    if not texto and not anexo:
        raise ValueError("Escreva uma mensagem.")
    lista = conversa_tela(chave)
    hist = [{"papel": m.get("papel"), "texto": m.get("texto") or (f"[{m['anexo']}]" if m.get("anexo") else "")} for m in lista][-MAX_HISTORICO:]
    ultimo = next((m.get("app_id") for m in reversed(lista) if m.get("app_id")), None)
    eu = {"papel": "eu", "texto": texto, "em": agora_iso()}
    tipo = None
    if anexo:
        b64 = str(anexo["b64"])
        m = re.match(r"^data:([\w.+-]+/[\w.+-]+);base64,", b64)
        tipo = (m.group(1) if m else str(anexo.get("tipo") or "")).lower()
        if len(b64) * 3 // 4 > MAX_ANEXO:
            raise ValueError("O arquivo é grande demais (até 15 MB).")
        eu["anexo"] = str(anexo.get("nome") or ("PDF" if tipo == "application/pdf" else "Foto"))[:120]
        anexo = {"tipo": tipo, "nome": str(anexo.get("nome") or "")[:120], "b64": b64}
    r = None
    if anexo:
        guardar_pendente("tela:" + chave, None)
    else:
        r = responder_ia("tela:" + chave, texto, hist, pessoa, "correria", "CorrerIA")
    if r is not None:  # a IA com as ferramentas dos apps
        resposta, app = r[0], ({"app": "_ia", "nome": ", ".join(r[1])} if r[1] else None)
    else:
        app = APPS.escolher(texto, ultimo, tipo=tipo)
        if not app:
            resposta = NAO_LE if (tipo and APPS.lista()) else SEM_APP
        else:
            try:
                resposta = APPS.perguntar(app, texto, hist, pessoa, timeout=300 if anexo else 150, anexo=anexo, canal="correria")
            except apps.ErroApp as e:
                log("CorrerIA:", e)
                resposta = f"Não consegui falar com o {app['nome']} agora. {e}"
    resp = {"papel": "ia", "texto": whatsapp.para_whatsapp(resposta), "em": agora_iso()}
    if app:
        resp.update(app=app["nome"], app_id=app["app"])
    lista += [eu, resp]
    _gravar_tela(chave, lista)
    return {"mensagens": lista[-MAX_TELA:], "conversa": conversa_aberta(chave)}


class Tela(BaseHTTPRequestHandler):
    server_version = "CorrerIA/" + VERSAO

    def log_message(self, fmt, *args):
        if DEV and LOG_HTTP:
            log(self.address_string(), fmt % args)

    def permitido(self):
        if DEV or self.client_address[0].replace("::ffff:", "") in PERMITIDOS:
            return True
        self.send_error(403, "Use o CorrerIA pelo painel do Home Assistant.")
        return False

    def caminho(self):
        return urllib.parse.urlparse(self.path).path

    def enviar(self, status, corpo, tipo="application/json; charset=utf-8"):
        if isinstance(corpo, (dict, list)):
            corpo = json.dumps(corpo, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(corpo)

    def corpo_json(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > (22 * 1024 * 1024 if self.caminho() == "/api/conversa" else 1024 * 1024):  # a conversa leva foto ou PDF
            resto = min(n, 64 * 1024 * 1024)
            while resto > 0:  # lê e joga fora, para a resposta chegar (sem cortar a conexão no meio do envio)
                pedaco = self.rfile.read(min(resto, 1024 * 1024))
                if not pedaco:
                    break
                resto -= len(pedaco)
            raise ValueError("Pedido grande demais.")
        try:
            v = json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            raise ValueError("Pedido inválido.") from None
        return v if isinstance(v, dict) else {}

    def do_GET(self):
        if not self.permitido():
            return
        p = self.caminho()
        if p == "/api/estado":
            return self.enviar(200, estado())
        if p == "/api/conversa":
            pessoa, chave = pessoa_da_tela(self.headers)
            return self.enviar(200, {"mensagens": conversa_tela(chave), "pessoa": pessoa["nome"], "ola": ola_da_tela(self.headers),
                                     "conversa": conversa_aberta(chave)})
        if p == "/api/conversas":
            return self.enviar(200, {"conversas": conversas_tela(pessoa_da_tela(self.headers)[1])})
        nome = "index.html" if p in ("/", "") else p.lstrip("/")
        arq = os.path.realpath(os.path.join(WWW, nome))
        if not arq.startswith(os.path.realpath(WWW) + os.sep) or not os.path.isfile(arq):
            return self.enviar(404, {"erro": "não encontrado"})
        with open(arq, "rb") as f:
            dados = f.read()
        tipo = mimetypes.guess_type(arq)[0] or "application/octet-stream"
        if tipo.startswith("text/") or tipo in ("application/javascript", "image/svg+xml"):
            tipo += "; charset=utf-8"
        return self.enviar(200, dados, tipo)

    def fala(self):
        """POST /api/fala: o microfone da conversa (PCM de 16 kHz, 16 bits, mono, como o Assist) -> {texto}."""
        n = int(self.headers.get("Content-Length") or 0)
        if n > fala.PCM_MAX:
            resto = min(n, 64 * 1024 * 1024)
            while resto > 0:  # lê e joga fora, para a resposta chegar
                pedaco = self.rfile.read(min(resto, 1024 * 1024))
                if not pedaco:
                    break
                resto -= len(pedaco)
            return self.enviar(413, {"erro": "Fale até 2 minutos de cada vez."})
        audio = self.rfile.read(n) if n > 0 else b""
        try:
            return self.enviar(200, {"texto": FALA.texto(audio, "wav")})
        except fala.ErroFala as e:
            return self.enviar(400, {"erro": str(e)})

    def do_POST(self):
        if not self.permitido():
            return
        p = self.caminho()
        if p == "/api/fala":
            return self.fala()
        try:
            c = self.corpo_json()
            if p == "/api/config":
                salvar_config(c)
                return self.enviar(200, estado())
            if p == "/api/pessoa":
                salvar_pessoa(c.get("id"), c.get("numero"))
                return self.enviar(200, estado())
            if p == "/api/conferir":
                conferir_conta()
                return self.enviar(200, estado())
            if p == "/api/conversa":
                pessoa, chave = pessoa_da_tela(self.headers)
                return self.enviar(200, conversar(c, pessoa, chave))
            if p == "/api/conversa/limpar":  # apaga a conversa aberta (o botão antigo; hoje a lista tem o Apagar de cada uma)
                chave = pessoa_da_tela(self.headers)[1]
                _gravar_tela(chave, [])
                guardar_pendente("tela:" + chave, None)
                return self.enviar(200, {"mensagens": []})
            if p == "/api/conversa/nova":
                return self.enviar(200, nova_conversa(pessoa_da_tela(self.headers)[1]))
            if p == "/api/conversa/abrir":
                return self.enviar(200, abrir_conversa(pessoa_da_tela(self.headers)[1], str(c.get("id") or "")))
            if p == "/api/conversa/apagar":
                return self.enviar(200, apagar_conversa(pessoa_da_tela(self.headers)[1], str(c.get("id") or "")))
            if p == "/api/mcp/decidir":
                pessoa, _ = pessoa_da_tela(self.headers)
                AUT.decidir(c.get("id"), c.get("aprovar") is True, pessoa)
                if TOKEN:
                    threading.Thread(target=lambda: _tentar(ha_post, "/services/persistent_notification/dismiss",
                                                            {"notification_id": "correria_conectar"}), daemon=True).start()
                return self.enviar(200, estado())
            if p == "/api/mcp/desconectar":
                AUT.desconectar(c.get("id"))
                return self.enviar(200, estado())
            if p == "/api/registro/limpar":
                with TRAVA:
                    cv = ler_conversas()
                    cv["registro"] = []
                    _gravar_conversas(cv)
                return self.enviar(200, estado())
            return self.enviar(404, {"erro": "não encontrado"})
        except (ValueError, LookupError, whatsapp.ErroWhatsApp) as e:
            return self.enviar(400, {"erro": str(e)})
        except Exception as e:  # noqa: BLE001
            log("Erro", p, e)
            return self.enviar(500, {"erro": str(e)})


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    ler_config()  # cria o token de verificação na primeira vez
    hook = ServidorWebhook(("0.0.0.0", PORTA_WEBHOOK), Webhook)
    threading.Thread(target=hook.serve_forever, daemon=True).start()
    cc = certificado()
    log(f"CorrerIA {VERSAO}: tela na porta {PORTA}; webhook e MCP na porta {PORTA_WEBHOOK} ({'https, ' + os.path.basename(cc[0]) if cc else 'http, sem certificado em ' + SSL_DIR})")
    tela = ThreadingHTTPServer(("0.0.0.0", PORTA), Tela)
    tela.daemon_threads = True
    tela.serve_forever()


if __name__ == "__main__":
    main()
