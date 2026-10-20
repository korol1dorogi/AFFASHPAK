"""Bank workplace: application card and officer actions (docs/openapi.yaml, tag `bank`).

The queue (L3) lists submitted applications; drafts are the client's and stay out of it.
The dashboard comes in L7. Every action needs the `version` the officer saw;
a stale version answers 409 version_conflict.
"""

from datetime import datetime, timedelta

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
    ApplicationStatus,
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
from apps.core.permissions import IsBankUser
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
    search = serializers.CharField(max_length=100, required=False)
    ordering = serializers.ChoiceField(choices=QUEUE_ORDERING, default="status_changed_at")
    page = serializers.IntegerField(min_value=1, default=1)
    page_size = serializers.IntegerField(min_value=1, max_value=100, default=20)


def _queue_filters(request: Request, params: dict) -> QuerySet[Application]:
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
        since = timezone.now() - timedelta(hours=params["min_hours_in_status"])
        applications = applications.filter(status_changed_at__lte=since)
    search = params.get("search", "").strip()
    if search:
        applications = applications.filter(
            Q(company__inn__startswith=search) | Q(company__name__icontains=search)
        )
    return applications


def _queue_item(application: Application, now: datetime) -> dict:
    score = getattr(application, "score", None)  # reverse one-to-one: missing → None
    product = application.product
    in_status = now - application.status_changed_at
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
        "version": application.version,
    }


class BankQueueView(_BankView):
    def get(self, request: Request) -> Response:
        params = _valid_params(request)
        applications = _queue_filters(request, params)
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
        now = timezone.now()
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
