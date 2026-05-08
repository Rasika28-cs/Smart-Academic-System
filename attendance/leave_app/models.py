from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Student(models.Model):
    """
    Represents a student profile linked 1-to-1 to a Django User.
    username = roll_no  (used for Django auth)
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='student_profile'
    )
    name = models.CharField(max_length=100)
    roll_no = models.CharField(max_length=20, unique=True)
    password = models.CharField(max_length=255)  # kept for legacy data; auth is via User

    def __str__(self):
        return f"{self.name} ({self.roll_no})"




class LeaveRequest(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
    ]

    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    reason = models.TextField()
    from_date = models.DateField()
    to_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    
    created_at = models.DateTimeField(auto_now_add=True) 
    def __str__(self):
        return f"{self.student.name} - {self.status}"




class Attendance(models.Model):
    STATUS_CHOICES = [
    ('Present', 'Present'),
    ('Leave', 'Leave'),
    ('Absent', 'Absent'),
]

    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)

    def __str__(self):
        return f"{self.student.name} - {self.date} - {self.status}"


class Teacher(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=100)

    def __str__(self):
        return self.name






from django.db import models
from django.contrib.auth.models import User

class Notification(models.Model):
    TYPE_CHOICES = (
        ('leave', 'Leave'),
        ('od', 'OD'),
    )

    title = models.CharField(max_length=255)
    message = models.TextField()
    type = models.CharField(max_length=10, choices=TYPE_CHOICES)

    created_at = models.DateTimeField(auto_now_add=True)

    # Who should see this
    users = models.ManyToManyField(User, related_name="notifications")

    # Who has read this
    read_by = models.ManyToManyField(User, related_name="read_notifications", blank=True)

    # Redirect URL
    url = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return self.title
    






class DefaulterStudent(models.Model):
    roll_no = models.CharField(max_length=20)
    name = models.CharField(max_length=100)
    staff_incharge = models.CharField(max_length=100)
    department = models.CharField(max_length=10)
    year = models.IntegerField()
    reason = models.TextField()

    ACTION_CHOICES = [
        ('letter', 'Letter'),
        ('letter_seminar', 'Letter + Seminar'),
        ('letter_assignment', 'Letter + Assignment'),
    ]

    action_taken = models.CharField(
        max_length=30,
        choices=ACTION_CHOICES,
        null=True,
        blank=True
    )

    