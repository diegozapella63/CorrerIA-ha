"""Ajuda dos testes do CorrerIA: o caminho do app, pastas temporárias, um servidor HTTP de mentira (a Meta e os apps
da família) e o servidor do CorrerIA com tudo em pastas temporárias. Pessoas e números inventados (Ana, Beto)."""
import importlib
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(RAIZ, "correria", "app")
if APP not in sys.path:
    sys.path.insert(0, APP)

ANA = "5511987650001"     # com o 9 do celular
ANA_WA = "551187650001"   # como o WhatsApp manda (sem o 9)
BETO = "5521912340002"


def pasta_temp():
    return tempfile.mkdtemp(prefix="correria-teste-")


def porta_livre():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class ServidorFalso:
    """Um servidor HTTP numa porta livre; rotas = {caminho: (status, corpo)} ou {caminho: função(handler, corpo) -> (status,
    corpo)}. Guarda os pedidos em .pedidos (método, caminho com a busca, cabeçalhos, corpo em JSON quando der)."""

    def __init__(self, rotas=None):
        self.rotas = rotas if rotas is not None else {}
        self.pedidos = []
        dono = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _responder(self):
                n = int(self.headers.get("Content-Length") or 0)
                corpo = self.rfile.read(n) if n else b""
                try:
                    j = json.loads(corpo) if corpo else None
                except ValueError:
                    j = corpo
                dono.pedidos.append((self.command, self.path, dict(self.headers), j))
                r = dono.rotas.get(self.path.split("?")[0])
                if callable(r):
                    r = r(self, j)
                status, resp = r if r else (404, {"error": {"message": "não achei"}})
                dados = resp if isinstance(resp, (bytes, str)) else json.dumps(resp)
                dados = dados.encode() if isinstance(dados, str) else dados
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(dados)))
                self.end_headers()
                self.wfile.write(dados)

            do_GET = do_POST = do_PUT = do_DELETE = _responder

        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.srv.daemon_threads = True
        self.url = f"http://127.0.0.1:{self.srv.server_address[1]}"
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def fechar(self):
        self.srv.shutdown()
        self.srv.server_close()


class MetaFalsa(ServidorFalso):
    """A Graph API da Meta: guarda o que o CorrerIA mandou (mensagens e "lida")."""
    NUMERO_ID = "109876543210"

    def __init__(self):
        super().__init__()
        self.rotas[f"/{self.NUMERO_ID}/messages"] = lambda h, c: (200, {"messaging_product": "whatsapp", "messages": [{"id": "wamid.resp"}]})
        self.rotas[f"/{self.NUMERO_ID}"] = (200, {"display_phone_number": "+55 11 4000-0000", "verified_name": "CorrerIA Code", "id": self.NUMERO_ID})

    def textos(self):
        return [(c["to"], c["text"]["body"]) for m, p, h, c in self.pedidos if isinstance(c, dict) and c.get("type") == "text"]

    def lidas(self):
        return [c for m, p, h, c in self.pedidos if isinstance(c, dict) and c.get("status") == "read"]


def certificado(pasta):
    """Um certificado próprio (como o do Duck DNS, mas sem valer na internet) em pasta/fullchain.pem e privkey.pem."""
    subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "2", "-subj", "/CN=localhost",
                    "-keyout", os.path.join(pasta, "privkey.pem"), "-out", os.path.join(pasta, "fullchain.pem")],
                   check=True, capture_output=True)


def importar_servidor(**env):
    """O server.py com as pastas temporárias (uma vez por processo; os testes mudam as variáveis do módulo)."""
    if "server" in sys.modules:
        return sys.modules["server"]
    base = pasta_temp()
    for k, sub in (("CORRERIA_DATA", "data"), ("CORRERIA_SHARE", "share"), ("CORRERIA_SSL", "ssl")):
        os.environ[k] = os.path.join(base, sub)
        os.makedirs(os.environ[k], exist_ok=True)
    os.environ.setdefault("CORRERIA_DEV", "1")
    os.environ.setdefault("CORRERIA_LOG_HTTP", "0")
    os.environ.pop("SUPERVISOR_TOKEN", None)
    os.environ.update(env)
    return importlib.import_module("server")


FERRAMENTAS_FALSAS = [
    {"nome": "resumo", "titulo": "Resumo", "descricao": "O que tem hoje.", "entrada": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
     "grava": False, "apaga": False},
    {"nome": "lancar", "titulo": "Lançar gasto", "descricao": "Lança um gasto.",
     "entrada": {"type": "object", "properties": {"descricao": {"type": "string"}, "valor": {"type": "number"}}, "required": ["descricao", "valor"],
                 "additionalProperties": False}, "grava": True, "apaga": False},
    {"nome": "apagar", "titulo": "Apagar", "descricao": "Apaga um gasto.", "entrada": {"type": "object", "properties": {"id": {"type": "string"}}},
     "grava": True, "apaga": True},
]


class AppFalso(ServidorFalso):
    """Um app da família com o contrato das ferramentas (GET lista, POST chama). .feitos guarda os POST."""

    def __init__(self, nome="GerencIA", ferramentas=None, chave="chave-de-teste-" + "x" * 20):
        super().__init__()
        self.nome, self.chave, self.feitos = nome, chave, []
        lista = FERRAMENTAS_FALSAS if ferramentas is None else ferramentas

        def rota(h, c):
            if h.headers.get("Authorization") != f"Bearer {self.chave}":
                return 401, {"erro": "Chave inválida."}
            if h.command == "GET":
                return 200, {"instrucoes": f"{nome}: dicas.", "ferramentas": lista}
            self.feitos.append(c)
            if c["nome"] == "resumo":
                return 200, {"texto": f"Hoje no {nome}: 3 contas, R$ 120,00."}
            if c["nome"] == "lancar":
                if not c["argumentos"].get("valor"):
                    return 400, {"erro": "Falta o valor."}
                return 200, {"texto": f"Lançado: {c['argumentos'].get('descricao')} · R$ {c['argumentos']['valor']}. id: l1\nmais uma linha"}
            if c["nome"] == "apagar":
                return 200, {"texto": "Apagado."}
            return 404, {"erro": f"Ferramenta desconhecida: {c['nome']}."}
        self.rotas["/api/integracao/ferramentas"] = rota

    def publicar(self, share, app="gerencia", rota=None):
        os.makedirs(os.path.join(share, app), exist_ok=True)
        with open(os.path.join(share, app, "correria.json"), "w", encoding="utf-8") as f:
            json.dump({"app": app, "nome": self.nome, "assunto": "um assunto", "url": self.url, "chave": self.chave, "versao": "9.9.9",
                       "ferramentas": "/api/integracao/ferramentas", **({"rota": rota} if rota else {})}, f)
