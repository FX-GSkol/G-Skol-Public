#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from core.collection_folders import CollectionFolderStore


class CollectionManager:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    @staticmethod
    def _ensure_table(connection: sqlite3.Connection) -> None:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS collections(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                owner TEXT,
                description TEXT,
                created_at TEXT NOT NULL
            )"""
        )

    def create_collection(self, data: dict[str, str]) -> int:
        name = data.get("name", "").strip()
        if not name:
            raise ValueError("Le nom de la collection est obligatoire.")

        with self._connect() as connection:
            self._ensure_table(connection)
            duplicate = connection.execute(
                "SELECT 1 FROM collections WHERE name = ? COLLATE NOCASE LIMIT 1",
                (name,),
            ).fetchone()
            if duplicate is not None:
                raise ValueError(f"Une collection nommée « {name} » existe déjà.")

            cursor = connection.execute(
                """INSERT INTO collections(name, owner, description, created_at)
                   VALUES (?, ?, ?, ?)""",
                (
                    name,
                    data.get("owner", "").strip(),
                    data.get("description", "").strip(),
                    datetime.now().isoformat(timespec="seconds"),
                ),
            )
            return int(cursor.lastrowid)

    def get_collection_by_name(self, name: str) -> dict[str, Any] | None:
        if not name.strip():
            return None
        with self._connect() as connection:
            self._ensure_table(connection)
            row = connection.execute(
                """SELECT id, name, owner, description, created_at
                   FROM collections
                   WHERE name = ? COLLATE NOCASE
                   ORDER BY id DESC
                   LIMIT 1""",
                (name.strip(),),
            ).fetchone()
        return dict(row) if row is not None else None

    def get_collection_by_id(self, collection_id: int) -> dict[str, Any] | None:
        with self._connect() as connection:
            self._ensure_table(connection)
            row = connection.execute(
                """SELECT id, name, owner, description, created_at
                   FROM collections WHERE id = ?""",
                (int(collection_id),),
            ).fetchone()
        return dict(row) if row is not None else None

    def inspect_collections(self) -> list[dict[str, Any]]:
        """Lit les collections d'un fichier existant sans jamais le modifier.

        Utilisé par « Parcourir… » pour vérifier qu'un fichier choisi est bien
        une base MM3 avant de l'ouvrir.
        """
        if not self.db_path.exists() or not self.db_path.is_file():
            raise ValueError("Le fichier sélectionné n'existe pas.")

        uri = self.db_path.resolve().as_uri() + "?mode=ro"
        try:
            connection = sqlite3.connect(uri, uri=True)
            connection.row_factory = sqlite3.Row
            tables = {
                str(row[0])
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            required = {"collections", "records", "mm3_meta"}
            if not required.issubset(tables):
                missing = ", ".join(sorted(required - tables))
                raise ValueError(
                    "Le fichier ne possède pas la structure attendue d'une base MM3"
                    + (f" (table(s) manquante(s) : {missing})." if missing else ".")
                )
            rows = connection.execute(
                """SELECT id, name, owner, description, created_at
                   FROM collections
                   ORDER BY name COLLATE NOCASE, id"""
            ).fetchall()
        except sqlite3.DatabaseError as exc:
            raise ValueError("Le fichier sélectionné n'est pas une base SQLite MM3 valide.") from exc
        finally:
            try:
                connection.close()
            except Exception:
                pass
        return [dict(row) for row in rows]

    def list_collections(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            self._ensure_table(connection)
            rows = connection.execute(
                """SELECT id, name, owner, description, created_at
                   FROM collections
                   ORDER BY name COLLATE NOCASE, id"""
            ).fetchall()
        return [dict(row) for row in rows]

    def update_collection_metadata(
        self,
        collection_id: int,
        *,
        owner: str | None = None,
        created_at: str | None = None,
        description: str | None = None,
    ) -> dict[str, Any]:
        """Modifie les informations descriptives d'une collection.

        Une chaîne vide est volontairement acceptée : elle permet d'effacer
        Propriétaire, Date ou Description depuis la liste des collections.
        """
        changes = []
        params = []
        if owner is not None:
            changes.append("owner = ?")
            params.append(str(owner).strip())
        if created_at is not None:
            changes.append("created_at = ?")
            params.append(str(created_at).strip())
        if description is not None:
            changes.append("description = ?")
            params.append(str(description).strip())

        if not changes:
            current = self.get_collection_by_id(collection_id)
            if current is None:
                raise ValueError("La collection n'existe plus.")
            return current

        params.append(int(collection_id))
        with self._connect() as connection:
            self._ensure_table(connection)
            connection.execute(
                f"UPDATE collections SET {', '.join(changes)} WHERE id = ?",
                tuple(params),
            )

        updated = self.get_collection_by_id(collection_id)
        if updated is None:
            raise ValueError("La collection n'existe plus.")
        return updated

    def rename_collection(self, collection_id: int, new_name: str) -> dict[str, Any]:
        new_name = new_name.strip()
        if not new_name:
            raise ValueError("Le nom de la collection est obligatoire.")
        with self._connect() as connection:
            self._ensure_table(connection)
            duplicate = connection.execute(
                """SELECT 1 FROM collections
                   WHERE name = ? COLLATE NOCASE AND id <> ? LIMIT 1""",
                (new_name, int(collection_id)),
            ).fetchone()
            if duplicate is not None:
                raise ValueError(f"Une collection nommée « {new_name} » existe déjà.")
            connection.execute(
                "UPDATE collections SET name = ? WHERE id = ?",
                (new_name, int(collection_id)),
            )
        renamed = self.get_collection_by_id(collection_id)
        if renamed is None:
            raise ValueError("La collection à renommer n'existe plus.")
        return renamed

    def delete_collection(self, collection_id: int) -> None:
        """Supprime une collection et ses données dépendantes connues.

        La suppression est volontairement centralisée ici afin d'éviter de
        laisser des fiches ou des valeurs de référentiels orphelines.
        """
        with self._connect() as connection:
            self._ensure_table(connection)
            # Les tables peuvent ne pas encore exister dans une ancienne base.
            tables = {
                str(row[0])
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            if "referential_values" in tables and "referential_definitions" in tables:
                connection.execute(
                    """DELETE FROM referential_values
                       WHERE definition_id IN (
                           SELECT id FROM referential_definitions WHERE collection_id = ?
                       )""",
                    (int(collection_id),),
                )
                connection.execute(
                    "DELETE FROM referential_definitions WHERE collection_id = ?",
                    (int(collection_id),),
                )
            if "records" in tables:
                connection.execute(
                    "DELETE FROM records WHERE collection_id = ?",
                    (int(collection_id),),
                )
            connection.execute(
                "DELETE FROM collections WHERE id = ?",
                (int(collection_id),),
            )

    def collections_folder(self) -> Path:
        """Retourne le dossier utilisateur Workspace/Collections.

        Depuis 018.4.4.1.2.9 la base technique .mm3-system.db vit dans BacASable ;
        il ne faut donc plus déduire le dossier Collections avec db_path.parent.
        """
        path = self.db_path.resolve()
        if path.name.casefold() == ".mm3-system.db" and path.parent.name.casefold() == "bacasable":
            return path.parent.parent / "Collections"
        return path.parent

    @staticmethod
    def _safe_filename(name: str) -> str:
        forbidden = '<>:"/\\|?*'
        cleaned = "".join("_" if ch in forbidden else ch for ch in str(name).strip())
        cleaned = cleaned.rstrip(" .")
        return cleaned or "Collection"

    def discover_collection_files(self) -> list[dict[str, Any]]:
        """Découvre les fichiers MM3 autonomes présents dans le dossier Collections."""
        found: list[dict[str, Any]] = []
        folder = self.collections_folder()
        if not folder.exists():
            return found
        for path in sorted(folder.iterdir(), key=lambda p: p.name.casefold()):
            if not path.is_file() or path.suffix.casefold() != ".coldb":
                continue
            if path.resolve() == self.db_path.resolve():
                continue
            # Ancien conteneur multi-collections : conservé uniquement comme
            # sauvegarde/migration, jamais affiché depuis 018.4.4.1.2.9.
            if path.name.casefold() in {"micromin3.db", ".mm3-system.db"}:
                continue
            try:
                rows = CollectionManager(path).inspect_collections()
            except Exception:
                continue
            for row in rows:
                item = dict(row)
                item["_database_path"] = str(path.resolve())
                item["_standalone_file"] = True
                item["_folder_name"] = CollectionFolderStore(folder).folder_for(path)
                found.append(item)
        return found

    def import_collection_to_folder(
        self,
        collection_id: int,
        destination_folder: str | Path,
        requested_name: str | None = None,
    ) -> dict[str, Any]:
        """Importe une collection MM3 existante comme fichier autonome.

        Aucun contrôle de doublon de contenu n'est effectué : deux collections
        identiques sont volontairement autorisées. Seul un conflit de nom est
        résolu par « Nom - 2 », « Nom - 3 », etc.
        """
        source = self.get_collection_by_id(int(collection_id))
        if source is None:
            raise ValueError("La collection MM3 sélectionnée n'existe plus.")

        folder = Path(destination_folder)
        folder.mkdir(parents=True, exist_ok=True)

        base_name = str(requested_name or source.get("name") or "Collection").strip()
        if not base_name:
            base_name = "Collection"

        # Les noms déjà présents sont regardés uniquement pour produire un nom
        # distinct. Le contenu des bases n'est jamais comparé.
        existing_names: set[str] = set()
        for p in folder.iterdir():
            if not p.is_file() or p.suffix.casefold() not in {".coldb", ".db", ".sqlite", ".sqlite3"}:
                continue
            try:
                for row in CollectionManager(p).inspect_collections():
                    existing_names.add(str(row.get("name") or "").strip().casefold())
            except Exception:
                pass

        candidate = base_name
        suffix = 2
        while (
            candidate.casefold() in existing_names
            or any((folder / (self._safe_filename(candidate) + ext)).exists()
                   for ext in (".coldb", ".db", ".sqlite", ".sqlite3"))
        ):
            candidate = f"{base_name} - {suffix}"
            suffix += 1

        destination = folder / (self._safe_filename(candidate) + ".coldb")

        # Copie SQLite sûre par backup : le fichier source n'est jamais modifié.
        src_conn = sqlite3.connect(self.db_path)
        try:
            dst_conn = sqlite3.connect(destination)
            try:
                src_conn.backup(dst_conn)
                dst_conn.commit()
            finally:
                dst_conn.close()
        finally:
            src_conn.close()

        # Si le fichier source contient plusieurs collections, ne conserver que
        # celle choisie. Pour une base MM3 autonome classique, cela ne change rien.
        connection = sqlite3.connect(destination)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA foreign_keys=OFF")
            tables = [
                str(row[0])
                for row in connection.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                ).fetchall()
            ]
            for table in tables:
                cols = {
                    str(row[1])
                    for row in connection.execute(
                        f'PRAGMA table_info("{table}")'
                    ).fetchall()
                }
                if table != "collections" and "collection_id" in cols:
                    connection.execute(
                        f'DELETE FROM "{table}" WHERE collection_id <> ?',
                        (int(collection_id),),
                    )

            if "referential_values" in tables and "referential_definitions" in tables:
                connection.execute(
                    """DELETE FROM referential_values
                       WHERE definition_id NOT IN
                       (SELECT id FROM referential_definitions)"""
                )

            connection.execute(
                "DELETE FROM collections WHERE id <> ?",
                (int(collection_id),),
            )
            connection.execute(
                "UPDATE collections SET name=? WHERE id=?",
                (candidate, int(collection_id)),
            )
            connection.commit()
        except Exception:
            try:
                connection.close()
            finally:
                try:
                    destination.unlink()
                except Exception:
                    pass
            raise
        finally:
            try:
                connection.close()
            except Exception:
                pass

        imported = CollectionManager(destination).get_collection_by_id(int(collection_id))
        if imported is None:
            raise ValueError("La collection importée n'a pas pu être relue.")

        result = dict(imported)
        result["_database_path"] = str(destination.resolve())
        result["_standalone_file"] = True
        return result

    def duplicate_collection_to_file(self, collection_id: int, requested_name: str | None = None) -> dict[str, Any]:
        """Duplique une collection dans un fichier SQLite autonome et indépendant."""
        source = self.get_collection_by_id(int(collection_id))
        if source is None:
            raise ValueError("La collection à dupliquer n'existe plus.")

        base_name = (requested_name or f"{source['name']} - Copie").strip()
        if not base_name:
            base_name = f"{source['name']} - Copie"

        folder = self.db_path.parent
        folder.mkdir(parents=True, exist_ok=True)

        candidate = base_name
        suffix = 1
        while True:
            filename = self._safe_filename(candidate) + ".coldb"
            destination = folder / filename
            if not destination.exists():
                break
            suffix += 1
            candidate = f"{base_name} {suffix}"

        final_name = candidate

        # Copie SQLite sûre.
        src_conn = sqlite3.connect(self.db_path)
        try:
            dst_conn = sqlite3.connect(destination)
            try:
                src_conn.backup(dst_conn)
                dst_conn.commit()
            finally:
                dst_conn.close()
        finally:
            src_conn.close()

        # Epure la copie : une seule collection reste dans le fichier.
        connection = sqlite3.connect(destination)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA foreign_keys=OFF")
            tables = [
                str(row[0])
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                ).fetchall()
            ]
            for table in tables:
                cols = {
                    str(row[1])
                    for row in connection.execute(f'PRAGMA table_info("{table}")').fetchall()
                }
                if table != "collections" and "collection_id" in cols:
                    connection.execute(
                        f'DELETE FROM "{table}" WHERE collection_id <> ?',
                        (int(collection_id),),
                    )

            if "referential_values" in tables and "referential_definitions" in tables:
                connection.execute(
                    """DELETE FROM referential_values
                       WHERE definition_id NOT IN (SELECT id FROM referential_definitions)"""
                )

            connection.execute("DELETE FROM collections WHERE id <> ?", (int(collection_id),))
            connection.execute(
                "UPDATE collections SET name = ? WHERE id = ?",
                (final_name, int(collection_id)),
            )
            connection.commit()
        except Exception:
            try:
                connection.close()
            finally:
                try:
                    destination.unlink()
                except Exception:
                    pass
            raise
        finally:
            try:
                connection.close()
            except Exception:
                pass

        duplicated = CollectionManager(destination).get_collection_by_id(int(collection_id))
        if duplicated is None:
            raise ValueError("La copie a été créée mais n'a pas pu être relue.")
        result = dict(duplicated)
        result["_database_path"] = str(destination.resolve())
        result["_standalone_file"] = True
        return result

    def rename_standalone_collection(self, collection_id: int, new_name: str) -> dict[str, Any]:
        """Renomme atomiquement le fichier autonome et son nom interne."""
        new_name = new_name.strip()
        if not new_name:
            raise ValueError("Le nom de la collection est obligatoire.")

        old_path = self.db_path.resolve()
        target = old_path.with_name(self._safe_filename(new_name) + old_path.suffix)
        if target.resolve() != old_path and target.exists():
            raise ValueError(f"Un fichier nommé « {target.name} » existe déjà.")

        # Aucune connexion persistante n'est détenue par CollectionManager.
        # On renomme d'abord le fichier : si Windows le refuse, le nom interne
        # n'aura donc pas déjà été modifié.
        renamed_file = False
        if target.resolve() != old_path:
            # Windows peut conserver le handle quelques dizaines de ms après
            # la fermeture d'une fenêtre Qt. Le fichier est déjà libéré côté MM3,
            # mais MoveFileEx/rename peut encore répondre WinError 32 brièvement.
            last_error = None
            for _attempt in range(30):
                try:
                    old_path.rename(target)
                    last_error = None
                    break
                except PermissionError as exc:
                    last_error = exc
                    time.sleep(0.05)
                except OSError as exc:
                    # WinError 32 / sharing violation : même traitement.
                    if getattr(exc, "winerror", None) == 32:
                        last_error = exc
                        time.sleep(0.05)
                    else:
                        raise
            if last_error is not None:
                raise last_error
            self.db_path = target
            renamed_file = True

        try:
            renamed = self.rename_collection(collection_id, new_name)
        except Exception:
            # Rollback du nom de fichier si la mise à jour interne échoue.
            if renamed_file and self.db_path.exists() and not old_path.exists():
                try:
                    self.db_path.rename(old_path)
                    self.db_path = old_path
                except Exception:
                    pass
            raise

        result = dict(renamed)
        result["_database_path"] = str(self.db_path.resolve())
        result["_standalone_file"] = True
        return result
