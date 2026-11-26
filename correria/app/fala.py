"""Áudio para texto, pela fala para texto do Home Assistant (a mesma do Falar dos outros apps). Igual no CorrerIA e no
OdisseIA (tools/iguais.py): o microfone da Conversa grava em PCM de 16 kHz, 16 bits, mono, como o Assist ("wav"); o WhatsApp
do CorrerIA, em OGG/Opus ("ogg"). O motor do Home Assistant diz o que aceita (GET /api/stt/<motor>); o app usa o escolhido em
Integrações › Falar ou, sem escolha, o primeiro que aceita o formato, começando pelo do Home Assistant Cloud. Só biblioteca
padrão.
"""
import http.client
import json
import time
from urllib.parse import quote, urlparse

PREFERIDOS = ("stt.home_assistant_cloud",)
PCM_TAXA = 16000
PCM_MIN = PCM_TAXA * 2 * 0.4    # menos de 0,4 s: nada foi dito
PCM_MAX = PCM_TAXA * 2 * 125    # um pouco mais de 2 minutos


class ErroFala(Exception):
    pass


class Fala:
    def __init__(self, rest, token, log, simulada=False, exemplo=None):
        """simulada: fora do Home Assistant (no computador e nos testes), com dois motores de mentira; exemplo: o texto que
        ela ouve (sem ele, uma pergunta do CorrerIA, uma para o WhatsApp e outra para o microfone)."""
        self.rest, self.token, self.log, self.simulada, self.exemplo = rest.rstrip("/"), token, log, simulada, exemplo
        self.cache = {}

    def _pedir(self, metodo, caminho, corpo=None, cab=None, timeout=15):
        u = urlparse(self.rest)
        c = (http.client.HTTPSConnection if u.scheme == "https" else http.client.HTTPConnection)(u.hostname, u.port, timeout=timeout)
        try:
            # o proxy do Supervisor só repassa o "X-Speech-Content" escrito assim: os cabeçalhos vão à mão
            c.putrequest(metodo, u.path.rstrip("/") + caminho, skip_accept_encoding=True)
            c.putheader("Authorization", f"Bearer {self.token}")
            for k, v in (cab or {}).items():
                c.putheader(k, v)
            if corpo is not None:
                c.putheader("Content-Length", str(len(corpo)))
            c.endheaders()
            if corpo is not None:
                c.send(corpo)
            r = c.getresponse()
            return r.status, r.read()
        finally:
            c.close()

    def motor(self, formato="ogg", escolha=""):
        """{id, nome, idioma, taxa} do motor que aceita o áudio ("ogg": o do WhatsApp; "wav": o do microfone da tela), ou
        {motivo} quando nenhum aceita. escolha (a Fala para texto de Integrações › Falar): esse motor, se ele está no Home
        Assistant e aceita o áudio; senão, o automático (o primeiro, começando pelo do Home Assistant Cloud)."""
        r = self.todos(formato)
        if not r.get("lista"):
            return {"motivo": r["motivo"]}
        return next((m for m in r["lista"] if escolha and m["id"] == escolha), r["lista"][0])

    def todos(self, formato="ogg"):
        """{lista: os motores que aceitam o áudio, o automático primeiro} ou {lista: [], motivo}. Guardado por 5 minutos."""
        if self.simulada:
            return {"lista": [{"id": "stt.simulada", "nome": "Fala simulada (teste)", "idioma": "pt-BR", "taxa": 16000},
                              {"id": "stt.outra_simulada", "nome": "Outra fala simulada", "idioma": "pt-BR", "taxa": 16000}]}
        guardado = self.cache.get(formato)
        if guardado and time.time() - guardado[0] < 300:
            return guardado[1]
        r = self._achar(formato)
        self.cache[formato] = (time.time(), r)
        return r

    def _achar(self, formato):
        if not self.token:
            return {"lista": [], "motivo": "Fora do Home Assistant não há fala para texto."}
        try:
            st, corpo = self._pedir("GET", "/states")
            estados = json.loads(corpo) if st == 200 else []
        except (OSError, http.client.HTTPException, ValueError) as e:
            return {"lista": [], "motivo": f"Não consegui falar com o Home Assistant ({e})."}
        ents = [e for e in estados if isinstance(e, dict) and str(e.get("entity_id", "")).startswith("stt.")]
        if not ents:
            return {"lista": [], "motivo": "O Home Assistant não tem fala para texto (Configurações › Assistentes de voz)."}
        ents.sort(key=lambda e: (e["entity_id"] not in PREFERIDOS, e["entity_id"]))
        nomes, lista = [], []
        for e in ents:
            nome = (e.get("attributes") or {}).get("friendly_name") or e["entity_id"]
            nomes.append(nome)
            try:
                st, corpo = self._pedir("GET", "/stt/" + quote(e["entity_id"]))
                info = json.loads(corpo) if st == 200 else {}
            except (OSError, http.client.HTTPException, ValueError):
                continue
            taxas = info.get("sample_rates") or [16000]
            if formato == "wav":
                if "wav" not in (info.get("formats") or []) or "pcm" not in (info.get("codecs") or []) or PCM_TAXA not in taxas:
                    continue
            elif "ogg" not in (info.get("formats") or []) or "opus" not in (info.get("codecs") or []):
                continue
            langs = info.get("languages") or []
            idioma = "pt-BR" if "pt-BR" in langs else next((x for x in langs if str(x).lower().startswith("pt")), langs[0] if langs else "pt-BR")
            taxa = 16000 if 16000 in taxas else 48000 if 48000 in taxas else taxas[0]
            lista.append({"id": e["entity_id"], "nome": nome, "idioma": idioma, "taxa": taxa})
        if lista:
            return {"lista": lista}
        de = "do microfone" if formato == "wav" else "do WhatsApp (OGG)"
        return {"lista": [], "motivo": f"A fala para texto do Home Assistant ({', '.join(nomes)}) não aceita o áudio {de}."}

    def status(self, formato="ogg", escolha=""):
        """Pronta ou o motivo; com a lista para escolher, o automático (o nome do primeiro) e se a escolhida sumiu."""
        r = self.todos(formato)
        if not r.get("lista"):
            return {"pronta": False, "motivo": r["motivo"], "opcoes": []}
        m = self.motor(formato, escolha)
        return {"pronta": True, "nome": m["nome"], "automatico": r["lista"][0]["nome"],
                "opcoes": [{"id": x["id"], "nome": x["nome"]} for x in r["lista"]],
                "escolha_sumiu": bool(escolha) and m["id"] != escolha}

    def texto(self, audio, formato="ogg", escolha=""):
        """O áudio em texto: o do WhatsApp (OGG/Opus) ou o do microfone da tela ("wav": PCM de 16 kHz, 16 bits, mono)."""
        if formato == "wav":
            if len(audio) < PCM_MIN:
                raise ErroFala("Não ouvi nada. Toque no microfone e fale.")
            if len(audio) > PCM_MAX:
                raise ErroFala("Fale até 2 minutos de cada vez.")
        m = self.motor(formato, escolha)
        if not m.get("id"):
            raise ErroFala(m["motivo"])
        if self.simulada:
            return self.exemplo or ("O que tem na agenda amanhã?" if formato == "wav" else "Quanto gastei com mercado este mês?")
        fmt = f"format=wav; codec=pcm; sample_rate={PCM_TAXA}" if formato == "wav" else f"format=ogg; codec=opus; sample_rate={m['taxa']}"
        cab = {"Content-Type": "application/octet-stream",
               "X-Speech-Content": f"{fmt}; bit_rate=16; channel=1; language={m['idioma']}"}
        try:
            st, corpo = self._pedir("POST", "/stt/" + quote(m["id"]), audio, cab, timeout=90)
        except (OSError, http.client.HTTPException) as e:
            raise ErroFala(f"A fala para texto do Home Assistant não respondeu ({e}).") from None
        if not 200 <= st < 300:
            self.cache.pop(formato, None)
            self.log(f"Fala para texto ({m['id']}): {st} {corpo[:200]!r}")
            raise ErroFala("A fala para texto não aceitou o áudio." if st in (400, 415) else f"A fala para texto do Home Assistant falhou ({st}).")
        try:
            j = json.loads(corpo)
        except ValueError:
            j = {}
        txt = str(j.get("text") or "").strip()
        if j.get("result") != "success" or not txt:
            raise ErroFala("Não entendi o áudio.")
        return txt
