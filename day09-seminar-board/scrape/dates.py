# -*- coding: utf-8 -*-
"""학원 게시판에 흩어져 있는 온갖 날짜 표기를 ISO 날짜(YYYY-MM-DD)로 정규화한다."""
import re
from datetime import date, datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))


def today_kst():
    return datetime.now(KST).date()


def now_kst_iso():
    return datetime.now(KST).replace(microsecond=0).isoformat()


# 2026-09-22 / 2026.09.22 / 2026/9/22 / 2026년 9월 22일
FULL_RE = re.compile(r"(20\d{2})\s*[.\-/년]\s*(\d{1,2})\s*[.\-/월]\s*(\d{1,2})\s*일?")
# 9/22, 9월 22일, 09.22  (연도 없음)
SHORT_RE = re.compile(r"(?<!\d)(\d{1,2})\s*[./월]\s*(\d{1,2})\s*일?(?!\d)")
# 오후 2시 / PM 7:30 / 14시 00분 / 19:00
TIME_RE = re.compile(
    r"(오전|오후|AM|PM|A|P)?\s*(\d{1,2})\s*(?::|시)\s*(\d{2})?\s*분?", re.I
)


def _mk(y, m, d):
    try:
        return date(y, m, d)
    except ValueError:
        return None


def parse_date(text, ref=None, prefer=None):
    """텍스트에서 첫 번째 날짜를 뽑아 date 로 돌려준다. 없으면 None.

    연도가 없는 "9/22" 같은 표기는 기준일(ref, 기본 오늘)에서 가장 가까운 연도로 채운다.
    prefer="future" 면 지난 날짜로 해석되는 후보를 뒤로 미루고,
    prefer="past" 면 앞날로 해석되는 후보를 앞당긴다.
    (게시판이 "진행중/지난" 탭으로 나뉘어 있을 때 연도를 제대로 찍기 위한 힌트)
    """
    if not text:
        return None
    ref = ref or today_kst()

    m = FULL_RE.search(text)
    if m:
        return _mk(int(m.group(1)), int(m.group(2)), int(m.group(3)))

    m = SHORT_RE.search(text)
    if not m:
        return None
    mm, dd = int(m.group(1)), int(m.group(2))
    if not (1 <= mm <= 12 and 1 <= dd <= 31):
        return None

    cands = [d for d in (_mk(y, mm, dd) for y in (ref.year - 1, ref.year, ref.year + 1)) if d]
    if not cands:
        return None
    if prefer == "future":
        ahead = [d for d in cands if d >= ref]
        if ahead:
            return min(ahead)
    elif prefer == "past":
        behind = [d for d in cands if d <= ref]
        if behind:
            return max(behind)
    return min(cands, key=lambda d: abs((d - ref).days))


def parse_time(text):
    """'오후 2시', 'PM 7:30', '14시 00분' → '14:00'. 없으면 None."""
    if not text:
        return None
    # 날짜의 월/일 숫자를 시간으로 오인하지 않도록 날짜 표기를 먼저 지운다
    cleaned = FULL_RE.sub(" ", text)
    cleaned = re.sub(r"(?<!\d)\d{1,2}\s*[./]\s*\d{1,2}\s*(?:\([월화수목금토일]\))?", " ", cleaned)
    cleaned = re.sub(r"\d{1,2}\s*월\s*\d{1,2}\s*일", " ", cleaned)

    m = TIME_RE.search(cleaned)
    if not m:
        return None
    ampm, hh, mi = m.group(1), int(m.group(2)), int(m.group(3) or 0)
    if hh > 23 or mi > 59:
        return None
    if ampm and ampm.upper() in ("오후", "PM", "P") and hh < 12:
        hh += 12
    if ampm and ampm.upper() in ("오전", "AM", "A") and hh == 12:
        hh = 0
    return f"{hh:02d}:{mi:02d}"


def iso(d):
    return d.isoformat() if d else None
