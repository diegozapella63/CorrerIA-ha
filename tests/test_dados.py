"""Configurações › Dados (1.29.0): o .zip com tudo de /data (o token, a chave secreta e as conversas inclusive, a pedido do
dono), o backup na pasta share, importar, as versões anteriores e o Começar do zero."""
import base64
import io
import json
import os
import shutil
import tempfile
import unittest
import zipfile
from unittest import mock

import urllib.request

from tests.test_rondas import Base, S

D = S.copias


def gravar(pasta, nome, conteudo):
    os.makedirs(pasta, exist_ok=True)
    with open(os.path.join(pasta, nome), "w", encoding="utf-8") as f:
        json.dump(conteudo, f)


class TestZip(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)

    def test_monta_confere_aplica_e_zera(self):
        gravar(self.dir, "config.json", {"token": "segredo-inventado", "cor": "azul"})
        gravar(self.dir, "conversas.json", {"tela": {}})
        gravar(self.dir, "lembrancas.json", {"lista": [{"id": "a", "texto": "Creme é Higiene"}]})
        gravar(self.dir, "outro.json", {"x": 1})
        z = D.montar_zip(self.dir, "9.9.9", "2026-11-22T10:00:00-03:00")
        nomes = zipfile.ZipFile(io.BytesIO(z)).namelist()
        self.assertEqual(nomes, ["config.json", "conversas.json", "lembrancas.json", "correria.json"], "só o que é do app e existe")
        arquivos, man = D.ler_zip(z)
        self.assertEqual((man["app"], man["versao"], man["arquivos"]), ("correria", "9.9.9", ["config.json", "conversas.json", "lembrancas.json"]))
        self.assertEqual(json.loads(arquivos["config.json"])["token"], "segredo-inventado", "leva os segredos, a pedido do dono")
        # aplicar noutra pasta: grava o que veio e tira o que o backup não tem
        outra = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, outra, True)
        gravar(outra, "rondas.json", {"historico": [1]})
        gravados = []
        D.aplicar(outra, arquivos, lambda c, t: (gravados.append(os.path.basename(c)), S.gravar_arquivo(c, t)))
        self.assertEqual((gravados, sorted(os.listdir(outra))), (["config.json", "conversas.json", "lembrancas.json"], ["config.json", "conversas.json", "lembrancas.json"]))
        D.zerar(outra)
        self.assertEqual(sorted(os.listdir(outra)), ["config.json", "lembrancas.json"], "o Começar do zero deixa as configurações (e as lembranças de antes, que o servidor leva para a memória de todos)")

    def test_o_que_nao_e_um_backup_e_recusado(self):
        def zipar(**arqs):
            b = io.BytesIO()
            with zipfile.ZipFile(b, "w") as z:
                for n, t in arqs.items():
                    z.writestr(n.replace("_json", ".json"), t)
            return b.getvalue()
        man = json.dumps({"app": "correria"})
        for dados, erro in ((b"", "Escolha o arquivo do backup."), (b"isto nao e zip", "Não consegui abrir esse arquivo"),
                            (zipar(config_json="{}"), "não é um backup do CorrerIA"),
                            (zipar(correria_json=json.dumps({"app": "gerencia"}), config_json="{}"), "não é um backup do CorrerIA"),
                            (zipar(correria_json="[1]", config_json="{}"), "não é um backup do CorrerIA"),
                            (zipar(correria_json=man, conversas_json="{}"), "não tem as configurações"),
                            (zipar(correria_json=man, config_json="[1, 2]"), "O backup está estragado (config.json)."),
                            (zipar(correria_json=man, config_json="{estragado"), "Não consegui abrir esse arquivo")):
            with self.assertRaises(D.ErroDados) as cm:
                D.ler_zip(dados)
            self.assertIn(erro, str(cm.exception))
        with mock.patch.object(D, "MAX_ZIP", 10), self.assertRaisesRegex(D.ErroDados, "grande demais"):
            D.ler_zip(zipar(correria_json=man, config_json="{}"))
        with mock.patch.object(D, "MAX_ARQUIVO", 1), self.assertRaisesRegex(D.ErroDados, "grande demais"):
            D.ler_zip(zipar(correria_json=man, config_json="{}"))
        arqs, _ = D.ler_zip(zipar(correria_json=man, config_json="{}", intruso_json="{}"))
        self.assertEqual(list(arqs), ["config.json"], "um arquivo que não é do app fica de fora")

    def test_guardar_listar_e_abrir(self):
        pasta = os.path.join(self.dir, "b")
        nomes = [D.guardar(pasta, b"zip%d" % i, 3, agora=1795000000 + i * 60, motivo="zero" if i == 4 else "") for i in range(5)]
        lista = D.listar(pasta)
        self.assertEqual([x["nome"] for x in lista], nomes[:1:-1], "ficam os 3 mais novos, o mais novo primeiro")
        self.assertEqual((lista[0]["motivo"], lista[1]["motivo"], lista[0]["tamanho"]), ("antes de começar do zero", "", 4))
        self.assertRegex(lista[0]["em"], r"^2026-\d\d-\d\dT\d\d:\d\d:\d\d$")
        self.assertEqual(oct(os.stat(os.path.join(pasta, nomes[-1])).st_mode & 0o777), "0o600", "só do dono: leva o token e a chave")
        self.assertEqual(D.abrir(pasta, nomes[-1]), b"zip4")
        open(os.path.join(pasta, "estranho.zip"), "w").close()
        self.assertEqual(len(D.listar(pasta)), 3)
        for ruim in ("../config.json", "estranho.zip", nomes[0], ""):
            with self.assertRaisesRegex(D.ErroDados, "Não achei esse backup"):
                D.abrir(pasta, ruim)
        self.assertEqual(D.listar(os.path.join(self.dir, "nao-existe")), [])
        self.assertRegex(D.nome_do_arquivo(), r"^correria-\d{4}-\d\d-\d\d-\d{6}\.zip$")


