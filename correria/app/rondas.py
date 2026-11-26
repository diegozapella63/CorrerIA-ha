"""Rondas (1.18.0): um roteiro fixo que passa pelos apps, uma etapa de cada vez, dentro da Conversa da tela.

A primeira é a Ronda da casa: a pessoa escolhe um cômodo e o CorrerIA passa pelas tarefas (ResolvIA), pelos itens e pelos
consumíveis (InventarIA) e pelas compras (EconomIA), uma pergunta de cada vez. A ordem e as perguntas são fixas, daqui; a IA só lê o app da etapa
(com as ferramentas dele), diz o que há e faz a pergunta, e depois transforma a resposta da pessoa em mudanças, que
continuam esperando o "sim", como em toda a Conversa. Cada etapa só existe se o app está ligado ao CorrerIA e oferece a
ferramenta de que ela precisa: assim a ronda respeita o que está ligado em cada app (um app sem os cômodos não filtra por
cômodo; o InventarIA sem os consumíveis não tem a etapa deles).

Para criar outra ronda daqui: mais uma entrada em RONDAS, com as etapas (o app, a ferramenta que precisa existir e o pedido).
1.30.0: a pessoa cria e muda rondas pela tela (Mais › Rondas): PADRAO são as daqui e RONDAS, o que vale agora (montar).
"""
import copy
import json
import re
import secrets
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
        "resumo": "Antes de sair para comprar: a lista, a reposição, as ofertas, os cupons e onde ir.",
        "etapas": [
            _e("lista", "Lista", "O que falta", "economia", "EconomIA", "economia_lista", "Falta algo na lista de compras?",
               "Use economia_lista e conte o que está na lista de compras (o nome de cada item)."),
            # 1.37.0: o que já não precisa sai da lista (a mesma leitura de cima; vazia, a pergunta nem aparece)
            _e("limpar", "Lista", "Pode sair", "economia", "EconomIA", "economia_tirar_da_lista", "Algum item pode sair da lista?", se_tem=True),
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
        "resumo": "Uma vez por mês: as finanças, as faturas, a agenda, as tarefas, a casa e as anotações.",
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
for _rid, _r in RONDAS.items():
    for _x in _r["etapas"]:
        _x["orig"], _x["da"] = _x["id"], _rid   # de que etapa pronta é: vale também numa ronda criada ou mudada pela pessoa

# ---------- 1.30.0 (o dono: "a possibilidade de criar novas rondas e de alterar rondas existentes"; "no modo simples por padrão
# e com uma opção para ativar o modo avançado"). PADRAO são as rondas daqui; RONDAS é o que vale agora: as daqui com as
# mudanças e as rondas da pessoa por cima (montar). O que a pessoa guarda, em /data/rondas_minhas.json:
#   {avancado: bool, rondas: {<id>: {nome, onde: bool, etapas: [{id, de: "<ronda>.<etapa>", pergunta, pedido?} ou, no modo
#   avançado, uma etapa livre {id, ferramenta, app, nome_app, titulo, pergunta, pedido?}]}}}
# Uma ronda com o id de uma daqui é a daqui mudada (Voltar ao original apaga a mudança); as novas têm o id "m" + 6 letras.
PADRAO = copy.deepcopy(RONDAS)
MAX_RONDAS, MAX_ETAPAS, MAX_PERGUNTA, MAX_PEDIDO, MAX_NOME, MAX_QUANDO = 20, 30, 160, 600, 40, 160

# 1.32.0 (o dono: "analisar entre os apps para criar um template maior ali de opções… com base nos principais temas. Exemplo:
# investimentos, bens, novidades"): etapas prontas que não estão em nenhuma ronda daqui, para escolher no Adicionar etapa. Cada uma
# usa uma ferramenta que o app tem de verdade (as Novidades do InventarIA não têm ferramenta: ficam de fora).
MAIS = {"mais": {"nome": "Mais etapas", "onde": None, "resumo": "", "etapas": [
    _e("invest", "Investimentos", "Conferir", "gerencia", "GerencIA", "gerencia_investimentos", "Algum investimento mudou de valor?",
       "Use gerencia_investimentos e conte os investimentos (o nome e o valor de hoje de cada um) e o total do patrimônio.", se_tem=True),
    _e("invest_vence", "Investimentos", "Vencendo", "gerencia", "GerencIA", "gerencia_investimentos", "Algum desses investimentos vai ser resgatado?",
       "Use gerencia_investimentos e conte os que vencem nos próximos 60 dias (o nome, o valor de hoje e o dia; o TOTAL é só o desses).", se_tem=True),
    _e("invest_novo", "Investimentos", "Novo", "gerencia", "GerencIA", "gerencia_novo_investimento", "Fez algum investimento novo?"),
    _e("fixos", "Finanças", "Fixos", "gerencia", "GerencIA", "gerencia_cadastros", "Algum fixo mudou de valor?",
       "Use gerencia_cadastros e conte os fixos (o nome e o valor de cada um).", se_tem=True),
    _e("lancados", "Finanças", "Lançamentos do mês", "gerencia", "GerencIA", "gerencia_lancamentos", "Algum desses lançamentos está errado?",
       "Use gerencia_lancamentos (sem período: o mês atual) e conte os 6 maiores gastos (o que foi, o valor e o dia).", se_tem=True),
    _e("bens", "Bens", "Conferir", "inventario", "InventarIA", "inventario_buscar_itens", "Algum bem mudou de valor?",
       "Use inventario_buscar_itens com o cômodo «Bens» e conte os bens (o nome e o valor de cada um).", so_com="bens", se_tem=True),
    _e("bem_novo", "Bens", "Novo", "inventario", "InventarIA", "inventario_cadastrar_itens", "Tem algum bem novo para cadastrar?", so_com="bens"),
    _e("valiosos", "Itens", "Mais valiosos", "inventario", "InventarIA", "inventario_buscar_itens", "Algum desses valores precisa mudar?",
       "Use inventario_buscar_itens com a ordem valor{do_comodo} e conte os 6 itens de maior valor (o nome e o valor).", se_tem=True),
    _e("repete", "Tarefas", "Que se repetem", "resolvia", "ResolvIA", "resolvia_repeticoes", "Alguma repetição precisa mudar?",
       "Use resolvia_repeticoes e conte as tarefas que se repetem (o nome e de quanto em quanto tempo).", se_tem=True),
    _e("hoje", "Tarefas", "Para hoje", "resolvia", "ResolvIA", "resolvia_tarefas", "Alguma dessas tarefas já foi feita?",
       "Use resolvia_tarefas e conte as atrasadas e as que vencem hoje (o nome e o prazo; o TOTAL é só o dessas).", se_tem=True),
    _e("agenda_hoje", "Agenda", "Hoje", "cronologia", "CronologIA", "cronologia_agenda", "Falta marcar algo como feito?",
       "Use cronologia_agenda só de hoje e conte o que ainda falta fazer hoje (o nome e o horário).", se_tem=True),
    _e("agenda_semana", "Agenda", "Esta semana", "cronologia", "CronologIA", "cronologia_agenda", "Algum compromisso da semana precisa mudar?",
       "Use cronologia_agenda de hoje a 7 dias e conte os compromissos (sem as rotinas e os remédios de todo dia), com o dia de cada um.", se_tem=True),
    _e("remedios", "Remédios", "Conferir", "cronologia", "CronologIA", "cronologia_cadastros", "Algum remédio mudou?",
       "Use cronologia_cadastros e conte só os remédios (o nome, a dose e a repetição de cada um).", se_tem=True),
    _e("placar", "Placar", "Pontos", "cronologia", "CronologIA", "cronologia_placar", "Quer dar pontos a alguém?",
       "Use cronologia_placar e conte o placar do período (cada pessoa e os pontos)."),
    _e("cupons", "Ofertas", "Cupons", "economia", "EconomIA", "economia_cupons", "Quer usar algum desses cupons?",
       "Use economia_cupons e conte até 5 cupons válidos (a loja, o código e a validade).", se_tem=True),
    _e("blocos", "Anotações", "Blocos", "memoria", "MemorIA", "memoria_resumo", "Quer anotar algo em algum bloco?",
       "Use memoria_resumo e conte os blocos de anotações (o nome de cada um)."),
    # 1.33.0 (o dono: "mais algum template que você acha útil para criar nas rondas? faça uma análise nos 7 apps"): o que as
    # ferramentas de cada app já leem e ainda não tinha etapa; as Novidades, com a inventario_novidades do InventarIA 1.98.0
    _e("novidades", "Novidades", "Equipamentos", "inventario", "InventarIA", "inventario_novidades", "Alguma dessas novidades pede uma tarefa?",
       "Use inventario_novidades{do_comodo} e conte as novidades (o item, o que é e a data; as novas primeiro).", so_com="novidades", se_tem=True),
    _e("sem_valor", "Itens", "Sem valor", "inventario", "InventarIA", "inventario_buscar_itens", "Quer informar o valor de algum desses itens?",
       "Use inventario_buscar_itens com valor_max 0{do_comodo} e conte os itens sem valor (o nome e o cômodo; até 8).", se_tem=True),
    _e("manut", "Manutenção", "Conferir", "cronologia", "CronologIA", "cronologia_cadastros", "Alguma dessas manutenções já foi feita?",
       "Use cronologia_cadastros{do_comodo} e conte só as manutenções (o nome e a próxima vez de cada uma).",
       pedido_sem_filtro=" (conte só as que citam «{onde}»)", se_tem=True),
    _e("manut_nova", "Manutenção", "Nova", "cronologia", "CronologIA", "cronologia_criar_compromisso", "Falta cadastrar alguma manutenção?"),
    _e("remedio_hoje", "Remédios", "De hoje", "cronologia", "CronologIA", "cronologia_resumo", "Algum desses remédios já foi tomado?",
       "Use cronologia_resumo e conte os remédios de hoje que ainda não foram tomados (o nome, de quem é e o horário; o TOTAL é só o desses).", se_tem=True),
    _e("sem_prazo", "Tarefas", "Sem prazo", "resolvia", "ResolvIA", "resolvia_tarefas", "Alguma dessas tarefas precisa de prazo?",
       "Use resolvia_tarefas{do_comodo} e conte as pendentes que não têm prazo (o nome e a lista; até 8; o TOTAL é só o dessas).", se_tem=True),
    _e("semana", "Tarefas", "Próximos 7 dias", "resolvia", "ResolvIA", "resolvia_resumo", "Alguma dessas tarefas precisa mudar de prazo?",
       "Use resolvia_resumo e conte as tarefas que vencem nos próximos 7 dias (o nome e o dia; o TOTAL é só o dessas).", se_tem=True),
    _e("atrasadas", "Finanças", "Contas atrasadas", "gerencia", "GerencIA", "gerencia_contas_a_pagar", "Alguma dessas contas atrasadas já foi paga?",
       "Use gerencia_contas_a_pagar e conte só as atrasadas (o nome, o valor e o vencimento; o TOTAL é só o dessas).", se_tem=True),
    _e("recebidos", "Finanças", "Recebimentos", "gerencia", "GerencIA", "gerencia_lancamentos", "Falta lançar algum recebimento do mês?",
       "Use gerencia_lancamentos (sem período: o mês atual) e conte só os recebimentos (o que foi, o valor e o dia)."),
    _e("fixo_novo", "Finanças", "Fixo novo", "gerencia", "GerencIA", "gerencia_novo_fixo", "Tem algum gasto fixo novo?"),
    _e("lista_limpar", "Compras", "Limpar a lista", "economia", "EconomIA", "economia_lista", "Algum item pode sair da lista?",
       "Use economia_lista e conte os itens da lista de compras (o nome de cada um; até 10).", se_tem=True),
    _e("folhas", "Anotações", "Últimas folhas", "memoria", "MemorIA", "memoria_buscar", "Alguma dessas anotações precisa ser atualizada?",
       "Use memoria_buscar sem nada e conte as 5 folhas editadas por último (o bloco e o título de cada uma).", se_tem=True),
    # 1.35.0 (o dono: "pode criar"): as três que pediam ferramenta nova: gerencia_ajustar_saldo (GerencIA 1.85.0), o sem_foto do
    # inventario_buscar_itens (InventarIA 1.99.0) e o parados_ha_dias do memoria_resumo (MemorIA 1.47.0)
    _e("saldo", "Finanças", "Saldo do caixa", "gerencia", "GerencIA", "gerencia_ajustar_saldo", "O saldo do caixa está certo?",
       "Use gerencia_resumo e conte só o saldo do caixa de hoje e quanto entrou e saiu no mês."),
    _e("sem_foto", "Itens", "Sem foto", "inventario", "InventarIA", "inventario_buscar_itens", "Quer mandar a foto de algum desses itens?",
       "Use inventario_buscar_itens com sem_foto true{do_comodo} e conte os itens sem foto (o nome e o cômodo; até 8).", se_tem=True),
    _e("parados", "Anotações", "Blocos parados", "memoria", "MemorIA", "memoria_resumo", "Algum desses blocos pode ser arquivado?",
       "Use memoria_resumo com parados_ha_dias 60 e conte os blocos parados (o nome e há quantos dias).", se_tem=True),
    # 1.36.0 (o dono: "veja mais quais etapas e ferramentas podem ficar nas rondas como templates para uso"): o OdisseIA (os
    # filmes, as séries e os jogos), o que o EconomIA e a CronologIA fazem e ainda não tinham etapa (repor, o preço, pular)
    _e("continuar", "Séries", "Continuar vendo", "odisseia", "OdisseIA", "odisseia_proximo_episodio", "Viu algum episódio novo?",
       "Use odisseia_resumo e conte só as séries em andamento (o nome, o episódio em que parou e quantos faltam; até 8).", se_tem=True),
    _e("quero_ver", "Filmes e séries", "Quero ver", "odisseia", "OdisseIA", "odisseia_marcar", "Já viu algum desses?",
       "Use odisseia_buscar com situacao quero e conte os filmes e as séries que a casa quer ver (o nome e o ano; até 8; sem os jogos).", se_tem=True),
    _e("em_alta", "Sugestões", "Em alta", "odisseia", "OdisseIA", "odisseia_lista_pronta", "Quer pôr algum desses na lista?",
       "Use odisseia_lista_pronta com lista alta e conte os títulos que ainda não estão na lista da casa (o nome e o tipo; até 8)."),
    _e("quero_jogar", "Jogos", "Quero jogar", "odisseia", "OdisseIA", "odisseia_marcar", "Já jogou algum desses?",
       "Use odisseia_buscar com tipo jogo e situacao quero e conte os jogos que a casa quer jogar (o nome e o ano; até 8).", se_tem=True),
    _e("reposto", "Reposição", "Já repôs", "economia", "EconomIA", "economia_reposto", "Repôs algum desses?",
       "Use economia_reposicao e conte o que está na hora de repor (o nome e quando venceu; até 8).", se_tem=True),
    _e("precos", "Lista", "Preços", "economia", "EconomIA", "economia_preco", "Quer saber o preço de algum desses?",
       "Use economia_lista e conte os itens da lista de compras (o nome de cada um; até 10).", se_tem=True),
    _e("pular", "Agenda", "Pular hoje", "cronologia", "CronologIA", "cronologia_pular", "Alguma coisa de hoje não vai acontecer?",
       "Use cronologia_agenda só de hoje e conte o que ainda falta fazer hoje (o nome e o horário).", se_tem=True),
    # 1.37.0 (o dono: "revisa se mais etapas ou ferramentas devem ser integradas nas rondas… as etapas e a ronda devem ficar
    # completíssimas para o modo manual"): toda leitura dos apps que ainda não tinha etapa, e as das ferramentas novas
    # (gerencia_beneficios e gerencia_oportunidades no GerencIA 1.90.0; o casa_estado com ligados e comodo). tambem: outra
    # ferramenta que precisa existir (a etapa lê um app e muda outro).
    _e("comece", "Tarefas", "Comece por aqui", "resolvia", "ResolvIA", "resolvia_comece_por_aqui", "Quer começar por alguma destas?",
       "Use resolvia_comece_por_aqui e conte as tarefas escolhidas para começar agora (o nome e o porquê de cada uma; até 5).", se_tem=True),
    _e("amanha", "Agenda", "Amanhã", "cronologia", "CronologIA", "cronologia_agenda", "Algum compromisso de amanhã precisa mudar?",
       "Use cronologia_agenda só de amanhã e conte os compromissos (sem as rotinas e os remédios de todo dia), com o horário de cada um.", se_tem=True),
    _e("faturas_email", "Faturas", "Faturas do e-mail", "gerencia", "GerencIA", "gerencia_faturas_do_email", "Quer lançar alguma dessas faturas?",
       "Use gerencia_faturas_do_email e conte as faturas e as contas que esperam a conferência (de quem é, o total e quando chegou).", se_tem=True),
    _e("beneficios", "Benefícios", "Usados", "gerencia", "GerencIA", "gerencia_beneficios", "Usou algum desses benefícios?",
       "Use gerencia_beneficios e conte os benefícios (sem as milhas) com o que sobra no período de cada um e quando renova (até 8).", se_tem=True),
    _e("milhas", "Milhas", "Saldo", "gerencia", "GerencIA", "gerencia_beneficios", "O saldo das milhas está certo?",
       "Use gerencia_beneficios e conte só as milhas: o programa, de quem é, o saldo de hoje e o que vence nos próximos 90 dias.", se_tem=True),
    _e("oportunidades", "Investimentos", "Oportunidades", "gerencia", "GerencIA", "gerencia_oportunidades", "Quer aproveitar alguma dessas oportunidades?",
       "Use gerencia_oportunidades e conte as oportunidades de investimento (o que é, a taxa e por que vale; até 5; sem as assinaturas).", se_tem=True),
    _e("assinaturas", "Assinaturas", "Em promoção", "gerencia", "GerencIA", "gerencia_oportunidades", "Quer mudar de plano em alguma dessas assinaturas?",
       "Use gerencia_oportunidades e conte só as assinaturas em promoção (o serviço, o preço e até quando).", se_tem=True),
    _e("contas_viagem", "Contas", "Contas do período", "gerencia", "GerencIA", "gerencia_marcar_pago", "Quer pagar alguma dessas contas antes de viajar?",
       "Use gerencia_contas_a_pagar dos próximos 30 dias e conte as contas (o nome, o valor e o dia).", se_tem=True),
    _e("avaliar", "Consumíveis", "Avaliação", "inventario", "InventarIA", "inventario_avaliar", "Quer a avaliação de algum desses consumíveis?",
       "Use inventario_buscar_itens com o cômodo «Consumíveis» e conte os consumíveis (o nome de cada um; até 10).", so_com="consumiveis", se_tem=True),
    _e("estreias", "Sugestões", "Estreias", "odisseia", "OdisseIA", "odisseia_lista_pronta", "Quer pôr alguma dessas estreias na lista?",
       "Use odisseia_lista_pronta com lista estreias e conte os títulos que ainda não estão na lista da casa (o nome e o tipo; até 8)."),
    _e("lancamentos", "Lançamentos", "Vão sair", "cronologia", "CronologIA", "cronologia_criar_compromisso", "Quer um lembrete na agenda de algum desses lançamentos?",
       "Use odisseia_resumo e conte os episódios e os jogos que vão sair (o nome, o episódio e o dia).", se_tem=True, tambem=("odisseia_resumo",)),
    _e("ferias", "Agenda", "Férias", "cronologia", "CronologIA", "cronologia_ferias", "Quer ligar o modo férias para a viagem?",
       "Use cronologia_agenda de hoje a 30 dias e conte os compromissos (sem as rotinas e os remédios de todo dia), com o dia de cada um."),
    _e("remedios_levar", "Remédios", "Para a viagem", "economia", "EconomIA", "economia_por_na_lista", "Precisa comprar algum desses remédios antes de viajar?",
       "Use cronologia_cadastros e conte só os remédios (o nome e a dose de cada um).", se_tem=True, tambem=("cronologia_cadastros",)),
    _e("lista_viagem", "Viagem", "Compras", "economia", "EconomIA", "economia_por_na_lista", "Precisa comprar algo para a viagem?"),
    _e("ligado", "Ligados", "Ligado ou aberto", "casa", "Casa", "casa_estado", "Quer mexer em algum desses?",
       "Use casa_estado com ligados true{do_comodo} e conte o que está ligado ou aberto (o nome e o estado; até 8).", se_tem=True),
    # 1.38.0 (o dono: "cria mais para a casa, energia, cores da luz talvez, temperatura cômodos?"; "a MemorIA parece que
    # tem poucas etapas"; "Casa e OdisseIA também"; "o ResolvIA também parece que tem pouco"; "do MemorIA poderia ter pra
    # revisar horários"): as visões prontas do casa_estado (tipo) e mais etapas de cada app, com as ferramentas que eles têm
    _e("energia", "Energia", "O que gasta agora", "casa", "Casa", "casa_estado", "Quer desligar algum desses?",
       "Use casa_estado com tipo energia{do_comodo} e conte o que mais gasta agora (o nome, os watts e o cômodo; até 8).", se_tem=True),
    _e("luzes", "Luzes", "Acesas e cores", "casa", "Casa", "casa_estado", "Quer mudar alguma luz?",
       "Use casa_estado com tipo luzes{do_comodo} e conte as luzes acesas (o nome, o brilho, a cor e o cômodo; até 8).", se_tem=True),
    _e("temperatura", "Clima", "Temperatura dos cômodos", "casa", "Casa", "casa_estado", "Quer mudar a temperatura do ar?",
       "Use casa_estado com tipo temperatura{do_comodo} e conte a temperatura e a umidade de cada cômodo (e o ar ligado, com o alvo).", se_tem=True),
    _e("seguranca", "Segurança", "Portas e fechaduras", "casa", "Casa", "casa_estado", "Quer trancar alguma porta?",
       "Use casa_estado com tipo seguranca{do_comodo} e conte as fechaduras, as portas e janelas abertas e o alarme (o nome e o estado).", se_tem=True),
    _e("baterias", "Baterias", "Fracas", "casa", "Casa", "casa_estado", "Quer anotar alguma dessas para trocar?",
       "Use casa_estado com tipo baterias{do_comodo} e conte as baterias fracas (o nome, a carga e o cômodo; até 10).", se_tem=True),
    _e("sem_resposta", "Aparelhos", "Sem resposta", "casa", "Casa", "casa_estado", "Algum desses precisa de atenção?",
       "Use casa_estado com tipo sem_resposta{do_comodo} e conte o que o Home Assistant não alcança (o nome e o cômodo; até 10).", se_tem=True),
    _e("aspirador", "Limpeza", "Aspirador", "casa", "Casa", "casa_comando", "Quer ligar o aspirador?",
       "Use casa_estado com busca aspirador e conte cada aspirador (o nome e o estado; se não houver nenhum, diga).", se_tem=True, tambem=("casa_estado",)),
    _e("cenas", "Cenas", "Ligar uma cena", "casa", "Casa", "casa_comando", "Quer ligar alguma cena?",
       "Use casa_estado com busca cena e conte as cenas da casa (o nome de cada uma; até 10).", se_tem=True, tambem=("casa_estado",)),
    _e("listas", "Listas", "Conferir", "resolvia", "ResolvIA", "resolvia_editar_lista", "Alguma lista precisa mudar?",
       "Use resolvia_resumo e conte as listas (o nome e quantas tarefas pendentes cada uma tem).", se_tem=True, tambem=("resolvia_resumo",)),
    _e("concluidas", "Tarefas", "Feitas", "resolvia", "ResolvIA", "resolvia_concluir_tarefa", "Alguma dessas precisa ser feita de novo?",
       "Use resolvia_tarefas com situacao concluidas e limite 10 e conte as tarefas concluídas (o nome e a lista).", se_tem=True),
    _e("externos", "Serviços externos", "Combinar", "resolvia", "ResolvIA", "resolvia_tarefas", "Já combinou algum desses serviços?",
       "Use resolvia_tarefas e conte só as tarefas com serviço externo (o nome, quem faz e o prazo; sem prazo, diga).", se_tem=True),
    _e("pontos", "Pontos", "Quanto vale", "resolvia", "ResolvIA", "resolvia_pontos", "Alguma tarefa precisa valer outros pontos?",
       "Use resolvia_pontos e conte quanto vale cada tarefa (o nome e os pontos; até 10).", se_tem=True),
    _e("repete_nova", "Repetição", "Repetir sozinha", "resolvia", "ResolvIA", "resolvia_repeticoes", "Alguma tarefa devia se repetir sozinha?",
       "Use resolvia_repeticoes e conte as tarefas que já voltam sozinhas (o nome e de quanto em quanto tempo)."),
    _e("compras_rv", "Compras", "Lista do ResolvIA", "resolvia", "ResolvIA", "resolvia_concluir_tarefa", "Comprou algum desses?",
       "Use resolvia_resumo para achar a lista de compras (a que tem compra ou mercado no nome), depois resolvia_tarefas nela, e conte os itens pendentes (até 10).",
       se_tem=True, tambem=("resolvia_resumo",)),
    _e("horarios", "Horários", "Quando abrem", "memoria", "MemorIA", "memoria_editar_bloco", "Algum horário precisa mudar?",
       "Use memoria_resumo e conte os blocos que abrem sozinhos, com o período ou o horário de cada um (e de quem é).", se_tem=True, tambem=("memoria_resumo",)),
    _e("sem_horario", "Horários", "Sem horário", "memoria", "MemorIA", "memoria_editar_bloco", "Algum desses blocos devia abrir sozinho?",
       "Use memoria_resumo e conte os blocos que não abrem sozinhos (o nome e a categoria).", se_tem=True, tambem=("memoria_resumo",)),
    _e("bloco_agora", "Agora", "Bloco de agora", "memoria", "MemorIA", "memoria_acrescentar", "Quer anotar algo no bloco de agora?",
       "Use memoria_resumo e conte o bloco do momento (o nome e a folha aberta, com o começo do que ela tem).", tambem=("memoria_resumo",)),
    _e("categorias_mem", "Categorias", "Conferir", "memoria", "MemorIA", "memoria_editar_categoria", "Alguma categoria precisa mudar?",
       "Use memoria_resumo e conte as categorias, com quantos blocos tem cada uma.", se_tem=True, tambem=("memoria_resumo",)),
    _e("sem_categoria", "Sem categoria", "Blocos", "memoria", "MemorIA", "memoria_editar_bloco", "Quer pôr algum desses blocos numa categoria?",
       "Use memoria_resumo e conte os blocos sem categoria (o nome de cada um).", se_tem=True, tambem=("memoria_resumo",)),
    _e("arquivados", "Arquivados", "Voltar", "memoria", "MemorIA", "memoria_editar_bloco", "Algum bloco arquivado deve voltar?",
       "Use memoria_resumo com arquivados true e conte só os blocos arquivados (o nome de cada um).", se_tem=True, tambem=("memoria_resumo",)),
    _e("nova_anotacao", "Anotações", "Nova", "memoria", "MemorIA", "memoria_nova_folha", "Tem algo novo para anotar?"),
    _e("avaliados", "Sugestões", "Mais bem avaliados", "odisseia", "OdisseIA", "odisseia_adicionar", "Quer pôr algum desses na lista?",
       "Use odisseia_lista_pronta com lista avaliados e conte os títulos que ainda não estão na lista da casa (o nome e o tipo; até 8).", tambem=("odisseia_lista_pronta",)),
    _e("populares", "Sugestões", "Mais populares", "odisseia", "OdisseIA", "odisseia_adicionar", "Quer pôr algum dos populares na lista?",
       "Use odisseia_lista_pronta com lista populares e conte os títulos que ainda não estão na lista da casa (o nome e o tipo; até 8).", tambem=("odisseia_lista_pronta",)),
    _e("colecoes", "Coleções", "Para completar", "odisseia", "OdisseIA", "odisseia_adicionar_colecao", "Quer pôr alguma dessas coleções na lista?",
       "Use odisseia_lista_pronta com lista colecoes e conte as coleções que a casa ainda não completou (o nome e quantos faltam; até 6).", tambem=("odisseia_lista_pronta",)),
    _e("jogos_alta", "Jogos", "Em alta", "odisseia", "OdisseIA", "odisseia_adicionar", "Quer pôr algum desses jogos na lista?",
       "Use odisseia_lista_pronta com lista alta e tipo jogo e conte os jogos que ainda não estão na lista da casa (o nome; até 8).", tambem=("odisseia_lista_pronta",)),
    _e("sem_categoria_od", "Sem categoria", "Títulos", "odisseia", "OdisseIA", "odisseia_marcar_varios", "Quer pôr algum desses numa categoria?",
       "Use odisseia_buscar e conte os títulos sem categoria (o nome e o tipo; até 10).", se_tem=True, tambem=("odisseia_buscar",)),
    _e("quem_viu", "Concluídos", "Quem viu", "odisseia", "OdisseIA", "odisseia_marcar_varios", "Falta marcar quem viu algum desses?",
       "Use odisseia_buscar com situacao visto e conte os últimos títulos concluídos (o nome e quem viu; até 8).", se_tem=True, tambem=("odisseia_buscar",)),
    _e("novo_titulo", "Filmes e séries", "Começou a ver", "odisseia", "OdisseIA", "odisseia_adicionar", "Começou a ver algo novo?"),
    _e("aniversarios", "Aniversários", "Próximos", "cronologia", "CronologIA", "cronologia_agenda", "Precisa comprar algum presente?",
       "Use cronologia_agenda de hoje a 30 dias com busca aniversário e conte os aniversários (de quem e o dia).", se_tem=True),
]}}
for _x in MAIS["mais"]["etapas"]:
    _x["orig"], _x["da"] = _x["id"], "mais"

# 1.34.0 (o dono, à oferta de duas rondas inteiras prontas, a do patrimônio e a da semana: "pode fazer"): duas rondas daqui
# montadas com as etapas do MAIS (cada etapa leva o de "mais.<id>": no catálogo ela aparece uma vez só, pelo MAIS)
def _ronda_de_mais(nome, resumo, ids):
    por_id = {e["id"]: e for e in MAIS["mais"]["etapas"]}
    return {"nome": nome, "onde": None, "resumo": resumo, "de_mais": True, "etapas": [dict(copy.deepcopy(por_id[i]), de=f"mais.{i}") for i in ids]}


for _rid, _r in (("patrimonio", _ronda_de_mais("Ronda do patrimônio", "Os investimentos, as oportunidades, as milhas, os bens, os itens de valor e as novidades dos equipamentos.",
                                               ["invest", "invest_vence", "invest_novo", "oportunidades", "milhas", "bens", "bem_novo", "valiosos", "sem_valor", "sem_foto", "novidades"])),
                 ("semana", _ronda_de_mais("Ronda da semana", "Uma vez por semana: as tarefas, os serviços externos, a agenda, os aniversários, as manutenções, os remédios, as contas atrasadas e o placar.",
                                           ["hoje", "comece", "semana", "externos", "agenda_semana", "aniversarios", "manut", "remedios", "atrasadas", "placar"])),
                 # 1.36.0: a do OdisseIA, sem cômodo
                 ("lazer", _ronda_de_mais("Ronda do lazer", "As séries em andamento, o que vai sair, o que a casa quer ver e jogar, quem viu e as sugestões.",
                                          ["continuar", "quem_viu", "lancamentos", "quero_ver", "quero_jogar", "em_alta", "estreias", "colecoes"])),
                 # 1.37.0: cinco rondas novas, todas com as etapas do MAIS
                 ("dia", _ronda_de_mais("Ronda do dia", "De manhã: a agenda, os remédios e as tarefas de hoje, e por onde começar.",
                                        ["agenda_hoje", "remedio_hoje", "hoje", "comece", "pular"])),
                 ("noite", _ronda_de_mais("Ronda da noite", "Antes de dormir: o que ficou ligado ou aberto, os remédios, o que falta marcar e o dia de amanhã.",
                                          ["ligado", "remedio_hoje", "agenda_hoje", "amanha"])),
                 ("financas", _ronda_de_mais("Ronda das finanças", "As faturas do e-mail, as contas atrasadas, os lançamentos, o saldo, os benefícios e as milhas.",
                                             ["faturas_email", "atrasadas", "lancados", "recebidos", "saldo", "beneficios", "milhas", "assinaturas"])),
                 ("anotacoes", _ronda_de_mais("Ronda das anotações", "Os blocos, as últimas folhas, os horários, as categorias, os parados e os arquivados.",
                                              ["blocos", "folhas", "horarios", "sem_horario", "sem_categoria", "parados", "arquivados"])),
                 # 1.38.0: a casa no Home Assistant, sem cômodo
                 ("aparelhos", _ronda_de_mais("Ronda dos aparelhos", "A casa no Home Assistant: o que ficou ligado, o consumo, as luzes, a temperatura, as portas, as baterias e o que não responde.",
                                              ["ligado", "energia", "luzes", "temperatura", "seguranca", "baterias", "sem_resposta", "aspirador"])),
                 ("viagem", _ronda_de_mais("Ronda da viagem", "Antes de viajar: as férias, as contas do período, os remédios, as compras e a casa.",
                                           ["ferias", "contas_viagem", "remedios_levar", "lista_viagem", "ligado"]))):
    RONDAS[_rid] = _r
    PADRAO[_rid] = copy.deepcopy(_r)


# 1.37.0: e etapas do MAIS também nas rondas daqui que não são feitas só delas: (ronda, depois de qual etapa, [as do MAIS])
for _rid, _depois, _ids in (("casa", "rotina_sai", ["manut"]), ("casa", "item_mudou", ["sem_foto"]), ("casa", "pet", ["ligado"]),
                            ("compras", "ofertas", ["cupons"]),
                            ("chegada", "fora", ["reposto"]),
                            ("mes", "contas", ["recebidos", "fixos", "saldo", "faturas_email"]), ("mes", "tarefas", ["repete"]),
                            ("mes", "repor", ["parados"])):
    _por_id = {e["id"]: e for e in MAIS["mais"]["etapas"]}
    for _r in (RONDAS[_rid], PADRAO[_rid]):
        _k = next(i for i, e in enumerate(_r["etapas"]) if e["id"] == _depois) + 1
        _r["etapas"][_k:_k] = [dict(copy.deepcopy(_por_id[i]), de=f"mais.{i}") for i in _ids]


def precisa_todas(e):
    """As ferramentas que a etapa usa e que precisam existir: a dela e as de tambem (a que lê outro app)."""
    return (e["precisa"], *e.get("tambem", ()))


def catalogo():
    """As etapas prontas, para escolher numa ronda: [{de, app, nome_app, grupo, titulo, pergunta, le, precisa, tambem, ronda}].
    Uma etapa do MAIS numa ronda daqui aparece uma vez só, pelo MAIS."""
    return [{"de": f"{rid}.{e['id']}", "app": e["app"], "nome_app": e["nome_app"], "grupo": e["grupo"], "titulo": e["titulo"],
             "pergunta": _mostrar(e["pergunta"]), "le": bool(e.get("pedido")), "precisa": e["precisa"], "tambem": list(e.get("tambem", ())), "ronda": r["nome"]}
            for rid, r in {**PADRAO, **MAIS}.items() if not r.get("de_mais") for e in r["etapas"] if rid == "mais" or not e.get("de")]


def _pronta(de):
    rid, _, eid = str(de or "").partition(".")
    return next((e for e in (PADRAO.get(rid) or MAIS.get(rid) or {}).get("etapas", []) if e["id"] == eid), None)


# ---------- 1.32.0 (o dono: "criar algo aqui para indicar quando a pergunta deve ocorrer, para eu escrever algo como: não
# perguntar sobre pet shop no cômodo do quarto"): numa ronda por cômodo, cada etapa pode ter o Quando perguntar. A frase é da
# pessoa, mas quem decide não é a IA: o app acha na frase os nomes dos cômodos (os do InventarIA; o nome mais comprido primeiro,
# para «Quarto de hóspedes» não virar «Quarto») e vê se a frase nega (não, nunca, menos, exceto, sem, fora, pular): negando, a
# pergunta não sai nesses cômodos (fora); senão, só sai neles (so). A tela mostra o que foi entendido, embaixo do campo.
NEGA_RE = re.compile(r"(?<![a-z0-9])(nao|nunca|menos|exceto|sem|fora|pular|pule|tirar|tire)(?![a-z0-9])")


def _norm(t):
    import unicodedata
    return " ".join("".join(c for c in unicodedata.normalize("NFD", str(t or "").lower()) if unicodedata.category(c) != "Mn").split())


def quando_regra(texto, comodos):
    """{fora: [cômodos]} | {so: [cômodos]} | {} (nenhum cômodo reconhecido na frase)."""
    t, achados = f" {_norm(texto)} ", []
    for c in sorted({str(c) for c in comodos or [] if _norm(c)}, key=lambda c: (-len(_norm(c)), c)):
        alvo = re.compile(rf"(?<![a-z0-9]){re.escape(_norm(c))}(?![a-z0-9])")
        if alvo.search(t):
            achados.append(c)
            t = alvo.sub(" ", t)
    if not achados:
        return {}
    ordem = [c for c in comodos if c in achados]
    return {"fora": ordem} if NEGA_RE.search(_norm(texto)) else {"so": ordem}


def vale_em(e, onde):
    """A etapa sai neste cômodo? (sem regra, ou numa ronda sem cômodo, sempre)"""
    n = _norm(onde)
    if not e or not n:
        return True
    if e.get("fora"):
        return n not in {_norm(c) for c in e["fora"]}
    if e.get("so"):
        return n in {_norm(c) for c in e["so"]}
    return True


def _guardar_texto(t, maximo):
    """O texto da pessoa vai para um .format: as chaves dela não são campos (só {onde} é)."""
    t = " ".join(str(t or "").split())[:maximo]
    return t.replace("{", "{{").replace("}", "}}").replace("{{onde}}", "{onde}")


def _mostrar(t):
    return str(t or "").replace("{{", "{").replace("}}", "}")


def _pergunta_ok(t):
    """Cada etapa é uma pergunta só: uma frase que termina com um ponto de interrogação."""
    t = " ".join(str(t or "").split())
    if len(t) < 5:
        raise ValueError("Escreva a pergunta de cada etapa.")
    if len(t) > MAX_PERGUNTA:
        raise ValueError(f"A pergunta fica com até {MAX_PERGUNTA} letras.")
    if t.count("?") != 1 or not t.endswith("?"):
        raise ValueError("Cada etapa é uma pergunta só, terminando com «?».")
    return t


def conferir_ronda(dados, antes=None, avancado=False, leituras=None, comodos=None):
    """Confere o que veio da tela e devolve a ronda como fica guardada. antes: a ronda guardada hoje (o que é do modo
    avançado continua nela quando o modo está desligado). leituras: {id da ferramenta: {app, nome_app, titulo}}, as
    ferramentas de leitura ligadas agora (para as etapas livres do modo avançado). ValueError diz o que vale."""
    nome = " ".join(str(dados.get("nome") or "").split())[:MAX_NOME]
    if len(nome) < 2:
        raise ValueError("Dê um nome à ronda.")
    lista = dados.get("etapas")
    if not isinstance(lista, list) or not lista:
        raise ValueError("A ronda precisa de pelo menos uma etapa.")
    if len(lista) > MAX_ETAPAS:
        raise ValueError(f"Uma ronda tem até {MAX_ETAPAS} etapas.")
    velhas = {x["id"]: x for x in (antes or {}).get("etapas", [])}
    etapas, ids = [], set()
    for x in lista:
        if not isinstance(x, dict):
            raise ValueError("Etapa inválida.")
        velha = velhas.get(str(x.get("id") or ""))
        pronta = _pronta(x.get("de"))
        livre = not pronta and (velha if velha and velha.get("ferramenta") and not avancado else x)
        if pronta:
            e = {"de": str(x["de"]), "pergunta": _guardar_texto(_pergunta_ok(x.get("pergunta") or _mostrar(pronta["pergunta"])), MAX_PERGUNTA)}
            base = pronta["id"]
        elif livre and livre.get("ferramenta"):
            if not avancado and not velha:
                raise ValueError("Uma etapa livre só no modo avançado.")
            f = (leituras or {}).get(str(livre["ferramenta"])) or (velha if velha and velha.get("ferramenta") == livre["ferramenta"] else None)
            if not f:
                raise ValueError("Escolha o que a IA lê na etapa livre (o app precisa estar ligado).")
            titulo = (" ".join(str(livre.get("titulo") or "").split()) or str(f.get("titulo") or "Etapa livre"))[:MAX_NOME]
            e = {"ferramenta": str(livre["ferramenta"]), "app": f["app"], "nome_app": f["nome_app"], "titulo": titulo,
                 "pergunta": _guardar_texto(_pergunta_ok(x.get("pergunta")), MAX_PERGUNTA)}
            base = "livre"
        else:
            raise ValueError("Essa etapa não existe mais. Tire-a da ronda.")
        # o que a IA lê: só o modo avançado muda; desligado, fica o que já estava guardado
        pedido = " ".join(str(x.get("pedido") or "").split()) if avancado else _mostrar((velha or {}).get("pedido"))
        if len(pedido) > MAX_PEDIDO:
            raise ValueError(f"O que a IA lê fica com até {MAX_PEDIDO} letras.")
        if pedido:
            e["pedido"] = _guardar_texto(pedido, MAX_PEDIDO)
        quando = " ".join(str(x.get("quando") or "").split()) if dados.get("onde") is True else ""
        if len(quando) > MAX_QUANDO:
            raise ValueError(f"O Quando perguntar fica com até {MAX_QUANDO} letras.")
        if quando:  # 1.32.0: o que a frase quer dizer fica guardado junto (fora ou so), com os cômodos de agora
            regra = quando_regra(quando, comodos)
            if not regra:
                raise ValueError(f"Em «Quando perguntar» de {e.get('titulo') or pronta['titulo']}, escreva o nome de um cômodo como está no InventarIA."
                                 if comodos else "O Quando perguntar precisa dos cômodos do InventarIA (ligue o CorrerIA nele).")
            e.update(quando=quando, **regra)
        eid, n = (velha or {}).get("id") or base, 2
        while eid in ids:
            eid, n = f"{base}_{n}", n + 1
        ids.add(eid)
        etapas.append(dict(e, id=eid))
    return {"nome": nome, "onde": dados.get("onde") is True, "etapas": etapas}


def nova_id(existentes):
    while True:
        rid = "m" + secrets.token_hex(3)
        if rid not in existentes:
            return rid


def montar(minhas):
    """Refaz RONDAS: as daqui (PADRAO) com as rondas da pessoa por cima. Uma etapa cuja etapa pronta não existe mais sai."""
    novas = copy.deepcopy(PADRAO)
    for rid, m in ((minhas or {}).get("rondas") or {}).items():
        if not isinstance(m, dict) or not re.fullmatch(r"[a-z0-9_]{1,20}", str(rid)):
            continue
        etapas = []
        for x in m.get("etapas") or []:
            pronta = _pronta(x.get("de")) if isinstance(x, dict) else None
            if pronta:
                e = copy.deepcopy(pronta)
                e.update(id=str(x.get("id") or pronta["id"]), pergunta=x.get("pergunta") or pronta["pergunta"], de=x["de"])
                if x.get("pedido"):  # o modo avançado: a pessoa escreveu o que a IA lê
                    e["pedido"] = f"Use {e['precisa']}{{do_comodo}}. {x['pedido']}"
                    e.pop("pedido_com", None)
                    e["pedido_meu"] = x["pedido"]
            elif isinstance(x, dict) and x.get("ferramenta"):
                e = _e(str(x.get("id") or "livre"), x.get("nome_app") or "", x.get("titulo") or "", x.get("app") or "", x.get("nome_app") or "",
                       x["ferramenta"], x.get("pergunta") or "", f"Use {x['ferramenta']}{{do_comodo}} e conte o que há. {x.get('pedido') or ''}".strip(),
                       livre=True, pedido_meu=x.get("pedido") or "")
                e["orig"], e["da"] = e["id"], rid
            else:
                continue
            if m.get("onde") and x.get("quando"):  # 1.32.0: o Quando perguntar (só numa ronda por cômodo)
                e["quando"] = str(x["quando"])
                for k in ("fora", "so"):
                    if isinstance(x.get(k), list) and x[k]:
                        e[k] = [str(c) for c in x[k]]
            etapas.append(e)
        if etapas:
            daqui = PADRAO.get(rid)
            novas[rid] = {"nome": str(m.get("nome") or (daqui or {}).get("nome") or "Ronda"), "onde": "comodo" if m.get("onde") else "",
                          "resumo": (daqui or {}).get("resumo") or "Criada por você.", "etapas": etapas, "minha": not daqui, "mudada": bool(daqui)}
    RONDAS.clear()
    RONDAS.update(novas)


def para_editor(ids_ligados=None):
    """As rondas para a tela de editar: [{id, nome, onde, minha, mudada, etapas: [{id, de?, ferramenta?, app, grupo, titulo,
    pergunta, pedido (o que a pessoa escreveu), le, ligada}]}]. ligada: o app da etapa está ligado agora."""
    ok = (lambda f: True) if ids_ligados is None else (lambda f: f in ids_ligados)
    return [{"id": rid, "nome": r["nome"], "onde": bool(r["onde"]), "minha": bool(r.get("minha")), "mudada": bool(r.get("mudada")),
             "etapas": [{"id": e["id"], **({"de": e["de"]} if e.get("de") else {"de": f"{rid}.{e['id']}"} if not e.get("livre") else {"ferramenta": e["precisa"]}),
                         "app": e["nome_app"], "grupo": e["grupo"], "titulo": e["titulo"], "pergunta": _mostrar(e["pergunta"]),
                         "pedido": _mostrar(e.get("pedido_meu") or ""), "quando": e.get("quando") or "", "le": bool(e.get("pedido")),
                         "ligada": all(ok(f) for f in precisa_todas(e))} for e in r["etapas"]]}
            for rid, r in RONDAS.items()]


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
        etapas = [e for e in r["etapas"] if all(f in ids for f in precisa_todas(e)) and (not e.get("so_com") or e["so_com"] in ligado)]
        if etapas:
            onde = comodos if r["onde"] else []
            out.append({"id": rid, "nome": r["nome"], "resumo": r["resumo"],
                        "etapas": [{"id": e["id"], "titulo": e["titulo"], "grupo": e["grupo"], "app": e["nome_app"]} for e in etapas],
                        "onde": onde, "livre": bool(r["onde"]) and not onde, "sem_onde": not r["onde"], "opcoes": sorted(ligado)})
    return out


def opcoes(inv):
    """O que está ligado no InventarIA e muda as etapas: bens (Usar bens), consumiveis (Usar consumíveis), consumiveis_por_comodo e novidades (1.33.0)."""
    o = inv.get("opcoes") or {}
    return {k for k in ("bens", "consumiveis", "consumiveis_por_comodo", "novidades") if o.get(k) is True}


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
    # 1.32.0: numa ronda sem cômodo não há cômodo a dizer (antes saía «do cômodo «»» num pedido escrito pela pessoa)
    texto = modelo.format(onde=onde, em=f" em «{onde}»" if onde else "",
                          do_comodo="" if not onde else (f" do cômodo «{onde}» (o campo comodo)" if filtra else (e.get("pedido_sem_filtro") or "").format(onde=onde)))
    return "\n".join([
        f"{r['nome'].upper()}{f', cômodo «{onde}»' if onde else ''}, etapa {n} de {total}: {e['titulo']} ({e['nome_app']}).",
        texto,
        FIM.format(pergunta=pergunta(rid, eid, onde)),
    ] + ([e["depois"]] if e.get("depois") else []))


def rotulo(rid, eid, onde, n, total):
    e = etapa_de(rid, eid)
    return f"{onde or RONDAS[rid]['nome']} · {e['grupo']}: {e['titulo']} ({n} de {total})"


# 1.25.1 (o dono, na etapa dos consumíveis: a IA perguntou "são bens (valor em R$) ou consumíveis?" e leu a foto dos cremes como
# móveis e toalha: "alucinações"): numa etapa de consumíveis, tudo o que a pessoa manda é consumível
CONSUMIVEIS = ("Nesta etapa tudo o que eu citar ou mandar em foto é consumível: nunca pergunte se é bem ou consumível e nunca peça valor. "
               "Cadastre com inventario_cadastrar_itens no cômodo «Consumíveis»{usado}, com duracao_dias: a que eu disser; sem ela, a "
               "estimada pela leitura da foto (dizendo que é estimada); sem nenhuma das duas, pergunte só a duração. Antes de cadastrar, "
               "não repita o que já está nos consumíveis.")


# 1.26.0: o mesmo para os outros grupos: o que a etapa é, o que mandar e o que nunca perguntar
REGRAS = {
    "Tarefas": "Nesta etapa tudo é tarefa do ResolvIA{do_onde}: ao criar uma, ligue-a ao cômodo{onde_q} (se a ferramenta tiver esse campo) e não "
               "pergunte prazo, pontos nem repetição que eu não disse; se houver mais de uma lista e eu não disse qual, escolha a que mais "
               "combina e diga qual foi. Para concluir ou mudar uma tarefa, use o id que a leitura das tarefas dá, nunca um id inventado.",
    "Rotinas": "Nesta etapa tudo é rotina da casa ou manutenção do CronologIA{do_onde}: ao criar ou mudar, mande o cômodo{onde_q} (se a "
               "ferramenta tiver esse campo); se eu não disse de quanto em quanto tempo, pergunte só isso. Para mudar ou tirar, use o id que a "
               "leitura dos cadastros dá.",
    "Itens": "Nesta etapa tudo é item da casa{do_onde} (não é consumível nem bem): cadastre no cômodo{onde_q}; sem valor dito, cadastre sem "
             "valor, sem perguntar. Uma foto é lida com o cômodo{onde_q}, sem consumiveis. Para mover ou apagar, use o código ou o id que a busca dá.",
    "Compras": "Nesta etapa tudo vai para a lista de compras do EconomIA: para pôr um produto basta o nome; não pergunte preço, marca nem loja.",
}


def de_consumiveis(e):
    """Uma etapa em que se cadastram ou conferem consumíveis no InventarIA (a de pôr na lista de compras, não)."""
    return bool(e) and e.get("app") == "inventario" and e.get("orig", e.get("id")) in ("cons_acabando", "cons_novo", "consumivel")


def regras(rid, e, onde):
    """O contexto fixo da etapa, para a IA não perguntar o que a etapa já responde."""
    if de_consumiveis(e):
        return " " + CONSUMIVEIS.format(usado=f", com usado_em «{onde}»" if onde else "")
    r = REGRAS.get(e.get("grupo")) if e.get("da", rid) == "casa" and not e.get("livre") else None
    return " " + r.format(do_onde=f" do cômodo «{onde}»" if onde else "", onde_q=f" «{onde}»" if onde else "") if r else ""


def contexto(rid, eid, onde):
    """O que a IA precisa saber quando a pessoa responde no meio de uma etapa."""
    e = etapa_de(rid, eid)
    return (f"(Estou na {RONDAS[rid]['nome']}{f', cômodo «{onde}»' if onde else ''}, etapa {e['titulo']}: a minha próxima mensagem responde a «{e['pergunta'].format(onde=onde)}». "
            f"As mudanças desta etapa são no {e['nome_app']}; responda só a isso, sem fazer outra pergunta; se eu disser que não há nada, diga só para eu tocar em Próxima."
            + regras(rid, e, onde)
            + (" " + e["depois"] if e.get("depois") else "") + ")")


def contexto_anexo(e, tipo):
    """1.23.0: a pessoa mandou um arquivo no meio da ronda: o que a IA precisa saber para não inventar (ela não vê o arquivo)."""
    que = "um PDF" if tipo == "application/pdf" else "uma foto"
    return (f"(A pessoa mandou {que} junto com esta mensagem, no meio da ronda. Você não vê o arquivo. Ele é desta etapa, do "
            f"{e['nome_app']}: use só as ferramentas do {e['nome_app']} que recebem o arquivo. Para saber o que há nele, a de ler o "
            "arquivo; para cadastrar ou guardar, a que cadastra ou guarda, sem pedir o nome do que está nele (o app lê). Não use a "
            "ferramenta de outro app e não descreva o arquivo sem tê-lo lido."
            + (" A foto é de consumíveis: ao ler, mande consumiveis: true (a leitura traz só os consumíveis e diz os que já estão "
               "cadastrados); fale só do que a leitura trouxe." if de_consumiveis(e) and que == "uma foto" else "") + ")")


def sem_anexo(e, tipo):
    """A etapa é de um app que não recebe esse tipo de arquivo: diz isso, sem mandar o arquivo a outro app."""
    que = "um PDF" if tipo == "application/pdf" else "uma foto" if str(tipo or "").startswith("image/") else "esse arquivo"
    return f"Nesta etapa da ronda ({e['nome_app']}) não dá para usar {que}. Escreva o que você quer fazer aqui."


def abrir(rid, eid, onde, paineis):
    """1.22.0 (o dono: "tem como as ações da ronda terem link para os apps?"): o link da etapa, {texto, href}, que abre o app
    dela no Home Assistant, já no lugar: o InventarIA no cômodo (ou nos consumíveis), o ResolvIA no Buscar com as tarefas do
    cômodo, o CronologIA nas Rotinas (ou no Calendário). paineis: {app: /app/<slug>}; sem o endereço do app, None.
    Um app de antes desses endereços só abre, na tela de sempre."""
    e = etapa_de(rid, eid)
    base = (paineis or {}).get(e["app"]) if e else None
    if not base:
        return None
    q, cons = urllib.parse.quote(onde or "", safe=""), e["grupo"] == "Consumíveis" or "consum" in e.get("orig", e["id"])
    if e["app"] == "inventario":
        base += "/consumiveis" if cons else f"/comodo/{q}" if onde else ""
    elif e["app"] == "resolvia":
        # 1.22.3: os dois jeitos de dizer onde abrir: o resto do endereço (o painel do Home Assistant passa por mensagem, também
        # a uma tela que já estava aberta) e o ?aba= (lido quando a tela carrega)
        base += f"/buscar/comodo/{q}?aba=buscar&comodo={q}" if onde else "?aba=prazos"
    elif e["app"] == "cronologia":
        # 1.37.0: pelo que a etapa lê: a agenda no Calendário, o resumo de hoje no Agora, o placar nas Recompensas
        le = e.get("pedido") or ""
        if e.get("orig", e["id"]) == "agenda" or "cronologia_agenda" in le:
            base += "/calendario?aba=calendario"
        elif "cronologia_placar" in le:
            base += "/mais/recompensas"
        elif "cronologia_resumo" not in le:
            base += f"/mais/rotinas/comodo/{q}?aba=rotinas&comodo={q}" if onde else "/mais/rotinas?aba=rotinas"
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


# 1.35.1 (o dono, com o print de «Falta alguma rotina?» sozinha: "pq ele não diz que não encontrou nenhuma? do nada só uma
# pergunta sem contexto"): quando a leitura não deixa texto nenhum, quem escreve a linha de cima é o app, pelo que sabe: o
# TOTAL que a IA deu (0: nada encontrado; N: quantos) ou, sem ele, que a leitura não deu. O nome do que se procura vem do grupo.
VAZIO = {"Tarefas": ("Nenhuma tarefa encontrada.", "tarefa", "tarefas"), "Rotinas": ("Nenhuma rotina encontrada.", "rotina", "rotinas"),
         "Itens": ("Nenhum item encontrado.", "item", "itens"), "Consumíveis": ("Nenhum consumível encontrado.", "consumível", "consumíveis"),
         "Compras": ("A lista está vazia.", "item na lista", "itens na lista"), "Lista": ("A lista está vazia.", "item na lista", "itens na lista"),
         "Agenda": ("Nenhum compromisso encontrado.", "compromisso", "compromissos"),
         "Investimentos": ("Nenhum investimento encontrado.", "investimento", "investimentos"), "Bens": ("Nenhum bem encontrado.", "bem", "bens"),
         "Manutenção": ("Nenhuma manutenção encontrada.", "manutenção", "manutenções"), "Remédios": ("Nenhum remédio encontrado.", "remédio", "remédios"),
         "Novidades": ("Nenhuma novidade encontrada.", "novidade", "novidades"),
         "Séries": ("Nenhuma série em andamento.", "série", "séries"), "Filmes e séries": ("Nada em Quero ver.", "título", "títulos"),
         "Jogos": ("Nenhum jogo em Quero jogar.", "jogo", "jogos"), "Sugestões": ("Nada em alta agora.", "título", "títulos"),
         "Reposição": ("Nada na hora de repor.", "item", "itens"),
         # 1.37.0
         "Benefícios": ("Nenhum benefício encontrado.", "benefício", "benefícios"), "Milhas": ("Nenhum programa de milhas.", "programa", "programas"),
         "Assinaturas": ("Nenhuma assinatura em promoção.", "assinatura", "assinaturas"), "Lançamentos": ("Nada vai sair nos próximos dias.", "lançamento", "lançamentos"),
         "Ligados": ("Nada ligado ou aberto.", "coisa ligada ou aberta", "coisas ligadas ou abertas"),
         "Faturas": ("Nenhuma fatura para conferir.", "fatura", "faturas"), "Contas": ("Nenhuma conta a pagar.", "conta", "contas"),
         # 1.38.0
         "Energia": ("Nada gastando agora.", "aparelho gastando", "aparelhos gastando"), "Luzes": ("Nenhuma luz acesa.", "luz acesa", "luzes acesas"),
         "Clima": ("Nenhum sensor de temperatura.", "cômodo", "cômodos"), "Segurança": ("Tudo fechado e trancado.", "porta ou fechadura", "portas e fechaduras"),
         "Baterias": ("Nenhuma bateria fraca.", "bateria fraca", "baterias fracas"), "Aparelhos": ("Tudo responde.", "aparelho sem resposta", "aparelhos sem resposta"),
         "Limpeza": ("Nenhum aspirador na casa.", "aspirador", "aspiradores"), "Cenas": ("Nenhuma cena na casa.", "cena", "cenas"),
         "Listas": ("Nenhuma lista encontrada.", "lista", "listas"), "Serviços externos": ("Nenhum serviço externo.", "serviço externo", "serviços externos"),
         "Pontos": ("Nenhuma tarefa com pontos.", "tarefa com pontos", "tarefas com pontos"), "Repetição": ("Nenhuma tarefa se repete.", "tarefa que se repete", "tarefas que se repetem"),
         "Horários": ("Nenhum bloco encontrado.", "bloco", "blocos"), "Categorias": ("Nenhuma categoria.", "categoria", "categorias"),
         "Sem categoria": ("Tudo tem categoria.", "sem categoria", "sem categoria"), "Arquivados": ("Nenhum bloco arquivado.", "bloco arquivado", "blocos arquivados"),
         "Coleções": ("Nenhuma coleção para completar.", "coleção", "coleções"), "Concluídos": ("Nada concluído ainda.", "título", "títulos"),
         "Aniversários": ("Nenhum aniversário nos próximos 30 dias.", "aniversário", "aniversários")}


def vazio(rid, eid, achou):
    """A linha que o app escreve numa etapa que leu e cuja resposta veio sem texto: achou None é a leitura que não deu."""
    e = etapa_de(rid, eid)
    if achou is None:
        return f"Não consegui ler o {e['nome_app']} agora."
    zero, um, varios = VAZIO.get(e.get("grupo"), (f"Nada encontrado no {e['nome_app']}.", "resultado", "resultados"))
    return zero if achou == 0 else f"{achou} {um if achou == 1 else varios} no {e['nome_app']}."


def arrumar(texto, rid, eid, onde, perguntar=True, vazio=None):
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
    corpo = re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip() or vazio or ""
    return (corpo + "\n\n" if corpo else "") + f"*{p}*" if perguntar else corpo or "Nada por aqui."
