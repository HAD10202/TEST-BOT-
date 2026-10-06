import os
from getpass import getpass
if not os.getenv('TELEGRAM_BOT_TOKEN'):
 os.environ['TELEGRAM_BOT_TOKEN']=getpass('Dán token BotFather (ẩn khi nhập), Enter: ').strip()
if not os.getenv('TELEGRAM_ADMIN_ID'):
 os.environ['TELEGRAM_ADMIN_ID']=input('Telegram user ID của mày (số): ').strip()
from bot import main
main()
