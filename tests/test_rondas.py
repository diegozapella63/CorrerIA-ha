"""Rondas (1.18.0): o roteiro fixo pelos apps dentro da Conversa da tela. Apps de mentira (ResolvIA, InventarIA, EconomIA)
e a IA simulada; a casa é inventada (Sala, Cozinha)."""
import json
import re
import os
import shutil
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest import mock

from tests.base import importar_servidor, AppFalso
from tests.test_servidor import pedir
S = importar_servidor()
import apps  # noqa: E402
import rondas  # noqa: E402

OBJ = {"type": "object", "properties": {}}
COM_COMODO = {"type": "object", "properties": {"comodo": {"type": "string"}}}


def ferr(nome, entrada=OBJ, grava=False):
    return {"nome": nome, "titulo": nome, "descricao": nome, "entrada": entrada, "grava": grava, "apaga": False}


class AppDaRonda(AppFalso):
    """Um app que responde a cada ferramenta com um texto dele (e o resumo do InventarIA em JSON)."""

    def __init__(self, nome, lista, respostas):
        super().__init__(nome, ferramentas=lista)

        def rota(h, c):
            if h.command == "GET":
                return 200, {"instrucoes": "", "ferramentas": lista}
            self.feitos.append(c)
            r = respostas.get(c["nome"])
            return (200, {"texto": r if isinstance(r, str) else json.dumps(r)}) if r is not None else (404, {"erro": "?"})
        self.rotas["/api/integracao/ferramentas"] = rota


class Base(unittest.TestCase):
    CAB = {"X-Remote-User-Id": "u-ana", "X-Remote-User-Display-Name": "Ana Exemplo"}

    def setUp(self):
        for arq in (S.CONFIG_ARQ, S.CONVERSAS_ARQ):
            if os.path.exists(arq):
                os.remove(arq)
        shutil.rmtree(S.SHARE_DIR, ignore_errors=True)
        os.makedirs(S.SHARE_DIR)
        S.RONDAS_ATIVAS.clear()
        for arq in (S.RONDAS_ARQ,):
            if os.path.exists(arq):
                os.remove(arq)
        S.ESTADO["rondas_atrasadas"] = None
        self.addCleanup(S.RONDAS_ATIVAS.clear)
        self.addCleanup(lambda: os.path.exists(S.RONDAS_ARQ) and os.remove(S.RONDAS_ARQ))
        self.addCleanup(S._gravar_tela, "u-ana", [])
        p = mock.patch.object(S, "APPS", apps.Apps(S.SHARE_DIR, S.log, cache=0))
        p.start()
        self.addCleanup(p.stop)
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), S.Tela)
        self.srv.daemon_threads = True
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.addCleanup(self.srv.server_close)
        self.addCleanup(self.srv.shutdown)
        self.url = f"http://127.0.0.1:{self.srv.server_address[1]}"

    def ligar(self, app, nome, lista, respostas):
        a = AppDaRonda(nome, lista, respostas)
        self.addCleanup(a.fechar)
        a.publicar(S.SHARE_DIR, app)
        return a

    def casa(self, consumiveis=True, comodo_no_resolvia=True):
        self.resolvia = self.ligar("resolvia", "ResolvIA", [ferr("tarefas", COM_COMODO if comodo_no_resolvia else OBJ), ferr("criar_tarefa", grava=True)],
                                   {"tarefas": "2 tarefas: Trocar a lâmpada (hoje); Regar a planta."})
        self.inventario = self.ligar("inventario", "InventarIA", [ferr("resumo"), ferr("buscar_itens", COM_COMODO)],
                                     {"resumo": {"comodos": [{"nome": "Sala"}, {"nome": "Cozinha"}], "opcoes": {"consumiveis": consumiveis}},
                                      "buscar_itens": "3 itens: Sofá, Mesa, Abajur."})
        self.economia = self.ligar("economia", "EconomIA", [ferr("lista"), ferr("reposicao")], {"lista": "Na lista: Café, Ração.", "reposicao": "Nada a repor."})

    def j(self, caminho, corpo=None):
        st, r = pedir(self.url + caminho, "POST" if corpo is not None else "GET", corpo, self.CAB)
        return st, json.loads(r)


def com_painel(app, painel):
    """Põe o endereço do app no Home Assistant (/app/<slug>) no correria.json dele, como faz o nome da máquina no url."""
    arq = os.path.join(S.SHARE_DIR, app, "correria.json")
    with open(arq, encoding="utf-8") as f:
        d = json.load(f)
    d["painel"] = painel
    with open(arq, "w", encoding="utf-8") as f:
        json.dump(d, f)


