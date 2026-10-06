@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
 echo Máy chưa có Python. Cài Python 3.11 trở lên rồi mở lại file này.
 pause
 exit /b 1
)
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)"
if errorlevel 1 (
 echo Cần Python 3.11 trở lên. Cài Python mới rồi mở lại file này.
 pause
 exit /b 1
)
if not exist .venv\Scripts\python.exe (
 echo Đang chuẩn bị bot lần đầu. Vui lòng chờ...
 py -3 -m venv .venv
 if errorlevel 1 (
  echo Không tạo được môi trường Python.
  pause
  exit /b 1
 )
)
.venv\Scripts\python.exe -c "import telegram.ext, tzdata; from zoneinfo import ZoneInfo; assert telegram.__version__ == '22.5'; ZoneInfo('Asia/Ho_Chi_Minh')" >nul 2>nul
if errorlevel 1 (
 echo Đang cài thư viện. Cần kết nối Internet. Vui lòng chờ...
 .venv\Scripts\python.exe -m pip install -r requirements.txt
 if errorlevel 1 (
  echo Không cài được thư viện. Kiểm tra Internet rồi mở lại file này.
  pause
  exit /b 1
 )
)
.venv\Scripts\python.exe -X utf8 run.py %*
pause
