# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Ciconia es-419 translation project contributors.
# Part of ciconia-es419-patch. See <https://www.gnu.org/licenses/> (AGPL-3.0+).
"""
installer.py - Orquestación de instalar/desinstalar el parche (fuente única).

Tanto la CLI (`ciconia_patch.py`) como la interfaz gráfica (`ciconia_patch_gui.py`)
llaman aquí, para que haya UNA sola lógica de instalación, ya probada.

Garantías de seguridad:
  * NUNCA modifica `pscript.dat` (se lee y descifra solo en memoria).
  * Escribe SOLO `0.utf` (+ su sidecar de licencia) como obra derivada.
  * Respalda cualquier `0.utf` previo en `0.utf.orig`; desinstalar lo restaura.

Las funciones devuelven un dict con el resultado y reportan el avance por el
callback `log` (la CLI pasa `print`; la GUI escribe en su panel). Para fallos
accionables por el usuario (no se halla el juego, etc.) lanzan `InstallError`.
"""
import datetime
import glob
import json
import os
import shutil
import sys

from . import core, scan, stamp


class InstallError(Exception):
    """Fallo accionable por el usuario (mensaje en español + código de salida)."""

    def __init__(self, message, code=2):
        super().__init__(message)
        self.code = code


def _read_json(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def default_patches_dir():
    """Carpeta `patches/` junto al programa, contemplando el .exe de PyInstaller."""
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "patches")


def select_bundle(patches_dir, base_hash):
    """Elige el bundle cuyo manifest.base_hash coincide con la copia del usuario."""
    best = None
    for man_path in glob.glob(os.path.join(patches_dir, "*", "manifest.json")):
        try:
            man = _read_json(man_path)
        except Exception:
            continue
        bundle_dir = os.path.dirname(man_path)
        patch_path = os.path.join(bundle_dir, man.get("patch_file", "es_patch.json"))
        info = {"manifest": man, "dir": bundle_dir, "patch": patch_path}
        if man.get("base_hash") == base_hash:
            return info            # coincidencia exacta de versión
        best = best or info        # respaldo: primer bundle disponible
    return best


def resolve_game_dir(game_dir, log):
    """Devuelve una carpeta de juego válida (autodetecta si no se indicó)."""
    if not game_dir:
        cands = scan.autodetect()
        if not cands:
            raise InstallError(
                "No encontré una instalación de Ciconia automáticamente.\n"
                "Abre el programa, pulsa «Buscar…» e indica la carpeta del juego "
                "(la que contiene pscript.dat).", code=2)
        game_dir = cands[0]
        if len(cands) > 1:
            log("Varias instalaciones detectadas; uso la primera:")
            for c in cands:
                log("   - " + c)
    if not scan.looks_like_game_dir(game_dir):
        raise InstallError(
            "Esa carpeta no parece la del juego (no tiene pscript.dat ni el "
            "ejecutable):\n" + game_dir, code=2)
    return game_dir