class TestEditor(Base):
    """1.30.0 (o dono: "a possibilidade de criar novas rondas e de alterar rondas existentes"; "no modo simples por padrão e com
    uma opção para ativar o modo avançado"): as rondas da pessoa ficam por cima das daqui."""

    def setUp(self):
        super().setUp()
        if os.path.exists(S.MINHAS_ARQ):
            os.remove(S.MINHAS_ARQ)
        S.montar_rondas()
        self.addCleanup(lambda: (os.path.exists(S.MINHAS_ARQ) and os.remove(S.MINHAS_ARQ), S.montar_rondas()))

    def test_quando_perguntar(self):
        """1.32.0 (o dono: "para eu escrever algo como: não perguntar sobre pet shop no cômodo do quarto"): a frase é da pessoa,
        mas quem decide é o app, pelos nomes dos cômodos que estão nela."""
        C = ["Sala", "Quarto", "Quarto de hóspedes", "Banheiro", "Cozinha"]
        for frase, regra in (("não perguntar sobre pet shop no cômodo do quarto", {"fora": ["Quarto"]}),
                             ("Só no banheiro e na cozinha", {"so": ["Banheiro", "Cozinha"]}),
                             ("nunca no quarto de hospedes", {"fora": ["Quarto de hóspedes"]}),
                             ("menos na SALA e no Quarto de Hóspedes", {"fora": ["Sala", "Quarto de hóspedes"]}),
                             ("sempre", {}), ("na salada", {}), ("", {})):
            self.assertEqual(rondas.quando_regra(frase, C), regra, frase)
        self.assertTrue(rondas.vale_em({"fora": ["Quarto"]}, "Quarto de hóspedes"))
        self.assertFalse(rondas.vale_em({"fora": ["Quarto"]}, "quarto"))
        self.assertEqual([rondas.vale_em({"so": ["Banheiro"]}, c) for c in ("Banheiro", "Sala", "")], [True, False, True])
        self.casa()
        nova = {"id": "casa", "nome": "Ronda da casa", "onde": True,
                "etapas": [{"de": "casa.feita"}, {"de": "casa.pet", "quando": "Não perguntar na Cozinha"}, {"de": "casa.mercado", "quando": "só na cozinha"}]}
        st, ed = self.j("/api/rondas/editor", {"acao": "salvar", "ronda": nova})
        self.assertEqual((st, ed["comodos"], ed["max"]["quando"]), (200, ["Sala", "Cozinha"], 160))
        self.assertEqual([e["quando"] for e in ed["rondas"][0]["etapas"]], ["", "Não perguntar na Cozinha", "só na cozinha"])
        guardada = json.load(open(S.MINHAS_ARQ, encoding="utf-8"))["rondas"]["casa"]["etapas"]
        self.assertEqual([(e.get("fora"), e.get("so")) for e in guardada], [(None, None), (["Cozinha"], None), (None, ["Cozinha"])])
        self.assertEqual(self.j("/api/ronda", {"acao": "iniciar", "ronda": "casa", "onde": "Sala"})[0], 200)
        self.assertEqual(S.RONDAS_ATIVAS["u-ana"]["etapas"], ["feita", "pet"], "na Sala: sem o mercado")
        self.j("/api/ronda", {"acao": "sair"})
        self.j("/api/ronda", {"acao": "iniciar", "ronda": "casa", "onde": "Cozinha"})
        self.assertEqual(S.RONDAS_ATIVAS["u-ana"]["etapas"], ["feita", "mercado"], "na Cozinha: sem o pet shop")
        self.j("/api/ronda", {"acao": "sair"})
        # uma frase sem cômodo nenhum não é guardada: o erro diz o que escrever; numa ronda sem cômodo, o campo não vale
        st, r = self.j("/api/rondas/editor", {"acao": "salvar", "ronda": dict(nova, etapas=[{"de": "casa.pet", "quando": "de vez em quando"}])})
        self.assertEqual((st, "escreva o nome de um cômodo" in r["erro"]), (400, True))
        st, ed = self.j("/api/rondas/editor", {"acao": "salvar", "ronda": {"nome": "Sem cômodo", "onde": False, "etapas": [{"de": "casa.pet", "quando": "não na Sala"}]}})
        self.assertEqual((st, ed["rondas"][-1]["etapas"][0]["quando"]), (200, ""))
        # só uma etapa, que não vale no cômodo: a ronda não começa ali
        self.j("/api/rondas/editor", {"acao": "salvar", "ronda": dict(nova, etapas=[{"de": "casa.pet", "quando": "não na Sala"}])})
        st, r = self.j("/api/ronda", {"acao": "iniciar", "ronda": "casa", "onde": "Sala"})
        self.assertEqual((st, r["erro"]), (400, "Nenhuma pergunta desta ronda vale neste cômodo."))

    def test_mais_etapas_prontas(self):
        """1.32.0 (o dono: "mais opções disponíveis com base nos principais temas. Exemplo: investimentos, bens"): etapas
        prontas que não estão em nenhuma ronda daqui entram no catálogo, com as mesmas regras (uma pergunta só)."""
        self.casa()
        self.gerencia = self.ligar("gerencia", "GerencIA", [ferr("investimentos"), ferr("resumo")], {"investimentos": "2 investimentos: CDB 1.000; Tesouro 2.000."})
        cat = {c["de"]: c for c in self.j("/api/rondas/editor")[1]["catalogo"]}
        self.assertEqual((cat["mais.invest"]["grupo"], cat["mais.invest"]["nome_app"], cat["mais.invest"]["ligada"], cat["mais.bens"]["ligada"], cat["mais.cupons"]["ligada"]),
                         ("Investimentos", "GerencIA", True, True, False))
        self.assertNotIn("mais", [r["id"] for r in self.j("/api/rondas/editor")[1]["rondas"]], "não é uma ronda: só etapas para escolher")
        for e in rondas.MAIS["mais"]["etapas"]:
            p = e["pergunta"]
            self.assertEqual((p.count("?"), p.endswith("?")), (1, True), p)
            self.assertNotRegex(p, r" ou |,|…", p)
        ids = [c["de"] for c in rondas.catalogo()]
        self.assertEqual(len(ids), len(set(ids)))
        # 1.33.0: toda etapa pronta usa uma ferramenta que o app tem de verdade (os nomes conferidos nos repositórios dos apps)
        tem = {"gerencia": "resumo lancamentos contas_a_pagar investimentos cadastros lancar novo_investimento novo_fixo ajustar_saldo marcar_pago"
                           " faturas_do_email beneficios oportunidades",
               "inventario": "resumo buscar_itens novidades cadastrar_itens avaliar", "economia": "lista reposicao ofertas roteiro cupons comprei por_na_lista tirar_da_lista",
               "resolvia": "resumo tarefas repeticoes comece_por_aqui", "cronologia": "resumo agenda cadastros placar criar_compromisso pular ferias", "memoria": "resumo buscar",
               "odisseia": "resumo buscar marcar lista_pronta proximo_episodio", "casa": "estado comando"}
        tem["economia"] += " reposto preco"
        for c in rondas.catalogo():
            for f in (c["precisa"], *c["tambem"]):
                app, _, nome = f.partition("_")
                self.assertIn(nome, tem[app].split(), c["de"])
        self.assertEqual((cat["mais.novidades"]["nome_app"], cat["mais.manut"]["grupo"], len([c for c in rondas.catalogo() if c["de"].startswith("mais.")])), ("InventarIA", "Manutenção", 53))
        for e in rondas.MAIS["mais"]["etapas"]:  # o que a IA lê também é de uma ferramenta que o app tem
            for f in re.findall(r"Use ([a-z]+)_([a-z_]+)", e["pedido"] or ""):
                self.assertIn(f[1], tem[f[0]].split(), e["id"])
        # as Novidades só com elas ligadas no InventarIA (opcoes.novidades no resumo, InventarIA 1.98.0)
        self.assertEqual(rondas.opcoes({"opcoes": {"novidades": True, "bens": False}}), {"novidades"})
        self.assertIn("Use inventario_novidades e conte", rondas.MAIS["mais"]["etapas"][16]["pedido"].format(do_comodo=""))
        st, ed = self.j("/api/rondas/editor", {"acao": "salvar", "ronda": {"nome": "Patrimônio", "onde": False, "etapas": [{"de": "mais.invest"}, {"de": "mais.bens"}]}})
        rid = ed["rondas"][-1]["id"]
        self.assertEqual((st, [e["de"] for e in ed["rondas"][-1]["etapas"]]), (200, ["mais.invest", "mais.bens"]))
        # os bens só com Usar bens ligado no InventarIA (a casa de teste não diz que estão)
        self.assertEqual([e["id"] for x in self.j("/api/rondas")[1]["rondas"] if x["id"] == rid for e in x["etapas"]], ["invest"])
        p = rondas.pedido(rid, "invest", "", S.FERR.todas(), 1, 1)
        self.assertIn("Use gerencia_investimentos e conte os investimentos", p)
        self.assertNotIn("cômodo «»", rondas.pedido(rid, "invest", "", S.FERR.todas(), 1, 1))

    def test_rondas_do_patrimonio_e_da_semana(self):
        """1.34.0: duas rondas daqui, sem cômodo, montadas com as etapas do MAIS (no catálogo cada etapa aparece uma vez só)."""
        self.casa()
        self.gerencia = self.ligar("gerencia", "GerencIA", [ferr("investimentos"), ferr("contas_a_pagar"), ferr("novo_investimento", grava=True)],
                                   {"investimentos": "TOTAL: 2\n- CDB: 1.000\n- Tesouro: 2.000", "contas_a_pagar": "TOTAL: 0"})
        L = {x["id"]: x for x in self.j("/api/rondas")[1]["rondas"]}
        self.assertEqual((L["patrimonio"]["nome"], L["patrimonio"]["sem_onde"], [e["id"] for e in L["patrimonio"]["etapas"]]),
                         ("Ronda do patrimônio", True, ["invest", "invest_vence", "invest_novo", "valiosos", "sem_valor", "sem_foto"]), "sem os bens e as novidades, desligados na casa de teste")
        self.assertEqual((L["semana"]["nome"], [e["id"] for e in L["semana"]["etapas"]]), ("Ronda da semana", ["hoje", "atrasadas"]), "só as etapas dos apps ligados (aqui, o ResolvIA e o GerencIA)")
        self.assertEqual([e["id"] for e in rondas.PADRAO["semana"]["etapas"]], ["hoje", "comece", "semana", "agenda_semana", "manut", "remedios", "atrasadas", "placar"])
        ed = self.j("/api/rondas/editor")[1]
        pat = next(r for r in ed["rondas"] if r["id"] == "patrimonio")
        self.assertEqual((pat["minha"], pat["mudada"], [e["de"] for e in pat["etapas"]][:2]), (False, False, ["mais.invest", "mais.invest_vence"]))
        ids = [c["de"] for c in ed["catalogo"]]
        self.assertEqual((len(ids), [i for i in ids if i.startswith(("patrimonio.", "semana."))]), (len(set(ids)), []))
        st, r = self.j("/api/ronda", {"acao": "iniciar", "ronda": "patrimonio"})
        self.assertEqual((st, r["ronda"]["ativa"]["id"], "CDB" in r["mensagens"][-1]["texto"], "Algum investimento mudou de valor?" in r["mensagens"][-1]["texto"]), (200, "patrimonio", True, True))
        self.j("/api/ronda", {"acao": "sair"})
        # mudar uma delas e voltar ao original, como as outras daqui
        st, ed = self.j("/api/rondas/editor", {"acao": "salvar", "ronda": {"id": "semana", "nome": "Minha semana", "onde": False, "etapas": [{"de": "mais.hoje"}]}})
        sem = next(r for r in ed["rondas"] if r["id"] == "semana")
        self.assertEqual((st, sem["nome"], sem["mudada"]), (200, "Minha semana", True))
        ed = self.j("/api/rondas/editor", {"acao": "restaurar", "id": "semana"})[1]
        self.assertEqual(len(next(r for r in ed["rondas"] if r["id"] == "semana")["etapas"]), 8)

    def test_ronda_do_lazer(self):
        """1.36.0 (o dono: "veja mais quais etapas e ferramentas podem ficar nas rondas como templates"): a Ronda do lazer, com
        as etapas do OdisseIA (sem cômodo); sem o OdisseIA ligado, ela não aparece."""
        self.casa()
        self.assertNotIn("lazer", [x["id"] for x in self.j("/api/rondas")[1]["rondas"]], "sem o OdisseIA, sem a ronda")
        self.odisseia = self.ligar("odisseia", "OdisseIA", [ferr("resumo"), ferr("buscar"), ferr("lista_pronta"), ferr("marcar", grava=True), ferr("proximo_episodio", grava=True)],
                                   {"resumo": "TOTAL: 1\n- Mar de Estrelas: parou em T1 E3, faltam 2", "buscar": "TOTAL: 0", "lista_pronta": "TOTAL: 2\n- Farol Distante · filme\n- Casa no Morro · série"})
        L = {x["id"]: x for x in self.j("/api/rondas")[1]["rondas"]}
        self.assertEqual((L["lazer"]["nome"], L["lazer"]["sem_onde"], [e["id"] for e in L["lazer"]["etapas"]]),
                         ("Ronda do lazer", True, ["continuar", "quero_ver", "quero_jogar", "em_alta", "estreias"]), "o Vão sair pede o Criar compromisso do CronologIA")
        st, r = self.j("/api/ronda", {"acao": "iniciar", "ronda": "lazer"})
        self.assertEqual((st, "Mar de Estrelas" in r["mensagens"][-1]["texto"], "Viu algum episódio novo?" in r["mensagens"][-1]["texto"]), (200, True, True))
        self.j("/api/ronda", {"acao": "sair"})
        self.assertEqual(rondas.vazio("lazer", "quero_jogar", 0), "Nenhum jogo em Quero jogar.")
        self.assertEqual(rondas.vazio("lazer", "em_alta", 2), "2 títulos no OdisseIA.")

    def test_rondas_e_etapas_de_1_37(self):
        """1.37.0 (o dono: "as etapas e a ronda devem ficar completíssimas para o modo manual"): cinco rondas novas, mais
        etapas nas de sempre, a etapa que lê um app e muda outro (as duas ferramentas precisam existir) e o link pelo que a
        etapa lê."""
        P = {r: [e["id"] for e in rondas.PADRAO[r]["etapas"]] for r in ("dia", "noite", "financas", "anotacoes", "viagem", "compras", "chegada")}
        self.assertEqual(P["dia"], ["agenda_hoje", "remedio_hoje", "hoje", "comece", "pular"])
        self.assertEqual(P["noite"], ["ligado", "remedio_hoje", "agenda_hoje", "amanha"])
        self.assertEqual(P["financas"][:2], ["faturas_email", "atrasadas"])
        self.assertEqual(P["anotacoes"], ["blocos", "folhas", "parados"])
        self.assertEqual(P["viagem"], ["ferias", "contas_viagem", "remedios_levar", "lista_viagem", "ligado"])
        self.assertEqual((P["compras"][:2], "cupons" in P["compras"], "reposto" in P["chegada"]), (["lista", "limpar"], True, True))
        self.assertEqual([e["id"] for e in rondas.PADRAO["mes"]["etapas"]][:6], ["gastos", "contas", "recebidos", "fixos", "saldo", "faturas_email"])
        for r in rondas.PADRAO.values():  # a etapa do MAIS numa ronda daqui vem com o de do MAIS, como nas rondas feitas só delas
            for e in r["etapas"]:
                if e.get("de"):
                    self.assertTrue(e["de"].startswith("mais."), e["de"])
        self.assertEqual(rondas.precisa_todas(rondas.etapa_de("lazer", "lancamentos")), ("cronologia_criar_compromisso", "odisseia_resumo"))
        self.casa()
        self.ligar("odisseia", "OdisseIA", [ferr("resumo"), ferr("lista_pronta")], {"resumo": "TOTAL: 0", "lista_pronta": "TOTAL: 0"})
        L = {x["id"]: x for x in self.j("/api/rondas")[1]["rondas"]}
        self.assertNotIn("lancamentos", [e["id"] for e in L["lazer"]["etapas"]], "lê o OdisseIA, mas o lembrete é do CronologIA")
        cat = {c["de"]: c for c in self.j("/api/rondas/editor")[1]["catalogo"]}
        self.assertEqual((cat["mais.lancamentos"]["ligada"], cat["mais.estreias"]["ligada"], cat["mais.lancamentos"]["tambem"]), (False, True, ["odisseia_resumo"]))
        self.ligar("cronologia", "CronologIA", [ferr("criar_compromisso", grava=True), ferr("agenda"), ferr("resumo")], {"agenda": "TOTAL: 0", "resumo": "TOTAL: 0"})
        L = {x["id"]: x for x in self.j("/api/rondas")[1]["rondas"]}
        self.assertIn("lancamentos", [e["id"] for e in L["lazer"]["etapas"]])
        self.assertEqual([e["id"] for e in L["dia"]["etapas"]], ["agenda_hoje", "remedio_hoje", "hoje"])
        ed = self.j("/api/rondas/editor")[1]
        laz = next(r for r in ed["rondas"] if r["id"] == "lazer")
        self.assertTrue(next(e for e in laz["etapas"] if e["de"] == "mais.lancamentos")["ligada"])
        # o link: a agenda no Calendário, o de hoje no Agora, o placar nas Recompensas
        pn = {"cronologia": "/app/x_cronologia"}
        self.assertEqual((rondas.abrir("dia", "agenda_hoje", "", pn)["href"], rondas.abrir("dia", "remedio_hoje", "", pn)["href"],
                          rondas.abrir("semana", "placar", "", pn)["href"], rondas.abrir("semana", "remedios", "", pn)["href"]),
                         ("/app/x_cronologia/calendario?aba=calendario", "/app/x_cronologia", "/app/x_cronologia/mais/recompensas", "/app/x_cronologia/mais/rotinas?aba=rotinas"))
        # o que está ligado: a casa toda à noite, o cômodo na Ronda da casa (quando o casa_estado aceita o cômodo)
        T = [{"id": "casa_estado", "entrada": {"type": "object", "properties": {"busca": {}, "ligados": {}, "comodo": {}}}}]
        self.assertIn("Use casa_estado com ligados true e conte", rondas.pedido("noite", "ligado", "", T, 1, 4))
        self.assertIn("ligados true do cômodo «Sala» (o campo comodo)", rondas.pedido("casa", "ligado", "Sala", T, 1, 4))
        self.assertEqual((rondas.vazio("noite", "ligado", 0), rondas.vazio("financas", "faturas_email", 2)), ("Nada ligado ou aberto.", "2 faturas no GerencIA."))

    def test_modo_simples_mudar_criar_voltar_e_apagar(self):
        self.casa()
        st, ed = self.j("/api/rondas/editor")
        self.assertEqual((st, ed["avancado"], ed["leituras"]), (200, False, []))
        self.assertEqual([r["id"] for r in ed["rondas"]], ["casa", "compras", "chegada", "mes", "patrimonio", "semana", "lazer", "dia", "noite", "financas", "anotacoes", "viagem"])
        casa = ed["rondas"][0]
        self.assertEqual((casa["minha"], casa["mudada"], casa["onde"], casa["etapas"][0]["de"], casa["etapas"][0]["ligada"]), (False, False, True, "casa.feita", True))
        cat = {c["de"]: c for c in ed["catalogo"]}
        self.assertEqual((cat["casa.item_novo"]["nome_app"], cat["casa.item_novo"]["ligada"], cat["mes"+".contas"]["ligada"]), ("InventarIA", True, False))
        # mudar a Ronda da casa: duas etapas, outra ordem, a pergunta de uma com as palavras da pessoa
        nova = {"id": "casa", "nome": "Ronda da minha casa", "onde": True,
                "etapas": [{"de": "casa.item_novo", "pergunta": "Tem coisa nova aqui em {onde}?"}, {"de": "casa.feita"}]}
        st, ed = self.j("/api/rondas/editor", {"acao": "salvar", "ronda": nova})
        casa = ed["rondas"][0]
        self.assertEqual((st, casa["nome"], casa["mudada"], [e["id"] for e in casa["etapas"]]), (200, "Ronda da minha casa", True, ["item_novo", "feita"]))
        self.assertEqual(rondas.pergunta("casa", "item_novo", "Sala"), "Tem coisa nova aqui em Sala?")
        self.assertEqual(rondas.pergunta("casa", "feita", "Sala"), "Alguma dessas tarefas já foi feita?", "sem pergunta nova, a da etapa pronta")
        self.assertIn("tudo é item da casa do cômodo «Sala»", rondas.contexto("casa", "item_novo", "Sala"), "as regras da etapa pronta continuam")
        st, r = self.j("/api/rondas")
        self.assertEqual([(x["nome"], len(x["etapas"])) for x in r["rondas"] if x["id"] == "casa"], [("Ronda da minha casa", 2)])
        st, r = self.j("/api/ronda", {"acao": "iniciar", "ronda": "casa", "onde": "Sala"})
        self.assertEqual((st, r["ronda"]["ativa"]["total"]), (200, 2))
        self.assertIn("Tem coisa nova aqui em Sala?", r["mensagens"][-1]["texto"])
        # uma ronda nova, sem cômodo; a mesma etapa duas vezes ganha outro id; salvar acaba a ronda em andamento
        st, ed = self.j("/api/rondas/editor", {"acao": "salvar", "ronda": {"nome": "  Garagem  ", "etapas": [{"de": "casa.item_novo"}, {"de": "casa.item_novo", "pergunta": "E na prateleira de {cima}?"}]}})
        minha = ed["rondas"][-1]
        self.assertEqual((st, minha["nome"], minha["minha"], minha["onde"], [e["id"] for e in minha["etapas"]]), (200, "Garagem", True, False, ["item_novo", "item_novo_2"]))
        self.assertRegex(minha["id"], r"^m[0-9a-f]{6}$")
        self.assertEqual(minha["etapas"][1]["pergunta"], "E na prateleira de {cima}?", "as chaves da pessoa não são campos")
        self.assertEqual(rondas.pergunta(minha["id"], "item_novo_2", ""), "E na prateleira de {cima}?")
        self.assertEqual(S.RONDAS_ATIVAS, {})
        self.assertEqual(oct(os.stat(S.MINHAS_ARQ).st_mode & 0o777), "0o600")
        # o que não vale
        for ronda, erro in (({"nome": "A", "etapas": [{"de": "casa.feita"}]}, "Dê um nome à ronda."),
                            ({"nome": "Vazia", "etapas": []}, "A ronda precisa de pelo menos uma etapa."),
                            ({"nome": "Muitas", "etapas": [{"de": "casa.feita"}] * 31}, "Uma ronda tem até 30 etapas."),
                            ({"nome": "Duas", "etapas": [{"de": "casa.feita", "pergunta": "Fez? E guardou?"}]}, "Cada etapa é uma pergunta só, terminando com «?»."),
                            ({"nome": "Sem", "etapas": [{"de": "casa.feita", "pergunta": "Conte as tarefas."}]}, "Cada etapa é uma pergunta só, terminando com «?»."),
                            ({"nome": "Curta", "etapas": [{"de": "casa.feita", "pergunta": "Ok?"}]}, "Escreva a pergunta de cada etapa."),
                            ({"nome": "Longa", "etapas": [{"de": "casa.feita", "pergunta": "a" * 160 + "?"}]}, "A pergunta fica com até 160 letras."),
                            ({"nome": "Some", "etapas": [{"de": "casa.nao_existe"}]}, "Essa etapa não existe mais. Tire-a da ronda."),
                            ({"nome": "Torta", "etapas": ["x"]}, "Etapa inválida."),
                            ({"nome": "Livre", "etapas": [{"ferramenta": "inventario_resumo", "titulo": "Resumo", "pergunta": "Tudo certo?"}]}, "Uma etapa livre só no modo avançado."),
                            ({"id": "sumiu", "nome": "Outra", "etapas": [{"de": "casa.feita"}]}, "Essa ronda não existe mais.")):
            self.assertEqual(self.j("/api/rondas/editor", {"acao": "salvar", "ronda": ronda}), (400, {"erro": erro}), ronda["nome"])
        # voltar ao original e apagar: cada um só na sua
        self.assertEqual(self.j("/api/rondas/editor", {"acao": "apagar", "id": "casa"})[0], 400)
        self.assertEqual(self.j("/api/rondas/editor", {"acao": "restaurar", "id": minha["id"]})[0], 400)
        self.assertEqual(self.j("/api/rondas/editor", {"acao": "outra"}), (400, {"erro": "Pedido inválido."}))
        st, ed = self.j("/api/rondas/editor", {"acao": "restaurar", "id": "casa"})
        self.assertEqual((ed["rondas"][0]["nome"], ed["rondas"][0]["mudada"], len(ed["rondas"][0]["etapas"]) > 5), ("Ronda da casa", False, True))
        st, ed = self.j("/api/rondas/editor", {"acao": "apagar", "id": minha["id"]})
        self.assertEqual([r["id"] for r in ed["rondas"]], ["casa", "compras", "chegada", "mes", "patrimonio", "semana", "lazer", "dia", "noite", "financas", "anotacoes", "viagem"])
        with mock.patch.object(rondas, "MAX_RONDAS", 0):
            self.assertEqual(self.j("/api/rondas/editor", {"acao": "salvar", "ronda": {"nome": "Mais uma", "etapas": [{"de": "casa.feita"}]}})[1]["erro"], "Já são 0 rondas suas. Apague alguma.")

    def test_modo_avancado_o_que_a_ia_le_e_a_etapa_livre(self):
        self.casa()
        st, ed = self.j("/api/rondas/editor", {"acao": "avancado", "liga": True})
        self.assertEqual((st, ed["avancado"]), (200, True))
        lidas = {f["id"]: f for f in ed["leituras"]}
        self.assertEqual((lidas["inventario_resumo"]["nome_app"], "resolvia_criar_tarefa" in lidas), ("InventarIA", False), "só as leituras")
        ronda = {"nome": "Oficina", "onde": True, "etapas": [
            {"de": "casa.item_novo", "pedido": "Conte só as ferramentas {elétricas}."},
            {"ferramenta": "economia_lista", "titulo": "A lista", "pergunta": "Falta comprar alguma coisa para {onde}?", "pedido": "Diga só os 3 primeiros."}]}
        st, ed = self.j("/api/rondas/editor", {"acao": "salvar", "ronda": ronda})
        minha = ed["rondas"][-1]
        rid = minha["id"]
        self.assertEqual([(e["id"], e.get("de"), e.get("ferramenta"), e["pedido"], e["app"]) for e in minha["etapas"]],
                         [("item_novo", "casa.item_novo", None, "Conte só as ferramentas {elétricas}.", "InventarIA"), ("livre", None, "economia_lista", "Diga só os 3 primeiros.", "EconomIA")])
        todas = S.FERR.todas()
        p = rondas.pedido(rid, "item_novo", "Sala", todas, 1, 2)
        self.assertIn("Use inventario_buscar_itens do cômodo «Sala» (o campo comodo). Conte só as ferramentas {elétricas}.", p)
        p = rondas.pedido(rid, "livre", "Sala", todas, 2, 2)
        self.assertIn("Use economia_lista e conte o que há. Diga só os 3 primeiros.", p)
        self.assertIn("o app escreve a pergunta «Falta comprar alguma coisa para Sala?»", p)
        self.assertNotIn("nunca peça valor", rondas.contexto(rid, "livre", "Sala"), "uma etapa livre não tem as regras de uma pronta")
        # erros do modo avançado
        for etapa, erro in (({"ferramenta": "nao_existe", "titulo": "X", "pergunta": "Tudo certo?"}, "Escolha o que a IA lê na etapa livre (o app precisa estar ligado)."),
                            ({"ferramenta": "economia_lista", "titulo": " ", "pergunta": "Tudo certo?"}, None),
                            ({"de": "casa.feita", "pedido": "a" * 601}, "O que a IA lê fica com até 600 letras.")):
            st, r = self.j("/api/rondas/editor", {"acao": "salvar", "ronda": {"nome": "Erro", "etapas": [etapa]}})
            self.assertEqual((st, r.get("erro")) if erro else (st, None), (400, erro) if erro else (200, None), etapa)
        # desligado o modo avançado: o que foi escrito continua valendo, e salvar no modo simples não apaga
        st, ed = self.j("/api/rondas/editor", {"acao": "avancado", "liga": False})
        self.assertEqual(ed["leituras"], [])
        etapas = [dict(e, pergunta="Chegou coisa nova?", pedido="") if e["id"] == "item_novo" else e for e in minha["etapas"]]
        st, ed = self.j("/api/rondas/editor", {"acao": "salvar", "ronda": {"id": rid, "nome": "Oficina", "onde": True, "etapas": etapas}})
        de_novo = next(r for r in ed["rondas"] if r["id"] == rid)
        self.assertEqual([(e["pergunta"], e["pedido"]) for e in de_novo["etapas"]],
                         [("Chegou coisa nova?", "Conte só as ferramentas {elétricas}."), ("Falta comprar alguma coisa para {onde}?", "Diga só os 3 primeiros.")])
        # um app desligado: a etapa fica marcada e fora da ronda de agora
        shutil.rmtree(os.path.join(S.SHARE_DIR, "economia"))
        st, ed = self.j("/api/rondas/editor")
        self.assertEqual([e["ligada"] for e in next(r for r in ed["rondas"] if r["id"] == rid)["etapas"]], [True, False])
        self.assertEqual([len(x["etapas"]) for x in self.j("/api/rondas")[1]["rondas"] if x["id"] == rid], [1])
        # o arquivo estragado ou com uma etapa que sumiu não derruba nada
        rondas.montar({"rondas": {"casa": "x", "Ruim!": {}, "mzz": {"nome": "Sumiu", "etapas": [{"de": "casa.nao_existe"}, "x"]}}})
        self.assertEqual(list(rondas.RONDAS), ["casa", "compras", "chegada", "mes", "patrimonio", "semana", "lazer", "dia", "noite", "financas", "anotacoes", "viagem"])


