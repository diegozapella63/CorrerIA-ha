"""ia.py: a IA do WhatsApp e da conversa da tela com as ferramentas dos apps: lê (chama e responde com os resultados),
propõe as mudanças (o sim fica com o server.py), erra o nome de uma ferramenta, responde só texto. A IA é de mentira:
devolve as respostas da fila e guarda os pedidos."""
import unittest
from datetime import datetime

from tests.base import AppFalso, pasta_temp
import apps as A
import ferramentas as F
import ia as I

ANA = {"id": "person.ana", "nome": "Ana"}
AGORA = datetime(2026, 11, 8, 9, 30)


class IAFalsa:
    def __init__(self, *respostas):
        self.fila, self.pedidos = list(respostas), []

    def __call__(self, instrucoes):
        self.pedidos.append(instrucoes)
        return self.fila.pop(0)


class TestAgente(unittest.TestCase):
    def setUp(self):
        self.share = pasta_temp()
        self.app = AppFalso("GerencIA")
        self.addCleanup(self.app.fechar)
        self.app.publicar(self.share, "gerencia")
        self.ferr = F.Ferramentas(A.Apps(self.share, print, cache=0), print)

    def agente(self, *respostas):
        self.ia = IAFalsa(*respostas)
        return I.Agente(self.ferr, self.ia, print)

    def hist(self, texto):
        return [{"papel": "eu", "texto": "oi"}, {"papel": "ia", "texto": "Oi, Ana!"}, {"papel": "eu", "texto": texto}]

    def test_le_e_responde(self):
        ag = self.agente({"chamar": [{"ferramenta": "gerencia_resumo", "argumentos": {}}], "resposta": ""},
                         '```json\n{"chamar": [], "resposta": "Você tem *3 contas*."}\n```')
        r = ag.responder(self.hist("O que vence?"), ANA, "whatsapp", "WhatsApp", AGORA)
        self.assertEqual(r, {"resposta": "Você tem *3 contas*.", "pendente": [], "apps": ["GerencIA"]})
        p1, p2 = self.ia.pedidos
        self.assertIn("pelo WhatsApp. Quem está conversando: Ana. Agora: domingo, 08/11/2026 09:30.", p1)
        self.assertIn("pelo WhatsApp você ajuda só com os apps da CorrerIA Code", p1, "a regra da Meta")
        self.assertIn("gerencia_lancar | grava | GerencIA: Lança um gasto.", p1)
        self.assertIn("- GerencIA (um assunto): GerencIA: dicas.", p1)
        self.assertIn("Pessoa: oi\nIA: Oi, Ana!\nPessoa: O que vence?", p1)
        self.assertIn("gerencia_resumo({}) → Hoje no GerencIA: 3 contas, R$ 120,00.", p2, "o resultado volta para a IA")
        self.assertEqual(self.app.feitos[0]["cliente"], "WhatsApp")

    def test_mudar_fica_para_o_sim(self):
        ag = self.agente({"chamar": [{"ferramenta": "gerencia_lancar", "argumentos": {"descricao": "Feira", "valor": 32.5},
                                      "resumo": "Lançar R$ 32,50 de Feira hoje"}], "resposta": "Certo."})
        r = ag.responder(self.hist("lança 32,50 de feira"), ANA, "correria", "CorrerIA", AGORA)
        self.assertEqual(r["resposta"], "Certo.\n\nVou fazer isto:\n- Lançar R$ 32,50 de Feira hoje\n\nResponda *sim* para confirmar.")
        self.assertEqual(r["pendente"], [{"ferramenta": "gerencia_lancar", "argumentos": {"descricao": "Feira", "valor": 32.5},
                                          "resumo": "Lançar R$ 32,50 de Feira hoje", "app": "GerencIA"}])
        self.assertEqual(self.app.feitos, [], "nada gravado antes do sim")
        self.assertIn("na tela do app CorrerIA", self.ia.pedidos[0])
        self.assertIn("também pode conversar sobre outros assuntos", self.ia.pedidos[0])

    def test_sem_resumo_monta_um(self):
        ag = self.agente({"chamar": [{"ferramenta": "gerencia_apagar", "argumentos": {"id": "l1"}}, {"ferramenta": "gerencia_lancar", "argumentos": {"valor": 1}}]})
        r = ag.responder(self.hist("apaga e lança"), ANA, "whatsapp", "WhatsApp", AGORA)
        self.assertEqual([p["resumo"] for p in r["pendente"]], ["Apagar: id: l1", "Lançar gasto: valor: 1"])
        self.assertIn("Vou fazer isto tudo:", r["resposta"])

    def test_ferramenta_que_nao_existe_e_erro_do_app(self):
        ag = self.agente({"chamar": [{"ferramenta": "gerencia_sacar"}, {"ferramenta": "gerencia_resumo"}]}, {"resposta": "Pronto."})
        self.assertEqual(ag.responder(self.hist("?"), ANA, agora=AGORA)["resposta"], "Pronto.")
        self.assertIn("gerencia_sacar → ERRO: essa ferramenta não existe", self.ia.pedidos[1])
        self.app.chave = "outra"
        self.ferr.apps._ferr.clear()
        ag = self.agente({"resposta": "Sem apps."})
        self.assertEqual(ag.responder(self.hist("?"), ANA, agora=AGORA)["resposta"], "Sem apps.")

    def test_so_texto_e_rodadas_demais(self):
        ag = self.agente("Oi! Tudo bem por aqui.")
        self.assertEqual(ag.responder(self.hist("oi"), ANA, agora=AGORA)["resposta"], "Oi! Tudo bem por aqui.")
        ler = {"chamar": [{"ferramenta": "gerencia_resumo"}]}
        ag = self.agente(ler, ler, ler, ler)
        r = ag.responder(self.hist("?"), ANA, agora=AGORA)
        self.assertEqual(r["resposta"], "Não consegui responder agora. Pode perguntar de outro jeito?")
        self.assertEqual(len(self.ia.pedidos), 4)
        self.assertIn("Agora responda com o que já tem", self.ia.pedidos[-1])

    def test_extrair_json(self):
        self.assertEqual(I.extrair_json('Claro! {"resposta": "x"} tchau'), {"resposta": "x"})
        self.assertEqual(I.extrair_json("só texto"), {"resposta": "só texto"})
        self.assertEqual(I.extrair_json({"a": 1}), {"a": 1})
        self.assertEqual(I.extrair_json("[1, 2]"), {"resposta": "[1, 2]"})

    def test_simulada(self):
        ag = I.Agente(self.ferr, None, print, simulada=True)
        r = ag.responder([{"papel": "eu", "texto": "lança 25 de padaria"}], ANA, agora=AGORA)
        self.assertEqual(r["pendente"][0]["argumentos"], {"tipo": "despesa", "descricao": "Padaria", "valor": 25.0})
        r = ag.responder([{"papel": "eu", "texto": "o que vence?"}], ANA, agora=AGORA)
        self.assertEqual(r["resposta"], "Pelo que vi:\nHoje no GerencIA: 3 contas, R$ 120,00.")
        self.assertIn("IA simulada", ag.responder([{"papel": "eu", "texto": "bom dia"}], ANA, agora=AGORA)["resposta"])


if __name__ == "__main__":
    unittest.main()
