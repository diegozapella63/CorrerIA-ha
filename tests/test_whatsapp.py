"""whatsapp.py: a assinatura do webhook, as mensagens no que a Meta manda, o texto no jeito do WhatsApp, os números do
Brasil (com e sem o 9) e o cliente da Graph API (contra uma Meta de mentira)."""
import hashlib
import hmac
import json
import unittest

from tests.base import MetaFalsa, ServidorFalso, porta_livre, ANA, ANA_WA
import whatsapp as W


def entrega(*mensagens, numero_id=MetaFalsa.NUMERO_ID, contatos=None, statuses=None):
    v = {"messaging_product": "whatsapp", "metadata": {"display_phone_number": "554140000000", "phone_number_id": numero_id},
         "contacts": contatos if contatos is not None else [{"profile": {"name": "Ana Exemplo"}, "wa_id": ANA_WA}], "messages": list(mensagens)}
    if statuses:
        v = {"messaging_product": "whatsapp", "metadata": v["metadata"], "statuses": statuses}
    return {"object": "whatsapp_business_account", "entry": [{"id": "WABA", "changes": [{"field": "messages", "value": v}]}]}


def texto(corpo, de=ANA_WA, mid="wamid.1"):
    return {"from": de, "id": mid, "timestamp": "1762600000", "type": "text", "text": {"body": corpo}}


class TestAssinatura(unittest.TestCase):
    def test_hmac_sha256_com_a_chave_secreta(self):
        corpo = b'{"object":"whatsapp_business_account"}'
        sig = "sha256=" + hmac.new(b"segredo-do-app", corpo, hashlib.sha256).hexdigest()
        self.assertTrue(W.assinatura_ok("segredo-do-app", corpo, sig))
        self.assertTrue(W.assinatura_ok("segredo-do-app", corpo, sig.upper().replace("SHA256=", "sha256=")))
        self.assertFalse(W.assinatura_ok("outro", corpo, sig))
        self.assertFalse(W.assinatura_ok("segredo-do-app", corpo + b" ", sig), "o corpo exato")
        for ruim in ("", None, "md5=abc", sig[7:]):
            self.assertFalse(W.assinatura_ok("segredo-do-app", corpo, ruim))
        self.assertFalse(W.assinatura_ok("", corpo, sig), "sem a chave secreta, nada passa")


class TestMensagens(unittest.TestCase):
    def test_tira_as_mensagens_e_o_nome(self):
        e = entrega(texto("Quanto gastei?"), texto("e ontem?", mid="wamid.2"))
        lista = list(W.mensagens(e))
        self.assertEqual([(n, m["id"], nome) for n, m, nome in lista], [(MetaFalsa.NUMERO_ID, "wamid.1", "Ana Exemplo"), (MetaFalsa.NUMERO_ID, "wamid.2", "Ana Exemplo")])

    def test_ignora_o_que_nao_e_mensagem(self):
        self.assertEqual(list(W.mensagens({"object": "page"})), [])
        self.assertEqual(list(W.mensagens(None)), [])
        e = entrega(texto("oi"))
        e["entry"][0]["changes"][0]["field"] = "account_update"
        self.assertEqual(list(W.mensagens(e)), [])
        self.assertEqual(list(W.mensagens(entrega({"id": "x"}, "lixo", contatos=[]))), [], "sem quem mandou")
        self.assertEqual(list(W.mensagens({"object": "whatsapp_business_account", "entry": [None, {"changes": [None]}]})), [])

    def test_falhas_de_entrega(self):
        e = entrega(statuses=[{"id": "wamid.r", "status": "failed", "recipient_id": ANA_WA, "errors": [{"code": 131047, "title": "Re-engagement message"}]},
                              {"id": "wamid.s", "status": "delivered", "recipient_id": ANA_WA},
                              {"status": "failed", "recipient_id": "1", "errors": [{"code": 999, "title": "Outro erro"}]}])
        self.assertEqual(list(W.falhas(e)), [(ANA_WA, W.ERROS[131047]), ("1", "Outro erro")])
        self.assertEqual(list(W.falhas([])), [])

    def test_texto_da_mensagem(self):
        self.assertEqual(W.texto_da_mensagem(texto("oi")), "oi")
        self.assertEqual(W.texto_da_mensagem({"type": "button", "button": {"text": "Sim"}}), "Sim")
        self.assertEqual(W.texto_da_mensagem({"type": "interactive", "interactive": {"list_reply": {"title": "Opção A"}}}), "Opção A")
        for t in ("audio", "image", "document", "sticker", "location", "reaction"):
            self.assertIsNone(W.texto_da_mensagem({"type": t}), t)


