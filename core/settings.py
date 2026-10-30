#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from configparser import ConfigParser
from pathlib import Path

class Settings:
    def __init__(self, ini_file: Path):
        self.ini_file = Path(ini_file)
        self.config = ConfigParser()

    def load(self):
        if self.ini_file.exists():
            self.config.read(self.ini_file, encoding="utf-8")
        else:
            self.config["MM3"] = {
                "language": "fr",
                "theme": "system",
                "last_collection": "",
                "record_window_geometry": ""
            }
            self.save()

    def save(self):
        self.ini_file.parent.mkdir(parents=True, exist_ok=True)
        with self.ini_file.open("w", encoding="utf-8") as f:
            self.config.write(f)

    @property
    def language(self):
        return self.config["MM3"].get("language","fr")

    @language.setter
    def language(self, value):
        self.config["MM3"]["language"]=value

    @property
    def theme(self):
        return self.config["MM3"].get("theme","system")

    @theme.setter
    def theme(self,value):
        self.config["MM3"]["theme"]=value

    @property
    def last_collection(self):
        return self.config["MM3"].get("last_collection","")

    @last_collection.setter
    def last_collection(self,value):
        self.config["MM3"]["last_collection"]=value

    @property
    def last_collection_path(self):
        return self.config["MM3"].get("last_collection_path", "")

    @last_collection_path.setter
    def last_collection_path(self, value):
        self.config["MM3"]["last_collection_path"] = str(value or "")

    @property
    def last_collection_id(self):
        return self.config["MM3"].getint("last_collection_id", fallback=0)

    @last_collection_id.setter
    def last_collection_id(self, value):
        self.config["MM3"]["last_collection_id"] = str(int(value or 0))

    @property
    def restore_last_collection(self):
        return self.config["MM3"].getboolean("restore_last_collection", fallback=True)

    @restore_last_collection.setter
    def restore_last_collection(self, value):
        self.config["MM3"]["restore_last_collection"] = "true" if value else "false"

    @property
    def backup_directory(self):
        return self.config["MM3"].get("backup_directory", "")

    @backup_directory.setter
    def backup_directory(self, value):
        self.config["MM3"]["backup_directory"] = str(value or "")


    @property
    def record_window_geometry(self):
        return self.config["MM3"].get("record_window_geometry", "")

    @record_window_geometry.setter
    def record_window_geometry(self, value):
        self.config["MM3"]["record_window_geometry"] = str(value or "")


def preferred_backup_directory(workspace: Path) -> Path:
    settings = Settings(Path(workspace) / "Paramètres" / "mm3.ini")
    settings.load()
    chosen = Path(settings.backup_directory).expanduser() if settings.backup_directory else Path(workspace) / "Sauvegardes"
    return chosen if chosen.is_dir() else Path(workspace) / "Sauvegardes"
