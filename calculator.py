from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal
from itertools import combinations
from typing import Iterable


RATES = {
    "Đề": Decimal("90"),
    "Càng": Decimal("400"),
    "Bao": Decimal("3.5"),
    "Xiên 2": Decimal("15"),
    "Xiên 3": Decimal("48"),
    "Xiên 4": Decimal("180"),
}

AP_CANG_RATE = Decimal("10")


def _two_digits(values: Iterable[int]) -> list[str]:
    return [f"{value:02d}" for value in values]


EVEN_ODD = [f"{a}{b}" for a in range(0, 10, 2) for b in range(1, 10, 2)]
ODD_EVEN = [f"{a}{b}" for a in range(1, 10, 2) for b in range(0, 10, 2)]
ODD_ODD = [f"{a}{b}" for a in range(1, 10, 2) for b in range(1, 10, 2)]
EVEN_EVEN = [f"{a}{b}" for a in range(0, 10, 2) for b in range(0, 10, 2)]
SUM_GROUPS = {
    digit: [f"{a}{b}" for a in range(10) for b in range(10) if (a + b) % 10 == digit]
    for digit in range(10)
}

DAN_36 = [f"{a}{b}" for a in range(3, 9) for b in range(3, 9)]
DAN_56 = [
    "12", "13", "14", "15", "16", "17", "18", "21", "23", "24", "25", "26", "27", "28",
    "31", "32", "34", "35", "36", "37", "38", "41", "42", "43", "45", "46", "47", "48",
    "51", "52", "53", "54", "56", "57", "58", "61", "62", "63", "64", "65", "67", "68",
    "71", "72", "73", "74", "75", "76", "78", "81", "82", "83", "84", "85", "86", "87",
]
DAN_44 = [
    "00", "01", "02", "03", "04", "05", "06", "07", "08", "09", "19", "29", "39", "49", "59",
    "69", "79", "89", "99", "98", "97", "96", "95", "94", "93", "92", "91", "90", "80", "70",
    "60", "50", "40", "30", "20", "10", "11", "22", "33", "44", "55", "66", "77", "88",
]
DAN_49 = [f"{a}{b}" for a in range(2, 9) for b in range(2, 9)]
DAN_SUM_UNDER_10 = [f"{a}{b}" for a in range(10) for b in range(10) if a + b < 10]
DAN_SUM_OVER_10 = [f"{a}{b}" for a in range(10) for b in range(10) if a + b > 10]
DAN_HEAD_HIGH = [f"{a}{b}" for a in range(5, 10) for b in range(10)]
DAN_HEAD_LOW = [f"{a}{b}" for a in range(5) for b in range(10)]
DAN_TAIL_HIGH = [f"{a}{b}" for a in range(10) for b in range(5, 10)]
DAN_TAIL_LOW = [f"{a}{b}" for a in range(10) for b in range(5)]
DAN_HEAD_EVEN = [f"{a}{b}" for a in range(0, 10, 2) for b in range(10)]
DAN_HEAD_ODD = [f"{a}{b}" for a in range(1, 10, 2) for b in range(10)]
DAN_TAIL_EVEN = [f"{a}{b}" for a in range(10) for b in range(0, 10, 2)]
DAN_TAIL_ODD = [f"{a}{b}" for a in range(10) for b in range(1, 10, 2)]
DAN_LOW_LOW = [f"{a}{b}" for a in range(5) for b in range(5)]
DAN_HIGH_LOW = [f"{a}{b}" for a in range(5, 10) for b in range(5)]
DAN_LOW_HIGH = [f"{a}{b}" for a in range(5) for b in range(5, 10)]
DAN_HIGH_HIGH = [f"{a}{b}" for a in range(5, 10) for b in range(5, 10)]
DAN_SUM_HIGH = "05 50 14 41 23 32 69 96 78 87 06 60 15 51 24 42 33 79 97 88 07 70 16 61 25 52 34 43 89 98 08 80 17 71 26 62 35 53 44 99 09 90 18 81 27 72 36 63 45 54".split()
DAN_SUM_LOW = "00 19 91 28 82 37 73 46 64 55 01 10 29 92 38 83 47 74 56 65 02 20 11 39 93 48 84 57 75 66 03 30 12 21 49 94 58 85 67 76 04 40 13 31 22 59 95 68 86 77".split()
DAN_KEP_LECH = "05 50 16 61 27 72 38 83 49 94".split()


def _build_de_bo(code: str) -> tuple[str, ...]:
    """Sinh đúng dàn bộ từ hai chữ số và giữ thứ tự nguồn đã chốt."""
    first, second = int(code[0]), int(code[1])
    first_plus_five = (first + 5) % 10
    second_plus_five = (second + 5) % 10
    values = (
        f"{first}{second}", f"{second}{first}",
        f"{first}{second_plus_five}", f"{second_plus_five}{first}",
        f"{first_plus_five}{second}", f"{second}{first_plus_five}",
        f"{first_plus_five}{second_plus_five}", f"{second_plus_five}{first_plus_five}",
    )
    return tuple(dict.fromkeys(values))


DE_BO = {f"{value:02d}": _build_de_bo(f"{value:02d}") for value in range(100)}


def ascii_text(text: str) -> str:
    text = text.replace("đ", "d").replace("Đ", "D")
    text = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn")


