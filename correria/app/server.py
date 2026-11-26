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
import ipaddress
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
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import apps
import casa
import dados as copias  # com outro nome: aqui «dados» é nome de variável em vários lugares
import fala
import ferramentas
import ia
import memoria_ia
import mcp
import oauth
import avisos
import rondas
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
# 1.13.0: a porta do túnel da Cloudflare (o app Cloudflared): a mesma porta pública, em http e só na rede de casa (o https
# é o da Cloudflare, na 443, sem abrir porta no roteador); só com o túnel ligado na tela
PORTA_TUNEL = int(os.environ.get("CORRERIA_PORTA_TUNEL", "8444"))
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
RONDAS_ARQ = os.path.join(DATA_DIR, "rondas.json")  # 1.19.0: o histórico das rondas (as últimas 500)
PENDENTE_VALE = 30 * 60       # uma mudança proposta espera o "sim" por até 30 minutos
MAX_MCP = 1024 * 1024
MAX_CORPO = 3 * 1024 * 1024   # a Meta manda até 3 MB
MAX_HISTORICO = 16            # as últimas mensagens de cada pessoa que vão junto com a pergunta
HORAS_CONVERSA = 12           # depois disso, a conversa recomeça
MAX_REGISTRO = 60             # as últimas mensagens que a tela mostra
PESSOA_RE = re.compile(r"^person\.[a-z0-9_]+$")

TRAVA = threading.Lock()
_travas_numero = defaultdict(threading.Lock)  # uma pergunta de cada vez por pessoa (a conversa fica na ordem)
ESTADO = {"ultimo_webhook": None, "verificado_em": None, "conta": None, "conta_em": None, "conta_erro": "", "ia": None}


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

def _prazos_de(c):
    """1.32.0: o prazo do aviso de cada ronda, {id da ronda: dias} (0: sem aviso). O da Ronda da casa, sem escolha, é o
    ronda_dias de antes (30 de início); as outras começam sem aviso."""
    dias = lambda n: isinstance(n, int) and not isinstance(n, bool) and 0 <= n <= 365
    p = {str(k): v for k, v in c["ronda_prazos"].items() if dias(v) and re.fullmatch(r"[a-z0-9_]{1,20}", str(k))} if isinstance(c.get("ronda_prazos"), dict) else {}
    if "casa" not in p:
        p["casa"] = c["ronda_dias"] if dias(c.get("ronda_dias")) else 30
    return p


def ler_config():
    c = ler_json(CONFIG_ARQ)
    out = {"numero_id": str(c.get("numero_id") or ""), "token": str(c.get("token") or ""), "segredo": str(c.get("segredo") or ""),
           "verificacao": str(c.get("verificacao") or ""), "endereco": str(c.get("endereco") or ""), "ligado": c.get("ligado") is not False,
           "mcp": c.get("mcp") is True, "sensores": c.get("sensores") is True, "tunel": c.get("tunel") is True,
           # 1.14.0: o endereço público do conector MCP é dele (o do webhook pode ser outro, como o Duck DNS com a porta
           # 8443 para a Meta e um domínio pelo túnel da Cloudflare para as IAs); quem atualiza começa com o mesmo nos dois
           "endereco_mcp": str(c["endereco_mcp"] or "") if isinstance(c.get("endereco_mcp"), str) else str(c.get("endereco") or ""),
           # 1.5.0: a casa do Home Assistant (o Assist) como um app, ligada de início; a Conversa da tela cheia recolhe
           # sozinha depois de recolher minutos sem uso (1, 3, 5 ou 10; 3 de início)
           "casa": c.get("casa") is not False, "recolher": c.get("recolher") if c.get("recolher") in RECOLHER else 3,
           # 1.7.0: as conversas paradas há mais de tantos dias saem sozinhas (0: nunca; 30 de início)
           "apagar_dias": c.get("apagar_dias") if c.get("apagar_dias") in APAGAR_DIAS else 30,
           # 1.19.0: avisar quando um cômodo fica sem ronda há mais de tantos dias (0: nunca; 30 de início; até 365)
           # 1.21.0: o aviso no celular: a que horas (de meia em meia hora; 09:00 de início) e quem recebe (person.*)
           "ronda_hora": c["ronda_hora"] if HORA_RE.match(str(c.get("ronda_hora") or "")) else "09:00",
           "ronda_para": [p for p in c.get("ronda_para") or [] if isinstance(p, str) and PESSOA_RE.match(p)][:30] if isinstance(c.get("ronda_para"), list) else [],
           "ronda_dias": _prazos_de(c).get("casa", 0), "ronda_prazos": _prazos_de(c),
           # 0.17.0: o WhatsApp liga e desliga como o conector MCP; quem já tinha configurado continua ligado
           "whatsapp": c["whatsapp"] if isinstance(c.get("whatsapp"), bool) else None,  # None: ligado se já está configurado (wa_ligado)
           # a IA que conversa (uma entidade ai_task do Home Assistant); vazio: a padrão de lá (Configurações › Sistema › IA)
           "ia_entidade": str(c.get("ia_entidade") or "") if IA_RE.match(str(c.get("ia_entidade") or "")) else "",
           # 1.6.0: a IA que pesquisa na internet (a da conversa da tela); vazio: a mesma de conversar
           "ia_pesquisa": str(c.get("ia_pesquisa") or "") if IA_RE.match(str(c.get("ia_pesquisa") or "")) else "",
           # a cor do app, da casa toda (como nos outros apps): uma das 12 da família; a Cor do dia, ligada até desligar
           "cor": c.get("cor") if c.get("cor") in CORES else "", "cor_dia": c.get("cor_dia") is not False,
           "pessoas": {k: whatsapp.so_digitos(v) for k, v in (c.get("pessoas") or {}).items() if PESSOA_RE.match(str(k)) and whatsapp.so_digitos(v)}}
    if len(out["verificacao"]) < 16:  # o token de verificação que a Meta manda de volta ao cadastrar o webhook
        out["verificacao"] = secrets.token_urlsafe(18)
        gravar_config(out)
    return out


IA_RE = re.compile(r"^(ai_task\.[a-z0-9_]+)?$")
RECOLHER = (1, 3, 5, 10)
APAGAR_DIAS = (7, 30, 90, 0)  # 1.7.0: Apagar as conversas paradas há mais de (0: nunca)
def wa_ligado(c):
    """0.17.0: o WhatsApp ligado no CorrerIA: o que a pessoa escolheu ou, sem escolha, ligado se já está configurado."""
    return c["whatsapp"] if isinstance(c.get("whatsapp"), bool) else bool(c["numero_id"] and c["token"])


CORES = ("vermelho", "coral", "laranja", "ouro", "verde", "menta", "turquesa", "azul", "indigo", "lilas", "rosa", "grafite")


def gravar_config(c):
    gravar_arquivo(CONFIG_ARQ, json.dumps(c, ensure_ascii=False, indent=1))


def _fim(segredo):
    return ("••••" + segredo[-4:]) if len(segredo) >= 8 else ("••••" if segredo else "")


def limpar_endereco(e, mcp=False):
    """O endereço público (https://casa-exemplo.duckdns.org:8443), sem /webhook (o do conector: sem /mcp) nem barra no fim."""
    e = str(e or "").strip()
    if not e:
        return ""
    if not re.match(r"^https?://", e):
        e = "https://" + e
    u = urllib.parse.urlparse(e)
    if not u.hostname or " " in e:
        raise ValueError("Endereço inválido. Ex.: " + ("https://correria.casa-exemplo.com.br" if mcp else "https://casa-exemplo.duckdns.org:8443"))
    caminho = re.sub(r"/mcp/?$" if mcp else r"/webhook/?$", "", u.path.rstrip("/"))
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
        if "endereco_mcp" in corpo:  # 1.14.0: o do conector MCP, separado do do webhook
            c["endereco_mcp"] = limpar_endereco(corpo.get("endereco_mcp"), mcp=True)
        if "ligado" in corpo:
            c["ligado"] = corpo.get("ligado") is not False
        if "mcp" in corpo:
            c["mcp"] = corpo.get("mcp") is True
        if "tunel" in corpo:  # 1.13.0: o túnel da Cloudflare
            c["tunel"] = corpo.get("tunel") is True
        if "whatsapp" in corpo:
            c["whatsapp"] = corpo.get("whatsapp") is True
        if "sensores" in corpo:
            c["sensores"] = corpo.get("sensores") is True
        if "casa" in corpo:
            c["casa"] = corpo.get("casa") is not False
        if "recolher" in corpo:
            if corpo.get("recolher") not in RECOLHER:
                raise ValueError("Tempo desconhecido.")
            c["recolher"] = corpo.get("recolher")
        if "apagar_dias" in corpo:
            if corpo.get("apagar_dias") not in APAGAR_DIAS or isinstance(corpo.get("apagar_dias"), bool):
                raise ValueError("Escolha 7, 30 ou 90 dias, ou nunca.")
            c["apagar_dias"] = corpo.get("apagar_dias")
        if "ronda_hora" in corpo:  # 1.21.0
            if not HORA_RE.match(str(corpo.get("ronda_hora") or "")):
                raise ValueError("O horário vale de meia em meia hora (09:00, 09:30…).")
            c["ronda_hora"] = corpo["ronda_hora"]
        if "ronda_para" in corpo:
            para = corpo.get("ronda_para")
            if not isinstance(para, list) or not all(isinstance(p, str) and PESSOA_RE.match(p) for p in para) or len(para) > 30:
                raise ValueError("Quem recebe: as pessoas da casa (person.*).")
            c["ronda_para"] = list(dict.fromkeys(para))
        if "ronda_dias" in corpo:  # 1.19.0 (o prazo da Ronda da casa; 1.32.0: o de cada ronda vem em ronda_prazo)
            n = corpo.get("ronda_dias")
            if not isinstance(n, int) or isinstance(n, bool) or not 0 <= n <= 365:
                raise ValueError("Escolha de 1 a 365 dias, ou nunca.")
            c["ronda_prazos"] = dict(c["ronda_prazos"], casa=n)
        if "ronda_prazo" in corpo:  # 1.32.0: {ronda, dias}: o aviso de cada ronda (0 desliga)
            pz = corpo.get("ronda_prazo") if isinstance(corpo.get("ronda_prazo"), dict) else {}
            rid, n = str(pz.get("ronda") or ""), pz.get("dias")
            if rid not in rondas.RONDAS:
                raise ValueError("Essa ronda não existe mais.")
            if not isinstance(n, int) or isinstance(n, bool) or not 0 <= n <= 365:
                raise ValueError("Escolha de 1 a 365 dias.")
            c["ronda_prazos"] = dict(c["ronda_prazos"], **{rid: n})
        if "ia_entidade" in corpo:  # 0.16.0: a IA para conversar
            e = str(corpo.get("ia_entidade") or "")
            if not IA_RE.match(e):
                raise ValueError("IA desconhecida.")
            c["ia_entidade"] = e
            ESTADO["ia"] = None  # o que deu certo ou errado era da outra IA
        if "ia_pesquisa" in corpo:  # 1.6.0: a IA para pesquisar na internet
            e = str(corpo.get("ia_pesquisa") or "")
            if not IA_RE.match(e):
                raise ValueError("IA desconhecida.")
            c["ia_pesquisa"] = e
        if "cor" in corpo:  # escolher uma cor desliga a Cor do dia (a tela manda os dois)
            if corpo.get("cor") not in CORES:
                raise ValueError("Cor desconhecida.")
            c["cor"] = corpo.get("cor")
        if "cor_dia" in corpo:
            c["cor_dia"] = corpo.get("cor_dia") is not False
        gravar_config(c)
    if any(k in corpo for k in ("numero_id", "token")):
        ESTADO.update(conta=None, conta_em=None)
    if "sensores" in corpo:  # cria ou tira os sensores na hora
        threading.Thread(target=publicar_sensores if c["sensores"] else remover_sensores, daemon=True).start()
    if "apagar_dias" in corpo:  # 1.7.0: as velhas saem na hora
        limpar_conversas_velhas()
    if "ronda_dias" in corpo or "ronda_prazo" in corpo:  # 1.19.0: confere na hora (a tela já recebe os atrasados do prazo novo)
        _tentar(conferir_rondas)
    if "tunel" in corpo:  # 1.13.0: abre ou fecha a porta do túnel na hora
        ligar_tunel(c["tunel"])
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
    try:
        r = conta().conferir()
    except whatsapp.ErroWhatsApp as e:
        ESTADO.update(conta=None, conta_erro=str(e), conta_em=agora_iso())
        raise
    ESTADO.update(conta=r, conta_erro="", conta_em=agora_iso())
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


