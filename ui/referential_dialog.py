#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from core.collection_folders import collection_display_name
from core.i18n import tr, display_native_value

import csv
import io
import sqlite3
import unicodedata
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QProgressDialog,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from core.referential_manager import ReferentialManager
from core.model_manager import ModelManager
from ui.collection_theme import collection_theme


def _simple_key(text: str) -> str:
    raw = unicodedata.normalize("NFKD", str(text or ""))
    raw = "".join(ch for ch in raw if not unicodedata.combining(ch))
    return "".join(ch for ch in raw.casefold() if ch.isalnum())


def _xlsx_target_path(target: str) -> str:
    """Normalise une cible de relation XLSX vers son chemin ZIP réel."""
    clean = str(target or "").replace("\\", "/").lstrip("/")
    # Excel/LibreOffice peuvent écrire soit worksheets/sheet1.xml, soit
    # /xl/worksheets/sheet1.xml, soit xl/worksheets/sheet1.xml.
    if clean.startswith("xl/"):
        return clean
    return "xl/" + clean


def _read_xlsx_sheets(path: Path) -> list[tuple[str, list[str], list[list[str]]]]:
    """Lit toutes les feuilles d'un XLSX sans dépendance externe."""
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    rel_ns = {"r": "http://schemas.openxmlformats.org/package/2006/relationships"}
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        shared: list[str] = []
        if "xl/sharedStrings.xml" in names:
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in root.findall("m:si", ns):
                shared.append("".join(t.text or "" for t in si.iterfind(".//m:t", ns)))

        wb = ET.fromstring(z.read("xl/workbook.xml"))
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        rel_targets = {
            str(rel.attrib.get("Id") or ""): _xlsx_target_path(str(rel.attrib.get("Target") or ""))
            for rel in rels.findall("r:Relationship", rel_ns)
        }

        result: list[tuple[str, list[str], list[list[str]]]] = []
        for index, sheet in enumerate(wb.findall(".//m:sheets/m:sheet", ns), start=1):
            sheet_label = str(sheet.attrib.get("name") or f"Feuille {index}")
            rid = str(sheet.attrib.get(
                "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id", ""
            ))
            sheet_name = rel_targets.get(rid, "")
            if not sheet_name or sheet_name not in names:
                continue
            root = ET.fromstring(z.read(sheet_name))
            data: list[list[str]] = []
            for row in root.findall(".//m:sheetData/m:row", ns):
                values: list[str] = []
                last_col = 0
                for cell in row.findall("m:c", ns):
                    ref = cell.attrib.get("r", "A1")
                    letters = "".join(ch for ch in ref if ch.isalpha()).upper()
                    col = 0
                    for ch in letters:
                        col = col * 26 + (ord(ch) - 64)
                    while last_col + 1 < col:
                        values.append("")
                        last_col += 1
                    ctype = cell.attrib.get("t", "")
                    v = cell.find("m:v", ns)
                    value = "" if v is None else (v.text or "")
                    if ctype == "s" and value.isdigit():
                        idx = int(value)
                        value = shared[idx] if 0 <= idx < len(shared) else value
                    elif ctype == "inlineStr":
                        value = "".join(t.text or "" for t in cell.iterfind(".//m:t", ns))
                    values.append(value)
                    last_col = col
                if values:
                    data.append(values)

            if not data:
                result.append((sheet_label, [], []))
                continue
            width = max(len(r) for r in data)
            data = [r + [""] * (width - len(r)) for r in data]
            header = [str(x).strip() or f"Colonne {i+1}" for i, x in enumerate(data[0])]
            rows = [[str(x).strip() for x in row] for row in data[1:]]
            result.append((sheet_label, header, rows))
        return result


def _read_xlsx(path: Path) -> tuple[list[str], list[list[str]]]:
    """Compatibilité : renvoie la première feuille exploitable."""
    sheets = _read_xlsx_sheets(path)
    for _name, headers, rows in sheets:
        if headers:
            return headers, rows
    return [], []

def _read_tabular_file(filename: str) -> tuple[list[str], list[list[str]]]:
    path = Path(filename)
    if path.suffix.lower() == ".xlsx":
        return _read_xlsx(path)

    raw = path.read_bytes()
    text = None
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            pass
    if text is None:
        text = raw.decode("utf-8", errors="replace")

    sample = text[:8192]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\\t|")
    except csv.Error:
        dialect = csv.excel
        dialect.delimiter = ";"
    rows = list(csv.reader(io.StringIO(text), dialect))
    rows = [[str(x).strip() for x in row] for row in rows if any(str(x).strip() for x in row)]
    if not rows:
        return [], []
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    header = [x or f"Colonne {i+1}" for i, x in enumerate(rows[0])]
    return header, rows[1:]


class NoWheelComboBox(QComboBox):
    """Liste déroulante volontairement insensible à la roulette."""

    def wheelEvent(self, event) -> None:  # noqa: N802
        event.ignore()



