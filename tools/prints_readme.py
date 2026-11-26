"""Refaz as capturas do README (docs/*.png) com o servidor de verdade (correria/app/server.py), os apps da família de
mentira (as ferramentas respondem textos inventados) e uma casa inventada (Ana, Beto, a Sala e a Cozinha).
Uso: python3 tools/prints_readme.py (precisa do playwright). Nada sai para a internet."""
import base64
import hashlib
import json
import os
import secrets
import sys
import threading
from datetime import datetime, timedelta
from http.server import ThreadingHTTPServer
from unittest import mock

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
from playwright.sync_api import sync_playwright  # noqa: E402

from tests.base import importar_servidor, MetaFalsa  # noqa: E402
S = importar_servidor()
import apps  # noqa: E402
from tests.test_rondas import AppDaRonda, ferr, COM_COMODO  # noqa: E402

SAIDA = os.path.join(RAIZ, "docs")
CAB = {"X-Remote-User-Id": "u-ana", "X-Remote-User-Display-Name": "Ana Exemplo"}
agora = datetime.now().replace(second=0, microsecond=0)
iso = lambda m: (agora - timedelta(minutes=m)).isoformat(timespec="seconds")  # noqa: E731

# os apps da família, com o assunto e as ferramentas de leitura que as capturas usam
APPS = {
    "cronologia": ("CronologIA", "agenda da família: compromissos, rotinas, remédios e placar",
                   [ferr("resumo"), ferr("agenda"), ferr("cadastros", COM_COMODO), ferr("criar_compromisso", grava=True)],
                   {"cadastros": "TOTAL: 1\n- Regar as plantas (toda semana)", "agenda": "TOTAL: 0", "resumo": "TOTAL: 0"}),
    "gerencia": ("GerencIA", "finanças da casa: caixa, contas a pagar, cartões e investimentos",
                 [ferr("resumo"), ferr("lancamentos"), ferr("lancar", grava=True)], {"resumo": "Saldo de hoje: R$ 2.340,00."}),
    "resolvia": ("ResolvIA", "listas de tarefas com prazos, pontos e repetição",
                 [ferr("tarefas", COM_COMODO), ferr("criar_tarefa", grava=True)],
                 {"tarefas": "TOTAL: 2\n- Trocar a lâmpada do abajur (vence hoje)\n- Limpar o ar-condicionado"}),
    "inventario": ("InventarIA", "inventário da casa: cômodos, itens e valores",
                   [ferr("resumo"), ferr("buscar_itens", COM_COMODO), ferr("cadastrar_itens", grava=True)],
                   {"resumo": {"comodos": [{"nome": "Sala"}, {"nome": "Cozinha"}, {"nome": "Quarto"}], "opcoes": {"consumiveis": False}},
                    "buscar_itens": "TOTAL: 3\n- Sofá de 3 lugares\n- Televisão 55\"\n- Abajur"}),
    "economia": ("EconomIA", "lista de compras com o melhor preço perto de casa",
                 [ferr("lista"), ferr("por_na_lista", grava=True)], {"lista": "TOTAL: 2\n- Café\n- Detergente"}),
    "memoria": ("MemorIA", "cadernos de anotação que abrem na hora certa", [ferr("resumo"), ferr("buscar")], {"resumo": "3 blocos."}),
    "odisseia": ("OdisseIA", "filmes, séries e jogos: o que ver, jogar e onde", [ferr("resumo"), ferr("buscar")], {"resumo": "4 títulos."}),
}

CONVERSA = [
    {"papel": "eu", "texto": "Quanto gastei com mercado este mês?", "em": iso(9)},
    {"papel": "ia", "texto": "Neste mês foram *R$ 612,30* em Mercado, em 7 compras. A maior foi de R$ 184,90 no dia 03.", "app": "GerencIA", "em": iso(9)},
    {"papel": "eu", "texto": "lança 45,90 de padaria no cartão do Banco Azul", "em": iso(8)},
    {"papel": "ia", "texto": "Vou fazer isto:\n- Lançar R$ 45,90 de Padaria hoje, no cartão do Banco Azul\n\nToque em *Sim* para confirmar.", "app": "GerencIA", "em": iso(8)},
    {"papel": "eu", "texto": "sim", "em": iso(7)},
    {"papel": "ia", "texto": "Feito!\n- Lançado: Padaria · R$ 45,90 · hoje · Mercado · Banco Azul · Ana (cartão de crédito, fatura de 10/12).", "app": "GerencIA", "em": iso(7)},
    {"papel": "eu", "texto": "o que tem na agenda amanhã?", "em": iso(2)},
    {"papel": "ia", "texto": "Amanhã:\n- *Dentista* às 15:00 (Ana)\n- Remédio do Beto às 20:00", "app": "CronologIA", "em": iso(2)},
]


