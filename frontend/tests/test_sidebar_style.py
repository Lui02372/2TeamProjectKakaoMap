from pathlib import Path


APP_SOURCE = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")


def test_sidebar_does_not_force_white_text_on_every_widget() -> None:
    assert '[data-testid="stSidebar"] *' not in APP_SOURCE


def test_sidebar_white_controls_use_dark_readable_text() -> None:
    assert '[data-testid="stSidebar"] .stButton button *' in APP_SOURCE
    assert '[data-testid="stSidebar"] [data-baseweb="select"] *' in APP_SOURCE
    assert "color:#073b4c !important" in APP_SOURCE


def test_signup_help_matches_four_character_password_policy() -> None:
    assert 'help="4자 이상 입력해 주세요."' in APP_SOURCE
