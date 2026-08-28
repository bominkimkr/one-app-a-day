# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

"원데이 원앱 챌린지" (One Day One App Challenge): a multi-participant, 30-day challenge where each participant builds and links one small app per day. 봄인's own apps live in this repo as `dayNN-<short-name>/` folders; other participants link to apps hosted wherever they like. There is no shared build system between apps — each stands alone.

The repo root is **also** the challenge gallery website (`index.html`), backed by Supabase (see "Gallery site" below) and published via GitHub Pages.

## Project rules

- Scope each day's app to something completable in a single day. Don't let one day's app grow into a multi-day effort.
- Default stack is a single HTML file with inline `<style>` and `<script>` — no build step, no dependencies. Reach for React (or another framework) only when an app's complexity genuinely doesn't fit that model.
- Definition of done: opening the day's `index.html` directly in a browser must work immediately, with no install or build step. If a day deviates from the single-file default (e.g. uses React), its own README must document how to run it.
- Once a day's app is complete, register it in the gallery via the site itself (see below) and commit the app's folder with git.

## Running an app

Open the relevant day's `index.html` directly in a browser — e.g. on Windows: `start dayNN-<name>/index.html`. No dev server is needed for the default single-file stack.

## Structure

- `dayNN-<short-name>/` — one directory per day of 봄인's own apps, each with at minimum an `index.html` and a short `README.md`.
- `day01-reading-calendar/` — reading calendar: search a book title (Google Books API) to auto-fill its cover/author/pages, log a daily quote on the calendar, mark books finished with reflections, and earn monthly/yearly badges.
- `index.html` — the gallery site: participant list, per-participant app gallery, join form, upload-app form, and lightweight admin hide controls. All data comes from Supabase, not from local files.

## Gallery site

- Hosted via GitHub Pages from the `main` branch root. Pushing to `main` is enough to update the live site — no build step.
- Backed by the Supabase project **insta-challenge** (project ref `yapenvwinwwqjmrysxiu`), tables prefixed `gallery_` (`gallery_participants`, `gallery_apps`, `gallery_admin`, plus `gallery_participants_public` / `gallery_apps_public` views and `gallery_join` / `gallery_add_app` / `gallery_admin_set_hidden` RPC functions). The same Supabase project also hosts the separate `day03-insta-challenge` app's own tables — don't cross-reference or rename either app's tables without checking both.
- The publishable (anon-equivalent) Supabase key is embedded directly in `index.html` — this is expected and safe for this key type (RLS + SECURITY DEFINER functions are what actually enforce access, not key secrecy).
- Participants join and upload their own apps directly from the site (no JSON file to hand-edit). A 4-digit PIN set at signup gates who can add apps under a given participant.
- Hiding an inappropriate participant/app requires the separate admin PIN (stored hashed in `gallery_admin`) via the 🚫 button on any card.

### 매일 새 앱 추가하는 순서 (daily checklist, for 봄인's own apps)

1. `dayNN-<short-name>/` 폴더를 만들고 그 안에 `index.html`(단일 파일 기본 스택)과 `README.md`를 작성한다.
2. 앱을 브라우저에서 열어 직접 동작을 확인한다.
3. 커밋 + push해서 GitHub Pages에 올린다 (앱 주소는 `https://bominkimkr.github.io/one-app-a-day/dayNN-short-name/index.html` 형태가 된다).
4. 배포된 사이트의 "내 앱 올리기"에서 봄인 비밀번호로 로그인해 Day 번호, 앱 이름, 위 주소, 3줄 설명을 등록한다.

## Git

- This is a git repository with a GitHub remote (`origin`) hosted via GitHub Pages on `main`.
- Commit each day's app folder once finished, then push to publish. The gallery's participant/app data itself lives in Supabase, not in git.
