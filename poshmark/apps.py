from django.apps import AppConfig


class PoshmarkConfig(AppConfig):
    name = 'poshmark'

    def ready(self):
        import poshmark.signals
