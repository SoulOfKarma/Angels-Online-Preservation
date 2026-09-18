@echo off
REM Arranca el servidor de Angels Online con log detallado.
REM El server.xml del cliente ya apunta a 127.0.0.1:16768
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
C:\laragon\bin\python\python-3.10\python.exe server\app.py -v
pause
