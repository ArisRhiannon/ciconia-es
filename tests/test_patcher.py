# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Ciconia es-419 translation project contributors.
# Part of ciconia-es419-patch. See <https://www.gnu.org/licenses/> (AGPL-3.0+).
"""
Pruebas del parcheador. TODAS son seguras y no destructivas:

  * Los tests de lógica usan un script SINTÉTICO en memoria (no tocan el juego).
  * El test de integración COPIA el pscript.dat real a una carpeta temporal y
    trabaja solo ahí; nunca escribe en la carpeta del juego, ni en units/, ni en
    build/. Comprueba además que el pscript.dat real queda intacto (hash igual).

Ejecutar:  python -m unittest -v tests.test_patcher
"""
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from patcher import core, scan, stamp  # noqa: E402

PATCH_PATH = os.path.join(REPO, "patches", "phase1", "es_patch.json")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Base sintética (no depende del juego)
# ---------------------------------------------------------------------------
def synthetic_base():
    lines = [
        ";gameid test",                       # 1
        "*define",                            # 2
        "game",                               # 3
        "*start",                             # 4
        "langjp^\u3053\u3093\u306b\u3061\u306f^@",   # 5  (japonés, no se edita)
        "langen^Hello^@",                     # 6  -> "Hola"
        "langjp^\u30c6\u30b9\u30c8^\\",        # 7
        "langen^A test^\\",                   # 8  -> "Una prueba"
        "langen^Press ~i~X~/i~ now^@",        # 9  -> "Pulsa {0}X{1} ahora"
        "langen^one^@^two^\\",                # 10 -> ["uno","dos"]
        "return",                             # 11
    ]
    return "\n".join(lines)


def build_synthetic_patch(base):
    lines = base.split("\n")

    def h(n):
        return core.short_hash(lines[n - 1])

    by_line = {
        "6": {"h": h(6), "es": ["Hola"]},
        "8": {"h": h(8), "es": ["Una prueba"]},
        "9": {"h": h(9), "es": ["Pulsa {0}X{1} ahora"]},
        "10": {"h": h(10), "es": ["uno", "dos"]},
    }
    by_hash = {v["h"]: v["es"] for v in by_line.values()}
    return {"base_hash": core.short_hash(base), "lines": by_line, "by_hash": by_hash}


class TestCoreLossless(unittest.TestCase):
    def test_roundtrip_identity(self):
        for line in synthetic_base().split("\n"):
            if core.is_track_line(line, "langen"):
                parsed = core.parse_langen(line, "langen")
                self.assertEqual(core.build_langen(parsed), line)

    def test_protect_restore_inverse(self):
        for s in ["Press ~i~X~/i~ now", "Wait !s100 then %var and $name go",
                  "no markers here", "~a~~b~ edge"]:
            clean, ph = core.protect(s)
            self.assertEqual(core.restore(clean, ph), s)

    def test_short_hash_deterministic(self):
        self.assertEqual(core.short_hash("langen^Hello^@"),
                         core.short_hash("langen^Hello^@"))
        self.assertNotEqual(core.short_hash("a"), core.short_hash("b"))


class TestStamp(unittest.TestCase):
    def test_banner_is_pure_comment_append(self):
        body = "langen^Hola^@\nreturn"
        out = stamp.stamp(body, version="1.0", date="2026-01-01")
        self.assertTrue(out.startswith(body))
        for ln in out[len(body):].split("\n"):
            self.assertTrue(ln.strip() == "" or ln.lstrip().startswith(";"))

    def test_assert_safe_banner_rejects_body_change(self):
        with self.assertRaises(AssertionError):
            stamp.assert_safe_banner("hello world", "hi world\n; banner")


