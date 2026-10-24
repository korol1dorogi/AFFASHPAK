"""Client texts of decision-model.md §7 and number formatting for them (Russian conventions).

D8 may rephrase the texts without changing their meaning.
"""

from decimal import Decimal

from apps.credit_math import round_money

NO_DEBT = "Долгов нет, и на счёт приходит больше денег, чем уходит"
NO_DEBT_NO_CASH_FLOW = (
    "Долгов нет, но со счёта уходит не меньше денег, чем приходит, поэтому платить по новому "
    "кредиту нечем"
)
MISSING_KEY_METRIC = (
    "По счёту не хватает данных для автоматической оценки, поэтому заявку посмотрит сотрудник банка"
)
NO_REPORTING = "Отчётности нет, поэтому долговую нагрузку оценили по счёту"
NO_REGISTRATION_DATE = (
    "В ЕГРЮЛ не нашлось даты регистрации, поэтому возраст бизнеса проверит сотрудник банка"
)
BKI_UNAVAILABLE = "Бюро кредитных историй не ответило, поэтому историю проверит сотрудник банка"
TRANSPARENT_BUSINESS_UNAVAILABLE = (
    "«Прозрачный бизнес» сейчас не отвечает, поэтому заявку проверит сотрудник банка. Это не отказ"
)
# No data of another kind (SRC2): the same neutral points, a text that says why.
BKI_NO_DATA = {
    "unavailable": BKI_UNAVAILABLE,
    "restricted": (
        "Сведения в бюро кредитных историй скрыты, поэтому историю проверит сотрудник банка"
    ),
    "consent_missing": (
        "Согласия на запрос в бюро кредитных историй нет, поэтому историю проверит сотрудник банка"
    ),
}
TRANSPARENT_BUSINESS_NO_DATA = {
    "unavailable": TRANSPARENT_BUSINESS_UNAVAILABLE,
    "restricted": (
        "Сведения «Прозрачного бизнеса» скрыты, поэтому заявку проверит сотрудник банка. "
        "Это не отказ"
    ),
}
BKI_CLEAN = "В кредитной истории нет серьёзных просрочек"
TRANSPARENT_BUSINESS_CLEAN = "По данным ФНС признаков риска нет"

IMPROVE_DSCR = "Снизьте платежи по текущим долгам или увеличьте остаток денег после расходов"
IMPROVE_TREND = "Верните выручку хотя бы к уровню прошлого года"
IMPROVE_PAST_OVERDUE = "Подтвердите, что старая просрочка погашена, и не допускайте новых"
IMPROVE_CURRENT_OVERDUE = "Погасите текущую просрочку"
IMPROVE_TAX_ARREARS = "Погасите долг по налогам"
IMPROVE_MASS_ADDRESS = "Подтвердите, что компания действительно работает по этому адресу"


def number(value: Decimal) -> str:
    """2.2000 → «2,2»; 1.2500 → «1,25»; 3.0000 → «3»."""
    text = format(value.normalize(), "f")
    return text.replace(".", ",").replace("-", "−")


def percent(share: Decimal) -> str:
    """0.6000 → «60%»; 0.0525 → «5,25%»."""
    return number(share * 100) + "%"


def rubles(value: Decimal) -> str:
    """50000.00 → «50 000 ₽»; 1234.50 → «1 234,50 ₽»."""
    amount = round_money(value)
    whole, kopecks = divmod(abs(amount), 1)
    text = f"{int(whole):,}".replace(",", " ")
    if kopecks:
        text += "," + f"{kopecks:.2f}"[2:]
    return ("−" if amount < 0 else "") + text + " ₽"


def days(count: int) -> str:
    """1 день, 2 дня, 5 дней, 21 день, 11 дней."""
    if count % 10 == 1 and count % 100 != 11:
        word = "день"
    elif count % 10 in (2, 3, 4) and count % 100 not in (12, 13, 14):
        word = "дня"
    else:
        word = "дней"
    return f"{count} {word}"


def points(count: int) -> str:
    """1 балл, 2 балла, 5 баллов, 21 балл, 11 баллов."""
    if count % 10 == 1 and count % 100 != 11:
        word = "балл"
    elif count % 10 in (2, 3, 4) and count % 100 not in (12, 13, 14):
        word = "балла"
    else:
        word = "баллов"
    return f"{count} {word}"


def plan_step(metric: str, current: Decimal, target: Decimal) -> str:
    """One step of «как получить одобрение» (XP2): what to do, the target and where it is now."""
    if metric == "business_age_months":
        return f"Подайте заявку снова, когда бизнесу исполнится {target:f} мес (сейчас {current:f})"
    if metric == "dscr":
        return (
            f"Добейтесь, чтобы на каждый рубль платежей по долгам приходилось {number(target)} ₽ "
            f"свободных денег (сейчас {number(current)} ₽): снизьте платежи или увеличьте "
            "остаток денег после расходов"
        )
    if metric == "debt_to_ebitda":
        return (
            f"Снизьте долг до {number(target)} годовой прибыли (EBITDA) (сейчас {number(current)})"
        )
    if metric == "revenue_trend":
        return (
            f"Верните выручку хотя бы к {percent(target)} от прошлого года "
            f"(сейчас {percent(current)})"
        )
    if metric == "counterparty_concentration":
        return (
            f"Найдите ещё покупателей, чтобы на крупнейшего приходилось не больше "
            f"{percent(target)} поступлений (сейчас {percent(current)})"
        )
    raise ValueError(f"no plan step for {metric}")
