"""A versão fica num lugar só, o correria/config.yaml: o servidor lê de lá (no contêiner, o Dockerfile copia o arquivo
para /app) e a tela recebe pelo /api/estado. O CHANGELOG tem a seção dela."""
import os
import re
import tempfile
import unittest
from unittest import mock

from tests.base import importar_servidor
S = importar_servidor()

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def ler(*p):
    with open(os.path.join(RAIZ, *p), encoding="utf-8") as f:
        return f.read()


class Versao(unittest.TestCase):
    def test_um_lugar_so(self):
        v = re.search(r'^version:\s*"?([\d.]+)', ler("correria", "config.yaml"), re.M).group(1)
        self.assertEqual(S.VERSAO, v)
        self.assertIn(f"## {v}\n", ler("correria", "CHANGELOG.md"))
        self.assertIsNone(re.search(r"VERSAO = ['\"]\d", ler("correria", "app", "www", "app.js")), "a tela não tem a versão escrita")
        self.assertIn("COPY config.yaml /app/config.yaml", ler("correria", "Dockerfile"))

    def test_no_conteiner_e_sem_arquivo(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "config.yaml"), "w") as f:
                f.write('name: CorrerIA\nversion: "9.8.7"\n')
            with mock.patch.object(S.os.path, "abspath", return_value=os.path.join(d, "server.py")):
                self.assertEqual(S.ler_versao(), "9.8.7", "ao lado do server.py, como no contêiner")
            with mock.patch.object(S.os.path, "abspath", return_value=os.path.join(d, "vazio", "x", "server.py")):
                self.assertEqual(S.ler_versao(), "0", "sem o arquivo")


if __name__ == "__main__":
    unittest.main()
