"""Tests for configuration helpers."""

from azt3knet.core import config


def test_get_settings_reads_environment_and_compliance(monkeypatch):
    """Ensure get_settings respects environment variables."""

    config.get_settings.cache_clear()
    monkeypatch.setenv("AZT3KNET_ENVIRONMENT", "staging")
    monkeypatch.setenv("AZT3KNET_COMPLIANCE_ENABLED", "false")

    settings = config.get_settings()

    assert settings.environment == "staging"
    assert settings.compliance_enabled is False

    config.get_settings.cache_clear()