class TestLinksEMais(Base):
    """1.22.0: cada etapa leva o link do app dela, já no lugar; a lista menor que o total termina em «e mais N»."""

    def test_o_endereco_do_app_pelo_nome_da_maquina(self):
        self.assertEqual(apps.painel_de({"url": "http://a1b2c3d4-inventario:8099"}), "/app/a1b2c3d4_inventario")
        self.assertEqual(apps.painel_de({"url": "http://a1b2c3d4-ofertas-do-bairro:8099/"}), "/app/a1b2c3d4_ofertas_do_bairro")
        self.assertEqual(apps.painel_de({"url": "http://127.0.0.1:8191", "painel": "/app/x1_gerencia"}), "/app/x1_gerencia", "o que o app disser vale")
        for fora in ({"url": "http://127.0.0.1:8191"}, {"url": "http://localhost:8099"}, {}):
            self.assertIsNone(apps.painel_de(fora))
        self.assertEqual(apps.painel_de({"url": "http://a-b:1", "painel": "https://outro.site/app/x"}), "/app/a_b", "um painel que não é /app/… não vale")

    def test_o_link_de_cada_etapa(self):
        P = {"inventario": "/app/x_inventario", "resolvia": "/app/x_resolvia", "cronologia": "/app/x_cronologia", "economia": "/app/x_economia"}
        ab = lambda rid, eid, onde: rondas.abrir(rid, eid, onde, P)
        self.assertEqual(ab("casa", "item_novo", "Sala de estar"), {"texto": "Abrir no InventarIA", "href": "/app/x_inventario/comodo/Sala%20de%20estar"})
        self.assertEqual(ab("casa", "cons_novo", "Sala")["href"], "/app/x_inventario/consumiveis")
        self.assertEqual(ab("casa", "feita", "Área de serviço"), {"texto": "Abrir no ResolvIA", "href": "/app/x_resolvia/buscar/comodo/%C3%81rea%20de%20servi%C3%A7o?aba=buscar&comodo=%C3%81rea%20de%20servi%C3%A7o"})
        self.assertEqual(ab("casa", "rotina_nova", "Sala")["href"], "/app/x_cronologia/mais/rotinas/comodo/Sala?aba=rotinas&comodo=Sala")
        self.assertEqual(ab("mes", "rotinas", "")["href"], "/app/x_cronologia/mais/rotinas?aba=rotinas")
        self.assertEqual(ab("casa", "mercado", "Sala")["href"], "/app/x_economia")
        self.assertEqual(ab("mes", "tarefas", "")["href"], "/app/x_resolvia?aba=prazos")
        self.assertEqual(ab("mes", "agenda", "")["href"], "/app/x_cronologia/calendario?aba=calendario")
        self.assertEqual(ab("mes", "itens", "")["href"], "/app/x_inventario")
        self.assertIsNone(ab("mes", "gastos", ""), "sem o endereço do app, sem link")
        self.assertIsNone(rondas.abrir("casa", "item_novo", "Sala", {}))

    def test_e_mais_no_fim_da_lista(self):
        t = "Você tem 10 itens.\n\n- Tapete\n- Quadro\n- Mesa\n\n*Chegou algum item novo?*"
        self.assertEqual(rondas.e_mais(t, 10), "Você tem 10 itens.\n\n- Tapete\n- Quadro\n- Mesa\n- e mais 7\n\n*Chegou algum item novo?*")
        for igual, n in ((t, 3), (t, 2), (t, None), (t, 0), ("Nada aqui.\n\n*Falta algo?*", 4), (t.replace("- Mesa", "- e mais 8"), 10)):
            self.assertEqual(rondas.e_mais(igual, n), igual)

    def test_a_etapa_leva_o_link_e_o_e_mais(self):
        self.casa()
        com_painel("resolvia", "/app/x_resolvia")
        with mock.patch.object(S, "responder_ia", return_value=("TOTAL: 5\nVocê tem 5 tarefas.\n- Trocar a lâmpada\n- Regar a planta", ["ResolvIA"], False)):
            st, r = self.j("/api/ronda", {"acao": "iniciar", "ronda": "casa", "onde": "Sala"})
        self.assertEqual(st, 200)
        m = r["mensagens"][-1]
        self.assertEqual(m["abrir"], {"texto": "Abrir no ResolvIA", "href": "/app/x_resolvia/buscar/comodo/Sala?aba=buscar&comodo=Sala"})
        self.assertIn("- Regar a planta\n- e mais 3", m["texto"])
        st, r = self.j("/api/ronda", {"acao": "proxima"})  # 1.22.2: Tarefas: Nova é só uma pergunta: sem o botão
        self.assertEqual(r["ronda"]["ativa"]["etapa"], "Nova")
        self.assertNotIn("abrir", r["mensagens"][-1], "uma pergunta só não tem o que abrir")
        st, r = self.j("/api/ronda", {"acao": "proxima"})  # Itens (InventarIA, sem o endereço do app: sem link)
        self.assertNotIn("abrir", r["mensagens"][-1])


    def test_a_ia_que_nao_respondeu_nao_aparece_na_etapa(self):
        """1.31.1: numa etapa, o «Não consegui responder agora. Pode perguntar de outro jeito?» não faz sentido (quem pergunta
        é a ronda): fica só a pergunta da etapa, com o Abrir no app, e nenhuma pergunta do grupo sai."""
        self.casa()
        com_painel("resolvia", "/app/x_resolvia")
        for falha in S.ia.NAO_DEU:
            S.RONDAS_ATIVAS.clear()
            with mock.patch.object(S, "responder_ia", return_value=(falha, ["CorrerIA"], False)):
                st, r = self.j("/api/ronda", {"acao": "iniciar", "ronda": "casa", "onde": "Sala"})
            self.assertEqual(st, 200)
            m = r["mensagens"][-1]
            # 1.35.1 (o dono: "do nada só uma pergunta sem contexto"): a linha do app diz que a leitura não deu, e a pergunta vem embaixo
            self.assertRegex(m["texto"], r"^Não consegui ler o ResolvIA agora\.\n\n\*[^*\n]+\?\*$")
            self.assertNotIn("Pode perguntar de outro jeito", m["texto"])
            self.assertEqual(m["app"], "ResolvIA")
            self.assertIn("abrir", m)

    def test_a_leitura_sem_texto_ganha_a_linha_do_app(self):
        """1.35.1 (o dono, com o print de «Falta alguma rotina?» sozinha: "pq ele não diz que não encontrou nenhuma?"): a
        resposta que não deixa texto (só o TOTAL, só a pergunta repetida, nada) ganha a linha do app: nada encontrado, quantos,
        ou que a leitura não deu. Com texto da IA, a linha do app não entra."""
        self.casa()
        for resposta, linha in (("TOTAL: 0", "Nenhuma tarefa encontrada."), ("TOTAL: 3", "3 tarefas no ResolvIA."), ("TOTAL: 1", "1 tarefa no ResolvIA."),
                                ("Alguma dessas tarefas já foi feita?", "Não consegui ler o ResolvIA agora."), ("", "Não consegui ler o ResolvIA agora.")):
            S.RONDAS_ATIVAS.clear()
            with mock.patch.object(S, "responder_ia", return_value=(resposta, ["ResolvIA"], False)):
                st, r = self.j("/api/ronda", {"acao": "iniciar", "ronda": "casa", "onde": "Sala"})
            self.assertEqual(st, 200)
            self.assertTrue(r["mensagens"][-1]["texto"].startswith(linha + "\n\n*"), (resposta, r["mensagens"][-1]["texto"]))
        S.RONDAS_ATIVAS.clear()
        with mock.patch.object(S, "responder_ia", return_value=("TOTAL: 2\n2 tarefas abertas:\n- Varrer\n- Lavar", ["ResolvIA"], False)):
            r = self.j("/api/ronda", {"acao": "iniciar", "ronda": "casa", "onde": "Sala"})[1]
        self.assertTrue(r["mensagens"][-1]["texto"].startswith("2 tarefas abertas:"), "com o texto da IA, sem a linha do app")
        self.assertNotIn("no ResolvIA.", r["mensagens"][-1]["texto"])
        # o nome do que se procura vem do grupo; um grupo sem nome conhecido diz o app
        self.assertEqual([rondas.vazio("casa", "rotina_nova", n) for n in (0, 2, None)],
                         ["Nenhuma rotina encontrada.", "2 rotinas no CronologIA.", "Não consegui ler o CronologIA agora."])
        rid, e = next((rid, e) for rid, r in rondas.RONDAS.items() for e in r["etapas"] if e.get("pedido") and e["grupo"] not in rondas.VAZIO)
        self.assertEqual([rondas.vazio(rid, e["id"], n) for n in (0, 4)], [f"Nada encontrado no {e['nome_app']}.", f"4 resultados no {e['nome_app']}."])


