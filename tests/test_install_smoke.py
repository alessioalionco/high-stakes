#!/usr/bin/env python3
"""test_install_smoke.py — a experiência de quem instala (convenção deste projeto: PASS/exit≠0).

Simula a máquina do estranho: diretório de trabalho que não é o repo, nenhuma variável do
produto no ambiente, nenhuma chave de API. Teste unitário não pega esta classe de falha —
ele roda de dentro do repo, com o ambiente do autor já montado.

Trava também a promessa de capa: **zero dependência externa**. Ela é verificada por AST
sobre todo o pacote, não por confiança — é o tipo de regra que se perde no primeiro
`import requests` conveniente, e a falha apareceria só na máquina de quem instalou.
"""
import ast
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "high_stakes"


def external_imports() -> set[str]:
    """Módulos de topo importados pelo pacote que NÃO são da stdlib."""
    ext: set[str] = set()
    for py in sorted(PKG.rglob("*.py")):
        tree = ast.parse(py.read_text(), filename=str(py))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    ext.add(a.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.level:  # relativo (from .x import y) — é do próprio pacote
                    continue
                if node.module:
                    ext.add(node.module.split(".")[0])
    return {m for m in ext
            if m not in sys.stdlib_module_names and m != "high_stakes"}


def main() -> int:
    results: list[bool] = []

    def case(name, cond, detail=""):
        print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail and not cond else ""))
        results.append(bool(cond))

    # ---- ambiente de estranho: sem nenhuma variável do produto, sem chave ----
    # SEM PYTHONPATH: era exatamente a condição que falta na máquina de quem instala.
    # Injetá-la fazia o smoke passar 19/19 enquanto `python3 -m high_stakes.paths` dava
    # ModuleNotFoundError de qualquer cwd real — o teste escondia o defeito que existia
    # para pegar. Os comandos agora vão pelo launcher, como o adapter manda.
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("HIGH_STAKES_")
           and k not in ("OPENROUTER_API_KEY", "PYTHONPATH")}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    LAUNCHER = str(ROOT / "bin" / "high-stakes")

    tmp = Path(tempfile.mkdtemp())  # cwd que NÃO é o repo
    try:
        def run(*args, cwd=tmp):
            """Invoca pelo LAUNCHER — o caminho real de quem instalou o plugin."""
            return subprocess.run([LAUNCHER, *args], cwd=cwd, env=env,
                                  capture_output=True, text=True)

        def run_lib(*args, cwd=tmp):
            """Uso como BIBLIOTECA (import em script próprio): aí sim PYTHONPATH."""
            e = dict(env); e["PYTHONPATH"] = str(ROOT)
            return subprocess.run([sys.executable, *args], cwd=cwd, env=e,
                                  capture_output=True, text=True)

        # ---- a promessa de capa ----
        ext = external_imports()
        case("ZERO dependência externa: todo import do pacote é stdlib ou relativo",
             not ext, f"externos: {sorted(ext)}")
        case("piso de versão declarado no pyproject bate com o interpretador (tomllib ≥3.11)",
             sys.version_info >= (3, 11))
        case("pyproject declara dependencies = []",
             'dependencies = []' in (ROOT / "pyproject.toml").read_text())

        # ---- importa de fora do repo, sem env nenhum ----
        r = run_lib("-c", "import high_stakes.or_client, high_stakes.render_dossier, "
                          "high_stakes.qverify, high_stakes.quick_panel, high_stakes.config; print('ok')")
        case("como biblioteca: importa de diretório qualquer com PYTHONPATH",
             r.returncode == 0 and "ok" in r.stdout, r.stderr[-200:])

        case("REGRESSÃO: o launcher existe e é executável",
             os.access(LAUNCHER, os.X_OK))
        r_nu = subprocess.run([sys.executable, "-m", "high_stakes.paths", "core"],
                              cwd=tmp, env=env, capture_output=True, text=True)
        case("REGRESSÃO: `python3 -m high_stakes.X` SEM PYTHONPATH falha — é por isso "
             "que o adapter documenta o launcher, não o -m",
             r_nu.returncode != 0 and "ModuleNotFoundError" in r_nu.stderr)

        # ---- os comandos que o adapter chama ----
        r = run("paths", "core")
        case("`paths core` responde caminho existente de fora do repo",
             r.returncode == 0 and Path(r.stdout.strip()).is_dir(), r.stderr[-200:])

        r = run("config")
        case("`config` roda sem HOME criado e sem chave, e AVISA que a chave falta",
             r.returncode == 0 and "AUSENTE" in r.stdout, r.stderr[-200:])
        case("`config` cai nos boards embarcados quando o usuário não tem os dele",
             "high-stakes/boards" in r.stdout.replace(os.sep, "/"), r.stdout[-200:])

        # ---- o gate e o render, ponta a ponta, sobre o exemplo ----
        r = run("render_gate", str(ROOT / "examples" / "sample-dossier.md"))
        case("gate de render sai 0 no dossiê de exemplo, rodado de fora do repo",
             r.returncode == 0, r.stdout[-300:])

        out_html = tmp / "saida.html"
        r = run("render_dossier",
                str(ROOT / "examples" / "sample-dossier.md"), str(out_html))
        case("render produz HTML de fora do repo", r.returncode == 0 and out_html.exists(),
             r.stderr[-200:])
        if out_html.exists():
            h = out_html.read_text()
            case("HTML gerado é single-file (CSS embutido, zero referência externa)",
                 "<style>" in h and "<link " not in h and 'src="http' not in h)
            case("REGRESSÃO: o CSS veio do pacote — render não depende de examples/",
                 len(h) > 20000)

        # ---- erro de uso não pode ser stack trace ----
        r = run("render_gate")
        case("gate sem argumento sai 2 com mensagem de uso, não stack trace",
             r.returncode == 2 and "Traceback" not in r.stderr)
        r = run("render_gate", str(tmp / "nao-existe.md"))
        case("gate em arquivo inexistente sai 1 com mensagem, não stack trace",
             r.returncode == 1 and "Traceback" not in r.stderr)

        # ---- higiene de publicação: o repo não pode vazar a máquina nem a origem ----
        # (a checagem por NOME de empresa/empregador vive fora deste repo, de propósito:
        # um teste que procurasse o nome teria de conter o nome.)
        SRC = [f for f in ROOT.rglob("*")
               if f.is_file() and ".git/" not in str(f)
               and f.suffix in {".py", ".md", ".toml", ".yaml", ".json", ".css"}]

        AQUI = Path(__file__).resolve()  # o verificador contém as agulhas: se acha a si
        maquina = [f.relative_to(ROOT) for f in SRC                     # mesmo, é falso positivo
                   if f.resolve() != AQUI
                   and any(s in f.read_text(errors="ignore")
                           for s in ("/Users/", "/home/", "C:\\Users"))]
        case("nenhum caminho absoluto de máquina no repo", not maquina, f"{maquina}")

        import re as _re
        ALLOW = ("apache.org", "openrouter.ai", "github.com/alessioalionco",
                 "127.0.0.1", "localhost", "www.w3.org")
        urls = set()
        for f in SRC:
            if f.name.startswith("test_"):
                continue  # fixtures usam domínios inventados de propósito
            for u in _re.findall(r"https?://[\w./-]+", f.read_text(errors="ignore")):
                if not any(a in u for a in ALLOW):
                    urls.add(u)
        case("toda URL publicada está na allowlist", not urls, f"{sorted(urls)}")

        emails = set()
        for f in SRC:
            if f.name == "LICENSE":
                continue
            emails |= set(_re.findall(r"[\w.+-]+@[\w-]+\.[\w.]+", f.read_text(errors="ignore")))
        case("nenhum e-mail embutido no código ou nos docs", not emails, f"{sorted(emails)}")

        # ---- o plugin ----
        import json
        man = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
        case("manifest do plugin tem os campos obrigatórios",
             all(k in man for k in ("name", "description", "version", "author")))
        case("skill do plugin existe no caminho que o harness procura",
             (ROOT / "skills" / man["name"] / "SKILL.md").exists())
        case("versão do plugin bate com a do pacote",
             man["version"] in (ROOT / "pyproject.toml").read_text())

        print(f"{sum(results)}/{len(results)} testes ok")
        return 0 if all(results) else 1
    finally:
        __import__("shutil").rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
