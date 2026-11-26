"""1.5.0: a casa do Home Assistant como mais um app da CorrerIA ("casa"). Para mudar algo (ligar a luz da entrada,
fechar a cortina, pôr o ar em 23 graus), o pedido vai, do jeito que a pessoa falou, para o Assist do próprio Home
Assistant (o agente de conversa dele, conversation.home_assistant), que só mexe no que está exposto a ele
(Configurações › Assistentes de voz › Expor). Para saber como algo está, os estados vêm de /api/states, sem mexer
em nada. Liga e desliga em Configurações › Integrações › Casa (ligada de início). Só biblioteca padrão."""
import re
import unicodedata

ID = "casa"
APP = {"app": ID, "nome": "Casa", "assunto": "o Home Assistant: luzes, tomadas, cortinas, ar, cenas e o que mais estiver exposto ao Assist",
       "ferramentas": "/interno", "rota": None, "anexos": [], "versao": ""}
INSTRUCOES = ("para mudar algo da casa, casa_comando com o pedido em português, como a pessoa falou (\"liga a luz da "
              "entrada\"); para saber como algo está, casa_estado com o nome (\"luz da sala\", \"temperatura\"). Só vale o que "
              "está exposto ao Assist do Home Assistant.")
AGENTE = "conversation.home_assistant"
# o que dá para ver pelo casa_estado (sem a localização das pessoas)
DOMINIOS = ("light", "switch", "fan", "cover", "climate", "lock", "sensor", "binary_sensor", "media_player", "vacuum", "input_boolean",
            "scene", "script", "alarm_control_panel", "water_heater", "humidifier", "valve", "lawn_mower", "button", "weather")
ESTADOS = {"on": "ligado", "off": "desligado", "open": "aberto", "closed": "fechado", "opening": "abrindo", "closing": "fechando",
           "locked": "trancado", "unlocked": "destrancado", "home": "em casa", "not_home": "fora", "playing": "tocando",
           "paused": "pausado", "idle": "parado", "unavailable": "indisponível", "unknown": "desconhecido", "cleaning": "limpando",
           "docked": "na base", "heat": "aquecendo", "cool": "esfriando", "auto": "automático", "dry": "secando",
           "fan_only": "só ventilação", "heat_cool": "aquecendo e esfriando", "armed_away": "armado (fora)",
           "armed_home": "armado (em casa)", "disarmed": "desarmado", "triggered": "disparado"}
MAX = 40
# o nome de cada tipo, para achar "as luzes" mesmo num abajur
PALAVRAS = {"light": "luz lampada", "switch": "tomada interruptor", "fan": "ventilador", "cover": "cortina persiana portao",
            "climate": "ar condicionado clima", "lock": "fechadura tranca porta", "media_player": "tv som caixa",
            "vacuum": "aspirador robo", "sensor": "sensor", "binary_sensor": "sensor"}

FERRAMENTAS = [
    {"nome": "comando", "titulo": "Mexer na casa",
     "descricao": "Manda um pedido para o Assist do Home Assistant: ligar e desligar luzes e tomadas, abrir e fechar cortinas, "
                  "mudar a temperatura do ar, ligar uma cena ou um script, trancar a porta… Escreva o pedido em português, "
                  "como a pessoa falaria (\"liga a luz da entrada\", \"apaga todas as luzes da sala\"). Só mexe no que está "
                  "exposto ao Assist.",
     "entrada": {"type": "object", "properties": {"pedido": {"type": "string", "description": "O pedido, como a pessoa falou."}},
                 "required": ["pedido"], "additionalProperties": False},
     "grava": True, "apaga": False},
    {"nome": "estado", "titulo": "Ver como está a casa",
     "descricao": "Como estão as coisas da casa no Home Assistant (luzes, tomadas, cortinas, ar, sensores de temperatura, "
                  "portas…): o nome, o estado e o id. busca: palavras do nome (\"luz da sala\", \"temperatura\", \"porta\"); "
                  "sem busca, as luzes, tomadas, cortinas e o ar. ligados: true, só o que está ligado, aberto ou destrancado "
                  "(também as portas e janelas com sensor). comodo: só o que está nesse cômodo (a área do Home Assistant com esse "
                  "nome). Não mexe em nada.",
     "entrada": {"type": "object", "properties": {"busca": {"type": "string"},
                                                  "ligados": {"type": "boolean", "description": "Só o que está ligado, aberto ou destrancado."},
                                                  "comodo": {"type": "string", "description": "O cômodo (a área do Home Assistant)."}},
                 "additionalProperties": False},
     "grava": False, "apaga": False},
]


