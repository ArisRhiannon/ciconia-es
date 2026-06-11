# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Ciconia es-419 translation project contributors.
# Part of ciconia-es419-patch. See <https://www.gnu.org/licenses/> (AGPL-3.0+).
"""
build_exe.py - Construye el instalador gráfico como UN SOLO .exe con PyInstaller.

El ejecutable resultante:
  * No necesita Python instalado en la máquina del usuario.
  * Lleva DENTRO el parche (patches/) — solo huellas + traducción, nada del juego.
  * Abre una ventana; el usuario pulsa «Instalar parche al español» y listo.

Uso:
    python build_exe.py            # construye dist/<NOMBRE>.exe
    python build_exe.py --selftest # además, verifica el .exe recién creado

Requisitos: pip install pyinstaller   (ya viene en el entorno de desarrollo).
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
APP_NAME = "Instalar-Parche-Ciconia-Phase1"
ENTRY = os.path.join(HERE, "ciconia_patch_gui.py")
PATCHES = os.path.join(HERE, "patches")
SEP = ";" if os.name == "nt" else ":"  # separador src<SEP>dest de --add-data


def main():
    run_selftest = "--selftest" in sys.argv[1:]

    patch_json = os.path.join(PATCHES, "phase1", "es_patch.json")
    if not os.path.isfile(patch_json):
        print("ERROR: falta", patch_json)
        print("Genera el parche primero:  python build_patch.py --units-dir <...>")
        return 2

    args = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--onefile", "--windowed",
        "--name", APP_NAME,
        "--add-data", "%s%s%s" % (PATCHES, SEP, "patches"),
        # tkinter se detecta solo; fijamos el paquete propio por si acaso.
        "--collect-submodules", "patcher",
        "--distpath", os.path.join(HERE, "dist"),
        "--workpath", os.path.join(HERE, "build"),
        "--specpath", HERE,
        ENTRY,
    ]
    print("Construyendo .exe con PyInstaller…")
    print("  " + " ".join('"%s"' % a if " " in a else a for a in args))
    r = subprocess.run(args, cwd=HERE)
    if r.returncode != 0:
        print("PyInstaller falló con código", r.returncode)
        return r.returncode

    exe = os.path.join(HERE, "dist", APP_NAME + (".exe" if os.name == "nt" else ""))
    if not os.path.isfile(exe):
        print("ERROR: no se encontró el ejecutable esperado:", exe)
        return 1
    size_mb = os.path.getsize(exe) / (1024 * 1024)
    print("\nListo: %s  (%.1f MB)" % (exe, size_mb))

    if run_selftest:
        print("\nVerificando el .exe (--selftest)…")
        rr = subprocess.run([exe, "--selftest"], cwd=HERE)
        print("Código de salida del selftest:", rr.returncode)
        return rr.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
