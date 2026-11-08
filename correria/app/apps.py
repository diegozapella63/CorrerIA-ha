"""Os apps da família ligados ao CorrerIA. Cada um, com a opção ligada nele, grava share/<app>/correria.json
({app, nome, assunto, url, ip_url, chave, ferramentas?, rota?, anexos?}); o CorrerIA acha esses arquivos e, com
Authorization: Bearer <chave> e X-App: CorrerIA:
- ferramentas: GET <url><ferramentas> → {instrucoes, ferramentas: [{nome, titulo, descricao, entrada, grava, apaga}]} e
  POST {nome, argumentos, pessoa, cliente} → {texto} (400 {erro}: argumento inválido, a IA tenta de novo);
- rota (só quem responde com a IA dele, hoje o GerencIA, para fotos e PDFs): POST {texto, historico, pessoa, canal,
  anexo?} → {resposta}."""
import glob
import json
import os
import re
import time
import unicodedata
import urllib.error
import urllib.request

ARQUIVO = "correria.json"
APP_RE = re.compile(r"^[a-z0-9]{1,20}$")
NOME_RE = re.compile(r"^[a-z0-9_]{1,40}$")
MAX_FERRAMENTAS = 40   # de cada app
MAX_TEXTO = 60000      # o resultado de uma ferramenta

# o que é de cada app (para escolher quando houver mais de um); o "assunto" do arquivo também conta
PALAVRAS = {
    "gerencia": "gasto gastei gastos paguei pagar conta contas fatura faturas cartao saldo dinheiro real reais investimento investimentos "
                "rende rendimento patrimonio salario recebi recebimento mercado banco despesa despesas caixa compra compras boleto pix",
    "cronologia": "agenda compromisso evento remedio remedios rotina lembrete consulta aniversario calendario amanha semana horario",
    "resolvia": "tarefa tarefas lista listas fazer pendente pontos limpar",
    "inventario": "item itens comodo comodos inventario seguro garantia equipamento",
    "memoria": "anotacao anotacoes nota notas folha folhas bloco caderno",
}


def _sem_acento(t):
    return "".join(c for c in unicodedata.normalize("NFD", str(t or "")) if unicodedata.category(c) != "Mn").lower()


class ErroApp(Exception):
    pass


class ErroFerramenta(Exception):
    """O app recusou os argumentos (400): a mensagem diz o que vale, e a IA pode tentar de novo."""


