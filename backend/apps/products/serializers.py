from decimal import Decimal

from rest_framework import serializers

from apps.products.models import Product


class ProductSerializer(serializers.ModelSerializer):
    rate_min = serializers.DecimalField(max_digits=8, decimal_places=4)
    rate_max = serializers.DecimalField(max_digits=8, decimal_places=4)
    amount_min = serializers.DecimalField(max_digits=14, decimal_places=2)
    amount_max = serializers.DecimalField(max_digits=14, decimal_places=2)
    params = serializers.SerializerMethodField()
    requirements = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = (
            "code",
            "kind",
            "name",
            "description",
            "rate_min",
            "rate_max",
            "term_min_months",
            "term_max_months",
            "amount_min",
            "amount_max",
            "is_revolving",
            "collateral_required",
            "params",
            "requirements",
            "required_documents",
        )

    def get_params(self, product: Product) -> dict[str, str]:
        """Contract: every parameter is a decimal string ("0.3", "1.25")."""
        return {key: str(Decimal(str(value))) for key, value in product.params.items()}

    def get_requirements(self, product: Product) -> dict:
        requirements = product.requirements or {}
        return {
            "min_business_age_months": int(requirements.get("min_business_age_months", 0)),
            "legal_forms": list(requirements.get("legal_forms", ["ip", "ooo"])),
        }