def normalize(text: str) -> str:
    s = ascii_text(text).lower().replace("**", "")
    s = s.translate(str.maketrans({
        "（": "(", "）": ")", "［": "[", "］": "]",
        "，": ",", "．": ".", "：": ":", "＝": "=",
    }))
    replacements = (
        # Giữ “dưới” trong “tổng dưới 10”; không được đổi nhầm thành “đít”.
        (r"\btong\s+duoi\b", "tong_duoi"),
        (r"\bd\b|\bd[ea]\b|\bdee?\b|\bdeh\b", "de"),
        (r"\bdauu?\b|\bdou\b", "dau"),
        (r"\bdit+\b|\bduoi\b", "dit"),
        (r"\bxieng?\b|\bxienn\b", "xien"),
        (r"\b(?:xien\s*)?(?:x\s*)?(?:quay|vong)\s*2\b|\b(?:xq|xv|xvg)\s*2\b", "xq2"),
        (r"\bx(?:quay|vong|vg)\s*2\b", "xq2"),
        (r"\b(?:xien\s*)?(?:x\s*)?(?:quay|vong)\b|\b(?:xq|xv|xvg)\b", "xq"),
        (r"\bx(?:quay|vong|vg)\b", "xq"),
        (r"\blo\b", "bao"),
        (r"\b(?:ba\s*cang|bacang|cag)(?=\s*\d)", "cang "),
        (r"\bcang(?=\d)", "cang "),
        (r"nghin|ngan", "k"),
        (r"trieu", "tr"),
    )
    for pattern, value in replacements:
        s = re.sub(pattern, value, s, flags=re.I)
    # Các cách viết dính thường gặp trong tin đại lý.
    s = re.sub(r"(?im)(^|[\n,;])\s*de(?=(?:dau|dit|duoi|tong|dan|chap|kep|cham|\d))", r"\1de ", s)
    s = re.sub(r"\bdau(?=\d)", "dau ", s)
    s = re.sub(r"\bdit(?=\d)", "dit ", s)
    s = re.sub(r"\bduoi(?=\d)", "dit ", s)
    s = re.sub(r"\bmoiso\b", "moi so", s)
    s = re.sub(r"\bmoicon\b", "moi con", s)
    # Chỉ tên dàn Chập/Kép dùng dấu hai chấm như dấu ghi giá.
    s = re.sub(r"\b(chap|kep)\s*:\s*(?=\d)", r"\1 = ", s)
    # Sau một tên dàn kết thúc bằng chữ, “x 10k” là dấu ghi giá chứ không
    # phải loại Xiên. “X 00 11=10k” ở đầu vẫn giữ nguyên là Xiên.
    s = re.sub(r"(?<=[a-z])[ \t]+x[ \t]*(?=\d)", " = ", s)
    # B chỉ là Bao khi đứng đầu một dòng cược và dòng đó còn có dấu ghi giá.
    # Dòng giá riêng như "b175k" dưới tiêu đề Bao vẫn giữ nghĩa là "=175k".
    s = re.sub(
        r"(?im)^([ \t]*)b(?=[ \t]*\d{1,2}(?!\d)[^\n]*(?:=|[xb×])[ \t]*\d)",
        r"\1bao ",
        s,
    )
    s = re.sub(r"(?im)^([ \t]*)b[ \t]*:(?=[ \t]*(?:\n|$))", r"\1bao:", s)
    s = re.sub(r"\bdau\s*dit\b", "dau dit", s)
    s = re.sub(r"\bdau(?=dit)", "dau ", s)
    # “5x10”, “5 b 10” và “5×10” là “5 = 10k”. Đổi trước khi
    # tách loại vé để nhiều khoản viết liền trên một dòng vẫn được giữ đủ.
    s = re.sub(
        r"(?<=\d)[ \t]*[xb×][ \t]*(?=\d)",
        " = ",
        s,
    )
    s = re.sub(
        r"\b(mc(?:ap)?|moi\s*cap|moi\s*so)\b[ \t]*[xb×][ \t]*(?=\d)",
        r"\1 = ",
        s,
    )
    s = re.sub(r"[ \t]+", " ", s)
    return s.strip()


def parse_money(raw: str) -> Decimal:
    s = normalize(raw).replace(" ", "")
    joined_million = re.fullmatch(r"(\d+)(?:tr|m)(\d+)", s)
    if joined_million:
        return Decimal(joined_million.group(1)) * 1000 + Decimal(joined_million.group(2))
    multiplier = Decimal("1")
    if s.endswith("tr") or s.endswith("m"):
        multiplier = Decimal("1000")
        s = re.sub(r"(?:tr|m)$", "", s)
    else:
        s = re.sub(r"[kn]$", "", s)
    # Dấu chấm giữa các nhóm ba chữ số là phân cách hàng nghìn:
    # 10.000 = 10.000k, không phải 10k.
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", s):
        s = s.replace(".", "")
    else:
        # Giữ dấu phẩy thập phân cho các dạng như 1,5tr.
        s = s.replace(",", ".")
    try:
        return Decimal(s) * multiplier
    except Exception:
        return Decimal("0")


@dataclass(frozen=True)
class Entry:
    kind: str
    numbers: tuple[str, ...]
    unit_stake: Decimal
    ticket_count: int = 1
    source: str = ""
    # Mỗi tuple con là một vé Xiên thật. Trường này giữ ranh giới giữa
    # (07.71) và (07.64), tránh sinh tổ hợp chéo khi dò thưởng.
    ticket_groups: tuple[tuple[str, ...], ...] = ()

    @property
    def stake(self) -> Decimal:
        return self.unit_stake * self.ticket_count

    @property
    def reward(self) -> Decimal:
        # Một dàn có nhiều vé nhưng chỉ lấy giá của mỗi vé nhân tỷ lệ thưởng.
        # Ví dụ tổng chẵn 50 số, mỗi số 50k: vốn 2.500k nhưng thưởng 50×90.
        return self.unit_stake * RATES[self.kind]


@dataclass
class Calculation:
    entries: list[Entry]
    rejected: list[str]

    def totals(self) -> dict[str, tuple[Decimal, Decimal, int, Decimal]]:
        result: dict[str, tuple[Decimal, Decimal, int, Decimal]] = {}
        for kind in RATES:
            selected = [entry for entry in self.entries if entry.kind == kind]
            if selected:
                result[kind] = (
                    sum((entry.stake for entry in selected), Decimal("0")),
                    sum((entry.reward for entry in selected), Decimal("0")),
                    sum(entry.ticket_count for entry in selected),
                    sum((entry.unit_stake for entry in selected), Decimal("0")),
                )
        return result


@dataclass(frozen=True)
class CorrectionSuggestion:
    corrected: str
    display: str
    old_word: str
    new_word: str


@dataclass(frozen=True)
class BChoiceSuggestion:
    bao_corrected: str
    bo_corrected: str
    bao_display: str
    bo_display: str