class TestApplyPatch(unittest.TestCase):
    def setUp(self):
        self.base = synthetic_base()
        self.patch = build_synthetic_patch(self.base)

    def test_exact_translates_only_langen(self):
        out, st = core.apply_patch(self.base, self.patch, use_hash_fallback=False)
        ol = out.split("\n")
        self.assertEqual(st["langen_total"], 4)
        self.assertEqual(st["by_line"], 4)
        self.assertEqual(st["by_hash"], 0)
        self.assertEqual(st["untranslated"], 0)
        self.assertEqual(ol[5], "langen^Hola^@")          # línea 6
        self.assertEqual(ol[7], "langen^Una prueba^\\")   # línea 8
        # placeholders re-derivados desde la copia (los ~tags~ vuelven)
        self.assertEqual(ol[8], "langen^Pulsa ~i~X~/i~ ahora^@")
        self.assertEqual(ol[9], "langen^uno^@^dos^\\")    # 2 segmentos
        # líneas no-langen intactas
        self.assertEqual(ol[0], ";gameid test")
        self.assertEqual(ol[4], self.base.split("\n")[4])  # japonés intacto
        self.assertEqual(ol[10], "return")

    def test_structure_valid_after_apply(self):
        out, _ = core.apply_patch(self.base, self.patch)
        self.assertEqual(len(out.split("\n")), len(self.base.split("\n")))
        for line in out.split("\n"):
            if core.is_track_line(line, "langen"):
                self.assertEqual(core.build_langen(core.parse_langen(line, "langen")), line)

    def test_segcount_mismatch_is_skipped(self):
        bad = {"base_hash": self.patch["base_hash"],
               "lines": {"10": {"h": core.short_hash(self.base.split("\n")[9]),
                                "es": ["solo-uno"]}},  # 1 seg vs 2 esperados
               "by_hash": {}}
        out, st = core.apply_patch(self.base, bad)
        self.assertEqual(st["segcount_skip"], 1)
        self.assertEqual(out.split("\n")[9], "langen^one^@^two^\\")  # intacta

    def test_hash_fallback_on_drift(self):
        drifted = "\n\n" + self.base  # desplaza todas las líneas +2
        out_no, st_no = core.apply_patch(drifted, self.patch, use_hash_fallback=False)
        self.assertEqual(st_no["by_line"] + st_no["by_hash"], 0)  # nada por línea
        out_yes, st_yes = core.apply_patch(drifted, self.patch, use_hash_fallback=True)
        self.assertEqual(st_yes["by_hash"], 4)  # rescatadas por contenido
        self.assertIn("langen^Hola^@", out_yes)

    def test_wrong_hash_does_not_translate(self):
        bad = {"lines": {"6": {"h": "deadbeef", "es": ["Hola"]}}, "by_hash": {}}
        out, st = core.apply_patch(self.base, bad)
        self.assertEqual(st["by_line"], 0)
        self.assertEqual(out.split("\n")[5], "langen^Hello^@")  # original


class TestCaptionRewrite(unittest.TestCase):
    BASE = ('*define\n'
            ';caption "ORIGINAL JP"\n'
            'caption "\u30ad\u30b3\u30cb\u30a2 Phase1"\n'
            'versionstr "X","created by 07th Expansion"\n'
            'game\n*start\nlangen^Hi^@\nreturn')

    def test_rewrites_only_active_caption(self):
        out, n = core.rewrite_caption(self.BASE, "Mi Título - Parche")
        self.assertEqual(n, 1)
        self.assertIn('caption "Mi Título - Parche"', out)
        self.assertIn(';caption "ORIGINAL JP"', out)          # comentada intacta
        self.assertIn('versionstr "X","created by 07th Expansion"', out)  # sin tocar
        self.assertNotIn('\u30ad\u30b3\u30cb\u30a2', out)     # título JP reemplazado

    def test_rejects_unsafe_title(self):
        for bad in ['tiene "comillas"', "salto\nlinea", "barra\\mala"]:
            out, n = core.rewrite_caption(self.BASE, bad)
            self.assertEqual(n, 0)
            self.assertEqual(out, self.BASE)

    def test_no_caption_line_is_noop(self):
        out, n = core.rewrite_caption("*define\ngame\nreturn", "Título")
        self.assertEqual(n, 0)


