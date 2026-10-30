#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import sqlite3
import json
import uuid
import re
from datetime import datetime
from pathlib import Path

from core.layout_geometry import DEFAULT_FIELD_GEOMETRY
from core.field_catalog import FIELD_BY_KEY, FIELDS


MODEL_BLOCKS = ("Identification", "Localisation", "Aspect", "Acquisition", "Collection")

# Placement historique du modèle Micro-minéraux. Le Bandeau et la Photo restent
# structurels dans cette brique ; tous les autres champs peuvent changer de bloc.
DEFAULT_BLOCK_FIELDS = {
    "Identification": (
        "mineral_class", "chemical_formula", "crystal_system", "luminescence",
        "luminescence_intensity", "fluorescence_color", "internet_link",
    ),
    "Localisation": (
        "site_name", "deposit", "category", "site_internet_link",
        "department", "region", "country",
    ),
    "Aspect": (
        "growth", "specimen_shape", "specimen_color", "quality", "type_locality",
        "minimum_magnification", "description",
    ),
    "Acquisition": ("acquisition_date", "origin", "contact", "place"),
    "Collection": ("box_type", "box_count", "price", "total_cost"),
}
DEFAULT_PLACEMENT = {
    key: (block, pos)
    for block, keys in DEFAULT_BLOCK_FIELDS.items()
    for pos, key in enumerate(keys)
}
MOVABLE_FIELDS = frozenset(DEFAULT_PLACEMENT)


