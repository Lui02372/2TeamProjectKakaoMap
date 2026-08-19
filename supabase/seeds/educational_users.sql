-- 교육용 예시 계정: id01 / pw01, id02 / pw02
-- 비밀번호는 앱과 같은 Argon2id 해시로만 저장됩니다.
-- supabase/migrations/0002_busan_guide.sql 실행 후 SQL Editor에서 실행하세요.

do $$
declare
    user_one_id uuid;
    user_two_id uuid;
begin
    insert into public.app_users (
        username, normalized_username, password_hash, is_active
    ) values (
        'id01',
        'id01',
        '$argon2id$v=19$m=65536,t=3,p=4$WlZjuHmvZDpoigjwbvI8TQ$Yr2rzEPOW3du5Kcjj27BCKJKVlwVibN0QZYu6KgsH30',
        true
    )
    on conflict (normalized_username) do update set
        username = excluded.username,
        password_hash = excluded.password_hash,
        is_active = true,
        updated_at = now()
    returning id into user_one_id;

    insert into public.user_profiles (user_id, display_name)
    values (user_one_id, '부산 여행자 1')
    on conflict (user_id) do update set
        display_name = excluded.display_name,
        updated_at = now();

    insert into public.app_users (
        username, normalized_username, password_hash, is_active
    ) values (
        'id02',
        'id02',
        '$argon2id$v=19$m=65536,t=3,p=4$P1obHzihWvQzq6O2HrPSjw$BYQFjN9quat5mrieHsU7L54F5jB9408s3uNG9W5A7X4',
        true
    )
    on conflict (normalized_username) do update set
        username = excluded.username,
        password_hash = excluded.password_hash,
        is_active = true,
        updated_at = now()
    returning id into user_two_id;

    insert into public.user_profiles (user_id, display_name)
    values (user_two_id, '부산 여행자 2')
    on conflict (user_id) do update set
        display_name = excluded.display_name,
        updated_at = now();
end
$$;
