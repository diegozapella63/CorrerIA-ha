"""Rondas (1.18.0): um roteiro fixo que passa pelos apps, uma etapa de cada vez, dentro da Conversa da tela.

A primeira é a Ronda da casa: a pessoa escolhe um cômodo e o CorrerIA passa pelas tarefas (ResolvIA), pelos itens e pelos
consumíveis (InventarIA) e pelas compras (EconomIA), uma pergunta de cada vez. A ordem e as perguntas são fixas, daqui; a IA só lê o app da etapa
(com as ferramentas dele), diz o que há e faz a pergunta, e depois transforma a resposta da pessoa em mudanças, que
continuam esperando o "sim", como em toda a Conversa. Cada etapa só existe se o app está ligado ao CorrerIA e oferece a
ferramenta de que ela precisa: assim a ronda respeita o que está ligado em cada app (um app sem os cômodos não filtra por
cômodo; o InventarIA sem os consumíveis não tem a etapa deles).

Para criar outra ronda: mais uma entrada em RONDAS, com as etapas (o app, a ferramenta que precisa existir e o pedido).
"""
import json
import re
import urllib.parse

FIM = ("Não mude nada agora: só leia e conte. Responda assim: primeiro uma linha só com «TOTAL: N» (N é o número do que você achou "
       "para esta etapa; 0 se não há nada); depois uma frase curta com o total; depois, se houver itens, um por linha, "
       "cada linha começando com «- » (no máximo 6); nada mais (não diga para seguir nem para tocar em nada, e não repita o nome do cômodo: a tela já mostra). NÃO faça pergunta nenhuma: o app escreve a pergunta «{pergunta}» logo abaixo.")
def _e(eid, grupo, titulo, app, nome_app, precisa, pergunta, pedido=None, **mais):
    return dict({"id": eid, "grupo": grupo, "titulo": titulo, "app": app, "nome_app": nome_app, "precisa": precisa, "pergunta": pergunta, "pedido": pedido}, **mais)


