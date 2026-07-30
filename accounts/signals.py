from django.contrib.auth.models import Group
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User


@receiver(post_save, sender=User)
def add_user_to_customers_group(sender, instance, created, **kwargs):
    if created:
        group, _ = Group.objects.get_or_create(name='customers')
        instance.groups.add(group)
