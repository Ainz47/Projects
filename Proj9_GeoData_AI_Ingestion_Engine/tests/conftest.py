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
