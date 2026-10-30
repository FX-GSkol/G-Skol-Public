#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Surface visuelle unique de fiche MM3.

Atelier et vraie Fiche utilisent la même structure de blocs :
mêmes QGroupBox, mêmes marges, mêmes canvases, même Photo.
Seuls le contenu et les outils diffèrent selon le mode.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout, QGroupBox, QLabel, QSizePolicy, QVBoxLayout, QWidget
)

from core.layout_geometry import BLOCK_MIN_HEIGHT

BLOCK_NAMES = (
    "Bandeau", "Identification", "Localisation",
    "Aspect", "Acquisition", "Collection",
)

GROUP_STYLE = (
    "QGroupBox { font-weight:700; color:#496C5B; background:#FAFCFB; "
    "border:1px solid #C5D2CB; border-radius:8px; "
    "margin-top:0px; padding-top:12px; } "
    "QGroupBox::title { subcontrol-origin:padding; "
    "subcontrol-position:top left; left:6px; padding:0px 2px; }"
)


class FormSurface:
    """Construit UNE surface commune, réutilisable dans les deux modes."""

    def __init__(self, owner, canvas_factory) -> None:
        self.owner = owner
        self.widget = QWidget()
        self.grid = QGridLayout(self.widget)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(0)
        self.grid.setVerticalSpacing(0)
        self.grid.setColumnStretch(0, 4)
        self.grid.setColumnStretch(1, 4)
        self.grid.setColumnStretch(2, 3)

        self.groups = {}
        self.canvases = {}

        for block_name in BLOCK_NAMES:
            group = QGroupBox(block_name)
            group.setStyleSheet(GROUP_STYLE)
            box = QVBoxLayout(group)
            box.setContentsMargins(6, 10, 6, 6)
            box.setSpacing(0)

            canvas = canvas_factory(block_name, owner, group)
            canvas.setMinimumHeight(BLOCK_MIN_HEIGHT.get(block_name, 150))
            # 23.5.3 — quand un bloc est agrandi, son canvas doit grandir
            # avec lui : toute la nouvelle surface intérieure devient utilisable.
            canvas.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Expanding,
            )
            canvas.setMaximumSize(16777215, 16777215)
            box.addWidget(canvas, 1)

            self.groups[block_name] = group
            self.canvases[block_name] = canvas

        self.photo_group = QGroupBox("Photo")
        self.photo_group.setStyleSheet(GROUP_STYLE)
        photo_box = QVBoxLayout(self.photo_group)
        photo_box.setContentsMargins(0, 0, 0, 0)
        photo_box.setSpacing(0)

        self.photo_placeholder = QLabel("📷\nPhoto")
        self.photo_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.photo_placeholder.setMinimumSize(0, 0)
        self.photo_placeholder.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.photo_placeholder.setStyleSheet(
            "background:white; border:none; border-radius:0px; color:#718078;"
        )
        photo_box.addWidget(self.photo_placeholder)

        # Disposition initiale identique. Le moteur libre peut ensuite sortir
        # les mêmes objets de cette grille.
        self.grid.addWidget(self.groups["Bandeau"], 0, 0, 1, 3)
        self.grid.addWidget(self.groups["Identification"], 1, 0, 1, 2)
        self.grid.addWidget(self.photo_group, 1, 2, 1, 1)
        self.grid.addWidget(self.groups["Localisation"], 2, 0, 1, 3)
        self.grid.addWidget(self.groups["Aspect"], 3, 0, 1, 2)
        self.grid.addWidget(self.groups["Acquisition"], 3, 2, 1, 1)
        self.grid.addWidget(self.groups["Collection"], 4, 0, 1, 3)


def _title_css(style: dict) -> str:
    title = style.get("title", {}) if isinstance(style, dict) else {}
    parts = ["color:" + str(title.get("color", "#000000"))]
    family = str(title.get("family", "")).strip()
    if family:
        parts.append(f"font-family:'{family}'")
    size = int(title.get("size", 0) or 0)
    if size > 0:
        parts.append(f"font-size:{size}pt")
    parts.append("font-weight:700" if title.get("bold", True) else "font-weight:400")
    parts.append("font-style:italic" if title.get("italic", False) else "font-style:normal")
    parts.append("text-decoration:underline" if title.get("underline", False) else "text-decoration:none")
    return "; ".join(parts) + ";"


def apply_group_style(group: QGroupBox, style: dict, title: str) -> None:
    """Même style de groupe que l'Atelier, sans dépendre de la fenêtre."""
    style = dict(style or {})
    background = str(style.get("background", "#FAFCFB"))
    border = str(style.get("border", "#C5D2CB"))
    try:
        border_width = max(0, min(4, int(style.get("border_width", 1))))
    except Exception:
        border_width = 1
    group.setTitle(title)
    photo_frame = bool(style.get("photo_frame") or style.get("custom_photo"))
    padding = "padding:0px;" if photo_frame else "padding-top:12px;"
    group.setStyleSheet(
        "QGroupBox { "
        f"{_title_css(style)} background:{background}; "
        f"border:{border_width}px solid {border}; "
        f"border-radius:8px; margin-top:0px; {padding} }} "
        "QGroupBox::title { subcontrol-origin:padding; "
        "subcontrol-position:top left; left:2px; padding:0px; }"
    )


def detach_surface_groups(surface: FormSurface) -> dict[str, QGroupBox]:
    """Sort les blocs de la grille : leur géométrie devient 100 % absolue."""
    widgets = dict(surface.groups)
    widgets["Photo"] = surface.photo_group
    for widget in widgets.values():
        surface.grid.removeWidget(widget)
        widget.setParent(surface.widget)
        widget.show()
    return widgets


def canonical_group_rects(width: int = 800) -> dict[str, tuple[int, int, int, int]]:
    """Disposition compacte de secours, identique pour toute collection neuve.

    Elle n'est utilisée que lorsqu'aucune géométrie de bloc Atelier n'a encore
    été enregistrée pour la collection.
    """
    width = max(720, int(width))
    c1 = int(round(width * 4 / 11))
    c2 = int(round(width * 4 / 11))
    c3 = width - c1 - c2

    h_banner = 105
    h_ident = 145
    h_loc = 150
    h_aspect = 160
    h_collection = 95

    y0 = 0
    y1 = y0 + h_banner
    y2 = y1 + h_ident
    y3 = y2 + h_loc
    y4 = y3 + h_aspect

    return {
        "Bandeau":        (0,  y0, width,          h_banner),
        "Identification": (0,  y1, c1 + c2,        h_ident),
        "Photo":          (c1 + c2, y1, c3,        h_ident),
        "Localisation":   (0,  y2, width,           h_loc),
        "Aspect":         (0,  y3, c1 + c2,         h_aspect),
        "Acquisition":    (c1 + c2, y3, c3,         h_aspect),
        "Collection":     (0,  y4, width,           h_collection),
    }
