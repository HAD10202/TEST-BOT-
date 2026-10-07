"""Quick dialog input through production handlers; no ticket parser changes."""
import asyncio
import importlib
import os
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

OWNER=1001
STAFF=2002
DAY='06-10-2026'

class QuickInputTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.env=patch.dict(os.environ,{'BOT_DB':self.tmp.name+'/db','TELEGRAM_ADMIN_ID':str(OWNER)})
        self.env.start()
        self.previous=sys.modules.pop('bot',None)
        self.bot=importlib.import_module('bot')
        self.pid=self.bot.DB.create(OWNER,'Khách','Existing')
        self.bot.DB.configure(OWNER,self.pid,'percent','0;0;0;0;0')
        self.context=SimpleNamespace(user_data={'profile':self.pid,'day':DAY})
        self.outputs=[]
        self.sequence=0

    def tearDown(self):
        sys.modules.pop('bot',None)
        if self.previous is not None:sys.modules['bot']=self.previous
        self.env.stop()
        self.tmp.cleanup()

    async def send(self,text,actor=OWNER):
        self.sequence+=1
        async def reply(text,**kwargs):self.outputs.append(text)
        update=SimpleNamespace(effective_user=SimpleNamespace(id=actor),effective_chat=SimpleNamespace(type='private'),effective_message=SimpleNamespace(text=text,message_id=self.sequence,reply_text=reply))
        await self.bot.handle(update,self.context)

    def create(self,raw,side,name,actor=OWNER):
        async def flow():
            await self.send('Tạo người',actor)
            await self.send(raw,actor)
        asyncio.run(flow())
        p=self.bot.DB.profile(OWNER,self.context.user_data['profile'])
        self.assertEqual((p['side'],p['name'],p['owner']),(side,name,OWNER))
        self.assertNotEqual(p['id'],self.pid)
        self.assertNotIn('state',self.context.user_data)
        audit=self.bot.DB.query("SELECT * FROM workspace_audit WHERE action='create_profile' ORDER BY id")[-1]
        self.assertEqual(audit['actor'],actor)

    def configure(self,raw,expected,actor=OWNER):
        async def flow():
            await self.send('Sửa %',actor)
            await self.send(raw,actor)
        asyncio.run(flow())
        cfg=self.bot.DB.profile(OWNER,self.pid)['config']
        d,b,x,y,c=expected
        self.assertEqual(cfg['percent'],{'Đề':d,'Bao':b,'Xiên 2':x,'Xiên 3':y,'Xiên 4':y,'Càng':c,'Áp càng':'0'})
        self.assertEqual(cfg['variants']['15'],cfg['percent'])
        self.assertNotIn('state',self.context.user_data)
        audit=self.bot.DB.query("SELECT * FROM workspace_audit WHERE action='configure_percent' ORDER BY id")[-1]
        self.assertEqual(audit['actor'],actor)

    def reject_percent(self,raw):
        before=self.bot.DB.profile(OWNER,self.pid)
        audit=self.bot.DB.query('SELECT * FROM workspace_audit')
        async def flow():
            await self.send('Sửa %')
            await self.send(raw)
        asyncio.run(flow())
        self.assertEqual(self.bot.DB.profile(OWNER,self.pid),before)
        self.assertEqual(self.bot.DB.query('SELECT * FROM workspace_audit'),audit)
        self.assertEqual(self.context.user_data['state'],'percent')
        self.assertNotIn('Đã lưu',self.outputs[-1])

    def test_create_customer(self):self.create('Khách HBX','Khách','HBX')
    def test_create_master(self):self.create('Chủ OK','Chủ','OK')
    def test_create_unaccented_customer(self):self.create('Khach HBX','Khách','HBX')
    def test_create_unaccented_master(self):self.create('Chu OK','Chủ','OK')
    def test_create_spaced_name(self):self.create('Khách Nguyễn Văn A','Khách','Nguyễn Văn A')
    def test_create_legacy_semicolon(self):self.create('Khách; HBX','Khách','HBX')
    def test_create_trim_and_case(self):self.create('  khach   Nguyễn Văn A  ','Khách','Nguyễn Văn A')
    def test_create_hyphen_is_part_of_name(self):self.create('Khách Văn-A','Khách','Văn-A')
    def test_create_invalid_no_hyphen_separator(self):
        async def flow():
            await self.send('Tạo người');await self.send('Khách-HBX')
        asyncio.run(flow())
        self.assertEqual(len(self.bot.DB.profiles(OWNER)),1)
        self.assertEqual(self.context.user_data['state'],'create')
    def test_create_missing_name(self):
        async def flow():
            await self.send('Tạo người');await self.send('Khách')
        asyncio.run(flow())
        self.assertEqual(len(self.bot.DB.profiles(OWNER)),1)
    def test_create_legacy_empty_name_rejected(self):
        async def flow():
            await self.send('Tạo người');await self.send('Khách; ')
        asyncio.run(flow())
        self.assertEqual(len(self.bot.DB.profiles(OWNER)),1)
    def test_percent_space(self):self.configure('5 3,5 18 21 38',['5','3.5','18','21','38'])
    def test_percent_decimal_commas(self):self.configure('5,5 3,5 18,5 21,5 38,5',['5.5','3.5','18.5','21.5','38.5'])
    def test_percent_multiple_spaces(self):self.configure('5   3,5    18  21   38',['5','3.5','18','21','38'])
    def test_percent_zero(self):self.configure('0 0 0 0 0',['0']*5)
    def test_percent_legacy_semicolon(self):self.configure('5; 3,5; 18; 21; 38',['5','3.5','18','21','38'])
    def test_percent_legacy_spaced_hyphen(self):self.configure('5 - 3,5 - 18 - 21 - 38',['5','3.5','18','21','38'])
    def test_percent_whitespace(self):self.configure('5\t3,5\n18 21 38',['5','3.5','18','21','38'])
    def test_percent_missing(self):self.reject_percent('5 3,5 18 21')
    def test_percent_extra(self):self.reject_percent('5 3,5 18 21 38 40')
    def test_decimal_comma_never_two_values(self):self.reject_percent('5,5 18 21 38')
    def test_comma_is_not_list_separator(self):self.reject_percent('5,3,5,18,21,38')
    def test_mixed_separators_not_guessed(self):self.reject_percent('5;3,5 18 21 38')
    def test_percent_range_still_enforced(self):self.reject_percent('101 3,5 18 21 38')
    def test_percent_negative_still_rejected(self):self.reject_percent('-1 3,5 18 21 38')
    def test_create_prompt(self):
        asyncio.run(self.send('Tạo người'))
        self.assertIn('Khách HBX',self.outputs[-1]);self.assertIn('Chủ OK',self.outputs[-1]);self.assertIn('khoảng trắng',self.outputs[-1]);self.assertNotIn(';',self.outputs[-1])
    def test_percent_prompt(self):
        asyncio.run(self.send('Sửa %'))
        self.assertIn('Đề Bao Xiên 2 Xiên 3,4 Càng',self.outputs[-1]);self.assertIn('5 3,5 18 21 38',self.outputs[-1]);self.assertIn('5,5',self.outputs[-1]);self.assertNotIn(';',self.outputs[-1])
    def test_staff_create_shared_workspace_actor(self):
        self.bot.DB.add_users(OWNER,OWNER,str(STAFF));self.create('Chu Người chủ chung','Chủ','Người chủ chung',STAFF)
        self.assertEqual(self.bot.DB.profiles(STAFF),[])
    def test_staff_percent_shared_workspace_actor(self):
        self.bot.DB.add_users(OWNER,OWNER,str(STAFF));self.configure('5 3,5 18 21 38',['5','3.5','18','21','38'],STAFF)
    def test_percent_change_keeps_ticket_snapshot(self):
        self.bot.DB.add(OWNER,self.pid,DAY,900,'Đề 99=100')
        before=self.bot.DB.tickets(OWNER,self.pid,DAY)
        self.configure('5 3,5 18 21 38',['5','3.5','18','21','38'])
        self.assertEqual(self.bot.DB.tickets(OWNER,self.pid,DAY),before)
    def test_reward_legacy_unchanged(self):
        async def flow():
            await self.send('Sửa thưởng');await self.send('90;3,5;15;48;180;400;10')
        asyncio.run(flow())
        self.assertEqual(self.bot.DB.profile(OWNER,self.pid)['config']['reward'],{'Đề':'90','Bao':'3.5','Xiên 2':'15','Xiên 3':'48','Xiên 4':'180','Càng':'400','Áp càng':'10'})
    def test_reward_space_input_not_extended(self):
        before=self.bot.DB.profile(OWNER,self.pid)
        async def flow():
            await self.send('Sửa thưởng');await self.send('90 3,5 15 48 180 400 10')
        asyncio.run(flow())
        self.assertEqual(self.bot.DB.profile(OWNER,self.pid),before)
        self.assertEqual(self.context.user_data['state'],'reward')

if __name__=='__main__':unittest.main()
