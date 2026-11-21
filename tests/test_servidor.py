"""server.py: a configuração (o token e a chave nunca voltam para a tela), quem pode conversar, o webhook da Meta (conferir
o endereço, a assinatura, https com o certificado), responder pelo app da família e a tela. A Meta e o GerencIA são de
mentira; pessoas e números inventados (Ana, Beto)."""
import base64
import hashlib
import hmac
import json
import re
import secrets
import os
import shutil
import socket
import ssl
import threading
from datetime import datetime, timedelta
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer
from unittest import mock

from tests.base import importar_servidor, AppFalso, MetaFalsa, ServidorFalso, certificado, pasta_temp, ANA, ANA_WA, BETO
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
        for arq in (S.CONFIG_ARQ, S.CONVERSAS_ARQ, S.MCP_ARQ):
            if os.path.exists(arq):
                os.remove(arq)
        S.AUT.pedidos.clear()
        S.AUT.codigos.clear()
        S.ESTADO["ia"] = None
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

    def configurar(self, pessoas=True, app=True, anexos=("image/jpeg", "application/pdf")):
        S.salvar_config({"numero_id": MetaFalsa.NUMERO_ID, "token": TOKEN, "segredo": SEGREDO, "endereco": "casa-exemplo.duckdns.org:8443"})
        if pessoas:
            S.salvar_pessoa("person.ana", ANA)
            S.salvar_pessoa("person.beto", BETO)
        if app:
            os.makedirs(os.path.join(S.SHARE_DIR, "gerencia"), exist_ok=True)
            with open(os.path.join(S.SHARE_DIR, "gerencia", "correria.json"), "w") as f:
                json.dump({"app": "gerencia", "nome": "GerencIA", "assunto": "finanças", "rota": "/api/integracao/conversa",
                           "url": self.gerencia.url, "chave": "chave-gerencia-" + "x" * 20, "anexos": list(anexos)}, f)

    def registro(self):
        return [(r["tipo"], r["quem"], r["texto"]) for r in S.ler_conversas()["registro"]][::-1]


# ---------------------------------------------------------------------------------------------------------------
class TestConfig(Base):
    def test_atalho_no_celular(self):
        # o caminho do app no Home Assistant, pelo nome do contêiner; fora dele, nada
        self.assertEqual(S.atalho("a1b2c3d4-correria"), "/app/a1b2c3d4_correria")
        self.assertIsNone(S.atalho("meu-computador"))
        self.assertIsNone(S.atalho(""))
        with mock.patch.dict(os.environ, {"CORRERIA_HOST": "e5f6a7b8-correria"}):
            self.assertEqual(S.estado()["atalho"], "/app/e5f6a7b8_correria")

    def test_painel_da_cronologia(self):
        # 1.2.0: o endereço da CronologIA no navegador (o tela do integracao.json dela) com ?painel=1; sem ele ou estranho, nada
        arq = os.path.join(S.SHARE_DIR, "cronologia", "integracao.json")
        self.assertIsNone(S.painel())
        os.makedirs(os.path.dirname(arq), exist_ok=True)
        for tela, esperado in (("/api/hassio_ingress/AbC123_-xyz/", "/api/hassio_ingress/AbC123_-xyz/?painel=1"), ("/api/hassio_ingress/../../x", None),
                               ("https://outro.site/api/hassio_ingress/AbC123_-xyz", None), ("", None), (None, None)):
            with open(arq, "w") as f:
                json.dump({"app": "CronologIA", "tela": tela}, f)
            self.assertEqual(S.painel(), esperado, tela)
        with open(arq, "w") as f:
            f.write("não é json")
        self.assertIsNone(S.painel())
        with open(arq, "w") as f:
            json.dump({"app": "CronologIA", "tela": "/api/hassio_ingress/AbC123_-xyz"}, f)
        self.assertEqual(S.estado()["painel"], "/api/hassio_ingress/AbC123_-xyz/?painel=1")
        self.assertFalse(S.estado()["painel_cabecalho"])
        # 1.4.0: da CronologIA 1.97.0 em diante, &conversa=1 (os botões no alto do painel, sem a faixa daqui)
        for versao, cab in (("1.96.1", False), ("1.97.0", True), ("1.100.2", True), ("2.0.0", True), ("1.97", False), ("x", False)):
            with open(arq, "w") as f:
                json.dump({"app": "cronologia", "versao": versao, "tela": "/api/hassio_ingress/AbC123_-xyz"}, f)
            e = S.estado()
            self.assertEqual((e["painel"], e["painel_cabecalho"]), ("/api/hassio_ingress/AbC123_-xyz/?painel=1" + ("&conversa=1" if cab else ""), cab), versao)

    def test_casa_do_home_assistant(self):
        # 1.5.0: a casa (o Assist) como mais um app, ligada de início; só dentro do Home Assistant
        c = S.ler_config()
        self.assertEqual((c["casa"], c["recolher"]), (True, 3))
        self.assertEqual((S.estado()["casa"], S.estado()["recolher"]), ({"ligado": True, "disponivel": False}, 3))
        self.assertFalse(any(f["id"].startswith("casa_") for f in S.FERR.todas()), "fora do Home Assistant, sem a casa")
        resposta = {"response": {"response_type": "action_done", "speech": {"plain": {"speech": "Luz da entrada ligada"}}, "data": {"success": [{"type": "entity", "name": "Luz da entrada"}]}}}
        ha = ServidorFalso({"/api/conversation/process": (200, resposta), "/api/states": (200, [{"entity_id": "light.entrada", "state": "off", "attributes": {"friendly_name": "Luz da entrada"}}])})
        self.addCleanup(ha.fechar)
        with mock.patch.object(S, "TOKEN", "t"), mock.patch.object(S, "HA_API", ha.url + "/api"):
            self.assertTrue(S.FERR.tem())
            self.assertEqual([f["id"] for f in S.FERR.todas()], ["casa_comando", "casa_estado"])
            texto, nomes = S.executar([{"ferramenta": "casa_comando", "argumentos": {"pedido": "liga a luz da entrada"}, "resumo": "Ligar a luz da entrada"}], {"id": "person.ana", "nome": "Ana"}, "WhatsApp")
            self.assertEqual((texto, nomes), ("Feito!\n- Luz da entrada ligada", ["Casa"]))
            metodo, caminho, cab, corpo = ha.pedidos[-1]
            self.assertEqual((metodo, caminho, cab["Authorization"], corpo), ("POST", "/api/conversation/process", "Bearer t", {"text": "liga a luz da entrada", "language": "pt-BR", "agent_id": "conversation.home_assistant"}))
            texto, _ = S.FERR.usar(S.FERR.achar("casa_estado"), {"busca": "entrada"}, {}, "Claude")
            self.assertEqual(texto, "- Luz da entrada: desligado (light.entrada)")
            S.salvar_config({"casa": False})
            self.assertEqual(S.estado()["casa"], {"ligado": False, "disponivel": True})
            self.assertFalse(S.FERR.tem())
        S.salvar_config({"recolher": 5})
        self.assertEqual(S.ler_config()["recolher"], 5)
        with self.assertRaises(ValueError):
            S.salvar_config({"recolher": 7})

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

    def test_o_endereco_do_conector_e_dele(self):
        """1.14.0: o endereço público do conector MCP é separado do do webhook: a Meta pode chegar pelo Duck DNS, na
        porta 8443, e as IAs por outro domínio (o do túnel da Cloudflare, na 443)."""
        S.salvar_config({"endereco": "casa-exemplo.duckdns.org:8443", "endereco_mcp": "correria.casa-exemplo.com.br/mcp/"})
        c = S.ler_config()
        self.assertEqual((c["endereco"], c["endereco_mcp"]), ("https://casa-exemplo.duckdns.org:8443", "https://correria.casa-exemplo.com.br"))
        e = S.estado()
        self.assertEqual((e["config"]["webhook"], e["mcp"]["endereco"], e["mcp"]["url"]),
                         ("https://casa-exemplo.duckdns.org:8443/webhook", "https://correria.casa-exemplo.com.br", "https://correria.casa-exemplo.com.br/mcp"))
        S.salvar_config({"endereco": "outra-casa.duckdns.org:8443"})
        self.assertEqual(S.ler_config()["endereco_mcp"], "https://correria.casa-exemplo.com.br", "mudar o do webhook não mexe no do conector")
        S.salvar_config({"endereco_mcp": ""})
        e = S.estado()
        self.assertEqual((e["mcp"]["endereco"], e["mcp"]["url"], e["config"]["endereco"]), ("", "", "https://outra-casa.duckdns.org:8443"), "vazio: sem conector, e o webhook fica")
        with self.assertRaisesRegex(ValueError, r"Endereço inválido\. Ex\.: https://correria\.casa-exemplo\.com\.br"):
            S.salvar_config({"endereco_mcp": "https:// nada"})
        self.assertEqual(S.limpar_endereco("casa-exemplo.duckdns.org/mcp"), "https://casa-exemplo.duckdns.org/mcp", "o /mcp só sai do endereço do conector")

    def test_quem_atualiza_comeca_com_o_mesmo_endereco_nos_dois(self):
        """1.14.0: antes havia um endereço só. Quem já tinha continua com ele no conector, até escrever outro."""
        c = S.ler_json(S.CONFIG_ARQ)
        c.pop("endereco_mcp", None)
        c["endereco"] = "https://casa-exemplo.duckdns.org"
        S.gravar_config(c)
        self.assertEqual(S.ler_config()["endereco_mcp"], "https://casa-exemplo.duckdns.org")
        self.assertEqual(S.estado()["mcp"]["url"], "https://casa-exemplo.duckdns.org/mcp")
        S.salvar_config({"endereco": "casa-exemplo.duckdns.org:8443"})
        c = S.ler_config()
        self.assertEqual((c["endereco"], c["endereco_mcp"]), ("https://casa-exemplo.duckdns.org:8443", "https://casa-exemplo.duckdns.org"), "o do conector fica como estava")

    def test_o_certificado_do_conector_e_do_endereco_dele(self):
        from datetime import datetime, timezone
        S.salvar_config({"endereco": "casa-exemplo.duckdns.org:8443", "endereco_mcp": "correria.casa-exemplo.com.br"})
        with mock.patch.object(S, "certificado", return_value=("/ssl/fullchain.pem", "/ssl/privkey.pem")), \
                mock.patch.object(S, "validade_certificado", return_value=(datetime(2027, 1, 1, tzinfo=timezone.utc), "casa-exemplo.duckdns.org")):
            e = S.estado()
        self.assertEqual((e["webhook"]["cert_confere"], e["mcp"]["cert_confere"]), (True, False))

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
        ha = ServidorFalso({"/api/states": (200, [{"entity_id": "person.beto", "attributes": {"friendly_name": "Beto", "user_id": "u-beto"}},
                                                  {"entity_id": "person.ana", "attributes": {"friendly_name": "Ana"}},
                                                  {"entity_id": "sensor.x", "attributes": {}}])})
        self.addCleanup(ha.fechar)
        S._pessoas_cache.update(t=0, v=None)
        with mock.patch.object(S, "TOKEN", "t"), mock.patch.object(S, "HA_API", ha.url + "/api"):
            self.assertEqual(S.pessoas_ha(), [{"id": "person.ana", "nome": "Ana", "usuario": ""}, {"id": "person.beto", "nome": "Beto", "usuario": "u-beto"}])
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

    def test_figurinha_e_video(self):
        self.configurar()
        self.mandar({"from": ANA_WA, "id": "wamid.a", "type": "sticker", "sticker": {"id": "1"}})
        self.assertEqual(self.meta.textos(), [(ANA_WA, S.SO_TEXTO)])
        self.assertEqual(self.gerencia.pedidos, [])
        self.assertEqual(self.registro()[0], ("recebida", "Ana", "[sticker]"))

    # ---- fotos, PDFs e áudio
    def midia(self, mid, dados, tipo):
        self.meta.rotas[f"/{mid}"] = (200, {"url": f"{self.meta.url}/arquivo/{mid}", "mime_type": tipo, "file_size": len(dados)})
        self.meta.rotas[f"/arquivo/{mid}"] = (200, dados)

    def test_foto_vai_para_o_app_com_a_legenda(self):
        self.configurar()
        self.midia("FOTO1", b"\xff\xd8\xff-foto", "image/jpeg")
        self.gerencia.rotas["/api/integracao/conversa"] = (200, {"resposta": "Li 2 lançamentos na foto."})
        self.mandar({"from": ANA_WA, "id": "wamid.f", "type": "image", "image": {"id": "FOTO1", "mime_type": "image/jpeg", "caption": "Quanto deu?"}})
        c = self.gerencia.pedidos[0][3]
        self.assertEqual((c["texto"], c["anexo"]["tipo"], c["anexo"]["b64"]), ("Quanto deu?", "image/jpeg", "data:image/jpeg;base64,/9j/LWZvdG8="))
        self.assertEqual(self.meta.textos(), [(ANA_WA, "Li 2 lançamentos na foto.")])
        self.assertEqual(self.registro()[0], ("recebida", "Ana", "[foto] Quanto deu?"))
        self.assertEqual(S.historico(ANA_WA)[0]["texto"], "[foto] Quanto deu?", "a conversa lembra da foto")

    def test_pdf(self):
        self.configurar()
        self.midia("DOC1", b"%PDF-1.7 fatura", "application/pdf")
        self.mandar({"from": ANA_WA, "id": "wamid.d", "type": "document", "document": {"id": "DOC1", "mime_type": "application/pdf", "filename": "fatura-nov.pdf"}})
        c = self.gerencia.pedidos[0][3]
        self.assertEqual((c["texto"], c["anexo"]["nome"], c["anexo"]["tipo"]), ("", "fatura-nov.pdf", "application/pdf"))
        self.assertEqual(self.registro()[0], ("recebida", "Ana", "[arquivo]"))

    def test_arquivo_que_nenhum_app_le(self):
        self.configurar(anexos=())
        self.mandar({"from": ANA_WA, "id": "wamid.d", "type": "document", "document": {"id": "DOC1", "mime_type": "application/zip", "filename": "x.zip"}})
        self.assertEqual(self.meta.textos(), [(ANA_WA, S.NAO_LE)])
        self.assertEqual(self.gerencia.pedidos, [])

    def test_arquivo_sem_app_nenhum(self):
        self.configurar(app=False)
        self.mandar({"from": ANA_WA, "id": "wamid.d", "type": "image", "image": {"id": "F", "mime_type": "image/jpeg"}})
        self.assertEqual(self.meta.textos(), [(ANA_WA, S.SEM_APP)])

    def test_arquivo_que_a_meta_nao_entrega(self):
        self.configurar()
        self.mandar({"from": ANA_WA, "id": "wamid.f", "type": "image", "image": {"id": "SUMIU", "mime_type": "image/jpeg"}})
        self.assertTrue(self.meta.textos()[0][1].startswith("Não consegui pegar o arquivo: "))
        self.assertEqual(self.gerencia.pedidos, [])

    def test_app_com_erro_no_anexo(self):
        self.configurar()
        self.midia("FOTO1", b"\xff\xd8", "image/jpeg")
        self.gerencia.rotas["/api/integracao/conversa"] = (500, "pane")
        self.mandar({"from": ANA_WA, "id": "wamid.f", "type": "image", "image": {"id": "FOTO1", "mime_type": "image/jpeg"}})
        self.assertEqual(self.meta.textos(), [(ANA_WA, "Não consegui falar com o GerencIA agora. Tente de novo daqui a pouco.")])

    def test_audio_vira_texto_para_o_app(self):
        self.configurar()
        self.midia("AUD1", b"OggS-audio", "audio/ogg; codecs=opus")
        ouvidos = []
        fala_falsa = mock.Mock(texto=lambda b: ouvidos.append(b) or "Quanto gastei com mercado?", status=lambda: {"pronta": True, "nome": "Teste"})
        with mock.patch.object(S, "FALA", fala_falsa):
            self.mandar({"from": ANA_WA, "id": "wamid.a", "type": "audio", "audio": {"id": "AUD1", "mime_type": "audio/ogg; codecs=opus", "voice": True}})
        self.assertEqual(ouvidos, [b"OggS-audio"])
        self.assertEqual(self.gerencia.pedidos[0][3]["texto"], "Quanto gastei com mercado?", "o app recebe o texto")
        self.assertEqual(self.registro()[:2], [("recebida", "Ana", "[áudio] Quanto gastei com mercado?"), ("enviada", "Ana", "Resposta para *Ana*: Quanto gastei com mercado?")])

    def test_audio_sem_fala_para_texto(self):
        self.configurar()
        self.midia("AUD1", b"OggS", "audio/ogg")
        with mock.patch.object(S.FALA, "texto", side_effect=S.fala.ErroFala("A fala para texto não aceitou o áudio.")):
            self.mandar({"from": ANA_WA, "id": "wamid.a", "type": "audio", "audio": {"id": "AUD1"}})
        self.assertEqual(self.meta.textos(), [(ANA_WA, "Não consegui ouvir o áudio: A fala para texto não aceitou o áudio. Escreva a pergunta, por favor.")])
        self.assertEqual(self.gerencia.pedidos, [])

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

    def test_fala_simulada_no_computador(self):
        self.assertEqual(S.estado()["fala"], {"pronta": True, "nome": "Fala simulada (teste)"})

    def test_registro_guarda_so_as_ultimas(self):
        for n in range(S.MAX_REGISTRO + 5):
            S.registrar("recebida", "Ana", f"m{n}")
        r = S.ler_conversas()["registro"]
        self.assertEqual((len(r), r[0]["texto"]), (S.MAX_REGISTRO, f"m{S.MAX_REGISTRO + 4}"))

    def test_mascarar(self):
        self.assertEqual(S.mascarar("5531999990000"), "+5531•••0000")


