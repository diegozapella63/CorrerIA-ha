#!/usr/bin/env python3
"""Cobertura de linhas dos testes do CorrerIA, só com a biblioteca padrão (como o app; a mesma ferramenta do EconomIA).

Roda os testes unitários e de integração (tests/test_*.py) com um rastreador ligado só nos arquivos do app
(correria/app/*.py) e conta, para cada arquivo, quantas linhas que executam código os testes percorreram.
O servidor da tela (test_tela.py) roda numa thread do próprio teste, então entra na conta.

    python3 tools/cobertura.py                 resumo por arquivo
    python3 tools/cobertura.py --linhas        e as linhas que nenhum teste percorre
    python3 tools/cobertura.py --minimo 85     falha (código 1) se a cobertura total ficar abaixo de 85%
    python3 tools/cobertura.py --resumo ARQ    também escreve a tabela em Markdown no ARQ (no GitHub: $GITHUB_STEP_SUMMARY)
"""
import argparse
import os
import sys
import threading
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(RAIZ, "correria", "app")
ALVOS = {os.path.join(APP, f) for f in os.listdir(APP) if f.endswith(".py")}


def linhas_de_codigo(caminho):
    """As linhas que executam algo (as que o Python marca nos objetos de código), sem as de docstring."""
    with open(caminho, encoding="utf-8") as f:
        fonte = f.read()
    raiz = compile(fonte, caminho, "exec")
    linhas, pilha = set(), [raiz]
    while pilha:
        co = pilha.pop()
        doc = co.co_consts[0] if co.co_consts and isinstance(co.co_consts[0], str) and co.co_name != "<module>" else None
        for _, _, n in co.co_lines():
            if n is not None and n > co.co_firstlineno - 1:
                linhas.add(n)
        if doc is not None:  # a docstring da função não é código
            linhas.discard(co.co_firstlineno + 1)
        pilha.extend(c for c in co.co_consts if hasattr(c, "co_lines"))
    texto = fonte.splitlines()
    return {n for n in linhas if n <= len(texto) and texto[n - 1].strip() and not texto[n - 1].strip().startswith("#")}


def faixas(ns):
    ns, out = sorted(ns), []
    for n in ns:
        if out and n == out[-1][1] + 1:
            out[-1][1] = n
        else:
            out.append([n, n])
    return ", ".join(f"{a}" if a == b else f"{a}-{b}" for a, b in out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--linhas", action="store_true")
    ap.add_argument("--minimo", type=float, default=0)
    ap.add_argument("--padrao", default="test_*.py")
    ap.add_argument("--resumo", default="")
    a = ap.parse_args()

    vistas = {c: set() for c in ALVOS}

    def local(frame, evento, arg):
        if evento == "line":
            vistas[frame.f_code.co_filename].add(frame.f_lineno)
        return local

    def global_(frame, evento, arg):
        if frame.f_code.co_filename in vistas:
            vistas[frame.f_code.co_filename].add(frame.f_lineno)
            return local
        return None

    sys.path.insert(0, RAIZ)
    # o rastreador liga antes de achar os testes: eles importam os módulos do app no começo do arquivo, e o que roda
    # na importação (imports, constantes, def e class) também conta
    threading.settrace(global_)
    sys.settrace(global_)
    try:
        suite = unittest.defaultTestLoader.discover(os.path.join(RAIZ, "tests"), pattern=a.padrao, top_level_dir=RAIZ)
        r = unittest.TextTestRunner(stream=open(os.devnull, "w"), verbosity=0).run(suite)
    finally:
        sys.settrace(None)
        threading.settrace(None)

    total_cod = total_vis = 0
    print(f"{'arquivo':<12} {'linhas':>7} {'cobertas':>9} {'%':>7}")
    relatorio = []
    for c in sorted(ALVOS):
        cod = linhas_de_codigo(c)
        vis = vistas[c] & cod
        total_cod += len(cod)
        total_vis += len(vis)
        pct = 100 * len(vis) / len(cod) if cod else 100
        print(f"{os.path.basename(c):<12} {len(cod):>7} {len(vis):>9} {pct:>6.1f}%")
        relatorio.append((c, cod - vis))
    pct = 100 * total_vis / total_cod if total_cod else 100
    print(f"{'total':<12} {total_cod:>7} {total_vis:>9} {pct:>6.1f}%")
    print(f"{r.testsRun} testes, {len(r.failures) + len(r.errors)} com falha")
    for teste, erro in r.failures + r.errors:
        print(f"\nFALHOU {teste}\n{erro}")
    if a.resumo:
        with open(a.resumo, "a", encoding="utf-8") as f:
            f.write(f"### Cobertura de linhas: {pct:.1f}% ({r.testsRun} testes)\n\n| arquivo | linhas | cobertas | % |\n|---|---:|---:|---:|\n")
            for c, faltam in relatorio:
                cod = linhas_de_codigo(c)
                f.write(f"| {os.path.basename(c)} | {len(cod)} | {len(cod) - len(faltam)} | {100 * (len(cod) - len(faltam)) / len(cod):.1f}% |\n")
            f.write(f"| **total** | {total_cod} | {total_vis} | **{pct:.1f}%** |\n\n")
    if a.linhas:
        for c, faltam in relatorio:
            if faltam:
                print(f"\n{os.path.basename(c)}: {faixas(faltam)}")
    if r.failures or r.errors:
        sys.exit(1)
    if pct < a.minimo:
        print(f"Cobertura {pct:.1f}% abaixo do mínimo de {a.minimo:g}%.")
        sys.exit(1)


if __name__ == "__main__":
    main()
