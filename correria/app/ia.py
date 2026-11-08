"""A IA do CorrerIA no WhatsApp e na conversa da tela: a IA do Home Assistant (ai_task.generate_data) com as ferramentas
de todos os apps. Ela lê (chama as ferramentas de leitura e responde com os resultados) e propõe mudanças (as de
gravar): o CorrerIA mostra o que vai ser feito e só faz depois do "sim" da pessoa (server.py guarda o pendente).

O pedido à IA vai em texto (as ferramentas, a conversa e os resultados) e ela devolve JSON:
{"chamar": [{"ferramenta", "argumentos", "resumo"}], "resposta": ""}. Até RODADAS idas e voltas por mensagem."""
import json
import re
from datetime import datetime

import ferramentas as F

RODADAS = 4
MAX_CHAMADAS = 4          # de leitura, por rodada
MAX_RESULTADO = 8000      # o texto de cada resultado que volta para a IA
DIAS = ("segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo")

BASE = """Você é o CorrerIA, o assistente dos apps da CorrerIA Code, {onde}. Quem está conversando: {nome}. Agora: {agora}.
Converse em português do Brasil, curto e direto, como no WhatsApp: frases simples, no máximo uns 4 parágrafos curtos. Formatação do WhatsApp: *negrito* com um asterisco de cada lado e listas com "- "; nada de tabelas, títulos nem links. Valores como R$ 1.234,56 e datas como 20/11.
{assunto}
Use as ferramentas para ver os dados de verdade antes de responder: não invente números, nomes nem itens. Se faltar o dado, diga o que falta. Contas de cabeça podem errar: some e compare com cuidado.
Para mudar algo (ferramentas marcadas "grava"), não peça confirmação no texto: ponha a ação em "chamar", com um "resumo" curto e claro do que vai ser feito (ex.: "Lançar R$ 45,90 de Mercado hoje, no cartão do Banco Azul"); o CorrerIA mostra para a pessoa e só faz depois do sim dela. Faça só o que ela pediu. Se faltar um dado essencial (o valor, a data, qual item), pergunte antes. Para achar os ids, leia primeiro."""

ASSUNTO_WHATSAPP = "Por aqui você só ajuda com os apps: para qualquer outro assunto, diga numa frase, com gentileza, que pelo WhatsApp você ajuda só com os apps da CorrerIA Code."
ASSUNTO_TELA = "Ajude com os apps; também pode conversar sobre outros assuntos."

FORMATO = """Responda somente com JSON válido, sem markdown e sem texto antes ou depois, neste formato:
{"chamar":[{"ferramenta":"","argumentos":{},"resumo":""}],"resposta":""}
- Para ler: as ferramentas em "chamar" (até 4) e "resposta" vazia; você recebe os resultados e responde depois.
- Para mudar: as ações em "chamar", cada uma com "resumo"; em "resposta", no máximo uma frase.
- Com o que precisa: "chamar" vazio e a resposta em "resposta"."""


class ErroIA(Exception):
    pass


def _agora_txt(agora):
    return f"{DIAS[agora.weekday()]}, {agora:%d/%m/%Y %H:%M}"


def catalogo(lista):
    linhas = []
    for f in lista:
        ent = json.dumps(f["entrada"].get("properties") or {}, ensure_ascii=False, separators=(",", ":"))
        obrig = f["entrada"].get("required") or []
        linhas.append(f"{f['id']} | {'grava' if f['grava'] else 'lê'} | {f['app']['nome']}: {f['descricao']} | entrada: {ent}"
                      + (f" | obrigatórios: {', '.join(obrig)}" if obrig else ""))
    return "\n".join(linhas)


def extrair_json(t):
    """O JSON da resposta da IA (às vezes vem com ```json ou texto em volta)."""
    if isinstance(t, dict):
        return t
    s = str(t or "").strip()
    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", s)
    try:
        v = json.loads(s)
        return v if isinstance(v, dict) else {"resposta": s}
    except ValueError:
        pass
    i, j = s.find("{"), s.rfind("}")
    if 0 <= i < j:
        try:
            v = json.loads(s[i:j + 1])
            if isinstance(v, dict):
                return v
        except ValueError:
            pass
    return {"resposta": s}


