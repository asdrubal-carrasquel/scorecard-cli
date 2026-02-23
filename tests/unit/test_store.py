"""Tests unitarios de app_prueba.store."""

import pytest

from app_prueba.store import Store


@pytest.mark.unit
class TestStore:
    def test_set_get(self) -> None:
        s = Store()
        s.set("a", "1")
        assert s.get("a") == "1"

    def test_get_missing_returns_none(self) -> None:
        s = Store()
        assert s.get("x") is None

    def test_keys_empty(self) -> None:
        s = Store()
        assert s.keys() == []

    def test_keys_after_set(self) -> None:
        s = Store()
        s.set("k1", "v1")
        s.set("k2", "v2")
        assert set(s.keys()) == {"k1", "k2"}
