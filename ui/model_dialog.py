#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from core.calculation_formula import validate as validate_calculation_formula
from core.collection_folders import collection_display_name
from core.i18n import tr
from copy import deepcopy

from types import SimpleNamespace
import statistics
import json
import hashlib
import os
import sqlite3
import tempfile
import shutil
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QPoint, QRect, QEvent, QObject, QMimeData
import shiboken6
from PySide6.QtGui import QColor, QPainter, QPen, QCursor, QFont, QFontDatabase, QDrag
from PySide6.QtWidgets import (
    QCheckBox, QColorDialog, QComboBox, QDialog, QDialogButtonBox, QFrame, QGridLayout, QGroupBox,
    QApplication, QFileDialog, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget, QMenu, QMessageBox, QProgressDialog, QPushButton, QRadioButton, QRubberBand, QScrollArea, QSizePolicy, QSpinBox, QSplitter, QStyle, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from core.layout_geometry import BLOCK_GRID, BLOCK_MIN_HEIGHT, DEFAULT_FIELD_GEOMETRY
from core.layout_engine import (
    DISPLAY_SCALE, FIELD_LABEL_WIDTH, GROUP_CONTENT_RESERVE,
    field_outer_rect, field_parts,
)
from core.field_catalog import FIELD_BY_KEY
from core.model_manager import MODEL_BLOCKS, MOVABLE_FIELDS, ModelManager
from core.model_library import library_root, workspace_root_from_database, write_model, read_model, collect_model_field_keys, build_field_manifest, remap_model_payload
from ui.model_library_dialog import choose_model_save_path, choose_model_open_path, resolve_model_fields
from core.referential_manager import ReferentialManager
from ui.shared_field import SharedFieldFrame
from ui.form_surface import FormSurface
from ui.color_dialog import make_color_dialog, choose_color


GROUPS = (
    ("Bandeau", ("record_number", "mineral_name", "mineral_2", "mineral_3", "record_state")),
    ("Identification", (
        "mineral_class", "chemical_formula", "crystal_system", "luminescence",
        "luminescence_intensity", "fluorescence_color", "internet_link", "photo_data",
    )),
    ("Localisation", (
        "site_name", "deposit", "category", "site_internet_link", "department", "region", "country",
    )),
    ("Aspect", (
        "growth", "specimen_shape", "specimen_color", "quality", "type_locality",
        "minimum_magnification", "description",
    )),
    ("Acquisition", ("acquisition_date", "origin", "contact", "place")),
    ("Collection", ("box_type", "box_count", "price", "total_cost")),
)


class SheetGridOverlay(QWidget):
    """Quadrillage de fond de toute la feuille Atelier, sans intercepter la souris."""

    GRID_VISIBLE = 20

    def __init__(self, dialog, parent=None) -> None:
        super().__init__(parent)
        self.dialog = dialog
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        color = QColor("#D8DFDB")
        painter.setPen(QPen(color, 1))
        for x in range(0, self.width(), self.GRID_VISIBLE):
            painter.drawLine(x, 0, x, self.height())
        for y in range(0, self.height(), self.GRID_VISIBLE):
            painter.drawLine(0, y, self.width(), y)
        painter.end()


class MagneticCanvas(QWidget):
    """Surface de construction : grille, clic vide et lasso."""

    GRID_VISIBLE = 20
    GRID_SNAP = 5

    def __init__(self, block_name: str, dialog, parent=None) -> None:
        super().__init__(parent)
        self.block_name = block_name
        self.dialog = dialog
        self.setMinimumHeight(145)
        self.setMinimumWidth(520)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._lasso_origin = QPoint()
        self._lasso_rect = QRect()
        self._lasso_active = False

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        background, _border = self.dialog._group_colors(self.block_name)
        painter.fillRect(self.rect(), QColor(background))

        # 23.7.2 — en mode feuille libre, le quadrillage est unique et global.
        # Aucun second quadrillage n'est dessiné à l'intérieur des cadres.
        if not getattr(self.dialog, "_absolute_field_mode", False):
            painter.setPen(QPen(QColor("#D8DFDB"), 1))
            for x in range(0, self.width(), self.GRID_VISIBLE):
                painter.drawLine(x, 0, x, self.height())
            for y in range(0, self.height(), self.GRID_VISIBLE):
                painter.drawLine(0, y, self.width(), y)

        if self._lasso_active and not self._lasso_rect.isNull():
            painter.setPen(QPen(QColor("#3B78B8"), 1, Qt.PenStyle.DashLine))
            painter.setBrush(QColor(59, 120, 184, 35))
            painter.drawRect(self._lasso_rect)
        painter.end()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.RightButton:
            self.dialog._clear_preview_selection()
            self.dialog._show_group_context_menu(
                self.block_name, event.globalPosition().toPoint()
            )
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self.dialog._clear_preview_selection()
            self._lasso_origin = event.position().toPoint()
            self._lasso_rect = QRect(self._lasso_origin, self._lasso_origin)
            self._lasso_active = True
            self.update()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._lasso_active and (event.buttons() & Qt.MouseButton.LeftButton):
            self._lasso_rect = QRect(
                self._lasso_origin, event.position().toPoint()
            ).normalized()
            self.update()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self._lasso_active and event.button() == Qt.MouseButton.LeftButton:
            rect = self._lasso_rect.normalized()
            self._lasso_active = False
            self._lasso_rect = QRect()
            if rect.width() >= 4 and rect.height() >= 4:
                if getattr(self.dialog, "_absolute_field_mode", False):
                    host = self.dialog._construction_widget
                    top_left = self.mapTo(host, rect.topLeft())
                    sheet_rect = QRect(top_left, rect.size())
                    parts = self.dialog._parts_intersecting_sheet_rect(sheet_rect)
                    additive = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
                    # Règle Atelier : le lasso ne sélectionne jamais un cadre.
                    # Un cadre se sélectionne uniquement par clic sur son bandeau.
                    if not additive:
                        self.dialog._set_free_group_selection([], False)
                    self.dialog._set_preview_part_selection(parts, additive=additive)
                    self.dialog._raise_absolute_fields()
                    keys=list({key for key,_part in parts})
                else:
                    keys = [
                        key for key, field in self.dialog._preview_fields.items()
                        if field.parentWidget() is self
                        and field.isVisible()
                        and rect.intersects(field.geometry())
                    ]
                    self.dialog._set_preview_selection(keys)
                if keys:
                    first = self.dialog._preview_fields.get(keys[0])
                    if first is not None:
                        first.setFocus(Qt.FocusReason.MouseFocusReason)
            self.update()
            event.accept()
            return
        super().mouseReleaseEvent(event)


class DraggablePreviewField(SharedFieldFrame):
    """Objet de construction : sélection, déplacement, redimensionnement."""

    HANDLE = 9
    MIN_W = 100
    MIN_H = 22

    def __init__(self, dialog, key: str, label: str, parent=None) -> None:
        super().__init__(parent)
        self.dialog = dialog
        self.key = key
        self._dragging = False
        self._resizing = False
        self._resize_corner = ""
        self._press_global = QPoint()
        self._start_geom = QRect()
        self._drag_start_positions = {}

        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # 018.4.4.1.2.9 — IMPORTANT :
        # ne jamais utiliser setFixedSize ici. Il fixe min/max à la même valeur
        # et rend tout resize()/setGeometry() inopérant, même si les poignées
        # et curseurs apparaissent correctement.
        self.setMinimumSize(self.MIN_W, self.MIN_H)
        self.setMaximumSize(16777215, 16777215)
        self.resize(260, 31)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)

        # Présentation type Access : le même SharedFieldFrame sera utilisé
        # dans la vraie Fiche avec le vrai widget de saisie.
        self.caption = QLabel(label)
        self.caption.setWordWrap(False)
        self.caption.setStyleSheet(
            "font-weight: 600; color: #24342C; background: transparent; "
            "border: none; padding: 2px 4px;"
        )
        self.caption.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self.mock = QLabel("Exemple")
        self.mock.setMinimumHeight(18)
        self.mock.setStyleSheet(
            "background: white; border: 1px solid #B9C7C0; border-radius: 3px; "
            "padding: 2px 5px; color: #718078;"
        )
        self.mock.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self.set_widgets(self.caption, self.mock)
        self.set_scale(1.0)

        # 018.4.4.1.5.22.8 — poignées au-dessus des QLabel enfants.
        self._resize_handles = []
        for _ in range(8):
            handle = QFrame(self)
            handle.setFixedSize(self.HANDLE, self.HANDLE)
            handle.setStyleSheet("background: #F0A020; border: 1px solid #C77C00;")
            handle.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            handle.hide()
            self._resize_handles.append(handle)

        # Cadres de sélection de partie, réellement au-dessus des QLabel.
        self._part_selection_frames = {}
        for part in ("label", "data"):
            frame = QFrame(self)
            frame.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            frame.hide()
            self._part_selection_frames[part] = frame

        # Deux poignées horizontales VISIBLES par partie : gauche + droite.
        # Elles sont dessinées au-dessus des QLabel/QWidget de saisie.
        self._part_edge_handles = {}
        for part in ("label", "data"):
            for edge in ("left", "right"):
                handle = QFrame(self)
                handle.setFixedSize(self.HANDLE, max(self.HANDLE, 14))
                handle.setStyleSheet(
                    "background: #F0A020; border: 1px solid #C77C00;"
                )
                handle.setAttribute(
                    Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
                )
                handle.hide()
                self._part_edge_handles[(part, edge)] = handle

        # 23.8.6.9 — poignées verticales DÉDIÉES Haut/Bas.
        # Elles sont créées après les QLabel, cadres de sélection et poignées
        # de parties ; elles sont donc naturellement au sommet de l'empilement.
        self._vertical_resize_handles = {}
        for edge in ("top", "bottom"):
            handle = QFrame(self)
            handle.setObjectName(f"mm3VerticalResize_{edge}")
            handle.setStyleSheet(
                "background:#F0A020; border:1px solid #C77C00; border-radius:1px;"
            )
            handle.setAttribute(
                Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
            )
            handle.hide()
            self._vertical_resize_handles[edge] = handle

        # Polices de référence MM3. Elles servent au vrai retour "Style par défaut"
        # et évitent de repartir du dernier QFont personnalisé encore présent.
        self._default_caption_font = QFont(self.caption.font())
        self._default_mock_font = QFont(self.mock.font())

        self._apply_selection_style(False)

    def set_part_geometry(self, **kwargs) -> None:
        super().set_part_geometry(**kwargs)
        if hasattr(self, "_part_selection_frames"):
            self._update_part_selection_frames()

    def apply_shared_field_geometry(self, scale: float) -> None:
        """Même composant et même découpe que la vraie Fiche."""
        self.set_scale(scale)

    def set_label(self, text):
        self.caption.setText(text)

    def set_example(self, text):
        self.mock.setText(text if str(text).strip() else "Exemple")

    def apply_text_styles(self, styles=None) -> None:
        styles = styles or {}
        specs = (
            ("label", self.caption, "#24342C",
             "background: transparent; border: none; padding: 2px 4px;"),
            ("data", self.mock, "#8A9690",
             "background: white; border: 1px solid #B9C7C0; border-radius: 3px; padding: 2px 5px;"),
        )
        for target, widget, default_color, css in specs:
            style = styles.get(target, {}) if isinstance(styles, dict) else {}
            font = QFont(
                self._default_caption_font if target == "label"
                else self._default_mock_font
            )
            family = str(style.get("family", "")).strip()
            if family:
                font.setFamily(family)
            size = int(style.get("size", 0) or 0)
            if size > 0:
                font.setPointSize(size)
            font.setBold(bool(style.get("bold", False)))
            font.setItalic(bool(style.get("italic", False)))
            font.setUnderline(bool(style.get("underline", False)))
            widget.setFont(font)
            align_name = str(style.get("align", "left"))
            align_flag = {
                "left": Qt.AlignmentFlag.AlignLeft,
                "center": Qt.AlignmentFlag.AlignHCenter,
                "right": Qt.AlignmentFlag.AlignRight,
            }.get(align_name, Qt.AlignmentFlag.AlignLeft)
            valign_name = str(style.get("valign", "center")) if target == "data" else "center"
            valign_flag = {"top": Qt.AlignmentFlag.AlignTop, "center": Qt.AlignmentFlag.AlignVCenter, "bottom": Qt.AlignmentFlag.AlignBottom}.get(valign_name, Qt.AlignmentFlag.AlignVCenter)
            widget.setAlignment(align_flag | valign_flag)
            if target == "data":
                widget.setWordWrap(bool(style.get("wrap", False)))
            widget.setStyleSheet(
                f"color: {style.get('color', default_color)}; {css}"
            )

    def _update_part_selection_frames(self) -> None:
        frames = getattr(self, "_part_selection_frames", {})
        selected = getattr(self.dialog, "_selected_preview_parts", set())
        for part, frame in frames.items():
            active = (self.key, part) in selected
            if not active:
                frame.hide()
                continue
            rect = self.part_rect(part)
            if rect is None:
                frame.hide()
                continue
            # Orange pour Libellé, bleu pour Donnée : distinction immédiate.
            border = "#F0A020" if part == "label" else "#2474D2"
            frame.setStyleSheet(
                f"background: transparent; border: 2px solid {border};"
            )
            frame.setGeometry(rect.adjusted(0, 0, -1, -1))
            frame.show()
            frame.raise_()

        # Positionner les 4 poignées propres aux parties. Elles ne dépendent
        # plus des poignées du rectangle global du champ.
        part_handles = getattr(self, "_part_edge_handles", {})
        for (part, edge), handle in part_handles.items():
            active = (self.key, part) in selected
            rect = self.part_rect(part)
            if not active or rect is None:
                handle.hide()
                continue
            hh = max(self.HANDLE, min(14, max(1, rect.height() - 2)))
            handle.resize(self.HANDLE, hh)
            x = rect.left() - self.HANDLE // 2 if edge == "left" else rect.right() - self.HANDLE // 2
            x = max(0, min(max(0, self.width() - self.HANDLE), x))
            y = max(0, rect.center().y() - hh // 2)
            handle.move(x, y)
            handle.show()
            handle.raise_()

        # 23.8.6.7 — RÈGLE D'EMPILEMENT FINALE.
        # Cette méthode est rappelée après chaque resize/set_part_geometry.
        # Les 8 poignées du CHAMP COMPLET doivent donc être remontées ICI,
        # après tous les cadres et poignées Libellé/Donnée.
        whole_selected = (
            (self.key, "label") in selected
            and (self.key, "data") in selected
        )
        for handle in getattr(self, "_resize_handles", []):
            handle.setVisible(bool(whole_selected))
            if whole_selected:
                handle.show()
                handle.raise_()

        # Dernier mot sur l'empilement : Haut/Bas sont TOUJOURS au-dessus.
        self._position_vertical_resize_handles()

    def _position_vertical_resize_handles(self) -> None:
        handles = getattr(self, "_vertical_resize_handles", {})
        if not handles:
            return

        selected = self.key in self.dialog._selected_preview_keys
        grip_w = max(28, min(44, max(28, self.width() // 6)))
        grip_h = 7
        x = max(0, (self.width() - grip_w) // 2)

        top = handles.get("top")
        bottom = handles.get("bottom")

        if top is not None:
            top.setGeometry(x, 0, grip_w, grip_h)
            top.setVisible(bool(selected))
            if selected:
                top.raise_()
        if bottom is not None:
            bottom.setGeometry(
                x, max(0, self.height() - grip_h), grip_w, grip_h
            )
            bottom.setVisible(bool(selected))
            if selected:
                bottom.raise_()

    def _position_resize_handles(self) -> None:
        if not hasattr(self, "_resize_handles"):
            return
        s = self.HANDLE
        xs = (0, max(0, (self.width() - s)//2), max(0, self.width() - s))
        ys = (0, max(0, (self.height() - s)//2), max(0, self.height() - s))
        points = (
            (xs[0], ys[0]), (xs[2], ys[0]), (xs[0], ys[2]), (xs[2], ys[2]),
            (xs[1], ys[0]), (xs[1], ys[2]), (xs[0], ys[1]), (xs[2], ys[1]),
        )
        for index, (handle, (x, y)) in enumerate(zip(self._resize_handles, points)):
            # 0..3 = coins ; 4 = haut ; 5 = bas ; 6 = gauche ; 7 = droite.
            if index in (4, 5):
                # Poignées Haut/Bas volontairement très lisibles.
                hw = max(22, min(34, max(22, self.width() // 7)))
                hh = max(7, self.HANDLE)
                handle.resize(hw, hh)
                x = max(0, (self.width() - hw) // 2)
            elif index in (6, 7):
                handle.resize(
                    self.HANDLE,
                    max(self.HANDLE, min(16, max(self.HANDLE, self.height() - 2))),
                )
                y = max(0, (self.height() - handle.height()) // 2)
            else:
                handle.resize(self.HANDLE, self.HANDLE)
            handle.move(x, y)
            handle.raise_()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._position_resize_handles()
        self._update_part_selection_frames()
        self._position_vertical_resize_handles()

    def _apply_selection_style(self, selected: bool) -> None:
        self.setStyleSheet(
            "DraggablePreviewField { background: #FFF8E8; border: 2px solid #F0A020; }"
            if selected else
            "DraggablePreviewField { background: transparent; border: 1px solid transparent; }"
        )
        if hasattr(self, "_resize_handles"):
            self._position_resize_handles()
            self._update_part_selection_frames()
            whole_selected = (
                (self.key, "label") in self.dialog._selected_preview_parts
                and (self.key, "data") in self.dialog._selected_preview_parts
            )
            for handle in self._resize_handles:
                handle.setVisible(bool(selected and whole_selected))
            # IMPORTANT : les repères Libellé/Donnée sont dessinés avant,
            # puis les 8 poignées du champ complet sont remontées AU-DESSUS.
            # L'ancienne seconde passe _update_part_selection_frames() les
            # recouvrait, ce qui faisait disparaître surtout Haut/Bas.
            if selected and whole_selected:
                for handle in self._resize_handles:
                    handle.show()
                    handle.raise_()
        self._position_vertical_resize_handles()
        if self.width() < self.MIN_W or self.height() < self.MIN_H:
            self.resize(max(self.MIN_W, self.width()), max(self.MIN_H, self.height()))
        self.update()

    def _part_at(self, point: QPoint) -> str:
        for part in ("label","data"):
            r=self.part_rect(part)
            if r is not None and r.contains(point): return part
        return "data"

    def _part_handle_at(self, point: QPoint):
        for part in ("label","data"):
            if (self.key,part) not in self.dialog._selected_preview_parts: continue
            r=self.part_rect(part)
            if r is None: continue
            if abs(point.x()-r.left())<=8:return part,"left"
            if abs(point.x()-r.right())<=8:return part,"right"
        return None,""

    def _handle_at(self, point: QPoint) -> str:
        """Détecte le redimensionnement du champ complet."""
        if self.key not in self.dialog._selected_preview_keys:
            return ""

        x = point.x()
        y = point.y()
        w = max(1, self.width())
        h = max(1, self.height())

        edge = 10
        corner = 8

        # Zone Haut/Bas centrée correspondant exactement aux barrettes peintes.
        grip_w = max(28, min(44, max(28, w // 6)))
        gx0 = max(0, (w - grip_w) // 2)
        gx1 = min(w - 1, gx0 + grip_w)
        if gx0 <= x <= gx1:
            if y <= edge:
                return "t"
            if y >= h - 1 - edge:
                return "b"

        # Coins : petite zone seulement.
        if x <= corner and y <= corner:
            return "tl"
        if x >= w - 1 - corner and y <= corner:
            return "tr"
        if x <= corner and y >= h - 1 - corner:
            return "bl"
        if x >= w - 1 - corner and y >= h - 1 - corner:
            return "br"

        # IMPORTANT : aucun bord implicite.
        # Hors poignées Haut/Bas visibles et coins, le champ est une zone
        # de déplacement. Cela évite qu'un champ petit/étroit soit presque
        # entièrement interprété comme zone de redimensionnement.
        return ""

    def _cursor_for_point(self, point: QPoint) -> None:
        handle = self._handle_at(point)

        if handle in ("t", "b"):
            self.setCursor(Qt.CursorShape.SizeVerCursor)
            return
        if handle in ("tl", "br"):
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
            return
        if handle in ("tr", "bl"):
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)
            return

        # Redimensionnement horizontal de partie uniquement en sélection fine.
        if self.dialog._selected_part_kind(self.key) != "both":
            part, edge = self._part_handle_at(point)
            if part and edge in ("left", "right"):
                self.setCursor(Qt.CursorShape.SizeHorCursor)
                return

        if self.key in self.dialog._selected_preview_keys:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)


    def paintEvent(self, event) -> None:
        # Le contour normal reste peint par Qt.
        super().paintEvent(event)

        # 23.8.6.8 — Les poignées Haut/Bas sont DESSINÉES directement par
        # le champ lui-même. Elles ne peuvent donc plus être masquées par
        # QLabel, cadres de sélection ou ordre d'empilement Qt.
        whole_selected = (
            (self.key, "label") in self.dialog._selected_preview_parts
            and (self.key, "data") in self.dialog._selected_preview_parts
        )
        if not whole_selected:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setPen(QPen(QColor("#C77C00"), 1))
        painter.setBrush(QColor("#F0A020"))

        grip_w = max(24, min(38, max(24, self.width() // 7)))
        grip_h = 7
        x = max(0, (self.width() - grip_w) // 2)

        # Poignée supérieure et inférieure, volontairement à l'intérieur du
        # rectangle du champ pour éviter tout clipping par le parent.
        painter.drawRect(x, 0, grip_w, grip_h)
        painter.drawRect(x, max(0, self.height() - grip_h - 1), grip_w, grip_h)
        painter.end()


    def mousePressEvent(self, event) -> None:
        if event.button()==Qt.MouseButton.RightButton:
            self.dialog._set_free_group_selection([], False)
            part=self._part_at(event.position().toPoint())
            if (self.key,part) not in self.dialog._selected_preview_parts:
                self.dialog._set_preview_part_selection([(self.key,part)],False)
            self.dialog._show_preview_context_menu(event.globalPosition().toPoint())
            event.accept();return
        if event.button()==Qt.MouseButton.LeftButton:
            # Un champ ne sélectionne JAMAIS le cadre situé derrière lui.
            # Sans Ctrl, un clic sur un champ abandonne la sélection de cadres.
            # Avec Ctrl, champs et cadres peuvent désormais appartenir à la même
            # sélection combinée.
            additive=bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)

            # 23.9.3.2.2 — un champ déjà sélectionné peut servir de poignée
            # de déplacement à une sélection MIXTE champs + cadres.
            # Ne pas effacer les cadres au simple MousePress dans ce cas.
            # En revanche, un clic simple sur un champ NON sélectionné conserve
            # le comportement classique : nouvelle sélection, cadres abandonnés.
            field_already_selected = self.key in self.dialog._selected_preview_keys
            if not additive and not field_already_selected:
                self.dialog._set_free_group_selection([], False)

            point=event.position().toPoint(); part=self._part_at(point)

            # Ctrl+clic après un lasso / une sélection de champs complets :
            # ajouter ou retirer le CHAMP COMPLET, pas uniquement la Donnée.
            if additive:
                # 23.9.3.2 — Ctrl+clic est un vrai interrupteur de CHAMP COMPLET.
                # Il doit permettre aussi bien d'ajouter que de retirer un champ
                # d'une sélection mixte champs + cadres.
                keys = set(self.dialog._selected_preview_keys)
                if self.key in keys:
                    keys.remove(self.key)
                else:
                    keys.add(self.key)
                self.dialog._set_preview_selection(keys)
                self.dialog._whole_field_multi_selection = bool(keys)
                self.dialog._refresh_free_group_selection()
                event.accept()
                return

            # 23.7.6.5 — clic/prise de poignée sur UNE PARTIE déjà comprise
            # dans une sélection multiple : conserver toute la sélection.
            # Sinon la partie saisie pour étirer/déplacer le groupe était seule
            # re-sélectionnée et sortait immédiatement du lot.
            current_item = (self.key, part)
            preserve_multi = (
                not additive
                and current_item in self.dialog._selected_preview_parts
                and len(self.dialog._selected_preview_parts) > 1
            )
            # Si Ctrl a déjà ajouté le champ complet ci-dessus, preserve_multi
            # est vrai et aucune partie n'est re-sélectionnée isolément.
            if not preserve_multi:
                self.dialog._set_preview_part_selection(
                    [current_item], additive
                )
            elif len(self.dialog._selected_preview_keys) >= 2:
                # Une sélection constituée par Ctrl+clic de plusieurs champs
                # reste en mode "champs complets" lors de la prise de déplacement.
                if all(
                    self.dialog._selected_part_kind(k) == "both"
                    for k in self.dialog._selected_preview_keys
                ):
                    self.dialog._whole_field_multi_selection = True

            self.setFocus(Qt.FocusReason.MouseFocusReason); self.raise_()
            self._press_global=event.globalPosition().toPoint()
            self._start_geom=QRect(self.geometry())

            # 23.9.3.2 — la souris et les flèches utilisent exactement la même
            # sélection. Si des cadres sont sélectionnés avec les champs, prendre
            # un champ à la souris doit déplacer tout l'ensemble.
            self._drag_start_group_geometries = {
                name: QRect(group.geometry())
                for name in self.dialog._selected_free_groups
                for group in [self.dialog._free_group_widget(name)]
                if group is not None
            }

            # Sécurité forte : dès qu'au moins deux champs ont été constitués
            # par Ctrl+clic, reconstruire explicitement leurs deux parties avant
            # de décider entre déplacement et redimensionnement.
            if (
                getattr(self.dialog, "_whole_field_multi_selection", False)
                and len(self.dialog._selected_preview_keys) >= 2
            ):
                self.dialog._set_preview_selection(
                    set(self.dialog._selected_preview_keys)
                )

            # 23.8.6.9.2 — hiérarchie souris simplifiée et déterministe :
            # 1. poignées Haut/Bas/coins = redimensionnement du champ complet ;
            # 2. poignées horizontales Libellé/Donnée = redimensionnement de partie ;
            # 3. partout ailleurs = déplacement du ou des champs sélectionnés.
            field_selected_here = self.key in self.dialog._selected_preview_keys
            whole_handle = self._handle_at(point) if field_selected_here else ""
            vertical_handle = whole_handle in ("t", "b", "tl", "tr", "bl", "br")

            self._part_resize_part, self._part_resize_edge = None, ""
            self._drag_start_geometries = {}

            if field_selected_here and vertical_handle:
                self._resizing = True
                self._dragging = False
                self._resize_corner = whole_handle
                selected_fields = self.dialog._selected_fields() or [self]
                self._drag_start_geometries = {
                    f.key: QRect(f.geometry()) for f in selected_fields
                }
                self._drag_start_positions = {
                    f.key: QPoint(f.x(), f.y()) for f in selected_fields
                }
            else:
                # Les poignées de partie ne sont actives que si cette partie
                # est explicitement sélectionnée seule. Une sélection de champs
                # complets ne doit jamais être interceptée ici.
                if self.dialog._selected_part_kind(self.key) != "both":
                    self._part_resize_part, self._part_resize_edge = (
                        self._part_handle_at(point)
                    )

                if self._part_resize_part:
                    self._resizing = True
                    self._dragging = False
                    self._resize_corner = ""
                    self._part_resize_start = QRect(
                        self.dialog._field_part_sheet_rect(
                            self, self._part_resize_part
                        )
                    )
                    self._part_resize_starts = {
                        field.key: QRect(rect)
                        for field, rect in self.dialog._selected_parts_of_kind(
                            self._part_resize_part
                        )
                    }
                else:
                    self._resizing = False
                    self._dragging = True
                    self._resize_corner = ""
                    self._drag_mode = "fields"

                    # Si le clic simple a sélectionné une seule partie, le champ
                    # lui-même reste malgré tout l'objet déplacé. Les parties ne
                    # se déplacent jamais séparément par glisser-déposer.
                    selected_fields = self.dialog._selected_fields()
                    if self not in selected_fields:
                        self.dialog._set_preview_selection([self.key])
                        selected_fields = [self]

                    self._drag_start_positions = {
                        f.key: QPoint(f.x(), f.y()) for f in selected_fields
                    }
                    self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept();return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if not self._dragging and not self._resizing:
            self._cursor_for_point(event.position().toPoint())

        delta = event.globalPosition().toPoint() - self._press_global
        # Le déplacement manuel est au pixel. La grille n'est utilisée que
        # lorsque l'utilisateur demande explicitement un alignement sur grille.
        snap = 1

        if self._resizing and getattr(self,"_part_resize_part",""):
            changes = {}
            starts = getattr(self, "_part_resize_starts", {})
            if not starts:
                starts = {self.key: QRect(self._part_resize_start)}

            for key, start_rect in starts.items():
                nr = QRect(start_rect)
                if self._part_resize_edge=="left":
                    nr.setLeft(
                        min(start_rect.right()-20, start_rect.left()+delta.x())
                    )
                else:
                    nr.setRight(
                        max(start_rect.left()+20, start_rect.right()+delta.x())
                    )
                changes[(key, self._part_resize_part)] = nr

            self.dialog._apply_part_rect_batch(changes)
            event.accept();return

        force_whole_multi = bool(
            self._dragging
            and len(self.dialog._selected_preview_keys) >= 2
            and all(
                self.dialog._selected_part_kind(k) == "both"
                for k in self.dialog._selected_preview_keys
            )
        )

        if (
            self._dragging
            and getattr(self,"_drag_mode","")=="parts"
            and not force_whole_multi
        ):
            changes = {}
            drag_part = getattr(self, "_drag_part", "label")
            for key,start_rect in self._drag_start_part_rects.items():
                nr=QRect(start_rect)
                nr.translate(delta.x(),delta.y())
                changes[(key, drag_part)] = nr
            self.dialog._apply_part_rect_batch(changes)
            event.accept();return

        if force_whole_multi and getattr(self, "_drag_mode", "") != "fields":
            self._drag_mode = "fields"
            if not getattr(self, "_drag_start_positions", None):
                self._drag_start_positions = {
                    f.key: QPoint(f.x(), f.y())
                    for f in self.dialog._selected_fields()
                }

        if self._resizing:
            dx, dy = delta.x(), delta.y()

            selected_geoms = getattr(self, "_drag_start_geometries", {})
            if (
                selected_geoms
                and len(selected_geoms) >= 2
                and all(
                    self.dialog._selected_part_kind(k) == "both"
                    for k in self.dialog._selected_preview_keys
                )
            ):
                # Redimensionnement collectif : toutes les hauteurs/largeurs
                # suivent la même variation, comme avec les poignées horizontales.
                for field in self.dialog._selected_fields():
                    g = QRect(selected_geoms.get(field.key, field.geometry()))
                    x, y, w, h = g.x(), g.y(), g.width(), g.height()

                    if "l" in self._resize_corner:
                        new_w = max(field.MIN_W, g.width() - dx)
                        x = g.x() + (g.width() - new_w)
                        w = new_w
                    elif "r" in self._resize_corner:
                        w = max(field.MIN_W, g.width() + dx)

                    if "t" in self._resize_corner:
                        new_h = max(field.MIN_H, g.height() - dy)
                        y = g.y() + (g.height() - new_h)
                        h = new_h
                    elif "b" in self._resize_corner:
                        h = max(field.MIN_H, g.height() + dy)

                    field.setGeometry(x, y, w, h)
                    self.dialog._store_field_part_geometry(field)
                    field.raise_()

                event.accept()
                return

            g = QRect(
                getattr(self, "_drag_start_geometries", {}).get(
                    self.key, self._start_geom
                )
            )
            x = g.x()
            y = g.y()
            w = g.width()
            h = g.height()

            # Côtés : une seule dimension. Angles : les deux dimensions.
            if "l" in self._resize_corner:
                new_w = max(self.MIN_W, g.width() - dx)
                x = g.x() + (g.width() - new_w)
                w = new_w
            elif "r" in self._resize_corner:
                w = max(self.MIN_W, g.width() + dx)

            if "t" in self._resize_corner:
                new_h = max(self.MIN_H, g.height() - dy)
                y = g.y() + (g.height() - new_h)
                h = new_h
            elif "b" in self._resize_corner:
                h = max(self.MIN_H, g.height() + dy)

            # Redimensionnement au pixel ; la collision est gérée ensuite.
            x = max(0, int(x))
            y = max(0, int(y))
            w = max(self.MIN_W, int(w))
            h = max(self.MIN_H, int(h))

            parent = self.parentWidget()
            if parent is not None:
                # Ne jamais sortir du canevas.
                if x + w > parent.width():
                    if "l" in self._resize_corner:
                        x = max(0, parent.width() - w)
                    else:
                        w = max(self.MIN_W, parent.width() - x)
                if y + h > parent.height():
                    if "t" in self._resize_corner:
                        y = max(0, parent.height() - h)
                    else:
                        h = max(self.MIN_H, parent.height() - y)

            proposed = QRect(x, y, w, h)

            # Redimensionnement manuel : la géométrie choisie par l'utilisateur
            # est l'autorité. Aucune ancienne règle de collision ne doit annuler
            # une variation de hauteur.
            resolved = proposed
            if resolved != self.geometry():
                self.setGeometry(resolved)
                scale = self.dialog._preview_scale()
                self.dialog._visual_positions[self.key] = (
                    round(resolved.x() / scale), round(resolved.y() / scale)
                )
                self.dialog._visual_sizes[self.key] = (
                    round(resolved.width() / scale), round(resolved.height() / scale)
                )
                self.dialog._store_field_part_geometry(self)
                self.updateGeometry()
                self.update()
            event.accept()
            return

        if self._dragging and getattr(self,"_drag_mode","fields")=="fields" and (event.buttons() & Qt.MouseButton.LeftButton):
            dx = round(delta.x() / snap) * snap
            dy = round(delta.y() / snap) * snap
            proposals = {}
            fields = self.dialog._selected_fields()
            for field in fields:
                start = self._drag_start_positions.get(field.key, QPoint(field.x(), field.y()))
                x = max(0, start.x() + dx)
                y = max(0, start.y() + dy)
                parent = field.parentWidget()
                if parent:
                    x = min(x, max(0, parent.width() - field.width()))
                    y = min(y, max(0, parent.height() - field.height()))
                proposals[field.key] = QRect(x, y, field.width(), field.height())

            if len(fields) == 1:
                # 018.4.4.1.5.22.8 — SURVOL LIBRE :
                # pendant le trajet le champ suit exactement la souris et peut
                # passer au-dessus des autres. La collision n'est contrôlée
                # qu'au relâchement.
                field = fields[0]
                rect = proposals[field.key]
                field.move(rect.topLeft())
                field.raise_()
                scale = self.dialog._preview_scale()
                self.dialog._visual_positions[field.key] = (
                    round(rect.x() / scale), round(rect.y() / scale)
                )
            else:
                # Plusieurs champs sélectionnés : déplacement manuel libre,
                # exactement comme avec les flèches. Les anciennes règles de
                # collision ne doivent plus bloquer un groupe au sein d'un cadre.
                for field in fields:
                    rect = proposals[field.key]
                    field.move(rect.topLeft())
                    field.raise_()
                    scale = self.dialog._preview_scale()
                    self.dialog._visual_positions[field.key] = (
                        round(rect.x() / scale), round(rect.y() / scale)
                    )
            # Sélection mixte : les cadres suivent le même delta souris que
            # les champs, sans modifier la sélection.
            for name, start_rect in getattr(
                self, "_drag_start_group_geometries", {}
            ).items():
                group = self.dialog._free_group_widget(name)
                if group is not None:
                    group.move(
                        max(0, start_rect.x() + delta.x()),
                        max(0, start_rect.y() + delta.y()),
                    )
                    group.lower()
                    self.dialog._position_group_resize_handles(name)
            self.dialog._raise_absolute_fields()
            self.dialog._refresh_free_group_selection()
            self.dialog._resize_free_group_host()

            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button()==Qt.MouseButton.LeftButton and (self._dragging or self._resizing):
            # 23.9.3.2 — enregistrer aussi la nouvelle position des cadres
            # lorsque le déplacement mixte a été initié depuis un champ.
            if self._dragging and getattr(self, "_drag_start_group_geometries", {}):
                for name in self._drag_start_group_geometries:
                    self.dialog._persist_free_group_geometry(name)
                    self.dialog._position_group_resize_handles(name)
                self.dialog._refresh_free_group_selection()
                self.dialog._resize_free_group_host()
            self._drag_start_group_geometries = {}

            part_resize=bool(getattr(self,"_part_resize_part",""))
            part_drag=self._dragging and getattr(self,"_drag_mode","")=="parts"
            if part_resize or part_drag:
                self._dragging=False;self._resizing=False
                self._part_resize_part="";self._part_resize_edge=""
                self._part_resize_starts={}
                self._drag_mode="";self._drag_part=""
                self.setCursor(Qt.CursorShape.OpenHandCursor)
                for f in self.dialog._selected_fields():
                    self.dialog._store_field_part_geometry(f)
                self.dialog._record_history_state();event.accept();return
            multi_whole = (
                getattr(self, "_drag_mode", "") == "fields"
                and len(self.dialog._selected_fields()) > 1
                and all(
                    self.dialog._selected_part_kind(k) == "both"
                    for k in self.dialog._selected_preview_keys
                )
            )
            self._dragging=False;self._resizing=False;self._resize_corner=""
            scale=self.dialog._preview_scale()
            if multi_whole:
                for field in self.dialog._selected_fields():
                    self.dialog._visual_positions[field.key] = (
                        round(field.x()/scale), round(field.y()/scale)
                    )
                    self.dialog._visual_sizes[field.key] = (
                        round(field.width()/scale), round(field.height()/scale)
                    )
            else:
                current=QRect(self.geometry())
                resolved=QRect(self._start_geom) if not self.dialog._preview_field_rect_valid(self,current) else current
                self.setGeometry(resolved)
                self.dialog._visual_positions[self.key]=(round(self.x()/scale),round(self.y()/scale))
                self.dialog._visual_sizes[self.key]=(round(self.width()/scale),round(self.height()/scale))
            self._drag_mode=""
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            self.dialog._record_history_state();event.accept();return
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event) -> None:
        if (
            self.key not in self.dialog._selected_preview_keys
            or len(self.dialog._selected_preview_keys) == 1
        ):
            self.dialog._select_preview_field(self.key, False)
        self.dialog._show_preview_context_menu(event.globalPos())
        event.accept()

    def keyPressEvent(self, event) -> None:
        if (
            event.key() == Qt.Key.Key_C
            and event.modifiers() & Qt.KeyboardModifier.ControlModifier
            and self.dialog._copy_selected_field_for_duplication()
        ):
            event.accept()
            return
        delta = {
            Qt.Key.Key_Left: (-1, 0),
            Qt.Key.Key_Right: (1, 0),
            Qt.Key.Key_Up: (0, -1),
            Qt.Key.Key_Down: (0, 1),
        }.get(event.key())
        if delta:
            step = 10 if (
                event.modifiers() & Qt.KeyboardModifier.ShiftModifier
            ) else 1
            self.dialog._nudge_selected_preview_fields(
                delta[0] * step, delta[1] * step
            )
            event.accept()
            return
        super().keyPressEvent(event)


class PositionSpinBox(QSpinBox):
    """Nombre modifiable volontairement, sans roulette ni sélection bleue automatique."""
    def wheelEvent(self, event):
        event.ignore()

    def focusInEvent(self, event):
        super().focusInEvent(event)
        QTimer.singleShot(0, self._clear_selection)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        QTimer.singleShot(0, self._clear_selection)

    def _clear_selection(self):
        # Le QTimer peut se déclencher pendant la fermeture de l'Atelier, après
        # destruction du widget C++ par Qt. Dans ce cas, la désélection n'a
        # simplement plus rien à faire.
        try:
            line = self.lineEdit()
            if line is not None:
                line.deselect()
        except RuntimeError:
            return


class ModelDialog(QDialog):
    """018.4.4.1.2.9 — Atelier Modèles avec Défaire / Refaire."""

    def __init__(self, db_path, collection: dict, parent=None, language: str = "fr", workshop_mode: str = "collection") -> None:
        super().__init__(parent)
        self.language = language or "fr"
        self.workshop_mode = str(workshop_mode or "collection")
        self.collection = dict(collection)
        self.db_path = Path(db_path)
        self.manager = ModelManager(db_path)
        self.collection_id = int(collection["id"])

        self._checks: dict[str, QCheckBox] = {}
        self._labels: dict[str, QLineEdit] = {}
        self._blocks: dict[str, QComboBox] = {}
        self._positions: dict[str, QSpinBox] = {}
        self._tab_positions: dict[str, QSpinBox] = {}
        self._rows: dict[str, QWidget] = {}
        self._editor_groups: dict[str, QGroupBox] = {}
        self._editor_layouts: dict[str, QVBoxLayout] = {}
        self._preview_groups: dict[str, QGroupBox] = {}
        self._preview_canvases: dict[str, MagneticCanvas] = {}
        # 018.4.4.1.5.22.8 — déplacement libre des blocs.
        self._free_group_names = (
            "Bandeau", "Identification", "Photo",
            "Localisation", "Aspect", "Acquisition", "Collection"
        )
        self._free_group_default_geometries = {}
        self._free_group_drag_name = None
        self._free_group_drag_offset = None
        self._free_group_drag_press_global = None
        self._free_group_drag_started = False
        self._free_group_drag_start_geom = None
        self._selected_free_groups: set[str] = set()
        self._free_group_drag_start_geometries: dict[str, QRect] = {}
        self._group_selection_frames: dict[str, QFrame] = {}
        self._group_title_handles: dict[str, QFrame] = {}
        self._group_lasso_origin: QPoint | None = None
        self._group_rubber_band = None

        # 018.4.4.1.5.22.8 — redimensionnement des blocs, Atelier uniquement.
        self._free_group_resize_name = None
        self._free_group_resize_edge = ""
        self._free_group_resize_press_global = None
        self._free_group_resize_start_geom = None
        self._free_group_resize_handles = {}

        self._preview_fields: dict[str, DraggablePreviewField] = {}
        self._selected_preview_key: str | None = None
        self._selected_preview_keys: set[str] = set()
        self._selected_preview_parts: set[tuple[str, str]] = set()
        self._visual_positions: dict[str, tuple[int, int]] = {}
        self._visual_sizes: dict[str, tuple[int, int]] = {}
        self._updating_positions = False

        # 11.7.70.26.32 — placement explicite depuis la palette.
        # Un champ nouvellement coché devient disponible au glisser-déposer ;
        # il n'est plus injecté automatiquement en bas de la fiche.
        self._pending_palette_placement: set[str] = set()
        self._palette_drag_press: dict[str, QPoint] = {}

        # 018.4.4.1.2.9 — historique local du travail dans l'Atelier Modèles.
        self._undo_stack: list[dict] = []
        self._redo_stack: list[dict] = []
        # 11.7.57 — champs créés provisoirement par la correspondance d’un
        # modèle de bibliothèque. Ils ne deviennent définitifs qu’avec
        # « Enregistrer ». « Ne pas enregistrer » doit les retirer de la base.
        self._library_import_created_keys: set[str] = set()
        self._history_guard = False

        # 23.9.3.6.8 — le presse-papiers des champs de l'Atelier passe par
        # le presse-papiers Windows. Il survit donc à la fermeture de l'Atelier
        # source et permet un collage dans l'Atelier d'une autre collection.
        self._atelier_field_clipboard_key: str | None = None  # compatibilité ancien mécanisme
        self._atelier_paste_point: QPoint | None = None

        self.setWindowTitle(f"{self._t('Modèle de fiche')} — {collection_display_name(collection, self.language)}")
        # La fenêtre doit rester dans la zone de travail (hors barre des tâches).
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        available = screen.availableGeometry() if screen else None
        self.resize(min(1450, available.width() - 24) if available else 1450,
                    min(820, available.height() - 40) if available else 780)
        self.setMinimumSize(1050, 620)

        # 1.0.223 — repère visuel immédiat : atelier de collection (vert doux)
        # et atelier de modèle maître (bleu doux) utilisent le même moteur,
        # mais ne doivent jamais pouvoir être confondus.
        if self.workshop_mode in ("master", "template"):
            self.setStyleSheet("QDialog { background-color: #EAF1F8; }")
        else:
            self.setStyleSheet("QDialog { background-color: #EEF5F1; }")

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 7, 12, 7)
        root.setSpacing(5)

        title_prefix = self._t("Atelier - Modèles") if self.workshop_mode != "master" else self._t("Atelier - Modèle maître")
        title = QLabel(f"{title_prefix} — {collection_display_name(collection, self.language)}")
        self.atelier_title_label = title
        font = title.font()
        font.setPointSize(font.pointSize() + 5)
        font.setBold(True)
        title.setFont(font)
        title.setStyleSheet("color: #163A70;")
        root.addWidget(title)

        self._active_library_model_name = str(collection.get("name") or "Modèle de fiche")
        # Le titre unique remplace les deux lignes redondantes de l'ancien atelier.
        self.model_name_label = QLabel()
        self.model_name_label.hide()
        self._refresh_active_model_name()

        toolbar = QHBoxLayout()

        self.undo_btn = QPushButton("↶  " + self._t("Défaire"))
        self.redo_btn = QPushButton("↷  " + self._t("Refaire"))
        # MM3 018.4.4.1.5.23.9.3.6.6 — repérage visuel Défaire / Refaire.
        undo_redo_style = (
            "QPushButton { background-color: #FFB3B3; }"
            "QPushButton:disabled { background-color: #FFD6D6; color: #777777; }"
        )
        self.undo_btn.setStyleSheet(undo_redo_style)
        self.redo_btn.setStyleSheet(undo_redo_style)
        self.undo_btn.setToolTip(self._t("Annuler la dernière modification"))
        self.redo_btn.setToolTip(self._t("Rétablir la dernière modification annulée"))
        self.undo_btn.clicked.connect(self._undo)
        self.redo_btn.clicked.connect(self._redo)
        self.undo_btn.setEnabled(False)
        self.redo_btn.setEnabled(False)

        all_btn = QPushButton(self._t("Tout sélectionner").replace(" ", "\n", 1))
        tab_default_btn = QPushButton(self._t("Tabulation = ordre visuel").replace(" = ", " =\n"))
        tab_default_btn.setToolTip(self._t("Rétablir l'ordre de tabulation suivant l'ordre des champs dans la fiche"))
        all_btn.clicked.connect(self._select_all_present_fields)
        tab_default_btn.clicked.connect(self._reset_tab_to_visual)
        toolbar.addWidget(self.undo_btn)
        toolbar.addWidget(self.redo_btn)
        self.detach_palette_btn = QPushButton("⇱ " + self._t("Détacher la palette des champs"))
        self.detach_palette_btn.setToolTip(
            self._t("Place la liste des champs dans une palette flottante et libère la largeur pour la fiche.")
        )
        self.detach_palette_btn.clicked.connect(self._toggle_fields_palette)
        toolbar.addSpacing(12)
        toolbar.addWidget(self.detach_palette_btn)
        self.add_field_btn = QPushButton("＋ " + self._t("Ajouter un champ").replace(" ", "\n", 1))
        self.add_field_btn.setToolTip(self._t("Créer un nouveau champ propre à cette collection."))
        self.add_field_btn.clicked.connect(self._create_custom_field)
        toolbar.addWidget(self.add_field_btn)
        self.add_group_btn = QPushButton("＋ " + self._t("Ajouter un cadre").replace(" ", "\n", 1))
        self.add_group_btn.setToolTip(self._t("Créer un nouveau cadre graphique libre dans la fiche."))
        self.add_group_btn.clicked.connect(self._create_custom_group)
        toolbar.addWidget(self.add_group_btn)
        self.add_photo_frame_btn = QPushButton("＋ " + self._t("Ajouter un cadre Photo").replace(" Photo", "\nPhoto"))
        self.add_photo_frame_btn.setToolTip(
            self._t("Créer un cadre Photo supplémentaire, indépendant du cadre Photo principal.")
        )
        self.add_photo_frame_btn.clicked.connect(self._create_custom_photo_frame)
        toolbar.addWidget(self.add_photo_frame_btn)
        self.add_large_photo_frame_btn = QPushButton("＋ " + self._t("Grand cadre Photo").replace(" Photo", "\nPhoto"))
        self.add_large_photo_frame_btn.setToolTip(
            self._t("Créer un grand cadre Photo redimensionnable (image JPEG de 600 × 400 pixels maximum).")
        )
        self.add_large_photo_frame_btn.clicked.connect(self._create_large_photo_frame)
        toolbar.addWidget(self.add_large_photo_frame_btn)
        toolbar.addSpacing(12)
        toolbar.addWidget(all_btn)
        toolbar.addSpacing(8)
        toolbar.addWidget(tab_default_btn)
        toolbar.addSpacing(12)

        self.sheet_color_btn = QPushButton("🎨 " + self._t("Couleur de la fiche…").replace(" de ", "\nde ", 1))
        self.sheet_color_btn.setToolTip(self._t("Choisir la couleur de fond propre à cette collection."))
        self.sheet_color_btn.clicked.connect(self._choose_sheet_background)
        toolbar.addWidget(self.sheet_color_btn)

        self.default_style_btn = QPushButton(self._t("Style par défaut").replace(" ", "\n", 1))
        self.default_style_btn.setToolTip(self._t("Rétablir la couleur de fond MM3 par défaut."))
        self.default_style_btn.clicked.connect(self._reset_sheet_style)
        toolbar.addWidget(self.default_style_btn)

        # Bandeau lisible : autoriser naturellement deux lignes.
        for button in (
            self.detach_palette_btn,
            self.add_field_btn,
            self.add_group_btn,
            self.add_photo_frame_btn,
            self.add_large_photo_frame_btn,
            all_btn,
            tab_default_btn,
            self.sheet_color_btn,
            self.default_style_btn,
        ):
            # Deux lignes visibles, même géométrie quelle que soit la langue.
            button.setFixedHeight(52)

        # Les boutons d'action restent plus petits et centrés verticalement.
        self.undo_btn.setFixedHeight(40)
        self.redo_btn.setFixedHeight(40)
        toolbar.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        toolbar.addStretch(1)
        root.addLayout(toolbar)

        self._custom_field_defs = self.manager.custom_field_map(self.collection_id)
        # 23.9.3.6.0 — relations propres à cette collection.
        self._field_masters: set[str] = set(self.manager.field_masters(self.collection_id))
        self._field_links: dict[str, str] = dict(self.manager.field_links(self.collection_id))
        self._last_group_context = None
        visible = self.manager.visible_fields(self.collection_id)
        custom_labels = self.manager.custom_labels(self.collection_id)
        placement = self.manager.field_placement(self.collection_id)
        self._visual_positions = self.manager.visual_positions(self.collection_id, placement)
        self._visual_sizes = self.manager.visual_sizes(self.collection_id)
        self._sheet_background = self.manager.sheet_background(self.collection_id)
        self._default_sheet_background = "#EEF5F1"
        self._field_styles = self.manager.field_styles(self.collection_id)
        self._field_styles = self._normalized_field_styles(self._field_styles) if hasattr(self, "_normalized_field_styles") else self._field_styles
        self._group_styles = self.manager.group_styles(self.collection_id)

        # 23.7.7.3.1 — appliquer les suppressions de cadres historiques
        # uniquement maintenant, une fois _group_styles réellement chargé.
        self._free_group_names = tuple(
            name for name in self._free_group_names
            if not bool(self._group_styles.get(name, {}).get("frame_deleted"))
        )

        # 23.6.2 — mémoriser les groupes utilisateur, mais ne surtout pas les
        # introduire dans la grille initiale : la 23.5.3 doit d'abord construire
        # exactement sa géométrie validée.
        self._custom_group_names = [
            str(name) for name, style in self._group_styles.items()
            if isinstance(style, dict)
            and bool(style.get("custom_group") or style.get("custom_photo"))
        ]
        self._custom_groups_restored = False

        # 23.7.0 — architecture simplifiée :
        # les groupes ne pilotent plus les champs. Les champs vivent sur la feuille
        # elle-même avec des coordonnées X/Y absolues.
        layout_meta = self._group_styles.get("__mm3_layout__", {})

        # Migration douce des Collections vierges créées juste avant 23.8.7.2.1 :
        # si le Bandeau n'a aucune géométrie propre et que tous les anciens
        # cadres sont supprimés, il ne doit pas s'étirer sur toute la feuille.
        standard_deleted = all(
            bool(self._group_styles.get(name, {}).get("frame_deleted"))
            for name in (
                "Identification", "Photo", "Localisation",
                "Aspect", "Acquisition", "Collection",
            )
        )
        band_style = dict(self._group_styles.get("Bandeau", {}))
        band_geom = band_style.get("geometry")
        if standard_deleted and not (
            isinstance(band_geom, dict)
            and {"x", "y", "w", "h"} <= set(band_geom)
        ):
            layout_meta = dict(layout_meta) if isinstance(layout_meta, dict) else {}
            layout_meta["model_kind"] = "blank"
            layout_meta["field_space"] = "sheet_absolute_v1"
            self._group_styles["__mm3_layout__"] = layout_meta
            band_style["geometry_space"] = "atelier_px"
            band_style["geometry"] = {"x": 12, "y": 12, "w": 900, "h": 122}
            self._group_styles["Bandeau"] = band_style

        # Migration des Collections vierges 7.1/7.2 : si N° / Etat sont encore
        # collés en haut, les replacer sous la barre de titre sans toucher à une
        # position que l'utilisateur aurait déjà personnalisée.
        layout_meta_check = self._group_styles.get("__mm3_layout__", {})
        is_blank_layout = bool(
            isinstance(layout_meta_check, dict)
            and str(layout_meta_check.get("model_kind", "")).lower() == "blank"
        )
        if is_blank_layout:
            number_pos = self._visual_positions.get("record_number", (12, 12))
            state_pos = self._visual_positions.get("record_state", (570, 10))
            if int(number_pos[1]) < 32:
                self._visual_positions["record_number"] = (32, 82)
            if int(state_pos[1]) < 32:
                self._visual_positions["record_state"] = (430, 82)

            band_style = dict(self._group_styles.get("Bandeau", {}))
            geom = dict(band_style.get("geometry") or {})
            if geom and int(geom.get("h", 0) or 0) < 122:
                geom["h"] = 122
                band_style["geometry"] = geom
                band_style["geometry_space"] = "atelier_px"
                self._group_styles["Bandeau"] = band_style

        self._absolute_field_mode = True
        self._absolute_fields_ready = False
        self._stored_field_space = (
            str(layout_meta.get("field_space", ""))
            if isinstance(layout_meta, dict) else ""
        )

        # Ordre visuel par défaut : Bandeau, puis blocs de la fiche et positions.
        visual_default = self._visual_order_from_placement(placement)
        stored_tab_order = self.manager.tab_order(self.collection_id, visual_default)
        initial_tab_numbers = {key: index + 1 for index, key in enumerate(stored_tab_order)}

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self._model_splitter = splitter
        self._fields_palette_dialog = None

        # ------------------------------------------------------------------
        # EDITEUR COMPACT A GAUCHE
        # ------------------------------------------------------------------
        editor_scroll = QScrollArea()
        self._editor_scroll = editor_scroll
        self._editor_scroll = editor_scroll
        self._fields_palette_widget = editor_scroll
        editor_scroll.setWidgetResizable(True)
        editor_scroll.setMinimumWidth(205)
        editor_scroll.setMaximumWidth(285)
        editor_host = QWidget()
        editor_root = QVBoxLayout(editor_host)
        editor_root.setContentsMargins(4, 2, 4, 2)
        editor_root.setSpacing(6)

        headings = QWidget()
        hg = QGridLayout(headings)
        hg.setContentsMargins(8, 3, 8, 3)
        hg.setHorizontalSpacing(7)
        header_specs = ((self._t("Champ (glisser pour classer)"), 0),)
        for text, col in header_specs:
            lab = QLabel(text)
            f = lab.font()
            f.setBold(True)
            lab.setFont(f)
            if text == "/":
                lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
            hg.addWidget(lab, 0, col)
        hg.setColumnStretch(0, 1)
        editor_root.addWidget(headings)

        # 23.7.2 — palette plate : plus de familles/groupes graphiques.
        # Seuls le champ (case visible) et son ordre de tabulation restent affichés.
        self._relation_markers = {}
        fields_list = QWidget()
        fields_list.setAcceptDrops(True)
        fields_list.setProperty("_mm3_palette_order_host", True)
        fields_list.installEventFilter(self)
        fields_layout = QVBoxLayout(fields_list)
        fields_layout.setContentsMargins(2, 2, 2, 2)
        fields_layout.setSpacing(1)
        self._editor_groups = {"__all__": fields_list}
        self._editor_layouts = {"__all__": fields_layout}
        editor_root.addWidget(fields_list)
        editor_root.addStretch(1)

        # 23.8.7.2.1 — une Collection vierge possède SON catalogue :
        # N° de fiche, Etat de la fiche et les seuls champs créés par l'utilisateur.
        # Le marqueur reste vrai après l'ajout de 1, 10 ou 100 champs.
        layout_meta_for_palette = self._group_styles.get("__mm3_layout__", {})
        imported_palette_keys = (
            set(str(key) for key in layout_meta_for_palette.get("import_palette_keys", []))
            if isinstance(layout_meta_for_palette, dict)
            and isinstance(layout_meta_for_palette.get("import_palette_keys"), list)
            else None
        )
        marked_blank_model = bool(
            isinstance(layout_meta_for_palette, dict)
            and str(layout_meta_for_palette.get("model_kind", "")).lower() == "blank"
        )

        # Compatibilité avec les Collections vierges déjà créées par les deux
        # Cores précédents, qui ne possédaient pas encore le marqueur persistant.
        historical_keys = {
            str(key)
            for _group_name, group_keys in GROUPS
            for key in group_keys
            if str(key) not in {"record_number", "record_state", "photo_data"}
        }
        no_historical_field_visible = not bool(
            historical_keys.intersection(set(visible))
        )
        blank_model = marked_blank_model or no_historical_field_visible

        # Les modèles spécialisés modernes ont leur propre catalogue de champs.
        # Les anciens champs historiques (notamment Minéraux) ne doivent même
        # pas apparaître grisés dans leur palette. Ils restent disponibles dans
        # le catalogue global pour les anciennes collections, mais sont masqués
        # ici dès lors qu'ils ne font pas partie du modèle courant.
        model_kind_for_palette = str(layout_meta_for_palette.get("model_kind", "")).lower() if isinstance(layout_meta_for_palette, dict) else ""
        clean_specialized_model = model_kind_for_palette in {"sands", "fossils", "stamps", "postcards", "coins", "objects", "books", "labels"}

        for original_group, keys in GROUPS:
            for idx, key in enumerate(keys):
                spec = self._field_spec(key)
                if spec is None:
                    continue
                if imported_palette_keys is not None and key not in imported_palette_keys:
                    continue
                if blank_model and key not in {"record_number", "record_state"}:
                    # Aucun champ du catalogue historique dans une Collection vierge.
                    # Les champs personnalisés sont ajoutés séparément juste après.
                    continue
                # 11.4.21 — dans les modèles spécialisés, le premier cadre Photo
                # n'est plus construit comme un champ historique ordinaire. Une ligne
                # dédiée, identique aux autres cadres Photo, est créée plus bas.
                if clean_specialized_model and key == "photo_data":
                    continue
                if clean_specialized_model and key not in visible and key not in {"record_number", "record_state"}:
                    continue
                if bool(self._field_styles.get(key, {}).get("field_deleted")):
                    continue

                row_widget = QWidget()
                row_layout = QGridLayout(row_widget)
                row_layout.setContentsMargins(1, 0, 1, 0)
                row_layout.setHorizontalSpacing(6)
                row_layout.setVerticalSpacing(0)

                _raw_label = str(custom_labels.get(key, spec.label) or spec.label)
                if key == "record_state" and _raw_label == "État de la fiche":
                    _raw_label = "Etat de la fiche"
                _display_label = self._t(_raw_label) if (_raw_label == str(spec.label) or _raw_label == "Coût total") else _raw_label
                check = QCheckBox(_display_label)
                check.setChecked(key in visible)
                check.setMinimumWidth(120)
                check.setMaximumWidth(190)
                if key in {"record_number", "record_state"}:
                    # Champs communs obligatoires à toutes les collections.
                    check.setChecked(True)
                    check.setEnabled(False)
                    check.setToolTip(
                        "Ce champ est obligatoire et reste présent dans toutes les collections."
                    )
                self._checks[key] = check

                label_edit = QLineEdit(_display_label)
                label_edit.setPlaceholderText(self._t(str(spec.label)))
                label_edit.setToolTip("Nom affiché sur la Fiche")
                label_edit.setMaximumWidth(245)
                self._install_french_lineedit_menu(label_edit)
                self._labels[key] = label_edit

                relation_mark = QLabel("M" if key in self._field_masters else ("R" if key in self._field_links else ""))
                relation_mark.setFixedWidth(12)
                relation_mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
                if key in self._field_masters:
                    mf = QFont(relation_mark.font()); mf.setBold(True); relation_mark.setFont(mf)
                relation_mark.setToolTip("Champ Maître" if key in self._field_masters else ("Champ Relié" if key in self._field_links else ""))
                self._relation_markers[key] = relation_mark
                field_cell = QWidget()
                field_cell_layout = QHBoxLayout(field_cell)
                field_cell_layout.setContentsMargins(0, 0, 0, 0); field_cell_layout.setSpacing(2)
                field_cell_layout.addWidget(relation_mark); field_cell_layout.addWidget(check, 1)
                row_layout.addWidget(field_cell, 0, 0)
                label_edit.hide()  # conservé en interne pour compatibilité des modèles existants

                if key in MOVABLE_FIELDS:
                    block_combo = QComboBox()
                    block_combo.addItems(list(MODEL_BLOCKS))
                    block_combo.hide()
                    block, position = placement.get(key, (original_group, idx))
                    if block in MODEL_BLOCKS:
                        block_combo.setCurrentText(block)

                    # Position historique conservée uniquement pour compatibilité ;
                    # elle n'intervient plus dans la géométrie.
                    position_spin = PositionSpinBox()
                    position_spin.setRange(1, 99)
                    position_spin.setValue(int(position) + 1)
                    position_spin.hide()

                    self._blocks[key] = block_combo
                    self._positions[key] = position_spin
                    block_combo.currentTextChanged.connect(
                        lambda _text, k=key: self._on_block_changed(k)
                    )
                else:
                    pass

                if key != "photo_data":
                    tab_spin = PositionSpinBox()
                    tab_spin.setRange(1, 99)
                    tab_spin.setValue(int(initial_tab_numbers.get(key, len(initial_tab_numbers) + 1)))
                    tab_spin.setFixedWidth(48)
                    tab_spin.setToolTip(
                        "Ordre de tabulation. Par défaut il suit l'ordre visuel ; "
                        "vous pouvez le modifier indépendamment."
                    )
                    self._tab_positions[key] = tab_spin
                    tab_spin.setParent(row_widget)
                    tab_spin.hide()
                    tab_spin.valueChanged.connect(
                        lambda _value, k=key: self._on_tab_position_changed(k)
                    )
                    tab_spin.editingFinished.connect(
                        lambda k=key: self._finish_tab_position_edit(k)
                    )
                else:
                    no_tab = QLabel("—")
                    no_tab.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    no_tab.setStyleSheet("color: #9AA39E;")
                    no_tab.hide()

                row_layout.setColumnStretch(0, 1)

                check.toggled.connect(lambda _checked, k=key: self._on_visibility_changed(k))
                label_edit.textChanged.connect(self._refresh_preview)
                label_edit.editingFinished.connect(self._record_history_state)
                self._rows[key] = row_widget
                if key not in {"record_number", "record_state", "photo_data"}:
                    row_widget.setProperty("_mm3_palette_field_key", str(key))
                    row_widget.setAcceptDrops(True)
                    row_widget.setMouseTracking(True)
                    row_widget.installEventFilter(self)
                    check.setProperty("_mm3_palette_field_key", str(key))
                    check.setAcceptDrops(True)
                    check.setMouseTracking(True)
                    check.installEventFilter(self)
                    check.setToolTip((check.toolTip() + "\n" if check.toolTip() else "") +
                                     "Cochez puis faites glisser cette ligne sur la fiche pour placer le champ.")
                    self._install_palette_field_context_menu(row_widget, key)
                    self._install_palette_field_context_menu(check, key)

        for custom_key in self._custom_field_defs:
            if imported_palette_keys is not None and custom_key not in imported_palette_keys:
                continue
            self._add_custom_field_row(
                custom_key, visible, custom_labels, placement, initial_tab_numbers
            )

        # 11.4.21 — cadres Photo dans la palette.
        # Le premier cadre Photo possède désormais sa propre ligne stable, au même
        # titre que les cadres Photo supplémentaires. On ne dépend plus de la ligne
        # historique créée depuis GROUPS, ce qui supprimait son titre dans certains
        # modèles spécialisés après reconstruction de la palette.
        self._photo_frame_rows = {}
        self._photo_frame_checks = {}

        primary_photo_title = self._group_display_title("Photo").strip() or "Photo"
        primary_row = QWidget()
        primary_layout = QGridLayout(primary_row)
        primary_layout.setContentsMargins(1, 0, 1, 0)
        primary_layout.setHorizontalSpacing(6)
        primary_layout.setVerticalSpacing(0)
        primary_check = QCheckBox(primary_photo_title)
        primary_check.setChecked(not bool(self._group_styles.get("Photo", {}).get("frame_deleted")))
        primary_check.setMinimumWidth(120)
        primary_check.setMaximumWidth(190)
        primary_no_tab = QLabel("—")
        primary_no_tab.setAlignment(Qt.AlignmentFlag.AlignCenter)
        primary_no_tab.setStyleSheet("color: #9AA39E;")
        primary_layout.addWidget(primary_check, 0, 0)
        primary_no_tab.hide()
        primary_layout.setColumnStretch(0, 1)

        # Compatibilité avec le reste du moteur : photo_data reste la clé logique
        # du premier cadre, mais sa ligne est maintenant celle-ci. Le QLineEdit caché
        # est conservé car les fonctions génériques de style/sauvegarde l'attendent.
        primary_label_edit = QLineEdit(primary_photo_title)
        primary_label_edit.hide()
        self._checks["photo_data"] = primary_check
        self._labels["photo_data"] = primary_label_edit
        self._rows["photo_data"] = primary_row
        self._photo_frame_rows["Photo"] = primary_row
        self._photo_frame_checks["Photo"] = primary_check
        primary_check.toggled.connect(self._on_primary_photo_frame_visibility_changed)

        for photo_name in getattr(self, "_custom_group_names", []):
            photo_style = self._group_styles.get(photo_name, {})
            if not (isinstance(photo_style, dict) and photo_style.get("custom_photo")):
                continue
            row_widget = QWidget()
            row_layout = QGridLayout(row_widget)
            row_layout.setContentsMargins(1, 0, 1, 0)
            row_layout.setHorizontalSpacing(6)
            row_layout.setVerticalSpacing(0)
            check = QCheckBox(self._group_display_title(photo_name))
            check.setChecked(not bool(photo_style.get("frame_deleted")))
            check.setMinimumWidth(120)
            check.setMaximumWidth(190)
            no_tab = QLabel("—")
            no_tab.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no_tab.setStyleSheet("color: #9AA39E;")
            row_layout.addWidget(check, 0, 0)
            row_layout.addWidget(no_tab, 0, 1)
            row_layout.setColumnStretch(0, 1)
            check.toggled.connect(lambda checked, n=photo_name: self._on_photo_frame_visibility_changed(n, checked))
            self._photo_frame_rows[photo_name] = row_widget
            self._photo_frame_checks[photo_name] = check

        # 23.8.7.2 — les numéros de tabulation décrivent les places réellement
        # occupées dans le modèle courant : aucun trou laissé par un champ absent.
        self._renumber_tab_order()

        editor_scroll.setWidget(editor_host)
        splitter.addWidget(editor_scroll)

        # ------------------------------------------------------------------
        # APERCU DE LA FICHE A DROITE
        # ------------------------------------------------------------------
        preview_scroll = QScrollArea()
        self._preview_scroll = preview_scroll
        preview_scroll.setWidgetResizable(True)
        preview_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        preview_host = QWidget()
        self._preview_host = preview_host
        preview_host.setObjectName("modelPreviewSheet")
        preview_root = QVBoxLayout(preview_host)
        preview_root.setContentsMargins(8, 2, 8, 8)
        preview_root.setSpacing(7)

        preview_title = QLabel(self._t("Aperçu en direct de la fiche"))
        preview_font = preview_title.font()
        preview_font.setBold(True)
        preview_font.setPointSize(preview_font.pointSize() + 2)
        preview_title.setFont(preview_font)
        preview_title.setStyleSheet("color: #173C78;")
        preview_root.addWidget(preview_title)

        preview_hint = QLabel(
            self._t("Cliquez un champ pour le sélectionner, déplacez-le à la souris, puis affinez avec les flèches.")
        )
        preview_hint.setWordWrap(True)
        preview_hint.setStyleSheet("color: #607068;")
        preview_root.addWidget(preview_hint)

        # 018.4.4.1.5.22.8 — structure visuelle commune Atelier/Fiche.
        form_surface = FormSurface(
            self,
            lambda block_name, owner, parent: MagneticCanvas(block_name, owner, parent),
        )
        self._form_surface = form_surface
        construction = form_surface.widget
        self._construction_widget = construction

        # 23.9.3.5.4 — chemin rapide d'ouverture :
        # les collections actuelles utilisent déjà des coordonnées absolues
        # (sheet_absolute_v1). Construire directement les champs sur la feuille
        # finale évite un premier montage dans les anciens canvases, puis leur
        # reparentage et un second rafraîchissement complet quelques ms plus tard.
        if self._stored_field_space == "sheet_absolute_v1":
            self._absolute_fields_ready = True

        self._construction_widget.setProperty("_mm3_group_lasso_surface", True)
        self._construction_widget.setMouseTracking(True)
        self._construction_widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._construction_widget.setAcceptDrops(True)
        self._construction_widget.installEventFilter(self)

        # 23.7.1 — quadrillage continu sur TOUTE la feuille, y compris hors cadres.
        self._sheet_grid_overlay = SheetGridOverlay(self, self._construction_widget)
        self._sheet_grid_overlay.setGeometry(self._construction_widget.rect())
        self._sheet_grid_overlay.show()
        self._sheet_grid_overlay.lower()

        # Le viewport reçoit les clics dans la partie nouvellement agrandie.
        preview_scroll.viewport().setProperty("_mm3_group_lasso_viewport", True)
        preview_scroll.viewport().installEventFilter(self)
        self._group_rubber_band = QRubberBand(QRubberBand.Shape.Rectangle, self._construction_widget)
        self._construction_grid = form_surface.grid
        self._preview_groups = form_surface.groups
        self._preview_canvases = form_surface.canvases
        self._preview_photo_group = form_surface.photo_group
        self._preview_photo_placeholder = form_surface.photo_placeholder

        for block_name, group in self._preview_groups.items():
            group.setProperty("_mm3_free_group", block_name)
            group.installEventFilter(self)
            canvas = self._preview_canvases[block_name]
            canvas.setProperty("_mm3_free_group", block_name)
            # 23.9.2.4 — une zone libre DANS un cadre appartient au canevas de
            # lasso, pas au cadre. Le filtre traite cette propriété AVANT la
            # logique de sélection/déplacement du groupe.
            canvas.setProperty("_mm3_group_lasso_surface", True)
            canvas.setMouseTracking(True)
            canvas.installEventFilter(self)

        self._preview_photo_group.setProperty("_mm3_free_group", "Photo")
        self._preview_photo_group.installEventFilter(self)
        self._preview_photo_placeholder.setProperty("_mm3_free_group", "Photo")
        self._preview_photo_placeholder.setProperty("_mm3_group_lasso_surface", True)
        self._preview_photo_placeholder.installEventFilter(self)

        construction.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        preview_root.addWidget(construction, 1)
        # Les styles de cadres seront appliqués par le premier _refresh_preview().
        # Évite une passe complète redondante pendant l'ouverture.
        QTimer.singleShot(0, self._activate_free_group_layout)
        preview_scroll.setWidget(preview_host)
        splitter.addWidget(preview_scroll)

        # Plus de place à la fiche que dans 018.4.4.1.2.9.
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([245, 1120])

        # Un seul ascenseur pilotable : la fiche suit la colonne de travail.
        editor_scroll.verticalScrollBar().valueChanged.connect(
            preview_scroll.verticalScrollBar().setValue
        )
        root.addWidget(splitter, 1)

        self._normalize_all_positions()
        self._rebuild_editor_groups()
        self._refresh_all_row_styles()
        self._refresh_preview()
        self._apply_sheet_background_preview()

        # L'état d'ouverture est le premier point de retour.
        # Une seule capture suffit : l'ancienne version recalculait deux fois
        # exactement le même état complet du modèle.
        opening_state = self._snapshot_state()
        self._undo_stack = [opening_state]
        self._redo_stack = []
        self._saved_state = deepcopy(opening_state)
        self._model_was_saved = False
        self._closing_after_choice = False
        self._update_history_buttons()

        # 2.3.24.6.20.19 — récupération non destructive de l'Atelier.
        # Uniquement l'Atelier de la collection, jamais l'édition des maîtres.
        if self.workshop_mode == "collection":
            self._recovery_timer = QTimer(self)
            self._recovery_timer.setInterval(10000)
            self._recovery_timer.timeout.connect(self._write_recovery_snapshot)
            QTimer.singleShot(0, self._offer_recovery_snapshot)
            self._recovery_timer.start()

        # 23.5.1 — capture robuste des flèches tant qu'un champ de la maquette
        # est sélectionné. Le déplacement ne dépend plus des aléas de focus Qt.
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

        note = QLabel(self._t(
            "La grille n’apparaît qu’en mode construction. Ctrl+clic ou lasso = sélection multiple ; "
            "flèches = réglage au pixel. Huit poignées permettent largeur, hauteur ou les deux ; "
            "Aligner utilise toujours le bord extrême correspondant."
        ))
        note.setWordWrap(True)
        note.setStyleSheet("color: #607068;")
        root.addWidget(note)

        # Boutons avec icône de disquette explicite.
        buttons = QHBoxLayout()
        cancel_btn = QPushButton(self._t("Annuler"))
        open_model_btn = QPushButton(self._t("Ouvrir un modèle…"))
        open_model_btn.setToolTip(self._t("Charger un modèle depuis la bibliothèque Modèles de Fiches"))
        open_model_btn.clicked.connect(lambda _checked=False: self._open_model_from_library())
        preview_real_btn = QPushButton(self._t("Aperçu dans la Fiche"))
        preview_real_btn.setToolTip(self._t("Tester ce modèle sur une copie temporaire complète de la collection"))
        preview_real_btn.clicked.connect(self._preview_in_real_record)
        save_as_btn = QPushButton(self._t("Enregistrer sous…"))
        save_as_btn.setToolTip(self._t("Conserver ce modèle dans la bibliothèque Modèles de Fiches"))
        save_as_btn.clicked.connect(self._save_model_to_library)
        save_btn = QPushButton(self._t("Enregistrer le modèle"))
        save_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton))
        save_btn.setDefault(True)
        cancel_btn.clicked.connect(self.reject)
        save_btn.clicked.connect(self._save)
        buttons.addStretch(1)
        buttons.addWidget(cancel_btn)
        buttons.addWidget(open_model_btn)
        buttons.addWidget(preview_real_btn)
        buttons.addWidget(save_as_btn)
        buttons.addWidget(save_btn)
        root.addLayout(buttons)

    def _t(self, text: str) -> str:
        return tr(text, self.language)

    def _refresh_active_model_name(self) -> None:
        name = str(getattr(self, "_active_library_model_name", "") or "").strip()
        if not name:
            name = str(self.collection.get("name") or "Modèle de fiche")
        if hasattr(self, "model_name_label"):
            self.model_name_label.setText(f"{self._t('Modèle actif :')} {name}")
        if hasattr(self, "atelier_title_label"):
            prefix = self._t("Atelier - Modèle maître") if self.workshop_mode == "master" else self._t("Atelier - Modèles")
            self.atelier_title_label.setText(f"{prefix} — {collection_display_name(self.collection, self.language)}")
        self.setWindowTitle(f"{self._t('Modèle de fiche')} — {collection_display_name(self.collection, self.language)} — {name}")

    def _custom_group_title(self, name: str) -> str:
        style = self._group_styles.get(name, {})
        title = style.get("title", {}) if isinstance(style, dict) else {}
        if isinstance(title, dict) and bool(title.get("hidden")):
            return ""
        value = str(title.get("text", "")).strip() if isinstance(title, dict) else ""
        # Compatibilité avec un éventuel essai antérieur.
        if not value and isinstance(style, dict):
            value = str(style.get("display_title", "")).strip()
        return self._localized_native_photo_title(value or str(name))

    def _build_custom_group_after_layout(self, name: str):
        """Ajoute un cadre graphique libre, indépendant de tous les champs."""
        name = str(name).strip()
        if not name:
            return None
        if name in self._preview_groups:
            return self._preview_groups[name]

        host = getattr(self, "_construction_widget", None)
        if host is None:
            return None
        # 23.8.5.2 — une fiche peut désormais ne contenir AUCUN cadre.
        # La création d'un nouveau cadre ne doit donc jamais dépendre de
        # _free_group_default_geometries, qui devient légitimement vide
        # après suppression de tous les cadres existants.

        group = QGroupBox(self._custom_group_title(name), host)
        group.setMinimumSize(0, 0)
        group.setMaximumSize(16777215, 16777215)

        box = QVBoxLayout(group)
        style = self._group_styles.get(name, {})
        if bool(style.get("custom_photo")):
            box.setContentsMargins(0, 0, 0, 0)
        else:
            box.setContentsMargins(6, 10, 6, 6)
        box.setSpacing(0)

        if bool(style.get("custom_photo")):
            canvas = QLabel("📷\nPhoto", group)
            canvas.setAlignment(Qt.AlignmentFlag.AlignCenter)
            photo_background, _ = self._group_colors(name)
            canvas.setStyleSheet(
                f"background-color:{photo_background}; border:none; border-radius:0px; color:#718078;"
            )
            canvas.setMinimumSize(0, 0)
            canvas.setMaximumSize(16777215, 16777215)
            canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        else:
            canvas = MagneticCanvas(name, self, group)
            canvas.setMinimumSize(0, 0)
            canvas.setMaximumSize(16777215, 16777215)
            canvas.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Expanding,
            )
            # Lasso intérieur propre au canvas : champs seulement.
            canvas.setMouseTracking(True)
        box.addWidget(canvas, 1)

        self._preview_groups[name] = group
        self._preview_canvases[name] = canvas

        # Le nouveau groupe entre maintenant seulement dans les opérations libres.
        if name not in self._free_group_names:
            self._free_group_names = tuple(list(self._free_group_names) + [name])

        group.setProperty("_mm3_free_group", name)
        canvas.setProperty("_mm3_free_group", name)
        canvas.setProperty("_mm3_group_lasso_surface", True)
        group.installEventFilter(self)
        canvas.installEventFilter(self)

        stored = self._free_group_geometry_style(name)
        if stored is not None:
            x, y, w, h = stored
            geom = QRect(x, y, w, h)
        else:
            bottom = max(
                [
                    self._free_group_widget(n).geometry().bottom() + 1
                    for n in self._free_group_names
                    if n != name and self._free_group_widget(n) is not None
                    and self._free_group_widget(n).isVisible()
                ] or [0]
            )
            geom = QRect(12, bottom + 12, 300, 130)

        group.setGeometry(geom)
        group.show()
        self._free_group_default_geometries[name] = QRect(geom)

        self._create_group_resize_handles(name, group)
        self._ensure_group_title_handle(name)
        self._position_group_resize_handles(name)
        self._refresh_group_styles()
        self._resize_free_group_host()

        # 23.7.7.2 — le cadre vient d'être créé/restauré APRÈS les champs.
        # Il doit immédiatement repasser derrière eux. Sans cette remise en pile,
        # un champ situé à l'intérieur du cadre pouvait sembler avoir disparu
        # jusqu'au clic suivant (qui faisait simplement field.raise_()).
        group.lower()
        self._raise_absolute_fields()
        return group

    def _restore_custom_groups_after_layout(self) -> None:
        """Restaure les cadres mémorisés sans jamais recouvrir les champs."""
        for name in list(getattr(self, "_custom_group_names", [])):
            self._build_custom_group_after_layout(name)

        # Une dernière normalisation après la boucle protège également le cas
        # de plusieurs cadres utilisateur restaurés simultanément.
        self._raise_absolute_fields()

    def _create_custom_photo_frame(self, source_name: str | None = None) -> None:
        index = 2
        existing = set(self._group_styles) | set(self._preview_groups)
        while f"photo_slot_{index}" in existing:
            index += 1
        name = f"photo_slot_{index}"
        title = f"Photo {index}"

        source_style = (
            deepcopy(self._group_styles.get(source_name, {}))
            if source_name else {}
        )
        if source_name == "Photo" and not source_style:
            source_style = deepcopy(self._group_styles.get("Photo", {}))

        if source_name:
            source_style["custom_group"] = True
            source_style["custom_photo"] = True
            source_style["frame_deleted"] = False
            source_style["title"] = deepcopy(source_style.get("title", {}))
            source_style["title"]["text"] = title
            source_style["geometry_space"] = "atelier_px"
            geom = dict(source_style.get("geometry") or {})
            if geom:
                geom["x"] = int(geom.get("x", 12)) + 18
                geom["y"] = int(geom.get("y", 12)) + 18
                source_style["geometry"] = geom
            self._group_styles[name] = source_style
        else:
            self._group_styles[name] = {
                "custom_group": True,
                "custom_photo": True,
                "title": {"text": title},
                "geometry_space": "atelier_px",
            }
        if name not in self._custom_group_names:
            self._custom_group_names.append(name)

        group = self._build_custom_group_after_layout(name)
        if group is None:
            self._custom_group_names.remove(name)
            self._group_styles.pop(name, None)
            QMessageBox.warning(
                self, "Nouveau cadre Photo",
                "Le cadre Photo n'a pas pu être créé dans la fiche."
            )
            return
        self._persist_free_group_geometry(name)
        self._set_free_group_selection([name], False)
        self._record_history_state()

    def _create_large_photo_frame(self) -> None:
        """Ajoute un emplacement photo grand format sans modifier les cadres historiques."""
        if not getattr(self, "_large_photo_warning_shown", False):
            confirmation = QMessageBox(self)
            confirmation.setIcon(QMessageBox.Icon.Question)
            confirmation.setWindowTitle(self._t("Grand cadre Photo"))
            confirmation.setText(self._t(
                "Les grandes photos augmentent le poids du fichier de collection (.coldb), "
                "notamment sur plusieurs milliers de fiches.\n\n"
                "Chaque image sera réduite à 600 × 400 pixels maximum et convertie en JPEG.\n\n"
                "Créer ce cadre ?"
            ))
            yes_button = confirmation.addButton(self._t("Oui"), QMessageBox.ButtonRole.YesRole)
            confirmation.addButton(self._t("Non"), QMessageBox.ButtonRole.NoRole)
            confirmation.setDefaultButton(yes_button)
            confirmation.exec()
            if confirmation.clickedButton() is not yes_button:
                return
            self._large_photo_warning_shown = True
        before = set(self._group_styles)
        self._create_custom_photo_frame()
        created = [name for name in self._group_styles if name not in before and self._group_styles[name].get("custom_photo")]
        if not created:
            return
        name = created[-1]
        style = self._group_styles[name]
        style["large_photo"] = True
        style["title"] = {"text": self._t("Grand cadre Photo")}
        group = self._preview_groups.get(name)
        if group is not None:
            rect = group.geometry()
            group.setGeometry(rect.x(), rect.y(), 600, 400)
            group.setTitle(self._t("Grand cadre Photo"))
            self._free_group_default_geometries[name] = QRect(group.geometry())
            self._position_group_resize_handles(name)
            self._resize_free_group_host()
            self._persist_free_group_geometry(name)
        self._record_history_state()

    def _delete_custom_photo_frame(self, name: str) -> None:
        style = self._group_styles.get(name, {})
        if not (isinstance(style, dict) and style.get("custom_photo")):
            return
        title = self._group_display_title(name)
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Supprimer le cadre Photo")
        box.setText(f"Supprimer le cadre « {title} » ?")
        box.setInformativeText(
            "Les photos enregistrées dans ce cadre seront également supprimées définitivement."
        )
        yes_button = box.addButton("Oui", QMessageBox.ButtonRole.DestructiveRole)
        no_button = box.addButton("Non", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(no_button)
        box.exec()
        if box.clickedButton() is not yes_button:
            return

        self.manager.delete_extra_photo_slot_data(self.collection_id, name)
        self._delete_graphical_frame_without_confirmation(name)

    def _delete_graphical_frame_without_confirmation(self, name: str) -> None:
        group = self._preview_groups.pop(name, None)
        self._preview_canvases.pop(name, None)
        if group is not None:
            group.hide()
            group.deleteLater()
        frame = self._group_selection_frames.pop(name, None)
        if frame is not None:
            frame.hide()
            frame.deleteLater()
        handle = self._group_title_handles.pop(name, None)
        if handle is not None:
            handle.hide()
            handle.deleteLater()
        for resize_handle in self._free_group_resize_handles.pop(name, []):
            resize_handle.hide()
            resize_handle.deleteLater()
        self._selected_free_groups.discard(name)
        self._free_group_default_geometries.pop(name, None)
        self._group_styles.pop(name, None)
        self._custom_group_names = [x for x in self._custom_group_names if x != name]
        self._free_group_names = tuple(x for x in self._free_group_names if x != name)
        self._refresh_free_group_selection()
        self._raise_absolute_fields()
        self._resize_free_group_host()
        self._record_history_state()

    def _create_custom_group(self) -> None:
        title, ok = QInputDialog.getText(
            self, "Nouveau cadre", "Nom du cadre :"
        )
        if not ok:
            return
        title = str(title).strip()
        if not title:
            QMessageBox.information(
                self, "Nouveau cadre", "Le nom du cadre ne peut pas être vide."
            )
            return

        existing_titles = {
            self._group_display_title(name).casefold()
            for name in self._free_group_names
        }
        existing_titles.update(
            self._custom_group_title(name).casefold()
            for name in getattr(self, "_custom_group_names", [])
        )
        if title.casefold() in existing_titles:
            QMessageBox.warning(
                self, "Nouveau cadre", "Un cadre portant ce nom existe déjà."
            )
            return

        index = 1
        while (
            f"custom_group_{index}" in self._group_styles
            or f"custom_group_{index}" in self._preview_groups
        ):
            index += 1
        name = f"custom_group_{index}"

        self._group_styles[name] = {
            "custom_group": True,
            "title": {"text": title},
            "geometry_space": "atelier_px",
        }
        self._custom_group_names.append(name)

        # 23.7.7.0 — un nouveau cadre est exclusivement graphique : aucun champ ne lui appartient.
        group = self._build_custom_group_after_layout(name)
        if group is None:
            self._custom_group_names.remove(name)
            self._group_styles.pop(name, None)
            QMessageBox.warning(
                self, "Nouveau cadre",
                "Le cadre n'a pas pu être créé dans la fiche."
            )
            return

        # Enregistrer immédiatement sa géométrie dans l'état Atelier.
        self._persist_free_group_geometry(name)
        self._set_free_group_selection([name], False)
        self._record_history_state()

    def _delete_graphical_frame(self, name: str) -> None:
        if name not in getattr(self, "_free_group_names", ()):
            return

        style = self._group_styles.get(name, {})
        is_custom = bool(isinstance(style, dict) and style.get("custom_group"))
        title = self._group_display_title(name)

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle("Supprimer le cadre")
        box.setText(f"Supprimer le cadre « {title} » ?")
        if name == "Photo":
            box.setInformativeText(
                "Les photos enregistrées dans ce cadre seront également supprimées définitivement."
            )
        yes_button = box.addButton("Oui", QMessageBox.ButtonRole.YesRole)
        no_button = box.addButton("Non", QMessageBox.ButtonRole.NoRole)
        box.setDefaultButton(no_button)
        box.exec()
        if box.clickedButton() is not yes_button:
            return

        if name == "Photo":
            self.manager.delete_primary_photo_data(self.collection_id)

        group = self._preview_groups.get(name)

        if is_custom:
            # Un cadre personnalisé peut être réellement détruit : Undo saura
            # maintenant le reconstruire depuis group_styles, titre compris.
            self._preview_groups.pop(name, None)
            self._preview_canvases.pop(name, None)
            if group is not None:
                group.hide()
                group.deleteLater()

            frame = self._group_selection_frames.pop(name, None)
            if frame is not None:
                frame.hide()
                frame.deleteLater()

            handle = self._group_title_handles.pop(name, None)
            if handle is not None:
                handle.hide()
                handle.deleteLater()

            for resize_handle in self._free_group_resize_handles.pop(name, []):
                resize_handle.hide()
                resize_handle.deleteLater()

            self._group_styles.pop(name, None)
            self._custom_group_names = [
                item for item in self._custom_group_names if item != name
            ]
        else:
            # Cadre historique : ne pas détruire le QGroupBox. Le masquer suffit,
            # ce qui rend Défaire instantané et conserve son libellé.
            saved_style = dict(style) if isinstance(style, dict) else {}
            saved_style["frame_deleted"] = True
            self._group_styles[name] = saved_style
            if group is not None:
                group.hide()

            frame = self._group_selection_frames.get(name)
            if frame is not None:
                frame.hide()
            handle = self._group_title_handles.get(name)
            if handle is not None:
                handle.hide()
            for resize_handle in self._free_group_resize_handles.get(name, []):
                resize_handle.hide()

        self._selected_free_groups.discard(name)
        self._free_group_default_geometries.pop(name, None)
        self._free_group_names = tuple(
            item for item in self._free_group_names if item != name
        )

        self._refresh_free_group_selection()
        self._raise_absolute_fields()
        self._resize_free_group_host()
        self._record_history_state()


    def _delete_custom_group(self, name: str) -> None:
        self._delete_graphical_frame(name)

    def _make_french_color_dialog(self, initial: QColor, title: str) -> QColorDialog:
        """Compatibilité : utilise désormais le sélecteur de couleurs MM3 commun."""
        return make_color_dialog(self, initial, title)

    def _choose_color_fr(self, initial: QColor, title: str) -> QColor | None:
        return choose_color(self, initial, title)

    def _apply_sheet_background_preview(self) -> None:
        color = QColor(self._sheet_background)
        if not color.isValid():
            color = QColor(self._default_sheet_background)

        # La Fiche garde exactement sa couleur choisie. L'Atelier utilise une
        # variante nettement plus sombre afin que les deux surfaces se lisent
        # immédiatement comme deux zones différentes.
        atelier_color = QColor("#DCE7F2") if self.workshop_mode in ("master", "template") else color.darker(132)

        if hasattr(self, "_preview_host"):
            self._preview_host.setStyleSheet(
                f"#modelPreviewSheet {{ background-color: {color.name()}; }}"
            )

        palette = self.palette()
        palette.setColor(self.backgroundRole(), atelier_color)
        self.setPalette(palette)
        self.setAutoFillBackground(True)

        for scroll_name in ("_editor_scroll", "_preview_scroll"):
            scroll = getattr(self, scroll_name, None)
            if scroll is not None:
                viewport = scroll.viewport()
                vp = viewport.palette()
                vp.setColor(viewport.backgroundRole(), atelier_color)
                viewport.setPalette(vp)
                viewport.setAutoFillBackground(True)

        if hasattr(self, "sheet_color_btn"):
            self.sheet_color_btn.setStyleSheet(
                f"QPushButton {{ background-color: {self._sheet_background}; }}"
            )

    def _choose_sheet_background(self) -> None:
        initial = QColor(self._sheet_background)
        color = self._choose_color_fr(initial, self._t("Couleur de fond de la fiche"))
        if color is None:
            return
        value = color.name()
        if value == self._sheet_background:
            return
        self._sheet_background = value
        self._apply_sheet_background_preview()
        self._refresh_group_styles()
        self._record_history_state()

    def _reset_sheet_style(self) -> None:
        if self._sheet_background == self._default_sheet_background:
            return
        self._sheet_background = self._default_sheet_background
        self._apply_sheet_background_preview()
        self._refresh_group_styles()
        self._record_history_state()


    def _field_spec(self, key: str):
        # N° de fiche est structurel : il n'appartient volontairement pas au
        # catalogue des champs éditables/supprimables, mais il doit exister
        # dans l'Atelier comme objet déplaçable obligatoire.
        if key == "record_number":
            return SimpleNamespace(
                key="record_number",
                label="N° de fiche",
                field_type="number",
                referential=None,
            )
        spec = FIELD_BY_KEY.get(key)
        if spec is not None:
            return spec
        row = self._custom_field_defs.get(str(key))
        if not row:
            return None
        return SimpleNamespace(
            key=str(key),
            label=str(row.get("label") or "Nouveau champ"),
            field_type=str(row.get("field_type") or "text"),
            referential=row.get("referential_code"),
        )

    def _referential_values_for_default(self, key: str) -> list[str]:
        """Valeurs proposées pour la valeur par défaut d'un champ en liste."""
        spec = self._field_spec(str(key))
        code = str(getattr(spec, "referential", "") or "").strip() if spec is not None else ""
        if not code:
            return []
        try:
            return list(ReferentialManager(self.manager.db_path).list_values(self.collection_id, code))
        except Exception:
            return []

    def _fill_default_combo(self, combo: QComboBox, field_type: str, key: str | None, current: str) -> None:
        """Transforme Valeur par défaut en vraie liste lorsqu'il s'agit d'un référentiel."""
        value = str(current or "")
        combo.blockSignals(True)
        combo.clear()
        ftype = str(field_type or "text")
        if ftype == "list" and key:
            combo.addItems(self._referential_values_for_default(str(key)))
        elif ftype == "boolean":
            combo.addItems(["Oui", "Non"])
        combo.setEditable(True)
        combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        combo.setCurrentText(value)
        if combo.lineEdit() is not None:
            combo.lineEdit().setPlaceholderText("Facultatif")
        combo.blockSignals(False)

    def _add_default_to_referential(self, referential_code: str | None, value: str) -> None:
        """Ajoute au référentiel une valeur par défaut saisie qui n'existait pas encore."""
        code = str(referential_code or "").strip()
        clean_value = str(value or "").strip()
        if not code or not clean_value:
            return
        try:
            refs = ReferentialManager(self.manager.db_path)
            if not refs.contains(self.collection_id, code, clean_value, active_only=False):
                refs.add_value(self.collection_id, code, clean_value)
        except Exception as exc:
            QMessageBox.warning(
                self, "Valeur par défaut",
                "La valeur par défaut a été enregistrée, mais son ajout au référentiel a échoué :\n\n" + str(exc)
            )

    def _palette_group_names(self) -> list[str]:
        """Familles de champs de la palette, indépendantes des cadres graphiques."""
        return list(MODEL_BLOCKS)

    def _preferred_new_field_group(self) -> str:
        selected = list(self._selected_preview_keys)
        if selected:
            groups = {
                self._field_block_and_position(key)[0]
                for key in selected
                if self._field_block_and_position(key)[0] in self._palette_group_names()
            }
            if len(groups) == 1:
                return next(iter(groups))
        if self._last_group_context in self._palette_group_names():
            return self._last_group_context
        return "Identification"

    def _unique_duplicate_field_label(self, source_label: str) -> str:
        base = (source_label or "Champ").strip()
        labels = set()
        for key in self._checks:
            spec = self._field_spec(key)
            if spec is not None:
                labels.add((self._labels.get(key).text() if key in self._labels else spec.label).strip().casefold())
        for row in self._custom_field_defs.values():
            labels.add(str(row.get("label") or "").strip().casefold())

        index = 1
        while f"{base}-{index}".casefold() in labels:
            index += 1
        return f"{base}-{index}"

    def _duplicate_field(self, source_key: str, target_point: QPoint | None = None) -> None:
        """Crée un NOUVEAU champ MM3 indépendant à partir d'un champ existant."""
        source_key = str(source_key)
        if source_key == "record_number":
            return
        source = self._preview_fields.get(source_key)
        spec = self._field_spec(source_key)
        if source is None or spec is None:
            return

        source_label = (
            self._labels[source_key].text().strip()
            if source_key in self._labels
            else str(spec.label)
        )
        new_label = self._unique_duplicate_field_label(source_label)

        source_def = self._custom_field_defs.get(source_key, {})
        field_type = str(source_def.get("field_type") or getattr(spec, "field_type", "text") or "text")
        if field_type == "number":
            field_type = "numeric"
        if field_type not in {"text", "numeric", "date", "boolean", "list"}:
            field_type = "text"
        date_format = str(source_def.get("date_format") or "JJ/MM/AAAA")

        try:
            row = self.manager.create_custom_field(
                self.collection_id, new_label, field_type,
                "Identification", date_format,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Duplication impossible", str(exc))
            return

        key = str(row["field_key"])
        self._custom_field_defs[key] = dict(row)

        scale = max(0.01, float(self._preview_scale()))
        src_pos = self._visual_positions.get(
            source_key, (round(source.x()/scale), round(source.y()/scale))
        )
        src_size = self._visual_sizes.get(
            source_key, (round(source.width()/scale), round(source.height()/scale))
        )

        if target_point is None:
            x = src_pos[0] + 18
            y = src_pos[1] + 18
        else:
            x = round(max(0, target_point.x()) / scale)
            y = round(max(0, target_point.y()) / scale)

        self._visual_positions[key] = (x, y)
        self._visual_sizes[key] = tuple(src_size)
        self._field_styles[key] = deepcopy(self._field_styles.get(source_key, {}))

        placement = self.manager.field_placement(self.collection_id)
        visible = self.manager.visible_fields(self.collection_id)
        labels = self.manager.custom_labels(self.collection_id)
        tab_order = self.manager.tab_order(
            self.collection_id, self._visual_order_from_placement(placement)
        )
        tab_numbers = {k: i + 1 for i, k in enumerate(tab_order)}
        self._add_custom_field_row(key, visible, labels, placement, tab_numbers)
        if key in self._checks:
            self._checks[key].setChecked(True)
        self._renumber_tab_order()

        self._rebuild_editor_groups_preserving_view()
        self._refresh_preview()
        self._set_preview_selection([key])
        self._record_history_state()

    _MM3_FIELDS_CLIPBOARD_PREFIX = "MM3_ATELIER_FIELDS_V1\n"

    def _copy_selected_field_for_duplication(self) -> bool:
        """Copie un ou plusieurs champs personnalisés dans le presse-papiers Windows.

        Le contenu est sérialisé afin de rester disponible après fermeture de
        l'Atelier. La disposition relative, le type, le style et la définition
        d'un éventuel champ calculé sont conservés.
        """
        keys = [
            str(k) for k in self._selected_preview_keys
            if str(k) != "record_number" and str(k) in self._custom_field_defs
        ]
        if not keys:
            return False

        # Ordre stable, de haut en bas puis de gauche à droite.
        keys.sort(key=lambda k: (
            self._visual_positions.get(k, (10**9, 10**9))[1],
            self._visual_positions.get(k, (10**9, 10**9))[0],
            k,
        ))
        fields = []
        for key in keys:
            definition = dict(self._custom_field_defs.get(key, {}))
            label = (
                self._labels[key].text().strip()
                if key in self._labels else str(definition.get("label") or key)
            )
            pos = tuple(self._visual_positions.get(key, (12, 12)))
            size = tuple(self._visual_sizes.get(key, (260, 31)))
            fields.append({
                "source_key": key,
                "label": label,
                "definition": definition,
                "position": [int(pos[0]), int(pos[1])],
                "size": [int(size[0]), int(size[1])],
                "style": deepcopy(self._field_styles.get(key, {})),
            })

        payload = {
            "kind": "mm3_atelier_fields",
            "version": 1,
            "source_collection_id": int(self.collection_id),
            "fields": fields,
        }
        QApplication.clipboard().setText(
            self._MM3_FIELDS_CLIPBOARD_PREFIX
            + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        )
        # L'ancien pointeur reste utile pour une duplication locale très simple.
        self._atelier_field_clipboard_key = keys[0] if len(keys) == 1 else None
        return True

    def _read_atelier_fields_clipboard(self) -> dict | None:
        text = QApplication.clipboard().text() or ""
        if not text.startswith(self._MM3_FIELDS_CLIPBOARD_PREFIX):
            return None
        try:
            payload = json.loads(text[len(self._MM3_FIELDS_CLIPBOARD_PREFIX):])
        except Exception:
            return None
        if not isinstance(payload, dict) or payload.get("kind") != "mm3_atelier_fields":
            return None
        if not isinstance(payload.get("fields"), list) or not payload["fields"]:
            return None
        return payload

    def _paste_duplicated_field(self) -> bool:
        payload = self._read_atelier_fields_clipboard()
        if payload is None:
            return False

        source_cid = int(payload.get("source_collection_id") or -1)
        source_fields = [f for f in payload.get("fields", []) if isinstance(f, dict)]
        if not source_fields:
            return False

        # Les champs qui existent déjà par libellé dans une autre collection ne
        # sont jamais écrasés silencieusement.
        existing_labels = {
            str(v.get("label") or "").strip().casefold()
            for v in self._custom_field_defs.values()
        }
        skipped = []
        created = []
        key_map = {}

        positions = [f.get("position", [0, 0]) for f in source_fields]
        min_x = min(int(p[0]) for p in positions if len(p) >= 2)
        min_y = min(int(p[1]) for p in positions if len(p) >= 2)
        if self._atelier_paste_point is not None:
            scale = max(0.01, float(self._preview_scale()))
            anchor_x = round(max(0, self._atelier_paste_point.x()) / scale)
            anchor_y = round(max(0, self._atelier_paste_point.y()) / scale)
        else:
            anchor_x, anchor_y = (min_x + 18, min_y + 18) if source_cid == int(self.collection_id) else (20, 20)

        # Première passe : création des champs et établissement du nouveau mapping
        # des clés. Les formules seront remappées ensuite.
        for item in source_fields:
            old_key = str(item.get("source_key") or "")
            definition = dict(item.get("definition") or {})
            source_label = str(item.get("label") or definition.get("label") or "Champ").strip()
            if source_cid == int(self.collection_id):
                new_label = self._unique_duplicate_field_label(source_label)
            else:
                new_label = source_label
                if new_label.casefold() in existing_labels:
                    skipped.append(new_label)
                    continue

            field_type = str(definition.get("field_type") or "text")
            if field_type == "number":
                field_type = "numeric"
            if field_type not in {"text", "numeric", "date", "boolean", "list", "link", "currency", "calculated"}:
                field_type = "text"
            date_format = str(definition.get("date_format") or "JJ/MM/AAAA")
            calculation_formula = str(definition.get("calculation_formula") or "")
            calculation_format = str(definition.get("calculation_format") or "truncate2")

            try:
                row = self.manager.create_custom_field(
                    self.collection_id, new_label, field_type,
                    "Identification", date_format, calculation_formula, calculation_format,
                )
            except Exception as exc:
                QMessageBox.critical(self, "Collage impossible", str(exc))
                return True

            key = str(row["field_key"])
            key_map[old_key] = key
            self._custom_field_defs[key] = dict(row)
            existing_labels.add(new_label.casefold())

            src_pos = item.get("position", [min_x, min_y])
            src_size = item.get("size", [260, 31])
            x = anchor_x + int(src_pos[0]) - min_x
            y = anchor_y + int(src_pos[1]) - min_y
            self._visual_positions[key] = (max(0, x), max(0, y))
            self._visual_sizes[key] = (max(30, int(src_size[0])), max(20, int(src_size[1])))
            self._field_styles[key] = deepcopy(item.get("style") or {})
            created.append((key, old_key, calculation_formula))

        # Deuxième passe : dans un champ calculé copié avec ses champs sources,
        # remplacer les anciennes clés personnalisées par les nouvelles.
        for key, _old_key, formula in created:
            if not formula:
                continue
            remapped = str(formula)
            for old, new in key_map.items():
                remapped = remapped.replace("{" + old + "}", "{" + new + "}")
            if remapped != formula:
                try:
                    self.manager.update_custom_field_calculation(
                        self.collection_id, key, remapped
                    )
                    if key in self._custom_field_defs:
                        self._custom_field_defs[key]["calculation_formula"] = remapped
                except Exception:
                    pass

        if not created:
            if skipped:
                QMessageBox.information(
                    self, "Collage des champs",
                    "Aucun champ n'a été ajouté : les champs suivants existent déjà :\n\n"
                    + "\n".join("• " + x for x in skipped)
                )
            return True

        placement = self.manager.field_placement(self.collection_id)
        visible = self.manager.visible_fields(self.collection_id)
        labels = self.manager.custom_labels(self.collection_id)
        tab_order = self.manager.tab_order(
            self.collection_id, self._visual_order_from_placement(placement)
        )
        tab_numbers = {k: i + 1 for i, k in enumerate(tab_order)}
        for key, _old_key, _formula in created:
            self._add_custom_field_row(key, visible, labels, placement, tab_numbers)
            if key in self._checks:
                self._checks[key].setChecked(True)
        self._renumber_tab_order()
        self._rebuild_editor_groups_preserving_view()
        self._refresh_preview()
        self._set_preview_selection([x[0] for x in created])
        self._record_history_state()

        if skipped:
            QMessageBox.information(
                self, "Collage des champs",
                "Les champs suivants existaient déjà et n'ont pas été recopiés :\n\n"
                + "\n".join("• " + x for x in skipped)
            )
        return True

    def _create_custom_field(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Ajouter un champ")
        # La boîte change de contenu quand le type « Calculé » est choisi.
        # Sous Windows, laisser Qt la retailler automatiquement sous la taille
        # minimale native provoque des avertissements QWindowsWindow::setGeometry.
        # Une taille minimale stable évite ce bruit dans cmd.exe.
        dialog.setMinimumSize(430, 390)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        intro = QLabel("Définissez le nouveau champ. Il restera librement déplaçable sur la fiche.")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        grid = QGridLayout()
        grid.addWidget(QLabel("Nom du champ :"), 0, 0)
        name_edit = QLineEdit()
        name_edit.setPlaceholderText("Ex. Provenance détaillée")
        grid.addWidget(name_edit, 0, 1)

        grid.addWidget(QLabel("Type :"), 1, 0)
        type_combo = QComboBox()
        type_combo.addItem("Texte", "text")
        type_combo.addItem("Nombre", "numeric")
        type_combo.addItem("Date", "date")
        type_combo.addItem("Oui / Non (On / Off)", "boolean")
        type_combo.addItem("Lien (Internet ou autre)", "link")
        type_combo.addItem("Monétaire", "currency")
        type_combo.addItem("Liste déroulante (référentiel)", "list")
        type_combo.addItem("Calculé", "calculated")
        grid.addWidget(type_combo, 1, 1)

        grid.addWidget(QLabel("Placement :"), 2, 0)
        group_combo = QComboBox()
        group_combo.addItem("Libre", "Identification")
        group_combo.hide()
        free_placement = QLabel("Libre sur la fiche")
        free_placement.setStyleSheet("color:#607068;")
        grid.addWidget(free_placement, 2, 1)

        grid.addWidget(QLabel("Format de date :"), 3, 0)
        date_format_combo = QComboBox()
        date_format_combo.addItems(["JJ/MM/AAAA", "JJ/MM/AA", "MM/AAAA", "AAAA", "AAAA-MM-JJ"])
        grid.addWidget(date_format_combo, 3, 1)

        default_label = QLabel("Valeur par défaut :")
        default_edit = QComboBox()
        default_edit.setEditable(True)
        default_edit.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        default_edit.lineEdit().setPlaceholderText("Facultatif")
        grid.addWidget(default_label, 10, 0)
        grid.addWidget(default_edit, 10, 1)

        currency_label = QLabel("Devise :")
        currency_combo = QComboBox()
        currency_combo.setEditable(True)
        currency_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        currency_combo.addItems(["€", "$", "£", "CHF", "¥", "CAD", "AUD"])
        currency_combo.setCurrentText("€")
        if currency_combo.lineEdit() is not None:
            currency_combo.lineEdit().setPlaceholderText("€ ou saisie libre")
        grid.addWidget(currency_label, 8, 0)
        grid.addWidget(currency_combo, 8, 1)
        currency_decimals_label = QLabel("Décimales :")
        currency_decimals_spin = QSpinBox()
        currency_decimals_spin.setRange(0, 4)
        currency_decimals_spin.setValue(2)
        grid.addWidget(currency_decimals_label, 9, 0)
        grid.addWidget(currency_decimals_spin, 9, 1)

        calc_label = QLabel("Formule :")
        calc_edit = QLineEdit()
        calc_edit.setPlaceholderText("Ex. ([Prix] * 20 / 100) + 25")
        grid.addWidget(calc_label, 4, 0); grid.addWidget(calc_edit, 4, 1)
        insert_label = QLabel("Insérer un champ :")
        insert_combo = QComboBox(); insert_combo.addItem("— choisir —", "")
        field_choices = []
        for fk in self._rows.keys():
            fk = str(fk)
            if fk == "record_number":
                continue
            field_choices.append((self._relation_field_label(fk), fk))
        for flabel, fk in sorted(field_choices, key=lambda item: item[0].lower()): insert_combo.addItem(flabel, fk)
        def insert_calc_field(index):
            if index > 0:
                calc_edit.insert("[" + insert_combo.currentText() + "]"); insert_combo.setCurrentIndex(0)
        insert_combo.activated.connect(insert_calc_field)
        grid.addWidget(insert_label, 5, 0); grid.addWidget(insert_combo, 5, 1)
        format_label = QLabel("Résultat numérique :")
        calc_format_combo = QComboBox()
        calc_format_combo.addItem("Arrondi à l’entier", "round")
        calc_format_combo.addItem("Sans décimales (sans arrondi)", "truncate0")
        calc_format_combo.addItem("2 décimales (sans arrondi)", "truncate2")
        grid.addWidget(format_label, 6, 0); grid.addWidget(calc_format_combo, 6, 1)

        suffix_label = QLabel("Suffixe du résultat :")
        suffix_combo = QComboBox()
        suffix_combo.setEditable(True)
        suffix_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        suffix_combo.addItems([
            "", "€", "$", "£", "CHF", "¥",
            "g", "kg", "mg", "lb", "oz",
            "mm", "cm", "m", "km",
            "mL", "cL", "L",
            "%", "pcs"
        ])
        if suffix_combo.lineEdit() is not None:
            suffix_combo.lineEdit().setPlaceholderText("Ex. €, kg, lb, cm… ou libre")
        grid.addWidget(suffix_label, 7, 0)
        grid.addWidget(suffix_combo, 7, 1)
        def refresh_date_format():
            is_date = str(type_combo.currentData()) == "date"
            date_format_combo.setEnabled(is_date)
            date_format_combo.setVisible(is_date)
            is_calc = str(type_combo.currentData()) == "calculated"
            for w in (
                calc_label, calc_edit, insert_label, insert_combo,
                format_label, calc_format_combo, suffix_label, suffix_combo
            ):
                w.setVisible(is_calc); w.setEnabled(is_calc)
            default_label.setVisible(not is_calc)
            default_edit.setVisible(not is_calc)
            default_label.setEnabled(not is_calc)
            default_edit.setEnabled(not is_calc)
            is_currency = str(type_combo.currentData()) == "currency"
            currency_label.setVisible(is_currency)
            currency_label.setEnabled(is_currency)
            currency_combo.setVisible(is_currency)
            currency_combo.setEnabled(is_currency)
            currency_decimals_label.setVisible(is_currency)
            currency_decimals_label.setEnabled(is_currency)
            currency_decimals_spin.setVisible(is_currency)
            currency_decimals_spin.setEnabled(is_currency)
            self._fill_default_combo(default_edit, str(type_combo.currentData()), None, default_edit.currentText())
        type_combo.currentIndexChanged.connect(refresh_date_format)
        refresh_date_format()
        layout.addLayout(grid)

        note = QLabel(
            "Le cadre est proposé d'après votre sélection actuelle. "
            "Il reste modifiable ici et plus tard dans la palette."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color:#5F6F68;")
        layout.addWidget(note)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Créer")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Annuler")
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        label = name_edit.text().strip()
        if not label:
            QMessageBox.warning(self, "Ajouter un champ", "Indiquez un nom pour le nouveau champ.")
            return

        calculation_formula = ""
        if str(type_combo.currentData()) == "calculated":
            calculation_formula = calc_edit.text().strip()
            for flabel, fk in sorted(field_choices, key=lambda item: len(item[0]), reverse=True):
                calculation_formula = calculation_formula.replace("[" + flabel + "]", "{" + fk + "}")
            if calculation_formula:
                try:
                    validate_calculation_formula(calculation_formula)
                except (SyntaxError, ValueError) as exc:
                    QMessageBox.warning(self, "Formule incorrecte", f"Vérifiez la formule : {exc}"); return
        try:
            row = self.manager.create_custom_field(
                self.collection_id, label, str(type_combo.currentData()),
                "Identification", date_format_combo.currentText(), calculation_formula, str(calc_format_combo.currentData()),
            )
        except Exception as exc:
            QMessageBox.critical(self, "Création impossible", str(exc))
            return

        key = str(row["field_key"])
        self._custom_field_defs[key] = dict(row)

        # Les données des champs nouvellement créés doivent être noires par
        # défaut. L'Atelier garde ses exemples gris pour les champs existants
        # qui le demandent explicitement, mais un nouveau champ part en noir.
        whole_style = dict(self._field_styles.get(key, {}))
        data_style = dict(whole_style.get("data", {}))
        data_style["color"] = "#000000"
        whole_style["data"] = data_style
        default_value = default_edit.currentText().strip()
        whole_style["default_value"] = default_value
        if str(row.get("field_type") or "") == "currency":
            whole_style["currency_symbol"] = currency_combo.currentText().strip() or "€"
            whole_style["currency_decimals"] = int(currency_decimals_spin.value())
        if str(row.get("field_type") or "") == "calculated":
            whole_style["result_suffix"] = suffix_combo.currentText().strip()
        self._field_styles[key] = whole_style
        if str(row.get("field_type") or "") == "list":
            self._add_default_to_referential(row.get("referential_code"), default_value)

        placement = self.manager.field_placement(self.collection_id)
        self._visual_positions[key] = self.manager.visual_positions(
            self.collection_id, placement
        ).get(key, (12, 12))
        self._visual_sizes[key] = self.manager.visual_sizes(
            self.collection_id
        ).get(key, (260, 31))

        # 1.0.188 — un champ nouvellement créé enrichit uniquement la palette.
        # Il ne doit pas être posé automatiquement sur la Fiche : l'utilisateur
        # l'active ensuite volontairement dans la palette et choisit sa position.
        visible = self.manager.visible_fields(self.collection_id)
        if key in visible:
            visible.discard(key)
            self.manager.set_visible_fields(self.collection_id, visible)

        labels = self.manager.custom_labels(self.collection_id)
        tab_order = self.manager.tab_order(
            self.collection_id, self._visual_order_from_placement(placement)
        )
        tab_numbers = {k: i + 1 for i, k in enumerate(tab_order)}
        self._add_custom_field_row(key, visible, labels, placement, tab_numbers)
        self._renumber_tab_order()
        self._rebuild_editor_groups()
        self._refresh_preview()
        self._record_history_state()

        if row.get("referential_code"):
            QMessageBox.information(
                self, "Champ créé",
                f"Le champ « {label} » a été créé avec son référentiel associé.\n\n"
                "Ses valeurs pourront être gérées dans l’Atelier Référentiels."
            )

    def _edit_custom_field(self, key: str) -> None:
        definition = self._custom_field_defs.get(str(key))
        if not definition:
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Modifier le champ")
        layout = QVBoxLayout(dialog)
        grid = QGridLayout()

        grid.addWidget(QLabel("Nom du champ :"), 0, 0)
        name_edit = QLineEdit(str(definition.get("label") or ""))
        grid.addWidget(name_edit, 0, 1)

        old_type = str(definition.get("field_type") or "text")
        try:
            has_data = self.manager.custom_field_has_data(self.collection_id, key)
        except Exception:
            has_data = True

        grid.addWidget(QLabel("Type :"), 1, 0)
        type_combo = QComboBox()
        for text, value in (
            ("Texte", "text"),
            ("Nombre", "numeric"),
            ("Date", "date"),
            ("Oui / Non (On / Off)", "boolean"),
            ("Lien (Internet ou autre)", "link"),
            ("Monétaire", "currency"),
            ("Liste déroulante (référentiel)", "list"),
            ("Calculé", "calculated"),
        ):
            type_combo.addItem(text, value)
        type_index = type_combo.findData(old_type)
        if type_index >= 0:
            type_combo.setCurrentIndex(type_index)
        # 39.32.2 — un champ personnalisé/importé n'est plus verrouillé parce
        # qu'il contient des données. MM3 testera la compatibilité au moment
        # d'enregistrer la modification.
        type_combo.setEnabled(True)
        type_combo.setToolTip(
            "Le changement de type est autorisé si toutes les valeurs existantes "
            "peuvent être converties sans perte."
        )
        grid.addWidget(type_combo, 1, 1)

        date_label = QLabel("Format d'affichage :")
        grid.addWidget(date_label, 2, 0)
        date_combo = QComboBox()
        date_combo.addItems([
            "JJ/MM/AAAA", "JJ/MM/AA", "MM/AAAA", "AAAA", "AAAA-MM-JJ"
        ])
        date_combo.setCurrentText(
            str(definition.get("date_format") or "JJ/MM/AAAA")
        )
        grid.addWidget(date_combo, 2, 1)

        default_label = QLabel("Valeur par défaut :")
        grid.addWidget(default_label, 3, 0)
        default_edit = QComboBox()
        default_edit.setEditable(True)
        default_edit.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._fill_default_combo(
            default_edit, old_type, key,
            str(self._field_styles.get(key, {}).get("default_value", "") or "")
        )
        grid.addWidget(default_edit, 3, 1)

        currency_label = QLabel("Devise :")
        currency_combo = QComboBox()
        currency_combo.setEditable(True)
        currency_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        currency_combo.addItems(["€", "$", "£", "CHF", "¥", "CAD", "AUD"])
        current_currency = str(
            self._field_styles.get(key, {}).get("currency_symbol", "€") or "€"
        )
        currency_combo.setCurrentText(current_currency)
        if currency_combo.lineEdit() is not None:
            currency_combo.lineEdit().setPlaceholderText("€ ou saisie libre")
        grid.addWidget(currency_label, 4, 0)
        grid.addWidget(currency_combo, 4, 1)

        currency_decimals_label = QLabel("Décimales :")
        currency_decimals_spin = QSpinBox()
        currency_decimals_spin.setRange(0, 4)
        try:
            current_currency_decimals = int(self._field_styles.get(key, {}).get("currency_decimals", 2))
        except Exception:
            current_currency_decimals = 2
        currency_decimals_spin.setValue(max(0, min(4, current_currency_decimals)))
        grid.addWidget(currency_decimals_label, 5, 0)
        grid.addWidget(currency_decimals_spin, 5, 1)

        # Paramètres du champ calculé.
        calc_label = QLabel("Formule :")
        calc_edit = QLineEdit()
        calc_edit.setPlaceholderText("Ex. ([Prix] * 20 / 100) + 25")
        calculation_formula = str(definition.get("calculation_formula") or "")

        field_choices = []
        try:
            for fkey in self._checks.keys():
                fkey = str(fkey)
                if fkey == str(key) or fkey == "record_number":
                    continue
                spec = self._field_spec(fkey)
                if spec is None:
                    continue
                flabel = str(
                    self._labels.get(fkey).text()
                    if fkey in self._labels else getattr(spec, "label", fkey)
                ).strip()
                if flabel:
                    field_choices.append((flabel, fkey))
        except Exception:
            field_choices = []

        # Afficher à l'utilisateur les libellés, pas les clés internes.
        visible_formula = calculation_formula
        for flabel, fkey in sorted(field_choices, key=lambda item: len(item[1]), reverse=True):
            visible_formula = visible_formula.replace("{" + fkey + "}", "[" + flabel + "]")
        calc_edit.setText(visible_formula)
        grid.addWidget(calc_label, 6, 0)
        grid.addWidget(calc_edit, 6, 1)

        insert_label = QLabel("Insérer un champ :")
        insert_combo = QComboBox()
        insert_combo.addItem("— choisir —", "")
        for flabel, fkey in sorted(field_choices, key=lambda item: item[0].casefold()):
            insert_combo.addItem(flabel, fkey)

        def insert_calc_field(_index):
            fkey = str(insert_combo.currentData() or "")
            if not fkey:
                return
            flabel = insert_combo.currentText()
            cursor = calc_edit.cursorPosition()
            token = "[" + flabel + "]"
            text = calc_edit.text()
            calc_edit.setText(text[:cursor] + token + text[cursor:])
            calc_edit.setCursorPosition(cursor + len(token))
            insert_combo.setCurrentIndex(0)

        insert_combo.currentIndexChanged.connect(insert_calc_field)
        grid.addWidget(insert_label, 7, 0)
        grid.addWidget(insert_combo, 7, 1)

        format_label = QLabel("Format du résultat :")
        calc_format_combo = QComboBox()
        calc_format_combo.addItem("Arrondi à l’entier", "round")
        calc_format_combo.addItem("Sans décimales (sans arrondi)", "truncate0")
        calc_format_combo.addItem("2 décimales (sans arrondi)", "truncate2")
        current_calc_format = str(
            definition.get("calculation_format") or "truncate2"
        )
        format_index = calc_format_combo.findData(current_calc_format)
        if format_index >= 0:
            calc_format_combo.setCurrentIndex(format_index)
        grid.addWidget(format_label, 8, 0)
        grid.addWidget(calc_format_combo, 8, 1)

        suffix_label = QLabel("Suffixe du résultat :")
        suffix_combo = QComboBox()
        suffix_combo.setEditable(True)
        suffix_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        suffix_combo.addItems([
            "", "€", "$", "£", "CHF", "¥",
            "g", "kg", "mg", "lb", "oz",
            "mm", "cm", "m", "km",
            "mL", "cL", "L",
            "%", "pcs"
        ])
        suffix_combo.setCurrentText(
            str(self._field_styles.get(key, {}).get("result_suffix", "") or "")
        )
        if suffix_combo.lineEdit() is not None:
            suffix_combo.lineEdit().setPlaceholderText("Ex. €, kg, lb, cm… ou libre")
        grid.addWidget(suffix_label, 9, 0)
        grid.addWidget(suffix_combo, 9, 1)

        def refresh_options():
            current_type = str(type_combo.currentData())
            is_date = current_type == "date"
            date_label.setVisible(is_date)
            date_combo.setVisible(is_date)
            date_combo.setEnabled(is_date)

            is_calc = current_type == "calculated"
            for w in (
                calc_label, calc_edit, insert_label, insert_combo,
                format_label, calc_format_combo, suffix_label, suffix_combo
            ):
                w.setVisible(is_calc)
                w.setEnabled(is_calc)

            default_label.setVisible(not is_calc)
            default_edit.setVisible(not is_calc)
            default_label.setEnabled(not is_calc)
            default_edit.setEnabled(not is_calc)

            is_currency = current_type == "currency"
            currency_label.setVisible(is_currency)
            currency_label.setEnabled(is_currency)
            currency_combo.setVisible(is_currency)
            currency_combo.setEnabled(is_currency)
            currency_decimals_label.setVisible(is_currency)
            currency_decimals_label.setEnabled(is_currency)
            currency_decimals_spin.setVisible(is_currency)
            currency_decimals_spin.setEnabled(is_currency)

            if not is_calc:
                self._fill_default_combo(
                    default_edit, current_type, key, default_edit.currentText()
                )

        type_combo.currentIndexChanged.connect(refresh_options)
        refresh_options()

        if has_data:
            note = QLabel(
                "Ce champ contient déjà des données. Son type peut maintenant être modifié : "
                "MM3 vérifiera toutes les valeurs avant conversion et refusera toute opération "
                "qui risquerait d'en perdre. Texte → Liste crée automatiquement le référentiel."
            )
            note.setWordWrap(True)
            note.setStyleSheet("color:#7B3328; font-weight:600;")
            grid.addWidget(note, 10, 0, 1, 2)

        layout.addLayout(grid)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Enregistrer")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Annuler")
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        new_type = str(type_combo.currentData())
        new_formula = ""
        if new_type == "calculated":
            new_formula = calc_edit.text().strip()
            for flabel, fkey in sorted(
                field_choices, key=lambda item: len(item[0]), reverse=True
            ):
                new_formula = new_formula.replace(
                    "[" + flabel + "]", "{" + fkey + "}"
                )
            if new_formula:
                try:
                    validate_calculation_formula(new_formula)
                except (SyntaxError, ValueError) as exc:
                    QMessageBox.warning(self, "Formule incorrecte", f"Vérifiez la formule : {exc}")
                    return

        if new_type != old_type:
            try:
                analysis = self.manager.analyze_custom_field_type_change(
                    self.collection_id,
                    key,
                    new_type,
                    date_combo.currentText() if new_type == "date" else "JJ/MM/AAAA",
                )
            except Exception as exc:
                QMessageBox.critical(self, "Analyse impossible", str(exc))
                return

            if not bool(analysis.get("compatible")):
                reason = str(analysis.get("reason") or "").strip()
                invalid = list(analysis.get("invalid") or [])
                details = ""
                if invalid:
                    details = "\n\nValeurs incompatibles (exemples) :\n" + "\n".join(
                        "• " + str(value) for value in invalid[:12]
                    )
                QMessageBox.warning(
                    self,
                    "Conversion impossible",
                    (reason or
                     "Toutes les valeurs existantes ne sont pas compatibles avec le nouveau type.")
                    + details
                    + "\n\nAucune donnée n'a été modifiée."
                )
                return

            total = int(analysis.get("total") or 0)
            if total:
                type_names = {
                    "text": "Texte", "numeric": "Nombre", "date": "Date",
                    "boolean": "Oui / Non", "link": "Lien",
                    "currency": "Monétaire", "list": "Liste / Référentiel",
                    "calculated": "Calculé",
                }
                extra = (
                    "\n\nLe référentiel sera automatiquement créé à partir des "
                    "valeurs distinctes déjà présentes."
                    if new_type == "list" else ""
                )
                confirm = QMessageBox(self)
                confirm.setIcon(QMessageBox.Icon.Question)
                confirm.setWindowTitle("Confirmer la conversion")
                confirm.setText(
                    f"Les {total} valeur(s) non vide(s) du champ sont compatibles.\n\n"
                    f"Convertir « {definition.get('label', '')} » de "
                    f"{type_names.get(old_type, old_type)} vers "
                    f"{type_names.get(new_type, new_type)} ?"
                    + extra
                )
                yes_button = confirm.addButton("Oui", QMessageBox.ButtonRole.YesRole)
                no_button = confirm.addButton("Non", QMessageBox.ButtonRole.NoRole)
                confirm.setDefaultButton(no_button)
                confirm.exec()
                if confirm.clickedButton() is not yes_button:
                    return

        try:
            updated = self.manager.update_custom_field(
                self.collection_id,
                key,
                label=name_edit.text(),
                date_format=(
                    date_combo.currentText() if new_type == "date" else None
                ),
                field_type=new_type,
                calculation_formula=new_formula if new_type == "calculated" else None,
                calculation_format=(
                    str(calc_format_combo.currentData())
                    if new_type == "calculated" else None
                ),
            )
        except Exception as exc:
            QMessageBox.critical(
                self, "Modification impossible", str(exc)
            )
            return

        self._custom_field_defs[key] = dict(updated)
        style = dict(self._field_styles.get(key, {}))

        if new_type == "calculated":
            style.pop("default_value", None)
            style.pop("currency_symbol", None)
            style.pop("currency_decimals", None)
            style["result_suffix"] = suffix_combo.currentText().strip()
        else:
            style.pop("result_suffix", None)
            default_value = default_edit.currentText().strip()
            style["default_value"] = default_value
            if new_type == "currency":
                style["currency_symbol"] = currency_combo.currentText().strip() or "€"
                style["currency_decimals"] = int(currency_decimals_spin.value())
            else:
                style.pop("currency_symbol", None)
                style.pop("currency_decimals", None)
            if new_type == "list":
                self._add_default_to_referential(
                    updated.get("referential_code"), default_value
                )

        self._field_styles[key] = style
        self._model_was_saved = True

        # Un champ qui cesse d'être une liste déroulante ne peut plus rester Maître.
        if key in self._field_masters and new_type != "list":
            self._field_masters.discard(key)
            self._field_links = {
                linked: master for linked, master in self._field_links.items()
                if master != key
            }

        if key in self._labels:
            self._labels[key].setText(str(updated.get("label") or ""))
        if key in self._checks:
            label = str(updated.get("label") or "")
            if new_type == "calculated":
                label += " (calculé)"
            self._checks[key].setText(label)

        self._refresh_preview()
        self._record_history_state()

    def _edit_existing_field(self, key: str) -> None:
        """Modifie un champ historique de CETTE collection.

        11.4.27 — correction globale : les anciens champs métier ne sont plus
        condamnés à rester des champs "spéciaux" MM3. Tant qu'ils ne
        contiennent aucune donnée, un changement de type les convertit en un
        vrai champ personnalisé, à la même place, avec le même style et le même
        ordre de tabulation. La vraie Fiche bénéficie alors automatiquement du
        moteur générique des champs personnalisés (texte, liste, date, etc.).
        """
        key = str(key)
        if key in {"record_number", "photo_data"}:
            return
        spec = self._field_spec(key)
        if spec is None:
            return

        current = (
            self._labels[key].text().strip()
            if key in self._labels
            else str(spec.label)
        ) or str(spec.label)

        native_type = str(getattr(spec, "field_type", "text") or "text")
        if getattr(spec, "referential", None):
            native_type = "list"
        if native_type == "number":
            native_type = "numeric"
        # Prix et Coût total sont des champs historiques monétaires.
        # Les conserver évite de perdre le calcul automatique de Coût total.
        if key in {"price", "total_cost"}:
            native_type = "currency"
        if native_type not in {"text", "numeric", "date", "boolean", "list", "link", "currency"}:
            native_type = "text"

        try:
            has_data = self.manager.standard_field_has_data(self.collection_id, key)
        except Exception:
            has_data = True

        dialog = QDialog(self)
        dialog.setWindowTitle("Modifier le champ")
        layout = QVBoxLayout(dialog)
        form = QGridLayout()
        form.addWidget(QLabel("Nom du champ :"), 0, 0)
        name_edit = QLineEdit(current)
        name_edit.selectAll()
        form.addWidget(name_edit, 0, 1)

        form.addWidget(QLabel("Type :"), 1, 0)
        type_combo = QComboBox()
        for text, value in (
            ("Texte", "text"),
            ("Nombre", "numeric"),
            ("Date", "date"),
            ("Oui / Non (On / Off)", "boolean"),
            ("Lien (Internet ou autre)", "link"),
            ("Monétaire", "currency"),
            ("Liste déroulante (référentiel)", "list"),
        ):
            type_combo.addItem(text, value)
        idx = type_combo.findData(native_type)
        if idx >= 0:
            type_combo.setCurrentIndex(idx)
        type_combo.setEnabled(True)
        type_combo.setToolTip(
            "Le changement de type est autorisé si toutes les valeurs existantes "
            "peuvent être converties sans perte."
        )
        form.addWidget(type_combo, 1, 1)

        form.addWidget(QLabel("Format d'affichage :"), 2, 0)
        date_combo = QComboBox()
        date_combo.addItems(["JJ/MM/AAAA", "JJ/MM/AA", "MM/AAAA", "AAAA", "AAAA-MM-JJ"])
        form.addWidget(date_combo, 2, 1)

        standard_fallback_defaults = {
            "minimum_magnification": "20 X",
            "type_locality": "Non",
            "box_count": "1",
            "price": "0.00 €",
            "total_cost": "0.00 €",
        }
        current_default = self._field_styles.get(key, {}).get(
            "default_value", standard_fallback_defaults.get(key, "")
        )
        form.addWidget(QLabel("Valeur par défaut :"), 3, 0)
        default_edit = QComboBox()
        default_edit.setEditable(True)
        default_edit.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._fill_default_combo(default_edit, native_type, key, str(current_default or ""))
        form.addWidget(default_edit, 3, 1)

        currency_label = QLabel("Devise :")
        currency_combo = QComboBox()
        currency_combo.setEditable(True)
        currency_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        currency_combo.addItems(["€", "$", "£", "CHF", "¥", "CAD", "AUD"])
        current_currency = str(self._field_styles.get(key, {}).get("currency_symbol", "€") or "€")
        currency_combo.setCurrentText(current_currency)
        if currency_combo.lineEdit() is not None:
            currency_combo.lineEdit().setPlaceholderText("€ ou saisie libre")
        form.addWidget(currency_label, 4, 0)
        form.addWidget(currency_combo, 4, 1)

        currency_decimals_label = QLabel("Décimales :")
        currency_decimals_spin = QSpinBox()
        currency_decimals_spin.setRange(0, 4)
        try:
            current_currency_decimals = int(self._field_styles.get(key, {}).get("currency_decimals", 2))
        except Exception:
            current_currency_decimals = 2
        currency_decimals_spin.setValue(max(0, min(4, current_currency_decimals)))
        form.addWidget(currency_decimals_label, 5, 0)
        form.addWidget(currency_decimals_spin, 5, 1)

        def refresh_date_options():
            is_date = str(type_combo.currentData()) == "date"
            date_combo.setVisible(is_date)
            label_widget = form.itemAtPosition(2, 0).widget()
            if label_widget is not None:
                label_widget.setVisible(is_date)
            is_currency = str(type_combo.currentData()) == "currency"
            currency_label.setVisible(is_currency)
            currency_label.setEnabled(is_currency)
            currency_combo.setVisible(is_currency)
            currency_combo.setEnabled(is_currency)
            currency_decimals_label.setVisible(is_currency)
            currency_decimals_label.setEnabled(is_currency)
            currency_decimals_spin.setVisible(is_currency)
            currency_decimals_spin.setEnabled(is_currency)
            self._fill_default_combo(
                default_edit, str(type_combo.currentData()), key, default_edit.currentText()
            )

        type_combo.currentIndexChanged.connect(refresh_date_options)
        refresh_date_options()

        if has_data:
            note = QLabel(
                "Ce champ contient déjà des données. MM3 peut désormais changer son type "
                "si toutes les valeurs sont compatibles. Les données sont alors migrées "
                "vers le nouveau champ sans supprimer la colonne historique d'origine."
            )
            note.setWordWrap(True)
            note.setStyleSheet("color:#7B3328; font-weight:600;")
            form.addWidget(note, 6, 0, 1, 2)

        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Enregistrer")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Annuler")
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        new_label = name_edit.text().strip()
        if not new_label:
            QMessageBox.warning(self, "Modifier le champ", "Le nom du champ ne peut pas être vide.")
            return
        new_type = str(type_combo.currentData() or native_type)

        # Un simple renommage conserve le champ historique et donc sa colonne
        # de données. Seul un vrai changement de type déclenche la conversion.
        if new_type == native_type:
            if key in self._labels:
                self._labels[key].setText(new_label)
            if key in self._checks:
                self._checks[key].setText(new_label)
            field = self._preview_fields.get(key)
            if field is not None:
                field.set_label(new_label)
            style = dict(self._field_styles.get(key, {}))
            style["default_value"] = default_edit.currentText().strip()
            if new_type == "currency":
                style["currency_symbol"] = currency_combo.currentText().strip() or "€"
                style["currency_decimals"] = int(currency_decimals_spin.value())
            else:
                style.pop("currency_symbol", None)
                style.pop("currency_decimals", None)
            self._field_styles[key] = style
            if new_type == "list":
                self._add_default_to_referential(getattr(spec, "referential", None), default_edit.currentText())
            self._refresh_preview()
            self._record_history_state()
            return

        # 39.32.3 — la règle de conversion sûre s'applique également aux
        # champs historiques de toutes les collections MM3, quelle que soit leur
        # origine. On analyse AVANT de créer le champ remplaçant.
        try:
            analysis = self.manager.analyze_standard_field_type_change(
                self.collection_id,
                key,
                new_type,
                date_combo.currentText() if new_type == "date" else "JJ/MM/AAAA",
            )
        except Exception as exc:
            QMessageBox.critical(self, "Analyse impossible", str(exc))
            return

        if not bool(analysis.get("compatible")):
            invalid = list(analysis.get("invalid") or [])
            details = ""
            if invalid:
                details = "\n\nValeurs incompatibles (exemples) :\n" + "\n".join(
                    "• " + str(value) for value in invalid[:12]
                )
            QMessageBox.warning(
                self,
                "Conversion impossible",
                str(analysis.get("reason") or
                    "Toutes les valeurs existantes ne sont pas compatibles avec le nouveau type.")
                + details
                + "\n\nAucune donnée n'a été modifiée."
            )
            return

        total = int(analysis.get("total") or 0)
        if total:
            type_names = {
                "text": "Texte", "numeric": "Nombre", "date": "Date",
                "boolean": "Oui / Non", "link": "Lien",
                "currency": "Monétaire", "list": "Liste / Référentiel",
            }
            extra = (
                "\n\nLe référentiel sera automatiquement constitué à partir "
                "des valeurs distinctes présentes dans les fiches."
                if new_type == "list" else ""
            )
            confirm = QMessageBox(self)
            confirm.setIcon(QMessageBox.Icon.Question)
            confirm.setWindowTitle("Confirmer la conversion")
            confirm.setText(
                f"Les {total} valeur(s) non vide(s) sont compatibles.\n\n"
                f"Convertir « {current} » de {type_names.get(native_type, native_type)} "
                f"vers {type_names.get(new_type, new_type)} ?"
                + extra
            )
            yes_button = confirm.addButton("Oui", QMessageBox.ButtonRole.YesRole)
            no_button = confirm.addButton("Non", QMessageBox.ButtonRole.NoRole)
            confirm.setDefaultButton(no_button)
            confirm.exec()
            if confirm.clickedButton() is not yes_button:
                return

        try:
            block_name, _ = self._field_block_and_position(key)
            if block_name not in self._palette_group_names():
                block_name = "Identification"
            row = self.manager.create_custom_field(
                self.collection_id, new_label, new_type, block_name,
                date_combo.currentText() if new_type == "date" else "JJ/MM/AAAA",
            )
        except Exception as exc:
            QMessageBox.critical(self, "Modification impossible", str(exc))
            return

        new_key = str(row["field_key"])
        self._custom_field_defs[new_key] = dict(row)

        try:
            self.manager.migrate_standard_field_to_custom(
                self.collection_id,
                key,
                new_key,
                new_type,
                date_combo.currentText() if new_type == "date" else "JJ/MM/AAAA",
            )
        except Exception as exc:
            # Le champ vient juste d'être créé : le supprimer si la migration
            # échoue afin de laisser la collection exactement comme avant.
            try:
                self.manager.delete_custom_field(self.collection_id, new_key)
            except Exception:
                pass
            self._custom_field_defs.pop(new_key, None)
            QMessageBox.critical(
                self,
                "Conversion impossible",
                "La migration des données n'a pas pu être effectuée. "
                "La collection n'a pas été modifiée.\n\n" + str(exc)
            )
            return

        # Reprendre exactement l'apparence et la géométrie du champ remplacé.
        if key in self._visual_positions:
            self._visual_positions[new_key] = tuple(self._visual_positions[key])
        if key in self._visual_sizes:
            self._visual_sizes[new_key] = tuple(self._visual_sizes[key])
        if key in self._field_styles:
            self._field_styles[new_key] = dict(self._field_styles[key])
        new_style = dict(self._field_styles.get(new_key, {}))
        new_style["default_value"] = default_edit.currentText().strip()
        if new_type == "currency":
            new_style["currency_symbol"] = currency_combo.currentText().strip() or "€"
            new_style["currency_decimals"] = int(currency_decimals_spin.value())
        else:
            new_style.pop("currency_symbol", None)
            new_style.pop("currency_decimals", None)
        self._field_styles[new_key] = new_style
        if new_type == "list":
            self._add_default_to_referential(row.get("referential_code"), default_edit.currentText())
        old_style = dict(self._field_styles.get(key, {}))
        old_style["field_deleted"] = True
        self._field_styles[key] = old_style

        # Conserver autant que possible l'ordre de tabulation.
        old_tab = self._tab_positions.get(key)
        old_tab_value = old_tab.value() if old_tab is not None else None

        # Remapper les relations si le nouveau champ reste compatible avec une liste.
        if key in self._field_masters:
            self._field_masters.discard(key)
            if new_type == "list":
                self._field_masters.add(new_key)
        remapped_links = {}
        for linked, master in self._field_links.items():
            linked2 = new_key if linked == key else linked
            master2 = new_key if master == key else master
            if master2 == new_key and new_type != "list":
                continue
            remapped_links[linked2] = master2
        self._field_links = remapped_links

        # Retirer visuellement l'ancien champ de cette collection.
        check = self._checks.get(key)
        if check is not None:
            check.blockSignals(True); check.setChecked(False); check.blockSignals(False)
        old_field = self._preview_fields.get(key)
        if old_field is not None:
            old_field.hide()
        old_row = self._rows.get(key)
        if old_row is not None:
            old_row.hide()
        self._selected_preview_keys.discard(key)
        self._selected_preview_parts = {item for item in self._selected_preview_parts if item[0] != key}
        if self._selected_preview_key == key:
            self._selected_preview_key = None

        placement = self.manager.field_placement(self.collection_id)
        visible = self.manager.visible_fields(self.collection_id) | {new_key}
        labels = self.manager.custom_labels(self.collection_id)
        tab_order = self.manager.tab_order(self.collection_id, self._visual_order_from_placement(placement))
        tab_numbers = {k: i + 1 for i, k in enumerate(tab_order)}
        if old_tab_value is not None:
            tab_numbers[new_key] = old_tab_value
        self._add_custom_field_row(new_key, visible, labels, placement, tab_numbers)
        if old_tab_value is not None and new_key in self._tab_positions:
            self._tab_positions[new_key].setValue(old_tab_value)

        self._renumber_tab_order()
        self._rebuild_editor_groups()
        self._refresh_preview()
        self._record_history_state()

    def _install_palette_field_context_menu(self, widget: QWidget, key: str) -> None:
        """Ajoute la suppression du champ directement depuis la palette.

        11.7.67 — un champ retiré de la Fiche restait jusque-là difficile à
        supprimer puisqu'il n'était plus cliquable dans l'aperçu. La palette
        devient donc l'endroit de référence pour sa suppression de la collection.
        """
        if widget is None:
            return
        widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        widget.customContextMenuRequested.connect(
            lambda pos, w=widget, k=str(key): self._show_palette_field_context_menu(
                k, w.mapToGlobal(pos)
            )
        )

    def _show_palette_field_context_menu(self, key: str, global_pos) -> None:
        key = str(key)
        if key in {"record_number", "record_state", "photo_data"}:
            return
        spec = self._field_spec(key)
        if spec is None:
            return
        menu = QMenu(self)
        action = menu.addAction(tr("Supprimer définitivement le champ de la collection…", self.language))
        if key in self._custom_field_defs:
            action.triggered.connect(
                lambda checked=False, k=key: self._delete_custom_field(k)
            )
        else:
            action.triggered.connect(
                lambda checked=False, k=key: self._delete_existing_field(k)
            )
        menu.exec(global_pos)

    def _delete_existing_field(self, key: str) -> None:
        """Retire un champ historique de CETTE collection sans toucher au schéma MM3."""
        key = str(key)
        if key in {"record_number", "record_state", "photo_data"}:
            return
        spec = self._field_spec(key)
        if spec is None:
            return
        label = (
            self._labels[key].text().strip()
            if key in self._labels else str(spec.label)
        ) or str(spec.label)

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle("Supprimer le champ")
        box.setText(f"Supprimer le champ « {label} » de cette collection ?")
        box.setInformativeText(
            "Le champ sera retiré du modèle de cette collection. "
            "Cette opération ne modifie pas la structure interne de MM3."
        )
        yes_button = box.addButton("Oui", QMessageBox.ButtonRole.YesRole)
        no_button = box.addButton("Non", QMessageBox.ButtonRole.NoRole)
        box.setDefaultButton(no_button)
        box.exec()
        if box.clickedButton() is not yes_button:
            return

        # Un champ supprimé ne doit conserver aucune relation Maître / Relié à.
        # C'est notamment indispensable pour l'ancien champ « Localité type »
        # du modèle Minéraux, historiquement relié au champ Espèce/Nom.
        self._field_masters.discard(key)
        self._field_links = {
            linked: master for linked, master in self._field_links.items()
            if linked != key and master != key
        }

        check = self._checks.get(key)
        if check is not None:
            check.blockSignals(True)
            check.setChecked(False)
            check.blockSignals(False)

        style = dict(self._field_styles.get(key, {}))
        style["field_deleted"] = True
        self._field_styles[key] = style

        field = self._preview_fields.get(key)
        if field is not None:
            field.hide()

        self._selected_preview_keys.discard(key)
        self._selected_preview_parts = {
            item for item in self._selected_preview_parts if item[0] != key
        }
        if self._selected_preview_key == key:
            self._selected_preview_key = None

        # La palette ne doit plus afficher un champ supprimé.
        row = self._rows.get(key)
        if row is not None:
            row.hide()

        self._refresh_preview()
        self._record_history_state()

    def _delete_custom_field(self, key: str) -> None:
        definition = self._custom_field_defs.get(str(key))
        if not definition:
            return
        label = str(definition.get("label") or key)
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle("Supprimer le champ")
        box.setText(
            f"Supprimer définitivement le champ « {label} » et les données qu'il contient ?"
        )
        yes_button = box.addButton("Oui", QMessageBox.ButtonRole.YesRole)
        no_button = box.addButton("Non", QMessageBox.ButtonRole.NoRole)
        box.setDefaultButton(no_button)
        box.exec()
        if box.clickedButton() is not yes_button:
            return
        try:
            self.manager.delete_custom_field(self.collection_id, key)
        except Exception as exc:
            QMessageBox.critical(self, "Suppression impossible", str(exc)); return
        self._custom_field_defs.pop(key, None)
        self._visual_positions.pop(key, None); self._visual_sizes.pop(key, None); self._field_styles.pop(key, None)
        self._selected_preview_keys.discard(key)
        self._selected_preview_key = None if self._selected_preview_key == key else self._selected_preview_key
        for mapping in (self._checks, self._labels, self._blocks, self._positions, self._tab_positions, self._rows):
            obj = mapping.pop(key, None)
            if hasattr(obj, "deleteLater"): obj.deleteLater()
        self._renumber_tab_order()
        self._rebuild_editor_groups_preserving_view(); self._refresh_preview(); self._record_history_state()

    def _add_custom_field_row(
        self, key: str, visible: set[str], custom_labels: dict[str, str],
        placement: dict[str, tuple[str, int]], initial_tab_numbers: dict[str, int],
    ) -> None:
        if key in self._rows:
            return
        spec = self._field_spec(key)
        if spec is None:
            return

        row_widget = QWidget()
        row_layout = QGridLayout(row_widget)
        row_layout.setContentsMargins(1, 0, 1, 0)
        row_layout.setHorizontalSpacing(6)
        row_layout.setVerticalSpacing(0)

        _raw_label = str(custom_labels.get(key, spec.label) or spec.label)
        if key == "record_state" and _raw_label == "État de la fiche":
            _raw_label = "Etat de la fiche"
        palette_label = self._t(_raw_label) if _raw_label == "Coût total" else _raw_label
        if str(self._custom_field_defs.get(key, {}).get("field_type") or "") == "calculated":
            palette_label += " " + self._t("(calculé)")
        check = QCheckBox(palette_label)
        check.setChecked(key in visible)
        check.setMinimumWidth(120)
        check.setMaximumWidth(190)
        self._checks[key] = check

        label_edit = QLineEdit(self._t(_raw_label) if _raw_label == "Coût total" else _raw_label)
        label_edit.setPlaceholderText(self._t(str(spec.label)) if str(spec.label) == "Coût total" else str(spec.label))
        label_edit.setToolTip("Nom affiché sur la Fiche")
        label_edit.setMaximumWidth(245)
        self._labels[key] = label_edit
        relation_mark = QLabel("M" if key in self._field_masters else ("R" if key in self._field_links else ""))
        relation_mark.setFixedWidth(12)
        relation_mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if key in self._field_masters:
            mf = QFont(relation_mark.font()); mf.setBold(True); relation_mark.setFont(mf)
        relation_mark.setToolTip("Champ Maître" if key in self._field_masters else ("Champ Relié" if key in self._field_links else ""))
        self._relation_markers[key] = relation_mark
        field_cell = QWidget()
        field_cell_layout = QHBoxLayout(field_cell)
        field_cell_layout.setContentsMargins(0, 0, 0, 0); field_cell_layout.setSpacing(2)
        field_cell_layout.addWidget(relation_mark); field_cell_layout.addWidget(check, 1)
        row_layout.addWidget(field_cell, 0, 0)
        label_edit.hide()

        block_combo = QComboBox()
        block_combo.addItems(list(MODEL_BLOCKS))
        block, position = placement.get(
            key, (self._custom_field_defs[key].get("initial_group", "Identification"), 99)
        )
        if block in MODEL_BLOCKS:
            block_combo.setCurrentText(block)
        block_combo.hide()
        self._blocks[key] = block_combo
        position_spin = PositionSpinBox()
        position_spin.setRange(1, 999)
        position_spin.setValue(max(1, int(position) + 1))
        position_spin.hide()
        self._positions[key] = position_spin

        tab_spin = PositionSpinBox()
        tab_spin.setRange(1, 999)
        tab_spin.setValue(int(initial_tab_numbers.get(
            key, max(initial_tab_numbers.values(), default=0) + 1
        )))
        tab_spin.setFixedWidth(48)
        self._tab_positions[key] = tab_spin
        tab_spin.setParent(row_widget)
        tab_spin.hide()
        row_layout.setColumnStretch(0, 1)

        block_combo.currentTextChanged.connect(lambda _text, k=key: self._on_block_changed(k))
        tab_spin.valueChanged.connect(lambda _value, k=key: self._on_tab_position_changed(k))
        tab_spin.editingFinished.connect(lambda k=key: self._finish_tab_position_edit(k))
        check.toggled.connect(lambda _checked, k=key: self._on_visibility_changed(k))
        label_edit.textChanged.connect(self._refresh_preview)
        label_edit.editingFinished.connect(self._record_history_state)
        self._rows[key] = row_widget
        row_widget.setProperty("_mm3_palette_field_key", str(key))
        row_widget.setAcceptDrops(True)
        row_widget.setMouseTracking(True)
        row_widget.installEventFilter(self)
        check.setProperty("_mm3_palette_field_key", str(key))
        check.setAcceptDrops(True)
        check.setMouseTracking(True)
        check.installEventFilter(self)
        check.setToolTip((check.toolTip() + "\n" if check.toolTip() else "") +
                         "Cochez puis faites glisser cette ligne sur la fiche pour placer le champ.")
        self._install_palette_field_context_menu(row_widget, key)
        self._install_palette_field_context_menu(check, key)

    def _toggle_fields_palette(self) -> None:
        dlg = self._fields_palette_dialog
        if dlg is None:
            self._detach_fields_palette()
            return
        if not dlg.isVisible():
            dlg.show()
            dlg.raise_()
            self.detach_palette_btn.setText("⇲ " + self._t("Rattacher la palette des champs"))
            return
        self._attach_fields_palette()

    def _detach_fields_palette(self) -> None:
        if self._fields_palette_dialog is not None:
            return
        palette = self._fields_palette_widget
        splitter = self._model_splitter
        if palette is None or splitter is None:
            return

        # Fenêtre outil native : flottante et maintenue au-dessus de l'Atelier.
        # Conserver les dimensions réellement utilisées lorsqu'elle était attachée.
        attached_size = palette.size()
        attached_width = max(235, min(310, attached_size.width()))
        attached_height = max(360, attached_size.height())

        palette.setParent(None)
        # L'Atelier est ouvert par QDialog.exec() : sur Windows une Qt.Tool
        # peut se retrouver derriere la fenetre modale. Employer une vraie
        # fenetre enfant de l'Atelier, comme l'apercu de fiche deja fonctionnel.
        dlg = QWidget(self)
        dlg.setWindowFlag(Qt.WindowType.Window, True)
        dlg.setWindowTitle("G-Skol — Palette Champs")
        dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(6, 6, 6, 6)

        palette_head = QHBoxLayout()
        attach_btn = QPushButton("⇲ Rattacher à l'Atelier")
        attach_btn.clicked.connect(self._attach_fields_palette)
        palette_head.addWidget(attach_btn)
        palette_head.addStretch(1)

        # 23.2 — fermeture volontairement très visible pour un novice.
        close_palette_btn = QPushButton("✕")
        close_palette_btn.setToolTip("Fermer la palette flottante")
        close_palette_btn.setFixedSize(30, 30)
        close_palette_btn.setStyleSheet(
            "QPushButton { color:#FFFFFF; background:#C62828; "
            "border:1px solid #8E0000; border-radius:4px; "
            "font-size:18px; font-weight:bold; padding:0px; }"
            "QPushButton:hover { background:#E53935; }"
            "QPushButton:pressed { background:#8E0000; }"
        )
        close_palette_btn.clicked.connect(self._close_fields_palette)
        palette_head.addWidget(close_palette_btn)
        lay.addLayout(palette_head)
        lay.addWidget(palette, 1)

        self._fields_palette_dialog = dlg
        self.detach_palette_btn.setText("⇲ " + self._t("Rattacher la palette des champs"))
        # La barre supérieure ajoute seulement quelques pixels à la hauteur ;
        # aucune grande zone vide n'est créée à droite de la liste.
        dlg.resize(
            attached_width + 16,
            min(max(430, attached_height + 58), max(430, self.height() - 40)),
        )
        dlg.move(self.mapToGlobal(QPoint(12, 70)))
        dlg.show()
        dlg.raise_()

        # Toute la largeur libérée revient immédiatement à la maquette.
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

    def _close_fields_palette(self) -> None:
        """Ferme réellement la palette sans la rattacher à l'Atelier."""
        dlg = self._fields_palette_dialog
        if dlg is None:
            return
        dlg.hide()
        self.detach_palette_btn.setText("⇱ " + self._t("Afficher la palette des champs"))

    def _attach_fields_palette(self) -> None:
        dlg = self._fields_palette_dialog
        if dlg is None:
            return
        palette = self._fields_palette_widget
        if palette is None:
            return
        lay = dlg.layout()
        if lay is not None:
            lay.removeWidget(palette)
        palette.setParent(self._model_splitter)
        self._model_splitter.insertWidget(0, palette)
        palette.show()
        self._model_splitter.setStretchFactor(0, 2)
        self._model_splitter.setStretchFactor(1, 3)
        self._model_splitter.setSizes([610, 820])
        self._fields_palette_dialog = None
        self.detach_palette_btn.setText("⇱ " + self._t("Détacher la palette des champs"))
        dlg.hide()
        dlg.deleteLater()

    @staticmethod
    def _visual_order_from_placement(placement: dict[str, tuple[str, int]]) -> list[str]:
        """Ordre naturel de tabulation par défaut, basé sur la disposition de la fiche."""
        order: list[str] = []

        # Bandeau fixe, dans son ordre natif.
        for group_title, keys in GROUPS:
            if group_title == "Bandeau":
                order.extend(key for key in keys if key != "photo_data")
                break

        for block in MODEL_BLOCKS:
            entries = [
                (int(pos), key)
                for key, (target, pos) in placement.items()
                if target == block and key != "photo_data"
            ]
            entries.sort(key=lambda item: (item[0], item[1]))
            order.extend(key for _pos, key in entries)

        # Champs non mobiles/fixes hors bandeau qui pourraient ne pas être dans placement.
        for _group_title, keys in GROUPS:
            for key in keys:
                if key != "photo_data" and key not in order:
                    order.append(key)
        return order

    def _current_visual_order(self) -> list[str]:
        """Ordre visuel réel de la fiche : haut -> bas, puis gauche -> droite."""
        host = getattr(self, "_construction_widget", None)
        items = []

        for key in self._tab_positions:
            check = self._checks.get(key)
            if check is not None and not check.isChecked():
                continue

            field = self._preview_fields.get(key)
            if (
                field is not None
                and field.isVisible()
                and host is not None
            ):
                top_left = field.mapTo(host, QPoint(0, 0))
                x, y = int(top_left.x()), int(top_left.y())
            else:
                x, y = self._visual_positions.get(key, (0, 0))
                x, y = int(x), int(y)

            # Une "ligne visuelle" correspond à une ligne de la grille Atelier.
            # Cela évite qu'un décalage de quelques pixels inverse deux champs
            # qui sont manifestement sur la même ligne.
            grid_row = int(round(y / 20.0))
            items.append((grid_row, x, y, str(key)))

        items.sort(key=lambda item: (item[0], item[1], item[2], item[3]))
        return [key for _row, _x, _y, key in items]


    def _ordered_tab_keys(self, preferred_key: str | None = None) -> list[str]:
        keys = list(self._tab_positions)
        keys.sort(key=lambda k: (self._tab_positions[k].value(), k))
        if preferred_key in keys:
            requested = max(1, self._tab_positions[preferred_key].value())
            keys.remove(preferred_key)
            keys.insert(min(requested - 1, len(keys)), preferred_key)
        return keys

    def _renumber_tab_order(self, preferred_key: str | None = None) -> None:
        keys = self._ordered_tab_keys(preferred_key)
        self._history_guard = True
        try:
            for index, key in enumerate(keys, start=1):
                self._tab_positions[key].setValue(index)
        finally:
            self._history_guard = False

    def _on_tab_position_changed(self, key: str) -> None:
        if self._history_guard:
            return
        # Comme pour Position : on ajuste les numéros, sans déplacer les lignes.
        self._renumber_tab_order(preferred_key=key)
        # Chaque changement volontaire devient immédiatement annulable, y compris
        # lorsqu'il est fait avec les petites flèches du QSpinBox sans quitter le champ.
        self._record_history_state()

    def _finish_tab_position_edit(self, key: str) -> None:
        # Sécurité pour une saisie clavier directe ; _record_history_state ignore
        # automatiquement les doublons identiques au dernier état.
        self._record_history_state()

    def _reset_tab_to_visual(self) -> None:
        order = [
            key for key in self._current_visual_order()
            if key in self._tab_positions
        ]
        self._history_guard = True
        try:
            for index, key in enumerate(order, start=1):
                self._tab_positions[key].setValue(index)
        finally:
            self._history_guard = False

        # Le bouton signifie réellement "adopter cet ordre" :
        # on le mémorise tout de suite, sans attendre un autre changement.
        try:
            self.manager.set_tab_order(self.collection_id, order)
            self._model_was_saved = True
        except Exception as exc:
            QMessageBox.critical(
                self, "Tabulation impossible", str(exc)
            )
            return

        self._record_history_state()

    def _preview_scale(self) -> float:
        # Atelier volontairement compact : même présentation confortable que
        # la version validée, sans bouton "Ajuster à l'écran".
        return DISPLAY_SCALE

    def _clear_preview_selection(self) -> None:
        self._selected_preview_keys.clear()
        self._selected_preview_parts.clear()
        self._selected_preview_key = None
        self._whole_field_multi_selection = False
        for field in self._preview_fields.values():
            field._apply_selection_style(False)
            field.update()

    def _sync_preview_keys_from_parts(self) -> None:
        self._selected_preview_keys = {key for key, _part in self._selected_preview_parts}
        self._selected_preview_key = next(iter(self._selected_preview_keys), None)
        for key, field in self._preview_fields.items():
            field._apply_selection_style(key in self._selected_preview_keys)
            field.update()

    def _set_preview_selection(self, keys) -> None:
        self._selected_preview_parts = {
            (str(key), part) for key in keys for part in ("label", "data")
        }
        self._whole_field_multi_selection = bool(self._selected_preview_parts)
        self._sync_preview_keys_from_parts()

    def _set_preview_part_selection(self, parts, additive: bool = False) -> None:
        incoming = {(str(k), str(p)) for k,p in parts if p in {"label","data"}}
        if additive:
            for item in incoming:
                if item in self._selected_preview_parts:
                    self._selected_preview_parts.remove(item)
                else:
                    self._selected_preview_parts.add(item)
        else:
            self._selected_preview_parts = set(incoming)

        # Si chaque champ sélectionné possède ses deux parties, il s'agit
        # d'une sélection de champs complets (lasso global, Ctrl+clic champs).
        keys = {k for k, _p in self._selected_preview_parts}
        self._whole_field_multi_selection = bool(keys) and all(
            (k, "label") in self._selected_preview_parts
            and (k, "data") in self._selected_preview_parts
            for k in keys
        )
        self._sync_preview_keys_from_parts()

    def _selected_parts_of_kind(self, part: str):
        result = []
        for key, selected_part in self._selected_preview_parts:
            if selected_part != part:
                continue
            field = self._preview_fields.get(key)
            if field is not None and field.isVisible():
                result.append((field, QRect(self._field_part_sheet_rect(field, part))))
        return result

    def _apply_part_rect_batch(self, changes: dict[tuple[str, str], QRect]) -> None:
        """Applique plusieurs rectangles de parties en un seul passage."""
        touched = {key for key, _part in changes}
        snapshots = {}
        for key in touched:
            field = self._preview_fields.get(key)
            if field is None:
                continue
            snapshots[key] = {
                "label": QRect(self._field_part_sheet_rect(field, "label")),
                "data": QRect(self._field_part_sheet_rect(field, "data")),
            }

        for (key, part), rect in changes.items():
            if key in snapshots:
                snapshots[key][part] = QRect(rect)

        for key, pair in snapshots.items():
            field = self._preview_fields[key]
            self._set_two_part_rects(field, pair["label"], pair["data"])
            field.raise_()

    def _selected_part_kind(self, key: str) -> str:
        l=(key,"label") in self._selected_preview_parts
        d=(key,"data") in self._selected_preview_parts
        return "both" if l and d else "label" if l else "data" if d else ""

    def _nudge_selected_preview_fields(self, dx: int, dy: int) -> bool:
        """Déplace au pixel les champs sélectionnés, sans aucun ancien automatisme."""
        fields = self._selected_fields()
        if not fields:
            return False

        host = getattr(self, "_construction_widget", None)
        changed = False
        scale = max(0.01, float(self._preview_scale()))

        for field in fields:
            x = max(0, field.x() + int(dx))
            y = max(0, field.y() + int(dy))
            if host is not None:
                x = min(x, max(0, host.width() - field.width()))
                y = min(y, max(0, host.height() - field.height()))

            if x == field.x() and y == field.y():
                continue

            field.move(x, y)
            self._visual_positions[field.key] = (
                round(x / scale), round(y / scale)
            )
            changed = True

        if changed:
            self._raise_absolute_fields()
            self._record_history_state()
        return changed


    def _preview_keyboard_active(self) -> bool:
        """Vrai si les flèches doivent piloter la sélection de champs."""
        if not self._selected_preview_keys:
            return False
        focus = QApplication.focusWidget()
        construction = getattr(self, "_construction_widget", None)

        # Aucun focus précis après une opération Qt : la sélection reste l'autorité
        # tant que l'Atelier est la fenêtre active.
        if focus is None:
            return self.isActiveWindow()

        if focus is self:
            return True
        if construction is not None and (
            focus is construction or construction.isAncestorOf(focus)
        ):
            return True

        # Avec la sélection Libellé/Donnée, le focus peut être le QLabel enfant
        # plutôt que le DraggablePreviewField lui-même.
        # PySide6 peut exceptionnellement renvoyer un QWidgetItem ici.
        # isAncestorOf() n'accepte qu'un QWidget : filtrer avant l'appel.
        if isinstance(focus, QWidget):
            for field in self._selected_fields():
                if focus is field or field.isAncestorOf(focus):
                    return True
        return False

    def _select_preview_field(self, key: str, additive: bool = False) -> None:
        self._set_preview_part_selection([(key,"label"),(key,"data")], additive=additive)
        selected=self._preview_fields.get(self._selected_preview_key)
        if selected is not None and selected.isVisible():
            selected.setFocus(Qt.FocusReason.MouseFocusReason)


    def _selected_fields(self):
        return [self._preview_fields[k] for k in self._selected_preview_keys if k in self._preview_fields and self._preview_fields[k].isVisible()]

    def _align_selected(self, mode: str) -> None:
        fields = self._selected_fields()
        if not fields:
            return

        left_edge = min(f.x() for f in fields)
        right_edge = max(f.x() + f.width() for f in fields)
        top_edge = min(f.y() for f in fields)
        bottom_edge = max(f.y() + f.height() for f in fields)

        for f in fields:
            if mode == "left":
                f.move(left_edge, f.y())
            elif mode == "right":
                f.move(right_edge - f.width(), f.y())
            elif mode == "top":
                f.move(f.x(), top_edge)
            elif mode == "bottom":
                f.move(f.x(), bottom_edge - f.height())
            elif mode == "grid":
                s = MagneticCanvas.GRID_SNAP
                f.move(round(f.x()/s)*s, round(f.y()/s)*s)
            scale = self._preview_scale()
            self._visual_positions[f.key] = (round(f.x()/scale), round(f.y()/scale))
        self._sync_legacy_positions_from_visual()
        self._record_history_state()

    def _resize_selected_part_kind(self, part: str, mode: str) -> None:
        """Uniformise la largeur des Libellés OU des Données sélectionnés.

        Les deux parties du champ restent indépendantes : modifier la largeur
        des Données ne touche pas aux Libellés, et inversement.
        """
        items = []
        for key in self._selected_preview_keys:
            field = self._preview_fields.get(key)
            if field is None or not field.isVisible():
                continue
            rect = self._field_part_sheet_rect(field, part)
            items.append((field, QRect(rect)))

        if len(items) < 2:
            return

        widths = [rect.width() for _field, rect in items]
        if mode in {"widest", "largest"}:
            target_w = max(widths)
        elif mode in {"narrowest", "smallest"}:
            target_w = min(widths)
        elif mode == "grid":
            target_w = None
        else:
            return

        changes = {}
        for field, rect in items:
            nr = QRect(rect)

            if mode == "grid":
                step = max(1, int(MagneticCanvas.GRID_VISIBLE))
                new_w = max(20, round(nr.width() / step) * step)
            else:
                new_w = max(20, int(target_w))

            # Pour les Libellés, conserver leur bord DROIT : c'est le repère
            # naturel obtenu avec « Aligner > Libellés > Droite ».
            # Pour les Données, conserver leur bord GAUCHE : le début des zones
            # de saisie reste ainsi parfaitement aligné.
            if part == "label":
                right = nr.right()
                nr.setWidth(new_w)
                nr.moveRight(right)
            else:
                left = nr.left()
                nr.setWidth(new_w)
                nr.moveLeft(left)

            changes[(field.key, part)] = nr

        self._apply_part_rect_batch(changes)

        # 11.4.39.11 — NE PAS réaligner ensuite toutes les parties sur un
        # même bord. Cette ancienne seconde passe était correcte pour des
        # champs empilés verticalement, mais catastrophique pour deux champs
        # placés côte à côte : elle faisait glisser/étirer les zones jusqu'à
        # un bord commun. Chaque champ conserve désormais son propre ancrage ;
        # seule la largeur demandée est uniformisée.
        self._raise_absolute_fields()
        self._record_history_state()

    def _resize_whole_field_preserving_parts(
        self, field, width: int, height: int
    ) -> None:
        """Redimensionne un champ complet sans dérégler Libellé/Donnée.

        L'ancienne méthode faisait seulement field.resize(). Or les largeurs
        internes Libellé/Donnée sont mémorisées séparément : selon leur état
        précédent, Qt pouvait alors recomposer le champ différemment. Ici la
        géométrie interne est recalculée de façon déterministe.
        """
        scale = max(0.01, float(self._preview_scale()))
        width = max(field.MIN_W, int(width))
        height = max(field.MIN_H, int(height))

        label = QRect(field.part_rect("label"))
        data = QRect(field.part_rect("data"))

        # Conserver le libellé et le début de la donnée. La différence de
        # largeur est absorbée par la zone Donnée, comme dans Access.
        label_x = max(0, label.x())
        label_w = max(20, label.width())
        data_x = max(label_x + label_w, data.x())
        data_w = max(20, width - data_x)

        # Si le champ cible est trop étroit pour les valeurs internes actuelles,
        # réduire d'abord la donnée sans jamais écraser le libellé.
        minimum_width = data_x + 20
        if width < minimum_width:
            width = minimum_width
            data_w = 20

        field.setGeometry(
            field.x(), field.y(), width, height
        )
        field.set_part_geometry(
            label_x=round(label_x / scale),
            label_w=round(label_w / scale),
            data_x=round(data_x / scale),
            data_w=max(20, round(data_w / scale)),
        )
        self._visual_positions[field.key] = (
            round(field.x() / scale), round(field.y() / scale)
        )
        self._visual_sizes[field.key] = (
            round(width / scale), round(height / scale)
        )
        self._store_field_part_geometry(field)
        field.raise_()
        field.updateGeometry()
        field.update()

    def _size_selected(self, mode: str) -> None:
        """Redimensionnement collectif stable des champs complets."""
        fields = self._selected_fields()
        if not fields:
            return

        widths = [f.width() for f in fields]
        heights = [f.height() for f in fields]

        if mode == "largest":
            target_w, target_h = max(widths), max(heights)
        elif mode == "smallest":
            target_w, target_h = min(widths), min(heights)
        elif mode == "widest":
            target_w, target_h = max(widths), None
        elif mode == "narrowest":
            target_w, target_h = min(widths), None
        else:
            target_w = target_h = None

        for field in fields:
            w, h = field.width(), field.height()

            if mode == "content":
                hint = field.sizeHint()
                w = max(field.MIN_W, hint.width())
                h = max(field.MIN_H, hint.height())
            elif mode == "grid":
                step = max(1, int(MagneticCanvas.GRID_VISIBLE))
                w = max(field.MIN_W, round(w / step) * step)
                h = max(field.MIN_H, round(h / step) * step)
            else:
                if target_w is not None:
                    w = target_w
                if target_h is not None:
                    h = target_h

            self._resize_whole_field_preserving_parts(field, w, h)

        self._raise_absolute_fields()
        self._record_history_state()

    def _relation_field_label(self, key: str) -> str:
        edit = self._labels.get(str(key))
        if edit is not None and edit.text().strip():
            return edit.text().strip()
        spec = self._field_spec(str(key))
        return str(getattr(spec, "label", key) or key)

    def _can_be_master_field(self, key: str) -> bool:
        key = str(key)
        if key in {"record_number", "photo_data"}:
            return False
        spec = self._field_spec(key)
        if spec is None:
            return False
        if key in self._custom_field_defs:
            return str(self._custom_field_defs[key].get("field_type") or "") == "list"
        return bool(getattr(spec, "referential", None))

    def _activate_master_field(self, key: str) -> None:
        key = str(key)
        if not self._can_be_master_field(key):
            QMessageBox.information(
                self, "Champ maître",
                "Un champ Maître doit être une liste déroulante."
            )
            return
        if key in self._field_masters:
            return
        self._field_masters.add(key)
        self._refresh_field_styles()
        self._record_history_state()

    def _deactivate_master_field(self, key: str) -> None:
        key = str(key)
        if key not in self._field_masters:
            return
        self._field_masters.discard(key)
        # Un maître désactivé ne peut conserver de dépendances orphelines.
        self._field_links = {
            linked: master for linked, master in self._field_links.items()
            if master != key
        }
        self._refresh_field_styles()
        self._record_history_state()

    def _link_selected_fields_to_master(self, master_key: str) -> None:
        master_key = str(master_key)
        if master_key not in self._field_masters:
            return
        changed = False
        for key in set(self._selected_preview_keys):
            key = str(key)
            if key in {"record_number", "photo_data", master_key} or key in self._field_masters:
                continue
            if self._field_links.get(key) != master_key:
                self._field_links[key] = master_key
                changed = True
        if changed:
            self._refresh_field_styles()
            self._record_history_state()

    def _unlink_selected_fields_from_master(self, master_key: str) -> None:
        master_key = str(master_key)
        changed = False
        for key in set(self._selected_preview_keys):
            key = str(key)
            if self._field_links.get(key) == master_key:
                self._field_links.pop(key, None)
                changed = True
        if changed:
            self._refresh_field_styles()
            self._record_history_state()

    def _unlink_selected_fields(self) -> None:
        """Supprime toute liaison Maître des champs sélectionnés.

        Un champ précédemment relié redevient alors un champ totalement indépendant.
        """
        changed = False
        for key in set(self._selected_preview_keys):
            key = str(key)
            if key in self._field_links:
                self._field_links.pop(key, None)
                changed = True
        if changed:
            self._refresh_field_styles()
            self._record_history_state()

    def _add_field_relations_menu(self, menu: QMenu) -> None:
        selected = {str(k) for k in self._selected_preview_keys}
        if not selected:
            return
        relations = menu.addMenu(tr('Liaisons de champs', self.language))

        # Maître / Désactiver Maître : exclusivement sur UN champ.
        if len(selected) == 1:
            key = next(iter(selected))
            if key in self._field_masters:
                action = relations.addAction(tr('Désactiver Maître', self.language))
                action.triggered.connect(
                    lambda checked=False, k=key: self._deactivate_master_field(k)
                )
            else:
                action = relations.addAction(tr('Définir comme Maître', self.language))
                action.setEnabled(self._can_be_master_field(key))
                action.triggered.connect(
                    lambda checked=False, k=key: self._activate_master_field(k)
                )
            relations.addSeparator()

        # Relié à / Délier de : actions volontairement compatibles avec une
        # sélection multiple obtenue au lasso ou par Ctrl+clic.
        link_menu = relations.addMenu(tr('Relié à…', self.language))

        # Action directe : un champ relié peut toujours redevenir indépendant.
        linked_selected = [key for key in selected if key in self._field_links]
        unlink_direct = relations.addAction(tr('Délier', self.language))
        unlink_direct.setEnabled(bool(linked_selected))
        unlink_direct.triggered.connect(
            lambda checked=False: self._unlink_selected_fields()
        )

        unlink_menu = relations.addMenu(tr('Délier de…', self.language))
        usable_masters = [
            key for key in sorted(self._field_masters, key=lambda k: self._relation_field_label(k).casefold())
            if key not in selected
        ]
        if not usable_masters:
            empty = link_menu.addAction(tr('Aucun champ Maître', self.language))
            empty.setEnabled(False)
        for master in usable_masters:
            label = self._relation_field_label(master)
            action = link_menu.addAction(tr(label, self.language))
            # Pour un champ unique, afficher sans ambiguïté son Maître actuel.
            # Les autres Maîtres restent proposés comme destinations possibles.
            if len(selected) == 1:
                selected_key = next(iter(selected))
                action.setCheckable(True)
                action.setChecked(self._field_links.get(selected_key) == master)
            action.triggered.connect(
                lambda checked=False, m=master: self._link_selected_fields_to_master(m)
            )

        linked_masters = sorted(
            {self._field_links[k] for k in selected if k in self._field_links},
            key=lambda k: self._relation_field_label(k).casefold(),
        )
        if not linked_masters:
            empty = unlink_menu.addAction(tr('Aucune liaison sélectionnée', self.language))
            empty.setEnabled(False)
        for master in linked_masters:
            label = self._relation_field_label(master)
            action = unlink_menu.addAction(tr(label, self.language))
            action.triggered.connect(
                lambda checked=False, m=master: self._unlink_selected_fields_from_master(m)
            )

    def _show_preview_context_menu(self, global_pos) -> None:
        menu = QMenu(self)

        # Copier/Coller visible au clic droit : les raccourcis Ctrl+C / Ctrl+V
        # restent disponibles, mais ne sont plus nécessaires à connaître.
        copy_action = menu.addAction(tr("Copier", self.language))
        copy_action.setEnabled(bool([
            k for k in self._selected_preview_keys
            if str(k) != "record_number" and str(k) in self._custom_field_defs
        ]))
        copy_action.triggered.connect(
            lambda checked=False: self._copy_selected_field_for_duplication()
        )
        paste_action = menu.addAction(tr("Coller", self.language))
        paste_action.setEnabled(self._read_atelier_fields_clipboard() is not None)
        paste_action.triggered.connect(
            lambda checked=False: self._paste_duplicated_field()
        )
        menu.addSeparator()

        whole_fields = bool(
            self._selected_preview_keys
            and all(
                self._selected_part_kind(key) == "both"
                for key in self._selected_preview_keys
            )
        )

        align = menu.addMenu(tr('Aligner', self.language))
        if whole_fields and len(self._selected_preview_keys) >= 2:
            whole_menu = align.addMenu(tr('Champs complets', self.language))
            for text, mode in (
                ("Gauche", "left"), ("Centre", "center"), ("Droite", "right"),
                ("Haut", "top"), ("Bas", "bottom"),
            ):
                a = whole_menu.addAction(tr(text, self.language))
                a.triggered.connect(
                    lambda checked=False, m=mode:
                    self._align_selected_whole_fields(m)
                )

            label_menu = align.addMenu(tr('Libellés', self.language))
            for text, mode in (
                ("Gauche", "left"), ("Centre", "center"), ("Droite", "right"),
                ("Haut", "top"), ("Bas", "bottom"),
            ):
                a = label_menu.addAction(tr(text, self.language))
                a.triggered.connect(
                    lambda checked=False, m=mode:
                    self._align_selected_part_kind("label", m)
                )

            data_menu = align.addMenu(tr('Données', self.language))
            for text, mode in (
                ("Gauche", "left"), ("Centre", "center"), ("Droite", "right"),
                ("Haut", "top"), ("Bas", "bottom"),
            ):
                a = data_menu.addAction(tr(text, self.language))
                a.triggered.connect(
                    lambda checked=False, m=mode:
                    self._align_selected_part_kind("data", m)
                )
        else:
            # Même structure pour un champ seul que pour une multi-sélection.
            # Les anciennes actions directes étaient désactivées avec une seule
            # partie sélectionnée et n'avaient donc aucun effet.
            whole_menu = align.addMenu(tr('Champs complets', self.language))
            for text, mode in (
                ("Gauche", "left"), ("Centre", "center"), ("Droite", "right"),
                ("Haut", "top"), ("Bas", "bottom"),
            ):
                a = whole_menu.addAction(tr(text, self.language))
                a.setEnabled(len(self._selected_preview_keys) >= 2)
                a.triggered.connect(
                    lambda checked=False, m=mode:
                    self._align_selected_whole_fields(m)
                )

            label_menu = align.addMenu(tr('Libellés', self.language))
            for text, mode in (
                ("Gauche", "left"), ("Centre", "center"), ("Droite", "right"),
                ("Haut", "top"), ("Bas", "bottom"),
            ):
                a = label_menu.addAction(tr(text, self.language))
                a.triggered.connect(
                    lambda checked=False, m=mode:
                    self._align_single_field_part("label", m)
                )

            data_menu = align.addMenu(tr('Données', self.language))
            for text, mode in (
                ("Gauche", "left"), ("Centre", "center"), ("Droite", "right"),
                ("Haut", "top"), ("Bas", "bottom"),
            ):
                a = data_menu.addAction(tr(text, self.language))
                a.triggered.connect(
                    lambda checked=False, m=mode:
                    self._align_single_field_part("data", m)
                )

        a = align.addAction(tr('Sur la grille', self.language))
        a.setEnabled(bool(self._selected_preview_keys))
        a.triggered.connect(
            lambda checked=False: self._align_selected("grid")
        )

        size = menu.addMenu(tr('Taille', self.language))
        if whole_fields and len(self._selected_preview_keys) >= 2:
            whole_size = size.addMenu(tr('Champs complets', self.language))
            for text, mode in (
                ("Au contenu", "content"),
                ("Sur la grille", "grid"),
                ("Au plus grand", "largest"),
                ("Au plus petit", "smallest"),
                ("Au plus large", "widest"),
                ("Au plus étroit", "narrowest"),
            ):
                a = whole_size.addAction(tr(text, self.language))
                a.triggered.connect(
                    lambda checked=False, m=mode: self._size_selected(m)
                )

            label_size = size.addMenu(tr('Libellés', self.language))
            for text, mode in (
                ("Sur la grille", "grid"),
                ("Au plus large", "widest"),
                ("Au plus étroit", "narrowest"),
            ):
                a = label_size.addAction(tr(text, self.language))
                a.triggered.connect(
                    lambda checked=False, m=mode:
                    self._resize_selected_part_kind("label", m)
                )

            data_size = size.addMenu(tr('Données', self.language))
            for text, mode in (
                ("Sur la grille", "grid"),
                ("Au plus large", "widest"),
                ("Au plus étroit", "narrowest"),
            ):
                a = data_size.addAction(tr(text, self.language))
                a.triggered.connect(
                    lambda checked=False, m=mode:
                    self._resize_selected_part_kind("data", m)
                )
        else:
            for text, mode in (
                ("Au contenu", "content"),
                ("Sur la grille", "grid"),
                ("Au plus grand", "largest"),
                ("Au plus petit", "smallest"),
                ("Au plus large", "widest"),
                ("Au plus étroit", "narrowest"),
            ):
                a = size.addAction(tr(text, self.language))
                if mode in {"largest", "smallest", "widest", "narrowest"}:
                    a.setEnabled(len(self._selected_preview_keys) >= 2)
                a.triggered.connect(
                    lambda checked=False, m=mode: self._size_selected(m)
                )

        menu.addSeparator()
        fmt = menu.addMenu(tr('Mise en forme', self.language))
        for title, target in (("Libellé", "label"), ("Donnée", "data")):
            sub = fmt.addMenu(tr(title, self.language))
            action = sub.addAction(tr('Police et taille…', self.language))
            action.triggered.connect(
                lambda checked=False, tg=target: self._choose_selected_font(tg)
            )
            action = sub.addAction(tr('Couleur du texte…', self.language))
            action.triggered.connect(
                lambda checked=False, tg=target:
                self._choose_selected_text_color(tg)
            )
            sub.addSeparator()
            for text, mode in (
                ("Gras", "bold"),
                ("Italique", "italic"),
                ("Souligné", "underline"),
            ):
                action = sub.addAction(tr(text, self.language))
                action.setCheckable(True)
                if len(self._selected_preview_keys) == 1:
                    key = next(iter(self._selected_preview_keys))
                    action.setChecked(
                        bool(
                            self._field_styles.get(key, {})
                            .get(target, {})
                            .get(mode, False)
                        )
                    )
                action.triggered.connect(
                    lambda checked=False, m=mode, tg=target:
                    self._toggle_selected_text_style(tg, m, checked)
                )
            sub.addSeparator()
            action = sub.addAction(tr('Style par défaut', self.language))
            action.triggered.connect(
                lambda checked=False, tg=target:
                self._reset_selected_field_style(tg)
            )

        menu.addSeparator()
        self._add_field_relations_menu(menu)

        if len(self._selected_preview_keys) == 1:
            selected_key = next(iter(self._selected_preview_keys))
            if selected_key != "record_number":
                menu.addSeparator()
                action = menu.addAction(tr('Dupliquer le champ', self.language))
                action.triggered.connect(
                    lambda checked=False, k=selected_key:
                    self._duplicate_field(k)
                )

            if selected_key in self._custom_field_defs:
                menu.addSeparator()
                action = menu.addAction(tr('Modifier le champ…', self.language))
                action.triggered.connect(
                    lambda checked=False, k=selected_key:
                    self._edit_custom_field(k)
                )
                action = menu.addAction(tr('Effacer de la fiche', self.language))
                action.setToolTip(tr("Retire le champ de la fiche sans supprimer sa définition ni ses données.", self.language))
                action.triggered.connect(
                    lambda checked=False, k=selected_key:
                    self._erase_field_from_sheet(k)
                )
            elif selected_key not in {"record_number", "photo_data"}:
                # Régression corrigée : les champs historiques ont eux aussi
                # toujours le droit d'être renommés dans le modèle courant.
                menu.addSeparator()
                action = menu.addAction(tr('Modifier le champ…', self.language))
                action.triggered.connect(
                    lambda checked=False, k=selected_key:
                    self._edit_existing_field(k)
                )
                if selected_key != "record_state":
                    action = menu.addAction(tr('Effacer de la fiche', self.language))
                    action.setToolTip(tr("Retire le champ de la fiche sans supprimer sa définition ni ses données.", self.language))
                    action.triggered.connect(
                        lambda checked=False, k=selected_key:
                        self._erase_field_from_sheet(k)
                    )

        menu.exec(global_pos)

    def _show_atelier_background_context_menu(self, global_pos, paste_point=None) -> None:
        """Menu minimal sur une zone libre de l'Atelier."""
        if paste_point is not None:
            self._atelier_paste_point = QPoint(paste_point)
        menu = QMenu(self)
        action = menu.addAction(tr("Coller", self.language))
        action.setEnabled(self._read_atelier_fields_clipboard() is not None)
        action.triggered.connect(
            lambda checked=False: self._paste_duplicated_field()
        )
        menu.exec(global_pos)


    def _refresh_field_styles(self) -> None:
        # Repères structurels de palette : aucun filet/encadrement, seulement M/R
        # avant la case à cocher. M est gras, R reste en graisse normale.
        dead_markers = []
        for key, marker in list(getattr(self, "_relation_markers", {}).items()):
            # Une reconstruction de la palette détruit ses QLabel. PySide peut
            # conserver brièvement le wrapper Python : ne jamais réutiliser un
            # objet Qt dont le C++ a déjà été supprimé.
            if marker is None or not shiboken6.isValid(marker):
                dead_markers.append(key)
                continue
            is_master = key in getattr(self, "_field_masters", set())
            is_linked = key in getattr(self, "_field_links", {})
            marker.setText("M" if is_master else ("R" if is_linked else ""))
            mf = QFont(marker.font()); mf.setBold(bool(is_master)); marker.setFont(mf)
            marker.setToolTip("Champ Maître" if is_master else ("Champ Relié" if is_linked else ""))
        for key in dead_markers:
            getattr(self, "_relation_markers", {}).pop(key, None)
        for key, field in self._preview_fields.items():
            whole_style = self._field_styles.get(key, {})
            field.apply_text_styles(whole_style)
            # 11.7.70.26.13 — le rôle Maître/Relié est signalé dans la palette
            # par M/R avant la case à cocher. Le libellé de la fiche reste homogène.
            if hasattr(field, "set_part_geometry"):
                ls = whole_style.get("label", {}) if isinstance(whole_style, dict) else {}
                ds = whole_style.get("data", {}) if isinstance(whole_style, dict) else {}
                field.set_part_geometry(
                    label_x=ls.get("x"), label_w=ls.get("width"),
                    data_x=ds.get("x"), data_w=ds.get("width"),
                )

            if key == "record_number":
                # 018.4.4.1.5.22.8 — le N° conserve son aspect historique
                # PAR DÉFAUT, mais les réglages du clic droit deviennent actifs.
                whole = self._field_styles.get(key, {})
                label_style = whole.get("label", {}) if isinstance(whole, dict) else {}
                data_style = whole.get("data", {}) if isinstance(whole, dict) else {}

                def apply_number_part(widget, style, *, default_size, default_bold, default_color):
                    font = QFont(widget.font())
                    family = str(style.get("family", "")).strip()
                    if family:
                        font.setFamily(family)
                    font.setPointSize(int(style.get("size", default_size) or default_size))
                    font.setBold(bool(style.get("bold", default_bold)))
                    font.setItalic(bool(style.get("italic", False)))
                    font.setUnderline(bool(style.get("underline", False)))
                    widget.setFont(font)

                    align_name = str(style.get("align", "left"))
                    align = {
                        "left": Qt.AlignmentFlag.AlignLeft,
                        "center": Qt.AlignmentFlag.AlignHCenter,
                        "right": Qt.AlignmentFlag.AlignRight,
                    }.get(align_name, Qt.AlignmentFlag.AlignLeft)
                    widget.setAlignment(align | Qt.AlignmentFlag.AlignVCenter)
                    widget.setStyleSheet(
                        f"color:{style.get('color', default_color)}; "
                        "background:transparent; border:none; padding:0px 4px;"
                    )

                apply_number_part(
                    field.caption, label_style,
                    default_size=max(8, field._default_caption_font.pointSize()),
                    default_bold=False,
                    default_color="#111111",
                )
                apply_number_part(
                    field.mock, data_style,
                    default_size=18,
                    default_bold=True,
                    # Numéro système : même brun-rouge par défaut que la vraie fiche.
                    # Les styles explicitement définis dans le modèle restent prioritaires.
                    default_color="#963D32",
                )

    def _install_french_lineedit_menu(self, edit: QLineEdit) -> None:
        """Menu contextuel explicitement construit en français.

        On ne traduit plus createStandardContextMenu(): sous Windows/Qt les libellés
        natifs peuvent contenir des raccourcis ou varier selon la langue du système.
        """
        edit.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        def show_menu(pos):
            menu = QMenu(edit)
            actions = [
                (tr("Annuler", self.language), edit.undo, edit.isUndoAvailable),
                (tr("Rétablir", self.language), edit.redo, edit.isRedoAvailable),
                None,
                (tr("Couper", self.language), edit.cut, lambda: edit.hasSelectedText() and not edit.isReadOnly()),
                (tr("Copier", self.language), edit.copy, edit.hasSelectedText),
                (tr("Coller", self.language), edit.paste, lambda: not edit.isReadOnly()),
                (tr("Supprimer", self.language), lambda: edit.del_(), lambda: edit.hasSelectedText() and not edit.isReadOnly()),
                None,
                (tr("Tout sélectionner", self.language), edit.selectAll, lambda: bool(edit.text())),
            ]
            for spec in actions:
                if spec is None:
                    menu.addSeparator()
                    continue
                text, callback, enabled = spec
                action = menu.addAction(text)
                action.setEnabled(bool(enabled()))
                action.triggered.connect(callback)
            menu.exec(edit.mapToGlobal(pos))

        edit.customContextMenuRequested.connect(show_menu)

    def _font_dialog_fr(self, initial: QFont, target: str) -> QFont | None:
        dlg = QDialog(self)
        dlg.setWindowTitle("Mise en forme du texte")
        root = QVBoxLayout(dlg)
        grid = QGridLayout()

        grid.addWidget(QLabel("Police"), 0, 0)
        grid.addWidget(QLabel("Style"), 0, 1)
        grid.addWidget(QLabel("Taille"), 0, 2)

        families = QListWidget()
        for family_name in QFontDatabase.families():
            families.addItem(family_name)
            item = families.item(families.count() - 1)
            preview_font = QFont(family_name)
            preview_font.setPointSize(10)
            item.setFont(preview_font)
        styles = QListWidget()
        styles.addItems(["Normal", "Italique", "Gras", "Gras italique"])
        sizes = QListWidget()
        sizes.addItems([str(x) for x in (8, 9, 10, 11, 12, 14, 16, 18, 20, 22, 24, 28, 32, 36, 48, 72)])
        grid.addWidget(families, 1, 0)
        grid.addWidget(styles, 1, 1)
        grid.addWidget(sizes, 1, 2)

        underline = QCheckBox("Souligné")
        grid.addWidget(underline, 2, 0)

        grid.addWidget(QLabel("Justification"), 2, 1)
        justify = QWidget()
        justify_layout = QHBoxLayout(justify)
        justify_layout.setContentsMargins(0, 0, 0, 0)
        justify_layout.setSpacing(8)
        align_left = QRadioButton("Gauche")
        align_center = QRadioButton("Centré")
        align_right = QRadioButton("Droite")
        justify_layout.addWidget(align_left)
        justify_layout.addWidget(align_center)
        justify_layout.addWidget(align_right)
        grid.addWidget(justify, 2, 2)

        # 11.7.70.26.19 — propriétés d'affichage de la zone Donnée.
        # Elles restent purement graphiques : le type métier du champ ne change pas.
        valign_top = valign_center = valign_bottom = wrap_text = None
        if target == "data":
            grid.addWidget(QLabel("Alignement vertical"), 3, 1)
            valign_box = QWidget()
            valign_layout = QHBoxLayout(valign_box)
            valign_layout.setContentsMargins(0, 0, 0, 0); valign_layout.setSpacing(8)
            valign_top = QRadioButton("Haut")
            valign_center = QRadioButton("Centré")
            valign_bottom = QRadioButton("Bas")
            valign_layout.addWidget(valign_top); valign_layout.addWidget(valign_center); valign_layout.addWidget(valign_bottom)
            grid.addWidget(valign_box, 3, 2)
            wrap_text = QCheckBox("Retour à la ligne")
            grid.addWidget(wrap_text, 4, 1, 1, 2)
            preview_row = 5
        else:
            preview_row = 3

        grid.addWidget(QLabel("Aperçu"), preview_row, 0)
        sample = QLabel("Exemple de texte assez long pour visualiser le retour à la ligne" if target == "data" else "Nom du champ")
        sample.setMinimumHeight(72)
        sample.setFrameShape(QFrame.Shape.Box)
        grid.addWidget(sample, preview_row + 1, 0, 1, 3)
        root.addLayout(grid)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("OK")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Annuler")
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        root.addWidget(buttons)

        def select_item(lst, text):
            hits = lst.findItems(text, Qt.MatchFlag.MatchExactly)
            if hits:
                lst.setCurrentItem(hits[0])

        select_item(families, initial.family())
        select_item(
            styles,
            "Gras italique" if initial.bold() and initial.italic()
            else "Gras" if initial.bold()
            else "Italique" if initial.italic()
            else "Normal"
        )
        select_item(sizes, str(initial.pointSize() if initial.pointSize() > 0 else 10))
        underline.setChecked(initial.underline())

        first_key = next(iter(self._selected_preview_keys), None)
        first_style = (
            self._field_styles.get(first_key, {}).get(target, {})
            if first_key is not None else {}
        )
        initial_align = str(first_style.get("align", "left"))
        {"left": align_left, "center": align_center, "right": align_right}.get(initial_align, align_left).setChecked(True)
        if target == "data":
            initial_valign = str(first_style.get("valign", "center"))
            {"top": valign_top, "center": valign_center, "bottom": valign_bottom}.get(initial_valign, valign_center).setChecked(True)
            wrap_text.setChecked(bool(first_style.get("wrap", False)))

        original = {
            key: dict(self._field_styles.get(key, {}).get(target, {}))
            for key in self._selected_preview_keys
        }

        def build_font():
            font = QFont(initial)
            if families.currentItem():
                font.setFamily(families.currentItem().text())
            style_text = styles.currentItem().text() if styles.currentItem() else "Normal"
            font.setBold("Gras" in style_text)
            font.setItalic("italique" in style_text.lower())
            if sizes.currentItem():
                font.setPointSize(int(sizes.currentItem().text()))
            font.setUnderline(underline.isChecked())
            return font

        def live_preview():
            font = build_font()
            sample.setFont(font)
            align_name = (
                "center" if align_center.isChecked()
                else "right" if align_right.isChecked()
                else "left"
            )
            valign_name = "center"
            if target == "data":
                valign_name = "top" if valign_top.isChecked() else "bottom" if valign_bottom.isChecked() else "center"
                sample.setWordWrap(wrap_text.isChecked())
            vflag = {"top": Qt.AlignmentFlag.AlignTop, "center": Qt.AlignmentFlag.AlignVCenter, "bottom": Qt.AlignmentFlag.AlignBottom}[valign_name]
            sample.setAlignment({"left": Qt.AlignmentFlag.AlignLeft, "center": Qt.AlignmentFlag.AlignHCenter, "right": Qt.AlignmentFlag.AlignRight}[align_name] | vflag)
            for key in self._selected_preview_keys:
                whole = dict(self._field_styles.get(key, {}))
                style = dict(whole.get(target, {}))
                style.update(
                    family=font.family(),
                    size=font.pointSize(),
                    bold=font.bold(),
                    italic=font.italic(),
                    underline=font.underline(),
                    align=align_name,
                )
                if target == "data":
                    style["valign"] = valign_name
                    style["wrap"] = bool(wrap_text.isChecked())
                whole[target] = style
                self._field_styles[key] = whole
            self._refresh_field_styles()

        families.currentItemChanged.connect(lambda *_: live_preview())
        styles.currentItemChanged.connect(lambda *_: live_preview())
        sizes.currentItemChanged.connect(lambda *_: live_preview())
        underline.toggled.connect(lambda *_: live_preview())
        align_left.toggled.connect(lambda checked: live_preview() if checked else None)
        align_center.toggled.connect(lambda checked: live_preview() if checked else None)
        align_right.toggled.connect(lambda checked: live_preview() if checked else None)
        if target == "data":
            valign_top.toggled.connect(lambda checked: live_preview() if checked else None)
            valign_center.toggled.connect(lambda checked: live_preview() if checked else None)
            valign_bottom.toggled.connect(lambda checked: live_preview() if checked else None)
            wrap_text.toggled.connect(lambda *_: live_preview())
        live_preview()

        if dlg.exec() != QDialog.DialogCode.Accepted:
            for key in self._selected_preview_keys:
                whole = dict(self._field_styles.get(key, {}))
                if original[key]:
                    whole[target] = original[key]
                else:
                    whole.pop(target, None)
                if whole:
                    self._field_styles[key] = whole
                else:
                    self._field_styles.pop(key, None)
            self._refresh_field_styles()
            return None

        return build_font()

    def _choose_selected_font(self, target="label") -> None:
        if not self._selected_preview_keys:
            return
        first = next(iter(self._selected_preview_keys))
        style = self._field_styles.get(first, {}).get(target, {})

        # Pour le N°, partir de son rendu réel (notamment 18 pt gras en donnée)
        # afin que la boîte ne donne pas l'impression que le réglage est inactif.
        preview = self._preview_fields.get(first)
        if first == "record_number" and preview is not None:
            font = QFont(preview.caption.font() if target == "label" else preview.mock.font())
        else:
            font = QFont(self.font())

        if style.get("family"):
            font.setFamily(str(style["family"]))
        if style.get("size"):
            font.setPointSize(int(style["size"]))
        if "bold" in style:
            font.setBold(bool(style["bold"]))
        if "italic" in style:
            font.setItalic(bool(style["italic"]))
        if "underline" in style:
            font.setUnderline(bool(style["underline"]))

        if self._font_dialog_fr(font, target) is not None:
            self._record_history_state()

    def _choose_selected_text_color(self, target="label") -> None:
        if not self._selected_preview_keys:
            return

        first = next(iter(self._selected_preview_keys))
        style = self._field_styles.get(first, {}).get(target, {})
        if first == "record_number":
            default = "#111111" if target == "label" else "#159447"
        else:
            default = "#24342C" if target == "label" else "#8A9690"

        dlg = self._make_french_color_dialog(
            QColor(style.get("color", default)),
            "Couleur du texte",
        )
        original = {
            key: dict(self._field_styles.get(key, {}).get(target, {}))
            for key in self._selected_preview_keys
        }

        def live_color(color):
            if not color.isValid():
                return
            for key in self._selected_preview_keys:
                whole = dict(self._field_styles.get(key, {}))
                current = dict(whole.get(target, {}))
                current["color"] = color.name()
                whole[target] = current
                self._field_styles[key] = whole
            self._refresh_field_styles()

        dlg.currentColorChanged.connect(live_color)
        live_color(dlg.currentColor())

        if dlg.exec() != QDialog.DialogCode.Accepted:
            for key in self._selected_preview_keys:
                whole = dict(self._field_styles.get(key, {}))
                if original[key]:
                    whole[target] = original[key]
                else:
                    whole.pop(target, None)
                if whole:
                    self._field_styles[key] = whole
                else:
                    self._field_styles.pop(key, None)
            self._refresh_field_styles()
            return

        self._record_history_state()

    def _toggle_selected_text_style(self, target, mode, checked) -> None:
        for key in self._selected_preview_keys:
            whole = dict(self._field_styles.get(key, {}))
            style = dict(whole.get(target, {}))
            style[mode] = bool(checked)
            whole[target] = style
            self._field_styles[key] = whole
        self._refresh_field_styles()
        self._record_history_state()

    def _reset_selected_field_style(self, target="label") -> None:
        changed = False
        for key in list(self._selected_preview_keys):
            whole = dict(self._field_styles.get(key, {}))
            if target in whole:
                whole.pop(target, None)
                changed = True
                if whole:
                    self._field_styles[key] = whole
                else:
                    self._field_styles.pop(key, None)
        if changed:
            self._refresh_field_styles()
            for key in self._selected_preview_keys:
                field = self._preview_fields.get(key)
                if field is not None:
                    field.updateGeometry()
                    field.update()
            self._record_history_state()

    def _group_colors(self, block_name: str) -> tuple[str, str]:
        style = self._group_styles.get(block_name, {})
        # 23.7.7.1 — un cadre sans couleur explicitement choisie hérite du
        # fond de la fiche. Dès que l'utilisateur choisit une couleur de cadre,
        # la clé "background" existe et devient volontairement indépendante.
        return (
            str(style.get("background", self._sheet_background)),
            str(style.get("border", "#C5D2CB")),
        )

    def _group_border_width(self, block_name: str) -> int:
        style = self._group_styles.get(block_name, {})
        try:
            return max(0, min(4, int(style.get("border_width", 1))))
        except Exception:
            return 1

    def _group_title_style(self, block_name: str) -> dict:
        style = self._group_styles.get(block_name, {})
        value = style.get("title", {})
        return dict(value) if isinstance(value, dict) else {}

    def _group_title_css(self, block_name: str) -> str:
        style = self._group_title_style(block_name)
        parts = ["color:" + str(style.get("color", "#000000"))]
        family = str(style.get("family", "")).strip()
        if family:
            parts.append(f"font-family:'{family}'")
        size = int(style.get("size", 0) or 0)
        if size > 0:
            parts.append(f"font-size:{size}pt")
        parts.append("font-weight:700" if style.get("bold", True) else "font-weight:400")
        parts.append("font-style:italic" if style.get("italic", False) else "font-style:normal")
        parts.append("text-decoration:underline" if style.get("underline", False) else "text-decoration:none")
        return "; ".join(parts) + ";"

    def _refresh_group_styles(self) -> None:
        for block_name, group in self._preview_groups.items():
            group.setTitle(self._group_display_title(block_name))
            background, border = self._group_colors(block_name)
            border_width = self._group_border_width(block_name)
            title_css = self._group_title_css(block_name)
            is_photo = bool(
                block_name == "Photo"
                or self._group_styles.get(block_name, {}).get("custom_photo")
            )
            padding_top = 0 if is_photo else 12
            group.setStyleSheet(
                "QGroupBox { "
                f"{title_css} background:{background}; border:{border_width}px solid {border}; "
                f"border-radius:8px; margin-top:0px; padding-top:{padding_top}px; }} "
                "QGroupBox::title { subcontrol-origin: padding; subcontrol-position: top left; "
                "left:6px; padding:0px 2px; }"
            )
            if block_name in self._group_title_handles:
                self._ensure_group_title_handle(block_name)
            canvas = self._preview_canvases.get(block_name)
            if canvas is not None:
                canvas.update()
            # Le QLabel du cadre Photo supplémentaire a son propre fond.
            # Sans mise à jour, son blanc opaque masque le fond du cadre.
            if is_photo and bool(self._group_styles.get(block_name, {}).get("custom_photo")):
                photo_canvas = group.findChild(QLabel)
                if photo_canvas is not None:
                    photo_canvas.setStyleSheet(
                        f"background-color:{background}; border:none; border-radius:0px; color:#718078;"
                    )
        if hasattr(self, "_preview_photo_group"):
            background, border = self._group_colors("Photo")
            border_width = self._group_border_width("Photo")
            title_css = self._group_title_css("Photo")
            # Le QLabel intérieur est opaque et doit suivre la même couleur
            # que le fond du cadre (pas la couleur du bandeau de titre).
            self._preview_photo_placeholder.setStyleSheet(
                f"background-color:{background}; border:none; border-radius:0px; color:#718078;"
            )
            self._preview_photo_group.setStyleSheet(
                "QGroupBox { "
                f"{title_css} background:{background}; border:{border_width}px solid {border}; "
                "border-radius:8px; margin-top:0px; padding-top:0px; } "
                "QGroupBox::title { subcontrol-origin: padding; subcontrol-position: top left; "
                "left:6px; padding:0px 2px; }"
            )
            if "Photo" in self._group_title_handles:
                self._ensure_group_title_handle("Photo")

    def _free_group_widget(self, name: str):
        if name == "Photo":
            return getattr(self, "_preview_photo_group", None)
        return self._preview_groups.get(name)

    def _free_group_geometry_style(self, name: str):
        """Géométrie canonique MM3 = pixels visibles dans l'Atelier.
        Les géométries 1.5.6 étaient divisées par le facteur d'aperçu : elles
        sont migrées à la volée une seule fois visuellement.
        """
        style = self._group_styles.get(name, {})
        if not isinstance(style, dict):
            return None
        geom = style.get("geometry", {})
        if isinstance(geom, dict) and {"x", "y", "w", "h"} <= set(geom):
            try:
                x, y, w, h = (
                    int(geom["x"]), int(geom["y"]),
                    max(1, int(geom["w"])), max(1, int(geom["h"])),
                )
                if style.get("geometry_space") != "atelier_px":
                    legacy_scale = max(0.01, float(self._preview_scale()))
                    x = int(round(x * legacy_scale))
                    y = int(round(y * legacy_scale))
                    w = max(1, int(round(w * legacy_scale)))
                    h = max(1, int(round(h * legacy_scale)))
                return x, y, w, h
            except Exception:
                pass
        return None

    def _free_group_position_style(self, name: str) -> tuple[int, int]:
        style = self._group_styles.get(name, {})
        position = style.get("position", {}) if isinstance(style, dict) else {}
        try:
            return int(position.get("dx", 0)), int(position.get("dy", 0))
        except Exception:
            return 0, 0

    def _free_group_rect_is_valid(self, name: str, rect: QRect) -> bool:
        """Contact bord à bord autorisé ; recouvrement d'un seul pixel interdit."""
        for other in self._free_group_names:
            if other == name:
                continue
            widget = self._free_group_widget(other)
            if widget is None or not widget.isVisible():
                continue
            other_rect = QRect(widget.geometry())
            # QRect.intersects() est faux lorsque les rectangles se touchent seulement.
            if rect.intersects(other_rect):
                return False
        return True

    def _snap_free_group_rect(self, name: str, rect: QRect, threshold: int = 18) -> QRect:
        """Aimantation franche : les cadres peuvent réellement partager leur bord."""
        best = QRect(rect)
        best_distance = threshold + 1

        for other in self._free_group_names:
            if other == name:
                continue
            widget = self._free_group_widget(other)
            if widget is None or not widget.isVisible():
                continue
            o = QRect(widget.geometry())

            # Contact vertical : il suffit que les projections horizontales se croisent.
            horizontal_overlap = min(best.right(), o.right()) >= max(best.left(), o.left())
            if horizontal_overlap:
                for ny in (o.top() - best.height(), o.bottom() + 1):
                    d = abs(ny - best.y())
                    candidate = QRect(best.x(), ny, best.width(), best.height())
                    if d <= threshold and d < best_distance and self._free_group_rect_is_valid(name, candidate):
                        best = candidate
                        best_distance = d

            # Contact horizontal.
            vertical_overlap = min(best.bottom(), o.bottom()) >= max(best.top(), o.top())
            if vertical_overlap:
                for nx in (o.left() - best.width(), o.right() + 1):
                    d = abs(nx - best.x())
                    candidate = QRect(nx, best.y(), best.width(), best.height())
                    if d <= threshold and d < best_distance and self._free_group_rect_is_valid(name, candidate):
                        best = candidate
                        best_distance = d

        return best


    def _free_group_overlap_score(self, name: str, rect: QRect) -> int:
        score = 0
        for other in self._free_group_names:
            if other == name:
                continue
            widget = self._free_group_widget(other)
            if widget is None or not widget.isVisible():
                continue
            inter = rect.intersected(QRect(widget.geometry()))
            if not inter.isEmpty():
                score += max(0, inter.width()) * max(0, inter.height())
        return score

    def _nearest_valid_group_drop(self, name: str, rect: QRect, start_rect: QRect) -> QRect:
        """Survol libre puis dépôt universel, bord-à-bord si possible."""
        # Dépôt déjà libre : aimantation géométrique douce vers la frontière
        # collective du rang/colonne voisin.
        if self._free_group_rect_is_valid(name, rect):
            return self._nearest_group_contact_rect(name, rect, tolerance=18)

        # Si le pointeur est relâché en léger chevauchement, chercher les quatre
        # frontières collectives susceptibles de résoudre le conflit.
        others = []
        for other_name in self._free_group_names:
            if other_name == name:
                continue
            widget = self._free_group_widget(other_name)
            if widget is not None and widget.isVisible():
                others.append(QRect(widget.geometry()))

        candidates = []

        # Frontière au-dessus : tous les obstacles recouvrant horizontalement.
        horizontal = [
            o for o in others
            if self._axis_overlap(rect.left(), rect.right(), o.left(), o.right())
        ]
        if horizontal:
            tops = [o for o in horizontal if o.center().y() <= rect.center().y()]
            if tops:
                y = max(o.bottom() + 1 for o in tops)
                c = QRect(rect)
                c.moveTop(y)
                if self._free_group_rect_is_valid(name, c):
                    candidates.append((abs(c.y() - rect.y()), c))

            bottoms = [o for o in horizontal if o.center().y() >= rect.center().y()]
            if bottoms:
                y = min(o.top() for o in bottoms) - rect.height()
                c = QRect(rect)
                c.moveTop(y)
                if c.y() >= 0 and self._free_group_rect_is_valid(name, c):
                    candidates.append((abs(c.y() - rect.y()), c))

        vertical = [
            o for o in others
            if self._axis_overlap(rect.top(), rect.bottom(), o.top(), o.bottom())
        ]
        if vertical:
            lefts = [o for o in vertical if o.center().x() <= rect.center().x()]
            if lefts:
                x = max(o.right() + 1 for o in lefts)
                c = QRect(rect)
                c.moveLeft(x)
                if self._free_group_rect_is_valid(name, c):
                    candidates.append((abs(c.x() - rect.x()), c))

            rights = [o for o in vertical if o.center().x() >= rect.center().x()]
            if rights:
                x = min(o.left() for o in rights) - rect.width()
                c = QRect(rect)
                c.moveLeft(x)
                if c.x() >= 0 and self._free_group_rect_is_valid(name, c):
                    candidates.append((abs(c.x() - rect.x()), c))

        if candidates:
            candidates.sort(key=lambda item: item[0])
            return candidates[0][1]

        return QRect(start_rect)


    def _resolve_free_group_rect(self, name: str, proposed: QRect, previous: QRect) -> QRect:
        """Déplacement bloc : bord-à-bord autorisé, jamais de recouvrement."""
        if self._free_group_rect_is_valid(name, proposed):
            return self._snap_free_group_rect(name, proposed)

        dx = proposed.x() - previous.x()
        dy = proposed.y() - previous.y()
        distance = max(abs(dx), abs(dy), 1)
        last = QRect(previous)

        for step in range(1, distance + 1):
            ratio = step / distance
            candidate = QRect(
                round(previous.x() + dx * ratio),
                round(previous.y() + dy * ratio),
                proposed.width(), proposed.height(),
            )
            if self._free_group_rect_is_valid(name, candidate):
                last = candidate
            else:
                break
        return self._snap_free_group_rect(name, last)


    def _activate_free_group_layout(self) -> None:
        host = getattr(self, "_construction_widget", None)
        grid = getattr(self, "_construction_grid", None)
        if host is None or grid is None:
            return
        scale = max(0.01, float(self._preview_scale()))
        if not self._free_group_default_geometries:
            for name in self._free_group_names:
                widget = self._free_group_widget(name)
                if widget is not None:
                    self._free_group_default_geometries[name] = QRect(widget.geometry())
            for name in self._free_group_names:
                widget = self._free_group_widget(name)
                base = self._free_group_default_geometries.get(name)
                if widget is None or base is None:
                    continue
                grid.removeWidget(widget)
                widget.setParent(host)
                stored = self._free_group_geometry_style(name)
                if stored is not None:
                    x, y, w, h = stored
                    geom = QRect(x, y, w, h)
                else:
                    dx, dy = self._free_group_position_style(name)
                    geom = QRect(base)
                    geom.moveTo(
                        base.x() + int(round(dx * scale)),
                        base.y() + int(round(dy * scale)),
                    )
                widget.setGeometry(geom)
                widget.show()
        else:
            for name in self._free_group_names:
                widget = self._free_group_widget(name)
                base = self._free_group_default_geometries.get(name)
                if widget is None or base is None or self._free_group_drag_name == name:
                    continue
                stored = self._free_group_geometry_style(name)
                if stored is not None:
                    x, y, w, h = stored
                    widget.setGeometry(x, y, w, h)
                else:
                    dx, dy = self._free_group_position_style(name)
                    widget.move(
                        base.x() + int(round(dx * scale)),
                        base.y() + int(round(dy * scale)),
                    )
        # 23.9.3.5.3 — IMPORTANT : l'ouverture de l'Atelier doit être
        # strictement passive. Les géométries enregistrées sont l'autorité.
        # Ne jamais "normaliser" ni recoller automatiquement deux cadres proches :
        # un espace volontaire entre eux fait partie du modèle utilisateur.
        for name in self._free_group_names:
            group = self._free_group_widget(name)
            if group is not None:
                self._create_group_resize_handles(name, group)
                self._ensure_group_title_handle(name)
        self._position_all_group_resize_handles()
        self._refresh_free_group_selection()

        self._resize_free_group_host()

        if getattr(self, "_absolute_field_mode", False):
            if getattr(self, "_absolute_fields_ready", False):
                # Chemin rapide 23.9.3.5.4 : les champs sont déjà sur la feuille.
                # Les cadres viennent seulement de retrouver leur géométrie finale.
                self._resize_free_group_host()
                self._raise_absolute_fields()
            else:
                # Compatibilité anciennes collections : migration historique.
                QTimer.singleShot(0, self._activate_absolute_field_plane)

        # Les groupes utilisateur sont ajoutés seulement APRÈS ce premier
        # passage. Ils ne peuvent donc jamais modifier les dimensions initiales
        # des blocs historiques.
        if not getattr(self, "_custom_groups_restored", False):
            self._custom_groups_restored = True
            QTimer.singleShot(0, self._restore_custom_groups_after_layout)

    @staticmethod
    def _axis_overlap(a1: int, a2: int, b1: int, b2: int) -> bool:
        return min(a2, b2) >= max(a1, b1)

    def _nearest_group_contact_rect(self, name: str, rect: QRect, tolerance: int = 18) -> QRect:
        """Aimantation universelle fondée uniquement sur la géométrie.

        Aucun nom de bloc n'intervient. Si plusieurs blocs occupent le rang
        voisin, la butée est calculée sur leur frontière commune réelle.
        """
        others = []
        for other_name in self._free_group_names:
            if other_name == name:
                continue
            widget = self._free_group_widget(other_name)
            if widget is None or not widget.isVisible():
                continue
            others.append(QRect(widget.geometry()))

        if not others:
            return QRect(rect)

        candidates = []

        # Contact en montant : bord supérieur du bloc contre la frontière
        # inférieure la plus basse des blocs situés au-dessus et croisant X.
        above = [
            o for o in others
            if o.bottom() < rect.top()
            and self._axis_overlap(rect.left(), rect.right(), o.left(), o.right())
        ]
        if above:
            frontier = max(o.bottom() + 1 for o in above)
            gap = rect.top() - frontier
            if 0 <= gap <= tolerance:
                candidate = QRect(rect)
                candidate.moveTop(frontier)
                if self._free_group_rect_is_valid(name, candidate):
                    candidates.append((gap, candidate))

        # Contact en descendant.
        below = [
            o for o in others
            if o.top() > rect.bottom()
            and self._axis_overlap(rect.left(), rect.right(), o.left(), o.right())
        ]
        if below:
            frontier = min(o.top() for o in below)
            gap = frontier - (rect.bottom() + 1)
            if 0 <= gap <= tolerance:
                candidate = QRect(rect)
                candidate.moveBottom(frontier - 1)
                if self._free_group_rect_is_valid(name, candidate):
                    candidates.append((gap, candidate))

        # Contact vers la gauche.
        left_side = [
            o for o in others
            if o.right() < rect.left()
            and self._axis_overlap(rect.top(), rect.bottom(), o.top(), o.bottom())
        ]
        if left_side:
            frontier = max(o.right() + 1 for o in left_side)
            gap = rect.left() - frontier
            if 0 <= gap <= tolerance:
                candidate = QRect(rect)
                candidate.moveLeft(frontier)
                if self._free_group_rect_is_valid(name, candidate):
                    candidates.append((gap, candidate))

        # Contact vers la droite.
        right_side = [
            o for o in others
            if o.left() > rect.right()
            and self._axis_overlap(rect.top(), rect.bottom(), o.top(), o.bottom())
        ]
        if right_side:
            frontier = min(o.left() for o in right_side)
            gap = frontier - (rect.right() + 1)
            if 0 <= gap <= tolerance:
                candidate = QRect(rect)
                candidate.moveRight(frontier - 1)
                if self._free_group_rect_is_valid(name, candidate):
                    candidates.append((gap, candidate))

        if not candidates:
            return QRect(rect)
        candidates.sort(key=lambda item: item[0])
        return candidates[0][1]

    def _normalize_nearby_group_contacts(self, tolerance: int = 18) -> None:
        """Rapproche des cadres uniquement lors d'une action explicite.

        Cette méthode ne doit JAMAIS être appelée pendant l'ouverture de l'Atelier :
        les espaces enregistrés par l'utilisateur doivent être restitués à l'identique.
        """
        # Deux passes suffisent pour une composition en rangées/colonnes.
        for _ in range(2):
            changed = False
            # Ordre top-left : les blocs déjà placés servent de référence.
            widgets = []
            for name in self._free_group_names:
                widget = self._free_group_widget(name)
                if widget is not None and widget.isVisible():
                    widgets.append((name, widget))
            widgets.sort(key=lambda item: (item[1].y(), item[1].x()))

            for name, widget in widgets:
                current = QRect(widget.geometry())
                resolved = self._nearest_group_contact_rect(name, current, tolerance)
                if resolved != current:
                    widget.setGeometry(resolved)
                    style = dict(self._group_styles.get(name, {}))
                    geom = dict(style.get("geometry", {})) if isinstance(style.get("geometry"), dict) else {}
                    if geom:
                        geom.update({
                            "x": int(resolved.x()),
                            "y": int(resolved.y()),
                            "w": int(resolved.width()),
                            "h": int(resolved.height()),
                        })
                        style["geometry"] = geom
                        style["geometry_space"] = "atelier_px"
                        self._group_styles[name] = style
                    changed = True
            if not changed:
                break

        # Les groupes ont maintenant leur vraie taille : réafficher les champs
        # avec les coordonnées sauvegardées, sans aucun recalcul/bridage.
        if not bool(getattr(self, "_mm3_post_group_refresh_pending", False)):
            self._mm3_post_group_refresh_pending = True
            def _post_group_refresh():
                self._mm3_post_group_refresh_pending = False
                self._refresh_preview()
            QTimer.singleShot(0, _post_group_refresh)


    def _resize_free_group_host(self) -> None:
        host = getattr(self, "_construction_widget", None)
        if host is None:
            return
        bottom = 0
        for name in self._free_group_names:
            widget = self._free_group_widget(name)
            if widget is not None and widget.isVisible():
                bottom = max(bottom, widget.geometry().bottom() + 1)
        for field in getattr(self, "_preview_fields", {}).values():
            if field is not None and field.isVisible() and field.parentWidget() is host:
                bottom = max(bottom, field.geometry().bottom() + 12)
        # 23.2 — toute la page Atelier visible doit être une vraie surface
        # interactive, y compris les zones vierges créées par agrandissement.
        viewport = getattr(getattr(self, "_preview_scroll", None), "viewport", lambda: None)()
        visible_h = viewport.height() if viewport is not None else 0
        visible_w = viewport.width() if viewport is not None else 0
        host.setMinimumHeight(max(host.minimumHeight(), bottom, visible_h))
        host.setMinimumWidth(max(host.minimumWidth(), visible_w))
        overlay = getattr(self, "_sheet_grid_overlay", None)
        if overlay is not None:
            overlay.setGeometry(host.rect())
            overlay.show()
        if self._group_rubber_band is not None:
            self._group_rubber_band.setParent(host)

    def _create_group_resize_handles(self, name: str, group: QWidget) -> None:
        """Huit poignées très fines visibles uniquement dans l'Atelier."""
        if name in self._free_group_resize_handles:
            return
        handles = []
        for _ in range(8):
            h = QFrame(group)
            h.setFixedSize(5, 5)
            h.setStyleSheet(
                "background:#F0A020; border:1px solid #B86E00; border-radius:1px;"
            )
            h.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            h.show()
            h.raise_()
            handles.append(h)
        self._free_group_resize_handles[name] = handles
        self._position_group_resize_handles(name)

    def _position_group_resize_handles(self, name: str) -> None:
        group = self._free_group_widget(name)
        handles = self._free_group_resize_handles.get(name, [])
        if group is None or len(handles) != 8:
            return
        self._position_group_title_handle(name)
        s = 5
        left = 0
        right = max(0, group.width() - s)
        top = 0
        bottom = max(0, group.height() - s)
        mid_x = max(0, (group.width() - s) // 2)
        mid_y = max(0, (group.height() - s) // 2)
        points = (
            (left, top), (right, top), (left, bottom), (right, bottom),
            (mid_x, top), (mid_x, bottom), (left, mid_y), (right, mid_y),
        )
        for h, (x, y) in zip(handles, points):
            h.move(x, y)
            h.raise_()

    def _position_all_group_resize_handles(self) -> None:
        for name in self._free_group_names:
            self._position_group_resize_handles(name)

    @staticmethod
    def _group_resize_edge(group: QWidget, point: QPoint) -> str:
        """Détection bords/coins du bloc ; aucune dépendance au nom du groupe."""
        zone = 7
        x, y = point.x(), point.y()
        w, h = max(1, group.width()), max(1, group.height())
        l = x <= zone
        r = x >= w - 1 - zone
        t = y <= zone
        b = y >= h - 1 - zone
        if t and l: return "tl"
        if t and r: return "tr"
        if b and l: return "bl"
        if b and r: return "br"
        if l: return "l"
        if r: return "r"
        if t: return "t"
        if b: return "b"
        return ""

    @staticmethod
    def _group_resize_cursor(edge: str):
        if edge in ("l", "r"):
            return Qt.CursorShape.SizeHorCursor
        if edge in ("t", "b"):
            return Qt.CursorShape.SizeVerCursor
        if edge in ("tl", "br"):
            return Qt.CursorShape.SizeFDiagCursor
        if edge in ("tr", "bl"):
            return Qt.CursorShape.SizeBDiagCursor
        return Qt.CursorShape.ArrowCursor

    def _group_content_bounds(self, name: str, group: QWidget) -> QRect:
        """Rectangle occupé par le contenu, exprimé dans le repère DU GROUPE."""
        # Photo : son contenu visuel s'adapte au cadre.
        if name == "Photo":
            return QRect(0, 0, 0, 0)

        canvas = self._preview_canvases.get(name)
        if canvas is None:
            return QRect(0, 0, 0, 0)

        union = QRect()
        first = True
        for field in self._preview_fields.values():
            if not field.isVisible() or field.parentWidget() is not canvas:
                continue

            # Les champs sont positionnés dans le canvas ; pour limiter le
            # redimensionnement du groupe, il faut convertir ces coordonnées
            # dans le repère du groupe lui-même.
            top_left = canvas.mapTo(group, field.pos())
            rect = QRect(top_left, field.size())
            if first:
                union = QRect(rect)
                first = False
            else:
                union = union.united(rect)

        return QRect() if first else union

    def _group_min_size_for_content(self, name: str, group: QWidget) -> tuple[int, int]:
        bounds = self._group_content_bounds(name, group)

        # Quelques pixels de réserve entre le dernier champ et la bordure :
        # le champ limitrophe reste toujours entièrement visible.
        if bounds.isNull():
            return 80, 46

        reserve = int(GROUP_CONTENT_RESERVE)
        min_w = max(80, bounds.right() + 1 + reserve)
        min_h = max(46, bounds.bottom() + 1 + reserve)
        return min_w, min_h

    def _proposed_group_resize(self, name: str, group: QWidget, edge: str, delta: QPoint, start: QRect) -> QRect:
        rect = QRect(start)
        min_w, min_h = self._group_min_size_for_content(name, group)

        if "l" in edge:
            new_left = min(start.right() - min_w + 1, start.left() + delta.x())
            rect.setLeft(max(0, new_left))
        if "r" in edge:
            rect.setRight(max(start.left() + min_w - 1, start.right() + delta.x()))
        if "t" in edge:
            new_top = min(start.bottom() - min_h + 1, start.top() + delta.y())
            rect.setTop(max(0, new_top))
        if "b" in edge:
            rect.setBottom(max(start.top() + min_h - 1, start.bottom() + delta.y()))
        return rect

    def _resolve_group_resize(self, name: str, proposed: QRect, previous: QRect) -> QRect:
        """Redimensionnement au pixel, chevauchement interdit, bord-à-bord permis."""
        if self._free_group_rect_is_valid(name, proposed):
            return proposed

        dx = proposed.x() - previous.x()
        dy = proposed.y() - previous.y()
        dw = proposed.width() - previous.width()
        dh = proposed.height() - previous.height()
        distance = max(abs(dx), abs(dy), abs(dw), abs(dh), 1)
        last = QRect(previous)

        for step in range(1, distance + 1):
            ratio = step / distance
            candidate = QRect(
                round(previous.x() + dx * ratio),
                round(previous.y() + dy * ratio),
                max(1, round(previous.width() + dw * ratio)),
                max(1, round(previous.height() + dh * ratio)),
            )
            if self._free_group_rect_is_valid(name, candidate):
                last = candidate
            else:
                break
        return last

    def _ensure_group_title_handle(self, name: str):
        """Zone de commande du bandeau d'un bloc, indépendante de son contenu."""
        group = self._free_group_widget(name)
        if group is None:
            return None
        handle = self._group_title_handles.get(name)
        if handle is None:
            handle = QFrame(group)
            handle.setObjectName(f"mm3GroupTitleHandle_{name}")
            handle.setCursor(Qt.CursorShape.OpenHandCursor)
            handle.setProperty("_mm3_free_group", name)
            handle.setProperty("_mm3_group_title_handle", True)
            handle.installEventFilter(self)

            caption = QLabel(handle)
            caption.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            caption.setAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )
            caption.setObjectName("mm3AtelierFrameBandCaption")
            handle._mm3_caption = caption
            self._group_title_handles[name] = handle

        background, _border = self._group_colors(name)
        base = QColor(background)
        if not base.isValid():
            base = QColor(self._sheet_background)
        shade_1 = base.darker(112).name()
        shade_2 = base.darker(132).name()
        handle.setStyleSheet(
            "QFrame { "
            f"background:{shade_1}; border:none; border-bottom:2px solid {shade_2}; "
            "border-radius:3px; }"
        )

        # Laisser les bords/corners libres pour les poignées de redimensionnement.
        handle.setGeometry(
            10,
            3,
            max(1, group.width() - 20),
            min(22, max(1, group.height() - 6)),
        )

        caption = getattr(handle, "_mm3_caption", None)
        if caption is not None:
            caption.setGeometry(6, 0, max(1, handle.width() - 12), handle.height())
            caption.setText(self._group_display_title(name))
            caption.setStyleSheet(
                "QLabel { background:transparent; border:none; "
                + self._group_title_css(name)
                + " }"
            )
            caption.show()
            caption.raise_()

        handle.show()
        handle.raise_()
        return handle

    def _position_group_title_handle(self, name: str) -> None:
        handle = self._ensure_group_title_handle(name)
        if handle is not None:
            handle.raise_()

    def _ensure_group_selection_frame(self, name: str):
        group = self._free_group_widget(name)
        host = getattr(self, "_construction_widget", None)
        if group is None or host is None:
            return None
        frame = self._group_selection_frames.get(name)
        if frame is None:
            frame = QFrame(host)
            frame.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            frame.setStyleSheet("QFrame { background: transparent; border: 2px dashed #2878D0; }")
            frame.hide()
            self._group_selection_frames[name] = frame
        frame.setGeometry(group.geometry())
        return frame

    def _refresh_free_group_selection(self) -> None:
        for name in self._free_group_names:
            frame = self._ensure_group_selection_frame(name)
            if frame is None:
                continue
            if name in self._selected_free_groups:
                group = self._free_group_widget(name)
                if group is not None:
                    frame.setGeometry(group.geometry())
                    frame.show()
                    frame.raise_()
                    frame.repaint()
            else:
                frame.hide()

    def _field_part_sheet_rect(self, field, part: str) -> QRect:
        host=getattr(self,"_construction_widget",None)
        local=field.part_rect(part) if hasattr(field,"part_rect") else QRect(0,0,field.width(),field.height())
        top=field.mapTo(host,local.topLeft()) if host is not None else field.pos()+local.topLeft()
        return QRect(top,local.size())

    def _parts_intersecting_sheet_rect(self, rect: QRect):
        """Le lasso sélectionne des CHAMPS complets.

        Libellé + Donnée restent solidaires pour un déplacement issu du lasso.
        Les sélections fines Libellé/Donnée par clic/Ctrl+clic restent inchangées.
        """
        result = []
        for key, field in self._preview_fields.items():
            if field is None or not field.isVisible():
                continue
            label_rect = self._field_part_sheet_rect(field, "label")
            data_rect = self._field_part_sheet_rect(field, "data")
            if rect.intersects(label_rect.united(data_rect)):
                result.extend(((key, "label"), (key, "data")))
        return result

    def _store_field_part_geometry(self, field) -> None:
        scale=max(0.01,float(self._preview_scale()))
        whole=self._field_styles.setdefault(field.key,{})
        for part in ("label","data"):
            r=field.part_rect(part)
            if r is None: continue
            st=whole.setdefault(part,{})
            st["x"]=round(r.x()/scale)
            st["width"]=max(20,round(r.width()/scale))
        self._visual_positions[field.key]=(round(field.x()/scale),round(field.y()/scale))
        self._visual_sizes[field.key]=(round(field.width()/scale),round(field.height()/scale))

    def _set_two_part_rects(self, field, label_rect: QRect, data_rect: QRect) -> None:
        union=label_rect.united(data_rect)
        field.setGeometry(union.x(),union.y(),max(40,union.width()),max(26,union.height()))
        scale=max(0.01,float(self._preview_scale()))
        field.set_part_geometry(
            label_x=round((label_rect.x()-union.x())/scale),
            label_w=round(label_rect.width()/scale),
            data_x=round((data_rect.x()-union.x())/scale),
            data_w=round(data_rect.width()/scale),
        )
        self._store_field_part_geometry(field)
        field.update()

    def _set_part_absolute_rect(self, field, part: str, new_rect: QRect) -> None:
        other="data" if part=="label" else "label"
        other_rect=self._field_part_sheet_rect(field,other)
        label_rect=QRect(new_rect) if part=="label" else other_rect
        data_rect=QRect(new_rect) if part=="data" else other_rect
        self._set_two_part_rects(field,label_rect,data_rect)

    def _selected_part_columns(self, keys, part: str) -> list[list[str]]:
        """Sépare les colonnes visuelles à partir de la partie réellement alignée.

        Cas particulier important pour les Données : un champ transversal très
        large (Description, Lien, etc.) ne doit pas imposer son bord droit ou son
        centre à toute la colonne voisine. Après le regroupement par position X,
        les largeurs franchement atypiques sont donc isolées comme groupes propres.
        """
        samples = []
        for key in keys:
            key = str(key)
            field = self._preview_fields.get(key)
            if field is None or not field.isVisible():
                continue
            rect = QRect(self._field_part_sheet_rect(field, part))
            samples.append((key, rect))

        if not samples:
            return []

        samples.sort(key=lambda item: (item[1].left(), item[1].top()))
        widths = [max(1, r.width()) for _k, r in samples]
        median_w = statistics.median(widths) if widths else 80
        split_threshold = max(55, int(median_w * 0.60))

        coarse_groups = []
        current = [samples[0]]

        for item in samples[1:]:
            anchor = int(statistics.median([r.left() for _k, r in current]))
            if abs(item[1].left() - anchor) > split_threshold:
                coarse_groups.append(current)
                current = [item]
            else:
                current.append(item)
        coarse_groups.append(current)

        groups = []
        for coarse in coarse_groups:
            if part != "data" or len(coarse) < 3:
                groups.append(
                    [k for k, _r in sorted(coarse, key=lambda x: x[1].top())]
                )
                continue

            local_widths = [max(1, r.width()) for _k, r in coarse]
            local_median = statistics.median(local_widths)

            normal = []
            wide = []
            for item in coarse:
                width = item[1].width()
                # Un champ n'est isolé que s'il est vraiment transversal :
                # beaucoup plus large que ses voisins ET avec un écart absolu
                # suffisant pour ne pas réagir aux simples réglages manuels.
                if (
                    width >= local_median * 1.55
                    and width - local_median >= 90
                ):
                    wide.append(item)
                else:
                    normal.append(item)

            if normal:
                groups.append(
                    [k for k, _r in sorted(normal, key=lambda x: x[1].top())]
                )
            for item in wide:
                # Les champs transversaux restent sélectionnés, mais leur
                # alignement ne déplace aucun autre champ de la colonne.
                groups.append([item[0]])

        return groups


    def _selected_field_columns(self, keys) -> list[list[str]]:
        """Compatibilité pour l'alignement de champs complets.

        Les champs complets sont regroupés d'après leur bord gauche, sans utiliser
        le chevauchement horizontal de leur largeur totale.
        """
        samples = []
        for key in keys:
            key = str(key)
            field = self._preview_fields.get(key)
            if field is not None and field.isVisible():
                samples.append((key, QRect(field.geometry())))

        if not samples:
            return []

        samples.sort(key=lambda item: (item[1].left(), item[1].top()))
        lefts = [r.left() for _k, r in samples]
        widths = [max(1, r.width()) for _k, r in samples]
        median_w = statistics.median(widths) if widths else 120
        split_threshold = max(70, int(median_w * 0.45))

        groups = []
        current = [samples[0]]
        for item in samples[1:]:
            anchor = int(statistics.median([r.left() for _k, r in current]))
            if abs(item[1].left() - anchor) > split_threshold:
                groups.append(
                    [k for k, _r in sorted(current, key=lambda x: x[1].top())]
                )
                current = [item]
            else:
                current.append(item)

        groups.append(
            [k for k, _r in sorted(current, key=lambda x: x[1].top())]
        )
        return groups



    def _align_single_field_part(self, part: str, mode: str) -> None:
        """Applique l'alignement à Libellé ou Donnée d'un champ solitaire."""
        fields = self._selected_fields()
        if not fields or part not in {"label", "data"}:
            return
        field = fields[0]

        if mode in {"left", "center", "right"}:
            whole = self._field_styles.setdefault(field.key, {})
            style = whole.setdefault(part, {})
            style["align"] = mode
            field.apply_text_styles(whole)
            field._apply_selection_style(
                field.key in self._selected_preview_keys
            )
            self._record_history_state()

    def _align_selected_whole_fields(self, mode: str) -> None:
        """Aligne les champs complets en conservant les colonnes indépendantes."""
        fields = self._selected_fields()
        if len(fields) < 2:
            return

        keys = [field.key for field in fields]
        # Gauche/droite/centre : conserver les colonnes indépendantes.
        # Haut/bas : tous les champs sélectionnés appartiennent à UNE seule
        # opération verticale, sinon une sélection horizontale composée de
        # plusieurs colonnes ne bougeait pas.
        columns = (
            [keys]
            if mode in {"top", "bottom"}
            else self._selected_field_columns(keys)
        )
        scale = max(0.01, float(self._preview_scale()))
        changed = False

        for column_keys in columns:
            if len(column_keys) < 2:
                continue
            items = [
                (self._preview_fields[key], QRect(self._preview_fields[key].geometry()))
                for key in column_keys
            ]

            if mode == "left":
                target = min(r.left() for _f, r in items)
            elif mode == "right":
                target = max(r.right() for _f, r in items)
            elif mode == "center":
                target = round(
                    sum(r.center().x() for _f, r in items) / len(items)
                )
            elif mode == "top":
                target = min(r.top() for _f, r in items)
            elif mode == "bottom":
                target = max(r.bottom() for _f, r in items)
            else:
                continue

            for field, rect in items:
                nr = QRect(rect)
                if mode == "left":
                    nr.moveLeft(target)
                elif mode == "right":
                    nr.moveRight(target)
                elif mode == "center":
                    nr.moveCenter(QPoint(target, nr.center().y()))
                elif mode == "top":
                    nr.moveTop(target)
                elif mode == "bottom":
                    nr.moveBottom(target)
                field.move(nr.topLeft())
                self._visual_positions[field.key] = (
                    round(nr.x() / scale), round(nr.y() / scale)
                )
                field.raise_()
                changed = True

        if changed:
            self._record_history_state()


    def _align_selected_part_kind(self, part: str, mode: str) -> None:
        """Aligne les Libellés ou les Données, colonne par colonne.

        Gauche / Centre / Droite agissent à la fois sur la géométrie des zones
        et sur la justification visible du texte. Haut / Bas restent géométriques.
        """
        keys = [
            key for key in self._selected_preview_keys
            if (key, part) in self._selected_preview_parts
            and key in self._preview_fields
            and self._preview_fields[key].isVisible()
        ]
        if len(keys) < 2:
            return

        columns = self._selected_part_columns(keys, part)
        any_change = False

        for column_keys in columns:
            if len(column_keys) < 2:
                continue

            items = [
                (
                    self._preview_fields[key],
                    QRect(
                        self._field_part_sheet_rect(
                            self._preview_fields[key], part
                        )
                    ),
                )
                for key in column_keys
            ]

            if mode == "left":
                target = min(r.left() for _f, r in items)
            elif mode == "right":
                target = max(r.right() for _f, r in items)
            elif mode == "center":
                # Centre commun de la colonne calculé sur les zones sélectionnées.
                target = round(
                    sum(r.center().x() for _f, r in items) / len(items)
                )
            elif mode == "top":
                target = min(r.top() for _f, r in items)
            elif mode == "bottom":
                target = max(r.bottom() for _f, r in items)
            else:
                continue

            changes = {}
            for field, rect in items:
                nr = QRect(rect)
                if mode == "left":
                    nr.moveLeft(target)
                elif mode == "right":
                    nr.moveRight(target)
                elif mode == "center":
                    nr.moveCenter(QPoint(target, nr.center().y()))
                elif mode == "top":
                    nr.moveTop(target)
                elif mode == "bottom":
                    nr.moveBottom(target)
                changes[(field.key, part)] = nr

            self._apply_part_rect_batch(changes)
            any_change = True

            # Gauche/Centre/Droite règlent aussi la justification du contenu.
            if mode in {"left", "center", "right"}:
                for field, _rect in items:
                    whole = self._field_styles.setdefault(field.key, {})
                    style = whole.setdefault(part, {})
                    style["align"] = mode
                    field.apply_text_styles(whole)
                    field._apply_selection_style(
                        field.key in self._selected_preview_keys
                    )

        if any_change:
            self._raise_absolute_fields()
            self._record_history_state()


    def _align_selected_controls(self, mode: str) -> None:
        """Aligne les parties sélectionnées, sans déplacer les parties non sélectionnées."""
        selected = []
        for key, part in sorted(self._selected_preview_parts):
            field = self._preview_fields.get(key)
            if field is None or not field.isVisible():
                continue
            selected.append((field, part, QRect(self._field_part_sheet_rect(field, part))))

        if len(selected) < 2:
            return

        if mode == "left":
            target = min(r.left() for _f, _p, r in selected)
        elif mode == "right":
            target = max(r.right() for _f, _p, r in selected)
        elif mode == "center":
            target = round(
                sum(r.center().x() for _f, _p, r in selected) / len(selected)
            )
        elif mode == "top":
            target = min(r.top() for _f, _p, r in selected)
        else:
            target = max(r.bottom() for _f, _p, r in selected)

        # Snapshot absolu des DEUX parties avant toute modification.
        snapshots = {}
        for field, _part, _rect in selected:
            if field.key not in snapshots:
                snapshots[field.key] = {
                    "label": QRect(self._field_part_sheet_rect(field, "label")),
                    "data": QRect(self._field_part_sheet_rect(field, "data")),
                }

        for field, part, rect in selected:
            nr = QRect(rect)
            if mode == "left":
                nr.moveLeft(target)
            elif mode == "right":
                nr.moveRight(target)
            elif mode == "center":
                nr.moveCenter(QPoint(target, nr.center().y()))
            elif mode == "top":
                nr.moveTop(target)
            elif mode == "bottom":
                nr.moveBottom(target)
            snapshots[field.key][part] = nr

        for key, pair in snapshots.items():
            field = self._preview_fields[key]
            self._set_two_part_rects(field, pair["label"], pair["data"])
            field.raise_()

        self._record_history_state()


    def _fields_intersecting_sheet_rect(self, rect: QRect) -> list[str]:
        host = getattr(self, "_construction_widget", None)
        if host is None:
            return []
        keys = []
        for key, field in self._preview_fields.items():
            if field is None or not field.isVisible():
                continue
            if field.parentWidget() is host:
                field_rect = QRect(field.geometry())
            else:
                top_left = field.mapTo(host, QPoint(0, 0))
                field_rect = QRect(top_left, field.size())
            if rect.intersects(field_rect):
                keys.append(key)
        return keys

    def _groups_intersecting_sheet_rect(self, rect: QRect) -> list[str]:
        """Un cadre n'est sélectionné au lasso que s'il est ENTIÈREMENT englobé.

        Ainsi :
        - lasso à l'intérieur d'un cadre = champs seulement ;
        - lasso autour du cadre = cadre + champs ;
        - clic sur le bandeau = cadre seul.
        """
        names = []
        for name in self._free_group_names:
            group = self._free_group_widget(name)
            if (
                group is not None
                and group.isVisible()
                and rect.contains(group.geometry())
            ):
                names.append(name)
        return names

    def _raise_absolute_fields(self) -> None:
        # Empilement invariant de l'Atelier :
        #   cadres graphiques < quadrillage < champs < repères de sélection.
        # Ainsi un cadre ajouté/restauré ne peut jamais masquer un champ.
        for name in getattr(self, "_free_group_names", ()):
            group = self._free_group_widget(name)
            if group is not None and group.isVisible():
                group.lower()

        overlay = getattr(self, "_sheet_grid_overlay", None)
        if overlay is not None:
            overlay.raise_()
        for field in self._preview_fields.values():
            if field is not None and field.isVisible():
                field.raise_()
        self._refresh_free_group_selection()

    def _move_combined_selection_by(self, dx: int, dy: int) -> bool:
        """Déplace ensemble les cadres ET les champs explicitement sélectionnés."""
        moved = False

        # Cadres sélectionnés.
        proposals = {}
        for name in self._selected_free_groups:
            group = self._free_group_widget(name)
            if group is None:
                continue
            rect = QRect(group.geometry())
            rect.translate(int(dx), int(dy))
            if rect.x() < 0 or rect.y() < 0:
                return False
            proposals[name] = rect
        if proposals and not self._selected_group_proposals_valid(proposals):
            return False

        # Champs sélectionnés.
        field_proposals = {}
        host = getattr(self, "_construction_widget", None)
        for field in self._selected_fields():
            rect = QRect(field.geometry())
            rect.translate(int(dx), int(dy))
            if rect.x() < 0 or rect.y() < 0:
                return False
            if host is not None:
                if rect.right() >= host.width() or rect.bottom() >= host.height():
                    return False
            field_proposals[field.key] = rect

        for name, rect in proposals.items():
            group = self._free_group_widget(name)
            if group is not None:
                group.setGeometry(rect)
                self._persist_free_group_geometry(name)
                self._position_group_resize_handles(name)
                moved = True

        scale = max(0.01, float(self._preview_scale()))
        for field in self._selected_fields():
            rect = field_proposals.get(field.key)
            if rect is None:
                continue
            field.move(rect.topLeft())
            self._visual_positions[field.key] = (
                round(rect.x() / scale), round(rect.y() / scale)
            )
            moved = True

        if moved:
            self._raise_absolute_fields()
            self._resize_free_group_host()
        return moved

    def _set_free_group_selection(self, names, additive: bool = False) -> None:
        incoming = {str(n) for n in names if str(n) in self._free_group_names}
        if additive:
            for name in incoming:
                if name in self._selected_free_groups:
                    self._selected_free_groups.remove(name)
                else:
                    self._selected_free_groups.add(name)
        else:
            self._selected_free_groups = set(incoming)
        self._refresh_free_group_selection()
        self.setFocus(Qt.FocusReason.MouseFocusReason)

    def _persist_free_group_geometry(self, name: str) -> None:
        group = self._free_group_widget(name)
        base = self._free_group_default_geometries.get(name)
        if group is None or base is None:
            return
        style = dict(self._group_styles.get(name, {}))
        style["geometry"] = {"x": int(group.x()), "y": int(group.y()), "w": max(1,int(group.width())), "h": max(1,int(group.height()))}
        style["geometry_space"] = "atelier_px"
        style["position"] = {"dx": int(group.x()-base.x()), "dy": int(group.y()-base.y())}
        self._group_styles[name] = style

    def _selected_group_proposals_valid(self, proposals) -> bool:
        selected=set(proposals)
        for name,rect in proposals.items():
            if rect.x()<0 or rect.y()<0:
                return False
            for other_name in self._free_group_names:
                if other_name in selected:
                    continue
                other=self._free_group_widget(other_name)
                if other is not None and other.isVisible() and rect.intersects(other.geometry()):
                    return False
        return True

    def _move_selected_free_groups_by(self, dx:int, dy:int) -> bool:
        proposals={}
        for name in self._selected_free_groups:
            group=self._free_group_widget(name)
            if group is None:
                continue
            rect=QRect(group.geometry()); rect.translate(dx,dy); proposals[name]=rect
        if not proposals or not self._selected_group_proposals_valid(proposals):
            return False
        for name,rect in proposals.items():
            group=self._free_group_widget(name)
            group.setGeometry(rect)
            self._persist_free_group_geometry(name)
            self._position_group_resize_handles(name)
        self._refresh_free_group_selection()
        self._resize_free_group_host()
        return True

    def keyPressEvent(self, event) -> None:
        if self._selected_free_groups and event.key() in (Qt.Key.Key_Left,Qt.Key.Key_Right,Qt.Key.Key_Up,Qt.Key.Key_Down):
            step=10 if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1
            dx=-step if event.key()==Qt.Key.Key_Left else step if event.key()==Qt.Key.Key_Right else 0
            dy=-step if event.key()==Qt.Key.Key_Up else step if event.key()==Qt.Key.Key_Down else 0
            if self._move_selected_free_groups_by(dx,dy):
                self._record_history_state()
            event.accept(); return
        super().keyPressEvent(event)

    def eventFilter(self, watched, event):         # 11.7.70.26.32 — glisser-déposer d'un champ coché depuis la palette.
        if isinstance(watched, QWidget):
            palette_key = watched.property("_mm3_palette_field_key")
            palette_host = bool(watched.property("_mm3_palette_order_host"))
            if palette_key or palette_host:
                mime = getattr(event, "mimeData", lambda: None)()
                if mime is not None and mime.hasFormat("application/x-mm3-palette-field"):
                    if event.type() in (QEvent.Type.DragEnter, QEvent.Type.DragMove):
                        event.acceptProposedAction()
                        return True
                    if event.type() == QEvent.Type.Drop:
                        try:
                            source_key = bytes(mime.data("application/x-mm3-palette-field")).decode("utf-8")
                        except UnicodeError:
                            source_key = ""
                        if source_key in self._tab_positions:
                            target_key = str(palette_key) if palette_key else None
                            after = bool(palette_key and event.position().y() > watched.height() / 2)
                            if palette_host:
                                point = event.position().toPoint()
                                for candidate in self._tab_positions:
                                    row = self._rows.get(candidate)
                                    if row is not None and row.isVisible() and row.geometry().top() <= point.y() < row.geometry().bottom():
                                        target_key = candidate
                                        after = point.y() > row.geometry().center().y()
                                        break
                            order = self._ordered_tab_keys()
                            order.remove(source_key)
                            if target_key in order:
                                index = order.index(target_key) + int(after)
                            else:
                                index = len(order)
                            order.insert(index, source_key)
                            self._history_guard = True
                            try:
                                for number, key in enumerate(order, 1):
                                    self._tab_positions[key].setValue(number)
                            finally:
                                self._history_guard = False
                            self._rebuild_editor_groups_preserving_view()
                            self._record_history_state()
                            event.acceptProposedAction()
                            return True
            if palette_key:
                key = str(palette_key)
                if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                    self._palette_drag_press[key] = event.position().toPoint()
                elif event.type() == QEvent.Type.MouseMove and (event.buttons() & Qt.MouseButton.LeftButton):
                    origin = self._palette_drag_press.get(key)
                    if origin is not None and (event.position().toPoint() - origin).manhattanLength() >= QApplication.startDragDistance():
                        check = self._checks.get(key)
                        if check is not None:
                            mime = QMimeData()
                            mime.setData("application/x-mm3-palette-field", key.encode("utf-8"))
                            drag = QDrag(watched)
                            drag.setMimeData(mime)
                            drag.exec(Qt.DropAction.MoveAction)
                            self._palette_drag_press.pop(key, None)
                            return True
                elif event.type() == QEvent.Type.MouseButtonRelease:
                    self._palette_drag_press.pop(key, None)

        if watched is getattr(self, "_construction_widget", None):
            mime = getattr(event, "mimeData", lambda: None)()
            if mime is not None and mime.hasFormat("application/x-mm3-palette-field"):
                if event.type() in (QEvent.Type.DragEnter, QEvent.Type.DragMove):
                    event.acceptProposedAction()
                    return True
                if event.type() == QEvent.Type.Drop:
                    try:
                        key = bytes(mime.data("application/x-mm3-palette-field")).decode("utf-8")
                    except Exception:
                        key = ""
                    if key and key in self._pending_palette_placement and key in self._checks and self._checks[key].isChecked():
                        scale = max(0.01, float(self._preview_scale()))
                        point = event.position().toPoint()
                        model_w, model_h = self._visual_sizes.get(key, (260, 31))
                        px_w = max(1, int(round(model_w * scale)))
                        px_h = max(1, int(round(model_h * scale)))
                        x = max(0, point.x() - px_w // 2)
                        y = max(0, point.y() - px_h // 2)
                        self._visual_positions[key] = (round(x / scale), round(y / scale))
                        self._pending_palette_placement.discard(key)
                        self._refresh_row_style(key)
                        self._refresh_preview()
                        self._record_history_state()
                        event.acceptProposedAction()
                        return True

 # noqa: N802
        # Sécurité PySide6/Windows : un QWidgetItem n'est pas un QObject.
        if not isinstance(watched, QObject):
            return False
        if event.type() == QEvent.Type.KeyPress:
            ctrl = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
            if ctrl and event.key() == Qt.Key.Key_C:
                # Ne jamais détourner Ctrl+C d'un cadre Photo : la copie d'image
                # reste son comportement normal. Ici seuls les CHAMPS complets
                # sont mémorisés comme modèles de duplication.
                if not self._selected_free_groups and self._copy_selected_field_for_duplication():
                    event.accept()
                    return True
            if ctrl and event.key() == Qt.Key.Key_V:
                if self._paste_duplicated_field():
                    event.accept()
                    return True

        if (
            event.type() == QEvent.Type.KeyPress
            and self._selected_free_groups
            and self._selected_preview_keys
            and event.key() in (
                Qt.Key.Key_Left, Qt.Key.Key_Right,
                Qt.Key.Key_Up, Qt.Key.Key_Down,
            )
        ):
            step = 10 if (
                event.modifiers() & Qt.KeyboardModifier.ShiftModifier
            ) else 1
            dx = -step if event.key() == Qt.Key.Key_Left else step if event.key() == Qt.Key.Key_Right else 0
            dy = -step if event.key() == Qt.Key.Key_Up else step if event.key() == Qt.Key.Key_Down else 0
            if self._move_combined_selection_by(dx, dy):
                self._record_history_state()
            event.accept()
            return True

        # 23.5.1 — les flèches pilotent le ou les champs sélectionnés même si
        # Qt a déplacé momentanément le focus vers un enfant de la maquette.
        if (
            event.type() == QEvent.Type.KeyPress
            and event.key() in (
                Qt.Key.Key_Left, Qt.Key.Key_Right,
                Qt.Key.Key_Up, Qt.Key.Key_Down,
            )
            and self._preview_keyboard_active()
        ):
            step = 10 if (
                event.modifiers() & Qt.KeyboardModifier.ShiftModifier
            ) else 1
            dx = (
                -step if event.key() == Qt.Key.Key_Left
                else step if event.key() == Qt.Key.Key_Right
                else 0
            )
            dy = (
                -step if event.key() == Qt.Key.Key_Up
                else step if event.key() == Qt.Key.Key_Down
                else 0
            )
            self._nudge_selected_preview_fields(dx, dy)
            event.accept()
            return True

        # 23.9.3.0 — lasso intérieur réellement global.
        # Une partie du « fond libre » visible d'un cadre appartient au QGroupBox
        # lui-même (marges autour du canvas). Jusqu'ici ces zones tombaient dans
        # la logique de sélection/déplacement du cadre. Désormais :
        #   - bandeau + bord de redimensionnement => cadre ;
        #   - tout le reste du fond intérieur => lasso de CHAMPS.
        group_body_lasso = False
        group_resize_hit = False
        if isinstance(watched, QWidget):
            group_name = watched.property("_mm3_free_group")
            is_title_handle = bool(watched.property("_mm3_group_title_handle"))
            if group_name and not is_title_handle:
                # 23.9.3.1.1 — le canvas intérieur peut recouvrir visuellement
                # le bord bas/droit du QGroupBox. Dans ce cas le lasso recevait
                # le clic avant le moteur de redimensionnement. On teste donc
                # toujours le bord dans le repère DU GROUPE, quel que soit
                # l'enfant ayant reçu l'événement.
                group_widget = self._free_group_widget(str(group_name))
                if group_widget is not None and event.type() in (
                    QEvent.Type.MouseButtonPress,
                    QEvent.Type.MouseMove,
                    QEvent.Type.MouseButtonRelease,
                ):
                    local_group = group_widget.mapFromGlobal(
                        event.globalPosition().toPoint()
                    )
                    group_resize_hit = bool(
                        self._group_resize_edge(group_widget, local_group)
                    ) or self._free_group_resize_name == str(group_name)
            if group_name and not is_title_handle:
                group_widget = self._free_group_widget(str(group_name))
                if group_widget is watched:
                    if (
                        event.type() == QEvent.Type.MouseButtonPress
                        and event.button() == Qt.MouseButton.LeftButton
                    ):
                        local = event.position().toPoint()
                        on_resize_edge = bool(self._group_resize_edge(group_widget, local))
                        in_title_band = local.y() <= 28
                        group_body_lasso = not on_resize_edge and not in_title_band
                    elif (
                        self._group_lasso_origin is not None
                        and event.type() in (
                            QEvent.Type.MouseMove,
                            QEvent.Type.MouseButtonRelease,
                        )
                    ):
                        # Le widget ayant reçu le press conserve la souris pendant
                        # le glisser : poursuivre le lasso même hors de sa zone.
                        group_body_lasso = True

        if isinstance(watched, QWidget) and not group_resize_hit and (
            bool(watched.property("_mm3_group_lasso_surface"))
            or bool(watched.property("_mm3_group_lasso_viewport"))
            or group_body_lasso
        ):
            if event.type() == QEvent.Type.Resize:
                QTimer.singleShot(0, self._resize_free_group_host)
                return super().eventFilter(watched, event)

            def _lasso_point():
                point = event.position().toPoint()
                if watched is self._construction_widget:
                    return point
                # 23.9.2.5 — mapFrom exige une hiérarchie parent/enfant. Les
                # surfaces internes des cadres peuvent être des widgets frères ;
                # passer par les coordonnées globales fonctionne dans tous les cas.
                return self._construction_widget.mapFromGlobal(watched.mapToGlobal(point))

            if event.type()==QEvent.Type.MouseButtonPress and event.button()==Qt.MouseButton.RightButton:
                click_point = _lasso_point()
                global_point = watched.mapToGlobal(event.position().toPoint())
                self._show_atelier_background_context_menu(global_point, click_point)
                event.accept()
                return True

            if event.type()==QEvent.Type.MouseButtonPress and event.button()==Qt.MouseButton.LeftButton:
                ctrl = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
                click_point = _lasso_point()
                self._atelier_paste_point = QPoint(click_point)
                if not ctrl:
                    self._clear_preview_selection()
                self._group_lasso_origin=click_point
                if not ctrl:
                    self._set_free_group_selection([], False)
                self._group_rubber_band.setGeometry(QRect(self._group_lasso_origin,self._group_lasso_origin))
                self._group_rubber_band.show()
                return True
            if event.type()==QEvent.Type.MouseMove and self._group_lasso_origin is not None and (event.buttons() & Qt.MouseButton.LeftButton):
                self._group_rubber_band.setGeometry(QRect(self._group_lasso_origin,_lasso_point()).normalized())
                return True
            if event.type()==QEvent.Type.MouseButtonRelease and event.button()==Qt.MouseButton.LeftButton and self._group_lasso_origin is not None:
                rect=QRect(self._group_lasso_origin,_lasso_point()).normalized()
                self._group_lasso_origin=None; self._group_rubber_band.hide()
                parts = []
                if rect.width() >= 4 and rect.height() >= 4:
                    parts = self._parts_intersecting_sheet_rect(rect)

                additive = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
                # Le lasso ne sélectionne que des champs.
                # Les cadres sont réservés au clic sur leur bandeau.
                if not additive:
                    self._set_free_group_selection([], False)
                self._set_preview_part_selection(parts, additive=additive)
                self._raise_absolute_fields()
                return True

        name = watched.property("_mm3_free_group") if isinstance(watched, QWidget) else None
        name = str(name) if name else None
        if name:
            group = self._free_group_widget(name)
            if group is None:
                return super().eventFilter(watched, event)

            is_title_handle = bool(
                isinstance(watched, QWidget)
                and watched.property("_mm3_group_title_handle")
            )

            if (
                is_title_handle
                and event.type() == QEvent.Type.MouseButtonPress
                and event.button() == Qt.MouseButton.RightButton
            ):
                if name not in self._selected_free_groups:
                    self._set_free_group_selection([name], False)
                else:
                    self._refresh_free_group_selection()
                self._show_group_context_menu(
                    name, event.globalPosition().toPoint()
                )
                return True

            if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                local_in_group = group.mapFromGlobal(event.globalPosition().toPoint())
                ctrl = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)

                # Sans Ctrl : comportement classique, le cadre devient la nouvelle
                # sélection. Avec Ctrl : ajouter/retirer le cadre SANS perdre les
                # champs déjà sélectionnés (lasso ou Ctrl+clic).
                if not ctrl and name not in self._selected_free_groups:
                    self._clear_preview_selection()

                # 23.4 — ordre d'empilement corrigé :
                # le bloc passe d'abord au premier plan, puis le cadre de
                # sélection est levé EN DERNIER et reste donc visible immédiatement.
                # Le cadre reste derrière les champs : cliquer dans sa zone
                # vide ne doit jamais masquer les champs posés dessus.
                group.lower()
                self._raise_absolute_fields()

                if ctrl:
                    self._set_free_group_selection([name], True)
                    self._refresh_free_group_selection()
                    return True

                # 23.5 — un clic simple sur un bloc déjà membre d'une
                # sélection multiple NE détruit PAS le groupe. Il devient le
                # point de prise pour déplacer toute la sélection.
                if name not in self._selected_free_groups:
                    self._set_free_group_selection([name], False)
                else:
                    self._refresh_free_group_selection()

                self.setFocus(Qt.FocusReason.MouseFocusReason)

                resize_edge = "" if is_title_handle else self._group_resize_edge(group, local_in_group)
                if resize_edge:
                    self._free_group_resize_name = name
                    self._free_group_resize_edge = resize_edge
                    self._free_group_resize_press_global = event.globalPosition().toPoint()
                    self._free_group_resize_start_geom = QRect(group.geometry())
                    group.setCursor(self._group_resize_cursor(resize_edge))
                    return True

                title_drag = is_title_handle or local_in_group.y() <= 28
                if title_drag:
                    self._free_group_drag_name = name
                    self._free_group_drag_offset = local_in_group
                    self._free_group_drag_press_global = event.globalPosition().toPoint()
                    self._free_group_drag_started = False
                    self._free_group_drag_start_geom = QRect(group.geometry())
                    self._free_group_drag_start_geometries = {
                        n: QRect(g.geometry()) for n in self._selected_free_groups
                        for g in [self._free_group_widget(n)] if g is not None
                    }
                    self._free_group_drag_start_field_positions = {
                        f.key: QPoint(f.x(), f.y()) for f in self._selected_fields()
                    }
                    return True

            elif (
                event.type() == QEvent.Type.MouseMove
                and self._free_group_resize_name == name
                and self._free_group_resize_press_global is not None
                and self._free_group_resize_start_geom is not None
            ):
                current = event.globalPosition().toPoint()
                delta = current - self._free_group_resize_press_global
                proposed = self._proposed_group_resize(
                    name, group, self._free_group_resize_edge,
                    delta, QRect(self._free_group_resize_start_geom)
                )
                resolved = self._resolve_group_resize(
                    name, proposed, QRect(group.geometry())
                )
                group.setGeometry(resolved)

                # 23.5.3 — mise à jour immédiate de la zone réellement
                # disponible pour les champs, sans recréer ni déplacer ceux-ci.
                layout = group.layout()
                if layout is not None:
                    layout.invalidate()
                    layout.activate()
                canvas = self._preview_canvases.get(name)
                if canvas is not None:
                    canvas.setMaximumSize(16777215, 16777215)
                    canvas.updateGeometry()

                self._position_group_resize_handles(name)
                # 23.7.3 — le cadre reste derrière les champs pendant TOUT
                # le redimensionnement. Les champs ne disparaissent plus.
                group.lower()
                self._raise_absolute_fields()
                self._resize_free_group_host()
                return True

            elif (
                event.type() == QEvent.Type.MouseMove
                and self._free_group_drag_name == name
                and self._free_group_drag_press_global is not None
            ):
                current = event.globalPosition().toPoint()
                distance = (current - self._free_group_drag_press_global).manhattanLength()
                if not self._free_group_drag_started and distance < 5:
                    return True
                self._free_group_drag_started = True
                group.setCursor(Qt.CursorShape.ClosedHandCursor)
                target = self._construction_widget.mapFromGlobal(current) - self._free_group_drag_offset
                target.setX(max(0, target.x()))
                target.setY(max(0, target.y()))
                # SURVOL LIBRE pendant le trajet : le groupe suit la souris,
                # même au-dessus d'un autre groupe. Le dépôt seul est validé.
                anchor=self._free_group_drag_start_geometries.get(name,QRect(group.geometry()))
                dx,dy=target.x()-anchor.x(),target.y()-anchor.y()
                for n,start_rect in self._free_group_drag_start_geometries.items():
                    g=self._free_group_widget(n)
                    if g is not None:
                        g.move(start_rect.x()+dx,start_rect.y()+dy)
                        g.lower()
                for key, start_pos in getattr(
                    self, "_free_group_drag_start_field_positions", {}
                ).items():
                    field = self._preview_fields.get(key)
                    if field is not None and field.isVisible():
                        field.move(
                            max(0, start_pos.x() + dx),
                            max(0, start_pos.y() + dy),
                        )
                self._raise_absolute_fields()
                self._refresh_free_group_selection()
                self._resize_free_group_host()
                return True

            elif event.type() == QEvent.Type.MouseButtonRelease and self._free_group_resize_name == name:
                group.unsetCursor()
                self._free_group_resize_name = None
                self._free_group_resize_edge = ""
                self._free_group_resize_press_global = None
                self._free_group_resize_start_geom = None

                base = self._free_group_default_geometries.get(name)
                if base is not None:
                    style = dict(self._group_styles.get(name, {}))
                    style["geometry"] = {
                        "x": int(group.x()),
                        "y": int(group.y()),
                        "w": max(1, int(group.width())),
                        "h": max(1, int(group.height())),
                    }
                    style["geometry_space"] = "atelier_px"
                    style["position"] = {
                        "dx": int(group.x() - base.x()),
                        "dy": int(group.y() - base.y()),
                    }
                    self._group_styles[name] = style
                    self._record_history_state()

                layout = group.layout()
                if layout is not None:
                    layout.invalidate()
                    layout.activate()
                canvas = self._preview_canvases.get(name)
                if canvas is not None:
                    canvas.setMaximumSize(16777215, 16777215)
                    canvas.updateGeometry()

                self._position_group_resize_handles(name)
                group.lower()
                self._raise_absolute_fields()
                self._resize_free_group_host()
                return True

            elif (
                event.type() == QEvent.Type.MouseMove
                and self._free_group_drag_name is None
                and self._free_group_resize_name is None
            ):
                local_in_group = group.mapFromGlobal(event.globalPosition().toPoint())
                edge = self._group_resize_edge(group, local_in_group)
                if edge:
                    group.setCursor(self._group_resize_cursor(edge))
                else:
                    group.unsetCursor()

            elif event.type() == QEvent.Type.MouseButtonRelease and self._free_group_drag_name == name:
                started=self._free_group_drag_started
                starts=dict(self._free_group_drag_start_geometries)
                field_starts = dict(
                    getattr(self, "_free_group_drag_start_field_positions", {})
                )
                group.unsetCursor()
                self._free_group_drag_name=None
                self._free_group_drag_offset=None
                self._free_group_drag_press_global=None
                self._free_group_drag_started=False
                self._free_group_drag_start_geom=None
                self._free_group_drag_start_geometries={}
                self._free_group_drag_start_field_positions={}
                if started:
                    proposals={}
                    for n in starts:
                        g=self._free_group_widget(n)
                        if g is not None: proposals[n]=QRect(g.geometry())
                    if not self._selected_group_proposals_valid(proposals):
                        for n,r in starts.items():
                            g=self._free_group_widget(n)
                            if g is not None: g.setGeometry(r)
                        for key, pos in field_starts.items():
                            field = self._preview_fields.get(key)
                            if field is not None:
                                field.move(pos)
                    else:
                        for n in proposals:
                            self._persist_free_group_geometry(n)
                            self._position_group_resize_handles(n)
                        scale = max(0.01, float(self._preview_scale()))
                        for key in field_starts:
                            field = self._preview_fields.get(key)
                            if field is not None:
                                self._visual_positions[key] = (
                                    round(field.x() / scale),
                                    round(field.y() / scale),
                                )
                        self._record_history_state()
                    self._raise_absolute_fields()
                    self._refresh_free_group_selection()
                    self._resize_free_group_host()
                return True

        return super().eventFilter(watched, event)

    def _align_selected_frames(self, mode: str) -> None:
        """Aligne les cadres sélectionnés sur leur bord extrême."""
        items = [
            (name, self._free_group_widget(name))
            for name in self._selected_free_groups
        ]
        items = [(name, frame) for name, frame in items if frame is not None and frame.isVisible()]
        if len(items) < 2:
            return

        frames = [frame for _name, frame in items]
        if mode == "left":
            target = min(f.x() for f in frames)
        elif mode == "right":
            target = max(f.x() + f.width() for f in frames)
        elif mode == "top":
            target = min(f.y() for f in frames)
        else:
            target = max(f.y() + f.height() for f in frames)

        for name, frame in items:
            if mode == "left":
                frame.move(target, frame.y())
            elif mode == "right":
                frame.move(target - frame.width(), frame.y())
            elif mode == "top":
                frame.move(frame.x(), target)
            elif mode == "bottom":
                frame.move(frame.x(), target - frame.height())
            self._persist_free_group_geometry(name)
            self._position_group_resize_handles(name)

        self._refresh_free_group_selection()
        self._resize_free_group_host()
        self._record_history_state()

    def _align_selected_frames_to_grid(self) -> None:
        """Aligne chaque cadre sélectionné sur la grille visible."""
        step = max(1, int(MagneticCanvas.GRID_VISIBLE))
        changed = False
        for name in self._selected_free_groups:
            frame = self._free_group_widget(name)
            if frame is None or not frame.isVisible():
                continue
            x = round(frame.x() / step) * step
            y = round(frame.y() / step) * step
            if x != frame.x() or y != frame.y():
                frame.move(x, y)
                self._persist_free_group_geometry(name)
                self._position_group_resize_handles(name)
                changed = True
        if changed:
            self._refresh_free_group_selection()
            self._resize_free_group_host()
            self._record_history_state()

    def _size_selected_frames(self, reference_name: str, mode: str) -> None:
        """Uniformise/redimensionne les cadres sélectionnés.

        Les modes reprennent le vocabulaire des champs :
        Au contenu, Sur la grille, Au plus grand, Au plus petit,
        Au plus large et Au plus étroit.
        """
        names = [
            name for name in self._selected_free_groups
            if self._free_group_widget(name) is not None
            and self._free_group_widget(name).isVisible()
        ]
        if not names:
            return

        frames = [self._free_group_widget(name) for name in names]
        widths = [f.width() for f in frames]
        heights = [f.height() for f in frames]

        reference = self._free_group_widget(reference_name)
        ref_w = reference.width() if reference is not None else widths[0]
        ref_h = reference.height() if reference is not None else heights[0]

        if mode == "width":
            target_w, target_h = ref_w, None
        elif mode == "height":
            target_w, target_h = None, ref_h
        elif mode == "both":
            target_w, target_h = ref_w, ref_h
        elif mode == "largest":
            target_w, target_h = max(widths), max(heights)
        elif mode == "smallest":
            target_w, target_h = min(widths), min(heights)
        elif mode == "widest":
            target_w, target_h = max(widths), None
        elif mode == "narrowest":
            target_w, target_h = min(widths), None
        elif mode == "grid":
            step = max(1, int(MagneticCanvas.GRID_VISIBLE))
            target_w = target_h = None
        elif mode == "content":
            target_w = target_h = None
        else:
            return

        for name, frame in zip(names, frames):
            w, h = frame.width(), frame.height()

            if mode == "grid":
                step = max(1, int(MagneticCanvas.GRID_VISIBLE))
                w = max(20, round(w / step) * step)
                h = max(20, round(h / step) * step)
            elif mode == "content":
                hint = frame.sizeHint()
                w = max(20, hint.width())
                h = max(20, hint.height())
            else:
                if target_w is not None:
                    w = target_w
                if target_h is not None:
                    h = target_h

            frame.resize(max(1, w), max(1, h))
            self._persist_free_group_geometry(name)
            self._position_group_resize_handles(name)

        self._refresh_free_group_selection()
        self._resize_free_group_host()
        self._record_history_state()


    def _show_group_context_menu(self, block_name: str, global_pos) -> None:
        self._last_group_context = block_name
        menu = QMenu(self)
        title = menu.addAction(self._group_display_title(block_name))
        title.setEnabled(False)

        if len(self._selected_free_groups) >= 2 and block_name in self._selected_free_groups:
            selected_styles = [
                self._group_styles.get(name, {})
                for name in self._selected_free_groups
            ]
            photo_selection = all(
                name == "Photo"
                or bool(
                    isinstance(style, dict)
                    and style.get("custom_photo")
                )
                for name, style in zip(
                    self._selected_free_groups, selected_styles
                )
            )

            menu.addSeparator()
            align_menu = menu.addMenu(
                tr("Aligner les cadres Photo" if photo_selection else "Aligner", self.language)
            )
            for text, mode in (
                ("Gauche", "left"), ("Droite", "right"),
                ("Haut", "top"), ("Bas", "bottom"),
            ):
                action = align_menu.addAction(tr(text, self.language))
                action.triggered.connect(
                    lambda checked=False, m=mode: self._align_selected_frames(m)
                )
            action = align_menu.addAction(tr('Sur la grille', self.language))
            action.triggered.connect(
                lambda checked=False: self._align_selected_frames_to_grid()
            )

            size_menu = menu.addMenu(
                tr("Taille des cadres Photo" if photo_selection else "Taille", self.language)
            )
            for text, mode in (
                ("Au contenu", "content"),
                ("Sur la grille", "grid"),
                ("Au plus grand", "largest"),
                ("Au plus petit", "smallest"),
                ("Au plus large", "widest"),
                ("Au plus étroit", "narrowest"),
            ):
                action = size_menu.addAction(tr(text, self.language))
                action.triggered.connect(
                    lambda checked=False, b=block_name, m=mode:
                    self._size_selected_frames(b, m)
                )

        menu.addSeparator()
        action = menu.addAction(tr('Couleur de fond…', self.language))
        action.triggered.connect(
            lambda checked=False, b=block_name: self._choose_group_color(b, "background")
        )
        action = menu.addAction(tr('Couleur du cadre…', self.language))
        action.triggered.connect(
            lambda checked=False, b=block_name: self._choose_group_color(b, "border")
        )

        width_menu = menu.addMenu(tr('Épaisseur du cadre', self.language))
        for width in range(0, 5):
            label = "Aucun cadre" if width == 0 else f"{width} px"
            action = width_menu.addAction(tr(label, self.language))
            action.setCheckable(True)
            action.setChecked(self._group_border_width(block_name) == width)
            action.triggered.connect(
                lambda checked=False, b=block_name, w=width: self._set_group_border_width(b, w)
            )

        if block_name != "Bandeau":
            title_menu = menu.addMenu(tr('Titre du cadre', self.language))
            action = title_menu.addAction(tr('Modifier le texte…', self.language))
            action.triggered.connect(
                lambda checked=False, b=block_name: self._rename_group_title(b)
            )
            title_menu.addSeparator()
            action = title_menu.addAction(tr('Police et taille…', self.language))
            action.triggered.connect(
                lambda checked=False, b=block_name: self._choose_group_title_font(b)
            )
            action = title_menu.addAction(tr('Couleur…', self.language))
            action.triggered.connect(
                lambda checked=False, b=block_name: self._choose_group_title_color(b)
            )
            title_menu.addSeparator()
            current_title = self._group_title_style(block_name)
            for text, key, default in (
                ("Gras", "bold", True),
                ("Italique", "italic", False),
                ("Souligné", "underline", False),
            ):
                action = title_menu.addAction(tr(text, self.language))
                action.setCheckable(True)
                action.setChecked(bool(current_title.get(key, default)))
                action.triggered.connect(
                    lambda checked, b=block_name, k=key: self._set_group_title_flag(b, k, checked)
                )
            title_menu.addSeparator()
            action = title_menu.addAction(tr('Style du titre par défaut', self.language))
            action.triggered.connect(
                lambda checked=False, b=block_name: self._reset_group_title_style(b)
            )

        style_for_menu = self._group_styles.get(block_name, {})
        is_photo_frame = (
            block_name == "Photo"
            or bool(
                isinstance(style_for_menu, dict)
                and style_for_menu.get("custom_photo")
            )
        )
        if is_photo_frame:
            menu.addSeparator()
            action = menu.addAction(tr('Dupliquer le cadre Photo', self.language))
            action.triggered.connect(
                lambda checked=False, b=block_name:
                self._create_custom_photo_frame(b)
            )

        if isinstance(style_for_menu, dict) and style_for_menu.get("custom_photo"):
            menu.addSeparator()
            action = menu.addAction(tr('Supprimer le cadre Photo…', self.language))
            action.triggered.connect(
                lambda checked=False, b=block_name: self._delete_custom_photo_frame(b)
            )
        else:
            menu.addSeparator()
            label = "Supprimer le cadre Photo…" if block_name == "Photo" else "Supprimer le cadre…"
            action = menu.addAction(tr(label, self.language))
            action.triggered.connect(
                lambda checked=False, b=block_name: self._delete_graphical_frame(b)
            )

        menu.addSeparator()
        action = menu.addAction(tr('Style par défaut', self.language))
        action.triggered.connect(
            lambda checked=False, b=block_name: self._reset_group_style(b)
        )
        menu.exec(global_pos)

    def _set_group_border_width(self, block_name: str, width: int) -> None:
        style = dict(self._group_styles.get(block_name, {}))
        style["border_width"] = max(0, min(4, int(width)))
        self._group_styles[block_name] = style
        self._refresh_group_styles()
        self._record_history_state()

    def _localized_native_photo_title(self, title: str) -> str:
        """Traduction d'affichage des deux titres officiels Sables, sans modifier le modèle."""
        if str(getattr(self, "language", "fr") or "fr").lower().startswith("de"):
            return {"Photo du site": "Fundortfoto", "Photo du sable": "Sandfoto"}.get(title, title)
        return title

    def _group_display_title(self, block_name: str) -> str:
        """Titre visible uniquement ; l'identifiant technique n'est jamais exposé."""
        style = self._group_styles.get(block_name, {})
        title = style.get("title", {}) if isinstance(style, dict) else {}
        if isinstance(title, dict) and bool(title.get("hidden")):
            return ""
        value = str(title.get("text", "")).strip() if isinstance(title, dict) else ""
        return self._localized_native_photo_title(value or self._t(block_name))

    def _rename_group_title(self, block_name: str) -> None:
        current = self._group_display_title(block_name)
        text, ok = QInputDialog.getText(
            self,
            "Titre du cadre",
            "Texte affiché :",
            QLineEdit.EchoMode.Normal,
            current,
        )
        if not ok:
            return
        text = str(text).strip()
        style = dict(self._group_styles.get(block_name, {}))
        title = dict(style.get("title", {})) if isinstance(style.get("title"), dict) else {}
        # Une saisie vide signifie réellement « aucun titre ». Ne jamais
        # réafficher photo_slot_2/custom_group_1 à l'utilisateur.
        if not text:
            title.pop("text", None)
            title["hidden"] = True
        elif text == block_name:
            title.pop("text", None)
            title.pop("hidden", None)
        else:
            title["text"] = text
            title.pop("hidden", None)
        if title:
            style["title"] = title
        else:
            style.pop("title", None)
        if style:
            self._group_styles[block_name] = style
        else:
            self._group_styles.pop(block_name, None)
        self._refresh_group_styles()
        self._record_history_state()

    def _choose_group_title_font(self, block_name: str) -> None:
        current = self._group_title_style(block_name)
        font = QFont()
        family = str(current.get("family", "")).strip()
        if family:
            font.setFamily(family)
        size = int(current.get("size", 0) or 0)
        if size > 0:
            font.setPointSize(size)
        font.setBold(bool(current.get("bold", True)))
        font.setItalic(bool(current.get("italic", False)))
        font.setUnderline(bool(current.get("underline", False)))
        chosen = self._font_dialog_fr(font, "Police du titre du cadre")
        if chosen is None:
            return
        style = dict(self._group_styles.get(block_name, {}))
        title = dict(style.get("title", {})) if isinstance(style.get("title"), dict) else {}
        title.update({
            "family": chosen.family(),
            "size": chosen.pointSize(),
            "bold": chosen.bold(),
            "italic": chosen.italic(),
            "underline": chosen.underline(),
        })
        style["title"] = title
        self._group_styles[block_name] = style
        self._refresh_group_styles()
        self._record_history_state()

    def _choose_group_title_color(self, block_name: str) -> None:
        current = self._group_title_style(block_name)
        color = self._choose_color_fr(
            QColor(str(current.get("color", "#000000"))),
            "Couleur du titre du cadre",
        )
        if color is None:
            return
        style = dict(self._group_styles.get(block_name, {}))
        title = dict(style.get("title", {})) if isinstance(style.get("title"), dict) else {}
        title["color"] = color.name()
        style["title"] = title
        self._group_styles[block_name] = style
        self._refresh_group_styles()
        self._record_history_state()

    def _set_group_title_flag(self, block_name: str, key: str, value: bool) -> None:
        style = dict(self._group_styles.get(block_name, {}))
        title = dict(style.get("title", {})) if isinstance(style.get("title"), dict) else {}
        title[key] = bool(value)
        style["title"] = title
        self._group_styles[block_name] = style
        self._refresh_group_styles()
        self._record_history_state()

    def _reset_group_title_style(self, block_name: str) -> None:
        style = dict(self._group_styles.get(block_name, {}))
        if "title" not in style:
            return
        style.pop("title", None)
        if style:
            self._group_styles[block_name] = style
        else:
            self._group_styles.pop(block_name, None)
        self._refresh_group_styles()
        self._record_history_state()

    def _choose_group_color(self, block_name: str, part: str) -> None:
        background, border = self._group_colors(block_name)
        initial = background if part == "background" else border
        title = "Couleur de fond du cadre" if part == "background" else "Couleur du contour du cadre"
        color = self._choose_color_fr(QColor(initial), title)
        if color is None:
            return
        style = dict(self._group_styles.get(block_name, {}))
        style[part] = color.name()
        self._group_styles[block_name] = style
        self._refresh_group_styles()
        self._record_history_state()

    def _reset_group_style(self, block_name: str) -> None:
        if block_name in self._group_styles:
            self._group_styles.pop(block_name, None)
            self._refresh_group_styles()
            self._record_history_state()

    def _sync_legacy_positions_from_visual(self) -> None:
        """Convertit X/Y en ordre interne pour garder la Fiche actuelle cohérente."""
        self._updating_positions = True
        try:
            for block in MODEL_BLOCKS:
                keys = [
                    key for key, combo in self._blocks.items()
                    if combo.currentText() == block and key in self._visual_positions
                ]
                keys.sort(
                    key=lambda key: (
                        self._visual_positions[key][1],
                        self._visual_positions[key][0],
                        key,
                    )
                )
                for index, key in enumerate(keys, start=1):
                    self._positions[key].setValue(index)
        finally:
            self._updating_positions = False

    def _fixed_block_and_position(self, key: str) -> tuple[str, int]:
        for group_title, keys in GROUPS:
            if key in keys:
                return group_title, keys.index(key)
        return "Identification", 99

    def _field_block_and_position(self, key: str) -> tuple[str, int]:
        if key in self._blocks:
            return self._blocks[key].currentText(), self._positions[key].value() - 1
        return self._fixed_block_and_position(key)

    def _ordered_movable_keys(self, block: str, preferred_key: str | None = None) -> list[str]:
        keys = [key for key, combo in self._blocks.items() if combo.currentText() == block]
        keys.sort(key=lambda k: (self._positions[k].value(), k))
        if preferred_key in keys:
            requested = max(1, self._positions[preferred_key].value())
            keys.remove(preferred_key)
            keys.insert(min(requested - 1, len(keys)), preferred_key)
        return keys

    def _renumber_block(self, block: str, preferred_key: str | None = None) -> None:
        keys = self._ordered_movable_keys(block, preferred_key)
        self._updating_positions = True
        try:
            for index, key in enumerate(keys, start=1):
                self._positions[key].setValue(index)
        finally:
            self._updating_positions = False

    def _normalize_all_positions(self) -> None:
        for block in self._palette_group_names():
            self._renumber_block(block)

    def _rebuild_editor_groups_preserving_view(self) -> None:
        bar = self._editor_scroll.verticalScrollBar()
        old_value = bar.value()
        focus_widget = self.focusWidget()
        self._rebuild_editor_groups()
        bar.setValue(old_value)
        QTimer.singleShot(0, lambda b=bar, v=old_value: b.setValue(v))
        if focus_widget is not None:
            def _restore_focus_safely(w=focus_widget):
                try:
                    from shiboken6 import isValid
                    if isValid(w):
                        w.setFocus(Qt.FocusReason.OtherFocusReason)
                except (RuntimeError, ReferenceError):
                    pass
            QTimer.singleShot(0, _restore_focus_safely)

    def _on_position_changed(self, key: str) -> None:
        if self._updating_positions:
            return
        # Pendant l'utilisation des flèches, ne pas déplacer physiquement la ligne :
        # le QSpinBox reste sous la souris et garde le focus. Les autres numéros sont
        # néanmoins décalés immédiatement pour préserver l'unicité des positions.
        self._renumber_block(self._blocks[key].currentText(), preferred_key=key)
        self._refresh_preview()

    def _finish_position_edit(self, key: str) -> None:
        # Une fois le réglage terminé (focus quitté / validation), la ligne rejoint
        # réellement sa nouvelle place dans le groupe.
        if self._updating_positions:
            return
        self._rebuild_editor_groups_preserving_view()
        self._refresh_preview()
        self._record_history_state()

    def _on_block_changed(self, key: str) -> None:
        if self._updating_positions:
            return
        target = self._blocks[key].currentText()
        self._renumber_block(target, preferred_key=key)
        for block in self._palette_group_names():
            if block != target:
                self._renumber_block(block)
        self._rebuild_editor_groups_preserving_view()
        self._refresh_preview()
        self._record_history_state()

    def _erase_field_from_sheet(self, key: str) -> None:
        """Retire un champ placé de la Fiche, comme un décochage de palette."""
        key = str(key)
        check = self._checks.get(key)
        if check is None or key in {"record_number", "record_state", "photo_data"}:
            return
        if check.isChecked():
            # Laisser le signal toggled déclencher le chemin unique de retrait :
            # aperçu, état pending, styles et historique restent ainsi synchronisés.
            check.setChecked(False)
        else:
            self._pending_palette_placement.discard(key)
            field = self._preview_fields.get(key)
            if field is not None:
                field.hide()
            self._refresh_row_style(key)
            self._refresh_preview()
            self._record_history_state()

    def _on_visibility_changed(self, key: str) -> None:
        if key == "photo_data":
            checked = bool(self._checks.get(key) and self._checks[key].isChecked())
            self._on_primary_photo_frame_visibility_changed(checked)
            self._refresh_row_style(key)
            return

        checked = bool(self._checks.get(key) and self._checks[key].isChecked())
        if key not in {"record_number", "record_state"}:
            if checked:
                # Ne pas réutiliser l'ancien emplacement : le champ attend son
                # nouveau dépôt depuis la palette.
                self._pending_palette_placement.add(str(key))
            else:
                self._pending_palette_placement.discard(str(key))
                field = self._preview_fields.get(str(key))
                if field is not None:
                    field.hide()
        self._refresh_row_style(key)
        self._refresh_preview()
        self._record_history_state()

    def _on_primary_photo_frame_visibility_changed(self, checked: bool) -> None:
        """Même cycle de visibilité que les cadres Photo supplémentaires."""
        if "photo_data" in self._checks:
            blocker = self._checks["photo_data"].blockSignals(True)
            self._checks["photo_data"].setChecked(bool(checked))
            self._checks["photo_data"].blockSignals(blocker)
        style = dict(self._group_styles.get("Photo", {}))
        style["frame_deleted"] = not bool(checked)
        self._group_styles["Photo"] = style
        group = getattr(self, "_preview_photo_group", None)
        if group is not None:
            group.setVisible(bool(checked))
            if checked:
                group.lower()
                self._raise_absolute_fields()
        self._resize_free_group_host()
        self._record_history_state()

    def _on_photo_frame_visibility_changed(self, name: str, checked: bool) -> None:
        style = dict(self._group_styles.get(name, {}))
        style["frame_deleted"] = not bool(checked)
        self._group_styles[name] = style
        group = self._free_group_widget(name)
        if group is not None:
            group.setVisible(bool(checked))
            if checked:
                group.lower()
                self._raise_absolute_fields()
        self._resize_free_group_host()
        self._record_history_state()

    def _refresh_row_style(self, key: str) -> None:
        active = self._checks[key].isChecked()
        pending = key in getattr(self, "_pending_palette_placement", set())
        if active and pending:
            # Champ coché mais pas encore placé : aspect normal/noir.
            self._checks[key].setStyleSheet("")
            self._checks[key].setToolTip("Champ disponible : faites glisser cette ligne sur la fiche pour le placer.")
            self._labels[key].setStyleSheet("")
        elif active:
            # Champ déjà placé : brun-rouge MM3 pour le repérer d'un coup d'œil.
            self._checks[key].setStyleSheet("font-weight: 600; color: #8B3026;")
            self._checks[key].setToolTip("Champ placé sur la fiche.")
            self._labels[key].setStyleSheet("")
        else:
            self._checks[key].setStyleSheet("color: #9AA39E;")
            self._labels[key].setStyleSheet(
                "color: #9AA39E; background: #F0F2F1; border: 1px solid #D7DDDA;"
            )

    def _refresh_all_row_styles(self) -> None:
        for key in self._checks:
            self._refresh_row_style(key)

    @staticmethod
    def _clear_layout_without_deleting(layout: QVBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget() is not None:
                item.widget().setParent(None)

    def _rebuild_editor_groups(self) -> None:
        layout = self._editor_layouts.get("__all__")
        if layout is None:
            return
        self._clear_layout_without_deleting(layout)

        entries = []
        for key in self._rows:
            # Le cadre Photo principal est affiché séparément après les champs
            # afin de rester hors ordre de tabulation.
            if key == "photo_data":
                continue
            tab = self._tab_positions.get(key)
            tab_value = tab.value() if tab is not None else 9999
            label = self._checks[key].text() if key in self._checks else key
            entries.append((tab_value, label.casefold(), key))

        entries.sort()
        for _tab, _label, key in entries:
            layout.addWidget(self._rows[key])

        # 11.4.20 — réutiliser la vraie ligne photo_data déjà créée avec les
        # autres champs. Elle ne peut ainsi plus disparaître lors d'une
        # reconstruction de palette. Son libellé vient du titre réel du cadre.
        if "photo_data" in self._rows and "photo_data" in self._checks:
            primary_title = self._group_display_title("Photo").strip() or "Photo"
            self._checks["photo_data"].setText(primary_title)
            deleted = bool(self._group_styles.get("Photo", {}).get("frame_deleted"))
            blocker = self._checks["photo_data"].blockSignals(True)
            self._checks["photo_data"].setChecked(not deleted)
            self._checks["photo_data"].blockSignals(blocker)
            layout.addWidget(self._rows["photo_data"])

        # Les cadres Photo supplémentaires n'ont pas d'ordre de tabulation.
        # les champs sans les mélanger à leur numérotation.
        for name, row in getattr(self, "_photo_frame_rows", {}).items():
            if name == "Photo":
                continue
            # 11.4.19 — le libellé visible de chaque cadre Photo est toujours
            # resynchronisé depuis le titre réel du cadre. Cela évite notamment
            # que le premier cadre historique perde « Couverture » après une
            # reconstruction de la palette.
            check = getattr(self, "_photo_frame_checks", {}).get(name)
            if check is not None:
                title = self._group_display_title(name).strip() or ("Photo" if name == "Photo" else name)
                check.setText(title)
                deleted = bool(self._group_styles.get(name, {}).get("frame_deleted"))
                blocker = check.blockSignals(True)
                check.setChecked(not deleted)
                check.blockSignals(blocker)
            layout.addWidget(row)
        layout.addStretch(1)

    @staticmethod
    def _clear_grid(layout: QGridLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _example_for_key(self, key: str) -> str:
        spec = self._field_spec(key)
        if spec is not None and key.startswith("custom_"):
            if spec.field_type == "date":
                return "JJ/MM/AAAA"
            if spec.field_type == "numeric":
                return "0"
            if spec.field_type == "boolean":
                return "Oui / Non"
            if spec.field_type == "list":
                return "Exemple ▼"

        # Les anciens champs standards à référentiel sont de vraies listes
        # déroulantes dans la Fiche. L'Atelier doit donc les signaler dès la
        # première création du modèle, sans exiger un aller-retour Texte -> Liste.
        # Le petit triangle n'est qu'un indicateur visuel d'aperçu : il ne dépend
        # pas de la présence de valeurs dans le référentiel.
        if spec is not None and bool(getattr(spec, "referential", None)):
            if key == "minimum_magnification":
                return "20 X ▼"
            return "Exemple ▼"

        # Exception : date et champs numériques natifs, qui montrent leur nature.
        examples = {
            "record_number": "1",
            "acquisition_date": "JJ/MM/AAAA",
            "box_count": "1",
            "price": "0,00 €",
            "total_cost": "0,00 €",
            "minimum_magnification": "20 X",
            "photo_data": "📷  Photo",
        }
        return examples.get(key, "Exemple")

    def _make_preview_value(self, key: str) -> QWidget:
        if key == "photo_data":
            box = QLabel("📷\nPhoto")
            box.setAlignment(Qt.AlignmentFlag.AlignCenter)
            box.setMinimumSize(170, 90)
            box.setStyleSheet(
                "background: #F5F6F5; border: 1px solid #CAD3CF; "
                "border-radius: 5px; color: #87928C; font-size: 16px;"
            )
            return box

        value = QLabel(self._example_for_key(key))
        value.setMinimumHeight(25)
        value.setMinimumWidth(180)
        value.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        value.setStyleSheet(
            "background: white; border: 1px solid #C8D1CC; border-radius: 4px; "
            "padding: 3px 6px; color: #718078;"
        )
        return value

    @staticmethod
    def _rect_overlap_area(a: QRect, b: QRect) -> int:
        inter = a.intersected(b)
        if inter.isEmpty():
            return 0
        return max(0, inter.width()) * max(0, inter.height())

    def _preview_field_overlap_score(self, field, rect: QRect) -> int:
        score = 0
        parent = field.parentWidget()
        for other in self._preview_fields.values():
            if other is field or not other.isVisible() or other.parentWidget() is not parent:
                continue
            score += self._rect_overlap_area(rect, QRect(other.geometry()))
        return score

    def _preview_field_rect_valid(self, field, rect: QRect, ignored_keys=None) -> bool:
        """En mode feuille libre, l'utilisateur est seul maître du placement."""
        if getattr(self, "_absolute_field_mode", False):
            return True
        ignored = set(ignored_keys or ())
        parent = field.parentWidget()
        for other in self._preview_fields.values():
            if other is field or other.key in ignored or not other.isVisible():
                continue
            if other.parentWidget() is not parent:
                continue
            if rect.intersects(QRect(other.geometry())):
                return False
        return True

    def _preview_field_proposals_valid(self, proposals: dict) -> bool:
        moving = set(proposals)
        for key, rect in proposals.items():
            field = self._preview_fields.get(key)
            if field is None:
                continue
            if not self._preview_field_rect_valid(field, rect, ignored_keys=moving):
                return False
        keys = list(proposals)
        for i, key_a in enumerate(keys):
            fa = self._preview_fields.get(key_a)
            if fa is None:
                continue
            for key_b in keys[i + 1:]:
                fb = self._preview_fields.get(key_b)
                if fb is None or fa.parentWidget() is not fb.parentWidget():
                    continue
                if proposals[key_a].intersects(proposals[key_b]):
                    return False
        return True

    def _snap_preview_field_rect(self, field, rect: QRect, threshold: int = 2) -> QRect:
        """Contact visuel exact avec un champ voisin si son bord est proche."""
        best = QRect(rect)
        best_dist = threshold + 1
        for other in self._preview_fields.values():
            if other is field or not other.isVisible() or other.parentWidget() is not field.parentWidget():
                continue
            o = QRect(other.geometry())

            # Snap vertical si les projections X se croisent.
            x_overlap = not (best.right() < o.left() or best.left() > o.right())
            if x_overlap:
                for ny in (o.top() - best.height(), o.bottom() + 1):
                    d = abs(ny - best.y())
                    test = QRect(best.x(), ny, best.width(), best.height())
                    if d <= threshold and d < best_dist and self._preview_field_rect_valid(field, test):
                        best = test
                        best_dist = d

            # Snap horizontal si les projections Y se croisent.
            y_overlap = not (best.bottom() < o.top() or best.top() > o.bottom())
            if y_overlap:
                for nx in (o.left() - best.width(), o.right() + 1):
                    d = abs(nx - best.x())
                    test = QRect(nx, best.y(), best.width(), best.height())
                    if d <= threshold and d < best_dist and self._preview_field_rect_valid(field, test):
                        best = test
                        best_dist = d
        return best

    def _nearest_valid_field_drop(self, field, rect: QRect, start_rect: QRect | None = None) -> QRect:
        """Dépôt d'un champ : survol libre, dépôt exact.

        Si la position finale est valide, on la garde telle quelle.
        Si elle chevauche réellement un autre champ, retour exact à la position
        du début du déplacement. Aucun magnétisme/ressort caché.
        """
        if self._preview_field_rect_valid(field, rect):
            return QRect(rect)
        return QRect(start_rect if start_rect is not None else field.geometry())


    def _resolve_preview_field_rect(self, field, proposed: QRect, previous: QRect) -> QRect:
        """Déplacement au pixel ; contact autorisé ; recouvrement jamais aggravé."""
        proposed_score = self._preview_field_overlap_score(field, proposed)
        previous_score = self._preview_field_overlap_score(field, previous)

        if proposed_score == 0:
            return self._snap_preview_field_rect(field, proposed)

        # Permet de sortir d'une ancienne géométrie déjà en conflit.
        if previous_score > 0 and proposed_score < previous_score:
            return proposed

        dx = proposed.x() - previous.x()
        dy = proposed.y() - previous.y()
        distance = max(abs(dx), abs(dy), 1)
        last = QRect(previous)
        last_score = previous_score

        for step in range(1, distance + 1):
            ratio = step / distance
            candidate = QRect(
                round(previous.x() + dx * ratio),
                round(previous.y() + dy * ratio),
                proposed.width(), proposed.height(),
            )
            score = self._preview_field_overlap_score(field, candidate)
            if score == 0 or (last_score > 0 and score <= last_score):
                last = candidate
                last_score = score
            else:
                break

        return self._snap_preview_field_rect(field, last) if last_score == 0 else last


    def _resolve_preview_field_resize(self, field, proposed: QRect, previous: QRect) -> QRect:
        """Redimensionnement au pixel jusqu'au contact exact, sans recouvrement."""
        if self._preview_field_rect_valid(field, proposed):
            return QRect(proposed)

        dx = proposed.x() - previous.x()
        dy = proposed.y() - previous.y()
        dw = proposed.width() - previous.width()
        dh = proposed.height() - previous.height()
        distance = max(abs(dx), abs(dy), abs(dw), abs(dh), 1)
        last = QRect(previous)

        for step in range(1, distance + 1):
            ratio = step / distance
            candidate = QRect(
                round(previous.x() + dx * ratio),
                round(previous.y() + dy * ratio),
                max(DraggablePreviewField.MIN_W, round(previous.width() + dw * ratio)),
                max(DraggablePreviewField.MIN_H, round(previous.height() + dh * ratio)),
            )
            if self._preview_field_rect_valid(field, candidate):
                last = candidate
            else:
                break
        return last


    def _activate_absolute_field_plane(self) -> None:
        """Migre une fois les champs des anciens canvases vers la feuille globale."""
        if not getattr(self, "_absolute_field_mode", False):
            return
        host = getattr(self, "_construction_widget", None)
        if host is None:
            return

        scale = max(0.01, float(self._preview_scale()))
        already_absolute = self._stored_field_space == "sheet_absolute_v1"

        for key, field in list(self._preview_fields.items()):
            if field is None:
                continue

            if already_absolute:
                model_x, model_y = self._visual_positions.get(key, (12, 12))
                target = QPoint(round(model_x * scale), round(model_y * scale))
            else:
                # Conversion exacte de ce que l'utilisateur voit actuellement :
                # ancien parent local -> coordonnées feuille.
                target = host.mapFromGlobal(field.mapToGlobal(QPoint(0, 0)))
                self._visual_positions[key] = (
                    round(target.x() / scale),
                    round(target.y() / scale),
                )

            if field.parentWidget() is not host:
                field.setParent(host)
            field.move(target)
            if field.isVisible():
                field.show()
                field.raise_()

        self._absolute_fields_ready = True
        meta = dict(self._group_styles.get("__mm3_layout__", {}))
        meta["field_space"] = "sheet_absolute_v1"
        self._group_styles["__mm3_layout__"] = meta
        self._stored_field_space = "sheet_absolute_v1"
        self._resize_free_group_host()
        self._refresh_preview_absolute()

    def _refresh_preview_absolute(self) -> None:
        """Champs indépendants des cadres : coordonnées absolues sur la feuille."""
        host = getattr(self, "_construction_widget", None)
        if host is None:
            return

        photo_visible = bool(
            self._checks.get("photo_data")
            and self._checks["photo_data"].isChecked()
            and not bool(self._group_styles.get("Photo", {}).get("frame_deleted"))
        )
        if hasattr(self, "_preview_photo_group"):
            self._preview_photo_group.setVisible(photo_visible)

        # Les cadres sont graphiques et indépendants des champs. Une suppression
        # mémorisée doit toutefois être respectée : aucun ancien cadre ne peut
        # se réafficher tout seul lors d'un rafraîchissement.
        for name, group in self._preview_groups.items():
            if bool(self._group_styles.get(name, {}).get("frame_deleted")):
                group.hide()
                continue
            if name != "Photo":
                group.show()
                group.lower()
                canvas = self._preview_canvases.get(name)
                if canvas is not None:
                    canvas.show()
                    canvas.update()

        visible_keys = set()
        scale = max(0.01, float(self._preview_scale()))
        for key, check in self._checks.items():
            if key == "photo_data":
                continue
            if key != "record_number" and not check.isChecked():
                continue
            if key in getattr(self, "_pending_palette_placement", set()):
                continue

            spec = self._field_spec(key)
            if spec is None:
                continue
            label = self._labels[key].text().strip() or spec.label

            field = self._preview_fields.get(key)
            if field is None:
                field = DraggablePreviewField(self, key, label, host)
                self._preview_fields[key] = field
            elif field.parentWidget() is not host:
                field.setParent(host)

            field.set_label(label)
            field.set_example(self._example_for_key(key))
            model_w, model_h = self._visual_sizes.get(key, (260, 31))
            model_x, model_y = self._visual_positions.get(key, (12, 12))
            rect = field_outer_rect(model_x, model_y, model_w, model_h, scale)

            field.resize(max(field.MIN_W, rect.width()), max(field.MIN_H, rect.height()))
            field.apply_shared_field_geometry(scale)
            field.move(max(0, rect.x()), max(0, rect.y()))
            field.show()
            field.raise_()
            field._apply_selection_style(key in self._selected_preview_keys)
            visible_keys.add(key)

        for key, field in self._preview_fields.items():
            if key not in visible_keys:
                field.hide()

        self._refresh_field_styles()
        self._refresh_group_styles()
        # Quadrillage unique au-dessus des cadres, champs au-dessus du quadrillage.
        overlay = getattr(self, "_sheet_grid_overlay", None)
        if overlay is not None:
            overlay.raise_()
        for key in visible_keys:
            field = self._preview_fields.get(key)
            if field is not None:
                field.raise_()
        self._resize_free_group_host()

    def _refresh_preview(self, *_args) -> None:
        """Met à jour la maquette sans recréer les objets déplaçables."""
        if (
            getattr(self, "_absolute_field_mode", False)
            and getattr(self, "_absolute_fields_ready", False)
        ):
            self._refresh_preview_absolute()
            return
        visible_by_block = {name: [] for name in self._preview_canvases}

        photo_visible = bool(self._checks.get("photo_data") and self._checks["photo_data"].isChecked())
        if hasattr(self, "_preview_photo_group"):
            self._preview_photo_group.setVisible(photo_visible)

        for key, check in self._checks.items():
            if key == "photo_data":
                continue
            # N° est structurel : jamais masqué, même par une ancienne collection.
            if key != "record_number" and not check.isChecked():
                continue
            if key in getattr(self, "_pending_palette_placement", set()):
                continue
            block, _position = self._field_block_and_position(key)
            if block not in visible_by_block:
                continue
            spec = self._field_spec(key)
            if spec is None:
                continue
            label = self._labels[key].text().strip() or spec.label
            visible_by_block[block].append((key, label))

        visible_keys = set()
        for block, entries in visible_by_block.items():
            group = self._preview_groups[block]
            canvas = self._preview_canvases[block]
            group.setVisible(
                not bool(self._group_styles.get(block, {}).get("frame_deleted"))
                and (bool(entries) or block in getattr(self, "_custom_group_names", []))
            )

            # Adapter grossièrement la hauteur du groupe aux coordonnées existantes.
            max_y = 0
            for key, _label in entries:
                x, y = self._visual_positions.get(key, (12, 12))
                max_y = max(max_y, y + 45)
            scale = self._preview_scale()
            canvas.setMinimumHeight(max(105, int((max_y + 15) * scale)))

            for key, label in entries:
                visible_keys.add(key)
                field = self._preview_fields.get(key)
                if field is None:
                    field = DraggablePreviewField(self, key, label, canvas)
                    self._preview_fields[key] = field
                elif field.parentWidget() is not canvas:
                    field.setParent(canvas)

                field.set_label(label)
                field.set_example(self._example_for_key(key))
                scale = self._preview_scale()
                model_w, model_h = self._visual_sizes.get(key, (260, 31))
                model_x, model_y = self._visual_positions.get(key, (12, 12))

                shared_rect = field_outer_rect(
                    model_x, model_y, model_w, model_h, scale
                )
                w = max(field.MIN_W, shared_rect.width())
                h = max(field.MIN_H, shared_rect.height())
                field.resize(w, h)
                field.apply_shared_field_geometry(scale)

                # 018.4.4.1.5.22.8 — la géométrie enregistrée EST l'autorité.
                # À l'ouverture, le canvas n'a pas encore forcément sa taille
                # finale : le brider ici réécrivait visuellement Etat de la fiche
                # et Minéral 2 près de leur ancienne position.
                x = max(0, shared_rect.x())
                y = max(0, shared_rect.y())
                field.move(x, y)
                field.show()
                field.raise_()
                field._apply_selection_style(key in self._selected_preview_keys)

        for key, field in self._preview_fields.items():
            if key not in visible_keys:
                field.hide()
        self._refresh_field_styles()
        self._refresh_group_styles()

    def _select_all_present_fields(self) -> None:
        """Sélectionne tous les champs réellement présents sur la fiche.

        Les cases de la palette pilotent la visibilité ; ce bouton est désormais
        un vrai outil de sélection graphique pour mise en forme globale.
        """
        keys = [
            str(key)
            for key, field in self._preview_fields.items()
            if (
                field is not None
                and field.isVisible()
                and key in self._checks
                and self._checks[key].isChecked()
                and key != "photo_data"
            )
        ]
        self._set_free_group_selection([], False)
        self._set_preview_selection(keys)
        self._raise_absolute_fields()

    def _clear_all_design_selection(self) -> None:
        """Désélectionne champs et cadres sans masquer aucun élément."""
        self._clear_preview_selection()
        self._set_free_group_selection([], False)
        self._refresh_free_group_selection()

    def _set_all(self, checked: bool) -> None:
        previous_guard = self._history_guard
        self._history_guard = True
        try:
            for check in self._checks.values():
                check.setChecked(bool(checked))
        finally:
            self._history_guard = previous_guard
        self._refresh_all_row_styles()
        self._refresh_preview()
        self._record_history_state()

    # ------------------------------------------------------------------
    # 018.4.4.1.2.9 — Défaire / Refaire
    # ------------------------------------------------------------------
    def _normalized_field_styles(self, source=None) -> dict:
        source = self._field_styles if source is None else source
        if not isinstance(source, dict):
            return {}
        result = {}
        style_keys = {"family", "size", "bold", "italic", "underline", "color", "align", "valign", "wrap", "x", "width"}
        # Métadonnées de champ qui vivent volontairement au premier niveau.
        # Elles ne doivent surtout pas être perdues lors de la normalisation
        # des styles Libellé/Donnée. 11.4.35 avait ajouté default_value, mais
        # l'ancienne normalisation ne conservait que label/data : la valeur
        # était donc visible jusqu'à la fermeture de l'Atelier puis oubliée.
        metadata_keys = {"default_value", "field_deleted", "currency_symbol", "currency_decimals", "result_suffix"}
        for key, raw in source.items():
            if not isinstance(raw, dict):
                continue
            normalized = {k: raw[k] for k in metadata_keys if k in raw}
            # Nouveau format imbriqué.
            for part in ("label", "data"):
                value = raw.get(part)
                if isinstance(value, dict):
                    cleaned = {k: v for k, v in value.items() if k in style_keys}
                    if cleaned:
                        normalized[part] = cleaned
            if "label" in normalized or "data" in normalized:
                result[str(key)] = normalized
                continue
            # Ancien format plat : il concernait le libellé.
            flat = {k: v for k, v in raw.items() if k in style_keys}
            if flat:
                normalized["label"] = flat
            if normalized:
                result[str(key)] = normalized
        return result

    def _sync_graphical_frames_from_history(self) -> None:
        """Synchronise les cadres visibles après Défaire/Refaire.

        Un Undo doit restaurer immédiatement le cadre COMPLET, titre compris,
        sans nécessiter de fermer/réouvrir l'Atelier.
        """
        standard = (
            "Bandeau", "Identification", "Photo",
            "Localisation", "Aspect", "Acquisition", "Collection",
        )

        # 11.7.61 — détruire les cadres personnalisés qui appartiennent à
        # l'état que l'on quitte mais PAS au snapshot restauré. Les masquer ne
        # suffit pas : un cadre Photo importé peut rester peint jusqu'au prochain
        # cycle d'événements et laisser une « ombre » dans l'Atelier.
        restored_custom_names = {
            str(name) for name, style in self._group_styles.items()
            if isinstance(style, dict)
            and bool(style.get("custom_group") or style.get("custom_photo"))
        }
        for stale_name in list(self._preview_groups.keys()):
            stale_style = self._group_styles.get(str(stale_name), {})
            is_standard = str(stale_name) in {
                "Bandeau", "Identification", "Photo", "Localisation",
                "Aspect", "Acquisition", "Collection",
            }
            if is_standard or str(stale_name) in restored_custom_names:
                continue
            # Seuls les cadres dynamiques peuvent devenir orphelins lors d'un
            # Undo d'import. Nettoyage graphique complet, sans toucher au modèle
            # ni enregistrer un nouvel état historique.
            group = self._preview_groups.pop(stale_name, None)
            self._preview_canvases.pop(stale_name, None)
            if group is not None:
                group.hide(); group.setParent(None); group.deleteLater()
            frame = self._group_selection_frames.pop(stale_name, None)
            if frame is not None:
                frame.hide(); frame.setParent(None); frame.deleteLater()
            handle = self._group_title_handles.pop(stale_name, None)
            if handle is not None:
                handle.hide(); handle.setParent(None); handle.deleteLater()
            for resize_handle in self._free_group_resize_handles.pop(stale_name, []):
                resize_handle.hide(); resize_handle.setParent(None); resize_handle.deleteLater()
            self._selected_free_groups.discard(stale_name)
            self._free_group_default_geometries.pop(stale_name, None)

        # Cadres personnalisés présents dans l'état restauré.
        custom_names = [
            str(name) for name, style in self._group_styles.items()
            if isinstance(style, dict)
            and bool(style.get("custom_group") or style.get("custom_photo"))
        ]
        self._custom_group_names = custom_names

        wanted = []
        for name in standard:
            style = self._group_styles.get(name, {})
            if not bool(
                isinstance(style, dict) and style.get("frame_deleted")
            ):
                wanted.append(name)
        for name in custom_names:
            if name not in wanted:
                wanted.append(name)

        self._free_group_names = tuple(wanted)

        # Recréer au besoin les cadres personnalisés détruits par une suppression.
        for name in custom_names:
            if name not in self._preview_groups:
                self._build_custom_group_after_layout(name)

        # Cadres historiques : ils existent dans la surface ; les réafficher
        # immédiatement et restaurer leur titre/poignées.
        for name in standard:
            # 11.4.19 — Photo ne doit plus être exclu de Défaire/Refaire.
            # Le premier cadre Photo est historique techniquement, mais il doit
            # suivre exactement le même cycle de restauration que les autres.
            group = self._free_group_widget(name) if name == "Photo" else self._preview_groups.get(name)
            if group is None:
                continue
            deleted = bool(
                self._group_styles.get(name, {}).get("frame_deleted")
            )
            if deleted:
                group.hide()
                continue
            group.setTitle(self._group_display_title(name))
            group.show()
            group.lower()
            self._create_group_resize_handles(name, group)
            self._ensure_group_title_handle(name)
            self._position_group_resize_handles(name)

        # Resynchroniser également la ligne de palette du cadre Photo principal
        # après restauration d'un état historique.
        primary_check = getattr(self, "_photo_frame_checks", {}).get("Photo")
        if primary_check is not None:
            primary_check.setText(self._group_display_title("Photo").strip() or "Photo")
            deleted = bool(self._group_styles.get("Photo", {}).get("frame_deleted"))
            blocker = primary_check.blockSignals(True)
            primary_check.setChecked(not deleted)
            primary_check.blockSignals(blocker)
        if "photo_data" in self._checks:
            deleted = bool(self._group_styles.get("Photo", {}).get("frame_deleted"))
            blocker = self._checks["photo_data"].blockSignals(True)
            self._checks["photo_data"].setChecked(not deleted)
            self._checks["photo_data"].blockSignals(blocker)

        self._refresh_group_styles()
        self._raise_absolute_fields()

    def _snapshot_state(self) -> dict:
        self._field_styles = self._normalized_field_styles(self._field_styles)
        return {
            # 11.7.57 — l'univers de la palette fait partie de l'état Undo/Redo.
            # Les champs créés par un import peuvent ainsi disparaître réellement
            # de la palette au Défaire puis revenir au Refaire.
            "field_keys": list(self._checks.keys()),
            "visible": {key: bool(check.isChecked()) for key, check in self._checks.items()},
            "labels": {key: edit.text() for key, edit in self._labels.items()},
            "blocks": {key: combo.currentText() for key, combo in self._blocks.items()},
            "positions": {key: int(spin.value()) for key, spin in self._positions.items()},
            "tab_positions": {
                key: int(spin.value()) for key, spin in self._tab_positions.items()
            },
            "visual_positions": {
                key: (int(pos[0]), int(pos[1])) for key, pos in self._visual_positions.items()
            },
            "visual_sizes": {
                key: (int(size[0]), int(size[1])) for key, size in self._visual_sizes.items()
            },
            "sheet_background": self._sheet_background,
            "field_masters": sorted(self._field_masters),
            "field_links": dict(self._field_links),
            "field_styles": self._normalized_field_styles(),
            "group_styles": {
                str(key): dict(value) for key, value in self._group_styles.items()
                if isinstance(value, dict)
            },
        }

    def _update_history_buttons(self) -> None:
        self.undo_btn.setEnabled(len(self._undo_stack) > 1)
        self.redo_btn.setEnabled(bool(self._redo_stack))

    def _record_history_state(self, *_args) -> None:
        if self._history_guard:
            return
        state = self._snapshot_state()
        if self._undo_stack and state == self._undo_stack[-1]:
            return
        self._undo_stack.append(state)
        # Une nouvelle modification invalide la branche Refaire.
        self._redo_stack.clear()
        self._update_history_buttons()

    def _apply_history_state(self, state: dict) -> None:
        self._history_guard = True
        self._updating_positions = True
        try:
            state_field_keys = set(str(k) for k in state.get("field_keys", self._checks.keys()))
            for key, row in self._rows.items():
                row.setVisible(str(key) in state_field_keys)
            for key, check in self._checks.items():
                # 11.7.57 — un champ créé après le snapshot n'existait pas dans
                # cet état. Lors d'un Défaire il doit donc être MASQUÉ, jamais
                # considéré visible par défaut. C'était la cause des champs
                # Sables tous réaffichés sur la fiche Fossiles après Défaire.
                check.setChecked(bool(state.get("visible", {}).get(key, False)))
            for key, edit in self._labels.items():
                if key in state.get("labels", {}):
                    edit.setText(str(state["labels"][key]))
            for key, combo in self._blocks.items():
                value = state.get("blocks", {}).get(key)
                if value and combo.findText(str(value)) >= 0:
                    combo.setCurrentText(str(value))
            for key, spin in self._positions.items():
                if key in state.get("positions", {}):
                    spin.setValue(int(state["positions"][key]))
            for key, spin in self._tab_positions.items():
                if key in state.get("tab_positions", {}):
                    spin.setValue(int(state["tab_positions"][key]))
            if "visual_positions" in state:
                self._visual_positions = {key:(int(value[0]),int(value[1])) for key,value in state["visual_positions"].items()}
            if "visual_sizes" in state:
                self._visual_sizes = {key:(int(value[0]),int(value[1])) for key,value in state["visual_sizes"].items()}
            if "sheet_background" in state:
                self._sheet_background = str(state["sheet_background"])
            if "field_masters" in state:
                self._field_masters = {str(k) for k in state["field_masters"]}
            if "field_links" in state:
                self._field_links = {str(k): str(v) for k, v in state["field_links"].items()}
            if "field_styles" in state:
                self._field_styles = self._normalized_field_styles(state["field_styles"])
            if "group_styles" in state:
                self._group_styles = {
                    str(key): dict(value) for key, value in state["group_styles"].items()
                    if isinstance(value, dict)
                }
        finally:
            self._updating_positions = False
            self._history_guard = False

        self._normalize_all_positions()
        self._rebuild_editor_groups_preserving_view()
        self._refresh_all_row_styles()
        self._refresh_preview()
        self._apply_sheet_background_preview()
        self._refresh_field_styles()
        self._refresh_group_styles()
        self._sync_graphical_frames_from_history()

        # 11.7.60 — Undo/Redo doit restaurer un instantané graphique complet,
        # pas seulement les valeurs du modèle. Après un rappel de bibliothèque,
        # les caches de géométrie et le repère absolu appartiennent au modèle
        # importé ; si on les laisse gouverner le retour historique, la fiche
        # précédente est reconstruite avec des bases étrangères et apparaît
        # « en vrac ». Le snapshot historique est donc réappliqué comme autorité
        # finale, exactement comme lors du chargement d'un .colmod.
        state_group_styles = state.get("group_styles") or {}
        layout_meta = (
            state_group_styles.get("__mm3_layout__", {})
            if isinstance(state_group_styles, dict) else {}
        )
        field_space = str(
            layout_meta.get("field_space", "")
            if isinstance(layout_meta, dict) else ""
        )

        # Les géométries par défaut appartiennent à l'état précédent de l'écran.
        # Les vider oblige _activate_free_group_layout() à repartir des géométries
        # explicitement mémorisées dans le snapshot restauré.
        self._free_group_default_geometries.clear()
        self._activate_free_group_layout()

        if field_space == "sheet_absolute_v1":
            self._stored_field_space = "sheet_absolute_v1"
            self._absolute_fields_ready = True
            self._visual_positions = {
                str(key): (int(value[0]), int(value[1]))
                for key, value in (state.get("visual_positions") or {}).items()
                if isinstance(value, (list, tuple)) and len(value) >= 2
            }
            self._visual_sizes = {
                str(key): (int(value[0]), int(value[1]))
                for key, value in (state.get("visual_sizes") or {}).items()
                if isinstance(value, (list, tuple)) and len(value) >= 2
            }
            self._refresh_preview_absolute()

        # Dernière passe autoritaire pour tous les cadres : positions et tailles
        # réellement capturées avant l'import. Elle rend Défaire symétrique du
        # chargement d'un modèle de bibliothèque.
        for group_name, group_style in (state_group_styles or {}).items():
            if group_name == "__mm3_layout__" or not isinstance(group_style, dict):
                continue
            geom = group_style.get("geometry") or {}
            if not (
                isinstance(geom, dict)
                and {"x", "y", "w", "h"} <= set(geom)
                and group_style.get("geometry_space") == "atelier_px"
            ):
                continue
            widget = self._free_group_widget(str(group_name))
            if widget is None:
                continue
            widget.setGeometry(
                int(geom["x"]), int(geom["y"]),
                max(1, int(geom["w"])), max(1, int(geom["h"])),
            )
            if bool(group_style.get("frame_deleted")):
                widget.hide()
            else:
                widget.show()
                widget.lower()

        if field_space == "sheet_absolute_v1":
            self._refresh_preview_absolute()
        self._position_all_group_resize_handles()

    def _undo(self) -> None:
        if len(self._undo_stack) <= 1:
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        QApplication.processEvents()
        try:
            current = self._undo_stack.pop()
            self._redo_stack.append(current)
            self._apply_history_state(self._undo_stack[-1])
            self._update_history_buttons()
            QApplication.processEvents()
        finally:
            QApplication.restoreOverrideCursor()

    def _redo(self) -> None:
        if not self._redo_stack:
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        QApplication.processEvents()
        try:
            state = self._redo_stack.pop()
            self._undo_stack.append(state)
            self._apply_history_state(state)
            self._update_history_buttons()
            QApplication.processEvents()
        finally:
            QApplication.restoreOverrideCursor()

    def _capture_preview_field_geometries(self) -> None:
        """Copie la géométrie réellement visible vers le modèle avant sauvegarde.

        C'est l'autorité absolue pour les champs fixes du Bandeau, notamment
        État de la fiche et N° de fiche : aucune ancienne position ne peut
        les ramener en arrière lors de la réouverture.
        """
        scale = max(0.01, float(self._preview_scale()))
        for key, field in self._preview_fields.items():
            if field is None or not field.isVisible():
                continue
            self._visual_positions[key] = (
                round(field.x() / scale),
                round(field.y() / scale),
            )
            self._visual_sizes[key] = (
                round(field.width() / scale),
                round(field.height() / scale),
            )

    def _capture_preview_group_geometries(self) -> None:
        """Fige dans le modèle la géométrie *visible* de tous les cadres.

        Une bibliothèque de modèles doit reproduire la fiche à l'identique,
        indépendamment de la collection qui la reçoit. On ne peut donc pas se
        contenter d'une ancienne géométrie éventuellement restée en base.
        """
        for name in tuple(getattr(self, "_free_group_names", ())):
            widget = self._free_group_widget(name)
            if widget is None or not widget.isVisible():
                continue
            geom = widget.geometry()
            style = dict(self._group_styles.get(name, {}))
            style["geometry_space"] = "atelier_px"
            style["geometry"] = {
                "x": int(geom.x()), "y": int(geom.y()),
                "w": int(geom.width()), "h": int(geom.height()),
            }
            self._group_styles[name] = style

    def _prepare_canvas_for_library_model(self, state: dict) -> None:
        """Retire les cadres graphiques propres au modèle destination.

        Un modèle de bibliothèque est un dessin complet, pas une fusion des
        cadres de deux collections. Les cadres personnalisés absents du modèle
        importé doivent donc disparaître avant application du nouvel état.
        """
        imported_styles = state.get("group_styles") or {}
        imported_custom = {
            str(name) for name, style in imported_styles.items()
            if isinstance(style, dict)
            and bool(style.get("custom_group") or style.get("custom_photo"))
        }
        current_styles = dict(getattr(self, "_group_styles", {}) or {})
        current_custom = {
            str(name) for name, style in current_styles.items()
            if isinstance(style, dict)
            and bool(style.get("custom_group") or style.get("custom_photo"))
        }
        for name in sorted(current_custom - imported_custom):
            group = self._preview_groups.pop(name, None)
            self._preview_canvases.pop(name, None)
            if group is not None:
                group.hide()
                group.deleteLater()
            frame = self._group_selection_frames.pop(name, None)
            if frame is not None:
                frame.hide(); frame.deleteLater()
            handle = self._group_title_handles.pop(name, None)
            if handle is not None:
                handle.hide(); handle.deleteLater()
            for resize_handle in self._free_group_resize_handles.pop(name, []):
                resize_handle.hide(); resize_handle.deleteLater()
        # Les géométries par défaut appartiennent à l'ancien modèle : elles ne
        # doivent jamais servir de référence au modèle de bibliothèque chargé.
        self._free_group_default_geometries.clear()

    def _choose_managed_record_template(self):
        """1.0.226 — rend les modèles personnels du nouvel Atelier accessibles depuis l'Atelier de la fiche."""
        try:
            from core.paths import WORKSPACE
            managed_root = Path(WORKSPACE) / "Bibliothèques" / "Atelier des modèles de fiches"
        except Exception:
            return None
        dlg = QDialog(self)
        dlg.setWindowTitle(self._t("Ouvrir un modèle"))
        dlg.resize(760, 520)
        lay = QVBoxLayout(dlg)
        note = QLabel(self._t("Choisissez un modèle de fiche officiel ou personnel. Le modèle source restera inchangé."))
        note.setWordWrap(True); lay.addWidget(note)
        tree = QTreeWidget(); tree.setHeaderLabels([self._t("Modèles de fiches")]); lay.addWidget(tree, 1)
        # Modèles personnels du gestionnaire : masquer les anciens doublons
        # « Modèle maître », sans toucher aux fichiers présents sur disque.
        def add_dir(parent, path):
            children = []
            for child in sorted(path.iterdir(), key=lambda x:(not x.is_dir(), x.name.casefold())):
                if child.is_dir():
                    children.append(child)
                elif child.suffix.lower() == ".db" and child.stem.casefold() != "modèle maître":
                    children.append(child)
            if not children:
                return
            item = QTreeWidgetItem(parent, ["📁 " + path.name])
            item.setData(0, Qt.ItemDataRole.UserRole, None)
            for child in children:
                if child.is_dir():
                    add_dir(item, child)
                else:
                    ci = QTreeWidgetItem(item, ["📄 " + child.stem])
                    ci.setData(0, Qt.ItemDataRole.UserRole, str(child))
        if managed_root.exists():
            for child in sorted(managed_root.iterdir(), key=lambda x:x.name.casefold()):
                if child.is_dir():
                    add_dir(tree, child)
        # 2.3.24.6.10 : mêmes modèles maîtres que dans leur gestionnaire.
        official_root = Path(__file__).resolve().parents[1] / "ModelesOfficiels"
        masters = (("Minéraux", "minerals.db"), ("Sables", "geology_samples.db"),
                   ("Fossiles", "fossils.db"), ("Timbres", "stamps.db"),
                   ("Cartes postales", "postcards.db"),
                   ("Monnaies - Médailles - Jetons", "coins.db"),
                   ("Objets de collection", "objects.db"),
                   ("Livres - Documents", "books.db"),
                   ("Étiquettes - Documents graphiques", "labels.db"),
                   ("Vierge", "blank.db"))
        for label, filename in masters:
            folder = QTreeWidgetItem(tree, ["📁 " + self._t(label)])
            folder.setData(0, Qt.ItemDataRole.UserRole, None)
            master_path = official_root / filename
            if master_path.is_file():
                leaf = QTreeWidgetItem(folder, ["📄 " + self._t("Modèle maître")])
                leaf.setData(0, Qt.ItemDataRole.UserRole, str(master_path))
                folder.setExpanded(True)
        # La bibliothèque historique .colmod reste accessible par le bouton
        # « Bibliothèque classique… », mais n'est plus dupliquée dans l'arbre.
        tree.expandToDepth(0)
        row=QHBoxLayout(); classic=QPushButton(self._t("Bibliothèque classique…")); row.addWidget(classic); row.addStretch(1)
        open_b=QPushButton(self._t("Ouvrir")); cancel_b=QPushButton(self._t("Annuler")); open_b.setEnabled(False)
        row.addWidget(open_b); row.addWidget(cancel_b); lay.addLayout(row)
        result={"path":None,"classic":False}
        tree.currentItemChanged.connect(lambda cur,*_: open_b.setEnabled(bool(cur and cur.data(0,Qt.ItemDataRole.UserRole))))
        open_b.clicked.connect(lambda: (result.__setitem__("path", tree.currentItem().data(0,Qt.ItemDataRole.UserRole)), dlg.accept()))
        tree.itemDoubleClicked.connect(lambda item,*_: (result.__setitem__("path", item.data(0,Qt.ItemDataRole.UserRole)), dlg.accept()) if item.data(0,Qt.ItemDataRole.UserRole) else None)
        classic.clicked.connect(lambda: (result.__setitem__("classic",True), dlg.accept()))
        cancel_b.clicked.connect(dlg.reject)
        if dlg.exec()!=QDialog.DialogCode.Accepted: return None
        if result["classic"]: return "__CLASSIC_LIBRARY__"
        return result["path"]

    def _managed_db_as_exchange_model(self, db_filename: Path) -> Path:
        """Convertit à la volée un modèle .db géré en modèle de Fiche échangeable, sans modifier la source."""
        con=sqlite3.connect(str(db_filename)); con.row_factory=sqlite3.Row
        try:
            row=con.execute("SELECT * FROM collections ORDER BY id LIMIT 1").fetchone()
            source_collection=dict(row) if row else None
        finally: con.close()
        if not source_collection: raise RuntimeError(self._t("Ce modèle ne contient aucune collection."))
        source=ModelDialog(db_filename, source_collection, None, language=self.language, workshop_mode="template")
        try:
            QApplication.processEvents()
            source._activate_free_group_layout()
            if getattr(source,"_absolute_field_mode",False) and not getattr(source,"_absolute_fields_ready",False): source._activate_absolute_field_plane()
            source._capture_preview_field_geometries(); source._capture_preview_group_geometries()
            payload=source._snapshot_state()
            keys=collect_model_field_keys("fiche",payload)
            payload=remap_model_payload("fiche",payload,{key:key for key in keys})
            manifest=build_field_manifest(source.manager,source.collection_id,keys)
            tmp=Path(tempfile.mkstemp(prefix="gskol_modele_",suffix=".colmod")[1])
            write_model(tmp,kind="fiche",name=db_filename.stem,source_collection=str(source_collection.get("name") or ""),payload=payload,field_manifest=manifest)
            return tmp
        finally:
            source.close(); source.deleteLater()

    def _open_model_from_library(self, filename=None) -> bool:
        # 11.7.70.26.68 — accepte aussi un modèle d’échange .colmod fourni
        # directement par le module Importation. Sans chemin explicite, le
        # comportement historique de la bibliothèque locale reste inchangé.
        temp_exchange = None
        if filename is None:
            managed = self._choose_managed_record_template() if self.workshop_mode == "collection" else "__CLASSIC_LIBRARY__"
            if managed == "__CLASSIC_LIBRARY__":
                root = library_root(workspace_root_from_database(self.db_path), "fiche")
                filename = choose_model_open_path(self, root, "Modèles de Fiches")
            else:
                filename = managed
        if not filename:
            return False
        filename = Path(filename)
        if filename.suffix.lower() == ".db":
            temp_exchange = self._managed_db_as_exchange_model(filename)
            display_model_name = filename.stem
            filename = temp_exchange
        else:
            display_model_name = filename.stem
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        QApplication.processEvents()
        try:
            # 11.7.58 — figer l'état graphique REEL de la fiche courante avant
            # de charger un modèle de bibliothèque. Sur les anciennes collections,
            # l'état initial Undo pouvait avoir été capturé avant les QTimer qui
            # terminent la migration vers le plan absolu. Défaire restaurait alors
            # les bons champs, mais avec des coordonnées intermédiaires : fiche en vrac.
            # Ici on force la fin du placement, on capture ce qui est réellement
            # affiché, puis on remplace le point de retour courant par ce snapshot.
            self._activate_free_group_layout()
            if getattr(self, "_absolute_field_mode", False) and not getattr(self, "_absolute_fields_ready", False):
                self._activate_absolute_field_plane()
            self._capture_preview_field_geometries()
            self._capture_preview_group_geometries()
            pre_library_state = deepcopy(self._snapshot_state())
            if self._undo_stack:
                self._undo_stack[-1] = deepcopy(pre_library_state)
            else:
                self._undo_stack = [deepcopy(pre_library_state)]
            # Si aucune modification n'avait encore eu lieu, ce snapshot visuel
            # est également la représentation exacte de l'état sauvegardé.
            if not self._model_has_unsaved_changes():
                self._saved_state = deepcopy(pre_library_state)

            envelope = read_model(filename, expected_kind="fiche")
            state = resolve_model_fields(self, envelope, self.manager, self.collection_id, "fiche")
            if state is None:
                return False
            # 11.7.70.26.17 — garantir les trois états système après tout import
            # de modèle, sans supprimer les états supplémentaires propres à la
            # collection. Une instance neuve évite qu'un cache déjà initialisé
            # considère à tort les valeurs par défaut comme encore présentes.
            try:
                from core.referential_manager import ReferentialManager
                ReferentialManager(self.db_path).ensure_defaults(self.collection_id)
            except Exception:
                pass
            # 11.7.63 — resolve_model_fields rend volontairement le curseur normal
            # pendant que la fenêtre de Correspondance est interactive, puis
            # restaure son propre sablier en sortie. Le chargement graphique du
            # modèle continue cependant ici et peut être sensiblement plus long
            # pour les fiches complexes. Remettre donc immédiatement le sablier
            # pour toute cette seconde phase, jusqu'au finally de cette méthode.
            # Le sablier a déjà été posé au début de cette méthode. Ne pas empiler
            # un second override : un seul restore en fin d'import laisserait sinon
            # le curseur d'attente actif en permanence.
            QApplication.changeOverrideCursor(Qt.CursorShape.WaitCursor)
            QApplication.processEvents()
            # 11.7.70.26.16 — l'application d'un modèle complexe peut durer plusieurs
            # secondes. Afficher une progression explicite plutôt qu'un simple sablier.
            progress = QProgressDialog("Préparation du modèle…", "", 0, 5, self)
            progress.setWindowTitle("Application du modèle de fiche")
            progress.setCancelButton(None); progress.setAutoClose(False); progress.setAutoReset(False)
            progress.setMinimumDuration(0); progress.setValue(0); progress.show(); QApplication.processEvents()
            # Si Correspondance a créé des champs, les ajouter immédiatement à
            # l'Atelier courant avant d'appliquer le modèle.
            # 11.7.70.26.21 — resolve_model_fields peut créer les champs via une
            # autre instance de ModelManager. L'instance de l'Atelier conserve alors
            # son ancien cache jusqu'à la fermeture/réouverture : c'était la vraie
            # cause de la palette incomplète après import. Invalider explicitement
            # ce cache AVANT la relecture.
            try:
                self.manager._invalidate_custom_fields_cache(self.collection_id)
            except Exception:
                pass
            QApplication.processEvents()
            fresh_custom = self.manager.custom_field_map(self.collection_id)
            # Toujours remettre les métadonnées métier réelles dans la palette.
            # Le modèle importé n’a aucune autorité sur les libellés des champs custom.
            for _key, _row in fresh_custom.items():
                self._custom_field_defs[str(_key)] = dict(_row)
            # 11.7.70.26.19 — resolve_model_fields peut déjà avoir rafraîchi le
            # dictionnaire métier. L'autorité visuelle est donc la palette (_checks),
            # pas _custom_field_defs : ajouter toute ligne réellement absente.
            new_keys = [k for k in fresh_custom if k not in self._checks]
            if new_keys:
                placement = self.manager.field_placement(self.collection_id)
                visible = self.manager.visible_fields(self.collection_id)
                labels = self.manager.custom_labels(self.collection_id)
                tab_order = self.manager.tab_order(self.collection_id, self._visual_order_from_placement(placement))
                tab_numbers = {k: i + 1 for i, k in enumerate(tab_order)}
                for key in new_keys:
                    self._custom_field_defs[key] = dict(fresh_custom[key])
                    self._add_custom_field_row(key, visible, labels, placement, tab_numbers)
                self._renumber_tab_order()
                self._rebuild_editor_groups_preserving_view()
                self._refresh_preview()
            progress.setLabelText("Mise à jour de la palette…"); progress.setValue(1); QApplication.processEvents()
            # Un modèle de bibliothèque est un modèle complet, pas une fusion
            # graphique avec la fiche actuellement ouverte. Les champs propres à
            # la collection courante mais absents du modèle restent disponibles
            # dans la palette, mais sont décochés pour éviter les superpositions.
            imported_visible = dict(state.get("visible") or {})
            for key in self._checks:
                imported_visible.setdefault(key, False)
            state["visible"] = imported_visible

            # 11.7.56 — le repère graphique du MODELE IMPORTE est l'autorité.
            # Certaines collections anciennes (notamment Fossiles / Minéraux)
            # peuvent encore être ouvertes depuis l'ancien repère local par blocs.
            # Sans ce basculement préalable, la migration réutilisait la géométrie
            # de la collection receveuse et écrasait les coordonnées du modèle.
            imported_group_styles = state.get("group_styles") or {}
            imported_layout_meta = (
                imported_group_styles.get("__mm3_layout__", {})
                if isinstance(imported_group_styles, dict) else {}
            )
            imported_field_space = str(
                imported_layout_meta.get("field_space", "")
                if isinstance(imported_layout_meta, dict) else ""
            )
            if imported_field_space == "sheet_absolute_v1":
                self._stored_field_space = "sheet_absolute_v1"
                # Le rafraîchissement absolu sait re-parenter chaque champ sur la
                # feuille. Le déclarer prêt ici empêche tout passage par la
                # conversion de la collection destinataire.
                self._absolute_fields_ready = True

            # Le modèle de bibliothèque remplace également la structure graphique
            # des cadres. Éliminer d'abord les cadres propres au modèle destination
            # afin d'éviter tout mélange visuel entre les deux fiches.
            progress.setLabelText("Application de la disposition graphique…"); progress.setValue(2); QApplication.processEvents()
            self._prepare_canvas_for_library_model(state)
            self._apply_history_state(deepcopy(state))
            progress.setLabelText("Restauration des propriétés et des liaisons…"); progress.setValue(3); QApplication.processEvents()

            # Réaffirmer les coordonnées brutes enregistrées APRÈS les rebuild de
            # palette/groupes effectués par _apply_history_state.
            if imported_field_space == "sheet_absolute_v1":
                self._visual_positions = {
                    str(key): (int(value[0]), int(value[1]))
                    for key, value in (state.get("visual_positions") or {}).items()
                    if isinstance(value, (list, tuple)) and len(value) >= 2
                }
                self._visual_sizes = {
                    str(key): (int(value[0]), int(value[1]))
                    for key, value in (state.get("visual_sizes") or {}).items()
                    if isinstance(value, (list, tuple)) and len(value) >= 2
                }
                self._group_styles = deepcopy(imported_group_styles)
                self._stored_field_space = "sheet_absolute_v1"
                self._absolute_fields_ready = True

            # 11.7.53 — Un modèle de Fiche de bibliothèque est un instantané
            # graphique complet. _prepare_canvas_for_library_model() efface
            # volontairement les géométries de référence de la collection
            # destinataire ; _apply_history_state() ne réactivait alors pas le
            # placement libre (car son ancien garde testait que ce cache était
            # non vide). Résultat : les cadres restaient sur la grille construite
            # pour Cantal au lieu de reprendre les coordonnées de Sables.
            # Réactiver explicitement le plan libre APRÈS restauration de
            # group_styles : les cadres standards, personnalisés et Photo sont
            # alors placés avec les géométries du fichier .colmod, sans aucune
            # référence à la collection receveuse.
            self._activate_free_group_layout()
            if getattr(self, "_absolute_field_mode", False):
                if not getattr(self, "_absolute_fields_ready", False):
                    self._activate_absolute_field_plane()
                else:
                    self._refresh_preview_absolute()
            self._refresh_group_styles()
            self._position_all_group_resize_handles()

            # 11.7.56 — dernière passe autoritaire : après tous les recalculs Qt,
            # remettre chaque cadre exactement à la géométrie enregistrée dans le
            # .colmod. La collection d'accueil ne fournit plus aucune position.
            for group_name, group_style in (self._group_styles or {}).items():
                if group_name == "__mm3_layout__" or not isinstance(group_style, dict):
                    continue
                geom = group_style.get("geometry") or {}
                if not (
                    isinstance(geom, dict)
                    and {"x", "y", "w", "h"} <= set(geom)
                    and group_style.get("geometry_space") == "atelier_px"
                ):
                    continue
                widget = self._free_group_widget(str(group_name))
                if widget is None:
                    continue
                widget.setGeometry(
                    int(geom["x"]), int(geom["y"]),
                    max(1, int(geom["w"])), max(1, int(geom["h"])),
                )
                if not bool(group_style.get("frame_deleted")):
                    widget.show()
                    widget.lower()

            if imported_field_space == "sheet_absolute_v1":
                self._refresh_preview_absolute()
            self._position_all_group_resize_handles()

            # Après un rappel inter-collections, des champs nouvellement créés et
            # des champs historiques peuvent avoir hérité du même numéro. On
            # reconstruit systématiquement une suite 1..N unique en conservant
            # autant que possible l'ordre demandé par le modèle importé.
            self._renumber_tab_order()
            # Forcer la reconstruction visuelle de la palette après l'application :
            # les champs « Créer » doivent y apparaître immédiatement, sans fermer
            # puis rouvrir l'Atelier.
            progress.setLabelText("Rafraîchissement de l'Atelier…"); progress.setValue(4); QApplication.processEvents()
            self._rebuild_editor_groups_preserving_view()
            self._refresh_preview()
            state = self._snapshot_state()
            self._undo_stack.append(deepcopy(state)); self._redo_stack.clear()
            self._active_library_model_name = display_model_name
            self._refresh_active_model_name()
            self._refresh_preview(); self._apply_sheet_background_preview(); self._update_history_buttons()
            progress.setLabelText("Terminé"); progress.setValue(5); QApplication.processEvents()
            progress.close()
        except Exception as exc:
            QMessageBox.critical(self, "Ouverture impossible", str(exc)); return False
        finally:
            try:
                if 'progress' in locals(): progress.close()
            except Exception:
                pass
            QApplication.restoreOverrideCursor()
            if temp_exchange is not None:
                try: Path(temp_exchange).unlink(missing_ok=True)
                except Exception: pass
        return True

    def _save_model_to_library(self) -> bool:
        self._capture_preview_field_geometries()
        self._capture_preview_group_geometries()
        root = library_root(workspace_root_from_database(self.db_path), "fiche")
        default_name = str(self.collection.get("name") or "Modèle de fiche")
        filename = choose_model_save_path(self, root, default_name, "Modèles de Fiches")
        if not filename:
            return False
        try:
            payload = self._snapshot_state()
            # 11.7.55 — nettoyer le modèle AVANT son stockage : seuls les champs
            # réellement cochés font partie de l'instantané. Les géométries et
            # styles d'anciens champs masqués ne doivent plus voyager dans la
            # bibliothèque ni contaminer une autre collection au rappel.
            saved_keys = collect_model_field_keys("fiche", payload)
            payload = remap_model_payload("fiche", payload, {key: key for key in saved_keys})
            manifest = build_field_manifest(self.manager, self.collection_id, saved_keys)
            write_model(
                filename, kind="fiche", name=Path(filename).stem,
                source_collection=str(self.collection.get("name") or ""),
                payload=payload, field_manifest=manifest,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Enregistrement impossible", str(exc))
            return False
        self._active_library_model_name = Path(filename).stem
        self._refresh_active_model_name()
        QMessageBox.information(self, "Modèle de Fiche", "Le modèle a été enregistré dans la bibliothèque Modèles de Fiches.")
        # La sauvegarde dans la bibliothèque constitue une décision explicite sur
        # l'état courant. On ne redemande donc pas immédiatement une seconde
        # confirmation à la fermeture. Toute modification ultérieure sera, elle,
        # de nouveau détectée.
        self._saved_state = deepcopy(self._snapshot_state())
        return True

    def _rollback_library_import_created_fields(self) -> None:
        """Supprime les champs créés provisoirement par un rappel de modèle.

        La fenêtre de correspondance doit pouvoir préparer la maquette sans
        modifier définitivement la collection. Tant que l'utilisateur n'a pas
        choisi « Enregistrer », les créations restent transactionnelles.
        """
        keys = list(getattr(self, "_library_import_created_keys", set()) or set())
        if not keys:
            return
        for key in reversed(keys):
            try:
                self.manager.delete_custom_field(self.collection_id, str(key))
            except Exception:
                # À la fermeture, poursuivre le rollback des autres champs ;
                # une éventuelle erreur résiduelle sera visible à la réouverture.
                pass
        self._library_import_created_keys.clear()

    def _apply_current_model_to_manager(self, manager) -> None:
        """Applique la maquette courante à un gestionnaire de modèle (aperçu temporaire)."""
        self._capture_preview_field_geometries()
        visible = {
            key for key, check in self._checks.items()
            if check.isChecked() and key not in getattr(self, "_pending_palette_placement", set())
        }
        visible.add("record_number")
        visible.add("record_state")
        manager.set_visible_fields(self.collection_id, visible)
        labels = {}
        for key, edit in self._labels.items():
            spec = self._field_spec(key)
            value = edit.text().strip()
            if spec is not None and value and value not in {str(spec.label), self._t(str(spec.label))}:
                labels[key] = value
        manager.set_custom_labels(self.collection_id, labels)
        manager.set_visual_positions(self.collection_id, self._visual_positions)
        manager.set_visual_sizes(self.collection_id, self._visual_sizes)
        manager.set_sheet_background(self.collection_id, self._sheet_background)
        manager.set_field_styles(self.collection_id, self._normalized_field_styles())
        manager.set_group_styles(self.collection_id, self._group_styles)
        manager.set_field_relations(self.collection_id, self._field_masters, self._field_links)
        ordered_tab = sorted(self._tab_positions, key=lambda key: (self._tab_positions[key].value(), key))
        manager.set_tab_order(self.collection_id, ordered_tab)

    def _preview_in_real_record(self) -> None:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Information)
        box.setWindowTitle("Aperçu temporaire dans la Fiche")
        box.setText("Tester ce modèle sur une copie temporaire de la collection ?")
        box.setInformativeText(
            "MM3 va créer une copie temporaire complète de cette collection.\n\n"
            "Vous pourrez utiliser normalement la Fiche et modifier ses données pour tester "
            "les champs calculés, les listes, les liaisons et les photos.\n\n"
            "La collection originale ne sera pas modifiée. Toutes les modifications réalisées "
            "pendant cet aperçu seront supprimées à sa fermeture."
        )
        go = box.addButton("Ouvrir l’aperçu", QMessageBox.ButtonRole.AcceptRole)
        cancel = box.addButton("Annuler", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(cancel)
        box.exec()
        if box.clickedButton() is not go:
            return
        tmp_dir = Path(tempfile.mkdtemp(prefix="mm3-apercu-modele-"))
        tmp_db = tmp_dir / "collection-apercu.db"
        try:
            # SQLite backup produit une image cohérente même si la collection est ouverte.
            src = sqlite3.connect(str(self.db_path))
            dst = sqlite3.connect(str(tmp_db))
            try:
                src.backup(dst)
            finally:
                dst.close(); src.close()
            temp_manager = ModelManager(tmp_db)
            self._apply_current_model_to_manager(temp_manager)
            parent = self.parent()
            if parent is None or not hasattr(parent, "_startup_for_database"):
                raise RuntimeError("Le contexte MM3 nécessaire à l’aperçu est indisponible.")
            runtime = parent._startup_for_database(tmp_db)
            from ui.record_window import RecordWindow
            preview_collection = dict(self.collection)
            preview_collection["name"] = str(self.collection.get("name") or "Collection")
            # L’Atelier est ouvert via QDialog.exec() : une fenêtre totalement
            # indépendante reste bloquée derrière sa modalité. En faire une fenêtre
            # enfant de l’Atelier la rend interactive tout en restant un vrai top-level.
            window = RecordWindow(runtime, preview_collection, self, preview_mode=True)
            window.setWindowFlag(Qt.WindowType.Window, True)
            window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
            window.setProperty("_mm3_independent_window", True)
            window._mm3_preview_temp_dir = str(tmp_dir)
            def cleanup_preview(*_args):
                try:
                    runtime.database.disconnect()
                except Exception:
                    pass
                shutil.rmtree(tmp_dir, ignore_errors=True)
            window.destroyed.connect(cleanup_preview)
            window.show()
            window.raise_()
            window.activateWindow()
            # Windows peut différer l’activation d’une fenêtre juste créée.
            QTimer.singleShot(0, lambda w=window: (w.raise_(), w.activateWindow(), w.setFocus()))
            QTimer.singleShot(120, lambda w=window: (w.raise_(), w.activateWindow()))
            # Conserver une référence Python jusqu'à la destruction Qt.
            self._temporary_preview_window = window
        except Exception as exc:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            QMessageBox.critical(self, "Aperçu impossible", str(exc))

    def _recovery_file(self) -> Path:
        # Chemin canonique + ID : deux collections homonymes ne se mélangent pas.
        identity = f"{self.db_path.resolve()}|{self.collection_id}"
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
        folder = Path(tempfile.gettempdir()) / "G-Skol" / "Atelier-Recuperation"
        return folder / f"atelier-{digest}.colmod"

    def _clear_recovery_snapshot(self) -> None:
        if self.workshop_mode != "collection":
            return
        try:
            self._recovery_file().unlink(missing_ok=True)
        except OSError:
            pass

    def _write_recovery_snapshot(self) -> None:
        if self.workshop_mode != "collection" or not self._model_has_unsaved_changes():
            return
        target = self._recovery_file()
        pending = target.with_suffix(".writing")
        try:
            self._capture_preview_field_geometries()
            self._capture_preview_group_geometries()
            state = self._snapshot_state()
            target.parent.mkdir(parents=True, exist_ok=True)
            # Réutilise le format de modèle existant ; écriture puis remplacement atomique.
            write_model(pending, kind="fiche", name="Récupération Atelier",
                        source_collection=str(self.collection.get("name") or ""),
                        payload=state)
            os.replace(pending, target)
        except Exception as exc:
            # Le diagnostic reste indépendant de la récupération.
            try:
                from datetime import datetime
                with (target.parent / "erreurs-recuperation.log").open("a", encoding="utf-8") as log:
                    log.write(f"{datetime.now().isoformat()} | {exc!r}\n")
            except Exception:
                pass
        finally:
            try:
                pending.unlink(missing_ok=True)
            except OSError:
                pass

    def _offer_recovery_snapshot(self) -> None:
        if self.workshop_mode != "collection":
            return
        target = self._recovery_file()
        if not target.is_file():
            return
        try:
            recovered = read_model(target, expected_kind="fiche").get("payload")
            if not isinstance(recovered, dict) or "visible" not in recovered:
                raise ValueError("État de récupération incomplet")
        except Exception:
            # Ne pas supprimer un fichier potentiellement récupérable.
            return
        choice = QMessageBox(self)
        choice.setIcon(QMessageBox.Icon.Question)
        choice.setWindowTitle("Récupération de l'Atelier")
        choice.setText("Une mise en forme non enregistrée a été retrouvée.")
        choice.setInformativeText("Voulez-vous retrouver votre travail interrompu ?")
        restore = choice.addButton("Récupérer", QMessageBox.ButtonRole.AcceptRole)
        ignore = choice.addButton("Ignorer", QMessageBox.ButtonRole.DestructiveRole)
        choice.addButton("Annuler", QMessageBox.ButtonRole.RejectRole)
        choice.setDefaultButton(restore)
        choice.exec()
        if choice.clickedButton() is restore:
            try:
                self._apply_history_state(recovered)
                self._record_history_state()
            except Exception as exc:
                QMessageBox.warning(self, "Récupération impossible", str(exc))
                return
            # Les champs ajoutés pendant la séance peuvent rester marqués
            # « en attente de dépôt » par la palette initialisée avant restauration.
            # Le snapshot possède pourtant leur position : rétablir leur dépôt.
            restored_positions = recovered.get("visual_positions") or {}
            restored_visible = recovered.get("visible") or {}
            for key in restored_positions:
                if restored_visible.get(key, False):
                    self._pending_palette_placement.discard(str(key))
            self._refresh_preview()
            # Garder la récupération jusqu'à un enregistrement explicite.
        elif choice.clickedButton() is ignore:
            self._clear_recovery_snapshot()

    def _persist_model(self) -> bool:
        # Sauvegarder d'abord ce que l'utilisateur voit réellement.
        self._capture_preview_field_geometries()
        # 23.7.0 — aucun recalcul de groupe/rang : seule la géométrie compte.
        visible = {
            key for key, check in self._checks.items()
            if check.isChecked() and key not in getattr(self, "_pending_palette_placement", set())
        }
        visible.add("record_number")
        visible.add("record_state")
        try:
            self.manager.set_visible_fields(self.collection_id, visible)

            labels = {}
            for key, edit in self._labels.items():
                spec = self._field_spec(key)
                value = edit.text().strip()
                if spec is not None and value and value != spec.label:
                    labels[key] = value
            self.manager.set_custom_labels(self.collection_id, labels)

            # L'ancienne appartenance aux blocs est laissée intacte en base
            # uniquement pour compatibilité avec les collections antérieures.
            self.manager.set_visual_positions(self.collection_id, self._visual_positions)
            self.manager.set_visual_sizes(self.collection_id, self._visual_sizes)
            self.manager.set_sheet_background(self.collection_id, self._sheet_background)
            self._field_styles = self._normalized_field_styles()
            self.manager.set_field_styles(self.collection_id, self._field_styles)
            self.manager.set_group_styles(self.collection_id, self._group_styles)
            self.manager.set_field_relations(
                self.collection_id, self._field_masters, self._field_links
            )

            ordered_tab = sorted(
                self._tab_positions,
                key=lambda key: (self._tab_positions[key].value(), key),
            )
            self.manager.set_tab_order(self.collection_id, ordered_tab)
        except Exception as exc:
            QMessageBox.critical(self, "Enregistrement impossible", str(exc))
            return False

        self._saved_state = self._snapshot_state()
        self._model_was_saved = True
        self._clear_recovery_snapshot()
        # Les champs créés par Correspondance sont maintenant validés.
        self._library_import_created_keys.clear()
        return True

    @property
    def model_was_saved(self) -> bool:
        """Vrai dès qu'une sauvegarde du modèle a réellement réussi."""
        return bool(getattr(self, "_model_was_saved", False))

    def _save(self) -> None:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Appliquer ce modèle à la collection ?")
        box.setText("Le modèle actuellement affiché deviendra le modèle utilisé par cette collection.")
        box.setInformativeText(
            "Cette opération modifiera durablement l’apparence de la collection.\n"
            "Les données des fiches existantes seront conservées."
        )
        apply_btn = box.addButton("Appliquer le modèle", QMessageBox.ButtonRole.AcceptRole)
        cancel_btn = box.addButton("Annuler", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(cancel_btn)
        box.exec()
        if box.clickedButton() is not apply_btn:
            return
        if self._persist_model():
            self._closing_after_choice = True
            self.accept()

    def _model_has_unsaved_changes(self) -> bool:
        return self._snapshot_state() != getattr(self, "_saved_state", {})

    def _confirm_close_with_unsaved_model(self) -> bool:
        if self._closing_after_choice:
            return True
        if not self._model_has_unsaved_changes():
            # Un Défaire peut avoir ramené exactement la maquette d'origine tout
            # en laissant en base des champs provisoires créés par Correspondance.
            # Dans ce cas aucun dialogue n'est utile : annuler silencieusement la
            # transaction avant de fermer.
            self._rollback_library_import_created_fields()
            return True

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle("Modèle modifié")
        box.setText("Le modèle a été modifié.")
        box.setInformativeText("Voulez-vous enregistrer les modifications avant de quitter ?")
        save_button = box.addButton("Enregistrer", QMessageBox.ButtonRole.AcceptRole)
        discard_button = box.addButton("Ne pas enregistrer", QMessageBox.ButtonRole.DestructiveRole)
        cancel_button = box.addButton("Annuler", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(save_button)
        box.exec()

        clicked = box.clickedButton()
        if clicked is save_button:
            if not self._persist_model():
                return False
            self._closing_after_choice = True
            return True
        if clicked is discard_button:
            # 11.7.57 — vrai « Ne pas enregistrer » : aucune création de champ
            # effectuée pendant la correspondance ne doit survivre dans la
            # palette de la collection après fermeture/réouverture.
            self._rollback_library_import_created_fields()
            self._clear_recovery_snapshot()
            self._closing_after_choice = True
            return True
        return False

    def reject(self) -> None:
        if self._confirm_close_with_unsaved_model():
            super().reject()

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._confirm_close_with_unsaved_model():
            event.accept()
        else:
            event.ignore()
