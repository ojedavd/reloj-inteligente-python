"""Protocolo Lefun para relojes genéricos D20/Y68.

Pedido:    AB <largo> <cmd> <params...> <crc>
Respuesta: 5A <largo> <cmd> <params...> <crc>
"""
import asyncio
import struct
import sys
import unicodedata

from bleak import BleakScanner

NOMBRE = "NM-BAND"
SERVICIO = "18D0"
ESCRITURA = "00002d01-0000-1000-8000-00805f9b34fb"
NOTIFICA = "00002d00-0000-1000-8000-00805f9b34fb"

# Comandos del protocolo
FIRMWARE = 0x00
BATERIA = 0x03
HORA = 0x04
PERFIL = 0x06
BUSCAR_RELOJ = 0x09
BUSCAR_TEL = 0x0A
CAMARA = 0x0D
DISPARADOR = 0x0E
MEDIR = 0x0F
RESULTADO = 0x10
PASOS = 0x12
NOTIFICACION = 0x17
MUSICA = 0x27

LEER, ESCRIBIR = 0, 1

# Mensajes que el reloj manda por iniciativa propia
EVENTOS = {BUSCAR_TEL, DISPARADOR, MUSICA}

# Máscaras de las mediciones de salud
SENSORES = {"pulso": 1, "presion": 2, "oxigeno": 4}

# La fuente del reloj no tiene emojis: se
# reemplazan por equivalentes en texto
EMOJIS = {
    "❤️": "<3", "❤": "<3", "😀": ":D",
    "😂": "XD", "🙂": ":)", "😉": ";)",
    "😢": ":'(", "👍": "(Y)", "✅": "[v]",
    "❌": "[x]", "🔥": "(fuego)",
}
SIN_ACENTOS = False  # True si tu modelo no los muestra


def crc8(datos: bytes) -> int:
    """CRC-8/Maxim: polinomio 0x31 reflejado."""
    crc = 0
    for byte in datos:
        crc ^= byte
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0x8C
            else:
                crc >>= 1
    return crc


def armar_trama(cmd: int, params=b"") -> bytes:
    cuerpo = bytes([0xAB, len(params) + 4, cmd])
    cuerpo += bytes(params)
    return cuerpo + bytes([crc8(cuerpo)])


def leer_trama(datos: bytes):
    """Valida una respuesta: (cmd, params) o None."""
    if len(datos) < 4 or datos[0] != 0x5A:
        return None
    largo = datos[1]
    if largo > len(datos):
        return None
    if crc8(datos[:largo - 1]) != datos[largo - 1]:
        return None
    return datos[2], bytes(datos[3:largo - 1])


def texto_reloj(texto: str) -> bytes:
    for emoji, simple in EMOJIS.items():
        texto = texto.replace(emoji, simple)
    if SIN_ACENTOS:
        texto = unicodedata.normalize("NFKD", texto)
        texto = texto.encode("ascii", "ignore")
        texto = texto.decode()
    return texto.encode()[:254]


async def buscar_reloj(espera=20.0):
    """Encuentra el reloj, aunque macOS ya lo
    tenga conectado y no se esté anunciando."""
    if sys.platform == "darwin":
        from bleak.backends.corebluetooth import (
            CentralManagerDelegate as cb)
        from bleak.backends.device import BLEDevice
        from CoreBluetooth import CBUUID

        gestor = cb.CentralManagerDelegate()
        await gestor.wait_until_ready()
        uuid = CBUUID.UUIDWithString_(SERVICIO)
        central = gestor.central_manager
        conectados = central.\
            retrieveConnectedPeripheralsWithServices_(
                [uuid])
        for p in conectados:
            if p.name() == NOMBRE:
                return BLEDevice(
                    p.identifier().UUIDString(),
                    p.name(), (p, gestor))
    return await BleakScanner.find_device_by_name(
        NOMBRE, timeout=espera)


class Reloj:
    def __init__(self, cliente):
        self.cliente = cliente
        self.respuestas = asyncio.Queue()
        self.al_evento = None  # función(cmd, params)

    async def iniciar(self):
        await self.cliente.start_notify(
            NOTIFICA, self._recibir)

    def _recibir(self, _, datos):
        trama = leer_trama(bytes(datos))
        if trama is None:
            return
        cmd, params = trama
        if self.al_evento:
            self.al_evento(cmd, params)
        if cmd not in EVENTOS:
            self.respuestas.put_nowait(trama)

    async def enviar(self, cmd, params=b"",
                     esperar=True, espera=5.0):
        while not self.respuestas.empty():
            self.respuestas.get_nowait()
        await self.cliente.write_gatt_char(
            ESCRITURA, armar_trama(cmd, params),
            response=False)
        if esperar:
            return await self.esperar(cmd, espera)

    async def esperar(self, cmd, espera):
        bucle = asyncio.get_running_loop()
        limite = bucle.time() + espera
        while (resto := limite - bucle.time()) > 0:
            try:
                got, params = await asyncio.wait_for(
                    self.respuestas.get(), resto)
            except asyncio.TimeoutError:
                break
            if got == cmd:
                return params
        return None

    # --- Funciones de alto nivel ---------------

    async def bateria(self):
        p = await self.enviar(BATERIA)
        return p[0] if p else None

    async def firmware(self):
        p = await self.enviar(FIRMWARE)
        if not p or len(p) < 16:
            return None
        hw, sw = struct.unpack(">HH", p[8:12])
        return {
            "modelo": p[4:8].decode(errors="replace"),
            "hardware": f"{hw >> 8}.{hw & 0xFF:02d}",
            "software": f"V{sw >> 8}.{sw & 0xFF:02d}",
            "fabricante":
                p[12:16].decode(errors="replace"),
        }

    async def poner_hora(self, ahora):
        p = await self.enviar(HORA, bytes([
            ESCRIBIR, ahora.year - 2000, ahora.month,
            ahora.day, ahora.hour, ahora.minute,
            ahora.second]))
        return bool(p) and p[1] == 1

    async def perfil(self, hombre, cm, kg, edad):
        p = await self.enviar(PERFIL, bytes([
            ESCRIBIR, int(hombre), cm, kg, edad]))
        return bool(p) and p[1] == 1

    async def pasos(self, dias_atras=0):
        p = await self.enviar(
            PASOS, bytes([dias_atras]))
        if not p or len(p) < 16:
            return None
        return struct.unpack(">III", p[4:16])

    async def medir(self, sensor):
        """Mide pulso, presión u oxígeno.
        El reloj tarda entre 30 y 60 segundos."""
        mascara = SENSORES[sensor]
        p = await self.enviar(MEDIR, bytes([mascara]))
        if not p or p[1] != 1:
            return None
        r = await self.esperar(RESULTADO, 90)
        if not r:
            return None
        if sensor == "presion":
            return r[1], r[2]
        return r[1]

    async def vibrar(self):
        await self.enviar(BUSCAR_RELOJ)

    async def notificar(self, texto, llamada=False):
        datos = texto_reloj(texto)
        partes = [datos[i:i + 13]
                  for i in range(0, len(datos), 13)]
        partes = partes or [b""]
        tipo = 1 if llamada else 2
        for n, parte in enumerate(partes, 1):
            cabecera = bytes([tipo, len(partes), n])
            await self.enviar(NOTIFICACION,
                              cabecera + parte,
                              esperar=False)
            await asyncio.sleep(0.05)

    async def modo_camara(self, activo=True):
        await self.enviar(CAMARA, bytes([activo]))
