"""O login do Claude e do Gemini no CorrerIA: OAuth 2.1 com PKCE (S256) e registro dinâmico de cliente (RFC 7591), o
que o Claude e o Gemini pedem para um conector MCP. Sem senha: ao conectar, a página do CorrerIA mostra um código e
alguém da casa aprova o pedido no painel do Home Assistant (onde já está logado). A conexão fica com a pessoa que aprovou.

Em /data/mcp.json ficam os clientes registrados e as conexões (os tokens só como hash, SHA-256). Os pedidos e os
códigos de autorização ficam na memória (valem poucos minutos)."""
import base64
import hashlib
import json
import os
import re
import secrets
import threading
import time
import urllib.parse
from datetime import datetime

ESCOPO = "casa"
MAX_CLIENTES = 50
MAX_PEDIDOS = 5          # esperando aprovação ao mesmo tempo
PEDIDO_VALE = 10 * 60    # para aprovar
CODIGO_VALE = 5 * 60     # o código de autorização, para trocar pelo token
ACESSO_VALE = 60 * 60    # o token de acesso
RENOVAR_VALE = 90 * 86400
MAX_CONEXOES = 30


class ErroOAuth(Exception):
    """erro e descrição do OAuth; ir: para onde mandar o navegador com o erro (None: mostra a página de erro)."""

    def __init__(self, erro, descricao, status=400, ir=None):
        super().__init__(descricao)
        self.erro, self.descricao, self.status, self.ir = erro, descricao, status, ir

    def json(self):
        return {"error": self.erro, "error_description": self.descricao}


def _hash(t):
    return hashlib.sha256(str(t).encode()).hexdigest()


def _iso(ts):
    return datetime.fromtimestamp(ts).isoformat(timespec="seconds") if ts else None


def _uri_ok(u):
    """https, ou http só no próprio computador (localhost), sem fragmento."""
    try:
        p = urllib.parse.urlparse(u)
    except ValueError:
        return False
    if p.fragment or not p.hostname or len(u) > 500:
        return False
    return p.scheme == "https" or (p.scheme == "http" and p.hostname in ("localhost", "127.0.0.1", "::1"))


def _com_params(uri, **params):
    p = urllib.parse.urlparse(uri)
    q = urllib.parse.parse_qsl(p.query, keep_blank_values=True) + [(k, v) for k, v in params.items() if v is not None]
    return urllib.parse.urlunparse(p._replace(query=urllib.parse.urlencode(q)))


def _mesmo_redirect(registrados, uri):
    """Igual a um registrado; no localhost, a porta pode mudar a cada vez (RFC 8252)."""
    if uri in registrados:
        return True
    p = urllib.parse.urlparse(uri)
    if p.scheme != "http" or p.hostname not in ("localhost", "127.0.0.1", "::1"):
        return False
    for r in registrados:
        q = urllib.parse.urlparse(r)
        if q.scheme == "http" and q.hostname == p.hostname and q.path == p.path:
            return True
    return False


