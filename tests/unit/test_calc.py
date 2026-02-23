"""Tests unitarios de app_prueba.calc."""

import pytest

from app_prueba.calc import add, greet


@pytest.mark.unit
class TestAdd:
    def test_add_positive(self) -> None:
        assert add(2, 3) == 5

    def test_add_zero(self) -> None:
        assert add(0, 0) == 0

    def test_add_negative(self) -> None:
        assert add(-1, 1) == 0


@pytest.mark.unit
class TestGreet:
    def test_greet_returns_hello_name(self) -> None:
        assert greet("World") == "Hello, World!"

    def test_greet_empty(self) -> None:
        assert greet("") == "Hello, !"
