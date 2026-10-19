from django.contrib import admin

from apps.business.models import Company, FinancialSnapshot, Membership


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "inn", "legal_form", "registry_status", "is_demo")
    search_fields = ("name", "inn")
    inlines = (MembershipInline,)


admin.site.register(FinancialSnapshot)