# ---------------------------------------------------------------------------------------------------------------
class TestConversaTela(Base):
    """Conversar com a IA pela tela do CorrerIA: a mesma ponte, com a conversa de quem está na tela (o login do HA)."""
    ANA = {"X-Remote-User-Id": "u-ana", "X-Remote-User-Display-Name": "Ana Exemplo"}

    def setUp(self):
        super().setUp()
        self.addCleanup(S._gravar_tela, "u-ana", [])
        self.addCleanup(S._gravar_tela, "_", [])

    def test_quem_esta_na_tela(self):
        self.assertEqual(S.pessoa_da_tela(self.ANA), ({"id": "person.ana", "nome": "Ana"}, "u-ana"), "a pessoa ligada ao login")
        self.assertEqual(S.pessoa_da_tela({"X-Remote-User-Id": "u-x", "X-Remote-User-Name": "visita"}), ({"id": "", "nome": "visita"}, "u-x"))
        self.assertEqual(S.pessoa_da_tela({}), ({"id": "", "nome": "Você"}, "_"))

    def test_ola_com_o_primeiro_nome(self):
        self.assertEqual(S.ola_da_tela(self.ANA), "Ana", "a pessoa ligada ao login")
        self.assertEqual(S.ola_da_tela({"X-Remote-User-Id": "u-x", "X-Remote-User-Display-Name": "Carla  Souza"}), "Carla", "sem pessoa: o nome do login")
        self.assertEqual(S.ola_da_tela({"X-Remote-User-Id": "u-x", "X-Remote-User-Name": "visita"}), "visita")
        self.assertEqual(S.ola_da_tela({}), "", "sem login: sem o Olá (nunca \"Olá, Você\")")

    def test_pergunta_e_resposta_ficam_guardadas(self):
        self.configurar()
        pessoa, chave = S.pessoa_da_tela(self.ANA)
        r = S.conversar({"texto": "Quanto gastei?"}, pessoa, chave)
        self.assertEqual([(m["papel"], m["texto"], m.get("app")) for m in r["mensagens"]],
                         [("eu", "Quanto gastei?", None), ("ia", "Resposta para *Ana*: Quanto gastei?", "GerencIA")])
        c = self.gerencia.pedidos[0][3]
        self.assertEqual((c["canal"], c["pessoa"], c["historico"]), ("correria", {"id": "person.ana", "nome": "Ana"}, []))
        S.conversar({"texto": "e ontem?"}, pessoa, chave)
        self.assertEqual([m["texto"] for m in self.gerencia.pedidos[1][3]["historico"]], ["Quanto gastei?", "Resposta para *Ana*: Quanto gastei?"])
        self.assertEqual(len(S.conversa_tela("u-ana")), 4)
        self.assertEqual(S.conversa_tela("_"), [], "cada login a sua")
        self.assertEqual(self.meta.pedidos, [], "a conversa da tela não passa pela Meta")

    def test_foto_ou_pdf(self):
        self.configurar()
        pessoa, chave = S.pessoa_da_tela(self.ANA)
        r = S.conversar({"texto": "", "anexo": {"nome": "nota.jpg", "b64": "data:image/jpeg;base64,/9j/"}}, pessoa, chave)
        c = self.gerencia.pedidos[0][3]
        self.assertEqual(c["anexo"], {"tipo": "image/jpeg", "nome": "nota.jpg", "b64": "data:image/jpeg;base64,/9j/"})
        self.assertEqual(r["mensagens"][0]["anexo"], "nota.jpg")
        r = S.conversar({"anexo": {"nome": "x.zip", "b64": "data:application/zip;base64,UEs="}}, pessoa, chave)
        self.assertEqual(r["mensagens"][-1]["texto"], S.NAO_LE)
        with mock.patch.object(S, "MAX_ANEXO", 2):
            with self.assertRaisesRegex(ValueError, "grande demais"):
                S.conversar({"anexo": {"b64": "data:image/jpeg;base64,/9j/4AAQSkZJRg=="}}, pessoa, chave)

    def test_sem_app_e_erros(self):
        pessoa, chave = S.pessoa_da_tela({})
        self.assertEqual(S.conversar({"texto": "oi"}, pessoa, chave)["mensagens"][-1]["texto"], S.SEM_APP)
        with self.assertRaisesRegex(ValueError, "Escreva uma mensagem."):
            S.conversar({"texto": " "}, pessoa, chave)
        self.configurar(pessoas=False)
        self.gerencia.rotas["/api/integracao/conversa"] = (400, {"erro": "A IA está desligada."})
        self.assertEqual(S.conversar({"texto": "oi"}, pessoa, chave)["mensagens"][-1]["texto"], "Não consegui falar com o GerencIA agora. A IA está desligada.")

    def test_guarda_so_as_ultimas_e_nao_atrapalha_o_resto(self):
        self.configurar()
        S.registrar("recebida", "Ana", "do WhatsApp")
        with mock.patch.object(S, "MAX_TELA", 4):
            for n in range(3):
                S.conversar({"texto": f"pergunta {n}"}, {"id": "", "nome": "Ana"}, "u-ana")
        self.assertEqual([m["texto"] for m in S.conversa_tela("u-ana") if m["papel"] == "eu"], ["pergunta 1", "pergunta 2"])
        S.registrar("recebida", "Ana", "outra")
        self.assertEqual(len(S.conversa_tela("u-ana")), 4, "gravar o registro do WhatsApp não apaga a conversa da tela")
        self.assertEqual(S.ler_conversas()["registro"][1]["texto"], "do WhatsApp")