@unittest.skipUnless(os.path.isfile(PATCH_PATH), "no hay es_patch.json construido")
class TestIntegrationSandbox(unittest.TestCase):
    """Flujo real install/uninstall sobre una COPIA temporal del pscript.dat."""

    @classmethod
    def setUpClass(cls):
        cls.games = scan.autodetect()
        cls.real_script = None
        for g in cls.games:
            s = scan.find_script(g)
            if s:
                cls.real_script = s
                break

    def setUp(self):
        if not self.real_script:
            self.skipTest("no se encontró pscript.dat real para sandbox")
        self.sandbox = tempfile.mkdtemp(prefix="ciconia_sbx_")
        # Copia aislada; nunca tocamos el juego real.
        self.sbx_script = os.path.join(self.sandbox, "pscript.dat")
        shutil.copy2(self.real_script, self.sbx_script)
        self.real_hash_before = sha256_file(self.real_script)

    def tearDown(self):
        shutil.rmtree(self.sandbox, ignore_errors=True)

    def _run_cli(self, *args):
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        return subprocess.run(
            [sys.executable, os.path.join(REPO, "ciconia_patch.py"), *args],
            cwd=REPO, env=env, capture_output=True, text=True, encoding="utf-8")

    def test_install_then_uninstall_sandbox(self):
        out_utf = os.path.join(self.sandbox, "0.utf")

        # --- instalar en el sandbox ---
        r = self._run_cli("--game-dir", self.sandbox, "--patch", PATCH_PATH,
                          "--output", out_utf)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(os.path.isfile(out_utf), "no se generó 0.utf")
        self.assertTrue(os.path.isfile(out_utf + ".LICENSE.txt"), "falta sidecar de licencia")

        # el pscript del sandbox NO se modificó
        self.assertEqual(sha256_file(self.sbx_script), sha256_file(self.real_script))
        # el pscript REAL del juego NO se tocó
        self.assertEqual(sha256_file(self.real_script), self.real_hash_before)

        # integridad estructural del 0.utf generado
        base = core.decrypt_script(self.sbx_script)
        n_base_langen = sum(1 for l in base.split("\n") if core.is_track_line(l, "langen"))
        with open(out_utf, encoding="utf-8") as f:
            produced = f.read()
        prod_lines = produced.split("\n")
        n_prod_langen = sum(1 for l in prod_lines if core.is_track_line(l, "langen"))
        self.assertEqual(n_prod_langen, n_base_langen, "se perdieron/añadieron líneas langen")
        for l in prod_lines:
            if core.is_track_line(l, "langen"):
                self.assertEqual(core.build_langen(core.parse_langen(l, "langen")), l,
                                 "línea langen mal formada en la salida")
        self.assertIn(";  Parcheador (código): AGPL-3.0-or-later.", produced)
        # título de ventana reescrito (obra derivada)
        self.assertIn('caption "Ciconia When They Cry: Phase 1 - Parche al español por Aris Rhiannon"',
                      produced)

        # --- desinstalar ---
        r2 = self._run_cli("--uninstall", "--game-dir", self.sandbox, "--output", out_utf)
        self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)
        self.assertFalse(os.path.isfile(out_utf), "0.utf no se eliminó al desinstalar")
        self.assertFalse(os.path.isfile(out_utf + ".LICENSE.txt"), "sidecar no se eliminó")

    def test_dry_run_writes_nothing(self):
        out_utf = os.path.join(self.sandbox, "0.utf")
        r = self._run_cli("--game-dir", self.sandbox, "--patch", PATCH_PATH,
                          "--output", out_utf, "--dry-run")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse(os.path.isfile(out_utf), "dry-run NO debe escribir")


if __name__ == "__main__":
    unittest.main(verbosity=2)
