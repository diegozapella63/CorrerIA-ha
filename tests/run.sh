#!/usr/bin/env bash
# Todos os testes (servidor e tela; a tela precisa do playwright): tests/run.sh
# Com a cobertura de linhas do servidor (correria/app/*.py, só biblioteca padrão): tests/run.sh --cobertura
set -u
cd "$(dirname "$0")/.."
if [ "${1:-}" = "--cobertura" ]; then exec python3 tools/cobertura.py --linhas; fi
exec python3 -m unittest discover -s tests -t .
