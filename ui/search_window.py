#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from core.collection_folders import collection_display_name

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QFormLayout, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QComboBox, QLineEdit, QMainWindow, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from core.record_manager import RecordManager
from ui.collection_theme import collection_theme


class SearchWindow(QMainWindow):
    """Recherche multicritère instantanée de MM3."""

    CRITERIA = (
        ("Nom", "mineral_name", "Ex. : CAL"),
        ("Minéral 2", "mineral_2", ""),
        ("Minéral 3", "mineral_3", ""),
        ("Classe", "mineral_class", ""),
        ("Système cristallin", "crystal_system", ""),
        ("Pays", "country", ""),
        ("Département", "department", ""),
        ("Couleur", "specimen_color", ""),
        ("Qualité", "quality", ""),
        ("État de la fiche", "record_state", ""),
    )

    def __init__(self, startup, collection: dict, open_record_callback: Callable[[int], None], parent=None) -> None:
        super().__init__(parent)
        self.startup = startup
        self.collection = dict(collection)
        self.open_record_callback = open_record_callback
        self.manager = RecordManager(self.startup.database.database_path)
        self.results: list[dict] = []
        self.criteria_edits: dict[str, QLineEdit] = {}
        self.operator_boxes: dict[str, QComboBox] = {}

        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.setWindowTitle(f"Recherche — {collection_display_name(self.collection)}")
        self.resize(1120, 720)
        self.setMinimumSize(900, 560)
        self._build_ui()
        self._apply_style()
        self.refresh_results()

    def _build_ui(self) -> None:
        root = QWidget(); root.setObjectName("searchRoot")
        layout = QVBoxLayout(root); layout.setContentsMargins(18, 16, 18, 16); layout.setSpacing(10)
        title = QLabel("Recherche multicritère"); title.setObjectName("searchTitle")
        subtitle = QLabel("Renseignez un ou plusieurs critères. Les résultats sont actualisés immédiatement et tous les critères actifs se combinent.")
        subtitle.setObjectName("searchSubtitle"); subtitle.setWordWrap(True)
        layout.addWidget(title); layout.addWidget(subtitle)

        frame = QFrame(); frame.setObjectName("searchFrame")
        grid = QGridLayout(frame); grid.setContentsMargins(12, 10, 12, 10); grid.setHorizontalSpacing(10); grid.setVerticalSpacing(7)
        for index, (label_text, field, placeholder) in enumerate(self.CRITERIA):
            col = 0 if index < 5 else 2
            row = index if index < 5 else index - 5
            label = QLabel(label_text)
            criterion = QWidget()
            criterion_layout = QHBoxLayout(criterion)
            criterion_layout.setContentsMargins(0, 0, 0, 0)
            criterion_layout.setSpacing(5)
            edit = QLineEdit(); edit.setClearButtonEnabled(True); edit.setPlaceholderText(placeholder)
            operator = QComboBox()
            operator.setObjectName("operatorBox")
            operator.addItem("Contient", "contient")
            operator.addItem("Commence par", "commence_par")
            operator.addItem("Est exactement", "exactement")
            operator.addItem("Se termine par", "termine_par")
            operator.setToolTip("Mode de comparaison pour ce critère")
            operator.setMinimumWidth(116)
            edit.textChanged.connect(self.refresh_results)
            operator.currentIndexChanged.connect(self.refresh_results)
            self.criteria_edits[field] = edit
            self.operator_boxes[field] = operator
            criterion_layout.addWidget(edit, 1)
            criterion_layout.addWidget(operator)
            grid.addWidget(label, row, col); grid.addWidget(criterion, row, col + 1)
        grid.setColumnStretch(1, 1); grid.setColumnStretch(3, 1)
        layout.addWidget(frame)

        info = QHBoxLayout()
        self.result_label = QLabel(); self.result_label.setObjectName("resultLabel")
        clear_button = QPushButton("Effacer tous les critères"); clear_button.clicked.connect(self._clear_criteria)
        info.addWidget(self.result_label); info.addStretch(1); info.addWidget(clear_button)
        layout.addLayout(info)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["N°", "Nom", "Minéral 2", "Minéral 3", "Classe", "Pays"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True); self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader(); header.setStretchLastSection(True)
        for i, width in enumerate((75, 220, 170, 170, 180)):
            header.resizeSection(i, width)
        self.table.cellDoubleClicked.connect(self._open_selected_record)
        self.table.itemSelectionChanged.connect(self._update_open_button)
        layout.addWidget(self.table, 1)

        actions = QHBoxLayout()
        hint = QLabel("Double-cliquez sur une ligne pour ouvrir la fiche correspondante."); hint.setObjectName("searchHint")
        actions.addWidget(hint); actions.addStretch(1)
        self.open_button = QPushButton("Ouvrir la fiche"); self.open_button.setObjectName("primaryButton"); self.open_button.setEnabled(False)
        self.open_button.clicked.connect(self._open_selected_record)
        close_button = QPushButton("Fermer"); close_button.clicked.connect(self.close)
        actions.addWidget(self.open_button); actions.addWidget(close_button)
        layout.addLayout(actions)
        self.setCentralWidget(root)

    def _apply_style(self) -> None:
        theme = collection_theme(self.startup.database.database_path, self.collection)
        self.setStyleSheet(f"""
        #searchRoot {{ background: {theme['gradient']}; color: #24332B; }}
        #searchTitle {{ font-size: 24px; font-weight: 700; }}
        #searchSubtitle, #searchHint {{ color: #607068; }}
        #searchFrame {{ background: {theme['panel']}; border: 1px solid {theme['border']}; border-radius: 8px; }}
        #resultLabel {{ font-weight: 600; padding: 2px 0; }}
        QLineEdit {{ background: white; border: 1px solid {theme['border']}; border-radius: 6px; padding: 6px 8px; min-height: 21px; }}
        QLineEdit:focus {{ border: 2px solid #496C5B; padding: 5px 7px; }}
        #operatorBox {{ background: {theme['panel2']}; border: 1px solid {theme['border']}; border-radius: 6px; padding: 5px 6px; min-height: 23px; }}
        #operatorBox:hover {{ background: {theme['hover']}; }}
        QTableWidget {{ background: white; alternate-background-color: #F5F8F6; border: 1px solid {theme['border']}; border-radius: 7px; gridline-color: #D9E2DD; }}
        QTableWidget::item {{ padding: 6px; }}
        QTableWidget::item:selected {{ background: {theme['header']}; color: #24332B; }}
        QHeaderView::section {{ background: {theme['header']}; color: #24332B; border: none; border-right: 1px solid {theme['border']}; padding: 7px; font-weight: 650; }}
        QPushButton {{ background: white; color: #24332B; border: 1px solid {theme['border']}; border-radius: 7px; padding: 8px 14px; min-height: 22px; }}
        QPushButton:hover {{ background: {theme['hover']}; }}
        QPushButton:disabled {{ color: #98A39D; background: #F3F5F4; }}
        #primaryButton {{ background: #496C5B; color: white; border-color: #496C5B; }}
        #primaryButton:hover {{ background: #3C5B4C; }}
        """)

    def _criteria(self) -> dict[str, str]:
        return {field: edit.text() for field, edit in self.criteria_edits.items()}

    def _operators(self) -> dict[str, str]:
        return {field: str(box.currentData() or "contient") for field, box in self.operator_boxes.items()}

    def focus_first_criterion(self, select_all: bool = False) -> None:
        edit = next(iter(self.criteria_edits.values()))
        edit.setFocus()
        if select_all:
            edit.selectAll()

    def _clear_criteria(self) -> None:
        for edit in self.criteria_edits.values():
            edit.clear()
        for box in self.operator_boxes.values():
            box.setCurrentIndex(0)
        self.focus_first_criterion()

    def refresh_results(self, *_args) -> None:
        try:
            self.results = self.manager.search_records(int(self.collection["id"]), self._criteria(), self._operators())
        except Exception as exc:
            self.results = []; self.result_label.setText(f"Recherche impossible : {exc}"); self.table.setRowCount(0); return
        self.table.setRowCount(len(self.results))
        for row_index, record in enumerate(self.results):
            values = (record.get("record_number", ""), record.get("mineral_name", ""), record.get("mineral_2", ""), record.get("mineral_3", ""), record.get("mineral_class", ""), record.get("country", ""))
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value or ""))
                if column == 0: item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setData(Qt.ItemDataRole.UserRole, int(record["id"]))
                self.table.setItem(row_index, column, item)
        count = len(self.results)
        self.result_label.setText(f"{count} fiche{'s' if count != 1 else ''} trouvée{'s' if count != 1 else ''}")
        self.table.clearSelection(); self._update_open_button()

    def _selected_record_id(self) -> int | None:
        selected = self.table.selectionModel().selectedRows()
        if not selected: return None
        item = self.table.item(selected[0].row(), 0)
        value = item.data(Qt.ItemDataRole.UserRole) if item else None
        return int(value) if value is not None else None

    def _update_open_button(self) -> None:
        self.open_button.setEnabled(self._selected_record_id() is not None)

    def _open_selected_record(self, *_args) -> None:
        record_id = self._selected_record_id()
        if record_id is not None: self.open_record_callback(record_id)
