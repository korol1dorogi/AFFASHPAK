import pytest

from apps.demo_data.build import build_dataset


@pytest.fixture(scope="session")
def dataset() -> dict:
    return build_dataset()
