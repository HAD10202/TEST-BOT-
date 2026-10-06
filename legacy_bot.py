import asyncio
import logging
import os

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from calculator import calculate, format_check, format_result, propose_b_choice, propose_correction
from results import ResultError, fetch_latest_result, format_lottery_result, format_settlement


logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO)
LOGGER = logging.getLogger(__name__)
# Không ghi các URL chứa token Telegram ra màn hình.
logging.getLogger("httpx").setLevel(logging.WARNING)

BOT_VERSION = "FIX-BO-DAU-DIT-2026-09-14-v9"

BTN_CALCULATE = "🧾 TÍNH TIỀN / THƯỞNG"
BTN_CHECK = "🔍 KIỂM TRA VÉ"
BTN_RESULT = "📅 KẾT QUẢ XSMB"
BTN_RECALCULATE = "🔄 TÍNH LẠI"
BTN_HELP = "📖 HƯỚNG DẪN"
BTN_CANCEL = "❌ HỦY THAO TÁC"
MENU = ReplyKeyboardMarkup(
    [
        [BTN_CALCULATE],
        [BTN_CHECK, BTN_RESULT],
        [BTN_RECALCULATE, BTN_HELP],
        [BTN_CANCEL],
    ],
    resize_keyboard=True,
    is_persistent=True,
)
CORRECTION_MENU = InlineKeyboardMarkup([[
    InlineKeyboardButton("✅ ĐÚNG", callback_data="correction_yes"),
    InlineKeyboardButton("❌ SAI", callback_data="correction_no"),
]])
B_CHOICE_MENU = InlineKeyboardMarkup([[
    InlineKeyboardButton("✅ B = BAO TOÀN BỘ", callback_data="b_choice_bao"),
    InlineKeyboardButton("ĐỀ BỘ", callback_data="b_choice_bo"),
]])
TELEGRAM_SAFE_TEXT_LIMIT = 3900


def _short_display(text: str, limit: int = 3500) -> str:
    return text if len(text) <= limit else text[:limit].rstrip() + "\n…"


def _split_message(text: str, limit: int = TELEGRAM_SAFE_TEXT_LIMIT) -> list[str]:
    """Chia ở ranh giới dễ đọc và luôn thấp hơn giới hạn tin nhắn Telegram."""
    remaining = text.strip()
    chunks: list[str] = []
    while len(remaining) > limit:
        candidates = (
            remaining.rfind("\n\n", 0, limit + 1),
            remaining.rfind("\n", 0, limit + 1),
            remaining.rfind(" ", 0, limit + 1),
        )
        cut = max(candidates)
        if cut < limit // 2:
            cut = limit
        chunks.append(remaining[:cut].rstrip())
        remaining = remaining[cut:].lstrip()
    if remaining:
        chunks.append(remaining)
    return chunks or [""]


async def _reply_long(message, text: str, reply_markup=None) -> None:
    chunks = _split_message(text)
    for index, chunk in enumerate(chunks):
        markup = reply_markup if index == len(chunks) - 1 else None
        await message.reply_text(chunk, reply_markup=markup)


async def _finish_status(status, message, text: str) -> None:
    chunks = _split_message(text)
    await status.edit_text(chunks[0])
    for chunk in chunks[1:]:
        await message.reply_text(chunk)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop("mode", None)
    await update.effective_message.reply_text(
        "✅ Bot đã sẵn sàng. Menu được ghim bên dưới ô nhập tin nhắn.\n\n"
        f"Phiên bản: {BOT_VERSION}\n\n"
        "Mày có thể bấm nút hoặc gửi dữ liệu cần tính trực tiếp.\n\n"
        "Ví dụ:\n"
        "Đề 00 = 50k, Bao 00 = 100k, X 00-11 = 100k, "
        "X 00 11 22 = 100k, X 00 11 22 33 = 100k\n\n"
        "Bot hỗ trợ Đề, Đề bộ, Càng, Bao, Xiên 2/3/4, Xiên quây, đầu, đít, tổng và các dàn cố định.",
        reply_markup=MENU,
    )


