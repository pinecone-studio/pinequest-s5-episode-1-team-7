import pytest

from app import config, db


@pytest.fixture()
def env(tmp_path, monkeypatch):
    """Isolated data dir + fresh SQLite DB for every test."""
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "IMAGES_DIR", tmp_path / "images")
    monkeypatch.setattr(config, "HEATMAPS_DIR", tmp_path / "heatmaps")
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "triage.db")
    monkeypatch.setattr(config, "HASH_SALT", "")
    config.ensure_dirs()
    db.init_db()
    return tmp_path
