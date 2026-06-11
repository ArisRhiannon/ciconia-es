# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Ciconia es-419 translation project contributors.
#
# This file is part of ciconia-es419-patch.
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your
# option) any later version.  See <https://www.gnu.org/licenses/>.
"""
core.py - Motor del parcheador de texto de Ciconia (familia NScripter/PONScripter).

Reconstruye un `0.utf` jugable en español a partir de:
  * la copia LEGAL del usuario del script original (`pscript.dat`), que se lee y
    descifra EN MEMORIA pero NUNCA se modifica, y
  * un parche direccionado por contenido `{en_hash: [segmentos_es]}` que NO contiene
    nada del texto original (solo huellas SHA-1 + la traducción propia).

Por qué esto basta: el motor del juego carga `0.utf` con PRIORIDAD sobre `pscript.dat`,
así que generar `0.utf` es crear una OBRA DERIVADA nueva, sin tocar el original.
Los separadores y los marcadores inline se RE-DERIVAN de la copia del usuario con la
misma función determinista `protect()`, por lo que el parche no necesita transportarlos.

Las rutinas de parseo/serialización son equivalentes a las del pipeline interno de
extracción y deben mantener la invariante:  build_langen(parse_langen(l)) == l.
"""
import hashlib
import re

DEFAULT_XOR_KEY = 0x84
DEFAULT_TRACK = "langen"


# ---------------------------------------------------------------------------
# Descifrado de la copia del usuario (solo lectura en memoria)
# ---------------------------------------------------------------------------
def decrypt_bytes(data: bytes, key: int = DEFAULT_XOR_KEY) -> bytes:
    return bytes((b ^ key) & 0xFF for b in data)


def decrypt_script(path: str, key: int = DEFAULT_XOR_KEY) -> str:
    """Lee y descifra el script del usuario; normaliza EOL a LF. No escribe nada."""
    with open(path, "rb") as f:
        raw = f.read()
    text = decrypt_bytes(raw, key).decode("utf-8")
    return text.replace("\r\n", "\n").replace("\r", "\n")


# ---------------------------------------------------------------------------
# Parser / serializador lossless de líneas de pista (langen)
# ---------------------------------------------------------------------------
def is_track_line(line: str, track: str = DEFAULT_TRACK) -> bool:
    return line.startswith(track) and (
        len(line) == len(track) or not line[len(track)].isalnum()
    )


def parse_langen(line: str, track: str = DEFAULT_TRACK):
    """Descompone <track><lead>(^<seg>^<sep>)* en lead + segmentos + separadores."""
    if not is_track_line(line, track):
        return None
    rest = line[len(track):]
    i, n = 0, len(rest)
    lead = ""
    while i < n and rest[i] != "^":
        lead += rest[i]
        i += 1
    segs, seps, closed = [], [], []
    while i < n and rest[i] == "^":
        i += 1  # abre '^'
        seg = ""
        while i < n and rest[i] != "^":
            seg += rest[i]
            i += 1
        is_closed = False
        if i < n and rest[i] == "^":
            i += 1  # cierra '^'
            is_closed = True
        sep = ""
        while i < n and rest[i] != "^":
            sep += rest[i]
            i += 1
        segs.append(seg)
        seps.append(sep)
        closed.append(is_closed)
    return {"track": track, "lead": lead, "segs": segs, "seps": seps, "closed": closed}


def build_langen(parsed) -> str:
    out = parsed["track"] + parsed["lead"]
    for seg, sep, cl in zip(parsed["segs"], parsed["seps"], parsed["closed"]):
        out += "^" + seg + ("^" if cl else "") + sep
    return out


def build_translated(parsed, new_segs) -> str:
    """Reconstruye la línea con `new_segs` (ya en español) conservando lead/seps/cierre."""
    out = parsed["track"] + parsed["lead"]
    for seg, sep, cl in zip(new_segs, parsed["seps"], parsed["closed"]):
        out += "^" + seg + ("^" if cl else "") + sep
    return out


# ---------------------------------------------------------------------------
# Marcadores inline: protección/restauración determinista
# ---------------------------------------------------------------------------
_PH_PATTERNS = [
    r"~[^~]*~",            # tags de estilo / ruby
    r"\$[A-Za-z_]\w*",     # variables de cadena
    r"%[A-Za-z_]\w*",      # variables enteras
    r"![a-z]+\d*",         # comandos inline (!s0, !sd, !w200, ...)
]
_PH_RE = re.compile("|".join(_PH_PATTERNS))


