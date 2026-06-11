# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Ciconia es-419 translation project contributors.
#
# This file is part of ciconia-es419-patch.
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU Affero General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version. See <https://www.gnu.org/licenses/>.
"""
ciconia_patch_gui.py - Instalador GRÁFICO del parche al español (es-419).

Pensado para cualquier persona, sin conocimientos técnicos: se abre, detecta el
juego solo, y con un botón instala el parche. Otro botón restaura el original.

Comparte la MISMA lógica probada que la consola (patcher/installer.py): genera un
`0.utf` en español a partir de TU copia legal del juego, sin tocar ningún archivo
original (pscript.dat queda intacto). Empaquetado como .exe con PyInstaller.

Modo oculto de verificación (no abre ventana):  ciconia_patch_gui --selftest
"""
import os
import queue
import sys
import threading

# Permite importar el paquete `patcher` tanto en desarrollo como congelado (.exe).
if not getattr(sys, "frozen", False):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from patcher import installer, scan, stamp  # noqa: E402

APP_TITLE = "Ciconia: Phase 1 — Parche al español (es-419)"
SUBTITLE = "Traducción por Aris Rhiannon · no oficial · solo texto"


# ---------------------------------------------------------------------------
# Verificación headless del ejecutable (sin GUI): comprueba que el parche
# empaquetado carga y que el motor de aplicación funciona. Escribe el resultado
# en un archivo temporal (porque un .exe «windowed» no tiene consola visible).
# ---------------------------------------------------------------------------
def _selftest():
    import json
    import tempfile

    log = []
    ok = True

    def chk(cond, msg):
        nonlocal ok
        log.append(("OK  " if cond else "FALLO ") + msg)
        ok = ok and bool(cond)

    try:
        patches_dir = installer.default_patches_dir()
        chk(os.path.isdir(patches_dir), "patches dir: " + patches_dir)
        info = installer.select_bundle(patches_dir, "00000000")  # devuelve el mejor bundle
        chk(info is not None, "bundle de parche encontrado")
        if info:
            patch = json.load(open(info["patch"], encoding="utf-8-sig"))
            chk("lines" in patch and len(patch["lines"]) > 0,
                "es_patch.json tiene %d líneas" % len(patch.get("lines", {})))
            chk(bool(patch.get("window_title") or info["manifest"].get("window_title")),
                "título de ventana embebido")
        # Si hay un juego detectable, ejercita descifrar+aplicar en seco (no escribe).
        games = scan.autodetect()
        if games:
            res = installer.run_install(games[0], dry_run=True, log=lambda *a: None)
            chk(res["coverage"] > 0, "simulación sobre juego real: %.1f%% cobertura"
                % res["coverage_pct"])
            # Instalación REAL en un sandbox temporal (jamás toca la carpeta del juego).
            import shutil
            src = scan.find_script(games[0])
            sbx = tempfile.mkdtemp(prefix="ciconia_exe_sbx_")
            try:
                sbx_script = os.path.join(sbx, scan.SCRIPT_NAME)
                shutil.copy2(src, sbx_script)
                with open(sbx_script, "rb") as f:
                    before = f.read()
                out_utf = os.path.join(sbx, "0.utf")
                installer.run_install(sbx, output=out_utf, log=lambda *a: None)
                chk(os.path.isfile(out_utf), "sandbox: 0.utf escrito")
                chk(os.path.isfile(out_utf + ".LICENSE.txt"), "sandbox: sidecar de licencia")
                with open(sbx_script, "rb") as f:
                    after = f.read()
                chk(before == after, "sandbox: pscript.dat intacto")
                installer.run_uninstall(sbx, output=out_utf, log=lambda *a: None)
                chk(not os.path.isfile(out_utf), "sandbox: 0.utf eliminado al restaurar")
            finally:
                shutil.rmtree(sbx, ignore_errors=True)
        else:
            log.append("INFO  sin juego detectado (no se simuló sobre datos reales)")
    except Exception as e:  # noqa: BLE001
        ok = False
        log.append("EXCEPCIÓN: %r" % e)

    report = ("SELFTEST %s\n" % ("OK" if ok else "FALLÓ")) + "\n".join(log) + "\n"
    out = os.path.join(tempfile.gettempdir(), "ciconia_gui_selftest.txt")
    try:
        with open(out, "w", encoding="utf-8") as f:
            f.write(report)
    except Exception:  # noqa: BLE001
        pass
    # En un .exe «windowed» no hay consola: sys.stdout puede ser None.
    if getattr(sys, "stdout", None):
        try:
            sys.stdout.write(report)
        except Exception:  # noqa: BLE001
            pass
    return 0 if ok else 1


