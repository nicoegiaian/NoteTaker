# ============================================================
#  CONFIG.PY — Este es el único archivo que vas a editar
#              con frecuencia. Sin tocar código.
# ============================================================

# ----------------------------------------------------------
# MODELO DE WHISPER
# ----------------------------------------------------------
WHISPER_MODEL = "base"

# ----------------------------------------------------------
# IDIOMA DE LAS REUNIONES
# ----------------------------------------------------------
IDIOMA_REUNIONES = "es"

# ----------------------------------------------------------
# PROYECTOS
# Formato: "palabra clave en nombre de reunión" : "nombre del proyecto"
# IMPORTANTE: el valor debe coincidir EXACTAMENTE con el nombre
# del plan en Microsoft Planner (mayúsculas, espacios, tildes)
# ----------------------------------------------------------
PROYECTOS = {
    # Programa Salesforce — múltiples claves que apuntan al mismo plan
    "Salesforce":    "Programa Salesforce",
    "NICE":          "Programa Salesforce",
    "Ola 0":         "Programa Salesforce",
    "Ola0":          "Programa Salesforce",
    "Ola 1":         "Programa Salesforce",
    "Ola1":          "Programa Salesforce",

    # Otros proyectos — nombre exacto igual al plan en Planner
    "Monitoreo":     "Monitoreo",
    "Obsolescencia": "Obsolescencia",
    "DevSecOps":     "DevSecOps",
    "WURU":          "WURU Finochietto",
    "Finochietto":   "WURU Finochietto",
}

# Nombre que aparece si no se detecta ningún proyecto conocido
PROYECTO_DESCONOCIDO = "Sin Proyecto Asignado"

# ----------------------------------------------------------
# COMPORTAMIENTO DEL MONITOR
# ----------------------------------------------------------
ESPERA_SINCRONIZACION_SEG = 120  # 2 minutos

# ----------------------------------------------------------
# PLANNER
# Mapeo de nombre de proyecto → ID del plan en Planner
# Se completa automáticamente la primera vez que el bot
# se conecta a Planner. No editar manualmente.
# ----------------------------------------------------------
PLANNER_PLANES = {
    "DevSecOps": "QNz1pTxlGkWflbBOgjeZbmQADnjD",
    "Programa Salesforce": "lmWVA6a6uEWMb6ks2z4Z0mQABVNT",
    "Monitoreo": "75EuHZ6p50iXx0jiDdU-cWQACWAY",
    "Obsolescencia": "nEj_feGLd0GvDeVGf4ZcDGQAAv-W",
    "WURU Finochietto": "AZ-lGAVN9kO0vDbGOe0WtWQAClXH"
}
