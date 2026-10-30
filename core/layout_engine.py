#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Moteur géométrique unique Atelier = Fiche.

Toutes les coordonnées de modèle sont logiques. Atelier compact et vraie Fiche
utilisent exactement la même transformation vers les pixels affichés.
"""

from __future__ import annotations
from PySide6.QtCore import QRect

DISPLAY_SCALE = 0.72
FIELD_LABEL_WIDTH = 118
FIELD_DATA_MIN_WIDTH = 72
FIELD_GAP = 0
GROUP_CONTENT_RESERVE = 6


def scaled(value: int | float, scale: float = DISPLAY_SCALE) -> int:
    return int(round(float(value) * float(scale)))


def field_outer_rect(x: int, y: int, w: int, h: int, scale: float = DISPLAY_SCALE) -> QRect:
    """Rectangle affiché d'un champ complet (libellé + donnée)."""
    return QRect(
        scaled(x, scale),
        scaled(y, scale),
        max(1, scaled(w, scale)),
        max(1, scaled(h, scale)),
    )


def field_parts(rect: QRect, scale: float = DISPLAY_SCALE) -> tuple[QRect, QRect]:
    """Découpe exactement le rectangle commun en Libellé + Donnée.

    Pour un champ étroit, la donnée conserve une petite largeur utile minimale.
    Atelier et vraie Fiche appliquent strictement la même règle.
    """
    gap = max(0, scaled(FIELD_GAP, scale))
    desired_label = max(1, scaled(FIELD_LABEL_WIDTH, scale))
    min_data = max(1, scaled(FIELD_DATA_MIN_WIDTH, scale))

    # Le libellé cède quelques pixels si nécessaire afin que la zone de donnée
    # ne soit jamais réduite à une fente inutilisable.
    available = max(1, rect.width() - gap)
    label_w = min(desired_label, max(1, available - min_data))
    data_x = rect.x() + label_w + gap
    data_w = max(1, rect.right() + 1 - data_x)

    label_rect = QRect(rect.x(), rect.y(), label_w, rect.height())
    data_rect = QRect(data_x, rect.y(), data_w, rect.height())
    return label_rect, data_rect
