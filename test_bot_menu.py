import ast
import unittest
from pathlib import Path


class BotMenuTests(unittest.TestCase):
    def setUp(self):
        self.source = Path(__file__).with_name("legacy_bot.py").read_text(encoding="utf-8")
        ast.parse(self.source)

    def test_main_menu_contains_every_action_and_is_persistent(self):
        for label in (
            "🧾 TÍNH TIỀN / THƯỞNG",
            "🔍 KIỂM TRA VÉ",
            "📅 KẾT QUẢ XSMB",
            "🔄 TÍNH LẠI",
            "📖 HƯỚNG DẪN",
            "❌ HỦY THAO TÁC",
        ):
            self.assertIn(label, self.source)
        self.assertIn("is_persistent=True", self.source)

    def test_inline_correction_has_yes_and_no_callbacks(self):
        self.assertIn("✅ ĐÚNG", self.source)
        self.assertIn("❌ SAI", self.source)
        self.assertIn('callback_data="correction_yes"', self.source)
        self.assertIn('callback_data="correction_no"', self.source)
        self.assertIn("CallbackQueryHandler(correction_callback", self.source)

    def test_ambiguous_b_has_bao_and_de_bo_buttons(self):
        self.assertIn('InlineKeyboardButton("✅ B = BAO TOÀN BỘ", callback_data="b_choice_bao")', self.source)
        self.assertIn('InlineKeyboardButton("ĐỀ BỘ", callback_data="b_choice_bo")', self.source)
        self.assertIn("CallbackQueryHandler(b_choice_callback", self.source)
        self.assertIn("áp dụng Bao cho TOÀN BỘ các khoản", self.source)

    def test_release_has_visible_version_command(self):
        self.assertIn('BOT_VERSION = "FIX-BO-DAU-DIT-2026-09-14-v9"', self.source)
        self.assertIn('CommandHandler("version", version_command)', self.source)
        self.assertIn("không cộng thêm Áp càng ×10", self.source)

    def test_long_messages_are_split_below_telegram_limit(self):
        tree = ast.parse(self.source)
        split_function = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "_split_message"
        )
        namespace = {"TELEGRAM_SAFE_TEXT_LIMIT": 3900}
        exec(compile(ast.Module(body=[split_function], type_ignores=[]), "bot.py", "exec"), namespace)
        chunks = namespace["_split_message"](("vé 00 = 10k\n" * 1000).strip())
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk) <= 3900 for chunk in chunks))
        self.assertEqual("\n".join(chunks).replace("\n", " ").split(), ("vé 00 = 10k\n" * 1000).split())


if __name__ == "__main__":
    unittest.main()
