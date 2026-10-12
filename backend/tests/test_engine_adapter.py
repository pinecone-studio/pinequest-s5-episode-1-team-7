import pytest

from app import engine_adapter
from app.engine_adapter import AnalysisResult
from helpers import make_jpeg


def test_valid_full_result():
    r = AnalysisResult.from_dict({"score": 0.83, "risk_flag": "RED", "heatmap_path": "/x.png",
                                  "num_patches": 142, "inference_ms": 1180})
    assert (r.score, r.risk_flag, r.heatmap_path, r.num_patches, r.inference_ms) == (0.83, "red", "/x.png", 142, 1180.0)


def test_minimal_result():
    r = AnalysisResult.from_dict({"score": 0})
    assert r.score == 0.0 and r.risk_flag is None and r.heatmap_path is None


@pytest.mark.parametrize("bad", [
    None, 0.5, {}, {"score": "high"}, {"score": 1.5}, {"score": -0.1},
    {"score": float("nan")}, {"score": 0.5, "risk_flag": "purple"},
])
def test_contract_violations_rejected(bad):
    with pytest.raises(ValueError):
        AnalysisResult.from_dict(bad)


def test_stub_follows_the_contract(env, tmp_path):
    path = tmp_path / "s.jpg"
    path.write_bytes(make_jpeg((120, 20, 160)))
    result = AnalysisResult.from_dict(engine_adapter._stub_analyze_slide(str(path)))
    assert 0.0 <= result.score <= 1.0 and result.num_patches == 1
    from pathlib import Path
    assert Path(result.heatmap_path).is_file()


def test_stub_rejects_undecodable_file(env, tmp_path):
    path = tmp_path / "bad.jpg"
    path.write_bytes(b"nope")
    with pytest.raises(ValueError):
        engine_adapter._stub_analyze_slide(str(path))
