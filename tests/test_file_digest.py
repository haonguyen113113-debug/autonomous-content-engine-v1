"""Contract pins must not depend on the checkout's line endings.

Regression: card-contract.json pinned starter_sha256 over raw CRLF bytes. The
contract was generated on Windows, so on any LF checkout (CI, macOS, Linux,
Docker) ``load_contract`` raised "starter_sha256 drifted" and the planner,
selector, renderer and QA all failed closed for a reason unrelated to content.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from apps.file_digest import (
    digest_bytes,
    file_digest,
    is_text_artifact,
    normalise_newlines,
)


def test_normalise_newlines_is_idempotent_and_lf_only():
    crlf = b'{"a": 1}\r\n{"b": 2}\r\n'
    assert normalise_newlines(crlf) == b'{"a": 1}\n{"b": 2}\n'
    assert normalise_newlines(normalise_newlines(crlf)) == normalise_newlines(crlf)
    assert normalise_newlines(b"no newlines") == b"no newlines"


def test_digest_bytes_only_normalises_on_request():
    crlf = b"line\r\n"
    assert digest_bytes(crlf) == hashlib.sha256(crlf).hexdigest()
    assert digest_bytes(crlf, normalise=True) == hashlib.sha256(b"line\n").hexdigest()


def test_file_digest_is_identical_for_crlf_and_lf_json(tmp_path: Path):
    lf = tmp_path / "starter-lf.json"
    crlf = tmp_path / "starter-crlf.json"
    lf.write_bytes(b'{"width": 1080}\n{"height": 1920}\n')
    crlf.write_bytes(b'{"width": 1080}\r\n{"height": 1920}\r\n')
    assert file_digest(lf) == file_digest(crlf)


def test_file_digest_keeps_binary_bytes_verbatim(tmp_path: Path):
    png = tmp_path / "plate.png"
    payload = b"\x89PNG\r\n\x1a\n" + b"\r\n\x00\x01"
    png.write_bytes(payload)
    assert not is_text_artifact(png)
    assert file_digest(png) == hashlib.sha256(payload).hexdigest()


@pytest.mark.parametrize("suffix", [".json", ".md", ".py", ".svg", ".srt"])
def test_text_artifacts_are_recognised(suffix: str):
    assert is_text_artifact(Path(f"x{suffix}"))


def test_every_contract_pin_matches_the_file_on_this_checkout():
    from apps.studio_templates.card_media import load_contract

    for version in ("12.0.0", "12.1.0"):
        contract = load_contract(version)
        assert contract is not None, version
        for card in contract["cards"]:
            path = Path("apps/studio_templates") / card["starter_file"]
            assert path.is_file(), path
            assert file_digest(path) == card["starter_sha256"], (
                f"{version}/{card['card_id']} pin is line-ending dependent"
            )
