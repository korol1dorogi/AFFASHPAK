"""Explicit-field serializers for applications (docs/openapi.yaml). No "__all__".

Status, version, decisions and offers are output-only: they change through services.
"""

from django.contrib.auth.models import AbstractBaseUser
from rest_framework import serializers

from apps.applications.access import Actor
from apps.applications.models import (
    Application,
    ApplicationEvent,
    Check,
    Decision,
    DecisionOutcome,
    InfoRequest,
    InfoRequestStatus,
    NeedType,
    Offer,
    PrefillSource,
    Score,
)
from apps.applications.offers import current_offer
from apps.applications.transitions import available_actions
from apps.business.models import Company, FinancialSnapshot, IntegrationSource, Membership
from apps.documents.models import DocumentKind
from apps.products.serializers import ProductSerializer
from apps.scoring.plan import approval_plan


def money(**kwargs) -> serializers.DecimalField:
    return serializers.DecimalField(max_digits=14, decimal_places=2, **kwargs)


def rate(**kwargs) -> serializers.DecimalField:
    return serializers.DecimalField(max_digits=8, decimal_places=4, **kwargs)


def user_ref(user: AbstractBaseUser | None) -> dict | None:
    if user is None:
        return None
    profile = getattr(user, "profile", None)
    full_name = (profile.full_name if profile else "") or user.get_full_name() or user.username
    return {"id": user.pk, "full_name": full_name}


# ───────────────────────── output ─────────────────────────


class DecisionSerializer(serializers.ModelSerializer):
    application_id = serializers.IntegerField()
    is_preliminary = serializers.SerializerMethodField()
    approval_plan = serializers.SerializerMethodField()

    class Meta:
        model = Decision
        fields = (
            "id",
            "application_id",
            "outcome",
            "decided_by",
            "is_preliminary",
            "grade",
            "policy_version",
            "reasons",
            "improvements",
            "comment",
            "created_at",
            "approval_plan",
        )

    def get_is_preliminary(self, decision: Decision) -> bool:
        return decision.decided_by == "auto"

    def get_approval_plan(self, decision: Decision) -> dict | None:
        """XP2: only for an automatic decline by grade — a stop factor leaves no grade, and an
        officer's decline says its own reasons. Counted from the stored Score, so stable."""
        if decision.decided_by != "auto" or decision.outcome != DecisionOutcome.DECLINED:
            return None
        if decision.grade is None:
            return None
        score = Score.objects.filter(application_id=decision.application_id).first()
        plan = None if score is None else approval_plan(score.factors, score.model_version)
        if plan is None:
            return None
        return {
            "current_total": plan.current_total,
            "target_total": plan.target_total,
            "target_grade": plan.target_grade,
            "steps": [
                {
                    "metric": step.metric,
                    "current": format(step.current, "f"),
                    "target": format(step.target, "f"),
                    "points": step.points,
                    "message": step.message,
                }
                for step in plan.steps
            ],
        }


class OfferSerializer(serializers.ModelSerializer):
    product = ProductSerializer()
    amount = money()
    requested_amount = money()
    rate = rate()
    monthly_payment = money(allow_null=True)

    class Meta:
        model = Offer
        fields = (
            "id",
            "product",
            "amount",
            "requested_amount",
            "term_months",
            "rate",
            "monthly_payment",
            "is_counteroffer",
            "product_changed",
            "status",
            "expires_at",
            "reasons",
        )


class InfoRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = InfoRequest
        fields = (
            "id",
            "origin",
            "message",
            "fields",
            "document_kinds",
            "status",
            "response_message",
            "created_at",
            "answered_at",
        )


class ApplicationEventSerializer(serializers.ModelSerializer):
    actor = serializers.SerializerMethodField()

    class Meta:
        model = ApplicationEvent
        fields = (
            "id",
            "kind",
            "from_status",
            "to_status",
            "actor_kind",
            "actor",
            "message",
            "is_internal",
            "created_at",
        )

    def get_actor(self, event: ApplicationEvent) -> dict | None:
        return user_ref(event.actor)