def protect(text: str):
    """Sustituye marcadores inline por {0},{1},... y devuelve (texto_limpio, mapa)."""
    ph = {}
    idx = 0

    def repl(m):
        nonlocal idx
        token = "{%d}" % idx
        ph[token] = m.group(0)
        idx += 1
        return token

    clean = _PH_RE.sub(repl, text)
    return clean, ph


def restore(text: str, ph: dict) -> str:
    for token, original in ph.items():
        text = text.replace(token, original)
    return text


def short_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]


# ---------------------------------------------------------------------------
# Reescritura del título de la ventana (comando `caption "..."`)
# ---------------------------------------------------------------------------
# Líneas `caption "..."` o `caption $var` ACTIVAS, opcionalmente precedidas por `if ... caption`.
_CAPTION_RE = re.compile(r'^(?P<lead>.*\bcaption)[ \t]+(?P<arg>"(?:[^"\\]|\\.)*"|\$\w+)(?P<rest>[^"]*?)$')


def rewrite_caption(text: str, new_title: str):
    """Reemplaza el argumento de las líneas `caption` activas por `new_title`.

    Casa tanto `caption "texto"` como `caption $Variable`. Cambia SOLO el título
    de la ventana del 0.utf generado (obra derivada); no toca `versionstr`.
    Devuelve (texto, nº de líneas caption reescritas). Si `new_title` contiene
    caracteres que romperían el comando (comilla, barra, salto de línea), no hace nada.
    """
    if any(c in new_title for c in ('"', "\\", "\n", "\r")):
        return text, 0
    out, n = [], 0
    for line in text.split("\n"):
        m = _CAPTION_RE.match(line)
        if m and not line.lstrip().startswith(";"):
            out.append('%s "%s"%s' % (m.group("lead"), new_title, m.group("rest")))
            n += 1
        else:
            out.append(line)
    return "\n".join(out), n


# ---------------------------------------------------------------------------
# Aplicación del parche
# ---------------------------------------------------------------------------
def apply_patch(base_text: str, patch: dict, track: str = DEFAULT_TRACK,
                use_hash_fallback: bool = False):
    """Genera el texto de `0.utf` traducido a partir del script base del usuario.

    `patch["lines"]` es un dict line_no(str) -> {"h": en_hash, "es": [segmentos]}.
    `patch["by_hash"]` (opcional) es en_hash -> [segmentos].

    Estrategia:
      1. Para cada línea `langen` del script del usuario:
         a. Si hay entrada por número de línea y su hash coincide -> traducir (exacto).
         b. Si no, y `use_hash_fallback`, y el hash está en `by_hash` -> traducir.
         c. Si no -> copiar la línea original EXACTA (degradación elegante).

    `use_hash_fallback=False` (por defecto) reproduce EXACTAMENTE la salida revisada
    (QA) en la versión para la que se hizo el parche. Se activa solo cuando la versión
    del usuario difiere (las líneas se desplazaron) o a petición explícita (--complete).
    Devuelve (texto_resultante, stats).
    """
    by_line = patch.get("lines", {})
    by_hash = patch.get("by_hash", {}) if use_hash_fallback else {}
    lines = base_text.split("\n")

    out = []
    stats = {"langen_total": 0, "by_line": 0, "by_hash": 0,
             "untranslated": 0, "segcount_skip": 0}

    for idx, line in enumerate(lines, start=1):
        if not is_track_line(line, track):
            out.append(line)
            continue
        stats["langen_total"] += 1

        h = short_hash(line)
        entry = by_line.get(str(idx))
        es_segs = None
        source = None
        if entry is not None and entry.get("h") == h:
            es_segs = entry["es"]
            source = "by_line"
        elif h in by_hash:
            es_segs = by_hash[h]
            source = "by_hash"

        if es_segs is None:
            stats["untranslated"] += 1
            out.append(line)
            continue

        parsed = parse_langen(line, track)
        if len(es_segs) != len(parsed["segs"]):
            # Estructura distinta a la esperada: no arriesgar, dejar original.
            stats["segcount_skip"] += 1
            out.append(line)
            continue

        # Re-derivar el mapa de marcadores desde la copia del usuario y restaurar.
        new_segs = []
        for es_seg, orig_seg in zip(es_segs, parsed["segs"]):
            _, ph = protect(orig_seg)
            new_segs.append(restore(es_seg, ph))
        out.append(build_translated(parsed, new_segs))
        stats[source] += 1

    return "\n".join(out), stats
