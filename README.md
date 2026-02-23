# repo_scorecard

CLI en Python (solo biblioteca estándar) que analiza un repositorio local y calcula un **score de 0 a 100** con checks ponderados. Incluye una **app de prueba** con tests unitarios e de integración para ver el flujo CI completo (tests en paralelo + scorecard).

## App de prueba y flujo CI

El repo incluye un módulo de ejemplo `app_prueba` y tests que permiten validar el scorecard y el pipeline:

- **`app_prueba`**: módulo con `calc` (add, greet) y `Store` en memoria.
- **Tests unitarios** (`tests/unit/`): marcadados con `@pytest.mark.unit`.
- **Tests de integración** (`tests/integration/`): marcadados con `@pytest.mark.integration`, combinan varios módulos.

**Ejecutar tests en local:**

```bash
pip install pytest
pytest tests/unit -m unit -v
pytest tests/integration -m integration -v
# o todos
pytest tests -v
```

**Flujo en GitHub Actions** (`.github/workflows/ci.yml`):

- **Unit tests** y **Integration tests** se ejecutan **en paralelo** (dos jobs).
- Un tercer job **Repo Scorecard** ejecuta el CLI sobre el propio repo.
- Los tres jobs corren en cada push/PR a `main` o `master`.

Así puedes ver el flujo completo: tests en paralelo + scorecard en una sola pasada.

## Uso del CLI

```bash
# Analizar el directorio actual (salida JSON por defecto)
python repo_scorecard.py --path .
# En este repo la app de prueba hace que el scorecard pase con alta puntuación

# Especificar ruta y formato de salida
python repo_scorecard.py --path /ruta/al/repo --out json
python repo_scorecard.py --path /ruta/al/repo --out text
```

### Argumentos

| Argumento | Descripción |
|-----------|-------------|
| `--path` | Ruta al repositorio local (default: `.`) |
| `--out` | Formato: `json` o `text` (default: `json`) |
| `--min-score N` | En CI: devuelve exit 1 si el score es menor que N (opcional) |

### Requisitos

- Python 3.10+ (por el uso de `list[Path]` y sintaxis moderna; en 3.9 se puede cambiar a `List[Path]` de `typing` si hace falta).

## Checks y pesos

| ID | Check | Peso |
|----|--------|-----|
| readme | README.md o README.* en la raíz | 10 |
| license | LICENSE en la raíz | 5 |
| codeowners | .github/CODEOWNERS o CODEOWNERS | 10 |
| ci | .github/workflows/*.yml\|yaml o .gitlab-ci.yml | 15 |
| tests | Carpeta tests/ o __tests__/ o archivos *test*/*spec* | 15 |
| linter | .editorconfig, .eslintrc*, ruff.toml, pyproject con ruff/black/isort, stylecop.json | 10 |
| docker | Dockerfile o docker-compose.yml | 10 |
| security | SECURITY.md o .github/dependabot.yml | 10 |
| observability | String "opentelemetry" en archivos de config/deps | 5 |
| release | CHANGELOG.md o version en package.json/pyproject.toml/.csproj | 10 |

**Total:** 100 puntos. El score es la suma de los pesos de los checks que pasan.

Se ignoran las carpetas: `.git`, `node_modules`, `bin`, `obj`, `dist`, `build`, `.venv`.

## Uso en CI/CD (GitHub Actions)

Incluye un workflow de ejemplo en `.github/workflows/scorecard.yml` que ejecuta el scorecard en cada push y en cada pull request a `main`/`master`.

**Cómo usarlo en tu repo:**

1. Copia el script `repo_scorecard.py` y la carpeta `.github/workflows/` a tu repositorio (o añade el job al workflow que ya tengas).
2. El job hace checkout, configura Python y ejecuta el scorecard; el resultado se muestra en la pestaña Actions.

**Fallo por score bajo (opcional):**

