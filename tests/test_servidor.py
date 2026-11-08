"""server.py: a configuração (o token e a chave nunca voltam para a tela), quem pode conversar, o webhook da Meta (conferir
o endereço, a assinatura, https com o certificado), responder pelo app da família e a tela. A Meta e o GerencIA são de
mentira; pessoas e números inventados (Ana, Beto)."""
import hashlib
import hmac
import json
import os
import shutil
import ssl
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from unittest import mock

from tests.base import importar_servidor, MetaFalsa, ServidorFalso, certificado, pasta_temp, ANA, ANA_WA, BETO
S = importar_servidor()
import apps  # noqa: E402
import whatsapp as W  # noqa: E402
from tests.test_whatsapp import entrega, texto  # noqa: E402

SEGREDO = "segredo-do-app-123"
TOKEN = "EAAtoken-de-teste-0000-1234"


def esperar(cond, s=8):
    fim = time.time() + s
    while time.time() < fim:
        if cond():
            return True
        time.sleep(0.03)
    return False


def pedir(url, metodo="GET", corpo=None, cab=None, contexto=None):
    dados = corpo if isinstance(corpo, bytes) or corpo is None else json.dumps(corpo).encode()
    req = urllib.request.Request(url, data=dados, method=metodo, headers={"Content-Type": "application/json", **(cab or {})})
    try:
        with urllib.request.urlopen(req, timeout=10, context=contexto) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


class Base(unittest.TestCase):
    def setUp(self):
        for arq in (S.CONFIG_ARQ, S.CONVERSAS_ARQ):
            if os.path.exists(arq):
                os.remove(arq)
        shutil.rmtree(S.SHARE_DIR, ignore_errors=True)
        os.makedirs(S.SHARE_DIR)
        S.ESTADO.update(ultimo_webhook=None, verificado_em=None, conta=None, conta_em=None)
        self.meta = MetaFalsa()
        self.addCleanup(self.meta.fechar)
        self.gerencia = ServidorFalso({"/api/integracao/conversa": lambda h, c: (200, {"resposta": f"Resposta para **{c['pessoa']['nome']}**: {c['texto']}"})})
        self.addCleanup(self.gerencia.fechar)
        for alvo, valor in (("GRAPH", self.meta.url), ("APPS", apps.Apps(S.SHARE_DIR, S.log, cache=0))):
            p = mock.patch.object(S, alvo, valor)
            p.start()
            self.addCleanup(p.stop)

    def configurar(self, pessoas=True, app=True):
        S.salvar_config({"numero_id": MetaFalsa.NUMERO_ID, "token": TOKEN, "segredo": SEGREDO, "endereco": "casa-exemplo.duckdns.org:8443"})
        if pessoas:
            S.salvar_pessoa("person.ana", ANA)
            S.salvar_pessoa("person.beto", BETO)
        if app:
            os.makedirs(os.path.join(S.SHARE_DIR, "gerencia"), exist_ok=True)
            with open(os.path.join(S.SHARE_DIR, "gerencia", "correria.json"), "w") as f:
                json.dump({"app": "gerencia", "nome": "GerencIA", "assunto": "finanças", "rota": "/api/integracao/conversa",
                           "url": self.gerencia.url, "chave": "chave-gerencia-" + "x" * 20}, f)

    def registro(self):
        return [(r["tipo"], r["quem"], r["texto"]) for r in S.ler_conversas()["registro"]][::-1]


