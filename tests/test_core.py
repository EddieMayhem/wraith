"""Tests for wraith.core."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from wraith.core import DotfileEntry, Wraith, WraithfileParseError


class TestDotfileEntry:
    """Unit tests for DotfileEntry parsing."""

    def test_parses_simple_entry(self, tmp_path: Path) -> None:
        entry = DotfileEntry.from_line("bash/.bashrc -> ~/.bashrc", tmp_path)
        assert entry.source == tmp_path / "bash" / ".bashrc"
        assert entry.dest == Path("~/.bashrc").expanduser()

    def test_parses_absolute_dest(self, tmp_path: Path) -> None:
        entry = DotfileEntry.from_line("vim/vimrc -> /etc/vim/vimrc", tmp_path)
        assert entry.dest == Path("/etc/vim/vimrc")

    def test_strips_comments(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="Invalid line"):
            DotfileEntry.from_line("# this is a comment", tmp_path)

    def test_strips_whitespace(self, tmp_path: Path) -> None:
        entry = DotfileEntry.from_line("  bash/.bashrc   ->   ~/.bashrc  ", tmp_path)
        assert entry.source == tmp_path / "bash" / ".bashrc"


class TestWraith:
    """Integration tests for Wraith operations."""

    def _make_wraithfile(self, tmp_path: Path, content: str) -> Wraith:
        wf = tmp_path / "Wraithfile"
        wf.write_text(content)
        return Wraith(repo_root=tmp_path)

    def test_entries_yields_correct_items(self, tmp_path: Path) -> None:
        (tmp_path / "bash").mkdir()
        (tmp_path / "bash" / ".bashrc").touch()
        w = self._make_wraithfile(tmp_path, "bash/.bashrc -> ~/.bashrc\n")
        entries = list(w.entries())
        assert len(entries) == 1
        assert entries[0].dest == Path("~/.bashrc").expanduser()

    def test_entries_skips_blank_and_comment_lines(self, tmp_path: Path) -> None:
        w = self._make_wraithfile(tmp_path, "# comment\n\n  \n# another\n")
        assert list(w.entries()) == []

    def test_entries_raises_on_missing_wraithfile(self, tmp_path: Path) -> None:
        w = Wraith(repo_root=tmp_path)
        with pytest.raises(FileNotFoundError):
            list(w.entries())

    def test_status_linked(self, tmp_path: Path) -> None:
        """A symlink pointing to the correct source is 'linked'."""
        (tmp_path / "bash").mkdir()
        src = tmp_path / "bash" / ".bashrc"
        src.touch()

        dest = tmp_path / ".bashrc"
        os.symlink(src, dest)

        w = self._make_wraithfile(tmp_path, f"bash/.bashrc -> {dest}\n")
        state = w.status()
        assert state[str(dest)] == "linked"

    def test_status_modified(self, tmp_path: Path) -> None:
        """A regular file at dest (not a symlink) is 'modified'."""
        (tmp_path / "bash").mkdir()
        src = tmp_path / "bash" / ".bashrc"
        src.touch()

        dest = tmp_path / ".bashrc"
        dest.write_text("different content")

        w = self._make_wraithfile(tmp_path, f"bash/.bashrc -> {dest}\n")
        state = w.status()
        assert state[str(dest)] == "modified"

    def test_status_missing(self, tmp_path: Path) -> None:
        """A tracked file with no symlink or file at dest is 'missing'."""
        (tmp_path / "bash").mkdir()
        (tmp_path / "bash" / ".bashrc").touch()

        dest = tmp_path / ".bashrc"
        w = self._make_wraithfile(tmp_path, f"bash/.bashrc -> {dest}\n")

        # ensure dest does NOT exist
        assert not dest.exists()
        state = w.status()
        assert state[str(dest)] == "missing"

    def test_install_creates_symlinks(self, tmp_path: Path) -> None:
        """install() symlinks source -> dest for each entry."""
        (tmp_path / "bash").mkdir()
        src = tmp_path / "bash" / ".bashrc"
        src.touch()

        home = tmp_path / "home"
        home.mkdir()
        old_home = os.environ.get("HOME", "")
        os.environ["HOME"] = str(home)

        try:
            dest = home / ".bashrc"
            w = Wraith(repo_root=tmp_path, home=home)
            w.install()

            assert dest.is_symlink()
            assert dest.resolve() == src
        finally:
            if old_home:
                os.environ["HOME"] = old_home

    def test_install_backs_up_existing_file(self, tmp_path: Path) -> None:
        """If dest already exists, install() moves it to .bak first."""
        (tmp_path / "bash").mkdir()
        (tmp_path / "bash" / ".bashrc").touch()

        home = tmp_path / "home"
        home.mkdir()
        old_home = os.environ.get("HOME", "")
        os.environ["HOME"] = str(home)

        try:
            dest = home / ".bashrc"
            dest.write_text("original content")

            w = Wraith(repo_root=tmp_path, home=home)
            w.install()

            assert dest.is_symlink()
            backup = home / ".bashrc.bak"
            assert backup.exists()
            assert backup.read_text() == "original content"
        finally:
            if old_home:
                os.environ["HOME"] = old_home

    def test_dry_run_does_not_modify_filesystem(self, tmp_path: Path) -> None:
        """With dry_run=True, install() only prints."""
        (tmp_path / "bash").mkdir()
        (tmp_path / "bash" / ".bashrc").touch()

        home = tmp_path / "home"
        home.mkdir()
        old_home = os.environ.get("HOME", "")
        os.environ["HOME"] = str(home)

        try:
            dest = home / ".bashrc"
            dest.write_text("existing")

            w = Wraith(repo_root=tmp_path, home=home, dry_run=True)
            w.install()

            # dest should still be a regular file, unchanged
            assert dest.is_file()
            assert not dest.is_symlink()
        finally:
            if old_home:
                os.environ["HOME"] = old_home
