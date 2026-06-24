"""pytest 공통 설정 — web/ 를 import 경로에 추가하고 Flask test client 제공."""
import sys
import warnings
from pathlib import Path

import pytest

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "web"))


@pytest.fixture(scope="session")
def app():
    import churn_main
    churn_main.app.config.update(TESTING=True)
    return churn_main.app


@pytest.fixture()
def client(app):
    return app.test_client()
