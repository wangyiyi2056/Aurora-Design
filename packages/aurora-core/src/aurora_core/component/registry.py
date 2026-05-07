from typing import Any, Dict, TypeVar

T = TypeVar("T")


class ComponentRegistry:
    """Minimal SystemApp registry for Phase 1. Will expand in later phases."""

    def __init__(self):
        self._components: Dict[str, Any] = {}

    def register(self, name: str, component: Any) -> None:
        self._components[name] = component

    def get(self, name: str, expected_type: type[T] | None = None) -> T:
        comp = self._components.get(name)
        if comp is None:
            raise KeyError(f"Component '{name}' not registered")
        if expected_type is not None and not isinstance(comp, expected_type):
            raise TypeError(f"Component '{name}' is not of type {expected_type}")
        return comp

    def has(self, name: str) -> bool:
        return name in self._components
