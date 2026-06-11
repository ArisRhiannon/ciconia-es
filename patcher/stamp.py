# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Ciconia es-419 translation project contributors.
# Part of ciconia-es419-patch. See <https://www.gnu.org/licenses/> (AGPL-3.0+).
"""
stamp.py - Inyección ÉTICA de autoría y licencia en la obra derivada generada.

Solo estampa metadatos sobre TU PROPIO trabajo (la traducción y el código). No
reclama nada del original. Tres mecanismos complementarios:

  1. Banner de comentarios `;` al FINAL de `0.utf`. El motor NScripter/PONScripter
     ignora las líneas que empiezan con ';', y el final del script está tras `return`
     (zona inalcanzable), así que es inocuo y no altera ninguna línea de diálogo.
  2. Archivo lateral `0.utf.LICENSE.txt` junto a la salida (siempre seguro).
  3. (En el repo) cabeceras SPDX en cada fuente y los archivos LICENSE/NOTICE.

`assert_safe_banner()` comprueba que el banner solo añade líneas de comentario al
final y no toca el cuerpo del script, para no romper el juego.
"""

PROJECT_NAME = "Traducción es-419 de Ciconia no Naku Koro ni (no oficial, hecha por fans)"
PROJECT_URL = "https://github.com/ArisRhiannon/ciconia-es419"
CODE_LICENSE = "AGPL-3.0-or-later"
TRANSLATION_LICENSE = "CC BY-NC-SA 4.0"


def license_banner(version: str = "", date: str = "") -> str:
    """Bloque de comentarios ';' para anexar al final de 0.utf."""
    v = f" v{version}" if version else ""
    d = f"  ({date})" if date else ""
    lines = [
        ";",
        "; ============================================================",
        f";  {PROJECT_NAME}{v}{d}",
        ";  Obra DERIVADA generada localmente desde tu copia legal del juego.",
        ";  No modifica el original (pscript.dat queda intacto); el motor carga",
        ";  este 0.utf con prioridad. Distribución del original: 07th Expansion.",
        ";",
        f";  Traducción (texto): {TRANSLATION_LICENSE}  -  atribución + no comercial + compartir-igual.",
        f";  Parcheador (código): {CODE_LICENSE}.",
        f";  Fuente y créditos: {PROJECT_URL}",
        ";  Conserva estos créditos al redistribuir. Hecho por y para la comunidad.",
        "; ============================================================",
    ]
    return "\n".join(lines)


def sidecar_text(version: str = "", date: str = "") -> str:
    """Contenido del archivo 0.utf.LICENSE.txt."""
    v = f" v{version}" if version else ""
    d = f" ({date})" if date else ""
    return (
        f"{PROJECT_NAME}{v}{d}\n"
        "=================================================================\n\n"
        "Este archivo 0.utf es una OBRA DERIVADA generada en tu equipo a partir de\n"
        "tu copia legal del juego. El juego original y su guion son propiedad de\n"
        "07th Expansion; este proyecto no está afiliado ni autorizado por ellos.\n\n"
        f"- Texto de la traducción al español: {TRANSLATION_LICENSE}\n"
        "  (da crédito, NO uso comercial, y comparte las obras derivadas bajo la misma licencia)\n"
        f"- Código del parcheador: {CODE_LICENSE}\n\n"
        f"Fuente, créditos y forma de contribuir: {PROJECT_URL}\n\n"
        "Si redistribuyes el parche, hazlo íntegro y conservando los créditos.\n"
        "Distribuye SOLO el parche, nunca los archivos del juego original.\n"
    )


def assert_safe_banner(base_text: str, stamped_text: str) -> None:
    """Verifica que estampar SOLO añadió líneas ';' al final, sin tocar el cuerpo."""
    if not stamped_text.startswith(base_text):
        raise AssertionError("El banner alteró el cuerpo del script (no es un append puro).")
    tail = stamped_text[len(base_text):]
    for ln in tail.split("\n"):
        if ln.strip() == "":
            continue
        if not ln.lstrip().startswith(";"):
            raise AssertionError(f"Línea añadida no es comentario ';': {ln!r}")


def stamp(text: str, version: str = "", date: str = "") -> str:
    """Devuelve `text` con el banner de licencia anexado de forma segura."""
    banner = license_banner(version, date)
    stamped = text + ("\n" if not text.endswith("\n") else "") + banner + "\n"
    assert_safe_banner(text, stamped)
    return stamped
