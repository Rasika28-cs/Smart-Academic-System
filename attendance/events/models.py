from django.db import models
from django.conf import settings


class Event(models.Model):
    college_name = models.CharField(max_length=100)
    event_name = models.CharField(max_length=100)
    event_date = models.DateField()
    brochure = models.FileField(upload_to='brochures/', blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    def __str__(self):
        return self.event_name
