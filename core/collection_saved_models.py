"""Modèles enregistrés dans la base SQLite de chaque collection.

Les anciens fichiers JSON indexaient seulement un numéro interne, réutilisé par
plusieurs fichiers autonomes. Une migration automatique ne permet pas d'attribuer
ces entrées avec certitude à la bonne collection.
"""
import json
import sqlite3
from pathlib import Path


def _legacy_entry(legacy_path, collection_id):
    try:
        data = json.loads(Path(legacy_path).read_text(encoding="utf-8"))
        candidate = data.get("collections", {}).get(str(collection_id), {})
        return candidate if isinstance(candidate, dict) else {}
    except (OSError, ValueError, TypeError, AttributeError):
        return {}


def load(database_path, collection_id, kind, legacy_path=None):
    database_path = Path(database_path)
    # Une base autonome dans Collections a son propre espace de noms.
    autonomous = database_path.parent.name.casefold() == "collections"
    with sqlite3.connect(database_path) as con:
        con.execute("CREATE TABLE IF NOT EXISTS collection_saved_models (collection_id INTEGER NOT NULL, kind TEXT NOT NULL, content TEXT NOT NULL, PRIMARY KEY(collection_id, kind))")
        row = con.execute("SELECT content FROM collection_saved_models WHERE collection_id=? AND kind=?", (int(collection_id), kind)).fetchone()
        legacy = _legacy_entry(legacy_path, collection_id) if legacy_path is not None else {}
        if row is not None:
            entry = json.loads(row[0])
            # Les versions .143-.145 ont parfois copié mot pour mot le même JSON
            # dans chaque .db (identifiant 1). Écarter seulement la copie intacte,
            # et garder une sauvegarde dans la base pour une reprise manuelle.
            model_key = {"etat": "reports", "requete": "queries", "tableau": "views"}.get(kind)
            old_models = legacy.get(model_key, {}) if model_key else {}
            current_models = entry.get(model_key, {}) if isinstance(entry, dict) and model_key else {}
            copied = [name for name, definition in current_models.items()
                      if isinstance(old_models, dict) and name in old_models and old_models[name] == definition] \
                     if isinstance(current_models, dict) else []
            if autonomous and legacy and (entry == legacy or copied):
                con.execute("CREATE TABLE IF NOT EXISTS collection_saved_models_legacy_backup (collection_id INTEGER NOT NULL, kind TEXT NOT NULL, content TEXT NOT NULL, PRIMARY KEY(collection_id, kind))")
                con.execute("INSERT OR IGNORE INTO collection_saved_models_legacy_backup VALUES (?, ?, ?)", (int(collection_id), kind, row[0]))
                if entry == legacy:
                    entry = {}
                else:
                    entry[model_key] = {name: definition for name, definition in current_models.items() if name not in copied}
                    if isinstance(entry.get("custom_order"), list):
                        entry["custom_order"] = [name for name in entry["custom_order"] if name not in copied]
                    if entry.get("last_query") in copied:
                        entry["last_query"] = None
                con.execute("UPDATE collection_saved_models SET content=? WHERE collection_id=? AND kind=?", (json.dumps(entry, ensure_ascii=False), int(collection_id), kind))
                return entry
            return entry
        entry = {} if autonomous else legacy
        con.execute("INSERT INTO collection_saved_models (collection_id, kind, content) VALUES (?, ?, ?)", (int(collection_id), kind, json.dumps(entry, ensure_ascii=False)))
        return entry


def save(database_path, collection_id, kind, entry):
    with sqlite3.connect(database_path) as con:
        con.execute("CREATE TABLE IF NOT EXISTS collection_saved_models (collection_id INTEGER NOT NULL, kind TEXT NOT NULL, content TEXT NOT NULL, PRIMARY KEY(collection_id, kind))")
        con.execute("INSERT INTO collection_saved_models (collection_id, kind, content) VALUES (?, ?, ?) ON CONFLICT(collection_id, kind) DO UPDATE SET content=excluded.content", (int(collection_id), kind, json.dumps(entry, ensure_ascii=False)))
