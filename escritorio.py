"""Modo escritorio: control remoto, foto y guardián.

Uso: python escritorio.py
"""
import asyncio
import statistics
import time
from collections import deque
from datetime import datetime

from bleak import BleakClient

import acciones
import lefun
from lefun import Reloj, buscar_reloj

GUARDIAN = True  # bloquear al alejarse
CAIDA = 8        # dB bajo la señal habitual = lejos
VENTANA = 60     # segundos de señal habitual
GRACIA = 20      # segundos sin conexión
LECTURAS = 5     # mediana de las últimas lecturas
PUERTO = 8765    # buzón de avisos
MOSTRAR_SENAL = False  # True para calibrar

BOTONES_MUSICA = {
    0x01: acciones.TECLA_PLAY,
    0x02: acciones.TECLA_SIGUIENTE,
    0x03: acciones.TECLA_ANTERIOR,
}


def log(texto):
    print(f"{datetime.now():%H:%M:%S} {texto}",
          flush=True)


class Escritorio:
    def __init__(self):
        self.reloj = None
        self.ausente_desde = None
        self.bloqueada = False
        self.aviso = ""
        self.habitual = deque(maxlen=VENTANA)
        self.aviso_pendiente = False
        self.tareas = set()

    # --- Eventos que llegan desde el reloj -----

    def al_evento(self, cmd, params):
        if cmd == lefun.MUSICA and params:
            log(f"Música: botón {params[0]:#04x}")
            tecla = BOTONES_MUSICA.get(params[0])
            if tecla is not None:
                self.intentar(acciones.tecla_multimedia,
                              tecla)
                self.en_segundo_plano(self.mostrar_tema())
        elif cmd == lefun.DISPARADOR:
            self.en_segundo_plano(self.foto())
        elif cmd == lefun.BUSCAR_TEL:
            log("Bloqueo pedido desde el reloj")
            self.intentar(acciones.bloquear_pantalla)
        elif cmd == lefun.CAMARA and params == b"\0":
            log("Se cerró la cámara en el reloj")

    def intentar(self, accion, *args):
        try:
            accion(*args)
        except Exception as e:
            log(f"Error: {e}")

    def en_segundo_plano(self, corrutina):
        tarea = asyncio.create_task(corrutina)
        self.tareas.add(tarea)
        tarea.add_done_callback(self.tareas.discard)

    async def foto(self):
        try:
            ruta = await asyncio.to_thread(
                acciones.sacar_foto)
        except Exception as e:
            log(f"Error en la foto: {e}")
            await self.avisar("Error camara")
            return
        log(f"Foto guardada: {ruta}")
        await self.avisar("Foto OK")

    async def mostrar_tema(self):
        await asyncio.sleep(2)  # que cargue el tema
        try:
            tema = await asyncio.to_thread(
                acciones.tema_actual)
        except Exception as e:
            log(f"No pude leer el tema: {e}")
            return
        if tema:
            log(f"Sonando: {tema}")
            await self.avisar(tema)

    async def avisar(self, texto):
        reloj = self.reloj
        if reloj and reloj.cliente.is_connected:
            await reloj.notificar(texto)
            return True
        return False

    # --- Conexión y guardián -------------------

    async def sesion(self, dispositivo):
        cortado = asyncio.Event()
        try:
            async with BleakClient(
                dispositivo,
                disconnected_callback=lambda _:
                    cortado.set(),
            ) as cliente:
                self.reloj = Reloj(cliente)
                self.reloj.al_evento = self.al_evento
                await self.reloj.iniciar()
                await self.reloj.modo_camara(False)
                await self.reloj.poner_hora(
                    datetime.now())
                bateria = await self.reloj.bateria()
                log(f"Conectado. Batería: {bateria}%")
                await self.medir_distancia(
                    cliente, cortado)
        finally:
            if self.reloj:  # hubo conexión
                log("Se perdió la conexión")
                if self.ausente_desde is None:
                    self.ausente_desde = \
                        time.monotonic()
            self.reloj = None

    async def medir_distancia(self, cliente, cortado):
        """Estima la distancia con la intensidad
        de la señal (RSSI) mientras hay conexión."""
        lecturas = deque(maxlen=LECTURAS)
        fallos = 0
        while (not cortado.is_set()
               and cliente.is_connected):
            try:
                rssi = await asyncio.wait_for(
                    cliente._backend.get_rssi(), 3)
                lecturas.append(rssi)
                fallos = 0
            except (AttributeError,
                    NotImplementedError):
                # Sin RSSI: la conexión es la señal
                await self.volvio()
            except Exception:
                # Una conexión muerta puede no avisar
                fallos += 1
                if fallos >= 5:
                    log("El reloj dejó de responder")
                    return
            if len(lecturas) == LECTURAS:
                senal = statistics.median(lecturas)
                if not self.bloqueada or not self.habitual:
                    self.habitual.append(senal)
                umbral = max(self.habitual) - CAIDA
                if MOSTRAR_SENAL:
                    log(f"Señal: {senal} dBm "
                        f"(umbral {umbral})")
                if senal >= umbral:
                    await self.volvio()
                else:
                    await self.bloquear(
                        f"Señal débil ({senal} dBm)")
            try:
                await asyncio.wait_for(
                    cortado.wait(), 1)
            except asyncio.TimeoutError:
                pass

    async def volvio(self):
        if self.bloqueada:
            log("El reloj volvió")
            if self.aviso_pendiente:
                await self.avisar_bloqueo()
        self.ausente_desde = None
        self.bloqueada = False

    async def bloquear(self, motivo):
        if not GUARDIAN or self.bloqueada:
            return
        log(f"{motivo}: bloqueando")
        self.intentar(acciones.bloquear_pantalla)
        self.bloqueada = True
        hora = f"{datetime.now():%H:%M}"
        self.aviso = f"Bloqueada a las {hora}"
        self.aviso_pendiente = True
        if self.reloj:  # la cámara taparía el aviso
            await self.reloj.modo_camara(False)
        await self.avisar_bloqueo()

    async def avisar_bloqueo(self):
        # Sin conexión, el aviso espera al regreso
        if await self.avisar(self.aviso):
            self.aviso_pendiente = False

    async def revisar_ausencia(self):
        if self.ausente_desde is None:
            return
        ausente = time.monotonic() - self.ausente_desde
        if ausente >= GRACIA:
            await self.bloquear("Sin conexión")

    async def vigilar(self):
        while True:
            await self.revisar_ausencia()
            try:
                dispositivo = await buscar_reloj(5)
                if dispositivo:
                    await self.sesion(dispositivo)
            except Exception as e:
                log(f"Error de conexión: {e}")
                await asyncio.sleep(2)

    # --- Buzón de avisos -----------------------

    async def atender(self, lector, escritor):
        linea = await lector.readline()
        texto = linea.decode(errors="replace").strip()
        ok = bool(texto) and await self.avisar(texto)
        log(f"Aviso: {texto!r} -> "
            + ("enviado" if ok else "sin reloj"))
        escritor.write(b"ok\n" if ok
                       else b"sin reloj\n")
        await escritor.drain()
        escritor.close()


async def main():
    escritorio = Escritorio()
    try:
        servidor = await asyncio.start_server(
            escritorio.atender, "127.0.0.1", PUERTO)
    except OSError:
        raise SystemExit("Ya hay otra copia corriendo.")
    async with servidor:
        log(f"Buzón de avisos en el puerto {PUERTO}")
        await escritorio.vigilar()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
