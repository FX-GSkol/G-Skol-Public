#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import sqlite3
from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QMessageBox,
    QPushButton, QVBoxLayout, QWidget, QInputDialog,
)

from core.field_catalog import FIELD_BY_KEY, REFERENTIAL_BY_FIELD
from core.i18n import tr, display_native_value, canonical_native_value
from core.model_manager import ModelManager
from core.collection_manager import CollectionManager
from core.record_manager import RecordManager
from core.referential_manager import ReferentialManager


class ToolboxDialog(QDialog):
    """Boîte à outils — opérations volontaires portant sur toute la collection."""

    # Émis après toute modification globale (remplacement ou Défaire).
    # La fenêtre principale peut ainsi rafraîchir immédiatement les vues déjà ouvertes.
    dataChanged = Signal()
    collectionDuplicated = Signal(str)
    collectionEmptied = Signal()

    def __init__(self, db_path, collection_id: int, collection_name: str, parent=None, language: str = "fr") -> None:
        super().__init__(parent)
        self.db_path = db_path
        self.collection_id = int(collection_id)
        self.collection_name = str(collection_name or "")
        self.language = str(language or "fr")
        self.model_manager = ModelManager(db_path)
        self.record_manager = RecordManager(db_path)
        self.referential_manager = ReferentialManager(db_path)
        self._field_rows: list[tuple[str, str, str, str | None]] = []
        self._undo: dict | None = None
        self._fill_undo: dict | None = None

        self.setWindowTitle(f"{tr('Boîte à outils', self.language)} — {self.collection_name}")
        self.setMinimumWidth(650)
        self.resize(720, 430)
        self._build_ui()
        self._load_fields()

    def _connect(self):
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        return con

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(14)

        title = QLabel(tr("Boîte à outils", self.language))
        title.setStyleSheet("font-size: 22px; font-weight: 700;")
        root.addWidget(title)

        collection_label = QLabel(self.collection_name)
        collection_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        collection_label.setStyleSheet("font-size: 20px; font-weight: 700;")
        root.addWidget(collection_label)

        intro = QLabel(
            tr("Ces outils agissent volontairement sur l’ensemble de la collection. G-Skol indique toujours le nombre de fiches concernées avant toute modification.", self.language)
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        # Bloc 1 — remplacement global d'une valeur.
        replace_group = QGroupBox(tr("Remplacer une valeur dans toute la collection", self.language))
        replace_group.setStyleSheet("QGroupBox { font-size: 16px; font-weight: 650; border: 3px solid #4f5d55; border-radius: 5px; margin-top: 10px; padding-top: 8px; } QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; }")
        replace_layout = QVBoxLayout(replace_group)
        replace_layout.setContentsMargins(12, 16, 12, 12)
        replace_layout.setSpacing(10)

        form = QFormLayout()
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(12)

        self.field_combo = QComboBox()
        self.field_combo.currentIndexChanged.connect(self._field_changed)
        form.addRow(tr("Champ :", self.language), self.field_combo)

        self.old_combo = QComboBox()
        self.old_combo.setEditable(True)
        self.old_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.old_combo.currentTextChanged.connect(self._update_count)
        form.addRow(tr("Valeur à remplacer :", self.language), self.old_combo)

        self.new_combo = QComboBox()
        self.new_combo.setEditable(True)
        self.new_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        form.addRow(tr("Nouvelle valeur :", self.language), self.new_combo)

        self.count_label = QLabel(tr("0 fiche concernée", self.language))
        self.count_label.setStyleSheet("font-weight: 650;")
        form.addRow(tr("Résultat :", self.language), self.count_label)
        replace_layout.addLayout(form)

        note = QLabel(tr("Le remplacement porte sur la valeur complète du champ, et non sur une partie du texte.", self.language))
        note.setWordWrap(True)
        note.setStyleSheet("color: #5f6b65; font-weight: 400;")
        replace_layout.addWidget(note)

        replace_buttons = QHBoxLayout()
        self.undo_btn = QPushButton(tr(tr("Défaire", self.language), self.language))
        self.undo_btn.setEnabled(False)
        self.undo_btn.clicked.connect(self._undo_last)
        self.replace_btn = QPushButton(tr("Remplacer", self.language))
        self.replace_btn.clicked.connect(self._replace)
        replace_buttons.addWidget(self.undo_btn)
        replace_buttons.addStretch(1)
        replace_buttons.addWidget(self.replace_btn)
        replace_layout.addLayout(replace_buttons)
        root.addWidget(replace_group)

        # Bloc 2 — compléter uniquement les champs actuellement vides.
        fill_group = QGroupBox(tr("Compléter les champs vides", self.language))
        fill_group.setStyleSheet("QGroupBox { font-size: 16px; font-weight: 650; border: 3px solid #4f5d55; border-radius: 5px; margin-top: 10px; padding-top: 8px; } QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; }")
        fill_layout = QVBoxLayout(fill_group)
        fill_layout.setContentsMargins(12, 16, 12, 12)
        fill_layout.setSpacing(10)

        fill_form = QFormLayout()
        fill_form.setHorizontalSpacing(18)
        fill_form.setVerticalSpacing(12)

        self.fill_field_combo = QComboBox()
        self.fill_field_combo.currentIndexChanged.connect(self._fill_field_changed)
        fill_form.addRow(tr("Champ :", self.language), self.fill_field_combo)

        self.fill_value_combo = QComboBox()
        self.fill_value_combo.setEditable(True)
        self.fill_value_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.fill_value_combo.currentTextChanged.connect(self._update_fill_state)
        fill_form.addRow(tr("Valeur à inscrire :", self.language), self.fill_value_combo)

        self.fill_count_label = QLabel(tr("0 fiche concernée", self.language))
        self.fill_count_label.setStyleSheet("font-weight: 650;")
        fill_form.addRow(tr("Résultat :", self.language), self.fill_count_label)
        fill_layout.addLayout(fill_form)

        fill_note = QLabel(
            tr("Seules les fiches dont ce champ est vide seront complétées. Les valeurs déjà présentes ne seront jamais modifiées.", self.language)
        )
        fill_note.setWordWrap(True)
        fill_note.setStyleSheet("color: #5f6b65; font-weight: 400;")
        fill_layout.addWidget(fill_note)

        fill_buttons = QHBoxLayout()
        self.fill_undo_btn = QPushButton(tr(tr("Défaire", self.language), self.language))
        self.fill_undo_btn.setEnabled(False)
        self.fill_undo_btn.clicked.connect(self._undo_fill)
        self.fill_btn = QPushButton(tr("Compléter", self.language))
        self.fill_btn.clicked.connect(self._fill_empty)
        fill_buttons.addWidget(self.fill_undo_btn)
        fill_buttons.addStretch(1)
        fill_buttons.addWidget(self.fill_btn)
        fill_layout.addLayout(fill_buttons)
        root.addWidget(fill_group)

        # Bloc 3 — duplication de la structure de la collection.
        duplicate_group = QGroupBox(tr("Dupliquer la structure de la collection", self.language))
        duplicate_group.setStyleSheet("QGroupBox { font-size: 16px; font-weight: 650; border: 3px solid #4f5d55; border-radius: 5px; margin-top: 10px; padding-top: 8px; } QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; }")
        duplicate_layout = QVBoxLayout(duplicate_group)
        duplicate_layout.setContentsMargins(12, 16, 12, 12)
        duplicate_layout.setSpacing(8)

        duplicate_text = QLabel(
            tr("Crée une collection sœur vide, identique à celle-ci. La Fiche, les paramètres et les référentiels sont conservés, mais les fiches, leurs données et leurs photos ne sont pas copiées. La première fiche créée portera le N° 1.", self.language)
        )
        duplicate_text.setWordWrap(True)
        duplicate_text.setStyleSheet("font-weight: 400;")
        duplicate_layout.addWidget(duplicate_text)

        duplicate_buttons = QHBoxLayout()
        duplicate_btn = QPushButton(tr("Dupliquer la structure de cette collection", self.language))
        duplicate_btn.clicked.connect(self._duplicate_structure)
        duplicate_buttons.addWidget(duplicate_btn)
        duplicate_buttons.addStretch(1)
        duplicate_layout.addLayout(duplicate_buttons)
        root.addWidget(duplicate_group)

        root.addStretch(1)

        bottom_buttons = QHBoxLayout()
        bottom_buttons.addStretch(1)
        close_btn = QPushButton(tr("Fermer", self.language))
        close_btn.clicked.connect(self.accept)
        bottom_buttons.addWidget(close_btn)
        root.addLayout(bottom_buttons)

    def _load_fields(self) -> None:
        """Ne propose que les champs réellement présents dans le modèle courant."""
        self._field_rows.clear()
        self.field_combo.blockSignals(True)
        self.field_combo.clear()

        labels = self.model_manager.custom_labels(self.collection_id)
        styles = self.model_manager.field_styles(self.collection_id)
        custom_map = self.model_manager.custom_field_map(self.collection_id)
        visible = set(self.model_manager.visible_fields(self.collection_id))
        ordered = self.model_manager.tab_order(self.collection_id, list(visible))

        for key in ordered:
            key = str(key)
            if key in {"record_number", "photo_data"} or key not in visible:
                continue
            if styles.get(key, {}).get("field_deleted"):
                continue

            custom = custom_map.get(key)
            if custom is not None:
                # Les résultats calculés ne sont pas des données à remplacer.
                if str(custom.get("field_type") or "") == "calculated":
                    continue
                label = (
                    str(labels.get(key) or "").strip()
                    or str(custom.get("label") or "").strip()
                    or key
                )
                ref = str(custom.get("referential_code") or "").strip() or None
                self._field_rows.append((label, key, "custom", ref))
                continue

            if key not in RecordManager.FIELD_DEFAULTS:
                continue
            spec = FIELD_BY_KEY.get(key)
            label = str(labels.get(key) or (spec.label if spec else key))
            self._field_rows.append(
                (label, key, "standard", REFERENTIAL_BY_FIELD.get(key))
            )

        self.field_combo.addItems([])  # garde le modèle Qt initialisé sans signal
        for label, key, kind, ref in self._field_rows:
            self.field_combo.addItem(tr(str(label), self.language), (key, kind, ref))
        self.field_combo.blockSignals(False)

        self.fill_field_combo.blockSignals(True)
        self.fill_field_combo.clear()
        # 11.7.70.26.52 — dans « Compléter les champs vides », le choix du
        # champ est un choix de maintenance et non un parcours de saisie :
        # l'ordre alphabétique est donc plus naturel que l'ordre de tabulation.
        fill_rows = sorted(self._field_rows, key=lambda row: row[0].casefold())
        for label, key, kind, ref in fill_rows:
            self.fill_field_combo.addItem(tr(str(label), self.language), (key, kind, ref))
        self.fill_field_combo.blockSignals(False)

        self._field_changed()
        self._fill_field_changed()

    def _current_field(self):
        data = self.field_combo.currentData()
        return data if isinstance(data, tuple) and len(data) == 3 else None

    def _values_for_field(self, key: str, kind: str) -> list[str]:
        with self._connect() as con:
            RecordManager._ensure_table(con)
            if kind == "standard":
                # key vient exclusivement de FIELD_DEFAULTS : pas d'identifiant SQL utilisateur.
                rows = con.execute(
                    f'SELECT DISTINCT "{key}" AS value FROM records '
                    'WHERE collection_id=? AND TRIM(COALESCE("' + key + '", \'\')) <> \'\' '
                    'ORDER BY value COLLATE NOCASE',
                    (self.collection_id,),
                ).fetchall()
            else:
                RecordManager._ensure_custom_values_table(con)
                rows = con.execute(
                    "SELECT DISTINCT rcv.value AS value FROM record_custom_values rcv "
                    "JOIN records r ON r.id=rcv.record_id "
                    "WHERE r.collection_id=? AND rcv.field_key=? AND TRIM(COALESCE(rcv.value,''))<>'' "
                    "ORDER BY rcv.value COLLATE NOCASE",
                    (self.collection_id, key),
                ).fetchall()
        return [str(r["value"] or "") for r in rows]

    def _field_changed(self, *_args) -> None:
        current = self._current_field()
        self.old_combo.blockSignals(True)
        self.old_combo.clear()
        self.new_combo.clear()
        if current:
            key, kind, referential = current
            used_values = self._values_for_field(key, kind)
            values = list(used_values)
            if referential:
                # Pour un champ à liste, afficher le référentiel complet :
                # l'utilisateur peut ainsi choisir le libellé exact sans le retaper.
                try:
                    ref_values = self.referential_manager.list_values(
                        self.collection_id, referential, active_only=False
                    )
                except Exception:
                    ref_values = []
                seen = set()
                values = []
                for value in [*ref_values, *used_values]:
                    text = str(value or "")
                    marker = text.casefold()
                    if text and marker not in seen:
                        seen.add(marker)
                        values.append(text)
            # Dédupliquer APRES traduction d’affichage : plusieurs anciennes
            # valeurs canoniques (À vérifier / A vérifier / Valider / Vérifier)
            # peuvent toutes devenir « Check » en anglais. La Toolbox ne doit
            # alors présenter qu’une seule valeur visible.
            shown_values = []
            shown_seen = set()
            for value in values:
                shown = display_native_value(value, self.language)
                marker = shown.strip().casefold()
                if shown.strip() and marker not in shown_seen:
                    shown_seen.add(marker)
                    shown_values.append(shown)
            self.old_combo.addItems(shown_values)
            self.new_combo.addItems(shown_values)
            # Les listes restent éditables : une nouvelle valeur peut être saisie
            # dans « Nouvelle valeur » et sera ajoutée au référentiel au remplacement.
            self.old_combo.setMaxVisibleItems(24)
            self.new_combo.setMaxVisibleItems(24)
        self.old_combo.setCurrentIndex(-1)
        self.new_combo.setCurrentIndex(-1)
        self.old_combo.blockSignals(False)
        self._update_count()

    def _matching_ids(self, key: str, kind: str, old: str) -> list[int]:
        with self._connect() as con:
            RecordManager._ensure_table(con)
            if kind == "standard":
                rows = con.execute(
                    f'SELECT id FROM records WHERE collection_id=? AND "{key}"=? ORDER BY id',
                    (self.collection_id, old),
                ).fetchall()
            else:
                RecordManager._ensure_custom_values_table(con)
                rows = con.execute(
                    "SELECT r.id FROM records r JOIN record_custom_values v ON v.record_id=r.id "
                    "WHERE r.collection_id=? AND v.field_key=? AND v.value=? ORDER BY r.id",
                    (self.collection_id, key, old),
                ).fetchall()
        return [int(r[0]) for r in rows]

    def _update_count(self, *_args) -> None:
        current = self._current_field()
        old = canonical_native_value(self.old_combo.currentText(), self.language)
        count = len(self._matching_ids(current[0], current[1], old)) if current and old != "" else 0
        self.count_label.setText(tr("{count} fiche(s) concernée(s)", self.language).format(count=count))
        self.replace_btn.setEnabled(count > 0)

    def _replace(self) -> None:
        current = self._current_field()
        if not current:
            return
        key, kind, referential = current
        old = canonical_native_value(self.old_combo.currentText(), self.language)
        new = canonical_native_value(self.new_combo.currentText(), self.language)
        ids = self._matching_ids(key, kind, old)
        if not ids:
            QMessageBox.information(self, tr("Remplacement", self.language), tr("Aucune fiche ne contient cette valeur.", self.language))
            return
        if old == new:
            QMessageBox.information(self, tr("Remplacement", self.language), tr("L’ancienne et la nouvelle valeur sont identiques.", self.language))
            return

        label = self.field_combo.currentText()
        confirm_box = QMessageBox(self)
        confirm_box.setIcon(QMessageBox.Icon.Question)
        confirm_box.setWindowTitle(tr("Confirmer le remplacement", self.language))
        confirm_box.setText(tr("Champ : {label}\n\n« {old} » sera remplacé par « {new} » dans {count} fiche(s).\n\nVoulez-vous effectuer ce remplacement ?", self.language).format(label=label, old=old, new=new, count=len(ids)))
        yes_button = confirm_box.addButton(tr("Oui", self.language), QMessageBox.ButtonRole.YesRole)
        no_button = confirm_box.addButton(tr("Non", self.language), QMessageBox.ButtonRole.NoRole)
        confirm_box.setDefaultButton(no_button)
        confirm_box.exec()
        if confirm_box.clickedButton() is not yes_button:
            return

        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as con:
            RecordManager._ensure_table(con)
            if kind == "standard":
                placeholders = ",".join("?" for _ in ids)
                con.execute(
                    f'UPDATE records SET "{key}"=?, updated_at=? WHERE collection_id=? AND id IN ({placeholders})',
                    [new, now, self.collection_id, *ids],
                )
            else:
                RecordManager._ensure_custom_values_table(con)
                if new:
                    placeholders = ",".join("?" for _ in ids)
                    con.execute(
                        f"UPDATE record_custom_values SET value=? WHERE field_key=? AND record_id IN ({placeholders})",
                        [new, key, *ids],
                    )
                else:
                    placeholders = ",".join("?" for _ in ids)
                    con.execute(
                        f"DELETE FROM record_custom_values WHERE field_key=? AND record_id IN ({placeholders})",
                        [key, *ids],
                    )
                placeholders = ",".join("?" for _ in ids)
                con.execute(
                    f"UPDATE records SET updated_at=? WHERE collection_id=? AND id IN ({placeholders})",
                    [now, self.collection_id, *ids],
                )

        # Pour un champ à liste, une nouvelle valeur saisie devient immédiatement une valeur valide.
        if referential and new.strip():
            try:
                if not self.referential_manager.contains(
                    self.collection_id, referential, new, active_only=False
                ):
                    self.referential_manager.add_value(self.collection_id, referential, new)
            except Exception:
                pass

        self._undo = {"key": key, "kind": kind, "old": old, "new": new, "ids": ids}
        self.undo_btn.setEnabled(True)
        self._field_changed()
        self.dataChanged.emit()
        QMessageBox.information(self, tr("Remplacement effectué", self.language), tr("{count} fiche(s) modifiée(s).", self.language).format(count=len(ids)))

    def _current_fill_field(self):
        data = self.fill_field_combo.currentData()
        return data if isinstance(data, tuple) and len(data) == 3 else None

    def _empty_ids(self, key: str, kind: str) -> list[int]:
        """IDs des fiches où le champ est réellement vide (absent, NULL ou espaces)."""
        with self._connect() as con:
            RecordManager._ensure_table(con)
            if kind == "standard":
                rows = con.execute(
                    f'SELECT id FROM records WHERE collection_id=? '
                    f'AND TRIM(COALESCE("{key}", \'\'))=\'\' ORDER BY id',
                    (self.collection_id,),
                ).fetchall()
            else:
                RecordManager._ensure_custom_values_table(con)
                rows = con.execute(
                    "SELECT r.id FROM records r LEFT JOIN record_custom_values v "
                    "ON v.record_id=r.id AND v.field_key=? "
                    "WHERE r.collection_id=? AND TRIM(COALESCE(v.value,''))='' ORDER BY r.id",
                    (key, self.collection_id),
                ).fetchall()
        return [int(r[0]) for r in rows]

    def _fill_field_changed(self, *_args) -> None:
        current = self._current_fill_field()
        self.fill_value_combo.blockSignals(True)
        self.fill_value_combo.clear()
        if current:
            key, kind, referential = current
            values: list[str] = []
            if referential:
                try:
                    values = [str(v or "") for v in self.referential_manager.list_values(
                        self.collection_id, referential, active_only=False
                    ) if str(v or "").strip()]
                except Exception:
                    values = []
            shown_values = []
            shown_seen = set()
            for value in values:
                shown = display_native_value(value, self.language)
                marker = shown.strip().casefold()
                if shown.strip() and marker not in shown_seen:
                    shown_seen.add(marker)
                    shown_values.append(shown)
            self.fill_value_combo.addItems(shown_values)
            self.fill_value_combo.setMaxVisibleItems(24)
        self.fill_value_combo.setCurrentIndex(-1)
        self.fill_value_combo.blockSignals(False)
        self._update_fill_state()

    def _update_fill_state(self, *_args) -> None:
        current = self._current_fill_field()
        count = len(self._empty_ids(current[0], current[1])) if current else 0
        self.fill_count_label.setText(
            tr("{count} fiche(s) concernée(s)", self.language).format(count=count)
        )
        self.fill_btn.setEnabled(count > 0 and bool(self.fill_value_combo.currentText().strip()))

    def _fill_empty(self) -> None:
        current = self._current_fill_field()
        if not current:
            return
        key, kind, referential = current
        value = canonical_native_value(self.fill_value_combo.currentText().strip(), self.language)
        if not value:
            QMessageBox.information(self, tr("Compléter les champs vides", self.language), tr("Indiquez la valeur à inscrire.", self.language))
            return
        ids = self._empty_ids(key, kind)
        if not ids:
            QMessageBox.information(self, tr("Compléter les champs vides", self.language), tr("Aucune fiche ne possède ce champ vide.", self.language))
            return

        label = self.fill_field_combo.currentText()
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle(tr("Confirmer le complément", self.language))
        box.setText(tr("Champ : {label}\n\nLa valeur « {value} » sera inscrite uniquement dans {count} fiche(s) où ce champ est vide.\n\nLes fiches déjà renseignées resteront intactes. Voulez-vous continuer ?", self.language).format(label=label, value=value, count=len(ids)))
        yes_button = box.addButton(tr("Oui", self.language), QMessageBox.ButtonRole.YesRole)
        no_button = box.addButton(tr("Non", self.language), QMessageBox.ButtonRole.NoRole)
        box.setDefaultButton(no_button)
        box.exec()
        if box.clickedButton() is not yes_button:
            return

        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as con:
            RecordManager._ensure_table(con)
            placeholders = ",".join("?" for _ in ids)
            if kind == "standard":
                # Recontrôle du vide dans l'UPDATE : aucune donnée non vide ne peut être écrasée.
                con.execute(
                    f'UPDATE records SET "{key}"=?, updated_at=? WHERE collection_id=? '
                    f'AND id IN ({placeholders}) AND TRIM(COALESCE("{key}", \'\'))=\'\'',
                    [value, now, self.collection_id, *ids],
                )
            else:
                RecordManager._ensure_custom_values_table(con)
                for rid in ids:
                    row = con.execute(
                        "SELECT value FROM record_custom_values WHERE record_id=? AND field_key=?",
                        (rid, key),
                    ).fetchone()
                    if row is None:
                        con.execute(
                            "INSERT INTO record_custom_values(record_id, field_key, value) VALUES(?,?,?)",
                            (rid, key, value),
                        )
                    elif not str(row[0] or "").strip():
                        con.execute(
                            "UPDATE record_custom_values SET value=? WHERE record_id=? AND field_key=?",
                            (value, rid, key),
                        )
                con.execute(
                    f"UPDATE records SET updated_at=? WHERE collection_id=? AND id IN ({placeholders})",
                    [now, self.collection_id, *ids],
                )

        if referential:
            try:
                if not self.referential_manager.contains(
                    self.collection_id, referential, value, active_only=False
                ):
                    self.referential_manager.add_value(self.collection_id, referential, value)
            except Exception:
                pass

        self._fill_undo = {"key": key, "kind": kind, "value": value, "ids": ids}
        self.fill_undo_btn.setEnabled(True)
        self._fill_field_changed()
        self.dataChanged.emit()
        QMessageBox.information(
            self, tr("Champs complétés", self.language),
            tr("{count} fiche(s) complétée(s).", self.language).format(count=len(ids))
        )

    def _undo_fill(self) -> None:
        op = getattr(self, "_fill_undo", None)
        if not op:
            return
        key, kind = op["key"], op["kind"]
        ids = list(op["ids"])
        value = op["value"]
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as con:
            RecordManager._ensure_table(con)
            placeholders = ",".join("?" for _ in ids)
            if kind == "standard":
                # N'annule que les valeurs que cette opération avait inscrites.
                con.execute(
                    f'UPDATE records SET "{key}"=\'\', updated_at=? WHERE collection_id=? '
                    f'AND id IN ({placeholders}) AND "{key}"=?',
                    [now, self.collection_id, *ids, value],
                )
            else:
                RecordManager._ensure_custom_values_table(con)
                con.execute(
                    f"DELETE FROM record_custom_values WHERE field_key=? AND value=? "
                    f"AND record_id IN ({placeholders})",
                    [key, value, *ids],
                )
                con.execute(
                    f"UPDATE records SET updated_at=? WHERE collection_id=? AND id IN ({placeholders})",
                    [now, self.collection_id, *ids],
                )
        self._fill_undo = None
        self.fill_undo_btn.setEnabled(False)
        self._fill_field_changed()
        self.dataChanged.emit()
        QMessageBox.information(self, tr("Défaire", self.language), tr("Le dernier complément de champs vides a été annulé.", self.language))

    def _duplicate_structure(self) -> None:
        default_name = tr("{name} - Copie vierge", self.language).format(name=self.collection_name)
        name_dialog = QInputDialog(self)
        name_dialog.setWindowTitle(tr("Dupliquer la structure", self.language))
        name_dialog.setLabelText(tr("Nom de la nouvelle collection :", self.language))
        name_dialog.setTextValue(default_name)
        name_dialog.setOkButtonText("OK")
        name_dialog.setCancelButtonText(tr("Annuler", self.language))
        name_dialog.resize(620, 145)
        ok = name_dialog.exec() == QDialog.DialogCode.Accepted
        name = str(name_dialog.textValue() or "").strip()
        if not ok:
            return
        if not name:
            QMessageBox.warning(self, tr("Dupliquer la structure", self.language), tr("Le nom de la nouvelle collection est obligatoire.", self.language))
            return
        try:
            result = CollectionManager(self.db_path).duplicate_collection_to_file(self.collection_id, name)
            new_path = str(result.get("_database_path") or "")
            if not new_path:
                raise ValueError(tr("Le fichier de la nouvelle collection n'a pas pu être identifié.", self.language))
            self._empty_database_collection(new_path, int(result["id"]))
        except Exception as exc:
            QMessageBox.critical(self, tr("Dupliquer la structure", self.language), tr("La collection sœur n'a pas pu être créée.\n\n{error}", self.language).format(error=exc))
            return
        self.collectionDuplicated.emit(new_path)
        QMessageBox.information(
            self, tr("Collection sœur créée", self.language),
            tr("La collection « {name} » a été créée.\n\nElle conserve la Fiche, ses réglages et les référentiels, mais ne contient aucune fiche. La première fiche créée portera le N° 1.", self.language).format(name=result["name"])
        )

    @staticmethod
    def _empty_database_collection(db_path, collection_id: int) -> int:
        con = sqlite3.connect(db_path)
        try:
            con.execute("PRAGMA foreign_keys=OFF")
            tables = {str(r[0]) for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
            count = int(con.execute("SELECT COUNT(*) FROM records WHERE collection_id=?", (collection_id,)).fetchone()[0]) if "records" in tables else 0
            record_ids = [int(r[0]) for r in con.execute("SELECT id FROM records WHERE collection_id=?", (collection_id,)).fetchall()] if "records" in tables else []
            if record_ids:
                placeholders = ",".join("?" for _ in record_ids)
                for table in ("record_custom_values", "record_extra_photos"):
                    if table in tables:
                        con.execute(f'DELETE FROM "{table}" WHERE record_id IN ({placeholders})', record_ids)
            if "records" in tables:
                con.execute("DELETE FROM records WHERE collection_id=?", (collection_id,))
            con.commit()
            # Recompacte la base afin que les photos BLOB supprimées ne continuent pas à occuper le fichier.
            con.execute("VACUUM")
            return count
        finally:
            con.close()

    def _empty_collection(self) -> None:
        try:
            with self._connect() as con:
                RecordManager._ensure_table(con)
                count = int(con.execute("SELECT COUNT(*) FROM records WHERE collection_id=?", (self.collection_id,)).fetchone()[0])
        except Exception as exc:
            QMessageBox.critical(self, tr("Vider la collection", self.language), str(exc))
            return

        box = QMessageBox(self)
        box.setWindowTitle(tr("Vider complètement la collection", self.language))
        box.setIcon(QMessageBox.Icon.Warning)
        box.setTextFormat(Qt.TextFormat.RichText)
        box.setText(tr(
            '<div align="center"><span style="color:#c00000; font-size:18px; font-weight:700;">ATTENTION</span></div><p><b>Toute cette collection va être entièrement vidée.</b></p><p>{count} fiche(s) ainsi que leurs données et leurs photos seront définitivement supprimées.</p><p>La structure de la Fiche, sa présentation et les référentiels seront conservés.<br>La prochaine fiche créée portera le <b>N° 1</b>.</p><p><b>Travaillez de préférence sur une copie de votre collection ou sur une collection préalablement dupliquée.</b></p>',
            self.language).format(count=count))
        cancel = box.addButton(tr("Annuler", self.language), QMessageBox.ButtonRole.RejectRole)
        empty = box.addButton(tr("Vider complètement la collection", self.language), QMessageBox.ButtonRole.DestructiveRole)
        box.setDefaultButton(cancel)
        box.exec()
        if box.clickedButton() is not empty:
            return
        try:
            deleted = self._empty_database_collection(self.db_path, self.collection_id)
        except Exception as exc:
            QMessageBox.critical(self, tr("Vider la collection", self.language), tr("La collection n'a pas pu être vidée.\n\n{error}", self.language).format(error=exc))
            return
        self._undo = None
        self.undo_btn.setEnabled(False)
        self._field_changed()
        self.collectionEmptied.emit()
        self.dataChanged.emit()
        QMessageBox.information(
            self, tr("Collection vidée", self.language),
            tr("{count} fiche(s) supprimée(s).\n\nLa structure et les référentiels ont été conservés. La prochaine fiche créée portera le N° 1.", self.language).format(count=deleted)
        )

    def _undo_last(self) -> None:
        op = self._undo
        if not op:
            return
        ids = list(op["ids"])
        key, kind, old, new = op["key"], op["kind"], op["old"], op["new"]
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as con:
            RecordManager._ensure_table(con)
            placeholders = ",".join("?" for _ in ids)
            if kind == "standard":
                con.execute(
                    f'UPDATE records SET "{key}"=?, updated_at=? WHERE collection_id=? AND id IN ({placeholders})',
                    [old, now, self.collection_id, *ids],
                )
            else:
                RecordManager._ensure_custom_values_table(con)
                for rid in ids:
                    if old:
                        con.execute(
                            "INSERT INTO record_custom_values(record_id, field_key, value) VALUES(?,?,?) "
                            "ON CONFLICT(record_id, field_key) DO UPDATE SET value=excluded.value",
                            (rid, key, old),
                        )
                    else:
                        con.execute("DELETE FROM record_custom_values WHERE record_id=? AND field_key=?", (rid, key))
                con.execute(
                    f"UPDATE records SET updated_at=? WHERE collection_id=? AND id IN ({placeholders})",
                    [now, self.collection_id, *ids],
                )
        self._undo = None
        self.undo_btn.setEnabled(False)
        self._field_changed()
        self.dataChanged.emit()
        QMessageBox.information(self, tr("Défaire", self.language), tr("Le dernier remplacement a été annulé.", self.language))