# ---------------------------------------------------------------------------------------------------------------
class TestConfig(Base):
    def test_token_de_verificacao_criado_uma_vez(self):
        v = S.ler_config()["verificacao"]
        self.assertGreaterEqual(len(v), 16)
        self.assertEqual(S.ler_config()["verificacao"], v)

    def test_salvar_e_o_que_a_tela_ve(self):
        self.configurar(pessoas=False, app=False)
        c = S.ler_config()
        self.assertEqual((c["numero_id"], c["token"], c["segredo"], c["endereco"]), (MetaFalsa.NUMERO_ID, TOKEN, SEGREDO, "https://casa-exemplo.duckdns.org:8443"))
        e = S.estado()["config"]
        self.assertEqual((e["token"], e["segredo"]), ("••••1234", "••••-123"), "a tela só vê o fim")
        self.assertNotIn(TOKEN, json.dumps(S.estado()))
        self.assertNotIn(SEGREDO, json.dumps(S.estado()))
        self.assertEqual(e["webhook"], "https://casa-exemplo.duckdns.org:8443/webhook")
        self.assertTrue(S.estado()["pronto"])
        S.salvar_config({"token": "", "segredo": "  "})
        self.assertEqual((S.ler_config()["token"], S.ler_config()["segredo"]), (TOKEN, SEGREDO), "vazio: fica o que estava")

    def test_validacoes(self):
        with self.assertRaisesRegex(ValueError, "só números"):
            S.salvar_config({"numero_id": "abc"})
        with self.assertRaisesRegex(ValueError, "token parece incompleto"):
            S.salvar_config({"token": "curto"})
        with self.assertRaisesRegex(ValueError, "chave secreta parece incompleta"):
            S.salvar_config({"segredo": "com espaço no meio"})
        with self.assertRaisesRegex(ValueError, "Endereço inválido"):
            S.salvar_config({"endereco": "https:// nada"})
        self.assertEqual(S.limpar_endereco("https://casa-exemplo.duckdns.org:8443/webhook/"), "https://casa-exemplo.duckdns.org:8443")
        self.assertEqual(S.limpar_endereco("  "), "")

    def test_pessoas(self):
        S.salvar_pessoa("person.ana", "(11) 98765-0001")
        self.assertEqual(S.ler_config()["pessoas"], {"person.ana": ANA}, "sem o código do país: Brasil")
        with self.assertRaisesRegex(ValueError, "já é de outra pessoa"):
            S.salvar_pessoa("person.beto", ANA_WA)
        with self.assertRaisesRegex(ValueError, "Número inválido"):
            S.salvar_pessoa("person.beto", "123")
        with self.assertRaisesRegex(ValueError, "Pessoa inválida"):
            S.salvar_pessoa("../x", ANA)
        self.assertEqual(S.pessoa_do_numero(ANA_WA), {"id": "person.ana", "nome": "Ana"}, "o WhatsApp manda sem o 9")
        self.assertIsNone(S.pessoa_do_numero(BETO))
        S.salvar_pessoa("person.ana", "")
        self.assertEqual(S.ler_config()["pessoas"], {})

    def test_pessoas_do_home_assistant(self):
        ha = ServidorFalso({"/api/states": (200, [{"entity_id": "person.beto", "attributes": {"friendly_name": "Beto"}},
                                                  {"entity_id": "person.ana", "attributes": {"friendly_name": "Ana"}},
                                                  {"entity_id": "sensor.x", "attributes": {}}])})
        self.addCleanup(ha.fechar)
        S._pessoas_cache.update(t=0, v=None)
        with mock.patch.object(S, "TOKEN", "t"), mock.patch.object(S, "HA_API", ha.url + "/api"):
            self.assertEqual(S.pessoas_ha(), [{"id": "person.ana", "nome": "Ana"}, {"id": "person.beto", "nome": "Beto"}])
            S.pessoas_ha()
            self.assertEqual(len(ha.pedidos), 1, "guardado por 1 minuto")
            self.assertEqual(ha.pedidos[0][2]["Authorization"], "Bearer t")
        S._pessoas_cache.update(t=0, v=None)
        with mock.patch.object(S, "TOKEN", "t"), mock.patch.object(S, "HA_API", "http://127.0.0.1:9/api"):
            self.assertEqual(S.pessoas_ha(), [], "sem o Home Assistant: ninguém")
        S._pessoas_cache.update(t=0, v=None)

    def test_pessoa_cadastrada_que_saiu_do_home_assistant(self):
        S.salvar_pessoa("person.carla_souza", "5511900000003")
        p = next(x for x in S.estado()["pessoas"] if x["id"] == "person.carla_souza")
        self.assertEqual((p["nome"], p["fora"]), ("Carla Souza", True))


