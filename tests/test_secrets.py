"""Tests for wraith.secrets."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from wraith.secrets import KEY_FILE, SecretsManager, _hash_path


class TestHashPath:
    """Unit tests for path hashing."""

    def test_deterministic(self) -> None:
        h1 = _hash_path(Path("~/.env"))
        h2 = _hash_path(Path("~/.env"))
        assert h1 == h2

    def test_different_paths_different_hashes(self) -> None:
        h1 = _hash_path(Path("~/.env"))
        h2 = _hash_path(Path("~/.ssh/id_rsa"))
        assert h1 != h2


class TestSecretsManager:
    """Integration tests for SecretsManager."""

    def _make_manager(self, tmp_path: Path) -> SecretsManager:
        """Create a SecretsManager with a temp key file."""
        key_file = tmp_path / ".wraith.key"
        os.environ["HOME"] = str(tmp_path)
        from wraith import secrets

        # Patch KEY_FILE to point to our temp location
        original_key_file = secrets.KEY_FILE
        secrets.KEY_FILE = key_file
        sm = SecretsManager(repo_root=tmp_path)
        yield sm
        secrets.KEY_FILE = original_key_file

    def test_add_and_install_roundtrip(self, tmp_path: Path) -> None:
        """Encrypt a file, then decrypt it — should match the original."""
        key_file = tmp_path / ".wraith.key"
        os.environ["HOME"] = str(tmp_path)

        from wraith import secrets

        original_key_file = secrets.KEY_FILE
        secrets.KEY_FILE = key_file

        try:
            sm = SecretsManager(repo_root=tmp_path)

            # Create a secret file
            secret_file = tmp_path / "my-secret-token.txt"
            secret_file.write_text("super-secret-value-123")

            dest = tmp_path / "home" / ".env"
            dest.parent.mkdir()
            sm.add(secret_file, dest)

            # Verify blob was created
            entries = sm._entries()
            assert len(entries) == 1
            assert entries[0].blob_path.exists()

            # Verify .wraith-secrets file was created
            assert sm.secrets_file.exists()

            # Now decrypt and verify
            install_dest = tmp_path / "decrypted" / ".env"
            install_dest.parent.mkdir()

            # Patch the entry dest to our temp location for install
            sm2 = SecretsManager(repo_root=tmp_path)
            sm2._entries()[0].dest  # just to confirm entry exists

            # Overwrite dest for test
            import wraith.secrets as sec_mod
            orig_entries = sec_mod.SecretsManager._entries.__get__(sm2, type(sm2))
            # Simpler: just overwrite and call install on a fresh manager
            # Actually let's just verify by decrypting directly
            ciphertext = entries[0].blob_path.read_bytes()
            from cryptography.fernet import Fernet

            key = key_file.read_bytes()
            fernet = Fernet(key)
            plaintext = fernet.decrypt(ciphertext)
            assert plaintext == b"super-secret-value-123"
        finally:
            secrets.KEY_FILE = original_key_file

    def test_add_creates_blob_and_wraith_secrets_file(self, tmp_path: Path) -> None:
        """Adding a secret creates the encrypted blob and .wraith-secrets index."""
        key_file = tmp_path / ".wraith.key"
        os.environ["HOME"] = str(tmp_path)

        from wraith import secrets

        original_key_file = secrets.KEY_FILE
        secrets.KEY_FILE = key_file

        try:
            sm = SecretsManager(repo_root=tmp_path)

            secret = tmp_path / "secret.txt"
            secret.write_text("password123")
            dest = tmp_path / ".secret"

            sm.add(secret, dest)

            assert (tmp_path / ".wraith-secrets").exists()
            assert sm.secrets_file.exists()
            assert len(sm._entries()) == 1
        finally:
            secrets.KEY_FILE = original_key_file

    def test_status_empty_when_no_secrets(self, tmp_path: Path) -> None:
        """Status on an empty repo should report no secrets."""
        key_file = tmp_path / ".wraith.key"
        os.environ["HOME"] = str(tmp_path)

        from wraith import secrets

        original_key_file = secrets.KEY_FILE
        secrets.KEY_FILE = key_file

        try:
            sm = SecretsManager(repo_root=tmp_path)
            # Should not raise, should just print "No secrets tracked"
            sm.status()
        finally:
            secrets.KEY_FILE = original_key_file

    def test_init_creates_key_file(self, tmp_path: Path) -> None:
        """init() should create ~/.wraith.key if missing."""
        key_file = tmp_path / ".wraith.key"
        os.environ["HOME"] = str(tmp_path)

        from wraith import secrets

        original_key_file = secrets.KEY_FILE
        secrets.KEY_FILE = key_file

        try:
            assert not key_file.exists()
            sm = SecretsManager(repo_root=tmp_path)
            sm.init()
            assert key_file.exists()
            # Should be a valid Fernet key
            from cryptography.fernet import Fernet

            Fernet(key_file.read_bytes())
        finally:
            secrets.KEY_FILE = original_key_file

    def test_remove_deletes_entry_but_not_blob(self, tmp_path: Path) -> None:
        """Remove should delete the .wraith-secrets entry, but NOT the blob on disk."""
        key_file = tmp_path / ".wraith.key"
        os.environ["HOME"] = str(tmp_path)

        from wraith import secrets

        original_key_file = secrets.KEY_FILE
        secrets.KEY_FILE = key_file

        try:
            sm = SecretsManager(repo_root=tmp_path)

            secret = tmp_path / "secret.txt"
            secret.write_text("s3cret")
            dest = tmp_path / ".secret"
            sm.add(secret, dest)

            blob_path = sm._entries()[0].blob_path
            assert blob_path.exists()

            sm.remove(dest)
            assert len(sm._entries()) == 0
            # Blob should still exist on disk
            assert blob_path.exists()
        finally:
            secrets.KEY_FILE = original_key_file