- En el workflow, define la variable de entorno `MIN_SCORE` en el job `scorecard` para que el job falle si el score es menor:
  ```yaml
  jobs:
    scorecard:
      env:
        MIN_SCORE: 50
  ```
- O, si disparas el workflow a mano (`workflow_dispatch`), puedes indicar el score mínimo en el formulario.

**Integrar en un workflow existente:** añade un job que use `actions/checkout` y `actions/setup-python`, y en un paso ejecuta:
`python repo_scorecard.py --path . --out text --min-score 50` (ajusta `50` a tu umbral).

## Cómo extender checks

1. **Definir una función** que reciba `root: Path` y devuelva un `CheckResult`:

```python
def check_mi_check(root: Path) -> CheckResult:
    weight = 5
    if (root / "mi_archivo.txt").is_file():
        return CheckResult("mi_check", "Descripción", weight, True, "mi_archivo.txt")
    return CheckResult("mi_check", "Descripción", weight, False, "")
```

2. **Registrar el check** en `run_all_checks()` añadiendo la función a la lista `runners`:

```python
def run_all_checks(root: Path) -> list[CheckResult]:
    runners = [
        check_readme,
        # ...
        check_mi_check,  # nuevo
    ]
    return [fn(root) for fn in runners]
```

3. **Ajustar el total de puntos** si quieres mantener 100 como máximo: reduce pesos de otros checks o reparte el nuevo peso (el score seguirá siendo la suma de pesos pasados; si el total supera 100, el score puede ser >100 hasta que normalices).

## Ejemplo de salida JSON

```json
{
  "repoPath": "D:\\Git\\mi-repo",
  "score": 45,
  "passed": 4,
  "failed": 6,
  "checks": [
    {
      "id": "readme",
      "name": "README existe",
      "weight": 10,
      "passed": true,
      "evidence": "README.md"
    },
    {
      "id": "license",
      "name": "LICENSE existe",
      "weight": 5,
      "passed": true,
      "evidence": "LICENSE"
    },
    {
      "id": "ci",
      "name": "CI configurado",
      "weight": 15,
      "passed": true,
      "evidence": ".github/workflows/ci.yml"
    },
    {
      "id": "docker",
      "name": "Docker presente",
      "weight": 10,
      "passed": true,
      "evidence": "Dockerfile"
    }
  ],
  "timestamp": "2026-02-23T12:00:00Z"
}
```

## Ejemplo de salida text

```
repo_scorecard - D:\Git\mi-repo
Score: 45/100  Passed: 4  Failed: 6  (2026-02-23T12:00:00Z)
+------------+----------------------------+--------+------+--------------------------------------------+
| ID         | Name                       | Weight |  OK  | Evidence                                   |
+------------+----------------------------+--------+------+--------------------------------------------+
| readme     | README existe              |   10   | yes  | README.md                                  |
| license    | LICENSE existe             |   5    | yes  | LICENSE                                    |
| codeowners | CODEOWNERS existe          |   10   |  no  | -                                          |
| ci         | CI configurado             |   15   | yes  | .github/workflows/ci.yml                   |
| tests      | Tests presentes            |   15   |  no  | -                                          |
| linter     | Linter config              |   10   |  no  | -                                          |
| docker     | Docker presente            |   10   | yes  | Dockerfile                                 |
| security   | Security docs/config       |   10   |  no  | -                                          |
| observabil | OpenTelemetry en deps/conf |   5    |  no  | -                                          |
| release    | Release hygiene            |   10   |  no  | -                                          |
+------------+----------------------------+--------+------+--------------------------------------------+
```

## Errores

- **Ruta no existe:** mensaje a stderr y código de salida 1.
- **Ruta no es directorio:** igual.
- **Sin permiso de lectura:** se omite el directorio problemático o se informa según el caso; el script puede terminar con 1 si no puede leer la raíz.

## Licencia

Incluido como ejemplo; usar según la licencia del proyecto donde se integre.
