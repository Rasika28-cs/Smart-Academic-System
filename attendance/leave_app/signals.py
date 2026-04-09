from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings

from .models import LeaveRequest, Teacher
from od.models import ODApplication   # adjust if needed


# 🔔 COMMON FUNCTION (Reusable)
def get_teacher_emails():
    return list(Teacher.objects.values_list('email', flat=True))


# ============================
# 📩 LEAVE NOTIFICATION
# ============================
@receiver(post_save, sender=LeaveRequest)
def notify_staff_leave(sender, instance, created, **kwargs):
    if created:
        teacher_emails = get_teacher_emails()

        # Safety check
        if not teacher_emails:
            return

        student_name = instance.student.name
        roll_no = instance.student.roll_no

        total_days = (instance.to_date - instance.from_date).days + 1

        message = f"""
New Leave Request 📩

Student Name: {student_name}
Roll No: {roll_no}
From Date: {instance.from_date}
To Date: {instance.to_date}
Total Days: {total_days}

Reason:
{instance.reason}

Please review in staff panel.
"""

        send_mail(
            "New Leave Request 📩",
            message,
            settings.EMAIL_HOST_USER,
            teacher_emails,
            fail_silently=False,
        )


# ============================
# 📩 OD NOTIFICATION
# ============================
@receiver(post_save, sender=ODApplication)
def notify_staff_od(sender, instance, created, **kwargs):
    if created:
        teacher_emails = get_teacher_emails()

        # Safety check
        if not teacher_emails:
            return

        student_name = instance.student.name
        roll_no = instance.student.roll_no

        message = f"""
New OD Request 📩

Student Name: {student_name}
Roll No: {roll_no}
Event: {instance.event.event_name}
College: {instance.event.college_name}
Date: {instance.date}

Please review in staff panel.
"""

        send_mail(
            "New OD Request 📩",
            message,
            settings.EMAIL_HOST_USER,
            teacher_emails,
            fail_silently=False,
        )


