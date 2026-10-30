#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pathlib import Path

class WorkspaceManager:
    REQUIRED_FOLDERS=(
        "BacASable","Collections","Exports","Imports",
        "Journaux","Paramètres","Photos","Rapports",
        "Sauvegardes","Temp"
    )

    def __init__(self, workspace_path: Path):
        self.root=Path(workspace_path)

    def initialize(self):
        self.root.mkdir(parents=True, exist_ok=True)
        for folder in self.REQUIRED_FOLDERS:
            (self.root/folder).mkdir(parents=True, exist_ok=True)

    @property
    def collections_path(self): return self.root/"Collections"
    @property
    def photos_path(self): return self.root/"Photos"
    @property
    def reports_path(self): return self.root/"Rapports"
    @property
    def imports_path(self): return self.root/"Imports"
    @property
    def exports_path(self): return self.root/"Exports"
    @property
    def backups_path(self): return self.root/"Sauvegardes"
    @property
    def journals_path(self): return self.root/"Journaux"
    @property
    def settings_path(self): return self.root/"Paramètres"
    @property
    def sandbox_path(self): return self.root/"BacASable"
    @property
    def temp_path(self): return self.root/"Temp"

    def file_in_reports(self,name:str)->Path:
        return self.reports_path/name

    def photo_file(self,name:str)->Path:
        return self.photos_path/name
