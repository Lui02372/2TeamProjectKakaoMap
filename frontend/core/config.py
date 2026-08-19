"""프런트엔드 환경 설정."""

import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://127.0.0.1:8000").rstrip("/")

try:
    REQUEST_TIMEOUT_SECONDS = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "60"))
except ValueError:
    REQUEST_TIMEOUT_SECONDS = 60.0

KAKAO_JAVASCRIPT_KEY = os.getenv("KAKAO_JAVASCRIPT_KEY", "").strip()
