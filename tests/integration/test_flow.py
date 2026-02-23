"""Tests de integración: flujo que combina módulos."""

import pytest

from app_prueba import add, greet
from app_prueba.store import Store


@pytest.mark.integration
def test_calc_and_store_together() -> None:
    """Flujo: resultados de calc se guardan en Store."""
    store = Store()
    store.set("sum", str(add(10, 20)))
    store.set("greeting", greet("CI"))
    assert store.get("sum") == "30"
    assert store.get("greeting") == "Hello, CI!"


@pytest.mark.integration
def test_store_multiple_keys_workflow() -> None:
    """Flujo: múltiples operaciones sobre el mismo Store."""
    store = Store()
    for i in range(3):
        store.set(f"key_{i}", str(add(i, 1)))
    assert store.keys() == ["key_0", "key_1", "key_2"]
    assert store.get("key_1") == "2"
