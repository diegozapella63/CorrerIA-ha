"""WhatsApp Business (a API oficial da Meta, Cloud API): conferir a assinatura do webhook, tirar as mensagens do que a
Meta manda, responder, marcar como lida e conferir o número. Só biblioteca padrão.

Documentação: https://developers.facebook.com/docs/whatsapp/cloud-api
"""
import hashlib
import hmac
import json
import re
import urllib.error
import urllib.request

GRAPH = "https://graph.facebook.com/v26.0"
LIMITE = 4000  # o WhatsApp aceita até 4096 caracteres por mensagem


class ErroWhatsApp(Exception):
    def __init__(self, msg, codigo=None):
        super().__init__(msg)
        self.codigo = codigo


# códigos de erro da Meta que pedem uma explicação em português (o resto vai como a Meta mandou)
ERROS = {
    190: "O token do WhatsApp venceu ou está errado. Gere um token que não vence (Usuário do sistema) e cole de novo.",
    100: "A Meta não reconheceu o pedido. Confira o ID do número de telefone.",
    131030: "Este número ainda não está na lista de destinatários do número de teste da Meta.",
    131047: "Passaram mais de 24 horas da última mensagem da pessoa: o WhatsApp só deixa responder dentro desse prazo.",
    131026: "A mensagem não chegou: o número não tem WhatsApp ou não aceitou.",
    131056: "Muitas mensagens para o mesmo número em pouco tempo. Espere um pouco.",
    368: "A Meta bloqueou o envio temporariamente por violar as regras. Confira o painel da Meta.",
    80007: "Limite de envios da Meta atingido. Espere um pouco.",
}


def assinatura_ok(segredo, corpo, cabecalho):
    """X-Hub-Signature-256: sha256=<HMAC-SHA256 do corpo, com a chave secreta do aplicativo>."""
    if not segredo or not cabecalho or not str(cabecalho).startswith("sha256="):
        return False
    esperado = hmac.new(segredo.encode(), corpo, hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperado, str(cabecalho)[7:].strip().lower())


def mensagens(corpo):
    """As mensagens recebidas no que a Meta mandou: (id do número que recebeu, mensagem, nome no perfil de quem mandou)."""
    if not isinstance(corpo, dict) or corpo.get("object") != "whatsapp_business_account":
        return
    for entrada in corpo.get("entry") or []:
        for mudanca in (entrada or {}).get("changes") or []:
            if (mudanca or {}).get("field") != "messages":
                continue
            v = mudanca.get("value") or {}
            numero_id = str((v.get("metadata") or {}).get("phone_number_id") or "")
            nomes = {str(c.get("wa_id")): ((c.get("profile") or {}).get("name") or "") for c in v.get("contacts") or [] if isinstance(c, dict)}
            for m in v.get("messages") or []:
                if isinstance(m, dict) and m.get("id") and m.get("from"):
                    yield numero_id, m, nomes.get(str(m.get("from")), "")


def falhas(corpo):
    """Os avisos de mensagem que não chegou (statuses com failed): (para quem, texto do erro)."""
    if not isinstance(corpo, dict):
        return
    for entrada in corpo.get("entry") or []:
        for mudanca in (entrada or {}).get("changes") or []:
            for st in ((mudanca or {}).get("value") or {}).get("statuses") or []:
                if isinstance(st, dict) and st.get("status") == "failed":
                    erro = (st.get("errors") or [{}])[0] or {}
                    yield str(st.get("recipient_id") or ""), ERROS.get(erro.get("code")) or erro.get("title") or erro.get("message") or "Não chegou."


def texto_da_mensagem(m):
    """O texto de uma mensagem (texto, botão ou resposta de lista); None se for áudio, foto, figurinha..."""
    t = m.get("type")
    if t == "text":
        return str((m.get("text") or {}).get("body") or "")
    if t == "button":
        return str((m.get("button") or {}).get("text") or "")
    if t == "interactive":
        i = m.get("interactive") or {}
        return str((i.get("button_reply") or i.get("list_reply") or {}).get("title") or "")
    return None