_ias_cache = {"t": 0.0, "v": None}


def ias_ha():
    """As IAs do Home Assistant que fazem tarefas (as entidades ai_task.*): [{id, nome}]. Fora dele, duas de exemplo."""
    if not TOKEN:
        return [{"id": "ai_task.ia_de_exemplo", "nome": "IA de exemplo"}, {"id": "ai_task.outra_ia", "nome": "Outra IA"}] if DEV else []
    if _ias_cache["v"] is not None and time.time() - _ias_cache["t"] < 60:
        return _ias_cache["v"]
    try:
        v = sorted(({"id": s["entity_id"], "nome": (s.get("attributes") or {}).get("friendly_name") or s["entity_id"][8:]}
                    for s in ha_get("/states") if isinstance(s, dict) and str(s.get("entity_id", "")).startswith("ai_task.")),
                   key=lambda x: x["nome"].lower())
    except (urllib.error.URLError, OSError, ValueError) as e:
        log("Não consegui ver as IAs do Home Assistant:", e)
        return _ias_cache["v"] or []
    _ias_cache.update(t=time.time(), v=v)
    return v


def nome_da_ia(c=None, ent=None):
    """O nome da IA que conversa (ou de ent): a escolhida ou, na padrão, a única que existe (com mais de uma, não dá para
    saber qual)."""
    c = c or ler_config()
    lista = ias_ha()
    ent = c["ia_entidade"] if ent is None else ent
    if ent:
        return next((x["nome"] for x in lista if x["id"] == ent), ent)
    return lista[0]["nome"] if len(lista) == 1 else ""


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


def registrar(tipo, quem, texto, app="", canal="whatsapp"):
    """O que a tela mostra em Últimas mensagens (aba WhatsApp: recebida, enviada, bloqueada, o número sem cadastro, erro)
    e em Últimas mudanças (aba MCP, canal "mcp": o que as IAs conectadas mudaram). O canal "tela" (os erros da conversa
    da tela, que ela mesma mostra) fica só no arquivo."""
    with TRAVA:
        c = ler_conversas()
        c["registro"].insert(0, {"em": agora_iso(), "tipo": tipo, "quem": str(quem or "")[:60], "texto": str(texto or "")[:300], "app": app, "canal": canal})
        c["registro"] = c["registro"][:MAX_REGISTRO]
        _gravar_conversas(c)


def canal_de(r):
    """O canal de uma linha do registro; as de antes da 0.15.0 não têm: pelo tipo."""
    return r.get("canal") or ("mcp" if r.get("tipo") == "mcp" else "whatsapp")


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
CASA = casa.Casa(lambda c: ha_get(c), lambda c, corpo: ha_post(c, corpo), log, lambda m: ha_texto("/template", {"template": m}))
# 1.5.0: a casa do Home Assistant (o Assist) entra como mais um app, ligada de início (Configurações › Integrações › Casa)
FERR = ferramentas.Ferramentas(lambda: APPS, log, casa=lambda: CASA if (TOKEN and ler_config()["casa"]) else None)  # o APPS de agora (os testes trocam)
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
        USO.registrar(tipo, len(instrucoes), 0, time.time() - comeco, str(e), ia=(ESTADO["ia"] or {}).get("nome", ""))
        raise
    USO.registrar(tipo, len(instrucoes), len(json.dumps(dados, ensure_ascii=False)), time.time() - comeco, ia=(ESTADO["ia"] or {}).get("nome", ""))
    return dados


def erro_da_ia(msg, nome):
    """O erro da IA em português, dizendo qual IA (0.16.0): sem cota vira "A <IA> ficou sem cota…"."""
    quem = nome or "A IA padrão do Home Assistant"
    if uso.resultado(msg) == "cota":
        return f"{quem} ficou sem cota (o limite de uso acabou). Espere a cota voltar ou escolha outra em IA para conversar."
    if apps.erro_cru(msg):  # 1.16.2: fora do ar ou sobrecarregada: sem o JSON do provedor
        return f"{quem} está fora do ar ou sobrecarregada agora. Tente de novo daqui a pouco."
    return f"{quem}: {msg}" if nome else msg


# 1.27.0: a resposta já no formato (o `structure` do ai_task.generate_data, com os seletores do Home Assistant): a IA devolve
# os campos, em vez de um JSON escrito no meio do texto. Uma IA que não aceitar a estrutura (o Home Assistant responde erro)
# fica no jeito de antes, só com o FORMATO nas instruções; a escolha vale por IA, até o app reiniciar.
ESTRUTURA = {
    "resposta": {"description": "O texto para a pessoa. Vazio quando há ferramentas de leitura em chamar.", "selector": {"text": {"multiline": True}}},
    "chamar": {"description": "As ferramentas a chamar agora (lista vazia se nenhuma).",
               "selector": {"object": {"multiple": True, "fields": {
                   "ferramenta": {"required": True, "selector": {"text": {}}},
                   "argumentos": {"description": "Os argumentos da ferramenta, um objeto JSON com os campos da entrada dela.",
                                  "selector": {"object": {}}},
                   "resumo": {"selector": {"text": {}}}}}}},
}
SEM_ESTRUTURA = set()  # as IAs (entity_id; "" é a padrão) que recusaram a estrutura


def _chamar_ia(instrucoes):
    c = ler_config()
    nome = nome_da_ia(c)
    corpo = {"task_name": "CorrerIA", "instructions": instrucoes}
    if c["ia_entidade"]:
        corpo["entity_id"] = c["ia_entidade"]
    ent = c["ia_entidade"] or ""
    recusou = ""
    if ent not in SEM_ESTRUTURA:
        try:
            r = ha_post("/services/ai_task/generate_data?return_response", dict(corpo, structure=ESTRUTURA), timeout=150)
            dados = ((r or {}).get("service_response") or {}).get("data")
            if isinstance(dados, (dict, str)) and dados:
                ESTADO["ia"] = {"ok": True, "erro": "", "em": agora_iso(), "nome": nome}
                return dados
            raise ValueError("sem dados")
        except urllib.error.HTTPError as e:
            try:
                msg = str(json.loads(e.read() or b"{}").get("message") or "")
            except (ValueError, AttributeError):
                msg = ""
            if uso.resultado(msg) == "cota" or apps.erro_cru(msg):  # sem cota ou fora do ar: não é da estrutura
                ESTADO["ia"] = {"ok": False, "erro": erro_da_ia(msg, nome), "em": agora_iso(), "nome": nome}
                raise ia.ErroIA(erro_da_ia(msg, nome)) from None
            recusou = f"não aceitou a resposta estruturada ({msg[:160] or e.code})"
        except ValueError:
            recusou = "não devolveu a resposta estruturada"
        except (urllib.error.URLError, OSError) as e:
            ESTADO["ia"] = {"ok": False, "erro": f"Não consegui falar com o Home Assistant ({getattr(e, 'reason', e)}).", "em": agora_iso(), "nome": nome}
            raise ia.ErroIA(ESTADO["ia"]["erro"]) from None

    def falhou(msg):
        ESTADO["ia"] = {"ok": False, "erro": msg, "em": agora_iso(), "nome": nome}
        return ia.ErroIA(msg)
    try:
        r = ha_post("/services/ai_task/generate_data?return_response", corpo, timeout=150)
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read() or b"{}").get("message")
        except (ValueError, AttributeError):
            msg = None
        raise falhou(erro_da_ia(msg or f"O Home Assistant respondeu {e.code}.", nome)) from None
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise falhou(f"Não consegui falar com o Home Assistant ({getattr(e, 'reason', e)}).") from None
    dados = ((r or {}).get("service_response") or {}).get("data")
    if dados is None:
        raise falhou(erro_da_ia("não devolveu resposta.", nome) if nome else "A IA não devolveu resposta.")
    if recusou:  # sem a estrutura respondeu: o problema era ela; essa IA fica no jeito de antes (um erro passageiro não conta)
        log(f"IA: {nome or 'a padrão'} {recusou}; sigo sem ela.")
        SEM_ESTRUTURA.add(ent)
    ESTADO["ia"] = {"ok": True, "erro": "", "em": agora_iso(), "nome": nome}
    return dados


PESQUISA_INSTR = """Pesquise na internet e responda em português do Brasil, curto e direto, com o que achou e de onde veio (o nome do site).
Hoje é {hoje}. Se não conseguir pesquisar na internet agora, diga só "Não consigo pesquisar na internet com esta IA." e nada mais: não responda de memória.
A pesquisa: {pesquisa}"""


def pesquisar_internet(pesquisa):
    """1.6.0: a pesquisa na internet da conversa da tela, pela IA "Para pesquisar na internet" (vazia: a de conversar), que
    precisa ter a busca na web ligada no Home Assistant. Devolve o texto do que achou (levanta ia.ErroIA)."""
    if not TOKEN:
        if DEV:
            return f"(pesquisa simulada) Achei 3 resultados para \"{pesquisa}\" no Site de Exemplo."
        raise ia.ErroIA("Sem o Home Assistant.")
    c = ler_config()
    ent = c["ia_pesquisa"] or c["ia_entidade"]
    nome, comeco = nome_da_ia(c, ent), time.time()
    instr = PESQUISA_INSTR.format(hoje=f"{datetime.now():%d/%m/%Y}", pesquisa=pesquisa)
    corpo = {"task_name": "CorrerIA · pesquisa", "instructions": instr}
    if ent:
        corpo["entity_id"] = ent
    try:
        r = ha_post("/services/ai_task/generate_data?return_response", corpo, timeout=150)
        dados = ((r or {}).get("service_response") or {}).get("data")
        if dados is None:
            raise ia.ErroIA("não devolveu resposta.")
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read() or b"{}").get("message")
        except (ValueError, AttributeError):
            msg = None
        msg = erro_da_ia(msg or f"O Home Assistant respondeu {e.code}.", nome)
        USO.registrar("pesquisa", len(instr), 0, time.time() - comeco, msg, ia=nome)
        raise ia.ErroIA(msg) from None
    except (urllib.error.URLError, OSError, ValueError, ia.ErroIA) as e:
        msg = str(e) if isinstance(e, ia.ErroIA) else f"Não consegui falar com o Home Assistant ({getattr(e, 'reason', e)})."
        USO.registrar("pesquisa", len(instr), 0, time.time() - comeco, msg, ia=nome)
        raise ia.ErroIA(msg) from None
    texto = dados if isinstance(dados, str) else json.dumps(dados, ensure_ascii=False)
    USO.registrar("pesquisa", len(instr), len(texto), time.time() - comeco, ia=nome)
    return texto.strip()[:6000]


# 1.27.0: as lembranças da casa (Mais › Lembranças): frases que valem em toda conversa da IA; /data/lembrancas.json
# 1.31.0 (o dono: "e se eu não usar o CorrerIA e só decidir usar o InventarIA e o ResolvIA?"; "memória compartilhada"): a memória
# não é mais do CorrerIA. É uma só, da casa, na pasta share (share/familia/memoria_ia.json, memoria_ia.py, igual nos apps em
# Python): todo app tem o cartão Memória da IA, lê e escreve ali e a põe nas instruções da IA dele. O CorrerIA é mais um.
LEMBRANCAS_ARQ = os.path.join(DATA_DIR, "lembrancas.json")                 # a de antes (1.27.0 a 1.30.0): vai para a de todos e sai
LEMBRANCAS_SHARE = os.path.join(SHARE_DIR, "correria", "lembrancas.json")  # o que a 1.28.0 publicava para os outros apps: sai
MEMORIA_ARQ = os.environ.get("MEMORIA_IA_ARQ") or os.path.join(SHARE_DIR, "familia", "memoria_ia.json")
MAX_LEMBRANCAS = memoria_ia.MAX_FRASES


def lembrancas():
    return memoria_ia.ler(MEMORIA_ARQ)


def lembrar(texto, pessoa=None):
    """Guarda uma frase na memória da casa (a mesma não entra duas vezes). Devolve o texto guardado; ValueError diz o que vale."""
    memoria_ia.lembrar(texto, "CorrerIA", str((pessoa or {}).get("nome") or ""), MEMORIA_ARQ)
    return " ".join(str(texto or "").split())[:memoria_ia.MAX_LETRAS]


def esquecer(lid):
    memoria_ia.esquecer(lid, MEMORIA_ARQ)


