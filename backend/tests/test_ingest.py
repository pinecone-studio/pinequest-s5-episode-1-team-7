import pytest

from app import config, db, ingest, queue
from helpers import make_jpeg


def test_ingest_creates_file_and_new_slide(env):
    sid = ingest.ingest_bytes(make_jpeg(), "P-1", "Urgent")
    with db.session() as conn:
        row = queue.get_slide(conn, sid)
    assert row["state"] == "new" and row["indication"] == "Urgent"
    assert row["local_hash"] != "P-1" and "P-1" not in row["local_hash"]
    assert (env / "images").exists() and len(list((env / "images").iterdir())) == 1


def test_stored_image_has_no_exif(env):
    sid = ingest.ingest_bytes(make_jpeg(exif={0x010F: "SecretCameraMaker"}), None)
    with db.session() as conn:
        path = queue.get_slide(conn, sid)["image_path"]
    assert b"SecretCameraMaker" not in open(path, "rb").read()


@pytest.mark.parametrize("data,indication", [
    (b"", "Routine"),
    (b"not an image", "Routine"),
    (make_jpeg(), "Whenever"),
])
def test_bad_input_rejected_and_nothing_saved(env, data, indication):
    with pytest.raises(ValueError):
        ingest.ingest_bytes(data, "P-1", indication)
    with db.session() as conn:
        assert queue.list_all(conn) == []
    assert list((env / "images").iterdir()) == []


def test_size_limit(env, monkeypatch):
    monkeypatch.setattr(config, "MAX_UPLOAD_MB", 0)
    with pytest.raises(ValueError):
        ingest.ingest_bytes(make_jpeg(), None)
