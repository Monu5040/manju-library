from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = "core"
    verbose_name = "Core"

    def ready(self) -> None:
        from . import checks  # noqa: F401  (registers system checks)