async def version_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        f"Phiên bản: {BOT_VERSION}\n"
        "B đầu tin: hỏi BAO toàn bộ hoặc ĐỀ BỘ.\n"
        "Đề cặp/đảo: nhận chuỗi ABC như 924 → 92,24.\n"
        "Tiền 10.000 được hiểu là 10.000k.\n"
        "Dàn mới: Dàn 49; đầu/đít cao-thấp và các tên tương đương.\n"
        "Đầu chẵn/lẻ và đít/đuôi chẵn/lẻ: mỗi dàn 50 số.\n"
        "Dàn thấp thấp/cao thấp/thấp cao/cao cao: mỗi dàn 25 số.\n"
        "Nhiều dàn cách nhau bằng dấu phẩy/chấm phẩy/và được cộng chung một giá.\n"
        "Tổng chẵn/lẻ đi thẳng vào tính toán, không bị hỏi nhầm thành Chập.\n"
        "Càng trúng đủ 3 số: chỉ ×400, không cộng thêm Áp càng ×10.",
        reply_markup=MENU,
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        "CÁCH NHẬP\n\n"
        "Đề 52 = 50k\nĐ 11 x 10k\nđe 00 b 50k\n"
        "00.11.22.33 x 100  (không ghi loại → mặc định Đề)\n"
        "đít 1 x 100\nBao 83 = 100k\nX 00-83 = 100k\n"
        "Xiên: (07.71)(07.64) MC=100k\n"
        "Xquây2 00 11 22 = 100k\n"
        "Đề 88 99 và đầu 9 = 10k\n"
        "Đầu 1247 ghép đít 3689 = 5k\n"
        "Dàn 49 = 10k\nĐầu cao = 10k\nĐuôi nhỏ = 10k\n"
        "Đầu chẵn = 10k\nĐầu lẻ = 10k\nĐít chẵn = 10k\nĐuôi lẻ = 10k\n"
        "Thấp thấp = 10k\nCao thấp = 10k\nThấp cao = 10k\nCao cao = 10k\n"
        "Đề thấp thấp, chập, lẻ lẻ = 10k\n"
        "Đề tổng trên 10, đầu 1 = 100k\n"
        "Tổng dưới 10 = 10k\nTổng chẵn = 10k\n"
        "Đề 010.020.888 = 10k  (cặp đảo)\n\n"
        "B91=175k hoặc b20b500k  (bot hỏi Bao hay Đề bộ)\n"
        "Bộ 00=10k  (bung 00,05,50,55)\n"
        "C 851=10k  (Đặc Biệt càng ×400; Áp càng ×10)\n\n"
        "Các dấu =, x, × và b đều dùng để ghi tiền.\n"
        "MC nghĩa là mỗi cặp. Không ghi loại vé thì mặc định là Đề.\n"
        "Gõ /version để kiểm tra đúng bản đang chạy.",
        reply_markup=MENU,
    )


async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["mode"] = "check"
    await update.effective_message.reply_text(
        "🔍 Gửi dữ liệu vé cần kiểm tra. Bot chỉ đọc và tính vốn, chưa đối chiếu kết quả XSMB.",
        reply_markup=MENU,
    )


async def result_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    status = await update.effective_message.reply_text("⏳ Đang cập nhật kết quả từ AZ24...")
    try:
        result = await asyncio.to_thread(fetch_latest_result, True)
        await status.edit_text(format_lottery_result(result))
    except ResultError as exc:
        await status.edit_text(f"⚠️ {exc}")


async def _calculate_message(message, raw: str, force_result: bool = False) -> None:
    status = await message.reply_text("⏳ Đang đọc dữ liệu và kiểm tra kết quả...")
    calculation = calculate(raw)
    if not calculation.entries:
        await _finish_status(status, message, format_result(calculation))
        return
    result = await asyncio.to_thread(fetch_latest_result, force_result)
    await _finish_status(status, message, format_settlement(calculation, result))


async def _process_user_text(message, context: ContextTypes.DEFAULT_TYPE, raw: str, mode: str) -> None:
    b_choice = propose_b_choice(raw)
    if b_choice:
        context.user_data.pop("pending_correction", None)
        context.user_data["pending_b_choice"] = {
            "bao_corrected": b_choice.bao_corrected,
            "bo_corrected": b_choice.bo_corrected,
            "bao_display": b_choice.bao_display,
            "bo_display": b_choice.bo_display,
            "mode": mode,
        }
        await message.reply_text(
            "🤔 Tin nhắn bắt đầu bằng B.\n\n"
            "Ý của bạn có phải B = Bao và áp dụng Bao cho TOÀN BỘ các khoản trong tin nhắn này không?\n\n"
            f"1️⃣ {_short_display(b_choice.bao_display, 1500)}\n"
            f"2️⃣ {_short_display(b_choice.bo_display, 1500)}",
            reply_markup=B_CHOICE_MENU,
        )
        return

    suggestion = propose_correction(raw)
    if suggestion:
        context.user_data["pending_correction"] = {
            "corrected": suggestion.corrected,
            "display": suggestion.display,
            "mode": mode,
        }
        await message.reply_text(
            "🤔 Ý của bạn có phải là:\n\n"
            f"{_short_display(suggestion.display)}\n\n"
            f"Bot đang đề xuất sửa “{suggestion.old_word}” thành “{suggestion.new_word}”.",
            reply_markup=CORRECTION_MENU,
        )
        return

    if mode == "check":
        await _reply_long(message, format_check(calculate(raw)), reply_markup=MENU)
        return
    context.user_data["last_bet"] = raw
    await _calculate_message(message, raw)


