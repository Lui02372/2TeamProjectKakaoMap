-- 부산여행 가이드 2팀: custom username authentication and normalized guide data.
-- Keep the original educational favorite table without deleting its data.
alter table if exists public.favorite_places rename to legacy_favorite_places;

create table public.app_users (
    id uuid primary key default gen_random_uuid(),
    username text not null,
    normalized_username text not null unique,
    password_hash text not null check (password_hash like '$argon2id$%'),
    is_active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    check (normalized_username ~ '^[a-z0-9_]{4,30}$')
);

create table public.user_profiles (
    user_id uuid primary key references public.app_users(id) on delete cascade,
    display_name text not null check (char_length(trim(display_name)) between 1 and 40),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table public.user_sessions (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references public.app_users(id) on delete cascade,
    token_hash text not null unique check (char_length(token_hash) = 64),
    expires_at timestamptz not null,
    revoked_at timestamptz,
    created_at timestamptz not null default now()
);
create index user_sessions_token_expiry_idx on public.user_sessions (token_hash, expires_at) where revoked_at is null;

create table public.chat_threads (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references public.app_users(id) on delete cascade,
    title text not null default '새 부산 여행 대화',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create index chat_threads_user_updated_idx on public.chat_threads (user_id, updated_at desc);

create table public.chat_messages (
    id uuid primary key default gen_random_uuid(),
    thread_id uuid not null references public.chat_threads(id) on delete cascade,
    role text not null check (role in ('user', 'assistant')),
    content text not null check (char_length(trim(content)) between 1 and 4000),
    structured_intent jsonb,
    created_at timestamptz not null default now()
);
create index chat_messages_thread_order_idx on public.chat_messages (thread_id, created_at, id);

create table public.place_searches (
    id uuid primary key default gen_random_uuid(),
    message_id uuid not null unique references public.chat_messages(id) on delete cascade,
    region text not null default '부산',
    district text not null default '',
    category text not null check (category in ('food', 'cafe', 'attraction', 'shopping', 'all')),
    keyword text not null,
    center_latitude double precision,
    center_longitude double precision,
    radius_meters integer check (radius_meters between 100 and 20000),
    created_at timestamptz not null default now(),
    check (center_latitude is null or center_latitude between -90 and 90),
    check (center_longitude is null or center_longitude between -180 and 180)
);

create table public.places (
    id uuid primary key default gen_random_uuid(),
    kakao_place_id text not null unique,
    name text not null,
    category_name text not null default '',
    category_group_code text not null default '',
    address text not null default '',
    road_address text not null default '',
    latitude double precision not null check (latitude between -90 and 90),
    longitude double precision not null check (longitude between -180 and 180),
    phone text not null default '',
    kakao_place_url text not null check (kakao_place_url like 'https://place.map.kakao.com/%'),
    raw_snapshot jsonb not null default '{}'::jsonb,
    last_verified_at timestamptz not null default now()
);

create table public.search_results (
    search_id uuid not null references public.place_searches(id) on delete cascade,
    place_id uuid not null references public.places(id) on delete restrict,
    result_rank integer not null check (result_rank >= 1),
    distance_meters integer check (distance_meters >= 0),
    recommendation_reason text not null default '',
    primary key (search_id, place_id),
    unique (search_id, result_rank)
);

create table public.favorite_places (
    user_id uuid not null references public.app_users(id) on delete cascade,
    place_id uuid not null references public.places(id) on delete restrict,
    created_at timestamptz not null default now(),
    primary key (user_id, place_id)
);
create index favorite_places_user_created_idx on public.favorite_places (user_id, created_at desc);

create table public.travel_plans (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references public.app_users(id) on delete cascade,
    thread_id uuid references public.chat_threads(id) on delete set null,
    title text not null,
    summary text not null default '',
    days integer not null check (days between 1 and 31),
    created_at timestamptz not null default now()
);

create table public.travel_plan_places (
    plan_id uuid not null references public.travel_plans(id) on delete cascade,
    place_id uuid not null references public.places(id) on delete restrict,
    day_number integer not null check (day_number between 1 and 31),
    display_order integer not null check (display_order >= 1),
    note text not null default '',
    primary key (plan_id, place_id),
    unique (plan_id, day_number, display_order)
);

create or replace function public.register_app_user(
    p_username text, p_normalized_username text, p_password_hash text, p_display_name text
) returns table (id uuid, username text, password_hash text, is_active boolean, user_profiles jsonb)
language plpgsql security definer set search_path = public
as $$
declare new_user public.app_users;
begin
    insert into public.app_users (username, normalized_username, password_hash)
    values (p_username, p_normalized_username, p_password_hash) returning * into new_user;
    insert into public.user_profiles (user_id, display_name) values (new_user.id, p_display_name);
    return query select new_user.id, new_user.username, new_user.password_hash, new_user.is_active,
        jsonb_build_object('display_name', p_display_name);
end;
$$;
revoke all on function public.register_app_user(text, text, text, text) from public, anon, authenticated;
grant execute on function public.register_app_user(text, text, text, text) to service_role;

alter table public.app_users enable row level security;
alter table public.user_profiles enable row level security;
alter table public.user_sessions enable row level security;
alter table public.chat_threads enable row level security;
alter table public.chat_messages enable row level security;
alter table public.place_searches enable row level security;
alter table public.places enable row level security;
alter table public.search_results enable row level security;
alter table public.favorite_places enable row level security;
alter table public.travel_plans enable row level security;
alter table public.travel_plan_places enable row level security;

-- No anon/authenticated policies are created. Only the backend service role accesses these tables.
