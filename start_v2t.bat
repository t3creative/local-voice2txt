@echo off
REM Voice2Text Dictation System Launcher
REM Activates virtual environment and starts v2t.py

cd /d G:\voice2text
call .venv\Scripts\activate.bat
python v2t.py
