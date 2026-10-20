"""Client texts of decision-model.md §7 and number formatting for them (Russian conventions).

D8 may rephrase the texts without changing their meaning.
"""

from decimal import Decimal

from apps.credit_math import round_money

NO_DEBT = "Долгов нет — нагрузки нет"
NO_DEBT_NO_CASH_FLOW = (
    "Долгов нет, но денежный поток по счёту не положительный — платить по новому долгу нечем"
)
MISSING_KEY_METRIC = (
    "Не хватает данных по счёту для автоматической оценки — заявку посмотрит сотрудник"
)
NO_REPORTING = "Отчётности нет — долговую нагрузку оценили по счёту"
NO_REGISTRATION_DATE = "Дату регистрации не получили из ЕГРЮЛ — возраст бизнеса проверит сотрудник"
BKI_UNAVAILABLE = "БКИ не ответило — историю проверит сотрудник"
TRANSPARENT_BUSINESS_UNAVAILABLE = (
    "«Прозрачный бизнес» сейчас не отвечает — заявку проверит сотрудник банка. Это не отказ"
)
BKI_CLEAN = "Кредитная история без серьёзных просрочек"
TRANSPARENT_BUSINESS_CLEAN = "Признаков риска в ФНС нет"

IMPROVE_DSCR = "Снизьте текущие платежи по долгам или увеличьте свободный денежный поток"
IMPROVE_TREND = "Восстановите выручку хотя бы до уровня прошлого года"
IMPROVE_PAST_OVERDUE = "Подтвердите, что просрочка погашена; новых просрочек не допускайте"
IMPROVE_CURRENT_OVERDUE = "Погасите текущую просрочку"
IMPROVE_TAX_ARREARS = "Погасите налоговый долг"
IMPROVE_MASS_ADDRESS = "Подтвердите фактический адрес"


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
