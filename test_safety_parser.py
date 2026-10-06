"""Golden money/list fixtures and explicit no-guess boundaries (unit: k)."""
import unittest
from decimal import Decimal
from calculator import calculate, parse_money, normalize, propose_b_choice, DAN_KEP_LECH

class GoldenTests(unittest.TestCase):
    def assert_ticket(self, raw, numbers, unit):
        c = calculate(raw)
        self.assertFalse(c.rejected, c.rejected)
        self.assertEqual(len(c.entries), 1)
        self.assertEqual(c.entries[0].numbers, tuple(numbers))
        self.assertEqual(c.entries[0].unit_stake, Decimal(unit))
        self.assertEqual(c.entries[0].stake, Decimal(unit) * len(numbers))

    def test_A37(self):
        c = calculate('Đề 86.89.80 bang 230 k 98 bang 550 k')
        self.assertFalse(c.rejected)
        self.assertEqual([(e.numbers,e.unit_stake) for e in c.entries],
                         [(('86','89','80'),Decimal(230)),(('98',),Decimal(550))])
        self.assertEqual(c.totals()['Đề'][0], Decimal(1240))

    def test_A50(self):
        raw='Đề 89,98,99,11,94,84,80,87,78,88,24,69,68,67,76,64,46,66,60,06,89,98,90,95,9497 79 = 20'
        expected='89 98 99 11 94 84 80 87 78 88 24 69 68 67 76 64 46 66 60 06 89 98 90 95 94 97 79'.split()
        self.assert_ticket(raw, expected, '20')

    def test_A91(self):
        self.assert_ticket('Đề dau 1.6.2.7.3.8 ghep dit 1.6.2.7.3.8 bang 50',
                           [a+b for a in '162738' for b in '162738'], '50')

    def test_A128(self):
        self.assert_ticket('Đề tu dau 3 den 8 ghep dit 3 den 8 = 50',
                           [a+b for a in '345678' for b in '345678'], '50')

    def test_A132(self):
        c=calculate('Đề dau 345678 ghep dit 345678 bg550 56.88 = 100')
        self.assertFalse(c.rejected)
        self.assertEqual([e.numbers for e in c.entries],
                         [tuple(a+b for a in '345678' for b in '345678'),('56','88')])
        self.assertEqual([e.unit_stake for e in c.entries],[Decimal(550),Decimal(100)])
        self.assertEqual(c.totals()['Đề'][0],Decimal(20000))

    def test_A155(self):
        c=calculate('Đề dau,dit 0 = 30')
        old=calculate('Đề đầu đít 0=30')
        self.assertFalse(c.rejected)
        self.assertEqual(c.entries[0].numbers,old.entries[0].numbers)
        self.assertEqual(c.entries[0].numbers.count('00'),2)
        self.assertEqual(c.entries[0].stake,Decimal(600))

    def test_joined_8968(self):
        self.assert_ticket('Đề 83,84,8968 98 = 50n',['83','84','89','68','98'],'50')

    def test_zero_price(self):
        c=calculate('Đề 47.74.07.81.18.70.27.28.22.11.66 = 00')
        self.assertFalse(c.entries)
        self.assertTrue(c.rejected)

    def test_palindrome_frozen_two_tickets(self):
        self.assert_ticket('Đề cặp 88=10',['88','88'],'10')

    def test_ABC_pair_context(self):
        self.assert_ticket('Đề cặp 924=10',['92','24'],'10')

    def test_legacy_ABC_without_keyword_conflict_frozen(self):
        # Existing tests explicitly require this. No silent business change.
        self.assert_ticket('Đề 070 353 924=10',['07','70','35','53','92','24'],'10')

    def test_head_dash_is_separator_not_range(self):
        c=calculate('đầu 7-0=30')
        self.assertFalse(c.rejected)
        self.assertEqual(c.entries[0].ticket_count,20)

    def test_existing_chap_kep_cham(self):
        for name in ('chập','kép'):
            self.assert_ticket('Đề '+name+'=10',[str(n)*2 for n in range(10)],'10')
        self.assert_ticket('Đề kép lệch=10',DAN_KEP_LECH,'10')
        c=calculate('Đề chạm 0=10')
        self.assertFalse(c.rejected)
        self.assertEqual(c.entries[0].ticket_count,19)

    def test_b_choice_two_valid_interpretations(self):
        for raw in ('B91=175k','b20b500k'):
            choice=propose_b_choice(raw)
            self.assertIsNotNone(choice)
            bao=calculate(choice.bao_corrected);bo=calculate(choice.bo_corrected)
            self.assertFalse(bao.rejected);self.assertFalse(bo.rejected)
            self.assertNotEqual(bao.entries[0].stake,bo.entries[0].stake)

    def test_alias_normalization_is_stable(self):
        for raw in ('Đề 66 bảng 100 68=500','Đề 66 bàng 100 68=500'):
            text=normalize(raw)
            self.assertEqual(normalize(text),text)
            self.assertTrue(calculate(raw).rejected)

