"""Lista los dispositivos BLE cercanos.

Uso: python escanear.py
"""
import asyncio

from bleak import BleakScanner


async def main():
    print("Escaneando durante 10 segundos...")
    hallados = await BleakScanner.discover(
        timeout=10, return_adv=True)
    ordenados = sorted(hallados.values(),
                       key=lambda x: -x[1].rssi)
    for disp, anuncio in ordenados:
        nombre = disp.name or "(sin nombre)"
        print(f"{anuncio.rssi:4} dBm  {nombre:20}"
              f"  {disp.address}")
        for cod, datos in \
                anuncio.manufacturer_data.items():
            print(f"      fabricante {cod:#06x}:"
                  f" {datos.hex(' ')}")


asyncio.run(main())
