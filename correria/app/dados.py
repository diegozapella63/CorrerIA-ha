"""Os Dados do CorrerIA (Configurações › Dados): exportar, o backup na pasta share, importar, as versões anteriores e o
Começar do zero. Um arquivo .zip com os arquivos de /data e um `correria.json` dizendo de que app e de que versão é.

1.29.0 (o dono: "não tem o backup no correria, igual nos outros apps", "pode colocar os segredos e conversas no backup"):
o arquivo leva TUDO, o token da Meta, a chave secreta e as conversas inclusive. Por isso fica com a permissão só do dono
e a tela avisa para guardar como uma senha. Só biblioteca padrão."""
import io
import json
import os
import re
import time
import zipfile

# o que entra, nesta ordem; o que não existe ainda fica de fora
# (o lembrancas.json é de um backup de antes da 1.31.0: ao voltar, o servidor leva as frases para a memória de todos os apps)
ARQUIVOS = ("config.json", "conversas.json", "mcp.json", "rondas.json", "rondas_minhas.json", "lembrancas.json", "uso_ia.json")
# o que o Começar do zero apaga: as conversas, as rondas (o histórico e as criadas ou mudadas) e o Uso da IA.
# Ficam as configurações (o WhatsApp, o endereço, os números, a aparência) e as IAs conectadas. A Memória da IA não é
# daqui (1.31.0: é de todos os apps, na pasta share): não entra no arquivo nem é apagada.
DO_ZERO = ("conversas.json", "rondas.json", "rondas_minhas.json", "uso_ia.json")
MANIFESTO = "correria.json"
MAX_ZIP = 30 * 1024 * 1024       # o arquivo que chega
MAX_ARQUIVO = 25 * 1024 * 1024   # cada arquivo dentro dele, aberto
MAX_BACKUPS, MAX_VERSOES = 10, 3
NOME_RE = re.compile(r"^correria-(\d{4}-\d{2}-\d{2})-(\d{6})(?:-([a-z]+))?\.zip$")
MOTIVOS = {"importar": "antes de importar", "restaurar": "antes de restaurar", "zero": "antes de começar do zero"}


class ErroDados(ValueError):
    """O que dizer à pessoa."""


def montar_zip(data_dir, versao, agora_iso):
    """O .zip com os arquivos que existem em data_dir. Devolve os bytes."""
    saida = io.BytesIO()
    dentro = []
    with zipfile.ZipFile(saida, "w", zipfile.ZIP_DEFLATED) as z:
        for nome in ARQUIVOS:
            try:
                with open(os.path.join(data_dir, nome), "rb") as f:
                    z.writestr(nome, f.read())
                dentro.append(nome)
            except OSError:
                pass
        z.writestr(MANIFESTO, json.dumps({"app": "correria", "nome": "CorrerIA", "versao": versao, "gravado_em": agora_iso, "arquivos": dentro},
                                         ensure_ascii=False))
    return saida.getvalue()


def ler_zip(dados):
    """Confere um .zip do CorrerIA e devolve ({arquivo: texto}, manifesto). ErroDados diz o que há de errado."""
    if not dados or len(dados) > MAX_ZIP:
        raise ErroDados("Arquivo grande demais." if dados else "Escolha o arquivo do backup.")
    try:
        z = zipfile.ZipFile(io.BytesIO(dados))
        nomes = z.namelist()
        if MANIFESTO not in nomes:
            raise ErroDados("Esse arquivo não é um backup do CorrerIA.")
        man = json.loads(z.read(MANIFESTO).decode("utf-8"))
        if not isinstance(man, dict) or man.get("app") != "correria":
            raise ErroDados("Esse arquivo não é um backup do CorrerIA.")
        arquivos = {}
        for nome in ARQUIVOS:
            if nome not in nomes:
                continue
            if z.getinfo(nome).file_size > MAX_ARQUIVO:
                raise ErroDados("Arquivo grande demais.")
            texto = z.read(nome).decode("utf-8")
            if not isinstance(json.loads(texto), dict):
                raise ErroDados(f"O backup está estragado ({nome}).")
            arquivos[nome] = texto
    except ErroDados:
        raise
    except (zipfile.BadZipFile, ValueError, KeyError, OSError, UnicodeDecodeError):
        raise ErroDados("Não consegui abrir esse arquivo. É o .zip de um backup do CorrerIA?") from None
    if "config.json" not in arquivos:
        raise ErroDados("Esse backup não tem as configurações.")
    return arquivos, man


def aplicar(data_dir, arquivos, gravar):
    """Troca os dados pelos do backup: grava os que vieram e tira os que o backup não tem."""
    for nome in ARQUIVOS:
        caminho = os.path.join(data_dir, nome)
        if nome in arquivos:
            gravar(caminho, arquivos[nome])
        else:
            _tirar(caminho)


def zerar(data_dir):
    for nome in DO_ZERO:
        _tirar(os.path.join(data_dir, nome))


def _tirar(caminho):
    try:
        os.remove(caminho)
    except OSError:
        pass


def nome_do_arquivo(agora=None, motivo=""):
    t = time.localtime(agora if agora is not None else time.time())
    return f"correria-{time.strftime('%Y-%m-%d-%H%M%S', t)}{'-' + motivo if motivo else ''}.zip"


def guardar(pasta, dados, maximo, agora=None, motivo=""):
    """Grava um .zip em pasta (só do dono) e fica com os `maximo` mais novos. Devolve o nome."""
    os.makedirs(pasta, exist_ok=True)
    nome = nome_do_arquivo(agora, motivo)
    caminho = os.path.join(pasta, nome)
    tmp = caminho + ".tmp"
    with open(tmp, "wb") as f:
        f.write(dados)
        f.flush()
        os.fsync(f.fileno())
    os.chmod(tmp, 0o600)
    os.replace(tmp, caminho)
    for velho in [x["nome"] for x in listar(pasta)][maximo:]:
        _tirar(os.path.join(pasta, velho))
    return nome


def listar(pasta):
    """Os .zip de pasta, do mais novo para o mais velho: [{nome, em (AAAA-MM-DDTHH:MM:SS), tamanho, motivo}]."""
    try:
        nomes = os.listdir(pasta)
    except OSError:
        return []
    out = []
    for n in nomes:
        m = NOME_RE.match(n)
        if not m:
            continue
        h = m.group(2)
        try:
            st = os.stat(os.path.join(pasta, n))
        except OSError:
            continue
        out.append({"nome": n, "em": f"{m.group(1)}T{h[:2]}:{h[2:4]}:{h[4:]}", "tamanho": st.st_size, "motivo": MOTIVOS.get(m.group(3) or "", ""),
                    "_ordem": (m.group(1), h, st.st_mtime_ns)})  # dois no mesmo segundo: o gravado por último é o mais novo
    out.sort(key=lambda x: x.pop("_ordem"), reverse=True)
    return out


def abrir(pasta, nome):
    """Os bytes de um .zip de pasta, pelo nome (só os nomes que o app mesmo dá)."""
    if not NOME_RE.match(str(nome or "")):
        raise ErroDados("Não achei esse backup.")
    try:
        with open(os.path.join(pasta, nome), "rb") as f:
            return f.read()
    except OSError:
        raise ErroDados("Não achei esse backup.") from None
