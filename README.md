# De la muñeca a la terminal: código del informe

Código que acompaña al artículo publicado en la revista USERS.

Control de un reloj genérico D20/Y68 (protocolo Lefun, nombre BLE `NM-BAND`) desde Python, sin la app oficial.

| Archivo | Para qué sirve |
|---|---|
| `escanear.py` | Lista los dispositivos BLE cercanos |
| `explorar.py` | Recorre los servicios GATT del reloj (solo lectura) |
| `lefun.py` | Protocolo: tramas, CRC y la clase `Reloj` |
| `consola.py` | Consola interactiva: batería, pasos, sensores, notificaciones |
| `acciones.py` | Acciones en la computadora: música, bloqueo y foto (macOS) |
| `escritorio.py` | Modo escritorio: control remoto, foto con la webcam, guardián y buzón de avisos |
| `avisar.py` | Envía un aviso al reloj a través de `escritorio.py` |

```
git clone https://github.com/ojedavd/reloj-inteligente-python.git
cd reloj-inteligente-python
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python escritorio.py
```

En otra terminal: `python avisar.py "Backup terminado"`.

Si tu reloj se anuncia con otro nombre, cambiá `NOMBRE` en `lefun.py`. En macOS, la terminal necesita permisos de Bluetooth, Cámara y Accesibilidad.
