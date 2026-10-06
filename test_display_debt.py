"""Approved view/debt regression. Lottery fixtures are not live verification."""
import json
import sqlite3
from contextlib import closing
import tempfile
import unittest
from decimal import Decimal
from unittest.mock import patch
from accounting import Ledger, totals, stored_entries
from presentation import render_summary, render_book, display_k
from results import LotteryResult

DAY='06-10-2026'
RESULT=LotteryResult(DAY,'12312',tuple(['12','12','34','56','78']+['00']*22),0)

class DisplayDebtTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=Ledger(self.tmp.name+'/db')
        self.pid=self.db.create(1,'Khách','HUO')
        self.db.configure(1,self.pid,'percent','0;0;0;0;0')
        self.mid=0
    def tearDown(self):self.tmp.cleanup()
    def add(self,text):
        self.mid+=1
        self.db.add(1,self.pid,DAY,self.mid,text)
        return self.rows()[-1]
    def rows(self):return self.db.tickets(1,self.pid,DAY)
    def profile(self):return self.db.profile(1,self.pid)
    def view(self,result=RESULT):return render_summary(self.profile(),DAY,self.rows(),result)
    def debt(self,value):self.db.set_old_balance(1,self.pid,value)

    def test_half_up_whole_k(self):
        for value,want in [('453.5','454k'),('16.8','17k'),('1265.4','1.265k'),('1970.7','1.971k')]:
            self.assertEqual(display_k(Decimal(value)),want)
    def test_new_format_only_nonzero_goods(self):
        self.db.configure(1,self.pid,'percent','5;0;0;0;0');self.add('Đề 99=9070')
        text=self.view()
        self.assertIn('Khách HUO — 06-10-2026\n1 tin',text)
        self.assertIn('- Đề: 9.070k | % 454k |',text)
        self.assertNotIn('- Bao:',text);self.assertNotIn('thưởng 0k',text);self.assertNotIn('hàng 9.070k;',text)
    def test_balance_uses_original_cut(self):
        self.db.configure(1,self.pid,'percent','5;0;0;0;0');self.add('Đề 99=11')
        self.assertIn('% 1k',self.view());self.assertIn('THU HUO: 10k',self.view())
        self.assertEqual(totals(self.rows(),RESULT)['Đề'][1],Decimal('.55'))
    def test_exact_requested_totals(self):
        self.add('Đề 99=10');rows=self.rows()
        # Isolated presentation fixture for the user's arithmetic example; not a live result.
        with patch('presentation.totals',return_value={'Đề':[Decimal('16480'),Decimal('1970.7'),Decimal('2625')]}),patch('presentation._reward_lines',return_value=(['Bao: 2.625k'],Decimal('2625'))):
            text=render_summary(self.profile(),DAY,rows,RESULT)
        self.assertIn('Tổng hàng: 16.480k | Trừ %: 1.971k',text)
        self.assertIn('Tổng thưởng: 2.625k',text);self.assertTrue(text.endswith('THU HUO: 11.884k'))
    def test_no_reward(self):
        self.add('Đề 99=10');self.assertIn('THƯỞNG: Không có',self.view())
    def test_de_reward_payout(self):
        self.add('Đề 12=10');self.assertIn('\nĐề: 900k',self.view());self.assertIn('Tổng thưởng: 900k',self.view())
    def test_bao_multi_hit_payout(self):
        self.add('Bao 12=10');self.assertIn('\nBao: 70k',self.view());self.assertIn('Tổng thưởng: 70k',self.view())
    def test_x2_15_payout(self):
        self.add('X 12-34=10');self.assertIn('X2 ×15: 150k',self.view())
    def test_x2_14_snapshot_and_payout(self):
        self.db.select_variant(1,self.pid,'14');self.db.configure(1,self.pid,'percent','0;0;0;0;0');self.add('X 12-34=10')
        self.db.select_variant(1,self.pid,'15');self.assertIn('X2 ×14: 140k',self.view())
    def test_x3_base_and_payout(self):
        self.add('X3 12-34-56=20');text=self.view()
        self.assertIn('X3: 20k (gốc ×48 = 960k tính vào tổng thưởng)',text);self.assertIn('Tổng thưởng: 960k',text)
    def test_x4_payout(self):
        self.add('X4 12-34-56-78=10');self.assertIn('X4: 1.800k',self.view())
    def test_ap_base_and_payout(self):
        self.add('Càng 412=50');text=self.view()
        self.assertIn('AC: 50k (gốc ×10 = 500k tính vào tổng thưởng)',text);self.assertIn('Tổng thưởng: 500k',text);self.assertNotIn('\nC:',text)
    def test_exact_cang_no_ap(self):
        self.add('Càng 312=10');text=self.view()
        self.assertIn('\nC: 4.000k',text);self.assertNotIn('\nAC:',text);self.assertIn('Tổng thưởng: 4.000k',text)
    def test_reward_original_snapshot_factor(self):
        self.add('X3 12-34-56=20');self.db.configure(1,self.pid,'reward','90;75;15;49;180;400;10')
        self.assertIn('gốc ×48 = 960k',self.view())
    def test_wrong_result_day_rejected(self):
        self.add('Đề 99=10')
        with self.assertRaises(ValueError):self.view(LotteryResult('05-10-2026',RESULT.special_full,RESULT.loto,0))
    def test_without_result_no_settlement(self):
        self.add('Đề 99=10');self.debt('THU 100')
        text=self.view(None);self.assertIn('Chưa chốt',text);self.assertNotIn('THU HUO:',text)
    def test_reward_display_mismatch_rejects(self):
        self.add('Đề 12=10')
        with patch('presentation._reward_lines',return_value=([],Decimal(0))),self.assertRaises(ValueError):self.view()
    def test_book_reads_snapshot_not_raw(self):
        row=self.add('Đề 99=100');row['raw']='RAW MUST NEVER APPEAR'
        with patch('accounting.calculate',side_effect=AssertionError('must not parse')):
            text=render_book(self.profile(),DAY,[row]);summary=render_summary(self.profile(),DAY,[row],RESULT)
        self.assertIn('Đề: 100k',text);self.assertNotIn('RAW MUST',text+summary)
    def test_book_all_columns(self):
        self.add('Đề 99=100\nBao 98=200\nX 12-34=10\nX3 12-34-56=20\nX4 12-34-56-78=30\nCàng 999=40')
        text=render_book(self.profile(),DAY,self.rows())
        for expected in ['Đề: 100k','Bao: 200k','X2: 10k ×15','X3: 20k','X4: 30k','Càng: 40k']:self.assertIn(expected,text)
    def test_book_missing_columns_dash(self):
        self.add('Đề 99=100');text=render_book(self.profile(),DAY,self.rows());self.assertIn('Bao: -',text);self.assertIn('X2: -',text)
    def test_book_variant_each_snapshot(self):
        self.add('X 12-34=500');self.db.select_variant(1,self.pid,'14');self.db.configure(1,self.pid,'percent','0;0;0;0;0');self.add('X 12-34=200')
        text=render_book(self.profile(),DAY,self.rows());self.assertIn('500k ×15',text);self.assertIn('200k ×14',text)
    def test_book_edit_uses_new_entry_snapshot(self):
        row=self.add('Đề 99=100');self.db.replace(1,self.pid,DAY,row['id'],'Bao 98=200')
        text=render_book(self.profile(),DAY,self.rows());self.assertIn('Bao: 200k',text);self.assertIn('Đề: -',text)
    def test_book_deleted_excluded_and_raw_retained(self):
        row=self.add('Đề 99=100');self.db.delete(1,self.pid,DAY,row['id'])
        deleted=self.db.query('SELECT * FROM tickets');text=render_book(self.profile(),DAY,deleted)
        self.assertNotIn('ID ',text);self.assertEqual(deleted[0]['raw'],'Đề 99=100')
    def test_book_missing_snapshot_rejects(self):
        row=self.add('Đề 99=100');row['entries_snapshot']=None
        with self.assertRaises(ValueError):render_book(self.profile(),DAY,[row])
    def test_book_wrong_owner_rejects(self):
        row=self.add('Đề 99=100');row['owner']=2
        with self.assertRaises(ValueError):render_book(self.profile(),DAY,[row])
    def test_book_wrong_day_rejects(self):
        row=self.add('Đề 99=100');row['day']='05-10-2026'
        with self.assertRaises(ValueError):render_book(self.profile(),DAY,[row])
    def test_default_debt_zero(self):self.assertEqual(self.profile()['old_balance'],'0')
    def test_debt_thu_signed(self):self.debt('THU 2356');self.assertEqual(self.profile()['old_balance'],'2356')
    def test_debt_tra_signed(self):self.debt('TRẢ 2356');self.assertEqual(self.profile()['old_balance'],'-2356')
    def test_debt_replace_not_add(self):self.debt('THU 100');self.debt('THU 200');self.assertEqual(self.profile()['old_balance'],'200')
    def test_debt_same_direction(self):
        self.add('Đề 99=11884');self.debt('THU 2356');self.assertTrue(self.view().endswith('THU HUO: 14.240k'))
    def test_debt_opposite_direction(self):
        self.add('Đề 99=11884');self.debt('TRẢ 2000');self.assertTrue(self.view().endswith('THU HUO: 9.884k'))
    def test_debt_changes_sign(self):
        self.add('Đề 99=100');self.debt('TRẢ 200');self.assertTrue(self.view().endswith('TRẢ HUO: 100k'))
    def test_debt_exact_cancellation(self):
        self.add('Đề 99=100');self.debt('TRẢ 100');self.assertTrue(self.view().endswith('Cân bằng: không thu/trả.'))
    def test_debt_master_admin_direction(self):
        self.add('Đề 99=100');p=self.profile();p['side']='Chủ';p['old_balance']='200'
        self.assertTrue(render_summary(p,DAY,self.rows(),RESULT).endswith('THU HUO: 100k'))
    def test_zero_debt_hidden(self):self.add('Đề 99=100');self.assertNotIn('Nợ cũ',self.view())
    def test_debt_fraction_not_float_or_rounded_before_net(self):
        self.db.configure(1,self.pid,'percent','5;0;0;0;0');self.add('Đề 99=11');self.debt('THU 0,1');self.assertTrue(self.view().endswith('THU HUO: 11k'));self.assertEqual(self.profile()['old_balance'],'0.1')
    def test_debt_owner_isolation(self):
        with self.assertRaises(ValueError):self.db.set_old_balance(2,self.pid,'THU 100')
        self.assertEqual(self.profile()['old_balance'],'0');self.assertFalse(self.db.query('SELECT * FROM balance_audit'))
    def test_debt_profile_isolation(self):
        other=self.db.create(1,'Chủ','HUO');self.debt('THU 100');self.assertEqual(self.db.profile(1,other)['old_balance'],'0')
    def test_debt_audit_and_snapshot_unchanged(self):
        self.add('Đề 99=100');before=self.rows();self.debt('THU 100');self.debt('TRẢ 20');audit=self.db.query('SELECT * FROM balance_audit ORDER BY id')
        self.assertEqual((audit[1]['old_amount'],audit[1]['new_amount'],audit[1]['actor']),('100','-20',1));self.assertTrue(audit[1]['at']);self.assertEqual(self.rows(),before)
    def test_debt_invalid_ambiguous_reject(self):
        for value in ['2356','THU 2.356','TRẢ -20','THU NaN','THU 1e3','THU 1\nTRẢ 2']:
            with self.assertRaises(ValueError):self.debt(value)
        self.assertEqual(self.profile()['old_balance'],'0')
    def test_debt_reset_zero(self):self.debt('THU 100');self.debt('0');self.assertEqual(self.profile()['old_balance'],'0')
    def test_migration_old_db_preserves_rows(self):
        path=self.tmp.name+'/legacy'
        cfg=json.dumps(self.profile()['config'])
        with closing(sqlite3.connect(path)) as c:
            with c:
                c.execute('CREATE TABLE profiles(id INTEGER PRIMARY KEY,owner INTEGER,side TEXT,name TEXT,config TEXT)')
                c.execute('INSERT INTO profiles VALUES(1,1,?,?,?)',('Khách','Legacy',cfg))
        old=Ledger(path);self.assertEqual(old.profile(1,1)['old_balance'],'0');old.set_old_balance(1,1,'THU 25')
        self.assertEqual(Ledger(path).profile(1,1)['old_balance'],'25')

if __name__=='__main__':unittest.main()
