import os


# Default tests must never consume credentials from a developer's local .env.
# External smoke tests can opt in explicitly with RUN_EXTERNAL_TESTS=1.
if os.getenv("RUN_EXTERNAL_TESTS") != "1":
    os.environ["PYTHON_DOTENV_DISABLED"] = "1"
    os.environ["LLM_PROVIDER"] = "mock"
    os.environ["OPENAI_API_KEY"] = ""
    os.environ["GEMINI_API_KEY"] = ""
    os.environ["GEMINI_MODEL"] = ""
    os.environ["KAKAO_REST_API_KEY"] = ""
