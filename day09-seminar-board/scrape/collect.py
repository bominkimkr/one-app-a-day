# -*- coding: utf-8 -*-
"""대치동 학원 설명회 공지 수집기.

각 학원 공식 사이트의 설명회/공지 게시판에서 제목·게시일·설명회 일시·원문 링크만
가져온다. 자료 전문(본문 텍스트/첨부/이미지)은 저장하지 않는다.

사용법:
    python collect.py                 # data.json 갱신
    python collect.py --dry-run       # 저장하지 않고 결과만 출력
    python collect.py --only mexx,snt # 일부 학원만
"""
import argparse
import json
import os
import re
import sys
import traceback
from datetime import date
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from classify import classify, target_label, looks_like_seminar  # noqa: E402
from dates import iso, now_kst_iso, parse_date, parse_time, today_kst  # noqa: E402

requests.packages.urllib3.disable_warnings()

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(HERE, "..", "data.json")
# file:// 로 index.html 을 바로 열었을 때 fetch 가 막히므로 같은 내용을 JS 로도 남긴다
DATA_JS_PATH = os.path.join(HERE, "..", "data.js")

# 지난 설명회는 이만큼까지만 남긴다 (게시판이 살아 있는지 보이되 목록이 묵지 않게)
MAX_PAST_DAYS = 180

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
TIMEOUT = 25

ACADEMIES = [
    {"key": "daechan", "name": "대찬학원",    "color": "#c2410c", "site": "https://www.daechanedu.com/"},
    {"key": "sejung",  "name": "세정학원",    "color": "#0e7490", "site": "https://sejungedu.com/"},
    {"key": "mexx",    "name": "MEXX",       "color": "#1d4ed8", "site": "https://mexx.megastudy.net/"},
    {"key": "sdij",    "name": "시대인재",    "color": "#7c3aed", "site": "https://www.sdij.com/aca/"},
    {"key": "yoon",    "name": "윤도영과학",  "color": "#15803d", "site": "https://yoondyedu.com/"},
    {"key": "dawon",   "name": "다원교육",    "color": "#b91c1c", "site": "http://dawonedu.com/"},
    {"key": "kns",     "name": "KNS",        "color": "#a16207", "site": "https://www.knsedu.co.kr/"},
    {"key": "snt",     "name": "SNT",        "color": "#be185d", "site": "https://www.sntedu.co.kr/"},
    {"key": "saeum",   "name": "새움학원",   "color": "#65a30d", "site": "https://saeumedu.com/"},
]

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": UA, "Accept-Language": "ko-KR,ko;q=0.9"})


# ── 공통 유틸 ──────────────────────────────────────────────────────────

def get(url, **kw):
    r = SESSION.get(url, timeout=TIMEOUT, verify=False, **kw)
    r.raise_for_status()
    return r


def soup_of(url, **kw):
    """meta charset 을 존중해서 파싱한다 (euc-kr 게시판이 아직 많다)."""
    r = get(url, **kw)
    head = r.content[:3000]
    m = re.search(rb"charset\s*=\s*[\"']?\s*([\w\-]+)", head, re.I)
    enc = (m.group(1).decode("ascii", "ignore") if m else None) or r.apparent_encoding or "utf-8"
    if enc.lower() in ("ks_c_5601-1987", "ksc5601", "euckr"):
        enc = "euc-kr"
    try:
        text = r.content.decode(enc, errors="replace")
    except LookupError:
        text = r.content.decode("utf-8", errors="replace")
    return BeautifulSoup(text, "html.parser"), r.url


def txt(node):
    if node is None:
        return ""
    return re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip()


# 설명회 게시판에 섞여 있는 안내/플레이스홀더 행 (설명회 글이 아님)
NOT_A_POST = re.compile(
    r"^(DB\s*등록|DB등록신청|문자수신|문자\s*DB|추후\s*(안내|공지)|준비\s*중|"
    r"미정|신청\s*조회|예약\s*조회|공지사항)\s*$", re.I)