class TestListaDeConversas(Base):
    """As conversas da tela, como nos chats de sempre: a nova começa vazia, a anterior fica na lista, abrir e apagar."""
    ANA = "u-ana"

    def setUp(self):
        super().setUp()
        if os.path.exists(S.CONVERSAS_ARQ):
            os.remove(S.CONVERSAS_ARQ)

    def falar(self, *textos):
        for t in textos:
            lista = S.conversa_tela(self.ANA) + [{"papel": "eu", "texto": t, "em": S.agora_iso()}, {"papel": "ia", "texto": "ok", "em": S.agora_iso()}]
            S._gravar_tela(self.ANA, lista)

    def test_nova_abrir_apagar(self):
        self.falar("Quanto gastei no mercado?\nem outubro", "e em setembro?")
        self.assertEqual([(x["titulo"], x["mensagens"], x["aberta"]) for x in S.conversas_tela(self.ANA)], [("Quanto gastei no mercado?", 4, True)],
                         "o nome é a primeira pergunta (a primeira linha)")
        S.guardar_pendente("tela:" + self.ANA, [{"ferramenta": "gerencia_lancar", "argumentos": {}}])
        r = S.nova_conversa(self.ANA)
        self.assertEqual((r["mensagens"], r["conversa"], S.conversa_tela(self.ANA)), ([], None, []))
        self.assertIsNone(S.pegar_pendente("tela:" + self.ANA), "a mudança esperando o sim sai")
        self.assertEqual(len(S.conversas_tela(self.ANA)), 1, "a nova só entra na lista com a primeira mensagem")
        self.falar("Lança 20 de padaria")
        lista = S.conversas_tela(self.ANA)
        self.assertEqual([(x["titulo"], x["aberta"]) for x in lista], [("Lança 20 de padaria", True), ("Quanto gastei no mercado?", False)])
        r = S.abrir_conversa(self.ANA, lista[1]["id"])
        self.assertEqual((len(r["mensagens"]), r["conversa"]), (4, lista[1]["id"]))
        self.falar("e em agosto?")
        self.assertEqual(S.conversas_tela(self.ANA)[0]["titulo"], "Quanto gastei no mercado?", "a que recebeu mensagem sobe")
        r = S.apagar_conversa(self.ANA, lista[1]["id"])
        self.assertEqual((r["mensagens"], r["conversa"], [x["titulo"] for x in r["conversas"]]), ([], None, ["Lança 20 de padaria"]),
                         "apagar a aberta: fica uma nova, vazia")
        with self.assertRaisesRegex(ValueError, "não existe mais"):
            S.abrir_conversa(self.ANA, lista[1]["id"])
        self.assertEqual(S.conversas_tela("_"), [], "cada login a sua")

    def test_titulos(self):
        self.assertEqual(S._titulo([{"papel": "eu", "texto": "x" * 80}]), "x" * 59 + "…")
        self.assertEqual(S._titulo([{"papel": "eu", "texto": "", "anexo": "nota.jpg"}]), "nota.jpg")
        self.assertEqual(S._titulo([{"papel": "ia", "texto": "oi"}]), "Conversa")

    def test_ate_30_conversas(self):
        for n in range(32):
            S.nova_conversa(self.ANA)
            S._gravar_tela(self.ANA, [{"papel": "eu", "texto": f"pergunta {n}"}])
        lista = S.conversas_tela(self.ANA)
        self.assertEqual((len(lista), lista[0]["titulo"], lista[-1]["titulo"]), (30, "pergunta 31", "pergunta 2"), "as mais velhas saem")

    def test_a_conversa_da_versao_anterior_vira_a_primeira_da_lista(self):
        S.gravar_arquivo(S.CONVERSAS_ARQ, json.dumps({"tela": {self.ANA: [{"papel": "eu", "texto": "Quanto gastei?", "em": "2026-11-01T10:00:00"},
                                                                         {"papel": "ia", "texto": "R$ 300", "em": "2026-11-01T10:00:05"}]}}))
        lista = S.conversas_tela(self.ANA)
        self.assertEqual([(x["titulo"], x["aberta"], x["atualizada"]) for x in lista], [("Quanto gastei?", True, "2026-11-01T10:00:05")])
        self.assertEqual(S.abrir_conversa(self.ANA, lista[0]["id"])["conversa"], lista[0]["id"], "o mesmo id até gravar")
        self.assertEqual(len(S.conversa_tela(self.ANA)), 2)


# ---------------------------------------------------------------------------------------------------------------
class IAFalsa:
    """A IA do Home Assistant de mentira: devolve as respostas da fila (ou um erro) e guarda os pedidos."""

    def __init__(self, *respostas):
        self.fila, self.pedidos = list(respostas), []

    def __call__(self, instrucoes):
        self.pedidos.append(instrucoes)
        r = self.fila.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


LANCAR = {"chamar": [{"ferramenta": "gerencia_lancar", "argumentos": {"descricao": "Feira", "valor": 32.5}, "resumo": "Lançar R$ 32,50 de Feira hoje"}]}


