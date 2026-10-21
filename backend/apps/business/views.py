"""Company of the current client and its members (docs/openapi.yaml, tag `company`).

A client sees only their own company (MVP: one per user); everything else is 404.
Changing the company or its members is for the signatory; a preparer gets 403.
"""

from decimal import Decimal

from django.contrib.auth.models import AbstractBaseUser, User
from django.db import IntegrityError, transaction
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.demo import SNAPSHOT_NUMBERS
from apps.accounts.models import UserKind
from apps.applications.access import NOT_FOUND, current_membership, is_bank_user, user_kind
from apps.applications.serializers import (
    CompanySerializer,
    FinancialSnapshotSerializer,
    MemberSerializer,
)
from apps.business import registry
from apps.business.metrics import company_metrics, latest_snapshot
from apps.business.models import (
    Company,
    CompanyIntegration,
    FinancialSnapshot,
    IntegrationSource,
    LegalForm,
    MemberRole,
    Membership,
)
from apps.business.serializers import (
    CompanyUpdateSerializer,
    InnSerializer,
    MemberCreateSerializer,
)
from apps.core.exceptions import Conflict, SourceUnavailable
from apps.integrations.flags import failing_sources
from apps.integrations.simulator_data import dataset
from apps.recommendations.serializers import ReasonSerializer

SIGNATORY_ONLY = "Это может сделать только подписант компании."
NO_SOURCE_DATA = "По этой компании источник данных не ответил. Попробуйте позже."
CREATOR_POSITION = {LegalForm.IP: "Индивидуальный предприниматель", LegalForm.OOO: "Руководитель"}


def _membership(user: AbstractBaseUser) -> Membership:
    membership = current_membership(user) if not is_bank_user(user) else None
    if membership is None:
        raise NotFound(NOT_FOUND)
    return membership


def _require_signatory(membership: Membership) -> None:
    if membership.role != MemberRole.SIGNATORY:
        raise PermissionDenied(SIGNATORY_ONLY)


def _company_data(membership: Membership) -> dict:
    return CompanySerializer(membership.company, context={"role": membership.role}).data


def _valid(serializer_class, data) -> dict:
    serializer = serializer_class(data=data)
    serializer.is_valid(raise_exception=True)
    return dict(serializer.validated_data)


class CompanyLookupView(APIView):
    def get(self, request: Request) -> Response:
        inn = _valid(InnSerializer, request.query_params)["inn"]
        record = registry.lookup(inn)
        if record is None:
            raise NotFound("Не нашли компанию с таким ИНН в реестре.")
        return Response(record)


class CompanyView(APIView):
    def get(self, request: Request) -> Response:
        return Response(_company_data(_membership(request.user)))

    def post(self, request: Request) -> Response:
        if is_bank_user(request.user):
            raise PermissionDenied("Компанию подключает клиент.")
        inn = _valid(InnSerializer, request.data)["inn"]
        if current_membership(request.user) is not None:
            raise Conflict("Вы уже подключили компанию.", code="company_exists")
        record = registry.lookup(inn)
        if record is None:
            raise ValidationError({"inn": ["Не нашли компанию с таким ИНН в реестре."]})
        if Company.objects.filter(inn=inn).exists():
            raise _taken()
        try:
            with transaction.atomic():
                company = Company.objects.create(**record, is_demo=True)
                membership = Membership.objects.create(
                    user=request.user,
                    company=company,
                    role=MemberRole.SIGNATORY,
                    position=CREATOR_POSITION[company.legal_form],
                )
        except IntegrityError as exc:  # the same INN registered a moment ago
            raise _taken() from exc
        return Response(_company_data(membership), status=status.HTTP_201_CREATED)

    def patch(self, request: Request) -> Response:
        membership = _membership(request.user)
        _require_signatory(membership)
        data = _valid(CompanyUpdateSerializer, request.data)
        company = membership.company
        company.short_name = (data["short_name"] or "").strip()
        company.save(update_fields=["short_name"])
        return Response(_company_data(membership))


