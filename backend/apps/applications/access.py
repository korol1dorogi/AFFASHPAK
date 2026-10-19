"""Who is acting and what they may see (docs/state-machine.md, «Роли»).

Clients see only applications of companies they are members of; bank users see all.
Anything outside that scope is reported as 404, never 403 (AGENTS.md, security 1).
"""

from dataclasses import dataclass

from django.contrib.auth.models import AbstractBaseUser, AnonymousUser
from django.db.models import QuerySet
from rest_framework.exceptions import NotFound

from apps.accounts.models import UserKind
from apps.applications.models import ActorKind, Application
from apps.business.models import MemberRole, Membership

NOT_FOUND = "Не найдено."


@dataclass(frozen=True)
class Actor:
    kind: str  # ActorKind
    user: AbstractBaseUser | None = None
    role: str | None = None  # MemberRole for clients

    @property
    def is_client(self) -> bool:
        return self.kind == ActorKind.CLIENT

    @property
    def is_signatory(self) -> bool:
        return self.is_client and self.role == MemberRole.SIGNATORY

    @property
    def is_bank(self) -> bool:
        return self.kind == ActorKind.BANK

    @property
    def is_system(self) -> bool:
        return self.kind == ActorKind.SYSTEM


SYSTEM = Actor(kind=ActorKind.SYSTEM)


def user_kind(user: AbstractBaseUser | AnonymousUser) -> str | None:
    if not user.is_authenticated:
        return None
    profile = getattr(user, "profile", None)
    return profile.kind if profile is not None else UserKind.CLIENT


def is_bank_user(user: AbstractBaseUser | AnonymousUser) -> bool:
    return user_kind(user) == UserKind.BANK


def client_applications(user: AbstractBaseUser) -> QuerySet[Application]:
    return Application.objects.filter(company__memberships__user=user).distinct()


def membership_for(user: AbstractBaseUser, company_id: int) -> Membership | None:
    return Membership.objects.filter(user=user, company_id=company_id).first()


def current_membership(user: AbstractBaseUser) -> Membership | None:
    """MVP: one company per client user — the first membership."""
    return Membership.objects.filter(user=user).select_related("company").first()


def actor_for(user: AbstractBaseUser, application: Application) -> Actor:
    """Actor for this user on this application; 404 if the application is out of scope."""
    if is_bank_user(user):
        return Actor(kind=ActorKind.BANK, user=user)
    membership = membership_for(user, application.company_id)
    if membership is None:
        raise NotFound(NOT_FOUND)
    return Actor(kind=ActorKind.CLIENT, user=user, role=membership.role)


def get_client_application(user: AbstractBaseUser, application_id: int) -> Application:
    application = client_applications(user).filter(pk=application_id).first()
    if application is None:
        raise NotFound(NOT_FOUND)
    return application


def get_bank_application(application_id: int) -> Application:
    """Bank views are guarded by IsBankUser (403 for clients); here only existence."""
    application = Application.objects.filter(pk=application_id).first()
    if application is None:
        raise NotFound(NOT_FOUND)
    return application