class TestComFerramentas(Base):
    """Os apps com ferramentas: a IA do Home Assistant lê e propõe; a mudança só acontece com o sim."""

    def setUp(self):
        super().setUp()
        self.configurar(app=False)
        self.app = AppFalso("GerencIA")
        self.addCleanup(self.app.fechar)
        self.app.publicar(S.SHARE_DIR, "gerencia")

    def ia(self, *respostas, pesquisar=None):
        self.falsa = IAFalsa(*respostas)
        p = mock.patch.object(S, "AGENTE", S.ia.Agente(S.FERR, self.falsa, S.log, pesquisar=pesquisar))
        p.start()
        self.addCleanup(p.stop)

    def mandar(self, t, de=ANA_WA):
        n = len(self.meta.textos())
        S.receber(entrega(texto(t, de=de, mid="wamid." + secrets.token_hex(4))))
        return self.meta.textos()[n:]

    def test_le_e_responde(self):
        self.ia({"chamar": [{"ferramenta": "gerencia_resumo", "argumentos": {}}]}, {"resposta": "Você tem **3 contas**."})
        self.assertEqual(self.mandar("O que vence?"), [(ANA_WA, "Você tem *3 contas*.")])
        self.assertIn("Quem está conversando: Ana", self.falsa.pedidos[0])
        self.assertEqual(self.app.feitos[0]["cliente"], "WhatsApp")
        self.assertEqual(self.registro()[-1], ("enviada", "Ana", "Você tem *3 contas*."))
        self.assertEqual(S.ler_conversas()["registro"][0]["app"], "GerencIA")

    def test_mudar_so_com_o_sim(self):
        self.ia(LANCAR)
        r = self.mandar("lança 32,50 de feira")
        self.assertEqual(r[0][1], "Vou fazer isto:\n- Lançar R$ 32,50 de Feira hoje\n\nToque em *Sim* para confirmar.")
        self.assertEqual(self.meta.botoes(), [[("sim", "Sim"), ("nao", "Não")]], "1.10.0: o Sim e o Não em botões")
        self.assertEqual(self.app.feitos, [])
        r = self.mandar("Sim!")
        self.assertEqual(r[0][1], "Feito!\n- Lançado: Feira · R$ 32.5. id: l1")
        f = self.app.feitos[-1]
        self.assertEqual((f["nome"], f["argumentos"], f["pessoa"], f["cliente"]), ("lancar", {"descricao": "Feira", "valor": 32.5}, {"id": "person.ana", "nome": "Ana"}, "WhatsApp"))
        self.assertEqual(S.ler_conversas()["pendentes"], {}, "vale uma vez só")
        self.ia({"resposta": "Sim o quê?"})
        self.assertEqual(self.mandar("sim")[0][1], "Sim o quê?", "sem nada esperando, sim é só uma mensagem")

    def test_nao_e_outra_pergunta(self):
        self.ia(LANCAR)
        self.mandar("lança 32,50 de feira")
        self.assertEqual(self.mandar("não, deixa")[0][1], "Tudo bem, não mudei nada.")
        self.ia(LANCAR, {"chamar": [{"ferramenta": "gerencia_resumo"}]}, {"resposta": "Hoje: 3 contas."})
        self.mandar("lança 32,50 de feira")
        self.assertEqual(self.mandar("quanto tenho?")[0][1], "Hoje: 3 contas.", "outra pergunta desfaz o que esperava")
        self.assertEqual([f["nome"] for f in self.app.feitos], ["resumo"])
        self.assertIn("IA: Vou fazer isto:", self.falsa.pedidos[-1], "a IA vê o que foi proposto")

    def test_o_sim_vence_em_30_minutos(self):
        self.ia(LANCAR, {"resposta": "Sim o quê?"})
        self.mandar("lança 32,50 de feira")
        with S.TRAVA:
            c = S.ler_conversas()
            for p in c["pendentes"].values():
                p["em"] = "2020-01-01T00:00:00"
            S._gravar_conversas(c)
        self.assertEqual(self.mandar("sim")[0][1], "Sim o quê?")
        self.assertEqual(self.app.feitos, [])

    def test_o_app_recusa_no_sim(self):
        self.ia({"chamar": [{"ferramenta": "gerencia_lancar", "argumentos": {"descricao": "Feira"}, "resumo": "Lançar Feira"}]})
        self.mandar("lança feira")
        self.assertEqual(self.mandar("ok")[0][1], "- Não deu: Falta o valor.")
        self.assertEqual(self.registro()[-2][0], "erro")

    def test_ia_fora_do_ar(self):
        self.ia(S.ia.ErroIA("Nenhuma entidade de IA."))
        self.assertEqual(self.mandar("oi")[0][1], "A IA do Home Assistant não respondeu agora (Nenhuma entidade de IA). Tente de novo daqui a pouco.")
        # com um app que responde com a IA dele, vai por ele
        self.ia(S.ia.ErroIA("Nenhuma entidade de IA."))
        self.app.publicar(S.SHARE_DIR, "gerencia", rota="/api/integracao/conversa")
        self.app.rotas["/api/integracao/conversa"] = (200, {"resposta": "Pela IA do GerencIA."})
        self.assertEqual(self.mandar("oi")[0][1], "Pela IA do GerencIA.")

    def test_conversa_da_tela(self):
        self.ia(LANCAR)
        r = S.conversar({"texto": "lança 32,50 de feira"}, {"id": "person.ana", "nome": "Ana"}, "u-ana")
        self.assertEqual(r["mensagens"][-1]["app"], "GerencIA")
        self.assertIn("Toque em *Sim*", r["mensagens"][-1]["texto"])
        self.assertIs(r["mensagens"][-1].get("confirmar"), True, "1.10.0: a tela mostra o Sim e o Não")
        self.assertIn("na tela do app CorrerIA", self.falsa.pedidos[0])
        r = S.conversar({"texto": "Sim"}, {"id": "person.ana", "nome": "Ana"}, "u-ana")
        self.assertTrue(r["mensagens"][-1]["texto"].startswith("Feito!"))
        self.assertNotIn("confirmar", r["mensagens"][-1], "feito: sem os botões")
        self.assertEqual(self.app.feitos[-1]["cliente"], "CorrerIA")

    def test_conversas_velhas_saem(self):
        """1.7.0: as conversas da tela paradas há mais dias que o escolhido (30 de início) saem, e no WhatsApp as mensagens
        mais velhas que isso; com Nunca, ficam."""
        velha = (datetime.now() - timedelta(days=40)).isoformat(timespec="seconds")
        nova = (datetime.now() - timedelta(days=2)).isoformat(timespec="seconds")
        S._gravar_conversas({"tela": {"u-ana": {"atual": "c-velha", "lista": [
            {"id": "c-velha", "titulo": "Velha", "criada": velha, "atualizada": velha, "mensagens": [{"papel": "eu", "texto": "oi", "em": velha}]},
            {"id": "c-nova", "titulo": "Nova", "criada": nova, "atualizada": nova, "mensagens": [{"papel": "eu", "texto": "oi", "em": nova}]}]},
            "u-beto": {"atual": "c-b", "lista": [{"id": "c-b", "titulo": "Do Beto", "atualizada": velha, "mensagens": []}]},
            "u-antigo": [{"papel": "eu", "texto": "de antes", "em": velha}]},
            "conversas": {"5511999990000": [{"papel": "eu", "texto": "velha", "em": velha}, {"papel": "eu", "texto": "nova", "em": nova}],
                          "5511999990001": [{"papel": "eu", "texto": "velha", "em": velha}]}})
        self.assertEqual(S.ler_config()["apagar_dias"], 30, "30 de início")
        self.assertEqual([x["titulo"] for x in S.conversas_tela("u-ana")], ["Nova"], "a velha nem aparece")
        S.salvar_config({"apagar_dias": 0})
        self.assertEqual(len(S.conversas_tela("u-ana")), 2, "com Nunca, ficam")
        self.assertEqual(S.limpar_conversas_velhas(), 0)
        S.salvar_config({"apagar_dias": 30})  # salvar já limpa
        c = S.ler_json(S.CONVERSAS_ARQ)
        self.assertEqual([x["id"] for x in c["tela"]["u-ana"]["lista"]], ["c-nova"])
        self.assertEqual((c["tela"]["u-ana"]["atual"], "u-beto" in c["tela"], "u-antigo" in c["tela"]), (None, False, False))
        self.assertEqual(c["conversas"], {"5511999990000": [{"papel": "eu", "texto": "nova", "em": nova}]})
        self.assertEqual(S.limpar_conversas_velhas(), 0, "já limpo")
        for ruim in (5, "30", True, None):
            with self.assertRaisesRegex(ValueError, "7, 30 ou 90"):
                S.salvar_config({"apagar_dias": ruim})
        self.assertEqual(S.estado()["apagar_dias"], 30)
        S.salvar_config({"apagar_dias": 7})
        self.assertEqual([x["titulo"] for x in S.conversas_tela("u-ana")], ["Nova"], "a de 2 dias fica com 7")
        S.salvar_config({"apagar_dias": 30})

    def test_pesquisa_na_internet_so_na_tela(self):
        """1.6.0: a conversa da tela pesquisa na internet (uma ferramenta a mais, de leitura); o WhatsApp e o conector não."""
        feitas = []

        def pesquisar(q):
            feitas.append(q)
            if q == "falha":
                raise S.ia.ErroIA("IA Azul ficou sem cota.")
            return "Geladeira Exemplo: R$ 3.999 na Loja Fictícia."
        pesq = {"chamar": [{"ferramenta": "internet_pesquisar", "argumentos": {"pesquisa": "preço da geladeira Exemplo"}}]}
        self.ia(pesq, {"resposta": "Uns R$ 3.999."}, pesquisar=pesquisar)
        r = S.conversar({"texto": "quanto custa a geladeira Exemplo?"}, {"id": "person.ana", "nome": "Ana"}, "u-ana")
        self.assertEqual((r["mensagens"][-1]["texto"], r["mensagens"][-1]["app"]), ("Uns R$ 3.999.", "Internet"))
        self.assertEqual(feitas, ["preço da geladeira Exemplo"])
        self.assertIn("internet_pesquisar | lê | Internet:", self.falsa.pedidos[0])
        self.assertIn("internet_pesquisar({\"pesquisa\": \"preço da geladeira Exemplo\"}) → Geladeira Exemplo: R$ 3.999", self.falsa.pedidos[1])
        self.ia({"chamar": [{"ferramenta": "internet_pesquisar", "argumentos": {"pesquisa": "falha"}}, {"ferramenta": "internet_pesquisar", "argumentos": {}}]},
                {"resposta": "Não deu."}, pesquisar=pesquisar)
        S.conversar({"texto": "pesquisa falha"}, {"id": "person.ana", "nome": "Ana"}, "u-ana")
        self.assertIn("→ ERRO: A pesquisa na internet não deu certo: IA Azul ficou sem cota.", self.falsa.pedidos[1])
        self.assertIn("→ ERRO: Faltou o que pesquisar.", self.falsa.pedidos[1])
        self.ia({"chamar": [{"ferramenta": "internet_pesquisar", "argumentos": {"pesquisa": "x"}}]}, {"resposta": "Por aqui, só os apps."}, pesquisar=pesquisar)
        self.assertEqual(self.mandar("pesquisa x")[0][1], "Por aqui, só os apps.")
        self.assertNotIn("internet_pesquisar |", self.falsa.pedidos[0], "no WhatsApp a IA nem vê a pesquisa")
        self.assertIn("internet_pesquisar → ERRO: essa ferramenta não existe", self.falsa.pedidos[1])
        self.assertEqual(feitas, ["preço da geladeira Exemplo", "falha"])
        self.assertNotIn("internet_pesquisar", [f["id"] for f in S.FERR.todas()], "nem o conector (MCP): o Claude e o Gemini pesquisam sozinhos")

    def test_pesquisar_pelo_home_assistant(self):
        """1.6.0: a pesquisa vai para a IA Para pesquisar na internet (vazia: a de conversar), com o Uso da IA."""
        ha = ServidorFalso({"/api/states": (200, [{"entity_id": "ai_task.ia_azul", "attributes": {"friendly_name": "IA Azul"}}]),
                            "/api/services/ai_task/generate_data": lambda h, c: (200, {"service_response": {"data": "  Achei: R$ 10 no Site Fictício.  "}})})
        self.addCleanup(ha.fechar)
        S._ias_cache.update(t=0.0, v=None)
        self.addCleanup(lambda: S._ias_cache.update(t=0.0, v=None))
        with mock.patch.object(S, "TOKEN", "t"), mock.patch.object(S, "HA_API", ha.url + "/api"):
            self.assertEqual(S.pesquisar_internet("preço do X"), "Achei: R$ 10 no Site Fictício.")
            c = ha.pedidos[-1][3]
            self.assertEqual((c["task_name"], "entity_id" in c), ("CorrerIA · pesquisa", False), "nenhuma escolhida: a padrão")
            self.assertIn("A pesquisa: preço do X", c["instructions"])
            self.assertIn("não responda de memória", c["instructions"])
            S.salvar_config({"ia_entidade": "ai_task.ia_azul"})
            S.pesquisar_internet("y")
            self.assertEqual(ha.pedidos[-1][3]["entity_id"], "ai_task.ia_azul", "vazia: a de conversar")
            with self.assertRaisesRegex(ValueError, "IA desconhecida"):
                S.salvar_config({"ia_pesquisa": "light.sala"})
            S.salvar_config({"ia_pesquisa": "ai_task.ia_verde"})
            self.assertEqual(S.estado()["ias"]["pesquisa"], "ai_task.ia_verde")
            ha.rotas["/api/services/ai_task/generate_data"] = lambda h, c: (200, {"service_response": {"data": {"texto": "ok"}}})
            self.assertEqual(S.pesquisar_internet("z"), '{"texto": "ok"}')
            self.assertEqual(ha.pedidos[-1][3]["entity_id"], "ai_task.ia_verde")
            ult = S.USO.resumo()["ultimas"][0]
            self.assertEqual((ult["tipo"], ult["ia"]), ("pesquisa", "ai_task.ia_verde"))
            ha.rotas["/api/services/ai_task/generate_data"] = (500, {"message": "quota exceeded"})
            with self.assertRaisesRegex(S.ia.ErroIA, "^ai_task.ia_verde ficou sem cota"):
                S.pesquisar_internet("z")
            self.assertEqual(S.USO.resumo()["ultimas"][0]["resultado"], "cota")
            ha.rotas["/api/services/ai_task/generate_data"] = (200, {"service_response": {}})
            with self.assertRaisesRegex(S.ia.ErroIA, "não devolveu"):
                S.pesquisar_internet("z")
            ha.rotas["/api/services/ai_task/generate_data"] = (500, b"pane")
            with self.assertRaisesRegex(S.ia.ErroIA, "O Home Assistant respondeu 500"):
                S.pesquisar_internet("z")
        with mock.patch.object(S, "HA_API", "http://127.0.0.1:9/api"), mock.patch.object(S, "TOKEN", "t"):
            with self.assertRaisesRegex(S.ia.ErroIA, "Não consegui falar com o Home Assistant"):
                S.pesquisar_internet("z")
        with mock.patch.object(S, "DEV", False):
            with self.assertRaisesRegex(S.ia.ErroIA, "Sem o Home Assistant"):
                S.pesquisar_internet("z")
        with mock.patch.object(S, "DEV", True):
            self.assertIn("pesquisa simulada", S.pesquisar_internet("z"))
        S.salvar_config({"ia_entidade": "", "ia_pesquisa": ""})

    def test_chamar_a_ia_do_home_assistant(self):
        ha = ServidorFalso({"/api/services/ai_task/generate_data": lambda h, c: (200, {"service_response": {"data": {"resposta": "ok"}}})})
        self.addCleanup(ha.fechar)
        with mock.patch.object(S, "TOKEN", "t"), mock.patch.object(S, "HA_API", ha.url + "/api"):
            self.assertEqual(S.chamar_ia("Pergunta"), {"resposta": "ok"})
            m, p, h, c = ha.pedidos[-1]
            self.assertEqual((p, h["Authorization"], c), ("/api/services/ai_task/generate_data?return_response", "Bearer t", {"task_name": "CorrerIA", "instructions": "Pergunta"}))
            self.assertTrue(S.estado()["ia"]["ok"])
            ha.rotas["/api/services/ai_task/generate_data"] = (400, {"message": "Nenhuma entidade de IA padrão."})
            with self.assertRaisesRegex(S.ia.ErroIA, "Nenhuma entidade"):
                S.chamar_ia("x")
            self.assertEqual(S.estado()["ia"]["erro"], "Nenhuma entidade de IA padrão.")
            ha.rotas["/api/services/ai_task/generate_data"] = (200, {"service_response": {}})
            with self.assertRaisesRegex(S.ia.ErroIA, "não devolveu"):
                S.chamar_ia("x")
        with self.assertRaisesRegex(S.ia.ErroIA, "Sem o Home Assistant"):
            S.chamar_ia("x")


