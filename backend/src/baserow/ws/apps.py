from django.apps import AppConfig


class WSConfig(AppConfig):
    name = "baserow.ws"

    def ready(self):
        import baserow.ws.signals  # noqa: F403, F401
