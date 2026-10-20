from rest_framework.test import APIClient

from apps.core.factories import make_product
from apps.core.testing import assert_matches_contract


def test_catalog_is_public_and_matches_contract(db):
    make_product(params={"alpha": 0.3, "tranche_days": 60})

    listed = APIClient().get("/api/products")
    detail = APIClient().get("/api/products/overdraft_demo")

    assert listed.status_code == detail.status_code == 200
    assert_matches_contract(listed, method="get", path="/api/products")
    assert_matches_contract(detail, method="get", path="/api/products/overdraft_demo")
    assert detail.json()["params"] == {"alpha": "0.3", "tranche_days": "60"}
    assert APIClient().get("/api/products/nope").status_code == 404
