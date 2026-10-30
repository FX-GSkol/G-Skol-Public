from __future__ import annotations

from PySide6.QtCore import Qt
from core.i18n import tr

from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


MODELS = (
    (
        "blank",
        "Collection vierge",
        "Construire librement votre propre modèle de fiche.",
        True,
    ),
    (
        "minerals",
        "Minéraux / Microminéraux",
        "Espèces, cristallographie, localités, acquisition et photos.",
        True,
    ),
    (
        "fossils",
        "Fossiles",
        "Taxonomie, âge géologique, provenance, préparation et photos.",
        True,
    ),
    (
        "geology_samples",
        "Sables",
        "Site, localisation, identification du sable, acquisition et deux photos.",
        True,
    ),
    (
        "stamps",
        "Timbres",
        "Pays, émission, année, valeur, série, état et catalogue.",
        True,
    ),
    (
        "postcards",
        "Cartes postales",
        "Lieu, éditeur, période, état, acquisition, recto et verso.",
        True,
    ),
    (
        "coins",
        "Monnaies / Médailles / Jetons",
        "Pays, valeur, date, métal, dimensions, référence, avers et revers.",
        True,
    ),
    (
        "objects",
        "Objets de collection",
        "Porte-clés, pin’s, fèves, figurines, capsules et autres objets.",
        True,
    ),
    (
        "books",
        "Livres / Documents",
        "Titre, auteur, éditeur, année, édition, référence et état.",
        True,
    ),
    (
        "labels",
        "Étiquettes / Documents graphiques",
        "Catégorie, marque, origine, période, thème, dimensions et images.",
        True,
    ),
)


class CollectionModelSelectorDialog(QDialog):
    """Première étape de création : choisir le point de départ de la collection."""

    def __init__(self, parent=None, language: str = "fr"):
        super().__init__(parent)
        self.language = language or "fr"
        self.setWindowTitle(tr("Choisir un modèle de collection", self.language))
        self.resize(660, 700)
        self.setMinimumSize(560, 520)

        self._selected_key = "blank"
        self._buttons_by_key = {}
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)

        title = QLabel(tr("Quel type de collection souhaitez-vous créer ?", self.language))
        font = title.font()
        font.setPointSize(font.pointSize() + 3)
        font.setBold(True)
        title.setFont(font)
        root.addWidget(title)

        intro = QLabel(tr(
            "Choisissez le modèle le plus proche de votre besoin. Une fois la collection créée, tous ses champs, cadres et photos resteront librement personnalisables dans l’Atelier.",
            self.language
        ))
        intro.setWordWrap(True)
        intro.setStyleSheet("color:#607068;")
        root.addWidget(intro)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        host = QWidget()
        box = QVBoxLayout(host)
        box.setContentsMargins(2, 2, 6, 2)
        box.setSpacing(8)

        for index, (key, label, description, available) in enumerate(MODELS):
            card = QWidget()
            card.setObjectName("modelCard")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(12, 9, 12, 9)
            card_layout.setSpacing(3)

            radio = QRadioButton(tr(label, self.language))
            radio.setProperty("_mm3_model_key", key)
            radio.setEnabled(available)
            if key == "blank":
                radio.setChecked(True)
            self._group.addButton(radio, index)
            self._buttons_by_key[key] = radio
            card_layout.addWidget(radio)

            desc = QLabel(tr(description, self.language))
            desc.setWordWrap(True)
            desc.setStyleSheet(
                "color:#607068;" if available else "color:#9AA39E;"
            )
            card_layout.addWidget(desc)

            if not available:
                soon = QLabel(tr("Modèle prévu — disponible dans une prochaine étape", self.language))
                soon.setStyleSheet("color:#8A9690; font-style:italic;")
                card_layout.addWidget(soon)

            card.setStyleSheet(
                "#modelCard {"
                " background:#FFFFFF;"
                " border:1px solid #C5D2CB;"
                " border-radius:8px;"
                "}"
            )
            box.addWidget(card)

        box.addStretch(1)
        scroll.setWidget(host)
        root.addWidget(scroll, 1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.btn_next = QPushButton(tr("Suivant", self.language))
        self.btn_cancel = QPushButton(tr("Annuler", self.language))
        self.btn_next.setDefault(True)
        self.btn_next.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)
        buttons.addWidget(self.btn_next)
        buttons.addWidget(self.btn_cancel)
        root.addLayout(buttons)

        self._group.buttonClicked.connect(self._on_selection_changed)

    def _on_selection_changed(self, button) -> None:
        key = str(button.property("_mm3_model_key") or "blank")
        self._selected_key = key

    def selected_model_key(self) -> str:
        checked = self._group.checkedButton()
        if checked is None:
            return "blank"
        return str(checked.property("_mm3_model_key") or "blank")