class TestArquivoNaRonda(Base):
    """1.23.0 (o dono: mandou a foto de um consumível no meio da ronda e respondeu o GerencIA, "zero sentido"): no meio de uma
    ronda o arquivo é da etapa: a ferramenta do app da etapa que o recebe, ou a resposta de que ali não dá. Nunca outro app."""

    FOTO = {"nome": "foto.jpg", "b64": "data:image/jpeg;base64,/9j/LWZvdG8="}

    def leitor(self):
        """Um app que lê fotos e PDFs com a IA dele (como o GerencIA), que não é o da etapa."""
        g = AppFalso("GerencIA")
        self.addCleanup(g.fechar)
        g.rotas["/api/integracao/conversa"] = lambda h, c: (g.feitos.append(c), (200, {"resposta": "Não encontrei gastos nem recebimentos na foto."}))[1]
        g.publicar(S.SHARE_DIR, "gerencia", rota="/api/integracao/conversa")
        arq = os.path.join(S.SHARE_DIR, "gerencia", "correria.json")
        with open(arq, encoding="utf-8") as f:
            d = json.load(f)
        d.update(anexos=["image/jpeg", "application/pdf"], assunto="finanças: contas, faturas e gastos")
        with open(arq, "w", encoding="utf-8") as f:
            json.dump(d, f)
        return g

    def comeca(self):
        with mock.patch.object(S, "responder_ia", return_value=("TOTAL: 1\n- Trocar a lâmpada", ["ResolvIA"], False)):
            st, r = self.j("/api/ronda", {"acao": "iniciar", "ronda": "casa", "onde": "Sala"})
        self.assertEqual((st, r["ronda"]["ativa"]["app"]), (200, "ResolvIA"))

    def test_a_etapa_nao_recebe_foto_diz_isso_e_nao_manda_a_outro_app(self):
        self.casa()
        g = self.leitor()
        self.comeca()
        with mock.patch.object(S, "responder_ia") as ia:
            st, r = self.j("/api/conversa", {"texto": "Esse aqui tá cheio também, coloca 6 meses", "anexo": self.FOTO})
        self.assertEqual(st, 200)
        m = r["mensagens"][-1]
        self.assertEqual((m["texto"], m["app"]), ("Nesta etapa da ronda (ResolvIA) não dá para usar uma foto. Escreva o que você quer fazer aqui.", "ResolvIA"))
        self.assertEqual(g.feitos, [], "o app que lê fotos não é o da etapa: não recebe nada")
        ia.assert_not_called()
        with mock.patch.object(S, "responder_ia"):
            st, r = self.j("/api/conversa", {"anexo": {"nome": "f.pdf", "b64": "data:application/pdf;base64,JVBERg=="}})
        self.assertIn("não dá para usar um PDF", r["mensagens"][-1]["texto"])
        self.assertEqual(g.feitos, [])

    def test_a_ferramenta_do_app_da_etapa_recebe_a_foto(self):
        self.casa()
        self.resolvia.fechar()
        self.resolvia = self.ligar("resolvia", "ResolvIA", [ferr("tarefas", COM_COMODO), dict(ferr("anexar_foto", grava=True), anexo=["image/jpeg"])], {"tarefas": "1 tarefa."})
        g = self.leitor()
        self.addCleanup(S.FOTOS.clear)
        self.comeca()
        with mock.patch.object(S, "responder_ia", return_value=("Vou guardar.", ["ResolvIA"], True)) as ia:
            st, r = self.j("/api/conversa", {"texto": "conta de luz paga, guarda a fatura", "anexo": self.FOTO})
        self.assertEqual((st, r["mensagens"][-1]["app"]), (200, "ResolvIA"))
        hist = ia.call_args.args[2]
        self.assertIn("A pessoa mandou uma foto junto com esta mensagem, no meio da ronda. Você não vê o arquivo. Ele é desta etapa, do ResolvIA", hist[-1]["texto"])
        self.assertIn("Sala", hist[-2]["texto"], "antes, o contexto da etapa")
        self.assertEqual(g.feitos, [], "mesmo com a legenda falando de fatura: na ronda, é da etapa")
        self.assertTrue(S.foto_de("tela:" + next(iter(S.RONDAS_ATIVAS))), "a foto fica à mão para a ferramenta")

    def test_o_leitor_que_e_o_app_da_etapa_le(self):
        self.casa()
        g = self.leitor()
        self.comeca()
        rd = next(iter(S.RONDAS_ATIVAS.values()))
        de_verdade = S.rondas.etapa_de
        with mock.patch.object(S.rondas, "etapa_de", side_effect=lambda rid, eid: dict(de_verdade(rid, eid), app="gerencia", nome_app="GerencIA")):
            st, r = self.j("/api/conversa", {"texto": "", "anexo": self.FOTO})
        self.assertEqual(r["mensagens"][-1]["texto"], "Não encontrei gastos nem recebimentos na foto.")
        self.assertEqual(len(g.feitos), 1)
        self.assertTrue(rd)

    def test_fora_da_ronda_a_foto_segue_o_app_de_que_a_conversa_falava(self):
        inv = self.ligar("inventario", "InventarIA", [ferr("resumo"), dict(ferr("cadastrar_por_foto", grava=True), anexo=["image/jpeg"])], {"resumo": {}})
        g = self.leitor()
        self.addCleanup(S.FOTOS.clear)
        with mock.patch.object(S, "responder_ia", return_value=("Cadastrado o Sapólio.", ["InventarIA"], False)) as ia:
            self.j("/api/conversa", {"texto": "cadastra sapólio nos consumíveis"})
            st, r = self.j("/api/conversa", {"texto": "Esse aqui também, coloca 6 meses", "anexo": self.FOTO})
        self.assertEqual(ia.call_count, 2, "a legenda não fala de quem leria: vai para a IA com as ferramentas")
        self.assertEqual(g.feitos, [])
        # 1.24.1: o caso do dono, numa conversa nova: a legenda fala dos consumíveis; nunca vai para quem lê contas
        S._gravar_tela("_", [])
        for legenda in ("Adiciona esse nós consumíveis da lavanderia, 30 dias", "guarda isso aí pra mim"):
            with mock.patch.object(S, "responder_ia", return_value=("Vou cadastrar.", ["InventarIA"], True)) as ia:
                st, r = self.j("/api/conversa/nova", {})
                st, r = self.j("/api/conversa", {"texto": legenda, "anexo": self.FOTO})
            self.assertEqual((ia.call_count, r["mensagens"][-1]["app"], g.feitos), (1, "InventarIA", []), legenda)
        # a foto sem legenda nenhuma, numa conversa nova, continua indo para quem lê
        self.j("/api/conversa/nova", {})
        with mock.patch.object(S, "responder_ia") as ia:
            st, r = self.j("/api/conversa", {"texto": "", "anexo": self.FOTO})
        ia.assert_not_called()
        self.assertEqual(len(g.feitos), 1)
        # 1.25.0 (o dono: "não seria prudente dar a opção de indicar se o tema é em outro app?"): a resposta de quem leu leva os
        # outros apps que recebem esse arquivo, e ele fica à mão; um toque manda para lá, com o app dito à IA
        m = r["mensagens"][-1]
        self.assertEqual((m["app"], m["outros"]), ("GerencIA", [{"app": "inventario", "nome": "InventarIA"}]))
        with mock.patch.object(S, "responder_ia", return_value=("Vou cadastrar.", ["InventarIA"], True)) as ia:
            st, r = self.j("/api/conversa", {"texto": "É para o InventarIA.", "para": "inventario"})
        self.assertEqual((st, len(g.feitos), r["mensagens"][-1]["app"]), (200, 1, "InventarIA"))
        self.assertNotIn("outros", r["mensagens"][-1])
        hist = ia.call_args.args[2]
        self.assertIn("não era para o app que respondeu: é para o InventarIA. Use só as ferramentas do InventarIA que recebem o arquivo", hist[-1]["texto"])
        self.assertTrue(S.foto_de("tela:" + next(k for k in S.FOTOS if k.startswith("tela:"))[5:]), "o arquivo continua à mão para a ferramenta")
        # um app que não recebe o arquivo, ou sem arquivo à mão: diz, sem chamar ninguém
        S.FOTOS.clear()
        with mock.patch.object(S, "responder_ia") as ia:
            st, r = self.j("/api/conversa", {"texto": "É para o InventarIA.", "para": "inventario"})
        self.assertEqual((st, r["erro"]), (400, "O arquivo não está mais à mão. Mande de novo, dizendo de que app é."))
        ia.assert_not_called()
        g.feitos.clear()
        self.j("/api/conversa/nova", {})
        with mock.patch.object(S, "responder_ia") as ia:
            st, r = self.j("/api/conversa", {"texto": "olha a fatura do cartão", "anexo": self.FOTO})
        ia.assert_not_called()
        self.assertEqual(len(g.feitos), 1, "uma fatura continua indo para quem lê faturas")
        self.assertTrue(inv)