class ApplicationSerializer(serializers.ModelSerializer):
    """Needs `actor` in context to compute available_actions."""

    company_id = serializers.IntegerField()
    product_code = serializers.SerializerMethodField()
    requested_amount = money()
    invoice_amount = money(allow_null=True)
    available_actions = serializers.SerializerMethodField()

    class Meta:
        model = Application
        fields = (
            "id",
            "company_id",
            "need_type",
            "purpose",
            "product_code",
            "requested_amount",
            "term_months",
            "invoice_amount",
            "collateral_description",
            "status",
            "version",
            "prefill_source",
            "available_actions",
            "created_at",
            "submitted_at",
            "status_changed_at",
        )

    def get_product_code(self, application: Application) -> str | None:
        return application.product.code if application.product_id else None

    def get_available_actions(self, application: Application) -> list[str]:
        actor: Actor = self.context["actor"]
        return available_actions(application, actor)


class ApplicationDetailSerializer(ApplicationSerializer):
    offer = serializers.SerializerMethodField()
    open_info_requests = serializers.SerializerMethodField()
    decision = serializers.SerializerMethodField()

    class Meta(ApplicationSerializer.Meta):
        fields = (*ApplicationSerializer.Meta.fields, "offer", "open_info_requests", "decision")

    def get_offer(self, application: Application) -> dict | None:
        offer = current_offer(application)
        return OfferSerializer(offer).data if offer else None

    def get_open_info_requests(self, application: Application) -> list[dict]:
        requests = application.info_requests.filter(status=InfoRequestStatus.OPEN)
        return InfoRequestSerializer(requests, many=True).data

    def get_decision(self, application: Application) -> dict | None:
        decision = application.decisions.order_by("-created_at", "-id").first()
        return DecisionSerializer(decision).data if decision else None


class CompanySerializer(serializers.ModelSerializer):
    """Needs `role` in context (the viewer's MemberRole, or None for bank users)."""

    my_role = serializers.SerializerMethodField()

    class Meta:
        model = Company
        fields = (
            "id",
            "inn",
            "ogrn",
            "legal_form",
            "name",
            "okved",
            "okved_name",
            "registered_at",
            "region",
            "address",
            "registry_status",
            "director_name",
            "is_demo",
            "my_role",
            "short_name",
            "integrations",
        )

    short_name = serializers.SerializerMethodField()
    integrations = serializers.SerializerMethodField()

    def get_my_role(self, company: Company) -> str | None:
        return self.context.get("role")

    def get_short_name(self, company: Company) -> str | None:
        return company.short_name or None

    def get_integrations(self, company: Company) -> dict[str, str | None]:
        connected = {i.source: i.connected_at for i in company.integrations.all()}
        field = serializers.DateTimeField()
        return {
            source: field.to_representation(connected[source]) if source in connected else None
            for source in IntegrationSource.values
        }


class MemberSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()

    class Meta:
        model = Membership
        fields = ("id", "user", "role", "position")

    def get_user(self, membership: Membership) -> dict | None:
        return user_ref(membership.user)


class FinancialSnapshotSerializer(serializers.ModelSerializer):
    cleaned_credit_turnover = money(allow_null=True)
    cfads = money(allow_null=True)
    debt_service = money(allow_null=True)
    revenue = money(allow_null=True)
    cogs = money(allow_null=True)
    ebitda = money(allow_null=True)
    debt = money(allow_null=True)
    cash = money(allow_null=True)
    receivables = money(allow_null=True)
    inventory = money(allow_null=True)
    payables = money(allow_null=True)
    counterparty_concentration = rate(allow_null=True)
    revenue_trend = rate(allow_null=True)

    class Meta:
        model = FinancialSnapshot
        fields = (
            "id",
            "period",
            "source",
            "cleaned_credit_turnover",
            "cfads",
            "debt_service",
            "revenue",
            "cogs",
            "ebitda",
            "debt",
            "cash",
            "receivables",
            "inventory",
            "payables",
            "counterparty_concentration",
            "revenue_trend",
        )


