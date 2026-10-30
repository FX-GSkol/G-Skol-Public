#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from pathlib import Path
import json
import shutil
import tempfile
import zipfile

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QComboBox,
    QListWidget,
    QListWidgetItem,
    QFileDialog,
    QHeaderView,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from core.collection_manager import CollectionManager
from core.collection_folders import CollectionFolderStore, UNCLASSIFIED
from core.i18n import tr, translate_widget_tree


class OpenCollectionDialog(QDialog):
    """Sélection et gestion contextuelle des collections existantes."""

    def __init__(self, collections: list[dict], manager: CollectionManager, parent=None, language: str='fr') -> None:
        super().__init__(parent)
        self.language=language or 'fr'
        self.setWindowTitle(tr("Ouvrir une collection",self.language))
        self.resize(980, 460)
        self.manager = manager
        self._collections = collections
        self._selected: dict | None = None
        self.folder_store = CollectionFolderStore(self.manager.collections_folder())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        title = QLabel(tr("Choisissez une collection à ouvrir",self.language))
        title.setStyleSheet("font-size: 18px; font-weight: 650;")
        layout.addWidget(title)

        self.table = QTreeWidget(self)
        self.table.setColumnCount(5)
        self.table.setHeaderLabels([tr(x,self.language) for x in ["Collection","Taille (Mo)","Propriétaire","Créée le","Description"]])
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        header = self.table.header()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)
        self.table.setColumnWidth(0, 330)
        self.table.setColumnWidth(1, 90)
        self.table.setColumnWidth(2, 150)
        self.table.setColumnWidth(3, 190)
        self.table.itemDoubleClicked.connect(self._accept_selected)
        self.table.itemSelectionChanged.connect(self._update_buttons)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self.table, 1)

        actions = QHBoxLayout()
        self.open_button = QPushButton(tr("Ouvrir",self.language))
        self.rename_button = QPushButton(tr("Renommer…",self.language))
        self.duplicate_button = QPushButton(tr("Dupliquer…",self.language))
        self.delete_button = QPushButton(tr("Supprimer…",self.language))
        self.folder_button = QPushButton(tr("Nouveau dossier…",self.language))
        self.move_button = QPushButton(tr("Déplacer vers…",self.language))
        browse_button = QPushButton(tr("Parcourir…",self.language))
        cancel_button = QPushButton(tr("Fermer",self.language))

        self.open_button.setDefault(True)
        self.open_button.clicked.connect(self._accept_selected)
        self.rename_button.clicked.connect(self._rename_selected_item)
        self.duplicate_button.clicked.connect(self._duplicate_selected)
        self.delete_button.clicked.connect(self._delete_selected_item)
        self.folder_button.clicked.connect(self._create_folder)
        self.move_button.clicked.connect(self._move_selected)
        browse_button.clicked.connect(self._browse_file)
        cancel_button.clicked.connect(self.reject)

        actions.addWidget(self.open_button)
        actions.addWidget(self.rename_button)
        actions.addWidget(self.duplicate_button)
        actions.addWidget(self.delete_button)
        actions.addWidget(self.folder_button)
        actions.addWidget(self.move_button)
        actions.addStretch(1)
        actions.addWidget(browse_button)
        actions.addWidget(cancel_button)
        layout.addLayout(actions)

        self._populate()
        self._update_buttons()

    def showEvent(self, event) -> None:
        """Rescanne les fichiers juste avant chaque affichage de la liste."""
        super().showEvent(event)
        self._refresh_files(preserve_selection=True)

    def _refresh_files(self, *_args, preserve_selection: bool = True) -> None:
        current = self._current_collection() if preserve_selection else None
        selected_id = int(current.get("id")) if current and current.get("id") is not None else None
        selected_db = str(current.get("_database_path") or "") if current else None
        self._populate(selected_id, selected_db)

    def _populate(self, selected_id: int | None = None, selected_db: str | None = None) -> None:
        expanded = set()
        def remember(item):
            folder = item.data(0, Qt.ItemDataRole.UserRole + 1)
            if folder is not None and item.isExpanded():
                expanded.add(str(folder))
            for n in range(item.childCount()):
                remember(item.child(n))
        for n in range(self.table.topLevelItemCount()):
            remember(self.table.topLevelItem(n))
        all_collections = [dict(item) for item in self.manager.discover_collection_files()]
        for item in all_collections:
            item["_folder_name"] = self.folder_store.folder_for(item.get("_database_path", ""))
        self._collections = all_collections
        self.table.blockSignals(True)
        self.table.clear()
        root = QTreeWidgetItem(self.table, ["📁 " + tr("Collections (racine)", self.language)])
        root.setData(0, Qt.ItemDataRole.UserRole + 1, "")
        root.setExpanded(True)
        nodes = {"": root}
        paths = set(self.folder_store.data.get("folders", []))
        for collection in all_collections:
            folder = str(collection.get("_folder_name") or UNCLASSIFIED)
            if folder != UNCLASSIFIED:
                while folder:
                    paths.add(folder)
                    folder = folder.rpartition("/")[0]
        for path in sorted(paths, key=lambda x: (x.count("/"), x.casefold())):
            if path == UNCLASSIFIED:
                continue
            parent = nodes.get(path.rpartition("/")[0], root)
            item = QTreeWidgetItem(parent, ["📁 " + path.rpartition("/")[2]])
            item.setData(0, Qt.ItemDataRole.UserRole + 1, path)
            item.setExpanded(path in expanded)
            nodes[path] = item
        selected_item = None
        for collection in sorted(all_collections, key=lambda c: str(c.get("name", "")).casefold()):
            folder = str(collection.get("_folder_name") or UNCLASSIFIED)
            parent = nodes.get(folder, root)
            db_path = Path(str(collection.get("_database_path", "") or ""))
            try:
                size_mb = f"{db_path.stat().st_size / (1024 * 1024):.2f} Mo" if db_path.is_file() else ""
            except OSError:
                size_mb = ""
            item = QTreeWidgetItem(parent, ["📄 " + str(collection.get("name", "")),
                                           size_mb,
                                           str(collection.get("owner", "") or ""),
                                           str(collection.get("created_at", "") or ""),
                                           str(collection.get("description", "") or "")])
            item.setData(0, Qt.ItemDataRole.UserRole, collection)
            if selected_id is not None and int(collection["id"]) == int(selected_id):
                if selected_db is None or str(collection.get("_database_path", "")).casefold() == str(selected_db).casefold():
                    selected_item = item
        self.table.clearSelection()
        if selected_item is not None:
            self.table.setCurrentItem(selected_item)
            parent = selected_item.parent()
            while parent is not None:
                parent.setExpanded(True)
                parent = parent.parent()
        self.table.blockSignals(False)
        self._update_buttons()

    def _selected_collections(self) -> list[dict]:
        return [item.data(0, Qt.ItemDataRole.UserRole)
                for item in self.table.selectedItems()
                if isinstance(item.data(0, Qt.ItemDataRole.UserRole), dict)]

    def _selected_folder(self) -> str | None:
        item = self.table.currentItem()
        if item is None or isinstance(item.data(0, Qt.ItemDataRole.UserRole), dict):
            return None
        return str(item.data(0, Qt.ItemDataRole.UserRole + 1) or "")

    def _assign_selected_to_folder(self, folder_name: str) -> None:
        selected = self._selected_collections()
        if not selected: return
        self.folder_store.assign([c.get("_database_path", "") for c in selected], folder_name)
        self._populate()

    def _create_folder(self) -> None:
        parent = self._selected_folder() or ""
        name, ok = QInputDialog.getText(self, "Nouveau dossier", "Nom du dossier :")
        if not ok or not str(name).strip(): return
        try:
            path = parent + "/" + str(name).strip() if parent else str(name).strip()
            self.folder_store.add_folder(path)
        except ValueError as exc:
            QMessageBox.warning(self, "Dossier invalide", str(exc))
            return
        self._populate()
        self._select_folder(path)

    def _select_folder(self, path: str) -> None:
        def find(item):
            if str(item.data(0, Qt.ItemDataRole.UserRole + 1) or "") == path:
                return item
            for n in range(item.childCount()):
                result = find(item.child(n))
                if result is not None: return result
            return None
        for n in range(self.table.topLevelItemCount()):
            item = find(self.table.topLevelItem(n))
            if item is not None:
                self.table.setCurrentItem(item)
                parent = item.parent()
                while parent is not None:
                    parent.setExpanded(True)
                    parent = parent.parent()
                break

    def _move_selected(self) -> None:
        selected = self._selected_collections()
        if not selected: return
        choices = ["Collections (racine)"] + sorted(self.folder_store.data.get("folders", []), key=str.casefold)
        destination, ok = QInputDialog.getItem(self, "Déplacer les collections", "Déplacer vers :", choices, 0, False)
        if not ok: return
        target = UNCLASSIFIED if destination == choices[0] else destination
        self._assign_selected_to_folder(target)

    def _rename_folder(self, path: str) -> None:
        label, ok = QInputDialog.getText(self, "Renommer le dossier", "Nouveau nom :", text=path.rpartition("/")[2])
        if not ok or not str(label).strip(): return
        target = path.rpartition("/")[0]
        target = target + "/" + str(label).strip() if target else str(label).strip()
        try: self.folder_store.rename_folder(path, target)
        except ValueError as exc:
            QMessageBox.warning(self, "Renommage impossible", str(exc)); return
        self._populate(); self._select_folder(target)

    def _delete_folder(self, path: str) -> None:
        affected = [c for c in self.manager.discover_collection_files()
                    if (self.folder_store.folder_for(c.get("_database_path", "")).casefold() == path.casefold()
                        or self.folder_store.folder_for(c.get("_database_path", "")).casefold().startswith(path.casefold()+"/"))]
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Supprimer le dossier")
        box.setText(f"Supprimer le dossier « {path} » ?")
        if affected:
            box.setInformativeText(f"Ce dossier contient {len(affected)} collection(s). Elles seront déplacées à la racine ; aucune collection ne sera supprimée.")
        yes = box.addButton("Supprimer le dossier", QMessageBox.ButtonRole.DestructiveRole)
        no = box.addButton(tr("Annuler", self.language), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(no)
        box.exec()
        if box.clickedButton() is yes:
            self.folder_store.delete_folder(path)
            self._populate()

    def _delete_selected_item(self) -> None:
        folder = self._selected_folder()
        if folder is not None:
            if folder: self._delete_folder(folder)
            return
        self._delete_selected()

    def _manage_folders(self) -> None:
        self._create_folder()

    def _current_collection(self) -> dict | None:
        item = self.table.currentItem()
        if item is None or not item.isSelected(): return None
        value = item.data(0, Qt.ItemDataRole.UserRole)
        return value if isinstance(value, dict) else None

    def _show_context_menu(self, position: QPoint) -> None:
        item = self.table.itemAt(position)
        if item is None: return
        if not item.isSelected(): self.table.setCurrentItem(item)
        collection = item.data(0, Qt.ItemDataRole.UserRole)
        folder = item.data(0, Qt.ItemDataRole.UserRole + 1)
        menu = QMenu(self)
        if not isinstance(collection, dict):
            create = menu.addAction(tr("Nouveau dossier…", self.language))
            rename = menu.addAction(tr("Renommer…", self.language)) if folder else None
            delete = menu.addAction(tr("Supprimer…", self.language)) if folder else None
            action = menu.exec(self.table.viewport().mapToGlobal(position))
            if action is create: self._create_folder()
            elif action is rename: self._rename_folder(str(folder))
            elif action is delete: self._delete_folder(str(folder))
            return
        open_action = menu.addAction(tr("Ouvrir", self.language))
        menu.addSeparator()
        rename_action = menu.addAction(tr("Renommer…", self.language))
        info_menu = menu.addMenu(tr("Modifier les informations", self.language))
        owner_action = info_menu.addAction(tr("Propriétaire…", self.language))
        date_action = info_menu.addAction(tr("Date de création…", self.language))
        description_action = info_menu.addAction(tr("Description…", self.language))
        move_action = menu.addAction(tr("Déplacer vers…", self.language))
        duplicate_action = menu.addAction(tr("Dupliquer…", self.language))
        delete_action = menu.addAction(tr("Supprimer…", self.language))
        action = menu.exec(self.table.viewport().mapToGlobal(position))
        if action is open_action: self._accept_selected()
        elif action is rename_action: self._rename_selected()
        elif action is owner_action: self._edit_owner()
        elif action is date_action: self._edit_created_at()
        elif action is description_action: self._edit_description()
        elif action is move_action: self._move_selected()
        elif action is duplicate_action: self._duplicate_selected()
        elif action is delete_action: self._delete_selected()

    def _refresh_after_metadata_change(self, updated: dict, database_path: str) -> None:
        self._populate(
            int(updated["id"]),
            str(database_path or ""),
        )

    def _edit_owner(self) -> None:
        collection = self._current_collection()
        if collection is None:
            return
        value, accepted = QInputDialog.getText(
            self,
            "Modifier le propriétaire",
            "Propriétaire :\n(Laisser vide pour supprimer)",
            text=str(collection.get("owner", "") or ""),
        )
        if not accepted:
            return
        try:
            manager = self._manager_for_collection(collection)
            updated = manager.update_collection_metadata(
                int(collection["id"]), owner=value
            )
        except Exception as exc:
            QMessageBox.warning(self, "Modification impossible", str(exc))
            return
        self._refresh_after_metadata_change(
            updated, str(collection.get("_database_path", "") or "")
        )

    def _edit_created_at(self) -> None:
        collection = self._current_collection()
        if collection is None:
            return
        value, accepted = QInputDialog.getText(
            self,
            "Modifier la date de création",
            "Date de création :\n(Laisser vide pour supprimer)",
            text=str(collection.get("created_at", "") or ""),
        )
        if not accepted:
            return
        try:
            manager = self._manager_for_collection(collection)
            updated = manager.update_collection_metadata(
                int(collection["id"]), created_at=value
            )
        except Exception as exc:
            QMessageBox.warning(self, "Modification impossible", str(exc))
            return
        self._refresh_after_metadata_change(
            updated, str(collection.get("_database_path", "") or "")
        )

    def _edit_description(self) -> None:
        collection = self._current_collection()
        if collection is None:
            return
        value, accepted = QInputDialog.getMultiLineText(
            self,
            "Modifier la description",
            "Description :\n(Laisser vide pour supprimer)",
            str(collection.get("description", "") or ""),
        )
        if not accepted:
            return
        try:
            manager = self._manager_for_collection(collection)
            updated = manager.update_collection_metadata(
                int(collection["id"]), description=value
            )
        except Exception as exc:
            QMessageBox.warning(self, "Modification impossible", str(exc))
            return
        self._refresh_after_metadata_change(
            updated, str(collection.get("_database_path", "") or "")
        )

    def _prepare_file_mutation(self, collection: dict) -> bool:
        raw = collection.get("_database_path")
        if not raw:
            return True
        parent = self.parent()
        release = getattr(parent, "release_collection_file_for_mutation", None)
        if callable(release):
            return bool(release(raw))
        return True

    def _manager_for_collection(self, collection: dict) -> CollectionManager:
        raw = collection.get("_database_path")
        return CollectionManager(raw) if raw else self.manager

    def _rename_selected_item(self) -> None:
        folder = self._selected_folder()
        if folder is not None:
            if folder: self._rename_folder(folder)
            return
        self._rename_selected()

    def _rename_selected(self) -> None:
        collection = self._current_collection()
        if collection is None:
            return
        rename_dialog = QInputDialog(self)
        rename_dialog.setWindowTitle("Renommer la collection")
        rename_dialog.setLabelText("Nouveau nom :")
        rename_dialog.setTextValue(str(collection["name"]))
        rename_dialog.setOkButtonText("OK")
        rename_dialog.setCancelButtonText(tr("Annuler", self.language))
        accepted = rename_dialog.exec() == QDialog.DialogCode.Accepted
        new_name = rename_dialog.textValue()
        if not accepted:
            return
        if collection.get("_standalone_file") and not self._prepare_file_mutation(collection):
            return
        old_db_path = str(collection.get("_database_path", "") or "")
        try:
            selected_manager = self._manager_for_collection(collection)
            if collection.get("_standalone_file"):
                renamed = selected_manager.rename_standalone_collection(int(collection["id"]), new_name)
            else:
                renamed = selected_manager.rename_collection(int(collection["id"]), new_name)
        except Exception as exc:
            QMessageBox.warning(self, "Renommage impossible", str(exc))
            return
        new_db_path = str(renamed.get("_database_path", "") or "")
        if old_db_path and new_db_path:
            self.folder_store.migrate_path(old_db_path, new_db_path)
        renamed["_folder_name"] = self.folder_store.folder_for(new_db_path)
        self._populate(int(renamed["id"]), new_db_path)

    def _duplicate_selected(self) -> None:
        collection = self._current_collection()
        if collection is None:
            return

        suggested = f"{collection['name']} - Copie"
        new_name, accepted = QInputDialog.getText(
            self,
            "Dupliquer la collection",
            "Nom de la nouvelle collection :",
            text=suggested,
        )
        if not accepted:
            return

        try:
            selected_manager = self._manager_for_collection(collection)
            duplicated = selected_manager.duplicate_collection_to_file(
                int(collection["id"]),
                new_name.strip() or suggested,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Duplication impossible", str(exc))
            return

        self._populate(int(duplicated["id"]), str(duplicated.get("_database_path", "") or ""))
        QMessageBox.information(
            self,
            "Collection dupliquée",
            f"La collection « {collection['name']} » a été dupliquée sous le nom "
            f"« {duplicated['name']} ».\n\n"
            "La copie est un fichier indépendant et peut être modifiée sans affecter l’original.",
        )

    def _delete_selected(self) -> None:
        # La sélection multiple du QTreeWidget doit être conservée : currentItem()
        # ne représente qu'une seule des lignes sélectionnées.
        selected = self._selected_collections()
        if not selected:
            return
        # Dédupliquer par fichier et identifiant pour ne jamais supprimer deux fois.
        unique = {}
        for collection in selected:
            key = (str(collection.get("_database_path", "")).casefold(),
                   str(collection.get("id", "")))
            unique[key] = collection
        collections = list(unique.values())
        count = len(collections)
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(tr("Supprimer la collection", self.language))
        if count == 1:
            box.setText(tr("Supprimer définitivement la collection « {name} » ?", self.language).format(name=collections[0]["name"]))
            box.setInformativeText(tr("Toutes les fiches et tous les référentiels de cette collection seront supprimés.\nCette opération est irréversible.", self.language))
        else:
            box.setText(f"Supprimer définitivement {count} collections sélectionnées ?")
            box.setInformativeText("Toutes les fiches et tous les référentiels de ces collections seront supprimés. Cette opération est irréversible.\n\nCollections concernées :")
            box.setDetailedText("\n".join(str(c.get("name", "")) for c in collections))
        delete_button = box.addButton(tr("SUPPRIMER", self.language), QMessageBox.ButtonRole.DestructiveRole)
        cancel_button = box.addButton(tr("Annuler", self.language), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(cancel_button)
        box.exec()
        if box.clickedButton() is not delete_button:
            return
        deleted, failed = [], []
        for collection in collections:
            name = str(collection.get("name", ""))
            try:
                if collection.get("_standalone_file") and not self._prepare_file_mutation(collection):
                    failed.append(f"{name} : fichier utilisé ou opération annulée")
                    continue
                selected_manager = self._manager_for_collection(collection)
                if collection.get("_standalone_file"):
                    Path(selected_manager.db_path).unlink()
                else:
                    self.manager.delete_collection(int(collection["id"]))
                deleted.append(name)
            except Exception as exc:
                failed.append(f"{name} : {exc}")
        self._populate()
        if count > 1 or failed:
            message = f"{len(deleted)} collection(s) supprimée(s) sur {count}."
            if deleted:
                message += "\n\nCollections supprimées :\n" + "\n".join(deleted)
            if failed:
                message += "\n\nCollections non supprimées :\n" + "\n".join(failed)
                QMessageBox.warning(self, "Résultat de la suppression", message)
            else:
                QMessageBox.information(self, "Résultat de la suppression", message)


    def _browse_file(self) -> None:
        """Ouvre directement une collection contenue dans un fichier SQLite MM3.

        Le fichier n'est ni déplacé, ni copié, ni enregistré dans le catalogue.
        """
        start_dir = str(Path.home() / "Documents")
        if not Path(start_dir).exists():
            start_dir = str(Path.home())
        file_path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "Choisir un fichier de collection G-Skol",
            start_dir,
            "Collections G-Skol (*.coldb);;Structures G-Skol (*.colstr);;Tous les fichiers (*)",
        )
        if not file_path:
            return

        source_path = Path(file_path)
        temp_dir = None
        package_type = None
        manifest = {}
        try:
            # Les structures .colstr ne sont jamais ouvertes directement :
            # on extrait collection.db dans une copie de travail temporaire.
            if source_path.suffix.casefold() == ".colstr":
                temp_dir = Path(tempfile.mkdtemp(prefix="GSkol-externe-"))
                with zipfile.ZipFile(source_path, "r") as zf:
                    names = set(zf.namelist())
                    if "collection.db" not in names:
                        raise ValueError("Le paquet G-Skol ne contient pas collection.db.")
                    if "manifest.json" in names:
                        manifest = json.loads(zf.read("manifest.json").decode("utf-8-sig"))
                    package_type = str(manifest.get("package_type") or "")
                    with zf.open("collection.db") as src, (temp_dir / "collection.db").open("wb") as dst:
                        shutil.copyfileobj(src, dst)
                work_path = temp_dir / "collection.db"
            else:
                work_path = source_path
            external_manager = CollectionManager(work_path)
            collections = external_manager.inspect_collections()
        except Exception as exc:
            if temp_dir is not None:
                shutil.rmtree(temp_dir, ignore_errors=True)
            QMessageBox.warning(
                self,
                "Fichier non reconnu",
                "Ce fichier ne peut pas être ouvert comme une collection G-Skol.\n\n" + str(exc),
            )
            return

        if not collections:
            QMessageBox.information(
                self,
                "Aucune collection",
                "Ce fichier G-Skol ne contient aucune collection enregistrée.",
            )
            return

        if len(collections) == 1:
            selected = dict(collections[0])
        else:
            chooser = OpenCollectionDialog(collections, external_manager, self)
            chooser.setWindowTitle("Choisir la collection dans ce fichier")
            # Dans ce second niveau, la liste est déjà celle du fichier choisi.
            # Le bouton Parcourir reste disponible : cela permet de changer de
            # fichier sans revenir en arrière.
            if not chooser.exec():
                return
            selected = chooser.selected_collection()
            if selected is None:
                return
            selected = dict(selected)

        selected["_database_path"] = str(external_manager.db_path)
        if temp_dir is not None:
            selected["_external_temporary"] = True
            selected["_external_source"] = str(source_path)
            selected["_external_temp_dir"] = str(temp_dir)
            selected["_external_package_type"] = package_type or "structure"
        self._selected = selected
        self.accept()

    def _update_buttons(self) -> None:
        # Seule une sélection explicite de ligne active les actions. Le simple
        # fait que QTableWidget conserve une cellule courante ne suffit pas.
        collection = self._current_collection() is not None
        folder = self._selected_folder()
        self.open_button.setEnabled(collection)
        self.rename_button.setEnabled(collection or bool(folder))
        self.duplicate_button.setEnabled(collection)
        self.delete_button.setEnabled(collection or bool(folder))
        self.move_button.setEnabled(bool(self._selected_collections()))

    def _accept_selected(self, *_args) -> None:
        collection = self._current_collection()
        if collection is None:
            return
        self._selected = collection
        self.accept()

    def selected_collection(self) -> dict | None:
        return self._selected
