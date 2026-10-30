"""First collection dashboard: distribution of records by a chosen field."""
from __future__ import annotations

from collections import Counter
from pathlib import Path

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QComboBox, QDialog, QHBoxLayout, QLabel, QPushButton, QProgressBar,
    QScrollArea, QVBoxLayout, QWidget,
)

from core.field_catalog import FIELD_BY_KEY, field_sort_key
from core.model_manager import ModelManager
from core.record_manager import RecordManager
from core.i18n import tr


class DistributionChart(QWidget):
    """Compact chart; long category lists are grouped only in the graphic."""

    COLORS = ("#537B68", "#BE6D4C", "#D3A948", "#648BA2", "#8A6C9D",
              "#79A083", "#C28E76", "#687C9F", "#A89455", "#779B9B",
              "#A86E7A", "#AAB5A8")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.mode = "barres"
        self.values = []
        self.setMinimumHeight(300)

    def set_distribution(self, values, mode):
        self.mode = mode
        self.values = list(values)
        self.setVisible(mode != "barres" and bool(values))
        self.update()

    def paintEvent(self, event):
        if not self.values:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        visible = self.values[:11]
        if len(self.values) > 11:
            visible.append(("Autres valeurs", sum(count for _, count in self.values[11:])))
        total = sum(count for _, count in visible)
        if self.mode == "secteurs":
            side = min(self.height() - 28, self.width() * .48)
            area = QRectF(16, 14, side, side)
            angle = 90 * 16
            for index, (_label, count) in enumerate(visible):
                painter.setBrush(QColor(self.COLORS[index % len(self.COLORS)]))
                painter.setPen(Qt.PenStyle.NoPen)
                sweep = -round(count / total * 360 * 16)
                painter.drawPie(area, angle, sweep)
                angle += sweep
            x = area.right() + 25
            for index, (label, count) in enumerate(visible):
                y = 25 + index * 23
                painter.fillRect(int(x), y, 13, 13, QColor(self.COLORS[index % len(self.COLORS)]))
                shown = painter.fontMetrics().elidedText(label, Qt.TextElideMode.ElideRight,
                                                          max(85, int(self.width() - x - 100)))
                painter.setPen(QColor("#24332B"))
                painter.drawText(int(x) + 20, y + 12, f"{shown}  {count / total:.0%}")
        elif self.mode == "colonnes":
            left, top = 35, 22
            bottom = self.height() - 60
            height = max(1, bottom - top)
            maximum = max(count for _, count in visible)
            width = max(15, (self.width() - left - 20) / len(visible))
            painter.setPen(QColor("#7F9389"))
            painter.drawLine(left, bottom, self.width() - 10, bottom)
            for index, (label, count) in enumerate(visible):
                x = left + index * width + 5
                bar_height = height * count / maximum
                painter.fillRect(QRectF(x, bottom - bar_height, max(5, width - 10), bar_height),
                                 QColor(self.COLORS[index % len(self.COLORS)]))
                painter.setPen(QColor("#24332B"))
                painter.drawText(QRectF(x, bottom - bar_height - 22, width - 10, 20),
                                 Qt.AlignmentFlag.AlignCenter, str(count))
                short = painter.fontMetrics().elidedText(label, Qt.TextElideMode.ElideRight,
                                                         max(15, int(width - 6)))
                painter.drawText(QRectF(x - 3, bottom + 5, width, 42),
                                 Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, short)
        painter.end()


