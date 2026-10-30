#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pathlib import Path

from core.database import DatabaseManager
from core.settings import Settings
from core.workspace import WorkspaceManager
from core.logger import Logger


class Startup:
    def __init__(self, workspace_root: Path):
        self.workspace = WorkspaceManager(workspace_root)
        self.workspace.initialize()
        from core.model_library import install_example_models
        install_example_models(self.workspace.root)

        self.logger = Logger(self.workspace.journals_path / "mm3.log")
        self.settings = Settings(self.workspace.settings_path / "mm3.ini")
        self.database = DatabaseManager(
            self.workspace.sandbox_path / ".mm3-system.db"
        )

    def initialize(self):
        self.logger.info("Démarrage G-Skol")
        self.logger.info("Workspace initialisé")

        self.settings.load()
        self.logger.info("Paramètres chargés")

        # 018.4.4.1.2.7.1 — la base technique n'a rien à faire parmi les collections.
        # Si une ancienne version l'a créée dans Workspace/Collections, on la
        # déplace automatiquement vers BacASable avant l'initialisation.
        old_system_db = self.workspace.collections_path / ".mm3-system.db"
        new_system_db = self.workspace.sandbox_path / ".mm3-system.db"
        if old_system_db.exists() and not new_system_db.exists():
            try:
                old_system_db.replace(new_system_db)
            except OSError:
                # Si Windows refuse le déplacement, la nouvelle base technique
                # sera créée dans BacASable ; l'ancien fichier pourra être supprimé
                # manuellement après fermeture de l'ancienne version.
                pass

        self.database.initialize()

        if self.database.check_integrity():
            self.logger.info("Base SQLite OK")
        else:
            self.logger.error("Échec du contrôle d'intégrité SQLite")

        self.logger.info("Interface graphique créée")
        self.logger.info("G-Skol prêt")
        return True

    def shutdown(self):
        self.logger.info("Arrêt MM3")
        self.database.disconnect()