# 1.21.0 (o dono: "as perguntas precisam ser inteligentes, se não tem rotina da casa, pq perguntar se alguma precisa sair?"):
# se_tem marca a pergunta que só faz sentido quando há alguma coisa ali. A etapa que lê diz quantos achou (TOTAL: N); com 0,
# as etapas se_tem que vêm depois no mesmo grupo saem da ronda, e a própria etapa que leu, se for se_tem, só conta, sem perguntar.
# Cada etapa é UMA pergunta só (o dono: "para que de fato seja um GUIA"). A primeira etapa de cada grupo tem o pedido: a IA
# lê o app e conta o que há antes de perguntar; as outras só perguntam (sem chamar a IA: a pergunta sai na hora).
RONDAS = {
    "casa": {
        "nome": "Ronda da casa", "onde": "comodo",
        "resumo": "Um cômodo de cada vez, uma pergunta de cada vez.",
        "etapas": [
            _e("feita", "Tarefas", "Concluir", "resolvia", "ResolvIA", "resolvia_tarefas", "Alguma dessas tarefas já foi feita?",
               "Use resolvia_tarefas para ver as tarefas pendentes{do_comodo} e conte o que há para fazer{em}, com o prazo das que têm.",
               pedido_sem_filtro=" (a ferramenta não filtra por cômodo: veja as pendentes e fique com as que falam de «{onde}» no nome ou nas notas)", se_tem=True),
            _e("arrumar", "Tarefas", "Nova", "resolvia", "ResolvIA", "resolvia_tarefas", "Tem algo novo para arrumar?"),
            _e("rotina_nova", "Rotinas", "Nova", "cronologia", "CronologIA", "cronologia_cadastros", "Falta alguma rotina?",
               # 1.21.2: o CronologIA 1.108.0 diz os cômodos de cada rotina (comodos) e filtra por cômodo
               "Use cronologia_cadastros{do_comodo} e conte as rotinas da casa e as manutenções de «{onde}» (as que têm «{onde}» em comodos), "
               "com a repetição e a próxima vez de cada uma (se nenhuma for de lá, diga que não há).",
               pedido_sem_filtro=" (a ferramenta não filtra por cômodo: fique com as que têm «{onde}» em comodos ou no nome)"),
            _e("rotina_muda", "Rotinas", "Mudar", "cronologia", "CronologIA", "cronologia_cadastros", "Alguma rotina precisa mudar?", se_tem=True),
            _e("rotina_sai", "Rotinas", "Tirar", "cronologia", "CronologIA", "cronologia_cadastros", "Alguma rotina pode sair?", se_tem=True),
            _e("item_novo", "Itens", "Novo", "inventario", "InventarIA", "inventario_buscar_itens", "Chegou algum item novo?",
               "Use inventario_buscar_itens com o cômodo «{onde}» e a ordem recentes: diga quantos itens há e os últimos cadastrados."),
            _e("item_saiu", "Itens", "Descartado", "inventario", "InventarIA", "inventario_buscar_itens", "Algum item foi descartado?", se_tem=True),
            _e("item_mudou", "Itens", "Transferido", "inventario", "InventarIA", "inventario_buscar_itens", "Algum item foi transferido de cômodo?", se_tem=True),
            _e("cons_acabando", "Consumíveis", "Acabando", "inventario", "InventarIA", "inventario_buscar_itens", "Algum desses consumíveis precisa repor?",
               "Os consumíveis não têm cômodo. Use inventario_buscar_itens com o cômodo «Consumíveis» e conte os que já passaram do dura_ate "
               "ou acabam nos próximos 30 dias (se nenhum, diga quantos há; o TOTAL é só o dos que estão acabando).", so_com="consumiveis", se_tem=True,
               # 1.20.0: com Consumíveis por cômodo ligado no InventarIA (1.88.0), só os usados neste cômodo
               pedido_com={"consumiveis_por_comodo": "Use inventario_buscar_itens com o cômodo «Consumíveis» e usado_em «{onde}»: conte os consumíveis usados em «{onde}», "
                                                     "primeiro os que já passaram do dura_ate ou acabam nos próximos 30 dias (se nenhum for de lá, diga que não há; o TOTAL é só o dos que estão acabando)."}),
            _e("cons_novo", "Consumíveis", "Novo", "inventario", "InventarIA", "inventario_buscar_itens", "Quer adicionar algum consumível?", so_com="consumiveis"),
            _e("mercado", "Compras", "Mercado", "economia", "EconomIA", "economia_lista", "Precisa de algo do mercado?",
               "Use economia_lista (e economia_reposicao, se existir) e conte o que já está na lista de compras e o que está na hora de repor."),
            _e("farmacia", "Compras", "Farmácia", "economia", "EconomIA", "economia_lista", "Precisa de algo da farmácia?"),
            _e("pet", "Compras", "Pet shop", "economia", "EconomIA", "economia_lista", "Precisa de algo do pet shop?"),
        ],
    },
    # 1.20.0: as rondas sem cômodo (onde: None): começam direto
    "compras": {
        "nome": "Ronda de compras", "onde": None,
        "resumo": "Antes de sair para comprar: a lista, a reposição, as ofertas e onde ir.",
        "etapas": [
            _e("lista", "Lista", "O que falta", "economia", "EconomIA", "economia_lista", "Falta algo na lista de compras?",
               "Use economia_lista e conte o que está na lista de compras (o nome de cada item)."),
            _e("repor", "Reposição", "Na hora de repor", "economia", "EconomIA", "economia_reposicao", "Quer pôr na lista o que está na hora de repor?",
               "Use economia_reposicao e conte o que está na hora de repor ou perto disso.", se_tem=True),
            _e("acabando", "Consumíveis", "Acabando", "inventario", "InventarIA", "inventario_buscar_itens", "Quer pôr na lista algum consumível que está acabando?",
               "Use inventario_buscar_itens com o cômodo «Consumíveis» e conte os que já passaram do dura_ate ou acabam nos próximos 15 dias (se nenhum, diga que não há).",
               so_com="consumiveis", se_tem=True),
            _e("ofertas", "Ofertas", "Ofertas", "economia", "EconomIA", "economia_ofertas", "Quer aproveitar alguma dessas ofertas?",
               "Use economia_ofertas e conte as 5 de maior desconto (o produto, a loja e o preço).", se_tem=True),
            _e("roteiro", "Onde comprar", "Roteiro", "economia", "EconomIA", "economia_roteiro", "Vai comprar nessa loja?",
               "Use economia_roteiro e diga em qual loja a lista sai mais em conta (quantos itens têm preço lá e o total), com a segunda opção (o TOTAL é o de lojas com preço).", se_tem=True),
        ],
    },
    "chegada": {
        "nome": "Ronda da chegada das compras", "onde": None,
        "resumo": "Voltou das compras: o que comprou, quanto dura e o que guardar.",
        "etapas": [
            _e("comprei", "Lista", "O que comprou", "economia", "EconomIA", "economia_comprei", "O que da lista você comprou?",
               "Use economia_lista e conte o que estava na lista de compras (o nome de cada item).",
               se_tem=True, depois="Para cada item comprado use economia_comprei; se ele está na reposição ou é um consumível, pergunte por quanto tempo vai durar e mande dura_dias."),
            _e("fora", "Lista", "Fora da lista", "economia", "EconomIA", "economia_comprei", "Comprou algo que não estava na lista?"),
            _e("consumivel", "Guardar", "Consumível novo", "inventario", "InventarIA", "inventario_cadastrar_itens", "Algum consumível novo para cadastrar?", so_com="consumiveis"),
            _e("item", "Guardar", "Item novo", "inventario", "InventarIA", "inventario_cadastrar_itens", "Comprou algum item novo para a casa?"),
            _e("gasto", "Gasto", "Lançar", "gerencia", "GerencIA", "gerencia_lancar", "Quer lançar o gasto dessa compra?"),
        ],
    },
    "mes": {
        "nome": "Ronda do mês", "onde": None,
        "resumo": "Uma vez por mês: as finanças, as contas, a agenda, as tarefas e a casa.",
        "etapas": [
            _e("gastos", "Finanças", "Gastos do mês", "gerencia", "GerencIA", "gerencia_resumo", "Falta lançar algum gasto do mês?",
               "Use gerencia_resumo e conte o mês: quanto entrou, quanto saiu e quanto sobrou."),
            _e("contas", "Finanças", "Contas a pagar", "gerencia", "GerencIA", "gerencia_contas_a_pagar", "Alguma dessas contas já foi paga?",
               "Use gerencia_contas_a_pagar e conte as contas atrasadas e as que vencem nos próximos 10 dias (o nome, o valor e o dia).", se_tem=True),
            _e("agenda", "Agenda", "Próximo mês", "cronologia", "CronologIA", "cronologia_agenda", "Falta marcar algum compromisso?",
               "Use cronologia_agenda de hoje a 30 dias e conte os compromissos (sem as rotinas e os remédios de todo dia), com o dia de cada um."),
            _e("rotinas", "Agenda", "Rotinas", "cronologia", "CronologIA", "cronologia_cadastros", "Alguma rotina da casa precisa mudar?",
               "Use cronologia_cadastros e conte as rotinas da casa e as manutenções, com a repetição de cada uma.", se_tem=True),
            _e("tarefas", "Tarefas", "Atrasadas", "resolvia", "ResolvIA", "resolvia_tarefas", "Alguma tarefa atrasada pode sair da lista?",
               "Use resolvia_tarefas e conte as tarefas atrasadas (o nome e desde quando).", se_tem=True),
            _e("itens", "Casa", "Itens", "inventario", "InventarIA", "inventario_resumo", "Algum item saiu da casa neste mês?",
               "Use inventario_resumo e conte o total da casa e os últimos itens cadastrados."),
            _e("repor", "Casa", "Reposição", "economia", "EconomIA", "economia_reposicao", "Algum prazo da reposição precisa mudar?",
               "Use economia_reposicao e conte o que está na reposição, com de quanto em quanto tempo.", se_tem=True),
        ],
    },
}


