import os

environment = os.getenv("DJANGO_ENV", "production")

if environment == "production":
    from .production import *
else:
    from .local import *