CATEGORY_RE = re.compile(
    r"(?<!\w)(de|bao|cang|c(?=\s|:|\d)|xq2|xq|xien(?:\s*[234](?!\d))?|x\s*[234](?=\s|[:=(\[])|x(?=\s|[:=(\[]))",
    re.I,
)
# Tiền không có đơn vị chỉ nhận số nguyên. Dấu phẩy/chấm thập phân chỉ
# nhận với triệu (1,5tr); nhờ vậy “=100.20=300” là hai khoản riêng.
MONEY_TOKEN = (
    r"(?:\d{1,3}(?:\.\d{3})+\s*[kn]?|"
    r"\d+(?:[.,]\d+)?\s*(?:tr|m)(?:\s*\d+)?|"
    r"\d+\s*[kn]?)"
)
PER_UNIT_SUFFIX = (
    r"(?:\s*(?:/\s*)?(?:(?:1\s*/?\s*)?(?:so|con)|moi\s*(?:so|con)|m[sc]))?"
)
DEDUPE_WORDS = (
    r"(?:bo\s+(?:so\s+)?trung(?:\s+nhau)?|"
    r"khong\s+trung(?:\s+nhau)?|"
    r"(?:ko|k)\s+trung(?:\s+nhau)?|"
    r"loc\s+trung|loai\s+trung|tru\s+trung)"
)
DEDUPE_RE = re.compile(rf"[\(\[]?\s*{DEDUPE_WORDS}\s*[\)\]]?", re.I)
DEDUPE_AFTER_WORDS = rf"(?:{DEDUPE_WORDS}|trung(?:\s+nhau)?)"
SLASH_MONEY_MARKER = r"/(?=\s*\d+(?:[.,]\d+)?\s*(?:k|n|tr|m)\b)"
MONEY_RE = re.compile(
    rf"(?:(?:\b(?:mc(?:ap)?|ms|moi\s*cap|moi\s*so|moi\s*con)\b)\s*(?:=|[bx×])?|"
    rf"(?:=|[b×]|{SLASH_MONEY_MARKER}|x(?!\s*[234](?:\s|[:(\[]))))"
    rf"\s*(?P<amount>{MONEY_TOKEN}){PER_UNIT_SUFFIX}(?![a-z0-9])"
    rf"(?P<dedupe_after>\s*[\(\[]?\s*{DEDUPE_AFTER_WORDS}\s*[\)\]]?)?",
    re.I,
)


def _dedupe(numbers: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(numbers))


def _looks_like_named_de_component(text: str) -> bool:
    """Chỉ tách dấu phẩy khi mỗi vế thật sự là một dàn có tên.

    Nhờ đó “Bộ 00,05” và “Đề đảo 01,88” vẫn giữ chung ngữ cảnh,
    còn “tổng trên 10, đầu 1” được cộng thành hai dàn riêng.
    """
    compact = re.sub(r"[^a-z0-9]", "", text)
    if compact.startswith(("tong", "dau", "dit", "dan", "chap", "kep")):
        return True
    return compact in {
        "chanle", "lechan", "lele", "chanchan",
        "thapthap", "caothap", "thapcao", "caocao",
    }


DE_EXCLUSION_RE = re.compile(
    r"\b(?:bo|loai|tru|khong\s+lay)\s+"
    r"(?P<position>dau|dit)\s*:?\s*"
    r"(?P<digits>[0-9](?:[\s,./-]*[0-9])*)",
    re.I,
)


def _extract_de_exclusions(text: str) -> tuple[str, set[str], set[str]]:
    """Tách lệnh bỏ đầu/đít khỏi nội dung Đề và giữ phần cược còn lại."""
    excluded_heads: set[str] = set()
    excluded_tails: set[str] = set()

    def remove_command(match: re.Match[str]) -> str:
        target = excluded_heads if match.group("position") == "dau" else excluded_tails
        target.update(re.findall(r"\d", match.group("digits")))
        return " "

    cleaned = DE_EXCLUSION_RE.sub(remove_command, text)
    if excluded_heads or excluded_tails:
        # Dọn dấu ngoặc/chữ “và” còn thừa sau khi lấy lệnh loại trừ.
        cleaned = re.sub(r"\(\s*(?:va\s*)?\)", " ", cleaned)
        cleaned = re.sub(r"\bva\b(?=\s*(?:[),.;]|$))", " ", cleaned)
        cleaned = re.sub(r"[ \t]+", " ", cleaned).strip()
    return cleaned, excluded_heads, excluded_tails


def _format_de_exclusions(heads: set[str], tails: set[str]) -> str:
    parts: list[str] = []
    if heads:
        parts.append(f"bo dau {''.join(sorted(heads))}")
    if tails:
        parts.append(f"bo dit {''.join(sorted(tails))}")
    return " va ".join(parts)


