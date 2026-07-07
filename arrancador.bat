@echo off
cd /d "C:\Users\degiaian\OneDrive - ASE Conecta\Documentos\PMO\NoteTaker"
set PYTHONIOENCODING=utf-8
REM Evita usar .pyc cacheados: OneDrive resetea fechas y Python puede correr bytecode viejo
set PYTHONDONTWRITEBYTECODE=1
set PATH=C:\Users\degiaian\AppData\Local\Programs\Python\Python312;C:\Users\degiaian\AppData\Local\Programs\Python\Python312\Scripts;%PATH%
set PATH=%PATH%;C:\Users\degiaian\ffmpeg\bin
call venv\Scripts\activate
python main.py