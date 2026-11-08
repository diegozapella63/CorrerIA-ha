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
        self.assertEqual(self.f.instrucoes(), "- CronologIA (um assunto): CronologIA: dicas.")

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
