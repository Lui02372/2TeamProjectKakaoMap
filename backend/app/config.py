from dataclasses import dataclass, field
import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / "backend" / ".env")
load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    llm_provider: str = os.getenv("LLM_PROVIDER", "mock")
    supabase_url: str = field(
        default_factory=lambda: os.getenv("SUPABASE_URL", "").rstrip("/")
    )
    supabase_publishable_key: str = field(
        default_factory=lambda: os.getenv("SUPABASE_PUBLISHABLE_KEY", "")
    )
    supabase_service_role_key: str = field(
        default_factory=lambda: os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    )
    supabase_jwt_audience: str = field(
        default_factory=lambda: os.getenv("SUPABASE_JWT_AUDIENCE", "authenticated")
    )
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    openai_vision_model: str = os.getenv("OPENAI_VISION_MODEL", "gpt-4.1-mini")
    openai_tts_model: str = os.getenv("OPENAI_TTS_MODEL", "gpt-4o-mini-tts")
    openai_tts_voice: str = os.getenv("OPENAI_TTS_VOICE", "coral")
    max_image_size_mb: int = int(os.getenv("MAX_IMAGE_SIZE_MB", "5"))
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "")
    ollama_base_url: str = os.getenv(
        "OLLAMA_BASE_URL", "http://127.0.0.1:11434"
    ).rstrip("/")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "llama3.2")
    kakao_rest_api_key: str = os.getenv("KAKAO_REST_API_KEY", "")
    kakao_local_base_url: str = os.getenv(
        "KAKAO_LOCAL_BASE_URL", "https://dapi.kakao.com"
    ).rstrip("/")
    kakao_request_timeout_seconds: float = float(
        os.getenv("KAKAO_REQUEST_TIMEOUT_SECONDS", "5")
    )
    kakao_search_size: int = int(os.getenv("KAKAO_SEARCH_SIZE", "10"))
    kakao_max_retries: int = int(os.getenv("KAKAO_MAX_RETRIES", "1"))
    request_timeout_seconds: float = float(
        os.getenv("REQUEST_TIMEOUT_SECONDS", "60")
    )
    session_ttl_hours: int = int(os.getenv("SESSION_TTL_HOURS", "168"))

    @property
    def supabase_jwks_url(self) -> str:
        """Return Supabase Auth's public signing-key discovery endpoint."""

        if not self.supabase_url:
            return ""
        return f"{self.supabase_url}/auth/v1/.well-known/jwks.json"


settings = Settings()
