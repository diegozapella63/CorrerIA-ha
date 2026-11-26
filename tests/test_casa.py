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


    def test_ligados_e_por_comodo(self):
        """1.37.0 (as rondas: "ficou algo ligado?"): ligados só o que está ligado, aberto ou destrancado (e as portas e janelas
        abertas, pelo sensor); comodo, o que está na área do Home Assistant com esse nome (sem ela, o cômodo no nome)."""
        mais = ESTADOS + [{"entity_id": "binary_sensor.porta_da_varanda", "state": "on", "attributes": {"friendly_name": "Porta da varanda", "device_class": "door"}},
                          {"entity_id": "binary_sensor.movimento", "state": "on", "attributes": {"friendly_name": "Movimento", "device_class": "motion"}},
                          {"entity_id": "lock.porta", "state": "locked", "attributes": {"friendly_name": "Fechadura"}}]
        areas = "light.sala|Sala de estar\nsensor.temperatura_da_sala|Sala de estar\nclimate.ar_do_quarto|Quarto\ncover.cortina|Quarto\n"
        c = C.Casa(lambda caminho: mais, self.post, print, lambda modelo: areas)
        t = c.usar("estado", {"ligados": True})
        self.assertIn("Luz da sala: ligado", t)
        self.assertIn("Ar do quarto", t)
        self.assertIn("Cortina: aberto", t)
        self.assertIn("Porta da varanda", t)
        for fora in ("Luz da entrada", "Movimento", "Fechadura", "Temperatura"):
            self.assertNotIn(fora, t)
        q = c.usar("estado", {"ligados": True, "comodo": "quarto"})
        self.assertIn("Ar do quarto", q)
        self.assertIn("Cortina", q)
        self.assertNotIn("Luz da sala", q)
        self.assertIn("Luz da sala", c.usar("estado", {"comodo": "Sala de Estar"}))
        self.assertIn("Luz da sala", c.usar("estado", {"comodo": "Sala"}))  # a área que começa pelo nome do cômodo
        self.assertEqual(c.usar("estado", {"ligados": True, "comodo": "escritório"}), "Nada ligado ou aberto em «escritório».")
        # sem a área no Home Assistant (ou sem o /api/template), o cômodo vale no nome de cada coisa
        sem = C.Casa(lambda caminho: mais, self.post, print)
        self.assertIn("Luz da sala", sem.usar("estado", {"comodo": "sala"}))
        self.assertNotIn("Ar do quarto", sem.usar("estado", {"comodo": "sala"}))

        def quebra(m):
            raise RuntimeError("sem areas()")
        self.assertIn("Luz da sala", C.Casa(lambda caminho: mais, self.post, lambda *a: None, quebra).usar("estado", {"comodo": "sala"}))
        self.assertEqual(sem.usar("estado", {"comodo": "garagem"}), "Nada com “garagem” no Home Assistant.")
        self.assertTrue(C.ligado({"entity_id": "climate.x", "state": "heat"}) and not C.ligado({"entity_id": "climate.x", "state": "off"}))

    def test_visoes_prontas(self):
        """1.38.0 (o dono: "cria mais para a casa, energia, cores da luz talvez, temperatura cômodos?"): o casa_estado com
        tipo: energia (watts, do maior), temperatura (por cômodo), luzes (o brilho e a cor), seguranca, baterias fracas e
        o que não responde; cada linha com o cômodo (a área), e o comodo filtra."""
        E = [
            {"entity_id": "light.sala", "state": "on", "attributes": {"friendly_name": "Luz da sala", "brightness": 128, "color_mode": "color_temp", "color_temp_kelvin": 2700}},
            {"entity_id": "light.fita", "state": "on", "attributes": {"friendly_name": "Fita", "color_mode": "hs", "hs_color": [230, 80]}},
            {"entity_id": "light.abajur", "state": "on", "attributes": {"friendly_name": "Abajur", "color_mode": "rgb", "rgb_color": [255, 0, 0]}},
            {"entity_id": "light.corredor", "state": "off", "attributes": {"friendly_name": "Corredor"}},
            {"entity_id": "sensor.geladeira", "state": "120.4", "attributes": {"friendly_name": "Geladeira", "device_class": "power", "unit_of_measurement": "W"}},
            {"entity_id": "sensor.chuveiro", "state": "5.5", "attributes": {"friendly_name": "Chuveiro", "device_class": "power", "unit_of_measurement": "kW"}},
            {"entity_id": "sensor.tv", "state": "0", "attributes": {"friendly_name": "TV", "device_class": "power", "unit_of_measurement": "W"}},
            {"entity_id": "sensor.t_sala", "state": "24.5", "attributes": {"friendly_name": "Temperatura sala", "device_class": "temperature", "unit_of_measurement": "°C"}},
            {"entity_id": "sensor.u_sala", "state": "58", "attributes": {"friendly_name": "Umidade sala", "device_class": "humidity", "unit_of_measurement": "%"}},
            {"entity_id": "sensor.t_fora", "state": "19", "attributes": {"friendly_name": "Temperatura lá fora", "device_class": "temperature", "unit_of_measurement": "°C"}},
            {"entity_id": "climate.ar", "state": "cool", "attributes": {"friendly_name": "Ar do quarto", "current_temperature": 25, "temperature": 23}},
            {"entity_id": "lock.porta", "state": "unlocked", "attributes": {"friendly_name": "Fechadura da frente"}},
            {"entity_id": "binary_sensor.janela", "state": "on", "attributes": {"friendly_name": "Janela do quarto", "device_class": "window"}},
            {"entity_id": "binary_sensor.porta_fechada", "state": "off", "attributes": {"friendly_name": "Porta dos fundos", "device_class": "door"}},
            {"entity_id": "sensor.bat_porta", "state": "12", "attributes": {"friendly_name": "Bateria da porta", "device_class": "battery", "unit_of_measurement": "%"}},
            {"entity_id": "sensor.bat_ok", "state": "90", "attributes": {"friendly_name": "Bateria do controle", "device_class": "battery", "unit_of_measurement": "%"}},
            {"entity_id": "binary_sensor.bat_baixa", "state": "on", "attributes": {"friendly_name": "Sensor do banheiro", "device_class": "battery"}},
            {"entity_id": "light.varanda", "state": "unavailable", "attributes": {"friendly_name": "Luz da varanda"}},
            {"entity_id": "scene.cinema", "state": "unavailable", "attributes": {"friendly_name": "Cinema"}},
        ]
        areas = "sensor.t_sala|Sala\nsensor.u_sala|Sala\nclimate.ar|Quarto\nlight.sala|Sala\nsensor.geladeira|Cozinha\nbinary_sensor.janela|Quarto\n"
        c = C.Casa(lambda caminho: E, self.post, print, lambda modelo: areas)
        en = c.usar("estado", {"tipo": "energia"}).splitlines()
        self.assertEqual(en, ["- Chuveiro: 5500 W (sensor.chuveiro)", "- Geladeira: 120 W (sensor.geladeira) · Cozinha"])
        t = c.usar("estado", {"tipo": "temperatura"})
        self.assertIn("- Sala: 24,5 °C · umidade 58%", t)
        self.assertIn("- Quarto: Ar do quarto: esfriando, 25° agora, alvo 23°", t)
        self.assertIn("- Temperatura lá fora: 19 °C (sensor.t_fora)", t)
        self.assertEqual(c.usar("estado", {"tipo": "temperatura", "comodo": "sala"}), "- Sala: 24,5 °C · umidade 58%")
        lz = c.usar("estado", {"tipo": "luzes"})
        self.assertIn("- Luz da sala: acesa, 50%, branca quente (light.sala) · Sala", lz)
        self.assertIn("- Fita: acesa, azul (light.fita)", lz)
        self.assertIn("- Abajur: acesa, vermelha (light.abajur)", lz)
        self.assertNotIn("Corredor", lz)
        sg = c.usar("estado", {"tipo": "seguranca"})
        self.assertIn("- Fechadura da frente: destrancado (lock.porta)", sg)
        self.assertIn("- Janela do quarto: aberto (binary_sensor.janela) · Quarto", sg)
        self.assertNotIn("Porta dos fundos", sg)
        self.assertEqual(c.usar("estado", {"tipo": "baterias"}).splitlines(),
                         ["- Sensor do banheiro: fraca (binary_sensor.bat_baixa)", "- Bateria da porta: 12% (sensor.bat_porta)"])
        self.assertEqual(c.usar("estado", {"tipo": "sem_resposta"}), "- Luz da varanda (light.varanda)")
        # sem nada, a frase do vazio; o cômodo sem área vai pelo nome; um tipo que não existe é erro
        self.assertEqual(c.usar("estado", {"tipo": "luzes", "comodo": "Quarto"}), "Nenhuma luz acesa em «Quarto».")
        sem = C.Casa(lambda caminho: E, self.post, print)
        self.assertEqual(sem.usar("estado", {"tipo": "energia", "comodo": "chuveiro"}), "- Chuveiro: 5500 W (sensor.chuveiro)")
        self.assertEqual(C.Casa(lambda caminho: [], self.post, print).usar("estado", {"tipo": "baterias"}), "Nenhuma bateria fraca (20% ou menos).")
        self.assertEqual(C.Casa(lambda caminho: [], self.post, print).usar("estado", {"tipo": "energia"}),
                         "Nada gastando agora (nenhum sensor de consumo, em watts, acima de zero).")
        for t in ("temperatura", "seguranca", "sem_resposta"):
            self.assertTrue(C.Casa(lambda caminho: [], self.post, print).usar("estado", {"tipo": t}).endswith("."))
        with self.assertRaises(C.ErroCasa):
            c.usar("estado", {"tipo": "tudo"})
        # as cores: branca (pouca saturação), fria e neutra pela temperatura, e sem nada
        self.assertEqual((C.cor_da_luz({"hs_color": [30, 5]}), C.cor_da_luz({"color_mode": "color_temp", "color_temp_kelvin": 6000}),
                          C.cor_da_luz({"color_temp": 250}), C.cor_da_luz({}), C.cor_da_luz({"color_mode": "color_temp"}),
                          C.cor_da_luz({"rgb_color": [1, "x", 3]}), C.cor_da_luz({"hs_color": [300, 90]})),
                         ("branca", "branca fria", "branca neutra", "", "branca", "", "rosa"))
        self.assertIsNone(C._num("nan"))
        # a busca acha as cenas pelo nome do tipo
        self.assertIn("Cinema", c.usar("estado", {"busca": "cena"}))


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
