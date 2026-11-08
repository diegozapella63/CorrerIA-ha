"""apps.py: achar os apps da família (share/<app>/correria.json), escolher o app da pergunta e perguntar."""
import json
import os
import unittest

from tests.base import ServidorFalso, pasta_temp, porta_livre
import apps as A


def publicar(share, app, url, nome=None, assunto="", ip_url=None, chave="chave-de-teste-" + "x" * 20, anexos=None):
    os.makedirs(os.path.join(share, app), exist_ok=True)
    with open(os.path.join(share, app, "correria.json"), "w", encoding="utf-8") as f:
        json.dump({"app": app, "nome": nome or app.title(), "assunto": assunto, "rota": "/api/integracao/conversa",
                   "url": url, "ip_url": ip_url, "chave": chave, "versao": "1.37.0", **({"anexos": anexos} if anexos is not None else {})}, f)


class TestLista(unittest.TestCase):
    def setUp(self):
        self.share, self.reg = pasta_temp(), []
        self.a = A.Apps(self.share, lambda *x: self.reg.append(x), cache=0)

    def test_acha_os_arquivos(self):
        publicar(self.share, "gerencia", "http://gerencia:8099/", "GerencIA", "finanças da casa", "http://172.30.33.5:8099")
        os.makedirs(os.path.join(self.share, "estragado"))
        with open(os.path.join(self.share, "estragado", "correria.json"), "w") as f:
            f.write("{não é json")
        os.makedirs(os.path.join(self.share, "incompleto"))
        with open(os.path.join(self.share, "incompleto", "correria.json"), "w") as f:
            json.dump({"url": "http://x"}, f)  # sem chave
        os.makedirs(os.path.join(self.share, "outro"))  # sem arquivo
        lista = self.a.lista()
        self.assertEqual([(x["app"], x["nome"], x["url"], x["ip_url"]) for x in lista], [("gerencia", "GerencIA", "http://gerencia:8099", "http://172.30.33.5:8099")])
        self.assertEqual(len(self.reg), 1, "o estragado vai para o registro")
        self.assertEqual(self.a.publicos(), [{"app": "gerencia", "nome": "GerencIA", "assunto": "finanças da casa", "versao": "1.37.0", "anexos": []}], "sem a chave")

    def test_guarda_por_um_tempo(self):
        a = A.Apps(self.share, print, cache=60)
        self.assertEqual(a.lista(), [])
        publicar(self.share, "gerencia", "http://g")
        self.assertEqual(a.lista(), [], "ainda o de antes")
        self.assertEqual(len(a.lista(forcar=True)), 1)

    def test_escolher(self):
        self.assertIsNone(self.a.escolher("oi"))
        publicar(self.share, "gerencia", "http://g", "GerencIA", "finanças da casa")
        self.assertEqual(self.a.escolher("qualquer coisa")["app"], "gerencia", "um app só: ele")
        publicar(self.share, "cronologia", "http://c", "CronologIA", "agenda da família")
        self.assertEqual(self.a.escolher("Quanto gastei no mercado?")["app"], "gerencia")
        self.assertEqual(self.a.escolher("Qual o próximo remédio na agenda?")["app"], "cronologia")
        self.assertEqual(self.a.escolher("e amanhã?", ultimo="cronologia")["app"], "cronologia", "sem pista: o da última pergunta")
        self.assertEqual(self.a.escolher("oi")["app"], "cronologia", "sem pista nem última: o primeiro (em ordem)")


class TestAnexos(unittest.TestCase):
    def test_so_os_apps_que_leem_o_tipo(self):
        share = pasta_temp()
        a = A.Apps(share, print, cache=0)
        publicar(share, "gerencia", "http://g", "GerencIA", "finanças", anexos=["image/jpeg", "application/pdf", 3])
        publicar(share, "cronologia", "http://c", "CronologIA", "agenda")
        self.assertEqual(a.lista()[1]["anexos"], ["image/jpeg", "application/pdf"], "só textos")
        self.assertEqual(a.escolher("", tipo="image/jpeg")["app"], "gerencia")
        self.assertEqual(a.escolher("a agenda de amanhã", tipo="application/pdf")["app"], "gerencia", "a agenda não lê PDF")
        self.assertIsNone(a.escolher("", tipo="video/mp4"))
        self.assertEqual(a.escolher("a agenda de amanhã")["app"], "cronologia", "sem anexo, como antes")


