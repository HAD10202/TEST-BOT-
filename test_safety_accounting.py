import json
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from unittest.mock import patch
from accounting import Ledger, totals, summary
from results import LotteryResult

DAY='06-10-2026'

class DataSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=Ledger(self.tmp.name+'/db')
        self.pid=self.db.create(1,'Khách','A')
        self.db.configure(1,self.pid,'percent','0;0;0;0;0')
        self.result=LotteryResult(DAY,'12312',('12','12','34','56','78')+('00',)*22,0)
    def tearDown(self):self.tmp.cleanup()
    def add(self,raw,message=1):
        self.db.add(1,self.pid,DAY,message,raw)
        return self.db.tickets(1,self.pid,DAY)

    def test_b_not_saved_before_choice(self):
        for raw in ('B91=175k','b20b500k'):
            with self.assertRaises(ValueError):self.add(raw)
            self.assertEqual(self.db.tickets(1,self.pid,DAY),[])

    def test_independent_partial_is_visible_but_not_saved(self):
        with self.assertRaises(ValueError) as error:
            self.add('Đề 12=10\nBao chưa rõ')
        self.assertIn('CHƯA LƯU TOÀN BỘ',str(error.exception))
        self.assertIn('Đã hiểu',str(error.exception))
        self.assertIn('Chưa hiểu',str(error.exception))
        self.assertIn('10k',str(error.exception))
        self.assertFalse(self.db.tickets(1,self.pid,DAY))

    def test_unknown_tail_never_saved(self):
        with self.assertRaises(ValueError):self.add('Đề 12=10 còn 34 chưa có giá')
        self.assertFalse(self.db.tickets(1,self.pid,DAY))

    def test_money_shorthand_stored_as_1500(self):
        self.assertEqual(totals(self.add('Đề 12=1tr5'))['Đề'][0],Decimal(1500))

    def test_snapshot_parser_never_reparses_old_ticket(self):
        rows=self.add('Đề 12=10')
        with patch('accounting.calculate',side_effect=AssertionError('must not reparse')):
            self.assertEqual(totals(rows,self.result)['Đề'][2],Decimal(900))

    def test_config_snapshot_and_edit_keeps_original_percent(self):
        self.db.configure(1,self.pid,'percent','5;0;0;0;0')
        rows=self.add('Đề 12=10')
        self.db.configure(1,self.pid,'percent','20;0;0;0;0')
        self.db.replace(1,self.pid,DAY,rows[0]['id'],'Đề 34=20')
        rows=self.db.tickets(1,self.pid,DAY)
        self.assertEqual(totals(rows)['Đề'][1],Decimal(1))

    def test_duplicate_delivery_is_atomic(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            saved=list(pool.map(lambda _:self.db.add(1,self.pid,DAY,100,'Đề 12=10'),range(8)))
        self.assertEqual(saved.count(True),1)
        self.assertEqual(len(self.db.tickets(1,self.pid,DAY)),1)

    def test_edit_audit_and_failure_is_atomic(self):
        tid=self.add('Đề 12=10')[0]['id']
        self.db.replace(1,self.pid,DAY,tid,'Đề 34=20')
        audit=self.db.query('SELECT * FROM ticket_audit')[0]
        self.assertEqual((audit['old_raw'],audit['new_raw'],audit['actor'],audit['action']),
                         ('Đề 12=10','Đề 34=20',1,'edit'))
        self.assertTrue(audit['at'])
        for raw in ('Đề 34=00','B91=175k','Đề 66 bảng 100 68=500'):
            with self.assertRaises(ValueError):self.db.replace(1,self.pid,DAY,tid,raw)
        self.assertEqual(self.db.tickets(1,self.pid,DAY)[0]['raw'],'Đề 34=20')
        self.assertEqual(len(self.db.query('SELECT * FROM ticket_audit')),1)

    def test_soft_delete_audit_and_no_duplicate_resurrection(self):
        tid=self.add('Đề 12=10')[0]['id']
        self.db.delete(1,self.pid,DAY,tid)
        self.assertFalse(self.db.tickets(1,self.pid,DAY))
        row=self.db.query('SELECT * FROM tickets')[0]
        self.assertTrue(row['deleted_at']);self.assertEqual(row['raw'],'Đề 12=10')
        audit=self.db.query('SELECT * FROM ticket_audit')[0]
        self.assertEqual((audit['old_raw'],audit['new_raw'],audit['actor'],audit['action']),
                         ('Đề 12=10',None,1,'delete'))
        self.assertFalse(self.db.add(1,self.pid,DAY,1,'Đề 12=10'))
        self.assertEqual(totals([row])['Đề'][0],Decimal(0))
        with self.assertRaises(ValueError):self.db.replace(1,self.pid,DAY,tid,'Đề 12=20')

    def test_owner_profile_day_isolation(self):
        tid=self.add('Đề 12=10')[0]['id']
        other=self.db.create(1,'Chủ','B')
        for owner,pid,day in ((2,self.pid,DAY),(1,other,DAY),(1,self.pid,'05-10-2026')):
            with self.assertRaises(ValueError):self.db.delete(owner,pid,day,tid)
            with self.assertRaises(ValueError):self.db.replace(owner,pid,day,tid,'Đề 34=20')
        self.assertEqual(len(self.db.tickets(1,self.pid,DAY)),1)
        self.assertFalse(self.db.query('SELECT * FROM ticket_audit'))

    def test_result_wrong_day_blocked_in_totals_and_summary(self):
        rows=self.add('Đề 12=10')
        wrong=LotteryResult('05-10-2026',self.result.special_full,self.result.loto,0)
        with self.assertRaises(ValueError):totals(rows,wrong)
        with self.assertRaises(ValueError):summary(self.db.profile(1,self.pid),DAY,rows,wrong)

    def test_malformed_result_blocked(self):
        rows=self.add('Bao 12=10')
        for result in (LotteryResult(DAY,'12312',('12',),0),
                       LotteryResult(DAY,'12',self.result.loto,0),
                       LotteryResult(DAY,'12312',('00',)*27,0)):
            with self.assertRaises(ValueError):totals(rows,result)

    def test_legacy_database_migration_blocks_reinterpretation(self):
        path=self.tmp.name+'/old'
        with sqlite3.connect(path) as c:
            c.execute('CREATE TABLE tickets(id INTEGER PRIMARY KEY, owner INTEGER NOT NULL,profile INTEGER NOT NULL,day TEXT NOT NULL,message INTEGER NOT NULL,raw TEXT NOT NULL,config TEXT NOT NULL,UNIQUE(owner,message))')
            cfg=json.dumps(self.db.profile(1,self.pid)['config'])
            c.execute('INSERT INTO tickets VALUES(1,1,1,?,1,?,?)',(DAY,'Đề 12=1tr5',cfg))
        old=Ledger(path)
        pid=old.create(1,'Khách','A')
        rows=old.tickets(1,pid,DAY)
        self.assertEqual(rows[0]['raw'],'Đề 12=1tr5')
        self.assertIsNone(rows[0]['entries_snapshot'])
        with self.assertRaises(ValueError):totals(rows)
        old.replace(1,pid,DAY,1,'Đề 12=1tr5')
        self.assertEqual(totals(old.tickets(1,pid,DAY))['Đề'][0],Decimal(1500))
        self.assertEqual(len(old.query('SELECT * FROM ticket_audit')),1)
        Ledger(path)  # idempotent reopening

    def test_corrupt_snapshot_not_silently_reparsed(self):
        rows=self.add('Đề 12=10')
        rows[0]['entries_snapshot']='{}'
        with self.assertRaises(ValueError):totals(rows)

    def test_corrupt_money_config_is_blocked(self):
        rows=self.add('Đề 12=10')
        for field,key,value in (('percent','Đề','-5'),('reward','Đề','NaN'),('reward','Xiên 2','16')):
            cfg=json.loads(rows[0]['config']);cfg[field][key]=value
            changed={**rows[0],'config':json.dumps(cfg)}
            with self.assertRaises(ValueError):totals([changed],self.result)

    def test_large_money_exact_beyond_default_decimal_precision(self):
        value='100000000000000000000000000001'
        self.assertEqual(totals(self.add('Đề 99='+value))['Đề'][0],Decimal(value))

    def test_unsupported_precision_not_saved(self):
        with self.assertRaises(ValueError):self.add('Đề 12='+('9'*90))
        self.assertFalse(self.db.tickets(1,self.pid,DAY))

    def test_variant_initial_unconfigured_and_bad_variant(self):
        p=self.db.create(1,'Chủ','Unconfigured')
        self.db.select_variant(1,p,'14')
        self.assertFalse(self.db.profile(1,p)['config']['ready'])
        with self.assertRaises(ValueError):self.db.select_variant(1,p,'16')

    def test_x14_x15_percent_reward_snapshots(self):
        self.db.configure(1,self.pid,'percent','0;0;10;0;0')
        self.add('Xiên 12-34=10')
        self.db.select_variant(1,self.pid,'14')
        self.db.configure(1,self.pid,'percent','0;0;20;0;0')
        rows=self.add('Xiên 12-34=10',2)
        t=totals(rows,self.result)
        self.assertEqual(t['Xiên 2 ×15'],[Decimal(10),Decimal(1),Decimal(150)])
        self.assertEqual(t['Xiên 2 ×14'],[Decimal(10),Decimal(2),Decimal(140)])

    def test_round_half_up_no_intermediate_rounding(self):
        p=self.db.profile(1,self.pid)
        for pct,expected in (('47,5','11k'),('48','10k')):
            self.db.configure(1,self.pid,'percent',pct+';0;0;0;0')
            self.db.add(1,self.pid,DAY,len(self.db.tickets(1,self.pid,DAY))+1,'Đề 99=20')
            row=self.db.tickets(1,self.pid,DAY)[-1]
            text=summary(p,DAY,[row],self.result)
            self.assertIn('thu A: '+expected,text)

class RewardTests(unittest.TestCase):
    setUp=DataSafetyTests.setUp
    tearDown=DataSafetyTests.tearDown
    add=DataSafetyTests.add

def reward_test(raw, expected):
    def test(self):
        parts=totals(self.add(raw),self.result)
        self.assertEqual({k:v[2] for k,v in parts.items() if v[2]},
                         {k:Decimal(v) for k,v in expected.items()})
    return test

for i,(raw,expected) in enumerate([
    ('Bao 12=10',{'Bao':'70'}),
    ('Xiên 2 12-34=10',{'Xiên 2 ×15':'150'}),
    ('Xiên 3 12-34-56=10',{'Xiên 3':'480'}),
    ('Xiên 4 12-34-56-78=10',{'Xiên 4':'1800'}),
    ('Xiên quây 2 12-34-56=10',{'Xiên 2 ×15':'450'}),
    ('Xiên quây 12-34-56-78=10',{'Xiên 2 ×15':'900','Xiên 3':'1920','Xiên 4':'1800'}),
    ('Càng 312=10',{'Càng':'4000'}),
    ('Càng 412=10',{'Áp càng':'100'}),
    ('Càng 312.412=10',{'Càng':'4000','Áp càng':'100'}),
]):
    setattr(RewardTests,'test_reward_'+str(i),reward_test(raw,expected))

if __name__=='__main__':unittest.main()
