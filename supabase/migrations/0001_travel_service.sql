-- Supabase Cloud migration: authenticated travel data with owner-only access.

create table public.profiles (
    user_id uuid primary key references auth.users(id) on delete cascade,
    display_name text not null default '',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table public.travel_requests (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    query text not null check (char_length(trim(query)) between 1 and 2000),
    input_source text not null check (input_source in ('text', 'voice')),
    status text not null default 'queued' check (status in ('queued', 'running', 'completed', 'failed')),
    created_at timestamptz not null default now()
);

create table public.trips (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    request_id uuid not null unique references public.travel_requests(id) on delete cascade,
    destination text not null,
    nights integer not null check (nights between 0 and 30),
    days integer not null check (days between 1 and 31),
    summary text not null default '',
    created_at timestamptz not null default now(),
    check (days = nights + 1)
);

create table public.trip_places (
    id uuid primary key default gen_random_uuid(),
    trip_id uuid not null references public.trips(id) on delete cascade,
    kakao_place_id text not null,
    place_type text not null check (place_type in ('landmark', 'food')),
    name text not null,
    day_number integer not null check (day_number between 1 and 31),
    display_order integer not null check (display_order >= 1),
    latitude double precision not null check (latitude between -90 and 90),
    longitude double precision not null check (longitude between -180 and 180),
    kakao_place_url text not null check (kakao_place_url like 'https://place.map.kakao.com/%'),
    place_snapshot jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    unique (trip_id, kakao_place_id)
);

create table public.favorite_places (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    kakao_place_id text not null,
    place_snapshot jsonb not null,
    created_at timestamptz not null default now(),
    unique (user_id, kakao_place_id)
);

create index travel_requests_user_created_idx on public.travel_requests (user_id, created_at desc);
create index trips_user_created_idx on public.trips (user_id, created_at desc);
create index trip_places_trip_order_idx on public.trip_places (trip_id, day_number, display_order);
create index favorite_places_user_created_idx on public.favorite_places (user_id, created_at desc);

create or replace function public.handle_profile_updated_at()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

create trigger profiles_set_updated_at
before update on public.profiles
for each row execute procedure public.handle_profile_updated_at();

create or replace function public.create_profile_for_new_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
    insert into public.profiles (user_id, display_name)
    values (new.id, coalesce(new.raw_user_meta_data ->> 'display_name', ''));
    return new;
end;
$$;

create trigger auth_user_created_profile
after insert on auth.users
for each row execute procedure public.create_profile_for_new_user();

alter table public.profiles enable row level security;
alter table public.travel_requests enable row level security;
alter table public.trips enable row level security;
alter table public.trip_places enable row level security;
alter table public.favorite_places enable row level security;

create policy "profiles owner read" on public.profiles
for select to authenticated using ((select auth.uid()) = user_id);
create policy "profiles owner update" on public.profiles
for update to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);

create policy "requests owner read" on public.travel_requests
for select to authenticated using ((select auth.uid()) = user_id);
create policy "requests owner insert" on public.travel_requests
for insert to authenticated with check ((select auth.uid()) = user_id);
create policy "requests owner update" on public.travel_requests
for update to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);

create policy "trips owner read" on public.trips
for select to authenticated using ((select auth.uid()) = user_id);
create policy "trips owner insert" on public.trips
for insert to authenticated with check ((select auth.uid()) = user_id);
create policy "trips owner update" on public.trips
for update to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);

create policy "trip places owner read" on public.trip_places
for select to authenticated using (
    exists (
        select 1 from public.trips
        where trips.id = trip_id and trips.user_id = (select auth.uid())
    )
);
create policy "trip places owner insert" on public.trip_places
for insert to authenticated with check (
    exists (
        select 1 from public.trips
        where trips.id = trip_id and trips.user_id = (select auth.uid())
    )
);
create policy "trip places owner update" on public.trip_places
for update to authenticated using (
    exists (
        select 1 from public.trips
        where trips.id = trip_id and trips.user_id = (select auth.uid())
    )
) with check (
    exists (
        select 1 from public.trips
        where trips.id = trip_id and trips.user_id = (select auth.uid())
    )
);
create policy "trip places owner delete" on public.trip_places
for delete to authenticated using (
    exists (
        select 1 from public.trips
        where trips.id = trip_id and trips.user_id = (select auth.uid())
    )
);

create policy "favorites owner read" on public.favorite_places
for select to authenticated using ((select auth.uid()) = user_id);
create policy "favorites owner insert" on public.favorite_places
for insert to authenticated with check ((select auth.uid()) = user_id);
create policy "favorites owner update" on public.favorite_places
for update to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy "favorites owner delete" on public.favorite_places
for delete to authenticated using ((select auth.uid()) = user_id);
