#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from ui.color_dialog import choose_color
from core.calculation_formula import normalize as normalize_calculation_formula
from core.collection_folders import collection_display_name

from collections.abc import Callable
import ast
import copy
from datetime import datetime
import json
import sqlite3
import math
import re
from pathlib import Path

from PySide6.QtCore import QByteArray, QDate, QEvent, QMarginsF, QMimeData, QStringListModel, QTimer, Qt, Signal
from PySide6.QtGui import QAction, QBrush, QColor, QFont, QFontMetrics, QKeySequence, QPageLayout, QPainter, QPen, QShortcut, QTextDocument, QTextLength, QTextOption, QTextTable, QTextTableCellFormat
from PySide6.QtPrintSupport import QPrinter, QPrintPreviewDialog, QPrintPreviewWidget
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QCompleter,
    QDialog,
    QDialogButtonBox,
    QFontComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLineEdit,
    QLabel,
    QMenu,
    QMessageBox,
    QMainWindow,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QStyledItemDelegate,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from core.record_manager import RecordManager
from core.i18n import display_native_value, canonical_native_value, translate_widget_tree, tr
from core.field_catalog import TABLE_COLUMNS, NUMERIC_FIELDS, DATE_FIELDS, FIELD_BY_KEY, field_sort_key
from ui.collection_theme import collection_theme
from core.referential_manager import ReferentialManager
from core.model_manager import ModelManager
from core.model_library import library_root, write_model, read_model, collect_model_field_keys, build_field_manifest
from ui.model_library_dialog import choose_model_save_path, choose_model_open_path, resolve_model_fields
from ui.saved_model_folders import choose_folder, manage_folders, SavedModelCombo
from core import saved_model_folders as model_folders
from core.collection_saved_models import load as load_collection_models, save as save_collection_models


def _mm3_is_record_state_label(value) -> bool:
    """Reconnaît le libellé système État de la fiche, accents/casse indifférents."""
    text = str(value or "").strip().casefold()
    text = text.replace("é", "e").replace("è", "e").replace("ê", "e").replace("ë", "e")
    return text == "etat de la fiche"


class NumericTableWidgetItem(QTableWidgetItem):
    """Élément de tableau dont le tri est réellement numérique."""

    def __lt__(self, other) -> bool:  # type: ignore[override]
        try:
            return int(self.data(Qt.ItemDataRole.UserRole + 1)) < int(
                other.data(Qt.ItemDataRole.UserRole + 1)
            )
        except (TypeError, ValueError):
            return super().__lt__(other)


