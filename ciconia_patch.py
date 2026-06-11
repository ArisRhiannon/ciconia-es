# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Ciconia es-419 translation project contributors.
#
# This file is part of ciconia-es419-patch.
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU Affero General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version. This program is distributed WITHOUT ANY WARRANTY. You should
# have received a copy of the license along with it; if not, see
# <https://www.gnu.org/licenses/>.
"""
ciconia_patch.py - Instalador del parche de traducción es-419 (solo texto), por consola.

¿Prefieres algo visual? Usa la interfaz gráfica `ciconia_patch_gui.py` (o el .exe).
Esta CLI y la GUI comparten la MISMA lógica probada (patcher/installer.py).

Genera un `0.utf` en español a partir de TU copia legal del juego. No modifica
ningún archivo original: crea una obra derivada nueva que el motor carga con
prioridad. Distribuye e instala SOLO este parche, nunca los archivos del juego.

Uso típico:
    python ciconia_patch.py                 # autodetecta el juego e instala
    python ciconia_patch.py --game-dir RUTA # indica la carpeta del juego a mano
    python ciconia_patch.py --dry-run       # simula, no escribe nada
    python ciconia_patch.py --uninstall     # restaura el 0.utf previo (si hay respaldo)
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from patcher import core, installer  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PATCHES_DIR = os.path.join(HERE, "patches")


def install(args):
    try:
        res = installer.run_install(
            args.game_dir, patch_path=args.patch, patches_dir=args.patches_dir,
            output=args.output, xor_key=args.xor_key, no_stamp=args.no_stamp,
            no_title=args.no_title, complete=args.complete, dry_run=args.dry_run,
            log=print)
    except installer.InstallError as e:
        print(str(e))
        return e.code
    if not args.dry_run and res.get("wrote"):
        print("Listo. Inicia el juego; el texto en español se cargará con prioridad.")
        print('Para revertir:  python ciconia_patch.py --uninstall --game-dir "%s"'
              % res["game_dir"])
    return 0


def uninstall(args):
    try:
        installer.run_uninstall(args.game_dir, output=args.output, log=print)
    except installer.InstallError as e:
        print(str(e))
        return e.code
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description="Instalador del parche es-419 de Ciconia (solo texto).")
    p.add_argument("--game-dir", help="Carpeta del juego (si no, se autodetecta).")
    p.add_argument("--patch", help="Ruta a un es_patch.json específico (si no, se elige por versión).")
    p.add_argument("--patches-dir", default=DEFAULT_PATCHES_DIR, help="Carpeta con los bundles de parche.")
    p.add_argument("--output", help="Ruta de salida del 0.utf (por defecto, dentro del juego).")
    p.add_argument("--xor-key", type=lambda s: int(s, 0), default=core.DEFAULT_XOR_KEY,
                   help="Clave XOR del script (por defecto 0x84).")
    p.add_argument("--no-stamp", action="store_true", help="No anexar el banner de licencia.")
    p.add_argument("--no-title", action="store_true", help="No cambiar el título de la ventana.")
    p.add_argument("--complete", action="store_true",
                   help="Forzar cobertura máxima (rellena líneas idénticas vía hash, "
                        "aunque no se hayan revisado en contexto).")
    p.add_argument("--dry-run", action="store_true", help="Simular sin escribir.")
    p.add_argument("--uninstall", action="store_true", help="Restaurar el 0.utf previo.")
    args = p.parse_args(argv)

    try:
        return uninstall(args) if args.uninstall else install(args)
    except FileNotFoundError as e:
        print("Error: archivo no encontrado:", e)
        return 1
    except Exception as e:  # noqa: BLE001
        print("Error inesperado:", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
