from django.db import models


class Subscriber(models.Model):
    email = models.EmailField(unique=True)
    is_active = models.BooleanField(
        default=False,
        help_text='Only confirmed (double opt-in) subscribers are active.',
    )
    is_confirmed = models.BooleanField(
        default=False,
        help_text='True once the subscriber clicked the confirmation link in the '
                  'double opt-in email. The single source of consent.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return self.email
