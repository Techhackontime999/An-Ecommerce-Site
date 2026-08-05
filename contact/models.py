
# Create your models here.
from django.contrib.auth.models import User
from django.db import models

class ContactMessage(models.Model):
    class Status(models.TextChoices):
        NEW = 'new', 'New'
        IN_PROGRESS = 'in_progress', 'In progress'
        RESOLVED = 'resolved', 'Resolved'
        CLOSED = 'closed', 'Closed'

    name = models.CharField(max_length=100)
    email = models.EmailField()
    subject = models.CharField(max_length=200)
    message = models.TextField()
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.NEW,
        db_index=True,
        help_text='Support workflow state of this message.',
    )
    handled_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='handled_messages',
        verbose_name='Handled by',
    )
    reply = models.TextField(blank=True, help_text='Your reply. Use the "Send reply email" action to deliver it.')
    replied_at = models.DateTimeField(null=True, blank=True)
    handled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return f"{self.name} - {self.subject}"

    @property
    def is_handled(self):
        return self.status in (self.Status.RESOLVED, self.Status.CLOSED)
