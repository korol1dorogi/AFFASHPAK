"""XP7: GET /api/bank/policy — the credit policy in force; POST /api/bank/policy/what-if — the
population on other grade boundaries. Bank only; nothing is stored or changed."""

from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsBankUser
from apps.scoring import population


class GradeBoundariesSerializer(serializers.Serializer):
    A = serializers.IntegerField(min_value=1, max_value=100)
    B = serializers.IntegerField(min_value=1, max_value=100)
    C = serializers.IntegerField(min_value=1, max_value=100)
    D = serializers.IntegerField(min_value=1, max_value=100)

    def validate(self, attrs: dict) -> dict:
        if not attrs["A"] > attrs["B"] > attrs["C"] > attrs["D"]:
            raise serializers.ValidationError(
                "Пороги идут по убыванию: A выше B, B выше C, C выше D."
            )
        return attrs


class PolicyWhatIfRequestSerializer(serializers.Serializer):
    grades = GradeBoundariesSerializer()


class BankPolicyView(APIView):
    permission_classes = (IsBankUser,)

    def get(self, request: Request) -> Response:
        return Response(population.overview())


class BankPolicyWhatIfView(APIView):
    permission_classes = (IsBankUser,)

    def post(self, request: Request) -> Response:
        body = PolicyWhatIfRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        return Response(population.what_if(body.validated_data["grades"]))
