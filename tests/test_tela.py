"""A tela do CorrerIA num Chromium (Playwright), com o servidor de verdade e a Meta e o GerencIA de mentira: configurar
o WhatsApp (o token nunca volta para a tela), o webhook, quem conversa, os apps, Conversar com a IA, as últimas mensagens,
o Sobre, o tema e o celular (390 px). Pessoas e números inventados (Ana, Beto)."""
import base64
import hashlib
import json
import os
import secrets
import urllib.parse
import shutil
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest import mock

from playwright.sync_api import sync_playwright

from tests.base import importar_servidor, AppFalso, MetaFalsa, ServidorFalso, ANA
S = importar_servidor()
import apps  # noqa: E402

TOKEN = "EAAtoken-de-teste-0000-1234"


class Tela(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.meta = MetaFalsa()
        cls.app = ServidorFalso({"/api/integracao/conversa": lambda h, c: (200, {"resposta": f"Você gastou **R$ 123,45**, {c['pessoa']['nome']}.\n\n- Mercado: R$ 100,00\n- Farmácia: R$ 23,45"})})
        cls.patches = [mock.patch.object(S, "GRAPH", cls.meta.url), mock.patch.object(S, "APPS", apps.Apps(S.SHARE_DIR, S.log, cache=0))]
        for p in cls.patches:
            p.start()
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), S.Tela)
        cls.srv.daemon_threads = True
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.url = f"http://127.0.0.1:{cls.srv.server_address[1]}/"
        cls.pw = sync_playwright().start()
        cls.nav = cls.pw.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls.nav.close()
        cls.pw.stop()
        cls.srv.shutdown()
        cls.srv.server_close()
        for p in cls.patches:
            p.stop()
        cls.meta.fechar()
        cls.app.fechar()

    def setUp(self):
        for arq in (S.CONFIG_ARQ, S.CONVERSAS_ARQ, S.MCP_ARQ):
            if os.path.exists(arq):
                os.remove(arq)
        S.AUT.pedidos.clear()
        S.AUT.codigos.clear()
        shutil.rmtree(S.SHARE_DIR, ignore_errors=True)
        os.makedirs(S.SHARE_DIR)
        S.ESTADO.update(ultimo_webhook=None, verificado_em=None, conta=None, conta_em=None)
        self.meta.pedidos.clear()
        self.app.pedidos.clear()
        self.erros = []
        S._gravar_tela("_", [])

    def abrir(self, tema="dark"):
        self.pg = self.nav.new_page(viewport={"width": 390, "height": 844}, color_scheme=tema)
        self.addCleanup(self.pg.close)
        self.pg.on("pageerror", lambda e: self.erros.append(str(e)))
        self.pg.set_default_timeout(5000)
        self.pg.goto(self.url)
        self.pg.wait_for_selector("#whatsapp")
        self.addCleanup(lambda: self.assertEqual(self.erros, [], "nenhum erro na página"))

    def texto(self, sel):
        return self.pg.inner_text(sel).strip()

    def aviso(self, esperado):
        self.pg.wait_for_function("t => document.querySelector('#toast').classList.contains('on') && document.querySelector('#toast').textContent === t", arg=esperado)

    def publicar_app(self):
        os.makedirs(os.path.join(S.SHARE_DIR, "gerencia"), exist_ok=True)
        with open(os.path.join(S.SHARE_DIR, "gerencia", "correria.json"), "w") as f:
            json.dump({"app": "gerencia", "nome": "GerencIA", "assunto": "finanças da casa", "rota": "/api/integracao/conversa",
                       "url": self.app.url, "chave": "chave-" + "x" * 30, "versao": "1.37.0", "anexos": ["application/pdf", "image/jpeg", "image/png"]}, f)

    # ------------------------------------------------------------------------------------------------
    def test_comeca_pedindo_a_configuracao(self):
        self.abrir()
        self.assertEqual(self.texto(".cab h1"), "Contato da CorrerIA Code")
        self.assertEqual(self.texto(".sync"), "Falta terminar a configuração")
        self.assertEqual(self.texto("#whatsapp .status"), "Falta configurar: o ID do número, o token e a chave secreta.")
        self.assertTrue(self.pg.is_disabled('[data-a="conferir"]'), "sem configurar, nada a conferir")
        self.assertEqual(self.pg.locator('[data-a="ligado"]').count(), 0)
        self.assertFalse(self.pg.evaluate("document.documentElement.scrollWidth > innerWidth"), "nada sai da tela no celular")

    def test_salvar_confere_com_a_meta_e_o_token_nao_volta(self):
        self.abrir()
        self.pg.fill("#f-numero", MetaFalsa.NUMERO_ID)
        self.pg.fill("#f-token", TOKEN)
        self.pg.fill("#f-segredo", "segredo-do-app-123")
        self.pg.click('[data-a="salvar"]')
        self.aviso("Conferido com a Meta")
        self.assertEqual(self.texto("#whatsapp .status"), "+55 11 4000-0000 · CorrerIA Code")
        self.assertEqual(self.pg.input_value("#f-token"), "", "o campo volta vazio")
        self.assertEqual(self.pg.get_attribute("#f-token", "placeholder"), "••••1234 · cole outro para trocar")
        self.assertNotIn(TOKEN, self.pg.content(), "o token nunca aparece")
        self.assertEqual(S.ler_config()["token"], TOKEN)
        self.assertEqual(self.pg.get_attribute("#f-token", "type"), "password")

    def test_erro_da_meta_aparece(self):
        S.salvar_config({"numero_id": MetaFalsa.NUMERO_ID, "token": TOKEN, "segredo": "segredo-do-app-123"})
        self.meta.rotas[f"/{MetaFalsa.NUMERO_ID}"] = (401, {"error": {"code": 190, "message": "x"}})
        self.addCleanup(self.meta.rotas.__setitem__, f"/{MetaFalsa.NUMERO_ID}", (200, {"display_phone_number": "+55 11 4000-0000", "verified_name": "CorrerIA Code"}))
        self.abrir()
        self.assertEqual(self.texto("#whatsapp .status"), "Configurado. Toque em Conferir para testar com a Meta.")
        self.pg.click('[data-a="conferir"]')
        self.aviso("O token do WhatsApp venceu ou está errado. Gere um token que não vence (Usuário do sistema) e cole de novo.")

    def test_pausar(self):
        S.salvar_config({"numero_id": MetaFalsa.NUMERO_ID, "token": TOKEN, "segredo": "segredo-do-app-123"})
        self.abrir()
        self.pg.click('[data-a="ligado"]')
        self.aviso("Respostas pausadas")
        self.assertFalse(S.ler_config()["ligado"])
        self.assertIn("Pausado", self.texto("#whatsapp .linha-sw"))
        self.pg.click('[data-a="ligado"]')
        self.aviso("Respondendo")
        self.assertTrue(S.ler_config()["ligado"])

    def test_webhook_endereco_e_copiar(self):
        self.abrir()
        self.assertEqual(self.pg.locator("#f-url").count(), 0, "sem o endereço, nada para colar na Meta")
        v = S.ler_config()["verificacao"]
        self.assertEqual(self.pg.input_value("#f-verif"), v)
        self.pg.fill("#f-endereco", "casa-exemplo.duckdns.org:8443/webhook")
        self.pg.press("#f-endereco", "Tab")
        self.aviso("Endereço salvo")
        self.assertEqual(self.pg.input_value("#f-url"), "https://casa-exemplo.duckdns.org:8443/webhook")
        self.assertEqual(self.pg.input_value("#f-endereco"), "https://casa-exemplo.duckdns.org:8443")
        self.pg.click('[data-a="copiar"][data-v="f-url"]')
        self.pg.wait_for_function("['Copiado', 'Toque e segure no texto para copiar'].includes(document.querySelector('#toast').textContent)")
        self.assertIn("Sem certificado", self.texto("#webhook"))
        self.assertIn("A Meta ainda não chamou.", self.texto("#webhook"))
        self.pg.fill("#f-endereco", "https:// nada")
        self.pg.press("#f-endereco", "Tab")
        self.aviso("Endereço inválido. Ex.: https://casa-exemplo.duckdns.org:8443")

    def test_quem_conversa(self):
        self.abrir()
        self.assertEqual(self.pg.locator("#pessoas .pessoa b").all_inner_texts(), ["Ana", "Beto"])
        self.pg.fill('[data-pessoa="person.ana"]', "(11) 98765-0001")
        self.pg.press('[data-pessoa="person.ana"]', "Tab")
        self.aviso("Número salvo")
        self.assertEqual(self.pg.input_value('[data-pessoa="person.ana"]'), "+55 11 98765-0001")
        self.assertEqual(S.ler_config()["pessoas"], {"person.ana": ANA})
        self.pg.fill('[data-pessoa="person.beto"]', "123")
        self.pg.press('[data-pessoa="person.beto"]', "Tab")
        self.aviso("Número inválido. Use o código do país e o DDD: 55 11 99999-0000.")
        self.pg.fill('[data-pessoa="person.ana"]', "")
        self.pg.press('[data-pessoa="person.ana"]', "Tab")
        self.aviso("Número tirado")
        self.assertEqual(S.ler_config()["pessoas"], {})

    def test_audio_sem_fala_para_texto(self):
        self.publicar_app()
        with mock.patch.object(S.FALA, "status", return_value={"pronta": False, "motivo": "O Home Assistant não tem fala para texto (Configurações › Assistentes de voz)."}):
            self.abrir()
            self.assertEqual(self.texto("#apps .status"), "Áudio: O Home Assistant não tem fala para texto (Configurações › Assistentes de voz).")
            self.assertTrue(self.pg.evaluate("document.querySelector('#apps .status').classList.contains('manual')"))

    def test_sem_app_explica_e_sem_conversa(self):
        self.abrir()
        self.assertIn("Nenhum app ligado. Em cada app, ligue Mais › Configurações › Integrações › CorrerIA.", self.texto("#apps"))
        self.assertEqual(self.pg.locator('[data-a="conversa"]').count(), 0, "sem app, nada para conversar")

    def test_apps_que_respondem(self):
        self.publicar_app()
        self.abrir()
        self.assertEqual(self.texto("#apps .app-l b"), "GerencIA")
        self.assertEqual(self.texto("#apps h2"), "Apps da casa")
        self.assertEqual(self.texto("#apps .app-l .le"), "Responde; também lê fotos e PDF.")
        self.assertEqual(self.texto("#apps .status"), "Áudio: ouve pela fala para texto Fala simulada (teste).")

    def test_apps_com_ferramentas(self):
        app = AppFalso("CronologIA")
        self.addCleanup(app.fechar)
        app.publicar(S.SHARE_DIR, "cronologia")
        self.abrir("light")
        self.assertEqual(self.texto("#apps .app-l .le"), "Lê e muda.")
        self.assertEqual(self.pg.locator("#apps .status").all_inner_texts()[0], "IA simulada (fora do Home Assistant).")
        app.chave = "outra"
        S.APPS._ferr.clear()
        self.pg.reload()
        self.pg.wait_for_selector("#apps")
        self.assertEqual(self.texto("#apps .app-l .le"), "O CronologIA recusou a chave. Confira se a opção do CorrerIA está ligada nele.")

    # ---- Claude e Gemini
    def pedido(self):
        cli = S.AUT.registrar({"client_name": "Claude", "redirect_uris": ["https://claude.ai/api/mcp/auth_callback"], "token_endpoint_auth_method": "none"})
        v = secrets.token_urlsafe(48)
        d = base64.urlsafe_b64encode(hashlib.sha256(v.encode()).digest()).rstrip(b"=").decode()
        p = S.AUT.pedir({"response_type": ["code"], "client_id": [cli["client_id"]], "code_challenge": [d], "code_challenge_method": ["S256"]}, "https://x")
        return cli, v, p

    def test_claude_e_gemini(self):
        self.abrir()
        self.assertEqual(self.texto("#mcp h2"), "Claude e Gemini")
        self.assertIn("Desligado.", self.texto("#mcp"))
        self.assertEqual(self.pg.locator("#f-mcp").count(), 0)
        self.pg.click('[data-a="mcp"]')
        self.aviso("Claude e Gemini ligados")
        self.assertTrue(S.ler_config()["mcp"])
        self.assertEqual(self.texto("#mcp .status"), "Escreva o endereço público no cartão Webhook.")
        self.pg.fill("#f-endereco", "casa-exemplo.duckdns.org:8443")
        self.pg.press("#f-endereco", "Tab")
        self.aviso("Endereço salvo")
        self.assertEqual(self.pg.input_value("#f-mcp"), "https://casa-exemplo.duckdns.org:8443/mcp")
        self.assertIn("Adicionar conector personalizado", self.texto("#mcp .passos"))
        cli, v, p = self.pedido()
        self.pg.wait_for_selector(".pedido", timeout=8000)  # aparece sozinho (a tela confere a cada 4 segundos)
        self.assertEqual(self.texto(".aviso-topo"), "Claude quer se conectar")
        self.assertEqual(self.texto(".pedido .pedido-t"), f"Claude quer se conectar\nCódigo {p['codigo']} · claude.ai")
        larg = self.pg.evaluate("[...document.querySelectorAll('.pedido .btns .btn')].map(b => Math.round(b.getBoundingClientRect().width))")
        self.assertEqual(len(set(larg)), 1, "Recusar e Aprovar do mesmo tamanho")
        self.pg.click('[data-a="mcp-aprovar"]')
        self.aviso("Aprovado: volte para o Claude ou o Gemini")
        self.assertEqual(S.AUT.situacao(p["id"])["estado"], "aprovado")
        self.assertEqual(self.pg.locator(".pedido").count(), 0)
        code = urllib.parse.parse_qs(urllib.parse.urlparse(S.AUT.situacao(p["id"])["ir"]).query)["code"][0]
        S.AUT.trocar({"grant_type": "authorization_code", "code": code, "client_id": cli["client_id"], "code_verifier": v})
        self.pg.reload()
        self.pg.wait_for_selector(".conexao")
        self.assertRegex(self.texto(".conexao-t"), r"^Claude\nVocê · usou hoje às \d\d:\d\d$")
        self.assertEqual(self.pg.locator("#mcp .passos").count(), 0, "conectado, sem o passo a passo")
        self.assertFalse(self.pg.evaluate("document.documentElement.scrollWidth > innerWidth"))
        self.pg.click('[data-a="mcp-desconectar"]')
        self.aviso("Desconectado")
        self.assertEqual(S.AUT.conexoes(), [])

    def test_recusar_pelo_aviso_no_alto(self):
        S.salvar_config({"mcp": True})
        _, _, p = self.pedido()
        self.abrir("light")
        self.pg.click(".aviso-topo")
        self.pg.click('[data-a="mcp-recusar"]')
        self.aviso("Recusado")
        self.assertEqual(S.AUT.situacao(p["id"])["estado"], "recusado")
        self.assertEqual(self.pg.locator(".aviso-topo").count(), 0)

    # ---- Conversar com a IA
    def abrir_conversa(self):
        self.publicar_app()
        self.abrir()
        self.pg.click('.bt-topo[data-a="conversa"]')
        self.pg.wait_for_selector("#ch-txt")

    def test_conversar_com_a_ia(self):
        self.abrir_conversa()
        self.assertEqual(self.texto(".cab-tela h1"), "Conversa")
        self.assertEqual(self.pg.locator(".ch-sug .chip").all_inner_texts(), ["Quanto gastei este mês?", "O que vence esta semana?"])
        self.pg.click('[data-a="ch-enviar"]')  # vazio: nada
        self.assertEqual(self.app.pedidos, [])
        self.pg.fill("#ch-txt", "Quanto gastei?")
        self.pg.click('[data-a="ch-enviar"]')
        self.pg.wait_for_selector(".ch-msg.ia .ch-bolha p")
        self.assertEqual(self.texto(".ch-msg.eu .ch-bolha"), "Quanto gastei?")
        self.assertEqual(self.pg.inner_html(".ch-msg.ia .ch-bolha"), "<p>Você gastou <b>R$ 123,45</b>, Você.</p><ul><li>Mercado: R$ 100,00</li><li>Farmácia: R$ 23,45</li></ul>",
                         "negrito e lista do jeito do WhatsApp")
        self.assertEqual(self.texto(".ch-app"), "GerencIA")
        self.assertEqual(self.pg.input_value("#ch-txt"), "")
        self.assertEqual(self.app.pedidos[0][3]["canal"], "correria")
        self.assertEqual(self.meta.pedidos, [], "não passa pela Meta")
        self.assertFalse(self.pg.evaluate("document.documentElement.scrollWidth > innerWidth"))

    def test_sugestao_e_conversa_guardada(self):
        self.abrir_conversa()
        self.pg.click('[data-a="ch-sug"] >> nth=1')
        self.pg.wait_for_selector(".ch-msg.ia")
        self.assertEqual(self.app.pedidos[0][3]["texto"], "O que vence esta semana?")
        self.pg.reload()
        self.pg.wait_for_selector(".bt-topo")
        self.pg.click('.bt-topo')
        self.pg.wait_for_selector(".ch-msg.ia")
        self.assertEqual(self.pg.locator(".ch-msg").count(), 2, "fechou, abre de onde parou")
        self.pg.click('[data-a="ch-limpar"]')
        self.aviso("Conversa apagada")
        self.pg.wait_for_selector(".ch-vazio")

    def test_mandar_uma_foto(self):
        self.abrir_conversa()
        with self.pg.expect_file_chooser() as fc:
            self.pg.click('[data-a="ch-anexar"]')
        fc.value.set_files(files=[{"name": "nota.jpg", "mimeType": "image/jpeg", "buffer": b"\xff\xd8\xff\xe0foto"}])
        self.pg.wait_for_selector(".ch-prev")
        self.assertEqual(self.texto(".ch-prev span"), "nota.jpg")
        self.pg.fill("#ch-txt", "Quanto deu?")
        self.pg.click('[data-a="ch-enviar"]')
        self.pg.wait_for_selector(".ch-msg.ia")
        c = self.app.pedidos[0][3]
        self.assertEqual((c["texto"], c["anexo"]["tipo"], c["anexo"]["nome"]), ("Quanto deu?", "image/jpeg", "nota.jpg"))
        self.assertEqual(self.texto(".ch-msg.eu .ch-anexo"), "nota.jpg")
        self.assertEqual(self.pg.locator(".ch-prev").count(), 0)

    def test_voltar_do_celular_volta_para_a_casa(self):
        self.abrir_conversa()
        self.pg.go_back()
        self.pg.wait_for_selector("#whatsapp")
        self.pg.click('[data-a="conversa"] >> nth=0')
        self.pg.wait_for_selector("#ch-txt")
        self.pg.click('[data-a="voltar"]')
        self.pg.wait_for_selector("#whatsapp")
        self.assertEqual(self.pg.evaluate("history.state"), None)

    # ---- Sobre
    def test_sobre(self):
        self.abrir()
        self.pg.click('[data-a="sobre"]')
        self.pg.wait_for_selector(".sobre-topo")
        self.assertEqual(self.texto(".sb-nome"), "CorrerIA Code")
        apps = self.pg.locator(".sb-app b").all_inner_texts()
        self.assertEqual([a.split("\n")[0].replace("Este app · v" + S.VERSAO, "").strip() for a in apps],
                         ["CronologIA", "ResolvIA", "GerencIA", "InventarIA", "EconomIA", "MemorIA", "CorrerIA"])
        self.assertEqual(self.texto(".sb-app.aqui .sb-aqui"), "Este app · v" + S.VERSAO)
        self.assertEqual(self.pg.get_attribute(".sb-app.aqui", "href"), "https://github.com/diegozapella63/CorrerIA-ha")
        self.assertEqual(self.pg.get_attribute(".sb-github", "target"), "_blank")
        self.pg.go_back()
        self.pg.wait_for_selector("#whatsapp")

    def test_ultimas_mensagens(self):
        self.abrir()
        self.assertEqual(self.texto("#mensagens .vazio"), "Nenhuma mensagem ainda.")
        S.registrar("bloqueada", "Desconhecido", "Olá")
        S.registrar("recebida", "Ana", "Quanto gastei?")
        S.registrar("enviada", "Ana", "Você gastou *R$ 123,45*.")
        S.registrar("erro", "WhatsApp", "O token venceu.")
        self.pg.evaluate("window.CORRERIA_TESTE.carregar()")
        self.pg.wait_for_selector("#mensagens .msg")
        linhas = self.pg.evaluate("[...document.querySelectorAll('#mensagens .msg')].map(m => [m.className.replace('msg ', ''), m.querySelector('b').textContent, m.querySelector('p').textContent])")
        self.assertEqual(linhas, [["erro", "WhatsApp", "O token venceu."], ["enviada", "Ana", "Você gastou *R$ 123,45*."],
                                  ["recebida", "Ana", "Quanto gastei?"], ["bloqueada", "Desconhecido · sem cadastro", "Olá"]])
        self.pg.click('[data-a="limpar"]')
        self.aviso("Mensagens apagadas")
        self.assertEqual(self.texto("#mensagens .vazio"), "Nenhuma mensagem ainda.")

    def test_tudo_pronto(self):
        self.publicar_app()
        S.salvar_config({"numero_id": MetaFalsa.NUMERO_ID, "token": TOKEN, "segredo": "segredo-do-app-123", "endereco": "casa-exemplo.duckdns.org:8443"})
        S.salvar_pessoa("person.ana", ANA)
        S.ESTADO["verificado_em"] = S.agora_iso()
        with mock.patch.object(S, "certificado", return_value=("/ssl/fullchain.pem", "/ssl/privkey.pem")):
            self.abrir()
            self.assertEqual(self.texto(".sync"), "Respondendo pelo WhatsApp")
            self.assertIn("Certificado fullchain.pem · porta 8443", self.texto("#webhook"))
            self.assertRegex(self.texto("#webhook"), r"A Meta confirmou o endereço hoje às \d\d:\d\d\.")

    def test_tema_claro_e_escuro(self):
        self.abrir("light")
        self.assertEqual(self.pg.evaluate("document.documentElement.dataset.theme"), "light")
        fundo_claro = self.pg.evaluate("getComputedStyle(document.body).backgroundColor")
        self.pg.emulate_media(color_scheme="dark")
        self.pg.wait_for_function("document.documentElement.dataset.theme === 'dark'")
        self.assertNotEqual(self.pg.evaluate("getComputedStyle(document.body).backgroundColor"), fundo_claro, "troca na hora")

    def test_sobre_no_fim(self):
        self.abrir()
        self.assertEqual(self.pg.evaluate("[...document.querySelectorAll('#app > section')].pop().innerText.trim().replace(/\\s+/g, ' ')"),
                         "Sobre CorrerIA Code, os apps e o GitHub.")


if __name__ == "__main__":
    unittest.main()
