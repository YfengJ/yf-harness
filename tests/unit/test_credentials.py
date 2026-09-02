from __future__ import annotations

import pytest

from yfharness.config.credentials import CredentialStore


def test_environment_precedes_keyring(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("keyring.get_password", lambda service, name: "stored")

    assert CredentialStore().get("SEARCH_KEY", environ={"SEARCH_KEY": "environment"}) == (
        "environment"
    )
    assert CredentialStore().get("SEARCH_KEY", environ={}) == "stored"


def test_credentials_write_without_exposing_value(monkeypatch: pytest.MonkeyPatch) -> None:
    written: list[tuple[str, str, str]] = []
    monkeypatch.setattr(
        "keyring.set_password",
        lambda service, name, value: written.append((service, name, value)),
    )

    CredentialStore().set("SEARCH_KEY", "secret-value")

    assert written == [("YF-Harness", "SEARCH_KEY", "secret-value")]
