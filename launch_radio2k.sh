#!/bin/bash
# Radio2k launcher — activates venv and runs the app
cd "$(dirname "$0")"
source venv/bin/activate
python radio2k.py &
disown
