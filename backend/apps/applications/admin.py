"""Technical admin only (D7). Status and version are read-only: they change via services."""

from django.contrib import admin

from apps.applications import models


class ReadOnlyInline(admin.TabularInline):
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False


class EventInline(ReadOnlyInline):
    model = models.ApplicationEvent
    fields = ("created_at", "kind", "from_status", "to_status", "actor_kind", "message")
    readonly_fields = fields


class DecisionInline(ReadOnlyInline):
    model = models.Decision
    fields = ("created_at", "outcome", "decided_by", "grade", "policy_version")
    readonly_fields = fields


@admin.register(models.Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("id", "company", "need_type", "requested_amount", "status", "status_changed_at")
    list_filter = ("status", "need_type")
    search_fields = ("company__name", "company__inn")
    readonly_fields = ("status", "version", "submitted_at", "status_changed_at", "decided_at")
    inlines = (DecisionInline, EventInline)


for model in (
    models.Offer,
    models.InfoRequest,
    models.Check,
    models.Score,
    models.Signature,
    models.Disbursement,
):
    admin.site.register(model)
