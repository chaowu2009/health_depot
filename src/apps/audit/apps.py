from django.apps import AppConfig


class AuditConfig(AppConfig):
    name = "apps.audit"
    label = "audit"
    verbose_name = "Audit log"

    def ready(self) -> None:
        from . import signals

        signals.connect_model_signals()
        signals.connect_permission_signals()
