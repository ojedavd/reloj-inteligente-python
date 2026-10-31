"""Recorre los servicios GATT del reloj (solo lectura).

Uso: python explorar.py
"""
import asyncio

from bleak import BleakClient

from lefun import buscar_reloj


async def main():
    dispositivo = await buscar_reloj()
    if not dispositivo:
        print("No encontré el reloj.")
        return
    async with BleakClient(dispositivo) as cliente:
        for servicio in cliente.services:
            print(f"\nServicio {servicio.uuid}"
                  f"  {servicio.description}")
            for car in servicio.characteristics:
                props = ",".join(car.properties)
                print(f"  {car.uuid}  [{props}]")
                if "read" not in car.properties:
                    continue
                try:
                    valor = await cliente.\
                        read_gatt_char(car)
                    print(f"      = {valor.hex(' ')}"
                          f"  {valor!r}")
                except Exception as e:
                    print(f"      (no se pudo leer: {e})")


asyncio.run(main())
