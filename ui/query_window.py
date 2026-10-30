#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from core.collection_folders import collection_display_name
from core.i18n import tr, display_native_value, canonical_native_value, translate_widget_tree

import copy
import json
import sqlite3
from pathlib import Path

from collections.abc import Callable

from PySide6.QtCore import QStringListModel, Qt
from PySide6.QtGui import QColor
from core.referential_manager import ReferentialManager
from ui.collection_theme import collection_theme
from core.field_catalog import QUERY_COLUMNS, NUMERIC_FIELDS, DATE_FIELDS, REFERENTIAL_BY_FIELD, FIELD_BY_KEY, field_sort_key
from core.model_manager import ModelManager
from core.model_library import library_root, workspace_root_from_database, write_model, read_model, collect_model_field_keys, build_field_manifest
from ui.model_library_dialog import choose_model_save_path, choose_model_open_path, resolve_model_fields
from ui.saved_model_folders import choose_folder, manage_folders, SavedModelCombo
from core import saved_model_folders as model_folders
from core.collection_saved_models import load as load_collection_models, save as save_collection_models

from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QCompleter,
    QFrame,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


def _mm3_is_record_state_label(value) -> bool:
    """Reconnaît le libellé système État de la fiche, accents/casse indifférents."""
    text = str(value or "").strip().casefold()
    text = text.replace("é", "e").replace("è", "e").replace("ê", "e").replace("ë", "e")
    return text == "etat de la fiche"


TEXT_OPERATORS: tuple[tuple[str, str], ...] = (
    ("Contient", "contient"),
    ("Tous", "tous"),
    ("Commence par", "commence_par"),
    ("Est exactement", "exactement"),
    ("Est différent de", "different"),
    ("Se termine par", "termine_par"),
    ("Est vide", "est_vide"),
    ("N’est pas vide", "non_vide"),
)

NUMERIC_OPERATORS: tuple[tuple[str, str], ...] = (
    ("Égal à", "num_egal"),
    ("Tous", "tous"),
    ("Différent de", "num_different"),
    ("Supérieur à", "superieur"),
    ("Supérieur ou égal à", "superieur_egal"),
    ("Inférieur à", "inferieur"),
    ("Inférieur ou égal à", "inferieur_egal"),
    ("Compris entre", "entre"),
    ("Est vide", "est_vide"),
    ("N’est pas vide", "non_vide"),
)

DATE_OPERATORS: tuple[tuple[str, str], ...] = (
    ("Égal au", "num_egal"),
    ("Tous", "tous"),
    ("Différent du", "num_different"),
    ("Après le", "superieur"),
    ("À partir du", "superieur_egal"),
    ("Avant le", "inferieur"),
    ("Jusqu’au", "inferieur_egal"),
    ("Compris entre", "entre"),
    ("Année entière", "annee_entiere"),
    ("Est vide", "est_vide"),
    ("N’est pas vide", "non_vide"),
)

NO_VALUE_OPERATORS = {"tous", "est_vide", "non_vide"}





class QueryCompletingLineEdit(QLineEdit):
    """Zone de saisie avec complétion inline stable."""

    def __init__(self, choices: list[str], parent=None) -> None:
        super().__init__(parent)
        self._mm3_choices = tuple(str(v) for v in choices if str(v))
        self._mm3_internal_change = False

        model = QStringListModel(list(self._mm3_choices), self)
        completer = QCompleter(model, self)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.setCompleter(completer)
        self._mm3_completion_model = model
        self._mm3_completer = completer

    def set_choices(self, choices: list[str]) -> None:
        self._mm3_choices = tuple(str(v) for v in choices if str(v))
        self._mm3_completion_model.setStringList(list(self._mm3_choices))

    def keyPressEvent(self, event):  # type: ignore[override]
        # Qt traite d'abord la frappe normalement.
        super().keyPressEvent(event)

        if self._mm3_internal_change:
            return

        # Retour arrière / Suppr annulent la proposition inline en cours sans
        # la recréer immédiatement. L'utilisateur peut ensuite poursuivre avec
        # un autre texte, même absent du référentiel.
        if event.key() in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete):
            try:
                current = self.text()
                if current:
                    self._mm3_completer.setCompletionPrefix(current)
                    self._mm3_completer.complete()
            except RuntimeError:
                pass
            return

        if event.key() in (
            Qt.Key.Key_Up, Qt.Key.Key_Down,
            Qt.Key.Key_Left, Qt.Key.Key_Right,
            Qt.Key.Key_Return, Qt.Key.Key_Enter,
            Qt.Key.Key_Escape, Qt.Key.Key_Tab, Qt.Key.Key_Backtab,
        ):
            return

        current = self.text()
        selected = self.selectedText()
        base = current[:len(current) - len(selected)] if selected else current

        if not base:
            return

        prefix_matches = [
            value for value in self._mm3_choices
            if value.casefold().startswith(base.casefold())
        ]

        if len(prefix_matches) == 1:
            match = prefix_matches[0]
            if match.casefold() != base.casefold():
                self._mm3_internal_change = True
                try:
                    self.setText(match)
                    self.setSelection(len(base), len(match) - len(base))
                finally:
                    self._mm3_internal_change = False

        try:
            c = self._mm3_completer
            c.setCompletionPrefix(base)
            c.complete()
        except RuntimeError:
            pass