class Autorizacao:
    def __init__(self, arquivo, gravar, log, ao_pedir=None, relogio=time.time):
        self.arquivo, self.gravar, self.log = arquivo, gravar, log
        self.ao_pedir = ao_pedir   # ao_pedir(pedido): um pedido novo esperando (o aviso no Home Assistant)
        self.agora = relogio
        self.trava = threading.Lock()
        self.pedidos = {}
        self.codigos = {}
        self._usado_gravado = {}

    # ---------------------------------------------------------------- arquivo
    def _ler(self):
        try:
            with open(self.arquivo, encoding="utf-8") as f:
                d = json.load(f)
        except (OSError, ValueError):
            d = {}
        return {"clientes": d.get("clientes") if isinstance(d.get("clientes"), dict) else {},
                "conexoes": d.get("conexoes") if isinstance(d.get("conexoes"), dict) else {}}

    def _salvar(self, d):
        self.gravar(self.arquivo, json.dumps(d, ensure_ascii=False, indent=1))

    # ---------------------------------------------------------------- metadados (RFC 9728 e RFC 8414)
    @staticmethod
    def recurso(base):
        return {"resource": base + "/mcp", "authorization_servers": [base], "scopes_supported": [ESCOPO],
                "bearer_methods_supported": ["header"], "resource_name": "CorrerIA"}

    @staticmethod
    def servidor(base):
        return {"issuer": base, "authorization_endpoint": base + "/autorizar", "token_endpoint": base + "/token",
                "registration_endpoint": base + "/registrar", "scopes_supported": [ESCOPO], "response_types_supported": ["code"],
                "response_modes_supported": ["query"], "grant_types_supported": ["authorization_code", "refresh_token"],
                "code_challenge_methods_supported": ["S256"],
                "token_endpoint_auth_methods_supported": ["none", "client_secret_post", "client_secret_basic"]}

    # ---------------------------------------------------------------- registro do cliente (RFC 7591)
    def registrar(self, corpo):
        if not isinstance(corpo, dict):
            raise ErroOAuth("invalid_client_metadata", "Pedido inválido.")
        uris = corpo.get("redirect_uris")
        if not isinstance(uris, list) or not 1 <= len(uris) <= 5 or not all(isinstance(u, str) and _uri_ok(u) for u in uris):
            raise ErroOAuth("invalid_redirect_uri", "redirect_uris: de 1 a 5 endereços https (ou http no localhost).")
        metodo = corpo.get("token_endpoint_auth_method") or "none"
        if metodo not in ("none", "client_secret_post", "client_secret_basic"):
            raise ErroOAuth("invalid_client_metadata", "token_endpoint_auth_method não aceito.")
        tipos = corpo.get("grant_types") or ["authorization_code", "refresh_token"]
        if not isinstance(tipos, list) or "authorization_code" not in tipos:
            raise ErroOAuth("invalid_client_metadata", "grant_types precisa de authorization_code.")
        nome = re.sub(r"[\x00-\x1f<>]", "", str(corpo.get("client_name") or "")).strip()[:40] or urllib.parse.urlparse(uris[0]).hostname
        agora = int(self.agora())
        cid = "c-" + secrets.token_urlsafe(16)
        cli = {"nome": nome, "redirect_uris": uris, "metodo": metodo, "criado": agora}
        resp = {"client_id": cid, "client_id_issued_at": agora, "client_name": nome, "redirect_uris": uris,
                "grant_types": ["authorization_code", "refresh_token"], "response_types": ["code"], "token_endpoint_auth_method": metodo}
        if metodo != "none":
            segredo = secrets.token_urlsafe(32)
            cli["segredo"] = _hash(segredo)
            resp.update(client_secret=segredo, client_secret_expires_at=0)
        with self.trava:
            d = self._ler()
            if len(d["clientes"]) >= MAX_CLIENTES:  # tira os mais velhos que não têm conexão
                usados = {c.get("cliente") for c in d["conexoes"].values()}
                for velho in sorted((k for k in d["clientes"] if k not in usados), key=lambda k: d["clientes"][k].get("criado", 0)):
                    if len(d["clientes"]) < MAX_CLIENTES:
                        break
                    d["clientes"].pop(velho)
                if len(d["clientes"]) >= MAX_CLIENTES:
                    raise ErroOAuth("temporarily_unavailable", "Clientes demais registrados.", 503)
            d["clientes"][cid] = cli
            self._salvar(d)
        return resp

    # ---------------------------------------------------------------- autorizar (a página espera a aprovação no painel)
    def _limpar(self):
        t = self.agora()
        for pid in [k for k, p in self.pedidos.items() if t - p["criado"] > PEDIDO_VALE + 120]:
            self.pedidos.pop(pid)
        for h in [k for k, c in self.codigos.items() if c["expira"] < t]:
            self.codigos.pop(h)

    def pedir(self, q, base):
        """GET /autorizar: confere o pedido e deixa esperando a aprovação. Devolve o pedido (para a página)."""
        g = lambda k: str((q.get(k) or [""])[0]) if isinstance(q.get(k), list) else str(q.get(k) or "")  # noqa: E731
        cid = g("client_id")
        with self.trava:
            cli = self._ler()["clientes"].get(cid)
        if not cli:
            raise ErroOAuth("invalid_client", "Esse cliente não está registrado. Tente conectar de novo.")
        uri = g("redirect_uri") or (cli["redirect_uris"][0] if len(cli["redirect_uris"]) == 1 else "")
        if not uri or not _mesmo_redirect(cli["redirect_uris"], uri):
            raise ErroOAuth("invalid_request", "Endereço de retorno diferente do registrado.")
        estado = g("state")
        voltar = lambda e, d: ErroOAuth(e, d, ir=_com_params(uri, error=e, error_description=d, state=estado or None))  # noqa: E731
        if g("response_type") != "code":
            raise voltar("unsupported_response_type", "Só response_type=code.")
        desafio, metodo = g("code_challenge"), g("code_challenge_method")
        if not re.fullmatch(r"[A-Za-z0-9_-]{43,128}", desafio) or metodo != "S256":
            raise voltar("invalid_request", "PKCE com S256 é obrigatório.")
        recurso = g("resource")
        if recurso and urllib.parse.urlparse(recurso).path.rstrip("/") not in ("", "/mcp"):
            raise voltar("invalid_target", "Recurso desconhecido.")
        with self.trava:
            self._limpar()
            if sum(1 for p in self.pedidos.values() if p["estado"] == "esperando") >= MAX_PEDIDOS:
                raise voltar("temporarily_unavailable", "Muitos pedidos esperando aprovação. Tente daqui a pouco.")
            p = {"id": secrets.token_urlsafe(18), "cliente": cid, "nome": cli["nome"], "host": urllib.parse.urlparse(uri).hostname,
                 "redirect_uri": uri, "state": estado, "desafio": desafio, "codigo": str(1000 + secrets.randbelow(9000)),
                 "criado": self.agora(), "estado": "esperando", "ir": None}
            self.pedidos[p["id"]] = p
        self.log("Claude e Gemini:", p["nome"], "pediu para conectar (código", p["codigo"] + ")")
        if self.ao_pedir:
            try:
                self.ao_pedir(p)
            except Exception as e:  # noqa: BLE001  (o aviso é só uma ajuda)
                self.log("Não consegui avisar no Home Assistant:", e)
        return p

    def abertos(self):
        """Os pedidos esperando aprovação (para a tela)."""
        with self.trava:
            self._limpar()
            t = self.agora()
            return [{"id": p["id"], "nome": p["nome"], "host": p["host"], "codigo": p["codigo"], "em": _iso(p["criado"])}
                    for p in sorted(self.pedidos.values(), key=lambda x: x["criado"]) if p["estado"] == "esperando" and t - p["criado"] <= PEDIDO_VALE]

    def decidir(self, pid, aprovar, pessoa):
        """Aprovar (ou recusar) no painel. A página do pedido vê na próxima consulta e volta para o Claude ou o Gemini."""
        with self.trava:
            p = self.pedidos.get(str(pid or ""))
            if not p or p["estado"] != "esperando" or self.agora() - p["criado"] > PEDIDO_VALE:
                raise LookupError("Esse pedido não está mais esperando. Conecte de novo pelo Claude ou pelo Gemini.")
            if aprovar:
                code = secrets.token_urlsafe(32)
                self.codigos[_hash(code)] = {"cliente": p["cliente"], "nome": p["nome"], "redirect_uri": p["redirect_uri"], "desafio": p["desafio"],
                                             "pessoa": pessoa or {}, "expira": self.agora() + CODIGO_VALE}
                p.update(estado="aprovado", ir=_com_params(p["redirect_uri"], code=code, state=p["state"] or None))
            else:
                p.update(estado="recusado", ir=_com_params(p["redirect_uri"], error="access_denied", error_description="Recusado no CorrerIA.",
                                                          state=p["state"] or None))
        self.log("Claude e Gemini:", p["nome"], "aprovado" if aprovar else "recusado", f"por {(pessoa or {}).get('nome') or 'alguém'}")
        return p

    def situacao(self, pid):
        """O que a página do pedido mostra: esperando, ou para onde ir (aprovado ou recusado), ou que venceu."""
        with self.trava:
            p = self.pedidos.get(str(pid or ""))
            if not p:
                return {"estado": "vencido"}
            if p["estado"] == "esperando" and self.agora() - p["criado"] > PEDIDO_VALE:
                return {"estado": "vencido"}
            return {"estado": p["estado"], **({"ir": p["ir"]} if p["ir"] else {})}

    # ---------------------------------------------------------------- token
    def trocar(self, form, autorizacao=""):
        g = lambda k: str(form.get(k) or "")  # noqa: E731
        cid, segredo = g("client_id"), g("client_secret")
        if autorizacao.startswith("Basic "):
            try:
                u, _, s = base64.b64decode(autorizacao[6:]).decode().partition(":")
                cid, segredo = urllib.parse.unquote(u) or cid, urllib.parse.unquote(s) or segredo
            except (ValueError, UnicodeDecodeError):
                raise ErroOAuth("invalid_client", "Autenticação inválida.", 401) from None
        tipo = g("grant_type")
        with self.trava:
            d = self._ler()
            cli = d["clientes"].get(cid) if cid else None
            if cid and not cli:
                raise ErroOAuth("invalid_client", "Cliente desconhecido.", 401)
            if cli and segredo and (not cli.get("segredo") or not secrets.compare_digest(cli["segredo"], _hash(segredo))):
                raise ErroOAuth("invalid_client", "Segredo do cliente inválido.", 401)
            if tipo == "authorization_code":
                c = self.codigos.pop(_hash(g("code")), None)
                if not c or c["expira"] < self.agora():
                    raise ErroOAuth("invalid_grant", "Código inválido ou vencido.")
                if (cid and cid != c["cliente"]) or g("redirect_uri") not in ("", c["redirect_uri"]):
                    raise ErroOAuth("invalid_grant", "O código não é deste cliente.")
                verif = g("code_verifier")
                calc = base64.urlsafe_b64encode(hashlib.sha256(verif.encode()).digest()).rstrip(b"=").decode()
                if not re.fullmatch(r"[A-Za-z0-9._~-]{43,128}", verif) or not secrets.compare_digest(calc, c["desafio"]):
                    raise ErroOAuth("invalid_grant", "code_verifier não confere.")
                agora = self.agora()
                con = {"cliente": c["cliente"], "nome": c["nome"], "pessoa": c["pessoa"], "criado": int(agora), "usado": int(agora)}
                conid = "x-" + secrets.token_hex(6)
                d["conexoes"][conid] = con
                if len(d["conexoes"]) > MAX_CONEXOES:
                    for velho in sorted(d["conexoes"], key=lambda k: d["conexoes"][k].get("usado", 0))[:len(d["conexoes"]) - MAX_CONEXOES]:
                        d["conexoes"].pop(velho)
                self.log("Claude e Gemini:", c["nome"], "conectado", f"({(c['pessoa'] or {}).get('nome') or 'sem pessoa'})")
            elif tipo == "refresh_token":
                h = _hash(g("refresh_token"))
                conid = next((k for k, x in d["conexoes"].items() if x.get("renovar") and secrets.compare_digest(x["renovar"], h)), None)
                con = d["conexoes"].get(conid) if conid else None
                if not con or con.get("renovar_expira", 0) < self.agora() or (cid and cid != con["cliente"]):
                    raise ErroOAuth("invalid_grant", "Conexão desfeita ou vencida. Conecte de novo.")
            else:
                raise ErroOAuth("unsupported_grant_type", "Só authorization_code e refresh_token.")
            acesso, renovar = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
            agora = self.agora()
            con.update(acesso=_hash(acesso), acesso_expira=int(agora + ACESSO_VALE), renovar=_hash(renovar), renovar_expira=int(agora + RENOVAR_VALE))
            self._salvar(d)
        return {"access_token": acesso, "token_type": "Bearer", "expires_in": ACESSO_VALE, "refresh_token": renovar, "scope": ESCOPO}

    # ---------------------------------------------------------------- conexões
    def conexao(self, token):
        """A conexão do token de acesso (vale até expirar), ou None."""
        if not token:
            return None
        h = _hash(token)
        with self.trava:
            d = self._ler()
            for cid, c in d["conexoes"].items():
                if c.get("acesso") and secrets.compare_digest(c["acesso"], h):
                    if c.get("acesso_expira", 0) < self.agora():
                        return None
                    agora = int(self.agora())
                    c["usado"] = agora
                    if agora - self._usado_gravado.get(cid, 0) >= 60:  # grava o "usou há pouco" no máximo a cada minuto
                        self._usado_gravado[cid] = agora
                        self._salvar(d)
                    return dict(c, id=cid)
        return None

    def conexoes(self):
        with self.trava:
            d = self._ler()
        lista = [{"id": k, "nome": c.get("nome", ""), "pessoa": (c.get("pessoa") or {}).get("nome", ""), "criado": _iso(c.get("criado")),
                  "usado": _iso(c.get("usado"))} for k, c in d["conexoes"].items() if c.get("renovar_expira", 0) >= self.agora()]
        return sorted(lista, key=lambda c: c["usado"] or "", reverse=True)

    def desconectar(self, conid):
        with self.trava:
            d = self._ler()
            c = d["conexoes"].pop(str(conid or ""), None)
            if not c:
                raise LookupError("Essa conexão não existe mais.")
            self._salvar(d)
        self.log("Claude e Gemini:", c.get("nome"), "desconectado")
        return c

    def esquecer_tudo(self):
        """Desliga: as conexões e os pedidos saem (para voltar, conecta de novo)."""
        with self.trava:
            d = self._ler()
            d["conexoes"] = {}
            self._salvar(d)
            self.pedidos.clear()
            self.codigos.clear()


