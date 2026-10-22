"""Tables of docs/data-spec.md (D7) as data. Section numbers point to the spec.

Spec version used: see SPEC_REF. When the spec changes, these tables change with a new
GENERATOR_VERSION, never silently.
"""

from dataclasses import dataclass

GENERATOR_VERSION = "datagen-2026.10-v1"
# Commits of the draft specs this generator follows (branches not merged yet).
SPEC_REF = {
    "data_spec": "origin/D7-data-spec@8160cc1591e2e29ca01bb7aa66a4910bc16688ac",
    "decision_model": "origin/D4-decision-model@385348dee6dc5d901bb8dfc501c83f44fe49707f",
    "product_catalog": "origin/D3-product-catalog@18ed0e89547e62ee51c1295731e5531dc2b85c0d",
}

DEMO = " (демо)"
REGION = "Демо-регион (00)"  # §3.3
CITIES = ("Условный", "Примерный", "Тестовск", "Образцовск")
STREETS = (
    "Берёзовая", "Весенняя", "Вишнёвая", "Зелёная", "Кленовая", "Лесная", "Липовая",
    "Луговая", "Набережная", "Новая", "Озёрная", "Парковая", "Полевая", "Речная",
    "Рябиновая", "Садовая", "Светлая", "Сиреневая", "Солнечная", "Сосновая", "Средняя",
    "Тенистая", "Тихая", "Цветочная", "Школьная", "Центральная", "Южная", "Северная",
    "Западная", "Восточная",
)  # fmt: skip

# §3.3: 40 surnames (male form; female adds «а»), 30 + 30 first names, 30 patronymics.
SURNAMES = (
    "Алексеев", "Андреев", "Беляев", "Богданов", "Борисов", "Васильев", "Виноградов",
    "Волков", "Воробьёв", "Гаврилов", "Герасимов", "Голубев", "Григорьев", "Давыдов",
    "Дмитриев", "Егоров", "Ершов", "Жуков", "Захаров", "Зайцев", "Ильин", "Калинин",
    "Киселёв", "Ковалёв", "Козлов", "Комаров", "Королёв", "Крылов", "Кузнецов", "Лебедев",
    "Макаров", "Медведев", "Михайлов", "Морозов", "Никитин", "Новиков", "Павлов", "Поляков",
    "Романов", "Семёнов",
)  # fmt: skip
MALE_NAMES = (
    "Александр", "Алексей", "Андрей", "Антон", "Артём", "Борис", "Вадим", "Валерий",
    "Виктор", "Владимир", "Глеб", "Григорий", "Даниил", "Денис", "Дмитрий", "Евгений",
    "Егор", "Иван", "Игорь", "Илья", "Кирилл", "Константин", "Максим", "Михаил", "Никита",
    "Николай", "Олег", "Павел", "Роман", "Сергей",
)  # fmt: skip
FEMALE_NAMES = (
    "Алина", "Алла", "Анастасия", "Анна", "Валентина", "Валерия", "Вера", "Виктория",
    "Галина", "Дарья", "Евгения", "Екатерина", "Елена", "Елизавета", "Жанна", "Зоя", "Инна",
    "Ирина", "Кира", "Ксения", "Лариса", "Любовь", "Людмила", "Маргарита", "Марина",
    "Мария", "Надежда", "Наталья", "Ольга", "Полина",
)  # fmt: skip
PATRONYMICS = (
    "Александрович", "Алексеевич", "Андреевич", "Антонович", "Борисович", "Вадимович",
    "Валерьевич", "Викторович", "Владимирович", "Геннадьевич", "Глебович", "Григорьевич",
    "Денисович", "Дмитриевич", "Евгеньевич", "Егорович", "Иванович", "Игоревич",
    "Кириллович", "Константинович", "Максимович", "Михайлович", "Николаевич", "Олегович",
    "Павлович", "Петрович", "Романович", "Сергеевич", "Станиславович", "Юрьевич",
)  # fmt: skip


@dataclass(frozen=True)
class Okved:
    code: str
    name: str
    retail_share: tuple[str, str]  # share of retail (no INN) in revenue, §4.5


@dataclass(frozen=True)
class OkvedGroup:
    code: str
    okveds: tuple[Okved, ...]  # equal odds inside the group
    population_share: int  # %, §4.5
    seasonality_months: str  # Jan…Dec, space separated
    opex_shares: tuple[str, str, str]  # payroll, rent, tax; supplier takes the rest
    cogs_ratio: str  # §6.3
    dio_days: tuple[int, int]  # §6.3
    ooo_words: tuple[tuple[str, ...], tuple[str, ...]]  # adjective, noun (§3.3)
    ip_kinds: tuple[str, ...]  # «вид бизнеса» (§3.3)
    ip_signs: tuple[str, ...]  # «вывеска» (§3.3)

    @property
    def seasonality(self) -> tuple[str, ...]:
        return tuple(self.seasonality_months.split())