class ReferentialMappingDialog(QDialog):
    def __init__(self, headers: list[str], field_choices: list[tuple[str, str]], parent=None, preferred_master_key: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Importer un référentiel complet")
        self.resize(720, 520)
        layout = QVBoxLayout(self)
        intro = QLabel(
            "Associez les colonnes du fichier aux champs MM3, puis choisissez le champ Maître. "
            "Les colonnes laissées sur « Ignorer » ne seront pas importées."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        master_row = QHBoxLayout()
        master_row.addWidget(QLabel("Colonne Maître :"))
        self.master_combo = NoWheelComboBox()
        for idx, header in enumerate(headers):
            self.master_combo.addItem(header, idx)
        master_row.addWidget(self.master_combo, 1)
        layout.addLayout(master_row)

        self.table = QTableWidget(len(headers), 2)
        self.table.setHorizontalHeaderLabels(["Colonne du fichier", "Champ MM3"])
        self.table.setStyleSheet(
            "QTableWidget { font-size: 12px; } "
            "QHeaderView::section { font-size: 12px; padding: 4px; } "
            "QComboBox { font-size: 12px; padding: 2px 6px; min-height: 22px; }"
        )
        self.table.verticalHeader().setDefaultSectionSize(30)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.mapping_combos = []
        by_name = {_simple_key(label): key for label, key in field_choices}
        for row, header in enumerate(headers):
            item = QTableWidgetItem(header)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 0, item)
            combo = NoWheelComboBox()
            combo.addItem("— Ignorer —", "")
            for label, key in field_choices:
                combo.addItem(label, key)
            guess = by_name.get(_simple_key(header))
            if guess:
                idx = combo.findData(guess)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
            self.table.setCellWidget(row, 1, combo)
            self.mapping_combos.append(combo)

        # La colonne Maître doit être réellement associée à un champ MM3.
        # Quand le libellé du fichier diffère du libellé personnalisé MM3
        # (ex. « Nom » dans un ancien IMA, « Espèce » dans MM3), on associe
        # automatiquement la colonne Maître au référentiel actuellement choisi.
        self.preferred_master_key = str(preferred_master_key or "")
        self.master_combo.currentIndexChanged.connect(self._ensure_master_mapping)
        self._ensure_master_mapping()
        layout.addWidget(self.table, 1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        ok = QPushButton("Importer")
        ok.setObjectName("primaryButton")
        cancel = QPushButton("Annuler")
        ok.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        buttons.addWidget(ok)
        buttons.addWidget(cancel)
        layout.addLayout(buttons)

    def _ensure_master_mapping(self, *_args) -> None:
        if not self.preferred_master_key:
            return
        try:
            row = int(self.master_combo.currentData())
        except (TypeError, ValueError):
            return
        if row < 0 or row >= len(self.mapping_combos):
            return
        combo = self.mapping_combos[row]
        if str(combo.currentData() or ""):
            return
        idx = combo.findData(self.preferred_master_key)
        if idx >= 0:
            combo.setCurrentIndex(idx)

    def mapping(self) -> tuple[int, dict[int, str]]:
        return (
            int(self.master_combo.currentData()),
            {
                idx: str(combo.currentData() or "")
                for idx, combo in enumerate(self.mapping_combos)
                if str(combo.currentData() or "")
            },
        )


class ReferentialDialog(QDialog):
    """Gestion générique des premiers référentiels MM3."""

    def __init__(self, startup, collection: dict, parent=None) -> None:
        super().__init__(parent)
        self.startup = startup
        self.collection = collection
        self.language = getattr(parent, "language", "fr")
        self.manager = ReferentialManager(startup.database.database_path)
        self.setWindowTitle(f"{tr('Référentiels', self.language)} — {collection_display_name(collection, self.language)}")
        self.resize(720, 710)
        self.setMinimumSize(640, 590)
        self._definitions: list[dict] = []
        self._undo_stack: list[dict] = []
        self._redo_stack: list[dict] = []
        self._history_limit = 20
        self._history_replaying = False
        self._build_ui()
        self._apply_style()
        self.reload_definitions()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(14)

        title = QLabel(tr("Gestion des référentiels", self.language))
        title.setObjectName("dialogTitle")
        layout.addWidget(title)

        selector_row = QHBoxLayout()
        selector_row.addWidget(QLabel(tr("Référentiel :", self.language)))
        self.definition_combo = QComboBox()
        self.definition_combo.currentIndexChanged.connect(self.reload_values)
        self.definition_combo.activated.connect(self._definition_activated)
        selector_row.addWidget(self.definition_combo, 1)
        self.definition_order_combo = QComboBox()
        self.definition_order_combo.addItem("A → Z", "asc")
        self.definition_order_combo.addItem("Z → A", "desc")
        self.definition_order_combo.setToolTip(tr("Trier la liste des référentiels", self.language))
        self.definition_order_combo.currentIndexChanged.connect(self.reload_definitions)
        selector_row.addWidget(self.definition_order_combo)
        layout.addLayout(selector_row)

        order_row = QHBoxLayout()
        order_row.addWidget(QLabel(tr("Ordre des valeurs :", self.language)))
        self.order_combo = QComboBox()
        self.order_combo.addItem(tr("Croissant (A → Z)", self.language), "asc")
        self.order_combo.addItem(tr("Décroissant (Z → A)", self.language), "desc")
        self.order_combo.addItem(tr("Personnalisé", self.language), "custom")
        self.order_combo.currentIndexChanged.connect(self.change_sort_mode)
        self.order_combo.activated.connect(self.change_sort_mode)
        order_row.addWidget(self.order_combo)
        order_row.addStretch(1)
        layout.addLayout(order_row)

        self.explanation = QLabel()
        self.explanation.setWordWrap(True)
        self.explanation.setObjectName("explanation")
        layout.addWidget(self.explanation)

        self.list_widget = QListWidget()
        self.list_widget.setAlternatingRowColors(True)
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._show_value_context_menu)
        self.list_widget.itemDoubleClicked.connect(lambda _item: self.edit_selected())
        self.list_widget.itemSelectionChanged.connect(self._update_buttons)
        layout.addWidget(self.list_widget, 1)

        add_row = QHBoxLayout()
        self.value_edit = QLineEdit()
        self.value_edit.setPlaceholderText(tr("Nouvelle valeur", self.language))
        self.value_edit.textEdited.connect(self._normalize_while_typing)
        self.value_edit.returnPressed.connect(self._submit_value_from_keyboard)
        add_btn = QPushButton(tr("Ajouter", self.language))
        add_btn.setObjectName("primaryButton")
        add_btn.clicked.connect(self.add_value)
        add_row.addWidget(self.value_edit, 1)
        add_row.addWidget(add_btn)
        layout.addLayout(add_row)

        actions_bar = QFrame()
        actions_bar.setMinimumHeight(104)
        actions_bar.setMaximumHeight(104)
        actions = QHBoxLayout(actions_bar)
        actions.setContentsMargins(0, 7, 0, 7)
        actions.setSpacing(8)

        self.undo_btn = QPushButton(tr("Défaire", self.language))
        self.redo_btn = QPushButton(tr("Refaire", self.language))
        undo_redo_style = (
            "QPushButton { background:#ef9a9a; border:1px solid #cf6f6f; "
            "border-radius:5px; padding:5px 12px; color:#222; } "
            "QPushButton:disabled { background:#f8dada; border-color:#e7bcbc; color:#8a7777; }"
        )
        self.undo_btn.setStyleSheet(undo_redo_style)
        self.redo_btn.setStyleSheet(undo_redo_style)
        self.undo_btn.setToolTip(tr("Annuler la dernière modification du référentiel", self.language))
        self.redo_btn.setToolTip(tr("Rétablir la dernière modification annulée", self.language))
        self.undo_btn.clicked.connect(self.undo_last_action)
        self.redo_btn.clicked.connect(self.redo_last_action)
        self.undo_btn.setFixedHeight(90)
        self.redo_btn.setFixedHeight(90)

        self.import_file_btn = QPushButton(tr("Ajouter des\nvaleurs…", self.language))
        self.import_file_btn.setFixedHeight(90)
        self.import_file_btn.clicked.connect(self.import_file_values)
        self.create_ref_btn = QPushButton(tr("Créer un\nréférentiel…", self.language))
        self.create_ref_btn.setFixedHeight(90)
        self.create_ref_btn.setToolTip(tr("Créer un nouveau champ Liste dans la palette et importer simultanément son référentiel", self.language))
        self.create_ref_btn.clicked.connect(self._create_new_referential_from_button)
        self.remove_btn = QPushButton(tr("Retirer de\nla liste", self.language))
        self.remove_btn.setFixedHeight(90)
        self.remove_btn.clicked.connect(self.remove_selected)

        for button in (
            self.undo_btn,
            self.redo_btn,
            self.import_file_btn,
            self.create_ref_btn,
            self.remove_btn,
        ):
            button.setMinimumWidth(88)
        close_btn = QPushButton(tr("Fermer", self.language))
        close_btn.setFixedHeight(90)
        close_btn.clicked.connect(self.accept)
        actions.addWidget(self.undo_btn)
        actions.addWidget(self.redo_btn)
        actions.addWidget(self.import_file_btn)
        actions.addWidget(self.create_ref_btn)
        actions.addWidget(self.remove_btn)
        actions.addStretch(1)
        actions.addWidget(close_btn)
        layout.addWidget(actions_bar)
        self._update_buttons()

    def _apply_style(self) -> None:
        theme = collection_theme(self.startup.database.database_path, self.collection)
        self.setStyleSheet(
            f"""
            QDialog {{ background: {theme['gradient']}; color: #24332B; }}
            #dialogTitle {{ font-size: 23px; font-weight: 700; }}
            #explanation {{ color: #52645B; font-size: 14px; }}
            QListWidget, QLineEdit, QComboBox {{
                background: white; color: #24332B; border: 1px solid {theme['border']};
                border-radius: 7px; padding: 8px; font-size: 15px;
            }}
            QPushButton {{
                background: white; color: #24332B; border: 1px solid {theme['border']};
                border-radius: 7px; padding: 10px 13px;
            }}
            QPushButton:hover {{ background: {theme['hover']}; }}
            QPushButton:disabled {{ color: #9AA59F; background: #DCE4E0; }}
            #primaryButton {{ background: #496C5B; color: white; border-color: #496C5B; }}
            #primaryButton:hover {{ background: #3C5B4C; }}
            """
        )

    def _history_snapshot(self) -> dict:
        """Capture l'état des référentiels et liaisons de cette collection."""
        cid = int(self.collection["id"])
        db_path = self.startup.database.database_path
        snapshot: dict[str, object] = {}
        with sqlite3.connect(db_path) as connection:
            connection.row_factory = sqlite3.Row
            defs = connection.execute(
                "SELECT id, sort_mode FROM referential_definitions WHERE collection_id=? ORDER BY id",
                (cid,),
            ).fetchall()
            snapshot["definition_modes"] = [(int(r["id"]), str(r["sort_mode"] or "custom")) for r in defs]
            snapshot["referential_values"] = [
                tuple(r) for r in connection.execute(
                    """SELECT rv.id, rv.definition_id, rv.value, rv.sort_order, rv.is_active, rv.created_at, rv.updated_at
                       FROM referential_values rv
                       JOIN referential_definitions rd ON rd.id=rv.definition_id
                       WHERE rd.collection_id=? ORDER BY rv.id""",
                    (cid,),
                ).fetchall()
            ]
            for table, order_by in (
                ("collection_field_masters", "field_key"),
                ("collection_field_links", "linked_key"),
                ("collection_reference_data", "master_key, master_value, linked_key"),
                ("referential_value_exclusions", "code, value"),
            ):
                exists = connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
                ).fetchone()
                if not exists:
                    snapshot[table] = []
                    continue
                cols = [str(r[1]) for r in connection.execute(f"PRAGMA table_info({table})").fetchall()]
                rows = connection.execute(
                    f"SELECT * FROM {table} WHERE collection_id=? ORDER BY {order_by}", (cid,)
                ).fetchall()
                snapshot[table] = {"columns": cols, "rows": [tuple(r) for r in rows]}
        return snapshot

    def _restore_history_snapshot(self, snapshot: dict) -> None:
        cid = int(self.collection["id"])
        db_path = self.startup.database.database_path
        with sqlite3.connect(db_path) as connection:
            connection.execute("PRAGMA foreign_keys=ON")
            definition_ids = [
                int(r[0]) for r in connection.execute(
                    "SELECT id FROM referential_definitions WHERE collection_id=?", (cid,)
                ).fetchall()
            ]
            if definition_ids:
                placeholders = ",".join("?" for _ in definition_ids)
                connection.execute(
                    f"DELETE FROM referential_values WHERE definition_id IN ({placeholders})", definition_ids
                )
            rows = list(snapshot.get("referential_values") or [])
            if rows:
                connection.executemany(
                    """INSERT INTO referential_values(
                           id, definition_id, value, sort_order, is_active, created_at, updated_at
                       ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    rows,
                )
            for definition_id, mode in list(snapshot.get("definition_modes") or []):
                connection.execute(
                    "UPDATE referential_definitions SET sort_mode=? WHERE id=? AND collection_id=?",
                    (mode, int(definition_id), cid),
                )
            for table in (
                "collection_field_links", "collection_field_masters",
                "collection_reference_data", "referential_value_exclusions"
            ):
                exists = connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
                ).fetchone()
                if not exists:
                    continue
                connection.execute(f"DELETE FROM {table} WHERE collection_id=?", (cid,))
                data = snapshot.get(table) or {}
                if isinstance(data, dict):
                    cols = list(data.get("columns") or [])
                    table_rows = list(data.get("rows") or [])
                    if cols and table_rows:
                        placeholders = ",".join("?" for _ in cols)
                        connection.executemany(
                            f"INSERT INTO {table} ({','.join(cols)}) VALUES ({placeholders})",
                            table_rows,
                        )
            connection.commit()
        self.manager = ReferentialManager(db_path)
        self.reload_definitions()

    def _history_begin(self) -> dict | None:
        if self._history_replaying:
            return None
        return self._history_snapshot()

    def _history_commit(self, before: dict | None, label: str) -> None:
        if before is None or self._history_replaying:
            return
        after = self._history_snapshot()
        if before == after:
            return
        self._undo_stack.append({"label": label, "before": before, "after": after})
        if len(self._undo_stack) > self._history_limit:
            self._undo_stack.pop(0)
        self._redo_stack.clear()
        self._update_buttons()

    def undo_last_action(self) -> None:
        if not self._undo_stack:
            return
        action = self._undo_stack.pop()
        self._history_replaying = True
        try:
            self._restore_history_snapshot(action["before"])
        finally:
            self._history_replaying = False
        self._redo_stack.append(action)
        self._update_buttons()

    def redo_last_action(self) -> None:
        if not self._redo_stack:
            return
        action = self._redo_stack.pop()
        self._history_replaying = True
        try:
            self._restore_history_snapshot(action["after"])
        finally:
            self._history_replaying = False
        self._undo_stack.append(action)
        self._update_buttons()

    def reload_definitions(self, *_args) -> None:
        current_code = ""
        current = self._current_definition() if hasattr(self, "definition_combo") else None
        if current:
            current_code = str(current.get("code") or "")

        self._definitions = self.manager.list_definitions(int(self.collection["id"]))

        # Les référentiels doivent afficher le libellé réellement utilisé
        # par le modèle de la collection (ex. Nom renommé en Espèce),
        # et non le libellé historique stocké dans la définition technique.
        try:
            from core.field_catalog import FIELDS
            from core.model_manager import ModelManager

            model_manager = ModelManager(self.startup.database.database_path)
            cid = int(self.collection["id"])
            custom_labels = model_manager.custom_labels(cid)
            custom_map = model_manager.custom_field_map(cid)
            visible_fields = model_manager.visible_fields(cid)

            # Ne présenter que les référentiels réellement utilisés par les
            # champs visibles de cette collection. Les définitions techniques
            # héritées mais inutilisées ne doivent plus créer de doublons dans
            # l'Atelier Référentiels.
            active_codes: set[str] = set()
            for spec in FIELDS:
                if str(spec.key) in visible_fields and getattr(spec, "referential", None):
                    active_codes.add(str(spec.referential))
            for key, item in custom_map.items():
                if str(key) not in visible_fields:
                    continue
                ref = str(item.get("referential_code") or "")
                if ref:
                    active_codes.add(ref)

            self._definitions = [
                definition for definition in self._definitions
                if str(definition.get("code") or "") in active_codes
            ]

            # Référentiel -> champ principal. Quand le code du référentiel
            # correspond directement à une clé de champ, on le privilégie.
            by_referential: dict[str, str] = {}
            for spec in FIELDS:
                if not spec.referential:
                    continue
                ref = str(spec.referential)
                if ref not in by_referential or spec.key == ref:
                    by_referential[ref] = str(spec.key)

            for key, item in custom_map.items():
                ref = str(item.get("referential_code") or "")
                if ref:
                    by_referential[ref] = str(key)

            for definition in self._definitions:
                code = str(definition.get("code") or "")
                field_key = by_referential.get(code)
                if not field_key:
                    continue
                if field_key in custom_map:
                    visible_label = str(custom_map[field_key].get("label") or definition["label"])
                else:
                    visible_label = str(custom_labels.get(field_key) or definition["label"])
                definition["label"] = visible_label
        except Exception:
            # En cas de modèle ancien ou incomplet, on conserve simplement
            # le libellé historique du référentiel.
            pass

        direction = (
            str(self.definition_order_combo.currentData() or "asc")
            if hasattr(self, "definition_order_combo")
            else "asc"
        )
        self._definitions.sort(
            key=lambda definition: str(definition.get("label") or "").casefold(),
            reverse=(direction == "desc"),
        )

        self.definition_combo.blockSignals(True)
        self.definition_combo.clear()
        # 26.50 — accès volontairement doublé : la première ligne de la liste
        # déclenche exactement la même création que le bouton dédié.
        self.definition_combo.addItem(tr("--- Créer un référentiel ---", self.language), "__create_referential__")
        selected_index = -1
        for index, definition in enumerate(self._definitions, start=1):
            self.definition_combo.addItem(str(definition["label"]), definition)
            if current_code and str(definition.get("code") or "") == current_code:
                selected_index = index
        if selected_index >= 0:
            self.definition_combo.setCurrentIndex(selected_index)
        self.definition_combo.blockSignals(False)
        self.reload_values()

    def _current_definition(self) -> dict | None:
        data = self.definition_combo.currentData()
        return dict(data) if isinstance(data, dict) else None

    def _definition_activated(self, _index: int) -> None:
        if self.definition_combo.currentData() != "__create_referential__":
            return
        self._show_new_referential_state()
        self.create_new_referential()

    def _show_new_referential_state(self) -> None:
        """Vide clairement l'ancien référentiel avant une création."""
        self.list_widget.clear()
        self.explanation.setText(
            "Création d’un nouveau référentiel : aucun référentiel existant ne sera modifié."
        )
        self.value_edit.clear()
        self.value_edit.setPlaceholderText("Nouveau référentiel à créer")

    def _raw_value(self, item) -> str:
        """Use the canonical stored value for every database operation."""
        raw = item.data(Qt.ItemDataRole.UserRole)
        return str(raw) if raw is not None else item.text()

    def _display_sort_key(self, value: str) -> tuple[str, str]:
        """Sort by the localized label without changing the canonical value."""
        label = str(display_native_value(str(value), self.language))
        # Ignore diacritics for predictable alphabetical ordering in FR/EN/DE.
        # German ß is normalized by casefold() to ss.
        folded = unicodedata.normalize("NFKD", label.casefold())
        primary = "".join(ch for ch in folded if not unicodedata.combining(ch))
        return primary, label.casefold()

    def _show_values(self, values) -> None:
        self.list_widget.clear()
        for raw in values:
            raw = str(raw)
            item = QListWidgetItem(display_native_value(raw, self.language))
            item.setData(Qt.ItemDataRole.UserRole, raw)
            self.list_widget.addItem(item)

    def _select_raw_value(self, value: str) -> None:
        for index in range(self.list_widget.count()):
            item = self.list_widget.item(index)
            if self._raw_value(item) == value:
                self.list_widget.setCurrentItem(item)
                break

    def reload_values(self, *_args) -> None:
        definition = self._current_definition()
        if definition is None:
            self.list_widget.clear()
            return
        code = str(definition["code"])
        label = str(definition["label"])
        mode = self.manager.get_sort_mode(int(self.collection["id"]), code)
        self.order_combo.blockSignals(True)
        mode_index = self.order_combo.findData(mode)
        self.order_combo.setCurrentIndex(mode_index if mode_index >= 0 else 2)
        self.order_combo.blockSignals(False)

        values = self.manager.list_values(int(self.collection["id"]), code)
        if mode in ("asc", "desc"):
            values = sorted(
                values,
                key=self._display_sort_key,
                reverse=(mode == "desc"),
            )
        self._show_values(values)
        if code == "mineral_name":
            self.explanation.setText(
                "Les noms proposés dans les fiches sont classés automatiquement par ordre alphabétique. "
                "Une valeur retirée reste présente dans les fiches qui l'utilisent déjà."
            )
            self.value_edit.setPlaceholderText("Nouvelle valeur (mise en majuscules automatiquement)")
        elif code == "mineral_class":
            self.explanation.setText(
                "Les classes proposées dans les fiches sont classées automatiquement par ordre alphabétique. "
                "Une valeur retirée reste présente dans les fiches qui l'utilisent déjà."
            )
            self.value_edit.setPlaceholderText("Nouvelle classe")
        elif code in ("crystal_system", "site_name", "department", "region", "country", "box_type", "category", "contact", "specimen_shape", "specimen_color"):
            self.explanation.setText(
                f"Les valeurs du référentiel « {label} » sont classées automatiquement par ordre alphabétique. "
                "Une valeur retirée reste présente dans les fiches qui l'utilisent déjà."
            )
            self.value_edit.setPlaceholderText(tr("Nouvelle valeur", self.language))
        else:
            self.explanation.setText(
                f"Les valeurs du référentiel « {label} » sont proposées dans les fiches. "
                "Les nouvelles valeurs sont ajoutées à la fin de la liste."
            )
            self.value_edit.setPlaceholderText(tr("Nouvelle valeur", self.language))

        mode_label = {
            "asc": tr("ordre croissant", self.language),
            "desc": tr("ordre décroissant", self.language),
            "custom": tr("ordre personnalisé", self.language),
        }.get(mode, tr("ordre personnalisé", self.language))
        if str(self.language).lower().startswith("en"):
            mode_label = {"asc": "ascending order", "desc": "descending order", "custom": "custom order"}.get(mode, "custom order")
        description = tr("Référentiel « {label} » — {mode_label}. Une valeur retirée reste présente dans les fiches qui l'utilisent déjà.", self.language)
        if description.startswith("Référentiel «") and str(self.language).lower().startswith("en"):
            description = "Reference list ‘{label}’ — {mode_label}. A removed value remains in records where it is already used."
        self.explanation.setText(description.format(label=label, mode_label=mode_label))
        self._update_buttons()

    def change_sort_mode(self, *_args) -> None:
        definition = self._current_definition()
        if definition is None:
            return

        before_history = self._history_begin()
        collection_id = int(self.collection["id"])
        code = str(definition["code"])
        mode = str(self.order_combo.currentData() or "custom")

        current_values = [
            self._raw_value(self.list_widget.item(index))
            for index in range(self.list_widget.count())
        ]

        if mode == "custom":
            self.manager.set_custom_order(collection_id, code, current_values)
            values = current_values
        else:
            self.manager.set_sort_mode(collection_id, code, mode)
            values = sorted(
                current_values,
                key=self._display_sort_key,
                reverse=(mode == "desc"),
            )

        self._show_values(values)

        label = str(definition["label"])
        mode_label = {
            "asc": tr("ordre croissant", self.language),
            "desc": tr("ordre décroissant", self.language),
            "custom": tr("ordre personnalisé", self.language),
        }.get(mode, tr("ordre personnalisé", self.language))
        if str(self.language).lower().startswith("en"):
            mode_label = {"asc": "ascending order", "desc": "descending order", "custom": "custom order"}.get(mode, "custom order")
        description = tr("Référentiel « {label} » — {mode_label}. Une valeur retirée reste présente dans les fiches qui l'utilisent déjà.", self.language)
        if description.startswith("Référentiel «") and str(self.language).lower().startswith("en"):
            description = "Reference list ‘{label}’ — {mode_label}. A removed value remains in records where it is already used."
        self.explanation.setText(description.format(label=label, mode_label=mode_label))
        self._history_commit(before_history, "Ordre des valeurs")
        self._update_buttons()

    def move_selected(self, delta: int) -> None:
        definition = self._current_definition()
        item = self.list_widget.currentItem()
        if definition is None or item is None:
            return
        if self.manager.get_sort_mode(
            int(self.collection["id"]), str(definition["code"])
        ) != "custom":
            return
        value = self._raw_value(item)
        self.manager.move_value(
            int(self.collection["id"]), str(definition["code"]), value, delta
        )
        self.reload_values()
        self._select_raw_value(value)

    def _normalize_while_typing(self, text: str) -> None:
        definition = self._current_definition()
        if definition is None or definition.get("code") != "mineral_name":
            return
        upper = text.upper()
        if upper != text:
            cursor = self.value_edit.cursorPosition()
            self.value_edit.blockSignals(True)
            self.value_edit.setText(upper)
            self.value_edit.setCursorPosition(min(cursor, len(upper)))
            self.value_edit.blockSignals(False)

    def add_value(self) -> None:
        definition = self._current_definition()
        before_history = self._history_begin()
        if definition is None:
            return
        try:
            normalized = self.manager.add_value(
                int(self.collection["id"]), str(definition["code"]), self.value_edit.text()
            )
        except Exception as exc:
            QMessageBox.warning(self, "Ajout impossible", str(exc))
            return
        self.value_edit.clear()
        self.reload_values()
        self._select_raw_value(normalized)
        self._history_commit(before_history, "Ajout d'une valeur")

    def _show_value_context_menu(self, pos) -> None:
        items = self.list_widget.selectedItems()
        if not items:
            item = self.list_widget.itemAt(pos)
            if item is None:
                return
            self.list_widget.setCurrentItem(item)
            items = [item]

        menu = QMenu(self)
        if len(items) == 1:
            modify_action = menu.addAction("Modifier…")
            modify_action.triggered.connect(self.edit_selected)
        remove_action = menu.addAction(
            "Retirer de la liste" if len(items) == 1
            else f"Retirer les {len(items)} valeurs de la liste"
        )
        remove_action.triggered.connect(self.remove_selected)
        menu.exec(self.list_widget.mapToGlobal(pos))

    def _submit_value_from_keyboard(self) -> None:
        """Entrée modifie la valeur sélectionnée ; sans sélection, elle ajoute."""
        items = self.list_widget.selectedItems()
        entered = self.value_edit.text().strip()
        if len(items) == 1 and entered:
            current = self._raw_value(items[0])
            definition = self._current_definition()
            if definition is not None:
                normalized = self.manager.normalize(entered, str(definition["code"]))
                if normalized and normalized.casefold() != current.casefold():
                    self._rename_value(current, entered)
                    return
        self.add_value()

    def _rename_value(self, old_value: str, new_value: str) -> None:
        definition = self._current_definition()
        before_history = self._history_begin()
        if definition is None:
            return
        try:
            normalized = self.manager.rename_value(
                int(self.collection["id"]),
                str(definition["code"]),
                old_value,
                new_value,
            )
        except Exception as exc:
            QMessageBox.warning(self, "Modification impossible", str(exc))
            return

        self.value_edit.clear()
        self.reload_values()
        self._select_raw_value(normalized)
        self._history_commit(before_history, "Modification d'une valeur")

    def edit_selected(self) -> None:
        items = self.list_widget.selectedItems()
        if len(items) != 1:
            return
        old_value = self._raw_value(items[0])

        dialog = QInputDialog(self)
        dialog.setWindowTitle("Modifier une valeur")
        dialog.setLabelText("Nouvelle valeur :")
        dialog.setTextEchoMode(QLineEdit.EchoMode.Normal)
        dialog.setTextValue(old_value)
        dialog.setOkButtonText("OK")
        dialog.setCancelButtonText("Annuler")

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._rename_value(old_value, dialog.textValue())

    def remove_selected(self) -> None:
        definition = self._current_definition()
        items = self.list_widget.selectedItems()
        if definition is None or not items:
            return

        values = [self._raw_value(item) for item in items]
        code = str(definition["code"])
        values = [v for v in values if not (code == "record_state" and v.casefold() in {"ok", "libre"})]
        if not values:
            return
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        if len(values) == 1:
            box.setWindowTitle("Retirer cette valeur")
            box.setText(f"Retirer « {values[0]} » des propositions ?")
        else:
            box.setWindowTitle("Retirer plusieurs valeurs")
            box.setText(f"Retirer les {len(values)} valeurs sélectionnées des propositions ?")
        box.setInformativeText(
            "Les fiches qui utilisent déjà ces valeurs ne seront pas modifiées."
        )
        yes_button = box.addButton("OUI", QMessageBox.ButtonRole.YesRole)
        no_button = box.addButton("NON", QMessageBox.ButtonRole.NoRole)
        box.setDefaultButton(no_button)
        box.exec()
        if box.clickedButton() is not yes_button:
            return

        before_history = self._history_begin()
        collection_id = int(self.collection["id"])
        code = str(definition["code"])
        self.manager.deactivate_values(collection_id, code, values)

        # Si le référentiel est un champ Maître, retirer aussi ses anciennes
        # lignes canoniques Maître/Relié. Les fiches historiques conservent
        # leurs valeurs, mais la proposition supprimée ne peut plus renaître
        # depuis collection_reference_data.
        try:
            model_manager = ModelManager(self.startup.database.database_path)
            if code in model_manager.field_masters(collection_id):
                model_manager.remove_reference_master_values(collection_id, code, values)
        except Exception:
            pass

        self.reload_values()
        self._history_commit(before_history, "Retrait de valeur(s)")


    def _choose_import_file(self) -> str:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            tr("Choisir les données à importer", self.language),
            "",
            "Données (*.csv *.txt *.tsv *.xlsx *.mdb *.accdb);;Access (*.mdb *.accdb);;Excel (*.xlsx);;CSV / Texte (*.csv *.txt *.tsv);;Tous les fichiers (*)",
        )
        return filename

    def _create_new_referential_from_button(self) -> None:
        self.definition_combo.blockSignals(True)
        try:
            self.definition_combo.setCurrentIndex(0)
        finally:
            self.definition_combo.blockSignals(False)
        self._show_new_referential_state()
        self.create_new_referential()

    @staticmethod
    def _referential_candidate_name(name: str) -> bool:
        """Écarte les colonnes manifestement incompatibles avec un référentiel simple."""
        key = _simple_key(name)
        forbidden = (
            "numero", "photo", "image", "date", "prix", "cout", "montant",
            "description", "commentaire", "remarque", "note", "lien", "url",
            "quantite", "nombre", "nbre", "poids", "longueur", "largeur",
            "epaisseur", "dimension", "codepostal",
        )
        return bool(key) and not any(token in key for token in forbidden) and key not in {"n", "id"}

    def create_new_referential(self) -> None:
        """Crée un champ Liste inédit et alimente son référentiel depuis une source externe."""
        filename = self._choose_import_file()
        if not filename:
            return
        path = Path(filename)
        is_access = path.suffix.lower() in {".mdb", ".accdb"}
        access_tables: list[dict] = []
        sheets: list[tuple[str, list[str], list[list[str]]]] = []
        try:
            if is_access:
                from ui.import_export_dialog import CollectionImportDialog
                structure = CollectionImportDialog._read_access_structure(path)
                access_tables = [t for t in list(structure.get("tables", []) or []) if list(t.get("fields", []) or [])]
                if not access_tables:
                    QMessageBox.information(self, "Créer un référentiel", "La base Access ne contient aucune table exploitable.")
                    return
            elif path.suffix.lower() == ".xlsx":
                sheets = [(n, h, r) for n, h, r in _read_xlsx_sheets(path) if h]
            else:
                headers, rows = _read_tabular_file(filename)
                sheets = [(path.name, headers, rows)] if headers else []
        except Exception as exc:
            QMessageBox.warning(self, "Import impossible", f"Impossible de lire le fichier :\n{exc}")
            return
        if not is_access and not sheets:
            QMessageBox.information(self, "Créer un référentiel", "Le fichier ne contient aucune donnée exploitable.")
            return

        choose = QDialog(self)
        choose.setWindowTitle("Créer un nouveau référentiel")
        choose.resize(560, 260)
        lay = QVBoxLayout(choose)
        intro = QLabel("Choisissez la colonne qui contient les valeurs. MM3 créera un nouveau champ Liste dans la palette de l’Atelier et son référentiel simple.")
        intro.setWordWrap(True); lay.addWidget(intro)
        source_combo = QComboBox(); column_combo = QComboBox(); name_edit = QLineEdit()

        def access_fields(table: dict) -> list[str]:
            out=[]
            for field in list(table.get("fields", []) or []):
                name = str((field.get("name") or field.get("source_field") or "") if isinstance(field, dict) else field or "").strip()
                if name: out.append(name)
            return out

        if is_access:
            lay.addWidget(QLabel("Table Access :"))
            for idx,t in enumerate(access_tables): source_combo.addItem(str(t.get("name") or f"Table {idx+1}"), idx)
            lay.addWidget(source_combo)
        elif len(sheets)>1:
            lay.addWidget(QLabel("Feuille :"))
            for idx,(n,_h,_r) in enumerate(sheets): source_combo.addItem(n,idx)
            lay.addWidget(source_combo)
        lay.addWidget(QLabel("Colonne à importer :")); lay.addWidget(column_combo)
        lay.addWidget(QLabel("Nom du nouveau champ / référentiel :")); lay.addWidget(name_edit)

        def reload_columns(_index=0):
            column_combo.clear()
            if is_access:
                ti=int(source_combo.currentData()) if source_combo.count() else 0
                for i,h in enumerate(access_fields(access_tables[ti])):
                    if self._referential_candidate_name(h):
                        column_combo.addItem(h,i)
            else:
                si=int(source_combo.currentData()) if len(sheets)>1 else 0
                for i,h in enumerate(sheets[si][1]):
                    if self._referential_candidate_name(str(h)):
                        column_combo.addItem(str(h),i)
            if column_combo.count(): name_edit.setText(column_combo.currentText())
        def sync_name(_index=0):
            name_edit.setText(column_combo.currentText())
        source_combo.currentIndexChanged.connect(reload_columns)
        column_combo.currentIndexChanged.connect(sync_name)
        reload_columns()
        buttons=QHBoxLayout(); buttons.addStretch(1)
        ok=QPushButton("Prévisualiser"); cancel=QPushButton("Annuler")
        ok.clicked.connect(choose.accept); cancel.clicked.connect(choose.reject)
        buttons.addWidget(ok); buttons.addWidget(cancel); lay.addLayout(buttons)
        if choose.exec()!=QDialog.DialogCode.Accepted: return
        label=name_edit.text().strip()
        if not label:
            QMessageBox.warning(self,"Nom manquant","Indiquez le nom du nouveau champ / référentiel."); return

        try:
            if is_access:
                from ui.import_export_dialog import CollectionImportDialog
                ti=int(source_combo.currentData()) if source_combo.count() else 0
                table=access_tables[ti]; fields=access_fields(table); col=int(column_combo.currentData()); fname=fields[col]
                rr=CollectionImportDialog._read_access_rows(path,str(table.get("name") or ""),[fname])
                raw_values=["" if r.get(fname) is None else str(r.get(fname)) for r in rr]
            else:
                si=int(source_combo.currentData()) if len(sheets)>1 else 0
                rows=sheets[si][2]; col=int(column_combo.currentData())
                raw_values=[str(r[col]).strip() if col<len(r) and r[col] is not None else "" for r in rows]
        except Exception as exc:
            QMessageBox.warning(self,"Import impossible",f"Impossible de lire les valeurs :\n{exc}"); return

        values=[]; seen=set(); ignored=0
        for raw in raw_values:
            value=str(raw).strip()
            if not value: ignored+=1; continue
            marker=value.casefold()
            if marker in seen: continue
            seen.add(marker); values.append(value)
        if not values:
            QMessageBox.information(self,"Créer un référentiel","Aucune valeur non vide n'a été trouvée."); return

        preview=QDialog(self); preview.setWindowTitle("Créer un nouveau référentiel"); preview.resize(650,600)
        pl=QVBoxLayout(preview)
        pl.addWidget(QLabel(f"Nouveau champ / référentiel : « {label} »\n{len(values)} valeur(s) unique(s) trouvée(s). Décochez celles à ne pas importer."))
        table=QTableWidget(len(values),1); table.setHorizontalHeaderLabels(["Valeurs à importer"]); table.verticalHeader().setVisible(False); table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch)
        for i,v in enumerate(values):
            item=QTableWidgetItem(v); item.setFlags(item.flags()|Qt.ItemFlag.ItemIsUserCheckable); item.setCheckState(Qt.CheckState.Checked); table.setItem(i,0,item)
        pl.addWidget(table,1)
        bb=QHBoxLayout(); bb.addStretch(1); create=QPushButton("Créer le référentiel"); cancel2=QPushButton("Annuler"); create.clicked.connect(preview.accept); cancel2.clicked.connect(preview.reject); bb.addWidget(create); bb.addWidget(cancel2); pl.addLayout(bb)
        if preview.exec()!=QDialog.DialogCode.Accepted: return
        selected=[values[i] for i in range(len(values)) if table.item(i,0).checkState()==Qt.CheckState.Checked]
        if not selected:
            QMessageBox.information(self,"Créer un référentiel","Aucune valeur n'a été sélectionnée."); return

        cid=int(self.collection["id"]); before_history=self._history_begin()
        try:
            mm=ModelManager(self.startup.database.database_path)
            info=mm.create_custom_field(cid,label,"list")
            code=str(info.get("referential_code") or info.get("field_key") or "")
            field_key=str(info.get("field_key") or code)
            # 26.50 — tout nouveau champ créé par import démarre avec ses
            # données en noir, comme les autres créations modernes de MM3.
            styles=mm.field_styles(cid)
            style=dict(styles.get(field_key, {}))
            data_style=dict(style.get("data", {}))
            data_style["color"]="#000000"
            style["data"]=data_style
            styles[field_key]=style
            mm.set_field_styles(cid, styles)
            result=self.manager.add_values_bulk(cid,code,selected)
        except Exception as exc:
            QMessageBox.warning(self,"Création impossible",str(exc)); return
        self.reload_definitions()
        idx=self.definition_combo.findData(code)
        if idx>=0: self.definition_combo.setCurrentIndex(idx)
        self.reload_values(); self._history_commit(before_history,"Création d'un référentiel")
        QMessageBox.information(self,"Référentiel créé",f"Le champ « {label} » a été créé dans la palette de l’Atelier avec son référentiel simple.\n{result.get('added',0)} valeur(s) ajoutée(s).\n{ignored} ligne(s) vide(s) ignorée(s).\n\nLe champ n'est pas placé automatiquement sur la Fiche.")

    def import_file_values(self) -> None:
        """Ajoute des valeurs externes au référentiel actuellement sélectionné.

        39.32.11.7.32 — le mode « liste simple » accepte désormais Access en
        plus des formats déjà gérés ici. Il ne crée ni champ, ni liaison
        Maître/Relié : il ajoute uniquement des valeurs au référentiel choisi.
        """
        definition = self._current_definition()
        if definition is None:
            return
        filename = self._choose_import_file()
        if not filename:
            return

        path = Path(filename)
        is_access = path.suffix.lower() in {".mdb", ".accdb"}
        access_tables: list[dict] = []
        sheets: list[tuple[str, list[str], list[list[str]]]] = []

        try:
            if is_access:
                # Réutiliser exactement le lecteur Access rapide déjà validé
                # dans Import/Export, sans dupliquer le moteur OLE DB.
                from ui.import_export_dialog import CollectionImportDialog
                structure = CollectionImportDialog._read_access_structure(path)
                access_tables = [
                    t for t in list(structure.get("tables", []) or [])
                    if list(t.get("fields", []) or [])
                ]
                if not access_tables:
                    QMessageBox.information(self, "Import", "La base Access ne contient aucune table exploitable.")
                    return
            elif path.suffix.lower() == ".xlsx":
                sheets = _read_xlsx_sheets(path)
                sheets = [(name, headers, rows) for name, headers, rows in sheets if headers]
                if not sheets:
                    QMessageBox.information(self, "Import", "Le classeur ne contient aucune feuille exploitable.")
                    return
            else:
                headers, rows = _read_tabular_file(filename)
                sheets = [(path.name, headers, rows)] if headers else []
        except Exception as exc:
            QMessageBox.warning(self, "Import impossible", f"Impossible de lire le fichier :\n{exc}")
            return

        if not is_access and not sheets:
            QMessageBox.information(self, "Import", "Le fichier ne contient aucune donnée.")
            return

        choose = QDialog(self)
        choose.setWindowTitle("Ajouter des valeurs à un référentiel")
        lay = QVBoxLayout(choose)
        target_label = str(definition.get("label") or definition.get("code") or "référentiel")
        lay.addWidget(QLabel(f"Référentiel MM3 de destination : « {target_label} »"))

        source_combo = QComboBox()
        column_combo = QComboBox()

        if is_access:
            lay.addWidget(QLabel("Table Access contenant les valeurs :"))
            for idx, table in enumerate(access_tables):
                source_combo.addItem(str(table.get("name") or f"Table {idx + 1}"), idx)
            lay.addWidget(source_combo)
        elif len(sheets) > 1:
            lay.addWidget(QLabel("Feuille Excel contenant les valeurs :"))
            for idx, (name, _headers, _rows) in enumerate(sheets):
                source_combo.addItem(name, idx)
            lay.addWidget(source_combo)

        lay.addWidget(QLabel("Colonne contenant les valeurs à ajouter :"))
        lay.addWidget(column_combo)

        def access_field_names(table: dict) -> list[str]:
            result: list[str] = []
            for field in list(table.get("fields", []) or []):
                if isinstance(field, dict):
                    name = str(field.get("name") or field.get("source_field") or "").strip()
                else:
                    name = str(field or "").strip()
                if name:
                    result.append(name)
            return result

        def reload_columns(index: int = 0) -> None:
            column_combo.clear()
            if is_access:
                table_index = int(source_combo.currentData()) if source_combo.count() else 0
                if table_index < 0 or table_index >= len(access_tables):
                    table_index = 0
                for col, header in enumerate(access_field_names(access_tables[table_index])):
                    column_combo.addItem(header, col)
            else:
                sheet_index = int(source_combo.currentData()) if len(sheets) > 1 else 0
                if sheet_index < 0 or sheet_index >= len(sheets):
                    sheet_index = 0
                for col, header in enumerate(sheets[sheet_index][1]):
                    column_combo.addItem(str(header), col)

        if is_access or len(sheets) > 1:
            source_combo.currentIndexChanged.connect(reload_columns)
        reload_columns()

        row_buttons = QHBoxLayout()
        row_buttons.addStretch(1)
        ok = QPushButton("Ajouter les valeurs")
        cancel = QPushButton("Annuler")
        ok.clicked.connect(choose.accept)
        cancel.clicked.connect(choose.reject)
        row_buttons.addWidget(ok)
        row_buttons.addWidget(cancel)
        lay.addLayout(row_buttons)

        if choose.exec() != QDialog.DialogCode.Accepted:
            return

        try:
            if is_access:
                from ui.import_export_dialog import CollectionImportDialog
                table_index = int(source_combo.currentData()) if source_combo.count() else 0
                if table_index < 0 or table_index >= len(access_tables):
                    table_index = 0
                table = access_tables[table_index]
                table_name = str(table.get("name") or "")
                fields = access_field_names(table)
                col = int(column_combo.currentData())
                if col < 0 or col >= len(fields):
                    raise ValueError("Colonne Access invalide.")
                field_name = fields[col]
                access_rows = CollectionImportDialog._read_access_rows(path, table_name, [field_name])
                rows = [["" if row.get(field_name) is None else str(row.get(field_name))] for row in access_rows]
                col = 0
            else:
                sheet_index = int(source_combo.currentData()) if len(sheets) > 1 else 0
                if sheet_index < 0 or sheet_index >= len(sheets):
                    sheet_index = 0
                _sheet_name, _headers, rows = sheets[sheet_index]
                col = int(column_combo.currentData())
        except Exception as exc:
            QMessageBox.warning(self, "Import impossible", f"Impossible de lire les valeurs sélectionnées :\n{exc}")
            return

        code = str(definition["code"])
        values: list[str] = []
        ignored = 0
        seen: set[str] = set()
        for row in rows:
            raw = str(row[col]).strip() if col < len(row) and row[col] is not None else ""
            if not raw:
                ignored += 1
                continue
            normalized = self.manager.normalize(raw, code)
            if not normalized:
                ignored += 1
                continue
            marker = normalized.casefold()
            if marker in seen:
                continue
            seen.add(marker)
            values.append(normalized)

        if not values:
            QMessageBox.information(self, "Import", "Aucune valeur non vide n'a été trouvée dans cette colonne.")
            return

        # 39.32.11.7.33 — prévisualisation obligatoire avant écriture.
        # Afficher toutes les valeurs uniques trouvées dans la colonne source,
        # distinguer celles déjà présentes dans MM3 et permettre à l'utilisateur
        # de n'importer qu'une partie des nouvelles valeurs.
        collection_id = int(self.collection["id"])
        existing_values = self.manager.list_values(collection_id, code, active_only=True)
        existing_markers = {str(v).strip().casefold() for v in existing_values if str(v).strip()}
        new_count = sum(1 for value in values if value.casefold() not in existing_markers)
        existing_count = len(values) - new_count

        preview = QDialog(self)
        preview.setWindowTitle("Valeurs à ajouter au référentiel")
        preview.resize(680, 620)
        preview_layout = QVBoxLayout(preview)
        preview_layout.addWidget(QLabel(
            f"Référentiel MM3 : « {target_label} »\n"
            f"{len(values)} valeur(s) unique(s) trouvée(s) — "
            f"{new_count} nouvelle(s) — {existing_count} déjà présente(s)."
        ))
        preview_layout.addWidget(QLabel(
            "Décochez les valeurs que vous ne souhaitez pas ajouter. "
            "Les valeurs déjà présentes sont indiquées mais ne seront pas réimportées."
        ))

        preview_table = QTableWidget(len(values), 2, preview)
        preview_table.setHorizontalHeaderLabels(["Valeur", "État"])
        preview_table.verticalHeader().setVisible(False)
        preview_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        preview_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        preview_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        preview_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)

        selectable_rows: list[int] = []
        for row_index, value in enumerate(values):
            marker = value.casefold()
            value_item = QTableWidgetItem(value)
            state_item = QTableWidgetItem()
            if marker in existing_markers:
                value_item.setFlags(value_item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
                value_item.setCheckState(Qt.CheckState.Unchecked)
                value_item.setFlags(value_item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
                state_item.setText("Déjà présente")
                state_item.setFlags(state_item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            else:
                value_item.setFlags(value_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                value_item.setCheckState(Qt.CheckState.Checked)
                state_item.setText("Nouvelle")
                selectable_rows.append(row_index)
            preview_table.setItem(row_index, 0, value_item)
            preview_table.setItem(row_index, 1, state_item)
        preview_layout.addWidget(preview_table, 1)

        select_buttons = QHBoxLayout()
        select_all = QPushButton("Tout sélectionner")
        select_none = QPushButton("Tout désélectionner")
        invert = QPushButton("Inverser la sélection")
        select_buttons.addWidget(select_all)
        select_buttons.addWidget(select_none)
        select_buttons.addWidget(invert)
        select_buttons.addStretch(1)
        preview_layout.addLayout(select_buttons)

        def set_checks(state: Qt.CheckState) -> None:
            for row_index in selectable_rows:
                item = preview_table.item(row_index, 0)
                if item is not None:
                    item.setCheckState(state)

        def invert_checks() -> None:
            for row_index in selectable_rows:
                item = preview_table.item(row_index, 0)
                if item is not None:
                    item.setCheckState(
                        Qt.CheckState.Unchecked
                        if item.checkState() == Qt.CheckState.Checked
                        else Qt.CheckState.Checked
                    )

        # 39.32.11.7.34 — rendre immédiatement visibles les valeurs écartées.
        # Une nouvelle valeur décochée reste cliquable mais toute sa ligne est grisée.
        # Les valeurs déjà présentes conservent leur affichage désactivé natif.
        normal_text_brush = QApplication.palette().text()
        unchecked_text_brush = QBrush(QColor(145, 145, 145))

        def refresh_row_style(row_index: int) -> None:
            if row_index not in selectable_rows:
                return
            value_item = preview_table.item(row_index, 0)
            if value_item is None:
                return
            brush = (
                normal_text_brush
                if value_item.checkState() == Qt.CheckState.Checked
                else unchecked_text_brush
            )
            preview_table.blockSignals(True)
            try:
                for column_index in range(preview_table.columnCount()):
                    row_item = preview_table.item(row_index, column_index)
                    if row_item is not None:
                        row_item.setForeground(brush)
            finally:
                preview_table.blockSignals(False)

        def refresh_all_row_styles() -> None:
            for row_index in selectable_rows:
                refresh_row_style(row_index)

        def on_preview_item_changed(item: QTableWidgetItem) -> None:
            if item.column() == 0 and item.row() in selectable_rows:
                refresh_row_style(item.row())

        preview_table.itemChanged.connect(on_preview_item_changed)
        refresh_all_row_styles()

        select_all.clicked.connect(lambda: set_checks(Qt.CheckState.Checked))
        select_none.clicked.connect(lambda: set_checks(Qt.CheckState.Unchecked))
        invert.clicked.connect(invert_checks)

        action_buttons = QHBoxLayout()
        action_buttons.addStretch(1)
        add_selected = QPushButton("Ajouter la sélection")
        cancel_preview = QPushButton("Annuler")
        add_selected.clicked.connect(preview.accept)
        cancel_preview.clicked.connect(preview.reject)
        action_buttons.addWidget(add_selected)
        action_buttons.addWidget(cancel_preview)
        preview_layout.addLayout(action_buttons)

        if preview.exec() != QDialog.DialogCode.Accepted:
            return

        selected_values: list[str] = []
        for row_index in selectable_rows:
            item = preview_table.item(row_index, 0)
            if item is not None and item.checkState() == Qt.CheckState.Checked:
                selected_values.append(values[row_index])

        if not selected_values:
            QMessageBox.information(self, "Import", "Aucune nouvelle valeur n'a été sélectionnée.")
            return

        before_history = self._history_begin()
        result = self.manager.add_values_bulk(collection_id, code, selected_values)
        self.reload_values()
        self._history_commit(before_history, "Ajout de valeurs externes")
        QMessageBox.information(
            self,
            "Ajout terminé",
            f"{result.get('added', 0)} nouvelle(s) valeur(s) ajoutée(s).\n"
            f"{existing_count} valeur(s) de la source déjà présente(s) dans MM3.\n"
            f"{len(selectable_rows) - len(selected_values)} nouvelle(s) valeur(s) laissée(s) de côté.\n"
            f"{ignored} ligne(s) vide(s) ignorée(s).",
        )

    def _model_field_choices(self) -> list[tuple[str, str]]:
        from core.field_catalog import FIELD_BY_KEY
        from core.model_manager import ModelManager

        manager = ModelManager(self.startup.database.database_path)
        cid = int(self.collection["id"])
        custom_labels = manager.custom_labels(cid)
        custom_map = manager.custom_field_map(cid)
        visible = manager.visible_fields(cid)
        keys = [k for k in manager.all_model_keys(cid) if k in visible and k not in {"record_number", "photo_data"}]
        choices = []
        for key in keys:
            if key in custom_map:
                label = str(custom_map[key].get("label") or key)
            else:
                spec = FIELD_BY_KEY.get(key)
                label = str(custom_labels.get(key) or (spec.label if spec else key))
            choices.append((label, key))
        return sorted(choices, key=lambda item: item[0].casefold())

    def _referential_code_for_field(self, field_key: str) -> str | None:
        from core.field_catalog import FIELD_BY_KEY
        from core.model_manager import ModelManager

        manager = ModelManager(self.startup.database.database_path)
        custom = manager.custom_field_map(int(self.collection["id"])).get(str(field_key))
        if custom:
            return str(custom.get("referential_code") or "") or None
        spec = FIELD_BY_KEY.get(str(field_key))
        return str(spec.referential) if spec and spec.referential else None

    def import_complete_referential(self) -> None:
        """Importe une matrice Maître -> champs reliés sans créer de fiches."""
        filename = self._choose_import_file()
        if not filename:
            return
        try:
            headers, rows = _read_tabular_file(filename)
        except Exception as exc:
            QMessageBox.warning(self, "Import impossible", f"Impossible de lire le fichier :\\n{exc}")
            return
        if not headers or not rows:
            QMessageBox.information(self, "Import", "Le fichier ne contient aucune donnée exploitable.")
            return

        choices = self._model_field_choices()
        definition = self._current_definition()
        current_ref_code = str(definition.get("code") or "") if definition else ""
        preferred_master_key = next(
            (key for _label, key in choices if self._referential_code_for_field(key) == current_ref_code),
            "",
        )
        dialog = ReferentialMappingDialog(
            headers, choices, self, preferred_master_key=preferred_master_key
        )
        dialog.setStyleSheet(self.styleSheet())
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        master_col, mapping = dialog.mapping()
        master_key = mapping.get(master_col, "")
        if not master_key:
            QMessageBox.warning(
                self,
                "Champ Maître manquant",
                "La colonne choisie comme Maître doit être associée à un champ MM3.",
            )
            return
        if len(mapping) < 2:
            QMessageBox.warning(
                self,
                "Import incomplet",
                "Associez au moins une autre colonne au champ Maître.",
            )
            return

        imported_rows = []
        for source_row in rows:
            mapped = {}
            for col, key in mapping.items():
                mapped[key] = source_row[col].strip() if col < len(source_row) else ""
            if mapped.get(master_key, "").strip():
                imported_rows.append(mapped)

        before_history = self._history_begin()
        progress = QProgressDialog(
            "Importation du référentiel en cours…\nVeuillez patienter.",
            "",
            0,
            0,
            self,
        )
        progress.setWindowTitle("Importation en cours")
        progress.setCancelButton(None)
        progress.setMinimumDuration(0)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setAutoClose(False)
        progress.setAutoReset(False)

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        progress.show()
        QApplication.processEvents()

        try:
            from core.model_manager import ModelManager
            model_manager = ModelManager(self.startup.database.database_path)
            result = model_manager.import_reference_rows(
                int(self.collection["id"]), master_key, imported_rows
            )

            # Alimenter également les listes déroulantes, mais en LOT :
            # l'ancienne version ouvrait SQLite pour chaque cellule et pouvait prendre
            # plusieurs minutes sur un référentiel IMA complet.
            values_by_referential: dict[str, list[str]] = {}
            for mapped in imported_rows:
                for key, value in mapped.items():
                    if not value:
                        continue
                    ref_code = self._referential_code_for_field(key)
                    if ref_code:
                        values_by_referential.setdefault(ref_code, []).append(value)

            for ref_code, values in values_by_referential.items():
                try:
                    self.manager.add_values_bulk(
                        int(self.collection["id"]), ref_code, values
                    )
                except Exception:
                    pass

            self.reload_definitions()
        finally:
            progress.close()
            QApplication.restoreOverrideCursor()
            QApplication.processEvents()

        self._history_commit(before_history, "Import d'un référentiel complet")
        linked_count = max(0, len(set(mapping.values())) - 1)
        QMessageBox.information(
            self,
            "Référentiel importé",
            f"{result['rows']} ligne(s) importée(s), "
            f"{result['masters']} valeur(s) Maître distincte(s).\n"
            f"{linked_count} champ(s) relié(s) au Maître « "
            f"{next((label for label, key in choices if key == master_key), master_key)} ».\n\n"
            "Aucune fiche n'a été créée : ces données servent uniquement de référentiel.",
        )


    def import_existing(self) -> None:
        definition = self._current_definition()
        if definition is None:
            return
        count = self.manager.import_existing_record_values(
            int(self.collection["id"]), str(definition["code"])
        )
        self.reload_values()
        QMessageBox.information(
            self,
            "Import terminé",
            f"{count} nouvelle(s) valeur(s) ajoutée(s) depuis les fiches existantes.",
        )

    def _update_buttons(self) -> None:
        selected = self.list_widget.selectedItems()
        definition = self._current_definition()
        code = str(definition["code"]) if definition else ""
        removable = any(not (code == "record_state" and self._raw_value(item).casefold() in {"ok", "libre"}) for item in selected)
        self.remove_btn.setEnabled(removable)
        if hasattr(self, "undo_btn"):
            self.undo_btn.setEnabled(bool(self._undo_stack))
        if hasattr(self, "redo_btn"):
            self.redo_btn.setEnabled(bool(self._redo_stack))
