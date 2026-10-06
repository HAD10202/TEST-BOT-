"""Offline Telegram handler tests: confirmation is a storage boundary."""
import asyncio
import importlib
import os
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

class Filter:
    def __and__(self,other):return self
    def __invert__(self):return self

class UISafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        tg=types.ModuleType('telegram')
        tg.Update=object;tg.ReplyKeyboardMarkup=lambda buttons,**kw:buttons
        ext=types.ModuleType('telegram.ext')
        ext.Application=object;ext.CommandHandler=object;ext.MessageHandler=object
        ext.ContextTypes=types.SimpleNamespace(DEFAULT_TYPE=object)
        ext.filters=types.SimpleNamespace(TEXT=Filter(),COMMAND=Filter())
        self.environment=patch.dict(os.environ,{'BOT_DB':self.tmp.name+'/db','TELEGRAM_ADMIN_ID':'1'})
        self.modules=patch.dict(sys.modules,{'telegram':tg,'telegram.ext':ext})
        self.environment.start();self.modules.start()
        self.old_bot=sys.modules.pop('bot',None)
        self.bot=importlib.import_module('bot')
        self.outputs=[]
        outputs=self.outputs
        class Message:
            message_id=0;text=''
            async def reply_text(self,text,**kwargs):outputs.append((text,kwargs))
        self.message=Message()
        self.update=types.SimpleNamespace(effective_message=self.message,
            effective_user=types.SimpleNamespace(id=1),effective_chat=types.SimpleNamespace(type='private'))
        self.pid=self.bot.DB.create(1,'Khách','A')
        self.bot.DB.configure(1,self.pid,'percent','0;0;0;0;0')
        self.context=types.SimpleNamespace(user_data={'profile':self.pid,'day':'06-10-2026'})
    def tearDown(self):
        sys.modules.pop('bot',None)
        if self.old_bot is not None:sys.modules['bot']=self.old_bot
        self.modules.stop();self.environment.stop();self.tmp.cleanup()
    async def send(self,raw):
        self.message.message_id+=1;self.message.text=raw
        await self.bot.handle(self.update,self.context)
    def rows(self):return self.bot.DB.tickets(1,self.pid,'06-10-2026')
    def run_flow(self,flow):asyncio.run(flow())

    def test_b_bao_choice_stores_original_message_id_once(self):
        async def flow():
            await self.send('B91=175k')
            original=self.message.message_id
            self.assertFalse(self.rows())
            self.assertIn('BAO TOÀN BỘ',self.outputs[-1][0])
            self.assertIn('ĐỀ BỘ',self.outputs[-1][0])
            await self.send('BAO TOÀN BỘ')
            self.assertEqual(len(self.rows()),1)
            self.assertEqual(self.rows()[0]['message'],original)
            self.assertEqual(self.rows()[0]['raw'],'Bao91=175k')
            self.assertFalse(self.bot.DB.add(1,self.pid,'06-10-2026',original,'Bao91=175k'))
            await self.send('BAO TOÀN BỘ')
            self.assertEqual(len(self.rows()),1)
        self.run_flow(flow)

    def test_b_de_bo_choice(self):
        async def flow():
            await self.send('b20b500k');self.assertFalse(self.rows())
            await self.send('ĐỀ BỘ')
            self.assertEqual(len(self.rows()),1)
            self.assertTrue(self.rows()[0]['raw'].startswith('Đề bộ'))
        self.run_flow(flow)

    def test_multiple_b_lines_each_confirmed(self):
        async def flow():
            await self.send('B91=175k\nB20=500k')
            await self.send('BAO TOÀN BỘ');self.assertFalse(self.rows())
            await self.send('ĐỀ BỘ');self.assertEqual(len(self.rows()),1)
        self.run_flow(flow)

    def test_cancel_and_navigation_clear_choice(self):
        async def flow():
            for action in ('Hủy','Đổi ngày','Đổi người','Danh sách tin','Xiên ×14'):
                self.bot.clear_pending(self.context)
                await self.send('B91=175k')
                await self.send(action)
                self.assertNotIn('pending_b',self.context.user_data)
                self.assertFalse(self.rows())
        self.run_flow(flow)

    def test_changed_config_or_expired_choice_not_saved(self):
        async def flow():
            await self.send('B91=175k')
            self.bot.DB.configure(1,self.pid,'percent','5;0;0;0;0')
            await self.send('BAO TOÀN BỘ');self.assertFalse(self.rows())
            await self.send('B91=175k')
            self.context.user_data['pending_b']['expires']=0
            await self.send('ĐỀ BỘ');self.assertFalse(self.rows())
        self.run_flow(flow)

    def test_delete_confirmation_cannot_cross_navigation(self):
        async def flow():
            await self.send('Đề 12=10');tid=self.rows()[0]['id']
            await self.send('Xóa tin');await self.send(str(tid))
            await self.send('Danh sách tin');await self.send('XÓA')
            self.assertEqual(len(self.rows()),1)
            self.assertFalse(self.bot.DB.query('SELECT * FROM ticket_audit'))
        self.run_flow(flow)

    def test_edit_b_does_not_change_old_ticket_until_choice(self):
        async def flow():
            await self.send('Đề 12=10');tid=self.rows()[0]['id']
            await self.send('Sửa tin');await self.send(f'{tid}; B91=175k')
            self.assertEqual(self.rows()[0]['raw'],'Đề 12=10')
            await self.send('ĐỀ BỘ')
            self.assertTrue(self.rows()[0]['raw'].startswith('Đề bộ'))
            self.assertEqual(len(self.bot.DB.query('SELECT * FROM ticket_audit')),1)
        self.run_flow(flow)

    def test_partial_warning_and_rejection(self):
        async def flow():
            await self.send('Đề 12=10\nBao chưa rõ')
            self.assertFalse(self.rows())
            self.assertIn('CHƯA LƯU TOÀN BỘ',self.outputs[-1][0])
            self.assertIn('Chưa hiểu',self.outputs[-1][0])
        self.run_flow(flow)

    def test_unauthorized_or_group_has_no_storage_or_output(self):
        async def flow():
            self.update.effective_user.id=2
            await self.send('Đề 12=10')
            self.update.effective_user.id=1;self.update.effective_chat.type='group'
            await self.send('Đề 12=10')
            self.assertFalse(self.rows());self.assertFalse(self.outputs)
        self.run_flow(flow)

    def test_total_command_without_profile_reports_error(self):
        async def flow():
            self.context.user_data.pop('profile')
            await self.bot.handle_command_total(self.update,self.context)
            self.assertIn('chọn tên',self.outputs[-1][0])
        self.run_flow(flow)

    def test_total_command_blocks_unreviewed_legacy_ticket(self):
        async def flow():
            await self.send('Đề 12=10')
            self.bot.DB.query('UPDATE tickets SET entries_snapshot=NULL',write=True)
            with patch.object(self.bot,'fetch_latest_result',side_effect=self.bot.ResultError('offline')):
                await self.bot.handle_command_total(self.update,self.context)
            self.assertIn('chưa có bản lưu',self.outputs[-1][0])
            self.assertNotIn('Mày thu',self.outputs[-1][0])
        self.run_flow(flow)

if __name__=='__main__':unittest.main()