_NO_RETAIL = ("0", "0")
_RETAIL = ("0.85", "0.95")

GROUPS = (
    OkvedGroup(
        "food_service",
        (
            Okved(
                "56.10", "Деятельность ресторанов и услуги по доставке продуктов питания", _RETAIL
            ),
        ),
        12,
        "0.92 0.90 0.97 1.00 1.04 1.06 1.08 1.07 1.02 0.99 0.96 0.99",
        ("0.40", "0.15", "0.07"),
        "0.35",
        (5, 10),
        (("Тёплый", "Уютный", "Домашний", "Вечерний"), ("Очаг", "Стол", "Двор", "Самовар")),
        ("кофейня", "пекарня", "кафе"),
        ("Утренний кофе", "Тёплый хлеб", "Добрый вечер", "Свежая выпечка"),
    ),
    OkvedGroup(
        "retail",
        (Okved("47.19", "Торговля розничная прочая в неспециализированных магазинах", _RETAIL),),
        18,
        "0.90 0.88 0.96 0.98 1.00 0.98 0.97 0.99 1.00 1.03 1.06 1.25",
        ("0.20", "0.10", "0.05"),
        "0.75",
        (30, 60),
        (
            ("Удобный", "Ближний", "Соседский", "Добрый"),
            ("Магазин", "Прилавок", "Выбор", "Квартал"),
        ),
        ("магазин", "минимаркет"),
        ("У дома", "Всё рядом", "Каждый день", "Полка"),
    ),
    OkvedGroup(
        "garden",
        (
            Okved(
                "47.76",
                "Торговля розничная цветами и другими растениями, семенами, удобрениями, домашними "
                "животными и кормами для домашних животных в специализированных магазинах",
                _RETAIL,
            ),
        ),
        4,
        "0.30 0.40 0.90 1.80 2.20 1.90 1.40 1.10 0.80 0.50 0.35 0.35",
        ("0.20", "0.08", "0.05"),
        "0.65",
        (30, 90),
        (("Зелёный", "Цветущий", "Садовый", "Летний"), ("Сад", "Питомник", "Росток", "Луг")),
        ("садовый центр", "цветочный магазин"),
        ("Грядка", "Первоцвет", "Дачный сезон", "Сад и огород"),
    ),
    OkvedGroup(
        "wholesale",
        (Okved("46.90", "Торговля оптовая неспециализированная", _NO_RETAIL),),
        18,
        "0.92 0.94 1.00 1.00 1.02 1.00 0.96 0.98 1.04 1.06 1.04 1.04",
        ("0.10", "0.03", "0.04"),
        "0.85",
        (20, 45),
        (
            ("Северный", "Южный", "Центральный", "Надёжный"),
            ("Поставщик", "Склад", "Терминал", "Партнёр"),
        ),
        ("оптовая база", "склад"),
        ("Опт и розница", "Склад у трассы", "Запас", "Товарный двор"),
    ),
    OkvedGroup(
        "manufacturing",
        (
            Okved("31.09", "Производство прочей мебели", _NO_RETAIL),
            Okved("25.62", "Обработка металлических изделий механическая", _NO_RETAIL),
        ),
        12,
        "0.85 0.92 1.02 1.02 1.00 0.98 0.94 0.96 1.05 1.08 1.08 1.10",
        ("0.30", "0.06", "0.05"),
        "0.60",
        (30, 90),
        (("Точный", "Прочный", "Мастеровой", "Заводской"), ("Цех", "Станок", "Профиль", "Мастер")),
        ("мастерская", "цех"),
        ("Стружка", "Верстак", "Деталь", "Резец"),
    ),
    OkvedGroup(
        "construction",
        (Okved("41.20", "Строительство жилых и нежилых зданий", _NO_RETAIL),),
        10,
        "0.70 0.75 0.90 1.05 1.15 1.20 1.20 1.20 1.15 1.05 0.90 0.75",
        ("0.30", "0.03", "0.05"),
        "0.70",
        (10, 30),
        (
            ("Каменный", "Надёжный", "Высотный", "Крепкий"),
            ("Дом", "Фундамент", "Монолит", "Каркас"),
        ),
        ("строительная бригада", "ремонтная служба"),
        ("Крепкий дом", "Кладка", "Свой угол", "Отделка"),
    ),
    OkvedGroup(
        "trucking",
        (Okved("49.41", "Деятельность автомобильного грузового транспорта", _NO_RETAIL),),
        10,
        "0.90 0.92 1.00 1.02 1.03 1.02 1.00 1.00 1.03 1.05 1.03 1.00",
        ("0.35", "0.05", "0.05"),
        "0.50",
        (0, 5),
        (
            ("Быстрый", "Дальний", "Магистральный", "Грузовой"),
            ("Маршрут", "Рейс", "Транзит", "Путь"),
        ),
        ("грузоперевозки",),
        ("Дальний рейс", "Попутный груз", "Колесо", "Трасса"),
    ),
    OkvedGroup(
        "services",
        (
            Okved("62.01", "Разработка компьютерного программного обеспечения", _NO_RETAIL),
            Okved(
                "96.02", "Предоставление услуг парикмахерскими и салонами красоты", ("0.60", "0.90")
            ),
        ),
        16,
        "0.95 0.95 1.00 1.00 1.00 0.95 0.90 0.95 1.05 1.05 1.05 1.15",
        ("0.55", "0.10", "0.07"),
        "0.20",
        (0, 0),
        (("Цифровой", "Светлый", "Умный", "Новый"), ("Код", "Стиль", "Сервис", "Формат")),
        ("студия", "салон"),
        ("Локон", "Пиксель", "Зеркало", "Строка"),
    ),
)
GROUPS_BY_CODE = {group.code: group for group in GROUPS}

