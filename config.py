# ============================================================
#  CONFIG.PY — Este es el único archivo que vas a editar
#              con frecuencia. Sin tocar código.
# ============================================================

# ----------------------------------------------------------
# MODELO DE WHISPER
# Opciones y su impacto en tu PC:
#   "tiny"   → rapidísimo, calidad básica
#   "base"   → rápido, buena calidad        ← recomendado sin GPU
#   "small"  → equilibrado, mejor calidad   ← recomendado con GPU
#   "medium" → lento en CPU, excelente calidad
# ----------------------------------------------------------
WHISPER_MODEL = "base"  # Cambiá a "small" si tenés GPU NVIDIA

# ----------------------------------------------------------
# IDIOMA DE LAS REUNIONES
# "es" = español | "en" = inglés | None = detección automática
# Especificarlo acelera la transcripción y mejora la calidad
# ----------------------------------------------------------
IDIOMA_REUNIONES = "es"

# ----------------------------------------------------------
# PROYECTOS
# Formato: "palabra clave en nombre de reunión" : "nombre del proyecto"
# El sistema busca estas palabras en el título de la reunión
# No distingue mayúsculas/minúsculas
# ----------------------------------------------------------
PROYECTOS = {
    "Salesforce":        "Programa Salesforce",
    "NICE":        "Programa Salesforce",
    "Ola 0":        "Programa Salesforce",
    "Ola0":        "Programa Salesforce",
    "Ola 1":        "Programa Salesforce",
    "Ola1":        "Programa Salesforce",
    "Monitoreo":         "Proyecto Monitoreo",
    "Obsolescencia":        "Proyecto Obsolescencia",
    "DevSecOps":          "Proyecto DevSecOps",
    # Agregá tus proyectos acá ↑
}

# Nombre que aparece si no se detecta ningún proyecto conocido
PROYECTO_DESCONOCIDO = "Sin Proyecto Asignado"

# ----------------------------------------------------------
# COMPORTAMIENTO DEL MONITOR
# Tiempo en segundos que espera antes de procesar un archivo
# nuevo (para asegurarse de que terminó de sincronizarse)
# ----------------------------------------------------------
ESPERA_SINCRONIZACION_SEG = 120  # 2 minutos
