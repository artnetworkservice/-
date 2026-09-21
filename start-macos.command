#!/bin/zsh
set -e
cd "${0:A:h}"
if [[ ! -x .venv/bin/python ]]; then
  for candidate in python3.14 python3.13 python3.12 python3.11 python3; do
    if command -v "$candidate" >/dev/null && "$candidate" -c 'import sys; raise SystemExit(sys.version_info < (3, 11))' 2>/dev/null; then
      "$candidate" -m venv .venv
      break
    fi
  done
  if [[ ! -x .venv/bin/python ]]; then
    echo "ต้องติดตั้ง Python 3.11 ขึ้นไปก่อน"
    read -k 1 '?กดปุ่มใดก็ได้เพื่อปิด'
    exit 1
  fi
  .venv/bin/python -m pip install -r requirements.txt
fi
.venv/bin/python run.py