def preparar():
    falsos = []
    for app, (nome, assunto, lista, respostas) in APPS.items():
        a = AppDaRonda(nome, lista, respostas)
        falsos.append(a)
        os.makedirs(os.path.join(S.SHARE_DIR, app), exist_ok=True)
        with open(os.path.join(S.SHARE_DIR, app, "correria.json"), "w", encoding="utf-8") as f:
            json.dump({"app": app, "nome": nome, "assunto": assunto, "url": a.url, "chave": a.chave, "versao": "2.0.0",
                       "ferramentas": "/api/integracao/ferramentas"}, f)
    S.salvar_config({"mcp": True, "whatsapp": True, "endereco": "https://casa-exemplo.duckdns.org:8443",
                     "endereco_mcp": "https://casa-exemplo.duckdns.org", "numero_id": MetaFalsa.NUMERO_ID, "token": "EAA-exemplo-" + "0" * 20,
                     "segredo": "segredo-de-exemplo-1234", "pessoas": {"person.ana": "5511987650001", "person.beto": "5521912340002"}})
    S.ESTADO.update(conta={"numero": "+55 11 4000-0000", "nome": "CorrerIA Code"}, conta_em=iso(30), ultimo_webhook=iso(5))
    with open(S.CONVERSAS_ARQ, "w", encoding="utf-8") as f:
        json.dump({"tela": {"u-ana": {"atual": "c1", "lista": [{"id": "c1", "titulo": "Quanto gastei com mercado este mês?", "criada": iso(9),
                                                                "atualizada": iso(2), "mensagens": CONVERSA}]}}}, f)
    return falsos


def pedido_mcp():
    cli = S.AUT.registrar({"client_name": "Gemini", "redirect_uris": ["https://gemini.google.com/mcp/callback"], "token_endpoint_auth_method": "none"})
    v = secrets.token_urlsafe(48)
    d = base64.urlsafe_b64encode(hashlib.sha256(v.encode()).digest()).rstrip(b"=").decode()
    S.AUT.pedir({"response_type": ["code"], "client_id": [cli["client_id"]], "code_challenge": [d], "code_challenge_method": ["S256"]}, "https://x")


def main():
    meta = MetaFalsa()
    falsos = preparar()
    with mock.patch.object(S, "GRAPH", meta.url), mock.patch.object(S, "APPS", apps.Apps(S.SHARE_DIR, S.log, cache=0)), \
            mock.patch.object(S, "pessoas_ha", return_value=[{"id": "person.ana", "nome": "Ana", "usuario": "u-ana"}, {"id": "person.beto", "nome": "Beto", "usuario": "u-beto"}]):
        srv = ThreadingHTTPServer(("127.0.0.1", 0), S.Tela)
        srv.daemon_threads = True
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        url = f"http://127.0.0.1:{srv.server_address[1]}/"
        with sync_playwright() as pw:
            nav = pw.chromium.launch()

            def pagina(aba=None):
                pg = nav.new_page(viewport={"width": 390, "height": 844}, color_scheme="dark", device_scale_factor=2, extra_http_headers=CAB)
                pg.goto(url)
                pg.wait_for_selector(".ch-msg.ia")
                pg.wait_for_timeout(500)
                if aba:
                    pg.click('[data-a="mais"]')
                    pg.click('[data-a="opcoes"]')
                    pg.wait_for_selector(".abas")
                    pg.click(f'.abas [data-v="{aba}"]')
                    pg.wait_for_timeout(500)
                return pg

            pg = pagina()
            pg.screenshot(path=f"{SAIDA}/conversa.png")
            # a Ronda da casa na Sala: o que o app tem e a pergunta (a IA simulada lê o app)
            pg.click('[data-a="rondas"]')
            pg.wait_for_selector(".ch-ronda-onde .btn")
            pg.click(".ch-ronda-onde .btn >> text=Sala")
            pg.wait_for_selector(".ch-ronda-t b >> text=Sala")
            pg.wait_for_timeout(600)
            pg.screenshot(path=f"{SAIDA}/rondas.png")
            pg.close()
            pg = pagina("apps")
            pg.screenshot(path=f"{SAIDA}/apps.png")
            pg.close()
            pg = pagina("whatsapp")
            pg.screenshot(path=f"{SAIDA}/whatsapp.png")
            pg.close()
            pedido_mcp()
            pg = pagina("mcp")
            pg.wait_for_selector(".pedido")
            pg.screenshot(path=f"{SAIDA}/claude-gemini.png")
            pg.close()
            nav.close()
        srv.shutdown()
    for a in falsos + [meta]:
        a.fechar()
    print("ok")


if __name__ == "__main__":
    main()
