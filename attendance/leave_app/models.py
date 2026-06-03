from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

# ─────────────────────────────
# DEPARTMENT
# ─────────────────────────────

class Department(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10, unique=True)
    hod = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='managed_dept'
    )

    def __str__(self):
        return f"{self.name} ({self.code})"


# ─────────────────────────────
# SUBJECT
# ─────────────────────────────

class Subject(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='subjects')
    credits = models.IntegerField(default=3)

    def __str__(self):
        return f"{self.code} - {self.name}"


# ─────────────────────────────
# STUDENT
# ─────────────────────────────

class Student(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True, related_name='student_profile')
    name = models.CharField(max_length=100)
    roll_no = models.CharField(max_length=20, unique=True)
    reg_no = models.CharField(max_length=30, unique=True)
    password = models.CharField(max_length=255)
    batch = models.CharField(max_length=20, default="2024-2028")

    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)

    mentor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_students')
    class_incharge = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='ci_students')

    def __str__(self):
        return f"{self.name} ({self.roll_no})"


from django.db import models
from django.contrib.auth.models import User

class LeaveRequest(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]

    REVIEWER_CHOICES = [
        ('Mentor', 'Mentor'),
        ('Class Incharge', 'Class Incharge'),
        ('Superuser', 'Superuser'),
    ]

    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    from_date = models.DateField()
    to_date = models.DateField()
    reason = models.TextField()

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING'
    )

    # Legacy tracking fields
    mentor_reviewed_by = models.ForeignKey(
        User,
        related_name='mentor_reviews',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    class_incharge_reviewed_by = models.ForeignKey(
        User,
        related_name='ci_reviews',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    # Unified audit fields
    reviewed_by = models.ForeignKey(
        User,
        related_name='reviewed_leaves',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    reviewer_role = models.CharField(
        max_length=20,
        choices=REVIEWER_CHOICES,
        null=True,
        blank=True
    )

    reviewed_at = models.DateTimeField(
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.student.roll_no} - {self.status}"
    
    
# ─────────────────────────────
# ATTENDANCE (FIXED)
# ─────────────────────────────

class Attendance(models.Model):
    STATUS_CHOICES = [
        ('Present', 'Present'),
        ('Leave', 'Leave'),
        ('Absent', 'Absent')
    ]

    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.SET_NULL, null=True, blank=True)
    date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)

    class Meta:
        unique_together = ('student', 'subject', 'date')

    def __str__(self):
        return f"{self.student.name} - {self.date} - {self.status}"


# ─────────────────────────────
# TIMETABLE (FIXED)
# ─────────────────────────────

class Timetable(models.Model):
    DAYS = [
        ('Mon', 'Monday'),
        ('Tue', 'Tuesday'),
        ('Wed', 'Wednesday'),
        ('Thu', 'Thursday'),
        ('Fri', 'Friday'),
        ('Sat', 'Saturday'),
    ]

    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    batch = models.CharField(max_length=20)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    teacher = models.ForeignKey(User, on_delete=models.CASCADE)
    day = models.CharField(max_length=3, choices=DAYS)
    start_time = models.TimeField()
    end_time = models.TimeField()
    room = models.CharField(max_length=20, blank=True)

    def clean(self):
        clash = Timetable.objects.filter(
            day=self.day,
            room=self.room,
            start_time__lt=self.end_time,
            end_time__gt=self.start_time
        ).exclude(pk=self.pk)

        if clash.exists():
            raise ValidationError("Room is already occupied at this time.")


# ─────────────────────────────
# ASSIGNMENT
# ─────────────────────────────

class Assignment(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    batch = models.CharField(max_length=20)
    due_date = models.DateTimeField()
    file = models.FileField(upload_to='assignments/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


# ─────────────────────────────
# ASSIGNMENT SUBMISSION (NEW FIXED)
# ─────────────────────────────

class AssignmentSubmission(models.Model):
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name='submissions')
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    file = models.FileField(upload_to='submissions/')
    submitted_at = models.DateTimeField(auto_now_add=True)
    marks = models.FloatField(null=True, blank=True)
    feedback = models.TextField(null=True, blank=True)

    class Meta:
        unique_together = ('assignment', 'student')


# ─────────────────────────────
# EXAM
# ─────────────────────────────

class Exam(models.Model):
    TYPE_CHOICES = [
        ('Internal 1', 'Internal 1'),
        ('Internal 2', 'Internal 2'),
        ('Model', 'Model'),
        ('University', 'University')
    ]

    name = models.CharField(max_length=100)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    exam_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    date = models.DateField()
    max_marks = models.IntegerField(default=100)


# ─────────────────────────────
# RESULT (FIXED)
# ─────────────────────────────

class Result(models.Model):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE)
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    marks_obtained = models.FloatField()
    is_present = models.BooleanField(default=True)

    class Meta:
        unique_together = ('exam', 'student')


# ─────────────────────────────
# NOTIFICATION
# ─────────────────────────────

class Notification(models.Model):
    TYPE_CHOICES = (
        ('leave', 'Leave'),
        ('od', 'OD'),
        ('academic', 'Academic'),
        ('circular', 'Circular')
    )

    title = models.CharField(max_length=255)
    message = models.TextField()
    type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    users = models.ManyToManyField(User, related_name='notifications')
    read_by = models.ManyToManyField(User, related_name='read_notifications', blank=True)
    url = models.CharField(max_length=255, blank=True)


# ─────────────────────────────
# CIRCULAR
# ─────────────────────────────

class Circular(models.Model):
    title = models.CharField(max_length=255)
    content = models.TextField()
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)
    file = models.FileField(upload_to='circulars/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


# ─────────────────────────────
# DEFAULTERS
# ─────────────────────────────

class DefaulterStudent(models.Model):
    roll_no = models.CharField(max_length=20)
    name = models.CharField(max_length=100)
    staff_incharge = models.CharField(max_length=100)
    department = models.CharField(max_length=10)
    year = models.IntegerField()
    reason = models.TextField()
    action_taken = models.CharField(max_length=30, null=True, blank=True)


# ─────────────────────────────
# ACTIVITY LOG
# ─────────────────────────────

class ActivityLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    action = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True)


# ─────────────────────────────
# PARENT PROFILE
# ─────────────────────────────

class ParentProfile(models.Model):
    student = models.OneToOneField(Student, on_delete=models.CASCADE, related_name='parent')
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone_number = models.CharField(max_length=15)



from django.db import models
from django.contrib.auth.models import User
from leave_app.models import Student   # ✅ IMPORTANT FIX (must import)


class GradeUpload(models.Model):
    title = models.CharField(max_length=150)
    semester = models.IntegerField()
    uploaded_file = models.FileField(upload_to='grades/')
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class StudentGrade(models.Model):
    upload = models.ForeignKey(
        GradeUpload,
        on_delete=models.CASCADE,
        related_name='grades'
    )

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='grades'   # ✅ helps reverse queries
    )

    subject_code = models.CharField(max_length=50)
    subject_name = models.CharField(max_length=150, blank=True, null=True)

    grade = models.CharField(max_length=5)

    class Meta:
        unique_together = ('upload', 'student', 'subject_code')

    def __str__(self):
        return f"{self.student.roll_no} - {self.subject_code}"
    