def _resumo_inventario(ferr, todas, pessoa):
    """O resumo do InventarIA (os cômodos e o que está ligado lá), ou {} sem ele."""
    f = next((x for x in todas if x["id"] == "inventario_resumo"), None)
    if not f:
        return {}
    texto, erro = ferr.usar(f, {}, pessoa, "CorrerIA")
    if erro:
        return {}
    try:
        d = json.loads(texto)
    except (TypeError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


def disponiveis(ferr, pessoa=None):
    """As rondas que dá para fazer agora: [{id, nome, resumo, etapas: [{id, titulo, app}], onde: [nomes dos cômodos], livre}].
    Uma ronda sem nenhuma etapa possível não aparece. livre: sem a lista dos cômodos (o InventarIA desligado), a pessoa escreve."""
    todas = ferr.todas()
    ids = {f["id"] for f in todas}
    inv = _resumo_inventario(ferr, todas, pessoa)
    ligado = opcoes(inv)
    comodos = [str(c.get("nome")) for c in inv.get("comodos") or [] if isinstance(c, dict) and c.get("nome")][:60]
    out = []
    for rid, r in RONDAS.items():
        etapas = [e for e in r["etapas"] if e["precisa"] in ids and (not e.get("so_com") or e["so_com"] in ligado)]
        if etapas:
            onde = comodos if r["onde"] else []
            out.append({"id": rid, "nome": r["nome"], "resumo": r["resumo"],
                        "etapas": [{"id": e["id"], "titulo": e["titulo"], "grupo": e["grupo"], "app": e["nome_app"]} for e in etapas],
                        "onde": onde, "livre": bool(r["onde"]) and not onde, "sem_onde": not r["onde"], "opcoes": sorted(ligado)})
    return out


def opcoes(inv):
    """O que está ligado no InventarIA e muda as etapas: consumiveis (Usar consumíveis) e consumiveis_por_comodo."""
    o = inv.get("opcoes") or {}
    return {k for k in ("consumiveis", "consumiveis_por_comodo") if o.get(k) is True}


def etapa_de(rid, eid):
    return next((e for e in RONDAS.get(rid, {}).get("etapas", []) if e["id"] == eid), None)


def aceita(todas, fid, campo):
    """A ferramenta tem esse campo na entrada? (o ResolvIA só filtra por cômodo com Usar cômodos ligado lá)"""
    f = next((x for x in todas if x["id"] == fid), None)
    return bool(f and campo in ((f.get("entrada") or {}).get("properties") or {}))


def pergunta(rid, eid, onde):
    return etapa_de(rid, eid)["pergunta"].format(onde=onde)


def pedido(rid, eid, onde, todas, n, total, ligado=()):
    """O que vai para a IA numa etapa que lê o app antes de perguntar (None: a etapa só pergunta). A pessoa vê só o rótulo.
    ligado: as opções do InventarIA (opcoes): uma etapa pode ter outro pedido com uma delas (pedido_com)."""
    r, e = RONDAS[rid], etapa_de(rid, eid)
    if not e.get("pedido"):
        return None
    modelo = next((t for k, t in (e.get("pedido_com") or {}).items() if k in ligado), e["pedido"])
    filtra = aceita(todas, e["precisa"], "comodo")
    texto = modelo.format(onde=onde, em=f" em «{onde}»",
                          do_comodo=(f" do cômodo «{onde}» (o campo comodo)" if filtra else (e.get("pedido_sem_filtro") or "").format(onde=onde)))
    return "\n".join([
        f"{r['nome'].upper()}{f', cômodo «{onde}»' if onde else ''}, etapa {n} de {total}: {e['titulo']} ({e['nome_app']}).",
        texto,
        FIM.format(pergunta=pergunta(rid, eid, onde)),
    ] + ([e["depois"]] if e.get("depois") else []))


def rotulo(rid, eid, onde, n, total):
    e = etapa_de(rid, eid)
    return f"{onde or RONDAS[rid]['nome']} · {e['grupo']}: {e['titulo']} ({n} de {total})"


def contexto(rid, eid, onde):
    """O que a IA precisa saber quando a pessoa responde no meio de uma etapa."""
    e = etapa_de(rid, eid)
    return (f"(Estou na {RONDAS[rid]['nome']}{f', cômodo «{onde}»' if onde else ''}, etapa {e['titulo']}: a minha próxima mensagem responde a «{e['pergunta'].format(onde=onde)}». "
            f"As mudanças desta etapa são no {e['nome_app']}; responda só a isso, sem fazer outra pergunta; se eu disser que não há nada, diga só para eu tocar em Próxima."
            + (" " + e["depois"] if e.get("depois") else "") + ")")


def abrir(rid, eid, onde, paineis):
    """1.22.0 (o dono: "tem como as ações da ronda terem link para os apps?"): o link da etapa, {texto, href}, que abre o app
    dela no Home Assistant, já no lugar: o InventarIA no cômodo (ou nos consumíveis), o ResolvIA no Buscar com as tarefas do
    cômodo, o CronologIA nas Rotinas (ou no Calendário). paineis: {app: /app/<slug>}; sem o endereço do app, None.
    Um app de antes desses endereços só abre, na tela de sempre."""
    e = etapa_de(rid, eid)
    base = (paineis or {}).get(e["app"]) if e else None
    if not base:
        return None
    q, cons = urllib.parse.quote(onde or "", safe=""), e["grupo"] == "Consumíveis" or "consum" in e["id"]
    if e["app"] == "inventario":
        base += "/consumiveis" if cons else f"/comodo/{q}" if onde else ""
    elif e["app"] == "resolvia":
        # 1.22.3: os dois jeitos de dizer onde abrir: o resto do endereço (o painel do Home Assistant passa por mensagem, também
        # a uma tela que já estava aberta) e o ?aba= (lido quando a tela carrega)
        base += f"/buscar/comodo/{q}?aba=buscar&comodo={q}" if onde else "?aba=prazos"
    elif e["app"] == "cronologia":
        base += "/calendario?aba=calendario" if e["id"] == "agenda" else (f"/mais/rotinas/comodo/{q}?aba=rotinas&comodo={q}" if onde else "/mais/rotinas?aba=rotinas")
    return {"texto": f"Abrir no {e['nome_app']}", "href": base}


def e_mais(texto, achou):
    """1.22.0 (o dono: "ele vira 10 mas traz só alguns, deveria indicar e mais no final"): a lista mostra menos do que o
    TOTAL: uma última linha «- e mais N»."""
    linhas = str(texto or "").split("\n")
    itens = [k for k, l in enumerate(linhas) if re.match(r"\s*[-•–]\s+\S", l)]
    if not achou or not itens or achou <= len(itens) or re.search(r"\be mais \d+", linhas[itens[-1]], re.I):
        return texto
    linhas.insert(itens[-1] + 1, f"- e mais {achou - len(itens)}")
    return "\n".join(linhas)


TOTAL_RE = re.compile(r"^[ \t]*[«\"*]*TOTAL[ \t]*:[ \t]*(\d+)[»\"*.]*[ \t]*$\n?", re.M | re.I)


def total(texto):
    """(N, o texto sem a linha) da resposta de uma etapa que leu: quantos a IA achou; None se ela não disse."""
    t = str(texto or "")
    m = TOTAL_RE.search(t)
    return (int(m.group(1)), TOTAL_RE.sub("", t).strip()) if m else (None, t)


def junta_com(rid, etapas, i, n):
    """1.21.1 (o dono: "direto ali e não em outra pergunta, se não quebra o ritmo"): a etapa i leu, não achou nada e a pergunta
    dela só vale com alguma coisa: a pergunta da etapa seguinte do mesmo grupo (a que vale sempre) vem na mesma mensagem.
    Devolve o índice dessa etapa, ou None. Chame depois do sem_o_que_perguntar."""
    e = etapa_de(rid, etapas[i])
    if n != 0 or not e.get("se_tem") or i + 1 >= len(etapas):
        return None
    p = etapa_de(rid, etapas[i + 1])
    return i + 1 if p["grupo"] == e["grupo"] and not p.get("pedido") else None


def sem_o_que_perguntar(rid, etapas, i, n):
    """Com 0 achados na etapa i (que leu), as etapas que ficam: saem as se_tem que só perguntam, logo depois, no mesmo grupo."""
    if n != 0:
        return etapas
    g, fica, k = etapa_de(rid, etapas[i])["grupo"], list(etapas[:i + 1]), i + 1
    while k < len(etapas):
        e = etapa_de(rid, etapas[k])
        if e["grupo"] != g or e.get("pedido"):
            break
        if not e.get("se_tem"):
            fica.append(etapas[k])
        k += 1
    return fica + list(etapas[k:])


def arrumar(texto, rid, eid, onde, perguntar=True):
    """A resposta da IA numa etapa, arrumada para ler: a pergunta sai de dentro do texto (a IA às vezes repete, entre «»),
    uma lista escrita numa linha só («: - a - b») vira uma linha por item, e a pergunta da etapa vem no fim, à parte, em negrito (perguntar=False: sem a pergunta, quando não há do que perguntar)."""
    p = pergunta(rid, eid, onde)
    t = str(texto or "").replace("\r\n", "\n")
    t = re.sub(r"\s*[«\"“*]*" + re.escape(p) + r"[»\"”*]*", "", t)
    t = re.sub(r"\s*(Você )?[Pp]ode(mos)? (seguir|ir|passar|avançar) para a próxima( etapa| pergunta)?[.!]?", "", t)  # a tela já tem o Próxima
    t = re.sub(r"(?<=[:.;])[ \t]+[-•–][ \t]+(?=\S)", "\n- ", t)       # o primeiro item, depois de «:»
    linhas = []
    for l in t.split("\n"):
        if re.match(r"\s*[-•–]\s+", l):  # os outros itens da mesma linha
            l = re.sub(r"[ \t]+[-•–][ \t]+(?=[A-ZÀ-Ú0-9])", "\n- ", re.sub(r"^\s*[-•–]\s+", "- ", l))
            ult = l.split("\n")
            m = re.match(r"(- .+?[.!?])\s+([A-ZÀ-Ú].+)$", ult[-1])  # a frase que vem depois do último item
            if m and len(ult) > 1:
                ult[-1:] = [m.group(1).rstrip("."), "", m.group(2)]
            linhas += ult
        else:
            linhas.append(l.strip())
    out = []
    for l in linhas:  # a lista num parágrafo só dela (a tela desenha como lista)
        item = l.startswith("- ")
        if out and out[-1] and l and item != out[-1].startswith("- "):
            out.append("")
        out.append(l)
    corpo = re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()
    return (corpo + "\n\n" if corpo else "") + f"*{p}*" if perguntar else corpo or "Nada por aqui."