class TestPerguntar(unittest.TestCase):
    def setUp(self):
        self.share = pasta_temp()
        self.a = A.Apps(self.share, print, cache=0)
        self.app = ServidorFalso({"/api/integracao/conversa": (200, {"resposta": "Você gastou R$ 123,45."})})
        self.addCleanup(self.app.fechar)

    def test_pergunta_com_a_chave(self):
        publicar(self.share, "gerencia", self.app.url, "GerencIA")
        app = self.a.lista()[0]
        r = self.a.perguntar(app, "Quanto gastei?", [{"papel": "eu", "texto": "oi"}], {"id": "person.ana", "nome": "Ana"})
        self.assertEqual(r, "Você gastou R$ 123,45.")
        m, p, h, c = self.app.pedidos[0]
        self.assertEqual((m, p, h["Authorization"], h["X-App"]), ("POST", "/api/integracao/conversa", "Bearer " + app["chave"], "CorrerIA"))
        self.assertEqual(c, {"texto": "Quanto gastei?", "historico": [{"papel": "eu", "texto": "oi"}], "pessoa": {"id": "person.ana", "nome": "Ana"}})

    def test_com_anexo(self):
        publicar(self.share, "gerencia", self.app.url, "GerencIA")
        anexo = {"tipo": "image/jpeg", "nome": "", "b64": "data:image/jpeg;base64,/9j/"}
        self.a.perguntar(self.a.lista()[0], "quanto deu?", [], {"nome": "Ana"}, anexo=anexo)
        self.assertEqual(self.app.pedidos[0][3]["anexo"], anexo)
        self.a.perguntar(self.a.lista()[0], "oi", [], {})
        self.assertNotIn("anexo", self.app.pedidos[1][3], "sem anexo, nem o campo")

    def test_tenta_o_ip_quando_o_nome_nao_responde(self):
        publicar(self.share, "gerencia", f"http://127.0.0.1:{porta_livre()}", "GerencIA", ip_url=self.app.url)
        self.assertEqual(self.a.perguntar(self.a.lista()[0], "oi", [], {}, timeout=3), "Você gastou R$ 123,45.")

    def test_erros(self):
        publicar(self.share, "gerencia", self.app.url, "GerencIA")
        app = self.a.lista()[0]
        self.app.rotas["/api/integracao/conversa"] = (401, {"erro": "Chave inválida"})
        with self.assertRaisesRegex(A.ErroApp, "O GerencIA recusou a chave"):
            self.a.perguntar(app, "oi", [], {})
        self.app.rotas["/api/integracao/conversa"] = (400, {"erro": "A IA está desligada."})
        with self.assertRaisesRegex(A.ErroApp, "^A IA está desligada.$"):
            self.a.perguntar(app, "oi", [], {})
        self.app.rotas["/api/integracao/conversa"] = (500, "pane")
        with self.assertRaisesRegex(A.ErroApp, "O GerencIA respondeu 500."):
            self.a.perguntar(app, "oi", [], {})
        self.app.rotas["/api/integracao/conversa"] = (200, {"resposta": "  "})
        self.assertEqual(self.a.perguntar(app, "oi", [], {}), "Não entendi. Pode dizer de outro jeito?")
        with self.assertRaisesRegex(A.ErroApp, "Não consegui falar com o GerencIA"):
            self.a.perguntar(dict(app, url=f"http://127.0.0.1:{porta_livre()}", ip_url=""), "oi", [], {}, timeout=2)


if __name__ == "__main__":
    unittest.main()
