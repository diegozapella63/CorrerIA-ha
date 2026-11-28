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
        self.assertEqual([x["id"] for x in todas], ["casa_comando", "casa_estado", "casa_historico", "casa_tempo", "casa_manutencao", "casa_avisar"])
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
        self.assertEqual([x["id"] for x in self.f.todas()][-6:], ["casa_comando", "casa_estado", "casa_historico", "casa_tempo", "casa_manutencao", "casa_avisar"], "depois dos apps")


if __name__ == "__main__":
    unittest.main()


class TestHistorico(unittest.TestCase):
    """1.40.0 (o dono, às ferramentas que faltavam: "pode seguir neles"): casa_historico, o dia de uma coisa da casa pelo
    /api/history: o que liga e desliga, o sensor de número e o consumo dos medidores de energia."""
    E = [
        {"entity_id": "light.sala", "state": "off", "attributes": {"friendly_name": "Luz da sala"}},
        {"entity_id": "binary_sensor.porta", "state": "off", "attributes": {"friendly_name": "Porta da frente", "device_class": "door"}},
        {"entity_id": "sensor.t_quarto", "state": "22", "attributes": {"friendly_name": "Temperatura do quarto", "unit_of_measurement": "°C", "device_class": "temperature"}},
        {"entity_id": "sensor.e_geladeira", "state": "104", "attributes": {"friendly_name": "Energia da geladeira", "unit_of_measurement": "kWh", "device_class": "energy", "state_class": "total_increasing"}},
        {"entity_id": "sensor.e_chuveiro", "state": "9", "attributes": {"friendly_name": "Energia do chuveiro", "unit_of_measurement": "kWh", "device_class": "energy", "state_class": "total_increasing"}},
        {"entity_id": "person.ana", "state": "home", "attributes": {"friendly_name": "Ana da sala"}},
    ]
    H = {
        "light.sala": [("2026-11-07T03:00:00+00:00", "off"), ("2026-11-07T10:00:00+00:00", "on"), ("2026-11-07T11:30:00+00:00", "off"),
                       ("2026-11-07T22:00:00+00:00", "on"), ("2026-11-07T22:45:00+00:00", "off")],
        "binary_sensor.porta": [("2026-11-07T03:00:00+00:00", "off"), ("2026-11-07T05:10:00+00:00", "on"), ("2026-11-07T05:11:00+00:00", "off")],
        "sensor.t_quarto": [("2026-11-07T03:00:00+00:00", "20"), ("2026-11-07T09:00:00+00:00", "19.5"), ("2026-11-07T18:00:00+00:00", "27"), ("2026-11-07T21:00:00+00:00", "unavailable"),
                            ("2026-11-07T23:00:00+00:00", "22")],
        "sensor.e_geladeira": [("2026-11-06T03:00:00+00:00", "100"), ("2026-11-06T20:00:00+00:00", "101.5"), ("2026-11-07T03:00:00+00:00", "101.5"), ("2026-11-07T20:00:00+00:00", "103.5"),
                               ("2026-11-07T21:00:00+00:00", "0.2"), ("2026-11-07T23:00:00+00:00", "0.5")],
        "sensor.e_chuveiro": [("2026-11-07T03:00:00+00:00", "4"), ("2026-11-07T12:00:00+00:00", "9")],
    }

    def setUp(self):
        from datetime import datetime, timezone, timedelta
        self.agora = datetime(2026, 11, 8, 9, 30, tzinfo=timezone(timedelta(hours=-3)))
        self.pedidos = []
        self.c = C.Casa(self.get, lambda c, corpo: {}, print)

    def get(self, caminho):
        self.pedidos.append(caminho)
        if caminho == "/states":
            return self.E
        from datetime import datetime
        from urllib.parse import unquote
        ids = unquote(caminho.split("filter_entity_id=")[1].split("&")[0]).split(",")
        ini = datetime.fromisoformat(unquote(caminho.split("/history/period/")[1].split("?")[0]))
        fim = datetime.fromisoformat(unquote(caminho.split("end_time=")[1].split("&")[0]))
        out = []
        for i in ids:
            pts = [(t, st) for t, st in self.H.get(i, []) if ini <= datetime.fromisoformat(t) < fim]
            if pts:
                out.append([dict({"state": st, "last_changed": t}, **({"entity_id": i} if k == 0 else {})) for k, (t, st) in enumerate(pts)])
        return out

    def test_liga_e_desliga_numero_e_porta(self):
        r = self.c.historico("luz sala", "ontem", agora=self.agora)
        self.assertEqual(r, "- Luz da sala, ontem: 2 vezes, 2 h 15 min ao todo. 00:00 desligado · 07:00 ligado · 08:30 desligado · 19:00 ligado · 19:45 desligado")
        self.assertIn("/history/period/2026-11-07T00%3A00%3A00-03%3A00?end_time=2026-11-08T00%3A00%3A00-03%3A00&filter_entity_id=light.sala&minimal_response&no_attributes", self.pedidos[-1])
        self.assertEqual(self.c.historico("porta", "2026-11-07", agora=self.agora), "- Porta da frente, ontem: 1 vez, 1 min ao todo. 00:00 fechado · 02:10 aberto · 02:11 fechado")
        r = self.c.historico("temperatura quarto", "ontem", agora=self.agora)
        self.assertIn("- Temperatura do quarto, ontem: mínima 19,5 °C às 06:00, máxima 27 °C às 15:00, média ", r)
        self.assertTrue(r.endswith("por último, 22 °C."))
        self.assertEqual(self.c.historico("xyz", agora=self.agora), "Nada com “xyz” no Home Assistant.")
        self.assertNotIn("Ana", self.c.historico("sala", "ontem", agora=self.agora), "as pessoas ficam de fora")
        muitas = C.Casa(lambda c: [dict(self.E[0], entity_id=f"light.luz{i}", attributes={"friendly_name": f"Luz {i}"}) for i in range(5)], None, print)
        self.assertIn("5 coisas com “luz”: diga qual. Luz 0; Luz 1", muitas.historico("luz", agora=self.agora))
        self.assertEqual(self.c.historico("luz sala", "anteontem", agora=self.agora), "- Luz da sala: sem histórico de 06/11/2026.")

    def test_energia_do_dia_com_o_dia_anterior(self):
        r = self.c.historico(tipo="energia", dia="ontem", agora=self.agora)
        self.assertEqual(r.split("\n"), ["Consumo de energia de ontem, do maior para o menor:", "- Energia do chuveiro: 5,00 kWh ontem",
                                         "- Energia da geladeira: 2,30 kWh ontem (no dia anterior, 1,50 kWh)"], "a queda é o medidor recomeçando")
        self.assertEqual(self.c.historico("energia geladeira", "ontem", agora=self.agora), "- Energia da geladeira: 2,30 kWh ontem.")
        sem = C.Casa(lambda c: self.E[:3], None, print)
        self.assertIn("Nenhum medidor de energia", sem.historico(tipo="energia", agora=self.agora))

    def test_o_que_vale(self):
        for args, parte in (({"busca": "luz", "dia": "amanhã"}, "hoje, ontem ou AAAA-MM-DD"), ({"busca": "luz", "dia": "2020-01-01"}, "até 30 dias"),
                            ({}, "Diga a busca"), ({"tipo": "agua"}, "tipo vale energia")):
            with self.assertRaises(C.ErroCasa) as e:
                self.c.usar("historico", args)
            self.assertIn(parte, str(e.exception))

        def cai(c):
            raise OSError("fora do ar")
        with self.assertRaises(C.ErroCasa):
            C.Casa(cai, None, print).historico("luz", agora=self.agora)
        self.assertEqual([f["nome"] for f in C.FERRAMENTAS], ["comando", "estado", "historico", "tempo", "manutencao", "avisar"])


