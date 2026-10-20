import pytest

from apps.demo_data.ids import (
    INSPECTION_COUNTERPARTY,
    INSPECTION_FOUNDER,
    Counter,
    company_ids,
    is_valid_inn,
    is_valid_ogrn,
    make_inn10,
    make_inn12,
    make_ogrn,
    make_ogrnip,
)

# docs/data-spec.md §9.1: (legal form, persona number, registration year) → (inn, ogrn)
PERSONA_IDS = [
    ("ip", 1, 2023, "000100000170", "323000100000013"),
    ("ooo", 2, 2020, "0001000028", "1200001000022"),
    ("ip", 3, 2018, "000100000318", "318000100000031"),
    ("ooo", 4, 2014, "0001000042", "1140001000040"),
    ("ooo", 5, 2022, "0001000050", "1220001000053"),
    ("ooo", 6, 2021, "0001000067", "1210001000065"),
    ("ip", 7, 2023, "000100000702", "323000100000079"),
]


@pytest.mark.parametrize(("form", "number", "year", "inn", "ogrn"), PERSONA_IDS)
def test_persona_ids_match_data_spec(form, number, year, inn, ogrn):
    assert company_ids(form, number, year) == (inn, ogrn)
    assert is_valid_inn(inn) and is_valid_ogrn(ogrn)


def test_structure():
    assert make_inn10(1234) == "000101234" + make_inn10(1234)[-1]
    assert make_inn12(1234)[:10] == "0001001234"
    assert make_inn10(13, INSPECTION_COUNTERPARTY).startswith("0002")
    assert make_inn12(5, INSPECTION_FOUNDER).startswith("0003")
    assert make_ogrn(1000, 2019)[:12] == "119000101000"
    assert make_ogrnip(1000, 2021)[:14] == "32100010001000"


def test_all_numbers_in_ranges_are_valid():
    for number in [*range(1, 1200), 99_999]:
        assert is_valid_inn(make_inn10(number))
        assert is_valid_inn(make_inn12(number))
        assert is_valid_ogrn(make_ogrn(number, 2015))
        assert is_valid_ogrn(make_ogrnip(number, 2015))


@pytest.mark.parametrize(
    "inn",
    [
        "0012345678",  # wrong check digit
        "001234567878",  # wrong second check digit
        "001234567",
        "00123456788",
        "00123456 3",
        "００12345673",  # non-ASCII digits
        "",
    ],
)
def test_invalid_inn(inn):
    assert not is_valid_inn(inn)


@pytest.mark.parametrize(
    "ogrn", ["1200012345670", "320001234567890", "12000123456", "1200012345675a", ""]
)
def test_invalid_ogrn(ogrn):
    assert not is_valid_ogrn(ogrn)


def test_number_overflow_and_bad_form():
    with pytest.raises(ValueError):
        make_inn10(100_000)
    with pytest.raises(ValueError):
        make_inn12(0)
    with pytest.raises(ValueError):
        company_ids("zao", 1, 2020)


def test_counter():
    counter = Counter(100, 101)
    assert [counter.next(), counter.next()] == [100, 101]
    with pytest.raises(ValueError):
        counter.next()