class QueryValueCombo(QComboBox):
    """Valeur de requête avec liste assistée du référentiel, sans écriture."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.setMaxVisibleItems(25)
        self._line = QueryCompletingLineEdit([], self)
        self._line.setClearButtonEnabled(True)
        self.setLineEdit(self._line)
        self.set_values([])

    def set_values(self, values: list[str]) -> None:
        current = self.currentText()
        self.blockSignals(True)
        QComboBox.clear(self)
        self.addItems(values)
        self._line.set_choices(values)
        self.setEditText(current)
        self.blockSignals(False)

        if values:
            self.setStyleSheet("")
            self.setToolTip(
                "Tapez quelques lettres ou ouvrez la liste. "
                "La requête ne peut pas ajouter de valeur au référentiel."
            )
        else:
            self.setStyleSheet(
                "QComboBox::drop-down { width: 0px; border: none; }"
                "QComboBox::down-arrow { image: none; }"
            )
            self.setToolTip("")

    def text(self) -> str:
        return self.currentText()

    def setText(self, value: str) -> None:
        self.setEditText(str(value or ""))

    def clear(self) -> None:  # type: ignore[override]
        self.setEditText("")

    def setPlaceholderText(self, text: str) -> None:
        self._line.setPlaceholderText(text)

    def setClearButtonEnabled(self, enabled: bool) -> None:
        self._line.setClearButtonEnabled(enabled)
    def clear_text(self) -> None:
        self.setEditText("")

    def selectAll(self) -> None:
        self._line.selectAll()



class QueryCriterionRow(QFrame):
    """Une ligne de critère : [ET/OU] Champ → Opérateur → Valeur."""

    def __init__(
        self,
        columns: tuple[tuple[str, str], ...],
        remove_callback: Callable[["QueryCriterionRow"], None],
        move_up_callback: Callable[["QueryCriterionRow"], None],
        move_down_callback: Callable[["QueryCriterionRow"], None],
        value_provider: Callable[[str], list[str]],
        numeric_fields: set[str] | None = None,
        date_fields: set[str] | None = None,
        language: str = "fr",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.columns = tuple(columns)
        self.numeric_fields = set(numeric_fields or NUMERIC_FIELDS)
        self.date_fields = set(date_fields or DATE_FIELDS)
        self.remove_callback = remove_callback
        self.move_up_callback = move_up_callback
        self.move_down_callback = move_down_callback
        self.value_provider = value_provider
        self.language = language or "fr"
        self.setObjectName("criterionRow")

        row = QHBoxLayout(self)
        row.setContentsMargins(10, 8, 10, 8)
        row.setSpacing(8)

        self.connector_combo = QComboBox()
        self.connector_combo.setFixedWidth(68)
        self.connector_combo.addItem("ET", "and")
        self.connector_combo.addItem("OU", "or")

        self.field_combo = QComboBox()
        self.field_combo.setMinimumWidth(180)
        for label, field in sorted(self.columns, key=lambda item: field_sort_key(item[0])):
            if field != "photo_data":
                self.field_combo.addItem(label, field)
                if field in {"record_number", "record_state"} or str(label) in {"N°", "État de la fiche"}:
                    self.field_combo.setItemData(self.field_combo.count()-1, QColor("#0055FF"), Qt.ItemDataRole.ForegroundRole)

        self.operator_combo = QComboBox()
        self.operator_combo.setMinimumWidth(175)

        self.value_edit = QueryValueCombo()
        self.value_edit.setPlaceholderText("Valeur recherchée…")
        self.value_edit.setClearButtonEnabled(True)

        self.value_edit_2 = QLineEdit()
        self.value_edit_2.setPlaceholderText("Et…")
        self.value_edit_2.setClearButtonEnabled(True)
        self.value_edit_2.setVisible(False)

        self.up_button = QPushButton("↑")
        self.up_button.setObjectName("moveCriterion")
        self.up_button.setToolTip("Monter ce critère")
        self.up_button.setFixedWidth(34)

        self.down_button = QPushButton("↓")
        self.down_button.setObjectName("moveCriterion")
        self.down_button.setToolTip("Descendre ce critère")
        self.down_button.setFixedWidth(34)

        self.remove_button = QPushButton(tr("Supprimer", self.language))
        self.remove_button.setObjectName("removeCriterion")
        self.remove_button.clicked.connect(lambda: self.remove_callback(self))
        self.up_button.clicked.connect(lambda: self.move_up_callback(self))
        self.down_button.clicked.connect(lambda: self.move_down_callback(self))

        row.addWidget(self.connector_combo)
        row.addWidget(self.field_combo)
        row.addWidget(self.operator_combo)
        row.addWidget(self.value_edit, 1)
        row.addWidget(self.value_edit_2, 1)
        row.addWidget(self.up_button)
        row.addWidget(self.down_button)
        row.addWidget(self.remove_button)

        self.field_combo.currentIndexChanged.connect(self._field_changed)
        self.operator_combo.currentIndexChanged.connect(self._operator_changed)

        # Initialiser immédiatement le référentiel du champ affiché.
        # Sans ce rafraîchissement final, la première liste pouvait rester vide
        # jusqu'au premier changement de champ (ex. Couleur -> Site -> Couleur).
        self._field_changed()

    def _is_date_field(self, field: str) -> bool:
        return str(field or "") in self.date_fields

    def _operators_for_current_field(self) -> tuple[tuple[str, str], ...]:
        field = str(self.field_combo.currentData() or "")
        if self._is_date_field(field):
            return DATE_OPERATORS
        if field in self.numeric_fields:
            return NUMERIC_OPERATORS
        return TEXT_OPERATORS

    def _field_changed(self, *_args) -> None:
        field = str(self.field_combo.currentData() or "")
        current_text = self.value_edit.text()
        self.value_edit.set_values(self.value_provider(field))
        self.value_edit.setText(current_text)

        previous = self.operator_combo.currentData()
        self.operator_combo.blockSignals(True)
        self.operator_combo.clear()
        for label, operator in self._operators_for_current_field():
            self.operator_combo.addItem(tr(label, self.language), operator)

        index = self.operator_combo.findData(previous)
        self.operator_combo.setCurrentIndex(index if index >= 0 else 0)
        self.operator_combo.blockSignals(False)
        self._operator_changed()


    def _operator_changed(self, *_args) -> None:
        operator = str(self.operator_combo.currentData() or "")
        needs_value = operator not in NO_VALUE_OPERATORS
        is_between = operator == "entre"
        self.value_edit.setEnabled(needs_value)
        self.value_edit_2.setVisible(is_between)
        self.value_edit_2.setEnabled(is_between)

        field = str(self.field_combo.currentData() or "")
        is_numeric = field in self.numeric_fields
        is_date = self._is_date_field(field)

        if not needs_value:
            self.value_edit.clear()
            self.value_edit_2.clear()
            self.value_edit.setPlaceholderText("Aucune valeur nécessaire")
            return

        if is_between:
            if is_date:
                self.value_edit.setPlaceholderText("Date début…")
                self.value_edit_2.setPlaceholderText("Date fin…")
            else:
                self.value_edit.setPlaceholderText("Minimum…")
                self.value_edit_2.setPlaceholderText("Maximum…")
        else:
            self.value_edit_2.clear()
            if is_numeric:
                self.value_edit.setPlaceholderText("Nombre…")
            elif is_date:
                self.value_edit.setPlaceholderText("Date…")
            else:
                self.value_edit.setPlaceholderText("Valeur recherchée…")

    def set_first(self, is_first: bool) -> None:
        self.connector_combo.setVisible(not is_first)

    def set_move_state(self, can_move_up: bool, can_move_down: bool) -> None:
        self.up_button.setEnabled(can_move_up)
        self.down_button.setEnabled(can_move_down)

    def criterion(self) -> dict[str, str] | None:
        operator = str(self.operator_combo.currentData() or "contient")
        value = self.value_edit.text().strip()
        value2 = self.value_edit_2.text().strip()
        if operator not in NO_VALUE_OPERATORS and not value:
            return None
        if operator == "entre" and not value2:
            return None
        language = getattr(self.window(), "language", "fr")
        return {
            "connector": str(self.connector_combo.currentData() or "and"),
            "field": str(self.field_combo.currentData() or ""),
            "operator": operator,
            "value": canonical_native_value(value, language),
            "value2": canonical_native_value(value2, language),
        }

    def set_criterion(self, criterion: dict[str, str]) -> None:
        """Restaure une ligne enregistrée sans perdre les opérateurs adaptés."""
        field = str(criterion.get("field", ""))
        field_index = self.field_combo.findData(field)
        if field_index >= 0:
            self.field_combo.setCurrentIndex(field_index)

        operator = str(criterion.get("operator", "contient"))
        operator_index = self.operator_combo.findData(operator)
        if operator_index >= 0:
            self.operator_combo.setCurrentIndex(operator_index)

        connector = str(criterion.get("connector", "and"))
        connector_index = self.connector_combo.findData(connector)
        if connector_index >= 0:
            self.connector_combo.setCurrentIndex(connector_index)

        self.value_edit.setText(display_native_value(str(criterion.get("value", "")), getattr(self.window(),"language","fr")))
        self.value_edit_2.setText(display_native_value(str(criterion.get("value2", "")), getattr(self.window(),"language","fr")))

    def clear_value(self) -> None:
        self.value_edit.clear_text()
        self.value_edit_2.clear()


class QueryWindow(QMainWindow):
    """Constructeur de requête multicritère avec opérateurs adaptés aux champs."""

    def __init__(
        self,
        collection: dict,
        columns: tuple[tuple[str, str], ...],
        execute_callback: Callable[[list[dict[str, str]]], int],
        database_path,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.collection = dict(collection)
        self.language = getattr(parent, 'language', 'fr') or 'fr'
        self.database_path = database_path
        self.model_manager = ModelManager(database_path)
        self._custom_field_defs = self.model_manager.custom_field_map(int(self.collection["id"]))
        self.columns = self._collection_columns(tuple(columns))
        self.numeric_fields = set(NUMERIC_FIELDS) | {
            key for key, definition in self._custom_field_defs.items()
            if str(definition.get("field_type") or "") in {"numeric", "currency"}
        }
        self.date_fields = set(DATE_FIELDS) | {
            key for key, definition in self._custom_field_defs.items()
            if str(definition.get("field_type") or "") == "date"
        }
        self.execute_callback = execute_callback
        self.referentials = ReferentialManager(database_path)
        self.referentials.ensure_defaults(int(self.collection["id"]))
        self.criterion_rows: list[QueryCriterionRow] = []
        self.saved_queries: dict[str, dict] = {}
        self.current_query_name: str | None = None
        self.last_query_name: str | None = None
        self.query_order_mode = "alphabetical"
        self.query_custom_order: list[str] = []
        self._loading_saved_query = False
        # Les requêtes enregistrées sont des préférences de collection, au même
        # titre que les vues enregistrées.
        workspace = getattr(parent, "startup", None)
        if workspace is not None:
            settings_path = parent.startup.workspace.settings_path
        else:
            # Repli robuste : database_path est normalement Workspace/Collections/micromin3.db.
            settings_path = database_path.parent.parent / "Parametres"
        self.queries_file = settings_path / "saved_queries.json"
        self._load_saved_queries()

        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.setWindowTitle(f"{tr('Requête multicritère', self.language)} — {collection_display_name(self.collection, self.language)}")
        self.resize(950, 560)
        self.setMinimumSize(780, 450)
        self._build_ui()
        translate_widget_tree(self, self.language)
        self._apply_style()
        if self.last_query_name and self.last_query_name in self.saved_queries:
            state = self.saved_queries.get(self.last_query_name)
            if isinstance(state, dict):
                self._apply_query_state(self.last_query_name, state)
                self._refresh_saved_queries_combo(self.last_query_name)

    def _refresh_active_model_name(self) -> None:
        name = str(getattr(self, "active_model_name", "") or self.current_query_name or "Nouvelle requête").strip()
        if hasattr(self, "model_name_label"):
            self.model_name_label.setText(f"{tr('Modèle actif :', self.language)} {tr(name,self.language)}")
        if hasattr(self, "query_title_label"):
            self.query_title_label.setText(f"{tr('Constructeur de requête multicritère', self.language)} — {tr('Modèle :', self.language)} {tr(name,self.language)}")
        self.setWindowTitle(f"{tr('Requête multicritère', self.language)} — {collection_display_name(self.collection, self.language)} — {tr(name,self.language)}")

    def _collection_columns(
        self, native_columns: tuple[tuple[str, str], ...]
    ) -> tuple[tuple[str, str], ...]:
        """Champs de requête issus du modèle réel de la collection."""
        cid = int(self.collection["id"])
        visible = set(self.model_manager.visible_fields(cid))
        labels = self.model_manager.custom_labels(cid)
        native_labels = {field: label for label, field in native_columns}
        ordered = self.model_manager.tab_order(cid, list(visible))
        if "record_state" not in visible:
            visible.add("record_state")
            ordered = list(ordered) + ["record_state"]

        result: list[tuple[str, str]] = []
        seen: set[str] = set()
        for key in ordered:
            key = str(key)
            if key in seen or key == "photo_data" or key not in visible:
                continue
            seen.add(key)
            custom = self._custom_field_defs.get(key)
            if custom is not None:
                label = (
                    str(labels.get(key) or "").strip()
                    or str(custom.get("label") or "").strip()
                    or key
                )
            else:
                spec = FIELD_BY_KEY.get(key)
                label = (
                    str(labels.get(key) or "").strip()
                    or native_labels.get(key)
                    or (str(spec.label) if spec is not None else key)
                )
            result.append((tr(str(label), self.language), key))

        # Un seul « État de la fiche » : certaines collections importées possèdent
        # encore un ancien champ personnalisé portant le même libellé. Le champ
        # système record_state est prioritaire et l'ancien doublon ne doit jamais
        # apparaître dans les sélecteurs.
        if any(str(key) == "record_state" for _label, key in result):
            result = [
                (label, key) for label, key in result
                if str(key) == "record_state" or not _mm3_is_record_state_label(label)
            ]
        return tuple(sorted(result, key=lambda item: field_sort_key(item[0])))

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("queryRoot")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(12)

        title = QLabel("Constructeur de requête multicritère")
        self.query_title_label = title
        title.setObjectName("queryTitle")
        subtitle = QLabel(
            "Choisissez un champ : G-Skol adapte automatiquement les comparaisons possibles. "
            "À partir de la deuxième ligne, utilisez ET pour restreindre le résultat ou OU pour l’élargir."
        )
        subtitle.setObjectName("querySubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        self.active_model_name = None
        self.model_name_label = QLabel("Modèle : Nouvelle requête")
        self.model_name_label.setStyleSheet("font-weight: 600; color: #5A3A2A;")
        layout.addWidget(self.model_name_label)
        layout.addWidget(subtitle)

        saved_row = QHBoxLayout()
        saved_label = QLabel(tr("Requête enregistrée :", self.language))
        saved_label.setFixedWidth(120)

        self.saved_queries_combo = SavedModelCombo(self, lambda: self.database_path, lambda: self.collection["id"], "requete", lambda: self.saved_queries)
        self.saved_queries_combo.setMinimumWidth(300)
        self.saved_queries_combo.currentIndexChanged.connect(self._on_saved_query_selected)

        self.save_query_button = QPushButton("Enregistrer la requête…")
        self.save_query_button.clicked.connect(self.save_query_as)
        self.open_query_library_button = QPushButton("Ouvrir un modèle…")
        self.open_query_library_button.setToolTip(tr("Charger un modèle depuis la bibliothèque Modèles de Requêtes", self.language))
        self.open_query_library_button.clicked.connect(self.open_query_from_library)
        self.save_query_library_button = QPushButton("Enregistrer ce modèle")
        self.save_query_library_button.setToolTip(tr("Conserver cette requête dans la bibliothèque Modèles de Requêtes", self.language))
        self.save_query_library_button.clicked.connect(self.save_query_to_library)
        self.update_query_button = QPushButton("Mettre à jour")
        self.update_query_button.clicked.connect(self.update_current_query)
        self.rename_query_button = QPushButton("Renommer…")
        self.rename_query_button.clicked.connect(self.rename_current_query)
        self.duplicate_query_button = QPushButton("Dupliquer…")
        self.duplicate_query_button.clicked.connect(self.duplicate_current_query)
        self.delete_query_button = QPushButton("Supprimer…")
        self.delete_query_button.clicked.connect(self.delete_current_query)

        # Le nom de la requête reste toujours lisible : la liste occupe sa propre ligne.
        saved_row.addWidget(saved_label)
        saved_row.addWidget(self.saved_queries_combo, 1)
        layout.addLayout(saved_row)

        saved_actions = QHBoxLayout()
        saved_actions.setSpacing(8)
        saved_actions.addStretch(1)
        self.save_query_button.setText(tr("Enregistrer la requête…", self.language).replace(" ", "\n", 1))
        self.save_query_library_button.setText(tr("Enregistrer ce modèle", self.language).replace(" ", "\n", 1))
        self.update_query_button.setText(tr("Mettre à jour", self.language).replace(" ", "\n", 1))
        for button in (
            self.save_query_button, self.open_query_library_button, self.save_query_library_button, self.update_query_button,
            self.rename_query_button, self.duplicate_query_button, self.delete_query_button,
        ):
            button.setMinimumHeight(42)
            button.setMinimumWidth(92)
        saved_actions.addWidget(self.save_query_button)
        saved_actions.addWidget(self.open_query_library_button)
        saved_actions.addWidget(self.save_query_library_button)
        saved_actions.addWidget(self.update_query_button)
        saved_actions.addWidget(self.rename_query_button)
        saved_actions.addWidget(self.duplicate_query_button)
        saved_actions.addWidget(self.delete_query_button)
        folder_btn = QPushButton("Dossiers…")
        folder_btn.clicked.connect(self._manage_query_folders)
        saved_actions.addWidget(folder_btn)
        layout.addLayout(saved_actions)

        # Classement des requêtes : menu secondaire compact.
        # Disposition validée : mode + flèches à gauche, liste persistante à droite.
        ranking_row = QHBoxLayout()
        ranking_row.setContentsMargins(0, 0, 0, 0)
        ranking_row.setSpacing(8)

        ranking_left = QHBoxLayout()
        ranking_left.setContentsMargins(0, 0, 0, 0)
        ranking_left.setSpacing(5)

        ranking_mode_label = QLabel("Mode de classement :")
        ranking_mode_label.setObjectName("secondaryLabel")

        self.query_order_combo = QComboBox()
        self.query_order_combo.setObjectName("rankingModeCombo")
        self.query_order_combo.setFixedWidth(205)
        self.query_order_combo.setFixedHeight(16)
        self.query_order_combo.addItem("Alphabétique", "alphabetical")
        self.query_order_combo.addItem("Alphabétique inverse", "reverse")
        self.query_order_combo.addItem("Personnalisé", "custom")
        self.query_order_combo.currentIndexChanged.connect(self._on_query_order_changed)

        self.query_up_button = QPushButton("▲")
        self.query_up_button.setObjectName("rankingArrow")
        self.query_up_button.setToolTip(tr("Monter la requête sélectionnée", self.language))
        self.query_up_button.setFixedSize(24, 18)
        self.query_up_button.clicked.connect(lambda: self._move_current_query(-1))

        self.query_down_button = QPushButton("▼")
        self.query_down_button.setObjectName("rankingArrow")
        self.query_down_button.setToolTip(tr("Descendre la requête sélectionnée", self.language))
        self.query_down_button.setFixedSize(24, 18)
        self.query_down_button.clicked.connect(lambda: self._move_current_query(1))

        ranking_left.addWidget(ranking_mode_label)
        ranking_left.addWidget(self.query_order_combo)
        ranking_left.addWidget(self.query_up_button)
        ranking_left.addWidget(self.query_down_button)

        ranking_row.addLayout(ranking_left, 0)
        ranking_row.addSpacing(8)

        self.custom_query_list = QListWidget()
        self.custom_query_list.setObjectName("customQueryList")
        self.custom_query_list.setFixedWidth(470)
        self.custom_query_list.setMinimumHeight(86)
        self.custom_query_list.setMaximumHeight(118)
        self.custom_query_list.currentTextChanged.connect(self._on_custom_query_selected)

        ranking_row.addWidget(self.custom_query_list, 1)
        layout.addLayout(ranking_row)

        self._refresh_saved_queries_combo()
        order_index = self.query_order_combo.findData(self.query_order_mode)
        self.query_order_combo.blockSignals(True)
        self.query_order_combo.setCurrentIndex(order_index if order_index >= 0 else 0)
        self.query_order_combo.blockSignals(False)
        self._refresh_custom_query_list(self.current_query_name)
        self._update_saved_query_buttons()

        headers = QHBoxLayout()
        headers.setContentsMargins(10, 0, 10, 0)
        headers.setSpacing(8)
        for text, width in (("Lien", 68), ("Champ", 180), ("Comparaison", 175)):
            label = QLabel(text)
            label.setObjectName("columnHeader")
            label.setFixedWidth(width)
            headers.addWidget(label)
        value_header = QLabel("Valeur")
        value_header.setObjectName("columnHeader")
        headers.addWidget(value_header, 1)
        action_header = QLabel("")
        action_header.setFixedWidth(170)
        headers.addWidget(action_header)
        layout.addLayout(headers)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.rows_container = QWidget()
        self.rows_layout = QVBoxLayout(self.rows_container)
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.rows_layout.setSpacing(7)
        self.rows_layout.addStretch(1)
        self.scroll.setWidget(self.rows_container)
        layout.addWidget(self.scroll, 1)

        add_row = QPushButton("+ Ajouter un critère")
        add_row.setObjectName("addCriterion")
        add_row.clicked.connect(self.add_criterion)
        layout.addWidget(add_row, 0, Qt.AlignmentFlag.AlignLeft)

        self.result_label = QLabel("Aucune requête exécutée.")
        self.result_label.setObjectName("queryResult")
        self.result_label.setWordWrap(True)
        layout.addWidget(self.result_label)

        actions = QHBoxLayout()
        clear_button = QPushButton("Réinitialiser la requête")
        clear_button.clicked.connect(self.clear_query)
        actions.addWidget(clear_button)
        actions.addStretch(1)

        back_button = QPushButton("Fermer")
        back_button.clicked.connect(self.close)

        execute_button = QPushButton("Exécuter la requête")
        execute_button.setObjectName("primaryButton")
        execute_button.clicked.connect(self.execute_query)

        actions.addWidget(back_button)
        actions.addWidget(execute_button)
        layout.addLayout(actions)

        self.setCentralWidget(root)
        self.add_criterion()

    def _apply_style(self) -> None:
        theme = collection_theme(self.database_path, self.collection)
        self.setStyleSheet(
            f"""
            #queryRoot {{ background: {theme['gradient']}; color: #24332B; }}
            #queryTitle {{ font-size: 24px; font-weight: 700; }}
            #querySubtitle, #queryResult {{ color: #607068; }}
            #columnHeader {{ color: #607068; font-weight: 650; }}
            #criterionRow {{ background: {theme['panel']}; border: 1px solid {theme['border']}; border-radius: 7px; }}
            QScrollArea {{ background: transparent; }}
            QScrollArea > QWidget > QWidget {{ background: transparent; }}
            QComboBox, QLineEdit {{
                min-height: 34px; padding: 3px 8px; background: white;
                border: 1px solid {theme['border']}; border-radius: 5px;
            }}
            QLineEdit:disabled {{ background: #EDF1EF; color: #7B8781; }}
            QPushButton {{
                min-height: 34px; padding: 4px 13px; background: #FFFFFF;
                color: #24332B; border: 1px solid {theme['border']}; border-radius: 5px;
            }}
            QPushButton:hover {{ background: {theme['hover']}; }}
            #secondaryLabel {{ color: #5F6F67; font-size: 11px; padding: 0px; }}
            QComboBox#rankingModeCombo {{ min-height: 0px; max-height: 16px; padding: 0px 20px 0px 6px; border-radius: 3px; font-size: 11px; }}
            QComboBox#rankingModeCombo::drop-down {{ width: 18px; border: none; }}
            #rankingArrow {{ padding: 0px; min-height: 0px; max-height: 18px; border-radius: 3px; font-size: 11px; font-weight: 700; }}
            #customQueryList {{ background: white; color: #24332B; border: 1px solid {theme['border']}; border-radius: 3px; padding: 1px; font-size: 11px; }}
            #customQueryList::item {{ padding: 2px 5px; min-height: 14px; }}
            #customQueryList::item:selected {{ background: {theme['header']}; color: #24332B; }}
            #addCriterion {{ font-weight: 650; }}
            #removeCriterion {{ padding-left: 9px; padding-right: 9px; }}
            #moveCriterion {{ font-size: 17px; font-weight: 700; padding: 0px; }}
            #moveCriterion:disabled {{ color: #A9B2AD; background: #F3F5F4; }}
            #primaryButton {{ background: #496C5B; color: white; border-color: #496C5B; }}
            #primaryButton:hover {{ background: #3C5B4C; }}
            """
        )

    def _values_for_field(self, field: str) -> list[str]:
        key = str(field or "")
        custom = self._custom_field_defs.get(key)
        if custom is not None:
            code = str(custom.get("referential_code") or "").strip()
        else:
            code = str(REFERENTIAL_BY_FIELD.get(key) or "").strip()
        if not code:
            return []
        values = self.referentials.list_values(
            int(self.collection["id"]), code, active_only=True
        )
        return [display_native_value(v, self.language) for v in values]

    def _collection_queries_key(self) -> str:
        return str(self.collection.get("id", self.collection.get("name", "")))

    def _load_saved_queries(self) -> None:
        entry = load_collection_models(self.database_path, self.collection["id"], "requete")
        if not entry.get("queries"):
            legacy = self._located_legacy_models("requete", self.queries_file, self._collection_queries_key(), "queries")
            if legacy:
                entry = {"queries": legacy, "last_query": None, "order_mode": "alphabetical", "custom_order": list(legacy)}
                save_collection_models(self.database_path, self.collection["id"], "requete", entry)
        queries = entry.get("queries", {})
        self.saved_queries = {str(name): value for name, value in queries.items() if isinstance(value, dict)} if isinstance(queries, dict) else {}
        last = entry.get("last_query")
        self.last_query_name = last if isinstance(last, str) and last in self.saved_queries else None
        mode = entry.get("order_mode", "alphabetical")
        self.query_order_mode = mode if mode in {"alphabetical", "reverse", "custom"} else "alphabetical"
        order = entry.get("custom_order", [])
        self.query_custom_order = [str(name) for name in order if str(name) in self.saved_queries] if isinstance(order, list) else []
        self.query_custom_order.extend(name for name in self.saved_queries if name not in self.query_custom_order)

    def _located_legacy_models(self, kind, filename, collection_key, models_key):
        try:
            data = json.loads(filename.read_text(encoding="utf-8"))
            models = data.get("collections", {}).get(collection_key, {}).get(models_key, {})
            if not isinstance(models, dict): return {}
            with sqlite3.connect(self.database_path) as con:
                names = {row[0] for row in con.execute(
                    "SELECT name FROM saved_model_locations WHERE collection_id=? AND kind=?",
                    (int(self.collection["id"]), kind))}
            return {name: state for name, state in models.items() if name in names and isinstance(state, dict)}
        except (OSError, ValueError, TypeError, KeyError, sqlite3.Error):
            return {}

    def _write_saved_queries(self) -> None:
        save_collection_models(self.database_path, self.collection["id"], "requete", {
            "queries": self.saved_queries,
            "last_query": self.last_query_name if self.last_query_name in self.saved_queries else None,
            "order_mode": self.query_order_mode,
            "custom_order": [name for name in self.query_custom_order if name in self.saved_queries],
        })

    def _ordered_query_names(self) -> list[str]:
        names = list(self.saved_queries)
        if self.query_order_mode == "reverse":
            return sorted(names, key=str.casefold, reverse=True)
        if self.query_order_mode == "custom":
            ordered = [name for name in self.query_custom_order if name in self.saved_queries]
            ordered.extend(name for name in names if name not in ordered)
            return ordered
        return sorted(names, key=str.casefold)

    def _refresh_custom_query_list(self, select_name: str | None = None) -> None:
        if not hasattr(self, "custom_query_list"):
            return
        visible = self.query_order_mode == "custom"
        self.custom_query_list.setEnabled(visible)
        self.custom_query_list.setStyleSheet("" if visible else "QListWidget { background: transparent; border: none; }")
        if not visible:
            self.custom_query_list.blockSignals(True)
            self.custom_query_list.clear()
            self.custom_query_list.blockSignals(False)
            return

        wanted = select_name or self.current_query_name
        self.custom_query_list.blockSignals(True)
        self.custom_query_list.clear()
        for name in self._ordered_query_names():
            self.custom_query_list.addItem(name)
        if wanted:
            matches = self.custom_query_list.findItems(wanted, Qt.MatchFlag.MatchExactly)
            if matches:
                self.custom_query_list.setCurrentItem(matches[0])
        self.custom_query_list.blockSignals(False)

    def _on_custom_query_selected(self, name: str) -> None:
        if self.query_order_mode != "custom":
            return
        name = str(name or "").strip()
        if not name or name not in self.saved_queries:
            return

        # Synchroniser la liste persistante avec la vraie requête chargée.
        # Avant 014.3.2, seul le nom changeait : les critères affichés restaient
        # ceux de la requête précédente, ce qui pouvait ensuite écraser la
        # mauvaise requête avec « Mettre à jour ».
        combo_index = self.saved_queries_combo.findData(name)
        self.saved_queries_combo.blockSignals(True)
        if combo_index >= 0:
            self.saved_queries_combo.setCurrentIndex(combo_index)
        self.saved_queries_combo.blockSignals(False)

        state = self.saved_queries.get(name)
        if isinstance(state, dict):
            self._apply_query_state(name, state)

        self._update_saved_query_buttons()

    def _on_query_order_changed(self, _index: int) -> None:
        if not hasattr(self, "query_order_combo"):
            return
        mode = self.query_order_combo.currentData()
        if mode not in {"alphabetical", "reverse", "custom"}:
            mode = "alphabetical"
        self.query_order_mode = str(mode)
        for name in self._ordered_query_names():
            if name not in self.query_custom_order:
                self.query_custom_order.append(name)
        self._write_saved_queries()
        self._refresh_saved_queries_combo(self.current_query_name)
        self._refresh_custom_query_list(self.current_query_name)
        self._update_saved_query_buttons()

    def _move_current_query(self, direction: int) -> None:
        if self.query_order_mode != "custom":
            return

        name = self.current_query_name
        if hasattr(self, "custom_query_list"):
            item = self.custom_query_list.currentItem()
            if item is not None:
                name = item.text()

        if not name or name not in self.saved_queries:
            return

        current_order = self._ordered_query_names()
        self.query_custom_order = current_order[:]
        try:
            index = self.query_custom_order.index(name)
        except ValueError:
            return

        target = index + int(direction)
        if target < 0 or target >= len(self.query_custom_order):
            self._update_saved_query_buttons()
            return

        self.query_custom_order[index], self.query_custom_order[target] = (
            self.query_custom_order[target],
            self.query_custom_order[index],
        )
        self.current_query_name = name
        self._write_saved_queries()
        self._refresh_saved_queries_combo(name)
        self._refresh_custom_query_list(name)
        self._update_saved_query_buttons()

    def _manage_query_folders(self) -> None:
        manage_folders(self, self.database_path, int(self.collection["id"]),
                       "requete", self.saved_queries, self._refresh_saved_queries_combo)

    def _query_folder(self, name: str) -> str:
        return model_folders.folder_for(self.database_path, int(self.collection["id"]), "requete", name)

    def _refresh_saved_queries_combo(self, select_name: str | None = None) -> None:
        if not hasattr(self, "saved_queries_combo"):
            return
        wanted = (
            select_name
            if select_name is not None
            else (self.current_query_name or self.last_query_name)
        )
        self.saved_queries_combo.blockSignals(True)
        self.saved_queries_combo.clear()
        self.saved_queries_combo.addItem("— Nouvelle requête —  ▼", None)
        for name in self._ordered_query_names():
            folder = self._query_folder(name)
            self.saved_queries_combo.addItem(f"{name}  ▼", name)
        index = self.saved_queries_combo.findData(wanted) if wanted else 0
        self.saved_queries_combo.setCurrentIndex(index if index >= 0 else 0)
        self.saved_queries_combo.blockSignals(False)
        self.current_query_name = wanted if wanted in self.saved_queries else None
        self._refresh_custom_query_list(self.current_query_name)
        self._update_saved_query_buttons()

    def _update_saved_query_buttons(self) -> None:
        if self.current_query_name:
            self.active_model_name = self.current_query_name
        self._refresh_active_model_name()
        active = bool(self.current_query_name and self.current_query_name in self.saved_queries)
        if hasattr(self, "update_query_button"):
            self.update_query_button.setEnabled(active)
            self.rename_query_button.setEnabled(active)
            if hasattr(self, "duplicate_query_button"):
                self.duplicate_query_button.setEnabled(active)
            self.delete_query_button.setEnabled(active)

        if hasattr(self, "query_up_button"):
            can_move = self.query_order_mode == "custom"
            selected_name = self.current_query_name
            if hasattr(self, "custom_query_list"):
                item = self.custom_query_list.currentItem()
                if item is not None:
                    selected_name = item.text()

            names = self._ordered_query_names() if can_move else []
            index = names.index(selected_name) if can_move and selected_name in names else -1
            self.query_up_button.setEnabled(can_move and index > 0)
            self.query_down_button.setEnabled(can_move and 0 <= index < len(names) - 1)

    def _capture_query_state(self) -> dict:
        criteria = []
        for row in self.criterion_rows:
            criterion = row.criterion()
            if criterion is not None:
                if not criteria:
                    criterion["connector"] = "and"
                criteria.append(criterion)
        return {"criteria": criteria}

    def _apply_query_state(self, name: str, state: dict) -> None:
        criteria = state.get("criteria", [])
        if not isinstance(criteria, list) or not criteria:
            return

        while self.criterion_rows:
            row = self.criterion_rows.pop()
            self.rows_layout.removeWidget(row)
            row.deleteLater()

        # Le constructeur travaille toujours sur une copie détachée.
        # Ainsi, éditer une requête chargée ne peut jamais modifier en mémoire
        # la définition enregistrée d'une autre requête.
        editor_criteria = copy.deepcopy(criteria)
        for criterion in editor_criteria:
            if not isinstance(criterion, dict):
                continue
            self.add_criterion()
            self.criterion_rows[-1].set_criterion(criterion)

        self.current_query_name = name
        self.last_query_name = name
        self.active_model_name = name
        self._refresh_active_model_name()
        self._write_saved_queries()
        self._refresh_first_row_state()
        self.result_label.setText(tr('Requête enregistrée « {name} » chargée. Cliquez sur Exécuter la requête.', self.language).format(name=name))
        self._update_saved_query_buttons()

    def _on_saved_query_selected(self, _index: int) -> None:
        if self._loading_saved_query:
            return
        name = self.saved_queries_combo.currentData()
        if not name:
            self.current_query_name = None
            self.active_model_name = None
            self._refresh_active_model_name()
            self._update_saved_query_buttons()
            return
        state = self.saved_queries.get(str(name))
        if isinstance(state, dict):
            self._apply_query_state(str(name), state)

    def open_query_from_library(self) -> bool:
        root = library_root(workspace_root_from_database(self.database_path), "requete")
        filename = choose_model_open_path(self, root, "Modèles de Requêtes")
        if not filename: return False
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        QApplication.processEvents()
        try:
            envelope = read_model(filename, expected_kind="requete")
            state = resolve_model_fields(self, envelope, self.model_manager, int(self.collection["id"]), "requete")
            if state is None:
                return False
            self._custom_field_defs = self.model_manager.custom_field_map(int(self.collection["id"]))
            self.columns = self._collection_columns(tuple(self.columns))
            self.active_model_name = Path(filename).stem
            self._apply_query_state(Path(filename).stem, state)
            self._refresh_active_model_name()
        except Exception as exc:
            QMessageBox.critical(self, "Ouverture impossible", str(exc)); return False
        finally:
            QApplication.restoreOverrideCursor()
        return True

    def save_query_to_library(self) -> None:
        state = self._capture_query_state()
        if not state.get("criteria"):
            QMessageBox.information(self, "Requête vide", "Ajoutez au moins un critère complet avant d’enregistrer un modèle de requête.")
            return
        root = library_root(workspace_root_from_database(self.database_path), "requete")
        default_name = self.current_query_name or "Modèle de requête"
        filename = choose_model_save_path(self, root, default_name, "Modèles de Requêtes")
        if not filename:
            return
        try:
            manifest = build_field_manifest(self.model_manager, int(self.collection["id"]), collect_model_field_keys("requete", state))
            write_model(filename, kind="requete", name=Path(filename).stem, source_collection=str(self.collection.get("name") or ""), payload=state, field_manifest=manifest)
        except Exception as exc:
            QMessageBox.critical(self, "Enregistrement impossible", str(exc)); return
        self.active_model_name = Path(filename).stem
        self._refresh_active_model_name()
        QMessageBox.information(self, "Modèle de Requête", "Le modèle a été enregistré dans la bibliothèque Modèles de Requêtes.")

    def save_query_as(self) -> None:
        state = self._capture_query_state()
        if not state["criteria"]:
            QMessageBox.information(self, "Requête vide", "Ajoutez au moins un critère complet avant d’enregistrer la requête.")
            return
        name, ok = QInputDialog.getText(self, "Enregistrer la requête", "Nom de la requête :")
        if not ok:
            return
        name = name.strip()
        if not name:
            return
        if name in self.saved_queries:
            answer = QMessageBox.question(
                self, "Requête existante",
                f'La requête « {name} » existe déjà. Voulez-vous la remplacer ?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        folder = choose_folder(self, self.database_path, int(self.collection["id"]),
                               "requete", self._query_folder(name))
        if folder is None: return
        self.saved_queries[name] = state
        model_folders.assign(self.database_path, int(self.collection["id"]), "requete", name, folder)
        if name not in self.query_custom_order:
            self.query_custom_order.append(name)
        self._write_saved_queries()
        self.current_query_name = name
        self.last_query_name = name
        self._write_saved_queries()
        self._refresh_saved_queries_combo(name)

    def update_current_query(self) -> None:
        name = self.current_query_name
        if not name or name not in self.saved_queries:
            return
        state = self._capture_query_state()
        if not state["criteria"]:
            QMessageBox.information(self, "Requête vide", "Une requête enregistrée doit contenir au moins un critère complet.")
            return
        folder = choose_folder(self, self.database_path, int(self.collection["id"]),
                               "requete", self._query_folder(name))
        if folder is None: return
        self.saved_queries[name] = copy.deepcopy(state)
        model_folders.assign(self.database_path, int(self.collection["id"]), "requete", name, folder)
        self.last_query_name = name
        self._write_saved_queries()
        self._refresh_saved_queries_combo(name)

    def rename_current_query(self) -> None:
        old_name = self.current_query_name
        if not old_name or old_name not in self.saved_queries:
            return
        name, ok = QInputDialog.getText(
            self, "Renommer la requête", "Nouveau nom :", text=old_name
        )
        if not ok:
            return
        name = name.strip()
        if not name or name == old_name:
            return
        if name in self.saved_queries:
            QMessageBox.information(self, "Nom déjà utilisé", f'Une requête nommée « {name} » existe déjà.')
            return
        self.saved_queries[name] = self.saved_queries.pop(old_name)
        model_folders.rename_item(self.database_path, int(self.collection["id"]), "requete", old_name, name)
        self.query_custom_order = [
            name if item == old_name else item for item in self.query_custom_order
        ]
        if self.last_query_name == old_name:
            self.last_query_name = name
        self._write_saved_queries()
        self.current_query_name = name
        self._refresh_saved_queries_combo(name)

    def duplicate_current_query(self) -> None:
        """Crée une copie indépendante de la requête enregistrée sélectionnée."""
        source_name = self.current_query_name
        if not source_name or source_name not in self.saved_queries:
            return

        suggested_name = f"{source_name} - copie"
        name, ok = QInputDialog.getText(
            self,
            "Dupliquer la requête",
            "Nom de la nouvelle requête :",
            text=suggested_name,
        )
        if not ok:
            return

        name = name.strip()
        if not name:
            return

        if name in self.saved_queries:
            QMessageBox.information(
                self,
                "Nom déjà utilisé",
                f'Une requête nommée « {name} » existe déjà.',
            )
            return

        source_state = self.saved_queries[source_name]
        copied_state = copy.deepcopy(source_state)
        self.saved_queries[name] = copied_state
        model_folders.assign(self.database_path, int(self.collection["id"]), "requete", name, self._query_folder(source_name))

        if name not in self.query_custom_order:
            if source_name in self.query_custom_order:
                source_index = self.query_custom_order.index(source_name)
                self.query_custom_order.insert(source_index + 1, name)
            else:
                self.query_custom_order.append(name)

        self.current_query_name = name
        self.last_query_name = name
        self._write_saved_queries()
        self._refresh_saved_queries_combo(name)

        self._apply_query_state(name, copied_state)
        self._refresh_custom_query_list(name)
        self._update_saved_query_buttons()

    def delete_current_query(self) -> None:
        name = self.current_query_name
        if not name or name not in self.saved_queries:
            return
        answer = QMessageBox.question(
            self, "Supprimer cette requête",
            f'Supprimer la requête enregistrée « {name} » ?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.saved_queries.pop(name, None)
        model_folders.delete_item(self.database_path, int(self.collection["id"]), "requete", name)
        self.query_custom_order = [item for item in self.query_custom_order if item != name]
        if self.last_query_name == name:
            self.last_query_name = None
        self._write_saved_queries()
        self.current_query_name = None
        self._refresh_saved_queries_combo(None)
        self.clear_query()

    def add_criterion(self) -> None:
        row = QueryCriterionRow(
            self.columns,
            self.remove_criterion,
            self.move_criterion_up,
            self.move_criterion_down,
            self._values_for_field,
            self.numeric_fields,
            self.date_fields,
            self.language,
            self.rows_container,
        )
        self.rows_layout.insertWidget(max(0, self.rows_layout.count() - 1), row)
        self.criterion_rows.append(row)
        self._refresh_first_row_state()
        row.value_edit.lineEdit().returnPressed.connect(self.execute_query)
        if row.value_edit.isEnabled():
            row.value_edit.setFocus()
        else:
            row.field_combo.setFocus()

    def _move_criterion(self, row: QueryCriterionRow, delta: int) -> None:
        if row not in self.criterion_rows:
            return
        old_index = self.criterion_rows.index(row)
        new_index = old_index + delta
        if new_index < 0 or new_index >= len(self.criterion_rows):
            return

        self.criterion_rows.pop(old_index)
        self.criterion_rows.insert(new_index, row)

        # Retirer puis réinsérer le widget avant le stretch final.
        self.rows_layout.removeWidget(row)
        self.rows_layout.insertWidget(new_index, row)
        self._refresh_first_row_state()
        row.setFocus()

    def move_criterion_up(self, row: QueryCriterionRow) -> None:
        self._move_criterion(row, -1)

    def move_criterion_down(self, row: QueryCriterionRow) -> None:
        self._move_criterion(row, 1)

    def remove_criterion(self, row: QueryCriterionRow) -> None:
        if row not in self.criterion_rows:
            return
        if len(self.criterion_rows) == 1:
            row.clear_value()
            row.field_combo.setCurrentIndex(0)
            row.connector_combo.setCurrentIndex(0)
            return
        self.criterion_rows.remove(row)
        self.rows_layout.removeWidget(row)
        row.deleteLater()
        self._refresh_first_row_state()

    def _refresh_first_row_state(self) -> None:
        last_index = len(self.criterion_rows) - 1
        for index, row in enumerate(self.criterion_rows):
            row.set_first(index == 0)
            row.set_move_state(index > 0, index < last_index)

    def focus_value(self, select_all: bool = False) -> None:
        if not self.criterion_rows:
            self.add_criterion()
        row = self.criterion_rows[0]
        if row.value_edit.isEnabled():
            row.value_edit.setFocus()
            if select_all:
                row.value_edit.selectAll()
        else:
            row.operator_combo.setFocus()

    def clear_query(self) -> None:
        self.current_query_name = None
        if hasattr(self, "saved_queries_combo"):
            self._refresh_saved_queries_combo(None)
        while len(self.criterion_rows) > 1:
            row = self.criterion_rows.pop()
            self.rows_layout.removeWidget(row)
            row.deleteLater()
        if not self.criterion_rows:
            self.add_criterion()
        first = self.criterion_rows[0]
        first.field_combo.setCurrentIndex(0)
        first.connector_combo.setCurrentIndex(0)
        first.clear_value()
        self.result_label.setText("Aucune requête exécutée.")
        self.focus_value()

    def execute_query(self) -> None:
        criteria: list[dict[str, str]] = []
        for row in self.criterion_rows:
            criterion = row.criterion()
            if criterion is None:
                continue
            if not criteria:
                criterion["connector"] = "and"
            criterion["value"] = canonical_native_value(
                str(criterion.get("value", "")), self.language
            )
            criterion["value2"] = canonical_native_value(
                str(criterion.get("value2", "")), self.language
            )
            criteria.append(criterion)

        if not criteria:
            self.result_label.setText("Saisissez au moins un critère complet avant d’exécuter la requête.")
            self.focus_value()
            return

        count = int(self.execute_callback(criteria))
        suffix = "fiche trouvée" if count == 1 else "fiches trouvées"
        criterion_suffix = "critère" if len(criteria) == 1 else "critères"
        self.result_label.setText(
            f"Résultat : {count} {suffix} avec {len(criteria)} {criterion_suffix}. "
            "La Vue Tableau a été actualisée."
        )
