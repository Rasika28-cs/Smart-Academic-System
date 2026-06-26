from datetime import timedelta

from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.utils import timezone

from leave_app.models import LeaveRequest


class Command(BaseCommand):
    help = "Send hourly leave request summary to staff"

    def handle(self, *args, **kwargs):
        now = timezone.now()

        # Last 1 hour
        one_hour_ago = now - timedelta(days=365)

        # -------- FOR TESTING ONLY --------
        # Uncomment this line and comment the above line
        # to include all leave requests from the last year.
        #
        # one_hour_ago = now - timedelta(days=365)
        # ---------------------------------

        leaves = (
            LeaveRequest.objects.filter(
                created_at__gte=one_hour_ago,
                created_at__lt=now,
            )
            .select_related("student")
            .order_by("created_at")
        )

        if not leaves.exists():
            self.stdout.write(
                self.style.WARNING("No new leave requests found.")
            )
            return

        # All active staff users with email addresses
        staff_emails = list(
            User.objects.filter(
                is_staff=True,
                is_active=True
            )
            .exclude(email="")
            .values_list("email", flat=True)
            .distinct()
        )

        if not staff_emails:
            self.stdout.write(
                self.style.ERROR("No staff email addresses found.")
            )
            return

        body = []
        body.append("SMART ACADEMIC STUDENT SYSTEM")
        body.append("=" * 60)
        body.append("HOURLY LEAVE REQUEST SUMMARY")
        body.append("")
        body.append(
            f"Generated : {now.strftime('%d-%m-%Y %I:%M %p')}"
        )
        body.append(f"Total Requests : {leaves.count()}")
        body.append("")
        body.append("=" * 60)
        body.append("")

        for i, leave in enumerate(leaves, start=1):
            body.append(f"{i}. Student Name : {leave.student.name}")
            body.append(f"   Roll No      : {leave.student.roll_no}")
            body.append(f"   Register No  : {leave.student.reg_no}")
            body.append(f"   From Date    : {leave.from_date}")
            body.append(f"   To Date      : {leave.to_date}")
            body.append(f"   Status       : {leave.status}")
            body.append(f"   Reason       : {leave.reason}")
            body.append("-" * 60)

        send_mail(
            subject=f"Hourly Leave Summary ({leaves.count()} Request(s))",
            message="\n".join(body),
            from_email=None,  # Uses DEFAULT_FROM_EMAIL
            recipient_list=staff_emails,
            fail_silently=False,
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Summary email sent successfully to {len(staff_emails)} staff member(s)."
            )
        )