"""Multi-provider LLM configuration.

Env var names deliberately match the plain (non-`CLAIMGUARD_`-prefixed)
convention the operator asked for -- `LLM_PROVIDER`, `AZURE_OPENAI_KEY`,
`GROQ_API_KEY`, and so on -- so a `.env` written for that convention just
works: whichever provider keys are actually present activate automatically
via `llm.fallback.build_default_chain`, no per-provider wiring needed. The
few settings that are this project's own concept (cost-rate overrides) use
the `CLAIMGUARD_` prefix since they aren't part of that external convention.

`provider` (`LLM_PROVIDER`) selects which provider is tried *first*; every
other provider with credentials present becomes a fallback, in the fixed
order `_CANONICAL_ORDER` in `llm.fallback`, with local Ollama always last.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ProviderSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        populate_by_name=True,
    )

    provider: str = Field(default="azure", validation_alias="LLM_PROVIDER")

    # --- Anthropic -----------------------------------------------------
    anthropic_api_key: str = Field(default="", validation_alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(default="claude-opus-5", validation_alias="CLAIMGUARD_MODEL")

    # --- Azure OpenAI ----------------------------------------------------
    azure_openai_key: str = Field(default="", validation_alias="AZURE_OPENAI_KEY")
    azure_openai_key2: str = Field(
        default="", validation_alias="AZURE_OPENAI_KEY2"
    )  # secondary key for zero-downtime rotation -- tried if the primary fails
    azure_openai_endpoint: str = Field(default="", validation_alias="AZURE_OPENAI_ENDPOINT")
    azure_openai_deployment: str = Field(default="chat", validation_alias="AZURE_OPENAI_DEPLOYMENT")
    azure_openai_api_version: str = Field(
        default="2024-10-21", validation_alias="AZURE_OPENAI_API_VERSION"
    )
    azure_input_usd_per_mtok: float | None = Field(
        default=None, validation_alias="CLAIMGUARD_AZURE_INPUT_USD_PER_MTOK"
    )
    azure_output_usd_per_mtok: float | None = Field(
        default=None, validation_alias="CLAIMGUARD_AZURE_OUTPUT_USD_PER_MTOK"
    )

    # --- OpenRouter --------------------------------------------------------
    openrouter_api_key: str = Field(default="", validation_alias="OPENROUTER_API_KEY")
    openrouter_model: str = Field(
        default="meta-llama/llama-3.3-70b-instruct:free", validation_alias="OPENROUTER_MODEL"
    )
    openrouter_input_usd_per_mtok: float | None = Field(
        default=None, validation_alias="CLAIMGUARD_OPENROUTER_INPUT_USD_PER_MTOK"
    )
    openrouter_output_usd_per_mtok: float | None = Field(
        default=None, validation_alias="CLAIMGUARD_OPENROUTER_OUTPUT_USD_PER_MTOK"
    )

    # --- Groq --------------------------------------------------------------
    groq_api_key: str = Field(default="", validation_alias="GROQ_API_KEY")
    groq_model: str = Field(default="llama-3.3-70b-versatile", validation_alias="GROQ_MODEL")
    groq_input_usd_per_mtok: float | None = Field(
        default=None, validation_alias="CLAIMGUARD_GROQ_INPUT_USD_PER_MTOK"
    )
    groq_output_usd_per_mtok: float | None = Field(
        default=None, validation_alias="CLAIMGUARD_GROQ_OUTPUT_USD_PER_MTOK"
    )

    # --- Gemini --------------------------------------------------------------
    gemini_api_key: str = Field(default="", validation_alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-2.5-flash", validation_alias="GEMINI_MODEL")

    # --- DeepSeek ------------------------------------------------------------
    deepseek_api_key: str = Field(default="", validation_alias="DEEPSEEK_API_KEY")
    deepseek_model: str = Field(default="deepseek-chat", validation_alias="DEEPSEEK_MODEL")
    deepseek_input_usd_per_mtok: float | None = Field(
        default=None, validation_alias="CLAIMGUARD_DEEPSEEK_INPUT_USD_PER_MTOK"
    )
    deepseek_output_usd_per_mtok: float | None = Field(
        default=None, validation_alias="CLAIMGUARD_DEEPSEEK_OUTPUT_USD_PER_MTOK"
    )

    # --- Ollama (local, always eligible, no credentials needed) -------------
    ollama_base_url: str = Field(
        default="http://localhost:11434", validation_alias="OLLAMA_BASE_URL"
    )
    ollama_model: str = Field(default="qwen2.5:3b", validation_alias="OLLAMA_MODEL")


@lru_cache
def get_provider_settings() -> ProviderSettings:
    return ProviderSettings()