MONTH_NAMES = (
    "январь", "февраль", "март", "апрель", "май", "июнь",
    "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь",
)  # fmt: skip

# §4.4 step 9: acquiring weights by weekday of the sales day (Mon=0 … Sun=6), noise ±10 %.
WEEKDAY_WEIGHTS = (100, 100, 100, 100, 120, 120, 90)

# §6.1: stop quotas inside 5 % of n_companies, weights; then segments R1–R5.
STOP_SHARE = "0.05"
STOP_QUOTAS = (
    ("stop_liquidating", "1.5"),
    ("stop_liquidated", "0.5"),
    ("stop_not_in_egrul", "0.5"),
    ("stop_ebitda", "1.25"),
    ("stop_overdue", "0.75"),
    ("stop_young", "0.5"),
)
SEGMENT_SHARES = (("R1", "23"), ("R2", "32"), ("R3", "19"), ("R4", "18"), ("R5", "8"))

# §6.3: factors in draw order; main bucket per segment, p_main, P(ООО), base PD.
FACTORS = (
    "business_age_months",
    "dscr",
    "debt_to_ebitda",
    "revenue_trend",
    "counterparty_concentration",
    "bki_history",
    "transparent_business",
)
BUCKET_COUNTS = {
    "business_age_months": 4,
    "dscr": 5,
    "debt_to_ebitda": 4,
    "revenue_trend": 4,
    "counterparty_concentration": 4,
    "bki_history": 4,
    "transparent_business": 3,
}


@dataclass(frozen=True)
class Segment:
    main_bucket: dict[str, int]
    p_main: str
    p_ooo: str
    base_pd: str


SEGMENTS = {
    "R1": Segment(dict(zip(FACTORS, (0, 0, 0, 0, 0, 0, 0), strict=True)), "0.88", "0.55", "0.01"),
    "R2": Segment(dict(zip(FACTORS, (0, 0, 1, 1, 1, 0, 0), strict=True)), "0.75", "0.40", "0.02"),
    "R3": Segment(dict(zip(FACTORS, (0, 1, 1, 1, 1, 1, 0), strict=True)), "0.75", "0.35", "0.05"),
    "R4": Segment(dict(zip(FACTORS, (0, 2, 2, 1, 1, 1, 0), strict=True)), "0.75", "0.35", "0.10"),
    "R5": Segment(dict(zip(FACTORS, (2, 3, 2, 1, 2, 1, 1), strict=True)), "0.75", "0.35", "0.20"),
}
STOP_BASE_SEGMENT = "R3"  # §6.1: stop companies are «like R3» apart from the stop feature
STOP_BASE_PD = "0.30"  # §6.4

# §6.3 «корзина → значение»
AGE_MONTHS = ((36, 180), (24, 35), (12, 23), (6, 11))
AGE_EXTRA_DAYS = (0, 20)
DSCR_VALUES = (
    ("2.01", "4.00"),
    ("1.51", "1.99"),
    ("1.26", "1.49"),
    ("1.01", "1.24"),
    ("0.40", "0.99"),
)
DSCR_NO_DEBT_SHARE = "0.40"  # inside bucket 0
DEBT_TO_EBITDA_VALUES = (("0.50", "2.00"), ("2.01", "3.50"), ("3.51", "5.00"), ("5.01", "8.00"))
EBITDA_FACTOR = ("1.05", "1.60")
CASH_SHARE = ("0.05", "0.50")
TREND_VALUES = (("1.00", "1.25"), ("0.90", "0.99"), ("0.80", "0.89"), ("0.60", "0.79"))
CONCENTRATION_VALUES = (("0.05", "0.30"), ("0.31", "0.50"), ("0.51", "0.70"), ("0.71", "0.90"))
RECEIVABLE_DAYS = (20, 60)
PAYABLE_DAYS = (10, 40)

