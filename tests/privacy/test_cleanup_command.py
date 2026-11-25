"""Privacy regression: workspace-bounded cleanup (P032 T011).

Acceptance scenarios (IMPLEMENTATION_PLAN T011, PROJECT_BOOK §17.3):

12. the delete command can clean up specified files;
13. the cleanup command cannot delete arbitrary paths outside the
    workspace.

No cleanup command existed before T011 (``scripts/`` had none), so
this task implements the minimal one (§17): ``scripts/clean_evidence.py``
over :func:`accepttwin.privacy.delete_evidence_files`. Every refusal
is tested against a live "victim" file outside the workspace whose
survival is asserted afterwards — a refusal that still deleted the
file would be caught, not just reported.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from accepttwin.privacy import (
    PrivacyError,
    delete_evidence_files,
    resolve_cleanup_target,
)

ROOT = Path(__file__).resolve().parents[2]
CLEAN_SCRIPT = ROOT / "scripts" / "clean_evidence.py"


def _write(path: Path, content: str = "x") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CLEAN_SCRIPT), *args],
        capture_output=True,
        text=True,
        timeout=30,
    )


# ---------------------------------------------------------------------------
# Scenario 12 — the delete command can clean up specified files
# ---------------------------------------------------------------------------


def test_delete_named_files_inside_workspace(tmp_path):
    victim1 = _write(tmp_path / "evidence" / "tmp-a.json")
    victim2 = _write(tmp_path / "tmp-b.txt")
    keeper = _write(tmp_path / "keep.txt")
    deleted = delete_evidence_files(tmp_path, [victim1, victim2])
    assert deleted == [victim1.resolve(), victim2.resolve()]
    assert not victim1.exists()
    assert not victim2.exists()
    assert keeper.exists()


def test_delete_by_relative_path(tmp_path):
    target = _write(tmp_path / "sub" / "temp.html")
    deleted = delete_evidence_files(tmp_path, ["sub/temp.html"])
    assert deleted == [target.resolve()]
    assert not target.exists()


def test_delete_nested_path_with_dot_segments(tmp_path):
    target = _write(tmp_path / "a" / "b" / "temp.txt")
    deleted = delete_evidence_files(tmp_path, ["a/./b/../b/temp.txt"])
    assert deleted == [target.resolve()]
    assert not target.exists()


def test_dry_run_deletes_nothing(tmp_path):
    target = _write(tmp_path / "temp.txt")
    would_delete = delete_evidence_files(tmp_path, [target], dry_run=True)
    assert would_delete == [target.resolve()]
    assert target.exists()


def test_cli_deletes_named_file(tmp_path):
    target = _write(tmp_path / "evidence" / "old.json")
    result = _run_cli("--root", str(tmp_path), str(target))
    assert result.returncode == 0, result.stderr
    assert "deleted" in result.stdout
    assert not target.exists()


def test_cli_dry_run(tmp_path):
    target = _write(tmp_path / "evidence" / "temp.txt")
    result = _run_cli("--root", str(tmp_path), "--dry-run", str(target))
    assert result.returncode == 0, result.stderr
    assert "would delete" in result.stdout
    assert target.exists()


def test_cli_refuses_file_outside_evidence_subtree(tmp_path):
    """T014 (T011 P2): the script's deletable subtree is narrowed
    to evidence/ — an explicitly named file at the workspace root
    (e.g. a source file) is refused, even though it is inside the
    workspace and a regular file."""
    target = _write(tmp_path / "temp.txt")
    result = _run_cli("--root", str(tmp_path), str(target))
    assert result.returncode == 2
    assert "REFUSED" in result.stderr
    assert "outside the allowed subtree" in result.stderr
    assert target.exists()


def test_allowed_subtrees_parameter_narrows_primitive(tmp_path):
    """T014 (T011 P2): the primitive honours allowed_subtrees when
    a caller passes it; without it the workspace boundary stands."""
    inside = _write(tmp_path / "evidence" / "old.json")
    outside = _write(tmp_path / "src.txt")
    assert delete_evidence_files(
        tmp_path, [inside], allowed_subtrees=("evidence",)
    ) == [inside.resolve()]
    assert not inside.exists()
    with pytest.raises(PrivacyError, match="outside the allowed subtree"):
        delete_evidence_files(
            tmp_path, [outside], allowed_subtrees=("evidence",)
        )
    assert outside.exists()


def test_cli_defaults_root_to_project_root(tmp_path):
    """With no --root, the project root is used (refuses outside)."""
    outside = _write(tmp_path / "outside.txt")
    result = _run_cli(str(outside))
    assert result.returncode == 2
    assert "REFUSED" in result.stderr
    assert outside.exists()


# ---------------------------------------------------------------------------
# Scenario 13 — the cleanup command cannot delete outside the workspace
# ---------------------------------------------------------------------------


def test_absolute_path_outside_workspace_refused(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    victim = _write(tmp_path / "victim.txt", "do not delete")
    with pytest.raises(PrivacyError, match="outside the workspace"):
        delete_evidence_files(workspace, [victim])
    assert victim.exists()
    assert victim.read_text() == "do not delete"


def test_dotdot_escape_refused(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    victim = _write(tmp_path / "victim.txt", "do not delete")
    with pytest.raises(PrivacyError, match="outside the workspace"):
        delete_evidence_files(workspace, ["../victim.txt"])
    assert victim.exists()


def test_symlink_inside_pointing_outside_refused(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    victim = _write(tmp_path / "victim.txt", "do not delete")
    link = workspace / "link.txt"
    link.symlink_to(victim)
    with pytest.raises(PrivacyError, match="symlink"):
        delete_evidence_files(workspace, [link])
    assert victim.exists()
    assert link.is_symlink()


def test_symlink_pointing_inside_is_still_refused(tmp_path):
    """Fail-closed: symlinks are never followed, even inward ones."""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    real = _write(workspace / "real.txt")
    link = workspace / "link.txt"
    link.symlink_to(real)
    with pytest.raises(PrivacyError, match="symlink"):
        delete_evidence_files(workspace, [link])
    assert real.exists()


def test_workspace_root_itself_refused(tmp_path):
    with pytest.raises(PrivacyError):
        delete_evidence_files(tmp_path, [tmp_path])
    assert tmp_path.exists()


def test_directory_refused(tmp_path):
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    _write(subdir / "file.txt")
    with pytest.raises(PrivacyError, match="not a regular file"):
        delete_evidence_files(tmp_path, [subdir])
    assert (subdir / "file.txt").exists()


def test_missing_file_refused(tmp_path):
    with pytest.raises(PrivacyError, match="does not exist"):
        delete_evidence_files(tmp_path, ["no-such-file.txt"])


def test_empty_target_list_refused(tmp_path):
    with pytest.raises(PrivacyError, match="no cleanup targets"):
        delete_evidence_files(tmp_path, [])


def test_one_bad_target_blocks_the_whole_batch(tmp_path):
    """Atomicity: a bad target means nothing is deleted at all."""
    good = _write(tmp_path / "good.txt")
    # A real file just outside the workspace, reached via a `..` escape.
    victim = _write(tmp_path.parent / "t011-victim-outside.txt", "keep me")
    try:
        with pytest.raises(PrivacyError):
            delete_evidence_files(tmp_path, [good, "../t011-victim-outside.txt"])
        assert good.exists()
        assert victim.exists()
    finally:
        victim.unlink(missing_ok=True)


def test_cli_refuses_outside_path_with_nonzero_exit(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    victim = _write(tmp_path / "victim.txt", "do not delete")
    result = _run_cli("--root", str(workspace), str(victim))
    assert result.returncode == 2
    assert "REFUSED" in result.stderr
    assert "outside the workspace" in result.stderr
    assert victim.exists()


def test_cli_refuses_dotdot_escape(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    victim = _write(tmp_path / "victim.txt", "do not delete")
    result = _run_cli("--root", str(workspace), "../victim.txt")
    assert result.returncode == 2
    assert victim.exists()


def test_cli_refuses_symlink(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    victim = _write(tmp_path / "victim.txt", "do not delete")
    link = workspace / "link.txt"
    link.symlink_to(victim)
    result = _run_cli("--root", str(workspace), str(link))
    assert result.returncode == 2
    assert victim.exists()


def test_resolve_returns_canonical_absolute_path(tmp_path):
    target = _write(tmp_path / "sub" / "temp.txt")
    resolved = resolve_cleanup_target(tmp_path, "sub/temp.txt")
    assert resolved == target.resolve()
    assert resolved.is_absolute()
