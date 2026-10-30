#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sélecteur de couleurs commun à MM3.

Toutes les fenêtres MM3 doivent passer par ce module afin de conserver la
même présentation, les mêmes couleurs personnalisées et, plus tard, la même
traduction.
"""
from PySide6.QtCore import QTimer
from PySide6.QtGui import QColor
import json
from pathlib import Path

from core.i18n import tr
from core.paths import WORKSPACE

from PySide6.QtWidgets import (
    QColorDialog, QDialog, QDialogButtonBox, QGridLayout, QHBoxLayout, QLabel,
    QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

_custom_color_used = None


def _dialog_language(parent) -> str:
    widget = parent
    while widget is not None:
        language = getattr(widget, "language", None)
        if language:
            return str(language)
        try:
            widget = widget.parentWidget()
        except Exception:
            break
    return "fr"


def make_color_dialog(parent, initial: QColor, title: str, palette_path: Path | None = None) -> QColorDialog:
    global _custom_color_used
    # Palette commune et persistante, même lorsque l’Atelier appelle
    # le sélecteur sans fournir explicitement de chemin.
    if palette_path is None:
        palette_path = Path(WORKSPACE) / "Paramètres" / "custom_colors.json"
    language = _dialog_language(parent)
    english = language.lower().startswith("en")
    dialog = QColorDialog(initial, parent)
    dialog.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog, True)
    dialog.setWindowTitle(title)
    translations = {} if english else {
        "Basic colors": "Couleurs de base", "Custom colors": "Couleurs personnalisées",
        "Pick Screen Color": "Choisir une couleur à l’écran",
        "Add to Custom Colors": "Ajouter aux couleurs personnalisées",
        "Hue:": "Teinte :", "Sat:": "Saturation :", "Val:": "Valeur :",
        "Red:": "Rouge :", "Green:": "Vert :", "Blue:": "Bleu :",
        "Alpha channel:": "Transparence :", "HTML:": "HTML :",
        "OK": "OK", "Cancel": "Annuler",
    }
    def t(text):
        return tr(text, language)
    def custom_count():
        fn = getattr(QColorDialog, "customCount", None)
        try: return max(1, int(fn())) if callable(fn) else 16
        except Exception: return 16
    # La palette personnalisée appartient à G-Skol, pas à une fenêtre Qt.
    # On la recharge avant chaque ouverture afin qu'elle survive aux redémarrages.
    if palette_path is not None:
        try:
            data = json.loads(Path(palette_path).read_text(encoding="utf-8"))
            colors = data.get("colors", []) if isinstance(data, dict) else []
        except (OSError, ValueError, TypeError):
            colors = []
        if isinstance(colors, list):
            for index in range(custom_count()):
                value = colors[index] if index < len(colors) else ""
                color = QColor(str(value)) if value else QColor("#ffffff")
                QColorDialog.setCustomColor(index, color if color.isValid() else QColor("#ffffff"))

    _custom_color_used = set()
    for index in range(custom_count()):
        try:
            color = QColorDialog.customColor(index)
            if color.isValid() and color.name().lower() != "#ffffff":
                _custom_color_used.add(index)
        except Exception:
            pass
    used = _custom_color_used

    def save_palette():
        if palette_path is None:
            return
        colors = []
        for index in range(custom_count()):
            try:
                color = QColorDialog.customColor(index)
                colors.append(color.name() if color.isValid() and color.name().lower() != "#ffffff" else "")
            except Exception:
                colors.append("")
        path = Path(palette_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"colors": colors}, ensure_ascii=False, indent=2), encoding="utf-8")
    def refresh():
        dialog.update()
        for child in dialog.findChildren(QWidget): child.update()
    def add_custom():
        chosen = dialog.currentColor()
        if not chosen.isValid(): return
        free = next((i for i in range(custom_count()) if i not in used), None)
        if free is None:
            QMessageBox.information(dialog, t("Couleurs personnalisées"), t("Le damier des couleurs personnalisées est complet.\n\nSupprimez d’abord une couleur du damier avant d’en ajouter une nouvelle."))
            return
        QColorDialog.setCustomColor(int(free), chosen); used.add(int(free)); save_palette(); refresh()
    def delete_custom():
        # Ne pas dépendre de currentColor(): selon la version de Qt, un clic
        # sur une case du damier personnalisé ne permet pas toujours de
        # retrouver de façon fiable la case d'origine.  On présente donc les
        # cases MM3 réellement mémorisées et l'utilisateur choisit directement
        # celle à libérer.
        slots = []
        for i in sorted(used):
            try:
                color = QColorDialog.customColor(i)
                if color.isValid() and color.name().lower() != "#ffffff":
                    slots.append((i, color))
            except Exception:
                pass
        if not slots:
            QMessageBox.information(dialog, t("Couleurs personnalisées"),
                                    t("Aucune couleur personnalisée n’est mémorisée."))
            return

        picker = QDialog(dialog)
        picker.setWindowTitle(t("Supprimer une couleur personnalisée"))
        outer = QVBoxLayout(picker)
        outer.addWidget(QLabel(t("Cliquez sur la couleur personnalisée à supprimer :")))
        grid = QGridLayout()
        outer.addLayout(grid)

        def remove_slot(index):
            QColorDialog.setCustomColor(int(index), QColor("#ffffff"))
            used.discard(int(index))
            save_palette()
            picker.accept()
            refresh()

        for n, (index, color) in enumerate(slots):
            button = QPushButton()
            button.setFixedSize(42, 30)
            button.setToolTip(color.name().upper())
            button.setStyleSheet(
                f"QPushButton {{ background-color: {color.name()}; "
                "border: 1px solid #68766f; border-radius: 4px; }} "
                "QPushButton:hover { border: 2px solid #24332b; }"
            )
            button.clicked.connect(lambda checked=False, i=index: remove_slot(i))
            grid.addWidget(button, n // 8, n % 8)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        cancel = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel:
            cancel.setText("Cancel" if english else "Annuler")
        buttons.rejected.connect(picker.reject)
        outer.addWidget(buttons)
        picker.exec()
    def install_controls():
        add_button = None
        for child in dialog.findChildren(QPushButton):
            raw = child.text().replace("&", "")
            if raw in ("Add to Custom Colors", "Ajouter aux couleurs personnalisées"):
                add_button = child; break
        if add_button is None: return
        if not bool(add_button.property("_mm3_custom_add_installed")):
            try: add_button.clicked.disconnect()
            except Exception: pass
            add_button.clicked.connect(add_custom); add_button.setProperty("_mm3_custom_add_installed", True)
        parent_widget = add_button.parentWidget(); layout = parent_widget.layout() if parent_widget else None
        if layout is not None and not bool(dialog.property("_mm3_delete_color_installed")):
            delete_button = QPushButton(t("Supprimer une couleur personnalisée"), parent_widget)
            delete_button.setToolTip(t("Sélectionnez une couleur dans le damier, puis cliquez ici pour libérer sa case."))
            delete_button.clicked.connect(delete_custom); index = layout.indexOf(add_button)
            if isinstance(layout, (QHBoxLayout, QVBoxLayout)): layout.insertWidget(max(0, index + 1), delete_button)
            elif isinstance(layout, QGridLayout) and index >= 0:
                row,col,rs,cs = layout.getItemPosition(index); layout.addWidget(delete_button, row+rs, col, 1, max(1,cs))
            else:
                try: layout.addWidget(delete_button)
                except Exception: delete_button.setParent(dialog); delete_button.show()
            dialog.setProperty("_mm3_delete_color_installed", True)
    def translate():
        for child in dialog.findChildren(QLabel):
            key = child.text().replace("&", "")
            if key in translations: child.setText(translations[key])
        for child in dialog.findChildren(QPushButton):
            key = child.text().replace("&", "")
            if key in translations: child.setText(translations[key])
        for box in dialog.findChildren(QDialogButtonBox):
            b=box.button(QDialogButtonBox.StandardButton.Cancel)
            if b: b.setText("Cancel" if english else "Annuler")
            b=box.button(QDialogButtonBox.StandardButton.Ok)
            if b: b.setText("OK")
        install_controls()
    translate(); QTimer.singleShot(0, translate)
    # Persiste aussi les changements du damier lors de la fermeture du dialogue.
    dialog.finished.connect(lambda _result: save_palette())
    return dialog


def choose_color(parent, initial: QColor, title: str = "Couleur du texte", palette_path: Path | None = None):
    dialog = make_color_dialog(parent, initial, title, palette_path)
    if dialog.exec() != QDialog.DialogCode.Accepted: return None
    color = dialog.selectedColor()
    return color if color.isValid() else None
