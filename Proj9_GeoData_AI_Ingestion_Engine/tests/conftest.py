import io
import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def make_jpeg(width: int, height: int, fmt: str = "JPEG") -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), (120, 90, 60)).save(buf, fmt)
    return buf.getvalue()


class _Response:
    def __init__(self, text):
        self.text = text


class FakeGemini:
    """Stands in for google.genai.Client: .models.generate_content returns `text` or raises `error`."""

    def __init__(self, text="", error=None):
        self.models = self
        self._text, self._error = text, error
        self.calls = 0

    def generate_content(self, model, contents):
        self.calls += 1
        if self._error:
            raise self._error
        return _Response(self._text)


@pytest.fixture
def jpeg():
    return make_jpeg


class MockSession:
    """Lets WordPressClient (written against requests) talk to mock_wp through FastAPI's TestClient."""

    def __init__(self, client):
        self.client = client

    def get(self, url, params=None, auth=None, timeout=None):
        return self.client.get(url, params=params, auth=auth)

    def post(self, url, json=None, data=None, headers=None, auth=None, timeout=None):
        if data is not None:
            return self.client.post(url, content=data, headers=headers, auth=auth)
        return self.client.post(url, json=json, headers=headers, auth=auth)


@pytest.fixture
def mock_app():
    import mock_wp

    return mock_wp.create_app()


@pytest.fixture
def wp(mock_app):
    from fastapi.testclient import TestClient

    import mock_wp
    from wp_importer import WordPressClient

    return WordPressClient("http://testserver", (mock_wp.USERNAME, mock_wp.PASSWORD), session=MockSession(TestClient(mock_app)))
