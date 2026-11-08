"""Os apps da família que respondem pelo CorrerIA. Cada um, com a opção ligada nele, grava share/<app>/correria.json
({app, nome, assunto, rota, url, ip_url, chave}); o CorrerIA acha esses arquivos, escolhe o app da pergunta e chama
POST <url><rota> com Authorization: Bearer <chave> e {texto, historico, pessoa} → {resposta}."""
import glob
import json
import os
import re
import time
import unicodedata
import urllib.error
import urllib.request

ARQUIVO = "correria.json"

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


class Apps:
    def __init__(self, share_dir, log, cache=60):
        self.share_dir, self.log, self.cache = share_dir, log, cache
        self._lista, self._quando = [], 0.0

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
            out.append({"app": str(a.get("app") or pasta), "nome": str(a.get("nome") or pasta), "assunto": str(a.get("assunto") or ""),
                        "rota": str(a.get("rota") or "/api/integracao/conversa"), "url": str(a["url"]).rstrip("/"),
                        "ip_url": str(a.get("ip_url") or "").rstrip("/"), "chave": str(a["chave"]), "versao": str(a.get("versao") or ""),
                        "anexos": [str(t).lower() for t in a.get("anexos") or [] if isinstance(t, str)]})
        self._lista, self._quando = out, time.time()
        return out

    def publicos(self):
        """O que a tela vê (sem a chave)."""
        return [{k: a[k] for k in ("app", "nome", "assunto", "versao", "anexos")} for a in self.lista(forcar=True)]

    def escolher(self, texto, ultimo=None, tipo=None):
        """O app da pergunta: um só, ele; mais de um, o que tiver mais palavras do assunto dele na pergunta; empate ou
        nenhuma, o da última pergunta dessa pessoa; senão, o primeiro. Com um anexo (tipo), só os apps que leem esse tipo."""
        apps = [a for a in self.lista() if not tipo or tipo in a["anexos"]]
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

    def perguntar(self, app, texto, historico, pessoa, timeout=150, anexo=None, canal="whatsapp"):
        """Pergunta ao app e devolve o texto da resposta. Tenta o nome do app na rede interna e depois o IP. anexo:
        {tipo, nome, b64} (uma foto ou um PDF, em data URL), para os apps que leem esse tipo. canal: de onde veio a
        pergunta (whatsapp, ou correria: a conversa na tela do CorrerIA)."""
        corpo = json.dumps({"texto": texto, "historico": historico, "pessoa": pessoa, "canal": canal, **({"anexo": anexo} if anexo else {})}).encode()
        ultimo_erro = None
        for base in [app["url"]] + ([app["ip_url"]] if app.get("ip_url") else []):
            req = urllib.request.Request(base + app["rota"], data=corpo, method="POST",
                                         headers={"Authorization": f"Bearer {app['chave']}", "X-App": "CorrerIA", "Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    resp = json.loads(r.read() or b"{}")
                return str(resp.get("resposta") or "").strip() or "Não entendi. Pode dizer de outro jeito?"
            except urllib.error.HTTPError as e:
                try:
                    msg = json.loads(e.read() or b"{}").get("erro")
                except ValueError:
                    msg = None
                if e.code == 401:
                    self._quando = 0  # a chave mudou: lê os arquivos de novo na próxima
                    raise ErroApp(f"O {app['nome']} recusou a chave. Confira se a opção do CorrerIA está ligada nele.") from None
                raise ErroApp(msg or f"O {app['nome']} respondeu {e.code}.") from None
            except (urllib.error.URLError, OSError, ValueError) as e:
                ultimo_erro = e
        raise ErroApp(f"Não consegui falar com o {app['nome']} ({getattr(ultimo_erro, 'reason', ultimo_erro)}).")
