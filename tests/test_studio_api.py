"""Studio API helpers: config, starter, export-to-pack, build."""

from pathlib import Path
import base64
import io
import json

import pytest

from apps.web_ui.server import (
    _studio_build,
    _studio_config,
    _studio_export,
    _studio_starter,
)

ROOT = Path(__file__).resolve().parent.parent


def _data_url(width: int, height: int) -> str:
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (width, height), (200, 16, 46)).save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def test_studio_config_reports_key_state(tmp_path, monkeypatch):
    monkeypatch.delenv("POLOTNO_API_KEY", raising=False)
    assert _studio_config(tmp_path) == {"hasKey": False, "key": ""}
    monkeypatch.setenv("POLOTNO_API_KEY", "trial-123")
    assert _studio_config(tmp_path) == {"hasKey": True, "key": "trial-123"}


def test_studio_starter_serves_duel():
    design = _studio_starter("duel_columns", "short")
    assert design["width"] == 1080 and design["height"] == 1920
    assert design["schemaVersion"] == 4
    assert any(el.get("id") == "num-0-home" for el in design["pages"][0]["children"])
    with pytest.raises(ValueError):
        _studio_starter("nope-missing", "short")
    with pytest.raises(ValueError):
        _studio_starter("duel_columns", "square")


def test_studio_export_saves_exact_pixels(tmp_path):
    result = _studio_export(tmp_path, {
        "version": "12.0.0", "layout": "duel_columns",
        "prefix": "short", "dataUrl": _data_url(1080, 1920)})
    assert result["status"] == "PACK_FILE_SAVED"
    saved = tmp_path / result["path"]
    assert saved.is_file()
    from PIL import Image
    with Image.open(saved) as image:
        assert image.size == (1080, 1920)


def test_studio_export_rejects_wrong_size_and_shapes(tmp_path):
    good = {"version": "12.0.0", "layout": "duel_columns",
            "prefix": "short", "dataUrl": _data_url(1080, 1920)}
    with pytest.raises(ValueError):
        _studio_export(tmp_path, {**good, "dataUrl": _data_url(1920, 1080)})
    with pytest.raises(ValueError):
        _studio_export(tmp_path, {**good, "dataUrl": "not-a-data-url"})
    with pytest.raises(ValueError):
        _studio_export(tmp_path, {**good, "version": "v10"})
    with pytest.raises(ValueError):
        _studio_export(tmp_path, {**good, "layout": "../evil"})
    with pytest.raises(ValueError):
        _studio_export(tmp_path, {**good, "prefix": "square"})


def test_studio_build_reports_invalid_pack(tmp_path):
    with pytest.raises(ValueError):
        _studio_build(tmp_path, {"version": "12.0.0"})
    with pytest.raises(ValueError):
        _studio_build(tmp_path, {"version": "bad"})
