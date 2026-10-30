#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pathlib import Path
import sqlite3
from sqlite3 import Connection

class DatabaseManager:
    def __init__(self,database_path:Path):
        self.database_path=Path(database_path)
        self.connection:Connection|None=None
    def connect(self)->Connection:
        if self.connection is None:
            self.database_path.parent.mkdir(parents=True,exist_ok=True)
            self.connection=sqlite3.connect(self.database_path)
            self.connection.execute("PRAGMA foreign_keys=ON;")
        return self.connection
    def disconnect(self):
        if self.connection:
            self.connection.close()
            self.connection=None
    def initialize(self):
        self.connect()
        c=self.connection.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS mm3_meta(parameter TEXT PRIMARY KEY,value TEXT)")
        self.connection.commit()
    def check_integrity(self)->bool:
        c=self.connection.cursor()
        c.execute("PRAGMA integrity_check;")
        r=c.fetchone()
        return bool(r and r[0]=="ok")
