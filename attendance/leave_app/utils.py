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