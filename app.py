#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import signal
import traceback
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon
from core.version import APP_NAME, APP_VERSION
from core.db_file_association import register_db_association
from core.paths import WORKSPACE
from core.startup import Startup
from ui.main_window import MainWindow
from ui.record_window import RecordWindow
from ui.mm3_style import MM3ProxyStyle


def _install_error_log() -> None:
    """Capture exceptions in Qt callbacks, including windowed PyInstaller builds."""
    previous_hook = sys.excepthook

    def log_exception(exc_type, exc_value, exc_tb):
        try:
            base = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else PROJECT_ROOT
            log = base / "ERREURS-G-SKOL.txt"
            with log.open("a", encoding="utf-8") as output:
                output.write("\n=== " + datetime.now().isoformat(timespec="seconds") + " ===\n")
                traceback.print_exception(exc_type, exc_value, exc_tb, file=output)
        except Exception:
            pass
        previous_hook(exc_type, exc_value, exc_tb)

    sys.excepthook = log_exception


def main() -> int:
    from diagnostic_trace import start as start_diagnostics, log as diagnostic_log, instrument_main_window
    start_diagnostics()
    _install_error_log()
    instrument_main_window(MainWindow)
    from performance_diagnostic import install as install_performance_diagnostic
    install_performance_diagnostic(MainWindow, RecordWindow)
    # MM3 utilise Ctrl+C dans l'interface (copie de champs, photos, etc.).
    # Sous Windows avec une console attachée, ce raccourci peut aussi être
    # interprété comme SIGINT et produire un KeyboardInterrupt parasite.
    if sys.platform.startswith("win"):
        try:
            signal.signal(signal.SIGINT, signal.SIG_IGN)
        except Exception:
            pass

    # Sous Windows, attribuer une identité propre à G-Skol avant de créer
    # QApplication. Sans AppUserModelID explicite, une exécution via Python
    # peut conserver l'icône Python dans la barre des tâches malgré
    # QApplication.setWindowIcon().
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "G-Skol.GestionCollections"
            )
        except (AttributeError, OSError):
            pass

    diagnostic_log("AVANT QApplication")
    app = QApplication(sys.argv)
    diagnostic_log("APRES QApplication")
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    icon_root = Path(getattr(sys, "_MEIPASS", PROJECT_ROOT))
    icon_path = icon_root / "assets" / "G-Skol.ico"
    if icon_path.is_file():
        app.setWindowIcon(QIcon(str(icon_path)))

    # Rend MM3 visible dans « Ouvrir avec » sans imposer d'application par défaut.
    portable_build = (getattr(sys, "frozen", False) and
                      ((Path(sys.executable).parent / "G-Skol.portable").is_file() or
                       (Path(sys.executable).parent / "Col-Div.portable").is_file()))
    if sys.platform == "win32" and not portable_build:
        try:
            register_db_association(PROJECT_ROOT / "app.py", make_default=bool(getattr(sys, "frozen", False)))
        except (OSError, ValueError):
            pass

    # Ergonomie générale : conserver le style natif tout en élargissant les
    # ascenseurs (notamment ceux des longues listes déroulantes).
    app.setStyle(MM3ProxyStyle(app.style()))

    # Le proxy MM3 dessine lui-même les ascenseurs en 2D. Aucun QSS global
    # n’est appliqué : cela évite de repolir tous les widgets à l’ouverture.


    startup = Startup(WORKSPACE)
    startup.initialize()

    requested_db = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else None
    diagnostic_log("AVANT MainWindow")
    window = MainWindow(startup=startup, restore_last_collection=requested_db is None)
    diagnostic_log("APRES MainWindow")
    window.show()
    if requested_db is not None:
        # Attendre que l'interface soit prête avant de charger le fichier reçu
        # depuis l'Explorateur Windows (chemin entre guillemets, espaces compris).
        QTimer.singleShot(0, lambda: window.open_collection_file(requested_db))

    diagnostic_log("DEBUT BOUCLE QT")
    rc = app.exec()
    diagnostic_log("FIN BOUCLE QT code=" + str(rc))
    startup.shutdown()
    diagnostic_log("ARRET NORMAL")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