class ModelManager:
    """Première brique des modèles de fiche MM3.

    Un modèle indique, collection par collection, quels champs du catalogue MM3
    sont utilisés. Les colonnes SQLite restent communes : masquer un champ ne
    détruit donc jamais une ancienne valeur et le champ peut être réactivé plus tard.
    """

    # Le numéro est structurel et n'est pas paramétrable dans cette première brique.
    NON_CONFIGURABLE = frozenset({"record_number"})

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self._model_fields_schema_ready = False
        self._custom_fields_schema_ready = False
        self._appearance_schema_ready = False
        self._custom_fields_read_cache: dict[int, tuple[dict, ...]] = {}

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def delete_primary_photo_data(self, collection_id: int) -> None:
        """Supprime les images du cadre Photo principal pour cette collection."""
        with self._connect() as connection:
            tables = {
                str(row[0])
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            if "records" not in tables:
                return
            connection.execute(
                """UPDATE records
                   SET photo_data = NULL, photo_format = ''
                   WHERE collection_id = ?""",
                (int(collection_id),),
            )

    def delete_extra_photo_slot_data(self, collection_id: int, slot_key: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS record_extra_photos(
                    record_id INTEGER NOT NULL,
                    slot_key TEXT NOT NULL,
                    photo_data BLOB,
                    photo_format TEXT NOT NULL DEFAULT '',
                    PRIMARY KEY(record_id, slot_key)
                )"""
            )
            connection.execute(
                """DELETE FROM record_extra_photos
                   WHERE slot_key = ?
                   AND record_id IN (SELECT id FROM records WHERE collection_id = ?)""",
                (str(slot_key), int(collection_id)),
            )

    def _ensure_table(self, connection: sqlite3.Connection) -> None:
        if self._model_fields_schema_ready:
            return
        connection.execute(
            """CREATE TABLE IF NOT EXISTS collection_model_fields(
                collection_id INTEGER NOT NULL,
                field_key TEXT NOT NULL,
                visible INTEGER NOT NULL DEFAULT 1,
                custom_label TEXT,
                block_name TEXT,
                position INTEGER,
                tab_position INTEGER,
                visual_x INTEGER,
                visual_y INTEGER,
                visual_w INTEGER,
                visual_h INTEGER,
                PRIMARY KEY(collection_id, field_key),
                FOREIGN KEY(collection_id) REFERENCES collections(id)
            )"""
        )
        columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(collection_model_fields)").fetchall()}
        if "custom_label" not in columns:
            connection.execute("ALTER TABLE collection_model_fields ADD COLUMN custom_label TEXT")
        if "block_name" not in columns:
            connection.execute("ALTER TABLE collection_model_fields ADD COLUMN block_name TEXT")
        if "position" not in columns:
            connection.execute("ALTER TABLE collection_model_fields ADD COLUMN position INTEGER")
        if "tab_position" not in columns:
            connection.execute("ALTER TABLE collection_model_fields ADD COLUMN tab_position INTEGER")
        if "visual_x" not in columns:
            connection.execute("ALTER TABLE collection_model_fields ADD COLUMN visual_x INTEGER")
        if "visual_y" not in columns:
            connection.execute("ALTER TABLE collection_model_fields ADD COLUMN visual_y INTEGER")
        if "visual_w" not in columns:
            connection.execute("ALTER TABLE collection_model_fields ADD COLUMN visual_w INTEGER")
        if "visual_h" not in columns:
            connection.execute("ALTER TABLE collection_model_fields ADD COLUMN visual_h INTEGER")

        self._model_fields_schema_ready = True

    def _ensure_custom_fields_table(self, connection: sqlite3.Connection) -> None:
        if self._custom_fields_schema_ready:
            return
        connection.execute(
            """CREATE TABLE IF NOT EXISTS collection_custom_fields(
                collection_id INTEGER NOT NULL,
                field_key TEXT NOT NULL,
                label TEXT NOT NULL,
                field_type TEXT NOT NULL DEFAULT 'text',
                referential_code TEXT,
                initial_group TEXT NOT NULL DEFAULT 'Identification',
                date_format TEXT NOT NULL DEFAULT 'JJ/MM/AAAA',
                created_at TEXT NOT NULL,
                PRIMARY KEY(collection_id, field_key),
                FOREIGN KEY(collection_id) REFERENCES collections(id)
            )"""
        )
        columns = {
            str(row["name"])
            for row in connection.execute(
                "PRAGMA table_info(collection_custom_fields)"
            ).fetchall()
        }
        if "initial_group" not in columns:
            connection.execute(
                "ALTER TABLE collection_custom_fields "
                "ADD COLUMN initial_group TEXT NOT NULL DEFAULT 'Identification'"
            )
        if "date_format" not in columns:
            connection.execute(
                "ALTER TABLE collection_custom_fields "
                "ADD COLUMN date_format TEXT NOT NULL DEFAULT 'JJ/MM/AAAA'"
            )
        if "calculation_formula" not in columns:
            connection.execute("ALTER TABLE collection_custom_fields ADD COLUMN calculation_formula TEXT NOT NULL DEFAULT ''")
        if "calculation_format" not in columns:
            connection.execute("ALTER TABLE collection_custom_fields ADD COLUMN calculation_format TEXT NOT NULL DEFAULT 'truncate2'")
        self._custom_fields_schema_ready = True

    def _invalidate_custom_fields_cache(self, collection_id: int) -> None:
        self._custom_fields_read_cache.pop(int(collection_id), None)

    def custom_fields(self, collection_id: int) -> list[dict]:
        cid = int(collection_id)
        cached = self._custom_fields_read_cache.get(cid)
        if cached is not None:
            return [dict(row) for row in cached]
        with self._connect() as connection:
            self._ensure_custom_fields_table(connection)
            rows = connection.execute(
                "SELECT field_key, label, field_type, referential_code, "
                "initial_group, date_format, calculation_formula, calculation_format, created_at FROM collection_custom_fields "
                "WHERE collection_id=? ORDER BY created_at, field_key",
                (cid,),
            ).fetchall()
        values = tuple(dict(row) for row in rows)
        self._custom_fields_read_cache[cid] = values
        return [dict(row) for row in values]

    def custom_field_map(self, collection_id: int) -> dict[str, dict]:
        return {
            str(row["field_key"]): dict(row)
            for row in self.custom_fields(collection_id)
        }

    def all_model_keys(self, collection_id: int) -> tuple[str, ...]:
        # record_number reste structurel (obligatoire/non supprimable), mais il
        # fait partie du modèle géométrique : sa position et sa taille doivent
        # être enregistrées exactement comme celles des autres champs.
        keys = ["record_number"]
        keys.extend(self.configurable_fields())
        keys.extend(str(row["field_key"]) for row in self.custom_fields(collection_id))
        return tuple(dict.fromkeys(keys))

    @staticmethod
    def _ensure_record_custom_values_table(connection: sqlite3.Connection) -> None:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS record_custom_values(
                record_id INTEGER NOT NULL,
                field_key TEXT NOT NULL,
                value TEXT NOT NULL DEFAULT '',
                PRIMARY KEY(record_id, field_key),
                FOREIGN KEY(record_id) REFERENCES records(id) ON DELETE CASCADE
            )"""
        )

    def custom_field_has_data(self, collection_id: int, field_key: str) -> bool:
        with self._connect() as connection:
            self._ensure_record_custom_values_table(connection)
            row = connection.execute(
                """SELECT 1
                   FROM record_custom_values cv
                   JOIN records r ON r.id=cv.record_id
                   WHERE r.collection_id=? AND cv.field_key=?
                     AND trim(COALESCE(cv.value,''))<>''
                   LIMIT 1""",
                (int(collection_id), str(field_key)),
            ).fetchone()
        return row is not None


    def analyze_standard_field_type_change(
        self,
        collection_id: int,
        field_key: str,
        new_type: str,
        date_format: str = "JJ/MM/AAAA",
    ) -> dict:
        """Analyse la conversion d'un ancien champ MM3 sans modifier les données."""
        key = str(field_key or "").strip()
        if not key or key in {"record_number", "photo_data"}:
            return {
                "compatible": False,
                "total": 0,
                "converted": 0,
                "invalid": [],
                "reason": "Ce champ est structurel et ne peut pas changer de type.",
            }

        with self._connect() as connection:
            columns = {
                str(row[1])
                for row in connection.execute("PRAGMA table_info(records)").fetchall()
            }
            if key not in columns:
                return {
                    "compatible": True, "total": 0, "converted": 0,
                    "invalid": [], "conversions": [],
                }

            sql = (
                f'SELECT id, CAST("{key}" AS TEXT) AS value '
                f'FROM records WHERE collection_id=? '
                f'AND trim(COALESCE(CAST("{key}" AS TEXT), \'\')) <> \'\' '
                f'ORDER BY record_number, id'
            )
            rows = connection.execute(sql, (int(collection_id),)).fetchall()

        invalid = []
        conversions = []
        for data_row in rows:
            original = str(data_row["value"] or "")
            ok, converted = self._convert_value_for_field_type(
                original, str(new_type or "text"), date_format
            )
            if not ok:
                if len(invalid) < 12:
                    invalid.append(original)
            else:
                conversions.append((int(data_row["id"]), converted))

        return {
            "compatible": len(invalid) == 0 and len(conversions) == len(rows),
            "total": len(rows),
            "converted": len(conversions),
            "invalid": invalid,
            "conversions": conversions,
        }

    def migrate_standard_field_to_custom(
        self,
        collection_id: int,
        old_field_key: str,
        new_field_key: str,
        new_type: str,
        date_format: str = "JJ/MM/AAAA",
    ) -> int:
        """Copie sans perte les valeurs d'un champ historique vers son remplaçant.

        L'ancienne colonne n'est jamais détruite : elle pourra rester masquée dans
        cette collection. La migration est donc réversible au niveau des données.
        """
        analysis = self.analyze_standard_field_type_change(
            collection_id, old_field_key, new_type, date_format
        )
        if not bool(analysis.get("compatible")):
            invalid = list(analysis.get("invalid") or [])
            examples = "\n".join("• " + str(v) for v in invalid[:12])
            raise ValueError(
                "Conversion impossible sans perte de données."
                + (("\n\nValeurs incompatibles :\n" + examples) if examples else "")
            )

        conversions = list(analysis.get("conversions") or [])
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as connection:
            self._ensure_record_custom_values_table(connection)
            for record_id, converted in conversions:
                connection.execute(
                    """INSERT INTO record_custom_values(record_id, field_key, value)
                       VALUES (?, ?, ?)
                       ON CONFLICT(record_id, field_key) DO UPDATE SET value=excluded.value""",
                    (int(record_id), str(new_field_key), str(converted)),
                )

            if str(new_type) == "list":
                self._ensure_custom_fields_table(connection)
                row = connection.execute(
                    "SELECT referential_code FROM collection_custom_fields "
                    "WHERE collection_id=? AND field_key=?",
                    (int(collection_id), str(new_field_key)),
                ).fetchone()
                code = str(row["referential_code"] or "") if row is not None else ""
                if code:
                    definition = connection.execute(
                        "SELECT id FROM referential_definitions WHERE collection_id=? AND code=?",
                        (int(collection_id), code),
                    ).fetchone()
                    if definition is not None:
                        definition_id = int(definition["id"])
                        values = connection.execute(
                            """SELECT DISTINCT trim(cv.value) AS value
                               FROM record_custom_values cv
                               JOIN records r ON r.id=cv.record_id
                               WHERE r.collection_id=? AND cv.field_key=?
                                 AND trim(COALESCE(cv.value,''))<>''
                               ORDER BY lower(trim(cv.value)), trim(cv.value)""",
                            (int(collection_id), str(new_field_key)),
                        ).fetchall()
                        for order, value_row in enumerate(values, start=1):
                            value = str(value_row["value"] or "").strip()
                            if value:
                                connection.execute(
                                    """INSERT OR IGNORE INTO referential_values(
                                           definition_id, value, sort_order, is_active,
                                           created_at, updated_at
                                       ) VALUES (?, ?, ?, 1, ?, ?)""",
                                    (definition_id, value, order, now, now),
                                )

        return len(conversions)

    def standard_field_has_data(self, collection_id: int, field_key: str) -> bool:
        """Indique si un champ historique contient une valeur dans la collection.

        Cette vérification est volontairement générique : elle permet à l'Atelier
        de convertir un ancien champ MM3 en champ entièrement personnalisable
        uniquement lorsqu'aucune donnée existante ne risque d'être perdue.
        """
        key = str(field_key or "").strip()
        if not key or key in {"record_number", "photo_data"}:
            return True
        with self._connect() as connection:
            columns = {
                str(row[1])
                for row in connection.execute("PRAGMA table_info(records)").fetchall()
            }
            if key not in columns:
                return False
            # quote identifiant après validation stricte par PRAGMA
            # 11.4.28 — seules les vraies valeurs stockées dans records
            # verrouillent le type. Les données d'exemple de l'Atelier ne sont
            # jamais prises en compte. L'ancienne chaîne SQL était mal quotée
            # et provoquait une erreur SQLite, ensuite interprétée comme
            # has_data=True par sécurité.
            sql = (
                f'SELECT 1 FROM records WHERE collection_id=? '
                f'AND trim(COALESCE(CAST("{key}" AS TEXT), \'\')) <> \'\' LIMIT 1'
            )
            row = connection.execute(sql, (int(collection_id),)).fetchone()
        return row is not None

    def create_custom_field(
        self, collection_id: int, label: str, field_type: str,
        initial_group: str = "Identification", date_format: str = "JJ/MM/AAAA",
        calculation_formula: str = "", calculation_format: str = "truncate2",
    ) -> dict:
        self._invalidate_custom_fields_cache(collection_id)
        label = str(label or "").strip()
        if not label:
            raise ValueError("Le nom du champ est obligatoire.")
        field_type = str(field_type or "text")
        if field_type not in {"text", "numeric", "date", "boolean", "list", "link", "currency", "calculated"}:
            raise ValueError("Type de champ inconnu.")
        date_format = str(date_format or "JJ/MM/AAAA")
        if date_format not in {"JJ/MM/AAAA", "JJ/MM/AA", "MM/AAAA", "AAAA", "AAAA-MM-JJ"}:
            date_format = "JJ/MM/AAAA"
        group = str(initial_group or "Identification")
        if group not in MODEL_BLOCKS:
            group = "Identification"

        key = "custom_" + uuid.uuid4().hex[:12]
        referential_code = key if field_type == "list" else None
        now = datetime.now().isoformat(timespec="seconds")

        with self._connect() as connection:
            self._ensure_table(connection)
            self._ensure_custom_fields_table(connection)

            duplicate = connection.execute(
                "SELECT 1 FROM collection_custom_fields "
                "WHERE collection_id=? AND lower(trim(label))=lower(trim(?))",
                (int(collection_id), label),
            ).fetchone()
            if duplicate:
                raise ValueError(f"Un champ nommé « {label} » existe déjà.")

            connection.execute(
                "INSERT INTO collection_custom_fields("
                "collection_id, field_key, label, field_type, referential_code, "
                "initial_group, date_format, calculation_formula, calculation_format, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (int(collection_id), key, label, field_type, referential_code, group, date_format, str(calculation_formula or ""), str(calculation_format or "truncate2"), now),
            )

            max_pos = connection.execute(
                "SELECT COALESCE(MAX(position), -1) FROM collection_model_fields "
                "WHERE collection_id=? AND block_name=?",
                (int(collection_id), group),
            ).fetchone()[0]
            pos = int(max_pos) + 1
            connection.execute(
                "INSERT OR REPLACE INTO collection_model_fields("
                "collection_id, field_key, visible, custom_label, block_name, position, "
                "visual_x, visual_y, visual_w, visual_h) "
                "VALUES (?, ?, 1, ?, ?, ?, 12, ?, 260, 31)",
                (int(collection_id), key, label, group, pos, 12 + pos * 38),
            )

            if referential_code:
                connection.execute(
                    """CREATE TABLE IF NOT EXISTS referential_definitions(
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        collection_id INTEGER NOT NULL,
                        code TEXT NOT NULL,
                        label TEXT NOT NULL,
                        is_master INTEGER NOT NULL DEFAULT 0,
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
                connection.execute(
                    "INSERT OR IGNORE INTO referential_definitions("
                    "collection_id, code, label, is_master, created_at) "
                    "VALUES (?, ?, ?, 0, ?)",
                    (int(collection_id), referential_code, label, now),
                )

        return {
            "field_key": key,
            "label": label,
            "field_type": field_type,
            "referential_code": referential_code,
            "initial_group": group,
            "date_format": date_format,
            "calculation_formula": str(calculation_formula or ""),
            "calculation_format": str(calculation_format or "truncate2"),
            "created_at": now,
        }

    @staticmethod
    def _format_converted_date(value: datetime, date_format: str) -> str:
        fmt = str(date_format or "JJ/MM/AAAA")
        if fmt == "JJ/MM/AA":
            return value.strftime("%d/%m/%y")
        if fmt == "MM/AAAA":
            return value.strftime("%m/%Y")
        if fmt == "AAAA":
            return value.strftime("%Y")
        if fmt == "AAAA-MM-JJ":
            return value.strftime("%Y-%m-%d")
        return value.strftime("%d/%m/%Y")

    @classmethod
    def _convert_value_for_field_type(
        cls, value: str, new_type: str, date_format: str = "JJ/MM/AAAA"
    ) -> tuple[bool, str]:
        """Teste et convertit une valeur sans perte sémantique évidente."""
        original = str(value or "")
        raw = original.strip()
        if not raw:
            return True, ""

        target = str(new_type or "text")
        if target in {"text", "list", "link"}:
            return True, original

        if target == "numeric":
            compact = raw.replace("\u00a0", "").replace("\u202f", "").replace(" ", "")
            # Un nombre n'accepte volontairement aucune devise ni unité.
            if not re.fullmatch(r"[+-]?(?:\d+(?:[.,]\d+)?|[.,]\d+)", compact):
                return False, original
            try:
                number = float(compact.replace(",", "."))
            except ValueError:
                return False, original
            converted = str(int(number)) if number.is_integer() else format(number, ".15g")
            return True, converted

        if target == "currency":
            compact = raw.replace("\u00a0", " ").replace("\u202f", " ").strip()
            # Accepter les devises usuelles déjà présentes dans les données.
            compact = re.sub(r"(?i)\b(?:CHF|CAD|AUD|EUR|USD|GBP|JPY)\b", "", compact)
            compact = compact.replace("€", "").replace("$", "").replace("£", "").replace("¥", "")
            compact = compact.replace(" ", "")
            if not re.fullmatch(r"[+-]?(?:\d+(?:[.,]\d+)?|[.,]\d+)", compact):
                return False, original
            try:
                number = float(compact.replace(",", "."))
            except ValueError:
                return False, original
            return True, f"{number:.2f}".replace(".", ",")

        if target == "boolean":
            token = raw.casefold()
            yes = {"oui", "yes", "true", "vrai", "1", "on"}
            no = {"non", "no", "false", "faux", "0", "off"}
            if token in yes:
                return True, "Oui"
            if token in no:
                return True, "Non"
            return False, original

        if target == "date":
            candidates = (
                "%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d",
                "%d-%m-%Y", "%d-%m-%y", "%Y/%m/%d",
            )
            for pattern in candidates:
                try:
                    dt = datetime.strptime(raw, pattern)
                    return True, cls._format_converted_date(dt, date_format)
                except ValueError:
                    pass
            # MM/AAAA et AAAA sont aussi des formats MM3 valides.
            if re.fullmatch(r"\d{1,2}/\d{4}", raw):
                try:
                    dt = datetime.strptime(raw, "%m/%Y")
                    return True, cls._format_converted_date(dt, date_format)
                except ValueError:
                    pass
            if re.fullmatch(r"\d{4}", raw):
                try:
                    dt = datetime.strptime(raw, "%Y")
                    return True, cls._format_converted_date(dt, date_format)
                except ValueError:
                    pass
            return False, original

        if target == "calculated":
            # Un champ calculé ne doit pas écraser des valeurs existantes.
            return False, original

        return False, original

    def analyze_custom_field_type_change(
        self,
        collection_id: int,
        field_key: str,
        new_type: str,
        date_format: str = "JJ/MM/AAAA",
    ) -> dict:
        """Analyse une conversion de type sans modifier la collection."""
        with self._connect() as connection:
            self._ensure_custom_fields_table(connection)
            self._ensure_record_custom_values_table(connection)
            row = connection.execute(
                "SELECT field_type, label FROM collection_custom_fields "
                "WHERE collection_id=? AND field_key=?",
                (int(collection_id), str(field_key)),
            ).fetchone()
            if row is None:
                raise ValueError("Champ personnalisé introuvable.")

            old_type = str(row["field_type"] or "text")
            target = str(new_type or old_type)
            if target == old_type:
                return {
                    "compatible": True, "total": 0, "converted": 0,
                    "invalid": [], "old_type": old_type, "new_type": target,
                }

            if old_type == "calculated":
                return {
                    "compatible": False, "total": 0, "converted": 0,
                    "invalid": [],
                    "reason": (
                        "Dans cette première version, un champ Calculé conserve son type "
                        "afin de ne pas perdre sa formule ni son résultat dynamique."
                    ),
                    "old_type": old_type, "new_type": target,
                }

            rows = connection.execute(
                """SELECT cv.record_id, cv.value
                   FROM record_custom_values cv
                   JOIN records r ON r.id=cv.record_id
                   WHERE r.collection_id=? AND cv.field_key=?
                     AND trim(COALESCE(cv.value,''))<>'' ORDER BY r.record_number, r.id""",
                (int(collection_id), str(field_key)),
            ).fetchall()

        invalid = []
        conversions = []
        for data_row in rows:
            ok, converted = self._convert_value_for_field_type(
                str(data_row["value"] or ""), target, date_format
            )
            if not ok:
                if len(invalid) < 12:
                    invalid.append(str(data_row["value"] or ""))
            else:
                conversions.append((int(data_row["record_id"]), converted))

        return {
            "compatible": len(invalid) == 0 and len(conversions) == len(rows),
            "total": len(rows),
            "converted": len(conversions),
            "invalid": invalid,
            "old_type": old_type,
            "new_type": target,
            "conversions": conversions,
        }

    def update_custom_field(
        self, collection_id: int, field_key: str, *,
        label: str | None = None,
        date_format: str | None = None,
        field_type: str | None = None,
        calculation_formula: str | None = None,
        calculation_format: str | None = None,
    ) -> dict:
        self._invalidate_custom_fields_cache(collection_id)
        with self._connect() as connection:
            self._ensure_custom_fields_table(connection)
            self._ensure_record_custom_values_table(connection)
            row = connection.execute(
                "SELECT * FROM collection_custom_fields WHERE collection_id=? AND field_key=?",
                (int(collection_id), str(field_key)),
            ).fetchone()
            if row is None:
                raise ValueError("Champ personnalisé introuvable.")

            new_label = str(label if label is not None else row["label"]).strip()
            if not new_label:
                raise ValueError("Le nom du champ est obligatoire.")

            old_type = str(row["field_type"] or "text")
            new_type = str(field_type if field_type is not None else old_type)
            allowed = {"text", "numeric", "date", "boolean", "list", "link", "currency", "calculated"}
            if new_type not in allowed:
                raise ValueError("Type de champ inconnu.")

            conversion_plan = None
            if new_type != old_type:
                # Le verrouillage historique est remplacé par une conversion
                # contrôlée : toutes les valeurs doivent être compatibles.
                # L'analyse est faite dans cette même connexion pour éviter toute
                # modification partielle en cas d'échec.
                if old_type == "calculated":
                    raise ValueError(
                        "Dans cette première version, un champ Calculé conserve son type "
                        "afin de ne pas perdre sa formule ni son résultat dynamique."
                    )
                value_rows = connection.execute(
                    """SELECT cv.record_id, cv.value
                       FROM record_custom_values cv
                       JOIN records r ON r.id=cv.record_id
                       WHERE r.collection_id=? AND cv.field_key=?
                         AND trim(COALESCE(cv.value,''))<>'' ORDER BY r.record_number, r.id""",
                    (int(collection_id), str(field_key)),
                ).fetchall()
                conversion_plan = []
                invalid_values = []
                requested_date_format = str(
                    date_format if date_format is not None
                    else row["date_format"] or "JJ/MM/AAAA"
                )
                for value_row in value_rows:
                    ok, converted = self._convert_value_for_field_type(
                        str(value_row["value"] or ""), new_type, requested_date_format
                    )
                    if not ok:
                        if len(invalid_values) < 12:
                            invalid_values.append(str(value_row["value"] or ""))
                    else:
                        conversion_plan.append((converted, int(value_row["record_id"])))
                if invalid_values:
                    examples = "\n".join("• " + value for value in invalid_values)
                    raise ValueError(
                        "Conversion impossible sans perte de données.\n\n"
                        f"{len(invalid_values)} valeur(s) incompatible(s) ont été détectées "
                        "(12 exemples au maximum sont affichés) :\n" + examples
                    )

            new_format = str(
                date_format if date_format is not None
                else row["date_format"] or "JJ/MM/AAAA"
            )
            if new_format not in {
                "JJ/MM/AAAA", "JJ/MM/AA", "MM/AAAA", "AAAA", "AAAA-MM-JJ"
            }:
                new_format = "JJ/MM/AAAA"

            referential_code = row["referential_code"]
            now = datetime.now().isoformat(timespec="seconds")

            if old_type != "list" and new_type == "list":
                referential_code = str(field_key)
                connection.execute(
                    """CREATE TABLE IF NOT EXISTS referential_definitions(
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        collection_id INTEGER NOT NULL,
                        code TEXT NOT NULL,
                        label TEXT NOT NULL,
                        is_master INTEGER NOT NULL DEFAULT 0,
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
                connection.execute(
                    """INSERT OR IGNORE INTO referential_definitions(
                        collection_id, code, label, is_master, created_at
                    ) VALUES (?, ?, ?, 0, ?)""",
                    (int(collection_id), referential_code, new_label, now),
                )
            elif old_type == "list" and new_type != "list":
                if referential_code:
                    # Certaines anciennes collections possèdent encore le schéma
                    # referential_values avec une FK sans ON DELETE CASCADE.
                    # Il faut donc supprimer explicitement les valeurs avant la
                    # définition, sinon SQLite lève FOREIGN KEY constraint failed.
                    def_row = connection.execute(
                        "SELECT id FROM referential_definitions WHERE collection_id=? AND code=?",
                        (int(collection_id), str(referential_code)),
                    ).fetchone()
                    if def_row is not None:
                        connection.execute(
                            "DELETE FROM referential_values WHERE definition_id=?",
                            (int(def_row["id"]),),
                        )
                    connection.execute(
                        "DELETE FROM referential_definitions WHERE collection_id=? AND code=?",
                        (int(collection_id), str(referential_code)),
                    )
                referential_code = None

            new_calculation_formula = str(
                calculation_formula
                if calculation_formula is not None
                else row["calculation_formula"] or ""
            )
            new_calculation_format = str(
                calculation_format
                if calculation_format is not None
                else row["calculation_format"] or "truncate2"
            )
            if new_calculation_format not in {"round", "truncate0", "truncate2"}:
                new_calculation_format = "truncate2"
            if new_type != "calculated":
                new_calculation_formula = ""

            if conversion_plan is not None:
                for converted_value, record_id in conversion_plan:
                    connection.execute(
                        """UPDATE record_custom_values
                           SET value=? WHERE record_id=? AND field_key=?""",
                        (str(converted_value), int(record_id), str(field_key)),
                    )

            connection.execute(
                """UPDATE collection_custom_fields
                   SET label=?, field_type=?, referential_code=?, date_format=?,
                       calculation_formula=?, calculation_format=?
                   WHERE collection_id=? AND field_key=?""",
                (
                    new_label, new_type, referential_code, new_format,
                    new_calculation_formula, new_calculation_format,
                    int(collection_id), str(field_key),
                ),
            )
            connection.execute(
                """UPDATE collection_model_fields SET custom_label=?
                   WHERE collection_id=? AND field_key=?""",
                (new_label, int(collection_id), str(field_key)),
            )
            if new_type == "list" and referential_code:
                connection.execute(
                    """UPDATE referential_definitions SET label=?
                       WHERE collection_id=? AND code=?""",
                    (new_label, int(collection_id), str(referential_code)),
                )
                # Lorsqu'un champ existant devient une Liste, son référentiel est
                # automatiquement constitué à partir des valeurs distinctes déjà
                # présentes dans les fiches.
                def_row = connection.execute(
                    "SELECT id FROM referential_definitions WHERE collection_id=? AND code=?",
                    (int(collection_id), str(referential_code)),
                ).fetchone()
                if def_row is not None:
                    values = connection.execute(
                        """SELECT DISTINCT trim(cv.value) AS value
                           FROM record_custom_values cv
                           JOIN records r ON r.id=cv.record_id
                           WHERE r.collection_id=? AND cv.field_key=?
                             AND trim(COALESCE(cv.value,''))<>''
                           ORDER BY lower(trim(cv.value)), trim(cv.value)""",
                        (int(collection_id), str(field_key)),
                    ).fetchall()
                    for order, value_row in enumerate(values, start=1):
                        value = str(value_row["value"] or "").strip()
                        if value:
                            connection.execute(
                                """INSERT OR IGNORE INTO referential_values(
                                       definition_id, value, sort_order, is_active,
                                       created_at, updated_at
                                   ) VALUES (?, ?, ?, 1, ?, ?)""",
                                (int(def_row["id"]), value, order, now, now),
                            )

        return self.custom_field_map(collection_id)[str(field_key)]


    def update_custom_field_calculation(
        self, collection_id: int, field_key: str, calculation_formula: str
    ) -> None:
        """Met à jour uniquement la formule d'un champ calculé personnalisé."""
        self._invalidate_custom_fields_cache(collection_id)
        with self._connect() as connection:
            self._ensure_custom_fields_table(connection)
            row = connection.execute(
                "SELECT field_type FROM collection_custom_fields WHERE collection_id=? AND field_key=?",
                (int(collection_id), str(field_key)),
            ).fetchone()
            if row is None:
                raise ValueError("Champ personnalisé introuvable.")
            if str(row["field_type"] or "") != "calculated":
                return
            connection.execute(
                "UPDATE collection_custom_fields SET calculation_formula=? WHERE collection_id=? AND field_key=?",
                (str(calculation_formula or ""), int(collection_id), str(field_key)),
            )

    def delete_custom_field(self, collection_id: int, field_key: str) -> None:
        self._invalidate_custom_fields_cache(collection_id)
        with self._connect() as connection:
            self._ensure_custom_fields_table(connection)
            self._ensure_record_custom_values_table(connection)
            row = connection.execute("SELECT referential_code FROM collection_custom_fields WHERE collection_id=? AND field_key=?", (int(collection_id), str(field_key))).fetchone()
            if row is None:
                return
            self._ensure_field_links_table(connection)
            connection.execute(
                "DELETE FROM collection_field_links WHERE collection_id=? AND (linked_key=? OR master_key=?)",
                (int(collection_id), str(field_key), str(field_key)),
            )
            connection.execute(
                "DELETE FROM collection_field_masters WHERE collection_id=? AND field_key=?",
                (int(collection_id), str(field_key)),
            )
            connection.execute("DELETE FROM record_custom_values WHERE field_key=? AND record_id IN (SELECT id FROM records WHERE collection_id=?)", (str(field_key), int(collection_id)))
            connection.execute("DELETE FROM collection_model_fields WHERE collection_id=? AND field_key=?", (int(collection_id), str(field_key)))
            if row["referential_code"]:
                # Compatibilité avec les anciennes bases MM3 : dans plusieurs
                # modèles referential_values référence encore la définition avec
                # ON DELETE NO ACTION. Nettoyer les valeurs explicitement évite
                # FOREIGN KEY constraint failed lors de la suppression d'un champ
                # Liste (ex. ancien Localité type converti en champ personnalisable).
                def_row = connection.execute(
                    "SELECT id FROM referential_definitions WHERE collection_id=? AND code=?",
                    (int(collection_id), str(row["referential_code"])),
                ).fetchone()
                if def_row is not None:
                    connection.execute(
                        "DELETE FROM referential_values WHERE definition_id=?",
                        (int(def_row["id"]),),
                    )
                connection.execute(
                    "DELETE FROM referential_definitions WHERE collection_id=? AND code=?",
                    (int(collection_id), str(row["referential_code"])),
                )
            connection.execute("DELETE FROM collection_custom_fields WHERE collection_id=? AND field_key=?", (int(collection_id), str(field_key)))

    @classmethod
    def configurable_fields(cls) -> tuple[str, ...]:
        return tuple(field.key for field in FIELDS if field.key not in cls.NON_CONFIGURABLE)

    def visible_fields(self, collection_id: int) -> set[str]:
        allowed = set(self.all_model_keys(collection_id))
        with self._connect() as connection:
            self._ensure_table(connection)
            rows = connection.execute(
                "SELECT field_key, visible FROM collection_model_fields WHERE collection_id=?",
                (int(collection_id),),
            ).fetchall()
        overrides = {str(row["field_key"]): bool(row["visible"]) for row in rows}
        visible = {key for key in allowed if overrides.get(key, True)}
        visible.add("record_number")
        return visible

    def set_visible_fields(self, collection_id: int, visible_fields: set[str]) -> None:
        allowed = set(self.all_model_keys(collection_id))
        visible = {str(key) for key in visible_fields if str(key) in allowed}
        with self._connect() as connection:
            self._ensure_table(connection)
            for key in allowed:
                value = 1 if key in visible else 0
                row = connection.execute(
                    "SELECT 1 FROM collection_model_fields WHERE collection_id=? AND field_key=?",
                    (int(collection_id), key),
                ).fetchone()
                if row is None:
                    connection.execute(
                        "INSERT INTO collection_model_fields(collection_id, field_key, visible) "
                        "VALUES (?, ?, ?)",
                        (int(collection_id), key, value),
                    )
                else:
                    connection.execute(
                        "UPDATE collection_model_fields SET visible=? "
                        "WHERE collection_id=? AND field_key=?",
                        (value, int(collection_id), key),
                    )

    def custom_labels(self, collection_id: int) -> dict[str, str]:
        with self._connect() as connection:
            self._ensure_table(connection)
            rows = connection.execute(
                "SELECT field_key, custom_label FROM collection_model_fields WHERE collection_id = ? AND custom_label IS NOT NULL",
                (int(collection_id),),
            ).fetchall()
        return {str(row["field_key"]): str(row["custom_label"]) for row in rows if str(row["custom_label"]).strip()}

    def set_custom_labels(self, collection_id: int, labels: dict[str, str]) -> None:
        allowed = set(self.all_model_keys(collection_id))
        cleaned = {
            str(k): str(v).strip()
            for k, v in labels.items()
            if str(k) in allowed and str(v).strip()
        }
        with self._connect() as connection:
            self._ensure_table(connection)
            for key in allowed:
                custom = cleaned.get(key)
                row = connection.execute(
                    "SELECT 1 FROM collection_model_fields WHERE collection_id=? AND field_key=?",
                    (int(collection_id), key),
                ).fetchone()
                if row is None:
                    if custom:
                        connection.execute(
                            "INSERT INTO collection_model_fields("
                            "collection_id, field_key, visible, custom_label) VALUES (?, ?, 1, ?)",
                            (int(collection_id), key, custom),
                        )
                else:
                    connection.execute(
                        "UPDATE collection_model_fields SET custom_label=? "
                        "WHERE collection_id=? AND field_key=?",
                        (custom, int(collection_id), key),
                    )

    def field_placement(self, collection_id: int) -> dict[str, tuple[str, int]]:
        placement = dict(DEFAULT_PLACEMENT)
        custom_map = self.custom_field_map(collection_id)
        for idx, (key, row) in enumerate(custom_map.items()):
            group = str(row.get("initial_group") or "Identification")
            if group not in MODEL_BLOCKS:
                group = "Identification"
            placement[key] = (group, 100 + idx)

        allowed = set(MOVABLE_FIELDS) | set(custom_map)
        with self._connect() as connection:
            self._ensure_table(connection)
            rows = connection.execute(
                "SELECT field_key, block_name, position FROM collection_model_fields "
                "WHERE collection_id=? AND block_name IS NOT NULL",
                (int(collection_id),),
            ).fetchall()
        for row in rows:
            key = str(row["field_key"])
            block = str(row["block_name"] or "")
            if key in allowed and block in MODEL_BLOCKS:
                try:
                    pos = max(0, int(row["position"] or 0))
                except Exception:
                    pos = 0
                placement[key] = (block, pos)
        return placement

    def set_field_placement(
        self, collection_id: int, placement: dict[str, tuple[str, int]],
    ) -> None:
        allowed = set(MOVABLE_FIELDS) | set(self.custom_field_map(collection_id))
        with self._connect() as connection:
            self._ensure_table(connection)
            for key, value in placement.items():
                if key not in allowed:
                    continue
                try:
                    block, pos = value
                    pos = max(0, int(pos))
                except Exception:
                    continue
                if block not in MODEL_BLOCKS:
                    continue
                row = connection.execute(
                    "SELECT 1 FROM collection_model_fields WHERE collection_id=? AND field_key=?",
                    (int(collection_id), key),
                ).fetchone()
                if row is None:
                    connection.execute(
                        "INSERT INTO collection_model_fields("
                        "collection_id, field_key, visible, block_name, position) "
                        "VALUES (?, ?, 1, ?, ?)",
                        (int(collection_id), key, block, pos),
                    )
                else:
                    connection.execute(
                        "UPDATE collection_model_fields SET block_name=?, position=? "
                        "WHERE collection_id=? AND field_key=?",
                        (block, pos, int(collection_id), key),
                    )

    def visual_positions(
        self, collection_id: int, placement: dict[str, tuple[str, int]],
    ) -> dict[str, tuple[int, int]]:
        all_keys = set(self.all_model_keys(collection_id))
        result = {}
        for key in self.configurable_fields():
            geom = DEFAULT_FIELD_GEOMETRY.get(key)
            if geom is not None:
                result[key] = (int(geom[0]), int(geom[1]))
        for key in all_keys:
            if key not in result:
                _block, pos = placement.get(key, ("Identification", 0))
                result[key] = (12, 12 + max(0, int(pos)) * 38)
        with self._connect() as connection:
            self._ensure_table(connection)
            rows = connection.execute(
                "SELECT field_key, visual_x, visual_y FROM collection_model_fields "
                "WHERE collection_id=? AND visual_x IS NOT NULL AND visual_y IS NOT NULL",
                (int(collection_id),),
            ).fetchall()
        for row in rows:
            key = str(row["field_key"])
            if key in all_keys:
                result[key] = (max(0, int(row["visual_x"])), max(0, int(row["visual_y"])))
        return result

    def set_visual_positions(
        self, collection_id: int, positions: dict[str, tuple[int, int]],
    ) -> None:
        allowed = set(self.all_model_keys(collection_id))
        with self._connect() as connection:
            self._ensure_table(connection)
            for key, value in positions.items():
                if key not in allowed:
                    continue
                try:
                    x, y = max(0, int(value[0])), max(0, int(value[1]))
                except Exception:
                    continue
                row = connection.execute(
                    "SELECT 1 FROM collection_model_fields WHERE collection_id=? AND field_key=?",
                    (int(collection_id), key),
                ).fetchone()
                if row is None:
                    connection.execute(
                        "INSERT INTO collection_model_fields("
                        "collection_id, field_key, visible, visual_x, visual_y) "
                        "VALUES (?, ?, 1, ?, ?)",
                        (int(collection_id), key, x, y),
                    )
                else:
                    connection.execute(
                        "UPDATE collection_model_fields SET visual_x=?, visual_y=? "
                        "WHERE collection_id=? AND field_key=?",
                        (x, y, int(collection_id), key),
                    )

    def visual_sizes(self, collection_id: int) -> dict[str, tuple[int, int]]:
        all_keys = set(self.all_model_keys(collection_id))
        result = {
            key: (int(geom[2]), int(geom[3]))
            for key, geom in DEFAULT_FIELD_GEOMETRY.items()
            if key in all_keys
        }
        for key in all_keys:
            result.setdefault(key, (260, 31))
        with self._connect() as connection:
            self._ensure_table(connection)
            rows = connection.execute(
                "SELECT field_key, visual_w, visual_h FROM collection_model_fields "
                "WHERE collection_id=? AND visual_w IS NOT NULL AND visual_h IS NOT NULL",
                (int(collection_id),),
            ).fetchall()
        for row in rows:
            key = str(row["field_key"])
            if key in all_keys:
                result[key] = (max(120, int(row["visual_w"])), max(26, int(row["visual_h"])))
        return result

    def set_visual_sizes(
        self, collection_id: int, sizes: dict[str, tuple[int, int]],
    ) -> None:
        allowed = set(self.all_model_keys(collection_id))
        with self._connect() as connection:
            self._ensure_table(connection)
            for key, value in sizes.items():
                if key not in allowed:
                    continue
                try:
                    width, height = max(120, int(value[0])), max(26, int(value[1]))
                except Exception:
                    continue
                row = connection.execute(
                    "SELECT 1 FROM collection_model_fields WHERE collection_id=? AND field_key=?",
                    (int(collection_id), key),
                ).fetchone()
                if row is None:
                    connection.execute(
                        "INSERT INTO collection_model_fields("
                        "collection_id, field_key, visible, visual_w, visual_h) "
                        "VALUES (?, ?, 1, ?, ?)",
                        (int(collection_id), key, width, height),
                    )
                else:
                    connection.execute(
                        "UPDATE collection_model_fields SET visual_w=?, visual_h=? "
                        "WHERE collection_id=? AND field_key=?",
                        (width, height, int(collection_id), key),
                    )

    def _ensure_appearance_table(self, connection: sqlite3.Connection) -> None:
        if self._appearance_schema_ready:
            return
        connection.execute(
            """CREATE TABLE IF NOT EXISTS collection_model_appearance(
                collection_id INTEGER PRIMARY KEY,
                sheet_background TEXT,
                field_styles TEXT,
                group_styles TEXT,
                record_opening TEXT,
                last_record_id INTEGER,
                report_orientation TEXT,
                FOREIGN KEY(collection_id) REFERENCES collections(id)
            )"""
        )
        columns = {str(row["name"]) for row in connection.execute(
            "PRAGMA table_info(collection_model_appearance)"
        ).fetchall()}
        if "field_styles" not in columns:
            connection.execute(
                "ALTER TABLE collection_model_appearance ADD COLUMN field_styles TEXT"
            )
        if "group_styles" not in columns:
            connection.execute(
                "ALTER TABLE collection_model_appearance ADD COLUMN group_styles TEXT"
            )
        if "record_opening" not in columns:
            connection.execute("ALTER TABLE collection_model_appearance ADD COLUMN record_opening TEXT")
        if "last_record_id" not in columns:
            connection.execute("ALTER TABLE collection_model_appearance ADD COLUMN last_record_id INTEGER")
        if "report_orientation" not in columns:
            connection.execute("ALTER TABLE collection_model_appearance ADD COLUMN report_orientation TEXT")
        self._appearance_schema_ready = True

    def group_styles(self, collection_id: int) -> dict[str, dict]:
        with self._connect() as connection:
            self._ensure_appearance_table(connection)
            row = connection.execute(
                "SELECT group_styles FROM collection_model_appearance WHERE collection_id = ?",
                (int(collection_id),),
            ).fetchone()
        if not row or not row["group_styles"]:
            return {}
        try:
            data = json.loads(str(row["group_styles"]))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def set_group_styles(self, collection_id: int, styles: dict[str, dict]) -> None:
        payload = json.dumps(styles or {}, ensure_ascii=False, separators=(",", ":"))
        with self._connect() as connection:
            self._ensure_appearance_table(connection)
            connection.execute(
                "INSERT INTO collection_model_appearance(collection_id, group_styles) VALUES (?, ?) "
                "ON CONFLICT(collection_id) DO UPDATE SET group_styles=excluded.group_styles",
                (int(collection_id), payload),
            )

    def field_styles(self, collection_id: int) -> dict[str, dict]:
        with self._connect() as connection:
            self._ensure_appearance_table(connection)
            row = connection.execute(
                "SELECT field_styles FROM collection_model_appearance WHERE collection_id = ?",
                (int(collection_id),),
            ).fetchone()
        if not row or not row["field_styles"]:
            return {}
        try:
            data = json.loads(str(row["field_styles"]))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def set_field_styles(self, collection_id: int, styles: dict[str, dict]) -> None:
        payload = json.dumps(styles or {}, ensure_ascii=False, separators=(",", ":"))
        with self._connect() as connection:
            self._ensure_appearance_table(connection)
            connection.execute(
                "INSERT INTO collection_model_appearance(collection_id, field_styles) VALUES (?, ?) "
                "ON CONFLICT(collection_id) DO UPDATE SET field_styles=excluded.field_styles",
                (int(collection_id), payload),
            )

    def sheet_background(self, collection_id: int, default: str = "#EEF5F1") -> str:
        with self._connect() as connection:
            self._ensure_appearance_table(connection)
            row = connection.execute(
                "SELECT sheet_background FROM collection_model_appearance WHERE collection_id = ?",
                (int(collection_id),),
            ).fetchone()
        value = str(row["sheet_background"]).strip() if row and row["sheet_background"] else ""
        return value if value.startswith("#") and len(value) in (4, 7, 9) else default

    def set_sheet_background(self, collection_id: int, color: str | None) -> None:
        value = (str(color).strip() if color else None)
        with self._connect() as connection:
            self._ensure_appearance_table(connection)
            connection.execute(
                "INSERT INTO collection_model_appearance(collection_id, sheet_background) VALUES (?, ?) "
                "ON CONFLICT(collection_id) DO UPDATE SET sheet_background=excluded.sheet_background",
                (int(collection_id), value),
            )


    def collection_preferences(self, collection_id: int) -> dict:
        """Réglages propres à une collection, stockés dans son fichier .db."""
        with self._connect() as connection:
            self._ensure_appearance_table(connection)
            row = connection.execute(
                "SELECT record_opening, last_record_id, report_orientation "
                "FROM collection_model_appearance WHERE collection_id = ?",
                (int(collection_id),),
            ).fetchone()
        opening = str(row["record_opening"] or "last") if row else "last"
        orientation = str(row["report_orientation"] or "portrait") if row else "portrait"
        return {
            "record_opening": opening if opening in ("last", "first") else "last",
            "last_record_id": int(row["last_record_id"]) if row and row["last_record_id"] is not None else None,
            "report_orientation": orientation if orientation in ("portrait", "landscape") else "portrait",
        }

    def set_collection_preferences(
        self, collection_id: int, *, record_opening: str | None = None,
        last_record_id: int | None = None, report_orientation: str | None = None,
        update_last_record: bool = False,
    ) -> None:
        """Met à jour uniquement les préférences fournies, sans écraser les autres."""
        with self._connect() as connection:
            self._ensure_appearance_table(connection)
            connection.execute(
                "INSERT OR IGNORE INTO collection_model_appearance(collection_id) VALUES (?)",
                (int(collection_id),),
            )
            if record_opening in ("last", "first"):
                connection.execute(
                    "UPDATE collection_model_appearance SET record_opening=? WHERE collection_id=?",
                    (record_opening, int(collection_id)),
                )
            if report_orientation in ("portrait", "landscape"):
                connection.execute(
                    "UPDATE collection_model_appearance SET report_orientation=? WHERE collection_id=?",
                    (report_orientation, int(collection_id)),
                )
            if update_last_record:
                connection.execute(
                    "UPDATE collection_model_appearance SET last_record_id=? WHERE collection_id=?",
                    (last_record_id, int(collection_id)),
                )

    def tab_order(
        self, collection_id: int, default_order: list[str] | tuple[str, ...],
    ) -> list[str]:
        allowed = set(self.all_model_keys(collection_id))
        default = [str(key) for key in default_order if str(key) in allowed]
        with self._connect() as connection:
            self._ensure_table(connection)
            rows = connection.execute(
                "SELECT field_key, tab_position FROM collection_model_fields "
                "WHERE collection_id=? AND tab_position IS NOT NULL "
                "ORDER BY tab_position, field_key",
                (int(collection_id),),
            ).fetchall()
        # 23.9.2.5 — tab_position enregistré par l'Atelier est l'autorité
        # absolue. L'ancien code filtrait d'abord les lignes enregistrées par
        # ``default`` : un champ personnalisé, déplacé dans un cadre nouveau ou
        # absent de l'ordre visuel de secours pouvait donc disparaître de la
        # chaîne réelle de Tab/Entrée.
        ordered = []
        for row in rows:
            key = str(row["field_key"])
            if key in allowed and key not in ordered:
                ordered.append(key)
        ordered.extend(key for key in default if key not in ordered)
        ordered.extend(str(key) for key in self.all_model_keys(collection_id) if str(key) not in ordered)
        return ordered

    def set_tab_order(
        self, collection_id: int, ordered_fields: list[str] | tuple[str, ...],
    ) -> None:
        allowed = list(self.all_model_keys(collection_id))
        ordered = [str(key) for key in ordered_fields if str(key) in allowed]
        ordered.extend(key for key in allowed if key not in ordered)
        with self._connect() as connection:
            self._ensure_table(connection)
            for pos, key in enumerate(ordered):
                row = connection.execute(
                    "SELECT 1 FROM collection_model_fields WHERE collection_id=? AND field_key=?",
                    (int(collection_id), key),
                ).fetchone()
                if row is None:
                    connection.execute(
                        "INSERT INTO collection_model_fields("
                        "collection_id, field_key, visible, tab_position) VALUES (?, ?, 1, ?)",
                        (int(collection_id), key, pos),
                    )
                else:
                    connection.execute(
                        "UPDATE collection_model_fields SET tab_position=? "
                        "WHERE collection_id=? AND field_key=?",
                        (pos, int(collection_id), key),
                    )


    # ------------------------------------------------------------------
    # 23.9.3.6.0 — Liaisons de champs : Maître / Relié à / Délier de
    # ------------------------------------------------------------------
    @staticmethod
    def _ensure_field_links_table(connection: sqlite3.Connection) -> None:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS collection_field_masters(
                collection_id INTEGER NOT NULL,
                field_key TEXT NOT NULL,
                PRIMARY KEY(collection_id, field_key),
                FOREIGN KEY(collection_id) REFERENCES collections(id)
            )"""
        )
        connection.execute(
            """CREATE TABLE IF NOT EXISTS collection_field_links(
                collection_id INTEGER NOT NULL,
                linked_key TEXT NOT NULL,
                master_key TEXT NOT NULL,
                PRIMARY KEY(collection_id, linked_key),
                FOREIGN KEY(collection_id) REFERENCES collections(id)
            )"""
        )

    def field_masters(self, collection_id: int) -> set[str]:
        with self._connect() as connection:
            self._ensure_field_links_table(connection)
            rows = connection.execute(
                "SELECT field_key FROM collection_field_masters WHERE collection_id=?",
                (int(collection_id),),
            ).fetchall()
        return {str(row["field_key"]) for row in rows}

    def field_links(self, collection_id: int) -> dict[str, str]:
        with self._connect() as connection:
            self._ensure_field_links_table(connection)
            rows = connection.execute(
                "SELECT linked_key, master_key FROM collection_field_links WHERE collection_id=?",
                (int(collection_id),),
            ).fetchall()
        return {str(row["linked_key"]): str(row["master_key"]) for row in rows}

    def set_field_relations(
        self, collection_id: int, masters: set[str] | list[str] | tuple[str, ...],
        links: dict[str, str],
    ) -> None:
        cid = int(collection_id)
        master_set = {str(key) for key in masters}
        clean_links = {
            str(linked): str(master)
            for linked, master in (links or {}).items()
            if str(master) in master_set and str(linked) != str(master)
        }
        with self._connect() as connection:
            self._ensure_field_links_table(connection)
            connection.execute(
                "DELETE FROM collection_field_links WHERE collection_id=?", (cid,)
            )
            connection.execute(
                "DELETE FROM collection_field_masters WHERE collection_id=?", (cid,)
            )
            connection.executemany(
                "INSERT INTO collection_field_masters(collection_id, field_key) VALUES (?, ?)",
                [(cid, key) for key in sorted(master_set)],
            )
            connection.executemany(
                "INSERT INTO collection_field_links(collection_id, linked_key, master_key) VALUES (?, ?, ?)",
                [(cid, linked, master) for linked, master in clean_links.items()],
            )

    @staticmethod
    def _record_columns(connection: sqlite3.Connection) -> set[str]:
        return {str(row[1]) for row in connection.execute("PRAGMA table_info(records)").fetchall()}

    @staticmethod
    def _ensure_record_custom_values_for_links(connection: sqlite3.Connection) -> None:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS record_custom_values(
                record_id INTEGER NOT NULL,
                field_key TEXT NOT NULL,
                value TEXT NOT NULL DEFAULT '',
                PRIMARY KEY(record_id, field_key),
                FOREIGN KEY(record_id) REFERENCES records(id) ON DELETE CASCADE
            )"""
        )

    def _matching_record_ids_for_master(
        self, connection: sqlite3.Connection, collection_id: int,
        master_key: str, master_value: str,
    ) -> list[int]:
        columns = self._record_columns(connection)
        cid = int(collection_id)
        key = str(master_key)
        value = str(master_value or '')
        if key in columns:
            rows = connection.execute(
                f"SELECT id FROM records WHERE collection_id=? AND COALESCE(\"{key}\",'')=? ORDER BY id",
                (cid, value),
            ).fetchall()
        else:
            self._ensure_record_custom_values_for_links(connection)
            rows = connection.execute(
                """SELECT r.id FROM records r
                   JOIN record_custom_values cv ON cv.record_id=r.id
                   WHERE r.collection_id=? AND cv.field_key=? AND COALESCE(cv.value,'')=?
                   ORDER BY r.id""",
                (cid, key, value),
            ).fetchall()
        return [int(row[0]) for row in rows]

    def linked_values_for_master(
        self, collection_id: int, master_key: str, master_value: str,
    ) -> dict[str, str]:
        """Valeurs de référence des champs reliés pour une valeur maître connue."""
        links = self.field_links(int(collection_id))
        linked_keys = [k for k, m in links.items() if m == str(master_key)]
        if not linked_keys or not str(master_value or '').strip():
            return {}
        with self._connect() as connection:
            self._ensure_record_custom_values_for_links(connection)
            self._ensure_imported_reference_table(connection)

            # Priorité au référentiel tabulaire importé. Les champs absents
            # pourront encore être complétés depuis les fiches historiques.
            imported_rows = connection.execute(
                """SELECT linked_key, linked_value
                   FROM collection_reference_data
                   WHERE collection_id=? AND master_key=?
                     AND master_value=? COLLATE NOCASE""",
                (int(collection_id), str(master_key), str(master_value)),
            ).fetchall()
            imported = {
                str(row["linked_key"]): str(row["linked_value"] or "")
                for row in imported_rows
                if str(row["linked_key"]) in linked_keys
                # 39.32.11.7.19 — compatibilité avec d'anciens imports ayant
                # enregistré des chaînes vides : elles ne doivent pas avoir
                # priorité sur une valeur non vide déjà présente dans les fiches.
                and str(row["linked_value"] or "").strip()
            }

            ids = self._matching_record_ids_for_master(
                connection, int(collection_id), str(master_key), str(master_value)
            )
            if not ids:
                return imported
            columns = self._record_columns(connection)
            result: dict[str, str] = dict(imported)
            placeholders = ','.join('?' for _ in ids)
            for key in linked_keys:
                if key in result:
                    continue
                if key in columns:
                    row = connection.execute(
                        f"SELECT COALESCE(\"{key}\",'') FROM records "
                        f"WHERE id IN ({placeholders}) AND trim(COALESCE(\"{key}\",''))<>'' "
                        'ORDER BY id LIMIT 1',
                        tuple(ids),
                    ).fetchone()
                else:
                    row = connection.execute(
                        f"SELECT COALESCE(value,'') FROM record_custom_values "
                        f"WHERE field_key=? AND record_id IN ({placeholders}) "
                        "AND trim(COALESCE(value,''))<>'' ORDER BY record_id LIMIT 1",
                        (str(key), *ids),
                    ).fetchone()
                if row is not None:
                    result[str(key)] = str(row[0] or '')
                else:
                    # 23.9.3.6.4 — le vide est une valeur de liaison à part entière.
                    # S'il existe des fiches pour ce Maître mais aucune valeur
                    # non vide pour ce champ relié, le résultat canonique est "".
                    result[str(key)] = ""
            return result


    @staticmethod
    def _ensure_imported_reference_table(connection: sqlite3.Connection) -> None:
        """Données externes servant de référentiel Maître -> champs reliés."""
        connection.execute(
            """CREATE TABLE IF NOT EXISTS collection_reference_data(
                collection_id INTEGER NOT NULL,
                master_key TEXT NOT NULL,
                master_value TEXT NOT NULL,
                linked_key TEXT NOT NULL,
                linked_value TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL DEFAULT '',
                PRIMARY KEY(collection_id, master_key, master_value, linked_key),
                FOREIGN KEY(collection_id) REFERENCES collections(id)
            )"""
        )

    def import_reference_rows(
        self,
        collection_id: int,
        master_key: str,
        rows: list[dict[str, str]],
    ) -> dict[str, int]:
        """Importe un référentiel tabulaire sans créer de fiches.

        Chaque ligne contient la valeur Maître et zéro ou plusieurs champs reliés.
        Une valeur déjà présente est mise à jour par la dernière occurrence du fichier.
        """
        cid = int(collection_id)
        master = str(master_key)
        clean_rows = []
        linked_keys: set[str] = set()
        for row in rows or []:
            normalized = {str(k): str(v or "").strip() for k, v in dict(row).items()}
            master_value = normalized.get(master, "").strip()
            if not master_value:
                continue
            clean_rows.append(normalized)
            linked_keys.update(k for k in normalized if k != master)

        if not clean_rows:
            return {"rows": 0, "masters": 0, "values": 0}

        now = datetime.now().isoformat(timespec="seconds")
        masters_seen: set[str] = set()
        values_count = 0
        with self._connect() as connection:
            self._ensure_field_links_table(connection)
            self._ensure_imported_reference_table(connection)

            # Conserver les relations existantes et y ajouter celles de l'import.
            current_masters = {
                str(r["field_key"])
                for r in connection.execute(
                    "SELECT field_key FROM collection_field_masters WHERE collection_id=?",
                    (cid,),
                ).fetchall()
            }
            current_masters.add(master)
            current_links = {
                str(r["linked_key"]): str(r["master_key"])
                for r in connection.execute(
                    "SELECT linked_key, master_key FROM collection_field_links WHERE collection_id=?",
                    (cid,),
                ).fetchall()
            }
            for linked in linked_keys:
                if linked != master:
                    current_links[linked] = master

            connection.execute(
                "DELETE FROM collection_field_links WHERE collection_id=?", (cid,)
            )
            connection.execute(
                "DELETE FROM collection_field_masters WHERE collection_id=?", (cid,)
            )
            connection.executemany(
                "INSERT INTO collection_field_masters(collection_id, field_key) VALUES (?, ?)",
                [(cid, key) for key in sorted(current_masters)],
            )
            connection.executemany(
                "INSERT INTO collection_field_links(collection_id, linked_key, master_key) VALUES (?, ?, ?)",
                [
                    (cid, linked, linked_master)
                    for linked, linked_master in current_links.items()
                    if linked != linked_master and linked_master in current_masters
                ],
            )

            reference_rows = []
            for row in clean_rows:
                master_value = row[master].strip()
                masters_seen.add(master_value.casefold())
                for linked in linked_keys:
                    linked_value = row.get(linked, "").strip()
                    # 39.32.11.7.19 — un import de référentiel ne doit jamais
                    # transformer une information déjà connue en valeur vide.
                    # Les cellules vides signifient ici « aucune information
                    # fournie par la source », pas « effacer la valeur ».
                    if not linked_value:
                        continue
                    reference_rows.append(
                        (cid, master, master_value, linked, linked_value, now)
                    )
            if reference_rows:
                connection.executemany(
                    """INSERT INTO collection_reference_data(
                           collection_id, master_key, master_value,
                           linked_key, linked_value, updated_at
                       ) VALUES (?, ?, ?, ?, ?, ?)
                       ON CONFLICT(collection_id, master_key, master_value, linked_key)
                       DO UPDATE SET linked_value=excluded.linked_value,
                                     updated_at=excluded.updated_at""",
                    reference_rows,
                )
            values_count = len(reference_rows)

        return {
            "rows": len(clean_rows),
            "masters": len(masters_seen),
            "values": values_count,
        }


    def backfill_linked_blanks(self, collection_id: int) -> int:
        """Complète les anciennes valeurs reliées vides sans écraser l'existant.

        23.9.3.6.5 — lorsqu'une liaison vient d'être créée, ou lorsqu'une
        collection déjà reliée est ouverte, chaque couple (Maître, valeur)
        cherche une valeur reliée non vide déjà connue. Cette valeur sert
        uniquement à remplir les fiches du même Maître dont le champ relié
        est encore vide. Les anciennes valeurs non vides sont conservées.
        """
        cid = int(collection_id)
        links = self.field_links(cid)
        if not links:
            return 0

        updated_count = 0
        now = datetime.now().isoformat(timespec="seconds")

        with self._connect() as connection:
            self._ensure_record_custom_values_for_links(connection)
            columns = self._record_columns(connection)

            for linked_key, master_key in links.items():
                linked_key = str(linked_key)
                master_key = str(master_key)

                if master_key in columns:
                    master_sql = (
                        f'SELECT DISTINCT COALESCE("{master_key}", \'\') AS master_value '
                        f'FROM records WHERE collection_id=? '
                        f'AND trim(COALESCE("{master_key}", \'\'))<>\'\' '
                        f'ORDER BY master_value'
                    )
                    master_rows = connection.execute(master_sql, (cid,)).fetchall()
                else:
                    master_rows = connection.execute(
                        """SELECT DISTINCT COALESCE(cv.value,'') AS master_value
                           FROM records r
                           JOIN record_custom_values cv ON cv.record_id=r.id
                           WHERE r.collection_id=?
                             AND cv.field_key=?
                             AND trim(COALESCE(cv.value,''))<>''
                           ORDER BY master_value""",
                        (cid, master_key),
                    ).fetchall()

                for master_row in master_rows:
                    master_value = str(master_row[0] or "")
                    if not master_value:
                        continue

                    ids = self._matching_record_ids_for_master(
                        connection, cid, master_key, master_value
                    )
                    if not ids:
                        continue

                    placeholders = ",".join("?" for _ in ids)

                    # Un référentiel tabulaire importé est la source canonique.
                    # Il doit primer sur une ancienne association présente dans les fiches,
                    # sinon un nouveau référentiel pourrait hériter d'une valeur incohérente.
                    imported_ref = connection.execute(
                        """SELECT linked_value FROM collection_reference_data
                           WHERE collection_id=? AND master_key=?
                             AND master_value=? COLLATE NOCASE AND linked_key=?
                           LIMIT 1""",
                        (cid, master_key, master_value, linked_key),
                    ).fetchone()
                    if imported_ref is not None:
                        reference_value = str(imported_ref[0] or "")
                    else:
                        reference_value = None

                    if reference_value is None:
                        if linked_key in columns:
                            ref_sql = (
                                f'SELECT COALESCE("{linked_key}", '') '
                                f'FROM records WHERE id IN ({placeholders}) '
                                f'AND trim(COALESCE("{linked_key}", ''))<>'' '
                                f'ORDER BY id LIMIT 1'
                            )
                            ref_row = connection.execute(ref_sql, tuple(ids)).fetchone()
                        else:
                            ref_row = connection.execute(
                                f"""SELECT COALESCE(value,'')
                                    FROM record_custom_values
                                    WHERE field_key=?
                                      AND record_id IN ({placeholders})
                                      AND trim(COALESCE(value,''))<>''
                                    ORDER BY record_id LIMIT 1""",
                                (linked_key, *ids),
                            ).fetchone()
                        if ref_row is None:
                            continue
                        reference_value = str(ref_row[0] or "")

                    if not reference_value:
                        continue

                    if linked_key in columns:
                        update_sql = (
                            f'UPDATE records SET "{linked_key}"=?, updated_at=? '
                            f'WHERE id IN ({placeholders}) '
                            f'AND trim(COALESCE("{linked_key}", \'\'))=\'\''
                        )
                        cursor = connection.execute(
                            update_sql, (reference_value, now, *ids)
                        )
                        updated_count += max(0, int(cursor.rowcount or 0))
                    else:
                        existing_rows = connection.execute(
                            f"""SELECT record_id, COALESCE(value,'')
                                FROM record_custom_values
                                WHERE field_key=?
                                  AND record_id IN ({placeholders})""",
                            (linked_key, *ids),
                        ).fetchall()
                        existing = {
                            int(row[0]): str(row[1] or "")
                            for row in existing_rows
                        }
                        missing_or_blank = [
                            int(rid) for rid in ids
                            if not str(existing.get(int(rid), "")).strip()
                        ]
                        if missing_or_blank:
                            connection.executemany(
                                """INSERT INTO record_custom_values(record_id, field_key, value)
                                   VALUES (?, ?, ?)
                                   ON CONFLICT(record_id, field_key)
                                   DO UPDATE SET value=excluded.value""",
                                [
                                    (rid, linked_key, reference_value)
                                    for rid in missing_or_blank
                                ],
                            )
                            updated_count += len(missing_or_blank)

        return updated_count

    def remove_reference_master_values(
        self, collection_id: int, master_key: str, master_values: list[str] | tuple[str, ...]
    ) -> int:
        """Retire des données canoniques Maître/Relié les valeurs retirées d'un référentiel.

        Les fiches existantes ne sont jamais modifiées. Cela évite qu'une valeur
        supprimée du réservoir de propositions soit recréée depuis
        collection_reference_data lors d'un rafraîchissement/import ultérieur.
        """
        cid = int(collection_id)
        key = str(master_key)
        values = [str(v or "").strip() for v in master_values]
        values = [v for v in values if v]
        if not values:
            return 0
        with self._connect() as connection:
            self._ensure_imported_reference_table(connection)
            total = 0
            for value in values:
                cur = connection.execute(
                    """DELETE FROM collection_reference_data
                       WHERE collection_id=? AND master_key=?
                         AND master_value=? COLLATE NOCASE""",
                    (cid, key, value),
                )
                total += int(cur.rowcount or 0)
        return total

    def propagate_linked_value(
        self, collection_id: int, master_key: str, master_value: str,
        linked_key: str, linked_value: str,
    ) -> list[int]:
        """Applique immédiatement une valeur reliée à toutes les fiches du maître."""
        cid = int(collection_id)
        master_key = str(master_key)
        linked_key = str(linked_key)
        links = self.field_links(cid)
        if links.get(linked_key) != master_key or not str(master_value or '').strip():
            return []
        value = str(linked_value or '').strip()
        with self._connect() as connection:
            self._ensure_record_custom_values_for_links(connection)
            self._ensure_imported_reference_table(connection)
            now = datetime.now().isoformat(timespec='seconds')

            # Toute saisie manuelle d'un champ Relié enrichit le référentiel
            # canonique, y compris lorsque la valeur Maître existait seulement
            # dans une liste sans données relationnelles. Ainsi un nouveau Site
            # peut être complété progressivement sans perdre Département/Région/Pays.
            connection.execute(
                """INSERT INTO collection_reference_data(
                       collection_id, master_key, master_value,
                       linked_key, linked_value, updated_at
                   ) VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(collection_id, master_key, master_value, linked_key)
                   DO UPDATE SET linked_value=excluded.linked_value,
                                 updated_at=excluded.updated_at""",
                (cid, master_key, str(master_value), linked_key, value, now),
            )

            ids = self._matching_record_ids_for_master(
                connection, cid, master_key, str(master_value)
            )
            if not ids:
                return []
            columns = self._record_columns(connection)
            placeholders = ','.join('?' for _ in ids)
            if linked_key in columns:
                connection.execute(
                    f'UPDATE records SET "{linked_key}"=?, updated_at=? WHERE id IN ({placeholders})',
                    (value, now, *ids),
                )
            elif value:
                connection.executemany(
                    "INSERT INTO record_custom_values(record_id, field_key, value) VALUES (?, ?, ?) "
                    "ON CONFLICT(record_id, field_key) DO UPDATE SET value=excluded.value",
                    [(rid, linked_key, value) for rid in ids],
                )
            else:
                connection.execute(
                    f'DELETE FROM record_custom_values WHERE field_key=? AND record_id IN ({placeholders})',
                    (linked_key, *ids),
                )
        return ids

    def clear_tab_order(self, collection_id: int) -> None:
        """Revient au comportement par défaut : tabulation = ordre visuel."""
        with self._connect() as connection:
            self._ensure_table(connection)
            connection.execute(
                "UPDATE collection_model_fields SET tab_position = NULL WHERE collection_id = ?",
                (int(collection_id),),
            )

    def reset_model(self, collection_id: int) -> None:
        with self._connect() as connection:
            self._ensure_table(connection)
            connection.execute(
                "DELETE FROM collection_model_fields WHERE collection_id = ?",
                (int(collection_id),),
            )
