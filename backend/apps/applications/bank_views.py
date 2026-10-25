"""Bank workplace: application card and officer actions (docs/openapi.yaml, tag `bank`).

The queue (L3) lists submitted applications; drafts are the client's and stay out of it.
The dashboard comes in L7. Every action needs the `version` the officer saw;
a stale version answers 409 version_conflict.
"""

from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.db.models import Count, Q, QuerySet
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.applications import services
from apps.applications.access import Actor, get_bank_application
from apps.applications.models import (
    ActorKind,
    Application,
    ApplicationEvent,
    ApplicationStatus,
    Decision,
    Grade,
    Score,
)
from apps.applications.offers import current_offer
from apps.applications.serializers import (
    ApplicationEventSerializer,
    ApplicationSerializer,
    CheckSerializer,
    CommentSerializer,
    CompanySerializer,
    CounterofferSerializer,
    DecisionSerializer,
    DeclineSerializer,
    FinancialSnapshotSerializer,
    InfoRequestSerializer,
    MemberSerializer,
    OfferSerializer,
    RequestInfoSerializer,
    ScoreSerializer,
    VersionedActionSerializer,
    user_ref,
)
from apps.applications.sla import open_q, overdue_q, sla_hours, sla_state
from apps.core.permissions import IsBankUser
from apps.credit_math import round_ratio
from apps.documents.serializers import DocumentSerializer
from apps.products.models import ProductKind

QUEUE_STATUSES = [value for value in ApplicationStatus.values if value != ApplicationStatus.DRAFT]
QUEUE_ORDERING = (
    "status_changed_at",
    "-status_changed_at",
    "requested_amount",
    "-requested_amount",
    "created_at",
    "-created_at",
)


def bank_detail(request: Request, application: Application) -> dict:
    actor = Actor(kind=ActorKind.BANK, user=request.user)
    company = application.company
    snapshot = company.snapshots.first()
    score = Score.objects.filter(application=application).first()
    offer = current_offer(application)
    return {
        "application": ApplicationSerializer(
            application, context={"request": request, "actor": actor}
        ).data,
        "company": CompanySerializer(company, context={"role": None}).data,
        "members": MemberSerializer(
            company.memberships.select_related("user__profile"), many=True
        ).data,
        "snapshot": FinancialSnapshotSerializer(snapshot).data if snapshot else None,
        "checks": CheckSerializer(application.checks.all(), many=True).data,
        "score": ScoreSerializer(score).data if score else None,
        "decisions": DecisionSerializer(application.decisions.all(), many=True).data,
        "offer": OfferSerializer(offer).data if offer else None,
        "info_requests": InfoRequestSerializer(application.info_requests.all(), many=True).data,
        "documents": DocumentSerializer(
            application.documents.all(),
            many=True,
            context={"request": request, "download_route": "bank-application-document-download"},
        ).data,
        "events": ApplicationEventSerializer(
            application.events.select_related("actor__profile"), many=True
        ).data,
        "assignee": user_ref(application.assignee),
    }


class _BankView(APIView):
    permission_classes = (IsBankUser,)

    def actor(self, request: Request) -> Actor:
        return Actor(kind=ActorKind.BANK, user=request.user)


class BankQueueParamsSerializer(serializers.Serializer):
    status = serializers.ListField(
        child=serializers.ChoiceField(choices=ApplicationStatus.choices), required=False
    )
    product_kind = serializers.ChoiceField(choices=ProductKind.choices, required=False)
    grade = serializers.ChoiceField(choices=Grade.choices, required=False)
    assignee = serializers.RegexField(r"^(me|none|\d+)$", required=False)
    min_hours_in_status = serializers.IntegerField(min_value=0, required=False)
    overdue = serializers.BooleanField(required=False)
    search = serializers.CharField(max_length=100, required=False)
    ordering = serializers.ChoiceField(choices=QUEUE_ORDERING, default="status_changed_at")
    page = serializers.IntegerField(min_value=1, default=1)
    page_size = serializers.IntegerField(min_value=1, max_value=100, default=20)