def item(academy, uid, title, url, posted=None, event_date=None,
         event_time=None, event_text=None, place=None, hint=""):
    """수집 항목 하나를 표준 형태로 만든다. 본문 전문은 담지 않는다."""
    title = re.sub(r"\s+", " ", (title or "")).strip(" ■▶●·-")
    if not title or NOT_A_POST.match(title):
        return None
    levels, chips = classify(title, hint, place or "")
    return {
        "id": f"{academy['key']}:{uid}",
        "academy_key": academy["key"],
        "academy": academy["name"],
        "title": title,
        "url": url,
        "posted_at": posted,
        "event_date": event_date,
        "event_time": event_time,
        "event_text": event_text,
        "place": place or None,
        "levels": levels,
        "target": target_label(levels),
        "grades": chips,
    }


# ── 1. 대찬학원 ────────────────────────────────────────────────────────
# 학년별 설명회 탭이 menu_str 로 나뉜 서버 렌더링 테이블. 게시일은 없고 일정만 있다.

DAECHAN_TABS = [("0404", "고3"), ("0408", "고2"), ("0407", "고1"),
                ("0405", "중3"), ("0413", "예비중3")]


def fetch_daechan(aca):
    out = []
    for menu, label in DAECHAN_TABS:
        url = f"https://www.daechanedu.com/menu/?menu_str={menu}"
        sp, base = soup_of(url)
        table = sp.select_one("table.board_table2")
        if not table:
            continue
        for tr in table.select("tbody tr"):
            tds = tr.find_all("td")
            if len(tds) < 4:
                continue
            a = tds[1].find("a")
            if not a:
                continue
            title = txt(a)
            href = a.get("href") or ""
            wr = re.search(r"wr_id=(\d+)", href)
            if not wr or not title:
                continue
            when, place = txt(tds[2]), txt(tds[3])
            d = parse_date(when) or parse_date(title)
            out.append(item(aca, wr.group(1), title, urljoin(base, href),
                            event_date=iso(d), event_time=parse_time(when),
                            event_text=when or None, place=place, hint=label))
    return out


# ── 2. 세정학원 ────────────────────────────────────────────────────────
# 현장(중등) 설명회 + 학년별 온라인 설명회. 글마다 개별 URL이 없어 목록 URL을 링크한다.

SEJUNG_PAGES = [
    ("https://sejungedu.com/explain/presentationplan?co=중등", "중등", "현장"),
    ("https://sejungedu.com/explain/onlinepresentation?co=중3", "중3", "온라인"),
    ("https://sejungedu.com/explain/onlinepresentation?co=고1", "고1", "온라인"),
    ("https://sejungedu.com/explain/onlinepresentation?co=고2", "고2", "온라인"),
    ("https://sejungedu.com/explain/onlinepresentation?co=고3", "고3", "온라인"),
]


def fetch_sejung(aca):
    out, seen = [], set()
    for url, label, kind in SEJUNG_PAGES:
        sp, base = soup_of(url)
        for row in sp.select(".class-timetable-row"):
            title = txt(row.select_one(".col-title .txt")) or txt(row.select_one(".col-title"))
            if not title:
                continue
            when = txt(row.select_one(".col-date"))
            place = txt(row.select_one(".col-time"))
            btn = row.select_one("[data-id]")
            uid = (btn.get("data-id") if btn else None) or re.sub(r"\W+", "", title)[:24]
            uid = f"{label}-{uid}"
            if uid in seen:
                continue
            seen.add(uid)
            d = parse_date(when) or parse_date(title)
            out.append(item(aca, uid, title, base,
                            event_date=iso(d), event_time=parse_time(when),
                            event_text=when or None, place=place,
                            hint=f"{label} {kind} 설명회"))
    return out


# ── 3. MEXX ───────────────────────────────────────────────────────────
# 설명회 목록이 ajax 조각으로 오고, 그 안에 schema.org Event JSON-LD 가 함께 들어 있다.

