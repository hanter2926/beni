from django.conf import settings
from django.db import models


class Notification(models.Model):
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='notifications',
    )
    event_key = models.CharField(max_length=200)
    title = models.CharField(max_length=160)
    message = models.CharField(max_length=500)
    destination_url = models.CharField(max_length=500, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ('-created_at', '-pk')
        constraints = [
            models.UniqueConstraint(
                fields=('recipient', 'event_key'),
                name='notification_recipient_event_unique',
            ),
        ]
        indexes = [
            models.Index(
                fields=('recipient', 'read_at', 'created_at'),
                name='notification_inbox_idx',
            ),
        ]

    def __str__(self):
        return self.title
