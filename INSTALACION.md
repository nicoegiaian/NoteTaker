# ============================================================
#  GUÍA DE INSTALACIÓN PASO A PASO — Meeting Notes Bot
#  Para Windows. Sin conocimientos de programación requeridos.
# ============================================================


## PASO 1 — Instalar Python
─────────────────────────────────────────────────────
1. Abrí tu navegador y andá a: https://www.python.org/downloads/
2. Hacé clic en el botón amarillo "Download Python 3.11.x"
3. Ejecutá el instalador descargado
4. ⚠️ IMPORTANTE: Marcá la casilla "Add Python to PATH" antes de hacer clic en Install
5. Hacé clic en "Install Now"
6. Para verificar: abrí el menú inicio, escribí "cmd", abrí la terminal y escribí:
   python --version
   Deberías ver algo como: Python 3.11.9


## PASO 2 — Instalar ffmpeg (necesario para que Whisper procese audio)
─────────────────────────────────────────────────────
1. Andá a: https://www.gyan.dev/ffmpeg/builds/
2. Descargá "ffmpeg-release-essentials.zip"
3. Descomprimí el archivo en C:\ffmpeg
4. Abrí el menú inicio → escribí "variables de entorno" → "Editar las variables de entorno del sistema"
5. Hacé clic en "Variables de entorno"
6. En "Variables del sistema", buscá "Path" → hacé doble clic
7. Hacé clic en "Nuevo" y escribí: C:\ffmpeg\bin
8. Aceptá todo
9. Para verificar (abrí una terminal nueva):
   ffmpeg -version


## PASO 3 — Descargar el bot
─────────────────────────────────────────────────────
1. Creá una carpeta en tu PC, por ejemplo: C:\MeetingNotesBot
2. Copiá todos los archivos del proyecto dentro de esa carpeta:
   - main.py
   - config.py
   - transcriber.py
   - ai_processor.py
   - output_generator.py
   - requirements.txt
   - .env.template


## PASO 4 — Configurar credenciales
─────────────────────────────────────────────────────
1. En la carpeta del proyecto, renombrá ".env.template" a ".env"
2. Abrilo con el Bloc de Notas
3. Completá los tres valores:

   a) ANTHROPIC_API_KEY
      - Abrí https://console.anthropic.com/
      - Creá una cuenta (es gratis crear la cuenta)
      - Andá a "API Keys" → "Create Key"
      - Copiá la key y pegala en el .env

   b) ONEDRIVE_RECORDINGS_PATH
      - Abrí el Explorador de archivos
      - Navegá hasta la carpeta donde ves las grabaciones de Teams
      - Copiá la ruta desde la barra de direcciones
      - Pegala en el .env (reemplazando las barras \ con \\)

   c) OUTPUT_FOLDER
      - Puede ser tu escritorio u otra carpeta que prefieras
      - Ejemplo: C:\\Users\\TuNombre\\Desktop\\NotasReuniones


## PASO 5 — Configurar tus proyectos
─────────────────────────────────────────────────────
1. Abrí config.py con el Bloc de Notas (o VS Code)
2. Editá el diccionario PROYECTOS con los nombres de TUS proyectos
3. La clave debe coincidir con lo que aparece en los nombres de tus reuniones
   Ejemplo: si tus reuniones se llaman "Reunión ERP Semanal", la clave sería "ERP"


## PASO 6 — Instalar las dependencias de Python
─────────────────────────────────────────────────────
1. Abrí una terminal (cmd) en la carpeta del proyecto:
   - Abrí el Explorador de archivos en la carpeta del bot
   - Mantenés presionado Shift + clic derecho → "Abrir ventana de PowerShell aquí"
2. Ejecutá este comando:
   pip install -r requirements.txt
3. Esperá a que termine (puede tardar 5-10 minutos, descarga Whisper)
4. ⚠️ Si tenés GPU NVIDIA, también ejecutá:
   pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118


## PASO 7 — Primer arranque
─────────────────────────────────────────────────────
1. En la misma terminal, ejecutá:
   python main.py
2. Deberías ver:
   ═══════════════════════════════════════════════════════
     🚀  Meeting Notes Bot — Iniciado
     📁  Monitoreando: [tu ruta]
     💾  Output en:    [tu ruta]
     Para detener: Ctrl + C
   ═══════════════════════════════════════════════════════
3. ¡El bot está activo! Podés minimizar la ventana.


## PASO 8 — Probar con una grabación existente
─────────────────────────────────────────────────────
Para testear sin esperar una reunión nueva:
1. Dejá el bot corriendo (o lo detenés con Ctrl+C)
2. Copiá un .mp4 de Teams a la carpeta monitoreada
3. El bot lo detecta y empieza a procesar automáticamente
4. En ~5-20 minutos (depende del largo y tu PC), aparecerá el HTML en OUTPUT_FOLDER


## AUTOMATIZAR EL ARRANQUE (opcional)
─────────────────────────────────────────────────────
Para que el bot arranque automáticamente cuando encendés la PC:
1. Creá un archivo "arrancar_bot.bat" con este contenido:
   @echo off
   cd C:\MeetingNotesBot
   python main.py
2. Copiá ese archivo a:
   C:\Users\TuNombre\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup


## CÓMO USAR EL OUTPUT EN LOOP
─────────────────────────────────────────────────────
1. El bot genera un archivo .html en tu OUTPUT_FOLDER
2. Abrilo con cualquier navegador (doble clic)
3. Hacé clic en el botón azul "Copiar todo para pegar en Loop"
4. Andá a tu workspace de Loop en el proyecto correspondiente
5. Creá una nueva página
6. Pegá el contenido (Ctrl+V)
7. ¡Listo! Las notas quedan perfectamente formateadas.


## SOLUCIÓN DE PROBLEMAS COMUNES
─────────────────────────────────────────────────────

❌ "python no se reconoce como comando"
   → Python no está en el PATH. Reinstalalo marcando "Add to PATH"

❌ "ffmpeg no se reconoce como comando"  
   → ffmpeg no está configurado. Revisá el Paso 2.

❌ "Error: ANTHROPIC_API_KEY no encontrada"
   → El archivo .env no está en la carpeta correcta o le falta la key

❌ La transcripción está en inglés aunque la reunión es en español
   → En config.py, asegurate de tener: IDIOMA_REUNIONES = "es"

❌ El bot es muy lento transcribiendo
   → En config.py, cambiá: WHISPER_MODEL = "base" (más rápido, un poco menos preciso)
   → O si tenés GPU NVIDIA: WHISPER_MODEL = "small" con aceleración GPU

❌ No detecta el proyecto correcto
   → Revisá que la clave en PROYECTOS coincida con el nombre real de la reunión
   → Mirá el archivo meeting_notes.log para ver qué detectó
