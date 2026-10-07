"""Real PTB imports + registered handler smoke. No Telegram/AZ24 network.

This is deliberately separate from the frozen 180 unittest cases. Results
here prove offline wiring/storage only, not real messages or real winnings.
"""
import asyncio
from contextlib import closing
import importlib
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DAY = '06-10-2026'
CHECKS = []


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def passed(name):
    CHECKS.append(name)
    print(name + ': PASS', flush=True)


def forbid_network(*args, **kwargs):
    raise RuntimeError('Live network is forbidden during runtime smoke')


async def handler_flow(bot, application, telegram):
    from telegram.ext import MessageHandler
    from accounting import totals
    outputs = []
    context = SimpleNamespace(user_data={'day': DAY})
    handler = next(h for h in application.handlers[0] if isinstance(h, MessageHandler))
    sequence = 0
    contexts = {1: context}

    async def reply_text(message, text, **kwargs):
        outputs.append(text)

    async def send(text, message_id=None, user_id=1):
        nonlocal sequence
        sequence += 1
        mid = sequence if message_id is None else message_id
        update = telegram.Update.de_json({
            'update_id': sequence,
            'message': {
                'message_id': mid, 'date': 0, 'text': text,
                'from': {'id': user_id, 'is_bot': False, 'first_name': 'CI owner'},
                'chat': {'id': user_id, 'type': 'private', 'first_name': 'CI owner'},
            },
        }, application.bot)
        check = handler.check_update(update)
        require(bool(check), 'Registered Telegram handler rejected text fixture')
        actor_context = contexts.setdefault(user_id, SimpleNamespace(user_data={'day': DAY}))
        await handler.handle_update(update, application, check, actor_context)
        return mid

    def rows():
        return bot.DB.tickets(1, context.user_data['profile'], DAY)

    with patch.object(telegram.Message, 'reply_text', reply_text):
        await send('Tạo người')
        await send('Khach CI owner')
        await send('Sửa %')
        await send('0 0 0 0 0')
        require(bot.DB.profile(1, context.user_data['profile'])['side'] == 'Khách', 'Quick create side not normalized')
        passed('Quick create and whitespace percent through registered handlers')
        await send('Sửa thưởng')
        await send('90,5 3,5 15 48,5 180,5 400,5 10,5')
        cfg=bot.DB.profile(1, context.user_data['profile'])['config']
        require(cfg['reward']['Bao']=='3.5' and cfg['reward']['Đề']=='90.5', 'Reward decimal comma was split')
        await send('Sửa thưởng')
        await send('90 3,5 16 48 180 400 10')
        require(bot.DB.profile(1, context.user_data['profile'])['config']==cfg, 'Invalid X2 changed config')
        await send('90;3,5;15;48;180;400;10')
        passed('Reward whitespace, decimal comma, X2 rejection and legacy semicolon')
        original = await send('B91=175k')
        require(not rows(), 'B91 was stored before confirmation')
        require('BAO TOÀN BỘ' in outputs[-1] and 'ĐỀ BỘ' in outputs[-1],
                'Missing B confirmation choices')
        await send('BAO TOÀN BỘ')
        require(len(rows()) == 1 and rows()[0]['message'] == original,
                'Bao confirmation did not preserve original message ID')
        require(totals(rows())['Bao'][0] == 175, 'Bao goods should be 175k')
        passed('B91 -> Bao confirmation -> store only after choice')

        saved = rows()[0]
        tid = saved['id']
        await send(saved['raw'], original)
        require(len(rows()) == 1, 'Duplicate delivery added a second ticket')
        passed('Duplicate Telegram message ID')

        await send('Sửa %')
        await send('5;5;5;5;5')
        require(rows()[0]['config'] == saved['config'], 'Profile edit changed ticket snapshot')
        require(totals(rows())['Bao'][1] == 0, 'Old ticket percent changed')
        require(bool(rows()[0]['entries_snapshot']), 'Missing Entry snapshot')
        passed('Config and Entry snapshots')

        await send('Sửa tin')
        await send(f'{tid}; Bao 98=200k')
        require(rows()[0]['raw'] == 'Bao 98=200k', 'Edit was not stored')
        require(rows()[0]['config'] == saved['config'], 'Edit changed original config')
        require(totals(rows())['Bao'][0] == 200, 'Edited goods should be 200k')
        audit = bot.DB.query('SELECT * FROM ticket_audit WHERE ticket=?', (tid,))
        require(len(audit) == 1 and audit[0]['action'] == 'edit'
                and audit[0]['old_raw'] == saved['raw']
                and audit[0]['new_raw'] == 'Bao 98=200k', 'Missing edit audit')
        passed('Handler edit with audit')

        await send('Xóa tin')
        await send(str(tid))
        require(len(rows()) == 1, 'Delete occurred before confirmation')
        await send('XÓA')
        require(not rows(), 'Deleted ticket still in active totals')
        deleted = bot.DB.query('SELECT * FROM tickets WHERE id=?', (tid,))[0]
        require(bool(deleted['deleted_at']) and deleted['raw'] == 'Bao 98=200k',
                'Expected retained soft-deleted ticket')
        require(bot.DB.query('SELECT * FROM ticket_audit WHERE ticket=? ORDER BY id', (tid,))[-1]['action'] == 'delete',
                'Missing delete audit')
        await send('Bao 98=200k', original)
        require(not rows(), 'Duplicate delivery resurrected soft-deleted ticket')
        passed('Handler confirmed soft delete and duplicate tombstone')

        await send('B91=175k')
        require(not rows(), 'B91 was stored without De-bo choice')
        await send('ĐỀ BỘ')
        require(len(rows()) == 1 and rows()[0]['raw'].startswith('Đề bộ'),
                'De-bo confirmation did not store explicit choice')
        require(totals(rows())['Đề'][0] == 1400, 'De-bo 91 should have 8 x 175 = 1400k goods')
        require(totals(rows())['Đề'][1] == 70, 'Stored 5% should be 70k')
        passed('B91 -> De-bo confirmation -> store only after choice')

        await send('Sửa %')
        await send('20;20;20;20;20')
        with patch.object(bot, 'fetch_latest_result', side_effect=bot.ResultError('Offline CI; AZ24 NOT RUN')):
            await send('Xem tổng')
        require('Tổng hàng: 1.400k | Trừ %: 70k' in outputs[-1], 'Wrong daily goods/cut summary')
        require('Chưa chốt tiền thu/trả' in outputs[-1], 'Offline fixture unexpectedly settled winnings')
        passed('Daily goods total from frozen snapshot (no lottery settlement)')

        await send('➕ Thêm người')
        await send('10, 11')
        require(bot.DB.authorized(1, 10) and bot.DB.authorized(1, 11), 'Batch grant failed')
        await send('Nhập tin', user_id=10)
        await send('CI owner', user_id=10)
        await send('Bao 98=100k', original, user_id=10)
        require(len(rows()) == 2, 'Staff message collided with owner message ID')
        staff_ticket = next(r for r in rows() if r['raw'] == 'Bao 98=100k')
        require(staff_ticket['owner'] == 1, 'Staff created a separate workspace')
        await send('Nhập tin', user_id=11)
        await send('CI owner', user_id=11)
        await send('Sửa tin', user_id=11)
        await send(f"{staff_ticket['id']}; Bao 98=120k", user_id=11)
        audit = bot.DB.query('SELECT * FROM ticket_audit WHERE ticket=?', (staff_ticket['id'],))
        require(audit[-1]['actor'] == 11, 'Audit lost actual staff actor')
        require(totals(rows())['Bao'][0] == 120, 'Owner cannot see staff edit')
        await send('➖ Xóa người')
        await send('10')
        require(bot.DB.authorized(1, 10), 'Revocation happened before confirmation')
        await send('XÓA QUYỀN')
        before = len(outputs)
        await send('Sổ vé', user_id=10)
        require(len(outputs) == before and not bot.DB.authorized(1, 10), 'Revoked staff still read data')
        passed('Multi-user real handlers: batch grant, shared workspace, actor audit, confirmed revoke')



