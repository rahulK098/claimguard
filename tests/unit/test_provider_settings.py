"""ProviderSettings: env var names and defaults.

Every test disables `.env` loading (`_env_file=None`) and controls the
process environment explicitly via monkeypatch, so these are deterministic
regardless of what's actually in this machine's shell or repo `.env`.
"""

import pytest

from claimguard.llm.provider_settings import ProviderSettings


@pytest.fixture(autouse=True)
def _clear_provider_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in (
        "LLM_PROVIDER",
        "ANTHROPIC_API_KEY",
        "AZURE_OPENAI_KEY",
        "AZURE_OPENAI_KEY2",
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_DEPLOYMENT",
        "AZURE_OPENAI_API_VERSION",
        "OPENROUTER_API_KEY",
        "OPENROUTER_MODEL",
        "GROQ_API_KEY",
        "GROQ_MODEL",
        "GEMINI_API_KEY",
        "GEMINI_MODEL",
        "DEEPSEEK_API_KEY",
        "DEEPSEEK_MODEL",
        "OLLAMA_BASE_URL",
        "OLLAMA_MODEL",
        "CLAIMGUARD_MODEL",
    ):
        monkeypatch.delenv(var, raising=False)


def test_defaults_with_no_env_at_all() -> None:
    settings = ProviderSettings(_env_file=None)
    assert settings.provider == "azure"
    assert settings.azure_openai_deployment == "chat"
    assert settings.azure_openai_api_version == "2024-10-21"
    assert settings.openrouter_model == "meta-llama/llama-3.3-70b-instruct:free"
    assert settings.groq_model == "llama-3.3-70b-versatile"
    assert settings.gemini_model == "gemini-2.5-flash"
    assert settings.deepseek_model == "deepseek-chat"
    assert settings.ollama_base_url == "http://localhost:11434"
    assert settings.ollama_model == "qwen2.5:3b"
    assert settings.anthropic_api_key == ""
    assert settings.azure_openai_key == ""


def test_llm_provider_env_var_selects_primary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    settings = ProviderSettings(_env_file=None)
    assert settings.provider == "groq"


def test_plain_env_var_names_are_honored(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exactly the env var names from the operator's existing convention --
    no CLAIMGUARD_ prefix -- so an existing .env just works."""
    monkeypatch.setenv("AZURE_OPENAI_KEY", "key-1")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.setenv("GROQ_API_KEY", "groq-key")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-key")

    settings = ProviderSettings(_env_file=None)
    assert settings.azure_openai_key == "key-1"
    assert settings.azure_openai_endpoint == "https://example.openai.azure.com"
    assert settings.groq_api_key == "groq-key"
    assert settings.gemini_api_key == "gemini-key"


def test_direct_construction_by_field_name_also_works() -> None:
    """populate_by_name=True: field names work directly too, not just aliases
    -- needed so tests can construct settings without touching os.environ."""
    settings = ProviderSettings(
        _env_file=None,
        provider="anthropic",
        anthropic_api_key="sk-ant-test",
        azure_openai_key="azure-test",
    )
    assert settings.provider == "anthropic"
    assert settings.anthropic_api_key == "sk-ant-test"
    assert settings.azure_openai_key == "azure-test"


def test_cost_override_fields_default_to_none() -> None:
    settings = ProviderSettings(_env_file=None)
    assert settings.azure_input_usd_per_mtok is None
    assert settings.azure_output_usd_per_mtok is None
    assert settings.groq_input_usd_per_mtok is None
    assert settings.deepseek_input_usd_per_mtok is None
    assert settings.openrouter_input_usd_per_mtok is None
