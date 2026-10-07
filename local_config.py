"""Local-only credentials. No network calls and no credential logging."""
import logging
import os
from pathlib import Path
import re
import sys
import tempfile

class ConfigError(ValueError):
    pass

TOKEN_ERROR = 'Token có ký tự lỗi do cách dán. Hãy chạy CAI_DAT_BOT_WINDOWS.bat và dán lại token.'

def validate_token(value):
    if not isinstance(value, str) or any(ord(c) < 32 or ord(c) > 126 for c in value):
        raise ConfigError(TOKEN_ERROR)
    value = value.strip()
    if not re.fullmatch(r'[0-9]+:[A-Za-z0-9_-]{20,}', value) or len(value) > 512:
        raise ConfigError('TOKEN KHÔNG HỢP LỆ. Chạy CAI_DAT_BOT_WINDOWS.bat để nhập lại.')
    return value

def validate_admin(value):
    if not isinstance(value, str) or not re.fullmatch(r'[1-9][0-9]{0,19}', value.strip()):
        raise ConfigError('Admin ID phải là số nguyên dương. Chạy CAI_DAT_BOT_WINDOWS.bat để nhập lại.')
    return value.strip()

def secrets_path(environ=None, platform=None):
    env = os.environ if environ is None else environ
    platform = sys.platform if platform is None else platform
    if platform == 'win32':
        if not env.get('APPDATA'):
            raise ConfigError('Không tìm thấy thư mục cấu hình Windows APPDATA.')
        root = Path(env['APPDATA'])
    elif platform == 'darwin':
        root = Path.home() / 'Library' / 'Application Support'
    else:
        root = Path(env.get('XDG_CONFIG_HOME', str(Path.home() / '.config')))
    path = root / 'TEST-BOT' / 'secrets.env'
    ensure_outside_repo(path)
    return path

def ensure_outside_repo(path):
    if Path(path).resolve().is_relative_to(Path(__file__).resolve().parent):
        raise ConfigError('Cấu hình bí mật phải nằm ngoài thư mục source của bot.')

def parse_secrets(text):
    values = {}
    for line in text.split('\n'):
        # CRLF is a file line ending, never part of a credential.
        if line.endswith('\r'):
            line = line[:-1]
        if not line or line.startswith('#'):
            continue
        key, sep, value = line.partition('=')
        if not sep or key not in ('TELEGRAM_BOT_TOKEN', 'TELEGRAM_ADMIN_ID') or key in values:
            raise ConfigError('File cấu hình không hợp lệ. Chạy CAI_DAT_BOT_WINDOWS.bat để nhập lại.')
        values[key] = value
    if set(values) != {'TELEGRAM_BOT_TOKEN', 'TELEGRAM_ADMIN_ID'}:
        raise ConfigError('File cấu hình thiếu dữ liệu. Chạy CAI_DAT_BOT_WINDOWS.bat để nhập lại.')
    return validate_token(values['TELEGRAM_BOT_TOKEN']), validate_admin(values['TELEGRAM_ADMIN_ID'])

def read_secrets(path):
    ensure_outside_repo(path)
    try:
        return parse_secrets(Path(path).read_text(encoding='utf-8'))
    except (OSError, UnicodeError):
        raise ConfigError('Không đọc được cấu hình. Chạy CAI_DAT_BOT_WINDOWS.bat để nhập lại.') from None

def save_secrets(path, token, admin):
    token, admin = validate_token(token), validate_admin(admin)
    path = Path(path)
    ensure_outside_repo(path)
    temporary = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd, temporary = tempfile.mkstemp(prefix='.setup-', dir=path.parent)
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as file:
            file.write(f'TELEGRAM_BOT_TOKEN={token}\nTELEGRAM_ADMIN_ID={admin}\n')
            file.flush()
            os.fsync(file.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
        temporary = None
    except OSError:
        raise ConfigError('Không lưu được cấu hình trên máy này. Kiểm tra quyền ghi thư mục cấu hình.') from None
    finally:
        if temporary is not None:
            try:
                os.unlink(temporary)
            except OSError:
                pass

def setup(path, input_fn=input, output=print):
    output('================================\nCÀI ĐẶT BOT LẦN ĐẦU / ĐỔI CẤU HÌNH\n================================')
    while True:
        try:
            token = validate_token(input_fn('1. Dán Telegram Bot Token (Ctrl+V rồi Enter): '))
            break
        except ConfigError as error:
            output(str(error))
    while True:
        try:
            admin = validate_admin(input_fn('2. Nhập Telegram Admin ID: '))
            break
        except ConfigError as error:
            output(str(error))
    save_secrets(path, token, admin)
    output('Đã lưu cấu hình. Lần sau chỉ cần mở CHAY_BOT_WINDOWS.bat.')
    return token, admin

def load_config(environ=None, path=None, force_setup=False, input_fn=input, output=print):
    env = os.environ if environ is None else environ
    if not force_setup:
        token, admin = env.get('TELEGRAM_BOT_TOKEN'), env.get('TELEGRAM_ADMIN_ID')
        if token is not None or admin is not None:
            if token is None or admin is None:
                raise ConfigError('Cấu hình môi trường thiếu token hoặc Admin ID; không tự ghép hai cấu hình.')
            return validate_token(token), validate_admin(admin)
    path = secrets_path(env) if path is None else Path(path)
    if force_setup or not path.exists():
        credentials = setup(path, input_fn, output)
        if not force_setup:
            input_fn('Nhấn Enter để chạy bot: ')
        return credentials
    return read_secrets(path)

class SecretFilter(logging.Filter):
    def __init__(self, token):
        super().__init__()
        self.token = token
    def filter(self, record):
        message = record.getMessage().replace(self.token, '[TOKEN ĐÃ ẨN]')
        message = message.replace(self.token.replace(':', '%3A'), '[TOKEN ĐÃ ẨN]')
        message = re.sub(r'bot[0-9]+:[A-Za-z0-9_-]+', 'bot[TOKEN ĐÃ ẨN]', message)
        record.msg, record.args = message, ()
        # Tracebacks can contain exception URLs; normal startup must never expose them.
        record.exc_info, record.exc_text = None, None
        return True

def install_redaction(token):
    root = logging.getLogger()
    if not root.handlers:
        root.addHandler(logging.StreamHandler())
    handlers = list(root.handlers)
    for logger in logging.Logger.manager.loggerDict.values():
        if isinstance(logger, logging.Logger):
            handlers.extend(logger.handlers)
    for handler in set(handlers):
        handler.addFilter(SecretFilter(token))
