"""CLI interface for wraith."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from wraith import __version__
from wraith.core import Wraith


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="wraith",
        description="A ghost for your dotfiles.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"wraith {__version__}")
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path(__file__).parent.parent.parent,
        metavar="DIR",
        help="Path to the wraith repo (default: wherever this is installed)",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would happen without doing it"
    )

    sub = parser.add_subparsers(required=True)

    cmd_install = sub.add_parser("install", help="Symlink dotfiles into $HOME")
    cmd_install.set_defaults(func=lambda args: _cmd_install(args))

    cmd_status = sub.add_parser("status", help="Show link status of tracked dotfiles")
    cmd_status.set_defaults(func=lambda args: _cmd_status(args))

    cmd_list = sub.add_parser("list", help="List all tracked dotfiles")
    cmd_list.set_defaults(func=lambda args: _cmd_list(args))

    cmd_init = sub.add_parser("init", help="Scaffold a new wraith repo")
    cmd_init.add_argument("dest", type=Path, help="Where to create the repo")
    cmd_init.set_defaults(func=lambda args: _cmd_init(args))

    cmd_add = sub.add_parser("add", help="Add a file to the Wraithfile")
    cmd_add.add_argument("source", type=Path, help="File to track")
    cmd_add.add_argument("dest", type=Path, nargs="?", help="Symlink destination (default: same path in $HOME)")
    cmd_add.set_defaults(func=lambda args: _cmd_add(args))

    args = parser.parse_args(argv)
    try:
        args.func(args)
        return 0
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


def _wraith(args) -> Wraith:
    return Wraith(repo_root=args.repo, dry_run=args.dry_run)


def _cmd_install(args) -> None:
    w = _wraith(args)
    w.install()


def _cmd_status(args) -> None:
    w = _wraith(args)
    state = w.status()
    if not state:
        print("No dotfiles tracked.")
        return
    for dest, s in state.items():
        icon = {"linked": "✓", "modified": "!", "missing": "?"}[s]
        print(f"  {icon} {s:8} {dest}")


def _cmd_list(args) -> None:
    w = _wraith(args)
    for src in w.list_tracked():
        print(f"  {src}")


def _cmd_init(args) -> None:
    dest = args.dest.resolve()
    wf = dest / "Wraithfile"
    if wf.exists():
        print(f"error: {wf} already exists", file=sys.stderr)
        sys.exit(1)
    wf.write_text("# Wraithfile — one entry per line: 'relative/path -> ~/destination'\n"
                   "# Example: bash/.bashrc -> ~/.bashrc\n")
    print(f"Initialized wraith repo in {dest}")
    print("Edit the Wraithfile to add your dotfiles.")


def _cmd_add(args) -> None:
    src = args.source.resolve()
    dest: Path = args.dest or (Path("~") / src.name)
    wf = _wraith(args).repo_root / "Wraithfile"

    # Make source relative to repo root
    repo_root = _wraith(args).repo_root
    try:
        src_rel = src.relative_to(repo_root)
    except ValueError:
        src_rel = src

    entry = f"{src_rel} -> {dest}"
    with open(wf, "a") as f:
        f.write(entry + "\n")
    print(f"Added: {entry}")


if __name__ == "__main__":
    sys.exit(main())