class TestMcpHttp(Base):
    """O Claude e o Gemini pela porta pública: os metadados, o registro, a página do pedido, a aprovação no painel, o
    token e o MCP com as ferramentas dos apps."""

    def setUp(self):
        super().setUp()
        self.hook = S.ServidorWebhook(("127.0.0.1", 0), S.Webhook)
        threading.Thread(target=self.hook.serve_forever, daemon=True).start()
        self.addCleanup(self.hook.server_close)
        self.addCleanup(self.hook.shutdown)
        self.url = f"http://127.0.0.1:{self.hook.server_address[1]}"
        self.tela = ThreadingHTTPServer(("127.0.0.1", 0), S.Tela)
        threading.Thread(target=self.tela.serve_forever, daemon=True).start()
        self.addCleanup(self.tela.server_close)
        self.addCleanup(self.tela.shutdown)
        self.url_tela = f"http://127.0.0.1:{self.tela.server_address[1]}"
        self.app = AppFalso("GerencIA")
        self.addCleanup(self.app.fechar)
        self.app.publicar(S.SHARE_DIR, "gerencia")

    def j(self, url, metodo="GET", corpo=None, cab=None):
        st, r = pedir(url, metodo, corpo, cab)
        return st, (json.loads(r) if r and r[:1] in (b"{", b"[") else r)

    def conectar(self):
        st, cli = self.j(self.url + "/registrar", "POST", {"client_name": "Claude", "redirect_uris": ["https://claude.ai/api/mcp/auth_callback"],
                                                             "token_endpoint_auth_method": "none"})
        self.assertEqual(st, 201)
        v = secrets.token_urlsafe(48)
        d = base64.urlsafe_b64encode(hashlib.sha256(v.encode()).digest()).rstrip(b"=").decode()
        q = urllib.parse.urlencode({"response_type": "code", "client_id": cli["client_id"], "redirect_uri": "https://claude.ai/api/mcp/auth_callback",
                                    "code_challenge": d, "code_challenge_method": "S256", "state": "s1", "resource": self.url + "/mcp"})
        st, pagina = pedir(f"{self.url}/autorizar?{q}")
        self.assertEqual(st, 200)
        pid = re.search(rb'var id="([^"]+)"', pagina).group(1).decode()
        est = self.j(self.url_tela + "/api/estado")[1]
        pedido = est["mcp"]["pedidos"][0]
        self.assertIn(pedido["codigo"].encode(), pagina, "o mesmo código na página e no painel")
        self.assertEqual(self.j(f"{self.url}/autorizar/estado?p={pid}")[1], {"estado": "esperando"})
        st, est = self.j(self.url_tela + "/api/mcp/decidir", "POST", {"id": pedido["id"], "aprovar": True}, {"X-Remote-User-Id": "u-ana"})
        self.assertEqual((st, est["mcp"]["pedidos"]), (200, []))
        ir = self.j(f"{self.url}/autorizar/estado?p={pid}")[1]["ir"]
        code = urllib.parse.parse_qs(urllib.parse.urlparse(ir).query)["code"][0]
        corpo = urllib.parse.urlencode({"grant_type": "authorization_code", "code": code, "redirect_uri": "https://claude.ai/api/mcp/auth_callback",
                                        "client_id": cli["client_id"], "code_verifier": v}).encode()
        st, tok = self.j(self.url + "/token", "POST", corpo, {"Content-Type": "application/x-www-form-urlencoded"})
        self.assertEqual(st, 200, tok)
        return tok

    def mcp(self, tok, metodo, params=None, mid=1):
        m = {"jsonrpc": "2.0", "method": metodo, **({"params": params} if params is not None else {}), **({"id": mid} if mid is not None else {})}
        return self.j(self.url + "/mcp", "POST", m, {"Authorization": f"Bearer {tok['access_token']}", "Accept": "application/json, text/event-stream"})

    def test_desligado_nada_aparece(self):
        for c in ("/mcp", "/.well-known/oauth-protected-resource", "/.well-known/oauth-authorization-server", "/autorizar"):
            self.assertEqual(pedir(self.url + c)[0], 404, c)
        self.assertEqual(pedir(self.url + "/registrar", "POST", {"redirect_uris": ["https://claude.ai/x"]})[0], 404)

    def test_caminho_todo(self):
        S.salvar_config({"mcp": True, "endereco_mcp": "casa-exemplo.duckdns.org:8443"})
        st, meta = self.j(self.url + "/.well-known/oauth-protected-resource/mcp")
        self.assertEqual((st, meta["resource"], meta["authorization_servers"]), (200, self.url + "/mcp", [self.url]), "o endereço como foi chamado")
        st, srv = self.j(self.url + "/.well-known/oauth-authorization-server")
        self.assertEqual(srv["token_endpoint"], self.url + "/token")
        self.assertEqual(self.j(self.url + "/.well-known/openid-configuration")[1], srv)
        st, r = self.j(self.url + "/mcp", "POST", {"jsonrpc": "2.0", "id": 1, "method": "initialize"})
        self.assertEqual(st, 401)
        req = urllib.request.Request(self.url + "/mcp", data=b"{}", method="POST")
        try:
            urllib.request.urlopen(req, timeout=5)
        except urllib.error.HTTPError as e:
            self.assertEqual(e.headers["WWW-Authenticate"], f'Bearer resource_metadata="{self.url}/.well-known/oauth-protected-resource/mcp"')
        tok = self.conectar()
        est = self.j(self.url_tela + "/api/estado")[1]
        self.assertEqual(est["mcp"]["url"], "https://casa-exemplo.duckdns.org:8443/mcp")
        self.assertEqual([(c["nome"], c["pessoa"]) for c in est["mcp"]["conexoes"]], [("Claude", "Ana")])
        st, r = self.mcp(tok, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "claude"}})
        self.assertEqual((st, r["result"]["serverInfo"]["name"]), (200, "correria"))
        self.assertEqual(self.mcp(tok, "notifications/initialized", mid=None)[0], 202)
        st, r = self.mcp(tok, "tools/list")
        self.assertEqual([t["name"] for t in r["result"]["tools"]], ["gerencia_resumo", "gerencia_lancar", "gerencia_apagar"])
        st, r = self.mcp(tok, "tools/call", {"name": "gerencia_lancar", "arguments": {"descricao": "Feira", "valor": 12}})
        self.assertEqual(r["result"]["isError"], False)
        self.assertEqual((self.app.feitos[-1]["pessoa"]["nome"], self.app.feitos[-1]["cliente"]), ("Ana", "Claude"))
        self.assertEqual(self.registro()[-1], ("mcp", "Claude · Ana", "Lançado: Feira · R$ 12. id: l1"))
        self.assertEqual(pedir(self.url + "/mcp")[0], 405)
        self.assertEqual(pedir(self.url + "/mcp", "DELETE")[0], 405)
        conid = est["mcp"]["conexoes"][0]["id"]
        st, est = self.j(self.url_tela + "/api/mcp/desconectar", "POST", {"id": conid})
        self.assertEqual(est["mcp"]["conexoes"], [])
        self.assertEqual(self.mcp(tok, "tools/list")[0], 401, "desconectado, o token não vale mais")
        S.salvar_config({"mcp": False})
        self.assertEqual(pedir(self.url + "/mcp", "POST", b"{}")[0], 404)

    def test_recusar_e_erros_da_pagina(self):
        S.salvar_config({"mcp": True})
        st, pagina = pedir(self.url + "/autorizar?client_id=c-nada&response_type=code")
        self.assertEqual(st, 400)
        self.assertIn("Não deu para conectar".encode(), pagina)
        st, cli = self.j(self.url + "/registrar", "POST", {"redirect_uris": ["https://claude.ai/volta"]})
        req = urllib.request.Request(f"{self.url}/autorizar?client_id={cli['client_id']}&response_type=code&state=a")
        abridor = urllib.request.build_opener(type("SemSeguir", (urllib.request.HTTPRedirectHandler,), {"redirect_request": lambda *a: None}))
        try:
            abridor.open(req, timeout=5)
            self.fail("devia voltar com o erro")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 302)
            self.assertTrue(e.headers["Location"].startswith("https://claude.ai/volta?error=invalid_request"), "sem PKCE: volta com o erro")
        st, r = self.j(self.url + "/token", "POST", b"grant_type=authorization_code&code=x", {"Content-Type": "application/x-www-form-urlencoded"})
        self.assertEqual((st, r["error"]), (400, "invalid_grant"))
        st, r = self.j(self.url + "/registrar", "POST", b"{x")
        self.assertEqual((st, r["error"]), (400, "invalid_client_metadata"))
        with mock.patch.object(S, "MAX_MCP", 10):
            self.assertEqual(pedir(self.url + "/registrar", "POST", b"x" * 20)[0], 413)
        st, r = self.j(self.url_tela + "/api/mcp/decidir", "POST", {"id": "x", "aprovar": True})
        self.assertEqual(st, 400)
        self.assertIn("não está mais esperando", r["erro"])

    def test_estado_dos_apps(self):
        est = S.estado()
        a = est["apps"][0]
        self.assertEqual((a["app"], a["ferramentas"], a["gravam"], a["conversa"], a["erro"]), ("gerencia", 3, 2, False, ""))
        # 1.15.0: os outros apps da família, sem a opção CorrerIA ligada (sem o correria.json deles)
        fora = est["apps_desligados"]
        self.assertEqual([x["app"] for x in fora], ["cronologia", "economia", "inventario", "memoria", "resolvia"])
        self.assertEqual((fora[0]["nome"], set(fora[0])), ("CronologIA", {"app", "nome", "assunto"}))
        self.assertTrue(all(x["assunto"] and "chave" not in x for x in fora))
        self.assertEqual(est["mcp"], {"ligado": False, "endereco": "", "url": "", "cert_confere": None, "pedidos": [], "conexoes": []})


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

    def test_anota_a_ultima_conexao_de_fora(self):
        """1.11.0: a última conexão que chegou de fora (de um endereço da internet) e se o https fechou; as do próprio
        computador e da rede da casa não contam."""
        ssl_dir = pasta_temp()
        certificado(ssl_dir)
        S.FORA.update(em=None, ok=None, erro="")
        self.addCleanup(S.FORA.update, em=None, ok=None, erro="")
        with mock.patch.object(S, "SSL_DIR", ssl_dir):
            hook = S.ServidorWebhook(("127.0.0.1", 0), S.Webhook)
            threading.Thread(target=hook.serve_forever, daemon=True).start()
            self.addCleanup(hook.server_close)
            self.addCleanup(hook.shutdown)
            ctx = ssl.create_default_context()
            ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE
            url = f"https://127.0.0.1:{hook.server_address[1]}/.well-known/oauth-protected-resource"
            pedir(url, contexto=ctx)
            self.assertIsNone(S.estado()["webhook"]["fora"]["em"], "do próprio computador não conta")

            def esperar(cond):
                fim = time.time() + 3
                while not cond() and time.time() < fim:
                    time.sleep(0.02)
            with mock.patch.object(S, "de_fora", return_value=True):
                with self.assertRaises((urllib.error.URLError, ConnectionError, OSError)):
                    pedir(url.replace("https", "http"))
                esperar(lambda: S.FORA["em"])
                self.assertEqual((S.FORA["ok"], S.FORA["erro"]), (False, "chegou sem https"))
                pedir(url, contexto=ctx)
                esperar(lambda: S.FORA["ok"])
                self.assertEqual((S.FORA["ok"], S.FORA["erro"]), (True, ""))
            self.assertEqual(S.estado()["webhook"]["fora"]["ok"], True)

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

    def test_limpar_e_rotas(self):
        S.registrar("recebida", "Ana", "oi")
        S.registrar("mcp", "Claude · Ana", "Lançado: Feira", "GerencIA", canal="mcp")
        S.registrar("erro", "GerencIA", "Não deu", canal="tela")
        with S.TRAVA:  # uma linha de antes da 0.15.0, sem canal: pelo tipo
            cv = S.ler_conversas()
            cv["registro"].insert(0, {"em": S.agora_iso(), "tipo": "mcp", "quem": "Gemini · Beto", "texto": "Feito", "app": "ResolvIA"})
            S._gravar_conversas(cv)
        e = S.estado()
        self.assertEqual([r["texto"] for r in e["registro"]], ["oi"], "a aba WhatsApp só com o WhatsApp")
        self.assertEqual([r["texto"] for r in e["registro_mcp"]], ["Feito", "Lançado: Feira"], "a aba MCP com o que as IAs mudaram")
        st, e = self.json("/api/registro/limpar", {"canal": "mcp"})
        self.assertEqual((e["registro_mcp"], [r["texto"] for r in e["registro"]]), ([], ["oi"]), "Limpar na aba MCP só apaga as mudanças")
        st, e = self.json("/api/registro/limpar", {})
        self.assertEqual(e["registro"], [])
        self.assertEqual([r["texto"] for r in S.ler_conversas()["registro"]], ["Não deu"], "o da conversa da tela fica só no arquivo")
        self.assertEqual(self.json("/api/nada", {})[0], 404)
        self.assertEqual(self.json("/api/config", [1])[0], 200, "um corpo que não é objeto vale como vazio")

    def test_fala_da_tela(self):
        """O microfone da conversa: o áudio (PCM de 16 kHz) vira texto pela fala para texto; a tela manda o texto depois."""
        st, r = pedir(self.url + "/api/estado")
        self.assertEqual(json.loads(r)["fala_tela"], {"pronta": True, "nome": "Fala simulada (teste)"})
        st, r = pedir(self.url + "/api/fala", "POST", bytes(16000 * 2), {"Content-Type": "application/octet-stream"})
        self.assertEqual((st, json.loads(r)), (200, {"texto": "O que tem na agenda amanhã?"}))
        st, r = pedir(self.url + "/api/fala", "POST", bytes(800), {"Content-Type": "application/octet-stream"})
        self.assertEqual((st, json.loads(r)), (400, {"erro": "Não ouvi nada. Toque no microfone e fale."}))
        st, r = pedir(self.url + "/api/fala", "POST", bytes(S.fala.PCM_MAX + 2), {"Content-Type": "application/octet-stream"})
        self.assertEqual((st, json.loads(r)), (413, {"erro": "Fale até 2 minutos de cada vez."}))
        with mock.patch.object(S.FALA, "texto", side_effect=S.fala.ErroFala("Não entendi o áudio.")):
            st, r = pedir(self.url + "/api/fala", "POST", bytes(32000), {"Content-Type": "application/octet-stream"})
        self.assertEqual((st, json.loads(r)), (400, {"erro": "Não entendi o áudio."}))

    def test_conversa_pela_tela(self):
        self.configurar()
        cab = {"X-Remote-User-Id": "u-beto", "X-Remote-User-Display-Name": "Beto"}
        self.addCleanup(S._gravar_tela, "u-beto", [])
        st, r = pedir(self.url + "/api/conversa", cab=cab)
        self.assertEqual(json.loads(r), {"mensagens": [], "pessoa": "Beto", "ola": "Beto", "conversa": None})
        st, r = pedir(self.url + "/api/conversa", "POST", {"texto": "Quanto gastei?"}, cab)
        self.assertEqual((st, json.loads(r)["mensagens"][-1]["app"]), (200, "GerencIA"))
        st, r = pedir(self.url + "/api/conversa/limpar", "POST", {}, cab)
        self.assertEqual(json.loads(r), {"mensagens": []})
        self.assertEqual(S.conversa_tela("u-beto"), [])
        st, r = pedir(self.url + "/api/conversa", "POST", {"texto": ""}, cab)
        self.assertEqual((st, json.loads(r)["erro"]), (400, "Escreva uma mensagem."))
        # a lista de conversas: nova, abrir e apagar
        pedir(self.url + "/api/conversa", "POST", {"texto": "Primeira"}, cab)
        st, r = pedir(self.url + "/api/conversa/nova", "POST", {}, cab)
        self.assertEqual((st, json.loads(r)["mensagens"]), (200, []))
        pedir(self.url + "/api/conversa", "POST", {"texto": "Segunda"}, cab)
        st, r = pedir(self.url + "/api/conversas", cab=cab)
        lista = json.loads(r)["conversas"]
        self.assertEqual([(x["titulo"], x["aberta"]) for x in lista], [("Segunda", True), ("Primeira", False)])
        st, r = pedir(self.url + "/api/conversa/abrir", "POST", {"id": lista[1]["id"]}, cab)
        self.assertEqual(json.loads(r)["mensagens"][0]["texto"], "Primeira")
        st, r = pedir(self.url + "/api/conversa/apagar", "POST", {"id": lista[1]["id"]}, cab)
        self.assertEqual((json.loads(r)["mensagens"], [x["titulo"] for x in json.loads(r)["conversas"]]), ([], ["Segunda"]))
        st, r = pedir(self.url + "/api/conversa/abrir", "POST", {"id": "nao-existe"}, cab)
        self.assertEqual((st, json.loads(r)["erro"]), (400, "Essa conversa não existe mais."))
        self.addCleanup(lambda: os.path.exists(S.CONVERSAS_ARQ) and os.remove(S.CONVERSAS_ARQ))

    def test_corpo_grande_so_na_conversa(self):
        grande = b'{"texto": "' + b"x" * (1024 * 1024 + 10) + b'"}'
        self.assertEqual(pedir(self.url + "/api/config", "POST", grande)[0], 400)
        self.configurar()
        self.addCleanup(S._gravar_tela, "_", [])
        self.assertEqual(pedir(self.url + "/api/conversa", "POST", grande)[0], 200, "a conversa leva foto e PDF")

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


