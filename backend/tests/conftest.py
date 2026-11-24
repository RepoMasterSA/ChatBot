import litellm
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


class FakeProvider:
    """Stands in for the network call. Everything else (cache, usage) is real LiteLLM."""

    def __init__(self):
        self.calls = []  # (api_key, messages)
        self.failing_keys = {}  # api_key -> exception to raise

    def __call__(self, **kwargs):
        self.calls.append((kwargs["api_key"], kwargs["messages"]))
        error = self.failing_keys.get(kwargs["api_key"])
        if error:
            raise error
        last = kwargs["messages"][-1]["content"]
        return litellm.completion(mock_response=f"echo: {last}", **kwargs)


@pytest.fixture
def provider():
    return FakeProvider()


@pytest.fixture
def make_client(tmp_path, provider):
    def _make(simulation=True, keys=("k1", "k2")):
        settings = Settings(
            api_keys=tuple(keys),
            model="gemini/gemini-2.0-flash",
            database_path=str(tmp_path / "test.db"),
            enable_failure_simulation=simulation,
        )
        return TestClient(create_app(settings, completion_fn=provider), raise_server_exceptions=False)

    return _make


@pytest.fixture
def client(make_client):
    return make_client()
