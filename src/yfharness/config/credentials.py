"""System credential storage with environment-variable precedence."""

from __future__ import annotations

import os
from collections.abc import Mapping

import keyring
from keyring.errors import KeyringError

_SERVICE = "YF-Harness"


class CredentialError(RuntimeError):
    """The operating-system credential store was unavailable."""


class CredentialStore:
    def get(
        self,
        name: str,
        *,
        environ: Mapping[str, str] | None = None,
    ) -> str | None:
        source = environ if environ is not None else os.environ
        if value := source.get(name):
            return value
        try:
            return keyring.get_password(_SERVICE, name)
        except KeyringError as exc:
            raise CredentialError(f"系统凭据库不可用: {exc}") from exc

    def set(self, name: str, value: str) -> None:
        if not value:
            raise ValueError("凭据不能为空")
        try:
            keyring.set_password(_SERVICE, name, value)
        except KeyringError as exc:
            raise CredentialError(f"无法写入系统凭据库: {exc}") from exc

    def delete(self, name: str) -> None:
        try:
            keyring.delete_password(_SERVICE, name)
        except keyring.errors.PasswordDeleteError:
            return
        except KeyringError as exc:
            raise CredentialError(f"无法删除系统凭据: {exc}") from exc