def migrar_lembrancas():
    """As lembranças que o CorrerIA guardava em /data vão para a memória de todos, uma vez; os arquivos de antes saem."""
    v = ler_json(LEMBRANCAS_ARQ).get("lista")
    if isinstance(v, list) and v:
        try:
            n = memoria_ia.juntar(v, "CorrerIA", MEMORIA_ARQ)
            log(f"Memória da IA: {n} {'frase foi' if n == 1 else 'frases foram'} para a memória compartilhada.")
        except memoria_ia.ErroMemoria as e:
            return log("Memória da IA:", e)   # fica onde está; tenta de novo no próximo início
    for arq in (LEMBRANCAS_ARQ, LEMBRANCAS_SHARE):
        try:
            os.remove(arq)
        except OSError:
            pass


# 1.29.0 (o dono: "não tem o backup no correria, igual nos outros apps… nem exportar, importar, começar do zero"; "pode colocar
# os segredos e conversas no backup"): Configurações › Dados. O .zip leva tudo de /data (o token da Meta, a chave secreta e as
# conversas inclusive); os backups ficam em share/correria/backups (só do dono) e, antes de trocar ou apagar os dados, uma
# versão vai para /data/versoes (as 3 últimas).
BACKUPS_DIR = os.path.join(SHARE_DIR, "correria", "backups")
VERSOES_DIR = os.path.join(DATA_DIR, "versoes")


def dados_estado():
    return {"backups": copias.listar(BACKUPS_DIR), "versoes": copias.listar(VERSOES_DIR)}


def exportar_zip():
    return copias.montar_zip(DATA_DIR, VERSAO, agora_iso())


def fazer_backup():
    try:
        return copias.guardar(BACKUPS_DIR, exportar_zip(), copias.MAX_BACKUPS)
    except OSError as e:
        raise ValueError(f"Não consegui gravar na pasta share ({e.strerror or e}).") from None


def _dados_trocados():
    """Depois de importar, restaurar ou começar do zero: nada do que estava na memória vale mais."""
    for d in (RONDAS_ATIVAS, FOTOS, FEITOS, PASSOS):
        d.clear()
    SEM_ESTRUTURA.clear()
    migrar_lembrancas()  # um backup de antes da 1.31.0 traz as lembranças em /data
    montar_rondas()


def trocar_dados(zip_bytes, motivo):
    """Importar ou restaurar: confere o .zip, guarda uma versão do que há agora e troca tudo pelo que veio."""
    arquivos, man = copias.ler_zip(zip_bytes)
    with TRAVA:
        copias.guardar(VERSOES_DIR, exportar_zip(), copias.MAX_VERSOES, motivo=motivo)
        copias.aplicar(DATA_DIR, arquivos, gravar_arquivo)
    _dados_trocados()
    log(f"Dados: {copias.MOTIVOS[motivo].replace('antes de ', '')} um backup da versão {man.get('versao') or '?'}.")


def restaurar_dados(origem, nome):
    trocar_dados(copias.abrir(BACKUPS_DIR if origem == "backup" else VERSOES_DIR, nome), "restaurar")


def comecar_do_zero():
    with TRAVA:
        copias.guardar(VERSOES_DIR, exportar_zip(), copias.MAX_VERSOES, motivo="zero")
        copias.zerar(DATA_DIR)
    _dados_trocados()
    log("Dados: começou do zero (as configurações ficam).")


AGENTE = ia.Agente(FERR, chamar_ia, log, simulada=DEV and not TOKEN, pesquisar=pesquisar_internet, lembrancas=lambda: [x["texto"] for x in lembrancas()])
# 1.27.0: o que a IA está fazendo agora em cada conversa da tela («Consultando o InventarIA…»), para a tela mostrar
PASSOS = {}
# 1.27.0: o que o último sim fez em cada conversa (por 10 minutos), para o Desfazer
FEITOS = {}
DESFAZER_SEG = 10 * 60


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


# 1.17.0: a última foto que cada conversa mandou (na memória, por 30 minutos), para a ferramenta que recebe foto: pôr a
# foto numa tarefa do ResolvIA. Não fica em disco nem nas conversas guardadas.
FOTOS = {}
FOTO_SEG = 30 * 60
MINI_RE = re.compile(r"^data:image/jpeg;base64,[A-Za-z0-9+/]+=*$")


def guardar_foto(chave, anexo):
    agora = time.time()
    for k in [k for k, v in FOTOS.items() if agora - v["em"] > FOTO_SEG]:
        FOTOS.pop(k, None)
    if anexo is None:
        FOTOS.pop(chave, None)
    else:
        while len(FOTOS) >= 20 and chave not in FOTOS:
            FOTOS.pop(min(FOTOS, key=lambda k: FOTOS[k]["em"]))
        FOTOS[chave] = {"em": agora, "anexo": anexo, "lido": {}}


def lido_de(chave):
    """1.26.0: o que as ferramentas já leram do arquivo desta conversa ({chamada: texto}); vai embora com o arquivo."""
    v = FOTOS.get(chave)
    return v.setdefault("lido", {}) if v and time.time() - v["em"] <= FOTO_SEG else {}


# 1.26.0 (o dono: "Não deu: Item 1: Categoria não encontrada: Consumíveis. As categorias dos consumíveis: Limpeza (c-limpeza)…"):
# o erro de um app, na tela, é a primeira frase dele, sem os ids nem a lista técnica (essa parte é para a IA)
def erro_para_gente(texto):
    t = " ".join(str(texto or "").split())
    t = re.sub(r"\s*\((?:[a-z]+[-_.:])+[a-z0-9_.:|-]*\)", "", t)  # (c-limpeza), (todo.lista:abc)
    m = re.match(r"(.{12,}?[.!?])(?:\s|$)", t)
    t = (m.group(1) if m else t)[:220].strip()
    return t or "o app não aceitou."


def foto_de(chave):
    v = FOTOS.get(chave)
    return v["anexo"] if v and time.time() - v["em"] <= FOTO_SEG else None


def foto_para_ferramenta(texto, tipo, ultimo=None, recentes=()):
    """Uma foto que chegou vai para a IA com as ferramentas (para guardar numa tarefa) quando algum app tem ferramenta
    que recebe esse tipo e: nenhum app lê esse tipo com a IA dele, ou a legenda fala mais do assunto do app da
    ferramenta (tarefa, lista) do que do app que leria a foto (fatura, conta)."""
    donos = FERR.recebem(tipo) if FERR.tem() else set()
    if not donos:
        return False
    leitor = APPS.escolher(texto, ultimo, tipo=tipo)
    if not leitor:
        return True
    melhor = max((APPS.pontos(a, texto) for a in APPS.lista() if a["app"] in donos), default=0)
    do_leitor = APPS.pontos(leitor, texto)
    if melhor > 0 and melhor > do_leitor:
        return True
    if do_leitor > 0:
        return False  # a legenda fala do assunto de quem lê (uma conta, uma fatura): vai para ele
    # 1.24.1 (o dono: "Adiciona esse nos consumíveis da lavanderia, 30 dias" foi para o GerencIA): a legenda diz alguma coisa
    # e nada do assunto de quem leria: não é para ele. Vai para a IA com as ferramentas, que escolhe o app pelo pedido (ou
    # pergunta). Só a foto sem legenda nenhuma continua indo para quem lê, a não ser que a conversa viesse de outro app que
    # recebe a foto (1.23.0: "o da última resposta").
    if re.search(r"[a-zà-ú]{3,}", str(texto or "").lower()):
        return True
    return bool(set(recentes) & donos) and leitor["app"] not in set(recentes)


def executar(acoes, pessoa, cliente, chave=None, falhas=None):
    """O "sim": faz cada mudança proposta, pelas ferramentas dos apps. Devolve (texto, nomes dos apps).
    falhas (uma lista, 1.26.0): ganha (ação, o erro inteiro do app) de cada mudança que o app recusou."""
    lista, linhas, nomes = FERR.todas(), [], []
    feitos = []
    CANAL.feitos = feitos
    for a in acoes:
        if a.get("ferramenta") == ia.LEMBRAR["id"]:  # 1.27.0: a lembrança da casa é daqui, não de um app
            try:
                linhas.append(f"- Vou lembrar: {lembrar((a.get('argumentos') or {}).get('fato'), pessoa)}")
            except ValueError as e:
                linhas.append(f"- Não deu: {e}")
            nomes += [] if "CorrerIA" in nomes else ["CorrerIA"]
            continue
        f = FERR.achar(str(a.get("ferramenta") or ""), lista)
        if not f:
            linhas.append(f"- Não deu: {a.get('resumo') or a.get('ferramenta')} (o app não está mais ligado).")
            continue
        recusa = []
        if chave and chave.startswith("tela:"):
            PASSOS[chave] = f"Fazendo no {f['app']['nome']}…"
        texto, erro = FERR.usar(f, a.get("argumentos") or {}, pessoa, cliente, anexo=foto_de(chave) if chave and f.get("anexo") else None, recusa=recusa)
        if f.get("anexo") and not erro:
            guardar_foto(chave, None)  # a foto foi para o lugar dela: não vai duas vezes
        if erro:
            linhas.append(f"- Não deu: {str(a.get('resumo') or f['titulo']).rstrip('. ')}. {erro_para_gente(texto)}")
            if falhas is not None and recusa:
                falhas.append((a, texto))
        else:
            linhas.append(f"- {texto.splitlines()[0] if texto else 'feito.'}")
            feitos.append({"ferramenta": f["id"], "argumentos": a.get("argumentos") or {}, "resumo": a.get("resumo") or f["titulo"], "resultado": str(texto or "")[:600]})
            if f.get("anexo"):
                CANAL.arquivo = True
        if f["app"]["nome"] not in nomes:
            nomes.append(f["app"]["nome"])
        if erro:
            registrar("erro", f["app"]["nome"], texto, canal="whatsapp" if cliente == "WhatsApp" else "tela")
    ok = all(not x.startswith("- Não deu") for x in linhas)
    return ("Feito!\n" if ok else "") + "\n".join(linhas), nomes


def responder_ia(chave, texto, hist, pessoa, canal, cliente):
    """A pergunta pela IA do Home Assistant com as ferramentas dos apps: (resposta, nomes dos apps, espera o sim) ou None
    (nenhum app com ferramentas, ou a IA fora do ar com um app que responde sozinho: vai pelo caminho antigo)."""
    pend = pegar_pendente(chave)
    if pend:
        if SIM_RE.match(texto):
            falhas = []
            feito, nomes = executar(pend, pessoa, cliente, chave, falhas)
            # 1.26.0 (o dono: "toda hora isso de não achar"): o que o app recusou volta para a IA, com o erro inteiro, para ela
            # corrigir e propor de novo (uma vez só por mudança); sem conserto, fica o «Não deu» com a frase do app
            de_novo = [(a, e) for a, e in falhas if not a.get("corrigida")]
            if de_novo and FERR.tem():
                nota = ("(Eu disse sim. O app respondeu:\n" + feito + "\nO erro inteiro de cada mudança que não deu:\n"
                        + "\n".join(f"- {a.get('ferramenta')}({json.dumps(a.get('argumentos') or {}, ensure_ascii=False)}) → {e}" for a, e in de_novo)
                        + "\nCorrija os argumentos pelo que o erro diz e chame de novo só as que não deram; se faltar um dado que só eu sei, "
                          "pergunte uma coisa só. Não repita as que já foram feitas.)")
                try:
                    foto = foto_de(chave)
                    r = AGENTE.responder(hist + [{"papel": "eu", "texto": nota}], pessoa, canal, cliente,
                                         **({"foto": f"{foto.get('nome') or 'arquivo'}, {ia.TIPO_NOME.get(foto.get('tipo'), foto.get('tipo') or 'arquivo')}",
                                             "anexo": foto, "lido": lido_de(chave)} if foto else {}),
                                         passo=(lambda t: PASSOS.__setitem__(chave, t)) if chave.startswith("tela:") else None)
                except ia.ErroIA as e:
                    log("IA:", e)
                    r = None
                if r and r["pendente"]:
                    for p in r["pendente"]:
                        p["corrigida"] = True
                    guardar_pendente(chave, r["pendente"])
                    bloco = ia.BLOCO_SIM_RE.search(r["resposta"])
                    return (feito + "\n\nCorrigi o que não deu. " + (bloco.group(0) if bloco else r["resposta"]),
                            sorted(set(nomes) | set(r["apps"])), True)
                if r and r["resposta"] and not r["resposta"].startswith("Não consegui"):
                    return feito + "\n\n" + r["resposta"], nomes, False
            return feito, nomes, False
        if NAO_RE.match(texto):
            return "Tudo bem, não mudei nada.", [], False
    if not FERR.tem():
        return None
    CANAL.tipo = "whatsapp" if canal == "whatsapp" else "conversa"
    try:
        foto = foto_de(chave)
        r = AGENTE.responder(hist + [{"papel": "eu", "texto": texto}], pessoa, canal, cliente,
                             **({"foto": f"{foto.get('nome') or 'arquivo'}, {ia.TIPO_NOME.get(foto.get('tipo'), foto.get('tipo') or 'arquivo')}",
                                 "anexo": foto, "lido": lido_de(chave)} if foto else {}),
                                         passo=(lambda t: PASSOS.__setitem__(chave, t)) if chave.startswith("tela:") else None)
    except ia.ErroIA as e:
        log("IA:", e)
        # 1.16.2: fora do ar, sobrecarregada ou sem cota: a mesma IA não responde pelo app; diz logo, numa frase
        passageiro = apps.erro_cru(str(e)) or "fora do ar ou sobrecarregada" in str(e) or uso.resultado(str(e)) == "cota"
        if passageiro:
            return (apps.FORA_DO_AR if apps.erro_cru(str(e)) else str(e)), [], False
        if any(a["rota"] for a in APPS.lista()):
            return None
        return f"A IA do Home Assistant não respondeu agora ({str(e).rstrip('.')}). Tente de novo daqui a pouco.", [], False
    if r["pendente"]:
        guardar_pendente(chave, r["pendente"])
    if r.get("arquivo"):
        CANAL.arquivo = True  # 1.26.0: a resposta usou o arquivo da conversa: a tela mostra qual
    return r["resposta"], r["apps"], bool(r["pendente"])


