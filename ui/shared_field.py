#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Champ visuel commun MM3 : Atelier = vraie Fiche.

Le même conteneur QFrame reçoit :
- un widget de libellé,
- un widget de donnée,
avec exactement le même layout dans les deux modes.

Mode Atelier : libellé + QLabel "Exemple".
Mode Fiche   : libellé réel + widget de saisie réel.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QSizePolicy, QWidget

from core.layout_engine import FIELD_LABEL_WIDTH, scaled


class SharedFieldFrame(QFrame):
    """Conteneur visuel unique d'un champ MM3."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._label_widget = None
        self._data_widget = None
        self._scale = 1.0
        self._part_geometry = {"label": None, "data": None}

        self._field_layout = QHBoxLayout(self)
        self._field_layout.setContentsMargins(0, 0, 0, 0)
        self._field_layout.setSpacing(0)
        self._field_layout.setSizeConstraint(QHBoxLayout.SizeConstraint.SetNoConstraint)

        self.setMinimumSize(0, 0)
        self.setMaximumSize(16777215, 16777215)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)

        # Le shell est transparent ; il ne doit jamais contaminer le style
        # natif du widget de saisie réel.
        self.setStyleSheet("SharedFieldFrame { background: transparent; border: none; }")

    def set_scale(self, scale: float) -> None:
        self._scale = max(0.01, float(scale))
        self._apply_parts_geometry()

    def set_part_geometry(self, *, label_x=None, label_w=None, data_x=None, data_w=None) -> None:
        self._part_geometry["label"] = None if label_x is None or label_w is None else (int(label_x), max(20, int(label_w)))
        self._part_geometry["data"] = None if data_x is None or data_w is None else (int(data_x), max(20, int(data_w)))
        self._apply_parts_geometry()

    def part_rect(self, part: str):
        widget = self._label_widget if part == "label" else self._data_widget
        return widget.geometry() if widget is not None else None

    def set_widgets(self, label_widget: QWidget, data_widget: QWidget) -> None:
        """Installe les deux widgets réels dans le conteneur commun."""
        if self._label_widget is label_widget and self._data_widget is data_widget:
            self._apply_parts_geometry()
            return

        # Retirer proprement les anciens widgets du layout sans les supprimer.
        while self._field_layout.count():
            item = self._field_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)

        self._label_widget = label_widget
        self._data_widget = data_widget

        label_widget.setParent(self)
        data_widget.setParent(self)

        try:
            label_widget.setMinimumSize(0, 0)
            label_widget.setMaximumSize(16777215, 16777215)
            data_widget.setMinimumSize(0, 0)
            data_widget.setMaximumSize(16777215, 16777215)
            label_widget.setSizePolicy(
                QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Ignored
            )
            data_widget.setSizePolicy(
                QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored
            )
        except Exception:
            pass

        self._field_layout.addWidget(label_widget)
        self._field_layout.addWidget(data_widget, 1)

        # Les widgets réels gardent intégralement leur propre moteur de peinture
        # (QLineEdit, QComboBox, etc.). Le shell ne modifie aucun attribut de fond.
        self._apply_parts_geometry()

    def _apply_parts_geometry(self) -> None:
        if self._label_widget is None or self._data_widget is None:
            return

        default_label_w = max(20, scaled(FIELD_LABEL_WIDTH, self._scale))
        label_spec = self._part_geometry.get("label")
        data_spec = self._part_geometry.get("data")

        if label_spec is None:
            label_x = 0
            label_w = min(max(20, self.width() - 20), default_label_w)
        else:
            label_x = scaled(label_spec[0], self._scale)
            label_w = max(20, scaled(label_spec[1], self._scale))

        if data_spec is None:
            data_x = label_x + label_w
            data_w = max(20, self.width() - data_x)
        else:
            data_x = scaled(data_spec[0], self._scale)
            data_w = max(20, scaled(data_spec[1], self._scale))

        self._field_layout.setEnabled(False)
        self._label_widget.setGeometry(int(label_x), 0, int(label_w), max(1, self.height()))
        self._data_widget.setGeometry(int(data_x), 0, int(data_w), max(1, self.height()))

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._apply_parts_geometry()