def _parse_de_numbers_base(body: str) -> tuple[list[str], str | None]:
    s = normalize(body)
    s = re.sub(r"\b(dau|dit|tong|dan|chap|kep|bo)(?=\d)", r"\1 ", s)
    s = re.sub(r"\bdau(?=dit)", "dau ", s)
    s = re.sub(r"\bduoi(?=(?:cao|to|thap|be|nho|chan|le)\b)", "dit ", s)
    s = re.sub(r"\b(dau|dit)(?=(?:cao|to|thap|be|nho|chan|le)\b)", r"\1 ", s)

    # Ghép phải được xử lý trước các dàn đầu/đít độc lập.
    # Giữ từng lần xuất hiện của chữ số trong danh sách ghi trực tiếp.
    digit_groups = {
        "chan": "02468", "le": "13579",
        "cao": "56789", "lon": "56789", "to": "56789",
        "thap": "01234", "be": "01234", "nho": "01234",
    }
    operand = r"(?:[0-9][0-9,./:;\- ]*|chan|le|cao|lon|to|thap|be|nho)"
    join = re.fullmatch(
        rf"(?:dan\s*)?(dau|dit)\s*[:.]*\s*({operand})\s*ghep\s*(dau|dit)\s*[:.]*\s*({operand})", s
    )
    if join and join.group(1) != join.group(3):
        left = join.group(2).strip()
        right = join.group(4).strip()
        left_digits = digit_groups[left] if left in digit_groups else re.findall(r"\d", left)
        right_digits = digit_groups[right] if right in digit_groups else re.findall(r"\d", right)
        return [a + b if join.group(1) == "dau" else b + a
                for a in left_digits for b in right_digits], None

    # Nhiều dàn có tên dùng chung một giá: giữ từng dàn và nối toàn bộ vé,
    # kể cả số giao nhau. Không tách các dấu phẩy chỉ dùng để liệt kê số.
    named_parts = [part.strip() for part in re.split(r"\s*(?:[,;]+|\bva\b)\s*", s) if part.strip()]
    if len(named_parts) > 1 and all(_looks_like_named_de_component(part) for part in named_parts):
        combined: list[str] = []
        for part in named_parts:
            numbers, error = parse_de_numbers_detailed(part)
            if error:
                return [], error
            if not numbers:
                return [], f"không nhận diện được dàn: {part}"
            combined.extend(numbers)
        return combined, None

    compact = re.sub(r"[^a-z0-9]", "", s)

    named_compact = compact[3:] if compact.startswith("dan") else compact
    high_low_sets = {
        "thapthap": DAN_LOW_LOW,
        "caothap": DAN_HIGH_LOW,
        "thapcao": DAN_LOW_HIGH,
        "caocao": DAN_HIGH_HIGH,
    }
    if named_compact in high_low_sets:
        return high_low_sets[named_compact][:], None

    if named_compact in ("tongcao", "tonglon", "tongto"):
        return DAN_SUM_HIGH[:], None
    if named_compact in ("tongthap", "tongbe", "tongnho"):
        return DAN_SUM_LOW[:], None
    if named_compact == "keplech":
        return DAN_KEP_LECH[:], None
    if "tongduoi10" in compact or "tongnhohon10" in compact:
        return DAN_SUM_UNDER_10[:], None
    if "tongtren10" in compact or "tonglonhon10" in compact:
        return DAN_SUM_OVER_10[:], None
    multi_dan = re.fullmatch(r"dan\s*(36|44|49|56)(?:\s*[,;./:-]\s*|\s+)(36|44|49|56)", s)
    if multi_dan:
        mapping = {"36": DAN_36, "44": DAN_44, "49": DAN_49, "56": DAN_56}
        return mapping[multi_dan.group(1)][:] + mapping[multi_dan.group(2)][:], None
    if "dan44" in compact:
        return DAN_44[:], None
    if "dan48" in compact:
        return [], "Dàn 48 không được hỗ trợ"
    if "dan49" in compact:
        return DAN_49[:], None
    if "dan36" in compact:
        return DAN_36[:], None
    if "dan56" in compact:
        return DAN_56[:], None

    if re.search(r"(?:dan\s*)?(?:chan\s*le|cl)(?:\b|$)", s):
        return EVEN_ODD[:], None
    if re.search(r"(?:dan\s*)?(?:le\s*chan|lc)(?:\b|$)", s):
        return ODD_EVEN[:], None
    if re.search(r"(?:dan\s*)?(?:le\s*le|ll)(?:\b|$)", s):
        return ODD_ODD[:], None
    if re.search(r"(?:dan\s*)?(?:chan\s*chan|cc)(?:\b|$)", s):
        return EVEN_EVEN[:], None
    if re.search(r"tong\s*chan", s):
        return _dedupe(n for digit in (0, 2, 4, 6, 8) for n in SUM_GROUPS[digit]), None
    if re.search(r"tong\s*le", s):
        return _dedupe(n for digit in (1, 3, 5, 7, 9) for n in SUM_GROUPS[digit]), None
    if re.search(r"\bdau\s*(?:cao|to)\b", s):
        return DAN_HEAD_HIGH[:], None
    if re.search(r"\bdau\s*(?:thap|be|nho)\b", s):
        return DAN_HEAD_LOW[:], None
    if re.search(r"\bdit\s*(?:cao|to)\b", s):
        return DAN_TAIL_HIGH[:], None
    if re.search(r"\bdit\s*(?:thap|be|nho)\b", s):
        return DAN_TAIL_LOW[:], None
    if re.search(r"\bdau\s*chan\b", s):
        return DAN_HEAD_EVEN[:], None
    if re.search(r"\bdau\s*le\b", s):
        return DAN_HEAD_ODD[:], None
    if re.search(r"\bdit\s*chan\b", s):
        return DAN_TAIL_EVEN[:], None
    if re.search(r"\bdit\s*le\b", s):
        return DAN_TAIL_ODD[:], None

    result: list[str] = []

    bo_error: str | None = None
    s = re.sub(r"(?<=\d)\s+va\s+(?=\d)", ",", s)
    bo_pattern = re.compile(r"\bbo\s*:?\s*([0-9][0-9,./\- ]*)")

    def expand_de_bo(match: re.Match[str]) -> str:
        nonlocal bo_error
        codes = re.findall(r"\d+", match.group(1))
        if not codes or any(len(code) != 2 for code in codes):
            bo_error = "Đề bộ phải ghi đúng hai chữ số từ 00 đến 99"
            return " "
        for code in codes:
            result.extend(DE_BO[code])
        return " "

    s = bo_pattern.sub(expand_de_bo, s)
    if bo_error:
        return [], bo_error
    if re.search(r"\bbo\b", s):
        return [], "Đề bộ phải ghi đúng hai chữ số từ 00 đến 99"
    # “đầu đít 2” là hai dàn riêng: 10 số đầu 2 + 10 số đít 2.
    # Con 22 thuộc cả hai dàn và phải được tính hai vé, đúng cách ghi tiền.
    combined_pattern = re.compile(r"\bdau\s*(?:\+\s*)?dit\s*[:.]*\s*([0-9][0-9,./:;\- ]*)")

    def expand_combined(match: re.Match[str]) -> str:
        for digit in re.findall(r"\d", match.group(1)):
            result.extend(f"{digit}{b}" for b in range(10))
            result.extend(f"{a}{digit}" for a in range(10))
        return " "

    s = combined_pattern.sub(expand_combined, s)

    touch_pattern = re.compile(r"\bcham\s*[:.]*\s*([0-9][0-9,./:;\- ]*)")

    def expand_touch(match: re.Match[str]) -> str:
        for digit in re.findall(r"\d", match.group(1)):
            # Mỗi chạm có 19 số; số kép chỉ xuất hiện một lần trong chạm đó.
            result.extend(f"{a}{b}" for a in range(10) for b in range(10)
                          if str(a) == digit or str(b) == digit)
        return " "

    s = touch_pattern.sub(expand_touch, s)

    def expand_total(match: re.Match[str]) -> str:
        for digit in re.findall(r"\d", match.group(1)):
            result.extend(SUM_GROUPS[int(digit)])
        return " "

    def expand_head(match: re.Match[str]) -> str:
        for digit in re.findall(r"\d", match.group(1)):
            result.extend(f"{digit}{b}" for b in range(10))
        return " "

    def expand_tail(match: re.Match[str]) -> str:
        for digit in re.findall(r"\d", match.group(1)):
            result.extend(f"{a}{digit}" for a in range(10))
        return " "

    s = re.sub(r"\btong\s*[:.]*\s*([0-9][0-9,./:;\- ]*)", expand_total, s)
    s = re.sub(r"\bdau\s*[:.]*\s*([0-9][0-9,./:;\- ]*)", expand_head, s)
    s = re.sub(r"\bdit\s*[:.]*\s*([0-9][0-9,./:;\- ]*)", expand_tail, s)

    if re.search(r"\b(?:chap|kep)\b", s):
        result.extend(f"{n}{n}" for n in range(10))
        s = re.sub(r"\b(?:chap|kep)\b", " ", s)

    reverse_mode = bool(re.search(r"\b(?:dao|cap)\b", s))
    s = re.sub(r"\b(?:dao|cap)\b", " ", s)
    tokens = re.findall(r"(?<!\d)\d+(?!\d)", s)
    for token in tokens:
        if len(token) <= 2:
            number = f"{int(token):02d}"
            result.append(number)
            if reverse_mode:
                result.append(number[::-1])
        elif len(token) == 3:
            # Cặp viết gọn ABC là hai cặp liền nhau AB và BC:
            # 010 → 01,10; 924 → 92,24; 999 → 99,99.
            result.extend((token[:2], token[1:]))
        else:
            return [], f"chuỗi số {token} không rõ; hãy ghi Đề đảo/Đề cặp nếu muốn tách dạng ABC thành AB và BC"

    # Source Đề gốc giữ nguyên mọi vé, kể cả các số giao nhau hoặc lặp lại.
    return result, None