class TestRondas(Base):
    def test_sem_apps_nenhuma_ronda(self):
        self.assertEqual(self.j("/api/rondas"), (200, {"ativa": None, "feitos": [], "ultimas": {}, "avisar_dias": 30, "ultimas_de": {}, "prazos": {"casa": 30}, "rondas": [], "atrasados": [], "atrasados_de": [], "aviso": {"pessoas": []}}))
        self.assertIn("não está disponível", self.j("/api/ronda", {"acao": "iniciar", "ronda": "nada", "onde": "Sala"})[1]["erro"])
        st, r = self.j("/api/ronda", {"acao": "iniciar", "ronda": "casa", "onde": "Sala"})
        self.assertEqual(st, 400)
        self.assertIn("não está disponível", r["erro"])
        self.assertEqual(self.j("/api/ronda", {"acao": "proxima"})[1]["erro"], "Nenhuma ronda em andamento.")

    def test_as_etapas_seguem_o_que_esta_ligado(self):
        self.casa()
        r = self.j("/api/rondas")[1]["rondas"]
        self.assertEqual([(x["id"], x["nome"], x["onde"], x["livre"], x["sem_onde"]) for x in r],
                         [("casa", "Ronda da casa", ["Sala", "Cozinha"], False, False), ("compras", "Ronda de compras", [], False, True), ("mes", "Ronda do mês", [], False, True),
                          ("patrimonio", "Ronda do patrimônio", [], False, True), ("semana", "Ronda da semana", [], False, True), ("dia", "Ronda do dia", [], False, True)],
                         "a da chegada pede o Anotar compra do EconomIA, que esta casa de teste não tem")
        self.assertEqual([(e["id"], e["grupo"], e["app"]) for e in r[0]["etapas"]],
                         [("feita", "Tarefas", "ResolvIA"), ("arrumar", "Tarefas", "ResolvIA"),
                          ("item_novo", "Itens", "InventarIA"), ("item_saiu", "Itens", "InventarIA"), ("item_mudou", "Itens", "InventarIA"), ("sem_foto", "Itens", "InventarIA"),
                          ("cons_acabando", "Consumíveis", "InventarIA"), ("cons_novo", "Consumíveis", "InventarIA"),
                          ("mercado", "Compras", "EconomIA"), ("farmacia", "Compras", "EconomIA"), ("pet", "Compras", "EconomIA")])

    def test_cada_etapa_e_uma_pergunta_so(self):
        """O dono: "Deve sempre ser uma pergunta só… para que de fato seja um GUIA"."""
        for r in rondas.RONDAS.values():
            for e in r["etapas"]:
                p = e["pergunta"]
                self.assertEqual(p.count("?"), 1, p)
                self.assertTrue(p.endswith("?"), p)
                self.assertNotRegex(p, r" ou |,|…", p)
            self.assertEqual(len({e["id"] for e in r["etapas"]}), len(r["etapas"]))
            grupos = [e["grupo"] for e in r["etapas"]]
            for g in set(grupos):
                primeira = next(e for e in r["etapas"] if e["grupo"] == g)
                if r["onde"]:
                    self.assertTrue(primeira["pedido"], "na Ronda da casa, a primeira de cada grupo lê o app")
            self.assertTrue(r["etapas"][0]["pedido"], "toda ronda começa lendo")

    def test_o_texto_da_etapa_vem_arrumado(self):
        """O dono: "Não seria legal trazer mais organizado o texto?" A lista numa linha só vira uma linha por item, a
        pergunta que a IA repetiu (entre «») sai, e a pergunta da etapa vem no fim, à parte, em negrito."""
        a = rondas.arrumar("Temos 2 tarefas pendentes: - Tapar buracos da parede - Passar tíner no armário. Nenhuma delas tem prazo definido. "
                           "«Alguma dessas tarefas já foi feita?»", "casa", "feita", "Quarto")
        self.assertEqual(a, "Temos 2 tarefas pendentes:\n\n- Tapar buracos da parede\n- Passar tíner no armário\n\nNenhuma delas tem prazo definido.\n\n"
                            "*Alguma dessas tarefas já foi feita?*")
        self.assertEqual(rondas.arrumar("Há 3 itens. Os últimos: Mesa e Abajur. Chegou algum item novo?", "casa", "item_novo", "Sala"),
                         "Há 3 itens. Os últimos: Mesa e Abajur.\n\n*Chegou algum item novo?*")
        self.assertEqual(rondas.arrumar("Há 2.\r\n- Um\n- Dois\n\n\n\nFim.", "casa", "arrumar", "Sala"), "Há 2.\n\n- Um\n- Dois\n\nFim.\n\n*Tem algo novo para arrumar?*")
        self.assertEqual(rondas.arrumar(None, "casa", "pet", "Sala"), "*Precisa de algo do pet shop?*")
        # 1.21.2: a tela já tem o Próxima: o "pode seguir" da IA sai
        self.assertEqual(rondas.arrumar("Não há tarefas pendentes neste local. Pode seguir para a próxima etapa.", "casa", "arrumar", "Sala"),
                         "Não há tarefas pendentes neste local.\n\n*Tem algo novo para arrumar?*")
        self.assertNotIn("pode seguir", rondas.pedido("casa", "feita", "Sala", [], 1, 10))
        p = rondas.pedido("casa", "feita", "Sala", [], 1, 10)
        self.assertIn("NÃO faça pergunta nenhuma", p)
        self.assertIn("não repita o nome do cômodo", p)
        self.assertIsNone(rondas.pedido("casa", "arrumar", "Sala", [], 2, 10), "a segunda só pergunta")
        self.assertIn("um por linha", p)

    def test_sem_os_consumiveis_no_inventaria_sem_a_etapa(self):
        self.casa(consumiveis=False)
        self.assertEqual([e["id"] for e in self.j("/api/rondas")[1]["rondas"][0]["etapas"]], ["feita", "arrumar", "item_novo", "item_saiu", "item_mudou", "sem_foto", "mercado", "farmacia", "pet"])

    def test_so_um_app_ligado(self):
        self.ligar("economia", "EconomIA", [ferr("lista")], {"lista": "Na lista: Café."})
        r = self.j("/api/rondas")[1]["rondas"][0]
        self.assertEqual(([e["id"] for e in r["etapas"]], r["onde"], r["livre"]), (["mercado", "farmacia", "pet"], [], True), "sem o InventarIA, a pessoa escreve o cômodo")
        st, c = self.j("/api/ronda", {"acao": "iniciar", "ronda": "casa", "onde": "  Varanda  "})
        self.assertEqual((st, c["ronda"]["ativa"]["onde"], c["ronda"]["ativa"]["total"]), (200, "Varanda", 3))

    def test_a_ronda_inteira(self):
        self.casa()
        st, r = self.j("/api/ronda", {"acao": "iniciar", "ronda": "casa", "onde": "Banheiro"})
        self.assertEqual((st, r["erro"]), (400, "Escolha o cômodo."), "só um cômodo da lista do InventarIA")
        st, r = self.j("/api/ronda", {"acao": "iniciar", "ronda": "casa", "onde": "Sala"})
        self.assertEqual(st, 200)
        self.assertEqual(r["ronda"]["ativa"], {"id": "casa", "nome": "Ronda da casa", "onde": "Sala", "n": 1, "total": 11, "etapa": "Concluir", "grupo": "Tarefas", "app": "ResolvIA"})
        eu, ia_ = r["mensagens"][-2:]
        self.assertEqual((eu["papel"], eu["texto"], eu["ronda"]), ("eu", "Sala · Tarefas: Concluir (1 de 11)", True), "a pessoa vê só o rótulo, não o pedido")
        self.assertIn("Trocar a lâmpada", ia_["texto"])
        self.assertTrue(ia_["texto"].endswith("\n\n*Alguma dessas tarefas já foi feita?*"), ia_["texto"])
        self.assertEqual(self.resolvia.feitos[-1]["argumentos"], {"comodo": "Sala"}, "o ResolvIA com os cômodos: filtra")
        self.assertEqual(self.j("/api/conversa")[1]["ronda"]["ativa"]["n"], 1, "a conversa leva a ronda em andamento")
        # uma resposta da pessoa segue pela conversa de sempre, e a ronda continua
        visto = []
        real = S.AGENTE.responder
        with mock.patch.object(S.AGENTE, "responder", lambda h, *a, **k: (visto.append(h), real(h, *a, **k))[1]):
            st, r = self.j("/api/conversa", {"texto": "nada"})
        self.assertEqual(r["ronda"]["ativa"]["etapa"], "Concluir")
        self.assertIn("etapa Concluir", visto[0][-2]["texto"], "a IA sabe de que etapa é a resposta")
        self.assertIn("ResolvIA", visto[0][-2]["texto"])
        self.assertEqual((visto[0][-1]["texto"], r["mensagens"][-2]["texto"]), ("nada", "nada"), "na conversa, só o que a pessoa escreveu")
        n = len(self.resolvia.feitos)
        r = self.j("/api/ronda", {"acao": "proxima"})[1]  # a segunda do grupo: só a pergunta, sem ler de novo
        self.assertEqual((r["ronda"]["ativa"]["etapa"], r["mensagens"][-2]["texto"]), ("Nova", "Sala · Tarefas: Nova (2 de 11)"))
        self.assertEqual((r["mensagens"][-1]["texto"], r["mensagens"][-1]["app"]), ("*Tem algo novo para arrumar?*", "ResolvIA"))
        self.assertEqual(len(self.resolvia.feitos), n, "sem chamar o app")
        r = self.j("/api/ronda", {"acao": "voltar"})[1]
        self.assertEqual(r["ronda"]["ativa"]["n"], 1)
        self.assertEqual(self.j("/api/ronda", {"acao": "voltar"})[1]["ronda"]["ativa"]["n"], 1, "na primeira, fica")
        fins = {"Nova": "Tem algo novo para arrumar?", "Novo": "Chegou algum item novo?", "Descartado": "Algum item foi descartado?",
                "Transferido": "Algum item foi transferido de cômodo?", "Sem foto": "Quer mandar a foto de algum desses itens?", "Acabando": "Algum desses consumíveis precisa repor?", "Consumível novo": "Quer adicionar algum consumível?",
                "Mercado": "Precisa de algo do mercado?", "Farmácia": "Precisa de algo da farmácia?", "Pet shop": "Precisa de algo do pet shop?"}
        for etapa, fim in fins.items():
            r = self.j("/api/ronda", {"acao": "proxima"})[1]
            self.assertEqual(r["ronda"]["ativa"]["etapa"], "Novo" if etapa == "Consumível novo" else etapa)
            self.assertTrue(r["mensagens"][-1]["texto"].endswith(f"*{fim}*"), r["mensagens"][-1]["texto"])
            if etapa == "Novo":
                self.assertEqual(self.inventario.feitos[-1]["argumentos"], {"comodo": "Sala"})
            if etapa == "Acabando":
                self.assertEqual(self.inventario.feitos[-1]["argumentos"], {"comodo": "Consumíveis"}, "os consumíveis não têm cômodo: a área deles")
            if etapa == "Mercado":
                self.assertIn("Café", r["mensagens"][-1]["texto"])
        r = self.j("/api/ronda", {"acao": "proxima"})[1]  # a última: concluída, e a escolha do próximo cômodo
        self.assertIsNone(r["ronda"]["ativa"])
        self.assertEqual((r["ronda"]["feitos"], r["ronda"]["rondas"][0]["onde"]), (["Sala"], ["Sala", "Cozinha"]))
        self.assertEqual([m["texto"] for m in r["mensagens"][-2:]], ["Sala · concluída", "Ronda concluída. Quando quiser, escolha o próximo cômodo."])
        r = self.j("/api/ronda", {"acao": "iniciar", "ronda": "casa", "onde": "Cozinha"})[1]
        self.assertEqual((r["ronda"]["ativa"]["onde"], r["ronda"]["feitos"]), ("Cozinha", ["Sala"]))
        r = self.j("/api/ronda", {"acao": "sair"})[1]
        self.assertIsNone(r["ronda"]["ativa"])
        self.assertEqual(self.j("/api/ronda", {"acao": "dançar"})[1]["erro"], "Nenhuma ronda em andamento.")

    def test_acao_desconhecida_e_o_pendente_da_etapa_anterior(self):
        self.casa()
        self.j("/api/ronda", {"acao": "iniciar", "ronda": "casa", "onde": "Sala"})
        self.assertEqual(self.j("/api/ronda", {"acao": "dançar"}), (400, {"erro": "acao vale iniciar, proxima, voltar ou sair."}))
        S.guardar_pendente("tela:u-ana", {"chamadas": [], "em": S.agora_iso()})
        self.j("/api/ronda", {"acao": "proxima"})
        self.assertFalse(S.ler_conversas().get("pendentes", {}).get("tela:u-ana"), "mudou de etapa: o sim da anterior não vale mais")

    def test_outra_conversa_encerra_a_ronda(self):
        self.casa()
        self.j("/api/ronda", {"acao": "iniciar", "ronda": "casa", "onde": "Sala"})
        self.j("/api/conversa/nova", {})
        self.assertIsNone(self.j("/api/conversa")[1]["ronda"]["ativa"])

    def test_resolvia_sem_os_comodos_nao_filtra(self):
        self.casa(comodo_no_resolvia=False)
        self.j("/api/ronda", {"acao": "iniciar", "ronda": "casa", "onde": "Sala"})
        self.assertEqual(self.resolvia.feitos[-1]["argumentos"], {})
        p = rondas.pedido("casa", "feita", "Sala", S.FERR.todas(), 1, 4)
        self.assertIn("não filtra por cômodo", p)
        self.assertNotIn("o campo comodo", p)

    def test_sem_a_ia_avisa(self):
        self.casa()
        with mock.patch.object(S, "responder_ia", lambda *a, **k: None):
            r = self.j("/api/ronda", {"acao": "iniciar", "ronda": "casa", "onde": "Sala"})[1]
        self.assertEqual(r["mensagens"][-1]["texto"], "*Alguma dessas tarefas já foi feita?*", "sem a IA, a pergunta sai do mesmo jeito")

    def test_resumo_do_inventaria_com_defeito(self):
        self.ligar("inventario", "InventarIA", [ferr("resumo"), ferr("buscar_itens", COM_COMODO)], {"resumo": "não é JSON", "buscar_itens": "nada"})
        r = self.j("/api/rondas")[1]["rondas"][0]
        self.assertEqual(([e["id"] for e in r["etapas"]], r["livre"]), (["item_novo", "item_saiu", "item_mudou", "sem_foto"], True))
        class F:  # o resumo que não é um objeto, ou a ferramenta que erra
            def __init__(self, r): self.r = r
            def usar(self, f, a, p, c): return self.r
        T = [{"id": "inventario_resumo"}]
        self.assertEqual(rondas._resumo_inventario(F(("[1, 2]", None)), T, None), {})
        self.assertEqual(rondas._resumo_inventario(F((None, "fora do ar")), T, None), {})
        self.assertEqual(rondas._resumo_inventario(F((None, None)), T, None), {})

