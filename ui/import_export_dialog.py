#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Module Import / Export de MM3 — analyse initiale d'une base Access.

Cette fenêtre est indépendante de toute collection MM3. Elle permet de choisir
une base Microsoft Access puis d'en lire uniquement la structure (tables,
colonnes et nombre de lignes) avant toute décision concernant la destination.
Aucune donnée n'est écrite dans MM3 à cette étape.

11.4.39.22 — import Access : référentiels complets, lecture groupée et recherche par préfixe.
"""

from __future__ import annotations

import base64
from contextlib import closing
import csv
import io
import json
import os
import re
from pathlib import Path
import subprocess
import shutil
import sqlite3
import struct
import tempfile
import time
import xml.etree.ElementTree as ET
import unicodedata
import zipfile
from datetime import datetime, timedelta

from PySide6.QtCore import Qt, QTimer, QAbstractTableModel, QModelIndex
from PySide6.QtGui import QColor
from core.i18n import tr, translate_widget_tree
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QFormLayout,
    QInputDialog,
    QLineEdit,
    QMenu,
    QProgressDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QComboBox,
    QCheckBox,
    QRadioButton,
    QButtonGroup,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QTableView,
    QTabWidget,
    QStackedWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QSizePolicy,
    QWidget,
)

from core.collection_manager import CollectionManager
from core.backup_manager import create_native_workspace_backup, workspace_backup_inventory, create_selected_database_backup
from core.database import DatabaseManager
from core.record_manager import RecordManager
from core.model_manager import ModelManager
from core.referential_manager import ReferentialManager
from core.collection_templates import apply_official_template_database
from core.field_catalog import FIELD_BY_KEY
from core.collection_folders import CollectionFolderStore, UNCLASSIFIED
from core.model_library import write_model, read_model, library_root, build_field_manifest, collect_model_field_keys, remap_model_payload
from ui.model_library_dialog import choose_model_save_path, choose_model_open_path
from core.settings import preferred_backup_directory
from core.paths import WORKSPACE



class ExplicitImportConfirmDialog(QDialog):
    """Confirmation d'import sans bouton par défaut ni validation par Entrée.

    11.7.67 — une action destructive / longue doit résulter d'un clic explicite.
    """

    def __init__(self, collection_name: str, rows: int | None, parent=None, language: str | None = None) -> None:
        super().__init__(parent)
        self.language = str(language or getattr(parent, "language", "fr") or "fr")
        self.setWindowTitle(tr("Lancer l’import réel ?", self.language))
        self.setModal(True)
        self.resize(500, 190)

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 18)
        root.setSpacing(16)

        _rows_text = str(rows) if isinstance(rows, int) else tr("les", self.language)
        text = QLabel(
            tr("Créer la collection « {collection} » et importer {rows} fiche(s) depuis Access ?<br><br>La base Access ne sera jamais modifiée.", self.language).format(
                collection=collection_name, rows=_rows_text
            )
        )
        text.setTextFormat(Qt.TextFormat.RichText)
        text.setWordWrap(True)
        root.addWidget(text)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        yes = QPushButton("Oui")
        no = QPushButton("Non")
        for button in (yes, no):
            button.setAutoDefault(False)
            button.setDefault(False)
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        yes.clicked.connect(self.accept)
        no.clicked.connect(self.reject)
        buttons.addWidget(yes)
        buttons.addWidget(no)
        root.addLayout(buttons)
        translate_widget_tree(self, self.language)

    def keyPressEvent(self, event) -> None:
        # Entrée / Retour ne doit jamais lancer ni valider l'import par inadvertance.
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            event.accept()
            return
        super().keyPressEvent(event)


class AccessImportDestinationDialog(QDialog):
    """Dernière confirmation avant un import réel dans une nouvelle collection."""

    def __init__(self, source_name: str, rows: int | None, fields: int, parent=None, source_kind: str = "Access", language: str | None = None) -> None:
        super().__init__(parent)
        self.language = str(language or getattr(parent, "language", "fr") or "fr")
        self.source_kind = str(source_kind or "source")
        self.setWindowTitle(tr("Créer la collection G-Skol et importer", self.language))
        self.resize(620, 330)

        root = QVBoxLayout(self)
        title = QLabel(tr("Essai grandeur nature — création de la collection", self.language))
        title.setStyleSheet("font-size: 19px; font-weight: 700;")
        root.addWidget(title)

        info = QLabel(tr("Source : <b>{source}</b> — {rows} fiche(s), {fields} champ(s).<br><br>G-Skol va créer une <b>nouvelle collection indépendante</b>. Les numéros de fiches G-Skol seront recréés automatiquement à partir de 1 ; un éventuel N° provenant de {kind} restera une donnée utilisateur ordinaire.", self.language).format(source=source_name, rows=(rows if isinstance(rows, int) else "?"), fields=fields, kind=self.source_kind))
        info.setTextFormat(Qt.TextFormat.RichText)
        info.setWordWrap(True)
        root.addWidget(info)

        form = QFormLayout()
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText(tr("Nom de la nouvelle collection", self.language))
        form.addRow(tr("Nom de la collection :", self.language), self.name_edit)
        root.addLayout(form)

        warning = QLabel(tr("Le fichier {kind} source reste strictement en lecture seule. En cas de problème, seule la nouvelle collection G-Skol créée par cet essai sera concernée.", self.language).format(kind=self.source_kind))
        warning.setWordWrap(True)
        warning.setStyleSheet("background:#FFF8E7; border:1px solid #D7C48A; padding:8px;")
        root.addWidget(warning)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton(tr("Annuler", self.language))
        cancel.setAutoDefault(False)
        cancel.setDefault(False)
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        self.go = QPushButton("Créer et importer")
        self.go.setAutoDefault(False)
        self.go.setDefault(False)
        self.go.setEnabled(False)
        self.name_edit.textChanged.connect(lambda s: self.go.setEnabled(bool(s.strip())))
        self.go.clicked.connect(self.accept)
        buttons.addWidget(self.go)
        root.addLayout(buttons)
        translate_widget_tree(self, self.language)

    def keyPressEvent(self, event) -> None:
        # 11.7.67 — aucune validation implicite par Entrée sur cet écran.
        # L'utilisateur doit cliquer explicitement sur « Créer et importer ».
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            event.accept()
            return
        super().keyPressEvent(event)

    def collection_name(self) -> str:
        return self.name_edit.text().strip()


class SafeTypeComboBox(QComboBox):
    """Liste sensible : la roulette ne change rien tant que la liste n'est pas ouverte."""

    def wheelEvent(self, event) -> None:
        try:
            opened = self.view().isVisible()
        except Exception:
            opened = False
        if opened:
            super().wheelEvent(event)
        else:
            event.ignore()


class NoWheelComboBox(QComboBox):
    """Liste de choix volontaire : la roulette ne change jamais la valeur."""

    def wheelEvent(self, event) -> None:
        event.accept()


def _import_model_field_choices(model_key: str) -> list[tuple[str, str]]:
    """Read the actual labels and keys from the chosen official model DB."""
    from core.collection_templates import OFFICIAL_TEMPLATE_FILES
    if not model_key or model_key == "blank" or model_key not in OFFICIAL_TEMPLATE_FILES:
        return []
    path = Path(__file__).resolve().parent.parent / "ModelesOfficiels" / f"{model_key}.db"
    if not path.is_file():
        return []
    result = []
    with sqlite3.connect(str(path)) as con:
        for key, label in con.execute("SELECT field_key, custom_label FROM collection_model_fields WHERE visible=1"):
            if key == "record_number":
                continue
            if key == "record_state":
                result.append(("Etat de la fiche", "record_state"))
                continue
            default = FIELD_BY_KEY[key].label if key in FIELD_BY_KEY else ""
            display = str(label or default).strip()
            # Never expose a technical custom_ identifier as a field label.
            if not display or display.startswith("custom_"):
                continue
            result.append((display, str(key)))
        for key, label in con.execute("SELECT field_key, label FROM collection_custom_fields"):
            if label and not str(label).startswith("custom_"):
                result.append((str(label), str(key)))
    return sorted(set(result), key=lambda pair: pair[0].casefold())



def _apply_gskol_model_layout_to_copy(copy_path: Path, collection_id: int,
                                       model_key: str, mapping: list[dict]) -> tuple[int, int]:
    """Apply a native model to a new copy, retaining original values and fields.

    Model files are opened read-only. Source values are never deleted. Destination
    values are populated only when empty; conflicting existing values abort the
    transaction rather than silently overwriting collection data.
    """
    from core.collection_templates import OFFICIAL_TEMPLATE_FILES
    filename = OFFICIAL_TEMPLATE_FILES.get(model_key)
    if not filename:
        raise ValueError("Le modèle natif sélectionné est introuvable.")
    model_path = Path(__file__).resolve().parent.parent / "ModelesOfficiels" / filename
    if not model_path.is_file():
        raise FileNotFoundError(str(model_path))
    with closing(sqlite3.connect(model_path.resolve().as_uri() + "?mode=ro", uri=True)) as model_db:
        model_db.row_factory = sqlite3.Row
        first = model_db.execute("SELECT id FROM collections ORDER BY id LIMIT 1").fetchone()
        if first is None:
            raise ValueError("Le modèle ne contient aucune collection.")
        template_id = int(first["id"])
        layout = {r["field_key"]: dict(r) for r in model_db.execute(
            "SELECT * FROM collection_model_fields WHERE collection_id=?", (template_id,))}
        custom_model = {r["field_key"]: dict(r) for r in model_db.execute(
            "SELECT * FROM collection_custom_fields WHERE collection_id=?", (template_id,))}
        appearance = model_db.execute(
            "SELECT sheet_background,field_styles,group_styles FROM collection_model_appearance WHERE collection_id=?",
            (template_id,)).fetchone()
    inverse = {}
    for item in mapping:
        if not item.get("import"):
            continue
        dest = str(item.get("destination") or "")
        if dest in ("", "__create__"):
            continue
        if dest in inverse:
            raise ValueError("Deux champs sources utilisent la destination : " + dest)
        inverse[dest] = str(item["source_key"])
    with closing(sqlite3.connect(str(copy_path))) as db:
        db.row_factory = sqlite3.Row
        db.execute("BEGIN IMMEDIATE")
        try:
            record_cols = {r[1] for r in db.execute("PRAGMA table_info(records)")}
            current = {r["field_key"]: dict(r) for r in db.execute(
                "SELECT * FROM collection_model_fields WHERE collection_id=?", (collection_id,))}
            custom = {r["field_key"]: dict(r) for r in db.execute(
                "SELECT * FROM collection_custom_fields WHERE collection_id=?", (collection_id,))}
            source_available = set(current) | set(custom) | record_cols
            if "record_custom_values" not in {
                r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}:
                db.execute("CREATE TABLE record_custom_values("
                           "record_id INTEGER NOT NULL, field_key TEXT NOT NULL,"
                           "value TEXT NOT NULL DEFAULT '', PRIMARY KEY(record_id,field_key))")
            record_ids = [r[0] for r in db.execute(
                "SELECT id FROM records WHERE collection_id=?", (collection_id,))]
            # Snapshot before writes: mappings can swap two source/destination keys.
            def read_values(key):
                if key in record_cols:
                    return {r["id"]: r["v"] for r in db.execute(
                        'SELECT id, "' + key + '" AS v FROM records WHERE collection_id=?',
                        (collection_id,))}
                return {r["record_id"]: r["value"] for r in db.execute(
                    "SELECT v.record_id,v.value FROM record_custom_values v "
                    "JOIN records r ON r.id=v.record_id "
                    "WHERE r.collection_id=? AND v.field_key=?",
                    (collection_id, key))}
            source_snapshots = {}
            for dest, src in inverse.items():
                if dest not in layout:
                    raise ValueError("Champ absent du modèle : " + dest)
                if src not in source_available:
                    raise ValueError("Champ source absent : " + src)
                source_snapshots[src] = read_values(src)
            # Ensure destination custom fields are defined in the new collection.
            for dest in inverse:
                if dest in custom_model and dest not in custom:
                    info = custom_model[dest]
                    cols = [k for k in info if k != "collection_id"]
                    db.execute(
                        "INSERT INTO collection_custom_fields(collection_id," +
                        ",".join(cols) + ") VALUES (" +
                        ",".join("?" for _ in range(len(cols)+1)) + ")",
                        (collection_id, *(info[k] for k in cols)))
                    custom[dest] = info
                elif dest not in record_cols and dest not in custom:
                    raise ValueError("Destination sans définition de champ : " + dest)
            # Copy values without destroying existing destination values.
            for dest, src in inverse.items():
                if dest == src:
                    continue
                source_values = source_snapshots[src]
                target_values = read_values(dest)
                updates = []
                for rid in record_ids:
                    value = source_values.get(rid)
                    if value is None or str(value).strip() == "":
                        continue
                    existing = target_values.get(rid)
                    if existing is not None and str(existing).strip() not in ("", "Non", "Aucune"):
                        if str(existing) != str(value):
                            source_label = next(
                                (str(item.get("source_label") or src) for item in mapping
                                 if str(item.get("source_key")) == src), src)
                            dest_label = str(layout[dest].get("custom_label") or
                                             (FIELD_BY_KEY[dest].label if dest in FIELD_BY_KEY else dest))
                            raise ValueError(
                                f"Correspondance à corriger pour la fiche n° {rid} :\n"
                                f"Champ source : « {source_label} » — valeur : « {value} »\n"
                                f"Champ du modèle : « {dest_label} » — valeur déjà présente : « {existing} »\n\n"
                                "Les deux valeurs sont différentes. Revenez au tableau de "
                                "correspondance et choisissez le bon champ source, ou "
                                "« Ne pas importer » pour cette ligne.\n"
                                "Aucune valeur n'a été écrasée.")
                        continue
                    updates.append((value, rid))
                if dest in record_cols:
                    db.executemany('UPDATE records SET "' + dest + '"=? WHERE id=?', updates)
                else:
                    db.executemany(
                        "INSERT INTO record_custom_values(record_id,field_key,value) "
                        "VALUES (?,?,?) ON CONFLICT(record_id,field_key) "
                        "DO UPDATE SET value=excluded.value",
                        ((rid, dest, str(value)) for value, rid in updates))
            # Keep old source fields in the palette. Position the *destination*
            # keys so the visible controls read the populated destination values.
            db.execute("UPDATE collection_model_fields SET visible=0 WHERE collection_id=?",
                       (collection_id,))
            cols = ("visible", "custom_label", "block_name", "position", "tab_position",
                    "visual_x", "visual_y", "visual_w", "visual_h")
            for dest in inverse:
                model_row = layout[dest]
                values = [model_row.get(col) for col in cols]
                if dest == "record_state":
                    values[cols.index("custom_label")] = "Etat de la fiche"
                if dest in current:
                    db.execute("UPDATE collection_model_fields SET " +
                               ",".join(f"{col}=?" for col in cols) +
                               " WHERE collection_id=? AND field_key=?",
                               (*values, collection_id, dest))
                else:
                    db.execute("INSERT INTO collection_model_fields "
                               "(collection_id,field_key," + ",".join(cols) + ") VALUES (" +
                               ",".join("?" for _ in range(len(cols)+2)) + ")",
                               (collection_id, dest, *values))
            if appearance:
                # Model appearance is copied, not edited.
                db.execute("INSERT INTO collection_model_appearance "
                           "(collection_id,sheet_background,field_styles,group_styles) VALUES (?,?,?,?) "
                           "ON CONFLICT(collection_id) DO UPDATE SET "
                           "sheet_background=excluded.sheet_background,"
                           "field_styles=excluded.field_styles,group_styles=excluded.group_styles",
                           (collection_id, appearance["sheet_background"],
                            appearance["field_styles"], appearance["group_styles"]))
            # La palette de cette copie montre le modèle et UNIQUEMENT les
            # nouveaux champs explicitement demandés. Les anciennes données
            # restent en base, sans suppression de colonnes ni de référentiels.
            palette_keys = {key for key, row in layout.items() if row.get("visible")} | {"record_number", "record_state", "photo_data"}
            palette_keys.update(str(item["source_key"]) for item in mapping
                                if item.get("import") and item.get("destination") == "__create__")
            palette_keys.update(str(item["source_key"]) for item in mapping
                                if item.get("import") and item.get("destination") not in ("", "__create__")
                                and str(item["source_key"]) == str(item["destination"]))
            appearance_row = db.execute(
                "SELECT group_styles FROM collection_model_appearance WHERE collection_id=?",
                (collection_id,)).fetchone()
            if appearance_row:
                groups = json.loads(appearance_row["group_styles"] or "{}")
                if not isinstance(groups, dict):
                    groups = {}
                meta = groups.setdefault("__mm3_layout__", {})
                if not isinstance(meta, dict):
                    meta = {}
                    groups["__mm3_layout__"] = meta
                meta["import_palette_keys"] = sorted(palette_keys)
                db.execute("UPDATE collection_model_appearance SET group_styles=? WHERE collection_id=?",
                           (json.dumps(groups, ensure_ascii=False), collection_id))
            # Contrôle de données, dans la même transaction : ne jamais
            # annoncer une importation réussie si les valeurs ne suivent pas.
            for dest, src in inverse.items():
                original = source_snapshots[src]
                transferred = read_values(dest)
                for rid in record_ids:
                    value = original.get(rid)
                    if value is None or str(value).strip() == "":
                        continue
                    actual = transferred.get(rid)
                    if actual is None or str(actual).strip() != str(value).strip():
                        raise ValueError(
                            f"Valeur non transférée pour {src} → {dest}, fiche {rid}. "
                            "La transaction est annulée.")
            db.commit()
            return len(inverse), len(current)
        except Exception:
            db.rollback()
            raise


class AccessFieldMappingDialog(QDialog):
    """Prépare la correspondance entre les champs Access et la future collection MM3.

    Cette étape reste indépendante du choix de la collection de destination :
    pour chaque champ source, l'utilisateur décide s'il sera importé, sous quel
    nom et avec quel type MM3. Aucune donnée n'est encore écrite.
    """

    MM3_TYPES = (
        "Texte",
        "Nombre",
        "Monétaire",
        "Date",
        "Bouton On / Off",
        "Lien (Internet ou autre)",
        "Photo / Image",
        "Liste / Référentiel — reconnu par MM3",
        "Liste / Référentiel — probable / à vérifier",
        "Liste / Référentiel — à paramétrer",
        "Calculé — reconnu par MM3",
        "Calculé — probable / à vérifier",
        "Calculé — à paramétrer",
    )

    def __init__(
        self,
        table: dict,
        parent: QWidget | None = None,
        preview_loader=None,
        language: str | None = None,
        model_key: str | None = None,
    ) -> None:
        super().__init__(parent)
        # La langue d’affichage est indépendante des valeurs internes du moteur.
        # Les fenêtres non parentes (Excel, CSV, etc.) peuvent ainsi être traduites
        # sans modifier les clés canoniques telles que « Importer ».
        self.language = str(language or getattr(parent, "language", "fr") or "fr")
        self.table = table
        self.model_key = str(model_key or "blank")
        self.model_fields = _import_model_field_choices(self.model_key)
        self.source_kind = str(table.get("source_kind") or "Access")
        self.mapping: list[dict] | None = None
        self._preview_loader = preview_loader
        self._preview_window = None
        self.setWindowTitle(tr("Correspondance des champs {source} → G-Skol", self.language).format(source=self.source_kind))
        self.resize(1120, 760)
        self.setMinimumSize(900, 600)
        self._build_ui()
        self._populate()

    @staticmethod
    def _physical_mm3_type(access_type: str, field_name: str, field: dict | None = None) -> str:
        """Déduit le type de donnée sans confondre ce type avec la fonction du champ."""
        field = field or {}

        # DAO est prioritaire lorsqu'il est disponible : il décrit mieux les champs
        # Access, notamment les champs calculés ACE.
        dao_value = field.get("calculation_result_type")
        if dao_value in (None, "", 0, "0"):
            dao_value = field.get("dao_type")
        try:
            dao_type = int(dao_value)
        except (TypeError, ValueError):
            dao_type = None

        if dao_type in {1}:
            return "Bouton On / Off"
        if dao_type == 5:  # DAO dbCurrency
            return "Monétaire"
        if dao_type in {2, 3, 4, 6, 7, 16, 19, 20, 21, 102, 103, 104, 105, 106, 108}:
            return "Nombre"
        if dao_type in {8, 22, 23}:
            return "Date"
        if dao_type in {9, 11, 17, 101}:
            return "Photo / Image"

        t = (access_type or "").strip().lower()
        n = (field_name or "").strip().lower()
        if t in {"bouton on / off", "booléen", "booleen", "boolean"}:
            return "Bouton On / Off"

        # Les champs Access de type Hyperlien sont souvent exposés par ACE/DAO
        # comme de simples champs Texte. Le nom métier permet alors de conserver
        # leur vraie fonction dans MM3.
        link_tokens = ("lien", "link", "url", "internet", "web")
        if any(token in n for token in link_tokens):
            return "Lien (Internet ou autre)"

        if "binary" in t or "image" in t or "attachment" in t or "ole" in t:
            return "Photo / Image"
        if "date" in t or "time" in t:
            return "Date"
        if "monétaire" in t or "monetaire" in t or "currency" in t:
            return "Monétaire"
        if any(k in t for k in ("bool", "yesno", "bit")):
            return "Bouton On / Off"
        if any(k in t for k in (
            "integer", "smallint", "bigint", "tinyint", "decimal",
            "numeric", "double", "single", "float", "real", "currency", "nombre",
        )):
            return "Nombre"
        return "Texte"

    @classmethod
    def _suggest_mm3_type(cls, access_type: str, field_name: str, field: dict | None = None) -> str:
        field = field or {}
        expression = str(field.get("calculation_expression") or "").strip()
        if expression:
            return "Calculé — reconnu par MM3"

        field_name = str(
            field.get("target_label")
            or field.get("source_field")
            or field.get("name")
            or field_name
            or ""
        )
        if cls._physical_mm3_type(access_type, field_name, field) == "Lien (Internet ou autre)":
            return "Lien (Internet ou autre)"

        if (str(field.get("lookup_source") or "").strip()
                or str(field.get("relation_table") or "").strip()):
            return "Liste / Référentiel — reconnu par MM3"

        # Un champ portant un nom de total et déclaré par Access comme champ calculé
        # via ses attributs reste signalé comme probable même si l'expression n'a
        # pas pu être extraite.
        if bool(field.get("is_calculated")):
            return "Calculé — probable / à vérifier"

        return cls._physical_mm3_type(access_type, field_name, field)

    @staticmethod
    def _detection_text(field: dict) -> str:
        excel_detection = str(field.get("excel_detection") or "").strip()
        if excel_detection:
            return excel_detection
        if bool(field.get("is_related_field")):
            table = str(field.get("source_table") or "")
            source = str(field.get("source_field") or field.get("name") or "")
            form = str(field.get("related_form") or "")
            master = str(field.get("linked_master_source") or "")
            child = str(field.get("linked_child_source") or "")
            link = f" — liaison {master} → {child}" if master and child else ""
            return f"Sous-formulaire {form} → {table}.{source}{link}"
        expression = str(field.get("calculation_expression") or "").strip()
        physical = str(field.get("physical_mm3_type") or "").strip()
        if expression:
            suffix = f" — résultat : {physical}" if physical else ""
            return f"Calcul Access reconnu : {expression}{suffix}"
        if bool(field.get("is_calculated")):
            return "Champ calculé Access détecté, expression non lisible — à vérifier"

        lookup = str(field.get("lookup_source") or "").strip()
        relation_table = str(field.get("relation_table") or "").strip()
        relation_field = str(field.get("relation_field") or "").strip()
        if relation_table:
            suffix = f".{relation_field}" if relation_field else ""
            return f"Relation Access reconnue → {relation_table}{suffix}"
        if lookup:
            return f"Source de liste Access reconnue : {lookup}"

        name = str(field.get("name") or "").strip().casefold()
        if name in {"n°", "nº", "no", "n°.", "numéro", "numero"}:
            return "Numéro source ordinaire — sans effet sur la numérotation des fiches MM3"
        return "—"

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 18)
        root.setSpacing(12)

        title = QLabel(tr("Correspondance des champs {source} → G-Skol", self.language).format(source=self.source_kind))
        title.setStyleSheet("font-size: 24px; font-weight: 800;")
        root.addWidget(title)

        fields = self.table.get("fields", [])
        intro = QLabel(tr("Table source : <b>{table}</b> — {count} champ(s). Pour chaque champ {source}, choisissez s’il doit être importé, le nom du futur champ G-Skol et son type. Les propositions sont automatiques mais restent entièrement modifiables.", self.language).format(table=self.table.get("name", ""), count=len(fields), source=self.source_kind))
        intro.setWordWrap(True)
        intro.setTextFormat(Qt.TextFormat.RichText)
        root.addWidget(intro)

        note = QLabel(tr("Cette étape ne crée encore aucune collection et n’importe aucune donnée. Elle prépare seulement la structure de la future collection G-Skol.", self.language))
        note.setWordWrap(True)
        note.setStyleSheet("font-style: italic;")
        root.addWidget(note)

        if self.source_kind.casefold() == "excel":
            help_text = tr(
                "• <b>Double-cliquez sur le nom d’un champ G-Skol pour le modifier.</b><br>• G-Skol déduit <b>Texte, Nombre, Monétaire, Date, Bouton On / Off et Calculé</b> à partir des cellules et formats Excel ; vous pouvez corriger chaque proposition.<br>• Une colonne Excel devient un champ de la collection. Les cellules vides restent vides.<br>• L’ordre des lignes Excel est conservé : première ligne de données → fiche 1, puis 2, 3…<br>• Un champ source <b>N° / Numéro</b> reste une donnée ordinaire et n’influence jamais la numérotation automatique des fiches.",
                self.language,
            )
        elif self.source_kind.casefold() in {"csv", "txt", "tsv", "csv / txt / tsv"}:
            help_text = tr(
                "• <b>Double-cliquez sur le nom d’un champ G-Skol pour le modifier.</b><br>• G-Skol déduit <b>Texte, Nombre, Monétaire, Date et Bouton On / Off</b> à partir des valeurs ; vous pouvez corriger chaque proposition.<br>• Le séparateur et l’encodage sont détectés automatiquement puis affichés avant l’import.<br>• Une colonne devient un champ de la collection ; les cellules vides restent vides.<br>• Les fichiers texte ne contiennent pas de vraie information de liste déroulante : vous pouvez choisir manuellement <b>Liste / Référentiel</b> dans la correspondance.<br>• L’ordre des lignes source est conservé : première ligne de données → fiche 1, puis 2, 3…",
                self.language,
            )
        elif self.source_kind.casefold() == "ods":
            help_text = tr(
                "• <b>Double-cliquez sur le nom d’un champ G-Skol pour le modifier.</b><br>• G-Skol déduit <b>Texte, Nombre, Monétaire, Date, Bouton On / Off et Calculé</b> à partir des cellules et formats ODS ; vous pouvez corriger chaque proposition.<br>• Une colonne ODS devient un champ de la collection. Les cellules vides restent vides.<br>• L’ordre des lignes ODS est conservé : première ligne de données → fiche 1, puis 2, 3…<br>• Un champ source <b>N° / Numéro</b> reste une donnée ordinaire et n’influence jamais la numérotation automatique des fiches.",
                self.language,
            )
        elif self.source_kind.casefold() == "dbf":
            help_text = tr(
                "• <b>Double-cliquez sur le nom d’un champ G-Skol pour le modifier.</b><br>• G-Skol déduit <b>Texte, Nombre, Monétaire, Date et Bouton On / Off</b> à partir des types DBF ; vous pouvez corriger chaque proposition.<br>• Un champ DBF devient un champ de la collection. Les valeurs vides restent vides.<br>• L’ordre des enregistrements DBF est conservé : premier enregistrement → fiche 1, puis 2, 3…<br>• Un champ source <b>N° / Numéro</b> reste une donnée ordinaire et n’influence jamais la numérotation automatique des fiches.",
                self.language,
            )
        elif self.source_kind.casefold() == "sqlite":
            help_text = tr(
                "• <b>Double-cliquez sur le nom d’un champ G-Skol pour le modifier.</b><br>• G-Skol déduit <b>Texte, Nombre, Monétaire, Date, Bouton On / Off, Liste / Référentiel et Calculé</b> à partir des types, relations et données SQLite ; vous pouvez corriger chaque proposition.<br>• Une colonne SQLite devient un champ de la collection. Les valeurs vides restent vides.<br>• Les référentiels multi-colonnes reconnus peuvent créer des champs Maître / Reliés.<br>• L’ordre des lignes SQLite est conservé lors de la création des fiches.<br>• Un champ source <b>N° / Numéro</b> reste une donnée ordinaire et n’influence jamais la numérotation automatique des fiches.",
                self.language,
            )
        else:
            help_text = tr("• <b>Double-cliquez sur le nom d’un champ G-Skol pour le modifier.</b><br>• <b>Bouton On / Off</b> désigne un vrai champ à deux états à cliquer ; une liste contenant les textes Oui et Non reste une <b>Liste / Référentiel</b>.<br>• <b>Liste / Référentiel — à paramétrer</b> : le champ sera préparé comme liste ; les liaisons Maître / Relié à pourront être définies ensuite dans l’Atelier.<br>• <b>Calculé — à paramétrer</b> : le champ sera préparé comme calculé, mais sa formule devra être définie dans l’Atelier.<br>• La colonne <b>Détection G-Skol</b> indique la preuve retrouvée dans Access : relation, source de liste ou expression de calcul. Une absence de preuve est affichée « — ».<br>• Un champ source <b>N° / Numéro</b> reste toujours un champ utilisateur ordinaire : il n’a <b>aucune influence</b> sur la numérotation automatique des fiches G-Skol.", self.language)
        help_label = QLabel(help_text)
        help_label.setWordWrap(True)
        help_label.setTextFormat(Qt.TextFormat.RichText)
        help_label.setStyleSheet(
            "background: #F5F7F6; border: 1px solid #CDD7D2; border-radius: 6px; "
            "padding: 8px; color: #35443D;"
        )
        root.addWidget(help_label)

        self.table_widget = QTableWidget(0, 6)
        self.table_widget.setHorizontalHeaderLabels(
            [tr("Action", self.language), tr("Champ {source}", self.language).format(source=self.source_kind), tr("Type {source}", self.language).format(source=self.source_kind), tr("Champ G-Skol", self.language), tr("Type G-Skol", self.language), tr("Détection G-Skol", self.language)]
        )
        self.table_widget.setAlternatingRowColors(True)
        self.table_widget.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table_widget.verticalHeader().setVisible(True)
        self.table_widget.verticalHeader().setDefaultSectionSize(26)
        self.table_widget.verticalHeader().setMinimumWidth(42)
        header = self.table_widget.horizontalHeader()
        # Comme dans un tableur : chaque séparation d'en-tête peut être tirée
        # librement à la souris, y compris sur un petit écran.
        for col in range(6):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
        header.setMinimumSectionSize(55)
        header.setStretchLastSection(False)
        self.table_widget.setColumnWidth(0, 90)
        self.table_widget.setColumnWidth(1, 170)
        self.table_widget.setColumnWidth(2, 115)
        self.table_widget.setColumnWidth(3, 170)
        self.table_widget.setColumnWidth(4, 230)
        self.table_widget.setColumnWidth(5, 300)
        self.table_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_widget.customContextMenuRequested.connect(self._show_field_context_menu)
        root.addWidget(self.table_widget, 1)

        tools = QHBoxLayout()
        all_btn = QPushButton(tr("Tout importer", self.language))
        all_btn.clicked.connect(lambda: self._set_all_actions("Importer"))
        tools.addWidget(all_btn)
        none_btn = QPushButton(tr("Tout ignorer", self.language))
        none_btn.clicked.connect(lambda: self._set_all_actions("Ignorer"))
        tools.addWidget(none_btn)
        reset_btn = QPushButton(tr("Réinitialiser les propositions", self.language))
        reset_btn.clicked.connect(self._populate)
        tools.addWidget(reset_btn)
        if callable(self._preview_loader):
            preview_btn = QPushButton(tr("Aperçu des données — fenêtre flottante", self.language))
            preview_btn.clicked.connect(self._show_floating_preview)
            tools.addWidget(preview_btn)
        tools.addStretch(1)
        self.summary_label = QLabel()
        tools.addWidget(self.summary_label)
        root.addLayout(tools)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel_btn = QPushButton(tr("Annuler", self.language))
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(cancel_btn)
        validate_btn = QPushButton(tr("Valider la correspondance", self.language))
        validate_btn.clicked.connect(self._validate_mapping)
        buttons.addWidget(validate_btn)
        root.addLayout(buttons)

    def _show_field_context_menu(self, pos) -> None:
        """Propose au clic droit la même édition du libellé que le double-clic."""
        item = self.table_widget.itemAt(pos)
        if item is None:
            return
        row = item.row()
        target = self.table_widget.item(row, 3)
        if target is None or not (target.flags() & Qt.ItemFlag.ItemIsEditable):
            return
        menu = QMenu(self)
        action = menu.addAction(tr("Modifier le libellé…", self.language))
        chosen = menu.exec(self.table_widget.viewport().mapToGlobal(pos))
        if chosen is action:
            self.table_widget.setCurrentCell(row, 3)
            self.table_widget.editItem(target)

    def _show_floating_preview(self) -> None:
        """Ouvre l'aperçu sans bloquer la correspondance des champs."""
        if not callable(self._preview_loader):
            return
        try:
            preview = self._preview_loader()
        except Exception as exc:
            QMessageBox.warning(self, f"Aperçu {self.source_kind} impossible", str(exc))
            return

        # Une seule fenêtre flottante par correspondance ; si elle existe, on la ramène.
        try:
            if self._preview_window is not None and self._preview_window.isVisible():
                self._preview_window.raise_()
                self._preview_window.activateWindow()
                return
        except RuntimeError:
            self._preview_window = None

        window = AccessDataPreviewDialog(
            str(self.table.get("name", "")),
            preview,
            None,
            self.language,
        )
        window.setWindowModality(Qt.WindowModality.NonModal)
        window.setModal(False)
        window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        window.destroyed.connect(lambda *_: setattr(self, "_preview_window", None))
        self._preview_window = window
        window.show()
        window.raise_()
        window.activateWindow()

    @staticmethod
    def _access_type_display(access_type: str) -> str:
        """Libellé français d'affichage uniquement ; le type source brut reste intact."""
        raw = str(access_type or "").strip()
        key = raw.casefold().replace(" ", "")
        labels = {
            "text": "Texte", "varchar": "Texte", "char": "Texte",
            "memo": "Texte long", "longvarchar": "Texte long",
            "long": "Entier long", "integer": "Entier", "short": "Entier",
            "byte": "Octet", "single": "Réel simple", "double": "Réel double",
            "currency": "Monétaire", "decimal": "Décimal",
            "datetime": "Date / Heure", "date": "Date / Heure",
            "boolean": "Oui / Non", "yes/no": "Oui / Non",
            "longbinary": "Binaire long", "binary": "Binaire",
            "hyperlink": "Lien hypertexte", "attachment": "Pièce jointe",
        }
        return labels.get(key, raw)

    def _detection_text_display(self, field: dict) -> str:
        text = self._detection_text(field)
        if self.language.lower().startswith("de"):
            replacements = (
                ("Numéro source ordinaire — sans effet sur la numérotation des fiches MM3", "Gewöhnliche Quellnummer — ohne Auswirkung auf die automatische G-Skol-Datensatznummerierung"),
                ("Numéro source ordinaire — sans effet sur la numérotation automatique des fiches MM3", "Gewöhnliche Quellnummer — ohne Auswirkung auf die automatische G-Skol-Datensatznummerierung"),
                ("Source de liste Access reconnue", "Access-Listenquelle erkannt"),
                ("Relation Access reconnue", "Access-Beziehung erkannt"),
                ("Calcul Access reconnu", "Access-Berechnung erkannt"),
                ("Expression de calcul Access reconnue", "Access-Berechnungsausdruck erkannt"),
                ("Champ calculé Access détecté, expression non lisible — à vérifier", "Berechnetes Access-Feld erkannt, Ausdruck nicht lesbar — bitte prüfen"),
                ("Sous-formulaire", "Unterformular"),
                ("liaison", "Verknüpfung"),
                ("résultat", "Ergebnis"),
                ("Excel : contenu mixte ou texte", "Excel: gemischter Inhalt oder Text"),
                ("Excel : dates Excel", "Excel: Datumswerte"),
                ("Excel : valeurs numériques", "Excel: numerische Werte"),
                ("Excel : valeurs Oui/Non", "Excel: Ja/Nein-Werte"),
                ("Excel : valeur Excel conservée", "Excel: Excel-Wert beibehalten"),
                ("Excel : formule Excel traduite en calcul MM3", "Excel: Excel-Formel in eine G-Skol-Berechnung übersetzt"),
                ("Excel : formule Excel traduite en calcul G-Skol", "Excel: Excel-Formel in eine G-Skol-Berechnung übersetzt"),
                ("Excel : liste déroulante reconnue", "Excel: Dropdown-Liste erkannt"),
                ("Fichier texte : valeurs numériques reconnues", "Textdatei: numerische Werte erkannt"),
                ("Fichier texte : colonne monétaire reconnue", "Textdatei: Währungsspalte erkannt"),
                ("Fichier texte : valeurs monétaires reconnues", "Textdatei: Währungswerte erkannt"),
                ("Fichier texte : colonne monétaire reconnue par son libellé", "Textdatei: Währungsspalte anhand ihrer Bezeichnung erkannt"),
                ("Fichier texte : dates reconnues", "Textdatei: Datumswerte erkannt"),
                ("Fichier texte : valeurs booléennes reconnues", "Textdatei: boolesche Werte erkannt"),
                ("Fichier texte : contenu mixte ou texte", "Textdatei: gemischter Inhalt oder Text"),
                ("ODS : contenu mixte ou texte", "ODS: gemischter Inhalt oder Text"),
                ("ODS : valeurs numériques", "ODS: numerische Werte"),
                ("ODS : valeurs monétaires ODS", "ODS: Währungswerte"),
                ("ODS : dates ODS", "ODS: Datumswerte"),
                ("ODS : valeurs Oui/Non", "ODS: Ja/Nein-Werte"),
                ("ODS : formule ODS traduite en calcul G-Skol", "ODS: ODS-Formel in eine G-Skol-Berechnung übersetzt"),
                ('DBF : champ texte DBF', 'DBF: Textfeld'),
                ('DBF : champ numérique DBF à 2 décimales identifié comme monétaire', 'DBF: Zahlenfeld mit zwei Dezimalstellen als Währung erkannt'),
                ('DBF : champ numérique DBF', 'DBF: Zahlenfeld'),
                ('DBF : champ monétaire DBF', 'DBF: Währungsfeld'),
                ('DBF : champ logique DBF', 'DBF: logisches Feld'),
                ('DBF : date DBF', 'DBF: Datumsfeld'),
                ('DBF : mémo/objet DBF (fichier compagnon éventuel)', 'DBF: Memo-/Objektfeld (ggf. Begleitdatei erforderlich)'),
                ('DBF : champ date DBF', 'DBF: Datumsfeld'),
                ('DBF : champ mémo/objet DBF (fichier compagnon éventuel)', 'DBF: Memo-/Objektfeld (ggf. Begleitdatei erforderlich)'),
                ("SQLite : référentiel multi-colonnes reconnu dans", "SQLite: mehrspaltige Referenz erkannt in"),
                ("SQLite : champ Relié issu du référentiel", "SQLite: verknüpftes Feld aus der Referenz"),
                ("SQLite : calcul déduit des données", "SQLite: aus den Daten abgeleitete Berechnung"),
                ("SQLite : numérique SQLite à 2 décimales identifié comme monétaire", "SQLite: Zahlenwert mit zwei Dezimalstellen als Währung erkannt"),
                ("SQLite : type BOOLEAN/BOOL SQLite", "SQLite: BOOLEAN/BOOL-Typ"),
                ("SQLite : type date/heure SQLite", "SQLite: Datums-/Uhrzeittyp"),
                ("SQLite : type monétaire SQLite", "SQLite: Währungstyp"),
                ("SQLite : données binaires SQLite", "SQLite: Binärdaten"),
                ("SQLite : valeurs 0/1 cohérentes avec un booléen", "SQLite: Werte 0/1 entsprechen einem Wahrheitswert"),
                ("SQLite : valeurs numériques et nom de colonne monétaire", "SQLite: Zahlenwerte und Spaltenname weisen auf Währung hin"),
                ("SQLite : valeurs numériques SQLite", "SQLite: numerische Werte"),
                ("SQLite : valeurs texte reconnues comme dates", "SQLite: Textwerte als Datumsangaben erkannt"),
                ("SQLite : type texte SQLite", "SQLite: Texttyp"),
                ("SQLite : type numérique SQLite", "SQLite: Zahlentyp"),
                ("SQLite : type entier SQLite", "SQLite: Ganzzahltyp"),
                ("SQLite : type date SQLite", "SQLite: Datumstyp"),
                ("référentiel reconnu par MM3", "von G-Skol erkannte Referenz"),
                ("calcul reconnu par MM3", "von G-Skol erkannte Berechnung"),
                ("MM3", "G-Skol"),
            )
            for old, new in replacements:
                text = text.replace(old, new)
            return text
        if not self.language.lower().startswith("en"):
            return text.replace("MM3", "G-Skol")
        replacements = (
            ("Numéro source ordinaire — sans effet sur la numérotation automatique des fiches MM3", "Ordinary source number — no effect on automatic G-Skol record numbering"),
            ("Source de liste Access reconnue", "Access list source recognized"),
            ("Relation Access reconnue", "Access relationship recognized"),
            ("Expression de calcul Access reconnue", "Access calculation expression recognized"),
            ("Excel : contenu mixte ou texte", "Excel: mixed content or text"),
            ("Excel : dates Excel", "Excel: dates"),
            ("Excel : valeurs numériques", "Excel: numeric values"),
            ("Excel : valeurs Oui/Non", "Excel: Yes/No values"),
            ("Excel : valeur Excel conservée", "Excel: value preserved"),
            ("Excel : formule Excel traduite en calcul MM3", "Excel: formula translated into a G-Skol calculation"),
            ("Fichier texte : valeurs numériques reconnues", "Text file: numeric values recognized"),
            ("Fichier texte : colonne monétaire reconnue", "Text file: currency column recognized"),
            ("Fichier texte : dates reconnues", "Text file: dates recognized"),
            ("Fichier texte : valeurs booléennes reconnues", "Text file: Boolean values recognized"),
            ("Fichier texte : contenu mixte ou texte", "Text file: mixed content or text"),
            ("ODS : contenu mixte ou texte", "ODS: mixed content or text"),
            ("ODS : valeurs numériques", "ODS: numeric values"),
            ("ODS : valeurs monétaires ODS", "ODS: currency values"),
            ("ODS : dates ODS", "ODS: dates"),
            ("ODS : valeurs Oui/Non", "ODS: Yes/No values"),
            ("ODS : formule ODS traduite en calcul G-Skol", "ODS: formula translated into a G-Skol calculation"),
            ("DBF : champ texte DBF", "DBF: text field"),
            ("DBF : champ numérique DBF à 2 décimales identifié comme monétaire", "DBF: 2-decimal numeric field recognized as currency"),
            ("DBF : champ numérique DBF", "DBF: numeric field"),
            ("DBF : champ monétaire DBF", "DBF: currency field"),
            ("DBF : champ logique DBF", "DBF: logical field"),
            ("DBF : date DBF", "DBF: date"),
            ("DBF : mémo/objet DBF (fichier compagnon éventuel)", "DBF: memo/object field (companion file may be required)"),
            ("SQLite : type BOOLEAN/BOOL SQLite", "SQLite: BOOLEAN/BOOL type"),
            ("SQLite : type date/heure SQLite", "SQLite: date/time type"),
            ("SQLite : type monétaire SQLite", "SQLite: currency type"),
            ("SQLite : données binaires SQLite", "SQLite: binary data"),
            ("SQLite : numérique SQLite à 2 décimales identifié comme monétaire", "SQLite: 2-decimal numeric field recognized as currency"),
            ("SQLite : type numérique SQLite", "SQLite: numeric type"),
            ("SQLite : valeurs 0/1 cohérentes avec un booléen", "SQLite: 0/1 values consistent with a Boolean"),
            ("SQLite : valeurs numériques et nom de colonne monétaire", "SQLite: numeric values and currency column name"),
            ("SQLite : valeurs numériques SQLite", "SQLite: numeric values"),
            ("SQLite : valeurs texte reconnues comme dates", "SQLite: text values recognized as dates"),
            ("SQLite : type texte SQLite", "SQLite: text type"),
            ("SQLite : calcul déduit des données", "SQLite: calculation inferred from data"),
            ("SQLite : référentiel multi-colonnes reconnu dans", "SQLite: multi-column reference recognized in"),
            ("SQLite : champ Relié issu du référentiel", "SQLite: linked field from reference"),
            ("Maître", "Master"),
            ("champ(s) Relié(s)", "linked field(s)"),
            ("référentiel reconnu par MM3", "reference recognized by G-Skol"),
            ("calcul reconnu par MM3", "calculation recognized by G-Skol"),
            ("MM3", "G-Skol"),
        )
        for old, new in replacements:
            text = text.replace(old, new)
        return text

    def _populate(self) -> None:
        fields = self.table.get("fields", [])
        self.table_widget.setRowCount(0)
        for field in fields:
            row = self.table_widget.rowCount()
            self.table_widget.insertRow(row)
            self.table_widget.setVerticalHeaderItem(row, QTableWidgetItem(str(row + 1)))

            action = SafeTypeComboBox()
            action.addItem(tr("Importer", self.language), "Importer")
            action.addItem(tr("Ignorer", self.language), "Ignorer")
            action.currentTextChanged.connect(
                lambda _value, r=row: self._on_action_changed(r)
            )
            self.table_widget.setCellWidget(row, 0, action)

            source_name = str(field.get("name", ""))
            source_display = str(field.get("display_name") or source_name)
            source_type = str(field.get("type", ""))
            size = field.get("size")
            type_text = tr(self._access_type_display(source_type), self.language)
            if size not in (None, "", 0, "0") and source_type.lower() in {
                "varchar", "char", "longvarchar", "wchar", "varwchar", "longvarwchar"
            }:
                type_text = f"{type_text} ({size})"

            source_item = QTableWidgetItem(source_display)
            source_item.setData(Qt.ItemDataRole.UserRole, dict(field))
            source_item.setToolTip(
                str(field.get("source_table") or "") + "." +
                str(field.get("source_field") or source_name)
                if field.get("source_table") else source_display
            )
            source_item.setFlags(source_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table_widget.setItem(row, 1, source_item)
            type_item = QTableWidgetItem(type_text)
            type_item.setFlags(type_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table_widget.setItem(row, 2, type_item)

            normalized_source = source_name.strip().casefold()
            proposed_target = str(field.get("target_label") or "").strip() or (
                "N° source"
                if normalized_source in {"n°", "nº", "no", "n°.", "numéro", "numero"}
                else source_name
            )
            target_item = QTableWidgetItem(proposed_target)
            self.table_widget.setItem(row, 3, target_item)
            if self.model_fields:
                dest = SafeTypeComboBox()
                dest.addItem("— Ne pas importer —", "__skip__")
                dest.addItem("— Créer un nouveau champ… —", "__create__")
                for label, key in self.model_fields:
                    dest.addItem(label, key)
                # Match by label, then by historical internal field identity.
                index = dest.findText(proposed_target, Qt.MatchFlag.MatchFixedString)
                if index < 0:
                    for idx in range(2, dest.count()):
                        key = str(dest.itemData(idx) or "")
                        if key in FIELD_BY_KEY and FIELD_BY_KEY[key].label.casefold() == proposed_target.casefold():
                            index = idx
                            break
                if index < 0:
                    index = 1  # New source field: create in the Atelier palette.
                dest.setCurrentIndex(index)
                dest.currentIndexChanged.connect(lambda _i, r=row: self._model_target_changed(r))
                self.table_widget.setCellWidget(row, 3, dest)

            mm3_type = SafeTypeComboBox()
            for _canonical_type in self.MM3_TYPES:
                mm3_type.addItem(tr(_canonical_type.replace("MM3", "G-Skol"), self.language), _canonical_type)
            _suggested_type = self._suggest_mm3_type(source_type, source_name, field)
            _type_idx = mm3_type.findData(_suggested_type)
            if _type_idx >= 0:
                mm3_type.setCurrentIndex(_type_idx)
            else:
                mm3_type.setCurrentText(_suggested_type)
            self.table_widget.setCellWidget(row, 4, mm3_type)

            field["physical_mm3_type"] = self._physical_mm3_type(source_type, source_name, field)
            detection_item = QTableWidgetItem(self._detection_text_display(field))
            detection_item.setFlags(detection_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            detection_item.setToolTip(detection_item.text())
            self.table_widget.setItem(row, 5, detection_item)

        # Le nom MM3 reste éditable, mais seulement par double-clic afin
        # d'éviter les modifications accidentelles pendant la sélection.
        self.table_widget.setEditTriggers(
            QTableWidget.EditTrigger.DoubleClicked
            | QTableWidget.EditTrigger.EditKeyPressed
        )
        self._update_summary()
        for row in range(self.table_widget.rowCount()):
            self._apply_row_state(row)

    def _model_target_changed(self, row: int) -> None:
        combo = self.table_widget.cellWidget(row, 3)
        item = self.table_widget.item(row, 3)
        if isinstance(combo, QComboBox) and item is not None:
            choice = str(combo.currentData() or "")
            if choice == "__create__":
                source_item = self.table_widget.item(row, 1)
                meta = source_item.data(Qt.ItemDataRole.UserRole) if source_item else {}
                item.setText(str((meta or {}).get("target_label") or (source_item.text() if source_item else "")))
            elif choice == "__skip__":
                item.setText("")
            else:
                item.setText(combo.currentText() if choice else "")

    def _on_action_changed(self, row: int) -> None:
        self._apply_row_state(row)
        self._update_summary()

    def _apply_row_state(self, row: int) -> None:
        """Grise clairement toute ligne exclue de l'import."""
        combo = self.table_widget.cellWidget(row, 0)
        ignored = isinstance(combo, QComboBox) and (combo.currentData() or combo.currentText()) == "Ignorer"

        if ignored:
            # La surbrillance de sélection Qt masquait le gris des cellules texte
            # jusqu'au changement de ligne. On la retire immédiatement.
            self.table_widget.clearSelection()
            self.table_widget.setCurrentCell(-1, -1)

        fg = QColor("#8A918D") if ignored else QColor("#202522")
        bg = QColor("#ECEFEE") if ignored else QColor(Qt.GlobalColor.transparent)
        for col in (1, 2, 3, 5):
            item = self.table_widget.item(row, col)
            if item is not None:
                item.setForeground(fg)
                item.setBackground(bg)

        type_combo = self.table_widget.cellWidget(row, 4)
        widgets = [combo, type_combo, self.table_widget.cellWidget(row, 3)]
        for widget in widgets:
            if widget is None:
                continue
            if ignored:
                widget.setStyleSheet(
                    "QComboBox { background: #ECEFEE; color: #8A918D; "
                    "border: 1px solid #D5DAD7; }"
                )
            else:
                widget.setStyleSheet("")

        # Le champ cible n'est pas modifiable tant qu'il est ignoré.
        target_item = self.table_widget.item(row, 3)
        if target_item is not None:
            flags = target_item.flags()
            if ignored:
                target_item.setFlags(flags & ~Qt.ItemFlag.ItemIsEditable)
            else:
                target_item.setFlags(flags | Qt.ItemFlag.ItemIsEditable)

        # Le changement doit être visible immédiatement, même si la ligne
        # reste la ligne courante/sélectionnée.
        self.table_widget.viewport().update()
        self.table_widget.viewport().repaint()
        self.table_widget.update()
        self.table_widget.repaint()
        QApplication.processEvents()

    def _set_all_actions(self, value: str) -> None:
        for row in range(self.table_widget.rowCount()):
            combo = self.table_widget.cellWidget(row, 0)
            if isinstance(combo, QComboBox):
                idx = combo.findData(value)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
                else:
                    combo.setCurrentText(value)
        self._update_summary()

    def _update_summary(self, *_args) -> None:
        total = self.table_widget.rowCount()
        imported = 0
        for row in range(total):
            combo = self.table_widget.cellWidget(row, 0)
            if isinstance(combo, QComboBox) and (combo.currentData() or combo.currentText()) == "Importer":
                imported += 1
        self.summary_label.setText((f"{imported} / {total} field(s) to import") if self.language.lower().startswith("en") else ((f"{imported} / {total} Feld(er) zu importieren") if self.language.lower().startswith("de") else f"{imported} / {total} champ(s) à importer"))

    def _validate_mapping(self) -> None:
        mapping: list[dict] = []
        used_names: dict[str, int] = {}
        for row in range(self.table_widget.rowCount()):
            action_combo = self.table_widget.cellWidget(row, 0)
            source_item = self.table_widget.item(row, 1)
            target_item = self.table_widget.item(row, 3)
            type_combo = self.table_widget.cellWidget(row, 4)
            if not isinstance(action_combo, QComboBox) or source_item is None or target_item is None:
                continue

            action = str(action_combo.currentData() or action_combo.currentText())
            field_meta = source_item.data(Qt.ItemDataRole.UserRole)
            if not isinstance(field_meta, dict):
                field_meta = {}
            source_display = source_item.text().strip()
            source_name = str(field_meta.get("source_field") or field_meta.get("name") or source_display).strip()
            dest_combo = self.table_widget.cellWidget(row, 3)
            target_choice = str(dest_combo.currentData() or "") if isinstance(dest_combo, QComboBox) else ""
            if self.model_fields and target_choice == "__skip__":
                action = "Ignorer"
                target_name = ""
            elif self.model_fields and target_choice == "__create__":
                target_name = str(field_meta.get("target_label") or source_name).strip()
            elif self.model_fields:
                target_name = dest_combo.currentText().strip() if isinstance(dest_combo, QComboBox) else ""
            else:
                target_name = target_item.text().strip()
            mm3_type = str(type_combo.currentData() or type_combo.currentText()) if isinstance(type_combo, QComboBox) else "Texte"

            if action == "Importer":
                if not target_name:
                    QMessageBox.warning(
                        self, "Correspondance incomplète",
                        f"Le champ {self.source_kind} « {source_name} » doit avoir une destination G-Skol."
                    )
                    self.table_widget.setCurrentCell(row, 3)
                    return
                key = target_name.casefold()
                if key in used_names:
                    first = used_names[key] + 1
                    QMessageBox.warning(
                        self, tr("Nom de champ en double", self.language),
                        (f"Der G-Skol-Feldname „{target_name}“ wird zweimal verwendet (Zeilen {first} und {row + 1}). Wählen Sie unterschiedliche Namen." if self.language.lower().startswith("de") else f"Le nom G-Skol « {target_name} » est utilisé deux fois (lignes {first} et {row + 1}). Choisissez des noms différents.")
                    )
                    self.table_widget.setCurrentCell(row, 3)
                    return
                used_names[key] = row

            mapping.append({
                "source": source_name,
                "source_display": source_display,
                "source_table": str(field_meta.get("source_table") or ""),
                "is_related_field": bool(field_meta.get("is_related_field")),
                "related_form": str(field_meta.get("related_form") or ""),
                "linked_master_source": str(field_meta.get("linked_master_source") or ""),
                "linked_child_source": str(field_meta.get("linked_child_source") or ""),
                "access_tab_index": field_meta.get("access_tab_index"),
                "access_tab_stop": field_meta.get("access_tab_stop"),
                "access_tab_path": field_meta.get("access_tab_path"),
                "source_order": field_meta.get("source_order"),
                "calculation_expression": str(field_meta.get("calculation_expression") or ""),
                "calculation_result_type": str(field_meta.get("calculation_result_type") or ""),
                "calculation_format": str(field_meta.get("calculation_format") or "truncate2"),
                "currency_symbol": str(field_meta.get("currency_symbol") or ""),
                "result_suffix": str(field_meta.get("result_suffix") or ""),
                "excel_validation_formula": str(field_meta.get("excel_validation_formula") or ""),
                "excel_reference_values": list(field_meta.get("excel_reference_values") or []),
                "sqlite_reference_values": list(field_meta.get("sqlite_reference_values") or []),
                "sqlite_reference_table": str(field_meta.get("sqlite_reference_table") or ""),
                "action": action,
                "target": target_name,
                "target_field_key": (target_choice if target_choice not in {"__skip__", "__create__"} else ""),
                "create_in_palette": bool(self.model_fields and target_choice == "__create__"),
                "mm3_type": mm3_type,
                "needs_configuration": (
                    action == "Importer"
                    and ("à paramétrer" in mm3_type)
                ),
                "recognized_by_mm3": (
                    action == "Importer" and "reconnu par MM3" in mm3_type
                ),
                "needs_verification": (
                    action == "Importer" and "à vérifier" in mm3_type
                ),
            })

        imported = sum(1 for m in mapping if m["action"] == "Importer")
        if imported == 0:
            QMessageBox.warning(
                self, tr("Correspondance vide", self.language),
                tr("Aucun champ n’est actuellement prévu pour l’import.", self.language)
            )
            return

        pending = [
            m for m in mapping
            if m.get("action") == "Importer" and m.get("needs_configuration")
        ]
        if pending:
            calc_pending = sum(
                1 for m in pending if str(m.get("mm3_type", "")).startswith("Calculé")
            )
            ref_pending = sum(
                1 for m in pending if str(m.get("mm3_type", "")).startswith("Liste / Référentiel")
            )
            details = []
            if calc_pending:
                details.append(
                    f"{calc_pending} champ(s) calculé(s) : formule à définir dans l’Atelier"
                )
            if ref_pending:
                details.append(
                    f"{ref_pending} champ(s) Liste / Référentiel : liaison à définir dans l’Atelier"
                )
            QMessageBox.information(
                self,
                "Paramétrages à compléter après import",
                "MM3 conservera la nature de ces champs, mais certains réglages "
                f"ne sont pas encore déductibles automatiquement depuis la source {self.source_kind}.\n\n"
                + "\n".join("• " + d for d in details)
                + "\n\nIls seront clairement identifiés pour être complétés ensuite dans l’Atelier.",
            )

        self.mapping = mapping
        self.accept()


class AccessDataPreviewDialog(QDialog):
    """Fenêtre indépendante affichant un échantillon Access en lecture seule."""

    def __init__(self, table_name: str, preview: dict, parent: QWidget | None = None, language: str | None = None) -> None:
        # Qt.Window donne une vraie fenêtre de premier niveau, activable depuis
        # la barre des tâches et ramenable au premier plan par un simple clic.
        super().__init__(parent, Qt.WindowType.Window)
        self.language = str(language or getattr(parent, "language", "fr") or "fr")
        self.setWindowTitle(tr("Aperçu des données — {table}", self.language).format(table=table_name))
        self.setModal(False)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.resize(1200, 680)
        self.setMinimumSize(860, 520)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(10)
        title = QLabel(tr("Aperçu des données — <b>{table}</b>", self.language).format(table=table_name))
        title.setTextFormat(Qt.TextFormat.RichText)
        title.setStyleSheet("font-size: 19px; font-weight: 650;")
        root.addWidget(title)

        rows = preview.get("rows", []) or []
        columns = preview.get("columns", []) or []
        info = QLabel(tr("Lecture seule : {count} première(s) ligne(s) affichée(s). Cet aperçu sert à comprendre une base inconnue ; aucune donnée n’est modifiée.", self.language).format(count=len(rows)))
        info.setWordWrap(True)
        root.addWidget(info)

        table = QTableWidget(len(rows), len(columns))
        table.setHorizontalHeaderLabels([str(c) for c in columns])
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectItems)
        table.setAlternatingRowColors(True)
        for r, values in enumerate(rows):
            if not isinstance(values, list):
                continue
            for c, value in enumerate(values[:len(columns)]):
                item = QTableWidgetItem("" if value is None else str(value))
                item.setToolTip(item.text())
                table.setItem(r, c, item)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        table.horizontalHeader().setDefaultSectionSize(150)
        root.addWidget(table, 1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        close_btn = QPushButton(tr("Fermer", self.language))
        close_btn.clicked.connect(self.close)
        buttons.addWidget(close_btn)
        root.addLayout(buttons)
        translate_widget_tree(self, self.language)

    def mousePressEvent(self, event) -> None:
        self.raise_()
        self.activateWindow()
        super().mousePressEvent(event)



class AccessReferenceMappingDialog(QDialog):
    """Validation explicite des correspondances d'un référentiel Access vers MM3."""

    ROLE_SKIP = "Ne pas importer"
    ROLE_LINKED = "Relié"
    ROLE_MASTER = "Maître"
    DEST_CREATE = "Créer"

    def __init__(self, table_name: str, source_fields: list[dict], destination_fields: list[dict], proposals: dict[str, dict], parent=None, language: str = "fr") -> None:
        super().__init__(parent)
        self.language = language
        self.setWindowTitle(tr("Correspondance des champs — {table}", self.language).format(table=table_name))
        self.resize(900, 620)
        self.setMinimumSize(760, 500)
        self._destination_fields = [dict(x) for x in destination_fields]
        self.mapping: dict | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(10)

        title = QLabel(tr("Correspondance des champs — {table}", self.language).format(table=table_name))
        title.setStyleSheet("font-size: 20px; font-weight: 800;")
        root.addWidget(title)
        info = QLabel(tr(
            "G-Skol propose les correspondances trouvées. Vérifiez-les avant l'import : un seul champ doit être défini comme Maître ; les autres champs utiles sont Reliés. Dans la liste Champ G-Skol, choisissez un champ existant, « Créer » pour ajouter explicitement le champ à la collection, ou « Ne pas importer » pour ignorer la colonne.",
            self.language))
        info.setWordWrap(True)
        root.addWidget(info)

        self.table = QTableWidget(len(source_fields), 3)
        self.table.setHorizontalHeaderLabels([tr("Colonne Access (nom réel)", self.language), tr("Rôle", self.language), tr("Champ G-Skol (libellé actuel)", self.language)])
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        root.addWidget(self.table, 1)

        self._rows: list[tuple[str, QComboBox, QComboBox]] = []
        dest_sorted = sorted(self._destination_fields, key=lambda x: str(x.get("label") or x.get("key") or "").casefold())
        for row, field in enumerate(source_fields):
            src = str(field.get("name") or "")
            item = QTableWidgetItem(src)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 0, item)

            role = SafeTypeComboBox()
            role.addItem(tr("Ne pas importer", self.language), self.ROLE_SKIP)
            role.addItem(tr("Relié", self.language), self.ROLE_LINKED)
            role.addItem(tr("Maître", self.language), self.ROLE_MASTER)
            dest = SafeTypeComboBox()
            dest.addItem(tr("Ne pas importer", self.language), None)
            dest.addItem(tr(self.DEST_CREATE, self.language), {"create": True, "label": self.DEST_CREATE})
            for d in dest_sorted:
                dest.addItem(str(d.get("label") or d.get("key") or "Champ"), dict(d))

            proposal = dict(proposals.get(src) or {})
            proposed_dest = proposal.get("dest")
            proposed_role = str(proposal.get("role") or self.ROLE_SKIP)
            if proposed_dest:
                wanted_key = str(proposed_dest.get("key") or "")
                for i in range(dest.count()):
                    data = dest.itemData(i)
                    if isinstance(data, dict) and str(data.get("key") or "") == wanted_key:
                        dest.setCurrentIndex(i)
                        break
            wanted_role = proposed_role if proposed_dest else self.ROLE_SKIP
            for i in range(role.count()):
                if role.itemData(i) == wanted_role:
                    role.setCurrentIndex(i); break
            dest.setEnabled(role.currentData() != self.ROLE_SKIP)
            role.currentIndexChanged.connect(lambda _idx, r=row: self._role_changed(r))
            dest.currentIndexChanged.connect(self._update_state)
            self.table.setCellWidget(row, 1, role)
            self.table.setCellWidget(row, 2, dest)
            self._rows.append((src, role, dest))

        self.status = QLabel("")
        self.status.setWordWrap(True)
        root.addWidget(self.status)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton(tr("Annuler", self.language))
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        self.ok_btn = QPushButton(tr("Valider les correspondances", self.language))
        self.ok_btn.clicked.connect(self._accept_mapping)
        buttons.addWidget(self.ok_btn)
        root.addLayout(buttons)
        self._update_state()

    def _role_changed(self, row: int) -> None:
        _, role, dest = self._rows[row]
        role_value = role.currentData()
        dest.setEnabled(role_value != self.ROLE_SKIP)
        if role_value == self.ROLE_SKIP:
            dest.setCurrentIndex(0)
        elif dest.currentIndex() == 0 and dest.count() > 1:
            # Ne jamais inventer une destination ; le premier champ n'est choisi
            # automatiquement que si une proposition l'avait déjà positionné.
            pass
        self._update_state()

    def _validated_rows(self) -> tuple[list[dict], str]:
        chosen = []
        masters = 0
        destinations: set[str] = set()
        for src, role, dest in self._rows:
            role_text = role.currentData()
            if role_text == self.ROLE_SKIP:
                continue
            data = dest.currentData()
            if not isinstance(data, dict):
                return [], tr("Choisissez un champ G-Skol destination pour « {src} », « Créer », ou sélectionnez « Ne pas importer ».", self.language).format(src=src)
            creating = bool(data.get("create"))
            key = str(data.get("key") or "")
            if not creating and not key:
                return [], tr("Choisissez un champ G-Skol destination pour « {src} », « Créer », ou sélectionnez « Ne pas importer ».", self.language).format(src=src)
            if key:
                if key in destinations:
                    return [], tr("Le champ G-Skol « {field} » est utilisé plusieurs fois. Choisissez une seule colonne source pour cette destination.", self.language).format(field=data.get("label") or key)
                destinations.add(key)
            if role_text == self.ROLE_MASTER:
                masters += 1
            source_meta = {}
            # Le nom source permet au moteur d'import de retrouver ses métadonnées
            # et de choisir un type approprié si « Créer » a été demandé.
            chosen.append({"source": src, "role": role_text, "dest": dict(data), "create": creating, "source_meta": source_meta})
        if masters != 1:
            return [], tr("Un seul Maître est obligatoire pour ce référentiel.", self.language)
        return chosen, ""

    def _update_state(self, *args) -> None:
        chosen, error = self._validated_rows()
        self.ok_btn.setEnabled(not error)
        if error:
            self.status.setText(error)
            self.status.setStyleSheet("color:#A33; font-weight:600;")
        else:
            linked = sum(1 for x in chosen if x["role"] == self.ROLE_LINKED)
            creates = sum(1 for x in chosen if x.get("create"))
            suffix = tr(" — {count} champ(s) à créer", self.language).format(count=creates) if creates else ""
            self.status.setText(tr("Correspondance valide : 1 Maître et {count} champ(s) Relié(s){suffix}.", self.language).format(count=linked, suffix=suffix))
            self.status.setStyleSheet("color:#245E2D; font-weight:600;")

    def _accept_mapping(self) -> None:
        chosen, error = self._validated_rows()
        if error:
            QMessageBox.warning(self, tr("Correspondance incomplète", self.language), error)
            return
        master = next(x for x in chosen if x["role"] == self.ROLE_MASTER)
        linked = [x for x in chosen if x["role"] == self.ROLE_LINKED]
        self.mapping = {"master_source": master["source"], "master_dest": master["dest"], "linked": linked}
        self.accept()


class SQLiteReferenceImportDialog(QDialog):
    """Importe des référentiels multi-colonnes dans une collection G-Skol existante.

    Le moteur est commun aux sources SQLite et Excel .xlsx. Le mode reste sûr :
    « Ajouter / compléter » uniquement, sans suppression de fiches ni de valeurs.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.language = str(getattr(parent, "language", "fr") or "fr")
        self.setWindowTitle(tr("Importer des référentiels dans une collection existante", self.language))
        self.resize(900, 700)
        self.setMinimumSize(780, 600)
        self.destination_path: Path | None = None
        self.source_path: Path | None = None
        self.destination_collections: list[dict] = []
        self.source_structure: dict | None = None
        self.candidates: list[dict] = []
        self._build_ui()
        translate_widget_tree(self, self.language)
        self._load_known_collections()

        # Préselectionner la collection actuellement ouverte dans G-Skol.
        # Le dialogue reste utilisable sans collection ouverte : l'utilisateur
        # peut alors en choisir une manuellement comme auparavant.
        host = parent
        while host is not None:
            db_path = getattr(host, "_database_path", None)
            current = getattr(host, "collection", None)
            if db_path is not None and isinstance(current, dict):
                try:
                    wanted_path = str(Path(db_path).resolve())
                    wanted_id = int(current.get("id") or 0)
                    for i in range(self.collection_combo.count()):
                        item = self.collection_combo.itemData(i)
                        if not isinstance(item, dict):
                            continue
                        item_path = str(Path(str(item.get("path") or "")).resolve()) if item.get("path") else ""
                        item_id = int(item.get("id") or 0)
                        if item_path == wanted_path and (not wanted_id or item_id == wanted_id):
                            self.collection_combo.setCurrentIndex(i)
                            self._on_destination_changed()
                            break
                except Exception:
                    pass
                break
            host = host.parentWidget() if hasattr(host, "parentWidget") else None

    @staticmethod
    def _ident(value: str) -> str:
        text = unicodedata.normalize("NFKD", str(value or ""))
        return "".join(ch.casefold() for ch in text if ch.isalnum() and not unicodedata.combining(ch))

    def _workspace_collections_folder(self) -> Path:
        """Retrouve le dossier Workspace/Collections de l'installation G-Skol."""
        folder = Path(WORKSPACE) / "Collections"
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 18)
        root.setSpacing(11)

        title = QLabel(tr("Importation de référentiels dans une collection existante", self.language))
        title.setStyleSheet("font-size: 24px; font-weight: 800;")
        root.addWidget(title)
        intro = QLabel(
            "Ajoutez ou complétez des référentiels dans une collection G-Skol existante, sans créer de fiches. "
            "G-Skol reconnaît maintenant les référentiels multi-colonnes provenant d’Access, SQLite, Excel .xlsx, CSV/TXT/TSV, ODS ou DBF. "
            "Pour Excel, seules les vraies feuilles relationnelles (une ligne = une valeur Maître et ses données Reliées) sont utilisées ; "
            "les feuilles de fiches et les réservoirs de listes indépendantes sont volontairement écartés. "
            "Les valeurs existantes sont conservées ; seules les nouvelles valeurs et associations sont ajoutées ou mises à jour."
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        dest_box = QFrame(); dest_box.setFrameShape(QFrame.Shape.StyledPanel)
        dl = QVBoxLayout(dest_box); dl.setContentsMargins(14, 12, 14, 12); dl.setSpacing(7)
        dest_heading = QLabel(tr("1. Collection G-Skol de destination", self.language))
        dest_heading.setStyleSheet("font-size: 15px; font-weight: 700;")
        dl.addWidget(dest_heading)
        row = QHBoxLayout()
        self.choose_dest_btn = QPushButton(tr("Sélectionner une collection…", self.language))
        self.choose_dest_btn.clicked.connect(self._choose_destination)
        row.addWidget(self.choose_dest_btn)
        self.collection_combo = SafeTypeComboBox(); self.collection_combo.setEnabled(True)
        self.collection_combo.currentIndexChanged.connect(self._on_destination_combo_changed)
        row.addWidget(self.collection_combo, 1)
        dl.addLayout(row)
        self.dest_label = QLabel(tr("Aucune collection sélectionnée.", self.language)); self.dest_label.setWordWrap(True)
        dl.addWidget(self.dest_label)
        root.addWidget(dest_box)

        src_box = QFrame(); src_box.setFrameShape(QFrame.Shape.StyledPanel)
        sl = QVBoxLayout(src_box); sl.setContentsMargins(14, 12, 14, 12); sl.setSpacing(7)
        sl.addWidget(QLabel(tr("2. Source des référentiels", self.language)))
        # Choix du format sous forme d’onglets, comme pour l’importation complète.
        # Ici l’habillage reste volontairement neutre : l’onglet sélectionné doit
        # seulement indiquer le format courant, sans reprendre le brun-rouge métier.
        self.source_format_tabs = QTabWidget()
        self.source_format_tabs.setDocumentMode(True)
        self.source_format_tabs.setStyleSheet(
            "QTabBar::tab { padding: 7px 15px; border: 1px solid #C4C9C6; "
            "margin-right: 1px; background: #ECEFEE; color: #929A96; }"
            "QTabBar::tab:selected { background: #FFFFFF; color: #111111; font-weight: 700; "
            "border-color: #AEB6B2; border-bottom-color: #FFFFFF; }"
            "QTabBar::tab:hover:!selected { background: #E2E6E4; color: #69716D; }"
            "QTabBar::tab:disabled { color: #A9AFAC; background: #F2F3F3; }"
        )
        self._reference_format_kinds = ["access", "excel", "text", "ods", "dbf", "sqlite"]
        for label in ["Access", "Excel .xlsx", "CSV / TXT / TSV", "ODS", "DBF", "SQLite"]:
            self.source_format_tabs.addTab(QWidget(), label)
        # Access utilise la lecture rapide de STRUCTURE : les lignes réelles ne
        # sont lues qu'au moment de l'import, après validation des correspondances.
        self.source_format_tabs.setTabEnabled(0, True)
        self.source_format_tabs.setCurrentIndex(5)
        self.source_format_tabs.currentChanged.connect(self._on_source_format_changed)
        sl.addWidget(self.source_format_tabs)

        row2 = QHBoxLayout()
        self.choose_source_btn = QPushButton(tr("Choisir une base SQLite…", self.language))
        self.choose_source_btn.clicked.connect(self._choose_source)
        row2.addWidget(self.choose_source_btn)
        self.analyse_btn = QPushButton(tr("Analyser les référentiels", self.language)); self.analyse_btn.setEnabled(False)
        self.analyse_btn.clicked.connect(self._analyse_source)
        row2.addWidget(self.analyse_btn); row2.addStretch(1)
        sl.addLayout(row2)
        self.source_label = QLabel(tr("Aucune source sélectionnée.", self.language)); self.source_label.setWordWrap(True)
        sl.addWidget(self.source_label)
        root.addWidget(src_box)

        select_row = QHBoxLayout()
        select_hint = QLabel(tr("3. Référentiels à importer — cochez uniquement ceux que vous voulez ajouter ou compléter.", self.language))
        select_hint.setStyleSheet("font-weight: 700;")
        select_row.addWidget(select_hint, 1)
        self.select_all_btn = QPushButton(tr("Tout cocher", self.language))
        self.select_all_btn.setEnabled(False)
        self.select_all_btn.clicked.connect(lambda: self._set_all_candidates_checked(True))
        select_row.addWidget(self.select_all_btn)
        self.select_none_btn = QPushButton(tr("Tout décocher", self.language))
        self.select_none_btn.setEnabled(False)
        self.select_none_btn.clicked.connect(lambda: self._set_all_candidates_checked(False))
        select_row.addWidget(self.select_none_btn)
        root.addLayout(select_row)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([tr("Référentiel / Champ", self.language), tr("Destination G-Skol", self.language), tr("Lignes", self.language)])
        # 11.7.70.20 — mode radin : la liste des tables ne réserve plus de grand vide.
        self.tree.setMinimumHeight(118)
        self.tree.setMaximumHeight(138)
        self.tree.setAlternatingRowColors(True); self.tree.setRootIsDecorated(True)
        self.tree.header().resizeSection(0, 330); self.tree.header().resizeSection(1, 360); self.tree.header().resizeSection(2, 90)
        self.tree.itemChanged.connect(self._on_candidate_item_changed)
        root.addWidget(self.tree, 1)

        self.summary = QLabel(tr("Choisissez d'abord la collection puis la source contenant les référentiels.", self.language))
        self.summary.setWordWrap(True); self.summary.setStyleSheet("font-style: italic;")
        root.addWidget(self.summary)

        buttons = QHBoxLayout(); buttons.addStretch(1)
        cancel = QPushButton(tr("Fermer", self.language)); cancel.clicked.connect(self.close); buttons.addWidget(cancel)
        self.import_btn = QPushButton(tr("Importer / compléter les référentiels…", self.language)); self.import_btn.setEnabled(False)
        self.import_btn.clicked.connect(self._perform_import); buttons.addWidget(self.import_btn)
        root.addLayout(buttons)
        translate_widget_tree(self, self.language)

    def _catalog_path_from_parent(self) -> Path | None:
        """Retrouve la base catalogue de l'application sans imposer un chemin à l'utilisateur."""
        widget = self.parent()
        while widget is not None:
            candidate = getattr(widget, "_catalog_database_path", None)
            if candidate:
                try:
                    return Path(candidate)
                except Exception:
                    pass
            startup = getattr(widget, "startup", None)
            database = getattr(startup, "database", None) if startup is not None else None
            candidate = getattr(database, "database_path", None) if database is not None else None
            if candidate:
                try:
                    return Path(candidate)
                except Exception:
                    pass
            try:
                widget = widget.parent()
            except Exception:
                break
        return None

    def _set_destination_choice(self, path: Path, collection: dict) -> None:
        self.destination_path = Path(path)
        cid = int(collection.get("id") or 0)
        name = str(collection.get("name") or "Collection")
        self.dest_label.setText(tr("✓ Collection sélectionnée : {name} — {file}", self.language).format(name=name, file=self.destination_path.name))
        self._refresh_candidates()

    def _load_known_collections(self) -> None:
        """Préremplit la liste avec les collections G-Skol du dossier Collections."""
        self.collection_combo.blockSignals(True)
        self.collection_combo.clear()
        self.destination_collections = []
        # Cherche directement dans le Workspace/Collections de cette installation.
        # Cela évite de dépendre du chemin de la base catalogue transmis par les fenêtres parentes.
        discovered = []
        folder = self._workspace_collections_folder()
        if folder.exists():
            for path in sorted(folder.iterdir(), key=lambda p: p.name.casefold()):
                if not path.is_file() or path.suffix.casefold() != ".coldb":
                    continue
                if path.name.casefold() in {"micromin3.db", ".mm3-system.db"}:
                    continue
                try:
                    rows = CollectionManager(path).inspect_collections()
                except Exception:
                    continue
                for row in rows:
                    item = dict(row)
                    item["_database_path"] = str(path.resolve())
                    discovered.append(item)
        for item in discovered:
            path_text = str(item.get("_database_path") or "")
            if not path_text:
                continue
            entry = dict(item)
            self.destination_collections.append(entry)
            label = str(entry.get("name") or Path(path_text).stem)
            self.collection_combo.addItem(label, {"path": path_text, "id": int(entry.get("id") or 0)})
        self.collection_combo.blockSignals(False)
        if self.collection_combo.count():
            self.collection_combo.setEnabled(True)
            self.collection_combo.setCurrentIndex(0)
            self._on_destination_combo_changed()
            self.dest_label.setText(self.dest_label.text() + tr("  (liste des collections G-Skol détectées)", self.language))
        else:
            self.collection_combo.setEnabled(False)
            self.dest_label.setText(tr("Aucune collection détectée automatiquement. Utilisez « Sélectionner une collection… ».", self.language))

    def _on_destination_combo_changed(self) -> None:
        data = self.collection_combo.currentData()
        if isinstance(data, dict) and data.get("path") and int(data.get("id") or 0):
            self.destination_path = Path(str(data["path"]))
            cid = int(data["id"])
            name = self.collection_combo.currentText()
            self.dest_label.setText(tr("✓ Collection sélectionnée : {name} — {file}", self.language).format(name=name, file=self.destination_path.name))
            self._refresh_candidates()
            # Fil conducteur : la prochaine étape est le choix de la source.
            try:
                self.choose_source_btn.setDefault(True)
                self.choose_source_btn.setFocus(Qt.FocusReason.OtherFocusReason)
            except Exception:
                pass

    def _choose_destination(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self, tr("Choisir une collection G-Skol existante", self.language), str(self._workspace_collections_folder()),
            tr("Collections G-Skol (*.coldb);;Tous les fichiers (*.*)", self.language)
        )
        if not filename:
            return
        path = Path(filename)
        try:
            collections = CollectionManager(path).inspect_collections()
        except Exception as exc:
            QMessageBox.warning(self, tr("Collection G-Skol invalide", self.language), str(exc)); return
        if not collections:
            QMessageBox.warning(self, tr("Collection G-Skol", self.language), tr("Aucune collection n'a été trouvée dans ce fichier.", self.language)); return
        self.destination_path = path
        self.destination_collections = [dict(item) for item in collections]
        self.collection_combo.blockSignals(True)
        self.collection_combo.clear()
        for item in collections:
            self.collection_combo.addItem(
                str(item.get("name") or "Collection"),
                {"path": str(path), "id": int(item.get("id") or 0)},
            )
        self.collection_combo.blockSignals(False)
        self.collection_combo.setEnabled(True)
        self.collection_combo.setCurrentIndex(0)
        self._on_destination_combo_changed()

    def _source_kind(self) -> str:
        try:
            index = int(self.source_format_tabs.currentIndex())
            if 0 <= index < len(self._reference_format_kinds):
                return str(self._reference_format_kinds[index])
        except Exception:
            pass
        return "sqlite"

    def _on_source_format_changed(self) -> None:
        kind = self._source_kind()
        self.source_path = None
        self.source_structure = None
        self.candidates = []
        self.tree.clear()
        self.select_all_btn.setEnabled(False)
        self.select_none_btn.setEnabled(False)
        self.import_btn.setEnabled(False)
        self.analyse_btn.setEnabled(False)
        labels = {
            "access": (tr("Choisir une base Access…", self.language), tr("Aucune base Access sélectionnée.", self.language)),
            "excel": (tr("Choisir un fichier Excel…", self.language), tr("Aucun fichier Excel sélectionné.", self.language)),
            "text": (tr("Choisir un fichier CSV / TXT / TSV…", self.language), tr("Aucun fichier texte sélectionné.", self.language)),
            "ods": (tr("Choisir un fichier ODS…", self.language), tr("Aucun fichier ODS sélectionné.", self.language)),
            "dbf": (tr("Choisir un fichier DBF…", self.language), tr("Aucun fichier DBF sélectionné.", self.language)),
            "sqlite": (tr("Choisir une base SQLite…", self.language), tr("Aucune base SQLite sélectionnée.", self.language)),
        }
        button_text, source_text = labels.get(kind, (tr("Choisir une source…", self.language), tr("Aucune source sélectionnée.", self.language)))
        self.choose_source_btn.setText(button_text)
        self.source_label.setText(source_text)
        self.summary.setText(tr("Source non sélectionnée.", self.language))
        if self.destination_path is not None and self._current_collection_id():
            try:
                self.choose_source_btn.setDefault(True)
                self.choose_source_btn.setFocus(Qt.FocusReason.OtherFocusReason)
            except Exception:
                pass

    @classmethod
    def _excel_reference_structure(cls, workbook: dict) -> dict:
        """Convertit les feuilles Excel en tables candidates de référentiels.

        Une feuille multi-colonnes est analysée comme un tableau relationnel.
        Les feuilles servant de *réservoir de listes indépendantes* aux validations
        Excel sont écartées : aligner leurs colonnes ligne par ligne créerait des
        associations fausses (par exemple un Site avec le Département d'une autre
        ligne). Cette distinction est essentielle pour les classeurs exportés par
        G-Skol et pour les classeurs métier classiques.
        """
        sheets = list(workbook.get("sheets", []) or [])

        # Repérer les feuilles utilisées comme sources de plusieurs listes
        # déroulantes indépendantes. Le lecteur XLSX a déjà résolu les
        # validations sur les champs cibles ; il suffit donc de relire leurs
        # formules. Une feuille dont plusieurs colonnes distinctes sont utilisées
        # comme sources de listes est un catalogue de listes, pas un tableau
        # relationnel Maître/Reliés.
        validation_source_columns: dict[str, set[str]] = {}
        validation_target_counts: dict[str, int] = {}
        range_re = re.compile(
            r"(?:'((?:[^']|'')+)'|([^!]+))!\$?([A-Z]{1,3})\$?\d+"
            r"(?::\$?([A-Z]{1,3})\$?\d+)?",
            flags=re.IGNORECASE,
        )
        for target_sheet in sheets:
            target_name = str(target_sheet.get("name") or "").casefold()
            for field in list(target_sheet.get("fields", []) or []):
                formula = str(field.get("excel_validation_formula") or "").strip()
                if formula:
                    validation_target_counts[target_name] = validation_target_counts.get(target_name, 0) + 1
                if formula.startswith("="):
                    formula = formula[1:].strip()
                match = range_re.fullmatch(formula)
                if not match:
                    continue
                source_sheet = (match.group(1) or match.group(2) or "").replace("''", "'").strip().casefold()
                if not source_sheet:
                    continue
                cols = validation_source_columns.setdefault(source_sheet, set())
                cols.add(str(match.group(3) or "").upper())
                cols.add(str(match.group(4) or match.group(3) or "").upper())

        tables = []

        # Les listes de validation Excel sont de vrais référentiels, même lorsqu'elles
        # sont stockées dans une feuille technique de listes indépendantes. Le lecteur
        # XLSX a déjà résolu leurs valeurs dans ``excel_reference_values``. On les
        # expose donc comme référentiels simples (un seul champ Maître), au lieu de
        # dépendre uniquement de la détection d'une feuille relationnelle.
        simple_seen = set()
        for sheet in sheets:
            for field in list(sheet.get("fields", []) or []):
                values = [str(v or "").strip() for v in list(field.get("excel_reference_values", []) or [])]
                values = [v for v in values if v]
                if not values:
                    continue
                field_name = str(field.get("name") or "").strip()
                if not field_name:
                    continue
                marker = (field_name.casefold(), tuple(v.casefold() for v in values))
                if marker in simple_seen:
                    continue
                simple_seen.add(marker)
                simple_field = dict(field)
                simple_field["type"] = "Liste"
                tables.append({
                    "name": field_name,
                    "source_kind": "Excel",
                    "fields": [simple_field],
                    "rows": len(values),
                    "rows_data": [{field_name: value} for value in values],
                    "primary_key_columns": [field_name],
                    "simple_reference": True,
                    "sheet_order": int(sheet.get("sheet_order") or 0),
                })

        for sheet in sheets:
            fields = list(sheet.get("fields", []) or [])
            rows_data = list(sheet.get("rows_data", []) or [])
            if len(fields) < 2 or not rows_data:
                continue
            sheet_name = str(sheet.get("name") or "Feuille")
            sheet_marker = sheet_name.casefold()
            independent_columns = validation_source_columns.get(sheet_marker, set())
            if len(independent_columns) >= 2:
                # Plusieurs colonnes de cette feuille alimentent séparément des
                # listes déroulantes ailleurs dans le classeur : ne jamais les
                # relier artificiellement par leur numéro de ligne.
                continue
            if validation_target_counts.get(sheet_marker, 0) >= 2:
                # Une feuille de saisie possédant plusieurs listes déroulantes
                # est une table de fiches, pas un référentiel. L'ancienne
                # détection pouvait prendre la feuille principale (313 fiches)
                # pour un gigantesque référentiel et ne connaître alors les
                # associations que pour les valeurs déjà utilisées.
                continue
            tables.append({
                "name": sheet_name,
                "source_kind": "Excel",
                "fields": fields,
                "rows": len(rows_data),
                "rows_data": rows_data,
                "primary_key_columns": [],
                "sheet_order": int(sheet.get("sheet_order") or 0),
            })
        return {"tables": tables, "format": "xlsx", "source_kind": "Excel"}

    def _choose_source(self) -> None:
        kind = self._source_kind()
        choices = {
            "access": (tr("Choisir la base Access contenant les référentiels", self.language), tr("Bases Microsoft Access (*.accdb *.mdb);;Tous les fichiers (*.*)", self.language)),
            "excel": (tr("Choisir le fichier Excel contenant les référentiels", self.language), tr("Classeurs Excel (*.xlsx);;Tous les fichiers (*.*)", self.language)),
            "text": (tr("Choisir le fichier CSV / TXT / TSV contenant les référentiels", self.language), tr("Fichiers texte (*.csv *.txt *.tsv);;Tous les fichiers (*.*)", self.language)),
            "ods": (tr("Choisir le fichier ODS contenant les référentiels", self.language), tr("Classeurs ODS (*.ods);;Tous les fichiers (*.*)", self.language)),
            "dbf": (tr("Choisir le fichier DBF contenant les référentiels", self.language), tr("Fichiers DBF (*.dbf);;Tous les fichiers (*.*)", self.language)),
            "sqlite": (tr("Choisir la base SQLite contenant les référentiels", self.language), tr("Bases SQLite (*.db *.sqlite *.sqlite3);;Tous les fichiers (*.*)", self.language)),
        }
        title, file_filter = choices.get(kind, (tr("Choisir une source contenant les référentiels", self.language), tr("Tous les fichiers (*.*)", self.language)))
        filename, _ = QFileDialog.getOpenFileName(self, title, "", file_filter)
        if not filename:
            return
        self.source_path = Path(filename); self.source_structure = None; self.candidates = []
        self.source_label.setText(tr("Source : {name}", self.language).format(name=self.source_path.name))
        self.analyse_btn.setEnabled(True); self.import_btn.setEnabled(False); self.tree.clear()
        self.select_all_btn.setEnabled(False); self.select_none_btn.setEnabled(False)
        self.summary.setText(tr("Source sélectionnée. Cliquez sur « Analyser les référentiels ».", self.language))
        try:
            self.analyse_btn.setDefault(True); self.analyse_btn.setFocus(Qt.FocusReason.OtherFocusReason)
        except Exception:
            pass

    def _current_collection_id(self) -> int:
        try:
            data = self.collection_combo.currentData()
            if isinstance(data, dict):
                return int(data.get("id") or 0)
            return int(data or 0)
        except Exception:
            return 0

    def _destination_fields(self) -> tuple[dict[str, dict], set[str]]:
        """Champs G-Skol réellement disponibles dans la collection sélectionnée.

        11.7.29 : pour l'écran Access, il est essentiel de ne jamais confondre
        un alias historique avec un champ réellement affiché dans la collection.
        On part donc de l'état réel du modèle, puis les alias ne servent qu'à la
        proposition automatique — jamais au libellé présenté à l'utilisateur.
        """
        if self.destination_path is None or not self._current_collection_id():
            return {}, set()
        cid = self._current_collection_id(); mm = ModelManager(self.destination_path)
        visible = mm.visible_fields(cid)
        by_ident: dict[str, dict] = {}
        custom = mm.custom_field_map(cid)
        overrides = {}
        try:
            with sqlite3.connect(self.destination_path) as con:
                for row in con.execute(
                    "SELECT field_key, custom_label FROM collection_model_fields "
                    "WHERE collection_id=? AND custom_label IS NOT NULL", (cid,)
                ):
                    overrides[str(row[0])] = str(row[1] or "")
        except Exception:
            pass
        for key in visible:
            if key == "record_number":
                continue
            if key in custom:
                label = str(custom[key].get("label") or key)
                info = dict(custom[key]); info.update({"key": key, "label": label, "custom": True})
            else:
                spec = FIELD_BY_KEY.get(key)
                if spec is None:
                    continue
                label = overrides.get(key) or spec.label
                info = {"key": key, "label": label, "custom": False, "field_type": spec.field_type, "referential_code": spec.referential or ""}
            # Priorité au libellé réellement visible. La clé interne reste un
            # alias secondaire pour les imports techniques.
            for alias in (label, key):
                marker = self._ident(alias)
                if marker and marker not in by_ident:
                    by_ident[marker] = info
        return by_ident, visible

    def _destination_fields_for_mapping(self) -> list[dict]:
        """Retourne la liste exacte des champs visibles G-Skol, sans alias inventé.

        Contrairement au dictionnaire d'identifiants utilisé pour faire des
        propositions, cette liste est construite directement depuis le modèle
        de la collection. L'écran de correspondance affiche donc le vrai libellé
        actuel du champ (par ex. « Site1 ») et non un nom canonique/ancien.
        """
        if self.destination_path is None or not self._current_collection_id():
            return []
        cid = self._current_collection_id(); mm = ModelManager(self.destination_path)
        custom = mm.custom_field_map(cid)
        rows = []
        try:
            with sqlite3.connect(self.destination_path) as con:
                rows = con.execute(
                    "SELECT field_key, custom_label, position, tab_position "
                    "FROM collection_model_fields WHERE collection_id=? AND visible=1 "
                    "ORDER BY CASE WHEN position IS NULL THEN 1 ELSE 0 END, position, "
                    "CASE WHEN tab_position IS NULL THEN 1 ELSE 0 END, tab_position, rowid",
                    (cid,),
                ).fetchall()
        except Exception:
            rows = []

        result: list[dict] = []
        seen: set[str] = set()
        for row in rows:
            key = str(row[0] or "")
            if not key or key == "record_number" or key in seen:
                continue
            seen.add(key)
            custom_label = str(row[1] or "").strip()
            if key in custom:
                info = dict(custom[key])
                label = custom_label or str(info.get("label") or key)
                info.update({"key": key, "label": label, "custom": True})
            else:
                spec = FIELD_BY_KEY.get(key)
                if spec is None:
                    continue
                label = custom_label or spec.label
                info = {"key": key, "label": label, "custom": False,
                        "field_type": spec.field_type, "referential_code": spec.referential or ""}
            result.append(info)

        # Sécurité pour d'anciens modèles qui n'auraient pas de ligne explicite
        # visible=1 : compléter seulement avec les champs que ModelManager déclare
        # réellement visibles, sans substituer leur libellé.
        if not result:
            by_ident, _ = self._destination_fields()
            unique = {}
            for info in by_ident.values():
                key = str(info.get("key") or "")
                if key:
                    unique[key] = dict(info)
            result = list(unique.values())
        return result

    def _build_candidates(self) -> list[dict]:
        if not self.source_structure or self.destination_path is None or not self._current_collection_id():
            return []
        dest_by_ident, _ = self._destination_fields()
        candidates = []
        source_kind = str(self.source_structure.get("source_kind") or "SQLite")
        tables = list(self.source_structure.get("tables", []) or [])

        # Access : identifier la table principale uniquement par la structure,
        # comme dans .11.7.26, puis proposer les autres tables comme référentiels.
        # Aucune ligne de données n'est lue à ce stade.
        access_main_name = ""
        if source_kind.casefold() == "access" and tables:
            scored = []
            for pos, table in enumerate(tables):
                fields = list(table.get("fields", []) or [])
                common = sum(1 for f in fields if dest_by_ident.get(self._ident(str(f.get("name") or ""))))
                scored.append((common, len(fields), int(table.get("rows") or 0), -pos, str(table.get("name") or "")))
            scored.sort(reverse=True)
            if scored:
                access_main_name = scored[0][4]

        for table in tables:
            fields = list(table.get("fields", []) or [])
            rows = list(table.get("rows_data", []) or [])
            if len(fields) < 2 and not bool(table.get("simple_reference")):
                continue
            if not fields:
                continue

            if source_kind.casefold() == "access":
                table_name = str(table.get("name") or "")
                if table_name.casefold() == access_main_name.casefold():
                    continue
                usable_fields = []
                proposals: dict[str, dict] = {}
                table_cf = table_name.casefold()
                for field in fields:
                    src = str(field.get("name") or "").strip()
                    if not src:
                        continue
                    ftype = str(field.get("type") or "").casefold()
                    if any(token in ftype for token in ("binary", "varbinary", "longvarbinary", "ole", "attachment", "image")):
                        continue
                    usable_fields.append(field)
                    dest = dest_by_ident.get(self._ident(src))
                    # Cas historique validé : Access « Site » correspond au champ
                    # G-Skol « Site1 » lorsque ce dernier existe dans la collection.
                    if not dest and self._ident(src) == self._ident("Site"):
                        dest = dest_by_ident.get(self._ident("Site1"))
                    if dest:
                        role = AccessReferenceMappingDialog.ROLE_LINKED
                        if "ima" in table_cf and self._ident(src) == self._ident("Nom"):
                            role = AccessReferenceMappingDialog.ROLE_MASTER
                        elif "gisement" in table_cf and self._ident(src) in {self._ident("Site"), self._ident("Site1")}:
                            role = AccessReferenceMappingDialog.ROLE_MASTER
                        proposals[src] = {"dest": dest, "role": role}
                if len(usable_fields) < 2 or not proposals:
                    continue
                # Si aucun Maître historique n'a été reconnu, proposer comme
                # Maître le premier champ qui possède une destination G-Skol.
                if not any(p.get("role") == AccessReferenceMappingDialog.ROLE_MASTER for p in proposals.values()):
                    for field in usable_fields:
                        src = str(field.get("name") or "")
                        if src in proposals:
                            proposals[src]["role"] = AccessReferenceMappingDialog.ROLE_MASTER
                            break
                candidates.append({
                    "table": dict(table, fields=usable_fields),
                    "source_kind": source_kind,
                    "access_proposals": proposals,
                    "master_source": "",
                    "master_dest": None,
                    "linked": [],
                })
                continue

            if len(rows) < 1:
                continue
            master_source = ""
            master_dest = None
            pk = list(table.get("primary_key_columns", []) or [])
            if len(pk) == 1:
                master_source = str(pk[0] or "")
                master_dest = dest_by_ident.get(self._ident(master_source))
            elif source_kind.casefold() in {"excel", "ods", "csv", "tsv", "txt", "csv / txt / tsv", "dbf"}:
                # Une table relationnelle de référentiel n'impose pas que la
                # valeur Maître soit unique ligne par ligne. Par exemple plusieurs
                # lignes peuvent décrire le même Site avec des données Reliées.
                # L'ancienne règle ``unique == nombre de valeurs`` écartait donc
                # des feuilles Excel parfaitement valides et conduisait à
                # « Aucun référentiel compatible ». La feuille principale de
                # fiches reste filtrée en amont par _excel_reference_structure ;
                # ici on choisit prudemment le premier champ G-Skol compatible
                # suffisamment renseigné, puis la fenêtre de correspondance laisse
                # l'utilisateur confirmer explicitement Maître / Reliés.
                scored = []
                for pos, field in enumerate(fields):
                    src = str(field.get("name") or "")
                    dest = dest_by_ident.get(self._ident(src))
                    if not dest:
                        # Compatibilité historique : Site -> Site1.
                        if self._ident(src) == self._ident("Site"):
                            dest = dest_by_ident.get(self._ident("Site1"))
                    if not dest:
                        continue
                    values = [str(r.get(src, "") or "").strip() for r in rows]
                    values = [v for v in values if v]
                    if not values:
                        continue
                    unique = len({v.casefold() for v in values})
                    coverage = len(values) / max(1, len(rows))
                    # Priorité à la première colonne compatible et aux colonnes
                    # bien renseignées ; l'unicité n'est plus une condition.
                    score = (100000 if pos == 0 else 0) + int(coverage * 10000) + unique
                    scored.append((score, pos, src, dest))
                if scored:
                    scored.sort(key=lambda x: (-x[0], x[1]))
                    _, _, master_source, master_dest = scored[0]
            if not master_source or not master_dest:
                continue
            linked = []
            for field in fields:
                src = str(field.get("name") or "")
                if self._ident(src) == self._ident(master_source):
                    continue
                if not any(str(r.get(src, "") or "").strip() for r in rows):
                    continue
                existing = dest_by_ident.get(self._ident(src))
                # Import de référentiels = données uniquement : jamais de création
                # de champ dans le modèle. Une colonne source sans destination G-Skol
                # existante est ignorée.
                if not existing:
                    continue
                linked.append({"source": src, "field": field, "existing": existing})
            if not linked and not bool(table.get("simple_reference")):
                continue
            candidates.append({
                "table": table, "master_source": master_source, "master_dest": master_dest,
                "linked": linked, "source_kind": source_kind,
            })
        return candidates

    def _selected_candidates(self) -> list[dict]:
        selected: list[dict] = []
        for index, cand in enumerate(self.candidates):
            item = self.tree.topLevelItem(index)
            if item is not None and item.checkState(0) == Qt.CheckState.Checked:
                selected.append(cand)
        return selected

    def _update_candidate_selection_state(self) -> None:
        detected = len(self.candidates)
        selected = len(self._selected_candidates()) if detected else 0
        self.select_all_btn.setEnabled(bool(detected))
        self.select_none_btn.setEnabled(bool(detected))
        self.import_btn.setEnabled(bool(selected) and self.destination_path is not None and bool(self._current_collection_id()))
        if self.source_structure is None:
            return
        if not detected:
            self.summary.setText(tr("Aucun référentiel compatible n'a été détecté pour les champs visibles de cette collection.", self.language))
            return
        is_access = any(str(c.get("source_kind") or "").casefold() == "access" for c in self.candidates)
        is_en = str(getattr(self, "language", "fr") or "fr").lower().startswith("en")
        nlinks = sum(len(c["linked"]) for c in self.candidates)
        if selected:
            if is_access:
                if is_en:
                    self.summary.setText(
                        f"{detected} Access reference list(s) detected, {selected} selected. "
                        "Master / Linked mappings will be proposed and must be confirmed before import."
                    )
                else:
                    self.summary.setText(
                        f"{detected} référentiel(s) Access détecté(s), {selected} sélectionné(s). "
                        "Les correspondances Maître / Reliés seront proposées puis devront être validées avant l'import."
                    )
            else:
                if is_en:
                    self.summary.setText(
                        f"{detected} compatible reference list(s) detected, {selected} selected, "
                        f"{nlinks} Linked field(s) detected. Safe mode: add / complete, without deletion."
                    )
                else:
                    self.summary.setText(
                        f"{detected} référentiel(s) compatible(s) détecté(s), {selected} sélectionné(s), "
                        f"{nlinks} champ(s) Relié(s) détecté(s). Mode sûr : ajouter / compléter, sans suppression."
                    )
            try:
                self.import_btn.setDefault(True)
            except Exception:
                pass
        else:
            if is_en:
                self.summary.setText(
                    f"{detected} compatible reference list(s) detected. None is selected: "
                    "check at least one reference list to start the import."
                )
            else:
                self.summary.setText(
                    f"{detected} référentiel(s) compatible(s) détecté(s). Aucun n'est sélectionné : "
                    "cochez au moins un référentiel pour lancer l'import."
                )

    def _on_candidate_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        # Seules les lignes racines représentent un référentiel sélectionnable.
        if item.parent() is None and column == 0:
            self._update_candidate_selection_state()

    def _set_all_candidates_checked(self, checked: bool) -> None:
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        self.tree.blockSignals(True)
        try:
            for index in range(self.tree.topLevelItemCount()):
                item = self.tree.topLevelItem(index)
                if item is not None:
                    item.setCheckState(0, state)
        finally:
            self.tree.blockSignals(False)
        self._update_candidate_selection_state()

    def _refresh_candidates(self) -> None:
        self.tree.blockSignals(True)
        try:
            self.tree.clear(); self.candidates = self._build_candidates()
            for cand in self.candidates:
                table = cand["table"]
                if str(cand.get("source_kind") or "").casefold() == "access":
                    item = QTreeWidgetItem([
                        f"{table.get('name')} — correspondance à valider",
                        tr("Maître / Reliés proposés par G-Skol", self.language), str(table.get("rows") or 0)
                    ])
                    item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                    item.setCheckState(0, Qt.CheckState.Checked)
                    self.tree.addTopLevelItem(item)
                    proposals = dict(cand.get("access_proposals") or {})
                    for field in list(table.get("fields", []) or []):
                        src = str(field.get("name") or "")
                        prop = dict(proposals.get(src) or {})
                        dest = prop.get("dest")
                        if dest:
                            role = str(prop.get("role") or AccessReferenceMappingDialog.ROLE_LINKED)
                            target = f"{role} → {dest.get('label') or dest.get('key')}"
                        else:
                            target = tr("Ne pas importer", self.language)
                        item.addChild(QTreeWidgetItem([src, target, ""]))
                    item.setExpanded(True)
                    continue

                md = cand["master_dest"]
                is_en = str(getattr(self, "language", "fr") or "fr").lower().startswith("en")
                master_word = "Master" if is_en else "Maître"
                item = QTreeWidgetItem([
                    f"{table.get('name')} — {master_word}: {cand['master_source']}",
                    f"{master_word} G-Skol: {md.get('label')}", str(table.get("rows") or 0)
                ])
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(0, Qt.CheckState.Checked)
                self.tree.addTopLevelItem(item)
                for link in cand["linked"]:
                    ex = link.get("existing")
                    target = str(ex.get("label")) if ex else tr("Ne pas importer", self.language)
                    item.addChild(QTreeWidgetItem([str(link["source"]), target, ""]))
                item.setExpanded(True)
        finally:
            self.tree.blockSignals(False)
        self._update_candidate_selection_state()
        if self.source_structure is not None and self.candidates:
            try:
                self.tree.setFocus(Qt.FocusReason.OtherFocusReason)
            except Exception:
                pass

    def _analyse_source(self) -> None:
        if self.source_path is None:
            return
        kind = self._source_kind()
        try:
            if kind == "access":
                busy = QProgressDialog(
                    tr("Analyse de la structure Access…\nLecture des tables et des champs uniquement.", self.language),
                    "", 0, 0, self
                )
                busy.setWindowTitle(tr("Analyse des référentiels Access", self.language))
                busy.setCancelButton(None)
                busy.setWindowModality(Qt.WindowModality.ApplicationModal)
                busy.setMinimumDuration(0)
                busy.setAutoClose(False); busy.setAutoReset(False)
                busy.show()
                QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
                QApplication.processEvents()
                try:
                    self.source_structure = CollectionImportDialog._read_access_structure(self.source_path)
                finally:
                    busy.close()
                    QApplication.restoreOverrideCursor()
                    QApplication.processEvents()
                self.source_structure["source_kind"] = "Access"
                label = "Access"
            elif kind == "excel":
                workbook = CollectionImportDialog._read_xlsx_workbook(self.source_path)
                self.source_structure = self._excel_reference_structure(workbook)
                # Certains classeurs ne possèdent pas de feuille relationnelle
                # dédiée : les relations de référentiel sont alors portées par
                # la feuille de fiches elle-même. On conserve d'abord le filtre
                # prudent ci-dessus ; si celui-ci ne laisse aucune table, on
                # propose les feuilles multi-colonnes réellement renseignées.
                # La fenêtre de correspondance Maître / Reliés reste l'étape de
                # validation explicite avant toute écriture.
                if not list(self.source_structure.get("tables", []) or []):
                    fallback_tables = []
                    for sheet in list(workbook.get("sheets", []) or []):
                        fields = list(sheet.get("fields", []) or [])
                        rows_data = list(sheet.get("rows_data", []) or [])
                        if len(fields) < 2 or not rows_data:
                            continue
                        fallback_tables.append({
                            "name": str(sheet.get("name") or "Feuille"),
                            "source_kind": "Excel",
                            "fields": fields,
                            "rows": len(rows_data),
                            "rows_data": rows_data,
                            "primary_key_columns": [],
                            "sheet_order": int(sheet.get("sheet_order") or 0),
                        })
                    self.source_structure = {
                        "tables": fallback_tables, "format": "xlsx",
                        "source_kind": "Excel", "fallback_record_sheets": True,
                    }
                label = "Excel"
            elif kind == "text":
                self.source_structure = CollectionImportDialog._read_delimited_text(self.source_path)
                self.source_structure["source_kind"] = str(self.source_structure.get("format") or "CSV / TXT / TSV")
                label = "CSV / TXT / TSV"
            elif kind == "ods":
                workbook = CollectionImportDialog._read_ods_workbook(self.source_path)
                # ODS ne possède pas les validations Excel utilisées pour distinguer
                # les réservoirs de listes ; on ne conserve que les feuilles
                # multi-colonnes réellement renseignées et la détection des
                # candidats reste prudente dans _build_candidates.
                tables = []
                for sheet in list(workbook.get("sheets", []) or []):
                    fields = list(sheet.get("fields", []) or [])
                    rows_data = list(sheet.get("rows_data", []) or [])
                    if len(fields) < 2 or not rows_data:
                        continue
                    tables.append({
                        "name": str(sheet.get("name") or "Feuille"),
                        "source_kind": "ODS",
                        "fields": fields,
                        "rows": len(rows_data),
                        "rows_data": rows_data,
                        "primary_key_columns": [],
                        "sheet_order": int(sheet.get("sheet_order") or 0),
                    })
                self.source_structure = {"tables": tables, "format": "ODS", "source_kind": "ODS"}
                label = "ODS"
            elif kind == "dbf":
                self.source_structure = CollectionImportDialog._read_dbf_file(self.source_path)
                self.source_structure["source_kind"] = "DBF"
                label = "DBF"
            else:
                self.source_structure = CollectionImportDialog._read_sqlite_database(self.source_path)
                self.source_structure["source_kind"] = "SQLite"
                label = "SQLite"
        except Exception as exc:
            QMessageBox.warning(self, f"Analyse {label if 'label' in locals() else 'source'} impossible", str(exc)); return
        self._refresh_candidates()

    @staticmethod
    def _normalize_access_hyperlink(value: object) -> str:
        """Décoder la représentation interne d'un champ Hyperlien Access.

        Access peut restituer un hyperlien sous la forme
        ``Texte affiché#Adresse#Sous-adresse#Info-bulle`` ou, plus simplement,
        ``#https://exemple/#``.  G-Skol doit conserver l'adresse exploitable et non
        les séparateurs ``#`` propres à Access.  Les textes ordinaires restent
        strictement inchangés.
        """
        text = "" if value is None else str(value).strip()
        if "#" not in text:
            return text

        parts = text.split("#")
        # Chercher d'abord une vraie adresse Internet dans les segments Access.
        for part in parts:
            candidate = part.strip()
            if candidate.casefold().startswith(("http://", "https://", "ftp://", "mailto:")):
                return candidate

        # Forme Access standard : affichage#adresse#sous-adresse#info-bulle.
        # Ne l'appliquer que si le deuxième segment ressemble réellement à une
        # adresse afin de ne jamais altérer un texte contenant un # ordinaire.
        if len(parts) >= 2:
            candidate = parts[1].strip()
            if candidate and ("://" in candidate or candidate.casefold().startswith(("www.", "mailto:"))):
                return candidate

        return text

    @staticmethod
    def _source_type_to_mm3(field: dict) -> str:
        t = str(field.get("type") or "").casefold()
        if "monét" in t or "monet" in t or "currency" in t:
            return "currency"
        if "nombre" in t or "numeric" in t:
            return "numeric"
        if "date" in t:
            return "date"
        if "off" in t or "bool" in t:
            return "boolean"
        if "lien" in t or "url" in t:
            return "link"
        return "text"

    def _perform_import(self) -> None:
        if self.destination_path is None or not self.candidates or not self._current_collection_id():
            return
        selected_candidates = self._selected_candidates()
        if not selected_candidates:
            QMessageBox.information(self, tr("Aucun référentiel sélectionné", self.language), tr("Cochez au moins un référentiel à importer.", self.language))
            return
        cid = self._current_collection_id()
        collection_name = self.collection_combo.currentText()

        # 11.7.48 — Correspondance explicite pour TOUS les imports de référentiels.
        # La même fenêtre est utilisée pour Access, Excel, ODS, CSV/TXT/TSV, DBF
        # et SQLite. Aucune création de champ n'est automatique : l'utilisateur
        # doit choisir explicitement « Créer » dans la liste de destination.
        destination_fields = self._destination_fields_for_mapping()
        for cand in selected_candidates:
            table = cand.get("table") or {}
            proposals = dict(cand.get("access_proposals") or {})
            if not proposals:
                # Construire les propositions existantes pour les sources non Access.
                master_source = str(cand.get("master_source") or "")
                master_dest = cand.get("master_dest")
                if master_source and isinstance(master_dest, dict):
                    proposals[master_source] = {"dest": dict(master_dest), "role": AccessReferenceMappingDialog.ROLE_MASTER}
                for link in list(cand.get("linked", []) or []):
                    src = str(link.get("source") or "")
                    existing = link.get("existing")
                    if src and isinstance(existing, dict):
                        proposals[src] = {"dest": dict(existing), "role": AccessReferenceMappingDialog.ROLE_LINKED}

            source_fields = list(table.get("fields", []) or [])

            # G-Skol 1.0.210.3 — un référentiel simple déjà reconnu n'a pas à
            # repasser par une confirmation Maître/Relié. S'il n'existe qu'une
            # seule colonne source et qu'elle possède une destination G-Skol
            # existante, la correspondance 1 Maître / 0 Relié est sans ambiguïté
            # et est donc validée automatiquement. Les cas multicolonnes, les
            # créations de champs et les correspondances ambiguës restent
            # volontairement soumis à la fenêtre de validation.
            auto_mapping = None
            if len(source_fields) == 1:
                src = str(source_fields[0].get("name") or "")
                prop = dict(proposals.get(src) or {})
                dest = prop.get("dest")
                role = str(prop.get("role") or "")
                if (
                    src
                    and role == AccessReferenceMappingDialog.ROLE_MASTER
                    and isinstance(dest, dict)
                    and not dest.get("create")
                    and str(dest.get("key") or "")
                ):
                    auto_mapping = {
                        "master_source": src,
                        "master_dest": dict(dest),
                        "linked": [],
                    }

            if auto_mapping is None:
                dlg = AccessReferenceMappingDialog(
                    str(table.get("name") or "Référentiel"),
                    source_fields,
                    destination_fields,
                    proposals,
                    self,
                    self.language,
                )
                if dlg.exec() != QDialog.DialogCode.Accepted or not dlg.mapping:
                    return
                mapping_result = dlg.mapping
            else:
                mapping_result = auto_mapping

            cand["master_source"] = str(mapping_result["master_source"])
            cand["master_dest"] = dict(mapping_result["master_dest"])
            cand["linked"] = [
                {
                    "source": str(x["source"]),
                    "field": next((f for f in source_fields if str(f.get("name") or "") == str(x["source"])), {}),
                    "existing": dict(x["dest"]) if not x.get("create") else None,
                    "mapped_dest": dict(x["dest"]),
                    "create": bool(x.get("create")),
                }
                for x in mapping_result.get("linked", [])
            ]

        box = QMessageBox(self); box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle(tr("Importer les référentiels ?", self.language))
        box.setText(
            tr("Importer {count} référentiel(s) sélectionné(s) dans « {name} » ?", self.language).format(count=len(selected_candidates), name=collection_name)
            + "\n\n"
            + tr("Les référentiels décochés seront ignorés. Les valeurs existantes seront conservées. Seules les correspondances que vous venez de valider seront utilisées. Les champs marqués « Créer » seront ajoutés explicitement à la collection. Les nouvelles valeurs seront ajoutées et les associations Maître / Relié à seront complétées. Aucune fiche ne sera supprimée.", self.language)
        )
        yes = box.addButton(tr("Oui", self.language), QMessageBox.ButtonRole.YesRole); no = box.addButton(tr("Non", self.language), QMessageBox.ButtonRole.NoRole)
        box.setDefaultButton(no); box.exec()
        if box.clickedButton() is not yes:
            return

        progress = QProgressDialog(
            tr("Import / complément des référentiels en cours…\nAnalyse des relations et mise à jour de la collection.", self.language),
            "", 0, max(4, len(selected_candidates) * 4), self
        )
        progress.setWindowTitle(tr("Import de référentiels en cours", self.language))
        progress.setCancelButton(None)
        progress.setWindowModality(Qt.WindowModality.ApplicationModal)
        progress.setMinimumDuration(0)
        progress.setAutoClose(False); progress.setAutoReset(False)
        progress.setValue(0); progress.show()
        QApplication.processEvents()
        self.import_btn.setEnabled(False)

        mm = ModelManager(self.destination_path); rm = ReferentialManager(self.destination_path)
        dest_by_ident, _ = self._destination_fields()
        total_rows = total_links = total_values = created_fields = backfilled = 0
        total_list_values = 0

        def _created_field_type(source_field: dict, role: str) -> str:
            # Un champ de référentiel créé explicitement devient par défaut une
            # Liste/Référentiel. Les types manifestement spécialisés sont préservés.
            source_type = str(source_field.get("type") or "")
            source_name = str(source_field.get("name") or "")
            physical = AccessFieldMappingDialog._physical_mm3_type(source_type, source_name, source_field)
            return {
                "Nombre": "numeric",
                "Monétaire": "currency",
                "Date": "date",
                "Bouton On / Off": "boolean",
                "Lien (Internet ou autre)": "link",
            }.get(physical, "list")

        def _resolve_destination(dest: dict, source_name: str, source_field: dict, role: str) -> dict:
            nonlocal created_fields, destination_fields, dest_by_ident
            if not isinstance(dest, dict) or not dest.get("create"):
                return dict(dest or {})
            label = str(source_name or source_field.get("name") or tr("Nouveau champ", self.language)).strip() or tr("Nouveau champ", self.language)
            field_type = _created_field_type(source_field, role)
            created = mm.create_custom_field(cid, label, field_type)
            info = dict(created or {})
            info.update({
                "key": str(info.get("field_key") or info.get("key") or ""),
                "label": str(info.get("label") or label),
                "custom": True,
                "field_type": str(info.get("field_type") or field_type),
                "referential_code": str(info.get("referential_code") or ""),
            })
            if not info["key"]:
                # create_custom_field retourne normalement field_key ; relecture de
                # sécurité pour les versions de collection plus anciennes.
                refreshed = mm.custom_field_map(cid)
                match = next((dict(v) for v in refreshed.values() if str(v.get("label") or "").casefold() == label.casefold()), {})
                if match:
                    info.update(match); info["key"] = str(match.get("field_key") or match.get("key") or "")
            if not info.get("key"):
                raise ValueError(f"Le champ « {label} » n'a pas pu être créé.")
            created_fields += 1
            destination_fields = self._destination_fields_for_mapping()
            dest_by_ident, _ = self._destination_fields()
            return info

        def referential_code_for_field(field_key: str) -> str:
            """Retrouve le vrai code de référentiel d'un champ G-Skol.

            Le champ peut être standard ou personnalisé. Cette résolution ne dépend
            pas du libellé affiché (ex. Site renommé Site1), ce qui évite de remplir
            collection_reference_data sans alimenter la liste visible correspondante.
            """
            key = str(field_key or "")
            if not key:
                return ""
            spec = FIELD_BY_KEY.get(key)
            if spec is not None and str(spec.referential or ""):
                return str(spec.referential or "")
            custom_info = mm.custom_field_map(cid).get(key)
            if custom_info:
                code = str(custom_info.get("referential_code") or "")
                if code:
                    return code
            # Compatibilité avec d'anciennes collections : certaines définitions
            # existent déjà alors que leur code n'est plus recopié dans la métadonnée
            # du champ personnalisé. Le code identique au field_key est prioritaire.
            try:
                with sqlite3.connect(self.destination_path) as con:
                    row = con.execute(
                        "SELECT code FROM referential_definitions WHERE collection_id=? AND code=?",
                        (int(cid), key),
                    ).fetchone()
                    if row:
                        return str(row[0] or "")
            except Exception:
                pass
            return ""

        try:
            for cand_index, cand in enumerate(selected_candidates, start=1):
                table_name = str(cand.get("table", {}).get("name", ""))
                progress.setLabelText(
                    f"Import du référentiel « {table_name} »…\n"
                    "Lecture des données sélectionnées puis mise à jour des relations."
                )
                QApplication.processEvents()

                if str(cand.get("source_kind") or "").casefold() == "access":
                    columns = [str(cand.get("master_source") or "")]
                    columns += [str(link.get("source") or "") for link in cand.get("linked", [])]
                    columns = [c for c in dict.fromkeys(columns) if c]
                    progress.setLabelText(
                        f"Import du référentiel « {table_name} »…\n"
                        "Lecture des lignes Access sélectionnées…"
                    )
                    progress.setValue((cand_index - 1) * 4 + 1)
                    QApplication.processEvents()
                    bundle = CollectionImportDialog._read_access_bundle(
                        self.source_path, [{"table": table_name, "columns": columns}]
                    )
                    cand["table"]["rows_data"] = list(bundle.get(table_name, []) or [])
                    progress.setValue((cand_index - 1) * 4 + 2)
                    QApplication.processEvents()

                master_source_name = str(cand.get("master_source") or "")
                master_source_field = next((f for f in cand.get("table", {}).get("fields", []) if str(f.get("name") or "") == master_source_name), {})
                master = _resolve_destination(dict(cand.get("master_dest") or {}), master_source_name, master_source_field, AccessReferenceMappingDialog.ROLE_MASTER)
                cand["master_dest"] = master
                master_key = str(master.get("key") or "")
                if not master_key:
                    continue
                # Assurer que le Maître personnalisé est bien de type Liste/Référentiel.
                if bool(master.get("custom")) and str(master.get("field_type") or "") != "list":
                    analysis = mm.analyze_custom_field_type_change(cid, master_key, "list")
                    if not analysis.get("compatible"):
                        raise ValueError(f"Le champ Maître « {master.get('label')} » ne peut pas être converti sans perte en Liste / Référentiel.")
                    mm.update_custom_field(cid, master_key, field_type="list")
                    master = mm.custom_field_map(cid).get(master_key, master)

                linked_map = []
                for link in cand["linked"]:
                    src = str(link["source"])
                    mapped = link.get("mapped_dest")
                    if isinstance(mapped, dict) and mapped.get("create"):
                        mapped = _resolve_destination(mapped, src, dict(link.get("field") or {}), AccessReferenceMappingDialog.ROLE_LINKED)
                        link["mapped_dest"] = mapped
                    if isinstance(mapped, dict) and str(mapped.get("key") or ""):
                        linked_key = str(mapped.get("key") or "")
                    else:
                        existing = dest_by_ident.get(self._ident(src))
                        linked_key = str(existing.get("key") or "") if existing else ""
                    if linked_key and linked_key != master_key:
                        linked_map.append((src, linked_key))

                rows_to_import = []
                master_values = []
                list_values_by_key: dict[str, list[str]] = {master_key: master_values}
                master_source = str(cand["master_source"])
                for source_row in list(cand["table"].get("rows_data", []) or []):
                    master_value = str(source_row.get(master_source, "") or "").strip()
                    if not master_value:
                        continue
                    converted = {master_key: master_value}; master_values.append(master_value)
                    for src, linked_key in linked_map:
                        raw = source_row.get(src, "")
                        value = self._normalize_access_hyperlink(raw)
                        converted[linked_key] = value
                        if value:
                            list_values_by_key.setdefault(linked_key, []).append(value)
                    rows_to_import.append(converted)
                if not rows_to_import:
                    continue

                progress.setLabelText(
                    f"Import du référentiel « {table_name} »…\n"
                    "Enregistrement des relations Maître / Relié…"
                )
                stats = mm.import_reference_rows(cid, master_key, rows_to_import)
                total_rows += int(stats.get("rows", 0)); total_values += int(stats.get("values", 0)); total_links += len(linked_map)
                progress.setValue((cand_index - 1) * 4 + 3)
                QApplication.processEvents()

                # Alimenter les vraies listes visibles de Gestion des référentiels.
                # .27 enregistrait correctement collection_reference_data mais ne
                # remplissait pas toujours referential_values (et uniquement le
                # Maître). Ici le Maître ET chaque Relié de type Liste/Référentiel
                # reçoivent toutes leurs valeurs importées.
                for field_key, values in list_values_by_key.items():
                    ref_code = referential_code_for_field(field_key)
                    if not ref_code:
                        continue
                    list_stats = rm.add_values_bulk(cid, ref_code, values)
                    total_list_values += int(list_stats.get("added", 0))

                progress.setLabelText(
                    f"Import du référentiel « {table_name} »…\n"
                    "Mise à jour des listes déroulantes G-Skol…"
                )
                progress.setValue(cand_index * 4)
                QApplication.processEvents()

            progress.setLabelText("Finalisation des relations et complément des fiches…")
            QApplication.processEvents()
            backfilled = mm.backfill_linked_blanks(cid)
        except Exception as exc:
            progress.close(); self.import_btn.setEnabled(True)
            QMessageBox.critical(self, tr("Import de référentiels interrompu", self.language), str(exc)); return

        progress.setValue(max(4, len(selected_candidates) * 4)); progress.close(); self.import_btn.setEnabled(True)
        self.summary.setText(
            f"✓ Import terminé : {len(selected_candidates)} référentiel(s) sélectionné(s), {total_rows} ligne(s), "
            f"{total_links} liaison(s), {created_fields} champ(s) G-Skol créé(s)."
        )
        if str(getattr(self, "language", "fr") or "fr").lower().startswith("en"):
            report_text = (
                f"Import completed into « {collection_name} ».\n\n"
                f"Reference lists imported: {len(selected_candidates)}\nReference rows: {total_rows}\n"
                f"Linked fields: {total_links}\nFields created: {created_fields}\nLinked values saved: {total_values}\n"
                f"New values added to lists: {total_list_values}\n"
                f"Records completed: {backfilled}"
            )
        else:
            report_text = (
                f"Import terminé dans « {collection_name} ».\n\n"
                f"Référentiels importés : {len(selected_candidates)}\nLignes de référence : {total_rows}\n"
                f"Champs Reliés : {total_links}\nChamps créés : {created_fields}\nValeurs reliées enregistrées : {total_values}\n"
                f"Nouvelles valeurs ajoutées aux listes : {total_list_values}\n"
                f"Fiches complétées : {backfilled}"
            )
        QMessageBox.information(
            self, tr("Import de référentiels terminé", self.language), report_text
        )



class CollectionImportDialog(QDialog):
    """Importation d'une source externe et création d'une nouvelle collection MM3."""

    def __init__(self, parent: QWidget | None = None, language: str = "fr") -> None:
        super().__init__(parent)
        self.language = str(language or "fr")
        self.setWindowTitle(tr("Importation et création d’une collection", self.language))
        self.resize(940, 760)
        self.setMinimumSize(800, 650)
        self.setModal(False)

        self.access_source: Path | None = None
        self.access_structure: dict | None = None
        self.selected_access_table: dict | None = None
        self.access_field_mapping: list[dict] | None = None
        self.excel_source: Path | None = None
        self.excel_structure: dict | None = None
        self.selected_excel_sheet: dict | None = None
        self.excel_field_mapping: list[dict] | None = None
        self.text_source: Path | None = None
        self.text_structure: dict | None = None
        self.selected_text_table: dict | None = None
        self.text_field_mapping: list[dict] | None = None
        self.ods_source: Path | None = None
        self.ods_structure: dict | None = None
        self.selected_ods_sheet: dict | None = None
        self.ods_field_mapping: list[dict] | None = None
        self.dbf_source: Path | None = None
        self.dbf_structure: dict | None = None
        self.selected_dbf_table: dict | None = None
        self.dbf_field_mapping: list[dict] | None = None
        self.sqlite_source: Path | None = None
        self.sqlite_structure: dict | None = None
        self.selected_sqlite_table: dict | None = None
        self.sqlite_field_mapping: list[dict] | None = None
        self.mm3_source: Path | None = None
        self.mm3_collections: list[dict] = []
        self._preview_window = None
        self._mapping_window = None
        self._excel_preview_window = None
        self._excel_mapping_window = None
        self._text_preview_window = None
        self._text_mapping_window = None
        self._ods_preview_window = None
        self._ods_mapping_window = None
        self._dbf_preview_window = None
        self._dbf_mapping_window = None
        self._sqlite_preview_window = None
        self._sqlite_mapping_window = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 22)
        layout.setSpacing(14)

        title = QLabel(tr("Importation et création d’une collection", self.language))
        title.setStyleSheet("font-size: 22px; font-weight: 700;")
        layout.addWidget(title)

        intro = QLabel(
            tr("Créez une nouvelle collection G-Skol à partir d’une source externe. Choisissez d’abord le format ; G-Skol analyse ensuite la source avant toute création.", self.language)
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("font-size: 13px;")
        layout.addWidget(intro)

        access_box = QFrame()
        access_box.setFrameShape(QFrame.Shape.StyledPanel)
        access_layout = QVBoxLayout(access_box)
        access_layout.setContentsMargins(18, 16, 18, 16)
        access_layout.setSpacing(10)

        access_title = QLabel("Microsoft Access")
        access_title.setStyleSheet("font-size: 16px; font-weight: 700;")
        access_layout.addWidget(access_title)

        access_desc = QLabel(
            tr("Choisissez une base .accdb ou .mdb. G-Skol peut maintenant en examiner la structure sans importer ni modifier aucune donnée.", self.language)
        )
        access_desc.setWordWrap(True)
        access_layout.addWidget(access_desc)

        choose_row = QHBoxLayout()
        self.choose_access_btn = QPushButton(tr("Choisir une base Access…", self.language))
        self.choose_access_btn.clicked.connect(self._choose_access_file)
        choose_row.addWidget(self.choose_access_btn)

        self.analyse_access_btn = QPushButton(tr("Analyser la base", self.language))
        self.analyse_access_btn.setEnabled(False)
        self.analyse_access_btn.clicked.connect(self._analyse_access_file)
        choose_row.addWidget(self.analyse_access_btn)
        choose_row.addStretch(1)
        access_layout.addLayout(choose_row)

        self.source_label = QLabel(tr("Aucun fichier Access sélectionné.", self.language))
        self.source_label.setWordWrap(True)
        self.source_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.source_label.setStyleSheet("padding: 8px; background: rgba(255,255,255,0.55);")
        access_layout.addWidget(self.source_label)

        self.analysis_summary = QLabel(
            tr("Après analyse, les tables et leurs champs apparaîtront ci-dessous.", self.language)
        )
        self.analysis_summary.setWordWrap(True)
        self.analysis_summary.setStyleSheet("font-style: italic;")
        access_layout.addWidget(self.analysis_summary)

        self.structure_tree = QTreeWidget()
        self.structure_tree.setHeaderLabels([tr("Table / Champ", self.language), tr("Type", self.language), tr("Lignes", self.language)])
        self.structure_tree.setRootIsDecorated(True)
        self.structure_tree.setAlternatingRowColors(True)
        # La liste est la SEULE zone qui peut perdre de la hauteur sur un
        # petit écran. Son ascenseur prend alors naturellement le relais.
        self.structure_tree.setMinimumHeight(115)
        self.structure_tree.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.structure_tree.header().setStretchLastSection(False)
        self.structure_tree.header().resizeSection(0, 450)
        self.structure_tree.header().resizeSection(1, 180)
        self.structure_tree.header().resizeSection(2, 90)
        self.structure_tree.itemSelectionChanged.connect(self._on_structure_selection_changed)
        self.structure_tree.itemDoubleClicked.connect(self._on_structure_double_clicked)
        access_layout.addWidget(self.structure_tree, 1)

        # Pied de zone indépendant : Qt lui réserve toujours sa hauteur propre.
        # Il ne peut donc plus remonter ni être peint par-dessus la liste.
        source_footer = QFrame()
        source_footer.setFrameShape(QFrame.Shape.NoFrame)
        source_footer.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        source_footer_layout = QVBoxLayout(source_footer)
        source_footer_layout.setContentsMargins(0, 6, 0, 0)
        source_footer_layout.setSpacing(7)

        table_choice_row = QHBoxLayout()
        table_choice_row.setContentsMargins(0, 3, 0, 0)
        table_choice_row.addStretch(1)
        self.choose_table_btn = QPushButton(tr("Choisir cette table", self.language))
        self.choose_table_btn.setEnabled(False)
        self.choose_table_btn.clicked.connect(self._choose_selected_table)
        table_choice_row.addWidget(self.choose_table_btn)
        self.preview_btn = QPushButton(tr("Aperçu des données…", self.language))
        self.preview_btn.setEnabled(False)
        self.preview_btn.clicked.connect(self._open_data_preview)
        table_choice_row.addWidget(self.preview_btn)
        self.mapping_btn = QPushButton(tr("Correspondance des champs…", self.language))
        self.mapping_btn.setEnabled(False)
        self.mapping_btn.clicked.connect(self._open_field_mapping)
        table_choice_row.addWidget(self.mapping_btn)
        source_footer_layout.addLayout(table_choice_row)

        self.table_choice_label = QLabel(
            tr("Sélectionnez une table dans la liste ci-dessus. Les lignes de champs ne sont pas sélectionnables comme source.", self.language)
        )
        self.table_choice_label.setWordWrap(True)
        source_footer_layout.addWidget(self.table_choice_label)

        self.next_step_label = QLabel(
            tr("Après validation de la table source, l’étape suivante préparera la correspondance entre les champs Access et les champs G-Skol.", self.language)
        )
        self.next_step_label.setWordWrap(True)
        self.next_step_label.setStyleSheet("font-style: italic;")
        source_footer_layout.addWidget(self.next_step_label)

        import_row = QHBoxLayout()
        import_row.addStretch(1)
        self.real_import_btn = QPushButton(tr("Créer la collection G-Skol et importer…", self.language))
        self.real_import_btn.setEnabled(False)
        self.real_import_btn.clicked.connect(self._start_real_import)
        import_row.addWidget(self.real_import_btn)
        source_footer_layout.addLayout(import_row)

        access_layout.addWidget(source_footer, 0)
        access_layout.setStretchFactor(self.structure_tree, 1)
        access_layout.setStretchFactor(source_footer, 0)

        # Deux formats déjà opérationnels partagent le même module sans
        # allonger la fenêtre sur les écrans portables.
        source_tabs = QTabWidget()
        # Le choix du format d'import est volontairement mis en évidence :
        # brun-rouge MM3 au repos, brun-rouge soutenu pour l'onglet actif.
        source_tabs.setStyleSheet(
            "QTabBar::tab {"
            " color: #7B3328;"
            " background: #F3E5E0;"
            " border: 1px solid #B46A59;"
            " border-bottom: none;"
            " padding: 7px 18px;"
            " margin-right: 2px;"
            " font-weight: 700;"
            "}"
            "QTabBar::tab:selected {"
            " color: white;"
            " background: #9B4939;"
            "}"
            "QTabBar::tab:hover:!selected {"
            " background: #E8CFC7;"
            "}"
        )
        source_tabs.addTab(access_box, "Access")

        excel_box = QFrame()
        excel_box.setFrameShape(QFrame.Shape.StyledPanel)
        excel_layout = QVBoxLayout(excel_box)
        excel_layout.setContentsMargins(18, 16, 18, 16)
        excel_layout.setSpacing(10)

        excel_title = QLabel("Microsoft Excel (.xlsx)")
        excel_title.setStyleSheet("font-size: 16px; font-weight: 700;")
        excel_layout.addWidget(excel_title)

        excel_desc = QLabel(
            tr("Choisissez un classeur .xlsx. G-Skol analyse les feuilles, les en-têtes et les types de cellules sans modifier le fichier source. Les images intégrées au classeur ne sont pas importées dans cette première version.", self.language)
        )
        excel_desc.setWordWrap(True)
        excel_layout.addWidget(excel_desc)

        excel_choose_row = QHBoxLayout()
        self.choose_excel_btn = QPushButton(tr("Choisir un fichier Excel…", self.language))
        self.choose_excel_btn.clicked.connect(self._choose_excel_file)
        excel_choose_row.addWidget(self.choose_excel_btn)
        self.analyse_excel_btn = QPushButton(tr("Analyser le classeur", self.language))
        self.analyse_excel_btn.setEnabled(False)
        self.analyse_excel_btn.clicked.connect(self._analyse_excel_file)
        excel_choose_row.addWidget(self.analyse_excel_btn)
        excel_choose_row.addStretch(1)
        excel_layout.addLayout(excel_choose_row)

        self.excel_source_label = QLabel(tr("Aucun fichier Excel sélectionné.", self.language))
        self.excel_source_label.setWordWrap(True)
        self.excel_source_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.excel_source_label.setStyleSheet("padding: 8px; background: rgba(255,255,255,0.55);")
        excel_layout.addWidget(self.excel_source_label)

        self.excel_analysis_summary = QLabel(
            tr("Après analyse, les feuilles et leurs colonnes apparaîtront ci-dessous.", self.language)
        )
        self.excel_analysis_summary.setWordWrap(True)
        self.excel_analysis_summary.setStyleSheet("font-style: italic;")
        excel_layout.addWidget(self.excel_analysis_summary)

        self.excel_structure_tree = QTreeWidget()
        self.excel_structure_tree.setHeaderLabels([tr("Feuille / Colonne", self.language), tr("Type détecté", self.language), tr("Lignes", self.language)])
        self.excel_structure_tree.setRootIsDecorated(True)
        self.excel_structure_tree.setAlternatingRowColors(True)
        self.excel_structure_tree.setMinimumHeight(115)
        self.excel_structure_tree.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.excel_structure_tree.header().setStretchLastSection(False)
        self.excel_structure_tree.header().resizeSection(0, 450)
        self.excel_structure_tree.header().resizeSection(1, 180)
        self.excel_structure_tree.header().resizeSection(2, 90)
        self.excel_structure_tree.itemSelectionChanged.connect(self._on_excel_structure_selection_changed)
        self.excel_structure_tree.itemDoubleClicked.connect(self._on_excel_structure_double_clicked)
        excel_layout.addWidget(self.excel_structure_tree, 1)

        excel_footer = QFrame()
        excel_footer.setFrameShape(QFrame.Shape.NoFrame)
        excel_footer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        excel_footer_layout = QVBoxLayout(excel_footer)
        excel_footer_layout.setContentsMargins(0, 6, 0, 0)
        excel_footer_layout.setSpacing(7)

        excel_action_row = QHBoxLayout()
        excel_action_row.setContentsMargins(0, 3, 0, 0)
        excel_action_row.addStretch(1)
        self.choose_sheet_btn = QPushButton(tr("Choisir cette feuille", self.language))
        self.choose_sheet_btn.setEnabled(False)
        self.choose_sheet_btn.clicked.connect(self._choose_selected_excel_sheet)
        excel_action_row.addWidget(self.choose_sheet_btn)
        self.excel_preview_btn = QPushButton(tr("Aperçu des données…", self.language))
        self.excel_preview_btn.setEnabled(False)
        self.excel_preview_btn.clicked.connect(self._open_excel_preview)
        excel_action_row.addWidget(self.excel_preview_btn)
        self.excel_mapping_btn = QPushButton(tr("Correspondance des champs…", self.language))
        self.excel_mapping_btn.setEnabled(False)
        self.excel_mapping_btn.clicked.connect(self._open_excel_field_mapping)
        excel_action_row.addWidget(self.excel_mapping_btn)
        excel_footer_layout.addLayout(excel_action_row)

        self.excel_choice_label = QLabel(
            tr("Sélectionnez une feuille dans la liste ci-dessus. Les lignes de colonnes ne sont pas sélectionnables comme source.", self.language)
        )
        self.excel_choice_label.setWordWrap(True)
        excel_footer_layout.addWidget(self.excel_choice_label)

        self.excel_next_step_label = QLabel(
            tr("Après validation de la feuille source, l’étape suivante préparera la correspondance entre les colonnes Excel et les champs G-Skol.", self.language)
        )
        self.excel_next_step_label.setWordWrap(True)
        self.excel_next_step_label.setStyleSheet("font-style: italic;")
        excel_footer_layout.addWidget(self.excel_next_step_label)

        excel_import_row = QHBoxLayout()
        excel_import_row.addStretch(1)
        self.excel_real_import_btn = QPushButton(tr("Créer la collection G-Skol et importer…", self.language))
        self.excel_real_import_btn.setEnabled(False)
        self.excel_real_import_btn.clicked.connect(self._start_excel_import)
        excel_import_row.addWidget(self.excel_real_import_btn)
        excel_footer_layout.addLayout(excel_import_row)

        excel_layout.addWidget(excel_footer, 0)
        excel_layout.setStretchFactor(self.excel_structure_tree, 1)
        excel_layout.setStretchFactor(excel_footer, 0)

        source_tabs.addTab(excel_box, "Excel .xlsx")

        text_box = QFrame()
        text_box.setFrameShape(QFrame.Shape.StyledPanel)
        text_layout = QVBoxLayout(text_box)
        text_layout.setContentsMargins(18, 16, 18, 16)
        text_layout.setSpacing(10)

        text_title = QLabel("CSV / TXT / TSV")
        text_title.setStyleSheet("font-size: 16px; font-weight: 700;")
        text_layout.addWidget(text_title)

        text_desc = QLabel(tr("Choisissez un fichier tabulaire .csv, .txt ou .tsv. G-Skol détecte automatiquement l’encodage et le séparateur (point-virgule, virgule ou tabulation), puis analyse les en-têtes et les types de colonnes sans modifier le fichier source.", self.language))
        text_desc.setWordWrap(True)
        text_layout.addWidget(text_desc)

        text_choose_row = QHBoxLayout()
        self.choose_text_btn = QPushButton(tr("Choisir un fichier CSV / TXT / TSV…", self.language))
        self.choose_text_btn.clicked.connect(self._choose_text_file)
        text_choose_row.addWidget(self.choose_text_btn)
        self.analyse_text_btn = QPushButton(tr("Analyser le fichier", self.language))
        self.analyse_text_btn.setEnabled(False)
        self.analyse_text_btn.clicked.connect(self._analyse_text_file)
        text_choose_row.addWidget(self.analyse_text_btn)
        text_choose_row.addStretch(1)
        text_layout.addLayout(text_choose_row)

        self.text_source_label = QLabel(tr("Aucun fichier CSV / TXT / TSV sélectionné.", self.language))
        self.text_source_label.setWordWrap(True)
        self.text_source_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.text_source_label.setStyleSheet("padding: 8px; background: rgba(255,255,255,0.55);")
        text_layout.addWidget(self.text_source_label)

        self.text_analysis_summary = QLabel(
            tr("Après analyse, les colonnes et le nombre de lignes apparaîtront ci-dessous.", self.language)
        )
        self.text_analysis_summary.setWordWrap(True)
        self.text_analysis_summary.setStyleSheet("font-style: italic;")
        text_layout.addWidget(self.text_analysis_summary)

        self.text_structure_tree = QTreeWidget()
        self.text_structure_tree.setHeaderLabels([tr("Fichier / Colonne", self.language), tr("Type détecté", self.language), tr("Lignes", self.language)])
        self.text_structure_tree.setRootIsDecorated(True)
        self.text_structure_tree.setAlternatingRowColors(True)
        self.text_structure_tree.setMinimumHeight(115)
        self.text_structure_tree.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.text_structure_tree.header().setStretchLastSection(False)
        self.text_structure_tree.header().resizeSection(0, 450)
        self.text_structure_tree.header().resizeSection(1, 180)
        self.text_structure_tree.header().resizeSection(2, 90)
        self.text_structure_tree.itemSelectionChanged.connect(self._on_text_structure_selection_changed)
        self.text_structure_tree.itemDoubleClicked.connect(self._on_text_structure_double_clicked)
        text_layout.addWidget(self.text_structure_tree, 1)

        text_footer = QFrame()
        text_footer.setFrameShape(QFrame.Shape.NoFrame)
        text_footer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        text_footer_layout = QVBoxLayout(text_footer)
        text_footer_layout.setContentsMargins(0, 6, 0, 0)
        text_footer_layout.setSpacing(7)

        text_action_row = QHBoxLayout()
        text_action_row.addStretch(1)
        self.choose_text_table_btn = QPushButton(tr("Choisir ce fichier", self.language))
        self.choose_text_table_btn.setEnabled(False)
        self.choose_text_table_btn.clicked.connect(self._choose_selected_text_table)
        text_action_row.addWidget(self.choose_text_table_btn)
        self.text_preview_btn = QPushButton(tr("Aperçu des données…", self.language))
        self.text_preview_btn.setEnabled(False)
        self.text_preview_btn.clicked.connect(self._open_text_preview)
        text_action_row.addWidget(self.text_preview_btn)
        self.text_mapping_btn = QPushButton(tr("Correspondance des champs…", self.language))
        self.text_mapping_btn.setEnabled(False)
        self.text_mapping_btn.clicked.connect(self._open_text_field_mapping)
        text_action_row.addWidget(self.text_mapping_btn)
        text_footer_layout.addLayout(text_action_row)

        self.text_choice_label = QLabel(
            tr("Analysez le fichier puis validez-le comme source de la future collection G-Skol.", self.language)
        )
        self.text_choice_label.setWordWrap(True)
        text_footer_layout.addWidget(self.text_choice_label)

        self.text_next_step_label = QLabel(
            tr("Après validation, G-Skol préparera la correspondance entre les colonnes du fichier et les champs G-Skol.", self.language)
        )
        self.text_next_step_label.setWordWrap(True)
        self.text_next_step_label.setStyleSheet("font-style: italic;")
        text_footer_layout.addWidget(self.text_next_step_label)

        text_import_row = QHBoxLayout()
        text_import_row.addStretch(1)
        self.text_real_import_btn = QPushButton(tr("Créer la collection G-Skol et importer…", self.language))
        self.text_real_import_btn.setEnabled(False)
        self.text_real_import_btn.clicked.connect(self._start_text_import)
        text_import_row.addWidget(self.text_real_import_btn)
        text_footer_layout.addLayout(text_import_row)

        text_layout.addWidget(text_footer, 0)
        text_layout.setStretchFactor(self.text_structure_tree, 1)
        text_layout.setStretchFactor(text_footer, 0)
        source_tabs.addTab(text_box, "CSV / TXT / TSV")

        ods_box = QFrame()
        ods_box.setFrameShape(QFrame.Shape.StyledPanel)
        ods_layout = QVBoxLayout(ods_box)
        ods_layout.setContentsMargins(18, 16, 18, 16)
        ods_layout.setSpacing(10)

        ods_title = QLabel("ODS")
        ods_title.setStyleSheet("font-size: 16px; font-weight: 700;")
        ods_layout.addWidget(ods_title)

        ods_desc = QLabel(tr(
            "Choisissez un classeur OpenDocument .ods. G-Skol analyse ses feuilles, les en-têtes et les types de cellules sans modifier le fichier source. Les nombres, dates, booléens, montants monétaires et calculs arithmétiques simples sont reconnus.", self.language
        ))
        ods_desc.setWordWrap(True)
        ods_layout.addWidget(ods_desc)

        ods_choose_row = QHBoxLayout()
        self.choose_ods_btn = QPushButton(tr("Choisir un fichier ODS…", self.language))
        self.choose_ods_btn.clicked.connect(self._choose_ods_file)
        ods_choose_row.addWidget(self.choose_ods_btn)
        self.analyse_ods_btn = QPushButton(tr("Analyser le fichier", self.language))
        self.analyse_ods_btn.setEnabled(False)
        self.analyse_ods_btn.clicked.connect(self._analyse_ods_file)
        ods_choose_row.addWidget(self.analyse_ods_btn)
        ods_choose_row.addStretch(1)
        ods_layout.addLayout(ods_choose_row)

        self.ods_source_label = QLabel(tr("Aucun fichier ODS sélectionné.", self.language))
        self.ods_source_label.setWordWrap(True)
        self.ods_source_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.ods_source_label.setStyleSheet("padding: 8px; background: rgba(255,255,255,0.55);")
        ods_layout.addWidget(self.ods_source_label)

        self.ods_analysis_summary = QLabel(
            tr("Après analyse, les colonnes et le nombre de lignes apparaîtront ci-dessous.", self.language)
        )
        self.ods_analysis_summary.setWordWrap(True)
        self.ods_analysis_summary.setStyleSheet("font-style: italic;")
        ods_layout.addWidget(self.ods_analysis_summary)

        self.ods_structure_tree = QTreeWidget()
        self.ods_structure_tree.setHeaderLabels([tr("Feuille / Colonne", self.language), tr("Type détecté", self.language), tr("Lignes", self.language)])
        self.ods_structure_tree.setRootIsDecorated(True)
        self.ods_structure_tree.setAlternatingRowColors(True)
        self.ods_structure_tree.setMinimumHeight(115)
        self.ods_structure_tree.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.ods_structure_tree.header().setStretchLastSection(False)
        self.ods_structure_tree.header().resizeSection(0, 450)
        self.ods_structure_tree.header().resizeSection(1, 180)
        self.ods_structure_tree.header().resizeSection(2, 90)
        self.ods_structure_tree.itemSelectionChanged.connect(self._on_ods_structure_selection_changed)
        self.ods_structure_tree.itemDoubleClicked.connect(self._on_ods_structure_double_clicked)
        ods_layout.addWidget(self.ods_structure_tree, 1)

        ods_footer = QFrame()
        ods_footer.setFrameShape(QFrame.Shape.NoFrame)
        ods_footer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        ods_footer_layout = QVBoxLayout(ods_footer)
        ods_footer_layout.setContentsMargins(0, 6, 0, 0)
        ods_footer_layout.setSpacing(7)

        ods_action_row = QHBoxLayout()
        ods_action_row.addStretch(1)
        self.choose_ods_table_btn = QPushButton(tr("Choisir cette feuille", self.language))
        self.choose_ods_table_btn.setEnabled(False)
        self.choose_ods_table_btn.clicked.connect(self._choose_selected_ods_table)
        ods_action_row.addWidget(self.choose_ods_table_btn)
        self.ods_preview_btn = QPushButton(tr("Aperçu des données…", self.language))
        self.ods_preview_btn.setEnabled(False)
        self.ods_preview_btn.clicked.connect(self._open_ods_preview)
        ods_action_row.addWidget(self.ods_preview_btn)
        self.ods_mapping_btn = QPushButton(tr("Correspondance des champs…", self.language))
        self.ods_mapping_btn.setEnabled(False)
        self.ods_mapping_btn.clicked.connect(self._open_ods_field_mapping)
        ods_action_row.addWidget(self.ods_mapping_btn)
        ods_footer_layout.addLayout(ods_action_row)

        self.ods_choice_label = QLabel(
            tr("Analysez le classeur puis choisissez la feuille source de la future collection G-Skol.", self.language)
        )
        self.ods_choice_label.setWordWrap(True)
        ods_footer_layout.addWidget(self.ods_choice_label)

        self.ods_next_step_label = QLabel(
            tr("Après validation, G-Skol préparera la correspondance entre les colonnes du fichier et les champs G-Skol.", self.language)
        )
        self.ods_next_step_label.setWordWrap(True)
        self.ods_next_step_label.setStyleSheet("font-style: italic;")
        ods_footer_layout.addWidget(self.ods_next_step_label)

        ods_import_row = QHBoxLayout()
        ods_import_row.addStretch(1)
        self.ods_real_import_btn = QPushButton(tr("Créer la collection G-Skol et importer…", self.language))
        self.ods_real_import_btn.setEnabled(False)
        self.ods_real_import_btn.clicked.connect(self._start_ods_import)
        ods_import_row.addWidget(self.ods_real_import_btn)
        ods_footer_layout.addLayout(ods_import_row)

        ods_layout.addWidget(ods_footer, 0)
        ods_layout.setStretchFactor(self.ods_structure_tree, 1)
        ods_layout.setStretchFactor(ods_footer, 0)
        source_tabs.addTab(ods_box, "ODS")

        dbf_box = QFrame()
        dbf_box.setFrameShape(QFrame.Shape.StyledPanel)
        dbf_layout = QVBoxLayout(dbf_box)
        dbf_layout.setContentsMargins(18, 16, 18, 16)
        dbf_layout.setSpacing(10)

        dbf_title = QLabel("DBF")
        dbf_title.setStyleSheet("font-size: 16px; font-weight: 700;")
        dbf_layout.addWidget(dbf_title)

        dbf_desc = QLabel(tr(
            "Choisissez un fichier dBASE/FoxPro .dbf. G-Skol lit directement la structure du fichier, les noms de champs et les enregistrements sans modifier la source. Les champs texte, numériques, dates et logiques Oui/Non sont reconnus. Les mémos externes restent signalés lorsqu’ils nécessitent un fichier compagnon .dbt/.fpt.",
            self.language,
        ))
        dbf_desc.setWordWrap(True)
        dbf_layout.addWidget(dbf_desc)

        dbf_choose_row = QHBoxLayout()
        self.choose_dbf_btn = QPushButton(tr("Choisir un fichier DBF…", self.language))
        self.choose_dbf_btn.clicked.connect(self._choose_dbf_file)
        dbf_choose_row.addWidget(self.choose_dbf_btn)
        self.analyse_dbf_btn = QPushButton(tr("Analyser le fichier", self.language))
        self.analyse_dbf_btn.setEnabled(False)
        self.analyse_dbf_btn.clicked.connect(self._analyse_dbf_file)
        dbf_choose_row.addWidget(self.analyse_dbf_btn)
        dbf_choose_row.addStretch(1)
        dbf_layout.addLayout(dbf_choose_row)

        self.dbf_source_label = QLabel(tr("Aucun fichier DBF sélectionné.", self.language))
        self.dbf_source_label.setWordWrap(True)
        self.dbf_source_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.dbf_source_label.setStyleSheet("padding: 8px; background: rgba(255,255,255,0.55);")
        dbf_layout.addWidget(self.dbf_source_label)

        self.dbf_analysis_summary = QLabel(tr("Après analyse, les champs et le nombre d’enregistrements apparaîtront ci-dessous.", self.language))
        self.dbf_analysis_summary.setWordWrap(True)
        self.dbf_analysis_summary.setStyleSheet("font-style: italic;")
        dbf_layout.addWidget(self.dbf_analysis_summary)

        self.dbf_structure_tree = QTreeWidget()
        self.dbf_structure_tree.setHeaderLabels([tr("Fichier / Champ", self.language), tr("Type détecté", self.language), tr("Lignes", self.language)])
        self.dbf_structure_tree.setRootIsDecorated(True)
        self.dbf_structure_tree.setAlternatingRowColors(True)
        self.dbf_structure_tree.setMinimumHeight(115)
        self.dbf_structure_tree.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.dbf_structure_tree.header().setStretchLastSection(False)
        self.dbf_structure_tree.header().resizeSection(0, 450)
        self.dbf_structure_tree.header().resizeSection(1, 180)
        self.dbf_structure_tree.header().resizeSection(2, 90)
        self.dbf_structure_tree.itemSelectionChanged.connect(self._on_dbf_structure_selection_changed)
        self.dbf_structure_tree.itemDoubleClicked.connect(self._on_dbf_structure_double_clicked)
        dbf_layout.addWidget(self.dbf_structure_tree, 1)

        dbf_footer = QFrame()
        dbf_footer.setFrameShape(QFrame.Shape.NoFrame)
        dbf_footer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        dbf_footer_layout = QVBoxLayout(dbf_footer)
        dbf_footer_layout.setContentsMargins(0, 6, 0, 0)
        dbf_footer_layout.setSpacing(7)

        dbf_action_row = QHBoxLayout()
        dbf_action_row.addStretch(1)
        self.choose_dbf_table_btn = QPushButton(tr("Choisir ce fichier", self.language))
        self.choose_dbf_table_btn.setEnabled(False)
        self.choose_dbf_table_btn.clicked.connect(self._choose_selected_dbf_table)
        dbf_action_row.addWidget(self.choose_dbf_table_btn)
        self.dbf_preview_btn = QPushButton(tr("Aperçu des données…", self.language))
        self.dbf_preview_btn.setEnabled(False)
        self.dbf_preview_btn.clicked.connect(self._open_dbf_preview)
        dbf_action_row.addWidget(self.dbf_preview_btn)
        self.dbf_mapping_btn = QPushButton(tr("Correspondance des champs…", self.language))
        self.dbf_mapping_btn.setEnabled(False)
        self.dbf_mapping_btn.clicked.connect(self._open_dbf_field_mapping)
        dbf_action_row.addWidget(self.dbf_mapping_btn)
        dbf_footer_layout.addLayout(dbf_action_row)

        self.dbf_choice_label = QLabel(tr("Analysez le fichier puis validez-le comme source de la future collection G-Skol.", self.language))
        self.dbf_choice_label.setWordWrap(True)
        dbf_footer_layout.addWidget(self.dbf_choice_label)

        self.dbf_next_step_label = QLabel(tr("Après validation, G-Skol préparera la correspondance entre les champs DBF et les champs G-Skol.", self.language))
        self.dbf_next_step_label.setWordWrap(True)
        self.dbf_next_step_label.setStyleSheet("font-style: italic;")
        dbf_footer_layout.addWidget(self.dbf_next_step_label)

        dbf_import_row = QHBoxLayout()
        dbf_import_row.addStretch(1)
        self.dbf_real_import_btn = QPushButton(tr("Créer la collection G-Skol et importer…", self.language))
        self.dbf_real_import_btn.setEnabled(False)
        self.dbf_real_import_btn.clicked.connect(self._start_dbf_import)
        dbf_import_row.addWidget(self.dbf_real_import_btn)
        dbf_footer_layout.addLayout(dbf_import_row)

        dbf_layout.addWidget(dbf_footer, 0)
        dbf_layout.setStretchFactor(self.dbf_structure_tree, 1)
        dbf_layout.setStretchFactor(dbf_footer, 0)
        source_tabs.addTab(dbf_box, "DBF")

        sqlite_box = QFrame()
        sqlite_box.setFrameShape(QFrame.Shape.StyledPanel)
        sqlite_layout = QVBoxLayout(sqlite_box)
        sqlite_layout.setContentsMargins(18, 16, 18, 16)
        sqlite_layout.setSpacing(10)

        sqlite_title = QLabel("SQLite")
        sqlite_title.setStyleSheet("font-size: 16px; font-weight: 700;")
        sqlite_layout.addWidget(sqlite_title)

        sqlite_desc = QLabel(tr(
            "Choisissez une base SQLite .db, .sqlite ou .sqlite3. G-Skol ouvre la base strictement en lecture seule, recense ses tables utilisateur, leurs colonnes et leurs types, puis vous laisse choisir la table qui deviendra la source de la nouvelle collection.",
            self.language,
        ))
        sqlite_desc.setWordWrap(True)
        sqlite_layout.addWidget(sqlite_desc)

        sqlite_choose_row = QHBoxLayout()
        self.choose_sqlite_btn = QPushButton(tr("Choisir une base SQLite…", self.language))
        self.choose_sqlite_btn.clicked.connect(self._choose_sqlite_file)
        sqlite_choose_row.addWidget(self.choose_sqlite_btn)
        self.analyse_sqlite_btn = QPushButton(tr("Analyser la base", self.language))
        self.analyse_sqlite_btn.setEnabled(False)
        self.analyse_sqlite_btn.clicked.connect(self._analyse_sqlite_file)
        sqlite_choose_row.addWidget(self.analyse_sqlite_btn)
        sqlite_choose_row.addStretch(1)
        sqlite_layout.addLayout(sqlite_choose_row)

        self.sqlite_source_label = QLabel(tr("Aucune base SQLite sélectionnée.", self.language))
        self.sqlite_source_label.setWordWrap(True)
        self.sqlite_source_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.sqlite_source_label.setStyleSheet("padding: 8px; background: rgba(255,255,255,0.55);")
        sqlite_layout.addWidget(self.sqlite_source_label)

        self.sqlite_analysis_summary = QLabel(tr(
            "Après analyse, les tables, colonnes et nombres d’enregistrements apparaîtront ci-dessous.", self.language
        ))
        self.sqlite_analysis_summary.setWordWrap(True)
        self.sqlite_analysis_summary.setStyleSheet("font-style: italic;")
        sqlite_layout.addWidget(self.sqlite_analysis_summary)

        self.sqlite_structure_tree = QTreeWidget()
        self.sqlite_structure_tree.setHeaderLabels([tr("Table / Colonne", self.language), tr("Type détecté", self.language), tr("Lignes", self.language)])
        self.sqlite_structure_tree.setRootIsDecorated(True)
        self.sqlite_structure_tree.setAlternatingRowColors(True)
        self.sqlite_structure_tree.setMinimumHeight(115)
        self.sqlite_structure_tree.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.sqlite_structure_tree.header().setStretchLastSection(False)
        self.sqlite_structure_tree.header().resizeSection(0, 450)
        self.sqlite_structure_tree.header().resizeSection(1, 180)
        self.sqlite_structure_tree.header().resizeSection(2, 90)
        self.sqlite_structure_tree.itemSelectionChanged.connect(self._on_sqlite_structure_selection_changed)
        self.sqlite_structure_tree.itemDoubleClicked.connect(self._on_sqlite_structure_double_clicked)
        sqlite_layout.addWidget(self.sqlite_structure_tree, 1)

        sqlite_footer = QFrame()
        sqlite_footer.setFrameShape(QFrame.Shape.NoFrame)
        sqlite_footer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        sqlite_footer_layout = QVBoxLayout(sqlite_footer)
        sqlite_footer_layout.setContentsMargins(0, 6, 0, 0)
        sqlite_footer_layout.setSpacing(7)

        sqlite_action_row = QHBoxLayout()
        sqlite_action_row.addStretch(1)
        self.choose_sqlite_table_btn = QPushButton(tr("Choisir cette table", self.language))
        self.choose_sqlite_table_btn.setEnabled(False)
        self.choose_sqlite_table_btn.clicked.connect(self._choose_selected_sqlite_table)
        sqlite_action_row.addWidget(self.choose_sqlite_table_btn)
        self.sqlite_preview_btn = QPushButton(tr("Aperçu des données…", self.language))
        self.sqlite_preview_btn.setEnabled(False)
        self.sqlite_preview_btn.clicked.connect(self._open_sqlite_preview)
        sqlite_action_row.addWidget(self.sqlite_preview_btn)
        self.sqlite_mapping_btn = QPushButton(tr("Correspondance des champs…", self.language))
        self.sqlite_mapping_btn.setEnabled(False)
        self.sqlite_mapping_btn.clicked.connect(self._open_sqlite_field_mapping)
        sqlite_action_row.addWidget(self.sqlite_mapping_btn)
        sqlite_footer_layout.addLayout(sqlite_action_row)

        self.sqlite_choice_label = QLabel(tr("Analysez la base puis choisissez la table source de la future collection G-Skol.", self.language))
        self.sqlite_choice_label.setWordWrap(True)
        sqlite_footer_layout.addWidget(self.sqlite_choice_label)

        self.sqlite_next_step_label = QLabel(
            tr("Après validation, G-Skol préparera la correspondance entre les colonnes SQLite et les champs G-Skol.", self.language)
        )
        self.sqlite_next_step_label.setWordWrap(True)
        self.sqlite_next_step_label.setStyleSheet("font-style: italic;")
        sqlite_footer_layout.addWidget(self.sqlite_next_step_label)

        sqlite_import_row = QHBoxLayout()
        sqlite_import_row.addStretch(1)
        self.sqlite_real_import_btn = QPushButton(tr("Créer la collection G-Skol et importer…", self.language))
        self.sqlite_real_import_btn.setEnabled(False)
        self.sqlite_real_import_btn.clicked.connect(self._start_sqlite_import)
        sqlite_import_row.addWidget(self.sqlite_real_import_btn)
        sqlite_footer_layout.addLayout(sqlite_import_row)

        sqlite_layout.addWidget(sqlite_footer, 0)
        sqlite_layout.setStretchFactor(self.sqlite_structure_tree, 1)
        sqlite_layout.setStretchFactor(sqlite_footer, 0)
        source_tabs.addTab(sqlite_box, "SQLite")

        # MM3 : import d'une collection MM3 existante dans Workspace/Collections.
        mm3_box = QFrame()
        mm3_box.setFrameShape(QFrame.Shape.StyledPanel)
        mm3_layout = QVBoxLayout(mm3_box)
        mm3_layout.setContentsMargins(18, 16, 18, 16)
        mm3_layout.setSpacing(12)

        mm3_title = QLabel(("Bestehende G-Skol-Sammlung" if self.language.lower().startswith("de") else ("Existing G-Skol collection" if self.language.lower().startswith("en") else "Collection G-Skol existante")))
        mm3_title.setStyleSheet("font-size: 16px; font-weight: 700;")
        mm3_layout.addWidget(mm3_title)

        mm3_desc = QLabel(
            ("Import an existing G-Skol collection (.coldb) into this environment's collections folder. "
             "The source file remains unchanged. Two identical collections are allowed: G-Skol never compares their contents.")
            if self.language.lower().startswith("en") else
            ("Importieren Sie eine vorhandene G-Skol-Sammlung (.coldb) in den Sammlungsordner dieser Umgebung. "
             "Die Quelldatei bleibt unverändert. Zwei identische Sammlungen sind zulässig: G-Skol vergleicht ihre Inhalte nicht.")
            if self.language.lower().startswith("de") else
            ("Importez une collection G-Skol existante (.coldb) dans le dossier des collections de cet environnement. "
             "Le fichier source reste inchangé. Deux collections identiques sont autorisées : G-Skol ne compare jamais leur contenu.")
        )
        mm3_desc.setWordWrap(True)
        mm3_layout.addWidget(mm3_desc)

        mm3_choose_row = QHBoxLayout()
        self.choose_mm3_btn = QPushButton(("G-Skol-Sammlung auswählen…" if self.language.lower().startswith("de") else ("Choose a G-Skol collection…" if self.language.lower().startswith("en") else "Choisir une collection G-Skol…")))
        self.choose_mm3_btn.clicked.connect(self._choose_mm3_file)
        mm3_choose_row.addWidget(self.choose_mm3_btn)
        mm3_choose_row.addStretch(1)
        mm3_layout.addLayout(mm3_choose_row)

        self.mm3_source_label = QLabel(("Keine G-Skol-Sammlung ausgewählt." if self.language.lower().startswith("de") else ("No G-Skol collection selected." if self.language.lower().startswith("en") else "Aucune collection G-Skol sélectionnée.")))
        self.mm3_source_label.setWordWrap(True)
        self.mm3_source_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.mm3_source_label.setStyleSheet(
            "padding: 8px; background: rgba(255,255,255,0.55);"
        )
        mm3_layout.addWidget(self.mm3_source_label)

        mm3_select_row = QHBoxLayout()
        mm3_select_row.addWidget(QLabel(("Im Datei enthaltene Sammlung:" if self.language.lower().startswith("de") else ("Collection contained in the file:" if self.language.lower().startswith("en") else "Collection contenue dans le fichier :"))))
        self.mm3_collection_combo = QComboBox()
        self.mm3_collection_combo.setEnabled(False)
        self.mm3_collection_combo.currentIndexChanged.connect(
            self._on_mm3_collection_changed
        )
        mm3_select_row.addWidget(self.mm3_collection_combo, 1)
        mm3_layout.addLayout(mm3_select_row)

        self.mm3_info_label = QLabel(
            "Choose a file. G-Skol will verify that it is a valid G-Skol collection before offering the import."
            if self.language.lower().startswith("en") else
            "Wählen Sie eine Datei aus. G-Skol prüft vor dem Import, ob sie eine gültige G-Skol-Sammlung enthält."
            if self.language.lower().startswith("de") else
            "Choisissez un fichier. G-Skol vérifiera qu'il s'agit bien d'une collection G-Skol avant de proposer l'import."
        )
        self.mm3_info_label.setWordWrap(True)
        self.mm3_info_label.setStyleSheet("font-style: italic;")
        mm3_layout.addWidget(self.mm3_info_label)

        mm3_layout.addStretch(1)

        mm3_import_row = QHBoxLayout()
        mm3_import_row.addStretch(1)
        self.mm3_import_btn = QPushButton(("Diese G-Skol-Sammlung importieren…" if self.language.lower().startswith("de") else ("Import this G-Skol collection…" if self.language.lower().startswith("en") else "Importer cette collection G-Skol…")))
        self.mm3_import_btn.setEnabled(False)
        self.mm3_import_btn.clicked.connect(self._import_mm3_collection)
        mm3_import_row.addWidget(self.mm3_import_btn)
        mm3_layout.addLayout(mm3_import_row)

        source_tabs.addTab(mm3_box, "G-Skol")

        layout.addWidget(source_tabs, 1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.mm3_close_btn = QPushButton(tr("Fermer", self.language))
        self.mm3_close_btn.clicked.connect(self.close)
        buttons.addWidget(self.mm3_close_btn)
        layout.addLayout(buttons)

    @staticmethod
    def _xlsx_column_index(reference: str) -> int:
        letters = "".join(ch for ch in str(reference or "") if ch.isalpha()).upper()
        value = 0
        for ch in letters:
            value = value * 26 + (ord(ch) - 64)
        return max(0, value - 1)

    @staticmethod
    def _xlsx_is_date_format(num_fmt_id: int, format_code: str) -> bool:
        if int(num_fmt_id or 0) in {14, 15, 16, 17, 18, 19, 20, 21, 22, 45, 46, 47}:
            return True
        code = str(format_code or "").lower()
        # Retirer les textes entre guillemets et les séquences échappées avant
        # de rechercher les marqueurs usuels de date/heure Excel.
        code = re.sub(r'"[^"]*"', "", code)
        code = re.sub(r"\\.", "", code)
        return bool(re.search(r"(^|[^a-z])[dmyhs]+([^a-z]|$)", code))

    @staticmethod
    def _xlsx_currency_symbol(format_code: str) -> str:
        """Détecte une devise explicite dans le format numérique Excel."""
        code = str(format_code or "")
        for symbol in ("€", "$", "£", "¥"):
            if symbol in code:
                return symbol
        upper = code.upper()
        for symbol in ("CHF", "CAD", "AUD"):
            if symbol in upper:
                return symbol
        return ""

    @classmethod
    def _xlsx_formula_to_mm3(
        cls,
        formula: str,
        excel_row: int,
        headers: list[str],
    ) -> str:
        """Traduit une formule Excel simple de la ligne courante en formule MM3.

        Sont acceptées les opérations arithmétiques + - * /, les parenthèses,
        les constantes numériques et les références à des cellules de la même
        ligne. Exemple : =H2*I2 -> [Nombre de boîtes]*[Prix].
        """
        raw = str(formula or "").strip()
        if raw.startswith("="):
            raw = raw[1:].strip()
        if not raw:
            return ""

        # Écarter les fonctions, plages, références externes et syntaxes que le
        # moteur MM3 ne sait pas reproduire fidèlement.
        if any(token in raw for token in ("!", ":", ";")):
            return ""
        if re.search(r"[A-Za-z_][A-Za-z0-9_]*\s*\(", raw):
            return ""

        failed = False

        def replace_ref(match):
            nonlocal failed
            letters = str(match.group(1) or "")
            row_text = str(match.group(2) or "")
            try:
                row_no = int(row_text)
            except ValueError:
                failed = True
                return match.group(0)
            if row_no != int(excel_row):
                failed = True
                return match.group(0)
            col = cls._xlsx_column_index(letters)
            if not (0 <= col < len(headers)):
                failed = True
                return match.group(0)
            return "[" + str(headers[col]) + "]"

        translated = re.sub(r"\$?([A-Z]{1,3})\$?(\d+)", replace_ref, raw, flags=re.IGNORECASE)
        if failed:
            return ""

        # Après remplacement, seules les références [Champ], nombres, espaces,
        # parenthèses et quatre opérateurs arithmétiques sont admis.
        stripped = re.sub(r"\[[^\]]+\]", "", translated)
        stripped = stripped.replace(",", ".")
        if re.search(r"[^0-9\.\s+\-*/()]", stripped):
            return ""
        return translated.strip()

    @classmethod
    def _ods_formula_to_mm3(cls, formula: str, row_no: int, headers: list[str]) -> str:
        """Traduit les calculs ODS arithmétiques simples en formule MM3."""
        raw = str(formula or "").strip()
        raw = re.sub(r"^(?:of:)?=", "", raw, flags=re.IGNORECASE).strip()
        if not raw:
            return ""
        # Références ODF usuelles : [.$A2], [.A2], [$Feuille.$A2].
        def repl(match):
            col_letters = match.group(1)
            try:
                col = cls._xlsx_column_index(col_letters)
            except Exception:
                return match.group(0)
            if not (0 <= col < len(headers)):
                return match.group(0)
            return "[" + headers[col] + "]"
        translated = re.sub(r"\[(?:\$?[^.\]]+\.)?\.?\$?([A-Z]{1,3})\$?\d+\]", repl, raw, flags=re.IGNORECASE)
        stripped = re.sub(r"\[[^\]]+\]", "", translated).replace(",", ".")
        if re.search(r"[^0-9\.\s+\-*/()]", stripped):
            return ""
        return translated.strip()

    @classmethod
    def _read_ods_workbook(cls, path: Path) -> dict:
        """Lit un classeur .ods directement (ZIP/XML), sans LibreOffice."""
        if not path.exists():
            raise FileNotFoundError(str(path))
        ns = {
            "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
            "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
            "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
            "style": "urn:oasis:names:tc:opendocument:xmlns:style:1.0",
            "number": "urn:oasis:names:tc:opendocument:xmlns:datastyle:1.0",
        }
        T = "{" + ns["table"] + "}"
        O = "{" + ns["office"] + "}"
        S = "{" + ns["style"] + "}"
        with zipfile.ZipFile(path) as archive:
            if "content.xml" not in archive.namelist():
                raise ValueError("Ce fichier ne contient pas de classeur ODS lisible.")
            root = ET.fromstring(archive.read("content.xml"))

            # Dans un ODS, une cellule monétaire n'est pas obligatoirement
            # marquée office:value-type="currency". LibreOffice (et d'autres
            # producteurs) peuvent stocker un simple nombre et porter la devise
            # uniquement par le style de cellule. Résoudre donc aussi :
            # style de cellule -> style de données -> symbole monétaire.
            style_roots = [root]
            if "styles.xml" in archive.namelist():
                try:
                    style_roots.append(ET.fromstring(archive.read("styles.xml")))
                except Exception:
                    pass
            data_style_currency: dict[str, str] = {}
            cell_style_data: dict[str, str] = {}
            for style_root in style_roots:
                for cur_style in style_root.findall(".//number:currency-style", ns):
                    style_name = str(cur_style.get(S + "name") or "")
                    symbol_node = cur_style.find("number:currency-symbol", ns)
                    symbol = "" if symbol_node is None else "".join(symbol_node.itertext()).strip()
                    if style_name and symbol:
                        data_style_currency[style_name] = symbol
                for cell_style in style_root.findall(".//style:style", ns):
                    if str(cell_style.get(S + "family") or "") != "table-cell":
                        continue
                    style_name = str(cell_style.get(S + "name") or "")
                    data_name = str(cell_style.get(S + "data-style-name") or "")
                    if style_name and data_name:
                        cell_style_data[style_name] = data_name

        sheets = []
        for sheet_order, table_node in enumerate(root.findall(".//table:table", ns)):
            sheet_name = str(table_node.get(T + "name") or f"Feuille {sheet_order + 1}")
            physical_rows = []
            physical_row_no = 0
            for row_node in table_node.findall("table:table-row", ns):
                try:
                    row_repeat = max(1, int(row_node.get(T + "number-rows-repeated") or 1))
                except ValueError:
                    row_repeat = 1
                values = []
                for cell in list(row_node):
                    if cell.tag not in {T + "table-cell", T + "covered-table-cell"}:
                        continue
                    try:
                        repeat = max(1, int(cell.get(T + "number-columns-repeated") or 1))
                    except ValueError:
                        repeat = 1
                    value_type = str(cell.get(O + "value-type") or "").casefold()
                    formula = str(cell.get(T + "formula") or "")
                    currency = str(cell.get(O + "currency") or "")
                    if not currency:
                        cell_style_name = str(cell.get(T + "style-name") or "")
                        data_style_name = cell_style_data.get(cell_style_name, "")
                        currency = data_style_currency.get(data_style_name, "")
                    text_value = "\n".join(
                        "".join(p.itertext()) for p in cell.findall("text:p", ns)
                    ).strip()
                    kind = "blank"
                    value = text_value
                    if value_type in {"float", "percentage", "currency"}:
                        raw = cell.get(O + "value")
                        if raw is not None:
                            try:
                                n = float(raw)
                                value = str(int(n)) if n.is_integer() else format(n, ".15g")
                                kind = "number"
                            except ValueError:
                                kind = "text"
                        elif text_value:
                            kind = "text"
                    elif value_type == "date":
                        raw = str(cell.get(O + "date-value") or text_value)
                        try:
                            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                            value = dt.strftime("%d/%m/%Y") if "T" not in raw else dt.strftime("%d/%m/%Y %H:%M:%S")
                            kind = "date"
                        except Exception:
                            value, kind = raw, "text"
                    elif value_type == "boolean":
                        raw = str(cell.get(O + "boolean-value") or text_value).casefold()
                        value = "Oui" if raw in {"true", "1", "oui", "yes"} else "Non"
                        kind = "bool"
                    elif text_value:
                        kind = "text"
                    cell_info = (value, kind, formula, currency)
                    values.extend([cell_info] * repeat)
                # Eviter d'expanser les millions de lignes vides que certains ODS compressent.
                while values and not any(str(x or "").strip() for x in values[-1]):
                    values.pop()
                if values and any(str(v[0] or "").strip() or str(v[2] or "").strip() for v in values):
                    for _ in range(min(row_repeat, 100000)):
                        physical_row_no += 1
                        physical_rows.append((physical_row_no, list(values)))
                else:
                    physical_row_no += row_repeat

            header_pos = next((i for i, (_r, vals) in enumerate(physical_rows)
                               if any(str(v[0] or "").strip() for v in vals)), None)
            if header_pos is None:
                sheets.append({"name": sheet_name, "source_kind": "ODS", "fields": [], "rows": 0, "rows_data": [], "header_row": None, "sheet_order": sheet_order})
                continue
            header_vals = physical_rows[header_pos][1]
            max_col = max([len(v) for _r, v in physical_rows[header_pos:]] or [0])
            headers=[]; used={}
            for col in range(max_col):
                raw = str(header_vals[col][0] if col < len(header_vals) else "").strip()
                base = raw or f"Colonne {col+1}"
                key=base.casefold(); used[key]=used.get(key,0)+1
                headers.append(base if used[key]==1 else f"{base}-{used[key]}")
            rows_data=[]; kinds=[[] for _ in headers]; formulas=[[] for _ in headers]; currencies=[[] for _ in headers]
            for row_no, vals in physical_rows[header_pos+1:]:
                if not any(str(v[0] or "").strip() or str(v[2] or "").strip() for v in vals):
                    continue
                row={"__excel_row__": str(row_no)}
                for col,h in enumerate(headers):
                    val,kind,formula,currency = vals[col] if col < len(vals) else ("","blank","","")
                    row[h]=str(val or "")
                    if kind != "blank": kinds[col].append(kind)
                    if formula:
                        translated=cls._ods_formula_to_mm3(formula,row_no,headers)
                        formulas[col].append(translated)
                    if currency: currencies[col].append(currency)
                rows_data.append(row)
            fields=[]
            for col,h in enumerate(headers):
                ks=kinds[col]; non=len(ks); counts={k:ks.count(k) for k in set(ks)}
                cur=max(set(currencies[col]), key=currencies[col].count) if currencies[col] else ""
                cur = {"EUR":"€", "USD":"$", "GBP":"£", "JPY":"¥", "CHF":"CHF"}.get(cur.upper(), cur) if cur else ""
                fs=[x for x in formulas[col] if x]; uniq=list(dict.fromkeys(fs))
                expr=uniq[0] if formulas[col] and len(fs)==len(formulas[col]) and len(uniq)==1 else ""
                if expr: detected="Calculé"; note="formule ODS traduite en calcul MM3"
                elif non==0: detected="Texte"; note="colonne vide"
                elif counts.get("date",0)/non>=.8: detected="Date"; note="dates ODS"
                elif counts.get("bool",0)/non>=.8: detected="Booléen"; note="valeurs Oui/Non"
                elif counts.get("number",0)/non>=.8 and cur: detected="Monétaire"; note=f"valeurs monétaires ODS ({cur})"
                elif counts.get("number",0)/non>=.8: detected="Nombre"; note="valeurs numériques"
                else: detected="Texte"; note="contenu mixte ou texte"
                fields.append({"name":h,"source_field":h,"source_table":sheet_name,"target_label":h,"type":detected,"source_order":col,
                    "calculation_expression":expr,"calculation_result_type":"Monétaire" if expr and cur else "Nombre" if expr else "",
                    "calculation_format":"truncate2","currency_symbol":cur,"result_suffix":cur if expr else "",
                    "excel_detection":f"ODS : {note}"})
            sheets.append({"name":sheet_name,"source_kind":"ODS","fields":fields,"rows":len(rows_data),"rows_data":rows_data,
                           "header_row":physical_rows[header_pos][0],"sheet_order":sheet_order})
        return {"sheets": sheets, "format": "ODS"}

    @staticmethod
    def _dbf_encoding(path: Path, language_driver: int) -> tuple[str, str]:
        """Choisit l'encodage DBF sans dépendance externe."""
        cpg = path.with_suffix(".cpg")
        if cpg.exists():
            try:
                label = cpg.read_text(encoding="ascii", errors="ignore").strip().strip("\ufeff")
                aliases = {"1252":"cp1252", "windows-1252":"cp1252", "ansi 1252":"cp1252",
                           "65001":"utf-8", "utf8":"utf-8", "utf-8":"utf-8", "850":"cp850"}
                enc = aliases.get(label.casefold(), label or "cp1252")
                "".encode(enc)
                return enc, f"{enc} (.cpg)"
            except Exception:
                pass
        # Principaux language-driver IDs dBASE/FoxPro. Un fichier occidental ancien
        # sans indicateur est généralement CP1252/ANSI sous Windows.
        table = {0x01:"cp437", 0x02:"cp850", 0x03:"cp1252", 0x57:"cp1252", 0x58:"cp1252",
                 0x64:"cp852", 0x65:"cp866", 0x66:"cp865", 0xC8:"cp1250", 0xC9:"cp1251", 0xCA:"cp1254"}
        enc = table.get(int(language_driver or 0), "cp1252")
        return enc, enc

    @classmethod
    def _read_dbf_file(cls, path: Path) -> dict:
        """Lit les DBF dBASE III/IV et FoxPro courants avec la bibliothèque standard."""
        if not path.exists():
            raise FileNotFoundError(str(path))
        raw = path.read_bytes()
        if len(raw) < 33:
            raise ValueError("Le fichier DBF est trop court ou endommagé.")
        version = raw[0]
        records = struct.unpack_from("<I", raw, 4)[0]
        header_len = struct.unpack_from("<H", raw, 8)[0]
        record_len = struct.unpack_from("<H", raw, 10)[0]
        language_driver = raw[29] if len(raw) > 29 else 0
        if header_len < 33 or record_len < 2 or header_len > len(raw):
            raise ValueError("L'en-tête DBF est invalide.")
        encoding, encoding_label = cls._dbf_encoding(path, language_driver)
        fields_meta = []
        offset = 1
        pos = 32
        while pos + 32 <= header_len and raw[pos] != 0x0D:
            desc = raw[pos:pos+32]
            name_bytes = desc[:11].split(b"\x00", 1)[0]
            name = name_bytes.decode(encoding, errors="replace").strip() or f"Champ {len(fields_meta)+1}"
            ftype = chr(desc[11]) if 32 <= desc[11] <= 126 else "C"
            length = int(desc[16])
            decimals = int(desc[17])
            fields_meta.append({"name":name, "dbf_type":ftype, "length":length, "decimals":decimals, "offset":offset})
            offset += length
            pos += 32
        if not fields_meta:
            raise ValueError("Aucun champ lisible n'a été trouvé dans ce fichier DBF.")
        if offset > record_len:
            raise ValueError("La longueur des champs DBF dépasse la longueur d'un enregistrement.")

        def decode_field(meta, chunk: bytes):
            t = meta["dbf_type"].upper()
            text = chunk.decode(encoding, errors="replace").strip().rstrip("\x00")
            if not text:
                return ""
            if t in {"N","F","B","Y","I","+"}:
                # N/F sont ASCII. I/B/Y binaires existent en FoxPro ; conserver
                # une représentation sûre lorsque la variante binaire n'est pas simple.
                if t in {"N","F"}:
                    return text.replace(".", ",") if meta["decimals"] else text
                return text
            if t == "D" and len(text) == 8 and text.isdigit():
                try:
                    return datetime.strptime(text, "%Y%m%d").strftime("%d/%m/%Y")
                except Exception:
                    return text
            if t == "L":
                c = text[:1].upper()
                if c in {"Y","T","O","1"}: return "Oui"
                if c in {"N","F","0"}: return "Non"
                return ""
            if t in {"M","G","P"}:
                # L'index du mémo est conservé : le contenu dépend du compagnon DBT/FPT.
                return text
            return text

        rows_data = []
        deleted_count = 0
        data_start = header_len
        max_possible = max(0, (len(raw) - data_start) // record_len)
        count = min(int(records), max_possible)
        for i in range(count):
            rec = raw[data_start + i*record_len : data_start + (i+1)*record_len]
            if len(rec) < record_len: break
            if rec[:1] == b"*":
                deleted_count += 1
                continue
            if rec[:1] not in {b" ", b""}:
                continue
            row = {"__excel_row__": str(i + 1)}
            for meta in fields_meta:
                start = meta["offset"]
                chunk = rec[start:start+meta["length"]]
                row[meta["name"]] = decode_field(meta, chunk)
            rows_data.append(row)

        fields=[]
        for order, meta in enumerate(fields_meta):
            t=meta["dbf_type"].upper(); name=meta["name"]
            if t == "D": detected="Date"; note="date DBF"
            elif t == "L": detected="Booléen"; note="champ logique DBF"
            elif t in {"N","F","I","+","B"}: detected="Nombre"; note="champ numérique DBF"
            elif t == "Y": detected="Monétaire"; note="champ monétaire DBF"
            elif t in {"M","G","P"}: detected="Texte"; note="mémo/objet DBF (fichier compagnon éventuel)"
            else: detected="Texte"; note="champ texte DBF"
            # Les noms métier usuels gardent la même aide de typage que les autres imports.
            if detected == "Nombre" and any(tok in name.casefold() for tok in ("prix","price","cout","coût","montant","amount")) and meta["decimals"] >= 2:
                detected="Monétaire"; note="champ numérique DBF à 2 décimales identifié comme monétaire"
            fields.append({"name":name,"source_field":name,"source_table":path.stem,"target_label":name,
                           "type":detected,"source_order":order,"dbf_type":t,"currency_symbol":"€" if detected=="Monétaire" else "",
                           "excel_detection":f"DBF : {note}"})
        table={"name":path.stem,"source_kind":"DBF","fields":fields,"rows":len(rows_data),"rows_data":rows_data,
               "encoding":encoding_label,"dbf_version":f"0x{version:02X}","deleted_records":deleted_count}
        return {"tables":[table],"format":"DBF","encoding":encoding_label,"version":f"0x{version:02X}"}

    @classmethod
    def _read_xlsx_workbook(cls, path: Path) -> dict:
        """Lit un .xlsx avec la bibliothèque standard, sans dépendance Office."""
        if not path.exists():
            raise FileNotFoundError(str(path))

        ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        rel_ns = {"r": "http://schemas.openxmlformats.org/package/2006/relationships"}
        office_rel = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"

        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            if "xl/workbook.xml" not in names:
                raise ValueError("Ce fichier ne contient pas de classeur Excel lisible.")

            # Chaînes partagées.
            shared: list[str] = []
            if "xl/sharedStrings.xml" in names:
                root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
                for si in root.findall("m:si", ns):
                    shared.append("".join(node.text or "" for node in si.iterfind(".//m:t", ns)))

            # Formats de cellules, nécessaires pour reconnaître les dates.
            custom_formats: dict[int, str] = {}
            style_num_fmt_ids: list[int] = []
            if "xl/styles.xml" in names:
                styles_root = ET.fromstring(archive.read("xl/styles.xml"))
                numfmts = styles_root.find("m:numFmts", ns)
                if numfmts is not None:
                    for node in numfmts.findall("m:numFmt", ns):
                        try:
                            custom_formats[int(node.get("numFmtId") or 0)] = str(node.get("formatCode") or "")
                        except ValueError:
                            pass
                cell_xfs = styles_root.find("m:cellXfs", ns)
                if cell_xfs is not None:
                    for xf in cell_xfs.findall("m:xf", ns):
                        try:
                            style_num_fmt_ids.append(int(xf.get("numFmtId") or 0))
                        except ValueError:
                            style_num_fmt_ids.append(0)

            workbook_root = ET.fromstring(archive.read("xl/workbook.xml"))

            # Noms Excel pouvant servir de source à une liste déroulante.
            # Ex. =ListePays ou =INDIRECT(...). Les noms qui pointent vers une
            # plage simple sont résolus comme les références directes.
            defined_names: dict[str, str] = {}
            defined_names_node = workbook_root.find("m:definedNames", ns)
            if defined_names_node is not None:
                for node in defined_names_node.findall("m:definedName", ns):
                    name = str(node.get("name") or "").strip()
                    formula = str(node.text or "").strip()
                    if name and formula:
                        defined_names[name.casefold()] = formula

            workbook_pr = workbook_root.find("m:workbookPr", ns)
            date_1904 = bool(
                workbook_pr is not None
                and str(workbook_pr.get("date1904") or "").strip().casefold() in {"1", "true"}
            )

            relationships: dict[str, str] = {}
            if "xl/_rels/workbook.xml.rels" in names:
                rels_root = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
                for rel in rels_root.findall("r:Relationship", rel_ns):
                    relationships[str(rel.get("Id") or "")] = str(rel.get("Target") or "")

            sheets: list[dict] = []
            sheet_nodes = workbook_root.findall(".//m:sheets/m:sheet", ns)
            for sheet_order, sheet_node in enumerate(sheet_nodes):
                sheet_name = str(sheet_node.get("name") or f"Feuille {sheet_order + 1}")
                rid = str(sheet_node.get(office_rel) or "")
                target = relationships.get(rid, "")
                if not target:
                    continue
                if target.startswith("/"):
                    sheet_path = target.lstrip("/")
                else:
                    sheet_path = "xl/" + target.lstrip("/")
                # Normaliser d'éventuels ../ présents dans la relation.
                parts: list[str] = []
                for part in sheet_path.split("/"):
                    if part == "..":
                        if parts:
                            parts.pop()
                    elif part not in {"", "."}:
                        parts.append(part)
                sheet_path = "/".join(parts)
                if sheet_path not in names:
                    continue

                root = ET.fromstring(archive.read(sheet_path))
                physical_rows: list[tuple[int, dict[int, tuple[str, str, str, str]]]] = []
                physical_values: dict[tuple[int, int], str] = {}
                for row_node in root.findall(".//m:sheetData/m:row", ns):
                    try:
                        excel_row = int(row_node.get("r") or len(physical_rows) + 1)
                    except ValueError:
                        excel_row = len(physical_rows) + 1
                    cells: dict[int, tuple[str, str, str, str]] = {}
                    for cell in row_node.findall("m:c", ns):
                        ref = str(cell.get("r") or "")
                        col = cls._xlsx_column_index(ref)
                        ctype = str(cell.get("t") or "")
                        try:
                            style_index = int(cell.get("s") or 0)
                        except ValueError:
                            style_index = 0
                        formula_node = cell.find("m:f", ns)
                        formula_text = "" if formula_node is None else str(formula_node.text or "").strip()
                        value_node = cell.find("m:v", ns)
                        raw = "" if value_node is None else str(value_node.text or "")

                        num_fmt_id = (
                            style_num_fmt_ids[style_index]
                            if 0 <= style_index < len(style_num_fmt_ids)
                            else 0
                        )
                        fmt_code = custom_formats.get(num_fmt_id, "")

                        if ctype == "inlineStr":
                            inline = cell.find("m:is", ns)
                            value = "" if inline is None else "".join(
                                node.text or "" for node in inline.iterfind(".//m:t", ns)
                            )
                            kind = "text"
                        elif ctype == "s":
                            try:
                                value = shared[int(raw)]
                            except (ValueError, IndexError):
                                value = raw
                            kind = "text"
                        elif ctype == "b":
                            value = "Oui" if raw == "1" else "Non"
                            kind = "bool"
                        elif ctype in {"str", "e"}:
                            value = raw
                            kind = "text"
                        elif raw == "":
                            value = ""
                            kind = "blank"
                        else:
                            if cls._xlsx_is_date_format(num_fmt_id, fmt_code):
                                try:
                                    serial = float(raw)
                                    base = datetime(1904, 1, 1) if date_1904 else datetime(1899, 12, 30)
                                    dt = base + timedelta(days=serial)
                                    # Les exports de bases utilisent surtout des dates sans heure.
                                    if abs(serial - int(serial)) < 1e-10:
                                        value = dt.strftime("%d/%m/%Y")
                                    else:
                                        value = dt.strftime("%d/%m/%Y %H:%M:%S")
                                    kind = "date"
                                except (TypeError, ValueError, OverflowError):
                                    value = raw
                                    kind = "text"
                            else:
                                try:
                                    number = float(raw)
                                    value = str(int(number)) if number.is_integer() else format(number, ".15g")
                                    kind = "number"
                                except ValueError:
                                    value = raw
                                    kind = "text"
                        cells[col] = (value, kind, formula_text, fmt_code)
                        physical_values[(excel_row, col)] = str(value or "")
                    if cells:
                        physical_rows.append((excel_row, cells))

                # Lire les vraies validations de données Excel. Une validation
                # type="list" appliquée à une colonne signifie que le champ MM3
                # correspondant doit devenir une Liste / Référentiel.
                validations: list[dict] = []
                data_validations = root.find("m:dataValidations", ns)
                if data_validations is not None:
                    for dv in data_validations.findall("m:dataValidation", ns):
                        if str(dv.get("type") or "").strip().casefold() != "list":
                            continue
                        sqref = str(dv.get("sqref") or "").strip()
                        formula_node = dv.find("m:formula1", ns)
                        formula = "" if formula_node is None else str(formula_node.text or "").strip()
                        if sqref and formula:
                            validations.append({"sqref": sqref, "formula": formula})

                # Première ligne non vide = ligne d'en-têtes.
                header_position = None
                header_cells: dict[int, tuple[str, str, str, str]] = {}
                for pos, (_excel_row, cells) in enumerate(physical_rows):
                    if any(str(value or "").strip() for value, _kind, _formula, _fmt in cells.values()):
                        header_position = pos
                        header_cells = cells
                        break

                if header_position is None:
                    sheets.append({
                        "name": sheet_name, "source_kind": "Excel", "fields": [],
                        "rows": 0, "rows_data": [], "header_row": None,
                        "excel_validations": validations,
                        "excel_cells": physical_values,
                    })
                    continue

                max_col = max(header_cells) if header_cells else -1
                # Étendre jusqu'à la dernière colonne réellement utilisée dans les données.
                for _excel_row, cells in physical_rows[header_position + 1:]:
                    if cells:
                        max_col = max(max_col, max(cells))

                headers: list[str] = []
                used_headers: dict[str, int] = {}
                for col in range(max_col + 1):
                    raw_header = str(header_cells.get(col, ("", "", "", ""))[0] or "").strip()
                    base_header = raw_header or f"Colonne {col + 1}"
                    marker = base_header.casefold()
                    count = used_headers.get(marker, 0) + 1
                    used_headers[marker] = count
                    header = base_header if count == 1 else f"{base_header}-{count}"
                    headers.append(header)

                rows_data: list[dict] = []
                kinds_by_col: list[list[str]] = [[] for _ in headers]
                formulas_by_col = [0 for _ in headers]
                formula_exprs_by_col: list[list[str]] = [[] for _ in headers]
                currency_symbols_by_col: list[list[str]] = [[] for _ in headers]
                for excel_row, cells in physical_rows[header_position + 1:]:
                    if not any(str(value or "").strip() for value, _kind, _formula, _fmt in cells.values()):
                        continue
                    row: dict[str, str] = {"__excel_row__": str(excel_row)}
                    for col, header in enumerate(headers):
                        value, kind, formula_text, fmt_code = cells.get(col, ("", "blank", "", ""))
                        row[header] = str(value or "")
                        if kind != "blank":
                            kinds_by_col[col].append(kind)
                        if formula_text:
                            formulas_by_col[col] += 1
                            translated = cls._xlsx_formula_to_mm3(formula_text, excel_row, headers)
                            if translated:
                                formula_exprs_by_col[col].append(translated)
                        symbol = cls._xlsx_currency_symbol(fmt_code)
                        if symbol:
                            currency_symbols_by_col[col].append(symbol)
                    rows_data.append(row)

                fields: list[dict] = []
                for col, header in enumerate(headers):
                    kinds = kinds_by_col[col]
                    nonblank = len(kinds)
                    counts = {kind: kinds.count(kind) for kind in set(kinds)}

                    symbols = currency_symbols_by_col[col]
                    currency_symbol = ""
                    if symbols:
                        currency_symbol = max(set(symbols), key=symbols.count)

                    translated_formulas = [
                        str(expr).strip() for expr in formula_exprs_by_col[col] if str(expr).strip()
                    ]
                    unique_formulas = list(dict.fromkeys(translated_formulas))
                    formula_expression = (
                        unique_formulas[0]
                        if formulas_by_col[col] > 0
                        and len(translated_formulas) == formulas_by_col[col]
                        and len(unique_formulas) == 1
                        else ""
                    )

                    if formula_expression:
                        detected = "Calculé"
                        kind_note = "formule Excel traduite en calcul MM3"
                    elif nonblank == 0:
                        detected = "Texte"
                        kind_note = "colonne vide"
                    elif counts.get("date", 0) / nonblank >= 0.8:
                        detected = "Date"
                        kind_note = "dates Excel"
                    elif counts.get("bool", 0) / nonblank >= 0.8:
                        detected = "Booléen"
                        kind_note = "valeurs Oui/Non"
                    elif counts.get("number", 0) / nonblank >= 0.8 and currency_symbol:
                        detected = "Monétaire"
                        kind_note = f"format monétaire Excel ({currency_symbol})"
                    elif counts.get("number", 0) / nonblank >= 0.8:
                        detected = "Nombre"
                        kind_note = "valeurs numériques"
                    else:
                        detected = "Texte"
                        kind_note = "contenu mixte ou texte"

                    if formula_expression:
                        formula_note = f" • formule : {formula_expression}"
                    elif formulas_by_col[col]:
                        formula_note = (
                            f" • {formulas_by_col[col]} formule(s) non traduite(s) : "
                            "valeur Excel conservée"
                        )
                    else:
                        formula_note = ""

                    fields.append({
                        "name": header,
                        "source_field": header,
                        "source_table": sheet_name,
                        "target_label": header,
                        "type": detected,
                        "source_order": col,
                        "calculation_expression": formula_expression,
                        "calculation_result_type": (
                            "Monétaire" if formula_expression and currency_symbol else
                            "Nombre" if formula_expression else ""
                        ),
                        "calculation_format": "truncate2",
                        "currency_symbol": currency_symbol,
                        "result_suffix": currency_symbol if formula_expression else "",
                        "excel_detection": f"Excel : {kind_note}{formula_note}",
                    })

                sheets.append({
                    "name": sheet_name,
                    "source_kind": "Excel",
                    "fields": fields,
                    "rows": len(rows_data),
                    "rows_data": rows_data,
                    "header_row": physical_rows[header_position][0],
                    "sheet_order": sheet_order,
                    "excel_validations": validations,
                    "excel_cells": physical_values,
                })

            # Résoudre les listes déroulantes après lecture de toutes les feuilles,
            # car leur source peut se trouver sur une autre feuille du classeur.
            sheet_by_name = {
                str(sheet.get("name") or "").casefold(): sheet for sheet in sheets
            }

            def parse_range_formula(formula: str):
                raw_formula = str(formula or "").strip()
                if raw_formula.startswith("="):
                    raw_formula = raw_formula[1:].strip()

                # Un nom défini Excel peut lui-même pointer vers une plage.
                named = defined_names.get(raw_formula.casefold())
                if named:
                    raw_formula = str(named).strip()
                    if raw_formula.startswith("="):
                        raw_formula = raw_formula[1:].strip()

                # Liste littérale Excel : "Oui,Non" ou "Oui;Non".
                if len(raw_formula) >= 2 and raw_formula[0] == '"' and raw_formula[-1] == '"':
                    payload = raw_formula[1:-1]
                    separator = ";" if ";" in payload and "," not in payload else ","
                    return {"literal": [v.strip() for v in payload.split(separator) if v.strip()]}

                match = re.fullmatch(
                    r"(?:'((?:[^']|'')+)'|([^!]+))!\$?([A-Z]{1,3})\$?(\d+)"
                    r"(?::\$?([A-Z]{1,3})\$?(\d+))?",
                    raw_formula,
                    flags=re.IGNORECASE,
                )
                if not match:
                    return None
                sheet_ref = (match.group(1) or match.group(2) or "").replace("''", "'").strip()
                col1 = cls._xlsx_column_index(match.group(3))
                row1 = int(match.group(4))
                col2 = cls._xlsx_column_index(match.group(5) or match.group(3))
                row2 = int(match.group(6) or match.group(4))
                return {
                    "sheet": sheet_ref, "col1": min(col1, col2), "col2": max(col1, col2),
                    "row1": min(row1, row2), "row2": max(row1, row2),
                }

            for sheet in sheets:
                fields = list(sheet.get("fields", []) or [])
                for validation in list(sheet.get("excel_validations", []) or []):
                    formula = str(validation.get("formula") or "").strip()
                    source_spec = parse_range_formula(formula)
                    if not source_spec:
                        continue

                    if "literal" in source_spec:
                        reference_values = list(source_spec["literal"])
                        source_description = "liste intégrée dans Excel"
                    else:
                        ref_sheet = sheet_by_name.get(str(source_spec["sheet"]).casefold())
                        if ref_sheet is None:
                            continue
                        cells = ref_sheet.get("excel_cells", {}) or {}
                        reference_values = []
                        seen_values = set()
                        for row_no in range(int(source_spec["row1"]), int(source_spec["row2"]) + 1):
                            for col_no in range(int(source_spec["col1"]), int(source_spec["col2"]) + 1):
                                value = str(cells.get((row_no, col_no), "") or "").strip()
                                marker = value.casefold()
                                if value and marker not in seen_values:
                                    seen_values.add(marker)
                                    reference_values.append(value)
                        source_description = (
                            f"{source_spec['sheet']}!"
                            f"{formula.split('!', 1)[-1] if '!' in formula else formula}"
                        )

                    # sqref peut contenir plusieurs plages séparées par des espaces.
                    target_columns = set()
                    for target_range in str(validation.get("sqref") or "").split():
                        first_ref = target_range.split(":", 1)[0]
                        col_match = re.match(r"\$?([A-Z]{1,3})", first_ref, flags=re.IGNORECASE)
                        if col_match:
                            target_columns.add(cls._xlsx_column_index(col_match.group(1)))

                    for col in target_columns:
                        if not (0 <= col < len(fields)):
                            continue
                        field = fields[col]
                        field["lookup_source"] = formula
                        field["excel_validation_formula"] = formula
                        field["excel_reference_values"] = list(reference_values)
                        field["type"] = "Liste"
                        field["excel_detection"] = (
                            f"Excel : liste déroulante reconnue → {source_description} "
                            f"({len(reference_values)} valeur(s))"
                        )

            return {"sheets": sheets, "format": "xlsx"}

    @staticmethod
    def _text_decode_bytes(raw: bytes) -> tuple[str, str]:
        """Décode un fichier texte courant sans dépendance externe."""
        if raw.startswith(b"\xef\xbb\xbf"):
            return raw.decode("utf-8-sig"), "UTF-8 (BOM)"
        if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
            return raw.decode("utf-16"), "UTF-16"
        for codec_name, label in (("utf-8", "UTF-8"), ("cp1252", "Windows-1252"), ("latin-1", "ISO-8859-1")):
            try:
                return raw.decode(codec_name), label
            except UnicodeDecodeError:
                continue
        return raw.decode("utf-8", errors="replace"), "UTF-8 (caractères remplacés)"

    @staticmethod
    def _text_guess_delimiter(text: str, suffix: str) -> tuple[str, str]:
        """Détecte le séparateur d'un fichier délimité sans casser les champs multilignes.

        Important : l'échantillon reste brut afin que csv.Sniffer voie correctement les
        retours à la ligne placés *dans* un champ entre guillemets. Le caractère | est
        accepté, notamment pour les fichiers TXT exportés par certains logiciels.
        """
        suffix = str(suffix or "").casefold()
        sample = str(text or "")[:65536]
        if suffix == ".tsv":
            return "\t", "tabulation"
        if not sample.strip():
            return ";", "point-virgule"

        candidates = (";", ",", "\t", "|")
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=";,\t|")
            delimiter = dialect.delimiter
        except csv.Error:
            # Repli robuste : choisir le séparateur donnant le nombre de colonnes le
            # plus régulier sur les enregistrements CSV réellement parsés. Cela évite
            # qu'une virgule décimale soit prise pour le séparateur d'un TXT en |.
            best = None
            for candidate in candidates:
                try:
                    rows = list(csv.reader(io.StringIO(sample, newline=""), delimiter=candidate, quotechar='"'))[:30]
                except csv.Error:
                    continue
                widths = [len(row) for row in rows if any(str(v).strip() for v in row)]
                if not widths:
                    continue
                common_width = max(set(widths), key=widths.count)
                consistent = sum(1 for width in widths if width == common_width)
                score = (common_width > 1, consistent, common_width)
                if best is None or score > best[0]:
                    best = (score, candidate)
            delimiter = best[1] if best and best[0][0] else ("\t" if "\t" in sample else ";")

        label = {";": "point-virgule", ",": "virgule", "\t": "tabulation", "|": "barre verticale |"}.get(delimiter, repr(delimiter))
        return delimiter, label

    @staticmethod
    def _text_clean_number(value: str) -> str | None:
        text = str(value or "").strip().replace("\u00a0", " ")
        if not text:
            return None
        text = re.sub(r"\s+", "", text)
        text = re.sub(r"^(?:€|\$|£|¥|CHF|CAD|AUD)", "", text, flags=re.I)
        text = re.sub(r"(?:€|\$|£|¥|CHF|CAD|AUD)$", "", text, flags=re.I)
        if not text:
            return None
        # 1 234,56 / 1.234,56 / 1,234.56 / 1234,56 / 1234.56
        if "," in text and "." in text:
            if text.rfind(",") > text.rfind("."):
                text = text.replace(".", "").replace(",", ".")
            else:
                text = text.replace(",", "")
        elif "," in text:
            parts = text.split(",")
            if len(parts) == 2 and 1 <= len(parts[1]) <= 6:
                text = parts[0] + "." + parts[1]
            elif len(parts) > 1 and all(len(p) == 3 for p in parts[1:]):
                text = "".join(parts)
            else:
                text = text.replace(",", ".")
        if re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)", text):
            return text
        return None

    @staticmethod
    def _text_is_date(value: str) -> bool:
        text = str(value or "").strip()
        if not text:
            return False
        formats = (
            "%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y",
            "%Y/%m/%d", "%d %m %Y",
        )
        for fmt in formats:
            try:
                datetime.strptime(text, fmt)
                return True
            except ValueError:
                pass
        return False

    @classmethod
    def _text_detect_column(cls, name: str, values: list[str]) -> dict:
        nonblank = [str(v or "").strip() for v in values if str(v or "").strip()]
        result = {
            "name": str(name), "source_field": str(name), "target_label": str(name),
            "source_order": 0, "type": "Texte", "physical_mm3_type": "Texte",
            "excel_detection": "",
        }
        if not nonblank:
            return result
        lowered = {v.casefold() for v in nonblank}
        bool_set = {"oui", "non", "yes", "no", "true", "false", "vrai", "faux", "1", "0", "on", "off"}
        if lowered <= bool_set and len(lowered) <= 4:
            result["type"] = "Bouton On / Off"
            result["physical_mm3_type"] = "Bouton On / Off"
            result["excel_detection"] = "Fichier texte : valeurs booléennes reconnues"
            return result
        date_hits = sum(1 for v in nonblank if cls._text_is_date(v))
        if date_hits == len(nonblank) and len(nonblank) >= 1:
            result["type"] = "Date"
            result["physical_mm3_type"] = "Date"
            result["excel_detection"] = "Fichier texte : dates reconnues"
            return result
        currency_tokens = ("€", "$", "£", "¥", "CHF", "CAD", "AUD")
        currency_hits = sum(1 for v in nonblank if any(tok.casefold() in v.casefold() for tok in currency_tokens))
        numeric_hits = sum(1 for v in nonblank if cls._text_clean_number(v) is not None)
        if numeric_hits == len(nonblank):
            # Un CSV ne transporte aucun format de cellule. En l'absence de symbole,
            # les libellés monétaires usuels constituent donc le seul indice fiable.
            # On reste volontairement conservateur pour ne pas transformer n'importe
            # quelle colonne numérique en monnaie.
            name_norm = re.sub(r"[^a-z0-9]+", " ", str(name or "").casefold()).strip()
            monetary_name = any(token in name_norm.split() for token in ("prix", "cout", "coût", "price", "cost", "montant", "amount", "valeur"))
            if currency_hits or monetary_name:
                result["type"] = "Monétaire"
                result["physical_mm3_type"] = "Monétaire"
                result["currency_symbol"] = "€"
                for symbol in currency_tokens:
                    if any(symbol.casefold() in v.casefold() for v in nonblank):
                        result["currency_symbol"] = symbol
                        break
                result["excel_detection"] = (
                    "Fichier texte : valeurs monétaires reconnues" if currency_hits
                    else "Fichier texte : colonne monétaire reconnue par son libellé"
                )
            else:
                result["type"] = "Nombre"
                result["physical_mm3_type"] = "Nombre"
                result["excel_detection"] = "Fichier texte : valeurs numériques reconnues"
        return result

    @classmethod
    def _read_delimited_text(cls, path: Path) -> dict:
        raw = path.read_bytes()
        text, encoding_label = cls._text_decode_bytes(raw)
        delimiter, delimiter_label = cls._text_guess_delimiter(text, path.suffix)
        reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter, quotechar='"')
        parsed = [list(row) for row in reader]
        # Ignorer uniquement les lignes entièrement vides avant les en-têtes.
        header_index = next((i for i, row in enumerate(parsed) if any(str(v).strip() for v in row)), None)
        if header_index is None:
            raise RuntimeError("Le fichier ne contient aucune donnée lisible.")
        headers_raw = parsed[header_index]
        width = max([len(headers_raw)] + [len(r) for r in parsed[header_index + 1:]] or [len(headers_raw)])
        headers = []
        used = {}
        for i in range(width):
            base = str(headers_raw[i] if i < len(headers_raw) else "").strip() or f"Colonne {i + 1}"
            marker = base.casefold()
            used[marker] = used.get(marker, 0) + 1
            name = base if used[marker] == 1 else f"{base}-{used[marker]}"
            headers.append(name)
        rows_data = []
        for row in parsed[header_index + 1:]:
            padded = [str(row[i] if i < len(row) else "") for i in range(width)]
            if not any(v.strip() for v in padded):
                continue
            rows_data.append(dict(zip(headers, padded)))
        fields = []
        for idx, name in enumerate(headers):
            field = cls._text_detect_column(name, [r.get(name, "") for r in rows_data])
            field["source_order"] = idx
            fields.append(field)
        source_kind = {".csv": "CSV", ".tsv": "TSV", ".txt": "TXT"}.get(path.suffix.casefold(), "CSV / TXT / TSV")
        table = {
            "name": path.stem,
            "source_kind": source_kind,
            "fields": fields,
            "rows": len(rows_data),
            "rows_data": rows_data,
            "header_row": header_index + 1,
            "encoding": encoding_label,
            "delimiter": delimiter,
            "delimiter_label": delimiter_label,
        }
        return {"tables": [table], "format": source_kind, "encoding": encoding_label, "delimiter_label": delimiter_label}

    def _set_access_step_highlight(self, button) -> None:
        """Met en évidence l’étape suivante du parcours Access."""
        buttons = (
            self.choose_access_btn, self.analyse_access_btn, self.choose_table_btn,
            self.preview_btn, self.mapping_btn, self.real_import_btn,
        )
        for candidate in buttons:
            try:
                candidate.setDefault(False)
                candidate.setAutoDefault(True)
            except Exception:
                pass
        if button is not None and button.isEnabled():
            button.setDefault(True)
            button.setFocus(Qt.FocusReason.OtherFocusReason)

    def _set_excel_step_highlight(self, button) -> None:
        """Met en évidence l’étape suivante du parcours Excel."""
        buttons = (
            self.choose_excel_btn, self.analyse_excel_btn, self.choose_sheet_btn,
            self.excel_preview_btn, self.excel_mapping_btn, self.excel_real_import_btn,
        )
        for candidate in buttons:
            try:
                candidate.setDefault(False)
                candidate.setAutoDefault(True)
            except Exception:
                pass
        if button is not None and button.isEnabled():
            button.setDefault(True)
            button.setFocus(Qt.FocusReason.OtherFocusReason)

    def _set_text_step_highlight(self, button) -> None:
        """Met en évidence l'étape suivante du parcours CSV/TXT/TSV."""
        buttons = (
            self.choose_text_btn, self.analyse_text_btn, self.choose_text_table_btn,
            self.text_preview_btn, self.text_mapping_btn, self.text_real_import_btn,
        )
        for candidate in buttons:
            try:
                candidate.setDefault(False)
                candidate.setAutoDefault(True)
            except Exception:
                pass
        if button is not None and button.isEnabled():
            button.setDefault(True)
            button.setFocus(Qt.FocusReason.OtherFocusReason)

    def _set_ods_step_highlight(self, button) -> None:
        """Met en évidence l’étape suivante du parcours ODS."""
        buttons = (
            self.choose_ods_btn, self.analyse_ods_btn, self.choose_ods_table_btn,
            self.ods_preview_btn, self.ods_mapping_btn, self.ods_real_import_btn,
        )
        for candidate in buttons:
            try:
                candidate.setDefault(False)
                candidate.setAutoDefault(True)
            except Exception:
                pass
        if button is not None and button.isEnabled():
            button.setDefault(True)
            button.setFocus(Qt.FocusReason.OtherFocusReason)

    def _set_dbf_step_highlight(self, button) -> None:
        """Met en évidence l'étape suivante du parcours DBF."""
        buttons = (
            self.choose_dbf_btn, self.analyse_dbf_btn, self.choose_dbf_table_btn,
            self.dbf_preview_btn, self.dbf_mapping_btn, self.dbf_real_import_btn,
        )
        for candidate in buttons:
            try:
                candidate.setDefault(False)
                candidate.setAutoDefault(True)
            except Exception:
                pass
        if button is not None and button.isEnabled():
            button.setDefault(True)
            button.setFocus(Qt.FocusReason.OtherFocusReason)

    def _choose_text_file(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self, tr("Choisir un fichier CSV / TXT / TSV", self.language), "",
            tr("Fichiers tabulaires (*.csv *.txt *.tsv);;CSV (*.csv);;Texte (*.txt);;TSV (*.tsv);;Tous les fichiers (*.*)", self.language),
        )
        if not filename:
            return
        source = Path(filename)
        if source.suffix.casefold() not in {".csv", ".txt", ".tsv"}:
            QMessageBox.warning(self, "Import CSV / TXT / TSV", "Le fichier choisi doit être au format .csv, .txt ou .tsv.")
            return
        self.text_source = source
        self.text_structure = None
        self.selected_text_table = None
        self.text_field_mapping = None
        self.text_structure_tree.clear()
        self.choose_text_table_btn.setEnabled(False)
        self.text_preview_btn.setEnabled(False)
        self.text_mapping_btn.setEnabled(False)
        self.text_real_import_btn.setEnabled(False)
        self.analyse_text_btn.setEnabled(True)
        self._set_text_step_highlight(self.analyse_text_btn)
        self.text_analysis_summary.setText(tr("Fichier sélectionné. Cliquez sur « Analyser le fichier ».", self.language))
        try:
            size_mb = source.stat().st_size / (1024 * 1024)
            size_text = f" — {size_mb:.1f} Mo"
        except OSError:
            size_text = ""
        self.text_source_label.setText(
            tr("Fichier sélectionné : {source}{size}\nAucune donnée n’est importée ou modifiée pendant l’analyse.", self.language).format(source=source, size=size_text)
        )

    def _analyse_text_file(self) -> None:
        if self.text_source is None:
            return
        if not self.text_source.exists():
            QMessageBox.warning(self, "Import CSV / TXT / TSV", "Le fichier sélectionné est introuvable.")
            return
        self.analyse_text_btn.setEnabled(False)
        self.choose_text_btn.setEnabled(False)
        self.text_analysis_summary.setText(tr("Analyse du fichier en cours…", self.language))
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        QApplication.processEvents()
        try:
            result = self._read_delimited_text(self.text_source)
        except Exception as exc:
            self.text_structure_tree.clear()
            self.text_analysis_summary.setText(tr("L’analyse n’a pas pu être effectuée.", self.language))
            QMessageBox.warning(self, "Analyse CSV / TXT / TSV impossible", str(exc))
            return
        finally:
            QApplication.restoreOverrideCursor()
            self.analyse_text_btn.setEnabled(True)
            self.choose_text_btn.setEnabled(True)
        self.text_structure = result
        table = (result.get("tables") or [None])[0]
        self.selected_text_table = None
        self.text_field_mapping = None
        self.text_structure_tree.clear()
        if not table:
            self.text_analysis_summary.setText(tr("Analyse terminée : aucune table de données trouvée.", self.language))
            return
        fields = list(table.get("fields") or [])
        rows = int(table.get("rows") or 0)
        item = QTreeWidgetItem([str(table.get("name") or ""), tr("{count} colonne(s)", self.language).format(count=len(fields)), str(rows)])
        font = item.font(0); font.setBold(True); item.setFont(0, font)
        self.text_structure_tree.addTopLevelItem(item)
        for field in fields:
            item.addChild(QTreeWidgetItem([str(field.get("name") or ""), tr(str(field.get("type") or "Texte"), self.language), ""]))
        item.setExpanded(True)
        self.text_structure_tree.setCurrentItem(item)
        self.choose_text_table_btn.setEnabled(True)
        self._set_text_step_highlight(self.choose_text_table_btn)
        self.text_analysis_summary.setText(
            tr("Analyse terminée : {columns} colonne(s), {rows} ligne(s) — encodage {encoding} — séparateur : {delimiter}.", self.language).format(columns=len(fields), rows=rows, encoding=table.get('encoding'), delimiter=tr(str(table.get('delimiter_label') or ''), self.language))
        )
        self.text_choice_label.setText(tr("Fichier analysé. Cliquez sur « Choisir ce fichier » pour le retenir comme source.", self.language))

    def _selected_text_item(self):
        items = self.text_structure_tree.selectedItems()
        if len(items) != 1:
            return None
        return items[0] if items[0].parent() is None else None

    def _on_text_structure_selection_changed(self) -> None:
        enabled = self._selected_text_item() is not None
        self.choose_text_table_btn.setEnabled(enabled)
        if enabled and self.selected_text_table is None:
            self._set_text_step_highlight(self.choose_text_table_btn)

    def _on_text_structure_double_clicked(self, item, _column: int) -> None:
        if item is not None and item.parent() is None:
            self._choose_selected_text_table()

    def _choose_selected_text_table(self) -> None:
        if not self.text_structure or self._selected_text_item() is None:
            return
        table = (self.text_structure.get("tables") or [None])[0]
        if not table:
            return
        self.selected_text_table = table
        self.text_field_mapping = None
        self.text_choice_label.setText(
            tr("✓ Source retenue : {name} — {rows} ligne(s), {columns} colonne(s) — {encoding}, séparateur {delimiter}.", self.language).format(name=table.get('name'), rows=table.get('rows', 0), columns=len(table.get('fields') or []), encoding=table.get('encoding'), delimiter=tr(str(table.get('delimiter_label') or ''), self.language))
        )
        self.text_preview_btn.setEnabled(True)
        self.text_mapping_btn.setEnabled(True)
        self.text_real_import_btn.setEnabled(False)
        self._set_text_step_highlight(self.text_mapping_btn)
        self.text_next_step_label.setText(
            tr("Source validée. L’ordre des lignes sera conservé. Cliquez sur « Correspondance des champs… ».", self.language)
        )

    def _text_preview_data(self, limit: int = 10) -> dict:
        if self.selected_text_table is None:
            return {"columns": [], "rows": []}
        fields = [str(f.get("name") or "") for f in self.selected_text_table.get("fields", []) or []]
        rows = [[str(source_row.get(field, "") or "") for field in fields]
                for source_row in list(self.selected_text_table.get("rows_data", []) or [])[:max(1, int(limit))]]
        return {"columns": fields, "rows": rows}

    def _open_text_preview(self) -> None:
        if self.selected_text_table is None:
            return
        preview = self._text_preview_data(10)
        try:
            if self._text_preview_window is not None and self._text_preview_window.isVisible():
                self._text_preview_window.close()
        except RuntimeError:
            self._text_preview_window = None
        window = AccessDataPreviewDialog(str(self.selected_text_table.get("name") or tr("Fichier texte", self.language)), preview, None, language=self.language)
        window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        window.destroyed.connect(lambda *_: setattr(self, "_text_preview_window", None))
        self._text_preview_window = window
        window.show(); window.raise_(); window.activateWindow()

    def _open_text_field_mapping(self) -> None:
        if self.selected_text_table is None:
            return
        try:
            if self._text_mapping_window is not None and self._text_mapping_window.isVisible():
                self._text_mapping_window.raise_(); self._text_mapping_window.activateWindow(); return
        except RuntimeError:
            self._text_mapping_window = None
        dialog = AccessFieldMappingDialog(
            self.selected_text_table, None, preview_loader=lambda: self._text_preview_data(10),
            language=self.language, model_key=self._selected_import_template(),
        )
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        dialog.finished.connect(lambda result, d=dialog: self._text_field_mapping_finished(d, result))
        dialog.destroyed.connect(lambda *_: setattr(self, "_text_mapping_window", None))
        self._text_mapping_window = dialog
        dialog.show(); dialog.raise_(); dialog.activateWindow()

    def _text_field_mapping_finished(self, dialog: AccessFieldMappingDialog, result: int) -> None:
        if result != int(QDialog.DialogCode.Accepted) or not dialog.mapping:
            return
        self.text_field_mapping = list(dialog.mapping)
        imported = sum(1 for item in self.text_field_mapping if item.get("action") == "Importer")
        ignored = len(self.text_field_mapping) - imported
        self.text_next_step_label.setText(
            tr("✓ Correspondance validée : {imported} champ(s) seront importés, {ignored} ignoré(s). Prêt pour la création de la collection et l’import des lignes.", self.language).format(imported=imported, ignored=ignored)
        )
        self.text_real_import_btn.setEnabled(imported > 0)
        if imported > 0:
            self._set_text_step_highlight(self.text_real_import_btn)

    def _start_text_import(self) -> None:
        if self.text_source is None or self.selected_text_table is None or not self.text_field_mapping:
            return
        imported_mapping = [m for m in self.text_field_mapping if m.get("action") == "Importer"]
        if not imported_mapping:
            return
        rows = int(self.selected_text_table.get("rows") or 0)
        source_kind = str(self.selected_text_table.get("source_kind") or "CSV / TXT / TSV")
        dialog = AccessImportDestinationDialog(
            str(self.selected_text_table.get("name") or self.text_source.stem), rows, len(imported_mapping), self,
            source_kind=source_kind,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        name = dialog.collection_name()
        folder = self._workspace_collections_folder()
        destination = folder / (self._safe_filename(name) + ".coldb")
        if destination.exists():
            QMessageBox.warning(self, tr("Nom déjà utilisé", self.language), tr("Le fichier « {name} » existe déjà.", self.language).format(name=destination.name))
            return
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle(tr("Lancer l’import {source} ?", self.language).format(source=source_kind))
        box.setText(
            tr("Créer la collection « {name} » et importer {rows} fiche(s) depuis {source} ?\n\nL’ordre des lignes sera conservé. Le fichier source ne sera jamais modifié.", self.language).format(name=name, rows=rows, source=source_kind)
        )
        yes_button = box.addButton(tr("Oui", self.language), QMessageBox.ButtonRole.YesRole)
        no_button = box.addButton(tr("Non", self.language), QMessageBox.ButtonRole.NoRole)
        box.setDefaultButton(no_button); box.exec()
        if box.clickedButton() is not yes_button:
            return
        progress = QProgressDialog(
            tr("Import du fichier « {source} » en cours…\nCréation de la collection et copie des lignes.", self.language).format(source=self.text_source.name),
            "", 0, 0, self,
        )
        progress.setWindowTitle(tr("Import {source} en cours", self.language).format(source=source_kind))
        progress.setCancelButton(None); progress.setWindowModality(Qt.WindowModality.ApplicationModal)
        progress.setMinimumDuration(0); progress.setAutoClose(False); progress.setAutoReset(False)
        progress.show(); self.text_real_import_btn.setEnabled(False)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor); QApplication.processEvents()
        try:
            result = self._perform_excel_import(
                destination, name, imported_mapping,
                selected_sheet=self.selected_text_table,
                source_path=self.text_source,
                source_kind=source_kind,
            )
        except Exception as exc:
            try:
                if destination.exists(): destination.unlink()
            except Exception:
                pass
            progress.close()
            QMessageBox.critical(self, tr("Import {source} interrompu", self.language).format(source=source_kind), tr("L’import n’a pas été conservé.", self.language) + "\n\n" + str(exc))
            self.text_real_import_btn.setEnabled(True)
            return
        finally:
            QApplication.restoreOverrideCursor()
        progress.close(); self.text_real_import_btn.setEnabled(True)
        self.text_next_step_label.setText(
            tr("✓ Import terminé : {records} fiche(s) créées dans « {name} » — ordre des lignes conservé.", self.language).format(records=result['records'], name=name)
        )
        QMessageBox.information(
            self, tr("Import {source} terminé", self.language).format(source=source_kind),
            tr("Import terminé avec succès.\n\nCollection : {name}\nFiches créées : {records}\nChamps importés : {fields}\nValeurs de référentiels : {values}\n\nOrdre des fiches : ordre des lignes source conservé.", self.language).format(name=name, records=result['records'], fields=result['fields'], values=result.get('referential_values', 0)),
        )

    def _choose_ods_file(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self, tr("Choisir un fichier ODS", self.language), "",
            tr("Classeurs OpenDocument (*.ods);;Tous les fichiers (*.*)", self.language),
        )
        if not filename:
            return
        source = Path(filename)
        if source.suffix.casefold() != ".ods":
            QMessageBox.warning(self, tr("Import ODS", self.language), tr("Le classeur choisi doit être au format .ods.", self.language))
            return
        self.ods_source = source
        self.ods_structure = None
        self.selected_ods_sheet = None
        self.ods_field_mapping = None
        self.ods_structure_tree.clear()
        self.choose_ods_table_btn.setEnabled(False)
        self.ods_preview_btn.setEnabled(False)
        self.ods_mapping_btn.setEnabled(False)
        self.ods_real_import_btn.setEnabled(False)
        self.analyse_ods_btn.setEnabled(True)
        self._set_ods_step_highlight(self.analyse_ods_btn)
        self.ods_analysis_summary.setText(tr("Fichier sélectionné. Cliquez sur « Analyser le fichier ».", self.language))
        try:
            size_mb = source.stat().st_size / (1024 * 1024)
            size_text = f" — {size_mb:.1f} Mo"
        except OSError:
            size_text = ""
        self.ods_source_label.setText(
            tr("Fichier sélectionné : {source}{size}\nAucune donnée n’est importée ou modifiée pendant l’analyse.", self.language).format(source=source, size=size_text)
        )

    def _analyse_ods_file(self) -> None:
        if self.ods_source is None:
            return
        if not self.ods_source.exists():
            QMessageBox.warning(self, tr("Import ODS", self.language), tr("Le classeur sélectionné est introuvable.", self.language))
            return
        self.analyse_ods_btn.setEnabled(False)
        self.choose_ods_btn.setEnabled(False)
        self.ods_analysis_summary.setText(tr("Analyse du classeur ODS en cours…", self.language))
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor); QApplication.processEvents()
        try:
            result = self._read_ods_workbook(self.ods_source)
        except Exception as exc:
            self.ods_structure_tree.clear()
            self.ods_analysis_summary.setText(tr("L’analyse n’a pas pu être effectuée.", self.language))
            QMessageBox.warning(self, tr("Analyse ODS impossible", self.language), str(exc))
            return
        finally:
            QApplication.restoreOverrideCursor()
            self.analyse_ods_btn.setEnabled(True); self.choose_ods_btn.setEnabled(True)
        self.ods_structure = result
        self.selected_ods_sheet = None; self.ods_field_mapping = None
        self.ods_structure_tree.clear()
        sheets = list(result.get("sheets", []) or [])
        total_rows=0; total_fields=0
        for sheet in sheets:
            fields=list(sheet.get("fields",[]) or []); rows=int(sheet.get("rows") or 0)
            total_rows += rows; total_fields += len(fields)
            item=QTreeWidgetItem([str(sheet.get("name") or ""), tr("{count} colonne(s)", self.language).format(count=len(fields)), str(rows)])
            font=item.font(0); font.setBold(True); item.setFont(0,font)
            item.setData(0, Qt.ItemDataRole.UserRole, str(sheet.get("name") or ""))
            self.ods_structure_tree.addTopLevelItem(item)
            for field in fields:
                item.addChild(QTreeWidgetItem([str(field.get("name") or ""), tr(str(field.get("type") or "Texte"), self.language), ""]))
            item.setExpanded(len(sheets)==1)
        self.ods_analysis_summary.setText(
            tr("Analyse terminée : {sheets} feuille(s), {fields} colonne(s), {rows} ligne(s) de données au total.", self.language).format(sheets=len(sheets), fields=total_fields, rows=total_rows)
        )
        self.ods_choice_label.setText(tr("Sélectionnez une feuille dans la liste ci-dessus.", self.language))
        if len(sheets)==1:
            self.ods_structure_tree.setCurrentItem(self.ods_structure_tree.topLevelItem(0))

    def _selected_ods_item(self):
        items = self.ods_structure_tree.selectedItems()
        if len(items) != 1:
            return None
        return items[0] if items[0].parent() is None else None

    def _on_ods_structure_selection_changed(self) -> None:
        enabled = self._selected_ods_item() is not None
        self.choose_ods_table_btn.setEnabled(enabled)
        if enabled and self.selected_ods_sheet is None:
            self._set_ods_step_highlight(self.choose_ods_table_btn)

    def _on_ods_structure_double_clicked(self, item, _column: int) -> None:
        if item is not None and item.parent() is None:
            self._choose_selected_ods_table()

    def _choose_selected_ods_table(self) -> None:
        item=self._selected_ods_item()
        if item is None or not self.ods_structure:
            return
        name=item.text(0)
        sheet=next((x for x in self.ods_structure.get("sheets",[]) or [] if str(x.get("name") or "")==name),None)
        if sheet is None:
            return
        self.selected_ods_sheet=sheet; self.ods_field_mapping=None
        rows=int(sheet.get("rows") or 0); fields=list(sheet.get("fields",[]) or [])
        self.ods_choice_label.setText(tr("✓ Feuille source retenue : {name} — {rows} ligne(s), {fields} colonne(s).", self.language).format(name=name, rows=rows, fields=len(fields)))
        self.ods_preview_btn.setEnabled(True); self.ods_mapping_btn.setEnabled(True); self.ods_real_import_btn.setEnabled(False)
        self._set_ods_step_highlight(self.ods_mapping_btn)
        self.ods_next_step_label.setText(tr("Feuille source validée. L’ordre des lignes sera conservé. Cliquez sur « Correspondance des champs… ».", self.language))

    def _ods_preview_data(self, limit: int = 10) -> dict:
        if self.selected_ods_sheet is None:
            return {"columns": [], "rows": []}
        fields = [str(f.get("name") or "") for f in self.selected_ods_sheet.get("fields", []) or []]
        rows = [[str(source_row.get(field, "") or "") for field in fields]
                for source_row in list(self.selected_ods_sheet.get("rows_data", []) or [])[:max(1, int(limit))]]
        return {"columns": fields, "rows": rows}

    def _open_ods_preview(self) -> None:
        if self.selected_ods_sheet is None:
            return
        preview = self._ods_preview_data(10)
        try:
            if self._ods_preview_window is not None and self._ods_preview_window.isVisible():
                self._ods_preview_window.close()
        except RuntimeError:
            self._ods_preview_window = None
        window = AccessDataPreviewDialog(str(self.selected_ods_sheet.get("name") or "Feuille ODS"), preview, None)
        window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        window.destroyed.connect(lambda *_: setattr(self, "_ods_preview_window", None))
        self._ods_preview_window = window
        window.show(); window.raise_(); window.activateWindow()

    def _open_ods_field_mapping(self) -> None:
        if self.selected_ods_sheet is None:
            return
        try:
            if self._ods_mapping_window is not None and self._ods_mapping_window.isVisible():
                self._ods_mapping_window.raise_(); self._ods_mapping_window.activateWindow(); return
        except RuntimeError:
            self._ods_mapping_window = None
        dialog = AccessFieldMappingDialog(
            self.selected_ods_sheet, None, preview_loader=lambda: self._ods_preview_data(10),
            language=self.language, model_key=self._selected_import_template(),
        )
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        dialog.finished.connect(lambda result, d=dialog: self._ods_field_mapping_finished(d, result))
        dialog.destroyed.connect(lambda *_: setattr(self, "_ods_mapping_window", None))
        self._ods_mapping_window = dialog
        dialog.show(); dialog.raise_(); dialog.activateWindow()

    def _ods_field_mapping_finished(self, dialog: AccessFieldMappingDialog, result: int) -> None:
        if result != int(QDialog.DialogCode.Accepted) or not dialog.mapping:
            return
        self.ods_field_mapping = list(dialog.mapping)
        imported = sum(1 for item in self.ods_field_mapping if item.get("action") == "Importer")
        ignored = len(self.ods_field_mapping) - imported
        self.ods_next_step_label.setText(tr("✓ Correspondance validée : {imported} champ(s) seront importés, {ignored} ignoré(s). Prêt pour la création de la collection et l’import des lignes.", self.language).format(imported=imported, ignored=ignored))
        self.ods_real_import_btn.setEnabled(imported > 0)
        if imported > 0:
            self._set_ods_step_highlight(self.ods_real_import_btn)

    def _start_ods_import(self) -> None:
        if self.ods_source is None or self.selected_ods_sheet is None or not self.ods_field_mapping:
            return
        imported_mapping = [m for m in self.ods_field_mapping if m.get("action") == "Importer"]
        if not imported_mapping:
            return
        rows = int(self.selected_ods_sheet.get("rows") or 0)
        source_kind = "ODS"
        dialog = AccessImportDestinationDialog(
            str(self.selected_ods_sheet.get("name") or self.ods_source.stem), rows, len(imported_mapping), self,
            source_kind=source_kind,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        name = dialog.collection_name()
        folder = self._workspace_collections_folder()
        destination = folder / (self._safe_filename(name) + ".coldb")
        if destination.exists():
            QMessageBox.warning(self, tr("Nom déjà utilisé", self.language), tr("Le fichier « {name} » existe déjà.", self.language).format(name=destination.name))
            return
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle(tr("Lancer l’import {source} ?", self.language).format(source=source_kind))
        box.setText(
            tr("Créer la collection « {name} » et importer {rows} fiche(s) depuis {source} ?\n\nL’ordre des lignes sera conservé. Le fichier source ne sera jamais modifié.", self.language).format(name=name, rows=rows, source=source_kind)
        )
        yes_button = box.addButton(tr("Oui", self.language), QMessageBox.ButtonRole.YesRole)
        no_button = box.addButton(tr("Non", self.language), QMessageBox.ButtonRole.NoRole)
        box.setDefaultButton(no_button); box.exec()
        if box.clickedButton() is not yes_button:
            return
        progress = QProgressDialog(
            tr("Import du fichier « {source} » en cours…\nCréation de la collection et copie des lignes.", self.language).format(source=self.ods_source.name),
            "", 0, 0, self,
        )
        progress.setWindowTitle(tr("Import {source} en cours", self.language).format(source=source_kind))
        progress.setCancelButton(None); progress.setWindowModality(Qt.WindowModality.ApplicationModal)
        progress.setMinimumDuration(0); progress.setAutoClose(False); progress.setAutoReset(False)
        progress.show(); self.ods_real_import_btn.setEnabled(False)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor); QApplication.processEvents()
        try:
            result = self._perform_excel_import(
                destination, name, imported_mapping,
                selected_sheet=self.selected_ods_sheet,
                source_path=self.ods_source,
                source_kind=source_kind,
            )
        except Exception as exc:
            try:
                if destination.exists(): destination.unlink()
            except Exception:
                pass
            progress.close()
            QMessageBox.critical(self, tr("Import {source} interrompu", self.language).format(source=source_kind), tr("L’import n’a pas été conservé.", self.language) + "\n\n" + str(exc))
            self.ods_real_import_btn.setEnabled(True)
            return
        finally:
            QApplication.restoreOverrideCursor()
        progress.close(); self.ods_real_import_btn.setEnabled(True)
        self.ods_next_step_label.setText(
            tr("✓ Import terminé : {records} fiche(s) créées dans « {name} » — ordre des lignes conservé.", self.language).format(records=result['records'], name=name)
        )
        QMessageBox.information(
            self, tr("Import {source} terminé", self.language).format(source=source_kind),
            tr("Import terminé avec succès.\n\nCollection : {name}\nFiches créées : {records}\nChamps importés : {fields}\nValeurs de référentiels : {values}\n\nOrdre des fiches : ordre des lignes source conservé.", self.language).format(name=name, records=result['records'], fields=result['fields'], values=result.get('referential_values', 0)),
        )


    def _choose_dbf_file(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self, tr("Choisir un fichier DBF", self.language), "", tr(tr("Fichiers DBF (*.dbf);;Tous les fichiers (*.*)", self.language), self.language)
        )
        if not filename:
            return
        source=Path(filename)
        if source.suffix.casefold() != ".dbf":
            QMessageBox.warning(self, "Import DBF", tr("Le fichier choisi doit être au format .dbf.", self.language))
            return
        self.dbf_source=source; self.dbf_structure=None; self.selected_dbf_table=None; self.dbf_field_mapping=None
        self.dbf_structure_tree.clear(); self.analyse_dbf_btn.setEnabled(True)
        self.choose_dbf_table_btn.setEnabled(False); self.dbf_preview_btn.setEnabled(False)
        self.dbf_mapping_btn.setEnabled(False); self.dbf_real_import_btn.setEnabled(False)
        try: size_text=f" — {source.stat().st_size / 1024:.1f} Ko"
        except Exception: size_text=""
        self.dbf_source_label.setText(tr("Fichier sélectionné : {source}{size}\nAucune donnée n’est importée ou modifiée pendant l’analyse.", self.language).format(source=source, size=size_text))
        self.dbf_analysis_summary.setText(tr("Fichier prêt à être analysé.", self.language))
        self._set_dbf_step_highlight(self.analyse_dbf_btn)

    def _analyse_dbf_file(self) -> None:
        if self.dbf_source is None: return
        if not self.dbf_source.exists():
            QMessageBox.warning(self,"Import DBF",tr("Le fichier sélectionné est introuvable.", self.language)); return
        self.analyse_dbf_btn.setEnabled(False); self.choose_dbf_btn.setEnabled(False)
        self.dbf_analysis_summary.setText(tr("Analyse du fichier DBF en cours…", self.language))
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor); QApplication.processEvents()
        try:
            result=self._read_dbf_file(self.dbf_source)
        except Exception as exc:
            self.dbf_structure_tree.clear(); self.dbf_analysis_summary.setText(tr("L’analyse n’a pas pu être effectuée.", self.language))
            QMessageBox.warning(self,tr("Analyse DBF impossible", self.language),str(exc)); return
        finally:
            QApplication.restoreOverrideCursor(); self.analyse_dbf_btn.setEnabled(True); self.choose_dbf_btn.setEnabled(True)
        self.dbf_structure=result; self.selected_dbf_table=None; self.dbf_field_mapping=None
        self.dbf_structure_tree.clear()
        tables=list(result.get("tables",[]) or [])
        total_rows=0; total_fields=0
        for table in tables:
            fields=list(table.get("fields",[]) or []); rows=int(table.get("rows") or 0)
            total_rows += rows; total_fields += len(fields)
            item=QTreeWidgetItem([str(table.get("name") or ""), tr("{count} champ(s)", self.language).format(count=len(fields)), str(rows)])
            font=item.font(0); font.setBold(True); item.setFont(0,font)
            item.setData(0, Qt.ItemDataRole.UserRole, str(table.get("name") or ""))
            self.dbf_structure_tree.addTopLevelItem(item)
            for field in fields:
                item.addChild(QTreeWidgetItem([str(field.get("name") or ""), tr(str(field.get("type") or "Texte"), self.language), ""]))
            item.setExpanded(True)
        enc=str(result.get("encoding") or "")
        version=str(result.get("version") or "")
        self.dbf_analysis_summary.setText(tr("Analyse terminée : {fields} champ(s), {rows} ligne(s). Encodage : {enc}. Version DBF : {version}.", self.language).format(fields=total_fields, rows=total_rows, enc=enc, version=version))
        self.dbf_choice_label.setText(tr("Sélectionnez le fichier analysé dans la liste ci-dessus.", self.language))
        if len(tables)==1: self.dbf_structure_tree.setCurrentItem(self.dbf_structure_tree.topLevelItem(0))

    def _selected_dbf_item(self):
        items=self.dbf_structure_tree.selectedItems()
        if len(items)!=1: return None
        return items[0] if items[0].parent() is None else None

    def _on_dbf_structure_selection_changed(self) -> None:
        enabled=self._selected_dbf_item() is not None
        self.choose_dbf_table_btn.setEnabled(enabled)
        if enabled and self.selected_dbf_table is None: self._set_dbf_step_highlight(self.choose_dbf_table_btn)

    def _on_dbf_structure_double_clicked(self,item,_column:int) -> None:
        if item is not None and item.parent() is None: self._choose_selected_dbf_table()

    def _choose_selected_dbf_table(self) -> None:
        item=self._selected_dbf_item()
        if item is None or not self.dbf_structure: return
        name=item.text(0)
        table=next((x for x in self.dbf_structure.get("tables",[]) or [] if str(x.get("name") or "")==name),None)
        if table is None: return
        self.selected_dbf_table=table; self.dbf_field_mapping=None
        rows=int(table.get("rows") or 0); fields=list(table.get("fields",[]) or [])
        self.dbf_choice_label.setText(tr("✓ Source DBF retenue : {name} — {rows} ligne(s), {fields} champ(s).", self.language).format(name=name, rows=rows, fields=len(fields)))
        self.dbf_preview_btn.setEnabled(True); self.dbf_mapping_btn.setEnabled(True); self.dbf_real_import_btn.setEnabled(False)
        self._set_dbf_step_highlight(self.dbf_mapping_btn)
        self.dbf_next_step_label.setText(tr("Source validée. L’ordre des enregistrements sera conservé. Cliquez sur « Correspondance des champs… ».", self.language))

    def _dbf_preview_data(self,limit:int=10)->dict:
        if self.selected_dbf_table is None: return {"columns":[],"rows":[]}
        fields=[str(f.get("name") or "") for f in self.selected_dbf_table.get("fields",[]) or []]
        rows=[[str(source_row.get(field,"") or "") for field in fields]
              for source_row in list(self.selected_dbf_table.get("rows_data",[]) or [])[:max(1,int(limit))]]
        return {"columns":fields,"rows":rows}

    def _open_dbf_preview(self)->None:
        if self.selected_dbf_table is None: return
        preview=self._dbf_preview_data(10)
        try:
            if self._dbf_preview_window is not None and self._dbf_preview_window.isVisible(): self._dbf_preview_window.close()
        except RuntimeError: self._dbf_preview_window=None
        window=AccessDataPreviewDialog(str(self.selected_dbf_table.get("name") or "DBF"),preview,None)
        window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose,True)
        window.destroyed.connect(lambda *_: setattr(self,"_dbf_preview_window",None))
        self._dbf_preview_window=window; window.show(); window.raise_(); window.activateWindow()

    def _open_dbf_field_mapping(self)->None:
        if self.selected_dbf_table is None: return
        try:
            if self._dbf_mapping_window is not None and self._dbf_mapping_window.isVisible():
                self._dbf_mapping_window.raise_(); self._dbf_mapping_window.activateWindow(); return
        except RuntimeError: self._dbf_mapping_window=None
        dialog=AccessFieldMappingDialog(self.selected_dbf_table,None,preview_loader=lambda:self._dbf_preview_data(10), language=self.language, model_key=self._selected_import_template())
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose,True)
        dialog.finished.connect(lambda result,d=dialog:self._dbf_field_mapping_finished(d,result))
        dialog.destroyed.connect(lambda *_: setattr(self,"_dbf_mapping_window",None))
        self._dbf_mapping_window=dialog; dialog.show(); dialog.raise_(); dialog.activateWindow()

    def _dbf_field_mapping_finished(self,dialog:AccessFieldMappingDialog,result:int)->None:
        if result != int(QDialog.DialogCode.Accepted) or not dialog.mapping: return
        self.dbf_field_mapping=list(dialog.mapping)
        imported=sum(1 for item in self.dbf_field_mapping if item.get("action")=="Importer")
        ignored=len(self.dbf_field_mapping)-imported
        self.dbf_next_step_label.setText(tr("✓ Correspondance validée : {imported} champ(s) seront importés, {ignored} ignoré(s). Prêt pour l’import.", self.language).format(imported=imported, ignored=ignored))
        self.dbf_real_import_btn.setEnabled(imported>0)
        if imported>0: self._set_dbf_step_highlight(self.dbf_real_import_btn)

    def _start_dbf_import(self)->None:
        if self.dbf_source is None or self.selected_dbf_table is None or not self.dbf_field_mapping: return
        imported_mapping=[m for m in self.dbf_field_mapping if m.get("action")=="Importer"]
        if not imported_mapping: return
        rows=int(self.selected_dbf_table.get("rows") or 0); source_kind="DBF"
        dialog=AccessImportDestinationDialog(str(self.selected_dbf_table.get("name") or self.dbf_source.stem),rows,len(imported_mapping),self,source_kind=source_kind, language=self.language)
        if dialog.exec()!=QDialog.DialogCode.Accepted: return
        name=dialog.collection_name(); folder=self._workspace_collections_folder(); destination=folder/(self._safe_filename(name)+".coldb")
        if destination.exists():
            QMessageBox.warning(self,tr("Nom déjà utilisé", self.language),tr("Le fichier « {name} » existe déjà.", self.language).format(name=destination.name)); return
        box=QMessageBox(self); box.setIcon(QMessageBox.Icon.Question); box.setWindowTitle(tr("Lancer l’import {source} ?", self.language).format(source=source_kind))
        box.setText(tr("Créer la collection « {name} » et importer {rows} fiche(s) depuis {source} ?\n\nL’ordre des enregistrements sera conservé. Le fichier source ne sera jamais modifié.", self.language).format(name=name, rows=rows, source=source_kind))
        yes_button=box.addButton(tr("Oui", self.language),QMessageBox.ButtonRole.YesRole); no_button=box.addButton(tr("Non", self.language),QMessageBox.ButtonRole.NoRole)
        box.setDefaultButton(no_button); box.exec()
        if box.clickedButton() is not yes_button: return
        progress=QProgressDialog(tr("Import du fichier « {source} » en cours…\nCréation de la collection et copie des lignes.", self.language).format(source=self.dbf_source.name),"",0,0,self)
        progress.setWindowTitle(tr("Import {source} en cours", self.language).format(source=source_kind)); progress.setCancelButton(None); progress.setWindowModality(Qt.WindowModality.ApplicationModal)
        progress.setMinimumDuration(0); progress.setAutoClose(False); progress.setAutoReset(False); progress.show()
        self.dbf_real_import_btn.setEnabled(False); QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor); QApplication.processEvents()
        try:
            result=self._perform_excel_import(destination,name,imported_mapping,selected_sheet=self.selected_dbf_table,source_path=self.dbf_source,source_kind=source_kind)
        except Exception as exc:
            try:
                if destination.exists(): destination.unlink()
            except Exception: pass
            progress.close(); QMessageBox.critical(self,tr("Import {source} interrompu", self.language).format(source=source_kind),tr("L’import n’a pas été conservé.", self.language)+"\n\n"+str(exc)); self.dbf_real_import_btn.setEnabled(True); return
        finally: QApplication.restoreOverrideCursor()
        progress.close(); self.dbf_real_import_btn.setEnabled(True)
        self.dbf_next_step_label.setText(tr("✓ Import terminé : {records} fiche(s) créées dans « {name} » — ordre conservé.", self.language).format(records=result["records"], name=name))
        QMessageBox.information(self,tr("Import {source} terminé", self.language).format(source=source_kind),tr("Import terminé avec succès.\n\nCollection : {name}\nFiches créées : {records}\nChamps importés : {fields}\nValeurs de référentiels : {values}\n\nOrdre des fiches : ordre des enregistrements DBF conservé.", self.language).format(name=name, records=result["records"], fields=result["fields"], values=result.get("referential_values",0)))

    @staticmethod
    def _sqlite_quote_identifier(name: str) -> str:
        return '"' + str(name).replace('"', '""') + '"'

    @classmethod
    def _sqlite_detect_field(cls, declared_type: str, field_name: str, values: list) -> tuple[str, str]:
        """Déduit un type métier MM3 depuis l'affinité SQLite et les valeurs observées."""
        decl = str(declared_type or "").strip().upper()
        name = str(field_name or "").strip().casefold()
        nonblank = [v for v in values if v is not None and (not isinstance(v, str) or v.strip() != "")]

        if "BOOL" in decl:
            return "Booléen", "type BOOLEAN/BOOL SQLite"
        if "DATE" in decl or "TIME" in decl:
            return "Date", "type date/heure SQLite"
        if "MONEY" in decl or "CURRENCY" in decl:
            return "Monétaire", "type monétaire SQLite"
        if "BLOB" in decl:
            return "Photo / Image", "données binaires SQLite"

        price_tokens = ("prix", "price", "cout", "coût", "montant", "amount", "tarif", "valeur", "value")
        numeric_decl = any(x in decl for x in ("INT", "REAL", "FLOA", "DOUB", "NUM", "DEC"))
        decimal_two = bool(re.search(r"(?:DECIMAL|NUMERIC)\s*\(\s*\d+\s*,\s*2\s*\)", decl))
        if numeric_decl and (decimal_two and any(tok in name for tok in price_tokens)):
            return "Monétaire", "numérique SQLite à 2 décimales identifié comme monétaire"
        if numeric_decl:
            return "Nombre", "type numérique SQLite"

        # SQLite autorise un typage souple : les valeurs peuvent apporter une
        # information plus précise qu'une déclaration TEXT ou vide.
        if nonblank:
            if all(isinstance(v, (bool, int)) and v in (0, 1, False, True) for v in nonblank) and any(tok in name for tok in ("oui", "non", "actif", "active", "bool", "lumines", "fluores")):
                return "Booléen", "valeurs 0/1 cohérentes avec un booléen"
            if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in nonblank):
                if any(tok in name for tok in price_tokens):
                    return "Monétaire", "valeurs numériques et nom de colonne monétaire"
                return "Nombre", "valeurs numériques SQLite"
            if all(isinstance(v, str) for v in nonblank):
                date_hits = 0
                for v in nonblank[:100]:
                    text = v.strip()
                    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y", "%d-%m-%Y"):
                        try:
                            datetime.strptime(text, fmt); date_hits += 1; break
                        except ValueError:
                            pass
                if date_hits >= max(1, int(min(len(nonblank), 100) * 0.8)):
                    return "Date", "valeurs texte reconnues comme dates"
        return "Texte", "type texte SQLite"

    @classmethod
    def _infer_sqlite_calculated_fields(cls, fields: list[dict], rows_data: list[dict]) -> None:
        """Détecte prudemment les calculs arithmétiques simples réellement prouvés par les données.

        SQLite ne conserve généralement aucune formule pour une colonne ordinaire.
        Cette détection n'invente donc un calcul que lorsque toutes les lignes
        numériques exploitables démontrent la même relation entre trois colonnes.
        """
        numeric_types = {"Nombre", "Monétaire"}
        numeric_fields = [f for f in fields if str(f.get("type") or "") in numeric_types]
        if len(numeric_fields) < 3 or len(rows_data) < 3:
            return

        def as_number(value):
            if value is None or isinstance(value, bool):
                return None
            if isinstance(value, (int, float)):
                return float(value)
            text = str(value).strip().replace("\xa0", " ")
            if not text:
                return None
            text = re.sub(r"[€$£¥]", "", text).replace("CHF", "").strip().replace(" ", "")
            if "," in text and "." not in text:
                text = text.replace(",", ".")
            try:
                return float(text)
            except ValueError:
                return None

        def matches(target_name, left_name, right_name, op):
            checked = 0
            varied_targets = set()
            for row in rows_data:
                t = as_number(row.get(target_name))
                a = as_number(row.get(left_name))
                b = as_number(row.get(right_name))
                if t is None or a is None or b is None:
                    continue
                if op == "*": expected = a * b
                elif op == "+": expected = a + b
                elif op == "-": expected = a - b
                elif op == "/":
                    if abs(b) < 1e-12: continue
                    expected = a / b
                else: return False
                tol = max(1e-7, abs(t) * 1e-7, abs(expected) * 1e-7)
                if abs(t - expected) > tol:
                    return False
                checked += 1
                varied_targets.add(round(t, 8))
            return checked >= 3 and len(varied_targets) >= 2

        already_sources = set()
        candidates = []
        for target in numeric_fields:
            target_name = str(target.get("name") or "")
            others = [f for f in numeric_fields if f is not target]
            for i, left in enumerate(others):
                for right in others[i + 1:]:
                    left_name = str(left.get("name") or "")
                    right_name = str(right.get("name") or "")
                    for op in ("*", "+"):
                        if matches(target_name, left_name, right_name, op):
                            candidates.append((target, left, right, op))
                            break
                    if candidates and candidates[-1][0] is target:
                        break
                if candidates and candidates[-1][0] is target:
                    break

        # Ne retenir qu'un calcul non ambigu par champ cible.
        by_target = {}
        for candidate in candidates:
            by_target.setdefault(id(candidate[0]), []).append(candidate)
        for group in by_target.values():
            if len(group) != 1:
                continue
            target, left, right, op = group[0]
            left_name = str(left.get("name") or "")
            right_name = str(right.get("name") or "")
            target["calculation_expression"] = f"[{left_name}] {op} [{right_name}]"
            target["calculation_result_type"] = "Monétaire" if (
                str(target.get("type") or "") == "Monétaire"
                or str(left.get("type") or "") == "Monétaire"
                or str(right.get("type") or "") == "Monétaire"
            ) else "Nombre"
            target["calculation_format"] = "truncate2"
            if target["calculation_result_type"] == "Monétaire":
                target["result_suffix"] = "€"
            target["excel_detection"] = (
                f"SQLite : calcul déduit des données → {target['calculation_expression']}"
            )

    @classmethod
    def _attach_sqlite_reference_specs(cls, tables: list[dict]) -> int:
        """Repère génériquement les tables de référentiel reliables à une table de fiches.

        Une table de référence est retenue lorsque sa clé primaire simple (ou, à
        défaut, sa première colonne réellement unique) correspond à une colonne
        de la table source et qu'au moins deux valeurs se recoupent. Aucun nom de
        table ou de champ métier n'est codé en dur.
        """
        if not tables:
            return 0

        def ident(value: str) -> str:
            text = unicodedata.normalize("NFKD", str(value or ""))
            text = "".join(ch for ch in text if not unicodedata.combining(ch))
            return "".join(ch.casefold() for ch in text if ch.isalnum())

        detected = 0
        for source in tables:
            source_fields = list(source.get("fields", []) or [])
            source_rows = list(source.get("rows_data", []) or [])
            if not source_fields or not source_rows:
                source["sqlite_reference_specs"] = []
                continue
            source_by_id = {ident(f.get("name")): f for f in source_fields if ident(f.get("name"))}
            specs = []
            claimed_master_ids = set()

            for ref in tables:
                if ref is source:
                    continue
                ref_fields = list(ref.get("fields", []) or [])
                ref_rows = list(ref.get("rows_data", []) or [])
                if len(ref_fields) < 2 or len(ref_rows) < 2:
                    continue

                pk_cols = list(ref.get("primary_key_columns", []) or [])
                master_name = pk_cols[0] if len(pk_cols) == 1 else ""

                # Sans clé primaire simple, MM3 reste volontairement prudent :
                # une colonne unique dans une table de fiches pourrait sinon être
                # prise à tort pour un référentiel. Ces cas pourront être proposés
                # manuellement dans le futur module d'import de référentiels.
                if not master_name:
                    continue

                master_id = ident(master_name)
                source_master_field = source_by_id.get(master_id)
                if source_master_field is None or master_id in claimed_master_ids:
                    continue

                ref_values = []
                ref_markers = set()
                for row in ref_rows:
                    value = str(row.get(master_name, "") or "").strip()
                    marker_value = value.casefold()
                    if value and marker_value not in ref_markers:
                        ref_markers.add(marker_value)
                        ref_values.append(value)
                if len(ref_values) < 2:
                    continue

                source_name = str(source_master_field.get("name") or "")
                source_markers = {
                    str(row.get(source_name, "") or "").strip().casefold()
                    for row in source_rows
                    if str(row.get(source_name, "") or "").strip()
                }
                overlap = len(source_markers & ref_markers)
                if overlap < 2:
                    continue

                linked = []
                for field in ref_fields:
                    linked_name = str(field.get("name") or "")
                    if ident(linked_name) == master_id:
                        continue
                    linked.append(dict(field))
                if not linked:
                    continue

                spec = {
                    "table_name": str(ref.get("name") or ""),
                    "master_source": source_name,
                    "master_reference": master_name,
                    "reference_values": ref_values,
                    "linked_fields": linked,
                    "rows_data": ref_rows,
                    "overlap": overlap,
                }
                specs.append(spec)
                claimed_master_ids.add(master_id)
                source_master_field["lookup_source"] = str(ref.get("name") or "")
                source_master_field["sqlite_reference_table"] = str(ref.get("name") or "")
                source_master_field["sqlite_reference_values"] = list(ref_values)
                source_master_field["excel_detection"] = (
                    f"SQLite : référentiel multi-colonnes reconnu dans « {ref.get('name')} » "
                    f"→ Maître + {len(linked)} champ(s) Relié(s)"
                )
                detected += 1

            source["sqlite_reference_specs"] = specs
        return detected

    @classmethod
    def _read_sqlite_database(cls, path: Path) -> dict:
        """Lit une base SQLite en lecture seule et renvoie ses tables utilisateur."""
        uri = path.resolve().as_uri() + "?mode=ro"
        con = sqlite3.connect(uri, uri=True)
        con.row_factory = sqlite3.Row
        try:
            quick = con.execute("PRAGMA quick_check").fetchone()
            if quick and str(quick[0]).casefold() != "ok":
                raise ValueError("La base SQLite signale une anomalie : " + str(quick[0]))
            names = [str(r[0]) for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name COLLATE NOCASE"
            ).fetchall()]
            if not names:
                raise ValueError("Cette base SQLite ne contient aucune table utilisateur lisible.")
            tables = []
            for table_order, table_name in enumerate(names):
                qname = cls._sqlite_quote_identifier(table_name)
                info = con.execute(f"PRAGMA table_info({qname})").fetchall()
                if not info:
                    continue
                col_names = [str(r[1]) for r in info]
                declared = {str(r[1]): str(r[2] or "") for r in info}
                count = int(con.execute(f"SELECT COUNT(*) FROM {qname}").fetchone()[0])

                # Ordre stable : rowid si disponible, sinon clé primaire, sinon
                # ordre fourni par SQLite pour un SELECT simple.
                order_clause = ""
                try:
                    con.execute(f"SELECT rowid FROM {qname} LIMIT 1").fetchone()
                    order_clause = " ORDER BY rowid"
                except sqlite3.DatabaseError:
                    pk_cols = [str(r[1]) for r in sorted(info, key=lambda x: int(x[5] or 0)) if int(r[5] or 0) > 0]
                    if pk_cols:
                        order_clause = " ORDER BY " + ", ".join(cls._sqlite_quote_identifier(c) for c in pk_cols)
                cursor = con.execute(f"SELECT * FROM {qname}{order_clause}")
                fetched = cursor.fetchall()
                rows_data = []
                by_col = {c: [] for c in col_names}
                for row in fetched:
                    d = {}
                    for c in col_names:
                        v = row[c]
                        if isinstance(v, bytes):
                            # Les BLOB restent des octets pour le moteur d'import.
                            d[c] = v
                        elif v is None:
                            d[c] = ""
                        else:
                            d[c] = v
                        by_col[c].append(v)
                    rows_data.append(d)
                fields = []
                for source_order, c in enumerate(col_names):
                    detected, note = cls._sqlite_detect_field(declared.get(c, ""), c, by_col[c])
                    fields.append({
                        "name": c,
                        "source_order": source_order,
                        "type": detected,
                        "declared_type": declared.get(c, ""),
                        "excel_detection": f"SQLite : {note}",
                    })
                cls._infer_sqlite_calculated_fields(fields, rows_data)
                pk_cols = [str(r[1]) for r in sorted(info, key=lambda x: int(x[5] or 0)) if int(r[5] or 0) > 0]
                tables.append({
                    "name": table_name,
                    "source_kind": "SQLite",
                    "fields": fields,
                    "rows": count,
                    "rows_data": rows_data,
                    "table_order": table_order,
                    "primary_key_columns": pk_cols,
                })
            if not tables:
                raise ValueError("Aucune table SQLite exploitable n'a été trouvée.")
            reference_count = cls._attach_sqlite_reference_specs(tables)
            return {"tables": tables, "format": "SQLite", "reference_count": reference_count}
        finally:
            con.close()

    def _set_sqlite_step_highlight(self, active_button=None) -> None:
        """Met en évidence l’étape suivante du parcours SQLite."""
        buttons = (
            getattr(self, "choose_sqlite_btn", None), getattr(self, "analyse_sqlite_btn", None),
            getattr(self, "choose_sqlite_table_btn", None), getattr(self, "sqlite_preview_btn", None),
            getattr(self, "sqlite_mapping_btn", None), getattr(self, "sqlite_real_import_btn", None),
        )
        for button in buttons:
            if button is None:
                continue
            try:
                button.setDefault(False)
                button.setAutoDefault(True)
            except Exception:
                pass
        if active_button is not None and active_button.isEnabled():
            active_button.setDefault(True)
            active_button.setFocus(Qt.FocusReason.OtherFocusReason)

    def _choose_sqlite_file(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self, tr("Choisir une base SQLite", self.language), "",
            tr(tr("Bases SQLite (*.db *.sqlite *.sqlite3);;Tous les fichiers (*.*)", self.language), self.language)
        )
        if not filename:
            return
        source = Path(filename)
        self.sqlite_source = source
        self.sqlite_structure = None; self.selected_sqlite_table = None; self.sqlite_field_mapping = None
        self.sqlite_structure_tree.clear()
        self.choose_sqlite_table_btn.setEnabled(False); self.sqlite_preview_btn.setEnabled(False)
        self.sqlite_mapping_btn.setEnabled(False); self.sqlite_real_import_btn.setEnabled(False)
        self.analyse_sqlite_btn.setEnabled(True)
        self._set_sqlite_step_highlight(self.analyse_sqlite_btn)
        try:
            size_mb = source.stat().st_size / (1024 * 1024); size_text = f" — {size_mb:.1f} Mo"
        except OSError:
            size_text = ""
        self.sqlite_source_label.setText(tr("Base sélectionnée : {source}{size}\nOuverture strictement en lecture seule pendant l’analyse.", self.language).format(source=source, size=size_text))
        self.sqlite_analysis_summary.setText(tr("Base sélectionnée. Cliquez sur « Analyser la base ».", self.language))

    def _analyse_sqlite_file(self) -> None:
        if self.sqlite_source is None:
            return
        if not self.sqlite_source.exists():
            QMessageBox.warning(self, "Import SQLite", "La base sélectionnée est introuvable."); return
        self.analyse_sqlite_btn.setEnabled(False); self.choose_sqlite_btn.setEnabled(False)
        self.sqlite_analysis_summary.setText(tr("Analyse de la base SQLite en cours…", self.language))
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor); QApplication.processEvents()
        try:
            result = self._read_sqlite_database(self.sqlite_source)
        except Exception as exc:
            self.sqlite_structure_tree.clear(); self.sqlite_analysis_summary.setText("L'analyse n'a pas pu être effectuée.")
            QMessageBox.warning(self, "Analyse SQLite impossible", str(exc)); return
        finally:
            QApplication.restoreOverrideCursor(); self.choose_sqlite_btn.setEnabled(True); self.analyse_sqlite_btn.setEnabled(True)
        self.sqlite_structure = result; self.selected_sqlite_table = None; self.sqlite_field_mapping = None
        self.sqlite_structure_tree.clear()
        total_fields = 0; total_rows = 0
        for table in result.get("tables", []) or []:
            fields = list(table.get("fields", []) or []); rows = int(table.get("rows") or 0)
            total_fields += len(fields); total_rows += rows
            root = QTreeWidgetItem([str(table.get("name") or ""), tr("{count} colonne(s)", self.language).format(count=len(fields)), str(rows)])
            root.setData(0, Qt.ItemDataRole.UserRole, "table")
            self.sqlite_structure_tree.addTopLevelItem(root)
            for field in fields:
                typ = str(field.get("type") or "Texte")
                declared = str(field.get("declared_type") or "").strip()
                type_text = tr(typ, self.language) + (f" ({declared})" if declared else "")
                child = QTreeWidgetItem([str(field.get("name") or ""), type_text, ""])
                child.setData(0, Qt.ItemDataRole.UserRole, "field"); root.addChild(child)
            root.setExpanded(True)
        tables = list(result.get("tables", []) or [])
        ref_count = int(result.get("reference_count") or 0)
        ref_text = tr(" — {count} référentiel(s) multi-colonnes reconnu(s).", self.language).format(count=ref_count) if ref_count else ""
        self.sqlite_analysis_summary.setText(
            tr("Analyse terminée : {tables} table(s), {fields} colonne(s), {rows} ligne(s) au total.{refs}", self.language).format(tables=len(tables), fields=total_fields, rows=total_rows, refs=ref_text)
        )
        self.sqlite_choice_label.setText(tr("Sélectionnez la table contenant les fiches à importer.", self.language))
        if len(tables) == 1:
            self.sqlite_structure_tree.setCurrentItem(self.sqlite_structure_tree.topLevelItem(0))

    def _selected_sqlite_item(self):
        items = self.sqlite_structure_tree.selectedItems()
        if len(items) != 1:
            return None
        return items[0] if items[0].parent() is None else None

    def _on_sqlite_structure_selection_changed(self) -> None:
        enabled = self._selected_sqlite_item() is not None
        self.choose_sqlite_table_btn.setEnabled(enabled)
        if enabled and self.selected_sqlite_table is None:
            self._set_sqlite_step_highlight(self.choose_sqlite_table_btn)

    def _on_sqlite_structure_double_clicked(self, item, _column: int) -> None:
        if item is not None and item.parent() is None:
            self._choose_selected_sqlite_table()

    def _choose_selected_sqlite_table(self) -> None:
        item = self._selected_sqlite_item()
        if item is None or not self.sqlite_structure:
            return
        name = item.text(0)
        table = next((x for x in self.sqlite_structure.get("tables", []) or [] if str(x.get("name") or "") == name), None)
        if table is None:
            return
        self.selected_sqlite_table = table; self.sqlite_field_mapping = None
        rows = int(table.get("rows") or 0); fields = list(table.get("fields", []) or [])
        refs = list(table.get("sqlite_reference_specs", []) or [])
        ref_suffix = tr(" — {count} référentiel(s) associé(s) reconnu(s).", self.language).format(count=len(refs)) if refs else ""
        self.sqlite_choice_label.setText(
            tr("✓ Table SQLite retenue : {name} — {rows} ligne(s), {fields} colonne(s){refs}", self.language).format(name=name, rows=rows, fields=len(fields), refs=ref_suffix)
        )
        self.sqlite_preview_btn.setEnabled(True); self.sqlite_mapping_btn.setEnabled(True); self.sqlite_real_import_btn.setEnabled(False)
        self._set_sqlite_step_highlight(self.sqlite_mapping_btn)
        self.sqlite_next_step_label.setText(tr("Table validée. Cliquez sur « Correspondance des champs… ».", self.language))

    def _sqlite_preview_data(self, limit: int = 10) -> dict:
        if self.selected_sqlite_table is None:
            return {"columns": [], "rows": []}
        fields = [str(f.get("name") or "") for f in self.selected_sqlite_table.get("fields", []) or []]
        rows = []
        for source_row in list(self.selected_sqlite_table.get("rows_data", []) or [])[:max(1, int(limit))]:
            vals = []
            for field in fields:
                value = source_row.get(field, "")
                vals.append("<BLOB>" if isinstance(value, (bytes, bytearray)) else str(value or ""))
            rows.append(vals)
        return {"columns": fields, "rows": rows}

    def _open_sqlite_preview(self) -> None:
        if self.selected_sqlite_table is None:
            return
        preview = self._sqlite_preview_data(10)
        try:
            if self._sqlite_preview_window is not None and self._sqlite_preview_window.isVisible(): self._sqlite_preview_window.close()
        except RuntimeError:
            self._sqlite_preview_window = None
        window = AccessDataPreviewDialog(str(self.selected_sqlite_table.get("name") or "SQLite"), preview, None)
        window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        window.destroyed.connect(lambda *_: setattr(self, "_sqlite_preview_window", None))
        self._sqlite_preview_window = window; window.show(); window.raise_(); window.activateWindow()

    def _sqlite_mapping_table(self) -> dict:
        """Construit la vue de correspondance SQLite avec les champs Reliés.

        La table principale reste la source des fiches, mais les colonnes des
        référentiels multi-colonnes reconnues sont également proposées dans la
        correspondance. L'utilisateur peut ainsi décider AVANT l'import si un
        champ Relié doit rester Texte/Nombre/etc. ou devenir une Liste.
        """
        if self.selected_sqlite_table is None:
            return {}
        table = dict(self.selected_sqlite_table)
        fields = [dict(f) for f in list(table.get("fields", []) or [])]

        def norm(value: str) -> str:
            text = unicodedata.normalize("NFKD", str(value or ""))
            return "".join(ch.casefold() for ch in text if ch.isalnum() and not unicodedata.combining(ch))

        seen = {norm(f.get("name")) for f in fields if norm(f.get("name"))}
        next_order = max([int(f.get("source_order") or 0) for f in fields] + [-1]) + 1
        for spec in list(table.get("sqlite_reference_specs", []) or []):
            ref_table = str(spec.get("table_name") or "")
            master = str(spec.get("master_source") or "")
            ref_rows = list(spec.get("rows_data", []) or [])
            for linked in list(spec.get("linked_fields", []) or []):
                name = str(linked.get("name") or "").strip()
                marker = norm(name)
                if not name or not marker or marker in seen:
                    continue
                meta = dict(linked)
                meta["name"] = name
                meta["source_field"] = name
                meta["source_table"] = ref_table
                meta["display_name"] = f"{name}  [{ref_table}]" if ref_table else name
                meta["source_order"] = next_order
                meta["sqlite_reference_table"] = ref_table
                meta["sqlite_linked_only"] = True
                values = []
                value_seen = set()
                for row in ref_rows:
                    value = str(row.get(name, "") or "").strip()
                    key = value.casefold()
                    if value and key not in value_seen:
                        value_seen.add(key); values.append(value)
                meta["sqlite_reference_values"] = values
                meta["excel_detection"] = (
                    f"SQLite : champ Relié issu du référentiel « {ref_table} »"
                    + (f" — Maître : {master}" if master else "")
                )
                fields.append(meta)
                seen.add(marker)
                next_order += 1
        table["fields"] = fields
        return table

    def _open_sqlite_field_mapping(self) -> None:
        if self.selected_sqlite_table is None:
            return
        try:
            if self._sqlite_mapping_window is not None and self._sqlite_mapping_window.isVisible():
                self._sqlite_mapping_window.raise_(); self._sqlite_mapping_window.activateWindow(); return
        except RuntimeError:
            self._sqlite_mapping_window = None
        mapping_table = self._sqlite_mapping_table()
        dialog = AccessFieldMappingDialog(mapping_table, None, preview_loader=lambda: self._sqlite_preview_data(10), language=self.language, model_key=self._selected_import_template())
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        dialog.finished.connect(lambda result, d=dialog: self._sqlite_field_mapping_finished(d, result))
        dialog.destroyed.connect(lambda *_: setattr(self, "_sqlite_mapping_window", None))
        self._sqlite_mapping_window = dialog; dialog.show(); dialog.raise_(); dialog.activateWindow()

    def _sqlite_field_mapping_finished(self, dialog: AccessFieldMappingDialog, result: int) -> None:
        if result != int(QDialog.DialogCode.Accepted) or not dialog.mapping:
            return
        self.sqlite_field_mapping = list(dialog.mapping)
        imported = sum(1 for item in self.sqlite_field_mapping if item.get("action") == "Importer")
        ignored = len(self.sqlite_field_mapping) - imported
        self.sqlite_next_step_label.setText(tr("✓ Correspondance validée : {imported} champ(s) seront importés, {ignored} ignoré(s). Prêt pour l’import.", self.language).format(imported=imported, ignored=ignored))
        self.sqlite_real_import_btn.setEnabled(imported > 0)
        if imported > 0:
            self._set_sqlite_step_highlight(self.sqlite_real_import_btn)

    def _start_sqlite_import(self) -> None:
        if self.sqlite_source is None or self.selected_sqlite_table is None or not self.sqlite_field_mapping:
            return
        imported_mapping = [m for m in self.sqlite_field_mapping if m.get("action") == "Importer"]
        if not imported_mapping:
            return
        rows = int(self.selected_sqlite_table.get("rows") or 0); source_kind = "SQLite"
        dialog = AccessImportDestinationDialog(str(self.selected_sqlite_table.get("name") or self.sqlite_source.stem), rows, len(imported_mapping), self, source_kind=source_kind, language=self.language)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        name = dialog.collection_name(); folder = self._workspace_collections_folder(); destination = folder / (self._safe_filename(name) + ".coldb")
        if destination.exists():
            QMessageBox.warning(self, tr("Nom déjà utilisé", self.language), tr("Le fichier « {name} » existe déjà.", self.language).format(name=destination.name)); return
        box = QMessageBox(self); box.setIcon(QMessageBox.Icon.Question); box.setWindowTitle(tr("Lancer l’import SQLite ?", self.language))
        box.setText(tr("Créer la collection « {name} » et importer {rows} fiche(s) depuis la table « {table} » ?\n\nLa base SQLite source restera strictement en lecture seule.", self.language).format(name=name, rows=rows, table=self.selected_sqlite_table.get('name')))
        yes_button = box.addButton(tr("Oui", self.language), QMessageBox.ButtonRole.YesRole); no_button = box.addButton(tr("Non", self.language), QMessageBox.ButtonRole.NoRole)
        box.setDefaultButton(no_button); box.exec()
        if box.clickedButton() is not yes_button:
            return
        progress = QProgressDialog(tr("Import de « {source} » en cours…\nCréation de la collection et copie des lignes.", self.language).format(source=self.sqlite_source.name), "", 0, 0, self)
        progress.setWindowTitle(tr("Import SQLite en cours", self.language)); progress.setCancelButton(None); progress.setWindowModality(Qt.WindowModality.ApplicationModal)
        progress.setMinimumDuration(0); progress.setAutoClose(False); progress.setAutoReset(False); progress.show()
        self.sqlite_real_import_btn.setEnabled(False); QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor); QApplication.processEvents()
        try:
            result = self._perform_excel_import(destination, name, list(self.sqlite_field_mapping), selected_sheet=self.selected_sqlite_table, source_path=self.sqlite_source, source_kind=source_kind)
        except Exception as exc:
            try:
                if destination.exists(): destination.unlink()
            except Exception:
                pass
            progress.close(); QMessageBox.critical(self, tr("Import SQLite interrompu", self.language), tr("L’import n’a pas été conservé.", self.language) + "\n\n" + str(exc)); self.sqlite_real_import_btn.setEnabled(True); return
        finally:
            QApplication.restoreOverrideCursor()
        progress.close(); self.sqlite_real_import_btn.setEnabled(True)
        self.sqlite_next_step_label.setText(tr("✓ Import terminé : {records} fiche(s) créées dans « {name} ».", self.language).format(records=result['records'], name=name))
        QMessageBox.information(
            self, tr("Import SQLite terminé", self.language),
            tr("Import terminé avec succès.\n\nCollection : {name}\nFiches créées : {records}\nChamps importés : {fields}\nValeurs de référentiels : {values}\nChamps Maîtres détectés : {masters}\nChamps Reliés détectés : {links}", self.language).format(name=name, records=result['records'], fields=result['fields'], values=result.get('referential_values', 0), masters=result.get('sqlite_masters', 0), links=result.get('sqlite_links', 0))
        )

    def _choose_excel_file(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            tr("Choisir un classeur Microsoft Excel", self.language),
            "",
            tr(tr("Classeurs Excel (*.xlsx);;Tous les fichiers (*.*)", self.language), self.language),
        )
        if not filename:
            return
        source = Path(filename)
        if source.suffix.lower() != ".xlsx":
            QMessageBox.warning(self, tr("Import Excel", self.language), tr("Le fichier choisi n’est pas un classeur .xlsx.", self.language))
            return

        self.excel_source = source
        self.excel_structure = None
        self.selected_excel_sheet = None
        self.excel_field_mapping = None
        self.excel_structure_tree.clear()
        self.choose_sheet_btn.setEnabled(False)
        self.excel_preview_btn.setEnabled(False)
        self.excel_mapping_btn.setEnabled(False)
        self.excel_real_import_btn.setEnabled(False)
        self.analyse_excel_btn.setEnabled(True)
        self._set_excel_step_highlight(self.analyse_excel_btn)
        self.excel_analysis_summary.setText(
            tr("Classeur sélectionné. Cliquez sur « Analyser le classeur » pour afficher ses feuilles.", self.language)
        )
        try:
            size_mb = source.stat().st_size / (1024 * 1024)
            size_text = f" — {size_mb:.1f} Mo"
        except OSError:
            size_text = ""
        self.excel_source_label.setText(
            tr("Fichier Excel sélectionné : {source}{size}\n", self.language).format(source=source, size=size_text)
            + tr("Aucune donnée n’est importée ou modifiée pendant l’analyse.", self.language)
        )

    def _analyse_excel_file(self) -> None:
        if self.excel_source is None:
            return
        if not self.excel_source.exists():
            QMessageBox.warning(self, tr("Import Excel", self.language), tr("Le fichier Excel sélectionné est introuvable.", self.language))
            return
        self.analyse_excel_btn.setEnabled(False)
        self.choose_excel_btn.setEnabled(False)
        self.excel_analysis_summary.setText(tr("Analyse du classeur Excel en cours…", self.language))
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        QApplication.processEvents()
        try:
            result = self._read_xlsx_workbook(self.excel_source)
        except Exception as exc:
            self.excel_structure_tree.clear()
            self.excel_analysis_summary.setText(tr("L’analyse n’a pas pu être effectuée.", self.language))
            QMessageBox.warning(self, tr("Analyse Excel impossible", self.language), str(exc))
            return
        finally:
            QApplication.restoreOverrideCursor()
            self.analyse_excel_btn.setEnabled(True)
            self.choose_excel_btn.setEnabled(True)

        self.excel_structure = result
        self.selected_excel_sheet = None
        self.excel_field_mapping = None
        self._show_excel_structure(result)

    def _show_excel_structure(self, result: dict) -> None:
        self.excel_structure_tree.clear()
        sheets = list(result.get("sheets", []) or [])
        total_rows = 0
        total_fields = 0
        for sheet in sheets:
            fields = list(sheet.get("fields", []) or [])
            rows = int(sheet.get("rows") or 0)
            total_rows += rows
            total_fields += len(fields)
            item = QTreeWidgetItem([
                str(sheet.get("name") or ""),
                tr("{count} colonne(s)", self.language).format(count=len(fields)),
                str(rows),
            ])
            font = item.font(0)
            font.setBold(True)
            item.setFont(0, font)
            item.setData(0, Qt.ItemDataRole.UserRole, str(sheet.get("name") or ""))
            self.excel_structure_tree.addTopLevelItem(item)
            for field in fields:
                child = QTreeWidgetItem([
                    str(field.get("name") or ""),
                    tr(str(field.get("type") or "Texte"), self.language),
                    "",
                ])
                item.addChild(child)
            item.setExpanded(len(sheets) == 1)

        self.excel_analysis_summary.setText(
            tr("Analyse terminée : {sheets} feuille(s), {fields} colonne(s), {rows} ligne(s) de données au total.", self.language).format(sheets=len(sheets), fields=total_fields, rows=total_rows)
        )
        self.excel_choice_label.setText(
            tr("Sélectionnez une feuille dans la liste ci-dessus. Les lignes de colonnes ne sont pas sélectionnables comme source.", self.language)
        )
        if len(sheets) == 1:
            self.excel_structure_tree.setCurrentItem(self.excel_structure_tree.topLevelItem(0))

    def _selected_excel_sheet_item(self):
        items = self.excel_structure_tree.selectedItems()
        if len(items) != 1:
            return None
        item = items[0]
        return item if item.parent() is None else None

    def _on_excel_structure_selection_changed(self) -> None:
        enabled = self._selected_excel_sheet_item() is not None
        self.choose_sheet_btn.setEnabled(enabled)
        if enabled and self.selected_excel_sheet is None:
            self._set_excel_step_highlight(self.choose_sheet_btn)

    def _on_excel_structure_double_clicked(self, item, _column: int) -> None:
        if item is not None and item.parent() is None:
            self._choose_selected_excel_sheet()

    def _choose_selected_excel_sheet(self) -> None:
        item = self._selected_excel_sheet_item()
        if item is None or not self.excel_structure:
            return
        name = item.text(0)
        sheet = next(
            (entry for entry in self.excel_structure.get("sheets", []) or []
             if str(entry.get("name") or "") == name),
            None,
        )
        if sheet is None:
            return
        self.selected_excel_sheet = sheet
        self.excel_field_mapping = None
        rows = int(sheet.get("rows") or 0)
        fields = list(sheet.get("fields", []) or [])
        header_row = sheet.get("header_row")
        self.excel_choice_label.setText(
            tr("✓ Feuille source retenue : {name} — {rows} ligne(s), {fields} colonne(s){header}", self.language).format(
                name=name, rows=rows, fields=len(fields),
                header=(tr(" — en-têtes ligne {row}.", self.language).format(row=header_row) if header_row else "."),
            )
        )
        self.excel_preview_btn.setEnabled(True)
        self.excel_mapping_btn.setEnabled(True)
        self.excel_real_import_btn.setEnabled(False)
        self._set_excel_step_highlight(self.excel_mapping_btn)
        self.excel_next_step_label.setText(
            tr("Feuille source validée. L’ordre des lignes sera conservé pour créer les fiches. Cliquez sur « Correspondance des champs… ».", self.language)
        )

    def _excel_preview_data(self, limit: int = 10) -> dict:
        if self.selected_excel_sheet is None:
            return {"columns": [], "rows": []}
        fields = [str(f.get("name") or "") for f in self.selected_excel_sheet.get("fields", []) or []]
        rows = []
        for source_row in list(self.selected_excel_sheet.get("rows_data", []) or [])[:max(1, int(limit))]:
            rows.append([str(source_row.get(field, "") or "") for field in fields])
        return {"columns": fields, "rows": rows}

    def _open_excel_preview(self) -> None:
        if self.selected_excel_sheet is None:
            return
        preview = self._excel_preview_data(10)
        try:
            if self._excel_preview_window is not None and self._excel_preview_window.isVisible():
                self._excel_preview_window.close()
        except RuntimeError:
            self._excel_preview_window = None
        window = AccessDataPreviewDialog(str(self.selected_excel_sheet.get("name") or "Excel"), preview, None, language=self.language)
        window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        window.destroyed.connect(lambda *_: setattr(self, "_excel_preview_window", None))
        self._excel_preview_window = window
        window.show(); window.raise_(); window.activateWindow()

    def _open_excel_field_mapping(self) -> None:
        if self.selected_excel_sheet is None:
            return
        try:
            if self._excel_mapping_window is not None and self._excel_mapping_window.isVisible():
                self._excel_mapping_window.raise_(); self._excel_mapping_window.activateWindow(); return
        except RuntimeError:
            self._excel_mapping_window = None

        dialog = AccessFieldMappingDialog(
            self.selected_excel_sheet,
            None,
            preview_loader=lambda: self._excel_preview_data(10),
            language=self.language,
            model_key=self._selected_import_template(),
        )
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        dialog.finished.connect(lambda result, d=dialog: self._excel_field_mapping_finished(d, result))
        dialog.destroyed.connect(lambda *_: setattr(self, "_excel_mapping_window", None))
        self._excel_mapping_window = dialog
        dialog.show(); dialog.raise_(); dialog.activateWindow()

    def _excel_field_mapping_finished(self, dialog: AccessFieldMappingDialog, result: int) -> None:
        if result != int(QDialog.DialogCode.Accepted) or not dialog.mapping:
            return
        self.excel_field_mapping = list(dialog.mapping)
        imported = sum(1 for item in self.excel_field_mapping if item.get("action") == "Importer")
        ignored = len(self.excel_field_mapping) - imported
        self.excel_next_step_label.setText(
            tr("✓ Correspondance validée : {imported} champ(s) seront importés, {ignored} ignoré(s). Prêt pour la création d'une nouvelle collection puis import des fiches.", self.language).format(imported=imported, ignored=ignored)
        )
        self.excel_real_import_btn.setEnabled(imported > 0)
        if imported > 0:
            self._set_excel_step_highlight(self.excel_real_import_btn)

    def _start_excel_import(self) -> None:
        if self.excel_source is None or self.selected_excel_sheet is None or not self.excel_field_mapping:
            return
        imported_mapping = [m for m in self.excel_field_mapping if m.get("action") == "Importer"]
        if not imported_mapping:
            return
        rows = int(self.selected_excel_sheet.get("rows") or 0)
        dialog = AccessImportDestinationDialog(
            str(self.selected_excel_sheet.get("name") or self.excel_source.stem),
            rows,
            len(imported_mapping),
            self,
            source_kind="Excel",
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        name = dialog.collection_name()
        folder = self._workspace_collections_folder()
        destination = folder / (self._safe_filename(name) + ".coldb")
        if destination.exists():
            QMessageBox.warning(self, tr("Nom déjà utilisé", self.language), tr("Le fichier « {name} » existe déjà.", self.language).format(name=destination.name))
            return

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle(tr("Lancer l’import Excel ?", self.language))
        box.setText(
            tr("Créer la collection « {name} » et importer {rows} fiche(s) depuis Excel ?\n\nL’ordre des lignes Excel sera conservé. Le classeur source ne sera jamais modifié.", self.language).format(name=name, rows=rows)
        )
        yes_button = box.addButton(tr("Oui", self.language), QMessageBox.ButtonRole.YesRole)
        no_button = box.addButton(tr("Non", self.language), QMessageBox.ButtonRole.NoRole)
        box.setDefaultButton(no_button)
        box.exec()
        if box.clickedButton() is not yes_button:
            return

        progress = QProgressDialog(
            tr("Import du classeur « {source} » en cours…\nCréation de la collection et copie des lignes. Merci de patienter.", self.language).format(source=self.excel_source.name),
            "", 0, 0, self,
        )
        progress.setWindowTitle(tr("Import Excel en cours", self.language))
        progress.setCancelButton(None)
        progress.setWindowModality(Qt.WindowModality.ApplicationModal)
        progress.setMinimumDuration(0)
        progress.setAutoClose(False); progress.setAutoReset(False)
        progress.show()
        self.excel_real_import_btn.setEnabled(False)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        QApplication.processEvents()
        try:
            result = self._perform_excel_import(destination, name, imported_mapping)
        except Exception as exc:
            try:
                if destination.exists(): destination.unlink()
            except Exception:
                pass
            progress.close()
            QMessageBox.critical(self, tr("Import Excel interrompu", self.language), tr("L’import n’a pas été conservé.\n\n", self.language) + str(exc))
            self.excel_real_import_btn.setEnabled(True)
            return
        finally:
            QApplication.restoreOverrideCursor()

        progress.close()
        self.excel_real_import_btn.setEnabled(True)
        self.excel_next_step_label.setText(
            tr("✓ Import terminé : {records} fiche(s) créées dans « {name} » — ordre des lignes Excel conservé.", self.language).format(records=result['records'], name=name)
        )
        QMessageBox.information(
            self,
            tr("Import Excel terminé", self.language),
            tr("Import terminé avec succès.\n\nCollection : {name}\nFiches créées : {records}\nChamps importés : {fields}\nValeurs de référentiels : {values}\nChamps Maîtres détectés : {masters}\nChamps Reliés détectés : {links}\n\nOrdre des fiches : ordre des lignes Excel conservé.", self.language).format(
                name=name, records=result['records'], fields=result['fields'], values=result.get('referential_values', 0), masters=result.get('inferred_masters', 0), links=result.get('inferred_links', 0)
            ),
        )

    @staticmethod
    def _infer_excel_field_relations(
        entries: list[dict], rows_data: list[dict]
    ) -> list[dict]:
        """Déduit prudemment des relations Maître / Relié à depuis les lignes Excel.

        Les dépendances réellement variables restent le signal principal. Une fois
        un bloc relationnel solide reconnu, MM3 peut aussi rattacher des champs
        Liste constants situés *dans le même bloc de colonnes* (par exemple Région
        et Pays dans une collection limitée à une seule région/pays). Cela permet
        de les vider correctement pour une nouvelle valeur Maître sans transformer
        arbitrairement tous les champs constants de la feuille en champs Reliés.
        """
        if not entries or not rows_data:
            return []

        usable_entries = [
            e for e in entries
            if str(e.get("field_type") or "") != "calculated"
            and str(e.get("source") or "").strip()
        ]
        list_entries = [
            e for e in usable_entries
            if str(e.get("field_type") or "") == "list"
        ]
        if not list_entries:
            return []

        def source_order(entry: dict) -> int | None:
            try:
                return int(entry.get("source_order"))
            except (TypeError, ValueError):
                return None

        total_rows = max(1, len(rows_data))
        proposals: list[dict] = []

        for master in list_entries:
            master_source = str(master.get("source") or "")
            master_key = str(master.get("field_key") or "")
            if not master_source or not master_key:
                continue

            master_counts: dict[str, int] = {}
            master_display: dict[str, str] = {}
            for row in rows_data:
                value = str(row.get(master_source, "") or "").strip()
                if not value:
                    continue
                marker_value = value.casefold()
                master_counts[marker_value] = master_counts.get(marker_value, 0) + 1
                master_display.setdefault(marker_value, value)

            if len(master_counts) < 2:
                continue
            repeated_master_values = sum(1 for count in master_counts.values() if count >= 2)
            if repeated_master_values < 2:
                continue

            candidates: list[dict] = []
            for linked in usable_entries:
                linked_source = str(linked.get("source") or "")
                linked_key = str(linked.get("field_key") or "")
                if not linked_source or not linked_key or linked_key == master_key:
                    continue

                values_by_master: dict[str, set[str]] = {}
                display_by_value: dict[str, str] = {}
                paired_rows = 0
                linked_distinct: set[str] = set()

                for row in rows_data:
                    master_value = str(row.get(master_source, "") or "").strip()
                    linked_value = str(row.get(linked_source, "") or "").strip()
                    if not master_value or not linked_value:
                        continue
                    paired_rows += 1
                    master_marker = master_value.casefold()
                    linked_marker = linked_value.casefold()
                    values_by_master.setdefault(master_marker, set()).add(linked_marker)
                    display_by_value.setdefault(linked_marker, linked_value)
                    linked_distinct.add(linked_marker)

                if paired_rows < max(10, int(total_rows * 0.20)):
                    continue
                if len(values_by_master) < 2:
                    continue
                if any(len(values) > 1 for values in values_by_master.values()):
                    continue

                value_map = {
                    master_marker: display_by_value[next(iter(values))]
                    for master_marker, values in values_by_master.items()
                    if values
                }
                candidates.append({
                    "entry": linked,
                    "paired_rows": paired_rows,
                    "master_coverage": len(values_by_master),
                    "value_map": value_map,
                    "distinct_count": len(linked_distinct),
                    "is_constant": len(linked_distinct) == 1,
                    "source_order": source_order(linked),
                })

            # Un vrai Maître doit d'abord expliquer au moins deux champs variables.
            strong = [dep for dep in candidates if not dep["is_constant"]]
            if len(strong) < 2:
                continue

            # Les constantes ne sont acceptées qu'en tant que listes et seulement
            # lorsqu'elles sont physiquement incluses dans le bloc des dépendances
            # fortes. Exemple réel : Gisement / Département / Région / Pays /
            # Catégorie / Lien MINDAT. Cela exclut les constantes éloignées telles
            # que l'état de fiche ou un code général de collection.
            strong_orders = [dep["source_order"] for dep in strong if dep["source_order"] is not None]
            dependents = list(strong)
            if len(strong_orders) >= 2:
                low, high = min(strong_orders), max(strong_orders)
                for dep in candidates:
                    if not dep["is_constant"]:
                        continue
                    entry = dep["entry"]
                    order = dep["source_order"]
                    if (
                        str(entry.get("field_type") or "") == "list"
                        and order is not None
                        and low <= order <= high
                    ):
                        dependents.append(dep)

            proposals.append({
                "master": master,
                "master_counts": master_counts,
                "master_display": master_display,
                "dependents": dependents,
                "score": (
                    len(strong),
                    len(master_counts),
                    repeated_master_values,
                ),
            })

        if not proposals:
            return []

        # Un champ MM3 ne peut être relié qu'à un seul Maître. En cas de
        # concurrence, privilégier le Maître qui explique le bloc le plus riche.
        proposals.sort(key=lambda p: p["score"], reverse=True)
        assigned_linked: set[str] = set()
        accepted: list[dict] = []

        master_keys = {
            str(p["master"].get("field_key") or "") for p in proposals
        }
        for proposal in proposals:
            kept = []
            for dep in proposal["dependents"]:
                linked_key = str(dep["entry"].get("field_key") or "")
                if (
                    not linked_key
                    or linked_key in assigned_linked
                    or linked_key in master_keys
                ):
                    continue
                kept.append(dep)
                assigned_linked.add(linked_key)

            # Après résolution des conflits, conserver uniquement les vrais blocs.
            if len([dep for dep in kept if not dep.get("is_constant")]) < 2:
                for dep in kept:
                    assigned_linked.discard(str(dep["entry"].get("field_key") or ""))
                continue

            proposal = dict(proposal)
            proposal["dependents"] = kept
            accepted.append(proposal)

        return accepted

    @classmethod
    def _format_delimited_import_value(cls, raw, field_type: str, target_label: str) -> str:
        """Normalise seulement les types reconnus d'un fichier CSV/TXT/TSV."""
        value = "" if raw is None else str(raw).strip()
        if not value:
            return ""
        kind = str(field_type or "")
        if kind in {"numeric", "currency"}:
            cleaned = cls._text_clean_number(value)
            if cleaned is not None:
                try:
                    number = float(cleaned)
                    return f"{number:.2f}" if kind == "currency" else format(number, ".15g")
                except ValueError:
                    pass
        if kind == "boolean":
            low = value.casefold()
            if low in {"oui", "yes", "true", "vrai", "1", "on"}:
                return "1"
            if low in {"non", "no", "false", "faux", "0", "off"}:
                return "0"
        if kind == "date":
            for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y", "%Y/%m/%d", "%d %m %Y"):
                try:
                    return datetime.strptime(value, fmt).strftime("%d/%m/%Y")
                except ValueError:
                    pass
        return cls._format_imported_value(value, target_label)

    def _selected_import_template(self) -> str:
        """Modèle sélectionné dans l'étape 2.3.2 ; blanc par défaut."""
        key = str(getattr(self, "import_model_key", None) or "blank")
        from core.collection_templates import OFFICIAL_TEMPLATE_FILES
        return key if key in OFFICIAL_TEMPLATE_FILES else "blank"

    @staticmethod
    def _template_destination_fields(model_manager, cid: int) -> dict[str, dict]:
        """Associe les libellés *actuels* aux identifiants internes du modèle."""
        labels = model_manager.custom_labels(cid)
        custom = model_manager.custom_field_map(cid)
        visible = model_manager.visible_fields(cid)
        result = {"état de la fiche": {"field_key": "record_state", "field_type": "text", "referential_code": ""}}
        for key in model_manager.all_model_keys(cid):
            if key == "record_number" or key not in visible:
                continue
            meta = custom.get(key, {})
            label = str(labels.get(key) or meta.get("label") or
                        (FIELD_BY_KEY[key].label if key in FIELD_BY_KEY else key)).strip()
            if label:
                result[label.casefold()] = {"field_key": key,
                    "field_type": str(meta.get("field_type") or "text"),
                    "referential_code": str(meta.get("referential_code") or "")}
        return result

    def _perform_excel_import(
        self, destination: Path, name: str, mapping: list[dict],
        selected_sheet: dict | None = None, source_path: Path | None = None,
        source_kind: str = "Excel",
    ) -> dict:
        source_sheet = selected_sheet if selected_sheet is not None else self.selected_excel_sheet
        source_file = source_path if source_path is not None else self.excel_source
        if source_sheet is None:
            raise RuntimeError(f"Aucune source {source_kind} n'est sélectionnée.")
        manager = CollectionManager(destination)
        cid = manager.create_collection({
            "name": name,
            "owner": "",
            "description": f"Import {source_kind} : {source_file.name if source_file else ''}",
        })
        db = DatabaseManager(destination); db.initialize(); db.disconnect()
        record_manager = RecordManager(destination)
        with record_manager._connect() as connection:
            record_manager._ensure_table(connection)
            # Les imports DBF/ODS/Excel peuvent employer des champs de modèle
            # personnalisés : leur table doit exister avant toute synchronisation.
            record_manager._ensure_custom_values_table(connection)
        model_manager = ModelManager(destination)
        template_key = self._selected_import_template()
        apply_official_template_database(model_manager, int(cid), template_key)
        template_fields = (self._template_destination_fields(model_manager, int(cid))
                           if template_key != "blank" else {})

        def source_key(item: dict):
            try:
                return int(item.get("source_order"))
            except (TypeError, ValueError):
                return 1_000_000

        entries: list[dict] = []
        ordered_keys: list[str] = []
        source_to_key: dict[str, str] = {}

        # Première passe : créer tous les champs dans l'ordre Excel. Les champs
        # calculés sont eux aussi créés immédiatement, avec formule provisoirement
        # vide, afin que toutes les clés MM3 existent avant de traduire les
        # références entre colonnes.
        for item in sorted(list(mapping), key=source_key):
            if item.get("action") != "Importer":
                continue
            source = str(item.get("source") or "")
            target = str(item.get("target") or source).strip()
            mm3_type = str(item.get("mm3_type") or "Texte")
            field_type = self._mm3_field_type(mm3_type)

            # Les images intégrées Excel ne sont pas traitées ici : une colonne
            # déclarée Photo manuellement reste du texte.
            calculation_format = str(item.get("calculation_format") or "truncate2")
            target_key = str(item.get("target_field_key") or "")
            created = (next((meta for meta in template_fields.values() if meta.get("field_key") == target_key), None)
                       if target_key else template_fields.get(target.casefold()))
            if created is None:
                created = model_manager.create_custom_field(
                    int(cid), target, field_type, initial_group="Identification",
                    calculation_formula="", calculation_format=calculation_format,
                )
                # A field absent from the chosen model belongs in the Atelier
                # palette, never on top of the actual record form.
                if template_key != "blank":
                    with sqlite3.connect(destination) as con:
                        con.execute("UPDATE collection_model_fields SET visible=0 WHERE collection_id=? AND field_key=?", (int(cid), str(created["field_key"])))
            entry = dict(item)
            entry["field_key"] = str(created["field_key"])
            entry["field_type"] = field_type
            entry["referential_code"] = str(created.get("referential_code") or "")
            entries.append(entry)
            ordered_keys.append(entry["field_key"])
            source_to_key[source.casefold()] = entry["field_key"]

        # Deuxième passe : convertir les références [Colonne Excel] des formules
        # reconnues en références {clé_interne_MM3}. Le calcul devient ainsi
        # réellement dynamique dans la Fiche MM3.
        calculated_count = 0
        for entry in entries:
            if str(entry.get("field_type") or "") != "calculated":
                continue
            expression = str(entry.get("calculation_expression") or "").strip()
            if not expression:
                continue

            unresolved = False

            def replace_formula_field(match):
                nonlocal unresolved
                source_name = str(match.group(1) or "").strip()
                key = source_to_key.get(source_name.casefold())
                if not key:
                    unresolved = True
                    return match.group(0)
                return "{" + key + "}"

            mm3_formula = re.sub(r"\[([^\]]+)\]", replace_formula_field, expression)
            if unresolved or "[" in mm3_formula or "]" in mm3_formula:
                continue
            model_manager.update_custom_field_calculation(
                int(cid), str(entry["field_key"]), mm3_formula
            )
            entry["mm3_formula"] = mm3_formula
            calculated_count += 1

        # SQLite peut stocker les référentiels dans des tables séparées. Les
        # colonnes Reliées qui n'existent pas dans la table des fiches sont
        # ajoutées automatiquement au modèle afin que le bloc Maître / Relié à
        # soit immédiatement exploitable après l'import.
        sqlite_reference_specs = []
        if str(source_kind).casefold() == "sqlite":
            sqlite_reference_specs = list(source_sheet.get("sqlite_reference_specs", []) or [])
            def _sqlite_field_id(value: str) -> str:
                text = unicodedata.normalize("NFKD", str(value or ""))
                return "".join(ch.casefold() for ch in text if ch.isalnum() and not unicodedata.combining(ch))

            # Un champ Relié peut avoir été renommé par l'utilisateur dans la
            # correspondance. On suit donc à la fois son nom source et son nom
            # MM3 afin de ne jamais recréer un doublon automatiquement.
            existing_ids = set()
            for e in entries:
                for value in (e.get("source"), e.get("target")):
                    marker = _sqlite_field_id(value)
                    if marker:
                        existing_ids.add(marker)
            mapping_by_source = {
                _sqlite_field_id(m.get("source")): m
                for m in list(mapping)
                if _sqlite_field_id(m.get("source"))
            }
            next_order = max([source_key(e) for e in entries] + [-1]) + 1
            for spec in sqlite_reference_specs:
                for linked_field in list(spec.get("linked_fields", []) or []):
                    linked_name = str(linked_field.get("name") or "").strip()
                    if not linked_name:
                        continue
                    lid = _sqlite_field_id(linked_name)
                    if lid in existing_ids:
                        continue
                    explicit = mapping_by_source.get(lid)
                    if explicit is not None and explicit.get("action") != "Importer":
                        # Le champ était visible dans la correspondance et a été
                        # explicitement ignoré : respecter ce choix.
                        continue
                    source_type = str(linked_field.get("type") or "Texte")
                    mm3_type = AccessFieldMappingDialog._physical_mm3_type(source_type, linked_name, linked_field)
                    field_type = self._mm3_field_type(mm3_type)
                    created = model_manager.create_custom_field(
                        int(cid), linked_name, field_type, initial_group="Identification"
                    )
                    entry = {
                        "source": linked_name,
                        "target": linked_name,
                        "mm3_type": mm3_type,
                        "field_type": field_type,
                        "field_key": str(created["field_key"]),
                        "referential_code": str(created.get("referential_code") or ""),
                        "source_order": next_order,
                        "sqlite_linked_only": True,
                    }
                    next_order += 1
                    entries.append(entry)
                    ordered_keys.append(entry["field_key"])
                    existing_ids.add(lid)
                    existing_ids.add(_sqlite_field_id(entry.get("target")))

        positions: dict[str, tuple[int, int]] = {}
        sizes: dict[str, tuple[int, int]] = {}
        start_y, row_step = 190, 40
        left_x, right_x = 24, 500
        for index, key in enumerate(ordered_keys):
            positions[key] = (
                left_x if index % 2 == 0 else right_x,
                start_y + (index // 2) * row_step,
            )
            sizes[key] = (440, 31)
        if template_key == "blank":
            model_manager.set_visual_positions(int(cid), positions)
            model_manager.set_visual_sizes(int(cid), sizes)
            model_manager.set_tab_order(int(cid), ["record_number", *ordered_keys])
        else:
            # Préserver intégralement la géométrie du modèle choisi.
            # Les éventuels champs ajoutés conservent leur placement par défaut.
            pass

        # Styles fonctionnels : texte des données en noir ; devise issue du
        # format Excel ; suffixe d'un résultat calculé (ex. €) conservé.
        styles = model_manager.field_styles(int(cid))
        for entry in entries:
            key = str(entry["field_key"])
            whole = styles.setdefault(key, {})
            if template_key == "blank" or entry.get("create_in_palette"):
                whole.setdefault("data", {})["color"] = "#000000"
            if str(entry.get("field_type") or "") == "currency":
                whole["currency_symbol"] = str(entry.get("currency_symbol") or "€").strip() or "€"
            if str(entry.get("field_type") or "") == "calculated":
                suffix = str(entry.get("result_suffix") or "").strip()
                if suffix:
                    whole["result_suffix"] = suffix
        model_manager.set_field_styles(int(cid), styles)

        rows_data = list(source_sheet.get("rows_data", []) or [])
        count = 0
        for source_row in rows_data:
            record = record_manager.create_record(int(cid))
            values = {}
            for entry in entries:
                if str(entry.get("field_type") or "") == "calculated":
                    continue
                source = str(entry.get("source") or "")
                if str(source_kind).casefold() == "excel":
                    formatted_value = self._format_imported_value(
                        source_row.get(source, ""), str(entry.get("target") or source)
                    )
                else:
                    formatted_value = self._format_delimited_import_value(
                        source_row.get(source, ""), str(entry.get("field_type") or ""),
                        str(entry.get("target") or source),
                    )
                field_key = str(entry["field_key"])
                if field_key == "record_state":
                    state = str(formatted_value or "").strip().casefold()
                    states = {"ok": "OK", "vérifier": "Vérifier", "verifier": "Vérifier", "check": "Vérifier", "libre": "Libre", "free": "Libre"}
                    if state in states:
                        with record_manager._connect() as con:
                            con.execute("UPDATE records SET record_state=? WHERE id=?", (states[state], int(record["id"])))
                    continue
                values[field_key] = formatted_value
            native_columns = set(record_manager.FIELD_DEFAULTS)
            native_values = {k: v for k, v in values.items() if k in native_columns}
            extra_values = {k: v for k, v in values.items() if k not in native_columns}
            if native_values:
                with record_manager._connect() as con:
                    con.execute("UPDATE records SET " + ", ".join(f'"{k}"=?' for k in native_values) + " WHERE id=?", [*native_values.values(), int(record["id"])])
                    if "mineral_name" in native_values:
                        con.execute("UPDATE records SET species=? WHERE id=?", (native_values["mineral_name"], int(record["id"])))
            if extra_values:
                record_manager.set_custom_values(int(record["id"]), extra_values)
            count += 1
            if count % 50 == 0:
                QApplication.processEvents()

        # Alimenter les référentiels lorsqu'une colonne a été déclarée Liste.
        referential_values = 0
        with sqlite3.connect(destination) as connection:
            connection.execute("PRAGMA foreign_keys=ON")
            now = datetime.now().isoformat(timespec="seconds")
            for entry in entries:
                if not str(entry.get("mm3_type") or "").startswith("Liste / Référentiel"):
                    continue
                code = str(entry.get("referential_code") or entry["field_key"])
                definition = connection.execute(
                    "SELECT id FROM referential_definitions WHERE collection_id=? AND code=?",
                    (int(cid), code),
                ).fetchone()
                if definition is None:
                    continue
                definition_id = int(definition[0])
                source = str(entry.get("source") or "")
                seen = set(); values = []

                # Priorité au référentiel complet réellement désigné par la
                # validation de données Excel. Si aucune validation n'est
                # disponible (liste choisie manuellement dans la correspondance),
                # conserver le comportement historique : valeurs utilisées.
                excel_values = list(entry.get("excel_reference_values") or [])
                sqlite_values = list(entry.get("sqlite_reference_values") or [])
                complete_values = excel_values or sqlite_values
                if sqlite_values:
                    # Conserver aussi les valeurs déjà utilisées dans les fiches,
                    # même si la table annexe de référence est incomplète.
                    source_values = list(sqlite_values) + [row.get(source, "") for row in rows_data]
                else:
                    source_values = complete_values if complete_values else [
                        row.get(source, "") for row in rows_data
                    ]
                for raw_value in source_values:
                    value = str(raw_value or "").strip()
                    marker = value.casefold()
                    if value and marker not in seen:
                        seen.add(marker); values.append(value)
                if not complete_values:
                    values.sort(key=str.casefold)
                for order, value in enumerate(values, start=1):
                    connection.execute(
                        """INSERT OR IGNORE INTO referential_values(
                               definition_id, value, sort_order, is_active, created_at, updated_at
                           ) VALUES (?, ?, ?, 1, ?, ?)""",
                        (definition_id, value, order, now, now),
                    )
                referential_values += len(values)

        # SQLite — importer les tables de référentiel explicitement reconnues.
        sqlite_masters = 0
        sqlite_links = 0
        sqlite_reference_rows = 0
        if str(source_kind).casefold() == "sqlite" and sqlite_reference_specs:
            def simple_id(value: str) -> str:
                text = unicodedata.normalize("NFKD", str(value or ""))
                return "".join(ch.casefold() for ch in text if ch.isalnum() and not unicodedata.combining(ch))

            entries_by_source = {simple_id(e.get("source")): e for e in entries if simple_id(e.get("source"))}
            entries_by_target = {simple_id(e.get("target")): e for e in entries if simple_id(e.get("target"))}
            for spec in sqlite_reference_specs:
                master_source = str(spec.get("master_source") or "")
                master_reference = str(spec.get("master_reference") or "")
                master_entry = entries_by_source.get(simple_id(master_source)) or entries_by_target.get(simple_id(master_source))
                if not master_entry:
                    continue
                master_key = str(master_entry.get("field_key") or "")
                if not master_key:
                    continue
                linked_entries = []
                for linked_field in list(spec.get("linked_fields", []) or []):
                    linked_name = str(linked_field.get("name") or "")
                    linked_entry = entries_by_source.get(simple_id(linked_name)) or entries_by_target.get(simple_id(linked_name))
                    if linked_entry and str(linked_entry.get("field_key") or "") != master_key:
                        linked_entries.append((linked_name, linked_entry))
                if not linked_entries:
                    continue

                reference_rows = []
                for ref_row in list(spec.get("rows_data", []) or []):
                    master_value = str(ref_row.get(master_reference, "") or "").strip()
                    if not master_value:
                        continue
                    converted = {master_key: master_value}
                    for linked_name, linked_entry in linked_entries:
                        raw = ref_row.get(linked_name, "")
                        formatted = self._format_delimited_import_value(
                            raw,
                            str(linked_entry.get("field_type") or ""),
                            str(linked_entry.get("target") or linked_name),
                        )
                        if str(formatted or "").strip():
                            converted[str(linked_entry["field_key"])] = formatted
                    reference_rows.append(converted)
                if not reference_rows:
                    continue

                stats = model_manager.import_reference_rows(int(cid), master_key, reference_rows)
                sqlite_masters += 1
                sqlite_links += len(linked_entries)
                sqlite_reference_rows += int(stats.get("rows", 0))

                # Rattraper les fiches déjà créées : les champs Reliés ajoutés
                # depuis la table annexe sont renseignés à partir du Maître.
                linked_keys = [str(e[1]["field_key"]) for e in linked_entries]
                self._apply_imported_reference_to_records(
                    destination, master_key, linked_keys, reference_rows
                )

                code = str(master_entry.get("referential_code") or "")
                if code:
                    with sqlite3.connect(destination) as connection:
                        connection.execute(
                            "UPDATE referential_definitions SET is_master=1 WHERE collection_id=? AND code=?",
                            (int(cid), code),
                        )

        # 39.32.5 — reconstruire les blocs Maître / Relié à lorsque les données
        # Excel montrent une dépendance stricte et répétée. Cette détection est
        # volontairement indépendante des noms de colonnes.
        inferred_masters = 0
        inferred_links = 0
        inferred_reference_rows = 0
        relation_groups = (
            self._infer_excel_field_relations(entries, rows_data)
            if str(source_kind).casefold() == "excel" and template_key == "blank" else []
        )

        for group in relation_groups:
            master_entry = dict(group.get("master") or {})
            master_key = str(master_entry.get("field_key") or "")
            master_source = str(master_entry.get("source") or "")
            dependents = list(group.get("dependents") or [])
            if not master_key or not master_source or not dependents:
                continue

            # Construire une ligne de référence par valeur Maître réellement
            # observée. Les valeurs complètes de la liste Excel restent dans le
            # référentiel ; seules les associations prouvées par les données
            # deviennent des données de liaison.
            reference_by_master: dict[str, dict[str, str]] = {}
            display_by_master: dict[str, str] = {}
            for source_row in rows_data:
                master_value = str(source_row.get(master_source, "") or "").strip()
                if not master_value:
                    continue
                marker_value = master_value.casefold()
                display_by_master.setdefault(marker_value, master_value)
                converted = reference_by_master.setdefault(
                    marker_value, {master_key: master_value}
                )
                for dep in dependents:
                    linked_entry = dict(dep.get("entry") or {})
                    linked_source = str(linked_entry.get("source") or "")
                    linked_key = str(linked_entry.get("field_key") or "")
                    if not linked_source or not linked_key:
                        continue
                    linked_value = str(source_row.get(linked_source, "") or "").strip()
                    if linked_value:
                        converted[linked_key] = self._format_imported_value(
                            linked_value,
                            str(linked_entry.get("target") or linked_source),
                        )

            reference_rows = [
                reference_by_master[key]
                for key in sorted(
                    reference_by_master,
                    key=lambda marker_value: display_by_master.get(marker_value, marker_value).casefold(),
                )
            ]
            if not reference_rows:
                continue

            stats = model_manager.import_reference_rows(
                int(cid), master_key, reference_rows
            )
            inferred_masters += 1
            inferred_links += len(dependents)
            inferred_reference_rows += int(stats.get("rows", 0))

            # Le référentiel du Maître porte également son état visuel/logique
            # de Maître dans le module Référentiels.
            code = str(master_entry.get("referential_code") or "")
            if code:
                with sqlite3.connect(destination) as connection:
                    connection.execute(
                        "UPDATE referential_definitions SET is_master=1 "
                        "WHERE collection_id=? AND code=?",
                        (int(cid), code),
                    )

        # Brique 2.3.10 : les modèles prédéfinis possèdent déjà leurs liens
        # Maître/Relié et leurs tables de référence. Comme pour Access, remplir
        # les valeurs reliées dès l'import, sans ouvrir les fiches Qt.
        if template_key != "blank":
            self._synchronise_template_reference_records(destination, int(cid))

        return {
            "records": count,
            "fields": len(entries),
            "referential_values": referential_values,
            "calculated_fields": calculated_count,
            "inferred_masters": inferred_masters,
            "inferred_links": inferred_links,
            "inferred_reference_rows": inferred_reference_rows,
            "sqlite_masters": sqlite_masters,
            "sqlite_links": sqlite_links,
            "sqlite_reference_rows": sqlite_reference_rows,
        }

    def _choose_access_file(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            tr("Choisir une base Microsoft Access", self.language),
            "",
            tr("Bases Microsoft Access (*.accdb *.mdb);;Tous les fichiers (*.*)", self.language),
        )
        if not filename:
            return

        source = Path(filename)
        if source.suffix.lower() not in {".accdb", ".mdb"}:
            QMessageBox.warning(
                self,
                "Import Access",
                tr("Le fichier choisi n’est pas une base Access .accdb ou .mdb.", self.language),
            )
            return

        self.access_source = source
        self.access_structure = None
        self.selected_access_table = None
        self.access_field_mapping = None
        self.structure_tree.clear()
        self.choose_table_btn.setEnabled(False)
        self.preview_btn.setEnabled(False)
        self.mapping_btn.setEnabled(False)
        self.real_import_btn.setEnabled(False)
        self.table_choice_label.setText(tr("Sélectionnez une table dans la liste ci-dessus. Les lignes de champs ne sont pas sélectionnables comme source.", self.language))
        self.analysis_summary.setText(
            tr("Base sélectionnée. Cliquez sur « Analyser la base » pour afficher sa structure.", self.language)
        )
        self.analyse_access_btn.setEnabled(True)
        self._set_access_step_highlight(self.analyse_access_btn)

        try:
            size_mb = source.stat().st_size / (1024 * 1024)
            size_text = f" — {size_mb:.1f} Mo"
        except OSError:
            size_text = ""

        self.source_label.setText(
            (f"Selected Access database: {source}{size_text}\n" if self.language.lower().startswith("en") else (f"Ausgewählte Access-Datenbank: {source}{size_text}\n" if self.language.lower().startswith("de") else f"Base Access sélectionnée : {source}{size_text}\n"))
            + tr("Aucune donnée n’est importée ou modifiée pendant l’analyse.", self.language)
        )

    def _analyse_access_file(self) -> None:
        if self.access_source is None:
            return
        if not self.access_source.exists():
            QMessageBox.warning(self, "Import Access", tr("La base Access sélectionnée est introuvable.", self.language))
            return

        self.analyse_access_btn.setEnabled(False)
        self.choose_access_btn.setEnabled(False)
        self.analysis_summary.setText(tr("Analyse de la base Access en cours…", self.language))
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        QApplication.processEvents()
        try:
            result = self._read_access_structure(self.access_source)

            # Lecture complémentaire des formulaires/sous-formulaires.
            # Elle reste strictement indépendante : si Access refuse cette
            # lecture, l'analyse classique des tables demeure utilisable.
            try:
                form_result = self._read_access_forms_structure(self.access_source)
                result["forms"] = form_result.get("forms", [])
                result["queries"] = form_result.get("queries", [])
                if form_result.get("warning"):
                    result["forms_warning"] = str(form_result.get("warning"))
            except Exception as form_exc:
                result["forms"] = []
                result["queries"] = []
                result["forms_warning"] = str(form_exc)

        except Exception as exc:
            self.structure_tree.clear()
            self.analysis_summary.setText(tr("L’analyse n’a pas pu être effectuée.", self.language))
            QMessageBox.warning(
                self,
                tr("Analyse Access impossible", self.language),
                str(exc),
            )
            return
        finally:
            QApplication.restoreOverrideCursor()
            self.analyse_access_btn.setEnabled(True)
            self.choose_access_btn.setEnabled(True)

        self.access_structure = result
        self.selected_access_table = None
        self.access_field_mapping = None
        self.choose_table_btn.setEnabled(False)
        self.preview_btn.setEnabled(False)
        self.mapping_btn.setEnabled(False)
        self._show_structure(result)

    def _show_structure(self, result: dict) -> None:
        self.structure_tree.clear()
        tables = result.get("tables", [])
        total_fields = 0
        total_rows = 0
        counted_rows = 0
        detected_calculated = 0
        detected_referentials = 0

        for table in tables:
            fields = table.get("fields", [])
            total_fields += len(fields)
            count = table.get("rows")
            if isinstance(count, int):
                total_rows += count
                counted_rows += 1
                count_text = str(count)
            else:
                count_text = "?"

            table_item = QTreeWidgetItem(
                [str(table.get("name", "")), tr("{count} champ(s)", self.language).format(count=len(fields)), count_text]
            )
            font = table_item.font(0)
            font.setBold(True)
            table_item.setFont(0, font)
            table_item.setData(0, Qt.ItemDataRole.UserRole, str(table.get("name", "")))
            self.structure_tree.addTopLevelItem(table_item)

            for field in fields:
                type_text = str(field.get("type", ""))
                size = field.get("size")
                if size not in (None, "", 0, "0") and type_text.lower() in {
                    "varchar", "char", "longvarchar", "wchar", "varwchar", "longvarwchar"
                }:
                    type_text = f"{type_text} ({size})"
                if str(field.get("calculation_expression") or "").strip():
                    type_text += tr("  • calcul reconnu", self.language)
                    detected_calculated += 1
                elif (str(field.get("lookup_source") or "").strip()
                      or str(field.get("relation_table") or "").strip()):
                    type_text += tr("  • référentiel reconnu", self.language)
                    detected_referentials += 1
                child = QTreeWidgetItem([str(field.get("name", "")), type_text, ""])
                table_item.addChild(child)

        provider = result.get("provider", "pilote Access")
        if tables:
            rows_part = ""
            if counted_rows == len(tables):
                rows_part = f" — {total_rows} ligne(s) au total"
            detected_part = ""
            if detected_referentials or detected_calculated:
                detected_part = (
                    f" Détection approfondie : {detected_referentials} champ(s) de type "
                    f"référentiel et {detected_calculated} champ(s) calculé(s) reconnu(s)."
                )
            if self.language.lower().startswith("de"):
                rows_de = f" — insgesamt {total_rows} Zeile(n)" if counted_rows == len(tables) else ""
                detected_de = (f" Erweiterte Erkennung: {detected_referentials} Referenzfeld(er) und {detected_calculated} berechnete(s) Feld(er) erkannt." if (detected_referentials or detected_calculated) else "")
                self.analysis_summary.setText(f"Analyse abgeschlossen: {len(tables)} Tabelle(n), {total_fields} Feld(er){rows_de}. Gelesen über {provider}.{detected_de} Klicken Sie auf das Dreieck neben einer Tabelle, um ihre Felder anzuzeigen.")
            elif self.language.lower().startswith("en"):
                rows_en = f" — {total_rows} row(s) total" if counted_rows == len(tables) else ""
                detected_en = (f" Advanced detection: {detected_referentials} reference field(s) and {detected_calculated} calculated field(s) recognized." if (detected_referentials or detected_calculated) else "")
                self.analysis_summary.setText(f"Analysis complete: {len(tables)} table(s), {total_fields} field(s){rows_en}. Read via {provider}.{detected_en} Click the arrow next to a table to view its fields.")
            else:
                self.analysis_summary.setText(
                    f"Analyse terminée : {len(tables)} table(s), {total_fields} champ(s){rows_part}. "
                    f"Lecture via {provider}.{detected_part} "
                    "Cliquez sur le triangle d’une table pour voir ses champs."
                )
            if len(tables) <= 3:
                self.structure_tree.expandAll()
        else:
            self.analysis_summary.setText(tr("Analyse terminée : aucune table de données n’a été trouvée.", self.language))

    def _selected_top_level_table_item(self) -> QTreeWidgetItem | None:
        items = self.structure_tree.selectedItems()
        if not items:
            return None
        item = items[0]
        if item.parent() is not None:
            return None
        return item

    def _on_structure_selection_changed(self) -> None:
        item = self._selected_top_level_table_item()
        if item is None:
            self.choose_table_btn.setEnabled(False)
            if self.structure_tree.selectedItems():
                self.table_choice_label.setText(tr("Vous avez sélectionné un champ. Pour l’import, sélectionnez le nom de la table qui contient les fiches.", self.language))
            return

        self.choose_table_btn.setEnabled(True)
        if self.selected_access_table is None:
            self._set_access_step_highlight(self.choose_table_btn)
        name = item.text(0)
        rows = item.text(2) or "?"
        self.table_choice_label.setText(
            (f"Selected table: {name} — {rows} row(s). Click ‘Choose this table’ to use it as the source." if self.language.lower().startswith("en") else (f"Ausgewählte Tabelle: {name} — {rows} Zeile(n). Klicken Sie auf „Diese Tabelle auswählen“, um sie als Quelle zu verwenden." if self.language.lower().startswith("de") else f"Table sélectionnée : {name} — {rows} ligne(s). Cliquez sur « Choisir cette table » pour la retenir comme source."))
        )

    def _on_structure_double_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        if item.parent() is None:
            self._choose_selected_table()

    @staticmethod
    def _split_access_link_fields(value: str) -> list[str]:
        text = str(value or "").replace(",", ";")
        return [part.strip() for part in text.split(";") if part.strip()]

    @staticmethod
    def _plain_control_source(value: str) -> str:
        """Renvoie un nom de champ simple à partir d'un ControlSource Access."""
        text = str(value or "").strip()
        if not text or text.startswith("="):
            return ""
        # [Table].[Champ] ou Table.Champ -> Champ
        text = text.replace("[", "").replace("]", "")
        if "." in text:
            text = text.rsplit(".", 1)[-1]
        return text.strip()

    @staticmethod
    def _access_section_rank(control: dict) -> int:
        """Ordre de parcours des sections Access : En-tête, Détail, Pied, autres."""
        try:
            section = int(control.get("section"))
        except (TypeError, ValueError):
            section = 0
        # Access: 0=Détail, 1=En-tête formulaire, 2=Pied formulaire,
        # 3=En-tête page, 4=Pied page. Les sections de page ne participent
        # normalement pas à la saisie, mais restent après les sections de formulaire.
        return {1: 0, 0: 1, 2: 2, 3: 3, 4: 4}.get(section, 9)

    @staticmethod
    def _access_control_visible(control: dict) -> bool:
        value = control.get("visible")
        if value is None or value == "":
            return True
        if isinstance(value, bool):
            return value
        return str(value).strip().casefold() not in {"0", "false", "non", "no"}

    @staticmethod
    def _access_tab_index(control: dict, fallback: int = 1_000_000) -> int:
        try:
            value = control.get("tab_index")
            if value is None or value == "":
                return int(fallback)
            return int(value)
        except (TypeError, ValueError):
            return int(fallback)

    @staticmethod
    def _access_tab_stop(control: dict) -> bool:
        value = control.get("tab_stop")
        # Certains contrôles n'exposent pas TabStop. Dans ce cas, ne pas les
        # exclure arbitrairement : l'ordre reste exploitable si TabIndex existe.
        if value is None or value == "":
            return True
        if isinstance(value, bool):
            return value
        return str(value).strip().casefold() not in {"0", "false", "non", "no"}

    @staticmethod
    def _access_identity(value: str) -> str:
        """Normalise libellés/noms Access pour rapprocher les contrôles des champs."""
        text = unicodedata.normalize("NFKD", str(value or ""))
        text = "".join(ch for ch in text if not unicodedata.combining(ch))
        return "".join(ch.casefold() for ch in text if ch.isalnum())

    @classmethod
    def _access_control_match_score(
        cls, control: dict, field_source: str, field_label: str
    ) -> int:
        """Score générique ControlSource / Name / Caption -> champ source."""
        field_ids = {
            cls._access_identity(field_source),
            cls._access_identity(field_label),
        }
        field_ids.discard("")
        if not field_ids:
            return 0

        source = cls._access_identity(
            cls._plain_control_source(str(control.get("control_source") or ""))
        )
        name = cls._access_identity(str(control.get("name") or ""))
        label = cls._access_identity(str(control.get("label") or ""))

        score = 0
        for fid in field_ids:
            if source and source == fid:
                score = max(score, 100)
            if name and name == fid:
                score = max(score, 95)
            if label and label == fid:
                score = max(score, 90)

            for candidate, base_score in ((source, 80), (name, 75), (label, 70)):
                if not candidate or min(len(candidate), len(fid)) < 4:
                    continue
                if candidate in fid or fid in candidate:
                    score = max(score, base_score)
        return score

    def _apply_access_tab_order_to_fields(
        self,
        main_form: dict,
        base_fields: list[dict],
    ) -> None:
        """Reprend l'ordre défini par Outils de conception > Ordre de tabulation."""
        controls = [
            ctrl for ctrl in (main_form.get("controls", []) or [])
            if not str(ctrl.get("source_object") or "").strip()
        ]

        for source_order, field in enumerate(base_fields):
            source = str(field.get("source_field") or field.get("name") or "")
            field_label = str(
                field.get("target_label")
                or field.get("display_name")
                or field.get("name")
                or source
            ).strip()

            # 1) Liaison exacte ControlSource -> champ : autorité principale.
            exact = []
            for ctrl in controls:
                ctrl_source = self._plain_control_source(
                    str(ctrl.get("control_source") or "")
                )
                if ctrl_source and ctrl_source.casefold() == source.casefold():
                    exact.append(ctrl)

            candidates = exact
            if not candidates:
                # 2) Contrôles calculés / cas atypiques : Name / Caption.
                scored = []
                for ctrl in controls:
                    score = self._access_control_match_score(
                        ctrl, source, field_label
                    )
                    if score > 0:
                        scored.append((score, ctrl))
                if scored:
                    best_score = max(score for score, _ctrl in scored)
                    candidates = [
                        ctrl for score, ctrl in scored if score == best_score
                    ]

            if candidates:
                visible = [
                    c for c in candidates if self._access_control_visible(c)
                ]
                candidates = visible or candidates

                tabbed = [
                    c for c in candidates
                    if self._access_tab_index(c) < 1_000_000
                ]
                candidates = tabbed or candidates

                best = min(
                    candidates,
                    key=lambda c: (
                        self._access_section_rank(c),
                        self._access_tab_index(c),
                        int(c.get("top") or 0),
                        int(c.get("left") or 0),
                    ),
                )
                section_rank = self._access_section_rank(best)
                tab_index = self._access_tab_index(best)
                field["access_tab_index"] = tab_index
                field["access_tab_stop"] = self._access_tab_stop(best)
                field["access_section"] = best.get("section")
                field["access_tab_path"] = [
                    section_rank,
                    tab_index,
                    0,
                    0,
                    source_order,
                ]
            else:
                field["access_tab_index"] = None
                field["access_tab_stop"] = False
                field["access_section"] = None
                field["access_tab_path"] = [
                    9,
                    1_000_000,
                    0,
                    0,
                    source_order,
                ]

    @staticmethod
    def _sort_fields_by_access_tab(fields: list[dict]) -> list[dict]:
        def key(item: dict):
            raw = item.get("access_tab_path")
            if isinstance(raw, (list, tuple)) and raw:
                try:
                    values = [int(x) for x in raw]
                    while len(values) < 5:
                        values.append(0)
                    return tuple(values[:5])
                except (TypeError, ValueError):
                    pass
            return (9, 1_000_000, 9, 1_000_000, 1_000_000)
        return sorted(fields, key=key)

    def _record_source_tables(self, record_source: str) -> list[dict]:
        """Résout les tables réelles derrière un RecordSource (table, requête ou SQL)."""
        if not self.access_structure:
            return []

        source = str(record_source or "").strip()
        if not source:
            return []

        tables = self.access_structure.get("tables", []) or []
        queries = self.access_structure.get("queries", []) or []

        tables_by_name = {
            str(t.get("name") or "").casefold(): t
            for t in tables
        }
        queries_by_name = {
            str(q.get("name") or "").casefold(): str(q.get("sql") or "")
            for q in queries
        }

        direct = tables_by_name.get(source.strip("[]").casefold())
        if direct:
            return [direct]

        sql = queries_by_name.get(source.strip("[]").casefold(), source)
        sql_cf = sql.casefold()

        found = []
        for table in tables:
            name = str(table.get("name") or "")
            if not name:
                continue
            bracketed = f"[{name}]".casefold()
            if bracketed in sql_cf:
                found.append(table)
                continue
            try:
                if re.search(rf"(?<![\wÀ-ÿ]){re.escape(name)}(?![\wÀ-ÿ])", sql, re.IGNORECASE):
                    found.append(table)
            except re.error:
                pass
        return found

    @staticmethod
    def _resolve_link_token(form: dict, token: str, available_fields: set[str]) -> str:
        """LinkMasterFields peut viser un contrôle plutôt qu'un champ de table."""
        raw = str(token or "").strip()
        if not raw:
            return ""

        for ctrl in form.get("controls", []) or []:
            if str(ctrl.get("name") or "").strip().casefold() == raw.casefold():
                source = CollectionImportDialog._plain_control_source(
                    str(ctrl.get("control_source") or "")
                )
                if source:
                    return source

        for field_name in available_fields:
            if field_name.casefold() == raw.casefold():
                return field_name

        return raw

    @staticmethod
    def _access_autonumber_order(table: dict) -> tuple[str, str]:
        """Retourne un ORDER BY sur le premier champ AutoNumber Access détecté.

        DAO marque un AutoNumber par l'attribut dbAutoIncrField (bit 16).
        Ce champ sert uniquement à restaurer l'ordre historique de création de
        la source ; MM3 continue à générer ses propres numéros de fiche.
        """
        for field in table.get("fields", []) or []:
            try:
                attributes = int(field.get("field_attributes", 0) or 0)
            except Exception:
                attributes = 0
            if not (attributes & 16):
                continue
            name = str(field.get("name") or "").strip()
            if not name:
                continue
            quoted = "[" + name.replace("]", "]]") + "] ASC"
            return quoted, "autonumber"
        return "", "source"

    def _access_record_order(
        self,
        form: dict,
        available_fields: set[str],
    ) -> tuple[str, str]:
        """Retourne un ORDER BY SQL sûr à partir du tri actif du formulaire Access.

        Aucun champ métier n'est supposé. Les noms de contrôles Access sont
        résolus vers leur ControlSource ; seuls les champs réellement présents
        dans la table source sont retenus.
        """
        raw = ""
        mode = "source"

        # 1) Tri explicitement actif dans le formulaire.
        if bool(form.get("order_by_on")):
            raw = str(form.get("order_by") or "").strip()
            if raw:
                mode = "form_order"

        # 2) À défaut, tri porté par le RecordSource (requête enregistrée ou SQL).
        if not raw:
            record_source = str(form.get("record_source") or "").strip()
            query_sql = ""
            if record_source:
                if re.search(r"\bSELECT\b", record_source, re.IGNORECASE):
                    query_sql = record_source
                elif self.access_structure:
                    for query in self.access_structure.get("queries", []) or []:
                        if (
                            str(query.get("name") or "").strip().casefold()
                            == record_source.strip("[]").casefold()
                        ):
                            query_sql = str(query.get("sql") or "")
                            break
            if query_sql:
                match = re.search(
                    r"\bORDER\s+BY\s+(.+?)(?:;\s*$|$)",
                    query_sql,
                    re.IGNORECASE | re.DOTALL,
                )
                if match:
                    raw = str(match.group(1) or "").strip()
                    if raw:
                        mode = "query_order"

        if not raw:
            return "", "source"

        field_map = {str(name).casefold(): str(name) for name in available_fields}
        controls = list(form.get("controls", []) or [])

        def resolve_token(token: str) -> str:
            cleaned = str(token or "").strip()
            # Retirer crochets Access et éventuel préfixe Table.Champ.
            parts = [part.strip() for part in cleaned.split(".") if part.strip()]
            candidate = parts[-1] if parts else cleaned
            candidate = candidate.strip().strip("[]").strip()

            # Le tri peut viser le nom d'un contrôle du formulaire.
            for ctrl in controls:
                if str(ctrl.get("name") or "").strip().casefold() == candidate.casefold():
                    source = self._plain_control_source(
                        str(ctrl.get("control_source") or "")
                    )
                    if source:
                        candidate = source
                        break

            actual = field_map.get(candidate.casefold())
            return actual or ""

        terms: list[str] = []
        for raw_term in raw.split(","):
            term = str(raw_term or "").strip()
            if not term:
                continue

            direction = ""
            match = re.match(r"^(.*?)(?:\s+(ASC|DESC))?$", term, re.IGNORECASE)
            if match:
                token = str(match.group(1) or "").strip()
                direction = str(match.group(2) or "").upper()
            else:
                token = term

            field_name = resolve_token(token)
            if not field_name:
                continue

            quoted = "[" + field_name.replace("]", "]]") + "]"
            if direction in {"ASC", "DESC"}:
                quoted += " " + direction
            terms.append(quoted)

        if not terms:
            return "", "source"
        return ", ".join(terms), mode

    def _best_form_for_table(self, table: dict) -> dict | None:
        """Choisit le formulaire de saisie le plus représentatif de la table source."""
        if not self.access_structure:
            return None

        table_name = str(table.get("name") or "")
        table_id = self._access_identity(table_name)
        field_names = {
            str(f.get("name") or "")
            for f in table.get("fields", []) or []
        }
        field_cf = {x.casefold() for x in field_names}

        best = None
        best_score = -1

        for form in self.access_structure.get("forms", []) or []:
            source_tables = self._record_source_tables(
                str(form.get("record_source") or "")
            )
            source_names = {
                str(t.get("name") or "").casefold()
                for t in source_tables
            }

            score = 0
            direct_source = (
                str(form.get("record_source") or "").strip("[]").casefold()
                == table_name.casefold()
            )
            if direct_source:
                score += 1200
            elif table_name.casefold() in source_names:
                score += 600

            form_name_id = self._access_identity(str(form.get("name") or ""))
            caption_id = self._access_identity(str(form.get("caption") or ""))
            if table_id:
                if form_name_id == table_id or caption_id == table_id:
                    score += 5000
                elif table_id in form_name_id or table_id in caption_id:
                    score += 1800

            exact_bound = 0
            usable_tabbed = 0
            visible_bound = 0
            subforms = 0
            for ctrl in form.get("controls", []) or []:
                if str(ctrl.get("source_object") or "").strip():
                    subforms += 1
                    continue

                cs = self._plain_control_source(
                    str(ctrl.get("control_source") or "")
                )
                if not cs or cs.casefold() not in field_cf:
                    continue

                exact_bound += 1
                if self._access_control_visible(ctrl):
                    visible_bound += 1
                if (
                    self._access_control_visible(ctrl)
                    and self._access_tab_index(ctrl) < 1_000_000
                ):
                    usable_tabbed += 1

            # Le formulaire destiné à la saisie a généralement le plus grand
            # nombre de champs réellement tabulables et visibles.
            score += usable_tabbed * 140
            score += visible_bound * 45
            score += exact_bound * 15
            score += subforms * 100

            if score > best_score:
                best_score = score
                best = form

        return best if best_score > 0 else None

    def _best_child_table_for_form(self, form: dict, child_link_token: str) -> dict | None:
        """Choisit la table réellement portée par le sous-formulaire."""
        candidates = self._record_source_tables(str(form.get("record_source") or ""))
        if not candidates:
            return None
        if len(candidates) == 1:
            return candidates[0]

        control_sources = [
            self._plain_control_source(str(c.get("control_source") or ""))
            for c in form.get("controls", []) or []
        ]
        control_sources = [x for x in control_sources if x]

        scored = []
        for table in candidates:
            fields = {
                str(f.get("name") or "").casefold()
                for f in table.get("fields", []) or []
            }
            score = sum(1 for cs in control_sources if cs.casefold() in fields)
            if child_link_token and child_link_token.casefold() in fields:
                score += 10
            scored.append((score, table))

        scored.sort(key=lambda x: x[0], reverse=True)
        if not scored:
            return None
        return scored[0][1]

    def _augment_selected_table_from_relations(self, selected: dict) -> tuple[dict, int, list[str], list[str]]:
        """Ajoute les champs des tables liées par les relations DAO Access.

        Cette voie ne dépend pas des formulaires Access. Elle est donc stable
        même lorsque l'analyse graphique des formulaires est désactivée.
        Un champ de la table principale portant relation_table/relation_field
        devient le Maître ; les autres champs de la table liée sont proposés
        comme champs complémentaires de la même fiche MM3.
        """
        if not self.access_structure:
            return selected, 0, [], []

        result = dict(selected)
        base_name = str(selected.get("name") or "")
        base_fields = [dict(f) for f in selected.get("fields", []) or []]
        tables = self.access_structure.get("tables", []) or []
        tables_by_name = {
            str(t.get("name") or "").casefold(): t
            for t in tables
            if str(t.get("name") or "").strip()
        }

        for field in base_fields:
            field.setdefault("source_table", base_name)
            field.setdefault("source_field", str(field.get("name") or ""))
            field.setdefault("target_label", str(field.get("name") or ""))

        added: list[dict] = []
        detected_tables: list[str] = []
        warnings: list[str] = []
        structured_specs: list[dict] = []
        existing = {
            (base_name.casefold(), str(f.get("name") or "").casefold())
            for f in base_fields
        }
        seen_specs: set[tuple[str, str, str]] = set()

        # 11.7.70.26.4 — Référentiels Access déclarés uniquement par RowSource.
        # Certaines bases Access (notamment lorsque plusieurs listes déroulantes
        # d'une même table principale utilisent la même table de référence) ne
        # possèdent pas de relation DAO explicite. Access expose alors seulement
        # lookup_source. Il faut reconstruire un groupe Maître/Reliés indépendant
        # pour CHAQUE table de référence, sans réutiliser le premier maître trouvé.
        #
        # Règle générique : si au moins deux champs de la table principale ont
        # pour lookup_source le nom exact d'une table Access, et que ces champs
        # existent aussi dans cette table, le premier champ de la table de
        # référence présent dans le groupe devient le Maître ; les autres deviennent
        # ses Reliés. Une relation DAO explicite reste prioritaire et n'est jamais
        # remplacée par cette déduction.
        lookup_groups: dict[str, list[dict]] = {}
        for field in base_fields:
            if str(field.get("relation_table") or "").strip():
                continue
            lookup = str(field.get("lookup_source") or "").strip().strip("[]")
            if not lookup:
                continue
            table = tables_by_name.get(lookup.casefold())
            if table is None:
                continue
            lookup_groups.setdefault(lookup.casefold(), []).append(field)

        for lookup_cf, group_fields in lookup_groups.items():
            if len(group_fields) < 2:
                continue
            child_table = tables_by_name.get(lookup_cf)
            if child_table is None:
                continue
            child_table_name = str(child_table.get("name") or "").strip()
            child_fields = [dict(f) for f in child_table.get("fields", []) or []]
            child_names = [str(f.get("name") or "").strip() for f in child_fields]
            group_by_name = {
                str(f.get("source_field") or f.get("name") or "").strip().casefold(): f
                for f in group_fields
            }
            common_child_names = [name for name in child_names if name.casefold() in group_by_name]
            if len(common_child_names) < 2:
                continue

            child_master = common_child_names[0]
            master_field = group_by_name[child_master.casefold()]
            parent_master = str(
                master_field.get("source_field") or master_field.get("name") or child_master
            ).strip()
            spec_key = (child_table_name.casefold(), parent_master.casefold(), child_master.casefold())
            if spec_key in seen_specs:
                continue
            seen_specs.add(spec_key)
            detected_tables.append(child_table_name)
            structured_specs.append({
                "related_form": child_table_name,
                "child_table": child_table_name,
                "parent_master_source": parent_master,
                "child_master_source": child_master,
                "access_tab_index": 100000 + len(structured_specs),
                "access_tab_stop": True,
            })
            master_field["structured_reference_table"] = child_table_name
            master_field["structured_reference_master"] = child_master

            # Les champs déjà présents dans la table principale ne doivent pas
            # être dupliqués : on les requalifie en champs Reliés et leur source
            # canonique devient la table de référence.
            for child_name in common_child_names[1:]:
                linked_field = group_by_name[child_name.casefold()]
                linked_field.update({
                    "source_table": child_table_name,
                    "source_field": child_name,
                    "is_related_field": True,
                    "related_form": child_table_name,
                    "linked_master_source": parent_master,
                    "linked_child_source": child_master,
                })

        for master_field in base_fields:
            child_table_name = str(master_field.get("relation_table") or "").strip()
            child_master = str(master_field.get("relation_field") or "").strip()
            parent_master = str(master_field.get("source_field") or master_field.get("name") or "").strip()
            if not child_table_name or not child_master or not parent_master:
                continue

            child_table = tables_by_name.get(child_table_name.casefold())
            if child_table is None:
                warnings.append(
                    f"Relation « {parent_master} » : table « {child_table_name} » introuvable"
                )
                continue

            child_fields = [dict(f) for f in child_table.get("fields", []) or []]
            child_names_cf = {str(f.get("name") or "").casefold() for f in child_fields}
            if child_master.casefold() not in child_names_cf:
                warnings.append(
                    f"Relation « {parent_master} » : champ lié « {child_master} » absent de « {child_table_name} »"
                )
                continue

            spec_key = (child_table_name.casefold(), parent_master.casefold(), child_master.casefold())
            if spec_key in seen_specs:
                continue
            seen_specs.add(spec_key)
            detected_tables.append(child_table_name)
            structured_specs.append({
                "related_form": child_table_name,
                "child_table": child_table_name,
                "parent_master_source": parent_master,
                "child_master_source": child_master,
                "access_tab_index": 100000 + len(structured_specs),
                "access_tab_stop": True,
            })

            # Le champ de la table principale reste le Maître du référentiel.
            master_field["structured_reference_table"] = child_table_name
            master_field["structured_reference_master"] = child_master

            for order, schema_field in enumerate(child_fields):
                source_field = str(schema_field.get("name") or "").strip()
                if not source_field or source_field.casefold() == child_master.casefold():
                    continue
                identity = (child_table_name.casefold(), source_field.casefold())
                if identity in existing:
                    continue

                synthetic = dict(schema_field)
                synthetic.update({
                    "name": source_field,
                    "display_name": f"{source_field}  [{child_table_name}]",
                    "target_label": source_field,
                    "source_table": child_table_name,
                    "source_field": source_field,
                    "is_related_field": True,
                    "related_form": child_table_name,
                    "linked_master_source": parent_master,
                    "linked_child_source": child_master,
                    "access_tab_index": order,
                    "access_tab_stop": True,
                    "access_tab_path": [100000 + len(structured_specs), order, 0, order, len(added)],
                })
                added.append(synthetic)
                existing.add(identity)

        result["fields"] = base_fields + added
        result["access_main_form"] = ""
        result["access_tab_order_detected"] = False
        result["structured_reference_specs"] = structured_specs
        # 11.7.70.5 — même sans formulaire exploitable, un AutoNumber de la
        # table principale définit un ordre de source stable et historique.
        auto_order_sql, auto_order_mode = self._access_autonumber_order(selected)
        result["access_record_order_sql"] = auto_order_sql
        result["access_record_order_mode"] = auto_order_mode
        return result, len(added), sorted(set(detected_tables), key=str.casefold), warnings


    def _augment_selected_table_from_subforms(self, selected: dict) -> tuple[dict, int, list[str], list[str]]:
        """Ajoute les champs réellement affichés dans les sous-formulaires liés.

        Aucune table ni aucun champ métier n'est codé en dur : tout vient des
        propriétés Access SourceObject / RecordSource / LinkMasterFields /
        LinkChildFields / ControlSource.
        """
        if not self.access_structure:
            return selected, 0, [], []

        main_form = self._best_form_for_table(selected)
        if not main_form:
            # 11.7.65 — l'analyse des formulaires Access n'est plus nécessaire
            # pour reconstruire les tables complémentaires. Le lecteur DAO
            # fournit déjà les relations explicites de la base (table/champ).
            # On s'en sert comme solution principale de repli afin de retrouver
            # IMA, Gisements et toute autre table liée sans PowerShell.
            return self._augment_selected_table_from_relations(selected)

        result = dict(selected)
        base_name = str(selected.get("name") or "")
        base_fields = [dict(f) for f in selected.get("fields", []) or []]
        base_field_names = {
            str(f.get("name") or "")
            for f in base_fields
        }
        base_cf = {x.casefold() for x in base_field_names}

        for f in base_fields:
            f.setdefault("source_table", base_name)
            f.setdefault("source_field", str(f.get("name") or ""))
            f.setdefault("target_label", str(f.get("name") or ""))

        # Ordre réel de saisie du formulaire principal Access.
        self._apply_access_tab_order_to_fields(main_form, base_fields)

        # Ordre des FICHES : indépendant de l'ordre de tabulation et d'un
        # éventuel champ "N°". Si le formulaire Access possède un tri actif,
        # il devient l'ordre de création des fiches. Sinon, l'ordre naturel
        # renvoyé par DAO est conservé strictement.
        record_order_sql, record_order_mode = self._access_record_order(
            main_form, base_field_names
        )
        # 11.7.70.5 — si le formulaire/requête n'impose aucun tri, restaurer
        # l'ordre historique de création de la table via son AutoNumber.
        # La valeur Access n'est jamais reprise comme N° MM3 : elle sert
        # uniquement à ordonner les lignes avant création des fiches 1..N.
        if not record_order_sql:
            record_order_sql, record_order_mode = self._access_autonumber_order(selected)
        result["access_record_order_sql"] = record_order_sql
        result["access_record_order_mode"] = record_order_mode

        forms = self.access_structure.get("forms", []) or []
        forms_by_name = {
            str(f.get("name") or "").casefold(): f
            for f in forms
        }

        added = []
        detected_forms = []
        warnings = []
        structured_specs = []
        existing = {
            (base_name.casefold(), str(f.get("name") or "").casefold())
            for f in base_fields
        }

        for sub_ctrl in main_form.get("controls", []) or []:
            source_object = str(sub_ctrl.get("source_object") or "").strip()
            if not source_object:
                continue

            child_name = source_object
            if "." in child_name:
                prefix, remainder = child_name.split(".", 1)
                if prefix.casefold() in {"form", "forms", "formulaire", "formulaires"}:
                    child_name = remainder
            child_name = child_name.strip("[] ")

            child_form = forms_by_name.get(child_name.casefold())
            if child_form is None:
                warnings.append(f"Sous-formulaire « {source_object} » non résolu")
                continue

            master_tokens = self._split_access_link_fields(
                str(sub_ctrl.get("link_master_fields") or "")
            )
            child_tokens = self._split_access_link_fields(
                str(sub_ctrl.get("link_child_fields") or "")
            )

            if len(master_tokens) != 1 or len(child_tokens) != 1:
                warnings.append(
                    f"« {child_name} » : liaison multiple ou absente non importée automatiquement"
                )
                continue

            master_source = self._resolve_link_token(
                main_form, master_tokens[0], base_field_names
            )

            # On doit maintenant connaître la table enfant pour résoudre le champ enfant.
            child_table = self._best_child_table_for_form(child_form, child_tokens[0])
            if child_table is None:
                warnings.append(f"« {child_name} » : table source non résolue")
                continue

            child_table_name = str(child_table.get("name") or "")
            child_field_names = {
                str(f.get("name") or "")
                for f in child_table.get("fields", []) or []
            }
            child_source = self._resolve_link_token(
                child_form, child_tokens[0], child_field_names
            )

            if master_source.casefold() not in base_cf:
                warnings.append(
                    f"« {child_name} » : champ maître « {master_source} » absent de la table principale"
                )
                continue
            if child_source.casefold() not in {x.casefold() for x in child_field_names}:
                warnings.append(
                    f"« {child_name} » : champ enfant « {child_source} » absent de sa table source"
                )
                continue

            detected_forms.append(str(child_form.get("name") or child_name))
            parent_section = self._access_section_rank(sub_ctrl)
            parent_tab = self._access_tab_index(sub_ctrl)
            structured_specs.append({
                "related_form": str(child_form.get("name") or child_name),
                "child_table": child_table_name,
                "parent_master_source": master_source,
                "child_master_source": child_source,
                "access_tab_index": parent_tab,
                "access_tab_stop": self._access_tab_stop(sub_ctrl),
            })

            # Marquer le champ maître existant dans la table principale.
            for field in base_fields:
                if str(field.get("name") or "").casefold() == master_source.casefold():
                    field["structured_reference_table"] = child_table_name
                    field["structured_reference_master"] = child_source
                    field["lookup_source"] = child_table_name
                    field["relation_table"] = child_table_name
                    field["relation_field"] = child_source

            schema_by_name = {
                str(f.get("name") or "").casefold(): dict(f)
                for f in child_table.get("fields", []) or []
            }

            for ctrl in child_form.get("controls", []) or []:
                control_source = self._plain_control_source(
                    str(ctrl.get("control_source") or "")
                )
                if not control_source:
                    continue

                # Le champ enfant servant de clé est déjà représenté par le maître.
                if control_source.casefold() == child_source.casefold():
                    continue

                schema_field = schema_by_name.get(control_source.casefold())
                if not schema_field:
                    # Contrôle calculé ou champ provenant d'une autre table d'une requête complexe.
                    continue

                identity = (child_table_name.casefold(), control_source.casefold())
                if identity in existing:
                    continue

                label = str(ctrl.get("label") or "").strip()
                if not label:
                    label = str(ctrl.get("name") or "").strip()
                if not label:
                    label = control_source

                child_tab = self._access_tab_index(ctrl)
                synthetic = dict(schema_field)
                synthetic.update({
                    "name": label,
                    "display_name": f"{label}  [{child_form.get('name') or child_table_name}]",
                    "target_label": label,
                    "source_table": child_table_name,
                    "source_field": control_source,
                    "is_related_field": True,
                    "related_form": str(child_form.get("name") or child_name),
                    "linked_master_source": master_source,
                    "linked_child_source": child_source,
                    "access_tab_index": child_tab,
                    "access_tab_stop": self._access_tab_stop(ctrl),
                    "access_tab_path": [
                        parent_section,
                        parent_tab,
                        self._access_section_rank(ctrl),
                        child_tab,
                        len(added),
                    ],
                })
                added.append(synthetic)
                existing.add(identity)

        # 11.7.70.26.8 — récupérer aussi les calculs portés par le formulaire
        # principal. Access conserve parfois un champ physique (ex. Currency)
        # tout en affichant sa vraie valeur via un contrôle = [A]*[B]. Dans ce
        # cas la formule du formulaire doit primer sur le type physique afin de
        # recréer un vrai champ calculé MM3. Aucune règle métier/noms en dur.
        for ctrl in main_form.get("controls", []) or []:
            raw_expr = str(ctrl.get("control_source") or "").strip()
            if not raw_expr.startswith("="):
                continue
            # Un contrôle calculé Access peut avoir un libellé attaché différent
            # de son nom de contrôle. Tester les deux évite de perdre la formule
            # lorsque Caption/Label masque le vrai nom du champ affiché.
            candidates = [
                str(ctrl.get("name") or "").strip(),
                str(ctrl.get("label") or "").strip(),
            ]
            candidates = [c for c in candidates if c]
            if not candidates:
                continue
            candidate_cf = {c.casefold() for c in candidates}
            target_field = next((
                f for f in base_fields
                if str(f.get("target_label") or f.get("name") or "").strip().casefold() in candidate_cf
            ), None)
            if target_field is None:
                continue
            expr = raw_expr[1:].strip()
            # Les opérateurs arithmétiques et références [Champ] sont déjà au
            # format intermédiaire compris par le convertisseur MM3.
            if expr and re.search(r"\[[^\]]+\]", expr):
                target_field["calculation_expression"] = expr
                target_field["calculation_result_type"] = str(
                    target_field.get("dao_type") or target_field.get("type") or ""
                )
                target_field.setdefault("calculation_format", "truncate2")

        # 11.7.70.26.10 — dernier filet générique pour les totaux Access stockés
        # comme colonnes physiques (souvent Currency) alors que le formulaire les
        # calcule sans exposer un ControlSource rapprochable. On ne déclenche cette
        # déduction que si les rôles sont non ambigus : un champ de total monétaire,
        # un champ de prix monétaire et un champ de quantité numérique. Aucun nom
        # propre à une collection n'est utilisé.
        def _norm_words(value):
            text = unicodedata.normalize("NFKD", str(value or ""))
            text = "".join(ch for ch in text if not unicodedata.combining(ch)).casefold()
            return set(re.findall(r"[a-z0-9]+", text))

        total_words = {"total", "totale", "totaux"}
        cost_words = {"cout", "cost", "montant", "amount", "valeur", "value"}
        price_words = {"prix", "price", "tarif", "rate"}
        qty_words = {"quantite", "quantity", "qty", "nombre", "nb", "nbre", "pieces", "piece", "count"}

        unresolved_totals = []
        price_candidates = []
        qty_candidates = []
        for f in base_fields:
            if str(f.get("calculation_expression") or "").strip():
                continue
            label = str(f.get("target_label") or f.get("display_name") or f.get("name") or "")
            words = _norm_words(label)
            physical = AccessFieldMappingDialog._physical_mm3_type(str(f.get("type") or ""), label, f)
            if physical == "Monétaire" and (words & total_words) and (words & cost_words):
                unresolved_totals.append(f)
            if physical == "Monétaire" and (words & price_words) and not (words & total_words):
                price_candidates.append(f)
            if physical == "Nombre" and (words & qty_words):
                qty_candidates.append(f)

        if len(unresolved_totals) == 1 and len(price_candidates) == 1 and len(qty_candidates) == 1:
            total_field = unresolved_totals[0]
            price_field = price_candidates[0]
            qty_field = qty_candidates[0]
            price_name = str(price_field.get("name") or price_field.get("source_field") or "").strip()
            qty_name = str(qty_field.get("name") or qty_field.get("source_field") or "").strip()
            if price_name and qty_name:
                total_field["calculation_expression"] = f"[{qty_name}] * [{price_name}]"
                total_field["calculation_result_type"] = "Monétaire"
                total_field["calculation_format"] = "truncate2"
                total_field["result_suffix"] = "€"

        # 11.7.70.26.6 — compléter les groupes Maître/Reliés avec les listes
        # déroulantes du formulaire principal dont la RowSource pointe vers une
        # table Access multi-colonnes. Cette voie est indépendante des relations
        # DAO et des sous-formulaires : elle couvre notamment les référentiels
        # de datation/classification utilisés directement par plusieurs combos.
        #
        # Règle générique : plusieurs contrôles liés à des champs de la table
        # principale et alimentés par la même table Access forment un groupe.
        # L'ordre physique des colonnes de la table de référence désigne le
        # Maître (première colonne commune) ; les autres colonnes communes sont
        # Reliées à ce Maître. Un groupe déjà décrit par un sous-formulaire/DAO
        # n'est jamais recréé.
        tables_by_name = {
            str(t.get("name") or "").casefold(): t
            for t in (self.access_structure.get("tables", []) or [])
            if str(t.get("name") or "").strip()
        }
        base_by_name = {
            str(f.get("source_field") or f.get("name") or "").casefold(): f
            for f in base_fields
            if str(f.get("source_field") or f.get("name") or "").strip()
        }
        row_source_groups: dict[str, set[str]] = {}
        for ctrl in main_form.get("controls", []) or []:
            control_source = self._plain_control_source(str(ctrl.get("control_source") or ""))
            row_source = str(ctrl.get("row_source") or "").strip()
            if not control_source or not row_source or control_source.casefold() not in base_by_name:
                continue
            candidates = self._record_source_tables(row_source)
            # RowSource peut aussi être le nom brut d'une table.
            if not candidates:
                raw = row_source.strip().strip("[]")
                table = tables_by_name.get(raw.casefold())
                candidates = [table] if table is not None else []
            for table in candidates:
                table_name = str((table or {}).get("name") or "").strip()
                # 11.7.70.26.8 — la table principale n'est JAMAIS un
                # référentiel Maître/Reliés. Une RowSource de requête peut la
                # mentionner avec une vraie table de référence ; la retenir ici
                # avalait alors Époque/Genre/etc. et faisait disparaître leurs
                # vrais groupes. Les sous-formulaires/relations restent prioritaires.
                if table_name and table_name.casefold() != base_name.casefold():
                    row_source_groups.setdefault(table_name.casefold(), set()).add(control_source)

        existing_spec_tables = {
            str(spec.get("child_table") or "").casefold()
            for spec in structured_specs
            if str(spec.get("child_table") or "").strip()
        }
        for table_cf, control_fields in row_source_groups.items():
            if table_cf in existing_spec_tables or len(control_fields) < 2:
                continue
            child_table = tables_by_name.get(table_cf)
            if child_table is None:
                continue
            child_table_name = str(child_table.get("name") or "").strip()
            child_names = [
                str(f.get("name") or "").strip()
                for f in (child_table.get("fields", []) or [])
                if str(f.get("name") or "").strip()
            ]
            common = [name for name in child_names if name.casefold() in {x.casefold() for x in control_fields}]
            if len(common) < 2:
                continue
            master_name = common[0]
            master_entry = base_by_name.get(master_name.casefold())
            if master_entry is None:
                continue
            structured_specs.append({
                "related_form": child_table_name,
                "child_table": child_table_name,
                "parent_master_source": master_name,
                "child_master_source": master_name,
                "access_tab_index": 100000 + len(structured_specs),
                "access_tab_stop": True,
            })
            existing_spec_tables.add(table_cf)
            detected_forms.append(child_table_name)
            master_entry["structured_reference_table"] = child_table_name
            master_entry["structured_reference_master"] = master_name
            master_entry["lookup_source"] = child_table_name

            for linked_name in common[1:]:
                linked_entry = base_by_name.get(linked_name.casefold())
                if linked_entry is None:
                    continue
                linked_entry.update({
                    "source_table": child_table_name,
                    "source_field": linked_name,
                    "is_related_field": True,
                    "related_form": child_table_name,
                    "linked_master_source": master_name,
                    "linked_child_source": master_name,
                    "lookup_source": child_table_name,
                })

        result["fields"] = self._sort_fields_by_access_tab(base_fields + added)
        result["access_main_form"] = str(main_form.get("name") or "")
        result["access_tab_order_detected"] = any(
            int((f.get("access_tab_path") or [1_000_000])[0]) < 1_000_000
            for f in result["fields"]
        )
        result["structured_reference_specs"] = structured_specs
        return result, len(added), sorted(set(detected_forms), key=str.casefold), warnings


    def _choose_selected_table(self) -> None:
        item = self._selected_top_level_table_item()
        if item is None or not self.access_structure:
            return

        name = item.text(0)
        tables = self.access_structure.get("tables", [])
        selected = next((t for t in tables if str(t.get("name", "")) == name), None)
        if selected is None:
            return

        selected, added_related, detected_forms, subform_warnings = (
            self._augment_selected_table_from_subforms(selected)
        )
        self.selected_access_table = selected
        fields = selected.get("fields", [])
        rows = selected.get("rows")
        rows_text = str(rows) if isinstance(rows, int) else tr("nombre inconnu de", self.language)
        if self.language.lower().startswith("de"):
            self.table_choice_label.setText(
                f"✓ Quelltabelle ausgewählt: {name} — {rows_text} Zeile(n), {len(fields)} Feld(er)"
                + (f", davon {added_related} Feld(er) aus " + ", ".join(detected_forms) + "." if added_related else ".")
            )
        elif self.language.lower().startswith("en"):
            self.table_choice_label.setText(
                f"✓ Source table selected: {name} — {rows_text} row(s), {len(fields)} field(s)"
                + (f", including {added_related} field(s) from " + ", ".join(detected_forms) + "." if added_related else ".")
            )
        else:
            self.table_choice_label.setText(
                f"✓ Table source retenue : {name} — {rows_text} ligne(s), {len(fields)} champ(s)"
                + (f", dont {added_related} champ(s) provenant de " + ", ".join(detected_forms) + "." if added_related else ".")
            )
        self.access_field_mapping = None
        self.preview_btn.setEnabled(True)
        self.mapping_btn.setEnabled(True)
        self._set_access_step_highlight(self.mapping_btn)
        if self.language.lower().startswith("de"):
            tab_note = (
                " Die Tab-Reihenfolge des Access-Formulars wurde erkannt und wird in der Feldzuordnung sowie im G-Skol-Datensatzformular beibehalten."
                if bool(selected.get("access_tab_order_detected")) else ""
            )
            self.next_step_label.setText(
                "Quelltabelle bestätigt. Klicken Sie auf „Feldzuordnung…“, um festzulegen, welche Access-Felder unter welchem Namen und mit welchem Typ zu G-Skol-Feldern werden." + tab_note
            )
        elif self.language.lower().startswith("en"):
            tab_note = (
                " The Access form tab order was recognized and will be preserved "
                "in Mapping and then in the G-Skol Record form."
                if bool(selected.get("access_tab_order_detected"))
                else ""
            )
            self.next_step_label.setText(
                "Source table confirmed. Click ‘Field mapping…’ to choose which Access fields "
                "will become G-Skol fields, under which name and with which type."
                + tab_note
            )
        else:
            tab_note = (
                " L’ordre de tabulation du formulaire Access a été reconnu et sera repris "
                "dans Correspondance puis dans la Fiche G-Skol."
                if bool(selected.get("access_tab_order_detected"))
                else ""
            )
            self.next_step_label.setText(
                "Table source validée. Cliquez sur « Correspondance des champs… » pour décider "
                "quels champs Access deviendront des champs G-Skol, sous quel nom et avec quel type."
                + tab_note
            )
        lang = self.language.lower()
        if lang.startswith("en"):
            title = "Source table selected"
            intro = f"The table ‘{name}’ has been selected as the table containing the records to import.\n\n"
            summary = f"{rows_text} row(s) — {len(fields)} field(s) suggested."
            details = (f"\n\nG-Skol detected {len(detected_forms)} linked subform(s) and added {added_related} field(s) actually used in those subforms." if added_related else "")
            if subform_warnings:
                details += "\n\nNote: " + " ; ".join(subform_warnings[:3])
            ending = "\n\nYou can now prepare the field mapping."
        elif lang.startswith("de"):
            title = "Quelltabelle ausgewählt"
            intro = f"Die Tabelle „{name}“ wurde als Tabelle der zu importierenden Datensätze ausgewählt.\n\n"
            summary = f"{rows_text} Zeile(n) — {len(fields)} Feld(er) vorgeschlagen."
            details = (f"\n\nG-Skol hat {len(detected_forms)} verknüpfte Unterformular(e) erkannt und {added_related} tatsächlich verwendete(s) Feld(er) hinzugefügt." if added_related else "")
            if subform_warnings:
                details += "\n\nHinweis: " + " ; ".join(subform_warnings[:3])
            ending = "\n\nSie können jetzt die Feldzuordnung vorbereiten."
        else:
            title = "Table source retenue"
            intro = f"La table « {name} » a été retenue comme table des fiches à importer.\n\n"
            summary = f"{rows_text} ligne(s) — {len(fields)} champ(s) proposés."
            details = (f"\n\nG-Skol a détecté {len(detected_forms)} sous-formulaire(s) lié(s) et ajouté {added_related} champ(s) réellement utilisés dans ces sous-formulaires." if added_related else "")
            if subform_warnings:
                details += "\n\nRemarque : " + " ; ".join(subform_warnings[:3])
            ending = "\n\nVous pouvez maintenant préparer la correspondance des champs."
        QMessageBox.information(self, title, intro + summary + details + ending)

    def _open_data_preview(self) -> None:
        if self.access_source is None or self.selected_access_table is None:
            return
        table_name = str(self.selected_access_table.get("name", ""))
        if not table_name:
            return
        self.preview_btn.setEnabled(False)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        QApplication.processEvents()
        try:
            preview = self._read_access_preview(self.access_source, table_name, 10)
        except Exception as exc:
            QMessageBox.warning(self, "Aperçu Access impossible", str(exc))
            return
        finally:
            QApplication.restoreOverrideCursor()
            self.preview_btn.setEnabled(True)
        try:
            if self._preview_window is not None and self._preview_window.isVisible():
                self._preview_window.close()
        except RuntimeError:
            self._preview_window = None
        window = AccessDataPreviewDialog(table_name, preview, None, self.language)
        window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        window.destroyed.connect(lambda *_: setattr(self, "_preview_window", None))
        self._preview_window = window
        window.show()
        window.raise_()
        window.activateWindow()

    def _open_field_mapping(self) -> None:
        if self.selected_access_table is None:
            return

        try:
            if self._mapping_window is not None and self._mapping_window.isVisible():
                self._mapping_window.raise_()
                self._mapping_window.activateWindow()
                return
        except RuntimeError:
            self._mapping_window = None

        table_name = str(self.selected_access_table.get("name", ""))
        dialog = AccessFieldMappingDialog(
            self.selected_access_table,
            self,
            model_key=getattr(self, "import_model_key", "blank"),
            preview_loader=lambda: self._read_access_preview(self.access_source, table_name, 10),
        )
        dialog.setModal(False)
        dialog.setWindowModality(Qt.WindowModality.NonModal)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        dialog.finished.connect(lambda result, d=dialog: self._field_mapping_finished(d, result))
        dialog.destroyed.connect(lambda *_: setattr(self, "_mapping_window", None))
        self._mapping_window = dialog
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _field_mapping_finished(self, dialog: AccessFieldMappingDialog, result: int) -> None:
        if result != int(QDialog.DialogCode.Accepted) or dialog.mapping is None:
            return

        self.access_field_mapping = dialog.mapping
        imported = sum(1 for item in dialog.mapping if item.get("action") == "Importer")
        ignored = len(dialog.mapping) - imported
        if self.language.lower().startswith("de"):
            self.next_step_label.setText(
                f"✓ Zuordnung bestätigt: {imported} Feld(er) werden importiert, {ignored} ignoriert. Bereit zum Erstellen einer neuen Sammlung und zum Importieren der Datensätze."
            )
        elif self.language.lower().startswith("en"):
            self.next_step_label.setText(
                f"✓ Mapping confirmed: {imported} field(s) will be imported, "
                f"{ignored} ignored. Ready to create a new collection and import the records."
            )
        else:
            self.next_step_label.setText(
                f"✓ Correspondance validée : {imported} champ(s) seront importés, "
                f"{ignored} ignoré(s). Prêt pour la création d'une nouvelle collection "
                "puis import des fiches."
            )
        self.real_import_btn.setEnabled(True)
        self._set_access_step_highlight(self.real_import_btn)
        QMessageBox.information(
            self,
            tr("Correspondance validée", self.language),
            tr("Correspondance enregistrée pour cette préparation d’import.\n\n", self.language)
            + (
                (f"{imported} field(s) to import — {ignored} field(s) ignored.\n\n" if self.language.lower().startswith("en") else (f"{imported} Feld(er) zu importieren — {ignored} Feld(er) ignoriert.\n\n" if self.language.lower().startswith("de") else f"{imported} champ(s) à importer — {ignored} champ(s) ignoré(s).\n\n"))
            )
            + tr("Aucune collection n’a encore été créée ou modifiée.", self.language),
        )

    @staticmethod
    def _mm3_field_type(label: str) -> str:
        value = str(label or "")
        if value == "Nombre":
            return "numeric"
        if value == "Monétaire":
            return "currency"
        if value == "Date":
            return "date"
        if value == "Bouton On / Off":
            return "boolean"
        if value == "Lien (Internet ou autre)":
            return "link"
        if value.startswith("Liste / Référentiel"):
            return "list"
        if value.startswith("Calculé"):
            return "calculated"
        if value == "Photo / Image":
            # Pour ce premier import grandeur nature, les données binaires restent
            # conservées comme texte descriptif si elles ne sont pas une photo exploitable.
            return "text"
        return "text"

    def _gskol_lang(self, en, de, fr=None):
        lang = self.language.lower()
        return de if lang.startswith("de") else (en if lang.startswith("en") else (fr if fr is not None else en))

    def _choose_mm3_file(self) -> None:
        start_dir = str(self._workspace_collections_folder())
        filename, _ = QFileDialog.getOpenFileName(
            self,
            (("Bestehende G-Skol-Sammlung auswählen" if self.language.lower().startswith("de") else ("Choose an existing G-Skol collection" if self.language.lower().startswith("en") else "Choisir une collection G-Skol existante"))),
            start_dir,
            tr("Collections G-Skol (*.coldb);;Tous les fichiers (*.*)", self.language),
        )
        if not filename:
            return

        path = Path(filename)
        try:
            rows = CollectionManager(path).inspect_collections()
        except Exception as exc:
            self.mm3_source = None
            self.mm3_collections = []
            self.mm3_collection_combo.clear()
            self.mm3_collection_combo.setEnabled(False)
            self.mm3_import_btn.setEnabled(False)
            QMessageBox.warning(
                self,
                (("G-Skol-Sammlung nicht erkannt" if self.language.lower().startswith("de") else ("Unrecognized G-Skol collection" if self.language.lower().startswith("en") else "Collection G-Skol non reconnue"))),
                (("Die ausgewählte Datei ist keine gültige G-Skol-Sammlung.\n\n" if self.language.lower().startswith("de") else ("The selected file is not a valid G-Skol collection.\n\n" if self.language.lower().startswith("en") else "Le fichier sélectionné n'est pas une collection G-Skol valide.\n\n")))
                + str(exc),
            )
            return

        if not rows:
            QMessageBox.information(
                self,
                (("Leere G-Skol-Datei" if self.language.lower().startswith("de") else ("Empty G-Skol file" if self.language.lower().startswith("en") else "Fichier G-Skol vide"))),
                (("Diese G-Skol-Datei enthält keine Sammlung." if self.language.lower().startswith("de") else ("This G-Skol file contains no collection." if self.language.lower().startswith("en") else "Ce fichier G-Skol ne contient aucune collection."))),
            )
            return

        self.mm3_source = path
        self.mm3_collections = [dict(row) for row in rows]
        self.mm3_source_label.setText(f"Quelle: {path}" if self.language.lower().startswith("de") else f"Source : {path}")

        self.mm3_collection_combo.blockSignals(True)
        self.mm3_collection_combo.clear()
        for row in self.mm3_collections:
            self.mm3_collection_combo.addItem(
                str(row.get("name") or "Collection"),
                int(row.get("id") or 0),
            )
        self.mm3_collection_combo.blockSignals(False)
        self.mm3_collection_combo.setEnabled(True)
        self.mm3_collection_combo.setCurrentIndex(0)
        self._on_mm3_collection_changed()

        # 11.7.70.11 — après le choix du fichier MM3, la prochaine action
        # logique est l'import. Ce comportement a été validé en 11.7.70.10.
        self.choose_mm3_btn.setDefault(False)
        self.mm3_import_btn.setDefault(True)
        self.mm3_import_btn.setFocus(Qt.FocusReason.OtherFocusReason)

    def _on_mm3_collection_changed(self, *_args) -> None:
        index = self.mm3_collection_combo.currentIndex()
        valid = (
            self.mm3_source is not None
            and 0 <= index < len(self.mm3_collections)
        )
        self.mm3_import_btn.setEnabled(valid)
        if not valid:
            return
        row = self.mm3_collections[index]
        detected_name = row.get('name') or 'Collection'
        self.mm3_info_label.setText(
            (f"Collection detected: ‘{detected_name}’. The import will create an independent file in Workspace/Collections. "
             "If this name already exists, G-Skol will add ‘- 2’, then ‘- 3’, etc.")
            if self.language.lower().startswith("en") else
            (f"Sammlung erkannt: „{detected_name}“. Beim Import wird eine unabhängige Datei in Workspace/Collections erstellt. "
             "Falls der Name bereits vorhanden ist, fügt G-Skol „- 2“, dann „- 3“ usw. hinzu.")
            if self.language.lower().startswith("de") else
            (f"Collection détectée : « {detected_name} ». L'import créera un fichier indépendant dans Workspace/Collections. "
             "Si ce nom existe déjà, G-Skol ajoutera « - 2 », puis « - 3 », etc.")
        )

    def _preview_mm3_model_mapping(self) -> None:
        """Brique 2.3.19 : contrôle des correspondances, lecture seule.

        Ne crée ni collection ni fiche. Le transfert sera raccordé séparément.
        """
        if self.mm3_source is None:
            return
        index = self.mm3_collection_combo.currentIndex()
        if not (0 <= index < len(self.mm3_collections)):
            return
        model_key = str(getattr(self, "import_model_key", "") or "")
        destinations = _import_model_field_choices(model_key)
        if not destinations:
            QMessageBox.warning(self, "Modèle non disponible",
                "Impossible de lire les champs du modèle sélectionné. Aucune donnée n'a été modifiée.")
            return
        source_id = int(self.mm3_collections[index].get("id") or 0)
        try:
            uri = self.mm3_source.resolve().as_uri() + "?mode=ro"
            with sqlite3.connect(uri, uri=True) as con:
                tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                source = []
                source_types = {}
                if "collection_custom_fields" in tables:
                    cc = {r[1] for r in con.execute('PRAGMA table_info("collection_custom_fields")')}
                    if {"field_key", "field_type"}.issubset(cc):
                        condition = " WHERE collection_id=?" if "collection_id" in cc else ""
                        params = (source_id,) if condition else ()
                        for fkey, ftype in con.execute("SELECT field_key, field_type FROM collection_custom_fields" + condition, params):
                            source_types[str(fkey)] = str(ftype or "text").lower()
                if "collection_model_fields" in tables:
                    columns = {r[1] for r in con.execute('PRAGMA table_info("collection_model_fields")')}
                    if {"field_key", "custom_label"}.issubset(columns):
                        clause = " WHERE collection_id=?" if "collection_id" in columns else ""
                        args = (source_id,) if clause else ()
                        for key, label in con.execute("SELECT field_key, custom_label FROM collection_model_fields" + clause, args):
                            key = str(key or "")
                            if not key or key == "record_number":
                                continue
                            default = FIELD_BY_KEY[key].label if key in FIELD_BY_KEY else key
                            source.append((str(label or default), key))
                if "collection_custom_fields" in tables:
                    columns = {r[1] for r in con.execute('PRAGMA table_info("collection_custom_fields")')}
                    if {"field_key", "label"}.issubset(columns):
                        clause = " WHERE collection_id=?" if "collection_id" in columns else ""
                        args = (source_id,) if clause else ()
                        source.extend((str(label or key), str(key)) for key, label in
                                      con.execute("SELECT field_key, label FROM collection_custom_fields" + clause, args))
                if not source and "records" in tables:
                    source = [(str(r[1]), str(r[1])) for r in con.execute('PRAGMA table_info("records")')
                              if str(r[1]) not in {"id", "collection_id", "created_at", "updated_at"}]
        except Exception as exc:
            QMessageBox.warning(self, "Lecture impossible", str(exc))
            return
        # Un champ logique n'est présenté qu'une fois. Pour des collections
        # anciennes, le champ réellement alimenté peut être personnalisé,
        # tandis que son homonyme natif est vide. Privilégier LES VALEURS.
        unique_keys = {key: (label, key) for label, key in source}
        populated = {}
        try:
            with closing(sqlite3.connect(self.mm3_source.resolve().as_uri() + "?mode=ro", uri=True)) as scan:
                cols = {r[1] for r in scan.execute('PRAGMA table_info("records")')}
                tables = {r[0] for r in scan.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                for key in unique_keys:
                    if key in cols and key not in {"id", "collection_id"}:
                        # Quoted SQL identifier, only sourced from PRAGMA table_info.
                        quoted = '"' + key.replace('"', '""') + '"'
                        populated[key] = scan.execute(
                            f'SELECT COUNT(*) FROM records WHERE collection_id=? '
                            f"AND {quoted} IS NOT NULL AND TRIM(CAST({quoted} AS TEXT)) <> ''",
                            (source_id,)).fetchone()[0]
                    elif "record_custom_values" in tables:
                        populated[key] = scan.execute(
                            "SELECT COUNT(*) FROM record_custom_values v JOIN records r "
                            "ON r.id=v.record_id WHERE r.collection_id=? AND v.field_key=? "
                            "AND TRIM(COALESCE(v.value,''))<>''", (source_id, key)).fetchone()[0]
                    else:
                        populated[key] = 0
        except sqlite3.Error as exc:
            QMessageBox.warning(self, "Analyse des valeurs impossible",
                "La vérification des champs sources a échoué. "
                "Aucune collection n'a été modifiée.\n\n" + str(exc))
            return
        by_label = {}
        for label, key in unique_keys.values():
            norm = unicodedata.normalize("NFKD", label).casefold().strip()
            previous = by_label.get(norm)
            # D'abord le nombre de fiches alimentées, puis le champ natif.
            priority = (-populated.get(key, 0), 0 if key in FIELD_BY_KEY else 1, key)
            if previous is None or priority < previous[0]:
                by_label[norm] = (priority, (label, key))
        # 2.3.24.6.5 — Un champ logique source ne doit pas apparaître sous
        # plusieurs noms historiques. Les équivalences sont regroupées SEULEMENT
        # si les autres identifiants ne portent aucune donnée propre : ne jamais
        # fusionner silencieusement deux champs réellement différents.
        historical_groups = (
            {"site_name", "site1"}, {"mineral_class", "classe_mineraux"},
            {"internet_link", "lien"}, {"site_internet_link", "lien_mindat"},
            {"mineral_name", "nom"},
        )
        def logical_group(label, key):
            normalized = "".join(c for c in unicodedata.normalize("NFKD", label).casefold()
                                 if not unicodedata.combining(c)).strip()
            groups = (
                {"site", "site1"}, {"classe", "classe mineraux"},
                {"lien", "lien espece"}, {"lien mindat", "lien site"},
                {"nom", "espece"},
            )
            for idx, names in enumerate(groups):
                if normalized in names or str(key).casefold() in historical_groups[idx]:
                    return "historical:" + str(idx)
            return "key:" + str(key)
        grouped = {}
        for label, key in (value[1] for value in by_label.values()):
            grouped.setdefault(logical_group(label, key), []).append((label, key))
        source = []
        for candidates in grouped.values():
            if len(candidates) == 1:
                source.extend(candidates)
                continue
            with_values = [entry for entry in candidates if populated.get(entry[1], 0) > 0]
            # Plusieurs champs alimentés peuvent réellement porter des valeurs
            # distinctes : dans ce cas, ne pas les fusionner automatiquement.
            if len(with_values) > 1:
                source.extend(candidates)
            else:
                source.append(min(candidates, key=lambda entry:
                    (-populated.get(entry[1], 0), 0 if entry[1] in FIELD_BY_KEY else 1, entry[0])))
        source.sort(key=lambda x: x[0].casefold())
        if not source:
            QMessageBox.warning(self, "Champs introuvables", "Aucun champ source n'a pu être identifié.")
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Correspondance des champs G-Skol → modèle (vérification)")
        dialog.resize(950, 650)
        layout = QVBoxLayout(dialog)
        info = QLabel("Analyse de la collection source et correspondances avec le modèle choisi. "
                      "Les types sont proposés depuis G-Skol et restent modifiables pour la future collection. "
                      "Aucune donnée ni aucun modèle ne sera modifié : le transfert sera raccordé dans une prochaine brique.")
        info.setWordWrap(True)
        layout.addWidget(info)
        # Les clés internes restent distinctes même lorsque leurs libellés sont identiques.
        # Aucun champ ni modèle n'est écrit à cette étape de vérification.
        from collections import Counter
        label_counts = Counter(label.casefold() for label, _ in source)
        type_names = {"text": "Texte", "numeric": "Nombre", "number": "Nombre",
                      "currency": "Monétaire", "date": "Date", "boolean": "Bouton On / Off",
                      "list": "Liste / Référentiel", "link": "Lien", "binary": "Photo / Image",
                      "image": "Photo / Image", "calculated": "Calculé"}
        # Brique 2.3.22 : présentation alignée sur l'import Access.
        table = QTableWidget(len(source), 6, dialog)
        table.setHorizontalHeaderLabels(["Action", "Champ G-Skol", "Type G-Skol",
                                         "Champ du modèle", "Type du modèle", "Détection du modèle"])
        table.setAlternatingRowColors(True)
        for col in range(6):
            table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
        for col, width in enumerate((115, 230, 155, 230, 175, 265)):
            table.setColumnWidth(col, width)
        dialog.resize(1220, 740)
        # Équivalences sémantiques historiques : uniquement des propositions,
        # toujours modifiables dans la colonne « Champ du modèle ».
        def norm_name(value):
            return "".join(c for c in unicodedata.normalize("NFKD", str(value or "")).casefold()
                           if not unicodedata.combining(c)).strip()
        aliases = {
            "nom": "mineral_name", "espece": "mineral_name",
            "site1": "site_name", "site": "site_name",
            "classe mineraux": "mineral_class", "classe minerale": "mineral_class",
            "classe": "mineral_class", "formule chimique": "chemical_formula",
            "systeme cristallin": "crystal_system", "couleur fluo": "fluorescence_color",
            "etat de la fiche": "record_state", "localite type": "type_locality",
            # Anciennes collections G-Skol : noms historiques des liens.
            # Les clés de destination sont celles du catalogue natif ;
            # l'utilisateur peut toujours modifier ces propositions.
            "lien": "internet_link", "lien espece": "internet_link",
            "lien mindat": "site_internet_link", "lien site": "site_internet_link",
        }
        destination_by_key = {key: i for i, (_label, key) in enumerate(destinations)}
        candidate_rows = []
        for row_id, (src_label, src_key) in enumerate(source):
            choices = []
            for target_id, (target_label, target_key) in enumerate(destinations):
                if target_key == src_key:
                    rank = 3
                elif norm_name(target_label) == norm_name(src_label):
                    rank = 2
                elif aliases.get(norm_name(src_label)) == target_key:
                    rank = 1
                else:
                    continue
                choices.append((rank, target_id))
            for rank, target_id in choices:
                candidate_rows.append((rank, populated.get(src_key, 0), row_id, target_id))
        # Privilégier les champs qui contiennent des données, puis l'identifiant
        # natif, le libellé identique et enfin l'alias historique.
        proposals = {}
        assigned_destinations = set()
        for rank, count, row_id, target_id in sorted(
                candidate_rows, key=lambda c: (-int(c[1] > 0), -c[0], -c[1], c[2])):
            if row_id in proposals or target_id in assigned_destinations:
                continue
            proposals[row_id] = (target_id, rank)
            assigned_destinations.add(target_id)
        type_options = ("Texte", "Nombre", "Monétaire", "Date", "Bouton On / Off",
                        "Liste / Référentiel", "Lien", "Photo / Image", "Calculé")
        for row, (label, key) in enumerate(source):
            action = NoWheelComboBox()
            action.addItems(["Importer", "Ne pas importer"])
            table.setCellWidget(row, 0, action)
            display = label
            source_item = QTableWidgetItem(display)
            source_item.setToolTip(f"Identifiant interne : {key}")
            table.setItem(row, 1, source_item)
            spec = FIELD_BY_KEY.get(key)
            if key in source_types:
                proposed = type_names.get(source_types[key], "Texte")
                type_reason = "Métadonnées de la collection"
            elif spec is not None:
                proposed = ("Liste / Référentiel" if spec.referential else
                            "Monétaire" if key in {"price", "total_cost"} else
                            type_names.get(spec.field_type, "Texte"))
                type_reason = "Champ natif G-Skol"
            else:
                proposed = ("Photo / Image" if "photo" in key.casefold() or "image" in key.casefold()
                            else "Date" if "date" in key.casefold() else "Texte")
                type_reason = "Type proposé (à vérifier)"
            src_type = QTableWidgetItem(proposed)
            src_type.setToolTip(type_reason)
            table.setItem(row, 2, src_type)
            combo = NoWheelComboBox()
            combo.addItem("— Créer un nouveau champ", "__create__")
            combo.addItem("— Sans correspondance", "")
            for target_label, target_key in destinations:
                combo.addItem(target_label, target_key)
            chosen = proposals.get(row)
            if chosen is not None:
                available, rank = chosen
                combo.setCurrentIndex(available + 2)
                reason = ("Identifiant G-Skol identique" if rank == 3 else
                          "Libellé identique" if rank == 2 else
                          "Équivalence historique proposée")
            else:
                combo.setCurrentIndex(0)
                reason = "Aucune destination libre — correspondance manuelle possible"
            table.setCellWidget(row, 3, combo)
            type_combo = NoWheelComboBox()
            for name in type_options:
                type_combo.addItem(name, name)
            type_combo.setCurrentIndex(max(0, type_combo.findData(proposed)))
            type_combo.setToolTip("Type proposé pour la future collection uniquement. Le modèle reste intact.")
            table.setCellWidget(row, 4, type_combo)
            detection = QTableWidgetItem(reason + " — " + type_reason)
            detection.setToolTip("Correspondance proposée automatiquement ; modifiable par l'utilisateur.")
            table.setItem(row, 5, detection)
            if combo.currentData() == "__create__":
                action.setCurrentIndex(0)
        layout.addWidget(table, 1)
        status = QLabel("")
        status.setWordWrap(True)
        layout.addWidget(status)
        def refresh(*_):
            conflicts = {}
            selected = 0
            for row in range(table.rowCount()):
                ignored = table.cellWidget(row, 0).currentIndex() != 0
                background = QColor("#ECEFEE") if ignored else QColor(Qt.GlobalColor.transparent)
                foreground = QColor("#8A918D") if ignored else QColor("#202522")
                for col in (1, 2, 5):
                    item = table.item(row, col)
                    if item:
                        item.setBackground(background)
                        item.setForeground(foreground)
                for col in (0, 3, 4):
                    widget = table.cellWidget(row, col)
                    if widget:
                        widget.setStyleSheet("QComboBox { background: #ECEFEE; color: #8A918D; border: 1px solid #D5DAD7; }" if ignored else "")
                if ignored:
                    continue
                selected += 1
                choice = table.cellWidget(row, 3).currentData()
                if choice and choice != "__create__":
                    conflicts.setdefault(choice, []).append(row + 1)
            duplicates = [f"{key} : lignes {', '.join(map(str, rows))}"
                          for key, rows in conflicts.items() if len(rows) > 1]
            status.setText("Doublons de destination à corriger — " + " ; ".join(duplicates) if duplicates
                           else f"{selected} / {table.rowCount()} champ(s) à importer")
            status.setStyleSheet("color: #bd2626; font-weight: bold;" if duplicates else "")
            return duplicates
        defaults = [(table.cellWidget(r, 0).currentIndex(), table.cellWidget(r, 3).currentIndex(),
                     table.cellWidget(r, 4).currentIndex()) for r in range(table.rowCount())]
        for row in range(table.rowCount()):
            table.cellWidget(row, 0).currentIndexChanged.connect(refresh)
            table.cellWidget(row, 3).currentIndexChanged.connect(refresh)
        refresh()
        controls = QHBoxLayout()
        all_btn = QPushButton("Tout importer")
        none_btn = QPushButton("Tout ignorer")
        reset_btn = QPushButton("Réinitialiser les propositions")
        all_btn.clicked.connect(lambda: [table.cellWidget(r, 0).setCurrentIndex(0) for r in range(table.rowCount())])
        none_btn.clicked.connect(lambda: [table.cellWidget(r, 0).setCurrentIndex(1) for r in range(table.rowCount())])
        def reset():
            for r, (action_index, dest_index, type_index) in enumerate(defaults):
                table.cellWidget(r, 0).setCurrentIndex(action_index)
                table.cellWidget(r, 3).setCurrentIndex(dest_index)
                table.cellWidget(r, 4).setCurrentIndex(type_index)
            refresh()
        reset_btn.clicked.connect(reset)
        controls.addWidget(all_btn)
        controls.addWidget(none_btn)
        controls.addWidget(reset_btn)
        preview_btn = QPushButton("Aperçu des données — fenêtre flottante")
        def show_preview():
            preview = QDialog(dialog)
            preview.setWindowTitle("Aperçu des données G-Skol (lecture seule)")
            preview.resize(950, 470)
            v = QVBoxLayout(preview)
            try:
                uri = self.mm3_source.resolve().as_uri() + "?mode=ro"
                with sqlite3.connect(uri, uri=True) as con:
                    columns = {r[1] for r in con.execute('PRAGMA table_info("records")')}
                    if not columns:
                        raise ValueError("La table des fiches est absente.")
                    query = 'SELECT * FROM "records"'
                    params = ()
                    if "collection_id" in columns:
                        query += ' WHERE "collection_id"=?'
                        params = (source_id,)
                    query += " LIMIT 10"
                    cur = con.execute(query, params)
                    headers = [desc[0] for desc in cur.description]
                    rows = cur.fetchall()
                view = QTableWidget(len(rows), len(headers), preview)
                view.setHorizontalHeaderLabels(headers)
                for i, values in enumerate(rows):
                    for j, value in enumerate(values):
                        display = "[donnée binaire]" if isinstance(value, bytes) else str(value if value is not None else "")
                        view.setItem(i, j, QTableWidgetItem(display[:300]))
                v.addWidget(view)
            except Exception as exc:
                v.addWidget(QLabel("Aperçu indisponible : " + str(exc)))
            done = QPushButton("Fermer")
            done.clicked.connect(preview.accept)
            v.addWidget(done)
            preview.exec()
        preview_btn.clicked.connect(show_preview)
        controls.addWidget(preview_btn)
        controls.addStretch(1)
        controls.addWidget(status)
        layout.removeWidget(status)
        layout.addLayout(controls)
        footer = QHBoxLayout()
        footer.addStretch(1)
        cancel = QPushButton("Annuler")
        cancel.clicked.connect(dialog.reject)
        footer.addWidget(cancel)
        validate = QPushButton("Valider la correspondance")
        def validate_mapping():
            if refresh():
                QMessageBox.warning(dialog, "Correspondances en conflit",
                                    "Corrigez les destinations utilisées plusieurs fois avant de valider.")
                return
            # Étape de vérification : ne rien écrire dans la collection ou le modèle.
            self._gskol_verified_mapping = [
                {"source_key": source[r][1],
                 "source_label": source[r][0],
                 "import": table.cellWidget(r, 0).currentIndex() == 0,
                 "destination": table.cellWidget(r, 3).currentData(),
                 "type": table.cellWidget(r, 4).currentData()}
                for r in range(table.rowCount())
            ]
            # 2.3.24.1 : fermer explicitement toutes les connexions SQLite avant
            # la suppression du dossier temporaire (Windows WinError 32).
            # 2.3.24, étape 1 : ouvrir une copie SQLite isolée en interne.
            # Aucun modèle n'est appliqué et aucune collection du Workspace n'est créée.
            try:
                source_path = Path(self.mm3_source)
                selected_index = self.mm3_collection_combo.currentIndex()
                selected = self.mm3_collections[selected_index]
                selected_id = int(selected.get("id") or 0)
                if selected_id <= 0:
                    raise ValueError("Identifiant de collection source invalide.")
                with tempfile.TemporaryDirectory(prefix="gskol_import_test_") as temp_dir:
                    temp_path = Path(temp_dir) / "collection_travail.coldb"
                    # backup() tient compte du journal WAL sans écrire dans la source.
                    with closing(sqlite3.connect(source_path.resolve().as_uri() + "?mode=ro", uri=True)) as src_db:
                        with closing(sqlite3.connect(str(temp_path))) as copy_db:
                            src_db.backup(copy_db)
                    # Ouvrir la copie avec le moteur habituel, sans fenêtre graphique.
                    copied_collections = CollectionManager(temp_path).inspect_collections()
                    copied = next((row for row in copied_collections
                                   if int(row.get("id") or 0) == selected_id), None)
                    if copied is None:
                        raise RuntimeError("La collection sélectionnée est introuvable dans la copie de travail.")
                    with closing(sqlite3.connect(str(temp_path))) as check_db:
                        integrity = check_db.execute("PRAGMA integrity_check").fetchone()
                    if not integrity or integrity[0] != "ok":
                        raise RuntimeError("La copie de travail a échoué au contrôle d'intégrité SQLite.")
            except Exception as exc:
                QMessageBox.critical(dialog, "Ouverture interne impossible",
                                     "La copie temporaire n'a pas pu être ouverte.\n\n" + str(exc))
                return
            # Étape 2 : copie autonome avec le moteur d'import déjà éprouvé.
            # Le modèle ne sera appliqué que dans une prochaine brique.
            confirmation = QMessageBox(dialog)
            confirmation.setIcon(QMessageBox.Icon.Question)
            confirmation.setWindowTitle("Étape 3 — copie indépendante")
            confirmation.setText("L’ouverture interne a réussi.\n\nCréer une nouvelle collection indépendante dans le Workspace ?")
            confirmation.setInformativeText("Elle recevra un nom disponible (par exemple « Nom - 2 »).\n\nLe modèle choisi ne sera pas encore appliqué.")
            yes_button = confirmation.addButton("Oui", QMessageBox.ButtonRole.YesRole)
            no_button = confirmation.addButton("Non", QMessageBox.ButtonRole.NoRole)
            confirmation.setDefaultButton(no_button)
            confirmation.exec()
            answer = (QMessageBox.StandardButton.Yes if confirmation.clickedButton() is yes_button
                      else QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes:
                dialog.accept()
                QMessageBox.information(self, "Ouverture interne vérifiée — étape 1",
                    "La copie temporaire a été vérifiée puis supprimée. Aucune collection n'a été créée.")
                return
            result = None
            try:
                manager = CollectionManager(source_path)
                result = manager.import_collection_to_folder(
                    selected_id, self._workspace_collections_folder(),
                    str(selected.get("name") or "Collection"),
                )
                final_path = Path(str(result["_database_path"]))
                rows = CollectionManager(final_path).inspect_collections()
                if not any(int(r.get("id") or 0) == selected_id for r in rows):
                    raise RuntimeError("Collection absente à la relecture.")
                with closing(sqlite3.connect(str(final_path))) as verify_db:
                    check = verify_db.execute("PRAGMA integrity_check").fetchone()
                if not check or check[0] != "ok":
                    raise RuntimeError("Échec du contrôle d'intégrité SQLite.")
            except Exception as exc:
                # Ne retirer que le fichier créé par CETTE tentative.
                if result is not None:
                    try:
                        Path(str(result["_database_path"])).unlink(missing_ok=True)
                    except Exception:
                        pass
                QMessageBox.critical(dialog, "Création de la copie impossible",
                    "La nouvelle collection n'a pas pu être vérifiée.\n\n" + str(exc))
                return
            # Étape 3 : audit des correspondances sur la copie réellement créée.
            # Aucune écriture du modèle : les champs/référentiels sont préservés.
            try:
                mapped = [entry for entry in self._gskol_verified_mapping if entry["import"]]
                assigned = [entry for entry in mapped if entry["destination"] not in ("", "__create__")]
                extra = [entry for entry in mapped if entry["destination"] == "__create__"]
                no_target = [entry for entry in mapped if entry["destination"] == ""]
                target_keys = {key for _label, key in destinations}
                unknown = [entry["source_label"] for entry in assigned
                           if entry["destination"] not in target_keys]
                if unknown:
                    raise ValueError("Destination absente du modèle : " + ", ".join(unknown[:8]))
                with closing(sqlite3.connect(final_path.resolve().as_uri() + "?mode=ro", uri=True)) as audit_db:
                    columns = {r[1] for r in audit_db.execute('PRAGMA table_info("records")')}
                    if "collection_id" in columns:
                        records = audit_db.execute('SELECT COUNT(*) FROM "records" WHERE collection_id=?',
                                                   (selected_id,)).fetchone()[0]
                    else:
                        records = audit_db.execute('SELECT COUNT(*) FROM "records"').fetchone()[0]
                audit_message = (f"\n\nVérification sur la copie : {records} fiche(s), "
                                 f"{len(assigned)} correspondance(s) vers le modèle, "
                                 f"{len(extra)} champ(s) supplémentaire(s), "
                                 f"{len(no_target)} champ(s) sans destination."
                                 "\nAucun modèle n'a été appliqué et aucune donnée n'a été modifiée.")
            except Exception as exc:
                audit_message = ("\n\nAttention : l'audit des correspondances n'a pas abouti : "
                                 + str(exc) + ". La copie est conservée sans modification.")
            # Étape 4 : appliquer la géométrie du modèle sur la COPIE uniquement.
            # Ne jamais écrire dans la source ni dans ModelesOfficiels.
            try:
                applied, original_fields = _apply_gskol_model_layout_to_copy(
                    final_path, selected_id, model_key, self._gskol_verified_mapping
                )
                with closing(sqlite3.connect(final_path.resolve().as_uri() + "?mode=ro", uri=True)) as final_db:
                    check = final_db.execute("PRAGMA integrity_check").fetchone()
                    count_after = final_db.execute(
                        'SELECT COUNT(*) FROM "records" WHERE collection_id=?', (selected_id,)
                    ).fetchone()[0]
                if not check or check[0] != "ok" or count_after != records:
                    raise RuntimeError("Contrôle après application du modèle non conforme.")
            except Exception as exc:
                # The newly created copy is not an import success; discard it.
                try:
                    final_path.unlink(missing_ok=True)
                except OSError:
                    pass
                QMessageBox.critical(dialog, "Correspondances à vérifier",
                    "Le transfert n'a pas été effectué. La copie de travail a été "
                    "supprimée ; la source et le modèle sont intacts.\n\n"
                    + str(exc) + "\n\n"
                    "Le tableau de correspondance reste ouvert pour corriger les choix.")
                return
            dialog.accept()
            QMessageBox.information(self, "Importation terminée",
                "La collection « " + str(result.get("name") or "Collection")
                + " » a bien été copiée sur le nouveau modèle.\n\n"
                f"{count_after} fiche(s) conservée(s).\n"
                "La nouvelle collection est disponible dans « Ouvrir une collection ».\n\n"
                "La collection source et le modèle sont inchangés.\n"
                "Les référentiels supplémentaires peuvent être complétés "
                "en une seule opération lors de la fermeture de la fiche.")
            return
            QMessageBox.information(self, "Copie indépendante vérifiée — étape 3",
                "Collection : « " + str(result.get("name") or "Collection") + " »\n\n"
                "Fichier : " + str(final_path) + "\n\n"
                "La source et les modèles sont inchangés. "
                "Le modèle choisi n'a PAS encore été appliqué." + audit_message)
        validate.clicked.connect(validate_mapping)
        footer.addWidget(validate)
        layout.addLayout(footer)
        dialog.exec()

    def _import_mm3_collection(self) -> None:
        if getattr(self, "import_model_mode", "free") == "model":
            self._preview_mm3_model_mapping()
            return
        if self.mm3_source is None:
            return
        index = self.mm3_collection_combo.currentIndex()
        if not (0 <= index < len(self.mm3_collections)):
            return

        source_row = self.mm3_collections[index]
        source_name = str(source_row.get("name") or "Collection")
        source_id = int(source_row.get("id") or 0)
        if source_id <= 0:
            QMessageBox.warning(
                self,
                ("Import nicht möglich" if self.language.lower().startswith("de") else "Import impossible"),
                ("Die ausgewählte Sammlung hat keine gültige G-Skol-Kennung." if self.language.lower().startswith("de") else ("The selected collection does not have a valid G-Skol identifier." if self.language.lower().startswith("en") else "La collection sélectionnée ne possède pas d'identifiant G-Skol valide.")),
            )
            return

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle(("G-Skol-Sammlung importieren" if self.language.lower().startswith("de") else ("Import a G-Skol collection" if self.language.lower().startswith("en") else "Importer une collection G-Skol")))
        box.setText(
            (f"Sammlung „{source_name}“ in diese G-Skol-Umgebung importieren?" if self.language.lower().startswith("de") else (f"Import the collection ‘{source_name}’ into this G-Skol environment?" if self.language.lower().startswith("en") else f"Importer la collection « {source_name} » dans cet environnement G-Skol ?"))
        )
        box.setInformativeText(
            ("The source file will never be modified.\n\nNo content comparison is performed. If the name already exists, "
             "the new collection will be named ‘Name - 2’, then ‘Name - 3’, etc.")
            if self.language.lower().startswith("en") else
            ("Die Quelldatei wird niemals verändert.\n\nEs erfolgt kein Inhaltsvergleich. Ist der Name bereits vorhanden, "
             "erhält die neue Sammlung den Namen „Name - 2“, dann „Name - 3“ usw.")
            if self.language.lower().startswith("de") else
            ("Le fichier source ne sera jamais modifié.\n\nAucune comparaison de contenu n'est effectuée. Si le nom existe déjà, "
             "la nouvelle collection sera nommée « Nom - 2 », puis « Nom - 3 », etc.")
        )
        yes = box.addButton(("Importieren" if self.language.lower().startswith("de") else ("Import" if self.language.lower().startswith("en") else "Importer")), QMessageBox.ButtonRole.AcceptRole)
        no = box.addButton(("Abbrechen" if self.language.lower().startswith("de") else ("Cancel" if self.language.lower().startswith("en") else "Annuler")), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(yes)
        box.exec()
        if box.clickedButton() is not yes:
            return

        progress = QProgressDialog(
            ("G-Skol-Sammlung wird importiert…" if self.language.lower().startswith("de") else ("Importing G-Skol collection…" if self.language.lower().startswith("en") else "Import de la collection G-Skol en cours…")),
            "",
            0,
            0,
            self,
        )
        progress.setWindowTitle(("G-Skol-Import" if self.language.lower().startswith("de") else ("G-Skol import" if self.language.lower().startswith("en") else "Import G-Skol")))
        progress.setCancelButton(None)
        progress.setMinimumDuration(0)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.show()
        QApplication.processEvents()

        try:
            manager = CollectionManager(self.mm3_source)
            result = manager.import_collection_to_folder(
                source_id,
                self._workspace_collections_folder(),
                source_name,
            )
        except Exception as exc:
            progress.close()
            QMessageBox.critical(
                self,
                (("G-Skol-Import fehlgeschlagen" if self.language.lower().startswith("de") else ("G-Skol import failed" if self.language.lower().startswith("en") else "Import G-Skol impossible"))),
                str(exc),
            )
            return

        progress.close()
        final_name = str(result.get("name") or source_name)
        final_path = str(result.get("_database_path") or "")
        QMessageBox.information(
            self,
            (("G-Skol-Import abgeschlossen" if self.language.lower().startswith("de") else ("G-Skol import complete" if self.language.lower().startswith("en") else "Import G-Skol terminé"))),
            ((f"The collection ‘{final_name}’ was imported successfully.\n\nFile: {final_path}\n\n"
              "It will appear under ‘Open a collection’." )
             if self.language.lower().startswith("en") else
             (f"Die Sammlung „{final_name}“ wurde erfolgreich importiert.\n\nDatei: {final_path}\n\n"
              "Sie erscheint unter „Sammlung öffnen“.")
             if self.language.lower().startswith("de") else
             (f"La collection « {final_name} » a été importée avec succès.\n\nFichier : {final_path}\n\n"
              "Elle apparaîtra dans « Ouvrir une collection »."))
        )
        # 11.7.70.11 — après confirmation, proposer Fermer et éviter
        # qu'Entrée relance l'import.
        self.mm3_import_btn.setDefault(False)
        self.mm3_close_btn.setDefault(True)
        self.mm3_close_btn.setFocus(Qt.FocusReason.OtherFocusReason)

    def _workspace_collections_folder(self) -> Path:
        """Use the workspace selected by the application for portable or installed G-Skol."""
        from core.paths import WORKSPACE
        folder = Path(WORKSPACE) / "Collections"
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    @staticmethod
    def _safe_filename(name: str) -> str:
        forbidden = '<>:"/\\\\|?*'
        clean = "".join("_" if c in forbidden else c for c in str(name).strip()).rstrip(" .")
        return clean or "Collection importée"

    def _start_real_import(self) -> None:
        if self.access_source is None or self.selected_access_table is None or not self.access_field_mapping:
            return

        imported_mapping = [m for m in self.access_field_mapping if m.get("action") == "Importer"]
        if not imported_mapping:
            QMessageBox.warning(self, "Import impossible", "Aucun champ n'est prévu pour l'import.")
            return

        rows = self.selected_access_table.get("rows")
        dialog = AccessImportDestinationDialog(
            str(self.selected_access_table.get("name", "")),
            rows if isinstance(rows, int) else None,
            len(imported_mapping),
            self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        name = dialog.collection_name()
        folder = self._workspace_collections_folder()
        destination = folder / (self._safe_filename(name) + ".coldb")
        if destination.exists():
            QMessageBox.warning(
                self, tr("Nom déjà utilisé", self.language),
                tr("Le fichier « {name} » existe déjà dans le dossier des collections. Choisissez un autre nom.", self.language).format(name=destination.name)
            )
            return

        # 11.7.67 — confirmation volontaire : aucun bouton par défaut et
        # la touche Entrée n'a aucun effet. Un clic explicite sur « Oui » est requis.
        confirm = ExplicitImportConfirmDialog(name, rows if isinstance(rows, int) else None, self, self.language)
        if confirm.exec() != QDialog.DialogCode.Accepted:
            return

        source_display = self.access_source.stem if self.access_source else "Access"
        progress = QProgressDialog(
            tr("Import de la base « {source} » en cours…\nCréation de la collection et copie des fiches. Merci de patienter.", self.language).format(source=source_display),
            "",
            0,
            0,
            self,
        )
        progress.setWindowTitle(tr("Import en cours", self.language))
        progress.setCancelButton(None)
        progress.setWindowModality(Qt.WindowModality.ApplicationModal)
        progress.setMinimumDuration(0)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.show()

        self.real_import_btn.setEnabled(False)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        QApplication.processEvents()
        try:
            result = self._perform_real_import(destination, name, imported_mapping)
        except Exception as exc:
            try:
                if destination.exists():
                    destination.unlink()
            except Exception:
                pass
            progress.close()
            QMessageBox.critical(
                self, "Import interrompu",
                "L'import n'a pas été conservé. La base Access source est intacte.\n\n"
                + str(exc)
            )
            self.real_import_btn.setEnabled(True)
            return
        finally:
            QApplication.restoreOverrideCursor()

        progress.close()
        self.real_import_btn.setEnabled(True)
        order_mode = str(result.get("record_order_mode") or "source")
        order_summary = tr(
            "Tri Access du formulaire/requête conservé."
            if order_mode in {"form_order", "query_order"}
            else (
                "Ordre historique Access (AutoNumber) conservé."
                if order_mode == "autonumber"
                else "Ordre source Access conservé."
            ),
            self.language,
        )
        self.next_step_label.setText(
            tr("✓ Import terminé : {records} fiche(s) créées dans « {name} ». {fields} champ(s) importés ; {values} valeur(s) de listes simples ; {refs} référentiel(s) tabulaire(s) relié(s).", self.language).format(
                records=result['records'], name=name, fields=result['fields'],
                values=result.get('referential_values', 0), refs=result.get('structured_tables', 0)
            )
        )
        _timings = result.get("timings") or {}
        _timing_order = [
            "Préparation collection / modèle", "Lecture groupée Access",
            "Création fiches + valeurs + photos", "dont traitement photos",
            "Listes simples", "Référentiels liés + report dans les fiches",
            "dont écriture tables liées", "dont report valeurs reliées", "TOTAL",
        ]
        _timing_lines = []
        for _label in _timing_order:
            if _label in _timings:
                _timing_lines.append(f"{tr(_label, self.language)} : {float(_timings[_label]):.2f} s")
        _timing_text = "\n".join(_timing_lines)
        _access_diag = result.get("access_read_diagnostic") or {}
        _access_diag_lines = []
        if _access_diag:
            if "bridge_seconds" in _access_diag:
                _access_diag_lines.append(f"{tr('Pont Access/DAO (processus complet)', self.language)} : {float(_access_diag['bridge_seconds']):.2f} s")
            if "access_open_seconds" in _access_diag:
                _access_diag_lines.append(f"{tr('dont ouverture de la base Access', self.language)} : {float(_access_diag['access_open_seconds']):.2f} s")
            for _table_diag in _access_diag.get("tables", []) or []:
                _tname = str(_table_diag.get("name") or "?")
                _tseconds = float(_table_diag.get("seconds") or 0.0)
                _trows = int(_table_diag.get("rows") or 0)
                _tbseconds = float(_table_diag.get("binary_seconds") or 0.0)
                _tbcount = int(_table_diag.get("binary_count") or 0)
                _tbmb = float(_table_diag.get("binary_bytes") or 0) / (1024.0 * 1024.0)
                _line = tr("Table {name} : {seconds:.2f} s — {rows} ligne(s)", self.language).format(name=_tname, seconds=_tseconds, rows=_trows)
                if _tbcount:
                    _line += tr(" — binaires : {seconds:.2f} s / {count} objet(s) / {mb:.1f} Mo", self.language).format(seconds=_tbseconds, count=_tbcount, mb=_tbmb)
                _access_diag_lines.append(_line)
                _field_diags = list(_table_diag.get("fields", []) or [])
                _field_diags.sort(key=lambda item: float(item.get("seconds") or 0.0), reverse=True)
                _field_limit = len(_field_diags) if len(_field_diags) <= 20 else 15
                for _fd in _field_diags[:_field_limit]:
                    _access_diag_lines.append(tr("   • {name} : {seconds:.2f} s — {reads} lecture(s) — type DAO {type}", self.language).format(
                        name=str(_fd.get("name") or "?"), seconds=float(_fd.get("seconds") or 0.0),
                        reads=int(_fd.get("reads") or 0), type=str(_fd.get("dao_type") or "?")))
            if "xml_parse_seconds" in _access_diag:
                _access_diag_lines.append(f"{tr('Analyse du résultat XML', self.language)} : {float(_access_diag['xml_parse_seconds']):.2f} s")
            if "python_build_seconds" in _access_diag:
                _access_diag_lines.append(f"{tr('Reconstruction des données côté G-Skol', self.language)} : {float(_access_diag['python_build_seconds']):.2f} s")
        _access_diag_text = "\n".join(_access_diag_lines)
        _debug = result.get("structured_debug", []) or [tr("Aucun groupe détecté", self.language)]
        report = (
            tr("Import terminé avec succès.\n\n", self.language)
            + tr("Collection : {name}\n", self.language).format(name=name)
            + tr("Fiches G-Skol créées : {count}\n", self.language).format(count=result['records'])
            + tr("Champs importés : {count}\n", self.language).format(count=result['fields'])
            + tr("Valeurs de listes simples : {count}\n", self.language).format(count=result.get('referential_values', 0))
            + tr("Référentiels tabulaires reconnus : {count}\n", self.language).format(count=result.get('structured_tables', 0))
            + tr("Liaisons Maître / Relié à créées : {count}\n", self.language).format(count=result.get('structured_links', 0))
            + tr("Valeurs reliées reportées dans les fiches : {count}\n", self.language).format(count=result.get('linked_backfilled', 0))
            + tr("Ordre des fiches : {order}\n\n", self.language).format(order=order_summary)
            + tr("Diagnostic Maître/Reliés :\n", self.language) + "\n".join(_debug) + "\n\n"
            + tr("Chronométrage diagnostic :\n", self.language) + _timing_text + "\n\n"
            + ((tr("Détail de la lecture Access :\n", self.language) + _access_diag_text + "\n\n") if _access_diag_text else "")
            + tr("La nouvelle collection est désormais disponible dans la liste des collections.\nDepuis l'écran d'accueil, cliquez sur « Ouvrir une collection » pour l'ouvrir.\n\n", self.language)
            + tr("Les fiches ont reçu leur propre numérotation G-Skol de 1 à {count}. Le N° Access, s'il a été conservé, reste un champ ordinaire.\n\n", self.language).format(count=result['records'])
            + tr("Source(s) Photo détectée(s) : {count}.\n", self.language).format(count=result.get('photo_sources', 0))
            + tr("Photos Access importées dans les cadres Photo G-Skol : {count}.\n", self.language).format(count=result.get('photos_imported', 0))
            + tr("Photos binaires non reconnues : {count}.", self.language).format(count=result.get('photos_unreadable', 0))
        )
        if result.get("first_photo_signature"):
            report += tr("\nPremier objet illisible : {signature}", self.language).format(signature=str(result.get("first_photo_signature") or ""))
        QMessageBox.information(self, tr("Import terminé", self.language), report)

    @staticmethod
    def _format_imported_value(raw, target_label: str) -> str:
        if raw is None:
            return ""
        if isinstance(raw, bool):
            return "1" if raw else "0"
        value = str(raw)

        # Hyperlink Access : DisplayText#Address#SubAddress#ScreenTip.
        # MM3 stores the actual address, not Access' technical # separators.
        if "#" in value:
            parts = value.split("#")
            if len(parts) >= 3:
                address = str(parts[1] or "").strip()
                if address.casefold().startswith(("http://", "https://")):
                    subaddress = str(parts[2] or "").strip()
                    return address + (("#" + subaddress) if subaddress else "")

        normalized = str(target_label or "").strip().casefold()
        if normalized in {"prix", "price", "prix unitaire"}:
            try:
                number = float(value.replace(" ", "").replace(",", "."))
                return f"{number:.2f}"
            except (TypeError, ValueError):
                return value
        return value

    def _structured_reference_candidates(self, mapping: list[dict]) -> list[dict]:
        """Repère les tables Access servant probablement de référentiels structurés."""
        if not self.access_structure or not self.selected_access_table:
            return []
        source_table_name = str(self.selected_access_table.get("name") or "")
        mapped = {
            str(item.get("source") or "").casefold(): item
            for item in mapping
            if str(item.get("source") or "").strip()
        }
        candidates = []
        for table in self.access_structure.get("tables", []) or []:
            table_name = str(table.get("name") or "")
            if not table_name or table_name.casefold() == source_table_name.casefold():
                continue
            fields = [str(f.get("name") or "") for f in table.get("fields", []) or []]
            common = [f for f in fields if f.casefold() in mapped]
            if not common:
                continue

            # Les relations Access explicites sont prioritaires.
            relation_masters = []
            for f in self.selected_access_table.get("fields", []) or []:
                if str(f.get("relation_table") or "").casefold() == table_name.casefold():
                    relation_masters.append(str(f.get("name") or ""))

            preferred = relation_masters[:]
            table_cf = table_name.casefold()
            if "ima" in table_cf:
                preferred += ["Nom"]
            if "gisement" in table_cf:
                preferred += ["Site1", "Site"]
            preferred += common

            master = next(
                (name for name in preferred if name and name.casefold() in mapped
                 and any(name.casefold() == f.casefold() for f in fields)),
                None,
            )
            if not master:
                continue

            # Il faut au moins un champ relié commun en plus du maître pour
            # conclure automatiquement à un référentiel structuré.
            linked = [f for f in common if f.casefold() != master.casefold()]
            if not linked:
                continue
            candidates.append({
                "table": table,
                "master": master,
                "linked": linked,
                "recognized": bool(relation_masters) or "ima" in table_cf or "gisement" in table_cf,
            })
        return candidates

    @staticmethod
    def _read_access_bundle(path: Path, requests: list[dict]) -> dict[str, list[dict]]:
        """Lit toutes les tables nécessaires à l'import en une seule ouverture Access.

        Cette phase n'utilise pas PowerShell : elle passe par le moteur ADO
        de Windows via un petit pont VBScript statique. L'import complet ne
        déclenche donc plus une commande PowerShell par table/référentiel.
        """
        if os.name != "nt":
            raise RuntimeError("L'import Access doit être exécuté sous Windows.")

        clean_requests = []
        for request in requests or []:
            table = str(request.get("table") or "").strip()
            columns = [str(c) for c in request.get("columns", []) if str(c).strip()]
            if table and columns:
                clean_requests.append({
                    "table": table,
                    "columns": list(dict.fromkeys(columns)),
                    "order_by": str(request.get("order_by") or "").strip(),
                })
        if not clean_requests:
            return {}

        bridge_path = Path(__file__).resolve().parent / "access_data_bridge.vbs"
        if not bridge_path.exists():
            raise RuntimeError(f"Lecteur Access introuvable : {bridge_path.name}")

        with tempfile.TemporaryDirectory(prefix="mm3_access_") as temp_dir:
            temp = Path(temp_dir)
            request_path = temp / "request.xml"
            output_path = temp / "result.xml"

            root = ET.Element("requests")
            for request in clean_requests:
                table_node = ET.SubElement(root, "table")
                table_node.set("name", str(request["table"]))
                order_by = str(request.get("order_by") or "").strip()
                if order_by:
                    table_node.set("order_by", order_by)
                for column in request["columns"]:
                    column_node = ET.SubElement(table_node, "column")
                    column_node.set("name", str(column))
            ET.ElementTree(root).write(
                request_path, encoding="utf-8", xml_declaration=True
            )

            _bridge_t0 = time.perf_counter()
            proc = subprocess.Popen(
                [
                    "cscript.exe",
                    "//Nologo",
                    str(bridge_path),
                    str(path),
                    str(request_path),
                    str(output_path),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            deadline = time.monotonic() + 300
            while proc.poll() is None:
                QApplication.processEvents()
                if time.monotonic() > deadline:
                    proc.kill()
                    raise RuntimeError("La lecture Access a dépassé 5 minutes.")
                time.sleep(0.05)
            stdout_b, stderr_b = proc.communicate()
            _bridge_seconds = time.perf_counter() - _bridge_t0
            stdout = stdout_b.decode("mbcs", errors="replace").strip()
            stderr = stderr_b.decode("mbcs", errors="replace").strip()
            if proc.returncode != 0 or not output_path.exists():
                raise RuntimeError(
                    stderr or stdout or
                    "Le moteur Access n'a pas renvoyé les données demandées."
                )

            try:
                _xml_t0 = time.perf_counter()
                result_root = ET.parse(output_path).getroot()
                _xml_parse_seconds = time.perf_counter() - _xml_t0
            except Exception as exc:
                raise RuntimeError(f"Données Access illisibles : {exc}") from exc

            _build_t0 = time.perf_counter()
            result: dict[str, list[dict]] = {}
            _table_diagnostics = []
            for table_node in result_root.findall("table"):
                table_name = str(table_node.get("name") or "")
                def _diag_float(attr: str) -> float:
                    try:
                        return float(str(table_node.get(attr) or "0").replace(",", "."))
                    except Exception:
                        return 0.0
                def _diag_int(attr: str) -> int:
                    try:
                        return int(float(str(table_node.get(attr) or "0").replace(",", ".")))
                    except Exception:
                        return 0
                _field_diagnostics = []
                for _field_diag_node in table_node.findall("field_diag"):
                    try:
                        _field_seconds = float(str(_field_diag_node.get("seconds") or "0").replace(",", "."))
                    except Exception:
                        _field_seconds = 0.0
                    try:
                        _field_reads = int(float(str(_field_diag_node.get("reads") or "0").replace(",", ".")))
                    except Exception:
                        _field_reads = 0
                    _field_diagnostics.append({
                        "name": str(_field_diag_node.get("name") or ""),
                        "seconds": _field_seconds,
                        "reads": _field_reads,
                        "dao_type": str(_field_diag_node.get("dao_type") or ""),
                    })
                _table_diagnostics.append({
                    "name": table_name,
                    "rows": _diag_int("rows"),
                    "seconds": _diag_float("seconds"),
                    "binary_seconds": _diag_float("binary_seconds"),
                    "binary_count": _diag_int("binary_count"),
                    "binary_bytes": _diag_int("binary_bytes"),
                    "fields": _field_diagnostics,
                })
                rows: list[dict] = []
                for row_node in table_node.findall("row"):
                    row = {}
                    for cell in row_node.findall("cell"):
                        key = str(cell.get("name") or "")
                        binary_name = str(cell.get("binary_file") or "").strip()
                        if binary_name:
                            binary_path = temp / binary_name
                            try:
                                row[key] = binary_path.read_bytes()
                            except Exception:
                                row[key] = b""
                        else:
                            row[key] = cell.text or ""
                    rows.append(row)
                result[table_name] = rows
            _python_build_seconds = time.perf_counter() - _build_t0
            try:
                _open_seconds = float(str(result_root.get("open_seconds") or "0").replace(",", "."))
            except Exception:
                _open_seconds = 0.0
            result["__mm3_diagnostic__"] = {
                "bridge_seconds": _bridge_seconds,
                "access_open_seconds": _open_seconds,
                "xml_parse_seconds": _xml_parse_seconds,
                "python_build_seconds": _python_build_seconds,
                "tables": _table_diagnostics,
            }
            return result

    @staticmethod
    def _synchronise_template_reference_records(destination: Path, collection_id: int) -> int:
        """Complète les champs reliés d'un modèle à partir de ses référentiels.

        Comparaison insensible à la casse et aux accents, mais les valeurs
        canoniques des référentiels ne sont jamais transformées.
        """
        def normalise(value: object) -> str:
            text = unicodedata.normalize("NFKD", str(value or "").strip())
            return "".join(c for c in text if not unicodedata.combining(c)).casefold()

        updated = 0
        with sqlite3.connect(destination) as con:
            # Compatibilité avec les collections créées par des parcours d'import
            # qui n'ont pas encore matérialisé cette table facultative.
            RecordManager._ensure_custom_values_table(con)
            columns = {str(r[1]) for r in con.execute("PRAGMA table_info(records)")}
            links = con.execute(
                "SELECT master_key, linked_key FROM collection_field_links WHERE collection_id=?",
                (collection_id,),
            ).fetchall()
            if not links:
                return 0
            masters = {}
            for master_key, linked_key in links:
                masters.setdefault(str(master_key), set()).add(str(linked_key))
            for master_key, linked_keys in masters.items():
                refs = con.execute(
                    """SELECT master_value, linked_key, linked_value
                       FROM collection_reference_data
                       WHERE collection_id=? AND master_key=?""",
                    (collection_id, master_key),
                ).fetchall()
                by_name = {}
                for master_value, linked_key, linked_value in refs:
                    marker = normalise(master_value)
                    if not marker or str(linked_key) not in linked_keys:
                        continue
                    group = by_name.setdefault(marker, {"canonical": str(master_value), "values": {}})
                    if str(linked_value or "").strip():
                        group["values"].setdefault(str(linked_key), str(linked_value))
                if not by_name:
                    continue
                if master_key in columns:
                    record_rows = con.execute(
                        f'SELECT id, "{master_key}" FROM records WHERE collection_id=?',
                        (collection_id,),
                    ).fetchall()
                else:
                    record_rows = con.execute(
                        """SELECT r.id, cv.value FROM records r
                           JOIN record_custom_values cv ON cv.record_id=r.id
                           WHERE r.collection_id=? AND cv.field_key=?""",
                        (collection_id, master_key),
                    ).fetchall()
                for record_id, raw_value in record_rows:
                    group = by_name.get(normalise(raw_value))
                    if group is None:
                        continue
                    # Use the exact spelling supplied by the user's referential
                    # (e.g. SIDERITE, never SIDÉRITE).
                    canonical = group["canonical"]
                    if str(raw_value or "") != canonical:
                        if master_key in columns:
                            con.execute(f'UPDATE records SET "{master_key}"=? WHERE id=?', (canonical, record_id))
                        else:
                            con.execute(
                                "UPDATE record_custom_values SET value=? WHERE record_id=? AND field_key=?",
                                (canonical, record_id, master_key),
                            )
                    for linked_key, value in group["values"].items():
                        if linked_key in columns:
                            cur = con.execute(
                                f"""UPDATE records SET "{linked_key}"=? WHERE id=?
                                    AND TRIM(COALESCE("{linked_key}",''))='' """,
                                (value, record_id),
                            )
                        else:
                            cur = con.execute(
                                """INSERT INTO record_custom_values(record_id,field_key,value)
                                   VALUES (?,?,?) ON CONFLICT(record_id,field_key)
                                   DO UPDATE SET value=excluded.value
                                   WHERE TRIM(COALESCE(value,''))=''""",
                                (record_id, linked_key, value),
                            )
                        updated += max(0, cur.rowcount)
        return updated

    @staticmethod
    def _apply_imported_reference_to_records(
        destination: Path,
        master_key: str,
        linked_keys: list[str],
        reference_rows: list[dict[str, str]],
    ) -> int:
        """Synchronise les champs reliés après import, natifs ET personnalisés.

        Les valeurs explicitement présentes dans les fiches restent prioritaires.
        La synchronisation est réalisée en base, sans ouvrir les fiches Qt.
        """
        master_key = str(master_key or "")
        linked_keys = list(dict.fromkeys(str(k) for k in linked_keys if str(k)))
        if not master_key or not linked_keys or not reference_rows:
            return 0

        canonical: dict[str, dict[str, str]] = {}
        for row in reference_rows:
            master_value = str(row.get(master_key, "") or "").strip()
            if not master_value:
                continue
            bucket = canonical.setdefault(master_value.casefold(), {})
            for key in linked_keys:
                value = str(row.get(key, "") or "").strip()
                if value and not bucket.get(key):
                    bucket[key] = value
        if not canonical:
            return 0

        with sqlite3.connect(destination) as connection:
            columns = {
                str(row[1]) for row in connection.execute("PRAGMA table_info(records)")
            }
            if master_key in columns:
                master_rows = connection.execute(
                    f"""SELECT id, COALESCE("{master_key}", '') FROM records
                        WHERE TRIM(COALESCE("{master_key}", '')) <> ''"""
                ).fetchall()
            else:
                master_rows = connection.execute(
                    """SELECT r.id, COALESCE(cv.value,'') FROM records r
                       JOIN record_custom_values cv ON cv.record_id=r.id
                       WHERE cv.field_key=? AND TRIM(COALESCE(cv.value,''))<>''""",
                    (master_key,),
                ).fetchall()

            updated = 0
            for record_id, raw_master in master_rows:
                values = canonical.get(str(raw_master or "").strip().casefold())
                if not values:
                    continue
                for linked_key, value in values.items():
                    if linked_key in columns:
                        cursor = connection.execute(
                            f"""UPDATE records SET "{linked_key}"=? WHERE id=?
                                AND TRIM(COALESCE("{linked_key}", ''))=''""",
                            (value, int(record_id)),
                        )
                        updated += max(0, cursor.rowcount)
                    else:
                        cursor = connection.execute(
                            """INSERT INTO record_custom_values(record_id,field_key,value)
                               VALUES (?,?,?)
                               ON CONFLICT(record_id,field_key) DO UPDATE SET
                               value=excluded.value WHERE TRIM(COALESCE(value,''))=''""",
                            (int(record_id), linked_key, value),
                        )
                        updated += max(0, cursor.rowcount)
            return updated


    @staticmethod
    def _read_ole_lp_ansi(data: bytes, pos: int) -> tuple[str, int] | None:
        """Lit une LengthPrefixedAnsiString OLE1."""
        if pos < 0 or pos + 4 > len(data):
            return None
        length = struct.unpack_from("<I", data, pos)[0]
        pos += 4
        if length == 0:
            return "", pos
        if length > 65536 or pos + length > len(data):
            return None
        raw = data[pos:pos + length]
        text = raw.rstrip(b"\x00").decode("latin-1", errors="replace")
        return text, pos + length

    @staticmethod
    def _dib_to_bmp(dib: bytes) -> bytes | None:
        """Ajoute l'en-tête de fichier BMP manquant à un DIB valide."""
        if len(dib) < 12:
            return None
        try:
            header_size = struct.unpack_from("<I", dib, 0)[0]
        except struct.error:
            return None

        if header_size == 12:
            if len(dib) < 12:
                return None
            width, height, planes, bpp = struct.unpack_from("<HHHH", dib, 4)
            palette_entry_size = 3
            colors_used = 0
            compression = 0
        elif header_size >= 40 and len(dib) >= 40:
            width, height, planes, bpp, compression = struct.unpack_from("<iiHHI", dib, 4)
            colors_used = struct.unpack_from("<I", dib, 32)[0]
            palette_entry_size = 4
        else:
            return None

        if (
            planes != 1
            or not (1 <= abs(int(width)) <= 20000)
            or not (1 <= abs(int(height)) <= 20000)
            or int(bpp) not in (1, 4, 8, 16, 24, 32)
        ):
            return None

        palette_entries = int(colors_used or 0)
        if not palette_entries and int(bpp) <= 8:
            palette_entries = 1 << int(bpp)

        masks_size = 0
        if header_size == 40 and int(compression) in (3, 6):
            masks_size = 16 if int(compression) == 6 else 12

        pixel_offset = int(header_size) + masks_size + palette_entries * palette_entry_size
        if pixel_offset > len(dib):
            return None

        bmp_size = 14 + len(dib)
        file_header = b"BM" + struct.pack("<IHHI", bmp_size, 0, 0, 14 + pixel_offset)
        return file_header + dib

    @classmethod
    def _decode_image_payload(cls, payload: bytes) -> tuple[bytes | None, str]:
        """Reconnaît une image brute ou un DIB à l'intérieur d'un payload."""
        if not payload:
            return None, ""

        signatures = (
            (b"\xff\xd8\xff", "jpg"),
            (b"\x89PNG\r\n\x1a\n", "png"),
            (b"GIF87a", "gif"),
            (b"GIF89a", "gif"),
        )
        candidates = []
        for signature, fmt in signatures:
            pos = payload.find(signature)
            if pos >= 0:
                candidates.append((pos, fmt))
        if candidates:
            pos, fmt = min(candidates, key=lambda item: item[0])
            image = payload[pos:]
            if fmt == "jpg":
                end_marker = image.find(b"\xff\xd9", 2)
                if end_marker >= 0:
                    image = image[:end_marker + 2]
            return bytes(image), fmt

        # BMP complet.
        search_from = 0
        while True:
            pos = payload.find(b"BM", search_from)
            if pos < 0:
                break
            search_from = pos + 2
            if pos + 18 > len(payload):
                continue
            try:
                file_size = struct.unpack_from("<I", payload, pos + 2)[0]
                pixel_offset = struct.unpack_from("<I", payload, pos + 10)[0]
                dib_header = struct.unpack_from("<I", payload, pos + 14)[0]
            except struct.error:
                continue
            if (
                dib_header not in (12, 40, 52, 56, 108, 124)
                or pixel_offset < 14 + dib_header
                or pixel_offset > len(payload) - pos
            ):
                continue
            remaining = len(payload) - pos
            image_len = int(file_size) if 18 <= int(file_size) <= remaining else remaining
            return bytes(payload[pos:pos + image_len]), "bmp"

        # DIB sans en-tête BMP.
        marker = b"\x28\x00\x00\x00"
        search_from = 0
        while True:
            pos = payload.find(marker, search_from)
            if pos < 0:
                break
            search_from = pos + 1
            bmp = cls._dib_to_bmp(payload[pos:])
            if bmp:
                return bmp, "bmp"

        return None, ""

    @classmethod
    def _decode_access_ole1(cls, blob: bytes) -> tuple[bytes | None, str, str]:
        """Décapsule l'en-tête Access puis l'EmbeddedObject OLE1."""
        if len(blob) < 12:
            return None, "", ""
        try:
            signature = struct.unpack_from("<H", blob, 0)[0]
            access_header_size = struct.unpack_from("<H", blob, 2)[0]
        except struct.error:
            return None, "", ""
        if signature != 0x1C15 or access_header_size < 4 or access_header_size >= len(blob):
            return None, "", ""

        access_class = ""
        # L'en-tête Access indique classOffset à l'offset 12 sur les objets observés.
        try:
            class_len = struct.unpack_from("<H", blob, 8)[0]
            class_offset = struct.unpack_from("<H", blob, 12)[0]
            if class_len and class_offset + class_len <= access_header_size:
                access_class = (
                    blob[class_offset:class_offset + class_len]
                    .rstrip(b"\x00").decode("latin-1", errors="replace")
                )
        except Exception:
            pass

        pos = int(access_header_size)
        if pos + 8 > len(blob):
            return None, "", access_class

        try:
            _ole_version, format_id = struct.unpack_from("<II", blob, pos)
        except struct.error:
            return None, "", access_class
        pos += 8
        if format_id not in (1, 2):
            return None, "", access_class

        parsed = cls._read_ole_lp_ansi(blob, pos)
        if parsed is None:
            return None, "", access_class
        ole_class, pos = parsed
        for _ in range(2):  # TopicName, ItemName
            parsed = cls._read_ole_lp_ansi(blob, pos)
            if parsed is None:
                return None, ole_class, access_class
            _ignored, pos = parsed

        if format_id != 2 or pos + 4 > len(blob):
            return None, ole_class, access_class

        native_size = struct.unpack_from("<I", blob, pos)[0]
        pos += 4
        if native_size > len(blob) - pos:
            return None, ole_class, access_class

        native = blob[pos:pos + native_size]
        pos += native_size

        # D'abord les données natives.
        image, fmt = cls._decode_image_payload(native)
        if image:
            return image, fmt, f"{access_class}/{ole_class}".strip("/")

        # Puis la Presentation OLE1 : Photo Editor stocke souvent l'aperçu
        # affichable ici, même si NativeData est dans son format propre.
        if pos + 8 <= len(blob):
            try:
                _pres_ole_version, pres_format = struct.unpack_from("<II", blob, pos)
            except struct.error:
                pres_format = -1
            pos += 8

            if pres_format == 5:
                parsed = cls._read_ole_lp_ansi(blob, pos)
                if parsed is not None:
                    pres_class, pos = parsed
                    if pos + 12 <= len(blob):
                        # StandardPresentationObject: Width + Height.
                        pos += 8
                        data_size = struct.unpack_from("<I", blob, pos)[0]
                        pos += 4
                        if data_size <= len(blob) - pos:
                            presentation = blob[pos:pos + data_size]
                            if pres_class.upper() == "DIB":
                                bmp = cls._dib_to_bmp(presentation)
                                if bmp:
                                    return bmp, "bmp", f"{access_class}/{ole_class}/DIB".strip("/")
                            image, fmt = cls._decode_image_payload(presentation)
                            if image:
                                return image, fmt, (
                                    f"{access_class}/{ole_class}/{pres_class}".strip("/")
                                )

        return None, "", f"{access_class}/{ole_class}".strip("/")

    @classmethod
    def _decode_access_photo(cls, raw) -> tuple[bytes | None, str]:
        """Décode image directe, DIB ou objet OLE Access."""
        if isinstance(raw, (bytes, bytearray, memoryview)):
            blob = bytes(raw)
        else:
            text = str(raw or "")
            if not text.startswith("__MM3B64__"):
                return None, ""
            try:
                blob = base64.b64decode(text[len("__MM3B64__"):], validate=False)
            except Exception:
                return None, ""
        if not blob:
            return None, ""

        image, fmt, _ole_info = cls._decode_access_ole1(blob)
        if image:
            return image, fmt

        return cls._decode_image_payload(blob)


    def _perform_real_import(self, destination: Path, name: str, mapping: list[dict]) -> dict:
        """Crée une collection MM3 et reconstruit les données + sous-formulaires liés.

        11.7.69.3 — instrumentation champ par champ de l'import Access. Les temps
        retournés servent uniquement à localiser le vrai goulet d'étranglement
        avant toute nouvelle optimisation.
        """
        _chrono_start = time.perf_counter()
        _chrono_last = _chrono_start
        _timings: dict[str, float] = {}

        def _mark(label: str) -> None:
            nonlocal _chrono_last
            now = time.perf_counter()
            _timings[label] = _timings.get(label, 0.0) + (now - _chrono_last)
            _chrono_last = now

        manager = CollectionManager(destination)
        cid = manager.create_collection({
            "name": name,
            "owner": "",
            "description": f"Import Access : {self.access_source.name if self.access_source else ''}",
        })
        db = DatabaseManager(destination)
        db.initialize()
        db.disconnect()
        record_manager = RecordManager(destination)
        with record_manager._connect() as connection:
            record_manager._ensure_table(connection)

        model_manager = ModelManager(destination)
        template_key = self._selected_import_template()
        apply_official_template_database(model_manager, int(cid), template_key)
        template_fields = (self._template_destination_fields(model_manager, int(cid))
                           if template_key != "blank" else {})

        main_table = str(self.selected_access_table.get("name") or "")
        entries: list[dict] = []
        ordered_keys: list[str] = []

        # La correspondance peut être réouverte/modifiée : l'ordre Access
        # mémorisé dans chaque ligne reste l'autorité pour construire le modèle.
        def mapping_tab_key(item: dict):
            raw = item.get("access_tab_path")
            if isinstance(raw, (list, tuple)) and raw:
                try:
                    vals = [int(v) for v in raw]
                    while len(vals) < 5:
                        vals.append(0)
                    return tuple(vals[:5])
                except (TypeError, ValueError):
                    pass
            return (9, 1_000_000, 9, 1_000_000, 1_000_000)

        mapping = sorted(list(mapping), key=mapping_tab_key)

        photo_entries: list[dict] = []
        for item in mapping:
            source = str(item.get("source") or "")
            source_table = str(item.get("source_table") or main_table)
            target = str(item.get("target") or source).strip()
            mm3_type = str(item.get("mm3_type") or "Texte")
            # Le type explicitement validé dans les correspondances prime
            # sur le libellé : « Photo à faire » et « Fichier photo »
            # sont des champs ordinaires lorsqu'ils sont déclarés Texte/Liste.
            photo_like = (mm3_type == "Photo / Image")

            # Une photo Access alimente le vrai cadre Photo MM3 : elle ne doit
            # plus devenir un champ texte contenant "[Donnée binaire ...]".
            if photo_like:
                photo_index = len(photo_entries) + 1
                slot_key = "Photo" if photo_index == 1 else f"photo_slot_{photo_index}"
                entry = dict(item)
                entry.update({
                    "source": source,
                    "source_table": source_table,
                    "target": target,
                    "mm3_type": mm3_type,
                    "field_key": "photo_data" if photo_index == 1 else slot_key,
                    "referential_code": "",
                    "photo_index": photo_index,
                    "photo_slot_key": slot_key,
                    "is_photo_field": True,
                    "is_primary_photo": photo_index == 1,
                })
                entries.append(entry)
                photo_entries.append(entry)
                continue

            field_type = self._mm3_field_type(mm3_type)
            calculation_format = str(item.get("calculation_format") or "truncate2")
            target_key = str(item.get("target_field_key") or "")
            created = (next((meta for meta in template_fields.values() if meta.get("field_key") == target_key), None)
                       if target_key else template_fields.get(target.casefold()))
            if created is None:
                created = model_manager.create_custom_field(
                    int(cid), target, field_type, initial_group="Identification",
                    calculation_formula="", calculation_format=calculation_format,
                )
            if template_key != "blank" and item.get("create_in_palette") and created is not None:
                with sqlite3.connect(destination) as con:
                    con.execute("UPDATE collection_model_fields SET visible=0 WHERE collection_id=? AND field_key=?", (int(cid), str(created["field_key"])))
            entry = dict(item)
            entry.update({
                "source": source,
                "source_table": source_table,
                "target": target,
                "mm3_type": mm3_type,
                "field_key": str(created["field_key"]),
                "referential_code": str(created.get("referential_code") or ""),
            })
            entry["field_type"] = field_type
            entries.append(entry)
            ordered_keys.append(entry["field_key"])

        # 11.7.70.26.8 — activer réellement les champs calculés Access reconnus.
        # La correspondance conserve les noms source ; on les traduit ici vers
        # les clés internes MM3 une fois tous les champs créés.
        source_to_key = {
            str(e.get("source") or "").casefold(): str(e.get("field_key") or "")
            for e in entries if e.get("field_key") and not e.get("is_photo_field")
        }
        for entry in entries:
            if str(entry.get("field_type") or "") != "calculated":
                continue
            expression = str(entry.get("calculation_expression") or "").strip()
            if not expression:
                continue
            unresolved = False
            def _replace_access_formula_field(match):
                nonlocal unresolved
                source_name = str(match.group(1) or "").strip()
                key = source_to_key.get(source_name.casefold())
                if not key:
                    unresolved = True
                    return match.group(0)
                return "{" + key + "}"
            mm3_formula = re.sub(r"\[([^\]]+)\]", _replace_access_formula_field, expression)
            if not unresolved and "[" not in mm3_formula and "]" not in mm3_formula:
                model_manager.update_custom_field_calculation(
                    int(cid), str(entry["field_key"]), mm3_formula
                )
                entry["mm3_formula"] = mm3_formula

        # Bandeau du modèle vierge : une marge franche est volontairement
        # conservée avant la première rangée de champs importés.
        positions: dict[str, tuple[int, int]] = {}
        sizes: dict[str, tuple[int, int]] = {}
        start_y = 190
        row_step = 40
        left_x, right_x = 24, 500
        for index, key in enumerate(ordered_keys):
            column = index % 2
            row = index // 2
            positions[key] = (
                left_x if column == 0 else right_x,
                start_y + row * row_step,
            )
            sizes[key] = (440, 31)

        if template_key == "blank":
            model_manager.set_visual_positions(int(cid), positions)
            model_manager.set_visual_sizes(int(cid), sizes)
            model_manager.set_tab_order(int(cid), ["record_number", *ordered_keys])
        else:
            # Préserver intégralement la géométrie du modèle choisi.
            # Les éventuels champs ajoutés conservent leur placement par défaut.
            pass

        if template_key == "blank":
            styles = model_manager.field_styles(int(cid))
            for key in ordered_keys:
                styles.setdefault(key, {}).setdefault("data", {})["color"] = "#000000"
            model_manager.set_field_styles(int(cid), styles)

        if photo_entries:
            # Réactive le vrai cadre Photo du modèle vierge.
            with sqlite3.connect(destination) as connection:
                connection.execute(
                    """UPDATE collection_model_fields
                       SET visible=1
                       WHERE collection_id=? AND field_key='photo_data'""",
                    (int(cid),),
                )
                row = connection.execute(
                    """SELECT group_styles FROM collection_model_appearance
                       WHERE collection_id=?""",
                    (int(cid),),
                ).fetchone()
                if row:
                    try:
                        group_styles = json.loads(str(row[0] or "{}"))
                    except Exception:
                        group_styles = {}
                    photo_style = dict(group_styles.get("Photo", {}) or {})
                    photo_style["frame_deleted"] = False
                    photo_style["geometry_space"] = "atelier_px"
                    photo_style["geometry"] = {
                        "x": 720, "y": 190, "w": 300, "h": 170
                    }
                    group_styles["Photo"] = photo_style

                    # Les photos supplémentaires deviennent de vrais cadres
                    # Photo MM3, directement visibles dans l'Atelier et la Fiche.
                    # Elles sont placées sous la précédente pour ne jamais être cachées.
                    for photo_index in range(2, len(photo_entries) + 1):
                        slot_key = f"photo_slot_{photo_index}"
                        group_styles[slot_key] = {
                            "custom_group": True,
                            "custom_photo": True,
                            "frame_deleted": False,
                            "title": {"text": f"Photo {photo_index}"},
                            "geometry_space": "atelier_px",
                            "geometry": {
                                "x": 720,
                                "y": 190 + (photo_index - 1) * 190,
                                "w": 300,
                                "h": 170,
                            },
                        }

                    connection.execute(
                        """UPDATE collection_model_appearance
                           SET group_styles=? WHERE collection_id=?""",
                        (json.dumps(group_styles, ensure_ascii=False), int(cid)),
                    )

        _mark("Préparation collection / modèle")

        # 1) Fiches : uniquement les champs réellement portés par la table principale.
        main_entries = [
            e for e in entries
            if not e.get("is_related_field")
            and not e.get("is_photo_field")
            and str(e.get("source_table") or main_table).casefold() == main_table.casefold()
        ]
        main_photo_entries = [
            e for e in photo_entries
            if str(e.get("source_table") or main_table).casefold() == main_table.casefold()
        ]
        main_columns = list(dict.fromkeys(
            str(e.get("source") or "")
            for e in [*main_entries, *main_photo_entries]
            if str(e.get("source") or "")
        ))

        structured_specs = list(
            self.selected_access_table.get("structured_reference_specs", []) or []
        )

        # Compatibilité de secours : si une ancienne préparation n'a pas encore
        # les spécifications explicites, les reconstruire depuis les champs liés.
        if not structured_specs:
            seen_specs = set()
            for entry in entries:
                if not entry.get("is_related_field"):
                    continue
                key = (
                    str(entry.get("source_table") or ""),
                    str(entry.get("linked_master_source") or ""),
                    str(entry.get("linked_child_source") or ""),
                )
                if not all(key) or key in seen_specs:
                    continue
                seen_specs.add(key)
                structured_specs.append({
                    "child_table": key[0],
                    "parent_master_source": key[1],
                    "child_master_source": key[2],
                    "related_form": str(entry.get("related_form") or ""),
                })

        requests_by_table: dict[str, set[str]] = {
            main_table: set(main_columns)
        }
        for spec in structured_specs:
            child_table = str(spec.get("child_table") or "")
            child_master = str(spec.get("child_master_source") or "")
            parent_master = str(spec.get("parent_master_source") or "")
            if not child_table or not child_master or not parent_master:
                continue
            columns = requests_by_table.setdefault(child_table, set())
            columns.add(child_master)
            for entry in entries:
                if not entry.get("is_related_field"):
                    continue
                if str(entry.get("source_table") or "").casefold() != child_table.casefold():
                    continue
                if str(entry.get("linked_master_source") or "").casefold() != parent_master.casefold():
                    continue
                if str(entry.get("linked_child_source") or "").casefold() != child_master.casefold():
                    continue
                source_name = str(entry.get("source") or "")
                if source_name:
                    columns.add(source_name)

        main_order_sql = str(
            self.selected_access_table.get("access_record_order_sql") or ""
        ).strip()
        bundle_requests = []
        for table, columns in requests_by_table.items():
            if not table or not columns:
                continue
            request = {
                "table": table,
                "columns": sorted(columns, key=str.casefold),
            }
            if table.casefold() == main_table.casefold() and main_order_sql:
                request["order_by"] = main_order_sql
            bundle_requests.append(request)
        access_bundle = self._read_access_bundle(self.access_source, bundle_requests)
        _access_read_diagnostic = dict(access_bundle.get("__mm3_diagnostic__", {}) or {})
        data = list(access_bundle.get(main_table, []) or [])
        _mark("Lecture groupée Access")

        count = 0
        photos_imported = 0
        photos_unreadable = 0
        first_photo_signature = ''
        _photo_elapsed = 0.0
        for source_row in data:
            record = record_manager.create_record(int(cid))
            custom_values = {}
            for entry in main_entries:
                source_name = str(entry.get("source") or "")
                raw = source_row.get(source_name, "")
                if str(entry.get("field_key") or "") == "record_state":
                    state = str(raw or "").strip().casefold()
                    state_map = {"ok": "OK", "vérifier": "Vérifier", "verifier": "Vérifier", "check": "Vérifier", "libre": "Libre", "free": "Libre"}
                    if state in state_map:
                        with record_manager._connect() as state_con:
                            state_con.execute("UPDATE records SET record_state=? WHERE id=?", (state_map[state], int(record["id"])))
                    # Un état inconnu conserve la valeur native OK ; il ne devient jamais un champ personnalisé.
                    continue
                custom_values[str(entry["field_key"])] = self._format_imported_value(
                    raw, str(entry.get("target") or source_name)
                )
            # Les champs natifs du modèle sont des colonnes de records, pas des
            # entrées record_custom_values. Séparer les deux destinations.
            native_columns = set(record_manager.FIELD_DEFAULTS)
            native_values = {k: v for k, v in custom_values.items() if k in native_columns}
            extra_values = {k: v for k, v in custom_values.items() if k not in native_columns}
            if native_values:
                with record_manager._connect() as native_con:
                    native_con.execute(
                        "UPDATE records SET " + ", ".join(f'"{k}"=?' for k in native_values) + " WHERE id=?",
                        [*native_values.values(), int(record["id"])],
                    )
                    if "mineral_name" in native_values:
                        native_con.execute("UPDATE records SET species=? WHERE id=?", (native_values["mineral_name"], int(record["id"])))
            if extra_values:
                record_manager.set_custom_values(int(record["id"]), extra_values)

            _photo_t0 = time.perf_counter()
            for photo_entry in main_photo_entries:
                source_name = str(photo_entry.get("source") or "")
                raw_photo = source_row.get(source_name, "")
                photo_data, photo_format = self._decode_access_photo(raw_photo)
                if photo_data:
                    photo_index = int(photo_entry.get("photo_index") or 1)
                    if photo_index == 1:
                        with record_manager._connect() as connection:
                            record_manager._ensure_table(connection)
                            connection.execute(
                                "UPDATE records SET photo_data=?, photo_format=? WHERE id=?",
                                (sqlite3.Binary(photo_data), photo_format, int(record["id"])),
                            )
                    else:
                        record_manager.set_extra_photo(
                            int(record["id"]),
                            str(photo_entry.get("photo_slot_key") or f"photo_slot_{photo_index}"),
                            photo_data,
                            photo_format,
                        )
                    photos_imported += 1
                    continue

                if (
                    isinstance(raw_photo, (bytes, bytearray, memoryview))
                    and bool(raw_photo)
                ) or str(raw_photo or "").startswith("__MM3B64__"):
                    if not first_photo_signature and isinstance(raw_photo, (bytes, bytearray, memoryview)):
                        raw_bytes = bytes(raw_photo)
                        _img, _fmt, ole_info = self._decode_access_ole1(raw_bytes)
                        first_photo_signature = (
                            f"{len(raw_bytes)} octets — "
                            + raw_bytes[:24].hex(" ")
                            + (f" — OLE : {ole_info}" if ole_info else "")
                        )
                    photos_unreadable += 1
            _photo_elapsed += time.perf_counter() - _photo_t0
            count += 1
            if count % 20 == 0:
                QApplication.processEvents()

        QApplication.processEvents()
        _mark("Création fiches + valeurs + photos")
        _timings["dont traitement photos"] = _photo_elapsed

        # 2) Listes simples de la table principale.
        referential_values = 0
        with sqlite3.connect(destination) as connection:
            connection.execute("PRAGMA foreign_keys=ON")
            now = datetime.now().isoformat(timespec="seconds")
            for entry in main_entries:
                if not str(entry.get("mm3_type") or "").startswith("Liste / Référentiel"):
                    continue
                code = str(entry.get("referential_code") or entry["field_key"])
                row = connection.execute(
                    "SELECT id FROM referential_definitions "
                    "WHERE collection_id=? AND code=?",
                    (int(cid), code),
                ).fetchone()
                if row is None:
                    continue
                definition_id = int(row[0])
                seen: set[str] = set()
                values: list[str] = []
                source_name = str(entry.get("source") or "")
                for source_row in data:
                    value = " ".join(str(source_row.get(source_name, "") or "").strip().split())
                    if not value:
                        continue
                    marker = value.casefold()
                    if marker in seen:
                        continue
                    seen.add(marker)
                    values.append(value)
                values.sort(key=str.casefold)
                for order, value in enumerate(values, start=1):
                    connection.execute(
                        """INSERT OR IGNORE INTO referential_values(
                               definition_id, value, sort_order, is_active, created_at, updated_at
                           ) VALUES (?, ?, ?, 1, ?, ?)""",
                        (definition_id, value, order, now, now),
                    )
                referential_values += len(values)

        _mark("Listes simples")

        # 3) Sous-formulaires Access : reconstruire chaque référentiel complet
        # d'après la structure Access détectée, même si certains champs enfants
        # ont été ignorés dans Correspondance.
        structured_tables = 0
        structured_rows = 0
        structured_links = 0
        linked_backfilled = 0
        # 11.7.70.26.5-DIAG — photographie exacte des groupes Access avant création.
        # Diagnostic uniquement : aucune règle d'import n'est modifiée.
        structured_debug: list[str] = []
        for _idx, _spec in enumerate(structured_specs, start=1):
            _ct = str(_spec.get("child_table") or "")
            _pm = str(_spec.get("parent_master_source") or "")
            _cm = str(_spec.get("child_master_source") or "")
            _matches = [
                str(e.get("source") or "")
                for e in entries
                if e.get("is_related_field")
                and str(e.get("source_table") or "").casefold() == _ct.casefold()
                and str(e.get("linked_master_source") or "").casefold() == _pm.casefold()
                and str(e.get("linked_child_source") or "").casefold() == _cm.casefold()
            ]
            _master_matches = [
                str(e.get("target") or e.get("source") or "")
                for e in main_entries
                if str(e.get("source") or "").casefold() == _pm.casefold()
            ]
            if str(self.language or "").lower().startswith("de"):
                structured_debug.append(
                    f"Gruppe {_idx}: Tabelle={_ct or '?'} ; Quell-Master={_pm or '?'} ; "
                    f"Kind-Master={_cm or '?'} ; G-Skol-Master={','.join(_master_matches) or 'FEHLT'} ; "
                    f"verknüpft={','.join(_matches) or 'KEINE'}"
                )
            elif str(self.language or "").lower().startswith("en"):
                structured_debug.append(
                    f"Group {_idx}: table={_ct or '?'} ; source master={_pm or '?'} ; "
                    f"child master={_cm or '?'} ; G-Skol master={','.join(_master_matches) or 'MISSING'} ; "
                    f"linked={','.join(_matches) or 'NONE'}"
                )
            else:
                structured_debug.append(
                    f"Groupe {_idx}: table={_ct or '?'} ; maître source={_pm or '?'} ; "
                    f"maître enfant={_cm or '?'} ; maître G-Skol={','.join(_master_matches) or 'ABSENT'} ; "
                    f"reliés={','.join(_matches) or 'AUCUN'}"
                )
        _structured_import_elapsed = 0.0
        _linked_backfill_elapsed = 0.0

        for spec in structured_specs:
            child_table = str(spec.get("child_table") or "")
            parent_master_source = str(spec.get("parent_master_source") or "")
            child_master_source = str(spec.get("child_master_source") or "")
            if not child_table or not parent_master_source or not child_master_source:
                continue

            linked_entries = [
                e for e in entries
                if e.get("is_related_field")
                and str(e.get("source_table") or "").casefold() == child_table.casefold()
                and str(e.get("linked_master_source") or "").casefold() == parent_master_source.casefold()
                and str(e.get("linked_child_source") or "").casefold() == child_master_source.casefold()
            ]

            master_entry = next(
                (
                    e for e in main_entries
                    if str(e.get("source") or "").casefold() == parent_master_source.casefold()
                ),
                None,
            )
            if master_entry is None:
                continue
            master_key = str(master_entry["field_key"])

            child_columns = [child_master_source]
            child_columns.extend(
                str(e.get("source") or "")
                for e in linked_entries
                if str(e.get("source") or "")
            )
            child_columns = list(dict.fromkeys(child_columns))
            ref_source_rows = list(access_bundle.get(child_table, []) or [])

            reference_rows: list[dict[str, str]] = []
            masters: list[str] = []
            masters_seen: set[str] = set()
            list_values_by_entry: dict[str, set[str]] = {
                str(e["field_key"]): set() for e in linked_entries
                if str(e.get("mm3_type") or "").startswith("Liste / Référentiel")
            }

            for source_row in ref_source_rows:
                master_value = str(source_row.get(child_master_source, "") or "").strip()
                if not master_value:
                    continue
                marker = master_value.casefold()
                if marker not in masters_seen:
                    masters_seen.add(marker)
                    masters.append(master_value)

                converted = {master_key: master_value}
                for entry in linked_entries:
                    source_name = str(entry.get("source") or "")
                    value = self._format_imported_value(
                        source_row.get(source_name, ""),
                        str(entry.get("target") or source_name),
                    )
                    key = str(entry["field_key"])
                    converted[key] = value
                    if key in list_values_by_entry and value.strip():
                        list_values_by_entry[key].add(value.strip())
                reference_rows.append(converted)

            if not reference_rows:
                continue

            _ref_t0 = time.perf_counter()
            stats = model_manager.import_reference_rows(
                int(cid), master_key, reference_rows
            )
            _structured_import_elapsed += time.perf_counter() - _ref_t0

            if linked_entries:
                _backfill_t0 = time.perf_counter()
                linked_backfilled += self._apply_imported_reference_to_records(
                    destination,
                    master_key,
                    [str(e["field_key"]) for e in linked_entries],
                    reference_rows,
                )
                _linked_backfill_elapsed += time.perf_counter() - _backfill_t0

            # Le maître est toujours une vraie liste MM3 alimentée par TOUTE la
            # table de référence (IMA/Gisements), pas seulement les fiches utilisées.
            with sqlite3.connect(destination) as connection:
                connection.execute("PRAGMA foreign_keys=ON")
                now = datetime.now().isoformat(timespec="seconds")
                row = connection.execute(
                    "SELECT referential_code FROM collection_custom_fields "
                    "WHERE collection_id=? AND field_key=?",
                    (int(cid), master_key),
                ).fetchone()
                code = str(row[0] or "") if row else ""
                if not code:
                    code = master_key
                    connection.execute(
                        "UPDATE collection_custom_fields "
                        "SET field_type='list', referential_code=? "
                        "WHERE collection_id=? AND field_key=?",
                        (code, int(cid), master_key),
                    )
                    connection.execute(
                        """INSERT OR IGNORE INTO referential_definitions(
                               collection_id, code, label, is_master, created_at
                           ) VALUES (?, ?, ?, 1, ?)""",
                        (int(cid), code, str(master_entry.get("target") or parent_master_source), now),
                    )
                else:
                    connection.execute(
                        "UPDATE referential_definitions SET is_master=1 "
                        "WHERE collection_id=? AND code=?",
                        (int(cid), code),
                    )

                definition = connection.execute(
                    "SELECT id FROM referential_definitions "
                    "WHERE collection_id=? AND code=?",
                    (int(cid), code),
                ).fetchone()
                if definition:
                    did = int(definition[0])
                    for order, value in enumerate(sorted(masters, key=str.casefold), 1):
                        connection.execute(
                            """INSERT OR IGNORE INTO referential_values(
                                   definition_id, value, sort_order, is_active,
                                   created_at, updated_at
                               ) VALUES (?, ?, ?, 1, ?, ?)""",
                            (did, value, order, now, now),
                        )

                # Si un champ relié est lui-même une liste, récupérer également
                # toutes ses valeurs propres depuis le sous-formulaire.
                for entry in linked_entries:
                    key = str(entry["field_key"])
                    values = sorted(list_values_by_entry.get(key, set()), key=str.casefold)
                    if not values:
                        continue
                    code = str(entry.get("referential_code") or "")
                    if not code:
                        continue
                    def_row = connection.execute(
                        "SELECT id FROM referential_definitions "
                        "WHERE collection_id=? AND code=?",
                        (int(cid), code),
                    ).fetchone()
                    if not def_row:
                        continue
                    did = int(def_row[0])
                    for order, value in enumerate(values, 1):
                        connection.execute(
                            """INSERT OR IGNORE INTO referential_values(
                                   definition_id, value, sort_order, is_active,
                                   created_at, updated_at
                               ) VALUES (?, ?, ?, 1, ?, ?)""",
                            (did, value, order, now, now),
                        )

            structured_tables += 1
            structured_rows += int(stats.get("rows", 0))
            structured_links += len(linked_entries)
            QApplication.processEvents()

        if structured_tables:
            # Les fiches viennent d'être créées et ont déjà été alimentées
            # directement depuis collection_reference_data ci-dessus.
            # Le rattrapage historique complet serait donc redondant et pouvait
            # bloquer l'interface quelques secondes en toute fin d'import.
            QApplication.processEvents()

        # 2.3.24.6.12 : les trois valeurs IMA de fluorescence sont liées
        # au maître et ne sont PAS des colonnes de la table principale.
        # Dans un modèle natif, les valeurs par défaut (Non / Aucune)
        # sont déjà présentes : le rattrapage générique, qui n'écrit que
        # dans les champs vides, ne peut donc pas les remplacer.
        # Rétablir ici uniquement les valeurs IMA explicitement importées.
        if template_key != "blank":
            fluorescence_keys = {
                "luminescence", "luminescence_intensity", "fluorescence_color"
            }
            fluorescence_by_master = []
            for spec in structured_specs:
                child_table = str(spec.get("child_table") or "")
                parent_source = str(spec.get("parent_master_source") or "")
                child_source = str(spec.get("child_master_source") or "")
                master_entry = next((e for e in main_entries
                    if str(e.get("source") or "").casefold() == parent_source.casefold()), None)
                if not master_entry or not child_source:
                    continue
                linked_fluorescence = [e for e in entries
                    if e.get("is_related_field")
                    and str(e.get("source_table") or "").casefold() == child_table.casefold()
                    and str(e.get("linked_master_source") or "").casefold() == parent_source.casefold()
                    and str(e.get("linked_child_source") or "").casefold() == child_source.casefold()
                    and str(e.get("field_key") or "") in fluorescence_keys]
                if not linked_fluorescence:
                    continue
                lookup = {}
                for source_row in access_bundle.get(child_table, []) or []:
                    master_value = str(source_row.get(child_source, "") or "").strip().casefold()
                    if not master_value:
                        continue
                    values = lookup.setdefault(master_value, {})
                    for entry in linked_fluorescence:
                        key = str(entry["field_key"])
                        value = self._format_imported_value(
                            source_row.get(str(entry.get("source") or ""), ""),
                            str(entry.get("target") or entry.get("source") or ""))
                        if str(value or "").strip() and not values.get(key):
                            values[key] = value
                fluorescence_by_master.append((str(master_entry["field_key"]), lookup))
            if fluorescence_by_master:
                with record_manager._connect() as con:
                    columns = {str(r[1]) for r in con.execute("PRAGMA table_info(records)")}
                    for master_key, lookup in fluorescence_by_master:
                        if master_key in columns:
                            rows = con.execute(
                                'SELECT id, "' + master_key + '" FROM records WHERE collection_id=?',
                                (int(cid),)).fetchall()
                        else:
                            rows = con.execute(
                                "SELECT r.id, cv.value FROM records r "
                                "JOIN record_custom_values cv ON cv.record_id=r.id "
                                "AND cv.field_key=? WHERE r.collection_id=?",
                                (master_key, int(cid))).fetchall()
                        for record_id, master_value in rows:
                            values = lookup.get(str(master_value or "").strip().casefold(), {})
                            for key, value in values.items():
                                if key in columns:
                                    con.execute('UPDATE records SET "' + key + '"=? WHERE id=?',
                                                (value, int(record_id)))
                                else:
                                    con.execute(
                                        "INSERT INTO record_custom_values(record_id,field_key,value) "
                                        "VALUES (?,?,?) ON CONFLICT(record_id,field_key) "
                                        "DO UPDATE SET value=excluded.value",
                                        (int(record_id), key, value))

        _mark("Référentiels liés + report dans les fiches")
        _timings["dont écriture tables liées"] = _structured_import_elapsed
        _timings["dont report valeurs reliées"] = _linked_backfill_elapsed
        _timings["TOTAL"] = time.perf_counter() - _chrono_start

        return {
            "records": count,
            "fields": len(entries),
            "referential_values": referential_values,
            "structured_tables": structured_tables,
            "structured_rows": structured_rows,
            "structured_links": structured_links,
            "structured_debug": structured_debug,
            "linked_backfilled": linked_backfilled,
            "photos_imported": photos_imported,
            "photos_unreadable": photos_unreadable,
            "photo_sources": len(main_photo_entries),
            "first_photo_signature": first_photo_signature,
            "record_order_mode": str(
                self.selected_access_table.get("access_record_order_mode") or "source"
            ),
            "timings": dict(_timings),
            "access_read_diagnostic": _access_read_diagnostic,
        }

    @staticmethod
    def _read_access_rows(path: Path, table_name: str, columns: list[str]) -> list[dict]:
        """Lit des lignes Access sans PowerShell, via le pont Access/DAO VBScript."""
        result = CollectionImportDialog._read_access_bundle(
            path,
            [{"table": str(table_name), "columns": [str(c) for c in columns]}],
        )
        return list(result.get(str(table_name), []) or [])

    @staticmethod
    def _read_access_preview(path: Path, table_name: str, limit: int = 10) -> dict:
        """Aperçu Access sans PowerShell, via le même moteur que l'import."""
        limit = max(1, min(int(limit), 50))
        structure = CollectionImportDialog._read_access_structure(path)
        table = next(
            (t for t in structure.get("tables", []) or []
             if str(t.get("name") or "").casefold() == str(table_name).casefold()),
            None,
        )
        columns = [str(f.get("name") or "") for f in (table or {}).get("fields", []) or []]
        columns = [c for c in columns if c]
        if not columns:
            return {"columns": [], "rows": []}
        rows_dict = CollectionImportDialog._read_access_rows(path, table_name, columns)[:limit]
        rows = [[row.get(c, "") for c in columns] for row in rows_dict]
        return {"columns": columns, "rows": rows}

    @staticmethod
    def _read_access_forms_structure(path: Path) -> dict:
        """Lit formulaires et sous-formulaires Access sans PowerShell.

        Le pont VBScript ouvre Access en mode invisible et lit RecordSource,
        SourceObject, LinkMasterFields/LinkChildFields et les ControlSource.
        Ces informations sont indispensables pour reconstruire une fiche
        complète lorsque ses données sont réparties entre table principale et
        sous-formulaires (IMA, Gisements, etc.). La base reste en lecture seule
        du point de vue de MM3 : aucun objet n'est enregistré ni modifié.
        """
        if os.name != "nt":
            return {"forms": [], "queries": [], "warning": "Analyse des formulaires Access disponible sous Windows uniquement."}

        bridge_path = Path(__file__).resolve().parent / "access_forms_structure_bridge.vbs"
        if not bridge_path.exists():
            return {"forms": [], "queries": [], "warning": f"Lecteur des formulaires Access introuvable : {bridge_path.name}"}

        def _int_or_none(value):
            try:
                text = str(value or "").strip()
                return int(text) if text else None
            except (TypeError, ValueError):
                return None

        def _bool_attr(value, default=False):
            text = str(value or "").strip().casefold()
            if text in {"1", "true", "yes", "oui", "-1"}:
                return True
            if text in {"0", "false", "no", "non", ""}:
                return False
            return default

        with tempfile.TemporaryDirectory(prefix="mm3_access_forms_") as temp_dir:
            output_path = Path(temp_dir) / "forms.xml"
            proc = subprocess.run(
                ["cscript.exe", "//Nologo", str(bridge_path), str(path), str(output_path)],
                capture_output=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                timeout=120,
            )
            stdout = proc.stdout.decode("mbcs", errors="replace").strip()
            stderr = proc.stderr.decode("mbcs", errors="replace").strip()
            if proc.returncode != 0:
                return {"forms": [], "queries": [], "warning": stderr or stdout or "Erreur pendant l’analyse des formulaires Access."}
            if not output_path.exists():
                return {"forms": [], "queries": [], "warning": stdout or "Le moteur Access n’a renvoyé aucun formulaire."}

            root = ET.parse(output_path).getroot()
            queries = [
                {"name": q.get("name", ""), "sql": q.get("sql", "")}
                for q in root.findall("query")
            ]
            forms = []
            for form_node in root.findall("form"):
                controls = []
                for ctrl in form_node.findall("control"):
                    controls.append({
                        "name": ctrl.get("name", ""),
                        "label": ctrl.get("label", ""),
                        "control_source": ctrl.get("control_source", ""),
                        "row_source": ctrl.get("row_source", ""),
                        "source_object": ctrl.get("source_object", ""),
                        "link_master_fields": ctrl.get("link_master_fields", ""),
                        "link_child_fields": ctrl.get("link_child_fields", ""),
                        "control_type": _int_or_none(ctrl.get("control_type")),
                        "tab_index": _int_or_none(ctrl.get("tab_index")),
                        "tab_stop": _bool_attr(ctrl.get("tab_stop"), True),
                        "section": _int_or_none(ctrl.get("section")),
                        "visible": _bool_attr(ctrl.get("visible"), True),
                        "enabled": _bool_attr(ctrl.get("enabled"), True),
                        "left": _int_or_none(ctrl.get("left")),
                        "top": _int_or_none(ctrl.get("top")),
                    })
                forms.append({
                    "name": form_node.get("name", ""),
                    "caption": form_node.get("caption", ""),
                    "default_view": _int_or_none(form_node.get("default_view")),
                    "record_source": form_node.get("record_source", ""),
                    "order_by": form_node.get("order_by", ""),
                    "order_by_on": _bool_attr(form_node.get("order_by_on"), False),
                    "controls": controls,
                })
            return {"forms": forms, "queries": queries, "warning": None}


    @staticmethod
    def _read_access_structure(path: Path) -> dict:
        """Lit rapidement tables, champs et relations Access sans PowerShell.

        Le pont VBScript utilise Microsoft Access/DAO déjà présent sur le poste.
        Il ne modifie jamais la base source.
        """
        if os.name != "nt":
            raise RuntimeError("L’analyse Access doit être exécutée sous Windows.")

        bridge_path = Path(__file__).resolve().parent / "access_structure_bridge.vbs"
        if not bridge_path.exists():
            raise RuntimeError(f"Lecteur de structure Access introuvable : {bridge_path.name}")

        with tempfile.TemporaryDirectory(prefix="mm3_access_structure_") as temp_dir:
            output_path = Path(temp_dir) / "structure.xml"
            proc = subprocess.run(
                ["cscript.exe", "//Nologo", str(bridge_path), str(path), str(output_path)],
                capture_output=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                timeout=120,
            )
            stdout = proc.stdout.decode("mbcs", errors="replace").strip()
            stderr = proc.stderr.decode("mbcs", errors="replace").strip()
            if proc.returncode != 0:
                raise RuntimeError(stderr or stdout or "Erreur lors de l’analyse Access.")
            if not output_path.exists():
                raise RuntimeError(stdout or "Le moteur Access n’a renvoyé aucune structure.")

            root = ET.parse(output_path).getroot()
            tables = []
            for table_node in root.findall("table"):
                fields = []
                for field_node in table_node.findall("field"):
                    fields.append({
                        "name": field_node.get("name", ""),
                        "type": field_node.get("type", ""),
                        "size": int(field_node.get("size", "0") or 0) or None,
                        "calculation_expression": field_node.get("calculation_expression") or None,
                        "calculation_result_type": field_node.get("calculation_result_type") or None,
                        "dao_type": int(field_node.get("dao_type", "0") or 0) or None,
                        "field_attributes": int(field_node.get("field_attributes", "0") or 0),
                        "is_calculated": field_node.get("is_calculated", "0") == "1",
                        "lookup_source": field_node.get("lookup_source") or None,
                        "lookup_type": field_node.get("lookup_type") or None,
                        "relation_table": field_node.get("relation_table") or None,
                        "relation_field": field_node.get("relation_field") or None,
                    })
                rows_raw = table_node.get("rows", "")
                try:
                    row_count = int(rows_raw) if rows_raw != "" else None
                except ValueError:
                    row_count = None
                tables.append({
                    "name": table_node.get("name", ""),
                    "rows": row_count,
                    "fields": fields,
                })
            return {"provider": "Access.DAO", "tables": tables}


class ExportDialog(QDialog):
    """Exportation transportable d'une collection MM3 ou de sa structure."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.language = str(getattr(parent, "language", "fr") or "fr")
        self.setWindowTitle(tr("Exportation", self.language))
        self.resize(790, 520)
        self.setMinimumSize(690, 460)
        # Le Workspace est externe au programme en mode installé.
        # Ne jamais le reconstruire depuis __file__ (dossier Program Files).
        self._root = Path(WORKSPACE).parent
        self._collections_folder = Path(WORKSPACE) / "Collections"
        self._system_db = Path(WORKSPACE) / "BacASable" / ".mm3-system.db"
        self._manager = CollectionManager(self._system_db)
        self._folder_store = CollectionFolderStore(self._collections_folder)
        self._collections: list[dict] = []
        self._external_last_dir_file = Path(WORKSPACE) / "Paramètres" / "export_external_last_dir.txt"
        self._build_ui()
        translate_widget_tree(self, self.language)
        self._load_folders()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 26, 30, 24)
        layout.setSpacing(16)
        title = QLabel(tr("Exportation", self.language))
        title.setStyleSheet("font-size: 24px; font-weight: 800;")
        layout.addWidget(title)
        text = QLabel(tr("Choisissez un dossier puis une collection. L'export crée un fichier transportable sans modifier la collection d'origine.", self.language))
        text.setWordWrap(True); text.setStyleSheet("font-size: 13px;")
        layout.addWidget(text)

        choose = QFrame(); choose.setFrameShape(QFrame.Shape.StyledPanel)
        form = QFormLayout(choose); form.setContentsMargins(18, 16, 18, 16)
        self.folder_combo = QComboBox(); self.folder_combo.currentTextChanged.connect(self._load_collections)
        self.collection_combo = QComboBox(); self.collection_combo.currentIndexChanged.connect(self._selection_changed)
        form.addRow(tr("Dossier :", self.language), self.folder_combo)
        form.addRow(tr("Collection :", self.language), self.collection_combo)
        external_row = QHBoxLayout()
        self.external_browse_btn = QPushButton(tr("Parcourir…", self.language))
        self.external_browse_btn.clicked.connect(self._browse_external_collection)
        external_row.addWidget(self.external_browse_btn)
        self.external_path_label = QLabel("")
        self.external_path_label.setWordWrap(True)
        self.external_path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        external_row.addWidget(self.external_path_label, 1)
        form.addRow(tr("Collection externe :", self.language), external_row)
        layout.addWidget(choose)

        style = ("QPushButton { text-align: left; padding: 16px 20px; font-size: 16px; font-weight: 750; }")
        self.full_btn = QPushButton(tr("Exporter une collection complète  (.coldb)", self.language))
        self.full_btn.setToolTip(tr("Données, photos, référentiels, champs, modèles et réglages de la collection.", self.language))
        self.full_btn.setMinimumHeight(76); self.full_btn.setStyleSheet(style); self.full_btn.setEnabled(False)
        self.full_btn.clicked.connect(lambda: self._export_selected("complete"))
        layout.addWidget(self.full_btn)
        self.excel_btn = QPushButton(tr("Exporter une collection vers Excel  (.xlsx)", self.language))
        self.excel_btn.setToolTip(tr("Toutes les fiches et tous les champs, sans photos. Un seul onglet Excel.", self.language))
        self.excel_btn.setMinimumHeight(76); self.excel_btn.setStyleSheet(style); self.excel_btn.setEnabled(False)
        self.excel_btn.clicked.connect(self._export_excel)
        layout.addWidget(self.excel_btn)
        self.structure_btn = QPushButton(tr("Exporter une structure de collection  (.colstr)", self.language))
        self.structure_btn.setToolTip(tr("Structure, modèles, paramètres et référentiels, sans fiches, données ni photos.", self.language))
        self.structure_btn.setMinimumHeight(76); self.structure_btn.setStyleSheet(style); self.structure_btn.setEnabled(False)
        self.structure_btn.clicked.connect(lambda: self._export_selected("structure"))
        layout.addWidget(self.structure_btn)

        self.fiche_model_btn = QPushButton(tr("Exporter le modèle de Fiche  (.colmod)", self.language))
        self.fiche_model_btn.setToolTip(tr("Exporte uniquement le modèle de Fiche de la collection : disposition, styles, groupes, champs calculés et informations de liaison nécessaires. Aucune fiche ni donnée n'est exportée.", self.language))
        self.fiche_model_btn.setMinimumHeight(76); self.fiche_model_btn.setStyleSheet(style); self.fiche_model_btn.setEnabled(False)
        self.fiche_model_btn.clicked.connect(self._export_fiche_model)
        layout.addWidget(self.fiche_model_btn)

        self.table_model_btn = QPushButton(tr("Exporter un modèle de Tableau  (.colmod)", self.language))
        self.table_model_btn.setToolTip(tr("Choisit un modèle dans la bibliothèque Modèles de Tableaux et crée une copie échangeable .colmod. Aucune collection ni donnée n'est modifiée.", self.language))
        self.table_model_btn.setMinimumHeight(76); self.table_model_btn.setStyleSheet(style)
        self.table_model_btn.clicked.connect(self._export_table_model)
        layout.addWidget(self.table_model_btn)

        self.query_model_btn = QPushButton(tr("Exporter un modèle de Requête  (.colmod)", self.language))
        self.query_model_btn.setToolTip(tr("Choisit un modèle dans la bibliothèque Modèles de Requêtes et crée une copie échangeable .colmod. Aucune collection ni donnée n'est modifiée.", self.language))
        self.query_model_btn.setMinimumHeight(76); self.query_model_btn.setStyleSheet(style)
        self.query_model_btn.clicked.connect(self._export_query_model)
        layout.addWidget(self.query_model_btn)

        self.report_model_btn = QPushButton(tr("Exporter un modèle d'État  (.colmod)", self.language))
        self.report_model_btn.setToolTip(tr("Choisit un modèle dans la bibliothèque Modèles d’États et crée une copie échangeable .colmod. Aucune collection ni donnée n'est modifiée.", self.language))
        self.report_model_btn.setMinimumHeight(76); self.report_model_btn.setStyleSheet(style)
        self.report_model_btn.clicked.connect(self._export_report_model)
        layout.addWidget(self.report_model_btn)

        note = QLabel(
            "La structure exportée reprend le principe déjà utilisé par « Dupliquer la structure de la collection » "
            "dans la Boîte à outils."
        )
        note.setWordWrap(True); note.setStyleSheet("font-style: italic;")
        note.setText(tr(note.text(), self.language))
        layout.addWidget(note)
        layout.addStretch(1)
        row = QHBoxLayout(); back_btn = QPushButton(tr("Retour", self.language)); back_btn.clicked.connect(self.close); row.addWidget(back_btn)
        row.addStretch(1); close_btn = QPushButton(tr("Fermer", self.language)); close_btn.clicked.connect(self._close_all); row.addWidget(close_btn)
        layout.addLayout(row)

    def _load_folders(self) -> None:
        self._folder_store.load()
        self.folder_combo.blockSignals(True); self.folder_combo.clear()
        self.folder_combo.addItem(tr("— Aucun dossier sélectionné —", self.language), None)
        for folder in self._folder_store.ordered_folders():
            self.folder_combo.addItem(folder, folder)
        self.folder_combo.setCurrentIndex(0)
        self.folder_combo.blockSignals(False)
        self._load_collections()

    def _load_collections(self, *_args) -> None:
        self.external_path_label.clear()
        active = self.folder_combo.currentData()
        if not active:
            self._collections = []
            self.collection_combo.blockSignals(True); self.collection_combo.clear()
            self.collection_combo.addItem(tr("— Aucune collection sélectionnée —", self.language), None)
            self.collection_combo.setCurrentIndex(0); self.collection_combo.blockSignals(False)
            self._selection_changed()
            return
        all_items = [dict(x) for x in self._manager.discover_collection_files()]
        self._collections = [x for x in all_items if self._folder_store.folder_for(x.get("_database_path", "")).casefold() == active.casefold()]
        self._collections.sort(key=lambda x: str(x.get("name") or "").casefold())
        self.collection_combo.blockSignals(True); self.collection_combo.clear()
        self.collection_combo.addItem(tr("— Aucune collection sélectionnée —", self.language), None)
        for item in self._collections:
            self.collection_combo.addItem(str(item.get("name") or Path(str(item.get("_database_path") or "")).stem), item)
        self.collection_combo.setCurrentIndex(0); self.collection_combo.blockSignals(False)
        self._selection_changed()

    def _browse_external_collection(self) -> None:
        """Sélectionne une base autonome sans l'ajouter au Workspace."""
        start = self._collections_folder
        try:
            saved = self._external_last_dir_file.read_text(encoding="utf-8").strip()
            if saved and Path(saved).is_dir():
                start = Path(saved)
        except OSError:
            pass
        filename, _ = QFileDialog.getOpenFileName(
            self,
            tr("Choisir une collection G-Skol", self.language),
            str(start),
            tr("Collections G-Skol (*.coldb)", self.language),
        )
        if not filename:
            return
        source = Path(filename).resolve()
        try:
            # Ne pas ouvrir une base SQLite en écriture, même pour inspection.
            with sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as con:
                quick = con.execute("PRAGMA quick_check").fetchone()
                if not quick or str(quick[0]).lower() != "ok":
                    raise ValueError("Fichier de collection endommagé.")
                tables = {r[0] for r in con.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'")}
                if not {"collections", "records"}.issubset(tables):
                    raise ValueError("Ce fichier n'est pas une collection G-Skol valide.")
                rows = con.execute("SELECT id, name FROM collections ORDER BY id").fetchall()
            if len(rows) != 1:
                raise ValueError("Le fichier doit contenir une seule collection G-Skol.")
            cid, name = rows[0]
            item = {"id": int(cid), "name": str(name or source.stem),
                    "_database_path": str(source), "_standalone_file": True,
                    "_external_export": True}
        except (OSError, sqlite3.Error, ValueError) as exc:
            QMessageBox.warning(self, tr("Exportation", self.language), str(exc))
            return
        # Évite qu'un dossier Workspace resté sélectionné fournisse une
        # autre collection aux méthodes d'exportation.
        self.folder_combo.blockSignals(True)
        self.folder_combo.setCurrentIndex(0)
        self.folder_combo.blockSignals(False)
        self.collection_combo.blockSignals(True)
        self.collection_combo.clear()
        self.collection_combo.addItem(item["name"], item)
        self.collection_combo.setCurrentIndex(0)
        self.collection_combo.blockSignals(False)
        self.external_path_label.setText(str(source))
        self.external_path_label.setToolTip(str(source))
        try:
            self._external_last_dir_file.parent.mkdir(parents=True, exist_ok=True)
            self._external_last_dir_file.write_text(str(source.parent), encoding="utf-8")
        except OSError:
            pass
        self._selection_changed()

    def _selection_changed(self, *_args) -> None:
        ok = isinstance(self.collection_combo.currentData(), dict)
        self.full_btn.setEnabled(ok); self.excel_btn.setEnabled(ok); self.structure_btn.setEnabled(ok); self.fiche_model_btn.setEnabled(ok)

    def _export_save_file(self, title: str, suggested: str, file_filter: str) -> str:
        """Sélection de destination ; confirmation de remplacement dans la langue active."""
        output, _ = QFileDialog.getSaveFileName(
            self, title, suggested, file_filter, options=QFileDialog.Option.DontConfirmOverwrite
        )
        if not output:
            return ""
        path = Path(output)
        expected = Path(suggested).suffix
        if expected and path.suffix.casefold() != expected.casefold():
            path = path.with_suffix(expected)
        if path.exists():
            language = str(self.language or 'fr').lower()
            if language.startswith('de'):
                title_text = 'Speichern bestätigen'
                message = f'Die Datei „{path.name}“ ist bereits vorhanden.\nMöchten Sie sie ersetzen?'
                yes_text, no_text = 'Ja', 'Nein'
            elif language.startswith('en'):
                title_text = 'Confirm save'
                message = f'The file “{path.name}” already exists.\nDo you want to replace it?'
                yes_text, no_text = 'Yes', 'No'
            else:
                title_text = "Confirmer l’enregistrement"
                message = f'{path.name} existe déjà.\nVoulez-vous le remplacer ?'
                yes_text, no_text = 'Oui', 'Non'
            box = QMessageBox(self)
            box.setWindowTitle(title_text)
            box.setIcon(QMessageBox.Icon.Warning)
            box.setText(message)
            yes = box.addButton(yes_text, QMessageBox.ButtonRole.YesRole)
            box.addButton(no_text, QMessageBox.ButtonRole.NoRole)
            box.exec()
            if box.clickedButton() is not yes:
                return ""
        return str(path)

    def _export_success_message(self, category: str, name: str, output: Path) -> str:
        language = str(self.language or 'fr').lower()
        names = {
            'complete': ('vollständige Sammlung', 'complete collection', 'collection complète'),
            'structure': ('Sammlungsstruktur', 'collection structure', 'structure de collection'),
            'fiche': ('Datensatzvorlage', 'Record template', 'modèle de Fiche'),
            'tableau': ('Tabellenvorlage', 'Table template', 'modèle de Tableau'),
            'requete': ('Abfragevorlage', 'Query template', 'modèle de Requête'),
            'etat': ('Berichtsvorlage', 'Report template', "modèle d'État"),
        }
        de, en, fr = names[category]
        if language.startswith('de'):
            return f'Die {de} „{name}“ wurde erfolgreich exportiert.\n\n{output}'
        if language.startswith('en'):
            return f'The {en} “{name}” has been exported.\n\n{output}'
        return f'Le {fr} « {name} » a été exporté.\n\n{output}' if category not in ('complete', 'structure') else f'La {fr} « {name} » a été exportée.\n\n{output}'

    def _export_report_model(self) -> None:
        """Exporte un modèle d'État déjà enregistré dans sa bibliothèque."""
        model_root = library_root(Path(WORKSPACE), "etat")
        filename = choose_model_open_path(self, model_root, "Modèles d’États")
        if not filename:
            return
        try:
            envelope = read_model(filename, expected_kind="etat")
        except Exception as exc:
            QMessageBox.warning(self, tr("Modèle non valide", self.language), str(exc)); return
        documents_dir = Path.home() / "Documents"
        if not documents_dir.exists():
            documents_dir = Path.home()
        default_name = str(envelope.get("name") or Path(filename).stem).strip() or Path(filename).stem
        safe = CollectionManager._safe_filename(default_name + " - Modèle État")
        output = self._export_save_file(
            tr("Exporter un modèle d'État", self.language), str(documents_dir / f"{safe}.colmod"),
            tr("Modèle G-Skol (*.colmod)", self.language)
        )
        if not output:
            return
        out = Path(output)
        if out.suffix.casefold() != ".colmod":
            out = out.with_suffix(".colmod")
        try:
            # Copie logique fidèle de l'enveloppe de bibliothèque : le manifeste
            # créé lors de l'enregistrement de l'État est conservé intégralement.
            write_model(
                out, kind="etat", name=default_name,
                source_collection=str(envelope.get("source_collection") or ""),
                payload=dict(envelope.get("payload") or {}),
                field_manifest=dict(envelope.get("field_manifest") or {}),
            )
            QMessageBox.information(self, tr("Exportation terminée", self.language), self._export_success_message("etat", default_name, out))
        except Exception as exc:
            try:
                if out.exists(): out.unlink()
            except Exception:
                pass
            QMessageBox.critical(self, tr("Exportation impossible", self.language), str(exc))

    def _export_query_model(self) -> None:
        """Exporte un modèle de Requête déjà enregistré dans sa bibliothèque."""
        model_root = library_root(Path(WORKSPACE), "requete")
        filename = choose_model_open_path(self, model_root, "Modèles de Requêtes")
        if not filename:
            return
        try:
            envelope = read_model(filename, expected_kind="requete")
        except Exception as exc:
            QMessageBox.warning(self, tr("Modèle non valide", self.language), str(exc)); return
        documents_dir = Path.home() / "Documents"
        if not documents_dir.exists():
            documents_dir = Path.home()
        default_name = str(envelope.get("name") or Path(filename).stem).strip() or Path(filename).stem
        safe = CollectionManager._safe_filename(default_name + " - Modèle Requête")
        output = self._export_save_file(
            tr("Exporter un modèle de Requête", self.language), str(documents_dir / f"{safe}.colmod"),
            tr("Modèle G-Skol (*.colmod)", self.language)
        )
        if not output:
            return
        out = Path(output)
        if out.suffix.casefold() != ".colmod":
            out = out.with_suffix(".colmod")
        try:
            write_model(
                out, kind="requete", name=default_name,
                source_collection=str(envelope.get("source_collection") or ""),
                payload=dict(envelope.get("payload") or {}),
                field_manifest=dict(envelope.get("field_manifest") or {}),
            )
            QMessageBox.information(self, tr("Exportation terminée", self.language), self._export_success_message("requete", default_name, out))
        except Exception as exc:
            try:
                if out.exists(): out.unlink()
            except Exception:
                pass
            QMessageBox.critical(self, tr("Exportation impossible", self.language), str(exc))

    def _export_table_model(self) -> None:
        """Exporte un modèle de Tableau déjà enregistré dans sa bibliothèque."""
        model_root = library_root(Path(WORKSPACE), "tableau")
        filename = choose_model_open_path(self, model_root, "Modèles de Tableaux")
        if not filename:
            return
        try:
            envelope = read_model(filename, expected_kind="tableau")
        except Exception as exc:
            QMessageBox.warning(self, tr("Modèle non valide", self.language), str(exc)); return
        documents_dir = Path.home() / "Documents"
        if not documents_dir.exists():
            documents_dir = Path.home()
        default_name = str(envelope.get("name") or Path(filename).stem).strip() or Path(filename).stem
        safe = CollectionManager._safe_filename(default_name + " - Modèle Tableau")
        output = self._export_save_file(
            tr("Exporter un modèle de Tableau", self.language), str(documents_dir / f"{safe}.colmod"),
            tr("Modèle G-Skol (*.colmod)", self.language)
        )
        if not output:
            return
        out = Path(output)
        if out.suffix.casefold() != ".colmod":
            out = out.with_suffix(".colmod")
        try:
            write_model(
                out, kind="tableau", name=default_name,
                source_collection=str(envelope.get("source_collection") or ""),
                payload=dict(envelope.get("payload") or {}),
                field_manifest=dict(envelope.get("field_manifest") or {}),
            )
            QMessageBox.information(self, tr("Exportation terminée", self.language), self._export_success_message("tableau", default_name, out))
        except Exception as exc:
            try:
                if out.exists(): out.unlink()
            except Exception:
                pass
            QMessageBox.critical(self, tr("Exportation impossible", self.language), str(exc))

    def _export_fiche_model(self) -> None:
        """Exporte le modèle de Fiche courant dans un fichier échangeable .colmod."""
        item = self.collection_combo.currentData()
        if not isinstance(item, dict):
            return
        source = Path(str(item.get("_database_path") or ""))
        if not source.exists():
            QMessageBox.warning(self, tr("Exportation", self.language), tr("Le fichier de la collection sélectionnée est introuvable.", self.language))
            return
        cid = int(item.get("id") or 0)
        name = str(item.get("name") or source.stem).strip() or source.stem
        documents_dir = Path.home() / "Documents"
        if not documents_dir.exists():
            documents_dir = Path.home()
        safe = CollectionManager._safe_filename(name + " - Modèle Fiche")
        output = self._export_save_file(
            tr("Exporter le modèle de Fiche", self.language), str(documents_dir / f"{safe}.colmod"),
            tr("Modèle G-Skol (*.colmod)", self.language)
        )
        if not output:
            return
        out = Path(output)
        if out.suffix.casefold() != ".colmod":
            out = out.with_suffix(".colmod")
        try:
            manager = ModelManager(source)
            keys = list(manager.all_model_keys(cid))
            visible = set(manager.visible_fields(cid))
            labels = manager.custom_labels(cid)
            placement = manager.field_placement(cid)
            # Ces deux lectures ont besoin des informations de placement / ordre
            # utilisées par le ModelManager pour reconstruire leurs valeurs par défaut.
            visual_positions = manager.visual_positions(cid, placement)
            visual_sizes = manager.visual_sizes(cid)
            tabs = manager.tab_order(cid, keys)
            tab_positions = {key: pos for pos, key in enumerate(tabs)}
            payload = {
                "field_keys": keys,
                "visible": {k: k in visible for k in keys},
                "labels": {k: str(labels.get(k) or (getattr(FIELD_BY_KEY.get(k), "label", None) if FIELD_BY_KEY.get(k) else None) or k) for k in keys},
                "blocks": {k: str(placement.get(k, ("", 0))[0] or "") for k in keys},
                "positions": {k: int(placement.get(k, ("", 0))[1] or 0) for k in keys},
                "tab_positions": {k: int(tab_positions.get(k, 0)) for k in keys},
                "visual_positions": {k: list(visual_positions.get(k, (0, 0))) for k in keys},
                "visual_sizes": {k: list(visual_sizes.get(k, (0, 0))) for k in keys},
                "sheet_background": manager.sheet_background(cid),
                "field_masters": sorted(manager.field_masters(cid)),
                "field_links": dict(manager.field_links(cid)),
                "field_styles": manager.field_styles(cid),
                "group_styles": manager.group_styles(cid),
            }
            # Même nettoyage que l'enregistrement depuis l'Atelier : seuls les champs
            # réellement présents sur la Fiche voyagent dans le modèle échangeable.
            saved_keys = collect_model_field_keys("fiche", payload)
            payload = remap_model_payload("fiche", payload, {k: k for k in saved_keys})
            manifest = build_field_manifest(manager, cid, saved_keys)
            write_model(
                out, kind="fiche", name=out.stem, source_collection=name,
                payload=payload, field_manifest=manifest,
            )
            QMessageBox.information(
                self, tr("Exportation terminée", self.language),
                self._export_success_message("fiche", name, out)
            )
        except Exception as exc:
            try:
                if out.exists(): out.unlink()
            except Exception:
                pass
            QMessageBox.critical(self, tr("Exportation impossible", self.language), f"Le modèle n'a pas pu être exporté.\n\n{exc}")

    @staticmethod
    def _empty_database_collection(db_path: Path, collection_id: int) -> None:
        """Même principe que Boîte à outils > Dupliquer la structure."""
        con = sqlite3.connect(db_path)
        try:
            con.execute("PRAGMA foreign_keys=OFF")
            tables = {str(r[0]) for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
            record_ids = [int(r[0]) for r in con.execute("SELECT id FROM records WHERE collection_id=?", (collection_id,)).fetchall()] if "records" in tables else []
            if record_ids:
                placeholders = ",".join("?" for _ in record_ids)
                for table in ("record_custom_values", "record_extra_photos"):
                    if table in tables:
                        con.execute(f'DELETE FROM "{table}" WHERE record_id IN ({placeholders})', record_ids)
            if "records" in tables:
                con.execute("DELETE FROM records WHERE collection_id=?", (collection_id,))
            # Certaines versions stockent des photos dans des tables liées directement à la collection.
            for table in tables:
                if "photo" not in table.casefold() or table in {"record_extra_photos"}:
                    continue
                cols = {str(r[1]) for r in con.execute(f'PRAGMA table_info("{table}")').fetchall()}
                if "collection_id" in cols:
                    con.execute(f'DELETE FROM "{table}" WHERE collection_id=?', (collection_id,))
            # Remet le compteur SQLite des fiches à zéro si cette séquence existe.
            if "sqlite_sequence" in tables:
                try: con.execute("DELETE FROM sqlite_sequence WHERE name='records'")
                except Exception: pass
            con.commit()
        finally:
            con.close()

    def _export_excel(self) -> None:
        """Export complet vers une feuille Excel, sans modifier la base."""
        from core.export_excel import export_collection_xlsx
        item = self.collection_combo.currentData()
        if not isinstance(item, dict):
            return
        source = Path(str(item.get("_database_path") or ""))
        if not source.is_file():
            QMessageBox.warning(self, tr("Exportation", self.language), tr("Collection introuvable.", self.language))
            return
        name = str(item.get("name") or source.stem).strip() or source.stem
        safe = CollectionManager._safe_filename(name)
        destination = self._export_save_file(
            tr("Exporter vers Excel", self.language),
            str((Path.home() / "Documents" if (Path.home() / "Documents").exists() else Path.home()) / (safe + ".xlsx")),
            tr("Classeur Excel (*.xlsx)", self.language))
        if not destination:
            return
        output = Path(destination)
        try:
            count = export_collection_xlsx(source, int(item["id"]), output)
            language = self.language.lower()
            msg = (f"{count} records exported to Excel.\n\n{output}" if language.startswith("en")
                   else f"{count} Datensätze nach Excel exportiert.\n\n{output}" if language.startswith("de")
                   else f"{count} fiches exportées vers Excel.\n\n{output}")
            QMessageBox.information(self, tr("Exportation terminée", self.language), msg)
        except Exception as exc:
            try:
                output.unlink(missing_ok=True)
            except OSError:
                pass
            QMessageBox.critical(self, tr("Exportation impossible", self.language), str(exc))

    def _export_selected(self, kind: str) -> None:
        item = self.collection_combo.currentData()
        if not isinstance(item, dict): return
        source = Path(str(item.get("_database_path") or ""))
        if not source.exists():
            QMessageBox.warning(self, tr("Exportation", self.language), tr("Le fichier de la collection sélectionnée est introuvable.", self.language)); return
        name = str(item.get("name") or source.stem).strip() or source.stem
        ext = ".coldb" if kind == "complete" else ".colstr"
        label = "collection complète" if kind == "complete" else "structure de collection"
        label_en = "complete collection" if kind == "complete" else "collection structure"
        safe = CollectionManager._safe_filename(name)
        documents_dir = Path.home() / "Documents"
        if not documents_dir.exists():
            documents_dir = Path.home()
        output = self._export_save_file(tr(f"Exporter la {label}", self.language), str(documents_dir / f"{safe}{ext}"), tr(f"Fichier G-Skol (*{ext})", self.language))
        if not output: return
        out = Path(output)
        if out.suffix.casefold() != ext: out = out.with_suffix(ext)
        temp_db: Path | None = None
        try:
            # Une collection complète reste une vraie base .coldb directement exploitable.
            if kind == "complete":
                if source.resolve() == out.resolve():
                    raise ValueError("Le fichier de destination doit être différent de la collection d'origine.")
                out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, out)
                QMessageBox.information(self, tr(tr("Exportation terminée", self.language), self.language), self._export_success_message(kind, name, out))
                return
            db_to_pack = source
            if kind == "structure":
                # La copie de travail vit exclusivement dans le dossier temporaire
                # système : aucun fichier intermédiaire ne doit apparaître parmi les
                # collections G-Skol (notamment dans « Non classées »).
                tmp_dir = Path(tempfile.mkdtemp(prefix="gskol-export-structure-"))
                temp_db = tmp_dir / "collection.db"
                src_conn = sqlite3.connect(source)
                try:
                    dst_conn = sqlite3.connect(temp_db)
                    try:
                        src_conn.backup(dst_conn)
                        dst_conn.commit()
                    finally:
                        dst_conn.close()
                finally:
                    src_conn.close()

                cid = int(item.get("id") or 0)
                con = sqlite3.connect(temp_db)
                try:
                    con.execute("PRAGMA foreign_keys=OFF")
                    tables = [str(r[0]) for r in con.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                    ).fetchall()]
                    for table in tables:
                        cols = {str(r[1]) for r in con.execute(f'PRAGMA table_info("{table}")').fetchall()}
                        if table != "collections" and "collection_id" in cols:
                            con.execute(f'DELETE FROM "{table}" WHERE collection_id <> ?', (cid,))
                    if "referential_values" in tables and "referential_definitions" in tables:
                        con.execute("DELETE FROM referential_values WHERE definition_id NOT IN (SELECT id FROM referential_definitions)")
                    if "collections" in tables:
                        con.execute("DELETE FROM collections WHERE id <> ?", (cid,))
                        con.execute("UPDATE collections SET name=? WHERE id=?", (name, cid))
                    con.commit()
                finally:
                    con.close()
                self._empty_database_collection(temp_db, cid)
                db_to_pack = temp_db
            manifest = {
                "format": "G-Skol",
                "package_type": "collection" if kind == "complete" else "structure",
                "format_version": 1,
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "collection_name": name,
                "collection_folder": (source.parent.name if item.get("_external_export") else (self.folder_combo.currentText() or UNCLASSIFIED)),
                "database_file": "collection.db",
            }
            out.parent.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
                zf.write(db_to_pack, "collection.db")
                zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
            QMessageBox.information(self, tr(tr("Exportation terminée", self.language), self.language), self._export_success_message(kind, name, out))
        except Exception as exc:
            try:
                if out.exists() and out.resolve() != source.resolve(): out.unlink()
            except Exception: pass
            QMessageBox.critical(self, tr(tr("Exportation impossible", self.language), self.language), (f"The export could not be created.\n\n{exc}" if self.language.lower().startswith("en") else f"L'export n'a pas pu être créé.\n\n{exc}"))
        finally:
            if temp_db is not None:
                try:
                    temp_parent = temp_db.parent
                    temp_db.unlink(missing_ok=True)
                    if temp_parent.name.startswith("gskol-export-structure-"):
                        shutil.rmtree(temp_parent, ignore_errors=True)
                except Exception:
                    pass

    def _close_all(self) -> None:
        top = self.parentWidget(); self.close()
        if isinstance(top, QDialog): top.close()


class ExternalDataImportDialog(QDialog):
    """Point d'entrée de l'import de données complémentaires dans une collection existante.

    11.7.64 : première étape sûre. On choisit la collection cible et une source
    Access, puis G-Skol analyse uniquement la structure (tables/champs/lignes).
    Aucune donnée n'est encore écrite dans la collection à ce stade.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.language = str(getattr(parent, "language", "fr") or "fr")
        self.setWindowTitle(tr("Ajouter des fiches depuis une source extérieure", self.language))
        self.resize(930, 700)
        self.setMinimumSize(820, 620)
        self.destination_path: Path | None = None
        self.source_path: Path | None = None
        self._external_access_structure: dict = {}
        self._external_source_kind = "access"
        self._external_excel_workbook: dict = {}
        self._external_matching_verified = False
        self._external_selected_rows: list[dict] = []
        self._build_ui()
        self._load_known_collections()
        translate_widget_tree(self, self.language)

    @staticmethod
    def _workspace_collections_folder() -> Path:
        folder = Path(WORKSPACE) / "Collections"
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 18)
        root.setSpacing(11)

        title = QLabel("Ajouter des fiches depuis une source extérieure")
        title.setStyleSheet("font-size: 23px; font-weight: 800;")
        root.addWidget(title)
        intro = QLabel(
            "Cette fonction ajoute de nouvelles fiches à la suite des fiches déjà présentes dans la collection G-Skol. "
            "Les fiches existantes ne sont jamais modifiées. Sources disponibles : Access, Excel .xlsx et CSV / TXT / TSV ; les autres formats suivront."
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        dest_box = QFrame(); dest_box.setFrameShape(QFrame.Shape.StyledPanel)
        dl = QVBoxLayout(dest_box); dl.setContentsMargins(14, 12, 14, 12); dl.setSpacing(7)
        h = QLabel("1. Collection G-Skol qui recevra les nouvelles fiches"); h.setStyleSheet("font-size:15px; font-weight:700;")
        dl.addWidget(h)
        row = QHBoxLayout()
        self.choose_dest_btn = QPushButton("Sélectionner une collection…")
        self.choose_dest_btn.clicked.connect(self._choose_destination)
        row.addWidget(self.choose_dest_btn)
        self.collection_combo = QComboBox()
        self.collection_combo.currentIndexChanged.connect(self._on_destination_changed)
        row.addWidget(self.collection_combo, 1)
        dl.addLayout(row)
        self.dest_label = QLabel("Aucune collection sélectionnée."); self.dest_label.setWordWrap(True)
        dl.addWidget(self.dest_label)
        root.addWidget(dest_box)

        src_box = QFrame(); src_box.setFrameShape(QFrame.Shape.StyledPanel)
        sl = QVBoxLayout(src_box); sl.setContentsMargins(14, 12, 14, 12); sl.setSpacing(7)
        h2 = QLabel("2. Source contenant les fiches à ajouter"); h2.setStyleSheet("font-size:15px; font-weight:700;")
        sl.addWidget(h2)
        self.source_tabs = QTabWidget(); self.source_tabs.setDocumentMode(True)
        for label in ["Access", "Excel", "CSV / TXT / TSV", "ODS", "DBF", "SQLite"]:
            self.source_tabs.addTab(QWidget(), label)
        # ODS, DBF et SQLite sont disponibles pour l’ajout de fiches.
        self.source_tabs.setTabEnabled(5, True)
        self.source_tabs.setToolTip(tr("Access, Excel .xlsx et CSV / TXT / TSV utilisent le même parcours : analyse, correspondances, sélection des fiches, ajout.", self.language))
        self.source_tabs.currentChanged.connect(self._external_source_tab_changed)
        self.source_tabs.setFixedHeight(30)
        sl.addWidget(self.source_tabs)
        row2 = QHBoxLayout()
        self.choose_source_btn = QPushButton("Choisir une base Access…")
        self.choose_source_btn.clicked.connect(self._choose_access_source)
        row2.addWidget(self.choose_source_btn)
        self.analyse_btn = QPushButton("Analyser les données")
        self.analyse_btn.setEnabled(False)
        self.analyse_btn.clicked.connect(self._analyse_access)
        row2.addWidget(self.analyse_btn)
        row2.addStretch(1)
        sl.addLayout(row2)
        self.source_label = QLabel("Aucune base Access sélectionnée."); self.source_label.setWordWrap(True)
        sl.addWidget(self.source_label)
        root.addWidget(src_box)

        self.external_structure_label = QLabel("3. Tables détectées dans la source Access")
        self.external_structure_label.setStyleSheet("font-size:15px; font-weight:700;")
        root.addWidget(self.external_structure_label)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([tr("Table / Champ", self.language), tr("Type", self.language), tr("Lignes", self.language)])
        # 11.7.70.21 — mode radin strict : hauteur fixe, ascenseur au-delà.
        self.tree.setFixedHeight(104)
        self.tree.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.tree.setAlternatingRowColors(True)
        self.tree.setRootIsDecorated(True)
        self.tree.header().resizeSection(0, 470)
        self.tree.header().resizeSection(1, 190)
        self.tree.header().resizeSection(2, 100)
        root.addWidget(self.tree, 0)

        # 11.7.70.26.25 — la table source appartient désormais au bloc 3.
        table_row = QHBoxLayout()
        self.external_table_prompt = QLabel("Table contenant les fiches à ajouter :")
        table_row.addWidget(self.external_table_prompt)
        self.source_table_combo = QComboBox()
        self.source_table_combo.currentIndexChanged.connect(self._external_table_changed)
        table_row.addWidget(self.source_table_combo, 1)
        root.addLayout(table_row)

        self.summary = QLabel("Aucune analyse effectuée.")
        self.summary.setWordWrap(True); self.summary.setStyleSheet("font-style: italic;")
        root.addWidget(self.summary)

        # 11.7.70.26.25 — aucun rapprochement avec les fiches G-Skol existantes.
        # Ces contrôles restent internes pour compatibilité avec l'ancien code,
        # mais aucun bloc « ancien rapprochement » n'est affiché.
        self.match_box = QFrame(self); self.match_box.setVisible(False)
        self.source_key_label = QLabel(self.match_box); self.source_key_combo = QComboBox(self.match_box)
        self.dest_key_label = QLabel(self.match_box); self.dest_key_combo = QComboBox(self.match_box)
        self.preview_match_btn = QPushButton(self.match_box); self.match_summary = QLabel(self.match_box)

        # 11.7.70.22 — étape 5, toujours sans écriture : correspondance des champs.
        self.fields_box = QFrame(self); self.fields_box.setFrameShape(QFrame.Shape.StyledPanel)
        fl = QVBoxLayout(self.fields_box); fl.setContentsMargins(14, 10, 14, 10); fl.setSpacing(6)
        fh = QLabel("4. Correspondance des champs")
        fh.setStyleSheet("font-size:15px; font-weight:700;"); fl.addWidget(fh)
        fhelp = QLabel(
            "Pour chaque champ source, choisissez un champ G-Skol existant, « Ne pas importer » ou « Créer un nouveau champ… ». "
            "À ce stade, rien n’est créé ni modifié."
        )
        fhelp.setWordWrap(True); fl.addWidget(fhelp)
        self.external_sort_fields_cb = QCheckBox(tr("Classer les champs source par ordre alphabétique (A → Z)", self.language))
        self.external_sort_fields_cb.setChecked(True)
        self.external_sort_fields_cb.toggled.connect(self._external_sort_destination_choices)
        fl.addWidget(self.external_sort_fields_cb)
        self.fields_table = QTableWidget(0, 4)
        self.fields_table.setHorizontalHeaderLabels(["N°", tr("Champ source", self.language), tr("Type du champ", self.language), tr("Destination G-Skol / action", self.language)])
        self.fields_table.verticalHeader().setVisible(False)
        self.fields_table.setAlternatingRowColors(True)
        self.fields_table.setMinimumHeight(260)
        self.fields_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.fields_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.fields_table.setColumnWidth(0, 46)
        self.fields_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.fields_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.fields_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        fl.addWidget(self.fields_table)
        self.fields_summary = QLabel("Choisissez la destination G-Skol de chaque champ source.")
        self.fields_summary.setWordWrap(True); self.fields_summary.setStyleSheet("font-style: italic;")
        fl.addWidget(self.fields_summary)
        # Brique 1.3 : signalement immédiat des destinations en double.
        self.external_duplicate_warning = QLabel("")
        self.external_duplicate_warning.setWordWrap(True)
        self.external_duplicate_warning.setStyleSheet("color:#B00020; font-weight:600;")
        self.external_duplicate_warning.setVisible(False)
        fl.addWidget(self.external_duplicate_warning)
        self.fields_box.setVisible(False)  # Phase 4 is displayed in its own dialog.

        note = QLabel(
            "Sécurité : les fiches G-Skol existantes ne seront jamais modifiées. Après la correspondance des champs, "
            "vous pourrez choisir exactement quelles lignes source seront ajoutées comme nouvelles fiches."
        )
        note.setWordWrap(True)
        note.setStyleSheet("background:#FFF8E7; border:1px solid #D7C48A; padding:8px;")
        root.addWidget(note)

        # The Phase 4 action button lives in the dedicated Field mapping dialog.
        self.external_preview_btn = QPushButton("Choisir les fiches à ajouter…", self)
        self.external_preview_btn.setEnabled(False)
        self.external_preview_btn.clicked.connect(self._prepare_external_preview)
        self.external_preview_btn.setVisible(False)

        buttons = QHBoxLayout(); buttons.addStretch(1)
        close_btn = QPushButton(tr("Fermer", self.language)); close_btn.clicked.connect(self.close); buttons.addWidget(close_btn)
        root.addLayout(buttons)

    def _load_known_collections(self) -> None:
        self.collection_combo.blockSignals(True)
        self.collection_combo.clear()
        folder = self._workspace_collections_folder()
        for path in sorted(folder.iterdir(), key=lambda p: p.name.casefold()) if folder.exists() else []:
            if not path.is_file() or path.suffix.casefold() != ".coldb":
                continue
            if path.name.casefold() in {"micromin3.db", ".mm3-system.db"}:
                continue
            try:
                collections = CollectionManager(path).inspect_collections()
            except Exception:
                continue
            for item in collections:
                self.collection_combo.addItem(
                    str(item.get("name") or path.stem),
                    {"path": str(path.resolve()), "id": int(item.get("id") or 0)},
                )
        # 11.7.70.17 — aucune collection ne doit être choisie arbitrairement à l'ouverture.
        self.collection_combo.insertItem(0, tr("— Aucune collection sélectionnée —", self.language), None)
        self.collection_combo.setCurrentIndex(0)
        self.collection_combo.blockSignals(False)
        self.destination_path = None
        self.dest_label.setText(tr("Aucune collection sélectionnée.", self.language))

    def _on_destination_changed(self) -> None:
        data = self.collection_combo.currentData()
        if isinstance(data, dict) and data.get("path"):
            self.destination_path = Path(str(data["path"]))
            self.dest_label.setText(
                tr("✓ Collection sélectionnée : {name} — {file}", self.language).format(name=self.collection_combo.currentText(), file=self.destination_path.name)
            )
            self.choose_source_btn.setFocus(Qt.FocusReason.OtherFocusReason)
        else:
            self.destination_path = None
            self.dest_label.setText(tr("Aucune collection sélectionnée.", self.language))

    def _choose_destination(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self, "Choisir une collection G-Skol existante", str(self._workspace_collections_folder()),
            tr("Collections G-Skol (*.coldb);;Tous les fichiers (*.*)", self.language)
        )
        if not filename:
            return
        path = Path(filename)
        try:
            collections = CollectionManager(path).inspect_collections()
        except Exception as exc:
            QMessageBox.warning(self, "Collection G-Skol invalide", str(exc)); return
        if not collections:
            QMessageBox.warning(self, "Collection G-Skol", "Aucune collection n'a été trouvée dans ce fichier."); return
        self.collection_combo.blockSignals(True)
        self.collection_combo.clear()
        for item in collections:
            self.collection_combo.addItem(
                str(item.get("name") or path.stem),
                {"path": str(path.resolve()), "id": int(item.get("id") or 0)},
            )
        self.collection_combo.blockSignals(False)
        self.collection_combo.setCurrentIndex(0)
        self._on_destination_changed()

    def _external_source_tab_changed(self, index: int) -> None:
        self._external_source_kind = (
            "excel" if index == 1 else
            "text" if index == 2 else
            "ods" if index == 3 else
            "dbf" if index == 4 else
            "sqlite" if index == 5 else
            "access"
        )
        self.source_path = None
        self._external_access_structure = {}
        self._external_excel_workbook = {}
        self.tree.clear(); self.source_table_combo.clear()
        self.fields_box.setVisible(False); self.external_preview_btn.setEnabled(False)
        self.analyse_btn.setEnabled(False)
        if self._external_source_kind == "excel":
            self.external_structure_label.setText(tr("3. Feuilles détectées dans la source Excel", self.language))
            self.external_table_prompt.setText(tr("Feuille contenant les fiches à ajouter :", self.language))
            self.choose_source_btn.setText(tr("Choisir un fichier Excel…", self.language))
            self.source_label.setText(tr("Aucun fichier Excel sélectionné.", self.language))
            self.choose_source_btn.clicked.disconnect()
            self.choose_source_btn.clicked.connect(self._choose_excel_external_source)
        elif self._external_source_kind == "text":
            self.external_structure_label.setText(tr("3. Données détectées dans la source CSV / TXT / TSV", self.language))
            self.external_table_prompt.setText(tr("Données contenant les fiches à ajouter :", self.language))
            self.choose_source_btn.setText(tr("Choisir un fichier CSV / TXT / TSV…", self.language))
            self.source_label.setText(tr("Aucun fichier CSV / TXT / TSV sélectionné.", self.language))
            self.choose_source_btn.clicked.disconnect()
            self.choose_source_btn.clicked.connect(self._choose_text_external_source)
        elif self._external_source_kind == "ods":
            self.external_structure_label.setText(tr("3. Feuilles détectées dans la source ODS", self.language))
            self.external_table_prompt.setText(tr("Feuille contenant les fiches à ajouter :", self.language))
            self.choose_source_btn.setText(tr("Choisir un fichier ODS…", self.language))
            self.source_label.setText(tr("Aucun fichier ODS sélectionné.", self.language))
            self.choose_source_btn.clicked.disconnect()
            self.choose_source_btn.clicked.connect(self._choose_ods_external_source)
        elif self._external_source_kind == "dbf":
            self.external_structure_label.setText(tr("3. Données détectées dans la source DBF", self.language))
            self.external_table_prompt.setText(tr("Données contenant les fiches à ajouter :", self.language))
            self.choose_source_btn.setText(tr("Choisir un fichier DBF…", self.language))
            self.source_label.setText(tr("Aucun fichier DBF sélectionné.", self.language))
            self.choose_source_btn.clicked.disconnect()
            self.choose_source_btn.clicked.connect(self._choose_dbf_external_source)
        elif self._external_source_kind == "sqlite":
            self.external_structure_label.setText(tr("3. Tables détectées dans la source SQLite", self.language))
            self.external_table_prompt.setText(tr("Table contenant les fiches à ajouter :", self.language))
            self.choose_source_btn.setText(tr("Choisir une base SQLite…", self.language))
            self.source_label.setText(tr("Aucune base SQLite sélectionnée.", self.language))
            self.choose_source_btn.clicked.disconnect()
            self.choose_source_btn.clicked.connect(self._choose_sqlite_external_source)
        else:
            self.external_structure_label.setText(tr("3. Tables détectées dans la source Access", self.language))
            self.external_table_prompt.setText(tr("Table contenant les fiches à ajouter :", self.language))
            self.choose_source_btn.setText(tr("Choisir une base Access…", self.language))
            self.source_label.setText(tr("Aucune base Access sélectionnée.", self.language))
            self.choose_source_btn.clicked.disconnect()
            self.choose_source_btn.clicked.connect(self._choose_access_source)

    def _choose_excel_external_source(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self, tr("Choisir le fichier Excel contenant les fiches à ajouter", self.language), "",
            tr("Classeurs Excel (*.xlsx);;Tous les fichiers (*.*)", self.language)
        )
        if not filename:
            return
        self.source_path = Path(filename)
        self.source_label.setText(tr("✓ Source Excel : {name}", self.language).format(name=self.source_path.name))
        self.analyse_btn.setEnabled(True)
        self.choose_source_btn.setStyleSheet("")
        self.analyse_btn.setStyleSheet("QPushButton { background:#fff3a6; border:2px solid #c79a00; padding:3px 8px; }")
        self.analyse_btn.setFocus(Qt.FocusReason.OtherFocusReason)
        try:
            self.analyse_btn.clicked.disconnect()
        except Exception:
            pass
        self.analyse_btn.clicked.connect(self._analyse_excel_external)

    def _analyse_excel_external(self) -> None:
        if self.source_path is None:
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor); QApplication.processEvents()
        try:
            workbook = CollectionImportDialog._read_xlsx_workbook(self.source_path)
        except Exception as exc:
            QMessageBox.critical(self, "Analyse Excel", str(exc)); return
        finally:
            if QApplication.overrideCursor() is not None: QApplication.restoreOverrideCursor()
        sheets = list(workbook.get("sheets", []) or [])
        # L’analyse est terminée : cette action n’est plus l’étape active.
        # La surbrillance passe ensuite au choix de la feuille (ou à l’étape
        # suivante lorsqu’il n’y en a qu’une).
        self.analyse_btn.setStyleSheet("")
        self._external_excel_workbook = workbook
        # Présenter les feuilles comme les tables Access au reste de l'interface.
        self._external_access_structure = {"tables": sheets, "format": "xlsx", "source_kind": "Excel"}
        self.tree.clear()
        total_fields = 0
        for sheet in sheets:
            fields = list(sheet.get("fields", []) or []); total_fields += len(fields)
            top = QTreeWidgetItem([str(sheet.get("name") or ""), tr("{count} champ(s)", self.language).format(count=len(fields)), str(sheet.get("rows") or 0)])
            self.tree.addTopLevelItem(top)
            for f in fields:
                top.addChild(QTreeWidgetItem([str(f.get("name") or ""), str(f.get("type") or "Texte"), ""]))
        self.source_table_combo.blockSignals(True); self.source_table_combo.clear()
        self.source_table_combo.addItem(tr("— Choisir une feuille —", self.language), None)
        # Ligne d'instruction visuellement distincte des vraies feuilles Excel.
        instruction_font = self.source_table_combo.font()
        instruction_font.setBold(True)
        self.source_table_combo.setItemData(0, instruction_font, Qt.ItemDataRole.FontRole)
        self.source_table_combo.setItemData(
            0, int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter),
            Qt.ItemDataRole.TextAlignmentRole
        )
        for sheet in sheets:
            name = str(sheet.get("name") or "")
            if name: self.source_table_combo.addItem(name, name)
        self.source_table_combo.setCurrentIndex(0); self.source_table_combo.blockSignals(False)
        self.fields_box.setVisible(False); self.external_preview_btn.setEnabled(False); self._external_matching_verified=False
        self.summary.setText(tr("Analyse terminée : {sheets} feuille(s), {fields} champ(s). Aucune donnée n'a été importée ni modifiée.", self.language).format(sheets=len(sheets), fields=total_fields))
        if len(sheets) == 1:
            self.source_table_combo.setCurrentIndex(1)
        elif sheets:
            self.summary.setText(self.summary.text() + " " + tr("Choisissez maintenant la feuille contenant les fiches à ajouter.", self.language))
            self.source_table_combo.setStyleSheet("QComboBox { background: #fff3a6; border: 2px solid #c79a00; padding: 2px 6px; }")
            self.source_table_combo.setFocus(Qt.FocusReason.OtherFocusReason)



    def _choose_dbf_external_source(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self, tr("Choisir le fichier DBF contenant les fiches à ajouter", self.language), "",
            tr("Fichiers DBF (*.dbf);;Tous les fichiers (*.*)", self.language)
        )
        if not filename:
            return
        self.source_path = Path(filename)
        self.source_label.setText(tr("✓ Source DBF : {name}", self.language).format(name=self.source_path.name))
        self.analyse_btn.setEnabled(True)
        self.choose_source_btn.setStyleSheet("")
        self.analyse_btn.setStyleSheet("QPushButton { background:#fff3a6; border:2px solid #c79a00; padding:3px 8px; }")
        self.analyse_btn.setFocus(Qt.FocusReason.OtherFocusReason)
        try:
            self.analyse_btn.clicked.disconnect()
        except Exception:
            pass
        self.analyse_btn.clicked.connect(self._analyse_dbf_external)

    def _analyse_dbf_external(self) -> None:
        if self.source_path is None:
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor); QApplication.processEvents()
        try:
            structure = CollectionImportDialog._read_dbf_file(self.source_path)
        except Exception as exc:
            QMessageBox.critical(self, tr("Analyse DBF impossible", self.language), str(exc)); return
        finally:
            if QApplication.overrideCursor() is not None: QApplication.restoreOverrideCursor()
        tables = list(structure.get("tables", []) or [])
        self.analyse_btn.setStyleSheet("")
        self._external_excel_workbook = {"sheets": tables}
        self._external_access_structure = structure
        self.tree.clear()
        total_fields = 0
        for table in tables:
            fields = list(table.get("fields", []) or []); total_fields += len(fields)
            top = QTreeWidgetItem([str(table.get("name") or ""), tr("{count} champ(s)", self.language).format(count=len(fields)), str(table.get("rows") or 0)])
            self.tree.addTopLevelItem(top)
            for f in fields:
                top.addChild(QTreeWidgetItem([str(f.get("name") or ""), str(f.get("type") or "Texte"), ""]))
        self.source_table_combo.blockSignals(True); self.source_table_combo.clear()
        self.source_table_combo.addItem(tr("— Choisir les données —", self.language), None)
        instruction_font = self.source_table_combo.font(); instruction_font.setBold(True)
        self.source_table_combo.setItemData(0, instruction_font, Qt.ItemDataRole.FontRole)
        self.source_table_combo.setItemData(0, int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter), Qt.ItemDataRole.TextAlignmentRole)
        for table in tables:
            name = str(table.get("name") or "")
            if name: self.source_table_combo.addItem(name, name)
        self.source_table_combo.setCurrentIndex(0); self.source_table_combo.blockSignals(False)
        self.fields_box.setVisible(False); self.external_preview_btn.setEnabled(False); self._external_matching_verified=False
        rows = sum(int(t.get("rows") or 0) for t in tables)
        self.summary.setText(tr("Analyse terminée : {tables} source(s), {fields} champ(s), {rows} ligne(s). Aucune donnée n'a été importée ni modifiée.", self.language).format(tables=len(tables), fields=total_fields, rows=rows))
        if len(tables) == 1:
            self.source_table_combo.setCurrentIndex(1)
        elif tables:
            self.source_table_combo.setStyleSheet("QComboBox { background: #fff3a6; border: 2px solid #c79a00; padding: 2px 6px; }")
            self.source_table_combo.setFocus(Qt.FocusReason.OtherFocusReason)

    def _choose_ods_external_source(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self, tr("Choisir le fichier ODS contenant les fiches à ajouter", self.language), "",
            tr("Classeurs OpenDocument (*.ods);;Tous les fichiers (*.*)", self.language)
        )
        if not filename:
            return
        self.source_path = Path(filename)
        self.source_label.setText(tr("✓ Source ODS : {name}", self.language).format(name=self.source_path.name))
        self.analyse_btn.setEnabled(True)
        self.choose_source_btn.setStyleSheet("")
        self.analyse_btn.setStyleSheet("QPushButton { background:#fff3a6; border:2px solid #c79a00; padding:3px 8px; }")
        self.analyse_btn.setFocus(Qt.FocusReason.OtherFocusReason)
        try:
            self.analyse_btn.clicked.disconnect()
        except Exception:
            pass
        self.analyse_btn.clicked.connect(self._analyse_ods_external)

    def _analyse_ods_external(self) -> None:
        if self.source_path is None:
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor); QApplication.processEvents()
        try:
            workbook = CollectionImportDialog._read_ods_workbook(self.source_path)
        except Exception as exc:
            QMessageBox.critical(self, tr("Analyse ODS impossible", self.language), str(exc)); return
        finally:
            if QApplication.overrideCursor() is not None: QApplication.restoreOverrideCursor()
        sheets = list(workbook.get("sheets", []) or [])
        self.analyse_btn.setStyleSheet("")
        self._external_excel_workbook = {"sheets": sheets}
        self._external_access_structure = {"tables": sheets, "format": "ods", "source_kind": "ODS"}
        self.tree.clear()
        total_fields = 0
        for sheet in sheets:
            fields = list(sheet.get("fields", []) or []); total_fields += len(fields)
            top = QTreeWidgetItem([str(sheet.get("name") or ""), tr("{count} champ(s)", self.language).format(count=len(fields)), str(sheet.get("rows") or 0)])
            self.tree.addTopLevelItem(top)
            for f in fields:
                top.addChild(QTreeWidgetItem([str(f.get("name") or ""), str(f.get("type") or "Texte"), ""]))
        self.source_table_combo.blockSignals(True); self.source_table_combo.clear()
        self.source_table_combo.addItem(tr("— Choisir une feuille —", self.language), None)
        instruction_font = self.source_table_combo.font(); instruction_font.setBold(True)
        self.source_table_combo.setItemData(0, instruction_font, Qt.ItemDataRole.FontRole)
        self.source_table_combo.setItemData(0, int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter), Qt.ItemDataRole.TextAlignmentRole)
        for sheet in sheets:
            name = str(sheet.get("name") or "")
            if name: self.source_table_combo.addItem(name, name)
        self.source_table_combo.setCurrentIndex(0); self.source_table_combo.blockSignals(False)
        self.fields_box.setVisible(False); self.external_preview_btn.setEnabled(False); self._external_matching_verified=False
        self.summary.setText(tr("Analyse terminée : {sheets} feuille(s), {fields} champ(s). Aucune donnée n'a été importée ni modifiée.", self.language).format(sheets=len(sheets), fields=total_fields))
        if len(sheets) == 1:
            self.source_table_combo.setCurrentIndex(1)
        elif sheets:
            self.summary.setText(self.summary.text() + " " + tr("Choisissez maintenant la feuille contenant les fiches à ajouter.", self.language))
            self.source_table_combo.setStyleSheet("QComboBox { background: #fff3a6; border: 2px solid #c79a00; padding: 2px 6px; }")
            self.source_table_combo.setFocus(Qt.FocusReason.OtherFocusReason)

    def _choose_sqlite_external_source(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self, tr("Choisir la base SQLite contenant les fiches à ajouter", self.language), "",
            tr("Bases SQLite (*.db *.sqlite *.sqlite3);;Tous les fichiers (*.*)", self.language)
        )
        if not filename:
            return
        self.source_path = Path(filename)
        self.source_label.setText(tr("✓ Source SQLite : {name}", self.language).format(name=self.source_path.name))
        self.analyse_btn.setEnabled(True)
        self.choose_source_btn.setStyleSheet("")
        self.analyse_btn.setStyleSheet("QPushButton { background:#fff3a6; border:2px solid #c79a00; padding:3px 8px; }")
        self.analyse_btn.setFocus(Qt.FocusReason.OtherFocusReason)
        try:
            self.analyse_btn.clicked.disconnect()
        except Exception:
            pass
        self.analyse_btn.clicked.connect(self._analyse_sqlite_external)

    def _analyse_sqlite_external(self) -> None:
        if self.source_path is None:
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor); QApplication.processEvents()
        try:
            structure = CollectionImportDialog._read_sqlite_database(self.source_path)
        except Exception as exc:
            QMessageBox.critical(self, tr("Analyse SQLite impossible", self.language), str(exc)); return
        finally:
            if QApplication.overrideCursor() is not None: QApplication.restoreOverrideCursor()
        tables = list(structure.get("tables", []) or [])
        self.analyse_btn.setStyleSheet("")
        self._external_excel_workbook = {"sheets": tables}
        self._external_access_structure = structure
        self.tree.clear()
        total_fields = 0
        for table in tables:
            fields = list(table.get("fields", []) or []); total_fields += len(fields)
            top = QTreeWidgetItem([str(table.get("name") or ""), tr("{count} champ(s)", self.language).format(count=len(fields)), str(table.get("rows") or 0)])
            self.tree.addTopLevelItem(top)
            for f in fields:
                top.addChild(QTreeWidgetItem([str(f.get("name") or ""), str(f.get("type") or "Texte"), ""]))
        self.source_table_combo.blockSignals(True); self.source_table_combo.clear()
        self.source_table_combo.addItem(tr("— Choisir une table —", self.language), None)
        instruction_font = self.source_table_combo.font(); instruction_font.setBold(True)
        self.source_table_combo.setItemData(0, instruction_font, Qt.ItemDataRole.FontRole)
        self.source_table_combo.setItemData(0, int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter), Qt.ItemDataRole.TextAlignmentRole)
        for table in tables:
            name = str(table.get("name") or "")
            if name: self.source_table_combo.addItem(name, name)
        self.source_table_combo.setCurrentIndex(0); self.source_table_combo.blockSignals(False)
        self.fields_box.setVisible(False); self.external_preview_btn.setEnabled(False); self._external_matching_verified=False
        rows = sum(int(t.get("rows") or 0) for t in tables)
        self.summary.setText(tr("Analyse terminée : {tables} table(s), {fields} champ(s), {rows} ligne(s). Aucune donnée n'a été importée ni modifiée.", self.language).format(tables=len(tables), fields=total_fields, rows=rows))
        if len(tables) == 1:
            self.source_table_combo.setCurrentIndex(1)
        elif tables:
            self.summary.setText(self.summary.text() + " " + tr("Choisissez maintenant la table contenant les fiches à ajouter.", self.language))
            self.source_table_combo.setStyleSheet("QComboBox { background: #fff3a6; border: 2px solid #c79a00; padding: 2px 6px; }")
            self.source_table_combo.setFocus(Qt.FocusReason.OtherFocusReason)

    def _choose_text_external_source(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self, tr("Choisir le fichier CSV / TXT / TSV contenant les fiches à ajouter", self.language), "",
            tr("Fichiers texte délimités (*.csv *.txt *.tsv);;Tous les fichiers (*.*)", self.language)
        )
        if not filename:
            return
        self.source_path = Path(filename)
        self.source_label.setText(f"✓ Source {self.source_path.suffix.lstrip('.').upper()} : {self.source_path.name}")
        self.analyse_btn.setEnabled(True)
        self.choose_source_btn.setStyleSheet("")
        self.analyse_btn.setStyleSheet("QPushButton { background:#fff3a6; border:2px solid #c79a00; padding:3px 8px; }")
        self.analyse_btn.setFocus(Qt.FocusReason.OtherFocusReason)
        try:
            self.analyse_btn.clicked.disconnect()
        except Exception:
            pass
        self.analyse_btn.clicked.connect(self._analyse_text_external)

    def _analyse_text_external(self) -> None:
        if self.source_path is None:
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor); QApplication.processEvents()
        try:
            structure = CollectionImportDialog._read_delimited_text(self.source_path)
        except Exception as exc:
            QMessageBox.critical(self, "Analyse CSV / TXT / TSV", str(exc)); return
        finally:
            if QApplication.overrideCursor() is not None: QApplication.restoreOverrideCursor()
        tables = list(structure.get("tables", []) or [])
        self.analyse_btn.setStyleSheet("")
        self._external_excel_workbook = {"sheets": tables}
        self._external_access_structure = structure
        self.tree.clear()
        total_fields = 0
        for table in tables:
            fields = list(table.get("fields", []) or []); total_fields += len(fields)
            top = QTreeWidgetItem([str(table.get("name") or ""), tr("{count} champ(s)", self.language).format(count=len(fields)), str(table.get("rows") or 0)])
            self.tree.addTopLevelItem(top)
            for f in fields:
                top.addChild(QTreeWidgetItem([str(f.get("name") or ""), str(f.get("type") or "Texte"), ""]))
        self.source_table_combo.blockSignals(True); self.source_table_combo.clear()
        self.source_table_combo.addItem("— Choisir les données —", None)
        instruction_font = self.source_table_combo.font(); instruction_font.setBold(True)
        self.source_table_combo.setItemData(0, instruction_font, Qt.ItemDataRole.FontRole)
        self.source_table_combo.setItemData(0, int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter), Qt.ItemDataRole.TextAlignmentRole)
        for table in tables:
            name = str(table.get("name") or "")
            if name: self.source_table_combo.addItem(name, name)
        self.source_table_combo.setCurrentIndex(0); self.source_table_combo.blockSignals(False)
        self.fields_box.setVisible(False); self.external_preview_btn.setEnabled(False); self._external_matching_verified=False
        fmt = str(structure.get("format") or "CSV / TXT / TSV")
        enc = str(structure.get("encoding") or "")
        sep = str(structure.get("delimiter_label") or "")
        details = ", ".join(x for x in (enc, sep) if x)
        self.summary.setText(f"Analyse terminée : {len(tables)} source(s), {total_fields} champ(s) — {fmt}" + (f" ({details})." if details else ".") + " Aucune donnée n'a été importée ni modifiée.")
        if len(tables) == 1:
            self.source_table_combo.setCurrentIndex(1)
        elif tables:
            self.source_table_combo.setStyleSheet("QComboBox { background: #fff3a6; border: 2px solid #c79a00; padding: 2px 6px; }")
            self.source_table_combo.setFocus(Qt.FocusReason.OtherFocusReason)

    def _choose_access_source(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self, tr("Choisir la base Access contenant les fiches à ajouter", self.language), "",
            tr("Bases Microsoft Access (*.accdb *.mdb);;Tous les fichiers (*.*)", self.language)
        )
        if not filename:
            return
        self.source_path = Path(filename)
        self._external_source_kind = "access"
        self.source_label.setText(tr("✓ Source Access : {name}", self.language).format(name=self.source_path.name))
        self.analyse_btn.setEnabled(True)
        self.choose_source_btn.setStyleSheet("")
        self.analyse_btn.setStyleSheet("QPushButton { background:#fff3a6; border:2px solid #c79a00; padding:3px 8px; }")
        self.analyse_btn.setFocus(Qt.FocusReason.OtherFocusReason)
        try:
            self.analyse_btn.clicked.disconnect()
        except Exception:
            pass
        self.analyse_btn.clicked.connect(self._analyse_access)
        self.tree.clear()
        self.match_box.setVisible(False)
        self.fields_box.setVisible(False)
        self.external_preview_btn.setEnabled(False)
        self._external_matching_verified = False
        self.summary.setText(tr("Source sélectionnée. Cliquez sur « Analyser les données ».", self.language))
        self.analyse_btn.setFocus(Qt.FocusReason.OtherFocusReason)

    def _analyse_access(self) -> None:
        if self.source_path is None:
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        QApplication.processEvents()
        try:
            structure = CollectionImportDialog._read_access_structure(self.source_path)
        except Exception as exc:
            QMessageBox.critical(self, tr("Analyse Access", self.language), str(exc))
            return
        finally:
            QApplication.restoreOverrideCursor()

        # L’analyse est terminée : ne pas laisser « Analyser les données »
        # en surbrillance en même temps que le choix de la table.
        self.analyse_btn.setStyleSheet("")
        self.tree.clear()
        tables = list(structure.get("tables", []) or [])
        for table in tables:
            fields = list(table.get("fields", []) or [])
            rows = table.get("rows")
            parent = QTreeWidgetItem([
                str(table.get("name") or "Table"),
                tr("{count} champ(s)", self.language).format(count=len(fields)),
                str(rows if isinstance(rows, int) else "?"),
            ])
            parent.setExpanded(False)
            self.tree.addTopLevelItem(parent)
            for field in fields:
                QTreeWidgetItem(parent, [
                    str(field.get("name") or ""),
                    str(field.get("type") or ""),
                    "",
                ])
        total_fields = sum(len(list(t.get("fields", []) or [])) for t in tables)
        self.summary.setText(
            tr("Analyse terminée : {tables} table(s), {fields} champ(s). Aucune donnée n'a été importée ni modifiée.", self.language).format(
                tables=len(tables), fields=total_fields
            )
        )
        self._external_access_structure = structure
        self.source_table_combo.blockSignals(True)
        self.source_table_combo.clear()
        # 11.7.70.18 — aucune table choisie d'office : le choix de la table de fiches
        # est une étape explicite de sécurité avant le rapprochement.
        self.source_table_combo.addItem(tr("— Choisir une table —", self.language), None)
        for table in tables:
            name = str(table.get("name") or "")
            if name:
                self.source_table_combo.addItem(name, name)
        self.source_table_combo.setCurrentIndex(0)
        self.source_table_combo.blockSignals(False)
        self.source_key_combo.clear(); self.source_key_combo.setEnabled(False)
        self.dest_key_combo.clear(); self.dest_key_combo.setEnabled(False)
        self.preview_match_btn.setEnabled(False)
        self.match_box.setVisible(False)
        self.fields_box.setVisible(False)
        self._external_matching_verified = False
        if tables:
            # 11.7.70.26.24 — ajout de fiches : aucun rapprochement avec l'existant.
            # L'utilisateur choisit seulement la table source, puis les correspondances.
            self.source_table_combo.setFocus(Qt.FocusReason.OtherFocusReason)
            # Le choix de table est présenté dans le résumé pour ne pas réintroduire
            # l'ancien bloc de rapprochement.
            names = [str(t.get("name") or "") for t in tables if str(t.get("name") or "")]
            if len(names) == 1:
                self.source_table_combo.setCurrentIndex(1)
            else:
                self.summary.setText(self.summary.text() + " " + tr("Choisissez maintenant la table contenant les fiches à ajouter.", self.language))
                self.source_table_combo.setFocus(Qt.FocusReason.OtherFocusReason)
                # 11.7.70.26.27 — appel visuel explicite : l'étape suivante est le choix de la table.
                self.source_table_combo.setStyleSheet("QComboBox { background: #fff3a6; border: 2px solid #c79a00; padding: 2px 6px; }")
                QTimer.singleShot(0, self._fit_external_import_window)

    def _fit_external_import_window(self) -> None:
        """Ajuste la hauteur après apparition du bloc de rapprochement."""
        try:
            layout = self.layout()
            if layout is not None:
                layout.activate()
            self.fields_box.updateGeometry()
            if layout is not None:
                layout.activate()
            QApplication.processEvents()
            needed_h = int(self.sizeHint().height())
            screen = self.screen()
            avail = screen.availableGeometry() if screen is not None else None
            max_h = int(avail.height() - 36) if avail is not None else 900
            # Ne jamais rétrécir ici : on ajoute une étape. On grandit seulement
            # de ce qui est nécessaire, avec un plafond adapté aux portables.
            target_h = min(max_h, max(int(self.height()), needed_h))
            self.resize(int(self.width()), target_h)
            if avail is not None and self.frameGeometry().bottom() > avail.bottom():
                geo = self.frameGeometry()
                geo.moveBottom(avail.bottom())
                self.move(geo.topLeft())
        except Exception:
            pass

    def _external_keys_changed(self, _index: int = -1) -> None:
        if self._external_matching_verified:
            self._external_matching_verified = False
            self.fields_box.setVisible(False)
            self.external_preview_btn.setEnabled(False)
        ready = bool(
            self.source_table_combo.currentData()
            and self.source_key_combo.currentData()
            and self.dest_key_combo.currentData()
        )
        self.preview_match_btn.setEnabled(ready)
        if ready:
            self.preview_match_btn.setFocus(Qt.FocusReason.OtherFocusReason)


    def _external_table_changed(self) -> None:
        # Le choix a été fait : retirer la surbrillance d'appel.
        self.source_table_combo.setStyleSheet("")
        """11.7.70.26.24 — une table Access = des fiches nouvelles à ajouter.

        Aucun rapprochement avec les fiches G-Skol existantes : dès que la table est
        choisie, on passe directement à la correspondance des champs.
        """
        self.fields_box.setVisible(False)
        self.external_preview_btn.setEnabled(False)
        table_data = self.source_table_combo.currentData()
        if not table_data:
            return
        self._external_matching_verified = True  # signifie désormais « table source validée »
        self._populate_external_field_mapping()

    def _load_external_destination_keys(self) -> None:
        self.dest_key_combo.clear()
        data = self.collection_combo.currentData()
        if not isinstance(data, dict) or not data.get("path"):
            return
        cid = int(data.get("id") or 0)
        # Champs natifs visibles de G-Skol.
        for key, spec in FIELD_BY_KEY.items():
            if key == "photo_data":
                continue
            self.dest_key_combo.addItem(str(spec.label), str(key))
        # Champs personnalisés de la collection réceptrice.
        try:
            manager = ModelManager(Path(str(data["path"])))
            for row in manager.custom_fields(cid):
                key = str(row.get("field_key") or "")
                label = str(row.get("label") or key)
                if key:
                    self.dest_key_combo.addItem(label, key)
        except Exception:
            pass
        for i in range(self.dest_key_combo.count()):
            if str(self.dest_key_combo.itemData(i) or "") == "record_number":
                self.dest_key_combo.setCurrentIndex(i); break

    @staticmethod
    def _external_match_token(value) -> str:
        if value is None:
            return ""
        text = str(value).strip()
        # 1, 1.0 et 001 doivent pouvoir rapprocher un numéro de fiche numérique.
        try:
            number = float(text.replace(",", "."))
            if number.is_integer():
                return str(int(number))
        except Exception:
            pass
        return text.casefold()

    def _external_destination_field_choices(self) -> list[tuple[str, str]]:
        """Destinations issues des champs ACTUELS du modèle de la collection.

        Les champs natifs historiques absents de la palette ne sont plus proposés.
        Les libellés personnalisés du modèle ont priorité sur le catalogue natif.
        """
        data = self.collection_combo.currentData()
        if not (isinstance(data, dict) and data.get("path")):
            return []
        manager = ModelManager(Path(str(data["path"])))
        cid = int(data.get("id") or 0)
        visible = set(manager.visible_fields(cid) or [])
        labels = manager.custom_labels(cid) or {}
        custom_rows = manager.custom_fields(cid) or []
        styles = manager.field_styles(cid) or {}
        custom_by_key = {
            str(row.get("field_key") or ""): str(row.get("label") or "").strip()
            for row in custom_rows
        }
        choices = []
        for key in manager.all_model_keys(cid):
            key = str(key)
            if key in {"record_number", "photo_data"}:
                continue
            if key not in visible:
                continue
            if bool((styles.get(key) or {}).get("field_deleted")):
                continue
            spec = FIELD_BY_KEY.get(key)
            label = str(labels.get(key) or custom_by_key.get(key) or
                        (spec.label if spec else key)).strip()
            if label:
                choices.append((label, key))
        return sorted(choices, key=lambda item: self._external_normalized_label(item[0]))

    @staticmethod
    def _external_normalized_label(text: str) -> str:
        import unicodedata
        value = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode("ascii")
        return "".join(ch for ch in value.casefold() if ch.isalnum())

    @staticmethod
    def _external_french_type_name(value: str) -> str:
        raw = str(value or "Texte").strip()
        key = raw.casefold()
        names = {
            "text": "Texte", "texte": "Texte", "string": "Texte",
            "currency": "Monétaire", "monetaire": "Monétaire", "monétaire": "Monétaire",
            "number": "Nombre", "numeric": "Nombre", "integer": "Nombre entier",
            "long": "Nombre entier", "double": "Nombre", "single": "Nombre", "real": "Nombre",
            "date": "Date", "datetime": "Date / heure", "date/time": "Date / heure",
            "boolean": "Oui / Non", "bool": "Oui / Non", "yes/no": "Oui / Non",
            "binary": "Binaire / Photo", "ole": "Binaire / Photo", "blob": "Binaire / Photo",
            "memo": "Texte long", "long text": "Texte long",
        }
        return names.get(key, raw)

    @staticmethod
    def _external_creation_type_choices() -> list[tuple[str, str]]:
        """Types proposés lors de la création volontaire d'un nouveau champ G-Skol."""
        return [
            ("Texte", "text"),
            ("Nombre", "numeric"),
            ("Monétaire", "currency"),
            ("Date", "date"),
            ("Oui / Non", "boolean"),
            ("Lien", "link"),
            ("Liste / Référentiel", "list"),
        ]

    @staticmethod
    def _external_creation_type_from_detected(value: str) -> str:
        key = str(value or "").strip().casefold()
        if key in {"currency", "monetaire", "monétaire"}:
            return "currency"
        if key in {"number", "numeric", "integer", "long", "double", "single", "real"}:
            return "numeric"
        if key in {"date", "datetime", "date/time"}:
            return "date"
        if key in {"boolean", "bool", "yes/no"}:
            return "boolean"
        if key in {"link", "url", "hyperlink"}:
            return "link"
        return "text"

    def _external_mapping_action_changed(self, action_combo: QComboBox, type_combo: QComboBox) -> None:
        """Le type est modifiable uniquement si l'utilisateur demande une création.

        Un champ G-Skol existant conserve impérativement son paramétrage actuel.
        """
        data = action_combo.currentData()
        action = str(data.get("action") or "") if isinstance(data, dict) else ""
        # Le type détecté reste consultable et corrigeable à tout moment.
        # Pour un champ G-Skol existant, cette correction n'altère jamais son type :
        # le type réel du champ destination reste prioritaire lors de l'import.
        type_combo.setEnabled(True)
        type_combo.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def _external_consolidated_source(self, table_name: str) -> tuple[list[dict], list[dict]]:
        """Construit la source logique fiche + référentiels Access liés.

        Pour Excel, une feuille est une source plate : ses colonnes sont déjà
        consolidées par le lecteur .xlsx et aucune jointure n'est nécessaire.

        Réutilise les métadonnées DAO déjà lues par G-Skol. Les relations explicites
        sont prioritaires ; RowSource puis un recoupement prudent des champs servent
        de repli pour les anciennes bases Access dont les relations DAO sont pauvres.
        """
        tables = list(self._external_access_structure.get("tables", []) or [])
        if self._external_source_kind in {"excel", "text", "ods", "dbf", "sqlite"}:
            sheet = next((t for t in tables if str(t.get("name") or "").casefold() == table_name.casefold()), None)
            if not sheet: return [], []
            fields=[]
            rows_data = list(sheet.get("rows_data", []) or [])
            for f in (sheet.get("fields", []) or []):
                x=dict(f); name=str(f.get("name") or "")
                values = [r.get(name, "") for r in rows_data if str(r.get(name, "") or "").strip()]
                if values:
                    numeric = 0
                    for raw in values:
                        try:
                            float(str(raw).strip().replace(" ", "").replace(",", ".")); numeric += 1
                        except Exception:
                            pass
                    if numeric / len(values) >= 0.8:
                        norm = self._external_normalized_label(name)
                        if any(token in norm for token in ("prix", "cout", "montant", "tarif")):
                            x["type"] = "Monétaire"
                        else:
                            x["type"] = "Nombre"
                x.update({"source_table": table_name, "source_field": name, "source_key": name, "display_name": name, "target_label": name})
                fields.append(x)
            return fields, []
        base = next((t for t in tables if str(t.get("name") or "").casefold() == table_name.casefold()), None)
        if not base:
            return [], []
        base_fields = [dict(f) for f in (base.get("fields", []) or [])]
        base_names = {str(f.get("name") or "").casefold(): str(f.get("name") or "") for f in base_fields}
        refs: list[dict] = []
        used_tables: set[str] = set()

        # 1. Relations DAO explicites portées par les champs de la table principale.
        for f in base_fields:
            child = str(f.get("relation_table") or "").strip()
            child_key = str(f.get("relation_field") or "").strip()
            parent_key = str(f.get("name") or "").strip()
            if child and child_key and parent_key and child.casefold() != table_name.casefold():
                refs.append({"table": child, "parent_key": parent_key, "child_key": child_key})
                used_tables.add(child.casefold())

        # 2. RowSource Access : un champ principal pointe directement sur une table.
        for f in base_fields:
            lookup = str(f.get("lookup_source") or "").strip().strip("[]")
            parent_key = str(f.get("name") or "").strip()
            if not lookup or lookup.casefold() in used_tables or lookup.casefold() == table_name.casefold():
                continue
            child = next((t for t in tables if str(t.get("name") or "").casefold() == lookup.casefold()), None)
            if not child:
                continue
            child_names = {str(x.get("name") or "").casefold(): str(x.get("name") or "") for x in child.get("fields", []) or []}
            if parent_key.casefold() in child_names:
                refs.append({"table": str(child.get("name") or lookup), "parent_key": parent_key,
                             "child_key": child_names[parent_key.casefold()]})
                used_tables.add(lookup.casefold())

        # 3. Repli pour bases historiques : table de >=3 champs partageant un vrai
        # champ métier avec la table principale. On écarte les clés techniques.
        technical = {"n", "no", "numero", "id", "photo", "fichierphoto", "rem", "commentaire"}
        def tok(v: str) -> str:
            import unicodedata
            x=unicodedata.normalize("NFKD", str(v or "")).encode("ascii","ignore").decode("ascii").casefold()
            return "".join(c for c in x if c.isalnum())
        for child in tables:
            child_name = str(child.get("name") or "")
            if not child_name or child_name.casefold() == table_name.casefold() or child_name.casefold() in used_tables:
                continue
            child_fields = list(child.get("fields", []) or [])
            if len(child_fields) < 3:
                continue
            child_names = {str(x.get("name") or "").casefold(): str(x.get("name") or "") for x in child_fields}

            # Correspondance de clé générique. Les anciennes bases Access ont
            # parfois renommé le champ de la table principale (ex. suffixe
            # numérique ajouté par Access) sans renommer la clé du référentiel.
            # On ne code aucun nom métier : on compare d'abord les noms exacts,
            # puis une forme canonique qui ignore ponctuation et suffixe numérique.
            import re
            def keytok(v: str) -> str:
                return re.sub(r"\d+$", "", tok(v))

            candidates = []
            for bf in base_fields:
                bn = str(bf.get("name") or "").strip()
                if not bn or tok(bn) in technical:
                    continue
                for cf in child_fields:
                    cn = str(cf.get("name") or "").strip()
                    if not cn or tok(cn) in technical:
                        continue
                    exact = bn.casefold() == cn.casefold()
                    canonical = keytok(bn) and keytok(bn) == keytok(cn)
                    if not (exact or canonical):
                        continue
                    score = 100 if exact else 60
                    # Les métadonnées Access restent prioritaires lorsqu'elles
                    # existent ; elles rendent le choix non ambigu sans dépendre
                    # du nom d'une table ou d'un champ particulier.
                    lookup = str(bf.get("lookup_source") or "").strip().strip("[]")
                    relation = str(bf.get("relation_table") or "").strip()
                    if lookup.casefold() == child_name.casefold(): score += 80
                    if relation.casefold() == child_name.casefold(): score += 100
                    candidates.append((score, bn, cn))

            if not candidates:
                continue
            candidates.sort(key=lambda x: (-x[0], x[1].casefold(), x[2].casefold()))
            best_score = candidates[0][0]
            best = [c for c in candidates if c[0] == best_score]
            # En cas d'ambiguïté réelle, ne rien inventer.
            if len({(c[1].casefold(), c[2].casefold()) for c in best}) != 1:
                continue
            _, parent_key, child_key = best[0]
            refs.append({"table": child_name, "parent_key": parent_key,
                         "child_key": child_key})
            used_tables.add(child_name.casefold())

        # Champs affichés : champs principaux + champs enfants (sauf clé de jointure).
        fields: list[dict] = []
        for f in base_fields:
            x=dict(f); x["source_table"]=table_name; x["source_field"]=str(f.get("name") or "")
            x["source_key"]=str(f.get("name") or ""); x["display_name"]=str(f.get("name") or "")
            fields.append(x)
        for ref in refs:
            child = next((t for t in tables if str(t.get("name") or "").casefold() == ref["table"].casefold()), None)
            if not child: continue
            for f in child.get("fields", []) or []:
                name=str(f.get("name") or "")
                if not name or name.casefold() == str(ref["child_key"]).casefold():
                    continue
                key=f"{ref['table']}::{name}"
                x=dict(f); x.update({"source_table":ref["table"], "source_field":name,
                                     "source_key":key, "display_name":f"{name}  [{ref['table']}]",
                                     "target_label":name})
                fields.append(x)
        return fields, refs

    def _external_read_consolidated_rows(self, table_name: str, fields: list[dict], refs: list[dict]) -> list[dict]:
        """Lit la table principale puis enrichit chaque ligne avec les référentiels."""
        if self.source_path is None:
            return []
        if self._external_source_kind in {"excel", "text", "ods", "dbf", "sqlite"}:
            sheet = next((t for t in (self._external_excel_workbook.get("sheets", []) or []) if str(t.get("name") or "").casefold() == table_name.casefold()), None)
            return [dict(r) for r in (sheet.get("rows_data", []) or [])] if sheet else []
        base_cols=[str(f.get("source_field") or "") for f in fields if str(f.get("source_table") or "").casefold()==table_name.casefold()]
        rows=CollectionImportDialog._read_access_rows(self.source_path, table_name, base_cols)
        for ref in refs:
            child_fields=[f for f in fields if str(f.get("source_table") or "").casefold()==str(ref["table"]).casefold()]
            child_cols=[str(ref["child_key"])] + [str(f.get("source_field") or "") for f in child_fields]
            # dédoublonner en conservant l'ordre
            child_cols=list(dict.fromkeys(x for x in child_cols if x))
            child_rows=CollectionImportDialog._read_access_rows(self.source_path, str(ref["table"]), child_cols)
            index={self._external_match_token(r.get(str(ref["child_key"]), "")): r for r in child_rows}
            for row in rows:
                linked=index.get(self._external_match_token(row.get(str(ref["parent_key"]), "")))
                if not linked: continue
                for f in child_fields:
                    row[str(f.get("source_key") or "")]=linked.get(str(f.get("source_field") or ""), "")
        return rows

    def _external_sort_destination_choices(self, checked: bool) -> None:
        """Sort the *source rows* of phase 4 without losing their mappings.

        The three columns form one logical row.  We snapshot every mapping,
        rebuild the table in the requested source-field order, then restore the
        type and destination selections.  This also makes unchecking the box
        restore the original source order safely.
        """
        table = getattr(self, "fields_table", None)
        if table is None or table.rowCount() == 0:
            return

        saved = {}
        for row in range(table.rowCount()):
            item = table.item(row, 1)
            if item is None:
                continue
            source_key = str(item.data(Qt.ItemDataRole.UserRole) or item.text())
            type_combo = table.cellWidget(row, 2)
            dest_combo = table.cellWidget(row, 3)
            saved[source_key] = {
                "type": type_combo.currentData() if type_combo is not None else None,
                "dest": dest_combo.currentData() if dest_combo is not None else None,
            }

        self._external_saved_mapping_state = saved
        self._populate_external_field_mapping(show_dialog=False)
        self._external_saved_mapping_state = None

    def _populate_external_field_mapping(self, show_dialog: bool = True) -> None:
        table_name = str(self.source_table_combo.currentData() or "")
        fields, refs = self._external_consolidated_source(table_name)
        self._external_consolidated_fields = fields
        self._external_reference_specs = refs
        # The checkbox sorts SOURCE rows only; columns 2 and 3 travel with the row.
        if getattr(self, "external_sort_fields_cb", None) is not None and self.external_sort_fields_cb.isChecked():
            fields = sorted(fields, key=lambda f: self._external_normalized_label(
                str(f.get("display_name") or f.get("target_label") or f.get("name") or "")
            ))
        destinations = self._external_destination_field_choices()
        # Display and sort destination fields in the active interface language.
        # This is important in English: sorting the original French labels first
        # made the A→Z option appear not to work after translation.
        destinations = [(tr(label, self.language), key) for label, key in destinations]
        # Brique 1.2 : les DESTINATIONS sont toujours classées par libellé.
        # La case A→Z reste réservée au tri des lignes SOURCE.
        destinations.sort(key=lambda item: self._external_normalized_label(item[0]))
        by_label = {self._external_normalized_label(label): (label, key) for label, key in destinations}
        self.fields_table.setRowCount(len(fields))
        auto = 0
        for row, field in enumerate(fields):
            name = str(field.get("target_label") or field.get("name") or "")
            source_key = str(field.get("source_key") or field.get("name") or "")
            display_name = str(field.get("display_name") or name)
            ftype = str(field.get("type") or "Texte")
            source_cell = QTableWidgetItem(display_name)
            source_cell.setData(Qt.ItemDataRole.UserRole, source_key)
            self.fields_table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
            self.fields_table.setItem(row, 1, source_cell)

            # 11.7.70.24 — le type détecté devient une proposition modifiable,
            # mais uniquement lorsqu'un nouveau champ doit être créé.
            type_combo = NoWheelComboBox()
            for label, internal_type in self._external_creation_type_choices():
                type_combo.addItem(tr(label, self.language), internal_type)
            detected_type = self._external_creation_type_from_detected(ftype)
            for i in range(type_combo.count()):
                if str(type_combo.itemData(i) or "") == detected_type:
                    type_combo.setCurrentIndex(i)
                    break
            type_combo.setEnabled(True)
            type_combo.setToolTip(tr(
                "Type détecté/proposé par G-Skol, modifiable ici. Si la destination est un champ G-Skol existant, son type réel reste prioritaire et n'est jamais modifié.",
                self.language
            ))
            self.fields_table.setCellWidget(row, 2, type_combo)

            combo = NoWheelComboBox()
            combo.addItem(tr("— Ne pas importer —", self.language), {"action": "skip"})
            ref_probable = any(
                str(other.get("name") or "").casefold() != table_name.casefold()
                and any(self._external_normalized_label(str(ff.get("name") or "")) == self._external_normalized_label(name)
                        for ff in (other.get("fields", []) or []))
                for other in (self._external_access_structure.get("tables", []) or [])
            )
            create_type = "list" if ref_probable else detected_type
            create_type_label = "Liste / Référentiel" if ref_probable else self._external_french_type_name(ftype)
            create_label = tr("— Créer un nouveau champ… —", self.language)
            combo.addItem(create_label, {"action": "create", "name": name, "type": create_type, "referential": ref_probable})
            combo.insertSeparator(combo.count())
            for label, key in destinations:
                combo.addItem(label, {"action": "existing", "key": key})

            match = by_label.get(self._external_normalized_label(name))
            if match:
                wanted_key = match[1]
                for i in range(combo.count()):
                    data = combo.itemData(i)
                    if isinstance(data, dict) and data.get("action") == "existing" and data.get("key") == wanted_key:
                        combo.setCurrentIndex(i); auto += 1; break

            # Si G-Skol pense qu'il s'agit d'un référentiel et qu'aucun champ existant
            # n'a été rapproché, la proposition de création porte bien le type Liste.
            if combo.currentData() and isinstance(combo.currentData(), dict) and combo.currentData().get("action") == "create":
                for i in range(type_combo.count()):
                    if str(type_combo.itemData(i) or "") == create_type:
                        type_combo.setCurrentIndex(i); break

            # Restore the user's exact choices after a source-row sort.
            saved_state = getattr(self, "_external_saved_mapping_state", None) or {}
            state = saved_state.get(source_key)
            if isinstance(state, dict):
                wanted_type = state.get("type")
                for i in range(type_combo.count()):
                    if type_combo.itemData(i) == wanted_type:
                        type_combo.setCurrentIndex(i); break
                wanted_dest = state.get("dest")
                if isinstance(wanted_dest, dict):
                    for i in range(combo.count()):
                        data = combo.itemData(i)
                        if not isinstance(data, dict):
                            continue
                        if (data.get("action") == wanted_dest.get("action") and
                            data.get("key") == wanted_dest.get("key") and
                            data.get("name") == wanted_dest.get("name")):
                            combo.setCurrentIndex(i); break

            combo.currentIndexChanged.connect(
                lambda _idx, a=combo, t=type_combo: self._external_mapping_action_changed(a, t)
            )
            self._external_mapping_action_changed(combo, type_combo)
            self.fields_table.setCellWidget(row, 3, combo)
            combo.currentIndexChanged.connect(self._external_refresh_duplicate_warning)

        self._external_refresh_duplicate_warning()
        _source_label = 'Excel' if self._external_source_kind == 'excel' else ('CSV/TXT/TSV' if self._external_source_kind == 'text' else ('ODS' if self._external_source_kind == 'ods' else ('DBF' if self._external_source_kind == 'dbf' else ('SQLite' if self._external_source_kind == 'sqlite' else tr("Access consolidé(s)", self.language)))))
        self.fields_summary.setText(
            tr("{fields} champ(s) {source} ; {auto} correspondance(s) proposée(s) automatiquement. Pour « Créer… », le type proposé peut être corrigé. Un champ G-Skol existant conserve toujours son type.", self.language).format(
                fields=len(fields), source=_source_label, auto=auto
            )
        )
        self.external_preview_btn.setEnabled(True)
        if show_dialog:
            self._show_external_mapping_dialog()


    def _show_external_mapping_dialog(self) -> None:
        """Display phase 4 in a separate, laptop-friendly window."""
        if getattr(self, "_external_mapping_dialog", None) is not None:
            try:
                self._external_mapping_dialog.close()
            except Exception:
                pass

        dlg = QDialog(self)
        self._external_mapping_dialog = dlg
        dlg.setWindowTitle(tr("Correspondance des champs", self.language))
        dlg.resize(900, 620)
        dlg.setMinimumSize(760, 500)
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(14, 14, 14, 12)
        layout.setSpacing(10)

        self.fields_box.setParent(dlg)
        self.fields_box.setVisible(True)
        layout.addWidget(self.fields_box, 1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.external_preview_btn.setParent(dlg)
        self.external_preview_btn.setVisible(True)
        buttons.addWidget(self.external_preview_btn)
        back_btn = QPushButton(tr("Fermer", self.language), dlg)
        back_btn.clicked.connect(dlg.close)
        buttons.addWidget(back_btn)
        layout.addLayout(buttons)

        def restore_phase4_widgets() -> None:
            self.fields_box.setParent(self)
            self.fields_box.setVisible(False)
            self.external_preview_btn.setParent(self)
            self.external_preview_btn.setVisible(False)
            self._external_mapping_dialog = None

        dlg.finished.connect(lambda _result: restore_phase4_widgets())
        translate_widget_tree(dlg, self.language)
        self.external_preview_btn.setFocus(Qt.FocusReason.OtherFocusReason)
        dlg.exec()

    def _external_backup_destination(self) -> Path:
        """Copie de sécurité juste avant l'ajout réel des fiches."""
        if self.destination_path is None:
            raise RuntimeError("Aucune collection G-Skol de destination.")
        workspace = Path(WORKSPACE)
        folder = workspace / "Sauvegardes"
        folder.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = folder / f"{self.destination_path.stem}-avant-ajout-{stamp}{self.destination_path.suffix}"
        shutil.copy2(self.destination_path, backup)
        return backup

    def _external_resolve_mapping_for_import(self) -> list[dict]:
        if self.destination_path is None:
            raise RuntimeError("Aucune collection G-Skol de destination.")
        data = self.collection_combo.currentData()
        cid = int(data.get("id") or 0) if isinstance(data, dict) else 0
        if not cid:
            raise RuntimeError("Collection G-Skol invalide.")
        mm = ModelManager(self.destination_path)
        result = []
        for source, cfg0 in list(getattr(self, "_external_field_mapping_choices", []) or []):
            cfg = dict(cfg0 or {})
            action = str(cfg.get("action") or "skip")
            if action == "skip":
                continue
            if action == "create":
                label = str(cfg.get("name") or source).strip() or str(source)
                ftype = str(cfg.get("type") or "text")
                created = mm.create_custom_field(cid, label, ftype, initial_group="Identification")
                key = str(created.get("field_key") or "")
                with sqlite3.connect(self.destination_path) as con:
                    con.execute("UPDATE collection_model_fields SET visible=0 WHERE collection_id=? AND field_key=?", (cid, key))
                cfg = {"action": "existing", "key": key, "created": True, "field_type": ftype}
            key = str(cfg.get("key") or "")
            if key:
                result.append({"source": str(source), "key": key, **cfg})
        return result

    def _external_add_selected_rows(self, rows: list[dict], parent: QWidget) -> dict:
        """Ajoute les lignes sélectionnées comme nouvelles fiches, sans toucher aux anciennes."""
        if self.destination_path is None:
            raise RuntimeError("Aucune collection G-Skol de destination.")
        data = self.collection_combo.currentData()
        cid = int(data.get("id") or 0) if isinstance(data, dict) else 0
        if not cid:
            raise RuntimeError("Collection G-Skol invalide.")
        mapping = self._external_resolve_mapping_for_import()
        custom_meta = {str(x.get("field_key") or ""): x for x in ModelManager(self.destination_path).custom_fields(cid)}
        total = len(rows)
        progress = QProgressDialog("Ajout des nouvelles fiches…", "", 0, max(1, total), parent)
        progress.setWindowTitle("Import des fiches")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setCancelButton(None)
        progress.setMinimumDuration(0)
        progress.setAutoClose(False)
        progress.show()
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        QApplication.processEvents()
        rm = RecordManager(self.destination_path)
        now = datetime.now().isoformat(timespec="seconds")
        added = photos = 0
        list_values: dict[str, set[str]] = {}
        try:
            with rm._connect() as con:
                rm._ensure_table(con)
                rm._ensure_custom_values_table(con)
                start_number = int(con.execute("SELECT COALESCE(MAX(record_number),0) FROM records WHERE collection_id=?", (cid,)).fetchone()[0])
                defaults = dict(RecordManager.FIELD_DEFAULTS)
                field_names = list(defaults)
                columns = ["collection_id", "record_number", *field_names, "created_at", "updated_at"]
                placeholders = ",".join("?" for _ in columns)
                insert_sql = f"INSERT INTO records({', '.join(columns)}) VALUES ({placeholders})"
                for n, source_row in enumerate(rows, 1):
                    std = dict(defaults)
                    custom = {}
                    photo_blob = None
                    photo_fmt = ""
                    for entry in mapping:
                        source = str(entry.get("source") or "")
                        key = str(entry.get("key") or "")
                        raw = source_row.get(source, "")
                        if key == "record_number":
                            continue
                        if key == "photo_data":
                            blob, fmt = CollectionImportDialog._decode_access_photo(raw)
                            if blob:
                                photo_blob, photo_fmt = blob, fmt
                                photos += 1
                            continue
                        label = str(FIELD_BY_KEY[key].label) if key in FIELD_BY_KEY else str(custom_meta.get(key, {}).get("label") or source)
                        value = CollectionImportDialog._format_imported_value(raw, label)
                        if key in RecordManager.FIELD_DEFAULTS:
                            std[key] = value
                        else:
                            custom[key] = value
                        # Les référentiels ne sont pas enrichis pendant l'import.
                        # La collection proposera leur mise à jour globale à sa fermeture.
                    if std.get("mineral_name"):
                        std["species"] = str(std.get("mineral_name") or "")
                    params = [cid, start_number + n, *(str(std.get(k, defaults[k]) or "").strip() for k in field_names), now, now]
                    cur = con.execute(insert_sql, params)
                    rid = int(cur.lastrowid)
                    for key, value in custom.items():
                        value = str(value or "").strip()
                        if value:
                            con.execute("INSERT OR REPLACE INTO record_custom_values(record_id, field_key, value) VALUES(?,?,?)", (rid, key, value))
                    if photo_blob:
                        con.execute("UPDATE records SET photo_data=?, photo_format=? WHERE id=?", (sqlite3.Binary(photo_blob), photo_fmt, rid))
                    added += 1
                    if n == 1 or n % 20 == 0 or n == total:
                        progress.setValue(n)
                        progress.setLabelText(f"Ajout des nouvelles fiches… {n} / {total}")
                        QApplication.processEvents()
                for key, values in list_values.items():
                    meta = custom_meta.get(key, {})
                    code = str(meta.get("referential_code") or key)
                    defrow = con.execute("SELECT id FROM referential_definitions WHERE collection_id=? AND code=?", (cid, code)).fetchone()
                    if not defrow:
                        continue
                    did = int(defrow[0])
                    max_order = int(con.execute("SELECT COALESCE(MAX(sort_order),0) FROM referential_values WHERE definition_id=?", (did,)).fetchone()[0])
                    for value in sorted(values, key=str.casefold):
                        max_order += 1
                        con.execute("INSERT OR IGNORE INTO referential_values(definition_id,value,sort_order,is_active,created_at,updated_at) VALUES(?,?,?,1,?,?)", (did, value, max_order, now, now))
        finally:
            if QApplication.overrideCursor() is not None:
                QApplication.restoreOverrideCursor()
            progress.close()
        return {"added": added, "photos": photos}

    def _external_duplicate_groups(self) -> list:
        """Return duplicate existing-field mappings in displayed source-row order."""
        destinations = {}
        for row in range(self.fields_table.rowCount()):
            combo = self.fields_table.cellWidget(row, 3)
            cfg = combo.currentData() if isinstance(combo, QComboBox) else None
            if not isinstance(cfg, dict) or cfg.get("action") != "existing":
                continue
            key = str(cfg.get("key") or "").strip()
            if not key:
                continue
            item = self.fields_table.item(row, 1)
            source = item.text() if item is not None else f"Champ {row + 1}"
            destinations.setdefault(key, []).append((row + 1, source, combo.currentText()))
        return [entries for entries in destinations.values() if len(entries) > 1]

    def _external_refresh_duplicate_warning(self, *_args) -> None:
        """Refresh the red inline warning immediately after any destination change."""
        warning = getattr(self, "external_duplicate_warning", None)
        if warning is None:
            return
        groups = self._external_duplicate_groups()
        if not groups:
            warning.clear()
            warning.setVisible(False)
            return
        sections = []
        for entries in groups:
            sources = ", ".join(f"ligne {row} : {source}" for row, source, _ in entries)
            sections.append(f"« {entries[0][2]} » — {sources}")
        warning.setText("Correspondances en double : " + " ; ".join(sections))
        warning.setVisible(True)

    def _external_check_duplicate_destinations(self) -> bool:
        """Brique 1.2 : empêcher plusieurs sources d'écraser un même champ existant.

        Ne concerne pas les actions « Ne pas importer » ou « Créer ».
        Les numéros indiqués sont ceux des lignes visibles du tableau.
        """
        duplicates = self._external_duplicate_groups()
        if not duplicates:
            return True
        sections = []
        for entries in duplicates:
            sections.append("« {} » :\n{}".format(
                entries[0][2],
                "\n".join("  • Ligne {} — {}".format(row, source) for row, source, _ in entries)
            ))
        QMessageBox.warning(
            self,
            tr("Correspondances en double", self.language),
            tr("Plusieurs champs sources sont associés au même champ de destination :", self.language)
            + "\n\n" + "\n\n".join(sections)
            + "\n\n" + tr("Modifiez ces correspondances avant de poursuivre.", self.language),
        )
        return False

    def _prepare_external_preview(self) -> None:
        """11.7.70.26.24 — sélection des nouvelles fiches, sans écriture.

        Une ligne = une fiche Access. Toutes les lignes sont incluses au départ.
        Le tri des colonnes, la sélection multiple par glisser/Ctrl/Maj et le clic
        droit permettent de regrouper puis inclure/exclure rapidement des fiches.
        """
        if not self._external_matching_verified or not self.fields_box.isVisible():
            return
        if not self._external_check_duplicate_destinations():
            return
        _prep_kind = 'Excel' if self._external_source_kind == 'excel' else ('CSV/TXT/TSV' if self._external_source_kind == 'text' else ('ODS' if self._external_source_kind == 'ods' else ('DBF' if self._external_source_kind == 'dbf' else ('SQLite' if self._external_source_kind == 'sqlite' else 'Access'))))
        progress = QProgressDialog(tr("Préparation des fiches {kind}…", self.language).format(kind=_prep_kind), "", 0, 0, self)
        progress.setWindowTitle(tr("Préparation de la sélection", self.language))
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setCancelButton(None)
        progress.setMinimumDuration(0)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.show()
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        QApplication.processEvents()
        try:
            choices = []
            for row in range(self.fields_table.rowCount()):
                source_item = self.fields_table.item(row, 1)
                combo = self.fields_table.cellWidget(row, 3)
                cfg = combo.currentData() if isinstance(combo, QComboBox) else None
                if not isinstance(cfg, dict):
                    continue
                selected = dict(cfg)
                type_combo = self.fields_table.cellWidget(row, 2)
                if selected.get("action") == "create" and isinstance(type_combo, QComboBox):
                    selected["type"] = str(type_combo.currentData() or "text")
                    selected["type_label"] = str(type_combo.currentText() or "Texte")
                source_key = source_item.data(Qt.ItemDataRole.UserRole) if source_item else ""
                choices.append((str(source_key or (source_item.text() if source_item else "")), selected))
            self._external_field_mapping_choices = choices
            table_name = str(self.source_table_combo.currentData() or "")
            if not table_name or self.source_path is None:
                raise RuntimeError(
                    "Choisissez la feuille Excel contenant les fiches à ajouter." if self._external_source_kind == "excel" else
                    ("Choisissez les données CSV/TXT/TSV contenant les fiches à ajouter." if self._external_source_kind == "text" else
                     ("Choisissez la feuille ODS contenant les fiches à ajouter." if self._external_source_kind == "ods" else
                      ("Choisissez les données DBF contenant les fiches à ajouter." if self._external_source_kind == "dbf" else
                       ("Choisissez la table SQLite contenant les fiches à ajouter." if self._external_source_kind == "sqlite" else
                        "Choisissez la table Access contenant les fiches à ajouter."))))
                )
            # Aperçu consolidé : la ligne de fiche contient aussi les valeurs des
            # référentiels Access liés (IMA, Gisements ou équivalents génériques).
            consolidated_fields = list(getattr(self, "_external_consolidated_fields", []) or [])
            refs = list(getattr(self, "_external_reference_specs", []) or [])
            source_rows = self._external_read_consolidated_rows(table_name, consolidated_fields, refs)
            source_columns = [str(f.get("source_key") or f.get("name") or "") for f in consolidated_fields]
        except Exception as exc:
            QMessageBox.critical(self, tr("Sélection des fiches", self.language), str(exc)); return
        finally:
            if QApplication.overrideCursor() is not None: QApplication.restoreOverrideCursor()
            progress.close()

        dlg = QDialog(self); dlg.setWindowTitle(tr("Sélection des fiches à ajouter", self.language))
        dlg.resize(1180, 720); dlg.setMinimumSize(860, 520)
        lay = QVBoxLayout(dlg); lay.setContentsMargins(18, 16, 18, 14); lay.setSpacing(8)
        title = QLabel("5. Sélection des fiches à ajouter — une ligne = une nouvelle fiche G-Skol")
        title.setStyleSheet("font-size: 18px; font-weight: 800;"); lay.addWidget(title)
        help_label = QLabel("Toutes les fiches sont incluses au départ. Cliquez sur un en-tête pour trier (▲/▼), sélectionnez une ou plusieurs lignes par glisser, Ctrl ou Maj, puis utilisez le clic droit pour les ajouter ou les retirer de l'import.")
        help_label.setWordWrap(True); lay.addWidget(help_label)

        controls = QHBoxLayout()
        add_all = QPushButton("Ajouter tout"); remove_all = QPushButton("Supprimer tout")
        controls.addWidget(add_all); controls.addWidget(remove_all); controls.addStretch(1)
        counter = QLabel(); counter.setStyleSheet("font-weight:700;"); controls.addWidget(counter)
        lay.addLayout(controls)

        # 11.7.70.26.27 — modèle virtualisé : aucune QTableWidgetItem par cellule.
        # Avec 2 000 x 30 cellules, QTableWidget était le goulet d'étranglement.
        _dialog_language = self.language
        class ExternalRowsModel(QAbstractTableModel):
            def __init__(self, rows, columns, parent=None):
                self.language = _dialog_language
                super().__init__(parent)
                self.rows = list(rows)
                self.columns = list(columns)
                self.included = [True] * len(self.rows)
                self.order = list(range(len(self.rows)))

            def rowCount(self, parent=QModelIndex()): return 0 if parent.isValid() else len(self.order)
            def columnCount(self, parent=QModelIndex()): return 0 if parent.isValid() else len(self.columns) + 1
            def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
                if role != Qt.ItemDataRole.DisplayRole: return None
                if orientation == Qt.Orientation.Horizontal:
                    return tr("Import", self.language) if section == 0 else self.columns[section-1]
                return section + 1
            def data(self, index, role=Qt.ItemDataRole.DisplayRole):
                if not index.isValid(): return None
                src_i = self.order[index.row()]
                inc = self.included[src_i]
                if role == Qt.ItemDataRole.DisplayRole:
                    if index.column() == 0: return "✓" if inc else "—"
                    value = self.rows[src_i].get(self.columns[index.column()-1], "")
                    if value is None: return ""
                    if isinstance(value, (bytes, bytearray, memoryview)):
                        return tr("[donnée binaire]", self.language)
                    return str(value)
                if role == Qt.ItemDataRole.TextAlignmentRole and index.column() == 0:
                    return int(Qt.AlignmentFlag.AlignCenter)
                if role == Qt.ItemDataRole.ForegroundRole and not inc:
                    return QColor(145,145,145)
                return None
            def sort(self, column, order=Qt.SortOrder.AscendingOrder):
                self.layoutAboutToBeChanged.emit()
                if column == 0:
                    key = lambda i: self.included[i]
                else:
                    name = self.columns[column-1]
                    def key(i):
                        v = self.rows[i].get(name, "")
                        if v is None: return (2, "")
                        if isinstance(v, (int, float)): return (0, v)
                        text = str(v).strip()
                        try: return (0, float(text.replace(',', '.')))
                        except Exception: return (1, text.casefold())
                self.order.sort(key=key, reverse=(order == Qt.SortOrder.DescendingOrder))
                self.layoutChanged.emit()
            def set_included_source(self, source_indexes, include):
                changed = False
                for i in source_indexes:
                    if 0 <= i < len(self.included) and self.included[i] != include:
                        self.included[i] = include; changed = True
                if changed and self.rowCount():
                    self.dataChanged.emit(self.index(0,0), self.index(self.rowCount()-1,self.columnCount()-1), [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ForegroundRole])
            def set_all(self, include):
                self.included = [bool(include)] * len(self.included)
                if self.rowCount():
                    self.dataChanged.emit(self.index(0,0), self.index(self.rowCount()-1,self.columnCount()-1), [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ForegroundRole])
            def source_index_at_view_row(self, view_row): return self.order[view_row]
            def selected_rows_data(self): return [self.rows[i] for i, inc in enumerate(self.included) if inc]
            def included_count(self): return sum(self.included)

        model = ExternalRowsModel(source_rows, source_columns, dlg)
        tablew = QTableView(dlg); tablew.setModel(model)
        tablew.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        tablew.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        tablew.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        tablew.setAlternatingRowColors(True); tablew.setWordWrap(False)
        tablew.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        tablew.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        tablew.setSortingEnabled(True)
        tablew.setUniformRowHeights(True) if hasattr(tablew, "setUniformRowHeights") else None
        hdr = tablew.horizontalHeader(); hdr.setSectionResizeMode(QHeaderView.ResizeMode.Interactive); hdr.setStretchLastSection(False)
        hdr.resizeSection(0,72)
        for c in range(1, len(source_columns)+1): hdr.resizeSection(c,160)
        lay.addWidget(tablew,1)

        def update_counter(): counter.setText(tr("{selected} fiche(s) à ajouter sur {total}", self.language).format(selected=model.included_count(), total=model.rowCount()))
        def selected_source_indexes():
            return {model.source_index_at_view_row(idx.row()) for idx in tablew.selectionModel().selectedRows()}
        def set_selected(include):
            model.set_included_source(selected_source_indexes(), include); update_counter()
        def set_all(include): model.set_all(include); update_counter()
        add_all.clicked.connect(lambda: set_all(True)); remove_all.clicked.connect(lambda: set_all(False))
        tablew.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        def context_menu(pos):
            idx = tablew.indexAt(pos)
            if idx.isValid() and idx.row() not in {i.row() for i in tablew.selectionModel().selectedRows()}:
                tablew.selectRow(idx.row())
            menu=QMenu(tablew)
            a1=menu.addAction(tr("Ajouter à l'import", self.language)); a2=menu.addAction(tr("Retirer de l'import", self.language))
            chosen=menu.exec(tablew.viewport().mapToGlobal(pos))
            if chosen is a1: set_selected(True)
            elif chosen is a2: set_selected(False)
        tablew.customContextMenuRequested.connect(context_menu)
        update_counter()

        footer=QHBoxLayout(); footer.addStretch(1)
        back=QPushButton("Retour à la correspondance"); back.clicked.connect(dlg.reject); footer.addWidget(back)
        next_btn=QPushButton("Valider la sélection")
        def validate_selection():
            selected = list(model.selected_rows_data())
            # L'ordre visuel (tri de l'aperçu) ne doit jamais casser l'ordre historique
            # de la source. Si un N° Access existe, il sert uniquement à ordonner
            # les nouvelles fiches avant que G-Skol leur attribue ses propres numéros.
            def _access_order(row):
                for key in ("N°", "Nº", "No", "N° fiche", "Numero", "Numéro"):
                    if key in row:
                        try:
                            return (0, float(str(row.get(key) or "").replace(",", ".")))
                        except Exception:
                            return (1, str(row.get(key) or "").casefold())
                if "__excel_row__" in row:
                    try: return (0, float(row.get("__excel_row__") or 0))
                    except Exception: pass
                return (2, 0)
            selected.sort(key=_access_order)
            self._external_selected_rows = selected
            if not selected:
                QMessageBox.information(dlg, tr("Ajout des fiches", self.language), tr("Aucune fiche n'est sélectionnée pour l'import.", self.language))
                return
            data = self.collection_combo.currentData()
            collection_name = str(data.get("name") or self.destination_path.stem) if isinstance(data, dict) else self.destination_path.stem
            box = QMessageBox(dlg)
            box.setWindowTitle(tr("Confirmer l'ajout", self.language))
            box.setIcon(QMessageBox.Icon.Question)
            box.setText(tr("{count} nouvelle(s) fiche(s) vont être ajoutée(s) à la collection « {name} ».\n\nLes fiches déjà présentes ne seront pas modifiées. Continuer ?", self.language).format(count=len(selected), name=collection_name))
            yes = box.addButton(tr("Ajouter les fiches", self.language), QMessageBox.ButtonRole.AcceptRole)
            no = box.addButton("Cancel" if self.language.lower().startswith("en") else "Annuler", QMessageBox.ButtonRole.RejectRole)
            box.setDefaultButton(yes)
            yes.setFocus(Qt.FocusReason.OtherFocusReason)
            box.exec()
            if box.clickedButton() is not yes:
                return
            try:
                backup = self._external_backup_destination()
                result = self._external_add_selected_rows(selected, dlg)
            except Exception as exc:
                QMessageBox.critical(dlg, tr("Ajout des fiches", self.language), tr("L’import a été interrompu :\n{error}", self.language).format(error=exc))
                return
            QMessageBox.information(dlg, tr("Ajout terminé", self.language), tr("{added} nouvelle(s) fiche(s) ajoutée(s).\n{photos} photo(s) importée(s).\n\nSauvegarde de sécurité : {backup}", self.language).format(added=result.get("added", 0), photos=result.get("photos", 0), backup=backup.name))
            dlg.accept()
        next_btn.setText("Ajouter les fiches sélectionnées")
        next_btn.clicked.connect(validate_selection); footer.addWidget(next_btn); lay.addLayout(footer)
        translate_widget_tree(dlg, self.language)
        dlg.exec()

    def _preview_external_matching(self) -> None:
        if self.source_path is None or self.destination_path is None:
            QMessageBox.information(self, "Rapprochement", "Choisissez d’abord la collection G-Skol et la source Access.")
            return
        table = str(self.source_table_combo.currentData() or "")
        source_key = str(self.source_key_combo.currentData() or "")
        dest_key = str(self.dest_key_combo.currentData() or "")
        if not table or not source_key or not dest_key:
            QMessageBox.information(self, "Rapprochement", "Choisissez la table et les deux clés de rapprochement.")
            return
        data = self.collection_combo.currentData()
        cid = int(data.get("id") or 0) if isinstance(data, dict) else 0
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor); QApplication.processEvents()
        try:
            source_rows = CollectionImportDialog._read_access_rows(self.source_path, table, [source_key])
            rm = RecordManager(self.destination_path)
            records = rm.list_records(cid)
            custom_by_record = rm.custom_values_for_collection(cid) if dest_key not in FIELD_BY_KEY else {}
        except Exception as exc:
            QMessageBox.critical(self, "Rapprochement", str(exc)); return
        finally:
            QApplication.restoreOverrideCursor()
        dest_values = {}
        duplicate_dest = set()
        for record in records:
            rid = int(record.get("id") or 0)
            raw = record.get(dest_key, "") if dest_key in record else custom_by_record.get(rid, {}).get(dest_key, "")
            token = self._external_match_token(raw)
            if not token:
                continue
            if token in dest_values:
                duplicate_dest.add(token)
            else:
                dest_values[token] = rid
        matched = 0; unmatched = 0; blank = 0; seen_source = set(); duplicate_source = set()
        for row in source_rows:
            token = self._external_match_token(row.get(source_key, ""))
            if not token:
                blank += 1; continue
            if token in seen_source:
                duplicate_source.add(token)
            seen_source.add(token)
            if token in dest_values and token not in duplicate_dest:
                matched += 1
            else:
                unmatched += 1
        warnings = []
        if duplicate_source: warnings.append(f"{len(duplicate_source)} clé(s) en double dans Access")
        if duplicate_dest: warnings.append(f"{len(duplicate_dest)} clé(s) en double dans G-Skol")
        suffix = (" — Attention : " + ", ".join(warnings) + ".") if warnings else ""
        self.match_summary.setText(
            f"Vérification terminée : {len(source_rows)} ligne(s) source ; {matched} rapprochement(s) unique(s) ; "
            f"{unmatched} sans correspondance ; {blank} clé(s) vide(s).{suffix} Aucune fiche n’a été modifiée."
        )
        self._external_matching_verified = True
        self._populate_external_field_mapping()



class ExchangeModelImportDialog(QDialog):
    """Importe un .colmod dans la bibliothèque locale, sans modifier de collection."""
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.language = str(getattr(parent, "language", "fr") or "fr")
        self.setWindowTitle(tr("Importer un modèle G-Skol", self.language))
        self.resize(790, 330); self.setMinimumSize(680, 310)
        self._root = Path(__file__).resolve().parents[2]
        self._model_path = None
        self._envelope = None

        root = QVBoxLayout(self); root.setContentsMargins(30,26,30,24); root.setSpacing(16)
        title = QLabel("Importer un modèle G-Skol (.colmod)")
        title.setStyleSheet("font-size: 24px; font-weight: 800;"); root.addWidget(title)
        intro = QLabel(
            "Choisissez le modèle reçu. G-Skol reconnaîtra automatiquement s’il s’agit d’un modèle de Fiche, de Tableau, de Requête ou d’État, "
            "puis vous proposera la bibliothèque correspondante. Aucune collection ne sera modifiée."
        )
        intro.setWordWrap(True); root.addWidget(intro)

        frame = QFrame(); frame.setFrameShape(QFrame.Shape.StyledPanel); form = QFormLayout(frame)
        file_row = QHBoxLayout(); self.file_edit = QLineEdit(); self.file_edit.setReadOnly(True)
        self.browse = QPushButton("Parcourir…"); self.browse.clicked.connect(self._browse)
        file_row.addWidget(self.file_edit, 1); file_row.addWidget(self.browse); form.addRow("Modèle :", file_row)
        root.addWidget(frame)

        note = QLabel(
            "Le modèle importé rejoint simplement la bibliothèque correspondante. Pour l’utiliser, ouvrez ensuite une collection "
            "et choisissez ce modèle depuis le module correspondant."
        )
        note.setWordWrap(True); note.setStyleSheet("font-style: italic;"); root.addWidget(note)
        root.addStretch(1)
        row = QHBoxLayout(); cancel = QPushButton("Annuler"); cancel.clicked.connect(self.close); row.addWidget(cancel)
        row.addStretch(1); self.go = QPushButton("Choisir le dossier et importer…"); self.go.setEnabled(False)
        self.go.clicked.connect(self._import); row.addWidget(self.go); root.addLayout(row)
        translate_widget_tree(self, self.language)

    def _browse(self):
        documents = Path.home() / "Documents"; documents = documents if documents.exists() else Path.home()
        filename, _ = QFileDialog.getOpenFileName(self, "Importer un modèle G-Skol", str(documents), tr("Modèle G-Skol (*.colmod)", self.language))
        if not filename:
            return
        try:
            envelope = read_model(filename)
            if str(envelope.get("kind") or "") not in ("fiche", "tableau", "requete", "etat"):
                raise ValueError("Cette version accepte les modèles de Fiche, de Tableau, de Requête et d’État.")
        except Exception as exc:
            QMessageBox.warning(self, tr("Modèle non valide", self.language), str(exc)); return
        self._model_path = Path(filename)
        self._envelope = envelope
        self.file_edit.setText(str(self._model_path))
        self.go.setEnabled(True)
        # Le fichier est choisi : l’action logique suivante devient le bouton d’import.
        self.go.setDefault(True)
        self.go.setFocus(Qt.FocusReason.OtherFocusReason)

    def _import(self):
        if self._model_path is None or not isinstance(self._envelope, dict):
            return
        try:
            kind = str(self._envelope.get("kind") or "")
            if kind not in ("fiche", "tableau", "requete", "etat"):
                raise ValueError("Cette version accepte les modèles de Fiche, de Tableau, de Requête et d’État.")
            library_title = {
                "fiche": "Modèles de Fiches",
                "tableau": "Modèles de Tableaux",
                "requete": "Modèles de Requêtes",
                "etat": "Modèles d'États",
            }[kind]
            model_root = library_root(Path(WORKSPACE), kind)
            default_name = str(self._envelope.get("name") or self._model_path.stem).strip() or self._model_path.stem
            target = choose_model_save_path(self, model_root, default_name, library_title)
            if not target:
                return
            write_model(
                target,
                kind=kind,
                name=Path(target).stem,
                source_collection=str(self._envelope.get("source_collection") or ""),
                payload=dict(self._envelope.get("payload") or {}),
                field_manifest=dict(self._envelope.get("field_manifest") or {}),
            )
            usage = {
                "fiche": "Atelier → Ouvrir un modèle…",
                "tableau": "Vue Tableau → Ouvrir un modèle…",
                "requete": "Requête multicritère → Ouvrir un modèle…",
                "etat": "États → Ouvrir un modèle d’État…",
            }[kind]
            QMessageBox.information(
                self, "Importation terminée",
                f"Le modèle a été enregistré dans la bibliothèque {library_title}.\n\n"
                f"Aucune collection n’a été modifiée. Vous pourrez l’utiliser depuis {usage}."
            )
            self.accept()
        except Exception as exc:
            QMessageBox.critical(self, "Importation impossible", str(exc))


class CollectionImportModeDialog(QDialog):
    """Première étape du parcours d'importation : mode libre ou modèle G-Skol.

    Brique 2.3.1 : sélection visuelle uniquement. Le raccordement du sélecteur
    de modèles et de la structure de destination appartient à l'étape suivante.
    """

    def __init__(self, parent=None, language="fr"):
        super().__init__(parent)
        self.language = str(language or "fr")
        self.setWindowTitle(tr("Choisir le mode de création", self.language))
        self.setMinimumSize(570, 320)
        self.resize(660, 350)
        self.setModal(True)
        self.selected_mode = None
        self.selected_model_key = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(15)
        title = QLabel(tr("Comment souhaitez-vous créer votre collection ?", self.language))
        title.setStyleSheet("font-size: 20px; font-weight: 750;")
        layout.addWidget(title)
        intro = QLabel(tr("Choisissez le mode de création avant de sélectionner la base à importer.", self.language))
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self.free_option = QRadioButton(tr("Modèle libre — créer les champs à partir de la base importée", self.language))
        self.free_option.setChecked(True)
        self.model_option = QRadioButton(tr("Modèle G-Skol — utiliser un modèle maître ou personnel", self.language))
        self.free_option.setMinimumHeight(48)
        self.model_option.setMinimumHeight(48)
        layout.addWidget(self.free_option)
        layout.addWidget(self.model_option)
        layout.addStretch(1)
        row = QHBoxLayout()
        row.addStretch(1)
        cancel = QPushButton(tr("Annuler", self.language))
        cancel.clicked.connect(self.reject)
        next_button = QPushButton(tr("Suivant", self.language))
        next_button.setDefault(True)
        next_button.clicked.connect(self._next)
        row.addWidget(cancel)
        row.addWidget(next_button)
        layout.addLayout(row)

    def _next(self):
        if self.model_option.isChecked():
            # Brique 2.3.2 : réutiliser l'écran natif de choix de modèle.
            # Ne pas créer de collection à cette étape.
            from ui.collection_model_selector_dialog import CollectionModelSelectorDialog
            selector = CollectionModelSelectorDialog(self, self.language)
            if selector.exec() != QDialog.DialogCode.Accepted:
                return
            self.selected_mode = "model"
            self.selected_model_key = selector.selected_model_key()
            self.accept()
            return
        self.selected_mode = "free"
        self.selected_model_key = "blank"
        self.accept()


class ImportMenuDialog(QDialog):
    """Deuxième niveau : choix du type d'importation."""

    def __init__(self, parent: QWidget | None = None, language: str = "fr") -> None:
        super().__init__(parent)
        self.language = str(language or "fr")
        self.setWindowTitle(tr("Importation", self.language))
        self.resize(820, 610)
        self.setMinimumSize(700, 540)
        self.setModal(False)
        self._child_windows: list[QDialog] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(34, 30, 34, 28); layout.setSpacing(18)
        title = QLabel(tr("Importation", self.language)); title.setStyleSheet("font-size: 26px; font-weight: 800;"); layout.addWidget(title)
        intro = QLabel(tr("Choisissez le type d’importation. G-Skol vous guidera ensuite étape par étape dans le module correspondant.", self.language))
        intro.setWordWrap(True); intro.setStyleSheet("font-size: 14px;"); layout.addWidget(intro)
        style = ("QPushButton { text-align: left; padding: 16px 20px; font-size: 17px; font-weight: 750; }"
                 "QPushButton:hover { background: rgba(155,73,57,0.10); }")
        specs = [
            (tr("Importation et création d’une collection", self.language), self._open_collection_import,
             tr("Créer une nouvelle collection G-Skol depuis une source extérieure.", self.language)),
            (tr("Importation de référentiels dans une collection existante", self.language), self._open_reference_import,
             tr("Ajouter, compléter ou créer des référentiels dans une collection existante.", self.language)),
            (tr("Ajouter des fiches depuis une source extérieure", self.language), self._open_external_data_import,
             tr("Ajouter de nouvelles fiches à la suite d’une collection existante sans modifier les fiches déjà présentes.", self.language)),
            (tr("Importer un modèle G-Skol  (.colmod)", self.language), self._open_exchange_model_import,
             tr("Enregistrer dans la bibliothèque un modèle de Fiche ou de Tableau reçu d’un autre utilisateur, sans modifier de collection.", self.language)),
        ]
        for label, slot, tip in specs:
            b=QPushButton(label); b.setMinimumHeight(84); b.setStyleSheet(style); b.setToolTip(tip); b.clicked.connect(slot); layout.addWidget(b)
        layout.addStretch(1)
        row=QHBoxLayout(); back=QPushButton(tr("Retour", self.language)); back.clicked.connect(self.close); row.addWidget(back); row.addStretch(1)
        close=QPushButton(tr("Fermer", self.language)); close.clicked.connect(self._close_all); row.addWidget(close); layout.addLayout(row)

    def _track_child(self, dialog: QDialog) -> None:
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True); self._child_windows.append(dialog)
        dialog.destroyed.connect(lambda *_args, d=dialog: self._forget_child(d)); dialog.show(); dialog.raise_(); dialog.activateWindow()
    def _forget_child(self, dialog: QDialog) -> None:
        try: self._child_windows.remove(dialog)
        except ValueError: pass
    def _open_collection_import(self):
        choice = CollectionImportModeDialog(self, self.language)
        if choice.exec() != QDialog.DialogCode.Accepted:
            return
        dialog = CollectionImportDialog(self, self.language)
        # Conserver le choix pour le raccordement des champs et de la création
        # dans la brique suivante. Aucun changement du moteur d'import ici.
        dialog.import_model_mode = choice.selected_mode
        dialog.import_model_key = choice.selected_model_key
        self._track_child(dialog)
    def _open_reference_import(self): self._track_child(SQLiteReferenceImportDialog(self))
    def _open_external_data_import(self): self._track_child(ExternalDataImportDialog(self))
    def _open_exchange_model_import(self): self._track_child(ExchangeModelImportDialog(self))
    def _close_all(self):
        top=self.parentWidget(); self.close()
        if isinstance(top, QDialog): top.close()


def _refresh_open_collection_lists() -> None:
    """Rafraîchit immédiatement toute liste « Ouvrir une collection » déjà affichée."""
    try:
        for widget in QApplication.topLevelWidgets():
            refresh = getattr(widget, "_refresh_files", None)
            if callable(refresh):
                try:
                    refresh(preserve_selection=True)
                except TypeError:
                    refresh()
    except Exception:
        pass


class BackupManagementDialog(QDialog):
    """Gestion des sauvegardes internes du Workspace."""
    def __init__(self, parent: QWidget | None = None, language: str = "fr") -> None:
        super().__init__(parent)
        self.language = str(language or "fr")
        self.setWindowTitle(tr("Gérer les sauvegardes", self.language))
        self.resize(940, 700); self.setMinimumSize(800, 580)
        self._folder = Path(WORKSPACE) / "Sauvegardes"
        self._folder.mkdir(parents=True, exist_ok=True)
        root=QVBoxLayout(self); root.setContentsMargins(24,22,24,20); root.setSpacing(10)
        title=QLabel(tr("Gérer les sauvegardes",self.language)); title.setStyleSheet("font-size: 22px; font-weight: 800;"); root.addWidget(title)
        intro=QLabel(tr("Les sauvegardes volontaires et les copies de sécurité créées automatiquement par G-Skol sont séparées afin d’éviter toute confusion.",self.language)); intro.setWordWrap(True); root.addWidget(intro)
        self.user_label=QLabel(); self.user_label.setStyleSheet("font-size: 15px; font-weight: 750;"); root.addWidget(self.user_label)
        self.user_table=self._make_table(); self.user_table.itemDoubleClicked.connect(lambda *_: self._open_selected_backup()); self.user_table.itemSelectionChanged.connect(self._update_buttons); root.addWidget(self.user_table,1)
        ur=QHBoxLayout(); self.user_all=QPushButton(tr("Tout sélectionner",self.language)); self.user_all.clicked.connect(lambda:self._select_all(self.user_table)); ur.addWidget(self.user_all)
        self.user_none=QPushButton(tr("Tout désélectionner",self.language)); self.user_none.clicked.connect(self.user_table.clearSelection); ur.addWidget(self.user_none); ur.addStretch(1)
        self.user_open=QPushButton(tr("Ouvrir la sauvegarde",self.language)); self.user_open.clicked.connect(self._open_selected_backup); ur.addWidget(self.user_open)
        self.user_delete=QPushButton(tr("Supprimer les sauvegardes sélectionnées",self.language)); self.user_delete.clicked.connect(lambda:self._delete_selected(self.user_table,False)); ur.addWidget(self.user_delete); root.addLayout(ur)
        self.auto_label=QLabel(); self.auto_label.setStyleSheet("font-size: 15px; font-weight: 750;"); root.addWidget(self.auto_label)
        self.auto_table=self._make_table(); self.auto_table.itemSelectionChanged.connect(self._update_buttons); root.addWidget(self.auto_table,1)
        ar=QHBoxLayout(); self.auto_all=QPushButton(tr("Tout sélectionner",self.language)); self.auto_all.clicked.connect(lambda:self._select_all(self.auto_table)); ar.addWidget(self.auto_all)
        self.auto_none=QPushButton(tr("Tout désélectionner",self.language)); self.auto_none.clicked.connect(self.auto_table.clearSelection); ar.addWidget(self.auto_none); ar.addStretch(1)
        self.auto_delete=QPushButton(tr("Supprimer les sauvegardes sélectionnées",self.language)); self.auto_delete.clicked.connect(lambda:self._delete_selected(self.auto_table,True)); ar.addWidget(self.auto_delete); root.addLayout(ar)
        row=QHBoxLayout(); row.addStretch(1); close=QPushButton(tr("Fermer",self.language)); close.clicked.connect(self.close); row.addWidget(close); root.addLayout(row)
        self._refresh()

    def _make_table(self):
        t=QTableWidget(0,3); t.setHorizontalHeaderLabels([tr("Sauvegarde",self.language),tr("Date / heure",self.language),tr("Taille",self.language)])
        t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); t.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection); t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); t.verticalHeader().setVisible(False)
        t.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch); t.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeMode.Interactive); t.horizontalHeader().setSectionResizeMode(2,QHeaderView.ResizeMode.Interactive); t.setColumnWidth(1,180); t.setColumnWidth(2,110)
        return t

    def _fmt_size(self, n):
        value=float(n)
        english=self.language.lower().startswith("en")
        units=("B","KB","MB","GB") if english else ("o","Ko","Mo","Go")
        for unit in units:
            if value < 1024 or unit==units[-1]:
                if unit in (units[0], units[1]):
                    return f"{value:.0f} {unit}"
                text=f"{value:.2f} {unit}"
                return text if english else text.replace(".", ",")
            value/=1024
        return f"{n} {units[0]}"

    @staticmethod
    def _backup_size(path):
        try:
            if path.is_file(): return path.stat().st_size
            return sum(p.stat().st_size for p in path.rglob('*') if p.is_file())
        except OSError: return 0

    @staticmethod
    def _is_auto(path): return bool(re.search(r"-avant-(?:ajout|import)-",path.name,re.I))

    @staticmethod
    def _coldb_files(path):
        if not path.is_dir(): return []
        candidates=[]
        for root in (path/'Workspace'/'Collections', path/'Collections', path):
            if root.is_dir():
                candidates=[p for p in root.rglob('*.coldb') if p.is_file()]
                if candidates: break
        return sorted(candidates,key=lambda p:p.name.casefold())

    @staticmethod
    def _collection_name(path):
        try:
            rows=CollectionManager(path).inspect_collections()
            if rows: return str(rows[0].get('name') or path.stem).strip() or path.stem
        except Exception: pass
        return path.stem

    @staticmethod
    def _stamp(path):
        m=re.search(r"(20\d\d-\d\d-\d\d-\d{6})",path.name)
        return m.group(1) if m else datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d-%H%M%S")

    def _display_name(self,path):
        files=self._coldb_files(path)
        if len(files)==1: return f"{self._collection_name(files[0])} - {self._stamp(path)}"
        if len(files)>1:
            english=self.language.lower().startswith("en")
            if path.name.casefold().startswith(("sauvegarde complète","complete backup")):
                return (tr("Sauvegarde complète", self.language) + " - ")+self._stamp(path)
            if re.match(r"^Sauvegarde-20\d\d-",path.name,re.I):
                return (tr("Sauvegarde complète", self.language) + " - ")+self._stamp(path)
            return (tr("Sauvegarde de plusieurs collections", self.language) + " - ")+self._stamp(path)
        return path.name

    def _fill(self,table,files):
        table.setRowCount(len(files))
        for r,p in enumerate(files):
            st=p.stat(); a=QTableWidgetItem(self._display_name(p)); a.setData(Qt.ItemDataRole.UserRole,str(p)); table.setItem(r,0,a)
            table.setItem(r,1,QTableWidgetItem(datetime.fromtimestamp(st.st_mtime).strftime("%d/%m/%Y  %H:%M:%S")))
            z=QTableWidgetItem(self._fmt_size(self._backup_size(p))); z.setTextAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter); table.setItem(r,2,z)
        table.clearSelection()

    def _refresh(self):
        files=sorted([p for p in self._folder.iterdir() if p.is_file() or p.is_dir()],key=lambda p:p.stat().st_mtime,reverse=True)
        auto=[p for p in files if self._is_auto(p)]; user=[p for p in files if not self._is_auto(p)]
        self._fill(self.user_table,user); self._fill(self.auto_table,auto)
        if self.language.lower().startswith("en"):
            self.user_label.setText(f"User-created backups — {len(user)} item(s) — {self._fmt_size(sum(self._backup_size(p) for p in user))}")
            self.auto_label.setText(f"Automatic temporary backups (before adding or importing) — {len(auto)} item(s) — {self._fmt_size(sum(self._backup_size(p) for p in auto))}")
        else:
            self.user_label.setText(tr("Sauvegardes volontaires utilisateur", self.language) + f" — {len(user)} " + tr("élément(s)", self.language) + f" — {self._fmt_size(sum(self._backup_size(p) for p in user))}")
            self.auto_label.setText(tr("Sauvegardes temporaires automatiques (avant ajout ou import)", self.language) + f" — {len(auto)} " + tr("élément(s)", self.language) + f" — {self._fmt_size(sum(self._backup_size(p) for p in auto))}")
        self._update_buttons()

    def _select_all(self,table): table.setFocus(Qt.FocusReason.OtherFocusReason); table.selectAll(); self._update_buttons()

    def _selected_paths(self,table):
        result=[]
        for idx in table.selectionModel().selectedRows():
            it=table.item(idx.row(),0)
            if it: result.append(Path(str(it.data(Qt.ItemDataRole.UserRole))))
        return result

    def _update_buttons(self):
        up=self._selected_paths(self.user_table); ap=self._selected_paths(self.auto_table)
        self.user_all.setEnabled(self.user_table.rowCount()>0); self.user_none.setEnabled(bool(up)); self.user_delete.setEnabled(bool(up)); self.auto_all.setEnabled(self.auto_table.rowCount()>0); self.auto_none.setEnabled(bool(ap)); self.auto_delete.setEnabled(bool(ap))
        self.user_open.setEnabled(len(up)==1 and len(self._coldb_files(up[0]))>1)

    def _open_selected_backup(self):
        paths=self._selected_paths(self.user_table)
        if len(paths)!=1: return
        files=self._coldb_files(paths[0])
        if len(files)<=1: return
        dlg=BackupContentsDialog(paths[0],self,self.language); dlg.exec(); self._refresh()

    def _delete_selected(self,table,automatic):
        paths=self._selected_paths(table)
        if not paths: return
        size=sum(self._backup_size(p) for p in paths if p.exists())
        names = [self._display_name(p) for p in paths]
        grouped = [(p, self._coldb_files(p)) for p in paths]
        grouped = [(p, files) for p, files in grouped if len(files) > 1]

        english=self.language.lower().startswith("en")
        if grouped:
            files_to_delete = []
            for p in paths:
                files_to_delete.extend(self._coldb_files(p))

            dlg = QDialog(self)
            dlg.setWindowTitle(tr("Confirmer la suppression", self.language))
            dlg.resize(650, min(700, 300 + 24 * min(len(files_to_delete), 14)))
            lay = QVBoxLayout(dlg)

            if len(paths) == 1:
                intro = QLabel((
                    f"You are about to permanently delete the following backup:\n« {names[0]} »\n\n"
                    f"It contains {len(files_to_delete)} collection(s). The following backed-up files will be deleted:"
                ) if english else (
                    f"Vous allez supprimer définitivement la sauvegarde suivante :\n« {names[0]} »\n\n"
                    f"Elle contient {len(files_to_delete)} collection(s). Les fichiers sauvegardés suivants seront supprimés :"
                ))
            else:
                intro = QLabel((
                    f"You are about to permanently delete {len(paths)} backups.\n\n"
                    f"A total of {len(files_to_delete)} collection file(s) will be deleted:"
                ) if english else (
                    f"Vous allez supprimer définitivement {len(paths)} sauvegardes.\n\n"
                    f"Au total, {len(files_to_delete)} fichier(s) de collection seront supprimés :"
                ))
            intro.setWordWrap(True)
            lay.addWidget(intro)

            file_table = QTableWidget(len(files_to_delete), 1)
            file_table.setHorizontalHeaderLabels([tr("Collection", self.language)])
            file_table.verticalHeader().setVisible(False)
            file_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            file_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
            file_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            for row, fp in enumerate(files_to_delete):
                file_table.setItem(row, 0, QTableWidgetItem(fp.name))
            lay.addWidget(file_table, 1)

            info = QLabel((f"Space freed: {self._fmt_size(size)}.\n\nThis deletion cannot be undone.") if english else
                          (f"Espace libéré : {self._fmt_size(size)}.\n\nCette suppression est irréversible."))
            info.setWordWrap(True)
            lay.addWidget(info)

            buttons = QHBoxLayout()
            buttons.addStretch(1)
            delete_btn = QPushButton(tr("SUPPRIMER", self.language))
            cancel_btn = QPushButton(tr("Annuler", self.language))
            buttons.addWidget(delete_btn)
            buttons.addWidget(cancel_btn)
            lay.addLayout(buttons)
            accepted = {"delete": False}
            def _confirm_delete():
                accepted["delete"] = True
                dlg.accept()
            delete_btn.clicked.connect(_confirm_delete)
            cancel_btn.clicked.connect(dlg.reject)
            dlg.exec()
            if not accepted["delete"]:
                return
        else:
            if english:
                if len(names) == 1:
                    detail = f"You are about to permanently delete the following backup:\n\n« {names[0]} »"
                elif len(names) <= 6:
                    detail = f"You are about to permanently delete {len(names)} backups:\n\n" + "\n".join(f"• {name}" for name in names)
                else:
                    detail = f"You are about to permanently delete {len(names)} backups:\n\n" + "\n".join(f"• {name}" for name in names[:6]) + f"\n… and {len(names)-6} more"
                text=f"{detail}\n\nSpace freed: {self._fmt_size(size)}.\n\nThis deletion cannot be undone."
            else:
                if len(names) == 1:
                    detail = f"Vous allez supprimer définitivement la sauvegarde suivante :\n\n« {names[0]} »"
                elif len(names) <= 6:
                    detail = f"Vous allez supprimer définitivement {len(names)} sauvegardes :\n\n" + "\n".join(f"• {name}" for name in names)
                else:
                    detail = f"Vous allez supprimer définitivement {len(names)} sauvegardes :\n\n" + "\n".join(f"• {name}" for name in names[:6]) + f"\n… et {len(names)-6} autre(s)"
                text=f"{detail}\n\nEspace libéré : {self._fmt_size(size)}.\n\nCette suppression est irréversible."
            box=QMessageBox(self); box.setWindowTitle(tr("Confirmer la suppression",self.language)); box.setIcon(QMessageBox.Icon.Warning); box.setText(text); delete=box.addButton(tr("SUPPRIMER",self.language),QMessageBox.ButtonRole.DestructiveRole); box.addButton(tr("Annuler",self.language),QMessageBox.ButtonRole.RejectRole); box.exec()
            if box.clickedButton() is not delete:return
        errors=[]
        for p in paths:
            try:
                if p.is_dir(): shutil.rmtree(p)
                else:p.unlink(missing_ok=True)
            except Exception as exc:errors.append(f"{p.name} : {exc}")
        self._refresh()
        _refresh_open_collection_lists()
        if errors: QMessageBox.warning(self,tr("Suppression incomplète",self.language),"\n".join(errors[:8]))


class BackupContentsDialog(QDialog):
    def __init__(self,backup_path,parent=None,language="fr"):
        super().__init__(parent); self.language=str(language or 'fr'); self.backup_path=Path(backup_path); self.manager=parent
        self.setWindowTitle(tr("Contenu de la sauvegarde",self.language)); self.resize(760,520)
        root=QVBoxLayout(self); title=QLabel(self.manager._display_name(self.backup_path)); title.setStyleSheet("font-size:20px;font-weight:800;"); root.addWidget(title)
        self.table=QTableWidget(0,3); self.table.setHorizontalHeaderLabels([tr("Supprimer",self.language),tr("Collection",self.language),("Size (MB)" if self.language.lower().startswith("en") else "Taille (Mo)")]); self.table.verticalHeader().setVisible(False); self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); self.table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.ResizeToContents); self.table.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeMode.Stretch); self.table.horizontalHeader().setSectionResizeMode(2,QHeaderView.ResizeMode.ResizeToContents); root.addWidget(self.table,1)
        row=QHBoxLayout(); allb=QPushButton(tr("Tout sélectionner",self.language)); allb.clicked.connect(lambda:self._set_checks(True)); row.addWidget(allb); noneb=QPushButton(tr("Tout désélectionner",self.language)); noneb.clicked.connect(lambda:self._set_checks(False)); row.addWidget(noneb); row.addStretch(1); delete=QPushButton(tr("Supprimer les collections sélectionnées",self.language)); delete.clicked.connect(self._delete); row.addWidget(delete); close=QPushButton(tr("Fermer",self.language)); close.clicked.connect(self.accept); row.addWidget(close); root.addLayout(row); self._refresh()

    def _refresh(self):
        files=self.manager._coldb_files(self.backup_path); self.table.setRowCount(len(files))
        for r,p in enumerate(files):
            c=QTableWidgetItem(); c.setFlags(Qt.ItemFlag.ItemIsEnabled|Qt.ItemFlag.ItemIsUserCheckable); c.setCheckState(Qt.CheckState.Unchecked); c.setData(Qt.ItemDataRole.UserRole,str(p)); self.table.setItem(r,0,c); self.table.setItem(r,1,QTableWidgetItem(self.manager._collection_name(p))); self.table.setItem(r,2,QTableWidgetItem((f"{p.stat().st_size/(1024*1024):.2f} MB") if self.language.lower().startswith("en") else (f"{p.stat().st_size/(1024*1024):.2f} Mo")))

    def _set_checks(self,on):
        for r in range(self.table.rowCount()): self.table.item(r,0).setCheckState(Qt.CheckState.Checked if on else Qt.CheckState.Unchecked)

    def _delete(self):
        files=[Path(str(self.table.item(r,0).data(Qt.ItemDataRole.UserRole))) for r in range(self.table.rowCount()) if self.table.item(r,0).checkState()==Qt.CheckState.Checked]
        if not files:return
        was_complete=self.backup_path.name.casefold().startswith(("sauvegarde complète","complete backup","sauvegarde-"))
        collection_names = [self.manager._collection_name(p) for p in files]
        english=self.language.lower().startswith("en")
        if english:
            if len(collection_names) == 1:
                selected_text = f"Selected collection: « {collection_names[0]} »"
            else:
                selected_text = f"{len(collection_names)} selected collections:\n" + "\n".join(f"• {n}" for n in collection_names[:8])
                if len(collection_names) > 8:
                    selected_text += f"\n… and {len(collection_names)-8} more"
            backup_name = self.manager._display_name(self.backup_path)
            if was_complete:
                text=(f"Complete backup concerned:\n« {backup_name} »\n\n"
                      "This complete backup will be modified and will no longer contain all of the original collections.\n\n"
                      + selected_text + "\n\nContinue?")
            else:
                text=(f"Backup concerned: « {backup_name} »\n\n"
                      f"Delete {len(files)} collection(s) from this backup?\n\n{selected_text}")
        else:
            if len(collection_names) == 1:
                selected_text = f"Collection sélectionnée : « {collection_names[0]} »"
            else:
                selected_text = f"{len(collection_names)} collections sélectionnées :\n" + "\n".join(f"• {n}" for n in collection_names[:8])
                if len(collection_names) > 8:
                    selected_text += f"\n… et {len(collection_names)-8} autre(s)"
            backup_name = self.manager._display_name(self.backup_path)
            if was_complete:
                text=(f"Sauvegarde complète concernée :\n« {backup_name} »\n\n"
                      "Cette sauvegarde complète sera modifiée et ne contiendra plus toutes les collections d'origine.\n\n"
                      + selected_text + "\n\nContinuer ?")
            else:
                text=(f"Sauvegarde concernée : « {backup_name} »\n\n"
                      f"Supprimer {len(files)} collection(s) de cette sauvegarde ?\n\n{selected_text}")
        box=QMessageBox(self); box.setWindowTitle(tr("Confirmer la suppression",self.language)); box.setIcon(QMessageBox.Icon.Question); box.setText(tr(text,self.language))
        yes_btn=box.addButton(tr("Oui",self.language),QMessageBox.ButtonRole.AcceptRole); box.addButton(tr("Non",self.language),QMessageBox.ButtonRole.RejectRole); box.exec()
        if box.clickedButton() is not yes_btn:return
        for p in files:
            try:p.unlink()
            except Exception as exc: QMessageBox.warning(self,"Suppression impossible",str(exc)); return
        self._update_manifest()
        self._rename_after_change()
        self._refresh()
        if self.table.rowCount()==0:self.accept()

    def _update_manifest(self):
        mf=self.backup_path/'manifest.json'
        if not mf.is_file():return
        try:
            data=json.loads(mf.read_text(encoding='utf-8')); existing={str(p.relative_to(self.backup_path)).replace('\\','/') for p in self.manager._coldb_files(self.backup_path)}
            data['collections']=[x for x in data.get('collections',[]) if str(x).replace('\\','/') in existing]
            data['files']=[x for x in data.get('files',[]) if str(x.get('path','')).replace('\\','/') in existing or not str(x.get('path','')).lower().endswith('.coldb')]
            mf.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
        except Exception: pass

    def _rename_after_change(self):
        files=self.manager._coldb_files(self.backup_path); stamp=self.manager._stamp(self.backup_path)
        if not files:return
        base=(f"{self.manager._collection_name(files[0])} - {stamp}" if len(files)==1 else f"Sauvegarde de plusieurs collections - {stamp}")
        target=self.backup_path.with_name(base); n=2
        while target.exists() and target!=self.backup_path:
            target=self.backup_path.with_name(f"{base} - {n}"); n+=1
        if target!=self.backup_path:
            self.backup_path.rename(target); self.backup_path=target


class RestoreBackupDialog(QDialog):
    """Restore one or more .coldb files from a G-Skol backup folder."""
    def __init__(self, parent=None, language="fr"):
        super().__init__(parent)
        self.language = str(language or "fr")
        self.workspace = Path(WORKSPACE)
        self.collections_dir = self.workspace / "Collections"
        self.collections_dir.mkdir(parents=True, exist_ok=True)
        self._selected_backup = None
        self.setWindowTitle(tr("Restaurer une sauvegarde", self.language))
        self.resize(1020, 700); self.setMinimumSize(850, 580)
        root=QVBoxLayout(self); root.setContentsMargins(24,22,24,20); root.setSpacing(12)
        title=QLabel(tr("Restaurer une sauvegarde", self.language)); title.setStyleSheet("font-size: 22px; font-weight: 800;"); root.addWidget(title)
        self.pages=QStackedWidget(); root.addWidget(self.pages,1)

        # Step 1: choose and validate a backup folder.
        p1=QWidget(); l1=QVBoxLayout(p1)
        info=QLabel(tr("Choisissez un dossier de sauvegarde G-Skol. G-Skol l’analysera avant d’afficher les collections disponibles.", self.language)); info.setWordWrap(True); l1.addWidget(info)
        l1.addSpacing(140)
        internal_row=QHBoxLayout()
        internal_label=QLabel(tr("Sauvegardes internes (Workspace)", self.language)); internal_label.setStyleSheet("font-weight: 700;"); internal_row.addWidget(internal_label)
        internal_row.addStretch(1)
        internal_btn=QPushButton(tr("Choisir dans le Workspace…", self.language)); internal_btn.clicked.connect(self._choose_internal); internal_row.addWidget(internal_btn)
        l1.addLayout(internal_row)
        l1.addSpacing(140)

        external_row=QHBoxLayout()
        external_label=QLabel(tr("Sauvegarde stockée ailleurs dans Windows", self.language)); external_label.setStyleSheet("font-weight: 700;"); external_row.addWidget(external_label)
        external_row.addStretch(1)
        browse=QPushButton(tr("Parcourir…", self.language)); browse.clicked.connect(self._choose_external); external_row.addWidget(browse)
        l1.addLayout(external_row)

        self.path_edit=QLineEdit(); self.path_edit.setReadOnly(True); self.path_edit.setPlaceholderText(tr("Aucune sauvegarde sélectionnée", self.language)); l1.addWidget(self.path_edit)
        self.status=QLabel(tr("Aucun dossier de sauvegarde sélectionné.",self.language)); self.status.setWordWrap(True); l1.addWidget(self.status); l1.addStretch(1)
        nav=QHBoxLayout(); nav.addStretch(1); self.next_btn=QPushButton(tr("Suivant",self.language)); self.next_btn.setEnabled(False); self.next_btn.clicked.connect(self._next); nav.addWidget(self.next_btn)
        cancel=QPushButton(tr("Annuler",self.language)); cancel.clicked.connect(self.reject); nav.addWidget(cancel); l1.addLayout(nav); self.pages.addWidget(p1)

        # Step 2: select collections and conflict behaviour.
        p2=QWidget(); l2=QVBoxLayout(p2)
        self.summary=QLabel(""); self.summary.setWordWrap(True); l2.addWidget(self.summary)
        self.table=QTableWidget(0,5); self.table.setHorizontalHeaderLabels([tr("Restaurer",self.language),tr("Collection",self.language),tr("Taille (Mo)",self.language),tr("Destination",self.language),tr("En cas de conflit",self.language)])
        hdr=self.table.horizontalHeader()
        for col in range(5): hdr.setSectionResizeMode(col,QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(0,80); self.table.setColumnWidth(1,280); self.table.setColumnWidth(2,100); self.table.setColumnWidth(3,360); self.table.setColumnWidth(4,160)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); l2.addWidget(self.table,1)
        note=QLabel(tr("En cas de renommage, G-Skol ajoute « - Restaurée » (puis « - 2 », « - 3 »… en cas de doublon) au nom du fichier et au nom de la collection. Une collection actuellement ouverte ne peut pas être remplacée : utilisez alors « Conserver les deux ».",self.language)); note.setWordWrap(True); l2.addWidget(note)
        buttons=QHBoxLayout(); allb=QPushButton(tr("Tout sélectionner",self.language)); allb.clicked.connect(self._select_all); buttons.addWidget(allb)
        noneb=QPushButton(tr("Tout désélectionner",self.language)); noneb.clicked.connect(self._select_none); buttons.addWidget(noneb); buttons.addStretch(1)
        back=QPushButton(tr("Retour",self.language)); back.clicked.connect(lambda:self.pages.setCurrentIndex(0)); buttons.addWidget(back)
        self.restore_btn=QPushButton(tr("Restaurer la sélection",self.language)); self.restore_btn.clicked.connect(self._restore); buttons.addWidget(self.restore_btn)
        cancel2=QPushButton(tr("Annuler",self.language)); cancel2.clicked.connect(self.reject); buttons.addWidget(cancel2); l2.addLayout(buttons); self.pages.addWidget(p2)
        translate_widget_tree(self,self.language)

    def _choose_folder(self, start_folder):
        folder=QFileDialog.getExistingDirectory(self,tr("Choisir le dossier de sauvegarde à restaurer",self.language),str(Path(start_folder).resolve()))
        if not folder:
            return
        self.path_edit.setText(folder); self._selected_backup=Path(folder)
        count=self._scan(self._selected_backup)
        self.next_btn.setEnabled(count>0)
        if count>0:
            self.pages.setCurrentIndex(1)
            self.restore_btn.setDefault(True); self.restore_btn.setAutoDefault(True); self.restore_btn.setFocus()

    def _choose_internal(self):
        self._choose_folder(self.workspace/'Sauvegardes')

    def _choose_external(self):
        self._choose_folder(Path.home())

    def _next(self):
        if self.table.rowCount(): self.pages.setCurrentIndex(1)

    def _candidate_files(self, base):
        preferred=[base/'Workspace'/'Collections', base/'Collections', base]
        for folder in preferred:
            if folder.is_dir():
                files=sorted((p for p in folder.glob('*.coldb') if p.is_file()), key=lambda p:p.name.casefold())
                if files: return files
        found=[]
        try:
            for p in base.rglob('*.coldb'):
                if p.is_file(): found.append(p)
        except OSError: pass
        return sorted(set(found), key=lambda p:(len(p.parts),str(p).casefold()))

    def _scan(self, base):
        self.table.setRowCount(0); valid=[]
        for path in self._candidate_files(base):
            try:
                collections=CollectionManager(path).inspect_collections()
                if collections: valid.append((path,collections))
            except Exception: pass
        if not valid:
            self.status.setText(tr("Aucune collection .coldb valide n’a été trouvée dans ce dossier.",self.language)); return 0
        self.status.setText(tr("{count} collection(s) trouvée(s). Cliquez sur Suivant pour choisir celles à restaurer.",self.language).format(count=len(valid)))
        self.summary.setText(tr("{count} collection(s) trouvée(s). Sélectionnez celles à restaurer.",self.language).format(count=len(valid)))
        stamp=datetime.now().strftime('%Y-%m-%d-%H%M%S')
        for path,collections in valid:
            r=self.table.rowCount(); self.table.insertRow(r)
            chk=QTableWidgetItem(); chk.setFlags(Qt.ItemFlag.ItemIsEnabled|Qt.ItemFlag.ItemIsUserCheckable); chk.setCheckState(Qt.CheckState.Checked); chk.setData(Qt.ItemDataRole.UserRole,str(path)); chk.setData(Qt.ItemDataRole.UserRole+1,collections[0]); self.table.setItem(r,0,chk)
            self.table.setItem(r,1,QTableWidgetItem(path.name))
            self.table.setItem(r,2,QTableWidgetItem(f"{path.stat().st_size/(1024*1024):.2f}"))
            dest=self.collections_dir/path.name; self.table.setItem(r,3,QTableWidgetItem(str(dest)))
            combo=QComboBox()
            if dest.exists(): combo.addItem(tr("Remplacer",self.language),'replace'); combo.addItem(tr("Conserver les deux",self.language),'keep')
            else: combo.addItem(tr("Aucun conflit",self.language),'copy'); combo.setEnabled(False)
            combo.setProperty('restore_stamp',stamp); self.table.setCellWidget(r,4,combo)
        return len(valid)

    def _select_all(self):
        for r in range(self.table.rowCount()): self.table.item(r,0).setCheckState(Qt.CheckState.Checked)
    def _select_none(self):
        for r in range(self.table.rowCount()): self.table.item(r,0).setCheckState(Qt.CheckState.Unchecked)

    def _opened_paths(self):
        out=set()
        for w in QApplication.topLevelWidgets():
            db=getattr(w,'_database_path',None)
            if db is None: continue
            try: out.add(Path(db() if callable(db) else db).resolve())
            except Exception: pass
        return out

    def _restore(self):
        rows=[r for r in range(self.table.rowCount()) if self.table.item(r,0).checkState()==Qt.CheckState.Checked]
        if not rows:
            QMessageBox.information(self,tr("Aucune sélection",self.language),tr("Sélectionnez au moins une collection à restaurer.",self.language)); return
        opened=self._opened_paths(); plan=[]
        stamp=datetime.now().strftime('%Y-%m-%d-%H%M%S'); label=tr("Restaurée",self.language)
        for r in rows:
            src=Path(self.table.item(r,0).data(Qt.ItemDataRole.UserRole)); meta=self.table.item(r,0).data(Qt.ItemDataRole.UserRole+1) or {}
            original=self.collections_dir/src.name; combo=self.table.cellWidget(r,4); mode=combo.currentData() if combo else 'copy'
            if original.exists() and mode=='replace' and original.resolve() in opened:
                QMessageBox.warning(self,tr("Collection ouverte",self.language),tr("La collection « {name} » est actuellement ouverte. Fermez-la ou choisissez « Conserver les deux ».",self.language).format(name=original.name)); return
            base_internal=str(meta.get('name') or src.stem)
            restored_file=src.stem+f' - {label}'+src.suffix
            dest=self.collections_dir/restored_file
            suffix_num=None
            n=2
            while dest.exists():
                suffix_num=n
                dest=self.collections_dir/(src.stem+f' - {label} - {n}'+src.suffix); n+=1
            restored_internal=base_internal+f' - {label}' + (f' - {suffix_num}' if suffix_num is not None else '')
            plan.append((src,original,dest,restored_internal,mode))
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor); done=[]
        try:
            for src,original,dest,new_internal_name,mode in plan:
                # Valider la source avant toute suppression.
                if not CollectionManager(src).inspect_collections(): raise ValueError('invalid collection')
                # En mode Remplacer, l'ancienne collection disparaît réellement.
                if original.exists() and mode=='replace': original.unlink()
                shutil.copy2(src,dest)
                mgr=CollectionManager(dest); found=mgr.inspect_collections()
                if not found: raise ValueError('invalid restored collection')
                for c in found:
                    name=new_internal_name if len(found)==1 else new_internal_name+f" - {c['name']}"
                    mgr.rename_collection(int(c['id']),name)
                done.append(dest)
        except Exception as exc:
            QMessageBox.warning(self,tr("Restauration incomplète",self.language),tr("La restauration a été interrompue :",self.language)+f"\n{exc}"); return
        finally: QApplication.restoreOverrideCursor()
        _refresh_open_collection_lists()
        QMessageBox.information(self,tr("Restauration terminée",self.language),tr("{count} collection(s) restaurée(s) dans le Workspace.",self.language).format(count=len(done))); self.accept()

class BackupRestoreDialog(QDialog):
    """Deuxième niveau réservé aux futures fonctions de sauvegarde/restauration."""
    def __init__(self, parent: QWidget | None = None, language: str = "fr") -> None:
        super().__init__(parent)
        self.language = str(language or "fr")
        self.setWindowTitle(tr("Sauvegarde / Restauration", self.language))
        self.resize(760, 510); self.setMinimumSize(680, 465)
        layout=QVBoxLayout(self); layout.setContentsMargins(30,26,30,24); layout.setSpacing(16)
        title=QLabel(tr("Sauvegarde / Restauration", self.language)); title.setStyleSheet("font-size: 24px; font-weight: 800;"); layout.addWidget(title)
        text=QLabel(tr("Créez ou restaurez une sauvegarde, et gérez séparément les sauvegardes volontaires et les copies temporaires automatiques.", self.language))
        text.setWordWrap(True); text.setStyleSheet("font-size: 13px;"); layout.addWidget(text)
        style=("QPushButton { text-align: left; padding: 16px 20px; font-size: 17px; font-weight: 750; }")
        create=QPushButton(tr("Créer une sauvegarde complète des collections internes (dossier Workspace)", self.language))
        create.setMinimumHeight(72); create.setStyleSheet(style)
        create.clicked.connect(self._create_backup)
        layout.addWidget(create)
        selected=QPushButton(tr("Sauvegarder une ou plusieurs collections internes (dossier Workspace)", self.language))
        selected.setMinimumHeight(72); selected.setStyleSheet(style)
        selected.clicked.connect(self._create_selected_backup)
        layout.addWidget(selected)
        restore=QPushButton(tr("Restaurer une sauvegarde", self.language))
        restore.setMinimumHeight(72); restore.setStyleSheet(style)
        restore.clicked.connect(self._restore_backup)
        layout.addWidget(restore)
        manage=QPushButton(tr("Gérer les sauvegardes", self.language))
        manage.setToolTip(tr("Consulter et supprimer séparément les sauvegardes volontaires utilisateur et les sauvegardes temporaires automatiques.", self.language))
        manage.setMinimumHeight(72); manage.setStyleSheet(style); manage.clicked.connect(self._open_manager); layout.addWidget(manage)
        layout.addStretch(1)
        row=QHBoxLayout(); back=QPushButton(tr("Retour", self.language)); back.clicked.connect(self.close); row.addWidget(back); row.addStretch(1)
        close=QPushButton(tr("Fermer", self.language)); close.clicked.connect(self._close_all); row.addWidget(close); layout.addLayout(row)
    def _restore_backup(self):
        RestoreBackupDialog(self, self.language).exec()

    def _create_selected_backup(self):
        workspace = Path(WORKSPACE)
        dialog = QDialog(self)
        dialog.setWindowTitle(tr("Sauvegarder une ou plusieurs collections internes (dossier Workspace)", self.language))
        dialog.resize(920, 590)
        dialog.setMinimumSize(760, 500)
        layout = QVBoxLayout(dialog)
        heading = QLabel()
        heading.setStyleSheet("font-size: 19px; font-weight: 750;")
        layout.addWidget(heading)
        pages = QStackedWidget()
        layout.addWidget(pages, 1)
        sources = set()

        def make_table():
            table = QTableWidget(0, 2)
            table.setHorizontalHeaderLabels([tr("Collection(s) — cochez les fichiers à copier", self.language), tr("Fichier source", self.language)])
            table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            return table

        def add_base(table, path, checked=False):
            path = Path(path).expanduser().resolve()
            if path in sources:
                return
            try:
                found = CollectionManager(path).inspect_collections()
                if not found:
                    raise ValueError(tr("Aucune collection G-Skol dans ce fichier.", self.language))
            except Exception as exc:
                QMessageBox.warning(dialog, tr("Base non reconnue", self.language), f"{path}\n\n{exc}")
                return
            sources.add(path)
            row = table.rowCount()
            table.insertRow(row)
            name = QTableWidgetItem(", ".join(c["name"] for c in found))
            name.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            name.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
            table.setItem(row, 0, name)
            table.setItem(row, 1, QTableWidgetItem(str(path)))

        def selected(table):
            return [Path(table.item(i, 1).text()) for i in range(table.rowCount())
                    if table.item(i, 0).checkState() == Qt.CheckState.Checked]

        # Écran 1 : uniquement les fichiers du Workspace.
        first = QWidget()
        first_layout = QVBoxLayout(first)
        explanation = QLabel("Cochez les collections du Workspace à sauvegarder. "
                             "Vous pourrez ensuite ajouter des bases situées sur une clé USB, "
                             "un disque externe ou dans un autre dossier.")
        explanation.setWordWrap(True)
        first_layout.addWidget(explanation)
        workspace_table = make_table()
        first_layout.addWidget(workspace_table, 1)
        folder = workspace / "Collections"
        if folder.is_dir():
            for path in sorted(folder.rglob("*.coldb")):
                add_base(workspace_table, path)
        if not workspace_table.rowCount():
            first_layout.addWidget(QLabel("Aucune collection trouvée dans Workspace/Collections."))
        pages.addWidget(first)

        # Écran 2 : uniquement les fichiers extérieurs, ajoutés avec un choix de fichiers.
        second = QWidget()
        second_layout = QVBoxLayout(second)
        explanation = QLabel("Pour ajouter des bases situées hors du Workspace, cliquez sur « Parcourir… » "
                             "en bas de cet écran. Dans l'explorateur, choisissez un ou plusieurs fichiers .coldb "
                             "avec Ctrl ou Maj. Vous pouvez aussi passer cette étape sans rien ajouter.")
        explanation.setWordWrap(True)
        second_layout.addWidget(explanation)
        add = QPushButton("Parcourir…")
        add.setStyleSheet("font-size: 16px; font-weight: 750;")
        add.setMinimumHeight(44)
        external_table = make_table()
        second_layout.addWidget(external_table, 1)
        second_layout.addWidget(add)
        def browse_sources():
            paths, _ = QFileDialog.getOpenFileNames(
                dialog, tr("Choisir un ou plusieurs fichiers .coldb extérieurs", self.language),
                str(workspace.parent), "Collections G-Skol (*.coldb)")
            for path in paths:
                candidate = Path(path).resolve()
                if candidate.is_relative_to(workspace.resolve()):
                    QMessageBox.information(dialog, "Fichier du Workspace",
                                            "Cette base est dans le Workspace : sélectionnez-la à l'étape 1.")
                else:
                    add_base(external_table, candidate, checked=True)
        add.clicked.connect(browse_sources)
        pages.addWidget(second)

        # Écran 3 : destination uniquement ; aucun explorateur de source sur cette page.
        third = QWidget()
        third_layout = QVBoxLayout(third)
        explanation = QLabel("Choisissez maintenant le dossier où placer les copies. "
                             "G-Skol créera dans ce dossier un nouveau sous-dossier daté contenant les .coldb sélectionnés.")
        explanation.setWordWrap(True)
        third_layout.addWidget(explanation)
        summary = QLabel()
        summary.setWordWrap(True)
        third_layout.addWidget(summary)
        third_layout.addWidget(QLabel("Dossier de destination :"))
        row = QHBoxLayout()
        default_backup = workspace / "Sauvegardes"
        default_backup.mkdir(parents=True, exist_ok=True)
        folder_input = QLineEdit(str(default_backup.resolve()))
        row.addWidget(folder_input, 1)
        browse = QPushButton("Choisir le dossier…")
        def browse_destination():
            path = QFileDialog.getExistingDirectory(dialog, "Choisir le dossier où placer les copies", folder_input.text())
            if path:
                folder_input.setText(path)
        browse.clicked.connect(browse_destination)
        row.addWidget(browse)
        third_layout.addLayout(row)
        third_layout.addWidget(QLabel("Nom du nouveau sous-dossier :"))
        name_input = QLineEdit("Collections-" + datetime.now().strftime("%Y-%m-%d-%H%M%S"))
        auto_name = {"value": name_input.text()}
        third_layout.addWidget(name_input)
        preview = QLabel()
        preview.setWordWrap(True)
        def refresh_preview():
            preview.setText(tr("Emplacement final :", self.language) + " " +
                            str(Path(folder_input.text().strip() or ".").expanduser() / name_input.text().strip()))
        folder_input.textChanged.connect(refresh_preview)
        name_input.textChanged.connect(refresh_preview)
        refresh_preview()
        third_layout.addWidget(preview)
        third_layout.addStretch(1)
        pages.addWidget(third)

        buttons = QHBoxLayout()
        back = QPushButton("Précédent")
        next_button = QPushButton("Suivant")
        save = QPushButton("Créer les copies .coldb")
        cancel = QPushButton("Annuler")
        buttons.addWidget(back)
        buttons.addStretch(1)
        buttons.addWidget(next_button)
        buttons.addWidget(save)
        buttons.addWidget(cancel)
        layout.addLayout(buttons)
        cancel.clicked.connect(dialog.reject)
        def refresh():
            index = pages.currentIndex()
            heading.setText((tr("1 / 3 — Collections du Workspace", self.language),
                             tr("2 / 3 — Bases situées sur un autre support", self.language),
                             tr("3 / 3 — Destination de la sauvegarde", self.language))[index])
            back.setEnabled(index > 0)
            next_button.setVisible(index < 2)
            save.setVisible(index == 2)
            chosen_now = selected(workspace_table) + selected(external_table)
            summary.setText(tr("Sélection : {workspace_count} fichier(s) du Workspace et {external_count} fichier(s) extérieurs.", self.language).format(
                workspace_count=len(selected(workspace_table)), external_count=len(selected(external_table))))
            if index == 2 and name_input.text() == auto_name["value"]:
                stamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
                if len(chosen_now) == 1:
                    try:
                        rows = CollectionManager(chosen_now[0]).inspect_collections()
                        cname = str(rows[0].get("name") or chosen_now[0].stem).strip() if rows else chosen_now[0].stem
                    except Exception:
                        cname = chosen_now[0].stem
                    suggested = f"{cname} - {stamp}"
                else:
                    suggested = f"{tr('Sauvegarde de plusieurs collections', self.language)} - {stamp}"
                auto_name["value"] = suggested
                name_input.setText(suggested)
        def move(delta):
            pages.setCurrentIndex(pages.currentIndex() + delta)
            refresh()
        back.clicked.connect(lambda: move(-1))
        next_button.clicked.connect(lambda: move(1))
        save.clicked.connect(dialog.accept)
        translate_widget_tree(dialog, self.language)
        refresh()
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        chosen = selected(workspace_table) + selected(external_table)
        if not chosen:
            QMessageBox.warning(self, "Aucune sélection", "Cochez au moins une collection sur les écrans 1 ou 2.")
            return
        name = name_input.text().strip()
        if not name or name in {".", ".."} or any(c in name for c in '<>:"/\\|?*'):
            QMessageBox.warning(self, "Nom incorrect", "Choisissez un nom de dossier valide.")
            return
        if not folder_input.text().strip():
            QMessageBox.warning(self, "Destination manquante", "Choisissez un dossier de destination.")
            return
        destination = Path(folder_input.text().strip()).expanduser() / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            copies = create_selected_database_backup(chosen, destination)
        except Exception as exc:
            QMessageBox.warning(self, "Sauvegarde impossible", str(exc))
            return
        finally:
            QApplication.restoreOverrideCursor()
        QMessageBox.information(self, tr("Collections sauvegardées", self.language),
                                tr("{count} fichier(s) .coldb créé(s) et vérifié(s) dans :", self.language).format(count=len(copies)) + f"\n{destination.resolve()}\n\n"
                                + "\n".join(p.name for p in copies))

    def _create_backup(self):
        workspace = Path(WORKSPACE)
        try:
            inventory = workspace_backup_inventory(workspace)
        except Exception as exc:
            QMessageBox.warning(self, "Sauvegarde impossible", str(exc))
            return
        outside = []
        for window in QApplication.topLevelWidgets():
            collection = getattr(window, "collection", None)
            database = getattr(window, "_database_path", None)
            if not isinstance(collection, dict) or database is None:
                continue
            try:
                path = Path(database() if callable(database) else database).resolve()
                if not path.is_relative_to(workspace.resolve()):
                    outside.append(f"• {collection.get('name', path.stem)} : {path}")
            except (OSError, TypeError, ValueError):
                continue
        names = [p.name for p in inventory["collections"]]
        description = (tr("Sauvegarde complète de tous les fichiers du Workspace, sauf les anciennes sauvegardes. Chaque sauvegarde reprend l'ensemble : elle n'est pas incrémentielle. Les collections sont des .coldb utilisables individuellement.", self.language) + "\n\n"
                       + tr("Collections incluses ({count}) :", self.language).format(count=len(names)) + "\n"
                       + ("\n".join("• " + name for name in names) if names else tr("Aucune", self.language))
                       + "\n\n" + tr("Collections ouvertes hors du Workspace (exclues) :", self.language) + "\n"
                       + ("\n".join(outside) if outside else tr("Aucune actuellement ouverte. Les collections extérieures fermées ne sont pas recensées.", self.language)))
        dialog = QDialog(self)
        dialog.setWindowTitle(tr("Créer une sauvegarde", self.language))
        dialog.resize(760, 540)
        form = QVBoxLayout(dialog)
        label = QLabel(description)
        label.setWordWrap(True)
        form.addWidget(label, 1)
        form.addWidget(QLabel(tr("Nom du dossier daté :", self.language)))
        name_input = QLineEdit(tr("Sauvegarde complète", self.language) + " - " + datetime.now().strftime("%Y-%m-%d-%H%M%S"))
        form.addWidget(name_input)
        form.addWidget(QLabel("Dossier de destination :"))
        row = QHBoxLayout()
        default_backup = workspace / "Sauvegardes"
        default_backup.mkdir(parents=True, exist_ok=True)
        folder_input = QLineEdit(str(default_backup.resolve()))
        row.addWidget(folder_input, 1)
        browse = QPushButton("Parcourir…")
        def choose_folder():
            selected = QFileDialog.getExistingDirectory(dialog, tr("Choisir le dossier de destination", self.language), folder_input.text())
            if selected:
                folder_input.setText(selected)
                create.setFocus()
        browse.clicked.connect(choose_folder)
        row.addWidget(browse)
        form.addLayout(row)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        create = QPushButton("Créer la sauvegarde complète")
        cancel = QPushButton("Annuler")
        create.clicked.connect(dialog.accept)
        cancel.clicked.connect(dialog.reject)
        buttons.addWidget(create)
        buttons.addWidget(cancel)
        form.addLayout(buttons)
        translate_widget_tree(dialog, self.language)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        name = name_input.text().strip()
        if not name or name in {".", ".."} or any(c in name for c in '<>:"/\\|?*'):
            QMessageBox.warning(self, "Nom incorrect", "Choisissez un nom sans caractère interdit.")
            return
        if not folder_input.text().strip():
            QMessageBox.warning(self, "Destination manquante", "Choisissez un dossier de destination.")
            return
        destination = Path(folder_input.text().strip()).expanduser() / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            manifest = create_native_workspace_backup(workspace, destination, inventory)
        except Exception as exc:
            QMessageBox.warning(self, "Sauvegarde impossible", str(exc))
            return
        finally:
            QApplication.restoreOverrideCursor()
        QMessageBox.information(self, tr("Sauvegarde vérifiée", self.language),
                                tr("Dossier créé :", self.language) + f"\n{destination.resolve()}\n\n"
                                + tr("{collections} collection(s), {files} fichier(s) vérifié(s).", self.language).format(collections=len(manifest['collections']), files=len(manifest['files'])) + "\n"
                                + tr("Fichiers .coldb individuels :", self.language) + f"\n{destination.resolve() / 'Collections'}")

    def _open_manager(self):
        dialog=BackupManagementDialog(self, self.language)
        dialog.exec()

    def _close_all(self):
        top=self.parentWidget(); self.close()
        if isinstance(top,QDialog): top.close()


class ImportExportDialog(QDialog):
    """Premier niveau : Importation, Exportation ou Sauvegarde/Restauration."""
    def __init__(self, parent: QWidget | None = None, language: str = "fr") -> None:
        super().__init__(parent)
        self.language = str(language or "fr")
        self.setWindowTitle(tr("Import / Export / Sauvegarde", self.language))
        self.resize(820, 560); self.setMinimumSize(700, 500); self.setModal(False)
        self._child_windows: list[QDialog]=[]; self._build_ui()
    def _build_ui(self):
        layout=QVBoxLayout(self); layout.setContentsMargins(34,30,34,28); layout.setSpacing(18)
        title=QLabel(tr("Import / Export / Sauvegarde", self.language)); title.setStyleSheet("font-size: 26px; font-weight: 800;"); layout.addWidget(title)
        intro=QLabel(tr("Que voulez-vous faire ? Choisissez d’abord une famille d’opérations. G-Skol vous proposera ensuite les traitements correspondants.", self.language))
        intro.setWordWrap(True); intro.setStyleSheet("font-size: 14px;"); layout.addWidget(intro)
        style=("QPushButton { text-align: left; padding: 18px 20px; font-size: 18px; font-weight: 750; }"
               "QPushButton:hover { background: rgba(155,73,57,0.10); }")
        for label,slot,tip in [
            (tr("Importation", self.language), self._open_import, tr("Créer ou enrichir une collection à partir de sources extérieures.", self.language)),
            (tr("Exportation", self.language), self._open_export, tr("Exporter une collection ou des modèles G-Skol.", self.language)),
            (tr("Sauvegarde / Restauration", self.language), self._open_backup, tr("Sauvegarder l’environnement G-Skol ou restaurer une sauvegarde.", self.language)),
        ]:
            b=QPushButton(label); b.setMinimumHeight(92); b.setStyleSheet(style); b.setToolTip(tip); b.clicked.connect(slot); layout.addWidget(b)
        layout.addStretch(1); row=QHBoxLayout(); row.addStretch(1); close=QPushButton(tr("Fermer", self.language)); close.clicked.connect(self.close); row.addWidget(close); layout.addLayout(row)
    def _track_child(self, dialog):
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True); self._child_windows.append(dialog)
        dialog.destroyed.connect(lambda *_args,d=dialog:self._forget_child(d)); dialog.show(); dialog.raise_(); dialog.activateWindow()
    def _forget_child(self, dialog):
        try:self._child_windows.remove(dialog)
        except ValueError:pass
    def _open_import(self): self._track_child(ImportMenuDialog(self, self.language))
    def _open_export(self): self._track_child(ExportDialog(self))
    def _open_backup(self): self._track_child(BackupRestoreDialog(self, self.language))