# ---------------------------------------------------------------------------------------------------------------
class TestResponder(Base):
    def mandar(self, *msgs, **kw):
        S.receber(entrega(*msgs, **kw))

    def test_pergunta_vai_para_o_gerencia_e_a_resposta_volta(self):
        self.configurar()
        self.mandar(texto("Quanto gastei?"))
        self.assertEqual(self.meta.lidas()[0]["message_id"], "wamid.1", "marca como lida e mostra digitando")
        self.assertEqual(self.meta.textos(), [(ANA_WA, "Resposta para *Ana*: Quanto gastei?")], "no jeito do WhatsApp")
        _, _, h, c = self.gerencia.pedidos[0]
        self.assertEqual((c["texto"], c["historico"], c["pessoa"]), ("Quanto gastei?", [], {"id": "person.ana", "nome": "Ana"}))
        self.assertEqual(self.registro(), [("recebida", "Ana", "Quanto gastei?"), ("enviada", "Ana", "Resposta para *Ana*: Quanto gastei?")])
        self.assertEqual(S.ler_conversas()["registro"][0]["app"], "GerencIA")

    def test_a_conversa_vai_junto(self):
        self.configurar()
        self.mandar(texto("Quanto gastei?"))
        self.mandar(texto("e ontem?", mid="wamid.2"))
        hist = self.gerencia.pedidos[1][3]["historico"]
        self.assertEqual([m["papel"] for m in hist], ["eu", "ia"])
        self.assertEqual(hist[0]["texto"], "Quanto gastei?")
        self.assertEqual(S.historico(BETO), [], "cada pessoa a sua")

    def test_conversa_velha_recomeca(self):
        self.configurar()
        self.mandar(texto("Quanto gastei?"))
        c = S.ler_conversas()
        for m in c["conversas"][W.canonico(ANA)]:
            m["em"] = "2020-01-01T00:00:00"
        S._gravar_conversas(c)
        self.assertEqual(S.historico(ANA_WA), [])

    def test_numero_sem_cadastro_nao_recebe_resposta(self):
        self.configurar()
        self.mandar(texto("oi", de="5531999990000"), contatos=[{"profile": {"name": "Desconhecido"}, "wa_id": "5531999990000"}])
        self.assertEqual((self.meta.pedidos, self.gerencia.pedidos), ([], []))
        self.assertEqual(self.registro(), [("bloqueada", "Desconhecido", "oi")])

    def test_a_mesma_mensagem_uma_vez_so(self):
        self.configurar()
        self.mandar(texto("Quanto gastei?"))
        self.mandar(texto("Quanto gastei?"))
        self.assertEqual(len(self.meta.textos()), 1, "a Meta manda de novo quando não recebe o 200 a tempo")

    def test_audio_foto_e_figurinha(self):
        self.configurar()
        self.mandar({"from": ANA_WA, "id": "wamid.a", "type": "audio", "audio": {"id": "1"}})
        self.assertEqual(self.meta.textos(), [(ANA_WA, S.SO_TEXTO)])
        self.assertEqual(self.gerencia.pedidos, [])
        self.assertEqual(self.registro()[0], ("recebida", "Ana", "[audio]"))

    def test_pausado_nao_responde(self):
        self.configurar()
        S.salvar_config({"ligado": False})
        self.mandar(texto("Quanto gastei?"))
        self.assertEqual(self.meta.pedidos, [])
        self.assertEqual(self.registro(), [("recebida", "Ana", "Quanto gastei? (respostas pausadas)")])

    def test_sem_app_explica_o_que_ligar(self):
        self.configurar(app=False)
        self.mandar(texto("Quanto gastei?"))
        self.assertEqual(self.meta.textos(), [(ANA_WA, S.SEM_APP)])

    def test_app_com_erro(self):
        self.configurar()
        self.gerencia.rotas["/api/integracao/conversa"] = (400, {"erro": "A IA está desligada."})
        self.mandar(texto("Quanto gastei?"))
        self.assertEqual(self.meta.textos(), [(ANA_WA, "Não consegui falar com o GerencIA agora. Tente de novo daqui a pouco.")])
        self.assertIn(("erro", "GerencIA", "A IA está desligada."), self.registro())

    def test_erro_ao_mandar_vai_para_o_registro(self):
        self.configurar()
        self.meta.rotas[f"/{MetaFalsa.NUMERO_ID}/messages"] = (400, {"error": {"code": 131047, "message": "Re-engagement"}})
        self.mandar(texto("Quanto gastei?"))
        self.assertIn(("erro", "WhatsApp", W.ERROS[131047]), self.registro())

    def test_de_outro_numero_da_conta_e_falhas(self):
        self.configurar()
        self.mandar(texto("oi"), numero_id="999")
        self.assertEqual(self.meta.pedidos, [], "mensagem para outro número da mesma conta da Meta")
        S.receber(entrega(statuses=[{"status": "failed", "recipient_id": ANA_WA, "errors": [{"code": 131026}]}]))
        self.assertEqual(self.registro()[-1], ("erro", "WhatsApp", f"Não chegou para Ana: {W.ERROS[131026]}"))

    def test_erro_inesperado_nao_derruba_as_outras(self):
        self.configurar()
        with mock.patch.object(S, "pessoa_do_numero", side_effect=[KeyError("x"), {"id": "person.beto", "nome": "Beto"}]):
            self.mandar(texto("um", mid="m1"), texto("dois", de=BETO, mid="m2"))
        self.assertEqual([t for _, t in self.meta.textos()], ["Resposta para *Beto*: dois"])
        self.assertTrue(any(t == "erro" and q == "CorrerIA" for t, q, _ in self.registro()))

    def test_testar_pela_tela(self):
        self.configurar()
        r = S.testar({"texto": "Quanto gastei?", "pessoa": "person.beto"})
        self.assertEqual(r, {"resposta": "Resposta para *Beto*: Quanto gastei?", "app": "GerencIA"})
        self.assertEqual(self.meta.pedidos, [], "o teste não passa pelo WhatsApp")
        with self.assertRaisesRegex(ValueError, "Escreva uma pergunta."):
            S.testar({"texto": " "})
        shutil.rmtree(os.path.join(S.SHARE_DIR, "gerencia"))
        self.assertEqual(S.testar({"texto": "oi"}), {"resposta": S.SEM_APP, "app": ""})

    def test_registro_guarda_so_as_ultimas(self):
        for n in range(S.MAX_REGISTRO + 5):
            S.registrar("recebida", "Ana", f"m{n}")
        r = S.ler_conversas()["registro"]
        self.assertEqual((len(r), r[0]["texto"]), (S.MAX_REGISTRO, f"m{S.MAX_REGISTRO + 4}"))

    def test_mascarar(self):
        self.assertEqual(S.mascarar("5531999990000"), "+5531•••0000")