class TestMaisRondas(Base):
    """1.20.0: as rotinas (CronologIA) e os consumíveis por cômodo na Ronda da casa; as rondas sem cômodo (compras,
    chegada das compras e do mês)."""

    def test_rotinas_do_cronologia_depois_das_tarefas(self):
        self.casa()
        cron = self.ligar("cronologia", "CronologIA", [ferr("cadastros"), ferr("agenda")], {"cadastros": "Rotinas: Regar as plantas da sala (toda semana).", "agenda": "Dentista dia 3."})
        e = self.j("/api/rondas")[1]["rondas"][0]["etapas"]
        self.assertEqual([(x["id"], x["grupo"]) for x in e][:6], [("feita", "Tarefas"), ("arrumar", "Tarefas"), ("rotina_nova", "Rotinas"), ("rotina_muda", "Rotinas"),
                                                                  ("rotina_sai", "Rotinas"), ("manut", "Manutenção")])
        self.j("/api/ronda", {"acao": "iniciar", "ronda": "casa", "onde": "Sala"})
        self.j("/api/ronda", {"acao": "proxima"})
        r = self.j("/api/ronda", {"acao": "proxima"})[1]
        self.assertEqual(r["ronda"]["ativa"]["app"], "CronologIA")
        self.assertIn("Regar as plantas", r["mensagens"][-1]["texto"])
        self.assertTrue(r["mensagens"][-1]["texto"].endswith("*Falta alguma rotina?*"), "a primeira pergunta vale mesmo sem rotina nenhuma")
        self.assertEqual(cron.feitos[-1]["nome"], "cadastros")
        fins = [self.j("/api/ronda", {"acao": "proxima"})[1]["mensagens"][-1]["texto"] for _ in range(2)]
        self.assertEqual(fins, ["*Alguma rotina precisa mudar?*", "*Alguma rotina pode sair?*"], "a IA não disse quantas achou: as perguntas ficam")

    def test_perguntas_inteligentes(self):
        """O dono: "se não tem rotina da casa, pq perguntar se alguma precisa sair? Não tem nenhuma". Sem nada no app, as
        perguntas que só valem com alguma coisa saem da ronda; com alguma coisa, ficam."""
        self.resolvia = self.ligar("resolvia", "ResolvIA", [ferr("tarefas", COM_COMODO)], {"tarefas": "Nenhuma tarefa."})
        self.ligar("cronologia", "CronologIA", [ferr("cadastros")], {"cadastros": "Nenhuma rotina de lá."})
        self.ligar("inventario", "InventarIA", [ferr("resumo"), ferr("buscar_itens", COM_COMODO)],
                   {"resumo": {"comodos": [{"nome": "Sala"}], "opcoes": {"consumiveis": True}}, "buscar_itens": "0 itens."})
        r = self.j("/api/ronda", {"acao": "iniciar", "ronda": "casa", "onde": "Sala"})[1]
        # sem tarefas: nada de "alguma já foi feita?"; a pergunta que vale sempre vem direto ali, na mesma mensagem
        # (o dono: "direto ali e não em outra pergunta, se não quebra o ritmo das perguntas")
        self.assertEqual((r["ronda"]["ativa"]["etapa"], r["ronda"]["ativa"]["n"], r["ronda"]["ativa"]["total"]), ("Nova", 1, 11))
        self.assertEqual(r["mensagens"][-1]["texto"], "Pelo que vi:\nNenhuma tarefa.\n\n*Tem algo novo para arrumar?*")
        self.assertEqual(r["mensagens"][-2]["texto"], "Sala · Tarefas: Nova (1 de 11)")
        self.assertNotIn("TOTAL", r["mensagens"][-1]["texto"])
        vistos = []
        while True:
            r = self.j("/api/ronda", {"acao": "proxima"})[1]
            if not r["ronda"]["ativa"]:
                break
            vistos.append((r["ronda"]["ativa"]["grupo"], r["ronda"]["ativa"]["etapa"], r["ronda"]["ativa"]["total"], r["mensagens"][-1]["texto"].split("\n")[-1]))
        self.assertEqual(vistos, [("Rotinas", "Nova", 9, "*Falta alguma rotina?*"),            # sem rotinas: sem o Mudar e o Tirar
                                  ("Manutenção", "Conferir", 9, "Nenhuma rotina de lá."),     # 1.37.0: a etapa que lê e só vale com alguma coisa só conta
                                  ("Itens", "Novo", 7, "*Chegou algum item novo?*"),          # sem itens: sem o Descartado e o Transferido
                                  ("Itens", "Sem foto", 7, "0 itens."),
                                  ("Consumíveis", "Novo", 6, "*Quer adicionar algum consumível?*")])  # nenhum acabando: direto o adicionar
        self.assertIn("0 itens.", r["mensagens"][-3]["texto"])
        self.assertEqual(r["mensagens"][-4]["texto"], "Sala · Consumíveis: Novo (6 de 6)", "o rótulo com a conta do que ficou")
        self.assertEqual(S.historico_rondas()[-1]["perguntas"], 6)
        e0 = ["feita", "arrumar", "cons_acabando", "cons_novo", "mercado"]
        self.assertEqual((rondas.junta_com("casa", e0, 0, 0), rondas.junta_com("casa", e0, 2, 0)), (1, 3))
        self.assertEqual((rondas.junta_com("casa", e0, 0, 2), rondas.junta_com("casa", e0, 0, None), rondas.junta_com("casa", e0, 1, 0)), (None, None, None))
        self.assertIsNone(rondas.junta_com("casa", ["cons_acabando", "mercado"], 0, 0), "sem a seguinte no grupo, só conta")
        self.assertIsNone(rondas.junta_com("casa", ["cons_acabando"], 0, 0))
        self.assertEqual(rondas.total("TOTAL: 3\nHá 3."), (3, "Há 3."))
        self.assertEqual(rondas.total("Há 3.\n**TOTAL: 0**"), (0, "Há 3."))
        self.assertEqual(rondas.total("Há 3."), (None, "Há 3."))
        self.assertEqual(rondas.arrumar("", "casa", "cons_acabando", "Sala", perguntar=False), "Nada por aqui.")
        e = ["feita", "arrumar", "item_novo", "item_saiu", "item_mudou", "mercado"]
        self.assertEqual(rondas.sem_o_que_perguntar("casa", e, 2, 2), e, "com itens, tudo fica")
        self.assertEqual(rondas.sem_o_que_perguntar("casa", e, 2, None), e, "sem saber, tudo fica")
        self.assertEqual(rondas.sem_o_que_perguntar("casa", e, 0, 0), e, "o algo novo para arrumar vale sempre")

    def test_rotinas_pelo_comodo(self):
        """1.21.2 (o dono mandou o print do CronologIA com as rotinas por cômodo e a ronda dizia que não havia): o
        CronologIA 1.108.0 diz os cômodos de cada rotina e filtra por cômodo; a ronda pede assim."""
        self.casa()
        cron = self.ligar("cronologia", "CronologIA", [ferr("cadastros", COM_COMODO)], {"cadastros": "1 rotina: Regar as plantas (toda semana)."})
        self.j("/api/ronda", {"acao": "iniciar", "ronda": "casa", "onde": "Sala"})
        self.j("/api/ronda", {"acao": "proxima"})
        r = self.j("/api/ronda", {"acao": "proxima"})[1]
        self.assertEqual(r["ronda"]["ativa"]["grupo"], "Rotinas")
        self.assertEqual(cron.feitos[-1]["argumentos"], {"comodo": "Sala"}, "pede só as do cômodo")
        self.assertIn("Regar as plantas", r["mensagens"][-1]["texto"])
        p = rondas.pedido("casa", "rotina_nova", "Sala", S.FERR.todas(), 3, 13)
        self.assertIn("o campo comodo", p)
        self.assertIn("em comodos", p)
        velho = rondas.pedido("casa", "rotina_nova", "Sala", [{"id": "cronologia_cadastros", "entrada": {"properties": {}}}], 3, 13)
        self.assertIn("não filtra por cômodo", velho, "um CronologIA de antes: a IA procura nos comodos e no nome")

    def test_consumiveis_por_comodo(self):
        self.resolvia = self.ligar("resolvia", "ResolvIA", [ferr("tarefas", COM_COMODO)], {"tarefas": "nada"})
        USADO = {"type": "object", "properties": {"comodo": {"type": "string"}, "usado_em": {"type": "string"}}}
        self.ligar("inventario", "InventarIA", [ferr("resumo"), ferr("buscar_itens", USADO)],
                   {"resumo": {"comodos": [{"nome": "Cozinha"}], "opcoes": {"consumiveis": True, "consumiveis_por_comodo": True}}, "buscar_itens": "1 consumível: Detergente."})
        self.assertEqual(self.j("/api/rondas")[1]["rondas"][0]["opcoes"], ["consumiveis", "consumiveis_por_comodo"])
        self.j("/api/ronda", {"acao": "iniciar", "ronda": "casa", "onde": "Cozinha"})
        self.assertEqual(S.RONDAS_ATIVAS["u-ana"]["opcoes"], ["consumiveis", "consumiveis_por_comodo"])
        p = rondas.pedido("casa", "cons_acabando", "Cozinha", S.FERR.todas(), 6, 7, S.RONDAS_ATIVAS["u-ana"]["opcoes"])
        self.assertIn("usado_em «Cozinha»", p)
        self.assertNotIn("não têm cômodo", p)
        self.assertIn("não têm cômodo", rondas.pedido("casa", "cons_acabando", "Cozinha", S.FERR.todas(), 6, 7, ["consumiveis"]))

    def test_ronda_de_compras_sem_comodo(self):
        self.casa()
        self.economia.fechar()
        eco = self.ligar("economia", "EconomIA", [ferr("lista"), ferr("reposicao"), ferr("ofertas"), ferr("roteiro"), ferr("comprei", grava=True)],
                         {"lista": "Na lista: Café, Ração.", "reposicao": "Na hora: Sabão.", "ofertas": "Café 20% no Mercado Exemplo.", "roteiro": "Mercado Exemplo: 2 itens, R$ 30,00."})
        L = {x["id"]: x for x in self.j("/api/rondas")[1]["rondas"]}
        self.assertEqual(list(L), ["casa", "compras", "chegada", "mes", "patrimonio", "semana", "dia"], "a do lazer só com o OdisseIA ligado")
        self.assertEqual(([e["id"] for e in L["compras"]["etapas"]], L["compras"]["sem_onde"], L["compras"]["onde"]), (["lista", "repor", "acabando", "ofertas", "roteiro"], True, []))
        st, r = self.j("/api/ronda", {"acao": "iniciar", "ronda": "compras", "onde": "tanto faz"})
        self.assertEqual((st, r["ronda"]["ativa"]["onde"], r["ronda"]["ativa"]["total"], r["ronda"]["ativa"]["grupo"]), (200, "", 5, "Lista"))
        self.assertEqual(r["mensagens"][-2]["texto"], "Ronda de compras · Lista: O que falta (1 de 5)")
        self.assertTrue(r["mensagens"][-1]["texto"].endswith("*Falta algo na lista de compras?*"))
        self.assertIn("Café", r["mensagens"][-1]["texto"])
        fins = []
        for _ in range(4):
            r = self.j("/api/ronda", {"acao": "proxima"})[1]
            fins.append(r["mensagens"][-1]["texto"].split("*")[-2])
        self.assertEqual(fins, ["Quer pôr na lista o que está na hora de repor?", "Quer pôr na lista algum consumível que está acabando?",
                                "Quer aproveitar alguma dessas ofertas?", "Vai comprar nessa loja?"])
        self.assertEqual([c["nome"] for c in eco.feitos], ["lista", "reposicao", "ofertas", "roteiro"])
        r = self.j("/api/ronda", {"acao": "proxima"})[1]
        self.assertEqual([m["texto"] for m in r["mensagens"][-2:]], ["Ronda de compras · concluída", "Ronda de compras concluída."])
        self.assertNotIn("proximo", r["ronda"], "sem cômodo, não há próximo a escolher")
        self.assertEqual([(x["ronda"], x["onde"]) for x in S.historico_rondas()], [("compras", "")])
        self.assertEqual(S.ultimas_rondas(), {}, "não conta como ronda de um cômodo")
        h = self.j("/api/estado")[1]["rondas"]["historico"]
        self.assertEqual([(x["ronda"], x["onde"]) for x in h], [("Ronda de compras", "")])

    def test_chegada_e_mes(self):
        self.casa()
        self.economia.fechar()
        self.ligar("economia", "EconomIA", [ferr("lista"), ferr("reposicao"), ferr("comprei", grava=True)], {"lista": "Na lista: Café.", "reposicao": "Sabão a cada 30 dias."})
        self.ligar("gerencia", "GerencIA", [ferr("resumo"), ferr("contas_a_pagar"), ferr("lancar", grava=True)], {"resumo": "Entrou 100, saiu 80.", "contas_a_pagar": "Luz dia 10."})
        L = {x["id"]: [e["id"] for e in x["etapas"]] for x in self.j("/api/rondas")[1]["rondas"]}
        self.assertEqual(L["chegada"], ["comprei", "fora", "consumivel", "item", "gasto"][:2] + ["gasto"], "sem o cadastrar do InventarIA, sem as etapas de guardar")
        self.assertEqual(L["mes"], ["gastos", "contas", "tarefas", "itens", "repor"])
        r = self.j("/api/ronda", {"acao": "iniciar", "ronda": "chegada"})[1]
        self.assertTrue(r["mensagens"][-1]["texto"].endswith("*O que da lista você comprou?*"))
        self.assertIn("dura_dias", rondas.pedido("chegada", "comprei", "", S.FERR.todas(), 1, 3))
        self.assertIn("dura_dias", rondas.contexto("chegada", "comprei", ""))
        # 1.25.1 (o dono, na etapa dos consumíveis: "são bens (valor em R$) ou consumíveis?" e a foto dos cremes lida como móveis):
        # ali tudo é consumível, e a foto é lida como de consumíveis
        c = rondas.contexto("casa", "cons_novo", "Banheiro")
        self.assertIn("nunca pergunte se é bem ou consumível e nunca peça valor", c)
        self.assertIn("no cômodo «Consumíveis», com usado_em «Banheiro», com duracao_dias", c)
        e = rondas.etapa_de("casa", "cons_novo")
        self.assertIn("ao ler, mande consumiveis: true", rondas.contexto_anexo(e, "image/jpeg"))
        # 1.26.0: cada grupo da Ronda da casa tem o seu contexto fixo; a etapa de pôr consumível na lista de compras não é de cadastrar
        self.assertIn("tudo é tarefa do ResolvIA do cômodo «Sala»: ao criar uma, ligue-a ao cômodo «Sala»", rondas.contexto("casa", "arrumar", "Sala"))
        self.assertIn("tudo é rotina da casa ou manutenção do CronologIA do cômodo «Sala»", rondas.contexto("casa", "rotina_nova", "Sala"))
        self.assertIn("tudo é item da casa do cômodo «Sala» (não é consumível nem bem): cadastre no cômodo «Sala»; sem valor dito, cadastre sem valor", rondas.contexto("casa", "item_novo", "Sala"))
        self.assertIn("para pôr um produto basta o nome; não pergunte preço, marca nem loja", rondas.contexto("casa", "mercado", "Sala"))
        self.assertNotIn("nunca peça valor", rondas.contexto("compras", "acabando", ""))
        self.assertIn("nunca peça valor", rondas.contexto("chegada", "consumivel", ""))
        outro = next(x for x in rondas.RONDAS["casa"]["etapas"] if not rondas.de_consumiveis(x))
        self.assertNotIn("consumiveis: true", rondas.contexto_anexo(outro, "image/jpeg"))
        self.assertNotIn("nunca peça valor", rondas.contexto("casa", outro["id"], "Banheiro"))
        r = self.j("/api/ronda", {"acao": "iniciar", "ronda": "mes"})[1]
        self.assertEqual((r["ronda"]["ativa"]["nome"], r["mensagens"][-2]["texto"]), ("Ronda do mês", "Ronda do mês · Finanças: Gastos do mês (1 de 5)"))
        self.assertIn("Entrou 100", r["mensagens"][-1]["texto"])