class MoneyTests(unittest.TestCase):
    pass

def money_test(raw, expected):
    def test(self):
        self.assertEqual(parse_money(raw),Decimal(expected))
        c=calculate('Đề 12='+raw)
        self.assertFalse(c.rejected,c.rejected)
        self.assertEqual(c.entries[0].stake,Decimal(expected))
    return test

for i,(raw,expected) in enumerate([
    ('1tr','1000'),('1tr5','1500'),('1tr500','1500'),('1,5tr','1500'),('1.5tr','1500'),
    ('1triệu','1000'),('1triệu500','1500'),('100nghìn','100'),('100ngan','100'),
    ('100n','100'),('10.000','10000'),('1tr050','1050'),
    ('100000000000000000000000000001','100000000000000000000000000001'),
]):
    setattr(MoneyTests,'test_money_'+str(i),money_test(raw,expected))

class NegativeTests(unittest.TestCase):
    pass

def negative_test(raw):
    def test(self):
        self.assertTrue(calculate(raw).rejected,raw)
    return test

for i,raw in enumerate([
    'Đề 66 bảng 100 68=500','9497','9497=50','Đề 66 1000 68=50','Đề 123 4567=50',
    'đầu 8 đến 3=50','Đề đầu 8 đến 3 ghép đít 3 đến 8=50', 'Đề 12=00',
    'Đề cặp 9497=50','Đề 12=1tr50','Đề 12=1tr5000','Đề 12=1.5tr5',
    'Đề 12=1tr5abc','Đề 12=10k nội dung chưa hiểu', 'ghi chú Đề 12=10k',
    'Bao 12 abc 34=10','Xiên 12 34 abc=10','Xiên 12 34 1234=10',
    'Đề kép bỏ kép lệch=10','Đề chập bỏ chập=10','Đề kép bỏ sát kép=10',
    'Đề sát chập=10','Đề sát kép=10','Dàn 48=10','Đề tổng chẵn xyz=10',
    'Đề dàn 36 xyz=10','Đề đầu cao xyz=10','Đề đầu 1&2 ghép đít 3=10',
    'Đề đầu 1+2 ghép đít 3=10',
    'Đề 3 đến 8=50','Đề dàn 36 & =10','Đề kép lệch +=10',
    'Đề 12='+('9'*90),
]):
    setattr(NegativeTests,'test_reject_'+str(i),negative_test(raw))

class AliasTests(unittest.TestCase):
    def test_exact_price_aliases(self):
        for alias in ('bằng','bang','băng','bg'):
            c=calculate('Đề 12 '+alias+' 100 k')
            self.assertFalse(c.rejected)
            self.assertEqual(c.entries[0].stake,Decimal(100))

if __name__=='__main__':unittest.main()
