"""Double-click launcher entry point; importing this module never starts Telegram."""
import os
import sys
from local_config import ConfigError, install_redaction, load_config

def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if args not in ([], ['--setup']):
        print('Mở CHAY_BOT_WINDOWS.bat để chạy hoặc CAI_DAT_BOT_WINDOWS.bat để đổi cấu hình.')
        return 1
    try:
        token, admin = load_config(force_setup=args == ['--setup'])
        if args == ['--setup']:
            return 0
        install_redaction(token)
        os.environ['TELEGRAM_BOT_TOKEN'] = token
        os.environ['TELEGRAM_ADMIN_ID'] = admin
        from bot import main as start_bot
        start_bot()
        return 0
    except ConfigError as error:
        print(str(error))
    except (EOFError, KeyboardInterrupt):
        print('Đã dừng. Mở CHAY_BOT_WINDOWS.bat khi muốn chạy lại.')
    except Exception as error:
        from telegram.error import InvalidToken, NetworkError
        if isinstance(error, InvalidToken):
            print('TOKEN KHÔNG HỢP LỆ. Chạy CAI_DAT_BOT_WINDOWS.bat để nhập lại.')
        elif isinstance(error, NetworkError):
            print('KHÔNG KẾT NỐI ĐƯỢC TELEGRAM. Kiểm tra Internet rồi chạy lại.')
        else:
            print('BOT CHƯA CHẠY ĐƯỢC. Kiểm tra cấu hình và cài lại dependencies bằng CHAY_BOT_WINDOWS.bat.')
    return 1

if __name__ == '__main__':
    raise SystemExit(main())
