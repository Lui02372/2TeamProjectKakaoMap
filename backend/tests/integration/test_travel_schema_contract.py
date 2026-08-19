from pathlib import Path


MIGRATION = (
    Path(__file__).resolve().parents[3]
    / "supabase"
    / "migrations"
    / "0001_travel_service.sql"
)


def test_migration_enables_rls_for_every_user_table() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").lower()
    for table in (
        "profiles",
        "travel_requests",
        "trips",
        "trip_places",
        "favorite_places",
    ):
        assert f"alter table public.{table} enable row level security" in sql


def test_migration_scopes_user_rows_with_auth_uid() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").lower()
    assert "(select auth.uid()) = user_id" in sql
    assert "references auth.users(id) on delete cascade" in sql


def test_migration_prevents_duplicate_user_favorites() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").lower()
    assert "unique (user_id, kakao_place_id)" in sql