class ColumnChooserDialog(QDialog):
    """Choix simple des colonnes affichées dans la Vue Tableau."""

    def __init__(self, columns: tuple[tuple[str, str], ...], visible_fields: list[str], parent=None) -> None:
        super().__init__(parent)
        self.columns = columns
        self.setWindowTitle("Choisir les colonnes")
        self.resize(520, 560)

        root = QVBoxLayout(self)
        title = QLabel("Colonnes à afficher")
        title.setStyleSheet("font-size: 19px; font-weight: 700;")
        subtitle = QLabel(
            "Cochez les informations que vous souhaitez voir. Le N° de fiche reste toujours affiché."
        )
        subtitle.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(subtitle)

        actions = QHBoxLayout()
        select_all = QPushButton("Tout sélectionner")
        select_all.clicked.connect(lambda: self._set_all(True))
        select_none = QPushButton("Tout désélectionner")
        select_none.clicked.connect(lambda: self._set_all(False))
        actions.addWidget(select_all)
        actions.addWidget(select_none)
        actions.addStretch(1)
        root.addLayout(actions)

        area = QScrollArea()
        area.setWidgetResizable(True)
        container = QWidget()
        grid = QGridLayout(container)
        grid.setContentsMargins(8, 8, 8, 8)
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(7)
        self.checks: dict[str, QCheckBox] = {}
        for index, (label, field) in enumerate(columns):
            check = QCheckBox(label)
            if field in {"record_number", "record_state"}:
                check.setStyleSheet("QCheckBox { color: #0055FF; }")
            check.setChecked(field in visible_fields or field == "record_number")
            if field == "record_number":
                check.setEnabled(False)
            self.checks[field] = check
            grid.addWidget(check, index // 2, index % 2)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        area.setWidget(container)
        root.addWidget(area, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        translate_widget_tree(self, getattr(parent, "language", "fr"))

    def _set_all(self, checked: bool) -> None:
        for field, check in self.checks.items():
            if field != "record_number":
                check.setChecked(checked)

    def selected_fields(self) -> list[str]:
        return [
            field
            for _label, field in self.columns
            if field == "record_number" or self.checks[field].isChecked()
        ]



class A4GuideTableWidget(QTableWidget):
    """QTableWidget affichant la limite droite imprimable d'une feuille A4."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._mm3_show_a4_guide = True
        self._mm3_orientation = "portrait"
        self._mm3_margin_mm = 5.0

    def set_a4_guide(self, visible: bool, orientation: str = "portrait") -> None:
        self._mm3_show_a4_guide = bool(visible)
        self._mm3_orientation = (
            "landscape" if str(orientation) == "landscape" else "portrait"
        )
        self.viewport().update()

    def a4_printable_width_pixels(self) -> float:
        """Largeur imprimable A4 en pixels écran, marges MM3 comprises."""
        page_width_mm = 297.0 if self._mm3_orientation == "landscape" else 210.0
        printable_mm = max(10.0, page_width_mm - 2.0 * self._mm3_margin_mm)
        dpi = max(72.0, float(self.logicalDpiX()))
        return printable_mm / 25.4 * dpi

    def a4_guide_viewport_x(self) -> int:
        """Position du repère dans le viewport en tenant compte du défilement."""
        content_x = self.a4_printable_width_pixels()
        return int(round(content_x - self.horizontalScrollBar().value()))

    def paintEvent(self, event):  # type: ignore[override]
        super().paintEvent(event)
        if not self._mm3_show_a4_guide:
            return
        x = self.a4_guide_viewport_x()
        if x < 0 or x > self.viewport().width():
            return

        painter = QPainter(self.viewport())
        pen = QPen(QColor("#77847E"))
        pen.setWidth(1)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawLine(x, 0, x, self.viewport().height())
        painter.end()



class MM3CompletingLineEdit(QLineEdit):
    """Zone de saisie avec complétion inline stable."""

    def __init__(self, choices: list[str], parent=None) -> None:
        super().__init__(parent)
        self._mm3_choices = tuple(str(v) for v in choices if str(v))
        self._mm3_internal_change = False

        model = QStringListModel(list(self._mm3_choices), self)
        completer = QCompleter(model, self)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.setCompleter(completer)
        self._mm3_completion_model = model
        self._mm3_completer = completer

    def set_choices(self, choices: list[str]) -> None:
        self._mm3_choices = tuple(str(v) for v in choices if str(v))
        self._mm3_completion_model.setStringList(list(self._mm3_choices))

    def keyPressEvent(self, event):  # type: ignore[override]
        # Qt traite d'abord la frappe normalement.
        super().keyPressEvent(event)

        if self._mm3_internal_change:
            return

        # Retour arrière / Suppr annulent la proposition inline en cours sans
        # la recréer immédiatement. L'utilisateur peut ensuite poursuivre avec
        # un autre texte, même absent du référentiel.
        if event.key() in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete):
            try:
                current = self.text()
                if current:
                    self._mm3_completer.setCompletionPrefix(current)
                    self._mm3_completer.complete()
            except RuntimeError:
                pass
            return

        if event.key() in (
            Qt.Key.Key_Up, Qt.Key.Key_Down,
            Qt.Key.Key_Left, Qt.Key.Key_Right,
            Qt.Key.Key_Return, Qt.Key.Key_Enter,
            Qt.Key.Key_Escape, Qt.Key.Key_Tab, Qt.Key.Key_Backtab,
        ):
            return

        current = self.text()
        selected = self.selectedText()
        base = current[:len(current) - len(selected)] if selected else current

        if not base:
            return

        prefix_matches = [
            value for value in self._mm3_choices
            if value.casefold().startswith(base.casefold())
        ]

        if len(prefix_matches) == 1:
            match = prefix_matches[0]
            if match.casefold() != base.casefold():
                self._mm3_internal_change = True
                try:
                    self.setText(match)
                    self.setSelection(len(base), len(match) - len(base))
                finally:
                    self._mm3_internal_change = False

        try:
            c = self._mm3_completer
            c.setCompletionPrefix(base)
            c.complete()
        except RuntimeError:
            pass



class MM3FilterValueCombo(QComboBox):
    """Valeur de filtre avec liste assistée du référentiel, sans écriture."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.setMaxVisibleItems(25)
        self._line = MM3CompletingLineEdit([], self)
        self._line.setClearButtonEnabled(True)
        self.setLineEdit(self._line)
        self.set_values([])

    def set_values(self, values: list[str]) -> None:
        current = self.currentText()
        self.blockSignals(True)
        QComboBox.clear(self)
        self.addItems(values)
        self._line.set_choices(values)
        self.setEditText(current)
        self.blockSignals(False)

        if values:
            self.setStyleSheet("")
            self.setToolTip(
                "Tapez quelques lettres ou ouvrez la liste. "
                "Le filtre ne peut pas ajouter de valeur au référentiel."
            )
        else:
            self.setStyleSheet(
                "QComboBox::drop-down { width: 0px; border: none; }"
                "QComboBox::down-arrow { image: none; }"
            )
            self.setToolTip("")

    def text(self) -> str:
        return self.currentText()

    def setText(self, value: str) -> None:
        self.setEditText(str(value or ""))

    def clear(self) -> None:  # type: ignore[override]
        self.setEditText("")

    def setPlaceholderText(self, text: str) -> None:
        self._line.setPlaceholderText(text)

    def setClearButtonEnabled(self, enabled: bool) -> None:
        self._line.setClearButtonEnabled(enabled)

    def set_match_mode(self, starts_with: bool) -> None:
        """Adapte la liste de suggestions à l'opérateur du filtre."""
        mode = (
            Qt.MatchFlag.MatchStartsWith
            if starts_with
            else Qt.MatchFlag.MatchContains
        )
        self._line._mm3_completer.setFilterMode(mode)


class TableBorderDelegate(QStyledItemDelegate):
    """Dessine les traits horizontaux/verticaux selon la mise en page MM3."""

    def __init__(self, style_provider, parent=None) -> None:
        super().__init__(parent)
        self._style_provider = style_provider

    def paint(self, painter, option, index):  # type: ignore[override]
        super().paint(painter, option, index)

        try:
            style = dict(self._style_provider() or {})
        except Exception:
            style = {}

        mode = str(style.get("borders") or "all")
        row_width = max(0, int(style.get("row_lines", 1)))
        column_width = max(0, int(style.get("column_lines", 1)))

        draw_rows = mode in {"all", "rows"} and row_width > 0
        draw_columns = mode in {"all", "columns"} and column_width > 0
        if not draw_rows and not draw_columns:
            return

        painter.save()
        color = QColor("#9AA5A0")

        rect = option.rect
        model = index.model()
        last_row = model.rowCount() - 1
        last_col = model.columnCount() - 1

        if draw_rows:
            pen = QPen(color)
            pen.setWidth(row_width)
            pen.setStyle(Qt.PenStyle.SolidLine)
            painter.setPen(pen)

            # Trait supérieur de la première ligne + traits inférieurs.
            if index.row() == 0:
                painter.drawLine(rect.topLeft(), rect.topRight())
            painter.drawLine(rect.bottomLeft(), rect.bottomRight())

        if draw_columns:
            pen = QPen(color)
            pen.setWidth(column_width)
            pen.setStyle(Qt.PenStyle.SolidLine)
            painter.setPen(pen)

            # Trait gauche de la première colonne + traits droits.
            if index.column() == 0:
                painter.drawLine(rect.topLeft(), rect.bottomLeft())
            painter.drawLine(rect.topRight(), rect.bottomRight())

        painter.restore()



class TableLayoutDialog(QDialog):
    """Atelier simplifié de mise en page de la Vue Tableau."""

    DEFAULTS = {
        "header_font": "Calibri",
        "header_size": 9,
        "header_bold": True,
        "header_italic": False,
        "header_underline": False,
        "header_text": "#111111",
        "header_bg": "#DDE8E2",
        "body_font": "Calibri",
        "body_size": 8,
        "body_bold": False,
        "body_italic": False,
        "body_underline": False,
        "body_text": "#111111",
        "body_bg": "#FFFFFF",
        "borders": "all",
        "row_lines": 1,
        "column_lines": 1,
        "orientation": "portrait",
        "show_a4": True,
    }

    def __init__(self, current: dict, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Mise en page du Tableau")
        self.resize(920, 690)
        self.setMinimumSize(780, 600)
        self.values = {**self.DEFAULTS, **dict(current or {})}

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(9)

        title = QLabel("Mise en page du Tableau")
        title.setStyleSheet("font-size:20px; font-weight:700;")
        subtitle = QLabel(
            "Réglages globaux de présentation. "
            "L'alignement d'une colonne se règle directement par clic droit sur son en-tête."
        )
        subtitle.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(subtitle)

        styles_row = QHBoxLayout()
        styles_row.setSpacing(10)
        self.header_box = self._build_text_style_box("En-têtes de colonnes", "header")
        self.body_box = self._build_text_style_box("Données du tableau", "body")
        styles_row.addWidget(self.header_box, 1)
        styles_row.addWidget(self.body_box, 1)
        root.addLayout(styles_row)

        options_row = QHBoxLayout()
        options_row.setSpacing(10)

        traits = QGroupBox("Traits")
        tg = QGridLayout(traits)
        tg.setContentsMargins(9, 7, 9, 9)
        tg.setHorizontalSpacing(8)
        tg.setVerticalSpacing(6)

        self.borders_combo = QComboBox()
        self.borders_combo.addItem("Toutes", "all")
        self.borders_combo.addItem("Horizontales seulement", "rows")
        self.borders_combo.addItem("Verticales seulement", "columns")
        self.borders_combo.addItem("Aucune", "none")
        self._set_combo_data(self.borders_combo, self.values["borders"])

        self.row_lines = QSpinBox()
        self.row_lines.setRange(0, 3)
        self.row_lines.setSuffix(" pt")
        self.row_lines.setValue(int(self.values["row_lines"]))

        self.column_lines = QSpinBox()
        self.column_lines.setRange(0, 3)
        self.column_lines.setSuffix(" pt")
        self.column_lines.setValue(int(self.values["column_lines"]))

        tg.addWidget(QLabel("Bordures :"), 0, 0)
        tg.addWidget(self.borders_combo, 0, 1)
        tg.addWidget(QLabel("Traits lignes :"), 1, 0)
        tg.addWidget(self.row_lines, 1, 1)
        tg.addWidget(QLabel("Traits colonnes :"), 2, 0)
        tg.addWidget(self.column_lines, 2, 1)
        options_row.addWidget(traits, 1)

        printing = QGroupBox("Impression")
        pg = QGridLayout(printing)
        pg.setContentsMargins(9, 7, 9, 9)
        pg.setHorizontalSpacing(8)
        pg.setVerticalSpacing(6)

        self.portrait = QRadioButton("Portrait")
        self.landscape = QRadioButton("Paysage")
        if self.values["orientation"] == "landscape":
            self.landscape.setChecked(True)
        else:
            self.portrait.setChecked(True)

        self.show_a4 = QCheckBox("Afficher le repère de largeur A4")
        self.show_a4.setChecked(bool(self.values["show_a4"]))

        pg.addWidget(QLabel("Orientation :"), 0, 0)
        ori = QHBoxLayout()
        ori.addWidget(self.portrait)
        ori.addWidget(self.landscape)
        ori.addStretch(1)
        pg.addLayout(ori, 0, 1)
        pg.addWidget(self.show_a4, 1, 0, 1, 2)
        options_row.addWidget(printing, 1)

        root.addLayout(options_row)

        preview_box = QGroupBox("Aperçu dynamique")
        preview_lay = QVBoxLayout(preview_box)
        preview_lay.setContentsMargins(8, 7, 8, 8)
        # L'aperçu reprend les colonnes visibles du tableau qui a ouvert ce dialogue.
        source = getattr(parent, "table", None)
        visible_columns = []
        if source is not None:
            for col in range(source.columnCount()):
                if not source.isColumnHidden(col):
                    visible_columns.append(col)
        # Ne jamais inventer de colonnes ou de données d'une autre collection.
        self.preview = QTableWidget(min(3, source.rowCount()) if source is not None else 0,
                                    len(visible_columns))
        if source is not None:
            headers = []
            for col in visible_columns:
                item = source.horizontalHeaderItem(col)
                headers.append(item.text() if item is not None else "")
            self.preview.setHorizontalHeaderLabels(headers)
        self.preview.verticalHeader().setVisible(False)
        self.preview.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.preview.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.preview.setAlternatingRowColors(False)
        self.preview.setShowGrid(False)
        self.preview.setItemDelegate(
            TableBorderDelegate(self._preview_border_style, self.preview)
        )
        if source is not None:
            for r in range(self.preview.rowCount()):
                for preview_col, source_col in enumerate(visible_columns):
                    source_item = source.item(r, source_col)
                    value = source_item.text() if source_item is not None else ""
                    item = QTableWidgetItem(value)
                    if source_item is not None:
                        item.setTextAlignment(source_item.textAlignment())
                    self.preview.setItem(r, preview_col, item)
            for preview_col, source_col in enumerate(visible_columns):
                self.preview.setColumnWidth(preview_col, source.columnWidth(source_col))
        self.preview.horizontalHeader().setStretchLastSection(False)
        self.preview.setFixedHeight(145)
        preview_lay.addWidget(self.preview)
        self.a4_hint = QLabel("⋮  repère A4")
        self.a4_hint.setAlignment(Qt.AlignmentFlag.AlignRight)
        preview_lay.addWidget(self.a4_hint)
        root.addWidget(preview_box, 1)

        buttons = QHBoxLayout()
        reset_btn = QPushButton("Réinitialiser")
        reset_btn.clicked.connect(self._reset)
        cancel_btn = QPushButton("Annuler")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("Enregistrer")
        save_btn.setObjectName("primaryButton")
        save_btn.clicked.connect(self.accept)
        buttons.addStretch(1)
        buttons.addWidget(reset_btn)
        buttons.addWidget(cancel_btn)
        buttons.addWidget(save_btn)
        root.addLayout(buttons)

        # Rafraîchissement dynamique de la miniature.
        for signal in (
            self.header_font.currentFontChanged,
            self.header_size.valueChanged,
            self.header_bold.toggled,
            self.header_italic.toggled,
            self.header_underline.toggled,
            self.body_font.currentFontChanged,
            self.body_size.valueChanged,
            self.body_bold.toggled,
            self.body_italic.toggled,
            self.body_underline.toggled,
            self.borders_combo.currentIndexChanged,
            self.row_lines.valueChanged,
            self.column_lines.valueChanged,
            self.portrait.toggled,
            self.landscape.toggled,
            self.show_a4.toggled,
        ):
            signal.connect(lambda *_: self._refresh_preview())
        self._refresh_preview()
        translate_widget_tree(self, getattr(parent, "language", "fr"))

    @staticmethod
    def _set_combo_data(combo, value):
        idx = combo.findData(value)
        combo.setCurrentIndex(idx if idx >= 0 else 0)

    def _build_text_style_box(self, title: str, prefix: str):
        box = QGroupBox(title)
        grid = QGridLayout(box)
        grid.setContentsMargins(9, 7, 9, 9)
        grid.setHorizontalSpacing(7)
        grid.setVerticalSpacing(6)

        font = QFontComboBox()
        font.setCurrentFont(QFont(str(self.values[f"{prefix}_font"])))
        font.setMinimumWidth(185)

        size = QSpinBox()
        size.setRange(6, 24)
        size.setSuffix(" pt")
        size.setValue(int(self.values[f"{prefix}_size"]))
        size.setFixedWidth(72)

        bold = QCheckBox("Gras")
        italic = QCheckBox("Italique")
        underline = QCheckBox("Souligné")
        bold.setChecked(bool(self.values[f"{prefix}_bold"]))
        italic.setChecked(bool(self.values[f"{prefix}_italic"]))
        underline.setChecked(bool(self.values[f"{prefix}_underline"]))

        text_btn = self._color_button("Texte", str(self.values[f"{prefix}_text"]))
        bg_btn = self._color_button("Fond", str(self.values[f"{prefix}_bg"]))

        grid.addWidget(QLabel("Police :"), 0, 0)
        grid.addWidget(font, 0, 1, 1, 3)
        grid.addWidget(QLabel("Taille :"), 0, 4)
        grid.addWidget(size, 0, 5)
        grid.addWidget(bold, 1, 0)
        grid.addWidget(italic, 1, 1)
        grid.addWidget(underline, 1, 2)
        grid.addWidget(text_btn, 1, 4)
        grid.addWidget(bg_btn, 1, 5)

        setattr(self, f"{prefix}_font", font)
        setattr(self, f"{prefix}_size", size)
        setattr(self, f"{prefix}_bold", bold)
        setattr(self, f"{prefix}_italic", italic)
        setattr(self, f"{prefix}_underline", underline)
        setattr(self, f"{prefix}_text_btn", text_btn)
        setattr(self, f"{prefix}_bg_btn", bg_btn)
        return box

    def _color_button(self, label: str, color: str):
        btn = QPushButton(label)
        btn.setProperty("mm3Color", color)
        btn.setFixedWidth(72)
        self._paint_color_button(btn)
        btn.clicked.connect(lambda _=False, b=btn: self._choose_color(b))
        return btn

    @staticmethod
    def _paint_color_button(btn):
        color = str(btn.property("mm3Color") or "#FFFFFF")
        q = QColor(color)
        fg = "#F4F4F4" if q.lightness() < 120 else "#111111"
        btn.setStyleSheet(
            "QPushButton {"
            f"background:{color};color:{fg};"
            "border:1px solid #9aa9a3;border-radius:4px;padding:2px 6px;"
            "}"
        )

    def _choose_color(self, btn):
        current = QColor(str(btn.property("mm3Color") or "#FFFFFF"))
        color = choose_color(self, current, "Choisir une couleur")
        if not color.isValid():
            return
        btn.setProperty("mm3Color", color.name())
        self._paint_color_button(btn)
        self._refresh_preview()

    def _style_values(self, prefix: str):
        return {
            "font": getattr(self, f"{prefix}_font").currentFont().family(),
            "size": getattr(self, f"{prefix}_size").value(),
            "bold": getattr(self, f"{prefix}_bold").isChecked(),
            "italic": getattr(self, f"{prefix}_italic").isChecked(),
            "underline": getattr(self, f"{prefix}_underline").isChecked(),
            "text": str(getattr(self, f"{prefix}_text_btn").property("mm3Color")),
            "bg": str(getattr(self, f"{prefix}_bg_btn").property("mm3Color")),
        }

    def _preview_border_style(self) -> dict:
        return {
            "borders": str(self.borders_combo.currentData() or "all"),
            "row_lines": int(self.row_lines.value()),
            "column_lines": int(self.column_lines.value()),
        }

    def _refresh_preview(self):
        header = self._style_values("header")
        body = self._style_values("body")

        hf = QFont(header["font"], int(header["size"]))
        hf.setBold(header["bold"])
        hf.setItalic(header["italic"])
        hf.setUnderline(header["underline"])
        self.preview.horizontalHeader().setFont(hf)
        self.preview.horizontalHeader().setStyleSheet(
            "QHeaderView::section {"
            f"color:{header['text']};background:{header['bg']};"
            "padding:4px;border:1px solid #aab5b0;"
            "}"
        )

        bf = QFont(body["font"], int(body["size"]))
        bf.setBold(body["bold"])
        bf.setItalic(body["italic"])
        bf.setUnderline(body["underline"])
        for r in range(self.preview.rowCount()):
            for c in range(self.preview.columnCount()):
                item = self.preview.item(r, c)
                if item is None:
                    continue
                item.setFont(bf)
                item.setForeground(QColor(body["text"]))
                item.setBackground(QColor(body["bg"]))

        # Les traits sont peints par TableBorderDelegate afin de distinguer
        # réellement Toutes / Horizontales / Verticales / Aucune.
        self.preview.setShowGrid(False)
        self.preview.viewport().update()
        self.a4_hint.setVisible(self.show_a4.isChecked())

    def _reset(self):
        values = dict(self.DEFAULTS)
        self.header_font.setCurrentFont(QFont(values["header_font"]))
        self.header_size.setValue(values["header_size"])
        self.header_bold.setChecked(values["header_bold"])
        self.header_italic.setChecked(values["header_italic"])
        self.header_underline.setChecked(values["header_underline"])
        self.body_font.setCurrentFont(QFont(values["body_font"]))
        self.body_size.setValue(values["body_size"])
        self.body_bold.setChecked(values["body_bold"])
        self.body_italic.setChecked(values["body_italic"])
        self.body_underline.setChecked(values["body_underline"])
        for prefix in ("header", "body"):
            for suffix in ("text", "bg"):
                btn = getattr(self, f"{prefix}_{suffix}_btn")
                btn.setProperty("mm3Color", values[f"{prefix}_{suffix}"])
                self._paint_color_button(btn)
        self._set_combo_data(self.borders_combo, values["borders"])
        self.row_lines.setValue(values["row_lines"])
        self.column_lines.setValue(values["column_lines"])
        self.portrait.setChecked(True)
        self.show_a4.setChecked(values["show_a4"])
        self._refresh_preview()

    def result_values(self):
        out = {}
        for prefix in ("header", "body"):
            v = self._style_values(prefix)
            for key, value in v.items():
                out[f"{prefix}_{key}"] = value
        out.update({
            "borders": str(self.borders_combo.currentData() or "all"),
            "row_lines": int(self.row_lines.value()),
            "column_lines": int(self.column_lines.value()),
            "orientation": "landscape" if self.landscape.isChecked() else "portrait",
            "show_a4": bool(self.show_a4.isChecked()),
        })
        return out



class TableEditDelegate(TableBorderDelegate):
    """Éditeur de cellule MM3 + rendu des bordures du Tableau."""

    def __init__(self, table_window: "TableWindow") -> None:
        super().__init__(
            lambda: table_window.table_layout,
            table_window.table,
        )
        self.window = table_window

    def createEditor(self, parent, option, index):  # type: ignore[override]
        if not self.window._is_cell_editable(index.column()):
            return None
        field = self.window.visible_fields[index.column()]
        ref_code = self.window._referential_code(field)
        if ref_code:
            editor = QComboBox(parent)
            editor.setEditable(True)
            editor.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
            editor.setMaxVisibleItems(25)
            editor.addItem("— Effacer la valeur —", "__MM3_EMPTY__")
            values = self.window.referentials.list_values(
                int(self.window.collection["id"]), ref_code
            )
            # « Libre » est une valeur système MM3 obligatoire de l'état de fiche.
            if ref_code == "record_state" and not any(str(v).strip().casefold() == "libre" for v in values):
                values = list(values) + ["Libre"]
            editor.addItems(values)

            line_edit = MM3CompletingLineEdit(values, editor)
            line_edit.setClearButtonEnabled(True)
            line_edit.setPlaceholderText("Tapez pour rechercher…")
            editor.setLineEdit(line_edit)

            editor._mm3_completer = line_edit._mm3_completer
            editor._mm3_completion_model = line_edit._mm3_completion_model
            line_edit._mm3_delegate_editor = editor
            line_edit.installEventFilter(self)
        else:
            editor = QLineEdit(parent)
            editor.setClearButtonEnabled(True)
        editor.installEventFilter(self)
        editor.setProperty("mm3_row", int(index.row()))
        editor.setProperty("mm3_column", int(index.column()))
        return editor

    def setEditorData(self, editor, index):  # type: ignore[override]
        value = str(index.data(Qt.ItemDataRole.EditRole) or "")
        if isinstance(editor, QComboBox):
            if value:
                found = editor.findText(value, Qt.MatchFlag.MatchFixedString)
                if found < 0:
                    editor.addItem(value)
                    found = editor.findText(value, Qt.MatchFlag.MatchFixedString)
                editor.setCurrentIndex(found)
                editor.setEditText(value)
            else:
                editor.setCurrentIndex(-1)
                editor.setEditText("")
            if editor.lineEdit() is not None:
                editor.lineEdit().selectAll()
        else:
            editor.setText(value)
            editor.selectAll()

    def setModelData(self, editor, model, index):  # type: ignore[override]
        if isinstance(editor, QComboBox):
            value = editor.currentText()
            if value == "— Effacer la valeur —":
                value = ""
        else:
            value = editor.text()
        model.setData(index, str(value).strip(), Qt.ItemDataRole.EditRole)

    def eventFilter(self, editor, event):  # type: ignore[override]
        # Pour un QComboBox éditable, les touches de saisie arrivent sur son
        # QLineEdit interne. On remonte donc toujours à l'éditeur délégué réel.
        target = getattr(editor, "_mm3_delegate_editor", editor)
        if event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if isinstance(target, QComboBox):
                completer = getattr(target, "_mm3_completer", None)
                # Tant que la liste des occurrences est ouverte, les flèches et
                # Entrée restent réservées au choix dans cette liste.
                if completer is not None:
                    try:
                        if completer.popup().isVisible() and key in (
                            Qt.Key.Key_Down, Qt.Key.Key_Up, Qt.Key.Key_Return, Qt.Key.Key_Enter
                        ):
                            return False
                    except RuntimeError:
                        pass
                if target.view().isVisible() and key in (
                    Qt.Key.Key_Down, Qt.Key.Key_Up, Qt.Key.Key_Return, Qt.Key.Key_Enter
                ):
                    return False

            if key == Qt.Key.Key_Down:
                row = int(target.property("mm3_row"))
                column = int(target.property("mm3_column"))
                self.window._prepare_vertical_edit(row, column)
                self.commitData.emit(target)
                self.closeEditor.emit(target, QStyledItemDelegate.EndEditHint.NoHint)
                return True
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.commitData.emit(target)
                self.closeEditor.emit(target, QStyledItemDelegate.EndEditHint.NoHint)
                return True
        return super().eventFilter(editor, event)



class DateTableWidgetItem(QTableWidgetItem):
    """Item affiché en JJ/MM/AAAA mais trié chronologiquement."""

    @staticmethod
    def _date_value(text: str):
        value = str(text or "").strip()
        for fmt in ("dd/MM/yyyy", "d/M/yyyy", "dd/MM/yy", "d/M/yy"):
            parsed = QDate.fromString(value, fmt)
            if parsed.isValid():
                year = parsed.year()
                if year < 100:
                    year += 2000
                    parsed = QDate(year, parsed.month(), parsed.day())
                return parsed
        return QDate()

    def __lt__(self, other):
        left = self._date_value(self.text())
        right = self._date_value(other.text())
        if left.isValid() and right.isValid():
            return left < right
        if left.isValid() != right.isValid():
            return left.isValid()
        return super().__lt__(other)


class TableWindow(QMainWindow):
    """Vue tabulaire de la collection : une ligne = une fiche."""

    recordChanged = Signal(int)

    COLUMNS: tuple[tuple[str, str], ...] = TABLE_COLUMNS

    DEFAULT_FIELDS = [
        "record_number",
        "mineral_name",
        "site_name",
        "country",
        "mineral_class",
        "quality",
        "record_state",
    ]

    STANDARD_WIDTH = 145
    QUERY_VIEW_SENTINEL = "__mm3_query_result__"
    QUERY_VIEW_LABEL = "Vue résultat de la requête"

    TEXT_QUERY_OPERATORS = (
        ("Tous", "tous"),
        ("Contient", "contient"),
        ("Commence par", "commence_par"),
        ("Est exactement", "exactement"),
        ("Est différent de", "different"),
        ("Se termine par", "termine_par"),
        ("Est vide", "est_vide"),
        ("N’est pas vide", "non_vide"),
    )
    NUMERIC_QUERY_OPERATORS = (
        ("Tous", "tous"),
        ("Égal à", "num_egal"),
        ("Différent de", "num_different"),
        ("Supérieur à", "superieur"),
        ("Supérieur ou égal à", "superieur_egal"),
        ("Inférieur à", "inferieur"),
        ("Inférieur ou égal à", "inferieur_egal"),
        ("Compris entre", "entre"),
        ("Est vide", "est_vide"),
        ("N’est pas vide", "non_vide"),
    )
    NUMERIC_QUERY_FIELDS = set(NUMERIC_FIELDS)
    DATE_FIELD_HINTS = ()  # remplacé par DATE_FIELDS du catalogue central
    NO_VALUE_QUERY_OPERATORS = {"tous", "est_vide", "non_vide"}

    def __init__(
        self,
        startup,
        collection: dict,
        open_record_callback: Callable[[int], None],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.startup = startup
        self.language = getattr(getattr(startup, 'settings', None), 'language', 'fr') or 'fr'
        self.collection = dict(collection)
        self.open_record_callback = open_record_callback
        self.manager = RecordManager(self.startup.database.database_path)
        self.referentials = ReferentialManager(self.startup.database.database_path)
        self.model_manager = ModelManager(self.startup.database.database_path)

        cid = int(self.collection["id"])
        self._custom_field_defs = self.model_manager.custom_field_map(cid)
        self._field_styles_cache = self.model_manager.field_styles(cid)
        self.COLUMNS = self._collection_columns()
        self.DEFAULT_FIELDS = self._collection_default_fields()
        self.NUMERIC_QUERY_FIELDS = set(NUMERIC_FIELDS) | {
            key for key, definition in self._custom_field_defs.items()
            if str(definition.get("field_type") or "") in {"numeric", "currency"}
        }
        self.DATE_FIELD_HINTS = tuple(
            key.casefold()
            for key, definition in self._custom_field_defs.items()
            if str(definition.get("field_type") or "") == "date"
        )

        self.records: list[dict] = []
        self.visible_fields = list(self.DEFAULT_FIELDS)
        self.active_filters: list[dict[str, str]] = []
        self.query_criteria: list[dict[str, str]] = []
        self._record_clipboard: dict | None = None
        self._records_clipboard: list[dict] = []
        self._record_clipboard_number: int | None = None
        # Historique local de la Vue Tableau. Il couvre les modifications de données
        # faites depuis le tableau, notamment les collages/importations de fiches.
        self._undo_stack: list[dict] = []
        self._redo_stack: list[dict] = []
        self._history_replaying = False
        # True quand la ligne Filtrer affiche seulement le premier critère de la
        # requête courante comme aide visuelle. Tant que l'utilisateur ne la
        # modifie pas, elle ne constitue PAS un filtre supplémentaire.
        self._query_filter_prefill = False
        self._updating_query_filter = False
        self._widths_initialized = False
        self._loading_view = False
        self.saved_views: dict[str, dict] = {}
        self.current_view_name: str | None = None
        self._view_baseline_state: dict | None = None
        self._populating_table = False
        self._pending_vertical_edit: tuple[int, str] | None = None
        self._refresh_after_edit_scheduled = False
        self.views_file = self.startup.workspace.settings_path / "table_views.json"
        self.table_layout_file = self.startup.workspace.settings_path / "table_layout.json"
        self.table_layout = dict(TableLayoutDialog.DEFAULTS)
        self.column_alignments: dict[str, str] = {}
        self._load_saved_views()
        self._load_table_layout()

        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.setWindowTitle(f"Vue Tableau — {collection_display_name(self.collection, self.language)}")
        self.resize(1280, 760)
        self.setMinimumSize(920, 560)
        self._build_ui()
        translate_widget_tree(self, self.language)
        self._apply_style()
        self.refresh_table()
        self._mark_view_clean()

    def _collection_columns(self) -> tuple[tuple[str, str], ...]:
        """Colonnes construites depuis le modèle réel de la collection."""
        cid = int(self.collection["id"])
        visible = set(self.model_manager.visible_fields(cid))
        custom_labels = self.model_manager.custom_labels(cid)
        native_labels = {field: label for label, field in TABLE_COLUMNS}

        ordered = self.model_manager.tab_order(cid, list(visible))
        result: list[tuple[str, str]] = []
        seen = set()

        # N° de fiche reste toujours disponible et en première position.
        result.append((tr("N°", self.language), "record_number"))
        seen.add("record_number")

        # État de la fiche est un champ système MM3 : il reste toujours disponible,
        # sans dépendre du modèle graphique. Son tri visuel est alphabétique dans
        # les sélecteurs ; seul N° conserve sa place fixe de champ système principal.
        if "record_state" not in visible:
            visible.add("record_state")
        if "record_state" not in ordered:
            ordered = list(ordered) + ["record_state"]

        for key in ordered:
            key = str(key)
            if key in seen or key not in visible:
                continue
            seen.add(key)

            if key in self._custom_field_defs:
                definition = self._custom_field_defs[key]
                label = (
                    str(custom_labels.get(key) or "").strip()
                    or str(definition.get("label") or "").strip()
                    or key
                )
            else:
                spec = FIELD_BY_KEY.get(key)
                label = (
                    str(custom_labels.get(key) or "").strip()
                    or native_labels.get(key)
                    or (str(spec.label) if spec is not None else key)
                )
            result.append((tr(str(label), self.language), key))

        # Un seul « État de la fiche ». Une base importée peut contenir un ancien
        # champ personnalisé homonyme ; le champ système record_state est la
        # référence MM3 et remplace ce doublon dans toutes les listes Tableau.
        if any(str(key) == "record_state" for _label, key in result):
            result = [
                (label, key) for label, key in result
                if str(key) == "record_state" or not _mm3_is_record_state_label(label)
            ]

        # N° reste en tête ; tous les autres champs, y compris État de la fiche,
        # suivent l'ordre alphabétique de leur libellé.
        return tuple(result[:1] + sorted(result[1:], key=lambda item: field_sort_key(item[0])))

    def _collection_default_fields(self) -> list[str]:
        """Vue initiale : N° + premiers champs réels dans l'ordre du modèle."""
        fields = ["record_number"]
        for _label, key in self.COLUMNS:
            if key in {"record_number", "photo_data"}:
                continue
            fields.append(key)
            if len(fields) >= 7:
                break
        return fields

    def _records_with_custom_values(self, records: list[dict]) -> list[dict]:
        """Fusionne les champs personnalisés dans chaque ligne du Tableau."""
        if not records or not self._custom_field_defs:
            return records
        try:
            values_by_record = self.manager.custom_values_for_collection(
                int(self.collection["id"])
            )
        except Exception:
            values_by_record = {}

        merged = []
        for record in records:
            row = dict(record)
            try:
                custom = values_by_record.get(int(row.get("id", 0)), {})
            except Exception:
                custom = {}
            for key in self._custom_field_defs:
                row[key] = str(custom.get(key, "") or "")
            merged.append(row)
        return merged

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("tableRoot")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        title_row = QHBoxLayout()
        title = QLabel("Vue Tableau")
        title.setObjectName("tableTitle")
        subtitle = QLabel(
            "Une ligne = une fiche. Cliquez sur un titre pour trier, déplacez ou redimensionnez les colonnes à la souris."
        )
        subtitle.setObjectName("tableSubtitle")
        subtitle.setWordWrap(False)
        title_row.setSpacing(8)
        title_row.addWidget(title)
        title_row.addWidget(subtitle, 1)
        choose_columns = QPushButton("Choisir les colonnes…")
        choose_columns.clicked.connect(self.choose_columns)
        layout_button = QPushButton("Mise en page…")
        layout_button.clicked.connect(self.open_table_layout)
        print_button = QPushButton("Imprimer")
        print_button.setToolTip(
            "Aperçu avant impression du Tableau exactement dans son état actuel"
        )
        print_button.clicked.connect(self.print_current_table)
        title_row.addWidget(choose_columns)
        title_row.addWidget(layout_button)
        title_row.addWidget(print_button)
        layout.addLayout(title_row)

        self.active_model_name = None
        self.model_name_label = QLabel("Modèle actif : Vue actuelle")
        self.model_name_label.setStyleSheet("font-weight: 600; color: #5A3A2A;")
        layout.addWidget(self.model_name_label)

        self.query_banner = QFrame()
        self.query_banner.setObjectName("queryBanner")
        query_row = QHBoxLayout(self.query_banner)
        query_row.setContentsMargins(10, 7, 10, 7)
        self.query_label = QLabel()
        self.query_label.setObjectName("queryLabel")
        self.query_label.setWordWrap(True)
        show_all_button = QPushButton("Afficher toutes les fiches")
        show_all_button.clicked.connect(self.clear_query)
        query_row.addWidget(self.query_label, 1)
        query_row.addWidget(show_all_button)
        self.query_banner.setVisible(False)
        layout.addWidget(self.query_banner)

        views_row = QHBoxLayout()
        views_label = QLabel("Vue :")
        views_label.setObjectName("filterTitle")
        self.views_combo = SavedModelCombo(self, lambda: self.startup.database.database_path, lambda: self.collection["id"], "tableau", lambda: self.saved_views)
        self.views_combo.setMinimumWidth(220)
        self.views_combo.currentIndexChanged.connect(self._on_view_selected)
        self.save_view_button = QPushButton("Enregistrer la vue…")
        self.save_view_button.clicked.connect(self.save_view_as)
        self.open_view_library_button = QPushButton("Ouvrir un modèle…")
        self.open_view_library_button.setToolTip(tr("Charger un modèle depuis la bibliothèque Modèles de Tableaux", self.language))
        self.open_view_library_button.clicked.connect(self.open_view_from_library)
        self.save_view_library_button = QPushButton("Enregistrer ce modèle")
        self.save_view_library_button.setToolTip(tr("Conserver cette vue dans la bibliothèque Modèles de Tableaux", self.language))
        self.save_view_library_button.clicked.connect(self.save_view_to_library)
        self.update_view_button = QPushButton("Mettre à jour")
        self.update_view_button.clicked.connect(self.update_current_view)
        self.rename_view_button = QPushButton("Renommer…")
        self.rename_view_button.clicked.connect(self.rename_current_view)
        self.delete_view_button = QPushButton("Supprimer…")
        self.delete_view_button.clicked.connect(self.delete_current_view)
        views_row.addWidget(views_label)
        views_row.addWidget(self.views_combo, 1)
        views_row.addWidget(self.save_view_button)
        views_row.addWidget(self.open_view_library_button)
        views_row.addWidget(self.save_view_library_button)
        views_row.addWidget(self.update_view_button)
        views_row.addWidget(self.rename_view_button)
        views_row.addWidget(self.delete_view_button)
        folder_btn = QPushButton("Dossiers…")
        folder_btn.clicked.connect(self._manage_view_folders)
        views_row.addWidget(folder_btn)
        layout.addLayout(views_row)
        self._refresh_views_combo()

        # Filtrage direct de la vue : on peut épingler plusieurs critères,
        # qui sont alors combinés par ET.
        filter_box = QFrame()
        filter_box.setObjectName("filterBox")
        filter_layout = QVBoxLayout(filter_box)
        filter_layout.setContentsMargins(10, 9, 10, 9)
        filter_layout.setSpacing(7)

        filter_row = QHBoxLayout()
        filter_label = QLabel("Filtrer :")
        filter_label.setObjectName("filterTitle")
        self.filter_field = QComboBox()
        self.filter_field.setMinimumWidth(155)
        self._refresh_filter_fields()
        self.filter_operator = QComboBox()
        self.filter_operator.setMinimumWidth(175)
        self._refresh_filter_operators()
        self.filter_value = MM3FilterValueCombo()
        self.filter_value.setPlaceholderText(tr("Tapez une valeur…", self.language))
        self.filter_value.setClearButtonEnabled(True)

        self.filter_value_2 = QLineEdit()
        self.filter_value_2.setPlaceholderText("Et…")
        self.filter_value_2.setClearButtonEnabled(True)
        self.filter_value_2.setVisible(False)

        self.filter_value.lineEdit().textChanged.connect(self._activate_prefilled_query_filter)
        self.filter_value.lineEdit().textChanged.connect(self._on_filter_value_changed)
        self.filter_value_2.textChanged.connect(self._activate_prefilled_query_filter)
        self.filter_value_2.textChanged.connect(self._on_filter_value_changed)
        self.filter_field.currentIndexChanged.connect(self._activate_prefilled_query_filter)
        self.filter_field.currentIndexChanged.connect(self._on_filter_field_changed)
        self.filter_operator.currentIndexChanged.connect(self._activate_prefilled_query_filter)
        self.filter_operator.currentIndexChanged.connect(self._on_filter_operator_changed)
        self._refresh_filter_value_choices()
        add_filter = QPushButton("Ajouter ce filtre")
        add_filter.clicked.connect(self._pin_current_filter)
        self.clear_filters_button = QPushButton("Effacer les filtres")
        self.clear_filters_button.clicked.connect(self._clear_filters)
        filter_row.addWidget(filter_label)
        filter_row.addWidget(self.filter_field)
        filter_row.addWidget(self.filter_operator)
        filter_row.addWidget(self.filter_value, 1)
        filter_row.addWidget(self.filter_value_2, 1)
        filter_row.addWidget(add_filter)
        filter_row.addWidget(self.clear_filters_button)
        filter_layout.addLayout(filter_row)

        self.filters_summary = QLabel("Aucun filtre actif")
        self.filters_summary.setObjectName("filtersSummary")
        self.filters_summary.setWordWrap(True)
        filter_layout.addWidget(self.filters_summary)
        layout.addWidget(filter_box)

        info = QHBoxLayout()
        self.count_label = QLabel()
        self.count_label.setObjectName("countLabel")
        self.sort_label = QLabel("Tri : cliquez sur l'en-tête d'une colonne")
        self.sort_label.setObjectName("tableHint")
        info.addWidget(self.count_label)
        info.addStretch(1)
        info.addWidget(self.sort_label)
        layout.addLayout(info)

        self.table = A4GuideTableWidget()
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.EditKeyPressed
            | QAbstractItemView.EditTrigger.AnyKeyPressed
        )
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(False)
        # Pas de "...": une cellule trop étroite affiche simplement le début
        # de sa valeur jusqu'à la limite visuelle de la colonne.
        self.table.setTextElideMode(Qt.TextElideMode.ElideNone)
        # La grille native Qt ne sait pas différencier horizontal/vertical.
        # Le delegate MM3 dessine donc lui-même les bordures.
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(True)
        self.table.verticalHeader().setDefaultSectionSize(24)
        # MM3-Core 11.7.70.6 : rendre les N° de lignes franchement lisibles.
        # Sur certains affichages Windows/DPI, le style du header vertical
        # rognait visuellement les chiffres malgré une largeur théorique suffisante.
        row_header = self.table.verticalHeader()
        row_header.setFixedWidth(76)
        row_header.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        row_header.setStyleSheet(
            "QHeaderView { color: #111111; } "
            "QHeaderView::section { color: #111111; padding: 0px 6px; }"
        )
        self.table.setCornerButtonEnabled(True)
        self.table.setSortingEnabled(True)
        # MM3-Core-017.1.4 : menu contextuel sur les lignes du Tableau.
        # Le clic droit sélectionne la fiche visée puis propose Copier/Coller
        # selon la nature de la ligne et le contenu du Presse-papiers MM3.
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._record_context_menu)
        # Dernière ligne virtuelle : aucun N° tant qu'aucune donnée n'est saisie.
        for column_index, field in enumerate(self.visible_fields):
            item = QTableWidgetItem("")
            item.setData(Qt.ItemDataRole.UserRole, -1)
            item.setData(self.OLD_VALUE_ROLE, "")
            item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            if field == "record_number":
                item.setText("")

        header = self.table.horizontalHeader()
        header.setSectionsMovable(True)
        header.setSectionsClickable(True)
        header.setStretchLastSection(False)

        # Autoriser des colonnes extrêmement étroites.
        # 6 px laisse encore une poignée de redimensionnement utilisable,
        # mais permet visuellement 0 à 1 caractère selon la police.
        header.setMinimumSectionSize(6)
        header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        header.customContextMenuRequested.connect(self._header_context_menu)
        header.sectionResized.connect(
            lambda *_: self.table.viewport().update()
        )
        header.sectionMoved.connect(
            lambda *_: self.table.viewport().update()
        )
        self.table.horizontalScrollBar().valueChanged.connect(
            lambda *_: self.table.viewport().update()
        )
        self.table.setItemDelegate(TableEditDelegate(self))
        self.table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        self.table.itemChanged.connect(self._on_table_item_changed)
        self.table.itemSelectionChanged.connect(self._update_open_button)
        self.table.itemSelectionChanged.connect(self._refresh_selection_visuals)
        layout.addWidget(self.table, 1)

        actions = QHBoxLayout()
        hint = QLabel("Double-cliquez une cellule pour la corriger ; N° ouvre la fiche. Flèche BAS valide et passe à la cellule suivante.")
        hint.setObjectName("tableHint")
        actions.addWidget(hint)
        actions.addStretch(1)

        self.undo_button = QPushButton("Défaire")
        self.undo_button.setToolTip(tr("Annuler la dernière modification du Tableau (Ctrl+Z)", self.language))
        self.undo_button.clicked.connect(self.undo_last_action)
        self.redo_button = QPushButton("Refaire")
        self.redo_button.setToolTip(tr("Rétablir la dernière modification annulée (Ctrl+Y)", self.language))
        self.redo_button.clicked.connect(self.redo_last_action)
        # Même repère visuel que dans l’Atelier : rouge soutenu si disponible,
        # rouge très clair si la commande est inactive.
        undo_redo_style = (
            "QPushButton { background:#ef9a9a; border:1px solid #cf6f6f; "
            "border-radius:5px; padding:5px 12px; color:#222; } "
            "QPushButton:disabled { background:#f8dada; border-color:#e7bcbc; color:#8a7777; }"
        )
        self.undo_button.setStyleSheet(undo_redo_style)
        self.redo_button.setStyleSheet(undo_redo_style)
        actions.addWidget(self.undo_button)
        actions.addWidget(self.redo_button)

        self.copy_record_button = QPushButton("Copier la fiche")
        self.copy_record_button.setToolTip(tr("Copier la ou les fiches sélectionnées (Ctrl+C)", self.language))
        self.copy_record_button.setEnabled(False)
        self.copy_record_button.clicked.connect(self.copy_selected_record)

        self.paste_record_button = QPushButton("Coller la fiche")
        self.paste_record_button.setToolTip(tr("Coller la fiche copiée dans la ligne sélectionnée ; si plusieurs fiches ont été copiées, elles sont toutes ajoutées comme nouvelles fiches (Ctrl+V)", self.language))
        self.paste_record_button.clicked.connect(self._paste_shortcut)

        actions.addWidget(self.copy_record_button)
        actions.addWidget(self.paste_record_button)

        self.clear_record_button = QPushButton("Vider")
        self.clear_record_button.setToolTip(tr("Vider la ou les fiches sélectionnées et les passer à l'état Libre", self.language))
        self.clear_record_button.setEnabled(False)
        self.clear_record_button.clicked.connect(self.clear_selected_records)
        self.delete_record_button = QPushButton("Supprimer")
        self.delete_record_button.setToolTip(tr("Supprimer définitivement les fiches Libres et vides situées en fin de collection", self.language))
        self.delete_record_button.setEnabled(False)
        self.delete_record_button.clicked.connect(self.delete_selected_tail_records)
        for _tip_button in (self.copy_record_button, self.paste_record_button, self.clear_record_button, self.delete_record_button):
            _tip_button.setAttribute(Qt.WidgetAttribute.WA_AlwaysShowToolTips, True)
        actions.addWidget(self.clear_record_button)
        actions.addWidget(self.delete_record_button)

        self.open_button = QPushButton("Ouvrir la fiche")
        self.open_button.setObjectName("primaryButton")
        self.open_button.setEnabled(False)
        self.open_button.clicked.connect(self._open_selected_record)
        close_button = QPushButton("Retour")
        close_button.clicked.connect(self.close)
        actions.addWidget(self.open_button)
        actions.addWidget(close_button)
        layout.addLayout(actions)

        self.setCentralWidget(root)

        # Ctrl+C copie désormais la sélection tabulaire vers le Presse-papiers
        # Windows (Excel / Calc / etc.). La copie de fiches MM3 reste disponible
        # par le bouton dédié et par le menu contextuel.
        self.copy_table_shortcut = QShortcut(QKeySequence.StandardKey.Copy, self.table)
        self.copy_table_shortcut.activated.connect(self._copy_shortcut)
        self.paste_record_shortcut = QShortcut(QKeySequence.StandardKey.Paste, self.table)
        self.paste_record_shortcut.activated.connect(self._paste_shortcut)
        self.undo_shortcut = QShortcut(QKeySequence.StandardKey.Undo, self.table)
        self.undo_shortcut.activated.connect(self.undo_last_action)
        self.redo_shortcut = QShortcut(QKeySequence.StandardKey.Redo, self.table)
        self.redo_shortcut.activated.connect(self.redo_last_action)
        self._update_history_buttons()

    def _update_history_buttons(self) -> None:
        if hasattr(self, "undo_button"):
            self.undo_button.setEnabled(bool(self._undo_stack))
        if hasattr(self, "redo_button"):
            self.redo_button.setEnabled(bool(self._redo_stack))

    def _push_history(self, action: dict) -> None:
        if self._history_replaying:
            return
        self._undo_stack.append(copy.deepcopy(action))
        if len(self._undo_stack) > 50:
            del self._undo_stack[:-50]
        self._redo_stack.clear()
        self._update_history_buttons()

    def _snapshot_record(self, record_id: int) -> dict | None:
        record = self.manager.get_record(int(record_id), int(self.collection["id"]))
        if record is None:
            return None
        return {
            "record": copy.deepcopy(record),
            "custom": self.manager.custom_values(int(record_id)),
        }

    def _restore_snapshot(self, snapshot: dict) -> None:
        record = copy.deepcopy(snapshot.get("record") or {})
        record_id = int(record.get("id", 0) or 0)
        if record_id <= 0:
            return
        self.manager.update_record(
            record_id, record, bytes(record.get("photo_data") or b"") or None,
            str(record.get("photo_format", "") or ""),
        )
        self.manager.replace_custom_values(record_id, snapshot.get("custom") or {})

    def undo_last_action(self, *_args) -> None:
        if not self._undo_stack:
            return
        action = self._undo_stack.pop()
        self._history_replaying = True
        try:
            kind = action.get("type")
            if kind in {"paste_new", "create"}:
                for record_id in action.get("created_ids", []):
                    self.manager.delete_record(int(record_id), int(self.collection["id"]))
            elif kind == "clear_many":
                for snapshot in action.get("before", []):
                    self._restore_snapshot(snapshot)
            elif kind in {"replace", "edit"}:
                before = action.get("before")
                if before:
                    self._restore_snapshot(before)
            self._redo_stack.append(action)
            self.refresh_table()
            self.statusBar().showMessage("Dernière modification annulée.", 2500)
        except Exception as exc:
            self._undo_stack.append(action)
            QMessageBox.critical(self, "Défaire impossible", str(exc))
        finally:
            self._history_replaying = False
            self._update_history_buttons()

    def redo_last_action(self, *_args) -> None:
        if not self._redo_stack:
            return
        action = self._redo_stack.pop()
        self._history_replaying = True
        try:
            kind = action.get("type")
            if kind == "paste_new":
                new_ids = []
                for source_record in action.get("sources", []):
                    mapping = self._prepare_destination_custom_fields(source_record)
                    created = self.manager.paste_record_as_new(int(self.collection["id"]), source_record)
                    self._paste_custom_values(int(created["id"]), source_record, mapping)
                    new_ids.append(int(created["id"]))
                action["created_ids"] = new_ids
            elif kind == "create":
                source_record = action.get("source")
                if source_record:
                    mapping = self._prepare_destination_custom_fields(source_record)
                    created = self.manager.paste_record_as_new(int(self.collection["id"]), source_record)
                    self._paste_custom_values(int(created["id"]), source_record, mapping)
                    action["created_ids"] = [int(created["id"])]
            elif kind == "clear_many":
                for record_id in action.get("record_ids", []):
                    self.manager.clear_record_to_free(int(record_id), int(self.collection["id"]))
            elif kind in {"replace", "edit"}:
                after = action.get("after")
                if after:
                    self._restore_snapshot(after)
            self._undo_stack.append(action)
            self.refresh_table()
            self.statusBar().showMessage("Modification rétablie.", 2500)
        except Exception as exc:
            self._redo_stack.append(action)
            QMessageBox.critical(self, "Refaire impossible", str(exc))
        finally:
            self._history_replaying = False
            self._update_history_buttons()

    def closeEvent(self, event) -> None:
        """Même protection pour Retour et pour la croix Windows."""
        if self._confirm_unsaved_view_changes():
            event.accept()
        else:
            event.ignore()

    @staticmethod
    def _html_escape(value) -> str:
        text = "" if value is None else str(value)
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )

    def _current_visual_columns(self) -> list[int]:
        """Colonnes dans l'ordre réellement visible à l'écran."""
        header = self.table.horizontalHeader()
        pairs = []
        for logical in range(self.table.columnCount()):
            if self.table.isColumnHidden(logical):
                continue
            pairs.append((header.visualIndex(logical), logical))
        return [logical for _, logical in sorted(pairs)]

    def _build_current_table_print_document(self, printer: QPrinter) -> QTextDocument:
        """Construit le document à partir de ce que l'utilisateur voit maintenant."""
        style = {**TableLayoutDialog.DEFAULTS, **dict(self.table_layout or {})}
        logical_columns = self._current_visual_columns()
        if not logical_columns:
            raise ValueError("Aucune colonne visible à imprimer.")

        header = self.table.horizontalHeader()
        widths = [max(1, header.sectionSize(col)) for col in logical_columns]

        # Échelle commune écran/impression :
        # la ligne pointillée A4 du Tableau correspond exactement à la largeur
        # imprimable de la page. On ne renormalise donc PLUS les colonnes pour
        # remplir artificiellement 100 % de la feuille.
        page_rect = printer.pageRect(QPrinter.Unit.Point)
        printable_width_points = max(1.0, float(page_rect.width()))
        if isinstance(self.table, A4GuideTableWidget):
            guide_width_pixels = max(
                1.0, float(self.table.a4_printable_width_pixels())
            )
        else:
            dpi = max(72.0, float(self.logicalDpiX()))
            page_mm = 297.0 if style.get("orientation") == "landscape" else 210.0
            guide_width_pixels = max(1.0, (page_mm - 10.0) / 25.4 * dpi)

        points_per_screen_pixel = printable_width_points / guide_width_pixels
        print_widths_points = [
            max(3.0, float(width) * points_per_screen_pixel)
            for width in widths
        ]
        total_print_width_points = max(3.0, sum(print_widths_points))

        header_font = self._html_escape(style["header_font"])
        body_font = self._html_escape(style["body_font"])
        header_size = int(style["header_size"])
        body_size = int(style["body_size"])
        header_weight = "700" if style["header_bold"] else "400"
        body_weight = "700" if style["body_bold"] else "400"
        header_style = "italic" if style["header_italic"] else "normal"
        body_style = "italic" if style["body_italic"] else "normal"
        header_decoration = "underline" if style["header_underline"] else "none"
        body_decoration = "underline" if style["body_underline"] else "none"

        cols_html = "".join(
            f'<col style="width:{width:.3f}pt;">'
            for width in print_widths_points
        )

        ths = []
        for logical in logical_columns:
            item = self.table.horizontalHeaderItem(logical)
            label = item.text() if item is not None else ""
            ths.append(f"<th>{self._html_escape(label)}</th>")

        rows_html = []
        for row in range(self.table.rowCount()):
            cells = []
            for logical in logical_columns:
                item = self.table.item(row, logical)
                value = item.text() if item is not None else ""
                field = (
                    self.visible_fields[logical]
                    if 0 <= logical < len(self.visible_fields)
                    else ""
                )
                align = self.column_alignments.get(field, "left")
                css_align = {
                    "left": "left",
                    "center": "center",
                    "right": "right",
                }.get(align, "left")
                cells.append(
                    f'<td style="text-align:{css_align};">'
                    f"{self._html_escape(value)}</td>"
                )
            rows_html.append("<tr>" + "".join(cells) + "</tr>")

        # Les traits fins seront posés ensuite nativement par Qt.
        html = f"""<html><head><meta charset="utf-8"><style>
        body {{
            margin:0;
            color:{style['body_text']};
            font-family:"{body_font}",Arial,sans-serif;
            font-size:{body_size}pt;
        }}
        table {{
            table-layout:fixed;
            border-collapse:collapse;
        }}
        thead {{ display:table-header-group; }}
        tr {{ page-break-inside:avoid; page-break-after:auto; }}
        th {{
            color:{style['header_text']};
            background:{style['header_bg']};
            font-family:"{header_font}",Arial,sans-serif;
            font-size:{header_size}pt;
            font-weight:{header_weight};
            font-style:{header_style};
            text-decoration:{header_decoration};
            text-align:center;
            vertical-align:middle;
            padding:4px 3px;
            border:0;
            white-space:nowrap;
        }}
        td {{
            color:{style['body_text']};
            background:{style['body_bg']};
            font-family:"{body_font}",Arial,sans-serif;
            font-size:{body_size}pt;
            font-weight:{body_weight};
            font-style:{body_style};
            text-decoration:{body_decoration};
            vertical-align:middle;
            padding:2px 3px;
            border:0;
            white-space:nowrap;
        }}
        </style></head><body>
        <table>
          <colgroup>{cols_html}</colgroup>
          <thead><tr>{''.join(ths)}</tr></thead>
          <tbody>{''.join(rows_html)}</tbody>
        </table>
        </body></html>"""

        document = QTextDocument(self)
        document.setDocumentMargin(5)
        text_option = document.defaultTextOption()
        text_option.setWrapMode(QTextOption.WrapMode.NoWrap)
        document.setDefaultTextOption(text_option)
        document.setHtml(html)

        # Répéter l'en-tête sur les pages suivantes et appliquer les traits
        # via QTextTableCellFormat natif, méthode déjà fiabilisée dans MM3.
        mode = str(style.get("borders") or "all")
        row_width = max(0.0, float(style.get("row_lines", 1)))
        col_width = max(0.0, float(style.get("column_lines", 1)))

        def configure_frame(frame):
            child = frame.begin()
            while not child.atEnd():
                current = child.currentFrame()
                if current is not None:
                    if isinstance(current, QTextTable):
                        try:
                            fmt = current.format()
                            if current.rows() > 1:
                                fmt.setHeaderRowCount(1)

                            # IMPORTANT : les largeurs sont imposées NATIVEMENT
                            # au QTextTable. Le moteur QTextDocument ignore ou
                            # renormalise parfois les <col width=...> HTML.
                            # Ici 1 pixel écran = points_per_screen_pixel points
                            # imprimés, donc le redimensionnement du Tableau
                            # devient réellement visible dans l'aperçu.
                            if current.columns() == len(print_widths_points):
                                fmt.setColumnWidthConstraints([
                                    QTextLength(
                                        QTextLength.Type.FixedLength,
                                        float(width)
                                    )
                                    for width in print_widths_points
                                ])
                            current.setFormat(fmt)

                            rows = current.rows()
                            cols = current.columns()

                            rows_on = mode in {"all", "rows"} and row_width > 0
                            cols_on = mode in {"all", "columns"} and col_width > 0

                            # Bordure de base imposée au QTextTable lui-même.
                            # C'est ce niveau que QPrintPreviewDialog respecte
                            # le plus fiablement lors du rendu.
                            table_fmt = current.format()
                            if mode == "all" and (row_width > 0 or col_width > 0):
                                table_fmt.setBorder(max(row_width, col_width, 1.0))
                                table_fmt.setBorderBrush(QBrush(QColor("#777777")))
                                table_fmt.setCellSpacing(0)
                                table_fmt.setCellPadding(0)
                            else:
                                table_fmt.setBorder(0)
                                table_fmt.setCellSpacing(0)
                                table_fmt.setCellPadding(0)
                            current.setFormat(table_fmt)

                            for r in range(rows):
                                for c in range(cols):
                                    cell = current.cellAt(r, c)
                                    cf = cell.format()

                                    # Nettoyage complet préalable.
                                    cf.setTopBorderStyle(
                                        QTextTableCellFormat.BorderStyle.BorderStyle_None
                                    )
                                    cf.setBottomBorderStyle(
                                        QTextTableCellFormat.BorderStyle.BorderStyle_None
                                    )
                                    cf.setLeftBorderStyle(
                                        QTextTableCellFormat.BorderStyle.BorderStyle_None
                                    )
                                    cf.setRightBorderStyle(
                                        QTextTableCellFormat.BorderStyle.BorderStyle_None
                                    )
                                    cf.setTopBorder(0)
                                    cf.setBottomBorder(0)
                                    cf.setLeftBorder(0)
                                    cf.setRightBorder(0)

                                    if rows_on:
                                        # Un seul trait horizontal par séparation :
                                        # bas de chaque cellule, plus haut de la
                                        # première ligne.
                                        cf.setBottomBorderStyle(
                                            QTextTableCellFormat.BorderStyle.BorderStyle_Solid
                                        )
                                        cf.setBottomBorder(row_width)
                                        cf.setBottomBorderBrush(
                                            QBrush(QColor("#777777"))
                                        )
                                        if r == 0:
                                            cf.setTopBorderStyle(
                                                QTextTableCellFormat.BorderStyle.BorderStyle_Solid
                                            )
                                            cf.setTopBorder(row_width)
                                            cf.setTopBorderBrush(
                                                QBrush(QColor("#777777"))
                                            )

                                    if cols_on:
                                        # Même principe vertical : droite de chaque
                                        # cellule, plus gauche de la première colonne.
                                        cf.setRightBorderStyle(
                                            QTextTableCellFormat.BorderStyle.BorderStyle_Solid
                                        )
                                        cf.setRightBorder(col_width)
                                        cf.setRightBorderBrush(
                                            QBrush(QColor("#777777"))
                                        )
                                        if c == 0:
                                            cf.setLeftBorderStyle(
                                                QTextTableCellFormat.BorderStyle.BorderStyle_Solid
                                            )
                                            cf.setLeftBorder(col_width)
                                            cf.setLeftBorderBrush(
                                                QBrush(QColor("#777777"))
                                            )

                                    cell.setFormat(cf)
                        except Exception:
                            pass
                    configure_frame(current)
                child += 1

        configure_frame(document.rootFrame())

        # Dimension du document = zone imprimable réelle.
        try:
            page_rect = printer.pageRect(QPrinter.Unit.Point)
            document.setPageSize(page_rect.size())
        except Exception:
            pass
        return document

    def _paint_current_table(self, printer: QPrinter) -> None:
        """Dessine directement le Tableau courant sur l'imprimante / aperçu."""
        style = {**TableLayoutDialog.DEFAULTS, **dict(self.table_layout or {})}
        logical_columns = self._current_visual_columns()
        if not logical_columns:
            return

        painter = QPainter(printer)
        if not painter.isActive():
            return

        try:
            page_rect = printer.pageRect(QPrinter.Unit.DevicePixel)
            page_left = int(page_rect.left())
            page_top = int(page_rect.top())
            page_right = int(page_rect.right())
            page_bottom = int(page_rect.bottom())
            page_width = max(1, page_right - page_left + 1)
            page_height = max(1, page_bottom - page_top + 1)

            # Échelle écran -> impression calée sur le repère A4.
            if isinstance(self.table, A4GuideTableWidget):
                screen_a4_px = max(1.0, self.table.a4_printable_width_pixels())
            else:
                screen_a4_px = max(1.0, float(self.table.viewport().width()))
            scale = page_width / screen_a4_px

            # Même marge intérieure qu'à l'écran.
            # 4 pixels écran doivent devenir 4*scale pixels imprimante ;
            # sinon l'aperçu gagne artificiellement de la place et montre
            # davantage de caractères que la Vue Tableau.
            # QTableWidget conserve en pratique une très légère réserve
            # supplémentaire avant de couper le texte. On la reproduit ici :
            # 5 px écran par côté au lieu de 4, puis mise à l'échelle.
            # Cela évite que l'aperçu révèle 1 caractère de plus dans les
            # colonnes extrêmement étroites.
            cell_padding = max(1, int(round(5.0 * scale)))

            header = self.table.horizontalHeader()
            col_widths = [
                max(1, int(round(header.sectionSize(col) * scale)))
                for col in logical_columns
            ]

            # IMPORTANT : aucune normalisation à la largeur de page.
            # Si le tableau est plus étroit, blanc à droite.
            # S'il est plus large que l'A4, il est simplement coupé au bord
            # comme le repère A4 l'indique dans le Tableau.
            x_positions = [page_left]
            for width in col_widths:
                x_positions.append(x_positions[-1] + width)

            # Polices.
            header_font = QFont(
                str(style["header_font"]),
                int(style["header_size"]),
            )
            header_font.setBold(bool(style["header_bold"]))
            header_font.setItalic(bool(style["header_italic"]))
            header_font.setUnderline(bool(style["header_underline"]))

            body_font = QFont(
                str(style["body_font"]),
                int(style["body_size"]),
            )
            body_font.setBold(bool(style["body_bold"]))
            body_font.setItalic(bool(style["body_italic"]))
            body_font.setUnderline(bool(style["body_underline"]))

            painter.setFont(header_font)
            header_metrics = painter.fontMetrics()
            header_h = max(
                22,
                int(round((header_metrics.height() + 10) * 1.0)),
            )

            painter.setFont(body_font)
            body_metrics = painter.fontMetrics()
            body_h = max(
                18,
                int(round((body_metrics.height() + 7) * 1.0)),
            )

            mode = str(style.get("borders") or "all")
            row_w = max(0, int(style.get("row_lines", 1)))
            col_w = max(0, int(style.get("column_lines", 1)))
            rows_on = mode in {"all", "rows"} and row_w > 0
            cols_on = mode in {"all", "columns"} and col_w > 0

            border_color = QColor("#8F9994")
            header_bg = QColor(str(style["header_bg"]))
            header_fg = QColor(str(style["header_text"]))
            body_bg = QColor(str(style["body_bg"]))
            body_fg = QColor(str(style["body_text"]))

            def draw_hline(y, width):
                pen = QPen(border_color)
                pen.setWidth(max(1, int(width)))
                pen.setCosmetic(True)
                painter.setPen(pen)
                painter.drawLine(
                    int(page_left),
                    int(y),
                    int(min(x_positions[-1], page_right)),
                    int(y),
                )

            def draw_vline(x, y1, y2, width):
                if x > page_right:
                    return
                pen = QPen(border_color)
                pen.setWidth(max(1, int(width)))
                pen.setCosmetic(True)
                painter.setPen(pen)
                painter.drawLine(
                    int(x),
                    int(y1),
                    int(x),
                    int(y2),
                )

            def draw_text_cell(rect, text, font, color, align):
                painter.setFont(font)
                painter.setPen(color)
                flags = Qt.AlignmentFlag.AlignVCenter
                if align == "center":
                    flags |= Qt.AlignmentFlag.AlignHCenter
                elif align == "right":
                    flags |= Qt.AlignmentFlag.AlignRight
                else:
                    flags |= Qt.AlignmentFlag.AlignLeft

                # Exactement comme le Tableau : pas de retour à la ligne
                # et pas de points de suspension. Le texte complet est dessiné
                # mais strictement découpé par les limites de la cellule.
                text_rect = rect.adjusted(
                    cell_padding, 0, -cell_padding, 0
                )
                painter.save()
                painter.setClipRect(text_rect)
                painter.drawText(
                    text_rect,
                    int(flags),
                    str(text or ""),
                )
                painter.restore()

            def draw_header(y):
                painter.setFont(header_font)
                for idx, logical in enumerate(logical_columns):
                    x1 = x_positions[idx]
                    x2 = x_positions[idx + 1]
                    if x1 > page_right:
                        break
                    width = min(x2, page_right + 1) - x1
                    if width <= 0:
                        continue
                    rect = self._qt_rect(x1, y, width, header_h)
                    painter.fillRect(rect, header_bg)

                    hitem = self.table.horizontalHeaderItem(logical)
                    label = hitem.text() if hitem is not None else ""
                    draw_text_cell(
                        rect, label, header_font, header_fg, "center"
                    )

                # Grille d'en-tête : chaque séparation n'est tracée qu'une fois.
                if rows_on:
                    draw_hline(y, row_w)
                    draw_hline(y + header_h, row_w)
                if cols_on:
                    visible_x = [x for x in x_positions if x <= page_right]
                    if not visible_x or visible_x[-1] < min(x_positions[-1], page_right):
                        visible_x.append(min(x_positions[-1], page_right))
                    for x in visible_x:
                        draw_vline(x, y, y + header_h, col_w)
                return y + header_h

            # Nombre de lignes imprimables par page, en tenant compte de
            # l'en-tête qui est répété sur chaque page.
            usable_body_height = max(1, page_bottom - page_top + 1 - header_h)
            rows_per_page = max(1, usable_body_height // body_h)
            total_rows = self.table.rowCount()
            total_pages = max(1, (total_rows + rows_per_page - 1) // rows_per_page)

            # La boîte d'impression Windows renseigne fromPage()/toPage()
            # quand l'utilisateur choisit "Pages". En aperçu normal ces
            # valeurs sont nulles : on affiche alors toutes les pages.
            try:
                first_page = int(printer.fromPage() or 0)
                last_page = int(printer.toPage() or 0)
            except Exception:
                first_page = 0
                last_page = 0

            if first_page <= 0:
                first_page = 1
            if last_page <= 0:
                last_page = total_pages

            first_page = max(1, min(first_page, total_pages))
            last_page = max(first_page, min(last_page, total_pages))

            rendered_page = 0
            for page_no in range(first_page, last_page + 1):
                if rendered_page > 0:
                    printer.newPage()
                rendered_page += 1

                y = page_top
                y = draw_header(y)

                start_row = (page_no - 1) * rows_per_page
                end_row = min(total_rows, start_row + rows_per_page)

                for row in range(start_row, end_row):
                    row_top = y
                    row_bottom = y + body_h

                    for idx, logical in enumerate(logical_columns):
                        x1 = x_positions[idx]
                        x2 = x_positions[idx + 1]
                        if x1 > page_right:
                            break
                        width = min(x2, page_right + 1) - x1
                        if width <= 0:
                            continue

                        rect = self._qt_rect(x1, row_top, width, body_h)
                        painter.fillRect(rect, body_bg)

                        item = self.table.item(row, logical)
                        value = item.text() if item is not None else ""
                        field = (
                            self.visible_fields[logical]
                            if 0 <= logical < len(self.visible_fields)
                            else ""
                        )
                        align = self.column_alignments.get(field, "left")
                        draw_text_cell(
                            rect, value, body_font, body_fg, align
                        )

                    if rows_on:
                        draw_hline(row_bottom, row_w)

                    if cols_on:
                        visible_x = [x for x in x_positions if x <= page_right]
                        if not visible_x or visible_x[-1] < min(x_positions[-1], page_right):
                            visible_x.append(min(x_positions[-1], page_right))
                        for x in visible_x:
                            draw_vline(x, row_top, row_bottom, col_w)

                    y = row_bottom

        finally:
            painter.end()

    @staticmethod
    def _qt_rect(x: int, y: int, width: int, height: int):
        from PySide6.QtCore import QRect
        return QRect(int(x), int(y), int(width), int(height))

    def print_current_table(self) -> None:
        """Aperçu puis impression Windows/PDF du Tableau affiché."""
        if self.table.rowCount() <= 0:
            QMessageBox.information(
                self,
                "Imprimer le Tableau",
                "Le Tableau ne contient aucune ligne à imprimer.",
            )
            return
        if not self._current_visual_columns():
            QMessageBox.information(
                self,
                "Imprimer le Tableau",
                "Aucune colonne n'est actuellement visible.",
            )
            return

        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setDocName(f"Tableau — {collection_display_name(self.collection, self.language)}")
        landscape = (
            str(self.table_layout.get("orientation") or "portrait") == "landscape"
        )
        printer.setPageOrientation(
            QPageLayout.Orientation.Landscape
            if landscape
            else QPageLayout.Orientation.Portrait
        )
        try:
            page_layout = printer.pageLayout()
            page_layout.setMargins(QMarginsF(5.0, 5.0, 5.0, 5.0))
            printer.setPageLayout(page_layout)
        except Exception:
            pass

        preview = QPrintPreviewDialog(printer, self)
        preview.setWindowTitle(
            f"Aperçu avant impression — Tableau — {collection_display_name(self.collection, self.language)}"
        )
        preview.resize(1100, 780)

        preview_widget = preview.findChild(QPrintPreviewWidget)
        if preview_widget is not None:
            preview_widget.setZoomMode(QPrintPreviewWidget.ZoomMode.FitToWidth)
            preview_widget.setZoomFactor(1.0)

        translations = {
            "Print": "Imprimer",
            "Page setup": "Mise en page",
            "Page Setup": "Mise en page",
            "Fit width": "Ajuster à la largeur",
            "Fit page": "Ajuster à la page",
            "Zoom in": "Zoom avant",
            "Zoom out": "Zoom arrière",
            "Portrait": "Portrait",
            "Landscape": "Paysage",
            "Single page": "Une page",
            "Facing pages": "Pages en vis-à-vis",
            "All pages": "Toutes les pages",
            "First page": "Première page",
            "Previous page": "Page précédente",
            "Next page": "Page suivante",
            "Last page": "Dernière page",
        }

        for action in preview.findChildren(QAction):
            text = action.text().replace("&", "")
            tip = action.toolTip().replace("&", "")
            if text in translations:
                action.setText(translations[text])
            if tip in translations:
                action.setToolTip(translations[tip])

        for button in preview.findChildren(QToolButton):
            text = button.text().replace("&", "")
            tip = button.toolTip().replace("&", "")
            original_text = text
            original_tip = tip
            if text in translations:
                button.setText(translations[text])
            if tip in translations:
                button.setToolTip(translations[tip])

            if preview_widget is not None:
                marker = (original_text + " " + original_tip).lower()
                if "zoom in" in marker:
                    button.clicked.connect(preview_widget.zoomIn)
                    button.setEnabled(True)
                elif "zoom out" in marker:
                    button.clicked.connect(preview_widget.zoomOut)
                    button.setEnabled(True)

        if preview_widget is not None:
            zoom_combo = None
            for combo in preview.findChildren(QComboBox):
                texts = [combo.itemText(i) for i in range(combo.count())]
                if any("%" in str(value) for value in texts):
                    zoom_combo = combo
                    break

            if zoom_combo is not None:
                zoom_combo.setEditable(True)
                zoom_combo.setEnabled(True)

                def apply_zoom_percent(text):
                    raw = str(text or "").replace("%", "").replace(",", ".").strip()
                    try:
                        percent = float(raw)
                    except ValueError:
                        return
                    percent = max(10.0, min(500.0, percent))
                    preview_widget.setZoomMode(
                        QPrintPreviewWidget.ZoomMode.CustomZoom
                    )
                    preview_widget.setZoomFactor(percent / 100.0)

                zoom_combo.currentTextChanged.connect(apply_zoom_percent)
                if zoom_combo.lineEdit() is not None:
                    zoom_combo.lineEdit().editingFinished.connect(
                        lambda c=zoom_combo:
                            apply_zoom_percent(c.currentText())
                    )

        # Aperçu, imprimante physique ou PDF : un seul moteur QPainter.
        preview.paintRequested.connect(self._paint_current_table)
        preview.exec()

    def _table_layout_key(self) -> str:
        return str(int(self.collection["id"]))

    def _load_table_layout(self) -> None:
        self.table_layout = dict(TableLayoutDialog.DEFAULTS)
        self.column_alignments = {}
        try:
            if not self.table_layout_file.exists():
                return
            data = json.loads(self.table_layout_file.read_text(encoding="utf-8"))
            entry = dict(data.get("collections", {}).get(self._table_layout_key(), {}) or {})
            style = entry.get("style")
            if isinstance(style, dict):
                self.table_layout.update(style)
            aligns = entry.get("column_alignments")
            if isinstance(aligns, dict):
                self.column_alignments = {
                    str(k): str(v) for k, v in aligns.items()
                    if str(v) in {"left", "center", "right"}
                }
        except (OSError, ValueError, TypeError):
            self.table_layout = dict(TableLayoutDialog.DEFAULTS)
            self.column_alignments = {}

    def _write_table_layout(self) -> None:
        self.table_layout_file.parent.mkdir(parents=True, exist_ok=True)
        data = {"collections": {}}
        try:
            if self.table_layout_file.exists():
                existing = json.loads(self.table_layout_file.read_text(encoding="utf-8"))
                if isinstance(existing, dict):
                    data = existing
        except (OSError, ValueError, TypeError):
            data = {"collections": {}}
        data.setdefault("collections", {})[self._table_layout_key()] = {
            "style": dict(self.table_layout),
            "column_alignments": dict(self.column_alignments),
        }
        tmp = self.table_layout_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.table_layout_file)

    def open_table_layout(self) -> None:
        dialog = TableLayoutDialog(self.table_layout, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.table_layout = dialog.result_values()
        self._write_table_layout()
        self._apply_table_layout()

    def _apply_table_layout(self) -> None:
        if not hasattr(self, "table"):
            return
        style = {**TableLayoutDialog.DEFAULTS, **dict(self.table_layout or {})}

        header_font = QFont(str(style["header_font"]), int(style["header_size"]))
        header_font.setBold(bool(style["header_bold"]))
        header_font.setItalic(bool(style["header_italic"]))
        header_font.setUnderline(bool(style["header_underline"]))
        header = self.table.horizontalHeader()
        header.setFont(header_font)
        header.setDefaultAlignment(
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
        )
        header.setStyleSheet(
            "QHeaderView::section {"
            f"color:{style['header_text']};"
            f"background:{style['header_bg']};"
            "padding:4px;border:1px solid #aab5b0;"
            "}"
        )

        body_font = QFont(str(style["body_font"]), int(style["body_size"]))
        body_font.setBold(bool(style["body_bold"]))
        body_font.setItalic(bool(style["body_italic"]))
        body_font.setUnderline(bool(style["body_underline"]))

        for row in range(self.table.rowCount()):
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                if item is None:
                    continue
                item.setFont(body_font)
                item.setForeground(QColor(str(style["body_text"])))
                item.setBackground(QColor(str(style["body_bg"])))

                field = (
                    self.visible_fields[col]
                    if 0 <= col < len(self.visible_fields)
                    else ""
                )
                align = self.column_alignments.get(field, "left")
                if align == "center":
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
                    )
                elif align == "right":
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                else:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                    )

        # Les traits sont rendus par TableEditDelegate.
        self.table.setShowGrid(False)

        # Les largeurs de colonnes restent entièrement manuelles.
        # Pas de retour à la ligne dans les données : la hauteur dépend donc
        # uniquement de la police choisie, comme dans les États.
        metrics = QFontMetrics(body_font)
        row_height = max(14, int(metrics.height()) + 6)

        vertical_header = self.table.verticalHeader()
        vertical_header.setMinimumSectionSize(6)
        vertical_header.setDefaultSectionSize(row_height)

        for row in range(self.table.rowCount()):
            self.table.setRowHeight(row, row_height)

        self.table.viewport().update()

        if isinstance(self.table, A4GuideTableWidget):
            self.table.set_a4_guide(
                bool(style.get("show_a4", True)),
                str(style.get("orientation") or "portrait"),
            )

    def _header_context_menu(self, pos) -> None:
        header = self.table.horizontalHeader()
        logical = header.logicalIndexAt(pos)
        if logical < 0 or logical >= len(self.visible_fields):
            return
        field = self.visible_fields[logical]
        current = self.column_alignments.get(field, "left")

        menu = QMenu(self)
        title_action = QAction("Alignement de la colonne", menu)
        title_action.setEnabled(False)
        menu.addAction(title_action)
        menu.addSeparator()

        group = []
        for label, value in (
            ("Gauche", "left"),
            ("Centré", "center"),
            ("Droite", "right"),
        ):
            action = QAction(label, menu)
            action.setCheckable(True)
            action.setChecked(current == value)
            action.triggered.connect(
                lambda _checked=False, f=field, v=value:
                    self._set_column_alignment(f, v)
            )
            menu.addAction(action)
            group.append(action)

        menu.exec(header.mapToGlobal(pos))

    def _set_column_alignment(self, field: str, alignment: str) -> None:
        if alignment not in {"left", "center", "right"}:
            return
        self.column_alignments[str(field)] = alignment
        self._write_table_layout()
        self._apply_table_layout()

    def _collection_views_key(self) -> str:
        return str(int(self.collection["id"]))

    def _load_saved_views(self) -> None:
        db = self.startup.database.database_path
        entry = load_collection_models(db, self.collection["id"], "tableau")
        if not entry.get("views"):
            legacy = self._located_legacy_views()
            if legacy:
                entry = {"views": legacy}
                save_collection_models(db, self.collection["id"], "tableau", entry)
        views = entry.get("views", {})
        self.saved_views = {str(name): state for name, state in views.items() if isinstance(state, dict)} if isinstance(views, dict) else {}

    def _located_legacy_views(self):
        try:
            data = json.loads(self.views_file.read_text(encoding="utf-8"))
            models = data.get("collections", {}).get(self._collection_views_key(), {}).get("views", {})
            if not isinstance(models, dict): return {}
            with sqlite3.connect(self.startup.database.database_path) as con:
                names = {row[0] for row in con.execute(
                    "SELECT name FROM saved_model_locations WHERE collection_id=? AND kind=?",
                    (int(self.collection["id"]), "tableau"))}
            return {name: state for name, state in models.items() if name in names and isinstance(state, dict)}
        except (OSError, ValueError, TypeError, KeyError, sqlite3.Error):
            return {}

    def _write_saved_views(self) -> None:
        save_collection_models(self.startup.database.database_path,
                               self.collection["id"], "tableau", {"views": self.saved_views})

    def _manage_view_folders(self) -> None:
        manage_folders(self, self.startup.database.database_path, int(self.collection["id"]),
                       "tableau", self.saved_views, self._refresh_views_combo)

    def _view_folder(self, name: str) -> str:
        return model_folders.folder_for(self.startup.database.database_path,
                                        int(self.collection["id"]), "tableau", name)

    def _refresh_views_combo(self, select_name: str | None = None) -> None:
        if not hasattr(self, "views_combo"):
            return
        wanted = select_name if select_name is not None else self.current_view_name
        self.views_combo.blockSignals(True)
        self.views_combo.clear()
        if self.query_criteria:
            self.views_combo.addItem(tr(self.QUERY_VIEW_LABEL, self.language), self.QUERY_VIEW_SENTINEL)
        else:
            self.views_combo.addItem(tr("— Vue actuelle —", self.language), None)
        for name in sorted(self.saved_views, key=str.casefold):
            folder = self._view_folder(name)
            self.views_combo.addItem(name, name)
        if self.query_criteria and not wanted:
            index = self.views_combo.findData(self.QUERY_VIEW_SENTINEL)
        else:
            index = self.views_combo.findData(wanted) if wanted else 0
        self.views_combo.setCurrentIndex(index if index >= 0 else 0)
        self.views_combo.blockSignals(False)
        self.current_view_name = wanted if wanted in self.saved_views else None
        self._update_view_buttons()

    def _refresh_active_model_name(self) -> None:
        name = str(getattr(self, "active_model_name", "") or self.current_view_name or "Vue actuelle").strip()
        if hasattr(self, "model_name_label"):
            shown_name = tr(name, self.language)
            if str(self.language or "fr").lower().startswith("de") and name in ("Vue actuelle", "Current view"):
                shown_name = "Aktuelle Ansicht"
            prefix = tr("Modèle actif :", self.language)
            self.model_name_label.setText(f"{prefix} {shown_name}")
        try:
            self.setWindowTitle(f"Tableau — {collection_display_name(self.collection, self.language)} — {name}")
        except Exception:
            pass

    def _update_view_buttons(self) -> None:
        if self.current_view_name:
            self.active_model_name = self.current_view_name
        self._refresh_active_model_name()
        active = bool(self.current_view_name and self.current_view_name in self.saved_views)
        if hasattr(self, "update_view_button"):
            self.update_view_button.setEnabled(active)
            self.rename_view_button.setEnabled(active)
            self.delete_view_button.setEnabled(active)

    def _visual_fields(self) -> list[str]:
        if not hasattr(self, "table") or self.table.columnCount() != len(self.visible_fields):
            return list(self.visible_fields)
        header = self.table.horizontalHeader()
        ordered: list[str] = []
        for visual_index in range(header.count()):
            logical_index = header.logicalIndex(visual_index)
            if 0 <= logical_index < len(self.visible_fields):
                ordered.append(self.visible_fields[logical_index])
        return ordered or list(self.visible_fields)

    def _effective_filters(self) -> list[dict[str, str]]:
        filters = [dict(item) for item in self.active_filters]
        current = self._current_filter()
        if current is not None:
            filters.append(current)
        return filters

    def _capture_view_state(self) -> dict:
        visual_fields = self._visual_fields()
        widths: dict[str, int] = {}
        header = self.table.horizontalHeader()
        for logical_index, field in enumerate(self.visible_fields):
            widths[field] = int(header.sectionSize(logical_index))

        sort_field = None
        sort_order = "asc"
        sort_section = header.sortIndicatorSection()
        if 0 <= sort_section < len(self.visible_fields):
            sort_field = self.visible_fields[sort_section]
            sort_order = (
                "desc"
                if header.sortIndicatorOrder() == Qt.SortOrder.DescendingOrder
                else "asc"
            )

        return {
            "fields": visual_fields,
            "widths": widths,
            "filters": self._effective_filters(),
            "sort": {"field": sort_field, "order": sort_order},

            # Une Vue issue d'une requête doit rester cette même Vue quand on
            # la rouvre plus tard, et non revenir à toute la collection.
            "query": [
                dict(item) for item in self.query_criteria
                if isinstance(item, dict)
            ],

            # La présentation fait désormais partie intégrante de la Vue.
            "layout": dict(self.table_layout),
            "column_alignments": dict(self.column_alignments),
        }

    def _mark_view_clean(self) -> None:
        self._view_baseline_state = self._capture_view_state()

    def _view_has_unsaved_changes(self) -> bool:
        if self._view_baseline_state is None:
            return False
        return self._view_baseline_state != self._capture_view_state()

    def _restore_views_combo_to_current(self) -> None:
        self._loading_view = True
        try:
            if self.current_view_name:
                index = self.views_combo.findData(self.current_view_name)
            elif self.query_criteria:
                index = self.views_combo.findData(self.QUERY_VIEW_SENTINEL)
            else:
                index = self.views_combo.findData(None)
            if index >= 0:
                self.views_combo.setCurrentIndex(index)
        finally:
            self._loading_view = False

    def _confirm_unsaved_view_changes(self) -> bool:
        if not self._view_has_unsaved_changes():
            return True

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle("Modifications non enregistrées")

        if self.current_view_name and self.current_view_name in self.saved_views:
            box.setText(f'La vue « {self.current_view_name} » a été modifiée.')
            box.setInformativeText(
                "Voulez-vous enregistrer ces modifications avant de quitter ?"
            )
            save_same = box.addButton(
                "Enregistrer", QMessageBox.ButtonRole.AcceptRole
            )
            save_as = box.addButton(
                "Enregistrer sous…", QMessageBox.ButtonRole.ActionRole
            )
        else:
            box.setText("Cette vue n’a pas encore été enregistrée.")
            box.setInformativeText(
                "Voulez-vous l’enregistrer avant de quitter ?"
            )
            save_same = None
            save_as = box.addButton(
                "Enregistrer sous…", QMessageBox.ButtonRole.AcceptRole
            )

        discard = box.addButton(
            "Ne pas enregistrer", QMessageBox.ButtonRole.DestructiveRole
        )
        cancel = box.addButton(
            "Annuler", QMessageBox.ButtonRole.RejectRole
        )
        box.setDefaultButton(save_same or save_as)
        translate_widget_tree(box, self.language)
        box.exec()

        clicked = box.clickedButton()
        if clicked is cancel:
            return False
        if clicked is discard:
            return True
        if save_same is not None and clicked is save_same:
            self.update_current_view()
            return not self._view_has_unsaved_changes()
        if clicked is save_as:
            return self.save_view_as()
        return False

    def open_view_from_library(self) -> bool:
        root = library_root(self.startup.workspace.root_path, "tableau") if hasattr(self.startup.workspace, "root_path") else library_root(self.startup.workspace.settings_path.parent, "tableau")
        filename = choose_model_open_path(self, root, "Modèles de Tableaux")
        if not filename: return False
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        QApplication.processEvents()
        try:
            envelope = read_model(filename, expected_kind="tableau")
            state = resolve_model_fields(self, envelope, self.model_manager, int(self.collection["id"]), "tableau")
            if state is None:
                return False
            self._custom_field_defs = self.model_manager.custom_field_map(int(self.collection["id"]))
            self.COLUMNS = self._collection_columns()
            self.clear_query(refresh=False, clear_query_filter=False)
            self.active_model_name = Path(filename).stem
            self._apply_saved_view(Path(filename).stem, state); self.refresh_table(); self._mark_view_clean(); self._refresh_active_model_name()
        except Exception as exc:
            QMessageBox.critical(self, "Ouverture impossible", str(exc)); return False
        finally:
            QApplication.restoreOverrideCursor()
        return True

    def save_view_to_library(self) -> bool:
        state = self._capture_view_state()
        root = library_root(self.startup.workspace.root_path, "tableau") if hasattr(self.startup.workspace, "root_path") else library_root(self.startup.workspace.settings_path.parent, "tableau")
        default_name = self.current_view_name or "Modèle de tableau"
        filename = choose_model_save_path(self, root, default_name, "Modèles de Tableaux")
        if not filename:
            return False
        try:
            manifest = build_field_manifest(self.model_manager, int(self.collection["id"]), collect_model_field_keys("tableau", state))
            write_model(filename, kind="tableau", name=Path(filename).stem, source_collection=str(self.collection.get("name") or ""), payload=state, field_manifest=manifest)
        except Exception as exc:
            QMessageBox.critical(self, "Enregistrement impossible", str(exc)); return False
        self.active_model_name = Path(filename).stem
        self._refresh_active_model_name()
        QMessageBox.information(self, "Modèle de Tableau", "Le modèle a été enregistré dans la bibliothèque Modèles de Tableaux.")
        self._mark_view_clean()
        return True

    def save_view_as(self) -> bool:
        name_dialog = QInputDialog(self)
        name_dialog.setWindowTitle("Enregistrer la vue")
        name_dialog.setLabelText("Nom de la vue :")
        name_dialog.setOkButtonText("OK")
        name_dialog.setCancelButtonText("Annuler")
        ok = name_dialog.exec() == QDialog.DialogCode.Accepted
        name = str(name_dialog.textValue() or "").strip()
        if not ok:
            return False
        if not name:
            return False
        if name.casefold() == self.QUERY_VIEW_LABEL.casefold():
            QMessageBox.information(
                self,
                "Nom réservé",
                f'« {self.QUERY_VIEW_LABEL} » est un nom réservé aux résultats temporaires de requête.\n'
                "Choisissez un autre nom pour enregistrer cette vue.",
            )
            return False
        if name in self.saved_views:
            answer = QMessageBox.question(
                self,
                "Vue existante",
                f'La vue « {name} » existe déjà. Voulez-vous la remplacer ?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return False
        folder = choose_folder(self, self.startup.database.database_path, int(self.collection["id"]),
                               "tableau", self._view_folder(name))
        if folder is None: return False
        self.saved_views[name] = self._capture_view_state()
        model_folders.assign(self.startup.database.database_path, int(self.collection["id"]), "tableau", name, folder)
        self._write_saved_views()
        self.current_view_name = name
        self._refresh_views_combo(name)
        self._mark_view_clean()
        return True

    def update_current_view(self) -> None:
        name = self.current_view_name
        if not name or name not in self.saved_views:
            return
        folder = choose_folder(self, self.startup.database.database_path, int(self.collection["id"]),
                               "tableau", self._view_folder(name))
        if folder is None: return
        self.saved_views[name] = self._capture_view_state()
        model_folders.assign(self.startup.database.database_path, int(self.collection["id"]), "tableau", name, folder)
        self._write_saved_views()
        self._refresh_views_combo(name)
        self._mark_view_clean()

    def rename_current_view(self) -> None:
        old_name = self.current_view_name
        if not old_name or old_name not in self.saved_views:
            return
        rename_dialog = QInputDialog(self)
        rename_dialog.setWindowTitle("Renommer la vue")
        rename_dialog.setLabelText("Nouveau nom :")
        rename_dialog.setTextValue(old_name)
        rename_dialog.setOkButtonText("OK")
        rename_dialog.setCancelButtonText("Annuler")
        ok = rename_dialog.exec() == QDialog.DialogCode.Accepted
        name = str(rename_dialog.textValue() or "").strip()
        if not ok:
            return
        if not name or name == old_name:
            return
        if name.casefold() == self.QUERY_VIEW_LABEL.casefold():
            QMessageBox.information(
                self,
                "Nom réservé",
                f'« {self.QUERY_VIEW_LABEL} » est un nom réservé aux résultats temporaires de requête.\n'
                "Choisissez un autre nom.",
            )
            return
        if name in self.saved_views:
            QMessageBox.information(
                self,
                "Nom déjà utilisé",
                f'Une vue nommée « {name} » existe déjà.',
            )
            return
        self.saved_views[name] = self.saved_views.pop(old_name)
        model_folders.rename_item(self.startup.database.database_path, int(self.collection["id"]), "tableau", old_name, name)
        self._write_saved_views()
        self.current_view_name = name
        self._refresh_views_combo(name)
        self._mark_view_clean()

    def delete_current_view(self) -> None:
        name = self.current_view_name
        if not name or name not in self.saved_views:
            return
        answer = QMessageBox.question(
            self,
            "Supprimer cette vue",
            f'Supprimer la vue enregistrée « {name} » ?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.saved_views.pop(name, None)
        model_folders.delete_item(self.startup.database.database_path, int(self.collection["id"]), "tableau", name)
        self._write_saved_views()
        self.current_view_name = None
        self._refresh_views_combo(None)

    def _on_view_selected(self, _index: int) -> None:
        if self._loading_view:
            return
        name = self.views_combo.currentData()

        if not self._confirm_unsaved_view_changes():
            self._restore_views_combo_to_current()
            return

        if name == self.QUERY_VIEW_SENTINEL:
            self.current_view_name = None
            self._update_view_buttons()
            self._mark_view_clean()
            return
        if not name:
            self.current_view_name = None
            self._update_view_buttons()
            self._mark_view_clean()
            return
        state = self.saved_views.get(str(name))
        if not isinstance(state, dict):
            return
        # Une Vue enregistrée est autonome : quitter d'abord le résultat
        # temporaire, puis restaurer sa propre requête éventuelle, ses filtres,
        # sa présentation et enfin recalculer ses données.
        self.clear_query(refresh=False, clear_query_filter=False)
        self._apply_saved_view(str(name), state)
        self.refresh_table()
        self._mark_view_clean()

    def _apply_saved_view(self, name: str, state: dict) -> None:
        available = {field for _label, field in self.COLUMNS}
        fields = [field for field in state.get("fields", []) if field in available]
        if "record_number" not in fields:
            fields.insert(0, "record_number")
        if not fields:
            fields = list(self.DEFAULT_FIELDS)

        self._loading_view = True
        try:
            self.current_view_name = name
            self.visible_fields = fields

            # Requête d'origine : absente dans les anciennes Vues, donc []
            # pour compatibilité totale avec les définitions existantes.
            saved_query = state.get("query", [])
            self.query_criteria = [
                dict(item)
                for item in saved_query
                if isinstance(item, dict)
                and item.get("field") in available
            ]

            self.active_filters = [
                dict(item)
                for item in state.get("filters", [])
                if isinstance(item, dict) and item.get("field") in available
            ]

            # Présentation propre à la Vue si elle existe.
            saved_layout = state.get("layout")
            if isinstance(saved_layout, dict):
                self.table_layout = {
                    **TableLayoutDialog.DEFAULTS,
                    **saved_layout,
                }

            saved_alignments = state.get("column_alignments")
            if isinstance(saved_alignments, dict):
                self.column_alignments = {
                    str(field): str(value)
                    for field, value in saved_alignments.items()
                    if field in available
                    and str(value) in {"left", "center", "right"}
                }
            self.filter_value.blockSignals(True)
            self.filter_value.clear()
            self.filter_value.blockSignals(False)
            self._widths_initialized = False
            self._refresh_filter_fields()
            self._populate_table(self._filtered_records())

            widths = state.get("widths", {})
            header = self.table.horizontalHeader()
            for logical_index, field in enumerate(self.visible_fields):
                try:
                    width = int(widths.get(field, 82 if field == "record_number" else self.STANDARD_WIDTH))
                except (TypeError, ValueError):
                    width = 82 if field == "record_number" else self.STANDARD_WIDTH
                # Même plancher que la Vue Tableau actuelle : une Vue
                # enregistrée peut conserver une colonne presque fermée.
                header.resizeSection(logical_index, max(6, width))
            self._widths_initialized = True

            sort = state.get("sort", {}) if isinstance(state.get("sort"), dict) else {}
            sort_field = sort.get("field")
            if sort_field in self.visible_fields:
                logical_index = self.visible_fields.index(sort_field)
                order = (
                    Qt.SortOrder.DescendingOrder
                    if sort.get("order") == "desc"
                    else Qt.SortOrder.AscendingOrder
                )
                self.table.sortItems(logical_index, order)

            self._apply_table_layout()
            self._update_query_banner()
            self._update_filter_summary()
        finally:
            self._loading_view = False
        self._refresh_views_combo(name)

    def _apply_style(self) -> None:
        theme = collection_theme(self.startup.database.database_path, self.collection)
        self.setStyleSheet(f"""
        #tableRoot {{ background: {theme['gradient']}; color: #24332B; }}
        #tableTitle {{ font-size: 24px; font-weight: 700; }}
        #tableSubtitle, #tableHint {{ color: #607068; }}
        #countLabel {{ font-weight: 650; }}
        #filterBox {{ background: {theme['panel']}; border: 1px solid {theme['border']}; border-radius: 7px; }}
        #filterTitle {{ font-weight: 650; }}
        #filtersSummary {{ color: #607068; }}
        QLineEdit, QComboBox {{ background: white; color: #24332B; border: 1px solid {theme['border']}; border-radius: 6px; padding: 6px 8px; min-height: 22px; }}
        QTableWidget {{ background: white; alternate-background-color: #F5F8F6; border: 1px solid {theme['border']}; border-radius: 7px; gridline-color: #D9E2DD; }}
        QTableWidget::item {{ padding: 5px; }}
        /* 11.7.70.11 : sélection bien visible sans remplacer l'en-tête natif. */
        QTableWidget::item:selected {{ background: #B8CCC1; color: #111111; }}
        QHeaderView::section {{ background: {theme['header']}; color: #24332B; border: none; border-right: 1px solid {theme['border']}; padding: 7px; font-weight: 650; }}
        QTableCornerButton::section {{
            background: #D7DEDA;
            border: 1px solid #24332B;
            border-radius: 0px;
        }}
        QPushButton {{ background: white; color: #24332B; border: 1px solid {theme['border']}; border-radius: 7px; padding: 8px 14px; min-height: 22px; }}
        QPushButton:hover {{ background: {theme['hover']}; }}
        QPushButton:disabled {{ color: #98A39D; background: #F3F5F4; }}
        #queryBanner {{ background: {theme['panel2']}; border: 1px solid {theme['border']}; border-radius: 6px; }}
        #queryLabel {{ color: #24332B; font-weight: 600; }}
        #primaryButton {{ background: #496C5B; color: white; border-color: #496C5B; }}
        #primaryButton:hover {{ background: #3C5B4C; }}
        """)

    def _refresh_selection_visuals(self) -> None:
        """Colore le N° de ligne des lignes sélectionnées, sans modifier les événements natifs.

        Le QHeaderView d'origine est conservé : sélection souris, redimensionnement
        et double-clic de remise à hauteur restent donc ceux de Qt.
        """
        try:
            selected_rows = {idx.row() for idx in self.table.selectionModel().selectedIndexes()}
            for row in range(self.table.rowCount()):
                item = self.table.verticalHeaderItem(row)
                if item is None:
                    item = QTableWidgetItem(str(row + 1))
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.table.setVerticalHeaderItem(row, item)
                if row in selected_rows:
                    item.setBackground(QBrush(QColor("#B8CCC1")))
                    item.setForeground(QBrush(QColor("#111111")))
                else:
                    item.setBackground(QBrush())
                    item.setForeground(QBrush(QColor("#111111")))
            self.table.verticalHeader().viewport().update()
        except Exception:
            pass

    @staticmethod
    def _safe_table_calc_eval(expression: str):
        tree = ast.parse(expression, mode="eval")
        ops = {
            ast.Add: lambda a, b: a + b,
            ast.Sub: lambda a, b: a - b,
            ast.Mult: lambda a, b: a * b,
            ast.Div: lambda a, b: a / b,
        }
        def ev(node):
            if isinstance(node, ast.Expression):
                return ev(node.body)
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float, str)):
                return node.value
            if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
                value = ev(node.operand)
                return value if isinstance(node.op, ast.UAdd) else -value
            if isinstance(node, ast.BinOp) and type(node.op) in ops:
                return ops[type(node.op)](ev(node.left), ev(node.right))
            raise ValueError("Formule non autorisée")
        return ev(tree)

    @staticmethod
    def _table_calc_source_value(record: dict, key: str):
        text = str(record.get(str(key), "") or "").strip()
        if not text:
            return 0.0
        cleaned = re.sub(r"[^0-9,\.\-+]", "", text.replace("\u202f", "").replace(" ", ""))
        cleaned = cleaned.replace(",", ".")
        try:
            return float(cleaned)
        except Exception:
            return text

    def _calculated_table_value(self, record: dict, field: str, definition: dict) -> str:
        try:
            formula = str(definition.get("calculation_formula") or "")
            if not formula:
                return ""
            expression = re.sub(
                r"\{([^{}]+)\}",
                lambda m: repr(self._table_calc_source_value(record, m.group(1))),
                formula,
            )
            value = self._safe_table_calc_eval(normalize_calculation_formula(expression))
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                mode = str(definition.get("calculation_format") or "truncate2")
                if mode == "round":
                    result = str(int(math.floor(value + 0.5)) if value >= 0 else int(math.ceil(value - 0.5)))
                elif mode == "truncate0":
                    result = str(math.trunc(value))
                else:
                    result = f"{math.trunc(value * 100) / 100:.2f}".replace(".", ",")
                style = self._field_styles_cache.get(str(field), {}) if isinstance(self._field_styles_cache, dict) else {}
                suffix = str(style.get("result_suffix") or "").strip() if isinstance(style, dict) else ""
                return result + (" " + suffix if suffix else "")
            return str(value)
        except Exception:
            return ""

    @staticmethod
    def _normalize_table_date(value: str, display_format: str) -> str:
        raw = str(value or "").strip()
        if not raw:
            return ""
        cleaned = raw.replace("-", "/").replace(".", "/")
        parsed = None
        for fmt in ("%d/%m/%Y", "%d/%m/%y", "%d%m%Y", "%d%m%y", "%Y/%m/%d"):
            try:
                parsed = datetime.strptime(cleaned, fmt)
                break
            except ValueError:
                pass
        if parsed is None:
            parts = [part.strip() for part in cleaned.split("/")]
            if len(parts) == 3 and all(parts):
                try:
                    day, month, year = (int(part) for part in parts)
                    if year < 100:
                        year += 2000 if year <= 69 else 1900
                    parsed = datetime(year, month, day)
                except (ValueError, TypeError):
                    pass
        if parsed is None:
            return raw
        formats = {
            "JJ/MM/AAAA": "%d/%m/%Y",
            "JJ/MM/AA": "%d/%m/%y",
            "MM/AAAA": "%m/%Y",
            "AAAA": "%Y",
            "AAAA-MM-JJ": "%Y-%m-%d",
        }
        return parsed.strftime(formats.get(str(display_format), "%d/%m/%Y"))

    def _display_value(self, record: dict, field: str) -> str:
        if field == "photo_data":
            return display_native_value("Oui", self.language) if record.get("photo_data") else ""
        definition = self._custom_field_defs.get(str(field), {})
        field_type = str(definition.get("field_type") or "")
        if field_type == "calculated":
            return self._calculated_table_value(record, field, definition)
        value = record.get(field, "")
        text = str(value or "").strip()
        if field_type == "boolean":
            if text.casefold() in {"1", "oui", "yes", "true", "vrai", "on"}:
                return display_native_value("Oui", self.language)
            if text.casefold() in {"0", "non", "no", "false", "faux", "off", ""}:
                return display_native_value("Non", self.language) if text else ""
        if field_type == "date" and text:
            return self._normalize_table_date(text, str(definition.get("date_format") or "JJ/MM/AAAA"))
        if field_type == "currency" and text:
            raw = re.sub(r"[^0-9,\.\-+]", "", text).replace(",", ".")
            try:
                amount = float(raw)
                style = self._field_styles_cache.get(str(field), {}) if isinstance(self._field_styles_cache, dict) else {}
                symbol = str(style.get("currency_symbol") or "€").strip() or "€"
                try:
                    decimals = max(0, min(4, int(style.get("currency_decimals", 2))))
                except Exception:
                    decimals = 2
                return f"{amount:.{decimals}f}".replace(".", ",") + " " + symbol
            except ValueError:
                pass
        return display_native_value(text, self.language)

    def _record_matches_query(self, record: dict) -> bool:
        if not self.query_criteria:
            return True

        result: bool | None = None
        for index, criterion in enumerate(self.query_criteria):
            matched = self._matches_filter(
                self._display_value(record, criterion["field"]),
                criterion["value"],
                criterion["operator"],
                criterion.get("value2", ""),
            )
            if index == 0 or result is None:
                result = matched
                continue
            connector = str(criterion.get("connector", "and"))
            result = (result or matched) if connector == "or" else (result and matched)
        return bool(result)

    def apply_record_preview(self, record_id: int, values: dict) -> None:
        """Affiche immédiatement dans le Tableau les valeurs actuellement saisies
        dans une Fiche ouverte, sans attendre son changement de fiche.

        Il s'agit uniquement d'une synchronisation visuelle : l'enregistrement
        définitif reste géré par la Fiche comme auparavant.
        """
        rid = int(record_id)
        if not isinstance(values, dict):
            return

        # Mettre aussi à jour le cache local du Tableau.
        for record in self.records:
            if int(record.get("id", -1)) == rid:
                for key, value in values.items():
                    if key in record:
                        record[key] = value
                break

        self.table.blockSignals(True)
        try:
            for row in range(self.table.rowCount()):
                if self._record_id_at(row) != rid:
                    continue
                for column, field in enumerate(self.visible_fields):
                    if field not in values:
                        continue
                    item = self.table.item(row, column)
                    if item is None:
                        continue
                    text = str(values.get(field, "") or "")
                    item.setText(text)
                    item.setToolTip(text)
                break
        finally:
            self.table.blockSignals(False)

    def refresh_table(self) -> None:
        records = self._records_with_custom_values(
            self.manager.list_records(int(self.collection["id"]))
        )
        if self.query_criteria:
            records = [record for record in records if self._record_matches_query(record)]
        self.records = records
        self._update_query_banner()
        self._refresh_views_combo()
        self._apply_filters()

    def _reset_filter_to_default(self) -> None:
        """Rétablit Filtrer dans son état neutre : N° + Tous."""
        previous_updating = self._updating_query_filter
        self._updating_query_filter = True
        self._query_filter_prefill = False
        if not hasattr(self, "filter_field"):
            return
        self.active_filters.clear()
        self._refresh_filter_fields()
        field_index = self.filter_field.findData("record_number")
        self.filter_field.blockSignals(True)
        if field_index >= 0:
            self.filter_field.setCurrentIndex(field_index)
        self.filter_field.blockSignals(False)

        self._refresh_filter_value_choices()
        self._refresh_filter_operators("tous")
        operator_index = self.filter_operator.findData("tous")

        self.filter_operator.blockSignals(True)
        self.filter_value.blockSignals(True)
        self.filter_value_2.blockSignals(True)
        try:
            if operator_index >= 0:
                self.filter_operator.setCurrentIndex(operator_index)
            self.filter_value.clear()
            self.filter_value_2.clear()
            self._sync_filter_value_state()
        finally:
            self.filter_operator.blockSignals(False)
            self.filter_value.blockSignals(False)
            self.filter_value_2.blockSignals(False)
        self._updating_query_filter = previous_updating

    def _sync_filter_from_query(self, criteria: list[dict[str, str]]) -> None:
        """Recopie le premier critère de la requête dans la zone Filtrer."""
        self._reset_filter_to_default()
        if not criteria:
            return

        criterion = criteria[0]
        labels = {field_name: label for label, field_name in self.COLUMNS}
        field_index = self.filter_field.findData(criterion["field"])
        if field_index < 0:
            self.filter_field.addItem(
                labels.get(criterion["field"], criterion["field"]),
                criterion["field"],
            )
            field_index = self.filter_field.findData(criterion["field"])

        self.filter_field.blockSignals(True)
        if field_index >= 0:
            self.filter_field.setCurrentIndex(field_index)
        self.filter_field.blockSignals(False)

        self._refresh_filter_value_choices()
        self._refresh_filter_operators(criterion["operator"])
        operator_index = self.filter_operator.findData(criterion["operator"])

        self.filter_operator.blockSignals(True)
        self.filter_value.blockSignals(True)
        self.filter_value_2.blockSignals(True)
        try:
            if operator_index >= 0:
                self.filter_operator.setCurrentIndex(operator_index)
            self._sync_filter_value_state()
            self.filter_value.setText(criterion.get("value", ""))
            self.filter_value_2.setText(criterion.get("value2", ""))
        finally:
            self.filter_operator.blockSignals(False)
            self.filter_value.blockSignals(False)
            self.filter_value_2.blockSignals(False)

    def _show_query_criterion_in_filter(self, criteria: list[dict[str, str]]) -> None:
        """Affiche le premier critère de requête dans Filtrer, sans l'annuler."""
        self._query_filter_prefill = False
        self._updating_query_filter = True
        try:
            self.active_filters.clear()

            if not criteria:
                self._reset_filter_to_default()
                return

            criterion = criteria[0]
            labels = {field_name: label for label, field_name in self.COLUMNS}

            self._refresh_filter_fields()
            field_index = self.filter_field.findData(criterion["field"])
            if field_index < 0:
                self.filter_field.addItem(
                    labels.get(criterion["field"], criterion["field"]),
                    criterion["field"],
                )
                field_index = self.filter_field.findData(criterion["field"])

            self.filter_field.blockSignals(True)
            if field_index >= 0:
                self.filter_field.setCurrentIndex(field_index)
            self.filter_field.blockSignals(False)

            self._refresh_filter_value_choices()
            self._refresh_filter_operators(criterion["operator"])
            operator_index = self.filter_operator.findData(criterion["operator"])

            self.filter_operator.blockSignals(True)
            self.filter_value.blockSignals(True)
            self.filter_value_2.blockSignals(True)
            try:
                if operator_index >= 0:
                    self.filter_operator.setCurrentIndex(operator_index)
                self._sync_filter_value_state()
                self.filter_value.setText(criterion.get("value", ""))
                self.filter_value_2.setText(criterion.get("value2", ""))
            finally:
                self.filter_operator.blockSignals(False)
                self.filter_value.blockSignals(False)
                self.filter_value_2.blockSignals(False)

            self._query_filter_prefill = True
        finally:
            self._updating_query_filter = False

    def _activate_prefilled_query_filter(self, *_args) -> None:
        """Dès que l'utilisateur modifie Filtrer, il devient un vrai filtre."""
        if self._updating_query_filter:
            return
        if self._query_filter_prefill:
            self._query_filter_prefill = False

    def apply_multicriteria_query(self, criteria: list[dict[str, str]]) -> int:
        allowed_fields = {field_name for _label, field_name in self.COLUMNS}
        cleaned: list[dict[str, str]] = []
        for raw in criteria:
            field = str(raw.get("field", ""))
            value = canonical_native_value(str(raw.get("value", "")).strip(), self.language)
            operator = str(raw.get("operator", "contient") or "contient")
            no_value = operator in self.NO_VALUE_QUERY_OPERATORS
            if field not in allowed_fields or field == "photo_data" or (not value and not no_value):
                continue
            value2 = canonical_native_value(str(raw.get("value2", "")).strip(), self.language)
            if operator == "entre" and not value2:
                continue
            cleaned.append({
                "connector": "or" if str(raw.get("connector", "and")) == "or" else "and",
                "field": field,
                "operator": operator,
                "value": value,
                "value2": value2,
            })
        if cleaned:
            cleaned[0]["connector"] = "and"

        self.query_criteria = cleaned
        self.current_view_name = None
        self.active_filters.clear()

        # Le résultat de la requête est calculé une seule fois. Filtrer reprend
        # visuellement le premier critère, mais ne le réapplique pas tant que
        # l'utilisateur ne modifie pas cette ligne.
        self._show_query_criterion_in_filter(cleaned)
        self.refresh_table()
        return len(self.records)

    def apply_query(self, field: str, operator: str, value: str) -> int:
        return self.apply_multicriteria_query([{
            "connector": "and", "field": field, "operator": operator, "value": value
        }])

    def clear_query(
        self,
        *_args,
        refresh: bool = True,
        clear_query_filter: bool = True,
    ) -> None:
        self.query_criteria = []
        self.current_view_name = None
        if clear_query_filter and hasattr(self, "filter_field"):
            self._reset_filter_to_default()
        self._update_query_banner()
        self._refresh_views_combo()
        if refresh:
            self.refresh_table()

    def _update_query_banner(self) -> None:
        if not hasattr(self, "query_banner"):
            return
        criteria = self.query_criteria
        self.query_banner.setVisible(bool(criteria))
        if not criteria:
            self.query_label.clear()
            return
        labels = {field: label for label, field in self.COLUMNS}
        op_labels = {
            "tous": "tous",
            "contient": "contient",
            "commence_par": "commence par",
            "exactement": "est exactement",
            "different": "est différent de",
            "termine_par": "se termine par",
            "est_vide": "est vide",
            "non_vide": "n’est pas vide",
            "num_egal": "=",
            "num_different": "≠",
            "superieur": ">",
            "superieur_egal": "≥",
            "inferieur": "<",
            "inferieur_egal": "≤",
            "entre": "compris entre",
        }
        parts: list[str] = []
        for index, criterion in enumerate(criteria):
            prefix = "" if index == 0 else (" OU " if criterion.get("connector") == "or" else " ET ")
            operator = criterion["operator"]
            if operator in self.NO_VALUE_QUERY_OPERATORS:
                value_part = ""
            elif operator == "entre":
                value_part = f' « {criterion["value"]} » et « {criterion.get("value2", "")} »'
            else:
                value_part = f' « {criterion["value"]} »'
            parts.append(
                f'{prefix}{labels.get(criterion["field"], criterion["field"])} '
                f'{tr(op_labels.get(operator, operator), self.language)}{value_part}'
            )
        result_count = len(self.records)
        suffix = tr("fiche" if result_count == 1 else "fiches", self.language)
        self.query_label.setText(
            tr("Requête :", self.language) + " " + "".join(parts)
            + f" — {result_count} {suffix}"
        )

    @staticmethod
    def _parse_date_value(text: str):
        from datetime import datetime
        raw = str(text or "").strip()
        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y"):
            try:
                return datetime.strptime(raw, fmt)
            except ValueError:
                pass
        return None

    @classmethod
    def _matches_filter(cls, value: object, query: str, operator: str, query2: str = "") -> bool:
        if operator == "tous":
            return True
        raw_text = str(value or "").strip()
        text = raw_text.casefold()
        query_text = str(query or "").strip()
        query_folded = query_text.casefold()

        if operator == "est_vide":
            return raw_text == ""
        if operator == "non_vide":
            return raw_text != ""

        if operator == "annee_entiere":
            parsed = cls._parse_date_value(raw_text)
            try:
                year = int(str(query_text).strip())
            except (TypeError, ValueError):
                return False
            if parsed is None:
                return False
            return parsed.year == year

        if operator == "entre":
            # D'abord tenter une comparaison numérique.
            try:
                left = float(raw_text.replace(",", "."))
                low = float(query_text.replace(",", "."))
                high = float(str(query2 or "").strip().replace(",", "."))
                if low > high:
                    low, high = high, low
                return low <= left <= high
            except (TypeError, ValueError):
                pass

            # Sinon tenter une comparaison de dates usuelles.
            left_date = cls._parse_date_value(raw_text)
            low_date = cls._parse_date_value(query_text)
            high_date = cls._parse_date_value(query2)
            if left_date is None or low_date is None or high_date is None:
                return False
            if low_date > high_date:
                low_date, high_date = high_date, low_date
            return low_date <= left_date <= high_date

        if operator in {
            "num_egal", "num_different", "superieur", "superieur_egal",
            "inferieur", "inferieur_egal",
        }:
            # Les mêmes identifiants d'opérateurs servent aux nombres et aux dates.
            # Essayer d'abord le numérique, puis une vraie comparaison chronologique.
            try:
                left = float(raw_text.replace(",", "."))
                right = float(query_text.replace(",", "."))
            except (TypeError, ValueError):
                left = cls._parse_date_value(raw_text)
                right = cls._parse_date_value(query_text)
                if left is None or right is None:
                    return False
            if operator == "num_egal":
                return left == right
            if operator == "num_different":
                return left != right
            if operator == "superieur":
                return left > right
            if operator == "superieur_egal":
                return left >= right
            if operator == "inferieur":
                return left < right
            if operator == "inferieur_egal":
                return left <= right

        if not query_folded:
            return True
        if operator == "commence_par":
            return text.startswith(query_folded)
        if operator == "exactement":
            return text == query_folded
        if operator == "different":
            return text != query_folded
        if operator == "termine_par":
            return text.endswith(query_folded)
        return query_folded in text

    def _current_filter(self) -> dict[str, str] | None:
        if self._query_filter_prefill:
            return None
        query = self.filter_value.text().strip()
        query2 = self.filter_value_2.text().strip() if hasattr(self, "filter_value_2") else ""
        field = self.filter_field.currentData()
        operator = str(self.filter_operator.currentData() or "contient")
        if not field:
            return None
        if operator not in self.NO_VALUE_QUERY_OPERATORS and not query:
            return None
        if operator == "entre" and not query2:
            return None
        return {
            "field": str(field),
            "operator": operator,
            "value": query,
            "value2": query2,
        }

    def _filtered_records(self) -> list[dict]:
        filters = list(self.active_filters)
        current = self._current_filter()
        if current is not None:
            filters.append(current)
        if not filters:
            return list(self.records)
        return [
            record for record in self.records
            if all(
                self._matches_filter(
                    self._display_value(record, criterion["field"]),
                    criterion["value"],
                    criterion["operator"],
                    criterion.get("value2", ""),
                )
                for criterion in filters
            )
        ]

    def _apply_filters(self, *_args) -> None:
        if not hasattr(self, "table"):
            return
        self._populate_table(self._filtered_records())
        self._update_filter_summary()

    def _pin_current_filter(self) -> None:
        current = self._current_filter()
        if current is None:
            return
        self.active_filters.append(current)
        self.filter_value.clear()
        if hasattr(self, "filter_value_2"):
            self.filter_value_2.clear()
        self._apply_filters()

    def _clear_filters(self) -> None:
        self.active_filters.clear()
        self.filter_value.clear()
        if hasattr(self, "filter_value_2"):
            self.filter_value_2.clear()
        self._apply_filters()

    def _refresh_filter_fields(self) -> None:
        if not hasattr(self, "filter_field"):
            return
        previous = self.filter_field.currentData()
        self.filter_field.blockSignals(True)
        self.filter_field.clear()
        for label, field in sorted(self.COLUMNS, key=lambda item: field_sort_key(item[0])):
            if field != "photo_data":
                self.filter_field.addItem(label, field)
                if field in {"record_number", "record_state"}:
                    self.filter_field.setItemData(self.filter_field.count()-1, QColor("#0055FF"), Qt.ItemDataRole.ForegroundRole)
        index = self.filter_field.findData(previous) if previous else -1
        self.filter_field.setCurrentIndex(index if index >= 0 else 0)
        self.filter_field.blockSignals(False)

    def _refresh_filter_value_choices(self) -> None:
        if not hasattr(self, "filter_value"):
            return
        field = str(self.filter_field.currentData() or "")
        code = self._referential_code(field)
        values: list[str] = []
        if code:
            cid = int(self.collection["id"])
            if code == "record_state":
                # Valeur système obligatoire : ne dépend jamais du contenu importé.
                try:
                    if not self.referentials.contains(cid, "record_state", "Libre", active_only=True):
                        self.referentials.add_value(cid, "record_state", "Libre")
                except Exception:
                    pass
            values = self.referentials.list_values(cid, code, active_only=True)
            if code == "record_state" and not any(str(v).strip().casefold() == "libre" for v in values):
                values = list(values) + ["Libre"]
        current = self.filter_value.text()
        self.filter_value.set_values(values)
        self.filter_value.setText(current)

    def _is_date_filter_field(self, field: str) -> bool:
        lowered = field.casefold()
        return any(hint in lowered for hint in self.DATE_FIELD_HINTS)

    def _operators_for_filter_field(self) -> tuple[tuple[str, str], ...]:
        field = str(self.filter_field.currentData() or "")
        return (
            self.NUMERIC_QUERY_OPERATORS
            if field in self.NUMERIC_QUERY_FIELDS or self._is_date_filter_field(field)
            else self.TEXT_QUERY_OPERATORS
        )

    def _refresh_filter_operators(self, preferred: str | None = None) -> None:
        if not hasattr(self, "filter_operator") or not hasattr(self, "filter_field"):
            return
        previous = preferred if preferred is not None else self.filter_operator.currentData()
        self.filter_operator.blockSignals(True)
        self.filter_operator.clear()
        for label, operator in self._operators_for_filter_field():
            self.filter_operator.addItem(tr(label, self.language), operator)
        index = self.filter_operator.findData(previous) if previous else -1
        self.filter_operator.setCurrentIndex(index if index >= 0 else 0)
        self.filter_operator.blockSignals(False)
        self._sync_filter_value_state()

    def _sync_filter_value_state(self) -> None:
        if not hasattr(self, "filter_value"):
            return
        operator = str(self.filter_operator.currentData() or "")
        needs_value = operator not in self.NO_VALUE_QUERY_OPERATORS
        is_between = operator == "entre"

        # La liste de propositions doit respecter l'opérateur choisi :
        # "Commence par" => seulement les valeurs commençant par la saisie.
        self.filter_value.set_match_mode(operator == "commence_par")
        self.filter_value.setEnabled(needs_value)
        self.filter_value_2.setVisible(is_between)
        self.filter_value_2.setEnabled(is_between)

        if needs_value:
            field = str(self.filter_field.currentData() or "")
            if is_between:
                if self._is_date_filter_field(field):
                    self.filter_value.setPlaceholderText("Date début…")
                    self.filter_value_2.setPlaceholderText("Date fin…")
                else:
                    self.filter_value.setPlaceholderText("Minimum…")
                    self.filter_value_2.setPlaceholderText("Maximum…")
            elif field in self.NUMERIC_QUERY_FIELDS:
                self.filter_value.setPlaceholderText("Nombre…")
            elif self._is_date_filter_field(field):
                self.filter_value.setPlaceholderText("Date…")
            else:
                self.filter_value.setPlaceholderText(tr("Tapez une valeur…", self.language))

            if not is_between:
                self.filter_value_2.blockSignals(True)
                self.filter_value_2.clear()
                self.filter_value_2.blockSignals(False)
        else:
            self.filter_value.blockSignals(True)
            self.filter_value.clear()
            self.filter_value.blockSignals(False)
            self.filter_value_2.blockSignals(True)
            self.filter_value_2.clear()
            self.filter_value_2.blockSignals(False)
            self.filter_value.setPlaceholderText(tr("Aucune valeur nécessaire", self.language))

    def _detach_query_for_manual_filter(self) -> bool:
        """Quitte la population de requête et recharge toute la collection.

        Retourne True si un rechargement a été effectué.
        """
        if not self.query_criteria:
            return False

        self.query_criteria = []
        self.current_view_name = None
        self._update_query_banner()
        self._refresh_views_combo()

        # Recharger la collection entière sans perdre les widgets de filtre.
        records = self._records_with_custom_values(
            self.manager.list_records(int(self.collection["id"]))
        )
        self.records = records
        return True

    def _on_filter_value_changed(self, *_args) -> None:
        if self._updating_query_filter:
            return
        self._detach_query_for_manual_filter()
        self._apply_filters()

    def _on_filter_field_changed(self, *_args) -> None:
        if self._updating_query_filter:
            return
        self._detach_query_for_manual_filter()
        # Un champ système choisi comme critère doit aussi être visible dans le
        # tableau : l'utilisateur voit immédiatement sa valeur et peut l'éditer.
        field = str(self.filter_field.currentData() or "")
        if field == "record_state" and field not in self.visible_fields:
            self.visible_fields.append(field)
            self._widths_initialized = False
        self._refresh_filter_value_choices()
        self._refresh_filter_operators()
        self._apply_filters()

    def _on_filter_operator_changed(self, *_args) -> None:
        if self._updating_query_filter:
            return
        self._detach_query_for_manual_filter()
        self._sync_filter_value_state()
        self._apply_filters()

    def _update_filter_summary(self) -> None:
        labels = {field: label for label, field in self.COLUMNS}
        op_labels = {
            "contient": "contient",
            "commence_par": "commence par",
            "exactement": "est exactement",
            "different": "est différent de",
            "termine_par": "se termine par",
            "est_vide": "est vide",
            "non_vide": "n’est pas vide",
            "num_egal": "=",
            "num_different": "≠",
            "superieur": ">",
            "superieur_egal": "≥",
            "inferieur": "<",
            "inferieur_egal": "≤",
            "entre": "compris entre",
        }
        if not self.active_filters:
            self.filters_summary.setText(tr("Aucun filtre épinglé — la saisie ci-dessus filtre immédiatement le tableau.", self.language))
            self.clear_filters_button.setEnabled(bool(self.filter_value.text().strip()))
            return
        parts = [
            (
                f'{labels.get(f["field"], f["field"])} {op_labels.get(f["operator"], f["operator"])}'
                if f["operator"] in self.NO_VALUE_QUERY_OPERATORS
                else (
                    f'{labels.get(f["field"], f["field"])} {op_labels.get(f["operator"], f["operator"])} '
                    f'« {f["value"]} » et « {f.get("value2", "")} »'
                    if f["operator"] == "entre"
                    else f'{labels.get(f["field"], f["field"])} {op_labels.get(f["operator"], f["operator"])} « {f["value"]} »'
                )
            )
            for f in self.active_filters
        ]
        self.filters_summary.setText("Filtres actifs : " + "  ET  ".join(parts))
        self.clear_filters_button.setEnabled(True)

    REFERENTIAL_BY_FIELD = {
        "mineral_name": "mineral_name",
        "mineral_2": "mineral_name",
        "mineral_3": "mineral_name",
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

    # Les blocs Identification et Localisation sont des ensembles cohérents :
    # aucune de leurs cellules ne peut être corrigée isolément depuis le Tableau.
    # Toute modification passe par la fiche, qui applique les dépendances prévues.
    IDENTIFICATION_FIELDS = {
        "mineral_name", "mineral_2", "mineral_3", "mineral_class",
        "chemical_formula", "crystal_system", "luminescence",
        "luminescence_intensity", "fluorescence_color", "internet_link",
    }
    LOCATION_FIELDS = {
        "site_name", "deposit", "department", "region", "country",
        "category", "site_internet_link",
    }
    # Les deux champs maîtres Nom et Site restent éditables, mais uniquement
    # avec une valeur déjà existante dans leur référentiel. Tous les autres
    # champs dépendants des blocs Identification / Localisation restent verrouillés.
    READ_ONLY_TABLE_FIELDS = {
        "record_number", "photo_data",
        *(IDENTIFICATION_FIELDS - {"mineral_name"}),
        *(LOCATION_FIELDS - {"site_name"}),
    }
    MASTER_REFERENTIAL_CODES = {"mineral_name", "site_name"}
    OLD_VALUE_ROLE = Qt.ItemDataRole.UserRole + 2

    def _referential_code(self, field: str) -> str | None:
        definition = self._custom_field_defs.get(str(field))
        if definition is not None:
            code = str(definition.get("referential_code") or "").strip()
            return code or None
        return self.REFERENTIAL_BY_FIELD.get(field)

    def _is_cell_editable(self, column: int) -> bool:
        """Une cellule est éditable si le moteur Tableau sait enregistrer ce champ.

        Le N° de fiche et la Photo restent non modifiables. Les autres champs
        standards pris en charge par RecordManager redeviennent éditables en ligne,
        y compris les champs dépendants des blocs Identification / Localisation.
        """
        if not (0 <= column < len(self.visible_fields)):
            return False
        field = self.visible_fields[column]
        if field in self.manager.TABLE_EDITABLE_FIELDS:
            return True
        definition = self._custom_field_defs.get(field)
        if definition is None:
            return False
        return str(definition.get("field_type") or "") != "calculated"

    def _record_id_at(self, row: int) -> int | None:
        if not (0 <= row < self.table.rowCount()):
            return None
        for column in range(self.table.columnCount()):
            item = self.table.item(row, column)
            if item is not None:
                value = item.data(Qt.ItemDataRole.UserRole)
                if value is not None:
                    return int(value)
        return None

    def _on_cell_double_clicked(self, row: int, column: int) -> None:
        if self._is_cell_editable(column):
            item = self.table.item(row, column)
            if item is not None:
                self.table.editItem(item)
            return
        # N° et Photo restent intouchables ; un double-clic sur N° conserve
        # l'accès direct à la fiche complète.
        if 0 <= column < len(self.visible_fields) and self.visible_fields[column] == "record_number":
            self._open_selected_record()

    def _prepare_vertical_edit(self, row: int, column: int) -> None:
        """Mémorise la fiche suivante avant le tri/filtrage provoqué par l'édition."""
        if not self._is_cell_editable(column):
            self._pending_vertical_edit = None
            return
        next_record_id = self._record_id_at(row + 1)
        field = self.visible_fields[column]
        self._pending_vertical_edit = (next_record_id, field) if next_record_id is not None else None

    def _restore_item_value(self, item: QTableWidgetItem, value: str) -> None:
        self.table.blockSignals(True)
        try:
            item.setText(str(value or ""))
        finally:
            self.table.blockSignals(False)

    def _validate_table_referential_value(
        self, field: str, value: str, item: QTableWidgetItem
    ) -> tuple[bool, str]:
        ref_code = self._referential_code(field)
        if not ref_code:
            return True, value
        normalized = self.referentials.normalize(value, ref_code)
        if not normalized:
            return True, ""
        collection_id = int(self.collection["id"])
        if self.referentials.contains(collection_id, ref_code, normalized, active_only=True):
            return True, normalized

        label_by_field = {key: label for label, key in self.COLUMNS}
        field_label = label_by_field.get(field, field)
        if field in set(self.model_manager.field_masters(collection_id)):
            QMessageBox.warning(
                self,
                "Valeur maître inconnue",
                f'La valeur « {normalized} » n’existe pas dans le référentiel « {field_label} ».\n\n'
                "Depuis le Tableau, une valeur maître doit déjà exister afin que MM3 "
                "puisse charger correctement le bloc associé. Choisissez une valeur de la liste "
                "ou videz la cellule.",
            )
            return False, str(item.data(self.OLD_VALUE_ROLE) or "")

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle("Nouvelle valeur")
        box.setText(f'La valeur « {normalized} » n’existe pas encore dans le référentiel « {field_label} ».')
        box.setInformativeText("Voulez-vous l’ajouter au référentiel et l’enregistrer dans cette fiche ?")
        yes_button = box.addButton("OUI", QMessageBox.ButtonRole.YesRole)
        no_button = box.addButton("NON", QMessageBox.ButtonRole.NoRole)
        box.setDefaultButton(yes_button)
        box.exec()
        if box.clickedButton() is not yes_button:
            return False, str(item.data(self.OLD_VALUE_ROLE) or "")
        try:
            normalized = self.referentials.add_value(collection_id, ref_code, normalized)
        except Exception as exc:
            QMessageBox.critical(self, "Ajout impossible", str(exc))
            return False, str(item.data(self.OLD_VALUE_ROLE) or "")
        return True, normalized

    def _on_table_item_changed(self, item: QTableWidgetItem) -> None:
        if self._populating_table:
            return
        column = item.column()
        if not self._is_cell_editable(column):
            return
        record_id = item.data(Qt.ItemDataRole.UserRole)
        if record_id is None:
            return
        field = self.visible_fields[column]
        value = item.text().strip()
        definition = self._custom_field_defs.get(str(field), {})
        if str(definition.get("field_type") or "") == "date" and value:
            value = self._normalize_table_date(
                value, str(definition.get("date_format") or "JJ/MM/AAAA")
            )
            if item.text().strip() != value:
                self._restore_item_value(item, value)

        if int(record_id) == -1:
            if not value:
                return
            try:
                created = self.manager.create_record(int(self.collection["id"]))
                created_id = int(created["id"])
                if field in self._custom_field_defs:
                    self.manager.set_custom_values(created_id, {field: value})
                    updated = dict(created)
                    updated[field] = value
                else:
                    updated = self.manager.update_table_field(
                        created_id, int(self.collection["id"]), field, value
                    )
            except Exception as exc:
                QMessageBox.critical(self, "Création impossible", str(exc))
                self._pending_vertical_edit = None
                self.refresh_table()
                return
            created_id = int(updated.get("id", created_id))
            snapshot = self._snapshot_record(created_id)
            if snapshot is not None:
                source = copy.deepcopy(snapshot["record"])
                source["__mm3_custom_values__"] = copy.deepcopy(snapshot.get("custom") or {})
                self._push_history({"type": "create", "created_ids": [created_id], "source": source})
            self.refresh_table()
            self._select_record_by_id(created_id)
            return
        valid, value = self._validate_table_referential_value(field, value, item)
        if not valid:
            self._restore_item_value(item, value)
            self._pending_vertical_edit = None
            return
        if item.text().strip() != value:
            self._restore_item_value(item, value)
        before_snapshot = self._snapshot_record(int(record_id))
        try:
            cid = int(self.collection["id"])
            rid = int(record_id)

            if field in self._custom_field_defs:
                self.manager.set_custom_values(rid, {field: value})
                updated = next(
                    (dict(record) for record in self.records
                     if int(record.get("id", -1)) == rid),
                    {"id": rid},
                )
                updated[field] = value
            else:
                updated = self.manager.update_table_field(rid, cid, field, value)

            # Les relations explicites de l'Atelier sont l'autorité, qu'il
            # s'agisse de champs historiques ou de champs importés/personnalisés.
            links = dict(self.model_manager.field_links(cid))
            masters = set(self.model_manager.field_masters(cid))

            if field in links:
                master_key = str(links[field])
                current_row = next(
                    (record for record in self.records
                     if int(record.get("id", -1)) == rid),
                    {},
                )
                master_value = str(
                    updated.get(master_key, "")
                    or current_row.get(master_key, "")
                    or ""
                ).strip()
                if master_value:
                    self.model_manager.propagate_linked_value(
                        cid, master_key, master_value, field, value
                    )

            elif field in masters:
                master_value = str(value or "").strip()
                if master_value:
                    linked_values = self.model_manager.linked_values_for_master(
                        cid, field, master_value
                    )
                    for linked_key, linked_value in linked_values.items():
                        linked_key = str(linked_key)
                        if links.get(linked_key) != field:
                            continue
                        linked_text = str(linked_value or "")
                        if linked_key in self._custom_field_defs:
                            self.manager.set_custom_values(
                                rid, {linked_key: linked_text}
                            )
                        elif linked_key in self.manager.TABLE_EDITABLE_FIELDS:
                            self.manager.update_table_field(
                                rid, cid, linked_key, linked_text
                            )

            item.setData(self.OLD_VALUE_ROLE, value)
            after_snapshot = self._snapshot_record(rid)
            if before_snapshot is not None and after_snapshot is not None:
                self._push_history({
                    "type": "edit", "before": before_snapshot, "after": after_snapshot
                })
        except Exception as exc:
            QMessageBox.critical(self, "Modification impossible", str(exc))
            self._restore_item_value(item, str(item.data(self.OLD_VALUE_ROLE) or ""))
            self._pending_vertical_edit = None
            return

        # Une édition peut avoir modifié plusieurs fiches à cause d'une liaison :
        # le Tableau se relit et la Fiche ouverte se resynchronise.
        self.recordChanged.emit(int(record_id))
        self._schedule_refresh_after_edit()

    def _schedule_refresh_after_edit(self) -> None:
        if self._refresh_after_edit_scheduled:
            return
        self._refresh_after_edit_scheduled = True
        QTimer.singleShot(0, self._refresh_after_direct_edit)

    def _refresh_after_direct_edit(self) -> None:
        self._refresh_after_edit_scheduled = False
        pending = self._pending_vertical_edit
        self._pending_vertical_edit = None
        self.refresh_table()
        if pending is None:
            self.statusBar().showMessage("Modification enregistrée.", 2500)
            return
        record_id, field = pending
        self._edit_record_field(record_id, field)

    def _edit_record_field(self, record_id: int, field: str) -> None:
        if field not in self.visible_fields:
            return
        column = self.visible_fields.index(field)
        if not self._is_cell_editable(column):
            return
        for row in range(self.table.rowCount()):
            if self._record_id_at(row) == int(record_id):
                item = self.table.item(row, column)
                if item is None:
                    return
                self.table.setCurrentCell(row, column)
                self.table.scrollToItem(item, QAbstractItemView.ScrollHint.EnsureVisible)
                self.table.editItem(item)
                return

    def _populate_table(self, displayed_records: list[dict] | None = None) -> None:
        self._populating_table = True
        # Désactiver temporairement le tri évite que les lignes bougent pendant leur remplissage.
        sorting = self.table.isSortingEnabled()
        self.table.setSortingEnabled(False)

        labels_by_field = {field: label for label, field in self.COLUMNS}
        displayed_records = self.records if displayed_records is None else displayed_records
        self.table.clear()
        self.table.setColumnCount(len(self.visible_fields))
        self.table.setHorizontalHeaderLabels([labels_by_field[field] for field in self.visible_fields])
        # La ligne virtuelle reste disponible dans la Vue Tableau normale.
        # Un résultat de requête (query_criteria non vide) n'affiche que ses fiches.
        show_virtual_row = not bool(self.query_criteria)
        self.table.setRowCount(len(displayed_records) + (1 if show_virtual_row else 0))

        for row_index, record in enumerate(displayed_records):
            record_id = int(record["id"])
            for column_index, field in enumerate(self.visible_fields):
                text = self._display_value(record, field)
                if field == "record_number":
                    item = NumericTableWidgetItem(text)
                    item.setData(Qt.ItemDataRole.UserRole + 1, int(record.get("record_number", 0)))
                else:
                    item = QTableWidgetItem(text)
                item.setData(Qt.ItemDataRole.UserRole, record_id)
                item.setData(self.OLD_VALUE_ROLE, text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                if text:
                    item.setToolTip(text)
                self.table.setItem(row_index, column_index, item)

        # Ligne vierge permanente de fin de base : cible naturelle de Ctrl+V,
        # uniquement hors résultat de requête.
        if show_virtual_row:
            virtual_row = len(displayed_records)
            for column_index, field in enumerate(self.visible_fields):
                item = QTableWidgetItem("")
                item.setData(Qt.ItemDataRole.UserRole, -1)
                item.setData(self.OLD_VALUE_ROLE, "")
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                )
                self.table.setItem(virtual_row, column_index, item)

        header = self.table.horizontalHeader()
        if not self._widths_initialized:
            for index, field in enumerate(self.visible_fields):
                width = 82 if field == "record_number" else self.STANDARD_WIDTH
                header.resizeSection(index, width)
            self._widths_initialized = True

        self.table.setSortingEnabled(sorting)
        count = len(displayed_records)
        total = len(self.records)
        if str(self.language or "fr").lower().startswith("en"):
            word = "record" if count == 1 else "records"
            if count == total:
                self.count_label.setText(f"{count} {word}")
            else:
                self.count_label.setText(f"{count} {word} of {total}")
        elif str(self.language or "fr").lower().startswith("de"):
            word = "Datensatz" if count == 1 else "Datensätze"
            if count == total:
                self.count_label.setText(f"{count} {word}")
            else:
                self.count_label.setText(f"{count} {word} von {total}")
        else:
            if count == total:
                self.count_label.setText(f"{count} fiche{'s' if count != 1 else ''}")
            else:
                self.count_label.setText(f"{count} fiche{'s' if count != 1 else ''} sur {total}")
        self._apply_table_layout()
        self.table.clearSelection()
        self._update_open_button()
        self._populating_table = False

    def choose_columns(self) -> None:
        dialog = ColumnChooserDialog(self.COLUMNS, self.visible_fields, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.visible_fields = dialog.selected_fields()
        self.active_filters = [f for f in self.active_filters if f["field"] in self.visible_fields]
        self._widths_initialized = False
        self._refresh_filter_fields()
        self._apply_filters()

    def _selected_table_rows(self) -> list[int]:
        """Lignes touchées par la sélection, même si seules quelques cellules sont choisies."""
        indexes = self.table.selectionModel().selectedIndexes()
        return sorted({index.row() for index in indexes})

    def _selected_record_id(self) -> int | None:
        rows = self._selected_table_rows()
        if not rows:
            return None
        row = rows[0]
        for column in range(self.table.columnCount()):
            item = self.table.item(row, column)
            if item is not None:
                value = item.data(Qt.ItemDataRole.UserRole)
                if value is not None:
                    return int(value)
        return None

    def _selected_record_ids(self) -> list[int]:
        """Retourne les fiches réelles sélectionnées, dans l'ordre visuel du Tableau."""
        rows = self._selected_table_rows()
        result: list[int] = []
        for row in rows:
            record_id = None
            for column in range(self.table.columnCount()):
                item = self.table.item(row, column)
                if item is not None:
                    value = item.data(Qt.ItemDataRole.UserRole)
                    if value is not None:
                        record_id = int(value)
                        break
            if record_id is not None and record_id > 0:
                result.append(record_id)
        return result

    def _copy_shortcut(self) -> None:
        """Ctrl+C : plusieurs fiches sélectionnées = copie de fiches ; sinon copie de cellules."""
        if len(self._selected_record_ids()) > 1:
            self.copy_selected_record()
        else:
            self.copy_selected_cells()

    def copy_selected_cells(self, *_args) -> None:
        """Copie la sélection tabulaire au format TSV, prête à coller dans Excel/Calc."""
        indexes = self.table.selectionModel().selectedIndexes()
        if not indexes:
            current = self.table.currentItem()
            if current is None:
                return
            current.setSelected(True)
            indexes = self.table.selectionModel().selectedIndexes()
            if not indexes:
                return

        selected = {(idx.row(), idx.column()) for idx in indexes}
        rows = sorted({r for r, _c in selected})
        logical_columns = sorted({c for _r, c in selected})

        # Respecter l'ordre visuel choisi par l'utilisateur après déplacement
        # des colonnes et ignorer toute colonne éventuellement masquée.
        header = self.table.horizontalHeader()
        logical_columns = [
            c for c in logical_columns if not self.table.isColumnHidden(c)
        ]
        logical_columns.sort(key=lambda c: header.visualIndex(c))
        if not rows or not logical_columns:
            return

        def clean(value: str) -> str:
            # TSV : tabs et retours à la ligne internes sont neutralisés afin
            # qu'une valeur reste dans une seule cellule lors du collage.
            return str(value or "").replace("\t", " ").replace("\r", " ").replace("\n", " ")

        lines: list[str] = []
        labels = []
        for col in logical_columns:
            header_item = self.table.horizontalHeaderItem(col)
            labels.append(clean(header_item.text() if header_item is not None else ""))
        lines.append("\t".join(labels))

        for row in rows:
            # La dernière ligne virtuelle de création n'est pas exportée lorsqu'elle
            # est vide ; elle ne représente pas encore une fiche réelle.
            rid = self._record_id_at(row)
            if rid == -1:
                has_value = any(
                    bool((self.table.item(row, col).text() if self.table.item(row, col) else "").strip())
                    for col in logical_columns
                )
                if not has_value:
                    continue

            values = []
            for col in logical_columns:
                if (row, col) not in selected:
                    values.append("")
                    continue
                item = self.table.item(row, col)
                values.append(clean(item.text() if item is not None else ""))
            lines.append("\t".join(values))

        mime = QMimeData()
        mime.setText("\r\n".join(lines))
        QApplication.clipboard().setMimeData(mime)

    def _selected_records_tsv(self) -> str:
        """Retourne les fiches sélectionnées en TSV pour Excel/Calc, sans modifier la sélection."""
        rows = self._selected_table_rows()
        if not rows:
            return ""

        header = self.table.horizontalHeader()
        columns = [c for c in range(self.table.columnCount()) if not self.table.isColumnHidden(c)]
        columns.sort(key=lambda c: header.visualIndex(c))
        if not columns:
            return ""

        def clean(value: str) -> str:
            return str(value or "").replace("\t", " ").replace("\r", " ").replace("\n", " ")

        labels = []
        for col in columns:
            item = self.table.horizontalHeaderItem(col)
            labels.append(clean(item.text() if item is not None else ""))
        lines = ["\t".join(labels)]

        for row in rows:
            if self._record_id_at(row) == -1:
                continue
            values = []
            for col in columns:
                item = self.table.item(row, col)
                values.append(clean(item.text() if item is not None else ""))
            lines.append("\t".join(values))
        return "\r\n".join(lines) if len(lines) > 1 else ""

    def _record_context_menu(self, position) -> None:
        """Clic droit : copie tabulaire et opérations sur les fiches."""
        item = self.table.itemAt(position)
        if item is None:
            return

        # Un clic droit sur une ligne déjà comprise dans une sélection multiple
        # conserve toute la sélection. Sur une autre ligne, il la remplace.
        selected_rows = set(self._selected_table_rows())
        if item.row() not in selected_rows:
            self.table.clearSelection()
            item.setSelected(True)
            self.table.setCurrentItem(item)

        record_id = self._selected_record_id()
        if record_id is None:
            return

        menu = QMenu(self.table)

        copy_cells_action = menu.addAction(tr("Copier les cellules", self.language))
        copy_cells_action.setShortcut(QKeySequence.StandardKey.Copy)
        copy_cells_action.triggered.connect(self.copy_selected_cells)
        menu.addSeparator()

        selected_ids = self._selected_record_ids()
        copy_label = ("Datensatz kopieren" if len(selected_ids) <= 1 else f"{len(selected_ids)} Datensätze kopieren") if str(self.language or "fr").lower().startswith("de") else ("Copier la fiche" if len(selected_ids) <= 1 else f"Copier les {len(selected_ids)} fiches")
        copy_action = menu.addAction(copy_label)
        copy_action.setEnabled(bool(selected_ids))
        copy_action.triggered.connect(self.copy_selected_record)

        clip_count = len(self._clipboard_records())
        paste_label = ("Datensatz einfügen" if clip_count <= 1 else f"{clip_count} Datensätze einfügen") if str(self.language or "fr").lower().startswith("de") else ("Coller la fiche" if clip_count <= 1 else f"Coller les {clip_count} fiches")
        paste_action = menu.addAction(paste_label)
        paste_action.setEnabled(clip_count > 0 and (int(record_id) == -1 or int(record_id) > 0))
        paste_action.triggered.connect(self._paste_shortcut)
        menu.addSeparator()
        clear_action = menu.addAction(("Datensatz leeren" if len(selected_ids) <= 1 else f"{len(selected_ids)} Datensätze leeren") if str(self.language or "fr").lower().startswith("de") else ("Vider la fiche" if len(selected_ids) <= 1 else f"Vider les {len(selected_ids)} fiches"))
        clear_action.setEnabled(bool(selected_ids))
        clear_action.triggered.connect(self.clear_selected_records)
        delete_action = menu.addAction(
            ("Endgültig löschen" if len(selected_ids) <= 1 else f"{len(selected_ids)} Datensätze endgültig löschen")
            if str(self.language or "fr").lower().startswith("de") else ("Supprimer définitivement" if len(selected_ids) <= 1 else f"Supprimer définitivement les {len(selected_ids)} fiches")
        )
        delete_action.setEnabled(bool(selected_ids))
        delete_action.triggered.connect(self.delete_selected_tail_records)

        menu.exec(self.table.viewport().mapToGlobal(position))

    def _update_open_button(self) -> None:
        record_id = self._selected_record_id()
        selected_ids = self._selected_record_ids()
        selected_real = record_id is not None and int(record_id) > 0
        selected_virtual = record_id == -1
        # Une fiche seulement peut être ouverte ; plusieurs peuvent être copiées.
        self.open_button.setEnabled(selected_real and len(selected_ids) == 1)
        if hasattr(self, "copy_record_button"):
            self.copy_record_button.setEnabled(bool(selected_ids))
            if str(self.language or "fr").lower().startswith("de"):
                self.copy_record_button.setText("Datensatz kopieren" if len(selected_ids) <= 1 else f"{len(selected_ids)} Datensätze kopieren")
            elif str(self.language or "fr").lower().startswith("en"):
                self.copy_record_button.setText(
                    "Copy record" if len(selected_ids) <= 1 else f"Copy {len(selected_ids)} records"
                )
            else:
                self.copy_record_button.setText(
                    "Copier la fiche" if len(selected_ids) <= 1 else f"Copier les {len(selected_ids)} fiches"
                )
        if hasattr(self, "paste_record_button"):
            clip_count = len(self._clipboard_records())
            has_destination = selected_real or selected_virtual
            self.paste_record_button.setEnabled(has_destination and clip_count > 0)
            if str(self.language or "fr").lower().startswith("de"):
                self.paste_record_button.setText("Datensatz einfügen" if clip_count <= 1 else f"{clip_count} Datensätze einfügen")
            elif str(self.language or "fr").lower().startswith("en"):
                self.paste_record_button.setText(
                    "Paste record" if clip_count <= 1 else f"Paste {clip_count} records"
                )
            else:
                self.paste_record_button.setText(
                    "Coller la fiche" if clip_count <= 1 else f"Coller les {clip_count} fiches"
                )
        if hasattr(self, "clear_record_button"):
            self.clear_record_button.setEnabled(bool(selected_ids))
            self.clear_record_button.setText(("Leeren" if len(selected_ids) <= 1 else f"Leeren ({len(selected_ids)})") if str(self.language or "fr").lower().startswith("de") else (("Clear" if len(selected_ids) <= 1 else f"Clear ({len(selected_ids)})") if str(self.language or "fr").lower().startswith("en") else ("Vider" if len(selected_ids) <= 1 else f"Vider ({len(selected_ids)})")))
        if hasattr(self, "delete_record_button"):
            # Le bouton reste accessible dès qu'une ou plusieurs fiches réelles
            # sont sélectionnées. La sécurité définitive reste assurée dans
            # delete_selected_tail_records(), qui refuse toute sélection ne
            # respectant pas : Libre + vide + fin de collection.
            self.delete_record_button.setEnabled(bool(selected_ids))
            if str(self.language or "fr").lower().startswith("de"):
                self.delete_record_button.setText("Löschen" if len(selected_ids) <= 1 else f"Löschen ({len(selected_ids)})")
            elif str(self.language or "fr").lower().startswith("en"):
                self.delete_record_button.setText(
                    "Delete" if len(selected_ids) <= 1 else f"Delete ({len(selected_ids)})"
                )
            else:
                self.delete_record_button.setText(
                    "Supprimer" if len(selected_ids) <= 1 else f"Supprimer ({len(selected_ids)})"
                )


    def clear_selected_records(self, *_args) -> None:
        ids = self._selected_record_ids()
        if not ids:
            return
        nums = []
        before = []
        for rid in ids:
            snap = self._snapshot_record(rid)
            if snap:
                before.append(snap)
                nums.append(int((snap.get("record") or {}).get("record_number", 0)))
        if not before:
            return
        label = f"la fiche N° {nums[0]}" if len(nums)==1 else f"les {len(nums)} fiches sélectionnées"
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        if str(self.language or "fr").lower().startswith("en"):
            target = f"record No. {nums[0]}" if len(nums) == 1 else f"the {len(nums)} selected records"
            box.setWindowTitle("Clear records")
            box.setText(
                f"Do you want to completely clear {target}?\n\n"
                "All data and photos will be erased, record numbers will be kept "
                "and the status will change to “Free”.\nThis operation can be undone with Undo."
            )
        elif str(self.language or "fr").lower().startswith("de"):
            target = f"Datensatz Nr. {nums[0]}" if len(nums) == 1 else f"die {len(nums)} ausgewählten Datensätze"
            box.setWindowTitle("Datensätze leeren")
            box.setText(
                f"Möchten Sie {target} vollständig leeren?\n\n"
                "Alle Daten und Fotos werden gelöscht. Die Datensatznummern bleiben erhalten "
                "und der Status wird auf „Frei“ gesetzt.\n"
                "Dieser Vorgang kann mit „Rückgängig“ rückgängig gemacht werden."
            )
        else:
            box.setWindowTitle("Vider les fiches")
            box.setText(
                f"Voulez-vous vider complètement {label} ?\n\n"
                "Toutes les données et photos seront effacées, les N° seront conservés "
                "et l'État passera à « Libre ».\nCette opération pourra être annulée avec Défaire."
            )
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        box.setDefaultButton(QMessageBox.StandardButton.No)
        yes_button = box.button(QMessageBox.StandardButton.Yes)
        no_button = box.button(QMessageBox.StandardButton.No)
        if yes_button is not None:
            yes_button.setText(tr("Oui", self.language))
        if no_button is not None:
            no_button.setText(tr("Non", self.language))
        if box.exec() != QMessageBox.StandardButton.Yes:
            return
        try:
            if not self.referentials.contains(int(self.collection["id"]), "record_state", "Libre", active_only=True):
                self.referentials.add_value(int(self.collection["id"]), "record_state", "Libre")
            for rid in ids:
                self.manager.clear_record_to_free(int(rid), int(self.collection["id"]))
            self._push_history({"type":"clear_many", "record_ids":list(ids), "before":before})
            self.refresh_table()
            # Synchroniser immédiatement toute Fiche déjà ouverte sur cette collection.
            self.recordChanged.emit(int(ids[0]))
            self.statusBar().showMessage(f"{len(ids)} fiche(s) vidée(s) — État : Libre.", 5000)
        except Exception as exc:
            QMessageBox.critical(self, "Vidage impossible", str(exc))

    def delete_selected_tail_records(self, *_args) -> None:
        ids = self._selected_record_ids()
        if not ids:
            return
        ok, reason = self.manager.tail_records_deletable(ids, int(self.collection["id"]))
        if not ok:
            QMessageBox.warning(self, "Suppression impossible", reason)
            return
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        if str(self.language or "fr").lower().startswith("en"):
            box.setWindowTitle("Permanent deletion")
            box.setText(
                f"Permanently delete {len(ids)} empty Free record(s) at the end of the collection?\n\n"
                "Their numbers will be released and the next record will continue after the last retained record.\n"
                "This deletion cannot be undone with Undo."
            )
        elif str(self.language or "fr").lower().startswith("de"):
            box.setWindowTitle("Endgültiges Löschen")
            box.setText(
                f"Möchten Sie {len(ids)} leere Datensätze mit dem Status „Frei“ am Ende der Sammlung endgültig löschen?\n\n"
                "Die Nummern werden freigegeben. Der nächste Datensatz erhält die Nummer nach dem letzten verbleibenden Datensatz.\n"
                "Dieser Löschvorgang kann nicht mit „Rückgängig“ rückgängig gemacht werden."
            )
        else:
            box.setWindowTitle("Suppression définitive")
            box.setText(
                f"Supprimer définitivement {len(ids)} fiche(s) Libre(s) et vide(s) situées en fin de collection ?\n\n"
                "Leurs numéros seront libérés et la prochaine fiche reprendra à la suite de la dernière fiche conservée.\n"
                "Cette suppression n'est pas annulable avec Défaire."
            )
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        box.setDefaultButton(QMessageBox.StandardButton.No)
        yes_button = box.button(QMessageBox.StandardButton.Yes)
        no_button = box.button(QMessageBox.StandardButton.No)
        if yes_button is not None:
            yes_button.setText(tr("Oui", self.language))
        if no_button is not None:
            no_button.setText(tr("Non", self.language))
        if box.exec() != QMessageBox.StandardButton.Yes:
            return
        try:
            count = self.manager.delete_tail_records(ids, int(self.collection["id"]))
            self._undo_stack.clear(); self._redo_stack.clear(); self._update_history_buttons()
            self.refresh_table()
            # Une suppression peut faire disparaître la fiche actuellement affichée :
            # forcer la Fiche ouverte à relire immédiatement la collection.
            self.recordChanged.emit(int(ids[0]))
            self.statusBar().showMessage(f"{count} fiche(s) supprimée(s) définitivement. Numérotation remise à la suite de la dernière fiche.", 6000)
        except Exception as exc:
            QMessageBox.critical(self, "Suppression impossible", str(exc))

    def _select_record_by_id(self, record_id: int) -> None:
        """Resélectionne une fiche après actualisation du Tableau."""
        for row in range(self.table.rowCount()):
            for column in range(self.table.columnCount()):
                item = self.table.item(row, column)
                if item is not None and item.data(Qt.ItemDataRole.UserRole) == int(record_id):
                    self.table.selectRow(row)
                    self.table.scrollToItem(item)
                    return

    RECORD_CLIPBOARD_MIME = "application/x-mm3-record+json"
    RECORDS_CLIPBOARD_MIME = "application/x-mm3-records+json"

    @staticmethod
    def _record_for_clipboard(record: dict) -> dict:
        """Sérialise une fiche complète sans identité de base/numéro."""
        payload = {
            key: value
            for key, value in record.items()
            if key not in {"id", "collection_id", "record_number", "created_at", "updated_at"}
        }
        photo = bytes(payload.get("photo_data") or b"")
        payload["photo_data_b64"] = (
            __import__("base64").b64encode(photo).decode("ascii") if photo else ""
        )
        payload.pop("photo_data", None)
        return payload

    @staticmethod
    def _record_from_payload(payload: dict) -> dict | None:
        if not isinstance(payload, dict):
            return None
        payload = copy.deepcopy(payload)
        try:
            encoded = str(payload.pop("photo_data_b64", "") or "")
            payload["photo_data"] = (
                __import__("base64").b64decode(encoded.encode("ascii"))
                if encoded else None
            )
        except Exception:
            return None
        payload.pop("id", None)
        payload.pop("collection_id", None)
        payload.pop("record_number", None)
        return payload

    @staticmethod
    def _records_from_clipboard() -> list[dict]:
        mime = QApplication.clipboard().mimeData()
        if mime is None:
            return []
        try:
            if mime.hasFormat(TableWindow.RECORDS_CLIPBOARD_MIME):
                raw = bytes(mime.data(TableWindow.RECORDS_CLIPBOARD_MIME)).decode("utf-8")
                payloads = json.loads(raw)
                if isinstance(payloads, list):
                    result = []
                    for payload in payloads:
                        record = TableWindow._record_from_payload(payload)
                        if record is not None:
                            result.append(record)
                    if result:
                        return result
            if mime.hasFormat(TableWindow.RECORD_CLIPBOARD_MIME):
                raw = bytes(mime.data(TableWindow.RECORD_CLIPBOARD_MIME)).decode("utf-8")
                payload = json.loads(raw)
                record = TableWindow._record_from_payload(payload)
                return [record] if record is not None else []
        except Exception:
            return []
        return []

    @staticmethod
    def _record_from_clipboard() -> dict | None:
        records = TableWindow._records_from_clipboard()
        return records[0] if records else None

    def _clipboard_records(self) -> list[dict]:
        records = self._records_from_clipboard()
        if records:
            return records
        if self._records_clipboard:
            return copy.deepcopy(self._records_clipboard)
        if self._record_clipboard:
            return [copy.deepcopy(self._record_clipboard)]
        return []

    def _clipboard_record(self) -> dict | None:
        records = self._clipboard_records()
        return records[0] if records else None

    def _prepare_record_for_copy(self, record_id: int, model_manager: ModelManager) -> dict | None:
        record = self.manager.get_record(int(record_id), int(self.collection["id"]))
        if record is None:
            return None

        model_fields = sorted(model_manager.visible_fields(int(self.collection["id"])))
        record = copy.deepcopy(record)
        record["__mm3_model_fields__"] = model_fields

        custom_defs = []
        visible_source = set(model_fields)
        for definition in model_manager.custom_fields(int(self.collection["id"])):
            key = str(definition.get("field_key", "") or "")
            if not key:
                continue
            custom_defs.append({
                "field_key": key,
                "label": str(definition.get("label", "") or ""),
                "field_type": str(definition.get("field_type", "text") or "text"),
                "initial_group": str(definition.get("initial_group", "Identification") or "Identification"),
                "date_format": str(definition.get("date_format", "JJ/MM/AAAA") or "JJ/MM/AAAA"),
                "visible": key in visible_source,
            })
        record["__mm3_custom_fields__"] = custom_defs
        record["__mm3_custom_values__"] = self.manager.custom_values(int(record_id))
        return record

    def copy_selected_record(self, *_args) -> None:
        """Ctrl+C : copie une ou plusieurs fiches complètes dans le Presse-papiers MM3/Windows."""
        record_ids = self._selected_record_ids()
        if not record_ids:
            return

        model_manager = ModelManager(self.startup.database.database_path)
        records = []
        for record_id in record_ids:
            record = self._prepare_record_for_copy(record_id, model_manager)
            if record is not None:
                records.append(record)
        if not records:
            QMessageBox.warning(self, "Copie impossible", "Les fiches sélectionnées n'existent plus.")
            return

        self._records_clipboard = copy.deepcopy(records)
        self._record_clipboard = copy.deepcopy(records[0])
        self._record_clipboard_number = int(records[0].get("record_number", 0) or 0)

        payloads = [self._record_for_clipboard(record) for record in records]
        mime = QMimeData()
        if len(payloads) == 1:
            mime.setData(
                self.RECORD_CLIPBOARD_MIME,
                QByteArray(json.dumps(payloads[0], ensure_ascii=False).encode("utf-8")),
            )
        mime.setData(
            self.RECORDS_CLIPBOARD_MIME,
            QByteArray(json.dumps(payloads, ensure_ascii=False).encode("utf-8")),
        )
        # Une même copie sert aux deux usages :
        # - formats MIME G-Skol pour recoller des fiches complètes ;
        # - texte TSV standard pour Excel / Calc / autres tableurs.
        tsv = self._selected_records_tsv()
        if tsv:
            mime.setText(tsv)
        QApplication.clipboard().setMimeData(mime)

        self._update_open_button()
        if len(records) == 1:
            self.count_label.setText(
                f"Fiche N° {self._record_clipboard_number} copiée — prête à être collée"
            )
        else:
            self.count_label.setText(
                f"{len(records)} fiches copiées — prêtes à être collées dans une autre collection"
            )

    def _confirm_replace_target(self, target: dict) -> bool:
        state = str(target.get("record_state", "") or "").strip().casefold()
        if state == "libre":
            return True

        number = int(target.get("record_number", 0) or 0)
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle("Remplacer cette fiche ?")
        box.setText(
            f"La fiche N° {number} contient déjà des données.\n\n"
            "Son contenu sera remplacé par la fiche copiée, mais son N° sera conservé.\n"
            "Voulez-vous continuer ?"
        )
        box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        box.setDefaultButton(QMessageBox.StandardButton.No)
        yes_button = box.button(QMessageBox.StandardButton.Yes)
        no_button = box.button(QMessageBox.StandardButton.No)
        if yes_button is not None:
            yes_button.setText("Oui")
        if no_button is not None:
            no_button.setText("Non")
        return box.exec() == QMessageBox.StandardButton.Yes

    def _register_transferred_record(
        self,
        destination_record_id: int,
        source_record: dict,
    ) -> None:
        parent = self.parentWidget()
        register = getattr(parent, "register_transferred_record", None)
        if callable(register):
            register(int(destination_record_id), source_record)

    @staticmethod
    def _transfer_field_label(field: str) -> str:
        if field == "photo_format":
            return "Format photo"
        if field == "photo_data":
            return "Photo"
        spec = FIELD_BY_KEY.get(field)
        return spec.label if spec is not None else field

    def _show_transfer_compatibility(self, source_record: dict, *, replacing: bool) -> None:
        """N'affiche un bilan que si les modèles A et B diffèrent."""
        info = self.manager.transfer_compatibility(
            source_record, replacing=replacing, collection_id=int(self.collection["id"])
        )
        ignored = [self._transfer_field_label(key) for key in info.get("ignored", [])]
        preserved = [self._transfer_field_label(key) for key in info.get("preserved", [])]
        defaulted = [self._transfer_field_label(key) for key in info.get("defaulted", [])]
        if not (ignored or preserved or defaulted):
            return

        lines = ["La fiche a été transférée avec adaptation au modèle de la collection destinataire."]
        if ignored:
            lines.append("\nNon transféré(s), absent(s) de la destination : " + ", ".join(ignored))
        if preserved:
            lines.append("\nConservé(s) dans la fiche destinataire : " + ", ".join(preserved))
        if defaulted:
            lines.append("\nLaissé(s) à la valeur par défaut de la destination : " + ", ".join(defaulted))
        QMessageBox.information(self, "Transfert adapté", "".join(lines))

    def _prepare_destination_custom_fields(self, source_record: dict) -> dict[str, str]:
        """Crée les champs personnalisés source absents de B et retourne source_key -> dest_key.

        Les nouveaux champs restent volontairement hors de la Fiche : ils sont
        disponibles dans la palette jusqu'à ce que l'utilisateur les positionne.
        """
        defs = source_record.get("__mm3_custom_fields__")
        if not isinstance(defs, list):
            return {}

        cid = int(self.collection["id"])
        model_manager = ModelManager(self.startup.database.database_path)
        current_defs = model_manager.custom_fields(cid)
        by_label = {
            str(row.get("label", "") or "").strip().casefold(): dict(row)
            for row in current_defs
        }
        mapping = {}
        created = []

        for raw in defs:
            if not isinstance(raw, dict):
                continue
            source_key = str(raw.get("field_key", "") or "")
            label = str(raw.get("label", "") or "").strip()
            if not source_key or not label:
                continue

            existing = by_label.get(label.casefold())
            if existing is not None:
                mapping[source_key] = str(existing["field_key"])
                continue

            info = model_manager.create_custom_field(
                cid,
                label,
                str(raw.get("field_type", "text") or "text"),
                initial_group=str(raw.get("initial_group", "Identification") or "Identification"),
                date_format=str(raw.get("date_format", "JJ/MM/AAAA") or "JJ/MM/AAAA"),
            )
            dest_key = str(info["field_key"])
            mapping[source_key] = dest_key
            created.append(dest_key)
            by_label[label.casefold()] = dict(info)

        if created:
            visible = set(model_manager.visible_fields(cid))
            visible.difference_update(created)
            model_manager.set_visible_fields(cid, visible)

        return mapping

    def _paste_custom_values(
        self, destination_record_id: int, source_record: dict, mapping: dict[str, str]
    ) -> None:
        raw_values = source_record.get("__mm3_custom_values__")
        if not isinstance(raw_values, dict) or not mapping:
            return
        values = {}
        for source_key, raw_value in raw_values.items():
            dest_key = mapping.get(str(source_key))
            if dest_key is not None:
                values[dest_key] = str(raw_value or "")
        if values:
            self.manager.set_custom_values(int(destination_record_id), values)

    def paste_multiple_as_new_records(self, source_records: list[dict]) -> None:
        """Colle plusieurs fiches comme nouvelles fiches, avec nouveaux N° dans la destination."""
        if not source_records:
            return
        created_ids: list[int] = []
        try:
            for source_record in source_records:
                custom_mapping = self._prepare_destination_custom_fields(source_record)
                created = self.manager.paste_record_as_new(
                    int(self.collection["id"]), source_record
                )
                self._paste_custom_values(int(created["id"]), source_record, custom_mapping)
                self._register_transferred_record(int(created["id"]), source_record)
                created_ids.append(int(created["id"]))
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Collage interrompu",
                f"{len(created_ids)} fiche(s) ont été ajoutée(s) avant l'erreur.\n\n{exc}",
            )
            self.refresh_table()
            return

        self.clear_query(refresh=False)
        self._clear_filters()
        self.refresh_table()
        if created_ids:
            self._select_record_by_id(created_ids[-1])
            self._push_history({
                "type": "paste_new",
                "created_ids": list(created_ids),
                "sources": copy.deepcopy(source_records),
            })
        self.count_label.setText(
            f"{len(created_ids)} fiches collées — nouveaux numéros attribués par la collection"
        )

    def paste_into_selected_record(self, *_args) -> None:
        """Colle une fiche dans la ligne visée, ou plusieurs comme nouvelles fiches."""
        source_records = self._clipboard_records()
        if not source_records:
            QMessageBox.information(
                self,
                "Aucune fiche copiée",
                "Le Presse-papiers ne contient pas de fiche MM3.",
            )
            return
        if len(source_records) > 1:
            self.paste_multiple_as_new_records(source_records)
            return

        source_record = source_records[0]
        target_id = self._selected_record_id()
        # Pas de sélection : sélectionner explicitement la dernière ligne vierge
        # reste la manière la plus claire d'indiquer un ajout.
        if target_id is None:
            return
        if int(target_id) == -1:
            self.paste_as_new_record(source_record)
            return

        target = self.manager.get_record(int(target_id), int(self.collection["id"]))
        if target is None:
            QMessageBox.warning(self, "Collage impossible", "La fiche cible n'existe plus.")
            return
        if not self._confirm_replace_target(target):
            return

        before_snapshot = self._snapshot_record(int(target_id))
        try:
            custom_mapping = self._prepare_destination_custom_fields(source_record)
            updated = self.manager.paste_record_into(
                int(target_id),
                int(self.collection["id"]),
                source_record,
            )
            self._paste_custom_values(int(updated["id"]), source_record, custom_mapping)
        except Exception as exc:
            QMessageBox.critical(self, "Collage impossible", str(exc))
            return

        self._register_transferred_record(int(updated["id"]), source_record)
        after_snapshot = self._snapshot_record(int(updated["id"]))
        if before_snapshot is not None and after_snapshot is not None:
            self._push_history({
                "type": "replace", "before": before_snapshot, "after": after_snapshot
            })
        self._show_transfer_compatibility(source_record, replacing=True)
        self.refresh_table()
        self._select_record_by_id(int(updated["id"]))

    def paste_as_new_record(self, source_record: dict | None = None) -> None:
        """La ligne vierge de fin devient une nouvelle fiche numérotée par la base."""
        source_record = source_record or self._clipboard_record()
        if source_record is None:
            return
        try:
            custom_mapping = self._prepare_destination_custom_fields(source_record)
            created = self.manager.paste_record_as_new(
                int(self.collection["id"]),
                source_record,
            )
            self._paste_custom_values(int(created["id"]), source_record, custom_mapping)
        except Exception as exc:
            QMessageBox.critical(self, "Création impossible", str(exc))
            return

        self._register_transferred_record(int(created["id"]), source_record)
        self._push_history({
            "type": "paste_new",
            "created_ids": [int(created["id"])],
            "sources": [copy.deepcopy(source_record)],
        })
        self._show_transfer_compatibility(source_record, replacing=False)
        self.clear_query(refresh=False)
        self._clear_filters()
        self.refresh_table()
        self._select_record_by_id(int(created["id"]))

    def _paste_shortcut(self) -> None:
        """Ctrl+V : une fiche suit la ligne visée ; plusieurs sont ajoutées comme nouvelles fiches."""
        self.paste_into_selected_record()

    def _open_selected_record(self, *_args) -> None:
        record_id = self._selected_record_id()
        if record_id is not None and int(record_id) > 0:
            self.open_record_callback(record_id)
