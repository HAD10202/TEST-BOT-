from __future__ import annotations

import json
import re
import time
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from itertools import combinations
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from calculator import AP_CANG_RATE, Calculation, RATES, format_amount, normalize


AZ24_URL = "https://az24.vn/xsmb-sxmb-xo-so-mien-bac.html"
CACHE_FILE = Path(__file__).with_name("ket_qua_cache.json")
CACHE_SECONDS = 30 * 60
# Việt Nam dùng UTC+7 quanh năm, không có daylight-saving time.
# Dùng offset cố định để Windows không cần cài gói tzdata riêng.
VN_TIMEZONE = timezone(timedelta(hours=7), name="UTC+7")


class ResultError(RuntimeError):
    pass


@dataclass(frozen=True)
class LotteryResult:
    date: str
    special_full: str
    loto: tuple[str, ...]
    fetched_at: float

    @property
    def de_number(self) -> str:
        return self.special_full[-2:]

    @property
    def cang_number(self) -> str:
        return self.special_full[-3:]


def parse_az24_html(html: str) -> LotteryResult:
    start_match = re.search(r'<div\s+id=["\']load_kq_mb_0["\'][^>]*>', html, re.I)
    if not start_match:
        raise ResultError("Không tìm thấy bảng XSMB mới nhất trên AZ24.")
    table_end = html.find("</table>", start_match.end())
    if table_end < 0:
        raise ResultError("Bảng kết quả AZ24 chưa hoàn chỉnh.")
    latest = html[start_match.start():table_end]

    date_matches = list(re.finditer(r"ngày\s+(\d{1,2})-(\d{1,2})-(\d{4})", html[:start_match.start()], re.I))
    if not date_matches:
        raise ResultError("Không đọc được ngày kết quả từ AZ24.")
    day, month, year = date_matches[-1].groups()
    date = f"{int(day):02d}-{int(month):02d}-{year}"

    special_match = re.search(
        r'<span(?=[^>]*class=["\'][^"\']*\bv-gdb\b[^"\']*["\'])[^>]*>\s*(\d{5})\s*</span>',
        latest,
        re.I,
    )
    if not special_match:
        raise ResultError("Giải Đặc biệt trên AZ24 chưa có hoặc chưa hoàn chỉnh.")

    number_pattern = re.compile(
        r'<span(?=[^>]*data-nc=["\']\d+["\'])(?=[^>]*class=["\'][^"\']*\bv-g(?:db|[1-7](?:-\d+)?)\b[^"\']*["\'])[^>]*>\s*(\d{2,5})\s*</span>',
        re.I,
    )
    full_numbers = number_pattern.findall(latest)
    loto = tuple(value[-2:] for value in full_numbers)
    if len(loto) != 27:
        raise ResultError(f"AZ24 mới có {len(loto)}/27 kết quả; bot chưa dùng dữ liệu chưa đủ.")

    return LotteryResult(date, special_match.group(1), loto, time.time())


