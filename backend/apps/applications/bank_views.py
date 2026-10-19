"""Bank workplace: application card and officer actions (docs/openapi.yaml, tag `bank`).

Queue and dashboard come in L3/L7. Every action needs the `version` the officer saw;
a stale version answers 409 version_conflict.
"""

from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.applications import services
from apps.applications.access import Actor, get_bank_application
from apps.applications.models import ActorKind, Application, Score
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
