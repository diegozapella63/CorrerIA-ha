"""1.5.0: a casa do Home Assistant como mais um app da CorrerIA ("casa"). Para mudar algo (ligar a luz da entrada,
fechar a cortina, pôr o ar em 23 graus), o pedido vai, do jeito que a pessoa falou, para o Assist do próprio Home
Assistant (o agente de conversa dele, conversation.home_assistant), que só mexe no que está exposto a ele
(Configurações › Assistentes de voz › Expor). Para saber como algo está, os estados vêm de /api/states, sem mexer
em nada. Liga e desliga em Configurações › Integrações › Casa (ligada de início). Só biblioteca padrão."""
import re
import unicodedata
import urllib.parse
from datetime import datetime, timedelta, time as hora_do_dia

ID = "casa"
APP = {"app": ID, "nome": "Casa", "assunto": "o Home Assistant: luzes, tomadas, cortinas, ar, cenas e o que mais estiver exposto ao Assist",
       "ferramentas": "/interno", "rota": None, "anexos": [], "versao": ""}
INSTRUCOES = ("para mudar algo da casa, casa_comando com o pedido em português, como a pessoa falou (\"liga a luz da "
              "entrada\"); para saber como algo está, casa_estado com o nome (\"luz da sala\", \"temperatura\") ou com o tipo "
              "(energia, temperatura, luzes, seguranca, baterias, sem_resposta). Só vale o que está exposto ao Assist do Home Assistant.")
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
            "vacuum": "aspirador robo", "sensor": "sensor", "binary_sensor": "sensor", "scene": "cena", "script": "script rotina",
            "alarm_control_panel": "alarme"}

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
                  "nome). tipo: energia (o que gasta agora, em watts, do maior para o menor), temperatura (a temperatura e a umidade "
                  "de cada cômodo e o ar), luzes (as acesas, com o brilho e a cor), seguranca (as fechaduras, o alarme e as portas e "
                  "janelas abertas), baterias (as fracas, 20% ou menos) ou "
                  "sem_resposta (o que o Home Assistant não alcança); cada linha diz o cômodo. Não mexe em nada.",
     "entrada": {"type": "object", "properties": {"busca": {"type": "string"},
                                                  "ligados": {"type": "boolean", "description": "Só o que está ligado, aberto ou destrancado."},
                                                  "comodo": {"type": "string", "description": "O cômodo (a área do Home Assistant)."},
                                                  "tipo": {"type": "string", "enum": ["energia", "temperatura", "luzes", "seguranca", "baterias", "sem_resposta"],
                                                           "description": "Uma visão pronta da casa."}},
                 "additionalProperties": False},
     "grava": False, "apaga": False},
    # 1.40.0 (o dono, às ferramentas que faltavam: "pode seguir neles"): o histórico de um dia, pelo /api/history
    {"nome": "historico", "titulo": "Histórico da casa",
     "descricao": "O que aconteceu num dia com uma coisa da casa, pelo histórico do Home Assistant: quando ligou e desligou (ou abriu "
                  "e fechou) e quanto tempo ficou ligada; num sensor de número, a mínima, a máxima e a média (a temperatura do quarto); "
                  "num medidor de energia, quanto gastou. busca: palavras do nome (\"porta da frente\", \"temperatura do quarto\"). "
                  "tipo energia (sem busca): o consumo de cada medidor de energia no dia, do maior para o menor, com o do dia anterior "
                  "para comparar. dia: hoje (padrão), ontem ou AAAA-MM-DD (até 30 dias atrás). Não mexe em nada.",
     "entrada": {"type": "object", "properties": {"busca": {"type": "string", "description": "Palavras do nome da coisa."},
                                                  "tipo": {"type": "string", "enum": ["energia"], "description": "O consumo de energia do dia."},
                                                  "dia": {"type": "string", "description": "hoje, ontem ou AAAA-MM-DD."}},
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
            tipo = str(args.get("tipo") or "").strip()
            if tipo and tipo not in TIPOS:
                raise ErroCasa(f"tipo vale {', '.join(TIPOS)}.")
            return self.estado(str(args.get("busca") or "").strip(), ligados=args.get("ligados") is True,
                               comodo=str(args.get("comodo") or "").strip(), tipo=tipo)
        if nome == "historico":
            return self.historico(str(args.get("busca") or "").strip(), str(args.get("dia") or "").strip(), str(args.get("tipo") or "").strip())
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

    def areas(self):
        """{id: área} de tudo o que tem área no Home Assistant, ou None sem o /api/template."""
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
        return mapa

    def area_de(self, comodo, mapa=False):
        """{id: área} das coisas na área com o nome do cômodo (sem acento nem maiúsculas; o nome inteiro, ou a área que
        começa por ele), ou None: sem o /api/template ou sem essa área (aí vale o cômodo no nome de cada coisa)."""
        mapa = self.areas() if mapa is False else mapa
        if not mapa:
            return None
        alvo = dobrar(comodo).strip()
        nomes = {dobrar(a).strip() for a in mapa.values()}
        quais = {alvo} if alvo in nomes else {n for n in nomes if n.startswith(alvo) or alvo.startswith(n)}
        if not quais:
            return None
        return {e: a for e, a in mapa.items() if dobrar(a).strip() in quais}

    def estado(self, busca, ligados=False, comodo="", tipo=""):
        try:
            todos = self.get("/states")
        except Exception as e:  # noqa: BLE001
            raise ErroCasa(f"O Home Assistant não respondeu ({str(e).rstrip('.')}).") from e
        mapa = self.areas() if (comodo or tipo) else None
        area = self.area_de(comodo, mapa) if comodo else None
        if tipo:
            return por_tipo(tipo, todos if isinstance(todos, list) else [], mapa or {}, area, comodo)
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


    # ---------- 1.40.0: o histórico de um dia (GET /api/history/period)
    def _dia(self, dia, agora):
        d = dobrar(dia)
        hoje = agora.date()
        if d in ("", "hoje"):
            return hoje
        if d == "ontem":
            return hoje - timedelta(days=1)
        if d == "anteontem":
            return hoje - timedelta(days=2)
        try:
            v = datetime.strptime(dia, "%Y-%m-%d").date()
        except ValueError:
            raise ErroCasa("dia: hoje, ontem ou AAAA-MM-DD.") from None
        if v > hoje or (hoje - v).days > 30:
            raise ErroCasa("dia: de hoje até 30 dias atrás.")
        return v

    def _periodo(self, ini, fim, ids):
        q = urllib.parse.urlencode({"end_time": fim.isoformat(), "filter_entity_id": ",".join(ids)})
        try:
            v = self.get(f"/history/period/{urllib.parse.quote(ini.isoformat())}?{q}&minimal_response&no_attributes")
        except Exception as e:  # noqa: BLE001
            raise ErroCasa(f"O Home Assistant não respondeu ({str(e).rstrip('.')}).") from e
        out = {}
        for linha in v if isinstance(v, list) else []:
            eid = next((str(x.get("entity_id")) for x in linha if isinstance(x, dict) and x.get("entity_id")), "") if isinstance(linha, list) else ""
            if eid:
                out[eid] = [(quando(x.get("last_changed") or x.get("last_updated")), str(x.get("state", ""))) for x in linha if isinstance(x, dict)]
                out[eid] = [(t, st) for t, st in out[eid] if t is not None]
        return out

    def historico(self, busca="", dia="", tipo="", agora=None):
        agora = agora or datetime.now().astimezone()
        if tipo and tipo != "energia":
            raise ErroCasa("tipo vale energia.")
        d = self._dia(dia, agora)
        ini = datetime.combine(d, hora_do_dia.min).replace(tzinfo=agora.tzinfo)
        fim = min(ini + timedelta(days=1), agora)
        nome_dia = "hoje" if d == agora.date() else "ontem" if d == agora.date() - timedelta(days=1) else d.strftime("%d/%m/%Y")
        try:
            todos = self.get("/states")
        except Exception as e:  # noqa: BLE001
            raise ErroCasa(f"O Home Assistant não respondeu ({str(e).rstrip('.')}).") from e
        todos = [s for s in (todos if isinstance(todos, list) else []) if isinstance(s, dict)]
        if tipo == "energia":
            med = [s for s in todos if str(s.get("entity_id", "")).startswith("sensor.") and (s.get("attributes") or {}).get("device_class") == "energy"
                   and (s.get("attributes") or {}).get("state_class") in ("total_increasing", "total")][:20]
            if not med:
                return "Nenhum medidor de energia no Home Assistant (um sensor de energia que soma o consumo, em kWh)."
            h = self._periodo(ini - timedelta(days=1), fim, [s["entity_id"] for s in med])
            linhas = []
            for s in med:
                a = s.get("attributes") or {}
                pts = h.get(s["entity_id"]) or []
                vez = gasto([p for p in pts if p[0] >= ini])
                antes = gasto([p for p in pts if p[0] < ini])
                if vez is None:
                    continue
                un = str(a.get("unit_of_measurement") or "kWh")
                linhas.append((vez, f"- {a.get('friendly_name') or s['entity_id']}: {_br(vez, 2)} {un} {nome_dia}"
                                    + (f" (no dia anterior, {_br(antes, 2)} {un})" if antes is not None else "")))
            if not linhas:
                return f"Os medidores de energia não têm histórico de {nome_dia}."
            linhas.sort(key=lambda x: -x[0])
            return f"Consumo de energia de {nome_dia}, do maior para o menor:\n" + "\n".join(t for _, t in linhas[:12])
        palavras = [p for p in re.findall(r"[a-z0-9]+", dobrar(busca)) if len(p) > 1 and p not in ("da", "do", "de", "das", "dos", "na", "no", "a", "o", "e")]
        if not palavras:
            raise ErroCasa("Diga a busca (palavras do nome da coisa) ou tipo energia.")
        achados = []
        for s in todos:
            eid = str(s.get("entity_id", ""))
            dom = eid.split(".")[0]
            if dom not in DOMINIOS:
                continue
            nome = (s.get("attributes") or {}).get("friendly_name") or eid
            toks = re.findall(r"[a-z0-9]+", dobrar(f"{nome} {eid.replace('_', ' ')} {PALAVRAS.get(dom, '')}"))
            if all(any(t.startswith(x) for t in toks for x in (p, p[:-1] if p.endswith("s") else "") if x) for p in palavras):
                achados.append(s)
        if not achados:
            return f"Nada com “{busca}” no Home Assistant."
        if len(achados) > 3:
            return (f"{len(achados)} coisas com “{busca}”: diga qual. " + "; ".join(str((s.get('attributes') or {}).get('friendly_name') or s['entity_id']) for s in achados[:12])
                    + ("…" if len(achados) > 12 else "."))
        h = self._periodo(ini, fim, [s["entity_id"] for s in achados])
        return "\n".join(linha_do_dia(s, h.get(s["entity_id"]) or [], ini, fim, nome_dia) for s in achados)


def quando(t):
    try:
        return datetime.fromisoformat(str(t).replace("Z", "+00:00"))
    except ValueError:
        return None


def gasto(pts):
    """Quanto um medidor que só soma andou: a soma das subidas (uma queda é o medidor recomeçando)."""
    ns = [n for n in (_num(st) for _, st in pts) if n is not None]
    if len(ns) < 2:
        return None
    return sum(b - a for a, b in zip(ns, ns[1:]) if b > a)


def _dura(seg):
    m = int(round(seg / 60))
    return f"{m // 60} h {m % 60:02d} min" if m >= 60 else f"{m} min"


def linha_do_dia(s, pts, ini, fim, nome_dia):
    """Uma coisa num dia: o sensor de número (mínima, máxima, média), o medidor de energia (quanto andou), o que liga e
    desliga (quantas vezes e quanto tempo) ou as mudanças de estado, com a hora."""
    a = s.get("attributes") or {}
    nome = a.get("friendly_name") or s["entity_id"]
    hm = lambda t: t.astimezone(ini.tzinfo).strftime("%H:%M")  # noqa: E731
    if not pts:
        return f"- {nome}: sem histórico de {nome_dia}."
    nums = [(t, n) for t, n in ((t, _num(st)) for t, st in pts) if n is not None]
    un = str(a.get("unit_of_measurement") or "")
    if un and len(nums) >= max(1, len(pts) // 2):
        if a.get("device_class") == "energy" and a.get("state_class") in ("total_increasing", "total"):
            g = gasto(pts)
            return f"- {nome}: {_br(g or 0, 2)} {un} {nome_dia}."
        mn, mx = min(nums, key=lambda x: x[1]), max(nums, key=lambda x: x[1])
        # a média pelo tempo que cada valor durou
        total = peso = 0.0
        for (t, n), (t2, _) in zip(nums, nums[1:] + [(fim, 0)]):
            seg = max(0.0, (t2 - max(t, ini)).total_seconds())
            total, peso = total + n * seg, peso + seg
        media = total / peso if peso else sum(n for _, n in nums) / len(nums)
        return (f"- {nome}, {nome_dia}: mínima {_br(mn[1])} {un} às {hm(max(mn[0], ini))}, máxima {_br(mx[1])} {un} às {hm(max(mx[0], ini))}, "
                f"média {_br(media)} {un}; por último, {_br(nums[-1][1])} {un}.")
    dom = s["entity_id"].split(".")[0]
    mud = [(t, st) for k, (t, st) in enumerate(pts) if k == 0 or st != pts[k - 1][1]]
    porta = dom == "binary_sensor" and a.get("device_class") in ABRE
    txt = lambda st: ({"on": "aberto", "off": "fechado"}.get(st) if porta else None) or estado_txt({"entity_id": s["entity_id"], "state": st, "attributes": {}})  # noqa: E731
    partes = " · ".join(f"{hm(max(t, ini))} {txt(st)}" for t, st in mud[-12:])
    if dom in LIGADO or dom == "binary_sensor":
        ligada = 0.0
        vezes = 0
        for k, (t, st) in enumerate(mud):
            on = st == "on" if dom == "binary_sensor" else ligado({"entity_id": s["entity_id"], "state": st, "attributes": a})
            if on:
                ligada += ((mud[k + 1][0] if k + 1 < len(mud) else fim) - max(t, ini)).total_seconds()
                vezes += 1 if k > 0 else 0
        resumo = (f"{vezes} {'vez' if vezes == 1 else 'vezes'}, {_dura(ligada)} ao todo" if ligada else "nenhuma vez")
        return f"- {nome}, {nome_dia}: {resumo}. {partes}" + (" (as 12 últimas mudanças)" if len(mud) > 12 else "")
    return f"- {nome}, {nome_dia}: {partes}" + (" (as 12 últimas mudanças)" if len(mud) > 12 else "")


# 1.38.0 (o dono: "cria mais para a casa, energia, cores da luz talvez, temperatura cômodos?"): as visões prontas do
# casa_estado, para as etapas das rondas. Cada linha diz o cômodo (a área do Home Assistant), quando há.
TIPOS = ("energia", "temperatura", "luzes", "seguranca", "baterias", "sem_resposta")
BATERIA_FRACA = 20
# o nome da cor de uma luz pelo matiz (0 a 360) do hs_color; pouca saturação é branca
MATIZES = ((15, "vermelha"), (40, "laranja"), (70, "amarela"), (160, "verde"), (200, "ciano"), (250, "azul"), (290, "roxa"),
           (345, "rosa"), (361, "vermelha"))


def _num(v):
    try:
        n = float(v)
    except (TypeError, ValueError):
        return None
    return n if n == n and abs(n) != float("inf") else None


def _br(n, casas=1):
    t = f"{n:.{casas}f}".replace(".", ",")
    return t[:-2] if casas == 1 and t.endswith(",0") else t


def cor_da_luz(a):
    """A cor de uma luz acesa, em português: «branca quente», «azul»… ("" sem cor)."""
    modo = str(a.get("color_mode") or "")
    k = _num(a.get("color_temp_kelvin")) or (1e6 / m if (m := _num(a.get("color_temp"))) else None)
    if modo == "color_temp" or (k and not a.get("hs_color")):
        if not k:
            return "branca"
        return "branca quente" if k <= 3300 else "branca neutra" if k <= 4600 else "branca fria"
    hs = a.get("hs_color")
    if not (isinstance(hs, (list, tuple)) and len(hs) == 2 and _num(hs[0]) is not None and _num(hs[1]) is not None):
        rgb = a.get("rgb_color")
        if not (isinstance(rgb, (list, tuple)) and len(rgb) == 3 and all(_num(x) is not None for x in rgb)):
            return ""
        import colorsys
        h, _l, sat = colorsys.rgb_to_hls(*(float(x) / 255 for x in rgb))
        hs = (h * 360, sat * 100)
    h, sat = float(hs[0]) % 360, float(hs[1])
    if sat < 20:
        return "branca"
    return next(nome for ate, nome in MATIZES if h < ate)


def por_tipo(tipo, todos, mapa, area, comodo):
    """O texto de uma visão pronta (tipo) da casa; area: {id: área} do cômodo pedido (None: o cômodo no nome)."""
    def vale(s):
        eid = str(s.get("entity_id", ""))
        if area is not None:
            return eid in area
        if comodo:
            nome = (s.get("attributes") or {}).get("friendly_name") or eid
            return all(p in dobrar(f"{nome} {eid.replace('_', ' ')}") for p in re.findall(r"[a-z0-9]{2,}", dobrar(comodo)))
        return True
    estados = [s for s in todos if isinstance(s, dict) and s.get("entity_id") and vale(s)]
    onde = f" em «{comodo}»" if comodo else ""
    nome = lambda s: (s.get("attributes") or {}).get("friendly_name") or s["entity_id"]  # noqa: E731
    cls = lambda s: (s.get("attributes") or {}).get("device_class")  # noqa: E731
    dom = lambda s: s["entity_id"].split(".")[0]  # noqa: E731
    lugar = lambda s: f" · {mapa[s['entity_id']]}" if mapa.get(s["entity_id"]) else ""  # noqa: E731
    linhas = []
    if tipo == "energia":
        achados = []
        for s in estados:
            un = str((s.get("attributes") or {}).get("unit_of_measurement") or "")
            w = _num(s.get("state"))
            if dom(s) != "sensor" or cls(s) != "power" or w is None or un not in ("W", "kW"):
                continue
            w = w * 1000 if un == "kW" else w
            if w > 0:
                achados.append((w, s))
        linhas = [f"- {nome(s)}: {_br(w, 0)} W ({s['entity_id']}){lugar(s)}" for w, s in sorted(achados, key=lambda x: -x[0])]
        vazio = f"Nada gastando agora{onde} (nenhum sensor de consumo, em watts, acima de zero)."
    elif tipo == "temperatura":
        grupos, soltos = {}, []
        for s in estados:
            a = s.get("attributes") or {}
            if dom(s) == "sensor" and cls(s) in ("temperature", "humidity") and _num(s.get("state")) is not None:
                v = _num(s["state"])
                txt = f"{_br(v)} {a.get('unit_of_measurement') or ('°C' if cls(s) == 'temperature' else '%')}"
                txt = txt if cls(s) == "temperature" else f"umidade {_br(v, 0)}%"
            elif dom(s) == "climate" and s.get("state") not in ("unavailable", "unknown"):
                txt = f"{nome(s)}: {estado_txt(s)}"
            else:
                continue
            ar = mapa.get(s["entity_id"])
            if ar:
                grupos.setdefault(ar, []).append((cls(s) or "climate", txt))
            else:
                soltos.append(f"- {nome(s)}: {txt if dom(s) != 'climate' else estado_txt(s)} ({s['entity_id']})")
        ordem = {"temperature": 0, "humidity": 1, "climate": 2}
        for ar in sorted(grupos, key=dobrar):
            partes = [t for _c, t in sorted(grupos[ar], key=lambda x: ordem.get(x[0], 3))]
            linhas.append(f"- {ar}: {' · '.join(dict.fromkeys(partes))}")
        linhas += soltos
        vazio = f"Nenhum sensor de temperatura nem ar{onde} no Home Assistant."
    elif tipo == "luzes":
        for s in estados:
            if dom(s) != "light" or s.get("state") != "on":
                continue
            a = s.get("attributes") or {}
            partes = [f"{round(a['brightness'] / 255 * 100)}%"] if isinstance(a.get("brightness"), (int, float)) else []
            if cor_da_luz(a):
                partes.append(cor_da_luz(a))
            linhas.append(f"- {nome(s)}: acesa{''.join(', ' + p for p in partes)} ({s['entity_id']}){lugar(s)}")
        vazio = f"Nenhuma luz acesa{onde}."
    elif tipo == "seguranca":
        for s in estados:
            d, st = dom(s), str(s.get("state", ""))
            if d in ("lock", "alarm_control_panel") and st not in ("unknown", ""):
                linhas.append(f"- {nome(s)}: {estado_txt(s)} ({s['entity_id']}){lugar(s)}")
            elif (d == "binary_sensor" and cls(s) in ABRE and st == "on") or (d == "cover" and cls(s) in ("garage", "gate", "door") and st in LIGADO["cover"]):
                linhas.append(f"- {nome(s)}: aberto ({s['entity_id']}){lugar(s)}")
        vazio = f"Nenhuma fechadura, alarme nem porta aberta{onde} no Home Assistant."
    elif tipo == "baterias":
        achados = []
        for s in estados:
            if cls(s) != "battery":
                continue
            v = _num(s.get("state"))
            if dom(s) == "sensor" and v is not None and v <= BATERIA_FRACA:
                achados.append((v, f"- {nome(s)}: {_br(v, 0)}% ({s['entity_id']}){lugar(s)}"))
            elif dom(s) == "binary_sensor" and s.get("state") == "on":
                achados.append((-1, f"- {nome(s)}: fraca ({s['entity_id']}){lugar(s)}"))
        linhas = [t for _v, t in sorted(achados, key=lambda x: x[0])]
        vazio = f"Nenhuma bateria fraca{onde} ({BATERIA_FRACA}% ou menos)."
    else:  # sem_resposta
        fora = ("scene", "script", "button", "weather", "input_boolean")
        linhas = [f"- {nome(s)} ({s['entity_id']}){lugar(s)}" for s in estados
                  if dom(s) in DOMINIOS and dom(s) not in fora and s.get("state") == "unavailable"]
        vazio = f"Tudo{onde} responde no Home Assistant."
    if not linhas:
        return vazio
    mais = len(linhas) - MAX
    return "\n".join(linhas[:MAX]) + (f"\n… e mais {mais}." if mais > 0 else "")
