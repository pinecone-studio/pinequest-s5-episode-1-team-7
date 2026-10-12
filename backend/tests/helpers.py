"""Shared test helpers."""
import io

from PIL import Image


def make_jpeg(color=(120, 20, 160), size=(64, 64), exif: dict | None = None) -> bytes:
    img = Image.new("RGB", size, color)
    buf = io.BytesIO()
    if exif:
        e = Image.Exif()
        for tag, value in exif.items():
            e[tag] = value
        img.save(buf, format="JPEG", exif=e)
    else:
        img.save(buf, format="JPEG")
    return buf.getvalue()


def make_png(color=(10, 200, 10), size=(32, 32)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()