class ErroCasa(Exception):
    """O pedido não deu (o Assist não achou ou o Home Assistant falhou): a mensagem vai para a IA e para a pessoa."""


def dobrar(s):
    s = unicodedata.normalize("NFD", str(s or "")).lower()
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def estado_txt(s):
    st = str(s.get("state", ""))
    a = s.get("attributes") or {}
    txt = ESTADOS.get(st, st)
    un = a.get("unit_of_measurement")
    if un and st not in ("unavailable", "unknown"):
        txt = f"{st} {un}"
    dom = s["entity_id"].split(".")[0]
    if dom == "light" and st == "on" and isinstance(a.get("brightness"), (int, float)):
        txt += f", {round(a['brightness'] / 255 * 100)}%"
    if dom == "climate":
        extra = [f"{a['current_temperature']}° agora" if a.get("current_temperature") is not None else "",
                 f"alvo {a['temperature']}°" if a.get("temperature") is not None else ""]
        txt += "".join(f", {x}" for x in extra if x)
    if dom == "cover" and isinstance(a.get("current_position"), (int, float)):
        txt += f", {a['current_position']}%"
    return txt


# 1.37.0 (o dono, nas rondas: "ficou algo ligado?"): o que conta como ligado ou aberto em cada tipo, e as portas e janelas
# (os sensores de abrir: o device_class)
LIGADO = {"light": ("on",), "switch": ("on",), "fan": ("on",), "input_boolean": ("on",), "cover": ("open", "opening", "closing"),
          "lock": ("unlocked", "open", "opening"), "media_player": ("on", "playing", "paused", "idle", "buffering"),
          "valve": ("open", "opening"), "humidifier": ("on",), "vacuum": ("cleaning", "returning")}
ABRE = ("door", "window", "garage_door", "opening")
# as áreas do Home Assistant e o que está em cada uma (uma linha por coisa: «id|área»)
AREAS = ("{% for a in areas() %}{% for e in area_entities(a) %}{{ e }}|{{ area_name(a) }}\n{% endfor %}{% endfor %}")


def ligado(s):
    """Está ligado, aberto ou destrancado? (o ar: fora do desligado; uma porta ou janela: o sensor dela marcando aberta)"""
    eid, st = str(s.get("entity_id", "")), str(s.get("state", ""))
    dom = eid.split(".")[0]
    if dom == "climate":
        return st not in ("off", "unavailable", "unknown", "")
    if dom == "binary_sensor":
        return st == "on" and (s.get("attributes") or {}).get("device_class") in ABRE
    return st in LIGADO.get(dom, ())


