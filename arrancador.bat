@echo off
cd /d "C:\Users\degiaian\OneDrive - ASE Conecta\Documentos\PMO\NoteTaker"
set PYTHONIOENCODING=utf-8
set PATH=C:\Users\degiaian\AppData\Local\Programs\Python\Python312;C:\Users\degiaian\AppData\Local\Programs\Python\Python312\Scripts;%PATH%
set PATH=%PATH%;C:\Users\degiaian\ffmpeg\bin
call venv\Scripts\activate
python main.py