def _queue_filters(request: Request, params: dict, now: datetime) -> QuerySet[Application]:
    """Every filter except status: the status counters are computed on this set."""
    applications = Application.objects.filter(status__in=QUEUE_STATUSES)
    if "product_kind" in params:
        applications = applications.filter(product__kind=params["product_kind"])
    if "grade" in params:
        applications = applications.filter(score__grade=params["grade"])
    assignee = params.get("assignee")
    if assignee == "me":
        applications = applications.filter(assignee=request.user)
    elif assignee == "none":
        applications = applications.filter(assignee__isnull=True)
    elif assignee is not None:
        applications = applications.filter(assignee_id=int(assignee))
    if "min_hours_in_status" in params:
        since = now - timedelta(hours=params["min_hours_in_status"])
        applications = applications.filter(status_changed_at__lte=since)
    if params.get("overdue"):
        applications = applications.filter(overdue_q(now))
    search = params.get("search", "").strip()
    if search:
        applications = applications.filter(
            Q(company__inn__startswith=search) | Q(company__name__icontains=search)
        )
    return applications


def _queue_item(application: Application, now: datetime) -> dict:
    score = getattr(application, "score", None)  # reverse one-to-one: missing → None
    offer = current_offer(application)
    # The product on the table now: an alternative offer (leasing) replaces the requested one.
    product = offer.product if offer else application.product
    in_status = now - application.status_changed_at
    sla = sla_state(application.status, application.status_changed_at, now)
    return {
        "id": application.pk,
        "company_name": application.company.name,
        "company_inn": application.company.inn,
        "product_kind": product.kind if product else None,
        "requested_amount": f"{application.requested_amount:.2f}",
        "status": application.status,
        "grade": score.grade if score else None,
        "assignee": user_ref(application.assignee),
        "source_unavailable": application.source_unavailable,
        "status_changed_at": serializers.DateTimeField().to_representation(
            application.status_changed_at
        ),
        "hours_in_status": max(0, int(in_status.total_seconds())) // 3600,
        "sla_due_at": (
            serializers.DateTimeField().to_representation(sla.due_at) if sla.due_at else None
        ),
        "is_overdue": sla.is_overdue,
        "overdue_hours": sla.overdue_hours,
        "version": application.version,
    }


class BankQueueView(_BankView):
    def get(self, request: Request) -> Response:
        params = _valid_params(request)
        now = timezone.now()
        applications = _queue_filters(request, params, now)
        counts = dict(applications.order_by().values_list("status").annotate(total=Count("id")))
        counters = {value: counts.get(value, 0) for value in QUEUE_STATUSES}
        if params.get("status"):
            applications = applications.filter(status__in=params["status"])
        applications = applications.select_related(
            "company", "product", "assignee__profile", "score"
        )
        applications = applications.order_by(params["ordering"], "id")
        page, page_size = params["page"], params["page_size"]
        total = applications.count()
        start = (page - 1) * page_size
        return Response(
            {
                "count": total,
                "page": page,
                "page_size": page_size,
                "results": [
                    _queue_item(application, now)
                    for application in applications[start : start + page_size]
                ],
                "counters": counters,
            }
        )


def _valid_params(request: Request) -> dict:
    serializer = BankQueueParamsSerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)
    return dict(serializer.validated_data)


class BankApplicationDetailView(_BankView):
    def get(self, request: Request, pk: int) -> Response:
        return Response(bank_detail(request, get_bank_application(pk)))


class BankAssignView(_BankView):
    def post(self, request: Request, pk: int) -> Response:
        data = _valid(VersionedActionSerializer, request)
        application = services.assign(
            get_bank_application(pk), self.actor(request), data["version"]
        )
        return Response(bank_detail(request, application))


class BankApproveView(_BankView):
    def post(self, request: Request, pk: int) -> Response:
        data = _valid(VersionedActionSerializer, request)
        application = services.bank_approve(
            get_bank_application(pk), self.actor(request), data["version"], data.get("comment")
        )
        return Response(bank_detail(request, application))


class BankCounterofferView(_BankView):
    def post(self, request: Request, pk: int) -> Response:
        data = _valid(CounterofferSerializer, request)
        application = services.bank_counteroffer(
            get_bank_application(pk), self.actor(request), **data
        )
        return Response(bank_detail(request, application))


class BankRequestInfoView(_BankView):
    def post(self, request: Request, pk: int) -> Response:
        data = _valid(RequestInfoSerializer, request)
        application = services.bank_request_info(
            get_bank_application(pk), self.actor(request), **data
        )
        return Response(bank_detail(request, application))


