"""General preferences and current collection appearance."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QFileDialog, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QVBoxLayout, QFrame, QRadioButton,
    QButtonGroup,
)

from core.model_manager import ModelManager
from core.i18n import tr, translate_widget_tree
from ui.color_dialog import choose_color
from ui.collection_theme import collection_theme


class SettingsDialog(QDialog):
    def __init__(self, startup, db_path: Path | None, collection: dict | None, parent=None):
        super().__init__(parent)
        self.startup = startup
        self.language = getattr(startup.settings, "language", "fr") or "fr"
        self.setWindowTitle(tr("Paramètres de G-Skol", self.language))
        self.resize(680, 470)
        self.db_path = db_path
        self.collection = collection
        self.collection_color_changed = False
        self.selected_color = None
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 14)
        root.setSpacing(14)

        # Même langage graphique que l’écran des États : deux grands panneaux
        # arrondis, superposés, chacun avec son titre bien distinct.
        general_card = QFrame()
        general_card.setObjectName("settingsCard")
        general_lay = QVBoxLayout(general_card)
        general_lay.setContentsMargins(14, 12, 14, 14)
        general_lay.setSpacing(10)
        general_title = QLabel("Paramètres généraux — G-Skol")
        general_title.setObjectName("settingsCardTitle")
        general_lay.addWidget(general_title)

        self.restore_last = QCheckBox("Rouvrir la dernière collection au démarrage")
        self.restore_last.setChecked(startup.settings.restore_last_collection)
        general_lay.addWidget(self.restore_last)
        root.addWidget(general_card)

        collection_card = QFrame()
        collection_card.setObjectName("settingsCard")
        collection_lay = QVBoxLayout(collection_card)
        collection_lay.setContentsMargins(14, 12, 14, 14)
        collection_lay.setSpacing(10)
        collection_name = collection["name"] if collection is not None else tr("Aucune collection ouverte", self.language)
        collection_prefix = tr("Paramètres de la collection ouverte", self.language)
        collection_title = QLabel(f"{collection_prefix} — {collection_name}")
        collection_title.setObjectName("settingsCardTitle")
        collection_lay.addWidget(collection_title)

        if collection is None or db_path is None:
            collection_lay.addWidget(QLabel("Aucune collection ouverte. Ses réglages apparaîtront ici après ouverture."))
        else:
            collection_lay.addWidget(QLabel(f"Nom : {collection['name']}"))
            hint = QLabel("Le nom et le dossier se modifient depuis « Ouvrir une collection ».")
            hint.setObjectName("settingsHint")
            collection_lay.addWidget(hint)
            color_row = QHBoxLayout()
            color_row.addWidget(QLabel("Couleur de la fiche et de la collection :"))
            self.color_button = QPushButton("Choisir la couleur…")
            self.selected_color = ModelManager(db_path).sheet_background(int(collection["id"]))
            self._show_color()
            self.color_button.clicked.connect(self._choose_color)
            color_row.addWidget(self.color_button)
            color_row.addStretch(1)
            collection_lay.addLayout(color_row)

            prefs = ModelManager(db_path).collection_preferences(int(collection["id"]))

            opening_row = QHBoxLayout()
            opening_row.addWidget(QLabel("À l’ouverture de la Fiche :"))
            self.open_last = QRadioButton("Dernière fiche consultée")
            self.open_first = QRadioButton("Première fiche")
            self.opening_group = QButtonGroup(self)
            self.opening_group.addButton(self.open_last)
            self.opening_group.addButton(self.open_first)
            (self.open_first if prefs["record_opening"] == "first" else self.open_last).setChecked(True)
            opening_row.addWidget(self.open_last)
            opening_row.addWidget(self.open_first)
            opening_row.addStretch(1)
            collection_lay.addLayout(opening_row)

        root.addWidget(collection_card)

        root.addStretch(1)
        actions = QHBoxLayout()
        actions.addStretch(1)
        cancel = QPushButton("Annuler")
        cancel.clicked.connect(self.reject)
        actions.addWidget(cancel)
        save = QPushButton("Enregistrer")
        save.clicked.connect(self._save)
        actions.addWidget(save)
        root.addLayout(actions)

        # Reprise volontaire du style des cartes de l’écran États.
        theme = collection_theme(db_path, collection) if db_path is not None else {
            "panel": "#F8FAF9", "border": "#C9D2CD", "hover": "#EEF3F0"
        }
        translate_widget_tree(self, self.language)

        self.setStyleSheet(f"""
            QDialog {{ background:#E9EEEB; }}
            QFrame#settingsCard {{
                background:{theme['panel']};
                border:1px solid {theme['border']};
                border-radius:9px;
            }}
            QLabel#settingsCardTitle {{
                font-size:17px; font-weight:700; color:#496C5B;
                border:none; background:transparent;
            }}
            QLabel#settingsHint {{ color:#607068; border:none; background:transparent; }}
            QFrame#settingsCard QLabel, QFrame#settingsCard QCheckBox {{
                border:none; background:transparent;
            }}
            QPushButton {{
                padding:7px 12px; border:1px solid {theme['border']};
                border-radius:6px; background:white;
            }}
            QPushButton:hover {{ background:{theme['hover']}; }}
            QLineEdit {{
                background:white; border:1px solid {theme['border']};
                border-radius:5px; padding:5px;
            }}
        """)

    def _show_color(self):
        self.color_button.setStyleSheet(f"background-color: {self.selected_color};")

    def _choose_color(self):
        from PySide6.QtGui import QColor
        color = choose_color(
            self, QColor(self.selected_color), tr("Couleur de la collection", self.language),
            self.startup.workspace.settings_path / "custom_colors.json"
        )
        if color is not None and color.isValid():
            self.selected_color = color.name()
            self._show_color()

    def _save(self):
        settings = self.startup.settings
        settings.restore_last_collection = self.restore_last.isChecked()
        settings.save()
        if self.collection is not None and self.db_path is not None and self.selected_color:
            manager = ModelManager(self.db_path)
            current = manager.sheet_background(int(self.collection["id"]))
            if current != self.selected_color:
                manager.set_sheet_background(int(self.collection["id"]), self.selected_color)
                self.collection_color_changed = True
            manager.set_collection_preferences(
                int(self.collection["id"]),
                record_opening="first" if self.open_first.isChecked() else "last",
            )
        self.accept()
