"""O servidor MCP (Model Context Protocol) do CorrerIA: o Claude e o Gemini chamam POST /mcp (Streamable HTTP, só com
respostas JSON, sem sessão) com JSON-RPC 2.0. Aqui só o protocolo: initialize, ping, tools/list e tools/call, com as
ferramentas de todos os apps (ferramentas.Ferramentas). O login (OAuth) fica no oauth.py e o HTTP no server.py."""
import json

VERSOES = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")


class Erro(Exception):
    def __init__(self, codigo, msg):
        super().__init__(msg)
        self.codigo = codigo


def _erro(mid, codigo, msg):
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": codigo, "message": msg}}


def ferramenta_mcp(f):
    """Uma ferramenta de app no formato do MCP, com o app no nome, no título e na descrição."""
    nome_app = f["app"]["nome"]
    return {"name": f["id"], "title": f"{f['titulo']} ({nome_app})", "description": f"{nome_app}: {f['descricao']}",
            "inputSchema": f["entrada"],
            "annotations": {"title": f"{f['titulo']} ({nome_app})", "readOnlyHint": not f["grava"], "destructiveHint": bool(f["apaga"]),
                            "idempotentHint": not f["grava"], "openWorldHint": False}}


class Servidor:
    """tratar(mensagem, quem) → a resposta (ou None para notificações). quem: {pessoa, cliente} da conexão."""

    def __init__(self, ferramentas, versao, instrucoes_base, ao_gravar=None):
        self.ferr, self.versao, self.base = ferramentas, versao, instrucoes_base
        self.ao_gravar = ao_gravar  # ao_gravar(quem, ferramenta, argumentos, texto, erro): o registro da tela

    def instrucoes(self):
        apps = self.ferr.instrucoes()
        return self.base + ("\n\nOs apps:\n" + apps if apps else "\n\nNenhum app ligado ainda: em cada app, ligue a opção CorrerIA.")

    def tratar(self, msg, quem):
        if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0" or not isinstance(msg.get("method"), str):
            if isinstance(msg, dict) and ("result" in msg or "error" in msg):
                return None  # resposta do cliente a algo que não pedimos: ignora
            return _erro(msg.get("id") if isinstance(msg, dict) else None, -32600, "Pedido inválido.")
        mid, metodo, params = msg.get("id"), msg["method"], msg.get("params") if isinstance(msg.get("params"), dict) else {}
        notificacao = "id" not in msg
        try:
            r = self._metodo(metodo, params, quem)
        except Erro as e:
            return None if notificacao else _erro(mid, e.codigo, str(e))
        if notificacao:
            return None
        return {"jsonrpc": "2.0", "id": mid, "result": r}

    def _metodo(self, metodo, params, quem):
        if metodo == "initialize":
            pedida = str(params.get("protocolVersion") or "")
            return {"protocolVersion": pedida if pedida in VERSOES else VERSOES[1],
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": "correria", "title": "CorrerIA", "version": self.versao},
                    "instructions": self.instrucoes()}
        if metodo == "ping":
            return {}
        if metodo.startswith("notifications/"):
            return {}
        if metodo == "tools/list":
            return {"tools": [ferramenta_mcp(f) for f in self.ferr.todas()]}
        if metodo == "tools/call":
            nome, args = params.get("name"), params.get("arguments")
            if args is not None and not isinstance(args, dict):
                raise Erro(-32602, "arguments deve ser um objeto.")
            f = self.ferr.achar(str(nome or ""))
            if not f:
                raise Erro(-32602, f"Ferramenta desconhecida: {nome}.")
            texto, erro = self.ferr.usar(f, args or {}, quem.get("pessoa"), quem.get("cliente") or "MCP")
            if f["grava"] and self.ao_gravar:
                self.ao_gravar(quem, f, args or {}, texto, erro)
            return {"content": [{"type": "text", "text": texto}], "isError": bool(erro)}
        if metodo in ("resources/list", "resources/templates/list"):
            return {"resources" if metodo == "resources/list" else "resourceTemplates": []}
        if metodo == "prompts/list":
            return {"prompts": []}
        raise Erro(-32601, f"Método desconhecido: {metodo}.")

    def http(self, corpo, quem):
        """O corpo de um POST /mcp → (status, corpo da resposta ou None). Aceita um pedido ou uma lista (2025-03-26)."""
        try:
            dados = json.loads(corpo or b"null")
        except ValueError:
            return 400, _erro(None, -32700, "JSON inválido.")
        if isinstance(dados, list):
            if not dados:
                return 400, _erro(None, -32600, "Lista vazia.")
            resp = [r for r in (self.tratar(m, quem) for m in dados[:50]) if r is not None]
            return (200, resp) if resp else (202, None)
        r = self.tratar(dados, quem)
        return (200, r) if r is not None else (202, None)