class Casa:
    def __init__(self, get, post, log, texto=None):
        self.get, self.post, self.log = get, post, log  # get(caminho) e post(caminho, corpo): a API do Home Assistant
        self.texto = texto  # texto(modelo): o que o /api/template responde (as áreas, para o cômodo)

    def usar(self, nome, args):
        args = args if isinstance(args, dict) else {}
        if nome == "comando":
            return self.comando(str(args.get("pedido") or "").strip())
        if nome == "estado":
            return self.estado(str(args.get("busca") or "").strip(), ligados=args.get("ligados") is True,
                               comodo=str(args.get("comodo") or "").strip())
        raise ErroCasa(f"Ferramenta desconhecida: {nome}.")

    def comando(self, pedido):
        pedido = re.sub(r"\s+", " ", pedido)[:300]
        if not pedido:
            raise ErroCasa("Falta o pedido (ex.: liga a luz da entrada).")
        try:
            r = self.post("/conversation/process", {"text": pedido, "language": "pt-BR", "agent_id": AGENTE})
        except Exception as e:  # noqa: BLE001 (o Home Assistant fora do ar, sem o Assist…)
            raise ErroCasa(f"O Home Assistant não respondeu ({str(e).rstrip('.')}).") from e
        resp = (r or {}).get("response") or {}
        fala = ((resp.get("speech") or {}).get("plain") or {}).get("speech") or ""
        if resp.get("response_type") == "error":
            raise ErroCasa(fala or "O Assist não entendeu o pedido.")
        dados = resp.get("data") or {}
        falhou = [x.get("name") or x.get("id") for x in dados.get("failed") or [] if isinstance(x, dict)]
        if falhou and not dados.get("success"):
            raise ErroCasa(fala or f"Não deu: {', '.join(map(str, falhou))}.")
        feitos = [x.get("name") or x.get("id") for x in dados.get("success") or [] if isinstance(x, dict) and x.get("type") == "entity"]
        return (fala or "Feito.") + (f" ({', '.join(map(str, feitos[:8]))})" if feitos and not any(str(n) in fala for n in feitos) else "")

    def area_de(self, comodo):
        """{id: área} das coisas na área com o nome do cômodo (sem acento nem maiúsculas; o nome inteiro, ou a área que
        começa por ele), ou None: sem o /api/template ou sem essa área (aí vale o cômodo no nome de cada coisa)."""
        if not self.texto:
            return None
        try:
            linhas = str(self.texto(AREAS) or "")
        except Exception as e:  # noqa: BLE001 (um Home Assistant antigo, sem areas())
            self.log(f"Casa: as áreas não vieram ({e})")
            return None
        mapa = {}
        for l in linhas.splitlines():
            eid, _, area = l.strip().partition("|")
            if eid and area:
                mapa[eid] = area
        alvo = dobrar(comodo).strip()
        nomes = {dobrar(a).strip() for a in mapa.values()}
        quais = {alvo} if alvo in nomes else {n for n in nomes if n.startswith(alvo) or alvo.startswith(n)}
        if not quais:
            return None
        return {e: a for e, a in mapa.items() if dobrar(a).strip() in quais}

    def estado(self, busca, ligados=False, comodo=""):
        try:
            todos = self.get("/states")
        except Exception as e:  # noqa: BLE001
            raise ErroCasa(f"O Home Assistant não respondeu ({str(e).rstrip('.')}).") from e
        area = self.area_de(comodo) if comodo else None
        # sem a área no Home Assistant, o cômodo vai na busca (pelo nome de cada coisa: «Luz da sala»)
        if comodo and area is None:
            busca = f"{busca} {comodo}".strip()
        palavras = [p for p in re.findall(r"[a-z0-9]+", dobrar(busca)) if len(p) > 1 and p not in ("da", "do", "de", "das", "dos", "na", "no", "a", "o", "e")]
        achados = []
        for s in todos if isinstance(todos, list) else []:
            eid = str((s or {}).get("entity_id", ""))
            dom = eid.split(".")[0]
            if dom not in DOMINIOS:
                continue
            if area is not None and eid not in area:
                continue
            nome = (s.get("attributes") or {}).get("friendly_name") or eid
            toks = re.findall(r"[a-z0-9]+", dobrar(f"{nome} {eid.replace('_', ' ')} {PALAVRAS.get(dom, '')}"))
            if palavras:
                # cada palavra no começo de uma palavra do nome (luzes: luz; persiana não é "ana")
                if not all(any(t.startswith(x) for t in toks for x in (p, p[:-1] if p.endswith("s") else "", p[:-2] if p.endswith("es") else "") if x) for p in palavras):
                    continue
            elif ligados:
                if dom not in LIGADO and dom not in ("climate", "binary_sensor"):
                    continue
            elif dom not in ("light", "switch", "cover", "climate", "fan", "lock"):
                continue
            if ligados and not ligado(s):
                continue
            achados.append(f"- {nome}: {estado_txt(s)} ({eid})")
        if not achados:
            onde = f" em «{comodo}»" if comodo else ""
            if ligados:
                return f"Nada ligado ou aberto{onde}."
            return f"Nada com “{busca}” no Home Assistant." if busca else f"Nenhuma luz, tomada, cortina ou ar{onde} no Home Assistant."
        mais = len(achados) - MAX
        return "\n".join(achados[:MAX]) + (f"\n… e mais {mais}." if mais > 0 else "")
