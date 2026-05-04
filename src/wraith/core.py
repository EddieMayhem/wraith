"""Core dotfiles management logic."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator


# Regex to parse a wraithfile entry: "src -> dest"
LINK_RE = re.compile(r"^(.+?)\s*->\s*(.+)$")


@dataclass
class DotfileEntry:
    """A single dotfile mapping."""

    source: Path  # absolute path in the wraith repo
    dest: Path  # absolute path in $HOME

    @classmethod
    def from_line(cls, line: str, repo_root: Path) -> "DotfileEntry":
        """Parse a wraithfile line like 'bash/.bashrc -> ~/.bashrc'."""
        line = line.strip()
        if not line or line.startswith("#"):
            raise ValueError(f"Invalid line: {line}")

        m = LINK_RE.match(line)
        if not m:
            raise ValueError(f"Invalid wraithfile syntax: {line}")

        src_rel = Path(m.group(1)).expanduser()
        dest_rel = Path(m.group(2)).expanduser()

        # Resolve relative paths against repo root
        if not src_rel.is_absolute():
            src_rel = repo_root / src_rel
        if dest_rel == Path("~"):
            raise ValueError(f"Dest cannot be ~ alone: {line}")

        return cls(source=src_rel, dest=dest_rel)


@dataclass
class Wraith:
    """Main wraith engine."""

    repo_root: Path
    home: Path = field(default_factory=lambda: Path(os.environ["HOME"]))
    dry_run: bool = False

    def entries(self) -> Iterator[DotfileEntry]:
        """Yield parsed entries from the Wraithfile."""
        wf = self.repo_root / "Wraithfile"
        if not wf.exists():
            raise FileNotFoundError(f"No Wraithfile found in {self.repo_root}")

        for line in wf.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                yield DotfileEntry.from_line(line, self.repo_root)
            except ValueError as e:
                raise ValueError(f"Wraithfile error: {e}") from e

    def _run(self, cmd: list[str]) -> None:
        """Run a shell command."""
        if self.dry_run:
            print(f"[dry-run] would run: {' '.join(cmd)}")
            return
        subprocess.run(cmd, check=True)

    def install(self) -> None:
        """Symlink all dotfiles from the repo into $HOME."""
        print(f"Installing dotfiles from {self.repo_root} ...")

        for entry in self.entries():
            dest = entry.dest
            if dest.is_symlink() or dest.exists():
                backup = dest.with_name(dest.name + ".bak")
                n = 1
                while backup.exists() or backup.is_symlink():
                    backup = dest.with_name(f"{dest.name}.bak{n}")
                    n += 1
                print(f"  backing up {dest} -> {backup}")
                if not self.dry_run:
                    shutil.move(str(dest), str(backup))

            dest.parent.mkdir(parents=True, exist_ok=True)
            print(f"  linking {dest} -> {entry.source}")
            if not self.dry_run:
                dest.unlink(missing_ok=True)
                os.symlink(str(entry.source), str(dest))

        print("Done.")

    def status(self) -> dict[str, str]:
        """Check which dotfiles are tracked, linked, or orphaned."""
        state: dict[str, str] = {}
        for entry in self.entries():
            dest = entry.dest
            if dest.is_symlink() and dest.resolve() == entry.source:
                state[str(dest)] = "linked"
            elif dest.exists():
                state[str(dest)] = "modified"
            else:
                state[str(dest)] = "missing"
        return state

    def list_tracked(self) -> list[Path]:
        """List all source files tracked in the Wraithfile."""
        return [entry.source for entry in self.entries()]
