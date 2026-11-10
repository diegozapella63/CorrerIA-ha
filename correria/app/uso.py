"""Uso da IA (como nos outros apps da família): o Home Assistant não devolve tokens nem custo, então o CorrerIA conta as
próprias chamadas a ai_task.generate_data e estima os tokens pelo tamanho do texto (uns 4 caracteres por token).
Fica em /data/uso_ia.json (os totais de 120 dias e as últimas 40 chamadas) e aparece em Configurações › Apps › Uso da IA.
Tipos: whatsapp (as mensagens do WhatsApp) e conversa (a conversa da tela)."""
import json
import os
import re
import threading
from datetime import date, datetime, timedelta

DIAS = 120
ULTIMAS = 40
CONTAS = ("chamadas", "erros", "cota", "tokens", "segundos")


def resultado(erro):
    """ok | cota (sem cota ou limite de pedidos) | formato (a resposta não era o JSON esperado) | erro."""
    if not erro:
        return "ok"
    m = str(erro)
    if re.search(r"quota|cota|429|resource[_ ]?exhausted|rate.?limit|too many requests", m, re.I):
        return "cota"
    if re.search(r"json|formato|unexpected token|parse", m, re.I):
        return "formato"
    return "erro"


class Uso:
    def __init__(self, arquivo):
        self.arquivo = arquivo
        self.trava = threading.Lock()

    def ler(self):
        try:
            with open(self.arquivo, encoding="utf-8") as f:
                u = json.load(f)
            return u if isinstance(u, dict) else {}
        except (OSError, ValueError):
            return {}

    def registrar(self, tipo, entrada=0, saida=0, segundos=0.0, erro=None, agora=None):
        """Uma chamada: o tipo, os caracteres que foram e voltaram, quanto tempo levou e como terminou."""
        agora = agora or datetime.now()
        res = resultado(erro)
        tokens = round((int(entrada) + int(saida)) / 4)
        with self.trava:
            u = self.ler()
            dias = u["dias"] if isinstance(u.get("dias"), dict) else {}
            d = dias.setdefault(agora.date().isoformat(), {})
            soma = {"chamadas": 1, "tokens": tokens, "segundos": round(segundos, 1), "erros": 0 if res in ("ok", "cota") else 1, "cota": 1 if res == "cota" else 0}
            for k, v in soma.items():
                d[k] = round((d.get(k) or 0) + v, 1)
            d.setdefault("tipos", {})
            d["tipos"][tipo] = d["tipos"].get(tipo, 0) + 1
            for velho in sorted(dias)[:-DIAS]:
                del dias[velho]
            u["dias"] = dias
            ult = u["ultimas"] if isinstance(u.get("ultimas"), list) else []
            u["ultimas"] = ([{"quando": agora.isoformat(timespec="seconds"), "tipo": tipo, "resultado": res, "segundos": round(segundos, 1), "tokens": tokens}] + ult)[:ULTIMAS]
            tmp = self.arquivo + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(u, f, ensure_ascii=False)
            os.replace(tmp, self.arquivo)

    def resumo(self, hoje=None):
        """Hoje, os últimos 7 dias, este mês, os 7 dias um a um e as últimas chamadas."""
        hoje = hoje or date.today()
        u = self.ler()
        dias = u.get("dias") if isinstance(u.get("dias"), dict) else {}
        semana = [(hoje - timedelta(days=i)).isoformat() for i in range(6, -1, -1)]

        def soma(chaves):
            t = {k: 0 for k in CONTAS}
            t["tipos"] = {}
            for k in chaves:
                d = dias.get(k) or {}
                for c in CONTAS:
                    t[c] = round(t[c] + (d.get(c) or 0), 1)
                for n, v in (d.get("tipos") or {}).items():
                    t["tipos"][n] = t["tipos"].get(n, 0) + v
            return t

        mes = hoje.isoformat()[:7]
        return {
            "hoje": soma([hoje.isoformat()]),
            "semana": soma(semana),
            "mes": soma([k for k in dias if k[:7] == mes]),
            "dias": [{"dia": k, "chamadas": (dias.get(k) or {}).get("chamadas", 0), "erros": (dias.get(k) or {}).get("erros", 0)} for k in semana],
            "ultimas": (u.get("ultimas") if isinstance(u.get("ultimas"), list) else [])[:12],
        }
