"""mcp.py: o protocolo MCP (JSON-RPC 2.0 pelo POST /mcp): initialize, ping, tools/list e tools/call com as ferramentas
dos apps (de mentira: AppFalso), notificações, listas de pedidos e erros."""
import json
import unittest

from tests.base import AppFalso, pasta_temp
import apps as A
import ferramentas as F
import mcp as M

QUEM = {"pessoa": {"id": "person.ana", "nome": "Ana"}, "cliente": "Claude"}


def rpc(metodo, params=None, mid=1):
    m = {"jsonrpc": "2.0", "method": metodo, **({"params": params} if params is not None else {})}
    if mid is not None:
        m["id"] = mid
    return m


class TestMcp(unittest.TestCase):
    def setUp(self):
        self.share = pasta_temp()
        self.app = AppFalso("GerencIA")
        self.addCleanup(self.app.fechar)
        self.app.publicar(self.share, "gerencia")
        self.gravados = []
        self.s = M.Servidor(F.Ferramentas(A.Apps(self.share, print, cache=0), print), "0.4.0", "Base.",
                            ao_gravar=lambda *a: self.gravados.append(a))

    def test_initialize(self):
        r = self.s.tratar(rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "claude-ai"}}), QUEM)
        res = r["result"]
        self.assertEqual((r["id"], res["protocolVersion"], res["serverInfo"]["name"], res["serverInfo"]["version"]), (1, "2025-06-18", "correria", "0.4.0"))
        self.assertEqual(res["capabilities"], {"tools": {"listChanged": False}})
        self.assertIn("Base.", res["instructions"])
        self.assertIn("- GerencIA (um assunto): GerencIA: dicas.", res["instructions"])
        r = self.s.tratar(rpc("initialize", {"protocolVersion": "2099-01-01"}), QUEM)
        self.assertEqual(r["result"]["protocolVersion"], "2025-06-18", "versão desconhecida: a nossa")
        self.assertEqual(self.s.tratar(rpc("initialize", {"protocolVersion": "2025-03-26"}), QUEM)["result"]["protocolVersion"], "2025-03-26")

    def test_lista(self):
        tools = self.s.tratar(rpc("tools/list"), QUEM)["result"]["tools"]
        self.assertEqual([t["name"] for t in tools], ["gerencia_resumo", "gerencia_lancar", "gerencia_apagar"])
        t = tools[1]
        self.assertEqual((t["title"], t["description"]), ("Lançar gasto (GerencIA)", "GerencIA: Lança um gasto."))
        self.assertEqual(t["inputSchema"]["required"], ["descricao", "valor"])
        self.assertEqual({k: tools[0]["annotations"][k] for k in ("readOnlyHint", "destructiveHint")}, {"readOnlyHint": True, "destructiveHint": False})
        self.assertEqual({k: tools[2]["annotations"][k] for k in ("readOnlyHint", "destructiveHint")}, {"readOnlyHint": False, "destructiveHint": True})

    def test_chamar(self):
        r = self.s.tratar(rpc("tools/call", {"name": "gerencia_resumo", "arguments": {}}), QUEM)["result"]
        self.assertEqual(r, {"content": [{"type": "text", "text": "Hoje no GerencIA: 3 contas, R$ 120,00."}], "isError": False})
        self.assertEqual(self.gravados, [], "ler não vai para o registro")
        r = self.s.tratar(rpc("tools/call", {"name": "gerencia_lancar", "arguments": {"descricao": "Feira", "valor": 12}}), QUEM)["result"]
        self.assertFalse(r["isError"])
        self.assertEqual(self.app.feitos[-1]["pessoa"], {"id": "person.ana", "nome": "Ana"}, "quem aprovou a conexão")
        self.assertEqual(self.app.feitos[-1]["cliente"], "Claude")
        self.assertEqual(len(self.gravados), 1)
        r = self.s.tratar(rpc("tools/call", {"name": "gerencia_lancar", "arguments": {"descricao": "Feira"}}), QUEM)["result"]
        self.assertEqual(r, {"content": [{"type": "text", "text": "Falta o valor."}], "isError": True}, "a IA vê o erro e tenta de novo")
        r = self.s.tratar(rpc("tools/call", {"name": "gerencia_sacar"}), QUEM)
        self.assertEqual(r["error"]["code"], -32602)
        r = self.s.tratar(rpc("tools/call", {"name": "gerencia_resumo", "arguments": [1]}), QUEM)
        self.assertEqual(r["error"]["code"], -32602)

    def test_notificacoes_ping_e_desconhecidos(self):
        self.assertIsNone(self.s.tratar(rpc("notifications/initialized", mid=None), QUEM))
        self.assertEqual(self.s.tratar(rpc("ping", mid="a"), QUEM), {"jsonrpc": "2.0", "id": "a", "result": {}})
        self.assertEqual(self.s.tratar(rpc("sampling/x"), QUEM)["error"]["code"], -32601)
        self.assertEqual(self.s.tratar(rpc("prompts/list"), QUEM)["result"], {"prompts": []})
        self.assertEqual(self.s.tratar({"id": 3, "method": "ping"}, QUEM)["error"]["code"], -32600)
        self.assertIsNone(self.s.tratar({"jsonrpc": "2.0", "id": 9, "result": {}}, QUEM), "resposta do cliente: ignora")

    def test_http(self):
        self.assertEqual(self.s.http(b"{x", QUEM)[0], 400)
        self.assertEqual(self.s.http(json.dumps(rpc("notifications/initialized", mid=None)).encode(), QUEM), (202, None))
        st, r = self.s.http(json.dumps([rpc("ping", mid=1), rpc("notifications/initialized", mid=None), rpc("tools/list", mid=2)]).encode(), QUEM)
        self.assertEqual((st, [x["id"] for x in r]), (200, [1, 2]))
        self.assertEqual(self.s.http(b"[]", QUEM)[0], 400)


if __name__ == "__main__":
    unittest.main()
