#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from core.calculation_formula import normalize as normalize_calculation_formula
from core.collection_folders import collection_display_name

import time

from datetime import datetime
import ast
import math
import re

from PySide6.QtCore import QByteArray, QBuffer, QEvent, QTimer, QIODevice, QSignalBlocker, QSize, QRect, QStringListModel, Qt, Signal, QUrl, QObject
from PySide6.QtGui import QAction, QColor, QDesktopServices, QFont, QIcon, QImage, QImageReader, QKeySequence, QPainter, QPen, QPixmap, QTextBlockFormat, QTextCursor, QKeyEvent, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QCompleter,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSizePolicy,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.record_manager import RecordManager
from core.layout_geometry import BLOCK_MIN_HEIGHT, DEFAULT_FIELD_GEOMETRY
from core.layout_engine import DISPLAY_SCALE, field_outer_rect, field_parts, scaled
from core.field_catalog import FIELD_BY_KEY, REFERENTIAL_BY_FIELD
from core.model_manager import ModelManager
from core.referential_manager import ReferentialManager
from core.i18n import tr, display_native_value, canonical_native_value
from ui.shared_field import SharedFieldFrame
from ui.form_surface import (
    FormSurface, apply_group_style, detach_surface_groups, canonical_group_rects,
)


# 018.4.4.1.2.9 — constantes locales du modèle utilisées pour l'ordre de tabulation.
MODEL_BLOCKS = ("Identification", "Localisation", "Aspect", "Acquisition", "Collection")

GROUPS = (
    ("Bandeau", ("record_number", "mineral_name", "mineral_2", "mineral_3", "record_state")),
    ("Identification", (
        "mineral_class", "chemical_formula", "crystal_system", "luminescence",
        "luminescence_intensity", "fluorescence_color", "internet_link", "photo_data",
    )),
    ("Localisation", (
        "site_name", "deposit", "category", "site_internet_link",
        "department", "region", "country",
    )),
    ("Aspect", (
        "growth", "specimen_shape", "specimen_color", "quality",
        "type_locality", "minimum_magnification", "description",
    )),
    ("Collection", ("box_type", "box_count", "price", "total_cost")),
    ("Acquisition", ("contact", "acquisition_date", "origin", "place")),
)


class RecordPositionButton(QPushButton):
    """Compteur cliquable : seuls les nombres sont mis en évidence."""

    _counter_re = re.compile(r"^(Fiche|Résultat)\s+(\d+)\s+sur\s+(\d+)$")
    _accent = QColor("#9A3D2D")

    def paintEvent(self, event) -> None:
        match = self._counter_re.match(self.text())
        if not match:
            super().paintEvent(event)
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        normal_font = QFont(self.font())
        bold_font = QFont(normal_font)
        bold_font.setBold(True)

        parts = (
            (f"{match.group(1)} ", normal_font, self.palette().buttonText().color()),
            (match.group(2), bold_font, self._accent),
            (" sur ", normal_font, self.palette().buttonText().color()),
            (match.group(3), bold_font, self._accent),
        )
        widths = []
        for txt, font, _color in parts:
            painter.setFont(font)
            widths.append(painter.fontMetrics().horizontalAdvance(txt))
        x = (self.width() - sum(widths)) / 2.0
        baseline = (self.height() + painter.fontMetrics().ascent() - painter.fontMetrics().descent()) / 2.0
        for (txt, font, color), width in zip(parts, widths):
            painter.setFont(font)
            painter.setPen(color)
            painter.drawText(int(x), int(baseline), txt)
            x += width



class RuntimeFormCanvas(QWidget):
    """Canvas de saisie : même géométrie que l'Atelier, sans grille ni lasso."""
    def __init__(self, block_name: str, owner, parent=None) -> None:
        super().__init__(parent)
        self.block_name = block_name
        self.owner = owner
        self.setMinimumWidth(0)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )



class ReferentialLineEdit(QLineEdit):
    """Zone de saisie qui réserve Entrée à la validation MM3.

    QCompleter et QComboBox peuvent consommer la touche Entrée avant que la
    fenêtre ne la reçoive. Cette sous-classe intercepte donc la touche au
    niveau le plus bas et émet un signal explicite.
    """

    enterPressed = Signal()

    def keyPressEvent(self, event) -> None:  # noqa: N802 (Qt convention)
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            # 23.9.2.5 — une seule autorité pour Entrée. Les anciens signaux
            # enterPressed restent disponibles en secours, mais la Fiche MM3
            # reçoit directement le widget source afin de valider puis avancer
            # dans la chaîne globale tab_position.
            owner = self.window()
            handler = getattr(owner, "_validate_enter_and_continue", None)
            if callable(handler) and handler(self):
                event.accept()
                return
            self.enterPressed.emit()
            event.accept()
            return
        if event.key() in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete):
            self.setProperty("_mm3_skip_inline_once", True)
            # Une terminaison sélectionnée effacée par l'utilisateur ne doit
            # pas être réinjectée par le completer lors de la validation.
            if (self.property("_gskol_species_field") or self.property("_gskol_site_field") or self.property("_gskol_referential_field")) and self.hasSelectedText():
                self.setProperty("_gskol_species_truncated", True)
        elif (self.property("_gskol_species_field") or self.property("_gskol_site_field") or self.property("_gskol_referential_field")) and event.text() and event.text().isprintable():
            self.setProperty("_gskol_species_truncated", False)
        super().keyPressEvent(event)


class PhotoLabel(QLabel):
    """Cadre photo MM3 : clic, collage, glisser-déposer et menu contextuel."""

    addRequested = Signal()
    copyRequested = Signal()
    pasteRequested = Signal()
    menuRequested = Signal(object)
    imageDropped = Signal(object)
    resized = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setWordWrap(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        # Le clic gauche ne lance aucune commande : comme pour les autres
        # champs de la fiche, il sélectionne simplement le cadre Photo.
        # Une fois le cadre sélectionné, Ctrl+V colle l'image du Presse-papiers.
        if event.button() == Qt.MouseButton.LeftButton:
            self.setFocus(Qt.FocusReason.MouseFocusReason)
            event.accept()
            return
        # 11.4.22 — le premier cadre Photo historique peut être reparenté dans
        # la surface commune. Sur Windows/Qt, son ContextMenuEvent pouvait alors
        # ne jamais parvenir au PhotoLabel. On déclenche donc le même menu dès
        # le bouton droit pressé, comme pour les cadres Photo supplémentaires.
        if event.button() == Qt.MouseButton.RightButton:
            self.setFocus(Qt.FocusReason.MouseFocusReason)
            try:
                pos = event.globalPosition().toPoint()
            except Exception:
                pos = event.globalPos()
            self.menuRequested.emit(pos)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        # Même règle que le clic simple : le bouton gauche ne déclenche
        # aucune commande sur le cadre Photo.
        if event.button() == Qt.MouseButton.LeftButton:
            self.setFocus(Qt.FocusReason.MouseFocusReason)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event) -> None:  # noqa: N802
        self.menuRequested.emit(event.globalPos())
        event.accept()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        # Même comportement que les autres champs MM3 :
        # Ctrl+C copie la photo sélectionnée, Ctrl+V colle la photo
        # actuellement présente dans le Presse-papiers Windows.
        if event.matches(QKeySequence.StandardKey.Copy):
            self.copyRequested.emit()
            event.accept()
            return
        if event.matches(QKeySequence.StandardKey.Paste):
            self.pasteRequested.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        mime = event.mimeData()
        if mime.hasImage() or mime.hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:  # noqa: N802
        mime = event.mimeData()
        image = QImage()
        if mime.hasImage():
            candidate = mime.imageData()
            if isinstance(candidate, QImage):
                image = candidate
            elif isinstance(candidate, QPixmap):
                image = candidate.toImage()
        elif mime.hasUrls():
            for url in mime.urls():
                if url.isLocalFile():
                    image = QImage(url.toLocalFile())
                    if not image.isNull():
                        break
        if not image.isNull():
            self.imageDropped.emit(image)
            event.acceptProposedAction()
        else:
            event.ignore()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self.resized.emit()


class RecordWindow(QMainWindow):
    # 23.9.3.5.6 — signal de cycle de vie : MainWindow doit oublier
    # immédiatement une Fiche qui vient d'accepter sa fermeture.
    windowClosed = Signal()
    recordSaved = Signal(int)
    recordDraftChanged = Signal(int, object)

    """Première fiche de données réelle de MM3."""

    STATES = ["OK", "Vérifier", "Libre"]

    def _t(self, text: str) -> str:
        return tr(text, self.language)
    def _dv(self, value: str) -> str:
        return display_native_value(value, self.language)

    def _cv(self, value: str) -> str:
        return canonical_native_value(value, self.language)

    def _state_canonical(self, value: str) -> str:
        """Convertit uniquement les trois états système, sans toucher aux autres référentiels."""
        text = str(value or "").strip()
        states = {
            "ok": "OK",
            "prüfen": "Vérifier",
            "vérifier": "Vérifier",
            "à vérifier": "Vérifier",
            "a vérifier": "Vérifier",
            "valider": "Vérifier",
            "check": "Vérifier",
            "frei": "Libre",
            "free": "Libre",
            "libre": "Libre",
        }
        return states.get(text.casefold(), self._cv(text))

    def _state_display(self, value: str) -> str:
        canonical = self._state_canonical(value)
        if str(self.language or "").lower().startswith("de"):
            return {"OK": "OK", "Vérifier": "Prüfen", "Libre": "Frei"}.get(canonical, self._dv(canonical))
        return self._dv(canonical)

    def _bool_display(self, value: str) -> str:
        native = str(value or "").strip().casefold()
        if str(self.language or "fr").lower().startswith("en"):
            return "Yes" if native in {"oui", "yes"} else "No"
        return "Oui" if native in {"oui", "yes"} else "Non"


    def __init__(self, startup, collection: dict, parent=None, preview_mode: bool = False) -> None:
        _open_t0 = time.perf_counter()
        _open_last = _open_t0

        def _mark(label: str) -> None:
            nonlocal _open_last
            now = time.perf_counter()
            try:
                startup.logger.info(
                    f"PERF Fiche [{collection.get('name', '?')}] {label}: "
                    f"+{now - _open_last:.3f}s (total {now - _open_t0:.3f}s)"
                )
            except Exception:
                pass
            try:
                from performance_diagnostic import write as _perf_write
                _perf_write("INIT FICHE %-35s +%.3f s | total %.3f s" % (label, now - _open_last, now - _open_t0))
            except Exception:
                pass
            _open_last = now

        super().__init__(parent)
        self.startup = startup
        self.language = getattr(getattr(startup, "settings", None), "language", "fr") or "fr"
        self.collection = collection
        self.preview_mode = bool(preview_mode)
        self.manager = RecordManager(startup.database.database_path)
        self.model_manager = ModelManager(startup.database.database_path)
        # 23.9.3.6.0 — relations Maître / Relié à propres à la collection.
        _mark("initialisation gestionnaires")
        self._field_masters: set[str] = set(
            self.model_manager.field_masters(int(collection["id"]))
        )
        self._field_links: dict[str, str] = dict(
            self.model_manager.field_links(int(collection["id"]))
        )
        # Valeurs Maître présentes dans une liste mais ne disposant d’aucune
        # ligne relationnelle connue. Elles passent en mode « saisie libre » :
        # les anciens champs Reliés sont vidés une seule fois, puis l’utilisateur
        # peut renseigner les nouvelles données sans que MM3 les efface.
        self._unresolved_relation_masters: dict[str, str] = {}
        # Le rattrapage global des anciennes fiches est volontairement
        # NON exécuté à chaque ouverture de Fiche : sur un gros référentiel
        # multi-colonnes il pouvait ajouter plusieurs secondes. Il reste exécuté
        # lorsqu'un modèle / une liaison est réellement modifié.
        self._relation_runtime_guard = False
        # 39.32.11.7.7 — plusieurs chemins de construction demandaient la même
        # activation lourde de la surface Atelier/Fiche via QTimer.singleShot(0).
        # Au premier affichage, ces demandes s'empilaient dans la boucle Qt et
        # pouvaient rejouer plusieurs fois tout le reparentage/style des champs.
        # On les fusionne désormais : une seule activation par tour de boucle.
        self._runtime_surface_activation_pending = False
        # 23.9.3.6.4 — demandé lorsqu'un modèle vient d'être sauvegardé.
        # L'application réelle est faite à la FIN de la reconstruction graphique.
        self._apply_relations_after_model_refresh = False
        _mark("relations maître/relié")
        self.referentials = ReferentialManager(startup.database.database_path)
        _mark("création gestionnaire référentiels")
        self.referentials.ensure_defaults(int(collection["id"]))
        _mark("référentiels / migrations")
        self.records: list[dict] = []
        self.position = -1
        self.dirty = False
        # 11.7.70.13 — valeur d'entrée du champ actif pour Échap.
        # Les champs Reliés peuvent écrire immédiatement une valeur vide dans
        # le référentiel ; il faut donc conserver une copie indépendante de
        # la valeur affichée AVANT toute modification.
        self._escape_focus_key = None
        self._escape_focus_value = None
        self._extra_photo_widgets = {}
        self._large_photo_slots = set()
        self._extra_photo_states = {}
        self._quick_search_positions: list[int] = []
        self._quick_search_cursor = -1
        self._quick_search_label = ""
        self._loading = False
        self._name_declined_for_value = ""
        self._mineral2_declined_for_value = ""
        self._mineral3_declined_for_value = ""
        self._class_declined_for_value = ""
        self._crystal_declined_for_value = ""
        self._luminescence_declined_for_value = ""
        self._intensity_declined_for_value = ""
        self._fluorescence_color_declined_for_value = ""
        self._site_declined_for_value = ""
        self._department_declined_for_value = ""
        self._region_declined_for_value = ""
        self._country_declined_for_value = ""
        self._box_type_declined_for_value = ""
        self._category_declined_for_value = ""
        self._contact_declined_for_value = ""
        self._shape_declined_for_value = ""
        self._color_declined_for_value = ""
        self._quality_declined_for_value = ""
        self._state_declined_for_value = ""
        self._minimum_magnification_declined_for_value = ""
        self._growth_declined_for_value = ""
        self._origin_declined_for_value = ""
        self._place_declined_for_value = ""
        self._global_filter_installed = False
        self._photo_data: bytes | None = None
        self._virtual_new_record = False
        self._photo_format = ""
        self._photo_image = QImage()
        # Snapshot temporaire de la dernière fiche vidée. Il n'est jamais écrit
        # dans un fichier séparé : il vit uniquement pendant la session courante.
        self._restore_snapshot: dict | None = None
        self._restore_record_id: int | None = None

        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.setWindowTitle((self._t("Aperçu temporaire — ") if self.preview_mode else self._t("Fiches — ")) + collection_display_name(collection, self.language))
        display_menu = self.menuBar().addMenu(self._t("Affichage"))
        self.default_size_action = QAction(self._t("Taille par défaut de la fiche"), self)
        self.default_size_action.setToolTip(
            self._t("Rétablir la taille compacte MM3 et recentrer la fiche sur l’écran actuel.")
        )
        self.default_size_action.triggered.connect(self.reset_window_geometry)
        display_menu.addAction(self.default_size_action)

        # Taille compacte par défaut, validée sur écran portable 16 pouces.
        # Elle reste entièrement redimensionnable par l'utilisateur.
        self.resize(1280, 820)
        self.setMinimumSize(760, 700)

        self._preload_opening_referentials()
        _mark("préchargement listes")
        self._build_ui()

        # 39.32.11.7.32 — navigation Fiche indépendante du widget ayant le focus.
        # Le filtre global QApplication a été volontairement retiré pour les
        # performances ; des QShortcut de fenêtre garantissent désormais que
        # Page précédente / Page suivante restent actives partout dans la Fiche.
        self.page_previous_shortcut = QShortcut(QKeySequence(Qt.Key.Key_PageUp), self)
        self.page_previous_shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        self.page_previous_shortcut.activated.connect(self.go_previous)
        self.page_next_shortcut = QShortcut(QKeySequence(Qt.Key.Key_PageDown), self)
        self.page_next_shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        self.page_next_shortcut.activated.connect(self.go_next)

        # Le modèle peut créer d'autres QComboBox dynamiques que les champs
        # historiques. Les traiter tous une fois, après construction complète.
        for combo in self.findChildren(QComboBox):
            self._style_combo_popup_scrollbars(combo)
        _mark("construction interface")
        # apply_collection_model(), appelé à la fin de _build_ui(), a déjà
        # appliqué le style complet de la Fiche. Ne pas le recalculer une 2e fois.
        self.reload_records()
        if not self.preview_mode:
            try:
                prefs = self.model_manager.collection_preferences(int(self.collection["id"]))
                if prefs["record_opening"] == "last" and prefs["last_record_id"] is not None:
                    self.select_record_by_id(int(prefs["last_record_id"]))
                elif prefs["record_opening"] == "first" and self.records:
                    self.position = 0
                    self._refresh_display()
            except Exception:
                pass
        _mark("chargement première fiche")
        self._restore_window_geometry()
        _mark("géométrie / fin ouverture")

    def _preload_opening_referentials(self) -> None:
        """Charge une fois les référentiels courants avant de construire les widgets."""
        cid = int(self.collection["id"])
        codes = (
            "mineral_name", "mineral_class", "crystal_system",
            "luminescence", "luminescence_intensity", "fluorescence_color",
            "site_name", "department", "region", "country",
            "specimen_shape", "specimen_color", "quality",
            "record_state", "minimum_magnification", "growth",
            "origin", "place", "box_type", "category", "contact",
        )
        for code in codes:
            try:
                self.referentials.list_values(cid, code, active_only=True)
            except Exception:
                pass

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("recordRoot")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(5)

        if self.preview_mode:
            preview_banner = QLabel(
                "MODE APERÇU — COLLECTION TEMPORAIRE\n"
                "Vous pouvez modifier librement cette copie pour tester le modèle. "
                "La collection originale ne sera pas modifiée."
            )
            preview_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
            preview_banner.setWordWrap(True)
            preview_banner.setStyleSheet(
                "QLabel { background: #FFE39A; color: #8A2E12; border: 2px solid #D66A24; "
                "padding: 8px; font-weight: 700; font-size: 13px; }"
            )
            layout.addWidget(preview_banner)

        header = QHBoxLayout()
        self.title_label = QLabel(f"{self._t('Fiches — ')}{collection_display_name(self.collection, self.language)}")
        self.title_label.setObjectName("recordTitle")
        self.position_label = RecordPositionButton(self._t("Aucune fiche"))
        self.position_label.setObjectName("positionLabel")
        self.position_label.setFlat(True)
        self.position_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.position_label.setToolTip(self._t("Cliquer pour aller directement à un N° de fiche"))
        self.position_label.clicked.connect(self.go_to_record_number)
        header.addWidget(self.title_label)

        self.quick_search_button = QPushButton("🔍")
        self.quick_search_button.setToolTip(self._t("Rechercher rapidement une fiche"))
        self.quick_search_button.setFixedWidth(38)
        self.quick_search_button.clicked.connect(self.open_quick_search)

        self.quick_search_clear_button = QPushButton("✕")
        self.quick_search_clear_button.setToolTip(
            self._t("Quitter la recherche et revenir à toute la collection")
        )
        self.quick_search_clear_button.setFixedWidth(34)
        self.quick_search_clear_button.setVisible(False)
        self.quick_search_clear_button.clicked.connect(self.clear_quick_search)

        header.addWidget(self.quick_search_button)
        header.addWidget(self.quick_search_clear_button)
        header.addWidget(self.position_label)
        header.addStretch(1)
        layout.addLayout(header)

        card = QFrame()
        card.setObjectName("recordCard")
        card_layout = QVBoxLayout(card)
        self._record_card_layout = card_layout
        card_layout.setContentsMargins(12, 8, 12, 8)
        card_layout.setSpacing(6)

        # Bandeau supérieur : numéro, champ maître et état de la fiche.
        top_grid = QGridLayout()
        top_grid.setHorizontalSpacing(10)
        top_grid.setVerticalSpacing(3)
        number_caption = QLabel(self._t("N° de fiche"))
        number_caption.setObjectName("fieldCaption")
        self.number_value = QLabel("—")
        self.number_value.setObjectName("recordNumber")
        top_grid.addWidget(number_caption, 0, 0)
        top_grid.addWidget(self.number_value, 0, 1)

        self.name_combo = QComboBox()
        self.name_combo.setEditable(True)
        self.name_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.name_combo.setMaxVisibleItems(24)
        self.name_edit = ReferentialLineEdit(self.name_combo)
        self.name_edit.setProperty("_gskol_species_field", True)
        self.name_combo.setLineEdit(self.name_edit)
        self.name_edit.setPlaceholderText("")
        self.name_edit.setClearButtonEnabled(False)
        self.name_model = QStringListModel(self)
        self.name_combo.setModel(self.name_model)
        self.name_completer = QCompleter(self.name_model, self)
        self.name_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.name_completer.setFilterMode(Qt.MatchFlag.MatchStartsWith)
        self.name_completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.name_edit.setCompleter(self.name_completer)
        self._reload_name_referential()

        self.mineral2_combo, self.mineral2_edit, self.mineral2_model, self.mineral2_completer = self._create_referential_combo(
            "Minéral associé 2", 24
        )
        self.mineral3_combo, self.mineral3_edit, self.mineral3_model, self.mineral3_completer = self._create_referential_combo(
            "Minéral associé 3", 24
        )
        self.mineral2_edit.setProperty("_gskol_species_field", True)
        self.mineral3_edit.setProperty("_gskol_species_field", True)
        self._reload_associated_minerals()

        self.state_combo = QComboBox()
        self.state_combo.setEditable(True)
        self.state_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.state_combo.setMaxVisibleItems(20)
        self.state_edit = ReferentialLineEdit(self.state_combo)
        self.state_combo.setLineEdit(self.state_edit)
        self.state_model = QStringListModel(self)
        self.state_combo.setModel(self.state_model)
        self.state_completer = QCompleter(self.state_model, self)
        self.state_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.state_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.state_completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.state_edit.setCompleter(self.state_completer)
        self._reload_state_referential()

        name_label = QLabel("Nom")
        name_label.setObjectName("masterFieldLabel")
        state_label = QLabel(self._t("Etat de la fiche"))
        top_grid.addWidget(name_label, 0, 2)
        top_grid.addWidget(self.name_combo, 0, 3, 1, 3)
        top_grid.addWidget(state_label, 0, 6)
        top_grid.addWidget(self.state_combo, 0, 7)
        mineral2_label = QLabel("Minéral 2")
        mineral3_label = QLabel("Minéral 3")
        top_grid.addWidget(mineral2_label, 1, 2)
        top_grid.addWidget(self.mineral2_combo, 1, 3)
        top_grid.addWidget(mineral3_label, 1, 4)
        top_grid.addWidget(self.mineral3_combo, 1, 5)
        self.number_value.setMinimumWidth(92)
        self.number_value.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        top_grid.setColumnStretch(3, 3)
        top_grid.setColumnStretch(5, 3)
        top_grid.setColumnStretch(7, 2)
        self.name_combo.setMaximumWidth(500)
        self.name_combo.setObjectName("masterNameCombo")
        self.name_edit.setObjectName("masterNameEdit")
        # 018.4.4.1.2.9 — Nom suit le même standard que Minéral 2 / Minéral 3.
        name_font = QFont(self.mineral2_combo.font())
        name_font.setBold(False)
        self.name_edit.setFont(QFont(self.mineral2_combo.lineEdit().font()))
        self.name_combo.setFont(name_font)
        # Nom suit désormais le même style par défaut que Minéral 2 / Minéral 3.
        self.name_edit.setStyleSheet("")
        mineral2_line_font = QFont(self.mineral2_combo.lineEdit().font())
        mineral2_line_font.setBold(False)
        mineral2_combo_font = QFont(self.mineral2_combo.font())
        mineral2_combo_font.setBold(False)
        self.name_edit.setFont(mineral2_line_font)
        self.name_combo.setFont(mineral2_combo_font)
        if self.name_combo.lineEdit() is not None:
            self.name_combo.lineEdit().setFont(QFont(mineral2_line_font))

        # Le Bandeau devient un vrai groupe visuel afin que fond et cadre
        # enregistrés dans l'Atelier soient reproduits dans la Fiche.
        banner_section = QFrame()
        self.banner_section = banner_section
        banner_section.setObjectName("bannerSection")
        banner_layout = QVBoxLayout(banner_section)
        banner_layout.setContentsMargins(8, 5, 8, 5)
        banner_layout.setSpacing(0)
        banner_layout.addLayout(top_grid)
        card_layout.addWidget(banner_section)

        # Création des autres champs.
        self.class_combo = QComboBox()
        self.class_combo.setEditable(True)
        self.class_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.class_combo.setMaxVisibleItems(24)
        self.class_edit = ReferentialLineEdit(self.class_combo)
        self.class_combo.setLineEdit(self.class_edit)
        self.class_edit.setPlaceholderText("")
        self.class_edit.setClearButtonEnabled(False)
        self.class_model = QStringListModel(self.class_combo)
        self.class_combo.setModel(self.class_model)
        self.class_completer = QCompleter(self.class_model, self.class_combo)
        self.class_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.class_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.class_completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.class_edit.setCompleter(self.class_completer)
        self._reload_class_referential()

        self.formula_edit = QLineEdit()
        self.formula_edit.setPlaceholderText("")
        self.formula_edit.setClearButtonEnabled(False)
        self.formula_edit.setMinimumWidth(285)

        self.internet_link_edit = QLineEdit()
        self.internet_link_edit.setPlaceholderText("")
        self.internet_link_edit.setClearButtonEnabled(False)
        self._prepare_link_editor(self.internet_link_edit)
        self.internet_link_button = QPushButton()
        self.internet_link_button.setObjectName("linkButton")
        self.internet_link_button.setFixedWidth(38)
        self.internet_link_button.setIconSize(QSize(20, 20))
        self._update_internet_link_button("")
        internet_link_widget = QWidget()
        internet_link_layout = QHBoxLayout(internet_link_widget)
        internet_link_layout.setContentsMargins(0, 0, 0, 0)
        internet_link_layout.setSpacing(5)
        internet_link_layout.addWidget(self.internet_link_edit, 1)
        internet_link_layout.addWidget(self.internet_link_button)

        self.crystal_combo = QComboBox()
        self.crystal_combo.setEditable(True)
        self.crystal_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.crystal_combo.setMaxVisibleItems(20)
        self.crystal_edit = ReferentialLineEdit(self.crystal_combo)
        self.crystal_combo.setLineEdit(self.crystal_edit)
        self.crystal_edit.setPlaceholderText("")
        self.crystal_edit.setClearButtonEnabled(False)
        self.crystal_model = QStringListModel(self.crystal_combo)
        self.crystal_combo.setModel(self.crystal_model)
        self.crystal_completer = QCompleter(self.crystal_model, self.crystal_combo)
        self.crystal_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.crystal_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.crystal_completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.crystal_edit.setCompleter(self.crystal_completer)
        self._reload_crystal_referential()

        self.luminescence_combo, self.luminescence_edit, self.luminescence_model, self.luminescence_completer = self._create_referential_combo(
            "Saisissez ou choisissez une luminescence", 16
        )
        self._reload_luminescence_referential()
        self.intensity_combo, self.intensity_edit, self.intensity_model, self.intensity_completer = self._create_referential_combo(
            "Saisissez ou choisissez une intensité", 16
        )
        self._reload_intensity_referential()
        self.fluorescence_color_combo, self.fluorescence_color_edit, self.fluorescence_color_model, self.fluorescence_color_completer = self._create_referential_combo(
            "Saisissez ou choisissez une couleur", 18
        )
        self._reload_fluorescence_color_referential()
        # Dans le bloc Identification, l'effacement se fait naturellement au clavier :
        # les boutons « × » intégrés aux zones de saisie sont donc inutiles et prennent de la place.
        for edit in (self.luminescence_edit, self.intensity_edit, self.fluorescence_color_edit):
            edit.setClearButtonEnabled(False)
        self.site_combo, self.site_edit, self.site_model, self.site_completer = self._create_referential_combo(
            "Saisissez ou choisissez un site", 24
        )
        self._reload_site_referential()
        self.site_edit.setProperty("_gskol_site_field", True)
        self.deposit_edit = QLineEdit()
        self.deposit_edit.setPlaceholderText("")
        self.deposit_edit.setClearButtonEnabled(False)
        self.department_combo, self.department_edit, self.department_model, self.department_completer = self._create_referential_combo(
            "Saisissez ou choisissez un département", 24
        )
        self._reload_department_referential()
        self.region_combo, self.region_edit, self.region_model, self.region_completer = self._create_referential_combo(
            "Saisissez ou choisissez une région", 24
        )
        self._reload_region_referential()
        self.country_combo, self.country_edit, self.country_model, self.country_completer = self._create_referential_combo(
            "Saisissez ou choisissez un pays", 24
        )
        self._reload_country_referential()
        self.site_link_edit = QLineEdit()
        self.site_link_edit.setPlaceholderText("")
        self.site_link_edit.setClearButtonEnabled(False)
        self._prepare_link_editor(self.site_link_edit)
        self.site_link_button = QPushButton()
        self.site_link_button.setObjectName("linkButton")
        self.site_link_button.setFixedWidth(38)
        self.site_link_button.setIconSize(QSize(20, 20))
        self.site_link_button.clicked.connect(self._open_site_link)
        self._update_site_link_button("")
        site_link_widget = QWidget()
        site_link_layout = QHBoxLayout(site_link_widget)
        site_link_layout.setContentsMargins(0, 0, 0, 0)
        site_link_layout.setSpacing(5)
        site_link_layout.addWidget(self.site_link_edit, 1)
        # 11.4.34 — présentation uniforme des champs Lien : l'ancien bouton 🌐
        # du champ « Lien site » n'est plus affiché. Ctrl+clic et le menu
        # contextuel « Ouvrir le lien » restent disponibles comme pour tous les
        # champs personnalisés de type Lien. Le bouton est conservé en interne
        # pour ne pas casser les anciens raccordements du moteur.
        self.site_link_button.hide()
        self.box_type_combo, self.box_type_edit, self.box_type_model, self.box_type_completer = self._create_referential_combo(
            "Saisissez ou choisissez un contenant", 24
        )
        self._reload_box_type_referential()
        self.category_combo, self.category_edit, self.category_model, self.category_completer = self._create_referential_combo(
            "Saisissez ou choisissez une catégorie", 24
        )
        self._reload_category_referential()
        self.contact_combo, self.contact_edit, self.contact_model, self.contact_completer = self._create_referential_combo(
            "Saisissez ou choisissez un contact", 24
        )
        self._reload_contact_referential()

        self.shape_combo, self.shape_edit, self.shape_model, self.shape_completer = self._create_referential_combo(
            "Saisissez ou choisissez une forme", 20
        )
        self._reload_shape_referential()
        self.color_combo, self.color_edit, self.color_model, self.color_completer = self._create_referential_combo(
            "Saisissez ou choisissez une couleur", 20
        )
        self._reload_color_referential()
        self.quality_combo, self.quality_edit, self.quality_model, self.quality_completer = self._create_referential_combo(
            "Saisissez ou choisissez une qualité", 20
        )
        self._reload_quality_referential()
        self.description_edit = QPlainTextEdit()
        self.description_edit.setPlaceholderText("")
        self.description_edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.description_edit.setMinimumHeight(66)
        self.description_edit.setMaximumHeight(78)
        self.description_edit.setTabChangesFocus(True)

        # Champs complémentaires du modèle Micro-minéraux 013.5.
        self.minimum_magnification_combo, self.minimum_magnification_edit, self.minimum_magnification_model, self.minimum_magnification_completer = self._create_referential_combo(
            "Saisissez ou choisissez un grossissement", 20
        )
        self._reload_minimum_magnification_referential()

        self.growth_combo, self.growth_edit, self.growth_model, self.growth_completer = self._create_referential_combo(
            "Saisissez ou choisissez une croissance", 20
        )
        self._reload_growth_referential()

        self.type_locality_combo = QComboBox()
        self.type_locality_combo.setEditable(False)
        self.type_locality_combo.addItems([self._bool_display("Non"), self._bool_display("Oui")])
        self.type_locality_combo.setCurrentText(self._bool_display("Non"))

        self.acquisition_date_edit = QLineEdit()
        self.acquisition_date_edit.setPlaceholderText("")

        self.origin_combo, self.origin_edit, self.origin_model, self.origin_completer = self._create_referential_combo(
            "Saisissez ou choisissez une origine", 20
        )
        self._reload_origin_referential()

        self.place_combo, self.place_edit, self.place_model, self.place_completer = self._create_referential_combo(
            "Saisissez ou choisissez un lieu", 20
        )
        self._reload_place_referential()

        self.box_count_edit = QLineEdit()
        self.box_count_edit.setPlaceholderText("")
        self.price_edit = QLineEdit()
        self.price_edit.setPlaceholderText("")
        self.total_cost_edit = QLineEdit()
        self.total_cost_edit.setPlaceholderText("")
        self.total_cost_edit.setReadOnly(True)
        self.total_cost_edit.setToolTip("Calcul automatique : nombre de pièces × prix unitaire")

        def make_section(title: str) -> tuple[QFrame, QFormLayout]:
            section = QFrame()
            section.setObjectName("dataSection")
            section_box = QVBoxLayout(section)
            section_box.setContentsMargins(8, 5, 8, 6)
            section_box.setSpacing(2)
            caption = QLabel(title)
            caption.setObjectName("sectionTitle")
            section_box.addWidget(caption)
            form = QFormLayout()
            form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            form.setHorizontalSpacing(7)
            form.setVerticalSpacing(2)
            form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
            section_box.addLayout(form)
            return section, form

        # Grille de blocs du modèle par défaut Micro-minéraux.
        # Les blocs ne sont pas figés dans une colonne : ils peuvent occuper
        # plusieurs colonnes et possèdent leur propre grille interne.
        self._record_blocks_host = QWidget()
        self._record_blocks_host.setObjectName("recordBlocksHost")
        blocks = QGridLayout(self._record_blocks_host)
        self._record_blocks_grid = blocks
        blocks.setHorizontalSpacing(9)
        blocks.setVerticalSpacing(8)

        identification = QFrame()
        identification.setObjectName("dataSection")
        identification_box = QVBoxLayout(identification)
        identification_box.setContentsMargins(8, 5, 8, 6)
        identification_box.setSpacing(4)
        ident_title = QLabel("Identification")
        ident_title.setObjectName("sectionTitle")
        identification_box.addWidget(ident_title)

        ident_grid = QGridLayout()
        ident_grid.setHorizontalSpacing(7)
        ident_grid.setVerticalSpacing(3)

        # Colonne interne gauche : Classe / Formule / Système cristallin.
        ident_grid.addWidget(QLabel("Classe"), 0, 0)
        ident_grid.addWidget(self.class_combo, 0, 1)
        ident_grid.addWidget(QLabel("Formule chimique"), 1, 0)
        ident_grid.addWidget(self.formula_edit, 1, 1)
        ident_grid.addWidget(QLabel("Système cristallin"), 2, 0)
        ident_grid.addWidget(self.crystal_combo, 2, 1)

        # Colonne interne droite, légèrement plus large :
        # Luminescence / Intensité / Couleur fluo.
        ident_grid.addWidget(QLabel("Luminescence"), 0, 2)
        ident_grid.addWidget(self.luminescence_combo, 0, 3)
        ident_grid.addWidget(QLabel("Intensité"), 1, 2)
        ident_grid.addWidget(self.intensity_combo, 1, 3)
        ident_grid.addWidget(QLabel("Couleur fluo"), 2, 2)
        ident_grid.addWidget(self.fluorescence_color_combo, 2, 3)

        # Lien commun sur toute la largeur du bloc.
        ident_grid.addWidget(QLabel("Lien"), 3, 0)
        ident_grid.addWidget(internet_link_widget, 3, 1, 1, 3)
        ident_grid.setColumnStretch(1, 4)
        ident_grid.setColumnStretch(3, 5)
        identification_box.addLayout(ident_grid)

        self.photo_label = PhotoLabel()
        self.photo_label.setObjectName("photoPanel")
        # Photo proche du format « Très grandes icônes » de Windows.
        # Le cadre extérieur reste inchangé ; on exploite simplement beaucoup
        # mieux l'espace disponible à l'intérieur.
        self.photo_label.setFixedSize(300, 170)
        self.photo_label.setText("📷\nPhoto")
        self.photo_label.setToolTip(
            "Cliquez pour sélectionner le cadre. Ctrl + C pour copier, Ctrl + V pour coller. "
            "Clic droit pour les options."
        )
        self.photo_label.copyRequested.connect(self._copy_photo)
        self.photo_label.pasteRequested.connect(self._paste_photo)
        self.photo_label.menuRequested.connect(self._show_photo_menu)
        self.photo_label.imageDropped.connect(self._set_photo_from_image)
        self.photo_label.resized.connect(self._refresh_photo_display)

        photo_box = QFrame()
        photo_box.setObjectName("dataSection")
        photo_layout = QVBoxLayout(photo_box)
        photo_layout.setContentsMargins(3, 3, 3, 3)
        photo_layout.setSpacing(0)
        photo_layout.addWidget(self.photo_label, 0, Qt.AlignmentFlag.AlignCenter)

        location = QFrame()
        location.setObjectName("dataSection")
        location_box = QVBoxLayout(location)
        location_box.setContentsMargins(8, 5, 8, 6)
        location_box.setSpacing(4)
        location_title = QLabel("Localisation")
        location_title.setObjectName("sectionTitle")
        location_box.addWidget(location_title)

        location_grid = QGridLayout()
        location_grid.setHorizontalSpacing(7)
        location_grid.setVerticalSpacing(3)

        # Gauche : Site / Gisement / Catégorie / Lien.
        location_grid.addWidget(QLabel("Site"), 0, 0)
        location_grid.addWidget(self.site_combo, 0, 1)
        location_grid.addWidget(QLabel("Gisement"), 1, 0)
        location_grid.addWidget(self.deposit_edit, 1, 1)
        location_grid.addWidget(QLabel("Catégorie"), 2, 0)
        location_grid.addWidget(self.category_combo, 2, 1)
        location_grid.addWidget(QLabel("Lien"), 3, 0)
        location_grid.addWidget(site_link_widget, 3, 1)

        # Droite : emplacement réservé à Commune, puis Département / Région / Pays.
        # Commune n'est pas encore créée dans la base : on réserve simplement la grille.
        location_grid.addWidget(QLabel("Département"), 0, 2)
        location_grid.addWidget(self.department_combo, 0, 3)
        location_grid.addWidget(QLabel("Région"), 1, 2)
        location_grid.addWidget(self.region_combo, 1, 3)
        location_grid.addWidget(QLabel("Pays"), 2, 2)
        location_grid.addWidget(self.country_combo, 2, 3)
        location_grid.setColumnStretch(1, 5)
        location_grid.setColumnStretch(3, 4)
        location_box.addLayout(location_grid)

        aspect_panel = QFrame()
        aspect_panel.setObjectName("dataSection")
        aspect_box = QVBoxLayout(aspect_panel)
        aspect_box.setContentsMargins(8, 5, 8, 6)
        aspect_box.setSpacing(4)
        aspect_title = QLabel("Aspect")
        aspect_title.setObjectName("sectionTitle")
        aspect_box.addWidget(aspect_title)

        aspect_grid = QGridLayout()
        aspect_grid.setHorizontalSpacing(7)
        aspect_grid.setVerticalSpacing(3)

        # Gauche : Croissance / Forme / Couleur / Qualité.
        aspect_grid.addWidget(QLabel("Croissance"), 0, 0)
        aspect_grid.addWidget(self.growth_combo, 0, 1)
        aspect_grid.addWidget(QLabel("Forme"), 1, 0)
        aspect_grid.addWidget(self.shape_combo, 1, 1)
        aspect_grid.addWidget(QLabel("Couleur"), 2, 0)
        aspect_grid.addWidget(self.color_combo, 2, 1)
        aspect_grid.addWidget(QLabel("Qualité"), 3, 0)
        aspect_grid.addWidget(self.quality_combo, 3, 1)

        # Droite : Localité type / Grossissement mini / Description.
        aspect_grid.addWidget(QLabel("Localité type"), 0, 2)
        aspect_grid.addWidget(self.type_locality_combo, 0, 3)
        aspect_grid.addWidget(QLabel("Grossissement mini"), 1, 2)
        aspect_grid.addWidget(self.minimum_magnification_combo, 1, 3)
        aspect_grid.addWidget(QLabel("Description"), 2, 2)
        aspect_grid.addWidget(self.description_edit, 2, 3, 2, 1)
        aspect_grid.setColumnStretch(1, 4)
        aspect_grid.setColumnStretch(3, 5)
        aspect_box.addLayout(aspect_grid)

        acquisition_panel, acquisition_form = make_section("Acquisition")
        acquisition_form.addRow("Date", self.acquisition_date_edit)
        acquisition_form.addRow("Origine", self.origin_combo)
        acquisition_form.addRow("Contact", self.contact_combo)
        acquisition_form.addRow("Lieu", self.place_combo)

        collection_section = QFrame()
        collection_section.setObjectName("dataSection")
        collection_box = QVBoxLayout(collection_section)
        collection_box.setContentsMargins(8, 3, 8, 4)
        collection_box.setSpacing(1)
        collection_title = QLabel("Collection")
        collection_title.setObjectName("sectionTitle")
        collection_box.addWidget(collection_title)

        collection_grid = QGridLayout()
        collection_grid.setHorizontalSpacing(7)
        collection_grid.setVerticalSpacing(3)
        self.box_type_combo.setMaximumWidth(230)
        self.box_count_edit.setMaximumWidth(90)
        self.price_edit.setMaximumWidth(110)
        self.total_cost_edit.setMaximumWidth(120)
        collection_grid.addWidget(QLabel("Contenant"), 0, 0)
        collection_grid.addWidget(self.box_type_combo, 0, 1)
        collection_grid.addWidget(QLabel("Nombre de pièces"), 0, 2)
        collection_grid.addWidget(self.box_count_edit, 0, 3)
        collection_grid.addWidget(QLabel("Prix"), 0, 4)
        collection_grid.addWidget(self.price_edit, 0, 5)
        collection_grid.addWidget(QLabel(self._t("Coût total")), 0, 6)
        collection_grid.addWidget(self.total_cost_edit, 0, 7)
        collection_grid.setColumnStretch(8, 1)
        collection_box.addLayout(collection_grid)
        collection_section.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        # 018.0 — correspondance entre le catalogue de champs et les widgets de la Fiche.
        # Les colonnes SQLite restent communes ; le modèle décide seulement quels
        # champs participent à cette collection et sont donc affichés.
        def grid_widget(grid, row: int, column: int):
            item = grid.itemAtPosition(row, column)
            return item.widget() if item is not None else None

        self._model_field_widgets = {
            # N° devient un vrai champ du Bandeau commun. Sa valeur reste
            # évidemment non éditable : number_value est un QLabel.
            "record_number": [number_caption, self.number_value],
            "mineral_name": [name_label, self.name_combo],
            "mineral_2": [mineral2_label, self.mineral2_combo],
            "mineral_3": [mineral3_label, self.mineral3_combo],
            "record_state": [state_label, self.state_combo],
            "mineral_class": [grid_widget(ident_grid, 0, 0), self.class_combo],
            "chemical_formula": [grid_widget(ident_grid, 1, 0), self.formula_edit],
            "crystal_system": [grid_widget(ident_grid, 2, 0), self.crystal_combo],
            "luminescence": [grid_widget(ident_grid, 0, 2), self.luminescence_combo],
            "luminescence_intensity": [grid_widget(ident_grid, 1, 2), self.intensity_combo],
            "fluorescence_color": [grid_widget(ident_grid, 2, 2), self.fluorescence_color_combo],
            "internet_link": [grid_widget(ident_grid, 3, 0), internet_link_widget],
            "photo_data": [photo_box],
            "site_name": [grid_widget(location_grid, 0, 0), self.site_combo],
            "deposit": [grid_widget(location_grid, 1, 0), self.deposit_edit],
            "category": [grid_widget(location_grid, 2, 0), self.category_combo],
            "site_internet_link": [grid_widget(location_grid, 3, 0), site_link_widget],
            "department": [grid_widget(location_grid, 0, 2), self.department_combo],
            "region": [grid_widget(location_grid, 1, 2), self.region_combo],
            "country": [grid_widget(location_grid, 2, 2), self.country_combo],
            "growth": [grid_widget(aspect_grid, 0, 0), self.growth_combo],
            "specimen_shape": [grid_widget(aspect_grid, 1, 0), self.shape_combo],
            "specimen_color": [grid_widget(aspect_grid, 2, 0), self.color_combo],
            "quality": [grid_widget(aspect_grid, 3, 0), self.quality_combo],
            "type_locality": [grid_widget(aspect_grid, 0, 2), self.type_locality_combo],
            "minimum_magnification": [grid_widget(aspect_grid, 1, 2), self.minimum_magnification_combo],
            "description": [grid_widget(aspect_grid, 2, 2), self.description_edit],
            "acquisition_date": [acquisition_form.labelForField(self.acquisition_date_edit), self.acquisition_date_edit],
            "origin": [acquisition_form.labelForField(self.origin_combo), self.origin_combo],
            "contact": [acquisition_form.labelForField(self.contact_combo), self.contact_combo],
            "place": [acquisition_form.labelForField(self.place_combo), self.place_combo],
            "box_type": [grid_widget(collection_grid, 0, 0), self.box_type_combo],
            "box_count": [grid_widget(collection_grid, 0, 2), self.box_count_edit],
            "price": [grid_widget(collection_grid, 0, 4), self.price_edit],
            "total_cost": [grid_widget(collection_grid, 0, 6), self.total_cost_edit],
        }
        # 018.4.4.1.5.22.8 — une seule représentation visuelle de champ.
        # Les vrais widgets seront insérés dans les mêmes SharedFieldFrame que
        # ceux utilisés en mode construction dans l'Atelier.
        self._model_field_shells = {}

        self._model_sections = {
            identification: {
                "mineral_class", "chemical_formula", "crystal_system", "luminescence",
                "luminescence_intensity", "fluorescence_color", "internet_link"
            },
            photo_box: {"photo_data"},
            location: {
                "site_name", "deposit", "category", "site_internet_link", "department", "region", "country"
            },
            aspect_panel: {
                "growth", "specimen_shape", "specimen_color", "quality", "type_locality",
                "minimum_magnification", "description"
            },
            acquisition_panel: {"acquisition_date", "origin", "contact", "place"},
            collection_section: {"box_type", "box_count", "price", "total_cost"},
        }
        # 018.2 — les mêmes widgets peuvent désormais être réinsérés dans un autre bloc.
        self._model_block_layouts = {
            "Bandeau": top_grid,
            "Identification": ident_grid,
            "Localisation": location_grid,
            "Aspect": aspect_grid,
            "Acquisition": acquisition_form,
            "Collection": collection_grid,
        }
        self._model_block_sections = {
            "Identification": identification,
            "Localisation": location,
            "Aspect": aspect_panel,
            "Acquisition": acquisition_panel,
            "Collection": collection_section,
        }

        # Ligne 0 : Identification large + Photo.
        self._model_group_widgets = {
            "Bandeau": banner_section,
            "Identification": identification,
            "Photo": photo_box,
            "Localisation": location,
            "Aspect": aspect_panel,
            "Acquisition": acquisition_panel,
            "Collection": collection_section,
        }

        # 018.4.4.1.2.9 — moteur géométrique commun Atelier/Fiche.
        # Chaque groupe possède désormais une véritable zone de contenu libre,
        # exactement comme le MagneticCanvas de l'Atelier. Les anciens layouts
        # restent seulement comme supports de construction initiale puis sont vidés.
        self._model_content_canvases = {}
        for block_name in ("Bandeau",) + tuple(MODEL_BLOCKS):
            group_widget = self._model_group_widgets.get(block_name)
            if group_widget is None:
                continue
            canvas = QWidget(group_widget)
            canvas.setObjectName(f"modelContentCanvas_{block_name}")
            canvas.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
            canvas.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Fixed,
            )
            canvas.setMinimumHeight(BLOCK_MIN_HEIGHT.get(block_name, 150))
            outer_layout = group_widget.layout()
            if isinstance(outer_layout, QVBoxLayout):
                outer_layout.addWidget(canvas)
            self._model_content_canvases[block_name] = canvas

        self._custom_field_inputs = {}
        self._custom_field_defs = {}
        self._ensure_custom_field_widgets()
        QTimer.singleShot(0, self._connect_computed_field_sources)

        # 018.4.4.1.5.22.8 — la vraie Fiche utilise la même FormSurface.
        runtime_surface = FormSurface(
            self,
            lambda block_name, owner, parent: RuntimeFormCanvas(block_name, owner, parent),
        )
        self._runtime_form_surface = runtime_surface
        self._runtime_surface_widget = runtime_surface.widget
        self._runtime_groups = dict(runtime_surface.groups)
        self._runtime_groups["Photo"] = runtime_surface.photo_group
        self._runtime_canvases = runtime_surface.canvases
        self._runtime_field_shells = {}

        blocks.addWidget(identification, 0, 0, 1, 2)
        blocks.addWidget(photo_box, 0, 2, 1, 1)
        # Ligne 1 : Localisation sur toute la largeur.
        blocks.addWidget(location, 1, 0, 1, 3)
        # Ligne 2 : Aspect large + Acquisition.
        blocks.addWidget(aspect_panel, 2, 0, 1, 2)
        blocks.addWidget(acquisition_panel, 2, 2, 1, 1)
        # Ligne 3 : Collection, compacte.
        blocks.addWidget(collection_section, 3, 0, 1, 3)
        blocks.setColumnStretch(0, 4)
        blocks.setColumnStretch(1, 4)
        blocks.setColumnStretch(2, 3)

        # 018.4.4.1.5.22.8 — la vieille Fiche n'a PLUS aucun rôle visuel.
        # Elle ne sert qu'à fournir les widgets fonctionnels et leurs connexions.
        try:
            card_layout.removeWidget(self.banner_section)
            self.banner_section.hide()
        except Exception:
            pass
        self._record_blocks_host.hide()

        # Les blocs quittent la QGrid exactement comme dans l'Atelier :
        # leurs rectangles deviennent absolus et ne peuvent plus être réinterprétés.
        self._runtime_absolute_groups = detach_surface_groups(self._runtime_form_surface)

        card_layout.addWidget(
            self._runtime_surface_widget,
            0,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
        )
        card_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._record_free_group_defaults = {}
        self._schedule_runtime_surface_activation()

        # 018.4.4.1.2.9 — la fiche conserve sa hauteur naturelle.
        # Si elle dépasse la fenêtre, seule la zone de fiche défile verticalement :
        # ni le Bandeau ni les blocs ne sont comprimés pour "tenir" à l'écran.
        self.record_scroll = QScrollArea()
        self.record_scroll.setObjectName("recordVerticalScroll")
        self.record_scroll.setWidgetResizable(True)
        self.record_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.record_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.record_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.record_scroll.setWidget(card)
        card_layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        layout.addWidget(self.record_scroll, 1)

        navigation = QHBoxLayout()
        navigation.setSpacing(6)

        # Actions de libération/restauration regroupées à gauche.
        self.clear_record_btn = QPushButton(self._t("Vider la fiche"))
        self.clear_record_btn.setToolTip(
            self._t("Effacer le contenu de cette fiche en conservant son N° et la marquer Libre")
        )
        self.restore_record_btn = QPushButton(self._t("Restaurer la fiche"))
        self.restore_record_btn.setObjectName("restoreButton")
        self.restore_record_btn.setToolTip(
            self._t("Restaurer la fiche telle qu'elle était juste avant le dernier vidage")
        )
        self.restore_record_btn.setEnabled(False)

        self.first_btn = QPushButton("⏮ " + self._t("Première"))
        self.previous_btn = QPushButton("◀ " + self._t("Précédente"))
        self.next_btn = QPushButton(self._t("Suivante") + " ▶")
        self.last_btn = QPushButton(self._t("Dernière") + " ⏭")

        # Compatibilité interne : les actions de création/enregistrement ne sont
        # plus présentées à l'utilisateur. MM3 les gère automatiquement.
        self.new_btn = QPushButton(self._t("Créer une nouvelle fiche"))
        self.new_btn.setVisible(False)
        self.save_btn = QPushButton(self._t("Enregistrer la fiche"))
        self.save_btn.setVisible(False)
        close_btn = QPushButton(self._t("Fermer la fiche"))

        self.first_btn.clicked.connect(self.go_first)
        self.previous_btn.clicked.connect(self.go_previous)
        self.next_btn.clicked.connect(self.go_next)
        self.last_btn.clicked.connect(self.go_last)
        self.clear_record_btn.clicked.connect(self.clear_current_record)
        self.restore_record_btn.clicked.connect(self.restore_cleared_record)
        close_btn.clicked.connect(self.close)

        navigation.addWidget(self.clear_record_btn)
        navigation.addWidget(self.restore_record_btn)
        navigation.addSpacing(20)
        navigation.addWidget(self.first_btn)
        navigation.addWidget(self.previous_btn)
        navigation.addWidget(self.next_btn)
        navigation.addWidget(self.last_btn)
        navigation.addWidget(close_btn)
        navigation.addStretch(1)
        layout.addLayout(navigation)

        self.name_edit.textEdited.connect(self._on_name_edited)
        self.name_edit.textChanged.connect(self._mark_dirty)
        self.name_edit.enterPressed.connect(self._validate_name_and_continue)
        self.mineral2_edit.textEdited.connect(lambda text: self._on_associated_mineral_edited(self.mineral2_edit, text))
        self.mineral2_edit.textChanged.connect(self._mark_dirty)
        self.mineral2_edit.enterPressed.connect(lambda: self._validate_associated_mineral_and_continue(2))
        self.mineral3_edit.textEdited.connect(lambda text: self._on_associated_mineral_edited(self.mineral3_edit, text))
        self.mineral3_edit.textChanged.connect(self._mark_dirty)
        self.mineral3_edit.enterPressed.connect(lambda: self._validate_associated_mineral_and_continue(3))
        self.class_edit.textEdited.connect(self._on_class_edited)
        self.class_edit.textChanged.connect(self._mark_dirty)
        self.class_edit.enterPressed.connect(self._validate_class_and_continue)
        self.formula_edit.textChanged.connect(self._mark_dirty)
        self.formula_edit.returnPressed.connect(self._formula_and_continue)
        self.internet_link_edit.textChanged.connect(self._on_internet_link_changed)
        self.internet_link_edit.returnPressed.connect(self._internet_link_and_continue)
        self.site_link_edit.textChanged.connect(self._on_site_link_changed)
        self.site_link_edit.returnPressed.connect(self._site_link_and_continue)
        self.internet_link_button.clicked.connect(self._open_internet_link)
        self.crystal_edit.textEdited.connect(self._on_crystal_edited)
        self.crystal_edit.textChanged.connect(self._mark_dirty)
        self.crystal_edit.enterPressed.connect(self._validate_crystal_and_continue)
        self.luminescence_edit.textEdited.connect(self._on_luminescence_edited)
        self.luminescence_edit.textChanged.connect(self._mark_dirty)
        self.luminescence_edit.enterPressed.connect(self._validate_luminescence_and_continue)
        self.intensity_edit.textEdited.connect(self._on_intensity_edited)
        self.intensity_edit.textChanged.connect(self._mark_dirty)
        self.intensity_edit.enterPressed.connect(self._validate_intensity_and_continue)
        self.fluorescence_color_edit.textEdited.connect(self._on_fluorescence_color_edited)
        self.fluorescence_color_edit.textChanged.connect(self._mark_dirty)
        self.fluorescence_color_edit.enterPressed.connect(self._validate_fluorescence_color_and_continue)
        self.site_edit.textEdited.connect(self._on_site_edited)
        self.site_edit.textChanged.connect(self._mark_dirty)
        self.site_edit.enterPressed.connect(self._validate_site_and_continue)
        self.deposit_edit.textChanged.connect(self._mark_dirty)
        self.deposit_edit.returnPressed.connect(self._deposit_and_continue)
        self.department_edit.textEdited.connect(self._on_department_edited)
        self.department_edit.textChanged.connect(self._mark_dirty)
        self.department_edit.enterPressed.connect(self._validate_department_and_continue)
        self.region_edit.textEdited.connect(self._on_region_edited)
        self.region_edit.textChanged.connect(self._mark_dirty)
        self.region_edit.enterPressed.connect(self._validate_region_and_continue)
        self.country_edit.textEdited.connect(self._on_country_edited)
        self.country_edit.textChanged.connect(self._mark_dirty)
        self.country_edit.enterPressed.connect(self._validate_country_and_continue)
        self.box_type_edit.textEdited.connect(self._on_box_type_edited)
        self.box_type_edit.textChanged.connect(self._mark_dirty)
        self.box_type_edit.enterPressed.connect(self._validate_box_type_and_continue)
        self.category_edit.textEdited.connect(self._on_category_edited)
        self.category_edit.textChanged.connect(self._mark_dirty)
        self.category_edit.enterPressed.connect(self._validate_category_and_continue)
        self.contact_edit.textEdited.connect(self._on_contact_edited)
        self.contact_edit.textChanged.connect(self._mark_dirty)
        self.contact_edit.enterPressed.connect(self._validate_contact_and_continue)
        self.shape_edit.textEdited.connect(self._on_shape_edited)
        self.shape_edit.textChanged.connect(self._mark_dirty)
        self.shape_edit.enterPressed.connect(self._validate_shape_and_continue)
        self.color_edit.textEdited.connect(self._on_color_edited)
        self.color_edit.textChanged.connect(self._mark_dirty)
        self.color_edit.enterPressed.connect(self._validate_color_and_continue)
        self.quality_edit.textEdited.connect(self._on_quality_edited)
        self.quality_edit.textChanged.connect(self._mark_dirty)
        self.quality_edit.enterPressed.connect(self._validate_quality_and_continue)
        self.description_edit.textChanged.connect(self._mark_dirty)
        for widget in (
            self.acquisition_date_edit, self.box_count_edit, self.price_edit,
        ):
            widget.textChanged.connect(self._mark_dirty)

        self.acquisition_date_edit.returnPressed.connect(
            self._validate_acquisition_date_and_continue
        )
        self.box_count_edit.returnPressed.connect(self._validate_box_count_and_continue)
        self.box_count_edit.textChanged.connect(self._recalculate_total_cost)
        self.price_edit.textChanged.connect(self._recalculate_total_cost)

        self.price_edit.returnPressed.connect(self._validate_price_and_continue)

        self.minimum_magnification_edit.textEdited.connect(
            lambda text: self._on_generic_referential_edited("minimum_magnification", "_minimum_magnification_declined_for_value", text)
        )
        self.minimum_magnification_edit.textChanged.connect(self._mark_dirty)
        self.minimum_magnification_edit.enterPressed.connect(
            self._validate_minimum_magnification_and_continue
        )
        self.growth_edit.textEdited.connect(
            lambda text: self._on_generic_referential_edited("growth", "_growth_declined_for_value", text)
        )
        self.growth_edit.textChanged.connect(self._mark_dirty)
        self.growth_edit.enterPressed.connect(self._validate_growth_and_continue)
        self.origin_edit.textEdited.connect(
            lambda text: self._on_generic_referential_edited("origin", "_origin_declined_for_value", text)
        )
        self.origin_edit.textChanged.connect(self._mark_dirty)
        self.origin_edit.enterPressed.connect(self._validate_origin_and_continue)
        self.place_edit.textEdited.connect(
            lambda text: self._on_generic_referential_edited("place", "_place_declined_for_value", text)
        )
        self.place_edit.textChanged.connect(self._mark_dirty)
        self.place_edit.enterPressed.connect(self._validate_place_and_continue)
        self.type_locality_combo.currentTextChanged.connect(self._mark_dirty)
        self.state_combo.currentTextChanged.connect(self._mark_dirty)
        self.state_edit.textEdited.connect(self._on_state_edited)
        self.state_edit.enterPressed.connect(self._validate_state_and_continue)

        self.state_combo.installEventFilter(self)
        self.state_edit.installEventFilter(self)
        self.type_locality_combo.installEventFilter(self)
        for field in (
            self.name_edit, self.mineral2_edit, self.mineral3_edit, self.class_edit, self.formula_edit, self.internet_link_edit, self.crystal_edit,
            self.luminescence_edit, self.intensity_edit, self.fluorescence_color_edit,
            self.site_edit, self.deposit_edit, self.department_edit, self.region_edit,
            self.country_edit, self.site_link_edit, self.box_type_edit, self.category_edit, self.contact_edit,
            self.shape_edit, self.color_edit, self.quality_edit, self.description_edit,
            self.minimum_magnification_edit, self.growth_edit, self.acquisition_date_edit,
            self.origin_edit, self.place_edit, self.box_count_edit, self.price_edit, self.total_cost_edit,
        ):
            field.installEventFilter(self)
        self._install_inline_completion()
        self._apply_left_alignment()
        self._ensure_global_event_filter()
        self.setCentralWidget(root)
        self.apply_collection_model()

        try:
            # QTimer est importé au niveau du module. Ne surtout pas le réimporter
            # localement ici : Python le considérerait alors comme variable locale
            # dans toute _build_ui(), ce qui cassait l'appel précédent utilisé par
            # le nouveau moteur de déplacement des blocs.
            QTimer.singleShot(0, self._compact_banner_to_content)
        except Exception:
            self._compact_banner_to_content()


    def _reload_simple_referential(self, code: str, combo, model, selected: str = "") -> None:
        values = self.referentials.list_values(int(self.collection["id"]), code, active_only=True)
        current = selected if selected != "" else combo.currentText()
        combo.blockSignals(True)
        shown = [self._dv(v) for v in values]
        combo.clear()
        combo.addItems(shown)
        combo.setCurrentText(self._dv(current))
        combo.blockSignals(False)
        model.setStringList(shown)

    def _reload_minimum_magnification_referential(self, selected: str = "") -> None:
        self._reload_simple_referential("minimum_magnification", self.minimum_magnification_combo, self.minimum_magnification_model, selected)

    def _reload_growth_referential(self, selected: str = "") -> None:
        self._reload_simple_referential("growth", self.growth_combo, self.growth_model, selected)

    def _reload_origin_referential(self, selected: str = "") -> None:
        self._reload_simple_referential("origin", self.origin_combo, self.origin_model, selected)

    def _reload_place_referential(self, selected: str = "") -> None:
        self._reload_simple_referential("place", self.place_combo, self.place_model, selected)

    def _on_generic_referential_edited(self, code: str, declined_attr: str, text: str) -> None:
        if self._loading:
            return
        if text != getattr(self, declined_attr, ""):
            setattr(self, declined_attr, "")

    def _validate_minimum_magnification_and_continue(self) -> None:
        value = self.referentials.normalize(
            self._cv(self.minimum_magnification_combo.currentText()), "minimum_magnification"
        )
        if self._ensure_generic_referential(
            "minimum_magnification", value,
            "_minimum_magnification_declined_for_value",
            "Nouveau grossissement", "des grossissements",
            self._reload_minimum_magnification_referential,
        ):
            self._focus_next_tab_field()

    def _validate_growth_and_continue(self) -> None:
        value = self.referentials.normalize(
            self._cv(self.growth_combo.currentText()), "growth"
        )
        if self._ensure_generic_referential(
            "growth", value, "_growth_declined_for_value",
            "Nouvelle croissance", "des croissances",
            self._reload_growth_referential,
        ):
            self._focus_next_tab_field()

    def _validate_origin_and_continue(self) -> None:
        value = self.referentials.normalize(
            self._cv(self.origin_combo.currentText()), "origin"
        )
        if self._ensure_generic_referential(
            "origin", value, "_origin_declined_for_value",
            "Nouvelle origine", "des origines",
            self._reload_origin_referential,
        ):
            self._focus_next_tab_field()

    def _validate_place_and_continue(self) -> None:
        value = self.referentials.normalize(
            self._cv(self.place_combo.currentText()), "place"
        )
        if self._ensure_generic_referential(
            "place", value, "_place_declined_for_value",
            "Nouveau lieu", "des lieux",
            self._reload_place_referential,
        ):
            self._focus_next_tab_field()

    @staticmethod
    def _format_date_value(value: str) -> str:
        """Accepte les saisies courtes et retourne JJ/MM/AAAA.

        Exemples :
        1/1/26 -> 01/01/2026
        1-1-2026 -> 01/01/2026
        010126 -> 01/01/2026
        """
        from datetime import datetime

        raw = str(value or "").strip()
        if not raw:
            return ""

        cleaned = raw.replace("-", "/").replace(".", "/")

        formats = (
            "%d/%m/%Y",
            "%d/%m/%y",
            "%d%m%Y",
            "%d%m%y",
        )

        for fmt in formats:
            try:
                parsed = datetime.strptime(cleaned, fmt)
                return parsed.strftime("%d/%m/%Y")
            except ValueError:
                pass

        # Tolérer 1/1/26, 01/1/26, etc. explicitement.
        parts = [part.strip() for part in cleaned.split("/")]
        if len(parts) == 3 and all(parts):
            try:
                day, month, year = (int(part) for part in parts)
                if year < 100:
                    year += 2000 if year <= 69 else 1900
                parsed = datetime(year, month, day)
                return parsed.strftime("%d/%m/%Y")
            except (ValueError, TypeError):
                pass

        return raw

    @classmethod
    def _format_custom_date_value(cls, value: str, display_format: str) -> str:
        """Normalise une date puis l'affiche selon le format du champ.

        Accepte aussi les anciennes valeurs déjà enregistrées sous une forme
        d'affichage partielle (AAAA ou MM/AAAA), afin qu'un changement de
        format dans l'Atelier soit immédiatement visible. Pour une ancienne
        valeur réduite à l'année seule, le mois/jour inconnus sont ramenés au
        1er janvier ; pour MM/AAAA, le jour inconnu devient le 1er.
        """
        from datetime import datetime

        raw = str(value or "").strip()
        if not raw:
            return ""

        parsed = None
        normalized = cls._format_date_value(raw)
        try:
            parsed = datetime.strptime(normalized, "%d/%m/%Y")
        except ValueError:
            pass

        if parsed is None:
            for fmt in ("%Y-%m-%d", "%m/%Y", "%Y"):
                try:
                    parsed = datetime.strptime(raw, fmt)
                    break
                except ValueError:
                    pass

        if parsed is None:
            return raw

        formats = {
            "JJ/MM/AAAA": "%d/%m/%Y",
            "JJ/MM/AA": "%d/%m/%y",
            "MM/AAAA": "%m/%Y",
            "AAAA": "%Y",
            "AAAA-MM-JJ": "%Y-%m-%d",
        }
        return parsed.strftime(formats.get(str(display_format), "%d/%m/%Y"))

    def _validate_acquisition_date_and_continue(self) -> None:
        before = self.acquisition_date_edit.text()
        after = self._format_date_value(before)
        if after != before:
            self.acquisition_date_edit.blockSignals(True)
            self.acquisition_date_edit.setText(after)
            self.acquisition_date_edit.blockSignals(False)
            self._mark_dirty()
        self._focus_next_tab_field()
        self.origin_edit.selectAll()

    @staticmethod
    def _parse_number_value(value: str, default: float = 0.0) -> float:
        raw = str(value or "").strip()
        if not raw:
            return default
        raw = raw.replace("\u00a0", " ").replace("\u202f", " ").strip()
        # Conserver uniquement la partie numérique, le signe et le séparateur :
        # cela accepte €, $, £, CHF, ¥ ainsi qu'une devise libre.
        raw = re.sub(r"[^0-9,\.\-+]", "", raw)
        raw = raw.replace(",", ".")
        try:
            return float(raw)
        except ValueError:
            return default

    def _normalize_box_count(self) -> None:
        raw = self.box_count_edit.text().strip()
        if not raw:
            normalized = "1"
        else:
            try:
                count = int(float(raw.replace(",", ".")))
                normalized = str(max(0, count))
            except ValueError:
                normalized = raw

        if normalized != raw:
            self.box_count_edit.blockSignals(True)
            self.box_count_edit.setText(normalized)
            self.box_count_edit.blockSignals(False)
            self._mark_dirty()
        self._recalculate_total_cost()

    def _validate_box_count_and_continue(self) -> None:
        self._normalize_box_count()
        self._focus_next_tab_field()
        self.price_edit.selectAll()

    def _validate_price_and_continue(self) -> None:
        self._normalize_currency_field(self.price_edit)
        self._recalculate_total_cost()
        self._focus_next_tab_field()

    def _currency_symbol_for_field(self, key: str) -> str:
        try:
            styles = self.model_manager.field_styles(int(self.collection["id"]))
            style = styles.get(str(key), {}) if isinstance(styles, dict) else {}
            if isinstance(style, dict):
                symbol = str(style.get("currency_symbol", "") or "").strip()
                if symbol:
                    return symbol
        except Exception:
            pass
        return "€"

    def _currency_decimals_for_field(self, key: str) -> int:
        """Nombre de décimales d'affichage d'un champ Monétaire (0 à 4)."""
        try:
            styles = self.model_manager.field_styles(int(self.collection["id"]))
            style = styles.get(str(key), {}) if isinstance(styles, dict) else {}
            if isinstance(style, dict):
                value = int(style.get("currency_decimals", 2))
                return max(0, min(4, value))
        except Exception:
            pass
        return 2

    def _recalculate_total_cost(self, *_args) -> None:
        if not hasattr(self, "total_cost_edit"):
            return
        count = self._parse_number_value(self.box_count_edit.text(), 0.0)
        price = self._parse_number_value(self.price_edit.text(), 0.0)
        total = count * price
        formatted = self._format_currency_value(
            str(total), self._currency_symbol_for_field("total_cost"),
            self._currency_decimals_for_field("total_cost")
        )
        if self.total_cost_edit.text() != formatted:
            self.total_cost_edit.blockSignals(True)
            self.total_cost_edit.setText(formatted)
            self.total_cost_edit.blockSignals(False)
            if not self._loading:
                self._mark_dirty()

    @staticmethod
    def _format_currency_value(value: str, currency_symbol: str = "€", decimals: int = 2) -> str:
        """Normalise une saisie monétaire avec devise et nombre de décimales choisis."""
        raw = str(value or "").strip()
        if not raw:
            return ""
        raw = raw.replace("\u00a0", " ").replace("\u202f", " ").strip()
        raw = re.sub(r"[^0-9,\.\-+]", "", raw)
        raw = raw.replace(",", ".")
        try:
            amount = float(raw)
        except ValueError:
            return str(value or "").strip()
        symbol = str(currency_symbol or "€").strip() or "€"
        try:
            decimals = max(0, min(4, int(decimals)))
        except Exception:
            decimals = 2
        return f"{amount:.{decimals}f}".replace(".", ",") + " " + symbol

    def _normalize_currency_field(self, field: QLineEdit) -> None:
        before = field.text()
        currency_key = "price" if field is self.price_edit else "total_cost"
        after = self._format_currency_value(
            before, self._currency_symbol_for_field(currency_key),
            self._currency_decimals_for_field(currency_key)
        )
        if after != before:
            field.blockSignals(True)
            field.setText(after)
            field.blockSignals(False)
            self._mark_dirty()
        if field is self.price_edit:
            self._recalculate_total_cost()
        field.selectAll()

    def _apply_left_alignment(self) -> None:
        """Aligne à gauche tous les champs de saisie d'une ligne."""
        for edit in (
            self.name_edit, self.mineral2_edit, self.mineral3_edit, self.class_edit,
            self.formula_edit, self.internet_link_edit, self.crystal_edit,
            self.luminescence_edit, self.intensity_edit, self.fluorescence_color_edit,
            self.site_edit, self.deposit_edit, self.department_edit, self.region_edit,
            self.country_edit, self.site_link_edit, self.box_type_edit, self.category_edit,
            self.contact_edit, self.shape_edit, self.color_edit, self.quality_edit, self.state_edit,
        ):
            edit.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

    def _reset_single_line_scroll(self) -> None:
        """Affiche le début des valeurs longues lorsqu'un champ n'est pas édité."""
        for edit in (
            self.name_edit, self.mineral2_edit, self.mineral3_edit, self.class_edit,
            self.formula_edit, self.internet_link_edit, self.crystal_edit,
            self.luminescence_edit, self.intensity_edit, self.fluorescence_color_edit,
            self.site_edit, self.deposit_edit, self.department_edit, self.region_edit,
            self.country_edit, self.site_link_edit, self.box_type_edit, self.category_edit,
            self.contact_edit, self.shape_edit, self.color_edit, self.quality_edit, self.state_edit,
        ):
            try:
                if edit is not None and not edit.hasSelectedText():
                    edit.setCursorPosition(0)
            except RuntimeError:
                continue

    @staticmethod
    def _apply_flat_scrollbar_to_view(view) -> None:
        """Force un ascenseur 2D sur la vue réelle d'une liste Qt.

        Le popup d'un QComboBox/QCompleter peut être créé comme une fenêtre
        Qt séparée et continuer à utiliser le rendu Windows natif malgré le
        QProxyStyle de l'application. On cible donc directement SON
        QScrollBar. Le handle QSS occupe toute la largeur disponible et toute
        sa surface est la vraie zone de saisie à la souris.
        """
        if view is None:
            return
        try:
            bar = view.verticalScrollBar()
        except Exception:
            return
        if bar is None:
            return
        bar.setStyleSheet(
            "QScrollBar:vertical {"
            " background: #EEEEEE; width: 20px; margin: 0px; border: 0px;"
            "}"
            "QScrollBar::handle:vertical {"
            " background: #919191; min-height: 32px; margin: 0px; border: 0px;"
            "}"
            "QScrollBar::handle:vertical:hover { background: #7A7A7A; }"
            "QScrollBar::handle:vertical:pressed { background: #686868; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {"
            " height: 0px; background: #EEEEEE; border: 0px;"
            "}"
            "QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {"
            " background: #EEEEEE; border: 0px;"
            "}"
        )
        try:
            bar.setMinimumWidth(20)
            bar.setMaximumWidth(20)
        except Exception:
            pass

    def _style_combo_popup_scrollbars(self, combo: QComboBox) -> None:
        """Applique le rendu MM3 aux deux popups possibles du champ.

        11.7.70.12 — le filtre est aussi posé sur le QComboBox, son éditeur
        et le popup du QCompleter. Échap est ainsi intercepté avant que Qt ne
        se contente de fermer la liste, et la roulette peut être neutralisée
        sur le champ sans empêcher le défilement dans le popup ouvert.
        """
        if not isinstance(combo, QComboBox):
            return
        try:
            combo.installEventFilter(self)
        except Exception:
            pass
        try:
            view = combo.view()
            self._apply_flat_scrollbar_to_view(view)
            if view is not None:
                view.installEventFilter(self)
        except Exception:
            pass
        try:
            edit = combo.lineEdit()
            if edit is not None:
                edit.installEventFilter(self)
            completer = edit.completer() if edit is not None else None
            if completer is not None:
                popup = completer.popup()
                self._apply_flat_scrollbar_to_view(popup)
                if popup is not None:
                    popup.installEventFilter(self)
        except Exception:
            pass

    def _install_prefix_inline_completion(self, combo: QComboBox, values: list[str]) -> None:
        """Complète immédiatement une liste avec la première valeur commençant par la frappe."""
        if not isinstance(combo, QComboBox) or combo.lineEdit() is None:
            return
        edit = combo.lineEdit()
        clean_values = [str(v) for v in values if str(v)]
        edit.setProperty("_mm3_prefix_values", clean_values)
        edit.setProperty("_gskol_referential_field", True)

        completer = QCompleter(clean_values, combo)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchStartsWith)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        edit.setCompleter(completer)
        self._style_combo_popup_scrollbars(combo)

        if not bool(edit.property("_mm3_prefix_inline_connected")):
            edit.setProperty("_mm3_prefix_inline_connected", True)
            edit.textEdited.connect(
                lambda text, e=edit: self._prefix_inline_complete_edit(e, text)
            )

    def _prefix_inline_complete_edit(self, edit: QLineEdit, typed: str) -> None:
        if self._loading:
            return
        # Retour arrière / Suppr doivent toujours pouvoir enlever ce que
        # l'utilisateur vient de saisir. Sans ce garde-fou, l'autocomplétion
        # préfixe d'un champ Liste pouvait remettre immédiatement la valeur
        # supprimée et donner l'impression que Retour arrière ne fonctionnait
        # plus.
        skip_inline = bool(edit.property("_mm3_skip_inline_once"))
        if skip_inline:
            edit.setProperty("_mm3_skip_inline_once", False)
            return
        typed = str(typed or "")
        if not typed:
            return
        values = list(edit.property("_mm3_prefix_values") or [])
        folded = typed.casefold()
        match = next(
            (value for value in values if str(value).casefold().startswith(folded)),
            None,
        )
        if not match or len(match) <= len(typed):
            return

        blocker = QSignalBlocker(edit)
        edit.setText(str(match))
        edit.setSelection(len(typed), len(str(match)) - len(typed))
        del blocker

    def _create_referential_combo(self, placeholder: str, max_items: int):
        combo = QComboBox()
        combo.setEditable(True)
        combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        combo.setMaxVisibleItems(max_items)
        edit = ReferentialLineEdit(combo)
        edit.setProperty("_gskol_referential_field", True)
        combo.setLineEdit(edit)
        edit.setPlaceholderText("")
        edit.setClearButtonEnabled(False)
        # Le modèle et le completer appartiennent au combo : leur durée de vie
        # suit exactement celle du champ, y compris lors d'un changement rapide
        # de collection.
        model = QStringListModel(combo)
        combo.setModel(model)
        try:
            completer = QCompleter(model, combo)
        except SystemError:
            # PySide6/Windows peut très rarement retourner NULL lors de la
            # construction directe QCompleter(model, parent), surtout après
            # ouverture/changement rapide de collection. Construction en deux
            # temps = même résultat, sans planter la Fiche.
            completer = QCompleter(combo)
            completer.setModel(model)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        edit.setCompleter(completer)
        return combo, edit, model, completer

    def _reload_generic_referential(self, code: str, combo, edit, model, selected=None) -> None:
        values = self.referentials.list_values(int(self.collection["id"]), code)
        current = selected if selected is not None else edit.text()
        combo_blocker = QSignalBlocker(combo)
        edit_blocker = QSignalBlocker(edit)
        shown = [self._dv(v) for v in values]
        model.setStringList(shown)
        # L'autocomplétion en ligne utilise un modèle filtré distinct.
        # Lorsqu'un référentiel est rechargé (notamment Contact), ce modèle
        # doit être synchronisé lui aussi.
        filter_models = getattr(self, "_inline_filter_models", {})
        filter_model = filter_models.get(edit)
        if filter_model is not None:
            filter_model.setStringList(shown)
        combo.setCurrentText(self._dv(str(current).strip()))
        del edit_blocker
        del combo_blocker



    @staticmethod
    def _custom_definition_is_link(definition: dict) -> bool:
        """Reconnaît un champ Lien, y compris dans une collection déjà importée en Texte."""
        field_type = str(definition.get("field_type") or "").strip().casefold()
        if field_type == "link":
            return True
        if field_type != "text":
            return False
        label = str(definition.get("label") or "").strip().casefold()
        return any(token in label for token in ("lien", "link", "url", "internet", "web"))

    def _ensure_custom_field_widgets(self) -> None:
        collection_id = int(self.collection["id"])
        definitions = self.model_manager.custom_field_map(collection_id)
        self._custom_field_defs = definitions
        # 11.7.70.26.21 — le choix mono/multiligne est décidé AVANT la création
        # du contrôle. On ne remplace plus un QLineEdit déjà relié aux données,
        # ce qui avait provoqué en .26.20 la répétition de la fiche 1.
        try:
            runtime_field_styles = self.model_manager.field_styles(collection_id)
        except Exception:
            runtime_field_styles = {}
        holding_layout = self._model_block_layouts.get("Collection")
        if holding_layout is None:
            return

        for key, definition in definitions.items():
            if key in self._model_field_widgets:
                widget = self._custom_field_inputs.get(key)
                field_type = str(definition.get("field_type") or "text")

                # 11.7.70.7 — certains changements de type nécessitent un vrai
                # changement de contrôle Qt (Texte -> Liste, Texte -> Oui/Non,
                # Liste -> Texte, etc.). Reconfigurer un QLineEdit en place ne
                # suffit pas : on détruit uniquement les deux widgets du champ
                # et on les recrée ci-dessous avec le bon type. Cela évite une
                # Fiche vide après une conversion faite dans l'Atelier.
                wants_combo = field_type == "list"
                wants_button = field_type == "boolean"
                data_style = (runtime_field_styles.get(key, {}) or {}).get("data", {})
                wants_multiline = field_type == "text" and bool((data_style or {}).get("wrap", False))
                widget_matches = (
                    (wants_combo and isinstance(widget, QComboBox))
                    or (wants_button and isinstance(widget, QPushButton))
                    or (wants_multiline and isinstance(widget, QPlainTextEdit))
                    or ((not wants_combo and not wants_button and not wants_multiline) and isinstance(widget, QLineEdit))
                )
                if not widget_matches:
                    old_widgets = list(self._model_field_widgets.pop(key, []) or [])
                    self._custom_field_inputs.pop(key, None)
                    for old_widget in old_widgets:
                        try:
                            old_widget.hide()
                            old_widget.setParent(None)
                            old_widget.deleteLater()
                        except Exception:
                            pass
                else:

                        # 11.7.70.3 — un champ déjà présent dans une Fiche ouverte peut
                    # changer de type dans l'Atelier. Jusqu'ici le widget existant
                    # conservait son ancien comportement jusqu'à fermeture/réouverture
                    # de la collection. Reconfigurer immédiatement le QLineEdit pour
                    # qu'un Nombre devenu Calculé soit bien en lecture seule et puisse
                    # afficher son résultat dès le retour Atelier -> Fiche.
                    if isinstance(widget, QLineEdit):
                        if field_type == "calculated":
                            widget.setReadOnly(True)
                            widget.setToolTip("Valeur calculée automatiquement")
                            widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)
                        else:
                            # Ne pas laisser le statut Calculé survivre à un changement
                            # de type ultérieur sur une Fiche déjà ouverte.
                            if widget.toolTip() == "Valeur calculée automatiquement":
                                widget.setToolTip("")
                            widget.setReadOnly(False)
                            widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

                    if isinstance(widget, QLineEdit) and self._custom_definition_is_link(definition):
                        self._prepare_link_editor(widget)
                    # 018.4.4.1.4.1 — un champ Date existe déjà à l'écran :
                    # recharger immédiatement son nouveau format et reformater la
                    # valeur affichée lors d'un retour de l'Atelier Modèles.
                    if definition.get("field_type") == "date" and isinstance(widget, QLineEdit):
                        display_format = str(definition.get("date_format") or "JJ/MM/AAAA")
                        widget.setPlaceholderText("")
                        current = widget.text().strip()
                        if current:
                            formatted = self._format_custom_date_value(current, display_format)
                            blocker = QSignalBlocker(widget)
                            widget.setText(formatted)
                            del blocker
                    if definition.get("field_type") == "list" and isinstance(widget, QComboBox):
                        current = widget.currentText()
                        if widget.lineEdit() is not None and not isinstance(widget.lineEdit(), ReferentialLineEdit):
                            # Collections déjà ouvertes / anciens widgets : remplacer
                            # le QLineEdit standard sans perdre la valeur courante.
                            specialized = ReferentialLineEdit(widget)
                            specialized.setText(current)
                            specialized.setReadOnly(False)
                            specialized.setMaxLength(32767)
                            specialized.setClearButtonEnabled(False)
                            widget.setLineEdit(specialized)
                            specialized.installEventFilter(self)
                        code = str(definition.get("referential_code") or key)
                        try:
                            values = self.referentials.list_values(int(self.collection["id"]), code)
                        except Exception:
                            values = []
                        blocker = QSignalBlocker(widget)
                        shown_values = [self._dv(v) for v in values]
                        widget.clear()
                        widget.addItems(shown_values)
                        widget.setCurrentText(self._dv(self._cv(current)))
                        if widget.lineEdit() is not None:
                            widget.lineEdit().setReadOnly(False)
                            widget.lineEdit().setMaxLength(32767)
                            widget.lineEdit().setCursorPosition(len(widget.currentText()))
                            self._install_prefix_inline_completion(widget, shown_values)
                        del blocker
                    continue

            label = QLabel(str(definition.get("label") or "Nouveau champ"))
            label.setObjectName("fieldCaption")
            field_type = str(definition.get("field_type") or "text")

            if field_type == "boolean":
                # MM3 : un booléen est un vrai bouton à deux états, jamais une liste.
                field = QPushButton("Non")
                field.setCheckable(True)
                field.setProperty("mm3_boolean", True)
                field.setToolTip("Cliquez pour basculer entre Oui et Non (On / Off)")
                def _toggle_boolean(checked, button=field):
                    button.setText("Oui" if checked else "Non")
                    self._mark_dirty()
                field.toggled.connect(_toggle_boolean)
            elif field_type == "list":
                field = QComboBox()
                field.setEditable(True)
                # Utiliser le même QLineEdit spécialisé que les référentiels
                # natifs. Le QLineEdit standard créé par QComboBox pouvait
                # laisser QCompleter réinjecter immédiatement le texte après
                # Retour arrière / Suppr dans les collections issues d'Excel.
                # ReferentialLineEdit marque explicitement ces touches avant
                # que textEdited ne déclenche l'autocomplétion préfixe.
                field.setLineEdit(ReferentialLineEdit(field))
                field.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
                field.setMaxVisibleItems(24)
                code = str(definition.get("referential_code") or key)
                try:
                    values = self.referentials.list_values(
                        int(self.collection["id"]), code
                    )
                except Exception:
                    values = []
                shown_values = [self._dv(v) for v in values]
                field.addItems(shown_values)
                if field.lineEdit() is not None:
                    field.lineEdit().setReadOnly(False)
                    field.lineEdit().setMaxLength(32767)
                    field.lineEdit().setClearButtonEnabled(False)
                    field.lineEdit().setFocusPolicy(Qt.FocusPolicy.StrongFocus)
                    self._install_prefix_inline_completion(field, shown_values)
                field.currentTextChanged.connect(self._mark_dirty)
            else:
                data_style = (runtime_field_styles.get(key, {}) or {}).get("data", {})
                wants_multiline = field_type == "text" and bool((data_style or {}).get("wrap", False))
                if wants_multiline:
                    field = QPlainTextEdit()
                    field.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
                    field.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
                    field.textChanged.connect(self._mark_dirty)
                else:
                    field = QLineEdit()
                if field_type == "calculated":
                    field.setReadOnly(True); field.setToolTip("Valeur calculée automatiquement"); field.setFocusPolicy(Qt.FocusPolicy.NoFocus)
                if field_type == "date":
                    field.setPlaceholderText("")
                elif field_type == "numeric":
                    field.setPlaceholderText("")
                elif field_type == "currency":
                    field.setPlaceholderText("")
                elif field_type == "link":
                    field.setPlaceholderText("")
                    self._prepare_link_editor(field)
                elif self._custom_definition_is_link(definition):
                    # Compatibilité immédiate avec les collections déjà importées
                    # par .39.23 où les hyperliens Access avaient été classés Texte.
                    self._prepare_link_editor(field)
                if field_type != "calculated" and isinstance(field, QLineEdit):
                    field.textChanged.connect(self._mark_dirty)

            field.installEventFilter(self)
            if isinstance(field, QComboBox) and field.lineEdit() is not None:
                field.lineEdit().installEventFilter(self)
            self._custom_field_inputs[key] = field
            self._model_field_widgets[key] = [label, field]

            if isinstance(holding_layout, QGridLayout):
                row = holding_layout.rowCount()
                holding_layout.addWidget(label, row, 0)
                holding_layout.addWidget(field, row, 1)
            elif isinstance(holding_layout, QFormLayout):
                holding_layout.addRow(label, field)

    def _prepare_link_editor(self, edit: QLineEdit) -> None:
        """Active le comportement MM3 des champs Lien.

        Le clic gauche ordinaire reste réservé à la saisie. Ctrl+clic ouvre la
        cible ; le clic droit affiche un menu entièrement francisé.
        """
        if not isinstance(edit, QLineEdit):
            return
        edit.setProperty("mm3_link_field", True)
        edit.setToolTip("Ctrl+clic : ouvrir le lien")
        edit.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        # 11.4.32 — connexion unique : évite le RuntimeWarning de disconnect() à vide.
        if not bool(edit.property("mm3_link_menu_connected")):
            edit.customContextMenuRequested.connect(
                lambda pos, w=edit: self._show_link_context_menu(w, pos)
            )
            edit.setProperty("mm3_link_menu_connected", True)

    def _open_link_editor(self, edit: QLineEdit) -> None:
        value = str(edit.text() or "").strip()
        if not value:
            QMessageBox.information(self, "Ouvrir le lien", "Le champ Lien est vide.")
            return
        url = QUrl.fromUserInput(value)
        if not url.isValid() or url.isEmpty():
            QMessageBox.warning(self, "Lien invalide", "Cette valeur ne peut pas être ouverte comme lien.")
            return
        if not QDesktopServices.openUrl(url):
            QMessageBox.warning(
                self,
                "Ouverture impossible",
                "Windows n'a pas pu ouvrir ce lien avec l'application associée.",
            )

    def _show_link_context_menu(self, edit: QLineEdit, pos) -> None:
        if not isinstance(edit, QLineEdit):
            return
        menu = QMenu(edit)
        open_action = menu.addAction(tr("Ouvrir le lien", self.language))
        open_action.setEnabled(bool(edit.text().strip()))
        menu.addSeparator()

        undo_action = menu.addAction(tr("Annuler", self.language))
        undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        undo_action.setEnabled((not edit.isReadOnly()) and edit.isUndoAvailable())

        redo_action = menu.addAction(tr("Rétablir", self.language))
        redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        redo_action.setEnabled((not edit.isReadOnly()) and edit.isRedoAvailable())
        menu.addSeparator()

        cut_action = menu.addAction(tr("Couper", self.language))
        cut_action.setShortcut(QKeySequence.StandardKey.Cut)
        cut_action.setEnabled((not edit.isReadOnly()) and bool(edit.selectedText()))

        copy_action = menu.addAction(tr("Copier", self.language))
        copy_action.setShortcut(QKeySequence.StandardKey.Copy)
        copy_action.setEnabled(bool(edit.selectedText()))

        paste_action = menu.addAction(tr("Coller", self.language))
        paste_action.setShortcut(QKeySequence.StandardKey.Paste)
        paste_action.setEnabled(
            (not edit.isReadOnly()) and bool(QApplication.clipboard().text())
        )

        delete_action = menu.addAction(tr("Supprimer", self.language))
        delete_action.setEnabled((not edit.isReadOnly()) and bool(edit.selectedText()))
        menu.addSeparator()

        select_all_action = menu.addAction("Tout sélectionner")
        select_all_action.setShortcut(QKeySequence.StandardKey.SelectAll)
        select_all_action.setEnabled(bool(edit.text()))

        open_action.triggered.connect(lambda: self._open_link_editor(edit))
        undo_action.triggered.connect(edit.undo)
        redo_action.triggered.connect(edit.redo)
        cut_action.triggered.connect(edit.cut)
        copy_action.triggered.connect(edit.copy)
        paste_action.triggered.connect(edit.paste)
        delete_action.triggered.connect(lambda: edit.del_())
        select_all_action.triggered.connect(edit.selectAll)
        menu.exec(edit.mapToGlobal(pos))

    def _custom_key_for_widget(self, watched) -> str | None:
        for key, widget in self._custom_field_inputs.items():
            if watched is widget:
                return key
            if isinstance(widget, QComboBox) and widget.lineEdit() is not None:
                if watched is widget.lineEdit():
                    return key
        return None

    def _validate_custom_field_and_continue(self, key: str) -> None:
        definition = self._custom_field_defs.get(key, {})
        widget = self._custom_field_inputs.get(key)
        if widget is None:
            return

        field_type = str(definition.get("field_type") or "text")
        value = self._custom_widget_value(key)

        if field_type == "date" and isinstance(widget, QLineEdit):
            formatted = self._format_custom_date_value(value, str(definition.get("date_format") or "JJ/MM/AAAA"))
            if formatted != value:
                blocker = QSignalBlocker(widget)
                widget.setText(formatted)
                del blocker
                self._mark_dirty()

        if field_type == "currency" and isinstance(widget, QLineEdit) and value:
            formatted = self._format_currency_value(
                value, self._currency_symbol_for_field(key),
                self._currency_decimals_for_field(key)
            )
            if formatted != value:
                blocker = QSignalBlocker(widget)
                widget.setText(formatted)
                del blocker
                self._mark_dirty()

        if field_type == "list" and value:
            value = self._cv(str(value))
            code = str(definition.get("referential_code") or key)
            try:
                values = self.referentials.list_values(
                    int(self.collection["id"]), code
                )
            except Exception:
                values = []
            canonical_value = self._cv(str(value or "")).strip().casefold()
            canonical_values = {
                self._cv(str(item or "")).strip().casefold()
                for item in values
            }
            if canonical_value not in canonical_values:
                box = QMessageBox(self)
                box.setIcon(QMessageBox.Icon.Question)
                box.setWindowTitle("Nouvelle valeur")
                box.setText(
                    f"Ajouter « {value} » au référentiel "
                    f"« {definition.get('label', key)} » ?"
                )
                yes_button = box.addButton("Oui", QMessageBox.ButtonRole.YesRole)
                box.addButton("Non", QMessageBox.ButtonRole.NoRole)
                box.setDefaultButton(yes_button)
                box.exec()
                if box.clickedButton() is yes_button:
                    try:
                        self.referentials.add_value(
                            int(self.collection["id"]), code, value
                        )
                        values = self.referentials.list_values(
                            int(self.collection["id"]), code
                        )
                        if isinstance(widget, QComboBox):
                            blocker = QSignalBlocker(widget)
                            shown_values = [self._dv(v) for v in values]
                            widget.clear()
                            widget.addItems(shown_values)
                            widget.setCurrentText(self._dv(value))
                            if widget.lineEdit() is not None:
                                self._install_prefix_inline_completion(widget, shown_values)
                            del blocker
                    except Exception as exc:
                        QMessageBox.critical(self, "Ajout impossible", str(exc))
                        return

        self._focus_next_tab_field()

    def _custom_widget_value(self, key: str) -> str:
        widget = self._custom_field_inputs.get(key)
        if isinstance(widget, QPushButton) and bool(widget.property("mm3_boolean")):
            return "1" if widget.isChecked() else "0"
        if isinstance(widget, QComboBox):
            return self._cv(widget.currentText()).strip()
        if isinstance(widget, QLineEdit):
            return widget.text().strip()
        if isinstance(widget, QPlainTextEdit):
            return widget.toPlainText().strip()
        return ""

    def _set_custom_widget_value(self, key: str, value: str) -> None:
        widget = self._custom_field_inputs.get(key)
        if widget is None:
            return

        # 018.4.4.1.4.1 — le format Date est appliqué AU CHARGEMENT de la valeur.
        # C'est indispensable après une modification du format dans l'Atelier :
        # _load_custom_values_for_current_record() ne doit plus réinjecter la
        # valeur brute et annuler le reformatage fait juste avant.
        definition = self._custom_field_defs.get(str(key), {})
        text_value = str(value or "")
        if (
            str(definition.get("field_type") or "") == "date"
            and isinstance(widget, QLineEdit)
            and text_value.strip()
        ):
            text_value = self._format_custom_date_value(
                text_value,
                str(definition.get("date_format") or "JJ/MM/AAAA"),
            )
        if (
            str(definition.get("field_type") or "") == "currency"
            and isinstance(widget, QLineEdit)
            and text_value.strip()
        ):
            text_value = self._format_currency_value(
                text_value, self._currency_symbol_for_field(str(key)),
                self._currency_decimals_for_field(str(key))
            )

        blocker = QSignalBlocker(widget)
        if isinstance(widget, QPushButton) and bool(widget.property("mm3_boolean")):
            checked = text_value.strip().casefold() in {"1", "oui", "yes", "true", "vrai", "on"}
            widget.setChecked(checked)
            widget.setText("Oui" if checked else "Non")
        elif isinstance(widget, QComboBox):
            text = self._dv(self._cv(text_value))
            index = widget.findText(text)
            if index < 0:
                wanted = text.strip().casefold()
                for item_index in range(widget.count()):
                    if widget.itemText(item_index).strip().casefold() == wanted:
                        index = item_index
                        text = widget.itemText(item_index)
                        break
            if index >= 0:
                widget.setCurrentIndex(index)
            elif widget.isEditable():
                widget.setCurrentText(text)
            else:
                widget.setCurrentIndex(0 if widget.count() else -1)
        elif isinstance(widget, QLineEdit):
            widget.setText(text_value)
        elif isinstance(widget, QPlainTextEdit):
            widget.setPlainText(text_value)
        del blocker

    def _load_custom_values_for_current_record(self) -> None:
        values = {}
        has_persisted_record = 0 <= self.position < len(self.records)
        if has_persisted_record:
            values = self.manager.custom_values(int(self.records[self.position]["id"]))

        styles = {}
        if not has_persisted_record:
            try:
                styles = self.model_manager.field_styles(int(self.collection["id"]))
            except Exception:
                styles = {}

        for key in self._custom_field_inputs:
            if str(self._custom_field_defs.get(key, {}).get("field_type") or "") == "calculated":
                continue

            if has_persisted_record:
                value = values.get(key, "")
            else:
                style = styles.get(str(key), {}) if isinstance(styles, dict) else {}
                value = ""
                if isinstance(style, dict):
                    value = str(style.get("default_value", "") or "")
                # Un champ Monétaire avec défaut numérique vide reste vide ;
                # avec "0" / "0,00" / "0,00 €", _set_custom_widget_value()
                # applique ensuite automatiquement la devise configurée.
            self._set_custom_widget_value(key, value)

        self._recalculate_computed_fields()

    def _computed_source_value(self, key: str):
        text = self._custom_widget_value(key) if key in self._custom_field_inputs else self._relation_widget_value(key)
        text = str(text or "").strip()
        if not text: return 0.0
        cleaned = re.sub(r"[^0-9,\.\-+]", "", text.replace("\u202f", "").replace(" ", ""))
        cleaned = cleaned.replace(",", ".")
        try: return float(cleaned)
        except Exception: return text

    @staticmethod
    def _safe_calc_eval(expression: str):
        tree = ast.parse(expression, mode="eval")
        ops = {ast.Add: lambda a,b:a+b, ast.Sub: lambda a,b:a-b, ast.Mult: lambda a,b:a*b, ast.Div: lambda a,b:a/b}
        def ev(n):
            if isinstance(n, ast.Expression): return ev(n.body)
            if isinstance(n, ast.Constant) and isinstance(n.value, (int,float,str)): return n.value
            if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.UAdd, ast.USub)):
                v=ev(n.operand); return v if isinstance(n.op, ast.UAdd) else -v
            if isinstance(n, ast.BinOp) and type(n.op) in ops: return ops[type(n.op)](ev(n.left), ev(n.right))
            raise ValueError("Formule non autorisée")
        return ev(tree)

    def _calculated_result_suffix(self, key: str) -> str:
        try:
            styles = self.model_manager.field_styles(int(self.collection["id"]))
            style = styles.get(str(key), {}) if isinstance(styles, dict) else {}
            if isinstance(style, dict):
                return str(style.get("result_suffix", "") or "").strip()
        except Exception:
            pass
        return ""

    def _recalculate_computed_fields(self, *_args) -> None:
        if getattr(self, "_computing_custom_fields", False): return
        self._computing_custom_fields = True
        try:
            for key, definition in self._custom_field_defs.items():
                if str(definition.get("field_type") or "") != "calculated": continue
                try:
                    formula = str(definition.get("calculation_formula") or "")
                    expr = re.sub(r"\{([^{}]+)\}", lambda m: repr(self._computed_source_value(m.group(1))), formula)
                    value = self._safe_calc_eval(normalize_calculation_formula(expr))
                    if isinstance(value, (int,float)) and not isinstance(value,bool):
                        mode = str(definition.get("calculation_format") or "truncate2")
                        if mode == "round":
                            result = str(int(math.floor(value+0.5)) if value>=0 else int(math.ceil(value-0.5)))
                        elif mode == "truncate0":
                            result = str(math.trunc(value))
                        else:
                            result = f"{math.trunc(value*100)/100:.2f}".replace(".", ",")
                        suffix = self._calculated_result_suffix(key)
                        if suffix:
                            result = result + " " + suffix
                    else:
                        result = str(value)
                except Exception:
                    result = ""
                self._set_custom_widget_value(key, result)
        finally: self._computing_custom_fields = False

    def _connect_computed_field_sources(self) -> None:
        if getattr(self, "_computed_sources_connected", False): return
        self._computed_sources_connected = True
        for key in self._model_field_widgets:
            try: widget = self._relation_widget(key)
            except Exception: continue
            try:
                if isinstance(widget, QComboBox): widget.currentTextChanged.connect(self._recalculate_computed_fields)
                elif isinstance(widget, QLineEdit): widget.textChanged.connect(self._recalculate_computed_fields)
                elif isinstance(widget, QPlainTextEdit): widget.textChanged.connect(self._recalculate_computed_fields)
            except Exception: pass
        self._recalculate_computed_fields()

    def _save_custom_values_for_current_record(self) -> None:
        if not (0 <= self.position < len(self.records)):
            return
        values = {key: self._custom_widget_value(key) for key in self._custom_field_inputs
                  if str(self._custom_field_defs.get(key, {}).get("field_type") or "") != "calculated"}
        self.manager.set_custom_values(int(self.records[self.position]["id"]), values)

    def _relation_widget(self, key: str):
        """Widget fonctionnel utilisé par le moteur Maître / Relié à.

        23.9.3.6.2 — pour une liste éditable, conserver le QComboBox lui-même
        afin de recevoir immédiatement son signal activated(). La navigation,
        elle, continue d'utiliser le QLineEdit interne via _field_focus_target().
        """
        container, target = self._field_focus_target(str(key))
        if isinstance(container, QComboBox):
            return container
        return target

    def _relation_widget_value(self, key: str) -> str:
        widget = self._relation_widget(str(key))
        if isinstance(widget, QComboBox):
            return widget.currentText().strip()
        if isinstance(widget, QLineEdit):
            return widget.text().strip()
        if isinstance(widget, QPlainTextEdit):
            return widget.toPlainText().strip()
        return ""

    def _set_relation_widget_value(self, key: str, value: str) -> bool:
        widget = self._relation_widget(str(key))
        if widget is None:
            return False
        text = str(value or "")
        previous = self._relation_widget_value(str(key))
        if previous == text:
            return False
        # Le blocage du QComboBox seul ne bloque PAS les signaux de son
        # QLineEdit interne (ReferentialLineEdit). C'est précisément ce signal
        # qui créait une fiche virtuelle pendant une propagation Maître/Relié.
        blocker = QSignalBlocker(widget)
        edit_blocker = (QSignalBlocker(widget.lineEdit())
                        if isinstance(widget, QComboBox) and widget.lineEdit() is not None
                        else None)
        try:
            if isinstance(widget, QComboBox):
                index = widget.findText(text)
                if index >= 0:
                    widget.setCurrentIndex(index)
                elif widget.isEditable():
                    widget.setCurrentText(text)
                elif widget.count():
                    widget.setCurrentIndex(0)
            elif isinstance(widget, QLineEdit):
                widget.setText(text)
            elif isinstance(widget, QPlainTextEdit):
                widget.setPlainText(text)
            else:
                return False
        finally:
            if edit_blocker is not None:
                del edit_blocker
            del blocker
        return True

    def _apply_master_relations(self, master_key: str) -> None:
        """Applique un Maître et propage les éventuels Maîtres intermédiaires.

        Une valeur Maître sans ligne relationnelle connue passe en mode libre :
        MM3 efface une seule fois les anciennes données Reliées provenant de la
        valeur précédente, puis laisse l’utilisateur compléter manuellement les
        champs. Ce comportement vaut pour toute collection MM3, quelle que soit
        l’origine de son import.
        """
        master_key = str(master_key)
        if self._relation_runtime_guard or master_key not in self._field_masters:
            return

        changed = False
        queue = [master_key]
        visited: set[str] = set()
        self._relation_runtime_guard = True
        try:
            while queue:
                current_master = str(queue.pop(0))
                if current_master in visited or current_master not in self._field_masters:
                    continue
                visited.add(current_master)
                master_value = self._relation_widget_value(current_master)
                try:
                    values = (
                        self.model_manager.linked_values_for_master(
                            int(self.collection["id"]), current_master, master_value
                        )
                        if master_value else {}
                    )
                except Exception:
                    values = {}

                direct_linked = [
                    str(k) for k, m in self._field_links.items()
                    if str(m) == current_master
                ]

                # Une valeur déjà passée en mode libre le reste pendant toute
                # la saisie courante, même après l'enregistrement du premier
                # champ Relié. Sans cela, ce premier champ créerait une ligne
                # partielle de référence et les champs encore à saisir seraient
                # de nouveau vidés par une application automatique prématurée.
                token = str(master_value).casefold() if master_value else ""
                if master_value and self._unresolved_relation_masters.get(current_master) == token:
                    continue

                # Valeur non vide mais inconnue du référentiel : vider les
                # anciennes données une seule fois, puis libérer les champs.
                if master_value and not values:
                    self._unresolved_relation_masters[current_master] = token
                    for linked_key in direct_linked:
                        field_changed = self._set_relation_widget_value(linked_key, "")
                        changed = field_changed or changed
                        if linked_key in self._field_masters and linked_key not in visited:
                            queue.append(linked_key)
                    continue

                # Une valeur connue (ou un Maître vidé) repasse en pilotage normal.
                self._unresolved_relation_masters.pop(current_master, None)
                for linked_key in direct_linked:
                    value = values.get(linked_key, "")
                    field_changed = self._set_relation_widget_value(linked_key, value)
                    changed = field_changed or changed
                    if linked_key in self._field_masters and linked_key not in visited:
                        queue.append(linked_key)
        finally:
            self._relation_runtime_guard = False
        if changed and not (self._virtual_new_record and self.position == len(self.records)):
            # Sur une fiche virtuelle, la propagation automatique ne doit
            # jamais, à elle seule, matérialiser une fiche en base.
            # La saisie utilisateur reste détectée par ses propres signaux.
            self._mark_dirty()

    def _propagate_linked_empty_if_needed(self, linked_key: str) -> None:
        """Le vide est une vraie valeur reliée et doit être propagé immédiatement.

        On ne propage sur textChanged QUE lorsque le contrôle vient d'être vidé,
        afin de ne pas enregistrer chaque caractère intermédiaire pendant une saisie.
        """
        linked_key = str(linked_key)
        if self._relation_runtime_guard or linked_key not in self._field_links:
            return
        if self._relation_widget_value(linked_key) == "":
            self._propagate_linked_field(linked_key)

    def _propagate_linked_field(self, linked_key: str) -> None:
        linked_key = str(linked_key)
        if self._relation_runtime_guard:
            return
        master_key = self._field_links.get(linked_key)
        if not master_key:
            return
        master_value = self._relation_widget_value(master_key)
        if not master_value:
            return
        value = self._relation_widget_value(linked_key)
        try:
            ids = self.model_manager.propagate_linked_value(
                int(self.collection["id"]), master_key, master_value, linked_key, value
            )
        except Exception as exc:
            QMessageBox.critical(self, "Mise à jour impossible", str(exc))
            return

        # Les enregistrements standard déjà chargés en mémoire doivent refléter
        # immédiatement la propagation SQLite, sans imposer un rechargement écran.
        if ids:
            affected = set(int(rid) for rid in ids)
            for row in getattr(self, "records", []):
                if int(row.get("id", -1)) in affected and linked_key in row:
                    row[linked_key] = value

            # La propagation est déjà enregistrée en base pour toutes les fiches
            # partageant la même valeur Maître : le Tableau doit donc se relire
            # immédiatement, sans attendre une navigation dans la Fiche.
            current_id = self._current_record_id()
            self.recordSaved.emit(int(current_id if current_id is not None else ids[0]))

    def _apply_current_master_relations(self) -> None:
        """Applique les liaisons aux valeurs Maître déjà présentes à l'écran.

        23.9.3.6.3 — au retour de l'Atelier, une liaison nouvellement créée
        doit agir immédiatement sur la fiche affichée, sans obliger l'utilisateur
        à effacer puis ressaisir la valeur du champ Maître.
        """
        if self._relation_runtime_guard:
            return
        # Appliquer aussi les Maîtres vides. Un Maître vide signifie qu'aucune
        # donnée Reliée ne doit rester affichée. Cette règle est importante dès
        # la création d'une collection par import (notamment Excel) : une fiche
        # neuve ou un Site effacé doit repartir avec tous ses champs Reliés vides,
        # au lieu de conserver des valeurs provenant de la fiche précédente.
        for master_key in list(self._field_masters):
            self._apply_master_relations(master_key)

    def _install_field_relations_runtime(self) -> None:
        """Branche une seule fois les contrôles vivants aux relations de champs."""
        # Libellé Maître : gras seulement, conformément à ERG-039.
        for key, widgets in getattr(self, "_model_field_widgets", {}).items():
            if not widgets:
                continue
            label = widgets[0]
            if isinstance(label, QLabel):
                base = QFont(label.font())
                if key in self._field_masters:
                    base.setBold(True)
                label.setFont(base)

        for master_key in set(self._field_masters):
            widget = self._relation_widget(master_key)
            if widget is None:
                continue
            prop = f"_mm3_master_relation_{master_key}"
            if widget.property(prop):
                continue
            widget.setProperty(prop, True)
            if isinstance(widget, QComboBox):
                widget.activated.connect(
                    lambda _index=0, k=master_key: self._apply_master_relations(k)
                )
                if widget.isEditable() and widget.lineEdit() is not None:
                    widget.lineEdit().editingFinished.connect(
                        lambda k=master_key: self._apply_master_relations(k)
                    )
            elif isinstance(widget, QLineEdit):
                widget.editingFinished.connect(
                    lambda k=master_key: self._apply_master_relations(k)
                )

        for linked_key in set(self._field_links):
            widget = self._relation_widget(linked_key)
            if widget is None:
                continue
            prop = f"_mm3_linked_relation_{linked_key}"
            if widget.property(prop):
                continue
            widget.setProperty(prop, True)
            if isinstance(widget, QComboBox):
                widget.activated.connect(
                    lambda _index=0, k=linked_key: self._propagate_linked_field(k)
                )
                if widget.isEditable() and widget.lineEdit() is not None:
                    edit = widget.lineEdit()
                    edit.editingFinished.connect(
                        lambda k=linked_key: self._propagate_linked_field(k)
                    )
                    # 11.7.70.14 — ne jamais propager un effacement pendant
                    # la frappe. Un champ Relié vide n'est validé qu'à la sortie
                    # du champ (editingFinished) ou par une validation explicite.
                    # Cela permet à Échap de restaurer l'ancienne valeur, même
                    # après suppression complète du contenu.
                    # edit.textChanged: volontairement NON connecté.
            elif isinstance(widget, QLineEdit):
                widget.editingFinished.connect(
                    lambda k=linked_key: self._propagate_linked_field(k)
                )
                # 11.7.70.14 — même règle pour un QLineEdit Relié :
                # le vide reste une modification en cours jusqu'à validation.
                # widget.textChanged: volontairement NON connecté.
            elif isinstance(widget, QPlainTextEdit):
                widget.textChanged.connect(
                    lambda k=linked_key: self._propagate_linked_field(k)
                )

    def refresh_collection_model_runtime(self) -> None:
        """Recharge le modèle dans une Fiche déjà ouverte.

        018.4.4.1.2.9 : supprime tout état de navigation hérité de l'ancien modèle
        avant de reconstruire placement, visibilité et ordre Tab/Entrée.
        """
        self._tab_field_keys = []
        self._apply_relations_after_model_refresh = True
        self._field_masters = set(
            self.model_manager.field_masters(int(self.collection["id"]))
        )
        self._field_links = dict(
            self.model_manager.field_links(int(self.collection["id"]))
        )

        # 23.9.3.6.5 — une nouvelle liaison s'applique aussi à l'historique :
        # compléter toutes les anciennes fiches du même Maître dont le champ relié
        # est encore vide, sans toucher aux anciennes valeurs non vides.
        try:
            self.model_manager.backfill_linked_blanks(int(self.collection["id"]))
        except Exception:
            pass

        # ModelDialog et RecordWindow utilisent chacun leur propre ModelManager.
        # Après une conversion Nombre -> Calculé, le cache du RecordWindow pouvait
        # donc conserver l'ancienne définition jusqu'au redémarrage de MM3.
        # Invalider explicitement ce cache avant de relire les champs rend le
        # changement immédiatement effectif sur les collections déjà existantes.
        try:
            self.model_manager._invalidate_custom_fields_cache(int(self.collection["id"]))
        except Exception:
            pass
        self._ensure_custom_field_widgets()
        self.apply_collection_model()
        # Recharge les valeurs avec les définitions fraîchement relues.
        # Les champs Date sont donc immédiatement réaffichés dans le nouveau format.
        self._load_custom_values_for_current_record()

        # 11.7.70.3 — refaire explicitement le calcul après reconstruction du
        # modèle. _load_custom_values_for_current_record() le fait déjà dans le
        # cas normal, mais ce second passage après le rafraîchissement graphique
        # couvre le changement à chaud Nombre -> Calculé sans nécessiter de
        # fermer/réouvrir la collection.
        self._recalculate_computed_fields()
        QTimer.singleShot(0, self._recalculate_computed_fields)
        QTimer.singleShot(50, self._recalculate_computed_fields)

        # Repartir d'un focus neutre évite que Qt rattache le prochain Tab à
        # l'ancien widget actif après un déplacement de champ.
        focused = QApplication.focusWidget()
        if focused is not None and self.isAncestorOf(focused):
            self.setFocus(Qt.FocusReason.OtherFocusReason)


    def _compact_banner_to_content(self):
        """018.4.4.1.2.9 — Bandeau ajusté à la géométrie réelle de son contenu."""
        section = getattr(self, "banner_section", None)
        if section is None:
            section = getattr(self, "bannerSection", None)
        if section is None:
            return

        layout = section.layout()
        if layout is not None:
            layout.setContentsMargins(4, 2, 4, 2)
            layout.setSpacing(2)

        # Ne surtout pas utiliser sizeHint() : il peut encore contenir
        # l'ancienne hauteur historique. On mesure les enfants visibles.
        max_bottom = 0
        min_top = None
        for child in section.findChildren(QWidget):
            if child is section or not child.isVisible():
                continue
            # Ignorer les descendants indirects : leur géométrie est locale
            # à leur propre parent et fausserait la mesure.
            if child.parentWidget() is not section:
                continue
            g = child.geometry()
            if g.height() <= 0:
                continue
            min_top = g.top() if min_top is None else min(min_top, g.top())
            max_bottom = max(max_bottom, g.bottom() + 1)

        if max_bottom <= 0 and layout is not None:
            # Secours : hauteur minimale issue du layout, sans réserve.
            max_bottom = layout.minimumSize().height()

        target = max(36, max_bottom + 4)
        section.setMinimumHeight(target)
        section.setMaximumHeight(target)
        section.updateGeometry()

        # Le Bandeau doit être séparé du premier groupe comme deux groupes
        # ordinaires : supprimer les marges verticales du conteneur parent.
        parent = section.parentWidget()
        if parent is not None and parent.layout() is not None:
            pl = parent.layout()
            m = pl.contentsMargins()
            pl.setContentsMargins(m.left(), 2, m.right(), 2)
            pl.setSpacing(6)


    def _record_group_geometry(self, name: str, style: dict, default: QRect) -> QRect:
        """Même espace géométrique que l'Atelier, avec migration 1.5.6."""
        geom = style.get("geometry", {}) if isinstance(style, dict) else {}
        if isinstance(geom, dict) and {"x", "y", "w", "h"} <= set(geom):
            try:
                x, y, w, h = (
                    int(geom["x"]), int(geom["y"]),
                    max(1, int(geom["w"])), max(1, int(geom["h"])),
                )
                if style.get("geometry_space") != "atelier_px":
                    # Les versions 1.5.6 sauvegardaient la géométrie logique
                    # divisée par le facteur 0,72 de la maquette compacte.
                    x = int(round(x * 0.72))
                    y = int(round(y * 0.72))
                    w = max(1, int(round(w * 0.72)))
                    h = max(1, int(round(h * 0.72)))
                return QRect(x, y, w, h)
            except Exception:
                pass
        return QRect(default)

    @staticmethod
    def _record_axis_overlap(a1: int, a2: int, b1: int, b2: int) -> bool:
        return min(a2, b2) >= max(a1, b1)

    def _normalize_record_group_contacts(self, names, tolerance: int = 18) -> None:
        """Compactage générique de la vraie Fiche, sans nom de bloc.

        Priorité au contact VERTICAL, car un bloc de rang inférieur peut être
        déjà parfaitement aligné à gauche : cet alignement ne doit jamais
        empêcher la suppression de l'espace situé au-dessus.
        """
        widgets = [
            (name, self._model_group_widgets.get(name))
            for name in names
        ]
        widgets = [(name, w) for name, w in widgets if w is not None and w.isVisible()]
        widgets.sort(key=lambda item: (item[1].y(), item[1].x()))

        for _ in range(3):
            changed = False

            for name, widget in widgets:
                rect = QRect(widget.geometry())
                others = [
                    QRect(other.geometry())
                    for other_name, other in widgets
                    if other_name != name
                ]

                # ---- 1. PRIORITÉ : contact vertical avec le rang supérieur ----
                above = [
                    o for o in others
                    if o.bottom() < rect.top()
                    and self._record_axis_overlap(
                        rect.left(), rect.right(), o.left(), o.right()
                    )
                ]
                if above:
                    # Frontière collective : le bord inférieur le plus bas de
                    # tous les blocs du rang supérieur qui recouvrent notre largeur.
                    frontier = max(o.bottom() + 1 for o in above)
                    gap = rect.top() - frontier
                    if 0 < gap <= tolerance:
                        candidate = QRect(rect)
                        candidate.moveTop(frontier)
                        if not any(candidate.intersects(o) for o in others):
                            widget.setGeometry(candidate)
                            rect = candidate
                            changed = True

                # ---- 2. Ensuite seulement : contact horizontal ----
                lefts = [
                    o for o in others
                    if o.right() < rect.left()
                    and self._record_axis_overlap(
                        rect.top(), rect.bottom(), o.top(), o.bottom()
                    )
                ]
                if lefts:
                    frontier = max(o.right() + 1 for o in lefts)
                    gap = rect.left() - frontier
                    if 0 < gap <= tolerance:
                        candidate = QRect(rect)
                        candidate.moveLeft(frontier)
                        if not any(candidate.intersects(o) for o in others):
                            widget.setGeometry(candidate)
                            changed = True

            if not changed:
                break


    def _schedule_runtime_surface_activation(self) -> None:
        """Fusionne les activations différées de la surface réelle de la Fiche.

        La construction initiale peut demander cette activation depuis plusieurs
        étapes (création de surface, application du modèle, tabulation). Une seule
        passe suffit une fois que Qt rend la main à sa boucle d'événements.
        """
        if getattr(self, "_runtime_surface_activation_pending", False):
            return
        self._runtime_surface_activation_pending = True

        def _run_once():
            self._runtime_surface_activation_pending = False
            try:
                self._activate_runtime_common_surface()
            except RuntimeError:
                # Fenêtre détruite entre la programmation et l'exécution.
                return

        QTimer.singleShot(0, _run_once)

    def _activate_runtime_common_surface(self) -> None:
        """Vraie Fiche = copie exacte de la maquette Atelier, sans outils."""
        surface = getattr(self, "_runtime_form_surface", None)
        if surface is None:
            return

        collection_id = int(self.collection["id"])
        placement = self.model_manager.field_placement(collection_id)
        visible = set(self.model_manager.visible_fields(collection_id))
        visual_positions = self.model_manager.visual_positions(collection_id, placement)
        visual_sizes = self.model_manager.visual_sizes(collection_id)
        group_styles = self.model_manager.group_styles(collection_id)
        layout_meta = group_styles.get("__mm3_layout__", {}) if isinstance(group_styles, dict) else {}
        absolute_fields = (
            isinstance(layout_meta, dict)
            and layout_meta.get("field_space") == "sheet_absolute_v1"
        )
        custom_labels = self.model_manager.custom_labels(collection_id)
        field_styles = self.model_manager.field_styles(collection_id)
        scale = DISPLAY_SCALE

        # 23.8.5.2 — le fond choisi dans l'Atelier est aussi le fond réel
        # de la fiche, pas seulement celui de ses cadres.
        sheet_background = self.model_manager.sheet_background(
            collection_id, "#EEF5F1"
        )
        surface.widget.setStyleSheet(
            f"background-color: {sheet_background};"
        )

        # 1 — Bloc = rectangle Atelier, strictement.
        groups = getattr(self, "_runtime_absolute_groups", None) or detach_surface_groups(surface)

        # 23.6.2 — les groupes utilisateur sont ajoutés après la surface standard,
        # exactement comme dans l'Atelier. Ils ne modifient jamais sa géométrie.
        for name, style in group_styles.items():
            if not (
                isinstance(style, dict)
                and bool(style.get("custom_group"))
                and name not in groups
            ):
                continue

            title_style = style.get("title", {})
            title_hidden = bool(
                isinstance(title_style, dict) and title_style.get("hidden")
            )
            visible_title = (
                str(title_style.get("text", "")).strip()
                if isinstance(title_style, dict) else ""
            )
            if title_hidden:
                visible_title = ""
            elif not visible_title:
                visible_title = str(style.get("display_title", "")).strip() or str(name)

            if visible_title == "Bandeau":
                visible_title = self._t("Bandeau")
            group = QGroupBox(visible_title, surface.widget)
            box = QVBoxLayout(group)
            if bool(style.get("custom_photo")):
                box.setContentsMargins(0, 0, 0, 0)
            else:
                box.setContentsMargins(6, 10, 6, 6)
            box.setSpacing(0)

            if bool(style.get("custom_photo")):
                canvas = PhotoLabel(group)
                canvas.setObjectName("photoPanel")
                canvas.setText("📷\nPhoto")
                # Le fond du cadre Photo suit la couleur choisie dans l'Atelier.
                photo_bg = str(style.get("background") or self.model_manager.sheet_background(collection_id, "#EEF5F1"))
                canvas.setStyleSheet(
                    f"background-color:{photo_bg}; border:none; border-radius:0px;"
                )
                canvas.setMinimumSize(0, 0)
                canvas.setMaximumSize(16777215, 16777215)
                canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
                canvas.copyRequested.connect(lambda s=name: self._copy_extra_photo(s))
                canvas.pasteRequested.connect(lambda s=name: self._paste_extra_photo(s))
                canvas.menuRequested.connect(lambda pos, s=name: self._show_extra_photo_menu(s, pos))
                canvas.imageDropped.connect(lambda image, s=name: self._set_extra_photo_from_image(s, image))
                canvas.resized.connect(lambda s=name: self._refresh_extra_photo_display(s))
                if bool(style.get("large_photo")):
                    if not hasattr(self, "_large_photo_slots"):
                        self._large_photo_slots = set()
                    self._large_photo_slots.add(name)
                self._extra_photo_widgets[name] = canvas
            else:
                canvas = RuntimeFormCanvas(name, self, group)
                canvas.setMinimumSize(0, 0)
                canvas.setMaximumSize(16777215, 16777215)
                canvas.setSizePolicy(
                    QSizePolicy.Policy.Expanding,
                    QSizePolicy.Policy.Expanding,
                )
                self._runtime_canvases[name] = canvas
            box.addWidget(canvas, 1)

            groups[name] = group

        self._runtime_absolute_groups = groups
        fallback_rects = canonical_group_rects(800)

        # Titres affichés : reprendre le texte mémorisé dans le style quand présent.
        for name, widget in groups.items():
            style = group_styles.get(name, {}) if isinstance(group_styles, dict) else {}
            if bool(isinstance(style, dict) and style.get("frame_deleted")):
                widget.hide()
                continue
            title_style = style.get("title", {}) if isinstance(style, dict) else {}
            if isinstance(title_style, dict) and bool(title_style.get("hidden")):
                title = ""
            else:
                title = (
                    str(title_style.get("text", "")).strip()
                    if isinstance(title_style, dict) else ""
                ) or str(style.get("display_title") or style.get("label") or name)

            # 23.7.7.1 — même règle que l'Atelier : absence de couleur propre
            # = héritage de la couleur de fond de la fiche.
            effective_style = dict(style) if isinstance(style, dict) else {}
            if not str(effective_style.get("background", "")).strip():
                effective_style["background"] = self.model_manager.sheet_background(
                    collection_id, "#EEF5F1"
                )
            if name == "Photo" or bool(effective_style.get("custom_photo")):
                effective_style["photo_frame"] = True
            apply_group_style(widget, effective_style, title)

            geom = style.get("geometry", {}) if isinstance(style, dict) else {}
            if isinstance(geom, dict) and {"x", "y", "w", "h"} <= set(geom):
                rect = QRect(
                    int(geom["x"]), int(geom["y"]),
                    max(1, int(geom["w"])), max(1, int(geom["h"])),
                )
            else:
                x, y, w, h = fallback_rects.get(name, (0, 0, 200, 100))
                rect = QRect(x, y, w, h)

            widget.setMinimumSize(0, 0)
            widget.setMaximumSize(16777215, 16777215)
            widget.setGeometry(rect)
            widget.setFixedSize(rect.size())
            widget.move(rect.topLeft())
            widget.show()
            if absolute_fields:
                widget.lower()

        self._load_extra_photos_for_current_record()

        # 2 — Affectation complète des champs.
        # Les champs du Bandeau sont structurels et n'appartiennent pas à DEFAULT_PLACEMENT.
        full_block = {}
        for group_name, keys in GROUPS:
            target = group_name
            for key in keys:
                if key != "photo_data":
                    full_block[key] = target
        for key, (block, _pos) in placement.items():
            full_block[key] = block

        # 3 — Même SharedFieldFrame, même géométrie ET même style que l'Atelier.
        def apply_atelier_part_style(widget, style, *, part: str) -> None:
            """Clone strict du style texte Atelier sur le vrai contrôle."""
            style = style if isinstance(style, dict) else {}
            base_font = QFont(QApplication.font())
            family = str(style.get("family", "")).strip() or base_font.family()
            size = int(style.get("size", 0) or 0)
            if size <= 0:
                size = max(1, base_font.pointSize())
            bold = bool(style.get("bold", False))
            italic = bool(style.get("italic", False))
            underline = bool(style.get("underline", False))

            font = QFont(base_font)
            font.setFamily(family)
            font.setPointSize(size)
            font.setBold(bold)
            font.setItalic(italic)
            font.setUnderline(underline)

            align_name = str(style.get("align", "left"))
            align = {
                "left": Qt.AlignmentFlag.AlignLeft,
                "center": Qt.AlignmentFlag.AlignHCenter,
                "right": Qt.AlignmentFlag.AlignRight,
            }.get(align_name, Qt.AlignmentFlag.AlignLeft)
            valign_name = str(style.get("valign", "center")) if part == "data" else "center"
            valign = {"top": Qt.AlignmentFlag.AlignTop, "center": Qt.AlignmentFlag.AlignVCenter, "bottom": Qt.AlignmentFlag.AlignBottom}.get(valign_name, Qt.AlignmentFlag.AlignVCenter)
            full_align = align | valign

            css_font = (
                f"font-family:'{family}'; font-size:{size}pt; "
                f"font-weight:{'700' if bold else '400'}; "
                f"font-style:{'italic' if italic else 'normal'}; "
                f"text-decoration:{'underline' if underline else 'none'};"
            )

            widget.setFont(QFont(font))
            try:
                widget.setAlignment(full_align)
            except Exception:
                pass
            if part == "data" and isinstance(widget, QPlainTextEdit):
                widget.setLineWrapMode(
                    QPlainTextEdit.LineWrapMode.WidgetWidth if bool(style.get("wrap", False))
                    else QPlainTextEdit.LineWrapMode.NoWrap
                )
                # QPlainTextEdit n'a pas d'alignement vertical natif. Les marges
                # de viewport reproduisent Haut/Centré/Bas sans toucher au texte.
                widget.document().setDefaultTextOption(widget.document().defaultTextOption())
                widget.setViewportMargins(0, 0, 0, 0)
                widget.setProperty("mm3_valign", valign_name)

            child_edit = None
            try:
                getter = getattr(widget, "lineEdit", None)
                child_edit = getter() if callable(getter) else None
            except Exception:
                child_edit = None

            if child_edit is not None:
                child_edit.setFont(QFont(font))
                try:
                    child_edit.setAlignment(full_align)
                except Exception:
                    pass

            if part == "label":
                color = str(style.get("color", "#24342C"))
                widget.setStyleSheet(
                    f"{css_font} color:{color}; background:transparent; "
                    "border:none; padding:2px 4px; margin:0px;"
                )
            else:
                color = str(style.get("color", "#8A9690"))
                widget.setStyleSheet(
                    f"{css_font} color:{color}; background:white; "
                    "border:1px solid #B9C7C0; border-radius:3px; "
                    "padding:2px 5px; margin:0px;"
                )
                if child_edit is not None:
                    child_edit.setStyleSheet(
                        f"{css_font} color:{color}; background:transparent; "
                        "border:none; padding:0px 5px; margin:0px;"
                    )

        for key, widgets in self._model_field_widgets.items():
            if key == "photo_data":
                continue
            if len(widgets) < 2 or widgets[1] is None:
                continue

            block = full_block.get(key)
            canvas = surface.widget if absolute_fields else self._runtime_canvases.get(block)
            if canvas is None:
                continue

            old_label = widgets[0]
            real_input = widgets[1]

            shell = self._runtime_field_shells.get(key)
            if shell is None:
                shell = SharedFieldFrame(canvas)
                shell.setObjectName(f"runtimeField_{key}")
                self._runtime_field_shells[key] = shell
            elif shell.parentWidget() is not canvas:
                shell.setParent(canvas)

            # Libellé neuf : aucun héritage visuel de l'ancienne vraie Fiche.
            label = getattr(shell, "_mm3_runtime_caption", None)
            if label is None:
                label = QLabel(canvas)
                label.setWordWrap(False)
                label.setStyleSheet(
                    "color:#24342C; background:#F7F9F8; "
                    "border:1px solid #D9E0DC; padding:2px 4px;"
                )
                shell._mm3_runtime_caption = label

            # Le libellé affiché par la vraie Fiche doit avoir exactement la
            # même source que celui de l'Atelier. L'ancien QLabel de la Fiche
            # contient encore quelques textes historiques codés en dur (par
            # exemple les deux champs de lien étaient tous deux « Lien »).
            # Il ne doit donc jamais servir de référence visuelle.
            spec = FIELD_BY_KEY.get(key)
            if spec is not None:
                default_label = spec.label
            else:
                default_label = str(self._custom_field_defs.get(key, {}).get("label", key))
            display_label = str(custom_labels.get(key, "") or default_label)
            # 2.3.24.6.10 : le numéro système garde son libellé propre.
            # Ne pas confondre avec un champ utilisateur importé intitulé « N° ».
            if key == "record_number":
                display_label = "N° de fiche"
            if key == "record_state" and str(self.language or "fr").lower().startswith("fr"):
                display_label = display_label.replace("État de la fiche", "Etat de la fiche")
            label.setText(self._t(display_label))

            whole_style = field_styles.get(key, {})
            if not isinstance(whole_style, dict):
                whole_style = {}
            apply_atelier_part_style(label, whole_style.get("label", {}), part="label")
            apply_atelier_part_style(real_input, whole_style.get("data", {}), part="data")

            if key == "record_number":
                # 018.4.4.1.5.22.8 — même rendu que l'Atelier :
                # historique par défaut, personnalisable par clic droit.
                whole = field_styles.get("record_number", {})
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
                    label, label_style,
                    default_size=max(8, label.font().pointSize()),
                    default_bold=False,
                    default_color="#111111",
                )
                apply_number_part(
                    real_input, data_style,
                    default_size=18,
                    default_bold=True,
                    # Numéro système : même couleur par défaut que le modèle
                    # maître. Une couleur explicitement enregistrée dans le
                    # style du champ reste prioritaire.
                    default_color="#963A30",
                )

            # Le vrai widget de saisie est le seul élément fonctionnel repris.
            try:
                real_input.setMinimumSize(0, 0)
                real_input.setMaximumSize(16777215, 16777215)
                real_input.setMinimumWidth(0)
                real_input.setMaximumWidth(16777215)
                real_input.setMinimumHeight(0)
                real_input.setMaximumHeight(16777215)
            except Exception:
                pass

            shell.set_scale(scale)
            shell.set_widgets(label, real_input)
            whole_style=field_styles.get(key,{})
            ls=whole_style.get("label",{}) if isinstance(whole_style,dict) else {}
            ds=whole_style.get("data",{}) if isinstance(whole_style,dict) else {}
            shell.set_part_geometry(
                label_x=ls.get("x"),label_w=ls.get("width"),
                data_x=ds.get("x"),data_w=ds.get("width"),
            )

            x, y = visual_positions.get(key, (12, 12))
            w, h = visual_sizes.get(key, (260, 31))
            rect = field_outer_rect(x, y, w, h, scale)
            shell.setGeometry(rect)
            if isinstance(real_input, QPlainTextEdit):
                try:
                    valign_name = str(ds.get("valign", "center"))
                    available = max(0, real_input.viewport().height())
                    content = min(available, int(real_input.document().size().height()) + 4)
                    spare = max(0, available - content)
                    top_margin = 0 if valign_name == "top" else spare if valign_name == "bottom" else spare // 2
                    real_input.setViewportMargins(0, top_margin, 0, 0)
                except Exception:
                    pass
            is_visible = (key == "record_number") or (key in visible)
            shell.setVisible(is_visible)
            label.setVisible(is_visible)
            real_input.setVisible(is_visible)
            if is_visible:
                # Important pour anciennes/autres collections : le widget réel
                # peut provenir d'un ancien groupe masqué. On le réaffiche
                # explicitement après reparentage dans la surface commune.
                label.show()
                real_input.show()
                canvas.show()
                if not absolute_fields:
                    parent_group = canvas.parentWidget()
                    if parent_group is not None:
                        parent_group.show()
                shell.show()
                shell.raise_()

        # 4 — Photo principale : reconstruire son canvas exactement comme un
        # cadre Photo supplémentaire. Le vieux PhotoLabel créé par la fiche
        # historique suivait un chemin Qt différent après reparentage et son
        # clic droit pouvait rester muet alors que Ctrl+V fonctionnait.
        # 11.4.25 — on remplace donc réellement ce widget par une nouvelle
        # instance PhotoLabel, avec les mêmes connexions que photo_slot_2.
        photo_group = groups.get("Photo")
        placeholder = surface.photo_placeholder
        if photo_group is not None:
            self._primary_photo_group = photo_group
            layout = photo_group.layout()
            if layout is not None:
                layout.setContentsMargins(0, 0, 0, 0)
                layout.setSpacing(0)
                layout.removeWidget(placeholder)
            placeholder.hide()

            old_photo_label = getattr(self, "photo_label", None)
            if old_photo_label is not None:
                try:
                    if layout is not None:
                        layout.removeWidget(old_photo_label)
                    old_photo_label.hide()
                    old_photo_label.setParent(None)
                    old_photo_label.deleteLater()
                except RuntimeError:
                    pass

            canvas = PhotoLabel(photo_group)
            canvas.setObjectName("photoPanel")
            canvas.setText("📷\nPhoto")
            # Même couleur que le cadre Photo dans l'Atelier.
            photo_style = group_styles.get("Photo", {})
            photo_bg = str(photo_style.get("background") or self.model_manager.sheet_background(collection_id, "#EEF5F1"))
            canvas.setStyleSheet(
                f"background-color:{photo_bg}; border:none; border-radius:0px;"
            )
            canvas.setMinimumSize(0, 0)
            canvas.setMaximumSize(16777215, 16777215)
            canvas.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
            )
            canvas.setToolTip(
                "Cliquez pour sélectionner le cadre. Ctrl + C pour copier, Ctrl + V pour coller. "
                "Clic droit pour les options."
            )
            canvas.copyRequested.connect(self._copy_photo)
            canvas.pasteRequested.connect(self._paste_photo)
            canvas.menuRequested.connect(self._show_photo_menu)
            canvas.imageDropped.connect(self._set_photo_from_image)
            canvas.resized.connect(self._refresh_photo_display)
            # Utiliser aussi le mécanisme Qt natif de menu contextuel : c'est
            # exactement le même signal pour la première et les suivantes.
            canvas.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            canvas.customContextMenuRequested.connect(
                lambda pos, w=canvas: self._show_photo_menu(w.mapToGlobal(pos))
            )
            self.photo_label = canvas
            if layout is not None:
                layout.addWidget(canvas)
            canvas.show()
            try:
                photo_group.raise_()
                canvas.raise_()
            except RuntimeError:
                pass
            # Si la fiche est reconstruite après un passage par l'Atelier,
            # réafficher immédiatement l'image déjà en mémoire.
            try:
                self._refresh_photo_display()
            except Exception:
                pass

        # 5 — Taille de la surface = union exacte des blocs, comme l'Atelier.
        right = 0
        bottom = 0
        for widget in groups.values():
            if not widget.isVisible():
                continue
            g = widget.geometry()
            right = max(right, g.right() + 1)
            bottom = max(bottom, g.bottom() + 1)
        if absolute_fields:
            for shell in self._runtime_field_shells.values():
                if shell is not None and shell.isVisible() and shell.parentWidget() is surface.widget:
                    g = shell.geometry()
                    right = max(right, g.right() + 1)
                    bottom = max(bottom, g.bottom() + 1)

        root = surface.widget
        root.setMinimumSize(max(1, right), max(1, bottom))
        root.setMaximumSize(max(1, right), max(1, bottom))
        root.resize(max(1, right), max(1, bottom))
        root.show()


        # 23.9.2.7 — tous les widgets ont maintenant leur parent définitif.
        self._install_runtime_navigation()

        # 23.9.3.6.2 — les relations doivent être branchées APRÈS le reparentage
        # définitif de la vraie Fiche. En 9.3.6.0/6.1 le moteur était présent,
        # mais cette installation n'était jamais appelée : l'Atelier enregistrait
        # donc correctement Maître/Relié à, sans effet dans la vraie Fiche.
        self._install_field_relations_runtime()

        # 23.9.3.6.4 — point d'autorité : le modèle, les widgets réels et les
        # liaisons sont maintenant tous reconstruits. Si l'on revient de
        # l'Atelier, appliquer ici les valeurs Maître déjà présentes.
        if self._apply_relations_after_model_refresh:
            self._apply_relations_after_model_refresh = False
            self._apply_current_master_relations()

    def _activate_record_free_group_layout(self) -> None:
        """Un seul plan géométrique pour Atelier et vraie Fiche, Bandeau compris."""
        host = getattr(self, "_record_blocks_host", None)
        grid = getattr(self, "_record_blocks_grid", None)
        card_layout = getattr(self, "_record_card_layout", None)
        if host is None or grid is None or not hasattr(self, "_model_group_widgets"):
            return

        names = ("Bandeau", "Identification", "Photo", "Localisation", "Aspect", "Acquisition", "Collection")
        styles = self.model_manager.group_styles(int(self.collection["id"]))

        if not self._record_free_group_defaults:
            banner = self._model_group_widgets.get("Bandeau")
            banner_h = banner.height() if banner is not None else 120

            # Bandeau : il quitte le QVBoxLayout général et rejoint la même surface.
            if banner is not None:
                if card_layout is not None:
                    card_layout.removeWidget(banner)
                self._record_free_group_defaults["Bandeau"] = QRect(
                    0, 0, max(1, host.width()), max(1, banner_h)
                )
                banner.setParent(host)

            # Les autres blocs sont actuellement dans la grille située sous le
            # Bandeau. Pour leur défaut historique on les décale simplement de la
            # hauteur du Bandeau ; une géométrie Atelier enregistrée prime ensuite.
            for name in names[1:]:
                widget = self._model_group_widgets.get(name)
                if widget is None:
                    continue
                g = QRect(widget.geometry())
                g.translate(0, banner_h)
                self._record_free_group_defaults[name] = g
                grid.removeWidget(widget)
                widget.setParent(host)

        right = 0
        bottom = 0
        for name in names:
            widget = self._model_group_widgets.get(name)
            default = self._record_free_group_defaults.get(name)
            if widget is None or default is None:
                continue
            style = styles.get(name, {}) if isinstance(styles, dict) else {}
            if bool(isinstance(style, dict) and style.get("frame_deleted")):
                widget.hide()
                continue
            geom = self._record_group_geometry(name, style, default)

            # 018.4.4.1.5.22.8 — rectangle Atelier = rectangle Fiche, sans
            # négociation de taille par le layout interne Qt.
            layout = widget.layout()
            if layout is not None:
                layout.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)

            widget.setMinimumSize(0, 0)
            widget.setMaximumSize(16777215, 16777215)
            widget.setGeometry(geom)
            widget.setFixedSize(geom.size())
            widget.move(geom.topLeft())
            widget.show()

            right = max(right, geom.right() + 1)
            bottom = max(bottom, geom.bottom() + 1)

        # 018.4.4.1.5.22.8 — fidélité stricte Atelier = Fiche :
        # aucun compactage automatique. Un espace laissé dans l'Atelier reste
        # un espace dans la Fiche ; deux blocs accolés restent simplement accolés.
        right = 0
        bottom = 0
        for name in names:
            widget = self._model_group_widgets.get(name)
            if widget is not None and widget.isVisible():
                right = max(right, widget.geometry().right() + 1)
                bottom = max(bottom, widget.geometry().bottom() + 1)

        # Aucune marge cachée : la surface s'arrête exactement à la dernière bordure.
        host.setMinimumSize(max(1, right), max(1, bottom))
        host.setMaximumHeight(max(1, bottom))
        host.resize(max(host.width(), right), max(1, bottom))

        # Aucun second passage de compactage : la géométrie enregistrée par
        # l'Atelier reste l'autorité finale après stabilisation de Qt.


    def apply_collection_model(self) -> None:
        """018.4.4.1.2.9 — applique le modèle visuel Atelier directement à la vraie Fiche."""
        if not hasattr(self, "_model_field_widgets"):
            return

        # 23.9.2.9 — reconstruire TOUJOURS la navigation avant le retour
        # rapide lié à la surface commune. Depuis 018.4.4.1.5.22.8 cette surface
        # existe déjà à l'arrivée ici : l'ancien retour empêchait donc totalement
        # la création de _tab_field_keys dans la vraie Fiche.
        self._rebuild_runtime_tab_keys()

        # 018.4.4.1.5.22.8 — aucune reconstruction par l'ancienne Fiche.
        # La surface Atelier est désormais l'unique moteur visuel.
        if getattr(self, "_runtime_form_surface", None) is not None:
            self._schedule_runtime_surface_activation()
            return
        collection_id = int(self.collection["id"])
        visible = self.model_manager.visible_fields(collection_id)
        custom_labels = self.model_manager.custom_labels(collection_id)
        placement = self.model_manager.field_placement(collection_id)
        visual_positions = self.model_manager.visual_positions(collection_id, placement)
        visual_sizes = self.model_manager.visual_sizes(collection_id)
        field_styles = self.model_manager.field_styles(collection_id)
        group_styles = self.model_manager.group_styles(collection_id)
        if getattr(self, "_runtime_form_surface", None) is not None:
            self._schedule_runtime_surface_activation()

        # Capturer une seule fois les propriétés visuelles MM3 d'origine.
        # Les appels suivants commencent toujours de cette référence : supprimer
        # un style personnalisé restitue donc réellement le style par défaut.
        if not hasattr(self, "_model_default_widget_styles"):
            self._model_default_widget_styles = {}
            for key, widgets in self._model_field_widgets.items():
                for index, widget in enumerate(widgets[:2]):
                    if widget is not None:
                        self._model_default_widget_styles[(key, index)] = (
                            QFont(widget.font()),
                            widget.styleSheet(),
                        )

        for key, widgets in self._model_field_widgets.items():
            for index, widget in enumerate(widgets[:2]):
                if widget is None:
                    continue
                baseline = self._model_default_widget_styles.get((key, index))
                if baseline is not None:
                    base_font, base_sheet = baseline
                    widget.setFont(QFont(base_font))
                    widget.setStyleSheet(base_sheet)

        # La couleur appartient à la collection et suit immédiatement le modèle.
        self._apply_style()

        # 018.4.4.1.2.9 — fond et cadre propres à chaque groupe.
        for block_name, widget in getattr(self, "_model_group_widgets", {}).items():
            style = group_styles.get(block_name, {}) if isinstance(group_styles, dict) else {}
            background = str(style.get("background", "#FAFCFB"))
            border = str(style.get("border", "#C5D2CB"))
            try:
                border_width = max(0, min(4, int(style.get("border_width", 1))))
            except Exception:
                border_width = 1
            # Style uniquement du conteneur, jamais de ses enfants.
            # Utilise le nom d'objet du QFrame pour éviter que la couleur de fond
            # du groupe se propage aux zones de saisie.
            object_name = widget.objectName()
            if object_name:
                widget.setStyleSheet(
                    f"QFrame#{object_name} {{ "
                    f"background-color: {background}; "
                    f"border: {border_width}px solid {border}; "
                    f"border-radius: 8px; "
                    f"}}"
                )
            else:
                widget.setStyleSheet(
                    f"QFrame {{ background-color: {background}; "
                    f"border: {border_width}px solid {border}; border-radius: 8px; }}"
                )

            title_style = style.get("title", {}) if isinstance(style.get("title"), dict) else {}
            display_title = str(title_style.get("text", "")).strip() or block_name
            if str(getattr(self, "language", "fr") or "fr").lower().startswith("de"):
                display_title = {"Photo du site": "Fundortfoto", "Photo du sable": "Sandfoto"}.get(display_title, display_title)
            # 1.0.3 — Les noms structurels restent en français dans le modèle/.coldb
            # pour préserver la compatibilité, mais leur libellé visible suit la langue.
            # Un titre réellement personnalisé par l'utilisateur reste inchangé.
            if display_title == block_name:
                display_title = self._t(block_name)
            for label in widget.findChildren(QLabel):
                # Le nom technique reste block_name. On reconnaît le QLabel titre
                # soit par son ancien titre technique, soit par le titre affiché
                # précédemment, puis on ne change que son texte visible.
                previous_display = str(label.property("_mm3_group_display_title") or "").strip()
                if label.text().strip() != block_name and previous_display != label.text().strip():
                    continue
                label.setProperty("_mm3_group_display_title", display_title)
                label.setText(display_title)
                font = QFont(label.font())
                family = str(title_style.get("family", "")).strip()
                if family:
                    font.setFamily(family)
                size = int(title_style.get("size", 0) or 0)
                if size > 0:
                    font.setPointSize(size)
                font.setBold(bool(title_style.get("bold", True)))
                font.setItalic(bool(title_style.get("italic", False)))
                font.setUnderline(bool(title_style.get("underline", False)))
                label.setFont(font)
                # #sectionTitle fixe historiquement la taille à 17 px dans la feuille
                # globale. Une règle QSS a priorité sur QFont : il faut donc poser
                # explicitement la taille choisie sur le QLabel du titre.
                title_size = int(title_style.get("size", 0) or 0)
                css_size = f"font-size: {title_size}pt; " if title_size > 0 else ""
                label.setStyleSheet(
                    f"color: {title_style.get('color', '#000000')}; "
                    f"{css_size}"
                    "background: transparent; border: none;"
                )

        # Libellés + visibilité.
        for key, widgets in self._model_field_widgets.items():
            show = key in visible
            for widget in widgets:
                if widget is not None:
                    widget.setVisible(show)
            if widgets and isinstance(widgets[0], QLabel):
                spec = FIELD_BY_KEY.get(key)
                if spec is not None:
                    default_label = spec.label
                else:
                    default_label = str(self._custom_field_defs.get(key, {}).get("label", key))
                display_label = str(custom_labels.get(key, default_label))
                if key == "record_state" and str(self.language or "fr").lower().startswith("fr"):
                    display_label = display_label.replace("État de la fiche", "Etat de la fiche")
                widgets[0].setText(self._t(display_label))

        # 018.4.4.1.2.9 — mise en forme distincte Libellé / Donnée.
        for key, styles in field_styles.items():
            widgets = self._model_field_widgets.get(key, [])
            if not widgets:
                continue

            for target, index, default_color in (
                ("label", 0, "#24342C"),
                ("data", 1, "#24342C"),
            ):
                if index >= len(widgets) or widgets[index] is None:
                    continue
                style = styles.get(target, {})
                if not style:
                    continue

                widget = widgets[index]
                font = QFont(widget.font())
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

                color = str(style.get("color", default_color))
                current_sheet = widget.styleSheet().strip()
                if current_sheet and not current_sheet.endswith(";"):
                    current_sheet += ";"
                # La taille doit gagner même si le widget possède déjà une feuille
                # de style Qt : certaines feuilles peuvent sinon neutraliser setFont().
                font_css = ""
                if size > 0:
                    font_css += f" font-size: {size}pt;"
                if family:
                    safe_family = family.replace("'", "\\'")
                    font_css += f" font-family: '{safe_family}';"
                widget.setStyleSheet(current_sheet + f" color: {color};" + font_css)

                # 018.4.4.1.4.1 — justification indépendante Libellé / Donnée.
                align_name = str(style.get("align", "left"))
                align_flag = {
                    "left": Qt.AlignmentFlag.AlignLeft,
                    "center": Qt.AlignmentFlag.AlignHCenter,
                    "right": Qt.AlignmentFlag.AlignRight,
                }.get(align_name, Qt.AlignmentFlag.AlignLeft)
                full_alignment = align_flag | Qt.AlignmentFlag.AlignVCenter

                if isinstance(widget, QLabel):
                    widget.setAlignment(full_alignment)
                elif isinstance(widget, QLineEdit):
                    widget.setAlignment(full_alignment)
                elif isinstance(widget, QComboBox):
                    if widget.lineEdit() is not None:
                        widget.lineEdit().setAlignment(full_alignment)
                elif isinstance(widget, QPlainTextEdit):
                    cursor = widget.textCursor()
                    cursor.select(QTextCursor.SelectionType.Document)
                    block_format = QTextBlockFormat()
                    block_format.setAlignment(align_flag)
                    cursor.mergeBlockFormat(block_format)
                    widget.setTextCursor(cursor)

        # 018.4.4.1.2.9 — moteur géométrique commun Atelier/Fiche.
        # Aucune reconstruction QGrid/QForm : X/Y/W/H enregistrés dans l'Atelier
        # sont appliqués tels quels dans une zone de contenu propre à chaque groupe.
        banner_keys = ("mineral_name", "mineral_2", "mineral_3", "record_state")

        # Vider les anciens layouts Qt : ils ne doivent plus décider de la position
        # ni de l'espacement vertical des champs.
        for layout in getattr(self, "_model_block_layouts", {}).values():
            try:
                layout.setAlignment(Qt.AlignmentFlag.AlignTop)
            except Exception:
                pass
            for key, widgets in self._model_field_widgets.items():
                for widget in widgets[:2]:
                    if widget is not None:
                        layout.removeWidget(widget)

        by_block = {name: [] for name in self._model_content_canvases}

        # Champs mobiles, y compris les champs créés par l'utilisateur.
        for key, (block, position) in placement.items():
            if block not in by_block:
                continue
            x, y = visual_positions.get(key, (12, int(position) * 38 + 12))
            width, height = visual_sizes.get(key, (260, 31))
            by_block[block].append(
                (int(x), int(y), int(width), int(height), key)
            )

        # Bandeau structurel : son groupe est fixe, mais sa géométrie est libre.
        for position, key in enumerate(banner_keys):
            if key not in self._model_field_widgets:
                continue
            x, y = visual_positions.get(key, (12, position * 38 + 12))
            width, height = visual_sizes.get(key, (260, 31))
            by_block["Bandeau"].append(
                (int(x), int(y), int(width), int(height), key)
            )

        # 018.4.4.1.5.22.8 — les champs ne sont plus reconstruits :
        # ils utilisent directement le même SharedFieldFrame que l'Atelier.
        # 018.4.4.1.5.22.8 — même échelle visuelle que "Ajuster à l'écran".
        # Le modèle stocke les champs en coordonnées logiques historiques ;
        # la vraie Fiche les rend désormais comme la maquette validée.
        FIELD_GEOMETRY_SCALE = DISPLAY_SCALE

        for block, items in by_block.items():
            canvas = self._model_content_canvases.get(block)
            if canvas is None:
                continue

            # 018.4.4.1.2.9 — géométrie universelle :
            # aucun bloc (y compris Identification) n'a de traitement privilégié.
            min_height = 36
            compact_blocks = set(self._model_group_widgets.keys())
            max_bottom = min_height

            for x, y, width, height, key in sorted(
                items, key=lambda item: (item[1], item[0], item[4])
            ):
                shared_rect = field_outer_rect(
                    x, y, width, height, FIELD_GEOMETRY_SCALE
                )
                x = shared_rect.x()
                y = shared_rect.y()
                width = shared_rect.width()
                height = shared_rect.height()
                widgets = self._model_field_widgets.get(key, [])
                if len(widgets) < 2 or widgets[0] is None or widgets[1] is None:
                    continue

                label, field = widgets[0], widgets[1]

                # MODE SAISIE = le même composant que l'Atelier.
                shell = self._model_field_shells.get(key)
                if shell is None:
                    shell = SharedFieldFrame(canvas)
                    shell.setObjectName(f"mm3FieldShell_{key}")
                    self._model_field_shells[key] = shell
                elif shell.parentWidget() is not canvas:
                    shell.setParent(canvas)

                shell.set_scale(FIELD_GEOMETRY_SCALE)
                shell.set_widgets(label, field)
                shell.setGeometry(shared_rect)

                is_visible = key in visible
                shell.setVisible(is_visible)
                label.setVisible(is_visible)
                field.setVisible(is_visible)
                if is_visible:
                    shell.raise_()

                bottom_margin = 4 if block in compact_blocks else 6
                max_bottom = max(max_bottom, int(y) + int(height) + bottom_margin)

            # 018.4.4.1.2.9 — aucun champ ne peut être tronqué : le canvas et son
            # groupe prennent la hauteur nécessaire. Le QScrollArea absorbe ensuite
            # l'éventuel dépassement de la fenêtre.
            # 018.4.4.1.2.9 — conserver STRICTEMENT la géométrie verticale
            # compacte de 1.2.7.1. On ne touche ni au haut du canvas, ni à la
            # position du titre, ni à celle des champs. On agrandit seulement
            # le bord inférieur si le dernier champ descend plus bas.
            required_height = max(min_height, max_bottom)
            canvas.setFixedHeight(required_height)
            canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

            section = self._model_group_widgets.get(block)
            if section is not None:
                sl = section.layout()
                if block in compact_blocks and sl is not None:
                    mg = sl.contentsMargins()
                    sl.setContentsMargins(mg.left(), 1, mg.right(), 1)
                    sl.setSpacing(0)
                    sl.setAlignment(Qt.AlignmentFlag.AlignTop)

                # 018.4.4.1.2.11 — laisser QVBoxLayout calculer lui-même la hauteur
                # extérieure du groupe à partir du canvas fixé ci-dessus.
                # La version 1.2.10 recalculait cette hauteur à la main (titre +
                # marges + canvas) puis imposait un maximum : selon le style Qt,
                # ce maximum pouvait être inférieur de quelques pixels à
                # l'encombrement réel et tronquait systématiquement le dernier
                # champ. Le haut/titre reste inchangé ; seul le bas devient naturel.
                section.setMinimumHeight(0)
                section.setMaximumHeight(16777215)
                if sl is not None:
                    sl.invalidate()
                    sl.activate()
                section.updateGeometry()

        # Le conteneur complet doit lui aussi conserver la somme des hauteurs
        # naturelles des rangées. Ainsi Qt fait défiler au lieu de les écraser.
        try:
            blocks.activate()
            card_layout.activate()
            # La hauteur est désormais dictée par recordBlocksHost, qui contient
            # Bandeau + tous les blocs dans le même repère.
            card.setMinimumHeight(0)
        except Exception:
            pass

        # Afficher un bloc uniquement s'il contient au moins un champ actif.
        for block, section in getattr(self, "_model_block_sections", {}).items():
            assigned = {
                key for key, (target, _pos) in placement.items()
                if target == block
            }
            section.setVisible(bool(assigned & visible))

        # Photo reste un bloc structurel indépendant.
        for section, fields in getattr(self, "_model_sections", {}).items():
            if fields == {"photo_data"}:
                section.setVisible("photo_data" in visible)

        # 018.4.4.1.2.9 — ordre de tabulation personnalisable.
        # Par défaut il suit la disposition visuelle ; un ordre enregistré peut
        # ensuite être totalement indépendant de cette disposition.
        visual_default = []
        for group_title, keys in GROUPS:
            if group_title == "Bandeau":
                visual_default.extend(key for key in keys if key != "photo_data")
                break
        for block in MODEL_BLOCKS:
            entries = [
                (int(pos), key)
                for key, (target, pos) in placement.items()
                if target == block and key != "photo_data"
            ]
            entries.sort(key=lambda item: (item[0], item[1]))
            visual_default.extend(key for _pos, key in entries)
        for _group_title, keys in GROUPS:
            for key in keys:
                if key != "photo_data" and key not in visual_default:
                    visual_default.append(key)

        tab_keys = self.model_manager.tab_order(collection_id, visual_default)

        # Conserver l'ordre sous forme de clés de champs, pas de widgets internes.
        # Les QComboBox éditables peuvent recréer / déplacer leur QLineEdit interne ;
        # mémoriser ces QLineEdit rendait la chaîne instable et ramenait le focus sur Nom.
        self._tab_field_keys = [
            key
            for key in tab_keys
            if key in visible
            and key in self._model_field_widgets
            and len(self._model_field_widgets.get(key, [])) >= 2
            and self._model_field_widgets[key][1] is not None
        ]

        # 23.9.2.6 — imposer aussi cet ordre à la chaîne NATIVE de Qt.
        # C'est essentiel : sous Windows, QWidget peut traiter Tab via
        # focusNextPrevChild() avant/à la place d'un KeyPress classique.
        # L'Atelier devient donc l'unique source d'ordre aussi pour Qt lui-même.
        # 23.9.2.7 — la chaîne de navigation ne peut être installée qu'APRÈS
        # le reparentage final des vrais widgets dans la surface commune.
        self._schedule_runtime_surface_activation()
        QTimer.singleShot(0, self._install_field_relations_runtime)

    def _nav_diag(self, message: str) -> None:
        # Ancien diagnostic 9.2.8 définitivement désactivé.
        return

    def _nav_diag_snapshot(self, reason: str) -> None:
        return

    def _field_focus_target(self, key: str):
        """Retourne (conteneur_visible, widget_focus) pour un champ logique."""
        # Cas composites : dans le modèle, le second widget est le conteneur
        # ligne + bouton. Pour la tabulation, on veut le vrai QLineEdit.
        explicit = {
            "internet_link": getattr(self, "internet_link_edit", None),
            "site_internet_link": getattr(self, "site_link_edit", None),
        }
        if key in explicit and explicit[key] is not None:
            widgets = self._model_field_widgets.get(key, [])
            container = widgets[1] if len(widgets) >= 2 else explicit[key]
            return container, explicit[key]

        widgets = self._model_field_widgets.get(key, [])
        if len(widgets) < 2 or widgets[1] is None:
            return None, None

        field = widgets[1]

        # Pour les listes éditables, le conteneur QComboBox décide de la visibilité,
        # mais le vrai contrôle recevant le curseur est son QLineEdit interne.
        if isinstance(field, QComboBox) and field.isEditable() and field.lineEdit() is not None:
            return field, field.lineEdit()

        return field, field

    def _rebuild_runtime_tab_keys(self) -> None:
        """Reconstruit la chaîne Tab/Entrée directement depuis l'Atelier.

        23.9.2.9 — la surface graphique commune est créée AVANT
        ``apply_collection_model()``. L'ancien code quittait donc cette méthode
        prématurément et n'atteignait jamais le bloc qui remplissait
        ``_tab_field_keys``. L'ordre était bien enregistré dans la base, mais la
        vraie Fiche gardait une chaîne vide.

        Cette reconstruction est volontairement indépendante de la géométrie :
        ``tab_position`` est l'autorité, pour les champs historiques comme
        personnalisés et quels que soient leurs cadres.
        """
        if not hasattr(self, "_model_field_widgets"):
            self._tab_field_keys = []
            return

        collection_id = int(self.collection["id"])
        visible = self.model_manager.visible_fields(collection_id)
        try:
            default_order = list(self.model_manager.all_model_keys(collection_id))
        except Exception:
            default_order = list(self._model_field_widgets.keys())
        tab_keys = self.model_manager.tab_order(collection_id, default_order)

        self._tab_field_keys = [
            key
            for key in tab_keys
            if key in visible
            and key in self._model_field_widgets
            and len(self._model_field_widgets.get(key, [])) >= 2
            and self._model_field_widgets[key][1] is not None
        ]
        self._nav_diag(f"REBUILD tab keys={self._tab_field_keys}")

    def _install_runtime_navigation(self) -> None:
        """Installe la navigation sur les widgets APRÈS leur reparentage final."""
        # 23.9.2.9 — dernier recalcul après création des champs personnalisés et
        # reparentage final. Tab et Entrée travaillent ainsi sur la même chaîne.
        self._rebuild_runtime_tab_keys()
        for key in getattr(self, "_tab_field_keys", []):
            container, target = self._field_focus_target(key)
            for widget in (container, target):
                if not isinstance(widget, QWidget):
                    continue
                widget.setProperty("_mm3_field_key", key)
                try:
                    widget.removeEventFilter(self)
                except Exception:
                    pass
                widget.installEventFilter(self)
            if isinstance(container, QComboBox) and container.lineEdit() is not None:
                edit = container.lineEdit()
                edit.setProperty("_mm3_field_key", key)
                try:
                    edit.removeEventFilter(self)
                except Exception:
                    pass
                edit.installEventFilter(self)
        self._apply_native_tab_order()
        self._nav_diag_snapshot("navigation installed after runtime surface")

    def _apply_native_tab_order(self) -> None:
        """Injecte l'ordre Atelier dans la chaîne native de focus de Qt."""
        widgets = []
        for key in self._available_tab_field_keys():
            container, target = self._field_focus_target(key)
            widget = container if isinstance(container, QWidget) else target
            if not isinstance(widget, QWidget):
                continue
            if widget.focusPolicy() == Qt.FocusPolicy.NoFocus:
                widget = target
            if isinstance(widget, QWidget) and widget not in widgets:
                widgets.append(widget)

        for first, second in zip(widgets, widgets[1:]):
            try:
                QWidget.setTabOrder(first, second)
            except Exception:
                pass

    def focusNextPrevChild(self, next: bool) -> bool:  # noqa: A002, N802
        """Dernier garde-fou : Tab/Shift+Tab suivent toujours l'ordre Atelier."""
        if self.isVisible():
            delta = 1 if next else -1
            if self._focus_relative_tab_field(delta):
                return True
        return super().focusNextPrevChild(next)

    def _focused_model_key(self) -> str | None:
        focused = QApplication.focusWidget()
        if focused is None:
            return None

        for key in getattr(self, "_tab_field_keys", []):
            container, target = self._field_focus_target(key)
            if target is None:
                continue
            if focused is target or focused is container:
                return key
            if isinstance(container, QWidget) and container.isAncestorOf(focused):
                return key
            if isinstance(target, QWidget) and target.isAncestorOf(focused):
                return key
        return None

    def _available_tab_field_keys(self) -> list[str]:
        """Chaîne GLOBALE réellement focalisable de la Fiche.

        L'ordre vient exclusivement de ``tab_position`` (ou de l'ordre visuel
        de secours calculé par l'Atelier). Les champs structurels/non éditables
        comme N° et Coût total, les photos et les widgets masqués ne doivent
        jamais polluer cette chaîne.
        """
        keys: list[str] = []
        for key in getattr(self, "_tab_field_keys", []):
            container, target = self._field_focus_target(key)
            if container is None or target is None:
                continue
            if not container.isVisibleTo(self) or not container.isEnabled():
                continue
            if not target.isEnabled():
                continue

            # Un QLabel (N°) n'est pas un champ de saisie. Un QLineEdit en
            # lecture seule (Coût total) est affiché mais doit être sauté.
            if isinstance(target, QLineEdit) and target.isReadOnly():
                continue
            if not isinstance(target, (QLineEdit, QComboBox, QPlainTextEdit)):
                continue
            keys.append(key)
        return keys

    def _focus_relative_tab_field(self, delta: int = 1, source_key: str | None = None) -> bool:
        """Déplace le focus dans l'unique chaîne globale Tab/Entrée."""
        keys = self._available_tab_field_keys()
        if not keys:
            self._nav_diag(f"MOVE delta={delta} source={source_key} -> ABORT no available keys")
            return False

        current_key = source_key if source_key in keys else self._focused_model_key()
        if current_key in keys:
            index = keys.index(current_key)
            target_key = keys[(index + delta) % len(keys)]
        else:
            target_key = keys[0] if delta >= 0 else keys[-1]

        _container, target = self._field_focus_target(target_key)
        if target is None:
            self._nav_diag(f"MOVE current={current_key} target={target_key} -> ABORT target None")
            return False

        self._nav_diag(
            f"MOVE delta={delta} source={source_key} current={current_key} -> {target_key} "
            f"target={type(target).__name__} visible={target.isVisible()} enabled={target.isEnabled()}"
        )
        target.setFocus(
            Qt.FocusReason.TabFocusReason
            if delta >= 0 else Qt.FocusReason.BacktabFocusReason
        )
        if isinstance(target, QLineEdit):
            target.selectAll()
        return True

    def _model_key_for_widget(self, widget) -> str | None:
        """Retrouve la clé MM3 du contrôle réel de la vraie Fiche."""
        if widget is None:
            return None
        current = widget if isinstance(widget, QWidget) else None
        while isinstance(current, QWidget):
            value = current.property("_mm3_field_key")
            if value:
                return str(value)
            current = current.parentWidget()
        for key in getattr(self, "_tab_field_keys", []):
            container, target = self._field_focus_target(key)
            if container is None or target is None:
                continue
            if widget is target or widget is container:
                return key
            if isinstance(container, QWidget) and isinstance(widget, QWidget):
                if container.isAncestorOf(widget):
                    return key
            if isinstance(target, QWidget) and isinstance(widget, QWidget):
                if target.isAncestorOf(widget):
                    return key
        return None

    def _focus_next_tab_field(self) -> None:
        """Demande l'avancement global après une validation réussie.

        Pendant le traitement d'Entrée, les validateurs historiques continuent
        d'appeler cette méthode, mais elle ne déplace plus le focus elle-même :
        elle signale seulement que la validation autorise l'avancement. Entrée
        et Tab passent ensuite par le MÊME moteur explicite.
        """
        if getattr(self, "_enter_validation_in_progress", False):
            self._enter_validation_allows_advance = True
            return
        self._focus_relative_tab_field(1)


    def _apply_style(self) -> None:
        sheet_background = self.model_manager.sheet_background(
            int(self.collection["id"]), "#EEF5F1"
        )
        self.setStyleSheet(
            f"""
            #recordRoot {{ background: {sheet_background}; color: #000000; }}
            #recordTitle {{ font-size: 24px; font-weight: 700; }}
            #positionLabel {{ color: #607068; font-size: 14px; }}
            #recordCard {{ background: white; border: 1px solid #AABBB2; border-radius: 10px; }}
            #dataSection {{ background: #FAFCFB; border: 1px solid #C5D2CB; border-radius: 8px; }}
            #fieldCaption {{ font-size: 15px; color: #000000; }}
            #recordNumber {{ font-size: 30px; font-weight: 700; color: #496C5B; padding-left: 10px; }}
            QFormLayout QLabel {{ font-size: 15px; color: #000000; font-weight: 600; }}
            #masterFieldLabel {{ font-weight: 400; color: #000000; }}
            #sectionTitle {{ font-size: 17px; font-weight: 800; color: #496C5B; padding: 0 0 2px 0; border-bottom: 1px solid #D4DED9; }}
            QLineEdit, QComboBox {{
                background-color: white; color: #000000; border: 1px solid #9EB1A7;
                border-radius: 5px; padding: 2px 7px; min-height: 18px; font-size: 14px;
            }}
            QLineEdit QAbstractItemView, QComboBox QAbstractItemView {{
                background-color: white; color: #000000;
            }}
            QLineEdit:focus, QComboBox:focus {{ border: 2px solid #496C5B; padding: 1px 6px; }}
            QLineEdit:disabled, QComboBox:disabled {{ background: #F2F4F3; color: #929D97; }}
            #photoPanel {{ border: none; border-radius: 0px; }}
            #aspectHint {{ color: #718078; font-size: 13px; padding: 2px; }}
            #linkButton {{ padding: 2px; min-height: 18px; font-size: 16px; }}
            #linkButton:disabled {{ color: #A9B2AD; background: #F2F4F3; }}
            QPushButton {{
                background: white; color: #24332B; border: 1px solid #AABBB2;
                border-radius: 7px; padding: 6px 12px; min-height: 21px;
            }}
            QPushButton:hover {{ background: #E8F0EC; }}
            QPushButton:disabled {{ color: #9AA59F; background: #F3F5F4; }}
            #primaryButton {{ background: #496C5B; color: white; border-color: #496C5B; }}
            #primaryButton:hover {{ background: #3C5B4C; }}
            #saveButton[dirty="true"] {{ background: #496C5B; color: white; border-color: #496C5B; }}
            #saveButton[dirty="true"]:hover {{ background: #3C5B4C; }}
            #restoreButton:enabled {{
                background: #496C5B; color: white; border-color: #496C5B;
                font-weight: 700;
            }}
            #restoreButton:enabled:hover {{ background: #3C5B4C; }}
            #restoreButton:disabled {{ color: #98A39D; background: #F3F5F4; }}
            """
        )

    def _reload_name_referential(self, selected: str | None = None) -> None:
        values = self.referentials.list_values(
            int(self.collection["id"]), "mineral_name"
        )
        current = (selected if selected is not None else self.name_edit.text()).strip().upper()
        combo_blocker = QSignalBlocker(self.name_combo)
        edit_blocker = QSignalBlocker(self.name_edit)
        self.name_model.setStringList(values)
        self.name_combo.setCurrentText(current)
        del edit_blocker
        del combo_blocker


    def _reload_associated_minerals(self, selected2: str | None = None, selected3: str | None = None) -> None:
        values = self.referentials.list_values(int(self.collection["id"]), "mineral_name")
        for combo, edit, model, selected in (
            (self.mineral2_combo, self.mineral2_edit, self.mineral2_model, selected2),
            (self.mineral3_combo, self.mineral3_edit, self.mineral3_model, selected3),
        ):
            current = (selected if selected is not None else edit.text()).strip().upper()
            cb = QSignalBlocker(combo); eb = QSignalBlocker(edit)
            model.setStringList(values); combo.setCurrentText(current)
            del eb; del cb

    def _reload_mineral_views(self, selected_name: str | None = None, selected2: str | None = None, selected3: str | None = None) -> None:
        self._reload_name_referential(selected_name)
        self._reload_associated_minerals(selected2, selected3)

    def _reload_class_referential(self, selected: str | None = None) -> None:
        values = self.referentials.list_values(
            int(self.collection["id"]), "mineral_class"
        )
        current = selected if selected is not None else self.class_edit.text()
        combo_blocker = QSignalBlocker(self.class_combo)
        edit_blocker = QSignalBlocker(self.class_edit)
        self.class_model.setStringList([self._dv(v) for v in values])
        self.class_combo.setCurrentText(self._dv(str(current).strip()))
        del edit_blocker
        del combo_blocker


    def _reload_crystal_referential(self, selected: str | None = None) -> None:
        values = self.referentials.list_values(
            int(self.collection["id"]), "crystal_system"
        )
        current = selected if selected is not None else self.crystal_edit.text()
        combo_blocker = QSignalBlocker(self.crystal_combo)
        edit_blocker = QSignalBlocker(self.crystal_edit)
        self.crystal_model.setStringList([self._dv(v) for v in values])
        self.crystal_combo.setCurrentText(self._dv(str(current).strip()))
        del edit_blocker
        del combo_blocker


    def _reload_luminescence_referential(self, selected: str | None = None) -> None:
        self._reload_generic_referential("luminescence", self.luminescence_combo, self.luminescence_edit, self.luminescence_model, selected)

    def _reload_intensity_referential(self, selected: str | None = None) -> None:
        self._reload_generic_referential("luminescence_intensity", self.intensity_combo, self.intensity_edit, self.intensity_model, selected)

    def _reload_fluorescence_color_referential(self, selected: str | None = None) -> None:
        self._reload_generic_referential("fluorescence_color", self.fluorescence_color_combo, self.fluorescence_color_edit, self.fluorescence_color_model, selected)

    def _reload_site_referential(self, selected: str | None = None) -> None:
        self._reload_generic_referential("site_name", self.site_combo, self.site_edit, self.site_model, selected)

    def _reload_department_referential(self, selected: str | None = None) -> None:
        self._reload_generic_referential("department", self.department_combo, self.department_edit, self.department_model, selected)

    def _reload_region_referential(self, selected: str | None = None) -> None:
        self._reload_generic_referential("region", self.region_combo, self.region_edit, self.region_model, selected)

    def _reload_country_referential(self, selected: str | None = None) -> None:
        self._reload_generic_referential("country", self.country_combo, self.country_edit, self.country_model, selected)

    def _reload_box_type_referential(self, selected: str | None = None) -> None:
        self._reload_generic_referential("box_type", self.box_type_combo, self.box_type_edit, self.box_type_model, selected)

    def _reload_category_referential(self, selected: str | None = None) -> None:
        self._reload_generic_referential("category", self.category_combo, self.category_edit, self.category_model, selected)

    def _reload_contact_referential(self, selected: str | None = None) -> None:
        self._reload_generic_referential("contact", self.contact_combo, self.contact_edit, self.contact_model, selected)

    def _reload_shape_referential(self, selected: str | None = None) -> None:
        self._reload_generic_referential("specimen_shape", self.shape_combo, self.shape_edit, self.shape_model, selected)

    def _reload_color_referential(self, selected: str | None = None) -> None:
        self._reload_generic_referential("specimen_color", self.color_combo, self.color_edit, self.color_model, selected)

    def _reload_quality_referential(self, selected: str | None = None) -> None:
        self._reload_generic_referential("quality", self.quality_combo, self.quality_edit, self.quality_model, selected)

    def reload_all_referentials(self) -> None:
        """Recharge toutes les listes de la Fiche depuis SQLite.

        Important : chaque fenêtre possède son propre ReferentialManager et donc
        son propre cache. Si une autre fenêtre (Tableau, Boîte à outils, Atelier)
        ajoute une valeur, il faut invalider ici le cache local avant de relire.
        Les valeurs actuellement saisies dans la fiche sont conservées.
        """
        try:
            self.referentials._invalidate_values_cache(int(self.collection["id"]))
        except Exception:
            pass

        selected = {
            "name": self.name_edit.text(),
            "mineral2": self.mineral2_edit.text(),
            "mineral3": self.mineral3_edit.text(),
            "class": self.class_combo.currentText(),
            "crystal": self.crystal_combo.currentText(),
            "luminescence": self.luminescence_combo.currentText(),
            "intensity": self.intensity_combo.currentText(),
            "fluorescence_color": self.fluorescence_color_combo.currentText(),
            "site": self.site_combo.currentText(),
            "department": self.department_combo.currentText(),
            "region": self.region_combo.currentText(),
            "country": self.country_combo.currentText(),
            "box_type": self.box_type_combo.currentText(),
            "category": self.category_combo.currentText(),
            "contact": self.contact_combo.currentText(),
            "shape": self.shape_combo.currentText(),
            "color": self.color_combo.currentText(),
            "quality": self.quality_combo.currentText(),
            "state": self.state_combo.currentText(),
        }
        self._reload_name_referential(selected["name"])
        self._reload_associated_minerals(selected["mineral2"], selected["mineral3"])
        self._reload_class_referential(selected["class"])
        self._reload_crystal_referential(selected["crystal"])
        self._reload_luminescence_referential(selected["luminescence"])
        self._reload_intensity_referential(selected["intensity"])
        self._reload_fluorescence_color_referential(selected["fluorescence_color"])
        self._reload_site_referential(selected["site"])
        self._reload_department_referential(selected["department"])
        self._reload_region_referential(selected["region"])
        self._reload_country_referential(selected["country"])
        self._reload_box_type_referential(selected["box_type"])
        self._reload_category_referential(selected["category"])
        self._reload_contact_referential(selected["contact"])
        self._reload_shape_referential(selected["shape"])
        self._reload_color_referential(selected["color"])
        self._reload_quality_referential(selected["quality"])
        self._reload_state_referential(selected["state"])

        # Les champs personnalisés de type Liste ont leurs propres référentiels.
        # Ils doivent eux aussi voir immédiatement une valeur créée ailleurs.
        for key, definition in getattr(self, "_custom_field_defs", {}).items():
            if str(definition.get("field_type") or "") != "list":
                continue
            widget = getattr(self, "_custom_field_inputs", {}).get(key)
            if not isinstance(widget, QComboBox):
                continue

            current = self._cv(widget.currentText())
            code = str(definition.get("referential_code") or key)
            try:
                values = self.referentials.list_values(
                    int(self.collection["id"]), code
                )
            except Exception:
                values = []

            shown_values = [self._dv(v) for v in values]
            blocker = QSignalBlocker(widget)
            widget.clear()
            widget.addItems(shown_values)
            widget.setCurrentText(self._dv(current))

            if widget.lineEdit() is not None:
                widget.lineEdit().setReadOnly(False)
                widget.lineEdit().setMaxLength(32767)
                widget.lineEdit().setClearButtonEnabled(False)
                self._install_prefix_inline_completion(widget, shown_values)

            del blocker

    def _reload_state_referential(self, selected: str | None = None) -> None:
        cid = int(self.collection["id"])
        canonical_values = ["OK", "Vérifier", "Libre"]
        for value in canonical_values:
            try:
                if not self.referentials.contains(cid, "record_state", value, active_only=True):
                    self.referentials.add_value(cid, "record_state", value)
            except Exception:
                pass
        current = selected if selected is not None else self._state_canonical(self.state_combo.currentText())
        if current not in canonical_values:
            current = "OK"
        blocker = QSignalBlocker(self.state_combo)
        # Garder le QLineEdit de la liste déroulante pour que la justification
        # de la donnée définie dans l'Atelier soit visible sur la Fiche.
        # Le rendre non modifiable : seules les trois valeurs natives restent
        # sélectionnables via la flèche du combo.
        self.state_combo.setEditable(True)
        self.state_combo.clear()
        self.state_combo.addItems([self._state_display(v) for v in canonical_values])
        if self.state_combo.lineEdit() is not None:
            self.state_combo.lineEdit().setReadOnly(True)
            self.state_combo.lineEdit().setClearButtonEnabled(False)
        self.state_model.setStringList([self._state_display(v) for v in canonical_values])
        self.state_combo.setCurrentText(self._state_display(current))
        del blocker

    def _ensure_class_in_referential(self, value: str) -> bool:
        if getattr(self, "_batch_skip_referential_prompts", False):
            return True
        value = self.referentials.normalize(value, "mineral_class")
        if not value:
            return True
        active_values = {
            self.referentials.normalize(self._cv(item), "mineral_class").casefold()
            for item in self.referentials.list_values(
                int(self.collection["id"]), "mineral_class", active_only=True
            )
        }
        if self._cv(value).casefold() in active_values:
            self._class_declined_for_value = ""
            return True
        if value.casefold() == self._class_declined_for_value.casefold():
            return True
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle("Nouvelle classe")
        box.setText(f"La classe « {value} » n'existe pas encore dans le référentiel.")
        box.setInformativeText("Voulez-vous l'ajouter à la liste des classes ?")
        yes_button = box.addButton(self._t("OUI"), QMessageBox.ButtonRole.YesRole)
        no_button = box.addButton(self._t("NON"), QMessageBox.ButtonRole.NoRole)
        cancel_button = box.addButton("Annuler", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(yes_button)
        box.exec()
        clicked = box.clickedButton()
        if clicked is cancel_button:
            return False
        if clicked is yes_button:
            try:
                self.referentials.add_value(
                    int(self.collection["id"]), "mineral_class", value
                )
                self._reload_class_referential(value)
                self._class_declined_for_value = ""
            except Exception as exc:
                QMessageBox.critical(self, "Ajout impossible", str(exc))
                return False
        elif clicked is no_button:
            self._class_declined_for_value = value
        return True

    def _ensure_crystal_in_referential(self, value: str) -> bool:
        if getattr(self, "_batch_skip_referential_prompts", False):
            return True
        value = self.referentials.normalize(value, "crystal_system")
        if not value:
            return True
        active_values = {
            self.referentials.normalize(self._cv(item), "crystal_system").casefold()
            for item in self.referentials.list_values(
                int(self.collection["id"]), "crystal_system", active_only=True
            )
        }
        if self._cv(value).casefold() in active_values:
            self._crystal_declined_for_value = ""
            return True
        if value.casefold() == self._crystal_declined_for_value.casefold():
            return True
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle("Nouveau système cristallin")
        box.setText(f"Le système cristallin « {value} » n'existe pas encore dans le référentiel.")
        box.setInformativeText("Voulez-vous l'ajouter à la liste des systèmes cristallins ?")
        yes_button = box.addButton(self._t("OUI"), QMessageBox.ButtonRole.YesRole)
        no_button = box.addButton(self._t("NON"), QMessageBox.ButtonRole.NoRole)
        cancel_button = box.addButton("Annuler", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(yes_button)
        box.exec()
        clicked = box.clickedButton()
        if clicked is cancel_button:
            return False
        if clicked is yes_button:
            try:
                self.referentials.add_value(
                    int(self.collection["id"]), "crystal_system", value
                )
                self._reload_crystal_referential(value)
                self._crystal_declined_for_value = ""
            except Exception as exc:
                QMessageBox.critical(self, "Ajout impossible", str(exc))
                return False
        elif clicked is no_button:
            self._crystal_declined_for_value = value
        return True

    def _ensure_generic_referential(self, code: str, value: str, declined_attr: str, title: str, noun: str, reload_method) -> bool:
        if getattr(self, "_batch_skip_referential_prompts", False) or (False and getattr(self, "_defer_referential_prompts_until_close", True)):
            return True
        value = self.referentials.normalize(value, code)
        if not value:
            return True
        active_values = {
            self.referentials.normalize(self._cv(item), code).casefold()
            for item in self.referentials.list_values(int(self.collection["id"]), code, active_only=True)
        }
        if self._cv(value).casefold() in active_values:
            setattr(self, declined_attr, "")
            return True
        declined = str(getattr(self, declined_attr, ""))
        if value.casefold() == declined.casefold():
            return True
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle(title)
        box.setText(f"La valeur « {value} » n'existe pas encore dans le référentiel.")
        box.setInformativeText(f"Voulez-vous l'ajouter à la liste {noun} ?")
        yes_button = box.addButton(self._t("OUI"), QMessageBox.ButtonRole.YesRole)
        no_button = box.addButton(self._t("NON"), QMessageBox.ButtonRole.NoRole)
        cancel_button = box.addButton("Annuler", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(yes_button)
        box.exec()
        clicked = box.clickedButton()
        if clicked is cancel_button:
            return False
        if clicked is yes_button:
            try:
                self.referentials.add_value(int(self.collection["id"]), code, value)
                reload_method(value)
                setattr(self, declined_attr, "")
            except Exception as exc:
                QMessageBox.critical(self, "Ajout impossible", str(exc))
                return False
        elif clicked is no_button:
            setattr(self, declined_attr, value)
        return True

    def _ensure_luminescence_in_referential(self, value: str) -> bool:
        return self._ensure_generic_referential("luminescence", value, "_luminescence_declined_for_value", "Nouvelle luminescence", "des luminescences", self._reload_luminescence_referential)

    def _ensure_intensity_in_referential(self, value: str) -> bool:
        return self._ensure_generic_referential("luminescence_intensity", value, "_intensity_declined_for_value", "Nouvelle intensité", "des intensités", self._reload_intensity_referential)

    def _ensure_fluorescence_color_in_referential(self, value: str) -> bool:
        return self._ensure_generic_referential("fluorescence_color", value, "_fluorescence_color_declined_for_value", "Nouvelle couleur de fluorescence", "des couleurs de fluorescence", self._reload_fluorescence_color_referential)

    def _ensure_site_in_referential(self, value: str) -> bool:
        return self._ensure_generic_referential("site_name", value, "_site_declined_for_value", "Nouveau site", "des sites", self._reload_site_referential)

    def _ensure_department_in_referential(self, value: str) -> bool:
        return self._ensure_generic_referential("department", value, "_department_declined_for_value", "Nouveau département", "des départements", self._reload_department_referential)

    def _ensure_region_in_referential(self, value: str) -> bool:
        return self._ensure_generic_referential("region", value, "_region_declined_for_value", "Nouvelle région", "des régions", self._reload_region_referential)

    def _ensure_country_in_referential(self, value: str) -> bool:
        return self._ensure_generic_referential("country", value, "_country_declined_for_value", "Nouveau pays", "des pays", self._reload_country_referential)

    def _ensure_box_type_in_referential(self, value: str) -> bool:
        return self._ensure_generic_referential("box_type", value, "_box_type_declined_for_value", "Nouveau contenant", "des types de boîte", self._reload_box_type_referential)

    def _ensure_category_in_referential(self, value: str) -> bool:
        return self._ensure_generic_referential("category", value, "_category_declined_for_value", "Nouvelle catégorie", "des catégories", self._reload_category_referential)

    def _ensure_contact_in_referential(self, value: str) -> bool:
        return self._ensure_generic_referential("contact", value, "_contact_declined_for_value", "Nouveau contact", "des contacts", self._reload_contact_referential)

    def _ensure_shape_in_referential(self, value: str) -> bool:
        return self._ensure_generic_referential("specimen_shape", value, "_shape_declined_for_value", "Nouvelle forme", "des formes", self._reload_shape_referential)

    def _ensure_color_in_referential(self, value: str) -> bool:
        return self._ensure_generic_referential("specimen_color", value, "_color_declined_for_value", "Nouvelle couleur", "des couleurs", self._reload_color_referential)

    def _ensure_quality_in_referential(self, value: str) -> bool:
        return self._ensure_generic_referential("quality", value, "_quality_declined_for_value", "Nouvelle qualité", "des qualités", self._reload_quality_referential)

    def _ensure_state_in_referential(self, value: str) -> bool:
        if getattr(self, "_batch_skip_referential_prompts", False) or getattr(self, "_defer_referential_prompts_until_close", True):
            return True
        value = self._state_canonical(self.referentials.normalize(value, "record_state"))
        if not value:
            return True
        if value in {"À vérifier", "A vérifier", "Valider"}:
            value = "Vérifier"
        if value not in self.STATES:
            return True
        active_values = {
            self.referentials.normalize(item, "record_state")
            for item in self.referentials.list_values(
                int(self.collection["id"]), "record_state", active_only=True
            )
        }
        if value.casefold() in {item.casefold() for item in active_values}:
            self._state_declined_for_value = ""
            return True
        if value.casefold() == self._state_declined_for_value.casefold():
            return True
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle(self._t("Nouvel état de fiche"))
        box.setText(f"La valeur « {value} » n'existe pas encore dans le référentiel.")
        box.setInformativeText("Voulez-vous l'ajouter à la liste des états de fiche ?")
        yes_button = box.addButton(self._t("OUI"), QMessageBox.ButtonRole.YesRole)
        no_button = box.addButton(self._t("NON"), QMessageBox.ButtonRole.NoRole)
        cancel_button = box.addButton(self._t("Annuler"), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(yes_button)
        box.exec()
        clicked = box.clickedButton()
        if clicked is cancel_button:
            return False
        if clicked is yes_button:
            try:
                self.referentials.add_value(
                    int(self.collection["id"]), "record_state", value
                )
                self._reload_state_referential(value)
                self._state_declined_for_value = ""
            except Exception as exc:
                QMessageBox.critical(self, "Ajout impossible", str(exc))
                return False
        elif clicked is no_button:
            self._state_declined_for_value = value
        return True

    def _ensure_name_in_referential(self, value: str) -> bool:
        if getattr(self, "_batch_skip_referential_prompts", False):
            return True
        value = self.referentials.normalize(value)
        if not value:
            return True

        # Vérification volontairement faite sur la liste ACTIVE réellement
        # proposée à l'utilisateur. Une valeur seulement présente dans une
        # ancienne fiche, mais absente du référentiel actif, doit donc bien
        # déclencher la question d'ajout.
        active_values = {
            self.referentials.normalize(item)
            for item in self.referentials.list_values(
                int(self.collection["id"]), "mineral_name", active_only=True
            )
        }
        if value in active_values:
            self._name_declined_for_value = ""
            return True
        # Si l'utilisateur vient de répondre NON pour cette même valeur,
        # on respecte son choix jusqu'à ce que le texte du champ change.
        if value == self._name_declined_for_value:
            return True
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle("Nouveau nom")
        box.setText(f"Le nom « {value} » n'existe pas encore dans le référentiel.")
        box.setInformativeText("Voulez-vous l'ajouter à la liste des noms ?")
        yes_button = box.addButton(self._t("OUI"), QMessageBox.ButtonRole.YesRole)
        no_button = box.addButton(self._t("NON"), QMessageBox.ButtonRole.NoRole)
        cancel_button = box.addButton("Annuler", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(yes_button)
        box.exec()

        clicked = box.clickedButton()
        if clicked is cancel_button:
            return False
        if clicked is yes_button:
            self._name_declined_for_value = ""
            try:
                self.referentials.add_value(
                    int(self.collection["id"]), "mineral_name", value
                )
                self._reload_name_referential(value)
                self._reload_associated_minerals()
            except Exception as exc:
                QMessageBox.critical(self, "Ajout impossible", str(exc))
                return False
        # NON : la fiche pourra être enregistrée, mais le nom n'est pas ajouté.
        if clicked is no_button:
            self._name_declined_for_value = value
        return True

    def _quick_search_fields(self) -> list[tuple[str, str]]:
        """Tous les champs recherchables réellement présents dans la collection."""
        cid = int(self.collection["id"])
        visible = set(self.model_manager.visible_fields(cid))
        custom_map = self.model_manager.custom_field_map(cid)
        custom_labels = self.model_manager.custom_labels(cid)

        result: list[tuple[str, str]] = []
        ordered = self.model_manager.tab_order(cid, list(visible))
        seen = set()

        for key in ordered:
            key = str(key)
            if key in seen or key == "photo_data":
                continue
            if key not in visible and key != "record_number":
                continue
            seen.add(key)

            if key == "record_number":
                result.append(("N° de fiche", key))
                continue

            custom = custom_map.get(key)
            if custom is not None:
                field_type = str(custom.get("field_type") or "")
                if field_type == "calculated":
                    # Calculé reste recherchable si une valeur est stockée/importée.
                    pass
                label = (
                    str(custom_labels.get(key) or "").strip()
                    or str(custom.get("label") or "").strip()
                    or key
                )
                result.append((label, key))
                continue

            spec = FIELD_BY_KEY.get(key)
            label = (
                str(custom_labels.get(key) or "").strip()
                or (str(spec.label) if spec is not None else key)
            )
            result.append((label, key))
        # Recherche rapide : N° de fiche reste le raccourci système en tête,
        # tous les autres champs sont proposés A → Z.
        system = [pair for pair in result if pair[1] == "record_number"]
        others = sorted(
            (pair for pair in result if pair[1] != "record_number"),
            key=lambda pair: str(pair[0]).casefold(),
        )
        return system + others

    def _quick_search_value(
        self,
        record: dict,
        field: str,
        custom_values: dict | None = None,
    ) -> str:
        """Valeur de recherche pour champ standard ou personnalisé."""
        field = str(field)
        if field == "record_number":
            return str(record.get("record_number", "") or "")

        if field in self._custom_field_defs:
            values = custom_values
            if values is None:
                try:
                    values = self.manager.custom_values(int(record.get("id", 0)))
                except Exception:
                    values = {}
            return str((values or {}).get(field, "") or "")

        if field == "mineral_name":
            return str(
                record.get("mineral_name", "")
                or record.get("species", "")
                or ""
            )
        return str(record.get(field, "") or "")

    def open_quick_search(self) -> None:
        if not self._confirm_unsaved_changes():
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Recherche rapide")
        dialog.setMinimumWidth(470)
        lay = QVBoxLayout(dialog)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(9)

        title = QLabel("Rechercher une fiche")
        title.setStyleSheet("font-size:16px; font-weight:700;")
        lay.addWidget(title)

        form = QGridLayout()
        field_combo = QComboBox()
        for label, field in self._quick_search_fields():
            field_combo.addItem(label, field)

        operator_combo = QComboBox()
        operator_combo.addItem("Contient", "contains")
        operator_combo.addItem("Est exactement", "exact")

        value_combo = QComboBox()
        value_combo.setEditable(True)
        value_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        value_combo.setMaxVisibleItems(25)
        value_combo.setMinimumWidth(280)
        value_combo.lineEdit().setPlaceholderText("Tapez une valeur…")
        value_combo.lineEdit().setClearButtonEnabled(True)

        try:
            custom_cache = self.manager.custom_values_for_collection(
                int(self.collection["id"])
            )
        except Exception:
            custom_cache = {}

        def record_custom_values(record: dict) -> dict:
            try:
                return custom_cache.get(int(record.get("id", 0)), {})
            except Exception:
                return {}

        def search_records_for_field(field):
            # Le cache de navigation ne contient que id/numero. Pour la recherche,
            # lire la colonne demandée sans charger les autres données ni les photos.
            standard = {name.strip() for name in self.manager._select_columns().split(",")}
            if field not in standard or field in ("photo_data", "photo_format"):
                return self.records
            try:
                with self.manager._connect() as connection:
                    rows = connection.execute(
                        'SELECT id, ' + field + (' , species' if field == 'mineral_name' else '') +
                        ' FROM records WHERE collection_id = ?',
                        (int(self.collection['id']),),
                    ).fetchall()
                by_id = {int(row['id']): dict(row) for row in rows}
                return [dict(record, **by_id.get(int(record['id']), {})) for record in self.records]
            except Exception:
                # Repli exact, sans valeurs manquantes en cas d'erreur SQL.
                return [self.manager.get_record(int(record['id']), int(self.collection['id'])) or record
                        for record in self.records]

        def refresh_values():
            field = str(field_combo.currentData() or "mineral_name")
            current = value_combo.currentText()
            found_values = set()
            for record in search_records_for_field(field):
                value = self._quick_search_value(
                    record, field, record_custom_values(record)
                ).strip()
                if value:
                    found_values.add(value)
            values = sorted(found_values, key=str.casefold)
            value_combo.blockSignals(True)
            value_combo.clear()
            value_combo.addItems(values)
            value_combo.setEditText(current)
            value_combo.blockSignals(False)
            completer = QCompleter(values, value_combo)
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            completer.setFilterMode(Qt.MatchFlag.MatchContains)
            completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
            value_combo.setCompleter(completer)

        field_combo.currentIndexChanged.connect(lambda *_: refresh_values())
        refresh_values()

        form.addWidget(QLabel("Champ :"), 0, 0)
        form.addWidget(field_combo, 0, 1)
        form.addWidget(QLabel("Recherche :"), 1, 0)
        form.addWidget(operator_combo, 1, 1)
        form.addWidget(QLabel("Valeur :"), 2, 0)
        form.addWidget(value_combo, 2, 1)
        lay.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Ok
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Rechercher")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Annuler")
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        lay.addWidget(buttons)
        value_combo.lineEdit().returnPressed.connect(dialog.accept)
        value_combo.setFocus()

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        field = str(field_combo.currentData() or "mineral_name")
        field_label = str(field_combo.currentText())
        operator = str(operator_combo.currentData() or "contains")
        query = value_combo.currentText().strip()
        if not query:
            return

        query_folded = query.casefold()
        matches = []
        for index, record in enumerate(search_records_for_field(field)):
            value = self._quick_search_value(
                record, field, record_custom_values(record)
            ).strip()
            folded = value.casefold()
            ok = folded == query_folded if operator == "exact" else query_folded in folded
            if ok:
                matches.append(index)

        if not matches:
            QMessageBox.information(
                self, "Recherche rapide",
                f'Aucune fiche trouvée pour {field_label} : « {query} ».'
            )
            return

        self._virtual_new_record = False
        self._quick_search_positions = matches
        self._quick_search_cursor = 0
        self._quick_search_label = f"{field_label} : {query}"
        self.position = matches[0]
        self.quick_search_clear_button.setVisible(True)
        self._invalidate_restore()
        self._refresh_display()
        self.statusBar().showMessage(
            f"{len(matches)} fiche(s) trouvée(s) — {self._quick_search_label}", 5000
        )

    def clear_quick_search(self) -> None:
        if not self._quick_search_positions:
            return
        self._quick_search_positions = []
        self._quick_search_cursor = -1
        self._quick_search_label = ""
        self.quick_search_clear_button.setVisible(False)
        self._refresh_display()
        self.statusBar().showMessage("Recherche rapide terminée", 3000)

    def _sync_quick_search_cursor(self) -> None:
        if not self._quick_search_positions:
            self._quick_search_cursor = -1
            return
        try:
            self._quick_search_cursor = self._quick_search_positions.index(self.position)
        except ValueError:
            self._quick_search_cursor = 0
            self.position = self._quick_search_positions[0]

    def reload_records(
        self, select_last: bool = False, select_first: bool = False
    ) -> None:
        import time as _perf_time
        from performance_diagnostic import write as _perf_write
        _reload_t0 = _perf_time.perf_counter()
        self._virtual_new_record = False
        try:
            # Navigation légère : ne pas charger les BLOB photo des centaines
            # de fiches. La fiche courante est relue complètement à la demande.
            self.records = self.manager.list_record_navigation(int(self.collection["id"]))
        except Exception as exc:
            QMessageBox.critical(self, "Lecture impossible", str(exc))
            self.records = []

        _perf_write('RELOAD après list_record_navigation : %.3f s | fiches=%d' % (
            _perf_time.perf_counter() - _reload_t0, len(self.records)))
        if not self.records:
            # 23.9.1.1 — une collection neuve doit être immédiatement saisissable.
            # La première modification transforme cette fiche virtuelle en fiche N°1.
            self._virtual_new_record = True
            self.position = 0
        elif select_first:
            self.position = 0
        elif select_last:
            self.position = len(self.records) - 1
        elif self.position < 0:
            self.position = 0
        else:
            self.position = min(self.position, len(self.records) - 1)
        _before_refresh = _perf_time.perf_counter()
        self._refresh_display()
        _perf_write('RELOAD après _refresh_display : %.3f s | total %.3f s' % (
            _perf_time.perf_counter() - _before_refresh,
            _perf_time.perf_counter() - _reload_t0))

    def refresh_after_external_data_change(self) -> None:
        """Recharge les données après une modification globale faite hors de la Fiche.

        Si la fiche courante contient une saisie non enregistrée, MM3 ne l'écrase pas :
        seul le cache des enregistrements est renouvelé. Dès la navigation suivante, les
        nouvelles valeurs sont donc visibles. Si la fiche est propre, elle est rafraîchie
        immédiatement tout en restant sur le même numéro.
        """
        current_id = self._current_record_id()

        # Les listes peuvent elles aussi avoir été enrichies par la Boîte à outils.
        try:
            self.reload_all_referentials()
        except Exception:
            pass

        if self.dirty:
            try:
                fresh_records = self.manager.list_records(int(self.collection["id"]))
            except Exception:
                return
            self.records = fresh_records
            if current_id is not None:
                for index, record in enumerate(self.records):
                    if int(record.get("id", -1)) == int(current_id):
                        self.position = index
                        break
            return

        if current_id is not None and self.select_record_by_id(current_id):
            return
        self.reload_records()

    def select_record_by_id(self, record_id: int) -> bool:
        """Affiche une fiche précise depuis un autre module MM3."""
        self._quick_search_positions = []
        self._quick_search_cursor = -1
        self._quick_search_label = ""
        if hasattr(self, "quick_search_clear_button"):
            self.quick_search_clear_button.setVisible(False)
        self.reload_records()
        for index, record in enumerate(self.records):
            if int(record.get("id", -1)) == int(record_id):
                self.position = index
                self._refresh_display()
                return True
        return False

    def _refresh_display(self) -> None:
        # Changement de fiche : ne jamais réutiliser le instantané Échap de la
        # fiche précédente, même si le focus reste visuellement dans le même champ.
        self._escape_focus_key = None
        self._escape_focus_value = None
        has_record = 0 <= self.position < len(self.records)
        is_virtual = self._virtual_new_record and self.position == len(self.records)

        # Le mode « Maître inconnu / saisie libre » appartient à la fiche en cours,
        # jamais à la fenêtre entière. Le réinitialiser à chaque navigation évite
        # qu'un Site inconnu rencontré sur une fiche empêche le nettoyage ou la
        # mémorisation correcte des champs Reliés sur la suivante.
        self._unresolved_relation_masters.clear()

        editable_record = has_record or is_virtual
        self._loading = True
        try:
            blockers = [
                QSignalBlocker(self.name_combo),
                QSignalBlocker(self.name_edit),
                QSignalBlocker(self.mineral2_combo), QSignalBlocker(self.mineral2_edit),
                QSignalBlocker(self.mineral3_combo), QSignalBlocker(self.mineral3_edit),
                QSignalBlocker(self.class_combo),
                QSignalBlocker(self.class_edit),
                QSignalBlocker(self.formula_edit),
                QSignalBlocker(self.internet_link_edit),
                QSignalBlocker(self.site_link_edit),
                QSignalBlocker(self.crystal_combo),
                QSignalBlocker(self.crystal_edit),
                QSignalBlocker(self.luminescence_combo),
                QSignalBlocker(self.luminescence_edit),
                QSignalBlocker(self.intensity_combo),
                QSignalBlocker(self.intensity_edit),
                QSignalBlocker(self.fluorescence_color_combo),
                QSignalBlocker(self.fluorescence_color_edit),
                QSignalBlocker(self.site_combo),
                QSignalBlocker(self.site_edit),
                QSignalBlocker(self.deposit_edit),
                QSignalBlocker(self.department_combo),
                QSignalBlocker(self.department_edit),
                QSignalBlocker(self.region_combo),
                QSignalBlocker(self.region_edit),
                QSignalBlocker(self.country_combo),
                QSignalBlocker(self.country_edit),
                QSignalBlocker(self.box_type_combo),
                QSignalBlocker(self.box_type_edit),
                QSignalBlocker(self.category_combo),
                QSignalBlocker(self.category_edit),
                QSignalBlocker(self.contact_combo),
                QSignalBlocker(self.contact_edit),
                QSignalBlocker(self.shape_combo), QSignalBlocker(self.shape_edit),
                QSignalBlocker(self.color_combo), QSignalBlocker(self.color_edit),
                QSignalBlocker(self.quality_combo), QSignalBlocker(self.quality_edit),
                QSignalBlocker(self.description_edit),
                QSignalBlocker(self.minimum_magnification_edit),
                QSignalBlocker(self.growth_edit),
                QSignalBlocker(self.type_locality_combo),
                QSignalBlocker(self.acquisition_date_edit),
                QSignalBlocker(self.origin_edit),
                QSignalBlocker(self.place_edit),
                QSignalBlocker(self.box_count_edit),
                QSignalBlocker(self.price_edit),
                QSignalBlocker(self.total_cost_edit),
                QSignalBlocker(self.state_combo),
            ]
            if has_record:
                record = self.records[self.position]
                if not bool(record.get("__mm3_full_loaded__", True)):
                    try:
                        full = self.manager.get_record(
                            int(record["id"]), int(self.collection["id"])
                        )
                    except Exception:
                        full = None
                    if full is not None:
                        full["__mm3_full_loaded__"] = True
                        self.records[self.position] = full
                        record = full
                self.number_value.setStyleSheet("")
                self.number_value.setText(str(record["record_number"]))
                if self._quick_search_positions:
                    self._sync_quick_search_cursor()
                    self.position_label.setText(
                        self._t("Résultat {current} sur {total}").format(
                            current=self._quick_search_cursor + 1, total=len(self._quick_search_positions)
                        )
                    )
                else:
                    self.position_label.setText(
                        self._t("Fiche {current} sur {total}").format(
                            current=self.position + 1, total=len(self.records)
                        )
                    )
                stored_name = str(record.get("mineral_name", "") or record.get("species", ""))
                self.name_edit.setText(stored_name.upper())
                self.mineral2_combo.setCurrentText(str(record.get("mineral_2", "")).upper())
                self.mineral3_combo.setCurrentText(str(record.get("mineral_3", "")).upper())
                self.class_combo.setCurrentText(self._dv(str(record.get("mineral_class", ""))))
                self.formula_edit.setText(str(record.get("chemical_formula", "")))
                self.internet_link_edit.setText(str(record.get("internet_link", "")))
                self._update_internet_link_button(self.internet_link_edit.text())
                self.crystal_combo.setCurrentText(self._dv(str(record.get("crystal_system", ""))))
                self.luminescence_combo.setCurrentText(self._dv(str(record.get("luminescence", "Non"))))
                self.intensity_combo.setCurrentText(self._dv(str(record.get("luminescence_intensity", "Aucune"))))
                self.fluorescence_color_combo.setCurrentText(self._dv(str(record.get("fluorescence_color", "Aucune"))))
                self.site_combo.setCurrentText(str(record.get("site_name", "")))
                self.deposit_edit.setText(str(record.get("deposit", "")))
                self.department_combo.setCurrentText(str(record.get("department", "")))
                self.region_combo.setCurrentText(str(record.get("region", "")))
                self.country_combo.setCurrentText(str(record.get("country", "")))
                self.site_link_edit.setText(str(record.get("site_internet_link", "")))
                self._update_site_link_button(self.site_link_edit.text())
                self.box_type_combo.setCurrentText(self._dv(str(record.get("box_type", ""))))
                self.category_combo.setCurrentText(self._dv(str(record.get("category", ""))))
                self.contact_combo.setCurrentText(str(record.get("contact", "")))
                self.shape_combo.setCurrentText(self._dv(str(record.get("specimen_shape", ""))))
                self.color_combo.setCurrentText(self._dv(str(record.get("specimen_color", ""))))
                self.quality_combo.setCurrentText(self._dv(str(record.get("quality", ""))))
                self.description_edit.setPlainText(str(record.get("description", "")))
                self.minimum_magnification_combo.setCurrentText(self._dv(str(record.get("minimum_magnification", ""))))
                self.growth_combo.setCurrentText(self._dv(str(record.get("growth", ""))))
                self.type_locality_combo.setCurrentText(
                    self._bool_display(str(record.get("type_locality", "") or "Non"))
                )
                self.acquisition_date_edit.setText(
                    self._format_date_value(str(record.get("acquisition_date", "")))
                )
                self.origin_combo.setCurrentText(self._dv(str(record.get("origin", ""))))
                self.place_combo.setCurrentText(self._dv(str(record.get("place", ""))))
                self.box_count_edit.setText(str(record.get("box_count", "")))
                self.price_edit.setText(
                    self._format_currency_value(str(record.get("price", "")), self._currency_symbol_for_field("price"), self._currency_decimals_for_field("price"))
                )
                self.total_cost_edit.setText(
                    self._format_currency_value(str(record.get("total_cost", "")), self._currency_symbol_for_field("total_cost"), self._currency_decimals_for_field("total_cost"))
                )
                self._recalculate_total_cost()
                self._load_photo_from_record(record)
                self._load_extra_photos_for_current_record()
                self.state_combo.setCurrentText(self._state_display(str(record.get("record_state", "OK"))))
                self._load_custom_values_for_current_record()
            else:
                if is_virtual:
                    self.number_value.setStyleSheet("font-size:18px; font-weight:700; color:#496C5B; padding-left:10px;")
                else:
                    self.number_value.setStyleSheet("")
                self.number_value.setText(self._t("Nouvelle fiche") if is_virtual else "—")
                self.position_label.setText(self._t("Nouvelle fiche") if is_virtual else self._t("Aucune fiche"))
                self.name_edit.clear()
                self.mineral2_combo.setCurrentText("")
                self.mineral3_combo.setCurrentText("")
                self.class_combo.setCurrentText("")
                self.formula_edit.clear()
                self.internet_link_edit.clear()
                self._update_internet_link_button("")
                self.crystal_combo.setCurrentText("")
                self.luminescence_combo.setCurrentText(self._dv("Non"))
                self.intensity_combo.setCurrentText(self._dv("Aucune"))
                self.fluorescence_color_combo.setCurrentText(self._dv("Aucune"))
                self.site_combo.setCurrentText("")
                self.deposit_edit.clear()
                self.department_combo.setCurrentText("")
                self.region_combo.setCurrentText("")
                self.country_combo.setCurrentText("")
                self.site_link_edit.clear()
                self._update_site_link_button("")
                self.box_type_combo.setCurrentText("")
                self.category_combo.setCurrentText("")
                self.contact_combo.setCurrentText("")
                self.shape_combo.setCurrentText("")
                self.color_combo.setCurrentText("")
                self.quality_combo.setCurrentText("")
                self.description_edit.clear()
                self.minimum_magnification_combo.setCurrentText("20 X" if is_virtual else "")
                self.growth_combo.setCurrentText("")
                self.type_locality_combo.setCurrentText(self._bool_display("Non"))
                self.acquisition_date_edit.clear()
                self.origin_combo.setCurrentText("")
                self.place_combo.setCurrentText("")
                self.box_count_edit.setText("1" if is_virtual else "")
                self.price_edit.setText(self._format_currency_value("0", self._currency_symbol_for_field("price"), self._currency_decimals_for_field("price")) if is_virtual else "")
                self.total_cost_edit.setText(self._format_currency_value("0", self._currency_symbol_for_field("total_cost"), self._currency_decimals_for_field("total_cost")) if is_virtual else "")
                self._recalculate_total_cost()
                self._clear_photo_state(mark_dirty=False)
                self._extra_photo_states = {}
                for _slot in self._extra_photo_widgets:
                    self._extra_photo_states[_slot] = {"data": None, "format": "", "image": QImage()}
                    self._refresh_extra_photo_display(_slot)
                self.state_combo.setCurrentText(self._state_display("OK"))
                self._load_custom_values_for_current_record()

                # 11.4.35.2 — Une fiche virtuelle est déjà une vraie zone de saisie :
                # les valeurs par défaut définies dans l’Atelier doivent donc être
                # visibles immédiatement, avant même que la fiche soit matérialisée
                # en base par la première saisie.
                if is_virtual:
                    try:
                        styles = self.model_manager.field_styles(int(self.collection["id"]))
                    except Exception:
                        styles = {}

                    if isinstance(styles, dict):
                        # Champs historiques / standards. N'appliquer ici que les
                        # défauts explicitement enregistrés dans l'Atelier : les
                        # défauts historiques ci-dessus restent ainsi inchangés
                        # lorsqu'aucun réglage utilisateur n'existe.
                        for field_key, style in styles.items():
                            if (
                                field_key in self._model_field_widgets
                                and isinstance(style, dict)
                                and "default_value" in style
                            ):
                                try:
                                    self._set_relation_widget_value(
                                        str(field_key), str(style.get("default_value") or "")
                                    )
                                except Exception:
                                    pass

                        # Champs personnalisés. _load_custom_values_for_current_record()
                        # les a volontairement vidés puisqu'aucun record_id n'existe
                        # encore ; on injecte maintenant leurs vrais défauts visuels.
                        for field_key, definition in self._custom_field_defs.items():
                            if str(definition.get("field_type") or "") == "calculated":
                                continue
                            style = styles.get(field_key, {})
                            if isinstance(style, dict) and "default_value" in style:
                                self._set_custom_widget_value(
                                    str(field_key), str(style.get("default_value") or "")
                                )
                        self._recalculate_computed_fields()
            del blockers
        finally:
            self._loading = False

        # Ne jamais effacer une valeur Reliée persistée au simple affichage d'une
        # fiche parce que son Maître est vide. C'est notamment légitime après un
        # import plat (Excel/CSV…) : une ligne peut fournir « Pays » sans fournir
        # « Site ». Les relations restent pleinement actives dès que l'utilisateur
        # modifie un Maître ; vider volontairement un Maître continue alors à vider
        # ses champs Reliés via les signaux installés par _wire_field_relations().
        # L'ouverture/navigation d'une fiche doit en revanche restituer fidèlement
        # les valeurs réellement enregistrées dans la base.

        self._reset_single_line_scroll()
        for widget in (self.name_combo, self.mineral2_combo, self.mineral3_combo, self.class_combo, self.formula_edit, self.internet_link_edit, self.internet_link_button, self.crystal_combo, self.luminescence_combo, self.intensity_combo, self.fluorescence_color_combo, self.site_combo, self.deposit_edit, self.department_combo, self.region_combo, self.country_combo, self.site_link_edit, self.site_link_button, self.box_type_combo, self.category_combo, self.contact_combo, self.shape_combo, self.color_combo, self.quality_combo, self.description_edit,
            self.minimum_magnification_combo, self.growth_combo, self.type_locality_combo,
            self.acquisition_date_edit, self.origin_combo, self.place_combo,
            self.box_count_edit, self.price_edit, self.total_cost_edit,
            self.photo_label, self.state_combo):
            widget.setEnabled(editable_record)
        for widget in self._custom_field_inputs.values():
            widget.setEnabled(editable_record)
        self.save_btn.setEnabled(editable_record)
        restore_available = (
            has_record
            and self._restore_snapshot is not None
            and self._restore_record_id == int(self.records[self.position].get("id", -1))
        )
        # 11.7.47 — tant que la restauration immédiate d'une fiche vidée est
        # disponible, empêcher un second vidage qui écraserait le seul instantané.
        self.clear_record_btn.setEnabled(has_record and not restore_available)
        self.restore_record_btn.setEnabled(restore_available)
        if self._quick_search_positions:
            self._sync_quick_search_cursor()
            has_previous = self._quick_search_cursor > 0
            has_next = self._quick_search_cursor < len(self._quick_search_positions) - 1
            self.first_btn.setEnabled(has_previous)
            self.previous_btn.setEnabled(has_previous)
            self.next_btn.setEnabled(has_next)
            self.last_btn.setEnabled(has_next)
        else:
            self.first_btn.setEnabled(bool(self.records) and self.position > 0)
            self.previous_btn.setEnabled(bool(self.records) and self.position > 0)
            # Sur la dernière fiche réelle, Suivante ouvre la fiche virtuelle.
            self.next_btn.setEnabled(has_record)
            self.last_btn.setEnabled(
                bool(self.records) and (is_virtual or self.position < len(self.records) - 1)
            )
        self._name_declined_for_value = ""
        self._mineral2_declined_for_value = ""
        self._mineral3_declined_for_value = ""
        self._class_declined_for_value = ""
        self._crystal_declined_for_value = ""
        self._luminescence_declined_for_value = ""
        self._intensity_declined_for_value = ""
        self._fluorescence_color_declined_for_value = ""
        self._site_declined_for_value = ""
        self._department_declined_for_value = ""
        self._region_declined_for_value = ""
        self._country_declined_for_value = ""
        self._box_type_declined_for_value = ""
        self._category_declined_for_value = ""
        self._contact_declined_for_value = ""
        self._shape_declined_for_value = ""
        self._color_declined_for_value = ""
        self._quality_declined_for_value = ""
        self._state_declined_for_value = ""
        self._minimum_magnification_declined_for_value = ""
        self._growth_declined_for_value = ""
        self._origin_declined_for_value = ""
        self._place_declined_for_value = ""
        self._set_dirty(False)

    def _load_extra_photos_for_current_record(self) -> None:
        self._extra_photo_states = {}
        if 0 <= self.position < len(self.records):
            record_id = int(self.records[self.position]["id"])
            raw = self.manager.extra_photos(record_id)
            for slot, payload in raw.items():
                data = bytes(payload.get("photo_data") or b"")
                image = QImage()
                if data:
                    image.loadFromData(data)
                self._extra_photo_states[slot] = {
                    "data": data or None,
                    "format": str(payload.get("photo_format", "") or "JPEG"),
                    "image": image,
                }
        for slot in self._extra_photo_widgets:
            self._extra_photo_states.setdefault(
                slot, {"data": None, "format": "", "image": QImage()}
            )
            self._refresh_extra_photo_display(slot)

    def _refresh_extra_photo_display(self, slot: str) -> None:
        label = self._extra_photo_widgets.get(slot)
        if label is None:
            return
        state = self._extra_photo_states.get(slot, {})
        image = state.get("image")
        if not isinstance(image, QImage) or image.isNull():
            label.setPixmap(QPixmap())
            label.setText("📷\nPhoto")
            return
        label.setText("")
        available = label.contentsRect().size()
        label.setPixmap(
            QPixmap.fromImage(image).scaled(
                available,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def _set_extra_photo_from_image(self, slot: str, image: QImage) -> None:
        if image.isNull() or not self._ensure_record_for_photo():
            return
        # Seuls les grands cadres utilisent 600 × 400 ; cadres classiques inchangés.
        prepared, data, file_format = self._prepare_photo(
            image, large=slot in getattr(self, "_large_photo_slots", set())
        )
        if not data:
            QMessageBox.warning(self, "Photo impossible", "Cette image ne peut pas être intégrée à la fiche.")
            return
        self._extra_photo_states[slot] = {
            "data": data, "format": file_format, "image": prepared
        }
        self._refresh_extra_photo_display(slot)
        self._mark_dirty()

    @staticmethod
    def _load_photo_file(path: str) -> QImage:
        """Charge une photo en appliquant son orientation EXIF d'origine."""
        reader = QImageReader(path)
        reader.setAutoTransform(True)
        image = reader.read()
        return image

    def _choose_extra_photo(self, slot: str) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Ajouter une photo", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.gif *.webp);;Tous les fichiers (*.*)",
        )
        if path:
            image = self._load_photo_file(path)
            if not image.isNull():
                self._set_extra_photo_from_image(slot, image)

    def _paste_extra_photo(self, slot: str) -> None:
        image = QApplication.clipboard().image()
        if image.isNull():
            QMessageBox.information(self, "Aucune image", "Le Presse-papiers ne contient aucune image.")
            return
        self._set_extra_photo_from_image(slot, image)

    def _copy_extra_photo(self, slot: str) -> None:
        state = self._extra_photo_states.get(slot, {})
        image = state.get("image")
        if isinstance(image, QImage) and not image.isNull():
            QApplication.clipboard().setImage(image)

    def _remove_extra_photo(self, slot: str) -> None:
        state = self._extra_photo_states.get(slot, {})
        image = state.get("image")
        if not isinstance(image, QImage) or image.isNull():
            return
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Supprimer la photo")
        box.setText("Voulez-vous supprimer la photo de cette fiche ?")
        yes_button = box.addButton("Oui", QMessageBox.ButtonRole.DestructiveRole)
        no_button = box.addButton("Non", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(no_button)
        box.exec()
        if box.clickedButton() is yes_button:
            self._extra_photo_states[slot] = {
                "data": None, "format": "", "image": QImage()
            }
            self._refresh_extra_photo_display(slot)
            self._mark_dirty()

    def _show_extra_photo_menu(self, slot: str, global_pos) -> None:
        state = self._extra_photo_states.get(slot, {})
        image = state.get("image")
        menu = QMenu(self)
        empty = not isinstance(image, QImage) or image.isNull()
        if empty:
            add_action = menu.addAction(tr("Ajouter une photo…", self.language))
            paste_action = menu.addAction(tr("Coller une photo", self.language))
            chosen = menu.exec(global_pos)
            if chosen is add_action:
                self._choose_extra_photo(slot)
            elif chosen is paste_action:
                self._paste_extra_photo(slot)
            return
        replace_action = menu.addAction(tr("Remplacer la photo…", self.language))
        copy_action = menu.addAction(tr("Copier la photo", self.language))
        menu.addSeparator()
        remove_action = menu.addAction(tr("Supprimer la photo…", self.language))
        chosen = menu.exec(global_pos)
        if chosen is replace_action:
            self._choose_extra_photo(slot)
        elif chosen is copy_action:
            self._copy_extra_photo(slot)
        elif chosen is remove_action:
            self._remove_extra_photo(slot)

    def _save_extra_photos_for_current_record(self) -> None:
        if not (0 <= self.position < len(self.records)):
            return
        record_id = int(self.records[self.position]["id"])
        for slot, state in self._extra_photo_states.items():
            self.manager.set_extra_photo(
                record_id, slot, state.get("data"), str(state.get("format", "") or "")
            )

    @staticmethod
    def _prepare_photo(image: QImage, large: bool = False) -> tuple[QImage, bytes, str]:
        """Optimise une photo pour son affichage réel dans la Fiche MM3.

        Les collections pouvant dépasser 10 000 photos, MM3 ne conserve plus
        l'image originale surdimensionnée. Toute nouvelle photo importée/collée
        est réduite au format utile du cadre puis enregistrée en JPEG.
        """
        if image.isNull():
            return QImage(), b"", ""

        # Taille utile du cadre validé : 300 x 170 px.
        # KeepAspectRatio garantit zéro déformation, quelle que soit
        # l'orientation de la photo.
        max_width = 600 if large else 300
        max_height = 400 if large else 170
        prepared = image.scaled(
            max_width,
            max_height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        # JPEG ne gère pas la transparence. Aplatir proprement sur fond blanc
        # évite les fonds noirs avec certaines images PNG/WebP transparentes.
        flattened = QImage(
            prepared.size(),
            QImage.Format.Format_RGB888,
        )
        flattened.fill(Qt.GlobalColor.white)
        painter = QPainter(flattened)
        painter.drawImage(0, 0, prepared)
        painter.end()
        prepared = flattened

        array = QByteArray()
        buffer = QBuffer(array)
        if not buffer.open(QIODevice.OpenModeFlag.WriteOnly):
            return QImage(), b"", ""

        # 88 : très bon compromis visuel / poids pour une vignette de collection.
        if not prepared.save(buffer, "JPEG", 88):
            buffer.close()
            return QImage(), b"", ""
        buffer.close()

        return prepared, bytes(array), "JPEG"

    def _load_photo_from_record(self, record: dict) -> None:
        data = bytes(record.get("photo_data") or b"")
        image = QImage()
        if data:
            image.loadFromData(data)
        self._photo_data = data or None
        self._photo_format = str(record.get("photo_format", "") or ("PNG" if data else ""))
        self._photo_image = image
        self._refresh_photo_display()

    def _refresh_photo_display(self) -> None:
        if not hasattr(self, "photo_label"):
            return
        if self._photo_image.isNull():
            self.photo_label.setPixmap(QPixmap())
            self.photo_label.setText("📷\nPhoto")
            self.photo_label.setToolTip(
                "Cliquez pour sélectionner le cadre, puis Ctrl + V pour coller une image. "
                "Clic droit pour les options."
            )
            return
        self.photo_label.setText("")
        # Réserve minimale : l'image doit occuper presque tout le cadre.
        available = self.photo_label.contentsRect().size()
        pixmap = QPixmap.fromImage(self._photo_image)
        self.photo_label.setPixmap(
            pixmap.scaled(
                available,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        self.photo_label.setToolTip(
            "Cliquez pour sélectionner le cadre. Ctrl + C pour copier, Ctrl + V pour remplacer "
            "par l’image du Presse-papiers. Clic droit pour les options."
        )

    def _ensure_record_for_photo(self) -> bool:
        """Garantit qu'une fiche réelle existe avant d'y attacher une image.

        Une collection neuve peut afficher « Aucune fiche ». Dans ce cas,
        l'import/collage/dépôt d'une photo constitue une modification réelle :
        MM3 crée automatiquement la première fiche puis y attache l'image.
        """
        if 0 <= self.position < len(self.records):
            return True

        # Réutiliser le mécanisme validé de fiche virtuelle : _mark_dirty()
        # crée proprement le prochain N°, applique les valeurs par défaut et
        # met à jour la navigation.
        self._virtual_new_record = True
        self.position = len(self.records)
        self._mark_dirty()
        return 0 <= self.position < len(self.records)

    def _set_photo_from_image(self, image: QImage) -> None:
        if image.isNull() or not self._ensure_record_for_photo():
            return
        prepared, data, file_format = self._prepare_photo(image)
        if not data:
            QMessageBox.warning(self, "Photo impossible", "Cette image ne peut pas être intégrée à la fiche.")
            return
        self._photo_image = prepared
        self._photo_data = data
        self._photo_format = file_format
        self._refresh_photo_display()
        self._mark_dirty()

    def _choose_photo(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Ajouter une photo",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.gif *.webp);;Tous les fichiers (*.*)",
        )
        if not path:
            return
        image = self._load_photo_file(path)
        if image.isNull():
            QMessageBox.warning(self, "Photo impossible", "Le fichier choisi n'est pas une image lisible.")
            return
        self._set_photo_from_image(image)

    def _paste_photo(self) -> None:
        clipboard = QApplication.clipboard()
        image = clipboard.image()
        if image.isNull():
            QMessageBox.information(self, "Aucune image", "Le Presse-papiers ne contient aucune image.")
            return
        self._set_photo_from_image(image)

    def _copy_photo(self) -> None:
        if self._photo_image.isNull():
            return
        QApplication.clipboard().setImage(self._photo_image)
        self.statusBar().showMessage("Photo copiée dans le Presse-papiers.", 3000)

    def _remove_photo(self) -> None:
        if self._photo_image.isNull():
            return
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Supprimer la photo")
        box.setText("Voulez-vous supprimer la photo de cette fiche ?")
        yes_button = box.addButton("OUI", QMessageBox.ButtonRole.DestructiveRole)
        no_button = box.addButton("NON", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(no_button)
        box.exec()
        if box.clickedButton() is yes_button:
            self._clear_photo_state(mark_dirty=True)

    def _clear_photo_state(self, mark_dirty: bool = True) -> None:
        self._photo_data = None
        self._photo_format = ""
        self._photo_image = QImage()
        self._refresh_photo_display()
        if mark_dirty:
            self._mark_dirty()

    def _install_inline_completion(self) -> None:
        """Autocomplétion en ligne et liste complète des occurrences compatibles."""
        pairs = (
            (self.name_edit, self.name_model, self.name_completer),
            (self.mineral2_edit, self.mineral2_model, self.mineral2_completer),
            (self.mineral3_edit, self.mineral3_model, self.mineral3_completer),
            (self.class_edit, self.class_model, self.class_completer),
            (self.crystal_edit, self.crystal_model, self.crystal_completer),
            (self.luminescence_edit, self.luminescence_model, self.luminescence_completer),
            (self.intensity_edit, self.intensity_model, self.intensity_completer),
            (self.fluorescence_color_edit, self.fluorescence_color_model, self.fluorescence_color_completer),
            (self.site_edit, self.site_model, self.site_completer),
            (self.department_edit, self.department_model, self.department_completer),
            (self.region_edit, self.region_model, self.region_completer),
            (self.country_edit, self.country_model, self.country_completer),
            (self.box_type_edit, self.box_type_model, self.box_type_completer),
            (self.category_edit, self.category_model, self.category_completer),
            (self.contact_edit, self.contact_model, self.contact_completer),
            (self.shape_edit, self.shape_model, self.shape_completer),
            (self.color_edit, self.color_model, self.color_completer),
            (self.quality_edit, self.quality_model, self.quality_completer),
            (self.minimum_magnification_combo.lineEdit(), self.minimum_magnification_model, self.minimum_magnification_completer),
            (self.growth_edit, self.growth_model, self.growth_completer),
            (self.origin_edit, self.origin_model, self.origin_completer),
            (self.place_edit, self.place_model, self.place_completer),
            (self.state_edit, self.state_model, self.state_completer),
        )
        self._inline_filter_models = {}
        for edit, master_model, completer in pairs:
            filter_model = QStringListModel(master_model.stringList(), self)
            self._inline_filter_models[edit] = filter_model
            completer.setModel(filter_model)
            edit.textEdited.connect(
                lambda text, e=edit, m=master_model, f=filter_model, c=completer:
                    self._inline_complete(e, m, f, c, text)
            )

    def _inline_complete(self, edit, master_model, filter_model, completer, typed: str) -> None:
        if self._loading:
            return
        typed = str(typed)
        all_values = master_model.stringList()
        if not typed:
            filter_model.setStringList(all_values)
            return

        folded = typed.casefold()
        # Pour le champ Maître Nom/Espèce, la saisie doit être un PRÉFIXE :
        # taper CALCITE ne doit jamais proposer ALUMOHYDROCALCITE.
        if edit in (getattr(self, "name_edit", None), getattr(self, "mineral2_edit", None), getattr(self, "mineral3_edit", None)):
            matches = [
                value for value in all_values
                if value.casefold().startswith(folded)
            ]
        else:
            matches = [
                value for value in all_values
                if folded in value.casefold()
            ]
        filter_model.setStringList(matches)

        skip_inline = bool(edit.property("_mm3_skip_inline_once"))
        if skip_inline:
            edit.setProperty("_mm3_skip_inline_once", False)

        if matches and not skip_inline and not edit.hasSelectedText():
            inline_value = next(
                (value for value in matches
                 if value.casefold().startswith(folded) and len(value) > len(typed)),
                None,
            )
            if inline_value:
                blocker = QSignalBlocker(edit)
                edit.setText(inline_value)
                edit.setSelection(len(typed), len(inline_value) - len(typed))
                del blocker

        completer.setCompletionPrefix("")
        if matches:
            completer.complete()

    def _current_record_id(self) -> int | None:
        if 0 <= self.position < len(self.records):
            return int(self.records[self.position]["id"])
        return None

    @staticmethod
    def _set_field_text(widget, value: str) -> None:
        value = str(value or "").strip()
        if isinstance(widget, QComboBox):
            widget.setCurrentText(value)
            if widget.lineEdit() is not None:
                widget.lineEdit().setCursorPosition(0)
        else:
            widget.setText(value)
            if isinstance(widget, QLineEdit):
                widget.setCursorPosition(0)

    def _clear_identification_from_master(self) -> None:
        for widget in (
            self.class_combo, self.formula_edit, self.crystal_combo, self.internet_link_edit,
            self.luminescence_combo, self.intensity_combo, self.fluorescence_color_combo,
        ):
            self._set_field_text(widget, "")
        self._update_internet_link_button("")

    def _clear_location_from_master(self) -> None:
        for widget in (
            self.deposit_edit, self.department_combo, self.region_combo, self.country_combo,
            self.category_combo, self.site_link_edit,
        ):
            self._set_field_text(widget, "")
        self._update_site_link_button("")

    def _autofill_identification(self, name: str) -> None:
        name = str(name or "").strip()
        if not name:
            self._clear_identification_from_master()
            return
        source = self.manager.identification_for_name(int(self.collection["id"]), name)
        if not source:
            return
        targets = (
            (self.class_combo, "mineral_class"),
            (self.formula_edit, "chemical_formula"),
            (self.crystal_combo, "crystal_system"),
            (self.internet_link_edit, "internet_link"),
            (self.luminescence_combo, "luminescence"),
            (self.intensity_combo, "luminescence_intensity"),
            (self.fluorescence_color_combo, "fluorescence_color"),
        )
        for widget, key in targets:
            self._set_field_text(widget, source.get(key, ""))
        self._update_internet_link_button(self.internet_link_edit.text())
        self.statusBar().showMessage("Identification complétée à partir du nom connu.", 3500)

    def _autofill_location(self, site: str) -> None:
        site = str(site or "").strip()
        if not site:
            self._clear_location_from_master()
            return
        source = self.manager.location_for_site(int(self.collection["id"]), site)
        if not source:
            return
        targets = (
            (self.deposit_edit, "deposit"),
            (self.department_combo, "department"),
            (self.region_combo, "region"),
            (self.country_combo, "country"),
            (self.category_combo, "category"),
            (self.site_link_edit, "site_internet_link"),
        )
        for widget, key in targets:
            self._set_field_text(widget, source.get(key, ""))
        self._update_site_link_button(self.site_link_edit.text())
        self.statusBar().showMessage("Localisation complétée à partir du site connu.", 3500)

    def _show_photo_menu(self, global_pos) -> None:
        # 11.4.26 — ne pas bloquer le menu du premier cadre Photo sur une
        # fiche vierge / en cours de création. Les cadres Photo supplémentaires
        # n'avaient jamais ce garde, ce qui expliquait leur clic droit correct
        # alors que Photo 1 restait muette. Le collage et l'ajout travaillent
        # d'abord en mémoire ; l'enregistrement est géré ensuite normalement.
        menu = QMenu(self)
        if self._photo_image.isNull():
            add_action = menu.addAction(tr("Ajouter une photo…", self.language))
            paste_action = menu.addAction(tr("Coller une photo", self.language))
            # 11.4.21 — connexion directe des actions, exactement comme un menu
            # Qt normal. Cela évite toute dépendance au QAction renvoyé par exec(),
            # qui s'est montré non fiable pour le premier cadre reparenté.
            add_action.triggered.connect(self._choose_photo)
            paste_action.triggered.connect(self._paste_photo)
            menu.exec(global_pos)
            return
        replace_action = menu.addAction(tr("Remplacer la photo…", self.language))
        copy_action = menu.addAction(tr("Copier la photo", self.language))
        menu.addSeparator()
        remove_action = menu.addAction(tr("Supprimer la photo…", self.language))
        replace_action.triggered.connect(self._choose_photo)
        copy_action.triggered.connect(self._copy_photo)
        remove_action.triggered.connect(self._remove_photo)
        menu.exec(global_pos)

    def _on_name_edited(self, text: str) -> None:
        """Normalise Espèce/Nom sans aucune liaison historique implicite.

        23.9.3.6.1 — les remplissages automatiques sont désormais exclusivement
        pilotés par les liaisons Maître / Relié à déclarées dans l'Atelier.
        """
        self._name_declined_for_value = ""
        self._uppercase_name(text)

    def _uppercase_name(self, text: str) -> None:
        """Convertit le Nom en majuscules pendant la saisie, sans déplacer le curseur."""
        upper = text.upper()
        if upper == text:
            return
        cursor = self.name_edit.cursorPosition()
        blocker = QSignalBlocker(self.name_edit)
        self.name_edit.setText(upper)
        self.name_edit.setCursorPosition(min(cursor, len(upper)))
        del blocker
        self._mark_dirty()

    def _validate_name_and_continue(self) -> None:
        """Valide le Nom puis passe au champ Classe.

        Cette méthode est appelée directement par ReferentialLineEdit, ce qui
        garantit son exécution même lorsque la fenêtre de complétion est ouverte.
        """
        value = self.referentials.normalize(self.name_edit.text())
        if self._ensure_name_in_referential(value):
            self._focus_next_tab_field()

    def _on_associated_mineral_edited(self, edit, text: str) -> None:
        upper = text.upper()
        if upper != text:
            cursor = edit.cursorPosition(); blocker = QSignalBlocker(edit)
            edit.setText(upper); edit.setCursorPosition(min(cursor, len(upper))); del blocker
            self._mark_dirty()
        if edit is self.mineral2_edit:
            self._mineral2_declined_for_value = ""
        else:
            self._mineral3_declined_for_value = ""

    def _validate_associated_mineral_and_continue(self, number: int) -> None:
        edit = self.mineral2_edit if number == 2 else self.mineral3_edit
        value = self.referentials.normalize(edit.text())
        declined_attr = "_mineral2_declined_for_value" if number == 2 else "_mineral3_declined_for_value"
        if self._ensure_generic_referential(
            "mineral_name", value, declined_attr, f"Nouveau minéral {number}",
            "des noms", lambda selected: self._reload_mineral_views(None, selected if number == 2 else None, selected if number == 3 else None)
        ):
            self._focus_next_tab_field()

    def _on_class_edited(self, text: str) -> None:
        if text.strip().casefold() != self._class_declined_for_value.casefold():
            self._class_declined_for_value = ""

    def _validate_class_and_continue(self) -> None:
        value = self.referentials.normalize(self._cv(self.class_combo.currentText()), "mineral_class")
        if self._ensure_class_in_referential(value):
            self._focus_next_tab_field()

    def _formula_and_continue(self) -> None:
        self._focus_next_tab_field()

    @staticmethod
    def _make_internet_link_icon(active: bool) -> QIcon:
        """Crée une icône de globe monochrome, verte ou grisée."""
        size = 20
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        color = QColor("#496C5B" if active else "#A9B2AD")
        pen = QPen(color, 1.6)
        painter.setPen(pen)
        margin = 2.5
        rect = pixmap.rect().adjusted(int(margin), int(margin), -int(margin), -int(margin))
        painter.drawEllipse(rect)
        painter.drawLine(rect.left(), rect.center().y(), rect.right(), rect.center().y())
        painter.drawArc(rect.adjusted(4, 0, -4, 0), 90 * 16, 180 * 16)
        painter.drawArc(rect.adjusted(4, 0, -4, 0), 270 * 16, 180 * 16)
        painter.end()
        return QIcon(pixmap)

    def _update_internet_link_button(self, text: str) -> None:
        active = self._is_valid_internet_url(text)
        self.internet_link_button.setEnabled(active)
        self.internet_link_button.setIcon(self._make_internet_link_icon(active))
        self.internet_link_button.setToolTip(
            "Ouvrir le lien dans votre navigateur" if active else ""
        )

    @staticmethod
    def _is_valid_internet_url(value: str) -> bool:
        url = QUrl(value.strip())
        return url.isValid() and url.scheme().lower() in ("http", "https") and bool(url.host())

    def _on_internet_link_changed(self, text: str) -> None:
        self._update_internet_link_button(text)
        self._mark_dirty()

    def _internet_link_and_continue(self) -> None:
        self._focus_next_tab_field()

    def _open_internet_link(self) -> None:
        value = self.internet_link_edit.text().strip()
        if not self._is_valid_internet_url(value):
            return
        QDesktopServices.openUrl(QUrl(value))

    def _update_site_link_button(self, value: str) -> None:
        # Le signal clicked est connecté une seule fois lors de la création du bouton.
        # Ici on ne fait que mettre à jour son état visuel.
        valid = self._is_valid_internet_url(value)
        self.site_link_button.setEnabled(valid)
        self.site_link_button.setText("🌐")
        self.site_link_button.setToolTip(
            "Ouvrir le lien dans votre navigateur" if valid else ""
        )

    def _on_site_link_changed(self, value: str) -> None:
        self._update_site_link_button(value)
        self._mark_dirty()

    def _site_link_and_continue(self) -> None:
        self._focus_next_tab_field()

    def _open_site_link(self) -> None:
        value = self.site_link_edit.text().strip()
        if self._is_valid_internet_url(value):
            QDesktopServices.openUrl(QUrl(value))

    def _on_crystal_edited(self, text: str) -> None:
        if text.strip().casefold() != self._crystal_declined_for_value.casefold():
            self._crystal_declined_for_value = ""

    def _validate_crystal_and_continue(self) -> None:
        value = self.referentials.normalize(
            self._cv(self.crystal_combo.currentText()), "crystal_system"
        )
        if self._ensure_crystal_in_referential(value):
            self._focus_next_tab_field()

    def _on_luminescence_edited(self, text: str) -> None:
        if text.strip().casefold() != self._luminescence_declined_for_value.casefold():
            self._luminescence_declined_for_value = ""

    def _validate_luminescence_and_continue(self) -> None:
        value = self.referentials.normalize(self._cv(self.luminescence_combo.currentText()), "luminescence")
        if self._ensure_luminescence_in_referential(value):
            self._focus_next_tab_field()

    def _on_intensity_edited(self, text: str) -> None:
        if text.strip().casefold() != self._intensity_declined_for_value.casefold():
            self._intensity_declined_for_value = ""

    def _validate_intensity_and_continue(self) -> None:
        value = self.referentials.normalize(self._cv(self.intensity_combo.currentText()), "luminescence_intensity")
        if self._ensure_intensity_in_referential(value):
            self._focus_next_tab_field()

    def _on_fluorescence_color_edited(self, text: str) -> None:
        if text.strip().casefold() != self._fluorescence_color_declined_for_value.casefold():
            self._fluorescence_color_declined_for_value = ""

    def _validate_fluorescence_color_and_continue(self) -> None:
        value = self.referentials.normalize(self._cv(self.fluorescence_color_combo.currentText()), "fluorescence_color")
        if self._ensure_fluorescence_color_in_referential(value):
            self._focus_next_tab_field()

    def _on_site_edited(self, text: str) -> None:
        """Gère le référentiel Site sans liaison historique implicite."""
        if text.strip().casefold() != self._site_declined_for_value.casefold():
            self._site_declined_for_value = ""

    def _validate_site_and_continue(self) -> None:
        value = self.referentials.normalize(self._cv(self.site_combo.currentText()), "site_name")
        if self._ensure_site_in_referential(value):
            # Une nouvelle valeur Maître ne doit pas hériter des Reliés
            # de l'ancienne proposition du completer.
            self._apply_master_relations("site_name")
            self._focus_next_tab_field()

    def _deposit_and_continue(self) -> None:
        self._focus_next_tab_field()

    def _on_department_edited(self, text: str) -> None:
        if text.strip().casefold() != self._department_declined_for_value.casefold():
            self._department_declined_for_value = ""

    def _validate_department_and_continue(self) -> None:
        value = self.referentials.normalize(self._cv(self.department_combo.currentText()), "department")
        if self._ensure_department_in_referential(value):
            self._focus_next_tab_field()

    def _on_region_edited(self, text: str) -> None:
        if text.strip().casefold() != self._region_declined_for_value.casefold():
            self._region_declined_for_value = ""

    def _validate_region_and_continue(self) -> None:
        value = self.referentials.normalize(self._cv(self.region_combo.currentText()), "region")
        if self._ensure_region_in_referential(value):
            self._focus_next_tab_field()

    def _on_country_edited(self, text: str) -> None:
        if text.strip().casefold() != self._country_declined_for_value.casefold():
            self._country_declined_for_value = ""

    def _validate_country_and_continue(self) -> None:
        value = self.referentials.normalize(self._cv(self.country_combo.currentText()), "country")
        if self._ensure_country_in_referential(value):
            self._focus_next_tab_field()

    def _on_box_type_edited(self, text: str) -> None:
        if text.strip().casefold() != self._box_type_declined_for_value.casefold():
            self._box_type_declined_for_value = ""

    def _validate_box_type_and_continue(self) -> None:
        value = self.referentials.normalize(self._cv(self.box_type_combo.currentText()), "box_type")
        if self._ensure_box_type_in_referential(value):
            self._focus_next_tab_field()

    def _on_category_edited(self, text: str) -> None:
        if text.strip().casefold() != self._category_declined_for_value.casefold():
            self._category_declined_for_value = ""

    def _validate_category_and_continue(self) -> None:
        value = self.referentials.normalize(self._cv(self.category_combo.currentText()), "category")
        if self._ensure_category_in_referential(value):
            self._focus_next_tab_field()

    def _on_contact_edited(self, text: str) -> None:
        if text.strip().casefold() != self._contact_declined_for_value.casefold():
            self._contact_declined_for_value = ""

    def _validate_contact_and_continue(self) -> None:
        value = self.referentials.normalize(self._cv(self.contact_combo.currentText()), "contact")
        if self._ensure_contact_in_referential(value):
            self._focus_next_tab_field()

    def _on_shape_edited(self, text: str) -> None:
        if text.strip().casefold() != self._shape_declined_for_value.casefold():
            self._shape_declined_for_value = ""

    def _validate_shape_and_continue(self) -> None:
        value = self.referentials.normalize(self._cv(self.shape_combo.currentText()), "specimen_shape")
        if self._ensure_shape_in_referential(value):
            self._focus_next_tab_field()

    def _on_color_edited(self, text: str) -> None:
        if text.strip().casefold() != self._color_declined_for_value.casefold():
            self._color_declined_for_value = ""

    def _validate_color_and_continue(self) -> None:
        value = self.referentials.normalize(self._cv(self.color_combo.currentText()), "specimen_color")
        if self._ensure_color_in_referential(value):
            self._focus_next_tab_field()

    def _on_quality_edited(self, text: str) -> None:
        if text.strip().casefold() != self._quality_declined_for_value.casefold():
            self._quality_declined_for_value = ""

    def _validate_quality_and_continue(self) -> None:
        value = self.referentials.normalize(self._cv(self.quality_combo.currentText()), "quality")
        if self._ensure_quality_in_referential(value):
            self._focus_next_tab_field()

    def _set_description_text(self, value: str) -> None:
        self.description_edit.setPlainText(value)
        cursor = self.description_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.description_edit.setTextCursor(cursor)

    def _description_and_continue(self) -> None:
        self._focus_next_tab_field()

    def _on_state_edited(self, text: str) -> None:
        if text.strip().casefold() != self._state_declined_for_value.casefold():
            self._state_declined_for_value = ""

    def _validate_state_and_continue(self) -> None:
        value = self.referentials.normalize(self._state_canonical(self.state_combo.currentText()), "record_state")
        if self._ensure_state_in_referential(value):
            self._focus_next_tab_field()

    def _accept_completion_if_open(self, edit: QLineEdit) -> None:
        """Valide la proposition actuellement surlignée avant de traiter Entrée."""
        completer = edit.completer() if hasattr(edit, "completer") else None
        if completer is None:
            return
        popup = completer.popup()
        if popup is None or not popup.isVisible():
            return
        index = popup.currentIndex()
        value = str(index.data() or "").strip() if index.isValid() else ""
        if not value:
            value = str(completer.currentCompletion() or "").strip()
        if value:
            edit.setText(value)
        popup.hide()

    def _validate_enter_and_continue(self, source_widget=None) -> bool:
        """Valide le champ source puis avance selon l'ordre GLOBAL de l'Atelier.

        23.9.2.5 : la navigation ne dépend plus du widget qui a récupéré le
        focus pendant une validation (popup, rechargement d'un référentiel,
        QComboBox éditable...). La clé logique est figée au départ et
        ``tab_position`` est l'unique ordre de déplacement.
        """
        logical = source_widget if isinstance(source_widget, QWidget) else self._logical_focused_field()
        if logical is None:
            return False

        source_key = self._model_key_for_widget(logical)
        if source_key is None:
            source_key = self._custom_key_for_widget(logical)
        if source_key is None:
            # Si l'événement vient d'un popup/completer, retrouver son champ
            # logique réel puis sa clé MM3.
            logical = self._logical_focused_field()
            source_key = self._model_key_for_widget(logical)
            if source_key is None:
                source_key = self._custom_key_for_widget(logical)
        if source_key is None:
            return False

        # Accepter au préalable la proposition visible d'un completer.
        focus_target = logical
        if isinstance(focus_target, QComboBox) and focus_target.isEditable():
            focus_target = focus_target.lineEdit()
        if isinstance(focus_target, QLineEdit):
            # Le nom peut avoir été volontairement tronqué avec Suppr :
            # respecter ce préfixe plutôt que la proposition du popup.
            if bool(focus_target.property("_gskol_referential_field") or focus_target.property("_gskol_species_field") or focus_target.property("_gskol_site_field")) and bool(focus_target.property("_gskol_species_truncated")):
                completer = focus_target.completer()
                if completer is not None and completer.popup() is not None:
                    completer.popup().hide()
            else:
                self._accept_completion_if_open(focus_target)

        actions = {
            "mineral_name": self._validate_name_and_continue,
            "mineral_2": lambda: self._validate_associated_mineral_and_continue(2),
            "mineral_3": lambda: self._validate_associated_mineral_and_continue(3),
            "mineral_class": self._validate_class_and_continue,
            "chemical_formula": self._formula_and_continue,
            "internet_link": self._internet_link_and_continue,
            "crystal_system": self._validate_crystal_and_continue,
            "luminescence": self._validate_luminescence_and_continue,
            "luminescence_intensity": self._validate_intensity_and_continue,
            "fluorescence_color": self._validate_fluorescence_color_and_continue,
            "site_name": self._validate_site_and_continue,
            "deposit": self._deposit_and_continue,
            "department": self._validate_department_and_continue,
            "region": self._validate_region_and_continue,
            "country": self._validate_country_and_continue,
            "site_internet_link": self._site_link_and_continue,
            "box_type": self._validate_box_type_and_continue,
            "category": self._validate_category_and_continue,
            "contact": self._validate_contact_and_continue,
            "specimen_shape": self._validate_shape_and_continue,
            "specimen_color": self._validate_color_and_continue,
            "quality": self._validate_quality_and_continue,
            "description": self._description_and_continue,
            "minimum_magnification": self._validate_minimum_magnification_and_continue,
            "growth": self._validate_growth_and_continue,
            "acquisition_date": self._validate_acquisition_date_and_continue,
            "origin": self._validate_origin_and_continue,
            "place": self._validate_place_and_continue,
            "box_count": self._validate_box_count_and_continue,
            "price": self._validate_price_and_continue,
            "record_state": self._validate_state_and_continue,
        }

        self._enter_validation_in_progress = True
        self._enter_validation_allows_advance = False
        try:
            if source_key in getattr(self, "_custom_field_inputs", {}):
                self._validate_custom_field_and_continue(source_key)
            elif source_key == "type_locality":
                self._enter_validation_allows_advance = True
            else:
                action = actions.get(source_key)
                if action is None:
                    # Champ éditable sans validation métier particulière :
                    # Entrée reste strictement équivalente à Tab.
                    self._enter_validation_allows_advance = True
                else:
                    action()
        finally:
            self._enter_validation_in_progress = False

        if self._enter_validation_allows_advance:
            # 23.9.2.6 — différer le déplacement d'un tour de boucle Qt.
            # Certains validateurs/rechargements de listes rendent le focus
            # juste après leur retour ; notre déplacement doit être le dernier.
            QTimer.singleShot(0, lambda k=source_key: self._focus_relative_tab_field(1, source_key=k))
        return True


    def _logical_field_from_event_target(self, watched):
        """Retrouve le champ Fiche auquel appartient un événement Qt.

        Le popup d'un QComboBox/QCompleter est une fenêtre Qt séparée : quand
        il est ouvert, ``self.focusWidget()`` et ``isActiveWindow()`` ne sont
        pas toujours fiables sous Windows. Cette résolution par cible permet
        à Échap de restaurer la valeur en une seule frappe.
        """
        pairs = (
            (self.name_combo, self.name_edit, self.name_completer),
            (self.mineral2_combo, self.mineral2_edit, self.mineral2_completer),
            (self.mineral3_combo, self.mineral3_edit, self.mineral3_completer),
            (self.class_combo, self.class_edit, self.class_completer),
            (self.crystal_combo, self.crystal_edit, self.crystal_completer),
            (self.luminescence_combo, self.luminescence_edit, self.luminescence_completer),
            (self.intensity_combo, self.intensity_edit, self.intensity_completer),
            (self.fluorescence_color_combo, self.fluorescence_color_edit, self.fluorescence_color_completer),
            (self.site_combo, self.site_edit, self.site_completer),
            (self.department_combo, self.department_edit, self.department_completer),
            (self.region_combo, self.region_edit, self.region_completer),
            (self.country_combo, self.country_edit, self.country_completer),
            (self.box_type_combo, self.box_type_edit, self.box_type_completer),
            (self.category_combo, self.category_edit, self.category_completer),
            (self.contact_combo, self.contact_edit, self.contact_completer),
            (self.shape_combo, self.shape_edit, self.shape_completer),
            (self.color_combo, self.color_edit, self.color_completer),
            (self.quality_combo, self.quality_edit, self.quality_completer),
            (self.minimum_magnification_combo, self.minimum_magnification_edit, self.minimum_magnification_completer),
            (self.growth_combo, self.growth_edit, self.growth_completer),
            (self.origin_combo, self.origin_edit, self.origin_completer),
            (self.place_combo, self.place_edit, self.place_completer),
            (self.state_combo, self.state_edit, self.state_completer),
        )
        for combo, edit, completer in pairs:
            try:
                if watched in (combo, edit, combo.view(), completer.popup()):
                    return edit
            except Exception:
                if watched in (combo, edit):
                    return edit

        for widget in getattr(self, "_custom_field_inputs", {}).values():
            if watched is widget:
                return widget
            if isinstance(widget, QComboBox):
                edit = widget.lineEdit()
                try:
                    completer = edit.completer() if edit is not None else None
                    popup = completer.popup() if completer is not None else None
                    if watched in (edit, widget.view(), popup):
                        return edit if edit is not None else widget
                except Exception:
                    if watched is edit:
                        return edit

        if watched in (self.type_locality_combo, self.type_locality_combo.view()):
            return self.type_locality_combo

        if isinstance(watched, (QLineEdit, QPlainTextEdit)):
            return watched
        return None

    def eventFilter(self, watched, event):  # noqa: N802 (Qt convention)
        # Sécurité PySide6/Windows : ignorer les QWidgetItem transmis
        # exceptionnellement par le filtre d'application.
        if not isinstance(watched, QObject):
            return False

        # 11.4.31 — Champs Lien : Ctrl+clic ouvre la cible. Un clic
        # gauche simple reste entièrement consacré à l'édition du texte.
        if (
            isinstance(watched, QLineEdit)
            and bool(watched.property("mm3_link_field"))
            and event.type() == QEvent.Type.MouseButtonPress
        ):
            try:
                if (
                    event.button() == Qt.MouseButton.LeftButton
                    and event.modifiers() & Qt.KeyboardModifier.ControlModifier
                ):
                    self._open_link_editor(watched)
                    return True
            except (RuntimeError, AttributeError, TypeError):
                pass

        # 11.4.24 — premier cadre Photo : même comportement que les cadres
        # Photo supplémentaires, même si un widget absolu frère recouvre encore
        # momentanément sa zone. On ne se fie plus à la parenté du widget ayant
        # reçu l'événement : on teste la position écran du clic par rapport au
        # rectangle écran réel du cadre Photo. Cela couvre MouseButtonPress ET
        # ContextMenuEvent sous Windows/PySide6.
        primary_group = getattr(self, "_primary_photo_group", None)
        if primary_group is not None and isinstance(primary_group, QWidget):
            event_type = event.type()
            is_right_press = False
            if event_type == QEvent.Type.MouseButtonPress:
                try:
                    is_right_press = event.button() == Qt.MouseButton.RightButton
                except Exception:
                    is_right_press = False
            is_context = event_type == QEvent.Type.ContextMenu
            if is_right_press or is_context:
                try:
                    if is_context:
                        global_pos = event.globalPos()
                    else:
                        try:
                            global_pos = event.globalPosition().toPoint()
                        except Exception:
                            global_pos = event.globalPos()
                    top_left = primary_group.mapToGlobal(primary_group.rect().topLeft())
                    global_rect = QRect(top_left, primary_group.size())
                    if primary_group.isVisible() and global_rect.contains(global_pos):
                        self._show_photo_menu(global_pos)
                        return True
                except (RuntimeError, AttributeError, TypeError):
                    pass
        # 11.7.70.12 — la roulette ne doit jamais modifier accidentellement
        # la valeur d'une liste fermée. Le popup, lui, conserve sa roulette
        # pour parcourir volontairement les propositions.
        if event.type() == QEvent.Type.Wheel and isinstance(watched, QComboBox):
            try:
                if not watched.view().isVisible():
                    return True
            except Exception:
                return True

        # 11.7.70.12 — traiter Échap AVANT le test isActiveWindow(). Sous
        # Windows, le popup d'une liste est une fenêtre Qt distincte et faisait
        # auparavant consommer la première frappe uniquement pour se fermer.
        # Une seule frappe ferme maintenant le popup ET restaure la valeur
        # enregistrée, qu'une liste soit ouverte ou que l'utilisateur ait
        # simplement commencé à modifier/supprimer le texte du champ.
        if (
            event.type() == QEvent.Type.KeyPress
            and event.key() == Qt.Key.Key_Escape
            and event.modifiers() == Qt.KeyboardModifier.NoModifier
            and self.isVisible()
        ):
            logical = self._logical_field_from_event_target(watched)
            if logical is None:
                logical = self._logical_focused_field()
            if logical is not None:
                self._close_dropdowns_for_focus()
                return self._restore_current_field_value(logical)

        if event.type() == QEvent.Type.FocusIn and isinstance(watched, QLineEdit):
            # 11.7.70.13 — mémoriser la valeur AVANT édition pour les champs
            # Reliés. Lorsqu'ils sont vidés, le moteur Maître/Relié propage
            # immédiatement le vide en base ; relire record[] au moment d'Échap
            # est alors déjà trop tard. Le même champ peut perdre brièvement le
            # focus au profit du popup d'autocomplétion : ne pas écraser
            # l'instantané tant qu'on reste dans le même champ logique.
            try:
                _escape_logical = self._logical_field_from_event_target(watched)
                if _escape_logical is None:
                    _escape_logical = watched
                _escape_key = self._model_key_for_widget(_escape_logical)
                if _escape_key and _escape_key in self._field_links:
                    if self._escape_focus_key != _escape_key:
                        self._escape_focus_key = _escape_key
                        self._escape_focus_value = self._relation_widget_value(_escape_key)
                elif _escape_key and self._escape_focus_key != _escape_key:
                    self._escape_focus_key = _escape_key
                    self._escape_focus_value = None
            except Exception:
                pass
            # Arrivée au clavier : la valeur existante est sélectionnée.
            # Retour arrière peut donc vider immédiatement une valeur par défaut.
            # Un clic souris garde son comportement précis habituel.
            if event.reason() != Qt.FocusReason.MouseFocusReason:
                watched.selectAll()
            return super().eventFilter(watched, event)

        if event.type() == QEvent.Type.FocusOut and isinstance(watched, QLineEdit):
            if not watched.hasSelectedText():
                watched.setCursorPosition(0)
            return super().eventFilter(watched, event)

        if event.type() == QEvent.Type.KeyPress:
            raw_key = event.key()
            if raw_key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
                fw = QApplication.focusWidget()
                self._nav_diag(
                    f"EVENT key={int(raw_key)} watched={type(watched).__name__} "
                    f"focus={type(fw).__name__ if fw else None} "
                    f"focus_key={self._model_key_for_widget(fw)} "
                    f"visible={self.isVisible()} active={self.isActiveWindow()}"
                )
            # Le filtre d'application reste installé pendant toute la vie de la
            # fenêtre. Il ne doit toutefois agir que lorsque la fiche est visible
            # et active. Cela évite qu'une fermeture/réouverture désactive les
            # raccourcis clavier.
            if not self.isVisible() or not self.isActiveWindow():
                return super().eventFilter(watched, event)

            key = event.key()

            # 1.0.52 — Ctrl+" : le diagnostic 1.0.51 sur Windows/AZERTY a
            # établi que la seconde frappe arrive bien à Qt sous la forme
            # key=34 (Qt.Key_QuoteDbl), text='', avec ControlModifier.
            # La traiter ici, immédiatement, avant tout autre circuit clavier.
            if (
                key == Qt.Key.Key_QuoteDbl
                and (event.modifiers() & Qt.KeyboardModifier.ControlModifier)
            ):
                focused = self._logical_field_from_event_target(watched)
                if focused is None:
                    focused = self._logical_focused_field()
                if focused is not None:
                    return self._copy_previous_field(focused)
                return True

            # L'autocomplétion des listes personnalisées utilise parfois le
            # QLineEdit standard de QComboBox. Marquer explicitement une frappe
            # Retour arrière / Suppr afin que la complétion inline ne réinjecte
            # pas aussitôt le texte que l'utilisateur vient d'effacer.
            if key in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete):
                fw = QApplication.focusWidget()
                if isinstance(fw, QLineEdit):
                    fw.setProperty("_mm3_skip_inline_once", True)

            # 23.9.1.2 — Entrée a le même rôle ergonomique que Tab,
            # mais valide d'abord les listes/référentiels. Le filtre global
            # couvre aussi le popup d'autocomplétion, qui capturait auparavant
            # la touche avant le QLineEdit.
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if self._validate_enter_and_continue(watched if isinstance(watched, QWidget) else None):
                    return True

            # 018.4.4.1.2.9 — Tab utilise la même chaîne explicite que Entrée.
            if key == Qt.Key.Key_Tab:
                if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    return self._focus_relative_tab_field(-1)
                return self._focus_relative_tab_field(1)
            if key == Qt.Key.Key_Backtab:
                return self._focus_relative_tab_field(-1)

            if self._is_repeat_previous_shortcut(event):
                focused = self._logical_focused_field()
                if focused is not None:
                    return self._copy_previous_field(focused)

            # Navigation clavier entre les fiches.
            # - Flèche Haut : fiche précédente
            # - Flèche Bas : fiche suivante
            # - Page précédente / Page suivante : même comportement
            # Les flèches Gauche/Droite restent disponibles pour déplacer
            # le curseur à l'intérieur des champs de saisie.
            modifiers = event.modifiers()
            plain_key = modifiers in (
                Qt.KeyboardModifier.NoModifier,
                Qt.KeyboardModifier.KeypadModifier,
            )
            if plain_key and key in (Qt.Key.Key_PageUp, Qt.Key.Key_PageDown):
                if key == Qt.Key.Key_PageUp:
                    self.go_previous()
                else:
                    self.go_next()
                return True

            if plain_key and key in (Qt.Key.Key_Up, Qt.Key.Key_Down):
                # Lorsque la liste d'un champ est ouverte, Haut/Bas restent
                # réservées à la navigation dans les propositions. Lorsque
                # la liste est fermée, elles naviguent entre les fiches.
                if self._dropdown_is_open_for_focus():
                    return False
                if key == Qt.Key.Key_Up:
                    self.go_previous()
                else:
                    self.go_next()
                return True

            if watched in (self.class_combo, self.class_edit):
                if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    self._validate_class_and_continue()
                    return True
            if watched in (self.state_combo, self.state_edit):
                if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    self._validate_state_and_continue()
                    return True
        return super().eventFilter(watched, event)

    def _logical_focused_field(self):
        """Retourne le champ logique actif, même si le focus est dans un popup."""
        focused = self.focusWidget()

        pairs = (
            (self.name_combo, self.name_edit, self.name_completer),
            (self.mineral2_combo, self.mineral2_edit, self.mineral2_completer),
            (self.mineral3_combo, self.mineral3_edit, self.mineral3_completer),
            (self.class_combo, self.class_edit, self.class_completer),
            (self.crystal_combo, self.crystal_edit, self.crystal_completer),
            (self.luminescence_combo, self.luminescence_edit, self.luminescence_completer),
            (self.intensity_combo, self.intensity_edit, self.intensity_completer),
            (self.fluorescence_color_combo, self.fluorescence_color_edit, self.fluorescence_color_completer),
            (self.site_combo, self.site_edit, self.site_completer),
            (self.department_combo, self.department_edit, self.department_completer),
            (self.region_combo, self.region_edit, self.region_completer),
            (self.country_combo, self.country_edit, self.country_completer),
            (self.box_type_combo, self.box_type_edit, self.box_type_completer),
            (self.category_combo, self.category_edit, self.category_completer),
            (self.contact_combo, self.contact_edit, self.contact_completer),
            (self.shape_combo, self.shape_edit, self.shape_completer),
            (self.color_combo, self.color_edit, self.color_completer),
            (self.quality_combo, self.quality_edit, self.quality_completer),
            (self.minimum_magnification_combo, self.minimum_magnification_edit, self.minimum_magnification_completer),
            (self.growth_combo, self.growth_edit, self.growth_completer),
            (self.origin_combo, self.origin_edit, self.origin_completer),
            (self.place_combo, self.place_edit, self.place_completer),
            (self.state_combo, self.state_edit, self.state_completer),
        )

        for combo, edit, completer in pairs:
            if focused in (combo, edit, combo.view(), completer.popup()):
                return edit

        # Champs personnalisés : ils doivent emprunter exactement le même
        # circuit Entrée -> validation -> vrai Tab que les champs historiques.
        for widget in getattr(self, "_custom_field_inputs", {}).values():
            if focused is widget:
                return widget
            if isinstance(widget, QComboBox):
                edit = widget.lineEdit()
                try:
                    if focused is widget.view():
                        return edit if edit is not None else widget
                except Exception:
                    pass
                if edit is not None and focused is edit:
                    return edit

        # Combo non éditable.
        if focused in (self.type_locality_combo, self.type_locality_combo.view()):
            return self.type_locality_combo

        # Champs simples.
        if focused in (
            self.formula_edit,
            self.internet_link_edit,
            self.site_link_edit,
            self.deposit_edit,
            self.description_edit,
            self.acquisition_date_edit,
            self.box_count_edit,
            self.price_edit,
            self.total_cost_edit,
        ):
            return focused

        return None


    def _restore_current_field_value(self, focused_override=None) -> bool:
        """Restaure la valeur enregistrée du champ actif.

        Ce comportement reproduit l'usage d'Échap dans Access : une faute de
        frappe peut être annulée avant validation sans déplacer le curseur vers
        un autre champ.
        """
        focused = focused_override if focused_override is not None else self._logical_focused_field()
        if focused is None or not (0 <= self.position < len(self.records)):
            return False

        record = self.records[self.position]
        label = "Champ"

        # 11.7.70.13 — priorité à l'instantané pris à l'entrée dans un champ
        # Relié. Un effacement complet peut déjà avoir été propagé en base et
        # dans self.records ; cet instantané est donc la seule source fidèle
        # pour annuler réellement la saisie. Après restauration visuelle,
        # repropage la valeur d'origine afin d'annuler aussi l'écriture vide
        # éventuellement faite sur les autres fiches partageant le même Maître.
        try:
            linked_key = self._model_key_for_widget(focused)
        except Exception:
            linked_key = None
        if (
            linked_key
            and linked_key in self._field_links
            and self._escape_focus_key == linked_key
            and self._escape_focus_value is not None
        ):
            value = str(self._escape_focus_value or "")
            self._set_relation_widget_value(linked_key, value)
            try:
                self._propagate_linked_field(linked_key)
            except Exception:
                pass
            try:
                target = self._field_focus_target(linked_key)[1]
                if isinstance(target, QLineEdit):
                    target.setCursorPosition(len(target.text()))
            except Exception:
                pass
            try:
                label_widget = self._model_field_widgets.get(linked_key, [None])[0]
                if isinstance(label_widget, QLabel):
                    label = label_widget.text().strip() or linked_key
                else:
                    label = linked_key
            except Exception:
                label = linked_key
            self._recalculate_dirty_state()
            self.statusBar().showMessage(
                f"{label} restauré à sa valeur précédente.", 3000
            )
            return True

        # 11.7.70.11 — champs personnalisés/importés (dont listes SQLite).
        custom_key = self._custom_key_for_widget(focused)
        if custom_key is not None:
            try:
                values = self.manager.custom_values(int(record["id"]))
            except Exception:
                values = {}
            value = str(values.get(custom_key, "") or "")
            self._set_custom_widget_value(custom_key, value)
            definition = self._custom_field_defs.get(custom_key, {})
            label = str(definition.get("label") or custom_key)
            self._recalculate_dirty_state()
            self.statusBar().showMessage(
                f"{label} restauré à sa valeur précédente.", 3000
            )
            return True
        if focused is self.name_edit:
            value = str(record.get("mineral_name", "") or record.get("species", "")).upper()
            self.name_edit.setText(value)
            self.name_edit.setCursorPosition(len(value))
            label = "Nom"
        elif focused is self.mineral2_edit:
            value = str(record.get("mineral_2", "")).upper()
            self.mineral2_combo.setCurrentText(value); self.mineral2_edit.setCursorPosition(len(value)); label = "Minéral 2"
        elif focused is self.mineral3_edit:
            value = str(record.get("mineral_3", "")).upper()
            self.mineral3_combo.setCurrentText(value); self.mineral3_edit.setCursorPosition(len(value)); label = "Minéral 3"
        elif focused is self.class_edit:
            value = str(record.get("mineral_class", ""))
            self.class_combo.setCurrentText(value)
            self.class_edit.setCursorPosition(len(value))
            label = "Classe"
        elif focused is self.formula_edit:
            value = str(record.get("chemical_formula", ""))
            self.formula_edit.setText(value)
            self.formula_edit.setCursorPosition(len(value))
            label = "Formule chimique"
        elif focused is self.internet_link_edit:
            value = str(record.get("internet_link", ""))
            self.internet_link_edit.setText(value)
            self.internet_link_edit.setCursorPosition(len(value))
            self._update_internet_link_button(value)
            label = "Lien"
        elif focused is self.crystal_edit:
            value = str(record.get("crystal_system", ""))
            self.crystal_combo.setCurrentText(value)
            self.crystal_edit.setCursorPosition(len(value))
            label = "Système cristallin"
        elif focused is self.luminescence_edit:
            value = str(record.get("luminescence", "Non"))
            self.luminescence_combo.setCurrentText(value)
            self.luminescence_edit.setCursorPosition(len(value))
            label = "Luminescence"
        elif focused is self.intensity_edit:
            value = str(record.get("luminescence_intensity", "Aucune"))
            self.intensity_combo.setCurrentText(value)
            self.intensity_edit.setCursorPosition(len(value))
            label = "Intensité"
        elif focused is self.fluorescence_color_edit:
            value = str(record.get("fluorescence_color", "Aucune"))
            self.fluorescence_color_combo.setCurrentText(value)
            self.fluorescence_color_edit.setCursorPosition(len(value))
            label = "Couleur fluo"
        elif focused is self.site_edit:
            value = str(record.get("site_name", ""))
            self.site_combo.setCurrentText(value)
            self.site_edit.setCursorPosition(len(value))
            label = "Site"
        elif focused is self.deposit_edit:
            value = str(record.get("deposit", ""))
            self.deposit_edit.setText(value)
            self.deposit_edit.setCursorPosition(len(value))
            label = "Gisement"
        elif focused is self.department_edit:
            value = str(record.get("department", ""))
            self.department_combo.setCurrentText(value)
            self.department_edit.setCursorPosition(len(value))
            label = "Département"
        elif focused is self.region_edit:
            value = str(record.get("region", ""))
            self.region_combo.setCurrentText(value)
            self.region_edit.setCursorPosition(len(value))
            label = "Région"
        elif focused is self.country_edit:
            value = str(record.get("country", ""))
            self.country_combo.setCurrentText(value)
            self.country_edit.setCursorPosition(len(value))
            label = "Pays"
        elif focused is self.box_type_edit:
            value = str(record.get("box_type", ""))
            self.box_type_combo.setCurrentText(value)
            self.box_type_edit.setCursorPosition(len(value))
            label = "Contenant"
        elif focused is self.category_edit:
            value = str(record.get("category", ""))
            self.category_combo.setCurrentText(value)
            self.category_edit.setCursorPosition(len(value))
            label = "Catégorie"
        elif focused is self.contact_edit:
            value = str(record.get("contact", ""))
            self.contact_combo.setCurrentText(value)
            self.contact_edit.setCursorPosition(len(value))
            label = "Contact"
        elif focused is self.shape_edit:
            value = str(record.get("specimen_shape", ""))
            self.shape_combo.setCurrentText(value); label = "Forme"
        elif focused is self.color_edit:
            value = str(record.get("specimen_color", ""))
            self.color_combo.setCurrentText(value); label = "Couleur"
        elif focused is self.quality_edit:
            value = str(record.get("quality", ""))
            self.quality_combo.setCurrentText(value); label = "Qualité"
        elif focused is self.description_edit:
            value = str(record.get("description", ""))
            self._set_description_text(value)
            label = "Description"
        elif focused is self.state_edit:
            value = str(record.get("record_state", "OK"))
            self.state_combo.setCurrentText(value)
            self.state_edit.setCursorPosition(len(value))
            label = "État de la fiche"
        else:
            return False

        self._recalculate_dirty_state()
        self.statusBar().showMessage(
            f"{label} restauré à sa valeur précédente.", 3000
        )
        return True

    def _close_dropdowns_for_focus(self) -> None:
        """Ferme les propositions du champ actif sans modifier la valeur."""
        focused = self.focusWidget()
        pairs = (
            (self.name_combo, self.name_edit, self.name_completer),
            (self.mineral2_combo, self.mineral2_edit, self.mineral2_completer),
            (self.mineral3_combo, self.mineral3_edit, self.mineral3_completer),
            (self.class_combo, self.class_edit, self.class_completer),
            (self.crystal_combo, self.crystal_edit, self.crystal_completer),
            (self.luminescence_combo, self.luminescence_edit, self.luminescence_completer),
            (self.intensity_combo, self.intensity_edit, self.intensity_completer),
            (self.fluorescence_color_combo, self.fluorescence_color_edit, self.fluorescence_color_completer),
            (self.site_combo, self.site_edit, self.site_completer),
            (self.department_combo, self.department_edit, self.department_completer),
            (self.region_combo, self.region_edit, self.region_completer),
            (self.country_combo, self.country_edit, self.country_completer),
            (self.box_type_combo, self.box_type_edit, self.box_type_completer),
            (self.category_combo, self.category_edit, self.category_completer),
            (self.contact_combo, self.contact_edit, self.contact_completer),
            (self.shape_combo, self.shape_edit, self.shape_completer),
            (self.color_combo, self.color_edit, self.color_completer),
            (self.quality_combo, self.quality_edit, self.quality_completer),
            (self.minimum_magnification_combo, self.minimum_magnification_edit, self.minimum_magnification_completer),
            (self.growth_combo, self.growth_edit, self.growth_completer),
            (self.origin_combo, self.origin_edit, self.origin_completer),
            (self.place_combo, self.place_edit, self.place_completer),
            (self.state_combo, self.state_edit, self.state_completer),
        )
        for combo, edit, completer in pairs:
            try:
                if focused in (combo, edit, combo.view(), completer.popup()):
                    combo.hidePopup()
                    completer.popup().hide()
            except Exception:
                pass

        for widget in getattr(self, "_custom_field_inputs", {}).values():
            if not isinstance(widget, QComboBox):
                continue
            edit = widget.lineEdit()
            try:
                completer = edit.completer() if edit is not None else None
                popup = completer.popup() if completer is not None else None
                if focused in (widget, edit, widget.view(), popup):
                    widget.hidePopup()
                    if popup is not None:
                        popup.hide()
            except Exception:
                pass

    def _dropdown_is_open_for_focus(self) -> bool:
        focused = self.focusWidget()
        pairs = (
            (self.name_combo, self.name_edit, self.name_completer),
            (self.mineral2_combo, self.mineral2_edit, self.mineral2_completer),
            (self.mineral3_combo, self.mineral3_edit, self.mineral3_completer),
            (self.class_combo, self.class_edit, self.class_completer),
            (self.crystal_combo, self.crystal_edit, self.crystal_completer),
            (self.luminescence_combo, self.luminescence_edit, self.luminescence_completer),
            (self.intensity_combo, self.intensity_edit, self.intensity_completer),
            (self.fluorescence_color_combo, self.fluorescence_color_edit, self.fluorescence_color_completer),
            (self.site_combo, self.site_edit, self.site_completer),
            (self.department_combo, self.department_edit, self.department_completer),
            (self.region_combo, self.region_edit, self.region_completer),
            (self.country_combo, self.country_edit, self.country_completer),
            (self.box_type_combo, self.box_type_edit, self.box_type_completer),
            (self.category_combo, self.category_edit, self.category_completer),
            (self.contact_combo, self.contact_edit, self.contact_completer),
            (self.shape_combo, self.shape_edit, self.shape_completer),
            (self.color_combo, self.color_edit, self.color_completer),
            (self.quality_combo, self.quality_edit, self.quality_completer),
            (self.state_combo, self.state_edit, self.state_completer),
        )
        for combo, edit, completer in pairs:
            if focused not in (combo, edit, combo.view(), completer.popup()):
                continue
            if combo.view().isVisible() or completer.popup().isVisible():
                return True
        return False

    @staticmethod
    def _is_repeat_previous_shortcut(event) -> bool:
        """Reconnaît Ctrl + " sur les claviers français et internationaux."""
        modifiers = event.modifiers()
        if not (modifiers & Qt.KeyboardModifier.ControlModifier):
            return False

        # Sur un clavier AZERTY, le guillemet double correspond généralement
        # à Maj + 3. event.text() est la détection la plus fiable, mais les
        # deux variantes de touche sont également acceptées.
        if event.text() == '"':
            return True
        if event.key() == Qt.Key.Key_3 and (modifiers & Qt.KeyboardModifier.ShiftModifier):
            return True
        quote_key = getattr(Qt.Key, "Key_QuoteDbl", None)
        return quote_key is not None and event.key() == quote_key

    def _copy_previous_field(self, watched) -> bool:
        """Recopie, dans le champ actif, la valeur de la fiche précédente."""
        # Fiche réelle : précédente = position - 1.
        # Fiche virtuelle : position == len(records), donc la fiche précédente
        # est naturellement la dernière fiche réelle.
        if self._virtual_new_record and self.position == len(self.records):
            previous_index = len(self.records) - 1
        elif 0 <= self.position < len(self.records):
            previous_index = self.position - 1
        else:
            return True

        if previous_index < 0:
            self.statusBar().showMessage(
                "Aucune fiche précédente : aucune valeur à recopier.", 4000
            )
            return True

        previous = self.records[previous_index]
        if not bool(previous.get("__mm3_full_loaded__", True)):
            try:
                loaded = self.manager.get_record(int(previous["id"]), int(self.collection["id"]))
            except Exception:
                loaded = None
            if loaded is None:
                self.statusBar().showMessage("Impossible de lire la fiche précédente.", 4000)
                return True
            loaded["__mm3_full_loaded__"] = True
            self.records[previous_index] = loaded
            previous = loaded

        # 1.0.54 — moteur générique pour les champs personnalisés/importés.
        # Les collections récentes (et donc les modèles traduits) utilisent des
        # identifiants internes custom_... : ils ne doivent dépendre ni du
        # libellé affiché ni de la langue de la collection.
        custom_key = self._custom_key_for_widget(watched)
        if custom_key is None:
            model_key = self._model_key_for_widget(watched)
            if model_key in getattr(self, "_custom_field_inputs", {}):
                custom_key = model_key
        if custom_key is not None:
            definition = self._custom_field_defs.get(custom_key, {})
            # Un champ calculé reste piloté par sa formule : on ne lui injecte
            # jamais une valeur recopiée manuellement.
            if str(definition.get("field_type") or "") == "calculated":
                return True
            try:
                previous_values = self.manager.custom_values(int(previous["id"]))
            except Exception:
                previous_values = {}
            value = str(previous_values.get(custom_key, "") or "")
            self._set_custom_widget_value(custom_key, value)
            label = str(definition.get("label") or custom_key)

            # Même statut de modification que les champs historiques.
            if self._virtual_new_record and self.position == len(self.records):
                self._mark_dirty()
            else:
                self._set_dirty(True)
            self.statusBar().showMessage(
                f"{label} recopié depuis la fiche précédente.", 3500
            )
            return True

        if watched in (self.name_combo, self.name_edit):
            self.name_edit.setText(
                str(previous.get("mineral_name", "") or previous.get("species", "")).upper()
            )
            self.name_edit.setCursorPosition(len(self.name_edit.text()))
            label = "Nom"
        elif watched in (self.mineral2_combo, self.mineral2_edit):
            self.mineral2_combo.setCurrentText(str(previous.get("mineral_2", "")).upper())
            label = "Minéral 2"
        elif watched in (self.mineral3_combo, self.mineral3_edit):
            self.mineral3_combo.setCurrentText(str(previous.get("mineral_3", "")).upper())
            label = "Minéral 3"
        elif watched in (self.class_combo, self.class_edit):
            self.class_combo.setCurrentText(str(previous.get("mineral_class", "")))
            self.class_edit.setCursorPosition(len(self.class_edit.text()))
            label = "Classe"
        elif watched is self.formula_edit:
            self.formula_edit.setText(str(previous.get("chemical_formula", "")))
            self.formula_edit.setCursorPosition(len(self.formula_edit.text()))
            label = "Formule chimique"
        elif watched is self.internet_link_edit:
            self.internet_link_edit.setText(str(previous.get("internet_link", "")))
            self.internet_link_edit.setCursorPosition(len(self.internet_link_edit.text()))
            label = "Lien espèce"
        elif watched is self.site_link_edit:
            self.site_link_edit.setText(str(previous.get("site_internet_link", "")))
            self.site_link_edit.setCursorPosition(len(self.site_link_edit.text()))
            label = "Lien site"
        elif watched in (self.crystal_combo, self.crystal_edit, self.crystal_combo.lineEdit()):
            self.crystal_combo.setCurrentText(str(previous.get("crystal_system", "")))
            label = "Système cristallin"
        elif watched in (self.luminescence_combo, self.luminescence_edit, self.luminescence_combo.lineEdit()):
            self.luminescence_combo.setCurrentText(self._dv(str(previous.get("luminescence", "Non"))))
            label = "Luminescence"
        elif watched in (self.intensity_combo, self.intensity_edit, self.intensity_combo.lineEdit()):
            self.intensity_combo.setCurrentText(self._dv(str(previous.get("luminescence_intensity", "Aucune"))))
            label = "Intensité"
        elif watched in (self.fluorescence_color_combo, self.fluorescence_color_edit, self.fluorescence_color_combo.lineEdit()):
            self.fluorescence_color_combo.setCurrentText(self._dv(str(previous.get("fluorescence_color", "Aucune"))))
            label = "Couleur fluo"
        elif watched in (self.site_combo, self.site_edit, self.site_combo.lineEdit()):
            self.site_combo.setCurrentText(str(previous.get("site_name", "")))
            label = "Site"
        elif watched is self.deposit_edit:
            self.deposit_edit.setText(str(previous.get("deposit", "")))
            self.deposit_edit.setCursorPosition(len(self.deposit_edit.text()))
            label = "Gisement"
        elif watched in (self.department_combo, self.department_edit, self.department_combo.lineEdit()):
            self.department_combo.setCurrentText(str(previous.get("department", "")))
            label = "Département"
        elif watched in (self.region_combo, self.region_edit, self.region_combo.lineEdit()):
            self.region_combo.setCurrentText(str(previous.get("region", "")))
            label = "Région"
        elif watched in (self.country_combo, self.country_edit, self.country_combo.lineEdit()):
            self.country_combo.setCurrentText(str(previous.get("country", "")))
            label = "Pays"
        elif watched in (self.box_type_combo, self.box_type_edit, self.box_type_combo.lineEdit()):
            self.box_type_combo.setCurrentText(str(previous.get("box_type", "")))
            label = "Contenant"
        elif watched in (self.category_combo, self.category_edit, self.category_combo.lineEdit()):
            self.category_combo.setCurrentText(str(previous.get("category", "")))
            label = "Catégorie"
        elif watched in (self.contact_combo, self.contact_edit, self.contact_combo.lineEdit()):
            self.contact_combo.setCurrentText(str(previous.get("contact", "")))
            label = "Contact"
        elif watched in (self.shape_combo, self.shape_edit, self.shape_combo.lineEdit()):
            self.shape_combo.setCurrentText(str(previous.get("specimen_shape", "")))
            label = "Forme"
        elif watched in (self.color_combo, self.color_edit, self.color_combo.lineEdit()):
            self.color_combo.setCurrentText(str(previous.get("specimen_color", "")))
            label = "Couleur"
        elif watched in (self.quality_combo, self.quality_edit, self.quality_combo.lineEdit()):
            self.quality_combo.setCurrentText(str(previous.get("quality", "")))
            label = "Qualité"
        elif watched is self.description_edit:
            self._set_description_text(str(previous.get("description", "")))
            label = "Description"

        # Champs ajoutés à la répétition CTRL+".
        elif watched in (
            self.growth_combo, self.growth_edit, self.growth_combo.lineEdit()
        ):
            self.growth_combo.setCurrentText(str(previous.get("growth", "")))
            label = "Croissance"
        elif watched in (
            self.type_locality_combo, self.type_locality_combo.lineEdit()
            if self.type_locality_combo.isEditable() else self.type_locality_combo
        ):
            self.type_locality_combo.setCurrentText(
                self._bool_display(str(previous.get("type_locality", "") or "Non"))
            )
            label = "Localité type"
        elif watched in (
            self.minimum_magnification_combo,
            self.minimum_magnification_edit,
            self.minimum_magnification_combo.lineEdit(),
        ):
            self.minimum_magnification_combo.setCurrentText(
                str(previous.get("minimum_magnification", ""))
            )
            label = "Grossissement mini"
        elif watched is self.acquisition_date_edit:
            self.acquisition_date_edit.setText(
                self._format_date_value(str(previous.get("acquisition_date", "")))
            )
            label = "Date"
        elif watched in (
            self.origin_combo, self.origin_edit, self.origin_combo.lineEdit()
        ):
            self.origin_combo.setCurrentText(str(previous.get("origin", "")))
            label = "Origine"
        elif watched in (
            self.place_combo, self.place_edit, self.place_combo.lineEdit()
        ):
            self.place_combo.setCurrentText(str(previous.get("place", "")))
            label = "Lieu"
        elif watched is self.box_count_edit:
            self.box_count_edit.setText(str(previous.get("box_count", "") or ""))
            label = "Nombre de pièces"
        elif watched is self.price_edit:
            self.price_edit.setText(
                self._format_currency_value(str(previous.get("price", "")), self._currency_symbol_for_field("price"), self._currency_decimals_for_field("price"))
            )
            self._recalculate_total_cost()
            label = "Prix"
        elif watched in (self.state_combo, self.state_edit, self.state_combo.lineEdit()):
            self.state_combo.setCurrentText(self._state_display(str(previous.get("record_state", "OK"))))
            label = "État de la fiche"
        else:
            return False

        # Sur une fiche virtuelle, la répétition constitue une première saisie :
        # elle doit donc matérialiser immédiatement la fiche et lui donner son N°.
        if self._virtual_new_record and self.position == len(self.records):
            self._mark_dirty()
        else:
            self._set_dirty(True)

        self.statusBar().showMessage(
            f"{label} recopié depuis la fiche précédente.", 3500
        )
        return True


    def _mark_dirty(self, *_args) -> None:
        if self._loading:
            return

        if self._virtual_new_record and self.position == len(self.records):
            # La première modification réelle transforme la fiche virtuelle en
            # fiche persistante et lui attribue le prochain N°.
            try:
                created = self._apply_default_values_to_new_record(
                    self.manager.create_record(int(self.collection["id"]))
                )
            except Exception as exc:
                QMessageBox.critical(self, "Création impossible", str(exc))
                return

            self.records.append(created)
            self.position = len(self.records) - 1
            self._virtual_new_record = False
            self.number_value.setStyleSheet("")
            self.number_value.setText(str(created["record_number"]))
            self.position_label.setText(self._t("Fiche {current} sur {total}").format(current=len(self.records), total=len(self.records)))
            self.statusBar().showMessage(
                f"Nouvelle fiche N° {created['record_number']} créée", 4000
            )

            # La fiche est maintenant une vraie dernière fiche : Suivante doit
            # immédiatement redevenir disponible pour permettre validation +
            # ouverture d'une nouvelle fiche virtuelle.
            self.first_btn.setEnabled(self.position > 0)
            self.previous_btn.setEnabled(self.position > 0)
            self.next_btn.setEnabled(True)
            self.last_btn.setEnabled(False)

        if 0 <= self.position < len(self.records):
            self._set_dirty(True)
            try:
                current_id = self._current_record_id()
                if current_id is not None:
                    self.recordDraftChanged.emit(int(current_id), dict(self._current_values()))
            except Exception:
                pass

    def _recalculate_dirty_state(self) -> None:
        """Recalcule l'état modifié après une annulation de saisie."""
        if not (0 <= self.position < len(self.records)):
            self._set_dirty(False)
            return
        record = self.records[self.position]
        current = self._current_values()
        stored_name = str(record.get("mineral_name", "") or record.get("species", "")).strip().upper()
        changed = any((
            current["mineral_name"] != stored_name,
            current["mineral_2"] != str(record.get("mineral_2", "") or "").strip().upper(),
            current["mineral_3"] != str(record.get("mineral_3", "") or "").strip().upper(),
            current["mineral_class"] != str(record.get("mineral_class", "") or "").strip(),
            current["chemical_formula"] != str(record.get("chemical_formula", "") or "").strip(),
            current["internet_link"] != str(record.get("internet_link", "") or "").strip(),
            current["site_internet_link"] != str(record.get("site_internet_link", "") or "").strip(),
            current["crystal_system"] != str(record.get("crystal_system", "") or "").strip(),
            current["luminescence"] != str(record.get("luminescence", "Non") or "").strip(),
            current["luminescence_intensity"] != str(record.get("luminescence_intensity", "Aucune") or "").strip(),
            current["fluorescence_color"] != str(record.get("fluorescence_color", "Aucune") or "").strip(),
            current["site_name"] != str(record.get("site_name", "") or "").strip(),
            current["deposit"] != str(record.get("deposit", "") or "").strip(),
            current["department"] != str(record.get("department", "") or "").strip(),
            current["region"] != str(record.get("region", "") or "").strip(),
            current["country"] != str(record.get("country", "") or "").strip(),
            current["box_type"] != str(record.get("box_type", "") or "").strip(),
            current["category"] != str(record.get("category", "") or "").strip(),
            current["contact"] != str(record.get("contact", "") or "").strip(),
            current["specimen_shape"] != str(record.get("specimen_shape", "") or "").strip(),
            current["specimen_color"] != str(record.get("specimen_color", "") or "").strip(),
            current["quality"] != str(record.get("quality", "") or "").strip(),
            current["description"] != str(record.get("description", "") or "").strip(),
            current["minimum_magnification"] != str(record.get("minimum_magnification", "") or "").strip(),
            current["growth"] != str(record.get("growth", "") or "").strip(),
            current["type_locality"] != str(record.get("type_locality", "") or "").strip(),
            current["acquisition_date"] != str(record.get("acquisition_date", "") or "").strip(),
            current["origin"] != str(record.get("origin", "") or "").strip(),
            current["place"] != str(record.get("place", "") or "").strip(),
            current["box_count"] != str(record.get("box_count", "") or "").strip(),
            current["price"] != str(record.get("price", "") or "").strip(),
            current["total_cost"] != str(record.get("total_cost", "") or "").strip(),
            bytes(self._photo_data or b"") != bytes(record.get("photo_data") or b""),
            current["record_state"] != str(record.get("record_state", "OK") or "").strip(),
        ))
        self._set_dirty(changed)

    def _set_dirty(self, value: bool) -> None:
        self.dirty = value
        title = f"{self._t('Fiches — ')}{collection_display_name(self.collection, self.language)}"
        self.setWindowTitle(f"{title} *" if value else title)

    def _current_values(self) -> dict[str, str]:
        name = self.name_edit.text().strip().upper()
        return {
            "mineral_name": name,
            "mineral_2": self.mineral2_edit.text().strip().upper(),
            "mineral_3": self.mineral3_edit.text().strip().upper(),
            # Colonne conservée provisoirement pour compatibilité avec les briques précédentes.
            "species": name,
            "mineral_class": self._cv(self.class_combo.currentText()).strip(),
            "chemical_formula": self.formula_edit.text().strip(),
            "internet_link": self.internet_link_edit.text().strip(),
            "site_internet_link": self.site_link_edit.text().strip(),
            "crystal_system": self._cv(self.crystal_combo.currentText()).strip(),
            "luminescence": self._cv(self.luminescence_combo.currentText()).strip(),
            "luminescence_intensity": self._cv(self.intensity_combo.currentText()).strip(),
            "fluorescence_color": self._cv(self.fluorescence_color_combo.currentText()).strip(),
            "site_name": self.site_combo.currentText().strip(),
            "deposit": self.deposit_edit.text().strip(),
            "department": self.department_combo.currentText().strip(),
            "region": self.region_combo.currentText().strip(),
            "country": self.country_combo.currentText().strip(),
            "box_type": self._cv(self.box_type_combo.currentText()).strip(),
            "category": self._cv(self.category_combo.currentText()).strip(),
            "contact": self.contact_combo.currentText().strip(),
            "specimen_shape": self._cv(self.shape_combo.currentText()).strip(),
            "specimen_color": self._cv(self.color_combo.currentText()).strip(),
            "quality": self._cv(self.quality_combo.currentText()).strip(),
            "description": self.description_edit.toPlainText().strip(),
            "minimum_magnification": self._cv(self.minimum_magnification_combo.currentText()).strip(),
            "growth": self._cv(self.growth_combo.currentText()).strip(),
            "type_locality": self._cv(self.type_locality_combo.currentText()).strip(),
            "acquisition_date": self._format_date_value(
                self.acquisition_date_edit.text()
            ),
            "origin": self._cv(self.origin_combo.currentText()).strip(),
            "place": self._cv(self.place_combo.currentText()).strip(),
            "box_count": self.box_count_edit.text().strip(),
            "price": self._format_currency_value(self.price_edit.text(), self._currency_symbol_for_field("price"), self._currency_decimals_for_field("price")),
            "total_cost": self._format_currency_value(
                str(
                    self._parse_number_value(self.box_count_edit.text(), 0.0)
                    * self._parse_number_value(self.price_edit.text(), 0.0)
                ),
                self._currency_symbol_for_field("total_cost"),
                self._currency_decimals_for_field("total_cost"),
            ),
            "record_state": self._state_canonical(self.state_combo.currentText()).strip(),
        }

    def save_current_record(self) -> bool:
        if self._virtual_new_record and self.position == len(self.records):
            # Une fiche virtuelle intacte n'a rien à enregistrer.
            if not self.dirty:
                return True
            self._mark_dirty()
        if not (0 <= self.position < len(self.records)):
            return True
        values = self._current_values()
        if not self._ensure_name_in_referential(values["mineral_name"]):
            return False
        if not self._ensure_generic_referential("mineral_name", values["mineral_2"], "_mineral2_declined_for_value", "Nouveau minéral 2", "des noms", lambda v: self._reload_mineral_views(None, v, None)):
            return False
        if not self._ensure_generic_referential("mineral_name", values["mineral_3"], "_mineral3_declined_for_value", "Nouveau minéral 3", "des noms", lambda v: self._reload_mineral_views(None, None, v)):
            return False
        if not self._ensure_class_in_referential(values["mineral_class"]):
            return False
        if not self._ensure_crystal_in_referential(values["crystal_system"]):
            return False
        if not self._ensure_luminescence_in_referential(values["luminescence"]):
            return False
        if not self._ensure_intensity_in_referential(values["luminescence_intensity"]):
            return False
        if not self._ensure_fluorescence_color_in_referential(values["fluorescence_color"]):
            return False
        if not self._ensure_site_in_referential(values["site_name"]):
            return False
        if not self._ensure_department_in_referential(values["department"]):
            return False
        if not self._ensure_region_in_referential(values["region"]):
            return False
        if not self._ensure_country_in_referential(values["country"]):
            return False
        if not self._ensure_box_type_in_referential(values["box_type"]):
            return False
        if not self._ensure_category_in_referential(values["category"]):
            return False
        if not self._ensure_contact_in_referential(values["contact"]):
            return False
        if not self._ensure_shape_in_referential(values["specimen_shape"]):
            return False
        if not self._ensure_color_in_referential(values["specimen_color"]):
            return False
        if not self._ensure_quality_in_referential(values["quality"]):
            return False
        if not self._ensure_state_in_referential(values["record_state"]):
            return False
        if not self._ensure_generic_referential(
            "minimum_magnification", values["minimum_magnification"],
            "_minimum_magnification_declined_for_value", "Nouveau grossissement",
            "des grossissements", self._reload_minimum_magnification_referential
        ):
            return False
        if not self._ensure_generic_referential(
            "growth", values["growth"], "_growth_declined_for_value",
            "Nouvelle croissance", "des croissances", self._reload_growth_referential
        ):
            return False
        if not self._ensure_generic_referential(
            "origin", values["origin"], "_origin_declined_for_value",
            "Nouvelle origine", "des origines", self._reload_origin_referential
        ):
            return False
        if not self._ensure_generic_referential(
            "place", values["place"], "_place_declined_for_value",
            "Nouveau lieu", "des lieux", self._reload_place_referential
        ):
            return False
        try:
            updated = self.manager.update_record(
                int(self.records[self.position]["id"]), values,
                self._photo_data, self._photo_format
            )
        except Exception as exc:
            QMessageBox.critical(self, "Enregistrement impossible", str(exc))
            return False
        self.records[self.position] = updated
        try:
            self._save_extra_photos_for_current_record()
            self._save_custom_values_for_current_record()

            # Sécurisation Maître/Relié : au moment de l'enregistrement,
            # persister explicitement toutes les valeurs reliées visibles.
            # Cela couvre notamment les champs personnalisés importés et les
            # cas où editingFinished n'a pas été émis avant la navigation.
            for linked_key, master_key in dict(self._field_links).items():
                master_value = self._relation_widget_value(master_key)
                if not master_value:
                    continue
                linked_value = self._relation_widget_value(linked_key)
                self.model_manager.propagate_linked_value(
                    int(self.collection["id"]),
                    master_key, master_value, linked_key, linked_value
                )
        except Exception as exc:
            QMessageBox.critical(
                self, "Enregistrement impossible",
                f"La fiche a été enregistrée, mais pas ses champs personnalisés :\n{exc}"
            )
            return False
        self._reload_name_referential(str(updated.get("mineral_name", "")))
        self._reload_associated_minerals(str(updated.get("mineral_2", "")), str(updated.get("mineral_3", "")))
        self._reload_class_referential(str(updated.get("mineral_class", "")))
        self._reload_crystal_referential(str(updated.get("crystal_system", "")))
        self._reload_luminescence_referential(str(updated.get("luminescence", "Non")))
        self._reload_intensity_referential(str(updated.get("luminescence_intensity", "Aucune")))
        self._reload_fluorescence_color_referential(str(updated.get("fluorescence_color", "Aucune")))
        self._reload_site_referential(str(updated.get("site_name", "")))
        self._reload_department_referential(str(updated.get("department", "")))
        self._reload_region_referential(str(updated.get("region", "")))
        self._reload_country_referential(str(updated.get("country", "")))
        self._reload_box_type_referential(str(updated.get("box_type", "")))
        self._reload_category_referential(str(updated.get("category", "")))
        self._reload_contact_referential(str(updated.get("contact", "")))
        self._reload_shape_referential(str(updated.get("specimen_shape", "")))
        self._reload_color_referential(str(updated.get("specimen_color", "")))
        self._reload_quality_referential(str(updated.get("quality", "")))
        self._reload_state_referential(str(updated.get("record_state", "OK")))
        self._reload_minimum_magnification_referential(str(updated.get("minimum_magnification", "")))
        self._reload_growth_referential(str(updated.get("growth", "")))
        self._reload_origin_referential(str(updated.get("origin", "")))
        self._reload_place_referential(str(updated.get("place", "")))
        self._set_dirty(False)
        self.statusBar().showMessage(
            f"Fiche N° {updated['record_number']} enregistrée", 4000
        )
        self._invalidate_restore()

        # Synchronisation explicite avec les autres vues ouvertes.
        self.recordSaved.emit(int(updated["id"]))
        return True

    def _confirm_unsaved_changes(self) -> bool:
        if not self.dirty:
            return True
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle("Fiche modifiée")
        box.setText("Cette fiche a été modifiée.")
        box.setInformativeText("Que souhaitez-vous faire ?")
        save = box.addButton("Enregistrer", QMessageBox.ButtonRole.AcceptRole)
        discard = box.addButton("Ne pas enregistrer", QMessageBox.ButtonRole.DestructiveRole)
        cancel = box.addButton("Annuler", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(save)
        box.exec()
        clicked = box.clickedButton()
        if clicked is save:
            return self.save_current_record()
        if clicked is discard:
            self._set_dirty(False)
            return True
        return clicked is not cancel

    def _invalidate_restore(self) -> None:
        self._restore_snapshot = None
        self._restore_record_id = None
        if hasattr(self, "restore_record_btn"):
            self.restore_record_btn.setEnabled(False)

    def restore_cleared_record(self) -> None:
        """Restaure la dernière fiche vidée si elle est encore la fiche courante."""
        if self._restore_snapshot is None or self._restore_record_id is None:
            return
        if not (0 <= self.position < len(self.records)):
            self._invalidate_restore()
            return

        current = self.records[self.position]
        if int(current.get("id", -1)) != int(self._restore_record_id):
            self._invalidate_restore()
            return

        snapshot = dict(self._restore_snapshot)
        record_snapshot = dict(snapshot.get("record") or {})
        custom_snapshot = dict(snapshot.get("custom") or {})
        number = int(record_snapshot.get("record_number", 0))
        try:
            restored = self.manager.update_record(
                int(record_snapshot["id"]),
                record_snapshot,
                record_snapshot.get("photo_data"),
                str(record_snapshot.get("photo_format", "") or ""),
            )
            # 11.7.47 — le Tableau restaurait déjà ces valeurs. La vraie Fiche
            # doit elle aussi remettre les champs personnalisés effacés par le vidage.
            self.manager.replace_custom_values(
                int(record_snapshot["id"]), custom_snapshot
            )
        except Exception as exc:
            QMessageBox.critical(self, "Restauration impossible", str(exc))
            return

        self.records[self.position] = restored
        self._invalidate_restore()
        self._refresh_display()
        self._set_dirty(False)
        self.statusBar().showMessage(
            f"Fiche N° {number} restaurée dans son état précédent", 5000
        )

    def clear_current_record(self) -> None:
        """Libère la fiche courante sans jamais supprimer ni modifier son N°."""
        if not (0 <= self.position < len(self.records)):
            return
        record = self.records[self.position]
        number = int(record.get("record_number", 0))
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        lang = str(self.language or "fr").strip().lower()
        # Accepte également les libellés de langue et les codes régionaux.
        # La fenêtre de confirmation doit suivre la langue de la Fiche.
        if lang in {"deutsch", "german", "allemand", "de-de", "de_at", "de-at"}:
            lang = "de"
        elif lang in {"english", "anglais", "en-us", "en-gb", "en_us", "en_gb"}:
            lang = "en"
        if lang.startswith("en"):
            box.setWindowTitle("Clear record")
            box.setText(f"Do you want to completely clear record No. {number}?")
            box.setInformativeText(
                "All information and the photo will be erased. The record number will be kept "
                "and its status will become ‘Free’. This record can then be reused."
            )
            yes_label, no_label = "YES, clear record", "NO"
        elif lang.startswith("de"):
            box.setWindowTitle("Datensatz leeren")
            box.setText(f"Möchten Sie Datensatz Nr. {number} vollständig leeren?")
            box.setInformativeText(
                "Alle Angaben und das Foto werden gelöscht. Die Datensatznummer bleibt erhalten "
                "und der Status wird auf „Frei“ gesetzt. Der Datensatz kann anschließend erneut verwendet werden."
            )
            yes_label, no_label = "JA, Datensatz leeren", "NEIN"
        else:
            box.setWindowTitle("Vider la fiche")
            box.setText(f"Voulez-vous vider complètement la fiche N° {number} ?")
            box.setInformativeText(
                "Toutes les informations et la photo seront effacées. Le N° sera conservé "
                "et l’État de la fiche deviendra « Libre ». Cette fiche pourra ensuite être réutilisée."
            )
            yes_label, no_label = "OUI, vider la fiche", "NON"
        yes_button = box.addButton(yes_label, QMessageBox.ButtonRole.DestructiveRole)
        no_button = box.addButton(no_label, QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(no_button)
        box.exec()
        if box.clickedButton() is not yes_button:
            return
        # 11.7.47 — mémoriser l'état COMPLET avant le vidage, comme le Tableau :
        # données natives + photo + valeurs des champs personnalisés.
        # Le snapshot n'est validé que si le vidage aboutit.
        restore_snapshot = {
            "record": dict(record),
            "custom": self.manager.custom_values(int(record["id"])),
        }
        try:
            # « Libre » doit toujours être une valeur valide du référentiel d'état.
            if not self.referentials.contains(
                int(self.collection["id"]), "record_state", "Libre", active_only=True
            ):
                self.referentials.add_value(int(self.collection["id"]), "record_state", "Libre")
            updated = self.manager.clear_record_to_free(
                int(record["id"]), int(self.collection["id"])
            )
        except Exception as exc:
            QMessageBox.critical(self, "Vidage impossible", str(exc))
            return
        self.records[self.position] = updated
        self._restore_snapshot = restore_snapshot
        self._restore_record_id = int(record["id"])
        self._reload_state_referential("Libre")
        self._refresh_display()
        # _refresh_display() active Restaurer et grise Vider tant que cet
        # instantané correspond à la fiche courante.
        self._set_dirty(False)
        self.statusBar().showMessage(
            f"Fiche N° {number} vidée — État : Libre. "
            "« Restaurer la fiche » est disponible.", 7000
        )

    def _apply_default_values_to_new_record(self, record: dict) -> dict:
        """Applique les valeurs par défaut définies dans l'Atelier à une fiche neuve."""
        updated = dict(record)
        defaults = {
            "minimum_magnification": "20 X",
            "type_locality": "Non",
            "box_count": "1",
            "price": self._format_currency_value("0", self._currency_symbol_for_field("price"), self._currency_decimals_for_field("price")),
            "total_cost": self._format_currency_value("0", self._currency_symbol_for_field("total_cost"), self._currency_decimals_for_field("total_cost")),
        }
        try:
            styles = self.model_manager.field_styles(int(self.collection["id"]))
        except Exception:
            styles = {}
        # Une valeur explicitement enregistrée dans l'Atelier remplace le défaut
        # historique. Une chaîne vide signifie volontairement « aucun défaut ».
        for field in list(updated.keys()):
            style = styles.get(field, {}) if isinstance(styles, dict) else {}
            if isinstance(style, dict) and "default_value" in style:
                defaults[field] = str(style.get("default_value") or "")
        for field, default in defaults.items():
            if not str(updated.get(field, "") or "").strip() and str(default):
                updated[field] = str(default)
        # Le statut d'une fiche neuve est une valeur native fixe, non une
        # valeur par défaut modifiable par un modèle traduit.
        updated["record_state"] = "OK"
        return updated

    def _apply_custom_default_values_to_new_record(self, record_id: int) -> None:
        """Initialise les champs personnalisés d'une nouvelle fiche."""
        try:
            styles = self.model_manager.field_styles(int(self.collection["id"]))
            values = {}
            for key, definition in self._custom_field_defs.items():
                if str(definition.get("field_type") or "") == "calculated":
                    continue
                style = styles.get(key, {}) if isinstance(styles, dict) else {}
                if not isinstance(style, dict) or "default_value" not in style:
                    continue
                value = str(style.get("default_value") or "")
                if value:
                    values[str(key)] = value
            if values:
                self.manager.set_custom_values(int(record_id), values)
        except Exception:
            # Une valeur par défaut ne doit jamais empêcher la création d'une fiche.
            pass

    def create_record(self) -> None:
        if not self._confirm_unsaved_changes():
            return
        self._invalidate_restore()
        try:
            record = self._apply_default_values_to_new_record(
                self.manager.create_record(int(self.collection["id"]))
            )
            self._apply_custom_default_values_to_new_record(int(record["id"]))
        except Exception as exc:
            QMessageBox.critical(self, "Création impossible", str(exc))
            return
        self.records.append(record)
        self.position = len(self.records) - 1
        self._refresh_display()
        self.name_edit.setFocus()
        self.statusBar().showMessage(
            f"Fiche N° {record['record_number']} créée automatiquement", 5000
        )

    def _autosave_before_navigation(self) -> bool:
        """Enregistre silencieusement une fiche modifiée avant navigation."""
        if self.dirty:
            return self.save_current_record()
        return True

    def _navigate_to(self, new_position: int) -> None:
        if new_position == self.position and not self._virtual_new_record:
            return
        if not self._autosave_before_navigation():
            return
        self._invalidate_restore()
        self._virtual_new_record = False
        self.position = new_position
        self._refresh_display()

    def _show_virtual_new_record(self) -> None:
        if not self._autosave_before_navigation():
            return
        self._invalidate_restore()
        self._virtual_new_record = True
        self.position = len(self.records)
        self._set_dirty(False)
        self._refresh_display()
        self.name_edit.setFocus()

    def go_first(self) -> None:
        if self._quick_search_positions:
            self._quick_search_cursor = 0
            self._navigate_to(self._quick_search_positions[0])
        elif self.records:
            self._navigate_to(0)

    def go_previous(self) -> None:
        if self._quick_search_positions:
            self._sync_quick_search_cursor()
            if self._quick_search_cursor > 0:
                self._quick_search_cursor -= 1
                self._navigate_to(self._quick_search_positions[self._quick_search_cursor])
            return
        if self._virtual_new_record:
            if self.records:
                self._navigate_to(len(self.records) - 1)
            return
        if self.position > 0:
            self._navigate_to(self.position - 1)

    def go_next(self) -> None:
        if self._quick_search_positions:
            self._sync_quick_search_cursor()
            if self._quick_search_cursor < len(self._quick_search_positions) - 1:
                self._quick_search_cursor += 1
                self._navigate_to(self._quick_search_positions[self._quick_search_cursor])
            return
        if self._virtual_new_record:
            return
        if self.position < len(self.records) - 1:
            self._navigate_to(self.position + 1)
        elif self.position == len(self.records) - 1:
            self._show_virtual_new_record()

    def go_last(self) -> None:
        if self._quick_search_positions:
            self._quick_search_cursor = len(self._quick_search_positions) - 1
            self._navigate_to(self._quick_search_positions[self._quick_search_cursor])
        elif self.records:
            self._navigate_to(len(self.records) - 1)

    def go_to_record_number(self, *_args) -> None:
        """Accès direct à une fiche par son N° depuis « Fiche xx sur xx »."""
        if not self.records:
            return

        current_number = (
            int(self.records[self.position].get("record_number", 0))
            if 0 <= self.position < len(self.records)
            else 1
        )
        number, ok = QInputDialog.getInt(
            self,
            "Aller à la fiche",
            "N° de fiche :",
            current_number,
            1,
            2_147_483_647,
            1,
        )
        if not ok:
            return

        for index, record in enumerate(self.records):
            if int(record.get("record_number", 0) or 0) == int(number):
                self._navigate_to(index)
                return

        QMessageBox.information(
            self,
            "Fiche introuvable",
            f"Aucune fiche N° {number} n'existe dans cette collection.",
        )

    def _available_screen_geometry(self, x: int | None = None, y: int | None = None):
        """Retourne la zone réellement utilisable de l'écran concerné."""
        screen = None
        if x is not None and y is not None:
            from PySide6.QtCore import QPoint
            screen = QApplication.screenAt(QPoint(int(x), int(y)))
        if screen is None:
            screen = self.screen()
        if screen is None:
            screen = QApplication.primaryScreen()
        return screen.availableGeometry() if screen is not None else None

    def _default_window_geometry(self) -> tuple[int, int, int, int]:
        """Géométrie compacte par défaut, centrée et adaptée à l'écran."""
        available = self._available_screen_geometry()
        if available is None:
            return (80, 60, 1280, 820)

        margin_x = 40
        margin_y = 35
        width = min(1280, max(self.minimumWidth(), available.width() - 2 * margin_x))
        height = min(820, max(self.minimumHeight(), available.height() - 2 * margin_y))
        width = min(width, available.width())
        height = min(height, available.height())
        x = available.x() + max(0, (available.width() - width) // 2)
        y = available.y() + max(0, (available.height() - height) // 2)
        return (x, y, width, height)

    def _clamp_window_geometry(
        self, x: int, y: int, width: int, height: int
    ) -> tuple[int, int, int, int]:
        """Ramène une géométrie mémorisée dans l'écran disponible actuel."""
        center_x = int(x) + max(1, int(width)) // 2
        center_y = int(y) + max(1, int(height)) // 2
        available = self._available_screen_geometry(center_x, center_y)
        if available is None:
            return self._default_window_geometry()

        width = max(self.minimumWidth(), int(width))
        height = max(self.minimumHeight(), int(height))
        width = min(width, available.width())
        height = min(height, available.height())

        min_x = available.x()
        min_y = available.y()
        max_x = available.x() + available.width() - width
        max_y = available.y() + available.height() - height

        x = min(max(int(x), min_x), max_x)
        y = min(max(int(y), min_y), max_y)
        return (x, y, width, height)

    def _restore_window_geometry(self) -> None:
        """Restaure taille/position utilisateur ou applique le format compact."""
        raw = str(getattr(self.startup.settings, "record_window_geometry", "") or "").strip()
        geometry = None

        if raw:
            try:
                parts = [int(part.strip()) for part in raw.split(",")]
                if len(parts) == 4:
                    geometry = tuple(parts)
            except (TypeError, ValueError):
                geometry = None

        if geometry is None:
            geometry = self._default_window_geometry()

        x, y, width, height = self._clamp_window_geometry(*geometry)
        self.setGeometry(x, y, width, height)

    def reset_window_geometry(self) -> None:
        """Rétablit immédiatement la géométrie compacte de référence MM3."""
        if self.isMaximized() or self.isFullScreen():
            self.showNormal()
        x, y, width, height = self._default_window_geometry()
        x, y, width, height = self._clamp_window_geometry(x, y, width, height)
        self.setGeometry(x, y, width, height)
        self.startup.settings.record_window_geometry = f"{x},{y},{width},{height}"
        self.startup.settings.save()

    def _save_window_geometry(self) -> None:
        """Mémorise la géométrie normale dans le Workspace portable."""
        # Si l'utilisateur ferme en maximisé, conserver la dernière taille normale
        # afin que la prochaine ouverture reste une fenêtre de travail.
        geometry = self.normalGeometry() if self.isMaximized() else self.geometry()
        x, y, width, height = self._clamp_window_geometry(
            geometry.x(), geometry.y(), geometry.width(), geometry.height()
        )
        self.startup.settings.record_window_geometry = f"{x},{y},{width},{height}"
        self.startup.settings.save()

    def _ensure_global_event_filter(self) -> None:
        """Installe seulement les filtres nécessaires aux popups de la Fiche.

        39.32.11.7.11 — la Fiche ne devient plus filtre global de QApplication.
        Les champs ont déjà leur filtre local ; seuls les popups des QComboBox
        et QCompleter doivent aussi intercepter Entrée/Tab.
        """
        if self._global_filter_installed:
            return
        self._global_filter_installed = True
        for combo in self.findChildren(QComboBox):
            try:
                view = combo.view()
                if view is not None:
                    view.installEventFilter(self)
                completer = combo.completer()
                if completer is not None and completer.popup() is not None:
                    completer.popup().installEventFilter(self)
            except Exception:
                pass

    def showEvent(self, event) -> None:  # noqa: N802 (Qt convention)
        self._ensure_global_event_filter()
        super().showEvent(event)

    def _confirm_referentials_in_batch_before_close(self) -> bool:
        """One decision for all missing reference values, including imported records.

        The current unsaved form values are included. This operation changes
        only the current collection's referential lists, never the source/model.
        """
        if self.preview_mode:
            return True
        cid = int(self.collection["id"])
        try:
            # 20.34 : les référentiels ne nécessitent pas les photos ni les
            # autres colonnes lourdes de chaque fiche.
            records = self.manager.list_record_referential_values(cid)
            if 0 <= self.position < len(self.records):
                current_id = int(self.records[self.position]["id"])
                current_values = self._current_values()
                for record in records:
                    if int(record.get("id") or 0) == current_id:
                        record.update(current_values)
                        break
            candidates = {}
            for record in records:
                for field, code in REFERENTIAL_BY_FIELD.items():
                    value = str(record.get(field) or "").strip()
                    if value:
                        candidates.setdefault(code, set()).add(value)
            missing = {}
            for code, values in candidates.items():
                active = {
                    self.referentials.normalize(str(v), code).casefold()
                    for v in self.referentials.list_values(cid, code, active_only=True)
                }
                remaining = sorted((
                    self.referentials.normalize(value, code)
                    for value in values
                    if self.referentials.normalize(value, code).casefold() not in active
                ), key=str.casefold)
                if code == "record_state":
                    remaining = [v for v in remaining if v in {"OK", "Vérifier", "Libre"}]
                if remaining:
                    missing[code] = list(dict.fromkeys(remaining))
        except Exception as exc:
            QMessageBox.critical(self, "Vérification des référentiels impossible", str(exc))
            return False
        if not missing:
            return True
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle("Enregistrement des référentiels")
        box.setText("Des valeurs des fiches ne figurent pas encore dans les référentiels de cette collection.")
        box.setInformativeText("Voulez-vous les enregistrer toutes en une seule opération ?")
        box.setDetailedText("\n".join(
            f"{code} ({len(values)}) : " + ", ".join(values[:20])
            for code, values in missing.items()))
        for detail_button in box.findChildren(QPushButton):
            if "details" in detail_button.text().casefold():
                detail_button.setText("Afficher les détails…")

        save_all = box.addButton("Enregistrer tout", QMessageBox.ButtonRole.AcceptRole)
        skip = box.addButton("Ne rien ajouter", QMessageBox.ButtonRole.DestructiveRole)
        cancel = box.addButton("Annuler", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(save_all)
        box.exec()
        clicked = box.clickedButton()
        if clicked is cancel or clicked is None:
            return False
        if clicked is skip:
            self._batch_skip_referential_prompts = True
            return True
        try:
            for code, values in missing.items():
                self.referentials.add_values_bulk(cid, code, values)
            self._batch_skip_referential_prompts = True
            return True
        except Exception as exc:
            QMessageBox.critical(self, "Enregistrement des référentiels impossible", str(exc))
            return False

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt convention)
        if self.preview_mode:
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Warning)
            box.setWindowTitle("Fermer l’aperçu temporaire ?")
            box.setText("La copie temporaire et toutes les modifications effectuées pendant cet aperçu vont être supprimées.")
            close_btn = box.addButton("Fermer l’aperçu", QMessageBox.ButtonRole.DestructiveRole)
            cancel_btn = box.addButton("Annuler", QMessageBox.ButtonRole.RejectRole)
            box.setDefaultButton(cancel_btn)
            box.exec()
            if box.clickedButton() is not close_btn:
                event.ignore()
                return
            # Les données de cette fenêtre sont jetables : ne pas demander une seconde fois
            # d'enregistrer les éventuelles saisies en cours.
            self.dirty = False
        if not self.preview_mode and not self._confirm_referentials_in_batch_before_close():
            event.ignore()
            return
        if not self._confirm_unsaved_changes():
            self._batch_skip_referential_prompts = False
            event.ignore()
            return
        self._batch_skip_referential_prompts = False

        self._save_window_geometry()
        if not self.preview_mode:
            try:
                self.model_manager.set_collection_preferences(
                    int(self.collection["id"]),
                    last_record_id=self._current_record_id(),
                    update_last_record=True,
                )
            except Exception:
                pass

        # 39.32.11.7.13 — fermeture utilisateur = simple masquage.
        # Conserver l'arbre Qt vivant rend les réouvertures quasi immédiates et
        # évite de reconstruire toute la Fiche. Lors d'une vraie fermeture de
        # collection, MainWindow._safe_close_qt_window active WA_DeleteOnClose :
        # dans ce seul cas on laisse Qt détruire l'objet et on signale sa fin.
        force_destroy = self.testAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        if force_destroy:
            self._invalidate_restore()
            self._global_filter_installed = False
            event.accept()
            self.windowClosed.emit()
            return

        event.accept()