class DashboardDialog(QDialog):
    def __init__(self, db_path: Path, collection: dict, parent=None, language: str = "fr"):
        super().__init__(parent)
        self.language = str(language or "fr")
        self.setWindowTitle(f"{tr('Statistiques rapides', self.language)} — {collection['name']}")
        self.resize(850, 620)
        self.collection_id = int(collection["id"])
        self.records = RecordManager(db_path)
        manager = ModelManager(db_path)
        custom = {row["field_key"]: row["label"] for row in manager.custom_fields(self.collection_id)}
        labels = manager.custom_labels(self.collection_id)
        visible = manager.visible_fields(self.collection_id)

        root = QVBoxLayout(self)
        title = QLabel(tr("Répartition des fiches par champ", self.language))
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        root.addWidget(title)
        controls = QHBoxLayout()
        controls.addWidget(QLabel(tr("Champ :", self.language)))
        self.field = QComboBox()
        for key in sorted(visible, key=lambda k: field_sort_key(labels.get(k, custom.get(k, FIELD_BY_KEY[k].label if k in FIELD_BY_KEY else k)))):
            if key in FIELD_BY_KEY or key in custom:
                self.field.addItem(labels.get(key, custom.get(key, FIELD_BY_KEY[key].label if key in FIELD_BY_KEY else key)), key)
        controls.addWidget(self.field, 1)
        controls.addWidget(QLabel(tr("Graphique :", self.language)))
        self.chart_type = QComboBox()
        self.chart_type.addItem(tr("Barres horizontales", self.language), "barres")
        self.chart_type.addItem(tr("Colonnes", self.language), "colonnes")
        self.chart_type.addItem(tr("Secteurs", self.language), "secteurs")
        controls.addWidget(self.chart_type)
        refresh = QPushButton(tr("Actualiser", self.language))
        refresh.clicked.connect(self.refresh)
        controls.addWidget(refresh)
        root.addLayout(controls)
        self.summary = QLabel()
        root.addWidget(self.summary)
        self.chart = DistributionChart()
        root.addWidget(self.chart)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.content = QWidget()
        self.rows = QVBoxLayout(self.content)
        self.scroll.setWidget(self.content)
        root.addWidget(self.scroll, 1)
        close = QPushButton(tr("Fermer", self.language))
        close.clicked.connect(self.accept)
        root.addWidget(close, 0, Qt.AlignmentFlag.AlignRight)
        self.field.currentIndexChanged.connect(self.refresh)
        self.chart_type.currentIndexChanged.connect(self.refresh)
        for preferred in ("contact", "site_name", "mineral_name"):
            index = self.field.findData(preferred)
            if index >= 0:
                self.field.setCurrentIndex(index)
                break
        self.refresh()

    def refresh(self, _index=None):
        key = self.field.currentData()
        if not key:
            return
        records = self.records.list_records_light(self.collection_id)
        custom_values = self.records.custom_values_for_collection(self.collection_id) if key not in FIELD_BY_KEY else {}
        counts = Counter()
        for record in records:
            value = (custom_values.get(int(record["id"]), {}).get(key, "")
                     if custom_values else record.get(key, ""))
            counts[str(value or "").strip() or tr("(sans valeur)", self.language)] += 1
        self.summary.setText(tr("{records} fiche(s) · {values} valeur(s) distincte(s)", self.language).format(records=len(records), values=len(counts)))
        while self.rows.count():
            item = self.rows.takeAt(0)
            if item.widget():
                # Retirer immédiatement l’ancienne ligne de la zone d’affichage.
                # deleteLater() seul laissait brièvement l’ancien widget visible
                # et il se superposait aux nouvelles lignes lors d’un Actualiser
                # ou d’un changement de type de graphique.
                old = item.widget()
                old.hide()
                old.setParent(None)
                old.deleteLater()
        maximum = max(counts.values(), default=1)
        ordered = sorted(counts.items(), key=lambda pair: (-pair[1], field_sort_key(pair[0])))
        mode = self.chart_type.currentData()
        self.chart.set_distribution(ordered, mode)
        for value, count in ordered:
            line = QWidget()
            row = QHBoxLayout(line)
            row.setContentsMargins(4, 3, 4, 3)
            label = QLabel(value)
            label.setMinimumWidth(210)
            label.setWordWrap(True)
            row.addWidget(label, 2)
            if mode == "barres":
                bar = QProgressBar()
                bar.setRange(0, maximum)
                bar.setValue(count)
                bar.setFormat(f"{count}  ({count / len(records):.0%})")
                # Barre statistique volontairement statique : le style natif Windows
                # anime la zone remplie comme un indicateur de progression, ce qui
                # donne ici un faux effet de sablier. Un chunk uni supprime toute
                # animation tout en conservant exactement la longueur statistique.
                bar.setStyleSheet(
                    "QProgressBar { border: 1px solid #b8b8b8; background: #eeeeee; "
                    "text-align: right; padding-right: 3px; } "
                    "QProgressBar::chunk { background: #00b32d; margin: 0px; }"
                )
                row.addWidget(bar, 3)
            else:
                row.addWidget(QLabel(tr("{count} fiche(s)  ·  {percent}", self.language).format(count=count, percent=f"{count / len(records):.0%}")), 3)
            self.rows.addWidget(line)
        self.rows.addStretch(1)
