"""Offline handler integration; no Telegram network or token."""
import asyncio
import importlib
import os
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
class Filter:
 def __and__(self,x):return self
 def __invert__(self):return self
class UIIntegration(unittest.TestCase):
 def test_profile_config_tickets_and_total(self):
  tg=types.ModuleType('telegram');tg.Update=object;tg.ReplyKeyboardMarkup=lambda *a,**k:None
  ext=types.ModuleType('telegram.ext');ext.Application=object;ext.CommandHandler=object;ext.MessageHandler=object;ext.ContextTypes=types.SimpleNamespace(DEFAULT_TYPE=object);ext.filters=types.SimpleNamespace(TEXT=Filter(),COMMAND=Filter())
  with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'BOT_DB':d+'/db','TELEGRAM_ADMIN_ID':'1'}),patch.dict(sys.modules,{'telegram':tg,'telegram.ext':ext}):
   sys.modules.pop('bot',None);bot=importlib.import_module('bot');outputs=[]
   class Message:
    text='';message_id=0
    async def reply_text(self,text,**kwargs):outputs.append(text)
   msg=Message();u=types.SimpleNamespace(effective_message=msg,effective_user=types.SimpleNamespace(id=1),effective_chat=types.SimpleNamespace(type='private'));ctx=types.SimpleNamespace(user_data={})
   async def send(text):msg.text=text;msg.message_id+=1;await bot.handle(u,ctx)
   async def run():
    await send('Tạo người');await send('Khách; HBX');await send('Sửa %');await send('5 - 3,5 - 18 - 23 - 38');await send('Đề 99=10k');await send('Xiên ×14');await send('Sửa %');await send('5;3,5;20;23;38');await send('X 12-34=10k');await send('Danh sách tin')
    with patch.object(bot,'fetch_latest_result',side_effect=bot.ResultError('offline')):await send('Xem tổng')
   asyncio.run(run());self.assertEqual(len(bot.DB.tickets(1,ctx.user_data['profile'],ctx.user_data['day'])),2)
   self.assertIn('Xiên 2 ×14',outputs[-1]);self.assertIn('Chưa chốt',outputs[-1]);self.assertTrue(any('ID ' in s for s in outputs))