class BankDeclineView(_BankView):
    def post(self, request: Request, pk: int) -> Response:
        data = _valid(DeclineSerializer, request)
        application = services.bank_decline(get_bank_application(pk), self.actor(request), **data)
        return Response(bank_detail(request, application))


class BankCommentView(_BankView):
    def post(self, request: Request, pk: int) -> Response:
        data = _valid(CommentSerializer, request)
        event = services.bank_comment(
            get_bank_application(pk), self.actor(request), data["message"]
        )
        return Response(ApplicationEventSerializer(event).data, status=status.HTTP_201_CREATED)


def _valid(serializer_class, request: Request) -> dict:
    serializer = serializer_class(data=request.data)
    serializer.is_valid(raise_exception=True)
    return dict(serializer.validated_data)


FUNNEL = (
    ApplicationStatus.SUBMITTED,
    ApplicationStatus.PROCESSING,
    ApplicationStatus.MANUAL_REVIEW,
    ApplicationStatus.INFO_REQUESTED,
    ApplicationStatus.OFFER,
    ApplicationStatus.SIGNING,
    ApplicationStatus.SIGNED,
    ApplicationStatus.ISSUED,
    ApplicationStatus.DECLINED,
    ApplicationStatus.CANCELLED,
)
FINAL_OUTCOMES = ("offer", "counteroffer", "alternative_product", "declined")
# Hours in status to 0.01, half up like every other rounding here; shares go through round_ratio.
HOURS_STEP = Decimal("0.01")


class DashboardParamsSerializer(serializers.Serializer):
    days = serializers.IntegerField(min_value=1, max_value=90, default=30)


class BankDashboardView(_BankView):
    """GET /api/bank/dashboard — funnel, average hours in each status, share of auto decisions.

    Period: applications submitted in the last `days`. Hours in status come from the status
    journal (ApplicationEvent.to_status); the current status counts until now. SLA (XP4, sla.py):
    of the period's applications now in a status with a norm, how many are past it.
    """

    def get(self, request: Request) -> Response:
        params = DashboardParamsSerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        days = params.validated_data["days"]
        now = timezone.now()
        applications = Application.objects.filter(
            submitted_at__gte=now - timedelta(days=days)
        ).exclude(status=ApplicationStatus.DRAFT)
        ids = list(applications.values_list("id", flat=True))
        reached: dict[str, set[int]] = {stage: set() for stage in FUNNEL}
        reached[ApplicationStatus.SUBMITTED].update(ids)
        for app_id, state in applications.values_list("id", "status"):
            if state in reached:
                reached[state].add(app_id)
        hours: dict[str, list[Decimal]] = {}
        journal = (
            ApplicationEvent.objects.filter(application_id__in=ids, to_status__isnull=False)
            .order_by("application_id", "created_at", "id")
            .values_list("application_id", "to_status", "created_at")
        )
        previous: tuple[int, str, datetime] | None = None
        for app_id, state, at in [*journal, (None, None, None)]:
            if state in reached and app_id is not None:
                reached[state].add(app_id)
            if previous is not None:
                left = at if app_id == previous[0] else now
                spent = Decimal((left - previous[2]).total_seconds()) / 3600
                hours.setdefault(previous[1], []).append(spent)
            previous = (app_id, state, at) if app_id is not None else None
        sla_open = applications.filter(open_q())
        sla_open_count = sla_open.count()
        overdue_count = sla_open.filter(overdue_q(now)).count()
        decisions = Decision.objects.filter(application_id__in=ids, outcome__in=FINAL_OUTCOMES)
        total_decisions = decisions.count()
        auto = decisions.filter(decided_by="auto").count()
        return Response(
            {
                "period_days": days,
                "total_applications": len(ids),
                "funnel": [{"stage": stage, "count": len(reached[stage])} for stage in FUNNEL],
                "avg_hours_in_status": {
                    state: str(
                        (sum(values) / len(values)).quantize(HOURS_STEP, rounding=ROUND_HALF_UP)
                    )
                    for state, values in hours.items()
                },
                "auto_decision_share": (
                    str(round_ratio(Decimal(auto) / total_decisions)) if total_decisions else None
                ),
                "sla_hours": sla_hours(),
                "sla_open_count": sla_open_count,
                "overdue_count": overdue_count,
                "overdue_share": (
                    str(round_ratio(Decimal(overdue_count) / sla_open_count))
                    if sla_open_count
                    else None
                ),
            }
        )
