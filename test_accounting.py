import json
import tempfile
import unittest
from decimal import Decimal
from accounting import Ledger, totals, summary
from results import LotteryResult
class AccountingTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.db=Ledger(self.tmp.name+'/db');self.p=self.db.create(1,'Khách','HBX');self.db.configure(1,self.p,'percent','5;3,5;18;23;38');self.result=LotteryResult('06-10-2026','12312',tuple(['12','34']+['00']*25),0)
 def tearDown(self):self.tmp.cleanup()
 def test_snapshot_duplicate_and_owner(self):
  self.assertTrue(self.db.add(1,self.p,'06-10-2026',1,'Đề 12=10k'))
  self.assertFalse(self.db.add(1,self.p,'06-10-2026',1,'Đề 12=10k'))
  self.db.configure(1,self.p,'percent','10;3;14;20;30')
  rows=self.db.tickets(1,self.p,'06-10-2026');self.assertEqual(totals(rows)['Đề'][1],Decimal('.5'))
  with self.assertRaises(ValueError):self.db.profile(2,self.p)
 def test_variants(self):
  self.db.add(1,self.p,'06-10-2026',1,'X 12-34=10k');self.db.select_variant(1,self.p,'14')
  with self.assertRaises(ValueError):self.db.add(1,self.p,'06-10-2026',2,'X 12-34=10k')
  self.db.configure(1,self.p,'percent','5;3;20;23;38');self.db.add(1,self.p,'06-10-2026',2,'X 12-34=10k')
  t=totals(self.db.tickets(1,self.p,'06-10-2026'),self.result);self.assertEqual(t['Xiên 2 ×15'],[Decimal(10),Decimal('1.8'),Decimal(150)]);self.assertEqual(t['Xiên 2 ×14'],[Decimal(10),Decimal(2),Decimal(140)])
 def test_direction_rounding_and_date(self):
  self.db.add(1,self.p,'06-10-2026',1,'Đề 99=10k');rows=self.db.tickets(1,self.p,'06-10-2026');p=self.db.profile(1,self.p)
  self.assertIn('thu HBX: 10k',summary(p,'06-10-2026',rows,self.result));p['side']='Chủ';self.assertIn('trả HBX: 10k',summary(p,'06-10-2026',rows,self.result))
  with self.assertRaises(ValueError):summary(p,'05-10-2026',rows,self.result)
  self.assertIn('Chưa chốt',summary(p,'06-10-2026',rows))
 def test_winner_and_edit(self):
  self.db.add(1,self.p,'06-10-2026',1,'Đề 12=10k');rows=self.db.tickets(1,self.p,'06-10-2026');p=self.db.profile(1,self.p)
  self.assertIn('trả HBX: 891k',summary(p,'06-10-2026',rows,self.result));p['side']='Chủ';self.assertIn('thu HBX: 891k',summary(p,'06-10-2026',rows,self.result))
  with self.assertRaises(ValueError):self.db.replace(1,self.p,'06-10-2026',rows[0]['id'],'không hiểu')
  self.db.replace(1,self.p,'06-10-2026',rows[0]['id'],'Đề 99=10k');self.assertEqual(len(self.db.tickets(1,self.p,'06-10-2026')),1)
 def test_invalid_config_and_input(self):
  for text in ('NaN;3;4;5;6','101;3;4;5;6','1;2'):
   with self.assertRaises(ValueError):self.db.configure(1,self.p,'percent',text)
  with self.assertRaises(ValueError):self.db.add(1,self.p,'06-10-2026',1,'Đề 12=10k\n Bao thiếu giá')
if __name__=='__main__':unittest.main()
