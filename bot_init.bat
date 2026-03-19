@echo off
set PYTHONIOENCODING=utf-8
cd /d "C:\Users\degiaian\OneDrive - ASE Conecta\Documentos\PMO\NoteTaker"
set PATH=C:\Users\degiaian\AppData\Local\Programs\Python\Python312;C:\Users\degiaian\AppData\Local\Programs\Python\Python312\Scripts;%PATH%
set PATH=%PATH%;C:\Users\degiaian\ffmpeg\bin

:loop
call venv\Scripts\activate
python main.py
echo Bot detenido, reiniciando en 30 segundos...
timeout /t 30 /nobreak
goto loop