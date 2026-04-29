from chatbi_core.component import BaseComponent, SystemApp


class DemoComponent(BaseComponent):
    name = "demo"

    def __init__(self):
        self.events: list[str] = []

    def init_app(self, system_app: SystemApp) -> None:
        self.system_app = system_app
        self.events.append("init")

    def on_init(self) -> None:
        self.events.append("on_init")

    def after_init(self) -> None:
        self.events.append("after_init")

    def before_stop(self) -> None:
        self.events.append("before_stop")


def test_system_app_registers_components_and_runs_lifecycle():
    app = SystemApp()
    component = DemoComponent()

    app.register_instance(component)
    assert app.get_component("demo", DemoComponent) is component
    assert app.has_component("demo") is True

    app.on_init()
    app.after_init()
    app.before_stop()

    assert component.events == ["init", "on_init", "after_init", "before_stop"]
