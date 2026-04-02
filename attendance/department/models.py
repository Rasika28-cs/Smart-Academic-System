from django.db import models


# ─────────────────────────────────────────────────────────
# EXISTING MODELS — UNCHANGED
# ─────────────────────────────────────────────────────────

class Staff(models.Model):
    ROLE_CHOICES = [
        ('HOD', 'Head of Department'),
        ('Professor', 'Professor'),
        ('Associate Professor', 'Associate Professor'),
        ('Assistant Professor', 'Assistant Professor'),
        ('Lab Instructor', 'Lab Instructor'),
    ]
    name = models.CharField(max_length=100)
    role = models.CharField(max_length=50, choices=ROLE_CHOICES, default='Assistant Professor')
    qualification = models.CharField(max_length=200)
    email = models.EmailField(blank=True)
    image = models.ImageField(upload_to='staff/', blank=True, null=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']

    def __str__(self):
        return f"{self.name} ({self.role})"


class Achievement(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    date = models.DateField()
    image = models.ImageField(upload_to='achievements/', blank=True, null=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return self.title


class Winner(models.Model):
    POSITION_CHOICES = [
        ('1st', '1st Place'),
        ('2nd', '2nd Place'),
        ('3rd', '3rd Place'),
        ('Participant', 'Participant'),
        ('Special Award', 'Special Award'),
    ]
    event_name = models.CharField(max_length=200)
    student_name = models.CharField(max_length=100)
    position = models.CharField(max_length=20, choices=POSITION_CHOICES, default='1st')
    date = models.DateField()
    image = models.ImageField(upload_to='winners/', blank=True, null=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"{self.student_name} – {self.position} @ {self.event_name}"


# ─────────────────────────────────────────────────────────
# NEW MODELS — for Homepage Gallery / News / Events
# ─────────────────────────────────────────────────────────

class Gallery(models.Model):
    title = models.CharField(max_length=200, blank=True)
    image = models.ImageField(upload_to='gallery/')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Gallery Image'
        verbose_name_plural = 'Gallery Images'

    def __str__(self):
        return self.title if self.title else f"Gallery Image #{self.pk}"


class NewsItem(models.Model):
    title = models.CharField(max_length=300)
    description = models.TextField()
    date = models.DateField()
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-date']
        verbose_name = 'News Item'
        verbose_name_plural = 'News Items'

    def __str__(self):
        return self.title


class UpcomingEvent(models.Model):
    title = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    date = models.DateField()
    venue = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['date']
        verbose_name = 'Upcoming Event'
        verbose_name_plural = 'Upcoming Events'

    def __str__(self):
        return self.title