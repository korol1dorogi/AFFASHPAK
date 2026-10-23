"""Client application endpoints (docs/openapi.yaml, tag `applications`).

Thin views: validate input, resolve the actor (404 outside scope), call a service,
serialize. Business rules live in services.py / transitions.py.
"""

import uuid

from django.db import transaction
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.applications import services
from apps.applications.access import (
    Actor,
    actor_for,
    client_applications,
    get_client_application,
)
from apps.applications.models import Application, IdempotencyKey
from apps.applications.serializers import (
    ApplicationCreateSerializer,
    ApplicationDetailSerializer,
    ApplicationEventSerializer,
    ApplicationSerializer,
    ApplicationUpdateSerializer,
    DecisionSerializer,
    InfoRequestResponseSerializer,
    SignatureConfirmSerializer,
    SubmitSerializer,
)
from apps.applications.transitions import lock_application


def _detail(request: Request, application: Application, actor: Actor) -> dict:
    return ApplicationDetailSerializer(
        application, context={"request": request, "actor": actor}
    ).data


def _resolve(request: Request, pk: int) -> tuple[Application, Actor]:
    application = get_client_application(request.user, pk)
    return application, actor_for(request.user, application)


class ApplicationListCreateView(APIView):
    def get(self, request: Request) -> Response:
        applications = client_applications(request.user).select_related("product")
        actors: dict[int, Actor] = {}
        data = []
        for application in applications:
            actor = actors.get(application.company_id)
            if actor is None:
                actor = actors[application.company_id] = actor_for(request.user, application)
            data.append(
                ApplicationSerializer(
                    application, context={"request": request, "actor": actor}
                ).data
            )
        return Response(data)

    def post(self, request: Request) -> Response:
        serializer = ApplicationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        application = services.create_application(request.user, serializer.validated_data)
        actor = actor_for(request.user, application)
        body = ApplicationSerializer(application, context={"request": request, "actor": actor})
        return Response(body.data, status=status.HTTP_201_CREATED)


class ApplicationDetailView(APIView):
    def get(self, request: Request, pk: int) -> Response:
        application, actor = _resolve(request, pk)
        return Response(_detail(request, application, actor))

    def patch(self, request: Request, pk: int) -> Response:
        application, actor = _resolve(request, pk)
        serializer = ApplicationUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        application = services.update_draft(application, actor, serializer.validated_data)
        return Response(_detail(request, application, actor))


class ApplicationSubmitView(APIView):
    """Idempotent by the Idempotency-Key header: a retry returns the stored answer."""

    endpoint = "submit"

    def post(self, request: Request, pk: int) -> Response:
        application, actor = _resolve(request, pk)
        raw_key = request.headers.get("Idempotency-Key", "")
        try:
            key = uuid.UUID(raw_key)
        except ValueError:
            raise ValidationError(
                {"Idempotency-Key": ["Нужен заголовок Idempotency-Key с UUID."]}
            ) from None

        with transaction.atomic():
            lock_application(application.pk)  # serializes concurrent retries
            stored = IdempotencyKey.objects.filter(user=request.user, key=key).first()
            if stored is not None:
                if stored.endpoint != f"{self.endpoint}:{application.pk}":
                    raise ValidationError(
                        {"Idempotency-Key": ["Этот ключ уже использован для другого запроса."]}
                    )
                return Response(stored.response_body, status=stored.response_status)
            consent = SubmitSerializer(data=request.data)
            consent.is_valid(raise_exception=True)
            application = services.submit(
                application,
                actor,
                consent_version=consent.validated_data["consent_version"],
                version=consent.validated_data.get("version"),
            )
            body = _detail(request, application, actor)
            IdempotencyKey.objects.create(
                user=request.user,
                key=key,
                endpoint=f"{self.endpoint}:{application.pk}",
                response_status=status.HTTP_200_OK,
                response_body=body,
            )
            application_id = application.pk

            def _run() -> None:
                from apps.pipeline.tasks import enqueue

                enqueue(application_id)

            transaction.on_commit(_run)
        return Response(body)


class _ActionView(APIView):
    """POST that runs one service on the application and returns ApplicationDetail."""

    action_name = ""

    def run(self, request: Request, application: Application, actor: Actor) -> Application:
        return getattr(services, self.action_name)(application, actor)

    def post(self, request: Request, pk: int) -> Response:
        application, actor = _resolve(request, pk)
        application = self.run(request, application, actor)
        return Response(_detail(request, application, actor))


class ApplicationCancelView(_ActionView):
    action_name = "cancel"


class OfferAcceptView(_ActionView):
    action_name = "accept_offer"


class OfferDeclineView(_ActionView):
    action_name = "decline_offer"


class SignatureConfirmView(_ActionView):
    def run(self, request: Request, application: Application, actor: Actor) -> Application:
        serializer = SignatureConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return services.confirm_signature(application, actor, serializer.validated_data["code"])


class InfoRequestRespondView(APIView):
    def post(self, request: Request, pk: int, request_id: int) -> Response:
        application, actor = _resolve(request, pk)
        serializer = InfoRequestResponseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        application = services.respond_info(
            application, actor, request_id, serializer.validated_data["message"]
        )
        return Response(_detail(request, application, actor))


class SignatureStartView(APIView):
    def post(self, request: Request, pk: int) -> Response:
        application, actor = _resolve(request, pk)
        signature, code = services.start_signature(application, actor)
        return Response(
            {
                "code": code,
                "expires_at": signature.expires_at,
                "attempts_left": signature.attempts_left,
            }
        )


class ApplicationEventsView(APIView):
    def get(self, request: Request, pk: int) -> Response:
        application, _ = _resolve(request, pk)
        events = application.events.filter(is_internal=False).select_related("actor__profile")
        return Response(ApplicationEventSerializer(events, many=True).data)


class ApplicationDecisionView(APIView):
    def get(self, request: Request, pk: int) -> Response:
        application, _ = _resolve(request, pk)
        decision = application.decisions.order_by("-created_at", "-id").first()
        if decision is None:
            raise NotFound("Решения по заявке пока нет.")
        return Response(DecisionSerializer(decision).data)
