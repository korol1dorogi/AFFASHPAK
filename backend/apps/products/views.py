"""Public product catalog (docs/openapi.yaml: listProducts, getProduct)."""

from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

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
