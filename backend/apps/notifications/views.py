"""In-app notifications (docs/openapi.yaml, tag `notifications`). The SPA polls the list."""

from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.notifications.models import Notification

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


class NotificationSerializer(serializers.ModelSerializer):
    application_id = serializers.IntegerField(allow_null=True)

    class Meta:
        model = Notification
        fields = ("id", "kind", "title", "message", "application_id", "created_at", "read_at")


class _Query(serializers.Serializer):
    unread = serializers.BooleanField(required=False, allow_null=True, default=None)
    page = serializers.IntegerField(min_value=1, default=1)
    page_size = serializers.IntegerField(
        min_value=1, max_value=MAX_PAGE_SIZE, default=DEFAULT_PAGE_SIZE
    )


class NotificationListView(APIView):
    def get(self, request: Request) -> Response:
        query = _Query(data=request.query_params)
        query.is_valid(raise_exception=True)
        params = query.validated_data
        mine = Notification.objects.filter(user=request.user)
        filtered = mine
        if params["unread"] is True:
            filtered = mine.filter(read_at__isnull=True)
        elif params["unread"] is False:
            filtered = mine.filter(read_at__isnull=False)
        page, size = params["page"], params["page_size"]
        results = filtered[(page - 1) * size : page * size]
        return Response(
            {
                "count": filtered.count(),
                "page": page,
                "page_size": size,
                "unread_count": mine.filter(read_at__isnull=True).count(),
                "results": NotificationSerializer(results, many=True).data,
            }
        )


class NotificationReadView(APIView):
    def post(self, request: Request, notification_id: int) -> Response:
        updated = Notification.objects.filter(
            pk=notification_id, user=request.user, read_at__isnull=True
        ).update(read_at=timezone.now())
        if (
            not updated
            and not Notification.objects.filter(pk=notification_id, user=request.user).exists()
        ):
            raise NotFound("Не найдено.")
        return Response(status=status.HTTP_204_NO_CONTENT)


class NotificationReadAllView(APIView):
    def post(self, request: Request) -> Response:
        Notification.objects.filter(user=request.user, read_at__isnull=True).update(
            read_at=timezone.now()
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