def parse_de_numbers_detailed(body: str) -> tuple[list[str], str | None]:
    s = normalize(body)
    cleaned, excluded_heads, excluded_tails = _extract_de_exclusions(s)
    numbers, error = _parse_de_numbers_base(cleaned)
    if error or not (excluded_heads or excluded_tails):
        return numbers, error

    filtered = [
        number for number in numbers
        if number[0] not in excluded_heads and number[1] not in excluded_tails
    ]
    if numbers and not filtered:
        return [], "lệnh bỏ đầu/đít đã loại hết toàn bộ dàn Đề"
    return filtered, None


def parse_de_numbers(body: str) -> list[str]:
    numbers, _ = parse_de_numbers_detailed(body)
    return numbers


def parse_regular_numbers(body: str) -> list[str]:
    s = normalize(body)
    s = re.sub(r"\b(?:bao|xq2?|xien\s*[234]?|x\s*[234]?)\b", " ", s)
    return [f"{int(n):02d}" for n in re.findall(r"(?<!\d)\d{1,2}(?!\d)", s)]


def parse_cang_numbers(body: str) -> tuple[list[str], str | None]:
    """Càng giữ đủ ba chữ số, kể cả số 0 ở đầu."""
    s = normalize(body)
    s = re.sub(r"\b(?:cang|c)(?=\s*\d)", " ", s)
    numbers = re.findall(r"(?<!\d)\d{3}(?!\d)", s)
    remainder = re.sub(r"(?<!\d)\d{3}(?!\d)", " ", s)
    remainder = re.sub(r"\bva\b", " ", remainder)
    remainder = remainder.strip(" \n\r\t,;:./-")
    if remainder or not numbers:
        return [], "Càng phải ghi đúng ba chữ số cho mỗi vé"
    return numbers, None


GROUP_RE = re.compile(r"[\(\[]([^\)\]]+)[\)\]]")


def _clean_ticket_body(body: str) -> str:
    s = normalize(body)
    s = re.sub(r"/?\s*1\s*(?:so|cap)\b", " ", s)
    s = re.sub(r"\b(?:moi\s*so|moi\s*cap|mc(?:ap)?)\b", " ", s)
    return s.strip(" \n\r\t,;:.-")


def parse_xien_groups(body: str) -> tuple[list[tuple[str, ...]], str | None]:
    """Đọc Xiên thường; mỗi ngoặc là một vé và không sinh tổ hợp."""
    s = _clean_ticket_body(body)
    matches = list(GROUP_RE.finditer(s))
    if matches:
        outside = GROUP_RE.sub(" ", s)
        if parse_regular_numbers(outside):
            return [], "có số nằm ngoài nhóm ngoặc"
        groups: list[tuple[str, ...]] = []
        for match in matches:
            numbers = tuple(parse_regular_numbers(match.group(1)))
            if len(numbers) not in (2, 3, 4):
                return [], f"một nhóm ngoặc có {len(numbers)} số; Xiên thường chỉ nhận 2–4 số"
            if len(set(numbers)) != len(numbers):
                return [], "một vé Xiên có số bị lặp"
            groups.append(numbers)
        return groups, None

    numbers = tuple(parse_regular_numbers(s))
    if len(numbers) not in (2, 3, 4):
        return [], f"có {len(numbers)} số; Xiên thường chỉ nhận 2–4 số"
    if len(set(numbers)) != len(numbers):
        return [], "một vé Xiên có số bị lặp"
    return [numbers], None


def parse_quay_sets(body: str) -> tuple[list[tuple[str, ...]], str | None]:
    """Đọc từng dàn Xiên quây; tổ hợp chỉ được sinh từ các dàn này."""
    s = _clean_ticket_body(body)
    matches = list(GROUP_RE.finditer(s))
    if matches:
        outside = GROUP_RE.sub(" ", s)
        if parse_regular_numbers(outside):
            return [], "có số nằm ngoài nhóm ngoặc"
        sets = [tuple(parse_regular_numbers(match.group(1))) for match in matches]
    else:
        sets = [tuple(parse_regular_numbers(s))]
    if not sets or any(len(numbers) < 2 for numbers in sets):
        return [], "Xiên quây cần ít nhất 2 số"
    for numbers in sets:
        if len(set(numbers)) != len(numbers):
            return [], "dàn Xiên quây có số bị lặp"
    return sets, None


