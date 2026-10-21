import pytest

from apps.accounts.demo import seed
from apps.integrations.flags import reset


@pytest.fixture
def seeded(db):
    seed()
    yield
    reset()