def responder_pergunta(texto, pessoa, numero=None, confirmar=None):
    """A pergunta vai para a IA com as ferramentas dos apps (ou, sem nenhum app com ferramentas, para o app do assunto
    que responde com a IA dele); devolve (resposta, app). Serve para o WhatsApp. confirmar (uma lista): ganha True quando
    a resposta espera o sim (1.10.0: vai com os botões Sim e Não)."""
    hist = historico(numero) if numero else []
    r = responder_ia("wa:" + whatsapp.canonico(numero) if numero else "wa:", texto, hist, pessoa, "whatsapp", "WhatsApp")
    if r is not None:
        if confirmar is not None and r[2]:
            confirmar.append(True)
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


SIM_NAO = (("sim", "Sim"), ("nao", "Não"))


def enviar(wa, para, pessoa, texto, app=None, botoes=None):
    try:
        if botoes:
            try:  # 1.10.0: o Sim e o Não em botões; se a Meta recusar, vai o texto (escrever sim também vale)
                wa.botoes(para, texto, botoes)
            except whatsapp.ErroWhatsApp as e:
                log("WhatsApp (botões):", e)
                wa.texto(para, texto)
        else:
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
    if not wa_ligado(c):  # 0.17.0: o WhatsApp desligado no CorrerIA: nada é respondido nem guardado
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
    confirmar = []
    resposta, app = responder_pergunta(texto, pessoa, de, confirmar)
    if app:
        guardar_conversa(de, texto, resposta, app)
    enviar(wa, de, pessoa, resposta, app, botoes=SIM_NAO if confirmar else None)


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
    if foto_para_ferramenta(legenda, mime, ultimo_app(de)):
        # 1.17.0: uma foto para guardar (numa tarefa): fica à mão e a IA com as ferramentas decide onde
        try:
            bruto, tipo_meta = wa.midia(info.get("id"))
        except whatsapp.ErroWhatsApp as e:
            registrar("erro", "WhatsApp", str(e))
            return enviar(wa, de, pessoa, f"Não consegui pegar o arquivo: {str(e).rstrip('.')}. Mande de novo, por favor.")
        guardar_foto("wa:" + whatsapp.canonico(de), {"tipo": tipo_meta or mime, "nome": nome or "foto", "b64": f"data:{tipo_meta or mime};base64," + base64.b64encode(bruto).decode()})
        return responder_texto(wa, de, pessoa, legenda or "Mandei uma foto.", ja_registrada=True)
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


# 1.11.0: a última conexão que chegou de fora de casa na porta pública, e se o https fechou, para saber se o problema é o
# caminho até aqui (o roteador, o Duck DNS) ou o certificado
FORA = {"em": None, "ok": None, "erro": "", "via": ""}  # via: porta (a pública) ou tunel (o da Cloudflare)
TUNEL = {"em": None}  # 1.13.0: a última conexão que chegou pelo túnel


def de_fora(ip):
    """Um endereço da internet (não da rede da casa nem deste computador)."""
    try:
        a = ipaddress.ip_address(str(ip).split("%")[0])
    except ValueError:
        return False
    a = a.ipv4_mapped or a if a.version == 6 else a
    return a.is_global


def motivo_tls(e):
    """O porquê de o https não fechar, em poucas palavras."""
    t = str(getattr(e, "reason", "") or e).upper()
    if "CERTIFICATE" in t or "UNKNOWN_CA" in t or "BAD_CERT" in t:
        return "o aparelho recusou o certificado"
    if "WRONG_VERSION" in t or "HTTP_REQUEST" in t:
        return "chegou sem https"
    if "TIMED OUT" in t or isinstance(e, socket.timeout):
        return "demorou demais"
    return "o https não fechou"


def anotar_fora(ip, ok, erro="", via="porta"):
    if de_fora(ip):
        FORA.update(em=agora_iso(), ok=ok, erro=erro, via=via)
        if via == "tunel":
            TUNEL["em"] = FORA["em"]


def certificado_confere(endereco, nome):
    """O certificado é do endereço público (ou de um curinga *.dominio dele)? None: não dá para saber."""
    host = (urllib.parse.urlparse(endereco or "").hostname or "").lower()
    nome = (nome or "").lower()
    if not host or not nome:
        return None
    return host == nome or (nome.startswith("*.") and host.endswith(nome[1:]) and host.count(".") == nome.count("."))


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


# ---------------------------------------------------------------- sensores no Home Assistant (0.14.0)
# Com Sensores ligado (Configurações › Integrações; vem desligado): quantos dias faltam para o certificado de /ssl vencer (o
# Duck DNS renova sozinho; um que não renovou para o WhatsApp e o conector) e se o WhatsApp está conectado (a conta
# conferida na Meta a cada 30 minutos). Publicados quando mudam e a cada 15 minutos; desligado, saem do Home Assistant.
SENSORES = ("sensor.correria_certificado", "binary_sensor.correria_whatsapp")
CONFERIR_A_CADA = 30 * 60
_sensores = {"sig": None, "em": 0.0, "erro": False}
_sensores_trava = threading.Lock()


def validade_certificado(caminho):
    """Quando vence o certificado (o primeiro do arquivo: o do endereço) e para quem é, ou (None, "")."""
    try:
        d = ssl._ssl._test_decode_cert(caminho)  # noqa: SLF001  (só biblioteca padrão: o ssl lê o PEM sem abrir conexão)
        nomes = [v for k, v in d.get("subjectAltName") or () if k == "DNS"]
        return datetime.fromtimestamp(ssl.cert_time_to_seconds(d["notAfter"]), timezone.utc), (nomes[0] if nomes else "")
    except (OSError, ssl.SSLError, KeyError, ValueError):
        return None, ""


def estados_sensores(agora=None):
    agora = agora or datetime.now(timezone.utc)
    c = ler_config()
    cc = certificado()
    vence, dominio = validade_certificado(cc[0]) if cc else (None, "")
    dias = (vence - agora).days if vence else None
    cert = {"state": dias if vence else "unknown", "attributes": {
        "friendly_name": "CorrerIA: certificado", "unit_of_measurement": "d", "device_class": "duration",
        "icon": "mdi:certificate-outline" if dias is None or dias > 14 else "mdi:certificate",
        "vence": vence.astimezone().isoformat(timespec="minutes") if vence else None, "dominio": dominio or None,
        "arquivo": os.path.basename(cc[0]) if cc else None}}
    pronto = bool(c["numero_id"] and c["token"] and c["segredo"])
    on = pronto and wa_ligado(c) and bool(ESTADO["conta"])
    erro = "" if on else ("Falta configurar o WhatsApp." if not pronto else ESTADO.get("conta_erro") or "Ainda não conferido.")
    wpp = {"state": "on" if on else "off", "attributes": {
        "friendly_name": "CorrerIA: WhatsApp", "device_class": "connectivity", "icon": "mdi:whatsapp",
        "nome": (ESTADO["conta"] or {}).get("nome") or None, "respondendo": on and c["ligado"], "erro": erro or None,
        "conferido_em": ESTADO["conta_em"], "ultima_mensagem": ESTADO["ultimo_webhook"]}}
    return {"sensor.correria_certificado": cert, "binary_sensor.correria_whatsapp": wpp}


def publicar_sensores(forcar=False):
    if not TOKEN:
        return
    with _sensores_trava:
        c = ler_config()
        if not c["sensores"]:
            return
        corpos = estados_sensores()
        sig = json.dumps(corpos, sort_keys=True)
        if not forcar and sig == _sensores["sig"] and time.time() - _sensores["em"] < 900:
            return
        try:
            for ent, corpo in corpos.items():
                ha_post("/states/" + ent, corpo)
            _sensores.update(sig=sig, em=time.time(), erro=False)
        except (urllib.error.URLError, OSError, ValueError) as e:
            if not _sensores["erro"]:
                log("Sensores:", e)
            _sensores.update(sig=None, erro=True)


def remover_sensores():
    if not TOKEN:
        return
    with _sensores_trava:
        _sensores.update(sig=None, em=0.0)
        for ent in SENSORES:
            req = urllib.request.Request(HA_API + "/states/" + ent, method="DELETE", headers={"Authorization": f"Bearer {TOKEN}"})
            try:
                urllib.request.urlopen(req, timeout=10).read()
            except (urllib.error.URLError, OSError):
                pass  # já não existia, ou o Home Assistant está fora: some no próximo reinício


def rodada_sensores(agora=None):
    """Uma volta do laço (a cada minuto): confere a conta na Meta a cada 30 minutos e publica o que mudou; desligado, tira
    os sensores uma vez (os que ficaram de quando estava ligado)."""
    c = ler_config()
    if not c["sensores"]:
        if _sensores["sig"] is not False:
            remover_sensores()
            _sensores["sig"] = False
        return
    if _sensores["sig"] is False:
        _sensores["sig"] = None
    agora = agora or time.time()
    if c["numero_id"] and c["token"] and c["segredo"] and agora - _sensores.get("conferido", 0.0) >= CONFERIR_A_CADA:
        _sensores["conferido"] = agora
        try:
            conferir_conta()
        except (whatsapp.ErroWhatsApp, urllib.error.URLError, OSError, ValueError) as e:
            ESTADO.update(conta=None, conta_erro=str(e) or "Sem resposta da Meta.", conta_em=agora_iso())
    publicar_sensores()


def laco_sensores():
    volta = 0
    while True:
        try:
            rodada_sensores()
        except Exception as e:  # noqa: BLE001
            log("Sensores:", e)
        try:  # 1.21.0: uma vez por dia, no horário escolhido, o aviso no celular de quem recebe
            avisar_rondas()
        except Exception as e:  # noqa: BLE001
            log("Aviso das rondas:", e)
        if volta % 60 == 0:  # 1.19.0: de hora em hora, os cômodos sem ronda há tempo demais
            try:
                conferir_rondas()
            except Exception as e:  # noqa: BLE001
                log("Rondas:", e)
        if volta % 60 == 0:  # 1.7.0: de hora em hora (e ao começar), as conversas velhas saem
            try:
                limpar_conversas_velhas()
            except Exception as e:  # noqa: BLE001
                log("Conversas velhas:", e)
        volta += 1
        time.sleep(60)


# ---------------------------------------------------------------- o conector MCP para outras IAs (na porta pública)

INSTRUCOES_MCP = ("CorrerIA: os apps da CorrerIA Code num lugar só. Cada ferramenta tem o app na frente do nome "
                  "(gerencia_..., cronologia_...). Leia antes de gravar: os ids vêm das ferramentas de leitura. Antes de uma "
                  "ferramenta que grava ou apaga, diga à pessoa o que vai ser feito. Datas no formato AAAA-MM-DD; valores em reais.")