def para_whatsapp(texto):
    """O texto das IAs (com **negrito** e títulos) no jeito do WhatsApp (*negrito*, sem títulos nem links em markdown)."""
    t = str(texto or "").replace("\r\n", "\n")
    t = re.sub(r"\*\*(.+?)\*\*", r"*\1*", t)
    t = re.sub(r"__(.+?)__", r"_\1_", t)
    t = re.sub(r"(?m)^#{1,6}\s+(.+)$", r"*\1*", t)
    t = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r"\1 (\2)", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def partes(texto, limite=LIMITE):
    """Texto longo em pedaços que cabem numa mensagem, quebrando de preferência entre parágrafos."""
    t = str(texto or "").strip()
    out = []
    while len(t) > limite:
        corte = t.rfind("\n\n", 0, limite)
        if corte < limite // 2:
            corte = t.rfind("\n", 0, limite)
        if corte < limite // 2:
            corte = t.rfind(" ", 0, limite)
        if corte < limite // 2:
            corte = limite
        out.append(t[:corte].rstrip())
        t = t[corte:].lstrip()
    if t:
        out.append(t)
    return out


def so_digitos(n):
    return re.sub(r"\D", "", str(n or ""))


def canonico(n):
    """O número para comparar: só dígitos e, no Brasil, sem o 9 do celular (o WhatsApp manda alguns números sem ele)."""
    d = so_digitos(n)
    if d.startswith("55") and len(d) == 13 and d[4] == "9":
        d = d[:4] + d[5:]
    return d


def mesmo_numero(a, b):
    return bool(so_digitos(a)) and canonico(a) == canonico(b)


class WhatsApp:
    """A conta do WhatsApp Business: o ID do número de telefone e o token (de um Usuário do sistema, que não vence)."""

    def __init__(self, numero_id, token, base=GRAPH, timeout=20):
        self.numero_id, self.token, self.base, self.timeout = str(numero_id or ""), str(token or ""), base.rstrip("/"), timeout

    def _pedir(self, metodo, caminho, corpo=None):
        if not self.numero_id or not self.token:
            raise ErroWhatsApp("Falta configurar o WhatsApp (ID do número e token).")
        req = urllib.request.Request(f"{self.base}/{caminho}", method=metodo,
                                     data=json.dumps(corpo).encode() if corpo is not None else None,
                                     headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            try:
                erro = (json.loads(e.read() or b"{}").get("error") or {})
            except ValueError:
                erro = {}
            codigo = erro.get("code")
            raise ErroWhatsApp(ERROS.get(codigo) or erro.get("message") or f"A Meta respondeu {e.code}.", codigo) from None
        except (urllib.error.URLError, OSError) as e:
            raise ErroWhatsApp(f"Não consegui falar com a Meta ({getattr(e, 'reason', e)}).") from None

    def texto(self, para, texto):
        """Manda o texto (em pedaços, se for longo); devolve os ids das mensagens."""
        ids = []
        for p in partes(para_whatsapp(texto)):
            r = self._pedir("POST", f"{self.numero_id}/messages", {"messaging_product": "whatsapp", "recipient_type": "individual",
                                                                     "to": so_digitos(para), "type": "text", "text": {"preview_url": False, "body": p}})
            ids += [m.get("id") for m in r.get("messages") or [] if isinstance(m, dict)]
        return ids

    def lida(self, msg_id, digitando=True):
        """Os dois tracinhos azuis e o "digitando..." enquanto a IA pensa (some com a resposta ou em 25 s)."""
        corpo = {"messaging_product": "whatsapp", "status": "read", "message_id": msg_id}
        if digitando:
            corpo["typing_indicator"] = {"type": "text"}
        return self._pedir("POST", f"{self.numero_id}/messages", corpo)

    def conferir(self):
        """O número e o nome que aparecem no WhatsApp (confere o ID e o token)."""
        r = self._pedir("GET", f"{self.numero_id}?fields=display_phone_number,verified_name")
        return {"numero": r.get("display_phone_number") or "", "nome": r.get("verified_name") or ""}
