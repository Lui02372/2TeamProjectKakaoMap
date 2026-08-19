from pathlib import Path


MIGRATION = Path(__file__).resolve().parents[3] / "supabase" / "migrations" / "0002_busan_guide.sql"


def test_guide_migration_contains_normalized_relationships() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    for table in (
        "app_users", "user_profiles", "user_sessions", "chat_threads",
        "chat_messages", "place_searches", "places", "search_results",
        "favorite_places", "travel_plans", "travel_plan_places",
    ):
        assert f"create table public.{table}" in sql

    assert "password_hash text not null" in sql
    assert "password text" not in sql
    assert "unique (search_id, result_rank)" in sql
    assert "primary key (user_id, place_id)" in sql
    assert "on delete restrict" in sql
    assert "user_sessions_token_expiry_idx" in sql