class TestHistoricoEAviso(Base):
    """1.19.0: a ronda concluída vai para o histórico; um cômodo sem ronda há mais de N dias (15, 30, 45 ou outro) é avisado."""

    def anotar(self, onde, dias):
        from datetime import datetime, timedelta
        with mock.patch.object(S, "agora_iso", lambda: (datetime.now() - timedelta(days=dias)).isoformat(timespec="seconds")):
            S.anotar_ronda("casa", onde, {"nome": "Ana"}, 10)

    def test_a_ronda_concluida_fica_no_historico(self):
        self.ligar("economia", "EconomIA", [ferr("lista")], {"lista": "Na lista: Café."})
        self.j("/api/ronda", {"acao": "iniciar", "ronda": "casa", "onde": "Varanda"})
        for _ in range(3):
            r = self.j("/api/ronda", {"acao": "proxima"})[1]
        self.assertEqual((r["ronda"]["feitos"], r["ronda"]["ultimas"]), (["Varanda"], {"Varanda": 0}))
        h = S.historico_rondas()
        self.assertEqual([(x["ronda"], x["onde"], x["pessoa"], x["perguntas"]) for x in h], [("casa", "Varanda", "Ana", 3)])
        self.assertEqual(oct(os.stat(S.RONDAS_ARQ).st_mode & 0o777), "0o600")
        e = self.j("/api/estado")[1]["rondas"]
        self.assertEqual((e["avisar_dias"], [(x["onde"], x["pessoa"]) for x in e["historico"]]), (30, [("Varanda", "Ana")]))

    def test_so_as_ultimas_500_e_o_arquivo_com_defeito(self):
        with mock.patch.object(S, "MAX_RONDAS", 3):
            for i in range(5):
                S.anotar_ronda("casa", f"Cômodo {i}", None, 1)
        self.assertEqual([x["onde"] for x in S.historico_rondas()], ["Cômodo 2", "Cômodo 3", "Cômodo 4"])
        S.gravar_arquivo(S.RONDAS_ARQ, json.dumps({"historico": [{"onde": "Sala", "em": "ontem", "ronda": "casa"}, "x", {"onde": "Sala"}]}))
        self.assertEqual(S.ultimas_rondas(), {}, "uma data que não é data não conta")
        S.gravar_arquivo(S.RONDAS_ARQ, json.dumps({"historico": "x"}))
        self.assertEqual(S.historico_rondas(), [])

    def test_atrasados(self):
        self.casa()
        self.assertEqual(S.conferir_rondas(), [], "sem nenhuma ronda ainda, nada a avisar")
        self.anotar("Sala", 40)
        self.anotar("Sala", 31)
        self.anotar("Cozinha", 5)
        self.assertEqual(S.ultimas_rondas(), {"Sala": 31, "Cozinha": 5}, "a mais nova de cada cômodo")
        self.assertEqual(S.conferir_rondas(), [{"ronda": "casa", "nome": "Ronda da casa", "onde": "Sala", "dias": 31, "prazo": 30}])
        r = self.j("/api/rondas")[1]
        self.assertEqual((r["atrasados"], r["avisar_dias"], r["ultimas"]), (["Sala"], 30, {"Sala": 31, "Cozinha": 5}))
        self.assertEqual(self.j("/api/estado")[1]["rondas"]["atrasados"], ["Sala"])
        self.assertEqual(self.j("/api/config", {"ronda_dias": 45})[0], 200)
        self.assertEqual(S.conferir_rondas(), [])
        self.j("/api/config", {"ronda_dias": 4})  # outro: qualquer número de 1 a 365
        self.assertEqual([a["onde"] for a in S.conferir_rondas()], ["Sala", "Cozinha"])
        self.j("/api/config", {"ronda_dias": 0})
        self.assertEqual(S.conferir_rondas(), [], "nunca: sem aviso")
        for ruim in (366, -1, "30", True, 1.5):
            st, r = self.j("/api/config", {"ronda_dias": ruim})
            self.assertEqual((st, r["erro"]), (400, "Escolha de 1 a 365 dias, ou nunca."), ruim)
        self.assertEqual(S.ler_config()["ronda_dias"], 0)

    def test_comodo_que_nunca_teve_ronda(self):
        self.casa()
        self.anotar("Sala", 1)
        self.assertEqual([(a["onde"], a["dias"]) for a in S.conferir_rondas()], [("Cozinha", None)], "depois da primeira ronda da casa, o que nunca teve conta")

    def test_o_aviso_no_sino(self):
        self.casa()
        self.anotar("Sala", 31)
        self.anotar("Cozinha", 2)
        S.salvar_config({"casa": False})
        idos = []
        with mock.patch.object(S, "TOKEN", "t"), mock.patch.object(S, "ha_post", lambda rota, corpo: idos.append((rota, corpo))):
            S.conferir_rondas()
            S.conferir_rondas()  # a mesma lista: sem repetir
            self.assertEqual(idos, [("/services/persistent_notification/create", {"notification_id": "correria_ronda", "title": "CorrerIA · Ronda da casa",
                                                                                 "message": "Sala está sem ronda há mais de 30 dias."})])
            S.salvar_config({"ronda_dias": 1})
            S.conferir_rondas()
            self.assertEqual(idos[-1][1]["message"], "2 cômodos estão sem ronda há mais de 1 dias: Sala, Cozinha.")
            S.salvar_config({"ronda_dias": 0})
            S.conferir_rondas()
            self.assertEqual(idos[-1], ("/services/persistent_notification/dismiss", {"notification_id": "correria_ronda"}))


