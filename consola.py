"""Consola para hablar con el reloj desde la terminal.

Uso: python consola.py
"""
import asyncio
from datetime import datetime

from bleak import BleakClient

from lefun import Reloj, buscar_reloj

AYUDA = """
  bat              nivel de batería
  info             modelo y firmware
  hora             pone la hora de la computadora
  perfil h|m cm kg edad
  pasos [días]     0 = hoy, 1 = ayer...
  pulso | presion | oxigeno
  vibrar           hace vibrar el reloj
  msg <texto>      notificación de texto
  llamada <texto>  simula una llamada entrante
  salir
"""


async def ejecutar(reloj, orden, arg):
    if orden == "bat":
        print(f"Batería: {await reloj.bateria()}%")
    elif orden == "info":
        print(await reloj.firmware())
    elif orden == "hora":
        ok = await reloj.poner_hora(datetime.now())
        print("Hora configurada" if ok else "Falló")
    elif orden == "perfil":
        sexo, cm, kg, edad = arg.split()
        ok = await reloj.perfil(
            sexo == "h", int(cm), int(kg), int(edad))
        print("Perfil guardado" if ok else "Falló")
    elif orden == "pasos":
        datos = await reloj.pasos(int(arg or 0))
        if datos:
            pasos, metros, cal = datos
            print(f"{pasos} pasos, {metros} m, "
                  f"{cal} kcal")
    elif orden in ("pulso", "presion", "oxigeno"):
        print("Midiendo, no muevas el reloj...")
        print(await reloj.medir(orden))
    elif orden == "vibrar":
        await reloj.vibrar()
    elif orden == "msg":
        await reloj.notificar(arg)
    elif orden == "llamada":
        await reloj.notificar(arg, llamada=True)
    else:
        print(AYUDA)


async def main():
    dispositivo = await buscar_reloj()
    if not dispositivo:
        print("No encontré el reloj.")
        return
    async with BleakClient(dispositivo) as cliente:
        reloj = Reloj(cliente)
        await reloj.iniciar()
        print(f"Conectado a {dispositivo.name}")
        print(AYUDA)
        while cliente.is_connected:
            linea = await asyncio.to_thread(
                input, "reloj> ")
            orden, _, arg = linea.strip().partition(" ")
            if orden == "salir":
                break
            try:
                await ejecutar(reloj, orden, arg.strip())
            except ValueError:
                print("Argumentos inválidos.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, EOFError):
        pass