class Agente:
    def __init__(self, ferramentas, chamar_ia, log, simulada=False):
        self.ferr, self.chamar_ia, self.log, self.simulada = ferramentas, chamar_ia, log, simulada

    def instrucoes(self, lista, historico, pessoa, canal, resultados, agora, ultima=False):
        nome = (pessoa or {}).get("nome") or "alguém da casa"
        partes = [BASE.format(onde="pelo WhatsApp" if canal == "whatsapp" else "na tela do app CorrerIA", nome=nome, agora=_agora_txt(agora),
                              assunto=ASSUNTO_WHATSAPP if canal == "whatsapp" else ASSUNTO_TELA)]
        apps = self.ferr.instrucoes()
        if apps:
            partes.append("Os apps:\n" + apps)
        partes.append("Ferramentas (nome | lê ou grava | o que faz | entrada):\n" + catalogo(lista))
        conversa = [("IA: " if m.get("papel") == "ia" else "Pessoa: ") + str(m.get("texto") or "").strip()[:2000]
                    for m in historico if str(m.get("texto") or "").strip()]
        partes.append("A conversa (a última mensagem é a que você responde agora):\n" + "\n".join(conversa))
        if resultados:
            partes.append("Resultados das ferramentas que você chamou agora:\n" + "\n\n".join(resultados))
        if ultima:
            partes.append("Agora responda com o que já tem, sem chamar mais ferramentas de leitura.")
        partes.append(FORMATO)
        return "\n\n".join(partes)

    def responder(self, historico, pessoa, canal="whatsapp", cliente="WhatsApp", agora=None):
        """historico termina com a mensagem da pessoa. Devolve {resposta, pendente: [ações] ou [], apps: [nomes]}."""
        agora = agora or datetime.now()
        lista = self.ferr.todas()
        resultados, usados = [], []
        for rodada in range(RODADAS):
            ultima = rodada == RODADAS - 1
            if self.simulada:
                bruto = simulado(historico[-1]["texto"] if historico else "", lista, resultados)
            else:
                bruto = self.chamar_ia(self.instrucoes(lista, historico, pessoa, canal, resultados, agora, ultima))
            r = extrair_json(bruto)
            texto = str(r.get("resposta") or r.get("texto") or "").strip()[:4000]
            chamadas = [c for c in (r.get("chamar") or []) if isinstance(c, dict)] if isinstance(r.get("chamar"), list) else []
            achadas, desconhecidas = [], []
            for c in chamadas:
                f = self.ferr.achar(str(c.get("ferramenta") or c.get("nome") or ""), lista)
                (achadas if f else desconhecidas).append((f, c))
            gravar = [(f, c) for f, c in achadas if f["grava"]]
            if gravar:
                pend = [{"ferramenta": f["id"], "argumentos": c.get("argumentos") if isinstance(c.get("argumentos"), dict) else {},
                         "resumo": str(c.get("resumo") or "").strip()[:200] or f"{f['titulo']}: {F.resumo_args(c.get('argumentos'))}", "app": f["app"]["nome"]}
                        for f, c in gravar[:8]]
                linhas = "\n".join(f"- {p['resumo']}" for p in pend)
                frase = (texto + "\n\n") if texto else ""
                return {"resposta": f"{frase}Vou fazer {'isto' if len(pend) == 1 else 'isto tudo'}:\n{linhas}\n\nResponda *sim* para confirmar.",
                        "pendente": pend, "apps": sorted({p["app"] for p in pend} | set(usados))}
            ler = [(f, c) for f, c in achadas if not f["grava"]][:MAX_CHAMADAS]
            if (ler or desconhecidas) and not ultima:
                for f, c in ler:
                    args = c.get("argumentos") if isinstance(c.get("argumentos"), dict) else {}
                    res, erro = self.ferr.usar(f, args, pessoa, cliente)
                    if f["app"]["nome"] not in usados:
                        usados.append(f["app"]["nome"])
                    resultados.append(f"{f['id']}({json.dumps(args, ensure_ascii=False)}) → {'ERRO: ' if erro else ''}{res[:MAX_RESULTADO]}")
                for _, c in desconhecidas:
                    resultados.append(f"{c.get('ferramenta') or c.get('nome')} → ERRO: essa ferramenta não existe. Use só as da lista.")
                continue
            if texto:
                return {"resposta": texto, "pendente": [], "apps": usados}
            if ultima:
                break
        return {"resposta": "Não consegui responder agora. Pode perguntar de outro jeito?", "pendente": [], "apps": usados}


# ---------------------------------------------------------------- a IA simulada (no computador, sem o Home Assistant)

def simulado(texto, lista, resultados):
    """Previsível, para testar o caminho todo sem IA: lançar (gerencia_lancar), o resumo de um app e responder."""
    t = (texto or "").lower()
    ids = {f["id"] for f in lista}
    if resultados:
        primeiras = "\n".join(resultados[-1].split("→", 1)[-1].strip().splitlines()[:6])
        return {"resposta": f"Pelo que vi:\n{primeiras}"}
    m = re.search(r"\b(?:lan[cç]a|gastei)\s+(?:r\$\s*)?(\d+(?:[.,]\d{1,2})?)\s*(?:reais\s*)?(?:de|no|na|em)?\s*([a-zà-ú]+)?", t)
    if m and "gerencia_lancar" in ids:
        valor = float(m.group(1).replace(",", "."))
        desc = (m.group(2) or "gasto").capitalize()
        return {"chamar": [{"ferramenta": "gerencia_lancar", "argumentos": {"tipo": "despesa", "descricao": desc, "valor": valor},
                            "resumo": f"Lançar R$ {valor:.2f} de {desc} hoje".replace(".", ",")}]}
    resumo = next((f["id"] for f in lista if f["id"].endswith("_resumo")), None)
    if resumo and re.search(r"\?|quanto|qual|quais|tem |o que", t):
        return {"chamar": [{"ferramenta": resumo, "argumentos": {}}], "resposta": ""}
    return {"resposta": "Oi! Sou o CorrerIA (IA simulada). Pergunte sobre os apps."}