class TestAvisoNoCelular(Base):
    """1.21.0: o aviso de cômodo sem ronda no celular, como nos outros apps: o horário, quem recebe e o Testar."""
    ESTADOS = [{"entity_id": "person.ana", "attributes": {"friendly_name": "Ana", "user_id": "u-ana", "device_trackers": ["device_tracker.celular_da_ana", "device_tracker.roteador"]}},
               {"entity_id": "person.beto", "attributes": {"friendly_name": "Beto", "user_id": "u-beto", "device_trackers": ["device_tracker.pixel_do_beto"]}},
               {"entity_id": "person.caio", "attributes": {"friendly_name": "Caio", "user_id": "u-caio", "device_trackers": []}},
               {"entity_id": "light.sala", "attributes": {}}]
    SERVICOS = [{"domain": "light", "services": {"turn_on": {}}},
                {"domain": "notify", "services": {"mobile_app_moto_g_exemplo": {}, "mobile_app_pixel_do_beto": {}, "mobile_app_roteador": {}, "notify": {}}}]
    MODELO = [["device_tracker.celular_da_ana", "Moto G Exemplo", ["mobile_app"]], ["device_tracker.pixel_do_beto", "Pixel do Beto", ["mobile_app"]],
              ["device_tracker.roteador", "Roteador", ["tplink"]]]

    def ha(self, modelo=MODELO, recusa=()):
        self.idos = []
        S._celulares_cache.update(t=0, v=None)
        self.addCleanup(S._celulares_cache.update, {"t": 0, "v": None})
        S.ESTADO["ronda_avisado"] = None
        S.salvar_config({"casa": False})

        def texto(caminho, corpo):
            self.modelo_pedido = corpo["template"]
            if modelo is None:
                raise OSError("sem modelo")
            return json.dumps(modelo)

        def post(caminho, corpo):
            self.idos.append((caminho, corpo))
            if any(r in caminho for r in recusa):
                raise OSError("recusou")
            return {}
        for nome, v in (("TOKEN", "t"), ("ha_get", lambda c, timeout=10: self.ESTADOS if c == "/states" else self.SERVICOS), ("ha_texto", texto), ("ha_post", post),
                        ("atalho", lambda host=None: "/app/abc_correria")):
            p = mock.patch.object(S, nome, v)
            p.start()
            self.addCleanup(p.stop)

    def atrasar(self, onde="Sala", dias=40):
        from datetime import datetime, timedelta
        with mock.patch.object(S, "agora_iso", lambda: (datetime.now() - timedelta(days=dias)).isoformat(timespec="seconds")):
            S.anotar_ronda("casa", onde, {"nome": "Ana"}, 10)

    def avisos_idos(self):
        return [(c, x) for c, x in self.idos if "/notify/" in c]

    def test_os_celulares_de_cada_pessoa(self):
        self.ha()
        P = {p["nome"]: p["celulares"] for p in S.pessoas_com_celular()}
        self.assertEqual(P, {"Ana": ["mobile_app_moto_g_exemplo"], "Beto": ["mobile_app_pixel_do_beto"], "Caio": []},
                         "pelo nome do aparelho do app Home Assistant; o roteador não é celular")
        self.assertIn('"device_tracker.celular_da_ana"', self.modelo_pedido)
        self.assertEqual(self.j("/api/rondas")[1]["aviso"], {"pessoas": [{"id": "person.ana", "nome": "Ana", "celular": True, "eu": True},
                                                                       {"id": "person.beto", "nome": "Beto", "celular": True, "eu": False},
                                                                       {"id": "person.caio", "nome": "Caio", "celular": False, "eu": False}]})

    def test_sem_o_modelo_vale_o_id_do_rastreador(self):
        for modelo in (None, "não é lista"):
            self.ha(modelo=modelo)
            P = {p["nome"]: p["celulares"] for p in S.pessoas_com_celular(True)}
            self.assertEqual(P, {"Ana": ["mobile_app_roteador"], "Beto": ["mobile_app_pixel_do_beto"], "Caio": []}, modelo)
        import avisos
        self.assertIsNone(avisos.aparelhos("{"))
        self.assertEqual(avisos.aparelhos([["device_tracker.x", None, []], "lixo"]), {"device_tracker.x": None})
        self.assertEqual(avisos.celulares(["device_tracker.x"], {"mobile_app_x"}, {"device_tracker.x": None}), [], "um rastreador sem aparelho não é celular")
        self.assertEqual(avisos.slug("Relógio  do Davi"), "relogio_do_davi")
        self.assertEqual((avisos.titulo_do_app("CorrerIA · Oi"), avisos.titulo_do_app("")), ("CorrerIA · Oi", "CorrerIA"))

    def test_fora_do_home_assistant(self):
        self.assertEqual(S.pessoas_com_celular(), [])
        self.assertIsNone(S.avisar_rondas())
        self.assertEqual(self.j("/api/ronda/testar", {}), (400, {"erro": "Você não é uma pessoa da casa no Home Assistant."}))

    def test_o_horario_e_quem_recebe(self):
        self.assertEqual((S.ler_config()["ronda_hora"], S.ler_config()["ronda_para"]), ("09:00", []))
        self.assertEqual(self.j("/api/config", {"ronda_hora": "07:30", "ronda_para": ["person.ana", "person.ana", "person.beto"]})[0], 200)
        e = self.j("/api/estado")[1]["rondas"]
        self.assertEqual((e["hora"], e["para"]), ("07:30", ["person.ana", "person.beto"]))
        for ruim in ("7:30", "07:15", "24:00", "", None):
            self.assertEqual(self.j("/api/config", {"ronda_hora": ruim}), (400, {"erro": "O horário vale de meia em meia hora (09:00, 09:30…)."}), ruim)
        for ruim in ("person.ana", ["ana"], [1], ["person.x"] * 31):
            self.assertEqual(self.j("/api/config", {"ronda_para": ruim})[1]["erro"], "Quem recebe: as pessoas da casa (person.*).")
        self.assertEqual(S.ler_config()["ronda_hora"], "07:30")

    def test_cada_ronda_tem_o_seu_prazo(self):
        """1.32.0 (o dono: "os dias de avisos devem estar configurados em cada ronda"): o prazo é de cada ronda; uma sem cômodo
        com o aviso ligado conta também quando nunca foi feita, e o texto do aviso diz de qual ronda é."""
        from datetime import datetime, timedelta
        self.casa()
        self.assertEqual(S.ler_config()["ronda_prazos"], {"casa": 30}, "só a Ronda da casa começa com aviso")
        self.assertEqual(self.j("/api/config", {"ronda_prazo": {"ronda": "nao_existe", "dias": 10}})[0], 400)
        self.assertEqual(self.j("/api/config", {"ronda_prazo": {"ronda": "compras", "dias": 999}})[0], 400)
        st, e = self.j("/api/config", {"ronda_prazo": {"ronda": "compras", "dias": 7}})
        self.assertEqual((st, e["rondas"]["prazos"], e["rondas"]["avisar_dias"]), (200, {"casa": 30, "compras": 7}, 30))
        atras = S.conferir_rondas()
        self.assertEqual([(a["ronda"], a["onde"], a["dias"], a["prazo"]) for a in atras], [("compras", "", None, 7)], "nunca feita, com o aviso ligado")
        self.assertEqual(S.texto_do_aviso(atras), "Ronda de compras: ainda não foi feita.")
        self.assertEqual(self.j("/api/estado")[1]["rondas"]["atrasados"], ["Ronda de compras"])
        self.assertEqual(self.j("/api/estado")[1]["rondas"]["atrasados_de"], [{"ronda": "compras", "onde": ""}])
        for rid, onde, dias in (("compras", "", 9), ("casa", "Sala", 40), ("casa", "Cozinha", 2)):
            with mock.patch.object(S, "agora_iso", lambda d=dias: (datetime.now() - timedelta(days=d)).isoformat(timespec="seconds")):
                S.anotar_ronda(rid, onde, {"nome": "Ana"}, 3)
        atras = S.conferir_rondas()
        self.assertEqual([(a["ronda"], a["onde"]) for a in atras], [("casa", "Sala"), ("compras", "")])
        self.assertEqual(S.texto_do_aviso(atras), "Sala está sem ronda há mais de 30 dias. Ronda de compras: sem fazer há mais de 7 dias.")
        self.assertEqual(S._titulo_do_aviso(atras), "Rondas")
        r = self.j("/api/rondas")[1]
        self.assertEqual((r["ultimas_de"], r["prazos"]), ({"casa": {"Sala": 40, "Cozinha": 2}, "compras": {"": 9}}, {"casa": 30, "compras": 7}))
        # o prazo de antes (ronda_dias) continua valendo como o da Ronda da casa; 0 desliga só a dela
        self.assertEqual(self.j("/api/config", {"ronda_dias": 0})[1]["rondas"]["prazos"], {"casa": 0, "compras": 7})
        self.assertEqual([(a["ronda"], a["onde"]) for a in S.conferir_rondas()], [("compras", "")])
        self.assertEqual(self.j("/api/config", {"ronda_prazo": {"ronda": "compras", "dias": 0}})[1]["rondas"]["atrasados"], [])

    def test_avisa_uma_vez_por_dia_no_horario(self):
        from datetime import datetime
        self.casa()
        self.ha()
        self.atrasar("Sala", 40)
        self.atrasar("Cozinha", 2)
        S.salvar_config({"ronda_hora": "09:30", "ronda_para": ["person.ana", "person.caio"]})
        self.idos.clear()
        hoje = datetime.now().replace(hour=9, minute=0)
        self.assertIsNone(S.avisar_rondas(hoje), "antes do horário, nada")
        self.assertEqual(self.avisos_idos(), [])
        self.assertEqual(S.avisar_rondas(hoje.replace(minute=30)), 1)
        self.assertEqual(self.avisos_idos(), [("/services/notify/mobile_app_moto_g_exemplo", {
            "title": "CorrerIA · 🧭 Ronda da casa", "message": "Sala está sem ronda há mais de 30 dias.",
            "data": {"tag": "correria-ronda", "group": "correria-rondas", "channel": "Rondas", "notification_icon": "mdi:lightning-bolt",
                     "url": "/app/abc_correria", "clickAction": "/app/abc_correria"}})], "só para os celulares de quem recebe")
        self.assertIsNone(S.avisar_rondas(hoje.replace(hour=15)), "uma vez por dia")
        S.ESTADO["ronda_avisado"] = None  # o app reiniciou: o arquivo lembra
        self.assertIsNone(S.avisar_rondas(hoje.replace(hour=16)))
        self.assertEqual(len(self.avisos_idos()), 1)
        self.assertEqual([x["onde"] for x in S.historico_rondas()], ["Sala", "Cozinha"], "o histórico continua no arquivo")
        S.anotar_ronda("casa", "Sala", {"nome": "Ana"}, 10)
        self.assertEqual(S.ler_json(S.RONDAS_ARQ)["avisado"], hoje.strftime("%Y-%m-%d"), "e anotar uma ronda não esquece o aviso do dia")

    def test_sem_atrasado_sem_quem_recebe_ou_desligado_nao_avisa(self):
        from datetime import datetime
        self.casa()
        self.ha()
        meio_dia = datetime.now().replace(hour=12, minute=0)
        S.salvar_config({"ronda_para": ["person.ana"]})
        self.assertEqual(S.avisar_rondas(meio_dia), 0, "nenhum cômodo atrasado")
        S.ESTADO["ronda_avisado"] = None
        os.remove(S.RONDAS_ARQ)
        self.atrasar()
        S.salvar_config({"ronda_para": []})
        self.assertIsNone(S.avisar_rondas(meio_dia), "ninguém recebe")
        S.salvar_config({"ronda_para": ["person.ana"], "ronda_dias": 0})
        self.assertIsNone(S.avisar_rondas(meio_dia), "aviso desligado")
        self.assertEqual(self.avisos_idos(), [])

    def test_testar_no_meu_celular(self):
        self.ha()
        self.assertEqual(self.j("/api/ronda/testar", {}), (200, {"ok": True, "celulares": 1}))
        c, x = self.avisos_idos()[-1]
        self.assertEqual((c, x["title"], x["data"]["tag"]), ("/services/notify/mobile_app_moto_g_exemplo", "CorrerIA · 🧭 Ronda da casa", "correria-ronda-teste"))
        self.CAB = dict(self.CAB, **{"X-Remote-User-Id": "u-caio"})
        self.assertEqual(self.j("/api/ronda/testar", {}), (400, {"erro": "Sem celular ligado a você no Home Assistant."}))
        self.CAB = dict(self.CAB, **{"X-Remote-User-Id": "u-ninguem"})
        self.assertEqual(self.j("/api/ronda/testar", {}), (400, {"erro": "Você não é uma pessoa da casa no Home Assistant."}))

    def test_o_home_assistant_recusa(self):
        self.ha(recusa=("/notify/",))
        self.assertEqual(self.j("/api/ronda/testar", {}), (400, {"erro": "O Home Assistant não aceitou o aviso."}))
        with mock.patch.object(S, "ha_get", mock.Mock(side_effect=OSError("fora"))):
            S._celulares_cache.update(t=0, v=None)
            self.assertEqual(S.pessoas_do_aviso("u-ana"), {"erro": "Não consegui ver as pessoas da casa."})


if __name__ == "__main__":
    unittest.main()