def _kind(label: str, number_count: int) -> str | None:
    compact = re.sub(r"\s+", "", normalize(label))
    if compact == "de":
        return "Đề"
    if compact == "bao":
        return "Bao"
    if compact in {"c", "cang"}:
        return "Càng"
    if compact in {"xq", "xq2"}:
        return compact
    # Với Xiên thường, số lượng con quyết định loại vé. Nhờ đó
    # “Xiên 2 07.71.64” vẫn được sửa logic thành một vé Xiên 3.
    if re.fullmatch(r"(?:x|xien)[234]?", compact) and number_count in (2, 3, 4):
        return f"Xiên {number_count}"
    return None


def _category_segments(text: str) -> list[tuple[str, str]]:
    matches = list(CATEGORY_RE.finditer(text))
    if not matches:
        return [("de", text)]
    result: list[tuple[str, str]] = []
    prefix = text[:matches[0].start()].strip()
    if prefix and MONEY_RE.search(prefix):
        result.append(("de", prefix))
    result.extend([
        (match.group(1), text[match.end(): matches[i + 1].start() if i + 1 < len(matches) else len(text)])
        for i, match in enumerate(matches)
    ])
    return result


def _prepare_lines(text: str) -> str:
    """Gom tiêu đề và các dòng tiếp theo thành những vé logic.

    Tiêu đề đứng riêng (Bao:, Xiên 2:, Đề:) được giữ hiệu lực cho các dòng
    phía sau. Nếu nhiều dòng số Xiên dùng chung một dòng giá cuối, mỗi dòng số
    trở thành một nhóm ngoặc độc lập. Ngoài khối tiêu đề, dòng không ghi loại
    vẫn mặc định là Đề như quy tắc người dùng đã chốt.
    """
    output: list[str] = []
    active_header: str | None = None
    pending: list[str] = []

    def is_price_only(line: str) -> bool:
        match = MONEY_RE.search(line)
        if not match:
            return False
        remainder = (line[:match.start()] + line[match.end():])
        remainder = _clean_ticket_body(remainder)
        return not parse_regular_numbers(remainder)

    def build(header: str, bodies: list[str], price_line: str) -> str:
        compact = re.sub(r"\s+", "", normalize(header))
        ordinary_xien = bool(re.fullmatch(r"(?:x|xien)[234]?", compact))
        if ordinary_xien and len(bodies) > 1 and is_price_only(price_line):
            grouped = " ".join(
                body if GROUP_RE.search(body) else f"({body})"
                for body in bodies
            )
            return f"{header} {grouped} {price_line}"
        return f"{header} {' '.join(bodies + [price_line])}".strip()

    def flush_pending() -> None:
        nonlocal pending
        if pending:
            output.append(f"{active_header or 'de'} {' '.join(pending)}")
            pending = []

    def is_de_output(ticket: str) -> bool:
        match = CATEGORY_RE.search(ticket)
        return bool(match and re.sub(r"\s+", "", normalize(match.group(1))) == "de")

    def insert_exclusion_before_price(ticket: str, exclusion: str) -> str:
        matches = list(MONEY_RE.finditer(ticket))
        if not matches:
            return f"{ticket} {exclusion}".strip()
        price = matches[-1]
        return f"{ticket[:price.start()].rstrip()} {exclusion} {ticket[price.start():].lstrip()}"

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        # Dòng gạch chỉ dùng để chia các khoản, không phải nội dung vé.
        if re.fullmatch(r"(?:[-‐‑‒–—―_=~.]\s*){3,}", line):
            continue
        exclusion_cleaned, excluded_heads, excluded_tails = _extract_de_exclusions(line)
        exclusion = _format_de_exclusions(excluded_heads, excluded_tails)
        exclusion_only = bool(exclusion) and not exclusion_cleaned.strip(" \n\r\t,;:.-()")
        if exclusion_only:
            if pending:
                pending.append(exclusion)
            elif output and is_de_output(output[-1]):
                output[-1] = insert_exclusion_before_price(output[-1], exclusion)
            else:
                pending.append(exclusion)
            continue

        # Nếu điều kiện nằm sau giá trên cùng một dòng, chuyển nó vào thân vé
        # để parser áp dụng cho đúng khoản tiền vừa ghi.
        if exclusion:
            line = insert_exclusion_before_price(exclusion_cleaned, exclusion)
        # Dòng giá riêng “x 100” dưới một tiêu đề không phải nhãn Xiên.
        if active_header and re.fullmatch(rf"[xb×]\s*{MONEY_TOKEN}", line, re.I):
            line = re.sub(r"^[xb×]", "=", line, count=1, flags=re.I)
        categories = list(CATEGORY_RE.finditer(line))
        has_money = bool(MONEY_RE.search(line))
        if categories:
            remainder = CATEGORY_RE.sub("", line).strip(" \t:;,.—-")
            only_label = len(categories) == 1 and not has_money and not remainder
            if only_label:
                flush_pending()
                active_header = categories[0].group(1)
                continue
            if len(categories) == 1 and not has_money and remainder:
                flush_pending()
                active_header = categories[0].group(1)
                pending = [remainder]
                continue
            flush_pending()
            active_header = None
            output.append(line)
            continue

        if has_money:
            if active_header:
                if pending:
                    output.append(build(active_header, pending, line))
                    pending = []
                else:
                    output.append(f"{active_header} {line}")
            elif pending:
                output.append(build("de", pending, line))
                pending = []
            else:
                output.append(f"de {line}")
        else:
            pending.append(line)

    flush_pending()
    return "\n".join(output)