def main():
    os.chdir(ROOT)
    require(sys.version_info >= (3, 11), 'Python 3.11+ required')
    # Isolate this offline harness from any host proxy settings. No proxy
    # configuration or SOCKS compatibility is being verified here.
    environment = {key: value for key, value in os.environ.items()
                   if key.lower() not in ('http_proxy', 'https_proxy', 'all_proxy', 'no_proxy')}
    environment.update(TELEGRAM_ADMIN_ID='1', TELEGRAM_BOT_TOKEN='123456:CI_ONLY_NOT_A_REAL_TOKEN')
    # Create the event loop before the socket blockade: Windows may create a
    # loopback socket pair for its internal wake-up pipe. No service is called.
    with closing(asyncio.new_event_loop()) as loop, tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, environment, clear=True), \
            patch.object(socket.socket, 'connect', forbid_network), \
            patch.object(socket.socket, 'connect_ex', forbid_network), \
            patch.object(socket, 'create_connection', forbid_network):
        os.environ['BOT_DB'] = str(Path(directory) / 'runtime-smoke.sqlite3')
        import telegram
        from telegram.ext import Application
        require(telegram.__version__ == '22.5', 'Runtime dependency differs from requirements.txt')
        passed('python-telegram-bot real import (22.5)')
        bot = importlib.import_module('bot')
        require(isinstance(bot.MENU, telegram.ReplyKeyboardMarkup), 'Bot used mocked Telegram import')
        passed('bot.py real import')
        from zoneinfo import ZoneInfo
        require(str(ZoneInfo('Asia/Ho_Chi_Minh')) == 'Asia/Ho_Chi_Minh', 'Timezone not available')
        passed('Windows-compatible timezone dependency')
        # run.py import is passive. Mock only polling; explicitly start the
        # real Application and register the production handlers.
        with patch.object(Application, 'run_polling', autospec=True) as polling:
            launcher = importlib.import_module('run')
            polling.assert_not_called()
            require(launcher.main([]) == 0, 'Launcher returned an error')
            polling.assert_called_once()
            application = polling.call_args.args[0]
        require(isinstance(application, Application), 'Startup did not construct real Application')
        passed('run.py import and handler registration (polling mocked)')
        loop.run_until_complete(handler_flow(bot, application, telegram))
    print('AZ24 LIVE: NOT RUN; TELEGRAM LIVE: NOT RUN')
    print('RUNTIME SMOKE: PASS; separate from 394 unittest cases')
    if os.getenv('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as output:
            output.write('\nRuntime smoke (real dependency; live services disabled):\n\n')
            output.write('\n'.join('- PASS: ' + name for name in CHECKS))
            output.write('\n\nAZ24 LIVE: NOT RUN. Telegram live polling: NOT RUN.\n')


if __name__ == '__main__':
    main()