# ---------------------------------------------------------------------------------------------------------------
class TestWebhook(Base):
    def setUp(self):
        super().setUp()
        self.hook = S.ServidorWebhook(("127.0.0.1", 0), S.Webhook)
        threading.Thread(target=self.hook.serve_forever, daemon=True).start()
        self.addCleanup(self.hook.server_close)
        self.addCleanup(self.hook.shutdown)
        self.url = f"http://127.0.0.1:{self.hook.server_address[1]}"

    def assinado(self, dados, segredo=SEGREDO):
        corpo = json.dumps(dados).encode()
        return corpo, {"X-Hub-Signature-256": "sha256=" + hmac.new(segredo.encode(), corpo, hashlib.sha256).hexdigest()}

    def test_a_meta_confere_o_endereco(self):
        v = S.ler_config()["verificacao"]
        st, corpo = pedir(f"{self.url}/webhook?hub.mode=subscribe&hub.verify_token={v}&hub.challenge=1158201444")
        self.assertEqual((st, corpo), (200, b"1158201444"), "devolve o desafio, em texto")
        self.assertTrue(S.estado()["webhook"]["verificado_em"])
        for q in (f"hub.mode=subscribe&hub.verify_token=errado&hub.challenge=1", f"hub.mode=outro&hub.verify_token={v}&hub.challenge=1", ""):
            self.assertEqual(pedir(f"{self.url}/webhook?{q}")[0], 403)

    def test_mensagem_assinada_e_respondida(self):
        self.configurar()
        corpo, cab = self.assinado(entrega(texto("Quanto gastei?")))
        st, r = pedir(self.url + "/webhook", "POST", corpo, cab)
        self.assertEqual((st, r), (200, b"ok"))
        self.assertTrue(esperar(lambda: self.meta.textos()))
        self.assertEqual(self.meta.textos(), [(ANA_WA, "Resposta para *Ana*: Quanto gastei?")])
        self.assertTrue(S.estado()["webhook"]["ultimo"])

    def test_sem_assinatura_certa_nao_entra(self):
        self.configurar()
        corpo, cab = self.assinado(entrega(texto("oi")), segredo="outro")
        for c in (cab, {}):
            self.assertEqual(pedir(self.url + "/webhook", "POST", corpo, c)[0], 401)
        time.sleep(0.2)
        self.assertEqual(self.meta.pedidos, [])

    def test_sem_a_chave_secreta_nada_entra(self):
        corpo, cab = self.assinado(entrega(texto("oi")), segredo="")
        self.assertEqual(pedir(self.url + "/webhook", "POST", corpo, cab)[0], 401)

    def test_so_o_webhook(self):
        self.assertEqual(pedir(self.url + "/")[0], 404)
        self.assertEqual(pedir(self.url + "/api/estado")[0], 404, "a tela não fica exposta na internet")
        self.assertEqual(pedir(self.url + "/outro", "POST", b"{}")[0], 404)
        self.assertEqual(pedir(self.url + "/webhook", "PUT", b"{}")[0], 404)
        self.configurar(pessoas=False, app=False)
        self.assertEqual(pedir(self.url + "/webhook", "POST", b"")[0], 400)
        corpo, cab = self.assinado("nada")
        self.assertEqual(pedir(self.url + "/webhook", "POST", b"{x", {"X-Hub-Signature-256": "sha256=" + hmac.new(SEGREDO.encode(), b"{x", hashlib.sha256).hexdigest()})[0], 400)

    def test_corpo_grande_demais(self):
        with mock.patch.object(S, "MAX_CORPO", 10):
            self.assertEqual(pedir(self.url + "/webhook", "POST", b"x" * 20)[0], 413)


