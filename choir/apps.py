from django.apps import AppConfig


class ChoirConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "choir"

    def ready(self):
        # This imports the signals file when Django boots, activating the triggers
        import choir.signals  # noqa