def pagina(titulo, corpo, script=""):
    """A página do pedido (pública, na porta do webhook): simples, no claro ou no escuro do aparelho."""
    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="referrer" content="no-referrer"><meta name="robots" content="noindex"><title>{titulo} · CorrerIA</title><style>
:root{{--bg:#0f1318;--card:#151a21;--tx:#e9ebef;--mut:#9aa1ad;--cor:#FFB547;--bd:#242b35}}
@media (prefers-color-scheme:light){{:root{{--bg:#f2f4f7;--card:#fff;--tx:#14171c;--mut:#5d6470;--bd:#e3e7ec;--cor:#80591f}}}}
*{{box-sizing:border-box}}body{{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;background:var(--bg);color:var(--tx);
font:16px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;padding:16px}}
main{{width:100%;max-width:420px;background:var(--card);border:1px solid var(--bd);border-radius:18px;padding:28px 22px;text-align:center}}
.marca{{font-weight:800;letter-spacing:-.02em;font-size:20px;margin:0 0 18px;color:var(--tx)}}.marca span{{color:var(--cor)}}
h1{{font-size:21px;margin:0 0 10px}}p{{color:var(--mut);margin:0 0 14px}}b{{color:var(--tx)}}
.codigo{{font:800 44px/1 ui-monospace,Menlo,monospace;letter-spacing:.18em;color:var(--cor);margin:18px 0 20px}}
.espera{{display:inline-flex;gap:6px;margin-top:6px}}.espera i{{width:8px;height:8px;border-radius:50%;background:var(--mut);animation:p 1.2s infinite}}
.espera i:nth-child(2){{animation-delay:.2s}}.espera i:nth-child(3){{animation-delay:.4s}}@keyframes p{{0%,80%,100%{{opacity:.25}}40%{{opacity:1}}}}
</style></head><body><main><p class="marca">Correr<span>IA</span></p>{corpo}</main>{script}</body></html>"""
