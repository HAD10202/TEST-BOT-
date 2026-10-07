"""Reward dialog UX only: normalization, legacy validation and snapshots."""
import asyncio
import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

class RewardInputTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.env=patch.dict(os.environ,{'BOT_DB':self.tmp.name+'/db','TELEGRAM_ADMIN_ID':'1001'})
        self.env.start();self.previous=sys.modules.pop('bot',None);self.bot=importlib.import_module('bot')
        self.pid=self.bot.DB.create(1001,'Khách','Rewards')
        self.bot.DB.configure(1001,self.pid,'percent','5;3,5;18;21;38')
        self.ctx=SimpleNamespace(user_data={'profile':self.pid,'day':'06-10-2026'})
        self.outputs=[];self.sequence=0
    def tearDown(self):
        sys.modules.pop('bot',None)
        if self.previous is not None:sys.modules['bot']=self.previous
        self.env.stop();self.tmp.cleanup()
    async def send(self,text,actor=1001):
        self.sequence+=1
        async def reply(text,**kwargs):self.outputs.append(text)
        update=SimpleNamespace(effective_user=SimpleNamespace(id=actor),effective_chat=SimpleNamespace(type='private'),effective_message=SimpleNamespace(text=text,message_id=self.sequence,reply_text=reply))
        await self.bot.handle(update,self.ctx)
    def configure(self,raw,expected=None,actor=1001):
        expected=expected or ['90','3.5','15','48','180','400','10']
        async def flow():await self.send('Sửa thưởng',actor);await self.send(raw,actor)
        asyncio.run(flow())
        cfg=self.bot.DB.profile(1001,self.pid)['config']
        self.assertEqual(list(cfg['reward'].values()),expected)
        self.assertNotIn('state',self.ctx.user_data)
        audit=self.bot.DB.query("SELECT * FROM workspace_audit WHERE action='configure_reward' ORDER BY id")[-1]
        self.assertEqual(audit['actor'],actor)
    def reject(self,raw):
        before=self.bot.DB.profile(1001,self.pid);audit=self.bot.DB.query('SELECT * FROM workspace_audit')
        async def flow():await self.send('Sửa thưởng');await self.send(raw)
        asyncio.run(flow())
        self.assertEqual(self.bot.DB.profile(1001,self.pid),before)
        self.assertEqual(self.bot.DB.query('SELECT * FROM workspace_audit'),audit)
        self.assertEqual(self.ctx.user_data['state'],'reward')
    def test_space(self):self.configure('90 3,5 15 48 180 400 10')
    def test_decimal_commas(self):self.configure('90,5 3,5 15 48,5 180,5 400,5 10,5',['90.5','3.5','15','48.5','180.5','400.5','10.5'])
    def test_multiple_spaces(self):self.configure('90   3,5    15  48   180  400  10')
    def test_whitespace(self):self.configure('90\t3,5\n15 48 180 400 10')
    def test_legacy_semicolon(self):self.configure('90;3,5;15;48;180;400;10')
    def test_legacy_spaced_hyphen(self):self.configure('90 - 3,5 - 15 - 48 - 180 - 400 - 10')
    def test_missing(self):self.reject('90 3,5 15 48 180 400')
    def test_extra(self):self.reject('90 3,5 15 48 180 400 10 99')
    def test_invalid_xien_16(self):self.reject('90 3,5 16 48 180 400 10')
    def test_valid_xien_14(self):self.configure('90 3,5 14 48 180 400 10',['90','3.5','14','48','180','400','10'])
    def test_decimal_comma_is_one_value(self):self.reject('90 3,5 15 48 180 400')
    def test_comma_not_separator(self):self.reject('90,3,5,15,48,180,400,10')
    def test_mixed_invalid_separators(self):self.reject('90;3,5 15 48 180 400 10')
    def test_zero_reward_rejected(self):self.reject('0 3,5 15 48 180 400 10')
    def test_negative_reward_rejected(self):self.reject('-90 3,5 15 48 180 400 10')
    def test_fractional_xien_rejected(self):self.reject('90 3,5 14,5 48 180 400 10')
    def test_prompt(self):
        asyncio.run(self.send('Sửa thưởng'))
        self.assertIn('Đề Bao Xiên 2 Xiên 3 Xiên 4 Càng Áp càng',self.outputs[-1])
        self.assertIn('90 3,5 15 48 180 400 10',self.outputs[-1]);self.assertIn('ví dụ 3,5',self.outputs[-1]);self.assertNotIn(';',self.outputs[-1])
    def test_staff_actor_and_workspace(self):
        self.bot.DB.add_users(1001,1001,'2002');self.configure('90 3,5 15 48 180 400 10',actor=2002)
        self.assertEqual(self.bot.DB.profiles(2002),[])
    def test_old_ticket_snapshot_unchanged(self):
        self.bot.DB.add(1001,self.pid,'06-10-2026',99,'Đề 99=100')
        before=self.bot.DB.tickets(1001,self.pid,'06-10-2026')
        self.configure('91 4,5 15 49 181 401 11',['91','4.5','15','49','181','401','11'])
        self.assertEqual(self.bot.DB.tickets(1001,self.pid,'06-10-2026'),before)
    def test_same_variant_keeps_percent(self):
        before=self.bot.DB.profile(1001,self.pid)['config']['percent']
        self.configure('90 3,5 15 48 180 400 10')
        self.assertEqual(self.bot.DB.profile(1001,self.pid)['config']['percent'],before)

if __name__=='__main__':unittest.main()