class TestCasa141(unittest.TestCase):
    """1.41.0 (o dono, às ferramentas que faltavam: "pode seguir em todas"): casa_tempo, casa_manutencao e casa_avisar."""
    E = [
        {"entity_id": "weather.casa", "state": "partlycloudy", "attributes": {"friendly_name": "Previsão de casa", "temperature": 23.4, "humidity": 71, "temperature_unit": "°C"}},
        {"entity_id": "weather.zz_fora", "state": "unavailable", "attributes": {}},
        {"entity_id": "update.core", "state": "on", "attributes": {"friendly_name": "Core update", "title": "Home Assistant Core", "installed_version": "2026.11.1", "latest_version": "2026.11.3"}},
        {"entity_id": "update.zigbee", "state": "on", "attributes": {"friendly_name": "Zigbee da sala"}},
        {"entity_id": "update.em_dia", "state": "off", "attributes": {"friendly_name": "Em dia"}},
        {"entity_id": "automation.luz", "state": "off", "attributes": {"friendly_name": "Luz ao chegar"}},
        {"entity_id": "automation.ok", "state": "on", "attributes": {"friendly_name": "Bom dia"}},
        {"entity_id": "sensor.backup_last_successful_automatic_backup", "state": "2026-11-05T04:00:00+00:00", "attributes": {}},
    ]
    PREV = [{"datetime": "2026-11-08T12:00:00+00:00", "condition": "rainy", "temperature": 27.2, "templow": 19, "precipitation_probability": 80, "precipitation": 12.5},
            {"datetime": "2026-11-09T12:00:00+00:00", "condition": "sunny", "temperature": 30, "templow": 20, "precipitation": 0},
            {"datetime": "2026-11-10T12:00:00+00:00", "condition": "nova"}, {"datetime": "2026-11-11T12:00:00+00:00", "condition": "cloudy"}]

    def setUp(self):
        self.posts, self.recados = [], []
        self.estados = list(self.E)
        self.c = C.Casa(lambda c: self.estados, self.post, lambda *a: None, recado=lambda para, msg, pessoa: (self.recados.append((para, msg, pessoa)), "ok")[1])

    def post(self, caminho, corpo):
        self.posts.append((caminho, corpo))
        return {"service_response": {"weather.casa": {"forecast": self.PREV}}}

    def test_tempo(self):
        t = self.c.usar("tempo", {}).splitlines()
        self.assertEqual(self.posts, [("/services/weather/get_forecasts?return_response", {"entity_id": "weather.casa", "type": "daily"})])
        self.assertEqual(t, ["Agora (Previsão de casa): parcialmente nublado, 23,4 °C, umidade 71%.",
                             "Hoje: chuva, máxima 27 °C, mínima 19 °C, 80% de chance de chuva (12,5 mm).",
                             "Amanhã: sol, máxima 30 °C, mínima 20 °C.", "10/11: nova."])
        self.assertEqual(len(self.c.usar("tempo", {"dias": 1}).splitlines()), 2)
        with self.assertRaisesRegex(C.ErroCasa, "dias: de 1 a 7"):
            self.c.usar("tempo", {"dias": "x"})
        def falha(c, corpo):
            raise OSError("sem serviço")
        self.assertTrue(C.Casa(lambda c: self.E, falha, lambda *a: None).tempo().endswith("Essa previsão do tempo não dá os próximos dias."))
        with self.assertRaisesRegex(C.ErroCasa, "Não há previsão do tempo"):
            C.Casa(lambda c: [], self.post, print).tempo()
        def cai(c):
            raise OSError("fora do ar")
        with self.assertRaisesRegex(C.ErroCasa, "não respondeu"):
            C.Casa(cai, self.post, print).tempo()

    def test_manutencao(self):
        from datetime import datetime, timezone
        t = self.c.manutencao(datetime(2026, 11, 8, 12, 0, tzinfo=timezone.utc)).splitlines()
        self.assertEqual(t, ["2 atualizações pendentes:", "- Home Assistant Core: 2026.11.1 → 2026.11.3", "- Zigbee da sala",
                             "1 automação desligada: Luz ao chegar.", "Último backup do Home Assistant: há 3 dias."])
        self.estados = [{"entity_id": "sensor.backup_last_successful_automatic_backup", "state": "unknown"}]
        self.assertEqual(self.c.usar("manutencao", {}).splitlines(), ["0 atualizações pendentes.", "0 automações desligadas.", "Ainda não há um backup automático feito."])
        self.estados = [{"entity_id": f"update.u{i}", "state": "on", "attributes": {"friendly_name": f"U{i:02d}"}} for i in range(14)]
        t = self.c.manutencao()
        self.assertIn("- e mais 2", t)
        self.assertIn("Não sei do último backup", t)
        self.estados = [{"entity_id": "sensor.backup_last_successful_automatic_backup", "state": "2026-10-01T04:00:00+00:00"}]
        self.assertIn("faz mais de uma semana", self.c.manutencao(datetime(2026, 11, 8, 12, 0, tzinfo=timezone.utc)))
        self.assertIn("backup do Home Assistant: hoje.", self.c.manutencao(datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)))
        self.assertIn("ontem.", self.c.manutencao(datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)))

    def test_avisar(self):
        ana = {"id": "person.ana", "nome": "Ana"}
        self.assertEqual(self.c.usar("avisar", {"para": " Beto ", "mensagem": "Cheguei  em casa"}, ana), "ok")
        self.assertEqual(self.recados, [("Beto", "Cheguei em casa", ana)])
        with self.assertRaisesRegex(C.ErroCasa, "Faltam para"):
            self.c.usar("avisar", {"para": "Beto"})
        with self.assertRaisesRegex(C.ErroCasa, "não estão disponíveis"):
            C.Casa(lambda c: [], self.post, print).usar("avisar", {"para": "Beto", "mensagem": "oi"})
        f = {x["nome"]: x for x in C.FERRAMENTAS}
        self.assertEqual((f["avisar"]["grava"], f["tempo"]["grava"], f["manutencao"]["grava"]), (True, False, False))
