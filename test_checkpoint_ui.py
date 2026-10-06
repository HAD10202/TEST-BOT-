"""New menus exercise actual handlers with real PTB objects, offline."""
import asyncio
import contextlib
import importlib
import io
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch, Mock
from results import LotteryResult

DAY='06-10-2026'
class CheckpointUITests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.env=patch.dict(os.environ,{'BOT_DB':str(Path(self.tmp.name)/'db'),'TELEGRAM_ADMIN_ID':'1'})
        self.env.start();self.previous=sys.modules.pop('bot',None);self.bot=importlib.import_module('bot')
        self.outputs=[]
        async def reply(text,**kwargs):self.outputs.append(text)
        self.message=SimpleNamespace(text='',message_id=0,reply_text=reply)
        self.update=SimpleNamespace(effective_message=self.message,effective_user=SimpleNamespace(id=1),effective_chat=SimpleNamespace(type='private'))
        self.pid=self.bot.DB.create(1,'Khách','HUO');self.bot.DB.configure(1,self.pid,'percent','0;0;0;0;0')
        self.context=SimpleNamespace(user_data={'profile':self.pid,'day':DAY})
    def tearDown(self):
        sys.modules.pop('bot',None)
        if self.previous is not None:sys.modules['bot']=self.previous
        self.env.stop();self.tmp.cleanup()
    async def send(self,text):
        self.message.message_id+=1;self.message.text=text;await self.bot.handle(self.update,self.context)
    def test_new_menu_buttons(self):
        labels=[b.text for row in self.bot.MENU.keyboard for b in row]
        for label in ['Sổ vé','Nợ cũ','Xem raw']:self.assertIn(label,labels)
        self.assertNotIn('Danh sách tin',labels)
    def test_book_hides_raw_and_shows_id(self):
        async def flow():
            await self.send('Đề 99=100');await self.send('Sổ vé')
            self.assertIn('SỔ HUO',self.outputs[-1]);self.assertIn('ID 1',self.outputs[-1]);self.assertIn('Đề: 100k',self.outputs[-1]);self.assertNotIn('Đề 99=100',self.outputs[-1])
        asyncio.run(flow())
    def test_old_book_button_remains_compatible(self):
        async def flow():await self.send('Danh sách tin');self.assertIn('SỔ HUO',self.outputs[-1])
        asyncio.run(flow())
    def test_raw_only_on_explicit_request(self):
        async def flow():
            await self.send('Đề 99=100');await self.send('Xem raw');self.assertNotIn('Đề 99=100',self.outputs[-1]);await self.send('1');self.assertIn('Đề 99=100',self.outputs[-1])
        asyncio.run(flow())
    def test_raw_other_profile_cannot_access(self):
        other=self.bot.DB.create(1,'Khách','OTHER');self.bot.DB.configure(1,other,'percent','0;0;0;0;0');self.bot.DB.add(1,other,DAY,900,'Đề 88=200')
        async def flow():await self.send('Xem raw');await self.send('1');self.assertNotIn('Đề 88=200',self.outputs[-1])
        asyncio.run(flow())
    def test_raw_deleted_cannot_access(self):
        async def flow():
            await self.send('Đề 99=100');self.bot.DB.delete(1,self.pid,DAY,1);await self.send('Xem raw');await self.send('1');self.assertNotIn('Đề 99=100',self.outputs[-1])
        asyncio.run(flow())
    def test_debt_handler_and_cancel(self):
        async def flow():
            await self.send('Nợ cũ');self.assertIn('THU 2356',self.outputs[-1]);await self.send('TRẢ 100');self.assertEqual(self.bot.DB.profile(1,self.pid)['old_balance'],'-100')
            await self.send('Nợ cũ');await self.send('Hủy');self.assertNotIn('state',self.context.user_data);self.assertEqual(self.bot.DB.profile(1,self.pid)['old_balance'],'-100')
        asyncio.run(flow())
    def test_debt_navigation_cancels_b_pending(self):
        async def flow():
            await self.send('B91=175k');await self.send('Nợ cũ');await self.send('THU 100')
            self.assertNotIn('pending_b',self.context.user_data);self.assertFalse(self.bot.DB.tickets(1,self.pid,DAY))
        asyncio.run(flow())
    def test_summary_menu_uses_new_view_and_debt(self):
        result=LotteryResult(DAY,'12312',tuple(['12']+['00']*26),0)
        async def flow():
            await self.send('Đề 99=100');await self.send('Nợ cũ');await self.send('THU 20')
            with patch.object(self.bot,'fetch_latest_result',return_value=result):await self.send('Xem tổng')
            self.assertIn('- Đề: 100k | % 0k |',self.outputs[-1]);self.assertTrue(self.outputs[-1].endswith('THU HUO: 120k'))
            with patch.object(self.bot,'fetch_latest_result',return_value=result):await self.bot.handle_command_total(self.update,self.context)
            self.assertTrue(self.outputs[-1].endswith('THU HUO: 120k'))
        asyncio.run(flow())
    def test_unauthorized_debt_no_mutation(self):
        self.update.effective_user.id=2
        async def flow():await self.send('Nợ cũ');await self.send('THU 100')
        asyncio.run(flow());self.assertEqual(self.bot.DB.profile(1,self.pid)['old_balance'],'0')
    def test_bad_token_rejects_before_builder(self):
        with patch.dict(os.environ,{'TELEGRAM_BOT_TOKEN':'123456:OFFLINE_TEST_TOKEN\x16'}),patch.object(self.bot.Application,'builder') as builder:
            with self.assertRaises(ValueError):self.bot.main()
            builder.assert_not_called()
    def test_startup_banner_after_initialization(self):
        stream=io.StringIO()
        with contextlib.redirect_stdout(stream):asyncio.run(self.bot.startup_notice(None))
        self.assertIn('BOT ĐANG CHẠY',stream.getvalue());self.assertIn('Không đóng cửa sổ này',stream.getvalue())

if __name__=='__main__':unittest.main()
