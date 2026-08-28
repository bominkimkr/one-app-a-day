# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A "one app a day" challenge: each day is a small, self-contained app in its own `dayNN-<short-name>/` directory. There is no shared build system, package manager, or code between days — every day's app stands alone.

The repo root is **also** a gallery website (`index.html` + `apps.json`) that lists every day's app as a card and is published via GitHub Pages. See "Gallery site" below.

## Project rules

- Scope each day's app to something completable in a single day. Don't let one day's app grow into a multi-day effort.
- Default stack is a single HTML file with inline `<style>` and `<script>` — no build step, no dependencies. Reach for React (or another framework) only when an app's complexity genuinely doesn't fit that model.
- Definition of done: opening the day's `index.html` directly in a browser must work immediately, with no install or build step. If a day deviates from the single-file default (e.g. uses React), its own README must document how to run it.
- Once a day's app is complete, add it to the gallery (see below) and commit it with git.

## Running an app

Open the relevant day's `index.html` directly in a browser — e.g. on Windows: `start dayNN-<name>/index.html`. No dev server is needed for the default single-file stack.

## Structure

- `dayNN-<short-name>/` — one directory per day, each with at minimum an `index.html` and a short `README.md` describing what the app does.
- `day01-reading-calendar/` — reading calendar: search a book title (Google Books API) to auto-fill its cover/author/pages, log a daily quote on the calendar, mark books finished with reflections, and earn monthly/yearly badges.
- `index.html` — gallery homepage (root of the site), renders cards from `apps.json`.
- `apps.json` — the list of apps shown in the gallery.

## Gallery site

- Hosted via GitHub Pages from the `main` branch root. Pushing to `main` is enough to update the live site — no build step.
- The homepage (`index.html`) fetches `apps.json` at load time and renders one card per entry, newest `day` first.
- `apps.json` note: it's fetched with `fetch()`, which browsers block on `file://`. To preview the gallery locally, serve the folder over HTTP (e.g. `python -m http.server`) rather than double-clicking `index.html`. Each day's own app still must open directly via `file://` per the rule above — only the gallery root needs a server for local preview.

### 매일 새 앱 추가하는 순서 (daily checklist)

1. `dayNN-<short-name>/` 폴더를 만들고 그 안에 `index.html`(단일 파일 기본 스택)과 `README.md`를 작성한다.
2. 앱을 브라우저에서 열어 직접 동작을 확인한다.
3. 카드에 쓸 스크린샷을 찍어 `dayNN-<short-name>/screenshot.png`로 저장한다 (선택 사항: 없으면 카드에 앱 이름 플레이스홀더가 표시됨).
4. 루트의 `apps.json`에 새 항목을 추가한다 (배열 맨 앞이든 뒤든 순서는 상관없음 — 화면에서는 `day` 값 기준 내림차순으로 자동 정렬됨):
   ```json
   {
     "day": NN,
     "name": "앱 이름",
     "folder": "dayNN-short-name",
     "screenshot": "dayNN-short-name/screenshot.png",
     "description": ["설명 1줄", "설명 2줄", "설명 3줄"],
     "date": "YYYY-MM-DD"
   }
   ```
5. 로컬에서 `python -m http.server`로 갤러리를 열어 새 카드가 잘 보이는지 확인한다 (`file://`로 직접 열면 `apps.json`을 못 읽으니 주의).
6. 새 폴더와 `apps.json` 변경사항을 커밋하고 `main`에 푸시한다 — 푸시하면 GitHub Pages에 자동 반영된다.

## Git

- This is a git repository with a GitHub remote (`origin`) hosted via GitHub Pages on `main`.
- Commit each day's app (and its `apps.json` entry) once finished, then push to publish.