def fetch_mexx(aca):
    url = "https://mexx.megastudy.net/campus_common/2026/fair/fair_list_ajax.asp"
    r = SESSION.get(url, params={"group": "", "grade": "", "campusCd": "",
                                 "searchCampusType": "", "isIntro": "N"},
                    headers={"Referer": "https://mexx.megastudy.net/campus_common/2026/fair/list.asp"},
                    timeout=TIMEOUT, verify=False)
    r.raise_for_status()
    html = r.content.decode(r.apparent_encoding or "euc-kr", errors="replace")
    sp = BeautifulSoup(html, "html.parser")

    events = {}
    for tag in sp.find_all("script", {"type": "application/ld+json"}):
        try:
            blob = json.loads(tag.string or "{}")
        except json.JSONDecodeError:
            continue
        for el in (blob.get("mainEntity") or {}).get("itemListElement", []) or []:
            ev = el.get("item") or {}
            if ev.get("url"):
                events[ev["url"].split("#")[0]] = ev

    out = []
    for card in sp.select("a.lecture-card"):
        href = card.get("href") or ""
        idx = re.search(r"idx=(\d+)", href)
        if not idx:
            continue
        title = txt(card.select_one(".card-mexx__title h5")) or txt(card.select_one("h5"))
        sub = txt(card.select_one(".card-mexx__title p"))
        tags = " ".join(txt(t) for t in card.select(".card-mexx__head .tag"))
        when = place = ""
        for li in card.select(".card-mexx__info li"):
            key, val = txt(li.find("strong")), txt(li.find("span"))
            if "일시" in key:
                when = val
            elif "장소" in key:
                place = val
        ev = events.get(href.split("#")[0], {})
        # MEXX 외 캠퍼스 일정이 섞여 오면 걸러낸다
        org = ((ev.get("organizer") or {}).get("name") or "") + " " + place
        if "MEXX" not in org.upper() and "멕스" not in org:
            continue
        start = ev.get("startDate") or ""
        d = parse_date(start[:10]) or parse_date(when)
        t = (start[11:16] if len(start) >= 16 else None) or parse_time(when)
        audience = ((ev.get("audience") or {}).get("audienceType") or "")
        out.append(item(aca, idx.group(1), title, urljoin("https://mexx.megastudy.net/", href),
                        event_date=iso(d), event_time=t, event_text=when or None,
                        place=place, hint=f"{tags} {audience} {sub}"))
    return out


# ── 4. 시대인재 ────────────────────────────────────────────────────────
# 대치캠퍼스(campus=101) 학년 탭별 서버 렌더링. 진행 중인 설명회가 없으면 비어 있다.

SDIJ_GRADES = [("A11003", "고3"), ("A11006", "고2"), ("A11008", "고1"),
               ("A11007", "예비고1"), ("A11001", "중2")]


def fetch_sdij(aca):
    out = []
    for code, label in SDIJ_GRADES:
        url = ("https://www.sdij.com/aca/briefing/default.asp"
               f"?page=1&campus=101&stuGrd={code}")
        sp, base = soup_of(url)
        wrap = sp.select_one(".exam-presentation-list-wrapper")
        if not wrap or wrap.select_one(".exam-presentation-empty"):
            continue
        for card in wrap.select("li, .exam-presentation-item, .briefing-item"):
            title = txt(card.find(["h3", "h4", "strong", "p"]))
            if not title or len(title) < 4:
                continue
            body = txt(card)
            d = parse_date(body)
            uid = None
            for attr in ("data-brfcd", "data-code", "data-id", "id"):
                if card.get(attr):
                    uid = card.get(attr)
                    break
            uid = f"{code}-{uid or re.sub(r'\W+', '', title)[:24]}"
            out.append(item(aca, uid, title, base, event_date=iso(d),
                            event_time=parse_time(body), place=None, hint=label))
    return out


# ── 5. 윤도영과학 ──────────────────────────────────────────────────────
# SPA + 공개 JSON API. 오프라인/라이브 설명회 두 종류.

def fetch_yoon(aca):
    out = []
    for path, kind in [("/api/briefing/list", "briefing_offline"),
                       ("/api/briefing_live/list", "briefing_live")]:
        r = SESSION.get("https://yoondyedu.com" + path,
                        headers={"Referer": "https://yoondyedu.com/",
                                 "Accept": "application/json"},
                        timeout=TIMEOUT, verify=False)
        r.raise_for_status()
        body = r.json()
        if str(body.get("result")) != "200":
            continue
        for b in body.get("message") or []:
            start = b.get("briefing_start_datetime") or ""
            d = parse_date(start[:10])
            out.append(item(
                aca, b.get("id"), b.get("title"),
                f"https://yoondyedu.com/#/{kind}/apply?id={b.get('id')}",
                event_date=iso(d),
                event_time=(start[11:16] or None) if len(start) >= 16 else None,
                event_text=start.replace("-", ".")[:16] or None,
                place="온라인 라이브" if kind == "briefing_live" else None,
                hint="윤도영 통합과학 " + (b.get("title") or "")))
    return out


