import pytest

from apps.demo_data.build import dumps, generate


@pytest.fixture(scope="session")
def dataset() -> dict:
    return generate()


@pytest.fixture(scope="session")
def dataset_bytes(dataset) -> bytes:
    return dumps(dataset)
