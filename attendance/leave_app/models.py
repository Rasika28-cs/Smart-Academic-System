from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator

# ─────────────────────────────────────────────
# ACADEMIC CORE MODELS
# ─────────────────────────────────────────────

class Department(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10, unique=True)
    hod = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='managed_dept')

    def __str__(self):
        return f"{self.name} ({self.code})"

class Subject(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='subjects')
    credits = models.IntegerField(default=3)

    def __str__(self):
        return f"{self.code} - {self.name}"

# ─────────────────────────────────────────────
# STUDENT MODEL (Updated with Dept/Batch)
# ─────────────────────────────────────────────

class Student(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True, related_name='student_profile')
    name = models.CharField(max_length=100)
    roll_no = models.CharField(max_length=20, unique=True)
    password = models.CharField(max_length=255) # Legacy field
    batch = models.CharField(max_length=20, default="2024-2028")
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)
    mentor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_students')

    def __str__(self):
        return f"{self.name} ({self.roll_no})"

# ─────────────────────────────────────────────
# LEAVE REQUEST MODEL (Hierarchical Workflow)
# ─────────────────────────────────────────────

class LeaveRequest(models.Model):
    STATUS_CHOICES = [
        ('PENDING_MENTOR', 'Pending Mentor Approval'),
        ('APPROVED_BY_MENTOR', 'Approved by Mentor (Pending CI)'),
        ('REJECTED_BY_MENTOR', 'Rejected by Mentor'),
        ('PENDING_CLASSINCHARGE', 'Pending Class Incharge'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]

    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    reason = models.TextField()
    from_date = models.DateField()
    to_date = models.DateField()
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='PENDING_MENTOR')

    # Mentor Review Fields
    mentor_reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='mentor_reviews')
    mentor_reviewed_at = models.DateTimeField(null=True, blank=True)
    mentor_remark = models.TextField(null=True, blank=True)

    # Class Incharge Review Fields
    class_incharge_reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='ci_reviews')
    class_incharge_reviewed_at = models.DateTimeField(null=True, blank=True)
    class_incharge_remark = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student.name} - {self.status}"

# ─────────────────────────────────────────────
# ATTENDANCE MODEL
# ─────────────────────────────────────────────

class Attendance(models.Model):
    STATUS_CHOICES = [('Present', 'Present'), ('Leave', 'Leave'), ('Absent', 'Absent')]
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.SET_NULL, null=True, blank=True)
    date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)

    def __str__(self):
        return f"{self.student.name} - {self.date} - {self.status}"

# ─────────────────────────────────────────────
# ACADEMIC MODULES (Assignments, Timetable, Exams)
# ─────────────────────────────────────────────

class Timetable(models.Model):
    DAYS = [('Mon', 'Monday'), ('Tue', 'Tuesday'), ('Wed', 'Wednesday'), ('Thu', 'Thursday'), ('Fri', 'Friday'), ('Sat', 'Saturday')]
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    batch = models.CharField(max_length=20)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    teacher = models.ForeignKey(User, on_delete=models.CASCADE)
    day = models.CharField(max_length=3, choices=DAYS)
    start_time = models.TimeField()
    end_time = models.TimeField()
    room = models.CharField(max_length=20, blank=True)

class Assignment(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    batch = models.CharField(max_length=20)
    due_date = models.DateTimeField()
    file = models.FileField(upload_to='assignments/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

class Exam(models.Model):
    TYPE_CHOICES = [('Internal 1', 'Internal 1'), ('Internal 2', 'Internal 2'), ('Model', 'Model'), ('University', 'University')]
    name = models.CharField(max_length=100)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    exam_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    date = models.DateField()
    max_marks = models.IntegerField(default=100)

class Result(models.Model):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE)
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    marks_obtained = models.FloatField()
    is_present = models.BooleanField(default=True)

# ─────────────────────────────────────────────
# NOTIFICATIONS & COMMUNICATION
# ─────────────────────────────────────────────

class Notification(models.Model):
    TYPE_CHOICES = (('leave', 'Leave'), ('od', 'OD'), ('academic', 'Academic'), ('circular', 'Circular'))
    title = models.CharField(max_length=255)
    message = models.TextField()
    type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    users = models.ManyToManyField(User, related_name='notifications')
    read_by = models.ManyToManyField(User, related_name='read_notifications', blank=True)
    url = models.CharField(max_length=255, blank=True)

class Circular(models.Model):
    title = models.CharField(max_length=255)
    content = models.TextField()
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)
    file = models.FileField(upload_to='circulars/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

# ─────────────────────────────────────────────
# DEFAULTERS & AUDIT
# ─────────────────────────────────────────────

class DefaulterStudent(models.Model):
    roll_no = models.CharField(max_length=20)
    name = models.CharField(max_length=100)
    staff_incharge = models.CharField(max_length=100)
    department = models.CharField(max_length=10)
    year = models.IntegerField()
    reason = models.TextField()
    action_taken = models.CharField(max_length=30, null=True, blank=True)

class ActivityLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    action = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True)

class ParentProfile(models.Model):
    student = models.OneToOneField(Student, on_delete=models.CASCADE, related_name='parent')
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone_number = models.CharField(max_length=15)