class CheckSerializer(serializers.ModelSerializer):
    class Meta:
        model = Check
        fields = ("source", "status", "summary", "data", "checked_at")


class ScoreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Score
        fields = ("grade", "total", "factors", "model_version", "created_at")


# ───────────────────────── input ─────────────────────────


class ApplicationCreateSerializer(serializers.Serializer):
    need_type = serializers.ChoiceField(choices=NeedType.choices)
    purpose = serializers.CharField(max_length=1000)
    requested_amount = money(min_value=1)
    term_months = serializers.IntegerField(min_value=1, max_value=360)
    product_code = serializers.CharField(required=False)
    invoice_amount = money(required=False, min_value=1)
    collateral_description = serializers.CharField(required=False, max_length=1000)
    prefill_source = serializers.ChoiceField(choices=PrefillSource.choices, required=False)


class ApplicationUpdateSerializer(serializers.Serializer):
    version = serializers.IntegerField(min_value=0)
    need_type = serializers.ChoiceField(choices=NeedType.choices, required=False)
    purpose = serializers.CharField(max_length=1000, required=False)
    requested_amount = money(min_value=1, required=False)
    term_months = serializers.IntegerField(min_value=1, max_value=360, required=False)
    product_code = serializers.CharField(required=False, allow_null=True)
    invoice_amount = money(required=False, allow_null=True, min_value=1)
    collateral_description = serializers.CharField(required=False, allow_null=True, max_length=1000)

    def validate(self, attrs: dict) -> dict:
        if len(attrs) < 2:
            raise serializers.ValidationError("Укажите хотя бы одно поле для изменения.")
        return attrs


class SubmitSerializer(serializers.Serializer):
    """The signatory ticks the consent to the credit bureau request on the last wizard step."""

    bki_consent = serializers.BooleanField()
    consent_version = serializers.CharField(max_length=32)
    # The draft version the signatory reviewed: a preparer's later edit → 409 (optional for
    # older clients; the cabinet always sends it).
    version = serializers.IntegerField(min_value=0, required=False)

    def validate_bki_consent(self, value: bool) -> bool:
        if not value:
            raise serializers.ValidationError(
                "Без согласия на запрос в бюро кредитных историй заявку не отправить."
            )
        return value


class InfoRequestResponseSerializer(serializers.Serializer):
    message = serializers.CharField(max_length=2000)


class SignatureConfirmSerializer(serializers.Serializer):
    code = serializers.RegexField(r"^\d{6}$", error_messages={"invalid": "Код — 6 цифр."})


class VersionedActionSerializer(serializers.Serializer):
    version = serializers.IntegerField(min_value=0)
    comment = serializers.CharField(max_length=2000, required=False, allow_blank=True)


class CounterofferSerializer(serializers.Serializer):
    version = serializers.IntegerField(min_value=0)
    product_code = serializers.CharField(required=False)
    amount = money(min_value=1)
    term_months = serializers.IntegerField(min_value=1, max_value=360)
    rate = rate(min_value=0)
    comment = serializers.CharField(max_length=2000)


class RequestInfoSerializer(serializers.Serializer):
    version = serializers.IntegerField(min_value=0)
    message = serializers.CharField(max_length=2000)
    document_kinds = serializers.ListField(
        child=serializers.ChoiceField(choices=DocumentKind.choices), required=False
    )


class DeclineSerializer(serializers.Serializer):
    version = serializers.IntegerField(min_value=0)
    reasons_text = serializers.CharField(max_length=2000)
    improvements = serializers.ListField(child=serializers.CharField(max_length=500), min_length=1)


class CommentSerializer(serializers.Serializer):
    message = serializers.CharField(max_length=2000)
