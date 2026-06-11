from django.db import models
from django.conf import settings

class Event(models.Model):
    college_name = models.CharField(max_length=100)
    event_name = models.CharField(max_length=100)
    event_date = models.DateField()

    batch = models.CharField(max_length=20)   # NEW

    brochure = models.FileField(
        upload_to='brochures/'
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )