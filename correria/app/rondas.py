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

FIM = "Não mude nada agora: só leia e conte. Responda em até 5 linhas curtas, sem título, e termine com UMA pergunta só, exatamente assim: «{pergunta}»"
DEPOIS = ("Quando a pessoa responder, proponha as mudanças só no {app} (é o app desta etapa); se ela disser que não há nada, "
          "diga só que pode seguir para a próxima etapa.")

def _e(eid, grupo, titulo, app, nome_app, precisa, pergunta, pedido=None, **mais):
    return dict({"id": eid, "grupo": grupo, "titulo": titulo, "app": app, "nome_app": nome_app, "precisa": precisa, "pergunta": pergunta, "pedido": pedido}, **mais)


# Cada etapa é UMA pergunta só (o dono: "para que de fato seja um GUIA"). A primeira etapa de cada grupo tem o pedido: a IA
# lê o app e conta o que há antes de perguntar; as outras só perguntam (sem chamar a IA: a pergunta sai na hora).
RONDAS = {
    "casa": {
        "nome": "Ronda da casa", "onde": "comodo",
        "resumo": "Um cômodo de cada vez, uma pergunta de cada vez.",
        "etapas": [
            _e("arrumar", "Tarefas", "Arrumar", "resolvia", "ResolvIA", "resolvia_tarefas", "Tem algo para arrumar em {onde}?",
               "Use resolvia_tarefas para ver as tarefas pendentes{do_comodo} e conte o que há para fazer{em}, com o prazo das que têm.",
               pedido_sem_filtro=" (a ferramenta não filtra por cômodo: veja as pendentes e fique com as que falam de «{onde}» no nome ou nas notas)"),
            _e("tarefa", "Tarefas", "Outra tarefa", "resolvia", "ResolvIA", "resolvia_tarefas", "Alguma outra tarefa para {onde}?"),
            _e("item_novo", "Itens", "Item novo", "inventario", "InventarIA", "inventario_buscar_itens", "Chegou algum item novo em {onde}?",
               "Use inventario_buscar_itens com o cômodo «{onde}» e a ordem recentes: diga quantos itens há e os últimos cadastrados."),
            _e("item_saiu", "Itens", "Item que saiu", "inventario", "InventarIA", "inventario_buscar_itens", "Algum item saiu de {onde}?"),
            _e("item_mudou", "Itens", "Item que mudou", "inventario", "InventarIA", "inventario_buscar_itens", "Algum item de {onde} mudou?"),
            _e("cons_acabando", "Consumíveis", "Acabando", "inventario", "InventarIA", "inventario_buscar_itens", "Algum consumível de {onde} está acabando?",
               "Os consumíveis não têm cômodo. Use inventario_buscar_itens com o cômodo «Consumíveis» e conte os que já passaram do dura_ate "
               "ou acabam nos próximos 30 dias (se nenhum, diga quantos há).", so_com="consumiveis"),
            _e("cons_novo", "Consumíveis", "Consumível novo", "inventario", "InventarIA", "inventario_buscar_itens", "Algum consumível novo em {onde}?", so_com="consumiveis"),
            _e("mercado", "Compras", "Mercado", "economia", "EconomIA", "economia_lista", "Precisa de algo do mercado para {onde}?",
               "Use economia_lista (e economia_reposicao, se existir) e conte o que já está na lista de compras e o que está na hora de repor."),
            _e("farmacia", "Compras", "Farmácia", "economia", "EconomIA", "economia_lista", "Precisa de algo da farmácia para {onde}?"),
            _e("pet", "Compras", "Pet shop", "economia", "EconomIA", "economia_lista", "Precisa de algo do pet shop para {onde}?"),
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
    ligado = {"consumiveis": (inv.get("opcoes") or {}).get("consumiveis") is True}  # Usar consumíveis ligado no InventarIA
    comodos = [str(c.get("nome")) for c in inv.get("comodos") or [] if isinstance(c, dict) and c.get("nome")][:60]
    out = []
    for rid, r in RONDAS.items():
        etapas = [e for e in r["etapas"] if e["precisa"] in ids and (not e.get("so_com") or ligado.get(e["so_com"]))]
        if etapas:
            out.append({"id": rid, "nome": r["nome"], "resumo": r["resumo"], "etapas": [{"id": e["id"], "titulo": e["titulo"], "grupo": e["grupo"], "app": e["nome_app"]} for e in etapas],
                        "onde": comodos, "livre": not comodos})
    return out


def etapa_de(rid, eid):
    return next((e for e in RONDAS.get(rid, {}).get("etapas", []) if e["id"] == eid), None)


def aceita(todas, fid, campo):
    """A ferramenta tem esse campo na entrada? (o ResolvIA só filtra por cômodo com Usar cômodos ligado lá)"""
    f = next((x for x in todas if x["id"] == fid), None)
    return bool(f and campo in ((f.get("entrada") or {}).get("properties") or {}))


def pergunta(rid, eid, onde):
    return etapa_de(rid, eid)["pergunta"].format(onde=onde)


def pedido(rid, eid, onde, todas, n, total):
    """O que vai para a IA numa etapa que lê o app antes de perguntar (None: a etapa só pergunta). A pessoa vê só o rótulo."""
    r, e = RONDAS[rid], etapa_de(rid, eid)
    if not e.get("pedido"):
        return None
    filtra = aceita(todas, e["precisa"], "comodo")
    texto = e["pedido"].format(onde=onde, em=f" em «{onde}»",
                               do_comodo=(f" do cômodo «{onde}» (o campo comodo)" if filtra else (e.get("pedido_sem_filtro") or "").format(onde=onde)))
    return "\n".join([
        f"{r['nome'].upper()}, cômodo «{onde}», etapa {n} de {total}: {e['titulo']} ({e['nome_app']}).",
        texto,
        FIM.format(pergunta=pergunta(rid, eid, onde)),
        DEPOIS.format(app=e["nome_app"]),
    ])


def rotulo(rid, eid, onde, n, total):
    e = etapa_de(rid, eid)
    return f"{RONDAS[rid]['nome']} · {onde} · {e['grupo']}: {e['titulo']} ({n} de {total})"


def contexto(rid, eid, onde):
    """O que a IA precisa saber quando a pessoa responde no meio de uma etapa."""
    e = etapa_de(rid, eid)
    return (f"(Estou na {RONDAS[rid]['nome']}, cômodo «{onde}», etapa {e['titulo']}: a minha próxima mensagem responde a «{e['pergunta'].format(onde=onde)}». "
            f"As mudanças desta etapa são no {e['nome_app']}; responda só a isso, sem fazer outra pergunta; se eu disser que não há nada, diga só para eu tocar em Próxima.)")
