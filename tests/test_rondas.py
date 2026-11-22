"""Rondas (1.18.0): o roteiro fixo pelos apps dentro da Conversa da tela. Apps de mentira (ResolvIA, InventarIA, EconomIA)
e a IA simulada; a casa é inventada (Sala, Cozinha)."""
import json
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
        self.assertEqual(ab("casa", "feita", "Área de serviço"), {"texto": "Abrir no ResolvIA", "href": "/app/x_resolvia?aba=buscar&comodo=%C3%81rea%20de%20servi%C3%A7o"})
        self.assertEqual(ab("casa", "rotina_nova", "Sala")["href"], "/app/x_cronologia?aba=rotinas")
        self.assertEqual(ab("casa", "mercado", "Sala")["href"], "/app/x_economia")
        self.assertEqual(ab("mes", "tarefas", "")["href"], "/app/x_resolvia?aba=prazos")
        self.assertEqual(ab("mes", "agenda", "")["href"], "/app/x_cronologia?aba=calendario")
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
        self.assertEqual(m["abrir"], {"texto": "Abrir no ResolvIA", "href": "/app/x_resolvia?aba=buscar&comodo=Sala"})
        self.assertIn("- Regar a planta\n- e mais 3", m["texto"])
        for _ in range(2):  # Tarefas: Nova (ResolvIA, com link) e Itens (InventarIA, sem o endereço: sem link)
            st, r = self.j("/api/ronda", {"acao": "proxima"})
        self.assertNotIn("abrir", r["mensagens"][-1])


class TestRondas(Base):
    def test_sem_apps_nenhuma_ronda(self):
        self.assertEqual(self.j("/api/rondas"), (200, {"ativa": None, "feitos": [], "ultimas": {}, "avisar_dias": 30, "rondas": [], "atrasados": [], "aviso": {"pessoas": []}}))
        self.assertIn("não está disponível", self.j("/api/ronda", {"acao": "iniciar", "ronda": "nada", "onde": "Sala"})[1]["erro"])
        st, r = self.j("/api/ronda", {"acao": "iniciar", "ronda": "casa", "onde": "Sala"})
        self.assertEqual(st, 400)
        self.assertIn("não está disponível", r["erro"])
        self.assertEqual(self.j("/api/ronda", {"acao": "proxima"})[1]["erro"], "Nenhuma ronda em andamento.")

    def test_as_etapas_seguem_o_que_esta_ligado(self):
        self.casa()
        r = self.j("/api/rondas")[1]["rondas"]
        self.assertEqual([(x["id"], x["nome"], x["onde"], x["livre"], x["sem_onde"]) for x in r],
                         [("casa", "Ronda da casa", ["Sala", "Cozinha"], False, False), ("compras", "Ronda de compras", [], False, True), ("mes", "Ronda do mês", [], False, True)],
                         "a da chegada pede o Anotar compra do EconomIA, que esta casa de teste não tem")
        self.assertEqual([(e["id"], e["grupo"], e["app"]) for e in r[0]["etapas"]],
                         [("feita", "Tarefas", "ResolvIA"), ("arrumar", "Tarefas", "ResolvIA"),
                          ("item_novo", "Itens", "InventarIA"), ("item_saiu", "Itens", "InventarIA"), ("item_mudou", "Itens", "InventarIA"),
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
        self.assertEqual([e["id"] for e in self.j("/api/rondas")[1]["rondas"][0]["etapas"]], ["feita", "arrumar", "item_novo", "item_saiu", "item_mudou", "mercado", "farmacia", "pet"])

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
        self.assertEqual(r["ronda"]["ativa"], {"id": "casa", "nome": "Ronda da casa", "onde": "Sala", "n": 1, "total": 10, "etapa": "Concluir", "grupo": "Tarefas", "app": "ResolvIA"})
        eu, ia_ = r["mensagens"][-2:]
        self.assertEqual((eu["papel"], eu["texto"], eu["ronda"]), ("eu", "Sala · Tarefas: Concluir (1 de 10)", True), "a pessoa vê só o rótulo, não o pedido")
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
        self.assertEqual((r["ronda"]["ativa"]["etapa"], r["mensagens"][-2]["texto"]), ("Nova", "Sala · Tarefas: Nova (2 de 10)"))
        self.assertEqual((r["mensagens"][-1]["texto"], r["mensagens"][-1]["app"]), ("*Tem algo novo para arrumar?*", "ResolvIA"))
        self.assertEqual(len(self.resolvia.feitos), n, "sem chamar o app")
        r = self.j("/api/ronda", {"acao": "voltar"})[1]
        self.assertEqual(r["ronda"]["ativa"]["n"], 1)
        self.assertEqual(self.j("/api/ronda", {"acao": "voltar"})[1]["ronda"]["ativa"]["n"], 1, "na primeira, fica")
        fins = {"Nova": "Tem algo novo para arrumar?", "Novo": "Chegou algum item novo?", "Descartado": "Algum item foi descartado?",
                "Transferido": "Algum item foi transferido de cômodo?", "Acabando": "Algum desses consumíveis precisa repor?", "Consumível novo": "Quer adicionar algum consumível?",
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
        self.assertEqual(([e["id"] for e in r["etapas"]], r["livre"]), (["item_novo", "item_saiu", "item_mudou"], True))
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
                                                                  ("rotina_sai", "Rotinas"), ("item_novo", "Itens")])
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
        self.assertEqual((r["ronda"]["ativa"]["etapa"], r["ronda"]["ativa"]["n"], r["ronda"]["ativa"]["total"]), ("Nova", 1, 9))
        self.assertEqual(r["mensagens"][-1]["texto"], "Pelo que vi:\nNenhuma tarefa.\n\n*Tem algo novo para arrumar?*")
        self.assertEqual(r["mensagens"][-2]["texto"], "Sala · Tarefas: Nova (1 de 9)")
        self.assertNotIn("TOTAL", r["mensagens"][-1]["texto"])
        vistos = []
        while True:
            r = self.j("/api/ronda", {"acao": "proxima"})[1]
            if not r["ronda"]["ativa"]:
                break
            vistos.append((r["ronda"]["ativa"]["grupo"], r["ronda"]["ativa"]["etapa"], r["ronda"]["ativa"]["total"], r["mensagens"][-1]["texto"].split("\n")[-1]))
        self.assertEqual(vistos, [("Rotinas", "Nova", 7, "*Falta alguma rotina?*"),            # sem rotinas: sem o Mudar e o Tirar
                                  ("Itens", "Novo", 5, "*Chegou algum item novo?*"),          # sem itens: sem o Descartado e o Transferido
                                  ("Consumíveis", "Novo", 4, "*Quer adicionar algum consumível?*")])  # nenhum acabando: direto o adicionar
        self.assertIn("0 itens.", r["mensagens"][-3]["texto"])
        self.assertEqual(r["mensagens"][-4]["texto"], "Sala · Consumíveis: Novo (4 de 4)", "o rótulo com a conta do que ficou")
        self.assertEqual(S.historico_rondas()[-1]["perguntas"], 4)
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
        self.assertEqual(list(L), ["casa", "compras", "chegada", "mes"])
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
        self.assertEqual(S.conferir_rondas(), [{"onde": "Sala", "dias": 31}])
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
        self.assertEqual(S.conferir_rondas(), [{"onde": "Cozinha", "dias": None}], "depois da primeira ronda da casa, o que nunca teve conta")

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