# ---------------------------------------------------------------------------------------------------------------
class TestCasosRaros(Base):
    """O que quase nunca acontece, mas tem de dar certo: respostas quebradas, o app que saiu, o certificado estragado,
    o aviso no sino, o corpo que não chega inteiro, o registro no computador e o main()."""

    def setUp(self):
        super().setUp()
        self.tela = ThreadingHTTPServer(("127.0.0.1", 0), S.Tela)
        threading.Thread(target=self.tela.serve_forever, daemon=True).start()
        self.addCleanup(self.tela.server_close)
        self.addCleanup(self.tela.shutdown)
        self.url = f"http://127.0.0.1:{self.tela.server_address[1]}"
        self.hook = S.ServidorWebhook(("127.0.0.1", 0), S.Webhook)
        threading.Thread(target=self.hook.serve_forever, daemon=True).start()
        self.addCleanup(self.hook.server_close)
        self.addCleanup(self.hook.shutdown)
        self.url_hook = f"http://127.0.0.1:{self.hook.server_address[1]}"

    def cru(self, porta, cabecalho, corpo):
        """Um pedido que promete mais do que manda e fecha a escrita: a resposta chega mesmo assim."""
        import socket
        s = socket.create_connection(("127.0.0.1", porta), timeout=10)
        try:
            s.sendall(cabecalho.encode() + corpo)
            s.shutdown(socket.SHUT_WR)
            r = b""
            while True:
                b = s.recv(65536)
                if not b:
                    break
                r += b
        finally:
            s.close()
        return int(r.split(b" ", 2)[1]), r.split(b"\r\n\r\n", 1)[1]

    def test_cor_da_casa(self):
        with self.assertRaisesRegex(ValueError, "Cor desconhecida"):
            S.salvar_config({"cor": "amarelo-canario"})
        S.salvar_config({"cor": "turquesa", "cor_dia": False})
        c = S.ler_config()
        self.assertEqual((c["cor"], c["cor_dia"]), ("turquesa", False))
        S.salvar_config({"cor_dia": True})
        self.assertTrue(S.ler_config()["cor_dia"])

    def test_ia_para_conversar(self):
        """0.16.0: a IA que conversa é a escolhida (o entity_id na chamada) e o nome dela aparece no estado, no erro de cota
        (em português) e no Uso da IA. IAs inventadas: IA Azul e IA Verde."""
        estados = [{"entity_id": "ai_task.ia_verde", "attributes": {"friendly_name": "IA Verde"}},
                   {"entity_id": "ai_task.ia_azul", "attributes": {"friendly_name": "IA Azul"}}, {"entity_id": "person.ana", "attributes": {}}]
        ha = ServidorFalso({"/api/states": (200, estados), "/api/services/ai_task/generate_data": lambda h, c: (200, {"service_response": {"data": {"resposta": "ok"}}})})
        self.addCleanup(ha.fechar)
        S._ias_cache.update(t=0.0, v=None)
        self.addCleanup(lambda: S._ias_cache.update(t=0.0, v=None))
        with mock.patch.object(S, "TOKEN", "t"), mock.patch.object(S, "HA_API", ha.url + "/api"):
            self.assertEqual(S.estado()["ias"], {"lista": [{"id": "ai_task.ia_azul", "nome": "IA Azul"}, {"id": "ai_task.ia_verde", "nome": "IA Verde"}], "escolhida": "", "pesquisa": ""})
            self.assertEqual(S.nome_da_ia(), "", "a padrão, com duas: não dá para saber qual")
            S.chamar_ia("Pergunta")
            self.assertNotIn("entity_id", ha.pedidos[-1][3], "a padrão: sem entity_id")
            with self.assertRaisesRegex(ValueError, "IA desconhecida"):
                S.salvar_config({"ia_entidade": "light.sala"})
            S.salvar_config({"ia_entidade": "ai_task.ia_azul"})
            S.chamar_ia("Pergunta")
            self.assertEqual(ha.pedidos[-1][3], {"task_name": "CorrerIA", "instructions": "Pergunta", "entity_id": "ai_task.ia_azul"})
            self.assertEqual((S.estado()["ia"]["nome"], S.estado()["ias"]["escolhida"]), ("IA Azul", "ai_task.ia_azul"))
            ha.rotas["/api/services/ai_task/generate_data"] = (500, {"message": "Error generating content: 429 RESOURCE_EXHAUSTED. You exceeded your current quota."})
            with self.assertRaisesRegex(S.ia.ErroIA, r"^IA Azul ficou sem cota \(o limite de uso acabou\)\. Espere a cota voltar ou escolha outra em IA para conversar\.$"):
                S.chamar_ia("x")
            self.assertEqual(S.estado()["ia"]["erro"][:22], "IA Azul ficou sem cota")
            ult = S.USO.resumo()["ultimas"][0]
            self.assertEqual((ult["ia"], ult["resultado"]), ("IA Azul", "cota"), "o Uso da IA diz qual IA ficou sem cota")
            ha.rotas["/api/services/ai_task/generate_data"] = (500, {"message": "Pane na IA."})
            with self.assertRaisesRegex(S.ia.ErroIA, r"^IA Azul: Pane na IA\.$"):
                S.chamar_ia("x")
            S.salvar_config({"ia_entidade": ""})
            self.assertIsNone(S.ESTADO["ia"], "trocar de IA esquece o que deu com a outra")
            ha.rotas["/api/services/ai_task/generate_data"] = (500, {"message": "quota exceeded"})
            with self.assertRaisesRegex(S.ia.ErroIA, "^A IA padrão do Home Assistant ficou sem cota"):
                S.chamar_ia("x")
            S._ias_cache.update(t=0.0, v=None)
            ha.rotas["/api/states"] = (200, estados[1:])
            self.assertEqual(S.nome_da_ia(), "IA Azul", "a padrão, com uma só: é ela")

    def test_whatsapp_liga_e_desliga(self):
        """0.17.0: o WhatsApp liga e desliga como o conector MCP: sem escolha, ligado se já está configurado; desligado,
        o CorrerIA não responde nem guarda as mensagens."""
        S.salvar_config({"numero_id": "", "token": ""})
        self.assertFalse(S.wa_ligado(S.ler_config()), "nada configurado: desligado")
        S.salvar_config({"numero_id": "109876543210", "token": "EAAtoken-de-teste-0000-1234"})
        self.assertTrue(S.wa_ligado(S.ler_config()), "já configurado (quem atualizou): continua ligado")
        self.assertIsNone(S.ler_config()["whatsapp"], "a escolha não foi gravada: vale a do configurado")
        S.salvar_config({"whatsapp": False})
        c = S.ler_config()
        self.assertFalse(S.wa_ligado(c))
        self.assertFalse(S.estado()["config"]["whatsapp"])
        antes = len(S.ler_conversas()["registro"])
        with mock.patch.object(S, "pessoa_do_numero", return_value={"id": "person.ana", "nome": "Ana"}), mock.patch.object(S, "conta") as conta:
            S.tratar({"id": "wamid.teste-desligado", "from": "5511999990001", "type": "text", "text": {"body": "oi"}}, "Ana", c)
            conta.assert_not_called()
        self.assertEqual(len(S.ler_conversas()["registro"]), antes, "desligado: nada guardado nem respondido")
        S.salvar_config({"whatsapp": True})
        self.assertTrue(S.wa_ligado(S.ler_config()))

    def test_ia_que_responde_estranho(self):
        ha = ServidorFalso({"/api/services/ai_task/generate_data": (500, "pane geral")})
        self.addCleanup(ha.fechar)
        with mock.patch.object(S, "TOKEN", "t"), mock.patch.object(S, "HA_API", ha.url + "/api"):
            with self.assertRaisesRegex(S.ia.ErroIA, "respondeu 500"):
                S.chamar_ia("x")
        from tests.base import porta_livre
        with mock.patch.object(S, "TOKEN", "t"), mock.patch.object(S, "HA_API", f"http://127.0.0.1:{porta_livre()}/api"):
            with self.assertRaisesRegex(S.ia.ErroIA, "Não consegui falar com o Home Assistant"):
                S.chamar_ia("x")
        self.assertFalse(S.estado()["ia"]["ok"])

    def test_o_sim_depois_que_o_app_saiu(self):
        texto, nomes = S.executar([{"ferramenta": "gerencia_lancar", "resumo": "Lançar Feira"}], {"id": "person.ana", "nome": "Ana"}, "WhatsApp")
        self.assertEqual((texto, nomes), ("- Não deu: Lançar Feira (o app não está mais ligado).", []))

    def test_texto_vazio_nao_responde(self):
        self.configurar()
        self.assertIsNone(S.responder_texto(None, ANA_WA, {"id": "person.ana", "nome": "Ana"}, "   "))
        self.assertEqual(self.registro(), [])
        self.assertEqual(self.meta.pedidos, [])

    def test_certificado_estragado_fica_em_http(self):
        ssl_dir = pasta_temp()
        for arq in ("fullchain.pem", "privkey.pem"):
            with open(os.path.join(ssl_dir, arq), "w") as f:
                f.write("isto não é um certificado")
        with mock.patch.object(S, "SSL_DIR", ssl_dir), mock.patch.object(S, "log") as log:
            hook = S.ServidorWebhook(("127.0.0.1", 0), S.Webhook)
            threading.Thread(target=hook.serve_forever, daemon=True).start()
            self.addCleanup(hook.server_close)
            self.addCleanup(hook.shutdown)
            self.assertEqual(pedir(f"http://127.0.0.1:{hook.server_address[1]}/webhook")[0], 403, "responde, em http")
            self.assertTrue(any("certificado inválido" in str(c) for c in log.call_args_list))

    def test_aviso_no_sino_do_home_assistant(self):
        ha = ServidorFalso({"/api/services/persistent_notification/create": (200, []), "/api/services/persistent_notification/dismiss": (200, [])})
        self.addCleanup(ha.fechar)
        cli = S.AUT.registrar({"client_name": "Claude", "redirect_uris": ["https://claude.ai/api/mcp/auth_callback"]})
        d = base64.urlsafe_b64encode(hashlib.sha256(b"v" * 43).digest()).rstrip(b"=").decode()
        with mock.patch.object(S, "TOKEN", "t"), mock.patch.object(S, "HA_API", ha.url + "/api"):
            p = S.AUT.pedir({"response_type": ["code"], "client_id": [cli["client_id"]], "redirect_uri": ["https://claude.ai/api/mcp/auth_callback"],
                             "code_challenge": [d], "code_challenge_method": ["S256"]}, "https://casa-exemplo.duckdns.org:8443")
            self.assertTrue(esperar(lambda: any(x[1].endswith("/create") for x in ha.pedidos)))
            criado = next(x for x in ha.pedidos if x[1].endswith("/create"))[3]
            self.assertEqual(criado["notification_id"], "correria_conectar")
            self.assertIn(p["codigo"], criado["message"])
            st, e = pedir(self.url + "/api/mcp/decidir", "POST", {"id": p["id"], "aprovar": False})
            self.assertEqual(st, 200)
            self.assertTrue(esperar(lambda: any(x[1].endswith("/dismiss") for x in ha.pedidos)), "o aviso some do sino")
        with mock.patch.object(S, "log") as log:
            S._tentar(lambda: (_ for _ in ()).throw(OSError("fora do ar")))
        self.assertIn("fora do ar", str(log.call_args))
        S.avisar_pedido({"nome": "Claude", "codigo": "1234"})  # sem o Home Assistant: nada

    def test_desconectar_o_que_nao_existe_e_erro_inesperado(self):
        st, r = pedir(self.url + "/api/mcp/desconectar", "POST", {"id": "x-nada"})
        self.assertEqual(st, 400)
        with mock.patch.object(S, "ler_conversas", side_effect=RuntimeError("pane")), mock.patch.object(S, "log"):
            st, r = pedir(self.url + "/api/registro/limpar", "POST", {})
        self.assertEqual((st, json.loads(r)), (500, {"erro": "pane"}))

    def test_mcp_ligado_so_aceita_post(self):
        self.assertEqual(pedir(self.url_hook + "/mcp", "DELETE")[0], 404, "desligado: nem existe")
        S.salvar_config({"mcp": True})
        st, _ = pedir(self.url_hook + "/mcp")
        self.assertEqual(st, 405)
        self.assertEqual(pedir(self.url_hook + "/mcp", "DELETE")[0], 405)
        for corpo in (b"{quebrado", b"[1, 2]", json.dumps({"grant_type": "password"}).encode()):
            st, r = pedir(self.url_hook + "/token", "POST", corpo, {"Content-Type": "application/json"})
            self.assertEqual((st, json.loads(r)["error"]), (400, "unsupported_grant_type"), corpo)

    def test_conversa_antiga_sem_mensagens(self):
        self.assertEqual(S._tela_de({"tela": {"u-ana": ["texto solto", 3]}}, "u-ana"), {"atual": None, "lista": []})

    def test_corpo_que_nao_chega_inteiro(self):
        porta = self.tela.server_address[1]
        st, r = self.cru(porta, f"POST /api/config HTTP/1.1\r\nHost: x\r\nContent-Type: application/json\r\nContent-Length: {2 * 1024 * 1024}\r\n\r\n", b"{}")
        self.assertEqual((st, json.loads(r)), (400, {"erro": "Pedido grande demais."}))
        st, r = self.cru(porta, f"POST /api/fala HTTP/1.1\r\nHost: x\r\nContent-Type: application/octet-stream\r\nContent-Length: {S.fala.PCM_MAX + 10}\r\n\r\n", b"\0" * 10)
        self.assertEqual(st, 413)
        st, r = pedir(self.url + "/api/config", "POST", b"{quebrado")
        self.assertEqual((st, json.loads(r)), (400, {"erro": "Pedido inválido."}))

    def test_registro_dos_pedidos_no_computador(self):
        with mock.patch.object(S, "DEV", True), mock.patch.object(S, "LOG_HTTP", True), mock.patch.object(S, "log") as log:
            pedir(self.url + "/api/estado")
            pedir(self.url_hook + "/nada")
        txt = " ".join(str(c) for c in log.call_args_list)
        self.assertIn("/api/estado", txt)
        self.assertIn("Webhook:", txt)

    def test_main_sobe_os_dois_servidores(self):
        subidos = []

        class Falso:
            daemon_threads = False

            def __init__(self, endereco, handler):
                subidos.append((endereco, handler))

            def serve_forever(self):
                pass
        with mock.patch.object(S, "ServidorWebhook", Falso), mock.patch.object(S, "ThreadingHTTPServer", Falso), \
                mock.patch.object(S, "log") as log:
            S.main()
        self.assertEqual(subidos, [(("0.0.0.0", S.PORTA_WEBHOOK), S.Webhook), (("0.0.0.0", S.PORTA), S.Tela)])
        self.assertIn(f"CorrerIA {S.VERSAO}", str(log.call_args_list[-1]))


