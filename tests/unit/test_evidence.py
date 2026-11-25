"""Unit tests for the evidence-file writer guard (P032 T005).

:func:`accepttwin.evidence.write_evidence_file` must refuse, at any
depth of the evidence dict, any ``body_text`` / ``response_body`` /
``body`` field carrying raw response bytes (§7.12 I-12). Body hashes
(``body_sha256``) and sizes (``body_size``) are allowed.
"""

from __future__ import annotations

import pytest

from accepttwin.evidence import RAW_OBSERVATIONS_FORMAT, write_evidence_file


def _base_evidence():
    return {"format": RAW_OBSERVATIONS_FORMAT, "observations": []}


def test_write_evidence_file_rejects_top_level_body_text(tmp_path):
    evidence = _base_evidence()
    evidence["body_text"] = "<!DOCTYPE html>"
    with pytest.raises(ValueError, match="body_text"):
        write_evidence_file(tmp_path / "out.json", evidence)
    assert not (tmp_path / "out.json").exists()


def test_write_evidence_file_rejects_nested_body_text_in_observation(tmp_path):
    evidence = _base_evidence()
    evidence["observations"] = [
        {
            "request_index": 3,
            "body_sha256": "a" * 64,
            "body_text": "<!DOCTYPE html>",
        }
    ]
    with pytest.raises(ValueError, match="body_text"):
        write_evidence_file(tmp_path / "out.json", evidence)
    assert not (tmp_path / "out.json").exists()


def test_write_evidence_file_rejects_deeply_nested_body_field(tmp_path):
    evidence = _base_evidence()
    evidence["observations"] = [
        {"request_index": 3, "response": {"body": "# markdown"}}
    ]
    with pytest.raises(ValueError, match="'body'"):
        write_evidence_file(tmp_path / "out.json", evidence)
    assert not (tmp_path / "out.json").exists()


def test_write_evidence_file_accepts_hashes_and_sizes(tmp_path):
    evidence = _base_evidence()
    evidence["observations"] = [
        {
            "request_index": 3,
            "body_sha256": "a" * 64,
            "body_size": 128,
            "response_headers": {"x-accepttwin-cache-status": "MISS"},
        }
    ]
    out = write_evidence_file(tmp_path / "out.json", evidence)
    assert out.exists()
    assert "body_sha256" in out.read_text(encoding="utf-8")