def registrar_mcp(quem, f, args, texto, erro):
    """Uma mudança feita por uma IA conectada (MCP) vai para Últimas mensagens."""
    nome = (quem.get("pessoa") or {}).get("nome")
    registrar("erro" if erro else "mcp", quem.get("cliente") + (f" · {nome}" if nome else ""),
              (texto.splitlines()[0] if texto else f["titulo"]), f["app"]["nome"], canal="mcp")


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


MCP = mcp.Servidor(FERR, VERSAO, INSTRUCOES_MCP, ao_gravar=registrar_mcp, lembrancas=lambda: [x["texto"] for x in lembrancas()])
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
        ip = self.client_address[0] if self.client_address else ""
        if isinstance(self.request, ssl.SSLSocket):
            try:
                self.request.do_handshake()
            except (OSError, ssl.SSLError) as e:
                anotar_fora(ip, False, motivo_tls(e))
                raise
        anotar_fora(ip, True)
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


PAINEL_RE = re.compile(r"^/api/hassio_ingress/[A-Za-z0-9_-]{8,128}$")


def painel():
    """1.2.0: o painel da Tela cheia da CronologIA (o A seguir, as Tarefas do dia, o placar, a folha do MemorIA), para a Tela
    cheia daqui, ao lado da Conversa: o endereço da CronologIA no navegador (share/cronologia/integracao.json: tela, da
    CronologIA 1.95.0 ou mais nova) com ?painel=1. Sem a CronologIA (ou sem o endereço ainda), None: sem o botão.
    1.4.0: da CronologIA 1.97.0 em diante, também &conversa=1: os botões da Conversa e do Sair ficam no alto do painel
    (sem a faixa daqui) e a Conversa aberta fica no lugar da folha."""
    try:
        with open(os.path.join(SHARE_DIR, "cronologia", "integracao.json"), encoding="utf-8") as f:
            d = json.load(f)
            tela = str(d.get("tela") or "").rstrip("/")
            versao = str(d.get("versao") or "")
    except (OSError, ValueError, AttributeError):
        return None
    if not PAINEL_RE.fullmatch(tela):
        return None
    return tela + "/?painel=1" + ("&conversa=1" if versao_tupla(versao) >= (1, 97, 0) else "")


def versao_tupla(v):
    """"1.97.0" → (1, 97, 0); o que não é versão, (0,)."""
    m = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", str(v).strip())
    return tuple(int(x) for x in m.groups()) if m else (0,)


def _cert_do_endereco(cc, endereco):
    vence, nome = validade_certificado(cc[0]) if cc else (None, "")
    return {"cert_nome": nome, "cert_vence": vence.isoformat(timespec="seconds") if vence else None,
            "cert_confere": certificado_confere(endereco, nome)}