# ── 6. 다원교육 ────────────────────────────────────────────────────────
# 학년별 설명회 탭 (진행중 + 지난). 지난 것도 최근 것은 참고용으로 받아둔다.

DAWON_TABS = [("http://dawonedu.com/high/seminar/PreM", "중3"),
              ("http://dawonedu.com/high/seminar/premiddle", "고1"),
              ("http://dawonedu.com/high/seminar/PreHighSchool", "고2"),
              ("http://dawonedu.com/high/seminar/PreHigh", "고3"),
              ("http://dawonedu.com/elemid/seminar/sem", "초중등")]


def fetch_dawon(aca):
    out, seen = [], set()
    for base_url, label in DAWON_TABS:
        for vtype in ("ing", "end"):
            url = f"{base_url}?vtype={vtype}&page=1"
            try:
                sp, base = soup_of(url)
            except requests.RequestException:
                continue
            for li in sp.select("ul.reserve > li"):
                head = li.select_one(".reserve_box .head h4") or li.select_one("h4.sub_title")
                title = txt(head)
                for badge in ("마감임박", "마감완료", "마감", "접수중", "예약중"):
                    if title.startswith(badge):
                        title = title[len(badge):].strip()
                if not title:
                    continue
                link = li.select_one('.reserve_box .head a[href*="mode=reservation"]')
                href = link.get("href") if link else url
                uid = re.search(r"[?&]id=(\d+)", href or "")
                uid = uid.group(1) if uid else re.sub(r"\W+", "", title)[:24]
                if uid in seen:
                    continue
                seen.add(uid)
                status = txt(li.select_one("h4.sub_title .desc"))
                # "지난 설명회" 탭이면 제목의 "11/14"는 작년일 수도 있다
                d = parse_date(title, prefer="past" if vtype == "end" else "future")
                out.append(item(aca, uid, title, urljoin(base, href),
                                event_date=iso(d), event_time=parse_time(title),
                                place=None, hint=f"{label} {status}"))
    return out


# ── 7. KNS ────────────────────────────────────────────────────────────
# 전용 설명회 게시판(sub3/50_2)은 2023년 이후 갱신이 없어서,
# 실제로 살아 있는 초/중/고등부 공지사항 게시판에서 설명회성 글만 골라 온다.

KNS_BOARDS = [  # 이 서브도메인들은 https 를 지원하지 않아 http 로 접근한다

    ("http://ele.knsedu.co.kr/ele/sub5/01.php", "초등부", "초등"),
    ("http://mid.knsedu.co.kr/mid/info/info_01.php", "중등부", "중등"),
    ("http://high.knsedu.co.kr/high/sub5/10.php", "고등부", "고등"),
]


def fetch_kns(aca):
    out = []
    for url, label, level_hint in KNS_BOARDS:
        sp, base = soup_of(url)
        table = sp.select_one("table.tbl_type04")
        if not table:
            continue
        for tr in table.select("tbody tr"):
            a = tr.select_one("td.td_left03 a")
            if not a:
                continue
            title = txt(a)
            if not looks_like_seminar(title):
                continue
            tds = tr.find_all("td")
            posted = None
            for td in tds:
                d = parse_date(txt(td))
                if d and re.search(r"20\d{2}", txt(td)):
                    posted = d
                    break
            href = a.get("href") or ""
            num = re.search(r"num=(\d+)", href)
            uid = f"{label}-{num.group(1) if num else re.sub(r'\W+', '', title)[:20]}"
            ev = parse_date(title)
            out.append(item(aca, uid, title, urljoin(base, href),
                            posted=iso(posted), event_date=iso(ev),
                            event_time=parse_time(title),
                            hint=f"{label} {level_hint}"))
    return out


# ── 8. SNT ────────────────────────────────────────────────────────────
# 설명회 목록에 대상(초등/중등/고등/국제학교)·일자·장소가 컬럼으로 들어 있다.

