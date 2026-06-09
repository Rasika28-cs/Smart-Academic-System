from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from django.urls import reverse

from leave_app.models import Assignment, Student, Notification


class Command(BaseCommand):
    help = "Send assignment reminder notifications"

    def handle(self, *args, **options):

        tomorrow = timezone.now().date() + timedelta(days=1)

        print("Tomorrow:", tomorrow)

        count = Assignment.objects.filter(
            due_date__date=tomorrow
        ).count()

        print("Assignments due tomorrow:", count)

        assignments = Assignment.objects.filter(
            due_date__date=tomorrow
        )

        for assignment in assignments:

            reminder_msg = f"{assignment.title} is due tomorrow."

            exists = Notification.objects.filter(
                type="assignment_reminder",
                message=reminder_msg
            ).exists()

            if exists:
                continue

            students = Student.objects.filter(
                batch=assignment.batch
            ).select_related("user")

            recipient_users = [
                s.user for s in students if s.user
            ]

            if recipient_users:

                notif = Notification.objects.create(
                    title="Assignment Due Tomorrow",
                    message=reminder_msg,
                    type="assignment_reminder",
                    url=reverse("assignment_list")
                )

                notif.users.add(*recipient_users)

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Reminder sent for: {assignment.title}"
                    )
                )