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


def _form(count: int, one: str, few: str, many: str) -> str:
    """The word form for a count: one for 1 and 21, few for 2–4 and 22, many for 5–20 and 11–14."""
    if count % 10 == 1 and count % 100 != 11:
        return one
    if count % 10 in (2, 3, 4) and count % 100 not in (12, 13, 14):
        return few
    return many


def days(count: int) -> str:
    """1 день, 2 дня, 5 дней, 21 день, 11 дней."""
    return f"{count} {_form(count, 'день', 'дня', 'дней')}"


def points(count: int) -> str:
    """1 балл, 2 балла, 5 баллов, 21 балл, 11 баллов."""
    return f"{count} {_form(count, 'балл', 'балла', 'баллов')}"


def months(count: int) -> str:
    """A term after «на», «через»: 1 месяц, 3 месяца, 12 месяцев."""
    return f"{count} {_form(count, 'месяц', 'месяца', 'месяцев')}"


def months_genitive(count: int) -> str:
    """A term after «до», «не меньше»: 1 месяца, 3 месяцев, 36 месяцев."""
    return f"{count} {_form(count, 'месяца', 'месяцев', 'месяцев')}"


def age(total_months: int) -> str:
    """Business age the way people say it: 5 месяцев, 1 год, 2 года и 3 месяца, 12 лет."""
    whole, rest = divmod(total_months, 12)
    if not whole:
        return months(rest)
    text = f"{whole} {_form(whole, 'год', 'года', 'лет')}"
    return f"{text} и {months(rest)}" if rest else text


def age_genitive(total_months: int) -> str:
    """The same after «не меньше», «не младше»: 6 месяцев, 1 года, 2 лет, 1 года и 6 месяцев."""
    whole, rest = divmod(total_months, 12)
    if not whole:
        return months_genitive(rest)
    text = f"{whole} {_form(whole, 'года', 'лет', 'лет')}"
    return f"{text} и {months_genitive(rest)}" if rest else text


def years(value: Decimal, *, genitive: bool = False) -> str:
    """Years of profit: за 1 год, 2 года, 4,2 года; genitive: до 1 года, 5 лет, 3,5 года."""
    text = number(value)
    if "," in text:
        return f"{text} года"
    count = int(value)
    word = _form(count, "года", "лет", "лет") if genitive else _form(count, "год", "года", "лет")
    return f"{text} {word}"


def plan_step(metric: str, current: Decimal, target: Decimal) -> str:
    """One step of «как получить одобрение» (XP2): what to do, the target and where it is now."""
    if metric == "business_age_months":
        return (
            f"Подайте заявку снова, когда бизнесу исполнится {age(int(target))} "
            f"(сейчас {age(int(current))})"
        )
    if metric == "dscr":
        return (
            f"Добейтесь, чтобы на каждый рубль платежей по долгам приходилось {number(target)} ₽ "
            f"свободных денег (сейчас {number(current)} ₽): снизьте платежи или увеличьте "
            "остаток денег после расходов"
        )
    if metric == "debt_to_ebitda":
        return (
            f"Снизьте долг так, чтобы его можно было отдать из прибыли за {years(target)} "
            f"(сейчас — за {years(current)})"
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
