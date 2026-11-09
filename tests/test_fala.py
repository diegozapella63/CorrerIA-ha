"""fala.py: o áudio do WhatsApp (OGG/Opus) e o do microfone da tela (PCM de 16 kHz) em texto pela fala para texto do
Home Assistant (um Home Assistant de mentira): escolher o motor que aceita o formato (o do Home Assistant Cloud primeiro),
o cabeçalho X-Speech-Content, o texto e os erros."""
import json
import unittest

from tests.base import ServidorFalso, porta_livre
import fala as F

CLOUD = {"languages": ["en-US", "pt-BR"], "formats": ["wav", "ogg"], "codecs": ["pcm", "opus"], "sample_rates": [16000], "bit_rates": [16], "channels": [1]}
WHISPER = {"languages": ["pt"], "formats": ["wav"], "codecs": ["pcm"], "sample_rates": [16000], "bit_rates": [16], "channels": [1]}


class TestFala(unittest.TestCase):
    def setUp(self):
        self.ha = ServidorFalso({
            "/api/states": (200, [{"entity_id": "stt.faster_whisper", "attributes": {"friendly_name": "faster-whisper"}},
                                  {"entity_id": "stt.home_assistant_cloud", "attributes": {"friendly_name": "Home Assistant Cloud"}},
                                  {"entity_id": "light.sala", "attributes": {}}]),
            "/api/stt/stt.home_assistant_cloud": lambda h, c: (200, CLOUD) if h.command == "GET" else (200, {"result": "success", "text": "Quanto gastei este mês?"}),
            "/api/stt/stt.faster_whisper": (200, WHISPER),
        })
        self.addCleanup(self.ha.fechar)
        self.reg = []
        self.f = F.Fala(self.ha.url + "/api", "token-ha", lambda *a: self.reg.append(a))

    def test_escolhe_o_motor_que_aceita_ogg(self):
        self.assertEqual(self.f.motor(), {"id": "stt.home_assistant_cloud", "nome": "Home Assistant Cloud", "idioma": "pt-BR", "taxa": 16000})
        self.assertEqual(self.f.status(), {"pronta": True, "nome": "Home Assistant Cloud"})
        n = len(self.ha.pedidos)
        self.f.motor()
        self.assertEqual(len(self.ha.pedidos), n, "guardado por 5 minutos")

    def test_audio_para_texto(self):
        self.assertEqual(self.f.texto(b"OggS-audio"), "Quanto gastei este mês?")
        m, p, h, c = self.ha.pedidos[-1]
        self.assertEqual((m, p), ("POST", "/api/stt/stt.home_assistant_cloud"))
        self.assertEqual(h["X-Speech-Content"], "format=ogg; codec=opus; sample_rate=16000; bit_rate=16; channel=1; language=pt-BR")
        self.assertEqual(h["Authorization"], "Bearer token-ha")

    def test_nenhum_aceita_ogg(self):
        self.ha.rotas["/api/stt/stt.home_assistant_cloud"] = (200, WHISPER)
        st = self.f.status()
        self.assertFalse(st["pronta"])
        self.assertEqual(st["motivo"], "A fala para texto do Home Assistant (Home Assistant Cloud, faster-whisper) não aceita o áudio do WhatsApp (OGG).")
        with self.assertRaisesRegex(F.ErroFala, "não aceita o áudio do WhatsApp"):
            self.f.texto(b"OggS")

    def test_idioma_e_taxa(self):
        self.ha.rotas["/api/stt/stt.home_assistant_cloud"] = (200, dict(CLOUD, languages=["en", "pt-PT"], sample_rates=[48000, 8000]))
        m = self.f.motor()
        self.assertEqual((m["idioma"], m["taxa"]), ("pt-PT", 48000))

    def test_sem_fala_para_texto(self):
        self.ha.rotas["/api/states"] = (200, [{"entity_id": "light.sala"}])
        self.assertEqual(self.f.status()["motivo"], "O Home Assistant não tem fala para texto (Configurações › Assistentes de voz).")
        self.assertIn("Fora do Home Assistant", F.Fala("http://x/api", None, print).status()["motivo"])
        self.assertIn("Não consegui falar com o Home Assistant", F.Fala(f"http://127.0.0.1:{porta_livre()}/api", "t", print).status()["motivo"])

    def test_erros_ao_ouvir(self):
        self.f.motor()
        self.ha.rotas["/api/stt/stt.home_assistant_cloud"] = lambda h, c: (415, "formato") if h.command == "POST" else (200, CLOUD)
        with self.assertRaisesRegex(F.ErroFala, "não aceitou o áudio"):
            self.f.texto(b"OggS")
        self.assertNotIn("ogg", self.f.cache, "esquece o motor para olhar de novo")
        self.ha.rotas["/api/stt/stt.home_assistant_cloud"] = lambda h, c: (500, "pane") if h.command == "POST" else (200, CLOUD)
        with self.assertRaisesRegex(F.ErroFala, r"falhou \(500\)"):
            self.f.texto(b"OggS")
        self.ha.rotas["/api/stt/stt.home_assistant_cloud"] = lambda h, c: (200, {"result": "error", "text": ""}) if h.command == "POST" else (200, CLOUD)
        with self.assertRaisesRegex(F.ErroFala, "Não entendi o áudio."):
            self.f.texto(b"OggS")

    def test_microfone_da_tela(self):
        """O microfone da conversa: PCM de 16 kHz, 16 bits, mono, como o Assist; qualquer motor com wav/pcm em 16 kHz."""
        self.ha.rotas["/api/stt/stt.home_assistant_cloud"] = (200, dict(CLOUD, formats=["ogg"], codecs=["opus"]))
        self.ha.rotas["/api/stt/stt.faster_whisper"] = lambda h, c: (200, WHISPER) if h.command == "GET" else (200, {"result": "success", "text": "O que vence esta semana?"})
        self.assertEqual(self.f.status("wav"), {"pronta": True, "nome": "faster-whisper"})
        self.assertEqual(self.f.status()["nome"], "Home Assistant Cloud", "o do WhatsApp continua no Cloud: cada formato tem o seu")
        pcm = bytes(16000 * 2)
        self.assertEqual(self.f.texto(pcm, "wav"), "O que vence esta semana?")
        m, p, h, c = self.ha.pedidos[-1]
        self.assertEqual((m, p, len(c)), ("POST", "/api/stt/stt.faster_whisper", len(pcm)))
        self.assertEqual(h["X-Speech-Content"], "format=wav; codec=pcm; sample_rate=16000; bit_rate=16; channel=1; language=pt")
        with self.assertRaisesRegex(F.ErroFala, "Não ouvi nada"):
            self.f.texto(bytes(1000), "wav")
        with self.assertRaisesRegex(F.ErroFala, "até 2 minutos"):
            self.f.texto(bytes(F.PCM_MAX + 2), "wav")
        self.ha.rotas["/api/stt/stt.faster_whisper"] = (200, dict(WHISPER, sample_rates=[8000]))
        self.f.cache.clear()
        self.assertEqual(self.f.status("wav")["motivo"], "A fala para texto do Home Assistant (Home Assistant Cloud, faster-whisper) não aceita o áudio do microfone.")

    def test_simulada(self):
        f = F.Fala("http://x/api", None, print, simulada=True)
        self.assertTrue(f.status()["pronta"])
        self.assertEqual(f.texto(b"x"), "Quanto gastei com mercado este mês?")
        self.assertTrue(f.status("wav")["pronta"])
        self.assertEqual(f.texto(bytes(32000), "wav"), "O que tem na agenda amanhã?")


if __name__ == "__main__":
    unittest.main()
