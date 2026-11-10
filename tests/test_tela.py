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
RESPOSTA = ".ch-msg.ia .ch-bolha:not(.ch-pensando)"  # a resposta (o "pensando" também é uma bolha da IA)


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
        for arq in (S.CONFIG_ARQ, S.CONVERSAS_ARQ, S.MCP_ARQ, S.USO.arquivo):
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
        self.pg.wait_for_selector("#ch-txt")  # abre na conversa
        self.addCleanup(lambda: self.assertEqual(self.erros, [], "nenhum erro na página"))

    def opcoes(self, aba=None):
        """O Mais (os três pontos no alto da conversa) e, nele, Configurações; aba: apps, whatsapp, mcp, dados ou aparencia."""
        self.pg.click('.cab-bts [data-a="mais"]')
        self.pg.click('.mais-menu [data-a="opcoes"]')
        self.pg.wait_for_selector(".abas")
        if aba:
            self.pg.click(f'.abas [data-v="{aba}"]')
            self.pg.wait_for_selector(f'.abas [data-v="{aba}"].on')

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
        self.assertEqual(self.texto(".cab h1"), "Conversa")
        self.assertEqual(self.texto(".ch-vazio p"), "Nenhum app ligado. Em cada app, ligue Mais › Configurações › Integrações › CorrerIA.")
        self.pg.click('.ch-vazio [data-a="opcoes"]')
        self.pg.wait_for_selector(".abas")
        self.assertEqual(self.texto(".cab-tela h1"), "Configurações")
        self.assertEqual(self.pg.locator(".abas button").all_inner_texts(), ["Apps", "WhatsApp", "MCP", "Dados", "Aparência"])
        self.assertEqual(self.texto(".abas .on"), "Apps", "começa em Apps")
        self.pg.click('.abas [data-v="whatsapp"]')
        self.assertEqual(self.texto(".sync"), "Falta terminar a configuração do WhatsApp")
        self.assertEqual(self.texto("#whatsapp .status"), "Falta configurar: o ID do número, o token e a chave secreta.")
        self.assertTrue(self.pg.is_disabled('[data-a="conferir"]'), "sem configurar, nada a conferir")
        self.assertEqual(self.pg.locator('[data-a="ligado"]').count(), 0)
        self.assertFalse(self.pg.evaluate("document.documentElement.scrollWidth > innerWidth"), "nada sai da tela no celular")

    def test_salvar_confere_com_a_meta_e_o_token_nao_volta(self):
        self.abrir()
        self.opcoes("whatsapp")
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
        self.opcoes("whatsapp")
        self.assertEqual(self.texto("#whatsapp .status"), "Configurado. Toque em Conferir para testar com a Meta.")
        self.pg.click('[data-a="conferir"]')
        self.aviso("O token do WhatsApp venceu ou está errado. Gere um token que não vence (Usuário do sistema) e cole de novo.")

    def test_pausar(self):
        S.salvar_config({"numero_id": MetaFalsa.NUMERO_ID, "token": TOKEN, "segredo": "segredo-do-app-123"})
        self.abrir()
        self.opcoes("whatsapp")
        self.pg.click('[data-a="ligado"]')
        self.aviso("Respostas pausadas")
        self.assertFalse(S.ler_config()["ligado"])
        self.assertIn("Pausado", self.texto("#whatsapp .linha-sw"))
        self.pg.click('[data-a="ligado"]')
        self.aviso("Respondendo")
        self.assertTrue(S.ler_config()["ligado"])

    def test_webhook_endereco_e_copiar(self):
        self.abrir()
        self.opcoes("whatsapp")
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
        self.opcoes("whatsapp")
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
            self.opcoes("apps")
            self.assertEqual(self.texto("#apps .status"), "Áudio: O Home Assistant não tem fala para texto (Configurações › Assistentes de voz).")
            self.assertTrue(self.pg.evaluate("document.querySelector('#apps .status').classList.contains('manual')"))

    def test_sem_app_explica(self):
        self.abrir()
        self.assertEqual(self.pg.locator(".ch-sug").count(), 0, "sem app, sem sugestões")
        self.opcoes("apps")
        self.assertIn("Nenhum app ligado. Em cada app, ligue Mais › Configurações › Integrações › CorrerIA.", self.texto("#apps"))

    def test_apps_que_respondem(self):
        self.publicar_app()
        self.abrir()
        self.opcoes("apps")
        self.assertEqual(self.texto("#apps .app-l b"), "GerencIA")
        self.assertEqual(self.texto("#apps h2"), "Apps")
        self.assertEqual(self.texto("#apps .app-l .le"), "Responde; também lê fotos e PDF.")
        self.assertEqual(self.texto("#apps .status"), "Áudio: ouve pela fala para texto Fala simulada (teste).")

    def test_apps_com_ferramentas(self):
        app = AppFalso("CronologIA")
        self.addCleanup(app.fechar)
        app.publicar(S.SHARE_DIR, "cronologia")
        self.abrir("light")
        self.opcoes("apps")
        self.assertEqual(self.texto("#apps .app-l .le"), "Lê e muda.")
        self.assertEqual(self.pg.locator("#apps .status").all_inner_texts()[0], "IA simulada (fora do Home Assistant).")
        app.chave = "outra"
        S.APPS._ferr.clear()
        self.pg.reload()
        self.pg.wait_for_selector("#ch-txt")
        self.opcoes()
        self.assertEqual(self.texto(".abas .on"), "Apps", "a aba fica guardada")
        self.assertEqual(self.texto("#apps .app-l .le"), "O CronologIA recusou a chave. Confira se a opção do CorrerIA está ligada nele.")

    # ---- o conector MCP (qualquer IA: na tela, sem nome de marca)
    def pedido(self):
        cli = S.AUT.registrar({"client_name": "Claude", "redirect_uris": ["https://claude.ai/api/mcp/auth_callback"], "token_endpoint_auth_method": "none"})
        v = secrets.token_urlsafe(48)
        d = base64.urlsafe_b64encode(hashlib.sha256(v.encode()).digest()).rstrip(b"=").decode()
        p = S.AUT.pedir({"response_type": ["code"], "client_id": [cli["client_id"]], "code_challenge": [d], "code_challenge_method": ["S256"]}, "https://x")
        return cli, v, p

    def test_claude_e_gemini(self):
        self.abrir()
        self.opcoes("mcp")
        self.assertEqual(self.texto("#mcp h2"), "Conector MCP")
        self.assertNotRegex(self.texto("#mcp"), "Claude|Gemini|ChatGPT", "termos genéricos, sem marcas")
        self.assertIn("Desligado.", self.texto("#mcp"))
        self.assertEqual(self.pg.locator("#f-mcp").count(), 0)
        self.pg.click('[data-a="mcp"]')
        self.aviso("Conector ligado")
        self.assertTrue(S.ler_config()["mcp"])
        self.assertEqual(self.texto("#mcp .status"), "Escreva o endereço público na aba WhatsApp.")
        self.pg.click('.abas [data-v="whatsapp"]')
        self.pg.fill("#f-endereco", "casa-exemplo.duckdns.org:8443")
        self.pg.press("#f-endereco", "Tab")
        self.aviso("Endereço salvo")
        self.pg.click('.abas [data-v="mcp"]')
        self.assertEqual(self.pg.input_value("#f-mcp"), "https://casa-exemplo.duckdns.org:8443/mcp")
        self.assertEqual(self.texto("#mcp .passos"), "Na IA, adicione um conector personalizado com este endereço.\nAprove aqui o pedido com o código que aparece lá.")
        self.assertNotRegex(self.texto("#mcp"), "Claude|Gemini|ChatGPT")
        cli, v, p = self.pedido()
        self.pg.wait_for_selector(".pedido", timeout=8000)  # aparece sozinho (a tela confere a cada 4 segundos)
        self.assertEqual(self.pg.locator(".aviso-topo").count(), 0, "na aba MCP, o pedido já está à vista")
        self.assertEqual(self.texto(".pedido .pedido-t"), f"Claude quer se conectar\nCódigo {p['codigo']} · claude.ai")
        larg = self.pg.evaluate("[...document.querySelectorAll('.pedido .btns .btn')].map(b => Math.round(b.getBoundingClientRect().width))")
        self.assertEqual(len(set(larg)), 1, "Recusar e Aprovar do mesmo tamanho")
        self.pg.click('[data-a="mcp-aprovar"]')
        self.aviso("Aprovado: volte para a IA")
        self.assertEqual(S.AUT.situacao(p["id"])["estado"], "aprovado")
        self.assertEqual(self.pg.locator(".pedido").count(), 0)
        code = urllib.parse.parse_qs(urllib.parse.urlparse(S.AUT.situacao(p["id"])["ir"]).query)["code"][0]
        S.AUT.trocar({"grant_type": "authorization_code", "code": code, "client_id": cli["client_id"], "code_verifier": v})
        self.pg.reload()
        self.pg.wait_for_selector("#ch-txt")
        self.opcoes()
        self.pg.wait_for_selector(".conexao")
        self.assertRegex(self.texto(".conexao-t"), r"^Claude\nVocê · usou hoje às \d\d:\d\d$")
        self.assertEqual(self.pg.locator("#mcp .passos").count(), 0, "conectado, sem o passo a passo")
        self.assertFalse(self.pg.evaluate("document.documentElement.scrollWidth > innerWidth"))
        self.pg.click('[data-a="mcp-desconectar"]')
        self.aviso("Desconectado")
        self.assertEqual(S.AUT.conexoes(), [])

    def test_recusar_pelo_aviso_no_alto_da_conversa(self):
        S.salvar_config({"mcp": True})
        _, _, p = self.pedido()
        self.abrir("light")
        self.assertEqual(self.texto(".aviso-topo"), "Claude quer se conectar", "na conversa, onde o app abre")
        self.pg.click(".aviso-topo")
        self.pg.wait_for_selector(".pedido")
        self.assertEqual(self.texto(".abas .on"), "MCP")
        self.pg.click('[data-a="mcp-recusar"]')
        self.aviso("Recusado")
        self.assertEqual(S.AUT.situacao(p["id"])["estado"], "recusado")
        self.pg.go_back()
        self.pg.wait_for_selector("#ch-txt")
        self.assertEqual(self.pg.locator(".aviso-topo").count(), 0)

    # ---- Conversar com a IA
    def abrir_conversa(self):
        self.publicar_app()
        self.abrir()

    def test_ola_no_alto(self):
        self.publicar_app()
        self.abrir()
        self.pg.wait_for_selector(".ch-sug .chip")
        self.assertEqual(self.texto(".cab .eyebrow"), "CorrerIA", "sem o login, só o nome do app (sem \"Olá, Você\")")
        self.pg = self.nav.new_page(viewport={"width": 390, "height": 844}, extra_http_headers={"X-Remote-User-Id": "u-ana", "X-Remote-User-Display-Name": "Ana Exemplo"})
        self.addCleanup(self.pg.close)
        self.pg.on("pageerror", lambda e: self.erros.append(str(e)))
        self.pg.goto(self.url)
        self.pg.wait_for_function("() => /Olá/.test(document.querySelector('.cab .eyebrow').textContent)")
        self.assertEqual(self.pg.text_content(".cab .eyebrow"), "CorrerIA · Olá, Ana", "como nos outros apps: o primeiro nome da pessoa")
        self.pg.screenshot(path=os.path.join(os.environ.get("CORRERIA_PRINTS", "/tmp"), "correria-ola.png"))

    def test_conversar_com_a_ia(self):
        self.abrir_conversa()
        self.assertEqual(self.texto(".cab h1"), "Conversa")
        self.pg.wait_for_selector(".ch-sug .chip")  # as sugestões aparecem quando a conversa guardada chega
        self.assertEqual(self.pg.locator(".ch-sug .chip").all_inner_texts(), ["Quanto gastei este mês?", "O que vence esta semana?"])
        self.assertEqual(self.pg.get_attribute("#ch-pri", "aria-label"), "Falar", "vazio: o botão é o microfone")
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

    def test_falar(self):
        """O microfone da conversa (um microfone de mentira do Chromium): com a caixa vazia, o botão redondo é o Falar;
        ouvindo, fica vermelho com o Pronto e o Cancelar no lugar da câmera; o Pronto manda o que foi entendido."""
        nav = self.pw.chromium.launch(args=["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"])
        self.addCleanup(nav.close)
        self.publicar_app()
        for tema, w in (("dark", 390), ("light", 320)):
            self.pg = nav.new_page(viewport={"width": w, "height": 760}, color_scheme=tema)
            self.addCleanup(self.pg.close)
            self.pg.on("pageerror", lambda e: self.erros.append(str(e)))
            self.pg.set_default_timeout(8000)
            self.pg.goto(self.url)
            self.pg.wait_for_selector('.ch-sug .chip')
            self.assertEqual(self.pg.get_attribute("#ch-pri", "data-a"), "ch-falar", f"{tema}: a caixa vazia mostra o microfone")
            # escrever troca o microfone pelo Enviar; apagar volta
            self.pg.fill("#ch-txt", "oi")
            self.assertEqual(self.pg.get_attribute("#ch-pri", "data-a"), "ch-enviar")
            self.pg.fill("#ch-txt", "")
            self.assertEqual(self.pg.get_attribute("#ch-pri", "data-a"), "ch-falar")
            # ouvindo: o Pronto, o Cancelar e a caixa parada
            self.pg.click("#ch-pri")
            self.pg.wait_for_selector("#ch-pri.gravando:not([disabled])")
            self.assertEqual(self.pg.get_attribute("#ch-pri", "aria-label"), "Pronto: enviar o que falei")
            self.assertEqual(self.pg.get_attribute("#ch-txt", "placeholder"), "Ouvindo…")
            self.assertTrue(self.pg.is_disabled("#ch-txt"))
            self.assertEqual(self.pg.locator('[data-a="ch-camera"]').count(), 0, "o Cancelar fica no lugar da câmera")
            larg = self.pg.evaluate("[...document.querySelectorAll('.ch-barra .ch-bt')].map(b => Math.round(b.getBoundingClientRect().width))")
            self.assertEqual(larg, [46, 46], f"{tema}: Cancelar e Pronto do mesmo tamanho")
            self.assertFalse(self.pg.evaluate("document.documentElement.scrollWidth > innerWidth"), f"{tema}: nada passa da largura")
            self.pg.screenshot(path=os.path.join(S.DATA_DIR, f"falar-{tema}-{w}.png"))
            # Cancelar: nada é mandado
            self.pg.click('[data-a="ch-falar-x"]')
            self.pg.wait_for_selector('#ch-pri[data-a="ch-falar"]')
            self.assertEqual(self.app.pedidos, [])
            self.assertFalse(self.pg.is_disabled("#ch-txt"))
        # Pronto: o áudio vira texto (a fala simulada) e vai como a pergunta
        self.pg.click("#ch-pri")
        self.pg.wait_for_selector("#ch-pri.gravando:not([disabled])")
        self.pg.wait_for_timeout(900)
        self.pg.click("#ch-pri")
        self.pg.wait_for_selector(RESPOSTA)
        self.assertEqual(self.texto(".ch-msg.eu .ch-bolha"), "O que tem na agenda amanhã?")
        self.assertEqual(self.app.pedidos[-1][3]["texto"], "O que tem na agenda amanhã?")
        self.assertEqual(self.pg.get_attribute("#ch-pri", "data-a"), "ch-falar", "depois, o microfone de novo")
        self.assertEqual(self.erros, [])

    def test_falar_sem_microfone_ou_sem_fala_para_texto(self):
        self.publicar_app()
        self.abrir()
        self.pg.wait_for_selector('.ch-sug .chip')
        self.pg.click("#ch-pri")  # o Chromium de teste não tem microfone (ou não deixa): explica e volta ao microfone
        self.pg.wait_for_function("() => document.querySelector('#toast').classList.contains('on')")
        self.assertRegex(self.texto("#toast"), r"^(O microfone|Não achei um microfone|Este navegador)")
        self.pg.wait_for_selector('#ch-pri[data-a="ch-falar"]:not(.gravando)')
        self.assertFalse(self.pg.is_disabled("#ch-txt"))
        # sem fala para texto no Home Assistant: o botão é só o Enviar, e as Opções dizem por quê
        motivo = {"pronta": False, "motivo": "O Home Assistant não tem fala para texto (Configurações › Assistentes de voz)."}
        with mock.patch.object(S.FALA, "status", side_effect=lambda formato="ogg": motivo):
            self.pg.reload()
            self.pg.wait_for_selector('.ch-sug .chip')
            self.assertEqual(self.pg.get_attribute("#ch-pri", "data-a"), "ch-enviar")
            self.opcoes("apps")
            self.assertIn("Falar na conversa: O Home Assistant não tem fala para texto (Configurações › Assistentes de voz).", self.texto("#apps"))

    def test_sugestao_e_conversa_guardada(self):
        self.abrir_conversa()
        self.pg.click('[data-a="ch-sug"] >> nth=1')
        self.pg.wait_for_selector(RESPOSTA)
        self.assertEqual(self.app.pedidos[0][3]["texto"], "O que vence esta semana?")
        self.pg.reload()
        self.pg.wait_for_selector(RESPOSTA)
        self.assertEqual(self.pg.locator(".ch-msg").count(), 2, "fechou, abre de onde parou")
        self.pg.click('.cab-bts [data-a="ch-nova"]')  # nova conversa, no alto
        self.pg.wait_for_selector(".ch-vazio")
        self.assertEqual(self.pg.locator('.cab-bts [data-a="ch-nova"]').count(), 0, "vazia: sem o Nova conversa")
        self.pg.wait_for_function("() => document.activeElement && document.activeElement.id === 'ch-txt'")  # pronto para escrever

    def test_lista_de_conversas(self):
        self.abrir_conversa()
        self.pg.click('.cab-bts [data-a="conversas"]')
        self.pg.wait_for_function("() => (document.querySelector('.vazio') || {}).textContent === 'Nenhuma conversa ainda.'")  # depois do Carregando…
        self.assertEqual(self.texto(".cab-tela h1"), "Conversas")
        self.pg.go_back()
        self.pg.wait_for_selector("#ch-txt")
        for pergunta in ("Quanto gastei no mercado?", "O que vence esta semana?"):
            self.pg.fill("#ch-txt", pergunta)
            self.pg.click('[data-a="ch-enviar"]')
            self.pg.wait_for_function("n => document.querySelectorAll('.ch-msg.ia .ch-bolha:not(.ch-pensando)').length === n", arg=1)
            self.pg.click('.cab-bts [data-a="ch-nova"]')
            self.pg.wait_for_selector(".ch-vazio")
        self.pg.click('.cab-bts [data-a="conversas"]')
        self.pg.wait_for_selector(".conv")
        self.assertEqual(self.pg.locator(".conv-abrir b").all_inner_texts(), ["O que vence esta semana?", "Quanto gastei no mercado?"], "a mais recente primeiro")
        self.assertIn("hoje às", self.texto(".conv-abrir span"))
        self.assertIn("2 mensagens", self.texto(".conv-abrir span"))
        self.pg.click('.conv-abrir >> nth=1')  # abre a primeira conversa e volta para ela
        self.pg.wait_for_selector(RESPOSTA)
        self.assertEqual(self.texto(".ch-msg.eu .ch-bolha"), "Quanto gastei no mercado?")
        self.assertEqual(self.pg.evaluate("history.state"), None, "abrir volta um passo (o Voltar do celular não cai na lista)")
        self.pg.click('.cab-bts [data-a="conversas"]')
        self.pg.wait_for_selector(".conv.aberta")
        self.assertEqual(self.texto(".conv.aberta .conv-abrir b"), "Quanto gastei no mercado?")
        self.pg.click('.conv.aberta [data-a="conv-apagar"]')
        self.aviso("Conversa apagada")
        self.assertEqual(self.pg.locator(".conv-abrir b").all_inner_texts(), ["O que vence esta semana?"])
        self.pg.click('.conv-pag [data-a="ch-nova"]')
        self.pg.wait_for_selector(".ch-vazio")
        self.assertEqual(self.pg.evaluate("history.state"), None)

    def arrastar(self, dx, x=None, alvo="#ch-lista"):
        """Um dedo arrastado dx pixels para o lado (negativo: para a esquerda), como no celular."""
        x = (300 if dx < 0 else 90) if x is None else x
        self.pg.evaluate("""([alvo, x, dx]) => {
          const el = document.querySelector(alvo), y = 420, toque = cx => new Touch({identifier: 1, target: el, clientX: cx, clientY: y});
          el.dispatchEvent(new TouchEvent('touchstart', {touches: [toque(x)], changedTouches: [toque(x)], bubbles: true}));
          el.dispatchEvent(new TouchEvent('touchend', {touches: [], changedTouches: [toque(x + dx)], bubbles: true}));
        }""", [alvo, x, dx])
        self.pg.wait_for_timeout(500)

    def pergunta(self):
        return self.texto(".ch-msg.eu .ch-bolha") if self.pg.locator(".ch-msg.eu").count() else ""

    def test_arrastar_troca_de_conversa(self):
        self.abrir_conversa()
        self.pg.wait_for_selector(".ch-vazio")
        self.arrastar(-150)
        self.assertEqual(self.pergunta(), "", "sem conversas guardadas, nada muda")
        perguntas = ("Quanto gastei no mercado?", "O que vence esta semana?", "Quanto gastei na farmácia?")
        for n, pergunta in enumerate(perguntas):
            if n:
                self.pg.click('.cab-bts [data-a="ch-nova"]')
                self.pg.wait_for_selector(".ch-vazio")
            self.pg.fill("#ch-txt", pergunta)
            self.pg.click('[data-a="ch-enviar"]')
            self.pg.wait_for_selector(RESPOSTA)
        # na mais recente: dedo para a esquerda, as mais antigas, uma a uma; no fim da lista, fica
        for esperado in ("O que vence esta semana?", "Quanto gastei no mercado?", "Quanto gastei no mercado?"):
            self.arrastar(-150)
            self.assertEqual(self.pergunta(), esperado)
        self.arrastar(160)
        self.assertEqual(self.pergunta(), "O que vence esta semana?", "dedo para a direita: a mais nova")
        self.assertEqual(S.conversas_tela("_")[1]["aberta"], True, "fica aberta, como pela lista")
        self.assertEqual(self.pg.evaluate("history.state"), None, "o Voltar do celular não passa pelas conversas")
        # o que não troca: começar na borda (o Voltar do celular), no campo, um arraste mais para baixo que para o lado, pouco
        self.arrastar(-150, x=380)
        self.arrastar(-150, alvo="#ch-txt")
        self.arrastar(-50)
        self.pg.evaluate("""() => { const el = document.querySelector('#ch-lista'), t = (x, y) => new Touch({identifier: 1, target: el, clientX: x, clientY: y});
          el.dispatchEvent(new TouchEvent('touchstart', {touches: [t(300, 200)], changedTouches: [t(300, 200)], bubbles: true}));
          el.dispatchEvent(new TouchEvent('touchend', {touches: [], changedTouches: [t(200, 500)], bubbles: true})); }""")
        self.pg.wait_for_timeout(400)
        self.assertEqual(self.pergunta(), "O que vence esta semana?")
        # da conversa nova (vazia), dedo para a esquerda: a mais recente; para a direita, nada
        self.pg.click('.cab-bts [data-a="ch-nova"]')
        self.pg.wait_for_selector(".ch-vazio")
        self.arrastar(160)
        self.assertEqual(self.pergunta(), "")
        self.arrastar(-150)
        self.assertEqual(self.pergunta(), "Quanto gastei na farmácia?")
        # fora da conversa (na lista), arrastar não troca nada
        self.pg.click('.cab-bts [data-a="conversas"]')
        self.pg.wait_for_selector(".conv.aberta")
        self.arrastar(-150, alvo=".conv-pag")
        self.assertEqual(self.texto(".conv.aberta .conv-abrir b"), "Quanto gastei na farmácia?")
        self.assertFalse(self.pg.evaluate("document.documentElement.scrollWidth > innerWidth"))

    def test_tirar_foto(self):
        nav = self.pw.chromium.launch(args=["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"])
        self.addCleanup(nav.close)
        self.publicar_app()
        self.pg = nav.new_page(viewport={"width": 390, "height": 844})
        self.pg.on("pageerror", lambda e: self.erros.append(str(e)))
        self.pg.set_default_timeout(8000)
        self.pg.goto(self.url)
        self.pg.wait_for_selector('[data-a="ch-camera"]')
        self.pg.click('[data-a="ch-camera"]')
        self.pg.wait_for_selector("#camera .cam-disparo:not([disabled])")
        self.assertEqual(self.texto("#camera .cam-titulo"), "Tirar foto")
        self.pg.wait_for_function("() => document.querySelector('#camera video').videoWidth > 0")
        self.pg.click("#camera .cam-disparo")
        self.pg.wait_for_selector(".ch-prev img")
        self.assertEqual(self.pg.locator("#camera").count(), 0, "a foto fecha a câmera")
        self.assertTrue(self.texto(".ch-prev span").startswith("Foto "))
        self.assertEqual(self.pg.evaluate("history.state"), None, "a câmera não deixa entrada no histórico")
        self.pg.fill("#ch-txt", "Quanto deu?")
        self.pg.click('[data-a="ch-enviar"]')
        self.pg.wait_for_selector(RESPOSTA)
        self.assertEqual(self.app.pedidos[0][3]["anexo"]["tipo"], "image/jpeg")
        # o Voltar do celular fecha a câmera
        self.pg.click('[data-a="ch-camera"]')
        self.pg.wait_for_selector("#camera")
        self.pg.go_back()
        self.pg.wait_for_function("() => !document.querySelector('#camera')")
        self.assertEqual(self.pg.locator("#ch-txt").count(), 1)
        self.assertEqual(self.erros, [])

    def test_sem_camera_escolhe_a_foto(self):
        self.publicar_app()
        self.pg = self.nav.new_page(viewport={"width": 390, "height": 844})
        self.addCleanup(self.pg.close)
        self.pg.add_init_script("Object.defineProperty(navigator, 'mediaDevices', { value: undefined })")
        self.pg.goto(self.url)
        self.pg.wait_for_selector('[data-a="ch-camera"]')
        self.pg.click('[data-a="ch-camera"]')
        self.pg.wait_for_selector("#camera .cam-msg")
        self.assertIn("Dá para tirar a foto pelo celular e escolher.", self.texto("#camera .cam-msg p"))
        with self.pg.expect_file_chooser() as fc:
            self.pg.click('#camera [data-a="cam-galeria"]')
        self.assertEqual(self.pg.locator("#camera").count(), 0)
        fc.value.set_files(files=[{"name": "nota.jpg", "mimeType": "image/jpeg", "buffer": b"\xff\xd8\xff\xe0foto"}])
        self.pg.wait_for_selector(".ch-prev")
        self.assertEqual(self.texto(".ch-prev span"), "nota.jpg")

    def test_mandar_uma_foto(self):
        self.abrir_conversa()
        with self.pg.expect_file_chooser() as fc:
            self.pg.click('[data-a="ch-anexar"]')
        fc.value.set_files(files=[{"name": "nota.jpg", "mimeType": "image/jpeg", "buffer": b"\xff\xd8\xff\xe0foto"}])
        self.pg.wait_for_selector(".ch-prev")
        self.assertEqual(self.texto(".ch-prev span"), "nota.jpg")
        self.pg.fill("#ch-txt", "Quanto deu?")
        self.pg.click('[data-a="ch-enviar"]')
        self.pg.wait_for_selector(RESPOSTA)
        c = self.app.pedidos[0][3]
        self.assertEqual((c["texto"], c["anexo"]["tipo"], c["anexo"]["nome"]), ("Quanto deu?", "image/jpeg", "nota.jpg"))
        self.assertEqual(self.texto(".ch-msg.eu .ch-anexo"), "nota.jpg")
        self.assertEqual(self.pg.locator(".ch-prev").count(), 0)

    def test_voltar_do_celular_volta_um_passo(self):
        self.abrir_conversa()
        self.opcoes()
        self.assertEqual(self.texto(".voltar"), "Mais")
        self.pg.go_back()
        self.pg.wait_for_selector(".mais-menu")
        self.pg.click('.mais-menu [data-a="sobre"]')
        self.pg.wait_for_selector(".sobre-topo")
        self.assertEqual(self.texto(".voltar"), "Mais")
        self.pg.go_back()
        self.pg.wait_for_selector(".mais-menu")
        self.assertEqual(self.texto(".voltar"), "Conversa")
        self.pg.go_back()
        self.pg.wait_for_selector("#ch-txt")
        self.opcoes()
        self.pg.click('[data-a="voltar"]')
        self.pg.wait_for_selector(".mais-menu")
        self.pg.click('[data-a="voltar"]')
        self.pg.wait_for_selector("#ch-txt")
        self.assertEqual(self.pg.evaluate("history.state"), None)

    # ---- Sobre
    def test_sobre(self):
        self.abrir()
        self.pg.click('.cab-bts [data-a="mais"]')
        self.pg.click('.mais-menu [data-a="sobre"]')
        self.pg.wait_for_selector(".sobre-topo")
        self.assertEqual(self.texto(".sb-nome"), "CorrerIA Code")
        apps = self.pg.locator(".sb-app b").all_inner_texts()
        self.assertEqual([a.split("\n")[0].replace("Este app · v" + S.VERSAO, "").strip() for a in apps],
                         ["CronologIA", "ResolvIA", "GerencIA", "InventarIA", "EconomIA", "MemorIA", "CorrerIA"])
        self.assertEqual(self.texto(".sb-app.aqui .sb-aqui"), "Este app · v" + S.VERSAO)
        self.assertEqual(self.pg.locator(".sb-app.aqui .mb > span").inner_text().strip(), "Pergunte e peça a qualquer app, no chat ou no WhatsApp.",
                         "0.7.2: o chat com qualquer app, não só o WhatsApp")
        self.assertEqual(self.pg.get_attribute(".sb-app.aqui", "href"), "https://github.com/diegozapella63/CorrerIA-ha")
        self.assertEqual(self.pg.get_attribute(".sb-github", "target"), "_blank")
        self.pg.go_back()
        self.pg.wait_for_selector(".mais-menu")

    def test_ultimas_mensagens(self):
        self.abrir()
        self.opcoes("apps")
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
            self.opcoes("whatsapp")
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

    def test_mais_menu_configuracoes_e_sobre_no_fim(self):
        """1.0.0: como nos outros apps, o Mais (três pontos) é um menu: Configurações e, por último, o Sobre, à parte."""
        self.abrir()
        self.assertEqual(self.pg.locator('.cab-bts [data-a="mais"] circle').count(), 3, "os três pontos")
        self.pg.click('.cab-bts [data-a="mais"]')
        self.pg.wait_for_selector(".mais-menu")
        self.assertEqual(self.texto(".cab-tela h1"), "Mais")
        self.assertEqual([t.strip() for t in self.pg.locator(".mais-menu .linha-t b").all_inner_texts()], ["Configurações", "Sobre"])
        self.pg.click('.mais-menu [data-a="opcoes"]')
        self.pg.wait_for_selector(".abas")
        self.assertEqual(self.pg.locator('#app [data-a="sobre"]').count(), 0, "o Sobre não fica dentro de Configurações")

    def test_dados_onde_ficam(self):
        S.salvar_config({"numero_id": MetaFalsa.NUMERO_ID, "token": TOKEN, "segredo": "segredo-do-app-123"})
        self.abrir()
        self.opcoes("dados")
        t = self.texto("#onde")
        self.assertTrue(t.startswith("Onde ficam os dados") and "config.json" in t and "conversas.json" in t and "uso_ia.json" in t, t)
        self.assertNotIn(TOKEN, self.pg.content(), "o token nunca vai para a tela")

    def test_aparencia_tema_no_aparelho_e_cor_da_casa(self):
        self.abrir("light")
        self.opcoes("aparencia")
        self.assertEqual(self.pg.locator(".temas button").all_inner_texts(), ["Sistema", "Claro", "Escuro"])
        self.assertEqual(self.texto(".temas .on"), "Sistema", "começa em Sistema")
        self.assertEqual(self.pg.evaluate("document.documentElement.dataset.theme"), "light")
        self.pg.click('.temas [data-v="escuro"]')
        self.assertEqual(self.pg.evaluate("document.documentElement.dataset.theme"), "dark")
        nomes = [t.strip() for t in self.pg.locator(".cores .tsw span").all_inner_texts()]
        self.assertEqual(nomes, ["Vermelho", "Coral", "Laranja", "Ouro", "Verde", "Menta", "Turquesa", "Azul", "Índigo", "Lilás", "Rosa", "Grafite"])
        dia = self.pg.evaluate("""() => { const L = ['vermelho','coral','laranja','ouro','verde','menta','turquesa','azul','indigo','lilas','rosa'], d = new Date();
            return L[Math.floor(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()) / 864e5) % 11]; }""")
        self.assertEqual(self.pg.get_attribute('.sw[data-a="cor-dia"]', "aria-checked"), "true", "Cor do dia ligada de início")
        self.assertEqual(self.pg.get_attribute(".cores .tsw.on", "data-v"), dia, "a cor do dia, a mesma de todos os apps")
        outra = "azul" if dia != "azul" else "verde"
        self.pg.click(f'.cores [data-v="{outra}"]')
        self.aviso("Cor do app: " + ("Azul" if outra == "azul" else "Verde"))
        self.assertEqual(self.pg.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--accent').trim()"), "#62B5FF" if outra == "azul" else "#8BD45F")
        c = S.ler_config()
        self.assertEqual((c["cor"], c["cor_dia"]), (outra, False), "a cor vale para a casa toda (no servidor)")
        self.assertEqual(self.pg.get_attribute('.sw[data-a="cor-dia"]', "aria-checked"), "false", "escolher uma cor desliga a Cor do dia")
        # outro aparelho: a cor da casa; o tema, o dele (Sistema)
        outro = self.nav.new_page(viewport={"width": 390, "height": 844}, color_scheme="light")
        self.addCleanup(outro.close)
        outro.goto(self.url)
        outro.wait_for_selector("#ch-txt")
        self.assertEqual(outro.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--accent').trim()"), "#62B5FF" if outra == "azul" else "#8BD45F")
        self.assertEqual(outro.evaluate("document.documentElement.dataset.theme"), "light")
        self.pg.click('.sw[data-a="cor-dia"]')
        self.aviso("Cor do dia ligada")
        self.assertTrue(S.ler_config()["cor_dia"])
        self.assertFalse(self.pg.evaluate("document.documentElement.scrollWidth > innerWidth"), "nada sai da tela")

    def test_uso_da_ia(self):
        self.abrir()
        self.opcoes("apps")
        self.assertEqual(self.texto("#uso .vazio"), "Nenhuma chamada ainda.")
        S.USO.registrar("whatsapp", 4000, 400, 3.2)
        S.USO.registrar("conversa", 800, 0, 1.0, "HTTP 429 Too Many Requests")
        self.pg.evaluate("window.CORRERIA_TESTE.carregar()")
        self.pg.wait_for_selector("#uso .uso-ult li")
        tiles = [" ".join(t.split()) for t in self.pg.locator("#uso .uso-t").all_inner_texts()]
        self.assertEqual(tiles[0], "HOJE 2 1 sem cota")
        self.assertEqual(self.pg.locator("#uso .uso-b").count(), 7)
        self.assertEqual(self.texto("#uso .uso-tipos"), "WhatsApp 1 · Conversa 1")
        ult = self.pg.locator("#uso .uso-ult li").all_inner_texts()
        self.assertTrue(ult[0].startswith("Conversa") and "sem cota" in ult[0] and ult[1].startswith("WhatsApp"), ult)


    def test_abas_numa_linha_e_guardadas(self):
        self.abrir()
        self.opcoes("whatsapp")
        self.assertEqual(self.pg.locator("#whatsapp").count(), 1)
        self.assertEqual(self.pg.locator("#mcp").count(), 0, "uma aba de cada vez")
        tops = self.pg.evaluate("[...document.querySelectorAll('.abas button')].map(b => Math.round(b.getBoundingClientRect().top))")
        self.assertEqual(len(set(tops)), 1, "as cinco abas numa linha")
        self.assertFalse(self.pg.evaluate("document.documentElement.scrollWidth > innerWidth"))
        self.pg.set_viewport_size({"width": 320, "height": 700})
        self.assertFalse(self.pg.evaluate("document.querySelector('.abas').scrollWidth > document.querySelector('.abas').clientWidth + 1"), "cabem em 320 px")
        self.pg.reload()
        self.pg.wait_for_selector("#ch-txt")
        self.opcoes()
        self.assertEqual(self.texto(".abas .on"), "WhatsApp", "a aba fica guardada")

    def test_uma_altura_so(self):
        """0.11.0: botões, campos e botões de escolha (as abas, o Tema) com a altura da família (50 px), a mesma dos
        outros apps, no celular e no estreito; ficam de fora os botões só com ícone e a caixa da conversa."""
        self.abrir()
        medir = """() => [...document.querySelectorAll('.btn, .inp, .abas, .temas')].filter(e => e.offsetParent && e.getBoundingClientRect().width > 4 && !e.closest('.ch-barra'))
            .map(e => [e.offsetHeight, e.className + ' ' + (e.textContent || e.placeholder || '').trim().slice(0, 24)])"""
        for largura in (390, 320):
            self.pg.set_viewport_size({"width": largura, "height": 760})
            self.pg.reload()
            self.pg.wait_for_selector("#ch-txt")
            self.opcoes()
            for aba in ("apps", "whatsapp", "mcp", "dados", "aparencia"):
                self.pg.click(f'.abas [data-v="{aba}"]')
                self.pg.wait_for_selector(f'.abas [data-v="{aba}"].on')
                hs = self.pg.evaluate(medir)
                self.assertTrue(hs, aba)
                self.assertEqual([x for x in hs if x[0] != 50], [], f"{largura} px › {aba}: tudo com 50 px")


if __name__ == "__main__":
    unittest.main()
