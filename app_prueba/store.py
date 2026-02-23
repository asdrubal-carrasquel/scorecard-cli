"""Store mínimo para tests de integración."""


class Store:
    """Almacén en memoria clave -> valor."""

    def __init__(self) -> None:
        self._data: dict[str, str] = {}

    def set(self, key: str, value: str) -> None:
        self._data[key] = value

    def get(self, key: str) -> str | None:
        return self._data.get(key)

    def keys(self) -> list[str]:
        return list(self._data.keys())