class TestTexto(unittest.TestCase):
    def test_markdown_para_o_whatsapp(self):
        self.assertEqual(W.para_whatsapp("Você gastou **R$ 1.234,56** em __novembro__."), "Você gastou *R$ 1.234,56* em _novembro_.")
        self.assertEqual(W.para_whatsapp("## Resumo\n\n\n\nVeja [o app](https://exemplo.com/a)."), "*Resumo*\n\nVeja o app (https://exemplo.com/a).")
        self.assertEqual(W.para_whatsapp(None), "")

    def test_partes(self):
        self.assertEqual(W.partes("curto"), ["curto"])
        longo = "\n\n".join(["parágrafo " * 30] * 20)
        p = W.partes(longo, 1000)
        self.assertTrue(all(len(x) <= 1000 for x in p))
        self.assertEqual(" ".join(p).split(), longo.split(), "nada se perde")
        self.assertEqual(W.partes("x" * 2500, 1000), ["x" * 1000, "x" * 1000, "x" * 500], "sem espaço: corta no limite")
        self.assertEqual(W.partes(""), [])


class TestNumeros(unittest.TestCase):
    def test_com_e_sem_o_9(self):
        self.assertTrue(W.mesmo_numero(ANA, ANA_WA))
        self.assertTrue(W.mesmo_numero("+55 (11) 98765-0001", ANA_WA))
        self.assertFalse(W.mesmo_numero(ANA, "5511987650002"))
        self.assertFalse(W.mesmo_numero("", ""))
        self.assertEqual(W.canonico("14155550100"), "14155550100", "de fora do Brasil, como está")
        self.assertEqual(W.canonico("551134560000"), "551134560000", "fixo")


class TestCliente(unittest.TestCase):
    def setUp(self):
        self.meta = MetaFalsa()
        self.addCleanup(self.meta.fechar)
        self.wa = W.WhatsApp(MetaFalsa.NUMERO_ID, "token-teste-123", self.meta.url)

    def test_texto(self):
        ids = self.wa.texto(ANA_WA, "Você gastou **R$ 10**.")
        self.assertEqual(ids, ["wamid.resp"])
        m, p, h, c = self.meta.pedidos[0]
        self.assertEqual((m, p, h["Authorization"]), ("POST", f"/{MetaFalsa.NUMERO_ID}/messages", "Bearer token-teste-123"))
        self.assertEqual(c, {"messaging_product": "whatsapp", "recipient_type": "individual", "to": ANA_WA, "type": "text",
                             "text": {"preview_url": False, "body": "Você gastou *R$ 10*."}})

    def test_texto_longo_vai_em_partes(self):
        self.wa.texto(ANA_WA, "\n\n".join(["palavra " * 100] * 12))
        self.assertGreater(len(self.meta.textos()), 1)
        self.assertTrue(all(len(t) <= W.LIMITE for _, t in self.meta.textos()))

    def test_lida_e_digitando(self):
        self.wa.lida("wamid.1")
        self.wa.lida("wamid.2", digitando=False)
        self.assertEqual(self.meta.lidas(), [{"messaging_product": "whatsapp", "status": "read", "message_id": "wamid.1", "typing_indicator": {"type": "text"}},
                                             {"messaging_product": "whatsapp", "status": "read", "message_id": "wamid.2"}])

    def test_conferir(self):
        self.assertEqual(self.wa.conferir(), {"numero": "+55 11 4000-0000", "nome": "CorrerIA Code"})
        self.assertEqual(self.meta.pedidos[0][1], f"/{MetaFalsa.NUMERO_ID}?fields=display_phone_number,verified_name")

    def test_erros_da_meta_em_portugues(self):
        self.meta.rotas[f"/{MetaFalsa.NUMERO_ID}/messages"] = (401, {"error": {"message": "Error validating access token", "code": 190}})
        with self.assertRaises(W.ErroWhatsApp) as e:
            self.wa.texto(ANA_WA, "oi")
        self.assertEqual((str(e.exception), e.exception.codigo), (W.ERROS[190], 190))
        self.meta.rotas[f"/{MetaFalsa.NUMERO_ID}/messages"] = (400, {"error": {"message": "Algo novo", "code": 4242}})
        with self.assertRaisesRegex(W.ErroWhatsApp, "^Algo novo$"):
            self.wa.texto(ANA_WA, "oi")
        self.meta.rotas[f"/{MetaFalsa.NUMERO_ID}/messages"] = (500, "não é json")
        with self.assertRaisesRegex(W.ErroWhatsApp, "A Meta respondeu 500."):
            self.wa.texto(ANA_WA, "oi")

    def test_sem_configurar_e_sem_rede(self):
        with self.assertRaisesRegex(W.ErroWhatsApp, "Falta configurar"):
            W.WhatsApp("", "", self.meta.url).texto(ANA_WA, "oi")
        with self.assertRaisesRegex(W.ErroWhatsApp, "Não consegui falar com a Meta"):
            W.WhatsApp("1", "token-teste", f"http://127.0.0.1:{porta_livre()}", timeout=2).conferir()


if __name__ == "__main__":
    unittest.main()
