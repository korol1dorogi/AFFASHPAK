"""Fields a sent application must have (decision-model.md, validation).

Checked on submit: after sending, the client can only upload documents and answer in text
(info_requested), so a gap in a field would send the application round in circles. The pipeline
keeps the same check as a safety net for applications sent before this rule.
"""

from apps.applications.models import Application
from apps.scoring.texts import rubles


def field_gaps(application: Application) -> list[tuple[str, str]]:
    """(field, message) for every field the bank cannot work without; empty — complete."""
    from apps.scoring.policy import get_policy  # scoring imports applications

    gaps: list[tuple[str, str]] = []
    if len((application.purpose or "").strip()) < get_policy().purpose_min_length:
        gaps.append(("purpose", "Опишите цель подробнее: на что именно пойдут деньги"))
    product = application.product
    if product is None:
        gaps.append(("product_code", "Выберите продукт или воспользуйтесь подбором"))
        return gaps
    if application.requested_amount < product.amount_min:
        gaps.append(
            ("requested_amount", f"Этот продукт выдают на сумму от {rubles(product.amount_min)}")
        )
    if not product.term_min_months <= application.term_months <= product.term_max_months:
        gaps.append(
            (
                "term_months",
                f"Этот продукт выдают на срок от {product.term_min_months} до "
                f"{product.term_max_months} мес",
            )
        )
    if product.kind == "factoring" and application.invoice_amount is None:
        gaps.append(("invoice_amount", "Укажите сумму отгрузки по документу"))
    return gaps
