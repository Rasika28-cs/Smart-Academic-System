import traceback
from typing import Iterable, Union
from django.contrib.auth.models import User
from .models import Notification


def send_notification(
    *,
    title: str,
    message: str,
    notif_type: str,
    url: str = "",
    users: Union[User, Iterable[User]] = None
):
    """
    Centralized safe notification dispatcher
    Prevents missing users / inconsistent .add() usage
    """

    if users is None:
        return None

    if isinstance(users, User):
        users = [users]

    users = [u for u in users if u]  # remove None safely

    notif = Notification.objects.create(
        title=title,
        message=message,
        type=notif_type,
        url=url
    )

    notif.users.add(*users)

    return notif
import resend
import os
import logging
from django.contrib.auth.models import User

logger = logging.getLogger(__name__)

# Set API key ONCE (safe for Render + local)
resend.api_key = os.environ.get("RESEND_API_KEY")


def send_leave_email(student, from_date, to_date, reason):
    try:
        mentor_emails = list(
            User.objects.filter(groups__name="Mentor", is_active=True)
            .exclude(email="")
            .values_list("email", flat=True)
            .distinct()
        )

        if not mentor_emails:
            return

        resend.Emails.send({
            "from": "Leave System <onboarding@resend.dev>",
            "to": mentor_emails,
            "subject": "New Leave Request",
            "html": f"""
                <h2>New Leave Request</h2>
                <p><b>Student:</b> {student.name}</p>
                <p><b>From:</b> {from_date}</p>
                <p><b>To:</b> {to_date}</p>
                <p><b>Reason:</b> {reason}</p>
            """
        })

    except Exception:
        logger.exception("Failed to send leave email")