def calculate(raw: str) -> Calculation:
    text = _prepare_lines(normalize(raw))
    entries: list[Entry] = []
    rejected: list[str] = []
    segments = _category_segments(text)
    if not segments:
        return Calculation([], [raw.strip()] if raw.strip() else [])

    for label, segment in segments:
        money_matches = list(MONEY_RE.finditer(segment))
        if not money_matches:
            # Nhãn đứng riêng như “Đề:” chỉ là tiêu đề, không phải dữ liệu lỗi.
            if not segment.strip(" \n\r\t,;:.-"):
                continue
            rejected.append(f"{label} {segment}".strip())
            continue
        start = 0
        for money_match in money_matches:
            body = _clean_ticket_body(segment[start:money_match.start()])
            start = money_match.end()
            dedupe_requested = bool(money_match.group("dedupe_after")) or bool(DEDUPE_RE.search(body))
            body = DEDUPE_RE.sub(" ", body).strip(" \t,;:.")
            if not body:
                rejected.append(f"{label} (thiếu số/dàn) = {money_match.group('amount')}")
                continue
            stake = parse_money(money_match.group("amount"))
            label_norm = re.sub(r"\s+", "", normalize(label))
            if stake <= 0:
                rejected.append(f"{label} {body} = {money_match.group('amount')} (giá không hợp lệ)")
                continue

            if label_norm in {"xq", "xq2"}:
                quay_sets, error = parse_quay_sets(body)
                if error:
                    rejected.append(f"{label} {body} = {money_match.group('amount')} ({error})")
                    continue
                levels = (2,) if label_norm == "xq2" else (2, 3, 4)
                for number_set in quay_sets:
                    for level in levels:
                        groups = tuple(combinations(number_set, level)) if len(number_set) >= level else ()
                        if groups:
                            entries.append(Entry(
                                f"Xiên {level}", number_set, stake, len(groups),
                                f"{label} {body}".strip(), groups,
                            ))
                continue

            if re.fullmatch(r"(?:x|xien)[234]?", label_norm):
                groups, error = parse_xien_groups(body)
                if error:
                    rejected.append(f"{label} {body} = {money_match.group('amount')} ({error})")
                    continue
                for group in groups:
                    kind = f"Xiên {len(group)}"
                    entries.append(Entry(kind, group, stake, 1, f"{label} {'-'.join(group)}".strip(), (group,)))
                continue

            if label_norm in {"c", "cang"}:
                numbers, cang_error = parse_cang_numbers(body)
                if cang_error:
                    rejected.append(f"{label} {body} = {money_match.group('amount')} ({cang_error})")
                    continue
                entries.append(Entry("Càng", tuple(numbers), stake, len(numbers), f"cang {body}".strip()))
                continue

            if label_norm == "de":
                numbers, de_error = parse_de_numbers_detailed(body)
                if de_error:
                    rejected.append(f"{label} {body} = {money_match.group('amount')} ({de_error})")
                    continue
            else:
                numbers = parse_regular_numbers(body)
            if label_norm == "de" and dedupe_requested:
                numbers = _dedupe(numbers)
            kind = _kind(label, len(numbers))
            if not kind or not numbers:
                rejected.append(f"{label} {body} = {money_match.group('amount')} (không nhận diện được số hoặc loại vé)")
                continue
            if kind in {"Đề", "Bao"}:
                count = len(numbers)
            entries.append(Entry(kind, tuple(numbers), stake, count, f"{label} {body}".strip()))

    return Calculation(entries, rejected)


CORRECTION_WORDS = {
    "de": "Đề",
    "dau": "Đầu",
    "dit": "Đít",
    "bao": "Bao",
    "bo": "Bộ",
    "cang": "Càng",
    "xien": "Xiên",
    "tong": "Tổng",
    "dan": "Dàn",
    "chap": "Chập",
    "kep": "Kép",
    "ghep": "ghép",
    "quay": "quây",
    "vong": "vòng",
    "trieu": "triệu",
    "nghin": "nghìn",
}

# Những từ/biến thể hợp lệ phải đi thẳng vào parser, không được bộ sửa lỗi
# “đoán” thành từ khác chỉ vì khoảng cách chính tả gần (chan → chap, dao → dau...).
VALID_INPUT_WORDS = set(CORRECTION_WORDS) | {
    "c", "x", "xq", "xq2", "xv", "xvg",
    "ba", "bacang", "cag", "dao", "cap",
    "chan", "le", "cao", "to", "thap", "be", "nho",
    "duoi", "va", "moi", "so", "con", "mc", "ms", "mcap", "hon", "tren",
    "cham", "trung", "khong", "ko", "k", "loc", "loai", "tru", "nhau",
}


def _edit_distance(left: str, right: str) -> int:
    previous = list(range(len(right) + 1))
    for i, left_char in enumerate(left, 1):
        current = [i]
        for j, right_char in enumerate(right, 1):
            current.append(min(
                current[-1] + 1,
                previous[j] + 1,
                previous[j - 1] + (left_char != right_char),
            ))
        previous = current
    return previous[-1]


def _suggestion_display(text: str) -> str:
    # Tiền trần sau dấu “=” dùng đơn vị k; thêm k để câu hỏi xác nhận rõ ràng.
    display = re.sub(r"(?<=\d)\s*[xb×]\s*(?=\d)", " = ", text, flags=re.I)
    display = re.sub(r"\s*=\s*", " = ", display)
    display = re.sub(r"\b(Bao|Bộ)(?=\d)", r"\1 ", display, flags=re.I)
    money_pattern = re.compile(
        r"=\s*(\d+(?:[.,]\d+)*)"
        r"(\s*(?:(?:triệu|trieu|nghìn|nghin|tr|m|k|n)\s*\d*))?"
        r"(?![a-z0-9])",
        re.I,
    )

    def format_money(match: re.Match[str]) -> str:
        unit = (match.group(2) or "k").replace(" ", "")
        return f"= {match.group(1)}{unit}"

    return money_pattern.sub(format_money, display)


B_CHOICE_RE = re.compile(
    r"(?im)^([ \t]*)b(?=(?:"
    r"[ \t]*\d{1,2}(?!\d)[^\n]*(?:=|[xb×])[ \t]*\d"
    r"|[ \t]*:?[ \t]*$))"
)