async def b_choice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    pending = context.user_data.pop("pending_b_choice", None)
    if not pending:
        await query.edit_message_text("⚠️ Lựa chọn này đã hết hiệu lực. Hãy gửi lại dữ liệu.")
        return
    choice = "bao" if query.data == "b_choice_bao" else "bo"
    corrected = pending[f"{choice}_corrected"]
    display = pending[f"{choice}_display"]
    await query.edit_message_text(f"✅ Đã chọn:\n\n{_short_display(display)}")
    try:
        await _process_user_text(query.message, context, corrected, pending["mode"])
    except ResultError as exc:
        calculation = calculate(corrected)
        await _reply_long(
            query.message,
            f"{format_result(calculation)}\n\n⚠️ Chưa tính thưởng thực tế: {exc}",
            reply_markup=MENU,
        )
    except Exception:
        LOGGER.exception("Không thể xử lý dữ liệu sau khi chọn Bao/Đề bộ")
        await query.message.reply_text("Có lỗi khi xử lý lựa chọn. Hãy thử lại.", reply_markup=MENU)


async def correction_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    pending = context.user_data.pop("pending_correction", None)
    if not pending:
        await query.edit_message_text("⚠️ Gợi ý này đã hết hiệu lực. Hãy gửi lại dữ liệu.")
        return
    if query.data == "correction_no":
        await query.edit_message_text("❌ Đã bỏ gợi ý. Hãy sửa hoặc gửi lại dữ liệu theo ý của bạn.")
        return

    await query.edit_message_text(f"✅ Đã xác nhận sửa thành:\n\n{_short_display(pending['display'])}")
    try:
        await _process_user_text(query.message, context, pending["corrected"], pending["mode"])
    except ResultError as exc:
        calculation = calculate(pending["corrected"])
        await _reply_long(
            query.message,
            f"{format_result(calculation)}\n\n⚠️ Chưa tính thưởng thực tế: {exc}",
            reply_markup=MENU,
        )
    except Exception:
        LOGGER.exception("Không thể xử lý dữ liệu sau khi xác nhận sửa")
        await query.message.reply_text("Có lỗi khi xử lý dữ liệu đã sửa. Hãy thử lại.", reply_markup=MENU)


async def recalculate_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    raw = context.user_data.get("last_bet")
    if not raw:
        await update.effective_message.reply_text("Chưa có tin nhắn cược gần nhất để tính lại.")
        return
    try:
        await _calculate_message(update.effective_message, raw, True)
    except ResultError as exc:
        await update.effective_message.reply_text(f"⚠️ {exc}")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message or not update.effective_message.text:
        return
    raw = update.effective_message.text.strip()
    if raw == BTN_CALCULATE:
        context.user_data["mode"] = "calculate"
        await update.effective_message.reply_text("🧾 Gửi dữ liệu cần tính.", reply_markup=MENU)
        return
    if raw == BTN_CHECK:
        await check_command(update, context)
        return
    if raw == BTN_RESULT:
        await result_command(update, context)
        return
    if raw == BTN_RECALCULATE:
        await recalculate_command(update, context)
        return
    if raw == BTN_HELP:
        await help_command(update, context)
        return
    if raw == BTN_CANCEL:
        context.user_data.pop("mode", None)
        context.user_data.pop("pending_correction", None)
        context.user_data.pop("pending_b_choice", None)
        await update.effective_message.reply_text("✅ Đã hủy thao tác. Mày có thể chọn lại trên menu.", reply_markup=MENU)
        return

    try:
        mode = context.user_data.pop("mode", "calculate")
        context.user_data.pop("pending_correction", None)
        context.user_data.pop("pending_b_choice", None)
        await _process_user_text(update.effective_message, context, raw, mode)
    except ResultError as exc:
        calculation = calculate(update.effective_message.text)
        fallback = format_result(calculation)
        await _reply_long(update.effective_message, f"{fallback}\n\n⚠️ Chưa tính thưởng thực tế: {exc}")
    except Exception:
        LOGGER.exception("Không thể xử lý tin nhắn")
        await update.effective_message.reply_text("Có lỗi khi đọc dữ liệu. Hãy kiểm tra lại nội dung và thử lại.")


def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("Thiếu TELEGRAM_BOT_TOKEN. Xem README.md để cài đặt.")
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("version", version_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("huongdan", help_command))
    app.add_handler(CommandHandler("kiemtra", check_command))
    app.add_handler(CommandHandler("ketqua", result_command))
    app.add_handler(CommandHandler("tinhlai", recalculate_command))
    app.add_handler(CallbackQueryHandler(b_choice_callback, pattern=r"^b_choice_(?:bao|bo)$"))
    app.add_handler(CallbackQueryHandler(correction_callback, pattern=r"^correction_(?:yes|no)$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