class TestHttps(Base):
    def test_com_o_certificado_do_duck_dns(self):
        ssl_dir = pasta_temp()
        certificado(ssl_dir)
        with mock.patch.object(S, "SSL_DIR", ssl_dir):
            hook = S.ServidorWebhook(("127.0.0.1", 0), S.Webhook)
            threading.Thread(target=hook.serve_forever, daemon=True).start()
            self.addCleanup(hook.server_close)
            self.addCleanup(hook.shutdown)
            ctx = ssl.create_default_context()
            ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE  # o certificado do teste é próprio
            v = S.ler_config()["verificacao"]
            url = f"https://127.0.0.1:{hook.server_address[1]}/webhook?hub.mode=subscribe&hub.verify_token={v}&hub.challenge=42"
            self.assertEqual(pedir(url, contexto=ctx), (200, b"42"))
            with self.assertRaises((urllib.error.URLError, ConnectionError, OSError)):
                pedir(url.replace("https", "http"))  # sem TLS numa porta https: não responde
            self.assertEqual(S.estado()["webhook"]["certificado"], "fullchain.pem")
            self.assertTrue(S.estado()["webhook"]["https"])
            # o Duck DNS renovou: o certificado novo vale sem reiniciar
            antes = hook._ctx
            time.sleep(0.05)
            certificado(ssl_dir)
            os.utime(os.path.join(ssl_dir, "fullchain.pem"), (time.time() + 5, time.time() + 5))
            self.assertEqual(pedir(url, contexto=ctx)[0], 200)
            self.assertIsNot(hook._ctx, antes)

    def test_sem_certificado_fica_em_http(self):
        with mock.patch.object(S, "SSL_DIR", pasta_temp()):
            self.assertIsNone(S.certificado())
            self.assertFalse(S.estado()["webhook"]["https"])