def fetch_snt(aca):
    sp, base = soup_of("https://www.sntedu.co.kr/presentation/newclass/")
    out, seen = [], set()
    for li in sp.select(".class_lst > ul > li"):
        row = li.select_one(".tr_line")
        if not row:
            continue
        tds = row.select(".td")
        if len(tds) < 4:
            continue
        audience = txt(tds[0])
        title = txt(tds[1].find("p")) or txt(tds[1])
        title = re.sub(r"\[상세보기\]\s*$", "", title).strip()
        when = txt(tds[2])
        place = txt(tds[3])
        if not title:
            continue
        uid = re.sub(r"\W+", "", f"{audience}{title}")[:32]
        if uid in seen:
            continue
        seen.add(uid)
        d = parse_date(when) or parse_date(title)
        out.append(item(aca, uid, title, base, event_date=iso(d),
                        event_time=parse_time(when), event_text=when or None,
                        place=place, hint=f"{audience} 대상"))
    return out


# ── 9. 새움학원 ────────────────────────────────────────────────────────
# 학년별 아코디언 게시판. 개별 글 링크는 없고, 날짜는 제목 안에 "`26.8.7)" 식으로 박혀 있다.

SAEUM_TABS = [("https://saeumedu.com/Seminar01", "고1"),
              ("https://saeumedu.com/Seminar02", "고2"),
              ("https://saeumedu.com/Seminar03", "고3"),
              ("https://saeumedu.com/Seminar04", "중등")]

SAEUM_DATE_RE = re.compile(r"[`'](\d{2})\.(\d{1,2})\.(\d{1,2})")


def _saeum_event_date(title):
    """제목 속 "`26.8.7" 같은 표기를 모두 뽑아, 오늘 이후 중 가장 가까운 날을 고른다
    (전부 지난 날짜면 그중 가장 최근 것)."""
    found = []
    for y, mo, da in SAEUM_DATE_RE.findall(title):
        try:
            found.append(date(2000 + int(y), int(mo), int(da)))
        except ValueError:
            continue
    if not found:
        return None
    today = today_kst()
    ahead = [d for d in found if d >= today]
    return min(ahead) if ahead else max(found)


def fetch_saeum(aca):
    out, seen = [], set()
    for url, label in SAEUM_TABS:
        sp, base = soup_of(url)
        for row in sp.select(".acd_row"):
            title = txt(row.select_one(".acd_title"))
            if not title:
                continue
            uid = re.sub(r"\W+", "", title)[:32]
            if uid in seen:
                continue
            seen.add(uid)
            d = _saeum_event_date(title)
            out.append(item(aca, uid, title, url,
                            event_date=iso(d), event_time=parse_time(title),
                            place=None, hint=label))
    return out


FETCHERS = {
    "daechan": fetch_daechan,
    "sejung": fetch_sejung,
    "mexx": fetch_mexx,
    "sdij": fetch_sdij,
    "yoon": fetch_yoon,
    "dawon": fetch_dawon,
    "kns": fetch_kns,
    "snt": fetch_snt,
    "saeum": fetch_saeum,
}


# ── 실행 ──────────────────────────────────────────────────────────────

def merge_duplicates(got):
    """같은 학원에서 같은 설명회가 여러 번 잡히면 하나로 합친다.

    SNT처럼 대상(초등/중등/고등)별로 같은 설명회를 여러 줄로 띄우는 게시판이 있어서,
    제목+일정이 같으면 한 카드로 묶고 대상 레벨만 합쳐 준다.
    """
    by_id, by_key, out = {}, {}, []
    for i in got:
        if i["id"] in by_id:
            continue
        by_id[i["id"]] = i
        key = (i["title"], i.get("event_date"), i.get("event_time"))
        first = by_key.get(key)
        if first is None:
            by_key[key] = i
            out.append(i)
            continue
        for lv in i["levels"]:
            if lv not in first["levels"]:
                first["levels"].append(lv)
        for g in i["grades"]:
            if g not in first["grades"]:
                first["grades"].append(g)
        first["levels"].sort(key=lambda x: ("초등", "중등", "고등").index(x))
        first["target"] = target_label(first["levels"])
    return out


def too_old(i):
    """설명회 일정이 한참 지난 글은 버린다 (일정이 없는 글은 남긴다)."""
    d = i.get("event_date")
    if not d:
        return False
    try:
        return (today_kst() - date.fromisoformat(d)).days > MAX_PAST_DAYS
    except ValueError:
        return False


