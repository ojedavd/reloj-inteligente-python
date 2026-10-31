"""Acciones sobre la computadora (versión macOS)."""
import ctypes
import subprocess
from datetime import datetime
from pathlib import Path

CARPETA_FOTOS = Path.home() / "Pictures" / "reloj"
CAMARA_INDICE = 0  # 0 = webcam integrada

TECLA_PLAY, TECLA_SIGUIENTE, TECLA_ANTERIOR = (
    16, 17, 18)


def tecla_multimedia(tecla):
    """Simula una tecla multimedia del teclado.
    Requiere permiso de Accesibilidad."""
    import AppKit
    import Quartz

    if not Quartz.CGPreflightPostEventAccess():
        Quartz.CGRequestPostEventAccess()
        raise RuntimeError(
            "Falta el permiso de Accesibilidad")
    crear = getattr(
        AppKit.NSEvent,
        "otherEventWithType_location_modifierFlags_"
        "timestamp_windowNumber_context_subtype_"
        "data1_data2_")
    for estado in (0xA, 0xB):  # presionar, soltar
        evento = crear(
            14, (0, 0), estado << 8, 0, 0, None,
            8, (tecla << 16) | (estado << 8), -1)
        Quartz.CGEventPost(
            Quartz.kCGHIDEventTap, evento.CGEvent())


# Busca la ventana de Chrome con YouTube Music.
# Su título: "Tema | YouTube Music: ... - Google Chrome"
SCRIPT_TEMA = '''
tell application "System Events"
  repeat with pr in (every process ¬
      whose name is "Google Chrome")
    repeat with v in windows of pr
      if name of v contains "YouTube Music" then
        return name of v
      end if
    end repeat
  end repeat
end tell
return ""
'''


def tema_actual() -> str:
    """Nombre del tema que suena en YouTube Music."""
    r = subprocess.run(["osascript", "-e", SCRIPT_TEMA],
                       capture_output=True, text=True,
                       timeout=5)
    titulo = r.stdout.strip()
    if " | YouTube Music" not in titulo:
        return ""
    return titulo.split(" | YouTube Music")[0]


def bloquear_pantalla():
    ruta = ("/System/Library/PrivateFrameworks/"
            "login.framework/Versions/Current/login")
    ctypes.CDLL(ruta).SACLockScreenImmediate()


def sacar_foto() -> Path:
    """Captura una imagen con la webcam y
    devuelve la ruta del archivo guardado."""
    import cv2

    camara = cv2.VideoCapture(CAMARA_INDICE)
    try:
        if not camara.isOpened():
            raise RuntimeError("No pude abrir la cámara")
        # Los primeros cuadros salen oscuros:
        # la cámara todavía ajusta la exposición
        for _ in range(15):
            camara.read()
        ok, imagen = camara.read()
        if not ok:
            raise RuntimeError("La cámara no respondió")
        CARPETA_FOTOS.mkdir(parents=True, exist_ok=True)
        nombre = f"{datetime.now():%Y%m%d_%H%M%S}.jpg"
        ruta = CARPETA_FOTOS / nombre
        cv2.imwrite(str(ruta), imagen)
        return ruta
    finally:
        camara.release()
