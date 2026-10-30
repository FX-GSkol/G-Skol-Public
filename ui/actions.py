#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from PySide6.QtWidgets import QMessageBox

def new_collection(parent):
    QMessageBox.information(
        parent,
        "Nouvelle collection",
        "Assistant de création de collection\n\n"
        "Cette fonction sera développée dans le LOT 7.\n"
        "Le noyau de MM3 est maintenant prêt."
    )
