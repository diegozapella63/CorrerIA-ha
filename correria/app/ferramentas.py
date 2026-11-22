"""As ferramentas de todos os apps, juntas: cada app publica as suas (apps.Apps.ferramentas) e aqui elas ganham
o nome com o app na frente (gerencia_lancar), para o MCP (Claude e Gemini) e para a IA do WhatsApp. Um app que só
responde com a IA dele (rota, sem ferramentas) vira uma ferramenta <app>_perguntar."""
import re

import apps as A
import casa as C

PERGUNTAR = "__perguntar"


class Ferramentas:
    def __init__(self, apps, log, casa=None):
        self._apps, self.log = apps, log  # apps: um apps.Apps (ou uma função que o devolve)
        self._casa = casa  # 1.5.0: a casa do Home Assistant (casa.Casa), ou uma função que a devolve (None: desligada)
        self.erros = {}  # app -> a última falha ao listar (para a tela)

    @property
    def apps(self):
        return self._apps() if callable(self._apps) else self._apps

    @property
    def casa(self):
        return self._casa() if callable(self._casa) else self._casa

    def tem(self):
        """Alguma ferramenta: um app com ferramentas ou a casa ligada."""
        return bool(self.casa) or any(a["ferramentas"] for a in self.apps.lista())

    def todas(self):
        """[{id: "gerencia_lancar", app: {...}, nome, titulo, descricao, entrada, grava, apaga}] de todos os apps ligados."""
        out = []
        for app in self.apps.lista():
            if app["ferramentas"]:
                try:
                    lista = self.apps.ferramentas(app)["ferramentas"]
                    self.erros.pop(app["app"], None)
                except A.ErroApp as e:
                    self.erros[app["app"]] = str(e)
                    self.log("Ferramentas:", e)
                    continue
                out += [dict(f, id=f"{app['app']}_{f['nome']}", app=app) for f in lista]
            elif app["rota"]:
                out.append({"id": f"{app['app']}_perguntar", "app": app, "nome": PERGUNTAR, "titulo": f"Perguntar ao {app['nome']}",
                            "descricao": f"Faz uma pergunta ao {app['nome']} ({app['assunto'] or 'um app da CorrerIA Code'}); ele responde com a IA dele, com os dados dele.",
                            "entrada": {"type": "object", "properties": {"pergunta": {"type": "string"}}, "required": ["pergunta"], "additionalProperties": False},
                            "grava": False, "apaga": False})
        if self.casa:
            out += [dict(f, id=f"{C.ID}_{f['nome']}", app=C.APP) for f in C.FERRAMENTAS]
        return out

    def instrucoes(self):
        """Uma linha por app: o que ele é e as dicas dele. 1.16.0: e o contexto todo da família, para a IA saber de qual
        app a pessoa fala: os ligados que não responderam agora, os que estão com a integração desligada (com o assunto
        de cada um) e que o nome de um app na pergunta é o app, não um item dentro de outro."""
        linhas, mudos = [], []
        for app in self.apps.lista():
            dica = ""
            if app["ferramentas"]:
                try:
                    dica = self.apps.ferramentas(app)["instrucoes"]
                except A.ErroApp:
                    mudos.append(app["nome"])
                    continue
            elif not app["rota"]:
                continue
            linhas.append(f"- {app['nome']}" + (f" ({app['assunto']})" if app["assunto"] else "") + (f": {dica}" if dica else ""))
        if self.casa:
            linhas.append(f"- {C.APP['nome']} ({C.APP['assunto']}): {C.INSTRUCOES}")
        desligados = getattr(self.apps, "desligados", lambda: [])()
        if mudos:
            linhas.append("Ligados, mas sem responder agora (se perguntarem por eles, diga isso): " + ", ".join(mudos) + ".")
        if desligados:
            linhas.append("Apps da família com a integração desligada (você não vê nem muda os dados deles): "
                          + "; ".join(f"{a['nome']} ({a['assunto']})" for a in desligados)
                          + ". Se a pessoa perguntar por um deles ou pelo assunto dele, diga que a integração dele com o CorrerIA está "
                          "desligada e que ela liga no próprio app, em Mais › Configurações › Integrações › CorrerIA. Não procure "
                          "isso nos outros apps.")
        if linhas:
            linhas.append("O nome de um app na pergunta, mesmo em minúsculas, sem acento ou pela metade (resolvia, memória, cronologia, "
                          "gerência, inventário, economia), é o app, nunca um item dentro de outro app. Para \"o que tem no <app>\", "
                          "comece pela ferramenta de resumo ou de lista dele.")
            # 1.16.1: quem procura é a IA (ela respondia "sugiro verificar no InventarIA" em vez de buscar lá)
            linhas.append("Quem procura é você: nunca diga para a pessoa verificar, conferir ou procurar num app que está ligado. "
                          "Chame a ferramenta de busca ou de lista dele e responda com o que achou. Uma pergunta sobre o que a pessoa "
                          "tem, usa ou guardou (\"o que eu tenho para…\", \"tenho algum…\", \"onde está…\") é do inventário: busque lá, "
                          "com mais de uma palavra se a primeira não achar (câmera, tripé, lente, celular). Se o assunto cabe em mais de "
                          "um app, procure em todos antes de responder. Só diga que não achou depois de procurar, e diga onde procurou.")
        return "\n".join(linhas)

    def recebem(self, tipo):
        """1.17.0: os ids dos apps com uma ferramenta que recebe um arquivo desse tipo (uma foto para uma tarefa)."""
        t = str(tipo or "").lower()
        return {f["app"]["app"] for f in self.todas() if t and t in (f.get("anexo") or [])}

    def achar(self, fid, lista=None):
        return next((f for f in (lista if lista is not None else self.todas()) if f["id"] == fid), None)

    def usar(self, f, argumentos, pessoa, cliente, anexo=None, recusa=None):
        """Chama a ferramenta; devolve (texto, erro). erro: o app recusou (argumento inválido) ou não respondeu.
        anexo (1.17.0): a foto que a pessoa mandou há pouco; só vai para a ferramenta que recebe aquele tipo."""
        args = argumentos if isinstance(argumentos, dict) else {}
        if f.get("anexo"):
            if not anexo:
                return "Falta o arquivo: peça para a pessoa mandar (pelo clipe) e tente de novo.", True
            if str(anexo.get("tipo") or "").lower() not in f["anexo"]:  # 1.24.0: o tipo que não serve, dito com as palavras da pessoa
                return f"Esta ferramenta não recebe esse tipo de arquivo ({anexo.get('tipo') or 'desconhecido'}); recebe: {', '.join(f['anexo'])}. Diga isso à pessoa.", True
        else:
            anexo = None
        if f["app"]["app"] == C.ID:
            casa = self.casa
            if not casa:
                return "A casa do Home Assistant está desligada no CorrerIA.", True
            try:
                return casa.usar(f["nome"], args), False
            except C.ErroCasa as e:
                return str(e), True
        try:
            if f["nome"] == PERGUNTAR:
                return self.apps.perguntar(f["app"], str(args.get("pergunta") or "").strip()[:2000] or "Oi", [], pessoa or {}, canal="correria"), False
            return self.apps.usar(f["app"], f["nome"], args, pessoa, cliente, **({"anexo": anexo} if anexo else {})), False
        except A.ErroFerramenta as e:
            if recusa is not None:  # 1.26.0: o app recusou os argumentos (dá para corrigir e tentar de novo)
                recusa.append(True)
            return str(e), True
        except A.ErroApp as e:
            return str(e), True


def resumo_args(args):
    """Os argumentos de uma ação em poucas palavras (quando a IA não mandou o resumo)."""
    partes = []
    for k, v in (args or {}).items():
        if v in (None, "", [], {}):
            continue
        partes.append(f"{k}: {v}" if not isinstance(v, bool) else (k if v else f"sem {k}"))
    return re.sub(r"\s+", " ", ", ".join(partes))[:200]
