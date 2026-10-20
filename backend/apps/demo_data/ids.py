"""INN and OGRN/OGRNIP with valid check digits and region code 00 (docs/data-spec.md §3.1).

Numbers come from counters, not from randomness: personas take 1–99 (persona N → number N,
independent of the seed), edge cases 100–999, the population from 1000. A company's INN and
OGRN share one number from the counter of its legal form. Counterparties (inspection 02) and
founders (inspection 03) have counters of their own.
"""

DEMO_REGION_CODE = "00"
INSPECTION_COMPANY = "01"
INSPECTION_COUNTERPARTY = "02"
INSPECTION_FOUNDER = "03"

PERSONA_NUMBERS = (1, 99)
EDGE_NUMBERS = (100, 999)
POPULATION_FIRST_NUMBER = 1000

_INN10_WEIGHTS = (2, 4, 10, 3, 5, 9, 4, 6, 8)
_INN12_WEIGHTS_11 = (7, 2, 4, 10, 3, 5, 9, 4, 6, 8)
_INN12_WEIGHTS_12 = (3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8)

OGRN_SIGN = "1"  # legal entity
OGRNIP_SIGN = "3"  # individual entrepreneur


def _weighted_check(digits: str, weights: tuple[int, ...]) -> str:
    return str(sum(int(d) * w for d, w in zip(digits, weights, strict=True)) % 11 % 10)


def inn10_check(first9: str) -> str:
    return _weighted_check(first9, _INN10_WEIGHTS)


def inn12_checks(first10: str) -> str:
    n11 = _weighted_check(first10, _INN12_WEIGHTS_11)
    return n11 + _weighted_check(first10 + n11, _INN12_WEIGHTS_12)


def ogrn_check(first12: str) -> str:
    return str(int(first12) % 11 % 10)


def ogrnip_check(first14: str) -> str:
    return str(int(first14) % 13 % 10)


def is_valid_inn(inn: str) -> bool:
    if not inn.isascii() or not inn.isdigit():
        return False
    if len(inn) == 10:
        return inn[9] == inn10_check(inn[:9])
    if len(inn) == 12:
        return inn[10:] == inn12_checks(inn[:10])
    return False


def is_valid_ogrn(ogrn: str) -> bool:
    """OGRN (13 digits, legal entity) or OGRNIP (15 digits, entrepreneur)."""
    if not ogrn.isascii() or not ogrn.isdigit():
        return False
    if len(ogrn) == 13:
        return ogrn[12] == ogrn_check(ogrn[:12])
    if len(ogrn) == 15:
        return ogrn[14] == ogrnip_check(ogrn[:14])
    return False


def _number(number: int, digits: int) -> str:
    if not 0 < number < 10**digits:
        raise ValueError(f"number {number} does not fit into {digits} digits")
    return f"{number:0{digits}d}"


def make_inn10(number: int, inspection: str = INSPECTION_COMPANY) -> str:
    """Legal entity: region 00, inspection, 5-digit number, check digit."""
    first9 = DEMO_REGION_CODE + inspection + _number(number, 5)
    return first9 + inn10_check(first9)


def make_inn12(number: int, inspection: str = INSPECTION_COMPANY) -> str:
    """Entrepreneur or person: region 00, inspection, 6-digit number, two check digits."""
    first10 = DEMO_REGION_CODE + inspection + _number(number, 6)
    return first10 + inn12_checks(first10)


def make_ogrn(number: int, registration_year: int) -> str:
    year = f"{registration_year % 100:02d}"
    first12 = OGRN_SIGN + year + DEMO_REGION_CODE + INSPECTION_COMPANY + _number(number, 5)
    return first12 + ogrn_check(first12)


def make_ogrnip(number: int, registration_year: int) -> str:
    year = f"{registration_year % 100:02d}"
    first14 = OGRNIP_SIGN + year + DEMO_REGION_CODE + INSPECTION_COMPANY + _number(number, 7)
    return first14 + ogrnip_check(first14)


def company_ids(legal_form: str, number: int, registration_year: int) -> tuple[str, str]:
    """(inn, ogrn) of a company: ООО → INN-10 + OGRN, ИП → INN-12 + OGRNIP."""
    if legal_form == "ooo":
        return make_inn10(number), make_ogrn(number, registration_year)
    if legal_form == "ip":
        return make_inn12(number), make_ogrnip(number, registration_year)
    raise ValueError(f"unknown legal_form: {legal_form}")


class Counter:
    """Sequential numbers in [first, last]; running out is a generator error, not a wrap."""

    def __init__(self, first: int, last: int | None = None) -> None:
        self._next = first
        self._last = last

    def next(self) -> int:
        if self._last is not None and self._next > self._last:
            raise ValueError(f"counter exhausted at {self._last}")
        value = self._next
        self._next += 1
        return value