def estado():
    c = ler_config()
    nums = c["pessoas"]
    pessoas = [{"id": p["id"], "nome": p["nome"], "numero": nums.get(p["id"], "")} for p in pessoas_ha()]
    pessoas += [{"id": k, "nome": k[7:].replace("_", " ").title(), "numero": v, "fora": True} for k, v in nums.items() if k not in {p["id"] for p in pessoas}]
    cc = certificado()
    reg = ler_conversas()["registro"]
    lista = APPS.publicos()
    todas = FERR.todas()
    for a in lista:  # o que cada app faz pelo CorrerIA: quantas ferramentas (e quantas gravam)
        fs = [f for f in todas if f["app"]["app"] == a["app"] and f["nome"] != ferramentas.PERGUNTAR]
        a.update(ferramentas=len(fs), gravam=sum(1 for f in fs if f["grava"]), erro=FERR.erros.get(a["app"], ""))
        # 1.17.0: o que as ferramentas do app recebem (a foto para uma tarefa): a tela mostra o clipe por isso também
        a["guarda"] = sorted({t for f in fs for t in (f.get("anexo") or [])})
    return {
        "versao": VERSAO,
        "config": {"numero_id": c["numero_id"], "token": _fim(c["token"]), "segredo": _fim(c["segredo"]), "verificacao": c["verificacao"],
                   "endereco": c["endereco"], "webhook": (c["endereco"] + "/webhook") if c["endereco"] else "", "ligado": c["ligado"], "whatsapp": wa_ligado(c)},
        "mcp": {"ligado": c["mcp"], "endereco": c["endereco_mcp"], "url": (c["endereco_mcp"] + "/mcp") if c["endereco_mcp"] else "",
                # 1.14.0: o endereço público do conector é dele: o certificado confere com ele, não com o do webhook
                "cert_confere": _cert_do_endereco(cc, c["endereco_mcp"])["cert_confere"],
                "pedidos": AUT.abertos() if c["mcp"] else [], "conexoes": AUT.conexoes()},
        "ia": ESTADO["ia"] or {"ok": None, "erro": "", "em": None, "simulada": AGENTE.simulada, "nome": nome_da_ia(c)},
        "ias": {"lista": ias_ha(), "escolhida": c["ia_entidade"], "pesquisa": c["ia_pesquisa"]},
        "sensores": {"ligado": c["sensores"]},
        # 1.5.0: a casa do Home Assistant (o Assist); disponivel: só dentro do Home Assistant
        "casa": {"ligado": c["casa"], "disponivel": bool(TOKEN)},
        "recolher": c["recolher"], "apagar_dias": c["apagar_dias"],
        # 1.19.0: as rondas: o prazo do aviso, os cômodos atrasados (conferidos de hora em hora) e as últimas 30 do histórico
        "rondas": {"avisar_dias": c["ronda_dias"], "prazos": c["ronda_prazos"], "hora": c["ronda_hora"], "para": c["ronda_para"],
                   **_atrasados_para_tela(ESTADO.get("rondas_atrasadas")),
                   "historico": [{"ronda": rondas.RONDAS[x["ronda"]]["nome"], "onde": x.get("onde") or "", "em": x["em"], "pessoa": x.get("pessoa") or "", "perguntas": x.get("perguntas") or 0} for x in historico_rondas()[-30:][::-1]]},
        "pronto": bool(c["numero_id"] and c["token"] and c["segredo"]),
        "conta": ESTADO["conta"],
        "webhook": {"https": bool(cc), "certificado": os.path.basename(cc[0]) if cc else "", "porta": PORTA_WEBHOOK,
                    "verificado_em": ESTADO["verificado_em"], "ultimo": ESTADO["ultimo_webhook"],
                    # 1.11.0: de quem é o certificado (e se é do endereço público) e a última conexão de fora
                    **_cert_do_endereco(cc, c["endereco"]), "fora": dict(FORA),
                    # 1.13.0: o túnel da Cloudflare (ligado na tela, a porta aberta e a última conexão por ele)
                    "tunel": {"ligado": c["tunel"], "porta": PORTA_TUNEL, "aberto": bool(SERVIDOR_TUNEL["s"]), "em": TUNEL["em"]}},
        "pessoas": pessoas,
        "apps": lista,
        "apps_desligados": APPS.desligados(),  # 1.15.0: os da família sem a opção CorrerIA ligada
        "fala": FALA.status(),
        "fala_tela": FALA.status("wav"),
        "registro": [r for r in reg if canal_de(r) == "whatsapp"][:30],
        "registro_mcp": [r for r in reg if canal_de(r) == "mcp"][:30],
        "aparencia": {"cor": c["cor"], "cor_dia": c["cor_dia"]},
        "atalho": atalho(),
        "uso_ia": USO.resumo(),
        "painel": (pn := painel()),
        "painel_cabecalho": bool(pn and pn.endswith("&conversa=1")),
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


def _limite_velhas():
    """1.7.0: antes disso (ISO), a conversa está parada há mais dias que o escolhido; vazio: nunca apaga."""
    dias = ler_config()["apagar_dias"]
    return (datetime.now() - timedelta(days=dias)).isoformat(timespec="seconds") if dias else ""


def limpar_conversas_velhas():
    """1.7.0: apaga as conversas da tela paradas há mais dias que o escolhido (Configurações › Opções › Conversas) e, no
    WhatsApp, as mensagens mais velhas que isso; devolve quantas conversas e mensagens saíram."""
    lim = _limite_velhas()
    if not lim:
        return 0
    with TRAVA:
        c = ler_json(CONVERSAS_ARQ)
        n = 0
        tela = c.get("tela") if isinstance(c.get("tela"), dict) else {}
        for k in list(tela):
            v = tela[k]
            if isinstance(v, dict) and isinstance(v.get("lista"), list):
                fica = [x for x in v["lista"] if not isinstance(x, dict) or str(x.get("atualizada") or "") >= lim]
                n += len(v["lista"]) - len(fica)
                v["lista"] = fica
                if v.get("atual") and not any(isinstance(x, dict) and x.get("id") == v["atual"] for x in fica):
                    v["atual"] = None
                if not fica:
                    del tela[k]
            elif isinstance(v, list) and not any(isinstance(m, dict) and str(m.get("em") or "") >= lim for m in v):
                n += 1
                del tela[k]
        zap = c.get("conversas") if isinstance(c.get("conversas"), dict) else {}
        for k in list(zap):
            msgs = zap[k] if isinstance(zap[k], list) else []
            fica = [m for m in msgs if isinstance(m, dict) and str(m.get("em") or "") >= lim]
            n += len(msgs) - len(fica)
            if fica:
                zap[k] = fica
            else:
                del zap[k]
        if n:
            c["tela"], c["conversas"] = tela, zap
            _gravar_conversas(c)
    if n:
        log(f"Conversas velhas apagadas: {n}.")
    return n


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
    lim = _limite_velhas()  # 1.7.0: as paradas há mais dias que o escolhido já não aparecem (e saem ao gravar)
    if lim:
        lista = [x for x in lista if str(x.get("atualizada") or "") >= lim]
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


def apps_da_ultima(lista):
    """Os ids dos apps da última resposta da conversa (a da IA com as ferramentas leva os nomes: "InventarIA, ResolvIA")."""
    m = next((m for m in reversed(lista) if m.get("papel") == "ia" and m.get("app")), None)
    nomes = {n.strip() for n in str(m["app"]).split(",")} if m else set()
    return {a["app"] for a in APPS.lista() if a["nome"] in nomes}


def conversar(corpo, pessoa, chave):
    try:
        return _conversar(corpo, pessoa, chave)
    finally:
        PASSOS.pop("tela:" + chave, None)  # 1.27.0: acabou (ou deu erro): a tela para de mostrar o passo


def _conversar(corpo, pessoa, chave):
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
        mini = str(anexo.get("mini") or "")  # 1.26.0: a miniatura que a tela fez (uns 96 px), para ver qual foto foi
        if MINI_RE.match(mini) and len(mini) <= 16000:
            eu["mini"] = mini
        anexo = {"tipo": tipo, "nome": str(anexo.get("nome") or "")[:120], "b64": b64}
    CANAL.arquivo = False
    CANAL.feitos = None
    PASSOS["tela:" + chave] = "Pensando…"
    # 1.27.0: o Desfazer embaixo do «Feito!»: o que o último sim fez (até 10 minutos atrás) vai para a IA, que propõe o
    # contrário (apagar o que criou, pelo id do resultado); a volta também espera o sim, para a pessoa ver o que sai
    antes = FEITOS.pop("tela:" + chave, None)
    desfaz = None
    if corpo.get("desfazer") and not anexo:
        if not antes or time.time() - antes["em"] > DESFAZER_SEG:
            PASSOS.pop("tela:" + chave, None)
            raise ValueError("Não dá mais para desfazer por aqui. Diga o que você quer mudar.")
        desfaz = ("(Quero desfazer o que o app acabou de fazer com o meu sim:\n"
                  + "\n".join(f"- {x['ferramenta']}({json.dumps(x['argumentos'], ensure_ascii=False)}) → {x['resultado']}" for x in antes["acoes"])
                  + "\nProponha as mudanças que desfazem cada uma: apagar o que foi criado (pelo id ou código que o resultado diz; se não diz, "
                    "ache com uma leitura) e voltar o que foi mudado só se a conversa mostra como era antes. O que não der para desfazer, "
                    "diga qual é e por quê, sem inventar.)")
    para_app = None
    if not anexo and corpo.get("para"):  # 1.25.0: «É para o <app>»: só com o arquivo ainda à mão e um app que recebe o tipo dele
        guardado = foto_de("tela:" + chave)
        para_app = next((a for a in APPS.lista() if guardado and a["app"] == corpo.get("para") and a["app"] in FERR.recebem(guardado.get("tipo"))), None)
        if not para_app:
            raise ValueError("O arquivo não está mais à mão. Mande de novo, dizendo de que app é.")
    rd = RONDAS_ATIVAS.get(chave)
    if rd:  # 1.18.0: no meio de uma ronda, a IA sabe de que etapa é a resposta (a pessoa só vê o rótulo)
        hist = hist + [{"papel": "eu", "texto": rondas.contexto(rd["id"], rd["etapas"][rd["i"]], rd["onde"])}]
    if desfaz:
        hist = hist + [{"papel": "eu", "texto": desfaz}]
    r = None
    so_app = None
    # 1.23.0 (o dono, numa ronda: mandou a foto de um consumível e a resposta veio do GerencIA, "zero sentido"): no meio de uma
    # ronda, um arquivo é da etapa: vai para a ferramenta do app da etapa que recebe esse tipo; se quem lê esse tipo é o próprio
    # app da etapa, para ele; senão, a resposta diz que ali não dá. Nunca para outro app.
    et = rondas.etapa_de(rd["id"], rd["etapas"][rd["i"]]) if rd and anexo else None
    na_etapa = bool(et) and et["app"] in (FERR.recebem(tipo) if FERR.tem() else set())
    if et and na_etapa:
        hist = hist + [{"papel": "eu", "texto": rondas.contexto_anexo(et, tipo)}]
    if et and not na_etapa:
        so_app = next((a for a in APPS.lista() if a["app"] == et["app"] and tipo in (a.get("anexos") or [])), None)
    if et and not na_etapa and not so_app:
        guardar_pendente("tela:" + chave, None)
        r = (rondas.sem_anexo(et, tipo), [et["nome_app"]], False)
        anexo = None
    elif anexo and (na_etapa or (not et and foto_para_ferramenta(texto, tipo, ultimo, apps_da_ultima(lista)))):
        # 1.17.0: uma foto para guardar (numa tarefa): fica à mão e a IA com as ferramentas decide onde
        guardar_foto("tela:" + chave, anexo)
        r = responder_ia("tela:" + chave, texto or "Mandei uma foto.", hist, pessoa, "correria", "CorrerIA")
        anexo = None if r is not None else anexo
    elif anexo:
        guardar_pendente("tela:" + chave, None)
    elif para_app:
        # 1.25.0: a pessoa tocou em «É para o <app>» embaixo da resposta de quem leu o arquivo: o mesmo arquivo, que ficou à mão,
        # vai para a IA com as ferramentas, dizendo de que app é (o pedido dela está na mensagem de antes)
        hist = hist + [{"papel": "eu", "texto": f"(O arquivo que a pessoa mandou há pouco não era para o app que respondeu: é para o {para_app['nome']}. "
                                                f"Use só as ferramentas do {para_app['nome']} que recebem o arquivo, com o pedido que ela fez na mensagem do arquivo.)"}]
        r = responder_ia("tela:" + chave, texto, hist, pessoa, "correria", "CorrerIA")
    else:
        r = responder_ia("tela:" + chave, texto, hist, pessoa, "correria", "CorrerIA")
    confirmar = False
    leu = None  # o arquivo que foi para o app que lê (a `rota`), para oferecer os outros apps
    if r is not None:  # a IA com as ferramentas dos apps
        resposta, app, confirmar = r[0], ({"app": "_ia", "nome": ", ".join(r[1])} if r[1] else None), r[2]
    else:
        app = so_app or APPS.escolher(texto, ultimo, tipo=tipo)
        if not app:
            resposta = NAO_LE if (tipo and APPS.lista()) else SEM_APP
        else:
            PASSOS["tela:" + chave] = f"O {app['nome']} está lendo o arquivo…" if anexo else f"Perguntando ao {app['nome']}…"
            try:
                resposta = APPS.perguntar(app, texto, hist, pessoa, timeout=300 if anexo else 150, anexo=anexo, canal="correria")
                leu = anexo
            except apps.ErroApp as e:
                log("CorrerIA:", e)
                resposta = f"Não consegui falar com o {app['nome']} agora. {e}"
    resp = {"papel": "ia", "texto": whatsapp.para_whatsapp(resposta), "em": agora_iso()}
    if confirmar:  # 1.10.0: espera o sim: a tela mostra os botões Sim e Não embaixo
        resp["confirmar"] = True
    if app:
        resp.update(app=app["nome"], app_id=app["app"])
    PASSOS.pop("tela:" + chave, None)
    if getattr(CANAL, "feitos", None):  # o sim fez alguma coisa: dá para desfazer por 10 minutos
        FEITOS["tela:" + chave] = {"em": time.time(), "acoes": CANAL.feitos}
        resp["desfazer"] = True
        for k in [k for k, v in FEITOS.items() if time.time() - v["em"] > DESFAZER_SEG]:
            FEITOS.pop(k, None)
    usado = next((m["anexo"] for m in reversed(lista + [eu]) if m.get("papel") == "eu" and m.get("anexo")), None)
    if usado and (leu or getattr(CANAL, "arquivo", False)):
        resp["arquivo"] = usado  # 1.26.0: a resposta veio da leitura deste arquivo
    if leu and not rd and FERR.tem():
        # 1.25.0 (o dono: "se o correria não encontra a info em um app, não seria prudente dar a opção de indicar se o tema é em
        # outro app?"): o arquivo fica à mão e a resposta leva os outros apps que recebem esse tipo, para um toque mandar para lá
        outros = [{"app": a["app"], "nome": a["nome"]} for a in APPS.lista() if a["app"] in FERR.recebem(tipo) and a["app"] != app["app"]]
        if outros:
            guardar_foto("tela:" + chave, leu)
            resp["outros"] = outros
    lista += [eu, resp]
    _gravar_tela(chave, lista)
    return {"mensagens": lista[-MAX_TELA:], "conversa": conversa_aberta(chave)}


# ---------- Rondas (1.18.0): um roteiro fixo pelos apps, uma etapa de cada vez, dentro da Conversa da tela ----------
# A ronda em andamento de cada login fica na memória (some ao reiniciar o app: é só recomeçar). Cada etapa entra na conversa
# como uma mensagem da pessoa (só o rótulo: "Ronda da casa · Sala · Tarefas (1 de 4)") e a resposta da IA, que leu o app da
# etapa e faz a pergunta; o que a pessoa responder segue pela Conversa de sempre, com o sim antes de qualquer mudança.
RONDAS_ATIVAS = {}
# 1.30.0: as rondas que a pessoa criou ou mudou (Mais › Rondas › Editar), em /data/rondas_minhas.json; o rondas.montar põe por
# cima das daqui. avancado: o modo avançado (escrever o que a IA lê e criar etapas livres), desligado de início.
MINHAS_ARQ = os.path.join(DATA_DIR, "rondas_minhas.json")
TRAVA_MINHAS = threading.Lock()


def ler_minhas():
    m = ler_json(MINHAS_ARQ)
    return {"avancado": m.get("avancado") is True, "rondas": m.get("rondas") if isinstance(m.get("rondas"), dict) else {}}


def montar_rondas():
    rondas.montar(ler_minhas())


def _leituras():
    """As ferramentas de leitura ligadas agora, para as etapas livres: {id: {app, nome_app, titulo}} (sem as que pedem arquivo)."""
    return {f["id"]: {"app": f["app"]["app"], "nome_app": f["app"]["nome"], "titulo": f["titulo"]}
            for f in FERR.todas() if not f["grava"] and not f.get("anexo")}


def comodos_da_casa(pessoa=None):
    """Os nomes dos cômodos do InventarIA (para o Quando perguntar de uma etapa), ou [] sem ele."""
    try:
        inv = rondas._resumo_inventario(FERR, FERR.todas(), pessoa)
    except Exception:  # noqa: BLE001
        return []
    return [str(c.get("nome")) for c in inv.get("comodos") or [] if isinstance(c, dict) and c.get("nome")][:60]


def editor_rondas():
    m, todas = ler_minhas(), FERR.todas()
    ids = {f["id"] for f in todas}
    return {"avancado": m["avancado"], "rondas": rondas.para_editor(ids), "comodos": comodos_da_casa(),
            "catalogo": [dict(c, ligada=all(f in ids for f in (c["precisa"], *c["tambem"]))) for c in rondas.catalogo()],
            "leituras": [dict(v, id=k) for k, v in sorted(_leituras().items(), key=lambda kv: (kv[1]["nome_app"], kv[1]["titulo"]))] if m["avancado"] else [],
            "max": {"etapas": rondas.MAX_ETAPAS, "pergunta": rondas.MAX_PERGUNTA, "pedido": rondas.MAX_PEDIDO, "quando": rondas.MAX_QUANDO}}


def editar_rondas(c):
    """{acao: salvar, ronda: {id?, nome, onde, etapas}} | {acao: apagar | restaurar, id} | {acao: avancado, liga}."""
    acao = str(c.get("acao") or "")
    with TRAVA_MINHAS:
        m = ler_minhas()
        if acao == "avancado":
            m["avancado"] = c.get("liga") is True
        elif acao == "salvar":
            r = c.get("ronda") if isinstance(c.get("ronda"), dict) else {}
            rid = str(r.get("id") or "")
            if rid and rid not in rondas.RONDAS:
                raise ValueError("Essa ronda não existe mais.")
            if not rid:
                if len([k for k in m["rondas"] if k not in rondas.PADRAO]) >= rondas.MAX_RONDAS:
                    raise ValueError(f"Já são {rondas.MAX_RONDAS} rondas suas. Apague alguma.")
                rid = rondas.nova_id(set(rondas.RONDAS) | set(m["rondas"]))
            tem_quando = r.get("onde") is True and any(isinstance(x, dict) and str(x.get("quando") or "").strip() for x in r.get("etapas") or [])
            m["rondas"][rid] = rondas.conferir_ronda(r, m["rondas"].get(rid), m["avancado"], _leituras() if m["avancado"] else None,
                                                     comodos_da_casa() if tem_quando else None)
        elif acao in ("apagar", "restaurar"):
            rid = str(c.get("id") or "")
            if rid not in m["rondas"] or (acao == "apagar") != (rid not in rondas.PADRAO):
                raise ValueError("Essa ronda não existe mais.")
            m["rondas"].pop(rid)
        else:
            raise ValueError("Pedido inválido.")
        gravar_arquivo(MINHAS_ARQ, json.dumps(m, ensure_ascii=False))
        montar_rondas()
    if acao != "avancado":  # uma ronda em andamento era a de antes: acaba
        RONDAS_ATIVAS.clear()
    return editor_rondas()


montar_rondas()
HORA_RE = re.compile(r"^([01]\d|2[0-3]):(00|30)$")
PESSOA_RE = re.compile(r"^person\.[a-z0-9_]+$")
MAX_RONDAS = 500
TRAVA_RONDAS = threading.Lock()


def historico_rondas():
    h = ler_json(RONDAS_ARQ).get("historico")
    return [x for x in h if isinstance(x, dict) and x.get("em") and x.get("ronda") in rondas.RONDAS] if isinstance(h, list) else []


def anotar_ronda(rid, onde, pessoa, perguntas):
    """Uma ronda concluída vai para o histórico (/data/rondas.json, as últimas 500)."""
    with TRAVA_RONDAS:
        h = historico_rondas() + [{"ronda": rid, "onde": onde, "em": agora_iso(), "pessoa": str((pessoa or {}).get("nome") or ""), "perguntas": perguntas}]
        avisado = ler_json(RONDAS_ARQ).get("avisado")
        gravar_arquivo(RONDAS_ARQ, json.dumps({"historico": h[-MAX_RONDAS:], **({"avisado": avisado} if avisado else {})}, ensure_ascii=False))


def _dias_desde(iso, agora=None):
    try:
        return max(0, ((agora or datetime.now()).date() - datetime.fromisoformat(str(iso)).date()).days)
    except ValueError:
        return None


def ultimas_rondas(rid="casa", agora=None):
    """{cômodo: há quantos dias foi a última ronda concluída ali}."""
    out = {}
    for x in historico_rondas():
        d = _dias_desde(x["em"], agora) if x.get("ronda") == rid and x.get("onde") else None
        if d is not None:
            out[x["onde"]] = d if x["onde"] not in out else min(out[x["onde"]], d)
    return out


def ultima_ronda(rid, agora=None):
    """Há quantos dias foi a última vez desta ronda (em qualquer cômodo), ou None."""
    dias = [d for d in (_dias_desde(x["em"], agora) for x in historico_rondas() if x.get("ronda") == rid) if d is not None]
    return min(dias) if dias else None


def ultimas_de_todas(agora=None):
    """{id da ronda: {cômodo, ou "" numa ronda sem cômodo: há quantos dias}}."""
    out = {}
    for x in historico_rondas():
        d = _dias_desde(x["em"], agora)
        if d is not None:
            r, k = out.setdefault(x["ronda"], {}), str(x.get("onde") or "")
            r[k] = d if k not in r else min(r[k], d)
    return out


def atrasadas_todas(disps, agora=None):
    """1.32.0: cada ronda tem o seu prazo. [{ronda, nome, onde, dias, prazo}]: numa ronda por cômodo, os cômodos sem ronda há
    mais do que o prazo dela (um que nunca teve só conta depois da primeira vez dessa ronda); numa sem cômodo, a própria ronda
    (onde ""), também quando nunca foi feita: o aviso dela só existe porque a pessoa ligou."""
    prazos, out = ler_config()["ronda_prazos"], []
    for x in disps or []:
        limite = prazos.get(x["id"], 0)
        if not limite:
            continue
        if x.get("sem_onde"):
            d = ultima_ronda(x["id"], agora)
            if d is None or d > limite:
                out.append({"ronda": x["id"], "nome": x["nome"], "onde": "", "dias": d, "prazo": limite})
        else:
            ult = ultimas_rondas(x["id"], agora)
            out += [{"ronda": x["id"], "nome": x["nome"], "onde": c, "dias": ult.get(c), "prazo": limite}
                    for c in (x.get("onde") or []) if ult and (ult.get(c) is None or ult[c] > limite)]
    return out


def _atrasados_para_tela(atras):
    """atrasados: os nomes (o cômodo ou, sem cômodo, a ronda); atrasados_de: [{ronda, onde}], para a tela saber de qual ronda é."""
    atras = atras or []
    return {"atrasados": [a["onde"] or a.get("nome") or "" for a in atras], "atrasados_de": [{"ronda": a.get("ronda", "casa"), "onde": a["onde"]} for a in atras]}


def texto_do_aviso(atras):
    """O texto do aviso (no sino e no celular): uma frase por ronda atrasada. Só a Ronda da casa: a frase de sempre."""
    frases, vistos = [], []
    for a in atras:
        if a.get("ronda", "casa") in vistos:
            continue
        rid = a.get("ronda", "casa")
        vistos.append(rid)
        grupo = [b for b in atras if b.get("ronda", "casa") == rid]
        if a["onde"]:
            f = texto_atrasados([b["onde"] for b in grupo], a.get("prazo") or ler_config()["ronda_prazos"].get(rid, 0))
            frases.append(f if rid == "casa" else f"{a.get('nome') or 'Ronda'}: {f[0].lower()}{f[1:]}")
        else:
            frases.append(f"{a.get('nome') or 'Ronda'}: " + ("ainda não foi feita." if a.get("dias") is None else f"sem fazer há mais de {a.get('prazo')} dias."))
    return " ".join(frases)


def _titulo_do_aviso(atras):
    return "Ronda da casa" if all(a.get("ronda", "casa") == "casa" for a in atras) else "Rondas"


def rondas_atrasadas(comodos, agora=None):
    """Os cômodos sem ronda há mais de ronda_dias (com o aviso ligado). Um cômodo que nunca teve ronda só conta depois da
    primeira ronda da casa: numa instalação nova não há do que avisar."""
    return atrasadas_todas([{"id": "casa", "nome": rondas.RONDAS["casa"]["nome"], "onde": list(comodos)}], agora)


def conferir_rondas():
    """De hora em hora (e quando uma ronda acaba ou o prazo muda): guarda os atrasados para a tela e avisa no sino do Home
    Assistant (um aviso só, que muda com a lista e some quando não há mais nenhum)."""
    atras = atrasadas_todas(rondas.disponiveis(FERR) if FERR.tem() else [])
    antes = ESTADO.get("rondas_atrasadas")
    ESTADO["rondas_atrasadas"] = atras
    nomes = [(a["ronda"], a["onde"]) for a in atras]
    if not TOKEN or nomes == [(a.get("ronda", "casa"), a["onde"]) for a in antes or []]:
        return atras
    if nomes:
        _tentar(ha_post, "/services/persistent_notification/create",
                {"notification_id": "correria_ronda", "title": "CorrerIA · " + _titulo_do_aviso(atras), "message": texto_do_aviso(atras)})
    elif antes:
        _tentar(ha_post, "/services/persistent_notification/dismiss", {"notification_id": "correria_ronda"})
    return atras


_celulares_cache = {"t": 0, "v": None}


def pessoas_com_celular(forcar=False):
    """As pessoas da casa com os celulares de cada uma (notify.mobile_app_*), guardadas por 60 s. Fora do Home Assistant, []."""
    if not TOKEN:
        return []
    if not forcar and _celulares_cache["v"] is not None and time.time() - _celulares_cache["t"] < 60:
        return _celulares_cache["v"]
    v = avisos.pessoas(ha_get("/states"), ha_get("/services"), lambda m: ha_texto("/template", {"template": m}))
    _celulares_cache.update(t=time.time(), v=v)
    return v


def ha_texto(caminho, corpo, timeout=15):
    """Um POST ao Home Assistant que responde texto (o /api/template)."""
    req = urllib.request.Request(HA_API + caminho, data=json.dumps(corpo).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def mandar_aviso(alvos, titulo, mensagem, tag):
    """Manda para estes celulares; devolve quantos o Home Assistant aceitou. O toque abre o app (/app/<slug>)."""
    n = 0
    for alvo in alvos:
        try:
            ha_post(f"/services/notify/{alvo}", avisos.corpo(titulo, mensagem, tag, atalho()))
            n += 1
            log(f"Aviso (Rondas) para {alvo}")
        except Exception as e:  # noqa: BLE001
            log(f"Aviso (Rondas) para {alvo}:", e)
    return n


def texto_atrasados(nomes, dias):
    return ((f"{nomes[0]} está" if len(nomes) == 1 else f"{len(nomes)} cômodos estão") + f" sem ronda há mais de {dias} dias"
            + ("." if len(nomes) == 1 else ": " + ", ".join(nomes[:8]) + ("…" if len(nomes) > 8 else ".")))


def avisar_rondas(agora=None):
    """Uma vez por dia, a partir do horário escolhido: se há cômodo atrasado, avisa os celulares de quem recebe. Devolve
    quantos avisos saíram (None: não era a hora, ou já foi hoje)."""
    c = ler_config()
    agora = agora or datetime.now()
    hoje = agora.strftime("%Y-%m-%d")
    if not TOKEN or not any(c["ronda_prazos"].values()) or not c["ronda_para"] or agora.strftime("%H:%M") < c["ronda_hora"] or ESTADO.get("ronda_avisado") == hoje:
        return None
    if ler_json(RONDAS_ARQ).get("avisado") == hoje:  # o app reiniciou depois de avisar
        ESTADO["ronda_avisado"] = hoje
        return None
    atras = conferir_rondas()
    ESTADO["ronda_avisado"] = hoje
    with TRAVA_RONDAS:
        d = ler_json(RONDAS_ARQ)
        gravar_arquivo(RONDAS_ARQ, json.dumps({"historico": d.get("historico") if isinstance(d.get("historico"), list) else [], "avisado": hoje}, ensure_ascii=False))
    if not atras:
        return 0
    alvos = [cel for p in pessoas_com_celular(True) if p["id"] in c["ronda_para"] for cel in p["celulares"]]
    return mandar_aviso(list(dict.fromkeys(alvos)), "🧭 " + _titulo_do_aviso(atras), texto_do_aviso(atras), "correria-ronda")


def testar_aviso_ronda(usuario):
    """O Testar no meu celular: um aviso de exemplo para os celulares de quem está na tela."""
    eu = next((p for p in pessoas_com_celular(True) if usuario and p["usuario"] == usuario), None)
    if not eu:
        raise ValueError("Você não é uma pessoa da casa no Home Assistant.")
    if not eu["celulares"]:
        raise ValueError("Sem celular ligado a você no Home Assistant.")
    if not mandar_aviso(eu["celulares"], "🧭 Ronda da casa", "Teste: é assim que chega o aviso de cômodo sem ronda.", "correria-ronda-teste"):
        raise ValueError("O Home Assistant não aceitou o aviso.")
    return {"ok": True, "celulares": len(eu["celulares"])}


def pessoas_do_aviso(usuario):
    """Para a tela: {pessoas: [{id, nome, celular, eu}]} ou {erro}."""
    try:
        return {"pessoas": [{"id": p["id"], "nome": p["nome"], "celular": bool(p["celulares"]), "eu": bool(usuario) and p["usuario"] == usuario} for p in pessoas_com_celular()]}
    except (urllib.error.URLError, OSError, ValueError) as e:
        log("Não consegui ver os celulares das pessoas:", e)
        return {"erro": "Não consegui ver as pessoas da casa."}


def rondas_estado(chave, pessoa=None, listar=False):
    """{ativa: a ronda em andamento ou None, rondas: as que dá para fazer (só com listar: chama o InventarIA)}."""
    r = RONDAS_ATIVAS.get(chave)
    ativa = None
    if r:
        e = rondas.etapa_de(r["id"], r["etapas"][r["i"]])
        ativa = {"id": r["id"], "nome": rondas.RONDAS[r["id"]]["nome"], "onde": r["onde"], "n": r["i"] + 1, "total": len(r["etapas"]),
                 "etapa": e["titulo"], "grupo": e["grupo"], "app": e["nome_app"]}
    ult = ultimas_rondas()
    c = ler_config()
    out = {"ativa": ativa, "feitos": [c_ for c_, d in ult.items() if d == 0], "ultimas": ult, "avisar_dias": c["ronda_dias"],
           "ultimas_de": ultimas_de_todas(), "prazos": c["ronda_prazos"]}  # 1.32.0: de cada ronda
    if listar:
        out["rondas"] = rondas.disponiveis(FERR, pessoa) if FERR.tem() else []
        out.update(_atrasados_para_tela(atrasadas_todas(out["rondas"])))
    return out


def ronda_passo(corpo, pessoa, chave):
    """Começar, ir para a próxima etapa, voltar ou sair de uma ronda. Devolve a conversa e o estado da ronda."""
    acao = str(corpo.get("acao") or "")
    r = RONDAS_ATIVAS.get(chave)
    if acao == "sair":
        RONDAS_ATIVAS.pop(chave, None)
        return {"mensagens": conversa_tela(chave)[-MAX_TELA:], "conversa": conversa_aberta(chave), "ronda": rondas_estado(chave)}
    if acao == "iniciar":
        rid = str(corpo.get("ronda") or "")
        onde = " ".join(str(corpo.get("onde") or "").split())[:60]
        disp = next((x for x in rondas.disponiveis(FERR, pessoa) if x["id"] == rid), None) if FERR.tem() else None
        if not disp:
            raise ValueError("Esta ronda não está disponível: ligue o CorrerIA nos apps (Mais › Configurações › Integrações).")
        if disp["sem_onde"]:
            onde = ""
        elif not onde or (disp["onde"] and onde not in disp["onde"]):
            raise ValueError("Escolha o cômodo.")
        # 1.32.0: o Quando perguntar de cada etapa: as que não valem neste cômodo ficam de fora
        etapas = [e["id"] for e in disp["etapas"] if rondas.vale_em(rondas.etapa_de(rid, e["id"]), onde)]
        if not etapas:
            raise ValueError("Nenhuma pergunta desta ronda vale neste cômodo.")
        r = RONDAS_ATIVAS[chave] = {"id": rid, "onde": onde, "i": 0, "etapas": etapas, "opcoes": disp["opcoes"]}
    elif not r:
        raise ValueError("Nenhuma ronda em andamento.")
    elif acao == "proxima":
        if r["i"] + 1 >= len(r["etapas"]):  # a última etapa: o cômodo fica feito e a ronda espera o próximo
            RONDAS_ATIVAS.pop(chave, None)
            lista = conversa_tela(chave)
            nome = rondas.RONDAS[r["id"]]["nome"]
            lista += [{"papel": "eu", "texto": f"{r['onde'] or nome} · concluída", "em": agora_iso(), "ronda": True},
                      {"papel": "ia", "texto": "Ronda concluída. Quando quiser, escolha o próximo cômodo." if r["onde"] else f"{nome} concluída.",
                       "em": agora_iso(), "app": "CorrerIA", "app_id": "_ia"}]
            _gravar_tela(chave, lista)
            anotar_ronda(r["id"], r["onde"], pessoa, len(r["etapas"]))
            threading.Thread(target=lambda: _tentar(conferir_rondas), daemon=True).start()
            est = rondas_estado(chave, pessoa, listar=True)
            if r["onde"]:
                est["proximo"] = r["id"]  # a tela abre a escolha do próximo cômodo
            return {"mensagens": lista[-MAX_TELA:], "conversa": conversa_aberta(chave), "ronda": est}
        r["i"] += 1
    elif acao == "voltar":
        r["i"] = max(0, r["i"] - 1)
    else:
        raise ValueError("acao vale iniciar, proxima, voltar ou sair.")
    eid, total = r["etapas"][r["i"]], len(r["etapas"])
    guardar_pendente("tela:" + chave, None)  # mudou de etapa: o que esperava o sim da anterior não vale mais
    lista = conversa_tela(chave)
    hist = [{"papel": m.get("papel"), "texto": m.get("texto") or ""} for m in lista][-MAX_HISTORICO:]
    eu = {"papel": "eu", "em": agora_iso(), "ronda": True}
    ped = rondas.pedido(r["id"], eid, r["onde"], FERR.todas(), r["i"] + 1, total, r.get("opcoes") or ())
    etapa = rondas.etapa_de(r["id"], eid)
    if ped is None:  # a etapa só pergunta: sem a IA, na hora
        texto, nomes, confirmar = rondas.arrumar("", r["id"], eid, r["onde"]), [etapa["nome_app"]], False
    else:
        resp = responder_ia("tela:" + chave, ped, hist, pessoa, "correria", "CorrerIA")
        texto, nomes, confirmar = resp if resp is not None else ("", [etapa["nome_app"]], False)
        if str(texto or "").strip() in ia.NAO_DEU:
            # 1.31.1 (o dono mandou o print: «Não consegui responder agora. Pode perguntar de outro jeito?» em cima da
            # pergunta da etapa): a IA não conseguiu ler o app; a etapa é um guia e segue com a pergunta (e o Abrir no app).
            # 1.35.1: e com a linha do app que diz que a leitura não deu (rondas.vazio)
            log(f"Ronda: a IA não leu o {etapa['nome_app']} na etapa {eid}: {texto}")
            texto, nomes, confirmar = "", [etapa["nome_app"]], False
        achou, texto = rondas.total(texto)  # 1.21.0: sem nada ali, as perguntas que não fazem sentido saem
        # 1.35.1: o que o app diz se a resposta não deixar texto (da etapa que leu); sem IA nenhuma (resp None), a etapa é só o guia
        sem_texto = rondas.vazio(r["id"], eid, achou) if resp is not None else None
        r["etapas"] = rondas.sem_o_que_perguntar(r["id"], r["etapas"], r["i"], achou)
        junta = rondas.junta_com(r["id"], r["etapas"], r["i"], achou)
        if junta is not None:  # 1.21.1: nada ali: a pergunta seguinte do grupo vem na mesma mensagem (a etapa que leu sai)
            r["etapas"] = r["etapas"][:r["i"]] + r["etapas"][junta:]
            eid = r["etapas"][r["i"]]
            etapa = rondas.etapa_de(r["id"], eid)
        texto = rondas.arrumar(texto, r["id"], eid, r["onde"], perguntar=junta is not None or not (achou == 0 and etapa.get("se_tem")), vazio=sem_texto)
        texto = rondas.e_mais(texto, achou)
    ia_msg = {"papel": "ia", "texto": whatsapp.para_whatsapp(texto), "em": agora_iso(), "app": ", ".join(nomes) or "CorrerIA", "app_id": "_ia"}
    if confirmar:
        ia_msg["confirmar"] = True
    # 1.22.0: o botão embaixo da mensagem abre o app da etapa, já no lugar. 1.22.2 (o dono: "é só uma pergunta e ele já
    # mostrou o abrir"): só na etapa que leu o app e mostrou o que há lá; numa pergunta só, não
    link = rondas.abrir(r["id"], eid, r["onde"], {a["app"]: a.get("painel") for a in APPS.lista()}) if ped is not None else None
    if link:
        ia_msg["abrir"] = link
    eu["texto"] = rondas.rotulo(r["id"], eid, r["onde"], r["i"] + 1, len(r["etapas"]))
    lista += [eu, ia_msg]
    _gravar_tela(chave, lista)
    return {"mensagens": lista[-MAX_TELA:], "conversa": conversa_aberta(chave), "ronda": rondas_estado(chave)}


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
        if n > (42 * 1024 * 1024 if self.caminho() == "/api/dados/importar" else 22 * 1024 * 1024 if self.caminho() == "/api/conversa"
                else 1024 * 1024):  # a conversa leva foto ou PDF; o Importar, o .zip do backup
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
                                     "conversa": conversa_aberta(chave), "ronda": rondas_estado(chave)})
        if p == "/api/dados":  # 1.29.0: os backups da pasta share e as versões anteriores
            return self.enviar(200, dados_estado())
        if p == "/api/dados/exportar":  # o .zip com tudo, para baixar
            corpo = exportar_zip()
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Disposition", f'attachment; filename="{copias.nome_do_arquivo()}"')
            self.send_header("Content-Length", str(len(corpo)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return self.wfile.write(corpo)
        if p == "/api/conversa/passo":  # 1.27.0: o que a IA está fazendo agora nesta conversa
            return self.enviar(200, {"passo": PASSOS.get("tela:" + pessoa_da_tela(self.headers)[1], "")})
        if p == "/api/lembrancas":  # 1.27.0: o que a casa pediu para a IA lembrar
            return self.enviar(200, {"lembrancas": lembrancas(), "max": MAX_LEMBRANCAS})
        if p == "/api/rondas/editor":  # 1.30.0: as rondas para editar, as etapas prontas e o modo avançado
            return self.enviar(200, editor_rondas())
        if p == "/api/rondas":  # 1.18.0: as rondas que dá para fazer agora (os cômodos vêm do InventarIA)
            pessoa, chave = pessoa_da_tela(self.headers)
            return self.enviar(200, dict(rondas_estado(chave, pessoa, listar=True), aviso=pessoas_do_aviso(self.headers.get("X-Remote-User-Id") or "")))
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
                return self.enviar(200, dict(conversar(c, pessoa, chave), ronda=rondas_estado(chave)))
            if p.startswith("/api/dados/"):  # 1.29.0: backup, restaurar, importar e começar do zero
                if p == "/api/dados/backup":
                    fazer_backup()
                elif p == "/api/dados/restaurar":
                    restaurar_dados(str(c.get("origem") or ""), str(c.get("nome") or ""))
                elif p == "/api/dados/importar":
                    try:
                        bruto = base64.b64decode(str(c.get("zip") or "").split(",")[-1], validate=True)
                    except ValueError:
                        raise copias.ErroDados("Não consegui abrir esse arquivo. É o .zip de um backup do CorrerIA?") from None
                    trocar_dados(bruto, "importar")
                elif p == "/api/dados/zerar":
                    if c.get("confirmar") is not True:
                        raise ValueError("Confirme para começar do zero.")
                    comecar_do_zero()
                else:
                    return self.enviar(404, {"erro": "Não achei."})
                return self.enviar(200, dados_estado())
            if p == "/api/lembrancas":  # 1.27.0: {acao: nova, texto} ou {acao: apagar, id}
                if c.get("acao") == "apagar":
                    esquecer(str(c.get("id") or ""))
                else:
                    lembrar(c.get("texto"), pessoa_da_tela(self.headers)[0])
                return self.enviar(200, {"lembrancas": lembrancas(), "max": MAX_LEMBRANCAS})
            if p == "/api/rondas/editor":  # 1.30.0: salvar, apagar, voltar ao original, o modo avançado
                return self.enviar(200, editar_rondas(c))
            if p == "/api/ronda/testar":  # 1.21.0: o Testar no meu celular
                return self.enviar(200, testar_aviso_ronda(self.headers.get("X-Remote-User-Id") or ""))
            if p == "/api/ronda":  # 1.18.0: começar, próxima etapa, voltar ou sair
                pessoa, chave = pessoa_da_tela(self.headers)
                return self.enviar(200, ronda_passo(c, pessoa, chave))
            if p in ("/api/conversa/limpar", "/api/conversa/nova", "/api/conversa/abrir", "/api/conversa/apagar"):
                RONDAS_ATIVAS.pop(pessoa_da_tela(self.headers)[1], None)  # 1.18.0: a ronda é da conversa em que começou
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
            if p == "/api/ia/verificar":  # 0.16.1: as IAs do Home Assistant de novo; o erro da última chamada sai
                _ias_cache.update(t=0.0, v=None)
                ESTADO["ia"] = None
                return self.enviar(200, estado())
            if p == "/api/registro/limpar":  # 0.15.0: só o da aba (WhatsApp ou MCP)
                canal = "mcp" if c.get("canal") == "mcp" else "whatsapp"
                with TRAVA:
                    cv = ler_conversas()
                    cv["registro"] = [r for r in cv["registro"] if canal_de(r) != canal]
                    _gravar_conversas(cv)
                return self.enviar(200, estado())
            return self.enviar(404, {"erro": "não encontrado"})
        except (ValueError, LookupError, whatsapp.ErroWhatsApp) as e:
            return self.enviar(400, {"erro": str(e)})
        except Exception as e:  # noqa: BLE001
            log("Erro", p, e)
            return self.enviar(500, {"erro": str(e)})


class WebhookTunel(Webhook):
    """1.13.0: a porta pública para o túnel da Cloudflare (o app Cloudflared do Home Assistant): as mesmas rotas, em http e
    só na rede de casa. O https e o certificado são os da Cloudflare, na porta 443 (a única que o Claude aceita), sem abrir
    porta no roteador. Quem chamou vem no CF-Connecting-IP, que só a Cloudflare põe."""

    def setup(self):
        self.request.settimeout(15)
        BaseHTTPRequestHandler.setup(self)

    def parse_request(self):
        ok = super().parse_request()
        if ok:
            anotar_fora((self.headers.get("CF-Connecting-IP") or "").strip(), True, via="tunel")
        return ok

    def base(self):
        """Pelo túnel é sempre https (o da Cloudflare); sem um nome de verdade no Host, o endereço público."""
        host = re.sub(r"[^A-Za-z0-9.\-:\[\]]", "", self.headers.get("Host") or "")
        nome = host.rsplit(":", 1)[0].strip("[]") if host.count(":") <= 1 or host.startswith("[") else host
        if "." not in nome or _e_ip(nome):
            host = urllib.parse.urlparse(ler_config()["endereco_mcp"]).netloc or host or f"localhost:{PORTA_TUNEL}"
        return f"https://{host}"


def _e_ip(t):
    try:
        ipaddress.ip_address(t)
        return True
    except ValueError:
        return False


SERVIDOR_TUNEL = {"s": None}
TRAVA_TUNEL = threading.Lock()


def ligar_tunel(ligar):
    """Abre (ou fecha) a porta do túnel. Ela não vai para a internet: o app Cloudflared chega nela pela rede de casa."""
    with TRAVA_TUNEL:
        s = SERVIDOR_TUNEL["s"]
        if ligar and not s:
            try:
                s = ThreadingHTTPServer(("0.0.0.0", PORTA_TUNEL), WebhookTunel)
            except OSError as e:
                log("Túnel: não consegui abrir a porta", PORTA_TUNEL, e)
                return
            s.daemon_threads = True
            SERVIDOR_TUNEL["s"] = s
            threading.Thread(target=s.serve_forever, daemon=True).start()
            log(f"Túnel: porta {PORTA_TUNEL} aberta (http, para o app Cloudflared)")
        elif not ligar and s:
            SERVIDOR_TUNEL["s"] = None
            threading.Thread(target=lambda: (s.shutdown(), s.server_close()), daemon=True).start()
            log("Túnel: porta fechada")


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    c = ler_config()  # cria o token de verificação na primeira vez
    hook = ServidorWebhook(("0.0.0.0", PORTA_WEBHOOK), Webhook)
    threading.Thread(target=hook.serve_forever, daemon=True).start()
    ligar_tunel(c["tunel"])
    migrar_lembrancas()  # 1.31.0: a memória é de todos os apps, na pasta share
    threading.Thread(target=laco_sensores, daemon=True).start()
    cc = certificado()
    log(f"CorrerIA {VERSAO}: tela na porta {PORTA}; webhook e MCP na porta {PORTA_WEBHOOK} ({'https, ' + os.path.basename(cc[0]) if cc else 'http, sem certificado em ' + SSL_DIR})")
    tela = ThreadingHTTPServer(("0.0.0.0", PORTA), Tela)
    tela.daemon_threads = True
    tela.serve_forever()


if __name__ == "__main__":
    main()
