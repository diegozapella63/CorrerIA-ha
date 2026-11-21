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


# 1.10.0: as 6 perguntas prontas com o GerencIA ligado
G6 = ["Quanto gastei este mês?", "O que vence esta semana?", "Qual é o meu patrimônio hoje?", "Lança 45 de mercado", "Quanto sobrou este mês?", "Quanto rende a carteira por mês?"]


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
        S.FORA.update(em=None, ok=None, erro="", via="")
        S.TUNEL["em"] = None
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
        self.assertEqual(self.pg.locator(".abas button").all_inner_texts(), ["Integrações", "WhatsApp", "MCP", "Dados", "Aparência", "Opções"])
        self.assertEqual(self.texto(".abas .on"), "Integrações", "começa em Integrações (1.14.0: antes, Apps)")
        self.pg.click('.abas [data-v="whatsapp"]')
        self.assertEqual(self.pg.locator(".sync").count(), 0, "0.16.1: sem o \"Falta terminar a configuração\" no alto (o cartão já diz)")
        # 0.17.0: o WhatsApp liga e desliga como o conector MCP; desligado de início (nada configurado), só a chave
        self.assertIn("Desligado.", self.texto("#whatsapp"))
        self.assertEqual(self.pg.locator("#f-numero, #webhook, #pessoas, #mensagens").count(), 0, "desligado: sem os campos nem as outras seções")
        self.pg.click('[data-a="whatsapp"]')
        self.aviso("WhatsApp ligado")
        self.assertTrue(S.ler_config()["whatsapp"])
        self.assertEqual(self.pg.locator("#whatsapp .sub-box #f-numero").count(), 1, "ligado: os campos no quadro embaixo da chave")
        self.assertEqual(self.pg.locator('[data-a="salvar"]').count(), 0, "0.17.0: sem o botão Salvar (cada campo se salva sozinho)")
        self.assertEqual(self.texto("#whatsapp .status"), "Falta configurar: o ID do número, o token e a chave secreta.")
        self.assertTrue(self.pg.is_disabled('[data-a="conferir"]'), "sem configurar, nada a conferir")
        self.assertEqual(self.pg.locator('[data-a="ligado"]').count(), 0)
        self.assertFalse(self.pg.evaluate("document.documentElement.scrollWidth > innerWidth"), "nada sai da tela no celular")

    def test_salvar_confere_com_a_meta_e_o_token_nao_volta(self):
        S.salvar_config({"whatsapp": True})
        self.abrir()
        self.opcoes("whatsapp")
        # 0.17.0: cada campo se salva ao sair dele; com os três, confere com a Meta sozinho
        self.pg.fill("#f-numero", MetaFalsa.NUMERO_ID)
        self.pg.press("#f-numero", "Tab")
        self.aviso("Salvo")
        self.pg.fill("#f-token", TOKEN)
        self.pg.press("#f-token", "Tab")
        self.aviso("Salvo")
        self.pg.fill("#f-segredo", "segredo-do-app-123")
        self.pg.press("#f-segredo", "Tab")
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
        self.assertIn("Pausado", self.texto("#whatsapp .sub-box .linha-sw"))
        self.pg.click('[data-a="ligado"]')
        self.aviso("Respondendo")
        self.assertTrue(S.ler_config()["ligado"])

    def test_webhook_endereco_e_copiar(self):
        S.salvar_config({"whatsapp": True})
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
        S.salvar_config({"whatsapp": True})
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
        """0.15.0: o áudio do WhatsApp na aba do WhatsApp, escrito por extenso (antes: "Áudio: ouve pela fala para texto")."""
        self.publicar_app()
        S.salvar_config({"numero_id": MetaFalsa.NUMERO_ID, "token": TOKEN, "segredo": "segredo-do-app-123"})
        with mock.patch.object(S.FALA, "status", return_value={"pronta": False, "motivo": "O Home Assistant não tem fala para texto (Configurações › Assistentes de voz)."}):
            self.abrir()
            self.opcoes("apps")
            self.assertEqual(self.texto("#apps .status"), "Falar na conversa: O Home Assistant não tem fala para texto (Configurações › Assistentes de voz).")
            self.pg.click('.abas [data-v="whatsapp"]')
            st = self.pg.locator("#whatsapp .status.manual").all_inner_texts()
            self.assertIn("Áudios do WhatsApp não viram texto. O Home Assistant não tem fala para texto (Configurações › Assistentes de voz).", st)

    def test_sem_app_explica(self):
        self.abrir()
        self.assertEqual(self.pg.locator(".ch-sug").count(), 0, "sem app, sem sugestões")
        self.opcoes("apps")
        self.assertIn("Nenhum app ligado. Em cada app, ligue Mais › Configurações › Integrações › CorrerIA.", self.texto("#apps"))
        # 1.15.0: todos os apps da família aparecem, cada um dizendo que está com a integração desligada
        nomes = [t.strip() for t in self.pg.locator("#apps .app-l.off b").all_inner_texts()]
        self.assertEqual(nomes, ["CronologIA", "EconomIA", "GerencIA", "InventarIA", "MemorIA", "ResolvIA"])
        self.assertEqual(set(self.pg.locator("#apps .app-l.off .le").all_inner_texts()), {"Integração desligada."}, "o como ligar já está no aviso de cima")
        self.assertEqual(self.pg.locator("#apps .app-l.off .rot-ic svg").count(), 6, "cada um com o ícone")
        self.assertTrue(self.pg.evaluate("document.documentElement.scrollWidth <= innerWidth"))

    def test_apps_que_respondem(self):
        self.publicar_app()
        self.abrir()
        self.opcoes("apps")
        self.assertEqual(self.texto("#apps .app-l b"), "GerencIA")
        self.assertEqual(self.texto("#apps h2"), "Apps")
        self.assertEqual(self.texto("#apps .app-l .le"), "Responde; também lê fotos e PDF.")
        # 1.15.0: o ligado primeiro; os outros cinco da família depois, com a integração desligada e como ligar
        linhas = self.pg.evaluate("[...document.querySelectorAll('#apps .app-l')].map(l => [l.querySelector('b').textContent, l.classList.contains('off'), l.querySelector('.le').textContent])")
        self.assertEqual([x[:2] for x in linhas], [["GerencIA", False], ["CronologIA", True], ["EconomIA", True], ["InventarIA", True], ["MemorIA", True], ["ResolvIA", True]])
        self.assertEqual({x[2] for x in linhas[1:]}, {"Integração desligada. No app: Mais › Configurações › Integrações › CorrerIA."})
        op = self.pg.evaluate("[...document.querySelectorAll('#apps .app-l')].map(l => getComputedStyle(l.querySelector('b')).opacity)")
        self.assertEqual((op[0], set(op[1:])), ("1", {"0.55"}), "os desligados, apagados")
        self.assertEqual(self.pg.locator("#apps .status").count(), 0, "0.15.0: o áudio é do WhatsApp, fica na aba dele")
        self.assertEqual(self.pg.locator(".sync").count(), 0, "o estado do WhatsApp só na aba dele")

    def test_apps_com_ferramentas(self):
        app = AppFalso("CronologIA")
        self.addCleanup(app.fechar)
        app.publicar(S.SHARE_DIR, "cronologia")
        self.abrir("light")
        self.opcoes("apps")
        self.assertEqual(self.texto("#apps .app-l .le"), "Lê e muda.")
        self.assertEqual(self.pg.locator("#ia .status").all_inner_texts()[0], "Pronta para conversar · Usando a IA padrão do Home Assistant (simulada, fora do Home Assistant).", "0.16.0: na seção da IA")
        app.chave = "outra"
        S.APPS._ferr.clear()
        self.pg.reload()
        self.pg.wait_for_selector("#ch-txt")
        self.opcoes()
        self.assertEqual(self.texto(".abas .on"), "Integrações", "a aba fica guardada")
        self.assertEqual(self.texto("#apps .app-l .le"), "O CronologIA recusou a chave. Confira se a opção do CorrerIA está ligada nele.")

    # ---- 0.16.0: a IA para conversar, como nos outros apps (fora do Home Assistant, duas de exemplo)
    def test_ia_para_conversar(self):
        """0.16.1: no padrão dos outros apps: o estado (verde quando está tudo certo), a caixa de seleção (a janela do app,
        selectsheet.js) e o Verificar de novo."""
        app = AppFalso("CronologIA")
        self.addCleanup(app.fechar)
        app.publicar(S.SHARE_DIR, "cronologia")
        self.abrir()
        self.opcoes("apps")
        self.assertEqual(self.texto("#ia h2"), "IA", "1.6.0: só IA, como nos outros apps")
        ordem = self.pg.evaluate("[...document.querySelectorAll('#app section.card')].map(c => c.id)")
        self.assertEqual(ordem.index("ia"), ordem.index("apps") + 1, f"logo depois dos apps, como nos outros: {ordem}")
        self.assertEqual(self.pg.evaluate("[getComputedStyle(document.querySelector('#ia .status'), '::before').backgroundColor, getComputedStyle(document.documentElement).getPropertyValue('--good').trim()]")[0] != "", True)
        self.assertEqual(self.pg.get_attribute("#ia .status", "class"), "status", "verde: tudo certo")
        self.assertEqual([t.strip() for t in self.pg.locator("#ia .campo > label").all_inner_texts()], ["Para conversar", "Para pesquisar na internet"])
        self.assertEqual([t.strip() for t in self.pg.locator("#f-ia-pesquisa option").all_inner_texts()], ["Igual à de conversar", "IA de exemplo", "Outra IA"])
        self.assertEqual([t.strip() for t in self.pg.locator("#f-ia option").all_inner_texts()], ["Padrão do Home Assistant", "IA de exemplo", "Outra IA"])
        self.assertEqual(self.pg.locator("#f-ia").evaluate("s => getComputedStyle(s).pointerEvents"), "none", "a janela do celular não abre: a do app")
        self.pg.locator("#f-ia").scroll_into_view_if_needed()  # 1.15.0: com todos os apps na lista, a IA fica mais abaixo
        bx = self.pg.locator("#f-ia").bounding_box()
        self.pg.mouse.click(bx["x"] + bx["width"] / 2, bx["y"] + bx["height"] / 2)
        self.pg.wait_for_selector(".ss-wrap.in .ss-sheet")
        self.assertEqual(self.texto(".ss-head b"), "IA para conversar")
        self.pg.click(".ss-opt >> text=Outra IA")
        self.pg.wait_for_function("document.querySelector('#f-ia') && document.querySelector('#f-ia').value === 'ai_task.outra_ia'")
        self.pg.wait_for_function("!document.querySelector('.ss-wrap')")
        self.assertEqual(S.ler_config()["ia_entidade"], "ai_task.outra_ia")
        self.assertIn("Usando Outra IA", self.texto("#ia .status"))
        bx = self.pg.locator("#f-ia-pesquisa").bounding_box()  # 1.6.0: a IA para pesquisar na internet
        self.pg.mouse.click(bx["x"] + bx["width"] / 2, bx["y"] + bx["height"] / 2)
        self.pg.wait_for_selector(".ss-wrap.in .ss-sheet")
        self.assertEqual(self.texto(".ss-head b"), "IA para pesquisar na internet")
        self.pg.click(".ss-opt >> text=IA de exemplo")
        self.pg.wait_for_function("document.querySelector('#f-ia-pesquisa') && document.querySelector('#f-ia-pesquisa').value === 'ai_task.ia_de_exemplo'")
        self.pg.wait_for_function("!document.querySelector('.ss-wrap')")
        self.assertEqual([S.ler_config()["ia_entidade"], S.ler_config()["ia_pesquisa"]], ["ai_task.outra_ia", "ai_task.ia_de_exemplo"])
        S.ESTADO["ia"] = {"ok": False, "erro": "Outra IA ficou sem cota (o limite de uso acabou).", "em": None, "nome": "Outra IA"}
        self.pg.evaluate("window.CORRERIA_TESTE.carregar()")
        self.pg.wait_for_selector("#ia .status.erro")
        self.assertIn("ficou sem cota", self.texto("#ia .status"))
        self.pg.click('#ia [data-a="ia-verificar"]')
        self.pg.wait_for_selector("#ia .status:not(.erro)")
        self.assertIsNone(S.ESTADO["ia"], "Verificar de novo esquece o erro da última chamada")
        S.salvar_config({"ia_entidade": "", "ia_pesquisa": ""})

    # ---- 0.17.0 (padrão da família): toda seção contrai e expande no cabeçalho; o aparelho lembra
    def test_secoes_contraem(self):
        self.abrir()
        self.opcoes("apps")
        self.assertEqual(self.pg.get_attribute("#apps .rot", "aria-expanded"), "true")
        self.assertEqual(self.pg.locator("#apps .rot .dobra-ic svg").count(), 1, "a seta no canto")
        self.pg.click("#apps .rot h2")
        self.pg.wait_for_selector("#apps.fechada")
        self.assertEqual(self.pg.evaluate("[...document.querySelectorAll('#apps > :not(.rot)')].filter(e => e.getClientRects().length).length"), 0, "fechada: só o cabeçalho")
        self.assertEqual(self.pg.get_attribute("#apps .rot", "aria-expanded"), "false")
        self.pg.reload()
        self.pg.wait_for_selector("#ch-txt")
        self.opcoes("apps")
        self.assertEqual(self.pg.locator("#apps.fechada").count(), 1, "o aparelho lembra")
        self.pg.click("#apps .rot")
        self.pg.wait_for_selector("#apps:not(.fechada)")

    # ---- 0.16.0 (padrão da família): ícones nas seções, nas linhas, nos campos, nos botões, nas abas e nos títulos
    def test_icones_em_tudo(self):
        self.publicar_app()
        S.salvar_config({"numero_id": "109876543210", "token": TOKEN, "segredo": "segredo-de-teste-1234", "endereco": "https://casa-exemplo.duckdns.org:8443", "mcp": True})
        self.abrir()
        confere = """() => { const vis = e => e && e.getClientRects().length, ruins = [];
          for (const b of document.querySelectorAll('#app button, #app a.btn')) {
            if (!vis(b) || !b.textContent.trim() || b.querySelector('svg') || b.matches('.conv-abrir, .linha, .uso-bar, .tsw')) continue;
            ruins.push('botão sem ícone: ' + b.textContent.trim().slice(0, 30)); }
          for (const t of document.querySelectorAll('#app .linha-sw b, #app .campo > label, #app .lbl, #app section.card > .rot h2, #app h1'))
            if (vis(t) && !(t.querySelector('svg') || t.parentElement.querySelector(':scope > .rot-ic svg'))) ruins.push('título sem ícone: ' + t.textContent.trim().slice(0, 30));
          return ruins; }"""
        self.assertEqual(self.pg.evaluate(confere), [], "a conversa")
        self.opcoes()
        for aba in ("apps", "whatsapp", "mcp", "dados", "aparencia"):
            self.pg.click(f'.abas [data-v="{aba}"]')
            self.pg.wait_for_selector(f'.abas [data-v="{aba}"].on')
            self.assertEqual(self.pg.evaluate(confere), [], aba)
        self.assertEqual(self.pg.locator(".abas button svg").count(), self.pg.locator(".abas button").count(), "as abas com o ícone")
        self.assertEqual(self.pg.evaluate("getComputedStyle(document.querySelector('.abas button svg')).display"), "none", "no celular, só o nome")
        # 0.16.1: no celular, dentro do Home Assistant (com Opções), as abas não cabem; a ponta de onde há mais some aos
        # poucos, com uma seta
        self.addCleanup(mock.patch.dict(os.environ, {"CORRERIA_HOST": "a1b2c3d4-correria"}).stop)
        mock.patch.dict(os.environ, {"CORRERIA_HOST": "a1b2c3d4-correria"}).start()
        self.pg.evaluate("window.CORRERIA_TESTE.carregar()")
        self.pg.wait_for_selector('.abas [data-v="opcoes"]')
        self.pg.click('.abas [data-v="apps"]')
        self.pg.wait_for_selector('.abas [data-v="apps"].on')
        self.pg.evaluate("document.querySelector('.abas').scrollLeft = 0")
        self.pg.wait_for_timeout(150)
        pontas = "[...document.querySelector('.abas-wrap').classList].filter(c => c.startsWith('tem-')).sort()"
        self.assertEqual(self.pg.evaluate(pontas), ["tem-dir"], "no começo: há mais à direita")
        self.assertTrue(self.pg.is_visible(".abas-fim.dir svg") and not self.pg.is_visible(".abas-fim.esq"))
        # 0.16.2: a seta fica por cima das abas (antes, as abas cobriam a seta)
        self.assertTrue(self.pg.evaluate("""(() => { const f = document.querySelector('.abas-fim.dir'), r = f.getBoundingClientRect(); f.style.pointerEvents = 'auto';
          const e = document.elementFromPoint(r.right - 6, (r.top + r.bottom) / 2); f.style.pointerEvents = ''; return !!(e && e.closest('.abas-fim.dir')); })()"""), "a seta à vista, por cima das abas")
        self.pg.evaluate("(n => n.scrollLeft = n.scrollWidth)(document.querySelector('.abas'))")
        self.pg.wait_for_timeout(150)
        self.assertEqual(self.pg.evaluate(pontas), ["tem-esq"], "no fim: há mais à esquerda")
        self.pg.set_viewport_size({"width": 1100, "height": 900})
        self.pg.wait_for_timeout(200)
        self.assertEqual(self.pg.evaluate(pontas), [], "no computador, cabem todas: sem a seta")

    # ---- o conector MCP (qualquer IA: na tela, sem nome de marca)
    def pedido(self):
        cli = S.AUT.registrar({"client_name": "Claude", "redirect_uris": ["https://claude.ai/api/mcp/auth_callback"], "token_endpoint_auth_method": "none"})
        v = secrets.token_urlsafe(48)
        d = base64.urlsafe_b64encode(hashlib.sha256(v.encode()).digest()).rstrip(b"=").decode()
        p = S.AUT.pedir({"response_type": ["code"], "client_id": [cli["client_id"]], "code_challenge": [d], "code_challenge_method": ["S256"]}, "https://x")
        return cli, v, p

    def test_o_caminho_de_fora(self):
        """1.11.0: no MCP e no Webhook, de que endereço é o certificado, a porta que falta no endereço e a última conexão de
        fora, para saber se o que falta é o Duck DNS, o roteador ou o certificado."""
        from datetime import datetime, timezone
        cc = ("/ssl/fullchain.pem", "/ssl/privkey.pem")
        vence = datetime(2027, 1, 1, tzinfo=timezone.utc)
        S.salvar_config({"mcp": True, "whatsapp": True, "endereco": "https://casa-exemplo.duckdns.org", "endereco_mcp": "https://casa-exemplo.duckdns.org"})
        with mock.patch.object(S, "certificado", return_value=cc), mock.patch.object(S, "validade_certificado", return_value=(vence, "outra-casa.duckdns.org")):
            self.abrir()
            self.opcoes("mcp")
            t = self.texto("#mcp")
            self.assertIn("O certificado é de outra-casa.duckdns.org · No app Duck DNS, confira o domínio; depois reinicie o CorrerIA.", t)
            self.assertIn("Sem :8443 no fim do endereço, só chega aqui se o roteador mandar a porta 443 para a 8443.", t)
            self.assertIn("Nenhuma conexão de fora desde que o app abriu · Pelo 5G, abra o endereço do conector.", t)
            self.assertFalse(self.pg.evaluate("document.documentElement.scrollWidth > innerWidth"))
        S.salvar_config({"endereco": "https://casa-exemplo.duckdns.org:8443", "endereco_mcp": "https://casa-exemplo.duckdns.org:8443"})
        S.FORA.update(em=S.agora_iso(), ok=False, erro="o aparelho recusou o certificado")
        with mock.patch.object(S, "certificado", return_value=cc), mock.patch.object(S, "validade_certificado", return_value=(vence, "casa-exemplo.duckdns.org")):
            self.pg.reload()
            self.opcoes("mcp")
            t = self.texto("#mcp")
            self.assertIn("Certificado de casa-exemplo.duckdns.org · porta 8443", t)
            self.assertNotIn("Sem :8443", t)
            self.assertRegex(self.texto("#mcp [data-fora]"), r"^Chegou de fora hoje às \d\d:\d\d, mas não abriu · o aparelho recusou o certificado\.$")
            S.FORA.update(ok=True, erro="")
            self.pg.reload()
            self.opcoes("whatsapp")
            self.assertRegex(self.texto("#webhook [data-fora]"), r"^Chegou uma conexão de fora hoje às \d\d:\d\d\.$", "no Webhook também")
            self.assertIn("Certificado de casa-exemplo.duckdns.org · porta 8443", self.texto("#webhook"))

    def test_o_tunel_da_cloudflare(self):
        """1.13.0: no MCP, Pelo túnel da Cloudflare (para quando a operadora bloqueia a 443): ligado, o que vai no app
        Cloudflared, pronto para copiar (o endereço público e a porta do túnel), e a última conexão que chegou por ele;
        sem as linhas do certificado e da porta. Com outra porta no endereço, o aviso de que as IAs só usam a 443."""
        S.salvar_config({"mcp": True, "whatsapp": True, "endereco": "https://casa-exemplo.duckdns.org:8443", "endereco_mcp": "https://casa-exemplo.duckdns.org:8443"})
        self.addCleanup(S.ligar_tunel, False)
        self.abrir()
        self.opcoes("mcp")
        self.assertIn("As IAs só conectam na porta 443 · Tire o :8443 do endereço e, no roteador, mande a 443 para a 8443 (ou use o túnel da Cloudflare).", self.texto("#mcp"))
        self.assertEqual(self.pg.get_attribute('[data-a="tunel"]', "aria-checked"), "false")
        self.assertEqual(self.pg.locator("#f-tunel").count(), 0, "desligado: nada do túnel")
        S.salvar_config({"endereco_mcp": "https://correria.casa-exemplo.com.br"})
        with mock.patch.object(S, "PORTA_TUNEL", 0):
            self.pg.reload()
            self.opcoes("mcp")
            self.pg.click('[data-a="tunel"]')
            self.aviso("Túnel ligado")
        self.assertTrue(S.ler_config()["tunel"])
        self.assertIsNotNone(S.SERVIDOR_TUNEL["s"], "a porta abriu")
        yaml = self.pg.input_value("#f-tunel")
        self.assertEqual(yaml, "- hostname: correria.casa-exemplo.com.br\n  service: http://127.0.0.1:8444")
        t = self.texto("#mcp")
        self.assertIn("Nada chegou pelo túnel desde que o app abriu · Confira o app Cloudflared e abra o endereço do conector.", t)
        self.assertNotIn("Certificado", t, "pelo túnel, o certificado é o da Cloudflare")
        self.assertNotIn("porta 443 para", t)
        self.assertEqual(self.pg.locator('[data-a="copiar"][data-v="f-tunel"]').count(), 1)
        S.TUNEL["em"] = S.agora_iso()
        self.pg.reload()
        self.opcoes("mcp")
        self.assertRegex(self.texto("#mcp [data-fora]"), r"^Chegou uma conexão pelo túnel hoje às \d\d:\d\d\.$")
        self.assertFalse(self.pg.evaluate("document.documentElement.scrollWidth > innerWidth"))
        # 1.14.0: o túnel é do conector; o webhook, com outro endereço (o do Duck DNS), continua com o caminho dele
        self.pg.click('.abas [data-v="whatsapp"]')
        t = self.texto("#webhook")
        self.assertNotIn("túnel", t)
        self.assertIn("Sem certificado: instale o app Duck DNS", t)
        S.salvar_config({"endereco": "https://correria.casa-exemplo.com.br"})
        self.pg.reload()
        self.opcoes("whatsapp")
        self.assertRegex(self.texto("#webhook [data-fora]"), r"^Chegou uma conexão pelo túnel hoje às \d\d:\d\d\.$", "o mesmo endereço: o webhook também vem pelo túnel")
        self.pg.click('.abas [data-v="mcp"]')
        self.pg.click('[data-a="tunel"]')
        self.aviso("Túnel desligado")
        self.assertIsNone(S.SERVIDOR_TUNEL["s"], "desligado, a porta fecha")
        self.assertEqual(self.erros, [])

    def test_claude_e_gemini(self):
        S.salvar_config({"whatsapp": True})
        self.abrir()
        self.opcoes("mcp")
        self.assertEqual(self.texto("#mcp h2"), "Conector MCP")
        self.assertNotRegex(self.texto("#mcp"), "Claude|Gemini|ChatGPT", "termos genéricos, sem marcas")
        self.assertIn("Desligado.", self.texto("#mcp"))
        self.assertEqual(self.pg.locator("#f-mcp").count(), 0)
        self.pg.click('[data-a="mcp"]')
        self.aviso("Conector ligado")
        self.assertTrue(S.ler_config()["mcp"])
        # 0.15.0: o endereço público e o certificado na própria aba (antes: "Escreva o endereço público na aba WhatsApp")
        self.assertNotIn("aba WhatsApp", self.texto("#mcp"))
        self.assertEqual(self.texto("#mcp .status"), "Sem certificado: instale o app Duck DNS com o Let's Encrypt (as IAs só conectam por https), ou use o túnel da Cloudflare.")
        self.assertIn("O endereço, como o do Duck DNS, tem que abrir de fora na porta 443: no roteador, a 443 vai para a 8443, ou pelo túnel da Cloudflare.", self.texto("#mcp .lead"))
        self.assertEqual(self.pg.locator("#f-mcp").count(), 0)
        self.pg.fill("#f-endereco-mcp", "casa-exemplo.duckdns.org:8443")
        self.pg.press("#f-endereco-mcp", "Tab")
        self.aviso("Endereço salvo")
        self.assertEqual(self.texto(".abas .on"), "MCP", "salva sem sair da aba")
        self.assertEqual(self.pg.input_value("#f-endereco-mcp"), "https://casa-exemplo.duckdns.org:8443")
        self.assertEqual(self.pg.input_value("#f-mcp"), "https://casa-exemplo.duckdns.org:8443/mcp")
        # 1.14.0: o endereço do conector é dele: o do webhook não muda junto (e o contrário)
        self.assertEqual(self.texto('label[for="f-endereco-mcp"]'), "Endereço público do conector")
        self.pg.click('.abas [data-v="whatsapp"]')
        self.assertEqual(self.pg.input_value("#f-endereco"), "", "o do webhook é outro campo")
        self.pg.fill("#f-endereco", "outra-casa.duckdns.org:8443")
        self.pg.press("#f-endereco", "Tab")
        self.aviso("Endereço salvo")
        self.pg.click('.abas [data-v="mcp"]')
        self.assertEqual(self.pg.input_value("#f-endereco-mcp"), "https://casa-exemplo.duckdns.org:8443")
        self.assertEqual(self.pg.input_value("#f-mcp"), "https://casa-exemplo.duckdns.org:8443/mcp")
        self.assertEqual((S.ler_config()["endereco"], S.ler_config()["endereco_mcp"]), ("https://outra-casa.duckdns.org:8443", "https://casa-exemplo.duckdns.org:8443"))
        self.assertEqual(self.texto("#mcp .passos"), "Toque em Copiar.\nNa IA, em Conectores, adicione um conector personalizado e cole o endereço.\n"
                         "Ao entrar, abre uma página com um código: aprove aqui o pedido com o mesmo código.")
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

    def test_tela_cheia_com_o_painel_da_cronologia(self):
        """1.2.0: numa tela grande, com a CronologIA 1.95.0 (o endereço dela no navegador em share/cronologia/integracao.json),
        a Tela cheia põe o painel dela à esquerda e a Conversa à direita; sai pelo botão, pelo Esc e pelo Voltar. 1.3.0: a
        Conversa começa recolhida (uma faixa fina), abre num toque, recolhe sozinha em 5 minutos sem uso ou no Recolher;
        fixada (guardado no aparelho), fica aberta e nunca recolhe."""
        self.publicar_app()
        self.abrir()
        self.pg.set_viewport_size({"width": 1440, "height": 900})
        self.pg.wait_for_timeout(200)
        self.assertEqual(self.pg.locator('[data-a="cheia"]').count(), 0, "sem a CronologIA: sem o botão")
        os.makedirs(os.path.join(S.SHARE_DIR, "cronologia"), exist_ok=True)
        with open(os.path.join(S.SHARE_DIR, "cronologia", "integracao.json"), "w") as f:
            json.dump({"app": "CronologIA", "nome": "CronologIA", "versao": "1.95.0", "tela": "/api/hassio_ingress/AbC123_-xyz"}, f)
        # o monitor todo do navegador fica de mentira (o Chromium dos testes não muda de tamanho nele): só conta os pedidos
        self.pg.add_init_script("window.__fs = 0; Element.prototype.requestFullscreen = function () { window.__fs++; return Promise.resolve(); };")
        self.pg.clock.install()
        self.pg.reload()
        self.pg.wait_for_selector('[data-a="cheia"]')
        self.assertEqual(self.pg.get_attribute('[data-a="cheia"]', "aria-label"), "Tela cheia")
        self.pg.click('[data-a="cheia"]')
        self.pg.wait_for_selector("body.cheia #painel")
        self.assertEqual(self.pg.get_attribute("#painel", "src"), "/api/hassio_ingress/AbC123_-xyz/?painel=1")
        self.assertEqual(self.pg.evaluate("window.__fs"), 1, "pede o monitor todo")
        caixa = lambda sel: self.pg.locator(sel).bounding_box()
        # recolhida de início: a faixa fina à direita, o painel com quase a tela toda
        self.pg.wait_for_selector("body.recolhida .trilho")
        painel, faixa = caixa("#painel"), caixa(".trilho")
        self.assertLessEqual(faixa["width"], 80)
        self.assertGreater(painel["width"], 1440 - 90, "o painel com quase a tela toda")
        self.assertEqual(self.pg.locator("#ch-txt").count(), 0, "a caixa de escrever só com a Conversa aberta")
        self.pg.screenshot(path=os.path.join(os.environ.get("CORRERIA_PRINTS", "/tmp"), "correria-tela-cheia-recolhida.png"))
        # aberta: a Conversa à direita do painel
        self.pg.click('[data-a="conversa-abrir"]')
        self.pg.wait_for_selector("body.cheia:not(.recolhida) #ch-txt")
        painel, app, pe = caixa("#painel"), caixa("#app"), caixa(".ch-pe")
        self.assertEqual(painel["x"], 0)
        self.assertGreater(painel["width"], 900, "o painel com a maior parte da tela")
        self.assertAlmostEqual(app["x"], painel["width"], delta=2, msg="a Conversa logo à direita do painel")
        self.assertAlmostEqual(pe["x"], app["x"], delta=2, msg="a caixa de escrever na coluna da Conversa")
        self.assertEqual(self.pg.locator('.cab-bts [data-a="cheia"]').get_attribute("aria-label"), "Sair da tela cheia")
        # a conversa continua funcionando ao lado do painel, sem redesenhar o painel
        self.pg.evaluate("document.querySelector('#painel').dataset.marca = '1'")
        self.pg.fill("#ch-txt", "Quanto gastei?")
        self.pg.click('[data-a="ch-enviar"]')
        self.pg.wait_for_selector(".ch-msg.ia .ch-bolha p")
        self.assertEqual(self.pg.get_attribute("#painel", "data-marca"), "1", "o painel não recarrega com a conversa")
        self.pg.screenshot(path=os.path.join(os.environ.get("CORRERIA_PRINTS", "/tmp"), "correria-tela-cheia.png"))
        # 3 minutos sem uso (1.5.0; antes, 5): recolhe sozinha (usar antes conta o tempo de novo)
        self.pg.clock.fast_forward("02:00")
        self.pg.click("#ch-txt")
        self.pg.clock.fast_forward("02:00")
        self.assertEqual(self.pg.locator("body.recolhida").count(), 0, "usada há 2 minutos: continua aberta")
        self.pg.clock.fast_forward("01:05")
        self.pg.wait_for_selector("body.recolhida .trilho")
        self.assertEqual(self.pg.get_attribute("#painel", "data-marca"), "1", "recolher não recarrega o painel")
        # o Recolher
        self.pg.click('[data-a="conversa-abrir"]')
        self.pg.click('[data-a="conversa-recolher"]')
        self.pg.wait_for_selector("body.recolhida .trilho")
        # fixada: aberta, sem o Recolher, e não recolhe mais (nem na próxima vez)
        self.pg.click('[data-a="conversa-abrir"]')
        self.pg.click('[data-a="conversa-fixar"]')
        self.assertEqual(self.pg.get_attribute('[data-a="conversa-fixar"]', "aria-pressed"), "true")
        self.assertEqual(self.pg.locator('[data-a="conversa-recolher"]').count(), 0)
        self.pg.clock.fast_forward("10:00")
        self.assertEqual(self.pg.locator("body.recolhida").count(), 0, "fixada: não recolhe")
        self.pg.keyboard.press("Escape")
        self.pg.wait_for_function("() => !document.body.classList.contains('cheia') && !document.querySelector('#painel')")
        self.pg.click('[data-a="cheia"]')
        self.pg.wait_for_selector("body.cheia:not(.recolhida) #ch-txt")
        self.pg.click('[data-a="conversa-fixar"]')  # solta
        self.assertEqual(self.pg.get_attribute('[data-a="conversa-fixar"]', "aria-pressed"), "false")
        # o Voltar do celular também sai; numa tela estreita, o botão some e a Tela cheia termina
        self.pg.go_back()
        self.pg.wait_for_function("() => !document.body.classList.contains('cheia')")
        self.pg.click('[data-a="cheia"]')
        self.pg.wait_for_selector("body.cheia", state="attached")
        self.pg.set_viewport_size({"width": 900, "height": 900})
        self.pg.wait_for_function("() => !document.body.classList.contains('cheia') && !document.querySelector('[data-a=\\'cheia\\']')")

    def test_opcoes_tela_cheia_e_casa(self):
        """1.5.0: Configurações › Opções › Tela cheia (com a CronologIA): em quanto tempo a Conversa recolhe sozinha, 3
        minutos de início; Configurações › Integrações › Casa: mexer na casa pelo Assist, ligado de início."""
        self.publicar_app()
        os.makedirs(os.path.join(S.SHARE_DIR, "cronologia"), exist_ok=True)
        with open(os.path.join(S.SHARE_DIR, "cronologia", "integracao.json"), "w") as f:
            json.dump({"app": "cronologia", "nome": "CronologIA", "versao": "1.99.0", "tela": "/api/hassio_ingress/AbC123_-xyz"}, f)
        self.abrir()
        self.opcoes()
        self.assertEqual(self.pg.locator("#casa .sw").get_attribute("aria-checked"), "true")
        self.assertIn("Só dentro do Home Assistant.", self.texto("#casa"))
        self.pg.click("#casa .sw")
        self.pg.wait_for_selector('#casa .sw[aria-checked="false"]')
        self.assertFalse(S.ler_config()["casa"])
        self.pg.click('.abas [data-v="opcoes"]')
        self.pg.wait_for_selector("#tela-cheia")
        self.assertEqual(self.pg.locator("#tela-cheia .chip").all_inner_texts(), ["1 min", "3 min", "5 min", "10 min"])
        self.assertEqual(self.pg.locator('#tela-cheia .chip[aria-checked="true"]').inner_text(), "3 min")
        self.pg.click('#tela-cheia .chip[data-v="5"]')
        self.pg.wait_for_selector('#tela-cheia .chip[data-v="5"][aria-checked="true"]')
        self.assertEqual(S.ler_config()["recolher"], 5)
        caixas = self.pg.evaluate("[...document.querySelectorAll('#tela-cheia .chip')].map((b) => Math.round(b.getBoundingClientRect().width))")
        self.assertEqual(len(set(caixas)), 1, f"os quatro do mesmo tamanho ({caixas})")
        self.assertFalse(self.pg.evaluate("document.documentElement.scrollWidth > innerWidth"))
        # 1.6.1: o ícone na mesma linha do título; os tempos em duas linhas, cada um numa linha só
        tit = self.pg.evaluate("""(() => { const b = document.querySelector('#tela-cheia .campo > b'), i = b.querySelector('svg').getBoundingClientRect();
          const r = document.createRange(); r.selectNodeContents(b.lastChild); const t = r.getBoundingClientRect();
          return Math.abs((i.top + i.bottom) / 2 - (t.top + t.bottom) / 2) < 6; })()""")
        self.assertTrue(tit, "o ícone ao lado do título")
        linhas = self.pg.evaluate("[...document.querySelectorAll('#tela-cheia .chip')].map((b) => Math.round(b.getBoundingClientRect().top))")
        self.assertEqual((linhas[0] == linhas[1], linhas[2] == linhas[3], linhas[2] > linhas[0]), (True, True, True), f"duas linhas ({linhas})")
        alturas = self.pg.evaluate("[...document.querySelectorAll('#tela-cheia .chip')].map((b) => Math.round(b.getBoundingClientRect().height))")
        self.assertEqual(len(set(alturas)), 1, f"o 10 min não quebra ({alturas})")
        self.pg.locator("#tela-cheia").screenshot(path=os.path.join(os.environ.get("CORRERIA_PRINTS", "/tmp"), "correria-opcoes-tela-cheia.png"))

    PAINEL_FALSO = """<!doctype html><body style="margin:0">
<button id="conv" onclick="parent.postMessage({painel: 'conversa'}, location.origin)">Conversa</button>
<button id="sair" onclick="parent.postMessage({painel: 'sair'}, location.origin)">Sair</button>
<div id="folha" style="position: absolute; left: 900px; top: 70px; width: 500px; height: 780px">Folha</div>
<script>
window.__c = [];
addEventListener('message', (e) => {
  if (!e.data || !e.data.conversa) return;
  __c.push(e.data.conversa);
  const a = e.data.conversa.aberta;
  document.getElementById('folha').style.display = a ? 'none' : '';
  parent.postMessage(a ? {painel: 'lugar', x: 900, y: 70, w: 500, h: 780} : {painel: 'lugar', x: 0, y: 0, w: 0, h: 0}, location.origin);
});
parent.postMessage({painel: 'pronto'}, location.origin);
</script></body>"""

    def test_tela_cheia_com_os_botoes_no_painel(self):
        """1.4.0: com a CronologIA 1.97.0 ou mais nova (&conversa=1), os botões da Conversa e do Sair ficam no alto do painel
        dela, sem a faixa daqui: o painel com a tela toda, e a Conversa aberta no lugar da folha (o painel diz onde). Aqui se
        conta ao painel se ela está aberta; Ctrl+Espaço abre e recolhe. Mensagens de outra janela não valem."""
        self.publicar_app()
        os.makedirs(os.path.join(S.SHARE_DIR, "cronologia"), exist_ok=True)
        with open(os.path.join(S.SHARE_DIR, "cronologia", "integracao.json"), "w") as f:
            json.dump({"app": "cronologia", "nome": "CronologIA", "versao": "1.97.0", "tela": "/api/hassio_ingress/AbC123_-xyz"}, f)
        self.abrir()
        self.pg.set_viewport_size({"width": 1440, "height": 900})
        self.pg.route("**/api/hassio_ingress/**", lambda r: r.fulfill(body=self.PAINEL_FALSO, content_type="text/html"))
        self.pg.add_init_script("Element.prototype.requestFullscreen = function () { return Promise.resolve(); };")
        self.pg.reload()
        self.pg.click('[data-a="cheia"]')
        self.pg.wait_for_selector("body.cheia.cab-painel.recolhida #painel", state="attached")
        self.assertEqual(self.pg.get_attribute("#painel", "src"), "/api/hassio_ingress/AbC123_-xyz/?painel=1&conversa=1")
        quadro = self.pg.frame_locator("#painel")
        fr = self.pg.frame(url=lambda u: "hassio_ingress" in u)
        fr.wait_for_function("() => window.__c.length >= 1")
        self.assertEqual(fr.evaluate("window.__c.at(-1)"), {"aberta": False, "novidade": False}, "conta ao painel: recolhida")
        caixa = lambda sel: self.pg.locator(sel).bounding_box()
        self.assertEqual(self.pg.locator(".trilho").count(), 0, "sem a faixa")
        self.assertEqual(caixa("#painel")["width"], 1440, "o painel com a tela toda")
        self.assertFalse(self.pg.locator("#app").is_visible())
        # o botão do painel abre a Conversa no lugar da folha
        quadro.locator("#conv").click()
        self.pg.wait_for_selector("body.cab-painel:not(.recolhida):not(.espera-lugar) #ch-txt")
        app, pe = caixa("#app"), caixa(".ch-pe")
        for k, v in (("x", 900), ("y", 70), ("width", 500), ("height", 780)):
            self.assertAlmostEqual(app[k], v, delta=1, msg=f"no lugar da folha ({k})")
        self.assertTrue(pe["x"] >= 900 and pe["y"] + pe["height"] <= 70 + 780 + 1, "a caixa de escrever dentro do quadro")
        self.assertEqual(fr.evaluate("window.__c.at(-1).aberta"), True)
        self.assertEqual(self.pg.locator('.cab-bts [data-a="cheia"]').count(), 0, "o Sair fica no painel")
        self.pg.fill("#ch-txt", "Quanto gastei?")
        self.pg.click('[data-a="ch-enviar"]')
        self.pg.wait_for_selector(".ch-msg.ia .ch-bolha p")
        self.assertAlmostEqual(caixa("#app")["y"], 70, delta=1, msg="a conversa rola dentro do quadro, que não sai do lugar")
        self.pg.screenshot(path=os.path.join(os.environ.get("CORRERIA_PRINTS", "/tmp"), "correria-tela-cheia-no-lugar-da-folha.png"))
        # Ctrl+Espaço: recolhe e abre de novo
        self.pg.keyboard.press("Control+Space")
        self.pg.wait_for_selector("body.cab-painel.recolhida", state="attached")
        fr.wait_for_function("() => window.__c.at(-1).aberta === false")
        self.assertTrue(quadro.locator("#folha").is_visible(), "a folha volta")
        self.pg.keyboard.press("Control+Space")
        self.pg.wait_for_selector("body.cab-painel:not(.recolhida) #ch-txt")
        # só as mensagens do quadro valem
        self.pg.evaluate("postMessage({painel: 'sair'}, location.origin)")
        self.pg.wait_for_timeout(200)
        self.assertEqual(self.pg.locator("body.cheia").count(), 1, "de outra janela: nada")
        quadro.locator("#sair").click()
        self.pg.wait_for_function("() => !document.body.classList.contains('cheia') && !document.querySelector('#painel')")
        self.assertEqual(self.pg.evaluate("document.body.style.getPropertyValue('--lx')"), "", "saindo, o lugar some")

    def test_conversar_com_a_ia(self):
        self.abrir_conversa()
        self.assertEqual(self.texto(".cab h1"), "Conversa")
        self.pg.wait_for_selector(".ch-sug .chip")  # as sugestões aparecem quando a conversa guardada chega
        self.assertEqual(self.pg.locator(".ch-sug .chip").all_inner_texts(), G6)
        self.assertEqual(self.pg.get_attribute("#ch-pri", "aria-label"), "Falar", "vazio: o botão é o microfone")
        # 1.16.2: a caixa vazia não rola nem corta o texto de exemplo (ele quebrava em duas linhas, com uma barra de rolagem)
        self.assertEqual(self.pg.get_attribute("#ch-txt", "placeholder"), "Sua pergunta")
        for larg in (390, 320):
            self.pg.set_viewport_size({"width": larg, "height": 800})
            cx = self.pg.evaluate("""() => { const t = document.querySelector('#ch-txt'), c = document.createElement('canvas').getContext('2d'), s = getComputedStyle(t);
                c.font = s.fontWeight + ' ' + s.fontSize + ' ' + s.fontFamily;
                return [t.scrollHeight <= t.clientHeight + 1, s.overflowY, c.measureText(t.placeholder).width, t.clientWidth - parseFloat(s.paddingLeft) - parseFloat(s.paddingRight)]; }""")
            self.assertTrue(cx[0] and cx[1] == "hidden" and cx[2] <= cx[3], f"{larg} px: sem rolagem e o texto de exemplo inteiro ({cx})")
        self.pg.set_viewport_size({"width": 390, "height": 800})
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

    def test_sim_e_nao_para_tocar(self):
        """1.10.0: a mudança que espera o sim (a última mensagem, com confirmar) mostra o Sim e o Não, do mesmo tamanho e
        lado a lado; um toque manda a resposta; depois os botões somem. Uma mensagem de antes com confirmar não tem botões."""
        import json as _json
        espera = [{"papel": "eu", "texto": "lança 32,50 de feira", "em": "2026-11-18T10:00:00"},
                  {"papel": "ia", "texto": "Vou fazer isto:\n- Lançar R$ 32,50 de Feira hoje\n\nToque em *Sim* para confirmar.", "em": "2026-11-18T10:00:01",
                   "confirmar": True, "app": "GerencIA", "app_id": "_ia"}]
        feito = espera + [{"papel": "eu", "texto": "Sim", "em": "2026-11-18T10:00:05"},
                          {"papel": "ia", "texto": "Feito!\n- Lançado: Feira", "em": "2026-11-18T10:00:06", "app": "GerencIA", "app_id": "_ia"}]
        enviados = []

        def conversa(route):
            if route.request.method == "POST":
                enviados.append(_json.loads(route.request.post_data or "{}"))
                return route.fulfill(status=200, content_type="application/json", body=_json.dumps({"mensagens": feito, "conversa": "c1"}))
            return route.fulfill(status=200, content_type="application/json", body=_json.dumps({"mensagens": espera, "pessoa": "Ana", "ola": "", "conversa": "c1"}))
        self.publicar_app()
        self.pg = self.nav.new_page(viewport={"width": 390, "height": 844}, color_scheme="dark")
        self.addCleanup(self.pg.close)
        self.pg.on("pageerror", lambda e: self.erros.append(str(e)))
        self.pg.route("**/api/conversa", conversa)
        self.pg.goto(self.url)
        self.pg.wait_for_selector(".ch-sim .btn")
        self.assertEqual(self.pg.locator(".ch-sim .btn").all_inner_texts(), ["Não", "Sim"])
        caixas = self.pg.evaluate("[...document.querySelectorAll('.ch-sim .btn')].map(b => { const r = b.getBoundingClientRect(); return [Math.round(r.width), Math.round(r.top)]; })")
        self.assertEqual(caixas[0], caixas[1], "do mesmo tamanho, lado a lado")
        self.pg.click('.ch-sim [data-v="Sim"]')
        self.pg.wait_for_selector(".ch-msg.ia >> text=Feito!")
        self.assertEqual(enviados, [{"texto": "Sim"}])
        self.assertEqual(self.pg.locator(".ch-sim").count(), 0, "respondido: sem os botões")
        self.assertFalse(self.pg.evaluate("document.documentElement.scrollWidth > innerWidth"))

    def test_enter_envia(self):
        """1.4.1: com teclado, o Enter envia e o Shift+Enter quebra a linha (como no WhatsApp Web); no celular, o Enter do
        teclado da tela quebra a linha, até chegar uma tecla de um teclado de verdade."""
        self.abrir_conversa()
        self.pg.click("#ch-txt")
        self.pg.keyboard.type("Quanto")
        self.pg.keyboard.press("Shift+Enter")
        self.pg.keyboard.type("gastei?")
        self.assertEqual(self.pg.input_value("#ch-txt"), "Quanto\ngastei?", "Shift+Enter: outra linha")
        self.pg.keyboard.press("Enter")
        self.pg.wait_for_selector(".ch-msg.ia .ch-bolha p")
        self.assertEqual(self.texto(".ch-msg.eu .ch-bolha"), "Quanto\ngastei?")
        self.assertEqual(self.pg.input_value("#ch-txt"), "")
        # um celular (sem mouse): o Enter quebra a linha; uma tecla de verdade (um teclado ligado) e ele passa a enviar
        ctx = self.nav.new_context(viewport={"width": 390, "height": 760}, is_mobile=True, has_touch=True)
        self.addCleanup(ctx.close)
        pg = ctx.new_page()
        pg.goto(self.pg.url)
        pg.wait_for_selector(".ch-msg.ia")  # a conversa de antes (a mesma da tela)
        n = pg.locator(".ch-msg.eu").count()
        self.assertFalse(pg.evaluate("matchMedia('(any-hover: hover), (any-pointer: fine)').matches"))
        pg.fill("#ch-txt", "Oi")
        pg.press("#ch-txt", "Enter")
        self.assertEqual(pg.input_value("#ch-txt"), "Oi\n", "teclado da tela: outra linha")
        self.assertEqual(pg.locator(".ch-msg.eu").count(), n)
        pg.keyboard.type("x")
        pg.keyboard.press("Enter")
        pg.wait_for_function(f"() => document.querySelectorAll('.ch-msg.eu').length > {n}")
        self.assertEqual(pg.input_value("#ch-txt"), "")

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
        self.pg.wait_for_selector('[data-a="ch-menu"]')
        self.pg.click('[data-a="ch-menu"]')
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
        self.pg.click('[data-a="ch-menu"]')
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
        self.pg.wait_for_selector('[data-a="ch-menu"]')
        self.pg.click('[data-a="ch-menu"]')
        self.pg.click('[data-a="ch-camera"]')
        self.pg.wait_for_selector("#camera .cam-msg")
        self.assertIn("Dá para tirar a foto pelo celular e escolher.", self.texto("#camera .cam-msg p"))
        with self.pg.expect_file_chooser() as fc:
            self.pg.click('#camera [data-a="cam-galeria"]')
        self.assertEqual(self.pg.locator("#camera").count(), 0)
        fc.value.set_files(files=[{"name": "nota.jpg", "mimeType": "image/jpeg", "buffer": b"\xff\xd8\xff\xe0foto"}])
        self.pg.wait_for_selector(".ch-prev")
        self.assertEqual(self.texto(".ch-prev span"), "nota.jpg")

    def test_anexar_tirar_foto_escolher_fotos_ou_arquivo(self):
        """1.1.0: um botão só (Anexar) abre Tirar foto, Escolher fotos (a galeria) e Escolher arquivo (foto ou PDF)."""
        self.abrir_conversa()
        self.assertEqual(self.pg.locator(".ch-menu").count(), 0)
        self.pg.click('[data-a="ch-menu"]')
        self.assertEqual(self.pg.locator(".ch-menu .ch-op").all_inner_texts(), ["Tirar foto", "Escolher fotos", "Escolher arquivo"])
        self.assertEqual(self.pg.locator(".ch-menu .ch-op svg").count(), 3, "cada opção com o seu ícone")
        self.assertEqual(self.pg.get_attribute("#ch-galeria", "accept"), "image/*")
        self.assertIsNone(self.pg.get_attribute("#ch-galeria", "capture"), "a galeria, não a câmera")
        self.assertEqual(self.pg.get_attribute("#ch-arquivo", "accept"), "image/*,application/pdf")
        larg = self.pg.evaluate("[...document.querySelectorAll('.ch-barra .ch-bt')].map(b => Math.round(b.getBoundingClientRect().width))")
        self.assertTrue(all(w == 46 for w in larg), f"os botões redondos do mesmo tamanho ({larg})")
        self.pg.screenshot(path=os.path.join(S.DATA_DIR, "anexar.png"))
        with self.pg.expect_file_chooser() as fc:
            self.pg.click('[data-a="ch-galeria"]')
        self.assertEqual(self.pg.locator(".ch-menu").count(), 0, "escolher fecha o menu")
        fc.value.set_files(files=[{"name": "recibo.jpg", "mimeType": "image/jpeg", "buffer": b"\xff\xd8\xff\xe0foto"}])
        self.pg.wait_for_selector(".ch-prev")
        self.assertEqual(self.texto(".ch-prev span"), "recibo.jpg")
        self.pg.click('[data-a="ch-menu"]')
        self.pg.click('[data-a="ch-menu"]')
        self.assertEqual(self.pg.locator(".ch-menu").count(), 0, "o mesmo botão fecha o menu")
        self.assertFalse(self.pg.evaluate("document.documentElement.scrollWidth > innerWidth"))

    def test_perguntas_prontas(self):
        """1.1.0: as perguntas da conversa vazia viram da pessoa (Editar perguntas, no aparelho) e o ✨ abre a qualquer momento."""
        self.abrir_conversa()
        self.pg.wait_for_selector('[data-a="ch-ed-abrir"]')
        self.pg.click('[data-a="ch-ed-abrir"]')
        lin = ".ch-ed-lin:not(.ch-ed-modelo) > .ch-ed-txt"
        self.assertEqual(self.pg.locator(lin).evaluate_all('els => els.map(e => e.value)'), G6)
        # 1.10.0: os modelos: as outras perguntas dos apps ligados (aqui só o GerencIA) e as de todos os apps
        self.assertEqual(self.pg.locator(".ch-ed-modelo > span:first-child").all_inner_texts(), ["Resume o meu dia", "O que eu tenho para fazer hoje?", "O que vence nos próximos dias, em todos os apps?"])
        self.pg.click('.ch-ed-modelo >> nth=0')
        self.assertEqual(self.pg.locator(lin).evaluate_all('els => els.map(e => e.value)')[-1], "Resume o meu dia", "um toque põe o modelo na lista")
        self.assertEqual(self.pg.locator(".ch-ed-modelo").count(), 2)
        self.pg.click('[data-a="ch-ed-tirar"] >> nth=6')
        self.pg.click('[data-a="ch-ed-tirar"] >> nth=0')
        self.pg.fill("#ch-ed-txt", "Quanto sobrou no mês?")
        self.pg.click('[data-a="ch-ed-add"]')
        self.assertEqual(self.pg.input_value("#ch-ed-txt"), "", "Adicionar limpa a caixa")
        self.pg.fill("#ch-ed-txt", "Qual a maior despesa?")
        self.pg.press("#ch-ed-txt", "Enter")
        self.assertEqual(self.pg.locator(lin).evaluate_all('els => els.map(e => e.value)'), G6[1:] + ["Quanto sobrou no mês?", "Qual a maior despesa?"])
        larg = self.pg.evaluate("[...document.querySelectorAll('.ch-ed-bts .btn')].map(b => Math.round(b.getBoundingClientRect().width))")
        self.assertEqual(len(set(larg)), 1, f"Padrão e Pronto do mesmo tamanho ({larg})")
        self.pg.screenshot(path=os.path.join(S.DATA_DIR, "perguntas.png"))
        self.pg.click('[data-a="ch-ed-pronto"]')
        self.assertEqual(self.pg.locator(".ch-sug .chip").all_inner_texts(), G6[1:] + ["Quanto sobrou no mês?", "Qual a maior despesa?"])
        self.pg.reload()
        self.pg.wait_for_selector(".ch-sug .chip")
        self.assertEqual(self.pg.locator(".ch-sug .chip").count(), 7, "guardadas no aparelho")
        # com a conversa andando: o ✨ ao lado da caixa abre as mesmas
        self.assertEqual(self.pg.locator('[data-a="ch-rapidas"]').count(), 0, "vazia: as perguntas já estão à vista")
        self.pg.click('[data-a="ch-sug"] >> nth=5')
        self.pg.wait_for_selector(RESPOSTA)
        self.assertEqual(self.app.pedidos[-1][3]["texto"], "Quanto sobrou no mês?")
        self.pg.click('[data-a="ch-rapidas"]')
        self.assertEqual(self.pg.locator(".ch-rapidas .chip").count(), 7)
        self.assertEqual(self.pg.get_attribute('[data-a="ch-rapidas"]', "aria-expanded"), "true")

        self.pg.click('.ch-rapidas [data-a="ch-sug"] >> nth=2')
        self.pg.wait_for_function("() => document.querySelectorAll('.ch-msg.eu').length === 2")
        self.assertEqual(self.pg.locator(".ch-rapidas").count(), 0, "perguntar fecha as perguntas")
        # Padrão volta às dos apps
        self.pg.click('[data-a="ch-rapidas"]')
        self.pg.click('.ch-rapidas [data-a="ch-ed-abrir"]')
        self.pg.click('[data-a="ch-ed-padrao"]')
        self.pg.click('[data-a="ch-ed-pronto"]')
        self.assertEqual(self.pg.locator(".ch-rapidas .chip").all_inner_texts(), G6)
        self.assertIsNone(self.pg.evaluate("localStorage.getItem('correria-perguntas')"), "as dos apps: nada guardado")
        self.assertFalse(self.pg.evaluate("document.documentElement.scrollWidth > innerWidth"))
        self.assertEqual(self.erros, [])


    def test_mudar_uma_pergunta(self):
        """1.12.0: em Editar perguntas, um toque numa pergunta muda o texto dela (o Enter só termina); o Pronto guarda como
        ficou e uma apagada até ficar vazia sai."""
        self.abrir_conversa()
        self.pg.click('[data-a="ch-ed-abrir"]')
        q = ".ch-ed-lin:not(.ch-ed-modelo) > .ch-ed-txt"
        self.pg.locator(q).nth(1).fill(G6[1] + " Hoje")
        self.pg.locator(q).nth(1).press("Enter")
        self.assertEqual(self.pg.locator(q).nth(1).input_value(), G6[1] + " Hoje", "o Enter não quebra a linha")
        self.assertFalse(self.pg.evaluate("document.activeElement.classList.contains('ch-ed-txt')"), "o Enter termina")
        self.pg.locator(q).nth(2).fill("")
        self.pg.click('[data-a="ch-ed-pronto"]')
        self.assertEqual(self.pg.locator(".ch-sug .chip").all_inner_texts(), [G6[0], G6[1] + " Hoje"] + G6[3:])
        self.assertEqual(self.erros, [])

    def test_recolher_as_perguntas(self):
        """1.11.0: em Editar perguntas, Perguntas prontas e Mais perguntas fecham num toque no título (a seta no canto) e o
        aparelho lembra; de início, as duas abertas, com a contagem."""
        self.abrir_conversa()
        self.pg.click('[data-a="ch-ed-abrir"]')
        cabs = '[data-a="ch-ed-dobra"]'
        self.assertEqual([t.strip() for t in self.pg.locator(cabs).all_inner_texts()], ["Perguntas prontas (6)", "Mais perguntas (3)"])
        self.assertEqual(self.pg.locator(f'{cabs}[aria-expanded="true"]').count(), 2, "de início, abertas")
        self.pg.click(f'{cabs}[data-v="mais"]')
        self.assertEqual(self.pg.get_attribute(f'{cabs}[data-v="mais"]', "aria-expanded"), "false")
        self.assertEqual(self.pg.locator(".ch-ed-modelo").count(), 0, "fechada, sem os modelos")
        self.assertEqual(self.pg.locator(".ch-ed-lin:not(.ch-ed-modelo)").count(), 6, "as prontas continuam")
        self.pg.click(f'{cabs}[data-v="prontas"]')
        self.assertEqual((self.pg.locator(".ch-ed-lin").count(), self.pg.locator("#ch-ed-txt").count()), (0, 0), "as duas fechadas")
        self.assertEqual(self.pg.locator(".ch-ed-bts .btn").count(), 2, "Padrão e Pronto ficam")
        girada = self.pg.evaluate("getComputedStyle(document.querySelector('[data-v=\"mais\"] .dobra-ic')).transform")
        self.assertEqual(girada, "none", "fechada, a seta deitada")
        self.assertFalse(self.pg.evaluate("document.documentElement.scrollWidth > innerWidth"))
        self.pg.reload()
        self.pg.wait_for_selector('[data-a="ch-ed-abrir"]')
        self.pg.click('[data-a="ch-ed-abrir"]')
        self.assertEqual(self.pg.locator(f'{cabs}[aria-expanded="false"]').count(), 2, "o aparelho lembra")
        self.pg.click(f'{cabs}[data-v="prontas"]')
        self.pg.click(f'{cabs}[data-v="mais"]')
        self.assertEqual((self.pg.locator(".ch-ed-lin:not(.ch-ed-modelo)").count(), self.pg.locator(".ch-ed-modelo").count()), (6, 3))

    def test_mandar_uma_foto(self):
        self.abrir_conversa()
        self.pg.click('[data-a="ch-menu"]')
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
        """0.15.0: as Últimas mensagens ficam na aba WhatsApp; o que as IAs conectadas mudaram, na aba MCP."""
        S.salvar_config({"whatsapp": True})
        self.abrir()
        self.opcoes("apps")
        self.assertEqual(self.pg.locator("#mensagens").count(), 0, "não fica mais em Apps")
        self.pg.click('.abas [data-v="whatsapp"]')
        ids = self.pg.evaluate("[...document.querySelectorAll('.card')].map(c => c.id)")
        self.assertEqual(ids[-2:], ["pessoas", "mensagens"], "depois de Quem conversa")
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
        S.registrar("mcp", "Claude · Ana", "Lançado: Feira · R$ 12", "GerencIA", canal="mcp")
        self.pg.evaluate("window.CORRERIA_TESTE.carregar()")
        self.pg.wait_for_timeout(200)
        self.assertEqual(self.pg.locator("#mensagens .msg").count(), 4, "a mudança de uma IA não entra nas mensagens do WhatsApp")
        self.pg.click('#mensagens [data-a="limpar"]')
        self.aviso("Mensagens apagadas")
        self.assertEqual(self.texto("#mensagens .vazio"), "Nenhuma mensagem ainda.")
        self.pg.click('.abas [data-v="mcp"]')
        self.assertEqual(self.pg.locator("#mudancas").count(), 0, "0.16.3: com o conector desligado, nada dele (as Últimas mudanças dependem dele)")
        S.salvar_config({"mcp": True})
        self.pg.evaluate("window.CORRERIA_TESTE.carregar()")
        self.pg.wait_for_selector("#mcp .sub-box #mudancas")
        self.assertEqual(self.texto("#mcp .sub-box #mudancas summary"), "Últimas mudanças (1)", "0.16.3: no quadro do Conector MCP, embaixo de Ligar o conector")
        self.assertFalse(self.pg.evaluate("document.querySelector('#mudancas').open"), "0.17.0: recolhidas de início")
        self.pg.click("#mudancas summary")
        self.assertEqual(self.pg.locator("section#mudancas").count(), 0, "sem um cartão à parte")
        self.assertEqual(self.pg.evaluate("[...document.querySelectorAll('#mcp .sub-box .msg')].map(m => [m.querySelector('b').textContent, m.querySelector('p').textContent])"),
                         [["Claude · Ana", "Lançado: Feira · R$ 12 · GerencIA"]])
        self.pg.click('#mcp [data-a="limpar"]')
        self.aviso("Mudanças apagadas")
        self.assertEqual(self.texto("#mcp .sub-box .vazio"), "Nenhuma mudança ainda.")
        S.salvar_config({"mcp": False})

    def test_tudo_pronto(self):
        self.publicar_app()
        S.salvar_config({"numero_id": MetaFalsa.NUMERO_ID, "token": TOKEN, "segredo": "segredo-do-app-123", "endereco": "casa-exemplo.duckdns.org:8443"})
        S.salvar_pessoa("person.ana", ANA)
        S.ESTADO["verificado_em"] = S.agora_iso()
        with mock.patch.object(S, "certificado", return_value=("/ssl/fullchain.pem", "/ssl/privkey.pem")):
            self.abrir()
            self.opcoes("whatsapp")
            self.assertEqual(self.pg.locator(".sync").count(), 0, "0.16.1: o estado fica só no cartão do WhatsApp")
            self.assertIn("Áudios do WhatsApp viram texto pelo Fala simulada (teste).", self.pg.locator("#whatsapp .status").all_inner_texts(),
                          "0.15.0: o áudio na aba do WhatsApp, escrito por extenso")
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
        # 1.14.1: os textos de cima iguais aos dos outros apps
        self.assertEqual(self.texto("#tema .lead"), "Cada aparelho guarda a sua escolha. Sistema segue o do Home Assistant.")
        self.assertEqual(self.texto("#cor .lead"), "Vale para todos os aparelhos.")
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

    def test_apagar_as_conversas_velhas(self):
        """1.7.0: Configurações › Opções › Conversas: as paradas há mais de 7, 30 ou 90 dias (30 de início) saem sozinhas, ou
        nunca; os quatro do mesmo tamanho, em duas linhas."""
        self.abrir()
        self.opcoes()
        self.pg.click('.abas [data-v="opcoes"]')
        self.pg.wait_for_selector("#conversas-velhas")
        self.assertEqual(self.texto("#conversas-velhas h2"), "Conversas")
        chips = [t.strip() for t in self.pg.locator("#conversas-velhas .chip").all_inner_texts()]
        self.assertEqual(chips, ["7 dias", "30 dias", "90 dias", "Sempre"])
        self.assertEqual(self.texto("#conversas-velhas .campo > b"), "Guardar as conversas por")
        self.assertEqual(self.texto('#conversas-velhas .chip[aria-checked="true"]'), "30 dias", "30 de início")
        self.pg.click('#conversas-velhas [data-v="0"]')
        self.pg.wait_for_selector('#conversas-velhas [data-v="0"][aria-checked="true"]')
        self.assertEqual(S.ler_config()["apagar_dias"], 0)
        self.pg.click('#conversas-velhas [data-v="7"]')
        self.pg.wait_for_selector('#conversas-velhas [data-v="7"][aria-checked="true"]')
        self.assertEqual(S.ler_config()["apagar_dias"], 7)
        caixas = self.pg.evaluate("[...document.querySelectorAll('#conversas-velhas .chip')].map(b => { const r = b.getBoundingClientRect(); return [Math.round(r.width), Math.round(r.height)]; })")
        self.assertEqual(len(set(map(tuple, caixas))), 1, f"os quatro do mesmo tamanho ({caixas})")
        S.salvar_config({"apagar_dias": 30})

    def test_o_fundo_e_os_cartoes_do_tema_do_home_assistant(self):
        """1.9.0: o fundo e os cartões são os do tema do Home Assistant (hatema.js, o mesmo arquivo em todos os apps), para
        todos os apps terem o mesmo fundo. Dentro de um Home Assistant de mentira (a mesma origem, como no Ingress), com um
        tema dele, claro e depois escuro com o app aberto: o fundo e o cartão dele. Sozinho, os do tema padrão."""
        ha = """<!doctype html><html style="--primary-background-color:#eef3fb;--card-background-color:#fcfdff"><body style="margin:0">
<home-assistant></home-assistant><iframe id="app" src="/app/" style="position:fixed;inset:0;width:100%;height:100%;border:0"></iframe>
<script>document.querySelector("home-assistant").hass = { themes: { darkMode: false } };
window.modo = (dark, bg, card) => { document.querySelector("home-assistant").hass = { themes: { darkMode: dark } };
  document.documentElement.style.setProperty("--primary-background-color", bg); document.documentElement.style.setProperty("--card-background-color", card); };</script></body></html>"""
        base = self.url.rstrip("/")

        def servir(route):
            u = route.request.url
            if u.rstrip("/") == "http://ha.test":
                route.fulfill(body=ha, content_type="text/html")
            elif u.startswith("http://ha.test/app/"):
                route.fulfill(response=route.fetch(url=base + "/" + u[len("http://ha.test/app/"):]))  # como o Ingress
            else:
                route.fulfill(status=404, body="")

        cores = "() => ['--ha-bg-light', '--ha-card-light', '--ha-bg-dark', '--ha-card-dark'].map((v) => document.documentElement.style.getPropertyValue(v))"
        fundo = "() => getComputedStyle(document.body).backgroundColor"
        cartao = "() => { const d = document.createElement('div'); d.style.background = 'var(--card)'; document.body.append(d); const c = getComputedStyle(d).backgroundColor; d.remove(); return c; }"
        ctx = self.nav.new_context(viewport={"width": 390, "height": 844}, color_scheme="light")
        self.addCleanup(ctx.close)
        ctx.route("http://ha.test/**", servir)
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: self.erros.append(str(e)))
        pg.goto("http://ha.test/")
        fr = pg.frames[1]
        fr.wait_for_selector("#ch-txt")
        pg.wait_for_timeout(500)
        self.assertEqual(fr.evaluate("() => window.__haTema.doHA"), "light")
        self.assertEqual(fr.evaluate(cores), ["#eef3fb", "#fcfdff", "#111111", "#1c1c1c"])
        self.assertEqual(fr.evaluate("() => document.documentElement.dataset.theme"), "light", "o claro do Home Assistant")
        self.assertEqual(fr.evaluate(fundo), "rgb(238, 243, 251)", "o fundo do tema claro")
        self.assertEqual(fr.evaluate(cartao), "rgb(252, 253, 255)", "o cartão do tema claro")
        pg.emulate_media(color_scheme="dark")
        pg.evaluate("() => window.modo(true, '#0d1a26', '#172636')")
        # o app confere o modo do Home Assistant a cada 2 s: espera ele trocar (no GitHub, com a máquina mais lenta, 900 ms não bastavam)
        fr.wait_for_function("() => document.documentElement.dataset.theme === 'dark' && window.__haTema.doHA === 'dark'", timeout=5000)
        self.assertEqual(fr.evaluate("() => window.__haTema.doHA"), "dark")
        self.assertEqual(fr.evaluate(cores), ["#fafafa", "#ffffff", "#0d1a26", "#172636"])
        self.assertEqual(fr.evaluate(fundo), "rgb(13, 26, 38)", "o fundo do tema escuro")
        self.assertEqual(fr.evaluate(cartao), "rgb(23, 38, 54)", "o cartão do tema escuro")
        # sozinho (fora do Home Assistant): as cores do tema padrão do Home Assistant
        for tema, f, c in (("light", "rgb(250, 250, 250)", "rgb(255, 255, 255)"), ("dark", "rgb(17, 17, 17)", "rgb(28, 28, 28)")):
            p2 = self.nav.new_page(viewport={"width": 390, "height": 844}, color_scheme=tema)
            self.addCleanup(p2.close)
            p2.goto(self.url)
            p2.wait_for_selector("#ch-txt")
            self.assertIsNone(p2.evaluate("() => window.__haTema.doHA"), tema)
            self.assertEqual((p2.evaluate(fundo), p2.evaluate(cartao)), (f, c), tema)

    def test_no_computador_a_barra_lateral(self):
        """1.8.0: no computador (1000 px ou mais), a barra lateral da família em todas as telas: o app, Conversa e Mais, as
        conversas (a aberta marcada, a Nova conversa no +) e a versão; a Conversa com o resto da tela, as outras no meio. No
        celular, como antes."""
        self.publicar_app()
        self.abrir()
        self.pg.set_viewport_size({"width": 1280, "height": 800})
        self.pg.wait_for_selector("#lado .side-nav")
        self.assertEqual(self.texto("#lado .side-brand"), "CorrerIA")
        self.assertEqual([t.strip() for t in self.pg.locator("#lado .side-link").all_inner_texts()], ["Conversa", "Mais"])
        self.assertEqual(self.texto('#lado .side-link[aria-current="page"]'), "Conversa")
        for bt in ("conversas", "ch-nova", "mais"):
            self.assertEqual(self.pg.locator(f'.cab-bts [data-a="{bt}"]').count(), 0, f"sem o {bt} no alto: está na lateral")
        self.pg.fill("#ch-txt", "quanto gastei?")
        self.pg.keyboard.press("Enter")
        self.pg.wait_for_selector("#lado .side-conv.on")
        self.assertEqual(self.texto("#lado .side-conv.on .sl-nome"), "quanto gastei?")
        lado, app, pe = (self.pg.locator(x).bounding_box() for x in ("#lado", "#app", ".ch-pe"))
        self.assertEqual((round(lado["x"]), round(lado["width"])), (0, 272), "a lateral na esquerda")
        self.assertEqual((round(app["x"]), round(app["x"] + app["width"])), (272, 1280), "a Conversa com o resto da tela")
        self.assertEqual((round(pe["x"]), round(pe["x"] + pe["width"])), (272, 1280), "a caixa de escrever também")
        self.assertIn("CorrerIA ", self.texto("#lado .side-foot"))
        self.pg.screenshot(path=os.path.join(os.environ.get("CORRERIA_PRINTS", "/tmp"), "correria-computador.png"))
        # Mais, Configurações e Sobre: no meio do resto da tela, com a lateral (o Mais marcado)
        self.pg.click('#lado [data-v="mais"]')
        self.pg.wait_for_selector(".mais-menu")
        self.assertEqual(self.texto('#lado .side-link[aria-current="page"]'), "Mais")
        self.pg.click('.mais-menu [data-a="sobre"]')
        self.pg.wait_for_selector(".sobre-topo")
        app = self.pg.locator("#app").bounding_box()
        self.assertEqual((round(app["width"]), round(app["x"] - 272), round(1280 - app["x"] - app["width"])), (960, 24, 24), "no meio, com 960")
        self.pg.screenshot(path=os.path.join(os.environ.get("CORRERIA_PRINTS", "/tmp"), "correria-computador-sobre.png"))
        # a Nova conversa da lateral volta para a Conversa
        self.pg.click('#lado [data-a="ch-nova"]')
        self.pg.wait_for_selector("#ch-txt")
        self.assertEqual(self.texto('#lado .side-link[aria-current="page"]'), "Conversa")
        self.pg.set_viewport_size({"width": 390, "height": 844})
        self.pg.wait_for_selector('.cab-bts [data-a="conversas"]')
        self.assertEqual(self.pg.locator("#lado").count(), 0, "no celular, sem a lateral")
        self.assertFalse(self.pg.evaluate("document.body.classList.contains('lado')"))

    def test_atalho_no_celular(self):
        # Opções › Atalho no celular (0.13.0; antes em Aparência): o caminho do app no Home Assistant e o Copiar; fora do
        # Home Assistant, nem a aba
        self.abrir()
        self.opcoes()
        # 1.7.0: a aba Opções sempre (as Conversas valem em qualquer lugar); fora do Home Assistant, sem o Atalho
        self.pg.click('.abas [data-v="opcoes"]')
        self.pg.wait_for_selector("#conversas-velhas")
        self.assertEqual(self.pg.locator("#atalho").count(), 0, "fora do Home Assistant, sem o Atalho")
        with mock.patch.dict(os.environ, {"CORRERIA_HOST": "a1b2c3d4-correria"}):
            self.pg.evaluate("window.CORRERIA_TESTE.carregar()")
            self.pg.wait_for_selector('.abas [data-v="opcoes"]')
            self.assertEqual(self.pg.eval_on_selector_all(".abas button", "bs => bs.map(b => b.textContent.trim())"), ["Integrações", "WhatsApp", "MCP", "Dados", "Aparência", "Opções"], "Opções por último")
            self.pg.click('.abas [data-v="aparencia"]')
            self.assertEqual(self.pg.locator("#atalho").count(), 0, "fora da Aparência")
            self.pg.click('.abas [data-v="opcoes"]')
            self.pg.wait_for_selector("#atalho")
            # 0.13.1: no celular estreito as abas rolam para o lado: a escolhida (a última) fica à vista
            self.pg.set_viewport_size({"width": 360, "height": 800})
            self.pg.evaluate("window.CORRERIA_TESTE.carregar()")
            self.pg.wait_for_selector('.abas [data-v="opcoes"].on')
            self.assertTrue(self.pg.eval_on_selector('.abas [data-v="opcoes"]', "(b) => { const n = b.parentElement.getBoundingClientRect(), r = b.getBoundingClientRect(); return r.left >= n.left - 1 && r.right <= n.right + 1; }"), "Opções à vista")
            self.assertEqual(self.pg.input_value("#f-atalho"), "/app/a1b2c3d4_correria")
            self.assertIn("Gerenciar atalhos", self.texto("#atalho .passos"))
            self.pg.click('#atalho [data-a="copiar"]')
            self.aviso("Toque e segure no texto para copiar")  # em http, sem área de transferência: o texto fica selecionado
            self.assertEqual(self.pg.evaluate("document.activeElement.id"), "f-atalho")
            self.assertFalse(self.pg.evaluate("document.documentElement.scrollWidth > innerWidth"), "nada sai da tela")
            for w in (390, 320):  # o caminho inteiro à vista, sem cortar
                self.pg.set_viewport_size({"width": w, "height": 844})
                self.assertTrue(self.pg.eval_on_selector("#f-atalho", "(e) => e.scrollWidth <= e.clientWidth"), f"{w} px: o caminho cortado")
            self.pg.locator("#atalho").screenshot(path=os.path.join(os.environ.get("CORRERIA_PRINTS", "/tmp"), "correria-atalho.png"))

    def test_uso_da_ia(self):
        self.abrir()
        self.opcoes("apps")
        self.assertEqual(self.pg.eval_on_selector("#uso .uso-ult li", "e => e.textContent"), "Nenhuma chamada ainda.")
        self.assertEqual(self.texto("#uso .lead"), "As chamadas do app para a IA. Os tokens são estimados.", "1.14.1: o texto dos outros apps")
        self.assertEqual(self.texto("#uso .uso-cap"), "Hoje: 0 chamadas.")
        S.USO.registrar("whatsapp", 4000, 400, 3.2)
        S.USO.registrar("conversa", 800, 0, 1.0, "HTTP 429 Too Many Requests")
        self.pg.evaluate("window.CORRERIA_TESTE.carregar()")
        self.pg.wait_for_selector("#uso .uso-tipos")
        tiles = [" ".join(t.split()) for t in self.pg.locator("#uso .uso-t").all_inner_texts()]
        self.assertEqual(tiles[0], "HOJE 2 1 vez sem cota")
        # 0.15.0: no padrão dos outros apps: uma barra por dia que mostra o dia, os tipos em etiquetas e as Últimas chamadas recolhidas
        self.assertEqual(self.pg.locator("#uso .uso-bar").count(), 7)
        self.assertEqual(self.texto("#uso .uso-cap"), "Hoje: 2 chamadas, 1 sem cota.")
        self.pg.click("#uso .uso-bar >> nth=0")
        self.assertRegex(self.texto("#uso .uso-cap"), r"^[A-Z][a-zá]{2}, \d\d/\d\d: 0 chamadas\.$")
        self.assertEqual(self.pg.locator('#uso .uso-bar[aria-pressed="true"]').count(), 1)
        self.assertEqual(self.pg.locator("#uso .uso-tipos li").all_inner_texts(), ["WhatsApp 1", "Conversa 1"])
        self.assertFalse(self.pg.eval_on_selector("#uso .uso-ult", "d => d.open"), "Últimas chamadas começa recolhida")
        self.assertEqual(self.texto("#uso .uso-ult summary"), "Últimas chamadas (2)", "0.17.1: com quantas são (Nome (n))")
        self.pg.click("#uso .uso-ult summary")
        ult = self.pg.locator("#uso .uso-ult li").all_inner_texts()
        self.assertTrue(ult[0].startswith("Conversa") and "sem cota" in ult[0] and ult[1].startswith("WhatsApp"), ult)
        self.assertIn("HTTP 429 Too Many Requests", ult[0], "o motivo embaixo")
        self.assertRegex(ult[1], r"3,2 s · ≈ 1,1 mil tokens · hoje \d\d:\d\d$")
        self.pg.evaluate("window.CORRERIA_TESTE.carregar()")
        self.pg.wait_for_timeout(200)
        self.assertTrue(self.pg.eval_on_selector("#uso .uso-ult", "d => d.open"), "aberta, continua aberta quando a tela se redesenha")
        self.assertFalse(self.pg.evaluate("document.documentElement.scrollWidth > innerWidth"), "nada sai da tela")

    def test_uso_da_ia_o_consumo_de_cada_ia_em_uso(self):
        """1.14.0: no fim do Uso da IA, uma linha para cada IA em uso (a de conversar e a de pesquisar), com o site do
        consumo e do saldo, como nos outros apps; sem saber qual é o provedor, só onde fica."""
        ias = [{"id": "ai_task.google_ai_task", "nome": "Google AI Task"}, {"id": "ai_task.claude_ai_task", "nome": "Claude AI Task"}, {"id": "ai_task.casa", "nome": "IA da casa"}]
        with mock.patch.object(S, "ias_ha", return_value=ias):
            S.salvar_config({"ia_entidade": "ai_task.google_ai_task", "ia_pesquisa": "ai_task.claude_ai_task"})
            self.abrir()
            self.opcoes("apps")
            notas = self.pg.locator("#uso .uso-nota")
            self.assertEqual(notas.all_inner_texts(), ["Gemini: consumo e cota no Google AI Studio, em Dashboard › Usage; o saldo dos créditos, em Billing.",
                                                      "Claude: consumo e custo no Claude Console; o saldo dos créditos, em Billing."])
            links = self.pg.eval_on_selector_all("#uso .uso-nota a", "els => els.map(a => [a.textContent, a.href, a.target, a.rel])")
            self.assertEqual(links, [["Google AI Studio", "https://aistudio.google.com/", "_blank", "noopener noreferrer"],
                                     ["Claude Console", "https://platform.claude.com/usage", "_blank", "noopener noreferrer"],
                                     ["Billing", "https://platform.claude.com/settings/billing", "_blank", "noopener noreferrer"]])
            self.assertFalse(self.pg.evaluate("document.documentElement.scrollWidth > innerWidth"), "nada sai da tela")
            S.salvar_config({"ia_entidade": "ai_task.casa", "ia_pesquisa": ""})
            self.pg.evaluate("window.CORRERIA_TESTE.carregar()")
            self.pg.wait_for_function("document.querySelectorAll('#uso .uso-nota').length === 1")
            self.assertEqual(self.texto("#uso .uso-nota"), "O consumo exato fica no painel do provedor da IA.")
        # na padrão do Home Assistant, com as IAs de lá de um provedor só: o dele
        with mock.patch.object(S, "ias_ha", return_value=ias[:1]):
            S.salvar_config({"ia_entidade": ""})
            self.pg.evaluate("window.CORRERIA_TESTE.carregar()")
            self.pg.wait_for_function("document.querySelector('#uso .uso-nota a')")
            self.assertEqual(self.pg.locator("#uso .uso-nota").all_inner_texts(), ["Gemini: consumo e cota no Google AI Studio, em Dashboard › Usage; o saldo dos créditos, em Billing."])

    def test_os_sites_abrem_num_toque(self):
        """1.14.0: onde a tela fala de um site (o painel da Meta, a Cloudflare), o nome abre o site."""
        S.salvar_config({"whatsapp": True, "mcp": True, "endereco": "casa-exemplo.duckdns.org:8443"})
        self.abrir()
        self.opcoes("whatsapp")
        meta = "https://developers.facebook.com/apps/"
        self.assertEqual(self.texto("#whatsapp .lead"), "A conta do WhatsApp Business, criada no painel da Meta.")
        duck, nuvem = ["Duck DNS", "https://www.duckdns.org/", "_blank"], ["Cloudflare", "https://dash.cloudflare.com/", "_blank"]
        self.assertEqual(self.pg.eval_on_selector_all("#whatsapp .lead a, #webhook .passos a", "els => els.map(a => [a.textContent, a.href, a.target])"),
                         [["painel da Meta", meta, "_blank"], ["Meta", meta, "_blank"]])
        # 1.14.2: o texto de cima do Webhook também (a Meta e o Duck DNS), e os avisos de sem certificado
        self.assertEqual(self.texto("#webhook .lead"), "O endereço pelo qual a Meta entrega as mensagens, como o do Duck DNS. No roteador, a porta 8443 vai para o Home Assistant.")
        self.assertEqual(self.pg.eval_on_selector_all("#webhook .lead a", "els => els.map(a => [a.textContent, a.href, a.target])"), [["Meta", meta, "_blank"], duck])
        self.assertEqual(self.pg.eval_on_selector_all("#webhook .status a", "els => els.map(a => [a.textContent, a.href, a.target])"), [duck, ["Meta", meta, "_blank"]], "sem certificado: o Duck DNS e a Meta")
        self.pg.click('.abas [data-v="mcp"]')
        self.assertEqual(self.pg.eval_on_selector_all("#mcp .lead a", "els => els.map(a => [a.textContent, a.href, a.target])"), [duck, nuvem])
        self.assertEqual(self.pg.eval_on_selector_all("#mcp .status a", "els => els.map(a => [a.textContent, a.href, a.target])")[:2], [duck, nuvem], "sem certificado: o Duck DNS e a Cloudflare")
        self.assertEqual(self.pg.evaluate("[...document.querySelectorAll('a[target=_blank]')].filter(a => !/noopener/.test(a.rel)).length"), 0)
        S.salvar_config({"whatsapp": False})
        self.pg.evaluate("window.CORRERIA_TESTE.carregar()")
        self.pg.click('.abas [data-v="whatsapp"]')
        self.pg.wait_for_function("!document.querySelector('#webhook')")
        self.assertEqual(self.pg.eval_on_selector("#whatsapp .lead a", "a => a.href"), meta, "desligado também")

    def test_sensores(self):
        """0.14.0: Sensores no Home Assistant, depois do Uso da IA, desligado até ligar."""
        self.abrir()
        self.opcoes("apps")
        ids = self.pg.evaluate("[...document.querySelectorAll('.card')].map(c => c.id)")
        self.assertEqual(ids[ids.index("uso") + 1], "sensores", ids)
        self.assertIn("Desligado: nenhum sensor no Home Assistant.", self.texto("#sensores"))
        self.pg.click('#sensores [data-a="sensores"]')
        self.pg.wait_for_selector('#sensores .sw.on')
        self.assertTrue(S.ler_config()["sensores"])
        # 0.17.1: como no ResolvIA, Criar sensores e, num quadro embaixo da chave, cada sensor numa linha
        codigos = self.pg.evaluate("[...document.querySelectorAll('#sensores > .sub-op > .sub-box.sensor-list .sensor-row code')].map(c => c.textContent)")
        self.assertEqual(codigos, ["sensor.correria_certificado", "binary_sensor.correria_whatsapp"])
        self.assertIn("Criar sensores", self.texto("#sensores"))
        self.assertFalse(self.pg.evaluate("document.documentElement.scrollWidth > innerWidth"), "nada sai da tela")
        self.pg.click('#sensores [data-a="sensores"]')
        self.pg.wait_for_selector('#sensores .sw:not(.on)')
        self.assertFalse(S.ler_config()["sensores"])


    def test_abas_numa_linha_e_guardadas(self):
        self.abrir()
        self.opcoes("whatsapp")
        self.assertEqual(self.pg.locator("#whatsapp").count(), 1)
        self.assertEqual(self.pg.locator("#mcp").count(), 0, "uma aba de cada vez")
        tops = self.pg.evaluate("[...document.querySelectorAll('.abas button')].map(b => Math.round(b.getBoundingClientRect().top))")
        self.assertEqual(len(set(tops)), 1, "as cinco abas numa linha")
        self.assertFalse(self.pg.evaluate("document.documentElement.scrollWidth > innerWidth"))
        self.pg.set_viewport_size({"width": 320, "height": 700})
        # 1.7.0: com a aba Opções sempre, as seis não cabem em 320 px: rolam, com a seta na ponta de onde há mais
        self.pg.wait_for_function("document.querySelector('.abas-wrap').classList.contains('tem-dir') || document.querySelector('.abas-wrap').classList.contains('tem-esq')")
        self.assertFalse(self.pg.evaluate("document.documentElement.scrollWidth > innerWidth"), "a página não passa da largura")
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

    def test_cabecalho_fica_no_alto_ao_rolar(self):
        """1.13.1: na Conversa, o cabeçalho (CorrerIA › Conversa e os botões) fica no alto quando as mensagens rolam,
        no celular e no computador com a barra lateral; na Tela cheia ele já fica preso dentro do painel."""
        self.abrir()
        self.pg.evaluate("document.querySelector('#ch-lista').insertAdjacentHTML('beforeend', '<p style=\"height:3000px\">mensagem</p>')")
        for largura in (390, 1280):
            self.pg.set_viewport_size({"width": largura, "height": 760})
            self.pg.evaluate("window.scrollTo(0, 900)")
            self.pg.wait_for_timeout(100)
            topo = self.pg.evaluate("() => { const r = document.querySelector('.cab').getBoundingClientRect(); return [r.top, r.bottom]; }")
            self.assertLess(abs(topo[0]), 1, f"{largura} px: o cabeçalho cola no alto da tela")
            self.assertGreater(topo[1], 40, f"{largura} px: o cabeçalho continua aparecendo")
            self.assertTrue(self.pg.is_visible('.cab [data-a="mais"], .cab h1'), f"{largura} px: os botões e o título continuam visíveis")
            self.pg.evaluate("window.scrollTo(0, 0)")


if __name__ == "__main__":
    unittest.main()