def _taken() -> Conflict:
    return Conflict(
        "Эта компания уже подключена. Попросите её подписанта добавить вас в сотрудники.",
        code="company_taken",
    )


class MemberListView(APIView):
    def get(self, request: Request) -> Response:
        company = _membership(request.user).company
        members = company.memberships.select_related("user__profile")
        return Response(MemberSerializer(members, many=True).data)

    def post(self, request: Request) -> Response:
        membership = _membership(request.user)
        _require_signatory(membership)
        data = _valid(MemberCreateSerializer, request.data)
        user = User.objects.filter(username=data["username"], is_active=True).first()
        if user is None:
            raise NotFound("Пользователь с таким логином не найден.")
        if user_kind(user) != UserKind.CLIENT:
            raise ValidationError({"username": ["Сотрудника банка нельзя добавить в компанию."]})
        if Membership.objects.filter(user=user).exists():
            raise _already_member()
        try:
            member = Membership.objects.create(
                user=user, company=membership.company, role=data["role"], position=data["position"]
            )
        except IntegrityError as exc:
            raise _already_member() from exc
        return Response(MemberSerializer(member).data, status=status.HTTP_201_CREATED)


def _already_member() -> Conflict:
    return Conflict("Этот пользователь уже работает в компании.", code="member_exists")


class MemberDetailView(APIView):
    def delete(self, request: Request, member_id: int) -> Response:
        membership = _membership(request.user)
        member = membership.company.memberships.filter(pk=member_id).first()
        if member is None:
            raise NotFound(NOT_FOUND)
        _require_signatory(membership)
        if member.pk == membership.pk:
            raise Conflict("Себя убрать нельзя.", code="cannot_remove_self")
        member.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CompanyMetricsView(APIView):
    def get(self, request: Request) -> Response:
        company = _membership(request.user).company
        snapshot = latest_snapshot(company)
        reasons = company_metrics(company, snapshot)
        return Response(
            {
                "snapshot": FinancialSnapshotSerializer(snapshot).data if snapshot else None,
                "metrics": ReasonSerializer(reasons, many=True).data,
                "is_demo": company.is_demo,
            }
        )


class IntegrationConnectView(APIView):
    """POST /api/company/integrations/{source}/connect — connect a source (simulator, «демо»).

    Both sources bring the company's synthetic statement snapshot (the same data the pipeline's
    «bank_account» check reads); the connection is remembered with its time (Company.integrations).
    A switched-off bank account on the demo panel answers 503, like a real outage.
    """

    def post(self, request: Request, source: str) -> Response:
        if source not in IntegrationSource.values:
            raise NotFound(NOT_FOUND)
        if is_bank_user(request.user):
            raise PermissionDenied("Источники подключает клиент.")
        company = _membership(request.user).company
        if source == IntegrationSource.BANK_ACCOUNT and source in failing_sources():
            raise SourceUnavailable("Банк-симулятор выписок сейчас не отвечает. Попробуйте позже.")
        snapshot = latest_snapshot(company) or _snapshot_from_simulator(company)
        if snapshot is None:
            raise SourceUnavailable(NO_SOURCE_DATA)
        CompanyIntegration.objects.get_or_create(company=company, source=source)
        return Response(
            {
                "source": source,
                "status": "connected",
                "is_demo": True,
                "snapshot": FinancialSnapshotSerializer(snapshot).data,
            }
        )


def _snapshot_from_simulator(company: Company) -> FinancialSnapshot | None:
    """The statement snapshot the synthetic world has for this INN (apps/demo_data, S2)."""
    data = dataset()
    key = next((c["_key"] for c in data["companies"] if c["inn"] == company.inn), None)
    record = next((s for s in data["financial_snapshots"] if s["company"] == key), None)
    if record is None:
        return None
    numbers = {
        name: None if record[name] is None else Decimal(record[name]) for name in SNAPSHOT_NUMBERS
    }
    return FinancialSnapshot.objects.create(
        company=company, period=record["period"], source=record["source"], **numbers
    )
