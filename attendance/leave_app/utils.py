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


from django.core.mail import send_mail
from django.contrib.auth.models import User
import logging

logger = logging.getLogger(__name__)

def send_leave_email(student, from_date, to_date, reason):
    """
    Sends leave email to all mentors.
    Never raises an exception.
    """

    try:
        mentor_emails = list(
            User.objects.filter(
                groups__name="Mentor",
                is_active=True
            )
            .exclude(email="")
            .values_list("email", flat=True)
            .distinct()
        )

        if not mentor_emails:
            return

        send_mail(
            subject="New Leave Request",
            message=(
                f"Student : {student.name}\n"
                f"From    : {from_date}\n"
                f"To      : {to_date}\n"
                f"Reason  : {reason}\n"
            ),
            from_email=None,
            recipient_list=mentor_emails,
            fail_silently=False,
        )

    except Exception:
        logger.exception("Failed to send leave email")