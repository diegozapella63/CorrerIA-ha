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


class TestRondas(Base):
    def test_sem_apps_nenhuma_ronda(self):
        self.assertEqual(self.j("/api/rondas"), (200, {"ativa": None, "feitos": [], "ultimas": {}, "avisar_dias": 30, "rondas": [], "atrasados": []}))
        st, r = self.j("/api/ronda", {"acao": "iniciar", "ronda": "casa", "onde": "Sala"})
        self.assertEqual(st, 400)
        self.assertIn("não está disponível", r["erro"])
        self.assertEqual(self.j("/api/ronda", {"acao": "proxima"})[1]["erro"], "Nenhuma ronda em andamento.")

    def test_as_etapas_seguem_o_que_esta_ligado(self):
        self.casa()
        r = self.j("/api/rondas")[1]["rondas"]
        self.assertEqual([(x["id"], x["nome"], x["onde"], x["livre"]) for x in r], [("casa", "Ronda da casa", ["Sala", "Cozinha"], False)])
        self.assertEqual([(e["id"], e["grupo"], e["app"]) for e in r[0]["etapas"]],
                         [("arrumar", "Tarefas", "ResolvIA"), ("tarefa", "Tarefas", "ResolvIA"),
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
                self.assertTrue(primeira["pedido"], "a primeira de cada grupo lê o app")

    def test_o_texto_da_etapa_vem_arrumado(self):
        """O dono: "Não seria legal trazer mais organizado o texto?" A lista numa linha só vira uma linha por item, a
        pergunta que a IA repetiu (entre «») sai, e a pergunta da etapa vem no fim, à parte, em negrito."""
        a = rondas.arrumar("No Quarto, temos 2 tarefas pendentes: - Tapar buracos da parede - Passar tíner no armário. Nenhuma delas tem prazo definido. "
                           "«Tem algo para arrumar em Quarto?»", "casa", "arrumar", "Quarto")
        self.assertEqual(a, "No Quarto, temos 2 tarefas pendentes:\n\n- Tapar buracos da parede\n- Passar tíner no armário\n\nNenhuma delas tem prazo definido.\n\n"
                            "*Tem algo para arrumar em Quarto?*")
        self.assertEqual(rondas.arrumar("Há 3 itens. Os últimos: Mesa e Abajur. Chegou algum item novo em Sala?", "casa", "item_novo", "Sala"),
                         "Há 3 itens. Os últimos: Mesa e Abajur.\n\n*Chegou algum item novo em Sala?*")
        self.assertEqual(rondas.arrumar("Há 2.\r\n- Um\n- Dois\n\n\n\nFim.", "casa", "arrumar", "Sala"), "Há 2.\n\n- Um\n- Dois\n\nFim.\n\n*Tem algo para arrumar em Sala?*")
        self.assertEqual(rondas.arrumar(None, "casa", "pet", "Sala"), "*Precisa de algo do pet shop para Sala?*")
        p = rondas.pedido("casa", "arrumar", "Sala", [], 1, 10)
        self.assertIn("NÃO faça pergunta nenhuma", p)
        self.assertIn("um por linha", p)

    def test_sem_os_consumiveis_no_inventaria_sem_a_etapa(self):
        self.casa(consumiveis=False)
        self.assertEqual([e["id"] for e in self.j("/api/rondas")[1]["rondas"][0]["etapas"]], ["arrumar", "tarefa", "item_novo", "item_saiu", "item_mudou", "mercado", "farmacia", "pet"])

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
        self.assertEqual(r["ronda"]["ativa"], {"id": "casa", "nome": "Ronda da casa", "onde": "Sala", "n": 1, "total": 10, "etapa": "Arrumar", "grupo": "Tarefas", "app": "ResolvIA"})
        eu, ia_ = r["mensagens"][-2:]
        self.assertEqual((eu["papel"], eu["texto"], eu["ronda"]), ("eu", "Ronda da casa · Sala · Tarefas: Arrumar (1 de 10)", True), "a pessoa vê só o rótulo, não o pedido")
        self.assertIn("Trocar a lâmpada", ia_["texto"])
        self.assertTrue(ia_["texto"].endswith("\n\n*Tem algo para arrumar em Sala?*"), ia_["texto"])
        self.assertEqual(self.resolvia.feitos[-1]["argumentos"], {"comodo": "Sala"}, "o ResolvIA com os cômodos: filtra")
        self.assertEqual(self.j("/api/conversa")[1]["ronda"]["ativa"]["n"], 1, "a conversa leva a ronda em andamento")
        # uma resposta da pessoa segue pela conversa de sempre, e a ronda continua
        visto = []
        real = S.AGENTE.responder
        with mock.patch.object(S.AGENTE, "responder", lambda h, *a, **k: (visto.append(h), real(h, *a, **k))[1]):
            st, r = self.j("/api/conversa", {"texto": "nada"})
        self.assertEqual(r["ronda"]["ativa"]["etapa"], "Arrumar")
        self.assertIn("etapa Arrumar", visto[0][-2]["texto"], "a IA sabe de que etapa é a resposta")
        self.assertIn("ResolvIA", visto[0][-2]["texto"])
        self.assertEqual((visto[0][-1]["texto"], r["mensagens"][-2]["texto"]), ("nada", "nada"), "na conversa, só o que a pessoa escreveu")
        n = len(self.resolvia.feitos)
        r = self.j("/api/ronda", {"acao": "proxima"})[1]  # a segunda do grupo: só a pergunta, sem ler de novo
        self.assertEqual((r["ronda"]["ativa"]["etapa"], r["mensagens"][-2]["texto"]), ("Outra tarefa", "Ronda da casa · Sala · Tarefas: Outra tarefa (2 de 10)"))
        self.assertEqual((r["mensagens"][-1]["texto"], r["mensagens"][-1]["app"]), ("*Alguma outra tarefa para Sala?*", "ResolvIA"))
        self.assertEqual(len(self.resolvia.feitos), n, "sem chamar o app")
        r = self.j("/api/ronda", {"acao": "voltar"})[1]
        self.assertEqual(r["ronda"]["ativa"]["n"], 1)
        self.assertEqual(self.j("/api/ronda", {"acao": "voltar"})[1]["ronda"]["ativa"]["n"], 1, "na primeira, fica")
        fins = {"Outra tarefa": "Alguma outra tarefa para Sala?", "Item novo": "Chegou algum item novo em Sala?", "Item que saiu": "Algum item saiu de Sala?",
                "Item que mudou": "Algum item de Sala mudou?", "Acabando": "Algum consumível de Sala está acabando?", "Consumível novo": "Algum consumível novo em Sala?",
                "Mercado": "Precisa de algo do mercado para Sala?", "Farmácia": "Precisa de algo da farmácia para Sala?", "Pet shop": "Precisa de algo do pet shop para Sala?"}
        for etapa, fim in fins.items():
            r = self.j("/api/ronda", {"acao": "proxima"})[1]
            self.assertEqual(r["ronda"]["ativa"]["etapa"], etapa)
            self.assertTrue(r["mensagens"][-1]["texto"].endswith(f"*{fim}*"), r["mensagens"][-1]["texto"])
            if etapa == "Item novo":
                self.assertEqual(self.inventario.feitos[-1]["argumentos"], {"comodo": "Sala"})
            if etapa == "Acabando":
                self.assertEqual(self.inventario.feitos[-1]["argumentos"], {"comodo": "Consumíveis"}, "os consumíveis não têm cômodo: a área deles")
            if etapa == "Mercado":
                self.assertIn("Café", r["mensagens"][-1]["texto"])
        r = self.j("/api/ronda", {"acao": "proxima"})[1]  # a última: concluída, e a escolha do próximo cômodo
        self.assertIsNone(r["ronda"]["ativa"])
        self.assertEqual((r["ronda"]["feitos"], r["ronda"]["rondas"][0]["onde"]), (["Sala"], ["Sala", "Cozinha"]))
        self.assertEqual([m["texto"] for m in r["mensagens"][-2:]], ["Ronda da casa · Sala · concluída", "Ronda de Sala concluída. Quando quiser, escolha o próximo cômodo."])
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
        p = rondas.pedido("casa", "arrumar", "Sala", S.FERR.todas(), 1, 4)
        self.assertIn("não filtra por cômodo", p)
        self.assertNotIn("o campo comodo", p)

    def test_sem_a_ia_avisa(self):
        self.casa()
        with mock.patch.object(S, "responder_ia", lambda *a, **k: None):
            r = self.j("/api/ronda", {"acao": "iniciar", "ronda": "casa", "onde": "Sala"})[1]
        self.assertEqual(r["mensagens"][-1]["texto"], "*Tem algo para arrumar em Sala?*", "sem a IA, a pergunta sai do mesmo jeito")

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


if __name__ == "__main__":
    unittest.main()
