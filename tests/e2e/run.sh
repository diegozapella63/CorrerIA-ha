#!/usr/bin/env bash
# Os testes da tela num Chromium (Playwright): tests/e2e/run.sh            todos (tests/test_tela.py)
#                                             tests/e2e/run.sh test_sobre  só esses
set -u
cd "$(dirname "$0")/../.."
if [ $# -gt 0 ]; then args=(); for n in "$@"; do args+=("tests.test_tela.Tela.$n"); done; exec python3 -m unittest "${args[@]}"; fi
exec python3 -m unittest tests.test_tela
