"""Public product catalog and the payment calculator (listProducts, getProduct,
calculateAnnuity in docs/openapi.yaml)."""

from decimal import Decimal

from rest_framework import serializers
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.credit_math import annuity_summary
from apps.products.models import Product
from apps.products.serializers import ProductSerializer


class ProductListView(APIView):
    permission_classes = (AllowAny,)

    def get(self, request: Request) -> Response:
        products = Product.objects.filter(is_active=True)
        return Response(ProductSerializer(products, many=True).data)


class ProductDetailView(APIView):
    permission_classes = (AllowAny,)

    def get(self, request: Request, code: str) -> Response:
        product = Product.objects.filter(code=code, is_active=True).first()
        if product is None:
            raise NotFound("Такого продукта нет.")
        return Response(ProductSerializer(product).data)


class AnnuityRequestSerializer(serializers.Serializer):
    principal = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal("0.01"), coerce_to_string=False
    )
    annual_rate = serializers.DecimalField(
        max_digits=8, decimal_places=4, min_value=Decimal(0), coerce_to_string=False
    )
    term_months = serializers.IntegerField(min_value=1, max_value=360)


def _money(value: Decimal) -> str:
    return format(value, "f")


class AnnuityCalculatorView(APIView):
    """POST /api/calculators/annuity — payment, total, overpayment and the schedule.

    All maths is apps/credit_math.annuity_summary; nothing is stored, so it is open to anyone.
    """

    permission_classes = (AllowAny,)

    def post(self, request: Request) -> Response:
        serializer = AnnuityRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        summary = annuity_summary(data["principal"], data["annual_rate"], data["term_months"])
        return Response(
            {
                "payment": _money(summary.payment),
                "total_paid": _money(summary.total_paid),
                "overpayment": _money(summary.overpayment),
                "schedule": [
                    {
                        "number": row.number,
                        "payment": _money(row.payment),
                        "interest": _money(row.interest),
                        "principal": _money(row.principal),
                        "balance": _money(row.balance),
                    }
                    for row in summary.schedule
                ],
            }
        )
