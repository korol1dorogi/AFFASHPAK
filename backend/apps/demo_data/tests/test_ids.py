import pytest

from apps.demo_data.ids import (
    DEMO_REGION_CODE,
    is_valid_inn,
    is_valid_ogrn,
    make_inn10,
    make_inn12,
    make_ogrn,
    make_ogrnip,
)
from apps.demo_data.rng import Rng

# Hand-checked vectors on synthetic digits (region 00):
# INN-10: 0·2+0·4+1·10+2·3+3·5+4·9+5·4+6·6+7·8 = 179; 179 mod 11 = 3
# INN-12: n11 = 228 mod 11 = 8; n12 = 271 mod 11 = 7
# OGRN: 120001234567 mod 11 = 5; OGRNIP: 32000123456789 mod 13 = 7
VALID_INN = ["0012345673", "001234567887"]
VALID_OGRN = ["1200012345675", "320001234567897"]


@pytest.mark.parametrize("inn", VALID_INN)
def test_known_valid_inn(inn):
    assert is_valid_inn(inn)


@pytest.mark.parametrize("ogrn", VALID_OGRN)
def test_known_valid_ogrn(ogrn):
    assert is_valid_ogrn(ogrn)


@pytest.mark.parametrize(
    "inn",
    [
        "0012345678",  # wrong check digit
        "001234567878",  # wrong second check digit
        "001234567",  # too short
        "00123456788",  # 11 digits
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


def test_generated_ids_are_valid_and_in_demo_region():
    rng = Rng(7, "ids")
    for _ in range(500):
        inn10, inn12 = make_inn10(rng), make_inn12(rng)
        ogrn, ogrnip = make_ogrn(rng, 2019), make_ogrnip(rng, 2021)
        assert len(inn10) == 10 and is_valid_inn(inn10)
        assert len(inn12) == 12 and is_valid_inn(inn12)
        assert len(ogrn) == 13 and is_valid_ogrn(ogrn)
        assert len(ogrnip) == 15 and is_valid_ogrn(ogrnip)
        assert inn10[:2] == inn12[:2] == DEMO_REGION_CODE
        assert ogrn[3:5] == ogrnip[3:5] == DEMO_REGION_CODE
        assert ogrn[:3] == "119" and ogrnip[:3] == "321"
