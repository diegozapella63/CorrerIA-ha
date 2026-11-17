"""casa.py (1.5.0): a casa do Home Assistant como um app da CorrerIA. O pedido vai para o Assist (conversation/process,
o agente do próprio Home Assistant); como as coisas estão vem de /api/states, sem a localização das pessoas. Um Home
Assistant de mentira (as funções get e post)."""
import unittest

from tests.base import AppFalso, pasta_temp
import apps as A
import casa as C
import ferramentas as F

ESTADOS = [
    {"entity_id": "light.luz_da_entrada", "state": "off", "attributes": {"friendly_name": "Luz da entrada"}},
    {"entity_id": "light.sala", "state": "on", "attributes": {"friendly_name": "Luz da sala", "brightness": 128}},
    {"entity_id": "climate.ar_do_quarto", "state": "cool", "attributes": {"friendly_name": "Ar do quarto", "current_temperature": 25, "temperature": 23}},
    {"entity_id": "sensor.temperatura_da_sala", "state": "24.5", "attributes": {"friendly_name": "Temperatura da sala", "unit_of_measurement": "°C"}},
    {"entity_id": "cover.cortina", "state": "open", "attributes": {"friendly_name": "Cortina", "current_position": 60}},
    {"entity_id": "person.ana", "state": "home", "attributes": {"friendly_name": "Ana"}},
    {"entity_id": "device_tracker.celular_da_ana", "state": "home", "attributes": {"friendly_name": "Celular da Ana"}},
]


def assist(fala, tipo="action_done", sucesso=(), falhou=()):
    return {"response": {"response_type": tipo, "speech": {"plain": {"speech": fala}},
                         "data": {"success": [{"type": "entity", "name": n, "id": n} for n in sucesso], "failed": [{"name": n} for n in falhou]}}}


class TestCasa(unittest.TestCase):
    def setUp(self):
        self.pedidos = []
        self.resposta = assist("Luz da entrada ligada", sucesso=["Luz da entrada"])
        self.c = C.Casa(lambda caminho: ESTADOS, self.post, print)

    def post(self, caminho, corpo):
        self.pedidos.append((caminho, corpo))
        if isinstance(self.resposta, Exception):
            raise self.resposta
        return self.resposta

    def test_comando_vai_para_o_assist(self):
        self.assertEqual(self.c.usar("comando", {"pedido": "  liga a luz   da entrada "}), "Luz da entrada ligada")
        self.assertEqual(self.pedidos, [("/conversation/process", {"text": "liga a luz da entrada", "language": "pt-BR", "agent_id": "conversation.home_assistant"})])
        self.resposta = assist("Ligado", sucesso=["Luz da sala", "Abajur"])
        self.assertEqual(self.c.comando("liga as luzes da sala"), "Ligado (Luz da sala, Abajur)")
        self.resposta = {"response": {"response_type": "action_done", "data": {}}}
        self.assertEqual(self.c.comando("liga"), "Feito.")

    def test_comando_que_nao_deu(self):
        for resposta, msg in ((assist("Desculpe, não conheço nenhuma área chamada garagem", "error"), "Desculpe, não conheço nenhuma área chamada garagem"),
                              (assist("", "error"), "O Assist não entendeu o pedido."),
                              (assist("", falhou=["Luz da entrada"]), "Não deu: Luz da entrada."),
                              (OSError("HTTP Error 401: Unauthorized"), "O Home Assistant não respondeu (HTTP Error 401: Unauthorized).")):
            self.resposta = resposta
            with self.assertRaises(C.ErroCasa) as e:
                self.c.comando("liga a luz da garagem")
            self.assertEqual(str(e.exception), msg)
        with self.assertRaises(C.ErroCasa):
            self.c.usar("comando", {"pedido": " "})
        with self.assertRaises(C.ErroCasa):
            self.c.usar("voar", {})

    def test_estado_sem_mexer(self):
        self.assertEqual(self.c.usar("estado", {"busca": "luz da sala"}), "- Luz da sala: ligado, 50% (light.sala)")
        self.assertEqual(self.c.estado("temperatura"), "- Temperatura da sala: 24.5 °C (sensor.temperatura_da_sala)")
        self.assertEqual(self.c.estado("luzes"), "- Luz da entrada: desligado (light.luz_da_entrada)\n- Luz da sala: ligado, 50% (light.sala)")
        tudo = self.c.estado("")
        self.assertIn("- Ar do quarto: esfriando, 25° agora, alvo 23° (climate.ar_do_quarto)", tudo)
        self.assertIn("- Cortina: aberto, 60% (cover.cortina)", tudo)
        self.assertNotIn("temperatura_da_sala", tudo, "sem busca: luzes, tomadas, cortinas e ar")
        self.assertEqual(self.c.estado("ana"), "Nada com “ana” no Home Assistant.", "nem as pessoas nem onde estão")
        self.assertEqual(self.pedidos, [], "ver não mexe")
        muitos = [{"entity_id": f"light.l{i}", "state": "off", "attributes": {}} for i in range(45)]
        self.assertTrue(C.Casa(lambda c: muitos, self.post, print).estado("").endswith("… e mais 5."))
        self.assertEqual(C.Casa(lambda c: [], self.post, print).estado(""), "Nenhuma luz, tomada, cortina ou ar no Home Assistant.")

        def falha(c):
            raise OSError("fora do ar")
        with self.assertRaises(C.ErroCasa):
            C.Casa(falha, self.post, print).estado("luz")


class TestCasaNasFerramentas(unittest.TestCase):
    def setUp(self):
        self.share = pasta_temp()
        self.ligada = True
        self.casa = C.Casa(lambda c: ESTADOS, lambda c, corpo: assist("Luz da entrada ligada"), print)
        self.f = F.Ferramentas(A.Apps(self.share, print, cache=0), print, casa=lambda: self.casa if self.ligada else None)

    def test_casa_como_um_app(self):
        self.assertTrue(self.f.tem(), "sem nenhum app, a casa já basta")
        todas = self.f.todas()
        self.assertEqual([x["id"] for x in todas], ["casa_comando", "casa_estado"])
        cmd = self.f.achar("casa_comando", todas)
        self.assertEqual((cmd["grava"], cmd["app"]["nome"]), (True, "Casa"), "mexer na casa espera o sim")
        self.assertFalse(self.f.achar("casa_estado", todas)["grava"])
        self.assertIn("- Casa (o Home Assistant", self.f.instrucoes())
        self.assertEqual(self.f.usar(cmd, {"pedido": "liga a luz da entrada"}, {"nome": "Ana"}, "WhatsApp"), ("Luz da entrada ligada", False))
        self.assertEqual(self.f.usar(cmd, {}, {}, "WhatsApp"), ("Falta o pedido (ex.: liga a luz da entrada).", True))
        self.ligada = False
        self.assertFalse(self.f.tem())
        self.assertEqual(self.f.todas(), [])
        self.assertEqual(self.f.usar(cmd, {"pedido": "liga"}, {}, "WhatsApp"), ("A casa do Home Assistant está desligada no CorrerIA.", True))
        cron = AppFalso("CronologIA")
        self.addCleanup(cron.fechar)
        cron.publicar(self.share, "cronologia")
        self.ligada = True
        self.assertEqual([x["id"] for x in self.f.todas()][-2:], ["casa_comando", "casa_estado"], "depois dos apps")


if __name__ == "__main__":
    unittest.main()