class TestPelaTela(Base):
    def get_cru(self, caminho):
        with urllib.request.urlopen(urllib.request.Request(self.url + caminho, headers=self.CAB), timeout=10) as r:
            return r.status, dict(r.headers), r.read()

    def setUp(self):
        super().setUp()
        for pasta in (S.BACKUPS_DIR, S.VERSOES_DIR):
            shutil.rmtree(pasta, True)
            self.addCleanup(shutil.rmtree, pasta, True)
        self.addCleanup(lambda: [os.remove(a) for a in (S.RONDAS_ARQ, S.MINHAS_ARQ) if os.path.exists(a)])
        self.addCleanup(S.montar_rondas)
        S.memoria_ia._GUARDADO.clear()
        self.addCleanup(S.memoria_ia._GUARDADO.clear)

    def test_exportar_backup_importar_restaurar_e_zerar(self):
        S.salvar_config({"numero_id": "123456", "token": "token-inventado-1234", "segredo": "chave-inventada-5678"})
        S.lembrar("Creme é sempre Higiene")   # a Memória da IA é de todos os apps (na pasta share): não entra no arquivo daqui
        ronda = {"nome": "Garagem", "etapas": [{"de": "casa.item_novo"}]}
        S.editar_rondas({"acao": "salvar", "ronda": ronda})
        # exportar: o .zip para baixar, com tudo
        st, cab, corpo = self.get_cru("/api/dados/exportar")
        self.assertEqual((st, cab["Content-Type"]), (200, "application/zip"))
        self.assertRegex(cab["Content-Disposition"], r'^attachment; filename="correria-\d{4}-\d\d-\d\d-\d{6}\.zip"$')
        arquivos, man = D.ler_zip(corpo)
        self.assertEqual((man["versao"], json.loads(arquivos["config.json"])["token"]), (S.VERSAO, "token-inventado-1234"))
        self.assertNotIn("lembrancas.json", arquivos)
        self.assertIn("Garagem", arquivos["rondas_minhas.json"])
        # backup na pasta share
        self.assertEqual(self.j("/api/dados")[1], {"backups": [], "versoes": []})
        st, r = self.j("/api/dados/backup", {})
        self.assertEqual((st, len(r["backups"]), r["versoes"]), (200, 1, []))
        self.assertTrue(os.path.exists(os.path.join(S.BACKUPS_DIR, r["backups"][0]["nome"])))
        backup = r["backups"][0]["nome"]
        # muda os dados; restaurar volta e guarda uma versão do que havia
        S.editar_rondas({"acao": "salvar", "ronda": {"nome": "Oficina", "etapas": [{"de": "casa.item_novo"}]}})
        S.FOTOS["tela:x"] = {"em": 0, "anexo": {}}
        minhas = lambda: sorted(r["nome"] for r in S.ler_minhas()["rondas"].values())
        st, r = self.j("/api/dados/restaurar", {"origem": "backup", "nome": backup})
        self.assertEqual((st, len(r["versoes"]), r["versoes"][0]["motivo"]), (200, 1, "antes de restaurar"))
        self.assertEqual(minhas(), ["Garagem"])
        self.assertEqual(sorted(r["nome"] for r in S.rondas.RONDAS.values() if r.get("minha")), ["Garagem"], "as rondas valem na hora")
        self.assertEqual(S.FOTOS, {}, "o que estava na memória não vale mais")
        st, r = self.j("/api/dados/restaurar", {"origem": "versao", "nome": r["versoes"][0]["nome"]})
        self.assertEqual((st, minhas()), (200, ["Garagem", "Oficina"]), "a versão anterior volta ao que havia antes de restaurar")
        self.assertEqual(self.j("/api/dados/restaurar", {"origem": "backup", "nome": "../../config.json"}), (400, {"erro": "Não achei esse backup."}))
        # importar o arquivo exportado
        st, r = self.j("/api/dados/importar", {"zip": "data:application/zip;base64," + base64.b64encode(corpo).decode()})
        self.assertEqual((st, r["versoes"][0]["motivo"], minhas()), (200, "antes de importar", ["Garagem"]))
        self.assertEqual(S.ler_config()["token"], "token-inventado-1234")
        self.assertEqual(self.j("/api/dados/importar", {"zip": "isto não é base64!"})[1]["erro"], "Não consegui abrir esse arquivo. É o .zip de um backup do CorrerIA?")
        self.assertEqual(self.j("/api/dados/importar", {"zip": base64.b64encode(b"nada").decode()})[0], 400)
        # um backup de antes da 1.31.0 traz as lembranças em /data: ao importar, vão para a memória de todos os apps
        velho = io.BytesIO()
        with zipfile.ZipFile(velho, "w") as z:
            z.writestr("correria.json", json.dumps({"app": "correria", "versao": "1.29.0"}))
            z.writestr("config.json", arquivos["config.json"])
            z.writestr("lembrancas.json", json.dumps({"lista": [{"id": "v", "texto": "O lixo sai na terça"}]}))
        st, r = self.j("/api/dados/importar", {"zip": base64.b64encode(velho.getvalue()).decode()})
        self.assertEqual((st, [x["texto"] for x in S.lembrancas()], os.path.exists(S.LEMBRANCAS_ARQ)), (200, ["Creme é sempre Higiene", "O lixo sai na terça"], False))
        # começar do zero: só confirmando; as configurações ficam
        self.assertEqual(self.j("/api/dados/zerar", {}), (400, {"erro": "Confirme para começar do zero."}))
        st, r = self.j("/api/dados/zerar", {"confirmar": True})
        self.assertEqual((st, r["versoes"][0]["motivo"], minhas()), (200, "antes de começar do zero", []))
        self.assertEqual([x["texto"] for x in S.lembrancas()], ["Creme é sempre Higiene", "O lixo sai na terça"], "a Memória da IA é de todos os apps: fica")
        self.assertEqual((S.ler_config()["token"], len(r["versoes"])), ("token-inventado-1234", 3), "ficam as 3 últimas versões")
        self.assertEqual(self.j("/api/dados/outra", {})[0], 404)
        with mock.patch.object(D, "guardar", side_effect=OSError(30, "Read-only file system")):
            self.assertEqual(self.j("/api/dados/backup", {}), (400, {"erro": "Não consegui gravar na pasta share (Read-only file system)."}))


if __name__ == "__main__":
    unittest.main()
