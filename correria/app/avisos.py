"""Avisos no celular (1.21.0; Mais › Rondas › Aviso), como nos outros apps da família: o app olha para a pessoa, nunca
para um aparelho escolhido aqui. Os celulares de uma pessoa são os apps do Home Assistant entre os rastreadores dela
(Configurações › Pessoas); o serviço de aviso de cada um (notify.mobile_app_*) tem o nome do aparelho, não o do
rastreador (device_tracker.meu_celular pode ser notify.mobile_app_pixel_8). A mesma regra do avisos.py do GerencIA e do
phones.js do ResolvIA; aqui o aparelho de cada rastreador vem de um modelo (POST /api/template), porque o CorrerIA só
fala com a API REST do Home Assistant. Só biblioteca padrão do Python.
"""
import json
import re
import unicodedata

CELULAR_RE = re.compile(r"^mobile_app_[a-z0-9_]+$")
RASTREADOR_RE = re.compile(r"^device_tracker\.[a-z0-9_]+$")
APP_AVISO, ICONE_AVISO = "CorrerIA", "mdi:lightning-bolt"
# o nome do aparelho de cada rastreador e se ele é do app Home Assistant (o identificador mobile_app)
MODELO = ("{% set o = namespace(l=[]) %}{% for t in T %}{% set d = device_id(t) %}"
          "{% set o.l = o.l + [[t, (device_attr(d, 'name_by_user') or device_attr(d, 'name')) if d else none, "
          "(device_attr(d, 'identifiers') | map('first') | list) if d else []]] %}{% endfor %}{{ o.l | tojson }}")


def slug(s):
    """Como o Home Assistant nomeia as coisas: "Relógio Davi" -> "relogio_davi"."""
    s = unicodedata.normalize("NFD", str(s or ""))
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")


def modelo(rastreadores):
    return "{% set T = " + json.dumps(sorted(t for t in rastreadores if RASTREADOR_RE.match(t))) + " %}" + MODELO


def aparelhos(resposta):
    """{rastreador: {"nome", "app"} ou None (sem aparelho)} a partir da resposta do modelo; None se ela não serve."""
    try:
        v = json.loads(resposta) if isinstance(resposta, str) else resposta
    except ValueError:
        return None
    if not isinstance(v, list):
        return None
    out = {}
    for x in v:
        if isinstance(x, list) and len(x) == 3 and isinstance(x[0], str):
            out[x[0]] = {"nome": str(x[1]), "app": "mobile_app" in (x[2] or [])} if x[1] else None
    return out


def celulares(rastreadores, servicos, aparelhos_=None):
    """Os serviços de aviso (mobile_app_*, os que existem em notify) destes rastreadores: pelo nome do aparelho do app
    Home Assistant; um rastreador de outro tipo (o roteador, uma câmera) não é celular. Sem os aparelhos, ou um
    rastreador fora deles, pelo id do rastreador (device_tracker.pixel_8 -> mobile_app_pixel_8)."""
    out = []
    for t in rastreadores if isinstance(rastreadores, list) else []:
        t = str(t)
        pelo_id = "mobile_app_" + re.sub(r"^device_tracker\.", "", t)
        cands = [pelo_id]
        if aparelhos_ is not None and t in aparelhos_:
            a = aparelhos_[t]
            cands = ["mobile_app_" + slug(a["nome"]), pelo_id] if a and a["app"] else []
        alvo = next((c for c in cands if c in servicos), None)
        if alvo and alvo not in out:
            out.append(alvo)
    return out


def pessoas(estados, servicos_ha, render):
    """[{"id": "person.ana", "nome", "usuario", "celulares": [...]}], pelo nome. estados: /api/states; servicos_ha:
    /api/services; render(modelo) devolve o texto do POST /api/template (ou lança: aí vale o id do rastreador)."""
    servicos = set()
    for dom in servicos_ha or []:
        if isinstance(dom, dict) and dom.get("domain") == "notify":
            servicos = {k for k in (dom.get("services") or {}) if CELULAR_RE.match(k)}
    gente = [s for s in estados or [] if isinstance(s, dict) and str(s.get("entity_id", "")).startswith("person.")]
    todos = {str(t) for s in gente for t in ((s.get("attributes") or {}).get("device_trackers") or [])}
    ap = None
    if todos:
        try:
            ap = aparelhos(render(modelo(todos)))
        except Exception:  # noqa: BLE001  (sem o modelo: pelo id do rastreador)
            ap = None
    out = [{"id": s["entity_id"], "nome": (s.get("attributes") or {}).get("friendly_name") or s["entity_id"][7:],
            "usuario": str((s.get("attributes") or {}).get("user_id") or ""),
            "celulares": celulares((s.get("attributes") or {}).get("device_trackers"), servicos, ap)} for s in gente]
    return sorted(out, key=lambda p: slug(p["nome"]))


def titulo_do_app(titulo):
    """O título do aviso com o nome do app na frente (uma vez só)."""
    t = str(titulo or "").strip()
    return t if t.startswith(APP_AVISO + " · ") else f"{APP_AVISO} · {t}" if t else APP_AVISO


def corpo(titulo, mensagem, tag, url=None, grupo="correria-rondas", canal="Rondas"):
    """O que vai para notify.mobile_app_*: o título com o nome do app, o ícone do app e a tela que o toque abre."""
    return {"title": titulo_do_app(titulo), "message": mensagem,
            "data": {"tag": tag, "group": grupo, "channel": canal, "notification_icon": ICONE_AVISO, **({"url": url, "clickAction": url} if url else {})}}