def propose_b_choice(raw: str) -> BChoiceSuggestion | None:
    """Hỏi Bao hay Đề bộ khi một dòng cược bắt đầu bằng chữ B mơ hồ."""
    match = B_CHOICE_RE.search(raw)
    if not match:
        return None
    bao_corrected = raw[:match.start()] + match.group(1) + "Bao" + raw[match.end():]
    bo_corrected = raw[:match.start()] + match.group(1) + "Đề bộ" + raw[match.end():]
    if not calculate(bao_corrected).entries or not calculate(bo_corrected).entries:
        return None
    return BChoiceSuggestion(
        bao_corrected=bao_corrected,
        bo_corrected=bo_corrected,
        bao_display=_suggestion_display(bao_corrected),
        bo_display=_suggestion_display(bo_corrected),
    )


def propose_correction(raw: str) -> CorrectionSuggestion | None:
    """Đề xuất đúng một sửa lỗi chính tả nhỏ, chỉ khi bản sửa vẫn đọc hợp lệ."""
    for match in re.finditer(r"[^\W\d_]+", raw, re.UNICODE):
        old_word = match.group(0)
        plain = ascii_text(old_word).lower()
        # B ở đầu dòng được xử lý bằng lựa chọn Bao/Đề bộ riêng, không phải lỗi gõ.
        if plain == "b":
            continue
        if normalize(old_word) in VALID_INPUT_WORDS:
            continue
        distances = [(target, _edit_distance(plain, target)) for target in CORRECTION_WORDS]
        best_distance = min((distance for _, distance in distances), default=99)
        best = [target for target, distance in distances if distance == best_distance]
        if best_distance != 1 or len(best) != 1:
            continue
        target = best[0]
        replacement = CORRECTION_WORDS[target]
        corrected = raw[:match.start()] + replacement + raw[match.end():]
        corrected_calculation = calculate(corrected)
        original_calculation = calculate(raw)
        if not corrected_calculation.entries:
            continue
        if len(corrected_calculation.rejected) > len(original_calculation.rejected):
            continue
        return CorrectionSuggestion(
            corrected=corrected,
            display=_suggestion_display(corrected),
            old_word=old_word,
            new_word=replacement,
        )
    return None


def format_amount(value: Decimal) -> str:
    if value == value.to_integral():
        raw = f"{int(value):,}".replace(",", ".")
    else:
        raw = f"{value.normalize():f}".replace(".", ",")
    return f"{raw}k"


def format_result(result: Calculation) -> str:
    totals = result.totals()
    if not totals:
        message = "⚠️ Chưa nhận diện được dữ liệu để tính."
    else:
        lines = ["🧾 KẾT QUẢ TÍNH TIỀN", ""]
        for kind, rate in RATES.items():
            if kind not in totals:
                continue
            stake, reward, count, reward_base = totals[kind]
            lines.append(f"{kind} = {format_amount(stake)}")
            if kind == "Càng":
                lines.append("Tỷ lệ: Đặc Biệt càng × 400; Áp càng × 10")
            else:
                lines.append(f"Thưởng = {format_amount(reward_base)} × {str(rate).replace('.', ',')} = {format_amount(reward)}")
            if count > 1:
                lines.append(f"Số vé đã tính: {count}")
            lines.append("")
        message = "\n".join(lines).rstrip()
    if result.rejected:
        message += "\n\n⚠️ Chưa hiểu/thiếu giá:\n" + "\n".join(f"• {item}" for item in result.rejected[:10])
    return message


def format_check(result: Calculation) -> str:
    """Hiển thị bot đã hiểu gì mà không tải hoặc đối chiếu kết quả XSMB."""
    if not result.entries:
        message = "🔍 KIỂM TRA VÉ\n\n⚠️ Chưa nhận diện được dữ liệu để tính."
    else:
        lines = ["🔍 KIỂM TRA VÉ", "", "📖 BOT ĐÃ ĐỌC:"]
        for entry in result.entries[:30]:
            if entry.kind.startswith("Xiên") and entry.ticket_groups:
                group_text = ", ".join("-".join(group) for group in entry.ticket_groups)
                lines.append(
                    f"• {entry.kind} {group_text}: {entry.ticket_count} vé × "
                    f"{format_amount(entry.unit_stake)} = {format_amount(entry.stake)}"
                )
            else:
                source = entry.source or entry.kind
                if entry.kind == "Đề" and re.search(r"\bbo\s*:?\s*\d", normalize(source)):
                    source = f"{source} → {', '.join(entry.numbers)}"
                source = source.replace("de ", "Đề ", 1).replace("bao ", "Bao ", 1)
                source = re.sub(r"\bbo\s+dau\b", "bỏ đầu", source)
                source = re.sub(r"\bbo\s+dit\b", "bỏ đít", source)
                source = re.sub(r"\bbo\s*:", "bộ", source)
                source = re.sub(r"\bbo\b", "bộ", source)
                source = re.sub(r"\bcang\b", "Càng", source)
                source = re.sub(r"\bdau\b", "đầu", source)
                source = re.sub(r"\bdit\b", "đít", source)
                source = re.sub(r"\btong\b", "tổng", source)
                source = re.sub(r"\bdan\b", "dàn", source)
                source = re.sub(r"\bchan\b", "chẵn", source)
                source = re.sub(r"\ble\b", "lẻ", source)
                source = re.sub(r"\bva\b", "và", source)
                lines.append(
                    f"• {source}: {entry.ticket_count} vé × {format_amount(entry.unit_stake)} "
                    f"= {format_amount(entry.stake)}"
                )
        if len(result.entries) > 30:
            lines.append(f"• … và {len(result.entries) - 30} khoản khác")
        lines.extend(["", "TỔNG VỐN:"])
        grand_stake = Decimal("0")
        for kind, values in result.totals().items():
            lines.append(f"• {kind}: {format_amount(values[0])}")
            grand_stake += values[0]
        lines.append(f"• Tất cả: {format_amount(grand_stake)}")
        message = "\n".join(lines)
    if result.rejected:
        message += "\n\n⚠️ DỮ LIỆU CHƯA RÕ/THIẾU GIÁ:\n" + "\n".join(
            f"• {item}" for item in result.rejected[:20]
        )
    elif result.entries:
        message += "\n\n✅ Không có dòng nào bị bỏ qua do lỗi."
    return message
