#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from core.model_manager import ModelManager


class RecordManager:
    """Persistance des premières données réelles de la fiche MM3."""

    FIELD_DEFAULTS = {
        "mineral_name": "",
        "mineral_2": "",
        "mineral_3": "",
        "species": "",
        "mineral_class": "",
        "chemical_formula": "",
        "internet_link": "",
        "site_internet_link": "",
        "crystal_system": "",
        "luminescence": "Non",
        "luminescence_intensity": "Aucune",
        "fluorescence_color": "Aucune",
        "site_name": "",
        "deposit": "",
        "department": "",
        "region": "",
        "country": "",
        "box_type": "",
        "category": "",
        "contact": "",
        "specimen_shape": "",
        "specimen_color": "",
        "quality": "",
        "description": "",
        "minimum_magnification": "20 X",
        "growth": "",
        "type_locality": "Non",
        "acquisition_date": "",
        "origin": "",
        "place": "",
        "box_count": "1",
        "price": "0.00 €",
        "total_cost": "0.00 €",
        "record_state": "OK",
    }

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection


    @staticmethod
    def _ensure_custom_values_table(connection: sqlite3.Connection) -> None:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS record_custom_values(
                record_id INTEGER NOT NULL,
                field_key TEXT NOT NULL,
                value TEXT NOT NULL DEFAULT '',
                PRIMARY KEY(record_id, field_key),
                FOREIGN KEY(record_id) REFERENCES records(id) ON DELETE CASCADE
            )"""
        )

    def replace_custom_values(self, record_id: int, values: dict[str, str]) -> None:
        """Remplace exactement les valeurs personnalisées d'une fiche."""
        with self._connect() as connection:
            self._ensure_table(connection)
            self._ensure_custom_values_table(connection)
            connection.execute(
                "DELETE FROM record_custom_values WHERE record_id=?", (int(record_id),)
            )
            for key, raw in (values or {}).items():
                value = str(raw or "").strip()
                if value:
                    connection.execute(
                        "INSERT INTO record_custom_values(record_id, field_key, value) VALUES (?, ?, ?)",
                        (int(record_id), str(key), value),
                    )

    def delete_record(self, record_id: int, collection_id: int) -> None:
        """Supprime une fiche précise ; les données filles suivent par cascade SQLite."""
        with self._connect() as connection:
            self._ensure_table(connection)
            connection.execute(
                "DELETE FROM records WHERE id=? AND collection_id=?",
                (int(record_id), int(collection_id)),
            )

    def custom_values(self, record_id: int) -> dict[str, str]:
        with self._connect() as connection:
            self._ensure_table(connection)
            self._ensure_custom_values_table(connection)
            rows = connection.execute(
                "SELECT field_key, value FROM record_custom_values WHERE record_id=?",
                (int(record_id),),
            ).fetchall()
        return {str(row["field_key"]): str(row["value"] or "") for row in rows}

    def custom_values_for_collection(self, collection_id: int) -> dict[int, dict[str, str]]:
        """Charge en une seule requête toutes les valeurs personnalisées d'une collection."""
        with self._connect() as connection:
            self._ensure_table(connection)
            self._ensure_custom_values_table(connection)
            rows = connection.execute(
                """SELECT cv.record_id, cv.field_key, cv.value
                   FROM record_custom_values cv
                   JOIN records r ON r.id=cv.record_id
                   WHERE r.collection_id=?""",
                (int(collection_id),),
            ).fetchall()
        result: dict[int, dict[str, str]] = {}
        for row in rows:
            rid = int(row["record_id"])
            result.setdefault(rid, {})[str(row["field_key"])] = str(row["value"] or "")
        return result

    def set_custom_values(self, record_id: int, values: dict[str, str]) -> None:
        with self._connect() as connection:
            self._ensure_table(connection)
            self._ensure_custom_values_table(connection)
            for key, raw in (values or {}).items():
                value = str(raw or "").strip()
                if value:
                    connection.execute(
                        "INSERT INTO record_custom_values(record_id, field_key, value) "
                        "VALUES (?, ?, ?) "
                        "ON CONFLICT(record_id, field_key) DO UPDATE SET value=excluded.value",
                        (int(record_id), str(key), value),
                    )
                else:
                    connection.execute(
                        "DELETE FROM record_custom_values WHERE record_id=? AND field_key=?",
                        (int(record_id), str(key)),
                    )

    @classmethod
    def _ensure_table(cls, connection: sqlite3.Connection) -> None:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS records(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                collection_id INTEGER NOT NULL,
                record_number INTEGER NOT NULL,
                mineral_name TEXT NOT NULL DEFAULT '',
                mineral_2 TEXT NOT NULL DEFAULT '',
                mineral_3 TEXT NOT NULL DEFAULT '',
                species TEXT NOT NULL DEFAULT '',
                mineral_class TEXT NOT NULL DEFAULT '',
                chemical_formula TEXT NOT NULL DEFAULT '',
                internet_link TEXT NOT NULL DEFAULT '',
                site_internet_link TEXT NOT NULL DEFAULT '',
                crystal_system TEXT NOT NULL DEFAULT '',
                luminescence TEXT NOT NULL DEFAULT 'Non',
                luminescence_intensity TEXT NOT NULL DEFAULT 'Aucune',
                fluorescence_color TEXT NOT NULL DEFAULT 'Aucune',
                site_name TEXT NOT NULL DEFAULT '',
                deposit TEXT NOT NULL DEFAULT '',
                department TEXT NOT NULL DEFAULT '',
                region TEXT NOT NULL DEFAULT '',
                country TEXT NOT NULL DEFAULT '',
                box_type TEXT NOT NULL DEFAULT '',
                category TEXT NOT NULL DEFAULT '',
                contact TEXT NOT NULL DEFAULT '',
                specimen_shape TEXT NOT NULL DEFAULT '',
                specimen_color TEXT NOT NULL DEFAULT '',
                quality TEXT NOT NULL DEFAULT '',
                description TEXT NOT NULL DEFAULT '',
                minimum_magnification TEXT NOT NULL DEFAULT '',
                growth TEXT NOT NULL DEFAULT '',
                type_locality TEXT NOT NULL DEFAULT '',
                acquisition_date TEXT NOT NULL DEFAULT '',
                origin TEXT NOT NULL DEFAULT '',
                place TEXT NOT NULL DEFAULT '',
                box_count TEXT NOT NULL DEFAULT '',
                price TEXT NOT NULL DEFAULT '',
                total_cost TEXT NOT NULL DEFAULT '',
                photo_data BLOB,
                photo_format TEXT NOT NULL DEFAULT '',
                record_state TEXT NOT NULL DEFAULT 'OK',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(collection_id, record_number),
                FOREIGN KEY(collection_id) REFERENCES collections(id)
            )"""
        )

        existing = {
            str(row["name"])
            for row in connection.execute("PRAGMA table_info(records)").fetchall()
        }
        migrations = {
            "mineral_name": "ALTER TABLE records ADD COLUMN mineral_name TEXT NOT NULL DEFAULT ''",
            "mineral_2": "ALTER TABLE records ADD COLUMN mineral_2 TEXT NOT NULL DEFAULT ''",
            "mineral_3": "ALTER TABLE records ADD COLUMN mineral_3 TEXT NOT NULL DEFAULT ''",
            "species": "ALTER TABLE records ADD COLUMN species TEXT NOT NULL DEFAULT ''",
            "mineral_class": "ALTER TABLE records ADD COLUMN mineral_class TEXT NOT NULL DEFAULT ''",
            "chemical_formula": "ALTER TABLE records ADD COLUMN chemical_formula TEXT NOT NULL DEFAULT ''",
            "internet_link": "ALTER TABLE records ADD COLUMN internet_link TEXT NOT NULL DEFAULT ''",
            "site_internet_link": "ALTER TABLE records ADD COLUMN site_internet_link TEXT NOT NULL DEFAULT ''",
            "crystal_system": "ALTER TABLE records ADD COLUMN crystal_system TEXT NOT NULL DEFAULT ''",
            "luminescence": "ALTER TABLE records ADD COLUMN luminescence TEXT NOT NULL DEFAULT 'Non'",
            "luminescence_intensity": "ALTER TABLE records ADD COLUMN luminescence_intensity TEXT NOT NULL DEFAULT 'Aucune'",
            "fluorescence_color": "ALTER TABLE records ADD COLUMN fluorescence_color TEXT NOT NULL DEFAULT 'Aucune'",
            "site_name": "ALTER TABLE records ADD COLUMN site_name TEXT NOT NULL DEFAULT ''",
            "deposit": "ALTER TABLE records ADD COLUMN deposit TEXT NOT NULL DEFAULT ''",
            "department": "ALTER TABLE records ADD COLUMN department TEXT NOT NULL DEFAULT ''",
            "region": "ALTER TABLE records ADD COLUMN region TEXT NOT NULL DEFAULT ''",
            "country": "ALTER TABLE records ADD COLUMN country TEXT NOT NULL DEFAULT ''",
            "box_type": "ALTER TABLE records ADD COLUMN box_type TEXT NOT NULL DEFAULT ''",
            "category": "ALTER TABLE records ADD COLUMN category TEXT NOT NULL DEFAULT ''",
            "contact": "ALTER TABLE records ADD COLUMN contact TEXT NOT NULL DEFAULT ''",
            "specimen_shape": "ALTER TABLE records ADD COLUMN specimen_shape TEXT NOT NULL DEFAULT ''",
            "specimen_color": "ALTER TABLE records ADD COLUMN specimen_color TEXT NOT NULL DEFAULT ''",
            "quality": "ALTER TABLE records ADD COLUMN quality TEXT NOT NULL DEFAULT ''",
            "description": "ALTER TABLE records ADD COLUMN description TEXT NOT NULL DEFAULT ''",
            "minimum_magnification": "ALTER TABLE records ADD COLUMN minimum_magnification TEXT NOT NULL DEFAULT ''",
            "growth": "ALTER TABLE records ADD COLUMN growth TEXT NOT NULL DEFAULT ''",
            "type_locality": "ALTER TABLE records ADD COLUMN type_locality TEXT NOT NULL DEFAULT ''",
            "acquisition_date": "ALTER TABLE records ADD COLUMN acquisition_date TEXT NOT NULL DEFAULT ''",
            "origin": "ALTER TABLE records ADD COLUMN origin TEXT NOT NULL DEFAULT ''",
            "place": "ALTER TABLE records ADD COLUMN place TEXT NOT NULL DEFAULT ''",
            "box_count": "ALTER TABLE records ADD COLUMN box_count TEXT NOT NULL DEFAULT ''",
            "price": "ALTER TABLE records ADD COLUMN price TEXT NOT NULL DEFAULT ''",
            "total_cost": "ALTER TABLE records ADD COLUMN total_cost TEXT NOT NULL DEFAULT ''",
            "photo_data": "ALTER TABLE records ADD COLUMN photo_data BLOB",
            "photo_format": "ALTER TABLE records ADD COLUMN photo_format TEXT NOT NULL DEFAULT ''",
            "record_state": "ALTER TABLE records ADD COLUMN record_state TEXT NOT NULL DEFAULT 'OK'",
        }
        for column, sql in migrations.items():
            if column not in existing:
                connection.execute(sql)

        connection.execute(
            """CREATE TABLE IF NOT EXISTS record_extra_photos(
                record_id INTEGER NOT NULL,
                slot_key TEXT NOT NULL,
                photo_data BLOB,
                photo_format TEXT NOT NULL DEFAULT '',
                PRIMARY KEY(record_id, slot_key),
                FOREIGN KEY(record_id) REFERENCES records(id) ON DELETE CASCADE
            )"""
        )

    @staticmethod
    def _select_columns() -> str:
        return (
            "id, collection_id, record_number, mineral_name, mineral_2, mineral_3, species, "
            "mineral_class, chemical_formula, internet_link, site_internet_link, crystal_system, luminescence, "
            "luminescence_intensity, fluorescence_color, site_name, deposit, "
            "department, region, country, box_type, category, contact, "
            "specimen_shape, specimen_color, quality, description, minimum_magnification, growth, "
            "type_locality, acquisition_date, origin, place, box_count, price, total_cost, "
            "photo_data, photo_format, record_state, created_at, updated_at"
        )

    def get_record(self, record_id: int, collection_id: int | None = None) -> dict[str, Any] | None:
        """Relit une fiche complète, photo comprise."""
        with self._connect() as connection:
            self._ensure_table(connection)
            if collection_id is None:
                row = connection.execute(
                    f"SELECT {self._select_columns()} FROM records WHERE id = ?",
                    (int(record_id),),
                ).fetchone()
            else:
                row = connection.execute(
                    f"""SELECT {self._select_columns()} FROM records
                        WHERE id = ? AND collection_id = ?""",
                    (int(record_id), int(collection_id)),
                ).fetchone()
        return dict(row) if row is not None else None

    @classmethod
    def transferable_fields(cls) -> set[str]:
        """Champs de fiche que ce Core sait recevoir depuis une autre collection."""
        return set(cls.FIELD_DEFAULTS) | {"photo_data", "photo_format"}

    @staticmethod
    def _source_model_fields(source_record: dict[str, Any]) -> set[str]:
        raw = source_record.get("__mm3_model_fields__")
        if isinstance(raw, (list, tuple, set)):
            fields = {str(key) for key in raw}
        else:
            fields = {str(key) for key in source_record}
        if "photo_data" in fields:
            fields.add("photo_format")
        fields.discard("species")
        return fields

    def _destination_model_fields(self, collection_id: int) -> set[str]:
        fields = ModelManager(self.db_path).visible_fields(int(collection_id))
        if "photo_data" in fields:
            fields.add("photo_format")
        fields.discard("record_number")
        fields.discard("species")
        return fields & self.transferable_fields()

    def transfer_compatibility(
        self, source_record: dict[str, Any], *, replacing: bool, collection_id: int
    ) -> dict[str, list[str]]:
        """Décrit les écarts entre les modèles A et B sans bloquer le transfert."""
        source = self._source_model_fields(source_record) & self.transferable_fields()
        destination = self._destination_model_fields(int(collection_id))
        ignored = sorted(source - destination)
        destination_only = sorted(destination - source)
        return {
            "ignored": ignored,
            "preserved": destination_only if replacing else [],
            "defaulted": destination_only if not replacing else [],
        }

    @staticmethod
    def _parse_transfer_number(value: Any) -> float:
        raw = str(value or "").strip().replace("€", "").replace(" ", "").replace(",", ".")
        try:
            return float(raw) if raw else 0.0
        except ValueError:
            return 0.0

    @classmethod
    def _recalculate_transfer_total(cls, values: dict[str, Any]) -> None:
        """Le coût total est calculé dans la destination, jamais copié figé."""
        count = cls._parse_transfer_number(values.get("box_count", 0))
        price = cls._parse_transfer_number(values.get("price", 0))
        values["total_cost"] = f"{count * price:.2f}".replace(".", ",") + " €"

    def paste_record_into(
        self,
        target_record_id: int,
        collection_id: int,
        source_record: dict[str, Any],
    ) -> dict[str, Any]:
        """Colle les seuls champs communs sans effacer les champs propres à B."""
        target = self.get_record(target_record_id, collection_id)
        if target is None:
            raise ValueError("La fiche cible n'existe plus.")

        # Point essentiel de 017.2.0 : partir des valeurs de la destination puis
        # écraser uniquement les champs réellement présents dans la fiche source.
        # Ainsi un futur modèle B peut posséder des champs absents du modèle A
        # sans qu'un collage ne les efface.
        values = {
            key: str(target.get(key, default) if target.get(key, None) is not None else default).strip()
            for key, default in self.FIELD_DEFAULTS.items()
        }
        source_model = self._source_model_fields(source_record)
        destination_model = self._destination_model_fields(int(collection_id))
        transferable_now = source_model & destination_model
        for key in self.FIELD_DEFAULTS:
            if key in transferable_now and key in source_record and key not in {"total_cost", "species"}:
                values[key] = str(source_record.get(key, "") or "").strip()

        # Colonne historique : elle reste le miroir du Nom sans devenir un champ de modèle.
        values["species"] = str(values.get("mineral_name", "") or "").strip()
        if not values.get("record_state"):
            values["record_state"] = "OK"
        self._recalculate_transfer_total(values)

        # La photo suit les modèles : elle ne voyage que si Photo existe dans A et B.
        photo_data = target.get("photo_data")
        photo_format = target.get("photo_format", "")
        if "photo_data" in transferable_now and "photo_data" in source_record:
            photo_data = bytes(source_record.get("photo_data") or b"") or None
            photo_format = str(source_record.get("photo_format", "") or "")

        return self.update_record(
            int(target_record_id),
            values,
            bytes(photo_data or b"") or None,
            str(photo_format or ""),
        )

    def paste_record_as_new(
        self,
        collection_id: int,
        source_record: dict[str, Any],
    ) -> dict[str, Any]:
        """Crée une fiche B puis copie uniquement les champs compris par B."""
        created = self.create_record(int(collection_id))
        try:
            return self.paste_record_into(
                int(created["id"]),
                int(collection_id),
                source_record,
            )
        except Exception:
            with self._connect() as connection:
                connection.execute(
                    "DELETE FROM records WHERE id = ? AND collection_id = ?",
                    (int(created["id"]), int(collection_id)),
                )
            raise


    def list_record_navigation(self, collection_id: int) -> list[dict[str, Any]]:
        """20.31 : index de navigation strictement minimal, sans champs volumineux.

        Les fiches sont relues intégralement par get_record() lors de l'affichage.
        Les autres consommateurs de list_records_light restent inchangés.
        """
        import time
        from performance_diagnostic import write
        start = time.perf_counter()
        with self._connect() as connection:
            self._ensure_table(connection)
            rows = connection.execute(
                "SELECT id, collection_id, record_number FROM records "
                "WHERE collection_id = ? ORDER BY record_number",
                (int(collection_id),),
            ).fetchall()
        result = [dict(row) for row in rows]
        for row in result:
            row["__mm3_full_loaded__"] = False
        write('SQL NAVIGATION minimale : %.3f s | fiches=%d' % (
            time.perf_counter() - start, len(result)))
        return result

    def list_records_light(self, collection_id: int) -> list[dict[str, Any]]:
        """Liste de navigation sans charger toutes les photos BLOB.

        La photo de la fiche courante sera chargée à la demande par get_record().
        """
        # 20.27 : mesures uniquement, sans modifier les requêtes ni les données.
        import time as _perf_time
        from performance_diagnostic import write as _perf_write
        _perf_start = _perf_time.perf_counter()
        _perf_prev = _perf_start

        def _perf_step(label, extra=''):
            nonlocal _perf_prev
            now = _perf_time.perf_counter()
            _perf_write('SQL LISTE %-27s +%.3f s | total %.3f s%s' % (
                label, now - _perf_prev, now - _perf_start, extra))
            _perf_prev = now

        columns = self._select_columns().replace(
            "photo_data, photo_format,",
            "NULL AS photo_data, photo_format,"
        )
        _perf_step('préparation colonnes')
        with self._connect() as connection:
            _perf_step('connexion SQLite')
            self._ensure_table(connection)
            _perf_step('vérification table')
            # 20.29 : diagnostic en lecture seule du plan et du volume SQLite.
            # Aucune modification de requête, d'index, de cache ou de données.
            try:
                from pathlib import Path as _DiagPath
                _db_size = _DiagPath(self.db_path).stat().st_size
                _page_size = connection.execute('PRAGMA page_size').fetchone()[0]
                _page_count = connection.execute('PRAGMA page_count').fetchone()[0]
                _perf_write('SQL DIAG fichier=%d octets | pages=%d | taille_page=%d' % (
                    _db_size, _page_count, _page_size))
                _plan = connection.execute(
                    f'EXPLAIN QUERY PLAN SELECT {columns} FROM records WHERE collection_id = ? ORDER BY record_number',
                    (int(collection_id),)
                ).fetchall()
                for _plan_row in _plan:
                    _perf_write('SQL DIAG plan: ' + str(tuple(_plan_row)))
            except Exception as _diag_error:
                _perf_write('SQL DIAG indisponible: ' + str(_diag_error))
            # 20.30 : mesurer la lecture d'une liste minimale sans toucher à la
            # liste réellement utilisée par Fiche, Tableau, États et recherches.
            # Deux SELECT indépendants : l'un lit seulement les identifiants,
            # l'autre conserve strictement le comportement existant.
            try:
                _narrow_start = _perf_time.perf_counter()
                _narrow_rows = connection.execute(
                    "SELECT id, record_number FROM records "
                    "WHERE collection_id = ? ORDER BY record_number",
                    (int(collection_id),),
                ).fetchall()
                _perf_write('SQL DIAG liste minimale id+numero : %.3f s | lignes=%d' % (
                    _perf_time.perf_counter() - _narrow_start, len(_narrow_rows)))
                del _narrow_rows
            except Exception as _narrow_error:
                _perf_write('SQL DIAG liste minimale indisponible: ' + str(_narrow_error))
            _perf_step('diagnostic plan SQLite')
            _cursor = connection.execute(
                f"""SELECT {columns}
                    FROM records
                    WHERE collection_id = ?
                    ORDER BY record_number""",
                (int(collection_id),),
            )
            _perf_step('exécution SELECT')
            rows = _cursor.fetchall()
            _perf_step('fetchall', ' | lignes=%d' % len(rows))
        _perf_step('fermeture connexion')
        result = [dict(row) for row in rows]
        _perf_step('conversion dictionnaires')
        for row in result:
            row["__mm3_full_loaded__"] = False
        _perf_step('marquage fiches légères', ' | fiches=%d' % len(result))
        return result

    def list_record_referential_values(self, collection_id: int) -> list[dict[str, Any]]:
        """20.35: index couvrant les champs référentiels, sans lire les photos.

        La première création de l'index peut être lente sur une grande base ;
        ensuite SQLite peut lire les valeurs directement depuis l'index.
        La vérification complète de toutes les fiches reste inchangée.
        """
        import time
        from core.field_catalog import REFERENTIAL_BY_FIELD
        from performance_diagnostic import write
        start = time.perf_counter()
        allowed = set(self._select_columns().replace(' ', '').split(','))
        fields = [key for key in REFERENTIAL_BY_FIELD if key in allowed]
        columns = ', '.join(['id', *fields])
        index_name = 'idx_gskol_ref_cover_2035'
        with self._connect() as connection:
            self._ensure_table(connection)
            index_start = time.perf_counter()
            exists = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='index' AND name=?",
                (index_name,),
            ).fetchone() is not None
            if not exists:
                # Les 23 champs restent dans l'index, mais jamais les photos.
                quoted = ', '.join('"' + key + '"' for key in fields)
                connection.execute(
                    f'CREATE INDEX IF NOT EXISTS "{index_name}" '
                    f'ON records(collection_id, {quoted})'
                )
                connection.commit()
            write('SQL REFERENTIELS index : %.3f s | creation=%s' % (
                time.perf_counter() - index_start, not exists))
            query_start = time.perf_counter()
            # L'index couvre toutes les colonnes de la requête, id inclus
            # (clé ROWID implicite des index SQLite).
            rows = connection.execute(
                f"SELECT {columns} FROM records INDEXED BY {index_name} "
                "WHERE collection_id = ?",
                (int(collection_id),),
            ).fetchall()
            write('SQL REFERENTIELS lecture index : %.3f s | fiches=%d | champs=%d' % (
                time.perf_counter() - query_start, len(rows), len(fields)))
        result = [dict(row) for row in rows]
        write('SQL REFERENTIELS fermeture : %.3f s | fiches=%d | champs=%d' % (
            time.perf_counter() - start, len(result), len(fields)))
        return result

    def list_records(self, collection_id: int) -> list[dict[str, Any]]:
        with self._connect() as connection:
            self._ensure_table(connection)
            rows = connection.execute(
                f"""SELECT {self._select_columns()}
                    FROM records
                    WHERE collection_id = ?
                    ORDER BY record_number""",
                (collection_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def search_minerals(self, collection_id: int, query: str = "") -> list[dict[str, Any]]:
        """Recherche instantanée sur Nom, Minéral 2 et Minéral 3.

        La comparaison utilise ``casefold`` afin de rester insensible à la casse,
        y compris pour les caractères accentués. Une recherche vide retourne
        toutes les fiches de la collection, dans l'ordre des numéros.
        """
        with self._connect() as connection:
            self._ensure_table(connection)
            rows = connection.execute(
                """SELECT id, collection_id, record_number, mineral_name, mineral_2, mineral_3
                   FROM records
                   WHERE collection_id = ?
                   ORDER BY record_number""",
                (int(collection_id),),
            ).fetchall()

        records = [dict(row) for row in rows]
        normalized_query = str(query or "").strip().casefold()
        if not normalized_query:
            return records

        return [
            record
            for record in records
            if normalized_query in str(record.get("mineral_name", "")).casefold()
            or normalized_query in str(record.get("mineral_2", "")).casefold()
            or normalized_query in str(record.get("mineral_3", "")).casefold()
        ]

    def search_records(
        self, collection_id: int, criteria: dict[str, str],
        operators: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        """Recherche multicritère instantanée.

        Tous les critères actifs sont combinés par ET. Chaque champ peut utiliser
        l'opérateur contient, commence_par, exactement ou termine_par.
        """
        fields = (
            "mineral_name", "mineral_2", "mineral_3", "mineral_class",
            "crystal_system", "country", "department", "specimen_color",
            "quality", "record_state",
        )
        normalized = {
            key: str(criteria.get(key, "") or "").strip().casefold()
            for key in fields
        }
        operators = operators or {}

        def matches(value: Any, query: str, operator: str) -> bool:
            if not query:
                return True
            text = str(value or "").strip().casefold()
            if operator == "commence_par":
                return text.startswith(query)
            if operator == "exactement":
                return text == query
            if operator == "termine_par":
                return text.endswith(query)
            return query in text

        with self._connect() as connection:
            self._ensure_table(connection)
            rows = connection.execute(
                f"""SELECT {self._select_columns()} FROM records
                    WHERE collection_id = ? ORDER BY record_number""",
                (int(collection_id),),
            ).fetchall()
        result = []
        for row in rows:
            record = dict(row)
            if all(matches(record.get(key, ""), query, operators.get(key, "contient"))
                   for key, query in normalized.items()):
                result.append(record)
        return result

    def identification_for_name(self, collection_id: int, mineral_name: str, exclude_id: int | None = None) -> dict[str, Any] | None:
        """Retourne la fiche connue la plus récente pour une espèce donnée."""
        value = str(mineral_name or "").strip()
        if not value:
            return None
        with self._connect() as connection:
            self._ensure_table(connection)
            sql = f"""SELECT {self._select_columns()} FROM records
                      WHERE collection_id = ? AND mineral_name = ? COLLATE NOCASE"""
            params: list[Any] = [int(collection_id), value]
            if exclude_id is not None:
                sql += " AND id <> ?"; params.append(int(exclude_id))
            sql += " ORDER BY updated_at DESC, record_number DESC LIMIT 1"
            row = connection.execute(sql, params).fetchone()
        return dict(row) if row else None

    def location_for_site(self, collection_id: int, site_name: str, exclude_id: int | None = None) -> dict[str, Any] | None:
        """Retourne la localisation connue la plus récente pour un site donné."""
        value = str(site_name or "").strip()
        if not value:
            return None
        with self._connect() as connection:
            self._ensure_table(connection)
            sql = f"""SELECT {self._select_columns()} FROM records
                      WHERE collection_id = ? AND site_name = ? COLLATE NOCASE"""
            params: list[Any] = [int(collection_id), value]
            if exclude_id is not None:
                sql += " AND id <> ?"; params.append(int(exclude_id))
            sql += " ORDER BY updated_at DESC, record_number DESC LIMIT 1"
            row = connection.execute(sql, params).fetchone()
        return dict(row) if row else None

    def extra_photos(self, record_id: int) -> dict[str, dict[str, Any]]:
        with self._connect() as connection:
            self._ensure_table(connection)
            rows = connection.execute(
                "SELECT slot_key, photo_data, photo_format FROM record_extra_photos WHERE record_id = ?",
                (int(record_id),),
            ).fetchall()
        return {
            str(row["slot_key"]): {
                "photo_data": bytes(row["photo_data"] or b""),
                "photo_format": str(row["photo_format"] or ""),
            }
            for row in rows
        }

    def set_extra_photo(
        self, record_id: int, slot_key: str, photo_data: bytes | None, photo_format: str = ""
    ) -> None:
        slot_key = str(slot_key or "").strip()
        if not slot_key:
            return
        with self._connect() as connection:
            self._ensure_table(connection)
            if not photo_data:
                connection.execute(
                    "DELETE FROM record_extra_photos WHERE record_id = ? AND slot_key = ?",
                    (int(record_id), slot_key),
                )
                return
            connection.execute(
                """INSERT INTO record_extra_photos(record_id, slot_key, photo_data, photo_format)
                   VALUES(?, ?, ?, ?)
                   ON CONFLICT(record_id, slot_key)
                   DO UPDATE SET photo_data = excluded.photo_data, photo_format = excluded.photo_format""",
                (int(record_id), slot_key, sqlite3.Binary(photo_data), str(photo_format or "JPEG")),
            )

    def delete_extra_photo_slot_for_collection(self, collection_id: int, slot_key: str) -> None:
        with self._connect() as connection:
            self._ensure_table(connection)
            connection.execute(
                """DELETE FROM record_extra_photos
                   WHERE slot_key = ?
                   AND record_id IN (SELECT id FROM records WHERE collection_id = ?)""",
                (str(slot_key), int(collection_id)),
            )

    def create_record(self, collection_id: int) -> dict[str, Any]:
        """Crée une fiche à partir des valeurs par défaut officielles.

        La requête INSERT est construite dynamiquement depuis FIELD_DEFAULTS :
        ajouter un champ au modèle ne peut donc plus désynchroniser le nombre
        de colonnes et le nombre de valeurs SQL.
        """
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as connection:
            self._ensure_table(connection)
            next_number = connection.execute(
                "SELECT COALESCE(MAX(record_number), 0) + 1 FROM records WHERE collection_id = ?",
                (int(collection_id),),
            ).fetchone()[0]

            values = dict(self.FIELD_DEFAULTS)
            # Colonne historique conservée pour compatibilité.
            values["species"] = str(values.get("mineral_name", ""))

            field_names = list(values)
            columns = ["collection_id", "record_number", *field_names, "created_at", "updated_at"]
            placeholders = ", ".join("?" for _ in columns)
            sql = f"INSERT INTO records({', '.join(columns)}) VALUES ({placeholders})"
            params = [
                int(collection_id),
                int(next_number),
                *(values[name] for name in field_names),
                now,
                now,
            ]
            cursor = connection.execute(sql, params)
            record_id = int(cursor.lastrowid)
            row = connection.execute(
                f"SELECT {self._select_columns()} FROM records WHERE id = ?",
                (record_id,),
            ).fetchone()
        if row is None:
            raise ValueError("La fiche créée ne peut pas être relue.")
        return dict(row)


    TABLE_EDITABLE_FIELDS = {
        "mineral_name", "mineral_2", "mineral_3", "mineral_class",
        "chemical_formula", "internet_link", "site_internet_link",
        "crystal_system", "luminescence", "luminescence_intensity",
        "fluorescence_color", "site_name", "deposit", "department",
        "region", "country", "box_type", "category", "contact",
        "specimen_shape", "specimen_color", "quality", "description",
        "minimum_magnification", "growth", "type_locality", "acquisition_date",
        "origin", "place", "box_count", "price", "total_cost", "record_state",
    }

    def update_table_field(
        self, record_id: int, collection_id: int, field: str, value: str
    ) -> dict[str, Any]:
        """Modifie une cellule depuis la Vue Tableau.

        Le numéro de fiche et les données photo sont volontairement exclus.
        Les deux champs maîtres (Nom et Site) recopient le bloc dépendant de la
        valeur connue choisie, comme dans la fiche MM3.
        """
        field = str(field or "")
        if field not in self.TABLE_EDITABLE_FIELDS:
            raise ValueError("Ce champ ne peut pas être modifié depuis le Tableau.")

        clean = str(value or "").strip()
        if field in ("mineral_name", "mineral_2", "mineral_3"):
            clean = clean.upper()

        # Lire d'abord la fiche courante : sélectionner à nouveau la même
        # valeur ne doit jamais vider un bloc maître qui serait unique.
        with self._connect() as connection:
            self._ensure_table(connection)
            current_row = connection.execute(
                f"SELECT {self._select_columns()} FROM records WHERE id = ?",
                (int(record_id),),
            ).fetchone()
        if current_row is None:
            raise ValueError("La fiche à modifier n'existe plus.")
        current_record = dict(current_row)
        if int(current_record["collection_id"]) != int(collection_id):
            raise ValueError("Cette fiche n'appartient pas à la collection ouverte.")
        current_value = str(current_record.get(field, "") or "").strip()
        if current_value.casefold() == clean.casefold():
            return current_record

        now = datetime.now().isoformat(timespec="seconds")
        assignments: dict[str, str] = {field: clean}

        if field == "mineral_name":
            source = self.identification_for_name(
                int(collection_id), clean, exclude_id=int(record_id)
            ) if clean else None
            dependent = (
                "mineral_class", "chemical_formula", "crystal_system",
                "internet_link", "luminescence",
                "luminescence_intensity", "fluorescence_color",
            )
            for key in dependent:
                assignments[key] = str(source.get(key, "") if source else "").strip()
            assignments["species"] = clean

        elif field == "site_name":
            source = self.location_for_site(
                int(collection_id), clean, exclude_id=int(record_id)
            ) if clean else None
            dependent = (
                "deposit", "department", "region", "country",
                "category", "site_internet_link",
            )
            for key in dependent:
                assignments[key] = str(source.get(key, "") if source else "").strip()

        with self._connect() as connection:
            self._ensure_table(connection)
            columns = list(assignments)
            sql = "UPDATE records SET " + ", ".join(f"{key} = ?" for key in columns)
            sql += ", updated_at = ? WHERE id = ?"
            params = [assignments[key] for key in columns] + [now, int(record_id)]
            connection.execute(sql, params)
            row = connection.execute(
                f"SELECT {self._select_columns()} FROM records WHERE id = ?",
                (int(record_id),),
            ).fetchone()

        if row is None:
            raise ValueError("La fiche à modifier n'existe plus.")
        return dict(row)

    def clear_record_to_free(self, record_id: int, collection_id: int) -> dict[str, Any]:
        """Vide complètement une fiche tout en conservant son N° et son identité technique."""
        now = datetime.now().isoformat(timespec="seconds")
        clear_fields = [key for key in self.FIELD_DEFAULTS if key != "record_state"]
        # Les valeurs par défaut de luminescence ne conviennent pas ici : une
        # fiche Libre doit être réellement vide et ne pas polluer les résultats.
        assignments = {key: "" for key in clear_fields}
        assignments["species"] = ""
        assignments["record_state"] = "Libre"
        with self._connect() as connection:
            self._ensure_table(connection)
            row = connection.execute(
                "SELECT collection_id FROM records WHERE id = ?", (int(record_id),)
            ).fetchone()
            if row is None:
                raise ValueError("La fiche à vider n'existe plus.")
            if int(row["collection_id"]) != int(collection_id):
                raise ValueError("Cette fiche n'appartient pas à la collection ouverte.")
            columns = list(assignments)
            sql = "UPDATE records SET " + ", ".join(f"{key} = ?" for key in columns)
            sql += ", photo_data = NULL, photo_format = '', updated_at = ? WHERE id = ?"
            params = [assignments[key] for key in columns] + [now, int(record_id)]
            connection.execute(sql, params)
            connection.execute(
                "DELETE FROM record_extra_photos WHERE record_id = ?",
                (int(record_id),),
            )
            self._ensure_custom_values_table(connection)
            connection.execute(
                "DELETE FROM record_custom_values WHERE record_id = ?",
                (int(record_id),),
            )
            updated = connection.execute(
                f"SELECT {self._select_columns()} FROM records WHERE id = ?",
                (int(record_id),),
            ).fetchone()
        if updated is None:
            raise ValueError("La fiche vidée ne peut pas être relue.")
        return dict(updated)

    def tail_records_deletable(self, record_ids: list[int], collection_id: int) -> tuple[bool, str]:
        """Vérifie que les fiches choisies sont Libres, réellement vides et forment la fin de collection."""
        ids = sorted({int(x) for x in record_ids if int(x) > 0})
        if not ids:
            return False, "Aucune fiche sélectionnée."
        with self._connect() as connection:
            self._ensure_table(connection)
            self._ensure_custom_values_table(connection)
            rows = connection.execute(
                f"SELECT {self._select_columns()} FROM records WHERE collection_id=? ORDER BY record_number",
                (int(collection_id),),
            ).fetchall()
            all_rows = [dict(r) for r in rows]
            by_id = {int(r["id"]): r for r in all_rows}
            if any(i not in by_id for i in ids):
                return False, "Une fiche sélectionnée n'existe plus."
            selected = sorted((by_id[i] for i in ids), key=lambda r:int(r["record_number"]))
            numbers = [int(r["record_number"]) for r in selected]
            max_num = max((int(r["record_number"]) for r in all_rows), default=0)
            if numbers != list(range(numbers[0], max_num + 1)):
                return False, "Seules des fiches consécutives situées tout à la fin de la collection peuvent être supprimées."
            for r in selected:
                if str(r.get("record_state","") or "").strip().casefold() != "libre":
                    return False, f"La fiche N° {r['record_number']} n'est pas à l'état Libre."
                for key in self.FIELD_DEFAULTS:
                    if key == "record_state":
                        continue
                    if str(r.get(key, "") or "").strip():
                        return False, f"La fiche N° {r['record_number']} n'est pas vide."
                if bytes(r.get("photo_data") or b""):
                    return False, f"La fiche N° {r['record_number']} contient encore une photo."
                cv = connection.execute("SELECT 1 FROM record_custom_values WHERE record_id=? LIMIT 1", (int(r["id"]),)).fetchone()
                ep = connection.execute("SELECT 1 FROM record_extra_photos WHERE record_id=? LIMIT 1", (int(r["id"]),)).fetchone()
                if cv or ep:
                    return False, f"La fiche N° {r['record_number']} contient encore des données."
        return True, ""

    def delete_tail_records(self, record_ids: list[int], collection_id: int) -> int:
        ok, reason = self.tail_records_deletable(record_ids, collection_id)
        if not ok:
            raise ValueError(reason)
        ids = sorted({int(x) for x in record_ids if int(x) > 0})
        with self._connect() as connection:
            self._ensure_table(connection)
            placeholders = ",".join("?" for _ in ids)
            connection.execute(
                f"DELETE FROM records WHERE collection_id=? AND id IN ({placeholders})",
                [int(collection_id), *ids],
            )
        return len(ids)

    def update_record(
        self, record_id: int, data: dict[str, str],
        photo_data: bytes | None = None, photo_format: str = ""
    ) -> dict[str, Any]:
        """Enregistre une fiche avec un UPDATE construit depuis FIELD_DEFAULTS.

        Cette construction dynamique empêche tout décalage entre le nombre
        de champs SQL et le nombre de valeurs lorsqu'un nouveau champ est ajouté.
        """
        now = datetime.now().isoformat(timespec="seconds")
        values = {
            key: str(data.get(key, default)).strip()
            for key, default in self.FIELD_DEFAULTS.items()
        }
        if not values["record_state"]:
            values["record_state"] = "OK"

        # Compatibilité historique : species suit toujours le nom principal.
        values["species"] = str(values.get("mineral_name", "") or "")

        with self._connect() as connection:
            self._ensure_table(connection)

            assignments = [f"{field} = ?" for field in values]
            assignments.extend([
                "photo_data = ?",
                "photo_format = ?",
                "updated_at = ?",
            ])
            params = [
                *(values[field] for field in values),
                sqlite3.Binary(photo_data) if photo_data else None,
                str(photo_format or ""),
                now,
                int(record_id),
            ]
            connection.execute(
                f"UPDATE records SET {', '.join(assignments)} WHERE id = ?",
                params,
            )
            row = connection.execute(
                f"SELECT {self._select_columns()} FROM records WHERE id = ?",
                (int(record_id),),
            ).fetchone()

        if row is None:
            raise ValueError("La fiche à enregistrer n'existe plus.")
        return dict(row)