# Score buckets of D4 §4 (same as data-spec §6.3), used to check that drawn values landed.
DSCR_BUCKETS = (("2.0", None), ("1.5", "2.0"), ("1.25", "1.5"), ("1.0", "1.25"), (None, "1.0"))
DEBT_TO_EBITDA_BUCKETS = ((None, "2.0"), ("2.0", "3.5"), ("3.5", "5.0"), ("5.0", None))

# §6.2
REPORTING_SHARE_OOO = "0.70"
TURNOVER_MEDIAN = {"ip": 1_500_000, "ooo": 5_000_000}
TURNOVER_SIGMA = 0.6
TURNOVER_BOUNDS = (300_000, 60_000_000)
CFADS_SHARE = ("0.06", "0.20")

# §5.2 buckets → simulator data
BKI_BUCKETS = ("clean", "past_le_30", "past_gt_30", "current_1_30", "current_gt_30")
TB_BUCKETS = ("no_flags", "one_flag", "debt_or_both")
TAX_ARREARS = (5_000, 500_000)
MASS_VALUES = 3  # shared addresses / director names

# SRC5: descriptive keys of «Прозрачный бизнес» and ЕГРЮЛ (S1 keys, not read by the scorecard).
# Drawn from their own stream, so every value above stays as it was. Risk flags (accounts
# suspended, unreliable address or director, pending exclusion) are off in the population —
# a share of them would move the D9 stop share; only edge cases switch them on.
REVENUE_PER_EMPLOYEE = (250_000, 600_000)  # ₽ of monthly turnover per person
MAX_EMPLOYEES = 250
# 209-ФЗ, ПП РФ № 265: category by headcount and annual revenue, ₽.
MSP_LIMITS = (
    ("micro", 15, 120_000_000),
    ("small", 100, 800_000_000),
    ("medium", 250, 2_000_000_000),
)
TAX_REGIMES = {
    "ip": (("psn", "0.20"), ("usn_income", "0.45"), ("usn_income_minus_expenses", "0.25"),
           ("osn", "0.10")),
    "ooo": (("usn_income", "0.35"), ("usn_income_minus_expenses", "0.40"), ("osn", "0.25")),
}  # fmt: skip
USN_MAX_REVENUE = 450_000_000  # annual; above — ОСН
PSN_MAX_REVENUE = 60_000_000  # annual; above (or more people) — УСН «доходы»
PSN_MAX_EMPLOYEES = 15
# Taxes paid last year as a share of annual turnover, by regime.
TAX_BURDEN = {
    "psn": ("0.003", "0.010"),
    "usn_income": ("0.030", "0.060"),
    "usn_income_minus_expenses": ("0.015", "0.040"),
    "osn": ("0.020", "0.050"),
}
KPP_SUFFIX = "01001"  # КПП = first 4 digits of the INN (inspection) + reason 01 + 001; ООО only

# §4.4 step 8: debt_service over 1–3 obligations, 0.5 / 0.3 / the last takes the rest.
OBLIGATION_SHARES = ("0.5", "0.3")
# §4.4 step 8, §5.1: kinds and opening dates of population debts.
LEASING_SHARE = "0.25"
OPENED_INSIDE_SHARE = "0.30"  # only loans, only if a month before the window exists
OPENED_INSIDE_MAX_MONTH = 3
OPENED_BEFORE_MONTHS = (1, 36)
LOAN_PAYMENTS_IN_ADVANCE = (12, 24)
REMAINING_MONTHS = (6, 48)
PAYMENT_DAY = (10, 20)
PAYER_WEIGHTS = (95, 105)  # near-equal shares keep every other payer below kappa
OTHER_PAYERS = (1, 6)
SUPPLIERS = (2, 8)

# §8
OOO_DIRECTOR_POSITIONS = (("Генеральный директор", "0.85"), ("Директор", "0.15"))
ACCOUNTANT_SHARE = {"ooo": "0.50", "ip": "0.15"}
ACCOUNTANT_POSITIONS = (
    ("Главный бухгалтер", "0.60"),
    ("Бухгалтер", "0.25"),
    ("Финансовый директор", "0.15"),
)
IP_POSITION = "Индивидуальный предприниматель"
DIRECTOR_IS_FOUNDER_SHARE = "0.60"  # §5.1
FOUNDER_SHARES = (("1.0000",), ("0.5000", "0.5000"), ("0.5000", "0.3000", "0.2000"))