def load_previous():
    try:
        with open(DATA_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"academies": [], "items": []}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", default="")
    args = ap.parse_args()

    only = {k.strip() for k in args.only.split(",") if k.strip()}
    prev = load_previous()
    prev_items = {i["id"]: i for i in prev.get("items", [])}
    prev_aca = {a["key"]: a for a in prev.get("academies", [])}

    today = today_kst().isoformat()
    now = now_kst_iso()

    items, statuses = [], []
    for aca in ACADEMIES:
        old = prev_aca.get(aca["key"], {})
        if only and aca["key"] not in only:
            # 이번 실행에서 건드리지 않는 학원은 이전 결과를 그대로 유지
            statuses.append({**aca, **{k: old.get(k) for k in
                                       ("status", "count", "error", "last_success_at",
                                        "first_success_at", "checked_at")}})
            items.extend(i for i in prev.get("items", []) if i["academy_key"] == aca["key"])
            continue

        st = {**aca, "checked_at": now,
              "last_success_at": old.get("last_success_at"),
              "first_success_at": old.get("first_success_at"),
              "status": "ok", "count": 0, "error": None}
        # 이 학원을 처음 수집하는 실행인가? 그렇다면 이번에 담기는 글들은
        # "오늘 올라온 글"이 아니라 "처음 훑어온 기존 글"이므로 NEW 를 붙이지 않는다.
        bootstrap = not old.get("first_success_at")
        try:
            got = merge_duplicates([i for i in FETCHERS[aca["key"]](aca)
                                    if i and not too_old(i)])

            for i in got:
                was = prev_items.get(i["id"]) or {}
                i["first_seen"] = was.get("first_seen") or today
                i["bootstrap"] = was.get("bootstrap", bootstrap)
                # 이번에 게시판에서 실제 등록일을 읽었는지가 기준이다.
                # (직전 실행에서 채워 둔 추정값을 보고 판단하면 안 된다)
                real_posted = i.get("posted_at")
                i["posted_is_estimated"] = not real_posted
                # 등록일이 없는 게시판은 글을 처음 발견한 날을 대신 쓴다
                i["posted_at"] = real_posted or was.get("posted_at") or i["first_seen"]
            items.extend(got)
            st["count"] = len(got)
            st["last_success_at"] = now
            st["first_success_at"] = st["first_success_at"] or now
            st["status"] = "ok" if got else "empty"
        except Exception as exc:  # noqa: BLE001 - 한 곳이 죽어도 나머지는 살린다
            st["status"] = "fail"
            st["error"] = f"{type(exc).__name__}: {exc}"[:300]
            kept = [i for i in prev.get("items", []) if i["academy_key"] == aca["key"]]
            items.extend(kept)
            st["count"] = len(kept)
            print(f"  !! {aca['name']} 실패: {st['error']}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
        statuses.append(st)
        print(f"  {aca['name']:8s} {st['status']:5s} {st['count']:3d}건")

    items.sort(key=lambda i: (i.get("posted_at") or "", i.get("event_date") or ""), reverse=True)

    data = {
        "generated_at": now,
        "source_note": "각 학원 공식 홈페이지의 설명회·공지 게시판에서 제목/일정/링크만 수집합니다. 자세한 내용은 원문 링크에서 확인하세요.",
        "academies": statuses,
        "items": items,
    }

    print(f"\n총 {len(items)}건 / 성공 {sum(1 for s in statuses if s['status'] == 'ok')}곳")
    if args.dry_run:
        print(json.dumps(data, ensure_ascii=False, indent=2)[:4000])
        return 0

    blob = json.dumps(data, ensure_ascii=False, indent=1)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        f.write(blob)
    with open(DATA_JS_PATH, "w", encoding="utf-8") as f:
        f.write("// collect.py 가 data.json 과 함께 자동 생성합니다. 직접 고치지 마세요." + chr(10))
        f.write("window.__SEMINAR_DATA__ = " + blob + ";" + chr(10))
    print(f"→ {os.path.normpath(DATA_PATH)}")
    print(f"→ {os.path.normpath(DATA_JS_PATH)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