def run_install(game_dir=None, *, patch_path=None, patches_dir=None, output=None,
                xor_key=core.DEFAULT_XOR_KEY, no_stamp=False, no_title=False,
                complete=False, dry_run=False, log=None):
    """Instala el parche. Devuelve un dict con el resultado. Lanza InstallError."""
    log = log or (lambda *a: None)

    game_dir = resolve_game_dir(game_dir, log)
    script_path = scan.find_script(game_dir)
    if not script_path:
        raise InstallError("No encontré %s dentro de:\n%s" % (scan.SCRIPT_NAME, game_dir), code=2)
    log("Juego: " + game_dir)
    log("Script original: " + script_path)

    # Leer y descifrar la copia del usuario (en memoria; jamás se modifica).
    base_text = core.decrypt_script(script_path, xor_key)
    base_hash = core.short_hash(base_text)
    log("Huella del script (base_hash): " + base_hash)

    # Elegir el bundle del parche que corresponda a esta versión/fase.
    if patch_path:
        patch = _read_json(patch_path)
        manifest = patch.get("_manifest", {})
    else:
        patches_dir = patches_dir or default_patches_dir()
        info = select_bundle(patches_dir, base_hash)
        if not info:
            raise InstallError("No hay parches disponibles en:\n" + patches_dir, code=2)
        manifest = info["manifest"]
        patch = _read_json(info["patch"])

    # Aplicar (por número de línea con verificación; respaldo por hash si la versión difiere).
    expected_base = manifest.get("base_hash") or patch.get("base_hash")
    version_match = (expected_base is not None and expected_base == base_hash)
    if expected_base and not version_match:
        log("AVISO: tu versión del juego (base_hash %s) no coincide con la del parche "
            "(%s). Traduzco por contenido lo que coincida; el resto queda en el idioma "
            "original." % (base_hash, expected_base))
    use_fallback = complete or (expected_base is not None and not version_match)
    mode = "exacto (revisado)" if not use_fallback else "por contenido (cobertura máxima)"
    log("Modo de aplicación: " + mode)

    result, st = core.apply_patch(base_text, patch, use_hash_fallback=use_fallback)
    cov = st["by_line"] + st["by_hash"]
    total = max(1, st["langen_total"])
    log("")
    log("Líneas de texto: %d" % st["langen_total"])
    log("  traducidas:   %d  (%.1f%%)" % (cov, 100.0 * cov / total))
    log("  sin traducir: %d" % st["untranslated"])
    if st["segcount_skip"]:
        log("  omitidas por estructura distinta: %d" % st["segcount_skip"])

    # Reescribir el título de la ventana (obra derivada; no toca el original).
    window_title = patch.get("window_title") or manifest.get("window_title")
    caption_n = 0
    if window_title and not no_title:
        result, caption_n = core.rewrite_caption(result, window_title)
        if caption_n:
            log('Título de ventana: "%s"' % window_title)

    # Estampar licencia/autoría en la obra derivada.
    version = manifest.get("version", "")
    date = datetime.date.today().isoformat()
    if not no_stamp:
        result = stamp.stamp(result, version=version, date=date)

    out_path = output or os.path.join(game_dir, "0.utf")
    res = {
        "game_dir": game_dir, "script_path": script_path, "base_hash": base_hash,
        "expected_base": expected_base, "version_match": version_match, "mode": mode,
        "stats": st, "coverage": cov, "coverage_pct": 100.0 * cov / total,
        "out_path": out_path, "version": version, "caption_n": caption_n,
        "window_title": window_title if (window_title and not no_title) else None,
        "dry_run": dry_run, "wrote": False, "backup": None, "sidecar": None,
    }

    if dry_run:
        log("")
        log("[simulación] No se escribió nada. Se habría escrito: " + out_path)
        return res

    # Respaldo del 0.utf previo (pscript.dat no se toca jamás).
    backup = out_path + ".orig"
    if os.path.exists(out_path) and not os.path.exists(backup):
        shutil.copy2(out_path, backup)
        res["backup"] = backup
        log("")
        log("Respaldo del 0.utf previo: " + backup)

    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(result)
    res["wrote"] = True
    if not no_stamp:
        sidecar = out_path + ".LICENSE.txt"
        with open(sidecar, "w", encoding="utf-8") as f:
            f.write(stamp.sidecar_text(version=version, date=date))
        res["sidecar"] = sidecar
    log("")
    log("Instalado: " + out_path)
    return res


def run_uninstall(game_dir=None, *, output=None, log=None):
    """Restaura el 0.utf previo (o lo elimina). Devuelve un dict con el resultado."""
    log = log or (lambda *a: None)
    if not game_dir:
        cands = scan.autodetect()
        game_dir = cands[0] if cands else None
    if not game_dir:
        raise InstallError(
            "No encontré el juego. Pulsa «Buscar…» e indica su carpeta para restaurar.",
            code=2)

    out_path = output or os.path.join(game_dir, "0.utf")
    orig = out_path + ".orig"
    res = {"game_dir": game_dir, "out_path": out_path, "action": "nada"}
    if os.path.exists(orig):
        shutil.copy2(orig, out_path)
        res["action"] = "restaurado"
        log("Restaurado el 0.utf original desde el respaldo.")
    elif os.path.exists(out_path):
        os.remove(out_path)
        res["action"] = "eliminado"
        log("Parche eliminado. El motor volverá a usar pscript.dat (idioma original).")
    else:
        log("No había nada que desinstalar.")
    sidecar = out_path + ".LICENSE.txt"
    if os.path.exists(sidecar):
        os.remove(sidecar)
    return res
