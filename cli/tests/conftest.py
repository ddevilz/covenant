from pathlib import Path
import pytest

FIXTURES = Path(__file__).parent / "integration" / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture
def valid_spec_path() -> Path:
    return FIXTURES / "valid.covenant.yaml"
