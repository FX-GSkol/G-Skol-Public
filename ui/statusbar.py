#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from PySide6.QtWidgets import QStatusBar, QLabel
from core.i18n import tr


class MM3StatusBar(QStatusBar):
    def __init__(self, parent=None, language="fr"):
        super().__init__(parent)
        self.language = language or "fr"
        self.setMinimumHeight(26)

        self.space_label = QLabel(tr("Collection", self.language))
        self.space_label.setMinimumWidth(110)
        self.addWidget(self.space_label)

        self.state_label = QLabel(tr("Aucune collection ouverte", self.language))
        self.addWidget(self.state_label, 1)

        self.lang_label = QLabel("DE" if self.language.lower().startswith("de") else ("EN" if self.language.lower().startswith("en") else "FR"))
        self.addPermanentWidget(self.lang_label)


    def set_space(self, name: str) -> None:
        self.space_label.setText(tr(name, self.language))

    def set_collection(self, name: str | None) -> None:
        if name:
            self.state_label.setText(f"{tr('Collection', self.language)} : {name}")
        else:
            self.state_label.setText(tr("Aucune collection ouverte", self.language))

    def set_version(self, version: str) -> None:
        # La version reste interne à MM3 mais n'est plus affichée dans le bandeau.
        pass
