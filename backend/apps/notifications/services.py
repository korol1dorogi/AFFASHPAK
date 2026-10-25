"""In-app notifications for every member of the application's company."""

from django.contrib.auth.models import AbstractBaseUser

from apps.applications.models import Application
from apps.business.models import Membership
from apps.notifications.models import Notification


def notify_company(
    application: Application,
    *,
    kind: str,
    title: str,
    message: str = "",
    exclude: AbstractBaseUser | None = None,
    roles: tuple[str, ...] | None = None,
) -> int:
    """Create one notification per company member, except the user who caused it.
    `roles` narrows it to members with these MemberRole values (XP5: signatories only)."""
    memberships = Membership.objects.filter(company_id=application.company_id)
    if roles is not None:
        memberships = memberships.filter(role__in=roles)
    members = memberships.values_list("user_id", flat=True)
    exclude_id = getattr(exclude, "pk", None)
    notifications = [
        Notification(
            user_id=user_id, application=application, kind=kind, title=title, message=message
        )
        for user_id in members
        if user_id != exclude_id
    ]
    Notification.objects.bulk_create(notifications)
    return len(notifications)
