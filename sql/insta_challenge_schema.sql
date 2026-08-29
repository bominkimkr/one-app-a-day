-- 인스타그램 30일 챌린지 스키마 (Supabase project: insta-challenge, ref yapenvwinwwqjmrysxiu)
-- 이미 이 프로젝트에 적용되어 있습니다. 참고/재구성용으로 보관합니다.
-- anon(publishable) key만으로 안전하게 쓰도록 설계: 테이블 직접 접근은 막고,
-- 공개 조회는 view로, 쓰기는 SECURITY DEFINER 함수(PIN 검증)로만 허용합니다.
-- gallery_* 테이블과는 별개이며 서로 참조하지 않습니다.

create table if not exists insta_participants (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  instagram text not null,
  pin_hash text not null,
  start_date date not null default current_date,
  completed_at timestamptz,
  hidden boolean not null default false,
  created_at timestamptz not null default now()
);
create unique index if not exists insta_participants_instagram_key on insta_participants (lower(instagram));

create table if not exists insta_posts (
  id uuid primary key default gen_random_uuid(),
  participant_id uuid not null references insta_participants(id) on delete cascade,
  post_date date not null,
  url text not null,
  post_type text not null check (post_type in ('reel', 'post')),
  hidden boolean not null default false,
  created_at timestamptz not null default now(),
  unique (participant_id, post_date)
);

create table if not exists insta_admin (
  id smallint primary key default 1,
  pin_hash text not null,
  constraint insta_admin_single_row check (id = 1)
);

alter table insta_participants enable row level security;
alter table insta_posts enable row level security;
alter table insta_admin enable row level security;

revoke all on insta_participants from anon, authenticated;
revoke all on insta_posts from anon, authenticated;
revoke all on insta_admin from anon, authenticated;

create or replace view insta_participants_public as
  select id, name, instagram, start_date, completed_at, created_at
  from insta_participants
  where hidden = false;

create or replace view insta_posts_public as
  select id, participant_id, post_date, url, post_type, created_at
  from insta_posts
  where hidden = false;

grant select on insta_participants_public to anon, authenticated;
grant select on insta_posts_public to anon, authenticated;

create or replace function insta_join(p_name text, p_instagram text, p_pin text, p_start_date date default current_date)
returns uuid
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
  v_id uuid;
begin
  if p_name is null or length(trim(p_name)) = 0 then
    raise exception '이름을 입력해주세요';
  end if;
  if p_instagram is null or length(trim(p_instagram)) = 0 then
    raise exception '인스타그램 아이디를 입력해주세요';
  end if;
  if p_pin !~ '^[0-9]{4}$' then
    raise exception '비밀번호는 4자리 숫자여야 해요';
  end if;
  if exists (select 1 from insta_participants where lower(instagram) = lower(trim(p_instagram))) then
    raise exception '이미 등록된 인스타그램 아이디예요';
  end if;
  insert into insta_participants (name, instagram, pin_hash, start_date)
  values (trim(p_name), trim(p_instagram), crypt(p_pin, gen_salt('bf')), coalesce(p_start_date, current_date))
  returning id into v_id;
  return v_id;
end;
$$;

create or replace function insta_add_post(p_participant_id uuid, p_pin text, p_post_date date, p_url text)
returns jsonb
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
  v_hash text;
  v_completed_at timestamptz;
  v_post_type text;
  v_post_id uuid;
  v_distinct_days int;
  v_just_completed boolean := false;
begin
  select pin_hash, completed_at into v_hash, v_completed_at from insta_participants where id = p_participant_id;
  if v_hash is null then
    raise exception '참가자를 찾을 수 없어요';
  end if;
  if crypt(p_pin, v_hash) <> v_hash then
    raise exception '비밀번호가 올바르지 않아요';
  end if;
  if p_url ~* 'instagram\.com/stories/' then
    raise exception '스토리는 기록할 수 없어요. 릴스나 게시글 링크를 넣어주세요.';
  end if;
  if p_url ~* 'instagram\.com/(?:[^/?#]+/)?reels?/[A-Za-z0-9_-]+' then
    v_post_type := 'reel';
  elsif p_url ~* 'instagram\.com/(?:[^/?#]+/)?p/[A-Za-z0-9_-]+' then
    v_post_type := 'post';
  else
    raise exception '인스타그램 게시글/릴스 주소가 맞는지 확인해주세요.';
  end if;

  insert into insta_posts (participant_id, post_date, url, post_type)
  values (p_participant_id, p_post_date, trim(p_url), v_post_type)
  on conflict (participant_id, post_date)
  do update set url = excluded.url, post_type = excluded.post_type
  returning id into v_post_id;

  select count(distinct post_date) into v_distinct_days
  from insta_posts where participant_id = p_participant_id and hidden = false;

  if v_completed_at is null and v_distinct_days >= 30 then
    update insta_participants set completed_at = now() where id = p_participant_id;
    v_just_completed := true;
  end if;

  return jsonb_build_object(
    'id', v_post_id,
    'post_type', v_post_type,
    'distinct_days', v_distinct_days,
    'just_completed', v_just_completed
  );
end;
$$;

create or replace function insta_admin_set_hidden(p_admin_pin text, p_target_table text, p_target_id uuid, p_hidden boolean default true)
returns void
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
  v_hash text;
begin
  select pin_hash into v_hash from insta_admin where id = 1;
  if v_hash is null or crypt(p_admin_pin, v_hash) <> v_hash then
    raise exception '관리자 비밀번호가 올바르지 않아요';
  end if;
  if p_target_table = 'participant' then
    update insta_participants set hidden = p_hidden where id = p_target_id;
  elsif p_target_table = 'post' then
    update insta_posts set hidden = p_hidden where id = p_target_id;
  else
    raise exception 'invalid target table: %', p_target_table;
  end if;
end;
$$;

grant execute on function insta_join(text, text, text, date) to anon, authenticated;
grant execute on function insta_add_post(uuid, text, date, text) to anon, authenticated;
grant execute on function insta_admin_set_hidden(text, text, uuid, boolean) to anon, authenticated;

-- 관리자 비밀번호 시드 (이미 적용됨 — 바꾸려면 아래를 새 비밀번호로 다시 실행)
-- insert into insta_admin (id, pin_hash) values (1, crypt('새_관리자_비밀번호', gen_salt('bf')))
-- on conflict (id) do update set pin_hash = excluded.pin_hash;
