#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from core.collection_folders import collection_display_name, CollectionFolderStore

from dataclasses import dataclass
import copy
import base64
import gc
from pathlib import Path
import sys
import ctypes
import weakref
import shutil

from PySide6.QtCore import QCoreApplication, QEvent, QTimer, Qt, QRectF, QPointF
from PySide6.QtGui import QColor, QPainter, QPolygonF, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QDialog,
    QDialogButtonBox,
    QComboBox,
    QLineEdit,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTreeWidget, QTreeWidgetItem, QInputDialog,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core.db_file_association import register_db_association
from core.collection_manager import CollectionManager
from core.record_manager import RecordManager
from core.model_manager import ModelManager
from core.collection_templates import (
    apply_minerals_template, apply_sands_template, apply_fossils_template, apply_stamps_template, apply_postcards_template, apply_coins_template, apply_objects_template, apply_books_template, apply_labels_template, apply_official_template_database, translate_created_native_collection,
    ensure_minerals_legacy_fields,
)
from core.database import DatabaseManager
from core.referential_manager import ReferentialManager
from core.field_catalog import REFERENTIAL_BY_FIELD
from core.version import APP_NAME, APP_VERSION, ABOUT_TAGLINE
from core.i18n import tr, canonical_native_value, display_native_value
from ui.new_collection_dialog import NewCollectionDialog
from ui.collection_model_selector_dialog import CollectionModelSelectorDialog
from ui.open_collection_dialog import OpenCollectionDialog
from ui.record_window import RecordWindow
from ui.search_window import SearchWindow
from ui.query_window import QueryWindow
from ui.table_window import TableWindow
from ui.report_window import ReportWindow
from ui.referential_dialog import ReferentialDialog
from ui.model_dialog import ModelDialog
from ui.toolbox_dialog import ToolboxDialog
from ui.import_export_dialog import ImportExportDialog
from ui.dashboard_dialog import DashboardDialog
from ui.settings_dialog import SettingsDialog
from ui.statusbar import MM3StatusBar
from ui.collection_theme import collection_theme


