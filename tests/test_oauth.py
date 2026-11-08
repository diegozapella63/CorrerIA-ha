"""oauth.py: o login do Claude e do Gemini (OAuth 2.1 com PKCE e registro dinâmico), com a aprovação no painel, o
token, a renovação, desconectar e os erros. Com um relógio de mentira para os prazos."""
import base64
import hashlib
import json
import os
import secrets
import unittest
import urllib.parse

from tests.base import pasta_temp
import oauth as O

BASE = "https://casa-exemplo.duckdns.org:8443"
VOLTA = "https://claude.ai/api/mcp/auth_callback"
ANA = {"id": "person.ana", "nome": "Ana"}


def gravar(caminho, texto):
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(texto)


def pkce():
    v = secrets.token_urlsafe(48)
    return v, base64.urlsafe_b64encode(hashlib.sha256(v.encode()).digest()).rstrip(b"=").decode()


class Relogio:
    def __init__(self):
        self.t = 1_800_000_000.0

    def __call__(self):
        return self.t


class TestOAuth(unittest.TestCase):
    def setUp(self):
        self.arq = os.path.join(pasta_temp(), "mcp.json")
        self.avisos = []
        self.rel = Relogio()
        self.a = O.Autorizacao(self.arq, gravar, lambda *x: None, ao_pedir=self.avisos.append, relogio=self.rel)

    def cliente(self, **extra):
        return self.a.registrar({"client_name": "Claude", "redirect_uris": [VOLTA], "token_endpoint_auth_method": "none", **extra})

    def pedir(self, cid, desafio, **extra):
        q = {"response_type": "code", "client_id": cid, "redirect_uri": VOLTA, "code_challenge": desafio, "code_challenge_method": "S256",
             "state": "xyz", "scope": "casa", "resource": BASE + "/mcp", **extra}
        return self.a.pedir({k: [v] for k, v in q.items()}, BASE)

    def conectar(self):
        c = self.cliente()
        v, d = pkce()
        p = self.pedir(c["client_id"], d)
        self.a.decidir(p["id"], True, ANA)
        code = urllib.parse.parse_qs(urllib.parse.urlparse(self.a.situacao(p["id"])["ir"]).query)["code"][0]
        return c, self.a.trocar({"grant_type": "authorization_code", "code": code, "redirect_uri": VOLTA, "client_id": c["client_id"], "code_verifier": v})

    def test_metadados(self):
        self.assertEqual(O.Autorizacao.recurso(BASE)["resource"], BASE + "/mcp")
        self.assertEqual(O.Autorizacao.recurso(BASE)["authorization_servers"], [BASE])
        s = O.Autorizacao.servidor(BASE)
        self.assertEqual((s["issuer"], s["authorization_endpoint"], s["token_endpoint"], s["registration_endpoint"]),
                         (BASE, BASE + "/autorizar", BASE + "/token", BASE + "/registrar"))
        self.assertEqual(s["code_challenge_methods_supported"], ["S256"])
        self.assertIn("none", s["token_endpoint_auth_methods_supported"])

    def test_caminho_todo(self):
        c = self.cliente()
        self.assertTrue(c["client_id"].startswith("c-"))
        self.assertNotIn("client_secret", c, "cliente público")
        v, d = pkce()
        p = self.pedir(c["client_id"], d)
        self.assertRegex(p["codigo"], r"^\d{4}$")
        self.assertEqual(self.avisos, [p], "avisa no Home Assistant")
        self.assertEqual([(x["nome"], x["host"], x["codigo"]) for x in self.a.abertos()], [("Claude", "claude.ai", p["codigo"])])
        self.assertEqual(self.a.situacao(p["id"]), {"estado": "esperando"})
        self.a.decidir(p["id"], True, ANA)
        self.assertEqual(self.a.abertos(), [])
        s = self.a.situacao(p["id"])
        u = urllib.parse.urlparse(s["ir"])
        q = urllib.parse.parse_qs(u.query)
        self.assertEqual((s["estado"], f"{u.scheme}://{u.netloc}{u.path}", q["state"]), ("aprovado", VOLTA, ["xyz"]))
        tok = self.a.trocar({"grant_type": "authorization_code", "code": q["code"][0], "redirect_uri": VOLTA, "client_id": c["client_id"], "code_verifier": v})
        self.assertEqual((tok["token_type"], tok["expires_in"], tok["scope"]), ("Bearer", 3600, "casa"))
        con = self.a.conexao(tok["access_token"])
        self.assertEqual((con["nome"], con["pessoa"]), ("Claude", ANA))
        self.assertEqual([(x["nome"], x["pessoa"]) for x in self.a.conexoes()], [("Claude", "Ana")])
        with open(self.arq) as f:
            self.assertNotIn(tok["access_token"], f.read(), "os tokens ficam só como hash")
        with self.assertRaisesRegex(O.ErroOAuth, "inválido ou vencido"):
            self.a.trocar({"grant_type": "authorization_code", "code": q["code"][0], "redirect_uri": VOLTA, "client_id": c["client_id"], "code_verifier": v})

    def test_renovar_e_desconectar(self):
        c, tok = self.conectar()
        novo = self.a.trocar({"grant_type": "refresh_token", "refresh_token": tok["refresh_token"], "client_id": c["client_id"]})
        self.assertIsNone(self.a.conexao(tok["access_token"]), "o de antes não vale mais")
        self.assertTrue(self.a.conexao(novo["access_token"]))
        with self.assertRaises(O.ErroOAuth) as e:
            self.a.trocar({"grant_type": "refresh_token", "refresh_token": tok["refresh_token"]})
        self.assertEqual(e.exception.erro, "invalid_grant", "o de renovar também gira")
        self.rel.t += 3601
        self.assertIsNone(self.a.conexao(novo["access_token"]), "o de acesso vence em 1 hora")
        mais = self.a.trocar({"grant_type": "refresh_token", "refresh_token": novo["refresh_token"]})
        self.assertTrue(self.a.conexao(mais["access_token"]))
        self.a.desconectar(self.a.conexoes()[0]["id"])
        self.assertIsNone(self.a.conexao(mais["access_token"]))
        self.assertEqual(self.a.conexoes(), [])
        with self.assertRaises(LookupError):
            self.a.desconectar("x")

    def test_recusar_e_vencer(self):
        c = self.cliente()
        _, d = pkce()
        p = self.pedir(c["client_id"], d)
        self.a.decidir(p["id"], False, ANA)
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.a.situacao(p["id"])["ir"]).query)
        self.assertEqual((q["error"], q["state"]), (["access_denied"], ["xyz"]))
        p = self.pedir(c["client_id"], d)
        self.rel.t += 601
        self.assertEqual(self.a.situacao(p["id"]), {"estado": "vencido"})
        self.assertEqual(self.a.abertos(), [])
        with self.assertRaises(LookupError):
            self.a.decidir(p["id"], True, ANA)

    def test_erros_do_pedido(self):
        c = self.cliente()
        _, d = pkce()
        with self.assertRaises(O.ErroOAuth) as e:
            self.pedir("c-nao-existe", d)
        self.assertIsNone(e.exception.ir, "cliente desconhecido: mostra o erro, sem voltar")
        with self.assertRaises(O.ErroOAuth) as e:
            self.pedir(c["client_id"], d, redirect_uri="https://outro.exemplo/volta")
        self.assertIsNone(e.exception.ir, "endereço de retorno diferente: não volta para ele")
        for extra, erro in (({"code_challenge_method": "plain"}, "invalid_request"), ({"code_challenge": ""}, "invalid_request"),
                            ({"response_type": "token"}, "unsupported_response_type"), ({"resource": BASE + "/outro"}, "invalid_target")):
            with self.assertRaises(O.ErroOAuth) as e:
                self.pedir(c["client_id"], d, **extra)
            self.assertEqual(e.exception.erro, erro)
            self.assertTrue(e.exception.ir.startswith(VOLTA + "?error=" + erro), "volta para o Claude com o erro")
        for _ in range(5):
            self.pedir(c["client_id"], d)
        with self.assertRaises(O.ErroOAuth) as e:
            self.pedir(c["client_id"], d)
        self.assertEqual(e.exception.erro, "temporarily_unavailable", "no máximo 5 esperando")

    def test_erros_do_token(self):
        c = self.cliente()
        v, d = pkce()
        p = self.pedir(c["client_id"], d)
        self.a.decidir(p["id"], True, ANA)
        code = urllib.parse.parse_qs(urllib.parse.urlparse(self.a.situacao(p["id"])["ir"]).query)["code"][0]
        base = {"grant_type": "authorization_code", "code": code, "redirect_uri": VOLTA, "client_id": c["client_id"], "code_verifier": v}
        with self.assertRaisesRegex(O.ErroOAuth, "code_verifier"):
            self.a.trocar(dict(base, code_verifier=pkce()[0]))
        p = self.pedir(c["client_id"], d)
        self.a.decidir(p["id"], True, ANA)
        code = urllib.parse.parse_qs(urllib.parse.urlparse(self.a.situacao(p["id"])["ir"]).query)["code"][0]
        outro = self.cliente()
        with self.assertRaisesRegex(O.ErroOAuth, "não é deste cliente"):
            self.a.trocar(dict(base, code=code, client_id=outro["client_id"]))
        with self.assertRaises(O.ErroOAuth) as e:
            self.a.trocar({"grant_type": "password"})
        self.assertEqual(e.exception.erro, "unsupported_grant_type")
        with self.assertRaises(O.ErroOAuth) as e:
            self.a.trocar({"grant_type": "authorization_code", "client_id": "c-x"})
        self.assertEqual((e.exception.erro, e.exception.status), ("invalid_client", 401))
        p = self.pedir(c["client_id"], d)
        self.a.decidir(p["id"], True, ANA)
        code = urllib.parse.parse_qs(urllib.parse.urlparse(self.a.situacao(p["id"])["ir"]).query)["code"][0]
        self.rel.t += 301
        with self.assertRaisesRegex(O.ErroOAuth, "vencido"):
            self.a.trocar(dict(base, code=code))

    def test_cliente_com_segredo_e_localhost(self):
        c = self.a.registrar({"client_name": "Gemini", "redirect_uris": ["http://localhost:7777/callback"], "token_endpoint_auth_method": "client_secret_basic"})
        self.assertTrue(c["client_secret"])
        v, d = pkce()
        p = self.a.pedir({"response_type": ["code"], "client_id": [c["client_id"]], "redirect_uri": ["http://localhost:51234/callback"],
                          "code_challenge": [d], "code_challenge_method": ["S256"]}, BASE)
        self.assertEqual(p["host"], "localhost", "no localhost, a porta pode mudar")
        self.a.decidir(p["id"], True, ANA)
        code = urllib.parse.parse_qs(urllib.parse.urlparse(self.a.situacao(p["id"])["ir"]).query)["code"][0]
        basic = "Basic " + base64.b64encode(f"{c['client_id']}:errado".encode()).decode()
        with self.assertRaises(O.ErroOAuth) as e:
            self.a.trocar({"grant_type": "authorization_code", "code": code, "code_verifier": v}, basic)
        self.assertEqual(e.exception.status, 401)
        basic = "Basic " + base64.b64encode(f"{c['client_id']}:{c['client_secret']}".encode()).decode()
        p = self.a.pedir({"response_type": ["code"], "client_id": [c["client_id"]], "code_challenge": [d], "code_challenge_method": ["S256"]}, BASE)
        self.a.decidir(p["id"], True, ANA)
        code = urllib.parse.parse_qs(urllib.parse.urlparse(self.a.situacao(p["id"])["ir"]).query)["code"][0]
        tok = self.a.trocar({"grant_type": "authorization_code", "code": code, "code_verifier": v}, basic)
        self.assertEqual(self.a.conexao(tok["access_token"])["nome"], "Gemini")

    def test_registro_valida_e_tem_limite(self):
        for corpo in ({}, {"redirect_uris": []}, {"redirect_uris": ["http://claude.ai/volta"]}, {"redirect_uris": ["https://x/#y"]},
                      {"redirect_uris": [VOLTA], "token_endpoint_auth_method": "private_key_jwt"}, {"redirect_uris": [VOLTA], "grant_types": ["implicit"]}):
            with self.assertRaises(O.ErroOAuth):
                self.a.registrar(corpo)
        self.assertEqual(self.a.registrar({"redirect_uris": [VOLTA], "client_name": "<b>X</b>"})["client_name"], "bX/b")
        self.assertEqual(self.a.registrar({"redirect_uris": [VOLTA]})["client_name"], "claude.ai", "sem nome: o endereço de volta")
        self.conectar()
        for _ in range(60):
            self.cliente()
        with open(self.arq) as f:
            d = json.load(f)
        self.assertEqual(len(d["clientes"]), 50)
        self.assertEqual(len(self.a.conexoes()), 1, "o cliente com conexão fica")

    def test_esquecer_tudo(self):
        _, tok = self.conectar()
        self.a.esquecer_tudo()
        self.assertIsNone(self.a.conexao(tok["access_token"]))

    def test_pagina(self):
        h = O.pagina("Conectar", "<h1>Oi</h1>")
        self.assertIn("<title>Conectar · CorrerIA</title>", h)
        self.assertIn('lang="pt-BR"', h)


if __name__ == "__main__":
    unittest.main()
