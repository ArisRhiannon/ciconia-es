# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Ciconia es-419 translation project contributors.
# Part of ciconia-es419-patch. See <https://www.gnu.org/licenses/> (AGPL-3.0+).
"""
scan.py - Localiza una instalación legal de Ciconia en la máquina del usuario.

No descarga ni incluye nada del juego: solo BUSCA la copia que el usuario ya posee
(Steam / GOG / carpeta indicada a mano) y la confirma por la huella del contenido.
Robusto a versiones: si el `base_hash` no coincide exacto (juego actualizado u otra
fase), igual devuelve la carpeta y deja que el instalador informe la cobertura real.
"""
import os
import sys
import glob

GAME_EXE_HINTS = ("ciconia_phase1.exe", "ciconia_phase2.exe",
                  "ciconia_phase3.exe", "ciconia_phase4.exe")
SCRIPT_NAME = "pscript.dat"
APP_BUNDLE_HINT = "CiconiaPhase1.app"


def _steam_library_roots():
    """Devuelve posibles raíces de bibliotecas de Steam según el SO."""
    roots = []
    if sys.platform.startswith("win"):
        for base in (r"C:\Program Files (x86)\Steam", r"C:\Program Files\Steam"):
            roots.append(base)
        # Otras unidades / bibliotecas secundarias frecuentes
        for drive in "DEFGH":
            roots.append(rf"{drive}:\SteamLibrary")
            roots.append(rf"{drive}:\Steam")
    elif sys.platform == "darwin":
        home = os.path.expanduser("~")
        roots.append(os.path.join(home, "Library", "Application Support", "Steam"))
    else:  # linux
        home = os.path.expanduser("~")
        roots.append(os.path.join(home, ".steam", "steam"))
        roots.append(os.path.join(home, ".local", "share", "Steam"))
    out = []
    for r in roots:
        out.append(r)
        out.append(os.path.join(r, "steamapps", "common"))
    return out


def _gog_roots():
    roots = []
    if sys.platform.startswith("win"):
        roots += [r"C:\GOG Games", r"C:\Program Files (x86)\GOG Galaxy\Games",
                  r"C:\Program Files\GOG Galaxy\Games"]
    elif sys.platform == "darwin":
        roots.append(os.path.expanduser("~/GOG Games"))
    else:
        roots.append(os.path.expanduser("~/GOG Games"))
    return roots


def _candidate_dirs():
    cands = []
    for root in _steam_library_roots() + _gog_roots():
        if not root or not os.path.isdir(root):
            continue
        # Carpeta con "Ciconia" en el nombre, hasta 2 niveles.
        for pat in ("*[Cc]iconia*", os.path.join("*", "*[Cc]iconia*")):
            cands += glob.glob(os.path.join(root, pat))
    # Rutas frecuentes adicionales
    home = os.path.expanduser("~")
    cands += glob.glob(os.path.join(home, "Documents", "*[Cc]iconia*"))
    # Únicos, solo directorios
    seen, out = set(), []
    for c in cands:
        c = os.path.abspath(c)
        if c not in seen and os.path.isdir(c):
            seen.add(c)
            out.append(c)
    return out


def looks_like_game_dir(path: str) -> bool:
    if not os.path.isdir(path):
        return False
    if os.path.isfile(os.path.join(path, SCRIPT_NAME)):
        return True
    if any(os.path.isfile(os.path.join(path, e)) for e in GAME_EXE_HINTS):
        return True
    if os.path.isdir(os.path.join(path, APP_BUNDLE_HINT)):
        return True
    return False


def find_script(game_dir: str):
    """Devuelve la ruta a pscript.dat dentro de una carpeta de juego, o None."""
    direct = os.path.join(game_dir, SCRIPT_NAME)
    if os.path.isfile(direct):
        return direct
    hits = glob.glob(os.path.join(game_dir, "**", SCRIPT_NAME), recursive=True)
    return hits[0] if hits else None


def autodetect():
    """Lista de carpetas de juego candidatas (puede estar vacía)."""
    return [d for d in _candidate_dirs() if looks_like_game_dir(d)]
