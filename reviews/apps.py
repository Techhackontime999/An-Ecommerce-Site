from django.apps import AppConfig


class ReviewsConfig(AppConfig):
    name = 'reviews'

    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self):
        import reviews.signals


