"""Manda un aviso al reloj a través de escritorio.py.

Uso: python avisar.py "Backup terminado"
"""
import socket
import sys

PUERTO = 8765

texto = " ".join(sys.argv[1:]) or "Listo"
try:
    with socket.create_connection(
            ("127.0.0.1", PUERTO), timeout=5) as s:
        s.sendall(texto.encode() + b"\n")
        print(s.recv(64).decode().strip())
except OSError:
    sys.exit("escritorio.py no está corriendo.")
