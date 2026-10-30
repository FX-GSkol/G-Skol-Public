#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
import json
from pathlib import Path

UNCLASSIFIED = "Non classées"

class CollectionFolderStore:
    def __init__(self, collections_folder: str | Path) -> None:
        self.folder = Path(collections_folder)
        self.path = self.folder / ".mm3-collection-folders.json"
        self.data = {"sort_mode": "az", "folders": [], "assignments": {}}
        self.load()

    def load(self):
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(raw, dict): self.data.update(raw)
        except Exception:
            pass
        self.data["folders"] = [str(x).strip() for x in self.data.get("folders", []) if str(x).strip() and str(x).strip().casefold() != UNCLASSIFIED.casefold()]
        self.data["assignments"] = {str(k): str(v) for k,v in dict(self.data.get("assignments", {})).items()}
        if self.data.get("sort_mode") not in {"az","za","custom"}: self.data["sort_mode"]="az"

    def save(self):
        self.folder.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def key(db_path: str | Path) -> str:
        return Path(db_path).name.casefold()

    def folder_for(self, db_path: str | Path) -> str:
        key = self.key(db_path)
        if key not in self.data["assignments"] and Path(db_path).suffix.casefold() == ".coldb":
            old_key = Path(db_path).with_suffix(".db").name.casefold()
            if old_key in self.data["assignments"] and not (self.folder / Path(db_path).with_suffix(".db").name).exists():
                self.data["assignments"][key] = self.data["assignments"].pop(old_key)
                self.save()
        value = self.data["assignments"].get(key, UNCLASSIFIED)
        valid = {x.casefold(): x for x in self.data["folders"]}
        return valid.get(str(value).casefold(), UNCLASSIFIED)

    def assign(self, db_paths, folder_name: str):
        target = UNCLASSIFIED if folder_name.casefold() == UNCLASSIFIED.casefold() else folder_name
        for p in db_paths:
            k=self.key(p)
            if target == UNCLASSIFIED: self.data["assignments"].pop(k, None)
            else: self.data["assignments"][k]=target
        self.save()

    @staticmethod
    def normalize(name: str) -> str:
        parts = [part.strip() for part in str(name or "").replace("\\", "/").split("/")]
        if any(part in {".", ".."} for part in parts):
            raise ValueError("Nom de dossier invalide.")
        return "/".join(part for part in parts if part)

    def add_folder(self, name: str):
        name = self.normalize(name)
        if not name or name.casefold()==UNCLASSIFIED.casefold(): raise ValueError("Ce nom de dossier est réservé.")
        if any(x.casefold()==name.casefold() for x in self.data["folders"]): raise ValueError("Ce dossier existe déjà.")
        parts = name.split("/")
        existing = {x.casefold() for x in self.data["folders"]}
        for i in range(1, len(parts)+1):
            parent = "/".join(parts[:i])
            if parent.casefold() not in existing:
                self.data["folders"].append(parent)
                existing.add(parent.casefold())
        self.save()

    def rename_folder(self, old: str, new: str):
        old, new = self.normalize(old), self.normalize(new)
        if not old or old not in self.data["folders"]: raise ValueError("Dossier introuvable.")
        if not new or new.casefold()==UNCLASSIFIED.casefold() or new.casefold().startswith(old.casefold()+"/"):
            raise ValueError("Nom de dossier invalide.")
        affected = [x for x in self.data["folders"] if x.casefold()==old.casefold() or x.casefold().startswith(old.casefold()+"/")]
        mapped = {x: new+x[len(old):] for x in affected}
        others = {x.casefold() for x in self.data["folders"] if x not in affected}
        if any(v.casefold() in others for v in mapped.values()): raise ValueError("Ce dossier existe déjà.")
        self.data["folders"] = [mapped.get(x,x) for x in self.data["folders"]]
        for k,v in list(self.data["assignments"].items()):
            for original, updated in mapped.items():
                if v.casefold()==original.casefold():
                    self.data["assignments"][k]=updated
                    break
        self.save()

    def delete_folder(self, name: str):
        name = self.normalize(name)
        if not name or name.casefold()==UNCLASSIFIED.casefold(): return
        self.data["folders"]=[x for x in self.data["folders"] if x.casefold()!=name.casefold()
                              and not x.casefold().startswith(name.casefold()+"/")]
        for k,v in list(self.data["assignments"].items()):
            if v.casefold()==name.casefold() or v.casefold().startswith(name.casefold()+"/"):
                self.data["assignments"].pop(k,None)
        self.save()

    def ordered_folders(self):
        vals=list(self.data["folders"])
        mode=self.data.get("sort_mode","az")
        if mode=="az": vals.sort(key=str.casefold)
        elif mode=="za": vals.sort(key=str.casefold, reverse=True)
        return vals + [UNCLASSIFIED]

    def set_sort_mode(self, mode): self.data["sort_mode"]=mode; self.save()
    def move(self, name, delta):
        vals=self.data["folders"]
        try: i=next(i for i,x in enumerate(vals) if x.casefold()==name.casefold())
        except StopIteration: return
        j=max(0,min(len(vals)-1,i+delta))
        if i!=j: vals[i],vals[j]=vals[j],vals[i]; self.data["sort_mode"]="custom"; self.save()

    def migrate_path(self, old_path, new_path):
        old=self.key(old_path); new=self.key(new_path)
        if old in self.data["assignments"]:
            self.data["assignments"][new]=self.data["assignments"].pop(old); self.save()

def collection_display_name(collection: dict, language: str = "fr") -> str:
    name=str(collection.get("name") or "")
    if collection.get("_external_temporary"):
        return f"{name} — Extérieure (temporaire)" if name else "Extérieure (temporaire)"
    folder=str(collection.get("_folder_name") or UNCLASSIFIED)
    if folder.casefold() == UNCLASSIFIED.casefold():
        lang = str(language or "fr").lower()
        folder = "Nicht klassifiziert" if lang.startswith("de") else ("Unclassified" if lang.startswith("en") else UNCLASSIFIED)
    return f"{name} — {folder}" if name else folder
