"""App de prueba para validar scorecard y flujo CI (unit + integration tests)."""

__version__ = "0.1.0"

from app_prueba.calc import add, greet
from app_prueba.store import Store

__all__ = ["add", "greet", "Store", "__version__"]
