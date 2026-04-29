from __future__ import annotations

from abc import ABC
from typing import Any, Dict, Optional, Type, TypeVar


class LifeCycle:
    def on_init(self) -> None:
        pass

    def after_init(self) -> None:
        pass

    def before_stop(self) -> None:
        pass


class BaseComponent(LifeCycle, ABC):
    name = "base_component"

    def init_app(self, system_app: "SystemApp") -> None:
        self.system_app = system_app


class BaseService(BaseComponent):
    """Marker base class for service-layer components."""

    name = "base_service"


T = TypeVar("T", bound=BaseComponent)


class SystemApp(LifeCycle):
    """Lightweight component container inspired by DB-GPT's SystemApp."""

    def __init__(self, asgi_app: Optional[Any] = None):
        self.asgi_app = asgi_app
        self._components: Dict[str, Any] = {}

    def register_instance(self, component: T, name: str | None = None) -> T:
        component_name = name or getattr(component, "name", component.__class__.__name__)
        if hasattr(component, "init_app"):
            component.init_app(self)
        self._components[component_name] = component
        return component

    def register(self, component_cls: Type[T], *args: Any, **kwargs: Any) -> T:
        return self.register_instance(component_cls(*args, **kwargs))

    def get_component(
        self,
        name: str,
        expected_type: Type[T] | None = None,
        default: T | None = None,
    ) -> T:
        component = self._components.get(name)
        if component is None:
            if default is not None:
                return default
            raise KeyError(f"Component '{name}' not registered")
        if expected_type is not None and not isinstance(component, expected_type):
            raise TypeError(f"Component '{name}' is not of type {expected_type}")
        return component

    def has_component(self, name: str) -> bool:
        return name in self._components

    def on_init(self) -> None:
        for component in self._components.values():
            if hasattr(component, "on_init"):
                component.on_init()

    def after_init(self) -> None:
        for component in self._components.values():
            if hasattr(component, "after_init"):
                component.after_init()

    def before_stop(self) -> None:
        for component in reversed(list(self._components.values())):
            if hasattr(component, "before_stop"):
                component.before_stop()
