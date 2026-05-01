"""CLI interface for wraith."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from wraith import __version__
from wraith.core import Wraith
from wraith.secrets import SecretsManager


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

    # Secrets subcommands
    cmd_secrets = sub.add_parser("secrets", help="Manage encrypted secrets")
    secrets_sub = cmd_secrets.add_subparsers(required=True)

    cmd_secrets_init = secrets_sub.add_parser("init", help="Generate ~/.wraith.key encryption key")
    cmd_secrets_init.set_defaults(func=lambda args: _cmd_secrets_init(args))

    cmd_secrets_add = secrets_sub.add_parser("add", help="Encrypt and add a secret file")
    cmd_secrets_add.add_argument("source", type=Path, help="Secret file to encrypt and track")
    cmd_secrets_add.add_argument("dest", type=Path, nargs="?", help="Destination path (default: same as source)")
    cmd_secrets_add.set_defaults(func=lambda args: _cmd_secrets_add(args))

    cmd_secrets_install = secrets_sub.add_parser("install", help="Decrypt and install all secrets")
    cmd_secrets_install.set_defaults(func=lambda args: _cmd_secrets_install(args))

    cmd_secrets_status = secrets_sub.add_parser("status", help="Show tracked secrets")
    cmd_secrets_status.set_defaults(func=lambda args: _cmd_secrets_status(args))

    cmd_secrets_remove = secrets_sub.add_parser("remove", help="Remove a secret by destination")
    cmd_secrets_remove.add_argument("dest", type=Path, help="Destination path of the secret to remove")
    cmd_secrets_remove.set_defaults(func=lambda args: _cmd_secrets_remove(args))

    cmd_secrets_sync = secrets_sub.add_parser("sync", help="Commit secret changes to git")
    cmd_secrets_sync.set_defaults(func=lambda args: _cmd_secrets_sync(args))

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


def _secrets(args) -> SecretsManager:
    return SecretsManager(repo_root=args.repo)


def _cmd_secrets_init(args) -> None:
    _secrets(args).init()


def _cmd_secrets_add(args) -> None:
    src = args.source.resolve()
    dest = args.dest.expanduser() if args.dest else None
    _secrets(args).add(src, dest)


def _cmd_secrets_install(args) -> None:
    _secrets(args).install()


def _cmd_secrets_status(args) -> None:
    _secrets(args).status()


def _cmd_secrets_remove(args) -> None:
    _secrets(args).remove(args.dest)


def _cmd_secrets_sync(args) -> None:
    _secrets(args).sync()


if __name__ == "__main__":
    sys.exit(main())