def _load_cache() -> LotteryResult | None:
    try:
        data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        return LotteryResult(data["date"], data["special_full"], tuple(data["loto"]), float(data["fetched_at"]))
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _save_cache(result: LotteryResult) -> None:
    try:
        CACHE_FILE.write_text(json.dumps(asdict(result), ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def fetch_latest_result(force: bool = False) -> LotteryResult:
    cached = _load_cache()
    if not force and cached and time.time() - cached.fetched_at < CACHE_SECONDS:
        return cached
    try:
        request = Request(AZ24_URL, headers={"User-Agent": "Mozilla/5.0 (Telegram result calculator)"})
        with urlopen(request, timeout=25) as response:
            html = response.read().decode("utf-8", errors="replace")
        result = parse_az24_html(html)
        _save_cache(result)
        return result
    except (HTTPError, URLError, TimeoutError, ResultError) as exc:
        if cached:
            return cached
        if isinstance(exc, ResultError):
            raise
        raise ResultError("Không kết nối được AZ24. Hãy thử lại sau.") from exc


def format_lottery_result(result: LotteryResult) -> str:
    loto_text = " ".join(result.loto)
    warning = _stale_warning(result)
    fetched = datetime.fromtimestamp(result.fetched_at, VN_TIMEZONE).strftime("%H:%M ngày %d-%m-%Y")
    lines = [f"📅 KẾT QUẢ XSMB {result.date}"]
    if warning:
        lines.extend(["", warning])
    lines.extend([
        "",
        f"Giải ĐB: {result.special_full}",
        f"Càng: {result.cang_number}",
        f"Đề: {result.de_number}",
        f"Bao/Xiên (27 số):\n{loto_text}",
        "",
        "Nguồn: AZ24",
        f"Cập nhật lúc: {fetched}",
        "✅ Đã kiểm tra đủ 27 kết quả.",
    ])
    return "\n".join(lines)


def _stale_warning(result: LotteryResult) -> str:
    today = datetime.now(VN_TIMEZONE).strftime("%d-%m-%Y")
    if result.date != today:
        return f"⚠️ Kết quả đang dùng không phải hôm nay ({today}). Hãy kiểm tra ngày trước khi tính."
    return ""


def _winning_for_entry(entry, result: LotteryResult) -> tuple[Decimal, Decimal, int, list[str]]:
    counts = Counter(result.loto)
    if entry.kind == "Đề":
        winning_tickets = entry.numbers.count(result.de_number)
        if winning_tickets:
            base = entry.unit_stake * winning_tickets
            return base, base * RATES[entry.kind], winning_tickets, [result.de_number] * winning_tickets
        return Decimal("0"), Decimal("0"), 0, []

    if entry.kind == "Bao":
        hits: list[str] = []
        hit_count = 0
        for number in entry.numbers:
            occurrences = counts[number]
            hit_count += occurrences
            hits.extend([number] * occurrences)
        base = entry.unit_stake * hit_count
        return base, base * RATES[entry.kind], hit_count, hits

    level = int(entry.kind[-1])
    groups = entry.ticket_groups or tuple(combinations(entry.numbers, level))
    winning_groups = [group for group in groups if all(counts[number] > 0 for number in group)]
    details = ["-".join(combo) for combo in winning_groups]
    base = entry.unit_stake * len(winning_groups)
    return base, base * RATES[entry.kind], len(winning_groups), details


def _format_interpretation(calculation: Calculation) -> list[str]:
    lines = ["📖 BOT ĐÃ ĐỌC:"]
    for entry in calculation.entries[:12]:
        if entry.kind.startswith("Xiên") and entry.ticket_groups:
            source = f"{entry.kind} " + ", ".join("-".join(group) for group in entry.ticket_groups)
        else:
            source = entry.source.replace("de ", "Đề ", 1).replace("bao ", "Bao ", 1)
            if entry.kind == "Đề" and re.search(r"\bbo\b", normalize(entry.source)):
                source = f"{source} → {', '.join(entry.numbers)}"
        source = re.sub(r"\bdau\b", "đầu", source)
        source = re.sub(r"\bdit\b", "đít", source)
        source = re.sub(r"\btong\b", "tổng", source)
        source = re.sub(r"\bdan\b", "dàn", source)
        source = re.sub(r"\bchan\b", "chẵn", source)
        source = re.sub(r"\ble\b", "lẻ", source)
        source = re.sub(r"\bva\b", "và", source)
        source = re.sub(r"\bbo\s*:", "bộ", source)
        source = re.sub(r"\bbo\b", "bộ", source)
        source = re.sub(r"\bcang\b", "Càng", source)
        if entry.ticket_count > 1:
            lines.append(
                f"• {source}: {entry.ticket_count} vé × {format_amount(entry.unit_stake)} = {format_amount(entry.stake)}"
            )
        else:
            lines.append(f"• {source} = {format_amount(entry.unit_stake)}")
    if len(calculation.entries) > 12:
        lines.append(f"• … và {len(calculation.entries) - 12} khoản khác")
    return lines


def format_settlement(calculation: Calculation, result: LotteryResult) -> str:
    totals = calculation.totals()
    lines = [
        f"🧾 TÍNH THƯỞNG XSMB {result.date}",
        f"ĐB: {result.special_full} → Càng {result.cang_number} · Đề {result.de_number}",
    ]
    warning = _stale_warning(result)
    if warning:
        lines.extend(["", warning])
    lines.extend(["", *_format_interpretation(calculation), ""])
    grand_reward = Decimal("0")
    for kind in RATES:
        if kind not in totals:
            continue
        stake = totals[kind][0]
        if kind == "Càng":
            exact_base = Decimal("0")
            apply_base = Decimal("0")
            exact_details: list[str] = []
            apply_details: list[str] = []
            for entry in (item for item in calculation.entries if item.kind == kind):
                for number in entry.numbers:
                    if number == result.cang_number:
                        exact_base += entry.unit_stake
                        exact_details.append(number)
                    # Đã trúng đủ ba số thì không cộng thêm Áp càng.
                    elif number[-2:] == result.de_number:
                        apply_base += entry.unit_stake
                        apply_details.append(number)

            exact_reward = exact_base * RATES["Càng"]
            apply_reward = apply_base * AP_CANG_RATE
            grand_reward += exact_reward + apply_reward
            lines.append("CÀNG")
            lines.append(f"Vốn: {format_amount(stake)}")

            if exact_details:
                detail_counts = Counter(exact_details)
                shown = [
                    f"{item} ×{detail_counts[item]}" if detail_counts[item] > 1 else item
                    for item in list(detail_counts)[:12]
                ]
                suffix = " …" if len(detail_counts) > 12 else ""
                lines.append("🏆 ĐẶC BIỆT CÀNG")
                lines.append(f"Thưởng thực tế: {format_amount(exact_base)}")
                lines.append(f"Trúng {len(exact_details)} lượt: {', '.join(shown)}{suffix}")
                lines.append(
                    f"Tiền thưởng: {format_amount(exact_base)} × 400 = {format_amount(exact_reward)}"
                )
            else:
                lines.append("Đặc Biệt càng: Không trúng")

            if apply_details:
                detail_counts = Counter(apply_details)
                shown = [
                    f"{item} ×{detail_counts[item]}" if detail_counts[item] > 1 else item
                    for item in list(detail_counts)[:12]
                ]
                suffix = " …" if len(detail_counts) > 12 else ""
                lines.append("🎯 ÁP CÀNG")
                lines.append(f"Thưởng thực tế: {format_amount(apply_base)}")
                lines.append(f"Trúng {len(apply_details)} lượt: {', '.join(shown)}{suffix}")
                lines.append(
                    f"Tiền thưởng: {format_amount(apply_base)} × 10 = {format_amount(apply_reward)}"
                )
            else:
                lines.append("Áp càng: Không trúng")
            lines.append("")
            continue

        selected_entries = [item for item in calculation.entries if item.kind == kind]
        actual_base = Decimal("0")
        reward = Decimal("0")
        hit_count = 0
        details: list[str] = []
        for entry in selected_entries:
            entry_base, entry_reward, entry_hits, entry_details = _winning_for_entry(entry, result)
            actual_base += entry_base
            reward += entry_reward
            hit_count += entry_hits
            details.extend(entry_details)
        grand_reward += reward
        section_title = kind.upper()
        if kind == "Đề" and len(selected_entries) == 1:
            bo_match = re.search(r"\bbo\s*:?\s*((?:\d{2}[,./\- ]*)+)", normalize(selected_entries[0].source))
            if bo_match:
                codes = re.findall(r"\d{2}", bo_match.group(1))
                section_title = f"ĐỀ BỘ {', '.join(codes)}"
        lines.append(section_title)
        lines.append(f"Vốn: {format_amount(stake)}")
        lines.append(f"Thưởng thực tế: {format_amount(actual_base)}")
        if hit_count:
            detail_counts = Counter(details)
            unique_details = list(detail_counts)
            shown = [f"{item} ×{detail_counts[item]}" if detail_counts[item] > 1 else item for item in unique_details[:12]]
            detail_text = ", ".join(shown)
            suffix = " …" if len(unique_details) > 12 else ""
            lines.append(f"Trúng {hit_count} lượt: {detail_text}{suffix}")
        else:
            lines.append("Không trúng")
        if reward:
            rate = str(RATES[kind]).replace(".", ",")
            lines.append(f"Tiền thưởng: {format_amount(actual_base)} × {rate} = {format_amount(reward)}")
        lines.append("")
    lines.append(f"💰 TỔNG THƯỞNG: {format_amount(grand_reward)}")
    if calculation.rejected:
        lines.extend(["", "⚠️ Chưa hiểu/thiếu giá:"])
        lines.extend(f"• {item}" for item in calculation.rejected[:10])
    fetched = datetime.fromtimestamp(result.fetched_at, VN_TIMEZONE).strftime("%H:%M")
    lines.extend(["", "Nguồn: AZ24", f"Cập nhật lúc: {fetched}", "✅ Đủ 27 kết quả."])
    return "\n".join(lines)
