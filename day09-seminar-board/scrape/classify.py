# -*- coding: utf-8 -*-
"""제목/부가 텍스트에서 대상 학년을 추출해 초등/중등/고등으로 분류한다.

"예비고1" 같은 표현은 *현재* 학년 기준으로 본다 (예비고1 = 현 중3 → 중등).
아무 학년 신호도 없으면 levels 는 빈 리스트가 되고, 앱에서는 "전체"로 표시된다.
"""
import re

ELEM, MID, HIGH = "초등", "중등", "고등"
LEVEL_ORDER = {ELEM: 0, MID: 1, HIGH: 2}

# (정규식, 화면에 보여줄 학년칩 or None, 레벨)
# 순서가 중요하다. 매칭된 부분은 뒤 규칙이 다시 보지 못하도록 지워 나가므로
# "예비고1"이 "고1"보다, "초5~6"(범위)이 "초5"보다 먼저 처리돼야 한다.
RULES = [
    # ── 예비 표현: 현재 학년으로 환산 ────────────────────────────────
    (r"예비\s*중\s*1", "예비중1", ELEM),
    (r"예비\s*중\s*2", "예비중2", ELEM),
    (r"예비\s*중\s*3", "예비중3", MID),
    (r"예비\s*중등?", "예비중", ELEM),
    (r"예비\s*고\s*1", "예비고1", MID),
    (r"예비\s*고\s*2", "예비고2", HIGH),
    (r"예비\s*고\s*3", "예비고3", HIGH),
    (r"예비\s*고등?", "예비고1", MID),
    # ── 초등 ────────────────────────────────────────────────────────
    (r"초\s*([1-6])\s*학년", r"초\1", ELEM),
    (r"초\s*1(?![0-9])", "초1", ELEM),
    (r"초\s*2(?![0-9])", "초2", ELEM),
    (r"초\s*3(?![0-9])", "초3", ELEM),
    (r"초\s*4(?![0-9])", "초4", ELEM),
    (r"초\s*5(?![0-9])", "초5", ELEM),
    (r"초\s*6(?![0-9])", "초6", ELEM),
    (r"초등부|초등|초딩", "초등", ELEM),
    (r"\bG\s*[1-5]\b", "초등", ELEM),
    # ── 중등 ────────────────────────────────────────────────────────
    (r"중\s*([1-3])\s*학년", r"중\1", MID),
    (r"중\s*1(?![0-9])", "중1", MID),
    (r"중\s*2(?![0-9])", "중2", MID),
    (r"중\s*3(?![0-9])", "중3", MID),
    (r"중등부|중등|중학생|중학교", "중등", MID),
    (r"특목고|자사고|외고|과학고|영재학교|고교\s*선택", "고교선택", MID),
    # ── 고등 ────────────────────────────────────────────────────────
    (r"고\s*([1-3])\s*학년", r"고\1", HIGH),
    (r"고\s*1(?![0-9])", "고1", HIGH),
    (r"고\s*2(?![0-9])", "고2", HIGH),
    (r"고\s*3(?![0-9])", "고3", HIGH),
    (r"고등부|고등학생|고등학교|고등|고교생", "고등", HIGH),
    (r"N\s*수|재수|반수|졸업생|검정고시", "N수", HIGH),
    # 학년 칩으로 보여주진 않지만 고등 신호로는 쓰는 표현들
    (r"수능|수시|정시|모의고사|모평|학평|9평|6평|입시\s*전략|대입|의대\s*입시|논술", None, HIGH),
]

# "초5~6", "중1-3", "고1,2" 같은 범위 표현
RANGE_RE = re.compile(r"(초|중|고)\s*([1-6])\s*[~\-–ㆍ,/]\s*(?:(초|중|고)\s*)?([1-6])")
LEVEL_OF = {"초": ELEM, "중": MID, "고": HIGH}

# "2009년생 학생을 위한 …" — 대치동 설명회 제목에 꽤 자주 나오는 표기
BIRTH_RE = re.compile(r"(20[0-2]\d)\s*년\s*생")
_GRADE_BY_YEAR_INDEX = {1: "초1", 2: "초2", 3: "초3", 4: "초4", 5: "초5", 6: "초6",
                        7: "중1", 8: "중2", 9: "중3", 10: "고1", 11: "고2", 12: "고3"}


def grade_of_birth_year(birth_year, ref_year=None):
    """출생연도 → 현재 학년 라벨. 학령기를 벗어나면 None.

    한국 학제 기준으로 2009년생은 2016년에 초1이 되므로 (연도 - 출생연도 - 6) 이 학년 순번.
    """
    from datetime import date
    ref_year = ref_year or date.today().year
    return _GRADE_BY_YEAR_INDEX.get(ref_year - birth_year - 6)

# 일반 공지 게시판에서 "설명회성" 글만 골라낼 때 쓰는 키워드
SEMINAR_KEYWORDS = [
    "설명회", "간담회", "특강", "공개강좌", "공개특강", "입시전략", "입시 전략",
    "로드맵", "세미나", "브리핑", "학부모", "고교선택", "고교 선택", "진학전략",
]


def looks_like_seminar(text):
    """공지 게시판에서 설명회 관련 글만 걸러낼 때 사용."""
    return any(k in (text or "") for k in SEMINAR_KEYWORDS)


def classify(*texts):
    """여러 텍스트 조각을 합쳐 (levels, grade_chips) 를 돌려준다.

    levels: ["초등", "중등", "고등"] 의 부분집합. 빈 리스트면 '전체'.
    grade_chips: 화면에 그대로 보여줄 학년 라벨들 (예: ["예비고1", "중3"]).
    """
    blob = " ".join(t for t in texts if t)
    if not blob.strip():
        return [], []

    levels, chips, chip_level = [], [], {}

    def add(chip, level):
        if chip and chip not in chips:
            chips.append(chip)
            chip_level[chip] = level
        if level not in levels:
            levels.append(level)

    # 매칭된 표현은 지워 나가면서(consumed) 뒤 규칙의 오탐을 막는다.
    consumed = blob

    # 1) 범위 표현 먼저 (초5~6 → 초5, 초6)
    for m in list(RANGE_RE.finditer(consumed)):
        a, n1, b, n2 = m.group(1), int(m.group(2)), m.group(3), int(m.group(4))
        b = b or a
        if a == b and n1 <= n2:
            for n in range(n1, n2 + 1):
                add(f"{a}{n}", LEVEL_OF[a])
        else:
            add(f"{a}{n1}", LEVEL_OF[a])
            add(f"{b}{n2}", LEVEL_OF[b])
        consumed = consumed.replace(m.group(0), " ")

    # 2) "2009년생" 같은 출생연도 표기 → 현재 학년으로 환산
    for m in list(BIRTH_RE.finditer(consumed)):
        chip = grade_of_birth_year(int(m.group(1)))
        if chip:
            add(chip, LEVEL_OF[chip[0]])
            consumed = consumed.replace(m.group(0), " ")

    # 3) 나머지 규칙
    for pattern, chip, level in RULES:
        rx = re.compile(pattern)
        m = rx.search(consumed)
        while m:
            add(m.expand(chip) if chip else None, level)
            consumed = consumed[: m.start()] + " " + consumed[m.end():]
            m = rx.search(consumed)

    levels.sort(key=lambda x: LEVEL_ORDER[x])
    chips.sort(key=lambda c: (LEVEL_ORDER[chip_level[c]], c))
    return levels, chips[:3]


def target_label(levels):
    return "전체" if not levels or len(levels) == 3 else "·".join(levels)
