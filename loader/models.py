"""Singleton configuration model for the Shop-Seed Loader Experience System.

Phase 1 keeps a single row (pk=1) with everything the Loader Engine needs to
know: whether loaders are enabled, which animation plays on first load and on
navigation, the brand mark, colours, timing, exit animation and the display /
performance toggles. Later phases (presets, scheduling, analytics) grow from
here without changing the engine contract.
"""

from django.db import models

INITIAL_TYPES = [
    ('seed', 'Seed Grow — brand intro'),
    ('logo', 'Logo Reveal'),
    ('spinner', 'Minimal Spinner'),
    ('progress', 'Progress Bar'),
    ('skeleton', 'Skeleton Screen — page preview'),
    ('none', 'No initial loader'),
]

NAVIGATION_TYPES = [
    ('progress', 'Slim Progress Bar'),
    ('logo', 'Mini Logo'),
    ('none', 'No navigation loader'),
]

EXIT_ANIMATIONS = [
    ('fade', 'Fade out'),
    ('zoom', 'Zoom out'),
    ('slide', 'Slide up'),
    ('none', 'Instant'),
]

SHOW_ON_CHOICES = [
    ('first_visit', 'First visit only'),
    ('every_visit', 'Every page load'),
    ('once_per_session', 'Once per session'),
]


class LoaderConfig(models.Model):
    """The single, site-wide loader configuration (singleton, pk=1)."""

    # ---- Basic ----
    enabled = models.BooleanField(
        default=True,
        help_text='Master switch for the whole Loader Experience System.',
    )
    initial_type = models.CharField(
        max_length=20,
        choices=INITIAL_TYPES,
        default='seed',
        help_text='The animation shown while the first page of a visit loads.',
    )
    navigation_type = models.CharField(
        max_length=20,
        choices=NAVIGATION_TYPES,
        default='progress',
        help_text='Small, unobtrusive loader shown while navigating between pages.',
    )
    logo_image = models.ImageField(
        upload_to='loader/',
        blank=True,
        null=True,
        help_text='Optional custom logo. Leave empty to use the brand mark + site name.',
    )
    logo_text = models.CharField(
        max_length=60,
        blank=True,
        default='',
        help_text='Text under the logo. Leave empty to use the site name.',
    )
    background_color = models.CharField(
        max_length=9,
        default='#0c1017',
        help_text='Background colour of the loader screen.',
    )
    accent_color = models.CharField(
        max_length=9,
        default='#ff7a2f',
        help_text='Accent colour used by the animation and progress bar.',
    )
    duration_ms = models.PositiveIntegerField(
        default=1600,
        help_text='Target duration in milliseconds (400–6000). The loader can finish early when the page is ready.',
    )
    exit_animation = models.CharField(
        max_length=20,
        choices=EXIT_ANIMATIONS,
        default='fade',
        help_text='How the loader leaves the screen.',
    )
    show_on = models.CharField(
        max_length=20,
        choices=SHOW_ON_CHOICES,
        default='first_visit',
        help_text='When the initial loader plays. The large intro is not replayed on every page by default.',
    )

    # ---- Display ----
    device_desktop = models.BooleanField(default=True, help_text='Show loaders on desktop.')
    device_tablet = models.BooleanField(default=True, help_text='Show loaders on tablets.')
    device_mobile = models.BooleanField(default=True, help_text='Show loaders on phones.')

    # ---- Performance ----
    lightweight_mobile = models.BooleanField(
        default=True,
        help_text='Use the lightweight spinner on phones instead of the full animation.',
    )
    respect_reduced_motion = models.BooleanField(
        default=True,
        help_text='Skip the animation for visitors who prefer reduced motion.',
    )
    network_fallback = models.BooleanField(
        default=True,
        help_text='Use the lightweight spinner on slow / data-saving connections.',
    )
    skeleton_enabled = models.BooleanField(
        default=True,
        help_text='After the intro, show a page skeleton while content loads — makes the site feel faster.',
    )

    version = models.PositiveIntegerField(default=1, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Loader Configuration'
        verbose_name_plural = 'Loader Configuration'

    def __str__(self):
        return 'Loader Experience Configuration'

    def save(self, *args, **kwargs):
        # Enforce the singleton and bump the version so caches invalidate and
        # the frontend knows the config changed.
        self.pk = 1
        if self._state.adding:
            self.version = 1
        else:
            self.version = self.version + 1
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        obj = cls.objects.filter(pk=1).first()
        if obj is None:
            obj = cls.objects.create()
        return obj
