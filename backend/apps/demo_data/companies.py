"""Synthetic companies: registry fields of RegistryRecord (docs/openapi.yaml), all marked «демо».

Distributions here are placeholders until docs/data-spec.md (D7): equal ИП/ООО odds, age 1–15
years, everyone `active`. Liquidation and other registry statuses come with personas 4, 6, 7.
"""

from datetime import date

from apps.demo_data.ids import make_inn10, make_inn12, make_ogrn, make_ogrnip
from apps.demo_data.rng import Rng

DEMO_REGION = "Демо-область"

# (code, name) from the public OKVED classifier.
OKVED = (
    ("10.71", "Производство хлеба и мучных кондитерских изделий"),
    ("31.09", "Производство прочей мебели"),
    ("41.20", "Строительство жилых и нежилых зданий"),
    ("46.90", "Торговля оптовая неспециализированная"),
    (
        "47.11",
        "Торговля розничная преимущественно пищевыми продуктами в неспециализированных магазинах",
    ),
    ("47.76", "Торговля розничная цветами и другими растениями, семенами и удобрениями"),
    ("49.41", "Деятельность автомобильного грузового транспорта"),
    ("56.10", "Деятельность ресторанов и услуги по доставке продуктов питания"),
    ("62.01", "Разработка компьютерного программного обеспечения"),
    ("96.02", "Предоставление услуг парикмахерскими и салонами красоты"),
)

# (surname, first name, patronymic) — common words, not real people; every name gets «(демо)».
_PEOPLE = (
    ("Демидов", "Иван", "Петрович"),
    ("Примеров", "Сергей", "Андреевич"),
    ("Тестов", "Алексей", "Николаевич"),
    ("Образцов", "Дмитрий", "Олегович"),
    ("Макетов", "Павел", "Ильич"),
    ("Демидова", "Анна", "Сергеевна"),
    ("Примерова", "Ольга", "Ивановна"),
    ("Тестова", "Мария", "Павловна"),
    ("Образцова", "Елена", "Дмитриевна"),
    ("Макетова", "Наталья", "Алексеевна"),
)
_NAME_WORDS = (
    ("Северный", "Вектор"),
    ("Южный", "Ресурс"),
    ("Новый", "Горизонт"),
    ("Тёплый", "Дом"),
    ("Быстрый", "Маршрут"),
    ("Зелёный", "Сад"),
    ("Точный", "Расчёт"),
    ("Добрый", "Хлеб"),
)
_STREETS = ("Примерная", "Тестовая", "Демонстрационная", "Образцовая", "Шаблонная")

MIN_AGE_YEARS = 1
MAX_AGE_YEARS = 15


def person_name(rng: Rng) -> str:
    surname, first, patronymic = rng.choice(_PEOPLE)
    return f"{surname} {first} {patronymic} (демо)"


def _ip_name(director_name: str) -> str:
    surname, first, patronymic, _ = director_name.split(" ", 3)
    return f"ИП {surname} {first[0]}. {patronymic[0]}. (демо)"


def _ooo_name(rng: Rng) -> str:
    adjective, noun = rng.choice(_NAME_WORDS)
    return f"ООО «{adjective} {noun} {rng.between(1, 99)}» (демо)"


def _registered_at(rng: Rng, as_of: date, min_years: int, max_years: int) -> date:
    first = date(as_of.year - max_years, as_of.month, 1).toordinal()
    last = date(as_of.year - min_years, as_of.month, 1).toordinal()
    return date.fromordinal(rng.between(first, last))


def make_company(
    rng: Rng,
    *,
    as_of: date,
    legal_form: str | None = None,
    okved: str | None = None,
    min_age_years: int = MIN_AGE_YEARS,
    max_age_years: int = MAX_AGE_YEARS,
) -> dict:
    form = legal_form or rng.choice(("ip", "ooo"))
    if form not in ("ip", "ooo"):
        raise ValueError(f"unknown legal_form: {form}")
    okved_names = dict(OKVED)
    code = okved or rng.choice(OKVED)[0]
    registered_at = _registered_at(rng, as_of, min_age_years, max_age_years)
    director = person_name(rng)
    if form == "ip":
        inn, ogrn, name = make_inn12(rng), make_ogrnip(rng, registered_at.year), _ip_name(director)
    else:
        inn, ogrn, name = make_inn10(rng), make_ogrn(rng, registered_at.year), _ooo_name(rng)
    return {
        "inn": inn,
        "ogrn": ogrn,
        "legal_form": form,
        "name": name,
        "okved": code,
        "okved_name": okved_names[code],
        "registered_at": registered_at.isoformat(),
        "region": DEMO_REGION,
        "address": (f"г. Демо, ул. {rng.choice(_STREETS)}, д. {rng.between(1, 150)} (демо)"),
        "registry_status": "active",
        "director_name": director,
        "is_demo": True,
    }


def make_companies(rng: Rng, count: int, *, as_of: date, taken_inns: set[str]) -> list[dict]:
    """`count` companies with INNs unique among themselves and `taken_inns` (updated in place)."""
    companies = []
    index = 0
    while len(companies) < count:
        company = make_company(rng.child(f"company:{index}"), as_of=as_of)
        index += 1
        if company["inn"] in taken_inns:
            continue
        taken_inns.add(company["inn"])
        companies.append(company)
    return companies