# ---------------------------------------------------------------------------
# Interfaz gráfica
# ---------------------------------------------------------------------------
class PatcherGUI:
    def __init__(self, root):
        import tkinter as tk
        from tkinter import ttk

        self.tk = tk
        self.ttk = ttk
        self.root = root
        self.q = queue.Queue()
        self.busy = False

        root.title(APP_TITLE)
        root.minsize(640, 520)
        try:
            root.configure(bg="#f4f4f7")
        except Exception:  # noqa: BLE001
            pass

        pad = {"padx": 14, "pady": 6}
        frm = ttk.Frame(root, padding=16)
        frm.grid(row=0, column=0, sticky="nsew")
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        frm.columnconfigure(0, weight=1)

        ttk.Label(frm, text=APP_TITLE, font=("Segoe UI", 14, "bold")).grid(
            row=0, column=0, sticky="w")
        ttk.Label(frm, text=SUBTITLE, foreground="#666").grid(
            row=1, column=0, sticky="w", pady=(0, 8))
        ttk.Separator(frm).grid(row=2, column=0, sticky="ew", pady=6)

        ttk.Label(frm, text="1) Carpeta del juego (se busca automáticamente):").grid(
            row=3, column=0, sticky="w")
        path_row = ttk.Frame(frm)
        path_row.grid(row=4, column=0, sticky="ew", pady=(2, 6))
        path_row.columnconfigure(0, weight=1)
        self.path_var = tk.StringVar(value="Buscando el juego…")
        self.path_entry = ttk.Entry(path_row, textvariable=self.path_var)
        self.path_entry.grid(row=0, column=0, sticky="ew")
        self.browse_btn = ttk.Button(path_row, text="Buscar…", command=self.on_browse)
        self.browse_btn.grid(row=0, column=1, padx=(8, 0))

        ttk.Label(frm, text="2) Pulsa el botón verde para instalar el parche:").grid(
            row=5, column=0, sticky="w", pady=(6, 2))
        btn_row = ttk.Frame(frm)
        btn_row.grid(row=6, column=0, sticky="ew", pady=4)
        # Botón principal destacado (tk.Button permite color de fondo de forma fiable).
        self.install_btn = tk.Button(
            btn_row, text="Instalar parche al español", command=self.on_install,
            bg="#2e7d32", fg="white", activebackground="#256628", activeforeground="white",
            font=("Segoe UI", 11, "bold"), relief="raised", bd=2, padx=12, pady=8,
            cursor="hand2")
        self.install_btn.grid(row=0, column=0, sticky="w")
        self.restore_btn = ttk.Button(
            btn_row, text="Restaurar original (desinstalar)", command=self.on_restore)
        self.restore_btn.grid(row=0, column=1, padx=(10, 0))

        self.status_var = tk.StringVar(value="Listo.")
        ttk.Label(frm, textvariable=self.status_var, font=("Segoe UI", 10, "bold")).grid(
            row=7, column=0, sticky="w", pady=(8, 2))
        self.progress = ttk.Progressbar(frm, mode="indeterminate")
        self.progress.grid(row=8, column=0, sticky="ew")

        ttk.Label(frm, text="Detalles:").grid(row=9, column=0, sticky="w", pady=(8, 0))
        from tkinter import scrolledtext
        self.logbox = scrolledtext.ScrolledText(frm, height=10, wrap="word",
                                                 font=("Consolas", 9), state="disabled")
        self.logbox.grid(row=10, column=0, sticky="nsew")
        frm.rowconfigure(10, weight=1)

        footer = (
            "%s\n"
            "Texto: %s (atribución · no comercial · compartir-igual)   ·   "
            "Código: %s\n%s"
            % (stamp.PROJECT_NAME, stamp.TRANSLATION_LICENSE, stamp.CODE_LICENSE,
               stamp.PROJECT_URL)
        )
        ttk.Label(frm, text=footer, foreground="#666", font=("Segoe UI", 8),
                  justify="left").grid(row=11, column=0, sticky="w", pady=(8, 0))

        self._log("Bienvenido. Este instalador no modifica los archivos originales del "
                  "juego: crea un archivo de traducción que el juego carga con prioridad. "
                  "Puedes revertirlo cuando quieras con «Restaurar original».\n")
        # Autodetección en segundo plano para no congelar la ventana.
        threading.Thread(target=self._detect_worker, daemon=True).start()
        self.root.after(80, self._drain)

    # ---- utilidades de UI (solo en el hilo principal) ----
    def _log(self, msg):
        self.logbox.configure(state="normal")
        self.logbox.insert("end", msg + ("\n" if not msg.endswith("\n") else ""))
        self.logbox.see("end")
        self.logbox.configure(state="disabled")

    def _set_busy(self, busy, status=None):
        self.busy = busy
        state = "disabled" if busy else "normal"
        self.install_btn.configure(state=state)
        self.restore_btn.configure(state=state)
        self.browse_btn.configure(state=state)
        if busy:
            self.progress.start(12)
        else:
            self.progress.stop()
        if status is not None:
            self.status_var.set(status)

    # ---- callbacks de botones ----
    def on_browse(self):
        from tkinter import filedialog
        d = filedialog.askdirectory(title="Selecciona la carpeta del juego (con pscript.dat)")
        if d:
            self.path_var.set(d)
            if scan.looks_like_game_dir(d):
                self._log("Carpeta seleccionada: " + d)
            else:
                self._log("Aviso: esa carpeta no parece la del juego. Aun así puedes "
                          "intentar instalar; te avisaré si no encuentro pscript.dat.")

    def _game_dir(self):
        p = self.path_var.get().strip()
        if not p or p.startswith("Buscando") or p.startswith("No se encontró"):
            return None
        return p

    def on_install(self):
        if self.busy:
            return
        self._set_busy(True, "Instalando…")
        self._log("\n=== Instalando parche ===")
        threading.Thread(target=self._install_worker, args=(self._game_dir(),),
                         daemon=True).start()

    def on_restore(self):
        if self.busy:
            return
        from tkinter import messagebox
        if not messagebox.askyesno(
                "Restaurar original",
                "Esto quitará el parche y devolverá el juego a su idioma original.\n\n"
                "¿Continuar?"):
            return
        self._set_busy(True, "Restaurando…")
        self._log("\n=== Restaurando original ===")
        threading.Thread(target=self._restore_worker, args=(self._game_dir(),),
                         daemon=True).start()

    # ---- workers (hilo aparte; solo hablan por la cola) ----
    def _detect_worker(self):
        try:
            cands = scan.autodetect()
        except Exception as e:  # noqa: BLE001
            cands = []
            self.q.put(("log", "No pude autodetectar: %r" % e))
        self.q.put(("detect", cands))

    def _install_worker(self, game_dir):
        try:
            res = installer.run_install(game_dir, log=lambda m: self.q.put(("log", m)))
            self.q.put(("done", ("install", res)))
        except installer.InstallError as e:
            self.q.put(("fail", str(e)))
        except Exception as e:  # noqa: BLE001
            self.q.put(("fail", "Error inesperado: %r" % e))

    def _restore_worker(self, game_dir):
        try:
            res = installer.run_uninstall(game_dir, log=lambda m: self.q.put(("log", m)))
            self.q.put(("done", ("uninstall", res)))
        except installer.InstallError as e:
            self.q.put(("fail", str(e)))
        except Exception as e:  # noqa: BLE001
            self.q.put(("fail", "Error inesperado: %r" % e))

    # ---- bombeo de la cola hacia la UI ----
    def _drain(self):
        from tkinter import messagebox
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "log":
                    self._log(payload)
                elif kind == "detect":
                    if payload:
                        self.path_var.set(payload[0])
                        self.status_var.set("Juego detectado. Listo para instalar.")
                        self._log("Juego detectado: " + payload[0])
                        if len(payload) > 1:
                            self._log("(Hay varias copias; si no es la correcta, usa «Buscar…».)")
                    else:
                        self.path_var.set("")
                        self.status_var.set("No encontré el juego: usa «Buscar…».")
                        self._log("No se encontró el juego automáticamente. Pulsa «Buscar…» "
                                  "y elige la carpeta que contiene pscript.dat.")
                elif kind == "done":
                    action, res = payload
                    self._set_busy(False, "Listo.")
                    if action == "install":
                        self.status_var.set("¡Instalado! Inicia el juego.")
                        messagebox.showinfo(
                            "¡Parche instalado!",
                            "El parche al español se instaló correctamente.\n\n"
                            "Cobertura: %.1f%%\nCarpeta: %s\n\n"
                            "Inicia el juego normalmente; el texto aparecerá en español. "
                            "Si algo falla, usa «Restaurar original»."
                            % (res.get("coverage_pct", 0.0), res.get("game_dir", "")))
                    else:
                        msg = {"restaurado": "Se restauró el 0.utf original.",
                               "eliminado": "Se quitó el parche; el juego vuelve al idioma "
                                            "original.",
                               "nada": "No había parche instalado."}.get(
                                   res.get("action"), "Hecho.")
                        self.status_var.set("Original restaurado.")
                        messagebox.showinfo("Restaurado", msg)
                elif kind == "fail":
                    self._set_busy(False, "Hubo un problema.")
                    self._log("ERROR: " + payload)
                    messagebox.showerror("No se pudo completar", payload)
        except queue.Empty:
            pass
        self.root.after(80, self._drain)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if "--selftest" in argv:
        return _selftest()
    import tkinter as tk
    root = tk.Tk()
    PatcherGUI(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
