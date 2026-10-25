"""Assistant endpoints (AI3) by docs/openapi.yaml, tags `assistant` and `bank`.

Thin views: validate the body, call the orchestrator (engine.py) as the current user, serialize.
Client: GET/POST /api/assistant/messages, POST /api/assistant/actions/{id}/confirm — a bank user
or someone else's application is 404, as on every client endpoint. Bank: GET/POST
/api/bank/applications/{id}/assistant/messages and POST …/assistant/summary — IsBankUser (a
client gets 403, as on every /api/bank/* endpoint), an unknown application is 404.
Messages to the model are throttled per user (`assistant`, 20/min by default): every one costs
the provider's budget.
"""

from rest_framework import serializers, status
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.applications.access import (
    NOT_FOUND,
    actor_for,
    get_bank_application,
    get_client_application,
    is_bank_user,
)
from apps.applications.serializers import ApplicationDetailSerializer
from apps.assistant import engine
from apps.assistant.models import AssistantMessage, MessageRole
from apps.assistant.tools import confirm_pending_action
from apps.core.permissions import IsBankUser


class MessageRequestSerializer(serializers.Serializer):
    text = serializers.CharField(min_length=1, max_length=2000, trim_whitespace=False)
    application_id = serializers.IntegerField(min_value=1, required=False)

    def validate(self, attrs: dict) -> dict:
        unknown = sorted(set(self.initial_data) - set(self.fields))
        if unknown:  # contract: additionalProperties: false
            raise serializers.ValidationError({name: ["Неизвестное поле."] for name in unknown})
        return attrs


class BankMessageRequestSerializer(MessageRequestSerializer):
    application_id = None  # the application is in the path


class HistoryParamsSerializer(serializers.Serializer):
    application_id = serializers.IntegerField(min_value=1, required=False)


class AssistantMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssistantMessage
        fields = ("id", "role", "content", "tool_calls", "created_at")


def _history(user, application) -> list[dict]:
    rows = (
        AssistantMessage.objects.filter(user=user, application=application)
        .exclude(role=MessageRole.TOOL)
        .order_by("created_at", "id")
    )
    return AssistantMessageSerializer(rows, many=True).data


def _model_calls_only(request: Request, throttles: list) -> list:
    """The `assistant` scope (DEFAULT_THROTTLE_CLASSES has ScopedRateThrottle) counts only
    messages to the model: reading the history costs the provider nothing."""
    if request.method == "POST":
        return throttles
    return [throttle for throttle in throttles if not isinstance(throttle, ScopedRateThrottle)]


def _client_only(request: Request) -> None:
    if is_bank_user(request.user):
        raise NotFound(NOT_FOUND)


class AssistantMessagesView(APIView):
    throttle_scope = "assistant"

    def get_throttles(self):
        return _model_calls_only(self.request, super().get_throttles())

    def get(self, request: Request) -> Response:
        _client_only(request)
        params = HistoryParamsSerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        application_id = params.validated_data.get("application_id")
        application = (
            None if application_id is None else get_client_application(request.user, application_id)
        )
        return Response(_history(request.user, application))

    def post(self, request: Request) -> Response:
        _client_only(request)
        body = MessageRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        answer = engine.reply(
            request.user, "client", body.validated_data["text"],
            body.validated_data.get("application_id"),
        )  # fmt: skip
        return Response(answer)


class AssistantActionConfirmView(APIView):
    def post(self, request: Request, action_id) -> Response:
        _client_only(request)
        application = confirm_pending_action(request.user, action_id)
        actor = actor_for(request.user, application)
        detail = ApplicationDetailSerializer(
            application, context={"request": request, "actor": actor}
        ).data
        return Response({"action_id": str(action_id), "status": "done", "application": detail})


class BankAssistantMessagesView(APIView):
    permission_classes = (IsBankUser,)
    throttle_scope = "assistant"

    def get_throttles(self):
        return _model_calls_only(self.request, super().get_throttles())

    def get(self, request: Request, pk: int) -> Response:
        application = get_bank_application(pk)
        return Response(_history(request.user, application))

    def post(self, request: Request, pk: int) -> Response:
        get_bank_application(pk)
        body = BankMessageRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        answer = engine.reply(request.user, "bank", body.validated_data["text"], pk)
        answer["pending_action"] = None  # the bank's tools never propose a change
        return Response(answer, status=status.HTTP_200_OK)


class BankAssistantSummaryView(APIView):
    permission_classes = (IsBankUser,)
    throttle_scope = "assistant"  # the default ScopedRateThrottle applies it

    def post(self, request: Request, pk: int) -> Response:
        get_bank_application(pk)
        return Response(engine.summary(request.user, pk))
