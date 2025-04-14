from django.contrib.auth.models import Group
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User

@receiver(post_save, sender=User)
def add_user_to_customers_group(sender, instance, created, **kwargs):
    if created:  # only run this when a new user is created
        group = Group.objects.get(name='customers')  # Retrieve the 'customers' group
        instance.groups.add(group)  # Add the user to the group
        instance.save()
@receiver(post_save, sender=User)
def add_user_to_sellers_group(sender, instance, created, **kwargs):
    if created:  # only run this when a new user is created
        group = Group.objects.get(name='sellers')  # Retrieve the 'customers' group
        instance.groups.add(group)  # Add the user to the group
        instance.save()