if __name__ == "__main__":
    unittest.main()


# ---------------------------------------------------------------------------------------------------------------
class TestTunel(unittest.TestCase):
    """1.13.0: a porta do túnel da Cloudflare (o app Cloudflared): as mesmas rotas, em http e só na rede de casa; o
    endereço que o CorrerIA diz é https (o da Cloudflare); quem chamou vem no CF-Connecting-IP."""

    def setUp(self):
        S.FORA.update(em=None, ok=None, erro="", via="")
        S.TUNEL["em"] = None
        self.addCleanup(S.ligar_tunel, False)
        self.addCleanup(S.FORA.update, em=None, ok=None, erro="", via="")
        p = mock.patch.object(S, "PORTA_TUNEL", 0)  # uma porta livre
        p.start()
        self.addCleanup(p.stop)

    def url(self, caminho):
        return f"http://127.0.0.1:{S.SERVIDOR_TUNEL['s'].server_address[1]}{caminho}"

    def pedir(self, caminho, **cab):
        req = urllib.request.Request(self.url(caminho), headers=cab)
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.loads(r.read())

    def test_o_endereco_e_o_da_cloudflare(self):
        S.ligar_tunel(True)
        S.ligar_tunel(True)  # de novo: a mesma porta
        with mock.patch.object(S, "ler_config", return_value={**S.ler_config(), "mcp": True, "endereco": "https://casa-exemplo.duckdns.org:8443", "endereco_mcp": "https://correria.casa-exemplo.com.br"}):
            j = self.pedir("/.well-known/oauth-authorization-server", Host="correria.casa-exemplo.com.br", **{"CF-Connecting-IP": "8.8.8.8"})
            self.assertEqual(j["issuer"], "https://correria.casa-exemplo.com.br", "https, sem porta")
            self.assertEqual((S.FORA["via"], S.FORA["ok"]), ("tunel", True))
            self.assertIsNotNone(S.TUNEL["em"])
            for host in ("192.168.0.10:8444", "a1b2c3d4-correria:8444", "[::1]:8444", ""):
                with self.subTest(host=host):
                    j = self.pedir("/.well-known/oauth-authorization-server", Host=host)
                    self.assertEqual(j["issuer"], "https://correria.casa-exemplo.com.br", "um nome de dentro: o endereço público")
            w = S.estado()["webhook"]["tunel"]
            self.assertEqual((w["aberto"], w["porta"]), (True, 0))

    def test_sem_o_cabecalho_da_cloudflare_nao_conta_de_fora(self):
        S.ligar_tunel(True)
        with mock.patch.object(S, "ler_config", return_value={**S.ler_config(), "mcp": True, "endereco": "https://casa-exemplo.duckdns.org:8443", "endereco_mcp": "https://correria.casa-exemplo.com.br"}):
            self.pedir("/.well-known/oauth-authorization-server", Host="correria.casa-exemplo.com.br")
            self.pedir("/.well-known/oauth-authorization-server", Host="correria.casa-exemplo.com.br", **{"CF-Connecting-IP": "192.168.0.7"})
        self.assertIsNone(S.TUNEL["em"], "de dentro de casa não é de fora")

    def test_liga_e_desliga_pela_tela(self):
        with mock.patch.object(S, "gravar_config"), mock.patch.object(S, "ler_config", return_value=S.ler_config()):
            S.salvar_config({"tunel": True})
        self.assertIsNotNone(S.SERVIDOR_TUNEL["s"])
        S.ligar_tunel(False)
        self.assertIsNone(S.SERVIDOR_TUNEL["s"])
        S.ligar_tunel(False)  # já fechada: nada
        self.assertIsNone(S.SERVIDOR_TUNEL["s"])

    def test_a_porta_ocupada_nao_derruba(self):
        ocupada = socket.socket()
        ocupada.bind(("0.0.0.0", 0))
        ocupada.listen(1)
        self.addCleanup(ocupada.close)
        with mock.patch.object(S, "PORTA_TUNEL", ocupada.getsockname()[1]), mock.patch.object(S, "log") as log:
            S.ligar_tunel(True)
        self.assertIsNone(S.SERVIDOR_TUNEL["s"])
        self.assertIn("não consegui abrir a porta", " ".join(map(str, log.call_args.args)))

    def test_o_ip(self):
        self.assertTrue(S._e_ip("192.168.0.1") and S._e_ip("::1"))
        self.assertFalse(S._e_ip("correria.casa-exemplo.com.br"))