class Apps:
    def __init__(self, share_dir, log, cache=60):
        self.share_dir, self.log, self.cache = share_dir, log, cache
        self._lista, self._quando = [], 0.0
        self._ferr = {}  # app -> (quando, chave, {instrucoes, ferramentas})

    def lista(self, forcar=False):
        """Os apps que estão respondendo agora: [{app, nome, assunto, rota, url, ip_url, chave}], em ordem de nome."""
        if not forcar and time.time() - self._quando < self.cache:
            return self._lista
        out = []
        for arq in sorted(glob.glob(os.path.join(self.share_dir, "*", ARQUIVO))):
            try:
                with open(arq, encoding="utf-8") as f:
                    a = json.load(f)
            except (OSError, ValueError) as e:
                self.log("Não consegui ler", arq, e)
                continue
            if not isinstance(a, dict) or not a.get("url") or not a.get("chave"):
                continue
            pasta = os.path.basename(os.path.dirname(arq))
            app = str(a.get("app") or pasta).lower()
            if not APP_RE.match(app):
                self.log("App com nome inválido em", arq)
                continue
            rota = str(a.get("rota") or "")
            out.append({"app": app, "nome": str(a.get("nome") or pasta), "assunto": str(a.get("assunto") or ""),
                        "rota": rota if rota.startswith("/") else "", "url": str(a["url"]).rstrip("/"),
                        "ferramentas": str(a.get("ferramentas") or "") if str(a.get("ferramentas") or "").startswith("/") else "",
                        "ip_url": str(a.get("ip_url") or "").rstrip("/"), "chave": str(a["chave"]), "versao": str(a.get("versao") or ""),
                        "anexos": [str(t).lower() for t in a.get("anexos") or [] if isinstance(t, str)] if rota else []})
        self._lista, self._quando = out, time.time()
        return out

    def publicos(self):
        """O que a tela vê (sem a chave)."""
        return [dict({k: a[k] for k in ("app", "nome", "assunto", "versao", "anexos")}, conversa=bool(a["rota"]))
                for a in self.lista(forcar=True)]

    def escolher(self, texto, ultimo=None, tipo=None):
        """O app da pergunta (entre os que respondem com a IA dele: rota): um só, ele; mais de um, o que tiver mais
        palavras do assunto dele na pergunta; empate ou nenhuma, o da última pergunta dessa pessoa; senão, o primeiro.
        Com um anexo (tipo), só os apps que leem esse tipo."""
        apps = [a for a in self.lista() if a["rota"] and (not tipo or tipo in a["anexos"])]
        if not apps:
            return None
        if len(apps) == 1:
            return apps[0]
        palavras = set(re.findall(r"[a-z]+", _sem_acento(texto)))

        def pontos(a):
            vocab = set(PALAVRAS.get(a["app"], "").split()) | set(re.findall(r"[a-z]{4,}", _sem_acento(a["assunto"])))
            return len(palavras & vocab)
        notas = sorted(((pontos(a), a) for a in apps), key=lambda x: -x[0])
        if notas[0][0] > 0 and (len(notas) == 1 or notas[0][0] > notas[1][0]):
            return notas[0][1]
        return next((a for a in apps if a["app"] == ultimo), apps[0])

    def _pedir(self, app, rota, corpo=None, timeout=60, ferramenta=False):
        """GET (sem corpo) ou POST no app, com a chave. Tenta o nome do app na rede interna e depois o IP. Com
        ferramenta, um 400 vira ErroFerramenta (a IA vê o erro e pode tentar de novo)."""
        dados = json.dumps(corpo).encode() if corpo is not None else None
        ultimo_erro = None
        for base in [app["url"]] + ([app["ip_url"]] if app.get("ip_url") else []):
            req = urllib.request.Request(base + rota, data=dados, method="POST" if dados is not None else "GET",
                                         headers={"Authorization": f"Bearer {app['chave']}", "X-App": "CorrerIA", "Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    v = json.loads(r.read() or b"{}")
                return v if isinstance(v, dict) else {}
            except urllib.error.HTTPError as e:
                try:
                    msg = json.loads(e.read() or b"{}").get("erro")
                except (ValueError, AttributeError):
                    msg = None
                if e.code == 401:
                    self._quando = 0  # a chave mudou: lê os arquivos de novo na próxima
                    self._ferr.pop(app["app"], None)
                    raise ErroApp(f"O {app['nome']} recusou a chave. Confira se a opção do CorrerIA está ligada nele.") from None
                if ferramenta and e.code in (400, 404) and msg:
                    raise ErroFerramenta(str(msg)[:2000]) from None
                raise ErroApp(msg or f"O {app['nome']} respondeu {e.code}.") from None
            except (urllib.error.URLError, OSError, ValueError) as e:
                ultimo_erro = e
        raise ErroApp(f"Não consegui falar com o {app['nome']} ({getattr(ultimo_erro, 'reason', ultimo_erro)}).")

    def perguntar(self, app, texto, historico, pessoa, timeout=150, anexo=None, canal="whatsapp"):
        """Pergunta ao app (pela rota, com a IA dele) e devolve o texto da resposta. anexo: {tipo, nome, b64} (uma foto
        ou um PDF, em data URL), para os apps que leem esse tipo. canal: de onde veio a pergunta (whatsapp, ou
        correria: a conversa na tela do CorrerIA, o Claude ou o Gemini)."""
        if not app.get("rota"):
            raise ErroApp(f"O {app['nome']} não responde perguntas, só pelas ferramentas.")
        corpo = {"texto": texto, "historico": historico, "pessoa": pessoa, "canal": canal, **({"anexo": anexo} if anexo else {})}
        resp = self._pedir(app, app["rota"], corpo, timeout=timeout)
        return str(resp.get("resposta") or "").strip() or "Não entendi. Pode dizer de outro jeito?"

    def ferramentas(self, app, cache=60):
        """As ferramentas do app: {instrucoes, ferramentas: [{nome, titulo, descricao, entrada, grava, apaga}]}, só as
        bem formadas. Guarda por um tempo (a lista muda só quando o app atualiza)."""
        if not app.get("ferramentas"):
            return {"instrucoes": "", "ferramentas": []}
        guardado = self._ferr.get(app["app"])
        if guardado and guardado[1] == app["chave"] and time.time() - guardado[0] < cache:
            return guardado[2]
        r = self._pedir(app, app["ferramentas"], timeout=15)
        lista, vistos = [], set()
        for f in r.get("ferramentas") or []:
            if not isinstance(f, dict) or not NOME_RE.match(str(f.get("nome") or "")) or f["nome"] in vistos:
                continue
            entrada = f.get("entrada") if isinstance(f.get("entrada"), dict) and f["entrada"].get("type") == "object" else {"type": "object", "properties": {}}
            vistos.add(f["nome"])
            lista.append({"nome": f["nome"], "titulo": str(f.get("titulo") or f["nome"])[:80], "descricao": str(f.get("descricao") or "")[:1500],
                          "entrada": entrada, "grava": f.get("grava") is True, "apaga": f.get("apaga") is True})
        v = {"instrucoes": str(r.get("instrucoes") or "")[:1500], "ferramentas": lista[:MAX_FERRAMENTAS]}
        self._ferr[app["app"]] = (time.time(), app["chave"], v)
        return v

    def usar(self, app, nome, argumentos, pessoa, cliente, timeout=60):
        """Chama uma ferramenta do app; devolve o texto do resultado (ErroFerramenta: argumento inválido)."""
        r = self._pedir(app, app["ferramentas"], {"nome": nome, "argumentos": argumentos if isinstance(argumentos, dict) else {},
                                                  "pessoa": pessoa or {}, "cliente": cliente}, timeout=timeout, ferramenta=True)
        return str(r.get("texto") if r.get("texto") is not None else json.dumps(r, ensure_ascii=False))[:MAX_TEXTO]
