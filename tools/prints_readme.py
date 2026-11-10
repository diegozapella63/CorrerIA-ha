"""Refaz as capturas do README (docs/*.png): a tela de verdade (correria/app/www) com /api/* imitado e uma casa inventada
(Ana, Beto). Uso: python3 tools/prints_readme.py (precisa do playwright)."""
import json, mimetypes, os, sys
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WWW, SAIDA = os.path.join(RAIZ, "correria", "app", "www"), os.path.join(RAIZ, "docs")
agora = datetime.now().replace(second=0, microsecond=0)
iso = lambda m: (agora - timedelta(minutes=m)).isoformat(timespec="seconds")
APPS = [
    {"app": "cronologia", "nome": "CronologIA", "assunto": "agenda da família: compromissos, rotinas, remédios e placar", "versao": "1.60.0", "anexos": [], "conversa": False, "ferramentas": 10, "gravam": 6, "erro": ""},
    {"app": "gerencia", "nome": "GerencIA", "assunto": "finanças da casa: caixa, contas a pagar, cartões e investimentos", "versao": "1.39.0", "anexos": ["application/pdf", "image/jpeg", "image/png", "image/webp"], "conversa": True, "ferramentas": 12, "gravam": 7, "erro": ""},
    {"app": "inventario", "nome": "InventarIA", "assunto": "inventário da casa: cômodos, itens e valores", "versao": "1.37.0", "anexos": [], "conversa": False, "ferramentas": 8, "gravam": 5, "erro": ""},
    {"app": "memoria", "nome": "MemorIA", "assunto": "anotações em blocos: folhas, categorias e links", "versao": "1.8.0", "anexos": [], "conversa": False, "ferramentas": 12, "gravam": 8, "erro": ""},
    {"app": "resolvia", "nome": "ResolvIA", "assunto": "listas de tarefas com prazos, pontos e repetição", "versao": "2.49.0", "anexos": [], "conversa": False, "ferramentas": 8, "gravam": 4, "erro": ""},
]
def estado(pedido=False):
    return {"versao": "0.4.0",
            "config": {"numero_id": "109876543210", "token": "••••1234", "segredo": "••••5678", "verificacao": "k3v9-exemplo-verificacao",
                       "endereco": "https://casa-exemplo.duckdns.org:8443", "webhook": "https://casa-exemplo.duckdns.org:8443/webhook", "ligado": True},
            "pronto": True, "conta": {"numero": "+55 11 4000-0000", "nome": "CorrerIA Code"},
            "mcp": {"ligado": True, "url": "https://casa-exemplo.duckdns.org:8443/mcp",
                    "pedidos": [{"id": "p1", "nome": "Gemini", "host": "gemini.google.com", "codigo": "4821", "em": iso(1)}] if pedido else [],
                    "conexoes": [{"id": "x1", "nome": "Claude", "pessoa": "Ana", "criado": iso(3000), "usado": iso(12)}]},
            "ia": {"ok": True, "erro": "", "em": iso(5)},
            "webhook": {"https": True, "certificado": "fullchain.pem", "porta": 8443, "verificado_em": iso(4000), "ultimo": iso(5)},
            "pessoas": [{"id": "person.ana", "nome": "Ana", "numero": "5511987650001"}, {"id": "person.beto", "nome": "Beto", "numero": "5521912340002"}],
            "apps": APPS, "fala": {"pronta": True, "nome": "Home Assistant Cloud"},
            "aparencia": {"cor": "ouro", "cor_dia": False},
            "registro": [
                {"em": iso(5), "tipo": "enviada", "quem": "Beto", "texto": "Feito!\n- Tirar o lixo: concluída por Beto (+5 pontos).", "app": "ResolvIA"},
                {"em": iso(5), "tipo": "recebida", "quem": "Beto", "texto": "sim", "app": ""},
                {"em": iso(6), "tipo": "recebida", "quem": "Beto", "texto": "marca o lixo como feito", "app": ""},
                {"em": iso(12), "tipo": "mcp", "quem": "Claude · Ana", "texto": "Lançado: Padaria · R$ 18,40 · hoje · Mercado · pago.", "app": "GerencIA"},
                {"em": iso(40), "tipo": "enviada", "quem": "Ana", "texto": "Amanhã: *dentista às 15:00* e o remédio do Beto às 20:00.", "app": "CronologIA"},
                {"em": iso(41), "tipo": "recebida", "quem": "Ana", "texto": "O que tem amanhã?", "app": ""},
            ]}
CONVERSA = {"pessoa": "Ana", "mensagens": [
    {"papel": "eu", "texto": "Quanto gastei com mercado este mês?", "em": iso(9)},
    {"papel": "ia", "texto": "Neste mês foram *R$ 612,30* em Mercado, em 7 compras. A maior foi de R$ 184,90 no dia 03.", "app": "GerencIA", "em": iso(9)},
    {"papel": "eu", "texto": "lança 45,90 de padaria no cartão do Banco Azul", "em": iso(8)},
    {"papel": "ia", "texto": "Vou fazer isto:\n- Lançar R$ 45,90 de Padaria hoje, no cartão do Banco Azul\n\nResponda *sim* para confirmar.", "app": "GerencIA", "em": iso(8)},
    {"papel": "eu", "texto": "sim", "em": iso(7)},
    {"papel": "ia", "texto": "Feito!\n- Lançado: Padaria · R$ 45,90 · hoje · Mercado · Banco Azul · Ana (cartão de crédito, fatura de 10/12) · a pagar.", "app": "GerencIA", "em": iso(7)},
]}

def servir(rota, pedido):
    u = rota.request.url.split("correria.local", 1)[1].split("?")[0]
    if u.startswith("/api/estado"):
        return rota.fulfill(status=200, content_type="application/json", body=json.dumps(estado(pedido)))
    if u.startswith("/api/conversa"):
        return rota.fulfill(status=200, content_type="application/json", body=json.dumps(CONVERSA))
    arq = os.path.join(WWW, "index.html" if u in ("/", "") else u.lstrip("/"))
    if not os.path.isfile(arq):
        return rota.fulfill(status=404, body="")
    with open(arq, "rb") as f:
        rota.fulfill(status=200, content_type=mimetypes.guess_type(arq)[0] or "application/octet-stream", body=f.read())

with sync_playwright() as pw:
    nav = pw.chromium.launch()
    def pagina(tema, pedido=False, altura=844, aba=None):
        pg = nav.new_page(viewport={"width": 390, "height": altura}, color_scheme=tema, device_scale_factor=2)
        if aba:
            pg.add_init_script(f"try {{ localStorage.setItem('correria-aba', '{aba}') }} catch (e) {{}}")
        pg.route("http://correria.local/**", lambda r: servir(r, pedido))
        pg.goto("http://correria.local/"); pg.wait_for_selector(".ch-msg.ia"); pg.wait_for_timeout(400)
        if aba:
            pg.click('.cab-bts [data-a="mais"]'); pg.click('.mais-menu [data-a="opcoes"]')
            pg.wait_for_selector(".abas"); pg.wait_for_timeout(300)
        return pg
    pg = pagina("dark"); pg.screenshot(path=f"{SAIDA}/conversa.png"); pg.close()
    pg = pagina("dark", aba="apps"); pg.screenshot(path=f"{SAIDA}/apps.png"); pg.close()
    pg = pagina("dark", aba="whatsapp"); pg.screenshot(path=f"{SAIDA}/whatsapp.png"); pg.close()
    pg = pagina("dark", pedido=True, aba="mcp"); pg.screenshot(path=f"{SAIDA}/claude-gemini.png"); pg.close()
    nav.close()
print("ok")