# ---------------------------------------------------------------------------------------------------------------
class TestTela(Base):
    def setUp(self):
        super().setUp()
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), S.Tela)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.addCleanup(self.srv.server_close)
        self.addCleanup(self.srv.shutdown)
        self.url = f"http://127.0.0.1:{self.srv.server_address[1]}"

    def json(self, caminho, corpo=None):
        st, r = pedir(self.url + caminho, "POST" if corpo is not None else "GET", corpo)
        return st, json.loads(r)

    def test_estado_e_configurar(self):
        st, e = self.json("/api/estado")
        self.assertEqual((st, e["versao"], e["pronto"]), (200, S.VERSAO, False))
        self.assertEqual([p["id"] for p in e["pessoas"]], ["person.ana", "person.beto"])
        st, e = self.json("/api/config", {"numero_id": MetaFalsa.NUMERO_ID, "token": TOKEN, "segredo": SEGREDO, "endereco": "casa-exemplo.duckdns.org:8443"})
        self.assertEqual((st, e["pronto"], e["config"]["token"]), (200, True, "••••1234"))
        st, e = self.json("/api/conferir", {})
        self.assertEqual((st, e["conta"]), (200, {"numero": "+55 11 4000-0000", "nome": "CorrerIA Code"}))
        st, e = self.json("/api/pessoa", {"id": "person.ana", "numero": ANA})
        self.assertEqual(next(p for p in e["pessoas"] if p["id"] == "person.ana")["numero"], ANA)
        st, e = self.json("/api/pessoa", {"id": "person.ana", "numero": "12"})
        self.assertEqual((st, e["erro"]), (400, "Número inválido. Use o código do país e o DDD: 55 11 99999-0000."))

    def test_conferir_com_token_errado(self):
        S.salvar_config({"numero_id": MetaFalsa.NUMERO_ID, "token": TOKEN})
        self.meta.rotas[f"/{MetaFalsa.NUMERO_ID}"] = (401, {"error": {"code": 190, "message": "x"}})
        st, e = self.json("/api/conferir", {})
        self.assertEqual((st, e["erro"]), (400, W.ERROS[190]))

    def test_testar_e_limpar(self):
        self.configurar()
        st, r = self.json("/api/testar", {"texto": "Quanto gastei?", "pessoa": "person.ana"})
        self.assertEqual((st, r["app"]), (200, "GerencIA"))
        S.registrar("recebida", "Ana", "oi")
        st, e = self.json("/api/registro/limpar", {})
        self.assertEqual(e["registro"], [])
        self.assertEqual(self.json("/api/nada", {})[0], 404)
        self.assertEqual(self.json("/api/config", [1])[0], 200, "um corpo que não é objeto vale como vazio")

    def test_arquivos_da_tela(self):
        st, html = pedir(self.url + "/")
        self.assertEqual(st, 200)
        self.assertIn(b"<title>CorrerIA</title>", html)
        for arq in ("app.js", "styles.css", "icon.svg", "fonts/barlow-400.woff2"):
            self.assertEqual(pedir(self.url + "/" + arq)[0], 200, arq)
        for ruim in ("/../server.py", "/%2e%2e/server.py", "/nada.js"):
            self.assertEqual(pedir(self.url + ruim)[0], 404, ruim)

    def test_so_pelo_painel(self):
        with mock.patch.object(S, "DEV", False):
            self.assertEqual(pedir(self.url + "/api/estado")[0], 200, "127.0.0.1 é permitido")
            with mock.patch.object(S, "PERMITIDOS", set()):
                self.assertEqual(pedir(self.url + "/api/estado")[0], 403)
                self.assertEqual(pedir(self.url + "/api/config", "POST", {})[0], 403)


if __name__ == "__main__":
    unittest.main()
