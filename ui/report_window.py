#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from core.calculation_formula import normalize as normalize_calculation_formula
from core.collection_folders import collection_display_name

import json
import html
import re
import ast
import unicodedata
from collections import defaultdict
from pathlib import Path

from PySide6.QtCore import QDate, Qt, QEvent, QTimer, QMarginsF, QSize, QMimeData, QPoint
from PySide6.QtGui import QAction, QTextDocument, QTextTable, QTextFormat, QPageLayout, QColor, QFont, QFontDatabase, QTextTableCellFormat, QTextFrameFormat, QTextOption, QTextLength, QBrush, QPainter, QPen, QFontMetricsF, QDrag
from PySide6.QtPrintSupport import QPrinter, QPrintPreviewDialog, QPrintPreviewWidget, QPrintDialog
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView, QComboBox, QFontComboBox, QDialog, QDialogButtonBox, QFrame, QFormLayout,
    QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QFileDialog, QScrollArea,
    QListWidgetItem, QTreeWidget, QTreeWidgetItem, QMainWindow, QMessageBox, QPushButton, QToolButton, QRadioButton,
    QStackedWidget, QTextBrowser, QTableWidget, QTableWidgetItem, QHeaderView,
    QInputDialog, QCheckBox, QColorDialog, QSpinBox, QMenu,
    QVBoxLayout, QWidget, QSizePolicy, QSpacerItem, QGraphicsOpacityEffect, QToolBar, QWidgetAction,
)

from core.record_manager import RecordManager
from ui.collection_theme import collection_theme
from core.field_catalog import REPORT_COLUMNS, FIELD_BY_KEY, field_sort_key
from core.model_manager import ModelManager
from core.i18n import tr, display_native_value, translate_widget_tree
from core.collection_saved_models import load as load_collection_models, save as save_collection_models
from core.model_library import library_root, write_model, read_model, collect_model_field_keys, build_field_manifest
from ui.model_library_dialog import choose_model_save_path, choose_model_open_path, resolve_model_fields
from ui.saved_model_folders import choose_folder, manage_folders
from core import saved_model_folders as model_folders
from ui.table_window import TableWindow
from ui.color_dialog import choose_color as mm3_choose_color


def _mm3_is_record_state_label(value) -> bool:
    """Reconnaît le libellé système État de la fiche, accents/casse indifférents."""
    text = str(value or "").strip().casefold()
    text = text.replace("é", "e").replace("è", "e").replace("ê", "e").replace("ë", "e")
    return text == "etat de la fiche"


FIELDS = REPORT_COLUMNS
LABELS = {field: label for label, field in FIELDS}


def _escape(value) -> str:
    return (
        str(value or "").replace("&", "&amp;").replace("<", "&lt;")
        .replace(">", "&gt;").replace('"', "&quot;")
    )


def _number(value) -> float:
    text = str(value or "").strip().replace("€", "").replace(" ", "").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return 0.0

def _detail_display_value(field, value, language="fr") -> str:
    """Valeur d'état détaillé traduite à l'affichage, sans modifier la donnée stockée."""
    raw = str(value or "").strip()
    if str(field or "") in {"price", "total_cost"}:
        number = _number(value)
        text = f"{number:.2f}"
        return text if str(language or "fr").lower().startswith("en") else text.replace(".", ",")
    if not raw:
        return ""
    return display_native_value(raw, language)


def _summary_format_date_text(value, mode):
    """Format d'affichage d'une date dans un état, sans modifier la donnée."""
    text = str(value or "").strip()
    if not text or not mode or mode == "default":
        return text
    parsed = None
    for fmt in ("dd/MM/yyyy", "d/M/yyyy", "yyyy-MM-dd", "yyyy/MM/dd"):
        d = QDate.fromString(text, fmt)
        if d.isValid():
            parsed = d; break
    if parsed is None:
        return text
    formats = {
        "dd/MM/yyyy": "dd/MM/yyyy", "dd/MM/yy": "dd/MM/yy",
        "MM/yyyy": "MM/yyyy", "yyyy": "yyyy",
        "dd-MM-yyyy": "dd-MM-yyyy", "yyyy-MM-dd": "yyyy-MM-dd",
    }
    return parsed.toString(formats.get(str(mode), "dd/MM/yyyy"))


def _summary_rich_cell_html(value, style):
    """Valeur + préfixe/suffixe avec style du libellé libre indépendant."""
    st = dict(style or {})
    ls = dict(st.get("label_style") or {})
    def span(txt, cfg):
        if txt in (None, ""):
            return ""
        fam=_escape(cfg.get("font_family") or "Arial"); size=int(cfg.get("font_size", 9)); col=_escape(cfg.get("text_color") or "#111111")
        weight="700" if cfg.get("bold") else "400"; italic="italic" if cfg.get("italic") else "normal"
        return f'<span style="font-family:{fam};font-size:{size}pt;font-weight:{weight};font-style:{italic};color:{col};white-space:pre;">{_escape(txt)}</span>'
    return span(st.get("prefix") or "", ls) + span(value, st) + span(st.get("suffix") or "", ls)

def _summary_chip_html(value, style):
    """Dans la Construction, distingue visuellement les libellés libres des champs."""
    st = dict(style or {})
    ls = dict(st.get("label_style") or {})
    def span(txt, cfg):
        if txt in (None, ""):
            return ""
        fam=_escape(cfg.get("font_family") or "Arial"); size=int(cfg.get("font_size", 9)); col=_escape(cfg.get("text_color") or "#111111")
        weight="700" if cfg.get("bold") else "400"; italic="italic" if cfg.get("italic") else "normal"
        return f'<span style="font-family:{fam};font-size:{size}pt;font-weight:{weight};font-style:{italic};color:{col};white-space:pre;">{_escape(txt)}</span>'
    pref = st.get("prefix") or ""; suff = st.get("suffix") or ""
    # Parenthèses uniquement dans l'Atelier ; elles ne font pas partie de l'État final.
    return span(("(" + pref + ")") if pref else "", ls) + span(value, st) + span(("(" + suff + ")") if suff else "", ls)


class SummaryFieldChip(QWidget):
    """Pastille déplaçable d'un champ déjà placé dans la construction."""
    def __init__(self, field, text, role, style=None, parent=None):
        super().__init__(parent)
        self.field = str(field); self.role = str(role); self._press_pos = None
        self.resize_callback = None; self._resize_start = None
        self.reorder_callback = None
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        lay = QHBoxLayout(self); lay.setContentsMargins(7, 1, 7, 1); lay.setSpacing(3)
        self.label = QLabel(str(text)); self.label.setObjectName("chipLabel")
        lay.addWidget(self.label)
        self._grip = None
        self.apply_style(style or {})
        self.setStyleSheet("SummaryFieldChip { background:white; border:1px solid #C8D0CC; border-radius:2px; }")
    def enable_resize(self, callback):
        self.resize_callback = callback
        if self._grip is None:
            grip = QLabel("↔", self)
            grip.setAlignment(Qt.AlignCenter)
            grip.setFixedWidth(16)
            grip.setCursor(Qt.CursorShape.SizeHorCursor)
            grip.setStyleSheet("QLabel { background:#E6EFEB; color:#34584C; border-left:1px solid #839A90; font-weight:bold; }")
            grip.installEventFilter(self)
            self.layout().addWidget(grip)
            self._grip = grip
    def eventFilter(self, watched, event):
        if watched is self._grip:
            if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.LeftButton:
                self._resize_start = (event.globalPosition().x(), self.width())
                return True
            if event.type() == QEvent.Type.MouseMove and self._resize_start is not None:
                origin, width = self._resize_start
                self.setFixedWidth(max(28, min(480, int(width + event.globalPosition().x() - origin))))
                return True
            if event.type() == QEvent.Type.MouseButtonRelease and self._resize_start is not None:
                self._resize_start = None
                self.resize_callback(self.field, self.width())
                return True
        return super().eventFilter(watched,event)
    def apply_style(self, style):
        f = QFont(str(style.get("font_family") or "Arial"))
        f.setPointSize(int(style.get("font_size", 9)))
        f.setBold(bool(style.get("bold", False))); f.setItalic(bool(style.get("italic", False)))
        self.label.setFont(f)
        # Afficher aussi le libellé libre dans la Construction, avec son style propre.
        base_text = self.label.text()
        if style.get("prefix") or style.get("suffix"):
            self.label.setTextFormat(Qt.TextFormat.RichText)
            self.label.setText(_summary_chip_html(base_text, style))
        _chip_color = str(style.get("text_color") or "#111111")
        self.label.setStyleSheet(f"QLabel {{ border:0; background:transparent; color:{_chip_color}; }}")
        a=str(style.get("align") or "left")
        self.label.setAlignment((Qt.AlignHCenter if a=='center' else Qt.AlignRight if a=='right' else Qt.AlignLeft)|Qt.AlignVCenter)
    def mousePressEvent(self,event):
        if event.button()==Qt.LeftButton:
            self._press_pos=event.position().toPoint()
            if self.resize_callback and event.position().x() >= self.width()-9:
                self._resize_start=(event.globalPosition().x(),self.width())
                event.accept(); return
        super().mousePressEvent(event)
    def mouseMoveEvent(self,event):
        if self.resize_callback and self._resize_start is not None:
            origin,width=self._resize_start
            self.setFixedWidth(max(70,min(480,int(width+event.globalPosition().x()-origin))))
            event.accept(); return
        if self.resize_callback and not (event.buttons() & Qt.LeftButton):
            self.setCursor(Qt.CursorShape.SizeHorCursor if event.position().x() >= self.width()-9 else Qt.CursorShape.ArrowCursor)
        if not (event.buttons() & Qt.LeftButton) or self._press_pos is None: return
        if (event.position().toPoint()-self._press_pos).manhattanLength() < QApplication.startDragDistance(): return
        mime=QMimeData(); mime.setData("application/x-mm3-summary-field", f"{self.field}\t{self.role}".encode("utf-8"))
        drag=QDrag(self); drag.setMimeData(mime); drag.exec(Qt.MoveAction)
    def mouseReleaseEvent(self,event):
        if self._resize_start is not None:
            self._resize_start=None; self._press_pos=None
            self.resize_callback(self.field,self.width())
            event.accept(); return
        self._press_pos=None
        super().mouseReleaseEvent(event)
    def keyPressEvent(self,event):
        if self.reorder_callback and event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right):
            self.reorder_callback(self.field, -1 if event.key()==Qt.Key.Key_Left else 1)
            event.accept(); return
        super().keyPressEvent(event)


class DetailFreeRow(QWidget):
    """Atelier horizontal sans QHBoxLayout : chaque élément garde sa position."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(42)
        self._items = {}
        self._store = None
        self._drag = None
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.drop_callback = None
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if self.drop_callback and (event.mimeData().hasFormat("application/x-mm3-summary-field") or isinstance(event.source(), QListWidget)):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        if self.drop_callback:
            source = event.source()
            field = ""
            if event.mimeData().hasFormat("application/x-mm3-summary-field"):
                field = bytes(event.mimeData().data("application/x-mm3-summary-field")).decode("utf-8").split("\t", 1)[0]
            elif isinstance(source, QListWidget) and source.currentItem():
                field = str(source.currentItem().data(Qt.UserRole) or "")
            if field and self.drop_callback(field):
                event.acceptProposedAction()
                return
        event.ignore()

    def clear_items(self):
        self._drag = None
        for item in list(self._items.values()):
            item.removeEventFilter(self)
            for child in item.findChildren(QWidget):
                child.removeEventFilter(self)
            item.hide()
            item.deleteLater()
        self._items.clear()

    def add_item(self, field, widget, x, store):
        field = str(field)
        self._store = store
        widget.setParent(self)
        widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        widget.setProperty("detail_free_field", field)
        widget.installEventFilter(self)
        # Les clics arrivent sur les enfants (QLineEdit, QLabel), pas sur
        # le conteneur : filtrer aussi les enfants, sauf la poignée de taille.
        for child in widget.findChildren(QWidget):
            if isinstance(child, HorizontalResizeGrip):
                continue
            if child.objectName() == "detail_resize_grip":
                continue
            child.installEventFilter(self)
        self._items[field] = widget
        widget.move(max(0, int(x)), 4)
        widget.show()
        self._ensure_width()

    def _ensure_width(self):
        # Pas de repositionnement des voisins, même si la ligne déborde.
        right = max((w.x() + w.width() + 12 for w in self._items.values()), default=240)
        self.setMinimumWidth(max(240, right))

    def _select(self, widget):
        for other in self._items.values():
            other.setProperty("detail_selected", other is widget)
            other.setProperty("detail_selected", other is widget)
        widget.setFocus(Qt.FocusReason.MouseFocusReason)
        widget.setCursor(Qt.CursorShape.OpenHandCursor)

    def _move(self, widget, x):
        x = max(0, int(x))
        widget.move(x, 4)
        field = str(widget.property("detail_free_field") or "")
        if self._store and field:
            self._store(field, x)
        self._ensure_width()

    def eventFilter(self, watched, event):
        # Les événements de souris et clavier appartiennent souvent au
        # QLineEdit/QLabel enfant, et non au holder placé sur la ligne libre.
        holder = watched
        while holder is not None and holder not in self._items.values():
            holder = holder.parentWidget() if isinstance(holder, QWidget) else None
        if holder is not None:
            typ = event.type()
            if typ == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                self._select(holder)
                self._drag = (holder, event.globalPosition().x(), holder.x())
                return True
            if typ == QEvent.Type.MouseMove and self._drag and self._drag[0] is holder:
                if event.buttons() & Qt.MouseButton.LeftButton:
                    _, start, x = self._drag
                    self._move(holder, x + event.globalPosition().x() - start)
                    holder.setCursor(Qt.CursorShape.ClosedHandCursor)
                    return True
            if typ == QEvent.Type.MouseButtonRelease and self._drag and self._drag[0] is holder:
                self._drag = None
                holder.setCursor(Qt.CursorShape.OpenHandCursor)
                return True
            if typ == QEvent.Type.KeyPress and event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right):
                self._move(holder, holder.x() + (-1 if event.key() == Qt.Key.Key_Left else 1))
                return True
        return super().eventFilter(watched, event)


class DetailLabelEdit(QLineEdit):
    """Libellé du constructeur détaillé : déplacement horizontal sans toucher à sa largeur."""
    def __init__(self, field, reorder_callback, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.detail_field=str(field); self.reorder_callback=reorder_callback; self._drag_start=None
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton:
            self._drag_start=event.position().toPoint()
        super().mousePressEvent(event)
    def mouseMoveEvent(self,event):
        # Les libellés suivent l'ordre des champs liés : conserver ici le
        # comportement natif du QLineEdit pour permettre sélection/édition.
        super().mouseMoveEvent(event)
    def keyPressEvent(self,event):
        # Flèches = déplacement du curseur dans le libellé, pas réordonnancement.
        super().keyPressEvent(event)

class DetailLabelRow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent); self.setAcceptDrops(True); self.reorder_callback=None
    def dragEnterEvent(self,event):
        if event.mimeData().hasFormat("application/x-mm3-detail-label"): event.acceptProposedAction()
        else: event.ignore()
    def dropEvent(self,event):
        if not self.reorder_callback: event.ignore(); return
        field=bytes(event.mimeData().data("application/x-mm3-detail-label")).decode("utf-8")
        before=None
        lay=self.layout()
        for i in range(lay.count() if lay else 0):
            holder=lay.itemAt(i).widget()
            if holder is None: continue
            edit=holder if isinstance(holder,DetailLabelEdit) else holder.findChild(DetailLabelEdit)
            if edit is not None and edit.detail_field != field and event.position().x() < holder.geometry().center().x():
                before=edit.detail_field; break
        self.reorder_callback(field,before); event.acceptProposedAction()

class HorizontalResizeGrip(QPushButton):
    """Poignée ↔ : glisser horizontalement redimensionne le widget associé."""
    def __init__(self, target, callback=None, parent=None):
        super().__init__("↔", parent)
        self.target=target; self.callback=callback; self._start=None
        self.setFixedWidth(18); self.setCursor(Qt.CursorShape.SizeHorCursor)
        self.setStyleSheet("QPushButton { background:#E6EFEB; color:#34584C; border:1px solid #839A90; font-weight:bold; padding:0; }")
    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton:
            self._start=(event.globalPosition().x(), self.target.width()); event.accept(); return
        super().mousePressEvent(event)
    def mouseMoveEvent(self,event):
        if self._start is not None:
            x,w=self._start; value=max(70,min(480,int(w+event.globalPosition().x()-x)))
            self.target.setFixedWidth(value)
            holder=self.parentWidget()
            if holder is not None: holder.setFixedWidth(value+18)
            if self.callback: self.callback(value)
            event.accept(); return
        super().mouseMoveEvent(event)
    def mouseReleaseEvent(self,event):
        if self._start is not None:
            self._start=None; event.accept(); return
        super().mouseReleaseEvent(event)


class SummaryDropLane(QFrame):
    """Zone horizontale de dépôt pour l'atelier graphique des états résumés."""
    def __init__(self, role: str, drop_callback, remove_callback=None, format_callback=None, parent=None):
        super().__init__(parent)
        self.role = role; self.drop_callback = drop_callback; self.remove_callback = remove_callback; self.format_callback = format_callback; self.reorder_callback = None
        self.setAcceptDrops(True); self.setMinimumHeight(42); self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("QFrame { background:#FAFBFA; border:1px solid #AEBBB5; }")
        self.row=QHBoxLayout(self); self.row.setContentsMargins(8,4,8,4); self.row.setSpacing(8); self.row.addStretch(1)
    def dragEnterEvent(self,event):
        src=event.source()
        if (isinstance(src,QListWidget) and src.currentItem() is not None) or event.mimeData().hasFormat("application/x-mm3-summary-field"): event.acceptProposedAction()
        else: event.ignore()
    def dragMoveEvent(self,event): event.acceptProposedAction()
    def dropEvent(self,event):
        src=event.source(); field=""; label=""
        if event.mimeData().hasFormat("application/x-mm3-summary-field"):
            raw=bytes(event.mimeData().data("application/x-mm3-summary-field")).decode("utf-8"); field=raw.split("\t",1)[0]
            label=getattr(src,"label",QLabel(field)).text() if src else field
        elif isinstance(src,QListWidget) and src.currentItem() is not None:
            item=src.currentItem(); field=str(item.data(Qt.UserRole) or ""); label=str(item.data(Qt.UserRole+1) or item.text() or field)
        if field and isinstance(src, SummaryFieldChip) and src.role == self.role and self.reorder_callback:
            before = None
            for i in range(self.row.count()):
                w = self.row.itemAt(i).widget()
                if isinstance(w, SummaryFieldChip) and w.field != field and event.position().x() < w.geometry().center().x():
                    before = w.field; break
            self.reorder_callback(field, before)
            event.acceptProposedAction()
        elif field and self.drop_callback(field,label,self.role): event.acceptProposedAction()
        else: event.ignore()
    def set_chips(self,chips, styles=None, vertical_align=None):
        styles=styles or {}
        while self.row.count():
            it=self.row.takeAt(0); w=it.widget()
            if w is not None: w.deleteLater()
        for chip in chips:
            text,color=chip[0],chip[1]; field=chip[2] if len(chip)>2 else text
            style=dict(styles.get(str(field)) or {}); style.setdefault("text_color",color)
            box=SummaryFieldChip(field,text,self.role,style,self)
            if self.reorder_callback:
                box.reorder_callback = lambda f, direction, lane=self: lane.reorder_callback(f, direction)
            box.setContextMenuPolicy(Qt.CustomContextMenu)
            def _menu(pos,f=str(field),b=box):
                menu=QMenu(b); menu.setStyleSheet("QMenu { background:white; color:#111; border:1px solid #AEBBB5; } QMenu::item { padding:5px 24px 5px 10px; background:white; color:#111; } QMenu::item:selected { background:#DCEAF5; color:#111; }")
                _lang=str(self.property("gskolLanguage") or "fr")
                fmt=menu.addAction(tr("Mise en forme…", _lang)) if self.format_callback else None
                reset=menu.addAction(tr("Rétablir la mise en forme par défaut", _lang)) if self.format_callback else None
                if self.format_callback: menu.addSeparator()
                remove=menu.addAction(tr("Retirer de la construction", _lang)) if self.remove_callback else None
                chosen=menu.exec(b.mapToGlobal(pos))
                if chosen==fmt: self.format_callback(f,self.role,False)
                elif chosen==reset: self.format_callback(f,self.role,True)
                elif chosen==remove: self.remove_callback(f,self.role)
            box.customContextMenuRequested.connect(_menu)
            if vertical_align in {"top", "center", "bottom"}:
                box.setFixedHeight(max(28, box.sizeHint().height()))
                position = (Qt.AlignTop if vertical_align == "top" else
                            Qt.AlignBottom if vertical_align == "bottom" else Qt.AlignVCenter)
                self.row.addWidget(box, 0, position)
            else:
                self.row.addWidget(box)
        self.row.addStretch(1)


class SummaryMetricLabel(QLabel):
    """Total du constructeur déplaçable dans sa propre ligne."""
    def __init__(self, text, field, parent=None):
        super().__init__(text, parent)
        self.metric_field = str(field); self._press_pos = None
        self._resize_callback = None
        self._resize_start = None
        self._resize_grip = None
        self._move_callback = None
        self._drag_origin = None
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    def enable_resize(self, callback, width=None):
        self._resize_callback = callback
        natural = self.sizeHint().width() + 20
        self.setFixedWidth(max(55, min(480, int(width or natural))))
        self.setContentsMargins(0, 0, 18, 0)
        if self._resize_grip is None:
            grip = QLabel("↔", self)
            grip.setObjectName("metricResizeGrip")
            grip.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grip.setFixedWidth(16)
            grip.setCursor(Qt.CursorShape.SizeHorCursor)
            grip.setStyleSheet("QLabel#metricResizeGrip { color:#34584C; background:#E6EFEB; border:1px solid #839A90; font-weight:bold; }")
            grip.installEventFilter(self)
            self._resize_grip = grip
        self._resize_grip.setGeometry(self.width() - 16, 0, 16, max(20, self.height()))
        self._resize_grip.show()
        self._resize_grip.raise_()
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._resize_grip is not None:
            self._resize_grip.setGeometry(self.width() - 16, 0, 16, self.height())
    def eventFilter(self, watched, event):
        if watched is self._resize_grip:
            if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                self._resize_start = (event.globalPosition().x(), self.width())
                return True
            if event.type() == QEvent.Type.MouseMove and self._resize_start is not None:
                x, width = self._resize_start
                self.setFixedWidth(max(55, min(480, int(width + event.globalPosition().x() - x))))
                return True
            if event.type() == QEvent.Type.MouseButtonRelease and self._resize_start is not None:
                self._resize_start = None
                self._resize_callback(self.metric_field, self.width())
                return True
        return super().eventFilter(watched, event)
    def enable_move(self, callback):
        self._move_callback = callback
        self.setCursor(Qt.CursorShape.OpenHandCursor)
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setFocus(Qt.FocusReason.MouseFocusReason)
            self._press_pos = event.position().toPoint()
            self._drag_origin = self.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        super().mousePressEvent(event)
    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.MouseButton.LeftButton) or self._press_pos is None: return
        if self._move_callback is not None and self._drag_origin is not None:
            dx = event.position().toPoint().x() - self._press_pos.x()
            new_x = max(0, self._drag_origin.x() + dx)
            self.move(new_x, self.y())
            return
        if (event.position().toPoint() - self._press_pos).manhattanLength() < QApplication.startDragDistance(): return
        if self.metric_field in {"__groups__"}: return
        drag = QDrag(self); mime = QMimeData(); mime.setData("application/x-mm3-metric", self.metric_field.encode("utf-8"))
        drag.setMimeData(mime); drag.exec(Qt.DropAction.MoveAction)
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._move_callback is not None:
            self._move_callback(self.metric_field, self.x())
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        self._press_pos = None; self._drag_origin = None
        super().mouseReleaseEvent(event)
    def keyPressEvent(self, event):
        if self._move_callback is not None and event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right):
            step = -1 if event.key() == Qt.Key.Key_Left else 1
            new_x = max(0, self.x() + step)
            self.move(new_x, self.y())
            self._move_callback(self.metric_field, new_x)
            event.accept(); return
        super().keyPressEvent(event)


class SummaryMetricLane(QFrame):
    """Dépose un total avant le total survolé, ou à la fin de la ligne."""
    def __init__(self, parent=None):
        super().__init__(parent); self.reorder_callback = None; self.setAcceptDrops(True)
    def dragEnterEvent(self, event):
        source = event.source()
        if event.mimeData().hasFormat("application/x-mm3-metric") and isinstance(source, SummaryMetricLabel):
            parent = source.parentWidget()
            while parent is not None and parent is not self:
                parent = parent.parentWidget()
            if parent is self:
                event.acceptProposedAction()
                return
        event.ignore()
    def dragMoveEvent(self, event): self.dragEnterEvent(event)
    def dropEvent(self, event):
        if not self.reorder_callback: event.ignore(); return
        field = bytes(event.mimeData().data("application/x-mm3-metric")).decode("utf-8")
        before = None
        for child in self.findChildren(SummaryMetricLabel, options=Qt.FindChildOption.FindDirectChildrenOnly):
            if child.metric_field != field and event.position().x() < child.geometry().center().x():
                before = child.metric_field; break
        self.reorder_callback(field, before)
        event.acceptProposedAction()


class ReportNumericItem(QTableWidgetItem):
    """Cellule affichée normalement mais triée selon sa vraie valeur numérique."""
    def __init__(self, text="", numeric_value=0):
        super().__init__(str(text))
        try:
            self.numeric_value = float(numeric_value)
        except Exception:
            self.numeric_value = 0.0

    def __lt__(self, other):
        if isinstance(other, ReportNumericItem):
            return self.numeric_value < other.numeric_value
        try:
            return self.numeric_value < float(_number(other.text()))
        except Exception:
            return super().__lt__(other)


class ReportDateItem(QTableWidgetItem):
    """Date affichée en français et triée chronologiquement."""

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



def _print_field_class(field: str) -> str:
    """Classe CSS d'impression selon la nature du champ."""
    if field in {"record_number"}:
        return "col-number nowrap"
    if field in {
        "mineral_name", "country", "department", "region",
        "quality", "origin", "acquisition_place"
    }:
        return "nowrap"
    if field in {"contact"}:
        return "nowrap"
    return "wrap"


def _trait_css_width(value) -> str:
    """Épaisseurs de traits MM3 pour l'aperçu écran."""
    return {
        "none": "0px",
        "hairline": "1px",
        "1pt": "2px",
        "2pt": "4px",
    }.get(str(value or "none"), "0px")


def _trait_print_width(value) -> str:
    """Épaisseurs de traits MM3 exprimées pour l'impression."""
    return {
        "none": "0",
        "hairline": "0.25pt",
        "1pt": "1pt",
        "2pt": "2pt",
    }.get(str(value or "none"), "0")


def _print_table_geometry(table: QTableWidget, landscape: bool):
    """Return visible column widths and exact table/A4 ratios.

    The editor is the sole source of truth. The A4 width is converted to
    screen pixels using the table's logical DPI, exactly like a physical ruler.
    """
    header = table.horizontalHeader()
    logical_columns = [
        header.logicalIndex(visual) for visual in range(header.count())
    ]
    widths = [
        max(24, int(header.sectionSize(logical))) for logical in logical_columns
    ]
    total = float(sum(widths)) or 1.0
    dpi = float(table.logicalDpiX() or 96.0)
    # L'aperçu avant impression utilise des marges de 5 mm de
    # chaque côté (voir la configuration QPrinter). Le tableau HTML
    # occupe la zone imprimable, pas la largeur physique de la feuille.
    a4_mm = 297.0 if landscape else 210.0
    printable_mm = a4_mm - 10.0
    a4_px = max(1.0, (printable_mm / 25.4) * dpi)
    # Si une colonne franchit la marge, son texte aligné à droite
    # doit s'aligner sur la portion visible, pas hors de la page.
    # Ne pas toucher aux largeurs enregistrées dans le constructeur.
    printable_widths = []
    remaining = a4_px
    for width in widths:
        visible = max(0.0, min(float(width), remaining))
        printable_widths.append(visible)
        remaining -= visible
    visible_total = sum(printable_widths)
    table_percent = max(1.0, min(100.0, (visible_total / a4_px) * 100.0))
    column_percentages = [(w / max(1.0, visible_total)) * 100.0
                          for w in printable_widths]
    return logical_columns, widths, table_percent, column_percentages


def _clip_print_value(value, width_px, family, size_pt, bold=False, italic=False, pad_px=6):
    """Clip only the printed representation; never alter the source value.

    This prevents an unbreakable value from forcing QTextDocument to widen a
    column. No wrapping and no ellipsis: the visible text simply stops at the
    chosen column boundary, like MM3's table view.
    """
    text = str(value or '')
    if not text:
        return ''
    try:
        available = max(4.0, float(width_px) - float(pad_px))
        font = QFont(str(family or 'Arial'))
        font.setPointSizeF(max(1.0, float(size_pt or 10)))
        font.setBold(bool(bold)); font.setItalic(bool(italic))
        fm = QFontMetricsF(font)
        if fm.horizontalAdvance(text) <= available:
            return text
        lo, hi = 0, len(text)
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if fm.horizontalAdvance(text[:mid]) <= available:
                lo = mid
            else:
                hi = mid - 1
        return text[:lo]
    except Exception:
        return text


class _A4GuideOverlay(QWidget):
    """Repère vertical pointillé de fin de page A4 dans l'aperçu éditeur."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
        )
        self.setAttribute(
            Qt.WidgetAttribute.WA_NoSystemBackground, True
        )
        self.setFixedWidth(3)

    def paintEvent(self, event):
        painter = QPainter(self)
        pen = QPen(QColor("#69706D"))
        pen.setWidth(1)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawLine(1, 0, 1, self.height())


class _MM3SummaryHeader(QHeaderView):
    """En-tête du tableau résumé peint par MM3.

    Qt/Windows peut ignorer BackgroundRole des items d'en-tête selon le style
    natif. On peint donc explicitement fond + texte, tout en lisant les rôles
    standards du modèle. Cela conserve le moteur de formatage colonne par
    colonne sans feuille de style concurrente.
    """

    def __init__(self, parent=None):
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.setSectionsMovable(True)
        self.setSectionsClickable(True)

    def paintSection(self, painter, rect, logicalIndex):
        if not rect.isValid():
            return
        model = self.model()
        if model is None:
            return super().paintSection(painter, rect, logicalIndex)

        painter.save()
        bg = model.headerData(
            logicalIndex, Qt.Orientation.Horizontal, Qt.ItemDataRole.BackgroundRole
        )
        if isinstance(bg, QBrush):
            brush = bg
        elif isinstance(bg, QColor):
            brush = QBrush(bg)
        else:
            brush = QBrush(self.palette().button().color())
        painter.fillRect(rect, brush)

        # Bordures sobres + trait inférieur conservant l'aspect actuel.
        painter.setPen(QPen(QColor("#B8C7BF"), 1))
        painter.drawRect(rect.adjusted(0, 0, -1, -1))
        painter.setPen(QPen(QColor("#222222"), 2))
        painter.drawLine(rect.bottomLeft(), rect.bottomRight())

        font = model.headerData(
            logicalIndex, Qt.Orientation.Horizontal, Qt.ItemDataRole.FontRole
        )
        if isinstance(font, QFont):
            painter.setFont(font)

        fg = model.headerData(
            logicalIndex, Qt.Orientation.Horizontal, Qt.ItemDataRole.ForegroundRole
        )
        if isinstance(fg, QBrush):
            painter.setPen(QPen(fg.color()))
        elif isinstance(fg, QColor):
            painter.setPen(QPen(fg))
        else:
            painter.setPen(QPen(self.palette().buttonText().color()))

        align = model.headerData(
            logicalIndex, Qt.Orientation.Horizontal, Qt.ItemDataRole.TextAlignmentRole
        )
        try:
            flags = Qt.AlignmentFlag(int(align))
        except Exception:
            flags = Qt.AlignmentFlag.AlignCenter
        text = str(model.headerData(
            logicalIndex, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole
        ) or "")
        text_rect = rect.adjusted(7, 2, -7, -2)
        painter.drawText(text_rect, flags | Qt.AlignmentFlag.AlignVCenter, text)

        # Indicateur de tri discret quand le tri du tableau est actif.
        if self.isSortIndicatorShown() and self.sortIndicatorSection() == logicalIndex:
            x = rect.right() - 12
            y = rect.top() + 7
            painter.setPen(QPen(self.palette().buttonText().color(), 1))
            if self.sortIndicatorOrder() == Qt.SortOrder.AscendingOrder:
                painter.drawLine(x - 3, y + 4, x, y)
                painter.drawLine(x, y, x + 3, y + 4)
            else:
                painter.drawLine(x - 3, y, x, y + 4)
                painter.drawLine(x, y + 4, x + 3, y)
        painter.restore()




class _DetailPageNumberOverlay(QWidget):
    """Repères de pages de l'aperçu détaillé, non imprimables."""
    def __init__(self, table, page_chrome):
        super().__init__(table.viewport())
        self.table = table
        self.page_chrome = dict(page_chrome or {})
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.show()

    def paintEvent(self, event):
        if not bool(self.page_chrome.get("show_page_numbers", True)):
            return
        p = QPainter(self)
        p.setPen(QColor(str(self.page_chrome.get("footer_text_color") or "#4F5A55")))
        f = self.font(); f.setPointSize(int(self.page_chrome.get("footer_font_size", 9))); p.setFont(f)
        dpi = float(self.table.logicalDpiY() or 96.0)
        page_h = max(300, int(round(((200.0 if self.table._a4_landscape else 287.0) / 25.4) * dpi)))
        reserve = max(28, int(round((12.0 / 25.4) * dpi)))
        scroll = int(self.table.verticalScrollBar().value())
        total_h = max(self.table.viewport().height(),
                      int(self.table.verticalScrollBar().maximum()) + self.table.viewport().height(),
                      self.table.verticalHeader().length())
        pages = max(1, (total_h + page_h - 1) // page_h)
        fmt = str(self.page_chrome.get("page_number_format") or "page_x_y")
        align_name = str(self.page_chrome.get("footer_align") or "right")
        flags = Qt.AlignmentFlag.AlignVCenter | (Qt.AlignmentFlag.AlignLeft if align_name == "left" else (Qt.AlignmentFlag.AlignHCenter if align_name == "center" else Qt.AlignmentFlag.AlignRight))
        for n in range(1, pages + 1):
            y = n * page_h - reserve - scroll
            if -24 <= y <= self.height() + 24:
                text = (f"Page {n} / {pages}" if fmt == "page_x_y" else (f"Page {n}" if fmt == "page_x" else f"{n} / {pages}"))
                p.drawText(8, y - 10, max(10, self.width() - 16), 20, flags, text)

        # 1.0.139 — l’aperçu doit toujours montrer à l’utilisateur la pagination
        # active, même lorsque le vrai pied de page se trouve momentanément hors
        # de la zone visible. L’indicateur suit la page courante et reste purement
        # visuel : l’impression conserve son propre positionnement physique.
        current = max(1, min(pages, (scroll + max(1, self.height() // 2)) // page_h + 1))
        current_text = (f"Page {current} / {pages}" if fmt == "page_x_y" else
                        (f"Page {current}" if fmt == "page_x" else f"{current} / {pages}"))
        p.drawText(8, max(0, self.height() - 24), max(10, self.width() - 16), 20, flags, current_text)
        p.end()

class A4GuideTable(QTableWidget):
    """Table de prévisualisation détaillée avec repère A4 non imprimable."""

    def __init__(self, *args, landscape=False, **kwargs):
        # Ces attributs doivent exister avant QTableWidget.__init__,
        # car Qt peut envoyer des resizeEvent pendant son constructeur.
        self._a4_landscape = bool(landscape)
        self._a4_guide = None
        super().__init__(*args, **kwargs)

        self._a4_guide = _A4GuideOverlay(self.viewport())
        # 1.0.140 — pagination visuelle de l'Aperçu détaillé.
        # Elle est peinte directement par la table : aucun widget superposé,
        # aucun impact sur l'impression et aucun risque de disparition du calque.
        self._preview_page_numbers = False
        self._preview_page_number_format = "page_x_y"
        self._preview_page_number_align = "right"
        self.horizontalScrollBar().valueChanged.connect(
            lambda *_: self._update_a4_guide()
        )
        self.verticalScrollBar().valueChanged.connect(lambda *_: self.viewport().update())
        self.verticalScrollBar().rangeChanged.connect(lambda *_: self.viewport().update())
        QTimer.singleShot(0, self._update_a4_guide)

    def _a4_width_px(self):
        # Largeur physique de la feuille : 210 mm portrait / 297 mm paysage.
        mm = 287.0 if self._a4_landscape else 200.0
        dpi = float(self.logicalDpiX() or 96.0)
        return int(round((mm / 25.4) * dpi))

    def _update_a4_guide(self):
        guide = getattr(self, "_a4_guide", None)
        if guide is None:
            return
        viewport = self.viewport()
        if viewport is None:
            return

        x = self._a4_width_px() - self.horizontalScrollBar().value()

        # Le viewport est légèrement plus étroit que la table (cadre et
        # barre de défilement Qt). Garder le repère sur son bord visible.
        if x < 0 or x > viewport.width() + 24:
            guide.hide()
            return
        # Ne jamais plaquer la marge contre le bord du tableau.
        # Elle conserve sa coordonnée physique, même si les colonnes
        # dépassent la zone imprimable.
        if x >= viewport.width():
            guide.hide()
            return

        guide.setGeometry(
            max(0, x - 1), 0, 3, max(1, viewport.height())
        )
        guide.raise_()
        guide.show()
        guide.update()

    def set_preview_pagination(self, enabled=False, fmt="page_x_y", align="right", total_pages=None, break_rows=None):
        # 1.0.155 — les repères de pagination ne doivent jamais recouvrir une
        # ligne de données. On réserve donc une vraie ligne blanche dans le
        # QTableWidget, juste avant la première ligne de chaque nouvelle page.
        # Les césures continuent de provenir exclusivement du moteur
        # d'impression ; cette ligne n'est qu'une représentation visuelle.
        for row in sorted(list(getattr(self, "_preview_pagination_spacers", []) or []), reverse=True):
            if 0 <= int(row) < self.rowCount():
                self.removeRow(int(row))
        self._preview_pagination_spacers = []

        self._preview_page_numbers = bool(enabled)
        self._preview_page_number_format = str(fmt or "page_x_y")
        self._preview_page_number_align = str(align or "right")
        self._preview_total_pages = int(total_pages) if total_pages else None

        source_breaks = sorted({int(r) for r in (break_rows or []) if int(r) >= 0})
        visual_breaks = []
        if self._preview_page_numbers and source_breaks:
            dpi = float(self.logicalDpiY() or 96.0)
            reserve = max(28, int(round((12.0 / 25.4) * dpi)))
            margin_h = max(24, min(reserve, 36))
            offset = 0
            for source_row in source_breaks:
                row = min(self.rowCount(), source_row + offset)
                self.insertRow(row)
                self.setRowHeight(row, margin_h)
                # Une cellule vide suffit à matérialiser la marge ; aucune
                # donnée n'est déplacée ou modifiée.
                for col in range(self.columnCount()):
                    item = QTableWidgetItem("")
                    item.setFlags(Qt.ItemFlag.NoItemFlags)
                    item.setBackground(QColor("#FFFFFF"))
                    self.setItem(row, col, item)
                self._preview_pagination_spacers.append(row)
                visual_breaks.append(row)
                offset += 1

            # 1.0.156 — réserver également une vraie marge APRES la dernière
            # ligne de données. Jusqu'ici les pages intermédiaires avaient leur
            # spacer, mais le numéro de la dernière page était peint dans les
            # derniers pixels du tableau : la bande blanche pouvait donc masquer
            # la dernière ligne (cas très visible dans la base anglaise).
            # Le pied de la dernière page dispose désormais de son propre espace,
            # exactement comme les césures intermédiaires.
            terminal_row = self.rowCount()
            self.insertRow(terminal_row)
            self.setRowHeight(terminal_row, margin_h)
            for col in range(self.columnCount()):
                item = QTableWidgetItem("")
                item.setFlags(Qt.ItemFlag.NoItemFlags)
                item.setBackground(QColor("#FFFFFF"))
                self.setItem(terminal_row, col, item)
            self._preview_pagination_spacers.append(terminal_row)
        elif self._preview_page_numbers:
            # Même protection pour un état d'une seule page : son numéro ne doit
            # jamais être peint par-dessus la dernière fiche.
            dpi = float(self.logicalDpiY() or 96.0)
            reserve = max(28, int(round((12.0 / 25.4) * dpi)))
            margin_h = max(24, min(reserve, 36))
            terminal_row = self.rowCount()
            self.insertRow(terminal_row)
            self.setRowHeight(terminal_row, margin_h)
            for col in range(self.columnCount()):
                item = QTableWidgetItem("")
                item.setFlags(Qt.ItemFlag.NoItemFlags)
                item.setBackground(QColor("#FFFFFF"))
                self.setItem(terminal_row, col, item)
            self._preview_pagination_spacers.append(terminal_row)
            visual_breaks = source_breaks
        else:
            visual_breaks = source_breaks

        self._preview_break_rows = visual_breaks
        self.viewport().update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if not bool(getattr(self, "_preview_page_numbers", False)):
            return
        vp = self.viewport()
        if vp is None:
            return
        painter = QPainter(vp)
        dpi = float(self.logicalDpiY() or 96.0)
        page_h = max(300, int(round(((200.0 if self._a4_landscape else 287.0) / 25.4) * dpi)))
        reserve = max(28, int(round((12.0 / 25.4) * dpi)))
        scroll = int(self.verticalScrollBar().value())
        total_h = max(vp.height(), int(self.verticalScrollBar().maximum()) + vp.height(), self.verticalHeader().length())
        pages = max(1, (total_h + page_h - 1) // page_h)
        # 1.0.142 — le total affiché vient du même QTextDocument que
        # l'impression multipage. L'aperçu ne doit plus annoncer un total
        # calculé à partir de la hauteur écran du QTableWidget.
        pages = int(getattr(self, "_preview_total_pages", None) or pages)
        fmt = str(getattr(self, "_preview_page_number_format", "page_x_y") or "page_x_y")
        align_name = str(getattr(self, "_preview_page_number_align", "right") or "right")
        flags = Qt.AlignmentFlag.AlignVCenter | (Qt.AlignmentFlag.AlignLeft if align_name == "left" else (Qt.AlignmentFlag.AlignHCenter if align_name == "center" else Qt.AlignmentFlag.AlignRight))
        dash_pen = QPen(QColor("#7D8983")); dash_pen.setStyle(Qt.PenStyle.DashLine)
        font = painter.font(); font.setPointSize(9); painter.setFont(font)
        # 1.0.141 — le numéro est dessiné dans une vraie marge blanche juste
        # au-dessus du saut de page. Il reste ainsi lisible quelle que soit la
        # couleur des lignes et ne dépend d'aucun widget superposé.
        margin_h = max(24, min(reserve, 36))
        printable_w = max(40, min(vp.width(), self._a4_width_px() - self.horizontalScrollBar().value()))
        # 1.0.144 — les césures proviennent des vraies pages du QTextDocument
        # préparé pour l'impression. Chaque repère écran est donc attaché à la
        # première ligne réelle de la page suivante, et non à une hauteur estimée.
        break_rows = list(getattr(self, "_preview_break_rows", []) or [])
        boundaries = []
        if break_rows:
            for row in break_rows:
                if 0 <= int(row) < self.rowCount():
                    row = int(row)
                    if row in list(getattr(self, "_preview_pagination_spacers", []) or []):
                        # 1.0.155 — la marge est une vraie ligne blanche : le
                        # pointillé est posé à son bord inférieur, juste avant
                        # la première donnée de la page suivante.
                        boundary = int(self.rowViewportPosition(row) + self.rowHeight(row))
                    else:
                        boundary = int(self.rowViewportPosition(row))
                    boundaries.append(boundary)
            # Le dernier numéro appartient à la fin réelle du tableau.
            boundaries.append(int(self.verticalHeader().length()) - scroll)
        else:
            boundaries = [n * page_h - scroll for n in range(1, pages + 1)]
        for n, boundary in enumerate(boundaries[:pages], start=1):
            if -margin_h <= boundary <= vp.height() + margin_h:
                top = boundary - margin_h
                # La bande blanche reste cantonnée à la zone réservée à la
                # pagination ; elle ne doit plus masquer le contenu d'une ligne.
                painter.fillRect(0, top, printable_w, margin_h, QColor("#FFFFFF"))
                painter.setPen(QPen(QColor("#303633")))
                text = (f"Page {n} / {pages}" if fmt == "page_x_y" else (f"Page {n}" if fmt == "page_x" else f"{n} / {pages}"))
                painter.drawText(8, top, max(10, printable_w - 16), margin_h, flags, text)
                painter.setPen(dash_pen)
                painter.drawLine(0, boundary, printable_w, boundary)
        painter.end()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_a4_guide()

    def scrollContentsBy(self, dx, dy):
        super().scrollContentsBy(dx, dy)
        self._update_a4_guide()


class DetailPreviewDialog(QDialog):
    """Aperçu visuel interactif d'un état détaillé."""

    def __init__(self, owner, title: str, records: list[dict],
                 fields: list[str], landscape: bool, parent=None,
                 source_name=None, saved_name=None, layout_state=None,
                 advanced_style=None, page_chrome=None, atelier_style=None,
                 detail_column_alignments=None) -> None:
        super().__init__(parent)
        self.advanced_style = dict(advanced_style or {})
        self.page_chrome = dict(page_chrome or {})
        self.atelier_style = dict(atelier_style or owner._default_atelier_style())
        self.detail_column_alignments = dict(detail_column_alignments or {})
        self.owner = owner
        # 1.0.125 — le nouvel aperçu détaillé réutilise les commandes traduites
        # (notamment la Loupe) : reprendre explicitement la langue du propriétaire.
        self.language = getattr(owner, "language", "fr") or "fr"
        self.report_title = title
        self.records = list(records)
        self.fields = list(fields)
        self.landscape = landscape
        self.source_name = source_name
        self.saved_name = saved_name
        self.layout_state = layout_state or {}
        self.setWindowTitle(f"{tr('Aperçu', self.owner.language)} — {title}")
        self.resize(1100, 720)

        lay = QVBoxLayout(self)
        preview_name = self.saved_name or ""
        custom_title = str(self.advanced_style.get("header_title") or "").strip()
        page_title = str(self.page_chrome.get("title_text") or "").strip()
        heading_text = page_title or custom_title or (
            f"{tr('État détaillé', self.language)} : {preview_name}" if preview_name else tr("État détaillé", self.language)
        )
        if not bool(self.page_chrome.get("show_title", True)):
            heading_text = ""

        extra_header_parts = []
        if bool(self.page_chrome.get("show_collection", False)):
            collection_name = str(getattr(self.owner, "collection", {}).get("name") or "").strip()
            if collection_name:
                extra_header_parts.append(collection_name)
        if bool(self.page_chrome.get("show_print_date", False)):
            extra_header_parts.append(QDate.currentDate().toString("dd/MM/yyyy"))

        if extra_header_parts:
            heading_text = (
                (heading_text + " — ") if heading_text else ""
            ) + " — ".join(extra_header_parts)

        heading = QLabel(heading_text)
        heading.setObjectName("previewTitle")
        heading.setVisible(bool(heading_text))
        lay.addWidget(heading)
        self.preview_heading = heading
        self._apply_advanced_preview_style(heading)
        _tf = heading.font(); _tf.setFamily(str(self.page_chrome.get("title_font_family") or _tf.family())); heading.setFont(_tf)
        if bool(self.advanced_style.get("separator", True)):
            heading.setStyleSheet(heading.styleSheet() + "border-bottom: 1px solid #7f8b87; padding-bottom: 4px;")

        quantities = QHBoxLayout()
        boxes = sum(_number(r.get("box_count")) for r in self.records)
        boxes_text = str(int(boxes) if boxes.is_integer() else boxes).replace(".", ",")
        species=self.owner._species_count(self.records); style=self.atelier_style
        def add_metric(text,semantic):
            family=str(style.get(f"metric_{semantic}_font") or "Calibri")
            size=int(style.get(f"metric_{semantic}_size",10))
            color=str(style.get(f"metric_{semantic}_color") or "#8B3026")
            bg=str(style.get(f"metric_{semantic}_bg") or "#F4F6F5")
            lbl=QLabel(text); font=QFont(); font.setFamily(family); font.setPointSize(size)
            font.setBold(bool(style.get(f"metric_{semantic}_bold",False)))
            font.setItalic(bool(style.get(f"metric_{semantic}_italic",False)))
            font.setUnderline(bool(style.get(f"metric_{semantic}_underline",False)))
            lbl.setFont(font); lbl.setStyleSheet(f"QLabel {{ color:{color}; background:{bg}; padding:1px 3px; }}")
            quantities.addWidget(lbl); quantities.addSpacing(18)
        if style.get("show_boxes",True): add_metric(f"{boxes_text} boîtes","boxes")
        if style.get("show_species",True): add_metric(f"{species} {tr('espèce(s)', self.language)}","species")
        if style.get("show_records",True): add_metric(f"{len(self.records)} {tr('fiche(s)', self.language)}","records")
        quantities.addStretch(1); lay.addLayout(quantities)

        hint = QLabel(
            "Cliquez sur un titre pour trier. Déplacez les titres à la souris "
            "pour réorganiser les colonnes et tirez leurs séparations pour modifier leur largeur."
        )
        hint.setObjectName("previewHint")
        hint.setWordWrap(True)
        lay.addWidget(hint)

        self.table = A4GuideTable(len(self.records), len(self.fields), landscape=self.landscape)
        self.table.setHorizontalHeaderLabels([self.owner.labels.get(f, f) for f in self.fields])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(False)
        self.table.setWordWrap(False)
        self.table.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.table.verticalHeader().setVisible(False)
        body_size = int(self.page_chrome.get("body_font_size", 10))
        print_font = str(self.page_chrome.get("print_font_family") or "Arial")
        # Ne pas imposer police/taille au QTableWidget :
        # chaque cellule maître/secondaire possède maintenant son propre QFont.
        border_mode = str(self.advanced_style.get("detail_borders") or "none")
        line_width = _trait_css_width(self.advanced_style.get("detail_trait") or "none")
        if border_mode == "grid":
            table_border_css = "QTableWidget::item { border-right:1px solid #000000; border-bottom:1px solid #000000; }"
        elif border_mode == "horizontal":
            table_border_css = "QTableWidget::item { border-bottom:1px solid #000000; }"
        elif line_width != "0px":
            table_border_css = f"QTableWidget::item {{ border-bottom:{line_width} solid #000000; }}"
        else:
            table_border_css = "QTableWidget::item { border:0; }"
        self.table.setStyleSheet(self.table.styleSheet() + table_border_css)
        header = self.table.horizontalHeader()
        header_family = str(
            self.advanced_style.get("column_header_font_family") or "Calibri"
        )
        header_text = str(self.advanced_style.get("column_header_text_color") or "#111111")
        header_bg = str(self.advanced_style.get("column_header_bg_color") or "#DDE8E2")
        header_size = int(self.advanced_style.get("column_header_font_size", 10))
        header_weight = "700" if bool(self.advanced_style.get("column_header_bold", True)) else "400"
        header_italic = "italic" if bool(self.advanced_style.get("column_header_italic", False)) else "normal"
        header_decoration = "underline" if bool(self.advanced_style.get("column_header_underline", False)) else "none"
        header.setStyleSheet(
            "QHeaderView::section { "
            f"color:{header_text}; background:{header_bg}; "
            f"font-family:'{header_family}'; "
            f"font-size:{header_size}pt; font-weight:{header_weight}; "
            f"font-style:{header_italic}; text-decoration:{header_decoration}; "
            "padding:6px; border:1px solid #B8C7BF; }"
        )
        header_trait_px = _trait_css_width(
            self.advanced_style.get("header_trait") or "2pt"
        )
        if header_trait_px != "0px":
            header.setStyleSheet(
                header.styleSheet()
                + "QHeaderView::section {"
                f"border-bottom:{header_trait_px} solid #222;"
                "}"
            )
        header.setSectionsMovable(True)
        header.setSectionsClickable(True)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)

        for row, record in enumerate(self.records):
            for col, field in enumerate(self.fields):
                value = record.get(field, "")
                item = ReportDateItem(str(value or "")) if field == "acquisition_date" else QTableWidgetItem()
                if field == "record_number":
                    # DisplayRole numérique => tri 1, 2, 3... 10, 11...
                    item.setData(Qt.ItemDataRole.DisplayRole, int(_number(value)))
                elif field == "box_count":
                    item.setData(Qt.ItemDataRole.DisplayRole, float(_number(value)))
                elif field in {"price", "total_cost", "cost_total"} or str(self.owner.labels.get(field, "")).strip().casefold() in {"coût total", "cout total", "total cost"}:
                    is_total_cost = (field in {"total_cost", "cost_total"} or
                                     str(self.owner.labels.get(field, "")).strip().casefold() in {"coût total", "cout total", "total cost"})
                    display_value = self.owner._summary_numeric_value(record, field) if is_total_cost else value
                    # Les montants restent visibles même à zéro et gardent deux décimales.
                    number = _number(display_value)
                    text = f"{number:.2f}"
                    item.setText(text if str(self.language or "fr").lower().startswith("en") else text.replace(".", ","))
                elif field != "acquisition_date":
                    item.setText(_detail_display_value(field, value, self.language))
                detail_style = dict(
                    dict(self.advanced_style.get("typography") or {}).get("detail")
                    or {}
                )
                detail_font = QFont()
                detail_font.setFamily(
                    str(detail_style.get("font_family") or "Calibri")
                )
                detail_font.setPointSize(
                    int(detail_style.get("font_size", body_size))
                )
                detail_font.setBold(bool(detail_style.get("bold", False)))
                detail_font.setItalic(bool(detail_style.get("italic", False)))
                detail_font.setUnderline(
                    bool(detail_style.get("underline", False))
                )
                item.setFont(detail_font)
                item.setForeground(
                    QColor(str(detail_style.get("text_color") or "#111111"))
                )
                item.setBackground(
                    QColor(str(detail_style.get("bg_color") or "#FFFFFF"))
                )

                align = self.detail_column_alignments.get(
                    field, str(detail_style.get("align") or "left")
                )
                if align == "center":
                    item.setTextAlignment(int(Qt.AlignHCenter | Qt.AlignVCenter))
                elif align == "right":
                    item.setTextAlignment(int(Qt.AlignRight | Qt.AlignVCenter))
                else:
                    item.setTextAlignment(int(Qt.AlignLeft | Qt.AlignVCenter))
                self.table.setItem(row, col, item)

        self.table.setSortingEnabled(True)
        self.table.resizeColumnsToContents()
        self._apply_saved_layout()
        self.table.cellDoubleClicked.connect(self._open_record_from_number)
        lay.addWidget(self.table, 1)

        # 1.0.112 — l’Aperçu Résumé obéit à la numérotation définie dans
        # le constructeur (affichage/suppression, format et alignement).
        footer_parts = []
        footer_text = str(self.page_chrome.get("footer_text") or "").strip()
        if footer_text:
            footer_parts.append(footer_text)
        _pn_enabled = bool(self.summary_header_metrics.get("page_numbers_enabled", False))
        _pn_format = str(self.summary_header_metrics.get("page_number_format") or "page_x_y")
        if _pn_enabled:
            footer_parts.append("Page 1 / 1" if _pn_format == "page_x_y" else ("Page 1" if _pn_format == "page_x" else "1 / 1"))
        if footer_parts:
            footer = QLabel(" — ".join(footer_parts))

            footer_align = (str(self.summary_header_metrics.get("page_number_align") or "right")
                            if _pn_enabled and not footer_text
                            else str(self.page_chrome.get("footer_align") or "right"))
            if footer_align == "center":
                footer.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
            elif footer_align == "left":
                footer.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            else:
                footer.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

            footer_size = int(self.page_chrome.get("footer_font_size", 10))
            footer_bold = bool(self.page_chrome.get("footer_bold", False))
            footer_italic = bool(self.page_chrome.get("footer_italic", False))
            footer_underline = bool(self.page_chrome.get("footer_underline", False))
            footer_color = str(self.page_chrome.get("footer_text_color") or "#4F5A55")
            footer_bg = "#FFFFFF"  # 1.0.112 — fond de feuille blanc dans l’Aperçu

            font = footer.font()
            font.setPointSize(footer_size)
            font.setBold(footer_bold)
            font.setItalic(footer_italic)
            font.setUnderline(footer_underline)
            footer.setFont(font)

            weight = "700" if footer_bold else "400"
            style_name = "italic" if footer_italic else "normal"
            decoration = "underline" if footer_underline else "none"
            footer.setStyleSheet(
                "QLabel {"
                f"color:{footer_color}; background-color:{footer_bg};"
                "border-top:1px solid #AAB5B0;"
                "padding:5px 6px 2px 6px;"
                f"font-size:{footer_size}pt; font-weight:{weight};"
                f"font-style:{style_name}; text-decoration:{decoration};"
                "}"
            )
            lay.addWidget(footer)
            self._print_summary_page_footer = footer

        self._apply_body_font_to_cells()
        self._apply_compact_row_heights()
        self._install_screen_zoom(lay)

        actions = QHBoxLayout()
        actions.addStretch(1)
        modify_btn = QPushButton(tr("Modifier", self.language))
        save_btn = QPushButton(tr("Enregistrer l’état", self.language))
        library_btn = QPushButton(tr("Enregistrer sous…", self.language))
        library_btn.setToolTip(tr("Conserver cet état dans la bibliothèque Modèles d’États", self.owner.language))
        library_btn.clicked.connect(lambda: self.owner.save_report_to_library(self.saved_name, getattr(self, "builder_page", None)))
        print_btn = QPushButton(tr("Imprimer", self.language))
        back = QPushButton(tr("Retour", self.language))
        modify_btn.clicked.connect(
            lambda: self.owner._modify_report_from_preview(
                self,
                self.saved_name,
                getattr(self, "builder_page", None),
            )
        )
        save_btn.clicked.connect(self._save_report)
        print_btn.setToolTip(tr("Aperçu avant impression multipage", self.owner.language))
        print_btn.clicked.connect(self._print)
        back.clicked.connect(self.accept)
        actions.addWidget(modify_btn)
        actions.addWidget(save_btn)
        actions.addWidget(library_btn)
        actions.addWidget(print_btn)
        actions.addWidget(back)
        lay.addLayout(actions)

        self.setStyleSheet("""
            #previewTitle { }
            #mainCount { font-size:17px; font-weight:700; color:#8B3026; }
            #secondaryCount { color:#7A817D; margin-left:12px; }
            #previewHint { color:#66716B; }
            #atelierTotals { background:#E7E7E7; border:0px; }
            #atelierTotals QLabel { font-size:15px; }
        """)




    def _apply_body_font_to_cells(self) -> None:
        """Conserve le style Détail de la fiche comme source de vérité."""
        detail_style = dict(
            dict(self.advanced_style.get("typography") or {}).get("detail") or {}
        )
        family = str(
            detail_style.get("font_family")
            or self.page_chrome.get("print_font_family")
            or "Arial"
        )
        size = int(
            detail_style.get(
                "font_size",
                self.page_chrome.get("body_font_size", 10),
            )
        )

        for row in range(self.table.rowCount()):
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                if item is None:
                    continue

                font = QFont()
                font.setFamily(family)
                font.setPointSize(size)
                font.setBold(bool(detail_style.get("bold", False)))
                font.setItalic(bool(detail_style.get("italic", False)))
                font.setUnderline(bool(detail_style.get("underline", False)))
                item.setFont(font)
                item.setForeground(
                    QColor(str(detail_style.get("text_color") or "#111111"))
                )
                item.setBackground(
                    QColor(str(detail_style.get("bg_color") or "#FFFFFF"))
                )

                field = self.fields[col] if 0 <= col < len(self.fields) else ""
                align = str(
                    self.detail_column_alignments.get(
                        field, detail_style.get("align", "left")
                    )
                )
                if align == "center":
                    item.setTextAlignment(int(Qt.AlignHCenter | Qt.AlignVCenter))
                elif align == "right":
                    item.setTextAlignment(int(Qt.AlignRight | Qt.AlignVCenter))
                else:
                    item.setTextAlignment(int(Qt.AlignLeft | Qt.AlignVCenter))

    def _apply_compact_row_heights(self) -> None:
        """Adapte la hauteur des lignes à la petite taille de police."""
        body_size = int(self.page_chrome.get("body_font_size", 10))
        # Valeurs volontairement serrées pour retrouver un état dense type Access.
        if body_size <= 6:
            height = 16
        elif body_size == 7:
            height = 18
        elif body_size == 8:
            height = 20
        elif body_size == 9:
            height = 22
        else:
            height = 24

        for row in range(self.table.rowCount()):
            # Ne pas écraser les gros bandeaux de regroupement.
            if self.table.columnSpan(row, 0) > 1:
                continue
            self.table.setRowHeight(row, height)

    def _install_screen_zoom(self, lay) -> None:
        """Loupe d'affichage uniquement — ne modifie jamais l'état imprimé."""
        self._screen_zoom_percent = 100
        self._zoom_base_table_font = QFont(self.table.font())
        self._zoom_base_table_style = self.table.styleSheet()
        self._zoom_base_header_style = self.table.horizontalHeader().styleSheet()
        self._zoom_base_col_widths = [
            self.table.columnWidth(i) for i in range(self.table.columnCount())
        ]
        self._zoom_base_row_heights = [
            self.table.rowHeight(i) for i in range(self.table.rowCount())
        ]

        self._zoom_label_bases = []
        for label in self.findChildren(QLabel):
            self._zoom_label_bases.append(
                (
                    label,
                    QFont(label.font()),
                    label.styleSheet(),
                    label.text(),
                    label.textFormat(),
                )
            )

        row = QHBoxLayout()
        row.setContentsMargins(0, 2, 0, 2)
        row.addWidget(QLabel(tr("Loupe :", self.owner.language)))

        minus = QPushButton("−")
        minus.setFixedWidth(32)
        minus.setToolTip("Réduire l’affichage")

        zoom = QComboBox()
        zoom.setEditable(True)
        zoom.setFixedWidth(82)
        for value in (50, 60, 70, 80, 90, 100, 110, 125, 150, 175, 200):
            zoom.addItem(f"{value} %", value)
        zoom.setCurrentIndex(zoom.findData(100))
        zoom.setToolTip(
            "Agrandit ou réduit seulement l’affichage de l’état. "
            "La taille d’impression n’est pas modifiée."
        )

        plus = QPushButton("+")
        plus.setFixedWidth(32)
        plus.setToolTip("Agrandir l’affichage")

        row.addWidget(minus)
        row.addWidget(zoom)
        row.addWidget(plus)
        row.addStretch(1)
        lay.addLayout(row)

        self.screen_zoom_widget = zoom

        def current_percent():
            text = zoom.currentText().strip().replace("%", "").replace(",", ".")
            try:
                return int(round(float(text)))
            except Exception:
                return int(self._screen_zoom_percent)

        def apply_from_combo(*_):
            self._apply_screen_zoom(current_percent())

        def step(delta):
            value = max(40, min(250, current_percent() + delta))
            zoom.blockSignals(True)
            idx = zoom.findData(value)
            if idx >= 0:
                zoom.setCurrentIndex(idx)
            else:
                zoom.setEditText(f"{value} %")
            zoom.blockSignals(False)
            self._apply_screen_zoom(value)

        minus.clicked.connect(lambda: step(-10))
        plus.clicked.connect(lambda: step(10))
        zoom.currentTextChanged.connect(apply_from_combo)
        if zoom.lineEdit() is not None:
            zoom.lineEdit().editingFinished.connect(apply_from_combo)

    @staticmethod
    def _scaled_font_sizes_in_text(text: str, factor: float) -> str:
        def repl(match):
            value = float(match.group(1))
            scaled = max(5.0, value * factor)
            shown = f"{scaled:.1f}".rstrip("0").rstrip(".")
            return f"font-size:{shown}pt"
        return re.sub(r"font-size\s*:\s*([0-9]+(?:\.[0-9]+)?)pt", repl, text)

    def _apply_screen_zoom(self, percent: int) -> None:
        """Applique la loupe aux widgets visibles, sans toucher aux paramètres."""
        percent = max(40, min(250, int(percent)))
        self._screen_zoom_percent = percent
        factor = percent / 100.0

        # Tableau et en-têtes.
        font = QFont(self._zoom_base_table_font)
        base_size = font.pointSizeF()
        if base_size <= 0:
            base_size = 10.0
        font.setPointSizeF(max(5.0, base_size * factor))
        self.table.setFont(font)

        self.table.setStyleSheet(
            self._scaled_font_sizes_in_text(self._zoom_base_table_style, factor)
        )
        self.table.horizontalHeader().setStyleSheet(
            self._scaled_font_sizes_in_text(self._zoom_base_header_style, factor)
        )

        for i, width in enumerate(self._zoom_base_col_widths):
            self.table.setColumnWidth(i, max(24, int(round(width * factor))))
        for i, height in enumerate(self._zoom_base_row_heights):
            self.table.setRowHeight(i, max(16, int(round(height * factor))))

        # Titres, compteurs, bandeaux et pied de page.
        for label, base_font, base_style, base_text, text_format in self._zoom_label_bases:
            f = QFont(base_font)
            size = f.pointSizeF()
            if size > 0:
                f.setPointSizeF(max(5.0, size * factor))
                label.setFont(f)
            label.setStyleSheet(
                self._scaled_font_sizes_in_text(base_style, factor)
            )
            if (
                text_format == Qt.TextFormat.RichText
                or "font-size" in base_text.lower()
                or "<span" in base_text.lower()
            ):
                label.setText(
                    self._scaled_font_sizes_in_text(base_text, factor)
                )


    def _apply_advanced_preview_style(self, widget) -> None:
        """Style de l'en-tête général, avec compatibilité des anciens états."""
        legacy = dict(getattr(self, "advanced_style", {}) or {})
        chrome = dict(getattr(self, "page_chrome", {}) or {})
        if widget is None:
            return

        size = int(chrome.get("title_font_size", legacy.get("font_size", 20)))
        bold = bool(chrome.get("title_bold", True))
        italic = bool(chrome.get("title_italic", legacy.get("italic", False)))
        underline = bool(chrome.get("title_underline", legacy.get("underline", False)))

        font = widget.font()
        font.setFamily(str(chrome.get("print_font_family") or "Arial"))
        font.setPointSize(size)
        font.setBold(bold)
        font.setItalic(italic)
        font.setUnderline(underline)
        widget.setFont(font)

        align = str(chrome.get("title_align") or legacy.get("align", "left"))
        if align == "center":
            widget.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        elif align == "right":
            widget.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        else:
            widget.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        text_color = str(chrome.get("title_text_color") or "#111111")
        bg_color = "#FFFFFF"  # 1.0.112 — Aperçu: la feuille reste blanche, indépendamment du fond du constructeur
        weight = "700" if bold else "400"
        style_name = "italic" if italic else "normal"
        decoration = "underline" if underline else "none"

        widget.setStyleSheet(
            "QLabel {"
            f"color:{text_color}; background-color:{bg_color};"
            f"font-size:{size}pt; font-weight:{weight};"
            f"font-style:{style_name}; text-decoration:{decoration};"
            "padding:4px 6px;"
            "}"
        )


    def _apply_saved_layout(self) -> None:
        state = self.layout_state
        order = state.get("column_order", [])
        widths = state.get("column_widths", {})
        header = self.table.horizontalHeader()
        if order:
            for target, field in enumerate(order):
                if field not in self.fields:
                    continue
                logical = self.fields.index(field)
                current = header.visualIndex(logical)
                if current != target:
                    header.moveSection(current, target)
        for field, width in widths.items():
            if field in self.fields:
                header.resizeSection(self.fields.index(field), int(width))
        sort_field = state.get("sort_field")
        if sort_field in self.fields:
            order_value = Qt.SortOrder.DescendingOrder if state.get("sort_desc") else Qt.SortOrder.AscendingOrder
            self.table.sortItems(self.fields.index(sort_field), order_value)

    def _layout_state(self) -> dict:
        header = self.table.horizontalHeader()
        order = self.visual_fields()
        widths = {
            field: header.sectionSize(self.fields.index(field))
            for field in self.fields
        }
        logical = header.sortIndicatorSection()
        sort_field = self.fields[logical] if 0 <= logical < len(self.fields) else None
        return {
            "column_order": order,
            "column_widths": widths,
            "sort_field": sort_field,
            "sort_desc": header.sortIndicatorOrder() == Qt.SortOrder.DescendingOrder,
        }

    def _save_report(self) -> None:
        name = self.owner.save_report_definition(
            kind="detail",
            title=self.report_title,
            source_name=self.source_name,
            landscape=self.landscape,
            fields=list(self.fields),
            layout_state=self._layout_state(),
            existing_name=self.saved_name,
            builder_page=getattr(self, "builder_page", None),
        )
        if name:
            self.saved_name = name
            self.setWindowTitle(f"Aperçu — {self.report_title} — {name}")

    def visual_fields(self) -> list[str]:
        header = self.table.horizontalHeader()
        return [self.fields[header.logicalIndex(v)] for v in range(header.count())]

    def visual_widths(self) -> list[int]:
        header = self.table.horizontalHeader()
        return [header.sectionSize(header.logicalIndex(v)) for v in range(header.count())]

    def ordered_records(self) -> list[dict]:
        if not self.fields:
            return list(self.records)
        # Recover row order from the currently displayed first logical column.
        ordered=[]
        for row in range(self.table.rowCount()):
            # find original record by matching all visible cell texts; stable fallback.
            vals={field: self.table.item(row,col).text() if self.table.item(row,col) else ""
                  for col,field in enumerate(self.fields)}
            found=None
            for rec in self.records:
                if all(str(rec.get(f,"") or "") == vals[f] for f in self.fields):
                    if rec not in ordered:
                        found=rec; break
            if found is not None: ordered.append(found)
        return ordered if len(ordered)==len(self.records) else list(self.records)

    def _open_record_from_number(self, row: int, column: int) -> None:
        field = self.fields[column] if 0 <= column < len(self.fields) else ""
        if field != "record_number":
            return
        item = self.table.item(row, column)
        if item is None:
            return
        try:
            record_number = int(float(item.text().strip().replace(",", ".")))
        except (TypeError, ValueError):
            return

        # Retrouver l'identifiant interne à partir du numéro visible.
        fresh = self.owner.manager.list_records(int(self.owner.collection["id"]))
        record = next(
            (
                rec for rec in fresh
                if int(_number(rec.get("record_number"))) == record_number
            ),
            None,
        )
        if record is None:
            QMessageBox.information(
                self, "Fiche introuvable", "Cette fiche n'existe plus."
            )
            return

        record_id = record.get("id")
        if record_id is None:
            return

        parent = self.owner.main_window
        callback = getattr(parent, "open_record_from_table", None)
        if callback is None:
            callback = getattr(parent, "open_record_from_search", None)
        if callback is None:
            return

        # L'aperçu DÉTAIL est désormais non modal : il peut être masqué
        # temporairement sans jamais verrouiller le reste de MM3.
        self.hide()

        callback(int(record_id))

        record_window = getattr(parent, "record_window", None)
        bring_front = getattr(parent, "_bring_window_to_front", None)
        if record_window is not None and callable(bring_front):
            QTimer.singleShot(0, lambda: bring_front(record_window))
            QTimer.singleShot(120, lambda: bring_front(record_window))
            QTimer.singleShot(300, lambda: bring_front(record_window))

        # Quand la fiche sera refermée/masquée, l'État revient automatiquement,
        # relit la base et reprend le premier plan.
        if record_window is not None:
            try:
                record_window.installEventFilter(self)
            except Exception:
                pass

    def eventFilter(self, watched, event):
        parent = self.owner.main_window
        record_window = getattr(parent, "record_window", None)
        if watched is record_window and event.type() in (
            QEvent.Type.Hide,
            QEvent.Type.Close,
        ):
            QTimer.singleShot(0, self._return_from_record)
        return super().eventFilter(watched, event)

    def _detail_is_total_cost_field(self, field):
        key = str(field or "")
        if key in {"total_cost", "cost_total"}: return True
        label = str(self.owner.labels.get(key, key) or key).strip().casefold()
        label = unicodedata.normalize("NFKD", label)
        label = "".join(ch for ch in label if not unicodedata.combining(ch))
        label = re.sub(r"[^a-z0-9]+", " ", label).strip()
        return label in {"cout total", "total cost"}

    def _detail_total_cost_text(self, record, field):
        value = self.owner._summary_numeric_value(record, str(field))
        text = f"{float(value or 0):.2f}"
        return text if str(self.language or "fr").lower().startswith("en") else text.replace(".", ",")

    def _return_from_record(self) -> None:
        """Revient exactement à la liste résultat de l'État."""
        self.refresh_from_database()
        self.showNormal()
        self.raise_()
        self.activateWindow()

        parent = self.owner.main_window
        bring_front = getattr(parent, "_bring_window_to_front", None)
        if callable(bring_front):
            QTimer.singleShot(0, lambda: bring_front(self))

    def refresh_from_database(self) -> None:
        # Conserver ordre/largeurs/tri autant que possible.
        header = self.table.horizontalHeader()
        visual_fields = self.visual_fields()
        widths = self.visual_widths()

        fresh = self.owner._records_for_source(None)
        # Si l'aperçu provenait d'une requête, son jeu de données sera
        # recalculé au prochain Aperçu. Ici on actualise au minimum les
        # fiches actuellement présentes par leur numéro.
        by_number = {
            int(_number(rec.get("record_number"))): rec
            for rec in fresh
            if _number(rec.get("record_number")) > 0
        }
        refreshed = []
        for rec in self.records:
            num = int(_number(rec.get("record_number")))
            if num in by_number:
                refreshed.append(by_number[num])
        self.records = refreshed

        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self.records))
        for row, record in enumerate(self.records):
            for col, field in enumerate(self.fields):
                value = record.get(field, "")
                item = ReportDateItem(str(value or "")) if field == "acquisition_date" else QTableWidgetItem()
                if field == "record_number":
                    # DisplayRole numérique => tri 1, 2, 3... 10, 11...
                    item.setData(Qt.ItemDataRole.DisplayRole, int(_number(value)))
                elif field == "box_count":
                    item.setData(Qt.ItemDataRole.DisplayRole, float(_number(value)))
                elif field == "price":
                    item.setText(_detail_display_value(field, value, self.language))
                elif self._detail_is_total_cost_field(field):
                    # Toujours recalculer via le moteur commun : les anciennes collections
                    # utilisent parfois une clé personnalisée pour « Coût total ».
                    item.setText(self._detail_total_cost_text(record, field))
                elif field != "acquisition_date":
                    item.setText(_detail_display_value(field, value, self.language))
                if field == self.atelier_style.get("repeat_master_field"):
                    font = item.font()
                    font.setItalic(bool(self.atelier_style.get("repeat_master_italic", True)))
                    item.setFont(font)
                    item.setForeground(QColor(self.atelier_style.get("repeat_master_color", "#9A3324")))
                self.table.setItem(row, col, item)
        self.table.setSortingEnabled(True)

        # Restaurer l'ordre visuel.
        for target_visual, field in enumerate(visual_fields):
            logical = self.fields.index(field)
            current_visual = header.visualIndex(logical)
            if current_visual != target_visual:
                header.moveSection(current_visual, target_visual)
        for visual, width in enumerate(widths):
            logical = header.logicalIndex(visual)
            header.resizeSection(logical, width)

    def _print(self) -> None:
        """Imprime le même état détaillé que celui visible dans l'aperçu."""
        header = self.table.horizontalHeader()
        logical_columns, visual_widths, table_width_percent, column_percentages = (
            _print_table_geometry(self.table, self.landscape)
        )
        colgroup = "<colgroup>" + "".join(
            f"<col width='{pct:.4f}%' style='width:{pct:.4f}%;'>"
            for pct in column_percentages
        ) + "</colgroup>"
        # Les colonnes de cet aperçu simple correspondent à self.fields.
        # La typographie provient de la section « détail » du constructeur.
        detail_for_print = dict(
            dict(self.advanced_style.get("typography") or {}).get("detail") or {}
        )
        try:
            body_size = float(detail_for_print.get("font_size") or self.page_chrome.get("body_font_size") or 10)
        except (TypeError, ValueError):
            body_size = 10.0
        print_row_pad = "0px 2px"
        print_line_height = "1.0"
        print_font = str(detail_for_print.get("font_family") or
                         self.page_chrome.get("print_font_family") or "Calibri")

        border_mode = str(self.advanced_style.get("detail_borders") or "none")
        detail_trait = _trait_print_width(
            self.advanced_style.get("detail_trait") or "none"
        )
        header_trait = _trait_print_width(
            self.advanced_style.get("header_trait") or "2pt"
        )

        if border_mode == "grid":
            detail_border_css = "border:0.25pt solid #000000;"
        elif border_mode == "horizontal":
            detail_border_css = "border-bottom:0.25pt solid #000000;"
        elif detail_trait not in {"0", "0.25pt"}:
            detail_border_css = f"border-bottom:{detail_trait} solid #000000;"
        elif detail_trait == "0.25pt":
            detail_border_css = "border-bottom:0.25pt solid #000000;"
        else:
            detail_border_css = "border:0;"

        def separator_row(width, colspan):
            raw = str(width or "0").strip().lower()
            if raw in {"", "0", "0pt", "0px", "none", "0.25pt", "0.5pt"}:
                return ""
            height_map = {"1pt": "2", "2pt": "5"}
            h = height_map.get(raw, "1")
            span = max(1, int(colspan))
            return (
                f'<tr><td colspan="{span}" bgcolor="#000000" height="{h}" '
                f'style="height:{h}px; min-height:{h}px; max-height:{h}px; '
                f'padding:0; margin:0; font-size:1px; line-height:1px; '
                f'border:0; background:#000000; background-color:#000000;">'
                f'&#9608;</td></tr>'
            )

        # 27.49 — impression multipage : ne plus créer de lignes HTML
        # séparatrices autonomes. QTextDocument peut les étirer au bas d'une
        # page lors d'un saut de page, ce qui produit une large bande noire.
        # Le trait de détail appartient désormais directement aux cellules.
        detail_separator_html = ""
        cell_box_css = detail_border_css

        hs = self.advanced_style
        h_family = str(hs.get("column_header_font_family") or "Calibri")
        h_text = str(hs.get("column_header_text_color") or "#111111")
        h_bg = str(hs.get("column_header_bg_color") or ("#FFFFFF" if self.detail_graphic else "#DDE8E2"))
        h_size = int(hs.get("column_header_font_size", 10))
        h_weight = "700" if bool(hs.get("column_header_bold", True)) else "400"
        h_style = "italic" if bool(hs.get("column_header_italic", False)) else "normal"
        h_dec = "underline" if bool(hs.get("column_header_underline", False)) else "none"

        headers=[]
        for visual_index, logical in enumerate(logical_columns):
            item=self.table.horizontalHeaderItem(logical)
            label = item.text() if item else ""
            clipped = _clip_print_value(
                label, visual_widths[visual_index], h_family, h_size,
                bool(hs.get("column_header_bold", True)),
                bool(hs.get("column_header_italic", False)), 10
            )
            headers.append(f"<th>{_escape(clipped)}</th>")

        detail_style = dict(
            dict(self.advanced_style.get("typography") or {}).get("detail") or {}
        )
        d_family = str(detail_style.get("font_family") or print_font)
        d_size = int(detail_style.get("font_size", body_size))
        d_bold = bool(detail_style.get("bold", False))
        d_italic = bool(detail_style.get("italic", False))
        d_underline = bool(detail_style.get("underline", False))
        d_weight = "700" if d_bold else "400"
        d_style = "italic" if d_italic else "normal"
        d_dec = "underline" if d_underline else "none"
        d_text = str(detail_style.get("text_color") or "#111111")
        d_bg = str(detail_style.get("bg_color") or "#FFFFFF")

        rows=[]
        for row in range(self.table.rowCount()):
            cells=[]
            for visual_index, logical in enumerate(logical_columns):
                item=self.table.item(row,logical)
                shown=item.text() if item else ""
                field=self.fields[logical]
                align=self.detail_column_alignments.get(
                    field, str(detail_style.get("align") or "left")
                )
                css_class = "nowrap"
                clipped = _clip_print_value(
                    shown, visual_widths[visual_index], d_family, d_size,
                    d_bold, d_italic, 6
                )
                cells.append(
                    f"<td class='{css_class}' style='text-align:{align};"
                    f"font-family:{_escape(d_family)};font-size:{d_size}pt;"
                    f"font-weight:{d_weight};font-style:{d_style};"
                    f"text-decoration:{d_dec};color:{d_text};background:{d_bg};"
                    f"{detail_border_css}'><font face='{_escape(d_family)}'>"
                    f"{_escape(clipped)}</font></td>"
                )
            rows.append("<tr>"+"".join(cells)+"</tr>")
            if detail_separator_html:
                rows.append(detail_separator_html)

        preview_name=self.saved_name or ""
        custom_title=str(self.advanced_style.get("header_title") or "").strip()
        page_title=str(self.page_chrome.get("title_text") or "").strip()
        heading=page_title or custom_title or (f"{tr('État détaillé', self.language)} : {preview_name}" if preview_name else tr("État détaillé", self.language))
        if not bool(self.page_chrome.get("show_title",True)): heading=""

        extras=[]
        if bool(self.page_chrome.get("show_collection",False)):
            cn=str(getattr(self.owner,"collection",{}).get("name") or "").strip()
            if cn: extras.append(cn)
        if bool(self.page_chrome.get("show_print_date",False)):
            extras.append(QDate.currentDate().toString("dd/MM/yyyy"))
        if extras: heading=((heading+" — ") if heading else "")+" — ".join(extras)

        ts=int(self.page_chrome.get("title_font_size",20))
        tw="700" if bool(self.page_chrome.get("title_bold",True)) else "400"
        ti="italic" if bool(self.page_chrome.get("title_italic",False)) else "normal"
        td="underline" if bool(self.page_chrome.get("title_underline",False)) else "none"
        ta=str(self.page_chrome.get("title_align") or "left")
        tc=str(self.page_chrome.get("title_text_color") or "#111111")
        tb=str(self.page_chrome.get("title_bg_color") or "#FFFFFF")
        title_html=(f"<div style='font-size:{ts}pt;font-weight:{tw};font-style:{ti};text-decoration:{td};"
                    f"text-align:{ta};color:{tc};background:{tb};padding:5px 7px;margin-bottom:6px;'>"
                    f"{_escape(heading)}</div>") if heading else ""

        boxes=sum(_number(r.get("box_count")) for r in self.records)
        species=self.owner._species_count(self.records); st=self.atelier_style
        metric=[]
        def add_metric(n,label,semantic):
            family=str(st.get(f"metric_{semantic}_font") or "Calibri")
            size=int(st.get(f"metric_{semantic}_size",10))
            color=str(st.get(f"metric_{semantic}_color") or "#8B3026")
            bg=str(st.get(f"metric_{semantic}_bg") or "#F4F6F5")
            weight="700" if bool(st.get(f"metric_{semantic}_bold",False)) else "400"
            italic="italic" if bool(st.get(f"metric_{semantic}_italic",False)) else "normal"
            underline="underline" if bool(st.get(f"metric_{semantic}_underline",False)) else "none"
            metric.append(
                f"<span style='font-family:{_escape(family)};font-size:{size}pt;"
                f"font-weight:{weight};font-style:{italic};text-decoration:{underline};"
                f"color:{color};background:{bg};margin-right:18px;padding:1px 3px;'>"
                f"<font face='{_escape(family)}'>{_escape(n)} {_escape(label)}</font></span>"
            )
        if st.get("show_boxes",True): add_metric(self.owner._fmt_number(boxes),tr("pièce(s)", self.owner.language),"boxes")
        if st.get("show_species",True): add_metric(str(species),"espèces","species")
        if st.get("show_records",True): add_metric(str(len(self.records)),tr("fiche(s)", self.owner.language),"records")
        metrics_html="<div style='padding:5px 7px;margin-bottom:8px;'>"+ "".join(metric)+"</div>" if metric else ""

        footer=[]
        ft=str(self.page_chrome.get("footer_text") or "").strip()
        if ft: footer.append(ft)
        if bool(self.page_chrome.get("show_page_numbers",True)): footer.append("Page 1 / 1")
        footer_html=""
        if footer:
            fs=int(self.page_chrome.get("footer_font_size",10))
            fw="700" if bool(self.page_chrome.get("footer_bold",False)) else "400"
            fi="italic" if bool(self.page_chrome.get("footer_italic",False)) else "normal"
            fd="underline" if bool(self.page_chrome.get("footer_underline",False)) else "none"
            fa=str(self.page_chrome.get("footer_align") or "right")
            fc=str(self.page_chrome.get("footer_text_color") or "#4F5A55")
            fb=str(self.page_chrome.get("footer_bg_color") or "#FFFFFF")
            footer_html=(f"<div style='font-size:{fs}pt;font-weight:{fw};font-style:{fi};text-decoration:{fd};"
                         f"text-align:{fa};color:{fc};background:{fb};border-top:1px solid #AAB5B0;"
                         f"padding:5px 7px;margin-top:8px;'>{_escape(' — '.join(footer))}</div>")

        border_mode = str(self.advanced_style.get("detail_borders") or "none")
        detail_trait = _trait_print_width(self.advanced_style.get("detail_trait") or "none")
        header_trait = _trait_print_width(self.advanced_style.get("header_trait") or "2pt")
        if border_mode == "grid":
            detail_border_css = "border:0.25pt solid #000000;"
        elif border_mode == "horizontal":
            detail_border_css = "border-bottom:0.25pt solid #000000;"
        elif detail_trait != "0":
            detail_border_css = f"border-bottom:{detail_trait} solid #000000;"
        else:
            detail_border_css = "border:0;"

        def separator_row(width, colspan):
            # width est une valeur MM3 déjà exprimée sous forme de texte :
            # "0", "0.25pt", "1pt", "2pt".
            raw = str(width or "0").strip().lower()
            if raw in {"", "0", "0pt", "0px", "none", "0.25pt", "0.5pt"}:
                return ""

            # Les séparateurs épais restent des bandes fiables pour QTextDocument.
            # Le Filet, lui, est rendu comme une vraie bordure de cellule.
            height_map = {
                "1pt": "2",
                "2pt": "5",
            }
            h = height_map.get(raw, "1")
            span = max(1, int(colspan))

            return (
                f'<tr><td colspan="{span}" '
                f'bgcolor="#000000" height="{h}" '
                f'style="height:{h}px; min-height:{h}px; max-height:{h}px; '
                f'padding:0; margin:0; font-size:1px; line-height:1px; '
                f'border:0; background:#000000; background-color:#000000;">'
                f'&#9608;</td></tr>'
            )
        detail_separator_html = separator_row(detail_trait, len(logical_columns))

        cell_box_css = (
            "border:0.25pt solid #000000;"
            if border_mode == "grid"
            else "border:0;"
        )

        html=f"""<html><head><meta charset="utf-8"><style>
        body {{font-family:"{print_font}",Arial,sans-serif;color:#222;font-size:{body_size}pt;}}
        table {{width:{table_width_percent:.4f}%;table-layout:fixed;border-collapse:collapse;
                 page-break-inside:auto;font-size:{body_size}pt;}}
        .nowrap {{ white-space:nowrap; word-break:keep-all; }}
        .wrap {{ white-space:normal; word-break:normal; }}
        .col-number {{ width:5%; }}
        thead {{display:table-header-group;}} tbody {{display:table-row-group;}}
        tr {{page-break-inside:avoid;page-break-after:auto;}}
        th {{color:{h_text};background:{h_bg};font-size:{h_size}pt;font-weight:{h_weight};
             font-style:{h_style};text-decoration:{h_dec};padding:6px;
             border:0;border:0;}}
        td {{ {cell_box_css} padding:{print_row_pad};
               font-size:{body_size}pt;line-height:{print_line_height};vertical-align:top;
               white-space:nowrap;overflow:hidden;}}
        tr:nth-child(even):not(.mm3-separator) td {{background:#f5f7f6;}}
        .mm3-separator td, .mm3-separator th {{
            padding:0 !important;
            margin:0 !important;
            border:0 !important;
            background:#000000 !important; background-color:#000000 !important;
        }}
        </style></head><body>{title_html}{metrics_html}
        <table width="{table_width_percent:.4f}%" style="width:{table_width_percent:.4f}%;">{colgroup}<thead><tr>{''.join(headers)}</tr></thead>{separator_row(header_trait, len(logical_columns))}<tbody>{''.join(rows)}</tbody></table>
        {footer_html}</body></html>"""
        self.owner._last_html=html
        self.owner._last_summary_column_widths = None
        self.owner._last_title=self.report_title
        self.owner._last_landscape=self.landscape
        self.owner._last_print_advanced_style = dict(self.advanced_style or {})
        self.owner._print_preview()


class GroupedDetailPreviewDialog(QDialog):
    """État DÉTAIL avec 1 à 3 niveaux de regroupement visuels."""

    GROUP_COLORS = ("#C8D8D0", "#DDE8E2", "#EEF3F0")

    def __init__(self, owner, title, records, fields, groupings, landscape,
                 parent=None, source_name=None, saved_name=None,
                 layout_state=None, atelier_style=None, advanced_style=None,
                 page_chrome=None, detail_column_alignments=None,
                 detail_graphic=None):
        super().__init__(parent)
        self.detail_graphic = dict(detail_graphic or {})
        self.advanced_style = dict(advanced_style or {})
        self.page_chrome = dict(page_chrome or {})
        # 1.0.129 — la ligne N° de page du constructeur détaillé est la source
        # de vérité, exactement comme dans l'état résumé.
        if detail_graphic:
            _pn = dict((detail_graphic or {}).get("summary_header_metrics") or {})
            self.page_chrome["show_page_numbers"] = bool(_pn.get("page_numbers_enabled", False))
            self.page_chrome["page_number_format"] = str(_pn.get("page_number_format") or "page_x_y")
            self.page_chrome["footer_align"] = str(_pn.get("page_number_align") or "right")
        self.owner = owner
        # 1.0.126 — GroupedDetailPreviewDialog utilise les commandes traduites
        # de l’aperçu (Loupe, Modifier, Imprimer, etc.). La langue doit être
        # disponible avant _install_screen_zoom().
        self.language = getattr(owner, "language", "fr") or "fr"
        self.report_title = title
        self.records = list(records)
        self.atelier_style = dict(atelier_style or owner._default_atelier_style())
        self.detail_column_alignments = dict(detail_column_alignments or {})
        self.fields = list(fields)
        repeat_field = self.atelier_style.get("repeat_master_field")
        if repeat_field:
            self.fields = [f for f in self.fields if f != repeat_field]
            self.fields.insert(0, repeat_field)
        self.groupings = [g for g in groupings if g]
        self.group_sort_desc = [False for _ in self.groupings]
        self.group_sort_level = 0 if self.groupings else None
        # 27.249 — tri des colonnes du détail SANS activer le tri natif du
        # QTableWidget. Le tri natif déplaçait aussi les bandeaux de groupe et
        # cassait le regroupement (bandeaux repoussés en fin d'état).
        self.detail_sort_field = None
        self.detail_sort_desc = False
        self.landscape = landscape
        self.source_name = source_name
        self.saved_name = saved_name
        self.layout_state = layout_state or {}
        self.setWindowTitle(f"{tr('Aperçu groupé', self.language)} — {title}")
        self.resize(1180, 760)

        lay = QVBoxLayout(self)
        preview_name = self.saved_name or ""
        custom_title = str(self.advanced_style.get("header_title") or "").strip()
        page_title = str(self.page_chrome.get("title_text") or "").strip()
        heading_text = page_title or custom_title or (
            f"{tr('État détaillé', self.language)} : {preview_name}" if preview_name else tr("État détaillé", self.language)
        )
        if not bool(self.page_chrome.get("show_title", True)):
            heading_text = ""

        extra_header_parts = []
        if bool(self.page_chrome.get("show_collection", False)):
            collection_name = str(getattr(self.owner, "collection", {}).get("name") or "").strip()
            if collection_name:
                extra_header_parts.append(collection_name)
        if bool(self.page_chrome.get("show_print_date", False)):
            extra_header_parts.append(QDate.currentDate().toString("dd/MM/yyyy"))

        if extra_header_parts:
            heading_text = (
                (heading_text + " — ") if heading_text else ""
            ) + " — ".join(extra_header_parts)

        heading = QLabel(heading_text)
        heading.setObjectName("previewTitle")
        heading.setVisible(bool(heading_text))
        lay.addWidget(heading)
        self.preview_heading = heading
        self._apply_advanced_preview_style(heading)
        _tf = heading.font(); _tf.setFamily(str(self.page_chrome.get("title_font_family") or _tf.family())); heading.setFont(_tf)
        if bool(self.advanced_style.get("separator", True)):
            heading.setStyleSheet(heading.styleSheet() + "border-bottom: 1px solid #7f8b87; padding-bottom: 4px;")

        boxes = sum(_number(rec.get("box_count")) for rec in self.records)
        species = self.owner._species_count(self.records)
        primary_groups = self.owner._group_records_for_detail(
            self.records, self.groupings[0]
        ) if self.groupings else {}

        totals_frame = QFrame()
        totals_frame.setObjectName("atelierTotals")
        totals_lay = QHBoxLayout(totals_frame)
        totals_lay.setContentsMargins(16, 10, 16, 10)
        totals_lay.setSpacing(22)
        if (self.detail_graphic.get("summary_header_metrics", {}).get("groups", False)
                if self.detail_graphic else self.atelier_style.get("show_groups", True)) and self.groupings:
            count = len(primary_groups)
            group_word = self.owner._grouping_label(self.groupings[0]).lower()
            if self.groupings[0] == "__acquisition_year__":
                group_word = "année" if count == 1 else "années"
            elif count != 1 and not group_word.endswith("s"):
                group_word += "s"
            totals_lay.addWidget(self._make_detail_metric_label(f"{count} {group_word}","groups"))
        if self.detail_graphic:
            metrics = dict(self.detail_graphic.get("summary_header_metrics") or {})
            for field in metrics.get("selected_fields") or []:
                if field in self.owner.labels:
                    lbl = self._make_detail_metric_label(self._graphic_metric(field, self.records), "boxes")
                    width = (metrics.get("metric_widths") or {}).get(str(field))
                    if width:
                        lbl.setFixedWidth(max(55, min(480, int(width))))
                    totals_lay.addWidget(lbl)
            if metrics.get("records", False):
                totals_lay.addWidget(self._make_detail_metric_label(f"{len(self.records)} {tr('fiche(s)', self.language)}", "records"))
        else:
            if self.atelier_style.get("show_boxes", True):
                totals_lay.addWidget(self._make_detail_metric_label(f"{self.owner._fmt_number(boxes)} {tr('boîte(s)', self.language)}","boxes"))
            if self.atelier_style.get("show_species", True):
                totals_lay.addWidget(self._make_detail_metric_label(f"{species} {tr('espèce(s)', self.language)}","species"))
            if self.atelier_style.get("show_records", True):
                totals_lay.addWidget(self._make_detail_metric_label(f"{len(self.records)} {tr('fiche(s)', self.language)}","records"))
        totals_lay.addStretch(1)
        if not self.detail_graphic or totals_lay.count() > 1:
            lay.addWidget(totals_frame)
        else:
            totals_frame.deleteLater()
        lay.addSpacing(5)

        group_names = " → ".join(self.owner._grouping_label(g) for g in self.groupings)
        hint = QLabel(
            f"{tr('Regroupement :', self.language)} {group_names}. "
            + tr("Les en-têtes de groupe affichent le nombre de pièces et d’espèces. Les colonnes de détail restent déplaçables et redimensionnables.", self.language)
        )
        hint.setObjectName("previewHint")
        hint.setWordWrap(True)
        if not self.detail_graphic:
            lay.addWidget(hint)

        sort_row = QHBoxLayout()
        sort_row.addWidget(QLabel(tr("Trier les groupes :", self.language)))
        self.group_sort_combo = QComboBox()
        for level, field in enumerate(self.groupings):
            self.group_sort_combo.addItem(
                f"{tr('Niveau', self.language)} {level + 1} — {self.owner._grouping_label(field)}",
                level,
            )
        if self.group_sort_combo.count():
            self.group_sort_combo.setCurrentIndex(0)

        self.group_sort_direction = QPushButton("▲ " + tr("Croissant", self.language))
        self.group_sort_direction.setToolTip(
            "Inverse l’ordre du regroupement sélectionné"
        )
        self.group_sort_combo.currentIndexChanged.connect(
            self._change_group_sort_level
        )
        self.group_sort_direction.clicked.connect(
            self._toggle_group_sort_direction
        )
        sort_row.addWidget(self.group_sort_combo)
        sort_row.addWidget(self.group_sort_direction)
        sort_row.addStretch(1)
        if self.groupings:
            lay.addLayout(sort_row)

        self.table = A4GuideTable(landscape=self.landscape)
        # 1.0.127 — la feuille d’aperçu a la largeur physique de la page,
        # au lieu de s’étirer jusqu’au bord de la fenêtre. La justification
        # gauche/centre/droite de la pagination devient ainsi fidèle et visible.
        # 1.0.339.9 — repère visuel conservateur : retirer 10 mm à la
        # largeur de l'aperçu groupé, sans modifier le format imprimé.
        self._detail_page_width = max(200, self.table._a4_width_px() -
                                      round(10.0 * float(self.table.logicalDpiX() or 96) / 25.4))
        self.table.setMaximumWidth(self._detail_page_width)
        self.table.setColumnCount(len(self.fields))
        # 27.46 : même moteur d’en-tête peint que l’état résumé. Il respecte
        # les fonds/typos individuels tout en conservant déplacement, largeur et tri.
        self.table.setHorizontalHeader(_MM3SummaryHeader(self.table))
        self.table.setHorizontalHeaderLabels([self.owner.labels.get(f, f) for f in self.fields])
        if self.detail_graphic:
            labels = dict(self.detail_graphic.get("detail_column_labels") or {})
            self.table.setHorizontalHeaderLabels([str(labels.get(f) or self.owner.labels.get(f, f)) for f in self.fields])
            label_styles = dict(self.detail_graphic.get("detail_label_styles") or {})
            for col, field in enumerate(self.fields):
                item = self.table.horizontalHeaderItem(col)
                if item is None: continue
                fmt = dict(label_styles.get(field) or {})
                fnt = QFont(str(fmt.get("font_family") or "Arial"), int(fmt.get("font_size") or 9))
                fnt.setBold(bool(fmt.get("bold", False))); fnt.setItalic(bool(fmt.get("italic", False)))
                item.setFont(fnt); item.setForeground(QColor(str(fmt.get("text_color") or "#111111")))
                item.setBackground(QColor(str(fmt.get("background_color") or "#FFFFFF")))
                item.setTextAlignment(int((Qt.AlignHCenter if fmt.get("align") == "center" else Qt.AlignRight if fmt.get("align") == "right" else Qt.AlignLeft) | Qt.AlignVCenter))
            self.table.horizontalHeader().show()
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(False)
        self.table.setSortingEnabled(False)
        self.table.setWordWrap(False)
        self.table.setTextElideMode(Qt.TextElideMode.ElideRight)
        body_size = int(self.page_chrome.get("body_font_size", 10))
        print_font = str(self.page_chrome.get("print_font_family") or "Arial")
        self.table.setStyleSheet(
            self.table.styleSheet()
            + f"QTableWidget {{ font-family:'{print_font}'; font-size:{body_size}pt; }}"
        )
        group_trait_px = _trait_css_width(
            self.advanced_style.get("group_trait") or "1pt"
        )
        border_mode = str(self.advanced_style.get("detail_borders") or "none")
        line_width = _trait_css_width(self.advanced_style.get("detail_trait") or "none")
        if border_mode == "grid":
            table_border_css = "QTableWidget::item { border-right:1px solid #000000; border-bottom:1px solid #000000; }"
        elif border_mode == "horizontal":
            table_border_css = "QTableWidget::item { border-bottom:1px solid #000000; }"
        elif line_width != "0px":
            table_border_css = f"QTableWidget::item {{ border-bottom:{line_width} solid #000000; }}"
        else:
            table_border_css = "QTableWidget::item { border:0; }"
        # A Qt item stylesheet overrides the per-cell font and foreground roles
        # on Windows. Keep native painting for graphic detailed reports.
        if self.detail_graphic:
            self.table.setStyleSheet("")
        else:
            self.table.setStyleSheet(self.table.styleSheet() + table_border_css)
        header = self.table.horizontalHeader()
        header_family = str(
            self.advanced_style.get("column_header_font_family") or "Calibri"
        )
        header_text = str(self.advanced_style.get("column_header_text_color") or "#111111")
        header_bg = str(self.advanced_style.get("column_header_bg_color") or "#DDE8E2")
        header_size = int(self.advanced_style.get("column_header_font_size", 10))
        header_weight = "700" if bool(self.advanced_style.get("column_header_bold", True)) else "400"
        header_italic = "italic" if bool(self.advanced_style.get("column_header_italic", False)) else "normal"
        header_decoration = "underline" if bool(self.advanced_style.get("column_header_underline", False)) else "none"
        # 27.43 : ne plus imposer couleur/fond/police par feuille de style.
        # Une QSS sur QHeaderView::section écrasait les rôles Font/Foreground/
        # Background portés par chaque QTableWidgetItem d'en-tête. Les valeurs
        # individuelles définies dans le constructeur peuvent ainsi atteindre
        # réellement la Vue ; le style global reste le défaut des items.
        # 27.44 : aucune QSS sur QHeaderView::section. Sous Qt/Windows, la
        # moindre règle de style appliquée aux sections prend la main sur le
        # BackgroundRole des QTableWidgetItem d'en-tête. C'était la raison pour
        # laquelle police/couleur de texte étaient visibles mais pas le fond
        # individuel choisi dans le constructeur. Le rendu natif de QHeaderView
        # conserve ses bordures ; chaque section peut désormais peindre son
        # propre fond via item.setBackground().
        header.setStyleSheet("")
        header.setSectionsMovable(True)
        header.setSectionsClickable(bool(self.detail_graphic))
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        if self.detail_graphic:
            # Le tableau contient des lignes structurelles (champ maître, repères,
            # espacements). QTableWidget.sortItems() ne sait pas les préserver.
            # On garde donc le tri natif désactivé et on trie seulement les fiches
            # à l'intérieur de chaque groupe lors d'un clic sur un en-tête.
            header.setSortIndicatorShown(True)
            self.table.setSortingEnabled(False)
            # 27.252 — le QHeaderView reste le pilote du tri : le tri natif du
            # QTableWidget demeure interdit (il casserait les groupes), mais le
            # clic sur chaque section déclenche notre tri interne.
            header.setSectionsClickable(True)
            header.sectionClicked.connect(self._detail_header_clicked)
            # Mémoriser immédiatement les largeurs changées dans l'aperçu.
            # Auparavant elles n'étaient recopiées qu'en closeEvent ; or Retour
            # et Modifier ferment le dialogue par accept(), sans closeEvent fiable.
            header.sectionResized.connect(lambda *_: self._persist_preview_state())
            header.sectionMoved.connect(lambda *_: self._persist_preview_state())
        saved_level = self.layout_state.get("group_sort_level")
        saved_desc = self.layout_state.get("group_sort_desc")
        if isinstance(saved_level, int) and 0 <= saved_level < len(self.groupings):
            self.group_sort_level = saved_level
            self.group_sort_combo.setCurrentIndex(saved_level)
        if isinstance(saved_desc, list) and not self.detail_graphic:
            for i, value in enumerate(saved_desc[:len(self.group_sort_desc)]):
                self.group_sort_desc[i] = bool(value)
        self._update_group_sort_button()
        saved_detail_sort = self.layout_state.get("detail_sort_field")
        if saved_detail_sort in self.fields:
            self.detail_sort_field = saved_detail_sort
            self.detail_sort_desc = bool(self.layout_state.get("detail_sort_desc", False))
            header.setSortIndicator(
                self.fields.index(saved_detail_sort),
                Qt.SortOrder.DescendingOrder if self.detail_sort_desc else Qt.SortOrder.AscendingOrder,
            )

        self._build_grouped_rows()
        if not self.detail_graphic:
            self.table.resizeColumnsToContents()
        self._apply_saved_layout()
        if self.detail_graphic:
            # IMPORTANT : ne jamais réactiver le tri natif ici. Il mélange les
            # bandeaux de champ maître avec les lignes de fiches.
            self.table.setSortingEnabled(False)
        self.table.cellDoubleClicked.connect(self._open_record_from_number)
        if self.detail_graphic:
            # 1.0.140 — la table dessine elle-même les sauts et N° de page.
            self.table.set_preview_pagination(
                bool(self.page_chrome.get("show_page_numbers", False)),
                str(self.page_chrome.get("page_number_format") or "page_x_y"),
                str(self.page_chrome.get("footer_align") or "right"),
            )
            # Ancien calque conservé mais désactivé : la table est désormais
            # l'unique source de la pagination visuelle de l'Aperçu.
            # 1.0.127 — repères de pagination visibles pendant le défilement.
            # Ils suivent la feuille et n'altèrent ni les données ni l'impression.
            self.table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
            self._detail_page_overlay = None
            def _refresh_detail_pages(*_):
                ov = getattr(self, "_detail_page_overlay", None)
                if ov is not None:
                    ov.setGeometry(self.table.viewport().rect()); ov.raise_(); ov.update()
            self.table.verticalScrollBar().valueChanged.connect(_refresh_detail_pages)
            self.table.verticalScrollBar().rangeChanged.connect(_refresh_detail_pages)
            self.table.horizontalScrollBar().valueChanged.connect(_refresh_detail_pages)
            # 1.0.138 — Qt finalise la géométrie du viewport après show().
            # Recaler plusieurs fois le calque évite un overlay de pagination
            # resté à 0x0 lors de la première ouverture de l’Aperçu.
            QTimer.singleShot(0, _refresh_detail_pages)
            QTimer.singleShot(80, _refresh_detail_pages)
            QTimer.singleShot(250, _refresh_detail_pages)
            # 1.0.142 — une fois le tableau construit, demander au vrai moteur
            # d'impression son total de pages, sans ouvrir l'écran d'impression.
            QTimer.singleShot(0, self._sync_preview_print_page_count)
        lay.addWidget(self.table, 1)

        if self.detail_graphic:
            footer_metrics_html = self._graphic_footer_metrics_html()
            if footer_metrics_html:
                footer_metrics = QLabel(footer_metrics_html)
                footer_metrics.setTextFormat(Qt.TextFormat.RichText)
                footer_metrics.setWordWrap(True)
                lay.addWidget(footer_metrics)

        footer_parts = []
        footer_text = str(self.page_chrome.get("footer_text") or "").strip()
        if footer_text:
            footer_parts.append(footer_text)
        if bool(self.page_chrome.get("show_page_numbers", True)) and not self.detail_graphic:
            footer_parts.append("Page 1 / 1")
        if footer_parts:
            footer = QLabel(" — ".join(footer_parts))

            footer_align = str(self.page_chrome.get("footer_align") or "right")
            if footer_align == "center":
                footer.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
            elif footer_align == "left":
                footer.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            else:
                footer.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

            footer_size = int(self.page_chrome.get("footer_font_size", 10))
            footer_bold = bool(self.page_chrome.get("footer_bold", False))
            footer_italic = bool(self.page_chrome.get("footer_italic", False))
            footer_underline = bool(self.page_chrome.get("footer_underline", False))
            footer_color = str(self.page_chrome.get("footer_text_color") or "#4F5A55")
            footer_bg = "#FFFFFF"  # 1.0.112 — fond de feuille blanc dans l’Aperçu

            font = footer.font()
            font.setPointSize(footer_size)
            font.setBold(footer_bold)
            font.setItalic(footer_italic)
            font.setUnderline(footer_underline)
            footer.setFont(font)

            weight = "700" if footer_bold else "400"
            style_name = "italic" if footer_italic else "normal"
            decoration = "underline" if footer_underline else "none"
            footer.setStyleSheet(
                "QLabel {"
                f"color:{footer_color}; background-color:{footer_bg};"
                "border-top:1px solid #AAB5B0;"
                "padding:5px 6px 2px 6px;"
                f"font-size:{footer_size}pt; font-weight:{weight};"
                f"font-style:{style_name}; text-decoration:{decoration};"
                "}"
            )
            if self.detail_graphic:
                footer.setMaximumWidth(getattr(self, "_detail_page_width", 760))
            lay.addWidget(footer)
            self._print_summary_page_footer = footer

        self._apply_body_font_to_cells()
        self._apply_compact_row_heights()
        self._install_screen_zoom(lay)

        actions = QHBoxLayout()
        actions.addStretch(1)
        modify_btn = QPushButton(tr("Modifier", self.language))
        save_btn = QPushButton(tr("Enregistrer l’état", self.language))
        library_btn = QPushButton(tr("Enregistrer sous…", self.language))
        library_btn.setToolTip(tr("Conserver cet état dans la bibliothèque Modèles d’États", self.language))
        library_btn.clicked.connect(lambda: self.owner.save_report_to_library(self.saved_name, getattr(self, "builder_page", None)))
        print_btn = QPushButton(tr("Imprimer", self.language))
        back = QPushButton(tr("Retour", self.language))
        modify_btn.clicked.connect(
            lambda: self.owner._modify_report_from_preview(
                self,
                self.saved_name,
                getattr(self, "builder_page", None),
            )
        )
        save_btn.clicked.connect(self._save_report)
        print_btn.setToolTip(tr("Aperçu avant impression multipage", self.language))
        print_btn.clicked.connect(self._print)
        # Impression compacte : le tableau de l'aperçu, sans la composition
        # graphique multipage. Ne remplace pas le bouton Imprimer existant.
        table_print_btn = QPushButton(
            "Print table" if str(self.language).lower().startswith("en")
            else ("Tabelle drucken" if str(self.language).lower().startswith("de")
                  else "Imprimer le tableau")
        )
        table_print_btn.setToolTip(
            "Imprimer les lignes et colonnes du tableau, dans leur ordre visible"
        )
        table_print_btn.clicked.connect(self._print_preview_table_direct)
        actions.addWidget(table_print_btn)
        back.clicked.connect(self.accept)
        actions.addWidget(modify_btn)
        actions.addWidget(save_btn)
        actions.addWidget(library_btn)
        actions.addWidget(print_btn)
        actions.addWidget(back)
        lay.addLayout(actions)

        self.setStyleSheet("""
            #previewTitle { }
            #mainCount { font-size:17px; font-weight:700; color:#8B3026; }
            #secondaryCount { color:#7A817D; }
            #previewHint { color:#66716B; }
        """)




    def _apply_body_font_to_cells(self) -> None:
        """Préserve les styles Champ répété et Détail de la fiche."""
        typography = dict(self.advanced_style.get("typography") or {})
        repeat_style = dict(typography.get("repeat") or {})
        detail_style = dict(typography.get("detail") or {})
        repeat_field = self.atelier_style.get("repeat_master_field")

        # Le constructeur graphique porte ses propres styles par champ
        # (dont les alignements). Ils sont déjà appliqués pendant la construction
        # du tableau : ne pas les écraser ensuite avec le style générique.
        if self.detail_graphic:
            return

        for row in range(self.table.rowCount()):
            # Les bandeaux Niveau 1/2/3 gardent leur typographie propre.
            if self.table.columnSpan(row, 0) > 1:
                continue

            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                if item is None:
                    continue

                field = self.fields[col] if 0 <= col < len(self.fields) else ""
                style = (
                    repeat_style
                    if repeat_field and field == repeat_field
                    else detail_style
                )

                family = str(
                    style.get("font_family")
                    or self.page_chrome.get("print_font_family")
                    or "Arial"
                )
                size = int(
                    style.get(
                        "font_size",
                        self.page_chrome.get("body_font_size", 10),
                    )
                )

                font = QFont()
                font.setFamily(family)
                font.setPointSize(size)
                font.setBold(bool(style.get("bold", False)))
                font.setItalic(
                    bool(
                        style.get(
                            "italic",
                            True if repeat_field and field == repeat_field else False,
                        )
                    )
                )
                font.setUnderline(bool(style.get("underline", False)))
                item.setFont(font)

                item.setForeground(
                    QColor(
                        str(
                            style.get(
                                "text_color",
                                self.atelier_style.get(
                                    "repeat_master_color", "#9A3324"
                                )
                                if repeat_field and field == repeat_field
                                else "#111111",
                            )
                        )
                    )
                )
                item.setBackground(
                    QColor(str(style.get("bg_color") or "#FFFFFF"))
                )

                align = str(
                    (
                        style.get("align", "left")
                        if repeat_field and field == repeat_field
                        else self.detail_column_alignments.get(
                            field, style.get("align", "left")
                        )
                    )
                )
                if align == "center":
                    item.setTextAlignment(int(Qt.AlignHCenter | Qt.AlignVCenter))
                elif align == "right":
                    item.setTextAlignment(int(Qt.AlignRight | Qt.AlignVCenter))
                else:
                    item.setTextAlignment(int(Qt.AlignLeft | Qt.AlignVCenter))

    def _apply_compact_row_heights(self) -> None:
        """Adapte la hauteur aux tailles Détail / Champ répété."""
        typography = dict(self.advanced_style.get("typography") or {})
        detail_size = int(
            dict(typography.get("detail") or {}).get(
                "font_size", self.page_chrome.get("body_font_size", 10)
            )
        )
        repeat_size = int(
            dict(typography.get("repeat") or {}).get("font_size", detail_size)
        )
        body_size = max(detail_size, repeat_size)
        # Valeurs volontairement serrées pour retrouver un état dense type Access.
        if body_size <= 6:
            height = 16
        elif body_size == 7:
            height = 18
        elif body_size == 8:
            height = 20
        elif body_size == 9:
            height = 22
        else:
            height = 24

        for row in range(self.table.rowCount()):
            # Ne pas écraser les gros bandeaux de regroupement.
            if self.table.columnSpan(row, 0) > 1:
                continue
            self.table.setRowHeight(row, height)

    def _install_screen_zoom(self, lay) -> None:
        """Loupe d'affichage uniquement — ne modifie jamais l'état imprimé."""
        self._screen_zoom_percent = 100
        self._zoom_base_table_font = QFont(self.table.font())
        self._zoom_base_table_style = self.table.styleSheet()
        self._zoom_base_header_style = self.table.horizontalHeader().styleSheet()
        self._zoom_base_col_widths = [
            self.table.columnWidth(i) for i in range(self.table.columnCount())
        ]
        self._zoom_base_row_heights = [
            self.table.rowHeight(i) for i in range(self.table.rowCount())
        ]

        self._zoom_label_bases = []
        for label in self.findChildren(QLabel):
            self._zoom_label_bases.append(
                (
                    label,
                    QFont(label.font()),
                    label.styleSheet(),
                    label.text(),
                    label.textFormat(),
                )
            )

        row = QHBoxLayout()
        row.setContentsMargins(0, 2, 0, 2)
        row.addWidget(QLabel(tr("Loupe :", self.language)))

        minus = QPushButton("−")
        minus.setFixedWidth(32)
        minus.setToolTip("Réduire l’affichage")

        zoom = QComboBox()
        zoom.setEditable(True)
        zoom.setFixedWidth(82)
        for value in (50, 60, 70, 80, 90, 100, 110, 125, 150, 175, 200):
            zoom.addItem(f"{value} %", value)
        zoom.setCurrentIndex(zoom.findData(100))
        zoom.setToolTip(
            "Agrandit ou réduit seulement l’affichage de l’état. "
            "La taille d’impression n’est pas modifiée."
        )

        plus = QPushButton("+")
        plus.setFixedWidth(32)
        plus.setToolTip("Agrandir l’affichage")

        row.addWidget(minus)
        row.addWidget(zoom)
        row.addWidget(plus)
        # 1.0.137 — le grisage est un choix de l’Aperçu, jamais une commande
        # de l’écran d’impression multipage. Aucun document d’impression n’est
        # reconstruit au clic : seules les cellules déjà visibles sont repeintes.
        zebra = QCheckBox(tr("Lignes alternées grisées", self.owner.language))
        zebra.setChecked(bool(self.advanced_style.get("preview_zebra_rows", False)))
        zebra.setToolTip(tr("Griser une ligne de données sur deux dans l’aperçu et à l’impression", self.owner.language))
        header_gray = QCheckBox(tr("En-têtes de colonnes grisés", self.owner.language))
        header_gray.setChecked(bool(self.advanced_style.get("preview_gray_column_headers", False)))
        header_gray.setToolTip(tr("Griser les en-têtes de colonnes dans l’aperçu et à l’impression", self.owner.language))
        # Même présentation que l'état résumé : options de grisage superposées.
        gray_box = QVBoxLayout()
        gray_box.setContentsMargins(18, 0, 0, 0)
        gray_box.setSpacing(2)
        gray_box.addWidget(zebra)
        gray_box.addWidget(header_gray)
        row.addLayout(gray_box)
        row.addStretch(1)
        lay.addLayout(row)

        self.preview_zebra_checkbox = zebra
        self.preview_header_gray_checkbox = header_gray
        self.screen_zoom_widget = zoom

        def apply_zebra(checked):
            checked = bool(checked)
            self.advanced_style["preview_zebra_rows"] = checked
            page = getattr(self, "builder_page", None)
            if page is not None:
                page.preview_zebra_rows = checked
            gray = QColor("#F2F2F2")
            detail_style = dict((self.advanced_style.get("typography") or {}).get("detail") or {})
            repeat_style = dict((self.advanced_style.get("typography") or {}).get("repeat") or {})
            repeat_field = self.atelier_style.get("repeat_master_field")
            for data_index, table_row in enumerate(getattr(self, "_detail_data_rows", [])):
                shaded = checked and (data_index % 2 == 1)
                for col, field in enumerate(self.fields):
                    item = self.table.item(table_row, col)
                    if item is None:
                        continue
                    if shaded:
                        item.setBackground(gray)
                    else:
                        base = repeat_style if repeat_field and field == repeat_field else detail_style
                        item.setBackground(QColor(str(base.get("bg_color") or "#FFFFFF")))
            self.table.viewport().update()

        zebra.toggled.connect(apply_zebra)

        def apply_header_gray(checked):
            checked = bool(checked)
            self.advanced_style["preview_gray_column_headers"] = checked
            page = getattr(self, "builder_page", None)
            if page is not None:
                page.preview_gray_column_headers = checked
            label_styles = dict((self.detail_graphic or {}).get("detail_label_styles") or {})
            for col, field in enumerate(self.fields):
                item = self.table.horizontalHeaderItem(col)
                if item is None:
                    continue
                original = str((label_styles.get(field) or {}).get("background_color") or "#FFFFFF")
                item.setBackground(QColor("#F2F2F2" if checked else original))
            self.table.horizontalHeader().viewport().update()

        header_gray.toggled.connect(apply_header_gray)
        apply_header_gray(header_gray.isChecked())
        apply_zebra(zebra.isChecked())

        def current_percent():
            text = zoom.currentText().strip().replace("%", "").replace(",", ".")
            try:
                return int(round(float(text)))
            except Exception:
                return int(self._screen_zoom_percent)

        def apply_from_combo(*_):
            self._apply_screen_zoom(current_percent())

        def step(delta):
            value = max(40, min(250, current_percent() + delta))
            zoom.blockSignals(True)
            idx = zoom.findData(value)
            if idx >= 0:
                zoom.setCurrentIndex(idx)
            else:
                zoom.setEditText(f"{value} %")
            zoom.blockSignals(False)
            self._apply_screen_zoom(value)

        minus.clicked.connect(lambda: step(-10))
        plus.clicked.connect(lambda: step(10))
        zoom.currentTextChanged.connect(apply_from_combo)
        if zoom.lineEdit() is not None:
            zoom.lineEdit().editingFinished.connect(apply_from_combo)

    @staticmethod
    def _scaled_font_sizes_in_text(text: str, factor: float) -> str:
        def repl(match):
            value = float(match.group(1))
            scaled = max(5.0, value * factor)
            shown = f"{scaled:.1f}".rstrip("0").rstrip(".")
            return f"font-size:{shown}pt"
        return re.sub(r"font-size\s*:\s*([0-9]+(?:\.[0-9]+)?)pt", repl, text)

    def _apply_screen_zoom(self, percent: int) -> None:
        """Applique la loupe aux widgets visibles, sans toucher aux paramètres."""
        percent = max(40, min(250, int(percent)))
        self._screen_zoom_percent = percent
        factor = percent / 100.0

        # Tableau et en-têtes.
        font = QFont(self._zoom_base_table_font)
        base_size = font.pointSizeF()
        if base_size <= 0:
            base_size = 10.0
        font.setPointSizeF(max(5.0, base_size * factor))
        self.table.setFont(font)

        self.table.setStyleSheet(
            self._scaled_font_sizes_in_text(self._zoom_base_table_style, factor)
        )
        self.table.horizontalHeader().setStyleSheet(
            self._scaled_font_sizes_in_text(self._zoom_base_header_style, factor)
        )

        for i, width in enumerate(self._zoom_base_col_widths):
            self.table.setColumnWidth(i, max(24, int(round(width * factor))))
        for i, height in enumerate(self._zoom_base_row_heights):
            self.table.setRowHeight(i, max(16, int(round(height * factor))))

        # Titres, compteurs, bandeaux et pied de page.
        for label, base_font, base_style, base_text, text_format in self._zoom_label_bases:
            f = QFont(base_font)
            size = f.pointSizeF()
            if size > 0:
                f.setPointSizeF(max(5.0, size * factor))
                label.setFont(f)
            label.setStyleSheet(
                self._scaled_font_sizes_in_text(base_style, factor)
            )
            if (
                text_format == Qt.TextFormat.RichText
                or "font-size" in base_text.lower()
                or "<span" in base_text.lower()
            ):
                label.setText(
                    self._scaled_font_sizes_in_text(base_text, factor)
                )


    def _apply_advanced_preview_style(self, widget) -> None:
        """Style de l'en-tête général, avec compatibilité des anciens états."""
        legacy = dict(getattr(self, "advanced_style", {}) or {})
        chrome = dict(getattr(self, "page_chrome", {}) or {})
        if widget is None:
            return

        size = int(chrome.get("title_font_size", legacy.get("font_size", 20)))
        bold = bool(chrome.get("title_bold", True))
        italic = bool(chrome.get("title_italic", legacy.get("italic", False)))
        underline = bool(chrome.get("title_underline", legacy.get("underline", False)))

        font = widget.font()
        font.setFamily(str(chrome.get("print_font_family") or "Arial"))
        font.setPointSize(size)
        font.setBold(bold)
        font.setItalic(italic)
        font.setUnderline(underline)
        widget.setFont(font)

        align = str(chrome.get("title_align") or legacy.get("align", "left"))
        if align == "center":
            widget.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        elif align == "right":
            widget.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        else:
            widget.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        text_color = str(chrome.get("title_text_color") or "#111111")
        bg_color = "#FFFFFF"  # 1.0.112 — Aperçu: la feuille reste blanche, indépendamment du fond du constructeur
        weight = "700" if bold else "400"
        style_name = "italic" if italic else "normal"
        decoration = "underline" if underline else "none"

        widget.setStyleSheet(
            "QLabel {"
            f"color:{text_color}; background-color:{bg_color};"
            f"font-size:{size}pt; font-weight:{weight};"
            f"font-style:{style_name}; text-decoration:{decoration};"
            "padding:4px 6px;"
            "}"
        )


    def _make_detail_metric_label(self,text,semantic):
        style=dict(self.atelier_style or {})
        family=str(style.get(f"metric_{semantic}_font") or "Calibri")
        size=int(style.get(f"metric_{semantic}_size",10))
        color=str(style.get(f"metric_{semantic}_color") or "#8B3026")
        metric_settings = dict((self.detail_graphic or {}).get("summary_header_metrics") or {})
        band_bg = str((metric_settings.get("band_style") or {}).get("bg") or "")
        bg = (("transparent" if band_bg.upper() == "#F4F6F5" else (band_bg or "transparent"))
              if self.detail_graphic else str(style.get(f"metric_{semantic}_bg") or "#F4F6F5"))
        lbl=QLabel(text); font=QFont(); font.setFamily(family); font.setPointSize(size)
        font.setBold(bool(style.get(f"metric_{semantic}_bold",False)))
        font.setItalic(bool(style.get(f"metric_{semantic}_italic",False)))
        font.setUnderline(bool(style.get(f"metric_{semantic}_underline",False)))
        lbl.setFont(font); lbl.setStyleSheet(f"QLabel {{ color:{color}; background:{bg}; padding:1px 3px; }}")
        return lbl

    def _graphic_metric(self, field, records):
        treatment = self.owner._summary_treatment(
            field, (self.detail_graphic.get("summary_treatments") or {}).get(field))
        values = [r.get(field) for r in records if r.get(field) not in (None, "")]
        if treatment in {"sum", "avg", "min", "max"}:
            # Les champs calculés (dont Coût total / Total cost) ne sont pas
            # forcément stockés dans la fiche : utiliser le même moteur numérique
            # que les États résumés pour les recalculer fiche par fiche.
            nums = [self.owner._summary_numeric_value(r, field) for r in records]
            result = (sum(nums) if treatment == "sum" else
                      sum(nums) / len(nums) if treatment == "avg" and nums else
                      min(nums) if treatment == "min" and nums else
                      max(nums) if treatment == "max" and nums else 0)
        else:
            result = len({str(v).strip().casefold() for v in values if str(v).strip()})
        label = (self.detail_graphic.get("summary_header_metrics", {}).get("selected_labels", {}) or {}).get(field)
        label = label or (tr("pièce(s)", self.language) if field == "box_count" else self.owner.labels.get(field, field).lower())
        if treatment in {"sum", "avg", "min", "max"} and self.owner._is_numeric_field(field):
            number_text = self.owner._summary_total_text(field, result)
            if str(self.language or "fr").lower().startswith("en"):
                number_text = number_text.replace(",", ".")
        else:
            number_text = self.owner._fmt_number(result)
        return f"{number_text} {label}"

    def _graphic_footer_metrics_html(self):
        """Contenu réel du pied de page, partagé par l'écran et le papier."""
        if not self.detail_graphic:
            return ""
        metrics = dict(self.detail_graphic.get("summary_header_metrics") or {})
        linked = bool(metrics.get("footer_linked", False))
        if linked:
            fields = list(dict.fromkeys(str(f) for f in metrics.get("selected_fields") or []))
            if metrics.get("records", False) and "__records__" not in fields:
                fields.append("__records__")
        else:
            chosen = set(str(f) for f in metrics.get("footer_fields") or [])
            if not metrics.get("records", False):
                chosen.discard("__records__")
            fields = list(dict.fromkeys(
                [str(f) for f in metrics.get("footer_order") or [] if str(f) in chosen]
                + [str(f) for _label, f in self.owner.fields if str(f) in chosen]
            ))
            if "__records__" in chosen:
                fields.append("__records__")
        if not fields:
            return ""

        base = dict(metrics.get("footer_style") or {})
        family = str(base.get("font") or "Calibri")
        size = int(base.get("size", 10))
        color = str(base.get("text") or "#111111")
        bits = []
        widths = dict(metrics.get("metric_widths") or {}) if linked else dict(metrics.get("footer_metric_widths") or {})
        positions = dict(metrics.get("metric_positions") or {}) if linked else dict(metrics.get("footer_metric_positions") or {})
        if positions:
            fields = sorted(fields, key=lambda f: int(positions.get(str(f), 10**9)))
        _footer_html_cursor = 0
        for field in fields:
            if field == "__records__":
                number, default = str(self.owner._record_count(self.records)), tr("fiche(s)", self.language)
            elif field in self.owner.labels:
                treatment = self.owner._summary_treatment(
                    field, (self.detail_graphic.get("summary_treatments") or {}).get(field))
                values = [r.get(field) for r in self.records if r.get(field) not in (None, "")]
                if treatment in {"sum", "avg", "min", "max"}:
                    nums = [self.owner._summary_numeric_value(r, field) for r in self.records]
                    result = (sum(nums) if treatment == "sum" else
                              sum(nums) / len(nums) if treatment == "avg" and nums else
                              min(nums) if treatment == "min" and nums else
                              max(nums) if treatment == "max" and nums else 0)
                    number = self.owner._fmt_number(result)
                else:
                    number = str(self.owner._distinct_count(self.records, field))
                default = (tr("pièce(s)", self.language) if field == "box_count" else
                           self.owner.labels.get(field, field).lower() + "(s)")
            else:
                continue
            label = str((metrics.get("footer_metric_labels") or {}).get(field) or
                        ((metrics.get("selected_labels") or {}).get(field) if linked else "") or
                        default)
            styles = dict((metrics.get("footer_metric_styles") or {}).get(field) or {})
            value_style = dict(styles.get("value") or {})
            label_style = dict(styles.get("label") or {})
            def part(content, chosen, default_bold):
                font = _escape(str(chosen.get("font") or family))
                font_size = int(chosen.get("size", size))
                ink = _escape(str(chosen.get("text") or color))
                bold = 700 if chosen.get("bold", base.get("bold", default_bold)) else 400
                italic = "italic" if chosen.get("italic", base.get("italic", False)) else "normal"
                # Même conversion que les données du résumé, validée sur papier.
                px = font_size * 96.0 / 72.0
                return (f"<span style='font-family:{font};font-size:{px:g}px;"
                        f"color:{ink};font-weight:{bold};font-style:{italic};'>"
                        f"{_escape(content)}</span>")
            gap = int((metrics.get("footer_metric_spacing") or {}).get(field, 8 if linked else 16))
            text = part(number, value_style, True) + part(" " + label, label_style, True)
            width = widths.get(field)
            _w = max(55, min(480, int(width))) if width else 90
            if positions:
                _x = max(0, int(positions.get(str(field), _footer_html_cursor)))
                if _x > _footer_html_cursor:
                    bits.append(f'<td width="{_x-_footer_html_cursor}"></td>')
                bits.append(f'<td width="{_w}" style="border:0;padding:0;white-space:nowrap;">' + text + '</td>')
                _footer_html_cursor = max(_footer_html_cursor, _x) + _w
            else:
                bits.append((f'<td width="{_w}" style="border:0;padding:0;white-space:nowrap;">'
                             + text + '</td><td width="%d"></td>' % max(0, gap)) if width
                            else '<td style="border:0;padding:0;white-space:nowrap;">' + text
                                 + '</td><td width="%d"></td>' % max(0, gap))
        if not bits:
            return ""
        align = str(base.get("align") or "left")
        background = _escape(str(base.get("bg") or "#FFFFFF"))
        return (f"<div style='text-align:{align};background:{background};"
                f"border-top:1px solid #AAB5B0;padding:5px 7px;margin-top:8px;'>"
                + '<table cellspacing="0" cellpadding="0" style="border:0;"><tr>'
                + "".join(bits) + '</tr></table></div>')

    def _build_grouped_rows(self):
        self._detail_group_rows = set()
        self._detail_label_rows = set()
        self._detail_after_label_marks = {}
        self._detail_between_master_marks = {}
        self._detail_data_rows = []
        self.table.setRowCount(0)
        self._record_row_ids = {}

        def add_group_header(level, value, subset):
            if level == 0 and self.table.rowCount() > 0:
                raw = (self.advanced_style.get("summary_layout_marks") or {}).get("between_masters") if self.detail_graphic else None
                marks = raw if isinstance(raw, list) else ([raw] if raw else [])
                marks = [m for m in marks if isinstance(m, dict) and m.get("kind") in {"line", "space"}]
                # Un interligne réglé remplace l'espacement automatique.
                auto_lines = 0 if self.detail_graphic else (0 if any(m.get("kind") == "space" for m in marks) else int(self.atelier_style.get("primary_spacing_lines", 2)))
                for _ in range(max(0, auto_lines)):
                    spacer = self.table.rowCount()
                    self.table.insertRow(spacer)
                    self.table.setRowHeight(spacer, int(self.atelier_style.get("spacing_height", 22)))
                    for col in range(self.table.columnCount()):
                        item = QTableWidgetItem("")
                        item.setFlags(Qt.ItemFlag.NoItemFlags)
                        item.setBackground(QColor("#FFFFFF"))
                        self.table.setItem(spacer, col, item)
                for mark in sorted(marks, key=lambda m: 0 if m["kind"] == "line" else 1):
                    kind = str(mark["kind"])
                    size = float(mark.get("size") or (8 if kind == "space" else 0.5))
                    color = str(mark.get("color") or "#000000")
                    marker_row = self.table.rowCount()
                    self.table.insertRow(marker_row)
                    if self.table.columnCount() > 1:
                        self.table.setSpan(marker_row, 0, 1, self.table.columnCount())
                    self.table.setRowHeight(marker_row, max(2, round(size * float(self.table.logicalDpiY() or 96) / 72.0)) if kind == "space" else max(3, round((size + 2) * float(self.table.logicalDpiY() or 96) / 72.0)))
                    blank = QTableWidgetItem("")
                    blank.setFlags(Qt.ItemFlag.NoItemFlags)
                    self.table.setItem(marker_row, 0, blank)
                    if kind == "line":
                        line = QFrame()
                        line.setStyleSheet(f"QFrame {{ border:0; border-top:{max(0.5,size):g}px solid {color}; background:#FFFFFF; }}")
                        self.table.setCellWidget(marker_row, 0, line)
                    self._detail_between_master_marks[marker_row] = (kind, size, color)

            row = self.table.rowCount()
            self.table.insertRow(row)
            self._detail_group_rows.add(row)
            # Qt ne peut fusionner une ligne quand il n'existe qu'une colonne.
            if self.table.columnCount() > 1:
                self.table.setSpan(row, 0, 1, self.table.columnCount())

            boxes = sum(_number(rec.get("box_count")) for rec in subset)
            species = self.owner._species_count(subset)
            label = self.owner._grouping_label(self.groupings[level])
            prefix = "" if level == 0 else ("&nbsp;" * (4 * level)) + "↳&nbsp;"

            base_text_color = (
                self.atelier_style.get("level1_text", "#9A3324"),
                self.atelier_style.get("level2_text", "#111111"),
                self.atelier_style.get("level3_text", "#737B77"),
            )[min(level, 2)]

            # La couleur Texte avancée doit piloter TOUT le bandeau :
            # libellé, valeur, nombres, unités et nombre de fiches.
            adv_typography = dict(
                (self.advanced_style or {}).get("typography", {}) or {}
            )
            level_style = dict(
                adv_typography.get(f"level{level+1}") or {}
            )
            strong_color = str(
                level_style.get("text_color", base_text_color)
            )
            level_weight = (
                "700" if bool(level_style.get("bold", True)) else "400"
            )
            level_family = str(level_style.get("font_family") or "Calibri")

            html = (
                f"{prefix}"
                f"<span style='font-family:{_escape(level_family)};color:{strong_color};"
                f"font-weight:{level_weight}'>{_escape(label)} :</span> "
                f"<span style='font-family:{_escape(level_family)};color:{strong_color};"
                f"font-weight:{level_weight}'>{_escape(value)}</span>"
                f"&nbsp;&nbsp;—&nbsp;&nbsp;"
                f"<span style='font-family:{_escape(level_family)};color:{strong_color};"
                f"font-weight:{level_weight}'>{self.owner._fmt_number(boxes)} boîtes</span>"
                f"&nbsp;&nbsp;—&nbsp;&nbsp;"
                f"<span style='font-family:{_escape(level_family)};color:{strong_color};"
                f"font-weight:{level_weight}'>{species} espèces</span>"
                f"&nbsp;&nbsp;—&nbsp;&nbsp;"
                f"<span style='font-family:{_escape(level_family)};color:{strong_color};"
                f"font-weight:{level_weight}'>{len(subset)} fiche(s)</span>"
            )

            if self.detail_graphic:
                master_field = self.groupings[level]
                fmt = dict((self.detail_graphic.get("detail_master_styles") or {}).get(master_field) or {})
                family = _escape(str(fmt.get("font_family") or "Arial"))
                color = _escape(str(fmt.get("text_color") or "#111111"))
                weight = "700" if fmt.get("bold") else "400"
                italic = "italic" if fmt.get("italic") else "normal"
                size = int(fmt.get("font_size") or 10)
                html = (f"<span style='font-family:{family};font-size:{size}pt;color:{color};"
                        f"font-weight:{weight};font-style:{italic}'>{_escape(value)}</span>")
                for metric_field in self.detail_graphic.get("detail_group_totals") or []:
                    if metric_field in self.owner.labels:
                        total_fmt = dict((self.detail_graphic.get("detail_total_styles") or {}).get(metric_field) or {})
                        # 1.0.128 — un total reste atomique : retour à la ligne
                        # autorisé entre deux totaux, jamais entre sa valeur et son libellé.
                        metric = _escape(self._graphic_metric(metric_field, subset)).replace(" ", "&nbsp;")
                        html += ("&#8203;<span style='white-space:nowrap'>&nbsp;&nbsp;—&nbsp;&nbsp;<span style='font-family:" +
                                 _escape(str(total_fmt.get("font_family") or "Arial")) + ";font-size:" +
                                 str(int(total_fmt.get("font_size") or 9)) + "pt;color:" +
                                 _escape(str(total_fmt.get("text_color") or "#795422")) +
                                 ";font-weight:" + ("700" if total_fmt.get("bold") else "400") +
                                 ";font-style:" + ("italic" if total_fmt.get("italic") else "normal") +
                                 "'>" + metric + "</span></span>")

            item = QTableWidgetItem("")
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            base_background = (
                self.atelier_style.get("level1_bg", "#C8D8D0"),
                self.atelier_style.get("level2_bg", "#DDE8E2"),
                self.atelier_style.get("level3_bg", "#EEF3F0"),
            )[min(level, 2)]
            group_background = str(level_style.get("bg_color", base_background))
            # Associer le texte riche au modèle de la ligne, et non uniquement
            # au QLabel affiché. Les widgets peuvent être remplacés ou perdus
            # quand Qt reconstruit les lignes et la pagination.
            item.setData(Qt.ItemDataRole.UserRole, html)
            item.setBackground(QColor(group_background))
            self.table.setItem(row, 0, item)

            banner = QLabel()
            banner.setTextFormat(Qt.TextFormat.RichText)
            banner.setText(html)
            if self.detail_graphic:
                # 1.0.127 — les totaux par valeur maître doivent rester
                # entièrement lisibles, même lorsqu'ils sont nombreux.
                banner.setWordWrap(True)
                banner.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding)
            banner.setMargin(0 if self.detail_graphic else 8)
            adv = dict(self.advanced_style or {})
            typography = dict(adv.get("typography") or {})
            key = f"level{level+1}"
            typo = dict(typography.get(key) or {})
            if level == 0 and not typo:
                typo = {
                    "font_size": int(adv.get("font_size", 11)),
                    "bold": bool(adv.get("bold", True)),
                    "italic": bool(adv.get("italic", False)),
                    "underline": bool(adv.get("underline", False)),
                    "align": str(adv.get("align", "left")),
                }

            font = QFont()
            font.setFamily(str(typo.get("font_family") or "Calibri"))
            font.setPointSize(int(typo.get("font_size", 11 if level == 0 else 10)))
            font.setBold(bool(typo.get("bold", True)))
            font.setItalic(bool(typo.get("italic", False)))
            font.setUnderline(bool(typo.get("underline", False)))
            banner.setFont(font)

            # En état détaillé graphique, l'alignement du champ maître vient
            # du constructeur. Sinon on conserve l'alignement du bandeau standard.
            if self.detail_graphic:
                master_field = self.groupings[level]
                master_fmt = dict((self.detail_graphic.get("detail_master_styles") or {}).get(master_field) or {})
                align = str(master_fmt.get("align") or "left")
            else:
                align = str(typo.get("align", "left"))
            if align == "center":
                banner.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
            elif align == "right":
                banner.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            else:
                banner.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

            if level == 0 and not self.detail_graphic:
                custom = str(adv.get("header_title") or "").strip()
                if custom:
                    band_family = str(adv.get("band_font_family") or "Calibri")
                    banner.setText(
                        f"<span style='font-family:{_escape(band_family)};'><b>"
                        f"{_escape(custom)}</b></span>&nbsp;&nbsp;—&nbsp;&nbsp;" + html
                    )

            border = (
                "border-bottom:1px solid #7f8b87;"
                if level == 0 and bool(adv.get("separator", True))
                else "border:0px;"
            )
            text_color = str(typo.get("text_color", "#111111"))
            if self.detail_graphic:
                group_background = "#FFFFFF"
                text_color = "#111111"
            banner.setStyleSheet(
                f"background:{group_background}; color:{text_color}; padding:{'4px 0px' if self.detail_graphic else '4px'}; {border}"
            )
            banner.adjustSize()
            metrics = banner.fontMetrics()
            _group_height = max(32, metrics.height() + 14, banner.sizeHint().height() + 8)
            if self.detail_graphic:
                # 1.0.129 — autant de lignes que nécessaire, sans couper un total.
                _doc = QTextDocument(); _doc.setDefaultFont(banner.font()); _doc.setHtml(html)
                # Référence 1.0.144 : utiliser toute la largeur imprimable disponible.
                # Chaque total reste atomique et ne revient à la ligne que si nécessaire.
                _available = max(120, int(getattr(self, "_detail_page_width", self.table.viewport().width())))
                _doc.setTextWidth(_available)
                _group_height = max(_group_height, int(_doc.size().height()) + 12)
            self.table.setRowHeight(row, _group_height)
            self.table.setCellWidget(row, 0, banner)

        def add_record(record):
            row = self.table.rowCount()
            self.table.insertRow(row)
            self._detail_data_rows.append(row)
            if record.get("id") is not None:
                self._record_row_ids[row] = int(record["id"])
            for col, field in enumerate(self.fields):
                value = record.get(field, "")
                item = ReportDateItem(str(value or "")) if field == "acquisition_date" else QTableWidgetItem()
                if field == "record_number":
                    item.setData(Qt.ItemDataRole.DisplayRole, int(_number(value)))
                elif field == "box_count":
                    item.setData(Qt.ItemDataRole.DisplayRole, float(_number(value)))
                elif field == "price":
                    item.setText(_detail_display_value(field, value, self.language))
                elif self._detail_is_total_cost_field(field):
                    # Toujours recalculer via le moteur commun : les anciennes collections
                    # utilisent parfois une clé personnalisée pour « Coût total ».
                    item.setText(self._detail_total_cost_text(record, field))
                elif field != "acquisition_date":
                    item.setText(_detail_display_value(field, value, self.language))

                # Style réel du champ répété dans l'état groupé.
                repeat_field = self.atelier_style.get("repeat_master_field")
                if repeat_field and field == repeat_field:
                    repeat_style = dict(
                        (self.advanced_style or {})
                        .get("typography", {})
                        .get("repeat", {}) or {}
                    )

                    repeat_font = QFont()
                    repeat_font.setFamily(
                        str(repeat_style.get("font_family") or "Calibri")
                    )
                    repeat_font.setPointSize(
                        int(repeat_style.get("font_size", 10))
                    )
                    repeat_font.setBold(
                        bool(repeat_style.get("bold", False))
                    )
                    repeat_font.setItalic(
                        bool(repeat_style.get("italic", True))
                    )
                    repeat_font.setUnderline(
                        bool(repeat_style.get("underline", False))
                    )
                    item.setFont(repeat_font)

                    align = str(repeat_style.get("align", "left"))
                    if align == "center":
                        item.setTextAlignment(
                            int(Qt.AlignHCenter | Qt.AlignVCenter)
                        )
                    elif align == "right":
                        item.setTextAlignment(
                            int(Qt.AlignRight | Qt.AlignVCenter)
                        )
                    else:
                        item.setTextAlignment(
                            int(Qt.AlignLeft | Qt.AlignVCenter)
                        )

                    item.setForeground(
                        QColor(
                            str(
                                repeat_style.get(
                                    "text_color",
                                    self.atelier_style.get("repeat_master_color", "#9A3324")
                                )
                            )
                        )
                    )
                    item.setBackground(
                        QColor(str(repeat_style.get("bg_color", "#FFFFFF")))
                    )

                # Style du détail de la fiche : indépendant du champ répété.
                if not (repeat_field and field == repeat_field):
                    detail_style = dict(
                        (self.advanced_style or {})
                        .get("typography", {})
                        .get("detail", {}) or {}
                    )
                    detail_font = QFont()
                    detail_font.setFamily(
                        str(detail_style.get("font_family") or "Calibri")
                    )
                    detail_font.setPointSize(int(detail_style.get("font_size", 10)))
                    detail_font.setBold(bool(detail_style.get("bold", False)))
                    detail_font.setItalic(bool(detail_style.get("italic", False)))
                    detail_font.setUnderline(bool(detail_style.get("underline", False)))
                    item.setFont(detail_font)

                    item.setForeground(
                        QColor(str(detail_style.get("text_color", "#111111")))
                    )
                    item.setBackground(
                        QColor(str(detail_style.get("bg_color", "#FFFFFF")))
                    )

                    detail_align = str(
                        self.detail_column_alignments.get(
                            field,
                            detail_style.get("align", "left"),
                        )
                    )
                    if detail_align == "center":
                        item.setTextAlignment(int(Qt.AlignHCenter | Qt.AlignVCenter))
                    elif detail_align == "right":
                        item.setTextAlignment(int(Qt.AlignRight | Qt.AlignVCenter))
                    else:
                        item.setTextAlignment(int(Qt.AlignLeft | Qt.AlignVCenter))

                if self.detail_graphic:
                    fmt = dict((self.detail_graphic.get("detail_field_styles") or {}).get(field) or {})
                    font = item.font()
                    font.setFamily(str(fmt.get("font_family") or "Arial"))
                    font.setPointSize(int(fmt.get("font_size") or 9))
                    font.setBold(bool(fmt.get("bold", False)))
                    font.setItalic(bool(fmt.get("italic", False)))
                    item.setFont(font)
                    item.setForeground(QColor(str(fmt.get("text_color") or "#111111")))
                    alignment = str(fmt.get("align") or "left")
                    item.setTextAlignment(int((Qt.AlignHCenter if alignment == "center" else
                                              Qt.AlignRight if alignment == "right" else Qt.AlignLeft)
                                              | Qt.AlignVCenter))
                self.table.setItem(row, col, item)
                # Les rôles natifs de QTableWidgetItem portent la police et la
                # couleur. Éviter un QLabel par cellule accélère le tri des
                # centaines de fiches sans changer le format choisi.

        def walk(subset, level):
            if level >= len(self.groupings):
                records = list(subset)
                if self.detail_graphic and self.detail_sort_field:
                    field = self.detail_sort_field
                    def detail_key(record):
                        value = record.get(field, "")
                        text = str(value or "").strip()
                        # Nombres purs triés numériquement, le reste alphabétiquement.
                        try:
                            number = float(text.replace(",", "."))
                            return (0, number)
                        except Exception:
                            return (1, text.casefold())
                    records.sort(key=detail_key, reverse=bool(self.detail_sort_desc))
                else:
                    records = self.owner._sorted_records_for_grouped_detail(records, self.fields)
                for record in records:
                    add_record(record)
                return
            field = self.groupings[level]
            groups = self.owner._group_records_for_detail(subset, field)
            keys = self.owner._sorted_detail_group_keys(list(groups), field)
            if (
                self.group_sort_level is not None
                and level == self.group_sort_level
                and level < len(self.group_sort_desc)
                and self.group_sort_desc[level]
            ):
                keys = list(reversed(keys))

            for value in keys:
                entries = groups[value]
                add_group_header(level, value, entries)
                walk(entries, level + 1)

        # Les libellés de colonnes sont portés uniquement par le véritable
        # QHeaderView interactif. Les marques suivent immédiatement cet en-tête.
        # 1.0.299 — Les marques sous les libellés de colonnes appartiennent
        # à l'en-tête, et non à un groupe maître. Elles doivent être insérées
        # même lorsqu'aucun regroupement n'est défini.
        if self.detail_graphic:
            mark = (self.detail_graphic.get("advanced_style") or {}).get("summary_layout_marks", {}).get("after_detail_labels")
            marks = mark if isinstance(mark, list) else ([mark] if mark else [])
            for data in marks:
                if not isinstance(data, dict) or data.get("kind") not in {"space", "line"}:
                    continue
                kind = str(data["kind"])
                size = float(data.get("size") or (12 if kind == "space" else 1))
                color = str(data.get("color") or "#000000")
                extra_row = self.table.rowCount()
                self.table.insertRow(extra_row)
                if self.table.columnCount() > 1:
                    self.table.setSpan(extra_row, 0, 1, self.table.columnCount())
                # Les tailles de la construction sont en points ; la grille Qt
                # utilise des pixels. Convertir avec le DPI réel du tableau.
                height = size * float(self.table.logicalDpiY() or 96) / 72.0
                self.table.setRowHeight(extra_row, max(2, round(height)) if kind == "space" else max(3, round(height + 2)))
                blank = QTableWidgetItem("")
                blank.setFlags(Qt.ItemFlag.NoItemFlags)
                self.table.setItem(extra_row, 0, blank)
                if kind == "line":
                    line = QFrame()
                    line.setStyleSheet(f"QFrame {{ border:0; border-top:{max(0.5,size):g}pt solid {color}; background:#FFFFFF; }}")
                    self.table.setCellWidget(extra_row, 0, line)
                self._detail_after_label_marks[extra_row] = (kind, size, color)

        walk(self.records, 0)

    def _detail_header_clicked(self, logical_index):
        """Trie les fiches dans chaque groupe sans déplacer les lignes de structure."""
        if not self.detail_graphic or logical_index < 0 or logical_index >= len(self.fields):
            return
        field = self.fields[logical_index]
        if self.detail_sort_field == field:
            self.detail_sort_desc = not self.detail_sort_desc
        else:
            self.detail_sort_field = field
            self.detail_sort_desc = False
        order = Qt.SortOrder.DescendingOrder if self.detail_sort_desc else Qt.SortOrder.AscendingOrder
        self.table.horizontalHeader().setSortIndicator(logical_index, order)
        state = self._layout_state()
        self._build_grouped_rows()
        self.layout_state = state
        self._apply_saved_layout()
        self._persist_preview_state()

    def _change_group_sort_level(self, index):
        if index < 0 or index >= len(self.groupings):
            return
        self.group_sort_level = index
        self._update_group_sort_button()
        self._rebuild_after_group_sort()

    def _toggle_group_sort_direction(self):
        if self.group_sort_level is None:
            return
        level = self.group_sort_level
        self.group_sort_desc[level] = not self.group_sort_desc[level]
        self._update_group_sort_button()
        self._rebuild_after_group_sort()

    def _update_group_sort_button(self):
        if self.group_sort_level is None:
            return
        desc = self.group_sort_desc[self.group_sort_level]
        self.group_sort_direction.setText(
            "▼ " + tr("Décroissant", self.language) if desc else "▲ " + tr("Croissant", self.language)
        )

    def _rebuild_after_group_sort(self):
        # Conserver ordre/largeurs des colonnes de détail pendant le tri des groupes.
        state = self._layout_state()
        self._build_grouped_rows()
        self.layout_state = state
        self._apply_saved_layout()

    def _apply_saved_layout(self):
        header = self.table.horizontalHeader()
        order = self.layout_state.get("column_order", [])
        widths = self.layout_state.get("column_widths", {})
        for target, field in enumerate(order):
            if field not in self.fields:
                continue
            logical = self.fields.index(field)
            current = header.visualIndex(logical)
            if current != target:
                header.moveSection(current, target)
        if self.detail_graphic:
            # 1.0.339.10 : les dimensions enregistrées dans l'aperçu
            # prévalent sur les dimensions initiales du constructeur.
            # Utiliser le constructeur uniquement pour les champs sans
            # largeur sauvegardée (nouveaux modèles / nouveaux champs).
            explicit = dict(self.detail_graphic.get("detail_column_widths") or {})
            widths = {field: max(28, min(480, int(
                widths.get(field) or explicit.get(field) or 130)))
                for field in self.fields}
        for field, width in widths.items():
            if field in self.fields:
                header.resizeSection(self.fields.index(field), int(width))

    def _layout_state(self):
        header = self.table.horizontalHeader()
        return {
            "column_order": [
                self.fields[header.logicalIndex(v)]
                for v in range(header.count())
            ],
            "column_widths": {
                field: header.sectionSize(self.fields.index(field))
                for field in self.fields
            },
            "group_sort_level": self.group_sort_level,
            "group_sort_desc": list(self.group_sort_desc),
            "detail_sort_field": self.detail_sort_field,
            "detail_sort_desc": bool(self.detail_sort_desc),
        }

    def _persist_preview_state(self):
        """Recopie l'état interactif de l'aperçu vers le constructeur."""
        page = getattr(self, "builder_page", None)
        if page is not None and hasattr(self, "table"):
            try:
                page._detail_preview_layout_state = self._layout_state()
            except Exception:
                pass

    def done(self, result):
        # QDialog.accept()/reject() passent par done(), contrairement à
        # closeEvent qui n'est pas garanti lors de Retour / Modifier.
        self._persist_preview_state()
        super().done(result)

    def closeEvent(self, event):
        self._persist_preview_state()
        super().closeEvent(event)

    def _open_record_from_number(self, row, column):
        record_id = self._record_row_ids.get(row)
        if record_id is None:
            return
        field = self.fields[column] if 0 <= column < len(self.fields) else ""
        if field != "record_number":
            return
        parent = self.owner.main_window
        callback = getattr(parent, "open_record_from_table", None) or getattr(parent, "open_record_from_search", None)
        if callback is None:
            return
        self.hide()
        callback(int(record_id))
        record_window = getattr(parent, "record_window", None)
        bring_front = getattr(parent, "_bring_window_to_front", None)
        if record_window is not None and callable(bring_front):
            QTimer.singleShot(0, lambda: bring_front(record_window))
            QTimer.singleShot(120, lambda: bring_front(record_window))
        if record_window is not None:
            try:
                record_window.installEventFilter(self)
            except Exception:
                pass

    def eventFilter(self, watched, event):
        parent = self.owner.main_window
        record_window = getattr(parent, "record_window", None)
        if watched is record_window and event.type() in (QEvent.Type.Hide, QEvent.Type.Close):
            QTimer.singleShot(0, self._return_from_record)
        return super().eventFilter(watched, event)

    def _detail_is_total_cost_field(self, field):
        """Reconnaît Coût total par son rôle/sa définition, pas seulement par sa clé interne."""
        key = str(field or "")
        if key in {"total_cost", "cost_total"}:
            return True
        label = str(self.owner.labels.get(key, key) or key).strip().casefold()
        label = unicodedata.normalize("NFKD", label)
        label = "".join(ch for ch in label if not unicodedata.combining(ch))
        label = re.sub(r"[^a-z0-9]+", " ", label).strip()
        if label in {"cout total", "total cost"}:
            return True
        definition = dict(getattr(self.owner, "_custom_field_defs", {}).get(key) or {})
        formula = str(definition.get("calculation_formula") or "").casefold()
        # Les collections historiques peuvent avoir une clé libre pour Coût total.
        # Sa formule multiplicative prix × quantité permet de retrouver son rôle.
        if str(definition.get("field_type") or "").strip().casefold() in {"calculated", "calcule", "calculé"}:
            if ("price" in formula or "prix" in formula) and any(tok in formula for tok in ("box", "piece", "boite", "nombre", "qty", "quant")):
                return True
        return False

    def _detail_total_cost_text(self, record, field):
        value = self.owner._summary_numeric_value(record, str(field))
        text = f"{float(value or 0):.2f}"
        return text if str(self.language or "fr").lower().startswith("en") else text.replace(".", ",")

    def _return_from_record(self):
        self.records = list(self.owner._records_for_source(self.source_name))
        self._build_grouped_rows()
        self._apply_saved_layout()
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _save_report(self):
        if hasattr(self, "preview_zebra_checkbox"):
            _zebra = bool(self.preview_zebra_checkbox.isChecked())
            self.advanced_style["preview_zebra_rows"] = _zebra
            page = getattr(self, "builder_page", None)
            if page is not None:
                page.preview_zebra_rows = _zebra
        if hasattr(self, "preview_header_gray_checkbox"):
            _header_gray = bool(self.preview_header_gray_checkbox.isChecked())
            self.advanced_style["preview_gray_column_headers"] = _header_gray
            page = getattr(self, "builder_page", None)
            if page is not None:
                page.preview_gray_column_headers = _header_gray
        name = self.owner.save_report_definition(
            kind="detail", title=self.report_title, source_name=self.source_name,
            landscape=self.landscape, fields=list(self.fields),
            layout_state=self._layout_state(), existing_name=self.saved_name,
            builder_page=getattr(self, "builder_page", None),
            detail_groupings=list(self.groupings),
            atelier_style=dict(self.atelier_style),
        )
        if name:
            self.saved_name = name
            self.setWindowTitle(f"{tr('Aperçu groupé', self.language)} — {self.report_title} — {name}")
            if hasattr(self, "preview_heading"):
                self.preview_heading.setText(f"{tr('État détaillé', self.language)} : {name}")
            self.owner._sync_builder_after_preview_save(
                getattr(self, "builder_page", None), "detail", name
            )

    def _sync_preview_print_page_count(self):
        """Calcule le total avec le moteur d'impression, sans ouvrir le dialogue."""
        if not self.detail_graphic or not bool(self.page_chrome.get("show_page_numbers", False)):
            return
        self._pagination_probe = True
        self._pagination_probe_result = None
        try:
            self._print()
        finally:
            self._pagination_probe = False
        result = getattr(self, "_pagination_probe_result", None)
        if result:
            if isinstance(result, tuple):
                total, break_rows = result
            else:
                total, break_rows = result, []
            self.table.set_preview_pagination(
                True,
                str(self.page_chrome.get("page_number_format") or "page_x_y"),
                str(self.page_chrome.get("footer_align") or "right"),
                total_pages=total,
                break_rows=break_rows,
            )

    def _print_preview_table_direct(self):
        """Impression compacte du QTableWidget groupé, sans altérer l'État riche.

        Les lignes sont dessinées à partir des cellules réellement visibles
        (ordre des colonnes, valeurs, polices, fonds et regroupements). Les
        en-têtes sont répétés sur chaque feuille ; une ligne n'est pas coupée.
        """
        from PySide6.QtCore import QRectF
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setDocName(str(self.report_title or "État détaillé") + " - Tableau")
        printer.setPageOrientation(
            QPageLayout.Orientation.Landscape if self.landscape
            else QPageLayout.Orientation.Portrait
        )
        try:
            layout = printer.pageLayout()
            layout.setMargins(QMarginsF(8.0, 8.0, 8.0, 8.0))
            printer.setPageLayout(layout)
        except Exception:
            pass
        dialog = QPrintDialog(printer, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        table = self.table
        header = table.horizontalHeader()
        columns = [header.logicalIndex(i) for i in range(header.count())
                   if not table.isColumnHidden(header.logicalIndex(i))]
        if not columns:
            return
        natural_widths = [max(1, table.columnWidth(c)) for c in columns]
        natural_total = max(1, sum(natural_widths))
        # Capturer TOUS les bandeaux avant le premier saut de page.
        # Ne pas dépendre de la résolution différée des cellWidget Qt
        # lorsque l'impression parcourt des lignes hors de l'écran.
        group_banners = {}
        for group_row in range(table.rowCount()):
            item = table.item(group_row, 0)
            # Identifier les bandeaux par la donnée attachée à la cellule.
            # La correspondance reste correcte même si Qt décale les lignes.
            group_html = item.data(Qt.ItemDataRole.UserRole) if item else None
            if isinstance(group_html, str) and group_html.strip():
                widget = table.cellWidget(group_row, 0)
                group_font = QFont(widget.font()) if isinstance(widget, QLabel) else QFont(table.font())
                group_banners[group_row] = (group_html, group_font)
        painter = QPainter(printer)
        if not painter.isActive():
            return
        try:
            rect = printer.pageRect(QPrinter.Unit.DevicePixel)
            # Coordonnées logiques de l'écran converties uniformément vers
            # les pixels de l'imprimante : aucun lien avec le moteur riche.
            margin = max(1.0, printer.resolution() * 2.0 / 25.4)
            available_width = max(1.0, float(rect.width()) - 2 * margin)
            scale = min(available_width / natural_total,
                        max(0.1, printer.resolution() / 96.0))
            left = float(rect.x()) + margin
            top = float(rect.y()) + margin
            bottom = float(rect.y() + rect.height()) - margin
            header_h = max(22.0, float(header.height())) * scale
            base_font = table.font()
            def draw_header(y):
                x = left
                for c, w in zip(columns, natural_widths):
                    cw = w * scale
                    r = QRectF(x, y, cw, header_h)
                    painter.fillRect(r, QColor("#E9ECEF"))
                    painter.setPen(QColor("#C7CCD1"))
                    painter.drawRect(r)
                    painter.setPen(QColor("#202020"))
                    painter.setFont(base_font)
                    painter.drawText(r.adjusted(4 * scale, 0, -3 * scale, 0),
                                     int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                                     str(table.horizontalHeaderItem(c).text()
                                         if table.horizontalHeaderItem(c) else self.fields[c]))
                    x += cw
                return y + header_h
            y = draw_header(top)
            # L'aperçu groupé peut comporter, avant le premier groupe,
            # des lignes techniques sans texte (fond gris sur la colonne 1).
            # Ne pas les imprimer dans le mode tableau direct.
            group_rows = set(group_banners)
            first_group_row = min(group_rows) if group_rows else 0
            for row in range(table.rowCount()):
                if table.isRowHidden(row):
                    continue
                if row < first_group_row:
                    has_text = any(
                        bool(table.item(row, c) and table.item(row, c).text().strip())
                        or bool(isinstance(table.cellWidget(row, c), QLabel)
                                and table.cellWidget(row, c).text().strip())
                        for c in range(table.columnCount())
                    )
                    if not has_text:
                        continue
                # Les interlignes structurels doivent conserver leur hauteur,
                # mais ne jamais produire de fonds gris parasites dans le PDF.
                is_blank_spacer = (row not in group_banners and all(
                    not (table.item(row, c) and table.item(row, c).text().strip())
                    for c in columns
                ))
                rh = max(18.0, float(table.rowHeight(row))) * scale
                if y + rh > bottom and y > top + header_h:
                    printer.newPage()
                    y = draw_header(top)
                # Les lignes de regroupement sont des cellules fusionnées
                # contenant un QLabel riche, pas des QTableWidgetItem textuels.
                # Les dessiner sur la largeur entière avant les cellules ordinaires.
                if row in group_banners:
                    group_html, group_font = group_banners[row]
                    group_item = table.item(row, 0)
                    group_rect = QRectF(left, y, natural_total * scale, rh)
                    if group_item is not None:
                        bg = group_item.background()
                        if bg.style() != Qt.BrushStyle.NoBrush:
                            painter.fillRect(group_rect, bg)
                    if group_html:
                        painter.save()
                        painter.setClipRect(group_rect)
                        painter.translate(left + 3.0 * scale, y)
                        painter.scale(scale, scale)
                        group_doc = QTextDocument()
                        group_doc.setDocumentMargin(0)
                        group_doc.setDefaultFont(group_font)
                        group_doc.setHtml(group_html)
                        group_doc.setTextWidth(max(1.0, natural_total - 6.0))
                        group_doc.drawContents(painter, QRectF(
                            0.0, 0.0, max(1.0, natural_total - 6.0),
                            max(float(table.rowHeight(row)), group_doc.size().height())
                        ))
                        painter.restore()
                    y += rh
                    continue
                if is_blank_spacer:
                    y += rh
                    continue
                x = left
                for c, w in zip(columns, natural_widths):
                    cw = w * scale
                    cell = QRectF(x, y, cw, rh)
                    item = table.item(row, c)
                    if item is not None:
                        bg = item.background()
                        if bg.style() != Qt.BrushStyle.NoBrush:
                            painter.fillRect(cell, bg)
                        elif row % 2 and bool(self.advanced_style.get("preview_zebra_rows", False)):
                            painter.fillRect(cell, QColor("#F2F2F2"))
                        painter.save()
                        font = item.font()
                        if not font.family():
                            font = base_font
                        painter.setFont(font)
                        fg = item.foreground()
                        # QPainter.setPen accepte une QColor/QPen, pas une QBrush.
                        # Conserver la couleur de texte de la cellule.
                        painter.setPen(fg.color() if fg.style() != Qt.BrushStyle.NoBrush
                                       else QColor("#202020"))
                        alignment = int(item.textAlignment())
                        if not alignment:
                            alignment = int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                        # La cellule reste dans sa largeur ; le texte n'empiète
                        # jamais sur une autre colonne.
                        painter.setClipRect(cell.adjusted(1, 0, -1, 0))
                        painter.drawText(cell.adjusted(3 * scale, 0, -3 * scale, 0),
                                         alignment, item.text())
                        painter.restore()
                    x += cw
                y += rh
        finally:
            painter.end()

    def _print(self):
        # 1.0.138 — figer explicitement dans le style d’impression l’état de
        # la case de l’Aperçu. L’impression ne possède aucune commande zebra.
        if hasattr(self, "preview_zebra_checkbox"):
            self.advanced_style["preview_zebra_rows"] = bool(self.preview_zebra_checkbox.isChecked())
        if hasattr(self, "preview_header_gray_checkbox"):
            self.advanced_style["preview_gray_column_headers"] = bool(self.preview_header_gray_checkbox.isChecked())
        print_font = str(
            self.advanced_style.get("print_font")
            or self.page_chrome.get("print_font")
            or "Arial"
        )
        """Imprime fidèlement le tableau groupé actuellement visible."""
        header = self.table.horizontalHeader()
        logical_columns, visual_widths, table_width_percent, column_percentages = (
            _print_table_geometry(self.table, self.landscape)
        )
        colgroup = "<colgroup>" + "".join(
            f"<col width='{pct:.4f}%' style='width:{pct:.4f}%;'>"
            for pct in column_percentages
        ) + "</colgroup>"

        # En-têtes de colonnes : mêmes couleurs et typographie que l'écran.
        hs = dict(self.advanced_style or {})
        h_family = str(hs.get("column_header_font_family") or "Calibri")
        h_text = str(hs.get("column_header_text_color") or "#111111")
        h_bg = str(hs.get("column_header_bg_color") or ("#FFFFFF" if self.detail_graphic else "#DDE8E2"))
        h_size = int(hs.get("column_header_font_size", 10))
        h_weight = "700" if bool(hs.get("column_header_bold", True)) else "400"
        h_style = "italic" if bool(hs.get("column_header_italic", False)) else "normal"
        h_decoration = (
            "underline"
            if bool(hs.get("column_header_underline", False))
            else "none"
        )

        header_cells = []
        for logical in logical_columns:
            field = self.fields[logical]
            if self.detail_graphic:
                labels = dict(self.detail_graphic.get("detail_column_labels") or {})
                fmt = dict((self.detail_graphic.get("detail_label_styles") or {}).get(field) or {})
                label = str(labels.get(field) or self.owner.labels.get(field, field))
                family = str(fmt.get("font_family") or h_family)
                size = int(fmt.get("font_size") or h_size)
                color = str(fmt.get("text_color") or h_text)
                background = ("#F2F2F2" if bool(self.advanced_style.get("preview_gray_column_headers", False))
                              else str(fmt.get("background_color") or "#FFFFFF"))
                weight = "700" if bool(fmt.get("bold", False)) else "400"
                style = "italic" if bool(fmt.get("italic", False)) else "normal"
                decoration = "underline" if bool(fmt.get("underline", False)) else "none"
                align = str(fmt.get("align") or "left")
            else:
                label = self.owner.labels.get(field, field)
                family, size, color, background = h_family, h_size, h_text, h_bg
                weight, style, decoration, align = h_weight, h_style, h_decoration, "center"
            header_cells.append(
                "<th style='font-family:" + _escape(family) +
                ";font-size:" + str(size) + "pt;color:" + _escape(color) +
                ";background:" + _escape(background) +
                ";font-weight:" + weight + ";font-style:" + style +
                ";text-decoration:" + decoration + ";text-align:" + align +
                ";padding:3px 2px;'>" + _escape(label) + "</th>"
            )

        body_size = int(self.page_chrome.get("body_font_size", 10))
        print_row_pad = "0px 2px" if body_size <= 8 else "1px 2px"
        print_line_height = "1.0"
        print_font = str(self.page_chrome.get("print_font_family") or "Arial")
        border_mode = str(self.advanced_style.get("detail_borders") or "none")
        detail_trait = _trait_print_width(
            self.advanced_style.get("detail_trait") or "none"
        )
        header_trait = _trait_print_width(
            self.advanced_style.get("header_trait") or "2pt"
        )
        group_trait = _trait_print_width(
            self.advanced_style.get("group_trait") or "1pt"
        )

        if border_mode == "grid":
            detail_border_css = "border:0.25pt solid #000000;"
        elif border_mode == "horizontal":
            detail_border_css = "border-bottom:0.25pt solid #000000;"
        elif detail_trait == "0.25pt":
            detail_border_css = "border-bottom:0.25pt solid #000000;"
        elif detail_trait != "0":
            detail_border_css = f"border-bottom:{detail_trait} solid #000000;"
        else:
            detail_border_css = "border:0;"

        # Corps : reprendre exactement l'ordre de lignes affiché après tri des groupes.
        def separator_row(width, colspan):
            # width est une valeur MM3 déjà exprimée sous forme de texte :
            # "0", "0.25pt", "1pt", "2pt".
            raw = str(width or "0").strip().lower()
            if raw in {"", "0", "0pt", "0px", "none", "0.25pt", "0.5pt"}:
                return ""

            # Les séparateurs épais restent des bandes fiables pour QTextDocument.
            # Le Filet, lui, est rendu comme une vraie bordure de cellule.
            height_map = {
                "1pt": "2",
                "2pt": "5",
            }
            h = height_map.get(raw, "1")
            span = max(1, int(colspan))

            return (
                f'<tr><td colspan="{span}" '
                f'bgcolor="#000000" height="{h}" '
                f'style="height:{h}px; min-height:{h}px; max-height:{h}px; '
                f'padding:0; margin:0; font-size:1px; line-height:1px; '
                f'border:0; background:#000000; background-color:#000000;">'
                f'&#9608;</td></tr>'
            )
        detail_separator_html = ("" if self.detail_graphic else
                                 separator_row(detail_trait, len(logical_columns)))

        layout_marks = dict((self.detail_graphic.get("advanced_style") or self.advanced_style).get("summary_layout_marks") or {}) if self.detail_graphic else dict(self.advanced_style.get("summary_layout_marks") or {})
        detail_mark_rows = []
        detail_data_rows = []
        outer_marks = []
        def print_mark_items(position):
            raw = layout_marks.get(position)
            values = raw if isinstance(raw, list) else [raw]
            return [(str(item.get("kind")), float(item.get("size") or 0.5),
                     str(item.get("color") or "#000000")) for item in values
                    if isinstance(item, dict) and item.get("kind") in {"line", "space"}]

        def outer_mark_html(position):
            parts = []
            for kind, size, color in print_mark_items(position):
                if kind == "space":
                    parts.append(f"<div style='height:{max(1,size):g}pt;font-size:1pt;'>&nbsp;</div>")
                else:
                    outer_marks.append((size, color))
                    parts.append("<table width='100%' cellspacing='0' cellpadding='0' "
                                 "style='width:100%;border:0;'><tr><td "
                                 f"style='border-bottom:{size:g}pt solid {_escape(color)};"
                                 "font-size:1pt;line-height:1pt;padding:0;'>&nbsp;</td></tr></table>")
            return "".join(parts)

        marks_by_row = ({**getattr(self, "_detail_after_label_marks", {}),
                         **getattr(self, "_detail_between_master_marks", {})}
                        if self.detail_graphic else {})
        html_rows = []
        # 1.0.153 — correspondance exacte entre chaque ligne HTML imprimée et
        # sa ligne d'origine dans l'Aperçu. Les anciennes conversions tr-1
        # devenaient fausses dès qu'un filet, un interligne ou une ligne
        # structurelle était présent et pouvaient faire passer la marge de
        # pagination au travers d'une vraie ligne de données.
        print_screen_rows = []
        _print_data_index = 0
        _print_zebra = bool(self.advanced_style.get("preview_zebra_rows", False))
        for row in range(self.table.rowCount()):
            if row == getattr(self, "_detail_pagination_spacer_row", -1):
                continue
            if row in marks_by_row:
                kind, size, color = marks_by_row[row]
                detail_mark_rows.append((len(html_rows), kind, size, color))
                height = max(1, round(size * float(self.table.logicalDpiY() or 96) / 72.0)) if kind == "space" else 1
                html_rows.append(f"<tr><td colspan='{max(1,len(logical_columns))}' "
                                 f"style='height:{size:g}pt;min-height:{size:g}pt;padding:0;font-size:1px;line-height:1px;'>&nbsp;</td></tr>")
                print_screen_rows.append(row)
                continue
            span = self.table.columnSpan(row, 0)
            widget = self.table.cellWidget(row, 0)

            # Bandeau de regroupement.
            if (isinstance(widget, QLabel) and
                    (row in getattr(self, "_detail_group_rows", set()) if self.detail_graphic else span > 1)):
                source_item = self.table.item(row, 0)
                bg = "#FFFFFF"
                if source_item is not None and not self.detail_graphic:
                    bg = source_item.background().color().name()

                text = widget.text()
                if self.detail_graphic:
                    # Non-breaking spaces otherwise force QTextDocument to grow
                    # past the printable A4 width when six totals are shown.
                    # 1.0.128 — chaque total est indivisible (ex. « 3 catégorie »),
                    # mais la ligne peut se couper proprement ENTRE deux totaux.
                    text = text.replace("&nbsp;&nbsp;—&nbsp;&nbsp;", " — ")
                    chunks = text.split(" — ")
                    chunks = ["<span style='white-space:nowrap;'>" + c + "</span>" for c in chunks]
                    # 1.0.153 — aucune coupure forcée après quatre éléments.
                    # Qt décide du retour à la ligne uniquement selon la largeur
                    # réellement disponible sur la feuille imprimée.
                    text = " — ".join(chunks)
                font = widget.font()
                family = font.family() or "Calibri"
                size = max(6, font.pointSize())
                weight = "700" if font.bold() else "400"
                italic = "italic" if font.italic() else "normal"
                underline = "underline" if font.underline() else "none"

                alignment = widget.alignment()
                if alignment & Qt.AlignHCenter:
                    align = "center"
                elif alignment & Qt.AlignRight:
                    align = "right"
                else:
                    align = "left"

                if group_trait != "0" and not self.detail_graphic:
                    html_rows.append(separator_row(group_trait, len(logical_columns)))
                    print_screen_rows.append(row)
                html_rows.append(
                    "<tr class='group-row'><td colspan='"
                    + str(max(1, len(logical_columns)))
                    + "' style='"
                    + f"background:{bg};font-family:{_escape(family)};font-size:{size}pt;"
                    + f"font-weight:{weight};font-style:{italic};text-decoration:{underline};"
                    + f"text-align:{align};padding:{'4px 0px' if self.detail_graphic else '4px 6px'};"
                    + ("white-space:normal;overflow:visible;page-break-after:avoid;'>" if self.detail_graphic else
                       "white-space:nowrap;overflow:hidden;page-break-after:avoid;'>")
                    + text
                    + "</td></tr>"
                )
                print_screen_rows.append(row)
                continue

            if self.detail_graphic and row in getattr(self, "_detail_label_rows", set()):
                label_cells = []
                for logical in logical_columns:
                    item = self.table.item(row, logical)
                    field = self.fields[logical]
                    fmt = dict((self.detail_graphic.get("detail_label_styles") or {}).get(field) or {})
                    family = _escape(str(fmt.get("font_family") or "Arial"))
                    size = int(fmt.get("font_size") or 9)
                    color = _escape(str(fmt.get("text_color") or "#111111"))
                    background = _escape("#F2F2F2" if bool(self.advanced_style.get("preview_gray_column_headers", False)) else str(fmt.get("background_color") or "#FFFFFF"))
                    align = str(fmt.get("align") or "left")
                    label = _escape(str(item.data(Qt.ItemDataRole.UserRole + 43) or item.text()) if item else "")
                    content = ("<font face='" + family + "' color='" + color + "'>" +
                               ("<b>" if fmt.get("bold") else "") +
                               ("<i>" if fmt.get("italic") else "") + label +
                               ("</i>" if fmt.get("italic") else "") +
                               ("</b>" if fmt.get("bold") else "") + "</font>")
                    label_cells.append("<td align='" + align + "' style='padding:3px 2px;" +
                                       "font-family:" + family + ";font-size:" + str(size) +
                                       "pt;color:" + color + ";background:" + background + ";'>" +
                                       "<span style='font-size:" + str(size) + "pt;'>" + content +
                                       "</span></td>")
                html_rows.append("<tr class='detail-label-row'>" + "".join(label_cells) + "</tr>")
                print_screen_rows.append(row)
                continue

            # Ligne d'espacement.
            empty = True
            for visual_index, logical in enumerate(logical_columns):
                item = self.table.item(row, logical)
                if item is not None and str(item.data(Qt.ItemDataRole.UserRole + 42) or item.text()).strip():
                    empty = False
                    break
            if empty:
                html_rows.append(
                    "<tr class='spacer'><td colspan='"
                    + str(max(1, len(logical_columns)))
                    + "' style='background:#FFFFFF;background-color:#FFFFFF;'>&nbsp;</td></tr>"
                )
                print_screen_rows.append(row)
                continue

            # Ligne de fiche : reprendre exactement la typographie de l'écran.
            cells = []
            for visual_index, logical in enumerate(logical_columns):
                item = self.table.item(row, logical)
                shown = str(item.data(Qt.ItemDataRole.UserRole + 42) or item.text()) if item is not None else ""
                field = self.fields[logical]

                if item is not None:
                    font = item.font()
                    family = font.family() or print_font
                    size = max(6, font.pointSize())
                    bold = font.bold()
                    italic_flag = font.italic()
                    underline_flag = font.underline()
                    text_color = item.foreground().color().name()
                    bg_color = item.background().color().name()
                else:
                    family = print_font
                    size = body_size
                    bold = False
                    italic_flag = False
                    underline_flag = False
                    text_color = "#111111"
                    bg_color = "#FFFFFF"

                if self.detail_graphic:
                    fmt = dict((self.detail_graphic.get("detail_field_styles") or {}).get(field) or {})
                    family = str(fmt.get("font_family") or family)
                    size = int(fmt.get("font_size") or size)
                    bold = bool(fmt.get("bold", False))
                    italic_flag = bool(fmt.get("italic", False))
                    text_color = str(fmt.get("text_color") or "#111111")

                align_value = (
                    item.textAlignment() if item is not None else int(Qt.AlignLeft)
                )
                if align_value & int(Qt.AlignHCenter):
                    align = "center"
                elif align_value & int(Qt.AlignRight):
                    align = "right"
                else:
                    align = "left"

                css_class = "nowrap"
                # Même largeur visible que le colgroup : les caractères
                # hors marge ne doivent pas influer sur la justification.
                dpi = float(self.table.logicalDpiX() or 96.0)
                # Identique à _print_table_geometry : A4 moins
                # 5 mm de marge à gauche et à droite.
                page_px = (((297.0 if self.landscape else 210.0) - 10.0) / 25.4) * dpi
                preceding_px = sum(visual_widths[:visual_index])
                visible_px = max(0.0, min(float(visual_widths[visual_index]),
                                           page_px - preceding_px))
                # 1.0.339.8 : le document multipage réduit les colonnes
                # à la largeur imprimable A4. Tronquer selon cette largeur
                # réelle, et non selon les seuls pixels de l'aperçu écran.
                # Le correctif est réservé aux états détaillés anglais.
                english_detail = (bool(self.detail_graphic) and
                                  str(self.language).lower().startswith("en"))
                if english_detail:
                    printable_width_pt = ((297.0 if self.landscape else 210.0)
                                          - 10.0) * 72.0 / 25.4
                    native_available_pt = max(1.0, printable_width_pt - 30.0)
                    all_widths_pt = [float(w) * 72.0 / dpi for w in visual_widths]
                    native_scale = min(1.0, native_available_pt /
                                       max(1.0, sum(all_widths_pt)))
                    # Réserve pour la largeur intrinsèque des glyphes Qt,
                    # plus un petit blanc séparateur entre deux colonnes.
                    clipped_width_px = min(visible_px,
                                           float(visual_widths[visual_index]) * native_scale * 0.88)
                    clipped = _clip_print_value(
                        shown, clipped_width_px, family, size,
                        bold, italic_flag, 10
                    )
                else:
                    clipped = _clip_print_value(
                        shown, visible_px, family, size,
                        bold, italic_flag, 6
                    )
                weight = "700" if bold else "400"
                font_style = "italic" if italic_flag else "normal"
                decoration = "underline" if underline_flag else "none"
                # Comme dans l'impression du résumé, Qt conserve fidèlement
                # la taille lorsque le même style est porté par la cellule ET
                # par son texte. Un <font face> interne perdait le 7 pt choisi.
                size_px = max(1.0, float(size)) * (96.0 / 72.0)
                typography = (
                    f"font-family:'{_escape(family)}';font-size:{size_px:g}px;"
                    f"font-weight:{weight};font-style:{font_style};"
                    f"text-decoration:{decoration};color:{text_color};"
                )

                if self.detail_graphic and _print_zebra and (_print_data_index % 2 == 1):
                    bg_color = "#F2F2F2"

                cells.append(
                    f"<td class='{css_class}' style='text-align:{align};"
                    f"{typography}"
                    f"background:{bg_color};background-color:{bg_color};{detail_border_css}' bgcolor='{bg_color}'>"
                    f"<span style=\"{typography}\">{_escape(clipped)}</span></td>"
                )
            if self.detail_graphic:
                detail_data_rows.append(len(html_rows))
            html_rows.append("<tr class='detail-row'>" + "".join(cells) + "</tr>")
            print_screen_rows.append(row)
            if self.detail_graphic:
                _print_data_index += 1
            if detail_separator_html:
                html_rows.append(detail_separator_html)
                print_screen_rows.append(min(row + 1, max(0, self.table.rowCount() - 1)))

        # Conserver la table de correspondance pour le calcul des césures écran.
        self.owner._last_detail_print_screen_rows = list(print_screen_rows)

        # Titre général identique à l'aperçu écran.
        preview_name = self.saved_name or ""
        custom_title = str(self.advanced_style.get("header_title") or "").strip()
        page_title = str(self.page_chrome.get("title_text") or "").strip()
        heading = page_title or custom_title or (
            f"{tr('État détaillé', self.language)} : {preview_name}" if preview_name else tr("État détaillé", self.language)
        )
        if not bool(self.page_chrome.get("show_title", True)):
            heading = ""

        extras = []
        if bool(self.page_chrome.get("show_collection", False)):
            collection_name = str(
                getattr(self.owner, "collection", {}).get("name") or ""
            ).strip()
            if collection_name:
                extras.append(collection_name)
        if bool(self.page_chrome.get("show_print_date", False)):
            extras.append(QDate.currentDate().toString("dd/MM/yyyy"))
        if extras:
            heading = ((heading + " — ") if heading else "") + " — ".join(extras)

        title_size = int(self.page_chrome.get("title_font_size", 20))
        title_weight = (
            "700" if bool(self.page_chrome.get("title_bold", True)) else "400"
        )
        title_style = (
            "italic" if bool(self.page_chrome.get("title_italic", False))
            else "normal"
        )
        title_decoration = (
            "underline"
            if bool(self.page_chrome.get("title_underline", False))
            else "none"
        )
        title_align = str(self.page_chrome.get("title_align") or "left")
        title_color = str(
            self.page_chrome.get("title_text_color") or "#111111"
        )
        title_bg = str(self.page_chrome.get("title_bg_color") or "#FFFFFF")

        title_html = ""
        if heading:
            title_html = (
                f"<div style='font-size:{title_size}pt;"
                f"font-weight:{title_weight};font-style:{title_style};"
                f"text-decoration:{title_decoration};text-align:{title_align};"
                f"color:{title_color};background:{title_bg};"
                f"padding:5px 7px;margin-bottom:6px;'>"
                f"{_escape(heading)}</div>"
            )

        # Bandeau des compteurs : mêmes chiffres, tailles et couleurs.
        style = dict(self.atelier_style or {})
        boxes = sum(_number(rec.get("box_count")) for rec in self.records)
        species = self.owner._species_count(self.records)
        group_count = len(
            self.owner._group_records_for_detail(
                self.records, self.groupings[0]
            )
        ) if self.groupings else 0

        metric_parts = []
        metric_fields = []

        def add_metric(number,label,semantic,field=None):
            metric_fields.append(field)
            family=str(style.get(f"metric_{semantic}_font") or "Calibri")
            size=int(style.get(f"metric_{semantic}_size",10))
            color=str(style.get(f"metric_{semantic}_color") or "#8B3026")
            metric_settings = dict((self.detail_graphic or {}).get("summary_header_metrics") or {})
            band_bg = str((metric_settings.get("band_style") or {}).get("bg") or "")
            bg = (("transparent" if band_bg.upper() == "#F4F6F5" else (band_bg or "transparent"))
                  if self.detail_graphic else str(style.get(f"metric_{semantic}_bg") or "#F4F6F5"))
            weight="700" if bool(style.get(f"metric_{semantic}_bold",False)) else "400"
            italic="italic" if bool(style.get(f"metric_{semantic}_italic",False)) else "normal"
            underline="underline" if bool(style.get(f"metric_{semantic}_underline",False)) else "none"
            metric_parts.append(
                f"<span style='font-family:{_escape(family)};font-size:{size}pt;"
                f"font-weight:{weight};font-style:{italic};text-decoration:{underline};"
                f"color:{color};background:{bg};margin-right:18px;padding:1px 3px;'>"
                f"<font face='{_escape(family)}'>{_escape(number)} {_escape(label)}</font></span>"
            )

        if self.detail_graphic:
            metrics = dict(self.detail_graphic.get("summary_header_metrics") or {})
            _band_fields = list(metrics.get("selected_fields") or [])
            _band_positions = dict(metrics.get("metric_positions") or {})
            if _band_positions:
                _band_fields.sort(key=lambda f: int(_band_positions.get(str(f), 10**9)))
            for field in _band_fields:
                if field in self.owner.labels:
                    parts = self._graphic_metric(field, self.records).split(" ", 1)
                    add_metric(parts[0], parts[1] if len(parts) > 1 else "", "boxes", field)
            if metrics.get("records", False):
                add_metric(str(len(self.records)), tr("fiche(s)", self.owner.language), "records", "__records__")
        else:
            if style.get("show_groups", True) and self.groupings:
                group_label = self.owner._grouping_label(self.groupings[0]).lower()
                if group_count != 1 and not group_label.endswith("s"):
                    group_label += "s"
                add_metric(str(group_count),group_label,"groups")
            if style.get("show_boxes", True):
                add_metric(self.owner._fmt_number(boxes),tr("pièce(s)", self.owner.language),"boxes")
            if style.get("show_species", True):
                add_metric(str(species),"espèces","species")
            if style.get("show_records", True):
                add_metric(str(len(self.records)),tr("fiche(s)", self.owner.language),"records")

        metrics_html = (
            "<div style='padding:5px 7px;margin-bottom:8px;'>"
            + "".join(metric_parts)
            + "</div>"
            if metric_parts else ""
        )
        if self.detail_graphic and metric_parts:
            _hm = dict(self.detail_graphic.get("summary_header_metrics") or {})
            widths = dict(_hm.get("metric_widths") or {}); positions = dict(_hm.get("metric_positions") or {})
            if widths or positions:
                cells = []; cursor = 0
                ordered = list(zip(metric_fields, metric_parts))
                if positions: ordered.sort(key=lambda fp: int(positions.get(str(fp[0]), 10**9)))
                for field, part in ordered:
                    x = max(cursor, int(positions.get(str(field), cursor)))
                    if x > cursor: cells.append(f'<td width="{x-cursor}"></td>')
                    width = max(55, min(480, int(widths.get(str(field), 90))))
                    cells.append(f'<td width="{width}" style="border:0;padding:0;white-space:nowrap;">'
                                 + part.replace("margin-right:18px;", "") + '</td>')
                    cursor = x + width
                metrics_html = ('<table cellspacing="0" cellpadding="0" style="border:0;margin-bottom:8px;">'
                                '<tr>' + ''.join(cells) + '</tr></table>')

        # Pied de page identique au réglage Atelier.
        footer_parts = []
        footer_text = str(self.page_chrome.get("footer_text") or "").strip()
        if footer_text:
            footer_parts.append(footer_text)
        if bool(self.page_chrome.get("show_page_numbers", True)) and not self.detail_graphic:
            footer_parts.append("Page 1 / 1")

        footer_html = ""
        if footer_parts:
            footer_size = int(self.page_chrome.get("footer_font_size", 10))
            footer_weight = (
                "700"
                if bool(self.page_chrome.get("footer_bold", False))
                else "400"
            )
            footer_style = (
                "italic"
                if bool(self.page_chrome.get("footer_italic", False))
                else "normal"
            )
            footer_decoration = (
                "underline"
                if bool(self.page_chrome.get("footer_underline", False))
                else "none"
            )
            footer_align = str(self.page_chrome.get("footer_align") or "right")
            footer_color = str(
                self.page_chrome.get("footer_text_color") or "#4F5A55"
            )
            footer_bg = str(
                self.page_chrome.get("footer_bg_color") or "#FFFFFF"
            )
            footer_html = (
                f"<div style='font-size:{footer_size}pt;"
                f"font-weight:{footer_weight};font-style:{footer_style};"
                f"text-decoration:{footer_decoration};"
                f"text-align:{footer_align};color:{footer_color};"
                f"background:{footer_bg};border-top:1px solid #AAB5B0;"
                f"padding:5px 7px;margin-top:8px;'>"
                f"{_escape(' — '.join(footer_parts))}</div>"
            )

        if self.detail_graphic:
            footer_html = self._graphic_footer_metrics_html() + footer_html

        cell_box_css = (
            "border:0.25pt solid #000000;"
            if border_mode == "grid"
            else "border:0;"
        )

        if border_mode == "grid":
            detail_border_css = "border:0.25pt solid #000000;"
        elif border_mode == "horizontal":
            detail_border_css = "border-bottom:0.25pt solid #000000;"
        elif detail_trait != "0":
            detail_border_css = f"border-bottom:{detail_trait} solid #000000;"
        else:
            detail_border_css = "border:0;"


        html = f"""<html><head><meta charset="utf-8"><style>
        body {{
            font-family:"{print_font}",Arial,sans-serif;
            color:#222;
            font-size:{body_size}pt;
        }}
        table {{
            width:{table_width_percent:.4f}%;
            table-layout:fixed;
            border-collapse:collapse;
            page-break-inside:auto;
            font-size:{body_size}pt;
        }}
        .nowrap {{ white-space:nowrap; word-break:keep-all; }}
        .wrap {{ white-space:normal; word-break:normal; }}
        .col-number {{ width:5%; }}
        thead {{ display:table-header-group; }}
        tbody {{ display:table-row-group; }}
        tr.detail-row {{
            page-break-inside:avoid;
            page-break-after:auto;
        }}
        tr.group-row {{
            page-break-inside:avoid;
            page-break-after:avoid;
        }}
        tr.spacer td {{
            height:4px;
            border:0;
            background:#FFFFFF;
        }}
        th {{
            color:{h_text};
            background:{h_bg};
            font-family:"{h_family}";
            font-size:{h_size}pt;
            font-weight:{h_weight};
            font-style:{h_style};
            text-decoration:{h_decoration};
            padding:{'0px' if self.detail_graphic else '6px'};
            border:0;
            border:0;
        }}
        td {{
            
            padding:{'0px' if self.detail_graphic else print_row_pad};
            font-size:{body_size}pt;
            line-height:{print_line_height};
            vertical-align:top;
            white-space:nowrap;
            overflow:hidden;
        }}
        .mm3-separator td, .mm3-separator th {{
            padding:0 !important;
            margin:0 !important;
            border:0 !important;
            background:#000000 !important; background-color:#000000 !important;
        }}
        </style></head><body>
        {title_html}
        {outer_mark_html('after_title') if self.detail_graphic else ''}
        {metrics_html}
        {outer_mark_html('after_band') if self.detail_graphic else ''}
        <table width="{table_width_percent:.4f}%" style="width:{table_width_percent:.4f}%;">
          {colgroup}
          {"<thead><tr>" + "".join(header_cells) + "</tr></thead>" + ("" if self.detail_graphic else separator_row(header_trait, len(logical_columns)))}
          <tbody>{''.join(html_rows)}</tbody>
        </table>
        {outer_mark_html('before_footer_line') if self.detail_graphic else ''}
        {outer_mark_html('before_footer') if self.detail_graphic else ''}
        {footer_html}
        </body></html>"""

        self.owner._last_html=html
        self.owner._last_summary_column_widths = (
            (list(visual_widths), float(self.table.logicalDpiX() or 96))
            if self.detail_graphic else None
        )
        self.owner._last_print_detail_graphic = bool(self.detail_graphic)
        self.owner._last_detail_print_mark_rows = detail_mark_rows
        self.owner._last_detail_print_data_rows = detail_data_rows
        self.owner._last_detail_print_outer_marks = outer_marks
        self.owner._last_summary_header_metrics = (
            {"page_numbers_enabled": bool(
                 self.detail_graphic.get("summary_header_metrics", {}).get("page_numbers_enabled", False)),
             "page_number_format": str(
                 self.detail_graphic.get("summary_header_metrics", {}).get("page_number_format") or "page_x_y"),
             "page_number_align": str(
                 self.detail_graphic.get("summary_header_metrics", {}).get("page_number_align") or "right")}
            if self.detail_graphic else {}
        )
        self.owner._last_title=self.report_title
        self.owner._last_landscape=self.landscape
        self.owner._last_print_advanced_style = dict(self.advanced_style or {})
        if bool(getattr(self, "_pagination_probe", False)):
            self._pagination_probe_result = self.owner._prepared_print_pagination()
            return
        self.owner._print_preview()


class SummaryPreviewDialog(QDialog):
    """Aperçu interactif d'un état résumé ou groupé."""

    def __init__(
        self, owner, title, records, group_field, landscape, parent=None,
        source_name=None, saved_name=None, layout_state=None,
        date_group_mode="full_date", second_group_field=None, show_details=False,
        field_color="#9A3324", field_bold=True, advanced_style=None,
        summary_fields=None, summary_treatments=None, page_chrome=None,
        summary_header_metrics=None, summary_column_alignments=None, summary_field_styles=None):
        super().__init__(parent)
        self.advanced_style = dict(advanced_style or {})
        self.page_chrome = dict(page_chrome or {})
        self.summary_header_metrics = dict(summary_header_metrics or {})
        self.summary_column_header_labels = dict(self.summary_header_metrics.get("column_header_labels") or {})
        self.summary_column_header_styles = dict(self.summary_header_metrics.get("column_header_styles") or {})
        self.summary_column_header_hidden = set(self.summary_header_metrics.get("column_header_hidden") or [])
        self.summary_column_alignments = dict(summary_column_alignments or {})
        self.summary_field_styles = dict(summary_field_styles or {})
        self.owner = owner
        self.language = getattr(owner, "language", "fr")
        self.report_title = title
        self.records = list(records)
        self.group_field = group_field
        self.landscape = landscape
        self.source_name = source_name
        self.saved_name = saved_name
        self.layout_state = layout_state or {}
        self.date_group_mode = date_group_mode
        self.second_group_field = second_group_field
        self.show_details = bool(show_details)
        self.field_color = str(field_color or "#9A3324")
        self.field_bold = bool(field_bold)
        self.summary_fields = list(summary_fields or [])
        self.summary_treatments = dict(summary_treatments or {})

        self.setWindowTitle(f"{tr('Aperçu', self.owner.language)} — {title}")
        self.resize(980, 700)
        lay = QVBoxLayout(self)

        preview_name = self.saved_name or ""
        custom_title = str(self.advanced_style.get("header_title") or "").strip()
        page_title = str(self.page_chrome.get("title_text") or "").strip()
        heading_text = page_title or custom_title or title or tr("État résumé", self.owner.language)
        if not bool(self.page_chrome.get("show_title", True)):
            heading_text = ""

        extra_header_parts = []
        if bool(self.page_chrome.get("show_collection", False)):
            collection_name = str(getattr(self.owner, "collection", {}).get("name") or "").strip()
            if collection_name:
                extra_header_parts.append(collection_name)
        if bool(self.page_chrome.get("show_print_date", False)):
            extra_header_parts.append(QDate.currentDate().toString("dd/MM/yyyy"))

        if extra_header_parts:
            heading_text = (
                (heading_text + " — ") if heading_text else ""
            ) + " — ".join(extra_header_parts)

        heading = QLabel(heading_text)
        heading.setObjectName("previewTitle")
        heading.setVisible(bool(heading_text))
        lay.addWidget(heading)
        self.preview_heading = heading
        self._apply_advanced_preview_style(heading)

        # 27.62 — Interlignes/Filets du constructeur dans l'Aperçu écran.
        _layout_marks = dict(self.advanced_style.get("summary_layout_marks") or {})
        def _layout_mark_items(position):
            raw = _layout_marks.get(position)
            items = raw if isinstance(raw, list) else [raw]
            out=[]
            for item in items:
                if isinstance(item, dict):
                    kind=str(item.get("kind") or "none")
                    if kind in {"space","line"}:
                        out.append((kind,float(item.get("size") or 1),str(item.get("color") or "#000000")))
            return sorted(out, key=lambda x: 0 if x[0]=="line" else 1)
        def _layout_mark_data(position):
            items=_layout_mark_items(position)
            return items[0] if items else ("none",0,"#000000")
        self._print_summary_marks = {}
        def _add_preview_mark(position):
            bucket = self._print_summary_marks.setdefault(position, [])
            for kind, size, color in _layout_mark_items(position):
                w = QFrame()
                if kind == "space":
                    # 1.0.102 — l'interligne est un vrai widget blanc :
                    # il reste visible à l'écran ET peut être imprimé tel quel.
                    w.setFixedHeight(max(1, int(round(size))))
                    w.setStyleSheet("QFrame { border:0; background:#FFFFFF; }")
                else:
                    pt=max(0.2,float(size))
                    w.setFixedHeight(max(3,int(pt+2)))
                    w.setStyleSheet(
                        f"QFrame {{ border:0; border-top:{pt:g}px solid {color}; background:#FFFFFF; }}"
                    )
                lay.addWidget(w)
                bucket.append(w)

        _tf = heading.font(); _tf.setFamily(str(self.page_chrome.get("title_font_family") or _tf.family())); heading.setFont(_tf)
        if bool(self.advanced_style.get("separator", True)):
            heading.setStyleSheet(heading.styleSheet() + "border-bottom: 1px solid #7f8b87; padding-bottom: 4px;")
        _add_preview_mark("after_title")

        boxes = sum(_number(rec.get("box_count")) for rec in self.records)
        groups = self.owner._group_records(self.records, self.group_field, self.date_group_mode)
        # État résumé : une valeur maître vide ne constitue pas un groupe.
        groups.pop("(vide)", None); groups.pop("", None)

        metrics = dict(self.summary_header_metrics or {})
        distinct_field = metrics.get("distinct_field") or self.group_field
        species = self.owner._distinct_count(self.records, distinct_field)
        band_st = dict(metrics.get("band_style") or {})
        common_bg = str(
            band_st.get("bg") or metrics.get("groups_bg")
            or metrics.get("selected_bg")
            or metrics.get("species_bg")
            or metrics.get("records_bg")
            or "#F4F6F5"
        )
        counts_frame = QFrame()
        # 1.0.110 — le grisé du bandeau devient une option d’Aperçu.
        # La teinte existante reste inchangée ; seule son activation varie.
        self._summary_band_original_bg = common_bg
        self._summary_band_frame = counts_frame
        counts_frame.setStyleSheet(
            f"QFrame {{ background:{common_bg}; border:0px; }}"
        )
        counts = QHBoxLayout(counts_frame)
        counts.setContentsMargins(0, 0, 0, 0)
        # 1.0.106 — les positions X du constructeur sont désormais la source
        # de vérité de l'aperçu. Sans positions enregistrées, on conserve le
        # comportement historique pour les anciens modèles.
        _metric_positions = dict(metrics.get("metric_positions") or {})
        _metric_cursor = 0
        if (not _metric_positions) and str(band_st.get("align") or "left") in {"center", "right"}: counts.addStretch(1)

        def add_main_metric(number_text, label_text, family, size, text_color, bg_color, secondary=False, field=None):
            family = str(band_st.get("font") or family)
            size = int(band_st.get("size", size))
            text_color = str(band_st.get("text") or text_color)
            mst = dict(metrics.get("metric_styles", {}).get(str(field or "")) or {})
            vst = dict(mst.get("value") or {}); lst = dict(mst.get("label") or {})
            vf=str(vst.get("font") or family); vs=int(vst.get("size",size)); vc=str(vst.get("text") or text_color); vb=bool(vst.get("bold",band_st.get("bold",True))); vi=bool(vst.get("italic",band_st.get("italic",False)))
            lf=str(lst.get("font") or family); ls=int(lst.get("size",size)); lc=str(lst.get("text") or text_color); lb=bool(lst.get("bold",band_st.get("bold",True))); li=bool(lst.get("italic",band_st.get("italic",False)))
            lbl = QLabel(
                f"<span style='color:{vc};font-family:{_escape(vf)};font-size:{vs}pt;font-weight:{700 if vb else 400};font-style:{'italic' if vi else 'normal'}'>{_escape(str(number_text))}</span>"
                f"<span style='color:{lc};font-family:{_escape(lf)};font-size:{ls}pt;font-weight:{700 if lb else 400};font-style:{'italic' if li else 'normal'}'> {_escape(str(label_text))}</span>"
            )
            lbl.setTextFormat(Qt.TextFormat.RichText)
            if secondary:
                lbl.setObjectName("secondaryCount")
            chosen_width = dict(metrics.get("metric_widths") or {}).get(str(field or "__groups__"))
            if chosen_width:
                lbl.setFixedWidth(max(55, min(480, int(chosen_width))))
            nonlocal _metric_cursor
            _key = str(field or "__groups__")
            if _metric_positions:
                _x = max(0, int(_metric_positions.get(_key, _metric_cursor)))
                counts.addSpacing(max(0, _x - _metric_cursor))
                counts.addWidget(lbl)
                _metric_cursor = max(_metric_cursor, _x) + lbl.sizeHint().width()
            else:
                counts.addWidget(lbl)
                counts.addSpacing(16)

        if bool(metrics.get("groups", True)):
            add_main_metric(
                str(len(groups)),
                str(metrics.get("groups_label") or self.owner._plural_group_label(self.group_field, len(groups), self.date_group_mode)),
                metrics.get("groups_font", "Calibri"),
                metrics.get("groups_size", 11),
                metrics.get("groups_text", "#8B3026"),
                metrics.get("groups_bg", "#F4F6F5"),
            )

        if bool(metrics.get("selected", True)):
            selected_metric_fields = set(str(x) for x in (metrics.get("selected_fields") or []))
            # Les totaux sont indépendants des colonnes affichées.
            ordered_metric_fields = [str(f) for f in (metrics.get("selected_fields") or []) if str(f) in selected_metric_fields and str(f) in self.owner.labels]
            if _metric_positions:
                ordered_metric_fields.sort(key=lambda f: int(_metric_positions.get(str(f), 10**9)))
            for field in ordered_metric_fields:
                if field == "__records__":
                    add_main_metric(
                        str(self.owner._record_count(self.records)),
                        str(metrics.get("selected_labels", {}).get("__records__") or tr("fiche(s)", self.owner.language)),
                        metrics.get("records_font", "Calibri"),
                        metrics.get("records_size", 10),
                        metrics.get("records_text", "#7A817D"),
                        metrics.get("records_bg", "#F4F6F5"),
                        True, field="__records__",
                    )
                    continue
                treatment = self.owner._summary_treatment(field, self.summary_treatments.get(field))
                values = [rec.get(field) for rec in self.records if rec.get(field) not in (None, "")]
                label = self.owner.labels.get(field, field)
                custom_metric_label = str(metrics.get("selected_labels", {}).get(field) or "")

                if treatment in {"sum", "avg", "min", "max"}:
                    nums = [self.owner._summary_numeric_value(rec, field) for rec in self.records]
                    if treatment == "sum":
                        result = sum(nums) if nums else 0
                    elif treatment == "avg":
                        result = (sum(nums) / len(nums)) if nums else 0
                    elif treatment == "min":
                        result = min(nums) if nums else 0
                    else:
                        result = max(nums) if nums else 0
                    result_text = self.owner._summary_total_text(field, float(result))
                    metric_text = (
                        f"{result_text} {tr('pièce(s)', self.owner.language)}"
                        if field == "box_count"
                        else f"{result_text} {label.lower()}"
                    )
                    if field == "box_count":
                        number_text = result_text
                        label_text = custom_metric_label or tr("pièce(s)", self.owner.language)
                    else:
                        number_text = result_text
                        label_text = custom_metric_label or (label.lower() + "(s)")
                    add_main_metric(
                        number_text, label_text,
                        metrics.get("selected_font", "Calibri"),
                        metrics.get("selected_size", 11),
                        metrics.get("selected_text", "#8B3026"),
                        metrics.get("selected_bg", "#F4F6F5"),
                        field=field,
                    )
                else:
                    # Si le champ totalisé est précisément le champ Date qui sert
                    # au regroupement, compter les valeurs APRES découpage. Ainsi
                    # Date -> Année donne 14 années, pas 59 dates distinctes.
                    if field == self.group_field and self.owner._is_date_field(field) and self.date_group_mode != "full_date":
                        transformed = self.owner._group_records(self.records, field, self.date_group_mode)
                        distinct_count = len(transformed)
                        auto_label = self.owner._plural_group_label(field, distinct_count, self.date_group_mode)
                        # Le libellé « Groupes » est volontairement réutilisable :
                        # l'utilisateur peut écrire « années d'acquisition », etc.
                        label_text = custom_metric_label or str(metrics.get("groups_label") or auto_label)
                    else:
                        distinct_count = len({str(v) for v in values})
                        label_text = custom_metric_label or (label.lower() + "(s)")
                    add_main_metric(
                        str(distinct_count), label_text,
                        metrics.get("selected_font", "Calibri"),
                        metrics.get("selected_size", 11),
                        metrics.get("selected_text", "#8B3026"),
                        metrics.get("selected_bg", "#F4F6F5"),
                        field=field,
                    )

        if False:  # ancien compteur « Valeurs distinctes » supprimé : utiliser les coches Total
            distinct_label = str(metrics.get("distinct_label") or self.owner.labels.get(distinct_field, distinct_field)).strip().lower()
            add_main_metric(
                str(species), distinct_label or "valeurs",
                metrics.get("species_font", "Calibri"),
                metrics.get("species_size", 11),
                metrics.get("species_text", "#8B3026"),
                metrics.get("species_bg", "#F4F6F5"),
            )


        counts.addStretch(1)
        lay.addWidget(counts_frame)
        self._print_summary_top_totals = counts_frame
        _add_preview_mark("after_band")
        lay.addSpacing(6)

        hint = QLabel(tr(
            "Cliquez sur un titre pour trier. Déplacez les titres à la souris pour réorganiser les colonnes et redimensionnez-les à la souris.",
            self.owner.language,
        ))
        hint.setObjectName("previewHint"); hint.setWordWrap(True); lay.addWidget(hint); lay.addSpacing(8)

        self.rows_data = []
        for key in self.owner._sorted_group_keys(list(groups), self.group_field, self.date_group_mode):
            entries = groups[key]
            self.rows_data.append({
                "group": key,
                "boxes": sum(_number(rec.get("box_count")) for rec in entries),
                "species": self.owner._species_count(entries),
                "records": len(entries),
                "entries": entries,
            })

        def treatment_label(field):
            # L'opérateur appartient à la logique de calcul, pas au libellé imprimé.
            return tr("Nombre de fiches", self.owner.language) if field == "__records__" else self.owner.labels.get(field, field)

        # Une colonne n'est visible que si l'utilisateur a coché « Col. ».
        # Le champ de regroupement peut donc travailler en arrière-plan sans
        # s'imposer dans l'aperçu (ancien comportement : « Nom » revenait seul).
        self.show_group_column = self.group_field in self.summary_fields
        self.dynamic_summary_fields = [field for field in self.summary_fields if field != self.group_field]
        self.table_fields = ([self.group_field] if self.show_group_column else []) + list(self.dynamic_summary_fields)
        self.table = A4GuideTable(
            len(self.rows_data),
            len(self.table_fields),
            landscape=self.landscape,
        )
        # 1.0.102 — aucun filet implicite entre les données.
        # Les séparations sont désormais commandées uniquement par + Filet.
        self.table.setShowGrid(False)
        # 27.45 : QHeaderView natif sous Windows n'applique pas toujours
        # BackgroundRole par section. Le header MM3 peint explicitement le fond
        # et lit les mêmes rôles Font/Foreground/Alignment déjà utilisés.
        self.table.setHorizontalHeader(_MM3SummaryHeader(self.table))
        first_label = ("Année" if self.owner._is_date_field(self.group_field) and self.date_group_mode == "year" else ("Mois" if self.owner._is_date_field(self.group_field) and self.date_group_mode == "month" else ("Année + mois" if self.owner._is_date_field(self.group_field) and self.date_group_mode == "year_month" else self.owner.labels.get(self.group_field, self.group_field))))
        header_fields=[]
        header_labels = []
        if self.show_group_column:
            header_fields.append(self.group_field)
            header_labels.append("" if self.group_field in self.summary_column_header_hidden else str(self.summary_column_header_labels.get(self.group_field) or first_label))
        for field in self.dynamic_summary_fields:
            header_fields.append(field)
            header_labels.append("" if field in self.summary_column_header_hidden else str(self.summary_column_header_labels.get(field) or treatment_label(field)))
        self.table.setHorizontalHeaderLabels(header_labels)
        for col, field in enumerate(header_fields):
            item=self.table.horizontalHeaderItem(col)
            if item is None: continue
            st=dict(self.summary_column_header_styles.get(field) or {})
            f=QFont(str(st.get("font_family") or self.advanced_style.get("column_header_font_family") or "Calibri"))
            f.setPointSize(int(st.get("font_size", self.advanced_style.get("column_header_font_size",10))))
            f.setBold(bool(st.get("bold", self.advanced_style.get("column_header_bold",True))))
            f.setItalic(bool(st.get("italic", self.advanced_style.get("column_header_italic",False))))
            f.setUnderline(bool(st.get("underline", self.advanced_style.get("column_header_underline",False))))
            item.setFont(f); item.setForeground(QColor(str(st.get("text_color") or self.advanced_style.get("column_header_text_color") or "#111111")))
            header_bg = str(st.get("bg_color") or self.advanced_style.get("column_header_bg_color") or "#FFFFFF")
            item.setBackground(QColor("#FFFFFF" if header_bg.upper() == "#DDE8E2" else header_bg))
            al=str(st.get("align") or "center"); item.setTextAlignment((Qt.AlignLeft if al=="left" else Qt.AlignRight if al=="right" else Qt.AlignHCenter)|Qt.AlignVCenter)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(False)
        self.table.setWordWrap(False)
        self.table.setTextElideMode(Qt.TextElideMode.ElideRight)
        body_size = int(self.page_chrome.get("body_font_size", 10))
        print_font = str(self.page_chrome.get("print_font_family") or "Arial")
        # Police et taille définies cellule par cellule :
        # aucune règle globale ne doit les écraser.
        # 1.0.103 — État résumé : aucun filet inter-données par défaut.
        # Les anciens paramètres généraux detail_borders/detail_trait ne doivent
        # pas réintroduire de séparations. Un filet entre les données n'apparaît
        # que si l'utilisateur en ajoute explicitement dans "between_data".
        self.table.setStyleSheet(
            self.table.styleSheet()
            + "QTableWidget::item { border:0; }"
        )

        for row, data in enumerate(self.rows_data):
            _master_fmt = dict(self.summary_field_styles.get(self.group_field) or {})
            _master_value = str(data['group'])
            if self.owner._is_date_field(self.group_field):
                _master_value = _summary_format_date_text(_master_value, _master_fmt.get("date_format"))
            _master_text = f"{str(_master_fmt.get('prefix') or '')}{_master_value}{str(_master_fmt.get('suffix') or '')}"
            group_item=QTableWidgetItem(_master_text)
            typography = dict(self.advanced_style.get("typography") or {})
            master_style = dict(
                typography.get("summary_master")
                or {}
            )
            master_style.update(dict(self.summary_field_styles.get(self.group_field) or {}))
            group_item.setForeground(
                QColor(str(master_style.get("text_color", self.field_color)))
            )
            group_item.setBackground(
                QColor(str(master_style.get("bg_color", "#FFFFFF")))
            )
            group_font = QFont(
                str(master_style.get("font_family") or print_font)
            )
            group_font.setPointSize(int(master_style.get("font_size", 10)))
            group_font.setBold(bool(master_style.get("bold", self.field_bold)))
            group_font.setItalic(bool(master_style.get("italic", False)))
            group_font.setUnderline(bool(master_style.get("underline", False)))
            group_item.setFont(group_font)
            align = str(
                self.summary_column_alignments.get(
                    "__group__", master_style.get("align", "right")
                )
            )
            group_item.setTextAlignment(
                (Qt.AlignHCenter if align == "center" else Qt.AlignRight if align == "right" else Qt.AlignLeft)
                | Qt.AlignVCenter
            )
            if self.show_group_column:
                self.table.setItem(row, 0, group_item)
                if _master_fmt.get("prefix") or _master_fmt.get("suffix"):
                    rich=QLabel(); rich.setTextFormat(Qt.TextFormat.RichText); rich.setText(_summary_rich_cell_html(_master_value, master_style))
                    rich.setAlignment(Qt.AlignmentFlag(group_item.textAlignment())); rich.setStyleSheet("QLabel { background:transparent; padding-left:3px; padding-right:3px; }")
                    group_item.setText("")  # un seul rendu : le QLabel riche
                    self.table.setCellWidget(row,0,rich)
            entries = list(data.get("entries") or [])
            start_col = 1 if self.show_group_column else 0
            for col, field in enumerate(self.dynamic_summary_fields, start=start_col):
                treatment = self.owner._summary_treatment(field, self.summary_treatments.get(field))
                values = [rec.get(field) for rec in entries if rec.get(field) not in (None, "")]
                if field == "__records__":
                    result = len(entries)
                    text = str(result)
                elif treatment in {"sum", "avg", "min", "max"}:
                    nums = [self.owner._summary_numeric_value(rec, field) for rec in entries]
                    if treatment == "sum": result = sum(nums) if nums else 0
                    elif treatment == "avg": result = (sum(nums) / len(nums)) if nums else 0
                    elif treatment == "min": result = min(nums) if nums else 0
                    else: result = max(nums) if nums else 0
                    text = self.owner._summary_total_text(field, float(result))
                elif treatment == "count_distinct":
                    text = str(len({str(v) for v in values}))
                else:
                    text = ", ".join(sorted({str(v) for v in values}, key=str.casefold))
                _field_fmt = dict(self.summary_field_styles.get(field) or {})
                if self.owner._is_date_field(field):
                    text = _summary_format_date_text(text, _field_fmt.get("date_format"))
                text = f"{str(_field_fmt.get('prefix') or '')}{text}{str(_field_fmt.get('suffix') or '')}"
                result_item = (
                    ReportNumericItem(text, result)
                    if treatment in {"sum", "avg", "min", "max"}
                    else ReportNumericItem(text, len(entries))
                    if field == "__records__"
                    else QTableWidgetItem(text)
                )
                secondary_style = dict(
                    dict(self.advanced_style.get("typography") or {}).get(
                        "summary_secondary"
                    ) or {}
                )
                secondary_style.update(dict(self.summary_field_styles.get(field) or {}))
                result_item.setForeground(
                    QColor(str(secondary_style.get("text_color", "#111111")))
                )
                result_item.setBackground(
                    QColor(str(secondary_style.get("bg_color", "#FFFFFF")))
                )
                result_font = QFont(
                    str(secondary_style.get("font_family") or print_font)
                )
                result_font.setPointSize(
                    int(secondary_style.get("font_size", body_size))
                )
                result_font.setBold(bool(secondary_style.get("bold", False)))
                result_font.setItalic(bool(secondary_style.get("italic", False)))
                result_font.setUnderline(
                    bool(secondary_style.get("underline", False))
                )
                result_item.setFont(result_font)

                align = str(
                    self.summary_column_alignments.get(
                        field, secondary_style.get("align", "left")
                    )
                )
                if align == "center":
                    result_item.setTextAlignment(
                        int(Qt.AlignHCenter | Qt.AlignVCenter)
                    )
                elif align == "right":
                    result_item.setTextAlignment(
                        int(Qt.AlignRight | Qt.AlignVCenter)
                    )
                else:
                    result_item.setTextAlignment(
                        int(Qt.AlignLeft | Qt.AlignVCenter)
                    )
                self.table.setItem(row, col, result_item)
                if _field_fmt.get("prefix") or _field_fmt.get("suffix"):
                    # Le QLabel riche permet au libellé libre de conserver une
                    # typographie indépendante de la donnée dans l'Aperçu.
                    raw_value = text
                    pref=str(_field_fmt.get("prefix") or ""); suff=str(_field_fmt.get("suffix") or "")
                    if pref and raw_value.startswith(pref): raw_value=raw_value[len(pref):]
                    if suff and raw_value.endswith(suff): raw_value=raw_value[:-len(suff)]
                    rich=QLabel(); rich.setTextFormat(Qt.TextFormat.RichText); rich.setText(_summary_rich_cell_html(raw_value, secondary_style))
                    rich.setAlignment(Qt.AlignmentFlag(result_item.textAlignment())); rich.setStyleSheet("QLabel { background:transparent; padding-left:3px; padding-right:3px; }")
                    result_item.setText("")  # un seul rendu : le QLabel riche
                    self.table.setCellWidget(row,col,rich)

        header=self.table.horizontalHeader()
        header_align = str(
            self.advanced_style.get("column_header_align") or "center"
        )
        header_qt_align = (
            Qt.AlignLeft
            if header_align == "left"
            else Qt.AlignRight
            if header_align == "right"
            else Qt.AlignHCenter
        ) | Qt.AlignVCenter
        for logical in range(self.table.columnCount()):
            header_item = self.table.horizontalHeaderItem(logical)
            if header_item is not None:
                # 27.43 : l'alignement propre à chaque en-tête prime sur
                # l'ancien réglage global, conservé comme valeur par défaut.
                field = self.table_fields[logical] if logical < len(self.table_fields) else None
                st = dict(self.summary_column_header_styles.get(field) or {}) if field else {}
                al = str(st.get("align") or header_align)
                qa = (Qt.AlignLeft if al == "left" else Qt.AlignRight if al == "right" else Qt.AlignHCenter) | Qt.AlignVCenter
                header_item.setTextAlignment(int(qa))

        header_family = str(
            self.advanced_style.get("column_header_font_family") or "Calibri"
        )
        header_text = str(self.advanced_style.get("column_header_text_color") or "#111111")
        header_bg = str(self.advanced_style.get("column_header_bg_color") or "#FFFFFF")
        if header_bg.upper() == "#DDE8E2": header_bg = "#FFFFFF"
        header_size = int(self.advanced_style.get("column_header_font_size", 10))
        header_weight = "700" if bool(self.advanced_style.get("column_header_bold", True)) else "400"
        header_italic = "italic" if bool(self.advanced_style.get("column_header_italic", False)) else "normal"
        header_decoration = "underline" if bool(self.advanced_style.get("column_header_underline", False)) else "none"

        header_font = QFont()
        header_font.setFamily(header_family)
        header_font.setPointSize(header_size)
        header_font.setBold(
            bool(self.advanced_style.get("column_header_bold", True))
        )
        header_font.setItalic(
            bool(self.advanced_style.get("column_header_italic", False))
        )
        header_font.setUnderline(
            bool(self.advanced_style.get("column_header_underline", False))
        )
        header.setFont(header_font)

        # 27.43 : ne plus imposer couleur/fond/police par feuille de style.
        # Une QSS sur QHeaderView::section écrasait les rôles Font/Foreground/
        # Background portés par chaque QTableWidgetItem d'en-tête. Les valeurs
        # individuelles définies dans le constructeur peuvent ainsi atteindre
        # réellement la Vue ; le style global reste le défaut des items.
        header.setStyleSheet(
            "QHeaderView::section { padding:7px; border:1px solid #B8C7BF; }"
        )
        header_trait_px = _trait_css_width(
            self.advanced_style.get("header_trait") or "2pt"
        )
        if header_trait_px != "0px":
            header.setStyleSheet(
                header.styleSheet()
                + "QHeaderView::section {"
                f"border-bottom:{header_trait_px} solid #222;"
                "}"
            )
        header.setSectionsMovable(True); header.setSectionsClickable(True)
        try:
            header.setFirstSectionMovable(True)
        except Exception:
            pass
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.setSortingEnabled(True)
        typography = dict(self.advanced_style.get("typography") or {})
        master_size = int(
            dict(typography.get("summary_master") or {}).get("font_size", 10)
        )
        secondary_size = int(
            dict(typography.get("summary_secondary") or {}).get("font_size", 10)
        )
        row_height = max(20, int(max(master_size, secondary_size) * 2.25))
        self.table.verticalHeader().setDefaultSectionSize(row_height)
        self.table.setColumnWidth(0, 240)
        for col in range(1, self.table.columnCount()):
            self.table.setColumnWidth(col, 190)
        self._apply_saved_layout()
        for col, field in enumerate(self.table_fields):
            width = dict(self.summary_header_metrics.get("column_widths") or {}).get(field)
            if width is not None:
                self.table.setColumnWidth(col, max(28, min(480, int(width))))
        # Toute permutation à la souris devient immédiatement l'ordre officiel.
        # Cela évite qu'un rafraîchissement ultérieur réapplique l'ancien ordre.
        def _remember_column_order(*_args):
            keys = self._keys(); h = self.table.horizontalHeader()
            self.layout_state["column_order"] = [keys[h.logicalIndex(v)] for v in range(h.count())]
        header.sectionMoved.connect(_remember_column_order)
        # Dernière opération avant affichage : réimposer les QFont
        # maître/secondaires après toute feuille de style Qt.
        self._apply_summary_cell_typography()
        _add_preview_mark("after_header")
        for _bd_kind, _bd_size, _bd_color in _layout_mark_items("between_data"):
            if _bd_kind == "space":
                self.table.verticalHeader().setDefaultSectionSize(
                    self.table.verticalHeader().defaultSectionSize() + max(1,int(_bd_size))
                )
            elif _bd_kind == "line":
                # Filet demandé explicitement : séparation horizontale des données.
                self.table.setStyleSheet(
                    self.table.styleSheet()
                    + f"QTableWidget::item {{ border:0; border-bottom:{max(1,int(_bd_size))}px solid {_bd_color}; }}"
                )
        lay.addWidget(self.table, 1)

        if self.second_group_field or self.show_details:
            browser = QTextBrowser()
            browser.setHtml(self.owner._grouped_details_html(
                self.records, self.group_field, self.date_group_mode,
                self.second_group_field, self.show_details,
            ))
            browser.setMinimumHeight(240)
            lay.addWidget(browser, 1)

        # 1.0.102 — les marques basses appartiennent à la zone située
        # ENTRE les données et le pied de page, conformément au constructeur.
        _add_preview_mark("before_footer_line")
        _add_preview_mark("before_footer")

        # Pied de page de l’état résumé. En mode lié, il reprend automatiquement
        # les totaux du bandeau ; sinon il utilise sa propre sélection.
        _m = dict(self.summary_header_metrics or {})
        _footer_linked = bool(_m.get("footer_linked", False))
        _footer_fields = set(str(x) for x in (_m.get("footer_fields") or []))
        # 27.119 — ignorer le reliquat historique __records__ lorsqu'il n'est
        # pas explicitement coché comme Total.
        if not bool(_m.get("records", False)):
            _footer_fields.discard("__records__")
        if _footer_linked or _footer_fields:
            _fst = dict(_m.get("footer_style") or {})
            _frame=QFrame(); _frame.setStyleSheet(f"QFrame {{ background:{_fst.get('bg','#FFFFFF')}; border:0; }}")
            _fl=QHBoxLayout(_frame); _fl.setContentsMargins(0,3,0,3); _fl.setSpacing(0)
            _footer_positions = (dict(_m.get("metric_positions") or {}) if _footer_linked
                                 else dict(_m.get("footer_metric_positions") or {}))
            _footer_cursor = 0
            if (not _footer_positions) and (not _footer_linked) and str(_fst.get("align") or "left") in {"center","right"}: _fl.addStretch(1)
            _selected = set(str(x) for x in (_m.get("selected_fields") or [])) if _footer_linked else _footer_fields
            if _footer_linked and bool(_m.get("groups",True)):
                _selected.add("__groups__")
            if _footer_linked and bool(_m.get("records",False)):
                _selected.add("__records__")
            def _add_footer_metric(num, lab, field):
                mst=dict(_m.get("footer_metric_styles",{}).get(str(field),{}) or {}); vst=dict(mst.get("value") or {}); lst=dict(mst.get("label") or {})
                fam=str(_fst.get("font") or "Calibri"); size=int(_fst.get("size",10)); col=str(_fst.get("text") or "#111111")
                vf=str(vst.get("font") or fam); vs=int(vst.get("size",size)); vc=str(vst.get("text") or col); vb=bool(vst.get("bold",_fst.get("bold",True))); vi=bool(vst.get("italic",_fst.get("italic",False)))
                lf=str(lst.get("font") or fam); ls=int(lst.get("size",size)); lc=str(lst.get("text") or col); lb=bool(lst.get("bold",_fst.get("bold",True))); li=bool(lst.get("italic",_fst.get("italic",False)))
                lab=str(_m.get('footer_metric_labels',{}).get(str(field)) or lab)
                q=QLabel(f"<span style='font-family:{_escape(vf)};font-size:{vs}pt;color:{vc};font-weight:{700 if vb else 400};font-style:{'italic' if vi else 'normal'}'>{_escape(str(num))}</span><span style='font-family:{_escape(lf)};font-size:{ls}pt;color:{lc};font-weight:{700 if lb else 400};font-style:{'italic' if li else 'normal'};white-space:pre;'> {_escape(str(lab))}</span>"); q.setTextFormat(Qt.TextFormat.RichText); _widths=dict(_m.get("metric_widths") or {}) if _footer_linked else dict(_m.get("footer_metric_widths") or {}); _width=_widths.get(str(field)); q.setFixedWidth(max(55, min(480, int(_width))) if _width else max(1, q.sizeHint().width())); q.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
                nonlocal _footer_cursor
                if _footer_positions:
                    _x=max(0,int(_footer_positions.get(str(field),_footer_cursor))); _fl.addSpacing(max(0,_x-_footer_cursor)); _fl.addWidget(q); _footer_cursor=max(_footer_cursor,_x)+q.sizeHint().width()
                else:
                    _fl.addWidget(q); _spacing_map=dict(_m.get('footer_metric_spacing',{}) or {}); _default_gap=8 if _footer_linked else 16; _fl.addSpacing(int(_spacing_map.get(str(field),_default_gap)))
            if "__groups__" in _selected:
                _add_footer_metric(len(groups), str(_m.get("groups_label") or self.owner._plural_group_label(self.group_field,len(groups),self.date_group_mode)), "__groups__")
            _footer_render_fields = ([str(f) for f in (_m.get("selected_fields") or []) if str(f) in _selected and str(f) != "__records__"] if _footer_linked else list(dict.fromkeys([str(f) for f in (_m.get("footer_order") or []) if str(f) in _selected and str(f) != "__records__"]+[f for _label,f in self.owner.fields if str(f) in _selected and str(f) != "__records__"])))
            if _footer_positions:
                _footer_render_fields.sort(key=lambda f: int(_footer_positions.get(str(f), 10**9)))
            for _field in _footer_render_fields:
                _vals=[r.get(_field) for r in self.records if r.get(_field) not in (None,"")]; _tr=self.owner._summary_treatment(_field,self.summary_treatments.get(_field)); _custom=str(_m.get("selected_labels",{}).get(_field) or "")
                if _tr in {"sum","avg","min","max"}:
                    _nums=[self.owner._summary_numeric_value(r, _field) for r in self.records]
                    _res=(sum(_nums) if _tr=="sum" else (sum(_nums)/len(_nums) if _nums else 0) if _tr=="avg" else min(_nums) if _nums and _tr=="min" else max(_nums) if _nums else 0)
                    _num=self.owner._summary_total_text(_field, float(_res)); _lab=_custom or (tr("pièce(s)", self.owner.language) if _field=="box_count" else self.owner.labels.get(_field,_field).lower()+"(s)")
                else:
                    if _field==self.group_field and self.owner._is_date_field(_field) and self.date_group_mode!="full_date": _cnt=len(self.owner._group_records(self.records,_field,self.date_group_mode)); _lab=_custom or str(_m.get("groups_label") or self.owner._plural_group_label(_field,_cnt,self.date_group_mode))
                    else: _cnt=len({str(v) for v in _vals}); _lab=_custom or self.owner.labels.get(_field,_field).lower()+"(s)"
                    _num=str(_cnt)
                _add_footer_metric(_num,_lab,_field)
            if "__records__" in _selected:
                _add_footer_metric(self.owner._record_count(self.records), str(_m.get("selected_labels",{}).get("__records__") or tr("fiche(s)", self.owner.language)), "__records__")
            _fl.addStretch(1)
            lay.addWidget(_frame)
            self._print_summary_bottom_totals = _frame


        # 1.0.114 — la pagination de l'État résumé vient exclusivement du
        # Pied de page du constructeur. L'ancien page_chrome fabriquait un
        # « Page 1 / 1 » permanent, insensible aux réglages du constructeur.
        footer_text = str(self.page_chrome.get("footer_text") or "").strip()
        _pn_enabled = bool(metrics.get("page_numbers_enabled", False))
        _pn_fmt = str(metrics.get("page_number_format") or "page_x_y")
        _pn_align = str(metrics.get("page_number_align") or "right")
        _pn_sample = ("Page 1 / 1" if _pn_fmt == "page_x_y" else
                      ("Page 1" if _pn_fmt == "page_x" else "1 / 1"))
        footer_parts = [x for x in (footer_text, _pn_sample if _pn_enabled else "") if x]
        if footer_parts:
            footer = QLabel(" — ".join(footer_parts))

            footer_align = _pn_align if _pn_enabled else str(self.page_chrome.get("footer_align") or "right")
            if footer_align == "center":
                footer.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
            elif footer_align == "left":
                footer.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            else:
                footer.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

            footer_size = int(self.page_chrome.get("footer_font_size", 10))
            footer_bold = bool(self.page_chrome.get("footer_bold", False))
            footer_italic = bool(self.page_chrome.get("footer_italic", False))
            footer_underline = bool(self.page_chrome.get("footer_underline", False))
            footer_color = str(self.page_chrome.get("footer_text_color") or "#4F5A55")
            footer_bg = "#FFFFFF"  # 1.0.112 — fond de feuille blanc dans l’Aperçu

            font = footer.font()
            font.setPointSize(footer_size)
            font.setBold(footer_bold)
            font.setItalic(footer_italic)
            font.setUnderline(footer_underline)
            footer.setFont(font)

            weight = "700" if footer_bold else "400"
            style_name = "italic" if footer_italic else "normal"
            decoration = "underline" if footer_underline else "none"
            footer.setStyleSheet(
                "QLabel {"
                f"color:{footer_color}; background-color:{footer_bg};"
                # 1.0.121 — pagination sans filet supérieur : évite tout doublon
                # avec les filets de données/pied sur les états longs.
                "border:0px;"
                "padding:5px 6px 2px 6px;"
                f"font-size:{footer_size}pt; font-weight:{weight};"
                f"font-style:{style_name}; text-decoration:{decoration};"
                "}"
            )
            lay.addWidget(footer)
            # 1.0.115 — conserver le pied de pagination réellement affiché
            # afin que l’impression directe reprenne exactement l’Aperçu.
            self._print_summary_page_footer = footer

        self._apply_body_font_to_cells()
        self._apply_compact_row_heights()
        self._install_screen_zoom(lay)

        actions=QHBoxLayout()
        band_gray = QCheckBox(tr("Bandeau des totaux grisé", self.owner.language))
        band_gray.setChecked(bool(self.advanced_style.get("preview_gray_totals_band", True)))
        band_gray.setToolTip(tr("Afficher ou masquer le fond grisé du bandeau des totaux", self.owner.language))
        actions.addSpacing(220)
        actions.addWidget(band_gray)
        actions.addStretch(1)
        self.preview_band_gray_checkbox = band_gray
        modify_btn=QPushButton(tr("Modifier", self.owner.language)); save_btn=QPushButton(tr("Enregistrer l’état", self.owner.language)); library_btn=QPushButton(tr("Enregistrer sous…", self.owner.language)); print_btn=QPushButton(tr("Imprimer", self.owner.language)); back=QPushButton(tr("Retour", self.owner.language))
        modify_btn.clicked.connect(
            lambda: self.owner._modify_report_from_preview(
                self,
                self.saved_name,
                getattr(self, "builder_page", None),
            )
        )
        save_btn.clicked.connect(self._save_report); library_btn.setToolTip(tr("Conserver cet état dans la bibliothèque Modèles d’États", self.language)); library_btn.clicked.connect(lambda: self.owner.save_report_to_library(self.saved_name, getattr(self, "builder_page", None))); print_btn.setToolTip(tr("Aperçu avant impression multipage", self.language))
        print_btn.clicked.connect(self._print); back.clicked.connect(self.accept)
        actions.addWidget(modify_btn); actions.addWidget(save_btn); actions.addWidget(library_btn); actions.addWidget(print_btn); actions.addWidget(back); lay.addLayout(actions)

        def _remember_preview_option(key, value):
            self.advanced_style[key] = bool(value)
            page = getattr(self, "builder_page", None)
            if page is not None:
                setattr(page, key, bool(value))

        def _apply_zebra(checked):
            self.table.setAlternatingRowColors(bool(checked))
            _remember_preview_option("preview_zebra_rows", checked)
            self.table.viewport().update()

        def _apply_band_gray(checked):
            # 1.0.145 — « bandeau grisé » doit rester visiblement grisé quelle
            # que soit la langue. Certains modèles anglais restituent un fond
            # de bandeau blanc ; dans ce cas on applique le gris clair standard.
            bg = str(self._summary_band_original_bg or "").strip()
            if checked:
                _c = QColor(bg)
                if (not _c.isValid()) or (_c.red() >= 248 and _c.green() >= 248 and _c.blue() >= 248):
                    bg = "#F4F6F5"
            else:
                bg = "#FFFFFF"
            self._summary_band_frame.setStyleSheet(
                f"QFrame {{ background:{bg}; border:0px; }}"
            )
            _remember_preview_option("preview_gray_totals_band", checked)
            self._summary_band_frame.update()

        # 1.0.111 — les cases sont créées dans leurs lignes respectives avant
        # d’être reliées ici. La 1.0.110 reliait `zebra` avant sa création,
        # ce qui empêchait l’ouverture de l’Aperçu.
        zebra = self.preview_zebra_checkbox
        band_gray = self.preview_band_gray_checkbox
        zebra.toggled.connect(_apply_zebra)
        band_gray.toggled.connect(_apply_band_gray)
        # Appliquer aussi l’état initial (anciens modèles = les deux grisages actifs).
        _apply_zebra(zebra.isChecked())
        _apply_band_gray(band_gray.isChecked())

        self.setStyleSheet("""
            #previewTitle { }
            #mainCount { font-size:17px; font-weight:700; color:#8B3026; }
            #secondaryCount { color:#7A817D; }
            #previewHint { color:#66716B; }
        """)




    def _apply_body_font_to_cells(self) -> None:
        """Applique Police + Taille du corps sans écraser les styles Résumé.

        Dans un État Résumé, la colonne 0 est le groupe maître et les autres
        colonnes sont les groupes secondaires : leurs polices sont gérées par
        summary_master / summary_secondary et doivent rester prioritaires.
        """
        typography = dict(self.advanced_style.get("typography") or {})
        has_summary_styles = bool(
            typography.get("summary_master")
            or typography.get("summary_secondary")
        )

        if has_summary_styles:
            # Les nouveaux styles Résumé sont la source de vérité.
            self._apply_summary_cell_typography()
            return

        # Compatibilité avec les anciens états ne possédant pas encore
        # summary_master / summary_secondary.
        family = str(self.page_chrome.get("print_font_family") or "Arial")
        size = int(self.page_chrome.get("body_font_size", 10))

        for row in range(self.table.rowCount()):
            if self.table.columnSpan(row, 0) > 1:
                continue
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                if item is None:
                    continue
                font = QFont(item.font())
                font.setFamily(family)
                font.setPointSize(size)
                item.setFont(font)

    def _apply_compact_row_heights(self) -> None:
        """Adapte la hauteur des lignes à la petite taille de police."""
        body_size = int(self.page_chrome.get("body_font_size", 10))
        # Valeurs volontairement serrées pour retrouver un état dense type Access.
        if body_size <= 6:
            height = 16
        elif body_size == 7:
            height = 18
        elif body_size == 8:
            height = 20
        elif body_size == 9:
            height = 22
        else:
            height = 24
        # Interligne « Entre les lignes de données » : la hauteur demandée
        # s'ajoute réellement à chaque ligne de l'Aperçu.
        raw = dict(self.advanced_style.get("summary_layout_marks") or {}).get("between_data")
        if isinstance(raw, dict) and str(raw.get("kind") or "") == "space":
            height += max(1, int(raw.get("size") or 1))

        for row in range(self.table.rowCount()):
            # Ne pas écraser les gros bandeaux de regroupement.
            if self.table.columnSpan(row, 0) > 1:
                continue
            self.table.setRowHeight(row, height)

    def _install_screen_zoom(self, lay) -> None:
        """Loupe d'affichage uniquement — ne modifie jamais l'état imprimé."""
        self._screen_zoom_percent = 100
        self._zoom_base_table_font = QFont(self.table.font())
        self._zoom_base_table_style = self.table.styleSheet()
        self._zoom_base_header_style = self.table.horizontalHeader().styleSheet()
        self._zoom_base_col_widths = [
            self.table.columnWidth(i) for i in range(self.table.columnCount())
        ]
        self._zoom_base_row_heights = [
            self.table.rowHeight(i) for i in range(self.table.rowCount())
        ]

        self._zoom_label_bases = []
        for label in self.findChildren(QLabel):
            self._zoom_label_bases.append(
                (
                    label,
                    QFont(label.font()),
                    label.styleSheet(),
                    label.text(),
                    label.textFormat(),
                )
            )

        row = QHBoxLayout()
        row.setContentsMargins(0, 2, 0, 2)
        row.addWidget(QLabel(tr("Loupe :", self.owner.language)))

        minus = QPushButton("−")
        minus.setFixedWidth(32)
        minus.setToolTip("Réduire l’affichage")

        zoom = QComboBox()
        zoom.setEditable(True)
        zoom.setFixedWidth(82)
        for value in (50, 60, 70, 80, 90, 100, 110, 125, 150, 175, 200):
            zoom.addItem(f"{value} %", value)
        zoom.setCurrentIndex(zoom.findData(100))
        zoom.setToolTip(
            "Agrandit ou réduit seulement l’affichage de l’état. "
            "La taille d’impression n’est pas modifiée."
        )

        plus = QPushButton("+")
        plus.setFixedWidth(32)
        plus.setToolTip("Agrandir l’affichage")

        row.addWidget(minus)
        row.addWidget(zoom)
        row.addWidget(plus)

        # 1.0.110 — options visuelles placées dans l’espace libre de l’Aperçu,
        # sans déplacer la Loupe ni les boutons existants.
        zebra = QCheckBox(tr("Lignes alternées grisées", self.owner.language))
        zebra.setChecked(bool(self.advanced_style.get("preview_zebra_rows", True)))
        zebra.setToolTip(tr("Afficher ou masquer le grisé d’une ligne de données sur deux", self.owner.language))
        row.addSpacing(12)
        row.addWidget(zebra)
        row.addStretch(1)
        lay.addLayout(row)
        self.preview_zebra_checkbox = zebra

        self.screen_zoom_widget = zoom

        def current_percent():
            text = zoom.currentText().strip().replace("%", "").replace(",", ".")
            try:
                return int(round(float(text)))
            except Exception:
                return int(self._screen_zoom_percent)

        def apply_from_combo(*_):
            self._apply_screen_zoom(current_percent())

        def step(delta):
            value = max(40, min(250, current_percent() + delta))
            zoom.blockSignals(True)
            idx = zoom.findData(value)
            if idx >= 0:
                zoom.setCurrentIndex(idx)
            else:
                zoom.setEditText(f"{value} %")
            zoom.blockSignals(False)
            self._apply_screen_zoom(value)

        minus.clicked.connect(lambda: step(-10))
        plus.clicked.connect(lambda: step(10))
        zoom.currentTextChanged.connect(apply_from_combo)
        if zoom.lineEdit() is not None:
            zoom.lineEdit().editingFinished.connect(apply_from_combo)

    @staticmethod
    def _scaled_font_sizes_in_text(text: str, factor: float) -> str:
        def repl(match):
            value = float(match.group(1))
            scaled = max(5.0, value * factor)
            shown = f"{scaled:.1f}".rstrip("0").rstrip(".")
            return f"font-size:{shown}pt"
        return re.sub(r"font-size\s*:\s*([0-9]+(?:\.[0-9]+)?)pt", repl, text)

    def _apply_screen_zoom(self, percent: int) -> None:
        """Applique la loupe aux widgets visibles, sans toucher aux paramètres."""
        percent = max(40, min(250, int(percent)))
        self._screen_zoom_percent = percent
        factor = percent / 100.0

        # Tableau et en-têtes.
        font = QFont(self._zoom_base_table_font)
        base_size = font.pointSizeF()
        if base_size <= 0:
            base_size = 10.0
        font.setPointSizeF(max(5.0, base_size * factor))
        self.table.setFont(font)

        self.table.setStyleSheet(
            self._scaled_font_sizes_in_text(self._zoom_base_table_style, factor)
        )
        self.table.horizontalHeader().setStyleSheet(
            self._scaled_font_sizes_in_text(self._zoom_base_header_style, factor)
        )

        for i, width in enumerate(self._zoom_base_col_widths):
            self.table.setColumnWidth(i, max(24, int(round(width * factor))))
        for i, height in enumerate(self._zoom_base_row_heights):
            self.table.setRowHeight(i, max(16, int(round(height * factor))))

        # Titres, compteurs, bandeaux et pied de page.
        for label, base_font, base_style, base_text, text_format in self._zoom_label_bases:
            f = QFont(base_font)
            size = f.pointSizeF()
            if size > 0:
                f.setPointSizeF(max(5.0, size * factor))
                label.setFont(f)
            label.setStyleSheet(
                self._scaled_font_sizes_in_text(base_style, factor)
            )
            if (
                text_format == Qt.TextFormat.RichText
                or "font-size" in base_text.lower()
                or "<span" in base_text.lower()
            ):
                label.setText(
                    self._scaled_font_sizes_in_text(base_text, factor)
                )


    def _apply_advanced_preview_style(self, widget) -> None:
        """Style de l'en-tête général, avec compatibilité des anciens états."""
        legacy = dict(getattr(self, "advanced_style", {}) or {})
        chrome = dict(getattr(self, "page_chrome", {}) or {})
        if widget is None:
            return

        size = int(chrome.get("title_font_size", legacy.get("font_size", 20)))
        bold = bool(chrome.get("title_bold", True))
        italic = bool(chrome.get("title_italic", legacy.get("italic", False)))
        underline = bool(chrome.get("title_underline", legacy.get("underline", False)))

        font = widget.font()
        font.setFamily(str(chrome.get("print_font_family") or "Arial"))
        font.setPointSize(size)
        font.setBold(bold)
        font.setItalic(italic)
        font.setUnderline(underline)
        widget.setFont(font)

        align = str(chrome.get("title_align") or legacy.get("align", "left"))
        if align == "center":
            widget.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        elif align == "right":
            widget.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        else:
            widget.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        text_color = str(chrome.get("title_text_color") or "#111111")
        bg_color = "#FFFFFF"  # 1.0.112 — Aperçu: la feuille reste blanche, indépendamment du fond du constructeur
        weight = "700" if bold else "400"
        style_name = "italic" if italic else "normal"
        decoration = "underline" if underline else "none"

        widget.setStyleSheet(
            "QLabel {"
            f"color:{text_color}; background-color:{bg_color};"
            f"font-size:{size}pt; font-weight:{weight};"
            f"font-style:{style_name}; text-decoration:{decoration};"
            "padding:4px 6px;"
            "}"
        )


    def _keys(self):
        return list(getattr(self, "table_fields", []))

    def _apply_saved_layout(self):
        header=self.table.horizontalHeader(); keys=self._keys()
        for target,key in enumerate(self.layout_state.get("column_order", [])):
            if key in keys:
                current=header.visualIndex(keys.index(key))
                if current != target: header.moveSection(current,target)
        for key,width in self.layout_state.get("column_widths", {}).items():
            if key in keys: header.resizeSection(keys.index(key), int(width))
        sort_key=self.layout_state.get("sort_field")
        if sort_key in keys:
            order=Qt.SortOrder.DescendingOrder if self.layout_state.get("sort_desc") else Qt.SortOrder.AscendingOrder
            self.table.sortItems(keys.index(sort_key), order)

    def _layout_state(self):
        header=self.table.horizontalHeader(); keys=self._keys()
        logical=header.sortIndicatorSection()
        return {
            "column_order":[keys[header.logicalIndex(v)] for v in range(header.count())],
            "column_widths":{key:header.sectionSize(i) for i,key in enumerate(keys)},
            "sort_field":keys[logical] if 0 <= logical < len(keys) else None,
            "sort_desc":header.sortIndicatorOrder() == Qt.SortOrder.DescendingOrder,
        }

    def _save_report(self):
        name=self.owner.save_report_definition(
            kind="summary", title=self.report_title, source_name=self.source_name,
            landscape=self.landscape, group_field=self.group_field,
            layout_state=self._layout_state(), existing_name=self.saved_name,
            builder_page=getattr(self, "builder_page", None),
            date_group_mode=self.date_group_mode,
            second_group_field=self.second_group_field,
            show_details=self.show_details,
            summary_field_color=self.field_color,
            summary_field_bold=self.field_bold,
        )
        if name:
            # 1.0.121 — les deux options visuelles sont pilotées dans l’Aperçu.
            # Quand un état enregistré est ouvert directement, builder_page peut
            # être absent : il faut donc persister explicitement les valeurs dans
            # la définition sauvegardée, au lieu de retomber sur True au prochain
            # démarrage de G-Skol.
            _zebra = bool(self.preview_zebra_checkbox.isChecked())
            _band_gray = bool(self.preview_band_gray_checkbox.isChecked())
            self.advanced_style["preview_zebra_rows"] = _zebra
            self.advanced_style["preview_gray_totals_band"] = _band_gray
            _saved = self.owner.saved_reports.get(name)
            if isinstance(_saved, dict):
                _style = dict(_saved.get("advanced_style") or {})
                _style["preview_zebra_rows"] = _zebra
                _style["preview_gray_totals_band"] = _band_gray
                _saved["advanced_style"] = _style
                self.owner.saved_reports[name] = _saved
                self.owner._write_saved_reports()
            self.saved_name=name
            self.setWindowTitle(f"Aperçu — {self.report_title} — {name}")
            if hasattr(self, "preview_heading"):
                self.preview_heading.setText(f"État résumé : {name}")
            self.owner._sync_builder_after_preview_save(
                getattr(self, "builder_page", None), "summary", name
            )


    def _apply_summary_cell_typography(self):
        """Applique aux cellules les styles définis dans la Construction.

        Les styles propres à chaque champ (27.16+) ont priorité sur les anciens
        styles génériques maître/secondaire. L'en-tête de colonnes reste
        volontairement indépendant.
        """
        typography = dict(self.advanced_style.get("typography") or {})
        master_base = dict(
            typography.get("summary_master")
            or {}
        )
        secondary_base = dict(typography.get("summary_secondary") or {})
        max_size = 10

        for row in range(self.table.rowCount()):
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                if item is None:
                    continue
                field = self.table_fields[col] if 0 <= col < len(self.table_fields) else None
                is_master = bool(self.show_group_column and field == self.group_field)
                style = dict(master_base if is_master else secondary_base)
                if field:
                    style.update(dict(self.summary_field_styles.get(field) or {}))

                family = str(style.get("font_family") or "Arial")
                size = int(style.get("font_size", 10))
                max_size = max(max_size, size)
                font = QFont(family)
                font.setPointSize(size)
                font.setBold(bool(style.get("bold", True if is_master else False)))
                font.setItalic(bool(style.get("italic", False)))
                font.setUnderline(bool(style.get("underline", False)))
                item.setFont(font)
                item.setForeground(QColor(str(style.get("text_color", "#9A3324" if is_master else "#111111"))))
                item.setBackground(QColor(str(style.get("bg_color", "#FFFFFF"))))

                # L'alignement choisi dans Mise en forme appartient au champ.
                # Compatibilité : l'ancien maître pouvait être stocké sous __group__.
                # Le réglage propre au champ est prioritaire. L'ancien __group__
                # n'est utilisé qu'en compatibilité si le champ ne porte aucun
                # alignement explicite. Cela évite le premier aperçu à droite.
                if field in self.summary_column_alignments:
                    align = str(self.summary_column_alignments.get(field) or "left")
                elif "align" in style:
                    align = str(style.get("align") or "left")
                elif is_master:
                    align = str(self.summary_column_alignments.get("__group__", "left"))
                else:
                    align = "left"
                vertical = str(self.summary_header_metrics.get("row_vertical_align") or "center")
                valign = Qt.AlignTop if vertical == "top" else Qt.AlignBottom if vertical == "bottom" else Qt.AlignVCenter
                if align == "center":
                    item.setTextAlignment(int(Qt.AlignHCenter | valign))
                elif align == "right":
                    item.setTextAlignment(int(Qt.AlignRight | valign))
                else:
                    item.setTextAlignment(int(Qt.AlignLeft | valign))

        self.table.verticalHeader().setDefaultSectionSize(max(20, int(max_size * 2.25)))
        # Les champs à préfixe/suffixe sont peints par un QLabel posé sur la
        # cellule : l'alignement du QTableWidgetItem ne déplace pas ce widget.
        for row in range(self.table.rowCount()):
            for col in range(self.table.columnCount()):
                widget = self.table.cellWidget(row, col)
                item = self.table.item(row, col)
                if isinstance(widget, QLabel) and item is not None:
                    widget.setAlignment(Qt.AlignmentFlag(item.textAlignment()))

    def _print(self):
        # 1.0.102 : impression directe = même composition que l'aperçu.
        from PySide6.QtCore import QRect

        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        try:
            printer.setDocName(self.report_title or "État résumé")
        except Exception:
            pass

        dialog = QPrintDialog(printer, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        table_w = max(
            1,
            int(sum(self.table.columnWidth(c) for c in range(self.table.columnCount()))
                + self.table.frameWidth() * 2)
        )
        table_w = min(table_w, self.table.width())
        table_h = max(
            1,
            int(self.table.horizontalHeader().height()
                + sum(self.table.rowHeight(r) for r in range(self.table.rowCount()))
                + self.table.frameWidth() * 2)
        )
        table_h = min(table_h, self.table.height())

        pieces = []
        # 1.0.107 — certains filets horizontaux doivent respecter la marge
        # physique de la feuille, et pas seulement la largeur de la zone
        # imprimable. On mémorise donc ceux du bandeau et du pied pour pouvoir
        # corriger leur extrémité droite au moment du dessin.
        symmetric_sheet_mark_keys = set()

        def add_widget(widget):
            if widget is not None and widget.isVisible():
                pix = widget.grab()
                if not pix.isNull():
                    pieces.append(pix)

        def add_marks(position):
            for widget in getattr(self, "_print_summary_marks", {}).get(position, []):
                if widget is None or not widget.isVisible():
                    continue
                pix = widget.grab()
                if pix.isNull():
                    continue

                # 1.0.104 — filets haut/bas : retrait droit symétrique
                # au retrait gauche. Les filets inter-données restent intacts.
                if pix.width() > 2:
                    left_margin = max(0, int(widget.x()))
                    if left_margin > 0 and pix.width() > left_margin:
                        pix = pix.copy(
                            0, 0,
                            max(1, pix.width() - left_margin),
                            pix.height()
                        )
                # 1.0.109 — tous les filets horizontaux pleine largeur du
                # résumé doivent partager exactement la même limite droite.
                # En 1.0.108 seuls le gros filet du bandeau et les filets bas
                # recevaient le retrait d'impression ; le filet sous le titre
                # et le filet fin avant les en-têtes restaient plus longs.
                if position in {
                    "after_title", "after_band", "after_header",
                    "before_footer_line", "before_footer",
                }:
                    symmetric_sheet_mark_keys.add(int(pix.cacheKey()))
                pieces.append(pix)

        add_widget(getattr(self, "preview_heading", None))
        add_marks("after_title")
        add_widget(getattr(self, "_print_summary_top_totals", None))
        add_marks("after_band")
        add_marks("after_header")

        table_pix = self.table.grab(QRect(0, 0, table_w, table_h))
        if not table_pix.isNull():
            pieces.append(table_pix)

        # Les marques basses sont avant le pied de totaux, exactement comme
        # dans le constructeur et dans l'aperçu.
        add_marks("before_footer_line")
        add_marks("before_footer")
        add_widget(getattr(self, "_print_summary_bottom_totals", None))

        # 1.0.117 — la pagination n'appartient plus au flux vertical de l'état.
        # Elle est capturée séparément puis dessinée au bas de la zone imprimable,
        # comme un véritable pied de page papier (Word, Writer, etc.).
        page_footer_pix = None
        _page_footer_widget = getattr(self, "_print_summary_page_footer", None)
        if _page_footer_widget is not None and _page_footer_widget.isVisible():
            _pix = _page_footer_widget.grab()
            if not _pix.isNull():
                page_footer_pix = _pix

        if not pieces and page_footer_pix is None:
            return

        painter = QPainter(printer)
        if not painter.isActive():
            return
        try:
            page = printer.pageRect(QPrinter.Unit.DevicePixel)
            paper = printer.paperRect(QPrinter.Unit.DevicePixel)
            max_w = max(1, int(page.width()))
            max_h = max(1, int(page.height()))
            _all_widths = [p.width() for p in pieces]
            if page_footer_pix is not None:
                _all_widths.append(page_footer_pix.width())
            natural_w = max(_all_widths or [1])
            natural_h = sum(p.height() for p in pieces)
            footer_h_natural = page_footer_pix.height() if page_footer_pix is not None else 0
            # 1.0.120 — vraie réserve papier pour la pagination. Cette méthode
            # est le chemin réellement exécuté par le bouton Imprimer de
            # l'Aperçu résumé. La réserve est calculée en pixels physiques à
            # partir de la résolution du périphérique (PDF ou imprimante).
            _dpi = max(72, int(printer.resolution() or 300))
            _mm_px = float(_dpi) / 25.4
            _footer_bottom_margin_px = max(1, int(round(10.0 * _mm_px)))
            _footer_reserved_px = max(footer_h_natural, int(round(18.0 * _mm_px)))
            _content_max_h = max(1, max_h - _footer_reserved_px)
            scale = min(
                float(max_w) / max(1, natural_w),
                float(_content_max_h) / max(1, natural_h),
            )
            x = int(page.x())
            y = int(page.y())

            # La zone imprimable d'un pilote PDF/imprimante peut être légèrement
            # décentrée dans la feuille. Pour les filets du bandeau et du pied,
            # on compense uniquement l'éventuel manque de marge à droite afin
            # d'obtenir visuellement la même marge de feuille qu'à gauche.
            sheet_left = max(0, int(round(page.x() - paper.x())))
            sheet_right = max(0, int(round(
                (paper.x() + paper.width()) - (page.x() + page.width())
            )))
            # 1.0.108 — les filets du bandeau et du pied doivent laisser à
            # droite une marge visuelle réellement identique à celle de gauche.
            # La correction 1.0.107 ne compensait que le décentrage physique du
            # pilote, ce qui restait trop faible. On ajoute donc, pour ces seuls
            # filets, un retrait droit égal à la marge gauche de la zone
            # imprimable. Ainsi le résultat reste nettement symétrique en PDF
            # comme sur une imprimante, sans modifier les autres éléments.
            right_sheet_correction = max(0, sheet_left - sheet_right)
            symmetric_right_inset = max(0, sheet_left)

            for pix in pieces:
                w = max(1, int(round(pix.width() * scale)))
                h = max(1, int(round(pix.height() * scale)))
                if int(pix.cacheKey()) in symmetric_sheet_mark_keys:
                    w = max(1, w - right_sheet_correction - symmetric_right_inset)
                painter.drawPixmap(QRect(x, y, w, h), pix)
                y += h

            # Pagination ancrée physiquement en bas de la page imprimable.
            # Sa position verticale ne dépend donc plus de la hauteur du tableau
            # ni du pied de totaux. L'alignement gauche/centre/droite reste celui
            # déjà rendu dans le widget de pagination.
            if page_footer_pix is not None:
                fw = max(1, int(round(page_footer_pix.width() * scale)))
                fh = max(1, int(round(page_footer_pix.height() * scale)))
                # 1.0.120 — 10 mm de marge de sécurité sous le numéro.
                # Contrairement aux essais 1.0.118/119, ce calcul est placé
                # directement dans SummaryPreviewDialog._print(), juste avant
                # le drawPixmap effectivement envoyé au périphérique.
                fy = int(page.y() + page.height() - _footer_bottom_margin_px - fh)
                painter.drawPixmap(QRect(x, fy, fw, fh), page_footer_pix)
        finally:
            painter.end()


class ReportWindow(QMainWindow):
    """Centre des États MM3, accessible directement depuis l'accueil."""

    def __init__(self, startup, collection: dict, parent=None) -> None:
        super().__init__(parent)
        self.main_window = parent
        self.startup = startup
        self.language = getattr(startup.settings, "language", "fr") or "fr"
        self.collection = dict(collection)
        self.manager = RecordManager(self.startup.database.database_path)
        self.model_manager = ModelManager(self.startup.database.database_path)
        self._custom_field_defs = self.model_manager.custom_field_map(
            int(self.collection["id"])
        )
        self.fields = self._collection_fields()
        self.labels = {field: label for label, field in self.fields}
        self.records = self._merge_custom_values(
            self.manager.list_records(int(self.collection["id"]))
        )
        self.saved_queries = self._load_saved_queries()
        self.saved_reports = self._load_saved_reports()
        self.report_order_mode, self.report_custom_order = self._load_report_order_settings()
        self._load_custom_color_palette()
        self.current_edit_report_name: str | None = None
        self._last_html = ""
        self._last_title = "État"
        self._last_landscape = False
        self._detail_preview = None
        self.editor_context = False

        self.setWindowTitle(f"{tr('États', self.language)} — {collection_display_name(self.collection, self.language)}")
        # Taille initiale compacte : l'ancien constructeur occupait presque tout
        # l'écran. Le nouveau constructeur graphique n'en a plus besoin.
        self.resize(1100, 650)
        self.setMinimumSize(850, 600)
        self._build_ui()
        translate_widget_tree(self, self.language)
        self._apply_style()

    def _fit_builder_window(self) -> None:
        """Ouvre le constructeur sur une surface utile, adaptée à l'écran."""
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            self.resize(1100, 650)
            return
        available = screen.availableGeometry()
        # Surface de travail du nouveau constructeur : compacte sur grand écran,
        # mais toujours bornée par l'espace réellement disponible sur portable.
        width = min(1100, max(850, available.width() - 80))
        height = min(650, max(600, available.height() - 80))
        self.resize(width, height)

    def _collection_fields(self) -> tuple[tuple[str, str], ...]:
        """Champs d'état issus du modèle réel de la collection."""
        cid = int(self.collection["id"])
        visible = set(self.model_manager.visible_fields(cid))
        custom_labels = self.model_manager.custom_labels(cid)
        native_labels = {field: label for label, field in REPORT_COLUMNS}
        ordered = self.model_manager.tab_order(cid, list(visible))

        result: list[tuple[str, str]] = []
        seen: set[str] = set()
        for key in ordered:
            key = str(key)
            if key in seen or key == "photo_data" or key not in visible:
                continue
            seen.add(key)
            custom = self._custom_field_defs.get(key)
            if custom is not None:
                label = (
                    str(custom_labels.get(key) or "").strip()
                    or str(custom.get("label") or "").strip()
                    or key
                )
            else:
                spec = FIELD_BY_KEY.get(key)
                label = (
                    str(custom_labels.get(key) or "").strip()
                    or native_labels.get(key)
                    or (str(spec.label) if spec is not None else key)
                )
            if str(label).strip() == "Coût total":
                label = tr("Coût total", self.language)
            result.append((tr(str(label), self.language), key))

        # Un seul « État de la fiche » dans l'Atelier État : si une ancienne
        # collection importée contient un champ personnalisé homonyme, on conserve
        # uniquement le vrai champ système record_state.
        if any(str(key) == "record_state" for _label, key in result):
            result = [
                (label, key) for label, key in result
                if str(key) == "record_state" or not _mm3_is_record_state_label(label)
            ]
        # Les anciens imports peuvent contenir des champs personnalisés « N° ».
        # Garder le numéro système une seule fois dans la palette des États.
        if any(key == "record_number" for _label, key in result):
            result = [
                (label, key) for label, key in result
                if key == "record_number" or str(label).strip().casefold() not in {"n°", "nº"}
            ]
        return tuple(result)

    def _merge_custom_values(self, records: list[dict]) -> list[dict]:
        if not records or not self._custom_field_defs:
            return [dict(record) for record in records]
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

    def _load_saved_queries(self) -> dict[str, dict]:
        entry = load_collection_models(self.startup.database.database_path, self.collection["id"], "requete", self.startup.workspace.settings_path / "saved_queries.json")
        queries = entry.get("queries", {})
        return queries if isinstance(queries, dict) else {}

    def _custom_colors_path(self) -> Path:
        return self.startup.workspace.settings_path / "custom_colors.json"

    def _load_custom_color_palette(self) -> None:
        try:
            data=json.loads(self._custom_colors_path().read_text(encoding="utf-8"))
            colors=data.get("colors",[])
        except (OSError,ValueError,TypeError):
            colors=[]
        if isinstance(colors,list):
            for index,value in enumerate(colors[:QColorDialog.customCount()]):
                color=QColor(str(value))
                if color.isValid():
                    QColorDialog.setCustomColor(index,color)

    def _save_custom_color_palette(self) -> None:
        colors=[]
        for index in range(QColorDialog.customCount()):
            color=QColorDialog.customColor(index)
            colors.append(color.name() if color.isValid() else "")
        path=self._custom_colors_path()
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps({"colors":colors},ensure_ascii=False,indent=2),encoding="utf-8")

    def _delete_custom_color(self, dialog) -> None:
        """Supprime la couleur personnalisée correspondant à la couleur courante."""
        current=dialog.currentColor()
        target=-1
        for index in range(QColorDialog.customCount()):
            if QColorDialog.customColor(index).name().lower()==current.name().lower():
                target=index
                break
        if target < 0:
            QMessageBox.information(
                dialog,"Couleur personnalisée",
                "Sélectionnez d’abord une couleur personnalisée à supprimer."
            )
            return
        # QColorDialog représente une case libre par du blanc.
        QColorDialog.setCustomColor(target,QColor("#ffffff"))
        self._save_custom_color_palette()
        QMessageBox.information(dialog,"Couleur personnalisée","La couleur personnalisée a été supprimée.")

    def _reports_path(self) -> Path:
        return self.startup.workspace.settings_path / "saved_reports.json"

    def _report_entry(self) -> dict:
        return load_collection_models(self.startup.database.database_path, self.collection["id"], "etat", self._reports_path())

    def _load_saved_reports(self) -> dict[str, dict]:
        reports = self._report_entry().get("reports", {})
        return reports if isinstance(reports, dict) else {}

    def _load_report_order_settings(self) -> tuple[str, list[str]]:
        block = self._report_entry()
        custom = block.get("custom_order") or []
        return str(block.get("order_mode") or "alpha"), [str(x) for x in custom] if isinstance(custom, list) else []

    def _write_report_order_settings(self) -> None:
        block = self._report_entry()
        block["order_mode"] = self.report_order_mode
        block["custom_order"] = list(self.report_custom_order)
        save_collection_models(self.startup.database.database_path, self.collection["id"], "etat", block)

    def _write_saved_reports(self) -> None:
        block = self._report_entry()
        block["reports"] = self.saved_reports
        save_collection_models(self.startup.database.database_path, self.collection["id"], "etat", block)

    def open_report_from_library(self) -> bool:
        root = library_root(self.startup.workspace.settings_path.parent, "etat")
        filename = choose_model_open_path(self, root, "Modèles d’États")
        if not filename: return False
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        QApplication.processEvents()
        try:
            envelope = read_model(filename, expected_kind="etat")
            definition = resolve_model_fields(self, envelope, self.model_manager, int(self.collection["id"]), "etat")
            if definition is None:
                return False
            self._custom_field_defs = self.model_manager.custom_field_map(int(self.collection["id"]))
            temp_name = Path(filename).stem
            previous = self.saved_reports.get(temp_name, None)
            had_previous = temp_name in self.saved_reports
            self.saved_reports[temp_name] = definition
            self._load_report_into_builder(temp_name)
            if had_previous: self.saved_reports[temp_name] = previous
            else: self.saved_reports.pop(temp_name, None)
            kind = str(definition.get("kind", "detail")); page = self.stack.widget(1 if kind == "detail" else 2)
            page.editing_report_name = temp_name
            self.current_edit_report_name = temp_name
            self._refresh_builder_banner(page, kind)
            self._reset_builder_state(page)
        except Exception as exc:
            QMessageBox.critical(self, "Ouverture impossible", str(exc)); return False
        finally:
            QApplication.restoreOverrideCursor()
        return True

    def _write_report_model_to_library(self, definition: dict, default_name: str) -> str | None:
        root = library_root(self.startup.workspace.settings_path.parent, "etat")
        filename = choose_model_save_path(self, root, default_name or "Modèle d’État", "Modèles d’États")
        if not filename:
            return None
        try:
            manifest = build_field_manifest(self.model_manager, int(self.collection["id"]), collect_model_field_keys("etat", definition))
            write_model(
                filename, kind="etat", name=Path(filename).stem,
                source_collection=str(self.collection.get("name") or ""), payload=definition, field_manifest=manifest,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Enregistrement impossible", str(exc))
            return False
        QMessageBox.information(self, "Modèle d’État", "Le modèle a été enregistré dans la bibliothèque Modèles d’États.")
        return Path(filename).stem

    def _save_report_builder_to_library(self, kind: str, page) -> bool:
        """Enregistre un état directement comme modèle, sans sauvegarde préalable dans la collection."""
        definition = self._definition_from_builder(kind, page)
        if kind == "detail" and not definition.get("fields"):
            QMessageBox.information(self, "Aucun champ", "Choisissez au moins un champ avant d’enregistrer le modèle d’État.")
            return False
        default_name = str(getattr(page, "editing_report_name", "") or page.title_widget.text() or "Modèle d’État").strip()
        if default_name in {"État détaillé", "État résumé", "État"}:
            default_name = "Modèle d’État"
        saved_name = self._write_report_model_to_library(definition, default_name)
        if saved_name:
            # Le nom réellement choisi dans la bibliothèque devient le nom actif affiché.
            # Il ne crée pas pour autant un état enregistré dans la collection.
            page.editing_report_name = saved_name
            self.current_edit_report_name = saved_name
            self._refresh_builder_banner(page, kind)
            # « Enregistrer sous… » est une vraie alternative à « Sauvegarder » :
            # en quittant ensuite l'Atelier, MM3 ne redemande pas une seconde sauvegarde.
            self._reset_builder_state(page)
        return bool(saved_name)

    def save_report_to_library(self, report_name, builder_page=None) -> bool:
        # Depuis un aperçu, utiliser en priorité l'état actuellement construit, même s'il
        # n'a jamais été sauvegardé dans la collection.
        if builder_page is not None:
            kind = str(builder_page.property("kind") or "")
            if kind in {"detail", "summary"}:
                return self._save_report_builder_to_library(kind, builder_page)

        name = str(report_name or "").strip()
        if not name or name not in self.saved_reports:
            QMessageBox.information(self, "Modèle d’État", "Aucun état exploitable n’est disponible pour cet enregistrement.")
            return False
        definition = self.saved_reports.get(name)
        if not isinstance(definition, dict):
            return False
        return self._write_report_model_to_library(definition, name)

    @staticmethod
    def _folder_identity(path):
        """Identité d'un dossier indépendante des accents et de la casse."""
        return "/".join("".join(c for c in unicodedata.normalize("NFKD", part.casefold())
                                if not unicodedata.combining(c))
                        for part in model_folders.normalize(path).split("/"))

    def _choose_report_folder(self, kind, existing_name=None):
        """Choix des dossiers d'états, propre au type et entièrement en français."""
        db = self.startup.database.database_path
        cid = int(self.collection["id"])
        preferred = "États résumés" if kind == "summary" else "États détaillés"
        other = "États détaillés" if kind == "summary" else "États résumés"
        def canonical(path):
            return "".join(c for c in unicodedata.normalize("NFKD", str(path or "").strip().casefold())
                           if not unicodedata.combining(c))
        def allowed(path):
            text = canonical(path)
            blocked = canonical(other)
            return text != blocked and not text.startswith(blocked + "/")
        current = self._report_folder(existing_name) if existing_name in self.saved_reports else ""
        if not allowed(current):
            current = ""
        existing_paths = model_folders.folders(db, cid, "etat")
        # Anciens dossiers génériques : leurs états sont affichés directement
        # sous la racine du type, sans modifier les sauvegardes existantes.
        choices = [tr("(États résumés)", self.language) if kind == "summary" else tr("(États détaillés)", self.language)]
        identities = set()
        # Le dossier qui contient déjà l'état reste la valeur proposée.
        for path in ([current] if current else []) + existing_paths:
            identity = self._folder_identity(path)
            if identity == self._folder_identity(preferred):
                continue
            if allowed(path) and identity not in identities:
                choices.append(path)
                identities.add(identity)
        choices.append(tr("+ Nouveau dossier ou sous-dossier…", self.language))
        dlg = QDialog(self)
        dlg.setWindowTitle(tr("Dossier de l’état résumé", self.language) if kind == "summary" else tr("Dossier de l’état détaillé", self.language))
        form = QVBoxLayout(dlg)
        form.addWidget(QLabel(tr("Enregistrer dans :", self.language)))
        combo = QComboBox()
        combo.addItems(choices)
        combo.setMinimumWidth(300)
        combo.setCurrentIndex(choices.index(current) if current in choices else 0)
        form.addWidget(combo)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(tr("Enregistrer", self.language))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("Annuler", self.language))
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        form.addWidget(buttons)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return None
        selection = combo.currentText()
        if selection == choices[0]:
            return ""
        if selection != choices[-1]:
            return selection if allowed(selection) else None

        new_dlg = QDialog(self)
        new_dlg.setWindowTitle("Nouveau dossier")
        new_form = QVBoxLayout(new_dlg)
        new_form.addWidget(QLabel("Chemin du dossier (ex. Région / Année) :"))
        name_edit = QLineEdit()
        name_edit.setMinimumWidth(300)
        new_form.addWidget(name_edit)
        new_buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        new_buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Créer")
        new_buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("Annuler", self.language))
        new_buttons.accepted.connect(new_dlg.accept)
        new_buttons.rejected.connect(new_dlg.reject)
        new_form.addWidget(new_buttons)
        if new_dlg.exec() != QDialog.DialogCode.Accepted:
            return None
        try:
            folder = model_folders.normalize(name_edit.text())
            if not folder:
                raise ValueError("Saisissez un nom de dossier.")
            if not allowed(folder):
                raise ValueError("Ce dossier est réservé à l’autre type d’état.")
            model_folders.create_folder(db, cid, "etat", folder)
        except ValueError as exc:
            QMessageBox.warning(self, "Dossier invalide", str(exc))
            return None
        return folder

    def save_report_definition(self, *, kind, title, source_name, landscape,
                               layout_state, existing_name=None, fields=None,
                               group_field=None, date_group_mode="full_date",
                               second_group_field=None, show_details=False,
                               detail_groupings=None, atelier_style=None,
                               summary_field_color="#9A3324", summary_field_bold=True,
                               builder_page=None):
        default = existing_name or title or "Nouvel état"
        _name_dialog = QInputDialog(self)
        _name_dialog.setWindowTitle(tr("Enregistrer l’état", self.language))
        _name_dialog.setLabelText(tr("Nom de l’état :", self.language))
        _name_dialog.setTextValue(default)
        _name_dialog.setOkButtonText("OK")
        _name_dialog.setCancelButtonText(tr("Annuler", self.language))
        _name_dialog.setTextEchoMode(QLineEdit.EchoMode.Normal)
        _line = _name_dialog.findChild(QLineEdit)
        if _line is not None:
            _line.selectAll()
        ok = _name_dialog.exec() == QDialog.DialogCode.Accepted
        name = _name_dialog.textValue().strip()
        if not ok or not name:
            return None
        if name != existing_name and name in self.saved_reports:
            answer = QMessageBox.question(
                self, "État existant",
                f"Un état nommé « {name} » existe déjà. Le remplacer ?"
            )
            if answer != QMessageBox.StandardButton.Yes:
                return None
        original_name = existing_name if existing_name in self.saved_reports else name
        folder = self._choose_report_folder(kind, original_name)
        if folder is None:
            return None
        # L'aperçu ne contient qu'une partie des réglages du constructeur.
        # Partir de la définition complète évite de perdre les champs liés,
        # les totaux, le bandeau et la mise en forme lors d'une sauvegarde ici.
        if builder_page is not None:
            definition = self._definition_from_builder(kind, builder_page)
        else:
            definition = json.loads(json.dumps(self.saved_reports.get(existing_name, {})))
        definition.update({
            "kind": kind,
            "title": title,
            "source_name": source_name,
            "landscape": bool(landscape),
            "layout": layout_state,
        })
        if kind == "detail":
            if fields is not None:
                definition["fields"] = list(fields)
            if detail_groupings is not None:
                definition["detail_groupings"] = list(detail_groupings)
            if atelier_style is not None:
                definition["atelier_style"] = dict(atelier_style)
        else:
            definition["group_field"] = group_field
            definition["date_group_mode"] = date_group_mode
            definition["second_group_field"] = second_group_field
            definition["show_details"] = bool(show_details)
            definition["summary_field_color"] = str(summary_field_color or "#9A3324")
            definition["summary_field_bold"] = bool(summary_field_bold)
            # Sécurité des anciens modèles partiels : le champ maître doit
            # toujours former au moins la première colonne du résumé.
            if not definition.get("summary_fields") and group_field:
                definition["summary_fields"] = [group_field]
        if existing_name and existing_name != name:
            self.saved_reports.pop(existing_name, None)
            model_folders.rename_item(self.startup.database.database_path,
                                      int(self.collection["id"]), "etat", existing_name, name)
        self.saved_reports[name] = definition
        model_folders.assign(self.startup.database.database_path,
                             int(self.collection["id"]), "etat", name, folder)
        if name not in self.report_custom_order:
            self.report_custom_order.append(name)
        self._write_saved_reports()
        self._write_report_order_settings()
        self._refresh_saved_reports_list()
        QMessageBox.information(self, "État enregistré", f"« {name} » est enregistré.")
        return name

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        # Mode portable : aucune grande réserve décorative en haut.
        layout.setContentsMargins(18, 4, 18, 6)
        layout.setSpacing(2)

        title = QLabel(tr("États", self.language))
        title.setObjectName("reportTitle")
        self.report_page_title = title
        subtitle = QLabel(tr(
            "Créer et consulter les présentations de la collection : détail des fiches ou synthèse par regroupement.",
            self.language
        ))
        self.report_page_subtitle = subtitle
        subtitle.setWordWrap(True)
        subtitle.setObjectName("reportSubtitle")
        title_line = QHBoxLayout()
        title_line.setContentsMargins(0, 0, 0, 0)
        title_line.setSpacing(5)
        title_line.addWidget(title)
        title_line.addWidget(subtitle, 1)
        layout.addLayout(title_line)

        self.stack = QStackedWidget()
        self.stack.setContentsMargins(0, 0, 0, 0)
        self.stack.addWidget(self._build_home())
        self.stack.addWidget(self._build_builder("detail"))
        self.stack.addWidget(self._build_builder("summary"))
        layout.addWidget(self.stack, 1)

        self.setCentralWidget(root)

    def open_consultation_home(self) -> None:
        """Mode Collection : choisir, ouvrir et consulter les états."""
        self.editor_context = False
        self.saved_reports = self._load_saved_reports()
        self._refresh_saved_reports_list()
        self.stack.setCurrentIndex(0)
        self.report_page_subtitle.setVisible(True)
        self.report_page_title.setText(tr("États", self.language))
        self.report_page_subtitle.setText(tr(
            "Consulter les états enregistrés ou créer une présentation détaillée ou résumée de la collection.",
            self.language
        ))
        self.report_home_intro.setText(tr("Quel type d’état souhaitez-vous créer ?", self.language))
        self.saved_reports_box.setTitle(tr("États enregistrés", self.language))
        self.setWindowTitle(f"{tr('États', self.language)} — {collection_display_name(self.collection, self.language)}")

    def open_workshop_editor(self) -> None:
        """Mode Atelier : concevoir et personnaliser les états existants."""
        self.editor_context = True
        self.saved_reports = self._load_saved_reports()
        self._refresh_saved_reports_list()
        self.stack.setCurrentIndex(0)
        self.report_page_subtitle.setVisible(True)
        self.report_page_title.setText(tr("Éditeur d’états", self.language))
        self.report_page_subtitle.setText(tr(
            "Atelier de conception avancée : choisissez un état existant puis ouvrez-le avec Modifier pour accéder aux réglages fins.", self.language
        ))
        self.report_home_intro.setText(tr(
            "Choisissez un état enregistré. Le double-clic ouvre directement son éditeur avancé.", self.language
        ))
        self.saved_reports_box.setTitle(tr("États disponibles dans l’éditeur", self.language))
        self.setWindowTitle(
            f"{tr('Éditeur d’états', self.language)} — {collection_display_name(self.collection, self.language)}"
        )

    def _build_home(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setSpacing(16)

        intro = QLabel(tr("Quel type d’état souhaitez-vous créer ?", self.language))
        intro.setObjectName("sectionTitle")
        self.report_home_intro = intro
        lay.addWidget(intro)

        cards = QGridLayout()
        detail = self._type_card(
            tr("État détaillé", self.language),
            tr("Afficher les fiches une par une, avec les champs choisis.", self.language),
            lambda: self._open_builder(1),
        )
        summary = self._type_card(
            tr("État résumé", self.language),
            tr("Regrouper les fiches et afficher uniquement les totaux ou synthèses.", self.language),
            lambda: self._open_builder(2),
        )
        cards.addWidget(detail, 0, 0)
        cards.addWidget(summary, 0, 1)
        cards.setColumnStretch(0, 1)
        cards.setColumnStretch(1, 1)
        lay.addLayout(cards)

        saved_box = QGroupBox(tr("États enregistrés", self.language))
        self.saved_reports_box = saved_box
        saved_lay = QVBoxLayout(saved_box)
        saved_lay.setContentsMargins(8, 8, 8, 8)
        saved_lay.setSpacing(6)

        lists_row = QHBoxLayout()
        lists_row.setContentsMargins(0, 0, 0, 0)
        lists_row.setSpacing(0)

        self.saved_detail_reports_list = QTreeWidget()
        self.saved_summary_reports_list = QTreeWidget()
        for tree in (self.saved_detail_reports_list, self.saved_summary_reports_list):
            tree.setHeaderHidden(True)
            tree.setIndentation(19)
        # Alias conservé pour compatibilité avec le reste du code.
        self.saved_reports_list = self.saved_detail_reports_list

        for widget in (
            self.saved_detail_reports_list,
            self.saved_summary_reports_list,
        ):
            widget.itemDoubleClicked.connect(
                lambda *_: (
                    self._modify_selected_report()
                    if self.editor_context
                    else self._open_selected_report()
                )
            )

        self.saved_detail_reports_list.itemSelectionChanged.connect(
            lambda: self._exclusive_report_selection("detail")
        )
        self.saved_summary_reports_list.itemSelectionChanged.connect(
            lambda: self._exclusive_report_selection("summary")
        )

        separator = QFrame()
        separator.setFixedWidth(22)
        separator.setStyleSheet(
            "QFrame { background-color: #eaf2ee; "
            "border-left: 1px solid #c6d4ce; "
            "border-right: 1px solid #c6d4ce; }"
        )

        lists_row.addWidget(self.saved_detail_reports_list, 1)
        lists_row.addWidget(separator, 0)
        lists_row.addWidget(self.saved_summary_reports_list, 1)
        saved_lay.addLayout(lists_row, 1)

        buttons = QHBoxLayout()
        open_btn = QPushButton(tr("Ouvrir", self.language))
        open_btn.setToolTip(tr("Consulter l’état sélectionné", self.language))
        modify_btn = QPushButton(tr("Modifier", self.language))
        modify_btn.setToolTip(tr("Ouvrir l’état sélectionné dans son constructeur", self.language))
        rename_btn = QPushButton(tr("Renommer", self.language))
        duplicate_btn = QPushButton(tr("Dupliquer", self.language))
        delete_btn = QPushButton(tr("Supprimer", self.language))
        open_btn.clicked.connect(self._open_selected_report)
        modify_btn.clicked.connect(self._modify_selected_report)
        rename_btn.clicked.connect(self._rename_selected_report)
        duplicate_btn.clicked.connect(self._duplicate_selected_report)
        delete_btn.clicked.connect(self._delete_selected_report)
        open_model_btn = QPushButton(tr("Ouvrir un modèle d’État…", self.language))
        open_model_btn.setToolTip(tr("Charger un modèle depuis la bibliothèque Modèles d’États", self.language))
        open_model_btn.clicked.connect(self.open_report_from_library)
        buttons.addWidget(open_btn)
        buttons.addWidget(open_model_btn)
        buttons.addWidget(modify_btn)
        buttons.addWidget(rename_btn)
        buttons.addWidget(duplicate_btn)
        buttons.addWidget(delete_btn)
        folder_btn = QPushButton(tr("Dossiers…", self.language))
        folder_btn.clicked.connect(self._manage_saved_report_folders)
        buttons.addWidget(folder_btn)
        buttons.addStretch(1)
        saved_lay.addLayout(buttons)

        lay.addWidget(saved_box, 1)
        self._refresh_saved_reports_list()
        return page

    def _manage_saved_report_folders(self) -> None:
        manage_folders(self, self.startup.database.database_path, int(self.collection["id"]),
                       "etat", self.saved_reports, self._refresh_saved_reports_list)

    def _report_folder(self, name: str) -> str:
        folder = model_folders.folder_for(self.startup.database.database_path,
                                          int(self.collection["id"]), "etat", name)
        kind = str((self.saved_reports.get(name) or {}).get("kind") or "")
        generic = "États résumés" if kind == "summary" else "États détaillés" if kind == "detail" else ""
        return "" if generic and self._folder_identity(folder) == self._folder_identity(generic) else folder

    def _exclusive_report_selection(self, source: str) -> None:
        """Une seule des deux listes d'états peut porter la sélection."""
        if getattr(self, "_syncing_report_selection", False):
            return
        self._syncing_report_selection = True
        try:
            if source == "detail":
                current = self.saved_detail_reports_list.currentItem()
                if current is not None and current.isSelected():
                    self.saved_summary_reports_list.clearSelection()
                    self.saved_summary_reports_list.setCurrentItem(None)
                    self.saved_reports_list = self.saved_detail_reports_list
            else:
                current = self.saved_summary_reports_list.currentItem()
                if current is not None and current.isSelected():
                    self.saved_detail_reports_list.clearSelection()
                    self.saved_detail_reports_list.setCurrentItem(None)
                    self.saved_reports_list = self.saved_summary_reports_list
        finally:
            self._syncing_report_selection = False

    def _ordered_report_names(self) -> list[str]:
        names = list(self.saved_reports)
        mode = self.report_order_mode

        if mode == "alpha_desc":
            return sorted(names, key=str.casefold, reverse=True)

        if mode in {"detail_summary", "summary_detail"}:
            first_kind = "detail" if mode == "detail_summary" else "summary"
            second_kind = "summary" if first_kind == "detail" else "detail"
            first = sorted(
                [n for n in names if self.saved_reports.get(n, {}).get("kind") == first_kind],
                key=str.casefold,
            )
            second = sorted(
                [n for n in names if self.saved_reports.get(n, {}).get("kind") == second_kind],
                key=str.casefold,
            )
            other = sorted(
                [
                    n for n in names
                    if self.saved_reports.get(n, {}).get("kind") not in {first_kind, second_kind}
                ],
                key=str.casefold,
            )
            return first + second + other

        if mode == "custom":
            # Keep valid saved positions; append newly created states at the end.
            ordered = [n for n in self.report_custom_order if n in self.saved_reports]
            ordered.extend(n for n in names if n not in ordered)
            self.report_custom_order = ordered
            return ordered

        return sorted(names, key=str.casefold)

    @staticmethod
    def _tree_report_names(tree) -> list[str]:
        names = []
        def visit(node):
            name = node.data(0, Qt.ItemDataRole.UserRole)
            if name:
                names.append(str(name))
            for i in range(node.childCount()):
                visit(node.child(i))
        for i in range(tree.topLevelItemCount()):
            visit(tree.topLevelItem(i))
        return names

    def _refresh_saved_reports_list(self) -> None:
        detail_widget = getattr(self, "saved_detail_reports_list", None)
        summary_widget = getattr(self, "saved_summary_reports_list", None)
        if detail_widget is None or summary_widget is None:
            return
        selected = self._selected_report_name()
        for widget, kind, suffix in ((detail_widget, "detail", "DÉTAIL"),
                                     (summary_widget, "summary", "RÉSUMÉ")):
            expanded = set()
            def remember(node):
                path = node.data(0, Qt.ItemDataRole.UserRole + 1)
                if path is not None and node.isExpanded():
                    expanded.add(str(path))
                for i in range(node.childCount()): remember(node.child(i))
            for i in range(widget.topLevelItemCount()): remember(widget.topLevelItem(i))
            widget.blockSignals(True)
            widget.clear()
            root_label = tr("États détaillés", self.language) if kind == "detail" else tr("États résumés", self.language)
            root = QTreeWidgetItem(widget, [f"📁 {root_label}"])
            root.setData(0, Qt.ItemDataRole.UserRole + 1, "")
            root.setExpanded(True)
            nodes = {"": root}
            paths = set()
            names = sorted((name for name, definition in self.saved_reports.items()
                            if definition.get("kind") == kind), key=str.casefold)
            for name in names:
                folder = self._report_folder(name)
                while folder:
                    paths.add(folder)
                    folder = folder.rpartition("/")[0]
            canonical_nodes = {"": root}
            for path in sorted(paths, key=lambda x: (x.count("/"), x.casefold())):
                identity = self._folder_identity(path)
                if identity in canonical_nodes:
                    nodes[path] = canonical_nodes[identity]
                    continue
                parent_identity = self._folder_identity(path.rpartition("/")[0])
                parent = canonical_nodes.get(parent_identity, root)
                node = QTreeWidgetItem(parent, ["📁 " + path.rpartition("/")[2]])
                node.setData(0, Qt.ItemDataRole.UserRole + 1, path)
                canonical_nodes[identity] = node
                nodes[path] = node
                node.setExpanded(path in expanded)
            for name in names:
                folder = self._report_folder(name)
                item = QTreeWidgetItem(nodes.get(folder, root), [f"📄 {name}   —   {suffix}"])
                item.setData(0, Qt.ItemDataRole.UserRole, name)
                if name == selected:
                    widget.setCurrentItem(item)
                    parent = item.parent()
                    while parent is not None:
                        parent.setExpanded(True)
                        parent = parent.parent()
            widget.blockSignals(False)

    def _report_order_changed(self) -> None:
        if not hasattr(self, "report_order_combo"):
            return
        self.report_order_mode = str(self.report_order_combo.currentData() or "alpha")
        if self.report_order_mode == "custom":
            self.report_custom_order = (self._tree_report_names(self.saved_detail_reports_list)
                                        + self._tree_report_names(self.saved_summary_reports_list))
        self._write_report_order_settings()
        self._refresh_saved_reports_list()

    def _move_saved_report(self, delta: int) -> None:
        if self.report_order_mode != "custom":
            return
        name = self._selected_report_name()
        names = self._ordered_report_names()
        if name not in names:
            return
        row = names.index(name)
        target = row + delta
        if target < 0 or target >= len(names):
            return
        names[row], names[target] = names[target], names[row]
        self.report_custom_order = names
        self._write_report_order_settings()
        self._refresh_saved_reports_list()

    def _selected_report_name(self):
        for attr in ("saved_detail_reports_list", "saved_summary_reports_list"):
            widget = getattr(self, attr, None)
            if widget is not None:
                item = widget.currentItem()
                if item is not None and item.isSelected():
                    self.saved_reports_list = widget
                    return item.data(0, Qt.ItemDataRole.UserRole)
        return None

    def _open_selected_report(self) -> None:
        """Ouvre un état enregistré avec EXACTEMENT la définition sauvegardée."""
        name = self._selected_report_name()
        if not name:
            return

        definition = self.saved_reports.get(name)
        if not definition:
            return

        records = self._records_for_source(definition.get("source_name"))
        title = definition.get("title") or name
        landscape = bool(definition.get("landscape"))
        layout = definition.get("layout") or {}
        advanced_style = dict(definition.get("advanced_style") or {})
        page_chrome = dict(definition.get("page_chrome") or {})

        if definition.get("kind") == "detail":
            # 27.46 : un état détaillé enregistré s’ouvre dans son constructeur.
            # L’ancien aperçu groupé automatique créait une seconde chaîne de rendu
            # concurrente avec le bouton Aperçu.
            self._load_report_into_builder(name)
            return
            fields = list(
                definition.get("fields")
                or ["record_number", "mineral_name"]
            )
            groupings = self._normalized_detail_groupings(
                definition.get("detail_groupings") or []
            )
            atelier_style = (
                definition.get("atelier_style")
                or self._default_atelier_style()
            )

            repeat_field = atelier_style.get("repeat_master_field")
            if repeat_field:
                fields = [field for field in fields if field != repeat_field]
                fields.insert(0, repeat_field)

            if groupings:
                dlg = GroupedDetailPreviewDialog(
                    self,
                    title,
                    records,
                    fields,
                    groupings,
                    landscape,
                    self,
                    source_name=definition.get("source_name"),
                    saved_name=name,
                    layout_state=layout,
                    atelier_style=atelier_style,
                    advanced_style=advanced_style,
                    page_chrome=page_chrome,
                    detail_column_alignments=dict(
                        definition.get("detail_column_alignments") or {}
                    ),
                    detail_graphic=definition if "detail_secondary_fields" in definition else None,
                )
            else:
                dlg = DetailPreviewDialog(
                    self,
                    title,
                    records,
                    fields,
                    landscape,
                    self,
                    source_name=definition.get("source_name"),
                    saved_name=name,
                    layout_state=layout,
                    advanced_style=advanced_style,
                    page_chrome=page_chrome,
                    atelier_style=atelier_style,
                    detail_column_alignments=dict(
                        definition.get("detail_column_alignments") or {}
                    ),
                )

            self._detail_preview = dlg
            dlg.setModal(False)
            dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
            dlg.destroyed.connect(
                lambda *_: setattr(self, "_detail_preview", None)
            )
            dlg.show()
            dlg.raise_()
            dlg.activateWindow()
            return

        # ÉTAT RÉSUMÉ
        group_field = definition.get("group_field")
        if group_field == "__acquisition_year__":
            group_field = "acquisition_date"

        dlg = SummaryPreviewDialog(
            self,
            title,
            records,
            group_field or "origin",
            landscape,
            self,
            source_name=definition.get("source_name"),
            saved_name=name,
            layout_state=layout,
            date_group_mode=definition.get("date_group_mode") or "full_date",
            second_group_field=definition.get("second_group_field"),
            show_details=bool(definition.get("show_details")),
            field_color=str(
                definition.get("summary_field_color") or "#9A3324"
            ),
            field_bold=bool(
                definition.get("summary_field_bold", True)
            ),
            advanced_style=advanced_style,
            summary_fields=list(definition.get("summary_fields") or []),
            summary_treatments=dict(
                definition.get("summary_treatments") or {}
            ),
            page_chrome=page_chrome,
            summary_header_metrics=dict(
                definition.get("summary_header_metrics") or {}
            ),
            summary_column_alignments=dict(
                definition.get("summary_column_alignments") or {}
            ),
            summary_field_styles=dict(
                definition.get("summary_field_styles") or {}
            ),
        )
        dlg.exec()


    def _set_combo_by_data(self, combo: QComboBox, value) -> None:
        index = combo.findData(value)
        combo.setCurrentIndex(index if index >= 0 else 0)

    def _modify_selected_report(self) -> None:
        """Recharge l’état sélectionné dans son constructeur."""
        name = self._selected_report_name()
        if not name:
            return
        self._load_report_into_builder(name)

    def _load_report_into_builder(self, name: str) -> None:
        """Ouvre directement dans le constructeur l’état désigné par son nom."""
        definition = self.saved_reports.get(name)
        if not isinstance(definition, dict):
            return

        kind = str(definition.get("kind", "detail"))
        page_index = 1 if kind == "detail" else 2
        page = self.stack.widget(page_index)
        self._set_builder_context_visibility(page)
        page._loading_state = True

        self.saved_queries = self._load_saved_queries()
        source = page.source_widget
        source.blockSignals(True)
        source.clear()
        source.addItem(tr("Toute la collection", self.language), None)
        for query_name in sorted(self.saved_queries, key=str.casefold):
            source.addItem(f"{tr('Requête enregistrée :', self.language)} {query_name}", query_name)
        self._set_combo_by_data(source, definition.get("source_name"))
        source.blockSignals(False)

        page.title_widget.setText(str(definition.get("title") or name))
        if bool(definition.get("landscape")):
            page.landscape_widget.setChecked(True)
        else:
            page.portrait_widget.setChecked(True)

        if kind == "detail" and getattr(page, "detail_summary_clone", False) and "detail_secondary_fields" not in definition:
            page._loading_state = False
            QMessageBox.information(self, tr("État détaillé", self.language), tr("Ce modèle utilise l’ancien constructeur détaillé ; sa reprise sera ajoutée ultérieurement.", self.language))
            return
        if kind == "detail" and not getattr(page, "detail_summary_clone", False):
            saved_order = [str(f) for f in (definition.get("fields") or [])]
            selected = set(saved_order)
            widget = page.fields_widget
            if saved_order:
                widget.blockSignals(True)
                for target, field_key in enumerate(saved_order):
                    for position in range(target, widget.count()):
                        if str(widget.item(position).data(Qt.ItemDataRole.UserRole)) == field_key:
                            widget.insertItem(target, widget.takeItem(position))
                            break
                widget.blockSignals(False)
            for i in range(widget.count()):
                item = widget.item(i)
                field = str(item.data(Qt.ItemDataRole.UserRole))
                item.setCheckState(
                    Qt.CheckState.Checked
                    if field in selected
                    else Qt.CheckState.Unchecked
                )

            saved_groupings = list(definition.get("detail_groupings") or [])
            for level, combo in enumerate(page.detail_grouping_widgets):
                value = (
                    saved_groupings[level]
                    if level < len(saved_groupings)
                    else None
                )
                self._set_combo_by_data(combo, value)

            self._apply_atelier_style_to_page(
                page,
                definition.get("atelier_style")
                or self._default_atelier_style(),
            )
            page.detail_column_alignments = dict(
                definition.get("detail_column_alignments") or {}
            )
            if hasattr(page, "detail_alignment_field_widget"):
                combo = page.detail_alignment_field_widget
                combo.blockSignals(True)
                combo.clear()
                for i in range(widget.count()):
                    item = widget.item(i)
                    if item.checkState() == Qt.CheckState.Checked:
                        combo.addItem(
                            item.text(),
                            str(item.data(Qt.ItemDataRole.UserRole)),
                        )
                combo.blockSignals(False)
                if combo.count():
                    combo.setCurrentIndex(0)
                    field = str(combo.currentData())
                    choice = page.detail_alignment_choice_widget
                    pos = choice.findData(
                        page.detail_column_alignments.get(field, "left")
                    )
                    choice.blockSignals(True)
                    choice.setCurrentIndex(pos if pos >= 0 else 0)
                    choice.blockSignals(False)
        else:
            # Restaurer le regroupement enregistré. Le nouvel Atelier graphique
            # et l'ancien moteur interne doivent impérativement partager le même
            # champ maître ; sinon une sauvegarde après réouverture remplace le
            # maître par « Aucun » et l'aperçu agrège tout sur une seule ligne.
            saved_group = ((definition.get("detail_groupings") or [None])[0]
                           if kind == "detail" else definition.get("group_field"))
            if saved_group == "__acquisition_year__":
                saved_group = "acquisition_date"
            self._set_combo_by_data(page.group_widget, saved_group)
            self._set_combo_by_data(page.second_group_widget, definition.get("second_group_field"))
            self._set_combo_by_data(page.date_group_mode_widget, definition.get("date_group_mode") or "full_date")
            page.no_details_widget.setChecked(True)
            selected_summary = set(definition.get("summary_fields") or [])

            # Migration/chargement vers le nouvel Atelier graphique. Les anciens
            # états ne possèdent pas encore de structure graphique dédiée : leur
            # group_field devient le Groupe maître et les autres summary_fields
            # deviennent les Champs liés. Pour les états récents, cela restaure
            # exactement la construction sauvegardée.
            graphic_master = str(saved_group) if saved_group else None
            ordered_saved_fields = ([str(x) for x in (definition.get("detail_secondary_fields") or [])]
                                    if kind == "detail" else
                                    [str(x) for x in (definition.get("summary_fields") or [])])
            if not ordered_saved_fields and kind == "summary":
                # Réparation douce des modèles touchés par la régression 27.49/27.50 :
                # les colonnes peuvent encore être déduites de leur mise en forme enregistrée.
                _hm = dict(definition.get("summary_header_metrics") or {})
                _candidates = []
                if graphic_master:
                    _candidates.append(graphic_master)
                for _mapping in (
                    dict(_hm.get("column_header_labels") or {}),
                    dict(_hm.get("column_header_styles") or {}),
                    dict(definition.get("summary_field_styles") or {}),
                ):
                    for _f in _mapping.keys():
                        _f = str(_f)
                        if _f and _f not in _candidates and _f != "__records__":
                            _candidates.append(_f)
                ordered_saved_fields = _candidates[:5]
            graphic_secondaries = [f for f in ordered_saved_fields if f and (kind == "detail" or f != graphic_master)]
            page.summary_graphic_master = graphic_master
            page.summary_graphic_secondaries = graphic_secondaries[:12 if kind == "detail" else 4]
            widget = getattr(page, "summary_fields_widget", None)
            if widget is not None:
                widget.blockSignals(True)
                for i in range(widget.count()):
                    item = widget.item(i)
                    field = str(item.data(Qt.ItemDataRole.UserRole))
                    pair = getattr(page, "summary_field_row_widgets", {}).get(field)
                    if pair is not None:
                        col_cb, _total_cb = pair
                        col_cb.blockSignals(True)
                        col_cb.setChecked(field in selected_summary)
                        col_cb.blockSignals(False)
                widget.blockSignals(False)
            if hasattr(page, "summary_spacing_widget"):
                page.summary_spacing_widget.setValue(int(definition.get("summary_spacing", 2)))
            page.summary_treatments = dict(definition.get("summary_treatments") or {})
            page.summary_field_styles = dict(definition.get("detail_field_styles") or definition.get("summary_field_styles") or {})
            page.detail_master_styles = dict(definition.get("detail_master_styles") or {})
            page.detail_group_totals = [str(f) for f in (definition.get("detail_group_totals") or [])
                                        if str(f) in self.labels][:6]
            page.detail_total_styles = dict(definition.get("detail_total_styles") or {})
            page.detail_column_labels = dict(definition.get("detail_column_labels") or {})
            page.detail_label_styles = dict(definition.get("detail_label_styles") or {})
            page.detail_column_widths = dict(definition.get("detail_column_widths") or {})
            page.summary_column_alignments = dict(
                definition.get("summary_column_alignments") or {}
            )
            if hasattr(page, "summary_alignment_field_widget"):
                combo = page.summary_alignment_field_widget
                combo.blockSignals(True)
                combo.clear()
                if page.group_widget.currentData() is not None:
                    combo.addItem(page.group_widget.currentText(), "__group__")
                for i in range(widget.count()):
                    item = widget.item(i)
                    field = str(item.data(Qt.ItemDataRole.UserRole))
                    pair = getattr(page, "summary_field_row_widgets", {}).get(field)
                    if pair is not None and pair[0].isChecked():
                        combo.addItem(item.text(), field)
                combo.blockSignals(False)
                if combo.count():
                    combo.setCurrentIndex(0)
                    field = str(combo.currentData())
                    choice = page.summary_alignment_choice_widget
                    pos = choice.findData(page.summary_column_alignments.get(field, "left"))
                    choice.blockSignals(True)
                    choice.setCurrentIndex(pos if pos >= 0 else 0)
                    choice.blockSignals(False)
            header_metrics = dict(definition.get("summary_header_metrics") or {})
            page.summary_metric_fields = set(str(x) for x in (header_metrics.get("selected_fields") or []))
            page.summary_metric_order = [str(x) for x in (header_metrics.get("selected_fields") or [])]
            page.summary_footer_order = [str(x) for x in (header_metrics.get("footer_order") or [])]
            page.summary_metric_labels = dict(header_metrics.get("selected_labels") or {})
            page.summary_metric_widths = dict(header_metrics.get("metric_widths") or {})
            page.summary_metric_positions = dict(header_metrics.get("metric_positions") or {})
            page.summary_metric_styles = dict(header_metrics.get("metric_styles") or {})
            page.summary_band_style = dict(header_metrics.get("band_style") or getattr(page, "summary_band_style", {}) or {})
            page.summary_column_header_labels = dict(header_metrics.get("column_header_labels") or {})
            page.summary_column_header_styles = dict(header_metrics.get("column_header_styles") or {})
            page.summary_column_header_hidden = set(header_metrics.get("column_header_hidden") or [])
            page.summary_column_widths = dict(header_metrics.get("column_widths") or {})
            page.summary_vertical_align = str(header_metrics.get("row_vertical_align") or "center")
            position_widget = getattr(page, "summary_vertical_align_widget", None)
            if position_widget is not None:
                position_widget.blockSignals(True)
                position_index = position_widget.findData(page.summary_vertical_align)
                position_widget.setCurrentIndex(position_index if position_index >= 0 else 1)
                position_widget.blockSignals(False)
            page.summary_footer_linked = bool(header_metrics.get("footer_linked", False))
            page.summary_footer_metric_fields = set(str(x) for x in (header_metrics.get("footer_fields") or []))
            # 27.119 — nettoyer l'ancien ajout automatique « Nombre de fiches ».
            # Ce total spécial ne doit survivre à la réouverture que s'il est
            # réellement activé comme Total dans le bandeau.
            if not bool(header_metrics.get("records", False)):
                page.summary_footer_metric_fields.discard("__records__")
            page.summary_footer_style = dict(header_metrics.get("footer_style") or getattr(page, "summary_footer_style", {}) or {})
            page.summary_footer_metric_styles = dict(header_metrics.get("footer_metric_styles") or {})
            page.summary_footer_metric_labels = dict(header_metrics.get("footer_metric_labels") or {})
            page.summary_footer_metric_spacing = dict(header_metrics.get("footer_metric_spacing") or {})
            page.summary_footer_metric_widths = dict(header_metrics.get("footer_metric_widths") or {})
            page.summary_footer_metric_positions = dict(header_metrics.get("footer_metric_positions") or {})
            page.summary_page_numbers_enabled = bool(header_metrics.get("page_numbers_enabled", False))
            page.summary_page_number_format = str(header_metrics.get("page_number_format") or "page_x_y")
            page.summary_page_number_align = str(header_metrics.get("page_number_align") or "right")
            # 1.0.139 — restituer la pagination sauvegardée dans le constructeur.
            if hasattr(page, "refresh_summary_page_number_sample"):
                page.refresh_summary_page_number_sample()
            # 27.120 — ne pas reconstruire le pied de page avant d'avoir
            # restauré l'état réel des cases Total. Sinon le widget
            # « Nombre de fiches », encore à sa valeur par défaut pendant
            # le chargement, injecte visuellement __records__ dans le pied.
            for _field, _pair in getattr(page, "summary_field_row_widgets", {}).items():
                _col_cb, _total_cb = _pair
                _total_cb.blockSignals(True)
                _total_cb.setChecked(_field in page.summary_metric_fields)
                _total_cb.blockSignals(False)
                _col_cb.blockSignals(True)
                _col_cb.setChecked(_field in selected_summary)
                _col_cb.blockSignals(False)
            if hasattr(page, "summary_show_groups_metric_widget"):
                page.summary_show_groups_metric_widget.setChecked(bool(header_metrics.get("groups", False)) if bool(header_metrics.get("groups_explicit", False)) else False)
                # Le nouvel Atelier part d'un bandeau vide : seuls les champs
                # explicitement cochés « Total » doivent y apparaître.
                page.summary_show_selected_metrics_widget.setChecked(bool(page.summary_metric_fields))
                page.summary_show_species_metric_widget.setChecked(False)
                page.summary_show_records_metric_widget.setChecked(bool(header_metrics.get("records", False)))
                _rp = getattr(page, "summary_field_row_widgets", {}).get("__records__")
                if _rp is not None:
                    _rp[1].blockSignals(True); _rp[1].setChecked(bool(header_metrics.get("records", False))); _rp[1].blockSignals(False)
                page.summary_groups_label_widget.setText(str(header_metrics.get("groups_label") or ""))
                page.summary_distinct_label_widget.setText(str(header_metrics.get("distinct_label") or ""))
                _df = header_metrics.get("distinct_field") or definition.get("group_field")
                _di = page.summary_distinct_field_widget.findData(_df)
                if _di >= 0: page.summary_distinct_field_widget.setCurrentIndex(_di)

                # Les cases Total sont maintenant restaurées : le pied peut
                # être reconstruit sans faire réapparaître le compteur fantôme.
                if hasattr(page, "refresh_summary_footer_sample"):
                    page.refresh_summary_footer_sample()

                page.summary_groups_font_widget.setCurrentFont(
                    QFont(str(header_metrics.get("groups_font") or "Calibri"))
                )
                page.summary_selected_font_widget.setCurrentFont(
                    QFont(str(header_metrics.get("selected_font") or "Calibri"))
                )
                page.summary_species_font_widget.setCurrentFont(
                    QFont(str(header_metrics.get("species_font") or "Calibri"))
                )
                page.summary_records_font_widget.setCurrentFont(
                    QFont(str(header_metrics.get("records_font") or "Calibri"))
                )

                page.summary_groups_size_widget.setValue(int(header_metrics.get("groups_size", 11)))
                page.summary_selected_size_widget.setValue(int(header_metrics.get("selected_size", 11)))
                page.summary_species_size_widget.setValue(int(header_metrics.get("species_size", 11)))
                page.summary_records_size_widget.setValue(int(header_metrics.get("records_size", 10)))

                for widget_name, key, default in (
                    ("summary_groups_text_widget", "groups_text", "#8B3026"),
                    ("summary_selected_text_widget", "selected_text", "#8B3026"),
                    ("summary_species_text_widget", "species_text", "#8B3026"),
                    ("summary_records_text_widget", "records_text", "#7A817D"),
                    ("summary_groups_bg_widget", "groups_bg", "#F4F6F5"),
                    ("summary_selected_bg_widget", "selected_bg", "#F4F6F5"),
                    ("summary_species_bg_widget", "species_bg", "#F4F6F5"),
                    ("summary_records_bg_widget", "records_bg", "#F4F6F5"),
                ):
                    button = getattr(page, widget_name)
                    color = str(header_metrics.get(key, default))
                    button.setProperty("mm3Color", color)
                    foreground = "#F4F4F4" if QColor(color).lightness() < 120 else "#111111"
                    button.setStyleSheet(
                        "QPushButton {"
                        f" background-color:{color}; color:{foreground};"
                        " min-width:48px; max-width:60px; padding:2px 4px; font-weight:600;}"
                        "QPushButton:hover {"
                        f" background-color:{color}; color:{foreground};}}"
                    )

            # Replacer le curseur sur le premier champ coché afin que
            # « Traitement du champ sélectionné » reflète immédiatement l'état sauvegardé.
            if widget is not None:
                first_checked = None
                for i in range(widget.count()):
                    item = widget.item(i)
                    if item.checkState() == Qt.CheckState.Checked:
                        first_checked = item
                        break
                if first_checked is not None:
                    widget.setCurrentItem(first_checked)

        page_chrome = dict(definition.get("page_chrome") or {})
        page.page_show_title_widget.setChecked(bool(page_chrome.get("show_title", True)))
        page.page_title_text_widget.setText(str(page_chrome.get("title_text") or ""))
        page.page_title_size_widget.setValue(int(page_chrome.get("title_font_size", 20)))
        if hasattr(page, "summary_title_font_family"):
            page.summary_title_font_family = str(page_chrome.get("title_font_family") or "Arial")
        page.page_title_bold_widget.setChecked(bool(page_chrome.get("title_bold", True)))
        page.page_title_italic_widget.setChecked(bool(page_chrome.get("title_italic", False)))
        page.page_title_underline_widget.setChecked(bool(page_chrome.get("title_underline", False)))
        title_align = str(page_chrome.get("title_align") or "left")
        idx = page.page_title_align_widget.findData(title_align)
        page.page_title_align_widget.setCurrentIndex(idx if idx >= 0 else 0)

        for widget_name, key, default in (
            ("page_title_text_color_widget", "title_text_color", "#111111"),
            ("page_title_bg_color_widget", "title_bg_color", "#FFFFFF"),
        ):
            button = getattr(page, widget_name)
            color = str(page_chrome.get(key) or default)
            button.setProperty("mm3Color", color)
            q = QColor(color)
            foreground = "#F4F4F4" if q.lightness() < 120 else "#111111"
            button.setStyleSheet(
                "QPushButton {"
                f"background-color:{color}; color:{foreground};"
                "padding:1px 3px; min-width:60px; max-width:64px;"
                "border:1px solid #9aa9a3; border-radius:4px;}"
            )

        page.page_show_collection_widget.setChecked(bool(page_chrome.get("show_collection", False)))
        page.page_show_print_date_widget.setChecked(bool(page_chrome.get("show_print_date", False)))
        page.page_show_page_numbers_widget.setChecked(bool(page_chrome.get("show_page_numbers", True)))
        if hasattr(page, "refresh_summary_title_sample"):
            page.refresh_summary_title_sample()
        saved_font = str(page_chrome.get("print_font_family") or "")
        if saved_font:
            idx = page.page_print_font_widget.findData(saved_font)
            if idx < 0:
                idx = page.page_print_font_widget.findText(saved_font)
            if idx >= 0:
                page.page_print_font_widget.setCurrentIndex(idx)
        page.page_body_size_widget.setValue(int(page_chrome.get("body_font_size", 10)))
        page.page_footer_text_widget.setText(str(page_chrome.get("footer_text") or ""))
        page.page_footer_size_widget.setValue(int(page_chrome.get("footer_font_size", 10)))
        page.page_footer_bold_widget.setChecked(bool(page_chrome.get("footer_bold", False)))
        page.page_footer_italic_widget.setChecked(bool(page_chrome.get("footer_italic", False)))
        page.page_footer_underline_widget.setChecked(bool(page_chrome.get("footer_underline", False)))
        footer_align = str(page_chrome.get("footer_align") or "right")
        idx = page.page_footer_align_widget.findData(footer_align)
        page.page_footer_align_widget.setCurrentIndex(idx if idx >= 0 else 2)

        for widget_name, key, default in (
            ("page_footer_text_color_widget", "footer_text_color", "#4F5A55"),
            ("page_footer_bg_color_widget", "footer_bg_color", "#FFFFFF"),
        ):
            button = getattr(page, widget_name)
            color = str(page_chrome.get(key) or default)
            button.setProperty("mm3Color", color)
            q = QColor(color)
            foreground = "#F4F4F4" if q.lightness() < 120 else "#111111"
            button.setStyleSheet(
                "QPushButton {"
                f"background-color:{color}; color:{foreground};"
                "padding:1px 3px; min-width:60px; max-width:64px;"
                "border:1px solid #9aa9a3; border-radius:4px;}"
            )

        advanced_to_apply = dict(definition.get("advanced_style") or {})
        if kind == "summary" and not dict(advanced_to_apply.get("typography") or {}):
            # Migration douce des anciens états Résumé.
            advanced_to_apply["typography"] = {
                "level1": {
                    "text_color": str(definition.get("summary_field_color") or "#9A3324"),
                    "bold": bool(definition.get("summary_field_bold", True)),
                }
            }

        self._apply_advanced_style_to_page(page, advanced_to_apply)

        if hasattr(page, "rebuild_summary_graphic_lanes") and (kind == "summary" or getattr(page, "detail_summary_clone", False)):
            page.rebuild_summary_graphic_lanes()

        page._loading_state = False
        self._refresh_advanced_live_preview("summary" if getattr(page, "detail_summary_clone", False) else kind, page)

        if kind == "summary" or getattr(page, "detail_summary_clone", False):
            current = getattr(page, "summary_fields_widget", None)
            if current is not None and current.currentItem() is not None:
                # Déclencher la logique existante de sélection sans modifier l'état.
                item = current.currentItem()
                field = str(item.data(Qt.ItemDataRole.UserRole))
                treatment_widget = getattr(page, "summary_treatment_widget", None)
                treatment_name = getattr(page, "summary_treatment_name", None)
                if treatment_name is not None:
                    treatment_name.setText(f"Champ : {item.text()}")
                if treatment_widget is not None:
                    treatment_widget.blockSignals(True)
                    treatment_widget.clear()
                    numeric_fields = {
                        "box_count", "number_of_boxes", "nb_boxes", "boxes",
                        "price", "unit_price", "total_cost", "cost_total",
                    }
                    if field in numeric_fields:
                        treatment_widget.addItem("Somme", "sum")
                        treatment_widget.addItem("Moyenne", "avg")
                        treatment_widget.addItem("Minimum", "min")
                        treatment_widget.addItem("Maximum", "max")
                    elif field == "acquisition_date":
                        treatment_widget.addItem("Nombre de valeurs distinctes", "count_distinct")
                        treatment_widget.addItem("Liste des dates", "list")
                    else:
                        treatment_widget.addItem("Nombre de valeurs distinctes", "count_distinct")
                        treatment_widget.addItem(f"Liste — {item.text()}", "list")
                    saved = getattr(page, "summary_treatments", {}).get(field)
                    idx = treatment_widget.findData(saved)
                    treatment_widget.setCurrentIndex(idx if idx >= 0 else 0)
                    treatment_widget.setEnabled(True)
                    treatment_widget.blockSignals(False)

        page.editing_report_name = name
        self.current_edit_report_name = name
        self._refresh_builder_banner(page, kind)
        self._reset_builder_state(page)
        self._init_builder_undo(kind, page)
        page.update_button.setText(tr("Sauvegarder", self.language))
        self.stack.setCurrentIndex(page_index)
        self.showNormal()
        QTimer.singleShot(0, self._fit_builder_window)
        self.raise_()
        self.activateWindow()

    def _modify_report_from_preview(
        self,
        dialog,
        saved_name=None,
        builder_page=None,
    ) -> None:
        """Revient au constructeur sans perdre les réglages testés dans l’aperçu."""
        dialog.accept()

        # Aperçu lancé depuis le constructeur :
        # le constructeur courant est la référence, y compris pour un état déjà
        # enregistré. On conserve donc tous les réglages non encore sauvegardés
        # (police, taille 7 pt, couleurs, alignements, etc.).
        if builder_page is not None:
            self.stack.setCurrentWidget(builder_page)
            self.showNormal()
            self.raise_()
            self.activateWindow()
            return

        # Aperçu ouvert directement depuis Collection :
        # dans ce cas seulement, la définition enregistrée reste la référence.
        if saved_name and saved_name in self.saved_reports:
            self._load_report_into_builder(saved_name)
            return


    def _advanced_style_from_page(self, page) -> dict:
        typography = {}
        for key, group in getattr(page, "advanced_typography_widgets", {}).items():
            typography[key] = {
                "font_family": (
                    group["font"].currentFont().family()
                    if "font" in group else ""
                ),
                "font_size": int(group["size"].value()),
                "bold": bool(group["bold"].isChecked()),
                "italic": bool(group["italic"].isChecked()),
                "underline": bool(group["underline"].isChecked()),
                "align": str(group["align"].currentData() or "left"),
                "text_color": str(group["text_color"].property("mm3Color") or "#111111"),
                "bg_color": str(group["bg_color"].property("mm3Color") or "#F4F6F5"),
            }
        level1 = typography.get("level1", {})

        def _optional_combo_data(attr_name, default):
            widget = getattr(page, attr_name, None)
            if widget is None:
                return default
            try:
                value = widget.currentData()
                return str(value) if value not in (None, "") else default
            except Exception:
                return default

        return {
            "font_size": int(level1.get("font_size", 11)),
            "bold": bool(level1.get("bold", True)),
            "italic": bool(level1.get("italic", False)),
            "underline": bool(level1.get("underline", False)),
            "align": str(level1.get("align", "left")),
            "typography": typography,
            "band_font_family": (
                page.advanced_band_font_widget.currentFont().family()
                if getattr(page, "advanced_band_font_widget", None) is not None
                else "Calibri"
            ),
            "header_title": page.advanced_header_title_widget.text().strip(),
            "separator": bool(page.advanced_separator_widget.isChecked()),
            "column_header_font_family": (
                getattr(page, "advanced_column_header_font_widget").currentFont().family()
                if getattr(page, "advanced_column_header_font_widget", None) is not None
                else ""
            ),
            "column_header_font_size": int(
                getattr(page, "advanced_column_header_size_widget").value()
            ),
            "column_header_bold": bool(
                getattr(page, "advanced_column_header_bold_widget").isChecked()
            ),
            "column_header_italic": bool(
                getattr(page, "advanced_column_header_italic_widget").isChecked()
            ),
            "column_header_underline": bool(
                getattr(page, "advanced_column_header_underline_widget").isChecked()
            ),
            "column_header_align": _optional_combo_data(
                "advanced_column_header_align_widget", "center"
            ),
            "column_header_text_color": str(
                getattr(page, "advanced_column_header_text_widget").property("mm3Color")
                or "#111111"
            ),
            "column_header_bg_color": str(
                getattr(page, "advanced_column_header_bg_widget").property("mm3Color")
                or "#DDE8E2"
            ),
            "detail_borders": _optional_combo_data(
                "advanced_detail_borders_widget", "none"
            ),
            "detail_trait": _optional_combo_data(
                "advanced_detail_trait_widget", "none"
            ),
            "group_trait": _optional_combo_data(
                "advanced_group_trait_widget", "1pt"
            ),
            "header_trait": _optional_combo_data(
                "advanced_header_trait_widget", "2pt"
            ),
            "summary_layout_marks": dict(getattr(page, "summary_layout_marks", {}) or {}),
            "preview_zebra_rows": bool(getattr(page, "preview_zebra_rows", True)),
            "preview_gray_totals_band": bool(getattr(page, "preview_gray_totals_band", True)),
        }

    def _apply_advanced_style_to_page(self, page, style) -> None:
        style = dict(style or {})
        # 1.0.110 — ces deux choix appartiennent au modèle d’État, même s’ils
        # sont manipulés directement dans l’Aperçu.
        page.preview_zebra_rows = bool(style.get("preview_zebra_rows", True))
        page.preview_gray_totals_band = bool(style.get("preview_gray_totals_band", True))
        typography = dict(style.get("typography") or {})
        defaults = {
            "level1": {"font_family":"Calibri", "font_size":11, "bold":True, "italic":False, "underline":False, "align":"left", "text_color":"#9A3324", "bg_color":"#C8D8D0"},
            "level2": {"font_family":"Calibri", "font_size":10, "bold":True, "italic":False, "underline":False, "align":"left", "text_color":"#111111", "bg_color":"#DDE8E2"},
            "level3": {"font_family":"Calibri", "font_size":10, "bold":True, "italic":False, "underline":False, "align":"left", "text_color":"#737B77", "bg_color":"#EEF3F0"},
            "repeat": {"font_family":"Calibri", "font_size":10, "bold":False, "italic":True, "underline":False, "align":"left", "text_color":"#9A3324", "bg_color":"#FFFFFF"},
            "detail": {"font_family":"Calibri", "font_size":10, "bold":False, "italic":False, "underline":False, "align":"left", "text_color":"#111111", "bg_color":"#FFFFFF"},
            "summary_master": {"font_family":"Calibri", "font_size":10, "bold":False, "italic":False, "underline":False, "align":"left", "text_color":"#111111", "bg_color":"#FFFFFF"},
            "summary_secondary": {"font_family":"Calibri", "font_size":10, "bold":False, "italic":False, "underline":False, "align":"left", "text_color":"#111111", "bg_color":"#FFFFFF"},
        }

        if "level1" not in typography:
            typography["level1"] = {
                "font_size": int(style.get("font_size", 11)),
                "bold": bool(style.get("bold", True)),
                "italic": bool(style.get("italic", False)),
                "underline": bool(style.get("underline", False)),
                "align": str(style.get("align", "left")),
            }

        for key, group in getattr(page, "advanced_typography_widgets", {}).items():
            values = dict(defaults[key])
            saved_values = dict(typography.get(key) or {})
            values.update(saved_values)

            if "font" in group:
                family = str(values.get("font_family") or "Calibri")
                group["font"].setCurrentFont(QFont(family))

            group["size"].setValue(int(values["font_size"]))
            group["bold"].setChecked(bool(values["bold"]))
            group["italic"].setChecked(bool(values["italic"]))
            group["underline"].setChecked(bool(values["underline"]))

            idx = group["align"].findData(str(values["align"]))
            group["align"].setCurrentIndex(idx if idx >= 0 else 0)

            for button_key, color_key in (("text_color", "text_color"), ("bg_color", "bg_color")):
                button = group[button_key]
                color = str(values[color_key])
                button.setProperty("mm3Color", color)
                q = QColor(color)
                foreground = "#F4F4F4" if q.lightness() < 120 else "#111111"
                button.setStyleSheet(
                    "QPushButton {"
                    f"background-color:{color}; color:{foreground};"
                    "padding:1px 4px; min-width:68px; max-width:72px;"
                    "border:1px solid #9aa9a3; border-radius:4px;}"
                )

        band_font_widget = getattr(page, "advanced_band_font_widget", None)
        if band_font_widget is not None:
            band_font_widget.setCurrentFont(
                QFont(str(style.get("band_font_family") or "Calibri"))
            )

        page.advanced_header_title_widget.setText(str(style.get("header_title") or ""))
        page.advanced_separator_widget.setChecked(bool(style.get("separator", True)))
        if hasattr(page, "summary_layout_marks"):
            page.summary_layout_marks = dict(style.get("summary_layout_marks") or {})
            if hasattr(page, "refresh_summary_layout_marks"):
                page.refresh_summary_layout_marks()

        font_widget = getattr(page, "advanced_column_header_font_widget", None)
        if font_widget is not None:
            font_widget.setCurrentFont(
                QFont(str(style.get("column_header_font_family") or "Calibri"))
            )

        size_widget = getattr(page, "advanced_column_header_size_widget", None)
        if size_widget is not None:
            size_widget.setValue(int(style.get("column_header_font_size", 10)))

        for widget_name, style_key, default in (
            ("advanced_column_header_bold_widget", "column_header_bold", True),
            ("advanced_column_header_italic_widget", "column_header_italic", False),
            ("advanced_column_header_underline_widget", "column_header_underline", False),
        ):
            widget = getattr(page, widget_name, None)
            if widget is not None:
                widget.setChecked(bool(style.get(style_key, default)))

        header_align_widget = getattr(
            page, "advanced_column_header_align_widget", None
        )
        if header_align_widget is not None:
            idx = header_align_widget.findData(
                str(style.get("column_header_align") or "center")
            )
            header_align_widget.setCurrentIndex(idx if idx >= 0 else 0)

        for widget_name, style_key, default in (
            ("advanced_column_header_text_widget", "column_header_text_color", "#111111"),
            ("advanced_column_header_bg_widget", "column_header_bg_color", "#DDE8E2"),
        ):
            button = getattr(page, widget_name, None)
            if button is not None:
                color = str(style.get(style_key) or default)
                button.setProperty("mm3Color", color)
                q = QColor(color)
                foreground = "#F4F4F4" if q.lightness() < 120 else "#111111"
                button.setStyleSheet(
                    "QPushButton {"
                    f"background-color:{color}; color:{foreground};"
                    "padding:1px 4px; min-width:68px; max-width:72px;"
                    "border:1px solid #9aa9a3; border-radius:4px;}"
                )
        for widget_name, key, default in (
            ("advanced_detail_borders_widget", "detail_borders", "none"),
            ("advanced_detail_trait_widget", "detail_trait", "none"),
            ("advanced_group_trait_widget", "group_trait", "1pt"),
            ("advanced_header_trait_widget", "header_trait", "2pt"),
        ):
            widget = getattr(page, widget_name, None)
            if widget is not None:
                idx = widget.findData(str(style.get(key) or default))
                widget.setCurrentIndex(idx if idx >= 0 else 0)


    def _definition_from_builder(self, kind: str, page: QWidget) -> dict:
        if kind == "detail" and getattr(page, "detail_summary_clone", False):
            definition = self._definition_from_builder("summary", page)
            master = str(getattr(page, "summary_graphic_master", None) or "")
            secondary = [str(f) for f in getattr(page, "summary_graphic_secondaries", [])]
            definition.update(kind="detail", detail_groupings=[master] if master else [],
                              detail_secondary_fields=secondary,
                              fields=secondary or ([master] if master else []),
                              detail_master_styles=dict(getattr(page, "detail_master_styles", {}) or {}),
                              detail_field_styles=dict(getattr(page, "summary_field_styles", {}) or {}),
                              detail_group_totals=list(getattr(page, "detail_group_totals", []) or []),
                              detail_total_styles=dict(getattr(page, "detail_total_styles", {}) or {}),
                              detail_column_labels=dict(getattr(page, "detail_column_labels", {}) or {}),
                              detail_label_styles=dict(getattr(page, "detail_label_styles", {}) or {}),
                              detail_column_widths=dict(getattr(page, "detail_column_widths", {}) or {}))
            return definition
        definition = {
            "kind": kind,
            "title": page.title_widget.text().strip()
            or ("État détaillé" if kind == "detail" else "État résumé"),
            "source_name": page.source_widget.currentData(),
            "landscape": bool(page.landscape_widget.isChecked()),
        }

        definition["advanced_style"] = self._advanced_style_from_page(page)
        definition["page_chrome"] = {
            "show_title": bool(page.page_show_title_widget.isChecked()),
            "title_text": page.page_title_text_widget.text().strip(),
            "title_font_size": int(page.page_title_size_widget.value()),
            "title_font_family": str(getattr(page, "summary_title_font_family", "Calibri") or "Calibri"),
            "title_bold": bool(page.page_title_bold_widget.isChecked()),
            "title_italic": bool(page.page_title_italic_widget.isChecked()),
            "title_underline": bool(page.page_title_underline_widget.isChecked()),
            "title_align": str(page.page_title_align_widget.currentData() or "left"),
            "title_text_color": str(
                page.page_title_text_color_widget.property("mm3Color") or "#111111"
            ),
            "title_bg_color": str(
                page.page_title_bg_color_widget.property("mm3Color") or "#FFFFFF"
            ),
            "show_collection": bool(page.page_show_collection_widget.isChecked()),
            "show_print_date": bool(page.page_show_print_date_widget.isChecked()),
            "show_page_numbers": bool(page.page_show_page_numbers_widget.isChecked()),
            "print_font_family": str(page.page_print_font_widget.currentData() or page.page_print_font_widget.currentText() or "Arial"),
            "body_font_size": int(page.page_body_size_widget.value()),
            "footer_text": page.page_footer_text_widget.text().strip(),
            "footer_font_size": int(page.page_footer_size_widget.value()),
            "footer_bold": bool(page.page_footer_bold_widget.isChecked()),
            "footer_italic": bool(page.page_footer_italic_widget.isChecked()),
            "footer_underline": bool(page.page_footer_underline_widget.isChecked()),
            "footer_align": str(page.page_footer_align_widget.currentData() or "right"),
            "footer_text_color": str(page.page_footer_text_color_widget.property("mm3Color") or "#4F5A55"),
            "footer_bg_color": str(page.page_footer_bg_color_widget.property("mm3Color") or "#FFFFFF"),
        }

        # Conserver la mise en page visuelle enregistrée jusqu'au prochain
        # réglage effectué dans l'aperçu.
        existing_name = getattr(page, "editing_report_name", None)
        existing = self.saved_reports.get(existing_name, {}) if existing_name else {}
        definition["layout"] = dict(
            getattr(page, "_detail_preview_layout_state", None)
            if kind == "detail" and getattr(page, "_detail_preview_layout_state", None)
            else existing.get("layout") or {}
        )

        if kind == "detail":
            fields = []
            widget = page.fields_widget
            for i in range(widget.count()):
                item = widget.item(i)
                if item.checkState() == Qt.CheckState.Checked:
                    fields.append(str(item.data(Qt.ItemDataRole.UserRole)))
            definition["fields"] = fields
            definition["detail_column_alignments"] = dict(
                getattr(page, "detail_column_alignments", {}) or {}
            )
            definition["detail_groupings"] = self._normalized_detail_groupings(
                [combo.currentData() for combo in page.detail_grouping_widgets]
            )
            definition["atelier_style"] = self._atelier_style_from_page(page)
        else:
            # 27.51 — le constructeur graphique est la source de vérité.
            # Les anciens widgets cachés ne doivent jamais pouvoir vider un modèle.
            graphic_master = str(getattr(page, "summary_graphic_master", None) or "")
            definition["group_field"] = graphic_master or None
            definition["date_group_mode"] = str(
                page.date_group_mode_widget.currentData() or "full_date"
            )
            definition["second_group_field"] = page.second_group_widget.currentData()
            definition["show_details"] = False

            # Sauvegarder exactement les colonnes visibles de la construction.
            selected_summary_fields = []
            if graphic_master:
                selected_summary_fields.append(graphic_master)
            for _field in list(getattr(page, "summary_graphic_secondaries", []) or [])[:4]:
                _field = str(_field)
                if _field and _field not in selected_summary_fields:
                    selected_summary_fields.append(_field)
            definition["summary_fields"] = selected_summary_fields
            widget = getattr(page, "summary_fields_widget", None)
            definition["summary_column_alignments"] = dict(
                getattr(page, "summary_column_alignments", {}) or {}
            )

            # Chaque champ conserve son propre traitement.
            definition["summary_treatments"] = dict(
                getattr(page, "summary_treatments", {}) or {}
            )
            definition["summary_field_styles"] = dict(getattr(page, "summary_field_styles", {}) or {})
            definition["summary_spacing"] = int(
                getattr(page, "summary_spacing_widget").value()
            )
            definition["summary_header_metrics"] = {
                "groups": bool(page.summary_show_groups_metric_widget.isChecked()),
                "groups_explicit": True,
                "selected": bool(page.summary_show_selected_metrics_widget.isChecked()),
                "selected_fields": self._ordered_summary_totals(page),
                "footer_order": list(getattr(page, "summary_footer_order", []) or []),
                "selected_labels": dict(getattr(page, "summary_metric_labels", {}) or {}),
                "metric_widths": dict(getattr(page, "summary_metric_widths", {}) or {}),
                "metric_positions": dict(getattr(page, "summary_metric_positions", {}) or {}),
                "metric_styles": dict(getattr(page, "summary_metric_styles", {}) or {}),
                "band_style": dict(getattr(page, "summary_band_style", {}) or {}),
                "column_header_labels": dict(getattr(page, "summary_column_header_labels", {}) or {}),
                "column_header_styles": dict(getattr(page, "summary_column_header_styles", {}) or {}),
                "column_header_hidden": sorted(getattr(page, "summary_column_header_hidden", set()) or set()),
                "column_widths": dict(getattr(page, "summary_column_widths", {}) or {}),
                "row_vertical_align": str(getattr(page, "summary_vertical_align", "center")),
                "footer_linked": bool(getattr(page, "summary_footer_linked", False)),
                "footer_fields": (
                    [w.metric_field for w in getattr(page, "summary_footer_sample").findChildren(SummaryMetricLabel)
                     if getattr(w, "metric_field", None)]
                    if (getattr(page, "summary_footer_sample", None) is not None
                        and not bool(getattr(page, "summary_footer_linked", False)))
                    else list(getattr(page, "summary_footer_metric_fields", set()) or set())
                ),
                "footer_style": dict(getattr(page, "summary_footer_style", {}) or {}),
                "footer_metric_styles": dict(getattr(page, "summary_footer_metric_styles", {}) or {}),
                "footer_metric_labels": dict(getattr(page, "summary_footer_metric_labels", {}) or {}),
                "footer_metric_spacing": dict(getattr(page, "summary_footer_metric_spacing", {}) or {}),
                "footer_metric_widths": dict(getattr(page, "summary_footer_metric_widths", {}) or {}),
                "footer_metric_positions": dict(getattr(page, "summary_footer_metric_positions", {}) or {}),
                "page_numbers_enabled": bool(getattr(page, "summary_page_numbers_enabled", False)),
                "page_number_format": str(getattr(page, "summary_page_number_format", "page_x_y") or "page_x_y"),
                "page_number_align": str(getattr(page, "summary_page_number_align", "right") or "right"),
                "species": False,  # ancien compteur supprimé ; les totaux passent par Champ | Total
                "records": bool(page.summary_show_records_metric_widget.isChecked()),
                "groups_label": page.summary_groups_label_widget.text().strip(),
                "distinct_field": page.summary_distinct_field_widget.currentData(),
                "distinct_label": page.summary_distinct_label_widget.text().strip(),

                "groups_font": page.summary_groups_font_widget.currentFont().family(),
                "selected_font": page.summary_selected_font_widget.currentFont().family(),
                "species_font": page.summary_species_font_widget.currentFont().family(),
                "records_font": page.summary_records_font_widget.currentFont().family(),

                "groups_size": int(page.summary_groups_size_widget.value()),
                "selected_size": int(page.summary_selected_size_widget.value()),
                "species_size": int(page.summary_species_size_widget.value()),
                "records_size": int(page.summary_records_size_widget.value()),

                "groups_text": str(page.summary_groups_text_widget.property("mm3Color") or "#8B3026"),
                "selected_text": str(page.summary_selected_text_widget.property("mm3Color") or "#8B3026"),
                "species_text": str(page.summary_species_text_widget.property("mm3Color") or "#8B3026"),
                "records_text": str(page.summary_records_text_widget.property("mm3Color") or "#7A817D"),

                "groups_bg": str(page.summary_groups_bg_widget.property("mm3Color") or "#F4F6F5"),
                "selected_bg": str(page.summary_selected_bg_widget.property("mm3Color") or "#F4F6F5"),
                "species_bg": str(page.summary_species_bg_widget.property("mm3Color") or "#F4F6F5"),
                "records_bg": str(page.summary_records_bg_widget.property("mm3Color") or "#F4F6F5"),
            }
            level1 = page.advanced_typography_widgets.get("level1", {})
            definition["summary_field_color"] = str(
                level1["text_color"].property("mm3Color") if level1 else "#9A3324"
            )
            definition["summary_field_bold"] = bool(
                level1["bold"].isChecked() if level1 else True
            )

        return definition

    def _save_report_from_builder(self, kind: str, page: QWidget) -> None:
        """Sauvegarde simple : même nom = mise à jour, autre nom = nouvel état."""
        current_name = getattr(page, "editing_report_name", None)
        is_new = not bool(current_name)

        if (not is_new) and not bool(getattr(page, "builder_dirty", False)):
            return

        definition = self._definition_from_builder(kind, page)

        if kind == "detail" and not definition.get("fields"):
            QMessageBox.information(
                self,
                "Aucun champ",
                "Choisissez au moins un champ avant de sauvegarder l’état.",
            )
            return

        default_text = str(current_name or "")

        dialog = QDialog(self)
        dialog.setWindowTitle(tr("Sauvegarder l’état", self.language))
        dialog.setModal(True)
        dialog_layout = QVBoxLayout(dialog)
        dialog_layout.setContentsMargins(12, 10, 12, 10)
        dialog_layout.setSpacing(8)
        dialog_layout.addWidget(QLabel(tr("Nom de l’état :", self.language)))

        name_edit = QLineEdit(default_text)
        name_edit.setMinimumWidth(280)
        name_edit.selectAll()
        dialog_layout.addWidget(name_edit)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        ok_button = QPushButton("OK")
        cancel_button = QPushButton(tr("Annuler", self.language))
        button_row.addWidget(ok_button)
        button_row.addWidget(cancel_button)
        dialog_layout.addLayout(button_row)

        ok_button.clicked.connect(dialog.accept)
        cancel_button.clicked.connect(dialog.reject)
        name_edit.returnPressed.connect(dialog.accept)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        name = name_edit.text().strip()
        if not name:
            QMessageBox.information(
                self,
                "Nom obligatoire",
                "Saisissez un nom pour sauvegarder l’état.",
            )
            return

        if name in self.saved_reports and name != current_name:
            answer = QMessageBox.question(
                self,
                "Nom déjà utilisé",
                f"Un état nommé « {name} » existe déjà.\n"
                "Voulez-vous le remplacer ?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        folder = self._choose_report_folder(kind, current_name if current_name in self.saved_reports else name)
        if folder is None:
            return
        self.saved_reports[name] = definition
        model_folders.assign(self.startup.database.database_path, int(self.collection["id"]), "etat", name, folder)

        if name not in self.report_custom_order:
            self.report_custom_order.append(name)

        page.editing_report_name = name
        self.current_edit_report_name = name
        self._refresh_builder_banner(page, kind)

        self._write_saved_reports()
        self._write_report_order_settings()
        self._refresh_saved_reports_list()

        self._reset_builder_state(page)

        QMessageBox.information(
            self,
            tr("État sauvegardé", self.language),
            tr("« {name} » a été sauvegardé.", self.language).format(name=name),
        )


    def _update_report_from_builder(self, kind: str, page: QWidget) -> None:
        """Met à jour l'état sélectionné, comme pour une requête enregistrée."""
        name = getattr(page, "editing_report_name", None)
        if not name or name not in self.saved_reports:
            return

        definition = self._definition_from_builder(kind, page)
        if kind == "detail" and not definition.get("fields"):
            QMessageBox.information(
                self,
                "Aucun champ",
                "Choisissez au moins un champ avant de mettre l’état à jour.",
            )
            return

        folder = self._choose_report_folder(kind, name)
        if folder is None:
            return
        self.saved_reports[name] = definition
        model_folders.assign(self.startup.database.database_path,
                             int(self.collection["id"]), "etat", name, folder)
        self._write_saved_reports()
        self._refresh_saved_reports_list()
        QMessageBox.information(
            self,
            "État mis à jour",
            f"« {name} » a été mis à jour.",
        )

    def _rename_selected_report(self) -> None:
        old = self._selected_report_name()
        if not old:
            return
        new, ok = QInputDialog.getText(self, "Renommer l’état", "Nouveau nom :", text=old)
        new = new.strip()
        if not ok or not new or new == old:
            return
        if new in self.saved_reports:
            QMessageBox.information(self, "Nom déjà utilisé", "Ce nom d’état existe déjà.")
            return
        self.saved_reports[new] = self.saved_reports.pop(old)
        model_folders.rename_item(self.startup.database.database_path, int(self.collection["id"]), "etat", old, new)
        self.report_custom_order = [
            new if item == old else item for item in self.report_custom_order
        ]
        for page_index in (1, 2):
            page = self.stack.widget(page_index)
            if getattr(page, "editing_report_name", None) == old:
                page.editing_report_name = new
        if self.current_edit_report_name == old:
            self.current_edit_report_name = new
        self._write_saved_reports()
        self._write_report_order_settings()
        self._refresh_saved_reports_list()

    def _duplicate_selected_report(self) -> None:
        old = self._selected_report_name()
        if not old:
            return
        new, ok = QInputDialog.getText(
            self, "Dupliquer l’état", "Nom de la copie :", text=f"{old} - copie"
        )
        new = new.strip()
        if not ok or not new:
            return
        if new in self.saved_reports:
            QMessageBox.information(self, "Nom déjà utilisé", "Ce nom d’état existe déjà.")
            return
        # Copie profonde pour garantir l'indépendance des deux états.
        self.saved_reports[new] = json.loads(json.dumps(self.saved_reports[old]))
        model_folders.assign(self.startup.database.database_path, int(self.collection["id"]), "etat", new, self._report_folder(old))
        if new not in self.report_custom_order:
            self.report_custom_order.append(new)
        self._write_saved_reports()
        self._write_report_order_settings()
        self._refresh_saved_reports_list()

    def _delete_selected_report(self) -> None:
        name = self._selected_report_name()
        if not name:
            return
        answer = QMessageBox.question(
            self,
            "Delete report" if str(self.language).startswith("en") else ("Bericht löschen" if str(self.language).startswith("de") else "Supprimer l’état"),
            (f"Permanently delete “{name}”?" if str(self.language).startswith("en") else (f"Bericht „{name}“ endgültig löschen?" if str(self.language).startswith("de") else f"Supprimer définitivement « {name} » ?")),
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.saved_reports.pop(name, None)
        model_folders.delete_item(self.startup.database.database_path, int(self.collection["id"]), "etat", name)
        self.report_custom_order = [item for item in self.report_custom_order if item != name]
        for page_index in (1, 2):
            page = self.stack.widget(page_index)
            if getattr(page, "editing_report_name", None) == name:
                page.editing_report_name = None
                page.update_button.setEnabled(True)
        if self.current_edit_report_name == name:
            self.current_edit_report_name = None
        self._write_saved_reports()
        self._write_report_order_settings()
        self._refresh_saved_reports_list()

    def _type_card(self, title: str, text: str, callback) -> QFrame:
        card = QFrame()
        card.setObjectName("typeCard")
        lay = QVBoxLayout(card)
        label = QLabel(title)
        label.setObjectName("cardTitle")
        desc = QLabel(text)
        desc.setWordWrap(True)
        button = QPushButton(tr("Créer", self.language))
        button.clicked.connect(callback)
        lay.addWidget(label)
        lay.addWidget(desc)
        lay.addStretch(1)
        lay.addWidget(button)
        return card

    def _build_advanced_editor_panel(self, kind: str, page: QWidget) -> QGroupBox:
        """Réglages avancés réservés à Atelier -> Éditeur d'états."""
        box = QGroupBox("Réglages avancés de l’état")
        box.setObjectName("advancedReportSettings")
        box.setStyleSheet("""
            QGroupBox#advancedReportSettings {
                background-color: #c7d3ce;
                border: 1px solid #9aa9a3;
                border-radius: 8px;
                margin-top: 5px;
                padding-top: 6px;
            }
            QGroupBox#advancedReportSettings::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 5px;
                font-weight: 700;
            }
        """)
        grid = QGridLayout(box)
        grid.setContentsMargins(6, 3, 6, 4)
        grid.setHorizontalSpacing(3)
        grid.setVerticalSpacing(1)

        note = QLabel(
            "Typographie fine des niveaux du résumé."
            if kind == "summary"
            else "Typographie fine des regroupements, du champ répété et du détail."
        )
        note.setObjectName("previewHint")
        note.setWordWrap(False)
        note.setFixedHeight(18)
        grid.addWidget(note, 0, 0, 1, 9)

        for col, label in enumerate(
            ("Élément", "Police", "Taille", "Gras", "Italique", "Souligné", "Alignement", "Texte", "Fond")
        ):
            h = QLabel(label)
            h.setStyleSheet("font-weight:600;")
            grid.addWidget(h, 1, col)

        defaults = {
            "level1": (11, True, False, False, "#9A3324", "#C8D8D0"),
            "level2": (10, True, False, False, "#111111", "#DDE8E2"),
            "level3": (10, True, False, False, "#737B77", "#EEF3F0"),
            "repeat": (10, False, True, False, "#9A3324", "#FFFFFF"),
            "detail": (10, False, False, False, "#111111", "#FFFFFF"),
        }

        rows = (
            [
                ("Niveau 1", "level1"),
                ("Niveau 2", "level2"),
            ]
            if kind == "summary"
            else [
                ("Niveau 1", "level1"),
                ("Niveau 2", "level2"),
                ("Niveau 3", "level3"),
                ("Champ répété", "repeat"),
                ("Détail de la fiche", "detail"),
            ]
        )

        page.advanced_typography_widgets = {}

        def make_color_button(label: str, color: str) -> QPushButton:
            button = QPushButton(label)
            button.setProperty("mm3Color", color)
            button.setFixedWidth(64)
            button.setFixedHeight(24)

            def apply_style(value: str) -> None:
                q = QColor(value)
                foreground = "#F4F4F4" if q.lightness() < 120 else "#111111"
                button.setStyleSheet(
                    "QPushButton {"
                    f"background-color:{value}; color:{foreground};"
                    "padding:1px 3px; min-width:60px; max-width:64px;"
                    "border:1px solid #9aa9a3; border-radius:4px;}"
                )

            def choose_color() -> None:
                current = QColor(str(button.property("mm3Color") or color))
                dialog = QColorDialog(current, self)
                dialog.setWindowTitle("Choisir une couleur")
                translations = {
                    "Basic colors": "Couleurs de base",
                    "Custom colors": "Couleurs personnalisées",
                    "Pick Screen Color": "Choisir une couleur à l’écran",
                    "Add to Custom Colors": "Ajouter aux couleurs personnalisées",
                    "Hue:": "Teinte :",
                    "Sat:": "Saturation :",
                    "Val:": "Valeur :",
                    "Red:": "Rouge :",
                    "Green:": "Vert :",
                    "Blue:": "Bleu :",
                    "HTML:": "HTML :",
                    "OK": "OK",
                    "Cancel": "Annuler",
                }
                for child in dialog.findChildren(QLabel):
                    key = child.text().replace("&", "")
                    if key in translations:
                        child.setText(translations[key])
                for child in dialog.findChildren(QPushButton):
                    key = child.text().replace("&", "")
                    if key in translations:
                        child.setText(translations[key])
                for bb in dialog.findChildren(QDialogButtonBox):
                    cancel = bb.button(QDialogButtonBox.StandardButton.Cancel)
                    if cancel is not None:
                        cancel.setText("Annuler")
                    ok = bb.button(QDialogButtonBox.StandardButton.Ok)
                    if ok is not None:
                        ok.setText("OK")

                if dialog.exec() == QDialog.DialogCode.Accepted:
                    chosen = dialog.selectedColor()
                    if chosen.isValid():
                        button.setProperty("mm3Color", chosen.name())
                        apply_style(chosen.name())
                        self._mark_builder_dirty(page)
                        self._refresh_advanced_live_preview(kind, page)

            apply_style(color)
            button.clicked.connect(choose_color)
            return button

        for row, (label, key) in enumerate(rows, start=2):
            size_default, bold_default, italic_default, underline_default, text_default, bg_default = defaults[key]

            font = QFontComboBox()
            font.setCurrentFont(QFont("Calibri"))
            font.setMaximumWidth(175)
            font.setFixedHeight(24)

            size = QSpinBox()
            size.setRange(6, 24)
            size.setValue(size_default)
            size.setSuffix(" pt")
            size.setFixedHeight(24)
            size.setMaximumWidth(72)

            bold = QCheckBox()
            italic = QCheckBox()
            underline = QCheckBox()
            bold.setChecked(bold_default)
            italic.setChecked(italic_default)
            underline.setChecked(underline_default)
            for chk in (bold, italic, underline):
                chk.setFixedHeight(20)
                chk.setFixedWidth(22)

            align = QComboBox()
            align.addItem(tr("Gauche", self.language), "left")
            align.addItem(tr("Centré", self.language), "center")
            align.addItem(tr("Droite", self.language), "right")
            align.setFixedHeight(24)
            align.setMaximumWidth(105)

            text_color = make_color_button("Texte", text_default)
            bg_color = make_color_button("Fond", bg_default)

            grid.addWidget(QLabel(label), row, 0)
            grid.addWidget(font, row, 1)
            grid.addWidget(size, row, 2)
            grid.addWidget(bold, row, 3)
            grid.addWidget(italic, row, 4)
            grid.addWidget(underline, row, 5)
            grid.addWidget(align, row, 6)
            grid.addWidget(text_color, row, 7)
            grid.addWidget(bg_color, row, 8)

            page.advanced_typography_widgets[key] = {
                "font": font,
                "size": size,
                "bold": bold,
                "italic": italic,
                "underline": underline,
                "align": align,
                "text_color": text_color,
                "bg_color": bg_color,
            }

        # Présentation commune des en-têtes de colonnes du tableau.
        column_header_font = QFontComboBox()
        column_header_font.setCurrentFont(QFont("Calibri"))
        column_header_font.setMaximumWidth(175)
        column_header_font.setFixedHeight(24)

        column_header_size = QSpinBox()
        column_header_size.setRange(6, 24)
        column_header_size.setValue(10)
        column_header_size.setSuffix(" pt")
        column_header_size.setFixedHeight(24)
        column_header_size.setMaximumWidth(82)

        column_header_bold = QCheckBox()
        column_header_bold.setChecked(True)
        column_header_italic = QCheckBox()
        column_header_underline = QCheckBox()
        for chk in (
            column_header_bold,
            column_header_italic,
            column_header_underline,
        ):
            chk.setFixedWidth(22)

        column_header_text = make_color_button("Texte", "#111111")
        column_header_bg = make_color_button("Fond", "#DDE8E2")

        column_header_row = 2 + len(rows)
        grid.addWidget(QLabel("En-tête colonnes"), column_header_row, 0)
        grid.addWidget(column_header_font, column_header_row, 1)
        grid.addWidget(column_header_size, column_header_row, 2)
        grid.addWidget(column_header_bold, column_header_row, 3)
        grid.addWidget(column_header_italic, column_header_row, 4)
        grid.addWidget(column_header_underline, column_header_row, 5)
        grid.addWidget(QLabel(""), column_header_row, 6)
        grid.addWidget(column_header_text, column_header_row, 7)
        grid.addWidget(column_header_bg, column_header_row, 8)

        page.advanced_column_header_font_widget = column_header_font
        page.advanced_column_header_size_widget = column_header_size
        page.advanced_column_header_bold_widget = column_header_bold
        page.advanced_column_header_italic_widget = column_header_italic
        page.advanced_column_header_underline_widget = column_header_underline
        page.advanced_column_header_text_widget = column_header_text
        page.advanced_column_header_bg_widget = column_header_bg

        band_font = QFontComboBox()
        band_font.setCurrentFont(QFont("Calibri"))
        band_font.setMaximumWidth(175)
        band_font.setFixedHeight(24)

        header_title = QLineEdit()
        header_title.setPlaceholderText("Titre facultatif du bandeau")
        header_title.setFixedHeight(24)
        show_separator = QCheckBox("Séparateur")
        show_separator.setChecked(True)
        show_separator.setFixedHeight(20)

        # Ancienne ligne "Bandeau" supprimée de l'interface.
        # Widgets conservés hors affichage pour compatibilité.
        page.advanced_band_font_widget = band_font
        page.advanced_header_title_widget = header_title
        page.advanced_separator_widget = show_separator

        # Traits et bordures de l'état.
        line_row = 3 + len(rows)

        borders = QComboBox()
        borders.addItem("Aucune", "none")
        borders.addItem("Horizontales", "horizontal")
        borders.addItem("Grille", "grid")
        borders.setMaximumWidth(125)

        detail_trait = QComboBox()
        detail_trait.addItem("Aucun", "none")
        detail_trait.addItem("Filet", "hairline")
        detail_trait.addItem("1 point", "1pt")
        detail_trait.addItem("2 points", "2pt")
        detail_trait.setMaximumWidth(100)

        group_trait = QComboBox()
        group_trait.addItem("Aucun", "none")
        group_trait.addItem("Filet", "hairline")
        group_trait.addItem("1 point", "1pt")
        group_trait.addItem("2 points", "2pt")
        group_trait.setCurrentIndex(group_trait.findData("1pt"))
        group_trait.setMaximumWidth(100)

        header_trait = QComboBox()
        header_trait.addItem("Aucun", "none")
        header_trait.addItem("Filet", "hairline")
        header_trait.addItem("1 point", "1pt")
        header_trait.addItem("2 points", "2pt")
        header_trait.setCurrentIndex(header_trait.findData("2pt"))
        header_trait.setMaximumWidth(100)

        line_box = QWidget()
        line_lay = QHBoxLayout(line_box)
        line_lay.setContentsMargins(0, 0, 0, 0)
        line_lay.setSpacing(4)
        line_lay.addWidget(QLabel("Bordures :"))
        line_lay.addWidget(borders)
        line_lay.addSpacing(5)
        line_lay.addWidget(QLabel("Trait entre lignes :"))
        line_lay.addWidget(detail_trait)
        line_lay.addSpacing(5)
        line_lay.addWidget(QLabel("Avant groupe :"))
        line_lay.addWidget(group_trait)
        line_lay.addSpacing(5)
        line_lay.addWidget(QLabel("Sous en-tête :"))
        line_lay.addWidget(header_trait)
        line_lay.addStretch(1)

        grid.addWidget(QLabel("Traits :"), line_row, 0)
        grid.addWidget(line_box, line_row, 1, 1, 7)

        page.advanced_detail_borders_widget = borders
        page.advanced_detail_trait_widget = detail_trait
        page.advanced_group_trait_widget = group_trait
        page.advanced_header_trait_widget = header_trait

        # Alias Niveau 1 conservés pour compatibilité interne.
        page.advanced_font_size_widget = page.advanced_typography_widgets["level1"]["size"]
        page.advanced_italic_widget = page.advanced_typography_widgets["level1"]["italic"]
        page.advanced_underline_widget = page.advanced_typography_widgets["level1"]["underline"]
        page.advanced_align_widget = page.advanced_typography_widgets["level1"]["align"]

        box.setVisible(False)
        page.advanced_editor_box = box
        box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        box.adjustSize()
        box.setMaximumHeight(box.sizeHint().height() + 4)
        return box

    def _ordered_summary_totals(self, page):
        selected = set(getattr(page, "summary_metric_fields", set()) or set())
        if getattr(page, "summary_show_records_metric_widget", None) is not None and page.summary_show_records_metric_widget.isChecked():
            selected.add("__records__")
        palette = getattr(page, "summary_fields_widget", None)
        fallback = [str(palette.item(i).data(Qt.ItemDataRole.UserRole)) for i in range(palette.count())] if palette is not None else []
        if "__records__" in selected and "__records__" not in fallback:
            fallback.append("__records__")
        order = [str(f) for f in (getattr(page, "summary_metric_order", []) or [])]
        return list(dict.fromkeys(f for f in order + fallback if f in selected))

    def _refresh_summary_level_preview(self, page) -> None:
        """Miniature des regroupements et des champs réellement choisis."""
        if not hasattr(page, "summary_level1_sample"):
            return

        def label_for(field):
            if self._is_date_field(field):
                mode = str(page.date_group_mode_widget.currentData() or "full_date")
                if mode == "year":
                    return "Année"
                if mode == "month":
                    return "Mois"
                if mode == "year_month":
                    return "Année + mois"
            return self.labels.get(str(field), str(field or ""))

        def styled(widget, key, text):
            g = getattr(page, "advanced_typography_widgets", {}).get(key, {})
            size = g["size"].value() if g else (11 if key == "level1" else 10)
            bold = g["bold"].isChecked() if g else True
            italic = g["italic"].isChecked() if g else False
            underline = g["underline"].isChecked() if g else False
            align = str(g["align"].currentData() or "left") if g else "left"
            text_color = str(g["text_color"].property("mm3Color") or "#111111") if g else "#111111"
            bg_color = str(g["bg_color"].property("mm3Color") or "#F4F6F5") if g else "#FFFFFF"
            family = (
                g["font"].currentFont().family()
                if g and "font" in g
                else "Calibri"
            )
            font = QFont()
            font.setFamily(family)
            font.setPointSize(int(size)); font.setBold(bool(bold))
            font.setItalic(bool(italic)); font.setUnderline(bool(underline))
            widget.setFont(font)
            widget.setAlignment(
                (Qt.AlignHCenter if align == "center" else Qt.AlignRight if align == "right" else Qt.AlignLeft)
                | Qt.AlignVCenter
            )
            widget.setStyleSheet(
                "QLabel { "
                f"color: {text_color}; "
                f"background-color: {bg_color}; "
                "border: 1px solid #aab7b1; "
                "padding: 3px 7px; "
                "}"
            )
            widget.setText(text)

        selected = []
        sw = getattr(page, "summary_fields_widget", None)
        if sw is not None:
            for i in range(sw.count()):
                item = sw.item(i)
                field = str(item.data(Qt.ItemDataRole.UserRole))
                pair = getattr(page, "summary_field_row_widgets", {}).get(field)
                if pair is None or not pair[0].isChecked():
                    continue
                label = self.labels.get(field, str(item.data(Qt.ItemDataRole.UserRole + 1) or field))
                treatment = getattr(page, "summary_treatments", {}).get(field)
                if treatment == "sum": selected.append(f"{label} : somme 12")
                elif treatment == "avg": selected.append(f"{label} : moyenne 4,2")
                elif treatment == "min": selected.append(f"{label} : minimum 1")
                elif treatment == "max": selected.append(f"{label} : maximum 9")
                elif treatment == "count_distinct": selected.append(f"{label} : 3 distinct(s)")
                elif treatment == "list": selected.append(f"{label} : A, B, C")
                else: selected.append(label)
        suffix = (" — " + " — ".join(selected)) if selected else ""

        if hasattr(page, "summary_header_sample"):
            lay = getattr(page, "summary_header_sample_layout", None)
            if lay is not None:
                lay.setEnabled(True)
                while lay.count():
                    item = lay.takeAt(0)
                    widget = item.widget()
                    if widget is not None:
                        widget.deleteLater()

                band_st = dict(getattr(page, "summary_band_style", {}) or {})
                if str(band_st.get("align") or "left") in {"center", "right"}: lay.addStretch(1)
                def add_metric_label(number_text, label_text, family, size, text_color, field=None):
                    key = str(field or "")
                    st = dict(getattr(page, "summary_metric_styles", {}).get(key) or {}) if key else {}
                    value_st = dict(st.get("value") or {})
                    label_st = dict(st.get("label") or {})
                    base_family = str(band_st.get("font") or family or "Calibri")
                    base_size = int(band_st.get("size", size))
                    base_color = str(band_st.get("text") or text_color)
                    vf = str(value_st.get("font") or base_family); vs = int(value_st.get("size", base_size)); vc = str(value_st.get("text") or base_color)
                    vb = bool(value_st.get("bold", band_st.get("bold", True))); vi = bool(value_st.get("italic", band_st.get("italic", False)))
                    lf = str(label_st.get("font") or base_family); ls = int(label_st.get("size", base_size)); lc = str(label_st.get("text") or base_color)
                    lb = bool(label_st.get("bold", band_st.get("bold", True))); li = bool(label_st.get("italic", band_st.get("italic", False)))
                    html = (f"<span style='font-family:{_escape(vf)};font-size:{vs}pt;color:{vc};font-weight:{700 if vb else 400};font-style:{'italic' if vi else 'normal'}'>{_escape(str(number_text))}</span>"
                            f"<span style='font-family:{_escape(lf)};font-size:{ls}pt;color:{lc};font-weight:{700 if lb else 400};font-style:{'italic' if li else 'normal'};white-space:pre;'> {_escape(str(label_text))}</span>")
                    lbl = SummaryMetricLabel(html, key, page.summary_header_sample); lbl.setTextFormat(Qt.TextFormat.RichText)
                    lbl.setStyleSheet("QLabel { background:transparent; border:0; padding:0; }")
                    if field:
                        lbl.setContextMenuPolicy(Qt.CustomContextMenu)
                        def _edit_style(f):
                            cur = dict(getattr(page, "summary_metric_styles", {}).get(f) or {})
                            dlg=QDialog(self); dlg.setWindowTitle(tr("Mise en forme du total", self.language))
                            form=QFormLayout(dlg)
                            controls=[]
                            for title, part in (("Valeur", "value"),("Libellé", "label")):
                                ps=dict(cur.get(part) or {})
                                ff=QFontComboBox(); ff.setCurrentFont(QFont(str(ps.get("font") or base_family)))
                                sz=QSpinBox(); sz.setRange(7,36); sz.setValue(int(ps.get("size",base_size)))
                                bo=QCheckBox(tr("Gras", self.language)); bo.setChecked(bool(ps.get("bold", band_st.get("bold",True))))
                                it=QCheckBox(tr("Italique", self.language)); it.setChecked(bool(ps.get("italic", band_st.get("italic",False))))
                                co=QPushButton(tr("Choisir…", self.language)); co.setProperty("mm3Color",str(ps.get("text") or base_color))
                                def choose(_checked=False, btn=co):
                                    c=mm3_choose_color(dlg, QColor(str(btn.property("mm3Color") or "#000000")), "Couleur du texte")
                                    if c is not None and c.isValid(): btn.setProperty("mm3Color",c.name())
                                co.clicked.connect(choose)
                                form.addRow(f"{title} — Police :",ff); form.addRow(f"{title} — Taille :",sz)
                                flags=QWidget(); fl=QHBoxLayout(flags); fl.setContentsMargins(0,0,0,0); fl.addWidget(bo); fl.addWidget(it); fl.addStretch(1); form.addRow(f"{title} — Style :",flags); form.addRow(f"{title} — Couleur :",co)
                                controls.append((part,ff,sz,bo,it,co))
                            bb=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel); form.addRow(bb); bb.accepted.connect(dlg.accept); bb.rejected.connect(dlg.reject)
                            if dlg.exec()==QDialog.DialogCode.Accepted:
                                out={}
                                for part,ff,sz,bo,it,co in controls:
                                    out[part]={"font":ff.currentFont().family(),"size":sz.value(),"bold":bo.isChecked(),"italic":it.isChecked(),"text":str(co.property("mm3Color") or base_color)}
                                page.summary_metric_styles[f]=out; self._mark_builder_dirty(page); self._refresh_summary_level_preview(page)
                        def _metric_menu(pos, f=key, w=lbl):
                            menu=QMenu(w); edit=menu.addAction(tr("Modifier le libellé…", self.language)); style=menu.addAction(tr("Mise en forme du total…", self.language)); reset=menu.addAction(tr("Rétablir le libellé du champ", self.language))
                            chosen=menu.exec(w.mapToGlobal(pos))
                            if chosen==edit:
                                if f=="__records__": default=str(getattr(page,"summary_metric_labels",{}).get(f) or tr("fiche(s)", self.language))
                                else: default=str(getattr(page,"summary_metric_labels",{}).get(f) or (tr("pièce(s)", self.language) if f=="box_count" else self.labels.get(f,f).lower()+"(s)"))
                                value,ok=QInputDialog.getText(self,tr("Libellé du total", self.language),tr("Libellé affiché :", self.language),text=default)
                                if ok: page.summary_metric_labels[f]=str(value); self._mark_builder_dirty(page); self._refresh_summary_level_preview(page)
                            elif chosen==style: _edit_style(f)
                            elif chosen==reset: page.summary_metric_labels.pop(f,None); self._mark_builder_dirty(page); self._refresh_summary_level_preview(page)
                        lbl.customContextMenuRequested.connect(_metric_menu)
                    def resize_metric(metric_field, width):
                        page.summary_metric_widths[str(metric_field)] = max(55, min(480, int(width)))
                        if getattr(page, "summary_footer_linked", False) and hasattr(page, "refresh_summary_footer_sample"):
                            page.refresh_summary_footer_sample()
                        self._mark_builder_dirty(page)
                    lbl.enable_resize(resize_metric, page.summary_metric_widths.get(key))
                    def move_metric(metric_field, x):
                        page.summary_metric_positions[str(metric_field)] = max(0, int(x))
                        self._mark_builder_dirty(page)
                    lbl.enable_move(move_metric)
                    lbl.setToolTip(tr("Déplacer horizontalement à la souris ou avec ←/→ ; la poignée redimensionne uniquement la cellule", self.language))
                    lay.addWidget(lbl); page.summary_header_metric_labels.append(lbl)

                page.summary_header_metric_labels = []

                if page.summary_show_groups_metric_widget.isChecked():
                    gf = page.group_widget.currentData()
                    gl = page.summary_groups_label_widget.text().strip() or ("années" if gf in {"__acquisition_year__", "acquisition_date"} else "groupes")
                    add_metric_label(
                        "16",
                        gl,
                        page.summary_groups_font_widget.currentFont().family(),
                        page.summary_groups_size_widget.value(),
                        str(
                            page.summary_groups_text_widget.property("mm3Color")
                            or "#8B3026"
                        ),
                    )

                if page.summary_show_selected_metrics_widget.isChecked():
                    sw = page.summary_fields_widget
                    for field in self._ordered_summary_totals(page):
                        if field == "__records__":
                            add_metric_label(
                                str(self._record_count(list(getattr(self, "records", []) or []))),
                                str(getattr(page, "summary_metric_labels", {}).get("__records__") or tr("fiche(s)", self.language)),
                                page.summary_records_font_widget.currentFont().family(),
                                page.summary_records_size_widget.value(),
                                str(page.summary_records_text_widget.property("mm3Color") or "#8B3026"),
                                "__records__",
                            )
                            continue
                        item = next((sw.item(i) for i in range(sw.count()) if str(sw.item(i).data(Qt.ItemDataRole.UserRole)) == field), None)
                        if item is None: continue
                        pair = getattr(page, "summary_field_row_widgets", {}).get(field)
                        if pair is None or field not in getattr(page, "summary_metric_fields", set()):
                            continue
                        treatment = self._summary_treatment(field, page.summary_treatments.get(field))
                        label = self.labels.get(field, str(item.data(Qt.ItemDataRole.UserRole + 1) or field)).lower()
                        custom_label = str(getattr(page, "summary_metric_labels", {}).get(field) or "")
                        records = list(getattr(self, "records", []) or [])
                        if treatment == "sum":
                            value = sum(self._summary_numeric_value(r, field) for r in records)
                            number = self._summary_total_text(field, value)
                        elif treatment == "avg":
                            values = [self._summary_numeric_value(r, field) for r in records]
                            number = self._summary_total_text(field, sum(values) / len(values)) if values else "0"
                        elif treatment == "min":
                            values = [self._summary_numeric_value(r, field) for r in records]
                            number = self._summary_total_text(field, min(values)) if values else "0"
                        elif treatment == "max":
                            values = [self._summary_numeric_value(r, field) for r in records]
                            number = self._summary_total_text(field, max(values)) if values else "0"
                        else:
                            # Un Total portant sur le champ maître Date doit utiliser
                            # exactement le même regroupement que la Vue de l'État.
                            # Ex. 59 dates distinctes regroupées par année => 14 années.
                            group_field = page.group_widget.currentData()
                            date_mode = str(page.date_group_mode_widget.currentData() or "full_date")
                            if (
                                field == group_field
                                and self._is_date_field(field)
                                and date_mode != "full_date"
                            ):
                                number = str(len(self._group_records(records, field, date_mode)))
                            else:
                                number = str(self._distinct_count(records, field))
                        add_metric_label(
                            number,
                            custom_label or (tr("pièce(s)", self.language) if field == "box_count" else label + "(s)"),
                            page.summary_selected_font_widget.currentFont().family(),
                            page.summary_selected_size_widget.value(),
                            str(
                                page.summary_selected_text_widget.property("mm3Color")
                                or "#8B3026"
                            ),
                            field,
                        )

                if page.summary_show_species_metric_widget.isChecked():
                    add_metric_label(
                        "23",
                        (page.summary_distinct_label_widget.text().strip() or page.summary_distinct_field_widget.currentText().strip().lower() or "valeurs"),
                        page.summary_species_font_widget.currentFont().family(),
                        page.summary_species_size_widget.value(),
                        str(
                            page.summary_species_text_widget.property("mm3Color")
                            or "#8B3026"
                        ),
                    )

                if page.summary_show_records_metric_widget.isChecked() and not page.summary_show_selected_metrics_widget.isChecked():
                    add_metric_label(
                        str(self._record_count(list(getattr(self, "records", []) or []))),
                        str(getattr(page, "summary_metric_labels", {}).get("__records__") or "fiche(s)"),
                        page.summary_records_font_widget.currentFont().family(),
                        page.summary_records_size_widget.value(),
                        str(
                            page.summary_records_text_widget.property("mm3Color")
                            or "#7A817D"
                        ),
                        "__records__",
                    )

                lay.addStretch(1)
                # 1.0.105 — figer le layout puis positionner chaque total par sa propre coordonnée X.
                # Redimensionner une cellule ne peut ainsi plus repousser ses voisines.
                lay.activate(); lay.setEnabled(False)
                _next_x = 6
                for _metric in page.summary_header_metric_labels:
                    _key = str(_metric.metric_field)
                    _x = int(getattr(page, "summary_metric_positions", {}).get(_key, _next_x))
                    page.summary_metric_positions.setdefault(_key, _x)
                    # 1.0.299 — Une police/libellé plus long ne doit jamais
                    # faire recouvrir le total suivant. Conserver les positions
                    # enregistrées, mais corriger l'affichage si elles se croisent.
                    _x = max(_x, _next_x if _metric is not page.summary_header_metric_labels[0] else 6)
                    page.summary_metric_positions[_key] = _x
                    _metric.move(max(0, _x), max(1, (page.summary_header_sample.height()-_metric.height())//2))
                    _metric.show(); _metric.raise_()
                    _next_x = max(_next_x, _x + _metric.width() + 8)

            common_bg = str(
                (getattr(page, "summary_band_style", {}) or {}).get("bg") or
                page.summary_groups_bg_widget.property("mm3Color")
                or page.summary_selected_bg_widget.property("mm3Color")
                or page.summary_species_bg_widget.property("mm3Color")
                or page.summary_records_bg_widget.property("mm3Color")
                or "#F4F6F5"
            )
            page.summary_header_sample.setStyleSheet(
                "#summaryHeaderSample {"
                f"background:{common_bg};"
                "border:1px solid #c2cdc8;"
                "}"
            )

        # En-tête de colonnes — 27.41 : rendu directement piloté par la
        # construction graphique. Les anciens widgets restent chargés uniquement
        # pour la compatibilité avec les modèles historiques.
        header_sample = getattr(page, "summary_column_header_sample", None)
        if header_sample is not None:
            graphic_master = str(getattr(page, "summary_graphic_master", None) or "")
            fields = ([graphic_master] if graphic_master else []) + [str(f) for f in list(getattr(page, "summary_graphic_secondaries", []) or [])[:4]]
            labels_map=dict(getattr(page,"summary_column_header_labels",{}) or {})
            styles_map=dict(getattr(page,"summary_column_header_styles",{}) or {})
            hidden_headers=set(getattr(page,"summary_column_header_hidden",set()) or set())
            parts=[]
            for f in fields:
                label="" if f in hidden_headers else str(labels_map.get(f) or (tr("Nombre de fiches", self.language) if f == "__records__" else self.labels.get(f,f)))
                st=dict(styles_map.get(f) or {})
                family=str(st.get("font_family") or "Calibri"); size=int(st.get("font_size",10)); weight="700" if bool(st.get("bold",True)) else "400"; italic="italic" if bool(st.get("italic",False)) else "normal"; deco="underline" if bool(st.get("underline",False)) else "none"; color=str(st.get("text_color") or "#111111"); bg=str(st.get("bg_color") or "#FFFFFF")
                if bg.upper() == "#DDE8E2": bg = "#FFFFFF"
                width=max(70,min(480,int(getattr(page,"summary_column_widths",{}).get(f) or (240 if f == graphic_master else 190))))
                parts.append(f'<td width="{width}" style="width:{width}px; font-family:{html.escape(family)}; font-size:{size}pt; font-weight:{weight}; font-style:{italic}; text-decoration:{deco}; color:{color}; background:{bg}; padding:2px 5px;">{html.escape(label)}</td>')
            header_sample.setProperty("gskolHeaderFields", fields)
            header_sample.setProperty("gskolHeaderWidths", [max(70,min(480,int(getattr(page,"summary_column_widths",{}).get(f) or (240 if f == graphic_master else 190)))) for f in fields])
            header_sample.setTextFormat(Qt.TextFormat.RichText)
            header_sample.setText('<table cellspacing="0" cellpadding="0"><tr>' + ''.join(parts) + '</tr></table>' if parts else "")
            header_sample.setAlignment(Qt.AlignHCenter|Qt.AlignVCenter)
            header_sample.setStyleSheet("QLabel { background:#FFFFFF; border:1px solid #aab7b1; padding:3px 7px; }")

        def styled_new(widget, key, text, default_align):
            g = getattr(page, "advanced_typography_widgets", {}).get(key, {})
            if not g:
                return
            family = (
                g["font"].currentFont().family()
                if "font" in g else "Calibri"
            )
            font = QFont()
            font.setFamily(family)
            font.setPointSize(int(g["size"].value()))
            font.setBold(g["bold"].isChecked())
            font.setItalic(g["italic"].isChecked())
            font.setUnderline(g["underline"].isChecked())
            widget.setFont(font)

            align = str(g["align"].currentData() or default_align)
            widget.setAlignment(
                (Qt.AlignHCenter if align == "center"
                 else Qt.AlignRight if align == "right"
                 else Qt.AlignLeft) | Qt.AlignVCenter
            )
            text_color = str(
                g["text_color"].property("mm3Color") or "#111111"
            )
            bg_color = str(
                g["bg_color"].property("mm3Color") or "#FFFFFF"
            )
            widget.setStyleSheet(
                "QLabel {"
                f"color:{text_color}; background:{bg_color};"
                "border:1px solid #aab7b1; padding:3px 7px;"
                "}"
            )
            widget.setText(text)

        primary = page.group_widget.currentData()
        master_text = (
            "2011"
            if primary in {"__acquisition_year__", "acquisition_date"}
            else f"{label_for(primary) or 'Groupe'} : exemple"
        )
        if not isinstance(page.summary_level1_sample, SummaryDropLane):
            styled_new(
                page.summary_level1_sample,
                "summary_master",
                master_text,
                "right",
            )

        secondary_examples = []
        sw = getattr(page, "summary_fields_widget", None)
        if sw is not None:
            for i in range(sw.count()):
                item = sw.item(i)
                field = str(item.data(Qt.ItemDataRole.UserRole))
                pair = getattr(page, "summary_field_row_widgets", {}).get(field)
                if pair is not None and pair[0].isChecked():
                    treatment = getattr(page, "summary_treatments", {}).get(field)
                    if treatment == "sum":
                        value = "46"
                    elif treatment == "count_distinct":
                        value = "3"
                    elif treatment == "list":
                        value = "A, B, C"
                    else:
                        value = "exemple"
                    _lbl = self.labels.get(field, str(item.data(Qt.ItemDataRole.UserRole + 1) or field))
                    secondary_examples.append(f"{_lbl} : {value}")
                if len(secondary_examples) >= 2:
                    break

        if not isinstance(page.summary_level2_sample, SummaryDropLane):
            styled_new(
                page.summary_level2_sample,
                "summary_secondary",
                "   |   ".join(secondary_examples) if secondary_examples else "Aucun champ secondaire",
                "left",
            )


    def _refresh_advanced_live_preview(self, kind: str, page) -> None:
        """Met à jour immédiatement l'aperçu dynamique de l'Atelier."""
        if getattr(page, "_loading_state", False):
            return
        if kind == "detail":
            self._refresh_atelier_sample(page)
        else:
            self._refresh_summary_level_preview(page)


    def closeEvent(self, event) -> None:
        """La croix Windows suit exactement la même règle que le bouton Retour."""
        page = self.stack.currentWidget() if hasattr(self, "stack") else None
        if page is not None and str(page.property("kind") or "") in {"detail", "summary"}:
            if not self._confirm_leave_builder(page):
                event.ignore()
                return
        event.accept()


    def _confirm_leave_builder(self, page) -> bool:
        """Retourne True si la sortie est autorisée, après éventuelle sauvegarde."""
        if page is None:
            return True

        kind = str(page.property("kind") or "")
        if kind not in {"detail", "summary"}:
            return True

        # Le vrai indicateur MM3 est le bouton Sauvegarder activé OU un flag dirty.
        save_button = getattr(page, "builder_save_button", None)
        dirty = bool(getattr(page, "_builder_dirty", False))
        if save_button is not None and save_button.isEnabled():
            dirty = True

        if not dirty:
            return True

        dialog = QDialog(self)
        dialog.setWindowTitle(tr("Enregistrer les modifications", self.language))
        dialog.setModal(True)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        layout.addWidget(QLabel(tr("L’état a été modifié.", self.language)))

        form = QFormLayout()
        name_edit = QLineEdit()
        current_name = str(getattr(page, "editing_report_name", "") or "").strip()
        if not current_name:
            current_name = str(page.title_widget.text() or "").strip()
            if current_name in {"État détaillé", "État résumé", "État"}:
                current_name = ""
        name_edit.setText(current_name)
        name_edit.setMinimumWidth(360)
        form.addRow(tr("Nom de l’état :", self.language), name_edit)
        layout.addLayout(form)

        layout.addWidget(QLabel(tr("Enregistrer les modifications ?", self.language)))

        row = QHBoxLayout()
        row.addStretch(1)
        yes_btn = QPushButton(tr("Oui", self.language))
        no_btn = QPushButton(tr("Non", self.language))
        cancel_btn = QPushButton(tr("Annuler", self.language))
        row.addWidget(yes_btn)
        row.addWidget(no_btn)
        row.addWidget(cancel_btn)
        layout.addLayout(row)

        action = {"value": None}
        yes_btn.clicked.connect(lambda: (action.__setitem__("value", "yes"), dialog.accept()))
        no_btn.clicked.connect(lambda: (action.__setitem__("value", "no"), dialog.accept()))
        cancel_btn.clicked.connect(dialog.reject)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return False

        if action["value"] == "no":
            return True

        if action["value"] != "yes":
            return False

        new_name = name_edit.text().strip()
        if not new_name:
            QMessageBox.information(self, "Nom requis", "Indiquez un nom pour enregistrer l’état.")
            return False

        definition = self._definition_from_builder(kind, page)
        old_name = str(getattr(page, "editing_report_name", "") or "").strip()

        if old_name and old_name != new_name:
            self.saved_reports.pop(old_name, None)
            self.report_custom_order = [
                new_name if item == old_name else item
                for item in self.report_custom_order
            ]

        self.saved_reports[new_name] = definition
        if new_name not in self.report_custom_order:
            self.report_custom_order.append(new_name)

        page.editing_report_name = new_name
        self.current_edit_report_name = new_name
        self._write_saved_reports()
        self._refresh_saved_reports_list()
        self._reset_builder_state(page)
        return True


    def _return_from_builder(self) -> bool:
        page = self.stack.currentWidget()
        if not self._confirm_leave_builder(page):
            # 1.0.128 — Annuler signifie rester exactement dans le constructeur.
            return False
        self.stack.setCurrentIndex(0)
        self.report_page_subtitle.setVisible(True)
        return True


    def closeEvent(self, event) -> None:
        """La croix Windows respecte la même sécurité que le bouton Retour."""
        page = self.stack.currentWidget()
        kind = str(page.property("kind") or "") if page is not None else ""
        if kind in {"detail", "summary"} and bool(getattr(page, "builder_dirty", False)):
            if self._return_from_builder() is False:
                event.ignore()
                return
        event.accept()

    def _set_builder_context_visibility(self, page) -> None:
        """Un même éditeur complet depuis Collection et depuis Atelier."""
        advanced = getattr(page, "advanced_editor_box", None)
        if advanced is not None:
            # État détaillé : le panneau Réglages avancés fait désormais
            # partie intégrante de l'éditeur, quel que soit le point d'entrée.
            advanced.setVisible(True)

        # Même géométrie dans les deux contextes : seule la destination du
        # bouton Retour dépend du point d'entrée, pas le contenu de l'éditeur.
        main_layout = getattr(page, "builder_main_layout", None)
        if main_layout is not None:
            main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
            main_layout.setContentsMargins(0, 2, 0, 2)
            main_layout.setSpacing(3)

    def _build_builder(self, kind: str) -> QWidget:
        # Premier jalon : le détail reprend exactement le constructeur graphique
        # résumé. L'adaptation du moteur de sortie viendra ensuite.
        detail_clone = kind == "detail"
        if detail_clone:
            kind = "summary"
        page = QWidget()
        page.setProperty("kind", "detail" if detail_clone else kind)
        page.detail_summary_clone = detail_clone
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        lay.setAlignment(Qt.AlignmentFlag.AlignTop)
        page.builder_main_layout = lay

        # Barre de travail compacte : une seule ligne au lieu de deux.
        workbar = QHBoxLayout()
        workbar.setContentsMargins(0, 0, 0, 0)
        workbar.setSpacing(6)

        heading = QLabel(tr("État détaillé" if detail_clone else "État résumé", self.language))
        heading.setObjectName("sectionTitle")
        page.builder_banner_label = heading
        workbar.addWidget(heading)

        workbar.addSpacing(8)
        source_label = QLabel(tr("Source :", self.language))
        workbar.addWidget(source_label)

        source = QComboBox()
        source.setFixedHeight(28)
        source.setMinimumWidth(260)
        source.addItem("Toute la collection", None)
        for name in sorted(self.saved_queries, key=str.casefold):
            source.addItem(f"{tr('Requête enregistrée :', self.language)} {name}", name)
        workbar.addWidget(source, 1)
        page.source_widget = source

        workbar.addSpacing(8)
        workbar.addWidget(QLabel(tr("Orientation :", self.language)))
        portrait = QRadioButton(tr("Portrait", self.language))
        landscape = QRadioButton(tr("Paysage", self.language))
        try:
            default_orientation = self.model_manager.collection_preferences(
                int(self.collection["id"])
            )["report_orientation"]
        except Exception:
            default_orientation = "portrait"
        (landscape if default_orientation == "landscape" else portrait).setChecked(True)
        page.portrait_widget = portrait
        page.landscape_widget = landscape
        page.editing_report_name = None
        workbar.addWidget(portrait)
        workbar.addWidget(landscape)
        workbar.addStretch(1)
        lay.addLayout(workbar)

        # Le titre technique reste disponible pour la logique d'état,
        # mais n'occupe aucune ligne de l'écran.
        title = QLineEdit()
        title.setText("État détaillé" if detail_clone else "État résumé")
        title.setVisible(False)
        page.title_widget = title

        if kind == "detail":
            box = QGroupBox("Champs à afficher")
            box.setMaximumWidth(300)
            boxlay = QHBoxLayout(box)
            boxlay.setContentsMargins(7, 4, 7, 5)
            fields = QListWidget()
            fields.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
            fields.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
            fields.setDefaultDropAction(Qt.DropAction.MoveAction)
            fields.setDragEnabled(True)
            fields.setAcceptDrops(True)
            fields.setDropIndicatorShown(True)
            fields.model().rowsMoved.connect(lambda *_: self._mark_builder_dirty(page))
            defaults = {
                field for _label, field in self.fields[:5]
            }
            for label, field in sorted(self.fields, key=lambda pair: field_sort_key(pair[0])):
                item = QListWidgetItem(label)
                # Le QListWidget peignait encore son texte natif sous le QWidget de ligne,
                # d’où l’impression de deux polices superposées. On conserve item.text()
                # pour le moteur, mais on rend uniquement ce texte natif transparent.
                item.setForeground(QBrush(QColor(0, 0, 0, 0)))
                item.setData(Qt.ItemDataRole.UserRole, field)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked if field in defaults else Qt.CheckState.Unchecked)
                fields.addItem(item)
            note = QLabel(
                "Choisissez les champs. Leur ordre, leur largeur et le tri se règlent "
                "ensuite directement dans l’aperçu."
            )
            note.setWordWrap(True)
            boxlay.addWidget(fields, 1)
            note.setVisible(False)
            fields.setMaximumHeight(136)
            fields.setMinimumWidth(235)
            box.setMaximumHeight(165)
            page.fields_widget = fields

            # Réglage fin : justification de chaque colonne de détail.
            page.detail_column_alignments = {}

            grouping_box = QGroupBox("Regroupements")
            grouping_box.setMaximumWidth(360)
            grouping_grid = QGridLayout(grouping_box)
            grouping_grid.setContentsMargins(8, 4, 8, 4)
            grouping_grid.setHorizontalSpacing(5)
            grouping_grid.setVerticalSpacing(2)
            grouping_widgets = []

            grouping_inline_note = QLabel(
                "Exemples : Année d’acquisition → Contact ; Pays → Site ; "
                "Couleur → Forme. Chaque niveau affiche ses propres totaux."
            )
            grouping_inline_note.setStyleSheet(
                "color:#6F7773; font-weight:400;"
            )
            grouping_inline_note.setWordWrap(False)
            grouping_grid.addWidget(grouping_inline_note, 0, 1, 1, 3)

            atelier = QGroupBox("Atelier visuel")
            atelier_grid = QGridLayout(atelier)
            atelier_grid.setContentsMargins(7, 3, 7, 4)
            atelier_grid.setHorizontalSpacing(5)
            atelier_grid.setVerticalSpacing(2)
            atelier.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Maximum,
            )

            def make_color_button(text, color):
                button = QPushButton(text)
                button.setProperty("mm3Color", color)
                def apply_style(value):
                    foreground = "#F4F4F4" if QColor(value).lightness() < 120 else "#111111"
                    button.setStyleSheet(
                        "QPushButton {"
                        f" background-color:{value}; color:{foreground};"
                        " min-width:48px; max-width:60px; padding:2px 4px; font-weight:600;}"
                        "QPushButton:hover {"
                        f" background-color:{value}; color:{foreground};}}"
                    )
                apply_style(color)
                def choose_color():
                    dialog=QColorDialog(QColor(str(button.property("mm3Color"))),self)
                    dialog.setWindowTitle("Couleur")
                    translations={"Basic colors":"Couleurs de base","Custom colors":"Couleurs personnalisées","Pick Screen Color":"Choisir une couleur à l’écran","Add to Custom Colors":"Ajouter aux couleurs personnalisées","Hue:":"Teinte :","Sat:":"Saturation :","Val:":"Valeur :","Red:":"Rouge :","Green:":"Vert :","Blue:":"Bleu :","HTML:":"HTML :"}
                    for child in dialog.findChildren(QLabel):
                        key=child.text().replace("&","")
                        if key in translations: child.setText(translations[key])
                    for child in dialog.findChildren(QPushButton):
                        key=child.text().replace("&","")
                        if key in translations: child.setText(translations[key])
                        elif key=="Cancel": child.setText("Annuler")
                    for box in dialog.findChildren(QDialogButtonBox):
                        cancel=box.button(QDialogButtonBox.StandardButton.Cancel)
                        if cancel is not None: cancel.setText("Annuler")
                        ok=box.button(QDialogButtonBox.StandardButton.Ok)
                        if ok is not None: ok.setText("OK")
                    delete_custom=QPushButton("Supprimer une couleur personnalisée",dialog)
                    delete_custom.clicked.connect(lambda: self._delete_custom_color(dialog))
                    if dialog.layout() is not None:
                        dialog.layout().addWidget(delete_custom)
                    result=dialog.exec()
                    self._save_custom_color_palette()
                    if result==QDialog.DialogCode.Accepted:
                        chosen=dialog.currentColor()
                        if chosen.isValid():
                            button.setProperty("mm3Color",chosen.name())
                            apply_style(chosen.name())
                            self._refresh_atelier_sample(page)
                            self._mark_builder_dirty(page)
                button.clicked.connect(choose_color)
                return button

            level1=make_color_button("Texte","#9A3324")
            level2=make_color_button("Texte","#111111")
            level3=make_color_button("Texte","#737B77")
            level1_bg=make_color_button("Fond","#C8D8D0")
            level2_bg=make_color_button("Fond","#DDE8E2")
            level3_bg=make_color_button("Fond","#EEF3F0")
            repeat_color=make_color_button("Champ répété","#9A3324")
            page.atelier_level1_color=level1; page.atelier_level2_color=level2
            page.atelier_level3_color=level3; page.atelier_repeat_color=repeat_color
            page.atelier_level1_bg=level1_bg; page.atelier_level2_bg=level2_bg; page.atelier_level3_bg=level3_bg

            grouping_grid.addWidget(QLabel("Regroupement"),1,1)

            for level,(color_button,bg_button) in enumerate(((level1,level1_bg),(level2,level2_bg),(level3,level3_bg))):
                combo=QComboBox(); combo.setMinimumWidth(165); combo.setMaximumWidth(235)
                combo.addItem("Aucun",None)
                if any(field == "acquisition_date" for _label, field in self.fields):
                    combo.addItem("Année d’acquisition","__acquisition_year__")
                for label,field in self.fields:
                    if field not in {"description"}: combo.addItem(label,field)
                grouping_grid.addWidget(QLabel(f"Niveau {level+1} :"),level+2,0)
                grouping_grid.addWidget(combo,level+2,1)
                grouping_widgets.append(combo)

            spacing=QSpinBox()
            spacing.setRange(0,5)
            spacing.setValue(2)
            spacing.setSuffix(" ligne(s)")
            spacing.setMaximumWidth(130)
            page.atelier_spacing_widget=spacing

            grouping_grid.addWidget(
                QLabel("Espaces entre les groupes maîtres :"),
                5, 0
            )
            grouping_grid.addWidget(spacing, 5, 1)
            page.detail_grouping_widgets=grouping_widgets

            # Aperçu dynamique déplacé à droite du bloc Regroupements.
            preview_box = QGroupBox("Aperçu dynamique")
            preview_lay = QVBoxLayout(preview_box)
            preview_lay.setContentsMargins(7, 5, 7, 7)

            sample = QLabel()
            sample.setTextFormat(Qt.TextFormat.RichText)
            sample.setFrameShape(QFrame.Shape.StyledPanel)
            sample.setMinimumHeight(190)
            sample.setMaximumHeight(245)
            sample.setMinimumWidth(310)
            sample.setWordWrap(True)
            preview_lay.addWidget(sample)

            page.atelier_sample = sample
            page.atelier_preview_box = preview_box
            preview_box.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Maximum,
            )
            preview_box.setMinimumWidth(470)
            preview_box.setMaximumWidth(650)

            compact_row = QHBoxLayout()
            compact_row.setSpacing(5)
            compact_row.addWidget(box, 0)
            compact_row.addWidget(grouping_box, 1)
            compact_row.addWidget(preview_box, 2)
            lay.addLayout(compact_row)

            alignment_box = QGroupBox("Alignement des colonnes de détail")
            alignment_row = QHBoxLayout(alignment_box)
            alignment_row.setContentsMargins(7, 2, 7, 3)
            alignment_row.setSpacing(5)

            alignment_field = QComboBox()
            alignment_field.setMinimumWidth(230)
            alignment_choice = QComboBox()
            alignment_choice.addItem(tr("Gauche", self.language), "left")
            alignment_choice.addItem(tr("Centré", self.language), "center")
            alignment_choice.addItem(tr("Droite", self.language), "right")
            alignment_choice.setMinimumWidth(115)

            alignment_row.addWidget(QLabel("Colonne :"))
            alignment_row.addWidget(alignment_field)
            alignment_row.addWidget(QLabel("Alignement :"))
            alignment_row.addWidget(alignment_choice)
            alignment_row.addStretch(1)

            page.detail_alignment_field_widget = alignment_field
            page.detail_alignment_choice_widget = alignment_choice

            def refresh_detail_alignment_fields():
                previous = alignment_field.currentData()
                alignment_field.blockSignals(True)
                alignment_field.clear()
                for i in range(fields.count()):
                    item = fields.item(i)
                    if item.checkState() == Qt.CheckState.Checked:
                        field = str(item.data(Qt.ItemDataRole.UserRole))
                        alignment_field.addItem(item.text(), field)
                alignment_field.blockSignals(False)

                if alignment_field.count() == 0:
                    alignment_choice.setEnabled(False)
                    return

                idx = alignment_field.findData(previous)
                alignment_field.setCurrentIndex(idx if idx >= 0 else 0)
                alignment_choice.setEnabled(True)
                field = str(alignment_field.currentData())
                saved = page.detail_column_alignments.get(field, "left")
                pos = alignment_choice.findData(saved)
                alignment_choice.blockSignals(True)
                alignment_choice.setCurrentIndex(pos if pos >= 0 else 0)
                alignment_choice.blockSignals(False)

            def refresh_detail_alignment_choice():
                if alignment_field.count() == 0:
                    return
                field = str(alignment_field.currentData())
                saved = page.detail_column_alignments.get(field, "left")
                pos = alignment_choice.findData(saved)
                alignment_choice.blockSignals(True)
                alignment_choice.setCurrentIndex(pos if pos >= 0 else 0)
                alignment_choice.blockSignals(False)

            def store_detail_alignment():
                if alignment_field.count() == 0:
                    return
                field = str(alignment_field.currentData())
                page.detail_column_alignments[field] = str(
                    alignment_choice.currentData() or "left"
                )
                self._mark_builder_dirty(page)

            fields.itemChanged.connect(lambda *_: refresh_detail_alignment_fields())
            alignment_field.currentIndexChanged.connect(
                lambda *_: refresh_detail_alignment_choice()
            )
            alignment_choice.currentIndexChanged.connect(
                lambda *_: store_detail_alignment()
            )

            refresh_detail_alignment_fields()
            alignment_box.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Maximum,
            )
            alignment_box.setMaximumHeight(74)

            # Le réglage d'espace est maintenant intégré au bloc Regroupements,
            # aligné sous Niveau 1 / 2 / 3.
            # Nouvelle présentation cosmétique :
            # Alignement des colonnes + Structure sur une même ligne.
            structure_alignment_row = QWidget()
            structure_alignment_lay = QHBoxLayout(structure_alignment_row)
            structure_alignment_lay.setContentsMargins(0, 0, 0, 0)
            structure_alignment_lay.setSpacing(8)

            structure_box = QGroupBox("Structure")
            structure_box.setMaximumHeight(74)
            structure_lay = QHBoxLayout(structure_box)
            structure_lay.setContentsMargins(7, 3, 7, 4)
            structure_lay.setSpacing(6)

            repeat_master=QComboBox(); repeat_master.addItem("Ne pas répéter de champ",None)
            for label,field in self.fields:
                if field not in {"description"}: repeat_master.addItem(f"Répéter en 1re colonne : {label}",field)
            repeat_master.setMinimumWidth(250)
            repeat_master.setMaximumWidth(390)
            repeat_master.setFixedHeight(27)
            structure_lay.addWidget(repeat_master, 1)
            structure_lay.addWidget(repeat_color, 0)
            structure_lay.addStretch(1)
            page.atelier_repeat_master_widget=repeat_master


            alignment_box.setMinimumWidth(470)
            structure_box.setMinimumWidth(350)
            structure_alignment_lay.addWidget(alignment_box, 3)
            structure_alignment_lay.addWidget(structure_box, 2)

            atelier_grid.addWidget(structure_alignment_row, 0, 0, 1, 16)

            totals_title=QLabel("Bandeau d’En-tête / Totaux")
            totals_title.setStyleSheet("font-weight:700;")
            totals_title.setFixedHeight(18)
            atelier_grid.addWidget(totals_title, 1, 0, 1, 16)

            show_groups=QCheckBox("Groupes")
            show_boxes=QCheckBox("Nombre de pièces")
            show_species=QCheckBox("Valeurs distinctes")
            show_records=QCheckBox("Nombre de fiches")
            for check in (show_groups,show_boxes,show_species,show_records):
                check.setChecked(True)
                check.setFixedHeight(22)
                check.setFixedWidth(118)

            def metric_size(default):
                spin=QSpinBox()
                spin.setRange(8,24)
                spin.setValue(default)
                spin.setSuffix(" pt")
                spin.setFixedWidth(58)
                spin.setFixedHeight(25)
                spin.setSizePolicy(
                    QSizePolicy.Policy.Fixed,
                    QSizePolicy.Policy.Fixed,
                )
                return spin

            def metric_font():
                combo=QFontComboBox()
                combo.setCurrentFont(QFont("Calibri"))
                # Proportions du premier schéma validé :
                # assez large pour le nom + flèche native Windows/Qt.
                combo.setFixedWidth(132)
                combo.setFixedHeight(25)
                combo.setSizeAdjustPolicy(
                    QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
                )
                combo.setMinimumContentsLength(8)
                combo.setSizePolicy(
                    QSizePolicy.Policy.Fixed,
                    QSizePolicy.Policy.Fixed,
                )
                return combo

            def metric_check(letter):
                check=QCheckBox(letter)
                check.setFixedHeight(22)
                check.setFixedWidth(27)
                check.setStyleSheet("QCheckBox { spacing:3px; }")
                return check

            metric_groups_font=metric_font(); metric_boxes_font=metric_font()
            metric_species_font=metric_font(); metric_records_font=metric_font()

            metric_groups_size=metric_size(11); metric_boxes_size=metric_size(11)
            metric_species_size=metric_size(11); metric_records_size=metric_size(10)

            metric_groups_bold=metric_check("G"); metric_boxes_bold=metric_check("G")
            metric_species_bold=metric_check("G"); metric_records_bold=metric_check("G")
            metric_groups_italic=metric_check("I"); metric_boxes_italic=metric_check("I")
            metric_species_italic=metric_check("I"); metric_records_italic=metric_check("I")
            metric_groups_underline=metric_check("S"); metric_boxes_underline=metric_check("S")
            metric_species_underline=metric_check("S"); metric_records_underline=metric_check("S")

            metric_groups_color=make_color_button("Texte","#8B3026")
            metric_boxes_color=make_color_button("Texte","#8B3026")
            metric_species_color=make_color_button("Texte","#8B3026")
            metric_records_color=make_color_button("Texte","#7A817D")
            metric_groups_bg=make_color_button("Fond","#F4F6F5")
            metric_boxes_bg=make_color_button("Fond","#F4F6F5")
            metric_species_bg=make_color_button("Fond","#F4F6F5")
            metric_records_bg=make_color_button("Fond","#F4F6F5")

            for button in (
                metric_groups_color,metric_boxes_color,
                metric_species_color,metric_records_color,
                metric_groups_bg,metric_boxes_bg,
                metric_species_bg,metric_records_bg,
            ):
                button.setFixedWidth(58)
                button.setFixedHeight(25)

            # Deux groupes visuels nettement séparés :
            # [Groupes / Espèces]     [Boîtes / Fiches]
            left_metrics = QWidget()
            left_metrics_lay = QGridLayout(left_metrics)
            left_metrics_lay.setContentsMargins(0, 0, 0, 0)
            left_metrics_lay.setHorizontalSpacing(5)
            left_metrics_lay.setVerticalSpacing(5)
            left_metrics_lay.setColumnMinimumWidth(0, 118)
            left_metrics_lay.setColumnMinimumWidth(1, 132)
            left_metrics_lay.setColumnMinimumWidth(2, 58)
            left_metrics_lay.setColumnMinimumWidth(3, 27)
            left_metrics_lay.setColumnMinimumWidth(4, 27)
            left_metrics_lay.setColumnMinimumWidth(5, 27)
            left_metrics_lay.setColumnMinimumWidth(6, 58)
            left_metrics_lay.setColumnMinimumWidth(7, 58)

            left_metrics_lay.addWidget(show_groups, 0, 0)
            left_metrics_lay.addWidget(metric_groups_font, 0, 1)
            left_metrics_lay.addWidget(metric_groups_size, 0, 2)
            left_metrics_lay.addWidget(metric_groups_bold, 0, 3)
            left_metrics_lay.addWidget(metric_groups_italic, 0, 4)
            left_metrics_lay.addWidget(metric_groups_underline, 0, 5)
            left_metrics_lay.addWidget(metric_groups_color, 0, 6)
            left_metrics_lay.addWidget(metric_groups_bg, 0, 7)
            left_metrics_lay.addWidget(show_species, 1, 0)
            left_metrics_lay.addWidget(metric_species_font, 1, 1)
            left_metrics_lay.addWidget(metric_species_size, 1, 2)
            left_metrics_lay.addWidget(metric_species_bold, 1, 3)
            left_metrics_lay.addWidget(metric_species_italic, 1, 4)
            left_metrics_lay.addWidget(metric_species_underline, 1, 5)
            left_metrics_lay.addWidget(metric_species_color, 1, 6)
            left_metrics_lay.addWidget(metric_species_bg, 1, 7)

            right_metrics = QWidget()
            right_metrics_lay = QGridLayout(right_metrics)
            right_metrics_lay.setContentsMargins(0, 0, 0, 0)
            right_metrics_lay.setHorizontalSpacing(5)
            right_metrics_lay.setVerticalSpacing(5)
            right_metrics_lay.setColumnMinimumWidth(0, 118)
            right_metrics_lay.setColumnMinimumWidth(1, 132)
            right_metrics_lay.setColumnMinimumWidth(2, 58)
            right_metrics_lay.setColumnMinimumWidth(3, 27)
            right_metrics_lay.setColumnMinimumWidth(4, 27)
            right_metrics_lay.setColumnMinimumWidth(5, 27)
            right_metrics_lay.setColumnMinimumWidth(6, 58)
            right_metrics_lay.setColumnMinimumWidth(7, 58)

            right_metrics_lay.addWidget(show_boxes, 0, 0)
            right_metrics_lay.addWidget(metric_boxes_font, 0, 1)
            right_metrics_lay.addWidget(metric_boxes_size, 0, 2)
            right_metrics_lay.addWidget(metric_boxes_bold, 0, 3)
            right_metrics_lay.addWidget(metric_boxes_italic, 0, 4)
            right_metrics_lay.addWidget(metric_boxes_underline, 0, 5)
            right_metrics_lay.addWidget(metric_boxes_color, 0, 6)
            right_metrics_lay.addWidget(metric_boxes_bg, 0, 7)
            right_metrics_lay.addWidget(show_records, 1, 0)
            right_metrics_lay.addWidget(metric_records_font, 1, 1)
            right_metrics_lay.addWidget(metric_records_size, 1, 2)
            right_metrics_lay.addWidget(metric_records_bold, 1, 3)
            right_metrics_lay.addWidget(metric_records_italic, 1, 4)
            right_metrics_lay.addWidget(metric_records_underline, 1, 5)
            right_metrics_lay.addWidget(metric_records_color, 1, 6)
            right_metrics_lay.addWidget(metric_records_bg, 1, 7)


            # Bandeau / Totaux : deux moitiés équilibrées comme sur le
            # premier schéma validé, sans contrainte de colonnes imbriquées.
            totals_row = QWidget()
            totals_row_lay = QHBoxLayout(totals_row)
            totals_row_lay.setContentsMargins(0, 0, 0, 0)
            totals_row_lay.setSpacing(18)

            left_metrics.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Maximum,
            )
            right_metrics.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Maximum,
            )

            totals_row_lay.addWidget(left_metrics, 1)
            totals_row_lay.addWidget(right_metrics, 1)
            atelier_grid.addWidget(totals_row, 2, 0, 2, 16)

            page.atelier_show_groups=show_groups; page.atelier_show_boxes=show_boxes
            page.atelier_show_species=show_species; page.atelier_show_records=show_records
            page.atelier_metric_groups_font=metric_groups_font; page.atelier_metric_boxes_font=metric_boxes_font
            page.atelier_metric_species_font=metric_species_font; page.atelier_metric_records_font=metric_records_font
            page.atelier_metric_groups_size=metric_groups_size; page.atelier_metric_boxes_size=metric_boxes_size
            page.atelier_metric_species_size=metric_species_size; page.atelier_metric_records_size=metric_records_size
            page.atelier_metric_groups_bold=metric_groups_bold; page.atelier_metric_boxes_bold=metric_boxes_bold
            page.atelier_metric_species_bold=metric_species_bold; page.atelier_metric_records_bold=metric_records_bold
            page.atelier_metric_groups_italic=metric_groups_italic; page.atelier_metric_boxes_italic=metric_boxes_italic
            page.atelier_metric_species_italic=metric_species_italic; page.atelier_metric_records_italic=metric_records_italic
            page.atelier_metric_groups_underline=metric_groups_underline; page.atelier_metric_boxes_underline=metric_boxes_underline
            page.atelier_metric_species_underline=metric_species_underline; page.atelier_metric_records_underline=metric_records_underline
            page.atelier_metric_groups_color=metric_groups_color; page.atelier_metric_boxes_color=metric_boxes_color
            page.atelier_metric_species_color=metric_species_color; page.atelier_metric_records_color=metric_records_color
            page.atelier_metric_groups_bg=metric_groups_bg; page.atelier_metric_boxes_bg=metric_boxes_bg
            page.atelier_metric_species_bg=metric_species_bg; page.atelier_metric_records_bg=metric_records_bg

            for combo in grouping_widgets:
                combo.currentIndexChanged.connect(lambda *_: self._refresh_atelier_sample(page))
            for signal in (
                repeat_master.currentIndexChanged,spacing.valueChanged,
                show_groups.toggled,show_boxes.toggled,show_species.toggled,show_records.toggled,
                metric_groups_font.currentFontChanged,metric_boxes_font.currentFontChanged,
                metric_species_font.currentFontChanged,metric_records_font.currentFontChanged,
                metric_groups_size.valueChanged,metric_boxes_size.valueChanged,
                metric_species_size.valueChanged,metric_records_size.valueChanged,
                metric_groups_bold.toggled,metric_boxes_bold.toggled,
                metric_species_bold.toggled,metric_records_bold.toggled,
                metric_groups_italic.toggled,metric_boxes_italic.toggled,
                metric_species_italic.toggled,metric_records_italic.toggled,
                metric_groups_underline.toggled,metric_boxes_underline.toggled,
                metric_species_underline.toggled,metric_records_underline.toggled,
            ):
                signal.connect(lambda *_: self._refresh_atelier_sample(page))
            for button in (
                metric_groups_color,metric_boxes_color,metric_species_color,metric_records_color,
                metric_groups_bg,metric_boxes_bg,metric_species_bg,metric_records_bg,
            ):
                button.clicked.connect(
                    lambda _checked=False, p=page:
                        QTimer.singleShot(0, lambda p=p: self._refresh_atelier_sample(p))
                )
            lay.addWidget(atelier); self._refresh_atelier_sample(page)
        else:
            # État résumé : ordre logique spécifique.
            # D'abord les regroupements et leur présentation, puis les champs.
            # Le panneau historique reste le moteur interne de compatibilité.
            # Il n’est plus affiché, mais doit rester parenté à la page : sans parent,
            # Python le libère à la fin de _build_builder() et détruit ses QComboBox,
            # alors que l’Atelier graphique continue de les utiliser.
            grouping_box = QGroupBox("Regroupements", page)
            page.summary_legacy_grouping_box = grouping_box
            grouping_grid = QGridLayout(grouping_box)
            grouping_grid.setContentsMargins(8, 4, 8, 4)
            grouping_grid.setHorizontalSpacing(4)
            grouping_grid.setVerticalSpacing(2)

            defaults = {
                "level1": {"font_size": 11, "bold": True, "italic": False, "underline": False, "align": "left", "text_color": "#9A3324", "bg_color": "#C8D8D0"},
                "level2": {"font_size": 10, "bold": True, "italic": False, "underline": False, "align": "left", "text_color": "#111111", "bg_color": "#DDE8E2"},
            }
            page.advanced_typography_widgets = {}

            def make_color_button(label: str, color: str) -> QPushButton:
                button = QPushButton(label)
                button.setProperty("mm3Color", color)
                button.setFixedWidth(64)
                button.setFixedHeight(24)
                def apply_style(value: str) -> None:
                    q = QColor(value)
                    foreground = "#F4F4F4" if q.lightness() < 120 else "#111111"
                    button.setStyleSheet(
                        "QPushButton {"
                        f"background-color:{value}; color:{foreground};"
                        "padding:1px 3px; min-width:60px; max-width:64px;"
                        "border:1px solid #9aa9a3; border-radius:4px;}"
                    )
                def choose_color() -> None:
                    current = QColor(str(button.property("mm3Color") or color))
                    dialog = QColorDialog(current, self)
                    dialog.setWindowTitle("Choisir une couleur")
                    translations = {
                        "Basic colors": "Couleurs de base",
                        "Custom colors": "Couleurs personnalisées",
                        "Pick Screen Color": "Choisir une couleur à l’écran",
                        "Add to Custom Colors": "Ajouter aux couleurs personnalisées",
                        "Hue:": "Teinte :", "Sat:": "Saturation :", "Val:": "Valeur :",
                        "Red:": "Rouge :", "Green:": "Vert :", "Blue:": "Bleu :",
                        "HTML:": "HTML :",
                    }
                    for child in dialog.findChildren(QLabel):
                        key = child.text().replace("&", "")
                        if key in translations:
                            child.setText(translations[key])
                    for child in dialog.findChildren(QPushButton):
                        key = child.text().replace("&", "")
                        if key in translations:
                            child.setText(translations[key])
                        elif key == "Cancel":
                            child.setText("Annuler")
                        elif key == "OK":
                            child.setText("OK")
                    for bb in dialog.findChildren(QDialogButtonBox):
                        cancel = bb.button(QDialogButtonBox.StandardButton.Cancel)
                        if cancel is not None:
                            cancel.setText("Annuler")
                        ok = bb.button(QDialogButtonBox.StandardButton.Ok)
                        if ok is not None:
                            ok.setText("OK")
                    result = dialog.exec()
                    self._save_custom_color_palette()
                    if result == QDialog.DialogCode.Accepted:
                        chosen = dialog.currentColor()
                        if chosen.isValid():
                            button.setProperty("mm3Color", chosen.name())
                            apply_style(chosen.name())
                            self._mark_builder_dirty(page)
                            self._refresh_summary_level_preview(page)
                apply_style(color)
                button.clicked.connect(choose_color)
                return button

            # Les listes de champs sont toujours proposées A → Z.
            # Les choix fonctionnels (ici « Aucun ») restent en tête.
            grouping_fields = sorted(
                ((label, field) for label, field in self.fields if field not in {"description"}),
                key=lambda pair: field_sort_key(pair[0]),
            )

            group = QComboBox()
            group.addItem("Aucun", None)
            for label, field in grouping_fields:
                group.addItem(label, field)
            group.setCurrentIndex(0)
            group.setPlaceholderText("Aucun")

            second = QComboBox()
            second.addItem("Aucun", None)
            for label, field in grouping_fields:
                second.addItem(label, field)
            second.setCurrentIndex(0)

            date_mode = QComboBox()
            date_mode.addItem("Date complète", "full_date")
            date_mode.addItem("Année", "year")
            date_mode.addItem("Mois", "month")
            date_mode.addItem("Année + mois", "year_month")
            date_mode.setCurrentIndex(date_mode.findData("year"))

            grouping_grid.addWidget(
                QLabel("Exemples : Année → Contact ; Pays → Site ; Date → Mois."),
                0, 0, 1, 3
            )

            grouping_grid.addWidget(QLabel("Niveau 1 :"), 1, 0)
            grouping_grid.addWidget(group, 1, 1, 1, 2)

            grouping_grid.addWidget(QLabel("Niveau 2 :"), 2, 0)
            grouping_grid.addWidget(second, 2, 1, 1, 2)

            date_mode_label = QLabel("Découpage Date :")
            grouping_grid.addWidget(date_mode_label, 3, 0)
            grouping_grid.addWidget(date_mode, 3, 1, 1, 2)

            spacing = QSpinBox()
            spacing.setRange(0, 5)
            spacing.setValue(2)
            spacing.setSuffix(" ligne(s)")
            spacing.setMaximumWidth(120)
            grouping_grid.addWidget(
                QLabel("Espaces entre les groupes maîtres :"), 4, 0, 1, 2
            )
            grouping_grid.addWidget(spacing, 4, 2)
            page.summary_spacing_widget = spacing

            # Les réglages d'en-tête de colonnes sont créés ici mais affichés
            # plus bas dans le bloc "Détail des groupes maîtres".
            column_header_size = QSpinBox()
            column_header_size.setRange(6, 24)
            column_header_size.setValue(10)
            column_header_size.setSuffix(" pt")
            column_header_size.setMaximumWidth(72)

            column_header_bold = QCheckBox()
            column_header_bold.setChecked(True)
            column_header_italic = QCheckBox()
            column_header_underline = QCheckBox()
            for chk in (
                column_header_bold,
                column_header_italic,
                column_header_underline,
            ):
                chk.setFixedWidth(22)

            column_header_align = QComboBox()
            column_header_align.addItem(tr("Gauche", self.language), "left")
            column_header_align.addItem(tr("Centré", self.language), "center")
            column_header_align.addItem(tr("Droite", self.language), "right")
            column_header_align.setCurrentIndex(
                column_header_align.findData("center")
            )
            column_header_align.setMaximumWidth(105)

            column_header_text = make_color_button("Texte", "#111111")
            column_header_bg = make_color_button("Fond", "#DDE8E2")

            page.advanced_column_header_size_widget = column_header_size
            page.advanced_column_header_bold_widget = column_header_bold
            page.advanced_column_header_italic_widget = column_header_italic
            page.advanced_column_header_underline_widget = column_header_underline
            page.advanced_column_header_align_widget = column_header_align
            page.advanced_column_header_text_widget = column_header_text
            page.advanced_column_header_bg_widget = column_header_bg

            header_title = QLineEdit()
            header_title.setPlaceholderText("Titre facultatif du bandeau")
            header_title.setFixedHeight(24)
            separator = QCheckBox("Séparateur")
            separator.setChecked(True)
            separator.setFixedHeight(20)
            grouping_grid.addWidget(QLabel("Bandeau :"), 5, 0)
            grouping_grid.addWidget(header_title, 5, 1)
            grouping_grid.addWidget(separator, 5, 2)
            page.advanced_header_title_widget = header_title
            page.advanced_separator_widget = separator
            grouping_box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)

            # --- Atelier graphique résumé : palette + construction par glisser/déposer ---
            fields_box = QGroupBox(tr("Glisser un champ vers la construction", self.language))
            fields_box.setMaximumWidth(300)
            fields_lay = QVBoxLayout(fields_box)
            fields_lay.setContentsMargins(7, 5, 7, 6)
            fields_lay.setSpacing(4)

            palette_head = QWidget()
            palette_head_lay = QHBoxLayout(palette_head)
            palette_head_lay.setContentsMargins(4, 0, 4, 0)
            palette_head_lay.addStretch(1)
            _ht = QLabel(tr("Total", self.language))
            _ht.setAlignment(Qt.AlignmentFlag.AlignCenter)
            _ht.setFixedWidth(52)
            palette_head_lay.addWidget(_ht)
            # Compense la barre de défilement de la liste : « Total » est ainsi
            # centré exactement au-dessus de la colonne des cases.
            palette_head_lay.addSpacing(31)
            fields_lay.addWidget(palette_head)

            summary_fields = QListWidget()
            summary_fields.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
            summary_fields.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
            summary_fields.setDragEnabled(True)
            summary_fields.setAcceptDrops(False)
            summary_fields.setMinimumWidth(255)
            summary_fields.setMinimumHeight(260)
            summary_fields.setMaximumHeight(420)
            page.summary_field_row_widgets = {}
            page.summary_metric_fields = set()
            page.summary_metric_order = []
            page.summary_footer_order = []
            page.summary_metric_labels = {}
            page.summary_metric_widths = {}
            page.summary_metric_positions = {}
            page.summary_metric_styles = {}
            page.summary_graphic_master = None
            page.summary_graphic_secondaries = []

            def update_palette_roles():
                master = str(getattr(page, "summary_graphic_master", None) or "")
                secondaries = {str(x) for x in getattr(page, "summary_graphic_secondaries", [])}
                for i in range(summary_fields.count()):
                    item = summary_fields.item(i)
                    field = str(item.data(Qt.ItemDataRole.UserRole) or "")
                    row = summary_fields.itemWidget(item)
                    lab = row.findChild(QLabel, "fieldName") if row is not None else None
                    if lab is None: continue
                    # Repartir explicitement de la police normale de MM3 : le style
                    # global ne doit pas rendre toute la palette visuellement grasse.
                    font = QFont("Calibri", 9)
                    font.setBold(False); font.setWeight(QFont.Weight.Normal)
                    if field == master:
                        font.setBold(True); font.setWeight(QFont.Weight.Bold); lab.setFont(font)
                        lab.setStyleSheet("QLabel { color:#9A3324; font-family:Calibri; font-size:9pt; font-weight:700; }")
                    elif field in secondaries:
                        font.setBold(True); font.setWeight(QFont.Weight.Bold); lab.setFont(font); lab.setStyleSheet("QLabel { color:#111111; font-family:Calibri; font-size:9pt; font-weight:700; }")
                    else:
                        font.setBold(False); font.setWeight(QFont.Weight.Normal); lab.setFont(font)
                        palette_color = "#0055FF" if (field == "__records__" or field in {"record_number", "record_state"} or str(item.data(Qt.ItemDataRole.UserRole + 1) or "") in {"N°", "État de la fiche"}) else "#111111"
                        lab.setStyleSheet(f"QLabel {{ color:{palette_color}; font-family:Calibri; font-size:9pt; font-weight:normal; }}")

            def sync_graphic_columns():
                selected = []
                if getattr(page, "summary_graphic_master", None):
                    selected.append(str(page.summary_graphic_master))
                selected.extend(str(x) for x in getattr(page, "summary_graphic_secondaries", []))
                for field, pair in page.summary_field_row_widgets.items():
                    col_cb, _total_cb = pair
                    col_cb.blockSignals(True); col_cb.setChecked(field in selected); col_cb.blockSignals(False)
                self._mark_builder_dirty(page)
                self._refresh_summary_level_preview(page)

            def format_graphic_field(field, role, reset=False):
                field = str(field)
                styles = (page.detail_label_styles if detail_clone and role == "column_label" else
                          page.detail_total_styles if detail_clone and role == "group_total" else
                          page.detail_master_styles if detail_clone and role == "master"
                          else page.summary_field_styles)
                if reset:
                    styles.pop(field, None)
                    if role not in {"group_total", "column_label"}:
                        page.summary_column_alignments.pop(field, None)
                    rebuild_graphic_lanes(); self._mark_builder_dirty(page); return
                current = dict(styles.get(field) or {})
                dlg = QDialog(self); dlg.setWindowTitle(f"{tr('Mise en forme', self.language)} — {self.labels.get(field, field)}")
                form = QFormLayout(dlg)
                font_box = QFontComboBox(); font_box.setCurrentFont(QFont("Calibri" if role == "column_label" and str(current.get("font_family") or "Calibri").casefold() == "arial" else str(current.get("font_family") or "Calibri")))
                size_box = QSpinBox(); size_box.setRange(7, 36); size_box.setValue(int(current.get("font_size", 9)))
                bold_box = QCheckBox(tr("Gras", self.language)); bold_box.setChecked(bool(current.get("bold", False)))
                italic_box = QCheckBox(tr("Italique", self.language)); italic_box.setChecked(bool(current.get("italic", False)))
                color_btn = QPushButton(tr("Choisir…", self.language)); color = str(current.get("text_color") or "#111111")
                color_sample = QLabel(color); color_sample.setStyleSheet(f"QLabel {{ color:{color}; }}")
                color_row = QWidget(); cr=QHBoxLayout(color_row); cr.setContentsMargins(0,0,0,0); cr.addWidget(color_btn); cr.addWidget(color_sample); cr.addStretch(1)
                align_box=QComboBox(); align_box.addItem(tr("Gauche", self.language),"left"); align_box.addItem(tr("Centré", self.language),"center"); align_box.addItem(tr("Droite", self.language),"right")
                ai=align_box.findData(str(current.get("align", "left") if role in {"group_total", "column_label"} else page.summary_column_alignments.get(field,current.get("align","left")))); align_box.setCurrentIndex(ai if ai>=0 else 0)
                vertical_box = None
                if role == "master" and not detail_clone:
                    vertical_box = QComboBox()
                    for label, value in ((tr("Haut", self.language), "top"), (tr("Centré", self.language), "center"), (tr("Bas", self.language), "bottom")):
                        vertical_box.addItem(label, value)
                    vi = vertical_box.findData(getattr(page, "summary_vertical_align", "center"))
                    vertical_box.setCurrentIndex(vi if vi >= 0 else 1)
                date_format_box=None; date_group_box=None
                if role != "column_label" and self._is_date_field(field):
                    date_format_box=QComboBox()
                    for txt,data in (("Format de la fiche","default"),("JJ/MM/AAAA","dd/MM/yyyy"),("JJ/MM/AA","dd/MM/yy"),("MM/AAAA","MM/yyyy"),("AAAA","yyyy"),("JJ-MM-AAAA","dd-MM-yyyy"),("AAAA-MM-JJ","yyyy-MM-dd")):
                        date_format_box.addItem(txt,data)
                    di=date_format_box.findData(str(current.get("date_format") or "default")); date_format_box.setCurrentIndex(di if di>=0 else 0)
                    if role == "master":
                        date_group_box=QComboBox()
                        for txt,data in (("Date complète","full_date"),("Année","year"),("Mois (nom entier)","month"),("Année + mois (nom entier)","year_month")):
                            date_group_box.addItem(txt,data)
                        gi=date_group_box.findData(str(page.date_group_mode_widget.currentData() or "full_date")); date_group_box.setCurrentIndex(gi if gi>=0 else 0)
                def choose_color():
                    nonlocal color
                    c=mm3_choose_color(dlg, QColor(color), "Couleur du texte")
                    if c is not None and c.isValid(): color=c.name(); color_sample.setText(color); color_sample.setStyleSheet(f"QLabel {{ color:{color}; }}")
                color_btn.clicked.connect(choose_color)
                bg_color = str(current.get("background_color") or "#FFFFFF")
                bg_btn = None
                if role == "column_label":
                    bg_btn = QPushButton(tr("Choisir…", self.language))
                    bg_sample = QLabel(bg_color); bg_sample.setStyleSheet(f"QLabel {{ background:{bg_color}; padding:2px 12px; border:1px solid #AEBBB5; }}")
                    bg_row = QWidget(); bgr=QHBoxLayout(bg_row); bgr.setContentsMargins(0,0,0,0); bgr.addWidget(bg_btn); bgr.addWidget(bg_sample); bgr.addStretch(1)
                    def choose_bg():
                        nonlocal bg_color
                        c=mm3_choose_color(dlg, QColor(bg_color), tr("Couleur de fond de l’en-tête", self.language))
                        if c is not None and c.isValid():
                            bg_color=c.name(); bg_sample.setText(bg_color); bg_sample.setStyleSheet(f"QLabel {{ background:{bg_color}; padding:2px 12px; border:1px solid #AEBBB5; }}")
                    bg_btn.clicked.connect(choose_bg)
                form.addRow(tr("Donnée — Police :", self.language),font_box); form.addRow(tr("Donnée — Taille :", self.language),size_box); form.addRow(tr("Donnée — Style :", self.language),bold_box); form.addRow("",italic_box); form.addRow(tr("Donnée — Couleur :", self.language),color_row); form.addRow(tr("Alignement :", self.language),align_box)
                if bg_btn is not None: form.addRow(tr("Couleur de fond :", self.language), bg_row)
                if vertical_box is not None: form.addRow(tr("Position sur la ligne (tous les champs) :", self.language), vertical_box)
                if date_format_box is not None: form.addRow(tr("Format de date :", self.language),date_format_box)
                if date_group_box is not None: form.addRow(tr("Regroupement date :", self.language),date_group_box)
                buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel); buttons.accepted.connect(dlg.accept); buttons.rejected.connect(dlg.reject)
                _cancel_btn = buttons.button(QDialogButtonBox.StandardButton.Cancel)
                if _cancel_btn is not None: _cancel_btn.setText(tr("Annuler", self.language))
                form.addRow(buttons)
                if dlg.exec()!=QDialog.Accepted: return
                # État résumé : seuls les paramètres de la donnée sont utiles à l'affichage.
                # Les anciens paramètres de libellé restent tolérés à la lecture des vieux modèles,
                # mais ne sont plus proposés ni réécrits par cette fenêtre.
                styles[field]={"font_family":font_box.currentFont().family(),"font_size":int(size_box.value()),"bold":bold_box.isChecked(),"italic":italic_box.isChecked(),"text_color":color,"align":str(align_box.currentData() or "left"),"date_format":str(date_format_box.currentData() if date_format_box is not None else current.get("date_format") or "default")}
                if role == "column_label": styles[field]["background_color"] = bg_color
                if role not in {"group_total", "column_label"}:
                    page.summary_column_alignments[field]=str(align_box.currentData() or "left")
                if vertical_box is not None:
                    page.summary_vertical_align = str(vertical_box.currentData() or "center")
                    position_widget = getattr(page, "summary_vertical_align_widget", None)
                    if position_widget is not None:
                        position_widget.blockSignals(True)
                        position_widget.setCurrentIndex(position_widget.findData(page.summary_vertical_align))
                        position_widget.blockSignals(False)
                if date_group_box is not None:
                    gi=page.date_group_mode_widget.findData(str(date_group_box.currentData() or "full_date"))
                    if gi >= 0: page.date_group_mode_widget.setCurrentIndex(gi)
                rebuild_graphic_lanes(); self._mark_builder_dirty(page)

            def rebuild_graphic_lanes():
                master = str(getattr(page, "summary_graphic_master", None) or "")
                master_chips = [(self.labels.get(master, master), "#111111", master)] if master else []
                sec_chips = [((tr("Nombre de fiches", self.language) if str(f) == "__records__" else self.labels.get(str(f), str(f))), "#111111", str(f)) for f in getattr(page, "summary_graphic_secondaries", [])]
                # La Construction doit montrer la même mise en forme que l'aperçu/impression.
                lane_styles = {str(k): dict(v or {}) for k, v in page.summary_field_styles.items()}
                if master and master not in lane_styles:
                    lane_styles[master] = {"font_family":"Calibri", "font_size":10, "bold":False, "italic":False, "text_color":"#111111", "align":"left"}
                for f in getattr(page, "summary_graphic_secondaries", []):
                    key = str(f)
                    if key not in lane_styles:
                        lane_styles[key] = {"font_family":"Calibri", "font_size":10, "bold":False, "italic":False, "text_color":"#111111", "align":"left"}
                master_styles = dict(lane_styles)
                if detail_clone and master:
                    master_styles[master] = dict(page.detail_master_styles.get(master) or
                                                 {"font_family":"Calibri", "font_size":10, "bold":False,
                                                  "italic":False, "text_color":"#111111", "align":"left"})
                row_position = None if detail_clone else str(getattr(page, "summary_vertical_align", "center"))
                page.summary_master_lane.set_chips(master_chips, master_styles, row_position)
                page.summary_secondary_lane.set_chips(sec_chips, lane_styles, row_position)
                if not detail_clone:
                    for lane in (page.summary_master_lane, page.summary_secondary_lane):
                        lane.setMinimumHeight(72)
                if detail_clone:
                    def update_detail_width(field, width):
                        page.detail_column_widths[str(field)] = max(70,min(480,int(width)))
                        self._mark_builder_dirty(page)
                    free_row = page.detail_secondary_free_row
                    free_row.clear_items()
                    next_x = 8
                    def _store_secondary_x(field, x):
                        page.summary_field_styles.setdefault(str(field), {})["builder_x"] = int(x)
                        self._mark_builder_dirty(page)
                    chips = []
                    for index in range(page.summary_secondary_lane.row.count()):
                        widget = page.summary_secondary_lane.row.itemAt(index).widget()
                        if isinstance(widget, SummaryFieldChip):
                            chips.append(widget)
                    for widget in chips:
                        page.summary_secondary_lane.row.removeWidget(widget)
                        widget.setFixedWidth(max(28, min(480, int(page.detail_column_widths.get(widget.field) or 130))))
                        widget.enable_resize(update_detail_width)
                        widget.setToolTip("Clic gauche : sélectionner et déplacer horizontalement. Flèches ← → : déplacement précis. Poignée ↔ : largeur.")
                        saved_x = (page.summary_field_styles.get(widget.field) or {}).get("builder_x")
                        x = int(saved_x) if saved_x is not None else next_x
                        free_row.add_item(widget.field, widget, x, _store_secondary_x)
                        next_x = max(next_x, x + widget.width() + 8)
                    totals = [(self.labels.get(str(f), str(f)), "#795422", str(f))
                              for f in page.detail_group_totals]
                    page.detail_group_totals_lane.set_chips(totals, page.detail_total_styles)
                    rebuild_detail_labels()
                else:
                    def update_summary_width(field, width):
                        page.summary_column_widths[str(field)] = max(28, min(480, int(width)))
                        self._refresh_summary_level_preview(page)
                        self._mark_builder_dirty(page)
                    for lane in (page.summary_master_lane, page.summary_secondary_lane):
                        for index in range(lane.row.count()):
                            widget = lane.row.itemAt(index).widget()
                            if isinstance(widget, SummaryFieldChip):
                                default_width = 240 if widget.field == master else 190
                                widget.setFixedWidth(max(28, min(480, int(page.summary_column_widths.get(widget.field) or default_width))))
                                widget.enable_resize(update_summary_width)
                                widget.setToolTip(tr("Tirer la poignée droite pour ajuster la colonne et son en-tête", self.language))
                update_palette_roles()
                sync_graphic_columns()

            def drop_graphic_field(field, label, role):
                field = str(field)
                master = str(getattr(page, "summary_graphic_master", None) or "")
                secondaries = list(getattr(page, "summary_graphic_secondaries", []))
                if role == "group_total" and detail_clone:
                    if field not in self.labels:
                        return False
                    if field not in page.detail_group_totals:
                        if len(page.detail_group_totals) >= 6:
                            QMessageBox.information(self, "Sous-totaux", "Six champs de sous-totaux au maximum.")
                            return False
                        page.detail_group_totals.append(field)
                    rebuild_graphic_lanes()
                    self._mark_builder_dirty(page)
                    return True
                if role == "master":
                    # Un détail peut répéter le champ maître sur chaque fiche.
                    if field in secondaries and not detail_clone:
                        secondaries.remove(field)
                    if master and master != field:
                        if len(secondaries) >= (12 if detail_clone else 4):
                            QMessageBox.information(self, "Champ maître", "Le nombre maximal de champs complémentaires est atteint.")
                            return False
                        secondaries.insert(0, master)
                    page.summary_graphic_master = field
                    page.summary_graphic_secondaries = secondaries
                    self._set_combo_by_data(page.group_widget, field)
                else:
                    if field == master and not detail_clone:
                        page.summary_graphic_master = None
                        self._set_combo_by_data(page.group_widget, None)
                    if field not in secondaries:
                        if len(secondaries) >= (12 if detail_clone else 4):
                            QMessageBox.information(self, "État détaillé" if detail_clone else "État résumé", "Un état détaillé accepte jusqu'à 12 champs complémentaires." if detail_clone else "Un état résumé est limité à 4 champs liés (5 champs au total avec le maître).")
                            return False
                        secondaries.append(field)
                    page.summary_graphic_secondaries = secondaries
                rebuild_graphic_lanes()
                return True

            def remove_graphic_field(field, role):
                field = str(field)
                if role == "group_total" and detail_clone:
                    page.detail_group_totals = [f for f in page.detail_group_totals if f != field]
                    rebuild_graphic_lanes()
                    self._mark_builder_dirty(page)
                    return
                if role == "master" and str(getattr(page, "summary_graphic_master", None) or "") == field:
                    page.summary_graphic_master = None
                    self._set_combo_by_data(page.group_widget, None)
                else:
                    page.summary_graphic_secondaries = [
                        str(x) for x in getattr(page, "summary_graphic_secondaries", []) if str(x) != field
                    ]
                rebuild_graphic_lanes()

            for label, field in sorted(self.fields, key=lambda pair: field_sort_key(pair[0])):
                item = QListWidgetItem("")
                item.setData(Qt.ItemDataRole.UserRole, field)
                item.setData(Qt.ItemDataRole.UserRole + 1, label)
                item.setFlags((item.flags() | Qt.ItemFlag.ItemIsDragEnabled) & ~Qt.ItemFlag.ItemIsUserCheckable)
                item.setSizeHint(QSize(0, 25))
                summary_fields.addItem(item)
                row = QWidget(); row_lay = QHBoxLayout(row); row_lay.setContentsMargins(4,0,4,0); row_lay.setSpacing(4)
                lab = QLabel(label); lab.setObjectName("fieldName")
                _pf = QFont("Calibri", 9); _pf.setBold(False); _pf.setWeight(QFont.Weight.Normal); lab.setFont(_pf)
                _sys_color = "#0055FF" if (str(field) in {"record_number", "record_state"} or str(label) in {"N°", "État de la fiche"}) else "#111111"
                lab.setStyleSheet(f"QLabel {{ color:{_sys_color}; font-family:Calibri; font-size:9pt; font-weight:normal; }}")
                total_cb = QCheckBox(); total_cb.setToolTip("Afficher ce champ dans les totaux du bandeau")
                total_cell = QWidget(); total_cell.setFixedWidth(52)
                total_cell_lay = QHBoxLayout(total_cell); total_cell_lay.setContentsMargins(0,0,0,0)
                total_cell_lay.addStretch(1); total_cell_lay.addWidget(total_cb); total_cell_lay.addStretch(1)
                row_lay.addWidget(lab, 1); row_lay.addWidget(total_cell)
                summary_fields.setItemWidget(item, row)
                # Case Col. interne conservée pour compatibilité avec le moteur existant.
                col_cb = QCheckBox(); col_cb.setVisible(False)
                page.summary_field_row_widgets[str(field)] = (col_cb, total_cb)
                def toggle_total(checked, f=str(field), cb=total_cb):
                    # 27.141 — relire immédiatement la source réelle avant de
                    # calculer le total affiché dans le constructeur. Le premier
                    # rafraîchissement d'un nouvel état ne doit plus travailler
                    # sur un ancien jeu de données / état transitoire.
                    self._records_for_source(page.source_widget.currentData())
                    metrics = page.summary_metric_fields
                    if checked and f not in metrics and len(metrics) >= 8:
                        cb.blockSignals(True); cb.setChecked(False); cb.blockSignals(False)
                        QMessageBox.information(self, "Totaux", "Le bandeau est limité à 8 champs Total.")
                        return
                    metrics.add(f) if checked else metrics.discard(f)
                    # Les cases « Total » du nouvel Atelier pilotent directement
                    # l'affichage des totaux sélectionnés dans le bandeau.
                    show_selected = getattr(page, "summary_show_selected_metrics_widget", None)
                    if show_selected is not None:
                        show_selected.blockSignals(True)
                        show_selected.setChecked(bool(metrics))
                        show_selected.blockSignals(False)
                    self._mark_builder_dirty(page)
                    self._refresh_summary_level_preview(page)
                    # 27.136 — recalcul différé du bandeau : lors de la création d'un
                    # nouvel état, le premier rafraîchissement pouvait encore afficher
                    # 0 alors que les données de la collection étaient déjà disponibles.
                    QTimer.singleShot(0, lambda p=page: self._refresh_summary_level_preview(p))
                total_cb.toggled.connect(toggle_total)

            # Total système : Nombre de fiches. Il appartient à la palette des
            # Totaux mais ne peut pas devenir une colonne de l'état.
            records_item = QListWidgetItem("")
            records_item.setData(Qt.ItemDataRole.UserRole, "__records__")
            records_item.setData(Qt.ItemDataRole.UserRole + 1, tr("Nombre de fiches", self.language))
            records_item.setFlags(records_item.flags() | Qt.ItemFlag.ItemIsDragEnabled)
            records_item.setSizeHint(QSize(0, 25))
            summary_fields.addItem(records_item)
            records_row = QWidget(); records_lay = QHBoxLayout(records_row); records_lay.setContentsMargins(4,0,4,0); records_lay.setSpacing(4)
            records_lab = QLabel(tr("Nombre de fiches", self.language)); records_lab.setObjectName("fieldName")
            records_lab.setFont(QFont("Calibri", 9)); records_lab.setStyleSheet("QLabel { color:#0055FF; font-family:Calibri; font-size:9pt; font-weight:normal; }")
            records_total_cb = QCheckBox(); records_total_cb.setToolTip("Afficher le nombre de fiches dans le bandeau")
            records_cell = QWidget(); records_cell.setFixedWidth(52)
            records_cell_lay = QHBoxLayout(records_cell); records_cell_lay.setContentsMargins(0,0,0,0); records_cell_lay.addStretch(1); records_cell_lay.addWidget(records_total_cb); records_cell_lay.addStretch(1)
            records_lay.addWidget(records_lab, 1); records_lay.addWidget(records_cell)
            summary_fields.setItemWidget(records_item, records_row)
            records_col_cb = QCheckBox(); records_col_cb.setToolTip(tr("Afficher comme colonne liée", self.language))
            page.summary_field_row_widgets["__records__"] = (records_col_cb, records_total_cb)
            def toggle_records_total(checked):
                if checked and "__records__" not in page.summary_metric_order:
                    page.summary_metric_order.append("__records__")
                elif not checked:
                    page.summary_metric_order = [f for f in page.summary_metric_order if f != "__records__"]
                w = getattr(page, "summary_show_records_metric_widget", None)
                if w is not None:
                    w.blockSignals(True); w.setChecked(bool(checked)); w.blockSignals(False)
                self._mark_builder_dirty(page); self._refresh_summary_level_preview(page)
            records_total_cb.toggled.connect(toggle_records_total)
            def toggle_records_column(checked):
                secondaries = [str(x) for x in getattr(page, "summary_graphic_secondaries", [])]
                if checked:
                    if "__records__" not in secondaries:
                        if len(secondaries) < 4:
                            secondaries.append("__records__")
                        else:
                            records_col_cb.blockSignals(True); records_col_cb.setChecked(False); records_col_cb.blockSignals(False)
                            return
                else:
                    secondaries = [f for f in secondaries if f != "__records__"]
                page.summary_graphic_secondaries = secondaries
                rebuild_graphic_lanes()
                self._mark_builder_dirty(page)
            records_col_cb.toggled.connect(toggle_records_column)

            fields_lay.addWidget(summary_fields, 1)
            clear_fields_btn = QPushButton(tr("Vider la construction", self.language))
            clear_fields_btn.setFixedHeight(30)
            def clear_summary_fields():
                page.summary_graphic_master = None
                page.summary_graphic_secondaries = []
                if detail_clone:
                    page.detail_group_totals = []
                    page.detail_column_labels.clear()
                    page.detail_label_styles.clear()
                self._set_combo_by_data(page.group_widget, None)
                for _field, (_col_cb, _total_cb) in page.summary_field_row_widgets.items():
                    _total_cb.blockSignals(True); _total_cb.setChecked(False); _total_cb.blockSignals(False)
                page.summary_metric_fields.clear()
                page.summary_metric_order = []
                page.summary_footer_order = []
                page.summary_metric_labels.clear()
                page.summary_metric_widths = {}
                page.summary_metric_positions = {}
                page.summary_metric_styles.clear()
                if hasattr(page, "summary_show_records_metric_widget"):
                    page.summary_show_records_metric_widget.setChecked(False)
                rebuild_graphic_lanes()
            clear_fields_btn.clicked.connect(clear_summary_fields)
            fields_lay.addWidget(clear_fields_btn)
            page.summary_clear_fields_button = clear_fields_btn
            page.summary_fields_widget = summary_fields
            page.summary_column_alignments = {}
            page.summary_treatments = {}
            page.summary_field_styles = {}
            page.detail_master_styles = {}
            page.detail_group_totals = []
            page.detail_total_styles = {}
            page.detail_column_labels = {}
            page.detail_label_styles = {}
            page.detail_column_widths = {}
            # 27.41 — personnalisation propre des en-têtes de colonnes du résumé.
            # Ces réglages sont distincts des données et restent compatibles avec
            # les anciens modèles qui n'en possèdent pas.
            page.summary_column_header_labels = {}
            page.summary_column_header_styles = {}
            page.summary_column_header_hidden = set()
            page.summary_column_widths = {}
            page.summary_vertical_align = "center"

            construction = QGroupBox(tr("Construction de l'état détaillé" if detail_clone else "Construction de l'état résumé", self.language))
            construction_grid = QGridLayout(construction)
            construction_grid.setContentsMargins(8, 5, 8, 6)
            construction_grid.setHorizontalSpacing(7); construction_grid.setVerticalSpacing(5)

            summary_header_sample = SummaryMetricLane(); summary_header_sample.setObjectName("summaryHeaderSample")
            summary_header_sample.setFixedHeight(34); summary_header_sample.setStyleSheet("#summaryHeaderSample { border:1px solid #c2cdc8; background:#F4F6F5; }")
            summary_header_sample_lay = QHBoxLayout(summary_header_sample); summary_header_sample_lay.setContentsMargins(6,1,6,1); summary_header_sample_lay.setSpacing(8)
            page.summary_header_sample_layout = summary_header_sample_lay; page.summary_header_metric_labels = []
            page.summary_band_style = {"font":"Calibri","size":11,"bold":True,"italic":False,"text":"#8B3026","bg":"#FFFFFF","align":"left"}
            page.summary_footer_linked = False
            page.summary_footer_metric_fields = set()
            page.summary_footer_style = {"font":"Calibri","size":10,"bold":True,"italic":False,"text":"#111111","bg":"#FFFFFF","align":"left"}
            page.summary_footer_metric_styles = {}
            page.summary_footer_metric_labels = {}
            page.summary_footer_metric_spacing = {}
            page.summary_footer_metric_widths = {}
            page.summary_footer_metric_positions = {}
            # 1.0.105 — position X indépendante de chaque cellule de total.
            page.summary_metric_positions = {}
            page.summary_footer_metric_positions = {}
            # 27.132 — numérotation de pages propre à l’état résumé.
            page.summary_page_numbers_enabled = False
            page.summary_page_number_format = "page_x_y"
            page.summary_page_number_align = "right"

            summary_column_header_sample = QLabel("En-tête des colonnes")
            summary_column_header_sample.setFrameShape(QFrame.Shape.StyledPanel); summary_column_header_sample.setFixedHeight(32)
            summary_column_header_sample.setAlignment(Qt.AlignmentFlag.AlignCenter)
            summary_column_header_sample.setToolTip("Clic droit : personnaliser les en-têtes de colonnes")

            def _summary_header_fields():
                fields=[]
                master=str(getattr(page,"summary_graphic_master",None) or "")
                if master: fields.append(master)
                for f in list(getattr(page,"summary_graphic_secondaries",[]) or []):
                    if f and f not in fields: fields.append(str(f))
                return fields

            def _edit_column_header(field):
                field=str(field or "")
                if not field: return
                default_label=str(tr("Nombre de fiches", self.language) if field == "__records__" else self.labels.get(field,field))
                cur_label=str(getattr(page,"summary_column_header_labels",{}).get(field) or default_label)
                cur=dict(getattr(page,"summary_column_header_styles",{}).get(field) or {})
                dlg=QDialog(self); dlg.setWindowTitle(tr("Mise en forme de l’en-tête", self.language)+" — "+default_label)
                form=QFormLayout(dlg)
                label_edit=QLineEdit(cur_label)
                ff=QFontComboBox(); ff.setCurrentFont(QFont(str(cur.get("font_family") or "Calibri")))
                fs=QSpinBox(); fs.setRange(6,30); fs.setValue(int(cur.get("font_size",10))); fs.setSuffix(" pt")
                bo=QCheckBox(tr("Gras", self.language)); bo.setChecked(bool(cur.get("bold",True)))
                it=QCheckBox(tr("Italique", self.language)); it.setChecked(bool(cur.get("italic",False)))
                un=QCheckBox(tr("Souligné", self.language)); un.setChecked(bool(cur.get("underline",False)))
                al=QComboBox(); al.addItem(tr("Gauche", self.language),"left"); al.addItem(tr("Centré", self.language),"center"); al.addItem(tr("Droite", self.language),"right")
                ai=al.findData(str(cur.get("align") or "center")); al.setCurrentIndex(ai if ai>=0 else 1)
                tc=QPushButton(tr("Choisir…", self.language)); tc.setProperty("mm3Color",str(cur.get("text_color") or "#111111"))
                bg=QPushButton(tr("Choisir…", self.language)); bg.setProperty("mm3Color",str(cur.get("bg_color") or "#FFFFFF"))
                def paint_color_button(btn):
                    color = str(btn.property("mm3Color") or "#FFFFFF")
                    btn.setStyleSheet(f"QPushButton {{ background-color:{color}; }}")
                def choose(btn,title):
                    c=mm3_choose_color(dlg,QColor(str(btn.property("mm3Color") or "#000000")),tr(title, self.language))
                    if c is not None and c.isValid():
                        btn.setProperty("mm3Color",c.name()); paint_color_button(btn)
                paint_color_button(tc); paint_color_button(bg)
                tc.clicked.connect(lambda _=False: choose(tc,"Couleur du texte")); bg.clicked.connect(lambda _=False: choose(bg,"Couleur du fond"))
                flags=QWidget(); fl=QHBoxLayout(flags); fl.setContentsMargins(0,0,0,0); fl.addWidget(bo); fl.addWidget(it); fl.addWidget(un); fl.addStretch(1)
                form.addRow(tr("Libellé affiché :", self.language),label_edit); form.addRow(tr("Police :", self.language),ff); form.addRow(tr("Taille :", self.language),fs); form.addRow(tr("Style :", self.language),flags); form.addRow(tr("Alignement :", self.language),al); form.addRow(tr("Couleur texte :", self.language),tc); form.addRow(tr("Couleur fond :", self.language),bg)
                buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel); reset=buttons.addButton(tr("Rétablir par défaut", self.language),QDialogButtonBox.ButtonRole.ResetRole); form.addRow(buttons)
                buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("Annuler", self.language))
                buttons.button(QDialogButtonBox.StandardButton.Ok).setText("OK")
                buttons.accepted.connect(dlg.accept); buttons.rejected.connect(dlg.reject)
                reset.clicked.connect(lambda: (label_edit.setText(default_label),ff.setCurrentFont(QFont("Calibri")),fs.setValue(10),bo.setChecked(True),it.setChecked(False),un.setChecked(False),al.setCurrentIndex(al.findData("center")),tc.setProperty("mm3Color","#111111"),bg.setProperty("mm3Color","#FFFFFF"),paint_color_button(tc),paint_color_button(bg)))
                if dlg.exec()==QDialog.DialogCode.Accepted:
                    lab=label_edit.text()
                    if lab==default_label: page.summary_column_header_labels.pop(field,None)
                    else: page.summary_column_header_labels[field]=lab
                    page.summary_column_header_hidden.discard(field)
                    page.summary_column_header_styles[field]={"font_family":ff.currentFont().family(),"font_size":fs.value(),"bold":bo.isChecked(),"italic":it.isChecked(),"underline":un.isChecked(),"align":str(al.currentData() or "center"),"text_color":str(tc.property("mm3Color") or "#111111"),"bg_color":str(bg.property("mm3Color") or "#FFFFFF")}
                    self._mark_builder_dirty(page); self._refresh_summary_level_preview(page)

            def _column_header_menu(pos):
                fields=_summary_header_fields()
                menu=QMenu(summary_column_header_sample)
                if not fields:
                    a=menu.addAction(tr("Aucune colonne dans la construction", self.language)); a.setEnabled(False)
                    menu.exec(summary_column_header_sample.mapToGlobal(pos)); return

                # Le clic droit agit directement sur la colonne située sous la souris.
                # Les largeurs mémorisées sont utilisées si elles existent ; sinon
                # les colonnes se partagent la largeur disponible.
                stored_fields=list(summary_column_header_sample.property("gskolHeaderFields") or [])
                stored_widths=list(summary_column_header_sample.property("gskolHeaderWidths") or [])
                if stored_fields == fields and len(stored_widths) == len(fields):
                    widths=[max(1.0,float(w)) for w in stored_widths]
                else:
                    widths=[1.0 for _ in fields]
                total=sum(widths) or 1.0
                x=max(0.0, min(float(pos.x()), float(max(1, summary_column_header_sample.width()))))
                target=x/float(max(1, summary_column_header_sample.width()))*total
                acc=0.0; field=fields[-1]
                for f,w in zip(fields,widths):
                    acc += w
                    if target <= acc:
                        field=f; break

                lab=str(getattr(page,"summary_column_header_labels",{}).get(field) or (tr("Nombre de fiches", self.language) if field == "__records__" else self.labels.get(field,field)))
                edit=menu.addAction(tr("Mise en forme de l’en-tête…", self.language))
                rename=menu.addAction(tr("Modifier l’en-tête", self.language)+" « "+lab+" »…")
                if field in page.summary_column_header_hidden:
                    visibility=menu.addAction(tr("Rétablir l’en-tête", self.language)+" « "+lab+" »")
                else:
                    visibility=menu.addAction(tr("Supprimer l’en-tête", self.language)+" « "+lab+" »")
                reset=menu.addAction(tr("Rétablir cet en-tête par défaut", self.language))
                act=menu.exec(summary_column_header_sample.mapToGlobal(pos))
                if act is None: return
                if act in (edit, rename):
                    _edit_column_header(field)
                elif act == visibility:
                    if field in page.summary_column_header_hidden: page.summary_column_header_hidden.discard(field)
                    else: page.summary_column_header_hidden.add(field)
                    self._mark_builder_dirty(page); self._refresh_summary_level_preview(page)
                elif act == reset:
                    page.summary_column_header_labels.pop(field,None)
                    page.summary_column_header_styles.pop(field,None)
                    page.summary_column_header_hidden.discard(field)
                    self._mark_builder_dirty(page); self._refresh_summary_level_preview(page)
            summary_column_header_sample.setContextMenuPolicy(Qt.CustomContextMenu)
            summary_column_header_sample.customContextMenuRequested.connect(_column_header_menu)

            master_lane = SummaryDropLane("master", drop_graphic_field, remove_graphic_field, format_graphic_field)
            secondary_lane = SummaryDropLane("secondary", drop_graphic_field, remove_graphic_field, format_graphic_field)
            master_lane.setProperty("gskolLanguage", self.language)
            secondary_lane.setProperty("gskolLanguage", self.language)
            page.summary_master_lane = master_lane; page.summary_secondary_lane = secondary_lane
            # La ligne libre doit exister avant la liaison du dépôt de champs
            # et avant le premier appel à rebuild_graphic_lanes().
            if detail_clone:
                page.detail_secondary_free_row = DetailFreeRow()
            if detail_clone:
                page.detail_group_totals_lane = SummaryDropLane("group_total", drop_graphic_field, remove_graphic_field, format_graphic_field)
                page.detail_group_totals_lane.setProperty("gskolLanguage", self.language)
                page.detail_group_totals_lane.setToolTip("Déposer jusqu'à six champs. Clic droit sur un total : mise en forme ou retrait.")
                page.detail_label_row = DetailLabelRow()
                # Structure unique, indépendante de la langue : hauteur de référence
                # suffisante pour les libellés de colonnes (FR/EN et futures langues).
                page.detail_label_row.setMinimumHeight(38)
                page.detail_label_row = DetailFreeRow()
                def _store_header_x(field, x):
                    page.detail_label_styles.setdefault(str(field), {})["builder_x"] = int(x)
                    self._mark_builder_dirty(page)
                def rebuild_detail_labels():
                    page.detail_label_row.clear_items()
                    next_x = 8
                    for field in page.summary_graphic_secondaries:
                        field = str(field)
                        edit = DetailLabelEdit(field, lambda f, d: reorder_secondary(f, d), str(page.detail_column_labels.get(field) or ""))
                        edit.setProperty("detail_field",field)
                        edit.setPlaceholderText(self.labels.get(field, field))
                        edit.setToolTip("Libellé libre au-dessus de la colonne « " + self.labels.get(field, field) + " ». Laisser vide pour ne rien afficher.")
                        width = max(24, min(480, int((page.detail_label_styles.get(field) or {}).get("builder_width") or 130)))
                        edit.setFixedWidth(width)
                        label_fmt = dict(page.detail_label_styles.get(field) or {})
                        label_font = QFont(str(label_fmt.get("font_family") or "Calibri"), int(label_fmt.get("font_size") or 9))
                        label_font.setBold(bool(label_fmt.get("bold", False)))
                        label_font.setItalic(bool(label_fmt.get("italic", False)))
                        edit.setFont(label_font)
                        edit.setStyleSheet("QLineEdit { color:" + str(label_fmt.get("text_color") or "#111111") + "; background:" + str(label_fmt.get("background_color") or "#FFFFFF") + "; }")
                        _label_align = str(label_fmt.get("align") or "left")
                        edit.setAlignment(Qt.AlignHCenter if _label_align == "center" else Qt.AlignRight if _label_align == "right" else Qt.AlignLeft)
                        edit.textChanged.connect(lambda text, f=field: (page.detail_column_labels.__setitem__(f, text), self._mark_builder_dirty(page)))
                        def edit_width(pos, f=field, widget=edit):
                            menu = QMenu(widget)
                            format_action = menu.addAction(tr("Mise en forme de l’en-tête…", self.language))
                            rename_action = menu.addAction(tr("Modifier l’en-tête", self.language) + "…")
                            reset_action = menu.addAction(tr("Rétablir la mise en forme de l’en-tête", self.language))
                            menu.addSeparator()
                            hide_action = menu.addAction(tr("Masquer l’en-tête de colonne", self.language))
                            menu.addSeparator()
                            remove_action = menu.addAction(tr("Retirer le champ de la construction", self.language))
                            selected = menu.exec(widget.mapToGlobal(pos))
                            if selected == format_action:
                                format_graphic_field(f, "column_label")
                            elif selected == rename_action:
                                default_label = str(self.labels.get(f, f))
                                current_label = str(page.detail_column_labels.get(f) or default_label)
                                value, ok = QInputDialog.getText(self, tr("Modifier l’en-tête", self.language), tr("Libellé affiché :", self.language), text=current_label)
                                if ok:
                                    page.detail_column_labels[f] = "" if str(value) == default_label else str(value)
                                    widget.setText(str(value) if str(value) != default_label else "")
                                    self._mark_builder_dirty(page)
                            elif selected == reset_action:
                                format_graphic_field(f, "column_label", True)
                            elif selected == hide_action:
                                page.detail_column_labels[f] = ""
                                widget.clear(); self._mark_builder_dirty(page)
                            elif selected == remove_action:
                                remove_graphic_field(f, "secondary")
                        edit.setContextMenuPolicy(Qt.CustomContextMenu)
                        edit.customContextMenuRequested.connect(edit_width)
                        holder = QWidget()
                        holder_lay = QHBoxLayout(holder)
                        holder_lay.setContentsMargins(0, 0, 0, 0)
                        holder_lay.setSpacing(0)
                        holder_lay.addWidget(edit)
                        def _resize_header(value, f=field, container=holder):
                            # Le conteneur doit suivre la largeur de son libellé.
                            # Sinon, Qt réserve toujours l'ancienne largeur et
                            # l'espacement apparent ne correspond plus au modèle.
                            actual = max(24, min(480, int(value)))
                            page.detail_label_styles.setdefault(str(f), {})["builder_width"] = actual
                            container.setFixedWidth(actual + 18)
                            page.detail_label_row._ensure_width()
                            self._mark_builder_dirty(page)
                        grip = HorizontalResizeGrip(edit, _resize_header)
                        grip.setToolTip("Ajuster uniquement la largeur de cet en-tête")
                        holder_lay.addWidget(grip)
                        holder.setFixedWidth(width + 18)
                        saved_x = (page.detail_label_styles.get(field) or {}).get("builder_x")
                        x = int(saved_x) if saved_x is not None else next_x
                        page.detail_label_row.add_item(field, holder, x, _store_header_x)
                        next_x = max(next_x, x + holder.width() + 8)
            def _reorder_list(order, field, before_or_direction):
                order=list(order)
                if field not in order: return order
                old=order.index(field); order.remove(field)
                if isinstance(before_or_direction, int):
                    target=max(0,min(len(order),old+before_or_direction))
                else:
                    target=order.index(before_or_direction) if before_or_direction in order else len(order)
                order.insert(target,field); return order
            def reorder_secondary(field, before_or_direction):
                page.summary_graphic_secondaries = _reorder_list(page.summary_graphic_secondaries, field, before_or_direction)
                rebuild_graphic_lanes(); self._mark_builder_dirty(page)
            if detail_clone:
                page.detail_secondary_free_row.drop_callback = lambda field: drop_graphic_field(field, self.labels.get(field, field), "secondary")
            secondary_lane.reorder_callback = reorder_secondary
            if detail_clone:
                page.detail_label_row.reorder_callback = reorder_secondary
                def reorder_group_total(field, before_or_direction):
                    page.detail_group_totals = _reorder_list(page.detail_group_totals, field, before_or_direction)
                    rebuild_graphic_lanes(); self._mark_builder_dirty(page)
                page.detail_group_totals_lane.reorder_callback = reorder_group_total

            footer_sample = SummaryMetricLane()
            footer_sample.setFrameShape(QFrame.Shape.StyledPanel); footer_sample.setFixedHeight(32)
            footer_sample.setToolTip("Clic droit : totaux du pied de page")
            footer_layout = QHBoxLayout(footer_sample); footer_layout.setContentsMargins(6,2,6,2); footer_layout.setSpacing(0)

            def _footer_fields_available():
                out=[]
                for lab,f in self.fields:
                    if str(f) in getattr(page,"summary_metric_fields",set()): out.append((lab,str(f)))
                if getattr(page,"summary_show_records_metric_widget",None) is not None and page.summary_show_records_metric_widget.isChecked(): out.append(("Nombre de fiches","__records__"))
                return out

            def _footer_metric_value(field):
                records=list(getattr(self,"records",[]) or [])
                if field=="__records__": return str(self._record_count(records)), tr("fiche(s)", self.language)
                treatment=self._summary_treatment(field, page.summary_treatments.get(field))
                vals=[r.get(field) for r in records if r.get(field) not in (None,"")]
                if treatment=="sum":
                    number=self._summary_total_text(field, sum(self._summary_numeric_value(r, field) for r in records))
                elif treatment=="avg":
                    nums=[self._summary_numeric_value(r, field) for r in records]; number=self._summary_total_text(field, sum(nums)/len(nums)) if nums else "0"
                elif treatment=="min":
                    nums=[self._summary_numeric_value(r, field) for r in records]; number=self._summary_total_text(field, min(nums)) if nums else "0"
                elif treatment=="max":
                    nums=[self._summary_numeric_value(r, field) for r in records]; number=self._summary_total_text(field, max(nums)) if nums else "0"
                else:
                    gf=page.group_widget.currentData(); dm=str(page.date_group_mode_widget.currentData() or "full_date")
                    number=str(len(self._group_records(records,field,dm))) if field==gf and self._is_date_field(field) and dm!="full_date" else str(self._distinct_count(records,field))
                default=(tr("pièce(s)", self.language) if field=="box_count" else self.labels.get(field,field).lower()+"(s)")
                return number, default

            def _edit_footer_metric(field):
                fst=dict(getattr(page,"summary_footer_style",{}) or {})
                cur=dict(getattr(page,"summary_footer_metric_styles",{}).get(field) or {})
                dlg=QDialog(self); dlg.setWindowTitle(tr("Mise en forme du total du pied de page", self.language)); form=QFormLayout(dlg); controls=[]
                for title,part in (("Valeur","value"),("Libellé","label")):
                    ps=dict(cur.get(part) or {}); ff=QFontComboBox(); ff.setCurrentFont(QFont(str(ps.get("font") or fst.get("font") or "Calibri")))
                    sz=QSpinBox(); sz.setRange(7,36); sz.setValue(int(ps.get("size",fst.get("size",10))))
                    bo=QCheckBox(tr("Gras", self.language)); bo.setChecked(bool(ps.get("bold",fst.get("bold",True)))); it=QCheckBox(tr("Italique", self.language)); it.setChecked(bool(ps.get("italic",fst.get("italic",False))))
                    co=QPushButton(tr("Choisir…", self.language)); co.setProperty("mm3Color",str(ps.get("text") or fst.get("text") or "#111111"))
                    def choose(_checked=False,btn=co):
                        c=mm3_choose_color(dlg,QColor(str(btn.property("mm3Color") or "#111111")),"Couleur du texte")
                        if c is not None and c.isValid(): btn.setProperty("mm3Color",c.name())
                    co.clicked.connect(choose); form.addRow(f"{title} — Police :",ff); form.addRow(f"{title} — Taille :",sz)
                    flags=QWidget(); fl=QHBoxLayout(flags); fl.setContentsMargins(0,0,0,0); fl.addWidget(bo); fl.addWidget(it); fl.addStretch(1); form.addRow(f"{title} — Style :",flags); form.addRow(f"{title} — Couleur :",co)
                    controls.append((part,ff,sz,bo,it,co))
                sp=QSpinBox(); sp.setRange(0,200); sp.setValue(int(getattr(page,"summary_footer_metric_spacing",{}).get(field, 8 if bool(getattr(page,"summary_footer_linked",False)) else 16))); sp.setSuffix(" px"); form.addRow("Espace après :",sp)
                bb=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel); form.addRow(bb); bb.accepted.connect(dlg.accept); bb.rejected.connect(dlg.reject)
                if dlg.exec()==QDialog.DialogCode.Accepted:
                    out={}
                    for part,ff,sz,bo,it,co in controls: out[part]={"font":ff.currentFont().family(),"size":sz.value(),"bold":bo.isChecked(),"italic":it.isChecked(),"text":str(co.property("mm3Color") or "#111111")}
                    page.summary_footer_metric_styles[field]=out; page.summary_footer_metric_spacing[field]=sp.value(); _refresh_footer_sample(); self._mark_builder_dirty(page)

            def _refresh_footer_sample():
                footer_layout.setEnabled(True)
                while footer_layout.count():
                    it=footer_layout.takeAt(0); w=it.widget()
                    if w is not None: w.deleteLater()
                fst=dict(getattr(page,"summary_footer_style",{}) or {}); linked=bool(getattr(page,"summary_footer_linked",False))
                if detail_clone and linked:
                    # Conversion sans perte d'un pied anciennement lié : capturer
                    # les totaux réellement visibles AVANT de rompre la liaison.
                    original = list(dict.fromkeys(self._ordered_summary_totals(page)))
                    previous = list(getattr(page, "summary_footer_order", []) or [])
                    ordered = [str(f) for f in previous if str(f) in original]
                    ordered += [f for f in original if f not in ordered]
                    page.summary_footer_metric_fields = set(original)
                    page.summary_footer_order = ordered
                    if not getattr(page, "summary_footer_metric_positions", None):
                        page.summary_footer_metric_positions = dict(getattr(page, "summary_metric_positions", {}) or {})
                    if not getattr(page, "summary_footer_metric_widths", None):
                        page.summary_footer_metric_widths = dict(getattr(page, "summary_metric_widths", {}) or {})
                    page.summary_footer_linked = False
                    linked = False
                fields=[]
                if linked:
                    fields=list(dict.fromkeys(self._ordered_summary_totals(page)))
                else:
                    chosen=set(getattr(page,"summary_footer_metric_fields",set()) or set()); fields=list(dict.fromkeys([str(f) for f in getattr(page,"summary_footer_order",[]) if str(f) in chosen]+[str(f) for _lab,f in self.fields if str(f) in chosen]))
                    if "__records__" in chosen: fields.append("__records__")
                # En mode lié, les totaux reprennent la disposition compacte du bandeau :
                # aucun stretch ne doit pouvoir les disperser sur la largeur.
                if (not linked) and str(fst.get("align") or "left") in {"center","right"}: footer_layout.addStretch(1)
                for f in fields:
                    num,default=_footer_metric_value(f); lab=str(getattr(page,"summary_footer_metric_labels",{}).get(f) or (getattr(page,"summary_metric_labels",{}).get(f) if linked else "") or default)
                    st=dict(getattr(page,"summary_footer_metric_styles",{}).get(f) or {}); vst=dict(st.get("value") or {}); lst=dict(st.get("label") or {})
                    fam=str(fst.get("font") or "Calibri"); size=int(fst.get("size",10)); col=str(fst.get("text") or "#111111")
                    vf=str(vst.get("font") or fam); vs=int(vst.get("size",size)); vc=str(vst.get("text") or col); vb=bool(vst.get("bold",fst.get("bold",True))); vi=bool(vst.get("italic",fst.get("italic",False)))
                    lf=str(lst.get("font") or fam); ls=int(lst.get("size",size)); lc=str(lst.get("text") or col); lb=bool(lst.get("bold",fst.get("bold",True))); li=bool(lst.get("italic",fst.get("italic",False)))
                    q=SummaryMetricLabel(f"<span style='font-family:{_escape(vf)};font-size:{vs}pt;color:{vc};font-weight:{700 if vb else 400};font-style:{'italic' if vi else 'normal'}'>{_escape(num)}</span><span style='font-family:{_escape(lf)};font-size:{ls}pt;color:{lc};font-weight:{700 if lb else 400};font-style:{'italic' if li else 'normal'};white-space:pre;'> {_escape(lab)}</span>",f,footer_sample)
                    q.setTextFormat(Qt.TextFormat.RichText); q.setStyleSheet("QLabel { background:transparent; border:0; padding:0; }"); q.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred); q.setContextMenuPolicy(Qt.CustomContextMenu)
                    widths = page.summary_metric_widths if linked else page.summary_footer_metric_widths
                    def resize_footer(field, width):
                        page.summary_footer_metric_widths[str(field)] = max(55, min(480, int(width)))
                        self._mark_builder_dirty(page)
                    q.enable_resize((lambda field, width: (page.summary_metric_widths.__setitem__(str(field), width), self._refresh_summary_level_preview(page), self._mark_builder_dirty(page))) if linked else resize_footer, widths.get(f))
                    def move_footer(field, x):
                        target = page.summary_metric_positions if linked else page.summary_footer_metric_positions
                        target[str(field)] = max(0, int(x)); self._mark_builder_dirty(page)
                    q.enable_move(move_footer)
                    if linked:
                        q.setToolTip(tr("Largeur synchronisée avec le total du bandeau", self.language))
                    else:
                        q.setToolTip(tr("Déplacer horizontalement à la souris ou avec ←/→ ; la poignée redimensionne uniquement la cellule", self.language))
                    def menu(pos,field=f,w=q):
                        m=QMenu(w); el=m.addAction(tr("Modifier le libellé…", self.language)); es=m.addAction(tr("Mise en forme du total…", self.language)); er=m.addAction(tr("Rétablir le total par défaut", self.language)); a=m.exec(w.mapToGlobal(pos))
                        if a==el:
                            _n,d=_footer_metric_value(field); cur=str(getattr(page,"summary_footer_metric_labels",{}).get(field) or (getattr(page,"summary_metric_labels",{}).get(field) if linked else "") or d); val,ok=QInputDialog.getText(self,tr("Libellé du total", self.language),tr("Libellé affiché :", self.language),text=cur)
                            if ok: page.summary_footer_metric_labels[field]=str(val); _refresh_footer_sample(); self._mark_builder_dirty(page)
                        elif a==es: _edit_footer_metric(field)
                        elif a==er:
                            # Retour NATIF en une seule action : le résultat calculé ne change pas,
                            # mais toute personnalisation propre au pied disparaît.
                            page.summary_footer_metric_labels.pop(field, None)
                            page.summary_footer_metric_styles.pop(field, None)
                            page.summary_footer_metric_spacing.pop(field, None)
                            _refresh_footer_sample(); self._mark_builder_dirty(page)
                    q.customContextMenuRequested.connect(menu); footer_layout.addWidget(q); footer_layout.addSpacing(int(getattr(page,"summary_footer_metric_spacing",{}).get(f, 8 if linked else 16)))
                # La pagination possède désormais sa propre ligne de construction,
                # séparée du pied de page. Les totaux ne peuvent donc plus la
                # recouvrir lorsqu'ils sont déplacés horizontalement.
                footer_layout.addStretch(1)
                footer_layout.activate(); footer_layout.setEnabled(False)
                _positions = page.summary_metric_positions if linked else page.summary_footer_metric_positions
                _next_x = 6
                for _metric in footer_sample.findChildren(SummaryMetricLabel, options=Qt.FindChildOption.FindDirectChildrenOnly):
                    _key = str(_metric.metric_field); _x = int(_positions.get(_key, _next_x)); _positions.setdefault(_key, _x)
                    _metric.move(max(0, _x), max(1, (footer_sample.height()-_metric.height())//2)); _metric.show(); _metric.raise_()
                    _next_x = max(_next_x, _x + _metric.width() + 8)
                footer_sample.setStyleSheet(f"QFrame {{ background:{fst.get('bg','#FFFFFF')}; border:1px solid #aab7b1; }}")

            def _choose_footer_totals():
                dlg=QDialog(self); dlg.setWindowTitle("Totaux du pied de page"); vl=QVBoxLayout(dlg); vl.addWidget(QLabel("Choisissez les totaux à afficher dans le pied de page :")); checks=[]; selected=set(getattr(page,"summary_footer_metric_fields",set()) or set())
                for name,f in _footer_fields_available(): cb=QCheckBox(name); cb.setChecked(f in selected); vl.addWidget(cb); checks.append((f,cb))
                bb=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel); vl.addWidget(bb); bb.accepted.connect(dlg.accept); bb.rejected.connect(dlg.reject)
                if dlg.exec()==QDialog.DialogCode.Accepted: page.summary_footer_linked=False; page.summary_footer_metric_fields={f for f,cb in checks if cb.isChecked()}; _refresh_footer_sample(); self._mark_builder_dirty(page)

            def _edit_footer_style():
                st=dict(getattr(page,"summary_footer_style",{}) or {}); dlg=QDialog(self); dlg.setWindowTitle(tr("Mise en forme du pied de page", self.language)); form=QFormLayout(dlg)
                ff=QFontComboBox(); ff.setCurrentFont(QFont(str(st.get("font") or "Calibri"))); fs=QSpinBox(); fs.setRange(6,30); fs.setValue(int(st.get("size",10))); fs.setSuffix(" pt")
                bo=QCheckBox(tr("Gras", self.language)); bo.setChecked(bool(st.get("bold",True))); it=QCheckBox(tr("Italique", self.language)); it.setChecked(bool(st.get("italic",False))); al=QComboBox(); al.addItem(tr("Gauche", self.language),"left"); al.addItem(tr("Centré", self.language),"center"); al.addItem(tr("Droite", self.language),"right"); ai=al.findData(str(st.get("align") or "left")); al.setCurrentIndex(ai if ai>=0 else 0)
                tc=QPushButton("Couleur du texte"); tc.setProperty("mm3Color",str(st.get("text") or "#111111")); bg=QPushButton("Couleur du fond"); bg.setProperty("mm3Color",str(st.get("bg") or "#FFFFFF"))
                def cc(btn):
                    c=mm3_choose_color(dlg,QColor(str(btn.property("mm3Color") or "#000000")),"Couleur")
                    if c is not None and c.isValid(): btn.setProperty("mm3Color",c.name())
                tc.clicked.connect(lambda _=False:cc(tc)); bg.clicked.connect(lambda _=False:cc(bg)); form.addRow(tr("Police :", self.language),ff); form.addRow(tr("Taille :", self.language),fs)
                flw=QWidget(); fl=QHBoxLayout(flw); fl.setContentsMargins(0,0,0,0); fl.addWidget(bo); fl.addWidget(it); fl.addStretch(1); form.addRow(tr("Style :", self.language),flw); form.addRow(tr("Alignement :", self.language),al); form.addRow("Texte :",tc); form.addRow("Fond :",bg)
                bb=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel); form.addRow(bb); bb.accepted.connect(dlg.accept); bb.rejected.connect(dlg.reject)
                if dlg.exec()==QDialog.DialogCode.Accepted: page.summary_footer_style={"font":ff.currentFont().family(),"size":fs.value(),"bold":bo.isChecked(),"italic":it.isChecked(),"text":str(tc.property("mm3Color") or "#111111"),"bg":str(bg.property("mm3Color") or "#FFFFFF"),"align":str(al.currentData() or "left")}; _refresh_footer_sample(); self._mark_builder_dirty(page)

            # 1.0.122 — ligne dédiée à la pagination dans le constructeur.
            # Elle reproduit uniquement la présence, le format et la justification
            # du numéro de page ; le pied de page reste réservé aux totaux.
            page_number_sample = QFrame()
            page_number_sample.setMinimumHeight(32)
            page_number_sample.setStyleSheet("QFrame { background:#FFFFFF; border:1px solid #aab7b1; }")
            page_number_layout = QHBoxLayout(page_number_sample)
            page_number_layout.setContentsMargins(8, 2, 8, 2)
            page_number_layout.setSpacing(0)

            def _refresh_page_number_sample():
                while page_number_layout.count():
                    item = page_number_layout.takeAt(0)
                    w = item.widget()
                    if w is not None:
                        w.deleteLater()
                if not bool(getattr(page, "summary_page_numbers_enabled", False)):
                    page_number_layout.addStretch(1)
                    return
                fmt = str(getattr(page, "summary_page_number_format", "page_x_y") or "page_x_y")
                sample = "Page 1 / 2" if fmt == "page_x_y" else ("Page 1" if fmt == "page_x" else "1 / 2")
                align = str(getattr(page, "summary_page_number_align", "right") or "right")
                pn = QLabel(sample)
                pn.setStyleSheet("QLabel { background:transparent; border:0; padding:0; }")
                if align == "right":
                    page_number_layout.addStretch(1); page_number_layout.addWidget(pn)
                elif align == "center":
                    page_number_layout.addStretch(1); page_number_layout.addWidget(pn); page_number_layout.addStretch(1)
                else:
                    page_number_layout.addWidget(pn); page_number_layout.addStretch(1)

            def _edit_page_numbers():
                dlg=QDialog(self); dlg.setWindowTitle(tr("Numérotation des pages", self.language))
                form=QFormLayout(dlg)
                fmt=QComboBox(); fmt.addItem("Page 1 / 2","page_x_y"); fmt.addItem("Page 1","page_x"); fmt.addItem("1 / 2","x_y")
                i=fmt.findData(str(getattr(page,"summary_page_number_format","page_x_y") or "page_x_y")); fmt.setCurrentIndex(i if i>=0 else 0)
                align=QComboBox(); align.addItem(tr("Gauche", self.language),"left"); align.addItem(tr("Centré", self.language),"center"); align.addItem(tr("Droite", self.language),"right")
                i=align.findData(str(getattr(page,"summary_page_number_align","right") or "right")); align.setCurrentIndex(i if i>=0 else 2)
                form.addRow(tr("Présentation :", self.language),fmt); form.addRow(tr("Position :", self.language),align)
                bb=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel); bb.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("Annuler", self.language)); form.addRow(bb); bb.accepted.connect(dlg.accept); bb.rejected.connect(dlg.reject)
                if dlg.exec()==QDialog.DialogCode.Accepted:
                    page.summary_page_numbers_enabled=True; page.summary_page_number_format=str(fmt.currentData()); page.summary_page_number_align=str(align.currentData()); _refresh_footer_sample(); _refresh_page_number_sample(); self._mark_builder_dirty(page)

            def _footer_menu(pos):
                # 1.0.123 — le menu du pied ne contient plus les commandes de pagination.
                menu=QMenu(footer_sample)
                linked=menu.addAction(tr("Afficher les totaux du bandeau", self.language)); linked.setCheckable(True); linked.setChecked(bool(getattr(page,"summary_footer_linked",False)))
                choose=menu.addAction(tr("Choisir les totaux du pied de page…", self.language))
                style=menu.addAction(tr("Mise en forme du pied de page…", self.language))
                clear=menu.addAction(tr("Vider le pied de page", self.language))
                act=menu.exec(footer_sample.mapToGlobal(pos))
                if act==linked:
                    if detail_clone:
                        if linked.isChecked():
                            # L'action ajoute/copie les totaux du bandeau, sans
                            # synchroniser ensuite leurs positions ou leur ordre.
                            original = list(dict.fromkeys(self._ordered_summary_totals(page)))
                            page.summary_footer_metric_fields = set(original)
                            page.summary_footer_order = original
                            page.summary_footer_metric_positions = dict(getattr(page, "summary_metric_positions", {}) or {})
                            page.summary_footer_metric_widths = dict(getattr(page, "summary_metric_widths", {}) or {})
                        else:
                            # Décocher n'efface jamais les totaux déjà présents.
                            pass
                        page.summary_footer_linked = False
                    else:
                        page.summary_footer_linked = linked.isChecked()
                    _refresh_footer_sample(); self._mark_builder_dirty(page)
                elif act==choose: _choose_footer_totals()
                elif act==style: _edit_footer_style()
                elif act==clear: page.summary_footer_linked=False; page.summary_footer_metric_fields=set(); _refresh_footer_sample(); self._mark_builder_dirty(page)

            def _page_number_menu(pos):
                # La ligne N° de page possède désormais son propre menu contextuel.
                menu=QMenu(page_number_sample)
                pages=menu.addAction(tr("Numérotation des pages…", self.language))
                remove_pages=menu.addAction(tr("Supprimer la numérotation des pages", self.language)) if bool(getattr(page,"summary_page_numbers_enabled",False)) else None
                act=menu.exec(page_number_sample.mapToGlobal(pos))
                if act==pages:
                    _edit_page_numbers()
                elif remove_pages is not None and act==remove_pages:
                    page.summary_page_numbers_enabled=False
                    _refresh_page_number_sample()
                    self._mark_builder_dirty(page)

            footer_sample.setContextMenuPolicy(Qt.CustomContextMenu); footer_sample.customContextMenuRequested.connect(_footer_menu)
            page_number_sample.setContextMenuPolicy(Qt.CustomContextMenu); page_number_sample.customContextMenuRequested.connect(_page_number_menu)
            page.summary_footer_sample=footer_sample; page.refresh_summary_footer_sample=_refresh_footer_sample; _refresh_footer_sample()
            # 1.0.139 — exposer aussi le rafraîchissement de la ligne N° de page
            # afin que le chargement d’un état sauvegardé restitue immédiatement
            # son état visuel dans le constructeur.
            page.refresh_summary_page_number_sample = _refresh_page_number_sample
            _refresh_page_number_sample()
            def _reorder_total(order, field, before):
                if field not in order: return order
                order = [x for x in order if x != field]
                order.insert(order.index(before) if before in order else len(order), field)
                return order
            def reorder_band(field, before):
                if field not in self._ordered_summary_totals(page): return
                page.summary_metric_order = _reorder_total(self._ordered_summary_totals(page), field, before)
                self._refresh_summary_level_preview(page)
                if not detail_clone:
                    _refresh_footer_sample()
                self._mark_builder_dirty(page)
            def reorder_footer(field, before):
                if getattr(page, "summary_footer_linked", False):
                    reorder_band(field, before); return
                selected = set(getattr(page,"summary_footer_metric_fields",set()) or set())
                order = list(dict.fromkeys([str(x) for x in page.summary_footer_order if str(x) in selected]+[str(f) for _,f in self.fields if str(f) in selected]))
                page.summary_footer_order = _reorder_total(order, field, before)
                _refresh_footer_sample(); self._mark_builder_dirty(page)
            summary_header_sample.reorder_callback = reorder_band
            footer_sample.reorder_callback = reorder_footer

            def edit_summary_band_style(pos=None):
                st = dict(getattr(page, "summary_band_style", {}) or {})
                dlg = QDialog(self)
                _lang = str(getattr(self, "language", "fr") or "fr").lower()
                if _lang.startswith("de"):
                    dlg.setWindowTitle("Formatierung des Kopfbereichs")
                elif _lang.startswith("en"):
                    dlg.setWindowTitle("Header formatting")
                else:
                    dlg.setWindowTitle("Mise en forme du bandeau")
                form = QFormLayout(dlg)
                ff = QFontComboBox(); ff.setCurrentFont(QFont(str(st.get("font") or "Calibri")))
                fs = QSpinBox(); fs.setRange(6, 30); fs.setValue(int(st.get("size", 11))); fs.setSuffix(" pt")
                bold = QCheckBox(tr("Gras", self.language)); bold.setChecked(bool(st.get("bold", True)))
                italic = QCheckBox(tr("Italique", self.language)); italic.setChecked(bool(st.get("italic", False)))
                align = QComboBox(); align.addItem(tr("Gauche", self.language), "left"); align.addItem(tr("Centré", self.language), "center"); align.addItem(tr("Droite", self.language), "right")
                ai = align.findData(str(st.get("align") or "left")); align.setCurrentIndex(ai if ai >= 0 else 0)
                text_btn = QPushButton("Textfarbe" if _lang.startswith("de") else ("Text color" if _lang.startswith("en") else "Couleur du texte")); text_btn.setProperty("mm3Color", str(st.get("text") or "#8B3026"))
                bg_btn = QPushButton("Hintergrundfarbe" if _lang.startswith("de") else ("Background color" if _lang.startswith("en") else "Couleur du fond")); bg_btn.setProperty("mm3Color", str(st.get("bg") or "#FFFFFF"))
                def choose(btn):
                    c = mm3_choose_color(dlg, QColor(str(btn.property("mm3Color") or "#000000")), "Couleur")
                    if c is not None and c.isValid(): btn.setProperty("mm3Color", c.name())
                text_btn.clicked.connect(lambda: choose(text_btn)); bg_btn.clicked.connect(lambda: choose(bg_btn))
                form.addRow(tr("Police :", self.language), ff); form.addRow(tr("Taille :", self.language), fs)
                flags=QWidget(); fl=QHBoxLayout(flags); fl.setContentsMargins(0,0,0,0); fl.addWidget(bold); fl.addWidget(italic); fl.addStretch(1); form.addRow(tr("Style :", self.language), flags)
                form.addRow(tr("Alignement :", self.language), align)
                form.addRow("Text:" if _lang.startswith("de") else ("Text:" if _lang.startswith("en") else "Texte :"), text_btn)
                form.addRow("Hintergrund:" if _lang.startswith("de") else ("Background:" if _lang.startswith("en") else "Fond :"), bg_btn)
                buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
                if _lang.startswith("de"):
                    buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Abbrechen")
                elif _lang.startswith("fr"):
                    buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Annuler")
                form.addRow(buttons)
                buttons.accepted.connect(dlg.accept); buttons.rejected.connect(dlg.reject)
                if dlg.exec() == QDialog.DialogCode.Accepted:
                    page.summary_band_style = {"font":ff.currentFont().family(),"size":fs.value(),"bold":bold.isChecked(),"italic":italic.isChecked(),"text":str(text_btn.property("mm3Color") or "#8B3026"),"bg":str(bg_btn.property("mm3Color") or "#FFFFFF"),"align":str(align.currentData() or "left")}
                    self._mark_builder_dirty(page); self._refresh_summary_level_preview(page)
            summary_header_sample.setContextMenuPolicy(Qt.CustomContextMenu)
            summary_header_sample.customContextMenuRequested.connect(edit_summary_band_style)

            # 27.54 — le titre devient un élément à part entière de la Construction.
            # La case Imprimer est indépendante du texte : le titre peut rester
            # mémorisé dans le modèle tout en étant masqué à l'impression.
            title_row = QWidget(); title_row.setObjectName("summaryTitleSample")
            title_row.setFixedHeight(36)
            title_row_lay = QHBoxLayout(title_row); title_row_lay.setContentsMargins(6,1,6,1); title_row_lay.setSpacing(8)
            title_sample = QLabel(""); title_sample.setTextFormat(Qt.TextFormat.PlainText)
            title_sample.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            # 27.55 — quand « Imprimer » est décoché, le titre reste visible
            # dans sa couleur/mise en forme, mais atténué pour signaler son état.
            title_opacity = QGraphicsOpacityEffect(title_sample)
            title_opacity.setOpacity(1.0)
            title_sample.setGraphicsEffect(title_opacity)
            title_print = QCheckBox(tr("Imprimer le titre", self.language)); title_print.setChecked(True)
            title_row_lay.addWidget(title_sample, 0); title_row_lay.addWidget(title_print, 0)
            title_row_lay.addStretch(1)
            page.summary_title_sample = title_sample
            page.summary_title_print_widget = title_print
            page.summary_title_font_family = "Calibri"

            def _default_summary_title():
                name = str(getattr(page, "editing_report_name", None) or "").strip()
                label = tr("État détaillé" if detail_clone else "État résumé", self.language)
                return f"{label} : {name}" if name else label

            def _refresh_summary_title_sample():
                if not hasattr(page, "page_title_text_widget"):
                    return
                text = page.page_title_text_widget.text()
                shown = text if text != "" else _default_summary_title()
                page.summary_title_sample.setText(shown)
                f = QFont(str(getattr(page, "summary_title_font_family", "Calibri") or "Calibri"))
                f.setPointSize(int(page.page_title_size_widget.value()))
                f.setBold(bool(page.page_title_bold_widget.isChecked()))
                f.setItalic(bool(page.page_title_italic_widget.isChecked()))
                f.setUnderline(bool(page.page_title_underline_widget.isChecked()))
                page.summary_title_sample.setFont(f)
                al = str(page.page_title_align_widget.currentData() or "left")
                page.summary_title_sample.setAlignment((Qt.AlignHCenter if al=="center" else Qt.AlignRight if al=="right" else Qt.AlignLeft) | Qt.AlignVCenter)
                tc = str(page.page_title_text_color_widget.property("mm3Color") or "#111111")
                bg = str(page.page_title_bg_color_widget.property("mm3Color") or "#FFFFFF")
                page.summary_title_sample.setStyleSheet(f"QLabel {{ color:{tc}; background:{bg}; border:0; padding:2px 5px; }}")
                page.summary_title_print_widget.blockSignals(True)
                page.summary_title_print_widget.setChecked(bool(page.page_show_title_widget.isChecked()))
                page.summary_title_print_widget.blockSignals(False)
                # Conserver les couleurs choisies, mais griser visuellement le titre
                # lorsqu'il est mémorisé sans être destiné à l'impression.
                title_opacity.setOpacity(1.0 if page.summary_title_print_widget.isChecked() else 0.42)
                title_row.setStyleSheet("#summaryTitleSample { border:1px solid #c2cdc8; background:#FFFFFF; }")

            def _edit_summary_title(_pos=None):
                if not hasattr(page, "page_title_text_widget"):
                    return
                dlg=QDialog(self); dlg.setWindowTitle(tr("Titre de l’État", self.language))
                form=QFormLayout(dlg)
                txt=QLineEdit(page.page_title_text_widget.text())
                txt.setPlaceholderText(_default_summary_title())
                ff=QFontComboBox(); ff.setCurrentFont(QFont("Calibri" if str(getattr(page,"summary_title_font_family","Calibri") or "Calibri").casefold() == "arial" else str(getattr(page,"summary_title_font_family","Calibri") or "Calibri")))
                fs=QSpinBox(); fs.setRange(6,36); fs.setValue(page.page_title_size_widget.value()); fs.setSuffix(" pt")
                bo=QCheckBox(tr("Gras", self.language)); bo.setChecked(page.page_title_bold_widget.isChecked())
                it=QCheckBox(tr("Italique", self.language)); it.setChecked(page.page_title_italic_widget.isChecked())
                un=QCheckBox(tr("Souligné", self.language)); un.setChecked(page.page_title_underline_widget.isChecked())
                al=QComboBox(); al.addItem(tr("Gauche", self.language),"left"); al.addItem(tr("Centré", self.language),"center"); al.addItem(tr("Droite", self.language),"right")
                ai=al.findData(str(page.page_title_align_widget.currentData() or "left")); al.setCurrentIndex(ai if ai>=0 else 0)
                tc=QPushButton(tr("Choisir…", self.language)); tc.setProperty("mm3Color",str(page.page_title_text_color_widget.property("mm3Color") or "#111111"))
                bg=QPushButton(tr("Choisir…", self.language)); bg.setProperty("mm3Color",str(page.page_title_bg_color_widget.property("mm3Color") or "#FFFFFF"))
                def choose(btn,title):
                    c=mm3_choose_color(dlg,QColor(str(btn.property("mm3Color") or "#000000")),title)
                    if c is not None and c.isValid(): btn.setProperty("mm3Color",c.name())
                tc.clicked.connect(lambda _=False: choose(tc,"Couleur du texte")); bg.clicked.connect(lambda _=False: choose(bg,"Couleur du fond"))
                flags=QWidget(); fl=QHBoxLayout(flags); fl.setContentsMargins(0,0,0,0); fl.addWidget(bo); fl.addWidget(it); fl.addWidget(un); fl.addStretch(1)
                form.addRow(tr("Titre :", self.language),txt); form.addRow(tr("Police :", self.language),ff); form.addRow(tr("Taille :", self.language),fs); form.addRow(tr("Style :", self.language),flags); form.addRow(tr("Alignement :", self.language),al); form.addRow(tr("Couleur texte :", self.language),tc); form.addRow(tr("Couleur fond :", self.language),bg)
                buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
                buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("Annuler", self.language)); buttons.button(QDialogButtonBox.StandardButton.Ok).setText("OK")
                reset=buttons.addButton(tr("Rétablir par défaut", self.language),QDialogButtonBox.ButtonRole.ResetRole); form.addRow(buttons)
                buttons.accepted.connect(dlg.accept); buttons.rejected.connect(dlg.reject)
                def reset_title():
                    txt.clear(); ff.setCurrentFont(QFont("Calibri")); fs.setValue(20); bo.setChecked(True); it.setChecked(False); un.setChecked(False); al.setCurrentIndex(al.findData("left")); tc.setProperty("mm3Color","#111111"); bg.setProperty("mm3Color","#FFFFFF")
                reset.clicked.connect(reset_title)
                if dlg.exec()==QDialog.DialogCode.Accepted:
                    page.page_title_text_widget.setText(txt.text())
                    page.summary_title_font_family=ff.currentFont().family()
                    page.page_title_size_widget.setValue(fs.value()); page.page_title_bold_widget.setChecked(bo.isChecked()); page.page_title_italic_widget.setChecked(it.isChecked()); page.page_title_underline_widget.setChecked(un.isChecked())
                    page.page_title_align_widget.setCurrentIndex(page.page_title_align_widget.findData(str(al.currentData() or "left")))
                    page.page_title_text_color_widget.setProperty("mm3Color",str(tc.property("mm3Color") or "#111111")); page.page_title_bg_color_widget.setProperty("mm3Color",str(bg.property("mm3Color") or "#FFFFFF"))
                    _refresh_summary_title_sample(); self._mark_builder_dirty(page)
            title_sample.customContextMenuRequested.connect(_edit_summary_title)
            title_print.toggled.connect(lambda checked: (page.page_show_title_widget.setChecked(bool(checked)) if hasattr(page,"page_show_title_widget") else None, _refresh_summary_title_sample(), self._mark_builder_dirty(page)))
            page.refresh_summary_title_sample = _refresh_summary_title_sample

            # 27.61 — Interlignes et Filets sont de vrais éléments visuels de Construction.
            # Les anciens menus « Aucun / Espace / Filet » ont été supprimés.
            page.summary_layout_marks = {}
            page.summary_layout_mark_samples = {}
            _positions = [
                ("after_title", tr("Sous le titre", self.language)),
                ("after_band", tr("Sous le bandeau", self.language)),
                *(([("between_masters", tr("Entre les champs maîtres", self.language))] if detail_clone else [])),
                *(([("after_header", tr("Sous les en-têtes de colonnes", self.language))] if not detail_clone else
                   [("after_detail_labels", tr("Sous le libellé des colonnes", self.language))])),
                ("between_data", tr("Entre les lignes de données", self.language)),
                ("before_footer_line", tr("Entre les données et le filet du pied de page", self.language)),
                ("before_footer", tr("Avant le pied de page", self.language)),
            ]

            def _mark_sample(key):
                w = QLabel("")
                w.setMinimumHeight(0); w.setMaximumHeight(0)
                w.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                page.summary_layout_mark_samples[key] = w
                def menu_at(pos, k=key, lab=w):
                    items=_items_at(k)
                    if not items: return
                    m=QMenu(lab); actions={}
                    for item in items:
                        kind=str(item.get("kind") or "")
                        label=tr("Interligne", self.language) if kind=="space" else tr("Filet", self.language)
                        actions[m.addAction(tr("Modifier interligne…", self.language) if kind=="space" else tr("Modifier filet…", self.language))]=(kind,"edit")
                        actions[m.addAction(tr("Supprimer interligne", self.language) if kind=="space" else tr("Supprimer filet", self.language))]=(kind,"delete")
                    a=m.exec(lab.mapToGlobal(pos)); choice=actions.get(a)
                    if not choice:return
                    kind,op=choice
                    if op=="edit": _edit_layout_mark(k,kind)
                    else:
                        _store_items(k,[x for x in _items_at(k) if x.get("kind")!=kind]); _refresh_layout_marks(); self._mark_builder_dirty(page)
                w.customContextMenuRequested.connect(menu_at)
                return w

            def _items_at(key):
                raw=page.summary_layout_marks.get(key)
                items=raw if isinstance(raw,list) else ([raw] if raw else [])
                return [dict(x) for x in items if isinstance(x,dict) and str(x.get("kind") or "") in {"space","line"}]

            def _store_items(key, items):
                items=[dict(x) for x in items if isinstance(x,dict)]
                if not items: page.summary_layout_marks.pop(key,None)
                elif len(items)==1: page.summary_layout_marks[key]=items[0]
                else: page.summary_layout_marks[key]=items

            def _refresh_layout_marks():
                for key, lab in page.summary_layout_mark_samples.items():
                    items=_items_at(key)
                    if not items:
                        lab.setText(""); lab.setStyleSheet(""); lab.setMinimumHeight(0); lab.setMaximumHeight(0); continue
                    line=next((x for x in items if x.get("kind")=="line"),None)
                    space=next((x for x in items if x.get("kind")=="space"),None)
                    texts=[]
                    if line:
                        pt=max(0.5,float(line.get("size") or 0.5)); texts.append(f"{tr('Filet', self.language)} — {tr('Fin', self.language) if abs(pt-0.5)<0.01 else f'{pt:g} pt'}")
                    if space:
                        h=max(1,int(space.get("size") or 8)); texts.append(f"{tr('Interligne', self.language)} — {h} pt")
                    lab.setText("   +   ".join(texts))
                    lab.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                                     if detail_clone else Qt.AlignmentFlag.AlignCenter)
                    h=max(18, int(space.get("size") or 0) if space else 18)
                    lab.setMinimumHeight(h); lab.setMaximumHeight(h)
                    col=str(line.get("color") or "#000000") if line else "transparent"
                    width=max(0.5,float(line.get("size") or 0.5)) if line else 0
                    border=f"border-top:{width:g}px solid {col};" if line else "border:1px dashed #c7c7c7;"
                    padding = "padding-left:8px;" if detail_clone else ""
                    lab.setStyleSheet(f"QLabel {{ color:#555; background:#fafafa; {border} {padding} font-size:8pt; }}")
            page.refresh_summary_layout_marks=_refresh_layout_marks

            def _choose_position(title):
                dlg=QDialog(self); dlg.setWindowTitle(title); form=QFormLayout(dlg)
                combo=QComboBox(); [combo.addItem(label,key) for key,label in _positions]; form.addRow(tr("Emplacement :", self.language),combo)
                bb=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
                bb.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("Annuler", self.language)); bb.button(QDialogButtonBox.StandardButton.Ok).setText("OK")
                form.addRow(bb); bb.accepted.connect(dlg.accept); bb.rejected.connect(dlg.reject)
                return str(combo.currentData()) if dlg.exec()==QDialog.DialogCode.Accepted else None

            def _edit_layout_mark(key, kind=None):
                items=_items_at(key)
                current=next((x for x in items if x.get("kind")==kind),{}) if kind else (items[0] if items else {})
                kind=kind or str(current.get("kind") or "space")
                dlg=QDialog(self); dlg.setWindowTitle(tr("Interligne", self.language) if kind=="space" else tr("Filet", self.language)); form=QFormLayout(dlg)
                if kind=="space":
                    size=QSpinBox(); size.setRange(1,80); size.setValue(int(current.get("size") or 12)); size.setSuffix(" pt")
                else:
                    size=QComboBox(); size.addItem(tr("Fin", self.language),0.5); size.addItem("1 pt",1.0); size.addItem("2 pt",2.0)
                    cur=float(current.get("size") or 0.5); idx=min(range(size.count()),key=lambda i:abs(float(size.itemData(i))-cur)); size.setCurrentIndex(idx)
                form.addRow(tr("Hauteur :", self.language) if kind=="space" else tr("Épaisseur :", self.language),size)
                color_btn=None
                if kind=="line":
                    color=str(current.get("color") or "#000000"); color_btn=QPushButton(color); color_btn.setProperty("mm3Color",color)
                    def choose_color():
                        q=QColorDialog.getColor(QColor(str(color_btn.property("mm3Color") or color)),dlg,tr("Couleur du filet", self.language))
                        if q.isValid(): color_btn.setProperty("mm3Color",q.name()); color_btn.setText(q.name())
                    color_btn.clicked.connect(choose_color); form.addRow(tr("Couleur :", self.language),color_btn)
                bb=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel); bb.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("Annuler", self.language)); bb.button(QDialogButtonBox.StandardButton.Ok).setText("OK")
                form.addRow(bb); bb.accepted.connect(dlg.accept); bb.rejected.connect(dlg.reject)
                if dlg.exec()!=QDialog.DialogCode.Accepted:return
                value={"kind":kind,"size":(int(size.value()) if kind=="space" else float(size.currentData())),"color":str(color_btn.property("mm3Color") or "#000000") if color_btn else "#000000"}
                items=[x for x in items if x.get("kind")!=kind]; items.append(value); _store_items(key,items)
                _refresh_layout_marks(); self._mark_builder_dirty(page)

            def _add_mark(kind):
                key=_choose_position(tr("Insérer un interligne", self.language) if kind=="space" else tr("Insérer un filet", self.language))
                if key: _edit_layout_mark(key,kind)

            construction_grid.addWidget(QLabel(tr("Titre de l'État :", self.language)), 0, 0); construction_grid.addWidget(title_row, 0, 1)
            construction_grid.addWidget(_mark_sample("after_title"), 1, 1)
            construction_grid.addWidget(QLabel(tr("Bandeau :", self.language)), 2, 0); construction_grid.addWidget(summary_header_sample, 2, 1)
            construction_grid.addWidget(_mark_sample("after_band"), 3, 1)
            if detail_clone:
                # 1.0.127 — dans l’état détaillé, les libellés de colonnes
                # appartiennent à l’en-tête : ils sont donc placés immédiatement
                # sous le Bandeau, avant le Champ maître.
                summary_column_header_sample.setParent(page)
                summary_column_header_sample.hide()
                hidden_header_mark = _mark_sample("after_header")
                hidden_header_mark.setParent(page)
                hidden_header_mark.hide()
                construction_grid.addWidget(QLabel(tr("Libellés de colonne :", self.language)), 4, 0)
                construction_grid.addWidget(page.detail_label_row, 4, 1)
                construction_grid.addWidget(_mark_sample("after_detail_labels"), 5, 1)
            else:
                construction_grid.addWidget(QLabel(tr("En-tête colonnes :", self.language)), 4, 0)
                construction_grid.addWidget(summary_column_header_sample, 4, 1)
                construction_grid.addWidget(_mark_sample("after_header"), 5, 1)
            master_caption = QLabel(tr("Champ maître :", self.language))
            _master_caption_font = master_caption.font(); _master_caption_font.setBold(True); master_caption.setFont(_master_caption_font)
            if detail_clone:
                construction_grid.addWidget(master_caption, 6, 0)
            else:
                master_controls = QWidget()
                master_controls_layout = QVBoxLayout(master_controls)
                master_controls_layout.setContentsMargins(0, 0, 0, 0)
                master_controls_layout.setSpacing(3)
                master_controls_layout.addWidget(master_caption)
                vertical_choice = QComboBox()
                for label, value in ((tr("Haut", self.language), "top"), (tr("Centré", self.language), "center"), (tr("Bas", self.language), "bottom")):
                    vertical_choice.addItem(label, value)
                vertical_choice.setCurrentIndex(1)
                vertical_choice.setToolTip("Position de tous les champs dans chaque ligne de données")
                page.summary_vertical_align_widget = vertical_choice
                master_controls_layout.addWidget(vertical_choice)
                def choose_vertical_position(*_):
                    page.summary_vertical_align = str(vertical_choice.currentData() or "center")
                    rebuild_graphic_lanes()
                vertical_choice.currentIndexChanged.connect(choose_vertical_position)
                construction_grid.addWidget(master_controls, 6, 0)
            construction_grid.addWidget(master_lane, 6, 1)
            if detail_clone:
                construction_grid.addWidget(_mark_sample("between_masters"), 7, 1)
                totals_row = QHBoxLayout(); totals_row.setContentsMargins(0, 0, 0, 0)
                totals_row.addWidget(page.detail_group_totals_lane, 1)
                choose_total = QComboBox()
                choose_total.setMinimumWidth(145)
                choose_total.setMaximumWidth(175)
                choose_total.setMinimumHeight(28)
                choose_total.setMaxVisibleItems(9)
                choose_total.setStyleSheet("QComboBox { min-height:26px; padding-top:1px; padding-bottom:1px; } QComboBox QAbstractItemView { max-height:245px; }")
                choose_total.addItem(tr("Ajouter un total ▾", self.language), "")
                for label, field in sorted(self.fields, key=lambda pair: field_sort_key(pair[0])):
                    choose_total.addItem(str(label), str(field))
                def choose_group_total(index):
                    field = str(choose_total.itemData(index) or "")
                    if field:
                        drop_graphic_field(field, self.labels.get(field, field), "group_total")
                    choose_total.setCurrentIndex(0)
                choose_total.activated.connect(choose_group_total)
                totals_caption = QLabel(tr("Totaux par valeur maître :", self.language))
                totals_caption.setToolTip(tr("Ces totaux sont recalculés séparément pour chaque valeur du champ maître.", self.language))
                # 1.0.164 — cause du chevauchement corrigée : le libellé et la
                # liste « Ajouter un total » ne sont plus empilés dans un widget
                # fixe placé sur UNE seule ligne de grille. Cette ancienne structure
                # pouvait être comprimée différemment selon les métriques du texte
                # traduit, et le QComboBox débordait alors sur « Champs complémentaires ».
                #
                # Les trois niveaux sont désormais de vraies lignes de la grille,
                # identiques pour toutes les langues :
                #   8 = totaux (libellé + valeurs),
                #   9 = commande Ajouter un total,
                #  10 = champs complémentaires.
                # La géométrie ne dépend donc plus de la longueur des traductions.
                totals_caption.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                construction_grid.addWidget(totals_caption, 8, 0)
                construction_grid.addLayout(totals_row, 8, 1)
                # 1.0.165 — géométrie déterministe, calée sur le rendu anglais.
                # La différence FR/EN venait de l'espace libre que QGridLayout
                # redistribuait dans la ligne du combo selon la hauteur totale des
                # autres lignes (notamment les filets/interlignes enregistrés).
                # On ne laisse plus Qt fabriquer cet espace : combo de hauteur fixe
                # + vraie ligne d'interligne fixe, commune à toutes les langues.
                choose_total.setFixedHeight(28)
                construction_grid.addWidget(choose_total, 9, 0, alignment=Qt.AlignmentFlag.AlignTop)
                construction_grid.setRowMinimumHeight(9, 28)
                construction_grid.setRowStretch(9, 0)
                _totals_additional_gap = QSpacerItem(1, 14, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
                construction_grid.addItem(_totals_additional_gap, 10, 0, 1, 2)
                construction_grid.setRowMinimumHeight(10, 14)
                construction_grid.setRowStretch(10, 0)
                additional_caption = QLabel(tr("Champs complémentaires :", self.language))
                additional_caption.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                construction_grid.addWidget(additional_caption, 11, 0)
                construction_grid.addWidget(page.detail_secondary_free_row if detail_clone else secondary_lane, 11, 1)
            else:
                construction_grid.addWidget(QLabel(tr("Champs liés :", self.language)), 7, 0)
                construction_grid.addWidget(secondary_lane, 7, 1)
            if detail_clone:
                # 1.0.160 — la suite démarre sous le bloc autonome des totaux.
                _tail_row = 12
            else:
                _tail_row = 8
            construction_grid.addWidget(_mark_sample("between_data"), _tail_row, 1)
            construction_grid.addWidget(_mark_sample("before_footer_line"), _tail_row + 1, 1)
            construction_grid.addWidget(_mark_sample("before_footer"), _tail_row + 2, 1)
            construction_grid.addWidget(QLabel(tr("Pied de page :", self.language)), _tail_row + 3, 0); construction_grid.addWidget(footer_sample, _tail_row + 3, 1)
            construction_grid.addWidget(QLabel(tr("N° de page :", self.language)), _tail_row + 4, 0); construction_grid.addWidget(page_number_sample, _tail_row + 4, 1)
            page.summary_page_number_sample = page_number_sample
            page.refresh_summary_page_number_sample = _refresh_page_number_sample
            _refresh_page_number_sample()
            construction.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)

            elements_box=QGroupBox(tr("Éléments de construction", self.language))
            el=QHBoxLayout(elements_box); el.setContentsMargins(6,4,6,4); el.setSpacing(5)
            inter_btn=QPushButton(tr("+ Interligne", self.language)); line_btn=QPushButton(tr("+ Filet", self.language))
            inter_btn.clicked.connect(lambda: _add_mark("space")); line_btn.clicked.connect(lambda: _add_mark("line"))
            el.addWidget(inter_btn); el.addWidget(line_btn)
            fields_lay.insertWidget(max(0,fields_lay.count()-1), elements_box)

            page.summary_header_sample = summary_header_sample
            page.summary_column_header_sample = summary_column_header_sample
            page.summary_level1_sample = master_lane
            page.summary_level2_sample = secondary_lane
            page.rebuild_summary_graphic_lanes = rebuild_graphic_lanes

            # La première reconstruction graphique est volontairement différée :
            # les widgets du bandeau/totaux sont créés un peu plus bas.
            # La lancer ici déclenche la prévisualisation sur une page encore
            # incomplète (summary_show_groups_metric_widget, etc.).

            # Les anciens réglages de regroupement restent le moteur interne, mais
            # ne monopolisent plus l'écran : la construction graphique les pilote.
            grouping_box.setVisible(False)

            top_row = QHBoxLayout(); top_row.setSpacing(7)
            top_row.addWidget(fields_box, 0)
            if detail_clone:
                construction.setMinimumWidth(1510)
                builder_scroll = QScrollArea()
                # 1.0.157 — le canevas conserve sa hauteur utile : la zone de
                # défilement ne l'étire plus verticalement quand la fenêtre grandit.
                # La barre horizontale reste ainsi juste sous le constructeur et,
                # si la fenêtre rétrécit, reste dans le QScrollArea (donc visible).
                builder_scroll.setWidgetResizable(False)
                builder_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
                builder_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
                # 1.0.125 — réserver une vraie ligne visible sous le Pied de page
                # pour le N° de page ; la barre horizontale doit rester en dessous.
                # Géométrie de référence 1.0.144 : une seule structure du constructeur
                # pour toutes les langues, avec la ligne Page number entièrement visible.
                _detail_content_h = max(1, construction.sizeHint().height())
                construction.setMinimumHeight(_detail_content_h)
                construction.resize(max(construction.minimumWidth(), construction.sizeHint().width()), _detail_content_h)
                # Le scroll area peut se réduire avec la fenêtre ; sa barre horizontale
                # reste toujours au bord inférieur de sa propre zone visible.
                builder_scroll.setMinimumHeight(230)
                builder_scroll.setMaximumHeight(_detail_content_h + 24)
                builder_scroll.setWidget(construction)
                page.detail_print_guide = _A4GuideOverlay(construction)
                page.detail_print_guide.setToolTip("Limite imprimable A4 — portrait ou paysage")
                def update_detail_print_guide(*_args):
                    guide = page.detail_print_guide
                    if not guide or not master_lane.parentWidget():
                        return
                    mm = 287.0 if landscape.isChecked() else 200.0
                    start_x = master_lane.mapTo(construction, QPoint(0, 0)).x()
                    printable_w = int(round(mm * float(construction.logicalDpiX() or 96) / 25.4))
                    x = start_x + printable_w
                    # La justification Gauche/Centre/Droite du N° de page se lit
                    # dans la zone imprimable matérialisée par le pointillé.
                    page_number_sample.setMaximumWidth(max(120, printable_w))
                    guide.setGeometry(x, 8, 3, max(1, construction.height() - 16))
                    guide.raise_()
                    guide.show()
                page.update_detail_print_guide = update_detail_print_guide
                landscape.toggled.connect(update_detail_print_guide)
                QTimer.singleShot(0, update_detail_print_guide)
                top_row.addWidget(builder_scroll, 1)
            else:
                top_row.addWidget(construction, 1)
            lay.addLayout(top_row)


            header_metrics_box = QGroupBox("Bandeau d’En-tête / Totaux")
            header_metrics_box.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Maximum,
            )
            header_metrics_grid = QGridLayout(header_metrics_box)
            header_metrics_grid.setContentsMargins(7, 3, 7, 4)
            header_metrics_grid.setHorizontalSpacing(4)
            header_metrics_grid.setVerticalSpacing(2)

            show_groups_metric = QCheckBox("Groupes")
            show_selected_metrics = QCheckBox("Totaux cochés")
            show_species_metric = QCheckBox("Valeurs distinctes")
            show_records_metric = QCheckBox("Nombre de fiches")
            for check in (show_groups_metric, show_selected_metrics, show_species_metric, show_records_metric):
                check.setChecked(True)
                check.setFixedHeight(22)
            # Aucun compteur de regroupement implicite : il doit être demandé explicitement.
            show_groups_metric.setChecked(False)

            def summary_metric_size(default):
                spin = QSpinBox()
                spin.setRange(8, 24)
                spin.setValue(default)
                spin.setSuffix(" pt")
                spin.setMaximumWidth(70)
                spin.setFixedHeight(23)
                return spin

            summary_groups_font = QFontComboBox()
            summary_groups_font.setCurrentFont(QFont("Calibri"))
            summary_groups_font.setMaximumWidth(155)

            summary_selected_font = QFontComboBox()
            summary_selected_font.setCurrentFont(QFont("Calibri"))
            summary_selected_font.setMaximumWidth(155)

            summary_species_font = QFontComboBox()
            summary_species_font.setCurrentFont(QFont("Calibri"))
            summary_species_font.setMaximumWidth(155)

            summary_records_font = QFontComboBox()
            summary_records_font.setCurrentFont(QFont("Calibri"))
            summary_records_font.setMaximumWidth(155)

            summary_groups_size = summary_metric_size(11)
            summary_selected_size = summary_metric_size(11)
            summary_species_size = summary_metric_size(11)
            summary_records_size = summary_metric_size(10)

            summary_groups_text = make_color_button("Texte", "#8B3026")
            summary_selected_text = make_color_button("Texte", "#8B3026")
            summary_species_text = make_color_button("Texte", "#8B3026")
            summary_records_text = make_color_button("Texte", "#7A817D")

            summary_groups_bg = make_color_button("Fond", "#F4F6F5")
            summary_selected_bg = make_color_button("Fond", "#F4F6F5")
            summary_species_bg = make_color_button("Fond", "#F4F6F5")
            summary_records_bg = make_color_button("Fond", "#F4F6F5")

            # Même organisation visuelle que dans l'État détaillé :
            # deux familles compactes, nettement séparées.
            left_metrics = QWidget()
            left_metrics_lay = QGridLayout(left_metrics)
            left_metrics_lay.setContentsMargins(0, 0, 0, 0)
            left_metrics_lay.setHorizontalSpacing(4)
            left_metrics_lay.setVerticalSpacing(2)

            left_metrics_lay.addWidget(show_groups_metric, 0, 0)
            left_metrics_lay.addWidget(summary_groups_font, 0, 1)
            left_metrics_lay.addWidget(summary_groups_size, 0, 2)
            left_metrics_lay.addWidget(summary_groups_text, 0, 3)
            left_metrics_lay.addWidget(summary_groups_bg, 0, 4)

            # Ancien compteur « Valeurs distinctes » retiré de l’interface.
            # Les widgets restent instanciés pour lire sans erreur les anciens modèles,
            # mais ils ne sont plus affichés ni utilisés.
            show_species_metric.setChecked(False)

            right_metrics = QWidget()
            right_metrics_lay = QGridLayout(right_metrics)
            right_metrics_lay.setContentsMargins(0, 0, 0, 0)
            right_metrics_lay.setHorizontalSpacing(4)
            right_metrics_lay.setVerticalSpacing(2)

            right_metrics_lay.addWidget(show_selected_metrics, 0, 0)
            right_metrics_lay.addWidget(summary_selected_font, 0, 1)
            right_metrics_lay.addWidget(summary_selected_size, 0, 2)
            right_metrics_lay.addWidget(summary_selected_text, 0, 3)
            right_metrics_lay.addWidget(summary_selected_bg, 0, 4)

            right_metrics_lay.addWidget(show_records_metric, 1, 0)
            right_metrics_lay.addWidget(summary_records_font, 1, 1)
            right_metrics_lay.addWidget(summary_records_size, 1, 2)
            right_metrics_lay.addWidget(summary_records_text, 1, 3)
            right_metrics_lay.addWidget(summary_records_bg, 1, 4)

            header_metrics_grid.addWidget(left_metrics, 0, 0, 2, 4)
            header_metrics_grid.setColumnMinimumWidth(4, 95)
            header_metrics_grid.setColumnStretch(4, 1)
            header_metrics_grid.addWidget(right_metrics, 0, 5, 2, 4)

            # Paramètres génériques des compteurs (compact, une seule ligne).
            summary_groups_label = QLineEdit(); summary_groups_label.setPlaceholderText("Libellé groupes (auto)"); summary_groups_label.setMaximumWidth(160)
            summary_distinct_field = QComboBox(); [summary_distinct_field.addItem(label, field) for label, field in self.fields]; summary_distinct_field.setMaximumWidth(155)
            summary_distinct_label = QLineEdit(); summary_distinct_label.setPlaceholderText("Libellé valeurs (auto)"); summary_distinct_label.setMaximumWidth(160)
            opts = QWidget(); ol = QHBoxLayout(opts); ol.setContentsMargins(0,0,0,0); ol.setSpacing(5)
            ol.addWidget(QLabel("Groupes :")); ol.addWidget(summary_groups_label); ol.addStretch(1)
            summary_distinct_field.setVisible(False)
            summary_distinct_label.setVisible(False)
            header_metrics_grid.addWidget(opts, 2, 0, 1, 9)

            page.summary_show_groups_metric_widget = show_groups_metric
            page.summary_show_selected_metrics_widget = show_selected_metrics
            page.summary_show_species_metric_widget = show_species_metric
            page.summary_show_records_metric_widget = show_records_metric
            page.summary_groups_label_widget = summary_groups_label
            page.summary_distinct_field_widget = summary_distinct_field
            page.summary_distinct_label_widget = summary_distinct_label

            page.summary_groups_font_widget = summary_groups_font
            page.summary_selected_font_widget = summary_selected_font
            page.summary_species_font_widget = summary_species_font
            page.summary_records_font_widget = summary_records_font

            page.summary_groups_size_widget = summary_groups_size
            page.summary_selected_size_widget = summary_selected_size
            page.summary_species_size_widget = summary_species_size
            page.summary_records_size_widget = summary_records_size

            page.summary_groups_text_widget = summary_groups_text
            page.summary_selected_text_widget = summary_selected_text
            page.summary_species_text_widget = summary_species_text
            page.summary_records_text_widget = summary_records_text

            page.summary_groups_bg_widget = summary_groups_bg
            page.summary_selected_bg_widget = summary_selected_bg
            page.summary_species_bg_widget = summary_species_bg
            page.summary_records_bg_widget = summary_records_bg
            summary_groups_label.textChanged.connect(lambda *_: (self._mark_builder_dirty(page), self._refresh_atelier_sample(page)))
            summary_distinct_label.textChanged.connect(lambda *_: (self._mark_builder_dirty(page), self._refresh_atelier_sample(page)))
            summary_distinct_field.currentIndexChanged.connect(lambda *_: (self._mark_builder_dirty(page), self._refresh_atelier_sample(page)))

            # Rafraîchissement direct de la miniature Atelier.
            # Ces contrôles récents n'étaient pas reliés au rafraîchissement
            # dynamique historique.
            for font_widget in (
                summary_groups_font,
                summary_selected_font,
                summary_species_font,
                summary_records_font,
            ):
                font_widget.currentFontChanged.connect(
                    lambda *_args, p=page:
                        self._refresh_summary_level_preview(p)
                )

            for metric_widget, signal_name in (
                (summary_groups_size, "valueChanged"),
                (summary_selected_size, "valueChanged"),
                (summary_species_size, "valueChanged"),
                (summary_records_size, "valueChanged"),
                (show_groups_metric, "toggled"),
                (show_selected_metrics, "toggled"),
                (show_species_metric, "toggled"),
                (show_records_metric, "toggled"),
            ):
                getattr(metric_widget, signal_name).connect(
                    lambda *_args, p=page:
                        self._refresh_summary_level_preview(p)
                )

            for color_button in (
                summary_groups_text,
                summary_selected_text,
                summary_species_text,
                summary_records_text,
                summary_groups_bg,
                summary_selected_bg,
                summary_species_bg,
                summary_records_bg,
            ):
                color_button.clicked.connect(
                    lambda _checked=False, p=page:
                        QTimer.singleShot(
                            0,
                            lambda p=p:
                                self._refresh_summary_level_preview(p)
                        )
                )

            # Réglage du champ sélectionné supprimé : les choix Colonne / Total
            # sont désormais directement visibles dans la liste des champs.


            summary_detail_box = QGroupBox("Détail des groupes maîtres")
            summary_detail_grid = QGridLayout(summary_detail_box)
            summary_detail_grid.setContentsMargins(7, 4, 7, 5)
            summary_detail_grid.setHorizontalSpacing(4)
            summary_detail_grid.setVerticalSpacing(2)

            detail_headers = (
                "Élément", "Police", "Taille", "Gras", "Italique", "Souligné",
                "Alignement", "Texte", "Fond"
            )
            for col, label in enumerate(detail_headers):
                header_label = QLabel(label)
                header_label.setStyleSheet("font-weight:600;")
                summary_detail_grid.addWidget(header_label, 0, col)

            # En-tête des colonnes.
            column_header_font = QFontComboBox()
            column_header_font.setCurrentFont(QFont("Calibri"))
            column_header_font.setMaximumWidth(175)
            page.advanced_column_header_font_widget = column_header_font

            summary_detail_grid.addWidget(QLabel("En-tête colonnes"), 1, 0)
            summary_detail_grid.addWidget(column_header_font, 1, 1)
            summary_detail_grid.addWidget(column_header_size, 1, 2)
            summary_detail_grid.addWidget(column_header_bold, 1, 3)
            summary_detail_grid.addWidget(column_header_italic, 1, 4)
            summary_detail_grid.addWidget(column_header_underline, 1, 5)
            summary_detail_grid.addWidget(column_header_align, 1, 6)
            summary_detail_grid.addWidget(column_header_text, 1, 7)
            summary_detail_grid.addWidget(column_header_bg, 1, 8)

            def make_summary_detail_style(
                size_value, bold_value, italic_value, underline_value,
                align_value, text_value, bg_value
            ):
                font = QFontComboBox()
                font.setCurrentFont(QFont("Calibri"))
                font.setMaximumWidth(175)

                size = QSpinBox()
                size.setRange(6, 24)
                size.setValue(size_value)
                size.setSuffix(" pt")
                size.setMaximumWidth(72)

                bold = QCheckBox()
                italic = QCheckBox()
                underline = QCheckBox()
                bold.setChecked(bold_value)
                italic.setChecked(italic_value)
                underline.setChecked(underline_value)
                for chk in (bold, italic, underline):
                    chk.setFixedWidth(22)

                align = QComboBox()
                align.addItem(tr("Gauche", self.language), "left")
                align.addItem(tr("Centré", self.language), "center")
                align.addItem(tr("Droite", self.language), "right")
                idx = align.findData(align_value)
                align.setCurrentIndex(idx if idx >= 0 else 0)
                align.setMaximumWidth(105)

                text_button = make_color_button("Texte", text_value)
                bg_button = make_color_button("Fond", bg_value)
                return {
                    "font": font,
                    "size": size,
                    "bold": bold,
                    "italic": italic,
                    "underline": underline,
                    "align": align,
                    "text_color": text_button,
                    "bg_color": bg_button,
                }

            master_style = make_summary_detail_style(
                10, True, False, False, "right", "#9A3324", "#FFFFFF"
            )
            secondary_style = make_summary_detail_style(
                10, False, False, False, "left", "#111111", "#FFFFFF"
            )

            page.advanced_typography_widgets["summary_master"] = master_style
            page.advanced_typography_widgets["summary_secondary"] = secondary_style

            for row, (label, style_widgets) in enumerate((
                ("Détail du groupe maître", master_style),
                ("Détail des groupes secondaires", secondary_style),
            ), start=2):
                summary_detail_grid.addWidget(QLabel(label), row, 0)
                summary_detail_grid.addWidget(style_widgets["font"], row, 1)
                summary_detail_grid.addWidget(style_widgets["size"], row, 2)
                summary_detail_grid.addWidget(style_widgets["bold"], row, 3)
                summary_detail_grid.addWidget(style_widgets["italic"], row, 4)
                summary_detail_grid.addWidget(style_widgets["underline"], row, 5)
                summary_detail_grid.addWidget(style_widgets["align"], row, 6)
                summary_detail_grid.addWidget(style_widgets["text_color"], row, 7)
                summary_detail_grid.addWidget(style_widgets["bg_color"], row, 8)

            # Traits — intégrés dans le même bloc.
            borders = QComboBox()
            borders.addItem("Aucune", "none")
            borders.addItem("Horizontales", "horizontal")
            borders.addItem("Grille", "grid")
            borders.setMaximumWidth(125)

            detail_trait = QComboBox()
            detail_trait.addItem("Aucun", "none")
            detail_trait.addItem("Filet", "hairline")
            detail_trait.addItem("1 point", "1pt")
            detail_trait.addItem("2 points", "2pt")
            detail_trait.setMaximumWidth(100)

            group_trait = QComboBox()
            group_trait.addItem("Aucun", "none")
            group_trait.addItem("Filet", "hairline")
            group_trait.addItem("1 point", "1pt")
            group_trait.addItem("2 points", "2pt")
            group_trait.setCurrentIndex(group_trait.findData("1pt"))
            group_trait.setMaximumWidth(100)

            header_trait = QComboBox()
            header_trait.addItem("Aucun", "none")
            header_trait.addItem("Filet", "hairline")
            header_trait.addItem("1 point", "1pt")
            header_trait.addItem("2 points", "2pt")
            header_trait.setCurrentIndex(header_trait.findData("2pt"))
            header_trait.setMaximumWidth(100)

            traits_row = QWidget()
            traits_lay = QHBoxLayout(traits_row)
            traits_lay.setContentsMargins(0, 0, 0, 0)
            traits_lay.setSpacing(5)
            traits_lay.addWidget(QLabel("Bordures :"))
            traits_lay.addWidget(borders)
            traits_lay.addSpacing(5)
            traits_lay.addWidget(QLabel("Trait entre lignes :"))
            traits_lay.addWidget(detail_trait)
            traits_lay.addSpacing(5)
            traits_lay.addWidget(QLabel("Avant groupe :"))
            traits_lay.addWidget(group_trait)
            traits_lay.addSpacing(5)
            traits_lay.addWidget(QLabel("Sous en-tête :"))
            traits_lay.addWidget(header_trait)
            traits_lay.addStretch(1)

            summary_detail_grid.addWidget(QLabel("Traits :"), 4, 0)
            summary_detail_grid.addWidget(traits_row, 4, 1, 1, 8)

            page.advanced_detail_borders_widget = borders
            page.advanced_detail_trait_widget = detail_trait
            page.advanced_group_trait_widget = group_trait
            page.advanced_header_trait_widget = header_trait

            summary_detail_box.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Maximum,
            )

            # 27.41 — anciens panneaux conservés en mémoire pour la compatibilité
            # des modèles historiques, mais retirés de l’interface du nouvel Atelier.
            summary_detail_box.setVisible(False)
            header_metrics_box.setVisible(False)
            lay.addWidget(summary_detail_box)
            lay.addWidget(header_metrics_box)
            # Le traitement du champ et l’alignement du résumé sont placés
            # sur une même ligne plus bas afin d’économiser la hauteur.

            page.group_widget = group; page.date_group_mode_widget = date_mode; page.second_group_widget = second
            page.calc_widget = QComboBox(); page.calc_widget.addItem("Champs sélectionnés", "selected_fields")
            page.no_details_widget = QRadioButton(); page.no_details_widget.setChecked(True)
            page.details_widget = QRadioButton(); page.details_widget.setChecked(False)
            page.summary_color_widget = None; page.summary_bold_widget = None

            def refresh_date_mode():
                current = group.currentData()
                is_date = self._is_date_field(current)
                date_mode_label.setVisible(is_date)
                date_mode.setVisible(is_date)
            group.currentIndexChanged.connect(lambda *_: refresh_date_mode())

            summary_fields.model().rowsMoved.connect(lambda *_: (self._mark_builder_dirty(page), self._refresh_summary_level_preview(page)))
            refresh_date_mode()

        if kind == "summary":
            summary_alignment_box = QGroupBox("Alignement des colonnes du résumé")
            summary_alignment_row = QHBoxLayout(summary_alignment_box)
            summary_alignment_row.setContentsMargins(7, 2, 7, 3)
            summary_alignment_row.setSpacing(5)
            summary_alignment_field = QComboBox()
            summary_alignment_field.setMinimumWidth(210)
            summary_alignment_choice = QComboBox()
            summary_alignment_choice.addItem(tr("Gauche", self.language), "left")
            summary_alignment_choice.addItem(tr("Centré", self.language), "center")
            summary_alignment_choice.addItem(tr("Droite", self.language), "right")
            summary_alignment_choice.setMinimumWidth(100)
            summary_alignment_row.addWidget(QLabel("Colonne :"))
            summary_alignment_row.addWidget(summary_alignment_field)
            summary_alignment_row.addWidget(QLabel("Alignement :"))
            summary_alignment_row.addWidget(summary_alignment_choice)
            summary_alignment_row.addStretch(1)
            page.summary_alignment_field_widget = summary_alignment_field
            page.summary_alignment_choice_widget = summary_alignment_choice

            def refresh_summary_alignment_fields():
                previous = summary_alignment_field.currentData()
                summary_alignment_field.blockSignals(True)
                summary_alignment_field.clear()
                if page.group_widget.currentData() is not None:
                    summary_alignment_field.addItem(
                        page.group_widget.currentText(), "__group__"
                    )
                for i in range(page.summary_fields_widget.count()):
                    item = page.summary_fields_widget.item(i)
                    field = str(item.data(Qt.ItemDataRole.UserRole))
                    pair = getattr(page, "summary_field_row_widgets", {}).get(field)
                    if pair is not None and pair[0].isChecked():
                        summary_alignment_field.addItem(self.labels.get(field, str(item.data(Qt.ItemDataRole.UserRole + 1) or field)), field)
                summary_alignment_field.blockSignals(False)
                if summary_alignment_field.count() == 0:
                    summary_alignment_choice.setEnabled(False)
                    return
                idx = summary_alignment_field.findData(previous)
                summary_alignment_field.setCurrentIndex(idx if idx >= 0 else 0)
                summary_alignment_choice.setEnabled(True)
                field = str(summary_alignment_field.currentData())
                pos = summary_alignment_choice.findData(
                    page.summary_column_alignments.get(field, "left")
                )
                summary_alignment_choice.blockSignals(True)
                summary_alignment_choice.setCurrentIndex(pos if pos >= 0 else 0)
                summary_alignment_choice.blockSignals(False)

            def refresh_summary_alignment_choice():
                if summary_alignment_field.count() == 0:
                    return
                field = str(summary_alignment_field.currentData())
                pos = summary_alignment_choice.findData(
                    page.summary_column_alignments.get(field, "left")
                )
                summary_alignment_choice.blockSignals(True)
                summary_alignment_choice.setCurrentIndex(pos if pos >= 0 else 0)
                summary_alignment_choice.blockSignals(False)

            def store_summary_alignment():
                if summary_alignment_field.count() == 0:
                    return
                page.summary_column_alignments[
                    str(summary_alignment_field.currentData())
                ] = str(summary_alignment_choice.currentData() or "left")
                self._mark_builder_dirty(page)

            for _col_cb, _total_cb in getattr(page, "summary_field_row_widgets", {}).values():
                _col_cb.toggled.connect(lambda *_: refresh_summary_alignment_fields())
            page.group_widget.currentIndexChanged.connect(
                lambda *_: refresh_summary_alignment_fields()
            )
            summary_alignment_field.currentIndexChanged.connect(
                lambda *_: refresh_summary_alignment_choice()
            )
            summary_alignment_choice.currentIndexChanged.connect(
                lambda *_: store_summary_alignment()
            )
            refresh_summary_alignment_fields()
            summary_alignment_box.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum
            )

            # Le réglage ambigu du champ sélectionné a été supprimé.
            # L'alignement reste directement accessible, sur une ligne compacte.
            summary_alignment_box.setVisible(False)
            lay.addWidget(summary_alignment_box)

        # L'état détaillé conserve son bloc avancé séparé.
        # Pour le résumé, les réglages avancés sont fusionnés dans Regroupements.
        if kind == "detail":
            advanced_box = self._build_advanced_editor_panel(kind, page)
            advanced_box.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Maximum,
            )
            lay.addWidget(advanced_box)
        else:
            page.advanced_editor_box = None

        page_chrome_box = self._build_page_chrome_panel(page)
        if kind == "summary":
            # Le nouvel État résumé gère Bandeau / En-têtes / Pied directement
            # dans la Construction. Le vieux panneau reste disponible en interne
            # pour relire les anciens modèles.
            page_chrome_box.setVisible(False)
        lay.addWidget(page_chrome_box)
        page.page_chrome_box = page_chrome_box
        if kind == "summary" and hasattr(page, "refresh_summary_title_sample"):
            page.refresh_summary_title_sample()
            for _sig in (page.page_title_text_widget.textChanged, page.page_title_size_widget.valueChanged,
                         page.page_title_bold_widget.toggled, page.page_title_italic_widget.toggled,
                         page.page_title_underline_widget.toggled, page.page_title_align_widget.currentIndexChanged,
                         page.page_show_title_widget.toggled):
                _sig.connect(lambda *_: page.refresh_summary_title_sample())

        actions = QHBoxLayout()

        back = QPushButton("← " + tr("Retour", self.language))
        back.setFixedHeight(28)
        back.clicked.connect(lambda: self._return_from_builder())
        actions.addWidget(back)

        undo_btn = QPushButton(tr("Défaire", self.language))
        redo_btn = QPushButton(tr("Refaire", self.language))
        for _btn in (undo_btn, redo_btn):
            _btn.setFixedHeight(28)
            _btn.setStyleSheet(
                "QPushButton { background:#f2b8b5; border:1px solid #d89a96; border-radius:4px; padding:3px 12px; }"
                "QPushButton:disabled { background:#f7dddd; color:#b8a3a3; border-color:#ead0d0; }"
                "QPushButton:enabled { background:#e88984; color:#111111; }"
            )
        undo_btn.setEnabled(False); redo_btn.setEnabled(False)
        undo_btn.clicked.connect(lambda: self._builder_undo(kind, page))
        redo_btn.clicked.connect(lambda: self._builder_redo(kind, page))
        page.undo_button = undo_btn; page.redo_button = redo_btn
        actions.addWidget(undo_btn); actions.addWidget(redo_btn)
        actions.addStretch(1)

        save_btn = QPushButton(tr("Sauvegarder", self.language))
        # Les synchronisations graphiques du Résumé peuvent marquer la page
        # comme modifiée pendant la construction de l’interface. Les alias
        # doivent donc exister avant ces premiers signaux/appels.
        page.builder_save_button = save_btn
        page.save_button = save_btn
        page.update_button = save_btn
        save_btn.setEnabled(False)
        save_btn.setToolTip(
            tr("Nouveau : disponible après Aperçu. Existant : disponible après modification.", self.language)
        )
        open_library_btn = QPushButton(tr("Ouvrir un modèle…", self.language))
        open_library_btn.setToolTip(tr("Charger un modèle depuis la bibliothèque Modèles d’États", self.language))
        library_btn = QPushButton(tr("Enregistrer ce modèle", self.language))
        library_btn.setToolTip("Conserver directement cet état dans la bibliothèque Modèles d’États")
        preview = QPushButton(tr("Aperçu", self.language))
        print_btn = QPushButton(tr("Imprimer", self.language))

        save_btn.clicked.connect(
            lambda: self._save_report_from_builder("detail" if detail_clone else kind, page)
        )
        open_library_btn.clicked.connect(self.open_report_from_library)
        library_btn.clicked.connect(
            lambda: self._save_report_builder_to_library("detail" if detail_clone else kind, page)
        )
        preview.clicked.connect(
            lambda: self._preview("detail" if detail_clone else kind, page, source, title, landscape, False)
        )
        print_btn.clicked.connect(
            lambda: self._preview("detail" if detail_clone else kind, page, source, title, landscape, True)
        )

        actions.addWidget(save_btn)
        actions.addWidget(open_library_btn)
        actions.addWidget(library_btn)
        actions.addWidget(preview)
        actions.addWidget(print_btn)

        page.save_button = save_btn
        # Compatibilité interne avec le code existant qui référence encore update_button.
        page.update_button = save_btn
        lay.addLayout(actions)

        self._connect_builder_change_tracking(kind, page)
        return page

    def _mark_builder_dirty(self, page) -> None:
        page._builder_dirty = True
        if getattr(page, "_loading_state", False):
            return
        # 27.131 — historique adouci : on photographie l'état APRÈS le lot de
        # signaux Qt de l'action courante. Le point zéro est installé seulement
        # une fois le modèle complètement chargé, jamais pendant sa reconstruction.
        if hasattr(page, "undo_button") and not getattr(page, "_undo_restoring", False):
            if not getattr(page, "_undo_capture_pending", False):
                page._undo_capture_pending = True
                QTimer.singleShot(0, lambda p=page: self._capture_builder_undo_state(p))
        page.builder_dirty = True
        page.preview_done = False
        # Sauvegarde locale de l’état : disponible dès qu’une modification
        # est effectuée, qu’il s’agisse d’un nouvel état ou d’un état existant.
        # L’aperçu reste facultatif et « Enregistrer ce modèle » conserve
        # son rôle distinct vers la bibliothèque de modèles.
        save_button = getattr(page, "save_button", None)
        if save_button is not None:
            save_button.setEnabled(True)

    def _init_builder_undo(self, kind: str, page) -> None:
        """Installe le modèle chargé comme point zéro, sans créer d'étape Défaire."""
        if not hasattr(page, "undo_button"):
            return
        try:
            current = self._definition_from_builder(kind, page)
            page._undo_current = json.loads(json.dumps(current, ensure_ascii=False))
        except Exception:
            page._undo_current = None
        page._undo_kind = kind
        page._undo_stack = []
        page._redo_stack = []
        page._undo_capture_pending = False
        page._undo_restoring = False
        page.undo_button.setEnabled(False)
        page.redo_button.setEnabled(False)

    def _capture_builder_undo_state(self, page) -> None:
        page._undo_capture_pending = False
        if getattr(page, "_loading_state", False) or getattr(page, "_undo_restoring", False):
            return
        kind = str(getattr(page, "_undo_kind", "summary"))
        try:
            current = self._definition_from_builder(kind, page)
            current = json.loads(json.dumps(current, ensure_ascii=False))
        except Exception:
            return
        previous = getattr(page, "_undo_current", None)
        if previous is None:
            page._undo_current = current
            return
        if current == previous:
            return
        stack = getattr(page, "_undo_stack", [])
        stack.append(previous)
        if len(stack) > 10:
            del stack[:-10]
        page._undo_stack = stack
        page._undo_current = current
        page._redo_stack = []
        page.undo_button.setEnabled(bool(stack))
        page.redo_button.setEnabled(False)

    def _restore_builder_undo_definition(self, kind: str, page, definition: dict) -> None:
        """Restaure une photographie complète en réutilisant le chargeur éprouvé des modèles."""
        actual_name = getattr(page, "editing_report_name", None)
        current_edit = self.current_edit_report_name
        temp_name = "__MM3_UNDO_TEMP__"
        old_temp = self.saved_reports.get(temp_name)
        page._undo_restoring = True
        try:
            self.saved_reports[temp_name] = json.loads(json.dumps(definition, ensure_ascii=False))
            self._load_report_into_builder(temp_name)
            page.editing_report_name = actual_name
            self.current_edit_report_name = current_edit
            self._refresh_builder_banner(page, kind)
        finally:
            if old_temp is None:
                self.saved_reports.pop(temp_name, None)
            else:
                self.saved_reports[temp_name] = old_temp
            page._undo_restoring = False

    def _builder_undo(self, kind: str, page) -> None:
        stack = getattr(page, "_undo_stack", [])
        if not stack:
            return
        target = stack.pop()
        current = getattr(page, "_undo_current", None)
        redo = getattr(page, "_redo_stack", [])
        if current is not None:
            redo.append(current)
            if len(redo) > 10:
                del redo[:-10]
        self._restore_builder_undo_definition(kind, page, target)
        page._undo_stack = stack; page._redo_stack = redo; page._undo_current = target
        page.undo_button.setEnabled(bool(stack)); page.redo_button.setEnabled(bool(redo))
        self._mark_builder_dirty(page)

    def _builder_redo(self, kind: str, page) -> None:
        redo = getattr(page, "_redo_stack", [])
        if not redo:
            return
        target = redo.pop()
        current = getattr(page, "_undo_current", None)
        stack = getattr(page, "_undo_stack", [])
        if current is not None:
            stack.append(current)
            if len(stack) > 10:
                del stack[:-10]
        self._restore_builder_undo_definition(kind, page, target)
        page._undo_stack = stack; page._redo_stack = redo; page._undo_current = target
        page.undo_button.setEnabled(bool(stack)); page.redo_button.setEnabled(bool(redo))
        self._mark_builder_dirty(page)

    def _mark_preview_done(self, page) -> None:
        page.preview_done = True
        # Un nouvel état devient sauvegardable après un aperçu réussi.
        if not getattr(page, "editing_report_name", None):
            save_button = getattr(page, "save_button", None)
            if save_button is not None:
                save_button.setEnabled(True)

    def _reset_builder_state(self, page) -> None:
        page._builder_dirty = False
        page.builder_dirty = False
        page.preview_done = False
        save_button = getattr(page, "save_button", None)
        if save_button is not None:
            save_button.setEnabled(False)

    def _connect_builder_change_tracking(self, kind, page) -> None:
        if getattr(page, "_change_tracking_connected", False):
            return

        signals = [
            page.title_widget.textChanged,
            page.source_widget.currentIndexChanged,
            page.portrait_widget.toggled,
            page.landscape_widget.toggled,
        ]

        if kind == "detail":
            signals.append(page.fields_widget.itemChanged)
            for combo in page.detail_grouping_widgets:
                signals.append(combo.currentIndexChanged)
            signals.extend([
                page.atelier_repeat_master_widget.currentIndexChanged,
                page.atelier_spacing_widget.valueChanged,
                page.atelier_show_groups.toggled,
                page.atelier_show_boxes.toggled,
                page.atelier_show_species.toggled,
                page.atelier_show_records.toggled,
                page.atelier_metric_groups_font.currentFontChanged,page.atelier_metric_boxes_font.currentFontChanged,
                page.atelier_metric_species_font.currentFontChanged,page.atelier_metric_records_font.currentFontChanged,
                page.atelier_metric_groups_size.valueChanged,page.atelier_metric_boxes_size.valueChanged,
                page.atelier_metric_species_size.valueChanged,page.atelier_metric_records_size.valueChanged,
                page.atelier_metric_groups_bold.toggled,page.atelier_metric_boxes_bold.toggled,
                page.atelier_metric_species_bold.toggled,page.atelier_metric_records_bold.toggled,
                page.atelier_metric_groups_italic.toggled,page.atelier_metric_boxes_italic.toggled,
                page.atelier_metric_species_italic.toggled,page.atelier_metric_records_italic.toggled,
                page.atelier_metric_groups_underline.toggled,page.atelier_metric_boxes_underline.toggled,
                page.atelier_metric_species_underline.toggled,page.atelier_metric_records_underline.toggled,
            ])
        else:
            signals.extend([
                page.group_widget.currentIndexChanged,
                page.date_group_mode_widget.currentIndexChanged,
                page.second_group_widget.currentIndexChanged,
                page.no_details_widget.toggled,
                page.details_widget.toggled,
                page.summary_show_groups_metric_widget.toggled,
                page.summary_show_selected_metrics_widget.toggled,
                page.summary_show_species_metric_widget.toggled,
                page.summary_show_records_metric_widget.toggled,
                page.summary_groups_font_widget.currentFontChanged,
                page.summary_selected_font_widget.currentFontChanged,
                page.summary_species_font_widget.currentFontChanged,
                page.summary_records_font_widget.currentFontChanged,
                page.summary_groups_size_widget.valueChanged,
                page.summary_selected_size_widget.valueChanged,
                page.summary_species_size_widget.valueChanged,
                page.summary_records_size_widget.valueChanged,
            ])

        advanced_signals = [
            page.advanced_header_title_widget.textChanged,
            page.advanced_separator_widget.toggled,
        ]
        for widget_name, signal_name in (
            ("page_show_title_widget", "toggled"),
            ("page_title_text_widget", "textChanged"),
            ("page_title_size_widget", "valueChanged"),
            ("page_title_bold_widget", "toggled"),
            ("page_title_italic_widget", "toggled"),
            ("page_title_underline_widget", "toggled"),
            ("page_title_align_widget", "currentIndexChanged"),
            ("page_show_collection_widget", "toggled"),
            ("page_show_print_date_widget", "toggled"),
            ("page_show_page_numbers_widget", "toggled"),
            ("page_print_font_widget", "currentIndexChanged"),
            ("page_body_size_widget", "valueChanged"),
            ("page_footer_text_widget", "textChanged"),
            ("page_footer_size_widget", "valueChanged"),
            ("page_footer_bold_widget", "toggled"),
            ("page_footer_italic_widget", "toggled"),
            ("page_footer_underline_widget", "toggled"),
            ("page_footer_align_widget", "currentIndexChanged"),
        ):
            widget = getattr(page, widget_name, None)
            if widget is not None:
                advanced_signals.append(getattr(widget, signal_name))
        for widget_name, signal_name in (
            ("advanced_band_font_widget", "currentFontChanged"),
            ("advanced_column_header_font_widget", "currentFontChanged"),
            ("advanced_column_header_size_widget", "valueChanged"),
            ("advanced_column_header_bold_widget", "toggled"),
            ("advanced_column_header_italic_widget", "toggled"),
            ("advanced_column_header_underline_widget", "toggled"),
            ("advanced_column_header_align_widget", "currentIndexChanged"),
        ):
            widget = getattr(page, widget_name, None)
            if widget is not None:
                advanced_signals.append(getattr(widget, signal_name))
        for widget_name in (
            "advanced_detail_borders_widget",
            "advanced_detail_trait_widget",
            "advanced_group_trait_widget",
            "advanced_header_trait_widget",
        ):
            widget = getattr(page, widget_name, None)
            if widget is not None:
                advanced_signals.append(widget.currentIndexChanged)

        for group in getattr(page, "advanced_typography_widgets", {}).values():
            if "font" in group:
                advanced_signals.append(group["font"].currentFontChanged)
            advanced_signals.extend([
                group["size"].valueChanged,
                group["bold"].toggled,
                group["italic"].toggled,
                group["underline"].toggled,
                group["align"].currentIndexChanged,
            ])

        for signal in signals + advanced_signals:
            signal.connect(lambda *_args, pg=page: self._mark_builder_dirty(pg))

        for signal in advanced_signals:
            signal.connect(
                lambda *_args, k=kind, pg=page:
                    self._refresh_advanced_live_preview(k, pg)
            )

        if kind == "summary":
            # Tous les widgets de l'Atelier État existent maintenant : on peut
            # construire les couloirs graphiques et leur prévisualisation.
            if hasattr(page, "rebuild_summary_graphic_lanes"):
                page.rebuild_summary_graphic_lanes()
            for signal in (
                page.group_widget.currentIndexChanged,page.date_group_mode_widget.currentIndexChanged,page.second_group_widget.currentIndexChanged,
                page.summary_show_groups_metric_widget.toggled,page.summary_show_selected_metrics_widget.toggled,
                page.summary_show_species_metric_widget.toggled,page.summary_show_records_metric_widget.toggled,
                page.summary_groups_size_widget.valueChanged,page.summary_selected_size_widget.valueChanged,
                page.summary_species_size_widget.valueChanged,page.summary_records_size_widget.valueChanged,
            ):
                signal.connect(lambda *_args, pg=page: self._refresh_summary_level_preview(pg))
            self._refresh_summary_level_preview(page)

        page._change_tracking_connected = True


    def _build_page_chrome_panel(self, page) -> QGroupBox:
        """Réglages généraux d'en-tête et de pied de page de l'état."""
        box = QGroupBox("En-tête général / Pied de page")
        grid = QGridLayout(box)
        grid.setContentsMargins(6, 3, 6, 4)
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(2)

        def color_button(label: str, color: str) -> QPushButton:
            button = QPushButton(label)
            button.setProperty("mm3Color", color)
            button.setFixedWidth(64)
            button.setFixedHeight(24)

            def apply_style(value: str) -> None:
                q = QColor(value)
                foreground = "#F4F4F4" if q.lightness() < 120 else "#111111"
                button.setStyleSheet(
                    "QPushButton {"
                    f"background-color:{value}; color:{foreground};"
                    "padding:1px 3px; min-width:60px; max-width:64px;"
                    "border:1px solid #9aa9a3; border-radius:4px;}"
                )

            def choose_color() -> None:
                current = QColor(str(button.property("mm3Color") or color))
                dialog = QColorDialog(current, self)
                dialog.setWindowTitle("Choisir une couleur")

                translations = {
                    "Basic colors": "Couleurs de base",
                    "Custom colors": "Couleurs personnalisées",
                    "Pick Screen Color": "Choisir une couleur à l’écran",
                    "Add to Custom Colors": "Ajouter aux couleurs personnalisées",
                    "Hue:": "Teinte :",
                    "Sat:": "Saturation :",
                    "Val:": "Valeur :",
                    "Red:": "Rouge :",
                    "Green:": "Vert :",
                    "Blue:": "Bleu :",
                    "HTML:": "HTML :",
                    "OK": "OK",
                    "Cancel": "Annuler",
                }

                for child in dialog.findChildren(QLabel):
                    key = child.text().replace("&", "")
                    if key in translations:
                        child.setText(translations[key])

                for child in dialog.findChildren(QPushButton):
                    key = child.text().replace("&", "")
                    if key in translations:
                        child.setText(translations[key])

                for box in dialog.findChildren(QDialogButtonBox):
                    cancel = box.button(QDialogButtonBox.StandardButton.Cancel)
                    if cancel is not None:
                        cancel.setText("Annuler")
                    ok = box.button(QDialogButtonBox.StandardButton.Ok)
                    if ok is not None:
                        ok.setText("OK")

                if dialog.exec() == QDialog.DialogCode.Accepted:
                    chosen = dialog.selectedColor()
                    if chosen.isValid():
                        value = chosen.name()
                        button.setProperty("mm3Color", value)
                        apply_style(value)
                        self._mark_builder_dirty(page)

            apply_style(color)
            button.clicked.connect(choose_color)
            return button

        show_title = QCheckBox("Afficher")
        show_title.setChecked(True)

        title_text = QLineEdit()
        title_text.setPlaceholderText("Titre affiché de l’état")
        title_text.setFixedHeight(24)

        title_size = QSpinBox()
        title_size.setRange(6, 36)
        title_size.setValue(20)
        title_size.setSuffix(" pt")
        title_size.setMaximumWidth(82)

        title_bold = QCheckBox(tr("Gras", self.language))
        title_bold.setChecked(True)
        title_italic = QCheckBox(tr("Italique", self.language))
        title_underline = QCheckBox(tr("Souligné", self.language))

        title_align = QComboBox()
        title_align.addItem(tr("Gauche", self.language), "left")
        title_align.addItem(tr("Centré", self.language), "center")
        title_align.addItem(tr("Droite", self.language), "right")
        title_align.setMaximumWidth(120)

        title_text_color = color_button("Texte", "#111111")
        title_bg_color = color_button("Fond", "#FFFFFF")

        show_collection = QCheckBox("Nom de la collection")
        show_collection.setChecked(False)

        show_print_date = QCheckBox("Date d’impression")
        show_print_date.setChecked(False)

        show_page_numbers = QCheckBox("Pagination")
        show_page_numbers.setChecked(True)

        footer_text = QLineEdit()
        footer_text.setPlaceholderText("Texte libre du pied de page (facultatif)")
        footer_text.setFixedHeight(24)

        body_size = QSpinBox()
        body_size.setRange(6, 18)
        body_size.setValue(10)
        body_size.setSuffix(" pt")
        body_size.setMaximumWidth(82)

        print_font = QComboBox()
        print_font.setMinimumWidth(190)
        print_font.setMaximumWidth(280)

        installed_families = list(QFontDatabase.families())
        preferred_fonts = [
            "Calibri", "Calibri Light", "Arial", "Arial Narrow",
            "Segoe UI", "Tahoma", "Verdana", "Times New Roman",
        ]
        ordered_fonts = []
        for family in preferred_fonts:
            if family in installed_families and family not in ordered_fonts:
                ordered_fonts.append(family)
        for family in installed_families:
            if family not in ordered_fonts:
                ordered_fonts.append(family)
        for family in ordered_fonts:
            print_font.addItem(family, family)

        default_font = (
            "Calibri" if "Calibri" in ordered_fonts else
            "Segoe UI" if "Segoe UI" in ordered_fonts else
            "Arial" if "Arial" in ordered_fonts else
            (ordered_fonts[0] if ordered_fonts else "Arial")
        )
        idx = print_font.findData(default_font)
        if idx >= 0:
            print_font.setCurrentIndex(idx)

        footer_size = QSpinBox()
        footer_size.setRange(6, 24)
        footer_size.setValue(10)
        footer_size.setSuffix(" pt")
        footer_size.setMaximumWidth(82)

        footer_bold = QCheckBox(tr("Gras", self.language))
        footer_italic = QCheckBox(tr("Italique", self.language))
        footer_underline = QCheckBox(tr("Souligné", self.language))

        footer_align = QComboBox()
        footer_align.addItem(tr("Gauche", self.language), "left")
        footer_align.addItem(tr("Centré", self.language), "center")
        footer_align.addItem(tr("Droite", self.language), "right")
        footer_align.setCurrentIndex(2)
        footer_align.setMaximumWidth(120)

        footer_text_color = color_button("Texte", "#4F5A55")
        footer_bg_color = color_button("Fond", "#FFFFFF")

        # Ligne 1 : titre et typographie.
        grid.addWidget(QLabel("En-tête :"), 0, 0)
        grid.addWidget(show_title, 0, 1)
        grid.addWidget(title_text, 0, 2, 1, 3)
        grid.addWidget(title_size, 0, 5)
        grid.addWidget(title_bold, 0, 6)
        grid.addWidget(title_italic, 0, 7)
        grid.addWidget(title_underline, 0, 8)
        grid.addWidget(title_align, 0, 9)
        grid.addWidget(title_text_color, 0, 10)
        grid.addWidget(title_bg_color, 0, 11)

        separator_widget = getattr(page, "advanced_separator_widget", None)
        if separator_widget is not None:
            separator_widget.setText("Séparateur")
            grid.addWidget(separator_widget, 1, 5)

        # Ligne 2 : compléments d'en-tête et pied de page.
        grid.addWidget(QLabel("Compléments :"), 1, 0)
        grid.addWidget(show_collection, 1, 1, 1, 2)
        grid.addWidget(show_print_date, 1, 3, 1, 2)

        # "Corps de l’état" n'est plus affiché.
        # print_font et body_size restent créés et stockés comme repli technique.

        grid.addWidget(QLabel("Pied de page :"), 2, 0)
        grid.addWidget(show_page_numbers, 2, 1)
        grid.addWidget(footer_text, 2, 2, 1, 3)
        grid.addWidget(footer_size, 2, 5)
        grid.addWidget(footer_bold, 2, 6)
        grid.addWidget(footer_italic, 2, 7)
        grid.addWidget(footer_underline, 2, 8)
        grid.addWidget(footer_align, 2, 9)
        grid.addWidget(footer_text_color, 2, 10)
        grid.addWidget(footer_bg_color, 2, 11)

        page.page_show_title_widget = show_title
        page.page_title_text_widget = title_text
        page.page_title_size_widget = title_size
        page.page_title_bold_widget = title_bold
        page.page_title_italic_widget = title_italic
        page.page_title_underline_widget = title_underline
        page.page_title_align_widget = title_align
        page.page_title_text_color_widget = title_text_color
        page.page_title_bg_color_widget = title_bg_color
        page.page_show_collection_widget = show_collection
        page.page_show_print_date_widget = show_print_date
        page.page_show_page_numbers_widget = show_page_numbers
        page.page_print_font_widget = print_font
        page.page_body_size_widget = body_size
        page.page_footer_text_widget = footer_text
        page.page_footer_size_widget = footer_size
        page.page_footer_bold_widget = footer_bold
        page.page_footer_italic_widget = footer_italic
        page.page_footer_underline_widget = footer_underline
        page.page_footer_align_widget = footer_align
        page.page_footer_text_color_widget = footer_text_color
        page.page_footer_bg_color_widget = footer_bg_color

        box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        box.adjustSize()
        box.setMaximumHeight(box.sizeHint().height() + 4)
        return box

    def _refresh_builder_banner(self, page, kind: str) -> None:
        """Affiche toujours le nom courant de l'état dans le bandeau du constructeur."""
        label = getattr(page, "builder_banner_label", None)
        if label is None:
            return

        prefix = tr("État détaillé" if kind == "detail" else "État résumé", self.language)
        current_name = str(getattr(page, "editing_report_name", None) or "").strip()

        # Les noms personnels restent inchangés ; seul le nom système du nouveau modèle est traduit.
        display_name = current_name or tr("Nouveau modèle d’État", self.language)
        active_label = tr("Modèle actif", self.language)
        label.setText(f"{prefix} — {active_label}: {display_name}")
        self.report_page_title.setText(f"{tr('États', self.language)} — {tr('Modèle', self.language)}: {display_name}")
        self.setWindowTitle(f"{tr('États', self.language)} — {collection_display_name(self.collection, self.language)} — {display_name}")


    def _open_builder(self, index: int) -> None:
        self.records = self.manager.list_records(int(self.collection["id"]))
        self.saved_queries = self._load_saved_queries()
        self.saved_reports = self._load_saved_reports()
        self._refresh_saved_reports_list()

        page = self.stack.widget(index)
        self.report_page_subtitle.setVisible(False)
        self._set_builder_context_visibility(page)
        page._loading_state = True
        if index == 1 and hasattr(page, "detail_column_alignments"):
            page.detail_column_alignments = {}
        # Recharger immédiatement la liste « Source (issue des requêtes) »
        # afin qu'une requête créée pendant la session soit disponible sans
        # fermer puis relancer MM3.
        current_source = page.source_widget.currentData()
        page.source_widget.blockSignals(True)
        page.source_widget.clear()
        page.source_widget.addItem(tr("Toute la collection", self.language), None)
        for query_name in sorted(self.saved_queries, key=str.casefold):
            page.source_widget.addItem(
                f"Requête enregistrée : {query_name}", query_name
            )
        source_index = page.source_widget.findData(current_source)
        page.source_widget.setCurrentIndex(source_index if source_index >= 0 else 0)
        page.source_widget.blockSignals(False)
        page.editing_report_name = None
        if index == 2:
            page.group_widget.setCurrentIndex(0)
            page.second_group_widget.setCurrentIndex(0)
        self._apply_advanced_style_to_page(page, {})
        self.current_edit_report_name = None

        # Un nouveau constructeur repart de valeurs neutres.
        page.title_widget.setText(
            tr("État détaillé" if index == 1 else "État résumé", self.language)
        )
        page.page_show_title_widget.setChecked(True)
        page.page_title_text_widget.clear()
        page.summary_title_font_family = "Calibri"
        if hasattr(page, "refresh_summary_title_sample"):
            page.refresh_summary_title_sample()
        page.page_title_size_widget.setValue(20)
        page.page_title_bold_widget.setChecked(True)
        page.page_title_italic_widget.setChecked(False)
        page.page_title_underline_widget.setChecked(False)
        page.page_title_align_widget.setCurrentIndex(0)
        page.page_show_collection_widget.setChecked(False)
        page.page_show_print_date_widget.setChecked(False)
        page.page_show_page_numbers_widget.setChecked(True)
        for preferred in ("Calibri", "Segoe UI", "Arial"):
            idx = page.page_print_font_widget.findData(preferred)
            if idx >= 0:
                page.page_print_font_widget.setCurrentIndex(idx)
                break
        page.page_body_size_widget.setValue(10)
        page.page_footer_text_widget.clear()
        page.page_footer_size_widget.setValue(10)
        page.page_footer_bold_widget.setChecked(False)
        page.page_footer_italic_widget.setChecked(False)
        page.page_footer_underline_widget.setChecked(False)
        page.page_footer_align_widget.setCurrentIndex(2)
        if hasattr(page, "summary_show_groups_metric_widget"):
            # 27.135 — aucun total natif/legacy ne doit apparaître spontanément
            # dans un nouvel État résumé. Les totaux du bandeau sont désormais
            # exclusivement ceux explicitement cochés « Total » par l’utilisateur.
            # Ces quatre cases cachées appartiennent à l’ancien moteur et leurs
            # valeurs True réinjectaient notamment « groupes », « espèces » et
            # « Nombre de fiches », avec parfois un doublon du total Espèce actuel.
            page.summary_show_groups_metric_widget.setChecked(False)
            page.summary_show_selected_metrics_widget.setChecked(False)
            page.summary_show_species_metric_widget.setChecked(False)
            page.summary_show_records_metric_widget.setChecked(False)
            page.summary_groups_size_widget.setValue(11)
            page.summary_selected_size_widget.setValue(11)
            page.summary_species_size_widget.setValue(11)
            page.summary_records_size_widget.setValue(10)
        self._set_combo_by_data(page.source_widget, None)
        try:
            default_orientation = self.model_manager.collection_preferences(
                int(self.collection["id"])
            )["report_orientation"]
        except Exception:
            default_orientation = "portrait"
        if default_orientation == "landscape":
            page.landscape_widget.setChecked(True)
        else:
            page.portrait_widget.setChecked(True)
        if index == 1 and not getattr(page, "detail_summary_clone", False):
            for combo in page.detail_grouping_widgets:
                self._set_combo_by_data(combo, None)
            self._apply_atelier_style_to_page(page, self._default_atelier_style())
        if index == 2 or getattr(page, "detail_summary_clone", False):
            self._set_combo_by_data(page.group_widget, None)
            self._set_combo_by_data(page.second_group_widget, None)

            # 27.138 — Nouveau modèle d'État = construction réellement vierge.
            # Les éléments graphiques vivent en dehors des anciens combos et pouvaient
            # survivre en mémoire (ex. le dernier champ Date redevenait maître).
            page.summary_graphic_master = None
            page.summary_graphic_secondaries = []
            page.summary_metric_fields.clear()
            page.summary_metric_labels.clear()
            page.summary_metric_widths = {}
            page.summary_metric_positions = {}
            page.summary_metric_styles.clear()
            page.summary_column_alignments = {}
            page.summary_treatments = {}
            page.summary_field_styles = {}
            page.summary_column_header_labels = {}
            page.summary_column_header_styles = {}
            page.summary_column_header_hidden = set()
            page.summary_footer_linked = False
            page.summary_footer_metric_fields = set()
            page.summary_footer_metric_styles = {}
            page.summary_footer_metric_labels = {}
            page.summary_footer_metric_spacing = {}
            page.summary_footer_metric_widths = {}
            page.summary_footer_metric_positions = {}
            page.summary_page_numbers_enabled = False
            page.summary_page_number_format = "page_x_y"
            page.summary_page_number_align = "right"
            page.summary_layout_marks = {}
            # Garder les QLabel déjà placés dans la grille : les vider avec
            # ce dictionnaire rendait les nouveaux filets/interlignes invisibles.
            if hasattr(page, "refresh_summary_layout_marks"):
                page.refresh_summary_layout_marks()
            for _field, (_col_cb, _total_cb) in page.summary_field_row_widgets.items():
                _col_cb.blockSignals(True); _col_cb.setChecked(False); _col_cb.blockSignals(False)
                _total_cb.blockSignals(True); _total_cb.setChecked(False); _total_cb.blockSignals(False)
            if hasattr(page, "rebuild_summary_graphic_lanes"):
                page.rebuild_summary_graphic_lanes()

        # Verrou final : un nouvel état Résumé est toujours vierge de regroupement.
        # Ce verrou est volontairement placé après toutes les initialisations.
        if index == 2 or getattr(page, "detail_summary_clone", False):
            page.group_widget.blockSignals(True)
            page.second_group_widget.blockSignals(True)
            page.group_widget.setCurrentIndex(0)
            page.second_group_widget.setCurrentIndex(0)
            page.group_widget.blockSignals(False)
            page.second_group_widget.blockSignals(False)

        page._loading_state = False
        if getattr(page, "detail_summary_clone", False):
            page.detail_master_styles = {}
            page.detail_group_totals = []
            page.detail_total_styles = {}
            page.detail_column_labels = {}
            page.detail_label_styles = {}
            page.detail_column_widths = {}

        if index == 2 or getattr(page, "detail_summary_clone", False):
            self._refresh_summary_level_preview(page)
            if hasattr(page, "summary_treatment_widget"):
                page.summary_treatment_widget.setEnabled(False)
            if hasattr(page, "summary_treatment_name"):
                page.summary_treatment_name.setText("Champ : —")

        self._reset_builder_state(page)
        self._init_builder_undo("detail" if index == 1 else "summary", page)
        self._refresh_builder_banner(
            page,
            "detail" if index == 1 else "summary",
        )
        self.stack.setCurrentIndex(index)
        QTimer.singleShot(0, self._fit_builder_window)

    @staticmethod
    def _move(widget: QListWidget, direction: int) -> None:
        row = widget.currentRow()
        target = row + direction
        if row < 0 or target < 0 or target >= widget.count():
            return
        item = widget.takeItem(row)
        widget.insertItem(target, item)
        widget.setCurrentRow(target)

    def _records_for_source(self, source_name: str | None) -> list[dict]:
        # Toujours relire la base : les fiches peuvent avoir été modifiées
        # depuis l'ouverture du module États.
        self.records = self._merge_custom_values(
            self.manager.list_records(int(self.collection["id"]))
        )
        records = list(self.records)
        if not source_name:
            return records
        state = self.saved_queries.get(source_name, {})
        criteria = state.get("criteria", []) if isinstance(state, dict) else []
        if not criteria:
            return records

        def matches(record: dict) -> bool:
            result = None
            for index, criterion in enumerate(criteria):
                field = str(criterion.get("field", ""))
                value = record.get(field, "")
                ok = TableWindow._matches_filter(
                    value,
                    str(criterion.get("value", "")),
                    str(criterion.get("operator", "contient")),
                    str(criterion.get("value2", "")),
                )
                if index == 0 or result is None:
                    result = ok
                elif str(criterion.get("connector", "and")) == "or":
                    result = result or ok
                else:
                    result = result and ok
            return bool(result)

        return [record for record in records if matches(record)]

    def _sync_builder_after_preview_save(self, page, kind: str, name: str) -> None:
        """Synchronise immédiatement le constructeur après un Enregistrer depuis l'aperçu."""
        if page is None or not name:
            return
        page.editing_report_name = name
        self.current_edit_report_name = name
        self._refresh_builder_banner(page, kind)
        self._reset_builder_state(page)

    def _return_to_builder_from_preview(self, dialog, page) -> None:
        dialog.accept()
        if page is None: return
        self.stack.setCurrentWidget(page)
        self.showNormal(); self.raise_(); self.activateWindow()

    def _preview(self, kind, page, source, title, landscape, print_preview) -> None:
        records = self._records_for_source(source.currentData())
        report_title = title.text().strip() or "État"

        if kind == "detail" and getattr(page, "detail_summary_clone", False):
            definition = self._definition_from_builder("detail", page)
            fields = list(definition.get("detail_secondary_fields") or [])
            master = (definition.get("detail_groupings") or [None])[0]
            if not fields and master:
                fields = [master]
            if not fields:
                QMessageBox.information(self, "Aucun champ", "Ajoutez au moins un champ complémentaire.")
                return
            editing_name = getattr(page, "editing_report_name", None)
            saved = self.saved_reports.get(editing_name, {}) if editing_name else {}
            dlg = GroupedDetailPreviewDialog(
                self, report_title, records, fields, [master] if master else [],
                landscape.isChecked(), self,
                source_name=source.currentData(), saved_name=editing_name,
                layout_state=dict(getattr(page, "_detail_preview_layout_state", None) or saved.get("layout") or {}),
                atelier_style=dict(definition.get("atelier_style") or self._default_atelier_style()),
                advanced_style=dict(definition.get("advanced_style") or {}),
                page_chrome=dict(definition.get("page_chrome") or {}),
                detail_column_alignments=dict(definition.get("detail_column_alignments") or {}),
                detail_graphic=definition,
            )
            dlg.builder_page = page
            if print_preview:
                dlg._print()
                dlg.deleteLater()
            else:
                self._detail_preview = dlg
                dlg.setModal(False)
                dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
                dlg.destroyed.connect(lambda *_: setattr(self, "_detail_preview", None))
                dlg.show(); dlg.raise_(); dlg.activateWindow()
            self._mark_preview_done(page)
            return

        if kind == "detail":
            fields = []
            widget = page.fields_widget
            for i in range(widget.count()):
                item = widget.item(i)
                if item.checkState() == Qt.CheckState.Checked:
                    fields.append(str(item.data(Qt.ItemDataRole.UserRole)))
            if not fields:
                QMessageBox.information(
                    self, "Aucun champ", "Choisissez au moins un champ."
                )
                return

            editing_name = getattr(page, "editing_report_name", None)
            saved_layout = (
                self.saved_reports.get(editing_name, {}).get("layout", {})
                if editing_name else {}
            )
            groupings = self._normalized_detail_groupings(
                [combo.currentData() for combo in page.detail_grouping_widgets]
            )
            atelier_style = self._atelier_style_from_page(page)
            repeat_field = atelier_style.get("repeat_master_field")
            if repeat_field:
                fields = [field for field in fields if field != repeat_field]
                fields.insert(0, repeat_field)

            if groupings:
                dlg = GroupedDetailPreviewDialog(
                    self, report_title, records, fields, groupings,
                    landscape.isChecked(), self,
                    source_name=source.currentData(),
                    saved_name=editing_name, layout_state=saved_layout,
                    atelier_style=atelier_style,
                    advanced_style=self._advanced_style_from_page(page),
                    detail_column_alignments=dict(
                        getattr(page, "detail_column_alignments", {}) or {}
                    ),
                    page_chrome={
                "show_title": bool(page.page_show_title_widget.isChecked()),
                "title_text": page.page_title_text_widget.text().strip(),
                "title_font_size": int(page.page_title_size_widget.value()),
                "title_font_family": str(getattr(page, "summary_title_font_family", "Calibri") or "Calibri"),
                "title_bold": bool(page.page_title_bold_widget.isChecked()),
                "title_italic": bool(page.page_title_italic_widget.isChecked()),
                "title_underline": bool(page.page_title_underline_widget.isChecked()),
                "title_align": str(page.page_title_align_widget.currentData() or "left"),
                "title_text_color": str(page.page_title_text_color_widget.property("mm3Color") or "#111111"),
                "title_bg_color": str(page.page_title_bg_color_widget.property("mm3Color") or "#FFFFFF"),
                "show_collection": bool(page.page_show_collection_widget.isChecked()),
                "show_print_date": bool(page.page_show_print_date_widget.isChecked()),
                "show_page_numbers": bool(page.page_show_page_numbers_widget.isChecked()),
                "print_font_family": str(page.page_print_font_widget.currentData() or page.page_print_font_widget.currentText() or "Arial"),
                "body_font_size": int(page.page_body_size_widget.value()),
                "footer_text": page.page_footer_text_widget.text().strip(),
                "footer_font_size": int(page.page_footer_size_widget.value()),
                "footer_bold": bool(page.page_footer_bold_widget.isChecked()),
                "footer_italic": bool(page.page_footer_italic_widget.isChecked()),
                "footer_underline": bool(page.page_footer_underline_widget.isChecked()),
                "footer_align": str(page.page_footer_align_widget.currentData() or "right"),
                "footer_text_color": str(page.page_footer_text_color_widget.property("mm3Color") or "#4F5A55"),
                "footer_bg_color": str(page.page_footer_bg_color_widget.property("mm3Color") or "#FFFFFF"),
            },
                )
            else:
                dlg = DetailPreviewDialog(
                    self, report_title, records, fields, landscape.isChecked(), self,
                    source_name=source.currentData(),
                    saved_name=editing_name, layout_state=saved_layout,
                    advanced_style=self._advanced_style_from_page(page),
                    detail_column_alignments=dict(
                        getattr(page, "detail_column_alignments", {}) or {}
                    ),
                    page_chrome={
                "show_title": bool(page.page_show_title_widget.isChecked()),
                "title_text": page.page_title_text_widget.text().strip(),
                "title_font_size": int(page.page_title_size_widget.value()),
                "title_font_family": str(getattr(page, "summary_title_font_family", "Calibri") or "Calibri"),
                "title_bold": bool(page.page_title_bold_widget.isChecked()),
                "title_italic": bool(page.page_title_italic_widget.isChecked()),
                "title_underline": bool(page.page_title_underline_widget.isChecked()),
                "title_align": str(page.page_title_align_widget.currentData() or "left"),
                "title_text_color": str(page.page_title_text_color_widget.property("mm3Color") or "#111111"),
                "title_bg_color": str(page.page_title_bg_color_widget.property("mm3Color") or "#FFFFFF"),
                "show_collection": bool(page.page_show_collection_widget.isChecked()),
                "show_print_date": bool(page.page_show_print_date_widget.isChecked()),
                "show_page_numbers": bool(page.page_show_page_numbers_widget.isChecked()),
                "print_font_family": str(page.page_print_font_widget.currentData() or page.page_print_font_widget.currentText() or "Arial"),
                "body_font_size": int(page.page_body_size_widget.value()),
                "footer_text": page.page_footer_text_widget.text().strip(),
                "footer_font_size": int(page.page_footer_size_widget.value()),
                "footer_bold": bool(page.page_footer_bold_widget.isChecked()),
                "footer_italic": bool(page.page_footer_italic_widget.isChecked()),
                "footer_underline": bool(page.page_footer_underline_widget.isChecked()),
                "footer_align": str(page.page_footer_align_widget.currentData() or "right"),
                "footer_text_color": str(page.page_footer_text_color_widget.property("mm3Color") or "#4F5A55"),
                "footer_bg_color": str(page.page_footer_bg_color_widget.property("mm3Color") or "#FFFFFF"),
            },
                )
            dlg.builder_page = page
            if print_preview:
                dlg._print()
            else:
                self._detail_preview = dlg
                dlg.setModal(False)
                dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
                dlg.destroyed.connect(lambda *_: setattr(self, "_detail_preview", None))
                dlg.show(); dlg.raise_(); dlg.activateWindow()
            self._mark_preview_done(page)
            return

        group_field = str(page.group_widget.currentData() or "origin")
        if group_field == "__acquisition_year__":
            group_field = "acquisition_date"
            page.date_group_mode_widget.setCurrentIndex(
                page.date_group_mode_widget.findData("year")
            )
        editing_name = getattr(page, "editing_report_name", None)
        saved_layout = (
            self.saved_reports.get(editing_name, {}).get("layout", {})
            if editing_name else {}
        )
        dlg = SummaryPreviewDialog(
            self, report_title, records, group_field, landscape.isChecked(), self,
            source_name=source.currentData(), saved_name=editing_name, layout_state=saved_layout,
            date_group_mode=str(page.date_group_mode_widget.currentData() or "full_date"),
            second_group_field=page.second_group_widget.currentData(),
            show_details=bool(page.details_widget.isChecked()),
            field_color=str(
                page.advanced_typography_widgets["summary_master"]["text_color"].property("mm3Color")
                or "#9A3324"
            ),
            field_bold=bool(page.advanced_typography_widgets["summary_master"]["bold"].isChecked()),
            advanced_style=self._advanced_style_from_page(page),
            # Respecter l'ordre visible du constructeur (maître, puis champs liés).
            # La palette est alphabétique et ne définit pas l'ordre des colonnes.
            summary_fields=([str(page.summary_graphic_master)] if getattr(page, "summary_graphic_master", None) else [])
                + [str(f) for f in getattr(page, "summary_graphic_secondaries", [])[:4]
                   if f and str(f) != str(getattr(page, "summary_graphic_master", ""))],
            summary_treatments=dict(getattr(page, "summary_treatments", {}) or {}),
            page_chrome={
                "show_title": bool(page.page_show_title_widget.isChecked()),
                "title_text": page.page_title_text_widget.text().strip(),
                "title_font_size": int(page.page_title_size_widget.value()),
                "title_font_family": str(getattr(page, "summary_title_font_family", "Calibri") or "Calibri"),
                "title_bold": bool(page.page_title_bold_widget.isChecked()),
                "title_italic": bool(page.page_title_italic_widget.isChecked()),
                "title_underline": bool(page.page_title_underline_widget.isChecked()),
                "title_align": str(page.page_title_align_widget.currentData() or "left"),
                "title_text_color": str(page.page_title_text_color_widget.property("mm3Color") or "#111111"),
                "title_bg_color": str(page.page_title_bg_color_widget.property("mm3Color") or "#FFFFFF"),
                "show_collection": bool(page.page_show_collection_widget.isChecked()),
                "show_print_date": bool(page.page_show_print_date_widget.isChecked()),
                "show_page_numbers": bool(page.page_show_page_numbers_widget.isChecked()),
                "print_font_family": str(page.page_print_font_widget.currentData() or page.page_print_font_widget.currentText() or "Arial"),
                "body_font_size": int(page.page_body_size_widget.value()),
                "footer_text": page.page_footer_text_widget.text().strip(),
                "footer_font_size": int(page.page_footer_size_widget.value()),
                "footer_bold": bool(page.page_footer_bold_widget.isChecked()),
                "footer_italic": bool(page.page_footer_italic_widget.isChecked()),
                "footer_underline": bool(page.page_footer_underline_widget.isChecked()),
                "footer_align": str(page.page_footer_align_widget.currentData() or "right"),
                "footer_text_color": str(page.page_footer_text_color_widget.property("mm3Color") or "#4F5A55"),
                "footer_bg_color": str(page.page_footer_bg_color_widget.property("mm3Color") or "#FFFFFF"),
            },
            summary_column_alignments=dict(
                getattr(page, "summary_column_alignments", {}) or {}
            ),
            summary_field_styles=dict(getattr(page, "summary_field_styles", {}) or {}),
            summary_header_metrics={
                "groups": bool(page.summary_show_groups_metric_widget.isChecked()),
                "groups_explicit": True,
                "selected": bool(page.summary_show_selected_metrics_widget.isChecked()),
                "selected_fields": self._ordered_summary_totals(page),
                "footer_order": list(getattr(page, "summary_footer_order", []) or []),
                "selected_labels": dict(getattr(page, "summary_metric_labels", {}) or {}),
                "metric_widths": dict(getattr(page, "summary_metric_widths", {}) or {}),
                "metric_positions": dict(getattr(page, "summary_metric_positions", {}) or {}),
                "metric_styles": dict(getattr(page, "summary_metric_styles", {}) or {}),
                "band_style": dict(getattr(page, "summary_band_style", {}) or {}),
                "column_header_labels": dict(getattr(page, "summary_column_header_labels", {}) or {}),
                "column_header_styles": dict(getattr(page, "summary_column_header_styles", {}) or {}),
                "column_header_hidden": sorted(getattr(page, "summary_column_header_hidden", set()) or set()),
                "column_widths": dict(getattr(page, "summary_column_widths", {}) or {}),
                "row_vertical_align": str(getattr(page, "summary_vertical_align", "center")),
                "footer_linked": bool(getattr(page, "summary_footer_linked", False)),
                "footer_fields": (
                    [w.metric_field for w in getattr(page, "summary_footer_sample").findChildren(SummaryMetricLabel)
                     if getattr(w, "metric_field", None)]
                    if (getattr(page, "summary_footer_sample", None) is not None
                        and not bool(getattr(page, "summary_footer_linked", False)))
                    else list(getattr(page, "summary_footer_metric_fields", set()) or set())
                ),
                "footer_style": dict(getattr(page, "summary_footer_style", {}) or {}),
                "footer_metric_styles": dict(getattr(page, "summary_footer_metric_styles", {}) or {}),
                "footer_metric_labels": dict(getattr(page, "summary_footer_metric_labels", {}) or {}),
                "footer_metric_spacing": dict(getattr(page, "summary_footer_metric_spacing", {}) or {}),
                "footer_metric_widths": dict(getattr(page, "summary_footer_metric_widths", {}) or {}),
                "footer_metric_positions": dict(getattr(page, "summary_footer_metric_positions", {}) or {}),
                # 27.134 — transmettre aussi la numérotation au dialogue d’aperçu/impression.
                # La sauvegarde du modèle possédait déjà ces valeurs, mais le chemin direct
                # Constructeur -> Aperçu/Imprimer les omettait : le moteur d’impression
                # recevait donc systématiquement page_numbers_enabled=False.
                "page_numbers_enabled": bool(getattr(page, "summary_page_numbers_enabled", False)),
                "page_number_format": str(getattr(page, "summary_page_number_format", "page_x_y") or "page_x_y"),
                "page_number_align": str(getattr(page, "summary_page_number_align", "right") or "right"),
                "species": False,  # ancien compteur supprimé ; les totaux passent par Champ | Total
                "records": bool(page.summary_show_records_metric_widget.isChecked()),
                "groups_label": page.summary_groups_label_widget.text().strip(),
                "distinct_field": page.summary_distinct_field_widget.currentData(),
                "distinct_label": page.summary_distinct_label_widget.text().strip(),

                "groups_font": page.summary_groups_font_widget.currentFont().family(),
                "selected_font": page.summary_selected_font_widget.currentFont().family(),
                "species_font": page.summary_species_font_widget.currentFont().family(),
                "records_font": page.summary_records_font_widget.currentFont().family(),

                "groups_size": int(page.summary_groups_size_widget.value()),
                "selected_size": int(page.summary_selected_size_widget.value()),
                "species_size": int(page.summary_species_size_widget.value()),
                "records_size": int(page.summary_records_size_widget.value()),

                "groups_text": str(page.summary_groups_text_widget.property("mm3Color") or "#8B3026"),
                "selected_text": str(page.summary_selected_text_widget.property("mm3Color") or "#8B3026"),
                "species_text": str(page.summary_species_text_widget.property("mm3Color") or "#8B3026"),
                "records_text": str(page.summary_records_text_widget.property("mm3Color") or "#7A817D"),

                "groups_bg": str(page.summary_groups_bg_widget.property("mm3Color") or "#F4F6F5"),
                "selected_bg": str(page.summary_selected_bg_widget.property("mm3Color") or "#F4F6F5"),
                "species_bg": str(page.summary_species_bg_widget.property("mm3Color") or "#F4F6F5"),
                "records_bg": str(page.summary_records_bg_widget.property("mm3Color") or "#F4F6F5"),
            },
        )
        dlg.builder_page = page
        if print_preview:
            dlg._print()
        else:
            dlg.exec()
        self._mark_preview_done(page)


    def _detail_html(self, title: str, records: list[dict], fields: list[str]) -> str:
        headers = "".join(f"<th>{_escape(self.labels.get(f, f))}</th>" for f in fields)
        rows = []
        for record in records:
            cells = "".join(f"<td>{_escape(record.get(f, ''))}</td>" for f in fields)
            rows.append(f"<tr>{cells}</tr>")
        boxes = sum(_number(r.get("box_count")) for r in records)
        boxes_text = str(int(boxes) if boxes.is_integer() else boxes).replace(".", ",")
        subtitle = (
            f"<b>{boxes_text} boîtes</b> "
            f"<span style='color:#888'>— {len(records)} fiche(s)</span>"
        )
        return self._html_shell(
            title, subtitle,
            f"<table><thead><tr>{headers}</tr></thead><tbody>{''.join(rows)}</tbody></table>",
            subtitle_is_html=True,
        )


    @staticmethod
    def _fmt_number(value) -> str:
        number = float(value or 0)
        return str(int(number) if number.is_integer() else number).replace(".", ",")

    @staticmethod
    def _distinct_count(records: list[dict], field: str) -> int:
        if not field: return 0
        return len({str(r.get(field, "") or "").strip().casefold() for r in records if str(r.get(field, "") or "").strip()})

    @staticmethod
    def _record_count(records: list[dict]) -> int:
        """Compte les fiches MM3. Une ligne chargée = une fiche.

        Ne jamais déduire ce compteur d'un champ métier (N° de pièce, nombre de
        boîtes, etc.) : ces valeurs peuvent être répétées ou supérieures à 1.
        """
        return len(records)

    def _species_count(self, records: list[dict]) -> int:
        """Compatibilité historique : compte distinctement le champ affiché « Nom »."""
        name_field = next((field for label, field in self.fields if str(label).strip().casefold() == "nom"), None)
        if not name_field and "mineral_name" in self.labels:
            name_field = "mineral_name"
        return self._distinct_count(records, name_field) if name_field else 0

    def _field_type(self, field) -> str:
        field = str(field or "")
        custom = self._custom_field_defs.get(field)
        if custom is not None:
            return str(custom.get("field_type") or "").strip().casefold()
        spec = FIELD_BY_KEY.get(field)
        return str(getattr(spec, "field_type", "") or "").strip().casefold() if spec is not None else ""

    def _is_numeric_field(self, field) -> bool:
        ftype = self._field_type(field)
        return ftype in {"nombre", "number", "numérique", "numeric", "monétaire", "monetaire", "currency", "calculé", "calcule", "calculated"} or str(field) in {"box_count", "number_of_boxes", "nb_boxes", "boxes", "price", "unit_price", "total_cost", "cost_total"}

    @staticmethod
    def _safe_summary_calc(expression: str):
        tree = ast.parse(expression, mode="eval")
        ops = {ast.Add: lambda a,b:a+b, ast.Sub: lambda a,b:a-b, ast.Mult: lambda a,b:a*b, ast.Div: lambda a,b:a/b}
        def ev(n):
            if isinstance(n, ast.Expression): return ev(n.body)
            if isinstance(n, ast.Constant) and isinstance(n.value, (int,float,str)): return n.value
            if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.UAdd, ast.USub)):
                v=ev(n.operand); return v if isinstance(n.op, ast.UAdd) else -v
            if isinstance(n, ast.BinOp) and type(n.op) in ops: return ops[type(n.op)](ev(n.left), ev(n.right))
            raise ValueError("Formule non autorisée")
        return ev(tree)

    def _summary_numeric_value(self, record: dict, field: str) -> float:
        """Valeur numérique d'un champ d'état, y compris un champ calculé non stocké."""
        field = str(field or "")
        definition = self._custom_field_defs.get(field)
        # Champ système Coût total : dans les collections historiques il n'est
        # pas toujours stocké dans records. Le recalcul de référence est
        # Prix unitaire × Nombre de pièces/boîtes.
        if field in {"total_cost", "cost_total"}:
            raw = record.get(field)
            if raw not in (None, ""):
                return _number(raw)
            price = record.get("price", record.get("unit_price", 0))
            qty = record.get("box_count", record.get("number_of_pieces", record.get("number_of_boxes", 0)))
            return _number(price) * _number(qty)
        if definition is not None and str(definition.get("field_type") or "").strip().casefold() in {"calculated", "calculé", "calcule"}:
            formula = str(definition.get("calculation_formula") or "")
            def source(match):
                key = str(match.group(1) or "").strip()
                return repr(_number(record.get(key)))
            try:
                return float(self._safe_summary_calc(normalize_calculation_formula(re.sub(r"\{([^{}]+)\}", source, formula))))
            except Exception:
                return 0.0
        return _number(record.get(field))

    def _summary_total_text(self, field: str, value: float) -> str:
        """Formate un total en conservant la devise/suffixe configuré du champ.

        Les champs monétaires gardent toujours deux décimales dans les États.
        """
        try:
            styles = self.model_manager.field_styles(int(self.collection["id"]))
            style = dict((styles or {}).get(str(field), {}) or {})
        except Exception:
            style = {}
        definition = self._custom_field_defs.get(str(field)) or {}
        is_calculated = str(definition.get("field_type") or "").casefold() == "calculated"
        suffix = str(style.get("result_suffix") or "").strip() if is_calculated else ""
        native_currency = (
            self._field_type(field) in {"currency", "monétaire", "monetaire"}
            or str(field) in {"price", "unit_price", "total_cost", "cost_total"}
        )
        if not suffix and native_currency:
            suffix = str(style.get("currency_symbol") or "€").strip()
        currency_suffix = suffix in {"€", "$", "£", "¥", "₹", "₩", "₽", "CHF"}
        if native_currency or currency_suffix:
            text = f"{float(value or 0):.2f}".replace(".", ",")
        else:
            text = self._fmt_number(value)
        return f"{text} {suffix}".strip()

    def _summary_treatment(self, field, explicit=None) -> str:
        """Traitement par défaut cohérent : somme pour un nombre, distinct pour le reste."""
        # Les anciens modèles pouvaient mémoriser « list » / « count_distinct »
        # pour un champ numérique, à l'époque où le bloc Traitement existait.
        # Depuis la simplification Col./Total, un numérique se totalise par somme.
        if self._is_numeric_field(field):
            return explicit if explicit in {"sum", "avg", "min", "max"} else "sum"
        if explicit in {"count_distinct", "list"}:
            return explicit
        return "count_distinct"

    def _is_date_field(self, field) -> bool:
        """Vrai pour tout champ MM3 réellement typé Date, natif ou personnalisé."""
        field = str(field or "")
        if not field:
            return False
        custom = self._custom_field_defs.get(field)
        if custom is not None:
            return str(custom.get("field_type") or "").strip().casefold() == "date"
        spec = FIELD_BY_KEY.get(field)
        return bool(spec is not None and str(getattr(spec, "field_type", "")).casefold() == "date")

    @staticmethod
    def _date_parts(value: str):
        text = str(value or "").strip()
        if not text:
            return None
        for fmt in ("dd/MM/yyyy", "d/M/yyyy", "yyyy-MM-dd", "yyyy/MM/dd"):
            parsed = QDate.fromString(text, fmt)
            if parsed.isValid():
                return parsed.year(), parsed.month(), parsed.day()
        match = re.search(r"(?<!\d)(\d{1,2})[./-](\d{1,2})[./-](\d{4})(?!\d)", text)
        if match:
            day, month, year = map(int, match.groups())
            parsed = QDate(year, month, day)
            if parsed.isValid():
                return year, month, day
        return None

    def _group_value(self, record: dict, field: str, date_mode: str = "full_date") -> str:
        raw = str(record.get(field, "") or "").strip()
        if self._is_date_field(field) and date_mode != "full_date":
            parts = self._date_parts(raw)
            if not parts:
                return "(vide)" if not raw else raw
            year, month, _day = parts
            month_names = (
                "", "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
                "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre",
            )
            if date_mode == "year":
                return str(year)
            if date_mode == "month":
                return month_names[month]
            if date_mode == "year_month":
                return f"{year:04d} - {month_names[month]}"
        return raw or "(vide)"

    def _group_records(self, records: list[dict], field: str, date_mode: str = "full_date"):
        groups = defaultdict(list)
        for record in records:
            groups[self._group_value(record, field, date_mode)].append(record)
        return groups

    def _sorted_group_keys(self, keys: list[str], field: str, date_mode: str = "full_date") -> list[str]:
        if self._is_date_field(field) and date_mode in {"year", "year_month"}:
            def date_key(value):
                text = str(value)
                match = re.match(r"^(\d{4})(?:\s*-\s*)?", text)
                return (0, int(match.group(1)), text.casefold()) if match else (1, 0, text.casefold())
            return sorted(keys, key=date_key)
        if self._is_date_field(field) and date_mode == "month":
            order = {name.casefold(): i for i, name in enumerate((
                "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
                "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"
            ), 1)}
            return sorted(keys, key=lambda value: (order.get(str(value).casefold(), 99), str(value).casefold()))
        return sorted(keys, key=lambda value: str(value).casefold())

    def _plural_group_label(self, field: str, count: int, date_mode: str = "full_date") -> str:
        if self._is_date_field(field) and date_mode == "year":
            return "année" if count == 1 else "années"
        if self._is_date_field(field) and date_mode == "month":
            return "mois"
        if self._is_date_field(field) and date_mode == "year_month":
            return "période" if count == 1 else "périodes"
        label = self.labels.get(field, field).lower()
        if count != 1 and not label.endswith("s"):
            label += "s"
        return label

    def _grouped_details_html(
        self,
        records: list[dict],
        group_field: str,
        date_mode: str,
        second_group_field,
        show_details: bool,
    ) -> str:
        primary = self._group_records(records, group_field, date_mode)
        parts = []

        for primary_key in self._sorted_group_keys(
            list(primary), group_field, date_mode
        ):
            entries = primary[primary_key]
            boxes = sum(_number(record.get("box_count")) for record in entries)
            species = self._species_count(entries)
            parts.append(
                f"<div style='margin-top:24px;margin-bottom:10px;padding:9px 12px;"
                f"background:#DDE8E2;font-size:15px;font-weight:bold;border-top:2px solid #9EAAA4'>"
                f"{_escape(primary_key)} — {self._fmt_number(boxes)} boîtes — {species} espèces "
                f"</div>"
            )

            groups = {None: entries}
            if second_group_field:
                nested = defaultdict(list)
                for record in entries:
                    nested[self._group_value(record, second_group_field)].append(record)
                groups = dict(nested)

            for second_key in sorted(
                groups,
                key=lambda value: "" if value is None else str(value).casefold()
            ):
                subset = groups[second_key]

                if second_key is not None:
                    sub_boxes = sum(_number(record.get("box_count")) for record in subset)
                    sub_species = self._species_count(subset)
                    parts.append(
                        f"<div style='margin:8px 0 6px 20px;padding:6px 10px;background:#EEF3F0;font-weight:bold'>"
                        f"{_escape(second_key)} — {self._fmt_number(sub_boxes)} boîtes — {sub_species} espèces "
                        f"</div>"
                    )

                if show_details:
                    parts.append(
                        "<table><thead><tr>"
                        "<th>N°</th><th>Nom</th><th>Site</th><th>Pays</th>"
                        "<th>Contact</th><th>Date</th>"
                        "</tr></thead><tbody>"
                    )
                    for record in subset:
                        parts.append(
                            "<tr>"
                            f"<td>{_escape(record.get('record_number', ''))}</td>"
                            f"<td>{_escape(record.get('mineral_name', ''))}</td>"
                            f"<td>{_escape(record.get('site_name', ''))}</td>"
                            f"<td>{_escape(record.get('country', ''))}</td>"
                            f"<td>{_escape(record.get('contact', ''))}</td>"
                            f"<td>{_escape(record.get('acquisition_date', ''))}</td>"
                            "</tr>"
                        )
                    parts.append("</tbody></table>")

        return self._html_shell("Détail groupé", "", "".join(parts))

    def _default_atelier_style(self) -> dict:
        return {
            "level1_text":"#9A3324","level2_text":"#111111","level3_text":"#737B77",
            "level1_bg":"#C8D8D0","level2_bg":"#DDE8E2","level3_bg":"#EEF3F0",
            "repeat_master_field":None,"repeat_master_color":"#9A3324",
            "repeat_master_italic":True,"primary_spacing_lines":2,"spacing_height":22,
            "show_groups":True,"show_boxes":True,"show_species":True,"show_records":True,
            "metric_groups_font":"Calibri","metric_boxes_font":"Calibri",
            "metric_species_font":"Calibri","metric_records_font":"Calibri",
            "metric_groups_size":11,"metric_boxes_size":11,
            "metric_species_size":11,"metric_records_size":10,
            "metric_groups_bold":False,"metric_boxes_bold":False,
            "metric_species_bold":False,"metric_records_bold":False,
            "metric_groups_italic":False,"metric_boxes_italic":False,
            "metric_species_italic":False,"metric_records_italic":False,
            "metric_groups_underline":False,"metric_boxes_underline":False,
            "metric_species_underline":False,"metric_records_underline":False,
            "metric_groups_color":"#8B3026","metric_boxes_color":"#8B3026",
            "metric_species_color":"#8B3026","metric_records_color":"#7A817D",
            "metric_groups_bg":"#F4F6F5","metric_boxes_bg":"#F4F6F5",
            "metric_species_bg":"#F4F6F5","metric_records_bg":"#F4F6F5",
        }

    def _default_atelier_style(self) -> dict:
        return {"level1_text":"#9A3324","level2_text":"#111111","level3_text":"#737B77","level1_bg":"#C8D8D0","level2_bg":"#DDE8E2","level3_bg":"#EEF3F0","repeat_master_field":None,"repeat_master_color":"#9A3324","repeat_master_italic":True,"primary_spacing_lines":2,"spacing_height":22,"show_groups":True,"show_boxes":True,"show_species":True,"show_records":True,"metric_groups_size":11,"metric_boxes_size":11,"metric_species_size":11,"metric_records_size":10,"metric_groups_color":"#8B3026","metric_boxes_color":"#8B3026","metric_species_color":"#8B3026","metric_records_color":"#7A817D"}

    def _atelier_style_from_page(self, page) -> dict:
        style=self._default_atelier_style()
        style.update({
            "level1_text":str(page.atelier_level1_color.property("mm3Color")),
            "level2_text":str(page.atelier_level2_color.property("mm3Color")),
            "level3_text":str(page.atelier_level3_color.property("mm3Color")),
            "level1_bg":str(page.atelier_level1_bg.property("mm3Color")),
            "level2_bg":str(page.atelier_level2_bg.property("mm3Color")),
            "level3_bg":str(page.atelier_level3_bg.property("mm3Color")),
            "repeat_master_field":page.atelier_repeat_master_widget.currentData(),
            "repeat_master_color":str(page.atelier_repeat_color.property("mm3Color")),
            "primary_spacing_lines":int(page.atelier_spacing_widget.value()),
            "show_groups":bool(page.atelier_show_groups.isChecked()),
            "show_boxes":bool(page.atelier_show_boxes.isChecked()),
            "show_species":bool(page.atelier_show_species.isChecked()),
            "show_records":bool(page.atelier_show_records.isChecked()),
        })
        for semantic in ("groups","boxes","species","records"):
            style[f"metric_{semantic}_font"]=getattr(page,f"atelier_metric_{semantic}_font").currentFont().family()
            style[f"metric_{semantic}_size"]=int(getattr(page,f"atelier_metric_{semantic}_size").value())
            style[f"metric_{semantic}_bold"]=bool(getattr(page,f"atelier_metric_{semantic}_bold").isChecked())
            style[f"metric_{semantic}_italic"]=bool(getattr(page,f"atelier_metric_{semantic}_italic").isChecked())
            style[f"metric_{semantic}_underline"]=bool(getattr(page,f"atelier_metric_{semantic}_underline").isChecked())
            style[f"metric_{semantic}_color"]=str(getattr(page,f"atelier_metric_{semantic}_color").property("mm3Color"))
            style[f"metric_{semantic}_bg"]=str(getattr(page,f"atelier_metric_{semantic}_bg").property("mm3Color"))
        return style

    def _apply_atelier_style_to_page(self, page, style):
        style={**self._default_atelier_style(), **dict(style or {})}
        self._set_combo_by_data(page.atelier_repeat_master_widget,style.get("repeat_master_field"))
        for button,key in (
            (page.atelier_level1_color,"level1_text"),(page.atelier_level2_color,"level2_text"),
            (page.atelier_level3_color,"level3_text"),(page.atelier_level1_bg,"level1_bg"),
            (page.atelier_level2_bg,"level2_bg"),(page.atelier_level3_bg,"level3_bg"),
            (page.atelier_repeat_color,"repeat_master_color"),
        ):
            color=str(style.get(key)); button.setProperty("mm3Color",color)
            fg="#F4F4F4" if QColor(color).lightness()<120 else "#111111"
            button.setStyleSheet("QPushButton {"+f" background-color:{color}; color:{fg}; min-width:105px; font-weight:600;"+"}")
        page.atelier_spacing_widget.setValue(int(style.get("primary_spacing_lines",2)))
        page.atelier_show_groups.setChecked(bool(style.get("show_groups",True)))
        page.atelier_show_boxes.setChecked(bool(style.get("show_boxes",True)))
        page.atelier_show_species.setChecked(bool(style.get("show_species",True)))
        page.atelier_show_records.setChecked(bool(style.get("show_records",True)))
        for semantic,default_size,default_color in (
            ("groups",11,"#8B3026"),("boxes",11,"#8B3026"),
            ("species",11,"#8B3026"),("records",10,"#7A817D"),
        ):
            getattr(page,f"atelier_metric_{semantic}_font").setCurrentFont(
                QFont(str(style.get(f"metric_{semantic}_font") or "Calibri"))
            )
            getattr(page,f"atelier_metric_{semantic}_size").setValue(
                int(style.get(f"metric_{semantic}_size",default_size))
            )
            getattr(page,f"atelier_metric_{semantic}_bold").setChecked(
                bool(style.get(f"metric_{semantic}_bold",False))
            )
            getattr(page,f"atelier_metric_{semantic}_italic").setChecked(
                bool(style.get(f"metric_{semantic}_italic",False))
            )
            getattr(page,f"atelier_metric_{semantic}_underline").setChecked(
                bool(style.get(f"metric_{semantic}_underline",False))
            )
            for suffix,default in (("color",default_color),("bg","#F4F6F5")):
                button=getattr(page,f"atelier_metric_{semantic}_{suffix}")
                color=str(style.get(f"metric_{semantic}_{suffix}") or default)
                button.setProperty("mm3Color",color)
                fg="#F4F4F4" if QColor(color).lightness()<120 else "#111111"
                button.setStyleSheet("QPushButton {"+f" background-color:{color}; color:{fg}; min-width:48px; max-width:60px; padding:2px 4px; font-weight:600;"+"}")
        self._refresh_atelier_sample(page)

    def _refresh_atelier_sample(self, page):
        if not hasattr(page, "atelier_sample"):
            return

        style = self._atelier_style_from_page(page)
        adv = self._advanced_style_from_page(page) if hasattr(page, "advanced_typography_widgets") else {}
        typography = dict(adv.get("typography") or {})
        colors = [style["level1_text"], style["level2_text"], style["level3_text"]]
        bgs = [style["level1_bg"], style["level2_bg"], style["level3_bg"]]
        examples = {
            "__acquisition_year__":"2024", "contact":"FX",
            "site_name":"Côte Rousse Quarry", "country":"France",
            "quality":"Très bien", "color":"Vert", "shape":"Cristaux",
            "origin":"Achat"
        }

        active = [c.currentData() for c in getattr(page, "detail_grouping_widgets", []) if c.currentData()]
        parts = []
        def metric_preview(text,semantic):
            family=str(style.get(f"metric_{semantic}_font") or "Calibri")
            size=int(style.get(f"metric_{semantic}_size",10))
            weight="700" if bool(style.get(f"metric_{semantic}_bold",False)) else "400"
            italic="italic" if bool(style.get(f"metric_{semantic}_italic",False)) else "normal"
            underline="underline" if bool(style.get(f"metric_{semantic}_underline",False)) else "none"
            color=str(style.get(f"metric_{semantic}_color") or "#8B3026")
            bg=str(style.get(f"metric_{semantic}_bg") or "#F4F6F5")
            return (
                f"<span style='font-family:{_escape(family)};font-size:{size}pt;"
                f"font-weight:{weight};font-style:{italic};text-decoration:{underline};"
                f"color:{color};background:{bg};padding:1px 3px;'>"
                f"<font face='{_escape(family)}'>{_escape(text)}</font></span>"
            )
        metric_parts=[]
        if style.get("show_groups",True): metric_parts.append(metric_preview("8 contacts","groups"))
        if style.get("show_boxes",True): metric_parts.append(metric_preview("46 boîtes","boxes"))
        if style.get("show_species",True): metric_parts.append(metric_preview("23 espèces","species"))
        if style.get("show_records",False): metric_parts.append(metric_preview("35 fiche(s)","records"))
        if metric_parts:
            parts.append("<div style='padding:3px 2px;margin-bottom:3px'>"+"&nbsp;&nbsp;&nbsp;&nbsp;".join(metric_parts)+"</div>")
        # En-tête de colonnes, afin de visualiser aussi sa typographie.
        h_family = str(adv.get("column_header_font_family") or "Calibri")
        h_size = int(adv.get("column_header_font_size", 10))
        h_weight = "700" if bool(adv.get("column_header_bold", True)) else "400"
        h_italic = "font-style:italic;" if bool(adv.get("column_header_italic", False)) else ""
        h_under = "text-decoration:underline;" if bool(adv.get("column_header_underline", False)) else ""
        h_color = str(adv.get("column_header_text_color") or "#111111")
        h_bg = str(adv.get("column_header_bg_color") or "#DDE8E2")
        parts.append(
            f"<div style='font-family:{_escape(h_family)};font-size:{h_size}pt;"
            f"font-weight:{h_weight};{h_italic}{h_under}color:{h_color};"
            f"background:{h_bg};padding:3px 5px;'>"
            "N°&nbsp;&nbsp;&nbsp; Nom&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; Site"
            "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; Pays&nbsp;&nbsp;&nbsp; Qualité</div>"
        )
        if not active:
            parts.append("<div style='background:#F4F6F5;padding:3px;color:#6F7773'>Choisissez un regroupement.</div>")

        for level, field in enumerate(active[:3]):
            key = f"level{level+1}"
            typo = dict(typography.get(key) or {})
            label = self._grouping_label(field)
            value = examples.get(field, self.labels.get(field, label))
            color = str(typo.get("text_color", colors[level]))
            background = str(typo.get("bg_color", bgs[level]))
            family = str(typo.get("font_family") or "Calibri")
            fs = int(typo.get("font_size", 11 if level == 0 else 10))
            weight = "700" if typo.get("bold", True) else "400"
            italic = "font-style:italic;" if typo.get("italic", False) else ""
            underline = "text-decoration:underline;" if typo.get("underline", False) else ""
            align = str(typo.get("align", "left"))
            border = "border-bottom:1px solid #7f8b87;" if level == 0 and adv.get("separator", True) else ""

            totals = ""
            if style.get("show_boxes", True):
                totals += f" — <span style='color:{color};font-weight:700'>9</span> <span style='color:{color};font-weight:400'>boîtes</span>"
            if style.get("show_species", True):
                totals += f" — <span style='color:{color};font-weight:700'>7</span> <span style='color:{color};font-weight:400'>espèces</span>"
            if style.get("show_records", True):
                totals += f" — <span style='color:{color};font-weight:700'>9</span> <span style='color:{color};font-weight:400'>fiche(s)</span>"

            prefix = ""
            parts.append(
                f"<div style='background:{background};padding:3px;margin-left:{10*level}px;"
                f"text-align:{align};font-family:{_escape(family)};font-size:{fs}pt;"
                f"font-weight:{weight};{italic}{underline}{border}'>"
                f"{prefix}<span style='color:{color};font-weight:400'>{_escape(label)} :</span> "
                f"<span style='color:{color};font-weight:700'>{_escape(value)}</span>{totals}</div>"
            )

        repeat = style.get("repeat_master_field")

        repeat_typo = dict(typography.get("repeat") or {})
        repeat_color = str(
            repeat_typo.get(
                "text_color",
                style.get("repeat_master_color", "#9A3324"),
            )
        )
        repeat_bg = str(repeat_typo.get("bg_color") or "#FFFFFF")
        repeat_family = str(repeat_typo.get("font_family") or "Calibri")
        repeat_size = int(repeat_typo.get("font_size", 10))
        repeat_weight = (
            "700" if bool(repeat_typo.get("bold", False)) else "400"
        )
        repeat_italic = (
            "font-style:italic;"
            if bool(repeat_typo.get("italic", True))
            else ""
        )
        repeat_underline = (
            "text-decoration:underline;"
            if bool(repeat_typo.get("underline", False))
            else ""
        )
        repeat_align = str(repeat_typo.get("align") or "left")

        detail_typo = dict(typography.get("detail") or {})
        detail_family = str(detail_typo.get("font_family") or "Calibri")
        detail_size = int(detail_typo.get("font_size", 10))
        detail_weight = (
            "700" if bool(detail_typo.get("bold", False)) else "400"
        )
        detail_italic = (
            "font-style:italic;"
            if bool(detail_typo.get("italic", False))
            else ""
        )
        detail_underline = (
            "text-decoration:underline;"
            if bool(detail_typo.get("underline", False))
            else ""
        )
        detail_align = str(detail_typo.get("align") or "left")
        detail_color = str(detail_typo.get("text_color") or "#111111")
        detail_bg = str(detail_typo.get("bg_color") or "#FFFFFF")

        repeat_label = (
            self.labels.get(repeat, repeat)
            if repeat
            else "Champ répété"
        )

        # Une vraie ligne d'en-tête visuelle pour ces deux éléments.
        parts.append(
            "<div style='padding:2px 3px;background:#F4F6F5;"
            "border-top:1px solid #AAB5B0;'>"
            "<b>Champ répété</b>&nbsp;&nbsp; | &nbsp;&nbsp;"
            "<b>Détail de la fiche</b></div>"
        )

        for repeated_value, detail_value in (
            (f"{repeat_label} : ZIRCON", "4  Bou Skour Mine  Maroc"),
            (f"{repeat_label} : ARGENT", "5  Châteauguay  France"),
            (f"{repeat_label} : PHILLIPSITE", "6  Les Vieux Travaux mine  France"),
        ):
            parts.append(
                f"<div style='padding:2px 3px;background:{detail_bg};'>"
                f"<span style='display:inline-block;min-width:38%;"
                f"text-align:{repeat_align};font-family:{_escape(repeat_family)};"
                f"font-size:{repeat_size}pt;font-weight:{repeat_weight};"
                f"{repeat_italic}{repeat_underline};color:{repeat_color};"
                f"background:{repeat_bg};'>{_escape(repeated_value)}</span>"
                f" &nbsp; | &nbsp; "
                f"<span style='display:inline-block;min-width:55%;"
                f"text-align:{detail_align};font-family:{_escape(detail_family)};"
                f"font-size:{detail_size}pt;font-weight:{detail_weight};"
                f"{detail_italic}{detail_underline};color:{detail_color};"
                f"background:{detail_bg};'>{_escape(detail_value)}</span>"
                "</div>"
            )

        page.atelier_sample.setText("".join(parts))

    @staticmethod
    def _normalized_detail_groupings(values):
        result = []
        for value in values or []:
            if not value:
                break
            text = str(value)
            if text not in result:
                result.append(text)
        return result[:3]

    def _grouping_label(self, field):
        if field == "__acquisition_year__":
            return "Année"
        return self.labels.get(field, field)

    def _detail_group_value(self, record, field):
        if field == "__acquisition_year__":
            raw = str(record.get("acquisition_date", "") or "").strip()
            match = re.search(r"(\d{4})$", raw)
            return match.group(1) if match else tr("(vide)", self.language)
        raw = str(record.get(field, "") or "").strip()
        return display_native_value(raw, self.language) if raw else tr("(vide)", self.language)

    def _group_records_for_detail(self, records, field):
        groups = defaultdict(list)
        for record in records:
            groups[self._detail_group_value(record, field)].append(record)
        return groups

    def _sorted_detail_group_keys(self, keys, field):
        if field == "__acquisition_year__":
            def year_key(value):
                text = str(value)
                return (0, int(text)) if text.isdigit() else (1, text.casefold())
            return sorted(keys, key=year_key)
        return sorted(keys, key=lambda value: str(value).casefold())

    @staticmethod
    def _sorted_records_for_grouped_detail(records, fields):
        if "record_number" in fields:
            return sorted(records, key=lambda record: _number(record.get("record_number")))
        return list(records)

    def _grouped_detail_print_html(self, title, records, fields, groupings, atelier_style=None):
        atelier_style = {**self._default_atelier_style(), **dict(atelier_style or {})}
        headers = "".join(f"<th>{_escape(self.labels.get(field, field))}</th>" for field in fields)

        def render(subset, level):
            if level >= len(groupings):
                rows = []
                for record in self._sorted_records_for_grouped_detail(subset, fields):
                    cells = "".join(f"<td>{_escape(_detail_display_value(field, record.get(field, ''), self.language))}</td>" for field in fields)
                    rows.append(f"<tr>{cells}</tr>")
                return f"<table><thead><tr>{headers}</tr></thead><tbody>{''.join(rows)}</tbody></table>"
            field = groupings[level]
            groups = self._group_records_for_detail(subset, field)
            parts = []
            for value in self._sorted_detail_group_keys(list(groups), field):
                entries = groups[value]
                boxes = sum(_number(rec.get("box_count")) for rec in entries)
                species = self._species_count(entries)
                margin = 24 * level
                background = (atelier_style.get("level1_bg", "#C8D8D0"), atelier_style.get("level2_bg", "#DDE8E2"), atelier_style.get("level3_bg", "#EEF3F0"))[min(level, 2)]
                top_margin = (22 * int(atelier_style.get("primary_spacing_lines", 2))) if level == 0 else 10
                label = _escape(self._grouping_label(field))
                strong_color = (atelier_style.get("level1_text", "#9A3324"), atelier_style.get("level2_text", "#111111"), atelier_style.get("level3_text", "#737B77"))[min(level, 2)]
                parts.append(
                    f"<div class='group-header level-{level + 1}' "
                    f"style='margin-top:{top_margin}px;margin-left:{margin}px;"
                    f"padding:9px 12px;background:{background};page-break-after:avoid;'>"
                    f"<span style='color:#6F7773'>{label} :</span> "
                    f"<b><span style='color:{strong_color}'>{_escape(value)}</span></b>"
                    f" &nbsp;—&nbsp; <b><span style='color:{strong_color}'>{self._fmt_number(boxes)}</span></b> "
                    f"<span style='color:#6F7773'>boîtes</span>"
                    f" &nbsp;—&nbsp; <b><span style='color:{strong_color}'>{species}</span></b> "
                    f"<span style='color:#6F7773'>espèces</span>"
                    f" &nbsp;—&nbsp; "
                    f"<span style='color:#888888'>{len(entries)} fiche(s)</span>"
                    f"</div>"
                )
                parts.append(render(entries, level + 1))
            return "".join(parts)

        body = render(records, 0)
        boxes = sum(_number(rec.get("box_count")) for rec in records)
        species = self._species_count(records)
        subtitle = (
            f"<b>{self._fmt_number(boxes)} boîtes — {species} espèces</b> "
            f"<span style='color:#888'>— {len(records)} fiche(s)</span>"
        )
        return self._html_shell(title, subtitle, body, subtitle_is_html=True)

    def _summary_html(
        self, title: str, records: list[dict], group_field: str, calc: str
    ) -> str:
        # Compatibilité avec le constructeur actuel :
        # le résumé MM3 met désormais toujours en avant le nombre de pièces
        # et conserve le nombre de fiches comme information secondaire.
        groups: dict[str, list[dict]] = defaultdict(list)
        for record in records:
            key = str(record.get(group_field, "") or "(vide)")
            groups[key].append(record)

        rows_data = []
        for key in sorted(groups, key=str.casefold):
            entries = groups[key]
            rows_data.append({
                "group": key,
                "boxes": sum(_number(rec.get("box_count")) for rec in entries),
                "species": self._species_count(entries),
                "records": len(entries),
                "entries": entries,
            })

        return self._summary_html_visual(
            title,
            rows_data,
            group_field,
            [group_field, "__boxes__", "__species__", "__records__"],
            len(records),
        )

    def _summary_html_visual(
        self,
        title: str,
        rows_data: list[dict],
        group_field: str,
        visual_fields: list[str],
        total_records: int,
    ) -> str:
        label_by_key = {
            group_field: self.labels.get(group_field, group_field),
            "__boxes__": "Nombre de pièces",
            "__species__": "Nombre d’espèces",
            "__records__": "Nombre de fiches",
        }

        def visual_label(key):
            return label_by_key.get(key, self.labels.get(key, key))

        headers = "".join(
            f"<th>{_escape(visual_label(key))}</th>" for key in visual_fields
        )

        rows = []
        total_boxes = 0.0
        for row in rows_data:
            total_boxes += float(row["boxes"])
            cells = []
            for key in visual_fields:
                if key == group_field:
                    shown = str(row["group"])
                elif key == "__boxes__":
                    val = float(row["boxes"])
                    shown = str(int(val) if val.is_integer() else val).replace(".", ",")
                elif key == "__species__":
                    shown = str(int(row.get("species", 0)))
                elif key == "__records__":
                    shown = str(int(row["records"]))
                else:
                    entries = list(row.get("entries", []) or [])
                    values = [
                        str(rec.get(key, "") or "").strip()
                        for rec in entries
                        if str(rec.get(key, "") or "").strip()
                    ]
                    shown = ", ".join(dict.fromkeys(values))
                cells.append(f"<td style='{cell_box_css}'>{_escape(shown)}</td>")
            rows.append("<tr>" + "".join(cells) + "</tr>")

        total_cells = []
        for key in visual_fields:
            if key == group_field:
                shown = "Total"
            elif key == "__boxes__":
                shown = str(
                    int(total_boxes) if total_boxes.is_integer() else total_boxes
                ).replace(".", ",")
            elif key == "__species__":
                shown = str(len({
                    str(rec.get("mineral_name","") or "").strip().upper()
                    for row in rows_data for rec in row.get("entries", [])
                    if str(rec.get("mineral_name","") or "").strip()
                }))
            elif key == "__records__":
                shown = str(total_records)
            else:
                shown = ""
            total_cells.append(f"<td>{_escape(shown)}</td>")

        body = (
            f"<table><thead><tr>{headers}</tr></thead>"
            f"<tbody>{''.join(rows)}"
            f"<tr class='total'>{''.join(total_cells)}</tr></tbody></table>"
        )

        boxes_text = str(
            int(total_boxes) if total_boxes.is_integer() else total_boxes
        ).replace(".", ",")
        group_count = len(rows_data)
        group_label = self.labels.get(group_field, group_field).lower()
        if group_count != 1 and not group_label.endswith("s"):
            group_label += "s"
        subtitle = (
            f"<b>{boxes_text} boîtes</b> "
            f"<span style='color:#888'>— {group_count} {_escape(group_label)} "
            f"— {total_records} fiche(s)</span>"
        )
        return self._html_shell(
            title,
            subtitle,
            body,
            subtitle_is_html=True,
        )


    @staticmethod
    def _html_shell(title: str, subtitle: str, body: str, subtitle_is_html: bool = False) -> str:
        subtitle_text = subtitle if subtitle_is_html else _escape(subtitle)
        return f"""<html><head><meta charset="utf-8"><style>
        body {{ font-family: Arial, sans-serif; color:#222; font-size:10pt; }}
        h1 {{ font-size:18pt; margin-bottom:4px; }}
        .sub {{ color:#666; margin-bottom:14px; }}
        table {{ width:100%; border-collapse:collapse; page-break-inside:auto; }}
        thead {{ display:table-header-group; }}
        tbody {{ display:table-row-group; }}
        tr {{ page-break-inside:avoid; page-break-after:auto; }}
        th {{ background:#e7ece9; text-align:left; }}
        th,td {{ border-bottom:1px solid #999; padding:5px 7px; }}
        tr:nth-child(even):not(.mm3-separator) td {{ background:#f5f7f6; }}
        .group-header {{ page-break-after:avoid; }}
        .total {{ page-break-inside:avoid; }}
        .total td {{ font-weight:bold; border-top:2px solid #444; }}
        .mm3-separator td, .mm3-separator th {{
            padding:0 !important;
            margin:0 !important;
            border:0 !important;
            background:#000000 !important; background-color:#000000 !important;
        }}
        </style></head><body><h1>{_escape(title)}</h1>
        <div class="sub">{subtitle_text}</div>{body}</body></html>"""


    def _apply_native_print_table_lines(self, document: QTextDocument) -> None:
        """Applique Filet/Grille avec les primitives natives du moteur Qt.

        Les bordures CSS très fines sont parfois arrondies à zéro par QTextDocument.
        QTextTableCellFormat est utilisé ici après setHtml(), donc juste avant
        l'aperçu et l'impression réels.
        """
        style = dict(getattr(self, "_last_print_advanced_style", {}) or {})
        border_mode = str(style.get("detail_borders") or "none")
        trait = str(style.get("detail_trait") or "none")

        # Une vraie ligne de 0,25 pt pour Filet / Horizontales / Grille.
        wants_grid = border_mode == "grid"
        wants_horizontal = border_mode == "horizontal"
        wants_hairline = trait == "hairline"

        if not (wants_grid or wants_horizontal or wants_hairline):
            return

        try:
            solid = QTextFrameFormat.BorderStyle.BorderStyle_Solid
        except Exception:
            try:
                solid = QTextFrameFormat.BorderStyle_Solid
            except Exception:
                solid = 1

        black = QBrush(QColor("#000000"))
        width = 0.25

        def format_table(table: QTextTable) -> None:
            if (getattr(self, "_last_print_detail_graphic", False)
                    and table.rows() == 1 and table.columns() == 1):
                return
            try:
                tf = table.format()
                tf.setBorderCollapse(True)
                table.setFormat(tf)
            except Exception:
                pass

            rows = table.rows()
            cols = table.columns()

            for row in range(rows):
                for col in range(cols):
                    cell = table.cellAt(row, col)
                    if not cell.isValid():
                        continue

                    try:
                        fmt = QTextTableCellFormat(cell.format())
                    except Exception:
                        try:
                            fmt = cell.format().toTableCellFormat()
                        except Exception:
                            continue

                    try:
                        if wants_grid:
                            fmt.setBorder(width)
                            fmt.setBorderBrush(black)
                            fmt.setBorderStyle(solid)
                        else:
                            # Filet et Horizontales : uniquement sous la cellule.
                            fmt.setBottomBorder(width)
                            fmt.setBottomBorderBrush(black)
                            fmt.setBottomBorderStyle(solid)

                        cell.setFormat(fmt)
                    except Exception:
                        continue

        def visit(frame) -> None:
            for child in frame.childFrames():
                if isinstance(child, QTextTable):
                    format_table(child)
                visit(child)

        visit(document.rootFrame())


    def _apply_native_summary_vertical_align(self, document: QTextDocument) -> None:
        """Répartit l'espace d'une ligne imprimée autour de ses données."""
        if getattr(self, "_last_print_detail_graphic", False):
            return
        value = str(dict(getattr(self, "_last_summary_header_metrics", {}) or {}).get("row_vertical_align") or "center")
        heights = list(getattr(self, "_last_summary_row_heights_pt", []) or [])
        sizes = list(getattr(self, "_last_summary_row_font_sizes_pt", []) or [])
        tables = []
        def collect(frame):
            for child in frame.childFrames():
                if isinstance(child, QTextTable):
                    tables.append(child)
                collect(child)
        collect(document.rootFrame())
        if not tables:
            return
        table = max(tables, key=lambda t: (t.rows(), t.columns()))
        style = dict(getattr(self, "_last_print_advanced_style", {}) or {})
        raw = dict(style.get("summary_layout_marks") or {}).get("after_header")
        entries = raw if isinstance(raw, list) else [raw]
        data_start = 2 if any(isinstance(item, dict) and item.get("kind") == "space" for item in entries) else 1
        for row in range(data_start, table.rows()):
            index = row - data_start
            if index >= len(heights):
                break
            # L'option valign des cellules n'est pas respectée à l'impression
            # par certains moteurs Qt. Les marges internes sont, elles, rendues.
            spare = max(0.0, heights[index] -
                        (sizes[index] if index < len(sizes) else 10.0) * 1.1 - 1.5)
            for col in range(table.columns()):
                cell = table.cellAt(row, col)
                try:
                    fmt = QTextTableCellFormat(cell.format())
                except Exception:
                    fmt = cell.format().toTableCellFormat()
                # Les interlignes étaient entièrement logés dans le padding
                # inférieur. Le conserver avec max() empêchait « Bas » de
                # déplacer le texte : on redistribue cette même hauteur.
                original_top = max(0.0, float(fmt.topPadding()))
                original_bottom = max(0.0, float(fmt.bottomPadding()))
                free = max(spare, original_top + original_bottom - 2.0)
                fraction = 1.0 if value == "bottom" else 0.5 if value == "center" else 0.0
                fmt.setTopPadding(1.0 + free * fraction)
                fmt.setBottomPadding(1.0 + free * (1.0 - fraction))
                cell.setFormat(fmt)

    def _apply_native_summary_layout_marks(self, document: QTextDocument, monochrome: bool = False) -> None:
        """27.63 — applique Interlignes/Filets du résumé avec les primitives Qt.

        Le constructeur et l'Aperçu écran savent déjà rendre ces éléments. Pour
        l'impression, QTextDocument peut compacter les lignes HTML de séparation ;
        on applique donc les marques du tableau directement aux cellules du vrai
        tableau de données, après setHtml().
        """
        if getattr(self, "_last_print_detail_graphic", False):
            return
        style = dict(getattr(self, "_last_print_advanced_style", {}) or {})
        marks = dict(style.get("summary_layout_marks") or {})
        if not marks:
            return

        def mark_items(position):
            raw = marks.get(position)
            items = raw if isinstance(raw, list) else [raw]
            out=[]
            for item in items:
                if isinstance(item, dict):
                    kind=str(item.get("kind") or "none")
                    if kind in {"space","line"}:
                        size=float(item.get("size") or (8 if kind=="space" else 1))
                        color="#000000" if monochrome else str(item.get("color") or "#000000")
                        out.append((kind,max(0.5 if kind=="line" else 1,size),color))
            return sorted(out, key=lambda x: 0 if x[0]=="line" else 1)

        def mark(position):
            items=mark_items(position)
            return items[0] if items else ("none",0,"#000000")

        tables = []
        def collect(frame):
            for child in frame.childFrames():
                if isinstance(child, QTextTable):
                    tables.append(child)
                collect(child)
        collect(document.rootFrame())
        if not tables:
            return
        # Identifier les filets hors tableau par leur marqueur HTML, puis ôter
        # le marqueur du document. Qt ignore parfois les bordures CSS mais
        # conserve les bordures affectées au QTextTableCellFormat.
        for position in ("after_title", "after_band", "before_footer_line", "before_footer"):
            cursor = document.find("MM3_LINE_" + position.upper())
            if cursor.isNull():
                continue
            outer = cursor.currentTable()
            if outer is None:
                continue
            cell = outer.cellAt(0, 0)
            cursor.removeSelectedText()
            for kind, size, color in mark_items(position):
                if kind != "line":
                    continue
                try:
                    fmt = QTextTableCellFormat(cell.format())
                except Exception:
                    fmt = cell.format().toTableCellFormat()
                try:
                    fmt.setBottomBorder(float(size))
                    fmt.setBottomBorderBrush(QBrush(QColor(color)))
                    fmt.setBottomBorderStyle(QTextFrameFormat.BorderStyle.BorderStyle_Solid)
                    cell.setFormat(fmt)
                except Exception:
                    pass
        # Le tableau de données est celui qui possède le plus de lignes.
        table = max(tables, key=lambda t: (t.rows(), t.columns()))
        if table.rows() < 1:
            return

        try:
            solid = QTextFrameFormat.BorderStyle.BorderStyle_Solid
        except Exception:
            try:
                solid = QTextFrameFormat.BorderStyle_Solid
            except Exception:
                solid = 1

        def cell_format(row, col):
            cell = table.cellAt(row, col)
            if not cell.isValid():
                return None, None
            try:
                return cell, QTextTableCellFormat(cell.format())
            except Exception:
                try:
                    return cell, cell.format().toTableCellFormat()
                except Exception:
                    return None, None

        # Sous les en-têtes : filet sur l'en-tête, interligne dans une ligne
        # propre au tableau, sans agrandir la première ligne de données.
        has_header_space = any(kind == "space" for kind, _, _ in mark_items("after_header"))
        data_start = 2 if has_header_space else 1
        for kind, size, color in mark_items("after_header"):
            if kind == "line":
                brush = QBrush(QColor(color))
                for col in range(table.columns()):
                    cell, fmt = cell_format(0, col)
                    if fmt is None: continue
                    try:
                        fmt.setBottomBorder(float(size)); fmt.setBottomBorderBrush(brush); fmt.setBottomBorderStyle(solid); cell.setFormat(fmt)
                    except Exception: pass
            elif kind == "space" and table.rows() > 1:
                cell, fmt = cell_format(1, 0)
                if fmt is not None:
                    try:
                        fmt.setBottomPadding(max(float(fmt.bottomPadding()), float(size)))
                        cell.setFormat(fmt)
                    except Exception: pass

        # 27.110 — Qt épaissit les bordures internes lorsque le QTextTable est
        # en mode border-collapse : la frontière entre deux lignes est alors
        # fusionnée comme une frontière partagée, tandis que la bordure terminale
        # reste correctement fine.  Dès qu'un filet « entre les données » est
        # demandé, on isole donc les cellules (espacement nul) AVANT d'appliquer
        # leurs bordures basses.  Cela doit donner à chaque séparation le même
        # statut que la bordure terminale, sans toucher au filet after_header.
        _between_items = mark_items("between_data")
        if any(kind == "line" for kind, _size, _color in _between_items):
            try:
                tf = table.format()
                tf.setBorderCollapse(False)
                try:
                    tf.setCellSpacing(0.0)
                except Exception:
                    pass
                table.setFormat(tf)
            except Exception:
                pass

        # Entre les lignes : bordure ou marge basse portée par chaque cellule.
        for kind, size, color in _between_items:
            if kind in {"line", "space"}:
                brush = QBrush(QColor(color))
                for row in range(data_start, table.rows()):
                    for col in range(table.columns()):
                        cell, fmt = cell_format(row, col)
                        if fmt is None: continue
                        try:
                            if kind == "line":
                                # 27.102 — le filet minimal est désormais « Fin » (0,5 pt).
                                fmt.setBottomPadding(max(float(fmt.bottomPadding()), 2.0))
                                fmt.setBottomBorder(float(size)); fmt.setBottomBorderBrush(brush); fmt.setBottomBorderStyle(solid)
                            else:
                                fmt.setBottomPadding(max(float(fmt.bottomPadding()), float(size)))
                            cell.setFormat(fmt)
                        except Exception: pass

    def _apply_native_detail_layout_marks(self, document: QTextDocument, monochrome=False) -> None:
        """Filets du détail : chaque position correspond à sa propre ligne."""
        if not getattr(self, "_last_print_detail_graphic", False):
            return
        style = dict(getattr(self, "_last_print_advanced_style", {}) or {})
        marks = dict(style.get("summary_layout_marks") or {})
        tables = []
        def collect(frame):
            for child in frame.childFrames():
                if isinstance(child, QTextTable):
                    tables.append(child)
                collect(child)
        collect(document.rootFrame())
        data = next((t for t in tables if t.rows() > 1), None)
        try:
            solid = QTextFrameFormat.BorderStyle.BorderStyle_Solid
        except AttributeError:
            solid = QTextFrameFormat.BorderStyle_Solid

        def apply(cell, kind, size, color):
            if not cell.isValid():
                return
            try:
                fmt = QTextTableCellFormat(cell.format())
            except Exception:
                fmt = cell.format().toTableCellFormat()
            if kind == "line":
                fmt.setBottomBorder(max(0.5, float(size)))
                fmt.setBottomBorderBrush(QBrush(QColor(
                    "#000000" if monochrome else color)))
                fmt.setBottomBorderStyle(solid)
            else:
                fmt.setBottomPadding(max(float(fmt.bottomPadding()), float(size)))
            cell.setFormat(fmt)

        # Les filets du titre, bandeau et pied sont des tableaux d'une cellule,
        # dans le même ordre que les emplacements insérés dans le document.
        outer = [t for t in tables if t.rows() == 1 and t.columns() == 1]
        for table, (size, color) in zip(outer, getattr(self, "_last_detail_print_outer_marks", [])):
            apply(table.cellAt(0, 0), "line", size, color)
        if data is None:
            return
        fmt = data.format()
        try:
            fmt.setBorderCollapse(False)
            fmt.setCellSpacing(0.0)
            data.setFormat(fmt)
        except Exception:
            pass
        # 1.0.339.15 — html_rows indexe uniquement le <tbody>, tandis que
        # QTextTable inclut la ligne <thead> en position zéro. L'ancien code
        # appliquait donc chaque repère à la ligne PRÉCÉDENTE : un interligne
        # de 20 pt se retrouvait dans la dernière cellule grisée du groupe.
        # Déduire le décalage de la présence réelle des libellés de colonnes.
        html_row_offset = max(0, data.rows() - len(getattr(self, "_last_detail_print_screen_rows", [])))
        for html_row, kind, size, color in getattr(self, "_last_detail_print_mark_rows", []):
            row = html_row + html_row_offset
            if 0 <= row < data.rows():
                # Les repères « entre champs maîtres » concernent toute la
                # largeur utile de l’état. Sur une cellule HTML fusionnée,
                # QTextTable n’appliquait le bord qu’à la première colonne.
                # Poser le repère sur chaque colonne garantit un filet continu,
                # comme celui placé avant le pied de page.
                for col in range(data.columns()):
                    apply(data.cellAt(row, col), kind, size, color)

        raw = marks.get("between_data")
        entries = raw if isinstance(raw, list) else [raw]
        for entry in entries:
            if not isinstance(entry, dict) or entry.get("kind") not in {"line", "space"}:
                continue
            kind = str(entry["kind"])
            size = float(entry.get("size") or (8 if kind == "space" else 0.5))
            color = str(entry.get("color") or "#000000")
            for html_row in getattr(self, "_last_detail_print_data_rows", []):
                row = html_row + html_row_offset
                if 0 <= row < data.rows():
                    for col in range(data.columns()):
                        apply(data.cellAt(row, col), kind, size, color)

    def _prepare_multipage_document(self, document: QTextDocument, printer: QPrinter) -> None:
        """Prépare le document pour une impression réellement multipage.

        - taille de page synchronisée sur l'imprimante ;
        - répétition de la première ligne de chaque tableau sur les pages suivantes ;
        - lignes de tableau indivisibles autant que Qt le permet.
        """
        try:
            page_rect = printer.pageRect(QPrinter.Unit.Point)
            page_size = page_rect.size()
            metrics = dict(getattr(self, "_last_summary_header_metrics", {}) or {})
            if bool(metrics.get("page_numbers_enabled", False)):
                # Réserver une vraie zone au bas de chaque page : le numéro ne
                # doit jamais recouvrir la dernière ligne de données.
                page_size.setHeight(max(36.0, float(page_size.height()) - 18.0))
            document.setPageSize(page_size)
        except Exception:
            # Une imprimante virtuelle ou un pilote exotique ne doit pas bloquer l'aperçu.
            pass

        def configure_frame(frame) -> None:
            for child in frame.childFrames():
                if isinstance(child, QTextTable):
                    try:
                        fmt = child.format()
                        # Le détail graphique commence par un groupe ou un filet :
                        # cette première ligne ne doit pas se répéter en tête
                        # de chaque page imprimée.
                        fmt.setHeaderRowCount(
                            0 if getattr(self, "_last_print_detail_graphic", False)
                            else (1 if child.rows() > 1 else 0)
                        )
                        child.setFormat(fmt)
                    except Exception:
                        pass
                configure_frame(child)

        configure_frame(document.rootFrame())


    def _print_document_with_page_numbers(self, document: QTextDocument, printer: QPrinter) -> None:
        """Imprime le QTextDocument et ajoute un numéro calculé sur chaque page (27.132)."""
        metrics = dict(getattr(self, "_last_summary_header_metrics", {}) or {})
        if not bool(metrics.get("page_numbers_enabled", False)):
            document.print_(printer); return
        painter = None
        try:
            page_pt = printer.pageRect(QPrinter.Unit.Point)
            page_px = printer.pageRect(QPrinter.Unit.DevicePixel)
            page_h = max(1.0, float(document.pageSize().height()))
            total = max(1, int(document.pageCount()))
            # Le rendu manuel des numéros contourne QTextDocument.print_ :
            # appliquer explicitement les pages retenues par le dialogue Qt.
            pages = list(range(1, total + 1))
            if printer.printRange() == QPrinter.PrintRange.PageRange:
                first = max(1, int(printer.fromPage() or 1))
                last = min(total, int(printer.toPage() or total))
                pages = [n for n in pages if first <= n <= last]
            if not pages:
                return
            painter = QPainter(printer)
            if not painter.isActive():
                document.print_(printer); return
            sx = float(page_px.width()) / max(1.0, float(page_pt.width()))
            sy = float(page_px.height()) / max(1.0, float(page_pt.height()))
            fmt = str(metrics.get("page_number_format") or "page_x_y")
            align = str(metrics.get("page_number_align") or "right")
            for position, n in enumerate(pages):
                idx = n - 1
                if position: printer.newPage()
                painter.save(); painter.scale(sx, sy); painter.translate(0.0, -idx * page_h)
                from PySide6.QtCore import QRectF
                document.drawContents(painter, QRectF(0.0, idx*page_h, float(page_pt.width()), page_h))
                painter.restore()
                text = f"Page {n} / {total}" if fmt=="page_x_y" else (f"Page {n}" if fmt=="page_x" else f"{n} / {total}")
                painter.save(); font=QFont("Calibri"); font.setPointSize(9); painter.setFont(font); painter.setPen(QColor("#111111"))
                margin=max(8, int(6*sx)); y=max(0, int(page_px.height())-max(18,int(14*sy)))
                flags = Qt.AlignmentFlag.AlignVCenter | (Qt.AlignmentFlag.AlignLeft if align=="left" else Qt.AlignmentFlag.AlignHCenter if align=="center" else Qt.AlignmentFlag.AlignRight)
                painter.drawText(margin, y, max(1,int(page_px.width())-2*margin), max(16,int(12*sy)), int(flags), text); painter.restore()
            painter.end()
        except Exception:
            # Ne jamais relancer l'impression complète après le début d'un rendu
            # partiel : cela réimprimerait des pages non sélectionnées.
            if painter is not None and painter.isActive():
                painter.end()


    def _apply_native_summary_column_widths(self, document: QTextDocument, printer: QPrinter) -> None:
        """Fixe la largeur physique des colonnes à celle de l'aperçu écran."""
        geometry = getattr(self, "_last_summary_column_widths", None)
        if not geometry:
            return
        widths_px, screen_dpi = geometry
        if not widths_px or screen_dpi <= 0:
            return
        # Le document Qt travaille en points après setPageSize(pageRect(Point)).
        widths_pt = [max(1.0, float(width) * 72.0 / screen_dpi) for width in widths_px]
        page_width = float(printer.pageRect(QPrinter.Unit.Point).width())
        # 1.0.333 : le diagnostic Qt 1.0.332 a révélé un tableau de
        # 591 pt pour une page imprimable de 571 pt. Laisser une réserve
        # explicite de 20 pt pour l'expansion intrinsèque du tableau Qt,
        # sans toucher aux marges physiques A4 ni au constructeur.
        # Le diagnostic 1.0.332 avait appelé document.adjustSize(), ce
        # qui modifiait la pagination : ne jamais le reproduire ici.
        detail = bool(getattr(self, "_last_print_detail_graphic", False))
        available = max(1.0, page_width - (30.0 if detail else 10.0))
        scale = min(1.0, available / sum(widths_pt))
        widths_pt = [width * scale for width in widths_pt]

        def visit(frame):
            for child in frame.childFrames():
                if isinstance(child, QTextTable) and child.columns() == len(widths_pt) and child.rows() > 1:
                    fmt = child.format()
                    if getattr(self, "_last_print_detail_graphic", False):
                        fmt.setCellPadding(0)
                        fmt.setCellSpacing(0)
                    fmt.setWidth(QTextLength(QTextLength.Type.FixedLength, min(available, sum(widths_pt))))
                    fmt.setColumnWidthConstraints([
                        QTextLength(QTextLength.Type.FixedLength, width) for width in widths_pt
                    ])
                    child.setFormat(fmt)
                    if detail:
                        # 1.0.337 : conserver le recul visuel de la date obtenu
                        # en 1.0.335, mais sans modifier le format des cellules
                        # Qt. Le padding de cellule peut élargir/recalculer la
                        # grille et perturber les lignes de groupe fusionnées.
                        # Une marge de paragraphe ne touche pas au tableau.
                        last_column = child.columns() - 1
                        for row_index in range(child.rows()):
                            cell = child.cellAt(row_index, last_column)
                            if (not cell.isValid() or cell.column() != last_column
                                    or cell.columnSpan() != 1):
                                continue
                            cursor = cell.firstCursorPosition()
                            block = cursor.block()
                            if not block.isValid():
                                continue
                            # Ne décaler que les valeurs effectivement
                            # justifiées à droite, pas les séparateurs.
                            if not (block.blockFormat().alignment() & Qt.AlignmentFlag.AlignRight):
                                continue
                            if not block.text().strip():
                                continue
                            block_fmt = cursor.blockFormat()
                            block_fmt.setRightMargin(max(float(block_fmt.rightMargin()), 24.0))
                            cursor.setBlockFormat(block_fmt)
                    return True
                if visit(child):
                    return True
            return False
        visit(document.rootFrame())

    def _keep_detail_rows_on_one_page(self, document: QTextDocument) -> None:
        """Déplace une ligne entière si Qt répartit ses cellules sur deux pages."""
        if not getattr(self, "_last_print_detail_graphic", False):
            return
        page_height = float(document.pageSize().height())
        if page_height <= 0:
            return

        def find_table(frame):
            for child in frame.childFrames():
                if isinstance(child, QTextTable) and child.columns() > 1 and child.rows() > 1:
                    return child
                found = find_table(child)
                if found is not None:
                    return found
            return None

        table = find_table(document.rootFrame())
        if table is None:
            return
        layout = document.documentLayout()
        # Recalculer après chaque saut : un saut peut changer la page des lignes
        # suivantes. Ne pas appliquer de saut aux lignes de groupe fusionnées.
        for _ in range(3):
            changed = False
            document.pageCount()
            for row in range(table.rows()):
                if table.cellAt(row, 0).columnSpan() > 1:
                    continue
                blocks = [table.cellAt(row, col).firstCursorPosition().block()
                          for col in range(table.columns())]
                pages = [int(max(0.0, layout.blockBoundingRect(block).top()) / page_height)
                         for block in blocks if block.isValid()]
                if len(pages) < 2 or min(pages) == max(pages):
                    continue
                cursor = table.cellAt(row, 0).firstCursorPosition()
                fmt = cursor.blockFormat()
                if fmt.pageBreakPolicy() & QTextFormat.PageBreakFlag.PageBreak_AlwaysBefore:
                    continue
                fmt.setPageBreakPolicy(QTextFormat.PageBreakFlag.PageBreak_AlwaysBefore)
                cursor.setBlockFormat(fmt)
                changed = True
            if not changed:
                break

    def _prepared_print_pagination(self):
        """Retourne (nombre de pages, lignes écran ouvrant les pages 2..n)."""
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setPageOrientation(QPageLayout.Orientation.Landscape if self._last_landscape else QPageLayout.Orientation.Portrait)
        try:
            layout = printer.pageLayout(); layout.setMargins(QMarginsF(5.0, 5.0, 5.0, 5.0)); printer.setPageLayout(layout)
        except Exception:
            pass
        document = QTextDocument(self); document.setDocumentMargin(0 if getattr(self, "_last_print_detail_graphic", False) else 5)
        option = document.defaultTextOption()
        option.setWrapMode(QTextOption.WrapMode.NoWrap)
        document.setDefaultTextOption(option); document.setHtml(self._last_html)
        self._apply_native_print_table_lines(document)
        self._apply_native_summary_layout_marks(document, False)
        self._apply_native_summary_vertical_align(document)
        self._apply_native_detail_layout_marks(document, False)
        self._prepare_multipage_document(document, printer)
        self._apply_native_summary_column_widths(document, printer)
        self._keep_detail_rows_on_one_page(document)
        total = max(1, int(document.pageCount()))
        breaks = []
        if getattr(self, "_last_print_detail_graphic", False):
            def find_table(frame):
                for child in frame.childFrames():
                    if isinstance(child, QTextTable) and child.columns() > 1 and child.rows() > 1:
                        return child
                    found = find_table(child)
                    if found is not None:
                        return found
                return None
            table = find_table(document.rootFrame())
            if table is not None:
                layout = document.documentLayout()
                page_h = max(1.0, float(document.pageSize().height()))
                previous_page = 0
                # row 0 est l'en-tête HTML; les lignes tbody suivent l'ordre
                # exact des lignes de l'aperçu détaillé.
                for tr in range(1, table.rows()):
                    block = table.cellAt(tr, 0).firstCursorPosition().block()
                    if not block.isValid():
                        continue
                    page = int(max(0.0, layout.blockBoundingRect(block).top()) / page_h)
                    if page > previous_page:
                        html_index = tr - 1
                        row_map = list(getattr(self, "_last_detail_print_screen_rows", []) or [])
                        if 0 <= html_index < len(row_map):
                            screen_row = int(row_map[html_index])
                        else:
                            screen_row = html_index
                        if screen_row >= 0:
                            breaks.append(screen_row)
                        previous_page = page
        return total, breaks

    def _prepared_print_page_count(self) -> int:
        """Retourne le nombre de pages avec exactement la préparation d'impression."""
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setPageOrientation(QPageLayout.Orientation.Landscape if self._last_landscape else QPageLayout.Orientation.Portrait)
        try:
            layout = printer.pageLayout(); layout.setMargins(QMarginsF(5.0, 5.0, 5.0, 5.0)); printer.setPageLayout(layout)
        except Exception:
            pass
        document = QTextDocument(self); document.setDocumentMargin(0 if getattr(self, "_last_print_detail_graphic", False) else 5)
        option = document.defaultTextOption()
        option.setWrapMode(QTextOption.WrapMode.NoWrap)
        document.setDefaultTextOption(option); document.setHtml(self._last_html)
        self._apply_native_print_table_lines(document)
        self._apply_native_summary_layout_marks(document, False)
        self._apply_native_summary_vertical_align(document)
        self._apply_native_detail_layout_marks(document, False)
        self._prepare_multipage_document(document, printer)
        self._apply_native_summary_column_widths(document, printer)
        self._keep_detail_rows_on_one_page(document)
        return max(1, int(document.pageCount()))

    def _print_preview(self) -> None:
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setDocName(self._last_title)
        printer.setPageOrientation(
            QPageLayout.Orientation.Landscape
            if self._last_landscape
            else QPageLayout.Orientation.Portrait
        )
        try:
            layout = printer.pageLayout()
            layout.setMargins(QMarginsF(5.0, 5.0, 5.0, 5.0))
            printer.setPageLayout(layout)
        except Exception:
            pass

        document = QTextDocument(self)
        document.setDocumentMargin(0 if getattr(self, "_last_print_detail_graphic", False) else 5)
        text_option = document.defaultTextOption()
        text_option.setWrapMode(
            QTextOption.WrapMode.WordWrap
            if getattr(self, "_last_print_detail_graphic", False)
            else QTextOption.WrapMode.NoWrap
        )
        document.setDefaultTextOption(text_option)
        document.setHtml(self._last_html)

        # Les lignes fines et la grille sont appliquées au document Qt lui-même.
        self._apply_native_print_table_lines(document)
        self._apply_native_summary_layout_marks(document, False)
        self._apply_native_summary_vertical_align(document)
        self._apply_native_detail_layout_marks(document, False)
        self._prepare_multipage_document(document, printer)
        self._apply_native_summary_column_widths(document, printer)
        self._keep_detail_rows_on_one_page(document)

        preview = QPrintPreviewDialog(printer, self)
        preview.setWindowTitle(f"{tr('Aperçu avant impression multipage', self.language)} — {self._last_title}")
        preview.resize(1100, 780)

        if str(self.language or "fr").lower().startswith("en"):
            translations = {
                "Imprimer":"Print", "Mise en page":"Page setup",
                "Ajuster à la largeur":"Fit width", "Ajuster à la page":"Fit page",
                "Zoom avant":"Zoom in", "Zoom arrière":"Zoom out",
                "Paysage":"Landscape", "Une page":"Single page",
                "Pages en vis-à-vis":"Facing pages", "Toutes les pages":"All pages",
                "Afficher une seule page":"Show single page",
                "Afficher les pages en vis-à-vis":"Show facing pages",
                "Afficher un aperçu de toutes les pages":"Show overview of all pages",
                "Première page":"First page", "Page précédente":"Previous page",
                "Page suivante":"Next page", "Dernière page":"Last page",
            }
        else:
            translations = {
                "Print":"Imprimer", "Page setup":"Mise en page", "Page Setup":"Mise en page",
                "Fit width":"Ajuster à la largeur", "Fit page":"Ajuster à la page",
                "Zoom in":"Zoom avant", "Zoom out":"Zoom arrière",
                "Portrait":"Portrait", "Landscape":"Paysage",
                "Single page":"Une page", "Facing pages":"Pages en vis-à-vis",
                "All pages":"Toutes les pages",
                "Show single page":"Afficher une seule page",
                "Show facing pages":"Afficher les pages en vis-à-vis",
                "Show overview of all pages":"Afficher un aperçu de toutes les pages",
                "First page":"Première page",
                "Previous page":"Page précédente", "Next page":"Page suivante",
                "Last page":"Dernière page",
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
            if text in translations:
                button.setText(translations[text])
            if tip in translations:
                button.setToolTip(translations[tip])

        preview_widget = preview.findChild(QPrintPreviewWidget)
        zoom_combo = None
        for combo in preview.findChildren(QComboBox):
            values = [combo.itemText(i) for i in range(combo.count())]
            if any("%" in value for value in values) or "%" in combo.currentText():
                zoom_combo = combo
                break

        if preview_widget is not None and zoom_combo is not None:
            zoom_combo.setEditable(True)

            def apply_zoom_text(text):
                raw = str(text or "").strip().replace("%", "").replace(",", ".")
                try:
                    value = float(raw)
                except ValueError:
                    return
                value = max(10.0, min(500.0, value))
                preview_widget.setZoomMode(
                    QPrintPreviewWidget.ZoomMode.CustomZoom
                )
                preview_widget.setZoomFactor(value / 100.0)

            zoom_combo.currentTextChanged.connect(apply_zoom_text)
            if zoom_combo.lineEdit() is not None:
                zoom_combo.lineEdit().editingFinished.connect(
                    lambda: apply_zoom_text(zoom_combo.currentText())
                )
            # 27.61 — ouverture de l'aperçu d'impression à 100 %.
            QTimer.singleShot(0, lambda: (zoom_combo.setCurrentText("100,0%"), apply_zoom_text("100")))

        # 27.56 — l'impression est fidèle aux couleurs du modèle par défaut.
        # L'utilisateur peut demander explicitement une sortie Noir et blanc.
        original_html = self._last_html

        def monochrome_html(source):
            out = str(source)
            # Fonds clairs/blancs, textes noirs. Les traits restent noirs.
            out = re.sub(r"(?i)(?<!-)color\s*:\s*#[0-9a-f]{3,8}", "color:#000000", out)
            out = re.sub(r"(?i)background(?:-color)?\s*:\s*#[0-9a-f]{3,8}", "background:#FFFFFF", out)
            out = re.sub(r"(?i)bgcolor\s*=\s*[\"'][^\"']+[\"']", 'bgcolor="#FFFFFF"', out)
            return out

        bw_check = QCheckBox(tr("Noir et blanc", self.language), preview)
        bw_check.setToolTip(tr("Coché : impression en noir et blanc. Décoché : conserver les couleurs de l’état.", self.language))
        toolbar = preview.findChild(QToolBar)
        if toolbar is not None:
            toolbar.addSeparator()
            wa = QWidgetAction(toolbar)
            wa.setDefaultWidget(bw_check)
            toolbar.addAction(wa)
        elif preview.layout() is not None:
            preview.layout().insertWidget(0, bw_check)

        def apply_print_mode(checked):
            document.setHtml(monochrome_html(original_html) if checked else original_html)
            self._apply_native_print_table_lines(document)
            self._apply_native_summary_layout_marks(document, bool(checked))
            self._apply_native_summary_vertical_align(document)
            self._apply_native_detail_layout_marks(document, bool(checked))
            self._prepare_multipage_document(document, printer)
            self._apply_native_summary_column_widths(document, printer)
            self._keep_detail_rows_on_one_page(document)
            if preview_widget is not None:
                preview_widget.updatePreview()

        bw_check.toggled.connect(apply_print_mode)
        preview.paintRequested.connect(lambda p: self._print_document_with_page_numbers(document, p))
        preview.exec()

    def _apply_style(self) -> None:
        theme = collection_theme(self.startup.database.database_path, self.collection)
        self.setStyleSheet(f"""
            QMainWindow {{ background: {theme['gradient']}; }}
            #reportTitle {{ font-size:25px; font-weight:700; color:#24332B; }}
            #reportSubtitle {{ color:#607068; }}
            #sectionTitle {{ font-size:18px; font-weight:700; color:#24332B; }}
            #typeCard {{ background:{theme['panel']}; border:1px solid {theme['border']}; border-radius:9px; }}
            #cardTitle {{ font-size:17px; font-weight:700; color:#496C5B; }}
            QPushButton {{ padding:7px 12px; border:1px solid {theme['border']}; border-radius:6px; background:white; }}
            QPushButton:hover {{ background:{theme['hover']}; }}
            QGroupBox {{ border:1px solid {theme['border']}; border-radius:7px; margin-top:8px; padding-top:10px; font-weight:600; background:{theme['panel']}; }}
            QLineEdit, QComboBox, QListWidget {{ background:white; border:1px solid {theme['border']}; border-radius:5px; padding:5px; }}
        """)
