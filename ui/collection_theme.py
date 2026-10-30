# -*- coding: utf-8 -*-
"""Thème visuel dérivé de la couleur de Fiche d'une collection.

Le but est uniquement de fournir un repère visuel cohérent entre les fenêtres
MM3, sans modifier la couleur enregistrée du modèle de Fiche.
"""
from __future__ import annotations

from core.model_manager import ModelManager


def _hex_rgb(value: str, fallback: str = "#EEF5F1") -> tuple[int, int, int]:
    text = str(value or "").strip()
    if len(text) == 7 and text.startswith("#"):
        try:
            return tuple(int(text[i:i+2], 16) for i in (1, 3, 5))
        except ValueError:
            pass
    return _hex_rgb(fallback, "#EEF5F1") if value != fallback else (238, 245, 241)


def _mix(color: str, other: str, amount: float) -> str:
    """Mélange color vers other ; amount=0 garde color, amount=1 donne other."""
    c = _hex_rgb(color)
    o = _hex_rgb(other, "#FFFFFF")
    a = max(0.0, min(1.0, float(amount)))
    rgb = tuple(round(c[i] * (1.0 - a) + o[i] * a) for i in range(3))
    return "#%02X%02X%02X" % rgb


def collection_theme(database_path, collection: dict | None) -> dict[str, str]:
    base = "#EEF5F1"
    if collection is not None:
        try:
            base = ModelManager(database_path).sheet_background(
                int(collection["id"]), "#EEF5F1"
            )
        except Exception:
            base = "#EEF5F1"
    # Les teintes claires gardent la couleur propre de la Fiche tout en
    # préservant la lisibilité et le style doux/graduel historique de MM3.
    top = _mix(base, "#FFFFFF", 0.62)
    bottom = _mix(base, "#FFFFFF", 0.18)
    panel = _mix(base, "#FFFFFF", 0.82)
    panel2 = _mix(base, "#FFFFFF", 0.68)
    header = _mix(base, "#FFFFFF", 0.48)
    hover = _mix(base, "#FFFFFF", 0.60)
    border = _mix(base, "#66736C", 0.34)

    # L'Atelier doit être identifiable au premier coup d'œil par rapport à
    # l'espace Collection/Fiche : même teinte directrice, mais environ deux
    # nuances plus sombre, tout en conservant le dégradé MM3.
    workshop_base = _mix(base, "#4F5752", 0.40)
    workshop_top = _mix(workshop_base, "#FFFFFF", 0.40)
    workshop_bottom = _mix(workshop_base, "#FFFFFF", 0.02)
    workshop_panel = _mix(workshop_base, "#FFFFFF", 0.60)

    return {
        "base": base,
        "top": top,
        "bottom": bottom,
        "panel": panel,
        "panel2": panel2,
        "header": header,
        "hover": hover,
        "border": border,
        "gradient": (
            "qlineargradient(x1:0, y1:0, x2:0, y2:1, "
            f"stop:0 {top}, stop:1 {bottom})"
        ),
        "workshop_gradient": (
            "qlineargradient(x1:0, y1:0, x2:0, y2:1, "
            f"stop:0 {workshop_top}, stop:1 {workshop_bottom})"
        ),
        "workshop_panel": workshop_panel,
    }
