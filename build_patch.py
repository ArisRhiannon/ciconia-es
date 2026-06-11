# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Ciconia es-419 translation project contributors.
# Part of ciconia-es419-patch. See <https://www.gnu.org/licenses/> (AGPL-3.0+).
"""
build_patch.py - HERRAMIENTA DE DESARROLLO (no se distribuye al usuario final).

Convierte las unidades de traducción PRIVADAS (units/*.json, que SÍ contienen el
texto original en inglés/japonés) en un parche PÚBLICO y limpio:

    patches/<fase>/es_patch.json   ->   { "lines": { "<n>": {"h": <hash>, "es": [...] } },
                                          "by_hash": { <hash>: [...] } }

El parche resultante NO contiene NADA del texto original: solo
  - números de línea (hechos estructurales de la copia del usuario),
  - huellas SHA-1 de 8 hex (irreversibles), y
  - la traducción al español (obra propia).

Mantén las units en tu repo privado; publica solo es_patch.json + manifest.json.
"""
import argparse
import datetime
import hashlib
import json
import os
import sys


def short_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]


def read_json(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def is_ready(unit):
    """Mismo criterio que compile.py: cada segmento con texto está traducido."""
    en, es = unit.get("en", []), unit.get("es", [])
    if len(en) != len(es):
        return False
    any_text = False
    for e, s in zip(en, es):
        if e == "":
            continue
        if s == "":
            return False
        any_text = True
    return any_text


def main(argv=None):
    p = argparse.ArgumentParser(description="Construye es_patch.json desde units privados.")
    p.add_argument("--units-dir", required=True, help="Carpeta translation/units con los *.json privados.")
    p.add_argument("--meta", help="Ruta a source/meta.json (para base_hash y total de líneas).")
    p.add_argument("--out-dir", required=True, help="Carpeta de salida del bundle, p.ej. patches/phase1.")
    p.add_argument("--phase", default="phase1")
    p.add_argument("--version", default="0.1.0")
    p.add_argument("--title",
                   default="Ciconia When They Cry: Phase 1 - Parche al español por Aris Rhiannon",
                   help="Título de ventana del 0.utf parcheado.")
    args = p.parse_args(argv)

    meta = read_json(args.meta) if args.meta else {}
    base_hash = meta.get("base_hash", "")
    langen_total = meta.get("total_langen_lines", 0)

    by_line = {}
    # Para detectar colisiones hash<->traducción divergente:
    hash_to_es = {}        # hash -> set de traducciones (serializadas) distintas
    ready = 0
    for fn in sorted(os.listdir(args.units_dir)):
        if not fn.endswith(".json"):
            continue
        data = read_json(os.path.join(args.units_dir, fn))
        for u in data.get("units", []):
            if not is_ready(u):
                continue
            h = u.get("en_hash") or ""
            es = u["es"]
            by_line[str(u["line"])] = {"h": h, "es": es}
            hash_to_es.setdefault(h, set()).add(json.dumps(es, ensure_ascii=False))
            ready += 1

    # Índice por hash SOLO para hashes con una única traducción (sin ambigüedad).
    by_hash, collisions = {}, 0
    for h, variants in hash_to_es.items():
        if len(variants) == 1:
            by_hash[h] = json.loads(next(iter(variants)))
        else:
            collisions += 1  # se resolverán por número de línea (by_line)

    os.makedirs(args.out_dir, exist_ok=True)
    patch = {
        "_format": "ciconia-es419/1",
        "_note": "Solo huellas SHA-1 + traducción es-419. No contiene texto original.",
        "base_hash": base_hash,
        "window_title": args.title,
        "lines": by_line,
        "by_hash": by_hash,
    }
    patch_path = os.path.join(args.out_dir, "es_patch.json")
    with open(patch_path, "w", encoding="utf-8") as f:
        json.dump(patch, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")

    manifest = {
        "project": "ciconia-es419",
        "phase": args.phase,
        "version": args.version,
        "built": datetime.date.today().isoformat(),
        "base_hash": base_hash,
        "patch_file": "es_patch.json",
        "window_title": args.title,
        "translated_lines": ready,
        "langen_total": langen_total,
        "coverage_pct": round(100.0 * ready / langen_total, 1) if langen_total else None,
        "hash_index_entries": len(by_hash),
        "hash_collisions_line_keyed": collisions,
        "code_license": "AGPL-3.0-or-later",
        "translation_license": "CC BY-NC-SA 4.0",
    }
    with open(os.path.join(args.out_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"Unidades listas:        {ready}")
    print(f"Cobertura:              {manifest['coverage_pct']}%  ({ready}/{langen_total})")
    print(f"Índice por hash:        {len(by_hash)} entradas")
    print(f"Colisiones (por línea): {collisions}")
    print(f"Escrito: {patch_path}")
    print(f"Escrito: {os.path.join(args.out_dir, 'manifest.json')}")
    # Tamaño del parche
    sz = os.path.getsize(patch_path)
    print(f"Tamaño es_patch.json:   {sz/1024:.0f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