class _ImportExportIcon(QWidget):
    """Deux flèches épaisses fidèles à la maquette, dessinées sans glyphe/emoji."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(62, 54)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)

        # Flèche verte vers le haut.
        painter.setBrush(QColor("#07972A"))
        painter.drawRect(QRectF(12, 19, 9, 31))
        painter.drawPolygon(QPolygonF([QPointF(5, 21), QPointF(16.5, 4), QPointF(28, 21)]))

        # Flèche orange/rouge vers le bas.
        painter.setBrush(QColor("#FF5A18"))
        painter.drawRect(QRectF(41, 4, 9, 31))
        painter.drawPolygon(QPolygonF([QPointF(34, 33), QPointF(45.5, 50), QPointF(57, 33)]))



# Icône colorée de la Boîte à outils : clé à molette et tournevis croisés.
# PNG transparent embarqué pour fonctionner également en version portable.
_TOOLBOX_ICON_PNG = (
    "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"
)

@dataclass(frozen=True)
class Palette:
    collection_bg: str = "#EEF5F1"
    collection_panel: str = "#FFFFFF"
    workshop_bg: str = "#C9D8D0"
    workshop_panel: str = "#DEE8E3"
    accent: str = "#496C5B"
    accent_hover: str = "#3C5B4C"
    text: str = "#24332B"
    muted: str = "#607068"
    border: str = "#AABBB2"


class MainWindow(QMainWindow):
    # 017.2.0.3 — registre symétrique des fenêtres MM3 vivantes.
    # Il n'existe plus de notion permanente de « fenêtre principale » / « secondaire ».
    _mm3_windows: "weakref.WeakSet[MainWindow]" = weakref.WeakSet()

    def __init__(
        self,
        startup,
        restore_last_collection: bool = True,
        persist_last_collection: bool = True,
        catalog_startup=None,
    ) -> None:
        super().__init__()
        self.startup = startup
        # La base catalogue reste celle du Workspace principal, même lorsqu’une
        # fenêtre ouvre ponctuellement un fichier externe via « Parcourir… ».
        self.catalog_startup = catalog_startup or startup
        self.persist_last_collection = persist_last_collection
        self.palette_mm3 = Palette()
        self.language = getattr(self.catalog_startup.settings, "language", "fr") or "fr"
        self.collection: dict | None = None
        self.collection_name: str | None = None
        self.record_window: RecordWindow | None = None
        self.search_window: SearchWindow | None = None
        self.query_window: QueryWindow | None = None
        self.table_window: TableWindow | None = None
        self.report_window: ReportWindow | None = None
        self.referential_dialog: ReferentialDialog | None = None
        self.toolbox_window: ToolboxDialog | None = None
        self.import_export_window: ImportExportDialog | None = None

        # 017.0 — compatibilité avec les versions précédentes. La gestion réelle
        # des deux collections est désormais assurée par le registre symétrique
        # MainWindow._mm3_windows (017.2.0.3).
        self.secondary_collection_windows: list[MainWindow] = []
        self._second_collection_owner: MainWindow | None = None
        MainWindow._mm3_windows.add(self)

        # 017.1.1 — valeurs de référentiels introduites par Copier/Coller
        # de fiches. Elles sont proposées en une seule fois à la fermeture.
        self._pending_transferred_referentials: dict[str, set[str]] = {}
        self._transferred_record_ids: set[int] = set()

        self.setWindowTitle(APP_NAME)
        self.resize(1180, 760)
        self.setMinimumSize(940, 620)

        self._build_menu()
        self._build_center()
        self._build_statusbar()
        self._apply_style()
        if restore_last_collection and self.startup.settings.restore_last_collection:
            self._restore_last_collection()
        self.show_collection_space()

    def _build_menu(self) -> None:
        menu = self.menuBar()
        file_menu = menu.addMenu(self._t("Fichier"))
        file_menu.addAction(self._t("Créer une nouvelle collection…"), self.new_collection)
        file_menu.addAction(self._t("Ouvrir une collection…"), self.open_collection)
        self.save_as_file_action = file_menu.addAction(self._t("Enregistrer sous…"), self.save_collection_as)
        self.open_second_collection_file_action = file_menu.addAction(
            self._t("Ouvrir une 2e collection…"),
            self.open_second_collection,
        )
        file_menu.addSeparator()
        file_menu.addAction(self._t("Activer le double clic sur les fichiers .coldb…"), self.enable_db_double_click)
        file_menu.addSeparator()
        file_menu.addAction(self._t("Quitter"), self.close)

        menu.addMenu(self._t("Édition"))
        collection_menu = menu.addMenu(self._t("Collection"))
        collection_menu.addAction(self._t("Ouvrir les fiches…"), self.open_records)
        collection_menu.addAction(self._t("Recherche rapide…"), self.open_search)
        collection_menu.addAction(self._t("Requête multicritère…"), self.open_query)
        collection_menu.addAction(self._t("Vue Tableau…"), self.open_table)
        collection_menu.addAction(self._t("États…"), self.open_reports)
        collection_menu.addSeparator()
        collection_menu.addAction(self._t("Créer une nouvelle collection…"), self.new_collection)
        collection_menu.addAction(self._t("Ouvrir une collection…"), self.open_collection)
        self.open_second_collection_menu_action = collection_menu.addAction(
            self._t("Ouvrir une 2e collection…"),
            self.open_second_collection,
        )
        collection_menu.addAction(self._t("Fermer la collection"), self.close_collection)
        tools_menu = menu.addMenu(self._t("Outils"))
        tools_menu.addAction(self._t("Gérer les référentiels…"), self.open_referentials)
        tools_menu.addAction(self._t("Boîte à outils…"), self.open_toolbox)
        help_menu = menu.addMenu(self._t("Aide"))
        help_menu.addAction(self._t("À propos de G-Skol"), self.show_about)

    def _build_center(self) -> None:
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.navbar = QFrame()
        self.navbar.setObjectName("navbar")
        nav = QGridLayout(self.navbar)
        nav.setContentsMargins(18, 12, 18, 12)
        nav.setSpacing(10)

        self.btn_collection = QPushButton("📂  " + self._t("Collection"))
        self.btn_collection.setObjectName("spaceButton")
        self.btn_collection.clicked.connect(self.show_collection_space)

        self.btn_workshop = QPushButton("🛠  " + self._t("Atelier"))
        self.btn_workshop.setObjectName("spaceButton")
        self.btn_workshop.clicked.connect(self.show_workshop_space)

        self.btn_language = QPushButton("🌐  " + self._language_name())
        self.btn_language.setObjectName("languageButton")
        self.btn_language.setToolTip(self._t("Langue de l’interface"))
        self.btn_language.clicked.connect(self.choose_language)

        self.current_collection_label = QLabel(self._t("Aucune collection ouverte"))
        self.current_collection_label.setObjectName("collectionName")

        left_buttons = QWidget()
        left_layout = QHBoxLayout(left_buttons)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)
        left_layout.addWidget(self.btn_collection)
        left_layout.addWidget(self.btn_workshop)
        left_layout.addStretch(1)
        nav.addWidget(left_buttons, 0, 0)
        nav.addWidget(self.btn_language, 0, 1, Qt.AlignmentFlag.AlignCenter)
        nav.addWidget(self.current_collection_label, 0, 2, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        nav.setColumnStretch(0, 1)
        nav.setColumnStretch(1, 1)
        nav.setColumnStretch(2, 1)

        self.stack = QStackedWidget()
        self.collection_page = self._build_collection_page()
        self.workshop_page = self._build_workshop_page()
        self.stack.addWidget(self.collection_page)
        self.stack.addWidget(self.workshop_page)

        root_layout.addWidget(self.navbar)
        root_layout.addWidget(self.stack, 1)
        self.setCentralWidget(root)

    def _build_collection_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("collectionPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 20, 32, 20)
        layout.setSpacing(12)

        self.collection_page_title = QLabel(self._t("Collection"))
        self.collection_page_title.setObjectName("pageTitle")
        subtitle = QLabel(
            self._t("L’espace quotidien pour saisir, consulter, rechercher et exploiter votre collection.")
        )
        subtitle.setWordWrap(True)
        subtitle.setObjectName("pageSubtitle")
        layout.addWidget(self.collection_page_title)
        layout.addWidget(subtitle)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(12)
        grid.addWidget(self._card("Fiches", "Créer, ouvrir et parcourir les fiches.", self.open_records), 0, 0)
        grid.addWidget(self._card("Requêtes", "Construire une requête avec un ou plusieurs critères.", self.open_query), 0, 1)
        grid.addWidget(self._card("États", "Créer, consulter et imprimer des états.", self.open_reports), 1, 0)
        grid.addWidget(self._card("Statistiques rapides", "Répartir les fiches par champ et choisir un graphique.", self.open_statistics), 1, 1)
        grid.addWidget(self._card("Vue Tableau", "Afficher les fiches en lignes et choisir librement les colonnes.", self.open_table), 2, 0, 1, 2)
        grid.addWidget(self._card("Boîte à outils", "Effectuer volontairement des opérations globales de maintenance sur la collection.", self.open_toolbox), 3, 0)
        grid.addWidget(self._card("Import / Export / Sauvegarde-Restauration", "<b>Importation : aucune collection à ouvrir au préalable.</b><br>Importer &nbsp;&nbsp;•&nbsp;&nbsp; Exporter &nbsp;&nbsp;•&nbsp;&nbsp; Sauvegarder / Restaurer.", self.open_import_export), 3, 1)
        layout.addLayout(grid)

        # Bandeau inférieur dédié : les boutons sont centrés verticalement
        # pour être mieux distingués des cartes situées juste au-dessus.
        actions_band = QWidget()
        actions_band.setObjectName("collectionActionsBand")
        actions_band.setFixedHeight(62)
        actions = QHBoxLayout(actions_band)
        actions.setContentsMargins(0, 10, 0, 8)
        actions.setSpacing(12)

        self.close_collection_btn = QPushButton(self._t("Fermer la collection"))
        self.close_collection_btn.clicked.connect(self.close_collection)
        self.new_collection_btn = QPushButton(self._t("Créer une nouvelle collection"))
        self.new_collection_btn.clicked.connect(self.new_collection)
        open_btn = QPushButton(self._t("Ouvrir une collection"))
        open_btn.clicked.connect(self.open_collection)
        self.open_second_collection_btn = QPushButton(self._t("Ouvrir une 2e collection"))
        self.open_second_collection_btn.clicked.connect(self.open_second_collection)
        # Création à gauche ; les deux commandes d'ouverture restent regroupées à droite.
        actions.addWidget(self.new_collection_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        actions.addWidget(self.close_collection_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        actions.addStretch(1)
        actions.addWidget(open_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        actions.addWidget(self.open_second_collection_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        self._update_collection_action_buttons()
        layout.addWidget(actions_band)
        return page

    def open_toolbox(self, _feature_name: str | None = None) -> None:
        """Ouvre la boîte à outils sans bloquer les autres fenêtres MM3."""
        if self.collection is None:
            QMessageBox.information(
                self,
                self._t("Boîte à outils"),
                self._t("Ouvrez ou créez d’abord une collection avant d’utiliser la Boîte à outils."),
            )
            return

        # Fenêtre volontairement NON modale : l'utilisateur peut revenir à la
        # Fiche, copier un libellé ou vérifier une donnée, puis reprendre l'outil.
        if self.toolbox_window is None:
            dialog = ToolboxDialog(
                self._database_path,
                int(self.collection["id"]),
                collection_display_name(self.collection),
                self,
                self.language,
            )
            dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
            dialog.setWindowModality(Qt.WindowModality.NonModal)
            dialog.dataChanged.connect(self._refresh_after_toolbox_change)
            dialog.collectionDuplicated.connect(self._after_toolbox_duplicate)
            dialog.collectionEmptied.connect(self._after_toolbox_empty)
            dialog.destroyed.connect(lambda *_: setattr(self, "toolbox_window", None))
            self.toolbox_window = dialog
            dialog.show()
        self._bring_window_to_front(self.toolbox_window)

    def _after_toolbox_duplicate(self, _database_path: str) -> None:
        # La nouvelle base autonome sera automatiquement proposée par « Ouvrir une collection ».
        self.statusBar().showMessage("Collection sœur créée", 4000)

    def _after_toolbox_empty(self) -> None:
        # Ferme les vues qui pourraient encore conserver des identifiants de fiches supprimées.
        self.record_window = self._safe_close_qt_window(self.record_window)
        self.search_window = self._safe_close_qt_window(self.search_window)
        self.query_window = self._safe_close_qt_window(self.query_window)
        self.table_window = self._safe_close_qt_window(self.table_window)
        self.statusBar().showMessage("Collection entièrement vidée — prochaine fiche : N° 1", 5000)

    def _refresh_after_record_change(self, record_id: int | None = None) -> None:
        """Synchronise les vues après une modification ponctuelle d'une fiche.

        Utilisé dans les deux sens : Fiche -> Tableau et Tableau -> Fiche.
        """
        try:
            if self.table_window is not None and self.table_window.isVisible():
                self.table_window.refresh_table()
        except RuntimeError:
            self.table_window = None
        except Exception:
            pass

        try:
            record_window = self._live_record_window()
            if record_window is not None:
                refresh = getattr(record_window, "refresh_after_external_data_change", None)
                if callable(refresh):
                    refresh()
        except Exception:
            pass

        try:
            if self.search_window is not None and self.search_window.isVisible():
                self.search_window.refresh_results()
        except RuntimeError:
            self.search_window = None
        except Exception:
            pass

    def _refresh_after_toolbox_change(self) -> None:
        """Répercute immédiatement une modification globale dans les vues ouvertes."""
        record_window = self._live_record_window()
        # 11.7.70.26.52 — rafraîchir aussi une Fiche déjà créée mais
        # momentanément masquée. Sinon la Boîte à outils modifie bien SQLite,
        # mais la réouverture de cette même fenêtre peut encore présenter son
        # ancien cache jusqu'à une fermeture/réouverture supplémentaire.
        if record_window is not None:
            refresh = getattr(record_window, "refresh_after_external_data_change", None)
            if callable(refresh):
                refresh()

        # Même logique pour les autres vues susceptibles d'être déjà à l'écran.
        try:
            if self.table_window is not None and self.table_window.isVisible():
                self.table_window.refresh_table()
        except RuntimeError:
            self.table_window = None
        except Exception:
            pass

        try:
            if self.search_window is not None and self.search_window.isVisible():
                self.search_window.refresh_results()
        except RuntimeError:
            self.search_window = None
        except Exception:
            pass

    def open_import_export(self, _feature_name: str | None = None) -> None:
        """Ouvre Import / Export, indépendamment de toute collection active."""
        if self.import_export_window is None:
            dialog = ImportExportDialog(self, self.language)
            dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
            dialog.setWindowModality(Qt.WindowModality.NonModal)
            dialog.destroyed.connect(
                lambda *_: setattr(self, "import_export_window", None)
            )
            self.import_export_window = dialog
            dialog.show()

        self._bring_window_to_front(self.import_export_window)

    def _build_workshop_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("workshopPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 26, 32, 30)
        layout.setSpacing(18)

        self.workshop_page_title = QLabel(self._t("Atelier"))
        self.workshop_page_title.setObjectName("pageTitle")
        subtitle = QLabel(self._t("L’espace de préparation et de personnalisation. Les réglages effectués ici seront réutilisés ensuite dans Collection."))
        subtitle.setWordWrap(True)
        subtitle.setObjectName("pageSubtitle")
        layout.addWidget(self.workshop_page_title)
        layout.addWidget(subtitle)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(16)
        grid.addWidget(self._card("Modèles de fiches", "Préparer les modèles de fiches.", self.open_models), 0, 0)
        grid.addWidget(self._card("Référentiels", "Gérer les listes et leurs valeurs.", self.open_referentials), 0, 1)
        grid.addWidget(
            self._card(
                "Éditeur d’états",
                "Personnaliser finement la structure, la présentation et les bandeaux des états.",
                self.open_report_editor,
            ),
            1, 0
        )
        grid.addWidget(self._card("Paramètres", "Adapter G-Skol à votre manière de travailler.", self.open_settings), 1, 1)
        layout.addLayout(grid)
        layout.addStretch(1)
        return page

    def _card(self, title: str, description: str, callback) -> QFrame:
        """Carte d'accueil compacte : contenu à gauche, action à droite.

        11.4.39.8 — cette disposition remplace l'ancien bouton placé dans un
        bandeau inférieur, qui pouvait recouvrir la deuxième ligne de texte.
        """
        frame = QFrame()
        frame.setObjectName("featureCard")
        frame.setMinimumHeight(118)

        row = QHBoxLayout(frame)
        row.setContentsMargins(20, 14, 20, 14)
        row.setSpacing(14)

        icons = {
            "Fiches": "📄",
            "Requêtes": "🔎",
            "États": "🖨",
            "Statistiques rapides": "📊",
            "Vue Tableau": "📋",
            "Boîte à outils": "⚙",
            "Import / Export / Sauvegarde-Restauration": "↕",
            "Modèles de fiches": "▤",
            "Référentiels": "≡",
            "Éditeur d’états": "✎",
            "Tableaux de bord": "▥",
            "Paramètres": "⚙",
        }
        # Icônes : privilégier des glyphes bien rendus sous Windows.
        # Les deux anciens caractères de tableau/statistiques étaient presque
        # invisibles avec certaines polices système.
        if title == "Vue Tableau":
            # Pictogramme robuste sous Windows : l'ancien glyphe de grille
            # apparaissait minuscule selon la police système.
            icon_text = "📋"
        elif title == "Statistiques rapides":
            icon_text = "📊"
        else:
            icon_text = icons.get(title, "")
        if title == "Boîte à outils":
            icon = QLabel()
            icon.setObjectName("toolboxCardIcon")
            icon.setFixedWidth(48)
            icon.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
            pixmap = QPixmap()
            pixmap.loadFromData(base64.b64decode(_TOOLBOX_ICON_PNG))
            icon.setPixmap(pixmap.scaled(42, 42,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))
            row.addWidget(icon, 0)
        elif title == "Import / Export / Sauvegarde-Restauration":
            # Icône fidèle à la maquette : deux grandes flèches texte, côte à côte,
            # sans fond ni carré emoji (on évite volontairement les glyphes ⬆/⬇
            # que Windows peut remplacer par des pictogrammes bleus).
            icon = _ImportExportIcon()
            row.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)
        else:
            icon = QLabel(icon_text)
            icon.setObjectName("cardIcon")
            icon.setFixedWidth(48)
            icon.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
            row.addWidget(icon, 0)

        text_box = QVBoxLayout()
        text_box.setContentsMargins(0, 0, 0, 0)
        text_box.setSpacing(5)
        label = QLabel(self._t(title))
        label.setObjectName("cardTitle")
        desc = QLabel(self._t(description))
        desc.setWordWrap(True)
        desc.setObjectName("cardDescription")
        desc.setTextFormat(Qt.TextFormat.RichText if "<" in description else Qt.TextFormat.PlainText)
        text_box.addWidget(label)
        text_box.addWidget(desc)
        text_box.addStretch(1)
        row.addLayout(text_box, 1)

        button = QPushButton(self._t("Ouvrir"))
        button.setFixedWidth(125)
        button.clicked.connect(lambda: callback(title))
        row.addWidget(button, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return frame

    def _build_statusbar(self) -> None:
        status = MM3StatusBar(self, self.language)
        status.set_version(APP_VERSION)
        self.setStatusBar(status)
        self.mm3_statusbar = status

    def _apply_style(self) -> None:
        p = self.palette_mm3
        theme = collection_theme(self._database_path, self.collection)
        page_bg = theme["gradient"] if self.collection is not None else p.collection_bg
        workshop_bg = theme["workshop_gradient"] if self.collection is not None else p.workshop_bg
        panel = theme["panel"] if self.collection is not None else p.collection_panel
        workshop_panel = theme["workshop_panel"] if self.collection is not None else p.workshop_panel
        nav_bg = theme["top"] if self.collection is not None else "#F7F8F7"
        hover = theme["hover"] if self.collection is not None else "#E8F0EC"
        header = theme["header"] if self.collection is not None else "#DDE8E2"
        border = theme["border"] if self.collection is not None else p.border
        self.setStyleSheet(
            f"""
            QMainWindow {{ color: {p.text}; }}
            QMenuBar {{ background: {nav_bg}; padding: 4px; }}
            QMenuBar::item:selected {{ background: {header}; }}
            QMenu {{ background: white; color: {p.text}; }}
            QMenu::item:selected {{ background: {header}; color: {p.text}; }}
            #navbar {{ background: {nav_bg}; border-bottom: 1px solid {border}; }}
            #collectionPage {{ background: {page_bg}; }}
            #workshopPage {{ background: {workshop_bg}; }}
            #pageTitle {{ font-size: 28px; font-weight: 700; color: {p.text}; }}
            #pageSubtitle {{ font-size: 15px; color: {p.muted}; }}
            #collectionName {{ font-size: 14px; color: {p.muted}; padding: 6px 10px; font-weight: 650; }}
            #featureCard {{ background: {panel}; border: 1px solid {border}; border-radius: 10px; }}
            #workshopPage #featureCard {{ background: {workshop_panel}; }}
            #cardIcon {{ font-size: 30px; font-weight: 700; color: {p.accent}; padding-top: 2px; }}
            #cardTitle {{ font-size: 19px; font-weight: 650; color: {p.text}; }}
            #cardDescription {{ font-size: 14px; color: {p.muted}; }}
            QPushButton {{
                background: #FFFFFF; color: {p.text}; border: 1px solid {border};
                border-radius: 7px; padding: 8px 14px; min-height: 22px;
            }}
            QPushButton:hover {{ background: {hover}; }}
            QPushButton:disabled {{
                background: #E6E9E7;
                color: #9AA39E;
                border-color: #C6CDC9;
            }}
            #primaryButton {{ background: {p.accent}; color: white; border-color: {p.accent}; }}
            #primaryButton:hover {{ background: {p.accent_hover}; }}
            #spaceButton {{ font-size: 15px; font-weight: 600; padding: 9px 16px; }}
            #spaceButton[active="true"] {{ background: {p.accent}; color: white; border-color: {p.accent}; }}
            #languageButton {{ font-size: 13px; font-weight: 500; padding: 6px 12px; color: {p.muted}; border-color: {border}; }}
            #languageButton:hover {{ color: {p.text}; border-color: {p.muted}; }}
            QStatusBar {{ background: {nav_bg}; border-top: 1px solid {border}; min-height: 26px; }}
            QStatusBar QLabel {{ padding: 2px 6px; color: {p.text}; }}
            QStatusBar::item {{ border: none; }}
            """
        )

    def _restore_last_collection(self) -> None:
        """Rouvre la dernière collection réellement active à la fermeture précédente.

        Le chemin mémorisé reste prioritaire. S'il est devenu caduc (déplacement du
        dossier G-Skol, nouvelle brique/Core, etc.), on recherche la même collection
        dans le dossier Collections au lieu d'effacer immédiatement la mémoire.
        """
        settings = self.catalog_startup.settings
        last_path = settings.last_collection_path.strip()
        last_id = settings.last_collection_id
        last_name = settings.last_collection.strip()

        candidates: list[Path] = []
        if last_path:
            candidates.append(Path(last_path).expanduser())

        # Secours : le chemin absolu peut changer entre deux installations/empilements.
        try:
            collections_root = CollectionManager(self._catalog_database_path).collections_folder()
            for candidate in Path(collections_root).rglob("*.coldb"):
                if candidate not in candidates:
                    candidates.append(candidate)
        except Exception:
            pass

        for path in candidates:
            if not path.is_file():
                continue
            try:
                manager = CollectionManager(path)
                collection = manager.get_collection_by_id(last_id) if last_id else None
                if collection is not None and last_name and str(collection.get("name") or "") != last_name:
                    collection = None
                if collection is None and last_name:
                    collection = manager.get_collection_by_name(last_name)
                if collection is None:
                    found = manager.inspect_collections()
                    if len(found) == 1 and (not last_name or str(found[0].get("name") or "") == last_name):
                        collection = found[0]
                if collection is None:
                    continue

                self._prepare_database_switch(path)
                self._use_database(path)
                self._activate_collection(dict(collection))
                return
            except Exception as exc:
                self.startup.logger.error(
                    f"Impossible de restaurer la dernière collection depuis {path} : {exc}"
                )

        # Ne pas détruire la préférence : elle pourra redevenir valable si le
        # support/dossier revient. On démarre simplement sans collection.
        try:
            self._use_database(self._catalog_database_path)
        except Exception:
            pass

    @classmethod
    def _live_mm3_windows(cls) -> list["MainWindow"]:
        """Retourne les fenêtres MM3 encore utilisables.

        Le WeakSet évite qu'une ancienne fenêtre fermée conserve artificiellement
        le verrou « deux collections ouvertes ». Les wrappers Qt déjà détruits
        sont écartés par précaution.
        """
        live: list[MainWindow] = []
        for window in list(cls._mm3_windows):
            try:
                window.isVisible()
            except RuntimeError:
                cls._mm3_windows.discard(window)
                continue
            live.append(window)
        return live

    @classmethod
    def _active_collection_windows(cls) -> list["MainWindow"]:
        return [w for w in cls._live_mm3_windows() if w.collection is not None]

    @classmethod
    def _refresh_second_collection_controls(cls) -> None:
        """Recalcule le bouton/menu dans toutes les fenêtres, sans propriétaire.

        Dès qu'il ne reste qu'une collection ouverte, toute fenêtre restante
        retrouve immédiatement le droit d'en ouvrir une seconde.
        """
        for window in cls._live_mm3_windows():
            try:
                window._update_second_collection_button()
            except RuntimeError:
                cls._mm3_windows.discard(window)

    def _release_secondary_collection_window(self, child) -> None:
        """Compatibilité 017.2.0.2 : libère une ancienne référence locale."""
        self.secondary_collection_windows = [
            w for w in self.secondary_collection_windows if w is not child
        ]
        MainWindow._refresh_second_collection_controls()

    def _update_second_collection_button(self) -> None:
        # 017.2.0.3 — décision globale et symétrique : maximum deux collections
        # ouvertes, quelle que soit la fenêtre qui a été ouverte en premier.
        try:
            active_count = len(MainWindow._active_collection_windows())
        except RuntimeError:
            active_count = 2
        can_open = active_count < 2

        button = getattr(self, "open_second_collection_btn", None)
        if button is not None:
            button.setEnabled(can_open)
            button.setProperty("mm3SecondCollectionAvailable", can_open)
            button.setToolTip(
                "Ouvrir une autre collection dans une seconde fenêtre MM3"
                if can_open else
                "Deux collections sont déjà ouvertes"
            )
            button.style().unpolish(button)
            button.style().polish(button)
            button.update()

        for action_name in (
            "open_second_collection_file_action",
            "open_second_collection_menu_action",
        ):
            action = getattr(self, action_name, None)
            if action is not None:
                action.setEnabled(can_open)

    def _update_collection_action_buttons(self) -> None:
        has_collection = self.collection is not None
        self._update_second_collection_button()
        self.close_collection_btn.setVisible(has_collection)
        self.new_collection_btn.setObjectName("")
        self.close_collection_btn.setObjectName("primaryButton" if has_collection else "")
        for button in (self.new_collection_btn, self.close_collection_btn):
            button.style().unpolish(button)
            button.style().polish(button)
            button.update()

    def _set_active_button(self, collection_active: bool) -> None:
        self.btn_collection.setProperty("active", collection_active)
        self.btn_workshop.setProperty("active", not collection_active)
        for button in (self.btn_collection, self.btn_workshop):
            button.style().unpolish(button)
            button.style().polish(button)

    def show_collection_space(self) -> None:
        self.stack.setCurrentWidget(self.collection_page)
        self._set_active_button(True)
        self.mm3_statusbar.set_space("Collection")

    def show_workshop_space(self) -> None:
        self.stack.setCurrentWidget(self.workshop_page)
        self._set_active_button(False)
        self.mm3_statusbar.set_space("Atelier")

    @property
    def _database_path(self) -> Path:
        return Path(self.startup.database.database_path)

    @property
    def _catalog_database_path(self) -> Path:
        return Path(self.catalog_startup.database.database_path)

    def _startup_for_database(self, database_path: str | Path):
        """Crée un contexte MM3 léger pointant vers un autre fichier SQLite."""
        path = Path(database_path).resolve()
        if path == self._catalog_database_path.resolve():
            return self.catalog_startup
        runtime = copy.copy(self.catalog_startup)
        runtime.database = DatabaseManager(path)
        return runtime

    def _use_database(self, database_path: str | Path) -> None:
        self.startup = self._startup_for_database(database_path)

    def _prepare_database_switch(self, target_database: str | Path) -> None:
        """Libère proprement le contexte courant avant de changer de fichier SQLite.

        Une collection dupliquée est un nouveau fichier autonome qui peut conserver
        le même identifiant interne que sa source. Le changement doit donc se faire
        par le chemin du fichier, après destruction des fenêtres qui utilisent encore
        l'ancien contexte et fermeture explicite de sa connexion SQLite.
        """
        target = Path(target_database).resolve()
        current = self._database_path.resolve()
        if current == target:
            return

        # Détruire d'abord toutes les fenêtres susceptibles de conserver des objets
        # Qt ou des gestionnaires liés à l'ancienne collection.
        self.record_window = self._safe_close_qt_window(self.record_window)
        self.search_window = self._safe_close_qt_window(self.search_window)
        self.query_window = self._safe_close_qt_window(self.query_window)
        self.table_window = self._safe_close_qt_window(self.table_window)
        self.report_window = self._safe_close_qt_window(self.report_window)
        self.toolbox_window = self._safe_close_qt_window(self.toolbox_window)

        try:
            self.startup.database.disconnect()
        except Exception:
            pass

        # Vider les deleteLater() avant de remplacer le contexte : cela évite qu'un
        # ancien widget se réveille ensuite avec le nouveau fichier SQLite.
        try:
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            QApplication.sendPostedEvents(None, 0)
            QApplication.processEvents()
            gc.collect()
            QApplication.processEvents()
        except Exception:
            pass

    def _selected_collection_database(self, collection: dict) -> Path:
        raw = collection.get("_database_path") if isinstance(collection, dict) else None
        return Path(raw).resolve() if raw else self._catalog_database_path.resolve()

    def _window_collection_key(self) -> tuple[str, int] | None:
        if self.collection is None:
            return None
        return (str(self._database_path.resolve()).casefold(), int(self.collection["id"]))

    def release_collection_file_for_mutation(self, database_path: str | Path) -> bool:
        """Libère partout un fichier de collection avant Renommer/Supprimer.

        Si la collection est ouverte dans une fenêtre MM3, elle est fermée proprement
        (avec les protections habituelles) puis toutes les connexions SQLite
        correspondantes sont explicitement libérées.
        """
        target = Path(database_path).resolve()

        for window in list(MainWindow._mm3_windows):
            try:
                if window.collection is not None and window._database_path.resolve() == target:
                    if not window.close_collection():
                        return False
            except RuntimeError:
                continue

        # Sécurité supplémentaire : une fenêtre peut encore pointer sur le fichier
        # sans collection active après un changement de contexte.
        for window in list(MainWindow._mm3_windows):
            try:
                if window._database_path.resolve() == target:
                    window.startup.database.disconnect()
                    window._use_database(window._catalog_database_path)
            except Exception:
                pass

        # Forcer le traitement des deleteLater() avant que le dialogue
        # OpenCollectionDialog tente physiquement de supprimer/renommer le .db.
        try:
            # DeferredDelete est précisément l'évènement Qt qui détruit les
            # widgets ayant reçu deleteLater(). Le traiter explicitement est
            # indispensable avant un renommage physique sous Windows.
            QCoreApplication.sendPostedEvents(
                None, QEvent.Type.DeferredDelete
            )
            QApplication.sendPostedEvents(None, 0)
            QApplication.processEvents()
            gc.collect()
            QApplication.processEvents()
        except Exception:
            pass

        return True

    @staticmethod
    def _set_new_model_data_text_black(model_manager, collection_id: int) -> None:
        """Applique le noir aux données d'un nouveau modèle, sans toucher aux libellés."""
        cid = int(collection_id)
        styles = model_manager.field_styles(cid)
        for field_key in model_manager.all_model_keys(cid):
            key = str(field_key)
            style = dict(styles.get(key, {}))
            data_style = dict(style.get("data", {}))
            data_style["color"] = "#000000"
            style["data"] = data_style
            styles[key] = style
        model_manager.set_field_styles(cid, styles)

    def new_collection(self) -> None:
        # 23.9.0 — création en deux étapes :
        # 1. choix du modèle ; 2. identité de la collection.
        selector = CollectionModelSelectorDialog(self, self.language)
        if not selector.exec():
            return
        model_key = selector.selected_model_key()

        dialog = NewCollectionDialog(self, self.language)
        if not dialog.exec():
            return
        values = dialog.values()
        values["model_key"] = model_key
        # 018.4.4.1.2.9 : chaque nouvelle collection naît directement dans son
        # propre fichier SQLite, nommé d'après la collection.
        catalog_manager = CollectionManager(self._catalog_database_path)
        collections_dir = catalog_manager.collections_folder()
        collections_dir.mkdir(parents=True, exist_ok=True)
        safe_name = CollectionManager._safe_filename(values["name"])
        database_path = collections_dir / f"{safe_name}.coldb"
        if database_path.exists():
            # 23.8.5.1 — un échec de création antérieur peut avoir laissé un
            # fichier SQLite incomplet, invisible dans « Ouvrir une collection ».
            # Un tel fichier orphelin est supprimé automatiquement. En revanche,
            # une vraie collection MM3 existante n'est jamais écrasée.
            stale_file = False
            try:
                existing_rows = CollectionManager(database_path).inspect_collections()
                stale_file = not bool(existing_rows)
            except Exception:
                stale_file = True

            if stale_file:
                try:
                    database_path.unlink()
                except Exception as exc:
                    QMessageBox.critical(
                        self,
                        "Création impossible",
                        "Un ancien fichier incomplet porte déjà ce nom et ne peut pas "
                        f"être supprimé.\n\n{exc}",
                    )
                    return
            else:
                QMessageBox.warning(
                    self,
                    "Création impossible",
                    f"Une collection ou un fichier nommé « {database_path.name} » existe déjà.",
                )
                return

        manager = CollectionManager(database_path)
        try:
            manager.create_collection(values)

            # 23.8.5 — un fichier de collection autonome doit être reconnu
            # immédiatement par « Ouvrir une collection ». La découverte MM3
            # exige collections + records + mm3_meta : les créer dès la naissance
            # du fichier, avant même l'ouverture de la première fiche.
            db = DatabaseManager(database_path)
            db.initialize()
            db.disconnect()

            # Import local volontaire : garantit que le constructeur de
            # collection dispose toujours du gestionnaire d'enregistrements,
            # quelle que soit la copie portable de main_window chargée.
            record_manager = RecordManager(database_path)
            with record_manager._connect() as connection:
                record_manager._ensure_table(connection)

            collection = manager.get_collection_by_name(values["name"])

            # 23.9.1 — le socle historique de MM3 est précisément le modèle
            # Minéraux / Microminéraux : champs, référentiels et disposition
            # standard sont donc conservés tels quels. On mémorise seulement
            # l'origine du modèle ; la collection reste ensuite 100 % modifiable.
            if collection is not None and model_key == "minerals":
                mineral_model_manager = ModelManager(database_path)
                # 23.9.1.1 — le modèle Minéraux reprend exactement la disposition
                # réarrangée et validée dans « 02-choix-Minéraux-Micro minéraux ».
                apply_minerals_template(
                    mineral_model_manager, int(collection["id"])
                )
                self._set_new_model_data_text_black(
                    mineral_model_manager, int(collection["id"])
                )

            if collection is not None and model_key == "fossils":
                fossils_model_manager = ModelManager(database_path)
                apply_fossils_template(
                    fossils_model_manager, int(collection["id"])
                )
                self._set_new_model_data_text_black(
                    fossils_model_manager, int(collection["id"])
                )

            if collection is not None and model_key == "geology_samples":
                sands_model_manager = ModelManager(database_path)
                apply_sands_template(
                    sands_model_manager, int(collection["id"])
                )
                self._set_new_model_data_text_black(
                    sands_model_manager, int(collection["id"])
                )

            if collection is not None and model_key == "stamps":
                stamps_model_manager = ModelManager(database_path)
                apply_stamps_template(
                    stamps_model_manager, int(collection["id"])
                )
                self._set_new_model_data_text_black(
                    stamps_model_manager, int(collection["id"])
                )

            if collection is not None and model_key == "postcards":
                postcards_model_manager = ModelManager(database_path)
                apply_postcards_template(postcards_model_manager, int(collection["id"]))
                self._set_new_model_data_text_black(postcards_model_manager, int(collection["id"]))

            if collection is not None and model_key == "coins":
                coins_model_manager = ModelManager(database_path)
                apply_coins_template(coins_model_manager, int(collection["id"]))
                self._set_new_model_data_text_black(coins_model_manager, int(collection["id"]))

            if collection is not None and model_key == "objects":
                objects_model_manager = ModelManager(database_path)
                apply_objects_template(objects_model_manager, int(collection["id"]))
                self._set_new_model_data_text_black(objects_model_manager, int(collection["id"]))
            if collection is not None and model_key == "books":
                books_model_manager = ModelManager(database_path)
                apply_books_template(books_model_manager, int(collection["id"]))
                self._set_new_model_data_text_black(books_model_manager, int(collection["id"]))
            if collection is not None and model_key == "labels":
                labels_model_manager = ModelManager(database_path)
                apply_labels_template(labels_model_manager, int(collection["id"]))
                self._set_new_model_data_text_black(labels_model_manager, int(collection["id"]))

            if collection is not None and model_key == "blank":
                # 23.8.7.1 — premier modèle réellement générique : Collection vierge.
                # Elle ne naît plus avec la fiche micro-minéralogie héritée.
                # Seuls les deux champs structurels indispensables sont présents.
                model_manager = ModelManager(database_path)
                collection_id = int(collection["id"])

                model_manager.set_visible_fields(
                    collection_id, {"record_number", "record_state"}
                )

                field_styles = model_manager.field_styles(collection_id)
                for field_key in model_manager.all_model_keys(collection_id):
                    field_key = str(field_key)
                    style = dict(field_styles.get(field_key, {}))
                    if field_key in {"record_number", "record_state"}:
                        style.pop("field_deleted", None)
                    else:
                        style["field_deleted"] = True
                    field_styles[field_key] = style
                model_manager.set_field_styles(collection_id, field_styles)

                group_styles = model_manager.group_styles(collection_id)
                for group_name in (
                    "Identification", "Photo", "Localisation",
                    "Aspect", "Acquisition", "Collection",
                ):
                    style = dict(group_styles.get(group_name, {}))
                    style["frame_deleted"] = True
                    group_styles[group_name] = style
                # Le Bandeau reste le support minimal des champs N° et Etat.
                # Une collection vierge possède désormais un marqueur structurel
                # persistant : l'ajout de champs personnalisés ne doit JAMAIS
                # réintroduire le vieux catalogue micro-minéralogique.
                layout_meta = dict(group_styles.get("__mm3_layout__", {}))
                layout_meta["model_kind"] = "blank"
                layout_meta["field_space"] = "sheet_absolute_v1"
                group_styles["__mm3_layout__"] = layout_meta

                band_style = dict(group_styles.get("Bandeau", {}))
                band_style.pop("frame_deleted", None)
                band_style["geometry_space"] = "atelier_px"
                # Taille volontairement minimale : juste N° de fiche + Etat.
                # L'utilisateur reste libre de l'agrandir ensuite.
                band_style["geometry"] = {
                    "x": 12, "y": 12, "w": 900, "h": 122
                }
                group_styles["Bandeau"] = band_style
                model_manager.set_group_styles(collection_id, group_styles)

                # Les deux champs structurels sont placés SOUS la barre de titre
                # du Bandeau, avec environ une ligne de grille de respiration.
                model_manager.set_visual_positions(
                    collection_id,
                    {
                        "record_number": (32, 82),
                        "record_state": (430, 82),
                    },
                )
                model_manager.set_tab_order(
                    collection_id, ["record_number", "record_state"]
                )
                self._set_new_model_data_text_black(
                    model_manager, collection_id
                )

            # 11.4.32 — appliquer en dernier la copie exacte du modèle officiel.
            if collection is not None:
                official_manager = ModelManager(database_path)
                apply_official_template_database(official_manager, int(collection["id"]), model_key)
                translate_created_native_collection(official_manager, int(collection["id"]), self.language)
        except Exception as exc:
            try:
                if 'db' in locals():
                    db.disconnect()
            except Exception:
                pass
            try:
                if database_path.exists():
                    database_path.unlink()
            except Exception:
                pass
            QMessageBox.critical(self, "Création impossible", str(exc))
            return
        if collection is None:
            QMessageBox.critical(self, "Création impossible", "La collection créée n'a pas pu être relue.")
            return
        self._use_database(database_path)
        self._activate_collection(collection)
        QMessageBox.information(
            self,
            self._t("Collection créée"),
            self._t("La collection « {name} » a été créée.\n\nVous pouvez maintenant ouvrir l’atelier des fiches.").format(name=self.collection_name),
        )

    def enable_db_double_click(self) -> None:
        if sys.platform != "win32":
            QMessageBox.information(self, "Double clic .coldb", "Cette fonction est disponible sous Windows.")
            return
        answer = QMessageBox.question(
            self, "Ouvrir les fichiers .coldb avec G-Skol",
            "Associer les fichiers .coldb à G-Skol pour votre compte Windows ?\n\n"
            "Vous pourrez modifier l'application par défaut dans les paramètres Windows.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes: return
        try:
            app_path = Path(__file__).resolve().parents[1] / "app.py"
            windows_choice = register_db_association(app_path, make_default=True)
        except Exception as exc:
            QMessageBox.warning(self, "Association impossible", str(exc))
            return
        message = "L'ouverture des fichiers .coldb avec G-Skol a été enregistrée pour votre compte Windows."
        if windows_choice:
            message += ("\n\nWindows a déjà une application par défaut pour .coldb. Faites un clic droit sur un .coldb, "
                        "choisissez « Ouvrir avec », puis G-Skol et cochez « Toujours utiliser cette application ».")
        QMessageBox.information(self, "Double clic .coldb", message)

    def open_collection_file(self, path: str | Path) -> None:
        """Ouvre directement, à son emplacement, le fichier .coldb reçu par Windows."""
        path = Path(path).expanduser().resolve()
        if path.suffix.casefold() != ".coldb":
            QMessageBox.warning(self, "Collection non reconnue", "Ce fichier n'est pas une collection SQLite MM3.")
            return
        try:
            manager = CollectionManager(path)
            found = manager.inspect_collections()
        except Exception as exc:
            QMessageBox.warning(self, "Collection non reconnue", str(exc))
            return
        if not found:
            QMessageBox.warning(self, "Collection vide", "Ce fichier ne contient aucune collection MM3.")
            return
        if len(found) == 1:
            collection = dict(found[0])
        else:
            from PySide6.QtWidgets import QInputDialog
            labels = [f"{item['name']} (N° {item['id']})" for item in found]
            selection, accepted = QInputDialog.getItem(self, "Collection à ouvrir", "Collection :", labels, 0, False)
            if not accepted: return
            collection = dict(found[labels.index(selection)])
        try:
            self._prepare_database_switch(path)
            self._use_database(path)
            self._activate_collection(collection)
        except Exception as exc:
            QMessageBox.warning(self, "Ouverture impossible", str(exc))
            self._use_database(self._catalog_database_path)
            return
        self.statusBar().showMessage(f"Collection « {self.collection_name} » ouverte depuis {path}", 6000)

    def open_collection(self) -> None:
        manager = CollectionManager(self._catalog_database_path)
        dialog = OpenCollectionDialog([], manager, self, self.language)
        accepted = bool(dialog.exec())

        # Le menu contextuel peut avoir renommé ou supprimé la collection
        # actuellement ouverte, même si l'utilisateur ferme ensuite la boîte.
        if (
            self.collection is not None
            and self._database_path.resolve() == self._catalog_database_path.resolve()
        ):
            refreshed = manager.get_collection_by_id(int(self.collection["id"]))
            if refreshed is None:
                self.close_collection()
            elif refreshed["name"] != self.collection["name"]:
                self._activate_collection(refreshed)

        if not accepted:
            return
        collection = dialog.selected_collection()
        if collection is None:
            return

        selected_db = self._selected_collection_database(collection)
        selected_folder = str(collection.get("_folder_name") or "Non classées")
        selected_manager = CollectionManager(selected_db)
        # Relire la ligne : elle a pu être renommée juste avant l'ouverture,
        # tout en conservant les marqueurs d'une copie extérieure temporaire.
        external_meta = {k: v for k, v in dict(collection).items() if str(k).startswith("_external_")}
        collection = selected_manager.get_collection_by_id(int(collection["id"])) or collection
        collection = dict(collection)
        collection.pop("_database_path", None)
        collection.update(external_meta)
        collection["_folder_name"] = selected_folder
        # 11.4.33 — changement de fichier explicite et sûr. Une collection
        # dupliquée peut avoir le même id interne que l'originale, mais son fichier
        # SQLite est différent : il faut libérer l'ancien contexte AVANT le switch.
        self._prepare_database_switch(selected_db)
        self._use_database(selected_db)
        self._activate_collection(collection)
        self.statusBar().showMessage(f"Collection « {self.collection_name} » ouverte", 5000)

    def save_collection_as(self) -> None:
        """Enregistre la collection active comme nouvelle collection MM3 locale.

        Pour un .coldb/.colstr ouvert par Parcourir, la base active est une copie
        temporaire : le paquet source reste donc strictement intact.
        """
        if self.collection is None:
            QMessageBox.information(self, "Enregistrer sous", "Aucune collection n'est ouverte.")
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("Enregistrer la collection sous")
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel("Nom de la collection :"))
        name_edit = QLineEdit(str(self.collection.get("name") or ""), dlg)
        name_edit.selectAll(); lay.addWidget(name_edit)
        lay.addWidget(QLabel("Dossier destinataire :"))
        store = CollectionFolderStore(CollectionManager(self._catalog_database_path).collections_folder())
        folder_combo = QComboBox(dlg); folder_combo.addItems(store.ordered_folders()); lay.addWidget(folder_combo)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel, parent=dlg)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Enregistrer")
        buttons.accepted.connect(dlg.accept); buttons.rejected.connect(dlg.reject); lay.addWidget(buttons)
        if not dlg.exec(): return
        requested = name_edit.text().strip()
        if not requested:
            QMessageBox.warning(self, "Enregistrer sous", "Le nom de la collection est obligatoire."); return
        try:
            old_external_temp_dir = str(self.collection.get("_external_temp_dir") or "")
            source_manager = CollectionManager(self._database_path)
            result = source_manager.import_collection_to_folder(
                int(self.collection["id"]),
                CollectionManager(self._catalog_database_path).collections_folder(),
                requested,
            )
            target_path = str(result.get("_database_path") or "")
            folder = folder_combo.currentText() or "Non classées"
            store.assign([target_path], folder)
            result["_folder_name"] = folder
            # L'enregistrement est terminé : basculer sur la nouvelle collection locale.
            self._prepare_database_switch(target_path)
            self._use_database(target_path)
            self._activate_collection(result)
            if old_external_temp_dir:
                try: shutil.rmtree(old_external_temp_dir, ignore_errors=True)
                except Exception: pass
            QMessageBox.information(self, "Enregistrer sous", f"La collection « {result.get('name','')} » a été enregistrée dans le dossier « {folder} ».")
        except Exception as exc:
            QMessageBox.critical(self, "Enregistrement impossible", str(exc))

    def open_second_collection(self) -> None:
        """Ouvre une autre collection dans une deuxième fenêtre MM3.

        017.2.0.3 : fonctionnement totalement symétrique. La fenêtre qui reste
        ouverte après fermeture de l'autre peut immédiatement ouvrir une nouvelle
        deuxième collection, autant de fois que nécessaire.
        """
        active_windows = MainWindow._active_collection_windows()
        if len(active_windows) >= 2:
            QMessageBox.information(
                self,
                "Deux collections déjà ouvertes",
                "Deux collections sont déjà ouvertes dans MM3.",
            )
            MainWindow._refresh_second_collection_controls()
            return

        manager = CollectionManager(self._catalog_database_path)
        try:
            collections = manager.list_collections()
        except Exception as exc:
            QMessageBox.critical(self, "Ouverture impossible", str(exc))
            return

        dialog = OpenCollectionDialog(collections, manager, self, self.language)
        dialog.setWindowTitle("Ouvrir une 2e collection")
        if not dialog.exec():
            return

        collection = dialog.selected_collection()
        if collection is None:
            return

        selected_db = self._selected_collection_database(collection)
        selected_folder = str(collection.get("_folder_name") or "Non classées")
        selected_manager = CollectionManager(selected_db)
        collection = selected_manager.get_collection_by_id(int(collection["id"])) or collection
        collection = dict(collection)
        collection.pop("_database_path", None)
        collection["_folder_name"] = selected_folder

        # Une collection est identifiée par le couple fichier SQLite + id.
        # Deux fichiers différents peuvent parfaitement contenir un id identique.
        selected_key = (str(selected_db.resolve()).casefold(), int(collection["id"]))
        current_keys = {
            w._window_collection_key()
            for w in MainWindow._active_collection_windows()
            if w.collection is not None
        }
        if selected_key in current_keys:
            QMessageBox.information(
                self,
                "Collection déjà ouverte",
                f'La collection « {collection["name"]} » est déjà ouverte.',
            )
            return

        # Si une ancienne seconde fenêtre existe encore mais a simplement fermé
        # sa collection, la réutiliser au lieu d'empiler une troisième fenêtre.
        target = None
        for candidate in MainWindow._live_mm3_windows():
            if candidate is not self and candidate.collection is None:
                target = candidate
                break

        selected_startup = self._startup_for_database(selected_db)
        if target is None:
            target = MainWindow(
                selected_startup,
                restore_last_collection=False,
                persist_last_collection=False,
                catalog_startup=self.catalog_startup,
            )
        else:
            target.startup = selected_startup
            target.catalog_startup = self.catalog_startup
            target.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
            target.destroyed.connect(
                lambda *_args: MainWindow._refresh_second_collection_controls()
            )

        target._activate_collection(collection)
        target.setWindowTitle(APP_NAME)
        target.show()
        target.showNormal()
        target.raise_()
        target.activateWindow()

        MainWindow._refresh_second_collection_controls()
        self.statusBar().showMessage(
            f'Seconde collection « {collection["name"]} » ouverte', 5000
        )

    def register_transferred_record(
        self,
        record_id: int,
        source_record: dict | None = None,
    ) -> None:
        """Mémorise une fiche créée/remplacée par Copier/Coller."""
        if self.collection is None:
            return
        self._transferred_record_ids.add(int(record_id))

        # Conserver aussi les valeurs source immédiatement comme filet de sécurité.
        if isinstance(source_record, dict):
            for field, code in REFERENTIAL_BY_FIELD.items():
                value = str(source_record.get(field, "") or "").strip()
                if value:
                    self._pending_transferred_referentials.setdefault(code, set()).add(value)

    def _pending_missing_referentials(self) -> dict[str, list[str]]:
        """Vérifie tous les champs sans répéter les conversions multilingues.

        La vérification reste complète, y compris pour les anciennes collections.
        Les valeurs canoniques sont calculées une seule fois par valeur distincte
        pendant cette fermeture, et non à chaque comparaison.
        """
        if self.collection is None:
            return {}

        from functools import lru_cache

        collection_id = int(self.collection["id"])
        records = RecordManager(self._database_path)
        all_records = records.list_records(collection_id)

        candidates_by_code: dict[str, set[str]] = {}
        for record in all_records:
            for field, code in REFERENTIAL_BY_FIELD.items():
                value = str(record.get(field, "") or "").strip()
                if value:
                    candidates_by_code.setdefault(code, set()).add(value)

        if not candidates_by_code:
            return {}

        manager = ReferentialManager(self._database_path)
        manager.ensure_defaults(collection_id)
        language = self.language

        # En allemand, canonical_native_value reconstruisait la table de
        # traduction inverse à CHAQUE valeur (près de 6 000 fois pour mineral_name).
        # La construire une fois par fermeture préserve exactement les mêmes
        # correspondances tout en supprimant le coût quadratique.
        if str(language or "").lower().startswith("de"):
            from core import i18n as _i18n
            _de_reverse = {
                str(v).casefold(): str(k)
                for k, v in _i18n.DE.items()
                if str(v) and str(k) != str(v)
            }
            _de_reverse.update({
                str(v).casefold(): str(k)
                for k, v in _i18n._DE_NATIVE_VALUES.items()
            })

            @lru_cache(maxsize=None)
            def canonical(value: str) -> str:
                text = str(value or "").strip()
                if text in {"À vérifier", "A vérifier", "Valider"}:
                    return "Vérifier"
                return _de_reverse.get(text.casefold(), text)
        else:
            @lru_cache(maxsize=None)
            def canonical(value: str) -> str:
                return canonical_native_value(value, language)

        missing: dict[str, list[str]] = {}
        for code, candidates in candidates_by_code.items():
            # La comparaison doit employer EXACTEMENT la normalisation
            # utilisée par ReferentialManager.add_value(). En particulier,
            # mineral_name est stocké en MAJUSCULES et les espaces multiples
            # sont condensés. Sinon, des valeurs déjà ajoutées peuvent être
            # signalées à nouveau à chaque fermeture.
            def identity(value: str) -> str:
                return manager.normalize(canonical(str(value).strip()), code).casefold()

            existing = {
                identity(value)
                for value in manager.list_values(collection_id, code, active_only=False)
            }
            excluded = {
                identity(value)
                for value in manager.excluded_values(collection_id, code)
            }
            values_by_key: dict[str, str] = {}
            for raw in candidates:
                value = manager.normalize(canonical(raw.strip()), code)
                key = identity(value)
                if key in existing or key in excluded:
                    continue
                if code == "record_state":
                    if value in {"À vérifier", "A vérifier", "Valider"}:
                        value = "Vérifier"
                        key = value.casefold()
                    if value not in {"OK", "Vérifier", "Libre"}:
                        continue
                    if key in existing or key in excluded:
                        continue
                values_by_key[key] = value
            if values_by_key:
                missing[code] = sorted(values_by_key.values(), key=str.casefold)
        return missing

    def _confirm_transferred_referentials_before_close(self) -> bool:
        """Retourne False uniquement si l'utilisateur annule la fermeture."""
        missing = self._pending_missing_referentials()
        if not missing or self.collection is None:
            self._pending_transferred_referentials.clear()
            self._transferred_record_ids.clear()
            return True

        collection_name = str(self.collection["name"])
        labels = {
            code: label
            for code, label, _is_master in ReferentialManager.DEFAULT_REFERENTIALS
        }
        lines = []
        for code, values in missing.items():
            label = labels.get(code, code)
            lines.append(f"{label} :")
            lines.extend(f"   • {value}" for value in values)
            lines.append("")
        details = "\n".join(lines).rstrip()

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle(tr("Mise à jour des référentiels", self.language))
        box.setText(
            tr("Des valeurs présentes dans les fiches ne figurent pas encore dans les référentiels de « {name} ».", self.language).format(name=collection_name)
        )
        box.setInformativeText(
            tr("Voulez-vous mettre automatiquement à jour les référentiels de cette collection ?", self.language)
        )
        box.setDetailedText(details)
        add_button = box.addButton(tr("Ajouter tout", self.language), QMessageBox.ButtonRole.AcceptRole)
        skip_button = box.addButton(tr("Ne rien ajouter", self.language), QMessageBox.ButtonRole.DestructiveRole)
        cancel_button = box.addButton(
            tr("Annuler la fermeture de la collection {name}", self.language).format(name=collection_name),
            QMessageBox.ButtonRole.RejectRole,
        )

        # Qt crée lui-même le bouton qui ouvre la zone de détails.
        # Le redimensionnement précédent intervenait trop tôt : au moment où
        # QMessageBox reconstruisait sa barre de boutons, sa largeur était reperdue.
        # On le règle donc APRÈS l'ajout de tous les boutons et on lui impose une
        # largeur minimale calculée à partir de son vrai texte français.
        for button in box.findChildren(QPushButton):
            if button.text() in {"Show Details...", "Show Details…", "Afficher détails", "Afficher les détails"}:
                button.setText(tr("Afficher les détails", self.language))
                button.setMinimumWidth(max(145, button.sizeHint().width() + 18))

        # Donne un peu d'air à l'ensemble pour que les quatre boutons tiennent
        # naturellement sur une seule ligne, même avec un nom de collection long.
        box.setMinimumWidth(760)
        box.setDefaultButton(add_button)
        box.exec()

        clicked = box.clickedButton()
        if clicked is cancel_button:
            return False

        if clicked is add_button:
            manager = ReferentialManager(self._database_path)
            collection_id = int(self.collection["id"])
            manager.ensure_defaults(collection_id)
            try:
                for code, values in missing.items():
                    for value in values:
                        manager.add_value(collection_id, code, value)
            except Exception as exc:
                QMessageBox.critical(
                    self,
                    tr("Mise à jour impossible", self.language),
                    f"Les référentiels n'ont pas pu être mis à jour.\n\n{exc}",
                )
                return False

        # Ajouter tout ou Ne rien ajouter : la décision est prise pour ce lot.
        self._pending_transferred_referentials.clear()
        self._transferred_record_ids.clear()
        return True

    def _update_page_titles(self) -> None:
        """017.1.5 — affiche la collection active dans les grands titres d'accueil."""
        if self.collection_name:
            name = collection_display_name(self.collection or {"name": self.collection_name})
            accent = "#8B3F2F"
            self.collection_page_title.setText(
                f'<span style="color:#111111; font-weight:700;">{self._t("Collection")} :</span> '
                f'<span style="color:{accent}; font-weight:700;">{name}</span>'
            )
            self.workshop_page_title.setText(
                f'<span style="color:#111111; font-weight:700;">{self._t("Atelier")} :</span> '
                f'<span style="color:{accent}; font-weight:700;">{name}</span>'
            )
        else:
            self.collection_page_title.setText(
                f'<span style="color:#111111; font-weight:700;">{self._t("Collection")}</span>'
            )
            self.workshop_page_title.setText(
                f'<span style="color:#111111; font-weight:700;">{self._t("Atelier")}</span>'
            )

    @staticmethod
    def _safe_close_qt_window(window):
        """Ferme ET détruit un QWidget afin de libérer immédiatement SQLite.

        Sous Windows, masquer/fermer une fenêtre ne suffit pas toujours : tant
        que l'objet Qt reste vivant, un gestionnaire associé peut conserver un
        handle sur le fichier de collection et bloquer Renommer/Supprimer.
        """
        if window is None:
            return None
        try:
            window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        except Exception:
            pass
        try:
            window.close()
        except RuntimeError:
            return None
        except Exception:
            pass
        try:
            window.deleteLater()
        except Exception:
            pass
        try:
            QApplication.processEvents()
        except Exception:
            pass
        return None

    def _activate_collection(self, collection: dict) -> None:
        # 23.9.3.1.1 — évolution non destructive des anciennes collections Minéraux.
        try:
            ensure_minerals_legacy_fields(
                ModelManager(self._database_path), int(collection["id"])
            )
        except Exception:
            # Une migration de modèle ne doit jamais empêcher l'ouverture.
            pass
        self.record_window = self._safe_close_qt_window(self.record_window)
        self.search_window = self._safe_close_qt_window(self.search_window)
        self.query_window = self._safe_close_qt_window(self.query_window)
        self.table_window = self._safe_close_qt_window(self.table_window)
        self.report_window = self._safe_close_qt_window(self.report_window)
        self.toolbox_window = self._safe_close_qt_window(self.toolbox_window)
        self._pending_transferred_referentials.clear()
        self._transferred_record_ids.clear()
        self.collection = dict(collection)
        self.collection_name = str(collection["name"])
        self._update_page_titles()
        self._apply_style()
        self.setWindowTitle(APP_NAME)
        self.current_collection_label.setText(collection_display_name(self.collection))
        self.mm3_statusbar.set_collection(collection_display_name(self.collection))
        self._update_collection_action_buttons()
        if self.persist_last_collection:
            self.catalog_startup.settings.last_collection = self.collection_name
            self.catalog_startup.settings.last_collection_path = str(self._database_path.resolve())
            self.catalog_startup.settings.last_collection_id = int(self.collection["id"])
            self.catalog_startup.settings.save()

    def close_collection(self) -> bool:
        # 20.32 : diagnostic non intrusif, chronométrage par étape.
        import time as _close_time
        from performance_diagnostic import write as _close_log
        _close_t0 = _close_time.perf_counter()
        _close_last = _close_t0
        def _close_mark(label):
            nonlocal _close_last
            now = _close_time.perf_counter()
            _close_log('FERMETURE %-38s +%.3f s | total %.3f s' % (
                label, now - _close_last, now - _close_t0))
            _close_last = now
        _close_mark('début close_collection')
        if self.collection is None:
            self.statusBar().showMessage(self._t("Aucune collection ouverte"), 3000)
            return True
        if self.collection.get("_external_temporary"):
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Warning)
            box.setWindowTitle("Collection extérieure")
            box.setText("Cette collection extérieure n'a pas été enregistrée dans MM3.")
            box.setInformativeText("Les modifications effectuées dans MM3 seront perdues.\n\nLe fichier source original restera intact et pourra être transféré ou réutilisé ultérieurement dans son état d'origine.")
            save_btn = box.addButton("Enregistrer sous…", QMessageBox.ButtonRole.AcceptRole)
            close_btn = box.addButton("Fermer sans enregistrer", QMessageBox.ButtonRole.DestructiveRole)
            cancel_btn = box.addButton("Annuler", QMessageBox.ButtonRole.RejectRole)
            box.setDefaultButton(cancel_btn); box.exec()
            if box.clickedButton() is save_btn:
                self.save_collection_as()
                # Si l'enregistrement a réussi, la collection n'est plus temporaire.
                if self.collection is not None and not self.collection.get("_external_temporary"):
                    return self.close_collection()
                return False
            if box.clickedButton() is not close_btn: return False
        _close_mark('avant vérification référentiels')
        if not self._confirm_transferred_referentials_before_close():
            _close_mark('annulation référentiels')
            return False
        _close_mark('après vérification référentiels')
        previous = self.collection_name
        external_temp_dir = str(self.collection.get("_external_temp_dir") or "")
        self.record_window = self._safe_close_qt_window(self.record_window)
        _close_mark("fenêtre record_window")
        self.search_window = self._safe_close_qt_window(self.search_window)
        _close_mark("fenêtre search_window")
        self.query_window = self._safe_close_qt_window(self.query_window)
        _close_mark("fenêtre query_window")
        self.table_window = self._safe_close_qt_window(self.table_window)
        _close_mark("fenêtre table_window")
        self.report_window = self._safe_close_qt_window(self.report_window)
        _close_mark("fenêtre report_window")
        self.toolbox_window = self._safe_close_qt_window(self.toolbox_window)
        _close_mark("fenêtre toolbox_window")
        # 018.4.4.1.2.9 — libérer réellement le fichier autonome à la fermeture.
        # Sans cela Windows conserve un handle SQLite et refuse ensuite de renommer
        # physiquement le .db (WinError 32).
        active_database = self._database_path.resolve()
        catalog_database = self._catalog_database_path.resolve()
        _close_mark("avant libération base SQLite")
        if active_database != catalog_database:
            try:
                self.startup.database.disconnect()
            except Exception:
                pass
            self._use_database(catalog_database)
        _close_mark("après libération base SQLite")

        self.collection = None
        self.collection_name = None
        self._update_page_titles()
        self._apply_style()
        self.setWindowTitle(APP_NAME)
        self.current_collection_label.setText(self._t("Aucune collection ouverte"))
        self.mm3_statusbar.set_collection(None)
        self._update_collection_action_buttons()
        _close_mark("mise à jour interface")
        # Conserver la dernière collection utilisée pour la réouverture au démarrage.
        self.statusBar().showMessage(self._t("Collection « {name} » fermée").format(name=previous), 5000)
        self._second_collection_owner = None
        MainWindow._refresh_second_collection_controls()
        if external_temp_dir:
            try: shutil.rmtree(external_temp_dir, ignore_errors=True)
            except Exception: pass
        _close_mark("fin close_collection")
        return True

    def closeEvent(self, event) -> None:  # noqa: N802
        """La croix Windows applique la même protection que Fermer la collection."""
        if self.collection is not None and self.persist_last_collection:
            # Dernière écriture juste avant fermeture : c'est cette collection,
            # encore ouverte à cet instant, qui doit revenir au prochain lancement.
            try:
                self.catalog_startup.settings.last_collection = str(self.collection_name or self.collection.get("name") or "")
                self.catalog_startup.settings.last_collection_path = str(self._database_path.resolve())
                self.catalog_startup.settings.last_collection_id = int(self.collection["id"])
                self.catalog_startup.settings.save()
            except Exception as exc:
                self.startup.logger.error(f"Impossible de mémoriser la dernière collection : {exc}")
        if self.collection is not None:
            if self.collection.get("_external_temporary"):
                box = QMessageBox(self)
                box.setIcon(QMessageBox.Icon.Warning)
                box.setWindowTitle("Collection extérieure")
                box.setText("Cette collection extérieure n'a pas été enregistrée dans MM3.")
                box.setInformativeText("Les modifications effectuées dans MM3 seront perdues.\n\nLe fichier source original restera intact et pourra être transféré ou réutilisé ultérieurement dans son état d'origine.")
                save_btn = box.addButton("Enregistrer sous…", QMessageBox.ButtonRole.AcceptRole)
                close_btn = box.addButton("Fermer sans enregistrer", QMessageBox.ButtonRole.DestructiveRole)
                cancel_btn = box.addButton("Annuler", QMessageBox.ButtonRole.RejectRole)
                box.setDefaultButton(cancel_btn); box.exec()
                if box.clickedButton() is save_btn:
                    self.save_collection_as()
                    # En cas de succès, la copie locale est désormais active et peut être fermée.
                    if self.collection is not None and not self.collection.get("_external_temporary"):
                        self.close_collection()
                        event.accept()
                    else:
                        event.ignore()
                    return
                if box.clickedButton() is not close_btn:
                    event.ignore(); return
            if not self._confirm_transferred_referentials_before_close():
                event.ignore()
                return
        self._second_collection_owner = None
        # Retirer immédiatement la fenêtre du registre AVANT la destruction Qt :
        # la fenêtre restante doit récupérer son bouton dès le premier cycle.
        MainWindow._mm3_windows.discard(self)
        event.accept()
        MainWindow._refresh_second_collection_controls()

    def _create_record_window(self) -> RecordWindow:
        """Construit une Fiche directement comme vraie fenêtre indépendante.

        39.32.11.7.6 — auparavant la Fiche était d'abord construite avec la
        fenêtre d'accueil comme parent, puis tout son arbre Qt était reparenté
        après coup par _make_independent_window(). Sous Windows, ce reparentage
        d'une Fiche riche peut forcer une seconde passe de polish/layout et
        consommer plusieurs secondes qui n'apparaissaient pas dans le chrono du
        constructeur. La Fiche naît désormais top-level : aucun reparentage
        massif au premier affichage.
        """
        window = RecordWindow(self.startup, self.collection, None)
        window.setProperty("_mm3_independent_window", True)
        window.recordSaved.connect(self._after_record_saved)
        window.recordDraftChanged.connect(self._after_record_draft_changed)

        def forget_closed_record_window():
            # Ne jamais effacer une éventuelle Fiche plus récente.
            if self.record_window is window:
                self.record_window = None

        window.windowClosed.connect(forget_closed_record_window)
        return window

    def _live_record_window(self):
        """Retourne la Fiche seulement si son objet Qt est encore exploitable."""
        window = self.record_window
        if window is None:
            return None
        try:
            # Un simple accès Qt suffit à détecter un wrapper dont le C++ a été détruit.
            window.isVisible()
            return window
        except RuntimeError:
            self.record_window = None
            return None

    def _after_record_draft_changed(self, record_id: int, values: object) -> None:
        """Répercute immédiatement la saisie courante de la Fiche dans le Tableau."""
        try:
            if self.table_window is not None and self.table_window.isVisible():
                preview = getattr(self.table_window, "apply_record_preview", None)
                if callable(preview):
                    preview(int(record_id), dict(values or {}))
        except RuntimeError:
            self.table_window = None
        except Exception:
            pass

    def _after_record_saved(self, record_id: int) -> None:
        """Une Fiche vient d'être enregistrée : rafraîchir les autres vues."""
        try:
            if self.table_window is not None and self.table_window.isVisible():
                self.table_window.refresh_table()
        except RuntimeError:
            self.table_window = None
        except Exception:
            pass

        try:
            if self.search_window is not None and self.search_window.isVisible():
                self.search_window.refresh_results()
        except RuntimeError:
            self.search_window = None
        except Exception:
            pass

    def _after_table_record_changed(self, record_id: int) -> None:
        """Une cellule du Tableau vient d'être enregistrée : rafraîchir la Fiche."""
        try:
            record_window = self._live_record_window()
            if record_window is not None:
                refresh = getattr(record_window, "refresh_after_external_data_change", None)
                if callable(refresh):
                    refresh()
        except Exception:
            pass

        try:
            if self.search_window is not None and self.search_window.isVisible():
                self.search_window.refresh_results()
        except RuntimeError:
            self.search_window = None
        except Exception:
            pass

    def open_records(self, _feature_name: str | None = None) -> None:
        if self.collection is None:
            QMessageBox.information(
                self,
                self._t("Aucune collection ouverte"),
                self._t("Ouvrez ou créez d'abord une collection avant d'accéder aux fiches."),
            )
            return
        # 39.32.11.7.13 — la Fiche est construite une seule fois par collection.
        # Fermer la fenêtre utilisateur la masque désormais sans détruire son
        # arbre Qt. Les réouvertures réutilisent donc exactement la même Fiche
        # déjà construite, ce qui évite le coût de création de dizaines de
        # widgets, référentiels, filtres et surfaces graphiques à chaque clic.
        current_record_window = self._live_record_window()

        if current_record_window is None:
            self.record_window = self._create_record_window()
        else:
            self.record_window = current_record_window
            # La fenêtre peut avoir été masquée par sa croix Windows. Ne pas
            # reconstruire ni recharger toute la collection : les données sont
            # déjà en mémoire et les autres vues déclenchent leurs rafraîchissements
            # ciblés via les signaux existants.
        # Ouvrir la fiche dans sa taille de travail normale.
        # showNormal() évite que Qt mémorise et réapplique un état maximisé
        # à chaque retour depuis l'écran d'accueil.
        self._bring_window_to_front(self.record_window)

    def open_search(self, _feature_name: str | None = None) -> None:
        if self.collection is None:
            QMessageBox.information(
                self,
                self._t("Aucune collection ouverte"),
                self._t("Ouvrez ou créez d'abord une collection avant d'effectuer une recherche."),
            )
            return
        if self.search_window is None:
            self.search_window = SearchWindow(
                self.startup, self.collection, self.open_record_from_search, self
            )
        else:
            self.search_window.refresh_results()
        self._bring_window_to_front(self.search_window)
        self.search_window.focus_first_criterion(select_all=True)

    def open_query(self, _feature_name: str | None = None) -> None:
        if self.collection is None:
            QMessageBox.information(
                self,
                self._t("Aucune collection ouverte"),
                self._t("Ouvrez ou créez d'abord une collection avant de construire une requête."),
            )
            return
        if self.query_window is None:
            self.query_window = QueryWindow(
                self.collection,
                TableWindow.COLUMNS,
                self.execute_multicriteria_query,
                self._database_path,
                self,
            )
        self._bring_window_to_front(self.query_window)
        self.query_window.focus_value(select_all=True)

    def execute_multicriteria_query(self, criteria: list[dict[str, str]]) -> int:
        if self.collection is None:
            return 0
        if self.table_window is None:
            self.table_window = TableWindow(
                self.startup, self.collection, self.open_record_from_table, self
            )
            self.table_window.recordChanged.connect(self._after_table_record_changed)
        count = self.table_window.apply_multicriteria_query(criteria)
        self._bring_window_to_front(self.table_window)
        return count

    # Compatibilité interne avec 013.0 : une requête simple est simplement
    # une requête multicritère contenant une seule ligne.
    def execute_simple_query(self, field: str, operator: str, value: str) -> int:
        return self.execute_multicriteria_query([{
            "connector": "and", "field": field, "operator": operator, "value": value
        }])

    def _make_independent_window(self, window) -> None:
        """Transforme une grande fenêtre MM3 en vraie fenêtre Windows indépendante."""
        if window is None:
            return
        if window.property("_mm3_independent_window"):
            return

        # Un parent Qt rend la fenêtre "owned" par la fenêtre principale sous Windows.
        # On le retire pour obtenir un vrai top-level : clic dans la barre des tâches,
        # Alt+Tab et clic direct retrouvent alors le comportement Windows normal.
        geometry = window.geometry()
        window.setParent(None, Qt.WindowType.Window)
        window.setGeometry(geometry)
        window.setProperty("_mm3_independent_window", True)

    def _bring_window_to_front(self, window) -> None:
        """Affiche d'abord la fenêtre, puis renforce le premier plan sans bloquer."""
        if window is None:
            return

        self._make_independent_window(window)

        # Afficher immédiatement. Les opérations de mise au premier plan Windows
        # sont repoussées à la boucle Qt suivante : elles ne retardent plus
        # l'apparition visuelle de la Fiche.
        window.showNormal()

        def finish_activation():
            try:
                window.raise_()
                window.activateWindow()
            except RuntimeError:
                return

            if sys.platform.startswith("win"):
                try:
                    hwnd = int(window.winId())
                    user32 = ctypes.windll.user32

                    SW_RESTORE = 9
                    HWND_TOP = 0
                    SWP_NOMOVE = 0x0002
                    SWP_NOSIZE = 0x0001
                    SWP_SHOWWINDOW = 0x0040

                    user32.ShowWindow(hwnd, SW_RESTORE)
                    user32.SetWindowPos(
                        hwnd,
                        HWND_TOP,
                        0, 0, 0, 0,
                        SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW,
                    )
                    user32.SetForegroundWindow(hwnd)
                    user32.BringWindowToTop(hwnd)
                except Exception:
                    pass

        QTimer.singleShot(0, finish_activation)

    def open_report_editor(self, _feature_name: str | None = None) -> None:
        """Ouvre le moteur États dans son contexte Atelier / conception."""
        if self.collection is None:
            QMessageBox.information(
                self,
                self._t("Aucune collection ouverte"),
                self._t("Ouvrez ou créez d’abord une collection avant d’utiliser l’Éditeur d’états."),
            )
            return

        if self.report_window is None:
            self.report_window = ReportWindow(
                self.startup, self.collection, self
            )

        self.report_window.open_workshop_editor()
        self._bring_window_to_front(self.report_window)

    def open_reports(self, _feature_name: str | None = None) -> None:
        if self.collection is None:
            QMessageBox.information(
                self,
                self._t("Aucune collection ouverte"),
                self._t("Ouvrez ou créez d'abord une collection avant d'utiliser les États."),
            )
            return
        if self.report_window is None:
            self.report_window = ReportWindow(
                self.startup, self.collection, self
            )
        self.report_window.open_consultation_home()
        self._bring_window_to_front(self.report_window)

    def open_table(self, _feature_name: str | None = None) -> None:
        if self.collection is None:
            QMessageBox.information(
                self,
                self._t("Aucune collection ouverte"),
                self._t("Ouvrez ou créez d'abord une collection avant d'afficher la Vue Tableau."),
            )
            return
        if self.table_window is None:
            self.table_window = TableWindow(
                self.startup, self.collection, self.open_record_from_table, self
            )
            self.table_window.recordChanged.connect(self._after_table_record_changed)
        else:
            self.table_window.clear_query(refresh=False)
            self.table_window.refresh_table()
        self._bring_window_to_front(self.table_window)

    def open_record_from_table(self, record_id: int) -> None:
        # La logique d'ouverture est identique à celle d'un résultat de recherche.
        self.open_record_from_search(record_id)

    def open_record_from_search(self, record_id: int) -> None:
        if self.collection is None:
            return
        if self.record_window is None:
            self.record_window = self._create_record_window()
        if not self.record_window.select_record_by_id(record_id):
            QMessageBox.information(
                self, "Fiche introuvable", "La fiche sélectionnée n'existe plus."
            )
            if self.search_window is not None:
                self.search_window.refresh_results()
            return
        self._bring_window_to_front(self.record_window)


    def open_models(self, _feature_name: str | None = None) -> None:
        """1.0.223 — sépare nettement l’Atelier de la fiche courante et les modèles maîtres."""
        chooser = QDialog(self)
        chooser.setWindowTitle(self._t("Atelier — Modèles de fiches"))
        chooser.resize(720, 330)
        lay = QVBoxLayout(chooser)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(16)
        title = QLabel(self._t("Que souhaitez-vous modifier ?"))
        f = title.font(); f.setPointSize(f.pointSize() + 4); f.setBold(True); title.setFont(f)
        lay.addWidget(title)
        intro = QLabel(self._t("Les deux modules utilisent le même moteur graphique, mais travaillent sur des éléments différents."))
        intro.setWordWrap(True); lay.addWidget(intro)
        current_btn = QPushButton(self._t("Modifier la fiche actuelle de la collection"))
        current_btn.setMinimumHeight(76)
        current_btn.setEnabled(self.collection is not None)
        if self.collection is None:
            current_btn.setToolTip(self._t("Aucune collection n’est actuellement ouverte."))
        master_btn = QPushButton(self._t("Créer / modifier des modèles adaptés à une collection"))
        master_btn.setMinimumHeight(76)
        current_btn.setStyleSheet("QPushButton { background:#DDECE4; font-weight:600; text-align:left; padding:16px; }")
        master_btn.setStyleSheet("QPushButton { background:#DDE8F4; font-weight:600; text-align:left; padding:16px; }")
        lay.addWidget(current_btn); lay.addWidget(master_btn)
        close_btn = QPushButton(self._t("Fermer")); lay.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignRight)
        action = {"kind": None}
        current_btn.clicked.connect(lambda: (action.__setitem__("kind", "collection"), chooser.accept()))
        master_btn.clicked.connect(lambda: (action.__setitem__("kind", "master"), chooser.accept()))
        close_btn.clicked.connect(chooser.reject)
        if chooser.exec() != QDialog.DialogCode.Accepted:
            return
        if action["kind"] == "master":
            self._open_master_model_workshop()
            return
        self._open_current_collection_workshop()

    def _open_current_collection_workshop(self) -> None:
        if self.collection is None:
            return
        dialog = ModelDialog(self._database_path, self.collection, self, language=self.language, workshop_mode="collection")
        dialog.exec()
        model_was_saved = bool(getattr(dialog, "model_was_saved", False))
        try:
            dialog.deleteLater(); QCoreApplication.sendPostedEvents(dialog, QEvent.Type.DeferredDelete)
        except Exception:
            pass
        if not model_was_saved:
            return
        record_window = self._live_record_window()
        if record_window is not None:
            try:
                record_window.close(); record_window.deleteLater()
            except Exception:
                pass
            self.record_window = None

    def _open_master_model_workshop(self) -> None:
        """Gestion arborescente des modèles de fiches : maîtres protégés + modèles personnels."""
        from core.paths import WORKSPACE
        import sqlite3

        official = Path(__file__).resolve().parents[1] / "ModelesOfficiels"
        root = Path(WORKSPACE) / "Bibliothèques" / "Atelier des modèles de fiches"
        root.mkdir(parents=True, exist_ok=True)
        masters = [
            ("Minéraux", "minerals.db"), ("Sables", "geology_samples.db"),
            ("Fossiles", "fossils.db"), ("Timbres", "stamps.db"),
            ("Cartes postales", "postcards.db"), ("Monnaies - Médailles - Jetons", "coins.db"),
            ("Objets de collection", "objects.db"), ("Livres - Documents", "books.db"),
            ("Étiquettes - Documents graphiques", "labels.db"), ("Vierge", "blank.db"),
        ]
        master_by_name = {label: filename for label, filename in masters}
        # Les dix dossiers existent réellement afin de pouvoir recevoir sous-dossiers et modèles personnels.
        for label, _filename in masters:
            (root / label).mkdir(parents=True, exist_ok=True)

        dlg = QDialog(self)
        dlg.setWindowTitle(self._t("Gestion des modèles de fiches"))
        dlg.resize(900, 610)
        lay = QVBoxLayout(dlg); lay.setContentsMargins(18,16,18,16); lay.setSpacing(10)
        title = QLabel(self._t("Choisissez un modèle à ouvrir ou organisez vos modèles personnels."))
        f=title.font(); f.setPointSize(f.pointSize()+3); f.setBold(True); title.setFont(f); lay.addWidget(title)
        hint = QLabel(self._t("Les 10 dossiers maîtres G-Skol et leur modèle maître sont protégés. Vous pouvez y créer des sous-dossiers et des modèles personnels. Vous pouvez aussi créer vos propres dossiers à la racine."))
        hint.setWordWrap(True); lay.addWidget(hint)
        tree=QTreeWidget(); tree.setHeaderLabels([self._t("Modèles de fiches"), self._t("Type")]); tree.setColumnWidth(0,610); lay.addWidget(tree,1)

        def add_dir(parent_item, path: Path, native_root=False):
            # Même langage visuel que l’écran « Ouvrir une collection » :
            # dossier jaune Windows pour tous les dossiers de modèles.
            folder_label = self._t(path.name) if native_root else path.name
            item=QTreeWidgetItem(parent_item, ["📁 " + folder_label, self._t("Dossier maître") if native_root else self._t("Dossier personnel")])
            item.setData(0, Qt.ItemDataRole.UserRole, ("master_folder" if native_root else "folder", str(path)))
            if native_root:
                fn=master_by_name[path.name]
                mi=QTreeWidgetItem(item,["📄 " + self._t("Modèle maître"), self._t("Protégé")]); mi.setData(0,Qt.ItemDataRole.UserRole,("master",str(official/fn),path.name))
            for child in sorted(path.iterdir(), key=lambda x:(not x.is_dir(),x.name.casefold())):
                if child.is_dir(): add_dir(item,child,False)
                elif child.suffix.lower()==".db":
                    ci=QTreeWidgetItem(item,["📄 " + child.stem,self._t("Modèle personnel")]); ci.setData(0,Qt.ItemDataRole.UserRole,("model",str(child)))
            return item

        def refresh(select_path=None):
            tree.clear()
            for label,_ in masters: add_dir(tree,root/label,True)
            native={label for label,_ in masters}
            for child in sorted(root.iterdir(),key=lambda x:x.name.casefold()):
                if child.is_dir() and child.name not in native: add_dir(tree,child,False)
            tree.expandToDepth(0)
            if select_path:
                it=QTreeWidgetItemIterator(tree)
                while it.value():
                    d=it.value().data(0,Qt.ItemDataRole.UserRole)
                    if d and len(d)>1 and str(d[1])==str(select_path): tree.setCurrentItem(it.value()); break
                    it += 1

        # Import local évitant d'alourdir les imports globaux.
        from PySide6.QtWidgets import QTreeWidgetItemIterator
        refresh()
        buttons=QHBoxLayout()
        open_b=QPushButton(self._t("Ouvrir")); new_model_b=QPushButton(self._t("Nouveau modèle…")); new_folder_b=QPushButton(self._t("Nouveau dossier…"))
        rename_b=QPushButton(self._t("Renommer…")); move_b=QPushButton(self._t("Déplacer vers…")); delete_b=QPushButton(self._t("Supprimer…")); close_b=QPushButton(self._t("Fermer"))
        for b in (open_b,new_model_b,new_folder_b,rename_b,move_b,delete_b): buttons.addWidget(b)
        buttons.addStretch(1); buttons.addWidget(close_b); lay.addLayout(buttons)

        def data():
            i=tree.currentItem(); return i.data(0,Qt.ItemDataRole.UserRole) if i else None
        def update_buttons():
            d=data(); kind=d[0] if d else ""
            open_b.setEnabled(kind in ("master","model")); new_model_b.setEnabled(kind in ("master_folder","folder")); new_folder_b.setEnabled(kind in ("master_folder","folder") or not d)
            rename_b.setEnabled(kind in ("folder","model")); move_b.setEnabled(kind in ("folder","model")); delete_b.setEnabled(kind in ("folder","model"))
        tree.currentItemChanged.connect(lambda *_:update_buttons()); update_buttons()

        def open_db(path, master_label=None):
            db_path=Path(path)
            if master_label:
                box=QMessageBox(QMessageBox.Icon.Warning,self._t("Modification d’un modèle maître"),self._t("Vous allez modifier un modèle maître G-Skol. Les modifications seront utilisées automatiquement pour les futures collections de ce type. Les collections déjà créées ne seront pas modifiées.\n\nVoulez-vous continuer ?"),parent=dlg)
                yes_b=box.addButton(self._t("Oui"),QMessageBox.ButtonRole.YesRole); no_b=box.addButton(self._t("Non"),QMessageBox.ButtonRole.NoRole)
                box.setDefaultButton(no_b); box.exec()
                if box.clickedButton() is not yes_b:return
            con=sqlite3.connect(str(db_path)); con.row_factory=sqlite3.Row
            try:r=con.execute("SELECT * FROM collections ORDER BY id LIMIT 1").fetchone(); collection=dict(r) if r else None
            finally:con.close()
            if not collection: QMessageBox.critical(dlg,self._t("Modèle invalide"),self._t("Ce modèle ne contient aucune collection.")); return
            editor=ModelDialog(db_path,collection,self,language=self.language,workshop_mode="master" if master_label else "template")
            editor.exec(); editor.deleteLater()
        def do_open():
            d=data();
            if not d:return
            if d[0]=="master": open_db(d[1],d[2])
            elif d[0]=="model": open_db(d[1])
        open_b.clicked.connect(do_open); tree.itemDoubleClicked.connect(lambda *_:do_open())

        def selected_folder():
            d=data()
            if not d:return root
            if d[0] in ("master_folder","folder"):return Path(d[1])
            return Path(d[1]).parent
        def do_new_folder():
            parent=selected_folder(); name,ok=QInputDialog.getText(dlg,self._t("Nouveau dossier"),self._t("Nom du dossier :"))
            if not ok or not name.strip():return
            target=parent/name.strip()
            if target.exists(): QMessageBox.warning(dlg,self._t("Nom déjà utilisé"),self._t("Un dossier ou modèle porte déjà ce nom.")); return
            target.mkdir(); refresh(target)
        new_folder_b.clicked.connect(do_new_folder)
        def do_new_model():
            parent=selected_folder(); name,ok=QInputDialog.getText(dlg,self._t("Nouveau modèle"),self._t("Nom du modèle :"))
            if not ok or not name.strip():return
            target=parent/(name.strip()+".db")
            if target.exists(): QMessageBox.warning(dlg,self._t("Nom déjà utilisé"),self._t("Un dossier ou modèle porte déjà ce nom.")); return
            # Dans un dossier maître, le nouveau modèle part de son maître ; ailleurs, d'un modèle vierge.
            try: rel=parent.relative_to(root); top=rel.parts[0] if rel.parts else ""
            except ValueError: top=""
            source=official/master_by_name.get(top,"blank.db")
            shutil.copy2(source,target); refresh(target)
        new_model_b.clicked.connect(do_new_model)
        def do_rename():
            d=data();
            if not d or d[0] not in ("folder","model"):return
            old=Path(d[1]); base=old.stem if old.is_file() else old.name
            name,ok=QInputDialog.getText(dlg,self._t("Renommer"),self._t("Nouveau nom :"),text=base)
            if not ok or not name.strip():return
            target=old.with_name(name.strip()+old.suffix if old.is_file() else name.strip())
            if target.exists(): QMessageBox.warning(dlg,self._t("Nom déjà utilisé"),self._t("Un dossier ou modèle porte déjà ce nom.")); return
            old.rename(target); refresh(target)
        rename_b.clicked.connect(do_rename)
        def choose_destination(exclude=None):
            choices=[]
            for p in [root]+[x for x in root.rglob("*") if x.is_dir()]:
                if exclude and (p==exclude or exclude in p.parents): continue
                rel="/" if p==root else str(p.relative_to(root))
                choices.append((rel,p))
            labels=[x[0] for x in choices]; val,ok=QInputDialog.getItem(dlg,self._t("Déplacer vers"),self._t("Dossier de destination :"),labels,0,False)
            if not ok:return None
            return dict(choices).get(val)
        def do_move():
            d=data();
            if not d or d[0] not in ("folder","model"):return
            old=Path(d[1]); dest=choose_destination(old if old.is_dir() else None)
            if not dest:return
            target=dest/old.name
            if target.exists(): QMessageBox.warning(dlg,self._t("Nom déjà utilisé"),self._t("Un dossier ou modèle porte déjà ce nom dans la destination.")); return
            shutil.move(str(old),str(target)); refresh(target)
        move_b.clicked.connect(do_move)
        def do_delete():
            d=data();
            if not d or d[0] not in ("folder","model"):return
            p=Path(d[1])
            box=QMessageBox(QMessageBox.Icon.Question,self._t("Supprimer"),self._t("Supprimer définitivement « {0} » ?").format(p.stem if p.is_file() else p.name),parent=dlg)
            yes_b=box.addButton(self._t("Oui"),QMessageBox.ButtonRole.YesRole); no_b=box.addButton(self._t("Non"),QMessageBox.ButtonRole.NoRole)
            box.setDefaultButton(no_b); box.exec()
            if box.clickedButton() is not yes_b:return
            if p.is_dir(): shutil.rmtree(p)
            else:p.unlink()
            refresh()
        delete_b.clicked.connect(do_delete); close_b.clicked.connect(dlg.reject)
        dlg.exec()

    def open_referentials(self, _feature_name: str | None = None) -> None:
        if self.collection is None:
            QMessageBox.information(
                self,
                self._t("Aucune collection ouverte"),
                self._t("Ouvrez ou créez d'abord une collection avant de gérer ses référentiels."),
            )
            return
        dialog = ReferentialDialog(self.startup, self.collection, self)
        dialog.exec()
        if self.record_window is not None:
            self.record_window.reload_all_referentials()

    def cards_placeholder(self, feature_name: str) -> None:
        QMessageBox.information(
            self,
            feature_name,
            f"Le module « {feature_name} » est prêt à recevoir sa prochaine brique.",
        )

    def open_statistics(self, _feature_name: str | None = None) -> None:
        if self.collection is None:
            QMessageBox.information(self, self._t("Aucune collection ouverte"), self._t("Ouvrez d’abord une collection."))
            return
        dialog = DashboardDialog(self._database_path, self.collection, self, self.language)
        dialog.exec()
        dialog.deleteLater()

    def open_settings(self, _feature_name: str | None = None) -> None:
        dialog = SettingsDialog(self.catalog_startup, self._database_path if self.collection else None,
                                self.collection, self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.collection_color_changed:
            # Appliquer immédiatement la nouvelle couleur, sans redémarrer G-Skol.
            self._apply_style()
            record_window = self._live_record_window()
            if record_window is not None:
                try:
                    record_window._apply_style()
                    record_window.update()
                except Exception:
                    pass
            # Les autres écrans relisent le thème à leur prochaine ouverture.
            self.update()
        dialog.deleteLater()

    def show_about(self) -> None:
        language = str(self.language or "fr").lower()[:2]
        texts = {
            "fr": ("Créé par FX", "© 2026 FX — Tous droits réservés", "Freeware — utilisation et redistribution gratuites", "G-Skol est un logiciel gratuit (freeware). Son utilisation et sa redistribution à titre gratuit sont autorisées à condition de conserver la mention de l’auteur et les mentions de propriété intellectuelle.\n\nToute vente, commercialisation ou exploitation commerciale de G-Skol est interdite sans l’autorisation écrite préalable de son auteur."),
            "en": ("Created by FX", "© 2026 FX — All rights reserved", "Freeware — free use and redistribution", "G-Skol is freeware. Free use and redistribution are permitted provided the author's credit and copyright notices are retained.\n\nSale or commercial exploitation of G-Skol is prohibited without the author's prior written permission."),
            "de": ("Erstellt von FX", "© 2026 FX — Alle Rechte vorbehalten", "Freeware — kostenlose Nutzung und Weitergabe", "G-Skol ist Freeware. Kostenlose Nutzung und Weitergabe sind gestattet, sofern der Urheberhinweis und die Copyright-Vermerke erhalten bleiben.\n\nVerkauf oder kommerzielle Nutzung von G-Skol sind ohne vorherige schriftliche Zustimmung des Urhebers untersagt."),
        }
        created, rights, freeware, warning = texts.get(language, texts["fr"])
        dialog = QMessageBox(self)
        dialog.setWindowTitle(self._t("À propos de G-Skol"))
        dialog.setIcon(QMessageBox.Icon.Information)
        dialog.setText(f"{APP_NAME}\n{APP_VERSION}\n\n{ABOUT_TAGLINE.strip() or self._t('Gestion de collections.')}\n{created}\n{rights}\n{freeware}")
        warning_button = dialog.addButton(self._t("Avertissement"), QMessageBox.ButtonRole.ActionRole)
        dialog.addButton(QMessageBox.StandardButton.Ok)
        dialog.exec()
        if dialog.clickedButton() is warning_button:
            QMessageBox.information(self, self._t("Avertissement"), warning)

    def _t(self, text: str) -> str:
        return tr(text, self.language)

    def _language_name(self) -> str:
        lang = str(self.language or "fr").lower()
        if lang.startswith("de"):
            return "Deutsch"
        if lang.startswith("en"):
            return "English"
        return "Français"

    def choose_language(self) -> None:
        dialog = QDialog(self)
        layout = QVBoxLayout(dialog)
        language_label = QLabel()
        layout.addWidget(language_label)
        combo = QComboBox()
        # Langues classées par ordre alphabétique de leur nom affiché.
        languages = [("Deutsch", "de"), ("English", "en"), ("Français", "fr")]
        for label, code in sorted(languages, key=lambda item: item[0].casefold()):
            combo.addItem(label, code)
        current = str(self.language or "fr").lower()[:2]
        idx = combo.findData(current)
        combo.setCurrentIndex(idx if idx >= 0 else combo.findData("fr"))
        layout.addWidget(combo)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)

        def refresh_language_dialog(*_args) -> None:
            # La petite fenêtre se traduit immédiatement selon la langue pointée
            # dans la liste, avant même que l'utilisateur ne valide son choix.
            selected_language = str(combo.currentData() or "fr")
            dialog.setWindowTitle(tr("Langue de l’interface", selected_language))
            language_label.setText(tr("Choisissez la langue de G-Skol :", selected_language))
            ok_button.setText("OK")
            cancel_button.setText(tr("Annuler", selected_language))
            dialog.adjustSize()

        combo.currentIndexChanged.connect(refresh_language_dialog)
        refresh_language_dialog()
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        selected = str(combo.currentData() or "fr")
        if selected == self.language:
            return
        self.language = selected
        self.catalog_startup.settings.language = selected
        self.catalog_startup.settings.save()
        # Recompose uniquement l'accueil et les menus : les fenêtres métier déjà
        # ouvertes restent intactes et prendront la langue lors de leur prochaine ouverture.
        self.menuBar().clear()
        self._build_menu()
        old = self.centralWidget()
        if old is not None:
            old.setParent(None)
            old.deleteLater()
        self._build_center()
        self._apply_style()
        self._update_collection_action_buttons()
        if self.collection is not None:
            try:
                self._update_collection_labels()
            except Exception:
                pass
        self.show_collection_space()
