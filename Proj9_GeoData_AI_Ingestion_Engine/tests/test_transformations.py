from conftest import FakeGemini, make_jpeg
from image_generator import enhance_scraped_image, generate_restaurant_image
from transformations import is_image_relevant, process_and_filter_image


def _never(*_):
    raise AssertionError("should not be called")


def test_irrelevant_photo_is_dropped():
    assert process_and_filter_image(make_jpeg(1600, 900), "Restaurant", "A", relevance=lambda *_: False, enhance=_never) is None


def test_large_relevant_photo_is_kept_as_is():
    photo = make_jpeg(1600, 900)
    assert process_and_filter_image(photo, "Restaurant", "A", relevance=lambda *_: True, enhance=_never) == photo


def test_small_relevant_photo_goes_to_enhance():
    out = process_and_filter_image(make_jpeg(800, 600), "Restaurant", "A", relevance=lambda *_: True, enhance=lambda b, n: b"enhanced")
    assert out == b"enhanced"


def test_relevance_says_yes_or_no():
    assert is_image_relevant(make_jpeg(10, 10), "Restaurant", client=FakeGemini("YES")) is True
    assert is_image_relevant(make_jpeg(10, 10), "Restaurant", client=FakeGemini("No.")) is False


def test_relevance_error_keeps_the_photo():
    assert is_image_relevant(make_jpeg(10, 10), "Restaurant", client=FakeGemini(error=RuntimeError("down"))) is True


class _ImagenFails:
    def __init__(self):
        self.models = self

    def generate_images(self, **_):
        raise RuntimeError("free tier")


def test_enhance_keeps_the_original_when_imagen_fails():
    photo = make_jpeg(800, 600)
    assert enhance_scraped_image(photo, "A", client=_ImagenFails()) == photo


def test_gallery_image_is_none_when_imagen_fails():
    assert generate_restaurant_image("A", "exterior", "X", client=_ImagenFails()) is None
