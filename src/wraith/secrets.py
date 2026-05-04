"""Secret management for wraith.

Uses Fernet symmetric encryption (AES-128-CBC + HMAC) to store secrets
in the repo. The key lives at ~/.wraith.key and is NEVER committed.

File format: .wraith-secrets (same line format as Wraithfile)
  encrypted_blob_path -> ~/destination

The encrypted blobs are stored alongside the Wraithfile, named:
  .wraith-secrets/<base16_of_dest_path>
"""

from __future__ import annotations

import base64
import datetime
import hashlib
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from cryptography.fernet import Fernet


KEY_FILE = Path("~/.wraith.key").expanduser()
SECRETS_BLOB_DIR = ".wraith-blobs"


def _hash_path(path: Path) -> str:
    """Stable name for a secret blob based on its destination."""
    return hashlib.sha256(str(path).encode()).hexdigest()[:32]


@dataclass
class SecretEntry:
    """A single secret mapping."""

    blob_path: Path  # encrypted blob in .wraith-secrets/
    dest: Path  # where the decrypted content goes


def _write_secure(path: Path, data: bytes) -> None:
    """Atomically create a file with mode 0o600 and write data to it.

    Removes any existing file first so O_EXCL succeeds.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        os.write(fd, data)
    finally:
        os.close(fd)


def _load_key() -> bytes:
    """Load the Fernet key from ~/.wraith.key, or generate and save one."""
    if KEY_FILE.exists():
        return KEY_FILE.read_text().strip().encode()
    key = Fernet.generate_key()
    _write_secure(KEY_FILE, key)
    return key


def _fernet() -> Fernet:
    return Fernet(_load_key())


class SecretsManager:
    """Manage encrypted secrets in a wraith repo."""

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.blob_dir = repo_root / SECRETS_BLOB_DIR
        self.secrets_file = repo_root / ".wraith-secrets"
        self.key = _load_key()
        self.fernet = Fernet(self.key)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _entries(self) -> list[SecretEntry]:
        """Parse .wraith-secrets file."""
        if not self.secrets_file.exists():
            return []

        entries: list[SecretEntry] = []
        for line in self.secrets_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if " -> " not in line:
                continue
            blob_rel, dest_rel = line.split(" -> ", 1)
            blob_path = (self.repo_root / blob_rel.strip()).resolve()
            dest = Path(dest_rel.strip()).expanduser()
            entries.append(SecretEntry(blob_path=blob_path, dest=dest))
        return entries

    def _save_entries(self, entries: list[SecretEntry]) -> None:
        """Rewrite .wraith-secrets file from current state."""
        self.secrets_file.parent.mkdir(parents=True, exist_ok=True)
        lines = ["# wraith encrypted secrets — do not edit by hand\n"]
        lines += [f"{e.blob_path.relative_to(self.repo_root)} -> {e.dest}\n" for e in entries]
        self.secrets_file.write_text("".join(lines))

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    def init(self) -> None:
        """Generate ~/.wraith.key if it doesn't exist."""
        _load_key()
        print(f"Key {'already exists' if KEY_FILE.exists() else 'generated'} at {KEY_FILE}")
        print("BACK UP THIS KEY — without it your secrets cannot be recovered.")

    def add(self, source: Path, dest: Path | None = None) -> None:
        """Encrypt a file and add it to the secrets store.

        Usage: wraith secrets-add ~/.env
               wraith secrets-add /path/to/secret -> ~/destination
        """
        source = source.resolve()
        if not source.exists():
            raise FileNotFoundError(source)

        dest = (dest or source).expanduser()

        # Reject path traversal: dest must resolve under HOME
        if ".." in dest.parts:
            raise ValueError(f"Refusing dest with '..': {dest}")
        home = Path(os.environ["HOME"]).resolve()
        try:
            dest.resolve().relative_to(home)
        except ValueError:
            raise ValueError(f"Refusing dest outside HOME: {dest}")

        # Determine where the encrypted blob goes
        self.blob_dir.mkdir(parents=True, exist_ok=True)
        blob_name = _hash_path(dest)
        blob_path = self.blob_dir / blob_name

        # Encrypt the file content
        plaintext = source.read_bytes()
        ciphertext = self.fernet.encrypt(plaintext)
        blob_path.write_bytes(ciphertext)

        # Update .wraith-secrets
        entries = self._entries()

        # Remove any existing entry for the same dest (replace)
        entries = [e for e in entries if e.dest != dest]

        entries.append(SecretEntry(blob_path=blob_path, dest=dest))
        self._save_entries(entries)

        print(f"Encrypted {source} -> {dest} (blob: {blob_path.relative_to(self.repo_root)})")
        print(f"Add {self.secrets_file.name} and {SECRETS_BLOB_DIR}/ to your .gitignore!")

    def install(self) -> None:
        """Decrypt all secrets and write them to their destinations."""
        entries = self._entries()
        if not entries:
            print("No secrets tracked.")
            return

        print(f"Decrypting {len(entries)} secret(s) ...")
        for entry in entries:
            if not entry.blob_path.exists():
                print(f"  ! blob missing for {entry.dest} — cannot decrypt")
                continue

            ciphertext = entry.blob_path.read_bytes()
            try:
                plaintext = self.fernet.decrypt(ciphertext)
            except Exception as exc:
                print(f"  ! decryption failed for {entry.dest}: {exc}")
                continue

            # Validate dest is under HOME (block path traversal)
            home = Path(os.environ["HOME"]).resolve()
            try:
                resolved_dest = entry.dest.resolve()
                resolved_dest.relative_to(home)
            except ValueError:
                print(f"  ! refusing to write outside HOME: {entry.dest}")
                continue

            entry.dest.parent.mkdir(parents=True, exist_ok=True)
            _write_secure(entry.dest, plaintext)
            print(f"  ✓ {entry.dest}")

        print("Done.")

    def status(self) -> None:
        """Show which secrets are tracked and where they go."""
        entries = self._entries()
        if not entries:
            print("No secrets tracked.")
            return
        for entry in entries:
            exists = "✓ blob" if entry.blob_path.exists() else "✗ blob missing"
            print(f"  {exists}  -> {entry.dest}")

    def remove(self, dest: Path) -> None:
        """Remove a secret by its destination path."""
        dest = dest.expanduser()
        entries = self._entries()
        before = len(entries)
        entries = [e for e in entries if e.dest != dest]
        if len(entries) == before:
            print(f"No secret found for {dest}")
            return

        self._save_entries(entries)
        print(f"Removed secret entry for {dest}")
        print("  Note: the encrypted blob file was NOT deleted from disk.")
        print("  Clean it up manually or run: git rm -r .wraith-secrets/<old_hash>")

    def sync(self) -> None:
        """Commit secrets to git (doesn't push — do that separately)."""
        if not self.secrets_file.exists() and not self.blob_dir.exists():
            print("No secrets to sync.")
            return

        subprocess.run(["git", "add", str(self.secrets_file), str(self.blob_dir)], check=True)
        result = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
        )
        if result.returncode == 0:
            print("No secret changes to commit.")
            return

        stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        subprocess.run(["git", "commit", "-m", f"wraith: sync secrets {stamp}"], check=True)
        print("Secrets committed.")
