"""
auth_microsoft.py — Autenticacion Microsoft via Device Code Flow
Se ejecuta una sola vez para autorizar el bot.
Guarda el refresh token para no volver a pedir autorizacion.
No requiere app registration de empresa.
"""

import os
import json
import logging
import time
import requests
import urllib3
from datetime import datetime, timedelta
from pathlib import Path

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
log = logging.getLogger(__name__)

# Client ID publico de Microsoft Office — no requiere registro
# Es un app ID conocido que Microsoft permite usar para autenticacion delegada
CLIENT_ID = "d3590ed6-52b3-4102-aeff-aad2292ab01c"
SCOPES    = "https://graph.microsoft.com/Tasks.ReadWrite https://graph.microsoft.com/Group.Read.All offline_access"

TOKEN_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "ms_token.json"
)


def _guardar_token(datos: dict):
    """Guarda el token en disco."""
    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        json.dump(datos, f, indent=2)
    log.info("   Token guardado en ms_token.json")


def _cargar_token() -> dict:
    """Carga el token desde disco."""
    if not os.path.exists(TOKEN_FILE):
        return {}
    try:
        with open(TOKEN_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _refrescar_token(refresh_token: str, tenant_id: str) -> dict:
    """Usa el refresh token para obtener un nuevo access token sin interaccion."""
    resp = requests.post(
        f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token",
        data={
            "client_id":     CLIENT_ID,
            "grant_type":    "refresh_token",
            "refresh_token": refresh_token,
            "scope":         SCOPES,
        },
        verify=False,
        timeout=30,
    )

    if resp.status_code != 200:
        raise ValueError(f"Error refrescando token: {resp.status_code} — {resp.text[:200]}")

    return resp.json()


def obtener_token() -> str:
    """
    Retorna un access token valido.
    - Si hay token guardado y vigente: lo usa directamente
    - Si el token vencio: lo refresca automaticamente
    - Si no hay token: inicia el Device Code Flow (requiere accion del usuario)
    """
    datos = _cargar_token()

    # Verificar si hay token vigente
    if datos.get("access_token") and datos.get("expira_en"):
        expira = datetime.fromisoformat(datos["expira_en"])
        if datetime.now() < expira - timedelta(minutes=5):
            return datos["access_token"]

    # Intentar refrescar con el refresh token
    if datos.get("refresh_token") and datos.get("tenant_id"):
        try:
            log.info("   Refrescando token de Microsoft...")
            nuevos = _refrescar_token(datos["refresh_token"], datos["tenant_id"])
            datos["access_token"]  = nuevos["access_token"]
            datos["refresh_token"] = nuevos.get("refresh_token", datos["refresh_token"])
            datos["expira_en"]     = (datetime.now() + timedelta(seconds=nuevos.get("expires_in", 3600))).isoformat()
            _guardar_token(datos)
            log.info("   Token refrescado correctamente")
            return datos["access_token"]
        except Exception as e:
            log.warning(f"   No se pudo refrescar el token: {e}")

    # Iniciar Device Code Flow — requiere accion del usuario una sola vez
    return _device_code_flow()


def _device_code_flow() -> str:
    """
    Inicia el Device Code Flow.
    Muestra un codigo y URL al usuario, espera que lo ingrese en el navegador.
    """
    log.info("=" * 55)
    log.info("  AUTORIZACION DE MICROSOFT REQUERIDA")
    log.info("  (solo se hace una vez)")
    log.info("=" * 55)

    # Paso 1 — Solicitar el device code
    resp = requests.post(
        "https://login.microsoftonline.com/common/oauth2/v2.0/devicecode",
        data={
            "client_id": CLIENT_ID,
            "scope":     SCOPES,
        },
        verify=False,
        timeout=30,
    )

    if resp.status_code != 200:
        raise ValueError(f"Error iniciando autorizacion: {resp.status_code} — {resp.text[:200]}")

    datos_code = resp.json()
    device_code = datos_code["device_code"]
    intervalo   = datos_code.get("interval", 5)
    expira_en   = datos_code.get("expires_in", 900)

    # Mostrar instrucciones al usuario
    log.info(f"")
    log.info(f"  1. Abri este link en tu navegador:")
    log.info(f"     {datos_code['verification_uri']}")
    log.info(f"")
    log.info(f"  2. Ingresa este codigo: {datos_code['user_code']}")
    log.info(f"")
    log.info(f"  3. Logueate con tu cuenta corporativa")
    log.info(f"")
    log.info(f"  Esperando autorizacion (expira en {expira_en//60} minutos)...")

    # Mostrar tambien como notificacion de Windows
    try:
        from notificaciones import _notificar
        _notificar(
            "NoteTaker — Autorizar Microsoft",
            f"Abri microsoft.com/devicelogin\nCodigo: {datos_code['user_code']}",
            duracion=30,
        )
    except Exception:
        pass

    # Paso 2 — Polling hasta que el usuario autorice
    tiempo_inicio = time.time()
    while time.time() - tiempo_inicio < expira_en:
        time.sleep(intervalo)

        resp_token = requests.post(
            "https://login.microsoftonline.com/common/oauth2/v2.0/token",
            data={
                "client_id":   CLIENT_ID,
                "grant_type":  "urn:ietf:params:oauth:grant-type:device_code",
                "device_code": device_code,
            },
            verify=False,
            timeout=30,
        )

        datos_token = resp_token.json()

        if "access_token" in datos_token:
            # Exito — guardar token y refresh token
            tenant_id = _extraer_tenant_id(datos_token["access_token"])

            _guardar_token({
                "access_token":  datos_token["access_token"],
                "refresh_token": datos_token.get("refresh_token", ""),
                "tenant_id":     tenant_id,
                "expira_en":     (datetime.now() + timedelta(seconds=datos_token.get("expires_in", 3600))).isoformat(),
            })

            log.info("  Autorizacion exitosa. El bot ya puede crear tareas en Planner.")
            log.info("=" * 55)
            return datos_token["access_token"]

        error = datos_token.get("error", "")
        if error == "authorization_pending":
            continue  # usuario todavia no autorizo, seguir esperando
        elif error == "slow_down":
            intervalo += 5
            continue
        else:
            raise ValueError(f"Error en autorizacion: {datos_token.get('error_description', error)}")

    raise ValueError("Tiempo de autorizacion vencido. Reinicia el bot para intentar de nuevo.")


def _extraer_tenant_id(access_token: str) -> str:
    """Extrae el tenant ID del JWT sin verificar la firma."""
    try:
        import base64
        partes  = access_token.split(".")
        payload = partes[1] + "=="  # padding
        decoded = json.loads(base64.b64decode(payload))
        return decoded.get("tid", "common")
    except Exception:
        return "common"


def esta_autorizado() -> bool:
    """Retorna True si hay credenciales guardadas."""
    datos = _cargar_token()
    return bool(datos.get("refresh_token") or datos.get("access_token"))
