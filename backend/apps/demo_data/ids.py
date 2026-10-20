"""INN and OGRN/OGRNIP with valid check digits and region code 00, so they never match real ones.

INN: the first 2 digits are the region, then the tax office. OGRN/OGRNIP: sign, last two digits
of the registration year, region, tax office, record number, check digit.
"""

from apps.demo_data.rng import Rng

DEMO_REGION_CODE = "00"

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


def make_inn10(rng: Rng) -> str:
    """Legal entity: region 00, tax office, 5-digit number, check digit."""
    first9 = DEMO_REGION_CODE + rng.digits(7)
    return first9 + inn10_check(first9)


def make_inn12(rng: Rng) -> str:
    """Individual: region 00, tax office, 6-digit number, two check digits."""
    first10 = DEMO_REGION_CODE + rng.digits(8)
    return first10 + inn12_checks(first10)


def make_ogrn(rng: Rng, registration_year: int) -> str:
    first12 = OGRN_SIGN + f"{registration_year % 100:02d}" + DEMO_REGION_CODE + rng.digits(7)
    return first12 + ogrn_check(first12)


def make_ogrnip(rng: Rng, registration_year: int) -> str:
    first14 = OGRNIP_SIGN + f"{registration_year % 100:02d}" + DEMO_REGION_CODE + rng.digits(9)
    return first14 + ogrnip_check(first14)
