from pathlib import Path

from app.config import Settings

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _template_values() -> dict[str, str]:
    values: dict[str, str] = {}
    for line in (PROJECT_ROOT / ".env.example").read_text(encoding="utf-8").splitlines():
        if line and not line.lstrip().startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
    return values


def test_environment_template_contains_required_deployment_keys() -> None:
    values = _template_values()
    required = {
        "SUPABASE_URL",
        "SUPABASE_PUBLISHABLE_KEY",
        "SUPABASE_SERVICE_ROLE_KEY",
        "SUPABASE_JWT_AUDIENCE",
        "REDIS_URL",
        "UPSTASH_REDIS_REST_URL",
        "UPSTASH_REDIS_REST_TOKEN",
        "VOICE_MAX_UPLOAD_MB",
        "WHISPER_MODEL",
        "PIPER_VOICE",
        "TTS_PROVIDER",
        "VISION_PROVIDER",
        "GEMINI_TTS_MODEL",
        "GEMINI_VISION_MODEL",
        "KAKAO_JAVASCRIPT_KEY",
    }
    assert required <= values.keys()


def test_environment_template_never_contains_real_secret_values() -> None:
    values = _template_values()
    secrets = {
        "SUPABASE_PUBLISHABLE_KEY",
        "SUPABASE_SERVICE_ROLE_KEY",
        "UPSTASH_REDIS_REST_TOKEN",
        "OPENAI_API_KEY",
        "GEMINI_API_KEY",
        "KAKAO_REST_API_KEY",
    }
    assert all(values.get(key, "") == "" for key in secrets)


def test_jwks_url_is_derived_from_the_public_supabase_url(monkeypatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://project-ref.supabase.co/")

    assert Settings().supabase_jwks_url == (
        "https://project-ref.supabase.co/auth/v1/.well-known/jwks.json"
    )


def test_requirements_include_cloud_state_and_free_voice_adapters() -> None:
    requirements = (PROJECT_ROOT / "requirements.txt").read_text(encoding="utf-8")
    for package in (
        "supabase",
        "upstash-redis",
        "sse-starlette",
        "faster-whisper",
        "piper-tts",
    ):
        assert package in requirements
