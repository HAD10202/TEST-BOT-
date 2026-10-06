import unittest
from decimal import Decimal

from calculator import (
    DAN_49, DAN_HEAD_EVEN, DAN_HEAD_HIGH, DAN_HEAD_LOW, DAN_HEAD_ODD,
    DAN_HIGH_HIGH, DAN_HIGH_LOW, DAN_LOW_HIGH, DAN_LOW_LOW,
    DAN_TAIL_EVEN, DAN_TAIL_HIGH, DAN_TAIL_LOW, DAN_TAIL_ODD,
    DE_BO, calculate, format_check, format_result, parse_de_numbers,
    propose_b_choice, propose_correction,
)
from results import LotteryResult, format_settlement, parse_az24_html


class CalculatorTests(unittest.TestCase):
    def test_xien_header_preserves_first_digit_of_ticket(self):
        calculation = calculate("Xien.\n30-28=94k\n30-82=94k\n96-32=94k\n32-73=94k")
        self.assertFalse(calculation.rejected)
        self.assertEqual([entry.numbers for entry in calculation.entries],
                         [("30", "28"), ("30", "82"), ("96", "32"), ("32", "73")])
        self.assertEqual(calculation.totals()["Xiên 2"][0], Decimal("376"))

    def test_xien_two_digit_numbers_and_explicit_levels(self):
        for label in ("Xien", "Xiên", "Xieng"):
            for number in range(20, 50):
                with self.subTest(label=label, number=number):
                    calculation = calculate(f"{label} {number}-82=94k")
                    self.assertFalse(calculation.rejected)
                    self.assertEqual(calculation.entries[0].numbers, (str(number), "82"))
        for label, numbers in (("Xiên 2", ("30", "28")),
                               ("xien3", ("30", "28", "82")),
                               ("Xiên 4", ("30", "28", "82", "96"))):
            calculation = calculate(f"{label} {'-'.join(numbers)}=94k")
            self.assertFalse(calculation.rejected)
            self.assertEqual(calculation.entries[0].numbers, numbers)

    def test_de_list_can_exclude_head_and_tail_from_following_line(self):
        raw = """Đề:
12 13 14 15 16 17 18
21 23 24 25 26 27 28
31 32 34 35 36 37 38
41 42 43 45 46 47 48
51 52 53 54 56 57 58
61 62 63 64 65 67 68
71 72 73 74 75 76 78
81 82 83 84 85 86 87
Mỗi SỐ = 55k
( bỏ đầu 5 và bỏ đít 1 )"""
        calculation = calculate(raw)
        self.assertFalse(calculation.rejected)
        entry = calculation.entries[0]
        self.assertEqual(entry.ticket_count, 43)
        self.assertEqual(entry.stake, Decimal("2365"))
        self.assertFalse(any(number.startswith("5") for number in entry.numbers))
        self.assertFalse(any(number.endswith("1") for number in entry.numbers))
        checked = format_check(calculation)
        self.assertIn("bỏ đầu 5 và bỏ đít 1", checked)
        self.assertNotIn("bộ đầu", checked)

    def test_de_exclusions_work_on_same_line_and_without_accents(self):
        calculation = calculate("De 11 12 21 22 moi so = 10k (bo dau 1 va bo dit 1)")
        self.assertFalse(calculation.rejected)
        self.assertEqual(calculation.entries[0].numbers, ("22",))
        self.assertEqual(calculation.entries[0].stake, Decimal("10"))

    def test_full_user_example(self):
        raw = (
            "Đề 00 = 50k, Bao 00 = 100k, X 00 - 11 = 100k, "
            "X 00 11 22 = 100k, X 00 11 22 33 = 100"
        )
        totals = calculate(raw).totals()
        self.assertEqual(totals["Đề"][:2], (Decimal("50"), Decimal("4500")))
        self.assertEqual(totals["Bao"][:2], (Decimal("100"), Decimal("350")))
        self.assertEqual(totals["Xiên 2"][:2], (Decimal("100"), Decimal("1500")))
        self.assertEqual(totals["Xiên 3"][:2], (Decimal("100"), Decimal("4800")))
        self.assertEqual(totals["Xiên 4"][:2], (Decimal("100"), Decimal("18000")))

    def test_only_present_categories_are_printed(self):
        output = format_result(calculate("Đề 00 = 100k"))
        self.assertIn("Đề = 100k", output)
        self.assertNotIn("Bao =", output)
        self.assertNotIn("Xiên", output)

    def test_typo_and_missing_accents(self):
        totals = calculate("Đ đâu 5 = 10; dề dít 5x10").totals()
        self.assertEqual(totals["Đề"][0], Decimal("200"))
        self.assertEqual(totals["Đề"][2], 20)

    def test_equal_x_b_and_default_de(self):
        cases = {
            "00.11.22. 33 x 100": (Decimal("400"), 4),
            "đit 1 x 100": (Decimal("1000"), 10),
            "Đ 11 x 10k": (Decimal("10"), 1),
            "đe 00 b 50k": (Decimal("50"), 1),
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                result = calculate(raw)
                self.assertFalse(result.rejected)
                self.assertEqual(result.totals()["Đề"][0], expected[0])
                self.assertEqual(result.totals()["Đề"][2], expected[1])

    def test_unlabelled_line_after_bao_defaults_to_de(self):
        totals = calculate("Bao 83 = 100k\n00.11 = 50k").totals()
        self.assertEqual(totals["Bao"][0], Decimal("100"))
        self.assertEqual(totals["Đề"][0], Decimal("100"))

    def test_dau_dit_counts_as_two_full_sets(self):
        raw = (
            "45,54,00,05,50,03.30=50\n"
            "Đầu 173 x20\n"
            "Đầu 7.0.5=50\n"
            "đề 17.71.47.74.27.72,09,90 x 100\n"
            "Đít 1 x 100\n"
            "ĐẦU ĐÍT 2=50"
        )
        calculation = calculate(raw)
        totals = calculation.totals()
        self.assertFalse(calculation.rejected)
        self.assertEqual(totals["Đề"][0], Decimal("5250"))
        last_entry = calculation.entries[-1]
        self.assertEqual(last_entry.ticket_count, 20)
        self.assertEqual(last_entry.numbers.count("22"), 2)

        result = LotteryResult("12-09-2026", "12352", tuple(f"{n:02d}" for n in range(27)), 0)
        output = format_settlement(calculation, result)
        self.assertIn("Vốn: 5.250k", output)
        self.assertIn("Thưởng thực tế: 100k", output)
        self.assertIn("Tiền thưởng: 100k × 90 = 9.000k", output)

    def test_separate_dau_2_dit_2_keeps_overlap(self):
        calculation = calculate("Đề: ĐẦU 2 ĐÍT 2 = 50")
        self.assertFalse(calculation.rejected)
        self.assertEqual(calculation.totals()["Đề"][0], Decimal("1000"))
        entry = calculation.entries[0]
        self.assertEqual(entry.ticket_count, 20)
        self.assertEqual(entry.numbers.count("22"), 2)

        result = LotteryResult("12-09-2026", "12322", tuple(f"{n:02d}" for n in range(27)), 0)
        output = format_settlement(calculation, result)
        self.assertIn("Thưởng thực tế: 100k", output)
        self.assertIn("Trúng 2 lượt: 22 ×2", output)
        self.assertIn("Tiền thưởng: 100k × 90 = 9.000k", output)

    def test_original_de_source_preserves_every_repeated_ticket(self):
        raw = (
            "01,28,08.01,08,80.01,62,28 =10 "
            "01,28,80,01=10 "
            "01,10=25 "
            "12,21,72=10 "
            "01-28-01-80=20 "
            "60=300"
        )
        calculation = calculate(raw)
        self.assertFalse(calculation.rejected)
        self.assertEqual(calculation.totals()["Đề"][0], Decimal("590"))
        self.assertEqual(calculation.totals()["Đề"][2], 23)
        self.assertEqual(calculation.entries[0].numbers.count("01"), 3)
        self.assertEqual(calculation.entries[1].numbers.count("01"), 2)
        self.assertEqual(calculation.entries[4].numbers.count("01"), 2)

        result = LotteryResult("12-09-2026", "12301", tuple(f"{n:02d}" for n in range(27)), 0)
        output = format_settlement(calculation, result)
        self.assertIn("Thưởng thực tế: 115k", output)
        self.assertIn("Trúng 8 lượt: 01 ×8", output)
        self.assertIn("Tiền thưởng: 115k × 90 = 10.350k", output)

    def test_original_source_debug_de_1(self):
        raw = (
            "Đề: Tổng 4 = 90k\n"
            "Đề: 98 = 300k\n"
            "Đề: 77 78 48 49 50 = 10k\n"
            "Đề: 22.55 = 50k\n"
            "Đề: dau 2 , dit 2 =30k\n"
            "Đề: 38.83.37.45.65.57.75.86=20k /1số\n"
            "Đề: Dau 4=30k"
        )
        calculation = calculate(raw)
        self.assertFalse(calculation.rejected)
        self.assertEqual(calculation.totals()["Đề"][0], Decimal("2410"))

    def test_original_source_debug_de_2(self):
        raw = (
            "Đề :\n"
            "Tổng 2,7=10k\n"
            "Đầu 7=30k\n"
            "Đầu 2=10k\n"
            "37,73,23,32=50k/1số\n"
            "04,40,09,90,45,54,59,95=20k/1số\n\n"
            "Đề: 23,32,28,82,37,73,78,87,33,88,38,83=15k/1số"
        )
        calculation = calculate(raw)
        self.assertFalse(calculation.rejected)
        self.assertEqual(calculation.totals()["Đề"][0], Decimal("1140"))

    def test_original_source_bao_and_xien_core_rules(self):
        cases = {
            "Bao:\n23,15 =500": {"Bao": Decimal("1000")},
            "Bao 86 /68 =200": {"Bao": Decimal("400")},
            "X2 00 11=100": {"Xiên 2": Decimal("100")},
            "X3 00 11 22=100": {"Xiên 3": Decimal("100")},
            "X4 00 11 22 33=100": {"Xiên 4": Decimal("100")},
            "XQ2 00 11 22 33=10": {"Xiên 2": Decimal("60")},
            "XQ 00 11 22 33=10": {
                "Xiên 2": Decimal("60"),
                "Xiên 3": Decimal("40"),
                "Xiên 4": Decimal("10"),
            },
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                calculation = calculate(raw)
                self.assertFalse(calculation.rejected)
                totals = calculation.totals()
                self.assertEqual({kind: values[0] for kind, values in totals.items()}, expected)

    def test_new_parity_sets(self):
        self.assertEqual(len(parse_de_numbers("dàn chẵn lẻ")), 25)
        self.assertEqual(len(parse_de_numbers("dan le chan")), 25)
        self.assertEqual(len(parse_de_numbers("dàn lẻ lẻ")), 25)
        self.assertEqual(len(parse_de_numbers("dàn chẵn chẵn")), 25)
        self.assertIn("01", parse_de_numbers("dàn chẵn lẻ"))
        self.assertIn("98", parse_de_numbers("dàn lẻ chẵn"))

    def test_even_odd_sums(self):
        even = parse_de_numbers("tổng chẵn")
        odd = parse_de_numbers("tổng lẻ")
        self.assertEqual(len(even), 50)
        self.assertEqual(len(odd), 50)
        self.assertEqual(set(even), {f"{a}{b}" for a in range(10) for b in range(10) if (a + b) % 2 == 0})
        self.assertEqual(set(odd), {f"{a}{b}" for a in range(10) for b in range(10) if (a + b) % 2 == 1})
        self.assertFalse(set(even) & set(odd))

    def test_sum_under_ten_and_dan_49_match_supplied_sets(self):
        expected_under_ten = [f"{a}{b}" for a in range(10) for b in range(10) if a + b < 10]
        for raw in ("tổng dưới 10", "tong duoi 10", "tổng nhỏ hơn 10"):
            with self.subTest(raw=raw):
                under_ten = parse_de_numbers(raw)
                self.assertEqual(under_ten, expected_under_ten)
                self.assertEqual(len(under_ten), 55)

        expected_49 = [f"{a}{b}" for a in range(2, 9) for b in range(2, 9)]
        self.assertEqual(DAN_49, expected_49)
        for raw in ("Dàn 49=10k", "Dan49=10k", "Đề dàn 49 = 10k"):
            with self.subTest(raw=raw):
                calculation = calculate(raw)
                self.assertFalse(calculation.rejected)
                self.assertEqual(calculation.entries[0].numbers, tuple(expected_49))
                self.assertEqual(calculation.entries[0].ticket_count, 49)
                self.assertEqual(calculation.entries[0].stake, Decimal("490"))

        removed_48 = calculate("Dàn 48=10k")
        self.assertFalse(removed_48.entries)
        self.assertEqual(len(removed_48.rejected), 1)
        self.assertIn("Dàn 48 không được hỗ trợ", removed_48.rejected[0])

    def test_high_low_head_tail_aliases(self):
        cases = {
            "Đầu cao=10k": DAN_HEAD_HIGH,
            "đầu to=10k": DAN_HEAD_HIGH,
            "dauto=10k": DAN_HEAD_HIGH,
            "Đầu thấp=10k": DAN_HEAD_LOW,
            "đầu bé=10k": DAN_HEAD_LOW,
            "dau nho=10k": DAN_HEAD_LOW,
            "Đít cao=10k": DAN_TAIL_HIGH,
            "đít to=10k": DAN_TAIL_HIGH,
            "đuôi cao=10k": DAN_TAIL_HIGH,
            "duoito=10k": DAN_TAIL_HIGH,
            "Đít thấp=10k": DAN_TAIL_LOW,
            "đít nhỏ=10k": DAN_TAIL_LOW,
            "đuôi bé=10k": DAN_TAIL_LOW,
            "duoi nho=10k": DAN_TAIL_LOW,
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                calculation = calculate(raw)
                self.assertFalse(calculation.rejected)
                self.assertEqual(calculation.entries[0].numbers, tuple(expected))
                self.assertEqual(calculation.entries[0].ticket_count, 50)
                self.assertEqual(calculation.entries[0].stake, Decimal("500"))

    def test_even_odd_head_tail_aliases(self):
        self.assertEqual(DAN_HEAD_EVEN, [f"{a}{b}" for a in range(0, 10, 2) for b in range(10)])
        self.assertEqual(DAN_HEAD_ODD, [f"{a}{b}" for a in range(1, 10, 2) for b in range(10)])
        self.assertEqual(DAN_TAIL_EVEN, [f"{a}{b}" for a in range(10) for b in range(0, 10, 2)])
        self.assertEqual(DAN_TAIL_ODD, [f"{a}{b}" for a in range(10) for b in range(1, 10, 2)])
        self.assertFalse(set(DAN_HEAD_EVEN) & set(DAN_HEAD_ODD))
        self.assertFalse(set(DAN_TAIL_EVEN) & set(DAN_TAIL_ODD))
        cases = {
            "Đầu chẵn=10k": DAN_HEAD_EVEN,
            "dau chan=10k": DAN_HEAD_EVEN,
            "dauchan=10k": DAN_HEAD_EVEN,
            "Đầu lẻ=10k": DAN_HEAD_ODD,
            "dau le=10k": DAN_HEAD_ODD,
            "daule=10k": DAN_HEAD_ODD,
            "Đít chẵn=10k": DAN_TAIL_EVEN,
            "dit chan=10k": DAN_TAIL_EVEN,
            "đuôi chẵn=10k": DAN_TAIL_EVEN,
            "duoichan=10k": DAN_TAIL_EVEN,
            "Đít lẻ=10k": DAN_TAIL_ODD,
            "dit le=10k": DAN_TAIL_ODD,
            "đuôi lẻ=10k": DAN_TAIL_ODD,
            "duoile=10k": DAN_TAIL_ODD,
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                calculation = calculate(raw)
                self.assertFalse(calculation.rejected)
                self.assertEqual(calculation.entries[0].numbers, tuple(expected))
                self.assertEqual(calculation.entries[0].ticket_count, 50)
                self.assertEqual(calculation.entries[0].stake, Decimal("500"))
                self.assertIsNone(propose_correction(raw))

    def test_valid_keywords_never_trigger_typo_prompt(self):
        valid_inputs = (
            "Đề tổng chẵn = 100k",
            "Đề tổng lẻ = 100k",
            "Đề đảo 924 = 10k",
            "Đề cặp 924 = 10k",
            "Đầu cao = 10k",
            "Đầu thấp = 10k",
            "Đuôi to = 10k",
            "Đuôi bé = 10k",
            "Ba càng 851 = 10k",
            "Bao:\n12 02 20\nMỗi số=10k",
        )
        for raw in valid_inputs:
            with self.subTest(raw=raw):
                calculation = calculate(raw)
                self.assertTrue(calculation.entries)
                self.assertFalse(calculation.rejected)
                self.assertIsNone(propose_correction(raw))

    def test_named_sets_accept_every_price_separator_without_becoming_xien(self):
        names_and_counts = {
            "Tổng chẵn": 50,
            "Tổng lẻ": 50,
            "Đầu chẵn": 50,
            "Đầu lẻ": 50,
            "Đít chẵn": 50,
            "Đuôi lẻ": 50,
            "Dàn chẵn lẻ": 25,
        }
        for name, expected_count in names_and_counts.items():
            for marker in ("=", "x", "b", "×"):
                raw = f"{name} {marker} 10k"
                with self.subTest(raw=raw):
                    calculation = calculate(raw)
                    self.assertFalse(calculation.rejected)
                    self.assertEqual(calculation.entries[0].kind, "Đề")
                    self.assertEqual(calculation.entries[0].ticket_count, expected_count)
                    self.assertIsNone(propose_correction(raw))

    def test_high_low_quadrant_sets_match_supplied_lists(self):
        expected = {
            "Dàn thấp thấp": [f"{a}{b}" for a in range(5) for b in range(5)],
            "Dàn cao thấp": [f"{a}{b}" for a in range(5, 10) for b in range(5)],
            "Dàn thấp cao": [f"{a}{b}" for a in range(5) for b in range(5, 10)],
            "Dàn cao cao": [f"{a}{b}" for a in range(5, 10) for b in range(5, 10)],
        }
        self.assertEqual(DAN_LOW_LOW, expected["Dàn thấp thấp"])
        self.assertEqual(DAN_HIGH_LOW, expected["Dàn cao thấp"])
        self.assertEqual(DAN_LOW_HIGH, expected["Dàn thấp cao"])
        self.assertEqual(DAN_HIGH_HIGH, expected["Dàn cao cao"])
        self.assertEqual(
            set().union(*(set(numbers) for numbers in expected.values())),
            {f"{n:02d}" for n in range(100)},
        )
        for name, numbers in expected.items():
            for raw in (f"{name}=10k", f"{name.removeprefix('Dàn ')}=10k", f"{name.replace(' ', '')}=10k"):
                with self.subTest(raw=raw):
                    calculation = calculate(raw)
                    self.assertFalse(calculation.rejected)
                    self.assertEqual(calculation.entries[0].numbers, tuple(numbers))
                    self.assertEqual(calculation.entries[0].ticket_count, 25)
                    self.assertEqual(calculation.entries[0].stake, Decimal("250"))
                    self.assertIsNone(propose_correction(raw))

    def test_multiple_named_de_sets_share_one_price_and_keep_overlaps(self):
        combined = calculate("đề thấp thấp , chập , lẻ lẻ = 10k")
        self.assertFalse(combined.rejected)
        self.assertEqual(combined.entries[0].ticket_count, 60)
        self.assertEqual(combined.entries[0].stake, Decimal("600"))
        self.assertEqual(combined.entries[0].numbers.count("11"), 3)
        self.assertIsNone(propose_correction("đề thấp thấp , chập , lẻ lẻ = 10k"))

        total_and_head = calculate("đê tổng trên 10 , đầu 1 = 100k")
        self.assertFalse(total_and_head.rejected)
        self.assertEqual(total_and_head.entries[0].ticket_count, 46)
        self.assertEqual(total_and_head.entries[0].stake, Decimal("4600"))
        self.assertIsNone(propose_correction("đê tổng trên 10 , đầu 1 = 100k"))

        under_and_tail = calculate("Đề tổng dưới 10, đít 9=10k")
        self.assertFalse(under_and_tail.rejected)
        self.assertEqual(under_and_tail.entries[0].ticket_count, 65)
        self.assertEqual(under_and_tail.entries[0].stake, Decimal("650"))

        result = LotteryResult("13-09-2026", "12311", tuple(f"{n:02d}" for n in range(27)), 0)
        output = format_settlement(combined, result)
        self.assertIn("Vốn: 600k", output)
        self.assertIn("Thưởng thực tế: 30k", output)
        self.assertIn("Trúng 3 lượt: 11 ×3", output)
        self.assertIn("Tiền thưởng: 30k × 90 = 2.700k", output)

    def test_new_fixed_sets_reward_only_the_winning_ticket_stake(self):
        cases = (
            ("Dàn 49=10k", "22", "Vốn: 490k"),
            ("Đầu cao=10k", "58", "Vốn: 500k"),
            ("Đầu thấp=10k", "08", "Vốn: 500k"),
            ("Đuôi cao=10k", "95", "Vốn: 500k"),
            ("Đuôi nhỏ=10k", "94", "Vốn: 500k"),
            ("Tổng dưới 10=10k", "45", "Vốn: 550k"),
            ("Đầu chẵn=10k", "28", "Vốn: 500k"),
            ("Đầu lẻ=10k", "39", "Vốn: 500k"),
            ("Đít chẵn=10k", "98", "Vốn: 500k"),
            ("Đít lẻ=10k", "99", "Vốn: 500k"),
        )
        for raw, winning_number, expected_capital in cases:
            with self.subTest(raw=raw):
                calculation = calculate(raw)
                result = LotteryResult(
                    "13-09-2026", f"123{winning_number}",
                    tuple(f"{n:02d}" for n in range(27)), 0,
                )
                output = format_settlement(calculation, result)
                self.assertIn(expected_capital, output)
                self.assertIn("Thưởng thực tế: 10k", output)
                self.assertIn("Tiền thưởng: 10k × 90 = 900k", output)

    def test_reward_uses_unit_stake_not_whole_de_set(self):
        totals = calculate("Đề tổng chẵn = 50k").totals()
        self.assertEqual(totals["Đề"][0], Decimal("2500"))
        self.assertEqual(totals["Đề"][1], Decimal("4500"))
        self.assertEqual(totals["Đề"][3], Decimal("50"))
        output = format_result(calculate("Đề tổng chẵn = 50k"))
        self.assertIn("Thưởng = 50k × 90 = 4.500k", output)
        self.assertNotIn("225.000k", output)

    def test_normal_xien_uses_actual_number_count(self):
        totals = calculate("Xiên 2 00 11 22 = 10k").totals()
        self.assertNotIn("Xiên 2", totals)
        self.assertEqual(totals["Xiên 3"][0], Decimal("10"))
        self.assertEqual(totals["Xiên 3"][2], 1)

    def test_xien_quay_from_source(self):
        totals = calculate("XQ 00 11 22 = 10k").totals()
        self.assertEqual(totals["Xiên 2"][0], Decimal("30"))
        self.assertEqual(totals["Xiên 3"][0], Decimal("10"))
        self.assertNotIn("Xiên 4", totals)

    def test_parse_daily_result_and_actual_rewards(self):
        prizes = [
            "29352", "76083", "08590", "75553", "88200", "79039", "18954", "69147", "63705", "52097",
            "3999", "8383", "3002", "5031", "2110", "3571", "3864", "5633", "0008", "2974", "827", "083",
            "875", "00", "41", "89", "12",
        ]
        spans = []
        for i, number in enumerate(prizes):
            css = "v-gdb" if i == 0 else f"v-g1-{i}"
            spans.append(f'<span data-nc="{len(number)}" class="{css}">{number}</span>')
        html = f'<div>ngày 11-9-2026</div><div id="load_kq_mb_0"><table>{"".join(spans)}</table>'
        result = parse_az24_html(html)
        self.assertEqual(result.de_number, "52")
        self.assertEqual(len(result.loto), 27)
        self.assertEqual(result.loto.count("83"), 3)

        calculation = calculate("Đề 52=50k, Bao 83=100k, X 00 83=100k")
        output = format_settlement(calculation, result)
        self.assertIn("ĐỀ\nVốn: 50k", output)
        self.assertIn("Thưởng thực tế: 50k", output)
        self.assertIn("Tiền thưởng: 50k × 90 = 4.500k", output)
        self.assertIn("Thưởng thực tế: 300k", output)
        self.assertIn("Tiền thưởng: 300k × 3,5 = 1.050k", output)
        self.assertIn("Tiền thưởng: 100k × 15 = 1.500k", output)
        self.assertIn("💰 TỔNG THƯỞNG: 7.050k", output)

    def test_parenthesized_xien_keeps_each_ticket_independent(self):
        raw = (
            "Xiên 2: (07.71)(07.64).(70.71).(70.17).(70.64).(21.17)."
            "(21.64).(12.71).(12.17).(12.64).(17.64).(71.64)=1triệu"
        )
        calculation = calculate(raw)
        self.assertFalse(calculation.rejected)
        entries = [entry for entry in calculation.entries if entry.kind == "Xiên 2"]
        self.assertEqual(len(entries), 12)
        self.assertTrue(all(entry.ticket_count == 1 for entry in entries))
        self.assertEqual(calculation.totals()["Xiên 2"][0], Decimal("12000"))
        self.assertEqual(entries[0].ticket_groups, (("07", "71"),))
        self.assertEqual(entries[-1].ticket_groups, (("71", "64"),))

    def test_parenthesized_xien_price_variants(self):
        variants = [
            "Xiên 2: (07.71)(07.64)=1triệu",
            "Xiên 2: (07.71)(07.64)=1triệu/1cặp",
            "Xiên: (07.71)(07.64) MC 1triệu",
            "Xiên: (07.71)(07.64) MC=1triệu",
            "Xiên: (07.71)(07.64) mỗi cặp x 1triệu",
            "Xiên: (07.71)(07.64) MCap b1tr",
        ]
        for raw in variants:
            with self.subTest(raw=raw):
                calculation = calculate(raw)
                self.assertFalse(calculation.rejected)
                self.assertEqual(calculation.totals()["Xiên 2"][0], Decimal("2000"))
                self.assertEqual(calculation.totals()["Xiên 2"][2], 2)

    def test_each_parenthesized_group_infers_its_own_xien_kind(self):
        calculation = calculate("Xiên: (07.71)(07.71.64)(07.71.64.21)=100")
        self.assertFalse(calculation.rejected)
        self.assertEqual(set(calculation.totals()), {"Xiên 2", "Xiên 3", "Xiên 4"})
        for kind in ("Xiên 2", "Xiên 3", "Xiên 4"):
            self.assertEqual(calculation.totals()[kind][0], Decimal("100"))

    def test_normal_xien_corrects_wrong_written_kind(self):
        cases = {
            "Xiên 2 07.71.64=100": "Xiên 3",
            "Xiên 3 07.71=100": "Xiên 2",
            "Xiên 3 07.71.64.21=100": "Xiên 4",
        }
        for raw, expected_kind in cases.items():
            with self.subTest(raw=raw):
                calculation = calculate(raw)
                self.assertFalse(calculation.rejected)
                self.assertEqual(list(calculation.totals()), [expected_kind])
                self.assertEqual(calculation.totals()[expected_kind][2], 1)

    def test_only_xien_quay_generates_combinations(self):
        variants = [
            "XQ2 00 11 22=100",
            "Xquay2 00 11 22=100",
            "Xquây2 00 11 22=100",
            "Xiên quay 2 00 11 22=100",
            "Xiên vòng 2 00 11 22=100",
        ]
        for raw in variants:
            with self.subTest(raw=raw):
                calculation = calculate(raw)
                self.assertFalse(calculation.rejected)
                entry = calculation.entries[0]
                self.assertEqual(entry.kind, "Xiên 2")
                self.assertEqual(entry.ticket_count, 3)
                self.assertEqual(
                    entry.ticket_groups,
                    (("00", "11"), ("00", "22"), ("11", "22")),
                )

    def test_money_spelling_variants(self):
        cases = {
            "Đề 01=1triệu": Decimal("1000"),
            "Đề 01=1trieu": Decimal("1000"),
            "Đề 01=1triệu500": Decimal("1500"),
            "Đề 01=1tr500": Decimal("1500"),
            "Đề 01=1,5tr": Decimal("1500"),
            "Đề 01=100nghìn": Decimal("100"),
            "Đề 01=100ngan": Decimal("100"),
            "Đề 01=10.000": Decimal("10000"),
            "Đề 01=100.000": Decimal("100000"),
            "Đề 01=1.000.000": Decimal("1000000"),
            "Đề 01=10.000k": Decimal("10000"),
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                calculation = calculate(raw)
                self.assertFalse(calculation.rejected)
                self.assertEqual(calculation.totals()["Đề"][0], expected)

    def test_attached_multiplication_sign_and_multiple_inline_entries(self):
        calculation = calculate("Đ 11×10k Đ 22x20k Đ 33b30k")
        self.assertFalse(calculation.rejected)
        self.assertEqual(calculation.totals()["Đề"][0], Decimal("60"))
        self.assertEqual(calculation.totals()["Đề"][2], 3)

    def test_stuck_dau_dit_and_multiline_shared_price(self):
        de = calculate("đầuđít2=50")
        self.assertFalse(de.rejected)
        self.assertEqual(de.totals()["Đề"][0], Decimal("1000"))
        self.assertEqual(de.entries[0].numbers.count("22"), 2)

        xien = calculate("X2:\n07 71\n07 64\nMC=100")
        self.assertFalse(xien.rejected)
        self.assertEqual(xien.totals()["Xiên 2"][0], Decimal("200"))
        self.assertEqual(len(xien.entries), 2)

        bao = calculate("Bao:\n12 02 20\n30 45 54\nMỗi số=1triệu500")
        self.assertFalse(bao.rejected)
        self.assertEqual(bao.totals()["Bao"][0], Decimal("9000"))

    def test_ambiguous_or_invalid_data_is_reported(self):
        invalid = [
            "Xiên 01.02.03.04.05=100",
            "Xiên 2 (07.07)=100",
            "Xquây2 07 07 71=100",
            "071764=100",
            "07.71.64 100",
            "Đề 01=100đ",
        ]
        for raw in invalid:
            with self.subTest(raw=raw):
                calculation = calculate(raw)
                self.assertFalse(calculation.entries)
                self.assertTrue(calculation.rejected)

    def test_repeated_written_xien_tickets_are_not_deduplicated(self):
        calculation = calculate("Xiên: (07.71)(07.71)(71.07)=100")
        self.assertFalse(calculation.rejected)
        self.assertEqual(len(calculation.entries), 3)
        self.assertEqual(calculation.totals()["Xiên 2"][0], Decimal("300"))

        result = LotteryResult("12-09-2026", "12300", ("07", "71") + tuple(f"{n:02d}" for n in range(25)), 0)
        output = format_settlement(calculation, result)
        self.assertIn("Trúng 3 lượt", output)
        self.assertIn("Tiền thưởng: 300k × 15 = 4.500k", output)

    def test_check_mode_format_does_not_need_lottery_result(self):
        output = format_check(calculate("Xiên: (07.71)(07.64)=100"))
        self.assertIn("🔍 KIỂM TRA VÉ", output)
        self.assertIn("Xiên 2 07-71", output)
        self.assertIn("Tất cả: 200k", output)
        self.assertIn("Không có dòng nào bị bỏ", output)

    def test_explicit_de_numbers_and_head_share_the_same_price(self):
        for raw in (
            "Đề: 88 99 và đầu 9 = 10k",
            "Đề: 88 99 đầu 9 = 10k",
        ):
            with self.subTest(raw=raw):
                calculation = calculate(raw)
                self.assertFalse(calculation.rejected)
                entry = calculation.entries[0]
                self.assertEqual(entry.ticket_count, 12)
                self.assertEqual(entry.stake, Decimal("120"))
                self.assertEqual(entry.numbers.count("99"), 2)

    def test_head_join_tail_cartesian_product_variants(self):
        variants = [
            "Đầu 1247 ghép đít 3689=5",
            "Đầu 1 2 4 7 ghép đít 3 6 8 9 =5",
            "Đầu 1,2,4,7 ghép đít 3,6,8,9=5",
            "Đầu 1247 ghép đít 3 689 x5",
            "dau 1247 ghep dit 3689=5",
        ]
        expected = {
            "13", "16", "18", "19", "23", "26", "28", "29",
            "43", "46", "48", "49", "73", "76", "78", "79",
        }
        for raw in variants:
            with self.subTest(raw=raw):
                calculation = calculate(raw)
                self.assertFalse(calculation.rejected)
                entry = calculation.entries[0]
                self.assertEqual(entry.ticket_count, 16)
                self.assertEqual(entry.stake, Decimal("80"))
                self.assertEqual(set(entry.numbers), expected)

        result = LotteryResult("12-09-2026", "12313", tuple(f"{n:02d}" for n in range(27)), 0)
        output = format_settlement(calculate(variants[0]), result)
        self.assertIn("Vốn: 80k", output)
        self.assertIn("Thưởng thực tế: 5k", output)
        self.assertIn("Trúng 1 lượt: 13", output)

    def test_kep_and_chap_are_the_same_ten_double_numbers(self):
        expected = ("00", "11", "22", "33", "44", "55", "66", "77", "88", "99")
        for raw in ("Kép=10", "Chập=10", "de kep x10", "Đề chập b10"):
            with self.subTest(raw=raw):
                calculation = calculate(raw)
                self.assertFalse(calculation.rejected)
                self.assertEqual(calculation.entries[0].numbers, expected)
                self.assertEqual(calculation.entries[0].stake, Decimal("100"))

    def test_compact_reversed_de_pairs_keep_palindrome_twice(self):
        calculation = calculate("Đề: 010.020.888 = 10k")
        self.assertFalse(calculation.rejected)
        entry = calculation.entries[0]
        self.assertEqual(entry.numbers, ("01", "10", "02", "20", "88", "88"))
        self.assertEqual(entry.ticket_count, 6)
        self.assertEqual(entry.stake, Decimal("60"))

        result = LotteryResult("12-09-2026", "12388", tuple(f"{n:02d}" for n in range(27)), 0)
        output = format_settlement(calculation, result)
        self.assertIn("Thưởng thực tế: 20k", output)
        self.assertIn("Trúng 2 lượt: 88 ×2", output)
        self.assertIn("Tiền thưởng: 20k × 90 = 1.800k", output)

    def test_de_dao_and_de_cap_keywords_expand_reverse_numbers(self):
        for raw in ("Đề đảo 01.88=10", "Đề cặp 01.88=10"):
            with self.subTest(raw=raw):
                calculation = calculate(raw)
                self.assertFalse(calculation.rejected)
                self.assertEqual(calculation.entries[0].numbers, ("01", "10", "88", "88"))
                self.assertEqual(calculation.entries[0].stake, Decimal("40"))

    def test_de_dao_and_de_cap_accept_arbitrary_compact_triplets(self):
        variants = (
            "Đề cap 010 999 555 924 = 10k",
            "Đề đảo 010 999 555 924 = 10k",
            "Đề đảo : 010 999 555 924 = 10k",
            "Đề đảo : 010.999.555.924 = 10k",
            "Đề cặp : 010.999.555.924 = 10k",
        )
        expected = ("01", "10", "99", "99", "55", "55", "92", "24")
        for raw in variants:
            with self.subTest(raw=raw):
                calculation = calculate(raw)
                self.assertFalse(calculation.rejected)
                self.assertEqual(calculation.entries[0].numbers, expected)
                self.assertEqual(calculation.entries[0].stake, Decimal("80"))

        five_triplets = calculate("Đề đảo : 010 999 555 924 876 = 10k")
        self.assertFalse(five_triplets.rejected)
        self.assertEqual(five_triplets.entries[0].numbers, expected + ("87", "76"))
        self.assertEqual(five_triplets.entries[0].stake, Decimal("100"))

    def test_de_multiline_with_numbers_after_label_on_same_line(self):
        body = (
            "02 20 03 06 07 08\n09 56 65 76 89 98 24\n42 08 05 50 06 07 70\n"
            "46 64 27 32 98 70 07\n77 88 99 55 01 10 02\n20 03 30 04 40 05 50\n"
            "28 82 29 92 26 62 24\n42 12 98 41 73 88 77\n55 27 72 22 69 89 98\n"
            "97 46 64 74 07 70 05\n50 29 92 55 99 19 18\n22 29 14 =20k/1số"
        )
        for raw in ("Đề: " + body, "Đề:\n" + body):
            with self.subTest(first_line=raw.splitlines()[0]):
                calculation = calculate(raw)
                self.assertFalse(calculation.rejected)
                self.assertEqual(calculation.totals()["Đề"][0], Decimal("1580"))
                self.assertEqual(calculation.totals()["Đề"][2], 79)

    def test_x_at_start_is_xien_not_money_separator(self):
        calculation = calculate("x 00 11 =10k")
        self.assertFalse(calculation.rejected)
        self.assertEqual(set(calculation.totals()), {"Xiên 2"})
        self.assertEqual(calculation.entries[0].numbers, ("00", "11"))
        self.assertEqual(calculation.entries[0].stake, Decimal("10"))

    def test_small_typo_proposes_confirmation_before_calculating(self):
        suggestion = propose_correction("Điit 8=25")
        self.assertIsNotNone(suggestion)
        self.assertEqual(suggestion.corrected, "Đít 8=25")
        self.assertEqual(suggestion.display, "Đít 8 = 25k")
        corrected = calculate(suggestion.corrected)
        self.assertFalse(corrected.rejected)
        self.assertEqual(corrected.totals()["Đề"][0], Decimal("250"))
        self.assertIsNone(propose_correction("Đề 88 99 và đầu 9=10"))

    def test_b_at_start_means_bao_but_price_b_still_works(self):
        cases = {
            "B 91 = 175k": (Decimal("175"), ("91",)),
            "B91=175k": (Decimal("175"), ("91",)),
            "B00,11,22=100k": (Decimal("300"), ("00", "11", "22")),
            "B:\n00 11 22\nMỗi số=100k": (Decimal("300"), ("00", "11", "22")),
            "Bao:\n91\nb175k": (Decimal("175"), ("91",)),
        }
        for raw, (stake, numbers) in cases.items():
            with self.subTest(raw=raw):
                calculation = calculate(raw)
                self.assertFalse(calculation.rejected)
                self.assertEqual(calculation.entries[0].kind, "Bao")
                self.assertEqual(calculation.entries[0].numbers, numbers)
                self.assertEqual(calculation.entries[0].stake, stake)

        de = calculate("Đề 00 b 50k")
        self.assertFalse(de.rejected)
        self.assertEqual(de.entries[0].kind, "Đề")
        self.assertEqual(de.entries[0].stake, Decimal("50"))

    def test_ambiguous_b_offers_bao_and_de_bo_without_corrupting_money(self):
        cases = {
            "B 91 = 175k": ("Bao 91 = 175k", "Đề bộ 91 = 175k"),
            "b 20 b 500k": ("Bao 20 = 500k", "Đề bộ 20 = 500k"),
            "B00,11,22=100k": ("Bao 00,11,22 = 100k", "Đề bộ 00,11,22 = 100k"),
            "B\n91=175k": ("Bao\n91 = 175k", "Đề bộ\n91 = 175k"),
            "B:\n91=175k": ("Bao:\n91 = 175k", "Đề bộ:\n91 = 175k"),
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                suggestion = propose_b_choice(raw)
                self.assertIsNotNone(suggestion)
                self.assertEqual(suggestion.bao_display, expected[0])
                self.assertEqual(suggestion.bo_display, expected[1])
                self.assertFalse(calculate(suggestion.bao_corrected).rejected)
                self.assertFalse(calculate(suggestion.bo_corrected).rejected)
                self.assertIsNone(propose_correction(raw))

        # Chữ b sau loại vé chỉ là dấu ghi giá, không được hỏi Bao/Đề bộ.
        self.assertIsNone(propose_b_choice("Đề 00 b 50k"))
        self.assertIsNone(propose_b_choice("Bao:\n91\nb175k"))

    def test_b_at_start_applies_bao_to_entire_long_message_and_keeps_thousands(self):
        raw = (
            "B 93.38=10.000 56=5000 52=4000 55.17=2000 32=3200 "
            "68=1600 76=1000 83=4200 38.83=1800 "
            "25,52,34,43,39,93,29,88,13,31=1500 56=3000"
        )
        suggestion = propose_b_choice(raw)
        self.assertIsNotNone(suggestion)
        calculation = calculate(suggestion.bao_corrected)
        self.assertFalse(calculation.rejected)
        self.assertEqual(len(calculation.entries), 11)
        self.assertTrue(all(entry.kind == "Bao" for entry in calculation.entries))
        self.assertEqual(calculation.entries[0].numbers, ("93", "38"))
        self.assertEqual(calculation.entries[0].unit_stake, Decimal("10000"))
        self.assertEqual(calculation.totals()["Bao"][0], Decimal("64600"))

    def test_all_de_bo_groups_are_complete_and_known_groups_match(self):
        self.assertEqual(len(DE_BO), 100)
        self.assertTrue(all(len(group) in (4, 8) for group in DE_BO.values()))
        self.assertTrue(all(len(group) == len(set(group)) for group in DE_BO.values()))
        expected = {
            "00": ("00", "05", "50", "55"),
            "01": ("01", "10", "06", "60", "51", "15", "56", "65"),
            "14": ("14", "41", "19", "91", "64", "46", "69", "96"),
            "44": ("44", "49", "94", "99"),
            "99": ("99", "94", "49", "44"),
        }
        for code, numbers in expected.items():
            self.assertEqual(DE_BO[code], numbers)

    def test_de_bo_input_variants_expand_and_keep_overlapping_tickets(self):
        for raw in ("Đề bộ 00=10k", "Đề bo 00=10k", "Bộ 00=10k", "Bộ00=10k", "Bộ:\n00\n=10k"):
            with self.subTest(raw=raw):
                calculation = calculate(raw)
                self.assertFalse(calculation.rejected)
                self.assertEqual(calculation.entries[0].numbers, ("00", "05", "50", "55"))
                self.assertEqual(calculation.entries[0].stake, Decimal("40"))

        overlap = calculate("Bộ 00,05=10k")
        self.assertFalse(overlap.rejected)
        self.assertEqual(overlap.entries[0].ticket_count, 8)
        self.assertEqual(overlap.entries[0].stake, Decimal("80"))
        self.assertEqual(overlap.entries[0].numbers.count("00"), 2)

    def test_de_bo_rejects_codes_that_are_not_two_digits(self):
        for raw in ("Bộ 1=10k", "Bộ 100=10k", "Bộ=10k"):
            with self.subTest(raw=raw):
                calculation = calculate(raw)
                self.assertFalse(calculation.entries)
                self.assertTrue(calculation.rejected)

    def test_de_bo_uses_normal_de_reward_and_explicit_display(self):
        calculation = calculate("Bộ 00=10k")
        result = LotteryResult("13-09-2026", "12000", tuple(f"{n:02d}" for n in range(27)), 0)
        output = format_settlement(calculation, result)
        self.assertIn("Đề bộ 00 → 00, 05, 50, 55", output)
        self.assertIn("ĐỀ BỘ 00", output)
        self.assertIn("Vốn: 40k", output)
        self.assertIn("Thưởng thực tế: 10k", output)
        self.assertIn("Tiền thưởng: 10k × 90 = 900k", output)

    def test_cang_aliases_and_multiline_keep_three_digits(self):
        variants = (
            "C 851=10k", "C851=10k", "Càng 851=10k", "Càg 851=10k",
            "Ba càng 851=10k", "bacang851=10k", "C:\n851\n=10k",
        )
        for raw in variants:
            with self.subTest(raw=raw):
                calculation = calculate(raw)
                self.assertFalse(calculation.rejected)
                self.assertEqual(calculation.entries[0].kind, "Càng")
                self.assertEqual(calculation.entries[0].numbers, ("851",))
                self.assertEqual(calculation.entries[0].stake, Decimal("10"))

        leading_zero = calculate("C 051.151.251=10k")
        self.assertFalse(leading_zero.rejected)
        self.assertEqual(leading_zero.entries[0].numbers, ("051", "151", "251"))
        self.assertEqual(leading_zero.entries[0].stake, Decimal("30"))

    def test_cang_rejects_non_three_digit_tickets(self):
        for raw in ("C 51=10k", "C 8512=10k", "C abc=10k"):
            with self.subTest(raw=raw):
                calculation = calculate(raw)
                self.assertFalse(calculation.entries)
                self.assertTrue(calculation.rejected)

    def test_cang_exact_ticket_does_not_receive_apply_reward(self):
        raw = "C 051.151.251.351.451.551.651.751.851.951=10k"
        calculation = calculate(raw)
        result = LotteryResult("13-09-2026", "12851", tuple(f"{n:02d}" for n in range(27)), 0)
        output = format_settlement(calculation, result)
        self.assertIn("Vốn: 100k", output)
        self.assertIn("🏆 ĐẶC BIỆT CÀNG", output)
        self.assertIn("Trúng 1 lượt: 851", output)
        self.assertIn("10k × 400 = 4.000k", output)
        self.assertIn("🎯 ÁP CÀNG", output)
        self.assertIn("Trúng 9 lượt: 051, 151, 251, 351, 451, 551, 651, 751, 951", output)
        self.assertIn("90k × 10 = 900k", output)
        self.assertIn("💰 TỔNG THƯỞNG: 4.900k", output)
        self.assertNotIn("100k × 10", output)

    def test_exact_screenshot_cases(self):
        choice = propose_b_choice("b 91 = 150k")
        self.assertIsNotNone(choice)
        self.assertEqual(choice.bao_display, "Bao 91 = 150k")
        self.assertEqual(choice.bo_display, "Đề bộ 91 = 150k")

        calculation = calculate("C 851=500k")
        result = LotteryResult("12-09-2026", "58851", tuple(f"{n:02d}" for n in range(27)), 0)
        output = format_settlement(calculation, result)
        self.assertIn("500k × 400 = 200.000k", output)
        self.assertIn("Áp càng: Không trúng", output)
        self.assertIn("💰 TỔNG THƯỞNG: 200.000k", output)
        self.assertNotIn("500k × 10", output)

    def test_separator_lines_and_per_number_suffixes(self):
        raw = """Đề 85,40=100k/1số
——————
Đề:
60 04 07
MỗiSố=170k/1so
——————"""
        calculation = calculate(raw)
        self.assertFalse(calculation.rejected)
        self.assertEqual([entry.ticket_count for entry in calculation.entries], [2, 3])
        self.assertEqual(sum((entry.stake for entry in calculation.entries), Decimal("0")), Decimal("710"))

    def test_slash_price_marker_only_when_followed_by_money_unit(self):
        calculation = calculate("Đít 3/450k\nĐề 00/50k")
        self.assertFalse(calculation.rejected)
        self.assertEqual(calculation.entries[0].ticket_count, 10)
        self.assertEqual(calculation.entries[0].stake, Decimal("4500"))
        self.assertEqual(calculation.entries[1].stake, Decimal("50"))

    def test_completed_assignments_are_not_read_as_decimal_money(self):
        calculation = calculate("Đề 00=100.20=300.15=100.98=50")
        self.assertFalse(calculation.rejected)
        self.assertEqual(
            [(entry.numbers, entry.unit_stake) for entry in calculation.entries],
            [(('00',), Decimal('100')), (('20',), Decimal('300')), (('15',), Decimal('100')), (('98',), Decimal('50'))],
        )

    def test_dotted_thousands_are_preserved(self):
        calculation = calculate("00 = 4.650k\n01 = 2.290k\n22 = 2.750k")
        self.assertFalse(calculation.rejected)
        self.assertEqual([entry.unit_stake for entry in calculation.entries], [
            Decimal("4650"), Decimal("2290"), Decimal("2750"),
        ])

    def test_cham_and_bo_trung_variants(self):
        for raw in (
            "Chạm 0,5x30 (bỏ trùng)",
            "Cham 0,5x30 bo trung",
            "Chạm 0,5 (không trùng) x30",
            "Chạm 0,5x30 lọc trùng",
            "Chạm 0,5x30 loại trùng",
            "Chạm 0,5x30 k trùng",
        ):
            with self.subTest(raw=raw):
                calculation = calculate(raw)
                self.assertFalse(calculation.rejected)
                self.assertEqual(calculation.entries[0].ticket_count, 36)
                self.assertEqual(calculation.entries[0].stake, Decimal("1080"))
        self.assertEqual(calculate("Chạm 0,5x30").entries[0].ticket_count, 38)
        self.assertIsNone(propose_correction("Chạm 0,5x30 (bỏ trùng)"))

    def test_latest_de_formats_keep_their_exact_ticket_rules(self):
        total_high = calculate("Đề tổng cao=10")
        self.assertFalse(total_high.rejected)
        self.assertEqual(total_high.entries[0].ticket_count, 50)

        two_sets = calculate("Dàn 36,44x10")
        self.assertFalse(two_sets.rejected)
        self.assertEqual(two_sets.entries[0].ticket_count, 80)

        pairs = calculate("Đề 070 353 924=10")
        self.assertFalse(pairs.rejected)
        self.assertEqual(pairs.entries[0].numbers, ("07", "70", "35", "53", "92", "24"))

    def test_full_real_message_with_bo_trung_is_fully_understood(self):
        raw = """De đầu 6,8,9x100,
Dit 1 dau 0,6=10
ĐẦU 5,7,8,0=50
De 36.66.83x20
05=50
03-06-83-86=30
đuôi 3,6=30
Đ
Dàn 36 ,44 x40k
đầu 7-0=30
22,33=70
98,15,45,05,50=30
Đầu 0.4.8=20
45,75.54=20
Chạm 0,5x30 ( bỏ trùng )
Đ
36.66.83x20
05=50
03-06-83-86=30
đuôi 3,6=30"""
        calculation = calculate(raw)
        self.assertFalse(calculation.rejected)
        self.assertEqual(len(calculation.entries), 18)
        self.assertEqual(sum((entry.stake for entry in calculation.entries), Decimal("0")), Decimal("12790"))


if __name__ == "__main__":
    unittest.main()
