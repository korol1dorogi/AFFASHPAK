from django.db import DatabaseError, connection
from django.db.migrations.executor import MigrationExecutor
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthView(APIView):
    """GET /api/health — liveness of the API and its database (openapi: getHealth)."""

    authentication_classes = ()
    permission_classes = (AllowAny,)
    throttle_classes = ()

    def get(self, request: Request) -> Response:
        try:
            connection.ensure_connection()
        except DatabaseError:
            return Response(
                {"status": "degraded", "database": "unavailable"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response({"status": "ok", "database": "ok"})


class ReadinessView(APIView):
    """GET /api/ready — ready for traffic (openapi: getReadiness).

    Components that exist today: the database and its migrations. The queue and simulators
    join when L4 and S1 land.
    """

    authentication_classes = ()
    permission_classes = (AllowAny,)
    throttle_classes = ()

    def get(self, request: Request) -> Response:
        components = {"database": "ok", "migrations": "ok"}
        try:
            connection.ensure_connection()
            executor = MigrationExecutor(connection)
            if executor.migration_plan(executor.loader.graph.leaf_nodes()):
                components["migrations"] = "unavailable"
        except DatabaseError:
            components = {"database": "unavailable", "migrations": "unavailable"}
        ready = all(state == "ok" for state in components.values())
        return Response(
            {"status": "ready" if ready else "not_ready", "components": components},
            status=status.HTTP_200_OK if ready else status.HTTP_503_SERVICE_UNAVAILABLE,
        )
