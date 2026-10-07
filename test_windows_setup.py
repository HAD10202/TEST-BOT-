"""Offline local setup validation; no real credentials or Telegram calls."""
import contextlib
import importlib
import io
import logging
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo, reset_tzpath
import local_config as config

TOKEN='123456:OFFLINE_TEST_NOT_A_REAL_TOKEN'
NEW_TOKEN='654321:ANOTHER_TEST_NOT_A_REAL_TOKEN'
ROOT=Path(__file__).resolve().parent

class WindowsSetupTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/'TEST-BOT'/'secrets.env'
    def tearDown(self):self.tmp.cleanup()
    def test_requirements_tzdata(self):self.assertIn('tzdata',(ROOT/'requirements.txt').read_text(encoding='utf-8').splitlines())
    def test_timezone_from_tzdata_without_system_db(self):
        import zoneinfo
        previous=zoneinfo.TZPATH
        try:
            reset_tzpath(());ZoneInfo.clear_cache()
            self.assertEqual(str(ZoneInfo('Asia/Ho_Chi_Minh')),'Asia/Ho_Chi_Minh')
        finally:reset_tzpath(previous);ZoneInfo.clear_cache()
    def test_trim_spaces(self):self.assertEqual(config.validate_token('  '+TOKEN+'  '),TOKEN)
    def test_control_chars_rejected(self):
        for char in ['\x16','\x00','\t','\x7f']:
            with self.assertRaises(config.ConfigError) as caught:config.validate_token(TOKEN+char)
            self.assertIn('ký tự lỗi',str(caught.exception));self.assertNotIn(TOKEN,str(caught.exception))
    def test_newline_rejected(self):
        for char in ['\n','\r','\r\n']:
            with self.assertRaises(config.ConfigError):config.validate_token(TOKEN+char)
    def test_non_ascii_rejected(self):
        with self.assertRaises(config.ConfigError):config.validate_token(TOKEN+'ế')
    def test_empty_rejected(self):
        for value in ['', '   ']:
            with self.assertRaises(config.ConfigError):config.validate_token(value)
    def test_format_rejected(self):
        for value in ['abc','123:abc','x:'+('A'*30),'123:'+('A'*20)+' space']:
            with self.assertRaises(config.ConfigError):config.validate_token(value)
    def test_admin_validation(self):
        self.assertEqual(config.validate_admin(' 6935873181 '),'6935873181')
        for value in ['0','-1','1.2','١','1\n2','x']:
            with self.assertRaises(config.ConfigError):config.validate_admin(value)
    def test_parse_valid(self):
        self.assertEqual(config.parse_secrets('TELEGRAM_BOT_TOKEN='+TOKEN+'\nTELEGRAM_ADMIN_ID=1\n'),(TOKEN,'1'))
    def test_parse_crlf(self):
        self.assertEqual(config.parse_secrets('TELEGRAM_BOT_TOKEN='+TOKEN+'\r\nTELEGRAM_ADMIN_ID=1\r\n'),(TOKEN,'1'))
    def test_parse_injection_and_duplicates_reject(self):
        for extra in ['\nUNKNOWN=x','\nTELEGRAM_ADMIN_ID=2','\ninjected','\n TELEGRAM_ADMIN_ID=2']:
            with self.assertRaises(config.ConfigError):config.parse_secrets('TELEGRAM_BOT_TOKEN='+TOKEN+'\nTELEGRAM_ADMIN_ID=1'+extra)
    def test_parse_missing_reject(self):
        with self.assertRaises(config.ConfigError):config.parse_secrets('TELEGRAM_BOT_TOKEN='+TOKEN)
    def test_first_setup_once_then_existing_auto_load(self):
        inputs=Mock(side_effect=[TOKEN,'1','']);out=Mock()
        self.assertEqual(config.load_config({},self.path,input_fn=inputs,output=out),(TOKEN,'1'))
        self.assertEqual(inputs.call_count,3)
        self.assertEqual(config.load_config({},self.path,input_fn=Mock(side_effect=AssertionError('must not prompt'))),(TOKEN,'1'))
    def test_change_token_and_admin(self):
        config.save_secrets(self.path,TOKEN,'1')
        self.assertEqual(config.load_config({},self.path,True,Mock(side_effect=[NEW_TOKEN,'2']),Mock()),(NEW_TOKEN,'2'))
        self.assertEqual(config.read_secrets(self.path),(NEW_TOKEN,'2'))
    def test_setup_retry_does_not_echo_token(self):
        out=Mock();config.setup(self.path,Mock(side_effect=[TOKEN+'\x16',TOKEN,'bad','1']),out)
        self.assertNotIn(TOKEN,' '.join(str(c) for c in out.call_args_list))
    def test_existing_invalid_file_never_calls_api(self):
        self.path.parent.mkdir();self.path.write_text('TELEGRAM_BOT_TOKEN='+TOKEN+'\x16\nTELEGRAM_ADMIN_ID=1')
        with self.assertRaises(config.ConfigError):config.load_config({},self.path,input_fn=Mock(side_effect=AssertionError('unexpected prompt')))
    def test_env_pair_supported_without_save(self):
        self.assertEqual(config.load_config({'TELEGRAM_BOT_TOKEN':TOKEN,'TELEGRAM_ADMIN_ID':'1'},self.path),(TOKEN,'1'))
        self.assertFalse(self.path.exists())
    def test_partial_env_rejects_no_silent_mix(self):
        config.save_secrets(self.path,TOKEN,'1')
        with self.assertRaises(config.ConfigError):config.load_config({'TELEGRAM_BOT_TOKEN':NEW_TOKEN},self.path)
    def test_appdata_outside_repo(self):
        path=config.secrets_path({'APPDATA':self.tmp.name},'win32')
        self.assertEqual(path,self.path);self.assertFalse(path.resolve().is_relative_to(ROOT))
    def test_missing_appdata_reject(self):
        with self.assertRaises(config.ConfigError):config.secrets_path({},'win32')
    def test_repo_secret_location_reject(self):
        with self.assertRaises(config.ConfigError):config.save_secrets(ROOT/'secrets.env',TOKEN,'1')
    def test_invalid_update_keeps_old_file(self):
        config.save_secrets(self.path,TOKEN,'1')
        with self.assertRaises(config.ConfigError):config.save_secrets(self.path,NEW_TOKEN+'\x16','2')
        self.assertEqual(config.read_secrets(self.path),(TOKEN,'1'))
    def test_atomic_failed_write_keeps_old_file(self):
        config.save_secrets(self.path,TOKEN,'1')
        with patch('local_config.os.replace',side_effect=OSError('disk')),self.assertRaises(config.ConfigError):config.save_secrets(self.path,NEW_TOKEN,'2')
        self.assertEqual(config.read_secrets(self.path),(TOKEN,'1'));self.assertFalse(list(self.path.parent.glob('.setup-*')))
    def test_posix_file_permissions(self):
        config.save_secrets(self.path,TOKEN,'1')
        # Windows chmod has different ACL semantics; no claim of POSIX protection there.
        if os.name!='nt':self.assertEqual(self.path.stat().st_mode & 0o777,0o600)
        self.assertTrue(self.path.is_file())
    def test_logs_redact_token_urls_and_exception(self):
        stream=io.StringIO();handler=logging.StreamHandler(stream);handler.addFilter(config.SecretFilter(TOKEN))
        logger=logging.getLogger('setup-test');logger.addHandler(handler);previous=logger.level;propagate=logger.propagate;logger.propagate=False;logger.setLevel(logging.WARNING)
        try:
            try:raise ValueError('https://api.telegram.org/bot'+TOKEN+'/getMe')
            except ValueError:logger.exception('failed URL %s',TOKEN)
            logger.warning('https://api.telegram.org/bot%s/getMe',TOKEN.replace(':','%3A'))
        finally:logger.removeHandler(handler);logger.setLevel(previous);logger.propagate=propagate
        self.assertNotIn(TOKEN,stream.getvalue());self.assertNotIn(TOKEN.replace(':','%3A'),stream.getvalue());self.assertNotIn('Traceback',stream.getvalue())
    def test_setup_console_no_getpass(self):
        self.assertNotIn('getpass',(ROOT/'run.py').read_text(encoding='utf-8')+(ROOT/'local_config.py').read_text(encoding='utf-8'))
        self.assertIn('Ctrl+V',(ROOT/'local_config.py').read_text(encoding='utf-8'))
    def test_bat_double_click_dependency_and_change_flow(self):
        bat=(ROOT/'CHAY_BOT_WINDOWS.bat').read_text(encoding='utf-8');change=(ROOT/'CAI_DAT_BOT_WINDOWS.bat').read_text(encoding='utf-8')
        self.assertIn('run.py %*',bat);self.assertIn('.venv',bat);self.assertIn('pip install -r requirements.txt',bat)
        self.assertIn('--setup',change);self.assertNotIn('TELEGRAM_BOT_TOKEN=',bat+change);self.assertNotIn('getpass',bat+change)
    def test_run_import_passive(self):
        with patch('local_config.load_config',side_effect=AssertionError('must not configure')):
            import run;importlib.reload(run)
    def test_run_setup_no_telegram_start(self):
        import run
        with patch.object(run,'load_config',return_value=(TOKEN,'1')) as load:
            self.assertEqual(run.main(['--setup']),0);self.assertTrue(load.call_args.kwargs['force_setup'])
    def test_run_invalid_config_friendly_no_token(self):
        import run
        stream=io.StringIO()
        with patch.object(run,'load_config',side_effect=config.ConfigError(config.TOKEN_ERROR)),contextlib.redirect_stdout(stream):self.assertEqual(run.main([]),1)
        self.assertIn('CAI_DAT_BOT_WINDOWS',stream.getvalue());self.assertNotIn(TOKEN,stream.getvalue())
    def test_run_unknown_error_redacted(self):
        self.run_failure(ValueError(TOKEN),'BOT CHƯA CHẠY ĐƯỢC')
    def test_run_network_error_friendly(self):
        from telegram.error import NetworkError
        self.run_failure(NetworkError('URL '+TOKEN),'KHÔNG KẾT NỐI ĐƯỢC TELEGRAM')
    def test_run_invalid_token_friendly(self):
        from telegram.error import InvalidToken
        self.run_failure(InvalidToken(TOKEN),'TOKEN KHÔNG HỢP LỆ')
    def run_failure(self,error,want):
        import run
        from types import SimpleNamespace
        stream=io.StringIO()
        with patch.object(run,'load_config',return_value=(TOKEN,'1')),patch.dict(sys.modules,{'bot':SimpleNamespace(main=Mock(side_effect=error))}),patch.dict(os.environ,{}),contextlib.redirect_stdout(stream):self.assertEqual(run.main([]),1)
        self.assertIn(want,stream.getvalue());self.assertNotIn(TOKEN,stream.getvalue());self.assertNotIn('Traceback',stream.getvalue())

if __name__=='__main__':unittest.main()
