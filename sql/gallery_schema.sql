-- 원데이 원앱 챌린지 갤러리 스키마 (Supabase project: insta-challenge, ref yapenvwinwwqjmrysxiu)
-- 이미 이 프로젝트에 적용되어 있습니다. 참고/재구성용으로 보관합니다.
-- anon(publishable) key만으로 안전하게 쓰도록 설계: 테이블 직접 접근은 막고,
-- 공개 조회는 view로, 쓰기는 SECURITY DEFINER 함수(PIN 검증)로만 허용합니다.

create extension if not exists pgcrypto;

create table if not exists gallery_participants (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  instagram text,
  pin_hash text not null,
  start_date date not null default current_date,
  hidden boolean not null default false,
  created_at timestamptz not null default now()
);

create table if not exists gallery_apps (
  id uuid primary key default gen_random_uuid(),
  participant_id uuid not null references gallery_participants(id) on delete cascade,
  day_number int not null check (day_number > 0),
  name text not null,
  url text not null,
  description text not null,
  hidden boolean not null default false,
  created_at timestamptz not null default now()
);

create table if not exists gallery_admin (
  id smallint primary key default 1,
  pin_hash text not null,
  constraint gallery_admin_single_row check (id = 1)
);

alter table gallery_participants enable row level security;
alter table gallery_apps enable row level security;
alter table gallery_admin enable row level security;

revoke all on gallery_participants from anon, authenticated;
revoke all on gallery_apps from anon, authenticated;
revoke all on gallery_admin from anon, authenticated;

create or replace view gallery_participants_public as
  select id, name, instagram, start_date, created_at
  from gallery_participants
  where hidden = false;

create or replace view gallery_apps_public as
  select id, participant_id, day_number, name, url, description, created_at
  from gallery_apps
  where hidden = false;

grant select on gallery_participants_public to anon, authenticated;
grant select on gallery_apps_public to anon, authenticated;

create or replace function gallery_join(p_name text, p_instagram text, p_pin text, p_start_date date default current_date)
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
  if p_pin !~ '^[0-9]{4}$' then
    raise exception '비밀번호는 4자리 숫자여야 해요';
  end if;
  insert into gallery_participants (name, instagram, pin_hash, start_date)
  values (trim(p_name), nullif(trim(coalesce(p_instagram, '')), ''), crypt(p_pin, gen_salt('bf')), coalesce(p_start_date, current_date))
  returning id into v_id;
  return v_id;
end;
$$;

create or replace function gallery_add_app(p_participant_id uuid, p_pin text, p_day_number int, p_name text, p_url text, p_description text)
returns uuid
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
  v_hash text;
  v_id uuid;
begin
  select pin_hash into v_hash from gallery_participants where id = p_participant_id;
  if v_hash is null then
    raise exception '참가자를 찾을 수 없어요';
  end if;
  if crypt(p_pin, v_hash) <> v_hash then
    raise exception '비밀번호가 올바르지 않아요';
  end if;
  if p_name is null or length(trim(p_name)) = 0 then
    raise exception '앱 이름을 입력해주세요';
  end if;
  if p_url is null or length(trim(p_url)) = 0 then
    raise exception '앱 주소를 입력해주세요';
  end if;
  insert into gallery_apps (participant_id, day_number, name, url, description)
  values (p_participant_id, p_day_number, trim(p_name), trim(p_url), coalesce(p_description, ''))
  returning id into v_id;
  return v_id;
end;
$$;

create or replace function gallery_admin_set_hidden(p_admin_pin text, p_target_table text, p_target_id uuid, p_hidden boolean default true)
returns void
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
  v_hash text;
begin
  select pin_hash into v_hash from gallery_admin where id = 1;
  if v_hash is null or crypt(p_admin_pin, v_hash) <> v_hash then
    raise exception '관리자 비밀번호가 올바르지 않아요';
  end if;
  if p_target_table = 'participant' then
    update gallery_participants set hidden = p_hidden where id = p_target_id;
  elsif p_target_table = 'app' then
    update gallery_apps set hidden = p_hidden where id = p_target_id;
  else
    raise exception 'invalid target table: %', p_target_table;
  end if;
end;
$$;

grant execute on function gallery_join(text, text, text, date) to anon, authenticated;
grant execute on function gallery_add_app(uuid, text, int, text, text, text) to anon, authenticated;
grant execute on function gallery_admin_set_hidden(text, text, uuid, boolean) to anon, authenticated;

-- 관리자 비밀번호 시드 (이미 적용됨 — 바꾸려면 아래를 새 비밀번호로 다시 실행)
-- insert into gallery_admin (id, pin_hash) values (1, crypt('새_관리자_비밀번호', gen_salt('bf')))
-- on conflict (id) do update set pin_hash = excluded.pin_hash;

-- 봄인 초기 데이터 시드 (이미 적용됨, 참고용)
-- insert into gallery_participants (name, instagram, pin_hash, start_date)
-- select '봄인', 'bom_in_kr', crypt('봄인_비밀번호', gen_salt('bf')), date '2026-08-28'
-- where not exists (select 1 from gallery_participants where name = '봄인' and instagram = 'bom_in_kr');
