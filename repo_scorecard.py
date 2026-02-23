#!/usr/bin/env python3
"""
repo_scorecard - CLI para puntuar repositorios locales con checks ponderados.
Solo usa la biblioteca estándar de Python.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

# Carpetas que se ignoran al recorrer el repo
IGNORED_DIRS = {".git", "node_modules", "bin", "obj", "dist", "build", ".venv"}

# Máximo de bytes a leer por archivo al buscar strings (p. ej. opentelemetry)
MAX_READ_BYTES = 64 * 1024


@dataclass
class CheckResult:
    """Resultado de un check individual."""
    id: str
    name: str
    weight: int
    passed: bool
    evidence: str


def parse_args() -> argparse.Namespace:
    """Parsea argumentos del CLI."""
    parser = argparse.ArgumentParser(
        description="Calcula un score 0-100 para un repositorio local."
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=Path("."),
        help="Ruta al repositorio local (default: .)",
    )
    parser.add_argument(
        "--out",
        choices=("json", "text"),
        default="json",
        help="Formato de salida: json o text (default: json)",
    )
    parser.add_argument(
        "--min-score",
        type=int,
        default=None,
        metavar="N",
        help="En CI: fallar con exit 1 si el score es menor que N (ej: 50)",
    )
    return parser.parse_args()


def walk_repo(root: Path) -> list[Path]:
    """Recorre el repo y devuelve rutas de archivos, ignorando IGNORED_DIRS."""
    paths: list[Path] = []
    try:
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            if any(part in p.parts for part in IGNORED_DIRS):
                continue
            paths.append(p)
    except PermissionError:
        pass  # Se omiten directorios sin permiso
    return paths


def check_readme(root: Path) -> CheckResult:
    """README.md o README.* existe (peso 10)."""
    weight = 10
    for p in root.iterdir():
        if not p.is_file():
            continue
        name = p.name.upper()
        if name == "README.MD" or (name.startswith("README.") and len(name) > 7):
            return CheckResult("readme", "README existe", weight, True, str(p.name))
    return CheckResult("readme", "README existe", weight, False, "")


def check_license(root: Path) -> CheckResult:
    """LICENSE existe (peso 5)."""
    weight = 5
    for p in root.iterdir():
        if p.is_file() and p.name.upper().startswith("LICENSE"):
            return CheckResult("license", "LICENSE existe", weight, True, p.name)
    return CheckResult("license", "LICENSE existe", weight, False, "")


def check_codeowners(root: Path) -> CheckResult:
    """CODEOWNERS en .github/CODEOWNERS o raíz (peso 10)."""
    weight = 10
    candidates = [
        root / ".github" / "CODEOWNERS",
        root / "CODEOWNERS",
    ]
    for p in candidates:
        if p.is_file():
            return CheckResult("codeowners", "CODEOWNERS existe", weight, True, str(p.relative_to(root)))
    return CheckResult("codeowners", "CODEOWNERS existe", weight, False, "")


def check_ci(root: Path) -> CheckResult:
    """CI: .github/workflows/*.yml|yaml o .gitlab-ci.yml (peso 15)."""
    weight = 15
    workflows = root / ".github" / "workflows"
    if workflows.is_dir():
        for f in workflows.iterdir():
            if f.suffix.lower() in (".yml", ".yaml"):
                return CheckResult("ci", "CI configurado", weight, True, str(f.relative_to(root)))
    gl = root / ".gitlab-ci.yml"
    if gl.is_file():
        return CheckResult("ci", "CI configurado", weight, True, gl.name)
    return CheckResult("ci", "CI configurado", weight, False, "")


def check_tests(root: Path) -> CheckResult:
    """Tests: tests/, __tests__/ o archivos *test*/*spec* (peso 15)."""
    weight = 15
    paths = walk_repo(root)
    if (root / "tests").is_dir() or (root / "test").is_dir():
        return CheckResult("tests", "Tests presentes", weight, True, "tests/ o test/")
    for p in paths:
        rel = p.relative_to(root)
        if "__tests__" in rel.parts:
            return CheckResult("tests", "Tests presentes", weight, True, str(rel))
        name = p.stem.lower()
        if "test" in name or "spec" in name:
            if any(x in rel.parts for x in ("test", "tests", "spec", "specs", "__tests__")):
                return CheckResult("tests", "Tests presentes", weight, True, str(rel))
    # Carpeta __tests__ en cualquier nivel
    for p in paths:
        if "__tests__" in p.parts:
            return CheckResult("tests", "Tests presentes", weight, True, str(p.relative_to(root)))
    return CheckResult("tests", "Tests presentes", weight, False, "")


def check_linter(root: Path) -> CheckResult:
    """Linter: .editorconfig, .eslintrc*, ruff.toml, pyproject con ruff/black/isort, stylecop (peso 10)."""
    weight = 10
    paths = walk_repo(root)
    for p in paths:
        try:
            rel = str(p.relative_to(root)).replace("\\", "/")
        except ValueError:
            continue
        name = p.name.lower()
        if name == ".editorconfig":
            return CheckResult("linter", "Linter config", weight, True, rel)
        if name.startswith(".eslintrc"):
            return CheckResult("linter", "Linter config", weight, True, rel)
        if name == "ruff.toml":
            return CheckResult("linter", "Linter config", weight, True, rel)
        if name == "stylecop.json":
            return CheckResult("linter", "Linter config", weight, True, rel)
        if name == "pyproject.toml":
            try:
                content = p.read_text(encoding="utf-8", errors="ignore")[:8192]
                if "ruff" in content or "black" in content or "isort" in content:
                    return CheckResult("linter", "Linter config", weight, True, rel)
            except (OSError, PermissionError):
                continue
    return CheckResult("linter", "Linter config", weight, False, "")


def check_docker(root: Path) -> CheckResult:
    """Docker: Dockerfile o docker-compose.yml (peso 10)."""
    weight = 10
    for name in ("Dockerfile", "docker-compose.yml", "docker-compose.yaml"):
        p = root / name
        if p.is_file():
            return CheckResult("docker", "Docker presente", weight, True, name)
    return CheckResult("docker", "Docker presente", weight, False, "")


def check_security(root: Path) -> CheckResult:
    """Security: SECURITY.md o .github/dependabot.yml (peso 10)."""
    weight = 10
    if (root / "SECURITY.md").is_file():
        return CheckResult("security", "Security docs/config", weight, True, "SECURITY.md")
    if (root / ".github" / "dependabot.yml").is_file():
        return CheckResult("security", "Security docs/config", weight, True, ".github/dependabot.yml")
    return CheckResult("security", "Security docs/config", weight, False, "")


def check_observability(root: Path) -> CheckResult:
    """Observabilidad: string 'opentelemetry' en config/deps (peso 5)."""
    weight = 5
    paths = walk_repo(root)
    config_names = {
        "package.json", "pyproject.toml", "requirements.txt", "setup.py",
        "pom.xml", "build.gradle", "build.gradle.kts", "cargo.toml",
        "go.mod", "docker-compose.yml", "docker-compose.yaml",
        ".github/workflows", "config", "conf", "*.yml", "*.yaml",
    }
    needle = b"opentelemetry"
    for p in paths:
        try:
            rel = p.relative_to(root)
            if rel.suffix.lower() in (".json", ".toml", ".yml", ".yaml", ".txt", ".xml", ".gradle", ".mod"):
                content = p.read_bytes()[:MAX_READ_BYTES]
                if needle in content.lower():
                    return CheckResult("observability", "OpenTelemetry en deps/config", weight, True, str(rel))
            if "config" in rel.parts or "conf" in rel.parts or "workflows" in rel.parts:
                content = p.read_bytes()[:MAX_READ_BYTES]
                if needle in content.lower():
                    return CheckResult("observability", "OpenTelemetry en deps/config", weight, True, str(rel))
        except (OSError, PermissionError):
            continue
    return CheckResult("observability", "OpenTelemetry en deps/config", weight, False, "")


def check_release_hygiene(root: Path) -> CheckResult:
    """Release: CHANGELOG.md o version en package/pyproject/csproj (peso 10)."""
    weight = 10
    if (root / "CHANGELOG.md").is_file():
        return CheckResult("release", "Release hygiene", weight, True, "CHANGELOG.md")
    version_pattern = re.compile(r'"(?:version|Version)"\s*:\s*["\']?[\d.]+\d["\']?', re.I)
    version_csproj = re.compile(r"<Version>[\d.]+</Version>", re.I)
    for name in ("package.json", "pyproject.toml"):
        p = root / name
        if p.is_file():
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")[:4096]
                if version_pattern.search(text):
                    return CheckResult("release", "Release hygiene", weight, True, f"{name} (version)")
            except (OSError, PermissionError):
                pass
    for p in walk_repo(root):
        if p.suffix.lower() == ".csproj" and p.is_file():
            try:
                if version_csproj.search(p.read_text(encoding="utf-8", errors="ignore")[:4096]):
                    return CheckResult("release", "Release hygiene", weight, True, str(p.relative_to(root)))
            except (OSError, PermissionError):
                pass
    return CheckResult("release", "Release hygiene", weight, False, "")


def run_all_checks(root: Path) -> list[CheckResult]:
    """Ejecuta todos los checks y devuelve la lista de resultados."""
    runners: list[Callable[[Path], CheckResult]] = [
        check_readme,
        check_license,
        check_codeowners,
        check_ci,
        check_tests,
        check_linter,
        check_docker,
        check_security,
        check_observability,
        check_release_hygiene,
    ]
    return [fn(root) for fn in runners]


def compute_score(checks: list[CheckResult]) -> int:
    """Score = suma de pesos de checks pasados (máx 100)."""
    return sum(c.weight for c in checks if c.passed)


def build_report(root: Path, checks: list[CheckResult], score: int) -> dict:
    """Construye el reporte para salida JSON."""
    return {
        "repoPath": str(root.resolve()),
        "score": score,
        "passed": sum(1 for c in checks if c.passed),
        "failed": sum(1 for c in checks if not c.passed),
        "checks": [asdict(c) for c in checks],
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def output_json(report: dict) -> None:
    """Imprime el reporte en JSON."""
    print(json.dumps(report, indent=2, ensure_ascii=False))


def output_text(report: dict) -> None:
    """Imprime el reporte como tabla en consola."""
    repo_path = report["repoPath"]
    score = report["score"]
    passed = report["passed"]
    failed = report["failed"]
    ts = report["timestamp"]
    checks = report["checks"]

    sep = "+" + "-" * 12 + "+" + "-" * 28 + "+" + "-" * 8 + "+" + "-" * 6 + "+" + "-" * 44 + "+"
    head = "| {:<10} | {:<26} | {:^6} | {:^4} | {:<42} |".format("ID", "Name", "Weight", "OK", "Evidence")
    print(f"repo_scorecard — {repo_path}")
    print(f"Score: {score}/100  Passed: {passed}  Failed: {failed}  ({ts})")
    print(sep)
    print(head)
    print(sep)
    for c in checks:
        ev = (c["evidence"] or "-")[:42]
        ok = "yes" if c["passed"] else "no"
        print("| {:<10} | {:<26} | {:^6} | {:^4} | {:<42} |".format(
            c["id"][:10], c["name"][:26], c["weight"], ok, ev
        ))
    print(sep)


def main() -> int:
    """Punto de entrada."""
    args = parse_args()
    root = args.path.resolve()

    if not root.exists():
        print("Error: la ruta no existe.", file=sys.stderr)
        return 1
    if not root.is_dir():
        print("Error: la ruta no es un directorio.", file=sys.stderr)
        return 1

    try:
        if not any(root.iterdir()):
            pass  # directorio vacío, continuar
    except PermissionError:
        print("Error: sin permiso de lectura en el directorio.", file=sys.stderr)
        return 1

    checks = run_all_checks(root)
    score = compute_score(checks)
    report = build_report(root, checks, score)

    if args.out == "text":
        output_text(report)
    else:
        output_json(report)

    if args.min_score is not None and score < args.min_score:
        print(
            f"Score {score} por debajo del mínimo {args.min_score}.",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
