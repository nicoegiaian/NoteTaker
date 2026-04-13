import logging
import os
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

os.chdir(r"C:\Users\degiaian\OneDrive - ASE Conecta\Documentos\PMO\NoteTaker")

from dotenv import load_dotenv
load_dotenv()

import os
print("API KEY:", os.getenv("ANTHROPIC_API_KEY")[:10] if os.getenv("ANTHROPIC_API_KEY") else "NO ENCONTRADA")
print("WEBHOOK:", os.getenv("TEAMS_WEBHOOK_URL")[:30] if os.getenv("TEAMS_WEBHOOK_URL") else "NO ENCONTRADA")

from proyecto_watcher import procesar_archivo, leer_contenido, detectar_proyecto

ruta = r"C:\Users\degiaian\OneDrive - ASE Conecta\CORPO - Gerencia de Proyectos Corporativos - Proyectos en curso\DevSecOps\6- Adopción\Apigee\Requisitos_OpenAPI_Apigee.docx"

print("Extensión:", os.path.splitext(ruta)[1])
print("Proyecto detectado:", detectar_proyecto(ruta))
print("Leyendo contenido...")
contenido = leer_contenido(ruta)
print("Contenido (primeros 200 chars):", contenido[:200] if contenido else "VACÍO")


print("Procesando archivo completo...")
procesar_archivo(ruta, "subió")
print("Listo.")
