import io

import pytest
from PIL import Image

from app import anonymize
from helpers import make_jpeg, make_png


def test_hash_is_stable_and_not_raw(env):
    h1, h2 = anonymize.hash_patient_id("P-001"), anonymize.hash_patient_id(" P-001 ")
    assert h1 == h2 and "P-001" not in h1 and len(h1) == 16
    assert anonymize.hash_patient_id("P-002") != h1


def test_missing_id_gets_random_hash(env):
    assert anonymize.hash_patient_id(None) != anonymize.hash_patient_id("")


def test_salt_is_generated_once_and_persisted(env):
    anonymize.hash_patient_id("x")
    salt_file = env / ".salt"
    assert salt_file.exists()
    first = salt_file.read_text()
    anonymize.hash_patient_id("y")
    assert salt_file.read_text() == first


def test_exif_is_stripped(env):
    data = make_jpeg(exif={0x010F: "SecretCameraMaker"})
    assert b"SecretCameraMaker" in data
    clean, ext = anonymize.strip_exif(data)
    assert ext == "jpg" and b"SecretCameraMaker" not in clean


def test_exif_orientation_is_applied_before_stripping(env):
    data = make_jpeg(size=(40, 20), exif={0x0112: 6})  # rotate 90 degrees
    clean, _ = anonymize.strip_exif(data)
    assert Image.open(io.BytesIO(clean)).size == (20, 40)


def test_png_stays_png(env):
    clean, ext = anonymize.strip_exif(make_png())
    assert ext == "png" and Image.open(io.BytesIO(clean)).format == "PNG"


def test_not_an_image_raises_value_error(env):
    with pytest.raises(ValueError):
        anonymize.strip_exif(b"hello world")
