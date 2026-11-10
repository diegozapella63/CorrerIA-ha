"""Uso da IA (correria/app/uso.py): as chamadas da IA do WhatsApp e da tela, contadas aqui (o Home Assistant não
devolve tokens nem custo), por dia, tipo e resultado; os tokens estimados pelo tamanho do texto."""
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta

from tests.base import importar_servidor
S = importar_servidor()
import uso  # noqa: E402


class Uso(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.mkdtemp(prefix="correria-uso-")
        self.u = uso.Uso(os.path.join(self.pasta, "uso_ia.json"))

    def test_resultado(self):
        self.assertEqual(uso.resultado(None), "ok")
        for m in ("Quota exceeded", "HTTP 429", "RESOURCE_EXHAUSTED", "rate limit", "Too Many Requests", "sem cota"):
            self.assertEqual(uso.resultado(m), "cota", m)
        for m in ("invalid json", "fora do formato", "could not parse"):
            self.assertEqual(uso.resultado(m), "formato", m)
        self.assertEqual(uso.resultado("O Home Assistant respondeu 500."), "erro")

    def test_conta_por_dia_tipo_e_resultado(self):
        hoje = datetime(2026, 11, 10, 9, 30)
        self.u.registrar("whatsapp", 4000, 400, 3.24, agora=hoje)
        self.u.registrar("conversa", 800, 0, 1.0, "HTTP 429", agora=hoje)
        self.u.registrar("conversa", 100, 100, 0.5, "O Home Assistant respondeu 500.", agora=hoje - timedelta(days=2))
        self.u.registrar("whatsapp", 40, 0, 0.1, agora=hoje - timedelta(days=40))
        r = self.u.resumo(hoje.date())
        self.assertEqual({k: r["hoje"][k] for k in ("chamadas", "erros", "cota", "tokens")}, {"chamadas": 2, "erros": 0, "cota": 1, "tokens": 1100 + 200})
        self.assertEqual(r["hoje"]["tipos"], {"whatsapp": 1, "conversa": 1})
        self.assertEqual((r["semana"]["chamadas"], r["semana"]["erros"]), (3, 1))
        self.assertEqual(r["mes"]["chamadas"], 3, "o de 40 dias atrás é de outro mês")
        self.assertEqual([d["chamadas"] for d in r["dias"]], [0, 0, 0, 0, 1, 0, 2])
        self.assertEqual(r["dias"][-1]["dia"], "2026-11-10")
        self.assertEqual([(c["tipo"], c["resultado"]) for c in r["ultimas"][:3]], [("whatsapp", "ok"), ("conversa", "erro"), ("conversa", "cota")])

    def test_guarda_120_dias_e_40_chamadas(self):
        d0 = datetime(2026, 1, 1, 12)
        for i in range(130):
            self.u.registrar("whatsapp", 4, 0, 0, agora=d0 + timedelta(days=i))
        u = self.u.ler()
        self.assertEqual(len(u["dias"]), uso.DIAS)
        self.assertEqual(len(u["ultimas"]), uso.ULTIMAS)
        self.assertEqual(min(u["dias"]), (d0 + timedelta(days=10)).date().isoformat())

    def test_arquivo_estragado(self):
        with open(self.u.arquivo, "w") as f:
            f.write("[1, 2")
        self.assertEqual(self.u.resumo(date(2026, 11, 10))["hoje"]["chamadas"], 0)
        self.u.registrar("conversa", 8, 8, 1, agora=datetime(2026, 11, 10, 8))
        self.assertEqual(self.u.resumo(date(2026, 11, 10))["hoje"]["chamadas"], 1)

    def test_a_ia_conta_o_canal(self):
        """chamar_ia conta cada chamada com o canal da pergunta (o WhatsApp ou a conversa da tela), também as que falham."""
        from unittest import mock
        u = uso.Uso(os.path.join(self.pasta, "s.json"))
        with mock.patch.object(S, "USO", u), mock.patch.object(S, "TOKEN", "x"), \
                mock.patch.object(S, "ha_post", return_value={"service_response": {"data": {"resposta": "oi"}}}):
            S.CANAL.tipo = "whatsapp"
            self.assertEqual(S.chamar_ia("pergunta"), {"resposta": "oi"})
        with mock.patch.object(S, "USO", u), mock.patch.object(S, "TOKEN", "x"), mock.patch.object(S, "ha_post", return_value={}):
            S.CANAL.tipo = "conversa"
            with self.assertRaises(S.ia.ErroIA):
                S.chamar_ia("outra")
        r = u.resumo()
        self.assertEqual(r["hoje"]["tipos"], {"whatsapp": 1, "conversa": 1})
        self.assertEqual(r["hoje"]["erros"], 1)


if __name__ == "__main__":
    unittest.main()
