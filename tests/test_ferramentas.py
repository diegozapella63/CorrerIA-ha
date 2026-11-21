"""ferramentas.py: as ferramentas de todos os apps juntas, com o app na frente do nome; um app que só responde com a IA
dele vira <app>_perguntar. Apps de mentira (AppFalso)."""
import unittest

from tests.base import AppFalso, ServidorFalso, pasta_temp
import apps as A
import ferramentas as F


class TestFerramentas(unittest.TestCase):
    def setUp(self):
        self.share = pasta_temp()
        self.f = F.Ferramentas(A.Apps(self.share, print, cache=0), print)
        self.cron = AppFalso("CronologIA")
        self.addCleanup(self.cron.fechar)
        self.cron.publicar(self.share, "cronologia")

    def test_todas_com_o_app_na_frente(self):
        ids = [x["id"] for x in self.f.todas()]
        self.assertEqual(ids, ["cronologia_resumo", "cronologia_lancar", "cronologia_apagar"])
        linhas = self.f.instrucoes().split("\n")
        self.assertEqual(linhas[0], "- CronologIA (um assunto): CronologIA: dicas.")
        # 1.16.0: o contexto todo da família: os que estão com a integração desligada (com o assunto) e o que dizer deles
        self.assertEqual(len(linhas), 3)
        self.assertTrue(linhas[1].startswith("Apps da família com a integração desligada (você não vê nem muda os dados deles): EconomIA (compras da casa:"), linhas[1])
        for nome in ("GerencIA (finanças da casa:", "InventarIA (inventário da casa:", "MemorIA (anotações em blocos", "ResolvIA (listas de tarefas da casa:"):
            self.assertIn(nome, linhas[1])
        self.assertNotIn("CronologIA (", linhas[1], "o ligado não está entre os desligados")
        self.assertIn("diga que a integração dele com o CorrerIA está desligada e que ela liga no próprio app, em Mais › Configurações › Integrações › CorrerIA. Não procure isso nos outros apps.", linhas[1])
        self.assertIn("O nome de um app na pergunta, mesmo em minúsculas, sem acento ou pela metade (resolvia, memória", linhas[2])
        self.assertIn('Para "o que tem no <app>", comece pela ferramenta de resumo ou de lista dele.', linhas[2])

    def test_instrucoes_um_app_ligado_que_nao_responde(self):
        self.cron.chave = "outra"  # o app recusa a chave
        self.f.apps._ferr.clear()
        t = self.f.instrucoes()
        self.assertIn("Ligados, mas sem responder agora (se perguntarem por eles, diga isso): CronologIA.", t)
        self.assertNotIn("- CronologIA", t)

    def test_instrucoes_sem_nenhum_app_ligado(self):
        import shutil
        shutil.rmtree(self.share + "/cronologia")
        t = self.f.instrucoes()
        self.assertTrue(t.startswith("Apps da família com a integração desligada"), t[:80])
        self.assertIn("CronologIA (agenda da família:", t)
        self.assertEqual(F.Ferramentas(type("SemFamilia", (), {"lista": lambda s: []})(), print).instrucoes(), "", "uns apps de teste sem a família: nada")

    def test_app_so_com_a_ia_dele_vira_perguntar(self):
        g = ServidorFalso({"/api/integracao/conversa": lambda h, c: (200, {"resposta": f"Resposta: {c['texto']} ({c['canal']})"})})
        self.addCleanup(g.fechar)
        import json, os
        os.makedirs(os.path.join(self.share, "gerencia"))
        with open(os.path.join(self.share, "gerencia", "correria.json"), "w") as fh:
            json.dump({"app": "gerencia", "nome": "GerencIA", "assunto": "finanças", "rota": "/api/integracao/conversa", "url": g.url, "chave": "k" * 30}, fh)
        todas = self.f.todas()
        p = self.f.achar("gerencia_perguntar", todas)
        self.assertEqual((p["grava"], p["entrada"]["required"]), (False, ["pergunta"]))
        self.assertEqual(self.f.usar(p, {"pergunta": "Quanto gastei?"}, {"nome": "Ana"}, "Claude"), ("Resposta: Quanto gastei? (correria)", False))
        self.assertIn("- GerencIA (finanças)", self.f.instrucoes())

    def test_usar_e_erros(self):
        lancar = self.f.achar("cronologia_lancar")
        self.assertEqual(self.f.usar(lancar, {"descricao": "X"}, {}, "Claude"), ("Falta o valor.", True))
        texto, erro = self.f.usar(lancar, {"descricao": "X", "valor": 2}, {}, "Claude")
        self.assertFalse(erro)
        self.assertIsNone(self.f.achar("cronologia_sacar"))
        self.cron.fechar()
        self.assertEqual(len(self.f.todas()), 3, "a lista fica guardada por um minuto")
        self.assertEqual(self.f.usar(lancar, {"valor": 1}, {}, "Claude")[1], True, "mas chamar dá erro")
        self.f.apps._ferr.clear()
        self.assertEqual(self.f.todas(), [], "o app fora do ar sai da lista")
        self.assertIn("cronologia", self.f.erros)

    def test_resumo_args(self):
        self.assertEqual(F.resumo_args({"valor": 10, "pago": True, "cartao": False, "obs": "", "x": None}), "valor: 10, pago, sem cartao")


if __name__ == "__main__":
    unittest.main()
