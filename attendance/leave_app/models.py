from django.db import models
from django.contrib.auth.models import User


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
