"""CorrerIA: o contato da CorrerIA Code no WhatsApp (a API oficial da Meta). As pessoas da casa mandam uma pergunta pelo
WhatsApp; o CorrerIA confere quem mandou, passa para o app da família que responde aquele assunto (o GerencIA, para as
finanças) e devolve a resposta pelo WhatsApp.

Dois servidores (só biblioteca padrão do Python):
- a tela, pelo painel do Home Assistant (ingress, porta 8099): configuração, quem conversa, os apps e as últimas mensagens;
- o webhook da Meta (porta 8443, https com o certificado do Duck DNS em /ssl): só GET e POST em /webhook, com a
  assinatura conferida; o resto responde 404.
"""
import json
import mimetypes
import os
import re
import secrets
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
import whatsapp

VERSAO = "0.1.0"
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
CONVERSAS_ARQ = os.path.join(DATA_DIR, "conversas.json")
MAX_CORPO = 3 * 1024 * 1024   # a Meta manda até 3 MB
MAX_HISTORICO = 16            # as últimas mensagens de cada pessoa que vão junto com a pergunta
HORAS_CONVERSA = 12           # depois disso, a conversa recomeça
MAX_REGISTRO = 60             # as últimas mensagens que a tela mostra
PESSOA_RE = re.compile(r"^person\.[a-z0-9_]+$")

TRAVA = threading.Lock()
_travas_numero = defaultdict(threading.Lock)  # uma pergunta de cada vez por pessoa (a conversa fica na ordem)
ESTADO = {"ultimo_webhook": None, "verificado_em": None, "conta": None, "conta_em": None}


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
           "pessoas": {k: whatsapp.so_digitos(v) for k, v in (c.get("pessoas") or {}).items() if PESSOA_RE.match(str(k)) and whatsapp.so_digitos(v)}}
    if len(out["verificacao"]) < 16:  # o token de verificação que a Meta manda de volta ao cadastrar o webhook
        out["verificacao"] = secrets.token_urlsafe(18)
        gravar_config(out)
    return out


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
    """As pessoas do Home Assistant: [{id, nome}]. Fora dele (no computador), Ana e Beto de exemplo."""
    if not TOKEN:
        return [{"id": "person.ana", "nome": "Ana"}, {"id": "person.beto", "nome": "Beto"}] if DEV else []
    if _pessoas_cache["v"] is not None and time.time() - _pessoas_cache["t"] < 60:
        return _pessoas_cache["v"]
    try:
        estados = ha_get("/states")
        v = sorted(({"id": s["entity_id"], "nome": (s.get("attributes") or {}).get("friendly_name") or s["entity_id"][7:]}
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
            "registro": [x for x in c.get("registro") or [] if isinstance(x, dict)][:MAX_REGISTRO]}


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
SO_TEXTO = "Por enquanto eu só leio mensagens de texto. Escreva a sua pergunta."
SEM_APP = "Ainda não há app respondendo por aqui. No GerencIA, ligue Mais › Configurações › Integrações › CorrerIA no WhatsApp."


def responder_pergunta(texto, pessoa, numero=None):
    """A pergunta vai para o app do assunto; devolve (resposta, app). Serve para o WhatsApp e para o Testar da tela."""
    app = APPS.escolher(texto, ultimo_app(numero) if numero else None)
    if not app:
        return SEM_APP, None
    try:
        return APPS.perguntar(app, texto, historico(numero) if numero else [], pessoa), app
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
        if texto is None:
            registrar("recebida", pessoa["nome"], f"[{m.get('type')}]")
            return enviar(wa, de, pessoa, SO_TEXTO)
        texto = texto.strip()[:2000]
        if not texto:
            return
        registrar("recebida", pessoa["nome"], texto)
        resposta, app = responder_pergunta(texto, pessoa, de)
        if app:
            guardar_conversa(de, texto, resposta, app)
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

    def responder(self, status, texto=""):
        corpo = texto.encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        if u.path.rstrip("/") != "/webhook":
            return self.responder(404)
        q = urllib.parse.parse_qs(u.query)
        modo, tok, desafio = (q.get(k, [""])[0] for k in ("hub.mode", "hub.verify_token", "hub.challenge"))
        c = ler_config()
        if modo == "subscribe" and tok and secrets.compare_digest(tok, c["verificacao"]):
            ESTADO["verificado_em"] = agora_iso()
            log("Webhook: a Meta confirmou o endereço")
            return self.responder(200, desafio)
        return self.responder(403)

    def do_POST(self):
        if urllib.parse.urlparse(self.path).path.rstrip("/") != "/webhook":
            return self.responder(404)
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

    def do_HEAD(self):
        self.responder(404)

    do_PUT = do_DELETE = do_PATCH = do_OPTIONS = do_HEAD


# ---------------------------------------------------------------- a tela (porta 8099, pelo painel)

def estado():
    c = ler_config()
    nums = c["pessoas"]
    pessoas = [dict(p, numero=nums.get(p["id"], "")) for p in pessoas_ha()]
    pessoas += [{"id": k, "nome": k[7:].replace("_", " ").title(), "numero": v, "fora": True} for k, v in nums.items() if k not in {p["id"] for p in pessoas}]
    cc = certificado()
    return {
        "versao": VERSAO,
        "config": {"numero_id": c["numero_id"], "token": _fim(c["token"]), "segredo": _fim(c["segredo"]), "verificacao": c["verificacao"],
                   "endereco": c["endereco"], "webhook": (c["endereco"] + "/webhook") if c["endereco"] else "", "ligado": c["ligado"]},
        "pronto": bool(c["numero_id"] and c["token"] and c["segredo"]),
        "conta": ESTADO["conta"],
        "webhook": {"https": bool(cc), "certificado": os.path.basename(cc[0]) if cc else "", "porta": PORTA_WEBHOOK,
                    "verificado_em": ESTADO["verificado_em"], "ultimo": ESTADO["ultimo_webhook"]},
        "pessoas": pessoas,
        "apps": APPS.publicos(),
        "registro": ler_conversas()["registro"][:30],
    }


def testar(corpo):
    """Testar uma pergunta pela tela, sem o WhatsApp: vai para o app como se viesse da pessoa escolhida."""
    texto = str(corpo.get("texto") or "").strip()[:2000]
    if not texto:
        raise ValueError("Escreva uma pergunta.")
    pid = str(corpo.get("pessoa") or "")
    nome = next((p["nome"] for p in pessoas_ha() if p["id"] == pid), "") or "Teste"
    resposta, app = responder_pergunta(texto, {"id": pid, "nome": nome})
    return {"resposta": whatsapp.para_whatsapp(resposta), "app": app["nome"] if app else ""}


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
        if n > 1024 * 1024:
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

    def do_POST(self):
        if not self.permitido():
            return
        p = self.caminho()
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
            if p == "/api/testar":
                return self.enviar(200, testar(c))
            if p == "/api/registro/limpar":
                with TRAVA:
                    cv = ler_conversas()
                    cv["registro"] = []
                    _gravar_conversas(cv)
                return self.enviar(200, estado())
            return self.enviar(404, {"erro": "não encontrado"})
        except (ValueError, whatsapp.ErroWhatsApp) as e:
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
    log(f"CorrerIA {VERSAO}: tela na porta {PORTA}; webhook na porta {PORTA_WEBHOOK} ({'https, ' + os.path.basename(cc[0]) if cc else 'http, sem certificado em ' + SSL_DIR})")
    tela = ThreadingHTTPServer(("0.0.0.0", PORTA), Tela)
    tela.daemon_threads = True
    tela.serve_forever()


if __name__ == "__main__":
    main()
