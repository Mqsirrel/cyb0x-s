"""Tests for the derive-guidance runtime gate (`cyb0x_s.settings`)."""

import pytest

from cyb0x_s.settings import (
    ENV_VAR,
    derive_guidance_enabled,
    describe_derive_guidance,
    set_derive_guidance,
)


@pytest.fixture(autouse=True)
def _reset_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENV_VAR, raising=False)
    set_derive_guidance(None)
    yield
    set_derive_guidance(None)


def test_off_by_default_when_env_unset() -> None:
    assert derive_guidance_enabled() is False


@pytest.mark.parametrize("truthy", ["1", "true", "yes", "on", "enabled", " True "])
def test_env_truthy(monkeypatch: pytest.MonkeyPatch, truthy: str) -> None:
    monkeypatch.setenv(ENV_VAR, truthy)
    assert derive_guidance_enabled() is True


@pytest.mark.parametrize("falsy", ["0", "false", "no", "off", "disabled"])
def test_env_falsy(monkeypatch: pytest.MonkeyPatch, falsy: str) -> None:
    monkeypatch.setenv(ENV_VAR, falsy)
    assert derive_guidance_enabled() is False


def test_override_wins_and_clears(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_VAR, "1")
    assert derive_guidance_enabled() is True

    set_derive_guidance(False)
    assert derive_guidance_enabled() is False

    set_derive_guidance(None)
    assert derive_guidance_enabled() is True


def test_describe_and_coercion() -> None:
    set_derive_guidance(True)
    assert describe_derive_guidance() == "on"
    assert derive_guidance_enabled() is True

    set_derive_guidance(0)
    assert derive_guidance_enabled() is False
    assert describe_derive_guidance() == "off"