class TestCaminhoDeFora(unittest.TestCase):
    """1.11.0: o que ajuda a achar o que falta para chegar de fora (o Duck DNS, o roteador ou o certificado)."""

    def test_de_fora(self):
        for ip in ("8.8.8.8", "::ffff:8.8.8.8", "2001:4860:4860::8888"):
            self.assertTrue(S.de_fora(ip), ip)
        for ip in ("127.0.0.1", "192.168.0.2", "10.1.2.3", "100.64.1.1", "::1", "::ffff:192.168.1.1", "fe80::1%eth0", "nada", ""):
            self.assertFalse(S.de_fora(ip), ip)

    def test_motivo_tls(self):
        def erro(reason):
            e = ssl.SSLError(1, reason)
            e.reason = reason
            return e
        self.assertEqual(S.motivo_tls(erro("SSLV3_ALERT_CERTIFICATE_UNKNOWN")), "o aparelho recusou o certificado")
        self.assertEqual(S.motivo_tls(erro("TLSV1_ALERT_UNKNOWN_CA")), "o aparelho recusou o certificado")
        self.assertEqual(S.motivo_tls(erro("HTTP_REQUEST")), "chegou sem https")
        self.assertEqual(S.motivo_tls(erro("WRONG_VERSION_NUMBER")), "chegou sem https")
        self.assertEqual(S.motivo_tls(socket.timeout("timed out")), "demorou demais")
        self.assertEqual(S.motivo_tls(ConnectionResetError("reset")), "o https não fechou")

    def test_o_certificado_e_do_endereco(self):
        self.assertIs(S.certificado_confere("https://casa-exemplo.duckdns.org:8443", "casa-exemplo.duckdns.org"), True)
        self.assertIs(S.certificado_confere("https://Casa-Exemplo.duckdns.org", "casa-exemplo.duckdns.org"), True)
        self.assertIs(S.certificado_confere("https://casa-exemplo.duckdns.org", "outra-casa.duckdns.org"), False)
        self.assertIs(S.certificado_confere("https://casa-exemplo.duckdns.org", "*.duckdns.org"), True)
        self.assertIs(S.certificado_confere("https://x.casa-exemplo.duckdns.org", "*.duckdns.org"), False)
        self.assertIsNone(S.certificado_confere("", "casa-exemplo.duckdns.org"))
        self.assertIsNone(S.certificado_confere("https://casa-exemplo.duckdns.org", ""))

    def test_no_estado(self):
        from datetime import datetime, timezone
        vence = datetime(2027, 1, 1, tzinfo=timezone.utc)
        with mock.patch.object(S, "certificado", return_value=("/ssl/fullchain.pem", "/ssl/privkey.pem")), \
                mock.patch.object(S, "validade_certificado", return_value=(vence, "outra-casa.duckdns.org")), \
                mock.patch.object(S, "ler_config", return_value={**S.ler_config(), "endereco": "https://casa-exemplo.duckdns.org:8443"}):
            w = S.estado()["webhook"]
        self.assertEqual((w["cert_nome"], w["cert_vence"], w["cert_confere"]), ("outra-casa.duckdns.org", "2027-01-01T00:00:00+00:00", False))
        with mock.patch.object(S, "certificado", return_value=None):
            w = S.estado()["webhook"]
        self.assertEqual((w["cert_nome"], w["cert_vence"], w["cert_confere"]), ("", None, None))


class TestSensores(Base):
    """0.14.0: sensor.correria_certificado e binary_sensor.correria_whatsapp, com Sensores ligado."""

    def setUp(self):
        super().setUp()
        self.ha = ServidorFalso({f"/api/states/{e}": (200, {}) for e in S.SENSORES})
        self.addCleanup(self.ha.fechar)
        for alvo, valor in (("TOKEN", "t"), ("HA_API", self.ha.url + "/api")):
            p = mock.patch.object(S, alvo, valor)
            p.start()
            self.addCleanup(p.stop)
        S._sensores.update(sig=None, em=0.0, erro=False, conferido=0.0)
        S.ESTADO["conta_erro"] = ""
        self.ssl = pasta_temp()
        p = mock.patch.object(S, "SSL_DIR", self.ssl)
        p.start()
        self.addCleanup(p.stop)

    def enviados(self, metodo="POST"):
        return {p[1].split("/states/")[1]: p[3] for p in self.ha.pedidos if p[0] == metodo}

    def test_certificado_e_whatsapp(self):
        certificado(self.ssl)
        self.configurar(pessoas=False, app=False)
        S.salvar_config({"sensores": True})
        S.rodada_sensores()
        s = self.enviados()
        c = s["sensor.correria_certificado"]
        self.assertIn(c["state"], (1, 2), "o certificado de teste vale 2 dias")
        self.assertEqual((c["attributes"]["unit_of_measurement"], c["attributes"]["device_class"], c["attributes"]["arquivo"]), ("d", "duration", "fullchain.pem"))
        self.assertEqual(c["attributes"]["icon"], "mdi:certificate", "perto de vencer")
        self.assertTrue(c["attributes"]["vence"])
        w = s["binary_sensor.correria_whatsapp"]
        self.assertEqual((w["state"], w["attributes"]["nome"], w["attributes"]["respondendo"], w["attributes"]["erro"]), ("on", "CorrerIA Code", True, None))
        self.assertEqual(w["attributes"]["device_class"], "connectivity")
        self.assertNotIn("4000", json.dumps(w), "o número não vai para o sensor")
        n = len(self.ha.pedidos)
        S.rodada_sensores()
        self.assertEqual(len(self.ha.pedidos), n, "nada mudou: não manda de novo (e a Meta só a cada 30 minutos)")

    def test_token_vencido_desliga_o_whatsapp(self):
        self.configurar(pessoas=False, app=False)
        S.salvar_config({"sensores": True})
        self.meta.rotas[f"/{MetaFalsa.NUMERO_ID}"] = (401, {"error": {"code": 190, "message": "expirou"}})
        S.rodada_sensores()
        s = self.enviados()
        self.assertEqual(s["sensor.correria_certificado"]["state"], "unknown", "sem certificado em /ssl")
        w = s["binary_sensor.correria_whatsapp"]
        self.assertEqual(w["state"], "off")
        self.assertIn("token do WhatsApp venceu", w["attributes"]["erro"])

    def test_sem_whatsapp_configurado(self):
        S.salvar_config({"sensores": True})
        S.rodada_sensores()
        w = self.enviados()["binary_sensor.correria_whatsapp"]
        self.assertEqual((w["state"], w["attributes"]["erro"]), ("off", "Falta configurar o WhatsApp."))

    def test_desligado_tira_uma_vez(self):
        S.rodada_sensores()
        self.assertEqual(set(self.enviados("DELETE")), set(S.SENSORES))
        n = len(self.ha.pedidos)
        S.rodada_sensores()
        self.assertEqual(len(self.ha.pedidos), n, "já tirados")
        S.salvar_config({"sensores": True})
        S.rodada_sensores()
        self.assertIn("binary_sensor.correria_whatsapp", self.enviados())
        self.assertTrue(S.estado()["sensores"]["ligado"])

    def test_ligar_e_desligar_pela_tela_na_hora(self):
        S.salvar_config({"sensores": True})
        for _ in range(50):
            if len(self.enviados()) == 2:
                break
            time.sleep(0.05)
        self.assertEqual(len(self.enviados()), 2)
        S.salvar_config({"sensores": False})
        for _ in range(50):
            if len(self.enviados("DELETE")) == 2:
                break
            time.sleep(0.05)
        self.assertEqual(set(self.enviados("DELETE")), set(S.SENSORES))

    def test_home_assistant_fora_avisa_uma_vez(self):
        S.salvar_config({"sensores": True})
        with mock.patch.object(S, "HA_API", "http://127.0.0.1:9/api"), mock.patch.object(S, "log") as log:
            S.publicar_sensores()
            S.publicar_sensores()
            S.remover_sensores()
        self.assertEqual(log.call_count, 1)
        self.assertIsNone(S._sensores["sig"])

    def test_sem_home_assistant_nada(self):
        with mock.patch.object(S, "TOKEN", None):
            S.salvar_config({"sensores": True})
            S.publicar_sensores()
            S.remover_sensores()
        self.assertEqual(self.ha.pedidos, [])

    def test_certificado_que_nao_abre(self):
        with open(os.path.join(self.ssl, "fullchain.pem"), "w") as f:
            f.write("lixo")
        self.assertEqual(S.validade_certificado(os.path.join(self.ssl, "fullchain.pem")), (None, ""))
