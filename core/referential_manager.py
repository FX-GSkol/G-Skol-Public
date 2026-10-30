#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


class ReferentialManager:
    """Moteur générique des référentiels MM3, isolé par collection."""

    DEFAULT_REFERENTIALS = (
        ("mineral_name", "Nom", True),
        ("mineral_class", "Classe", False),
        ("crystal_system", "Système cristallin", False),
        ("luminescence", "Luminescence", False),
        ("luminescence_intensity", "Intensité de luminescence", False),
        ("fluorescence_color", "Couleur de fluorescence", False),
        ("site_name", "Site", False),
        ("department", "Département", False),
        ("region", "Région", False),
        ("country", "Pays", False),
        ("box_type", "Contenant", False),
        ("category", "Catégorie", False),
        ("contact", "Contact", False),
        ("specimen_shape", "Forme", False),
        ("specimen_color", "Couleur", False),
        ("quality", "Qualité", False),
        ("minimum_magnification", "Grossissement mini", False),
        ("growth", "Croissance", False),
        ("origin", "Origine", False),
        ("place", "Lieu", False),
        ("record_state", "État de la fiche", False),
    )
    DEFAULT_VALUES = {
        "luminescence": ("Non", "Fluorescent", "Phosphorescence", "Fluorescence (UV 365 Nm)"),
        "luminescence_intensity": ("Aucune", "Très faible", "Faible", "Moyenne", "Forte", "Très forte", "Inconnue"),
        "fluorescence_color": ("Aucune", "Blanc", "Bleu", "Crème", "Jaune", "Orange", "Rose", "Rouge", "Vert", "Violet", "Multicolore"),
        "minimum_magnification": ("20 X",),
        "record_state": ("OK", "Vérifier", "Libre"),
    }

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        # Les migrations / valeurs par défaut sont coûteuses et immuables
        # pendant la vie de cette instance. Ne les refaire qu'une seule fois.
        self._defaults_ready: set[int] = set()
        # Cache de lecture local à cette instance/fenêtre.
        # Evite de rouvrir SQLite plusieurs fois pour le même référentiel.
        self._values_cache: dict[tuple[int, str, bool], tuple[str, ...]] = {}

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    @classmethod
    def _ensure_tables(cls, connection: sqlite3.Connection) -> None:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS referential_definitions(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                collection_id INTEGER NOT NULL,
                code TEXT NOT NULL,
                label TEXT NOT NULL,
                is_master INTEGER NOT NULL DEFAULT 0,
                sort_mode TEXT NOT NULL DEFAULT 'custom',
                created_at TEXT NOT NULL,
                UNIQUE(collection_id, code),
                FOREIGN KEY(collection_id) REFERENCES collections(id)
            )"""
        )
        connection.execute(
            """CREATE TABLE IF NOT EXISTS referential_values(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                definition_id INTEGER NOT NULL,
                value TEXT NOT NULL,
                sort_order INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(definition_id, value),
                FOREIGN KEY(definition_id) REFERENCES referential_definitions(id)
                    ON DELETE CASCADE
            )"""
        )

    def ensure_defaults(self, collection_id: int) -> None:
        """Crée et migre les référentiels d'une collection, une fois par instance."""
        cid = int(collection_id)
        if cid in self._defaults_ready:
            return
        with self._connect() as connection:
            # Une collection déjà initialisée par cette version n'a pas besoin
            # de rejouer les migrations à chaque démarrage de G-Skol.
            # Le contrôle est en lecture seule et indexé (clé primaire).
            # Sur les bases anciennes, la table n'existe pas : on exécute
            # normalement l'initialisation complète, puis on mémorise sa réussite.
            marker_version = 'gskol-referentials-20.26-v1'
            marker_table = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' "
                "AND name='gskol_initialization_markers'"
            ).fetchone()
            if marker_table is not None:
                already_ready = connection.execute(
                    "SELECT 1 FROM gskol_initialization_markers "
                    "WHERE collection_id=? AND version=?",
                    (cid, marker_version),
                ).fetchone()
                if already_ready is not None:
                    self._defaults_ready.add(cid)
                    return
            connection.execute(
                """CREATE TABLE IF NOT EXISTS referential_definitions(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    collection_id INTEGER NOT NULL,
                    code TEXT NOT NULL,
                    label TEXT NOT NULL,
                    is_master INTEGER NOT NULL DEFAULT 0,
                    sort_mode TEXT NOT NULL DEFAULT 'custom',
                    created_at TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT '',
                    UNIQUE(collection_id, code),
                    FOREIGN KEY(collection_id) REFERENCES collections(id)
                )"""
            )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS referential_values(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    definition_id INTEGER NOT NULL,
                    value TEXT NOT NULL,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT '',
                    UNIQUE(definition_id, value),
                    FOREIGN KEY(definition_id) REFERENCES referential_definitions(id)
                )"""
            )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS referential_value_exclusions(
                    collection_id INTEGER NOT NULL,
                    code TEXT NOT NULL,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT '',
                    PRIMARY KEY(collection_id, code, value COLLATE NOCASE),
                    FOREIGN KEY(collection_id) REFERENCES collections(id)
                )"""
            )

            # Migration complète des anciennes bases MM3.
            definition_columns = {
                str(row["name"])
                for row in connection.execute(
                    "PRAGMA table_info(referential_definitions)"
                ).fetchall()
            }
            definition_migrations = {
                "sort_mode": (
                    "ALTER TABLE referential_definitions "
                    "ADD COLUMN sort_mode TEXT NOT NULL DEFAULT 'custom'"
                ),
                "created_at": (
                    "ALTER TABLE referential_definitions "
                    "ADD COLUMN created_at TEXT NOT NULL DEFAULT ''"
                ),
                "updated_at": (
                    "ALTER TABLE referential_definitions "
                    "ADD COLUMN updated_at TEXT NOT NULL DEFAULT ''"
                ),
            }
            for column, sql in definition_migrations.items():
                if column not in definition_columns:
                    connection.execute(sql)

            value_columns = {
                str(row["name"])
                for row in connection.execute(
                    "PRAGMA table_info(referential_values)"
                ).fetchall()
            }
            value_migrations = {
                "sort_order": (
                    "ALTER TABLE referential_values "
                    "ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 0"
                ),
                "is_active": (
                    "ALTER TABLE referential_values "
                    "ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1"
                ),
                "created_at": (
                    "ALTER TABLE referential_values "
                    "ADD COLUMN created_at TEXT NOT NULL DEFAULT ''"
                ),
                "updated_at": (
                    "ALTER TABLE referential_values "
                    "ADD COLUMN updated_at TEXT NOT NULL DEFAULT ''"
                ),
            }
            for column, sql in value_migrations.items():
                if column not in value_columns:
                    connection.execute(sql)

            now = datetime.now().isoformat(timespec="seconds")

            # Compléter les horodatages vides issus des migrations anciennes.
            # Ne jamais réécrire tout le référentiel à chaque ouverture de Fiche.
            # Sur des imports volumineux, l'ancien UPDATE sans WHERE touchait
            # toutes les lignes même déjà migrées et pouvait coûter plusieurs
            # secondes. Seules les anciennes lignes réellement incomplètes sont
            # désormais corrigées.
            connection.execute(
                """UPDATE referential_definitions
                   SET created_at = CASE WHEN created_at = '' THEN ? ELSE created_at END,
                       updated_at = CASE WHEN updated_at = '' THEN ? ELSE updated_at END
                   WHERE created_at = '' OR updated_at = ''""",
                (now, now),
            )
            connection.execute(
                """UPDATE referential_values
                   SET created_at = CASE WHEN created_at = '' THEN ? ELSE created_at END,
                       updated_at = CASE WHEN updated_at = '' THEN ? ELSE updated_at END
                   WHERE created_at = '' OR updated_at = ''""",
                (now, now),
            )

            alphabetical_codes = {
                "mineral_name", "mineral_class", "crystal_system", "site_name",
                "department", "region", "country", "specimen_shape", "specimen_color",
            }
            for code, label, is_master in self.DEFAULT_REFERENTIALS:
                initial_sort_mode = "asc" if code in alphabetical_codes else "custom"
                connection.execute(
                    """INSERT OR IGNORE INTO referential_definitions(
                           collection_id, code, label, is_master, sort_mode,
                           created_at, updated_at
                       ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        int(collection_id),
                        code,
                        label,
                        1 if is_master else 0,
                        initial_sort_mode,
                        now,
                        now,
                    ),
                )

            # Harmonisation cosmétique des anciennes collections :
            # le référentiel de la fiche s'appelle désormais simplement « Site ».
            connection.execute(
                """UPDATE referential_definitions
                   SET label = 'Site', updated_at = ?
                   WHERE collection_id = ? AND code = 'site_name'
                     AND label <> 'Site'""",
                (now, int(collection_id)),
            )

            # 23.9.1.2 — ancien état technique abandonné.
            state_definition_id = self._definition_id(
                connection, int(collection_id), "record_state"
            )
            connection.execute(
                """DELETE FROM referential_values
                   WHERE definition_id=? AND value='Libre (New fiche)'""",
                (state_definition_id,),
            )

            # G-Skol 1.0.169 — nomenclature système unique : OK / Vérifier / Libre.
            # Migrer les anciennes variantes dans les données et le référentiel.
            connection.execute(
                """UPDATE records SET record_state='Vérifier'
                   WHERE collection_id=? AND record_state IN ('À vérifier','A vérifier','Valider')""",
                (int(collection_id),),
            )
            connection.execute(
                """INSERT OR IGNORE INTO referential_values(
                       definition_id, value, sort_order, is_active, created_at, updated_at
                   ) VALUES (?, 'Vérifier', 2, 1, ?, ?)""",
                (state_definition_id, now, now),
            )
            connection.execute(
                """DELETE FROM referential_values
                   WHERE definition_id=? AND value IN ('À vérifier','A vérifier','Valider')""",
                (state_definition_id,),
            )
            connection.execute(
                """DELETE FROM referential_value_exclusions
                   WHERE collection_id=? AND code='record_state'
                     AND value IN ('À vérifier','A vérifier','Valider')""",
                (int(collection_id),),
            )

            # Terminologie générique commune à tous les futurs modèles.
            connection.execute(
                """UPDATE referential_definitions
                   SET label='Contenant', updated_at=?
                   WHERE collection_id=? AND code='box_type'
                     AND label <> 'Contenant'""",
                (now, int(collection_id)),
            )

            for code, values in self.DEFAULT_VALUES.items():
                definition_id = self._definition_id(
                    connection, int(collection_id), code
                )
                for order, value in enumerate(values, start=1):
                    connection.execute(
                        """INSERT OR IGNORE INTO referential_values(
                               definition_id, value, sort_order, is_active,
                               created_at, updated_at
                           ) VALUES (?, ?, ?, 1, ?, ?)""",
                        (definition_id, value, order, now, now),
                    )

            # « OK » et « Libre » sont des valeurs système G-Skol protégées.
            # Réactiver aussi « OK » dans les collections où il avait été retiré.
            for mandatory in ("OK", "Libre"):
                connection.execute(
                    """INSERT OR IGNORE INTO referential_values(
                           definition_id, value, sort_order, is_active, created_at, updated_at
                       ) VALUES (?, ?, ?, 1, ?, ?)""",
                    (self._definition_id(connection, int(collection_id), "record_state"),
                     mandatory, 1 if mandatory == "OK" else 3, now, now),
                )
                connection.execute(
                    """UPDATE referential_values SET is_active=1, updated_at=?
                       WHERE definition_id=? AND value=? COLLATE NOCASE
                         AND is_active <> 1""",
                    (now, self._definition_id(connection, int(collection_id), "record_state"), mandatory),
                )
                connection.execute(
                    """DELETE FROM referential_value_exclusions
                       WHERE collection_id=? AND code='record_state' AND value=? COLLATE NOCASE""",
                    (int(collection_id), mandatory),
                )

            # « Libre » est une valeur système MM3 : toujours présente, active et non exclue.
            state_definition_id = self._definition_id(connection, int(collection_id), "record_state")
            connection.execute(
                """UPDATE referential_values SET is_active=1, updated_at=?
                   WHERE definition_id=? AND value='Libre' COLLATE NOCASE
                     AND is_active <> 1""",
                (now, state_definition_id),
            )
            connection.execute(
                """DELETE FROM referential_value_exclusions
                   WHERE collection_id=? AND code='record_state' AND value='Libre' COLLATE NOCASE""",
                (int(collection_id),),
            )

            # Marquer la migration uniquement après toutes les étapes réussies.
            # La transaction SQLite rend ce marqueur atomique avec les données.
            connection.execute(
                """CREATE TABLE IF NOT EXISTS gskol_initialization_markers(
                       collection_id INTEGER NOT NULL,
                       version TEXT NOT NULL,
                       PRIMARY KEY(collection_id, version)
                   )"""
            )
            connection.execute(
                "INSERT OR IGNORE INTO gskol_initialization_markers "
                "(collection_id, version) VALUES (?, ?)",
                (cid, marker_version),
            )

        self._defaults_ready.add(cid)

    def _definition_id(self, connection: sqlite3.Connection, collection_id: int, code: str) -> int:
        row = connection.execute(
            """SELECT id FROM referential_definitions
               WHERE collection_id = ? AND code = ?""",
            (int(collection_id), code),
        ).fetchone()
        if row is None:
            raise ValueError(f"Référentiel inconnu : {code}")
        return int(row["id"])

    def list_definitions(self, collection_id: int) -> list[dict[str, Any]]:
        self.ensure_defaults(collection_id)
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT id, collection_id, code, label, is_master, created_at
                   FROM referential_definitions
                   WHERE collection_id = ?
                   ORDER BY label COLLATE NOCASE""",
                (int(collection_id),),
            ).fetchall()
        return [dict(row) for row in rows]

    def _invalidate_values_cache(self, collection_id: int, code: str | None = None) -> None:
        cid = int(collection_id)
        if code is None:
            self._values_cache = {
                key: value for key, value in self._values_cache.items()
                if key[0] != cid
            }
            return
        clean = str(code)
        self._values_cache = {
            key: value for key, value in self._values_cache.items()
            if not (key[0] == cid and key[1] == clean)
        }

    def excluded_values(self, collection_id: int, code: str) -> set[str]:
        """Valeurs retirées volontairement du réservoir de propositions.

        Elles peuvent rester présentes dans d'anciennes fiches sans être
        réinjectées automatiquement dans le référentiel.
        """
        cid = int(collection_id)
        clean_code = str(code)
        self.ensure_defaults(cid)
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT value FROM referential_value_exclusions
                   WHERE collection_id=? AND code=?""",
                (cid, clean_code),
            ).fetchall()
        return {str(row["value"]) for row in rows}

    def _clear_exclusions(
        self, connection: sqlite3.Connection, collection_id: int, code: str, values: list[str]
    ) -> None:
        if not values:
            return
        connection.executemany(
            """DELETE FROM referential_value_exclusions
               WHERE collection_id=? AND code=? AND value=? COLLATE NOCASE""",
            [(int(collection_id), str(code), str(value)) for value in values],
        )

    def list_values(self, collection_id: int, code: str, active_only: bool = True) -> list[str]:
        cid = int(collection_id)
        clean_code = str(code)
        cache_key = (cid, clean_code, bool(active_only))
        cached = self._values_cache.get(cache_key)
        if cached is not None:
            return list(cached)

        self.ensure_defaults(cid)
        with self._connect() as connection:
            definition_id = self._definition_id(connection, cid, clean_code)
            definition = connection.execute(
                "SELECT sort_mode FROM referential_definitions WHERE id = ?",
                (definition_id,),
            ).fetchone()
            sort_mode = str(definition["sort_mode"] if definition else "custom")
            where_active = "AND is_active = 1" if active_only else ""

            if sort_mode == "asc":
                order_clause = "value COLLATE NOCASE ASC"
            elif sort_mode == "desc":
                order_clause = "value COLLATE NOCASE DESC"
            else:
                order_clause = "sort_order ASC, value COLLATE NOCASE ASC"

            rows = connection.execute(
                f"""SELECT value FROM referential_values
                    WHERE definition_id = ? {where_active}
                    ORDER BY {order_clause}""",
                (definition_id,),
            ).fetchall()

        values = tuple(str(row["value"]) for row in rows)
        self._values_cache[cache_key] = values
        return list(values)

    def get_sort_mode(self, collection_id: int, code: str) -> str:
        self.ensure_defaults(collection_id)
        with self._connect() as connection:
            definition_id = self._definition_id(connection, collection_id, code)
            row = connection.execute(
                "SELECT sort_mode FROM referential_definitions WHERE id = ?",
                (definition_id,),
            ).fetchone()
        mode = str(row["sort_mode"] if row else "custom")
        return mode if mode in ("asc", "desc", "custom") else "custom"

    def set_sort_mode(self, collection_id: int, code: str, mode: str) -> None:
        self._invalidate_values_cache(collection_id, code if 'code' in locals() else None)
        clean = str(mode or "").strip().lower()
        if clean not in ("asc", "desc", "custom"):
            raise ValueError("Mode de tri de référentiel invalide.")
        self.ensure_defaults(collection_id)
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as connection:
            definition_id = self._definition_id(connection, collection_id, code)
            connection.execute(
                """UPDATE referential_definitions
                   SET sort_mode = ?, updated_at = ?
                   WHERE id = ?""",
                (clean, now, definition_id),
            )

    def set_custom_order(
        self, collection_id: int, code: str, ordered_values: list[str]
    ) -> None:
        """Mémorise exactement l'ordre courant comme ordre personnalisé."""
        self._invalidate_values_cache(collection_id, code if 'code' in locals() else None)
        self.ensure_defaults(collection_id)
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as connection:
            definition_id = self._definition_id(connection, collection_id, code)
            for order, value in enumerate(ordered_values, start=1):
                connection.execute(
                    """UPDATE referential_values
                       SET sort_order = ?, updated_at = ?
                       WHERE definition_id = ? AND value = ?""",
                    (order, now, definition_id, str(value)),
                )
            connection.execute(
                """UPDATE referential_definitions
                   SET sort_mode = 'custom', updated_at = ?
                   WHERE id = ?""",
                (now, definition_id),
            )

    def move_value(self, collection_id: int, code: str, value: str, delta: int) -> None:
        """Déplace une valeur d'un cran en mode personnalisé."""
        self._invalidate_values_cache(collection_id, code if 'code' in locals() else None)
        self.ensure_defaults(collection_id)
        with self._connect() as connection:
            definition_id = self._definition_id(connection, collection_id, code)
            rows = connection.execute(
                """SELECT id, value, sort_order FROM referential_values
                   WHERE definition_id = ? AND is_active = 1
                   ORDER BY sort_order ASC, value COLLATE NOCASE ASC""",
                (definition_id,),
            ).fetchall()
            ids = [int(row["id"]) for row in rows]
            values = [str(row["value"]) for row in rows]
            try:
                old_index = values.index(str(value))
            except ValueError:
                return
            new_index = old_index + int(delta)
            if new_index < 0 or new_index >= len(ids):
                return
            ids[old_index], ids[new_index] = ids[new_index], ids[old_index]
            now = datetime.now().isoformat(timespec="seconds")
            for order, row_id in enumerate(ids, start=1):
                connection.execute(
                    """UPDATE referential_values
                       SET sort_order = ?, updated_at = ?
                       WHERE id = ?""",
                    (order, now, row_id),
                )


    def add_values_bulk(
        self, collection_id: int, code: str, values: list[str]
    ) -> dict[str, int]:
        """Ajoute/réactive beaucoup de valeurs en une seule transaction SQLite."""
        cid = int(collection_id)
        clean_code = str(code)
        normalized_values: list[str] = []
        seen: set[str] = set()
        ignored = 0
        for raw in values or []:
            normalized = self.normalize(raw, clean_code)
            if not normalized:
                ignored += 1
                continue
            marker = normalized.casefold()
            if marker in seen:
                continue
            seen.add(marker)
            normalized_values.append(normalized)

        if not normalized_values:
            return {"added": 0, "existing": 0, "ignored": ignored}

        self.ensure_defaults(cid)
        now = datetime.now().isoformat(timespec="seconds")
        added = 0
        existing = 0

        with self._connect() as connection:
            definition_id = self._definition_id(connection, cid, clean_code)
            rows = connection.execute(
                """SELECT value, is_active FROM referential_values
                   WHERE definition_id=?""",
                (definition_id,),
            ).fetchall()
            # Comparer sur la forme normalisée, pas sur le texte SQLite brut.
            # D'anciennes bases peuvent contenir des doubles espaces (ex.
            # « Saint Pierre  (haute) ») alors que l'interface les normalise.
            known = {
                self.normalize(str(row["value"]), clean_code).casefold():
                    (str(row["value"]), int(row["is_active"]))
                for row in rows
            }
            next_order = int(
                connection.execute(
                    """SELECT COALESCE(MAX(sort_order), 0) + 1
                       FROM referential_values WHERE definition_id=?""",
                    (definition_id,),
                ).fetchone()[0]
            )

            inserts = []
            reactivate = []
            for value in normalized_values:
                marker = value.casefold()
                if marker in known:
                    existing += 1
                    actual, active = known[marker]
                    if not active:
                        reactivate.append((now, definition_id, actual))
                    continue
                inserts.append(
                    (definition_id, value, next_order, 1, now, now)
                )
                next_order += 1
                added += 1

            if inserts:
                connection.executemany(
                    """INSERT INTO referential_values(
                           definition_id, value, sort_order, is_active, created_at, updated_at
                       ) VALUES (?, ?, ?, ?, ?, ?)""",
                    inserts,
                )
            if reactivate:
                connection.executemany(
                    """UPDATE referential_values
                       SET is_active=1, updated_at=?
                       WHERE definition_id=? AND value=? COLLATE NOCASE""",
                    reactivate,
                )
            # Un ajout explicite (import simple ou import structuré) annule
            # naturellement un ancien retrait volontaire de la même valeur.
            self._clear_exclusions(connection, cid, clean_code, normalized_values)

        if hasattr(self, "_invalidate_values_cache"):
            self._invalidate_values_cache(cid, clean_code)
        return {"added": added, "existing": existing, "ignored": ignored}


    def contains(
        self, collection_id: int, code: str, value: str, active_only: bool = True
    ) -> bool:
        normalized = self.normalize(value, code)
        if not normalized:
            return False
        self.ensure_defaults(collection_id)
        with self._connect() as connection:
            definition_id = self._definition_id(connection, collection_id, code)
            where_active = "AND is_active = 1" if active_only else ""
            rows = connection.execute(
                f"""SELECT value FROM referential_values
                    WHERE definition_id = ? {where_active}""",
                (definition_id,),
            ).fetchall()
        marker = normalized.casefold()
        return any(self.normalize(str(row["value"]), code).casefold() == marker for row in rows)

    def add_value(self, collection_id: int, code: str, value: str) -> str:
        cid = int(collection_id)
        clean_code = str(code)
        self._invalidate_values_cache(cid, clean_code)
        normalized = self.normalize(value, clean_code)
        if not normalized:
            raise ValueError("La valeur du référentiel ne peut pas être vide.")
        now = datetime.now().isoformat(timespec="seconds")
        self.ensure_defaults(cid)
        with self._connect() as connection:
            definition_id = self._definition_id(connection, cid, clean_code)
            rows = connection.execute(
                "SELECT id, value, is_active FROM referential_values WHERE definition_id=?",
                (definition_id,),
            ).fetchall()
            marker = normalized.casefold()
            equivalent = next(
                (row for row in rows if self.normalize(str(row["value"]), clean_code).casefold() == marker),
                None,
            )
            if equivalent is not None:
                # Profiter de la réactivation pour harmoniser l'ancien texte brut
                # (doubles espaces, espaces parasites, etc.).
                connection.execute(
                    """UPDATE referential_values SET value=?, is_active=1, updated_at=? WHERE id=?""",
                    (normalized, now, int(equivalent["id"])),
                )
            else:
                next_order = connection.execute(
                    """SELECT COALESCE(MAX(sort_order), 0) + 1
                       FROM referential_values WHERE definition_id = ?""",
                    (definition_id,),
                ).fetchone()[0]
                connection.execute(
                    """INSERT INTO referential_values(
                           definition_id, value, sort_order, is_active, created_at, updated_at
                       ) VALUES (?, ?, ?, 1, ?, ?)""",
                    (definition_id, normalized, int(next_order), now, now),
                )
            self._clear_exclusions(connection, cid, clean_code, [normalized])
        return normalized

    def rename_value(
        self, collection_id: int, code: str, old_value: str, new_value: str
    ) -> str:
        """Renomme une proposition du référentiel sans toucher aux fiches existantes."""
        self._invalidate_values_cache(collection_id, code)
        old_normalized = self.normalize(old_value, code)
        new_normalized = self.normalize(new_value, code)
        if str(code) == "record_state" and old_normalized.casefold() in {"ok", "libre"}:
            raise ValueError("« OK » et « Libre » sont des valeurs système G-Skol non modifiables.")
        if not new_normalized:
            raise ValueError("La nouvelle valeur ne peut pas être vide.")
        self.ensure_defaults(collection_id)

        with self._connect() as connection:
            definition_id = self._definition_id(connection, collection_id, code)
            old_row = connection.execute(
                """SELECT id FROM referential_values
                   WHERE definition_id = ? AND value = ? COLLATE NOCASE""",
                (definition_id, old_normalized),
            ).fetchone()
            if old_row is None:
                raise ValueError("La valeur à modifier n'existe plus.")

            existing = connection.execute(
                """SELECT id FROM referential_values
                   WHERE definition_id = ? AND value = ? COLLATE NOCASE""",
                (definition_id, new_normalized),
            ).fetchone()
            if existing is not None and int(existing["id"]) != int(old_row["id"]):
                raise ValueError("Cette valeur existe déjà.")

            connection.execute(
                """UPDATE referential_values
                   SET value = ?, is_active = 1, updated_at = ?
                   WHERE id = ?""",
                (
                    new_normalized,
                    datetime.now().isoformat(timespec="seconds"),
                    int(old_row["id"]),
                ),
            )
        return new_normalized

    def deactivate_value(self, collection_id: int, code: str, value: str) -> None:
        self.deactivate_values(collection_id, code, [value])

    def deactivate_values(
        self, collection_id: int, code: str, values: list[str] | tuple[str, ...]
    ) -> None:
        """Retire durablement des valeurs du réservoir de propositions.

        Les fiches existantes ne sont pas modifiées. Le retrait compare les
        formes normalisées afin de supprimer aussi les anciennes variantes
        contenant des doubles espaces. Un marqueur d'exclusion empêche ensuite
        une vieille fiche de réinjecter automatiquement la valeur.
        """
        cid = int(collection_id)
        clean_code = str(code)
        normalized_values = [self.normalize(value, clean_code) for value in values]
        normalized_values = [value for value in normalized_values if value]
        if clean_code == "record_state":
            normalized_values = [value for value in normalized_values if value.casefold() not in {"ok", "libre"}]
        if not normalized_values:
            return
        target_markers = {value.casefold() for value in normalized_values}
        self._invalidate_values_cache(cid, clean_code)
        self.ensure_defaults(cid)
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as connection:
            definition_id = self._definition_id(connection, cid, clean_code)
            rows = connection.execute(
                "SELECT id, value FROM referential_values WHERE definition_id=?",
                (definition_id,),
            ).fetchall()
            ids = [
                int(row["id"]) for row in rows
                if self.normalize(str(row["value"]), clean_code).casefold() in target_markers
            ]
            if ids:
                connection.executemany(
                    "DELETE FROM referential_values WHERE id=?",
                    [(row_id,) for row_id in ids],
                )
            connection.executemany(
                """INSERT INTO referential_value_exclusions(collection_id, code, value, updated_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(collection_id, code, value) DO UPDATE SET updated_at=excluded.updated_at""",
                [(cid, clean_code, value, now) for value in normalized_values],
            )

    def import_existing_record_values(self, collection_id: int, code: str = "mineral_name") -> int:
        """Alimente un référentiel à partir des fiches déjà saisies."""
        self._invalidate_values_cache(collection_id, code if 'code' in locals() else None)
        self.ensure_defaults(collection_id)
        field_by_code = {
            "mineral_name": "mineral_name",
            "mineral_class": "mineral_class",
            "crystal_system": "crystal_system",
            "luminescence": "luminescence",
            "luminescence_intensity": "luminescence_intensity",
            "fluorescence_color": "fluorescence_color",
            "site_name": "site_name",
            "department": "department",
            "region": "region",
            "country": "country",
            "box_type": "box_type",
            "category": "category",
            "contact": "contact",
            "specimen_shape": "specimen_shape",
            "specimen_color": "specimen_color",
            "quality": "quality",
            "minimum_magnification": "minimum_magnification",
            "growth": "growth",
            "origin": "origin",
            "place": "place",
            "record_state": "record_state",
        }
        field = field_by_code.get(code)
        if field is None:
            return 0
        with self._connect() as connection:
            try:
                rows = connection.execute(
                    f"""SELECT DISTINCT {field} AS value
                       FROM records
                       WHERE collection_id = ? AND TRIM({field}) <> ''
                       ORDER BY {field} COLLATE NOCASE""",
                    (int(collection_id),),
                ).fetchall()
            except sqlite3.OperationalError:
                return 0
        added = 0
        for row in rows:
            value = self.normalize(str(row["value"]), code)
            if value and not self.contains(collection_id, code, value):
                self.add_value(collection_id, code, value)
                added += 1
        return added

    @staticmethod
    def normalize(value: str, code: str | None = None) -> str:
        compact = " ".join(str(value).strip().split())
        if code in (None, "mineral_name"):
            return compact.upper()
        return compact
