#!/bin/bash
cd "$(dirname "$0")" || exit 1
if ! command -v python3 >/dev/null; then
 echo 'Máy chưa có Python 3.11 trở lên.'
 read -r -p 'Enter để đóng' answer
 exit 1
fi
[ -x .venv/bin/python ] || python3 -m venv .venv || exit 1
.venv/bin/python -m pip install -r requirements.txt || exit 1
.venv/bin/python run.py
read -r -p 'Enter để đóng' answer
